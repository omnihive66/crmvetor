"""Lembretes privados (SPEC-05): referências por acesso atual, aviso idempotente e conversão em demanda.

Privacidade: toda leitura parte de Lembrete.objects.filter(dono=user). Lembretes não entram na busca
global, na auditoria (só o fato de uma conversão, sem conteúdo), nos eventos do Taiga nem em exportações.
"""
import calendar
import datetime
import logging
import zoneinfo

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from taiga.base import exceptions as exc
from taiga.permissions.services import user_has_perm
from taiga.projects.history.services import take_snapshot
from taiga.projects.userstories.models import UserStory

from . import clientes as regras
from .auditoria import registrar
from .models import Lembrete

log = logging.getLogger("vetor.lembretes")
FUSO = zoneinfo.ZoneInfo("America/Sao_Paulo")
PASSO = {"diaria": datetime.timedelta(days=1), "semanal": datetime.timedelta(weeks=1)}


def referencias(lembrete, user):
    """Só o que o dono ainda pode ver; acesso revogado some daqui sem apagar o lembrete."""
    projetos = set(regras.projetos_visiveis(user).values_list("id", flat=True))
    com_us = set(regras.projetos_visiveis(user, "view_us").values_list("id", flat=True))
    out = {"cliente": None, "projeto": None, "historia": None, "convertido_em": None}
    if lembrete.cliente_id and regras.clientes_visiveis(user).filter(pk=lembrete.cliente_id).exists():
        out["cliente"] = {"id": lembrete.cliente_id, "nome": lembrete.cliente.nome}
    if lembrete.projeto_id in projetos:
        out["projeto"] = {"id": lembrete.projeto_id, "nome": lembrete.projeto.name, "slug": lembrete.projeto.slug}
    for campo in ("historia", "convertido_em"):
        us = getattr(lembrete, campo)
        if us and us.project_id in com_us:
            out[campo] = {"id": us.id, "ref": us.ref, "assunto": us.subject, "projeto": us.project.slug}
    out["referencia_indisponivel"] = any(getattr(lembrete, f"{c}_id") and not out[c] for c in ("cliente", "projeto", "historia"))
    return out


def validar_referencias(user, data):
    dados = {}
    if "cliente" in data:
        cid = data.get("cliente")
        if cid and not regras.clientes_visiveis(user).filter(pk=cid).exists():
            raise exc.WrongArguments({"cliente": ["Cliente não encontrado."]})
        dados["cliente_id"] = cid or None
    if "projeto" in data:
        pid = data.get("projeto")
        if pid and not regras.projetos_visiveis(user).filter(pk=pid).exists():
            raise exc.WrongArguments({"projeto": ["Projeto não encontrado."]})
        dados["projeto_id"] = pid or None
    if "historia" in data:
        hid = data.get("historia")
        if hid and not UserStory.objects.filter(pk=hid, project__in=regras.projetos_visiveis(user, "view_us").values("id")).exists():
            raise exc.WrongArguments({"historia": ["História não encontrada."]})
        dados["historia_id"] = hid or None
    return dados


def proximo(vencimento, recorrencia, agora):
    """Próxima ocorrência estritamente no futuro, contada no fuso de São Paulo (mensal: mesmo dia do mês)."""
    local = vencimento.astimezone(FUSO)
    dia_base = local.day  # 31/jan → 28/fev → 31/mar, sem ficar preso no dia 28
    while local <= agora:
        if recorrencia == "mensal":
            ano, mes = local.year + local.month // 12, local.month % 12 + 1
            local = local.replace(year=ano, month=mes, day=min(dia_base, calendar.monthrange(ano, mes)[1]))
        else:
            local = (local.replace(tzinfo=None) + PASSO[recorrencia]).replace(tzinfo=FUSO)  # mesma hora local
    return local


def avisar_vencidos(agora=None):
    """Avisa cada vencimento uma vez. A reserva é um UPDATE condicional: dois workers não avisam o mesmo."""
    agora = agora or timezone.now()
    avisados = 0
    for lembrete in Lembrete.objects.filter(estado=Lembrete.ABERTO, notificado_em__isnull=True, vencimento__lte=agora).select_related("dono"):
        if not Lembrete.objects.filter(pk=lembrete.pk, notificado_em__isnull=True).update(notificado_em=agora, visto_em=None):
            continue
        avisados += 1
        if lembrete.avisar_email and lembrete.dono.email:
            quando = lembrete.vencimento.astimezone(FUSO).strftime("%d/%m/%Y %H:%M")
            try:
                send_mail(f"[Vetor Sistemas] Lembrete: {lembrete.titulo}",
                          f"Seu lembrete venceu em {quando} (horário de Brasília).\n\n{lembrete.titulo}\n\n{lembrete.notas}\n\n"
                          f"Abra Minhas demandas na Vetor Sistemas para concluir ou reagendar.",
                          settings.DEFAULT_FROM_EMAIL, [lembrete.dono.email])
            except Exception:  # o aviso interno já foi dado; e-mail é complementar
                log.exception("lembrete %s: falha ao enviar e-mail", lembrete.pk)
        if lembrete.recorrencia:
            # Recorrente: o próximo vencimento já fica agendado (com aviso pendente) e o atual some da lista.
            Lembrete.objects.filter(pk=lembrete.pk).update(vencimento=proximo(lembrete.vencimento, lembrete.recorrencia, agora),
                                                           notificado_em=None)
        log.info("lembrete %s avisado (dono %s)", lembrete.pk, lembrete.dono_id)  # sem título nem notas
    return avisados


def previa_conversao(lembrete, user, projeto_id, copiar_notas):
    projeto = regras.projetos_visiveis(user).filter(pk=projeto_id).first()
    if projeto is None:
        raise exc.WrongArguments({"projeto": ["Projeto não encontrado."]})
    if not user_has_perm(user, "add_us", projeto):
        raise exc.PermissionDenied("Você não pode criar demandas neste projeto.")
    membros = projeto.memberships.filter(user__isnull=False).count()
    prazo = lembrete.vencimento.astimezone(FUSO).date() if lembrete.vencimento else None
    return projeto, {
        "destino": {"id": projeto.id, "nome": projeto.name},
        "visibilidade": f"Visível para as {membros} pessoa(s) do projeto “{projeto.name}”"
                        + (" e para qualquer pessoa (projeto público)" if not projeto.is_private else "") + ".",
        "campos": {"assunto": lembrete.titulo, "descricao": lembrete.notas if copiar_notas else "",
                   "prazo": prazo.isoformat() if prazo else None},
        "nao_copiados": [c for c, v in (("notas", lembrete.notas and not copiar_notas), ("cliente/projeto/história de referência", True)) if v],
        "lembrete_continua_privado": True,
    }


def converter(lembrete, user, projeto_id, copiar_notas):
    """Cria uma única demanda: repetir a chamada devolve a mesma (o vínculo fica no lembrete, sob lock)."""
    with transaction.atomic():
        lembrete = Lembrete.objects.select_for_update().get(pk=lembrete.pk, dono=user)
        if lembrete.convertido_em_id:
            return lembrete.convertido_em, False
        projeto, previa = previa_conversao(lembrete, user, projeto_id, copiar_notas)
        c = previa["campos"]
        us = UserStory.objects.create(project=projeto, owner=user, subject=c["assunto"], description=c["descricao"],
                                      due_date=c["prazo"], status=projeto.default_us_status)
        take_snapshot(us, user=user)
        lembrete.convertido_em, lembrete.estado = us, Lembrete.CONCLUIDO
        lembrete.save(update_fields=["convertido_em", "estado", "atualizado_em"])
        registrar("lembrete.convertido", lembrete, projeto=projeto.id, historia=us.id)  # só ids: o conteúdo é privado
        return us, True
