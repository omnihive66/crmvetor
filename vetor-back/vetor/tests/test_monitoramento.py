"""Monitoramento (SPEC-07): Kuma e Beszel → incidentes com linha do tempo, triagem, fora de ordem, falhas e diagnóstico."""
import json
import logging

import pytest
from django.core import mail

from taiga.permissions.choices import MEMBERS_PERMISSIONS
from tests import factories as f

from vetor import monitoramento
from vetor.models import EventoMonitoramento, Incidente, Perfil, RecursoMonitorado

pytestmark = pytest.mark.django_db
TOKEN = "token-de-teste-kuma"
TOKEN_B = "token-de-teste-beszel"


@pytest.fixture(autouse=True)
def ambiente(settings):
    settings.VETOR_PAPEL_SEM_PERFIL = "observador"
    settings.VETOR_MONITOR_TOKENS = {"kuma": [TOKEN], "beszel": [TOKEN_B]}
    settings.VETOR_MONITOR_JANELA_MIN = 15
    settings.VETOR_MONITOR_AVISO_MIN = 30


def pessoa(papel, **kw):
    user = f.UserFactory.create(**kw)
    Perfil.objects.create(user=user, papel=papel)
    return user


def kuma(status, hora, monitor_id=7, nome="Portal ACME", msg="", url="https://admin:senha@portal.acme.example/saude?token=x"):
    """Formato do provedor Webhook do Uptime Kuma 2.5.7 (heartbeat.time em UTC)."""
    return {"heartbeat": {"monitorID": monitor_id, "status": status, "time": f"2026-10-23 {hora}:00.000", "msg": msg or ("timeout" if status == 0 else "200 - OK"),
                          "ping": 120, "important": True, "duration": 60, "timezone": "America/Sao_Paulo", "localDateTime": "x"},
            "monitor": {"id": monitor_id, "name": nome, "type": "http", "url": url, "hostname": None, "port": None},
            "msg": f"[{nome}] [{'🔴 Down' if status == 0 else '✅ Up'}] ..."}


def beszel(titulo, mensagem="", sistema="abc123def"):
    """Shoutrrr generic com template=json no Beszel v0.21.1: {title, message}; o link vai no fim da mensagem."""
    return {"title": titulo, "message": f"{mensagem or titulo}\n\nhttps://beszel.vetor.example/system/{sistema}"}


def enviar(client, provedor, dados, token=None):
    cab = {} if token is False else {"HTTP_X_VETOR_TOKEN": token or (TOKEN if provedor == "kuma" else TOKEN_B)}
    return client.post(f"/api/v1/vetor/monitoramento/{provedor}/webhook", json.dumps(dados), content_type="application/json", **cab)


@pytest.fixture
def projeto():
    dono = pessoa("gestor", email="gestor@exemplo.com")
    proj = f.create_project(owner=dono)
    f.MembershipFactory.create(project=proj, user=dono, is_admin=True,
                               role=f.RoleFactory.create(project=proj, permissions=[p for p, _ in MEMBERS_PERMISSIONS]))
    return proj


def mapear(provedor, id_externo, proj):
    rec = RecursoMonitorado.objects.get(provedor=provedor, id_externo=id_externo)
    monitoramento.mapear(rec, proj)
    return rec


# Critério principal: queda → repetidos → recuperação = 1 incidente com linha do tempo ------------

def test_queda_alertas_repetidos_e_recuperacao_viram_um_incidente(client, projeto):
    enviar(client, "kuma", kuma(0, "10:00"))
    mapear("kuma", "7", projeto)  # estava em triagem; mapear cria a demanda do incidente aberto
    for hora in ("10:05", "10:10"):
        assert enviar(client, "kuma", kuma(0, hora)).status_code == 202
    assert enviar(client, "kuma", kuma(1, "10:20")).status_code == 202
    inc = Incidente.objects.get()
    assert (inc.estado, inc.ocorrencias, inc.tipo, inc.severidade) == ("recuperado", 3, "disponibilidade", "critica")
    assert inc.recuperado_em.isoformat() == "2026-10-23T10:20:00+00:00"
    assert [e.status for e in inc.eventos.order_by("ocorrido_em")] == ["down", "down", "down", "up"]
    assert inc.historia.subject == "[Incidente] Portal ACME fora do ar" and inc.historia.project == projeto
    assert not inc.historia.status.is_closed  # recuperação não conclui a demanda
    client.login(projeto.owner)
    detalhe = client.get(f"/api/v1/vetor/incidentes/{inc.id}")
    assert [p["status"] for p in detalhe.json()["linha_do_tempo"]] == ["down", "down", "down", "up"]


def test_reincidencia_na_janela_reabre_o_mesmo_e_fora_dela_abre_outro(client, projeto):
    for status, hora in ((0, "10:00"), (1, "10:05"), (0, "10:12")):  # 7 min depois de recuperar: dentro da janela de 15
        enviar(client, "kuma", kuma(status, hora))
    inc = Incidente.objects.get()
    assert (inc.estado, inc.reincidencias) == ("aberto", 1)
    enviar(client, "kuma", kuma(1, "10:20"))
    enviar(client, "kuma", kuma(0, "11:00"))  # 40 min depois: novo incidente
    assert Incidente.objects.count() == 2


def test_eventos_fora_de_ordem_nao_revertem_o_estado(client, projeto):
    enviar(client, "kuma", kuma(0, "10:00"))
    enviar(client, "kuma", kuma(1, "10:20"))
    enviar(client, "kuma", kuma(0, "10:10"))  # queda antiga chegando depois da recuperação
    inc = Incidente.objects.get()
    assert inc.estado == "recuperado" and inc.ultimo_evento_em.isoformat() == "2026-10-23T10:20:00+00:00"
    assert inc.eventos.count() == 3  # mas entra na linha do tempo
    enviar(client, "kuma", kuma(0, "11:00"))
    enviar(client, "kuma", kuma(1, "10:50"))  # recuperação antiga não fecha o incidente novo
    assert Incidente.objects.order_by("-aberto_em").first().estado == "aberto"


def test_reenvio_do_mesmo_heartbeat_nao_duplica(client, projeto):
    assert enviar(client, "kuma", kuma(0, "10:00")).status_code == 202
    assert enviar(client, "kuma", kuma(0, "10:00")).json()["status"] == "duplicado"
    assert EventoMonitoramento.objects.count() == 1 and Incidente.objects.get().ocorrencias == 1


# Triagem e mapeamento ---------------------------------------------------------------------------

def test_recurso_desconhecido_entra_em_triagem_sem_demanda_inventada(client, projeto):
    enviar(client, "kuma", kuma(0, "10:00", monitor_id=99, nome="Servidor X"))
    rec = RecursoMonitorado.objects.get(id_externo="99")
    assert rec.projeto is None and rec.nome == "Servidor X"
    inc = Incidente.objects.get()
    assert inc.historia is None and not mail.outbox
    admin, gestor = pessoa("administrador"), projeto.owner
    client.login(admin)
    assert [r["nome"] for r in client.get("/api/v1/vetor/recursos-monitorados?triagem=true").json()] == ["Servidor X"]
    assert client.patch(f"/api/v1/vetor/recursos-monitorados/{rec.id}", json.dumps({"projeto": 999999}), content_type="application/json").status_code == 400
    client.login(gestor)  # gestor não mapeia nem vê triagem
    assert client.get("/api/v1/vetor/recursos-monitorados").status_code == 403
    assert client.get("/api/v1/vetor/incidentes").json() == []  # incidente em triagem não aparece para o projeto
    client.login(admin)  # o Administrador mapeia para qualquer projeto, mesmo sem ser membro
    r = client.patch(f"/api/v1/vetor/recursos-monitorados/{rec.id}", json.dumps({"projeto": projeto.id}), content_type="application/json")
    assert r.status_code == 200 and r.json()["projeto"]["id"] == projeto.id
    inc.refresh_from_db()
    assert inc.historia and inc.historia.project == projeto  # incidente aberto ganha a demanda ao mapear
    client.login(gestor)
    assert [i["id"] for i in client.get("/api/v1/vetor/incidentes").json()] == [inc.id]
    client.login(pessoa("gestor"))
    assert client.get("/api/v1/vetor/incidentes").json() == []


# Beszel -----------------------------------------------------------------------------------------

def test_beszel_conexao_e_limites_incluindo_bateria_invertida(client, projeto):
    assert enviar(client, "beszel", beszel("Connection to web-01 is down 🔴")).status_code == 202
    enviar(client, "beszel", beszel("Connection to web-01 is up ✅"))
    enviar(client, "beszel", beszel("web-01 CPU above threshold", "CPU averaged 93.10% for the previous 10 minutes."))
    enviar(client, "beszel", beszel("web-01 CPU below threshold", "CPU averaged 40.00% for the previous 10 minutes."))
    enviar(client, "beszel", beszel("notebook battery below threshold", sistema="nb1"))
    rec = RecursoMonitorado.objects.get(provedor="beszel", id_externo="abc123def")
    assert rec.nome == "web-01"
    tipos = {(i.recurso.id_externo, i.tipo): i.estado for i in Incidente.objects.all()}
    assert tipos == {("abc123def", "disponibilidade"): "recuperado", ("abc123def", "limite:cpu"): "recuperado", ("nb1", "limite:battery"): "aberto"}
    ev = EventoMonitoramento.objects.filter(provedor="beszel").first()
    assert ev.url_origem == "https://beszel.vetor.example/system/abc123def" and ev.id_externo is None


def test_beszel_nome_com_espacos_e_metricas_compostas():
    casos = {"[FICTÍCIO] web 01 CPU above threshold": ("[FICTÍCIO] web 01", "limite:cpu", "alerta"),
             "db primário 15m load below threshold": ("db primário", "limite:15m load", "normal"),
             "app CPU I/O Wait above threshold": ("app", "limite:cpu i/o wait", "alerta"),
             "nas disk usage above threshold": ("nas", "limite:disk usage", "alerta")}
    for titulo, esperado in casos.items():
        c = monitoramento.normalizar_beszel(beszel(titulo))
        assert (c["nome"], c["tipo"], c["status"]) == esperado, titulo


def test_beszel_alerta_desconhecido_so_registra(client, projeto):
    enviar(client, "beszel", beszel("SMART failed on web-01: sda ❌"))
    assert EventoMonitoramento.objects.get().status == "info" and not Incidente.objects.exists()


# Segurança, dados sensíveis e retenção ----------------------------------------------------------

def test_sem_token_falha_e_sem_configuracao_nao_esta_ativo(client, settings):
    assert enviar(client, "kuma", kuma(0, "10:00"), token=False).status_code == 401
    assert enviar(client, "kuma", kuma(0, "10:00"), token=TOKEN_B).status_code == 401  # token de outro provedor
    assert enviar(client, "kuma", {"lixo": True}).status_code == 400
    assert enviar(client, "zabbix", {}).status_code == 404
    settings.VETOR_MONITOR_TOKENS = {"kuma": [], "beszel": []}
    assert enviar(client, "kuma", kuma(0, "10:00")).status_code == 503
    assert not EventoMonitoramento.objects.exists()


def test_payload_sem_credenciais_token_fora_do_log_e_retencao(client, caplog, settings):
    caplog.set_level(logging.DEBUG)
    enviar(client, "kuma", kuma(0, "10:00"))
    enviar(client, "kuma", kuma(0, "10:01"), token="errado")
    ev = EventoMonitoramento.objects.get()
    guardado = json.dumps(ev.payload)
    assert "senha" not in guardado and "token=x" not in guardado and ev.url_origem == "https://portal.acme.example/saude"
    assert TOKEN not in caplog.text and "errado" not in caplog.text
    settings.VETOR_MONITOR_RETENCAO_DIAS = 0
    assert monitoramento.limpar_payloads() == 1
    ev.refresh_from_db()
    assert ev.payload is None and ev.status == "down"  # a linha do tempo continua


def test_notificacao_ao_responsavel_com_controle_de_frequencia(client, projeto):
    enviar(client, "kuma", kuma(0, "10:00"))
    assert not mail.outbox  # em triagem: sem responsável
    mapear("kuma", "7", projeto)
    assert len(mail.outbox) == 1 and "Incidente aberto" in mail.outbox[0].subject  # avisado ao sair da triagem
    Incidente.objects.all().delete()
    for status, hora in ((0, "10:30"), (0, "10:31"), (1, "10:35"), (0, "10:40"), (1, "10:45")):
        enviar(client, "kuma", kuma(status, hora))
    assert len(mail.outbox) == 2 and mail.outbox[1].to == ["gestor@exemplo.com"]  # abertura; o resto dentro de 30 min


# Falha do conector, fila e diagnóstico ----------------------------------------------------------

def test_falha_fica_na_fila_reprocessa_e_aparece_como_telemetria_indisponivel(client, projeto, monkeypatch):
    admin = pessoa("administrador")
    client.login(admin)
    diag = {c["provedor"]: c for c in client.get("/api/v1/vetor/eventos-monitoramento/diagnostico").json()["conectores"]}
    assert diag["kuma"]["telemetria"] == "indisponivel"  # nunca recebeu nada: não é "no ar"
    enviar(client, "kuma", kuma(0, "10:00"))
    enviar(client, "kuma", kuma(1, "10:05"))
    diag = {c["provedor"]: c for c in client.get("/api/v1/vetor/eventos-monitoramento/diagnostico").json()["conectores"]}
    assert diag["kuma"]["telemetria"] == "disponivel" and diag["kuma"]["recebidos_24h"] == 2
    monkeypatch.setattr(monitoramento, "_aplicar", lambda ev: (_ for _ in ()).throw(RuntimeError("banco fora")))
    enviar(client, "kuma", kuma(0, "10:30"))
    ev = EventoMonitoramento.objects.get(processamento="falhou")
    assert ev.erro == "RuntimeError: banco fora" and ev.payload  # origem preservada
    diag = client.get("/api/v1/vetor/eventos-monitoramento/diagnostico").json()
    kuma_diag = {c["provedor"]: c for c in diag["conectores"]}["kuma"]
    assert kuma_diag["telemetria"] == "indisponivel" and kuma_diag["falhas_pendentes"] == 1
    assert "não calculada" in diag["disponibilidade_historica"]
    recursos = client.get("/api/v1/vetor/recursos-monitorados").json()
    assert recursos[0]["situacao"] == {"codigo": "telemetria_indisponivel"}  # nunca "no ar" com o conector falhando
    monkeypatch.undo()
    assert client.post(f"/api/v1/vetor/eventos-monitoramento/{ev.id}/reprocessar").json()["processamento"] == "processado"
    assert Incidente.objects.filter(estado="aberto").count() == 1
    client.login(projeto.owner)
    assert client.get("/api/v1/vetor/eventos-monitoramento/diagnostico").status_code == 403
