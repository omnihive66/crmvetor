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
    s["FEEDBACK_ENABLED"] = False  # o feedback oficial envia para support@taiga.io
