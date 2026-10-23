# GitHub — o que sincroniza e como configurar (SPEC-06)

## Direção
**Uma só direção: GitHub → Vetor.** A Vetor não escreve no GitHub, não guarda token do GitHub e não muda etapa de demanda por causa de código. Por isso não há loop possível.

| Entidade no GitHub | Na Vetor | Campos (todos vindos do GitHub) | Quem pode mudar na Vetor |
|---|---|---|---|
| Pull request | vínculo `pr` na demanda citada | número, título, URL, estado (`draft`, `open`, `merged`, `closed`), autor, atualizado em | ninguém (só leitura) |
| Commit (push) | vínculo `commit` | sha, primeira linha da mensagem, URL, autor, data | ninguém |
| Issue | vínculo `issue` | número, título, URL, estado (`open`, `closed`), autor, atualizado em | ninguém |
| Repositório | `Repositorio` ligado a um projeto (1:N) | nome `dono/repo` e id numérico (renomear no GitHub não quebra) | Administrador liga e desliga |
| Etapa, responsáveis e demais campos da demanda | — | — | só pessoas, na Vetor |

- **Como liga:** cite `TG-<número da demanda>` no título ou na descrição do PR, no nome da branch, na mensagem do commit ou no título/corpo da issue. Só vale para demandas do **projeto do repositório**.
- **Edição:** se o título ou a descrição do PR ou da issue deixar de citar uma demanda, o vínculo com ela some.
- **Ordem:** cada vínculo guarda a data de atualização do GitHub. Uma entrega antiga que chegue depois de uma nova é ignorada.
- **Origem:** cada vínculo aponta para a entrega que o criou ou mudou por último. A entrega fica guardada como chegou.

## Regra de conclusão
- A Vetor **não move a etapa** da demanda por causa de PR. A demanda mostra os PRs com o estado ("merged (concluído)", "fechado sem merge"), e uma pessoa confirma a conclusão movendo a etapa.
- **PR fechado sem merge nunca conta como concluído.**
- Com vários PRs na mesma demanda, vale o mesmo: confirmação manual (padrão da spec).
- Automação de etapa por PR fica para quando a regra for decidida: quais etapas, e se vale "todos os PRs merged" ou "qualquer um".

## Segurança
- **Segredo:**
  - Só o do webhook, em `VETOR_GITHUB_WEBHOOK_SECRET` no `.env` do servidor. Vazio significa integração desligada (503).
  - Nunca vai para o navegador, para a API nem para o log; os testes conferem isso.
- **Assinatura:** `X-Hub-Signature-256` (HMAC-SHA256), comparada em tempo constante. Sem assinatura ou com assinatura errada dá 401, e nada é gravado.
- **Rotação:**
  1. Copie o segredo atual para `VETOR_GITHUB_WEBHOOK_SECRET_ANTERIOR`.
  2. Ponha o novo em `VETOR_GITHUB_WEBHOOK_SECRET` e rode `./scripts/vetor.sh up`.
  3. Troque no GitHub.
  4. Esvazie `_ANTERIOR` e suba de novo.
- **Deduplicação:** pelo `X-GitHub-Delivery`. Uma entrega repetida responde `duplicado` e não cria nada. Se a original tinha falhado, o "Redeliver" do GitHub tenta processar de novo.
- **Processamento:**
  - Assíncrono, no worker (`taiga-async`). O webhook responde 202 assim que guarda a entrega.
  - Em caso de falha: até 5 tentativas (2, 4, 8 e 16 min).
  - Depois disso, a entrega fica na **fila de falhas** (Administração → Repositórios), com o erro e o botão Reprocessar, que usa o conteúdo guardado.
- **Acesso:** o link não dá acesso ao repositório. Quem vê a demanda vê o título e a URL; abrir o código depende da permissão no GitHub.
- **Log:** id da entrega, evento e status. Nada do conteúdo.

## Configurar
1. `openssl rand -hex 32` → `VETOR_GITHUB_WEBHOOK_SECRET` no `.env`, depois `./scripts/vetor.sh up`.
2. Administração → Repositórios: ligue `dono/repo` ao projeto.
3. No GitHub, configure o webhook do repositório (ou de um **GitHub App**, preferível para vários repositórios):
   - **Payload URL:** `https://<seu-domínio>/api/v1/vetor/github/webhook`.
   - **Content type:** `application/json`.
   - **Secret:** o mesmo do `.env`.
   - **Eventos:** *Pull requests*, *Pushes* e *Issues*.
   - **Permissões de um GitHub App:** só leitura de *Metadata*, *Pull requests*, *Contents* (para push) e *Issues*. Nenhuma de escrita.
4. Para o GitHub alcançar o servidor, a URL precisa ser pública com HTTPS. Isso é parte da publicação (SPEC-10), que exige autorização.

## Integração nativa do Taiga
O módulo GitHub do próprio Taiga (Configurações do projeto → Integrações) continua disponível, só para o Administrador. Ele:
- muda a etapa pela mensagem do commit (`TG-12 #closed`);
- cria issues do Taiga a partir de issues do GitHub.

Ele usa SHA-1, processa na hora, não deduplica e ignora PRs. Uma issue reenviada vira duas no Taiga. Prefira o conector da Vetor. Se usar o nativo no mesmo repositório, saiba que ele é uma segunda origem de mudança de etapa.

## Fora do escopo
- **Pipelines de CI/CD:** integração separada, com escopo próprio (spec), não ligada ao quadro de tarefas.
- **Outros provedores** (GitLab, Bitbucket, Azure Repos): entram como novos adaptadores de `vetor/github.py` (mesmo modelo de dados, `provedor` diferente). Nenhum foi feito.
