# Settings de teste: os do taiga-back (tests.config) com as mesmas mudanças de vetor-back/settings/config.py.
import os

from tests.config import *  # noqa: F401,F403

INSTALLED_APPS = ["vetor"] + INSTALLED_APPS
ROOT_URLCONF = "vetor.urls"
LOCALE_PATHS = (os.path.join(BASE_DIR, "vetor", "locale"),) + tuple(LOCALE_PATHS)
