# Configuração da Vetor Sistemas: parte do config.py oficial da imagem Docker e acrescenta o app "vetor".
# Montado em /taiga-back/settings/config.py; o oficial vai como settings/config_taiga.py.
import os

from .config_taiga import *  # noqa: F401,F403

INSTALLED_APPS = ["vetor"] + INSTALLED_APPS  # primeiro: templates e estáticos da Vetor têm prioridade
ROOT_URLCONF = "vetor.urls"
LOCALE_PATHS = (os.path.join(BASE_DIR, "vetor", "locale"),) + tuple(LOCALE_PATHS)

FEEDBACK_ENABLED = False  # o feedback oficial envia para support@taiga.io

_source_url = os.getenv("VETOR_SOURCE_URL", "")
SR = {
    **SR,
    "taigaio_url": TAIGA_URL,
    "social": {"twitter_url": "", "github_url": _source_url},
    "support": {"url": _source_url, "email": os.getenv("EMAIL_DEFAULT_FROM", DEFAULT_FROM_EMAIL)},
    "signature": "Equipe Vetor Sistemas",
    "product_name": "Vetor Sistemas",
}
