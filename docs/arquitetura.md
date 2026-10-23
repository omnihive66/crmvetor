# Arquitetura — Vetor Sistemas

A Vetor Sistemas é uma instalação do Taiga oficial, sem fork do núcleo, com extensões isoladas em diretórios próprios. Detalhes do Taiga em `docs/inventario-taiga.md`; motivos em `docs/decisoes/`.

```
navegador ──► taiga-gateway (nginx :9000)
               ├─ /            taiga-front  (imagem vetor/taiga-front: SPA oficial + marca aplicada no build)
               ├─ /api/        taiga-back   (imagem vetor/taiga-back: API oficial + app Django `vetor`)
               ├─ /events      taiga-events (imagem vetor/taiga-events: assinatura só do que o usuário pode ver)
               └─ /media/      taiga-protected (imagem vetor/taiga-protected: anexos e exportações com token assinado)
             taiga-async (Celery) ◄── taiga-async-rabbitmq
             taiga-db (PostgreSQL)
```

## Repositório

| Caminho | Conteúdo |
|---|---|
| `upstream/` | submódulos git do Taiga oficial, fixados em tag/commit. **Não editar**; mudanças no núcleo só com decisão registrada. |
| `infra/docker-compose.override.yml` | sobreposição do compose oficial: versões e digests fixos, idioma, fuso, cookies |
| `.env.example` | variáveis sem segredos; `.env` real é gerado e fica fora do git |
| `scripts/vetor.sh` | subir, parar, `manage.py`, backup e restauração |
| `scripts/test-backend.sh` | suíte pytest do taiga-back num Postgres descartável |
| `docs/` | arquitetura, inventário, decisões, entregas e evidências |
| `specs/`, `DESIGN.md`, `COMANDOS.md`, `RASTREABILIDADE.md` | o pacote de especificação |

| `vetor-front/` | `Dockerfile` + `build.py`: aplica paleta, logos, textos pt-BR e título sobre o build oficial do front (decisão 0003) |
| `vetor-back/` | `Dockerfile`, `settings/config.py` e o app Django `vetor`: papéis e auditoria (decisão 0006), rotas, traduções e e-mails (decisão 0002) |
| `vetor-front/ui/` | base das telas próprias: `vetor-ui.css` (componentes) e a barra lateral global `shell.js`/`shell.css` (também no app do Taiga) |
| `vetor-front/{clientes,demandas,busca,administracao}/` | telas próprias servidas em `/vetor/...`: CRM, demandas entre projetos, busca global e Administração |
| `vetor-events/`, `vetor-protected/` | imagens derivadas com uma troca verificada no código oficial (falham no build se o trecho mudar) |
| `infra/taiga-gateway.conf` | gateway oficial sem a seção que servia exportações sem token |
| `scripts/qa/` | capturas de tela, teclado/zoom e menu por papel (Playwright) |

`./scripts/vetor.sh up` reconstrói as imagens derivadas (rápido, com cache) e reinicia o gateway.

## Operação local

Requisitos: Docker com Compose v2, `openssl`, git.

```bash
git clone --recurse-submodules <repo> && cd vetor-sistemas
./scripts/vetor.sh init-env        # cria .env com segredos aleatórios (não sobrescreve)
./scripts/vetor.sh up              # http://localhost:9000
./scripts/vetor.sh manage createsuperuser
./scripts/vetor.sh backup          # backups/<UTC>/ : taiga.dump, media.tar.gz, env.backup, SHA256SUMS
./scripts/vetor.sh restore backups/<UTC>
./scripts/test-backend.sh tests/integration/test_auth.py   # sem argumentos roda a suíte inteira
```

Em ambiente com proxy TLS próprio, exporte `PIP_CERT=<bundle de CA>` antes de `test-backend.sh`.

## Convenções
- Datas no banco em UTC; exibição em `America/Sao_Paulo`. Idioma padrão `pt-br`.
- Autorização sempre no backend; o front só esconde o que o backend já nega.
- Dados de demonstração só no desenvolvimento e com prefixo `[FICTÍCIO]`.
- Nomes técnicos (pacotes, tabelas, `taiga-*`) não mudam por causa da marca.
