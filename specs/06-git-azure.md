# SPEC-06 — Repositórios e desenvolvimento

## Resultado
Projeto e demanda se relacionam com código sem centralizar credenciais desnecessárias no CRM.

## Implementação
Primeiro conector: GitHub. Validar o comportamento da integração nativa na versão instalada antes de ampliar. Outros provedores via adaptadores. Relação inicial 1:N entre projeto e repositórios; N:N apenas se a necessidade for confirmada. Vincular issues, commits e pull requests por identificadores estáveis, URL do provedor e referência de tarefa.

Definir uma direção de sincronização por entidade/campo. Preservar origem e responsável pela última alteração; impedir loops. Se houver automação de PR, mapear draft/open/merged/closed às etapas do projeto, sem considerar PR fechado sem merge como concluído. Vários PRs ligados a uma tarefa exigem regra de conclusão explícita, por padrão confirmação manual.

Autenticação preferencial com instalação de app e permissões mínimas quando suportado. Segredos no servidor, rotação, validação de assinatura de webhook, deduplicação por evento, processamento assíncrono e fila de falhas. Links externos não concedem acesso ao repositório.

Azure permanece dependência de refinamento: distinguir Azure DevOps Boards/Repos/Pipelines, Microsoft Entra ID e infraestrutura Azure. Não criar um conector genérico fingindo atender todos.

## Aceite
Evento legítimo cria/vincula o objeto correto; reenvio não duplica; evento sem assinatura falha; falha do provedor permite retry sem perder origem. Token nunca aparece no frontend/log. Documentar claramente quais entidades sincronizam e em qual direção. Pipeline CI/CD é integração separada do quadro de tarefas e exige escopo próprio.
