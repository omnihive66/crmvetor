"""Minhas demandas: lembretes privados, tokens pessoais do agente e as rotas do agente (SPEC-05)."""
import datetime
import hashlib
import logging
import secrets

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt

from taiga.base import exceptions as exc
from taiga.base import response
from taiga.base.api import serializers
from taiga.base.api.authentication import BaseAuthentication
from taiga.base.api.views import APIView
from taiga.base.decorators import detail_route, list_route
from taiga.base.fields import Field, MethodField
from taiga.permissions.services import user_has_perm
from taiga.projects.history.services import take_snapshot
from taiga.projects.userstories.models import UserStory

from . import clientes as regras
from . import lembretes
from .api_clientes import BaseVetor, _autenticado, _texto
from .ator import ATOR
from .models import Lembrete, RequisicaoAgente, TokenAgente

log = logging.getLogger("vetor.agente")


# Lembretes ----------------------------------------------------------------------------------

class LembreteSerializer(serializers.LightSerializer):
    id = Field()
    titulo = Field()
    notas = Field()
    vencimento = Field()
    recorrencia = Field()
    avisar_email = Field()
    estado = Field()
    vencido = MethodField()
    notificado_em = Field()
    visto_em = Field()
    referencias = MethodField()
    criado_em = Field()

    def get_vencido(self, obj):
        return bool(obj.vencimento and obj.vencimento <= timezone.now() and obj.estado == Lembrete.ABERTO)

    def get_referencias(self, obj):
        return lembretes.referencias(obj, self.context["request"].user)


def _validar_lembrete(user, data, atual=None):
    parcial = atual is not None
    dados = {}
    if "titulo" in data or not parcial:
        dados["titulo"] = _texto(data, "titulo", 200, obrigatorio=True)
    if "notas" in data:
        dados["notas"] = _texto(data, "notas", 20000)
    if "vencimento" in data:
        bruto = data.get("vencimento")
        quando = parse_datetime(bruto) if bruto else None
        if bruto and (quando is None or quando.tzinfo is None):
            raise exc.WrongArguments({"vencimento": ["Informe data e hora com fuso (ISO 8601)."]})
        dados["vencimento"] = quando
    if "recorrencia" in data:
        if data.get("recorrencia") not in dict(Lembrete.RECORRENCIAS):
            raise exc.WrongArguments({"recorrencia": ["Use diaria, semanal, mensal ou vazio."]})
        dados["recorrencia"] = data.get("recorrencia")
    if "avisar_email" in data:
        dados["avisar_email"] = bool(data.get("avisar_email"))
    if "estado" in data:
        if data.get("estado") not in dict(Lembrete.ESTADOS):
            raise exc.WrongArguments({"estado": ["Estado inválido."]})
        dados["estado"] = data.get("estado")
    dados.update(lembretes.validar_referencias(user, data))
    recorrencia = dados.get("recorrencia", atual.recorrencia if atual else "")
    if recorrencia and not dados.get("vencimento", atual.vencimento if atual else None):
        raise exc.WrongArguments({"recorrencia": ["Lembrete recorrente precisa de vencimento."]})
    return dados


class LembreteViewSet(BaseVetor):
    """Sempre e só os lembretes de quem pergunta: nem administrador nem superusuário veem os de outra pessoa."""
    serializer_class = LembreteSerializer
    paginate_by = 100

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Lembrete.objects.none()
        qs = Lembrete.objects.filter(dono=user).select_related("cliente", "projeto", "historia__project", "convertido_em__project")
        if self.action == "list":
            estado = self.request.QUERY_PARAMS.get("estado", Lembrete.ABERTO)
            qs = qs if estado == "todos" else qs.filter(estado=estado)
        return qs

    def retrieve(self, request, pk=None, **kwargs):
        _autenticado(request)
        return response.Ok(self.get_serializer(self.objeto(pk)).data)

    def create(self, request, **kwargs):
        _autenticado(request)
        lembrete = Lembrete.objects.create(dono=request.user, **_validar_lembrete(request.user, request.DATA))
        return response.Created(self.get_serializer(lembrete).data)

    def partial_update(self, request, pk=None, **kwargs):
        _autenticado(request)
        lembrete = self.objeto(pk)
        dados = _validar_lembrete(request.user, request.DATA, lembrete)
        if "vencimento" in dados and dados["vencimento"] != lembrete.vencimento:
            dados["notificado_em"] = dados["visto_em"] = None  # reagendado: avisa de novo no novo horário
        for k, v in dados.items():
            setattr(lembrete, k, v)
        lembrete.save()
        return response.Ok(self.get_serializer(lembrete).data)

    def destroy(self, request, pk=None, **kwargs):
        _autenticado(request)
        self.objeto(pk).delete()
        return response.NoContent()

    @list_route(methods=["GET"])
    def resumo(self, request, **kwargs):
        """Para o aviso interno na barra lateral: quantos venceram e ainda não foram vistos."""
        _autenticado(request)
        n = Lembrete.objects.filter(dono=request.user, estado=Lembrete.ABERTO, notificado_em__isnull=False, visto_em__isnull=True).count()
        return response.Ok({"avisos_nao_vistos": n})

    @list_route(methods=["POST"])
    def marcar_vistos(self, request, **kwargs):
        _autenticado(request)
        Lembrete.objects.filter(dono=request.user, notificado_em__isnull=False, visto_em__isnull=True).update(visto_em=timezone.now())
        return response.NoContent()

    @detail_route(methods=["GET"])
    def previa_conversao(self, request, pk=None):
        _autenticado(request)
        _, previa = lembretes.previa_conversao(self.objeto(pk), request.user, request.QUERY_PARAMS.get("projeto"),
                                               request.QUERY_PARAMS.get("copiar_notas") == "true")
        return response.Ok(previa)

    @detail_route(methods=["POST"])
    def converter(self, request, pk=None):
        _autenticado(request)
        if request.DATA.get("confirmar") is not True:
            raise exc.WrongArguments({"confirmar": ["Confirme depois de ver a prévia: a demanda fica visível para o projeto."]})
        us, criada = lembretes.converter(self.objeto(pk), request.user, request.DATA.get("projeto"), bool(request.DATA.get("copiar_notas")))
        corpo = {"id": us.id, "ref": us.ref, "projeto": us.project.slug, "criada": criada}
        return response.Created(corpo) if criada else response.Ok(corpo)


# Tokens do agente (cada pessoa gerencia os próprios) ---------------------------------------

ESCOPOS = (TokenAgente.LEMBRETES, TokenAgente.DEMANDAS)


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class TokenAgenteSerializer(serializers.LightSerializer):
    id = Field()
    nome = Field()
    prefixo = Field()
    escopos = Field()
    criado_em = Field()
    usado_em = Field()
    revogado_em = Field()


class TokenAgenteViewSet(BaseVetor):
    serializer_class = TokenAgenteSerializer

    def get_queryset(self):
        user = self.request.user
        return TokenAgente.objects.filter(dono=user).order_by("-criado_em") if user.is_authenticated else TokenAgente.objects.none()

    def create(self, request, **kwargs):
        _autenticado(request)
        escopos = request.DATA.get("escopos") or []
        if not escopos or not isinstance(escopos, list) or set(escopos) - set(ESCOPOS):
            raise exc.WrongArguments({"escopos": [f"Escolha um ou mais: {', '.join(ESCOPOS)}."]})
        token = "vtag_" + secrets.token_urlsafe(32)
        obj = TokenAgente.objects.create(dono=request.user, nome=_texto(request.DATA, "nome", 80, obrigatorio=True),
                                         prefixo=token[:12], hash=_hash(token), escopos=sorted(set(escopos)))
        # O token aparece só nesta resposta; depois, só o prefixo.
        return response.Created({**self.get_serializer(obj).data, "token": token})

    def destroy(self, request, pk=None, **kwargs):
        _autenticado(request)
        obj = self.objeto(pk)
        if not obj.revogado_em:
            obj.revogado_em = timezone.now()
            obj.save(update_fields=["revogado_em"])
        return response.NoContent()


# Rotas do agente ------------------------------------------------------------------------------

class TokenAgenteAuth(BaseAuthentication):
    """Authorization: Agente <token>. Só nas rotas /vetor/agente (o resto da API não aceita este token)."""
    def authenticate(self, request):
        cabecalho = request.META.get("HTTP_AUTHORIZATION", "")
        if not cabecalho.startswith("Agente "):
            return None
        token = TokenAgente.objects.select_related("dono").filter(hash=_hash(cabecalho[7:].strip()), revogado_em__isnull=True).first()
        if token is None or not token.dono.is_active:
            raise exc.NotAuthenticated("Token de agente inválido, revogado ou de conta inativa.")
        TokenAgente.objects.filter(pk=token.pk).update(usado_em=timezone.now())
        ATOR.set(token.dono)
        return token.dono, token

    def authenticate_header(self, request):
        return 'Agente realm="api"'


class AgenteView(APIView):
    authentication_classes = (TokenAgenteAuth,)
    permission_classes = ()
    escopo = None

    def post(self, request, *args, **kwargs):
        token = request.auth
        if not isinstance(token, TokenAgente):
            raise exc.NotAuthenticated("Use Authorization: Agente <token>.")
        if self.escopo not in token.escopos:
            raise exc.PermissionDenied(f"Este token não tem o escopo “{self.escopo}”.")
        chave = (request.META.get("HTTP_IDEMPOTENCY_KEY") or "").strip()
        if not chave or len(chave) > 100:
            raise exc.WrongArguments({"Idempotency-Key": ["Envie o cabeçalho Idempotency-Key (até 100 caracteres) para repetir com segurança."]})
        anterior = RequisicaoAgente.objects.filter(token=token, chave=chave).first()
        if anterior:
            return response.Response(anterior.resposta, status=anterior.status)
        # shortcut: só conta chamadas que criaram algo (erros e esclarecimentos não), trocar por cache se houver abuso.
        recentes = RequisicaoAgente.objects.filter(token=token, criado_em__gte=timezone.now() - datetime.timedelta(minutes=1)).count()
        if recentes >= settings.VETOR_AGENTE_LIMITE_MINUTO:
            raise exc.Throttled(60)
        esclarecer, status_code, corpo = self.executar(request.user, request.DATA)
        if esclarecer:
            return response.Response({"esclarecimento": esclarecer}, status=422)  # nada criado, nada guardado
        try:
            with transaction.atomic():
                RequisicaoAgente.objects.create(token=token, chave=chave, status=status_code, resposta=corpo)
        except IntegrityError:  # duas chamadas iguais ao mesmo tempo: vale a primeira
            anterior = RequisicaoAgente.objects.get(token=token, chave=chave)
            return response.Response(anterior.resposta, status=anterior.status)
        log.info("agente token=%s escopo=%s status=%s", token.prefixo, self.escopo, status_code)  # sem conteúdo
        return response.Response(corpo, status=status_code)

    @csrf_exempt  # autentica só por cabeçalho, nunca por cookie
    def dispatch(self, request, *args, **kwargs):
        # A transação cobre criar o objeto e registrar a chave: ou os dois, ou nenhum.
        with transaction.atomic():
            resp = super().dispatch(request, *args, **kwargs)
            if resp.status_code >= 400:
                transaction.set_rollback(True)
            return resp


def _resolver(qs, valor, campo_nome, rotulo):
    """Acha um único objeto pelo id ou pelo nome; nunca escolhe sozinho entre vários nem inventa."""
    if valor in (None, ""):
        return None, None
    if isinstance(valor, int) or str(valor).isdigit():
        obj = qs.filter(pk=int(valor)).first()
        return (obj, None) if obj else (None, {"campo": rotulo, "motivo": "nao_encontrado", "valor": valor})
    exatos = qs.filter(**{f"{campo_nome}__iexact": valor})
    candidatos = exatos if exatos.count() == 1 else qs.filter(**{f"{campo_nome}__icontains": valor})
    if candidatos.count() == 1:
        return candidatos.first(), None
    if not candidatos.exists():
        return None, {"campo": rotulo, "motivo": "nao_encontrado", "valor": valor}
    return None, {"campo": rotulo, "motivo": "ambiguo", "valor": valor,
                  "opcoes": [{"id": o.pk, "nome": getattr(o, campo_nome)} for o in candidatos[:10]]}


class AgenteLembretesView(AgenteView):
    """Cria lembrete privado do dono do token. O dono nunca vem do corpo da requisição."""
    escopo = TokenAgente.LEMBRETES

    def executar(self, user, data):
        if "dono" in data or "owner_id" in data:
            raise exc.WrongArguments({"dono": ["O dono é sempre o titular do token."]})
        cliente, duvida = _resolver(regras.clientes_visiveis(user), data.get("cliente"), "nome", "cliente")
        if duvida:
            return duvida, None, None
        projeto, duvida = _resolver(regras.projetos_visiveis(user).distinct(), data.get("projeto"), "name", "projeto")
        if duvida:
            return duvida, None, None
        dados = _validar_lembrete(user, {k: data[k] for k in ("titulo", "notas", "vencimento", "recorrencia", "avisar_email") if k in data})
        lembrete = Lembrete.objects.create(dono=user, cliente=cliente, projeto=projeto, **dados)
        return None, 201, {"id": lembrete.id, "tipo": "lembrete", "privado": True}


class AgenteDemandasView(AgenteView):
    """Cria demanda compartilhada num projeto; exige o escopo "demandas" e permissão add_us do titular."""
    escopo = TokenAgente.DEMANDAS

    def executar(self, user, data):
        projeto, duvida = _resolver(regras.projetos_visiveis(user).distinct(), data.get("projeto"), "name", "projeto")
        if duvida:
            return duvida, None, None
        if projeto is None:
            return {"campo": "projeto", "motivo": "obrigatorio"}, None, None
        if not user_has_perm(user, "add_us", projeto):
            raise exc.PermissionDenied("O titular do token não pode criar demandas neste projeto.")
        us = UserStory.objects.create(project=projeto, owner=user, subject=_texto(data, "assunto", 500, obrigatorio=True),
                                      description=_texto(data, "descricao", 20000), status=projeto.default_us_status)
        take_snapshot(us, user=user)
        return None, 201, {"id": us.id, "ref": us.ref, "projeto": projeto.slug, "tipo": "demanda", "privado": False}
