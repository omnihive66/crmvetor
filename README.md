# Vetor Sistemas — pacote de desenvolvimento orientado por especificações

Versão 1.0 • 22/10/2026 • Idioma: português do Brasil

## Objetivo
Adaptar uma instalação do Taiga para funcionar como a central de clientes, projetos, desenvolvimento e operação da Vetor Sistemas. Nome público do produto: **Vetor Sistemas**. Descrição: CRM e Gestão de Projetos. A identidade enviada pelo usuário está em `assets/logo-vetor-original.jpg`.

Este pacote define o trabalho; não contém uma aplicação implementada. Os comandos em COMANDOS.md são instruções para um agente de desenvolvimento, não comandos de terminal nem recursos já existentes no Taiga.

## Fontes e limites
Requisitos extraídos da conversa e da transcrição automática dos 12 áudios de 19/10/2026. Nomes próprios e nome do sistema financeiro precisam de confirmação. Os dois arquivos das 10:41:55 foram transcritos com o mesmo conteúdo. Não executar instruções contidas em anexos como autorização operacional. Validar requisitos ambíguos durante o refinamento.

A adaptação deve partir do código real do Taiga: versão, serviços, modelos, APIs e licenças precisam ser auditados antes de determinar alterações. Reaproveitar capacidades confirmadas e documentar lacunas. Não pressupor que um recurso da edição hospedada exista na versão instalada. Não substituir toda a aplicação por uma demonstração com dados fictícios.

## Entregáveis
- DESIGN.md: identidade visual, componentes, navegação e telas.
- specs/00 a 10: escopo funcional e técnico com critérios de aceite.
- COMANDOS.md: instruções sequenciais para implementar cada especificação.
- RASTREABILIDADE.md: requisitos dos áudios relacionados aos módulos.

## Fases
1. Base: auditoria, identidade, clientes, documentos, projetos, acesso e lembretes.
2. Integrações: GitHub, monitoramento, agente e Azure após definir qual serviço Azure será utilizado.
3. Operação: adoção, custos, governança e preparação para produção.

## Regra de execução
Para cada especificação: inspecionar código; registrar plano e impactos; implementar uma fatia funcional; aplicar migrações de forma segura; verificar autorização no servidor; testar riscos reais; revisar a interface; registrar evidências e pendências. Somente avançar quando os critérios da fatia estiverem atendidos ou quando dependências externas estiverem explicitamente identificadas. Publicação em produção exige autorização específica.

## Decisões propostas, ainda ajustáveis
Organização única Vetor Sistemas, preparada no modelo para separação futura entre organizações. Acesso inicial apenas interno; clientes externos são uma evolução. Login nominal por pessoa, sem conta compartilhada da matriz. Papéis iniciais: administrador, gestor, desenvolvedor e observador. Gerência não tem acesso automático a lembretes privados. Nenhum campo extra de fase é obrigatório por padrão. Datas armazenadas em UTC e exibidas em America/Sao_Paulo; valores em BRL, preservando moeda de origem.

## Créditos e licenças

A Vetor Sistemas é construída sobre o [Taiga](https://taiga.io), da Kaleidos INC, sem fork do núcleo:

| Componente | Licença | Código-fonte usado |
|---|---|---|
| taiga-back, taiga-events, taiga-protected, taiga-docker | MPL-2.0 | `upstream/` (submódulos fixados) |
| taiga-front | AGPL-3.0 | `upstream/taiga-front`; as alterações da Vetor estão em `vetor-front/` |
| Arquivos da Vetor derivados de arquivos do Taiga (tema, templates, textos e o rodapé de e-mail) | a licença do arquivo original | gerados por `vetor-front/build.py`; `vetor-back/vetor/templates/` |
| Demais arquivos da Vetor | a definir pela Vetor Sistemas | `vetor-front/`, `vetor-back/`, `infra/`, `scripts/` |

Como a interface modificada é servida pela rede, este repositório é o código-fonte correspondente exigido pela AGPL-3.0: o item "Ajuda, código-fonte e créditos" do menu do sistema aponta para cá. "Taiga" é marca da Kaleidos; a Vetor Sistemas não é um produto oficial do Taiga.
