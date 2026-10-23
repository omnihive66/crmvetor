"""Operação (SPEC-10): correlation_id, saúde operacional, alertas, registro de backup e conectores não configurados."""
import datetime
import logging

import pytest
from django.conf import settings as conf
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from tests import factories as f

from vetor import correlacao, saude
from vetor.models import BackupRegistro, EventoProvedor, Perfil

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def ambiente(settings):
    settings.VETOR_PAPEL_SEM_PERFIL = "observador"
    settings.VETOR_GITHUB_WEBHOOK_SEGREDOS = []
    settings.VETOR_MONITOR_TOKENS = {"kuma": [], "beszel": []}
    settings.VETOR_FINANCEIRO_USUARIOS = []
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


def pessoa(papel, **kw):
    user = f.UserFactory.create(**kw)
    Perfil.objects.create(user=user, papel=papel)
    return user


def codigos(agora=None):
    return {a["codigo"] for a in saude.estado(agora)["alertas"]}


def test_correlation_id_vai_e_volta_e_entra_no_log(client):
    r = client.get("/api/v1/vetor/perfis/me", HTTP_X_REQUEST_ID="abc123def456")
    assert r["X-Request-ID"] == "abc123def456"
    gerado = client.get("/api/v1/vetor/perfis/me", HTTP_X_REQUEST_ID="inválido\n<script>")["X-Request-ID"]
    assert len(gerado) == 32 and gerado.isalnum()  # id de fora só se for seguro para log
    registro = logging.LogRecord("vetor", logging.INFO, __file__, 1, "x", None, None)
    token = correlacao.ID.set("rid-12345678")
    assert correlacao.Filtro().filter(registro) and registro.correlation_id == "rid-12345678"
    correlacao.ID.reset(token)
    assert "%(correlation_id)s" in conf.LOGGING["formatters"]["simple"]["format"]


def test_saude_so_para_administrador_e_conectores_sem_credencial_nao_configurados(client):
    client.login(pessoa("gestor"))
    assert client.get("/api/v1/vetor/saude").status_code == 403
    client.logout()
    assert client.get("/api/v1/vetor/saude").status_code == 401
    client.login(pessoa("administrador"))
    s = client.get("/api/v1/vetor/saude").json()
    estados = {c["nome"]: c["estado"] for c in s["conectores"]}
    assert estados["GitHub (webhook)"] == estados["Uptime Kuma"] == estados["Beszel"] == "nao_configurado"
    assert estados["Financeiro (usuário matriz)"] == "fechado_para_todos" and estados["AWS / Oracle (custos)"] == "nao_implementado"
    assert estados["Azure"] == "nao_definido" and "configurado" not in {estados["MFA / SSO"]}


def test_alertas_de_backup_restauracao_fila_e_email(settings):
    agora = timezone.now()
    assert {"backup_atrasado", "restauracao_nao_testada"} <= codigos(agora)
    BackupRegistro.objects.create(tipo="backup", local="b/1", resultado="ok", cifrado=False)
    assert "backup_sem_cifra" in codigos(agora) and "backup_atrasado" not in codigos(agora)
    BackupRegistro.objects.create(tipo="backup", local="b/2", resultado="ok", cifrado=True)
    BackupRegistro.objects.create(tipo="restauracao_teste", local="b/2", resultado="ok")
    assert not {"backup_atrasado", "backup_sem_cifra", "restauracao_nao_testada"} & codigos(agora)
    assert "backup_atrasado" in codigos(agora + datetime.timedelta(hours=settings.VETOR_BACKUP_MAX_HORAS + 1))
    EventoProvedor.objects.create(entrega="x", evento="push", payload={}, status=EventoProvedor.FALHOU)
    assert "webhook_github_falhas" in codigos(agora)
    settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    assert "email_nao_configurado" in codigos(agora)


def test_avisos_aos_administradores_uma_vez_por_dia():
    pessoa("administrador", email="admin@exemplo.com")
    pessoa("gestor", email="gestor@exemplo.com")
    agora = timezone.now()
    primeiro = saude.avisar(agora)
    assert primeiro and len(mail.outbox) == 1 and mail.outbox[0].to == ["admin@exemplo.com"]
    assert saude.avisar(agora + datetime.timedelta(hours=2)) == [] and len(mail.outbox) == 1
    assert saude.avisar(agora + datetime.timedelta(hours=25)) and len(mail.outbox) == 2


def test_comando_registra_backup_sem_segredos():
    call_command("vetor_registrar_backup", "--tipo", "backup", "--local", "backups/x", "--resultado", "ok", "--cifrado",
                 "--detalhes", '{"banco_bytes": 10}')
    b = BackupRegistro.objects.get()
    assert (b.resultado, b.cifrado, b.detalhes) == ("ok", True, {"banco_bytes": 10})


def test_webhooks_de_saida_nao_alcancam_enderecos_internos():
    # SSRF: o único envio para URL configurável é o webhook de saída do Taiga (só o Administrador cadastra, SPEC-02).
    assert conf.WEBHOOKS_ALLOW_PRIVATE_ADDRESS is False and conf.WEBHOOKS_ALLOW_REDIRECTS is False
