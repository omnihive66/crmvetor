# Rastreabilidade

| Origem | Pedido | Especificação |
|---|---|---|
| 10:29:12 | Contas individuais, repasse de função, quadro, conversas e Git | 02, 04, 06 |
| 10:30:38 | Projetos, etapas, vários responsáveis e GitHub/Azure | 04, 06 |
| 10:31:27 | Visões de desenvolvedor e gestor | 01, 02 |
| 10:32:45 | Demandas administrativas, integração com agente, virar projeto | 03, 04, 05 |
| 10:34:21 | Lembretes privados, minitarefas e notificações | 04, 05 |
| 10:37:59 | Dados do cliente, documentos e financeiro separado | 03, 09 |
| 10:40:33 | Pós-venda, última reunião, banco, uso e último acesso | 07, 08 |
| 10:41:55 e cópia (1) | Cards por cliente, abas, etapas flexíveis sem obrigatoriedade | DESIGN, 03, 04 |
| 10:43:21 | Anotações, planejamento, POC, versão 1 e saúde | 03, 04, 08, 09 |
| 10:44:05 | Calculadora de gastos | 09 |
| 10:45:55 | AWS/Oracle e previsto versus realizado | 09 |
| Conversa | Uptime Kuma e Beszel | 07 |
| Pedido atual e imagem | Nome Vetor Sistemas, logo e acabamento premium | DESIGN, 01 |

## Questões para refinamento, sem bloquear especificação
- Confirmar se “berzel” é Beszel e qual o sistema financeiro mencionado.
- Identificar versão/instalação do Taiga e provedor de repositórios.
- Definir serviço Azure e contrato do agente existente.
- Confirmar usuários, papéis e escopos; usar nomes nominais após validação.
- Informar fontes disponíveis de auditoria/uso e credenciais de integração em canal seguro.
- Definir orçamento, política de retenção e metas operacionais.

Essas respostas bloqueiam apenas a parte técnica dependente; não justificam simular integrações como se funcionassem.

## Estado das entregas

| Spec | Estado | Relatório |
|---|---|---|
| 00 — Auditoria e fundação | Concluída: instalação, login, inventário, testes e backup verificados | `docs/entregas/00-fundacao.md` |
| 01 — Identidade e experiência | Concluída com pendências: barra lateral global e busca global adiadas (decisão 0005), cabeçalho gráfico dos e-mails | `docs/entregas/01-identidade-interface.md` |
| 02 — Identidades e permissões | Concluída: papéis com teto, Administração, auditoria e correções de eventos e exportações. Pendentes: MFA/SSO (provedor), lembretes privados chegam na SPEC-05 | `docs/entregas/02-usuarios-permissoes.md` |
| 03 — Clientes, documentos e reuniões | Concluída: CRM com escopo de acesso, documentos privados, reuniões que viram demanda, busca global e barra lateral. Pendentes: antivírus, retenção e nome do sistema financeiro | `docs/entregas/03-clientes-documentos.md` |
| 04 — Projetos, fases e colaboração | Concluída: modelo de fluxo Vetor, participação por etapa, Demandas com filtros e alternativa por teclado ao arrastar | `docs/entregas/04-projetos-workflow.md` |
| 05 — Minhas demandas, lembretes e agente | Concluída com pendência: lembretes privados com aviso no fuso de Brasília, conversão com prévia e sem duplicar, tokens pessoais por escopo e contrato HTTP do agente. Pendente: conectar o agente real (tecnologia não informada) | `docs/entregas/05-lembretes-agente.md`, `docs/agente.md` |
| 06 — Repositórios e desenvolvimento | Concluída com pendência: conector GitHub só de leitura (webhook assinado, deduplicado, assíncrono, com fila de falhas) que liga PRs, commits e issues às demandas. Pendente: Azure (serviço não definido) e CI/CD (integração separada) | `docs/entregas/06-git-azure.md`, `docs/integracoes/github.md` |
| 07 — Monitoramento | Concluída com pendência: Kuma e Beszel viram incidentes com linha do tempo, triagem, janela antirruído, aviso com frequência, fila de falhas e telemetria indisponível explícita. Pendente: configurar os provedores reais (URL pública) | `docs/entregas/07-monitoramento.md`, `docs/integracoes/monitoramento.md` |
| 08 a 10 | Não iniciadas | — |
