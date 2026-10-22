"""Matriz da SPEC-02: teto do papel, administração, integrações, desativação e auditoria."""
import json

import pytest

from taiga.permissions.choices import MEMBERS_PERMISSIONS
from tests import factories as f
from tests.utils import helper_test_http_method  # noqa: F401  (mantém a suíte oficial importável)

from vetor.models import Auditoria, Perfil

pytestmark = pytest.mark.django_db
TODAS = [p for p, _ in MEMBERS_PERMISSIONS]
LEITURA = [p for p in TODAS if p.startswith("view_")]


@pytest.fixture(autouse=True)
def padrao_de_producao(settings):
    settings.VETOR_PAPEL_SEM_PERFIL = "observador"


def pessoa(papel, **kw):
    user = f.UserFactory.create(**kw)
    Perfil.objects.create(user=user, papel=papel)
    return user


def api(client, user, metodo, url, dados=None):
    client.login(user)
    resp = getattr(client, metodo)(url, json.dumps(dados) if dados is not None else None,
                                   content_type="application/json")
    client.logout()
    return resp


@pytest.fixture
def projeto():
    gestor = pessoa("gestor")
    proj = f.create_project(owner=gestor)
    f.MembershipFactory.create(project=proj, user=gestor, is_admin=True,
                               role=f.RoleFactory.create(project=proj, permissions=TODAS))
    return proj, gestor


# Teto do papel -------------------------------------------------------------------------------

def test_observador_so_entra_com_papel_de_leitura(client, projeto):
    proj, gestor = projeto
    obs = pessoa("observador")
    leitura = f.RoleFactory.create(project=proj, permissions=LEITURA)
    edicao = f.RoleFactory.create(project=proj, permissions=LEITURA + ["add_us", "comment_us"])
    url = "/api/v1/memberships"
    negado = api(client, gestor, "post", url, {"project": proj.id, "role": edicao.id, "username": obs.email})
    assert negado.status_code == 403 and "só de leitura" in negado.json()["_error_message"]
    assert api(client, gestor, "post", url, {"project": proj.id, "role": leitura.id, "username": obs.email}).status_code == 201


def test_sem_perfil_vale_como_observador(client, projeto):
    proj, gestor = projeto
    sem_perfil = f.UserFactory.create()
    papel = f.RoleFactory.create(project=proj, permissions=TODAS)
    resp = api(client, gestor, "post", "/api/v1/memberships", {"project": proj.id, "role": papel.id, "username": sem_perfil.email})
    assert resp.status_code == 403


@pytest.fixture
def modelos_de_projeto():
    from django.core.management import call_command
    call_command("loaddata", "initial_project_templates", verbosity=0)  # os mesmos da produção


def test_desenvolvedor_nao_cria_projeto_e_nada_fica_no_banco(client, modelos_de_projeto):
    dev = pessoa("desenvolvedor")
    resp = api(client, dev, "post", "/api/v1/projects", {"name": "X", "description": "x"})
    assert resp.status_code == 403
    assert not dev.owned_projects.exists()


def test_gestor_cria_projeto(client, modelos_de_projeto):
    gestor = pessoa("gestor")
    assert api(client, gestor, "post", "/api/v1/projects", {"name": "X", "description": "x"}).status_code == 201


def test_ampliar_papel_do_projeto_alem_do_teto_e_recusado(client, projeto):
    proj, gestor = projeto
    leitura = f.RoleFactory.create(project=proj, permissions=LEITURA)
    f.MembershipFactory.create(project=proj, user=pessoa("observador"), role=leitura)
    resp = api(client, gestor, "patch", f"/api/v1/roles/{leitura.id}", {"permissions": LEITURA + ["add_us"]})
    assert resp.status_code == 403
    leitura.refresh_from_db()
    assert "add_us" not in leitura.permissions


def test_rebaixar_papel_com_acesso_incompativel_explica_o_projeto(client, projeto):
    proj, gestor = projeto
    admin = pessoa("administrador")
    resp = api(client, admin, "patch", f"/api/v1/vetor/perfis/{gestor.id}", {"papel": "desenvolvedor"})
    assert resp.status_code == 403 and proj.name in resp.json()["_error_message"]
    assert Perfil.objects.get(user=gestor).papel == "gestor"


def test_ultimo_administrador_nao_pode_sair(client):
    admin = pessoa("administrador")
    assert api(client, admin, "patch", f"/api/v1/vetor/perfis/{admin.id}", {"papel": "gestor"}).status_code == 403
    assert api(client, admin, "patch", f"/api/v1/vetor/perfis/{admin.id}", {"is_active": False}).status_code == 403
    outro = pessoa("administrador")
    assert api(client, outro, "patch", f"/api/v1/vetor/perfis/{admin.id}", {"papel": "gestor"}).status_code == 200


# Administração e integrações -----------------------------------------------------------------

@pytest.mark.parametrize("papel,esperado", [("administrador", 200), ("gestor", 403), ("desenvolvedor", 403), ("observador", 403)])
def test_so_administrador_lista_perfis_e_auditoria(client, papel, esperado):
    user = pessoa(papel)
    pessoa("administrador")
    assert api(client, user, "get", "/api/v1/vetor/perfis").status_code == esperado
    assert api(client, user, "get", "/api/v1/vetor/auditoria").status_code == esperado
    me = api(client, user, "get", "/api/v1/vetor/perfis/me")
    assert me.status_code == 200 and me.json()["papel"] == papel


def test_anonimo_nao_ve_nada(client):
    assert client.get("/api/v1/vetor/perfis").status_code == 401
    assert client.get("/api/v1/vetor/perfis/me").status_code == 401


def test_integracoes_so_para_administrador_mesmo_sendo_admin_do_projeto(client, projeto):
    proj, gestor = projeto
    hook = {"project": proj.id, "name": "x", "url": "https://example.com/hook", "key": "segredo"}
    assert api(client, gestor, "post", "/api/v1/webhooks", hook).status_code == 403
    assert api(client, gestor, "get", f"/api/v1/projects/{proj.id}/modules").status_code == 403
    admin = pessoa("administrador")
    f.MembershipFactory.create(project=proj, user=admin, is_admin=True, role=f.RoleFactory.create(project=proj, permissions=TODAS))
    assert api(client, admin, "post", "/api/v1/webhooks", hook).status_code == 201
    assert api(client, admin, "get", f"/api/v1/projects/{proj.id}/modules").status_code == 200


def test_criar_conta_sem_senha_compartilhada(client, django_capture_on_commit_callbacks):
    from django.core import mail
    admin = pessoa("administrador")
    dados = {"username": "joana.silva", "email": "Joana@Example.com", "full_name": "Joana Silva", "papel": "desenvolvedor"}
    with django_capture_on_commit_callbacks(execute=True):
        resp = api(client, admin, "post", "/api/v1/vetor/perfis", dados)
    assert resp.status_code == 201 and resp.json()["papel"] == "desenvolvedor"
    from django.contrib.auth import get_user_model
    joana = get_user_model().objects.get(username="joana.silva")
    assert not joana.has_usable_password() and joana.email == "joana@example.com"
    assert [m.to for m in mail.outbox] == [["joana@example.com"]]
    repetida = api(client, admin, "post", "/api/v1/vetor/perfis", dados)
    assert repetida.status_code == 400 and {"username", "email"} <= set(repetida.json())


# Desativação e auditoria ---------------------------------------------------------------------

def test_desativar_bloqueia_o_token_ja_emitido_e_fica_auditado(client, projeto):
    proj, gestor = projeto
    admin = pessoa("administrador")
    login = client.post("/api/v1/auth", json.dumps({"type": "normal", "username": gestor.username, "password": gestor.username}),
                        content_type="application/json")
    token = login.json()["auth_token"]
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
    assert client.get(f"/api/v1/projects/{proj.id}", **auth).status_code == 200
    assert api(client, admin, "patch", f"/api/v1/vetor/perfis/{gestor.id}", {"is_active": False}).status_code == 200
    assert client.get(f"/api/v1/projects/{proj.id}", **auth).status_code == 401
    reg = Auditoria.objects.get(acao="usuario.desativado")
    assert (reg.ator_id, reg.alvo_id) == (admin.id, str(gestor.id))


def test_troca_de_papel_no_projeto_registra_quem_fez(client, projeto):
    proj, gestor = projeto
    dev = pessoa("desenvolvedor")
    a = f.RoleFactory.create(project=proj, permissions=LEITURA)
    b = f.RoleFactory.create(project=proj, permissions=LEITURA + ["add_us"])
    m = f.MembershipFactory.create(project=proj, user=dev, role=a)
    assert api(client, gestor, "patch", f"/api/v1/memberships/{m.id}", {"role": b.id}).status_code == 200
    reg = Auditoria.objects.filter(acao="membership.alterada", alvo_id=str(m.id)).get()
    assert reg.ator_id == gestor.id and reg.detalhes["antes"]["role_id"] == a.id
    assert "senha" not in json.dumps(reg.detalhes) and "token" not in json.dumps(reg.detalhes)


def test_alteracao_de_perfil_auditada_com_antes_e_depois(client):
    admin, dev = pessoa("administrador"), pessoa("desenvolvedor")
    api(client, admin, "patch", f"/api/v1/vetor/perfis/{dev.id}", {"papel": "gestor", "ver_custos": True})
    reg = Auditoria.objects.get(acao="perfil.alterado")
    assert reg.ator_id == admin.id
    assert reg.detalhes["antes"] == {"papel": "desenvolvedor", "ver_custos": False}
    assert reg.detalhes["depois"] == {"papel": "gestor", "ver_custos": True}


# Acesso cruzado (critério de aceite) -----------------------------------------------------------

def test_quem_nao_e_membro_nao_ve_projeto_historia_anexo_nem_busca(client, projeto):
    proj, gestor = projeto
    proj.is_private, proj.anon_permissions, proj.public_permissions = True, [], []
    proj.save()
    us = f.UserStoryFactory.create(project=proj, subject="Segredo do cliente")
    anexo = f.UserStoryAttachmentFactory.create(project=proj, content_object=us)
    fora = pessoa("gestor")
    assert api(client, fora, "get", f"/api/v1/projects/{proj.id}").status_code == 403
    assert api(client, fora, "get", f"/api/v1/userstories/{us.id}").status_code in (403, 404)
    assert api(client, fora, "get", f"/api/v1/userstories/attachments/{anexo.id}").status_code in (403, 404)
    assert api(client, fora, "get", f"/api/v1/projects/{proj.id}/export").status_code in (403, 404, 405)
    busca = api(client, fora, "get", f"/api/v1/search?project={proj.id}&text=Segredo")
    assert "Segredo" not in busca.content.decode()
    assert api(client, gestor, "get", f"/api/v1/userstories/{us.id}").status_code == 200


def test_convite_em_lote_recusado_nao_fica_pela_metade(client, projeto):
    proj, gestor = projeto
    leitura = f.RoleFactory.create(project=proj, permissions=LEITURA)
    edicao = f.RoleFactory.create(project=proj, permissions=TODAS)
    ok, obs = pessoa("desenvolvedor"), pessoa("observador")
    antes = proj.memberships.count()
    resp = api(client, gestor, "post", "/api/v1/memberships/bulk_create", {"project_id": proj.id, "bulk_memberships": [
        {"role_id": leitura.id, "username": ok.email}, {"role_id": edicao.id, "username": obs.email}]})
    assert resp.status_code == 403
    assert proj.memberships.count() == antes


@pytest.mark.parametrize("url", ["/api/v1/memberships", "/api/v1/roles", "/api/v1/projects", "/api/v1/vetor/perfis",
                                 "/api/v1/webhooks", "/api/v1/users/password_recovery"])
def test_rotas_da_vetor_continuam_isentas_de_csrf_como_as_do_taiga(url):
    # A API autentica por token; sem a isenção o navegador recebe 403 do CsrfViewMiddleware.
    from django.test import Client
    resp = Client(enforce_csrf_checks=True).post(url, "{}", content_type="application/json")
    assert not (resp.status_code == 403 and b"CSRF" in resp.content)
