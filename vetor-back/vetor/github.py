"""Conector GitHub (SPEC-06): webhooks assinados viram vínculos de issue, commit e PR com as histórias citadas (TG-<ref>).

Direção única: GitHub → Vetor. A Vetor não escreve no GitHub e não guarda token dele; o único segredo é o do
webhook, no ambiente do servidor. Cada entrega é guardada como chegou (origem preservada) e processada no worker.
"""
import hashlib
import hmac
import json
import logging
import re

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from taiga.projects.userstories.models import UserStory

from .models import EventoProvedor, Repositorio, VinculoCodigo

log = logging.getLogger("vetor.github")
REF = re.compile(r"\bTG-(\d+)\b", re.I)
EVENTOS = ("pull_request", "push", "issues")
MAX_TENTATIVAS = 5


def assinatura_valida(corpo, cabecalho):
    """X-Hub-Signature-256. Aceita mais de um segredo para a troca (rotação) sem parar de receber."""
    if not cabecalho or not cabecalho.startswith("sha256="):
        return False
    return any(hmac.compare_digest("sha256=" + hmac.new(s.encode(), corpo, hashlib.sha256).hexdigest(), cabecalho)
               for s in settings.VETOR_GITHUB_WEBHOOK_SEGREDOS)


@csrf_exempt  # autenticado pela assinatura HMAC, não por cookie
@require_POST
def webhook(request):
    if not settings.VETOR_GITHUB_WEBHOOK_SEGREDOS:
        return JsonResponse({"erro": "Integração GitHub não configurada neste servidor."}, status=503)
    if not assinatura_valida(request.body, request.headers.get("X-Hub-Signature-256")):
        log.warning("github: entrega recusada, assinatura ausente ou inválida")
        return JsonResponse({"erro": "Assinatura ausente ou inválida."}, status=401)
    entrega, evento = request.headers.get("X-GitHub-Delivery", ""), request.headers.get("X-GitHub-Event", "")
    try:
        payload = json.loads(request.body)
    except ValueError:
        payload = None
    if not entrega or not evento or not isinstance(payload, dict):
        return JsonResponse({"erro": "Entrega sem X-GitHub-Delivery, X-GitHub-Event ou JSON válido."}, status=400)
    try:
        with transaction.atomic():
            ev = EventoProvedor.objects.create(entrega=entrega[:100], evento=evento[:50], payload=payload)
    except IntegrityError:
        ev = EventoProvedor.objects.get(provedor="github", entrega=entrega[:100])
        if ev.status == EventoProvedor.FALHOU:  # "Redeliver" no GitHub reprocessa o que falhou, sem duplicar
            agendar(ev.id)
        return JsonResponse({"status": "duplicado", "situacao": ev.status})
    agendar(ev.id)
    return JsonResponse({"status": "recebido"}, status=202)


def agendar(evento_id):
    if settings.CELERY_ENABLED:
        from .tasks import processar_evento_github
        transaction.on_commit(lambda: processar_evento_github.delay(evento_id))
    else:
        processar(evento_id)


def processar(evento_id):
    """Idempotente: evento já processado não é aplicado de novo; falha fica na fila com o erro e o payload."""
    with transaction.atomic():
        ev = EventoProvedor.objects.select_for_update().get(pk=evento_id)
        if ev.status in (EventoProvedor.PROCESSADO, EventoProvedor.IGNORADO):
            return ev
        ev.tentativas += 1
        try:
            with transaction.atomic():
                ev.status, ev.erro = _aplicar(ev), ""
        except Exception as e:  # o payload fica guardado: reprocessar depois não perde a origem
            ev.status, ev.erro = EventoProvedor.FALHOU, f"{type(e).__name__}: {e}"[:2000]
            log.exception("github: entrega %s falhou (tentativa %s)", ev.entrega, ev.tentativas)
        ev.processado_em = timezone.now()
        ev.save()
    log.info("github entrega=%s evento=%s status=%s", ev.entrega, ev.evento, ev.status)  # sem conteúdo do payload
    return ev


def _repositorio(dados):
    rid, nome = str(dados.get("id") or ""), dados.get("full_name") or ""
    qs = Repositorio.objects.filter(provedor="github")
    repo = (rid and qs.filter(id_externo=rid).first()) or qs.filter(Q(id_externo="") | Q(id_externo=rid), nome__iexact=nome).first()
    if repo and (repo.id_externo != rid or repo.nome != nome) and rid and nome:
        repo.id_externo, repo.nome = rid, nome  # renomeado no GitHub: o id continua o mesmo
        repo.save(update_fields=["id_externo", "nome"])
    return repo


def _quando(texto):
    return parse_datetime(texto) if texto else None


def _pr(pr):
    estado = "merged" if pr.get("merged") else "closed" if pr.get("state") == "closed" else "draft" if pr.get("draft") else "open"
    return dict(tipo="pr", id_externo=str(pr["id"]), editavel=True,
                texto=" ".join([pr.get("title") or "", pr.get("body") or "", (pr.get("head") or {}).get("ref") or ""]),
                campos=dict(numero=pr.get("number"), url=pr["html_url"], titulo=(pr.get("title") or "")[:500], estado=estado,
                            autor_externo=((pr.get("user") or {}).get("login") or "")[:100], atualizado_no_provedor=_quando(pr.get("updated_at"))))


def _issue(issue):
    return dict(tipo="issue", id_externo=str(issue["id"]), editavel=True,
                texto=f"{issue.get('title') or ''} {issue.get('body') or ''}",
                campos=dict(numero=issue.get("number"), url=issue["html_url"], titulo=(issue.get("title") or "")[:500],
                            estado=issue.get("state") or "", autor_externo=((issue.get("user") or {}).get("login") or "")[:100],
                            atualizado_no_provedor=_quando(issue.get("updated_at"))))


def _commit(c):
    autor = c.get("author") or {}
    return dict(tipo="commit", id_externo=c["id"], editavel=False, texto=c.get("message") or "",
                campos=dict(numero=None, url=c["url"], titulo=(c.get("message") or "").split("\n")[0][:500], estado="",
                            autor_externo=(autor.get("username") or autor.get("name") or "")[:100], atualizado_no_provedor=_quando(c.get("timestamp"))))


def _aplicar(ev):
    p = ev.payload
    if ev.evento not in EVENTOS:
        return EventoProvedor.IGNORADO  # ping e eventos que a Vetor não usa
    repo = _repositorio(p.get("repository") or {})
    if repo is None:
        return EventoProvedor.IGNORADO  # repositório não ligado a nenhum projeto
    ev.repositorio = repo
    itens = {"pull_request": lambda: [_pr(p["pull_request"])], "issues": lambda: [_issue(p["issue"])],
             "push": lambda: [_commit(c) for c in p.get("commits") or []]}[ev.evento]()
    for item in itens:
        _vincular(ev, repo, **item)
    return EventoProvedor.PROCESSADO


def _vincular(ev, repo, tipo, id_externo, texto, editavel, campos):
    do_objeto = VinculoCodigo.objects.filter(repositorio=repo, tipo=tipo, id_externo=id_externo)
    quando = campos["atualizado_no_provedor"]
    if quando and do_objeto.filter(atualizado_no_provedor__gt=quando).exists():
        return  # entrega antiga chegando depois de uma mais nova: não volta o estado
    # limitação conhecida: se todas as citações já foram removidas, uma entrega antiga atrasada recria o vínculo; raro, apagar à mão.
    # Só histórias do projeto do repositório: citar TG-<ref> não liga código a projeto alheio.
    historias = list(UserStory.objects.filter(project_id=repo.projeto_id, ref__in={int(n) for n in REF.findall(texto)}))
    for us in historias:
        VinculoCodigo.objects.update_or_create(historia=us, tipo=tipo, id_externo=id_externo,
                                               defaults={**campos, "repositorio": repo, "evento": ev})
    if editavel:  # título ou descrição editados: a história que deixou de ser citada perde o vínculo
        do_objeto.exclude(historia__in=historias).delete()
