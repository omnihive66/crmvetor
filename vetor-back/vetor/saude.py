"""Saúde operacional (SPEC-10): filas, envio, backup e conectores num só lugar, com alertas aos administradores.

Conector sem credencial aparece como "não configurado" — nunca como ativo.
"""
import datetime
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import (AvisoOperacional, BackupRegistro, EventoMonitoramento, EventoProvedor, Perfil, ProdutoTelemetria,
                     TokenAgente)

log = logging.getLogger("vetor.saude")
UM_DIA = datetime.timedelta(days=1)


def _worker():
    """O worker Celery responde? Em teste/desenvolvimento sem Celery: 'desligado'."""
    if not settings.CELERY_ENABLED:
        return "desligado"
    try:
        from taiga.celery import app
        return "ok" if app.control.ping(timeout=1.0) else "sem_resposta"
    except Exception:  # broker fora do ar
        return "sem_resposta"


def _email():
    backend = settings.EMAIL_BACKEND
    configurado = "console" not in backend and "locmem" not in backend and "dummy" not in backend
    falhas = 0
    try:
        from djmail.models import Message
        falhas = Message.objects.filter(status=Message.STATUS_FAILED, created_at__gte=timezone.now() - UM_DIA).count()
    except Exception:
        pass
    return {"configurado": configurado, "falhas_24h": falhas}


def _backup(tipo):
    b = BackupRegistro.objects.filter(tipo=tipo).first()
    return {"feito_em": b.feito_em, "resultado": b.resultado, "cifrado": b.cifrado, "local": b.local, "detalhes": b.detalhes} if b else None


def conectores():
    tok = settings.VETOR_MONITOR_TOKENS
    return [
        {"nome": "GitHub (webhook)", "estado": "configurado" if settings.VETOR_GITHUB_WEBHOOK_SEGREDOS else "nao_configurado"},
        {"nome": "Uptime Kuma", "estado": "configurado" if tok.get("kuma") else "nao_configurado"},
        {"nome": "Beszel", "estado": "configurado" if tok.get("beszel") else "nao_configurado"},
        {"nome": "Agente externo", "estado": "contrato_disponivel",
         "detalhe": f"{TokenAgente.objects.filter(revogado_em__isnull=True).count()} token(s) ativo(s); tecnologia do agente não definida"},
        {"nome": "Telemetria de uso dos produtos", "estado": "contrato_disponivel",
         "detalhe": f"{ProdutoTelemetria.objects.filter(revogado_em__isnull=True, sintetico=False).count()} produto(s) real(is) com token"},
        {"nome": "Financeiro (usuário matriz)", "estado": "configurado" if settings.VETOR_FINANCEIRO_USUARIOS else "fechado_para_todos"},
        {"nome": "Sistema financeiro externo", "estado": "configurado" if settings.VETOR_SISTEMA_FINANCEIRO["nome"] else "nao_configurado"},
        {"nome": "AWS / Oracle (custos)", "estado": "nao_implementado", "detalhe": "faltam credenciais e contrato técnico"},
        {"nome": "Azure", "estado": "nao_definido", "detalhe": "serviço a definir (decisão 0009)"},
        {"nome": "MFA / SSO", "estado": "nao_configurado", "detalhe": "provedor a definir (decisão 0006)"},
    ]


def estado(agora=None):
    agora = agora or timezone.now()
    github = EventoProvedor.objects.filter(status=EventoProvedor.FALHOU).count()
    monitor = EventoMonitoramento.objects.filter(processamento=EventoMonitoramento.FALHOU).count()
    email, worker = _email(), _worker()
    backup, restauracao = _backup(BackupRegistro.BACKUP), _backup(BackupRegistro.RESTAURACAO)
    alertas = []
    if github:
        alertas.append({"codigo": "webhook_github_falhas", "texto": f"{github} entrega(s) do GitHub com falha na fila."})
    if monitor:
        alertas.append({"codigo": "monitoramento_falhas", "texto": f"{monitor} evento(s) de monitoramento com falha na fila."})
    if worker == "sem_resposta":
        alertas.append({"codigo": "worker_sem_resposta", "texto": "O worker (taiga-async) não respondeu: filas paradas."})
    if not email["configurado"]:
        alertas.append({"codigo": "email_nao_configurado", "texto": "Envio de e-mail não configurado (os e-mails vão só para o log)."})
    if email["falhas_24h"]:
        alertas.append({"codigo": "email_falhas", "texto": f"{email['falhas_24h']} e-mail(s) com falha nas últimas 24 h."})
    limite = datetime.timedelta(hours=settings.VETOR_BACKUP_MAX_HORAS)
    if backup is None or backup["resultado"] != "ok" or agora - backup["feito_em"] > limite:
        alertas.append({"codigo": "backup_atrasado", "texto": f"Sem backup bem-sucedido nas últimas {settings.VETOR_BACKUP_MAX_HORAS} h."})
    elif not backup["cifrado"]:
        alertas.append({"codigo": "backup_sem_cifra", "texto": "Último backup sem criptografia (defina VETOR_BACKUP_CHAVE_ARQUIVO)."})
    if restauracao is None or restauracao["resultado"] != "ok":
        alertas.append({"codigo": "restauracao_nao_testada", "texto": "Nenhuma restauração isolada bem-sucedida registrada."})
    return {"verificado_em": agora, "filas": {"github_falhas": github, "monitoramento_falhas": monitor, "worker": worker},
            "email": email, "backup": backup, "restauracao_teste": restauracao, "conectores": conectores(), "alertas": alertas}


def avisar(agora=None):
    """E-mail aos administradores com os alertas novos; o mesmo código no máximo uma vez a cada 24 h."""
    agora = agora or timezone.now()
    novos = []
    for a in estado(agora)["alertas"]:
        aviso = AvisoOperacional.objects.filter(codigo=a["codigo"]).first()
        if aviso and agora - aviso.enviado_em < UM_DIA:
            continue
        AvisoOperacional.objects.update_or_create(codigo=a["codigo"], defaults={"enviado_em": agora})
        novos.append(a)
    destinos = list(Perfil.objects.filter(papel=Perfil.ADMINISTRADOR, user__is_active=True).exclude(user__email="")
                    .values_list("user__email", flat=True))
    if novos and destinos:
        try:
            send_mail("[Vetor Sistemas] Alertas de operação", "\n".join(f"- {a['texto']}" for a in novos) +
                      "\n\nDetalhes em Administração → Saúde operacional.", settings.DEFAULT_FROM_EMAIL, destinos)
        except Exception:
            log.exception("falha ao enviar alertas de operação")
    for a in novos:
        log.warning("alerta de operação: %s", a["codigo"])
    return novos
