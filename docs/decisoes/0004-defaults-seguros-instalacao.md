# 0004 — Padrões da instalação

- Data: 22/10/2026 • Estado: aceita

## Decisão
- Segredos aleatórios gerados localmente (`openssl rand -hex 32`); o `.env` nunca é versionado.
- Telemetria anônima do Taiga desligada (`ENABLE_TELEMETRY=False`).
- Cadastro público desligado; contas criadas por administrador (nominais).
- Idioma `pt-br`, banco em UTC, Celery em `America/Sao_Paulo`.
- Cookies `Secure` controlados por `COOKIES_SECURE` (False só no desenvolvimento sem HTTPS).
- Backup cobre banco (`pg_dump -Fc`), mídia e `.env`, com checksums conferidos antes de restaurar.

## Pendências
- PostgreSQL 12 e RabbitMQ 3.8 vêm do compose oficial e estão fora de suporte; atualizar com plano de migração na SPEC-10.
- O backup inclui o `.env` em texto claro. Antes de produção: cifrar o backup ou guardar os segredos num cofre separado.
