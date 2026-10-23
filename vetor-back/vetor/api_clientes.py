"""API do CRM (SPEC-03): clientes, contatos, documentos, reuniões e busca global."""
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from django.db import transaction
from django.db.models import Q
from django.utils.dateparse import parse_date, parse_datetime

from taiga.base import exceptions as exc
from taiga.base import response
from taiga.base.api import GenericViewSet, serializers
from taiga.base.api.mixins import ListModelMixin
from taiga.base.decorators import detail_route, list_route
from taiga.base.fields import Field, MethodField
from taiga.permissions.services import is_project_admin, user_has_perm
from taiga.projects.history.services import take_snapshot
from taiga.projects.userstories.models import UserStory

from . import clientes as regras
from . import permissoes
from .api import TransacaoNaEscrita
from .auditoria import registrar
from .models import Auditoria, Cliente, Contato, Documento, ProjetoCliente, Reuniao


def _texto(data, campo, max_len, obrigatorio=False):
    valor = (data.get(campo) or "").strip()
    if obrigatorio and not valor:
        raise exc.WrongArguments({campo: ["Campo obrigatório."]})
    if len(valor) > max_len:
        raise exc.WrongArguments({campo: [f"Máximo de {max_len} caracteres."]})
    return valor


def _autenticado(request):
    if not request.user.is_authenticated:
        raise exc.NotAuthenticated()


def _ids_visiveis(user):
    return set(regras.projetos_visiveis(user).values_list("id", flat=True)) if user.is_authenticated else set()


def _nome(user):
    return (user.get_full_name() or user.username) if user else None


class BaseVetor(TransacaoNaEscrita, ListModelMixin, GenericViewSet):
    permission_classes = ()  # as regras ficam em vetor.clientes
    paginate_by = 30

    def list(self, request, *args, **kwargs):
        _autenticado(request)
        return super().list(request, *args, **kwargs)

    def objeto(self, pk):
        obj = self.get_queryset().filter(pk=pk).first()
        if obj is None:
            raise exc.NotFound()
        return obj


# Clientes -----------------------------------------------------------------------------------

class ClienteSerializer(serializers.LightSerializer):
    id = Field()
    nome = Field()
    razao_social = Field()
    cnpj = Field()
    estrangeiro = Field()
    documento_estrangeiro = Field()
    cidade = Field()
    uf = Field()
    pais = Field()
    responsavel = Field(attr="responsavel_id")
    responsavel_nome = MethodField()
    ciclo = Field()
    codigo_financeiro = Field()
    proximo_contato = Field()
    observacoes = Field()
    arquivado = Field()
    criado_em = Field()
    atualizado_em = Field()
    projetos = MethodField()
    pode_editar = MethodField()

    def get_responsavel_nome(self, obj):
        return _nome(obj.responsavel)

    def get_projetos(self, obj):
        # Só os projetos que quem pergunta consegue ver: o nome de um projeto alheio não aparece.
        visiveis = self.context["projetos_visiveis"]
        return [{"id": p.project_id, "nome": p.project.name, "slug": p.project.slug}
                for p in obj.projetos.all() if p.project_id in visiveis]

    def get_pode_editar(self, obj):
        return self.context["pode_editar"]


CAMPOS_CLIENTE = {"nome": 200, "razao_social": 255, "documento_estrangeiro": 60, "cidade": 120,
                  "pais": 60, "codigo_financeiro": 60, "observacoes": 10000}


class ClienteViewSet(BaseVetor):
    serializer_class = ClienteSerializer

    def get_queryset(self):
        qs = regras.clientes_visiveis(self.request.user).select_related("responsavel").prefetch_related("projetos__project")
        p = self.request.QUERY_PARAMS
        if self.action == "list":
            q = (p.get("q") or "").strip()
            if q:
                digitos = regras.normalizar_cnpj(q)
                qs = qs.filter(Q(nome__icontains=q) | Q(razao_social__icontains=q) | (Q(cnpj__startswith=digitos) if len(digitos) >= 3 else Q(pk__in=[])))
            if p.get("responsavel"):
                qs = qs.filter(responsavel_id=p.get("responsavel"))
            if p.get("ciclo"):
                qs = qs.filter(ciclo=p.get("ciclo"))
            qs = qs.filter(arquivado=p.get("arquivados") == "true")
        return qs

    def get_extra_context(self):
        user = self.request.user
        return {**super().get_extra_context(), "pode_editar": regras.pode_criar_cliente(user),
                "projetos_visiveis": _ids_visiveis(user)}

    def _validar(self, data, cliente=None):
        dados = {k: _texto(data, k, n, obrigatorio=(k == "nome" and (cliente is None or "nome" in data)))
                 for k, n in CAMPOS_CLIENTE.items() if cliente is None or k in data}
        if cliente is None or "uf" in data:
            dados["uf"] = _texto(data, "uf", 2).upper()
        if "estrangeiro" in data or cliente is None:
            dados["estrangeiro"] = bool(data.get("estrangeiro", False))
        estrangeiro = dados.get("estrangeiro", cliente.estrangeiro if cliente else False)
        if "cnpj" in data or cliente is None:
            cnpj = regras.normalizar_cnpj(data.get("cnpj"))
            if cnpj and estrangeiro:
                raise exc.WrongArguments({"cnpj": ["Cliente estrangeiro não tem CNPJ; use o documento do país de origem."]})
            if cnpj and not regras.cnpj_valido(cnpj):
                raise exc.WrongArguments({"cnpj": ["CNPJ inválido (confira os dígitos)."]})
            if cnpj and Cliente.objects.filter(cnpj=cnpj).exclude(pk=getattr(cliente, "pk", None)).exists():
                raise exc.WrongArguments({"cnpj": ["Já existe um cliente com esse CNPJ."]})
            dados["cnpj"] = cnpj
        if "ciclo" in data or cliente is None:
            ciclo = data.get("ciclo") or Cliente.NEGOCIACAO
            if ciclo not in dict(Cliente.CICLOS):
                raise exc.WrongArguments({"ciclo": ["Ciclo inválido."]})
            dados["ciclo"] = ciclo
        if "responsavel" in data:
            rid = data.get("responsavel")
            if rid and not get_user_model().objects.filter(pk=rid, is_active=True, is_system=False).exists():
                raise exc.WrongArguments({"responsavel": ["Pessoa inválida ou inativa."]})
            dados["responsavel_id"] = rid or None
        if "proximo_contato" in data:
            bruto = data.get("proximo_contato")
            try:
                dados["proximo_contato"] = parse_date(bruto) if bruto else None
            except ValueError:  # bem formada mas inexistente (30/02)
                dados["proximo_contato"] = None
            if bruto and dados["proximo_contato"] is None:
                raise exc.WrongArguments({"proximo_contato": ["Use a data no formato AAAA-MM-DD."]})
        if "arquivado" in data and cliente is not None:
            dados["arquivado"] = bool(data["arquivado"])
        return dados

    def retrieve(self, request, pk=None, **kwargs):
        _autenticado(request)
        return response.Ok(self.get_serializer(self.objeto(pk)).data)

    @detail_route(methods=["GET"])
    def painel(self, request, pk=None):
        _autenticado(request)
        from . import operacao
        return response.Ok(operacao.painel(self.objeto(pk), request.user))

    def create(self, request, **kwargs):
        _autenticado(request)
        if not regras.pode_criar_cliente(request.user):
            raise exc.PermissionDenied("Só gestores e administradores cadastram clientes.")
        dados = self._validar(request.DATA)
        dados.setdefault("responsavel_id", request.user.id)
        parecidos = Cliente.objects.filter(nome__iexact=dados["nome"])
        if parecidos.exists() and not request.DATA.get("confirmar_duplicado"):
            # Mesmo nome não bloqueia (filiais, homônimos), mas pede confirmação explícita.
            raise exc.WrongArguments({"duplicado_possivel": [f"Já existe cliente chamado “{dados['nome']}”. Confirme para cadastrar mesmo assim."]})
        cliente = Cliente.objects.create(**dados)
        registrar("cliente.criado", cliente, nome=cliente.nome)
        return response.Created(self.get_serializer(cliente).data)

    def partial_update(self, request, pk=None, **kwargs):
        _autenticado(request)
        cliente = self.objeto(pk)
        regras.exigir_edicao(request.user, cliente)
        dados = self._validar(request.DATA, cliente)
        mudou = sorted(k for k, v in dados.items() if getattr(cliente, k) != v)
        for k, v in dados.items():
            setattr(cliente, k, v)
        cliente.save()
        if mudou:
            acao = {True: "cliente.arquivado", False: "cliente.reativado"}.get(dados.get("arquivado")) if mudou == ["arquivado"] else "cliente.alterado"
            registrar(acao, cliente, campos=mudou)
        return response.Ok(self.get_serializer(self.objeto(pk)).data)

    def destroy(self, request, pk=None, **kwargs):
        _autenticado(request)
        cliente = self.objeto(pk)
        regras.exigir_edicao(request.user, cliente)
        if cliente.projetos.exists():
            raise exc.WrongArguments({"projetos": ["O cliente tem projetos vinculados e não pode ser excluído. Arquive o cliente ou desvincule os projetos antes."]})
        registrar("cliente.excluido", cliente, nome=cliente.nome)
        for doc in cliente.documentos.exclude(arquivo=""):
            transaction.on_commit(lambda f=doc.arquivo: f.delete(save=False))
        cliente.delete()
        return response.NoContent()

    @detail_route(methods=["POST"])
    def vincular_projeto(self, request, pk=None):
        _autenticado(request)
        cliente = self.objeto(pk)
        regras.exigir_edicao(request.user, cliente)
        projeto = regras.projetos_visiveis(request.user).filter(pk=request.DATA.get("projeto")).first()
        if projeto is None:
            raise exc.WrongArguments({"projeto": ["Projeto não encontrado."]})
        if not is_project_admin(request.user, projeto):
            raise exc.PermissionDenied("Só quem administra o projeto pode vinculá-lo a um cliente.")
        atual = ProjetoCliente.objects.filter(project=projeto).select_related("cliente").first()
        if atual and atual.cliente_id != cliente.id:
            raise exc.WrongArguments({"projeto": [f"O projeto já pertence ao cliente “{atual.cliente.nome}”. Desvincule antes."]})
        ProjetoCliente.objects.get_or_create(project=projeto, cliente=cliente)
        registrar("cliente.projeto_vinculado", cliente, projeto=projeto.id)
        return response.Ok(self.get_serializer(self.objeto(pk)).data)

    @detail_route(methods=["POST"])
    def desvincular_projeto(self, request, pk=None):
        _autenticado(request)
        cliente = self.objeto(pk)
        regras.exigir_edicao(request.user, cliente)
        vinculo = cliente.projetos.filter(project_id=request.DATA.get("projeto")).select_related("project").first()
        if vinculo is None:
            raise exc.WrongArguments({"projeto": ["Projeto não vinculado a este cliente."]})
        if not is_project_admin(request.user, vinculo.project):
            raise exc.PermissionDenied("Só quem administra o projeto pode desvinculá-lo.")
        vinculo.delete()
        registrar("cliente.projeto_desvinculado", cliente, projeto=vinculo.project_id)
        return response.Ok(self.get_serializer(self.objeto(pk)).data)

    @detail_route(methods=["GET"])
    def historico(self, request, pk=None):
        """Alterações do cliente e do que pertence a ele (auditoria), para quem vê o cliente."""
        _autenticado(request)
        cliente = self.objeto(pk)
        registros = Auditoria.objects.filter(Q(alvo_tipo="vetor.cliente", alvo_id=str(cliente.pk)) |
                                             Q(detalhes__cliente=cliente.pk))[:100]
        return response.Ok([{"ocorrido_em": a.ocorrido_em, "ator_nome": a.ator_nome, "acao": a.acao,
                             "campos": a.detalhes.get("campos"), "titulo": a.detalhes.get("titulo")} for a in registros])

    @list_route(methods=["GET"])
    def opcoes(self, request, **kwargs):
        """Listas para os formulários: pessoas ativas, ciclos, categorias e projetos que a pessoa administra."""
        _autenticado(request)
        pessoas = get_user_model().objects.filter(is_active=True, is_system=False).order_by("full_name", "username")
        administrados = [p for p in regras.projetos_visiveis(request.user).distinct().order_by("name") if is_project_admin(request.user, p)]
        vinculos = dict(ProjetoCliente.objects.filter(project__in=administrados).values_list("project_id", "cliente_id"))
        return response.Ok({
            "pessoas": [{"id": u.id, "nome": _nome(u)} for u in pessoas],
            "ciclos": [{"id": k, "nome": v} for k, v in Cliente.CICLOS],
            "categorias": [{"id": k, "nome": v} for k, v in Documento.CATEGORIAS],
            "projetos_administrados": [{"id": p.id, "nome": p.name, "cliente": vinculos.get(p.id)} for p in administrados],
            "pode_criar": regras.pode_criar_cliente(request.user),
            "sistema_financeiro": settings.VETOR_SISTEMA_FINANCEIRO,
        })


# Contatos -----------------------------------------------------------------------------------

class ContatoSerializer(serializers.LightSerializer):
    id = Field()
    cliente = Field(attr="cliente_id")
    nome = Field()
    funcao = Field()
    telefone = Field()
    email = Field()


class ContatoViewSet(BaseVetor):
    serializer_class = ContatoSerializer

    def get_queryset(self):
        qs = Contato.objects.filter(cliente__in=regras.clientes_visiveis(self.request.user))
        cliente = self.request.QUERY_PARAMS.get("cliente")
        return qs.filter(cliente_id=cliente) if cliente and self.action == "list" else qs

    def _validar(self, data, parcial=False):
        dados = {k: _texto(data, k, n, obrigatorio=(k == "nome" and (not parcial or "nome" in data)))
                 for k, n in {"nome": 200, "funcao": 120, "telefone": 40, "email": 254}.items() if not parcial or k in data}
        if dados.get("email"):
            try:
                validate_email(dados["email"])
            except ValidationError:
                raise exc.WrongArguments({"email": ["E-mail inválido."]})
        return dados

    def create(self, request, **kwargs):
        _autenticado(request)
        cliente = regras.clientes_visiveis(request.user).filter(pk=request.DATA.get("cliente")).first()
        if cliente is None:
            raise exc.WrongArguments({"cliente": ["Cliente não encontrado."]})
        regras.exigir_edicao(request.user, cliente)
        contato = Contato.objects.create(cliente=cliente, **self._validar(request.DATA))
        registrar("contato.criado", contato, cliente=cliente.id)
        return response.Created(self.get_serializer(contato).data)

    def partial_update(self, request, pk=None, **kwargs):
        _autenticado(request)
        contato = self.objeto(pk)
        regras.exigir_edicao(request.user, contato.cliente)
        dados = self._validar(request.DATA, parcial=True)
        mudou = sorted(k for k, v in dados.items() if getattr(contato, k) != v)
        Contato.objects.filter(pk=contato.pk).update(**dados)
        if mudou:
            registrar("contato.alterado", contato, cliente=contato.cliente_id, campos=mudou)
        return response.Ok(self.get_serializer(self.objeto(pk)).data)

    def destroy(self, request, pk=None, **kwargs):
        _autenticado(request)
        contato = self.objeto(pk)
        regras.exigir_edicao(request.user, contato.cliente)
        registrar("contato.removido", contato, cliente=contato.cliente_id)
        contato.delete()
        return response.NoContent()


# Documentos ---------------------------------------------------------------------------------

class DocumentoSerializer(serializers.LightSerializer):
    id = Field()
    cliente = Field(attr="cliente_id")
    projeto = Field(attr="projeto_id")
    titulo = Field()
    categoria = Field()
    versao = Field()
    nome_arquivo = MethodField()
    tamanho = Field()
    url = MethodField()
    url_externa = Field()
    origem_externa = Field()
    modelo_de = Field(attr="modelo_de_id")
    autor_nome = MethodField()
    criado_em = Field()

    def get_nome_arquivo(self, obj):
        return os.path.basename(obj.arquivo.name) if obj.arquivo else None

    def get_url(self, obj):
        # Link assinado e temporário (taiga-protected); nunca um caminho público.
        return obj.arquivo.url if obj.arquivo else None

    def get_autor_nome(self, obj):
        return _nome(obj.autor)


def _validar_upload(arquivo):
    limite = settings.VETOR_DOCUMENTO_MAX_MB * 1024 * 1024
    if arquivo.size > limite:
        raise exc.WrongArguments({"arquivo": [f"Arquivo maior que {settings.VETOR_DOCUMENTO_MAX_MB} MB."]})
    ext = os.path.splitext(arquivo.name)[1].lower().lstrip(".")
    if ext not in settings.VETOR_DOCUMENTO_EXTENSOES:
        raise exc.WrongArguments({"arquivo": ["Tipo de arquivo não permitido. Aceitos: " + ", ".join(settings.VETOR_DOCUMENTO_EXTENSOES) + "."]})


class DocumentoViewSet(BaseVetor):
    serializer_class = DocumentoSerializer

    def get_queryset(self):
        qs = regras.documentos_visiveis(self.request.user).select_related("autor")
        p = self.request.QUERY_PARAMS
        if self.action == "list":
            if p.get("cliente"):
                qs = qs.filter(cliente_id=p.get("cliente"))
            if p.get("projeto"):
                qs = qs.filter(projeto_id=p.get("projeto"))
        return qs

    def _projeto_do_cliente(self, cliente, projeto_id):
        if not projeto_id:
            return None
        vinculo = cliente.projetos.filter(project_id=projeto_id).select_related("project").first()
        if vinculo is None or not regras.projetos_visiveis(self.request.user).filter(pk=projeto_id).exists():
            raise exc.WrongArguments({"projeto": ["Projeto não vinculado a este cliente."]})
        return vinculo.project

    def retrieve(self, request, pk=None, **kwargs):
        _autenticado(request)
        return response.Ok(self.get_serializer(self.objeto(pk)).data)

    def create(self, request, **kwargs):
        _autenticado(request)
        data = request.DATA
        cliente = regras.clientes_visiveis(request.user).filter(pk=data.get("cliente")).first()
        if cliente is None:
            raise exc.WrongArguments({"cliente": ["Cliente não encontrado."]})
        regras.exigir_edicao(request.user, cliente)
        categoria = data.get("categoria") or "outro"
        if categoria not in dict(Documento.CATEGORIAS):
            raise exc.WrongArguments({"categoria": ["Categoria inválida."]})
        doc = Documento(cliente=cliente, projeto=self._projeto_do_cliente(cliente, data.get("projeto")),
                        titulo=_texto(data, "titulo", 200, obrigatorio=True), categoria=categoria,
                        versao=_texto(data, "versao", 20) or "1", autor=request.user)
        arquivo = request.FILES.get("arquivo")
        url = (data.get("url_externa") or "").strip()
        if bool(arquivo) == bool(url):
            raise exc.WrongArguments({"arquivo": ["Envie um arquivo ou informe um link externo (só um dos dois)."]})
        if arquivo:
            _validar_upload(arquivo)
            doc.arquivo, doc.tamanho = arquivo, arquivo.size
        else:
            try:
                URLValidator(schemes=["https"])(url)
            except ValidationError:
                raise exc.WrongArguments({"url_externa": ["Informe um link https:// válido."]})
            doc.url_externa = url
            doc.origem_externa = _texto(data, "origem_externa", 80, obrigatorio=True)
        doc.save()
        registrar("documento.adicionado", doc, cliente=cliente.id, titulo=doc.titulo, tipo="arquivo" if arquivo else "link")
        return response.Created(self.get_serializer(doc).data)

    def destroy(self, request, pk=None, **kwargs):
        _autenticado(request)
        doc = self.objeto(pk)
        regras.exigir_edicao(request.user, doc.cliente)
        registrar("documento.removido", doc, cliente=doc.cliente_id, titulo=doc.titulo)
        if doc.arquivo:
            transaction.on_commit(lambda f=doc.arquivo: f.delete(save=False))
        doc.delete()
        return response.NoContent()

    @detail_route(methods=["POST"])
    def copiar_como_modelo(self, request, pk=None):
        """Cópia explícita para outro cliente. Leva só o arquivo ou link e o título; nunca o projeto do
        cliente de origem. O conteúdo do arquivo não é alterado: quem copia revisa antes de usar."""
        _autenticado(request)
        origem = self.objeto(pk)
        regras.exigir_edicao(request.user, origem.cliente)
        destino = regras.clientes_visiveis(request.user).filter(pk=request.DATA.get("cliente")).first()
        if destino is None:
            raise exc.WrongArguments({"cliente": ["Cliente de destino não encontrado."]})
        regras.exigir_edicao(request.user, destino)
        if not request.DATA.get("confirmar"):
            raise exc.WrongArguments({"confirmar": ["Confirme a cópia: o arquivo vai para outro cliente e deve ser revisado."]})
        copia = Documento(cliente=destino, titulo=_texto(request.DATA, "titulo", 200) or origem.titulo, categoria="modelo",
                          versao="1", url_externa=origem.url_externa, origem_externa=origem.origem_externa,
                          modelo_de=origem, autor=request.user)
        if origem.arquivo:
            with origem.arquivo.open("rb") as f:
                copia.arquivo.save(os.path.basename(origem.arquivo.name), f, save=False)
            copia.tamanho = origem.tamanho
        copia.save()
        registrar("documento.copiado_como_modelo", copia, origem=origem.id, cliente_origem=origem.cliente_id, cliente=destino.id)
        return response.Created(self.get_serializer(copia).data)


# Reuniões -----------------------------------------------------------------------------------

class ReuniaoSerializer(serializers.LightSerializer):
    id = Field()
    cliente = Field(attr="cliente_id")
    data = Field()
    participantes_internos = MethodField()
    participantes_externos = Field()
    notas = Field()
    proximos_passos = Field()
    demandas = MethodField()
    autor_nome = MethodField()

    def get_participantes_internos(self, obj):
        return [{"id": u.id, "nome": _nome(u)} for u in obj.participantes_internos.all()]

    def get_demandas(self, obj):
        visiveis = self.context.get("projetos_visiveis", set())
        return [{"id": us.id, "ref": us.ref, "assunto": us.subject, "projeto": us.project.slug}
                for us in obj.demandas.select_related("project") if us.project_id in visiveis]

    def get_autor_nome(self, obj):
        return _nome(obj.autor)


class ReuniaoViewSet(BaseVetor):
    serializer_class = ReuniaoSerializer

    def get_queryset(self):
        qs = Reuniao.objects.filter(cliente__in=regras.clientes_visiveis(self.request.user)).prefetch_related("participantes_internos")
        cliente = self.request.QUERY_PARAMS.get("cliente")
        return qs.filter(cliente_id=cliente) if cliente and self.action == "list" else qs

    def get_extra_context(self):
        return {**super().get_extra_context(), "projetos_visiveis": _ids_visiveis(self.request.user)}

    def _validar(self, data, parcial=False):
        dados = {}
        if "data" in data or not parcial:
            quando = parse_datetime(data.get("data") or "")
            if quando is None or quando.tzinfo is None:
                raise exc.WrongArguments({"data": ["Informe data e hora com fuso (ISO 8601)."]})
            dados["data"] = quando
        for campo in ("participantes_externos", "notas", "proximos_passos"):
            if campo in data or not parcial:
                dados[campo] = _texto(data, campo, 20000)
        return dados

    def _participantes(self, reuniao, ids):
        if ids is None:
            return
        pessoas = get_user_model().objects.filter(pk__in=ids, is_system=False)
        if len(set(ids)) != pessoas.count():
            raise exc.WrongArguments({"participantes_internos": ["Pessoa inválida."]})
        reuniao.participantes_internos.set(pessoas)

    def retrieve(self, request, pk=None, **kwargs):
        _autenticado(request)
        return response.Ok(self.get_serializer(self.objeto(pk)).data)

    def create(self, request, **kwargs):
        _autenticado(request)
        cliente = regras.clientes_visiveis(request.user).filter(pk=request.DATA.get("cliente")).first()
        if cliente is None:
            raise exc.WrongArguments({"cliente": ["Cliente não encontrado."]})
        regras.exigir_edicao(request.user, cliente)
        reuniao = Reuniao.objects.create(cliente=cliente, autor=request.user, **self._validar(request.DATA))
        self._participantes(reuniao, request.DATA.get("participantes_internos", []))
        registrar("reuniao.registrada", reuniao, cliente=cliente.id)
        return response.Created(self.get_serializer(reuniao).data)

    def partial_update(self, request, pk=None, **kwargs):
        _autenticado(request)
        reuniao = self.objeto(pk)
        regras.exigir_edicao(request.user, reuniao.cliente)
        dados = self._validar(request.DATA, parcial=True)
        Reuniao.objects.filter(pk=reuniao.pk).update(**dados)
        self._participantes(reuniao, request.DATA.get("participantes_internos"))
        registrar("reuniao.alterada", reuniao, cliente=reuniao.cliente_id, campos=sorted(dados))
        return response.Ok(self.get_serializer(self.objeto(pk)).data)

    def destroy(self, request, pk=None, **kwargs):
        _autenticado(request)
        reuniao = self.objeto(pk)
        regras.exigir_edicao(request.user, reuniao.cliente)
        registrar("reuniao.removida", reuniao, cliente=reuniao.cliente_id)
        reuniao.delete()
        return response.NoContent()

    @detail_route(methods=["POST"])
    def criar_demanda(self, request, pk=None):
        """Cria uma história no projeto do cliente a partir da ata. Exige poder criar histórias no projeto."""
        _autenticado(request)
        reuniao = self.objeto(pk)
        vinculo = reuniao.cliente.projetos.filter(project_id=request.DATA.get("projeto")).select_related("project").first()
        if vinculo is None:
            raise exc.WrongArguments({"projeto": ["Escolha um projeto deste cliente."]})
        projeto = vinculo.project
        if not user_has_perm(request.user, "add_us", projeto):
            raise exc.PermissionDenied("Você não pode criar histórias neste projeto.")
        assunto = _texto(request.DATA, "assunto", 500, obrigatorio=True)
        descricao = _texto(request.DATA, "descricao", 20000)
        us = UserStory.objects.create(project=projeto, owner=request.user, subject=assunto, description=descricao,
                                      status=projeto.default_us_status)
        take_snapshot(us, user=request.user)  # histórico nativo do Taiga, como se criada pela tela
        reuniao.demandas.add(us)
        registrar("reuniao.demanda_criada", reuniao, cliente=reuniao.cliente_id, projeto=projeto.id, historia=us.id)
        return response.Created({"id": us.id, "ref": us.ref, "projeto": projeto.slug})


# Busca global -------------------------------------------------------------------------------

class BuscaViewSet(GenericViewSet):
    """Clientes, documentos, projetos e histórias que a pessoa pode ver. Sem contagens totais: só o
    que já foi filtrado pelo acesso aparece, e nada de lembretes privados (SPEC-05) entra aqui."""
    permission_classes = ()

    def list(self, request, **kwargs):
        _autenticado(request)
        q = (request.QUERY_PARAMS.get("q") or "").strip()
        if len(q) < 2:
            raise exc.WrongArguments({"q": ["Digite pelo menos 2 caracteres."]})
        user, limite = request.user, 8
        digitos = regras.normalizar_cnpj(q)
        filtro_cnpj = Q(cnpj__startswith=digitos) if len(digitos) >= 3 else Q(pk__in=[])
        clientes = regras.clientes_visiveis(user).filter(Q(nome__icontains=q) | Q(razao_social__icontains=q) | filtro_cnpj)[:limite]
        documentos = regras.documentos_visiveis(user).filter(titulo__icontains=q).select_related("cliente")[:limite]
        projetos = regras.projetos_visiveis(user).filter(name__icontains=q).distinct()[:limite]
        historias = UserStory.objects.filter(project__in=regras.projetos_visiveis(user, "view_us").values("id"),
                                             subject__icontains=q).select_related("project")[:limite]
        return response.Ok({
            "clientes": [{"id": c.id, "nome": c.nome, "arquivado": c.arquivado} for c in clientes],
            "documentos": [{"id": d.id, "titulo": d.titulo, "cliente": d.cliente_id, "cliente_nome": d.cliente.nome} for d in documentos],
            "projetos": [{"id": p.id, "nome": p.name, "slug": p.slug} for p in projetos],
            "historias": [{"id": u.id, "ref": u.ref, "assunto": u.subject, "projeto": u.project.slug, "projeto_nome": u.project.name} for u in historias],
        })
