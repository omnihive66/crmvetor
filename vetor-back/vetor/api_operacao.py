"""Produtos com telemetria de uso e a rota de ingestão (SPEC-08)."""
import hashlib
import secrets

from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt

from taiga.base import exceptions as exc
from taiga.base import response
from taiga.base.api import serializers
from taiga.base.api.authentication import BaseAuthentication
from taiga.base.api.views import APIView
from taiga.base.fields import Field

from . import clientes as regras
from . import operacao, permissoes
from .api_clientes import BaseVetor, _autenticado, _texto
from .auditoria import registrar
from .models import Cliente, ProdutoTelemetria


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class ProdutoSerializer(serializers.LightSerializer):
    id = Field()
    cliente = Field(attr="cliente_id")
    nome = Field()
    chave = Field()
    prefixo = Field()
    sintetico = Field()
    janela_ativos_dias = Field()
    alerta_desuso_dias = Field()
    alerta_excecao_ate = Field()
    alerta_excecao_motivo = Field()
    revogado_em = Field()
    criado_em = Field()


def _ajustes(data):
    """Janela e alerta de desuso: ajustáveis por contrato/contexto."""
    dados = {}
    if "janela_ativos_dias" in data:
        n = data.get("janela_ativos_dias")
        if not isinstance(n, int) or not 1 <= n <= 365:
            raise exc.WrongArguments({"janela_ativos_dias": ["De 1 a 365 dias."]})
        dados["janela_ativos_dias"] = n
    if "alerta_desuso_dias" in data:
        n = data.get("alerta_desuso_dias")
        if n is not None and (not isinstance(n, int) or not 1 <= n <= 365):
            raise exc.WrongArguments({"alerta_desuso_dias": ["De 1 a 365 dias, ou vazio para desligar."]})
        dados["alerta_desuso_dias"] = n
    if "alerta_excecao_ate" in data:
        bruto = data.get("alerta_excecao_ate")
        try:
            dados["alerta_excecao_ate"] = parse_date(bruto) if bruto else None
        except ValueError:
            dados["alerta_excecao_ate"] = None
        if bruto and dados["alerta_excecao_ate"] is None:
            raise exc.WrongArguments({"alerta_excecao_ate": ["Use AAAA-MM-DD."]})
    if "alerta_excecao_motivo" in data:
        dados["alerta_excecao_motivo"] = _texto(data, "alerta_excecao_motivo", 200)
    return dados


class ProdutoViewSet(BaseVetor):
    """Ver e ajustar: quem edita o cliente. Emitir e revogar o token de ingestão: só o Administrador."""
    serializer_class = ProdutoSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return ProdutoTelemetria.objects.none()
        qs = ProdutoTelemetria.objects.filter(cliente__in=regras.clientes_visiveis(user))
        cliente = self.request.QUERY_PARAMS.get("cliente")
        return qs.filter(cliente_id=cliente) if str(cliente or "").isdigit() else qs

    def create(self, request, **kwargs):
        _autenticado(request)
        if not permissoes.e_administrador(request.user):
            raise exc.PermissionDenied("Só administradores emitem tokens de ingestão.")
        cliente = Cliente.objects.filter(pk=request.DATA.get("cliente")).first()
        if cliente is None:
            raise exc.WrongArguments({"cliente": ["Cliente não encontrado."]})
        chave = _texto(request.DATA, "chave", 60, obrigatorio=True)
        if cliente.produtos_telemetria.filter(chave=chave).exists():
            raise exc.WrongArguments({"chave": ["Este cliente já tem um produto com essa chave."]})
        token = "vtpr_" + secrets.token_urlsafe(32)
        produto = ProdutoTelemetria.objects.create(cliente=cliente, nome=_texto(request.DATA, "nome", 120, obrigatorio=True), chave=chave,
                                                   prefixo=token[:12], hash=_hash(token), sintetico=bool(request.DATA.get("sintetico")),
                                                   **_ajustes(request.DATA))
        registrar("produto_telemetria.criado", produto, cliente=cliente.id, sintetico=produto.sintetico)
        return response.Created({**self.get_serializer(produto).data, "token": token})  # o token aparece só aqui

    def partial_update(self, request, pk=None, **kwargs):
        _autenticado(request)
        produto = self.objeto(pk)
        regras.exigir_edicao(request.user, produto.cliente)
        dados = _ajustes(request.DATA)
        for k, v in dados.items():
            setattr(produto, k, v)
        produto.save()
        registrar("produto_telemetria.ajustado", produto, campos=sorted(dados))
        return response.Ok(self.get_serializer(produto).data)

    def destroy(self, request, pk=None, **kwargs):
        _autenticado(request)
        if not permissoes.e_administrador(request.user):
            raise exc.PermissionDenied("Só administradores revogam tokens de ingestão.")
        produto = self.objeto(pk)
        if not produto.revogado_em:
            produto.revogado_em = timezone.now()
            produto.save(update_fields=["revogado_em"])
            registrar("produto_telemetria.revogado", produto, cliente=produto.cliente_id)
        return response.NoContent()


class ProdutoAuth(BaseAuthentication):
    """Authorization: Produto <token>. Só na rota de ingestão; não autentica pessoa nenhuma."""
    def authenticate(self, request):
        cab = request.META.get("HTTP_AUTHORIZATION", "")
        if not cab.startswith("Produto "):
            return None
        produto = ProdutoTelemetria.objects.select_related("cliente").filter(hash=_hash(cab[8:].strip()), revogado_em__isnull=True).first()
        if produto is None:
            raise exc.NotAuthenticated("Token de produto inválido ou revogado.")
        return AnonymousUser(), produto

    def authenticate_header(self, request):
        return 'Produto realm="api"'


class IngestaoView(APIView):
    authentication_classes = (ProdutoAuth,)
    permission_classes = ()

    def post(self, request, *args, **kwargs):
        if not isinstance(request.auth, ProdutoTelemetria):
            raise exc.NotAuthenticated("Use Authorization: Produto <token>.")
        return response.Ok(operacao.ingerir(request.auth, request.DATA))

    @csrf_exempt  # autentica só por cabeçalho
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
