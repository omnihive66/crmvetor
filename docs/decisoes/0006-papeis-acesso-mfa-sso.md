# 0006 — Papéis da organização, contas e autenticação

- Data: 22/10/2026 • Estado: aceita (MFA/SSO: pendente de escolha do provedor)

## Papéis
O Taiga só conhece acesso por projeto (memberships com papéis de projeto). A Vetor acrescenta um **papel na organização** (`vetor.Perfil`): Administrador, Gestor, Desenvolvedor, Observador. Ele funciona como **teto**: a pessoa só pode ter memberships compatíveis com o papel. O acesso efetivo continua sendo o do projeto.

| Papel | Pode ser admin de projeto | Papel de projeto | Também |
|---|---|---|---|
| Administrador | sim | qualquer | gerencia pessoas e papéis, configura integrações (webhooks, GitHub e demais hooks), vê a auditoria |
| Gestor | sim (cria projetos) | qualquer | — |
| Desenvolvedor | não (não cria projetos) | qualquer, "conforme papel do projeto" | — |
| Observador | não | só permissões `view_*` | — |
| Conta sem perfil | tratada como Observador (negar por padrão) | | |

`ver_custos` é uma permissão explícita, separada do papel (usada a partir da SPEC-09).

Por que teto em vez de recalcular permissões: o Taiga calcula permissão em vários lugares, inclusive direto em SQL nas listagens. Limitar o que pode ser gravado (memberships, papéis de projeto e perfis, validados nos signals) vale para todos esses caminhos, inclusive importação e admin do Django.

**Interpretação a validar:** a matriz da SPEC-02 diz "Administrador: Criar/atribuir demandas — Sim" e "Atualizar/comentar — No escopo". Aqui o Administrador atua em projetos como qualquer membro (precisa estar no projeto). Ele não vira superusuário do Taiga.

**Superusuário do Taiga** (`is_superuser`) é a conta técnica de emergência: vê tudo, sem teto. Não deve ser usada no dia a dia. A tela de Administração mostra essas contas com a etiqueta "técnica".

## Contas
- Nominais. O administrador cria a conta (nome, usuário, e-mail, papel) e a pessoa recebe e-mail para definir a própria senha. Não há senha inicial nem conta compartilhada. A visão de "matriz" é o papel Gestor ou Administrador de cada pessoa.
- Convite de projeto para e-mail sem conta: a conta criada pelo convite nasce sem perfil (Observador). Se o papel do convite for maior, a aceitação é recusada com explicação. Fluxo recomendado: criar a conta na Administração e depois adicionar ao projeto.
- Desativar a conta bloqueia já a próxima requisição, inclusive com token emitido antes (o Taiga confere `is_active` em toda autenticação). Remover de um projeto vale na próxima requisição à API.
- Sempre existe pelo menos um administrador ativo (rebaixar ou desativar o último é recusado).

## Contas de serviço (conectores)
Integrações futuras (GitHub, Uptime Kuma, Beszel, agente) usam uma conta própria por conector (por exemplo `svc-github`), com papel Desenvolvedor ou Observador e membership só nos projetos necessários. A autenticação usa token de aplicação do Taiga (`external_apps`), que é por usuário e por aplicação. Nunca um token de administrador.

## MFA e SSO (investigado no código, taiga-back 6.10.2)
- **MFA:** não existe no Taiga.
- **SSO:** só os plugins oficiais GitHub e GitLab OAuth. O `config.py` oficial só os liga com cadastro público ativo, o que contraria a decisão 0004.
- **Ponto de extensão:** `taiga.auth.services.register_auth_plugin(nome, login_func)` aceita um login alternativo. Um plugin OIDC (Microsoft Entra ID, Google Workspace ou outro provedor) é desenvolvimento viável dentro do app `vetor`, e o MFA ficaria por conta do provedor.
- **Alternativa sem código:** proxy de identidade (por exemplo, oauth2-proxy) na frente do gateway. Ele protege o acesso, mas a pessoa ainda faz o login do Taiga.
- **Pendente:** escolher o provedor. Isso depende da definição do serviço Azure (SPEC-06).
