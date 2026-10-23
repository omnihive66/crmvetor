"""Participação por etapa (SPEC-04): abre e fecha intervalos quando status, responsável ou colaboradores mudam."""
from django.db.models.signals import m2m_changed, post_save
from django.utils import timezone

from taiga.projects.userstories.models import UserStory

from .ator import ATOR
from .models import ParticipacaoEtapa


def _nome(user):
    return (user.get_full_name() or user.username) if user else "sistema"


def sincronizar(historia):
    ator = ATOR.get()
    autor = _nome(ator if ator is not None and ator.is_authenticated else None)
    agora = timezone.now()
    status = historia.status
    pessoas = {u.id: u for u in historia.assigned_users.all()}
    if historia.assigned_to_id:
        pessoas.setdefault(historia.assigned_to_id, historia.assigned_to)
    if status is None or status.is_closed:
        pessoas = {}  # etapa de conclusão não conta como participação em andamento
    mantidas = set()
    for p in ParticipacaoEtapa.objects.filter(historia=historia, fim__isnull=True):
        if p.status_id == historia.status_id and p.usuario_id in pessoas:
            mantidas.add(p.usuario_id)
        else:
            p.fim, p.autor_fim = agora, autor
            p.save(update_fields=["fim", "autor_fim"])
    ParticipacaoEtapa.objects.bulk_create([
        ParticipacaoEtapa(historia=historia, usuario=u, usuario_nome=_nome(u), status=status, status_nome=status.name,
                          inicio=agora, autor_inicio=autor)
        for uid, u in pessoas.items() if uid not in mantidas])


def _apos_salvar(sender, instance, raw=False, **kwargs):
    if not raw and not getattr(instance, "_importing", False):
        sincronizar(instance)


def _apos_colaboradores(sender, instance, action, **kwargs):
    if action in ("post_add", "post_remove", "post_clear") and isinstance(instance, UserStory):
        sincronizar(instance)


def conectar():
    post_save.connect(_apos_salvar, sender=UserStory, dispatch_uid="vetor.participacao.post_save")
    m2m_changed.connect(_apos_colaboradores, sender=UserStory.assigned_users.through, dispatch_uid="vetor.participacao.m2m")
