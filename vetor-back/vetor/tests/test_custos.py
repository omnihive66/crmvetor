"""Custos (SPEC-09): exemplos do aceite, conversão explícita, versões, importação, rateio, alertas e permissão financeira."""
import json
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from tests import factories as f

from vetor.models import Auditoria, Cliente, CustoRealizado, Estimativa, Perfil

pytestmark = pytest.mark.django_db
B = "/api/v1/vetor/custos"


@pytest.fixture(autouse=True)
def ambiente(settings):
    settings.VETOR_PAPEL_SEM_PERFIL = "observador"


def pessoa(papel, ver_custos=True):
    user = f.UserFactory.create()
    Perfil.objects.create(user=user, papel=papel, ver_custos=ver_custos)
    return user


def api(client, user, metodo, url, dados=None):
    client.login(user) if user else client.logout()
    resp = getattr(client, metodo)(url, json.dumps(dados) if dados is not None else None, content_type="application/json")
    client.logout()
    return resp


@pytest.fixture
def fin():
    gestor = pessoa("gestor")
    cliente = Cliente.objects.create(nome="ACME", responsavel=gestor)
    return gestor, cliente


def estimativa(client, gestor, cliente, **kw):
    r = api(client, gestor, "post", f"{B}/estimativas", {"cliente": cliente.id, "nome": "Portal", "moeda": "BRL", "validade": "2026-12-31",
                                                         "fonte": "Tabela AWS out/2026", "premissas": "100 usuários", **kw})
    assert r.status_code == 201, r.content
    return r.json()["id"]


def item(client, gestor, est, **kw):
    r = api(client, gestor, "post", f"{B}/estimativas/{est}/itens", {"categoria": "infra", **kw})
    assert r.status_code == 201, r.content
    return r.json()["id"]


def totais(client, gestor, est):
    return {(g["tipo"], g["recorrencia"]): g for g in api(client, gestor, "get", f"{B}/estimativas/{est}").json()["totais"]["grupos"]}


# Critérios de aceite --------------------------------------------------------------------------

def test_100_unidades_a_20_centavos_mais_50_fixos_da_70_antes_de_ajustes(client, fin):
    gestor, cliente = fin
    est = estimativa(client, gestor, cliente)
    item(client, gestor, est, natureza="variavel", quantidade="100", unidade="GB", preco_unitario="0,20")
    item(client, gestor, est, natureza="fixo", quantidade="1", preco_unitario="50")
    item(client, gestor, est, natureza="ajuste", percentual="10", descricao="Impostos")
    item(client, gestor, est, natureza="ajuste", percentual="-5", descricao="Desconto")
    g = totais(client, gestor, est)[("custo", "mensal")]
    assert (g["variavel"], g["fixo"], g["antes_de_ajustes"]) == ("20.00", "50.00", "70.00")
    assert (g["ajustes"], g["total"]) == ("3.50", "73.50")  # 10% − 5% sobre os 70: ajuste não incide sobre ajuste


def test_orcamento_100_e_realizado_120_mostra_mais_20_e_mais_20_por_cento(client, fin):
    gestor, cliente = fin
    orc = api(client, gestor, "post", f"{B}/orcamentos", {"cliente": cliente.id, "periodo": "2026-10", "valor": "100"}).json()["id"]
    api(client, gestor, "post", f"{B}/realizados", {"cliente": cliente.id, "periodo": "2026-10", "categoria": "infra", "valor": "120"})
    c = api(client, gestor, "get", f"{B}/orcamentos/{orc}/comparacao").json()
    assert (c["orcamento"], c["realizado"], c["diferenca"], c["percentual"]) == ("100.00", "120.00", "20.00", "20.00")
    assert {a["codigo"] for a in c["alertas"]} == {"acima_do_orcamento", "desvio_percentual"} and c["corte_automatico"] is False


def test_orcamento_zero_nao_divide_por_zero(client, fin):
    gestor, cliente = fin
    orc = api(client, gestor, "post", f"{B}/orcamentos", {"cliente": cliente.id, "periodo": "2026-10", "valor": "0"}).json()["id"]
    c = api(client, gestor, "get", f"{B}/orcamentos/{orc}/comparacao").json()
    assert (c["percentual"], c["alertas"]) == (None, [])
    api(client, gestor, "post", f"{B}/realizados", {"cliente": cliente.id, "periodo": "2026-10", "categoria": "infra", "valor": "5"})
    c = api(client, gestor, "get", f"{B}/orcamentos/{orc}/comparacao").json()
    assert c["percentual"] is None and [a["codigo"] for a in c["alertas"]] == ["orcamento_zero"]


def test_mesma_importacao_nao_duplica_e_tudo_ou_nada(client, fin):
    gestor, cliente = fin
    csv = (f"id;periodo;categoria;descricao;valor;moeda;cliente;parcial\n"
           f"l1;2026-10;infra;EC2;1.234,56;BRL;{cliente.id};não\nl2;2026-10;rede;Tráfego;0,000125;BRL;;sim\n").encode()
    envio = lambda dados: (client.login(gestor), client.post(f"{B}/realizados/importar", {"lote": "aws-2026-10", "arquivo": SimpleUploadedFile("a.csv", dados)}))[1]
    r = envio(csv)
    assert r.status_code == 200 and r.json() == {"lote": "aws-2026-10", "importados": 2, "ja_existiam": 0, "nao_alocados": 1}
    assert envio(csv).json()["importados"] == 0 and CustoRealizado.objects.count() == 2
    assert CustoRealizado.objects.get(id_externo="l1").valor == Decimal("1234.56")
    assert CustoRealizado.objects.get(id_externo="l2").valor == Decimal("0.000125")  # fração preservada
    ruim = csv + b"l3;2026-13;infra;x;abc;BRL;;\n"
    r = envio(ruim)
    assert r.status_code == 400 and "linha 4" in json.dumps(r.json(), ensure_ascii=False) and CustoRealizado.objects.count() == 2
    client.logout()


def test_ajuste_e_remocao_auditados_sem_valores(client, fin):
    gestor, cliente = fin
    est = estimativa(client, gestor, cliente)
    it = item(client, gestor, est, quantidade="3", preco_unitario="987.65")
    api(client, gestor, "patch", f"{B}/itens/{it}", {"preco_unitario": "123.45"})
    api(client, gestor, "delete", f"{B}/itens/{it}")
    c = api(client, gestor, "post", f"{B}/realizados", {"cliente": cliente.id, "periodo": "2026-10", "categoria": "infra", "valor": "4321.99"}).json()["id"]
    api(client, gestor, "patch", f"{B}/realizados/{c}", {"valor": "1111.11"})
    api(client, gestor, "delete", f"{B}/realizados/{c}")
    acoes = list(Auditoria.objects.values_list("acao", flat=True))
    for a in ("estimativa.item_alterado", "estimativa.item_removido", "custo_realizado.alterado", "custo_realizado.removido"):
        assert a in acoes
    tudo = json.dumps(list(Auditoria.objects.values_list("detalhes", flat=True)))
    assert not any(v in tudo for v in ("987", "123.45", "4321", "1111"))  # auditoria vista por quem não tem ver_custos


def test_so_quem_tem_permissao_financeira_consulta_inclusive_api_e_exportacao(client, fin):
    gestor, cliente = fin
    est = estimativa(client, gestor, cliente)
    api(client, gestor, "post", f"{B}/realizados", {"cliente": cliente.id, "periodo": "2026-10", "categoria": "infra", "valor": "120"})
    sem = pessoa("administrador", ver_custos=False)  # nem o Administrador sem a permissão explícita
    for url in (f"{B}/estimativas", f"{B}/estimativas/{est}", f"{B}/realizados", f"{B}/realizados/exportar", f"{B}/orcamentos",
                f"{B}/rateios", f"{B}/taxas", f"{B}/realizados?nao_alocados=true&periodo=2026-10"):
        assert api(client, sem, "get", url).status_code == 403, url
        assert api(client, None, "get", url).status_code == 401, url
    assert api(client, sem, "post", f"{B}/realizados", {"cliente": cliente.id, "periodo": "2026-10", "categoria": "x", "valor": "1"}).status_code == 403
    # Valores não vazam por outras rotas.
    for url in (f"/api/v1/vetor/clientes/{cliente.id}", f"/api/v1/vetor/clientes/{cliente.id}/painel", "/api/v1/vetor/busca?q=infra"):
        assert "120" not in api(client, sem, "get", url).content.decode()
    exportado = (client.login(gestor), client.get(f"{B}/realizados/exportar?periodo=2026-10"))[1]
    assert exportado.status_code == 200 and "120" in exportado.content.decode() and exportado["Content-Type"].startswith("text/csv")
    observador = pessoa("observador")  # vê custos, mas não altera
    assert api(client, observador, "get", f"{B}/realizados").status_code == 200
    assert api(client, observador, "post", f"{B}/realizados", {"cliente": cliente.id, "periodo": "2026-10", "categoria": "x", "valor": "1"}).status_code == 403
    outro = pessoa("gestor")  # tem ver_custos mas não vê este cliente
    assert api(client, outro, "get", f"{B}/realizados?cliente={cliente.id}").json() == []


# Regras ---------------------------------------------------------------------------------------

def test_conversao_so_com_taxa_registrada(client, fin):
    gestor, cliente = fin
    est = estimativa(client, gestor, cliente)
    item(client, gestor, est, natureza="fixo", preco_unitario="10", moeda="USD")
    d = api(client, gestor, "get", f"{B}/estimativas/{est}").json()["totais"]
    assert d["pendentes"][0]["motivo"] == "sem taxa registrada de USD para BRL" and d["grupos"][0]["total"] == "0.00"
    taxa = api(client, gestor, "post", f"{B}/taxas", {"moeda_origem": "USD", "moeda_destino": "BRL", "taxa": "5,4321", "data": "2026-10-22", "origem": "PTAX BCB venda"}).json()
    it = item(client, gestor, est, natureza="fixo", preco_unitario="10", moeda="USD", taxa_cambio=taxa["id"])
    d = api(client, gestor, "get", f"{B}/estimativas/{est}").json()["totais"]
    conv = next(i for i in d["itens"] if i["id"] == it)
    assert conv["valor"].startswith("54.321") and conv["conversao"] == {"taxa": "5.432100", "data": "2026-10-22", "origem": "PTAX BCB venda", "par": "USD→BRL"}
    assert d["grupos"][0]["total"] == "54.32"


def test_custo_e_preco_de_venda_e_unico_e_mensal_separados(client, fin):
    gestor, cliente = fin
    est = estimativa(client, gestor, cliente)
    item(client, gestor, est, natureza="fixo", preco_unitario="30", recorrencia="mensal")
    item(client, gestor, est, natureza="fixo", preco_unitario="500", recorrencia="unico", categoria="implantação")
    item(client, gestor, est, natureza="fixo", preco_unitario="90", tipo="preco_venda")
    t = totais(client, gestor, est)
    assert {k: v["total"] for k, v in t.items()} == {("custo", "mensal"): "30.00", ("custo", "unico"): "500.00", ("preco_venda", "mensal"): "90.00"}


def test_versoes_congelam_a_anterior(client, fin):
    gestor, cliente = fin
    v1 = estimativa(client, gestor, cliente)
    it = item(client, gestor, v1, preco_unitario="1")
    v2 = api(client, gestor, "post", f"{B}/estimativas/{v1}/nova_versao").json()
    assert v2["versao"] == 2 and v2["anterior"] == v1
    assert api(client, gestor, "patch", f"{B}/itens/{it}", {"preco_unitario": "2"}).status_code == 400  # v1 congelada
    assert api(client, gestor, "post", f"{B}/estimativas/{v1}/itens", {"categoria": "x"}).status_code == 400
    assert Estimativa.objects.get(pk=v2["id"]).itens.count() == 1
    lista = api(client, gestor, "get", f"{B}/estimativas?cliente={cliente.id}").json()
    assert [(e["versao"], e["editavel"]) for e in lista] == [(2, True), (1, False)]


def test_rateio_explicito_e_nao_alocado(client, fin):
    gestor, cliente = fin
    outro = Cliente.objects.create(nome="Globex", responsavel=gestor)
    api(client, gestor, "post", f"{B}/realizados", {"cliente": None, "periodo": "2026-10", "categoria": "cluster", "valor": "200"})
    api(client, gestor, "post", f"{B}/realizados", {"cliente": None, "periodo": "2026-10", "categoria": "sem-tag", "valor": "7"})
    nao = api(client, gestor, "get", f"{B}/realizados?nao_alocados=true&periodo=2026-10").json()
    assert sorted(c["categoria"] for c in nao) == ["cluster", "sem-tag"]
    assert api(client, gestor, "post", f"{B}/rateios", {"periodo": "2026-10", "categoria": "cluster", "partes": {str(cliente.id): 60, str(outro.id): 30}}).status_code == 400
    assert api(client, gestor, "post", f"{B}/rateios", {"periodo": "2026-10", "categoria": "cluster", "partes": {str(cliente.id): 60, str(outro.id): 40}}).status_code == 201
    assert [c["categoria"] for c in api(client, gestor, "get", f"{B}/realizados?nao_alocados=true&periodo=2026-10").json()] == ["sem-tag"]
    orc = api(client, gestor, "post", f"{B}/orcamentos", {"cliente": cliente.id, "periodo": "2026-10", "valor": "150"}).json()["id"]
    c = api(client, gestor, "get", f"{B}/orcamentos/{orc}/comparacao").json()
    assert c["realizado"] == "120.00" and c["linhas"][0]["como"] == "rateio 60% de cluster"
    nov = api(client, gestor, "post", f"{B}/orcamentos", {"cliente": cliente.id, "periodo": "2026-11", "valor": "150"}).json()["id"]
    api(client, gestor, "post", f"{B}/realizados", {"cliente": None, "periodo": "2026-11", "categoria": "cluster", "valor": "200"})
    assert api(client, gestor, "get", f"{B}/orcamentos/{nov}/comparacao").json()["realizado"] == "0.00"  # regra vale só para o mês dela


def test_consumo_parcial_nao_e_fatura_final_e_moeda_sem_taxa_fica_pendente(client, fin):
    gestor, cliente = fin
    orc = api(client, gestor, "post", f"{B}/orcamentos", {"cliente": cliente.id, "periodo": "2026-10", "valor": "100"}).json()["id"]
    api(client, gestor, "post", f"{B}/realizados", {"cliente": cliente.id, "periodo": "2026-10", "categoria": "infra", "valor": "40", "parcial": True})
    api(client, gestor, "post", f"{B}/realizados", {"cliente": cliente.id, "periodo": "2026-10", "categoria": "aws", "valor": "10", "moeda": "USD"})
    c = api(client, gestor, "get", f"{B}/orcamentos/{orc}/comparacao").json()
    assert c["parcial"] is True and "não é fatura final" in c["aviso_parcial"]
    assert c["realizado"] == "40.00" and c["pendentes"][0]["motivo"] == "sem taxa registrada de USD para BRL"
