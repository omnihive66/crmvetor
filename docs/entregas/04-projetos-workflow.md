# Entrega 04 — Projetos, fases e colaboração

Data: 22/10/2026 • Spec: `specs/04-projetos-workflow.md` • Branch: `spec-04-projetos` (sobre `spec-03-clientes`)

## O que foi reaproveitado, configurado e desenvolvido
- **Reaproveitado (nativo):**
  - Projetos, histórias e tarefas (subtarefas de um nível).
  - Responsável principal e colaboradores.
  - Bloqueio com motivo, prazo, tags, anexos.
  - Comentários com menções e histórico de edição, e o histórico de mudanças separado da conversa.
  - OCC, etapas editáveis por projeto e duplicação de projeto como modelo.
  - Vínculo cliente↔projeto da SPEC-03, com projeto interno sem cliente. O ciclo do cliente continua separado das etapas das tarefas.
- **Configurado:** modelo de projeto **"Kanban (fluxo Vetor)"** (decisão 0007) com as etapas da spec em português e cores acessíveis, papéis de projeto Gestão, Desenvolvimento e Observação, e o campo opcional **Prioridade**. A opção Kanban da tela "Novo projeto" usa esse modelo. A newsletter do taiga.io foi desligada (`isSaas`): ela abria um pop-up ao criar projeto.
- **Desenvolvido:**
  - **Participação por etapa** (`ParticipacaoEtapa`): quem esteve em cada etapa, de quando até quando e quem fez cada mudança. É gerada sozinha a partir de etapa, responsável e colaboradores.
  - **API:**
    - `/vetor/demandas`: histórias de todos os projetos visíveis, com filtros de cliente, projeto, responsável, prazo, bloqueio e concluídas.
    - `/vetor/participacoes`.
  - **Tela Demandas** (`/vetor/demandas/`, item na barra lateral): filtros salvos por pessoa, link para o card no Taiga, botão **Etapas** (participação) e seletor **"Mover para"**. O seletor é a alternativa por teclado ao arrastar, com OCC; em conflito, a linha mostra o que está gravado.

## Arquivos

| Arquivo | Mudança |
|---|---|
| `vetor-back/vetor/migrations/0004_modelo_fluxo_vetor.py` | modelo de projeto 1001 a partir do kanban oficial |
| `vetor-back/vetor/models.py`, `migrations/0005_participacao_etapa.py`, `participacao.py`, `apps.py` | participação por etapa |
| `vetor-back/vetor/sinais.py` | opções do campo Prioridade |
| `vetor-back/vetor/api_projetos.py`, `urls.py` | demandas e participações |
| `vetor-back/vetor/tests/test_projetos.py` | 8 testes novos |
| `vetor-front/demandas/index.html`, `ui/shell.js` | tela Demandas e item na barra lateral |
| `vetor-front/build.py`, `locale/pt-br.json` | Kanban → modelo 1001; textos da opção; `isSaas` |
| `scripts/qa/projetos.js` | QA pela interface |
| `docs/decisoes/0007`, `docs/inventario-taiga.md`, `docs/arquitetura.md`, `RASTREABILIDADE.md` | atualizados |

**Migrações:** `vetor.0004` (insere o modelo de projeto 1001; reversível) e `vetor.0005` (tabela `vetor_participacaoetapa`). Nenhuma tabela do Taiga é alterada. Projetos existentes **não** mudam de etapas: o modelo vale para projetos novos.

## Configuração necessária
Nenhuma.

## Critérios de aceite

| Critério | Resultado | Evidência |
|---|---|---|
| Gestor cria demanda, dev pergunta no card, gestor responde, responsáveis são atualizados e a tarefa avança preservando histórico | **Atendido.** Os dois comentários ficam em ordem no histórico, e as mudanças de responsáveis e de etapa são entradas separadas da conversa. | `test_gestor_cria_dev_pergunta_…` |
| Dois devs podem colaborar na mesma etapa | **Atendido.** Dois intervalos abertos na mesma etapa. Ao avançar, os dois são fechados com fim e autor, e ao tirar um colaborador o intervalo dele é fechado. | `test_dois_devs_na_mesma_etapa_…`, `participacao-1440.png` |
| Nenhum campo extra bloqueia avanço por padrão | **Atendido.** Avança sem Prioridade; o modelo não tem campos obrigatórios. | mesmo teste |
| Reordenação e drag-and-drop com alternativa por teclado | **Atendido** na tela Demandas: com o foco no "Mover para" e uma seta, gravou "Desenvolvimento". O arrastar do quadro do Taiga continua igual. | `qa.txt` (item 2) |
| Movimentação falha sem deixar interface e banco divergentes | **Atendido:** <ul><li>Conflito real: outra pessoa mudou a etapa e a tela tinha a versão antiga. A API recusou, e o seletor e a coluna Etapa passaram a mostrar a etapa gravada ("Revisão").</li><li>Mover sem permissão no quadro (`bulk_update_kanban_order`): 403, banco inalterado.</li><li>Na API, a edição concorrente do mesmo campo é recusada.</li></ul> | `qa.txt` (item 3), `demandas-conflito-1440.png`, `test_edicao_concorrente_…`, `test_movimento_recusado_…` |
| Filtros por cliente, projeto, responsável, prazo e bloqueio | **Atendido.** Todos combináveis, e o colaborador conta como responsável. Concluídas ficam fora por padrão. Quem não tem acesso aos projetos recebe lista vazia. | `test_demandas_filtram_…` |
| Fluxo sugerido e modelos de fluxo por projeto | **Atendido.** Criado pela tela "Novo projeto → Kanban (fluxo Vetor)", o quadro saiu com Entrada, Refinamento, A fazer, Desenvolvimento, Revisão, Testes, Concluído e Arquivado. | `quadro-fluxo-vetor-1440.png`, `test_modelo_vetor_…` |
| "Bloqueado" como sinalização com motivo, sem apagar a etapa | **Atendido** (nativo; rótulo em texto desde a SPEC-01) | `test_bloqueio_…` |

### QA pela interface (`qa.txt`)
```
1. opção Kanban na tela → Kanban (fluxo Vetor) · Entrada → Refinamento → A fazer → Desenvolvimento → Revisão → Testes → Concluído
   colunas criadas → Entrada | Refinamento | A fazer | Desenvolvimento | Revisão | Testes | Concluído | Arquivado
2. teclado (seta para baixo) → Movida. · etapa gravada → Desenvolvimento
3. conflito → "Outra pessoa mudou esta demanda antes…" · select: Revisão · coluna Etapa: Revisão · banco: Revisão
4. participação → A fazer (fechada) · Desenvolvimento (fechada) · Revisão (em andamento), com horário e autor
```

### Testes automáticos
- `vetor/tests`: **58 passaram** (8 novos).
- Suíte oficial ampliada (agora com histórico, campos personalizados de história e ordenação do kanban): **923 passaram, 17 falharam**. São as 16 divergências intencionais de antes, mais uma esperada: um teste oficial conta os modelos de projeto e não conhece o modelo Vetor (`evidencias/04/pytest.txt`).

## Problemas encontrados e corrigidos no caminho
- **Pop-up da newsletter:** a tela "Novo projeto" abria o convite para a newsletter do taiga.io. Desligado com `isSaas`.
- **Divergências de tela que eu tinha introduzido:** a QA pegou duas. Depois de um conflito, o seletor voltava ao valor antigo, e a coluna Etapa nunca se atualizava. Agora ambos mostram o que está gravado.
- **Modelo oficial sobrescrito a cada início:** o modelo "kanban" oficial é recarregado no boot, por isso a Vetor tem um modelo próprio.
- **OCC parcial:** o OCC do Taiga só compara os campos alterados, pelo histórico. Uma mudança em campo diferente com versão antiga é aceita (comportamento do Taiga, coberto no teste).

## Riscos e pendências
- **Projetos existentes** continuam com as etapas antigas (Novo, Pronto…, com contraste baixo em amarelo). Ajustar manualmente em Configurações → Atributos, ou recriar a partir do modelo.
- **Participação por etapa:** é visível na tela Demandas, não dentro do card do Taiga. Também começa a contar a partir desta versão; mudanças anteriores aparecem só no histórico nativo.
- **Quadro do Taiga:** o arrastar continua sem OCC. Dois movimentos simultâneos do mesmo card no quadro: vale o último, e o card fica certo para quem recarregar. O seletor "Mover para" usa OCC.
- **Textos do Taiga sem tradução:** "subject or reference" e o texto de exemplo do quadro vazio ("This could be a user story…") continuam em inglês.
- **Prioridade:** um campo lista chamado "Prioridade" criado sem opções em qualquer projeto recebe as opções padrão.

## Reversão
Voltar a branch e rodar `./scripts/vetor.sh manage migrate vetor 0003`. Isso apaga a participação por etapa e o modelo 1001; os projetos já criados com ele continuam funcionando. Com o front anterior, a opção Kanban volta a usar o modelo oficial.
