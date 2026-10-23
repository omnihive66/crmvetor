"""Repositórios e GitHub (SPEC-06): validação da integração nativa e o conector da Vetor (webhook → vínculos)."""
import hashlib
import hmac
import json
import logging

import pytest
from django.urls import reverse

from taiga.permissions.choices import MEMBERS_PERMISSIONS
from taiga.projects.issues.models import Issue
from taiga.projects.userstories.models import UserStory
from tests import factories as f

from vetor import github
from vetor.models import Auditoria, EventoProvedor, Perfil, Repositorio, VinculoCodigo

pytestmark = pytest.mark.django_db
SEGREDO = "segredo-de-teste-123"
URL = "/api/v1/vetor/github/webhook"


@pytest.fixture(autouse=True)
def ambiente(settings):
    settings.VETOR_PAPEL_SEM_PERFIL = "observador"
    settings.VETOR_GITHUB_WEBHOOK_SEGREDOS = [SEGREDO]


def pessoa(papel):
    user = f.UserFactory.create()
    Perfil.objects.create(user=user, papel=papel)
    return user


def assinar(corpo, segredo=SEGREDO):
    return "sha256=" + hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()


def entregar(client, evento, payload, entrega="e-1", assinatura=None):
    corpo = json.dumps(payload).encode()
    cab = {"HTTP_X_GITHUB_EVENT": evento, "HTTP_X_GITHUB_DELIVERY": entrega}
    if assinatura is not False:
        cab["HTTP_X_HUB_SIGNATURE_256"] = assinatura or assinar(corpo)
    return client.post(URL, corpo, content_type="application/json", **cab)


def repo_json(nome="vetor/portal", rid=42):
    return {"id": rid, "full_name": nome}


def pr(numero=7, titulo="TG-{ref} Corrige login", estado="open", merged=False, draft=False, quando="2026-10-23T10:00:00Z", pid=900, ref=1):
    return {"action": "opened", "repository": repo_json(), "pull_request": {
        "id": pid, "number": numero, "html_url": f"https://github.com/vetor/portal/pull/{numero}", "title": titulo.format(ref=ref),
        "body": "", "state": estado, "merged": merged, "draft": draft, "user": {"login": "dev-gh"}, "updated_at": quando,
        "head": {"ref": "feature/login"}}}


@pytest.fixture
def cenario():
    gestor = pessoa("gestor")
    proj = f.create_project(owner=f.UserFactory.create())
    f.MembershipFactory.create(project=proj, user=gestor, is_admin=True,
                               role=f.RoleFactory.create(project=proj, permissions=[p for p, _ in MEMBERS_PERMISSIONS]))
    us = f.UserStoryFactory.create(project=proj, milestone=None, subject="Login")
    repo = Repositorio.objects.create(projeto=proj, nome="vetor/portal")
    return proj, us, repo, gestor


# Integração nativa do Taiga 6.10 (validada antes de ampliar) ---------------------------------

def test_nativo_recusa_sem_assinatura_e_duplica_issue_no_reenvio(client):
    proj = f.ProjectFactory.create()
    f.ProjectModulesConfigFactory.create(project=proj, config={"github": {"secret": "s"}})
    url = reverse("github-hook-list") + f"?project={proj.id}"
    assert client.post(url, "{}", content_type="application/json").status_code == 400
    corpo = json.dumps({"action": "opened", "issue": {"title": "Erro", "body": "x", "html_url": "https://github.com/a/b/issues/1",
                                                      "number": 1, "user": {"id": 1, "html_url": "u"}}, "repository": {"html_url": "r"}}).encode()
    sig = "sha1=" + hmac.new(b"s", corpo, hashlib.sha1).hexdigest()
    for _ in range(2):  # o GitHub reenvia a mesma entrega: o nativo cria de novo
        assert client.post(url, corpo, content_type="application/json", HTTP_X_GITHUB_EVENT="issues", HTTP_X_HUB_SIGNATURE=sig).status_code == 204
    assert Issue.objects.filter(project=proj, subject="Erro").count() == 2
    pr_corpo = json.dumps(pr()).encode()
    assert client.post(url, pr_corpo, content_type="application/json", HTTP_X_GITHUB_EVENT="pull_request",
                       HTTP_X_HUB_SIGNATURE="sha1=" + hmac.new(b"s", pr_corpo, hashlib.sha1).hexdigest()).status_code == 204  # PR: ignorado


# Assinatura, deduplicação e configuração -------------------------------------------------------

def test_sem_assinatura_ou_assinatura_errada_falha_e_nada_e_gravado(client, cenario):
    assert entregar(client, "pull_request", pr(), assinatura=False).status_code == 401
    assert entregar(client, "pull_request", pr(), assinatura=assinar(b"outro corpo")).status_code == 401
    assert entregar(client, "pull_request", pr(), assinatura="sha1=abc").status_code == 401
    assert not EventoProvedor.objects.exists() and not VinculoCodigo.objects.exists()


def test_sem_segredo_configurado_a_integracao_nao_esta_ativa(client, cenario, settings):
    settings.VETOR_GITHUB_WEBHOOK_SEGREDOS = []
    assert entregar(client, "pull_request", pr()).status_code == 503


def test_rotacao_aceita_o_segredo_anterior(client, cenario, settings):
    settings.VETOR_GITHUB_WEBHOOK_SEGREDOS = ["novo", SEGREDO]
    assert entregar(client, "pull_request", pr()).status_code == 202


def test_evento_legitimo_vincula_a_historia_citada_e_reenvio_nao_duplica(client, cenario):
    proj, us, repo, _ = cenario
    assert entregar(client, "pull_request", pr(ref=us.ref)).status_code == 202
    v = VinculoCodigo.objects.get()
    assert (v.historia_id, v.tipo, v.numero, v.estado, v.autor_externo) == (us.id, "pr", 7, "open", "dev-gh")
    assert v.evento.entrega == "e-1" and v.evento.payload["pull_request"]["number"] == 7  # origem preservada
    reenvio = entregar(client, "pull_request", pr(ref=us.ref))
    assert reenvio.status_code == 200 and reenvio.json()["status"] == "duplicado"
    assert VinculoCodigo.objects.count() == 1 and EventoProvedor.objects.count() == 1
    repo.refresh_from_db()
    assert repo.id_externo == "42"


def test_estados_do_pr_e_fechado_sem_merge_nao_conclui(client, cenario):
    proj, us, repo, _ = cenario
    etapa = us.status_id
    entregar(client, "pull_request", pr(ref=us.ref, draft=True, quando="2026-10-23T10:00:00Z"), entrega="a")
    assert VinculoCodigo.objects.get().estado == "draft"
    entregar(client, "pull_request", pr(ref=us.ref, estado="closed", quando="2026-10-23T11:00:00Z"), entrega="b")
    assert VinculoCodigo.objects.get().estado == "closed"
    us.refresh_from_db()
    assert us.status_id == etapa and not us.is_closed  # a Vetor não move etapa: conclusão é confirmação manual
    entregar(client, "pull_request", pr(ref=us.ref, estado="closed", merged=True, quando="2026-10-23T12:00:00Z"), entrega="c")
    assert VinculoCodigo.objects.get().estado == "merged"
    # Entrega antiga atrasada não volta o estado.
    entregar(client, "pull_request", pr(ref=us.ref, quando="2026-10-23T10:30:00Z"), entrega="d")
    assert VinculoCodigo.objects.get().estado == "merged"
    us.refresh_from_db()
    assert us.status_id == etapa


def test_pr_editado_troca_a_historia_citada(client, cenario):
    proj, us, repo, _ = cenario
    outra = f.UserStoryFactory.create(project=proj, milestone=None)
    entregar(client, "pull_request", pr(ref=us.ref, quando="2026-10-23T10:00:00Z"), entrega="a")
    entregar(client, "pull_request", pr(ref=outra.ref, quando="2026-10-23T11:00:00Z"), entrega="b")
    assert list(VinculoCodigo.objects.values_list("historia_id", flat=True)) == [outra.id]


def test_push_vincula_commits_e_issue_tambem(client, cenario):
    proj, us, repo, _ = cenario
    commits = [{"id": "a" * 40, "message": f"Ajusta tela TG-{us.ref}\n\ndetalhes", "url": "https://github.com/vetor/portal/commit/aaa",
                "author": {"username": "dev-gh"}, "timestamp": "2026-10-23T09:00:00-03:00"},
               {"id": "b" * 40, "message": "sem referência", "url": "https://github.com/vetor/portal/commit/bbb", "author": {}, "timestamp": None}]
    entregar(client, "push", {"repository": repo_json(), "commits": commits}, entrega="p")
    issue = {"action": "opened", "repository": repo_json(), "issue": {"id": 555, "number": 3, "html_url": "https://github.com/vetor/portal/issues/3",
             "title": "Bug", "body": f"Relacionado a tg-{us.ref}", "state": "open", "user": {"login": "cliente"}, "updated_at": "2026-10-23T10:00:00Z"}}
    entregar(client, "issues", issue, entrega="i")
    assert sorted(VinculoCodigo.objects.values_list("tipo", "titulo")) == [("commit", f"Ajusta tela TG-{us.ref}"), ("issue", "Bug")]


def test_nao_vincula_repositorio_desconhecido_nem_historia_de_outro_projeto(client, cenario):
    proj, us, repo, _ = cenario
    alheia = f.UserStoryFactory.create(project=f.create_project(owner=f.UserFactory.create()), milestone=None)
    UserStory.objects.filter(pk=alheia.pk).update(ref=us.ref + 50)
    alheia.refresh_from_db()
    payload = pr(ref=alheia.ref)
    payload["repository"] = repo_json("outro/repo", 99)
    entregar(client, "pull_request", payload, entrega="x")
    assert EventoProvedor.objects.get(entrega="x").status == "ignorado"
    entregar(client, "pull_request", pr(ref=alheia.ref, pid=901), entrega="y")  # TG-51 existe só no outro projeto
    assert EventoProvedor.objects.get(entrega="y").status == "processado" and not VinculoCodigo.objects.exists()
    entregar(client, "ping", {"zen": "x"}, entrega="z")
    assert EventoProvedor.objects.get(entrega="z").status == "ignorado"


def test_repositorio_renomeado_continua_ligado_pelo_id(client, cenario):
    proj, us, repo, _ = cenario
    entregar(client, "pull_request", pr(ref=us.ref), entrega="a")
    renomeado = pr(ref=us.ref, pid=902, numero=8)
    renomeado["repository"] = repo_json("vetor/portal-novo", 42)
    entregar(client, "pull_request", renomeado, entrega="b")
    repo.refresh_from_db()
    assert repo.nome == "vetor/portal-novo" and VinculoCodigo.objects.count() == 2


def test_falha_no_processamento_fica_na_fila_e_reprocessa_sem_perder_a_origem(client, cenario, monkeypatch):
    proj, us, repo, _ = cenario
    original = github._vincular
    monkeypatch.setattr(github, "_vincular", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("banco indisponível")))
    entregar(client, "pull_request", pr(ref=us.ref), entrega="f")
    ev = EventoProvedor.objects.get(entrega="f")
    assert (ev.status, ev.tentativas, ev.erro) == ("falhou", 1, "RuntimeError: banco indisponível")
    assert not VinculoCodigo.objects.exists()
    monkeypatch.setattr(github, "_vincular", original)
    # Redeliver no GitHub (mesma entrega) tenta de novo.
    assert entregar(client, "pull_request", pr(ref=us.ref), entrega="f").json()["status"] == "duplicado"
    ev.refresh_from_db()
    assert (ev.status, ev.tentativas) == ("processado", 2) and VinculoCodigo.objects.count() == 1


def test_reprocessar_pela_fila_so_administrador(client, cenario, monkeypatch):
    proj, us, repo, gestor = cenario
    monkeypatch.setattr(github, "_vincular", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    entregar(client, "pull_request", pr(ref=us.ref), entrega="g")
    monkeypatch.undo()
    ev = EventoProvedor.objects.get(entrega="g")
    admin = pessoa("administrador")
    client.login(gestor)
    assert client.get("/api/v1/vetor/eventos-github").status_code == 403
    assert client.post(f"/api/v1/vetor/eventos-github/{ev.id}/reprocessar").status_code == 403
    client.login(admin)
    fila = client.get("/api/v1/vetor/eventos-github?status=falhou").json()
    assert [e["entrega"] for e in fila] == ["g"] and "payload" not in fila[0]
    assert client.post(f"/api/v1/vetor/eventos-github/{ev.id}/reprocessar").json()["status"] == "processado"
    assert client.post(f"/api/v1/vetor/eventos-github/{ev.id}/reprocessar").status_code == 400


# Repositórios e visibilidade dos vínculos ------------------------------------------------------

def test_ligar_repositorio_e_do_administrador_e_fica_auditado(client, cenario):
    proj, us, repo, gestor = cenario
    admin = pessoa("administrador")
    f.MembershipFactory.create(project=proj, user=admin, is_admin=True, role=f.RoleFactory.create(project=proj, permissions=["view_project"]))
    client.login(gestor)
    assert client.post("/api/v1/vetor/repositorios", json.dumps({"projeto": proj.id, "nome": "vetor/api"}), content_type="application/json").status_code == 403
    client.login(admin)
    url = "/api/v1/vetor/repositorios"
    assert client.post(url, json.dumps({"projeto": proj.id, "nome": "nao valido"}), content_type="application/json").status_code == 400
    assert client.post(url, json.dumps({"projeto": proj.id, "nome": "VETOR/portal"}), content_type="application/json").status_code == 400  # já ligado
    novo = client.post(url, json.dumps({"projeto": proj.id, "nome": "https://github.com/vetor/api"}), content_type="application/json")
    assert novo.status_code == 201 and novo.json()["nome"] == "vetor/api"
    assert Auditoria.objects.filter(acao="repositorio.ligado").exists()
    assert client.delete(f"{url}/{novo.json()['id']}").status_code == 204


def test_vinculos_so_para_quem_ve_a_historia(client, cenario):
    proj, us, repo, gestor = cenario
    entregar(client, "pull_request", pr(ref=us.ref))
    client.login(gestor)
    assert [v["numero"] for v in client.get(f"/api/v1/vetor/vinculos-codigo?historia={us.id}").json()] == [7]
    client.login(pessoa("gestor"))
    assert client.get(f"/api/v1/vetor/vinculos-codigo?historia={us.id}").json() == []
    client.logout()
    assert client.get(f"/api/v1/vetor/vinculos-codigo?historia={us.id}").status_code == 401


def test_segredo_e_assinatura_nunca_vao_para_log_nem_api(client, cenario, caplog):
    proj, us, repo, gestor = cenario
    caplog.set_level(logging.DEBUG)
    payload = pr(ref=us.ref)
    entregar(client, "pull_request", payload)
    entregar(client, "pull_request", payload, entrega="z", assinatura=False)
    assinatura = assinar(json.dumps(payload).encode())
    assert SEGREDO not in caplog.text and assinatura[7:] not in caplog.text and "Corrige login" not in caplog.text
    client.login(pessoa("administrador"))
    tudo = "".join(client.get(u).content.decode() for u in ("/api/v1/vetor/eventos-github", "/api/v1/vetor/repositorios",
                                                             f"/api/v1/vetor/vinculos-codigo?historia={us.id}"))
    assert SEGREDO not in tudo and assinatura[7:] not in tudo
