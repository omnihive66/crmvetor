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
