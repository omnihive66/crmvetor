"""Valida o teto do papel e registra auditoria em toda mudança de acesso, venha de onde vier
(API, importação, admin do Django ou shell). Com ATOMIC_REQUESTS, recusar no pre_save desfaz a
requisição inteira, inclusive a criação do projeto que geraria a membership."""
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db.models.signals import post_delete, post_save, pre_save

from taiga.projects.custom_attributes.models import UserStoryCustomAttribute
from taiga.projects.models import Membership
from taiga.users.models import Role

from . import permissoes
from .auditoria import registrar
from .models import Perfil


def _antes(sender, instance, *campos):
    if instance.pk is None:
        return None
    return sender.objects.filter(pk=instance.pk).values(*campos).first()


def membership_pre_save(sender, instance, **kwargs):
    instance._vetor_antes = _antes(sender, instance, "role_id", "is_admin", "user_id")
    if instance.user_id:
        permissoes.checar_membership(instance.user, instance.project, instance.is_admin,
                                     instance.role.permissions if instance.role_id else [])


def membership_post_save(sender, instance, created, **kwargs):
    agora = {"role_id": instance.role_id, "is_admin": instance.is_admin, "user_id": instance.user_id}
    antes = instance._vetor_antes
    if created or antes != agora:
        registrar("membership.criada" if created else "membership.alterada", instance,
                  projeto=instance.project_id, usuario=instance.user_id, email_convite=bool(instance.email),
                  papel_projeto=instance.role.name if instance.role_id else None,
                  admin_projeto=instance.is_admin, antes=antes)


def membership_post_delete(sender, instance, **kwargs):
    registrar("membership.removida", instance, projeto=instance.project_id, usuario=instance.user_id)


def role_pre_save(sender, instance, **kwargs):
    instance._vetor_antes = _antes(sender, instance, "permissions")
    if instance.pk:
        for m in Membership.objects.filter(role=instance, user__isnull=False).select_related("user__vetor_perfil", "project"):
            permissoes.checar_membership(m.user, m.project, m.is_admin, instance.permissions)


def role_post_save(sender, instance, created, **kwargs):
    antes = (instance._vetor_antes or {}).get("permissions")
    if not created and sorted(antes or []) != sorted(instance.permissions or []):
        registrar("papel_projeto.permissoes_alteradas", instance, projeto=instance.project_id,
                  adicionadas=sorted(set(instance.permissions or []) - set(antes or [])),
                  removidas=sorted(set(antes or []) - set(instance.permissions or [])))


def perfil_pre_save(sender, instance, **kwargs):
    instance._vetor_antes = _antes(sender, instance, "papel", "ver_custos")
    for m in Membership.objects.filter(user_id=instance.user_id).select_related("user", "project", "role"):
        permissoes.checar_membership(m.user, m.project, m.is_admin, m.role.permissions, papel_org=instance.papel)
    antes = instance._vetor_antes or {}
    if antes.get("papel") == Perfil.ADMINISTRADOR != instance.papel:
        _garantir_outro_administrador(instance.user_id)


def perfil_post_save(sender, instance, created, **kwargs):
    agora = {"papel": instance.papel, "ver_custos": instance.ver_custos}
    if created or instance._vetor_antes != agora:
        registrar("perfil.criado" if created else "perfil.alterado", instance, usuario=instance.user_id,
                  antes=instance._vetor_antes, depois=agora)


def user_pre_save(sender, instance, **kwargs):
    instance._vetor_antes = _antes(sender, instance, "is_active")
    antes = instance._vetor_antes
    if antes and antes["is_active"] and not instance.is_active and permissoes.papel(instance) == Perfil.ADMINISTRADOR:
        _garantir_outro_administrador(instance.pk)


def user_post_save(sender, instance, created, **kwargs):
    antes = instance._vetor_antes
    if created:
        registrar("usuario.criado", instance, username=instance.username)
    elif antes and antes["is_active"] != instance.is_active:
        registrar("usuario.ativado" if instance.is_active else "usuario.desativado", instance)


def _garantir_outro_administrador(user_id):
    admins = get_user_model().objects.filter(Q(is_superuser=True) | Q(vetor_perfil__papel=Perfil.ADMINISTRADOR))
    if not admins.filter(is_active=True).exclude(pk=user_id).exists():
        permissoes.negar("É preciso manter pelo menos um administrador ativo.")


PRIORIDADES = ["Baixa", "Média", "Alta", "Urgente"]


def prioridade_post_save(sender, instance, created, **kwargs):
    # O modelo de projeto do Taiga não guarda as opções de um campo lista: o "Prioridade" do fluxo Vetor nasceria vazio.
    if created and instance.name == "Prioridade" and instance.type == "dropdown" and not instance.extra:
        sender.objects.filter(pk=instance.pk).update(extra=PRIORIDADES)


def conectar():
    User = get_user_model()
    for sinal, func, modelo in [
        (pre_save, membership_pre_save, Membership), (post_save, membership_post_save, Membership),
        (post_delete, membership_post_delete, Membership),
        (pre_save, role_pre_save, Role), (post_save, role_post_save, Role),
        (pre_save, perfil_pre_save, Perfil), (post_save, perfil_post_save, Perfil),
        (pre_save, user_pre_save, User), (post_save, user_post_save, User),
        (post_save, prioridade_post_save, UserStoryCustomAttribute),
    ]:
        sinal.connect(func, sender=modelo, dispatch_uid=f"vetor.{func.__name__}")
