# Entrega 06 — Repositórios e desenvolvimento

Data: 23/10/2026 • Branch: `spec-06-github` (sobre `spec-05-lembretes`)

## O que foi reaproveitado, configurado e desenvolvido
- **Validado antes de ampliar (nativo):** a integração GitHub do Taiga 6.10 foi testada.
  - Sem assinatura dá 400.
  - **Reenviar a mesma entrega de issue cria duas issues.**
  - PR é ignorado.
  - Usa SHA-1 e processa na hora.

  Ela continua disponível, só para o Administrador (SPEC-02), mas não atende aos critérios da spec.
- **Reaproveitado:** worker Celery do Taiga para processar e tentar de novo; auditoria; regras de acesso da SPEC-03 (`projetos_visiveis`).
- **Configurado:** `VETOR_GITHUB_WEBHOOK_SECRET` e `_ANTERIOR` (rotação). Vazio por padrão, ou seja, integração desligada.
- **Desenvolvido** (decisão 0009, `docs/integracoes/github.md`):
  - **Conector só de leitura, GitHub → Vetor.** A Vetor não escreve no GitHub e não guarda token dele.
  - **Webhook:**
    - `/api/v1/vetor/github/webhook`, com assinatura HMAC-SHA256 e deduplicação por `X-GitHub-Delivery`.
    - A entrega é guardada como chegou e processada no worker, com até 5 tentativas.
    - Depois disso vai para a fila de falhas, que pode ser reprocessada pela tela.
  - **Vínculos** (`VinculoCodigo`) de PR, commit e issue com a demanda citada por `TG-<ref>`:
    - Só do projeto do repositório.
    - O vínculo nunca volta a um estado mais antigo.
    - A edição do PR ou da issue que deixa de citar uma demanda remove o vínculo com ela.
    - Um repositório renomeado continua ligado pelo id do GitHub.
  - **Repositórios por projeto** (1:N), ligados e desligados pelo Administrador, com auditoria.
  - **Telas:**
    - Administração → "Repositórios (GitHub)": ligar, desligar, URL do webhook e fila de falhas com Reprocessar.
    - Demandas → botão **Código**: PRs, commits e issues da demanda, com estado e autor.

## Arquivos

| Arquivo | Mudança |
|---|---|
| `vetor-back/vetor/models.py`, `migrations/0007_github.py` | `Repositorio`, `EventoProvedor`, `VinculoCodigo` |
| `vetor-back/vetor/github.py` | webhook, assinatura, deduplicação, processamento e vínculos |
| `vetor-back/vetor/api_github.py`, `urls.py` | repositórios, vínculos e fila de entregas |
| `vetor-back/vetor/tasks.py`, `ajustes.py` | tarefa com novas tentativas; segredos do ambiente |
| `vetor-back/vetor/tests/test_github.py` | 15 testes novos (1 valida o nativo) |
| `vetor-front/administracao/index.html`, `vetor-front/demandas/index.html` | repositórios, fila de falhas, botão Código |
| `infra/docker-compose.override.yml`, `.env.example` | variáveis do segredo |
| `scripts/qa/github.js` | QA com entregas assinadas pelo webhook real e pelo worker |
| `docs/integracoes/github.md`, `docs/decisoes/0009-github-e-azure.md`, `docs/inventario-taiga.md`, `docs/arquitetura.md`, `docs/entregas/README.md` | direção da sincronização, decisão, atualizações |

**Migração:** `vetor.0007` cria três tabelas próprias. Nenhuma tabela do Taiga é alterada.

## Configuração necessária
Para ativar:
1. Gere o segredo do webhook com `openssl rand -hex 32` e ponha em `VETOR_GITHUB_WEBHOOK_SECRET`, no `.env`.
2. Ligue o repositório na Administração.
3. Configure o webhook no GitHub (ou num GitHub App, só leitura), como descrito em `docs/integracoes/github.md`.

O GitHub precisa alcançar a URL pública com HTTPS, o que depende da publicação autorizada (SPEC-10). **Nada foi configurado em nenhum repositório real do GitHub:** as entregas da QA foram simuladas e assinadas localmente.

## Critérios de aceite

| Critério | Resultado | Evidência |
|---|---|---|
| Evento legítimo cria/vincula o objeto correto | **Atendido.** PR com `TG-<ref>` vincula à demanda certa (número, estado, autor e entrega de origem). Também ligam push com commits e issue com `tg-<ref>`. Repositório desconhecido, `ping` e demanda de outro projeto com o mesmo número não ligam nada. | `test_evento_legitimo_…`, `test_push_vincula_…`, `test_nao_vincula_…`, `qa.txt` (item 2) |
| Reenvio não duplica | **Atendido.** A mesma entrega responde 200 `duplicado`, com 1 vínculo e 1 entrega gravados. O nativo, ao contrário, duplicou a issue. | `test_evento_legitimo_…`, `test_nativo_…`, `qa.txt` |
| Evento sem assinatura falha | **Atendido.** Sem assinatura, com assinatura de outro corpo ou SHA-1 dá 401, e nada é gravado. Sem segredo configurado dá 503. O segredo anterior vale durante a troca. | `test_sem_assinatura_…`, `test_sem_segredo_…`, `test_rotacao_…` |
| Falha permite retry sem perder origem | **Atendido.** Na falha, a entrega fica `falhou` com o erro e o payload. O "Redeliver" do GitHub ou o botão Reprocessar processam de novo a partir do conteúdo guardado. No ambiente, o worker agendou a nova tentativa sozinho. | `test_falha_no_processamento_…`, `test_reprocessar_…`, `fila-falhas-1440.png`, `logs.txt` |
| Token nunca no frontend/log | **Atendido.** Não há token do GitHub: a Vetor só lê. O segredo do webhook e a assinatura não aparecem nos logs nem em nenhuma resposta da API (teste), e o segredo aparece 0 vezes nos logs de back, worker e gateway. | `test_segredo_e_assinatura_…`, `logs.txt` |
| Documentar entidades e direção | **Atendido:** `docs/integracoes/github.md` traz a tabela entidade × campos × direção (só GitHub → Vetor). | — |
| PR draft/open/merged/closed; fechado sem merge não conclui; vários PRs com regra explícita | **Atendido.** Os quatro estados são registrados e uma entrega atrasada não volta o estado. A etapa da demanda não muda: a conclusão é confirmação manual, inclusive com vários PRs. Na tela, "merged (concluído)" e "fechado sem merge". | `test_estados_do_pr_…`, `demandas-codigo-1440.png`, `qa.txt` (item 3) |
| Links externos não concedem acesso | **Atendido.** Os vínculos só aparecem para quem vê a demanda (sem acesso: lista vazia; anônimo: 401). O link leva ao GitHub, que decide o acesso. | `test_vinculos_so_para_quem_…` |
| Azure sem conector genérico | **Atendido:** decisão 0009 separa Boards, Repos, Pipelines, Entra ID e infraestrutura. Nada foi implementado. | — |
| CI/CD separado do quadro | **Atendido:** fora do escopo, documentado. | `docs/integracoes/github.md` |

### QA (`qa.txt`)
```
1. ligar repositório pela Administração → ligado; URL do webhook mostrada
2. PR aberto → 202 · worker vinculou → pr #12 open · reenvio → 200 duplicado · sem assinatura → 401
3. estados → #12 merged, #13 closed · etapa mudou? false · total de vínculos → 2
4. Demandas → Código: PR #12 merged (concluído), PR #13 fechado sem merge
5. push malformado → 202 · fila → falhou, KeyError: 'url' · reprocessar pela tela → "Falhou de novo" (tentativas 2)
```

### Testes automáticos
- `vetor/tests`: **91 passaram** (15 novos).
- Suíte oficial ampliada: **994 passaram, 17 falharam**. As 17 são as mesmas divergências intencionais da SPEC-05, comparadas linha a linha, sem nenhuma falha nova (`evidencias/06/pytest.txt`).

## Problemas encontrados e corrigidos no caminho
- **Tentativas desatualizadas:** depois de reprocessar, o número de tentativas e o erro na fila não se atualizavam. A QA pegou; corrigido.
- **Auditoria:** a ação "lembrete.convertido" (SPEC-05) aparecia sem rótulo. Corrigido.

## Riscos e pendências
- **Sem automação de etapa por PR** (decisão 0009). Se quiserem, é preciso decidir o mapeamento (ex.: merged → Testes) e a regra com vários PRs.
- **Entrega atrasada:** se todas as citações de um PR já foram removidas, uma entrega antiga atrasada pode recriar o vínculo. É raro e está comentado no código como limitação conhecida.
- **Push muito grande:** o webhook de push traz no máximo 2048 commits (limite do GitHub). Commits além disso não são ligados; a Vetor não consulta a API do GitHub, porque não tem token.
- **Integração nativa:** ainda pode ser ativada pelo Administrador e é uma segunda origem de mudança de etapa (por mensagem de commit). Recomendado não usar.
- **Azure:** é preciso dizer qual serviço vocês usam.
- **Fila de falhas sem alerta:** só aparece na Administração. O alerta entra no monitoramento (SPEC-07).

## Reversão
Voltar a branch e rodar `./scripts/vetor.sh manage migrate vetor 0006`. Isso apaga repositórios, entregas e vínculos; nada muda no GitHub. Esvazie `VETOR_GITHUB_WEBHOOK_SECRET` para recusar entregas (503).
