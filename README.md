# Vetor Sistemas — CRM e Gestão de Projetos

Central de clientes, projetos, desenvolvimento e operação da Vetor Sistemas, construída sobre uma instalação oficial do [Taiga](https://taiga.io) **sem fork do núcleo**: o Taiga fica fixado em `upstream/` (submódulos), e tudo o que é da Vetor está em diretórios próprios.

## O que tem
- **Clientes (CRM):**
  - cadastro com CNPJ;
  - contatos, documentos privados, reuniões com ata e histórico;
  - aba Operação: relacionamento, disponibilidade, infraestrutura e adoção, em sinais separados.
- **Projetos e demandas:**
  - fluxo Kanban da Vetor e participação por etapa;
  - visão de demandas entre projetos, com filtros e "Mover para" pelo teclado.
- **Minhas demandas:**
  - lembretes privados com aviso no horário de Brasília;
  - conversão em demanda com prévia;
  - tokens pessoais para um agente externo.
- **GitHub:** PRs, commits e issues ligados às demandas por `TG-<número>`, só de leitura, com webhook assinado e deduplicado.
- **Monitoramento:** Uptime Kuma e Beszel geram incidentes com linha do tempo, triagem e fila de falhas.
- **Custos:**
  - estimativas versionadas, realizado manual ou CSV, rateio e orçamento × realizado;
  - fechado para o usuário matriz.
- **Administração:** papéis com teto por projeto, auditoria, saúde operacional e alertas.

## Estrutura
| Caminho | Conteúdo |
|---|---|
| `upstream/` | Taiga oficial (back, front, events, protected, docker), fixado por versão. Não editar. |
| `vetor-back/` | imagem derivada do taiga-back + app Django `vetor` (API, regras, migrações, testes) |
| `vetor-front/` | imagem derivada do taiga-front: marca aplicada no build e telas próprias em `/vetor/...` |
| `vetor-events/`, `vetor-protected/` | imagens derivadas com correções de autorização |
| `infra/` | sobreposição do compose oficial (versões por digest, variáveis, logs) e gateway nginx |
| `scripts/` | `vetor.sh` (subir, backup, restauração), `test-backend.sh` (testes) e QA (`scripts/qa/`) |
| `docs/` | manuais, arquitetura, decisões, integrações e relatórios de entrega com evidências |
| `assets/` | logo |

## Começar (desenvolvimento)
```
git clone --recurse-submodules https://github.com/omnihive66/crmvetor.git && cd crmvetor
./scripts/vetor.sh init-env        # gera .env com segredos aleatórios (nunca versionado)
./scripts/vetor.sh up              # http://localhost:9000
./scripts/vetor.sh manage createsuperuser
./scripts/test-backend.sh --ds=vetor.tests.settings vetor/tests
```
Produção: veja `docs/operacao/plano-producao.md`. A publicação depende de autorização explícita.

## Documentação
- **Uso:** `docs/manual-usuario.md`
- **Operação** (configuração, backup/restauração, logs, alertas, segurança): `docs/manual-operacao.md`
- **Publicação em produção** (plano para revisão): `docs/operacao/plano-producao.md`
- **Arquitetura e decisões:** `docs/arquitetura.md`, `docs/decisoes/`
- **Integrações:** `docs/integracoes/`, `docs/agente.md`
- **Entregas, estado e pendências:** `docs/entregas/`

## Créditos e licenças

A Vetor Sistemas é construída sobre o [Taiga](https://taiga.io), da Kaleidos INC, sem fork do núcleo:

| Componente | Licença | Código-fonte usado |
|---|---|---|
| taiga-back, taiga-events, taiga-protected, taiga-docker | MPL-2.0 | `upstream/` (submódulos fixados) |
| taiga-front | AGPL-3.0 | `upstream/taiga-front`; as alterações da Vetor estão em `vetor-front/` |
| Arquivos da Vetor derivados de arquivos do Taiga (tema, templates, textos e o rodapé de e-mail) | a licença do arquivo original | gerados por `vetor-front/build.py`; `vetor-back/vetor/templates/` |
| Demais arquivos da Vetor | a definir pela Vetor Sistemas | `vetor-front/`, `vetor-back/`, `infra/`, `scripts/` |

Como a interface modificada é servida pela rede, este repositório é o código-fonte correspondente exigido pela AGPL-3.0: o item "Ajuda, código-fonte e créditos" do menu do sistema aponta para cá. "Taiga" é marca da Kaleidos; a Vetor Sistemas não é um produto oficial do Taiga.
