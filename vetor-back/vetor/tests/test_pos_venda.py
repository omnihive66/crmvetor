"""Pós-venda e adoção (SPEC-08): painel com sinais separados, ingestão pseudonimizada, sem dados ≠ desuso, isolamento."""
import datetime
import json

import pytest
from django.utils import timezone

from taiga.permissions.choices import MEMBERS_PERMISSIONS
from tests import factories as f

from vetor import monitoramento, operacao
from vetor.models import Cliente, EventoUso, Incidente, Perfil, ProdutoTelemetria, ProjetoCliente, RecursoMonitorado, Reuniao

pytestmark = pytest.mark.django_db
TODAS = [p for p, _ in MEMBERS_PERMISSIONS]


@pytest.fixture(autouse=True)
def ambiente(settings):
    settings.VETOR_PAPEL_SEM_PERFIL = "observador"
    settings.VETOR_MONITOR_TOKENS = {"kuma": ["k"], "beszel": ["b"]}
    settings.VETOR_USO_RETENCAO_DIAS = 180


def pessoa(papel):
    user = f.UserFactory.create()
    Perfil.objects.create(user=user, papel=papel)
    return user


def api(client, user, metodo, url, dados=None, **extra):
    client.login(user) if user else client.logout()
    resp = getattr(client, metodo)(url, json.dumps(dados) if dados is not None else None, content_type="application/json", **extra)
    client.logout()
    return resp


def cliente_com_projeto(gestor, nome="ACME"):
    cliente = Cliente.objects.create(nome=nome, responsavel=gestor)
    proj = f.create_project(owner=gestor)
    f.MembershipFactory.create(project=proj, user=gestor, is_admin=True, role=f.RoleFactory.create(project=proj, permissions=TODAS))
    ProjetoCliente.objects.create(project=proj, cliente=cliente)
    return cliente, proj


def produto(client, cliente, **kw):
    resp = api(client, pessoa("administrador"), "post", "/api/v1/vetor/produtos-telemetria", {"cliente": cliente.id, "nome": "ERP Web", "chave": "erp", **kw})
    assert resp.status_code == 201, resp.content
    return ProdutoTelemetria.objects.get(pk=resp.json()["id"]), resp.json()["token"]


def enviar(client, token, eventos):
    return client.post("/api/v1/vetor/uso/eventos", json.dumps({"eventos": eventos}), content_type="application/json", HTTP_AUTHORIZATION=f"Produto {token}")


def ev(i, tipo="atividade", usuario="u-0000001", quando=None, **kw):
    quando = quando or timezone.now() - datetime.timedelta(hours=1)
    base = {"id": f"e{i}", "tipo": tipo, "usuario": usuario, "ocorrido_em": quando.isoformat()}
    if tipo == "atividade":
        base["funcionalidade"] = kw.pop("funcionalidade", "emitir_nota")
    if tipo == "pulso":
        base.pop("usuario")
    return {**base, **kw}


@pytest.fixture
def cenario(client):
    gestor = pessoa("gestor")
    cliente, proj = cliente_com_projeto(gestor)
    return gestor, cliente, proj


# Relacionamento -------------------------------------------------------------------------------

def test_relacionamento_ultima_reuniao_proximo_contato_e_pendencias(client, cenario):
    gestor, cliente, proj = cenario
    Reuniao.objects.create(cliente=cliente, data=timezone.now() - datetime.timedelta(days=9), notas="antiga")
    nova = Reuniao.objects.create(cliente=cliente, data=timezone.now() - datetime.timedelta(days=2), proximos_passos="Enviar proposta")
    assert api(client, gestor, "patch", f"/api/v1/vetor/clientes/{cliente.id}", {"proximo_contato": "2026-11-05"}).json()["proximo_contato"] == "2026-11-05"
    assert api(client, gestor, "patch", f"/api/v1/vetor/clientes/{cliente.id}", {"proximo_contato": "2026-02-30"}).status_code == 400
    f.UserStoryFactory.create(project=proj, milestone=None, is_blocked=True, due_date=datetime.date(2020, 1, 1))
    f.UserStoryFactory.create(project=proj, milestone=None, due_date=None)
    r = api(client, gestor, "get", f"/api/v1/vetor/clientes/{cliente.id}/painel").json()["relacionamento"]
    assert r["ultima_reuniao"]["id"] == nova.id and r["ultima_reuniao"]["proximos_passos"] == "Enviar proposta"  # abre a ata dela
    assert r["proximo_contato"] == "2026-11-05" and r["pendencias"] == {"abertas": 2, "bloqueadas": 1, "vencidas": 1}


# Ingestão -------------------------------------------------------------------------------------

def test_ingestao_autentica_deduplica_e_minimiza(client, cenario):
    _, cliente, _ = cenario
    prod, token = produto(client, cliente)
    assert enviar(client, "vtpr_falso", [ev(1)]).status_code == 401
    assert client.post("/api/v1/vetor/uso/eventos", "{}", content_type="application/json").status_code == 401
    r = enviar(client, token, [ev(1), ev(2, "login"), ev(3, "pulso")])
    assert r.status_code == 200 and r.json() == {"recebidos": 3, "duplicados": 0}
    assert enviar(client, token, [ev(1), ev(4)]).json() == {"recebidos": 1, "duplicados": 1}
    recusados = {"conteúdo": ev(5, texto="mensagem do usuário"), "e-mail": ev(6, usuario="ana@cliente.com"),
                 "outro cliente": ev(7, client_id=999), "sem fuso": {**ev(8), "ocorrido_em": "2026-10-23T10:00:00"},
                 "futuro": ev(9, quando=timezone.now() + datetime.timedelta(days=1)), "tipo": ev(10, tipo="clique"),
                 "sem funcionalidade": {**ev(11), "funcionalidade": "Tela Inteira!"}}
    for motivo, evento in recusados.items():
        assert enviar(client, token, [evento]).status_code == 400, motivo
    assert EventoUso.objects.count() == 4  # lote recusado não grava nada
    guardado = EventoUso.objects.get(id_externo="e1")
    assert guardado.usuario != "u-0000001" and len(guardado.usuario) == 64  # pseudônimo cifrado de novo no servidor
    api(client, pessoa("administrador"), "delete", f"/api/v1/vetor/produtos-telemetria/{prod.id}")
    assert enviar(client, token, [ev(12)]).status_code == 401  # revogado


def test_token_do_produto_nao_autentica_pessoa_em_outras_rotas(client, cenario):
    _, cliente, _ = cenario
    _, token = produto(client, cliente)
    for url in ("/api/v1/vetor/clientes", "/api/v1/users/me", f"/api/v1/vetor/clientes/{cliente.id}/painel"):
        assert client.get(url, HTTP_AUTHORIZATION=f"Produto {token}").status_code == 401


def test_pseudonimo_nao_cruza_produtos(client, cenario):
    gestor, cliente, _ = cenario
    a, ta = produto(client, cliente)
    b, tb = produto(client, cliente, chave="app", nome="App")
    enviar(client, ta, [ev(1, usuario="mesma-pessoa")])
    enviar(client, tb, [ev(1, usuario="mesma-pessoa")])
    assert a.eventos.get().usuario != b.eventos.get().usuario


# Métricas de adoção ---------------------------------------------------------------------------

def test_sem_eventos_e_sem_dados_nao_desuso(client, cenario):
    gestor, cliente, _ = cenario
    painel = api(client, gestor, "get", f"/api/v1/vetor/clientes/{cliente.id}/painel").json()
    assert painel["adocao"] == []  # nenhum produto
    prod, _ = produto(client, cliente, alerta_desuso_dias=7)
    adocao = api(client, gestor, "get", f"/api/v1/vetor/clientes/{cliente.id}/painel").json()["adocao"][0]
    assert adocao["situacao"] == "sem_dados" and "alerta" not in adocao


def test_ultimo_acesso_com_origem_ativos_na_janela_e_login_separado(client, cenario):
    gestor, cliente, _ = cenario
    prod, token = produto(client, cliente, janela_ativos_dias=7, sintetico=True)
    agora = timezone.now()
    enviar(client, token, [ev(1, "login", "pessoa-0001", agora - datetime.timedelta(days=1)),
                           ev(2, "atividade", "pessoa-0001", agora - datetime.timedelta(days=1)),
                           ev(3, "atividade", "pessoa-0002", agora - datetime.timedelta(days=2), funcionalidade="relatorio"),
                           ev(4, "login", "pessoa-0003", agora - datetime.timedelta(days=2)),  # só login: não é ativo
                           ev(5, "atividade", "pessoa-0004", agora - datetime.timedelta(days=20))])  # fora da janela
    a = api(client, gestor, "get", f"/api/v1/vetor/clientes/{cliente.id}/painel").json()["adocao"][0]
    assert a["sintetico"] is True and a["fuso"] == "America/Sao_Paulo" and a["janela_dias"] == 7
    assert a["usuarios_ativos"] == 2 and a["logins_na_janela"] == 2
    assert a["ultimo_acesso"]["origem"] == "login no produto ERP Web" and a["atualizado_em"]
    assert {x["funcionalidade"]: x["usuarios"] for x in a["funcionalidades"]} == {"emitir_nota": 1, "relatorio": 1}
    assert "pessoa-0001" not in json.dumps(a)  # nunca expõe pseudônimos


def test_alerta_de_desuso_exige_telemetria_viva_e_respeita_excecao(client, cenario):
    gestor, cliente, _ = cenario
    prod, token = produto(client, cliente, alerta_desuso_dias=7)
    antigo = timezone.now() - datetime.timedelta(days=10)
    enviar(client, token, [ev(1, "atividade", quando=antigo)])
    EventoUso.objects.update(recebido_em=antigo)  # produto parado há 10 dias
    alerta = lambda: operacao.adocao(ProdutoTelemetria.objects.get(pk=prod.pk))["alerta"]["codigo"]
    assert alerta() == "telemetria_parada"  # silêncio não vira desuso
    enviar(client, token, [ev(2, "pulso")])  # produto vivo, mas ninguém usa há 10 dias
    assert alerta() == "possivel_desuso"
    r = api(client, gestor, "patch", f"/api/v1/vetor/produtos-telemetria/{prod.id}", {"alerta_excecao_ate": "2099-01-31", "alerta_excecao_motivo": "Férias coletivas"})
    assert r.status_code == 200 and alerta() == "em_excecao"
    api(client, gestor, "patch", f"/api/v1/vetor/produtos-telemetria/{prod.id}", {"alerta_desuso_dias": None})
    assert alerta() == "desligado"
    obs = pessoa("observador")
    assert api(client, obs, "patch", f"/api/v1/vetor/produtos-telemetria/{prod.id}", {"alerta_desuso_dias": 3}).status_code == 404
    assert api(client, gestor, "post", "/api/v1/vetor/produtos-telemetria", {"cliente": cliente.id, "nome": "X", "chave": "x"}).status_code == 403


def test_retencao_apaga_eventos_antigos(client, cenario, settings):
    _, cliente, _ = cenario
    prod, token = produto(client, cliente)
    enviar(client, token, [ev(1, quando=timezone.now() - datetime.timedelta(days=100)), ev(2)])
    settings.VETOR_USO_RETENCAO_DIAS = 30
    assert operacao.limpar_uso() == 1 and EventoUso.objects.get().id_externo == "e2"


# Painel: queda × CPU alta × baixa adoção, e isolamento entre clientes -------------------------

def test_painel_separa_queda_cpu_e_adocao_e_nao_mostra_outro_cliente(client, cenario):
    gestor, cliente, proj = cenario
    outro_gestor = pessoa("gestor")
    outro, proj_b = cliente_com_projeto(outro_gestor, "Globex")
    rec = RecursoMonitorado.objects.create(provedor="beszel", id_externo="s1", nome="web-01", projeto=proj)
    RecursoMonitorado.objects.create(provedor="kuma", id_externo="9", nome="Globex API", projeto=proj_b)
    client.post("/api/v1/vetor/monitoramento/beszel/webhook", json.dumps({"title": "Connection to web-01 is down 🔴", "message": "x https://b.example/system/s1"}),
                content_type="application/json", HTTP_X_VETOR_TOKEN="b")
    client.post("/api/v1/vetor/monitoramento/beszel/webhook", json.dumps({"title": "web-01 CPU above threshold", "message": "x https://b.example/system/s1"}),
                content_type="application/json", HTTP_X_VETOR_TOKEN="b")
    RecursoMonitorado.objects.create(provedor="beszel", id_externo="s2", nome="db-01", projeto=proj)
    client.post("/api/v1/vetor/monitoramento/beszel/webhook", json.dumps({"title": "db-01 memory above threshold", "message": "x https://b.example/system/s2"}),
                content_type="application/json", HTTP_X_VETOR_TOKEN="b")
    produto(client, outro)  # adoção do outro cliente
    p = api(client, gestor, "get", f"/api/v1/vetor/clientes/{cliente.id}/painel").json()
    disp = {d["recurso"]: (d["quedas_abertas"], d["situacao"]["codigo"]) for d in p["disponibilidade"]}
    assert disp == {"web-01": (1, "fora_do_ar"), "db-01": (0, "sem_dados")}  # memória alta não é queda
    assert sorted((i["recurso"], i["metrica"], i["fonte"]) for i in p["infraestrutura"]) == [("db-01", "memory", "Beszel"), ("web-01", "cpu", "Beszel")]
    assert p["infraestrutura"][0]["ultimo_evento_em"] and p["adocao"] == []  # adoção: nada deste cliente
    assert "Globex" not in json.dumps(p)
    assert api(client, gestor, "get", f"/api/v1/vetor/clientes/{outro.id}/painel").status_code == 404
    assert api(client, None, "get", f"/api/v1/vetor/clientes/{cliente.id}/painel").status_code == 401
    # Quem vê o cliente mas não o projeto não vê os recursos dele.
    dev = pessoa("desenvolvedor")
    cliente.responsavel = dev
    cliente.save()
    assert api(client, dev, "get", f"/api/v1/vetor/clientes/{cliente.id}/painel").json()["disponibilidade"] == []
    assert Incidente.objects.filter(recurso=rec).count() == 2 and Incidente.objects.count() == 3
