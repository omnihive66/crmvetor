"""API de custos (SPEC-09). Uma trava só: toda rota daqui é do usuário matriz (VETOR_FINANCEIRO_USUARIOS), inclusive exportação."""
import csv
import io

from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.utils.dateparse import parse_date

from taiga.base import exceptions as exc
from taiga.base import response
from taiga.base.api import serializers
from taiga.base.decorators import detail_route, list_route
from taiga.base.fields import Field, MethodField

from . import clientes as regras
from . import custos, permissoes
from .api_clientes import BaseVetor, _autenticado, _texto
from .auditoria import registrar
from .models import CustoRealizado, Estimativa, ItemEstimativa, Orcamento, RegraRateio, TaxaCambio




class Texto(Field):
    """Decimal sai como texto: nada de float no caminho."""
    def to_value(self, value):
        return None if value is None else str(value)


class BaseCustos(BaseVetor):
    paginate_by = 100

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _autenticado(request)
        if not permissoes.financeiro(request.user):  # consulta e alteração: só o usuário matriz
            raise exc.PermissionDenied("O financeiro é restrito ao usuário matriz.")

    def cliente(self, cid):
        c = regras.clientes_visiveis(self.request.user).filter(pk=cid).first() if str(cid or "").isdigit() else None
        if c is None:
            raise exc.WrongArguments({"cliente": ["Cliente não encontrado."]})
        return c


def _moeda(data, campo="moeda", padrao="BRL"):
    m = str(data.get(campo) or padrao).strip().upper()
    if len(m) != 3 or not m.isalpha():
        raise exc.WrongArguments({campo: ["Use o código ISO de 3 letras (BRL, USD, EUR)."]})
    return m


def _taxa(data, campo="taxa_cambio"):
    if not data.get(campo):
        return None
    t = TaxaCambio.objects.filter(pk=data.get(campo)).first()
    if t is None:
        raise exc.WrongArguments({campo: ["Taxa de câmbio não encontrada."]})
    return t


# Taxas de câmbio ------------------------------------------------------------------------------

class TaxaSerializer(serializers.LightSerializer):
    id = Field()
    moeda_origem = Field()
    moeda_destino = Field()
    taxa = Texto()
    data = Field()
    origem = Field()


class TaxaViewSet(BaseCustos):
    serializer_class = TaxaSerializer
    queryset = TaxaCambio.objects.all()

    def get_queryset(self):
        return TaxaCambio.objects.all()

    def create(self, request, **kwargs):
        taxa = custos.decimal(request.DATA.get("taxa"), "taxa")
        quando = parse_date(str(request.DATA.get("data") or ""))
        if taxa <= 0 or quando is None:
            raise exc.WrongArguments({"taxa": ["Informe taxa maior que zero e a data (AAAA-MM-DD)."]})
        t = TaxaCambio.objects.create(moeda_origem=_moeda(request.DATA, "moeda_origem"), moeda_destino=_moeda(request.DATA, "moeda_destino"),
                                      taxa=taxa, data=quando, origem=_texto(request.DATA, "origem", 200, obrigatorio=True))
        registrar("taxa_cambio.criada", t, par=f"{t.moeda_origem}->{t.moeda_destino}", data=str(t.data))
        return response.Created(self.get_serializer(t).data)


# Estimativas ----------------------------------------------------------------------------------

class ItemSerializer(serializers.LightSerializer):
    id = Field()
    tipo = Field()
    natureza = Field()
    recorrencia = Field()
    categoria = Field()
    descricao = Field()
    quantidade = Texto()
    unidade = Field()
    preco_unitario = Texto()
    moeda = Field()
    taxa_cambio = Field(attr="taxa_cambio_id")
    percentual = Texto()


class EstimativaSerializer(serializers.LightSerializer):
    id = Field()
    cliente = Field(attr="cliente_id")
    nome = Field()
    versao = Field()
    anterior = Field(attr="anterior_id")
    moeda = Field()
    validade = Field()
    fonte = Field()
    premissas = Field()
    criado_em = Field()
    editavel = MethodField()

    def get_editavel(self, obj):
        return not Estimativa.objects.filter(anterior=obj).exists()


CAMPOS_ITEM = {"tipo": (ItemEstimativa.CUSTO, ItemEstimativa.PRECO), "natureza": (ItemEstimativa.FIXO, ItemEstimativa.VARIAVEL, ItemEstimativa.AJUSTE),
               "recorrencia": (ItemEstimativa.UNICO, ItemEstimativa.MENSAL)}


def _validar_item(data, atual=None):
    dados = {}
    for campo, opcoes in CAMPOS_ITEM.items():
        if campo in data or atual is None:
            v = data.get(campo, getattr(ItemEstimativa, campo).field.default)
            if v not in opcoes:
                raise exc.WrongArguments({campo: [f"Use {', '.join(opcoes)}."]})
            dados[campo] = v
    if "categoria" in data or atual is None:
        dados["categoria"] = _texto(data, "categoria", 80, obrigatorio=True)
    for campo, n in (("descricao", 300), ("unidade", 30)):
        if campo in data:
            dados[campo] = _texto(data, campo, n)
    for campo in ("quantidade", "preco_unitario"):
        if campo in data:
            dados[campo] = custos.decimal(data[campo], campo)
            if dados[campo] < 0:
                raise exc.WrongArguments({campo: ["Não pode ser negativo (desconto é uma linha de ajuste)."]})
    if "moeda" in data:
        dados["moeda"] = _moeda(data)
    if "taxa_cambio" in data:
        dados["taxa_cambio"] = _taxa(data)
    natureza = dados.get("natureza", atual.natureza if atual else None)
    if "percentual" in data:
        dados["percentual"] = custos.decimal(data["percentual"], "percentual") if data["percentual"] not in (None, "") else None
    percentual = dados.get("percentual", atual.percentual if atual else None)
    if natureza == ItemEstimativa.AJUSTE and percentual is None:
        raise exc.WrongArguments({"percentual": ["Ajuste é um percentual sobre a base do grupo (negativo = desconto)."]})
    if natureza != ItemEstimativa.AJUSTE:
        dados["percentual"] = None
    return dados


class EstimativaViewSet(BaseCustos):
    serializer_class = EstimativaSerializer

    def get_queryset(self):
        qs = Estimativa.objects.filter(cliente__in=regras.clientes_visiveis(self.request.user))
        cid = self.request.QUERY_PARAMS.get("cliente")
        return qs.filter(cliente_id=cid) if str(cid or "").isdigit() else qs

    def _ultima(self, est):
        if Estimativa.objects.filter(anterior=est).exists():
            raise exc.WrongArguments({"versao": [f"A versão {est.versao} já foi substituída; edite a mais nova."]})

    def retrieve(self, request, pk=None, **kwargs):
        est = self.objeto(pk)
        return response.Ok({**self.get_serializer(est).data, "itens": ItemSerializer(est.itens.all(), many=True).data, "totais": custos.totais(est)})

    def _cabecalho(self, data):
        dados = {k: _texto(data, k, n) for k, n in (("fonte", 300), ("premissas", 20000)) if k in data}
        if "nome" in data:
            dados["nome"] = _texto(data, "nome", 200, obrigatorio=True)
        if "moeda" in data:
            dados["moeda"] = _moeda(data)
        if "validade" in data:
            dados["validade"] = parse_date(str(data["validade"])) if data["validade"] else None
        return dados

    def create(self, request, **kwargs):
        est = Estimativa.objects.create(cliente=self.cliente(request.DATA.get("cliente")), criado_por=request.user,
                                        **{"nome": _texto(request.DATA, "nome", 200, obrigatorio=True), **self._cabecalho(request.DATA)})
        registrar("estimativa.criada", est, cliente=est.cliente_id, versao=est.versao)
        return response.Created(self.get_serializer(est).data)

    def partial_update(self, request, pk=None, **kwargs):
        est = self.objeto(pk)
        self._ultima(est)
        dados = self._cabecalho(request.DATA)
        Estimativa.objects.filter(pk=est.pk).update(**dados)
        registrar("estimativa.alterada", est, campos=sorted(dados))
        return response.Ok(self.get_serializer(self.objeto(pk)).data)

    @detail_route(methods=["POST"])
    def nova_versao(self, request, pk=None):
        """Congela a versão atual e copia cabeçalho e itens para a próxima (o histórico fica consultável)."""
        with transaction.atomic():
            est = Estimativa.objects.select_for_update().get(pk=self.objeto(pk).pk)
            self._ultima(est)
            nova = Estimativa.objects.create(cliente=est.cliente, nome=est.nome, versao=est.versao + 1, anterior=est, moeda=est.moeda,
                                             validade=est.validade, fonte=est.fonte, premissas=est.premissas, criado_por=request.user)
            for it in est.itens.all():
                it.pk, it.estimativa = None, nova
                it.save()
        registrar("estimativa.nova_versao", nova, anterior=est.id, versao=nova.versao)
        return response.Created(self.get_serializer(nova).data)

    @detail_route(methods=["POST"])
    def itens(self, request, pk=None):
        est = self.objeto(pk)
        self._ultima(est)
        item = ItemEstimativa.objects.create(estimativa=est, ordem=est.itens.count(), **_validar_item(request.DATA))
        registrar("estimativa.item_criado", est, item=item.id)
        return response.Created(ItemSerializer(item).data)


class ItemViewSet(BaseCustos):
    serializer_class = ItemSerializer

    def get_queryset(self):
        return ItemEstimativa.objects.filter(estimativa__cliente__in=regras.clientes_visiveis(self.request.user)).select_related("estimativa")

    def _editavel(self, item):
        if Estimativa.objects.filter(anterior=item.estimativa).exists():
            raise exc.WrongArguments({"versao": ["Versão substituída: edite a mais nova."]})

    def partial_update(self, request, pk=None, **kwargs):
        item = self.objeto(pk)
        self._editavel(item)
        dados = _validar_item(request.DATA, item)
        for k, v in dados.items():
            setattr(item, k, v)
        item.save()
        registrar("estimativa.item_alterado", item.estimativa, item=item.id, campos=sorted(k for k in request.DATA if k in dados))  # sem valores
        return response.Ok(ItemSerializer(item).data)

    def destroy(self, request, pk=None, **kwargs):
        item = self.objeto(pk)
        self._editavel(item)
        registrar("estimativa.item_removido", item.estimativa, item=item.id, categoria=item.categoria)
        item.delete()
        return response.NoContent()


# Realizado ------------------------------------------------------------------------------------

class CustoSerializer(serializers.LightSerializer):
    id = Field()
    cliente = Field(attr="cliente_id")
    periodo = Field()
    categoria = Field()
    descricao = Field()
    valor = Texto()
    moeda = Field()
    taxa_cambio = Field(attr="taxa_cambio_id")
    parcial = Field()
    origem = Field()
    lote = Field()
    id_externo = Field()


class CustoViewSet(BaseCustos):
    """?cliente=&periodo= ou ?nao_alocados=true&periodo= (custos sem cliente e sem regra de rateio no mês)."""
    serializer_class = CustoSerializer

    def get_queryset(self):
        p = self.request.QUERY_PARAMS
        if p.get("nao_alocados") == "true":
            return custos.nao_alocados(custos.periodo(p.get("periodo")))
        qs = CustoRealizado.objects.filter(cliente__in=regras.clientes_visiveis(self.request.user))
        if str(p.get("cliente") or "").isdigit():
            qs = qs.filter(cliente_id=p["cliente"])
        return qs.filter(periodo=custos.periodo(p["periodo"])) if p.get("periodo") else qs

    def _validar(self, data, atual=None):
        dados = {}
        if "cliente" in data:
            dados["cliente"] = self.cliente(data["cliente"]) if data["cliente"] else None  # vazio = não alocado
        if "periodo" in data or atual is None:
            dados["periodo"] = custos.periodo(data.get("periodo"))
        if "categoria" in data or atual is None:
            dados["categoria"] = _texto(data, "categoria", 80, obrigatorio=True)
        if "descricao" in data:
            dados["descricao"] = _texto(data, "descricao", 300)
        if "valor" in data or atual is None:
            dados["valor"] = custos.decimal(data.get("valor"), "valor")
        if "moeda" in data:
            dados["moeda"] = _moeda(data)
        if "taxa_cambio" in data:
            dados["taxa_cambio"] = _taxa(data)
        if "parcial" in data:
            dados["parcial"] = bool(data["parcial"])
        return dados

    def create(self, request, **kwargs):
        c = CustoRealizado.objects.create(criado_por=request.user, **self._validar(request.DATA))
        registrar("custo_realizado.criado", c, cliente=c.cliente_id, periodo=str(c.periodo))
        return response.Created(self.get_serializer(c).data)

    def partial_update(self, request, pk=None, **kwargs):
        c = self.objeto(pk)
        dados = self._validar(request.DATA, c)
        for k, v in dados.items():
            setattr(c, k, v)
        c.save()
        registrar("custo_realizado.alterado", c, campos=sorted(dados))  # auditado sem expor valores
        return response.Ok(self.get_serializer(c).data)

    def destroy(self, request, pk=None, **kwargs):
        c = self.objeto(pk)
        registrar("custo_realizado.removido", c, cliente=c.cliente_id, periodo=str(c.periodo), categoria=c.categoria, origem=c.origem)
        c.delete()
        return response.NoContent()

    def objeto(self, pk):  # não alocados também podem ser corrigidos (ex.: atribuir cliente)
        c = (CustoRealizado.objects.filter(pk=pk, cliente__isnull=True).first()
             or CustoRealizado.objects.filter(pk=pk, cliente__in=regras.clientes_visiveis(self.request.user)).first())
        if c is None:
            raise exc.NotFound()
        return c

    @list_route(methods=["POST"])
    def importar(self, request, **kwargs):
        """CSV id;periodo;categoria;descricao;valor;moeda;cliente;parcial. Mesmo lote + id não duplica."""
        lote = _texto(request.DATA, "lote", 80, obrigatorio=True)
        arquivo = request.FILES.get("arquivo")
        if arquivo is None:
            raise exc.WrongArguments({"arquivo": ["Envie o arquivo CSV."]})
        linhas = custos.ler_csv(arquivo)
        existentes = set(CustoRealizado.objects.filter(lote=lote, id_externo__in=[l["id_externo"] for l in linhas]).values_list("id_externo", flat=True))
        novos = [CustoRealizado(lote=lote, origem=CustoRealizado.IMPORTACAO, criado_por=request.user, **l) for l in linhas if l["id_externo"] not in existentes]
        try:
            with transaction.atomic():
                CustoRealizado.objects.bulk_create(novos)
        except IntegrityError:  # importação simultânea do mesmo lote
            raise exc.WrongArguments({"lote": ["Este lote está sendo importado agora; tente de novo."]})
        resumo = {"lote": lote, "importados": len(novos), "ja_existiam": len(existentes), "nao_alocados": sum(1 for n in novos if n.cliente_id is None)}
        registrar("custos.importados", CustoRealizado(pk=0), **resumo)
        return response.Ok(resumo)

    @list_route(methods=["GET"])
    def exportar(self, request, **kwargs):
        qs = self.get_queryset()
        saida = io.StringIO()
        w = csv.writer(saida, delimiter=";")
        w.writerow(["id", "cliente", "periodo", "categoria", "descricao", "valor", "moeda", "parcial", "origem", "lote"])
        for c in qs:
            w.writerow([c.id, c.cliente_id or "", c.periodo.strftime("%Y-%m"), c.categoria, c.descricao, c.valor, c.moeda, "sim" if c.parcial else "não", c.origem, c.lote])
        registrar("custos.exportados", CustoRealizado(pk=0), linhas=qs.count())
        resp = HttpResponse(saida.getvalue(), content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="custos-realizados.csv"'
        return resp


# Rateio e orçamento ---------------------------------------------------------------------------

class RateioSerializer(serializers.LightSerializer):
    id = Field()
    periodo = Field()
    categoria = Field()
    partes = Field()


class RateioViewSet(BaseCustos):
    serializer_class = RateioSerializer

    def get_queryset(self):
        p = self.request.QUERY_PARAMS.get("periodo")
        return RegraRateio.objects.filter(periodo=custos.periodo(p)) if p else RegraRateio.objects.all()

    def create(self, request, **kwargs):
        """Cria ou substitui a regra da categoria no mês."""
        mes, categoria = custos.periodo(request.DATA.get("periodo")), _texto(request.DATA, "categoria", 80, obrigatorio=True)
        regra, criada = RegraRateio.objects.update_or_create(periodo=mes, categoria=categoria,
                                                            defaults={"partes": custos.validar_partes(request.DATA.get("partes")), "criado_por": request.user})
        registrar("rateio.definido" if criada else "rateio.alterado", regra, periodo=str(mes), categoria=categoria, clientes=sorted(regra.partes))
        return response.Created(self.get_serializer(regra).data)

    def destroy(self, request, pk=None, **kwargs):
        regra = self.objeto(pk)
        registrar("rateio.removido", regra, periodo=str(regra.periodo), categoria=regra.categoria)
        regra.delete()
        return response.NoContent()


class OrcamentoSerializer(serializers.LightSerializer):
    id = Field()
    cliente = Field(attr="cliente_id")
    periodo = Field()
    valor = Texto()
    moeda = Field()
    alerta_percentual = Texto()
    origem = Field()


class OrcamentoViewSet(BaseCustos):
    serializer_class = OrcamentoSerializer

    def get_queryset(self):
        qs = Orcamento.objects.filter(cliente__in=regras.clientes_visiveis(self.request.user)).select_related("cliente")
        cid = self.request.QUERY_PARAMS.get("cliente")
        return qs.filter(cliente_id=cid) if str(cid or "").isdigit() else qs

    def create(self, request, **kwargs):
        """Cria ou substitui o orçamento do cliente no mês."""
        cliente, mes = self.cliente(request.DATA.get("cliente")), custos.periodo(request.DATA.get("periodo"))
        valor = custos.decimal(request.DATA.get("valor"), "valor")
        if valor < 0:
            raise exc.WrongArguments({"valor": ["Orçamento não pode ser negativo."]})
        dados = {"valor": valor, "moeda": _moeda(request.DATA), "origem": _texto(request.DATA, "origem", 300)}
        if "alerta_percentual" in request.DATA:
            dados["alerta_percentual"] = custos.decimal(request.DATA["alerta_percentual"], "alerta_percentual")
        orc, criado = Orcamento.objects.update_or_create(cliente=cliente, periodo=mes, defaults=dados)
        registrar("orcamento.definido" if criado else "orcamento.alterado", orc, cliente=cliente.id, periodo=str(mes))
        return response.Created(self.get_serializer(orc).data)

    def destroy(self, request, pk=None, **kwargs):
        orc = self.objeto(pk)
        registrar("orcamento.removido", orc, cliente=orc.cliente_id, periodo=str(orc.periodo))
        orc.delete()
        return response.NoContent()

    @detail_route(methods=["GET"])
    def comparacao(self, request, pk=None):
        return response.Ok(custos.comparar(self.objeto(pk)))
