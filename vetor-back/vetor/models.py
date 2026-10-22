from django.conf import settings
from django.db import models


class Perfil(models.Model):
    """Papel da pessoa na organização Vetor Sistemas (conta nominal; sem perfil = observador)."""
    ADMINISTRADOR, GESTOR, DESENVOLVEDOR, OBSERVADOR = "administrador", "gestor", "desenvolvedor", "observador"
    PAPEIS = [(ADMINISTRADOR, "Administrador"), (GESTOR, "Gestor"),
              (DESENVOLVEDOR, "Desenvolvedor"), (OBSERVADOR, "Observador")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, primary_key=True, on_delete=models.CASCADE,
                                related_name="vetor_perfil")
    papel = models.CharField(max_length=20, choices=PAPEIS, default=OBSERVADOR)
    ver_custos = models.BooleanField(default=False)  # permissão explícita (SPEC-02), para qualquer papel
    atualizado_em = models.DateTimeField(auto_now=True)


class Auditoria(models.Model):
    """Registro somente de inclusão: quem fez o quê, em quê e quando. Nunca guardar senha, token ou lembrete."""
    ocorrido_em = models.DateTimeField(auto_now_add=True, db_index=True)
    ator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    ator_nome = models.CharField(max_length=255)  # mantém o registro legível se o usuário for removido
    acao = models.CharField(max_length=60, db_index=True)
    alvo_tipo = models.CharField(max_length=60)
    alvo_id = models.CharField(max_length=60)
    resultado = models.CharField(max_length=20, default="sucesso")
    detalhes = models.JSONField(default=dict)

    class Meta:
        ordering = ["-ocorrido_em", "-id"]


# CRM (SPEC-03) --------------------------------------------------------------------------------

def _caminho_documento(instance, filename):
    # Mesmo formato dos anexos do Taiga: o taiga-protected só serve attachments/... com token assinado.
    from taiga.base.utils.files import get_file_path
    return get_file_path(instance, filename, "attachments")


class Cliente(models.Model):
    NEGOCIACAO, IMPLANTACAO, OPERACAO, ENCERRADO = "negociacao", "implantacao", "operacao", "encerrado"
    CICLOS = [(NEGOCIACAO, "Negociação"), (IMPLANTACAO, "Implantação"), (OPERACAO, "Operação"), (ENCERRADO, "Encerrado")]

    nome = models.CharField(max_length=200)
    razao_social = models.CharField(max_length=255, blank=True, default="")
    cnpj = models.CharField(max_length=14, blank=True, default="")  # só dígitos; vazio para prospect
    estrangeiro = models.BooleanField(default=False)  # sem CNPJ; documento do país de origem é opcional
    documento_estrangeiro = models.CharField(max_length=60, blank=True, default="")
    cidade = models.CharField(max_length=120, blank=True, default="")
    uf = models.CharField(max_length=2, blank=True, default="")
    pais = models.CharField(max_length=60, blank=True, default="Brasil")
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="vetor_clientes")
    ciclo = models.CharField(max_length=20, choices=CICLOS, default=NEGOCIACAO)
    codigo_financeiro = models.CharField(max_length=60, blank=True, default="")  # id no sistema financeiro externo
    observacoes = models.TextField(blank=True, default="")
    arquivado = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome", "id"]
        constraints = [models.UniqueConstraint(fields=["cnpj"], condition=~models.Q(cnpj=""), name="vetor_cliente_cnpj_unico")]


class Contato(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="contatos")
    nome = models.CharField(max_length=200)
    funcao = models.CharField(max_length=120, blank=True, default="")
    telefone = models.CharField(max_length=40, blank=True, default="")
    email = models.EmailField(blank=True, default="")

    class Meta:
        ordering = ["nome", "id"]


class ProjetoCliente(models.Model):
    """Um cliente tem vários projetos; um projeto tem no máximo um cliente (projetos internos: nenhum)."""
    project = models.OneToOneField("projects.Project", primary_key=True, on_delete=models.CASCADE, related_name="vetor_cliente")
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="projetos")


class Documento(models.Model):
    CATEGORIAS = [("contrato", "Contrato"), ("proposta", "Proposta"), ("especificacao", "Especificação"),
                  ("ata", "Ata"), ("modelo", "Modelo"), ("outro", "Outro")]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="documentos")
    projeto = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    titulo = models.CharField(max_length=200)
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, default="outro")
    versao = models.CharField(max_length=20, blank=True, default="1")
    arquivo = models.FileField(upload_to=_caminho_documento, max_length=500, blank=True)
    tamanho = models.PositiveIntegerField(default=0)
    url_externa = models.URLField(max_length=500, blank=True, default="")  # documento em outro sistema
    origem_externa = models.CharField(max_length=80, blank=True, default="")  # ex.: "Google Drive"
    modelo_de = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="copias")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em", "-id"]
        constraints = [models.CheckConstraint(name="vetor_documento_arquivo_ou_link",
                                              check=(~models.Q(arquivo="") & models.Q(url_externa="")) |
                                                    (models.Q(arquivo="") & ~models.Q(url_externa="")))]


class Reuniao(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="reunioes")
    data = models.DateTimeField()
    participantes_internos = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="+")
    participantes_externos = models.TextField(blank=True, default="")  # um por linha
    notas = models.TextField(blank=True, default="")
    proximos_passos = models.TextField(blank=True, default="")
    demandas = models.ManyToManyField("userstories.UserStory", blank=True, related_name="+")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data", "-id"]
