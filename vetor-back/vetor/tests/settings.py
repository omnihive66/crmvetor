# Settings de teste: os do taiga-back (tests.config) com os mesmos ajustes da produção.
from tests.config import *  # noqa: F401,F403
from vetor.ajustes import aplicar

aplicar(globals())

# A suíte oficial do Taiga cria usuários sem perfil com memberships completas: sem teto para ela.
# Os testes da Vetor que dependem do padrão de produção fixam "observador" explicitamente.
VETOR_PAPEL_SEM_PERFIL = "gestor"
