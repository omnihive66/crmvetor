"""Custos (SPEC-09): estimativa, realizado, rateio e orçamento. Regras explícitas, Decimal do começo ao fim.

- Item: quantidade × preço unitário (fixo ou variável). Ajuste (imposto, desconto) é linha em % sobre a base do
  próprio grupo (tipo × recorrência) — nunca sobre outro ajuste, então não há dupla contagem.
- Moeda diferente só entra com taxa registrada (taxa, data, origem); sem taxa, fica pendente e fora do total.
- Custo ≠ preço de venda: totais separados. Único ≠ mensal: totais separados.
"""
import csv
import datetime
import io
from decimal import Decimal, InvalidOperation

from taiga.base import exceptions as exc

from .models import Cliente, CustoRealizado, ItemEstimativa, RegraRateio

CENTAVO = Decimal("0.01")
CEM = Decimal(100)


def dinheiro(v):
    return str(v.quantize(CENTAVO)) if v is not None else None


def br(v):
    """Texto para pessoas: 1234.5 → 1.234,50."""
    return f"{v.quantize(CENTAVO):,}".replace(",", "_").replace(".", ",").replace("_", ".")


def decimal(valor, campo):
    """Aceita 1234.56, 1234,56 ou 1.234,56 (pt-BR). Nunca float."""
    s = str(valor if valor is not None else "").strip().replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise exc.WrongArguments({campo: ["Número inválido. Use 1234.56 ou 1234,56."]})
    if not d.is_finite():
        raise exc.WrongArguments({campo: ["Número inválido."]})
    return d


def periodo(valor, campo="periodo"):
    """AAAA-MM ou AAAA-MM-DD → 1º dia do mês."""
    try:
        ano, mes = map(int, str(valor or "")[:7].split("-"))
        return datetime.date(ano, mes, 1)
    except (ValueError, TypeError):
        raise exc.WrongArguments({campo: ["Use o mês no formato AAAA-MM."]})


def converter(valor, moeda, taxa, destino):
    """(valor convertido, None) ou (None, motivo). Só converte com taxa do par certo."""
    if moeda == destino:
        return valor, None
    if taxa is None:
        return None, f"sem taxa registrada de {moeda} para {destino}"
    if (taxa.moeda_origem, taxa.moeda_destino) != (moeda, destino):
        return None, f"a taxa informada é {taxa.moeda_origem}→{taxa.moeda_destino}, não {moeda}→{destino}"
    return valor * taxa.taxa, None


def _taxa(t):
    return {"taxa": str(t.taxa), "data": t.data, "origem": t.origem, "par": f"{t.moeda_origem}→{t.moeda_destino}"} if t else None


def totais(estimativa):
    grupos, itens, pendentes = {}, [], []
    todos = list(estimativa.itens.select_related("taxa_cambio"))
    for it in todos:
        g = grupos.setdefault((it.tipo, it.recorrencia), {"fixo": Decimal(0), "variavel": Decimal(0), "ajustes": Decimal(0)})
        if it.natureza == ItemEstimativa.AJUSTE:
            continue
        bruto = it.quantidade * it.preco_unitario
        valor, motivo = converter(bruto, it.moeda, it.taxa_cambio, estimativa.moeda)
        if motivo:
            pendentes.append({"item": it.id, "motivo": motivo})
        else:
            g[it.natureza] += valor
        itens.append({"id": it.id, "valor_original": str(bruto), "moeda_original": it.moeda, "valor": str(valor) if valor is not None else None,
                      "conversao": _taxa(it.taxa_cambio) if it.moeda != estimativa.moeda else None})
    for it in todos:  # ajustes depois: incidem só sobre fixo + variável do mesmo grupo
        if it.natureza == ItemEstimativa.AJUSTE:
            g = grupos[(it.tipo, it.recorrencia)]
            valor = (g["fixo"] + g["variavel"]) * (it.percentual or 0) / CEM
            g["ajustes"] += valor
            itens.append({"id": it.id, "valor": str(valor), "percentual": str(it.percentual), "base": "fixo + variável do grupo"})
    saida = []
    for (tipo, rec), g in sorted(grupos.items()):
        base = g["fixo"] + g["variavel"]
        saida.append({"tipo": tipo, "recorrencia": rec, "fixo": dinheiro(g["fixo"]), "variavel": dinheiro(g["variavel"]),
                      "antes_de_ajustes": dinheiro(base), "ajustes": dinheiro(g["ajustes"]), "total": dinheiro(base + g["ajustes"])})
    return {"moeda": estimativa.moeda, "grupos": saida, "itens": itens, "pendentes": pendentes}


def realizado_do_cliente(cliente, mes, moeda):
    """Diretos + parte do rateio do mês. Moeda diferente sem taxa fica fora e aparece em pendentes."""
    total, pendentes, parcial, linhas = Decimal(0), [], False, []

    def somar(c, fracao, motivo_linha):
        nonlocal total, parcial
        valor, motivo = converter(c.valor * fracao, c.moeda, c.taxa_cambio, moeda)
        parcial = parcial or c.parcial
        if motivo:
            pendentes.append({"custo": c.id, "motivo": motivo})
            return
        total += valor
        linhas.append({"custo": c.id, "categoria": c.categoria, "valor": dinheiro(valor), "como": motivo_linha, "parcial": c.parcial})

    for c in CustoRealizado.objects.filter(cliente=cliente, periodo=mes).select_related("taxa_cambio"):
        somar(c, Decimal(1), "direto")
    for regra in RegraRateio.objects.filter(periodo=mes):
        pct = regra.partes.get(str(cliente.id))
        if pct:
            for c in CustoRealizado.objects.filter(cliente__isnull=True, periodo=mes, categoria=regra.categoria).select_related("taxa_cambio"):
                somar(c, Decimal(str(pct)) / CEM, f"rateio {pct}% de {regra.categoria}")
    return total, parcial, pendentes, linhas


def comparar(orcamento):
    """Diferença absoluta e percentual. Orçamento zero: sem divisão; qualquer gasto já é desvio."""
    real, parcial, pendentes, linhas = realizado_do_cliente(orcamento.cliente, orcamento.periodo, orcamento.moeda)
    diferenca = real - orcamento.valor
    percentual = None if orcamento.valor == 0 else diferenca / orcamento.valor * CEM
    alertas = []
    if orcamento.valor == 0 and real > 0:
        alertas.append({"codigo": "orcamento_zero", "texto": "Orçamento zero com gasto realizado: percentual não se aplica."})
    elif real > orcamento.valor:
        alertas.append({"codigo": "acima_do_orcamento", "texto": f"Acima do orçamento em {br(diferenca)} {orcamento.moeda}."})
    if percentual is not None and percentual > orcamento.alerta_percentual:
        alertas.append({"codigo": "desvio_percentual", "texto": f"Desvio de {br(percentual)}% (limite {br(orcamento.alerta_percentual)}%)."})
    return {"periodo": orcamento.periodo, "moeda": orcamento.moeda, "orcamento": dinheiro(orcamento.valor), "realizado": dinheiro(real),
            "diferenca": dinheiro(diferenca), "percentual": dinheiro(percentual), "alertas": alertas, "pendentes": pendentes, "linhas": linhas,
            "parcial": parcial, "aviso_parcial": "Inclui consumo parcial do mês: não é fatura final." if parcial else None,
            "corte_automatico": False}  # a Vetor só alerta; não desliga infraestrutura


def nao_alocados(mes):
    cobertas = set(RegraRateio.objects.filter(periodo=mes).values_list("categoria", flat=True))
    return CustoRealizado.objects.filter(cliente__isnull=True, periodo=mes).exclude(categoria__in=cobertas)


def validar_partes(partes):
    if not isinstance(partes, dict) or not partes:
        raise exc.WrongArguments({"partes": ["Informe {id do cliente: percentual}."]})
    soma = Decimal(0)
    for cid, pct in partes.items():
        if not str(cid).isdigit() or not Cliente.objects.filter(pk=int(cid)).exists():
            raise exc.WrongArguments({"partes": [f"Cliente {cid} não encontrado."]})
        p = decimal(pct, "partes")
        if p <= 0:
            raise exc.WrongArguments({"partes": ["Percentuais precisam ser maiores que zero."]})
        soma += p
    if soma != CEM:
        raise exc.WrongArguments({"partes": [f"Os percentuais somam {soma}; precisam somar 100."]})
    return {str(c): str(decimal(p, "partes")) for c, p in partes.items()}


COLUNAS = ["id", "periodo", "categoria", "descricao", "valor", "moeda", "cliente", "parcial"]


def ler_csv(arquivo):
    """Valida o arquivo inteiro antes de gravar qualquer linha (tudo ou nada)."""
    try:
        texto = arquivo.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise exc.WrongArguments({"arquivo": ["Use CSV em UTF-8."]})
    leitor = csv.DictReader(io.StringIO(texto), delimiter=";" if texto.split("\n", 1)[0].count(";") > texto.split("\n", 1)[0].count(",") else ",")
    faltam = set(COLUNAS) - set(leitor.fieldnames or [])
    if faltam - {"descricao", "cliente", "parcial"}:
        raise exc.WrongArguments({"arquivo": [f"Colunas obrigatórias ausentes: {', '.join(sorted(faltam))}. Use: {';'.join(COLUNAS)}."]})
    linhas, erros, vistos = [], {}, set()
    for n, l in enumerate(leitor, start=2):
        try:
            if not (l.get("id") or "").strip() or l["id"].strip() in vistos:
                raise exc.WrongArguments({"id": ["id vazio ou repetido no arquivo."]})
            vistos.add(l["id"].strip())
            cliente = (l.get("cliente") or "").strip()
            if cliente and not (cliente.isdigit() and Cliente.objects.filter(pk=int(cliente)).exists()):
                raise exc.WrongArguments({"cliente": [f"Cliente {cliente} não encontrado (deixe vazio para não alocado)."]})
            linhas.append({"id_externo": l["id"].strip()[:120], "periodo": periodo(l["periodo"]), "categoria": (l["categoria"] or "").strip()[:80] or "sem categoria",
                           "descricao": (l.get("descricao") or "").strip()[:300], "valor": decimal(l["valor"], "valor"),
                           "moeda": (l["moeda"] or "BRL").strip().upper()[:3], "cliente_id": int(cliente) if cliente else None,
                           "parcial": (l.get("parcial") or "").strip().lower() in ("sim", "s", "true", "1", "parcial")})
        except exc.WrongArguments as e:
            erros[f"linha {n}"] = e.detail
    if erros:
        raise exc.WrongArguments({"linhas": erros})
    if not linhas:
        raise exc.WrongArguments({"arquivo": ["Arquivo sem linhas."]})
    return linhas

