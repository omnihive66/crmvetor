# Imagem do backend da Vetor Sistemas: taiga-back oficial + app "vetor" e config.py próprio.
# Contexto de build: raiz do repositório.
FROM taigaio/taiga-back:6.10.2@sha256:4beed8f62c9ffbbcea824aa01c48fa72a2c2f713be6732e2ee37d2e777843f51
RUN mv settings/config.py settings/config_taiga.py
COPY vetor-back/settings/config.py settings/config.py
COPY vetor-back/vetor vetor
