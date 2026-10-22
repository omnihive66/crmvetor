# Configuração da Vetor Sistemas: parte do config.py oficial da imagem Docker e acrescenta o app "vetor".
# A imagem (vetor-back/Dockerfile) põe este arquivo em settings/config.py e o oficial em settings/config_taiga.py.
import os

from .config_taiga import *  # noqa: F401,F403
from vetor.ajustes import aplicar

aplicar(globals())

_source_url = os.getenv("VETOR_SOURCE_URL", "")
SR = {
    **SR,
    "taigaio_url": TAIGA_URL,
    "social": {"twitter_url": "", "github_url": _source_url},
    "support": {"url": _source_url, "email": os.getenv("EMAIL_DEFAULT_FROM", DEFAULT_FROM_EMAIL)},
    "signature": "Equipe Vetor Sistemas",
    "product_name": "Vetor Sistemas",
}
