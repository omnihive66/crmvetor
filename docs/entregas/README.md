# Entregas — estado e pendências

Um relatório por entrega (`NN-*.md`), com critérios de aceite, evidências em `evidencias/NN/`, riscos e reversão.

## Estado
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
| 08 — Operação, pós-venda e adoção | Concluída com pendência: aba Operação do cliente com relacionamento, disponibilidade, infraestrutura e adoção separados; ingestão de uso pseudonimizada; sem dados ≠ desuso. Pendente: produtos reais enviarem eventos | `docs/entregas/08-pos-venda-adocao.md`, `docs/integracoes/telemetria-uso.md` |
| 09 — Estimativas e custos realizados | Concluída com pendência: estimativa versionada, realizado manual/CSV sem duplicar, rateio, orçamento × realizado com alertas e financeiro fechado para o usuário matriz. Pendente: AWS/Oracle (credenciais e contrato técnico) e nome do sistema financeiro | `docs/entregas/09-custos.md`, `docs/integracoes/custos.md` |
| 10 — Qualidade, operação e produção | Concluída, **sem publicar**: saúde operacional com alertas, correlation_id, rotação de logs, backup cifrado, restauração isolada demonstrada, CI, fluxo ponta a ponta, desempenho, acessibilidade (0 violações), manuais e plano de produção. Publicação aguarda autorização explícita | `docs/entregas/10-producao-governanca.md`, `docs/manual-operacao.md`, `docs/manual-usuario.md`, `docs/operacao/plano-producao.md` |

## Pendências que dependem de vocês (consolidado em 23/10/2026)
Nenhuma delas é simulada como se funcionasse: cada uma aparece como "não configurado", "contrato pronto" ou "não implementado" em Administração → Saúde operacional.

| Pendência | Bloqueia | Onde está documentado |
|---|---|---|
| Autorização e infraestrutura para produção (servidor, domínio, TLS, SMTP, destino do backup e guarda da chave) | publicação | `docs/operacao/plano-producao.md` |
| Login do usuário matriz do financeiro em produção | acesso a custos | `docs/manual-operacao.md` §2 |
| Tecnologia do agente externo | integração do agente (o contrato HTTP está pronto) | `docs/agente.md` |
| Serviço Azure (Boards, Repos, Pipelines, Entra ID ou infraestrutura) | conector Azure | decisão 0009 |
| Nome/URL do sistema financeiro | link e rótulo do financeiro | SPEC-03, SPEC-09 |
| AWS/Oracle: credenciais de leitura, mapeamento tag → cliente e contrato técnico | importação automática de custos (CSV disponível) | `docs/integracoes/custos.md` |
| Provedor de MFA/SSO | MFA/SSO | decisão 0006 |
| Antivírus para uploads e políticas de retenção (documentos, auditoria) | proteção de uploads e retenção | SPEC-03 |
| Produtos dos clientes enviarem eventos de uso, e o que é "atividade" em cada um | números de adoção | `docs/integracoes/telemetria-uso.md` |
| Configurar Kuma, Beszel e GitHub reais (exige URL pública) | incidentes e vínculos de código reais | `docs/integracoes/` |
| Mapeamento de etapa automática por PR (se desejado) | automação de etapa | decisão 0009 |
| Validar RPO 24 h / RTO 2 h, licença dos arquivos da Vetor e repositório público | governança | `docs/manual-operacao.md` §4, `docs/operacao/dependencias.md` |
