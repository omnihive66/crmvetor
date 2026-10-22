# SPEC-00 — Auditoria e fundação

## Resultado
Base reprodutível para modificar o Taiga com impacto conhecido e possibilidade de atualização futura.

## Implementação
Localizar ou obter repositórios oficiais e fixar versões/commits compatíveis de backend, frontend e serviços usados. Ler AGENTS.md e instruções existentes. Inventariar APIs, autenticação, permissões, tarefas assíncronas, anexos, eventos, dependências e infraestrutura. Verificar licenças e obrigações de atribuição/distribuição conforme a modalidade de uso; registrar LICENSE e avisos aplicáveis antes do rebranding.

Produzir `docs/arquitetura.md`, `docs/inventario-taiga.md`, `docs/decisoes/` e `.env.example` sem segredos. Determinar por inspeção se haverá extensão no backend existente e qual mecanismo de extensão do frontend. Preferir alterações isoladas em módulos próprios. Não introduzir framework ou microserviço sem justificar necessidade. Registrar o mapa entre objetos existentes e novos.

Modelos conceituais: organização → cliente → projetos; projeto → tarefas; cliente → contatos, documentos e reuniões. Lembrete pertence ao usuário. Uma tarefa tem responsável principal e pode ter colaboradores. Uma etapa é um estado do fluxo; participação por etapa possui histórico próprio. Esquema real será definido após auditoria.

## Aceite
Instalação local reproduzível e login funcionando; versão registrada; lacunas listadas como nativo, configuração ou desenvolvimento; testes existentes relevantes executados com resultado registrado. Backup e restauração de desenvolvimento demonstrados. Nenhum dado ou segredo da produção copiado sem autorização.
