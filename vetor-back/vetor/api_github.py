"""Repositórios dos projetos, vínculos de código nas histórias e fila de entregas do GitHub (SPEC-06)."""
import re

from taiga.base import exceptions as exc
from taiga.base import response
from taiga.base.api import serializers
from taiga.base.decorators import detail_route
from taiga.base.fields import Field, MethodField

from . import clientes as regras
from . import github
from .api import SomenteAdministrador
from .api_clientes import BaseVetor, _autenticado
from .auditoria import registrar
from .models import EventoProvedor, Repositorio, VinculoCodigo

NOME_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class RepositorioSerializer(serializers.LightSerializer):
    id = Field()
    provedor = Field()
    nome = Field()
    url = MethodField()
    projeto = MethodField()
    vinculos = MethodField()
    criado_em = Field()

    def get_url(self, obj):
        return f"https://github.com/{obj.nome}"

    def get_projeto(self, obj):
        return {"id": obj.projeto_id, "nome": obj.projeto.name, "slug": obj.projeto.slug}

    def get_vinculos(self, obj):
        return obj.vinculos.count()


class RepositorioViewSet(SomenteAdministrador, BaseVetor):
    """Ligar repositório a projeto é decisão do Administrador, como os webhooks (SPEC-02)."""
    serializer_class = RepositorioSerializer
    paginate_by = 100

    def get_queryset(self):
        return Repositorio.objects.select_related("projeto")

    def create(self, request, **kwargs):
        self.check_permissions(request, "create")
        nome = (request.DATA.get("nome") or "").strip().removeprefix("https://github.com/").strip("/")
        if not NOME_REPO.match(nome):
            raise exc.WrongArguments({"nome": ["Use dono/repositório, como aparece no GitHub."]})
        projeto = regras.projetos_visiveis(request.user).filter(pk=request.DATA.get("projeto")).first()
        if projeto is None:
            raise exc.WrongArguments({"projeto": ["Projeto não encontrado."]})
        if Repositorio.objects.filter(provedor="github", nome__iexact=nome).exists():
            raise exc.WrongArguments({"nome": ["Este repositório já está ligado a um projeto."]})
        repo = Repositorio.objects.create(projeto=projeto, nome=nome, criado_por=request.user)
        registrar("repositorio.ligado", repo, projeto=projeto.id, nome=nome)
        return response.Created(self.get_serializer(repo).data)

    def destroy(self, request, pk=None, **kwargs):
        self.check_permissions(request, "destroy")
        repo = self.objeto(pk)
        registrar("repositorio.desligado", repo, projeto=repo.projeto_id, nome=repo.nome)
        repo.delete()  # leva os vínculos; as entregas ficam, sem repositório
        return response.NoContent()


class VinculoSerializer(serializers.LightSerializer):
    id = Field()
    tipo = Field()
    numero = Field()
    id_externo = Field()
    url = Field()
    titulo = Field()
    estado = Field()
    autor_externo = Field()
    atualizado_no_provedor = Field()
    repositorio = Field(attr="repositorio.nome")


class VinculoViewSet(BaseVetor):
    """Quem vê a história vê os links; o link não dá acesso ao repositório (o GitHub decide isso)."""
    serializer_class = VinculoSerializer
    paginate_by = 200

    def get_queryset(self):
        user = self.request.user
        historia = self.request.QUERY_PARAMS.get("historia")
        if not user.is_authenticated or not str(historia or "").isdigit():
            return VinculoCodigo.objects.none()
        return VinculoCodigo.objects.filter(historia_id=historia, historia__project__in=regras.projetos_visiveis(user, "view_us").values("id")
                                            ).select_related("repositorio")


class EventoSerializer(serializers.LightSerializer):
    id = Field()
    entrega = Field()
    evento = Field()
    status = Field()
    tentativas = Field()
    erro = Field()
    repositorio = MethodField()
    recebido_em = Field()
    processado_em = Field()

    def get_repositorio(self, obj):
        return obj.repositorio.nome if obj.repositorio_id else (obj.payload.get("repository") or {}).get("full_name")


class EventoViewSet(SomenteAdministrador, BaseVetor):
    """Fila de entregas (o payload não sai pela API; fica no banco para reprocessar)."""
    serializer_class = EventoSerializer
    paginate_by = 50

    def get_queryset(self):
        qs = EventoProvedor.objects.select_related("repositorio")
        status = self.request.QUERY_PARAMS.get("status")
        return qs.filter(status=status) if status else qs

    @detail_route(methods=["POST"])
    def reprocessar(self, request, pk=None):
        self.check_permissions(request, "reprocessar")
        ev = self.objeto(pk)
        if ev.status != EventoProvedor.FALHOU:
            raise exc.WrongArguments({"status": ["Só entregas com falha podem ser reprocessadas."]})
        return response.Ok(self.get_serializer(github.processar(ev.id)).data)
