# SPEC-05 — Minhas demandas, lembretes e agente

## Resultado
Cada pessoa organiza compromissos de trabalho e pode transformá-los em demanda compartilhada de maneira explícita.

## Implementação
Lembrete privado: proprietário, título, notas, vencimento opcional, recorrência se viável, estado e referência opcional a cliente/projeto/tarefa. Notificação interna como canal inicial; e-mail opcional configurável. Definir fuso horário, reagendamento e idempotência para impedir notificações repetidas. Lista “Minhas demandas” separa tarefas compartilhadas de lembretes privados.

Converter lembrete em tarefa deve mostrar prévia, destino, visibilidade e quais campos serão copiados; a origem privada permanece privada. Preferir operação transacional, com repetição segura. Ao revogar acesso a projeto, remover previews e dados derivados do vínculo, mantendo apenas conteúdo próprio que não exponha dados restritos.

Agente externo: endpoint autenticado para criar lembrete em nome do titular; cliente não pode forjar owner_id. Escopos distintos para lembrete privado e tarefa compartilhada. Solicitação ambígua retorna necessidade de esclarecimento, sem inventar cliente ou projeto. Chave de idempotência, limites de requisição e logs sem conteúdo privado. Definir contrato do agente após descobrir a tecnologia existente.

## Aceite
Usuário B, incluindo gestor, não consulta lembrete de A por lista, ID, exportação, busca ou notificação. Converter exige ação clara e gera um único item mesmo após retry. Notificação ocorre no fuso esperado. Integração não possui token global capaz de assumir qualquer pessoa sem autorização.
