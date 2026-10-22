# 0002 — Extensão do backend por app Django próprio

- Data: 22/10/2026 • Estado: aceita, implementada na SPEC-01

## Contexto
Clientes, documentos, lembretes, incidentes e custos não existem no Taiga. O backend oficial lê `settings/config.py`, e o compose oficial já prevê montar esse arquivo. Os plugins oficiais (`taiga_contrib_*`) funcionam acrescentando apps a `INSTALLED_APPS`.

## Decisão
Criar um app Django em `vetor-back/vetor` e uma imagem derivada (`vetor-back/Dockerfile`) que renomeia o `config.py` oficial para `config_taiga.py` e põe no lugar um `config.py` que importa o oficial e acrescenta o app. Montar os arquivos no container não funciona: o entrypoint oficial faz `chown -R /taiga-back` e falha em montagem somente leitura (e com escrita alteraria o dono dos arquivos no host). Reaproveitar a base de API, as permissões por projeto e o histórico do Taiga. Sem microserviço nem framework novo.

## Consequências
- Migrações próprias rodam com as do Taiga (`manage.py migrate`).
- Modelos novos só referenciam modelos do Taiga por chave estrangeira; não alteram tabelas nativas.
- Arquivos novos não herdam a MPL obrigatoriamente; arquivos do Taiga copiados e modificados herdam.
