# 0005 — Barra lateral global e busca global ficam para quando houver o que navegar

- Data: 22/10/2026 • Estado: proposta, a validar com a gestão

## Contexto
O DESIGN.md pede barra lateral de 248 px com Visão geral, Clientes, Projetos, Minhas demandas, Operação, Custos e Administração, e busca global. Hoje só existem as telas nativas do Taiga: início, projetos e o menu lateral de cada projeto (escuro, recolhível, 200 px, que no celular já começa recolhido). Clientes, Minhas demandas, Operação e Custos ainda não existem (SPEC-03, 05, 07/08 e 09). A busca nativa é por projeto e já respeita permissões (testes `test_search_resources` e verificação manual: usuário sem acesso recebe `count: 0`).

## Decisão
Não criar agora uma barra lateral com itens que levariam a telas inexistentes nem uma busca global que só repetiria a busca de projetos. A barra lateral global e a busca global entram junto com a SPEC-03, quando houver Clientes e documentos para navegar e buscar, como plugin de front (`contribPlugins`) e endpoint de busca no app `vetor`, filtrado no servidor.

## Consequências
- Até lá a navegação global é a barra superior nativa (Projetos, notificações, usuário) e o menu do projeto.
- O critério visual "sidebar de 248 px" fica parcialmente atendido (menu do projeto escuro e recolhível de 200 px).
