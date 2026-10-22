# Entrega 02 — Identidades e permissões

Data: 22/10/2026 • Spec: `specs/02-usuarios-permissoes.md` • Branch: `spec-02-permissoes`

## O que foi reaproveitado, configurado e desenvolvido
- **Reaproveitado:** contas, login JWT, recusa de conta inativa em toda requisição, memberships e papéis por projeto com permissões granulares, filtros de listagem, busca por projeto e anexos com token. Tudo isso é nativo do Taiga.
- **Desenvolvido (backend, app `vetor`):**
  - **Papel na organização** (`Perfil`: Administrador, Gestor, Desenvolvedor, Observador, mais a permissão explícita `ver_custos`). Ele funciona como teto para as memberships: Observador só tem permissões `view_*`, Desenvolvedor não administra nem cria projetos, e conta sem perfil vale como Observador. Detalhes e motivo na decisão 0006.
  - **Validação em todo caminho de escrita** (signals de membership, papel de projeto, perfil e usuário). Sempre fica pelo menos um administrador ativo.
  - **Escrita transacional** em projetos, memberships, papéis e perfis. Uma recusa no meio não deixa nada pela metade.
  - **Integrações só para Administrador:** webhooks, logs de webhook e `projects/<id>/modules`, que guarda os segredos do GitHub e demais hooks.
  - **Auditoria** (`Auditoria`, somente inclusão): ator, ação, alvo, horário, resultado, e o antes e o depois de perfis, memberships, permissões de papel e ativação de contas. O ator é capturado na autenticação da API.
  - **API** `/api/v1/vetor/perfis` (listar, criar conta, alterar papel, custos e ativo, `me`) e `/api/v1/vetor/auditoria`.
  - **Migração** `0002_perfis_iniciais`: dá a cada conta existente o papel compatível com o acesso que ela já tem.
- **Desenvolvido (frontend):** tela **Administração** (`/vetor/administracao/`) com pessoas, criação de conta sem senha compartilhada, papel, custos, ativo e auditoria paginada. O link no menu do usuário aparece só para administradores.
- **Corrigido no Taiga oficial**, com imagens derivadas e trocas verificadas no build:
  - `vetor-events/`: o WebSocket aceitava qualquer assinatura. Qualquer usuário recebia eventos de projetos sem acesso e as **notificações de outras pessoas** (`web_notifications.<id>`). Agora só passa o próprio usuário ou o projeto que a API deixa ver.
  - `vetor-protected/` + `infra/taiga-gateway.conf`: exportações de projeto (`/media/exports/`) eram servidas sem token. Agora exigem o mesmo token assinado dos anexos.

## Arquivos

| Arquivo | Mudança |
|---|---|
| `vetor-back/vetor/{models,permissoes,sinais,ator,auditoria,ajustes,apps}.py` | novos |
| `vetor-back/vetor/api.py`, `urls.py` | perfis, auditoria, integrações só para administrador, escrita transacional |
| `vetor-back/vetor/migrations/0001_initial.py`, `0002_perfis_iniciais.py` | novas |
| `vetor-back/vetor/tests/{test_permissoes.py,conftest.py}`, `tests/settings.py` | novos/atualizados |
| `vetor-back/settings/config.py` | passa a usar `vetor.ajustes.aplicar` |
| `vetor-events/`, `vetor-protected/` | novas imagens derivadas |
| `infra/taiga-gateway.conf`, `infra/docker-compose.override.yml` | gateway e imagens novas |
| `vetor-front/administracao/index.html`, `build.py`, `vetor.css` | tela e link de Administração |
| `scripts/test-backend.sh` | banco de teste com nome por execução |
| `scripts/qa/{administracao,eventos}.js` | novos |
| `docs/decisoes/0006`, `docs/inventario-taiga.md`, `docs/arquitetura.md` | atualizados |

**Migrações:** `vetor.0001_initial` (tabelas `vetor_perfil` e `vetor_auditoria`) e `vetor.0002_perfis_iniciais` (dados). Rodam sozinhas no `up` (entrypoint oficial). No banco de desenvolvimento foram criados 1 administrador (`admin.dev`, superusuário) e 1 observador (`observador.dev`).

## Configuração necessária
Nenhuma variável nova. Depois de atualizar, o administrador deve revisar os papéis em **Administração**: a migração escolhe o papel pelo acesso atual, não pela função real da pessoa.

## Critérios de aceite

| Critério | Resultado | Evidência |
|---|---|---|
| Testes de acesso cruzado entre usuários e projetos, IDs diretos, anexos e busca | **Atendido.** Quem não é membro recebe 403 ou 404 no projeto, na história por ID, no anexo por ID e na exportação, e a busca não devolve o texto. No WebSocket, o observador recebeu só o evento do projeto dele, e as assinaturas de outro projeto e das notificações de outra pessoa foram recusadas. | `test_quem_nao_e_membro_…`, saídas abaixo |
| Desativar usuário impede novas ações | **Atendido.** O token emitido antes passa a receber 401 logo após a desativação. | `test_desativar_bloqueia_o_token_ja_emitido_e_fica_auditado` |
| Alterações de papel ficam auditadas | **Atendido.** Perfil (antes e depois), membership criada, alterada ou removida, permissões de papel e ativação, com ator. Sem senha nem token nos detalhes. | 4 testes de auditoria; tela de Administração |
| Administrador técnico sem acesso funcional a lembretes privados | **Preparado, não verificável ainda.** Lembretes chegam na SPEC-05. Ficou registrado que o superusuário do Taiga ignora o teto; os lembretes precisarão filtrar pelo dono também para ele. O WebSocket já não entrega notificação de outra pessoa nem a administradores. | decisão 0006 |
| Limite técnico do acesso ao banco explicitado | **Atendido:** quem tem acesso de infraestrutura ao banco lê tudo. Não há criptografia ponta a ponta. | este relatório |
| Matriz inicial | **Atendido** para tudo que já existe: integrações só para Administrador; criar e atribuir demandas conforme o papel, e o Observador não cria; atualizar e comentar no escopo do projeto. Clientes e custos usam o papel e `ver_custos` quando forem criados (SPEC-03 e 09). | `test_permissoes.py` |
| MFA e SSO investigados | **Atendido:** não há MFA. SSO só GitHub/GitLab com cadastro público. Um plugin OIDC é viável (`register_auth_plugin`), dependendo da escolha do provedor. | decisão 0006 |

### WebSocket e exportação (22/10/2026)
```
observador.dev assina changes.project.1.userstories, changes.project.2.userstories,
                      web_notifications.<admin>, web_notifications.<ele>, changes.project.1.projects
assinatura recusada: changes.project.1.userstories / changes.project.1.projects / web_notifications.5
admin edita US do projeto 1 e do projeto 2 → observador recebeu: changes.project.2.userstories (1)
exportação: com token assinado 200 (28577 bytes) · sem token 403 · token adulterado 403 · anexo (regressão) 200
```

### Tela de Administração (Playwright)
```
admin.dev: link Administração visível = true;  observador.dev: = false
observador.dev em /vetor/administracao/ → "Acesso negado. Esta área é só para administradores da organização."
criar conta → "Conta criada. dev.teste@vetor.local recebeu o e-mail para definir a senha."
rebaixar único administrador → "É preciso manter pelo menos um administrador ativo." (o campo volta ao valor salvo)
390 px: sem rolagem horizontal da página
```
Capturas: `evidencias/02/administracao-*.png`.

### Testes automáticos
- `vetor/tests`: 31 testes, todos passando (teto por papel, criação de projeto sem dono deixado no banco, convite em lote sem metade gravada, último administrador, matriz por papel, conta sem senha compartilhada, desativação com token já emitido, auditoria, acesso cruzado e isenção de CSRF das rotas sobrescritas).
- Suíte oficial ampliada com o app da Vetor ativo: **852 passaram, 16 falharam**, e as 16 são as mudanças pedidas pela spec (o admin do projeto não configura mais integrações; feedback para o Taiga desligado). Detalhes em `evidencias/02/pytest.txt`.

## Problemas encontrados e corrigidos no caminho
- **Regressão que eu mesmo introduzi:** as rotas sobrescritas (memberships, papéis, projetos, perfis) perderam a isenção de CSRF do Taiga e o navegador recebia 403. Os testes não pegavam porque o client de teste não aplica CSRF. Corrigido, com teste que falha sem a correção (4 falhas) e passa com ela.
- As listagens do Taiga não chamam `check_permissions`: sem cuidado, o anônimo listava `/vetor/perfis` e o gestor, os webhooks. A checagem agora vale também em `list`.
- `ATOMIC_REQUESTS` do Taiga sem efeito; ver inventário.
- O ator da auditoria vazava entre requisições na mesma thread; agora vale só durante a requisição.
- O link de exportação enviado por e-mail dava 404 porque o `taiga-protected` não reconhecia o caminho de exportações.

## Riscos e pendências
- **Link de exportação expira em 6 minutos** (`ATTACHMENTS_MAX_AGE`). Antes não expirava, porque era público. Quem perder o prazo exporta de novo.
- **WebSocket:** a permissão é conferida na assinatura. Quem for removido de um projeto continua recebendo os metadados de eventos daquele projeto até recarregar a página ou reconectar. O conteúdo continua exigindo a API, que já recusa.
- **Convite por e-mail para quem não tem conta** cria conta Observador. Se o papel do convite for maior, a aceitação é recusada. Recomendação: criar a conta na Administração antes (decisão 0006).
- **Administrador atua só em projetos dos quais é membro** (interpretação da matriz; validar com a gestão).
- **MFA/SSO:** dependem da escolha do provedor.
- O e-mail de conta nova usa o modelo de "recuperação de acesso" do Taiga (assunto "[Vetor Sistemas] Recuperação de acesso"). Um modelo de boas-vindas próprio é melhoria futura.
- A tela de Administração é uma página à parte (não está no shell do Taiga), até existir a barra lateral global (decisão 0005).

## Reversão
- Código: voltar a branch. Imagens: no override, `taiga-events` e `taiga-protected` voltam às imagens oficiais e o gateway volta ao volume oficial.
- Banco: `./scripts/vetor.sh manage migrate vetor zero` remove `vetor_perfil` e `vetor_auditoria`, **apagando a trilha de auditoria**. Faça backup antes (`./scripts/vetor.sh backup`). Memberships e papéis do Taiga não são alterados pelas migrações.
