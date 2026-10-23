"""Incidentes, triagem de recursos e diagnóstico dos conectores de monitoramento (SPEC-07)."""
import datetime

from django.conf import settings
from django.db.models import Max
from django.utils import timezone

from taiga.base import exceptions as exc
from taiga.base import response
from taiga.base.api import serializers
from taiga.base.decorators import detail_route, list_route
from taiga.base.fields import Field, MethodField
from taiga.projects.models import Project

from . import clientes as regras
from . import monitoramento, permissoes
from .api import SomenteAdministrador
from .api_clientes import BaseVetor, _autenticado
from .auditoria import registrar
from .models import EventoMonitoramento, Incidente, RecursoMonitorado


def estado_conector(provedor):
    """Telemetria indisponível se não configurado, sem nenhuma entrega ou com falha mais nova que o último sucesso.
    Silêncio não vira "no ar": Kuma e Beszel só avisam mudanças."""
    eventos = EventoMonitoramento.objects.filter(provedor=provedor)
    ok = eventos.filter(processamento=EventoMonitoramento.PROCESSADO).aggregate(m=Max("recebido_em"))["m"]
    falha = eventos.filter(processamento=EventoMonitoramento.FALHOU).aggregate(m=Max("recebido_em"))["m"]
    configurado = bool(settings.VETOR_MONITOR_TOKENS.get(provedor))
    disponivel = configurado and ok is not None and (falha is None or falha < ok)
    return {"provedor": provedor, "nome": monitoramento.NOMES[provedor], "configurado": configurado,
            "telemetria": "disponivel" if disponivel else "indisponivel", "ultimo_sucesso": ok, "ultima_falha": falha,
            "recebidos_24h": eventos.filter(recebido_em__gte=timezone.now() - datetime.timedelta(hours=24)).count(),
            "falhas_pendentes": eventos.filter(processamento=EventoMonitoramento.FALHOU).count(),
            "em_triagem": RecursoMonitorado.objects.filter(provedor=provedor, projeto__isnull=True).count(),
            "incidentes_abertos": Incidente.objects.filter(recurso__provedor=provedor, estado=Incidente.ABERTO).count()}


def _projeto(p):
    return {"id": p.id, "nome": p.name, "slug": p.slug} if p else None


class IncidenteSerializer(serializers.LightSerializer):
    id = Field()
    tipo = Field()
    estado = Field()
    severidade = Field()
    resumo = Field()
    aberto_em = Field()
    recuperado_em = Field()
    ocorrencias = Field()
    reincidencias = Field()
    recurso = MethodField()
    demanda = MethodField()

    def get_recurso(self, obj):
        r = obj.recurso
        return {"id": r.id, "nome": r.nome, "provedor": monitoramento.NOMES[r.provedor], "projeto": _projeto(r.projeto)}

    def get_demanda(self, obj):
        us = obj.historia
        return {"ref": us.ref, "projeto": us.project.slug, "assunto": us.subject} if us else None


class EventoSerializer(serializers.LightSerializer):
    id = Field()
    provedor = Field()
    id_recurso = Field()
    tipo = Field()
    status = Field()
    severidade = Field()
    resumo = Field()
    url_origem = Field()
    ocorrido_em = Field()
    recebido_em = Field()
    processamento = Field()
    tentativas = Field()
    erro = Field()


class IncidenteViewSet(BaseVetor):
    """Quem vê o projeto vê os incidentes dele; incidentes de recurso em triagem só o Administrador."""
    serializer_class = IncidenteSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Incidente.objects.none()
        qs = Incidente.objects.select_related("recurso__projeto", "historia__project")
        if not permissoes.e_administrador(user):
            qs = qs.filter(recurso__projeto__in=regras.projetos_visiveis(user).values("id"))
        estado = self.request.QUERY_PARAMS.get("estado")
        return qs.filter(estado=estado) if estado else qs

    def retrieve(self, request, pk=None, **kwargs):
        _autenticado(request)
        inc = self.objeto(pk)
        linha = EventoSerializer(inc.eventos.order_by("ocorrido_em", "id"), many=True).data
        return response.Ok({**self.get_serializer(inc).data, "linha_do_tempo": linha})


class RecursoSerializer(serializers.LightSerializer):
    id = Field()
    provedor = Field()
    id_externo = Field()
    nome = Field()
    projeto = MethodField()
    situacao = MethodField()

    def get_projeto(self, obj):
        return _projeto(obj.projeto)

    def get_situacao(self, obj):
        """Nunca "100% no ar": só o que os eventos dizem, e telemetria indisponível quando o conector falha."""
        conectores = self.__dict__.setdefault("_conectores", {})  # uma consulta por provedor na listagem
        if obj.provedor not in conectores:
            conectores[obj.provedor] = estado_conector(obj.provedor)["telemetria"]
        if conectores[obj.provedor] == "indisponivel":
            return {"codigo": "telemetria_indisponivel"}
        if obj.incidentes.filter(estado=Incidente.ABERTO).exists():
            return {"codigo": "incidente_aberto"}
        ultimo = obj.eventos.exclude(status="info").order_by("-ocorrido_em").first()
        return {"codigo": "ultimo_evento", "status": ultimo.status, "em": ultimo.ocorrido_em} if ultimo else {"codigo": "sem_dados"}


class RecursoViewSet(SomenteAdministrador, BaseVetor):
    """Mapear recurso → projeto é explícito e do Administrador; sem mapeamento, o recurso fica em triagem."""
    serializer_class = RecursoSerializer
    paginate_by = 100

    def get_queryset(self):
        qs = RecursoMonitorado.objects.select_related("projeto")
        return qs.filter(projeto__isnull=True) if self.request.QUERY_PARAMS.get("triagem") == "true" else qs

    def partial_update(self, request, pk=None, **kwargs):
        self.check_permissions(request, "partial_update")
        recurso = self.objeto(pk)
        pid = request.DATA.get("projeto")
        projeto = Project.objects.filter(pk=pid).first() if str(pid or "").isdigit() else None
        if pid not in (None, "") and projeto is None:
            raise exc.WrongArguments({"projeto": ["Projeto não encontrado."]})
        antes = recurso.projeto_id
        monitoramento.mapear(recurso, projeto)
        registrar("recurso_monitorado.mapeado", recurso, antes=antes, projeto=projeto.id if projeto else None)
        return response.Ok(self.get_serializer(recurso).data)


class EventoMonitoramentoViewSet(SomenteAdministrador, BaseVetor):
    serializer_class = EventoSerializer
    paginate_by = 50

    def get_queryset(self):
        qs = EventoMonitoramento.objects.order_by("-recebido_em")
        proc = self.request.QUERY_PARAMS.get("processamento")
        return qs.filter(processamento=proc) if proc else qs

    @list_route(methods=["GET"])
    def diagnostico(self, request, **kwargs):
        self.check_permissions(request, "diagnostico")
        return response.Ok({"conectores": [estado_conector(p) for p in monitoramento.NOMES],
                            "janela_min": settings.VETOR_MONITOR_JANELA_MIN, "aviso_min": settings.VETOR_MONITOR_AVISO_MIN,
                            "retencao_dias": settings.VETOR_MONITOR_RETENCAO_DIAS,
                            "disponibilidade_historica": "não calculada: os provedores só avisam mudanças, sem amostras contínuas (decisão 0010)"})

    @detail_route(methods=["POST"])
    def reprocessar(self, request, pk=None):
        self.check_permissions(request, "reprocessar")
        ev = self.objeto(pk)
        if ev.processamento != EventoMonitoramento.FALHOU:
            raise exc.WrongArguments({"processamento": ["Só eventos com falha podem ser reprocessados."]})
        return response.Ok(self.get_serializer(monitoramento.processar(ev.id)).data)
