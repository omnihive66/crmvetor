# Direção visual — Vetor Sistemas

## Identidade
A marca será Vetor Sistemas na interface, login, título do navegador e comunicações geradas pelo produto. Preservar avisos e atribuições exigidos pelas licenças do código e dependências. Não alterar nomes técnicos de pacotes e tabelas só para trocar a marca.

Utilizar a logo original enviada, sem redesenhar letras, distorcer, recolorir ou adicionar efeitos. A imagem é um JPEG quadrado com margem preta: aplicar enquadramento visual por CSS, sem esticar. No cabeçalho, área máxima sugerida de 160 × 48 px, fundo preto e objeto proporcional; validar legibilidade real, pois as margens do arquivo podem exigir um ativo oficial mais adequado. Não remover fundo por ferramentas improvisadas. Solicitar SVG/PNG oficial como melhoria opcional, sem bloquear o protótipo. Até existir símbolo autorizado, usar favicon tipográfico V; não extrair arbitrariamente parte da marca.

## Linguagem premium
Interface sóbria, hierarquia clara, dados legíveis e poucos destaques. Barra lateral escura, área de trabalho clara por padrão e verde para ações principais. Tema escuro opcional após validar os tokens. Sem excesso de gradientes, efeitos de vidro ou animações decorativas. Visão executiva deve mostrar decisões, responsáveis e pendências, não cartões sem função.

## Tokens propostos
| Token | Valor | Aplicação |
|---|---|---|
| brand | #00D47A | destaque visual e marca |
| action | #087443 | botão com texto branco |
| sidebar | #090D0B | navegação |
| canvas | #F5F7F6 | fundo |
| surface | #FFFFFF | tabelas e cartões |
| text | #14221B | texto principal |
| muted | #52645A | texto secundário |
| border | #DCE5DF | divisores |
| danger | #B42318 | falhas |
| warning | #8A5700 | atenção |
| info | #175CD3 | informação |

Valores aproximados da referência, sem alegar extração colorimétrica. Validar contraste WCAG AA, inclusive foco, hover e estados desabilitados. Nunca usar apenas cor para expressar estado. Verde vivo exige texto escuro quando utilizado como fundo.

Tipografia: Inter se disponível com licença adequada, fallback system-ui. Corpo 14–16 px; títulos 24–32 px; metadados 12–13 px. Escala de espaçamento 4, 8, 12, 16, 24, 32 e 48 px. Cantos 8–12 px. Sombras discretas. Ícones de uma biblioteca consistente com licença verificada. Movimento de 120–180 ms respeitando redução de movimento.

## Estrutura
Desktop: sidebar de 248 px, recolhível; barra superior com contexto, busca, notificações e usuário. Mobile: menu em gaveta, conteúdo em uma coluna, filtros em painel e quadro com alternativa em lista. Navegação: Visão geral, Clientes, Projetos, Minhas demandas, Operação, Custos e Administração. Mostrar apenas rotas autorizadas, mantendo verificação também no servidor.

## Telas obrigatórias
1. Login: marca legível, formulário acessível, recuperação de acesso e mensagens sem revelar existência de usuários.
2. Visão geral: minhas pendências, demandas bloqueadas, entregas próximas e incidentes por projeto. Métricas com período e definição.
3. Clientes: cartões e tabela alternáveis; busca, responsável, fase comercial/operacional e filtros persistidos por usuário.
4. Cliente: cabeçalho com nome/responsável; abas Resumo, Projetos, Contatos, Documentos, Reuniões, Operação e Custos. Exibir por permissão.
5. Projeto: abas Quadro, Lista, Documentos, Repositórios, Atividade e Operação. Separar ciclo do cliente e estado das tarefas.
6. Card/tarefa: descrição, responsável principal, colaboradores, checklist, anexos, discussão cronológica e histórico.
7. Minhas demandas: tarefas atribuídas e lembretes privados claramente diferenciados.
8. Operação: disponibilidade, infraestrutura e adoção em seções distintas. Fonte e atualização sempre visíveis.
9. Custos: estimativa versus realizado, moeda, intervalo e alertas.
10. Administração: usuários, papéis, integrações, auditoria e saúde dos conectores.

## Componentes e estados
Botões, campos, selects pesquisáveis, tabelas, paginação, filtros, chips, abas, drawers, menus e diálogos com teclado e foco visível. Cada tela deve ter loading, vazio com ação útil, erro com tentativa novamente, acesso negado e estado de integração indisponível. Exclusões relevantes devem informar consequência e permitir recuperação quando aplicável. Nunca representar dado ausente como zero nem serviço sem telemetria como saudável.

## Aceite visual
Verificar fluxos a 1440, 1024 e 390 px, zoom de 200%, navegação por teclado e leitores de tela nos formulários principais. Não pode haver textos cortados, ações inacessíveis ou contraste insuficiente. Capturas devem cobrir login, clientes, quadro, tarefa e operação. Dados de demonstração somente no ambiente de desenvolvimento, identificados como fictícios.
