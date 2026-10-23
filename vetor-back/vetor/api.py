import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt

from taiga.base import exceptions as exc
from taiga.base import response
from taiga.base.api import GenericViewSet, serializers
from taiga.base.api.mixins import ListModelMixin
from taiga.base.decorators import list_route
from taiga.base.fields import Field, MethodField
from taiga.base.mails import mail_builder
from taiga.projects import api as projects_api
from taiga.users import api as users_api
from taiga.webhooks import api as webhooks_api

from . import permissoes
from .models import Auditoria, Perfil


class UsersViewSet(users_api.UsersViewSet):
    def password_recovery(self, request, pk=None):
        # Mesma resposta para conta existente ou não: não revela quem tem acesso (DESIGN.md, tela de login).
        try:
            return super().password_recovery(request, pk)
        except exc.WrongArguments:
            if not request.DATA.get("username"):
                raise
            return response.Ok({"detail": _("Mail sent successfully!")})


class TransacaoNaEscrita:
    """Escrita num só bloco, desfeito se a resposta for de erro.

    O ATOMIC_REQUESTS do Taiga está fora de DATABASES e não tem efeito, e o tratador de exceções
    devolve a resposta dentro da view. Sem isto, recusar a membership do dono no meio da criação
    de um projeto deixaria o projeto gravado sem dono, e um convite em lote ficaria pela metade."""
    @csrf_exempt  # como o APIView do Taiga: o as_view copia a isenção do dispatch (a API usa token, não cookie)
    def dispatch(self, request, *args, **kwargs):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return super().dispatch(request, *args, **kwargs)
        with transaction.atomic():
            response = super().dispatch(request, *args, **kwargs)
            if response.status_code >= 400:
                transaction.set_rollback(True)
            return response


class ProjectViewSet(TransacaoNaEscrita, projects_api.ProjectViewSet):
    pass


class MembershipViewSet(TransacaoNaEscrita, projects_api.MembershipViewSet):
    pass


class RolesViewSet(TransacaoNaEscrita, users_api.RolesViewSet):
    pass


class SomenteAdministrador:
    """Ação reservada ao papel Administrador da organização (matriz da SPEC-02)."""
    mensagem_negado = "Somente administradores da organização podem fazer isso."

    def check_permissions(self, request, action=None, obj=None):
        if not request.user.is_authenticated:
            raise exc.NotAuthenticated()
        if not permissoes.e_administrador(request.user):
            raise exc.PermissionDenied(self.mensagem_negado)
        return super().check_permissions(request, action, obj)

    def list(self, request, *args, **kwargs):
        # As listagens do Taiga não chamam check_permissions (só filtram o queryset).
        self.check_permissions(request, "list")
        return super().list(request, *args, **kwargs)


class _Integracoes(SomenteAdministrador):
    mensagem_negado = "Somente administradores da organização configuram integrações."


class WebhookViewSet(_Integracoes, webhooks_api.WebhookViewSet):
    pass


class WebhookLogViewSet(_Integracoes, webhooks_api.WebhookLogViewSet):
    pass


class ProjectModulesViewSet(_Integracoes, ProjectViewSet):
    """Só a rota projects/<id>/modules (segredos do GitHub/GitLab/Bitbucket/Gogs) passa por aqui."""


class PerfilSerializer(serializers.LightSerializer):
    id = Field()
    username = Field()
    full_name = Field()
    email = Field()
    is_active = Field()
    is_superuser = Field()
    papel = MethodField()
    ver_custos = MethodField()

    def get_papel(self, user):
        return permissoes.papel(user)

    def get_ver_custos(self, user):
        return permissoes.financeiro(user)  # só o usuário matriz (servidor), não é mais opção por pessoa


class PerfilViewSet(TransacaoNaEscrita, SomenteAdministrador, ListModelMixin, GenericViewSet):
    """Pessoas, papéis e acesso. Conta nova recebe e-mail para definir a própria senha (sem senha compartilhada)."""
    serializer_class = PerfilSerializer
    permission_classes = ()  # a regra é SomenteAdministrador; as classes padrão do Taiga não se aplicam
    paginate_by = 50

    def get_queryset(self):
        return (get_user_model().objects.filter(is_system=False).select_related("vetor_perfil")
                .order_by("full_name", "username"))

    @list_route(methods=["GET"])
    def me(self, request, **kwargs):
        user = request.user
        if not user.is_authenticated:
            raise exc.NotAuthenticated()
        return response.Ok({"papel": permissoes.papel(user), "ver_custos": self.serializer_class(user).data["ver_custos"],
                            "administrador": permissoes.e_administrador(user)})

    def create(self, request, **kwargs):
        self.check_permissions(request, "create")
        User = get_user_model()
        username = (request.DATA.get("username") or "").strip()
        email = (request.DATA.get("email") or "").strip().lower()
        full_name = (request.DATA.get("full_name") or "").strip()
        dados = _validar_perfil(request.DATA)
        erros = {}
        try:
            User._meta.get_field("username").run_validators(username)
        except ValidationError as e:
            erros["username"] = e.messages
        if not username:
            erros["username"] = ["Informe o usuário."]
        try:
            validate_email(email)
        except ValidationError:
            erros["email"] = ["Informe um e-mail válido."]
        if not full_name:
            erros["full_name"] = ["Informe o nome completo."]
        if User.objects.filter(username__iexact=username).exists():
            erros["username"] = ["Já existe uma conta com esse usuário."]
        if User.objects.filter(email__iexact=email).exists():
            erros["email"] = ["Já existe uma conta com esse e-mail."]
        if erros:
            raise exc.WrongArguments(erros)
        with transaction.atomic():
            user = User(username=username, email=email, full_name=full_name, token=str(uuid.uuid4()))
            user.set_unusable_password()
            user.save()
            Perfil.objects.create(user=user, **dados)
        transaction.on_commit(lambda: mail_builder.password_recovery(user, {"user": user}).send())
        return response.Created(self.serializer_class(user).data)

    def partial_update(self, request, pk=None, **kwargs):
        self.check_permissions(request, "partial_update")
        user = self.get_queryset().filter(pk=pk).first()
        if user is None:
            raise exc.NotFound()
        dados = _validar_perfil(request.DATA, parcial=True)
        perfil = getattr(user, "vetor_perfil", None) or Perfil(user=user)
        for campo, valor in dados.items():
            setattr(perfil, campo, valor)
        if dados or perfil.pk is None:
            perfil.save()
        if "is_active" in request.DATA:
            if not isinstance(request.DATA["is_active"], bool):
                raise exc.WrongArguments({"is_active": ["Use verdadeiro ou falso."]})
            user.is_active = request.DATA["is_active"]
            user.save(update_fields=["is_active"])
        user.refresh_from_db()
        return response.Ok(self.serializer_class(user).data)


def _validar_perfil(data, parcial=False):
    dados = {}
    if "papel" in data or not parcial:
        if data.get("papel") not in permissoes.NOMES:
            raise exc.WrongArguments({"papel": ["Papel inválido. Use: %s." % ", ".join(permissoes.NOMES)]})
        dados["papel"] = data["papel"]
    if "ver_custos" in data:
        raise exc.WrongArguments({"ver_custos": ["O financeiro é fechado para o usuário matriz, definido no servidor (VETOR_FINANCEIRO_USUARIOS)."]})
    return dados


class SaudeViewSet(SomenteAdministrador, GenericViewSet):
    """Saúde operacional (SPEC-10): só o Administrador."""
    permission_classes = ()

    def list(self, request, *args, **kwargs):
        self.check_permissions(request, "list")
        from . import saude
        return response.Ok(saude.estado())


class AuditoriaSerializer(serializers.LightSerializer):
    id = Field()
    ocorrido_em = Field()
    ator = Field(attr="ator_id")
    ator_nome = Field()
    acao = Field()
    alvo_tipo = Field()
    alvo_id = Field()
    resultado = Field()
    detalhes = Field()


class AuditoriaViewSet(SomenteAdministrador, ListModelMixin, GenericViewSet):
    serializer_class = AuditoriaSerializer
    permission_classes = ()
    paginate_by = 50

    def get_queryset(self):
        qs = Auditoria.objects.all()
        acao = self.request.QUERY_PARAMS.get("acao")
        return qs.filter(acao__startswith=acao) if acao else qs
