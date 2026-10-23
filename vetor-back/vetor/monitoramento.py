"""Uptime Kuma e Beszel (SPEC-07): alertas viram incidentes com linha do tempo, ligados ao projeto do recurso.

Formatos conferidos no código-fonte: Uptime Kuma 2.5.7 (notificação "Webhook", JSON {heartbeat, monitor, msg})
e Beszel v0.21.1 (Shoutrrr generic com template=json: {title, message}). Nenhum dos dois assina o webhook:
a recepção exige o cabeçalho X-Vetor-Token (segredo no servidor, comparado em tempo constante) e HTTPS.
"""
import datetime
import hmac
import json
import logging
import re
import urllib.parse

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from taiga.projects.history.services import take_snapshot
from taiga.projects.userstories.models import UserStory

from .lembretes import FUSO
from .models import EventoMonitoramento, Incidente, RecursoMonitorado

log = logging.getLogger("vetor.monitoramento")
PROBLEMA, NORMAL = {"down", "alerta"}, {"up", "normal"}
NOMES = {"kuma": "Uptime Kuma", "beszel": "Beszel"}
MAX_TENTATIVAS = 5
KUMA_STATUS = {0: ("down", "critica"), 1: ("up", "info"), 2: ("pendente", "aviso"), 3: ("manutencao", "info")}
BESZEL_LINK = re.compile(r"https?://\S+?/system/([A-Za-z0-9_-]+)")
BESZEL_CONEXAO = re.compile(r"^Connection to (.+) is (down|up)\b")
# Métricas exatas dos títulos do Beszel (internal/alerts/alerts_system.go); o nome do servidor pode ter espaços.
BESZEL_LIMITE = re.compile(r"^(.+) (CPU I/O Wait|CPU Steal Time|CPU|GPU|memory|bandwidth|disk usage|temperature|1m load|5m load|15m load|battery)"
                           r" (above|below) threshold")


def token_valido(provedor, recebido):
    return bool(recebido) and any(hmac.compare_digest(t, recebido) for t in settings.VETOR_MONITOR_TOKENS.get(provedor, []))


def _url_segura(url):
    """Sem usuário/senha nem query string (podem carregar credenciais do monitor)."""
    if not url or not isinstance(url, str):
        return ""
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ("http", "https"):
        return ""
    return urllib.parse.urlunsplit((p.scheme, p.hostname + (f":{p.port}" if p.port else ""), p.path, "", ""))[:500]


def normalizar_kuma(dados):
    monitor, beat = dados.get("monitor") or {}, dados.get("heartbeat") or {}
    rid = str(monitor.get("id") or beat.get("monitorID") or "")
    payload = {"monitor": {k: monitor.get(k) for k in ("id", "name", "type", "hostname", "port")} | {"url": _url_segura(monitor.get("url"))},
               "heartbeat": {k: beat.get(k) for k in ("status", "time", "msg", "ping", "important", "duration")}, "msg": dados.get("msg")}
    if not beat:  # teste da notificação ou aviso de certificado: registrado, sem mudar incidente
        if not dados.get("msg"):
            raise ValueError("sem heartbeat nem msg")
        return dict(id_externo=None, id_recurso=rid, nome=monitor.get("name") or rid, tipo="aviso", status="info", severidade="info",
                    resumo=str(dados.get("msg") or "")[:500], url_origem=_url_segura(monitor.get("url")), ocorrido_em=timezone.now(), payload=payload)
    if beat.get("status") not in KUMA_STATUS or not beat.get("time"):
        raise ValueError("heartbeat sem status ou horário reconhecido")
    status, severidade = KUMA_STATUS[beat["status"]]
    quando = datetime.datetime.strptime(beat["time"][:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)  # Kuma grava em UTC
    return dict(id_externo=f"{rid}:{beat['time']}:{beat['status']}", id_recurso=rid, nome=monitor.get("name") or f"Monitor {rid}",
                tipo="disponibilidade", status=status, severidade=severidade, resumo=str(beat.get("msg") or dados.get("msg") or "")[:500],
                url_origem=_url_segura(monitor.get("url")), ocorrido_em=quando, payload=payload)


def normalizar_beszel(dados):
    titulo, mensagem = str(dados.get("title") or ""), str(dados.get("message") or "")
    link = BESZEL_LINK.search(mensagem)
    base = dict(id_externo=None, id_recurso=link.group(1) if link else "", url_origem=_url_segura(link.group(0)) if link else "",
                ocorrido_em=timezone.now(),  # o Beszel não manda horário: vale o recebimento
                resumo=titulo.strip()[:500], payload={"title": titulo, "message": mensagem})
    if m := BESZEL_CONEXAO.match(titulo):
        return base | dict(nome=m.group(1), tipo="disponibilidade", status=m.group(2), severidade="critica" if m.group(2) == "down" else "info")
    if m := BESZEL_LIMITE.match(titulo):
        metrica = m.group(2).strip().lower()
        disparou = (m.group(3) == "below") if metrica == "battery" else (m.group(3) == "above")  # bateria alerta por baixo
        return base | dict(nome=m.group(1), tipo=f"limite:{metrica}"[:60], status="alerta" if disparou else "normal",
                           severidade="aviso" if disparou else "info")
    return base | dict(nome=base["id_recurso"] or "Beszel", tipo="aviso", status="info", severidade="info")  # containers, SMART...


NORMALIZAR = {"kuma": normalizar_kuma, "beszel": normalizar_beszel}


@csrf_exempt  # autenticado pelo token no cabeçalho, não por cookie
@require_POST
def webhook(request, provedor):
    if provedor not in NORMALIZAR:
        return JsonResponse({"erro": "Provedor desconhecido."}, status=404)
    if not settings.VETOR_MONITOR_TOKENS.get(provedor):
        return JsonResponse({"erro": f"Integração {provedor} não configurada neste servidor."}, status=503)
    if not token_valido(provedor, request.headers.get("X-Vetor-Token", "")):
        log.warning("%s: entrega recusada, token ausente ou inválido", provedor)
        return JsonResponse({"erro": "Token ausente ou inválido."}, status=401)
    try:
        dados = json.loads(request.body)
        if not isinstance(dados, dict):
            raise ValueError
        campos = NORMALIZAR[provedor](dados)
    except (ValueError, TypeError, KeyError, AttributeError) as e:
        log.warning("%s: entrega recusada, formato não reconhecido (%s)", provedor, type(e).__name__)
        return JsonResponse({"erro": "Formato não reconhecido. Kuma: JSON padrão do webhook; Beszel: generic com template=json."}, status=400)
    nome = campos.pop("nome")
    try:
        with transaction.atomic():
            ev = EventoMonitoramento.objects.create(provedor=provedor, **campos)
    except IntegrityError:
        ev = EventoMonitoramento.objects.get(provedor=provedor, id_externo=campos["id_externo"])
        if ev.processamento == EventoMonitoramento.FALHOU:
            agendar(ev.id)
        return JsonResponse({"status": "duplicado", "situacao": ev.processamento})
    if ev.id_recurso:  # recurso novo entra em triagem (sem projeto); o nome acompanha o provedor
        recurso, criado = RecursoMonitorado.objects.get_or_create(provedor=provedor, id_externo=ev.id_recurso, defaults={"nome": nome[:200]})
        if not criado and recurso.nome != nome[:200] and ev.tipo != "aviso":
            RecursoMonitorado.objects.filter(pk=recurso.pk).update(nome=nome[:200])
        EventoMonitoramento.objects.filter(pk=ev.pk).update(recurso=recurso)
    agendar(ev.id)
    return JsonResponse({"status": "recebido"}, status=202)


def agendar(evento_id):
    if settings.CELERY_ENABLED:
        from .tasks import processar_evento_monitoramento
        transaction.on_commit(lambda: processar_evento_monitoramento.delay(evento_id))
    else:
        processar(evento_id)


def processar(evento_id):
    with transaction.atomic():
        ev = EventoMonitoramento.objects.select_for_update(of=("self",)).select_related("recurso__projeto").get(pk=evento_id)
        if ev.processamento == EventoMonitoramento.PROCESSADO:
            return ev
        ev.tentativas += 1
        try:
            with transaction.atomic():
                ev.incidente = _aplicar(ev)
                ev.processamento, ev.erro = EventoMonitoramento.PROCESSADO, ""
        except Exception as e:
            ev.processamento, ev.erro = EventoMonitoramento.FALHOU, f"{type(e).__name__}: {e}"[:2000]
            log.exception("%s: evento %s falhou (tentativa %s)", ev.provedor, ev.pk, ev.tentativas)
        ev.save()
    log.info("%s evento=%s recurso=%s status=%s processamento=%s", ev.provedor, ev.pk, ev.id_recurso, ev.status, ev.processamento)
    return ev


def _aplicar(ev):
    """Devolve o incidente ao qual o evento pertence (linha do tempo), mudando o estado só com evento mais novo."""
    if ev.recurso is None or ev.status not in PROBLEMA | NORMAL:
        return None
    janela = datetime.timedelta(minutes=settings.VETOR_MONITOR_JANELA_MIN)
    inc = Incidente.objects.select_for_update().filter(recurso=ev.recurso, tipo=ev.tipo).order_by("-aberto_em").first()
    if ev.status in PROBLEMA:
        if inc and inc.estado == Incidente.ABERTO:
            inc.ocorrencias += 1
            if ev.ocorrido_em > inc.ultimo_evento_em:
                inc.ultimo_evento_em = ev.ocorrido_em
            inc.save()
            return inc
        if inc and inc.recuperado_em and ev.ocorrido_em <= inc.recuperado_em:
            return inc  # queda anterior à recuperação já registrada (fora de ordem): só linha do tempo
        if inc and ev.ocorrido_em - inc.recuperado_em <= janela:  # reincidência dentro da janela antirruído
            inc.estado, inc.recuperado_em, inc.ultimo_evento_em = Incidente.ABERTO, None, ev.ocorrido_em
            inc.reincidencias += 1
            inc.ocorrencias += 1
            inc.save()
            _notificar(inc, f"voltou a falhar: {ev.resumo}")
            return inc
        inc = Incidente.objects.create(recurso=ev.recurso, tipo=ev.tipo, severidade=ev.severidade, resumo=ev.resumo or ev.tipo,
                                       aberto_em=ev.ocorrido_em, ultimo_evento_em=ev.ocorrido_em)
        criar_demanda(inc)
        _notificar(inc, f"aberto: {ev.resumo}")
        return inc
    if not inc or inc.estado != Incidente.ABERTO or ev.ocorrido_em < inc.ultimo_evento_em:
        return inc if inc and ev.ocorrido_em >= inc.aberto_em else None  # nada aberto ou recuperação antiga: só registra
    inc.estado, inc.recuperado_em, inc.ultimo_evento_em = Incidente.RECUPERADO, ev.ocorrido_em, ev.ocorrido_em
    inc.save()  # a demanda NÃO é concluída: quem acompanha decide (spec)
    _notificar(inc, "recuperado")
    return inc


def criar_demanda(inc):
    """Demanda no projeto do recurso; recurso em triagem não ganha demanda até ser mapeado."""
    projeto = inc.recurso.projeto
    if projeto is None or inc.historia_id:
        return
    titulo = "fora do ar" if inc.tipo == "disponibilidade" else inc.tipo.replace("limite:", "") + " fora do limite"
    us = UserStory.objects.create(
        project=projeto, owner=projeto.owner, status=projeto.default_us_status, assigned_to=projeto.owner,
        subject=f"[Incidente] {inc.recurso.nome} {titulo}"[:500],
        description=f"Aberto pelo {NOMES[inc.recurso.provedor]} em {inc.aberto_em.astimezone(FUSO):%d/%m/%Y %H:%M} (Brasília).\n\n"
                    f"{inc.resumo}\n\nLinha do tempo: /vetor/monitoramento/?incidente={inc.id}\n\n"
                    "A recuperação atualiza o incidente, mas não conclui esta demanda.")
    take_snapshot(us, user=projeto.owner)
    Incidente.objects.filter(pk=inc.pk).update(historia=us)
    inc.historia = us


def _notificar(inc, o_que):
    """Responsável pelo projeto (dono), no máximo um e-mail por incidente a cada VETOR_MONITOR_AVISO_MIN."""
    projeto = inc.recurso.projeto
    agora = timezone.now()
    if projeto is None or not projeto.owner.email:
        return
    if inc.notificado_em and agora - inc.notificado_em < datetime.timedelta(minutes=settings.VETOR_MONITOR_AVISO_MIN):
        return
    Incidente.objects.filter(pk=inc.pk).update(notificado_em=agora)
    inc.notificado_em = agora
    try:
        send_mail(f"[Vetor Sistemas] Incidente {o_que.split(':')[0]}: {inc.recurso.nome}"[:200],
                  f"{inc.recurso.nome} ({projeto.name}) — incidente {o_que}\n\nVeja a linha do tempo em Monitoramento na Vetor Sistemas.",
                  settings.DEFAULT_FROM_EMAIL, [projeto.owner.email])
    except Exception:
        log.exception("incidente %s: falha ao enviar e-mail", inc.pk)


def mapear(recurso, projeto):
    """Tira da triagem: incidentes ainda abertos ganham a demanda no projeto escolhido."""
    recurso.projeto = projeto
    recurso.save(update_fields=["projeto"])
    for inc in recurso.incidentes.filter(estado=Incidente.ABERTO, historia__isnull=True).select_related("recurso__projeto"):
        criar_demanda(inc)
        _notificar(inc, f"aberto: {inc.resumo}")  # na abertura estava em triagem: ninguém foi avisado


def limpar_payloads(agora=None):
    """Retenção: depois de VETOR_MONITOR_RETENCAO_DIAS fica só o evento normalizado (linha do tempo continua)."""
    limite = (agora or timezone.now()) - datetime.timedelta(days=settings.VETOR_MONITOR_RETENCAO_DIAS)
    return EventoMonitoramento.objects.filter(recebido_em__lt=limite, payload__isnull=False).update(payload=None)
