"""Demandas de vários projetos com filtros e participação por etapa (SPEC-04)."""
import datetime

from django.db.models import Q
from django.utils import timezone

from taiga.base import exceptions as exc
from taiga.base import response
from taiga.base.api import serializers
from taiga.base.fields import Field, MethodField
from taiga.projects.userstories.models import UserStory

from . import clientes as regras
from .api_clientes import BaseVetor, _autenticado, _nome
from .models import ParticipacaoEtapa


class DemandaSerializer(serializers.LightSerializer):
    id = Field()
    ref = Field()
    version = Field()  # para mover com controle de concorrência (OCC do Taiga)
    assunto = Field(attr="subject")
    projeto = MethodField()
    cliente = MethodField()
    etapa = MethodField()
    responsavel = MethodField()
    colaboradores = MethodField()
    prazo = Field(attr="due_date")
    bloqueada = Field(attr="is_blocked")
    motivo_bloqueio = Field(attr="blocked_note")
    atualizada_em = Field(attr="modified_date")

    def get_projeto(self, us):
        return {"id": us.project_id, "nome": us.project.name, "slug": us.project.slug}

    def get_cliente(self, us):
        vinculo = getattr(us.project, "vetor_cliente", None)
        return {"id": vinculo.cliente_id, "nome": vinculo.cliente.nome} if vinculo else None

    def get_etapa(self, us):
        return {"id": us.status_id, "nome": us.status.name, "cor": us.status.color, "concluida": us.status.is_closed} if us.status_id else None

    def get_responsavel(self, us):
        return {"id": us.assigned_to_id, "nome": _nome(us.assigned_to)} if us.assigned_to_id else None

    def get_colaboradores(self, us):
        return [{"id": u.id, "nome": _nome(u)} for u in us.assigned_users.all() if u.id != us.assigned_to_id]


class DemandaViewSet(BaseVetor):
    """Histórias dos projetos onde a pessoa tem view_us. Filtros: cliente, projeto, responsavel
    (principal ou colaborador), prazo (vencidas|7dias|sem), bloqueadas, concluidas."""
    serializer_class = DemandaSerializer

    def get_queryset(self):
        user, p = self.request.user, self.request.QUERY_PARAMS
        qs = (UserStory.objects.filter(project__in=regras.projetos_visiveis(user, "view_us").values("id"))
              .select_related("project__vetor_cliente__cliente", "status", "assigned_to").prefetch_related("assigned_users")
              .order_by("due_date", "-modified_date", "id"))
        if p.get("concluidas") != "true":
            qs = qs.filter(status__is_closed=False)
        if p.get("cliente"):
            qs = qs.filter(project__vetor_cliente__cliente_id=p.get("cliente"))
        if p.get("projeto"):
            qs = qs.filter(project_id=p.get("projeto"))
        if p.get("responsavel"):
            qs = qs.filter(Q(assigned_to_id=p.get("responsavel")) | Q(assigned_users=p.get("responsavel"))).distinct()
        hoje = timezone.localdate()
        prazo = p.get("prazo")
        if prazo == "vencidas":
            qs = qs.filter(due_date__lt=hoje)
        elif prazo == "7dias":
            qs = qs.filter(due_date__gte=hoje, due_date__lte=hoje + datetime.timedelta(days=7))
        elif prazo == "sem":
            qs = qs.filter(due_date__isnull=True)
        elif prazo:
            raise exc.WrongArguments({"prazo": ["Use vencidas, 7dias ou sem."]})
        if p.get("bloqueadas") == "true":
            qs = qs.filter(is_blocked=True)
        return qs


class ParticipacaoSerializer(serializers.LightSerializer):
    usuario = Field(attr="usuario_id")
    usuario_nome = Field()
    etapa = Field(attr="status_nome")
    inicio = Field()
    fim = Field()
    autor_inicio = Field()
    autor_fim = Field()


class ParticipacaoViewSet(BaseVetor):
    serializer_class = ParticipacaoSerializer
    paginate_by = 200

    def get_queryset(self):
        historia = self.request.QUERY_PARAMS.get("historia")
        if not historia:
            raise exc.WrongArguments({"historia": ["Informe a história."]})
        visiveis = regras.projetos_visiveis(self.request.user, "view_us").values("id")
        return ParticipacaoEtapa.objects.filter(historia_id=historia, historia__project__in=visiveis)
