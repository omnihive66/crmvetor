# SPEC-02 — Identidades e permissões

## Resultado
Cada pessoa usa conta nominal, com escopo por organização, projeto e ação.

## Matriz inicial
| Ação | Administrador | Gestor | Desenvolvedor | Observador |
|---|---|---|---|---|
| Configurar organização e integrações | Sim | Não | Não | Não |
| Gerenciar clientes | Sim | No escopo | Leitura no escopo | Leitura no escopo |
| Criar/atribuir demandas | Sim | No escopo | Conforme papel do projeto | Não |
| Atualizar/comentar tarefas | No escopo | No escopo | No escopo | Não |
| Consultar custos | Permissão explícita | Permissão explícita | Permissão explícita | Permissão explícita |
| Ler lembrete privado de outro usuário | Não | Não | Não | Não |

## Implementação
Combinar papel organizacional e participação no projeto; negar por padrão. Validar no backend em listagens, detalhes, downloads, busca, exportação e eventos em tempo real. Remover acesso de sessões e tokens conforme o mecanismo de revogação disponível. A conta “matriz” representa uma visão gerencial via papel, não uma senha compartilhada. Conectores usam contas de serviço com escopo mínimo. MFA e SSO: investigar suporte real e registrar implementação/dependência, sem prometer disponibilidade nativa.

## Aceite
Testes de acesso cruzado entre usuários/projetos, IDs diretos, anexos e busca. Desativar usuário impede novas ações autorizadas. Alterações de papel ficam auditadas. Administrador técnico não recebe acesso funcional a lembretes privados; acesso de infraestrutura ao banco é um limite técnico explicitado, sem promessa de criptografia ponta a ponta.
