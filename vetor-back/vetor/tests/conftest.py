# Fixtures da suíte oficial (client com login(user), etc.) também para os testes da Vetor.
from tests.conftest import pytest_configure  # noqa: F401  (Celery síncrono)
from tests.fixtures import *  # noqa: F401,F403
