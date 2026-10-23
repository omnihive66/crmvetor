# 0007 — Fluxo de etapas, prioridade e participação por etapa

- Data: 22/10/2026 • Estado: aceita

## Fluxo
O modelo de projeto **"Kanban (fluxo Vetor)"** (`vetor.0004`, id fixo 1001) tem:
- **Etapas:** Entrada → Refinamento → A fazer → Desenvolvimento → Revisão → Testes → Concluído (+ Arquivado). As cores têm contraste ≥ 4,5:1 sobre branco, porque o Taiga também usa a cor da etapa como cor de texto.
- **Papéis de projeto:** Gestão (dono, administra), Desenvolvimento e Observação (só leitura, compatível com o teto do Observador da SPEC-02).
- **Prioridade:** campo opcional (Baixa, Média, Alta, Urgente) que não bloqueia o avanço.

Por que um modelo novo, em vez de alterar o "kanban" oficial: o entrypoint do Taiga roda `loaddata initial_project_templates` a cada início e sobrescreveria a alteração. O formulário de criar projeto do front usa o id do modelo direto no código, então `vetor-front/build.py` troca o id 2 por 1001 na opção Kanban. O Scrum oficial continua disponível.

O modelo de projeto do Taiga não guarda as opções de campo lista (`extra`): um signal preenche as opções de "Prioridade" quando o campo é criado sem elas.

Cada projeto continua podendo editar as próprias etapas (Configurações → Atributos) e ser duplicado como modelo de outro projeto, ambos recursos nativos.

## O que é nativo do Taiga e foi mantido
- Bloqueio como sinalização com motivo (`is_blocked`, `blocked_note`), sem mudar de etapa.
- Responsável principal (`assigned_to`) e colaboradores (`assigned_users`).
- Tarefas como subtarefas (um nível).
- Comentários com menções e histórico de edição.
- Mudança de etapa e de responsável registradas no histórico, separadas da conversa.
- OCC (`version`). O Taiga só recusa quando os **mesmos campos** mudaram entre a versão lida e a atual. Mudar campos diferentes com uma versão antiga é aceito.

## Participação por etapa
`ParticipacaoEtapa` é gerada pelos signals de história (status) e de colaboradores (`m2m_changed`):
- Cada pessoa (responsável ou colaborador) numa etapa aberta tem um intervalo com início, fim e o autor de cada mudança.
- Etapas concluídas fecham tudo.
- Os registros não se editam à mão.
- O nome da etapa e o da pessoa ficam gravados no registro, para sobreviver a renomeação ou exclusão.

## Filtros entre projetos e alternativa ao arrastar
- A tela **Demandas** (`/vetor/demandas/`) lista as histórias de todos os projetos onde a pessoa tem `view_us`. Filtros: cliente, projeto, responsável (principal ou colaborador), prazo (vencidas, 7 dias, sem prazo), bloqueadas e concluídas. Os filtros ficam salvos por pessoa.
- O seletor "Mover para" é a alternativa ao arrastar, operável por teclado. Ele usa a versão (OCC). Em erro ou conflito, a linha busca a demanda no servidor e mostra a etapa gravada.
