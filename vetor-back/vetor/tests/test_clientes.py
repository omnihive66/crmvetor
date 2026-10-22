"""CRM (SPEC-03): cadastro, escopo de acesso, documentos, reuniões e busca."""
import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from taiga.permissions.choices import MEMBERS_PERMISSIONS
from taiga.projects.userstories.models import UserStory
from tests import factories as f

from vetor.models import Auditoria, Cliente, Documento, Perfil, ProjetoCliente

pytestmark = pytest.mark.django_db
TODAS = [p for p, _ in MEMBERS_PERMISSIONS]
LEITURA = [p for p in TODAS if p.startswith("view_")]
CNPJ = "11.222.333/0001-81"


@pytest.fixture(autouse=True)
def padrao_de_producao(settings, tmp_path):
    settings.VETOR_PAPEL_SEM_PERFIL = "observador"
    settings.MEDIA_ROOT = str(tmp_path)


def pessoa(papel):
    user = f.UserFactory.create()
    Perfil.objects.create(user=user, papel=papel)
    return user


def api(client, user, metodo, url, dados=None, multipart=False):
    client.login(user)
    if multipart:
        resp = client.post(url, dados)
    else:
        resp = getattr(client, metodo)(url, json.dumps(dados) if dados is not None else None, content_type="application/json")
    client.logout()
    return resp


def projeto_com(user, permissoes=TODAS, admin=False):
    proj = f.create_project(owner=user if admin else f.UserFactory.create())
    f.MembershipFactory.create(project=proj, user=user, is_admin=admin, role=f.RoleFactory.create(project=proj, permissions=permissoes))
    return proj


@pytest.fixture
def cenario():
    """Cliente com dois projetos: o desenvolvedor só participa do A."""
    gestor, dev, fora = pessoa("gestor"), pessoa("desenvolvedor"), pessoa("gestor")
    cliente = Cliente.objects.create(nome="ACME", responsavel=gestor)
    a, b = projeto_com(gestor, admin=True), projeto_com(gestor, admin=True)
    f.MembershipFactory.create(project=a, user=dev, role=f.RoleFactory.create(project=a, permissions=TODAS))
    ProjetoCliente.objects.create(project=a, cliente=cliente)
    ProjetoCliente.objects.create(project=b, cliente=cliente)
    return cliente, gestor, dev, fora, a, b


# Cadastro -----------------------------------------------------------------------------------

def test_cnpj_validado_unico_e_opcional_para_prospect(client):
    g = pessoa("gestor")
    url = "/api/v1/vetor/clientes"
    assert api(client, g, "post", url, {"nome": "Prospect sem CNPJ"}).status_code == 201
    criado = api(client, g, "post", url, {"nome": "Com CNPJ", "cnpj": CNPJ})
    assert criado.status_code == 201 and criado.json()["cnpj"] == "11222333000181"
    assert "inválido" in api(client, g, "post", url, {"nome": "X", "cnpj": "11.222.333/0001-82"}).json()["cnpj"][0]
    assert "Já existe" in api(client, g, "post", url, {"nome": "Y", "cnpj": "11222333000181"}).json()["cnpj"][0]
    assert api(client, g, "post", url, {"nome": "Z", "cnpj": CNPJ, "estrangeiro": True}).status_code == 400
    assert api(client, g, "post", url, {"nome": "Gmbh", "estrangeiro": True, "documento_estrangeiro": "DE123"}).status_code == 201


def test_nome_repetido_pede_confirmacao_mas_nao_bloqueia(client):
    g = pessoa("gestor")
    api(client, g, "post", "/api/v1/vetor/clientes", {"nome": "Padaria Central"})
    repetido = api(client, g, "post", "/api/v1/vetor/clientes", {"nome": "padaria central"})
    assert repetido.status_code == 400 and "duplicado_possivel" in repetido.json()
    assert api(client, g, "post", "/api/v1/vetor/clientes", {"nome": "padaria central", "confirmar_duplicado": True}).status_code == 201


@pytest.mark.parametrize("papel,esperado", [("administrador", 201), ("gestor", 201), ("desenvolvedor", 403), ("observador", 403)])
def test_quem_cadastra_cliente(client, papel, esperado):
    assert api(client, pessoa(papel), "post", "/api/v1/vetor/clientes", {"nome": "Novo"}).status_code == esperado


# Escopo ---------------------------------------------------------------------------------------

def test_escopo_leitura_e_edicao(client, cenario):
    cliente, gestor, dev, fora, a, b = cenario
    url = f"/api/v1/vetor/clientes/{cliente.id}"
    assert api(client, gestor, "patch", url, {"ciclo": "implantacao"}).status_code == 200
    visto = api(client, dev, "get", url)
    assert visto.status_code == 200 and [p["id"] for p in visto.json()["projetos"]] == [a.id]  # B não aparece
    assert api(client, dev, "patch", url, {"nome": "Outro"}).status_code == 403
    assert api(client, fora, "get", url).status_code == 404
    assert api(client, fora, "patch", url, {"nome": "Outro"}).status_code == 404
    assert api(client, fora, "get", "/api/v1/vetor/clientes").json() == []
    assert api(client, pessoa("administrador"), "get", url).status_code == 200


def test_busca_por_nome_e_cnpj_filtros_e_paginacao(client):
    admin = pessoa("administrador")
    Cliente.objects.create(nome="Alfa Ltda", cnpj="11222333000181", ciclo="operacao")
    Cliente.objects.create(nome="Beta", ciclo="negociacao")
    for i in range(35):
        Cliente.objects.create(nome=f"Lote {i:02}")
    nomes = lambda r: [c["nome"] for c in r.json()]
    assert nomes(api(client, admin, "get", "/api/v1/vetor/clientes?q=alfa")) == ["Alfa Ltda"]
    assert nomes(api(client, admin, "get", "/api/v1/vetor/clientes?q=11.222")) == ["Alfa Ltda"]
    assert nomes(api(client, admin, "get", "/api/v1/vetor/clientes?ciclo=negociacao")) == ["Beta"] + [f"Lote {i:02}" for i in range(29)]  # primeira página: 30
    pagina = api(client, admin, "get", "/api/v1/vetor/clientes")
    assert len(pagina.json()) == 30 and pagina["x-pagination-count"] == "37"


def test_cliente_com_projeto_nao_e_excluido_mas_pode_ser_arquivado(client, cenario):
    cliente, gestor, *_ = cenario
    url = f"/api/v1/vetor/clientes/{cliente.id}"
    negado = api(client, gestor, "delete", url)
    assert negado.status_code == 400 and "Arquive" in negado.json()["projetos"][0]
    assert api(client, gestor, "patch", url, {"arquivado": True}).json()["arquivado"] is True
    assert api(client, gestor, "get", "/api/v1/vetor/clientes").json() == []
    assert [c["nome"] for c in api(client, gestor, "get", "/api/v1/vetor/clientes?arquivados=true").json()] == ["ACME"]
    assert Auditoria.objects.filter(acao="cliente.arquivado", alvo_id=str(cliente.id), ator=gestor).exists()
    vazio = Cliente.objects.create(nome="Sem projetos", responsavel=gestor)
    assert api(client, gestor, "delete", f"/api/v1/vetor/clientes/{vazio.id}").status_code == 204


def test_historico_do_cliente_para_quem_ve(client, cenario):
    cliente, gestor, dev, fora, *_ = cenario
    api(client, gestor, "patch", f"/api/v1/vetor/clientes/{cliente.id}", {"ciclo": "operacao"})
    api(client, gestor, "post", "/api/v1/vetor/contatos", {"cliente": cliente.id, "nome": "Ana"})
    hist = api(client, dev, "get", f"/api/v1/vetor/clientes/{cliente.id}/historico").json()
    assert [h["acao"] for h in hist] == ["contato.criado", "cliente.alterado"] and hist[1]["campos"] == ["ciclo"]
    assert api(client, fora, "get", f"/api/v1/vetor/clientes/{cliente.id}/historico").status_code == 404


def test_vincular_projeto_exige_admin_do_projeto_e_projeto_livre(client, cenario):
    cliente, gestor, dev, fora, a, b = cenario
    outro = Cliente.objects.create(nome="Outro", responsavel=gestor)
    resp = api(client, gestor, "post", f"/api/v1/vetor/clientes/{outro.id}/vincular_projeto", {"projeto": a.id})
    assert resp.status_code == 400 and "ACME" in resp.json()["projeto"][0]
    livre = projeto_com(gestor, admin=True)
    assert api(client, gestor, "post", f"/api/v1/vetor/clientes/{outro.id}/vincular_projeto", {"projeto": livre.id}).status_code == 200
    so_membro = projeto_com(gestor, admin=False)
    assert api(client, gestor, "post", f"/api/v1/vetor/clientes/{outro.id}/vincular_projeto", {"projeto": so_membro.id}).status_code == 403


# Contatos -------------------------------------------------------------------------------------

def test_contatos_respeitam_o_acesso_ao_cliente(client, cenario):
    cliente, gestor, dev, fora, *_ = cenario
    criado = api(client, gestor, "post", "/api/v1/vetor/contatos", {"cliente": cliente.id, "nome": "Ana", "email": "ana@acme.com"})
    assert criado.status_code == 201
    assert api(client, gestor, "post", "/api/v1/vetor/contatos", {"cliente": cliente.id, "nome": "B", "email": "x"}).status_code == 400
    assert [c["nome"] for c in api(client, dev, "get", f"/api/v1/vetor/contatos?cliente={cliente.id}").json()] == ["Ana"]
    assert api(client, dev, "post", "/api/v1/vetor/contatos", {"cliente": cliente.id, "nome": "Z"}).status_code == 403
    assert api(client, fora, "get", f"/api/v1/vetor/contatos/{criado.json()['id']}").status_code in (404, 405)
    assert api(client, fora, "get", f"/api/v1/vetor/contatos?cliente={cliente.id}").json() == []


# Documentos ---------------------------------------------------------------------------------

def arquivo(nome="contrato.pdf", conteudo=b"%PDF-1.4 ficticio"):
    return SimpleUploadedFile(nome, conteudo, content_type="application/octet-stream")


def test_documento_de_projeto_so_para_quem_ve_o_projeto(client, cenario):
    cliente, gestor, dev, fora, a, b = cenario
    url = "/api/v1/vetor/documentos"
    geral = api(client, gestor, "post", url, {"cliente": cliente.id, "titulo": "Contrato", "categoria": "contrato", "arquivo": arquivo()}, multipart=True)
    assert geral.status_code == 201 and geral.json()["url"].split("?")[0].count("/attachments/") == 1
    so_b = api(client, gestor, "post", url, {"cliente": cliente.id, "projeto": b.id, "titulo": "Escopo B", "arquivo": arquivo("b.pdf")}, multipart=True)
    assert so_b.status_code == 201
    titulos = [d["titulo"] for d in api(client, dev, "get", f"{url}?cliente={cliente.id}").json()]
    assert titulos == ["Contrato"]
    assert api(client, dev, "get", f"{url}/{so_b.json()['id']}").status_code == 404
    assert api(client, fora, "get", f"{url}/{geral.json()['id']}").status_code == 404


def test_documento_valida_tipo_tamanho_e_link(client, cenario, settings):
    cliente, gestor, *_ = cenario
    url = "/api/v1/vetor/documentos"
    assert "não permitido" in api(client, gestor, "post", url, {"cliente": cliente.id, "titulo": "x", "arquivo": arquivo("virus.exe")}, multipart=True).json()["arquivo"][0]
    settings.VETOR_DOCUMENTO_MAX_MB = 0
    assert "maior que" in api(client, gestor, "post", url, {"cliente": cliente.id, "titulo": "x", "arquivo": arquivo()}, multipart=True).json()["arquivo"][0]
    assert api(client, gestor, "post", url, {"cliente": cliente.id, "titulo": "x", "url_externa": "http://inseguro.com/a", "origem_externa": "Drive"}).status_code == 400
    assert api(client, gestor, "post", url, {"cliente": cliente.id, "titulo": "x", "url_externa": "https://drive.example.com/a"}).status_code == 400  # sem origem
    link = api(client, gestor, "post", url, {"cliente": cliente.id, "titulo": "Planilha", "url_externa": "https://drive.example.com/a", "origem_externa": "Google Drive"})
    assert link.status_code == 201 and link.json()["url"] is None and link.json()["origem_externa"] == "Google Drive"


def test_copiar_como_modelo_exige_confirmacao_e_nao_leva_o_projeto(client, cenario):
    cliente, gestor, dev, fora, a, b = cenario
    doc = api(client, gestor, "post", "/api/v1/vetor/documentos", {"cliente": cliente.id, "projeto": a.id, "titulo": "Proposta", "arquivo": arquivo()}, multipart=True).json()
    destino = Cliente.objects.create(nome="Beta", responsavel=gestor)
    url = f"/api/v1/vetor/documentos/{doc['id']}/copiar_como_modelo"
    assert api(client, gestor, "post", url, {"cliente": destino.id}).status_code == 400
    copia = api(client, gestor, "post", url, {"cliente": destino.id, "confirmar": True}).json()
    assert (copia["cliente"], copia["projeto"], copia["modelo_de"], copia["categoria"]) == (destino.id, None, doc["id"], "modelo")
    assert Documento.objects.get(pk=copia["id"]).arquivo.read() == b"%PDF-1.4 ficticio"
    assert Documento.objects.filter(cliente=cliente).count() == 1  # origem intacta, nada compartilhado


# Reuniões -----------------------------------------------------------------------------------

def test_reuniao_vira_demanda_no_projeto_do_cliente(client, cenario):
    cliente, gestor, dev, fora, a, b = cenario
    r = api(client, gestor, "post", "/api/v1/vetor/reunioes", {"cliente": cliente.id, "data": "2026-10-20T14:00:00-03:00",
                                                               "participantes_internos": [dev.id], "notas": "Ata", "proximos_passos": "Enviar proposta"})
    assert r.status_code == 201 and r.json()["participantes_internos"][0]["id"] == dev.id
    url = f"/api/v1/vetor/reunioes/{r.json()['id']}/criar_demanda"
    assert api(client, gestor, "post", url, {"projeto": projeto_com(gestor, admin=True).id, "assunto": "X"}).status_code == 400
    obs = pessoa("observador")
    f.MembershipFactory.create(project=a, user=obs, role=f.RoleFactory.create(project=a, permissions=LEITURA))
    assert api(client, obs, "post", url, {"projeto": a.id, "assunto": "X"}).status_code == 403
    criada = api(client, dev, "post", url, {"projeto": a.id, "assunto": "Enviar proposta", "descricao": "Da reunião"})
    assert criada.status_code == 201
    us = UserStory.objects.get(pk=criada.json()["id"])
    assert (us.project_id, us.owner_id, us.subject) == (a.id, dev.id, "Enviar proposta")
    from taiga.projects.history.models import HistoryEntry
    assert HistoryEntry.objects.filter(key=f"userstories.userstory:{us.id}").exists()
    assert api(client, gestor, "get", f"/api/v1/vetor/reunioes/{r.json()['id']}").json()["demandas"][0]["id"] == us.id


def test_reuniao_exige_data_com_fuso(client, cenario):
    cliente, gestor, *_ = cenario
    assert api(client, gestor, "post", "/api/v1/vetor/reunioes", {"cliente": cliente.id, "data": "2026-10-20T14:00:00"}).status_code == 400


# Busca global -------------------------------------------------------------------------------

def test_busca_so_mostra_o_que_a_pessoa_pode_ver(client, cenario):
    cliente, gestor, dev, fora, a, b = cenario
    f.UserStoryFactory.create(project=a, subject="Integração ACME visível")
    f.UserStoryFactory.create(project=b, subject="Integração ACME secreta")
    Documento.objects.create(cliente=cliente, projeto=b, titulo="ACME contrato B", url_externa="https://x.example", origem_externa="Drive")
    r = api(client, dev, "get", "/api/v1/vetor/busca?q=ACME").json()
    assert [c["nome"] for c in r["clientes"]] == ["ACME"]
    assert [h["assunto"] for h in r["historias"]] == ["Integração ACME visível"]
    assert r["documentos"] == []
    vazio = api(client, fora, "get", "/api/v1/vetor/busca?q=ACME").json()
    assert vazio == {"clientes": [], "documentos": [], "projetos": [], "historias": []}


def test_busca_nao_aceita_permissao_de_outro_membro(client):
    # A pessoa vê o projeto mas não as histórias; outro membro vê as histórias. Nada de histórias para ela.
    vê_projeto = pessoa("observador")
    proj = projeto_com(vê_projeto, permissoes=["view_project"])
    f.MembershipFactory.create(project=proj, user=pessoa("desenvolvedor"), role=f.RoleFactory.create(project=proj, permissions=TODAS))
    f.UserStoryFactory.create(project=proj, subject="Restrita")
    assert api(client, vê_projeto, "get", "/api/v1/vetor/busca?q=Restrita").json()["historias"] == []
