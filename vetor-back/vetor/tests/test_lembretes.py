"""Lembretes privados e agente (SPEC-05): privacidade, conversão, aviso no fuso, recorrência e tokens do agente."""
import datetime
import io
import json
import zoneinfo

import pytest
from django.core import mail

from taiga.export_import.services import render_project
from taiga.permissions.choices import MEMBERS_PERMISSIONS
from taiga.projects.history.models import HistoryEntry
from taiga.projects.userstories.models import UserStory
from tests import factories as f

from vetor import lembretes
from vetor.models import Auditoria, Cliente, Lembrete, Perfil, TokenAgente

pytestmark = pytest.mark.django_db
TODAS = [p for p, _ in MEMBERS_PERMISSIONS]
LEITURA = [p for p in TODAS if p.startswith("view_")]
SP = zoneinfo.ZoneInfo("America/Sao_Paulo")
UTC = datetime.timezone.utc


@pytest.fixture(autouse=True)
def padrao_de_producao(settings):
    settings.VETOR_PAPEL_SEM_PERFIL = "observador"


def pessoa(papel, **kw):
    user = f.UserFactory.create(**kw)
    Perfil.objects.create(user=user, papel=papel)
    return user


def api(client, user, metodo, url, dados=None, **extra):
    if user:
        client.login(user)
    resp = getattr(client, metodo)(url, json.dumps(dados) if dados is not None else None, content_type="application/json", **extra)
    client.logout()
    return resp


def projeto_com(user, permissoes=TODAS):
    proj = f.create_project(owner=f.UserFactory.create())
    f.MembershipFactory.create(project=proj, user=user, role=f.RoleFactory.create(project=proj, permissions=permissoes))
    return proj


def agente(client, token, rota, dados, chave="k1", **extra):
    return client.post(f"/api/v1/vetor/agente/{rota}", json.dumps(dados), content_type="application/json",
                       HTTP_AUTHORIZATION=f"Agente {token}", HTTP_IDEMPOTENCY_KEY=chave, **extra)


def novo_token(client, user, escopos):
    resp = api(client, user, "post", "/api/v1/vetor/tokens-agente", {"nome": "Assistente", "escopos": escopos})
    assert resp.status_code == 201, resp.content
    return resp.json()["token"]


# Privacidade ---------------------------------------------------------------------------------

def test_ninguem_alem_do_dono_ve_o_lembrete(client):
    a = pessoa("desenvolvedor")
    criado = api(client, a, "post", "/api/v1/vetor/lembretes", {"titulo": "Ligar para o contador", "notas": "segredo"})
    assert criado.status_code == 201
    lid = criado.json()["id"]
    gestor, admin = pessoa("gestor"), pessoa("administrador")
    super_ = f.UserFactory.create(is_superuser=True)
    for b in (gestor, admin, super_):
        assert api(client, b, "get", "/api/v1/vetor/lembretes").json() == []
        assert api(client, b, "get", f"/api/v1/vetor/lembretes/{lid}").status_code == 404
        assert api(client, b, "patch", f"/api/v1/vetor/lembretes/{lid}", {"titulo": "x"}).status_code == 404
        assert api(client, b, "delete", f"/api/v1/vetor/lembretes/{lid}").status_code == 404
        assert api(client, b, "get", f"/api/v1/vetor/lembretes/{lid}/previa_conversao?projeto=1").status_code == 404
        assert "contador" not in api(client, b, "get", "/api/v1/vetor/busca?q=contador").content.decode()
    assert api(client, None, "get", "/api/v1/vetor/lembretes").status_code == 401
    assert [l["titulo"] for l in api(client, a, "get", "/api/v1/vetor/lembretes").json()] == ["Ligar para o contador"]
    # Fora da auditoria, do histórico/notificações do Taiga e da exportação de projeto.
    assert not Auditoria.objects.filter(detalhes__icontains="contador").exists()
    assert not HistoryEntry.objects.filter(key__startswith="vetor.").exists()


def test_exportacao_do_projeto_nao_leva_o_lembrete(client):
    a = pessoa("desenvolvedor")
    proj = projeto_com(a)
    Lembrete.objects.create(dono=a, titulo="Renegociar contrato XYZ", projeto=proj)
    saida = io.BytesIO()
    render_project(proj, saida)
    assert b"Renegociar contrato XYZ" not in saida.getvalue()


def test_referencia_some_quando_o_acesso_e_revogado(client):
    a = pessoa("desenvolvedor")
    proj = projeto_com(a)
    us = f.UserStoryFactory.create(project=proj, milestone=None, subject="Tela de login")
    lid = api(client, a, "post", "/api/v1/vetor/lembretes", {"titulo": "Revisar", "projeto": proj.id, "historia": us.id}).json()["id"]
    ref = api(client, a, "get", f"/api/v1/vetor/lembretes/{lid}").json()["referencias"]
    assert ref["historia"]["assunto"] == "Tela de login" and not ref["referencia_indisponivel"]
    proj.memberships.filter(user=a).delete()
    corpo = api(client, a, "get", f"/api/v1/vetor/lembretes/{lid}").json()
    assert corpo["titulo"] == "Revisar"  # o conteúdo próprio fica
    assert corpo["referencias"]["projeto"] is None and corpo["referencias"]["historia"] is None
    assert corpo["referencias"]["referencia_indisponivel"] and "Tela de login" not in json.dumps(corpo)


def test_nao_referencia_o_que_nao_pode_ver(client):
    a = pessoa("desenvolvedor")
    alheio = f.create_project(owner=f.UserFactory.create())
    cliente = Cliente.objects.create(nome="Sigiloso", responsavel=pessoa("gestor"))
    assert api(client, a, "post", "/api/v1/vetor/lembretes", {"titulo": "x", "projeto": alheio.id}).status_code == 400
    assert api(client, a, "post", "/api/v1/vetor/lembretes", {"titulo": "x", "cliente": cliente.id}).status_code == 400


# Conversão -----------------------------------------------------------------------------------

def test_converter_mostra_previa_exige_confirmacao_e_cria_um_so_item(client):
    a = pessoa("desenvolvedor")
    proj = projeto_com(a)
    vence = datetime.datetime(2026, 11, 5, 23, 30, tzinfo=SP)  # 02:30 UTC do dia 6: o prazo é o dia local
    lid = api(client, a, "post", "/api/v1/vetor/lembretes", {"titulo": "Proposta", "notas": "valor interno", "vencimento": vence.isoformat()}).json()["id"]
    previa = api(client, a, "get", f"/api/v1/vetor/lembretes/{lid}/previa_conversao?projeto={proj.id}").json()
    assert previa["destino"]["id"] == proj.id and "Visível" in previa["visibilidade"]
    assert previa["campos"] == {"assunto": "Proposta", "descricao": "", "prazo": "2026-11-05"}
    assert "notas" in previa["nao_copiados"] and previa["lembrete_continua_privado"]
    assert api(client, a, "post", f"/api/v1/vetor/lembretes/{lid}/converter", {"projeto": proj.id}).status_code == 400
    assert not UserStory.objects.filter(project=proj).exists()
    primeira = api(client, a, "post", f"/api/v1/vetor/lembretes/{lid}/converter", {"projeto": proj.id, "confirmar": True})
    repetida = api(client, a, "post", f"/api/v1/vetor/lembretes/{lid}/converter", {"projeto": proj.id, "confirmar": True})
    assert (primeira.status_code, repetida.status_code) == (201, 200)
    assert primeira.json()["id"] == repetida.json()["id"]
    us = UserStory.objects.get(project=proj)
    assert (us.subject, us.description, us.due_date.isoformat()) == ("Proposta", "", "2026-11-05")
    lembrete = Lembrete.objects.get(pk=lid)
    assert lembrete.estado == "concluido" and lembrete.convertido_em_id == us.id and lembrete.notas == "valor interno"
    log = Auditoria.objects.get(acao="lembrete.convertido")
    assert "Proposta" not in json.dumps(log.detalhes) and "valor interno" not in json.dumps(log.detalhes)


def test_converter_exige_permissao_de_criar_no_projeto(client):
    a = pessoa("desenvolvedor")
    leitura = projeto_com(a, LEITURA)
    lid = api(client, a, "post", "/api/v1/vetor/lembretes", {"titulo": "X"}).json()["id"]
    assert api(client, a, "post", f"/api/v1/vetor/lembretes/{lid}/converter", {"projeto": leitura.id, "confirmar": True}).status_code == 403
    assert not UserStory.objects.filter(project=leitura).exists()


# Aviso e recorrência -------------------------------------------------------------------------

def test_aviso_uma_vez_no_horario_de_brasilia_com_email(client):
    a = pessoa("desenvolvedor", email="a@exemplo.com")
    vence = datetime.datetime(2026, 11, 10, 9, 0, tzinfo=SP)  # 12:00 UTC
    lid = api(client, a, "post", "/api/v1/vetor/lembretes", {"titulo": "Reunião", "vencimento": vence.isoformat(), "avisar_email": True}).json()["id"]
    assert lembretes.avisar_vencidos(datetime.datetime(2026, 11, 10, 11, 59, tzinfo=UTC)) == 0  # 08:59 em Brasília
    assert lembretes.avisar_vencidos(datetime.datetime(2026, 11, 10, 12, 0, tzinfo=UTC)) == 1
    assert lembretes.avisar_vencidos(datetime.datetime(2026, 11, 10, 12, 1, tzinfo=UTC)) == 0  # sem repetir
    assert len(mail.outbox) == 1 and "10/11/2026 09:00" in mail.outbox[0].body
    assert api(client, a, "get", "/api/v1/vetor/lembretes/resumo").json() == {"avisos_nao_vistos": 1}
    assert api(client, pessoa("gestor"), "get", "/api/v1/vetor/lembretes/resumo").json() == {"avisos_nao_vistos": 0}
    api(client, a, "post", "/api/v1/vetor/lembretes/marcar_vistos")
    assert api(client, a, "get", "/api/v1/vetor/lembretes/resumo").json() == {"avisos_nao_vistos": 0}
    # Reagendar volta a avisar no novo horário.
    api(client, a, "patch", f"/api/v1/vetor/lembretes/{lid}", {"vencimento": vence.replace(hour=15).isoformat()})
    assert lembretes.avisar_vencidos(datetime.datetime(2026, 11, 10, 18, 0, tzinfo=UTC)) == 1


def test_lembrete_concluido_ou_sem_vencimento_nao_avisa():
    a = pessoa("desenvolvedor")
    Lembrete.objects.create(dono=a, titulo="sem data")
    Lembrete.objects.create(dono=a, titulo="feito", estado="concluido", vencimento=datetime.datetime(2026, 1, 1, tzinfo=UTC))
    assert lembretes.avisar_vencidos(datetime.datetime(2026, 12, 1, tzinfo=UTC)) == 0


def test_recorrencia_mensal_mantem_o_dia_e_a_hora_local():
    base = datetime.datetime(2026, 1, 31, 9, 0, tzinfo=SP)
    fev = lembretes.proximo(base, "mensal", base)
    assert (fev.month, fev.day, fev.hour) == (2, 28, 9)
    mar = lembretes.proximo(base, "mensal", fev)
    assert (mar.month, mar.day) == (3, 31)
    sem = lembretes.proximo(base, "semanal", base)
    assert (sem.day, sem.hour) == (7, 9)
    dez = datetime.datetime(2026, 12, 15, 9, 0, tzinfo=SP)
    assert lembretes.proximo(dez, "mensal", dez).date() == datetime.date(2027, 1, 15)


def test_recorrente_reagenda_e_avisa_de_novo():
    a = pessoa("desenvolvedor")
    l = Lembrete.objects.create(dono=a, titulo="Relatório", recorrencia="diaria", vencimento=datetime.datetime(2026, 11, 10, 9, 0, tzinfo=SP))
    assert lembretes.avisar_vencidos(datetime.datetime(2026, 11, 10, 12, 5, tzinfo=UTC)) == 1
    l.refresh_from_db()
    assert l.vencimento.astimezone(SP) == datetime.datetime(2026, 11, 11, 9, 0, tzinfo=SP) and l.notificado_em is None
    assert lembretes.avisar_vencidos(datetime.datetime(2026, 11, 10, 13, 0, tzinfo=UTC)) == 0
    assert lembretes.avisar_vencidos(datetime.datetime(2026, 11, 11, 12, 0, tzinfo=UTC)) == 1


def test_validacao_de_vencimento_e_recorrencia(client):
    a = pessoa("desenvolvedor")
    url = "/api/v1/vetor/lembretes"
    assert api(client, a, "post", url, {"titulo": ""}).status_code == 400
    assert api(client, a, "post", url, {"titulo": "x", "vencimento": "2026-11-10T09:00"}).status_code == 400  # sem fuso
    assert api(client, a, "post", url, {"titulo": "x", "recorrencia": "anual"}).status_code == 400
    assert api(client, a, "post", url, {"titulo": "x", "recorrencia": "diaria"}).status_code == 400  # sem vencimento
    lid = api(client, a, "post", url, {"titulo": "x"}).json()["id"]
    assert api(client, a, "patch", f"{url}/{lid}", {"recorrencia": "semanal"}).status_code == 400
    assert api(client, a, "patch", f"{url}/{lid}", {"recorrencia": "semanal", "vencimento": "2026-11-10T09:00:00-03:00"}).status_code == 200


# Agente --------------------------------------------------------------------------------------

def test_agente_cria_lembrete_do_titular_e_nao_aceita_forjar_dono(client):
    a, b = pessoa("desenvolvedor"), pessoa("desenvolvedor")
    token = novo_token(client, a, ["lembretes"])
    assert TokenAgente.objects.get(dono=a).hash != token and token not in json.dumps(api(client, a, "get", "/api/v1/vetor/tokens-agente").json())
    resp = agente(client, token, "lembretes", {"titulo": "Pagar boleto", "vencimento": "2026-11-10T09:00:00-03:00"})
    assert resp.status_code == 201 and resp.json()["privado"]
    assert Lembrete.objects.get(pk=resp.json()["id"]).dono == a
    for campo in ("owner_id", "dono"):
        assert agente(client, token, "lembretes", {"titulo": "x", campo: b.id}, chave=campo).status_code == 400
    assert not Lembrete.objects.filter(dono=b).exists()


def test_agente_idempotencia_repete_a_mesma_resposta(client):
    a = pessoa("desenvolvedor")
    token = novo_token(client, a, ["lembretes"])
    r1 = agente(client, token, "lembretes", {"titulo": "Uma vez"}, chave="abc")
    r2 = agente(client, token, "lembretes", {"titulo": "Uma vez"}, chave="abc")
    assert (r1.status_code, r2.status_code) == (201, 201) and r1.json() == r2.json()
    assert Lembrete.objects.filter(dono=a).count() == 1
    sem_chave = client.post("/api/v1/vetor/agente/lembretes", json.dumps({"titulo": "x"}), content_type="application/json",
                            HTTP_AUTHORIZATION=f"Agente {token}")
    assert sem_chave.status_code == 400 and Lembrete.objects.filter(dono=a).count() == 1


def test_agente_pede_esclarecimento_em_vez_de_adivinhar(client):
    a = pessoa("gestor")
    for nome in ("ACME Matriz", "ACME Filial"):
        Cliente.objects.create(nome=nome, responsavel=a)
    token = novo_token(client, a, ["lembretes"])
    ambiguo = agente(client, token, "lembretes", {"titulo": "Ligar", "cliente": "acme"}, chave="1")
    assert ambiguo.status_code == 422
    corpo = ambiguo.json()["esclarecimento"]
    assert corpo["motivo"] == "ambiguo" and sorted(o["nome"] for o in corpo["opcoes"]) == ["ACME Filial", "ACME Matriz"]
    inexistente = agente(client, token, "lembretes", {"titulo": "Ligar", "cliente": "Globex"}, chave="2")
    assert inexistente.status_code == 422 and inexistente.json()["esclarecimento"]["motivo"] == "nao_encontrado"
    assert not Lembrete.objects.exists()
    certo = agente(client, token, "lembretes", {"titulo": "Ligar", "cliente": "acme filial"}, chave="3")
    assert certo.status_code == 201 and Lembrete.objects.get().cliente.nome == "ACME Filial"


def test_agente_escopos_separados_e_permissao_do_titular(client):
    a = pessoa("desenvolvedor")
    proj, leitura = projeto_com(a), projeto_com(a, LEITURA)
    so_lembretes = novo_token(client, a, ["lembretes"])
    assert agente(client, so_lembretes, "demandas", {"projeto": proj.id, "assunto": "x"}).status_code == 403
    demandas = novo_token(client, a, ["demandas"])
    assert agente(client, demandas, "lembretes", {"titulo": "x"}).status_code == 403
    criada = agente(client, demandas, "demandas", {"projeto": proj.id, "assunto": "Corrigir boleto"}, chave="d1")
    assert criada.status_code == 201 and UserStory.objects.get(pk=criada.json()["id"]).owner == a
    assert agente(client, demandas, "demandas", {"projeto": leitura.id, "assunto": "x"}, chave="d2").status_code == 403
    assert agente(client, demandas, "demandas", {"assunto": "sem projeto"}, chave="d3").status_code == 422
    assert UserStory.objects.count() == 1


def test_token_do_agente_nao_vale_em_outras_rotas_nem_depois_de_revogado(client):
    a = pessoa("administrador")
    token = novo_token(client, a, ["lembretes", "demandas"])
    for url in ("/api/v1/vetor/lembretes", "/api/v1/users/me", "/api/v1/vetor/perfis"):
        assert client.get(url, HTTP_AUTHORIZATION=f"Agente {token}").status_code == 401
    assert agente(client, "vtag_inventado", "lembretes", {"titulo": "x"}).status_code == 401
    outro = pessoa("gestor")
    tid = TokenAgente.objects.get(dono=a).id
    assert api(client, outro, "delete", f"/api/v1/vetor/tokens-agente/{tid}").status_code == 404  # não revoga o de outro
    assert api(client, a, "delete", f"/api/v1/vetor/tokens-agente/{tid}").status_code == 204
    assert agente(client, token, "lembretes", {"titulo": "x"}, chave="depois").status_code == 401
    # Sessão normal não serve nas rotas do agente: nenhum token global, nenhuma troca de identidade.
    client.login(a)
    assert client.post("/api/v1/vetor/agente/lembretes", json.dumps({"titulo": "x"}), content_type="application/json",
                       HTTP_IDEMPOTENCY_KEY="s").status_code == 401
    client.logout()


def test_agente_limite_por_minuto(client, settings):
    settings.VETOR_AGENTE_LIMITE_MINUTO = 2
    a = pessoa("desenvolvedor")
    token = novo_token(client, a, ["lembretes"])
    assert [agente(client, token, "lembretes", {"titulo": "x"}, chave=str(i)).status_code for i in range(3)] == [201, 201, 429]
    assert agente(client, token, "lembretes", {"titulo": "x"}, chave="0").status_code == 201  # repetição ainda responde
    assert Lembrete.objects.count() == 2


def test_agente_sem_csrf_com_cliente_que_aplica_csrf(client):
    from django.test import Client
    a = pessoa("desenvolvedor")
    token = novo_token(client, a, ["lembretes"])
    rigoroso = Client(enforce_csrf_checks=True)
    assert agente(rigoroso, token, "lembretes", {"titulo": "x"}).status_code == 201
