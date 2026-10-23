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
    proximo_contato = models.DateField(null=True, blank=True)  # SPEC-08: relacionamento
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


# Projetos (SPEC-04) ---------------------------------------------------------------------------

class ParticipacaoEtapa(models.Model):
    """Quem esteve em cada etapa de uma história, de quando até quando, e quem fez a mudança.
    Gerada pelos signals a partir de status, responsável e colaboradores (não se edita à mão)."""
    historia = models.ForeignKey("userstories.UserStory", on_delete=models.CASCADE, related_name="+")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    usuario_nome = models.CharField(max_length=255)
    status = models.ForeignKey("projects.UserStoryStatus", null=True, on_delete=models.SET_NULL, related_name="+")
    status_nome = models.CharField(max_length=255)  # o nome da etapa pode mudar ou ela ser excluída depois
    inicio = models.DateTimeField()
    fim = models.DateTimeField(null=True, blank=True)
    autor_inicio = models.CharField(max_length=255)
    autor_fim = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["inicio", "id"]
        indexes = [models.Index(fields=["historia", "fim"])]


# Minhas demandas, lembretes e agente (SPEC-05) -----------------------------------------------

class Lembrete(models.Model):
    """Privado do dono: nenhuma consulta o expõe a outra pessoa, nem a administradores ou superusuários."""
    ABERTO, CONCLUIDO, CANCELADO = "aberto", "concluido", "cancelado"
    ESTADOS = [(ABERTO, "Aberto"), (CONCLUIDO, "Concluído"), (CANCELADO, "Cancelado")]
    RECORRENCIAS = [("", "Não repete"), ("diaria", "Diária"), ("semanal", "Semanal"), ("mensal", "Mensal")]

    dono = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vetor_lembretes")
    titulo = models.CharField(max_length=200)
    notas = models.TextField(blank=True, default="")
    vencimento = models.DateTimeField(null=True, blank=True)  # UTC; exibido em America/Sao_Paulo
    recorrencia = models.CharField(max_length=10, choices=RECORRENCIAS, blank=True, default="")
    avisar_email = models.BooleanField(default=False)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=ABERTO)
    # Referências opcionais: só aparecem enquanto o dono tiver acesso a elas (nada é copiado para cá).
    cliente = models.ForeignKey("vetor.Cliente", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    projeto = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    historia = models.ForeignKey("userstories.UserStory", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    notificado_em = models.DateTimeField(null=True, blank=True)  # aviso do vencimento atual já dado (idempotência)
    visto_em = models.DateTimeField(null=True, blank=True)
    convertido_em = models.ForeignKey("userstories.UserStory", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [models.F("vencimento").asc(nulls_last=True), "-criado_em"]
        indexes = [models.Index(fields=["estado", "notificado_em", "vencimento"])]


class TokenAgente(models.Model):
    """Token pessoal do agente externo: age só como o próprio dono, só nas rotas /vetor/agente e só nos escopos dados."""
    LEMBRETES, DEMANDAS = "lembretes", "demandas"
    dono = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vetor_tokens_agente")
    nome = models.CharField(max_length=80)
    prefixo = models.CharField(max_length=12, db_index=True)  # identifica o token na tela sem revelá-lo
    hash = models.CharField(max_length=64, unique=True)       # sha256; o token em si nunca é guardado
    escopos = models.JSONField(default=list)
    criado_em = models.DateTimeField(auto_now_add=True)
    usado_em = models.DateTimeField(null=True, blank=True)
    revogado_em = models.DateTimeField(null=True, blank=True)


class RequisicaoAgente(models.Model):
    """Uma por Idempotency-Key: repetir a mesma chave devolve o mesmo resultado. Serve também ao limite por minuto."""
    token = models.ForeignKey(TokenAgente, on_delete=models.CASCADE, related_name="requisicoes")
    chave = models.CharField(max_length=100)
    status = models.PositiveSmallIntegerField()
    resposta = models.JSONField(default=dict)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["token", "chave"], name="vetor_agente_chave_unica")]


class Repositorio(models.Model):
    """Repositório ligado a um projeto (1:N). Só identifica: a Vetor não guarda token do provedor."""
    projeto = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="vetor_repositorios")
    provedor = models.CharField(max_length=20, default="github")
    nome = models.CharField(max_length=200)  # "dono/repo", como o provedor mostra
    id_externo = models.CharField(max_length=40, blank=True, default="")  # id numérico do provedor: sobrevive a renomear
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        constraints = [models.UniqueConstraint(fields=["provedor", "nome"], name="vetor_repositorio_unico")]


class EventoProvedor(models.Model):
    """Cada entrega do webhook, como chegou: deduplicação pelo id da entrega, reprocessamento e fila de falhas."""
    RECEBIDO, PROCESSADO, IGNORADO, FALHOU = "recebido", "processado", "ignorado", "falhou"
    provedor = models.CharField(max_length=20, default="github")
    entrega = models.CharField(max_length=100)  # X-GitHub-Delivery
    evento = models.CharField(max_length=50)
    repositorio = models.ForeignKey(Repositorio, null=True, on_delete=models.SET_NULL, related_name="eventos")
    payload = models.JSONField()
    status = models.CharField(max_length=12, default=RECEBIDO, db_index=True)
    tentativas = models.PositiveSmallIntegerField(default=0)
    erro = models.TextField(blank=True, default="")
    recebido_em = models.DateTimeField(auto_now_add=True)
    processado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-recebido_em"]
        constraints = [models.UniqueConstraint(fields=["provedor", "entrega"], name="vetor_evento_entrega_unica")]


class VinculoCodigo(models.Model):
    """Issue, commit ou pull request citado numa história (TG-<ref>). Sincroniza só do provedor para a Vetor."""
    historia = models.ForeignKey("userstories.UserStory", on_delete=models.CASCADE, related_name="vetor_vinculos")
    repositorio = models.ForeignKey(Repositorio, on_delete=models.CASCADE, related_name="vinculos")
    tipo = models.CharField(max_length=12)  # issue, commit, pr
    id_externo = models.CharField(max_length=60)  # id do provedor (issue/PR) ou sha (commit)
    numero = models.PositiveIntegerField(null=True, blank=True)
    url = models.URLField(max_length=500)
    titulo = models.CharField(max_length=500)
    estado = models.CharField(max_length=10, blank=True, default="")  # PR: draft/open/merged/closed; issue: open/closed
    autor_externo = models.CharField(max_length=100, blank=True, default="")
    atualizado_no_provedor = models.DateTimeField(null=True, blank=True)  # evita que evento antigo sobrescreva o novo
    evento = models.ForeignKey(EventoProvedor, null=True, on_delete=models.SET_NULL, related_name="+")  # origem da última mudança

    class Meta:
        ordering = ["tipo", "-atualizado_no_provedor"]
        constraints = [models.UniqueConstraint(fields=["historia", "tipo", "id_externo"], name="vetor_vinculo_unico")]


class RecursoMonitorado(models.Model):
    """Monitor do Kuma ou servidor do Beszel. Sem projeto = triagem: nada é associado por suposição."""
    provedor = models.CharField(max_length=10)  # kuma, beszel
    id_externo = models.CharField(max_length=100)
    nome = models.CharField(max_length=200)
    projeto = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="vetor_recursos")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["provedor", "nome"]
        constraints = [models.UniqueConstraint(fields=["provedor", "id_externo"], name="vetor_recurso_unico")]


class Incidente(models.Model):
    """Um por recurso e tipo enquanto aberto; reincidência dentro da janela reabre o mesmo."""
    ABERTO, RECUPERADO = "aberto", "recuperado"
    recurso = models.ForeignKey(RecursoMonitorado, on_delete=models.CASCADE, related_name="incidentes")
    tipo = models.CharField(max_length=60)  # disponibilidade, limite:cpu, ...
    estado = models.CharField(max_length=10, default=ABERTO, db_index=True)
    severidade = models.CharField(max_length=10)
    resumo = models.CharField(max_length=500)
    aberto_em = models.DateTimeField()
    recuperado_em = models.DateTimeField(null=True, blank=True)
    ultimo_evento_em = models.DateTimeField()  # ocorrência mais recente aplicada: evento mais antigo não muda o estado
    ocorrencias = models.PositiveIntegerField(default=1)
    reincidencias = models.PositiveIntegerField(default=0)
    historia = models.ForeignKey("userstories.UserStory", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    notificado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-aberto_em"]


class EventoMonitoramento(models.Model):
    """Contrato do evento (SPEC-07) + estado do processamento. O payload guardado é só a lista de campos permitidos."""
    RECEBIDO, PROCESSADO, FALHOU = "recebido", "processado", "falhou"
    provedor = models.CharField(max_length=10)
    id_externo = models.CharField(max_length=200, null=True, blank=True)  # Beszel não tem: sem deduplicação por entrega
    id_recurso = models.CharField(max_length=100, blank=True, default="")
    recurso = models.ForeignKey(RecursoMonitorado, null=True, blank=True, on_delete=models.SET_NULL, related_name="eventos")
    incidente = models.ForeignKey(Incidente, null=True, blank=True, on_delete=models.SET_NULL, related_name="eventos")
    tipo = models.CharField(max_length=60)
    status = models.CharField(max_length=12)  # down, up, pendente, manutencao, alerta, normal, info
    severidade = models.CharField(max_length=10)
    resumo = models.CharField(max_length=500)
    url_origem = models.CharField(max_length=500, blank=True, default="")
    ocorrido_em = models.DateTimeField()
    recebido_em = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(null=True)  # limpo depois da retenção
    processamento = models.CharField(max_length=12, default=RECEBIDO, db_index=True)
    tentativas = models.PositiveSmallIntegerField(default=0)
    erro = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["ocorrido_em", "id"]
        constraints = [models.UniqueConstraint(fields=["provedor", "id_externo"], name="vetor_evento_monitor_unico")]


class ProdutoTelemetria(models.Model):
    """Produto entregue a um cliente que envia eventos de uso. Sem produto (ou sem eventos), adoção = "sem dados"."""
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="produtos_telemetria")
    nome = models.CharField(max_length=120)
    chave = models.CharField(max_length=60)  # product_id enviado pelo produto
    prefixo = models.CharField(max_length=12)
    hash = models.CharField(max_length=64, unique=True)  # sha256 do token de ingestão; o token nunca é guardado
    sintetico = models.BooleanField(default=False)  # dados de validação: sempre identificados na tela
    janela_ativos_dias = models.PositiveSmallIntegerField(default=30)  # "usuários ativos" = atividade nos últimos N dias (Brasília)
    alerta_desuso_dias = models.PositiveSmallIntegerField(null=True, blank=True)  # vazio = sem alerta de desuso
    alerta_excecao_ate = models.DateField(null=True, blank=True)  # exceção por contrato/contexto (férias, sazonalidade)
    alerta_excecao_motivo = models.CharField(max_length=200, blank=True, default="")
    revogado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        constraints = [models.UniqueConstraint(fields=["cliente", "chave"], name="vetor_produto_chave_unica")]


class EventoUso(models.Model):
    """Evento pseudonimizado e mínimo: quem (pseudônimo re-cifrado no servidor), o quê (tipo) e quando. Nada de conteúdo."""
    LOGIN, ATIVIDADE, PULSO = "login", "atividade", "pulso"  # pulso = o produto está enviando (não é uso)
    produto = models.ForeignKey(ProdutoTelemetria, on_delete=models.CASCADE, related_name="eventos")
    id_externo = models.CharField(max_length=100)
    tipo = models.CharField(max_length=10)
    funcionalidade = models.CharField(max_length=60, blank=True, default="")  # só em atividade
    usuario = models.CharField(max_length=64, blank=True, default="")  # HMAC do pseudônimo recebido
    ocorrido_em = models.DateTimeField(db_index=True)
    recebido_em = models.DateTimeField(auto_now_add=True)
    sintetico = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["produto", "id_externo"], name="vetor_evento_uso_unico")]
        indexes = [models.Index(fields=["produto", "tipo", "ocorrido_em"])]
