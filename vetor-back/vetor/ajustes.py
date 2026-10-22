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
    # Nome do sistema financeiro/contratual externo ainda não confirmado (README): fica configurável.
    s["VETOR_SISTEMA_FINANCEIRO"] = {"nome": os.getenv("VETOR_SISTEMA_FINANCEIRO_NOME", ""),
                                     "url": os.getenv("VETOR_SISTEMA_FINANCEIRO_URL", "")}  # o feedback oficial envia para support@taiga.io
