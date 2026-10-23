# Manual do usuário — Vetor Sistemas

A barra lateral mostra só o que o seu papel permite: Visão geral, Clientes, Minhas demandas, Demandas, Projetos, Monitoramento, Custos (só o usuário matriz) e Administração (só o Administrador). A busca no topo da barra procura clientes, projetos e demandas que você pode ver.

## Papéis
| Papel | Pode |
|---|---|
| Administrador | tudo da organização: pessoas, papéis, auditoria, repositórios, monitoramento, saúde operacional |
| Gestor | cadastrar e editar clientes, criar projetos, gerir demandas e equipes dos seus projetos |
| Desenvolvedor | trabalhar nas demandas dos projetos em que participa |
| Observador | consultar o que lhe foi liberado |

O acesso a cada projeto continua sendo definido no próprio projeto, limitado pelo papel. **Custos** são fechados para o **usuário matriz**, definido no servidor; ninguém libera pela tela.

## Clientes
- **Lista:** busca por nome, razão social ou CNPJ, com filtros de responsável, ciclo (negociação, implantação, operação, encerrado) e arquivados.
- **Abas do cliente:**
  - **Resumo:** dados, código no sistema financeiro, **próximo contato** e última reunião ("abrir ata").
  - **Operação** (quatro sinais separados, sem "nota de saúde"):
    - *Relacionamento:* última reunião, próximo contato e pendências.
    - *Disponibilidade:* quedas dos monitores dos projetos do cliente.
    - *Infraestrutura:* alertas de CPU, memória e disco, com fonte e horário. Isso não é uso pelo cliente.
    - *Adoção:* último acesso, usuários ativos e funcionalidades, só quando o produto do cliente envia eventos. Sem eventos, aparece "Sem dados", e isso não é desuso.
  - **Custos** (só o usuário matriz): estimativas com versões, e orçamento × realizado do mês.
  - **Projetos, Contatos, Documentos** (privados; link temporário para baixar), **Reuniões** (ata, participantes, próximos passos e "criar demanda") e **Histórico**.

## Projetos e demandas
- **Novo projeto → Kanban (fluxo Vetor):** cria as etapas Entrada, Refinamento, A fazer, Desenvolvimento, Revisão, Testes, Concluído e Arquivado.
- **No card do Taiga:** responsável e colaboradores, comentários com @menção, bloqueio com motivo, prazo, anexos e histórico.
- **Demandas:**
  - Mostra todas as demandas que você acompanha, com filtros de cliente, projeto, responsável, prazo, bloqueadas e concluídas. Os filtros ficam salvos.
  - **"Mover para"** troca a etapa pelo teclado. Se outra pessoa mudou antes, nada é gravado e aparece o valor atual.
  - **Etapas** mostra quem participou de cada etapa.
  - **Código** mostra PRs, commits e issues do GitHub que citam `TG-<número>`. PR merged aparece como concluído, mas **a etapa não muda sozinha**.

## Minhas demandas e lembretes
- **Tarefas compartilhadas comigo:** demandas em que você é responsável ou colaborador.
- **Meus lembretes:** privados. Ninguém mais vê, nem administradores.
  - Têm vencimento no horário de Brasília e podem repetir todo dia, semana ou mês.
  - O e-mail é opcional.
  - O aviso aparece como número em "Minhas demandas" na barra lateral.
- **Virar demanda:** mostra antes o projeto, quem verá e o que será copiado. A demanda só é criada quando você confirma, e repetir não duplica.
- **Agente externo:** crie um token para um assistente criar lembretes ou demandas em seu nome. O token aparece uma vez só, e você pode revogá-lo a qualquer momento.

## Monitoramento
- **Incidentes** do Uptime Kuma e do Beszel nos seus projetos, com **linha do tempo**.
  - Quedas repetidas viram um incidente só.
  - Cair de novo logo depois de voltar reabre o mesmo.
  - A recuperação não conclui a demanda do incidente.
- **Administrador:**
  - **Conectores:** "Telemetria indisponível" significa que não há dados, nunca "no ar".
  - **Recursos em triagem:** escolha o projeto de cada monitor novo.
  - **Eventos com falha:** botão Reprocessar.

## Custos (usuário matriz)
- **Estimativa:** itens de custo ou preço de venda; fixo, variável ou ajuste em %; único ou mensal.
  - Valor = quantidade × preço unitário.
  - O ajuste incide só sobre fixo + variável do grupo.
  - "Criar nova versão" congela a anterior.
- **Orçamento × realizado:** diferença em R$ e em %, com alertas. Orçamento zero não calcula percentual. "Parcial" quer dizer consumo do mês em curso, não fatura.
- **Página Custos:**
  - Importar CSV: o mesmo lote não duplica, e uma linha com erro recusa tudo.
  - Custos não alocados.
  - Rateio do mês (partes somando 100%).
  - Taxas de câmbio, com data e origem.
  - Exportar.

## Administração (Administrador)
- **Saúde operacional:** alertas e estado dos conectores.
- **Pessoas:**
  - Criar conta: a pessoa define a própria senha por e-mail.
  - Papel e ativo/inativo.
  - A coluna "Financeiro" mostra quem é o matriz.
- **Repositórios (GitHub):** ligar ao projeto e ver a fila de falhas.
- **Auditoria:** quem fez o quê e quando, sem senhas, tokens, conteúdo de lembretes ou valores de custo.

## Dúvidas comuns
- **"Não vejo um cliente ou projeto":** você não participa do projeto, ou o cliente está fora do seu escopo. Peça a um gestor.
- **"Sumiu a referência do meu lembrete":** você perdeu o acesso àquele cliente ou projeto. O texto do lembrete continua seu.
- **"O PR foi aceito e a demanda não concluiu":** é de propósito. Mova a etapa quando confirmar.
