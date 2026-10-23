# Entrega 00 — Auditoria e fundação

Data: 22/10/2026 • Ambiente: container de desenvolvimento (4 vCPU, 15 GiB, Docker 29.9.1, Compose 5.6.0)

## O que foi reaproveitado, configurado e desenvolvido
- **Reaproveitado:** Taiga oficial completo (API, front, eventos, anexos protegidos, async), imagens oficiais e o compose oficial sem edição.
- **Configurado:** versões e digests fixos, `pt-br`, fuso do Celery, telemetria desligada, cadastro público desligado, cookies seguros por variável, segredos aleatórios.
- **Desenvolvido:** `scripts/vetor.sh` (subir, parar, manage, backup e restauração), `scripts/test-backend.sh` (suíte oficial num banco descartável) e documentação.
- Nenhuma alteração de interface nesta fatia; marca e telas ficam na SPEC-01.

## Arquivos

| Arquivo | Mudança |
|---|---|
| `.gitmodules`, `upstream/*` | submódulos oficiais fixados (decisão 0001) |
| `infra/docker-compose.override.yml` | novo |
| `.env.example`, `.gitignore` | novos |
| `scripts/vetor.sh`, `scripts/test-backend.sh` | novos |
| `docs/arquitetura.md`, `docs/inventario-taiga.md`, `docs/decisoes/0001…0004` | novos |
| `.claude/settings.json` | registra o plugin Ponytail para as sessões do agente |
| `README.md`, `assets/logo-vetor-original.jpg` | apresentação do projeto e logo |

**Migrações:** nenhuma própria. As migrações oficiais do Taiga rodam no primeiro `up`.

## Configuração necessária
Docker com Compose v2 e `openssl`. `./scripts/vetor.sh init-env` gera o `.env`. Para produção: `TAIGA_SCHEME=https`, `WEBSOCKETS_SCHEME=wss`, `COOKIES_SECURE=True`, SMTP real e domínio real.

## Critérios de aceite

| Critério | Resultado | Evidência |
|---|---|---|
| Instalação local reproduzível | **Atendido.** Volumes apagados e recriados do zero com `init-env` + `up`; 9 serviços no ar; API 200 | sequência registrada abaixo |
| Login funcionando | **Atendido.** Login pela API (token JWT) e pela interface | `evidencias/00/login-taiga-original.png`, `evidencias/00/pos-login-taiga-original.png` |
| Versão registrada | **Atendido** | `docs/inventario-taiga.md` (commits e digests) |
| Lacunas como nativo/configuração/desenvolvimento | **Atendido** | `docs/inventario-taiga.md` → "Lacunas por especificação" |
| Testes existentes relevantes executados | **Atendido.** 315 passaram, 0 falharam (auth, permissões, anexos, OCC, memberships, roles, busca, hook GitHub, usuários e as suítes `resources_permissions` correspondentes). A suíte completa não foi executada. | `evidencias/00/pytest-relevantes.txt` |
| Backup e restauração demonstrados | **Atendido.** 3 restaurações: duas após apagar projeto e arquivos, e uma numa instalação limpa sem volumes. Projeto, história e anexo voltaram; checksums conferidos. | sequência abaixo |
| Nenhum dado ou segredo de produção copiado | **Atendido.** Só dados `[FICTÍCIO]` criados localmente | — |

### Sequência de verificação de backup
1. Criados projeto privado, história e anexo (24 bytes) `[FICTÍCIO]`.
2. `backup` → `taiga.dump`, `media.tar.gz`, `env.backup`, `SHA256SUMS`.
3. Projeto apagado pela API (204); arquivos de anexo no volume: 0.
4. `restore` → checksums OK; projeto de volta; o anexo baixa com o token assinado e devolve 403 sem o token.
5. `docker compose down -v` (5 volumes removidos) → `up` com 0 projetos → `restore` → projeto e anexo de volta.

Problema encontrado e corrigido no passo 4: depois de reiniciar o `taiga-back`, o gateway nginx do compose oficial continuava apontando para o IP antigo do container (502). O `restore` agora reinicia o gateway.

## Riscos e pendências
- **Licença AGPL do taiga-front:** a interface modificada servida a usuários exige oferecer o código-fonte. Definir onde o repositório ficará acessível antes da SPEC-01 ir para usuários.
- **Componentes fora de suporte** (PostgreSQL 12, RabbitMQ 3.8, nginx 1.19) herdados do compose oficial; tratar na SPEC-10.
- **`/media/exports/` sem token** no gateway oficial (protegido só pelo nome aleatório do arquivo).
- **Backup com `.env` em texto claro**, com permissão 600. Cifrar ou separar antes de produção.
- **Sem MFA nativo;** SSO só GitHub/GitLab OAuth com cadastro público.
- O backup roda com o sistema no ar (`pg_dump` é consistente para o banco, mas um anexo enviado durante o backup pode ficar de fora). RPO/RTO ficam para a SPEC-10.
- A suíte completa do taiga-back (inclusive importadores) e os testes do front não foram executados.

## Reversão
Nada no Taiga foi modificado. Para desfazer: `./scripts/vetor.sh down` e `docker compose -p vetor down -v` (apaga os dados locais), e remover o repositório. Para voltar a um estado de dados: `./scripts/vetor.sh restore backups/<UTC>`.
