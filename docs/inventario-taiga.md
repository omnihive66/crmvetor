# Inventário do Taiga instalado

Levantado por inspeção do código fixado em `upstream/` e da instalação local em 22/10/2026. Tudo aqui foi conferido no código ou na instância rodando; o que não foi conferido está marcado como "não verificado".

## Versões fixadas

| Componente | Versão | Commit / digest |
|---|---|---|
| taiga-back | 6.10.2 | `4b023d8414fc675780c6aae9d541b538c5c71369` / `sha256:4beed8f6…843f51` |
| taiga-front | 6.10.3 (imagem usa taiga-front-dist 6.10.3) | `a17d8c91070b9cf2230877084afe22848ea536aa` / `sha256:570c8792…2d646` |
| taiga-events | 6.10.0 | `e411856df4653dccdd727994b0d957db28d15770` / `sha256:92fc0822…ab40` |
| taiga-protected | 6.10.1 | `3fc1f92b75290d5c41fdd14c7d647aeeb68338a2` / `sha256:fd4568a9…d393` |
| taiga-docker | main (VERSION.md diz 6.9.0; não há tag 6.10) | `e12c106b265ab8c51ee7e62b744ffddd0f0d9771` |
| PostgreSQL | 12.3 (fora de suporte desde 11/2024) | `sha256:a06e6e6e…cf19` |
| RabbitMQ | 3.8-management-alpine (fora de suporte) | `sha256:c3e52676…64ef` |
| nginx (gateway) | 1.19-alpine (antigo) | `sha256:07ab71a2…05d2` |

Digests completos em `infra/docker-compose.override.yml`. Base do backend: Python 3.11, Django 3.2, DRF próprio do Taiga (`taiga.base.api`), Celery. Frontend: AngularJS 1.x + CoffeeScript + Jade, servido como estáticos pelo nginx.

## Serviços

| Serviço | Função |
|---|---|
| taiga-back | API REST `/api/v1/` (gunicorn), admin Django em `/admin/` |
| taiga-async | Worker Celery (e-mails em lote, exportação/importação, webhooks) |
| taiga-async-rabbitmq | Fila do Celery |
| taiga-events + taiga-events-rabbitmq | WebSocket `/events` para atualização em tempo real |
| taiga-protected | Serve `/media/` só com token assinado (validade `ATTACHMENTS_MAX_AGE`, 360 s) |
| taiga-front | SPA estática |
| taiga-gateway | nginx que une tudo na porta 9000 |
| taiga-db | PostgreSQL |

## Autenticação e sessão
- JWT (`taiga.auth.authentication.JWTAuthentication`): access 24 h, refresh 8 dias. Revogação de refresh por `taiga.auth.token_denylist`.
- Usuário inativo ou de sistema é recusado em toda requisição (`auth/authentication.py:149`). Isso cobre "desativar usuário impede novas ações" já no nativo; o access token já emitido para de funcionar na próxima chamada.
- Sessão Django (só para depuração/admin) e tokens de aplicação externa (`taiga.external_apps`): token **por usuário e por aplicação**, autorizado pelo próprio usuário. É a base candidata para o agente da SPEC-05 (sem token global).
- Cadastro público desligado (`PUBLIC_REGISTER_ENABLED=False`, mantido).
- **MFA: não existe nativo.** **SSO:** só os plugins oficiais GitHub/GitLab OAuth, e o `config.py` oficial só os ativa com cadastro público ligado. SAML/OIDC/Entra ID exigem desenvolvimento ou proxy de identidade.

## Permissões
- Por projeto: membros com papéis (`roles`) e permissões granulares por recurso (`view_us`, `modify_task`, `comment_us`, …), mais permissões para anônimos e "público" em projetos públicos. Admin de projeto e superusuário.
- **Não há nível de organização**, cliente nem "gestor de vários projetos": o escopo é sempre um projeto. Papel organizacional da SPEC-02 é desenvolvimento.
- Verificação no servidor em listagens, detalhes, busca (`/api/v1/search` filtra por projetos visíveis), anexos e eventos; coberta pela suíte `tests/integration/resources_permissions` (executada, ver entrega 00).
- Superusuário Django vê tudo. Isso importa para os lembretes privados (SPEC-05): o modelo novo precisa ser filtrado por dono também para superusuário.

## Objetos nativos relevantes

| Objeto | Campos/recursos úteis |
|---|---|
| Projeto | Kanban e/ou Scrum, módulos ligáveis, modelos de projeto (`scrum`, `kanban`), status configuráveis por projeto, swimlanes, atributos personalizados, tags |
| Épico | agrupa histórias, inclusive de projetos diferentes |
| História (user story) | status do fluxo, `assigned_to` + **`assigned_users` (vários responsáveis)**, `is_blocked` + `blocked_note`, `due_date`, tags, pontos, anexos, comentários, observadores, versão OCC |
| Tarefa | filha de história (um nível), status próprio, `assigned_to` único, bloqueio, prazo |
| Issue | itens com tipo/severidade/prioridade |
| Comentários/histórico | `taiga.projects.history`: cada alteração gera entrada; comentário com histórico de edição (`comment_versions`) e menções `@usuario` |
| Anexos | por objeto, servidos via taiga-protected |
| Notificações | e-mail com intervalo mínimo (`CHANGE_NOTIFICATIONS_MIN_INTERVAL` 120 s) e notificações web (`WebNotification`) |
| Userstorage | chave-valor por usuário (`/api/v1/user-storage`), já usado pelo front para filtros |
| Webhooks de saída | por projeto, assinados com HMAC-SHA1 (`X-TAIGA-WEBHOOK-SIGNATURE`) |
| Integrações Git | GitHub, GitLab, Bitbucket, Gogs: webhook de entrada por projeto |
| Exportação/importação | dump JSON do projeto |
| Timeline | feed de atividade por projeto/usuário |

### Integração GitHub nativa (base da SPEC-06)
`taiga.hooks.github`: recebe `push`, `issues` e `issue_comment`. Valida `X-Hub-Signature` (**HMAC-SHA1**, o cabeçalho legado do GitHub; não valida `X-Hub-Signature-256`). O push muda status por mensagem de commit (`TG-<ref> #<status>`). Issue do GitHub vira issue no Taiga. **Não trata pull requests**, não deduplica por `X-GitHub-Delivery` e processa de forma síncrona. Segredo por projeto fica em `modules_config`.

## Tarefas assíncronas, eventos e e-mail
Celery com serializer `pickle` (padrão do upstream; risco aceitável só porque o broker é interno). Fuso do Celery ajustado para `America/Sao_Paulo`; banco em UTC (`USE_TZ=True`, `TIME_ZONE="UTC"`). E-mail em modo `console` no desenvolvimento.

## Pontos de extensão (por inspeção)
- **Backend:** `settings/config.py` montado no container (o compose oficial já prevê o volume) pode acrescentar apps a `INSTALLED_APPS`, como fazem os plugins oficiais `taiga_contrib_*`. Um app Django próprio tem modelos, migrações, API (`taiga.base.api`) e reaproveita permissões e histórico do Taiga sem fork do núcleo.
- **Frontend:** `conf.json` → `contribPlugins`: o `app-loader` baixa um JSON por plugin com `js`, `css`, `module` (módulo AngularJS) e templates, e injeta o módulo no app. Também há `themes`. Isso permite marca, CSS e novas rotas sem recompilar o taiga-front. Textos do núcleo (por exemplo, "Taiga" aparece em 85 linhas do locale pt-BR) exigem sobrescrita do locale ou build próprio do front (decidir na SPEC-01).

## Licenças e obrigações

| Repositório | Licença | Consequência |
|---|---|---|
| taiga-back, taiga-events, taiga-protected, taiga-docker | MPL-2.0 | Copyleft por arquivo: arquivos do Taiga modificados continuam MPL e com o código disponível a quem receber a distribuição. Código novo em arquivos próprios pode ter outra licença. |
| taiga-front | **AGPL-3.0** | Se a interface modificada for oferecida pela rede, inclusive só para uso interno de funcionários, é preciso oferecer o código-fonte correspondente aos usuários. Manter link "código-fonte" acessível no produto e o repositório disponível. |

Todos têm `DCOLICENSE` (contribuições com DCO) e cabeçalho `Copyright (c) 2021-present Kaleidos INC`. O rebranding precisa manter cabeçalhos, os arquivos `LICENSE` e uma atribuição ao Taiga em local apropriado (por exemplo, "Sobre" ou rodapé). "Taiga" é marca da Kaleidos: o nome público pode ser Vetor Sistemas, mas sem sugerir que é produto oficial do Taiga. Não é assessoria jurídica; validar com jurídico antes de distribuir para fora da empresa.

## Lacunas por especificação

N = nativo, C = configuração, D = desenvolvimento.

| Spec | Necessidade | Tipo | Observação |
|---|---|---|---|
| 01 | Nome Vetor Sistemas, logo, tokens de cor | C + D | `contribPlugins`/tema + sobrescrita de textos com "Taiga" |
| 01 | Shell com sidebar Clientes/Operação/Custos | D | rotas novas via plugin de front |
| 01 | Busca respeitando acesso | N | busca nativa já filtra; ampliar para clientes/documentos (D) |
| 01 | Filtros persistidos por usuário | N | userstorage |
| 02 | Contas nominais, desativação, revogação | N | `is_active` checado a cada requisição |
| 02 | Papéis por projeto | N | roles por projeto |
| 02 | Papel organizacional (gestor/observador em vários projetos) | D | não existe nível acima de projeto |
| 02 | Auditoria de troca de papel | D | o histórico nativo não registra memberships: feito na SPEC-02 (`vetor.Auditoria`) |
| 02 | MFA / SSO corporativo | D ou externo | sem suporte nativo |
| 03 | Cliente, contatos, documentos, reuniões | D | feito na SPEC-03 (app `vetor`); vínculo projeto ↔ cliente 1:N |
| 04 | Etapas configuráveis e modelos de fluxo | N + C | status por projeto e templates |
| 04 | Bloqueio com motivo | N | `is_blocked` + `blocked_note` |
| 04 | Responsável principal + colaboradores | N | `assigned_to` + `assigned_users` em histórias |
| 04 | Participação por etapa com início/fim | D | derivável do histórico, mas sem modelo próprio |
| 04 | Conflito de edição concorrente | N | OCC (`version`) |
| 04 | Ciclo do cliente separado | D | depende de 03 |
| 05 | Lembrete privado, conversão em tarefa | D | app novo |
| 05 | Token do agente por usuário | N (base) | application tokens; escopos finos são D |
| 06 | GitHub push/issues | N | HMAC-SHA1, síncrono, sem deduplicação |
| 06 | Pull requests, deduplicação, fila | D | |
| 06 | Azure | pendente | serviço Azure não definido |
| 07 | Uptime Kuma / Beszel → incidente | D | |
| 08 | Pós-venda, adoção | D | |
| 09 | Estimativas e custos | D | |
| 10 | Backup/restauração | C | `scripts/vetor.sh backup/restore` (demonstrado) |

## Mapa de objetos (existente → novo)

| Conceito das specs | Objeto |
|---|---|
| Organização | nenhum nativo; criar só quando houver segunda organização (hoje é única e implícita) |
| Cliente | **novo** (`vetor.clientes.Cliente`) |
| Contato, Documento, Reunião | **novos**, ligados a Cliente |
| Projeto | `projects.Project` (nativo) + vínculo opcional com Cliente (novo) |
| Demanda/card | `userstories.UserStory` (nativo) |
| Subtarefa/checklist | `tasks.Task` (nativo, um nível) |
| Etapa | `projects.UserStoryStatus` (nativo) |
| Responsável principal / colaboradores | `assigned_to` / `assigned_users` (nativos) |
| Participação por etapa | **novo** (registro de entrada/saída por pessoa e etapa) |
| Conversa | comentários do histórico (nativo) |
| Lembrete privado | **novo**, pertencente ao usuário |
| Incidente, evento de monitoramento | **novos** |
| Estimativa, custo realizado | **novos** |

## Riscos encontrados
- PostgreSQL 12, RabbitMQ 3.8 e nginx 1.19 fora de suporte nas versões oficiais. Atualizar exige migração de dados planejada (SPEC-10).
- `/media/exports/` era servido **sem token** pelo gateway oficial (proteção só pelo UUID no nome). **Corrigido na SPEC-02:** `infra/taiga-gateway.conf` + `vetor-protected/` (token assinado, validade `ATTACHMENTS_MAX_AGE`).
- **`ATOMIC_REQUESTS = True` do Taiga não tem efeito** (está no nível de settings, não em `DATABASES`): requisições não são transacionais e um erro no meio deixa escrita parcial. A Vetor torna transacionais as escritas de projetos, memberships, papéis e perfis (`vetor.api.TransacaoNaEscrita`, SPEC-02).
- **taiga-events aceitava qualquer assinatura:** qualquer usuário autenticado podia assinar `changes.project.<id>` de qualquer projeto (metadados) e `web_notifications.<id>` de outra pessoa (conteúdo das notificações). **Corrigido na SPEC-02:** `vetor-events/`.
- O `PUT` do userstorage exige a chave no corpo (sem ela devolve 400); para atualizar só o valor, use `PATCH`.
- As listagens do Taiga não chamam `check_permissions` (o escopo vem só dos filtros). Endpoints novos precisam checar permissão também em `list`.
- `SECRET_KEY` e senhas do `.env` oficial são fixas e fracas; substituídas por segredos aleatórios via `scripts/vetor.sh init-env`.
- Telemetria anônima da Kaleidos ligada por padrão no upstream; desligada aqui (`ENABLE_TELEMETRY=False`).
- Assinatura GitHub em SHA1 e webhooks de saída em HMAC-SHA1.
