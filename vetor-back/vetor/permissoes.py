"""Papel na organização x participação no projeto (SPEC-02).

O Taiga calcula permissão por projeto em vários lugares, inclusive em SQL nas listagens. Em vez de
interceptar esses cálculos, o papel organizacional limita quais memberships a pessoa pode ter:
o que o Taiga concede nunca passa do teto do papel.
"""
from django.conf import settings

from taiga.base import exceptions as exc
from taiga.permissions.choices import MEMBERS_PERMISSIONS

from .models import Perfil

SO_LEITURA = {p for p, _ in MEMBERS_PERMISSIONS if p.startswith("view_")}
NOMES = dict(Perfil.PAPEIS)


def papel(user):
    if not user or not user.is_authenticated:
        return None
    perfil = getattr(user, "vetor_perfil", None)  # RelatedObjectDoesNotExist é AttributeError
    if perfil:
        return perfil.papel
    if user.is_superuser:
        return Perfil.ADMINISTRADOR
    return settings.VETOR_PAPEL_SEM_PERFIL  # produção: observador (negar por padrão)


def financeiro(user):
    """Custos só para o(s) usuário(s) matriz definidos no servidor (VETOR_FINANCEIRO_USUARIOS). Vazio = fechado."""
    return bool(user and user.is_authenticated and user.is_active
                and user.username.lower() in settings.VETOR_FINANCEIRO_USUARIOS)


def e_administrador(user):
    return bool(user and user.is_authenticated and user.is_active and
                (user.is_superuser or papel(user) == Perfil.ADMINISTRADOR))


def excede_teto(papel_org, is_admin, permissoes):
    """Motivo pelo qual a membership passa do teto do papel, ou None."""
    if papel_org in (Perfil.ADMINISTRADOR, Perfil.GESTOR):
        return None
    if is_admin:
        return "não pode administrar projetos"
    extras = set(permissoes or []) - SO_LEITURA
    if papel_org == Perfil.OBSERVADOR and extras:
        return "tem acesso só de leitura (papel do projeto inclui: %s)" % ", ".join(sorted(extras))
    return None


def negar(mensagem):
    # O rollback da requisição fica por conta de vetor.excecoes.exception_handler.
    raise exc.PermissionDenied(mensagem)


def checar_membership(user, project, is_admin, permissoes, papel_org=None):
    motivo = excede_teto(papel_org or papel(user), is_admin, permissoes)
    if motivo:
        negar("%s (%s) %s no projeto “%s”. Ajuste o papel na organização ou o papel no projeto."
                                   % (user.get_full_name() or user.username, NOMES[papel_org or papel(user)],
                                      motivo, project.name))
