# Entrega 03 — Clientes, documentos e reuniões

Data: 22/10/2026 • Branch: `spec-03-clientes` (sobre `spec-02-permissoes`)

## O que foi reaproveitado, configurado e desenvolvido
- **Reaproveitado:**
  - Projetos e histórias do Taiga: a reunião vira uma história de verdade, com histórico nativo.
  - Armazenamento protegido: documentos usam o mesmo caminho e o mesmo token assinado dos anexos.
  - userstorage do Taiga para os filtros salvos por pessoa.
  - Sprite de ícones do Taiga.
  - Auditoria da SPEC-02, para o histórico do cliente.
- **Desenvolvido (backend, app `vetor`):**
  - **Modelos:**
    - `Cliente`: nome, razão social, CNPJ opcional e validado, exceção para estrangeiro, localização, responsável, ciclo (Negociação, Implantação, Operação, Encerrado), código no sistema financeiro, observações e arquivamento.
    - `Contato`.
    - `ProjetoCliente`: um cliente tem vários projetos; um projeto tem no máximo um cliente.
    - `Documento`: arquivo privado ou link https com origem, categoria, versão, projeto opcional e "modelo de".
    - `Reuniao`: data com fuso, participantes da equipe e do cliente, notas, próximos passos e demandas.
  - **Regras de acesso** (`vetor/clientes.py`): o escopo são os clientes de que a pessoa é responsável ou que têm projeto onde ela é membro.
    - Administrador: todos.
    - Gestor: altera no escopo.
    - Desenvolvedor e Observador: só leem.
    - Documento ligado a projeto exige acesso ao projeto.
    - Fora do escopo a resposta é 404, para não revelar que o cliente existe.
  - **API:**
    - `/vetor/clientes` (busca por nome ou CNPJ, filtros, paginação, vincular e desvincular projeto, histórico, opções).
    - `/vetor/contatos`.
    - `/vetor/documentos` (envio, link, cópia como modelo).
    - `/vetor/reunioes` (criar demanda).
    - `/vetor/busca`.
  - **Regras de negócio:**
    - CNPJ único quando informado. Nome repetido pede confirmação, mas não bloqueia.
    - Cliente com projeto não pode ser excluído; deve ser arquivado.
    - Cópia como modelo exige confirmação explícita, não leva o projeto e registra a origem.
- **Desenvolvido (frontend):**
  - **Barra lateral global** (decisão 0005), a mesma no app do Taiga e nas telas novas. Recolhível; no celular vira gaveta. Busca global no topo dela.
  - **Clientes:** cartões ou tabela, busca, filtros de responsável, ciclo e arquivados, paginação e cadastro.
  - **Cliente:** abas Resumo (com a última reunião e o link da ata), Projetos, Contatos, Documentos, Reuniões e Histórico.
  - **Busca:** resultados agrupados por tipo.
  - Estados de carregamento, vazio com ação útil, erro com "tentar novamente", sessão expirada e fora do acesso. Confirmação nas exclusões, dizendo a consequência.
  - A tela de Administração passou a usar a mesma base (`ui/vetor-ui.css`) e a barra lateral.

## Arquivos

| Arquivo | Mudança |
|---|---|
| `vetor-back/vetor/models.py`, `migrations/0003_crm.py` | modelos do CRM |
| `vetor-back/vetor/clientes.py`, `api_clientes.py`, `urls.py`, `ajustes.py` | regras, API, rotas, configuração |
| `vetor-back/vetor/tests/test_clientes.py` | 19 testes novos |
| `vetor-front/ui/{shell.js,shell.css,vetor-ui.css}` | barra lateral e componentes compartilhados |
| `vetor-front/clientes/{index,cliente}.html`, `busca/index.html` | telas novas |
| `vetor-front/administracao/index.html`, `build.py`, `vetor.css` | Administração na base comum; shell no app; link antigo de Administração removido do menu do usuário |
| `infra/docker-compose.override.yml`, `.env.example` | `VETOR_DOCUMENTO_MAX_MB`, `VETOR_SISTEMA_FINANCEIRO_NOME/URL` |
| `scripts/qa/{crm,crm-acoes}.js` | QA visual e de ações |
| `docs/decisoes/0005`, `docs/arquitetura.md`, `docs/inventario-taiga.md` | atualizados |

**Migrações:** `vetor.0003_crm`, com cinco tabelas novas e restrições (CNPJ único quando preenchido; documento é arquivo **ou** link). Não altera tabelas do Taiga.

## Configuração necessária
- `VETOR_SISTEMA_FINANCEIRO_NOME` e `VETOR_SISTEMA_FINANCEIRO_URL`, com `{codigo}` no lugar do código do cliente. Enquanto o nome não for confirmado, a tela diz "sistema financeiro (a configurar)".
- `VETOR_DOCUMENTO_MAX_MB`, padrão 25. O gateway aceita até 100 MB.

## Critérios de aceite

| Critério | Resultado | Evidência |
|---|---|---|
| Busca por nome e CNPJ, filtros e paginação | **Atendido.** Busca com ou sem máscara no CNPJ, filtros de ciclo e responsável, 30 itens por página com total no cabeçalho. Filtros e modo de exibição salvos no servidor por pessoa, conferidos ao recarregar. | `test_busca_por_nome_e_cnpj_…`, `qa-acoes.txt` (item 2) |
| Histórico de alterações | **Atendido.** Aba Histórico com cliente, contatos, documentos, reuniões e vínculos: quem, quando e quais campos, sem o conteúdo. | `test_historico_do_cliente_para_quem_ve` |
| Contatos e arquivos respeitam acesso | **Atendido.** Quem está fora do escopo não vê cliente, contatos nem documentos (404 e listas vazias). Documento de um projeto não aparece para quem não está nesse projeto. Desenvolvedor e Observador não alteram (403), e a tela não mostra os botões. | `test_escopo_…`, `test_contatos_…`, `test_documento_de_projeto_…`, `clientes-observador-1440.png` |
| Cliente com projetos ativos: arquivar ou exclusão bloqueada com explicação | **Atendido.** Exclusão recusada com "Arquive o cliente ou desvincule os projetos". Arquivar e reativar são reversíveis e auditados. | `test_cliente_com_projeto_…` |
| Documento privado não acessível por URL pública | **Atendido.** Download com token 200, sem token 403. O link é gerado a cada clique, porque o token expira. | saída abaixo |
| Etapas não exigem documentos por padrão | **Atendido:** não existe nenhuma regra de obrigatoriedade. | — |
| Nome do sistema financeiro como configuração | **Atendido** (`VETOR_SISTEMA_FINANCEIRO_*`) | — |
| Fluxos: cadastrar, adicionar contato, vincular projeto, anexar documento, registrar reunião, reutilizar documento como modelo | **Atendido**, via API e tela. Pela tela: nome repetido pediu confirmação; arquivo enviado e baixado; a reunião virou a história #6, que abre no Taiga; a busca na barra lateral achou a demanda. | `qa-acoes.txt`, `demanda-da-reuniao-1440.png`, `busca-cronograma-1440.png` |
| Nunca compartilhar documentos entre clientes automaticamente | **Atendido:** só existe a cópia explícita, com confirmação. A origem fica intacta e registrada. | `test_copiar_como_modelo_…` |
| Busca global não revela objetos proibidos (pendência da SPEC-01) | **Atendido:** só aparece o que a pessoa vê, sem contagens totais. O teste cobre o caso de um projeto onde a pessoa vê o projeto mas não as histórias, e outro membro vê. | `test_busca_so_mostra_…`, `test_busca_nao_aceita_permissao_de_outro_membro` |

### Download privado (22/10/2026)
```
download com token: 200
download sem token: 403
```

### QA visual (`qa.txt`)
1440, 1024 e 390 px sem rolagem horizontal nas telas de clientes (tabela) e cliente. No celular a gaveta abre com o foco na busca e fecha com Esc. Nenhum erro de JavaScript. Observador: 0 botões de edição e sem "Novo cliente". Contraste dos chips de ciclo e da barra lateral: de 5,44:1 a 16,62:1. A borda do campo de busca da barra subiu de 1,90 para 4,97:1.

### Testes automáticos
- `vetor/tests`: **50 passaram** (19 novos do CRM + 31 da SPEC-02).
- Suíte oficial ampliada com o app ativo: **871 passaram**, e as 16 falhas são as mesmas divergências intencionais da SPEC-02, sem nenhuma nova (`evidencias/03/pytest.txt`).

## Problemas encontrados e corrigidos no caminho
- **Bug de permissão na busca:** dois `filter()` sobre memberships viravam joins diferentes no SQL. Uma pessoa que vê só o projeto receberia histórias porque outro membro as vê. Corrigido; o teste falha com a versão errada e passa com a certa.
- **Filtros salvos:** o `PUT` do userstorage do Taiga exige a chave e devolvia 400, que meu código engolia. Passei para `PATCH` com gravações em fila, e a falha agora vai para o console.
- **Botão "Novo cliente" visível para observador:** o `display` dos botões anulava o atributo `hidden`.
- **Captura de página inteira:** ela distorcia a barra lateral fixa e fazia parecer que cobria o conteúdo. A QA passou a usar capturas da janela.

## Riscos e pendências
- **Antivírus:** não há na infraestrutura atual. Os uploads são limitados por tipo (documentos, planilhas, imagens e zip) e tamanho. Recomenda-se um ClamAV ou similar antes de receber arquivos de clientes em produção.
- **Retenção:** não definida. Excluir um documento apaga o arquivo; a recuperação depende do backup.
- **Conteúdo copiado:** a cópia como modelo não altera o conteúdo do arquivo. A tela avisa para revisar e tirar dados específicos do cliente de origem, mas isso é responsabilidade de quem copia.
- **Escopo do gestor:** um gestor cadastra cliente e vira responsável. Um gestor que não é responsável nem membro de projeto do cliente não o vê.
- **Sistema financeiro:** o nome e a URL ainda precisam ser confirmados.
- **Organização única:** o modelo não tem organização. Para separar organizações no futuro, a migração acrescenta uma chave com valor padrão.
- **Barra lateral:** a preferência de recolher fica salva no navegador, não no servidor. Dentro do projeto, o menu do Taiga soma 200 px à barra.
- **Abas Operação e Custos:** não aparecem ainda (SPECs 07 e 09).

## Reversão
Voltar a branch e rodar `./scripts/vetor.sh manage migrate vetor 0002`. Isso **apaga clientes, contatos, documentos e reuniões**; os arquivos enviados ficam órfãos em `media/attachments`. Faça backup antes. As histórias criadas a partir de reuniões continuam no Taiga.
