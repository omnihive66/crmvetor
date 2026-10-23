"""Operação, pós-venda e adoção (SPEC-08): ingestão de uso pseudonimizada e o painel do cliente com sinais separados.

Nada aqui vira nota única: relacionamento, disponibilidade (queda), infraestrutura (limites como CPU) e adoção são
indicadores distintos. Sem eventos = "sem dados"; ausência de eventos nunca vira desuso nem falha por si só.
"""
import datetime
import hashlib
import hmac
import re

from django.conf import settings
from django.db.models import Count, Max
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from taiga.base import exceptions as exc
from taiga.projects.userstories.models import UserStory

from . import clientes as regras
from . import permissoes
from .lembretes import FUSO
from .models import EventoUso, Incidente, ProjetoCliente, RecursoMonitorado
from .monitoramento import NOMES

CAMPOS_EVENTO = {"id", "tipo", "funcionalidade", "usuario", "ocorrido_em", "sintetico", "client_id", "product_id"}
FUNCIONALIDADE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,59}$")
MAX_LOTE = 500
TELEMETRIA_RECENTE = datetime.timedelta(days=2)  # sem nenhum evento (nem pulso) há 2 dias: não dá para afirmar desuso


def _pseudonimo(produto, usuario):
    """Cifra de novo o pseudônimo do produto com chave do servidor e por produto: não cruza clientes nem produtos."""
    return hmac.new(settings.SECRET_KEY.encode(), f"{produto.id}:{usuario}".encode(), hashlib.sha256).hexdigest()


def ingerir(produto, corpo):
    eventos = corpo.get("eventos") if isinstance(corpo, dict) else None
    if not isinstance(eventos, list) or not 1 <= len(eventos) <= MAX_LOTE:
        raise exc.WrongArguments({"eventos": [f"Envie de 1 a {MAX_LOTE} eventos em \"eventos\"."]})
    agora, minimo = timezone.now(), timezone.now() - datetime.timedelta(days=settings.VETOR_USO_RETENCAO_DIAS)
    novos, erros = [], {}
    for i, ev in enumerate(eventos):
        problema = _validar_evento(produto, ev, agora, minimo)
        if problema:
            erros[str(i)] = problema
            continue
        novos.append(EventoUso(produto=produto, id_externo=str(ev["id"])[:100], tipo=ev["tipo"], funcionalidade=ev.get("funcionalidade") or "",
                               usuario=_pseudonimo(produto, ev["usuario"]) if ev.get("usuario") else "",
                               ocorrido_em=parse_datetime(ev["ocorrido_em"]), sintetico=bool(ev.get("sintetico")) or produto.sintetico))
    if erros:  # lote inteiro recusado: o produto corrige e reenvia (ids repetidos não duplicam)
        raise exc.WrongArguments({"eventos": erros})
    ids = [n.id_externo for n in novos]
    existentes = set(produto.eventos.filter(id_externo__in=ids).values_list("id_externo", flat=True))
    EventoUso.objects.bulk_create([n for n in novos if n.id_externo not in existentes], ignore_conflicts=True)
    return {"recebidos": len(set(ids) - existentes), "duplicados": len(ids) - len(set(ids) - existentes)}


def _validar_evento(produto, ev, agora, minimo):
    if not isinstance(ev, dict):
        return "Evento precisa ser um objeto."
    if extras := set(ev) - CAMPOS_EVENTO:  # minimização: nada de conteúdo, mensagens ou credenciais
        return f"Campos não aceitos: {', '.join(sorted(extras))}. Aceitos: {', '.join(sorted(CAMPOS_EVENTO))}."
    if ev.get("product_id") not in (None, produto.chave) or ev.get("client_id") not in (None, produto.cliente_id, str(produto.cliente_id)):
        return "client_id/product_id não correspondem ao token."
    if not ev.get("id") or len(str(ev["id"])) > 100:
        return "id obrigatório (até 100 caracteres), único por evento."
    if ev.get("tipo") not in (EventoUso.LOGIN, EventoUso.ATIVIDADE, EventoUso.PULSO):
        return "tipo deve ser login, atividade ou pulso."
    if ev["tipo"] == EventoUso.ATIVIDADE and not FUNCIONALIDADE.match(str(ev.get("funcionalidade") or "")):
        return "atividade exige funcionalidade (identificador curto, ex.: emitir_nota)."
    usuario = ev.get("usuario")
    if ev["tipo"] != EventoUso.PULSO and (not isinstance(usuario, str) or not 8 <= len(usuario) <= 128 or "@" in usuario):
        return "usuario deve ser um pseudônimo (8 a 128 caracteres), nunca e-mail ou nome."
    quando = parse_datetime(str(ev.get("ocorrido_em") or ""))
    if quando is None or quando.tzinfo is None:
        return "ocorrido_em em ISO 8601 com fuso."
    if quando > agora + datetime.timedelta(minutes=5) or quando < minimo:
        return "ocorrido_em fora do intervalo aceito (futuro ou além da retenção)."
    return None


def limpar_uso(agora=None):
    limite = (agora or timezone.now()) - datetime.timedelta(days=settings.VETOR_USO_RETENCAO_DIAS)
    return EventoUso.objects.filter(ocorrido_em__lt=limite).delete()[0]


def adocao(produto, agora=None):
    agora = agora or timezone.now()
    eventos = produto.eventos.all()
    base = {"produto": {"id": produto.id, "nome": produto.nome}, "sintetico": produto.sintetico or eventos.filter(sintetico=True).exists(),
            "janela_dias": produto.janela_ativos_dias, "fuso": "America/Sao_Paulo", "revogado": bool(produto.revogado_em),
            "config": {"alerta_desuso_dias": produto.alerta_desuso_dias, "excecao_ate": produto.alerta_excecao_ate, "motivo": produto.alerta_excecao_motivo}}
    ultimo_recebido = eventos.aggregate(m=Max("recebido_em"))["m"]
    if ultimo_recebido is None:
        return {**base, "situacao": "sem_dados"}
    inicio = datetime.datetime.combine(agora.astimezone(FUSO).date() - datetime.timedelta(days=produto.janela_ativos_dias - 1),
                                       datetime.time.min, tzinfo=FUSO)
    na_janela = eventos.filter(ocorrido_em__gte=inicio, ocorrido_em__lte=agora)
    atividade = na_janela.filter(tipo=EventoUso.ATIVIDADE)
    ultimo_login = eventos.filter(tipo=EventoUso.LOGIN).aggregate(m=Max("ocorrido_em"))["m"]
    ultima_atividade = eventos.filter(tipo=EventoUso.ATIVIDADE).aggregate(m=Max("ocorrido_em"))["m"]
    return {**base, "situacao": "com_dados", "janela_inicio": inicio, "atualizado_em": ultimo_recebido,
            "ultimo_acesso": {"em": ultimo_login, "origem": f"login no produto {produto.nome}"} if ultimo_login else None,
            "ultima_atividade": ultima_atividade,
            "usuarios_ativos": atividade.exclude(usuario="").values("usuario").distinct().count(),
            "logins_na_janela": na_janela.filter(tipo=EventoUso.LOGIN).count(),  # separado de atividade efetiva
            "funcionalidades": list(atividade.values("funcionalidade").annotate(eventos=Count("id"), usuarios=Count("usuario", distinct=True))
                                    .order_by("-eventos")[:10]),
            "alerta": _alerta(produto, agora, ultimo_recebido, ultima_atividade)}


def _alerta(produto, agora, ultimo_recebido, ultima_atividade):
    if not produto.alerta_desuso_dias:
        return {"codigo": "desligado"}
    if produto.alerta_excecao_ate and produto.alerta_excecao_ate >= agora.astimezone(FUSO).date():
        return {"codigo": "em_excecao", "ate": produto.alerta_excecao_ate, "motivo": produto.alerta_excecao_motivo}
    if agora - ultimo_recebido > TELEMETRIA_RECENTE:
        return {"codigo": "telemetria_parada"}  # silêncio do produto não é desuso
    if ultima_atividade is None or agora - ultima_atividade > datetime.timedelta(days=produto.alerta_desuso_dias):
        return {"codigo": "possivel_desuso", "dias": produto.alerta_desuso_dias}
    return {"codigo": "ok"}


def painel(cliente, user):
    """Só dados deste cliente, e só dos projetos dele que a pessoa vê."""
    vinculados = ProjetoCliente.objects.filter(cliente=cliente).values("project_id")
    projetos = vinculados if permissoes.e_administrador(user) else regras.projetos_visiveis(user).filter(id__in=vinculados).values("id")
    hoje = timezone.now().astimezone(FUSO).date()
    abertas = UserStory.objects.filter(project__in=projetos, status__is_closed=False)
    ultima = cliente.reunioes.first()
    recursos = list(RecursoMonitorado.objects.filter(projeto__in=projetos).select_related("projeto"))
    desde = timezone.now() - datetime.timedelta(days=30)
    incidentes = Incidente.objects.filter(recurso__in=recursos)
    from .api_monitoramento import estado_conector
    conectores = {p: estado_conector(p)["telemetria"] for p in {r.provedor for r in recursos}}

    def situacao(r):
        """Só disponibilidade: um alerta de CPU aberto não é "fora do ar" (spec: queda ≠ CPU alta)."""
        if conectores[r.provedor] == "indisponivel":
            return {"codigo": "telemetria_indisponivel"}
        if incidentes.filter(recurso=r, tipo="disponibilidade", estado=Incidente.ABERTO).exists():
            return {"codigo": "fora_do_ar"}
        ultimo = r.eventos.filter(tipo="disponibilidade").order_by("-ocorrido_em").first()
        return {"codigo": "ultimo_evento", "status": ultimo.status, "em": ultimo.ocorrido_em} if ultimo else {"codigo": "sem_dados"}
    return {
        "relacionamento": {
            "ultima_reuniao": {"id": ultima.id, "data": ultima.data, "proximos_passos": ultima.proximos_passos} if ultima else None,
            "proximo_contato": cliente.proximo_contato,
            "pendencias": {"abertas": abertas.count(), "bloqueadas": abertas.filter(is_blocked=True).count(),
                           "vencidas": abertas.filter(due_date__lt=hoje).count()}},
        "disponibilidade": [
            {"recurso": r.nome, "fonte": NOMES[r.provedor],
             "situacao": situacao(r),
             "quedas_abertas": incidentes.filter(recurso=r, tipo="disponibilidade", estado=Incidente.ABERTO).count(),
             "quedas_30d": incidentes.filter(recurso=r, tipo="disponibilidade", aberto_em__gte=desde).count()} for r in recursos],
        "infraestrutura": [
            {"recurso": i.recurso.nome, "metrica": i.tipo.removeprefix("limite:"), "estado": i.estado, "fonte": NOMES[i.recurso.provedor],
             "aberto_em": i.aberto_em, "ultimo_evento_em": i.ultimo_evento_em}
            for i in incidentes.filter(tipo__startswith="limite:", aberto_em__gte=desde).select_related("recurso")[:20]],
        "adocao": [adocao(p) for p in cliente.produtos_telemetria.all()],
    }
