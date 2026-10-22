# SPEC-04 — Projetos, fases e colaboração

## Resultado
Demandas fluem por etapas configuráveis com discussão e responsáveis claros.

## Implementação
Reutilizar projetos, histórias/tarefas, comentários e anexos confirmados no inventário. Um cliente pode ter vários projetos; projetos internos podem não ter cliente. Fluxo inicial sugerido: Entrada → Refinamento → A fazer → Desenvolvimento → Revisão → Testes → Concluído. “Bloqueado” preferencialmente é sinalizador com motivo, evitando apagar a etapa atual. Oferecer modelos de fluxo por projeto.

Separar o ciclo do cliente (Negociação, Implantação, Operação, Encerrado) do estado das tarefas. Dentro de tarefa, permitir subtarefas/checklists sem hierarquia infinita. Responsável principal, colaboradores e participação por etapa com data inicial/final e autor da alteração. Evitar reaproveitar significado de campos nativos de forma incompatível.

Cards: título, descrição, prioridade, prazo opcional, responsável, colaboradores, tags, anexos e conversa. Comentários cronológicos com menções autorizadas e histórico de edição quando implementado. Registro de mudança de fase e responsável é evento distinto da conversa. Movimentos concorrentes usam controle de versão e retorno de conflito.

## Aceite
Gestor cria demanda, dev pergunta no card, gestor responde, responsáveis são atualizados e a tarefa avança preservando histórico. Dois devs podem colaborar na mesma etapa. Nenhum campo extra bloqueia avanço por padrão. Reordenação/drag-and-drop tem alternativa por teclado. Movimentação falha sem deixar interface e banco divergentes. Filtros por cliente, projeto, responsável, prazo e bloqueio.
