# Entrega 01 — Identidade e experiência

Data: 22/10/2026 • Spec: `specs/01-identidade-interface.md` • Branch: `spec-01-identidade`

## O que foi reaproveitado, configurado e desenvolvido
- **Reaproveitado:** telas, componentes, estados de carregamento, vazio e erro, menu recolhível do projeto, permissões, busca por projeto e filtros salvos por usuário (userstorage). Tudo isso é nativo do Taiga.
- **Configurado:** `conf.json`: o link "Ajuda" aponta para o código-fonte e os créditos (`VETOR_SOURCE_URL`) e o feedback para support@taiga.io foi desligado. No backend, `SR`: nome do produto, assinatura e suporte, e `FEEDBACK_ENABLED=False`.
- **Desenvolvido:**
  - `vetor-front/`: imagem derivada do taiga-front 6.10.3. O `build.py` troca a paleta pelos tokens do DESIGN.md (no tema e nos web components), a fonte (Inter/system-ui), as logos (JPEG original recortado por CSS, sem esticar), o título, o idioma do documento, o favicon tipográfico "V" e 64 textos pt-BR. A camada `vetor.css` cuida da barra superior escura, do foco visível, de `prefers-reduced-motion`, do rótulo "Bloqueado" em texto, do layout de celular, das bordas de campo com contraste e das telas de erro.
  - `vetor-back/`: imagem derivada do taiga-back 6.10.2 com o app Django `vetor`, que traz três coisas:
    - A recuperação de senha agora dá a mesma resposta para conta existente e inexistente. Antes, a API devolvia 200 para conta existente e 400 para inexistente, o que revelava quem tem acesso.
    - Traduções pt-BR dos e-mails, com a marca Vetor em assuntos, convites, rodapé e assinatura.
    - Um rodapé de e-mail sem os links sociais do Taiga.
  - `scripts/qa/`: capturas, teclado/zoom, menu por papel e estados de erro (Playwright).

## Arquivos

| Arquivo | Mudança |
|---|---|
| `vetor-front/Dockerfile`, `build.py`, `vetor.css`, `favicon.svg`, `locale/pt-br.json` | novos |
| `vetor-back/Dockerfile`, `settings/config.py` | novos |
| `vetor-back/vetor/` (`api.py`, `urls.py`, `locale/pt_BR/…/django.po` e `.mo`, `templates/emails/includes/footer.jinja`, `tests/`) | novos |
| `infra/docker-compose.override.yml` | front e back passam a usar as imagens derivadas |
| `scripts/vetor.sh` | `up` reconstrói as imagens e reinicia o gateway; novo `i18n` |
| `scripts/test-backend.sh` | inclui o app `vetor` (`--ds=vetor.tests.settings`) |
| `scripts/qa/*.js` | novos |
| `.env.example` | `VETOR_SOURCE_URL` |
| `assets/logo-vetor-original.jpg` | permissão 600 → 644 (o nginx devolvia 403); conteúdo inalterado |
| `README.md` | seção "Créditos e licenças" (destino do link Ajuda, obrigação da AGPL) |
| `docs/decisoes/0002`, `0003` (revisadas), `0005` (nova); `docs/arquitetura.md` | atualizados |

**Migrações:** nenhuma.

## Configuração necessária
`VETOR_SOURCE_URL` no `.env`: URL pública do código-fonte, que aparece em "Ajuda" e nos e-mails. Depois, `./scripts/vetor.sh up`. Sem essa variável o link de ajuda some, e a obrigação da AGPL deixa de ser cumprida pela interface.

## Critérios de aceite

| Critério | Resultado | Evidência |
|---|---|---|
| Login, projeto e tarefa usam os mesmos componentes | **Atendido** para login, início, quadro e card (componentes nativos com a mesma camada de tokens). A tela de clientes não existe ainda (SPEC-03). | `evidencias/01/{login,inicio,quadro,card}-{1440,1024,390}.png` |
| Nome Vetor Sistemas visível nas áreas especificadas | **Atendido:** interface, login, título do navegador e e-mails. Nos e-mails, o assunto (`[Vetor Sistemas] Recuperação de acesso`), o `<title>`, o rodapé ("Ajuda e código-fonte") e a assinatura ("Equipe Vetor Sistemas") foram conferidos no log do backend. O build falha se sobrar texto pt-BR com "Taiga" fora das exceções listadas em `build.py`. | log do `taiga-back`; `build.py` |
| Nenhuma logo deformada ou texto ilegível | **Atendido:** recorte por CSS na faixa medida nos pixels (x141–506, y255–345), proporção 1:1 preservada | capturas de login, cabeçalho, 404 |
| Menu e endpoints obedecem aos papéis | **Atendido** (nativo, verificado). Um usuário só leitura não vê "Configurações", nem os "+" das colunas, nem o menu dos cards. Projeto privado do qual ele não é membro: 403 no detalhe e no ID da história. Criar história ou editar o projeto: 403. | `evidencias/01/quadro-observador-1440.png`, sequência abaixo |
| Critérios visuais do DESIGN.md | **Parcial.** Contraste AA em todos os pares de tokens (tabela abaixo); foco visível de 2 px em todos os controles do login; Enter envia o formulário; 1440, 1024 e 390 px sem ações escondidas; zoom de 200% sem rolagem no card. Pendentes: barra lateral global de 248 px (decisão 0005); leitor de tela não testado; o quadro em zoom de 200% tem 11 px de rolagem horizontal da página (além da rolagem própria das colunas). | `evidencias/01/teclado-zoom.txt`, `foco-teclado-inicio-1440.png`, `*-zoom200.png` |
| Busca não revela nomes ou contagens proibidos | **Atendido** para a busca existente (por projeto): usuário sem acesso recebe `{"count": 0}`; projeto proibido e inexistente mostram a mesma página 404. Busca global e busca de clientes/documentos ficam para a SPEC-03 (decisão 0005). | sequência abaixo; `nao-encontrado-1024.png`, `sem-permissao-1024.png` |
| Estados de carregamento, vazio e erro | **Atendido** nas telas existentes: estados nativos com a marca (início vazio com texto revisado, 404/sem permissão com fundo da marca) | capturas |

### Contraste (WCAG 2.1)

| Par | Razão |
|---|---|
| Texto `#14221B` / branco · fundo | 16,48 · 15,32 |
| Secundário `#52645A` / branco · fundo | 6,31 · 5,86 |
| Ação `#087443` / branco (texto e foco) · fundo | 5,85 · 5,44 |
| Branco / ação (botão) | 5,85 |
| Texto / brand `#00D47A` (botão de destaque) | 8,39 |
| Texto claro `#E8EEEA` · brand / barra `#090D0B` | 16,62 · 9,96 |
| Branco / danger `#B42318` (rótulo Bloqueado) | 6,57 |
| Placeholders e tags (`#9B9CB1`, `#A9AABC` do Taiga → `#5E7066`) | 2,70 / 2,29 → 5,27 |
| Borda de campo `#7A8B81` / branco (não-texto, mín. 3) | 3,60 |

### Papéis, busca e recuperação de senha (API, 22/10/2026)
```
observador.dev (só leitura no projeto 2, fora do projeto 1)
projeto 1 (privado, não é membro): 403
história do projeto 1 por ID: 403
busca no projeto 1: {"count": 0} [200]
projetos listados: ['[FICTÍCIO] Portal do Cliente']
criar história no projeto 2: 403   editar projeto 2: 403
password_recovery admin.dev → 200 {"detail": "Mail sent successfully!"}
password_recovery naoexiste.xyz → 200 {"detail": "Mail sent successfully!"}   (antes: 400 "Usuário ou senha não correspondem")
password_recovery "" → 400
```

### Testes automáticos
- `vetor/tests` (6): a rota oficial resolve para a versão da Vetor; existente e inexistente têm a mesma resposta; e-mail só para conta existente; usuário vazio continua inválido; todo `msgid` da Vetor existe no Taiga; a tradução da Vetor vence a do Taiga.
- Suíte oficial relevante da SPEC-00 rodando **com o app da Vetor** + os 6 acima: **321 passaram, 0 falharam** (`evidencias/01/pytest.txt`).

## Problemas encontrados e corrigidos no caminho
- O JPEG enviado tinha permissão 600: o nginx devolvia 403 e a logo não aparecia.
- O build oficial guarda as quebras de linha do `templates.js` como o texto `\n`: os padrões foram ajustados.
- Os web components têm paleta própria em variáveis CSS (`elements.js`): o menu do projeto continuava cinza-azulado.
- Traduções do backend não valiam porque o `.po` da Vetor não tinha o mesmo `Plural-Forms` do Taiga (o Django 3.2 guarda catálogos separados e o do Taiga vencia). Há teste para isso.
- O entrypoint oficial faz `chown -R /taiga-back`: montagens somente leitura derrubavam o backend; passou a ser imagem derivada.
- Containers recriados deixavam o gateway com IP antigo (502); `up` agora reinicia o gateway.

## Riscos e pendências
- **Barra lateral global e busca global** adiadas para a SPEC-03 (decisão 0005, a validar com a gestão).
- **Cabeçalho gráfico dos e-mails** continua com o logo e a cor do Taiga (imagens quadradas de 60×60 e 72×88; a marca 4:1 ficaria ilegível). Precisa de PNG oficial da logo e sobrescrita de `base-body-html`/`hero-body-html`. Os atributos `alt`/`title` "Taiga" desses dois templates também ficam.
- **Outros idiomas:** só pt-BR (padrão) teve os textos revisados; quem trocar o idioma no perfil verá "Taiga" em alguns textos.
- **Cores de status** vêm dos dados do modelo de projeto (por exemplo, amarelo "Pronto para teste" em texto sobre branco, com contraste baixo). Ajustar nos modelos de fluxo da SPEC-04.
- Algumas frases nativas não têm tradução pt-BR no Taiga ("subject or reference", "collapse menu", "Add assigned").
- Texturas decorativas do Taiga em Descobrir, projeto bloqueado e transferência de projeto.
- **Licença dos arquivos próprios da Vetor** não definida (README, "Créditos e licenças").
- Leitor de tela não testado; teste visual só em Chromium.

## Reversão
No `infra/docker-compose.override.yml`, voltar `taiga-front` para `image: taigaio/taiga-front:6.10.3@sha256:570c…` e `taiga-back`/`taiga-async`/`taiga-manage` para `image: taigaio/taiga-back:6.10.2@sha256:4beed…` (sem `build`), e rodar `./scripts/vetor.sh up`. Sem migrações nem dados alterados.
