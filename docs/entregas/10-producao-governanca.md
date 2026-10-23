# Entrega 10 — Qualidade, operação e produção

Data: 23/10/2026 • Branch: `spec-10-producao` (sobre `spec-09-custos`)

**Publicação em produção: NÃO realizada.** A spec exige autorização explícita, com plano revisável e backup verificado. O plano está em `docs/operacao/plano-producao.md`, e falta infraestrutura (servidor, domínio, TLS, SMTP), que depende de vocês.

## O que foi reaproveitado, configurado e desenvolvido
- **Reaproveitado:**
  - Auditoria (SPEC-02).
  - Filas de falha do GitHub (SPEC-06) e do monitoramento (SPEC-07).
  - Backup e restauração do `vetor.sh` (SPEC-00).
  - QAs de cada spec.
  - Proteções do Taiga: CSRF, sanitização de Markdown, `WEBHOOKS_ALLOW_PRIVATE_ADDRESS=False`.
- **Configurado:**
  - Rotação de logs por container (5 × 10 MB).
  - `VETOR_BACKUP_CHAVE_ARQUIVO` e `VETOR_BACKUP_MAX_HORAS`.
  - Verificação horária de alertas no beat.
  - `VETOR_FINANCEIRO_USUARIOS`: o financeiro fechado para o **usuário matriz**, pedido nesta etapa.
- **Desenvolvido** (decisão 0013):
  - **Saúde operacional** (Administração, só o Administrador):
    - **Alertas:** filas com falha, worker sem resposta, e-mail não configurado ou com falha, backup atrasado ou sem cifra, restauração nunca testada.
    - **Estado de cada conector:** configurado, não configurado, contrato pronto, não implementado ou não definido.
    - **E-mail** aos administradores, no máximo uma vez por dia para cada problema.
  - **correlation_id** de ponta a ponta: `request_id` do nginx → `X-Request-ID` → toda linha de log do back → cabeçalho da resposta.
  - **Backup cifrado** (AES-256, chave fora do repositório, permissões 600/700) e registrado no banco.
  - **`restaurar-teste`:** restauração isolada num banco descartável e rede interna, conferindo contagens, migrações e mídia.
  - **CI** (`.github/workflows/ci.yml`):
    - Testes da Vetor contra o taiga-back oficial fixado.
    - Sintaxe de shell, JavaScript e Python, mais validação do compose.
    - Busca de segredos versionados.
    - Build das imagens.
    - Ações fixadas por commit.
  - **QA de ponta a ponta** (`fim-a-fim.js`), **linha de base de desempenho** (`desempenho.js`) e **auditoria de acessibilidade** com axe-core (`acessibilidade.js`).
  - **Manuais** de usuário e de operação, **inventário de dependências**, **plano de produção** e a lista única de pendências em `docs/entregas/README.md`.

## Arquivos

| Arquivo | Mudança |
|---|---|
| `vetor-back/vetor/correlacao.py`, `ajustes.py`, `infra/taiga-gateway.conf` | correlation_id e formato de log |
| `vetor-back/vetor/saude.py`, `api.py`, `urls.py`, `tasks.py` | saúde operacional, alertas e tarefa horária |
| `vetor-back/vetor/models.py`, `migrations/0011_operacao.py`, `management/commands/vetor_registrar_backup.py` | registro de backup/restauração e avisos |
| `vetor-back/vetor/permissoes.py`, `api_custos.py`, `api.py` | financeiro só do usuário matriz |
| `scripts/vetor.sh` | backup cifrado, restore de backup cifrado, `restaurar-teste` |
| `infra/docker-compose.override.yml`, `.env.example` | rotação de logs e variáveis novas |
| `vetor-front/administracao/index.html` | Saúde operacional; "Ver custos" removido |
| `vetor-front/*/index.html`, `clientes/*.html` | tabelas roláveis com foco pelo teclado |
| `vetor-back/vetor/tests/test_producao.py`, `test_custos.py`, `test_permissoes.py` | 6 testes novos e ajustes da regra do matriz |
| `.github/workflows/ci.yml` | CI |
| `scripts/qa/fim-a-fim.js`, `desempenho.js`, `acessibilidade.js` | verificações da SPEC-10 |
| `docs/manual-usuario.md`, `docs/manual-operacao.md`, `docs/operacao/`, `docs/decisoes/0013-*`, `docs/entregas/README.md`, `README.md`, `docs/arquitetura.md` | documentação |

**Migração:** `vetor.0011` cria duas tabelas próprias (`vetor_backupregistro`, `vetor_avisooperacional`).

## Configuração necessária
Para a produção, veja `docs/operacao/plano-producao.md`. Para qualquer ambiente:
- Defina `VETOR_BACKUP_CHAVE_ARQUIVO` com a chave fora do repositório e uma cópia offline.
- Configure o SMTP; sem ele, os alertas e os e-mails só aparecem no log.
- Informe o login do matriz em `VETOR_FINANCEIRO_USUARIOS`.

## Critérios de aceite

| Critério | Resultado | Evidência |
|---|---|---|
| CI relevante passa | Ver "CI" abaixo | `.github/workflows/ci.yml` |
| Licenças e avisos preservados | **Atendido.** As licenças dos 5 submódulos e os créditos no README foram mantidos, e o código-fonte é acessível (AGPL do front). A licença dos arquivos próprios está pendente. | `docs/operacao/dependencias.md` |
| Manual do usuário e de operação | **Atendido** | `docs/manual-usuario.md`, `docs/manual-operacao.md` |
| Restauração demonstrada | **Atendido.** Um backup cifrado foi restaurado num banco isolado em 10 s: 0 erros, nenhuma migração pendente, 13 arquivos de mídia. As contagens são iguais às do banco em uso; a única diferença é a auditoria, que ganhou as 2 linhas dos próprios registros. Não sobrou container nem rede. | `evidencias/10/backup-restauracao.txt` |
| Riscos e pendências documentados | **Atendido:** lista única em `docs/entregas/README.md` e riscos em cada entrega | — |
| Conectores sem credencial claramente não configurados | **Atendido.** Com o `.env` vazio, GitHub, Kuma e Beszel aparecem como "não configurado" e respondem 503. Agente e telemetria aparecem como "contrato pronto, sem integração ativa", AWS/Oracle como "não implementado" e Azure como "não definido". | `test_saude_…`, `saude-operacional-1440.png` |
| Deploy só com autorização, plano revisável e backup verificado | **Atendido: não publicado.** Plano pronto para revisão. | `docs/operacao/plano-producao.md` |
| Auditoria (ator, ação, alvo, horário, resultado) sem senha, token ou lembrete | **Atendido** desde a SPEC-02, com testes por spec (lembretes, custos sem valores, tokens só como hash) | entregas 02, 05, 09 |
| Logs com correlation_id e retenção definida | **Atendido.** O mesmo id aparece no gateway (`rid=`) e na resposta (`X-Request-ID`), e o back o coloca em cada linha. Id externo inseguro é trocado. Rotação 5 × 10 MB. | `test_correlation_id_…` |
| Alertas: filas, webhooks, envio e backup | **Atendido.** Alertas no painel e por e-mail, no máximo 1 por dia por problema. No ambiente apareceram 2 alertas reais: as entregas do GitHub da QA da SPEC-06 e o e-mail não configurado. | `test_alertas_…`, `test_avisos_…`, `saude.txt` |
| Exportação respeita permissão e minimização | **Atendido** por spec: exportações de projeto com link assinado (SPEC-02) e custos só para o matriz (SPEC-09) | entregas 02, 09 |
| Backup de banco, anexos, configuração e segredos; RPO/RTO | **Atendido.** RPO 24 h e RTO 2 h propostos, a validar pela gestão. | `docs/manual-operacao.md` §4 |
| Rollback com compatibilidade de esquema, sem downgrade destrutivo automático | **Atendido:** documentado por migração. A reversão é manual e com backup. | `docs/manual-operacao.md` §5 |
| HTTPS, cookies seguros, CSRF, armazenamento privado, sanitização, uploads, SSRF, segredos cifrados, dependências fixadas | **Atendido no que é da aplicação;** HTTPS e disco cifrado dependem do servidor (plano). SSRF: webhooks de saída sem endereço interno (teste). Imagens por digest e ações por commit. | `docs/manual-operacao.md` §8, `test_webhooks_de_saida_…` |
| Fluxo ponta a ponta cliente → projeto → tarefa → colaboração → código → incidente → resolução | **Atendido.** 9 de 9 passos OK. A demanda só foi concluída quando uma pessoa a moveu, mesmo com o PR merged e o monitor recuperado. | `evidencias/10/fim-a-fim.txt`, `fim-a-fim-*.png` |
| Baseline de desempenho (50 itens, p95 < 800 ms) | **Dentro da meta.** p95 de 28 ms (clientes), 42 ms (demandas), 81 ms (histórias do Taiga) e 36 ms (busca), em 4 vCPU e 15 GB, com o dataset registrado. A meta é proposta, não garantia. | `evidencias/10/desempenho.txt` |
| QA visual e acessibilidade | **Atendido.** axe-core (WCAG 2.1 A/AA) em 10 telas, a 1440 e 390 px: 1 violação encontrada e corrigida, e **0** na rodada final. Mais as QAs visuais de cada spec. | `evidencias/10/acessibilidade.txt` |

### Testes automáticos
- `vetor/tests`: **129 passaram** (6 novos).
- Suíte oficial ampliada: ver `evidencias/10/pytest.txt`.

### CI
Ver o resultado da primeira execução no GitHub Actions, registrado abaixo depois do push.

## Problemas encontrados e corrigidos no caminho
- **Acessibilidade:** a tabela da aba Custos, no celular, rolava sem receber foco pelo teclado. Corrigido em todos os 16 contêineres de tabela das telas.
- **Backup:** os arquivos cifrados saíam com permissão 644 (a pasta era 700). Agora é `umask 077`.
- **CI:** a checagem `! comando` não derruba um job com `bash -e`; foi trocada por `if` explícito.
- **Dataset de desempenho:** a contagem usava a lista paginada em 30, e cada rodada criava demandas a mais. Corrigido; o projeto de carga ficou com 70 demandas, registrado.

## Riscos e pendências
- **Produção não publicada:** depende das decisões da tabela de `docs/operacao/plano-producao.md`.
- **Opção "Ver custos" por pessoa:** foi desativada pela regra do usuário matriz. O campo continua no banco, sem efeito.
- **Retenção longa de logs:** depende de um coletor externo. A rotação local guarda cerca de 50 MB por container.
- **Repositório público:** o código é visível a qualquer pessoa (os segredos nunca são versionados, e a CI confere). Precisa de confirmação.

## Reversão
`./scripts/vetor.sh manage migrate vetor 0010` remove o registro de backups e os avisos. As mudanças no `vetor.sh` são compatíveis com os backups antigos, sem cifra.
