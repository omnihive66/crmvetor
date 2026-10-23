"""Ajustes de settings da Vetor, aplicados por settings/config.py (produção) e vetor/tests/settings.py."""
import os


def aplicar(s):
    s["INSTALLED_APPS"] = ["vetor"] + s["INSTALLED_APPS"]  # primeiro: templates e estáticos da Vetor vencem
    s["ROOT_URLCONF"] = "vetor.urls"
    s["LOCALE_PATHS"] = (os.path.join(s["BASE_DIR"], "vetor", "locale"),) + tuple(s["LOCALE_PATHS"])
    s["MIDDLEWARE"] = ["vetor.ator.LimparAtorMiddleware"] + s["MIDDLEWARE"]
    # Mesmas classes do Taiga, mas registrando quem agiu (auditoria).
    s["REST_FRAMEWORK"]["DEFAULT_AUTHENTICATION_CLASSES"] = (
        "vetor.ator.JWTAuthentication", "vetor.ator.Session", "vetor.ator.Token")
    s["VETOR_PAPEL_SEM_PERFIL"] = "observador"  # conta sem perfil: só leitura até o administrador definir
    s["FEEDBACK_ENABLED"] = False
    # Documentos de cliente (SPEC-03). Sem antivírus na infraestrutura atual: só tipos de documento comuns.
    s["VETOR_DOCUMENTO_MAX_MB"] = int(os.getenv("VETOR_DOCUMENTO_MAX_MB", "25"))
    s["VETOR_DOCUMENTO_EXTENSOES"] = ["pdf", "doc", "docx", "odt", "xls", "xlsx", "ods", "csv", "ppt", "pptx", "odp",
                                      "txt", "md", "png", "jpg", "jpeg", "zip"]
    # Lembretes (SPEC-05): o worker do Taiga roda com beat (-B); a Vetor só acrescenta esta entrada.
    s["CELERY_BEAT_SCHEDULE"] = {**s.get("CELERY_BEAT_SCHEDULE", {}),
                                 "vetor-lembretes": {"task": "vetor.tasks.avisar_lembretes", "schedule": 60.0}}
    s["VETOR_AGENTE_LIMITE_MINUTO"] = int(os.getenv("VETOR_AGENTE_LIMITE_MINUTO", "30"))
    # GitHub (SPEC-06): só o segredo do webhook. O _ANTERIOR continua valendo durante a troca (rotação).
    s["VETOR_GITHUB_WEBHOOK_SEGREDOS"] = [v for v in (os.getenv("VETOR_GITHUB_WEBHOOK_SECRET", ""),
                                                      os.getenv("VETOR_GITHUB_WEBHOOK_SECRET_ANTERIOR", "")) if v]
    # O Taiga desliga loggers não declarados: sem isto, vetor.agente e vetor.lembretes não aparecem (só ids, nunca conteúdo).
    s["LOGGING"]["loggers"]["vetor"] = {"handlers": ["console"], "level": "INFO", "propagate": False}
    # Nome do sistema financeiro/contratual externo ainda não confirmado (README): fica configurável.
    s["VETOR_SISTEMA_FINANCEIRO"] = {"nome": os.getenv("VETOR_SISTEMA_FINANCEIRO_NOME", ""),
                                     "url": os.getenv("VETOR_SISTEMA_FINANCEIRO_URL", "")}  # o feedback oficial envia para support@taiga.io
