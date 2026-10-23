"""Projetos, etapas e colaboração (SPEC-04): modelo de fluxo, participação por etapa, conversa, conflito e filtros."""
import datetime
import json

import pytest
from django.core.management import call_command
from django.utils import timezone

from taiga.permissions.choices import MEMBERS_PERMISSIONS
from taiga.projects.history.models import HistoryEntry
from taiga.projects.models import Project
from taiga.projects.userstories.models import UserStory
from tests import factories as f

from vetor.models import Cliente, ParticipacaoEtapa, Perfil, ProjetoCliente

pytestmark = pytest.mark.django_db
TODAS = [p for p, _ in MEMBERS_PERMISSIONS]
LEITURA = [p for p in TODAS if p.startswith("view_")]


@pytest.fixture(autouse=True)
def padrao_de_producao(settings):
    settings.VETOR_PAPEL_SEM_PERFIL = "observador"


def pessoa(papel):
    user = f.UserFactory.create()
    Perfil.objects.create(user=user, papel=papel)
    return user


def api(client, user, metodo, url, dados=None):
    client.login(user)
    resp = getattr(client, metodo)(url, json.dumps(dados) if dados is not None else None, content_type="application/json")
    client.logout()
    return resp


@pytest.fixture
def projeto_vetor(client):
    """Projeto criado pela API com o modelo "Kanban (fluxo Vetor)" e dois desenvolvedores."""
    call_command("loaddata", "initial_project_templates", verbosity=0)
    gestor, dev1, dev2 = pessoa("gestor"), pessoa("desenvolvedor"), pessoa("desenvolvedor")
    resp = api(client, gestor, "post", "/api/v1/projects", {"name": "Portal", "description": "x", "creation_template": 1001})
    assert resp.status_code == 201, resp.content
    proj = Project.objects.get(pk=resp.json()["id"])
    dev_role = proj.roles.get(slug="desenvolvimento")
    for d in (dev1, dev2):
        f.MembershipFactory.create(project=proj, user=d, role=dev_role)
    return proj, gestor, dev1, dev2


def historia(**kw):
    # milestone=None: a fábrica criaria um sprint num projeto novo, cujo dono sem perfil o teto (SPEC-02) recusa.
    return f.UserStoryFactory.create(milestone=None, **kw)


def etapa(proj, nome):
    return proj.us_statuses.get(name=nome)


def patch_us(client, user, us_id, dados):
    versao = UserStory.objects.get(pk=us_id).version
    return api(client, user, "patch", f"/api/v1/userstories/{us_id}", {**dados, "version": versao})


# Modelo de fluxo ------------------------------------------------------------------------------

def test_modelo_vetor_cria_etapas_papeis_e_prioridade_opcional(projeto_vetor):
    proj, gestor, *_ = projeto_vetor
    assert list(proj.us_statuses.order_by("order").values_list("name", flat=True)) == [
        "Entrada", "Refinamento", "A fazer", "Desenvolvimento", "Revisão", "Testes", "Concluído", "Arquivado"]
    assert proj.default_us_status.name == "Entrada"
    assert set(proj.us_statuses.filter(is_closed=True).values_list("name", flat=True)) == {"Concluído", "Arquivado"}
    assert sorted(proj.roles.values_list("slug", flat=True)) == ["desenvolvimento", "gestao", "observacao"]
    dono = proj.memberships.get(user=gestor)
    assert dono.is_admin and dono.role.slug == "gestao"
    prioridade = proj.userstorycustomattributes.get(name="Prioridade")
    assert prioridade.type == "dropdown" and prioridade.extra == ["Baixa", "Média", "Alta", "Urgente"]


def test_observador_entra_com_o_papel_observacao_do_modelo(client, projeto_vetor):
    proj, gestor, *_ = projeto_vetor
    obs = pessoa("observador")
    resp = api(client, gestor, "post", "/api/v1/memberships", {"project": proj.id, "role": proj.roles.get(slug="observacao").id, "username": obs.email})
    assert resp.status_code == 201  # o papel do modelo respeita o teto da SPEC-02


# Fluxo de colaboração (critério de aceite) ---------------------------------------------------

def test_gestor_cria_dev_pergunta_gestor_responde_e_avanca_com_historico(client, projeto_vetor):
    proj, gestor, dev1, dev2 = projeto_vetor
    criada = api(client, gestor, "post", "/api/v1/userstories", {"project": proj.id, "subject": "Integração com ERP", "assigned_to": dev1.id})
    assert criada.status_code == 201
    us = criada.json()["id"]
    assert patch_us(client, dev1, us, {"comment": "Qual endpoint do ERP usamos?"}).status_code == 200
    assert patch_us(client, gestor, us, {"comment": "O /pedidos, documentação no anexo."}).status_code == 200
    assert patch_us(client, gestor, us, {"assigned_users": [dev1.id, dev2.id]}).status_code == 200
    assert patch_us(client, dev1, us, {"status": etapa(proj, "Desenvolvimento").id}).status_code == 200  # sem Prioridade: não bloqueia
    entradas = HistoryEntry.objects.filter(key=f"userstories.userstory:{us}").order_by("created_at")
    comentarios = [e.comment for e in entradas if e.comment]
    mudancas = [sorted(e.diff) for e in entradas if e.diff and not e.comment]
    assert comentarios == ["Qual endpoint do ERP usamos?", "O /pedidos, documentação no anexo."]
    assert any("status" in d for d in mudancas) and any("assigned_users" in d for d in mudancas)  # eventos separados da conversa


def test_dois_devs_na_mesma_etapa_e_participacao_com_inicio_fim_e_autor(client, projeto_vetor):
    proj, gestor, dev1, dev2 = projeto_vetor
    us = api(client, gestor, "post", "/api/v1/userstories", {"project": proj.id, "subject": "Relatório", "status": etapa(proj, "Desenvolvimento").id,
                                                           "assigned_to": dev1.id}).json()["id"]
    patch_us(client, gestor, us, {"assigned_users": [dev1.id, dev2.id]})
    abertas = ParticipacaoEtapa.objects.filter(historia_id=us, fim__isnull=True)
    assert sorted(abertas.values_list("usuario_id", "status_nome")) == sorted([(dev1.id, "Desenvolvimento"), (dev2.id, "Desenvolvimento")])
    patch_us(client, dev2, us, {"status": etapa(proj, "Revisão").id})
    fechadas = ParticipacaoEtapa.objects.filter(historia_id=us, status_nome="Desenvolvimento")
    assert all(p.fim and p.autor_fim == (dev2.get_full_name() or dev2.username) for p in fechadas)
    assert set(ParticipacaoEtapa.objects.filter(historia_id=us, fim__isnull=True).values_list("status_nome", flat=True)) == {"Revisão"}
    patch_us(client, gestor, us, {"assigned_users": [dev1.id]})
    assert list(ParticipacaoEtapa.objects.filter(historia_id=us, fim__isnull=True).values_list("usuario_id", flat=True)) == [dev1.id]
    patch_us(client, gestor, us, {"status": etapa(proj, "Concluído").id})
    assert not ParticipacaoEtapa.objects.filter(historia_id=us, fim__isnull=True).exists()
    lista = api(client, dev1, "get", f"/api/v1/vetor/participacoes?historia={us}").json()
    assert [(p["usuario_nome"] and p["etapa"]) for p in lista][:2] == ["Desenvolvimento", "Desenvolvimento"]
    assert api(client, pessoa("gestor"), "get", f"/api/v1/vetor/participacoes?historia={us}").json() == []


def test_edicao_concorrente_retorna_conflito_sem_mudar_nada(client, projeto_vetor):
    proj, gestor, dev1, dev2 = projeto_vetor
    # Criada pela API, como na tela: o OCC do Taiga compara os campos alterados pelo histórico.
    us = api(client, gestor, "post", "/api/v1/userstories", {"project": proj.id, "subject": "X", "status": etapa(proj, "A fazer").id}).json()["id"]
    versao = UserStory.objects.get(pk=us).version
    assert api(client, dev1, "patch", f"/api/v1/userstories/{us}", {"status": etapa(proj, "Desenvolvimento").id, "version": versao}).status_code == 200
    conflito = api(client, dev2, "patch", f"/api/v1/userstories/{us}", {"status": etapa(proj, "Testes").id, "version": versao})
    assert conflito.status_code == 400 and "version" in conflito.json()
    assert UserStory.objects.get(pk=us).status.name == "Desenvolvimento"
    # Campo diferente com a mesma versão antiga não conflita (regra do Taiga): só sobreposição é recusada.
    assert api(client, dev2, "patch", f"/api/v1/userstories/{us}", {"description": "nota", "version": versao}).status_code == 200


def test_bloqueio_e_sinalizacao_com_motivo_sem_trocar_de_etapa(client, projeto_vetor):
    proj, gestor, dev1, _ = projeto_vetor
    us = historia(project=proj, status=etapa(proj, "Desenvolvimento"), owner=gestor)
    assert patch_us(client, dev1, us.id, {"is_blocked": True, "blocked_note": "Aguardando credenciais"}).status_code == 200
    us.refresh_from_db()
    assert (us.is_blocked, us.blocked_note, us.status.name) == (True, "Aguardando credenciais", "Desenvolvimento")


def test_movimento_recusado_no_quadro_nao_altera_o_banco(client, projeto_vetor):
    proj, gestor, *_ = projeto_vetor
    obs = pessoa("observador")
    f.MembershipFactory.create(project=proj, user=obs, role=proj.roles.get(slug="observacao"))
    us = historia(project=proj, status=etapa(proj, "A fazer"), owner=gestor)
    resp = api(client, obs, "post", "/api/v1/userstories/bulk_update_kanban_order",
               {"project_id": proj.id, "status_id": etapa(proj, "Concluído").id, "bulk_userstories": [us.id]})
    assert resp.status_code == 403
    assert UserStory.objects.get(pk=us.id).status.name == "A fazer"


# Filtros entre projetos -----------------------------------------------------------------------

def test_demandas_filtram_por_cliente_projeto_responsavel_prazo_e_bloqueio(client, projeto_vetor):
    proj, gestor, dev1, dev2 = projeto_vetor
    outro = f.create_project(owner=gestor)  # o modelo cria a membership de dono
    cliente = Cliente.objects.create(nome="ACME", responsavel=gestor)
    ProjetoCliente.objects.create(project=proj, cliente=cliente)
    hoje = timezone.localdate()
    a = historia(project=proj, subject="vencida", status=etapa(proj, "A fazer"), due_date=hoje - datetime.timedelta(days=1), assigned_to=dev1)
    b = historia(project=proj, subject="semana", status=etapa(proj, "A fazer"), due_date=hoje + datetime.timedelta(days=3), is_blocked=True)
    b.assigned_users.add(dev2)
    historia(project=proj, subject="pronta", status=etapa(proj, "Concluído"), due_date=None)
    historia(project=outro, subject="interna", status=outro.us_statuses.first(), due_date=None)
    assuntos = lambda qs: sorted(d["assunto"] for d in api(client, gestor, "get", f"/api/v1/vetor/demandas{qs}").json())
    assert assuntos("") == ["interna", "semana", "vencida"]
    assert assuntos(f"?cliente={cliente.id}") == ["semana", "vencida"]
    assert assuntos(f"?projeto={outro.id}") == ["interna"]
    assert assuntos(f"?responsavel={dev2.id}") == ["semana"]  # colaborador também conta
    assert assuntos("?prazo=vencidas") == ["vencida"] and assuntos("?prazo=7dias") == ["semana"] and assuntos("?prazo=sem") == ["interna"]
    assert assuntos("?bloqueadas=true") == ["semana"]
    assert "pronta" in assuntos("?concluidas=true")
    primeira = api(client, gestor, "get", f"/api/v1/vetor/demandas?cliente={cliente.id}&prazo=vencidas").json()[0]
    assert (primeira["cliente"]["nome"], primeira["responsavel"]["id"], primeira["etapa"]["nome"]) == ("ACME", dev1.id, "A fazer")
    assert api(client, pessoa("gestor"), "get", "/api/v1/vetor/demandas").json() == []
    assert api(client, gestor, "get", "/api/v1/vetor/demandas?prazo=amanha").status_code == 400
