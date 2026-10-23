# 0009 — Conector GitHub só de leitura; Azure sem conector

- Data: 23/10/2026 • Estado: aceita

## Contexto
A integração GitHub nativa do Taiga 6.10 foi validada por teste (inventário):
- usa SHA-1;
- é síncrona;
- não deduplica: o reenvio cria uma issue duplicada;
- não trata PRs;
- guarda o segredo por projeto no banco.

Ela não atende à spec (reenvio sem duplicar, processamento assíncrono, fila de falhas, PRs).

## Decisão
- **Conector próprio, só GitHub → Vetor** (`vetor/github.py`). Ele recebe webhooks e mantém vínculos de PR, commit e issue com as demandas citadas por `TG-<ref>`.
- **Sem escrita no GitHub:**
  - Sem token do GitHub no CRM; só o segredo do webhook, no ambiente do servidor.
  - É o menor conjunto de credenciais possível, e não existe loop de sincronização.
  - Um GitHub App, se usado, precisa só de permissões de leitura.
- **Etapa nunca muda sozinha:**
  - PR merged aparece como concluído, e uma pessoa confirma movendo a etapa.
  - PR fechado sem merge nunca conclui.
  - Com vários PRs, a regra é confirmação manual.
- **Relação 1:N** entre projeto e repositórios. Um repositório pertence a um projeto só; N:N espera necessidade confirmada.
- **Dados:**
  - Cada entrega fica guardada (`EventoProvedor`): é a origem e permite reprocessar.
  - Um vínculo nunca regride para estado mais antigo (data do GitHub).
  - Vínculos só com demandas do projeto do repositório.
- **Ligar repositório é do Administrador da organização,** coerente com webhooks e integrações na SPEC-02.

## Azure
"Azure" pode ser coisas diferentes, e nenhuma foi feita:
- **Azure DevOps Boards:** quadro de tarefas, concorrente do Taiga. Integrar seria sincronizar tarefas nos dois sentidos, a decidir.
- **Azure Repos:** Git. Seria um novo adaptador do conector (assinatura e formato de evento próprios do Azure DevOps service hooks).
- **Azure Pipelines:** CI/CD. É integração separada do quadro (spec).
- **Microsoft Entra ID:** identidade (SSO). Pertence à pendência de SSO da SPEC-02, não a esta.
- **Infraestrutura Azure:** onde publicar (SPEC-10).

Um conector "Azure" genérico não foi criado, para não fingir atender a todos.

## Consequências
- Pessoas usam `TG-<ref>` no GitHub. Sem a citação, nada é ligado, e não há adivinhação por título.
- A URL do webhook precisa ser pública com HTTPS. Isso depende da publicação autorizada (SPEC-10).
