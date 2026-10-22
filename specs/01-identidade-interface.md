# SPEC-01 — Identidade e experiência

## Resultado
Aplicação identificada como Vetor Sistemas com navegação e componentes de acordo com DESIGN.md.

## Implementação
Aplicar tokens e componentes compartilhados, evitando CSS duplicado por página. Trocar nome visível, títulos e marca de mensagens controladas pelo produto; manter atribuições legais em local apropriado. Usar o JPEG original com proporção preservada e fallback textual acessível. Criar shell responsivo, breadcrumbs, atalhos de teclado sem conflito, filtros persistidos e busca respeitando o acesso do usuário.

A busca deve retornar somente clientes, projetos, tarefas e documentos autorizados. Não indexar lembretes privados em busca global compartilhada. Paginação no servidor para listagens grandes. Não esconder funcionalidade existente necessária ao trabalho sem um substituto verificável.

## Aceite
Login, clientes, projeto e tarefa usam os mesmos componentes. Nome Vetor Sistemas visível nas áreas especificadas. Nenhuma logo deformada ou texto ilegível. Menu e endpoints obedecem aos papéis. Critérios visuais de DESIGN.md atendidos; busca não revela nomes ou contagens de objetos proibidos. Telas completas com estados de carregamento, vazio e erro.
