# Manual de operação — Vetor Sistemas

Para quem instala, atualiza, faz backup e acompanha a saúde da instalação. Para o uso diário, veja `docs/manual-usuario.md`. A publicação em produção está em `docs/operacao/plano-producao.md` e **só acontece com autorização explícita**.

## 1. Componentes
Taiga oficial (back 6.10.2, front 6.10.3, events 6.10.0, protected 6.10.1) com imagens derivadas da Vetor, PostgreSQL 12.3, RabbitMQ 3.8 e nginx 1.19 no gateway. Todas as imagens são fixadas por digest (inventário em `docs/operacao/dependencias.md`). Arquitetura em `docs/arquitetura.md`.

## 2. Ambientes e configuração
Cada ambiente (desenvolvimento, homologação, produção) tem **seu próprio `.env`**, nunca versionado. `./scripts/vetor.sh init-env` gera um `.env` novo a partir do `.env.example`, com segredos aleatórios (`chmod 600`).

| Variável | Para quê | Padrão |
|---|---|---|
| `TAIGA_DOMAIN`, `TAIGA_SCHEME`, `TAIGA_SUBPATH`, `WEBSOCKETS_SCHEME` | endereço público (produção: `https`/`wss`) | localhost |
| `SECRET_KEY`, `POSTGRES_PASSWORD`, `RABBITMQ_*` | segredos internos | gerados |
| `COOKIES_SECURE` | cookies só por HTTPS | `False` em dev, **`True` em produção** |
| `EMAIL_BACKEND`, `EMAIL_HOST`… | envio de e-mail (SMTP) | console (não envia) |
| `VETOR_FINANCEIRO_USUARIOS` | login(s) do **usuário matriz**, o único com acesso a custos | vazio = fechado |
| `VETOR_GITHUB_WEBHOOK_SECRET` (+`_ANTERIOR`) | conector GitHub | vazio = desligado |
| `VETOR_KUMA_TOKEN`, `VETOR_BESZEL_TOKEN` (+`_ANTERIOR`) | monitoramento | vazio = desligado |
| `VETOR_SISTEMA_FINANCEIRO_NOME/URL` | link para o sistema financeiro externo | vazio |
| `VETOR_BACKUP_CHAVE_ARQUIVO` | chave que cifra o backup (arquivo **fora** do repositório) | vazio = backup sem cifra (alerta) |
| `VETOR_BACKUP_MAX_HORAS` | alerta de backup atrasado | 26 |
| `VETOR_DOCUMENTO_MAX_MB`, `VETOR_MONITOR_*`, `VETOR_USO_RETENCAO_DIAS`, `VETOR_AGENTE_LIMITE_MINUTO` | limites, janelas e retenções | ver `.env.example` |
| `ENABLE_TELEMETRY` | telemetria do Taiga para a Kaleidos | `False` |

**Conector sem credencial fica desligado** (o webhook responde 503) e aparece como "não configurado" em Administração → Saúde operacional.

## 3. Comandos
```
./scripts/vetor.sh up                 # sobe/atualiza (reconstrói as imagens derivadas, roda migrações, reinicia o gateway)
./scripts/vetor.sh down               # para
./scripts/vetor.sh logs [serviço]     # logs
./scripts/vetor.sh manage <comando>   # manage.py (ex.: createsuperuser, vetor_lembretes)
./scripts/vetor.sh backup             # backup (banco, anexos, .env), cifrado se houver chave
./scripts/vetor.sh restaurar-teste <dir>   # restauração ISOLADA de verificação (não toca a instalação)
./scripts/vetor.sh restore <dir>      # restauração REAL (substitui banco e anexos; para back/async)
./scripts/test-backend.sh --ds=vetor.tests.settings vetor/tests    # testes
```

## 4. Backup, restauração, RPO e RTO
- **O backup cobre** o banco (`pg_dump`), os anexos e documentos (`media`) e a configuração, com os segredos (`.env`): é o material de recuperação. A soma SHA-256 de cada arquivo fica em `SHA256SUMS`.
- **Criptografia em repouso:**
  - Com `VETOR_BACKUP_CHAVE_ARQUIVO`, os três arquivos saem cifrados (AES-256-CBC, PBKDF2 com 200 mil iterações), com permissões 600 e pasta 700.
  - **Gestão da chave:**
    - Gere com `openssl rand -base64 48 > /caminho/chave`, fora do repositório e fora da pasta de backups.
    - Guarde uma cópia offline com o responsável (cofre de senhas ou papel lacrado). **Sem ela, o backup não restaura.**
    - Para trocar a chave, gere uma nova, faça um backup novo e mantenha a antiga enquanto houver backups cifrados com ela.
- **Frequência proposta:** diária (agendada no servidor, ex.: `cron 0 3 * * * cd /opt/vetor && ./scripts/vetor.sh backup`), com cópia para fora do servidor. O destino depende da infraestrutura (SPEC-06/10).
- **RPO proposto: 24 h** (backup diário). **RTO proposto: 2 h** (servidor novo + restore). Na demonstração, a restauração isolada levou 10 s com o volume atual. **Os dois valores precisam ser validados pela gestão.**
- **Restauração demonstrada antes da produção:** `restaurar-teste` sobe um PostgreSQL descartável numa rede interna isolada e restaura o dump. Depois:
  - conta registros das tabelas principais;
  - confirma que a versão atual do sistema não tem migração pendente contra o banco restaurado;
  - confere os arquivos de mídia e registra o resultado.

  A evidência está em `docs/entregas/evidencias/10/backup-restauracao.txt`.
- **Alertas:** sem backup bem-sucedido em 26 h, backup sem cifra ou restauração nunca testada aparecem em Saúde operacional e geram e-mail aos administradores.

## 5. Atualização e rollback
- **Atualizar:**
  1. Faça backup.
  2. Atualize o repositório (branch revisada).
  3. Rode `./scripts/vetor.sh up`; as migrações rodam no início do back.
  4. Confira Saúde operacional.
- **Migrações:** cada entrega documenta as suas e como revertê-las (seção "Reversão" de `docs/entregas/NN-*.md`). As migrações da Vetor só criam tabelas e colunas próprias; nenhuma altera tabela do Taiga.
- **Rollback de código sem perder dados:** volte para a versão anterior **antes** de migrar a seguinte, ou reverta a migração com `./scripts/vetor.sh manage migrate vetor <número>`.
  - **Reverter apaga os dados das tabelas daquela entrega** (ex.: voltar para `0009` apaga os custos).
  - **Não há downgrade automático**: a reversão é decisão do responsável, com backup feito antes.
  - Restaurar o backup anterior é o caminho seguro quando o esquema já mudou.

## 6. Logs, correlação e retenção
- **Correlação:**
  - O gateway gera um `request_id` por requisição e o registra no log de acesso (`rid=`).
  - O back recebe o id como `X-Request-ID`, coloca em toda linha de log (`[id]`) e devolve no cabeçalho da resposta.
  - Para investigar, procure o mesmo id no gateway e no back (`./scripts/vetor.sh logs taiga-gateway | grep <id>`).
- **Conteúdo:** os logs dos conectores registram ids e status, nunca conteúdo privado, tokens ou segredos (verificado por teste em cada conector).
- **Retenção:** cada container guarda no máximo 5 arquivos de 10 MB (`json-file`). Para guardar por mais tempo, envie os logs a um coletor externo; isso depende da infraestrutura.

## 7. Saúde operacional e alertas
Em Administração → **Saúde operacional** (só o Administrador):
- **Alertas:** filas com falha (GitHub, monitoramento), worker sem resposta, e-mail não configurado ou falhando, backup atrasado ou sem cifra, restauração nunca testada.
- **Estado de cada conector:** configurado, não configurado, contrato pronto sem integração ativa, não implementado ou não definido.

A verificação roda a cada hora (Celery beat). Cada alerta novo vai por e-mail aos administradores, no máximo uma vez por dia por problema. **Configure o SMTP**: sem ele, os e-mails só aparecem no log, e a própria tela avisa.

## 8. Segurança aplicada
- **HTTPS:** em produção, por um proxy TLS na frente do gateway. Use `TAIGA_SCHEME=https`, `WEBSOCKETS_SCHEME=wss` e `COOKIES_SECURE=True`. **CSRF:** o do Taiga, mais isenção só em rotas autenticadas por cabeçalho (agente, webhooks, ingestão de uso), cada uma com teste de regressão.
- **Armazenamento privado:** anexos e documentos só por link assinado (taiga-protected), e exportações sem acesso direto (SPEC-02/03).
- **Conteúdo rico:** o Taiga sanitiza o Markdown. As telas da Vetor escrevem dados como texto (`textContent`), nunca como HTML.
- **Uploads:** limite de tamanho e lista de extensões nos documentos de cliente. Sem antivírus: pendência registrada.
- **SSRF:** a Vetor não faz requisições a URLs configuráveis. Os webhooks de saída do Taiga ficam restritos ao Administrador e **não alcançam endereços internos nem seguem redirecionamentos** (`WEBHOOKS_ALLOW_PRIVATE_ADDRESS/REDIRECTS=False`, com teste).
- **Segredos:**
  - Ficam no `.env` (600) e nunca no repositório; a CI confere.
  - Tokens de agente e de produto são guardados só como hash.
  - Os segredos dos webhooks de entrada ficam no ambiente.
  - O backup sai cifrado.
  - Disco cifrado no servidor é recomendação para a produção.
- **Financeiro:** fechado para o usuário matriz (`VETOR_FINANCEIRO_USUARIOS`).

## 9. Problemas comuns
| Sintoma | Causa e solução |
|---|---|
| 502 depois de `up` ou `restore` | o nginx guardou o IP antigo do back: `docker compose … restart taiga-gateway` (o `vetor.sh` já faz) |
| Docker não sobe ("timeout waiting for containerd") | containerd antigo travado: pare os processos, apague `/var/run/docker/containerd/*.pid` e suba o `dockerd` de novo |
| Webhook 503 | conector sem segredo/token no `.env` (desligado de propósito) |
| Webhook 401 | segredo/token diferente entre o provedor e o `.env` |
| E-mails não chegam | `EMAIL_BACKEND` ainda é o console; configure o SMTP |
| Restauração de backup cifrado falha | falta `VETOR_BACKUP_CHAVE_ARQUIVO` apontando para a chave correta |
