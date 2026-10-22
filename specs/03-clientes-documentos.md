# SPEC-03 — Clientes, documentos e reuniões

## Resultado
Central de informações por cliente sem duplicar o sistema financeiro/contratual externo.

## Dados
Cliente: nome, razão social opcional, CNPJ opcional, localização, responsável interno, ciclo de relacionamento e observações. Contatos: nome, função, telefone e e-mail. Clientes podem ter vários contatos e projetos; permitir prospect sem CNPJ. Validar formato e dígitos quando informado, prever exceção documentada para clientes estrangeiros e evitar duplicidade por organização sem bloquear casos legítimos.

Documento: título, categoria, vínculo com cliente/projeto, versão, autor e data; armazenamento privado e download autorizado. Links externos devem distinguir origem e exigir URL válida. Reunião: data, participantes, notas e próximos passos; criar demanda relacionada a partir da ata.

## Fluxos
Cadastrar cliente com campos mínimos; adicionar contato; vincular projeto; anexar documento; registrar reunião; reutilizar documento como modelo mediante cópia explícita autorizada, removendo conteúdo específico e mantendo origem registrada. Nunca compartilhar automaticamente documentos entre clientes. Definir limites de arquivo, retenção e tratamento antimalware conforme infraestrutura real.

## Aceite
Busca por nome/CNPJ, filtros e paginação. Histórico de alterações; contatos e arquivos respeitam acesso. Cliente com projetos ativos deve ser arquivado ou ter exclusão bloqueada com explicação. Documento privado não é acessível por URL pública. Etapas não exigem documentos por padrão. Nome do sistema financeiro permanece uma configuração até confirmar o termo dos áudios.


---

