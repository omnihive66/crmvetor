# 0002 — Extensão do backend por app Django próprio

- Data: 22/10/2026 • Estado: aceita (implementação a partir da SPEC-02/03)

## Contexto
Clientes, documentos, lembretes, incidentes e custos não existem no Taiga. O backend oficial lê `settings/config.py`, e o compose oficial já prevê montar esse arquivo. Os plugins oficiais (`taiga_contrib_*`) funcionam acrescentando apps a `INSTALLED_APPS`.

## Decisão
Criar um app Django em `vetor-back/`, montado no container oficial junto com um `config.py` que faz `from .common import *` como o oficial e acrescenta o app. Reaproveitar a base de API, as permissões por projeto e o histórico do Taiga. Sem microserviço nem framework novo.

## Consequências
- Migrações próprias rodam com as do Taiga (`manage.py migrate`).
- Modelos novos só referenciam modelos do Taiga por chave estrangeira; não alteram tabelas nativas.
- Arquivos novos não herdam a MPL obrigatoriamente; arquivos do Taiga copiados e modificados herdam.
