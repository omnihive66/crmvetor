"""Aplica a marca Vetor Sistemas sobre o build oficial do taiga-front.

Uso: build.py <html do taiga-front> <vetor-front> <saída>
Cada troca exige a quantidade esperada de ocorrências: se o Taiga mudar, o build falha
em vez de publicar uma marca pela metade.
"""
import json
import re
import shutil
import sys
from pathlib import Path

html, src, out = map(Path, sys.argv[1:4])
version = next(html.glob("v-*")).name  # pasta versionada do build oficial

# Paleta do Taiga -> tokens do DESIGN.md
COLORS = {
    "#008aa8": "#087443", "#25a28c": "#087443", "#5cbaa9": "#087443",  # ação / links
    "#83eede": "#00d47a",                                              # destaque (texto escuro por cima)
    "#2e3440": "#14221b", "#4c566a": "#14221b", "#434456": "#14221b",  # texto
    "#70728f": "#52645a", "#5a5b72": "#52645a",                        # texto secundário
    "#d8dee9": "#dce5df", "#e2e3e9": "#dce5df", "#e3e3e9": "#dce5df",
    "#d4d4de": "#dce5df", "#e5e9f0": "#dce5df",                        # bordas
    "#eceff4": "#f5f7f6", "#f9f9fb": "#f5f7f6", "#f1f1f4": "#f5f7f6",  # fundo
    "#e44057": "#b42318", "#ff6363": "#b42318", "#cf0404": "#b42318",
    "#ff3019": "#b42318",                                              # falhas
    "#3b4252": "#090d0b",                                              # menu lateral do projeto
    "#9b9cb1": "#5e7066", "#a9aabc": "#5e7066",                        # placeholders e tags (AA)
}
FONT = 'Inter,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif'

LOGO = ('<span class="vetor-logo"><img src="vetor/logo-vetor-original.jpg" '
        'alt="Vetor Sistemas" width="640" height="640"></span>')


def write(rel, text):
    path = out / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sub(text, pattern, repl, expected, what, flags=0):
    new, n = re.subn(pattern, repl, text, flags=flags)
    if n != expected:
        sys.exit(f"build.py: {what}: esperado {expected}, encontrado {n}")
    return new


# 1. Tema: cores, fonte e CSS da Vetor no fim (vence por ordem).
css = (html / version / "styles/theme-taiga.css").read_text(encoding="utf-8")
css = re.sub(r"#(?:[0-9a-fA-F]{6})\b", lambda m: COLORS.get(m.group(0).lower(), m.group(0)), css)
rgb = lambda h: ",".join(str(int(h[i:i + 2], 16)) for i in (1, 3, 5))
RGBA = {rgb(k): rgb(v) for k, v in COLORS.items()}  # mesmas cores usadas com transparência
css = re.sub(r"rgba\((\d+,\d+,\d+),", lambda m: f"rgba({RGBA.get(m.group(1), m.group(1))},", css)
css = sub(css, r"Ubuntu-Regular,Arial,Helvetica,sans-serif", FONT, 164, "fonte regular")
css = sub(css, r"Ubuntu-Medium,Arial,Helvetica,sans-serif", FONT + ";font-weight:600", 135, "fonte média")
write(f"{version}/styles/theme-taiga.css", css + "\n" + (src / "vetor.css").read_text(encoding="utf-8"))

# Web components (elements.js) declaram as mesmas cores em variáveis CSS próprias.
el = (html / version / "js/elements.js").read_text(encoding="utf-8")
el, n = re.subn(r"#(?:[0-9a-fA-F]{6})\b(?=[;,)\s\"'}])",
                lambda m: COLORS.get(m.group(0).lower(), m.group(0)), el)
for var in ("--color-black800:#090d0b", "--color-link-primary:#087443", "--color-solid-primary:#00d47a"):
    if var not in el:
        sys.exit(f"build.py: variável não aplicada em elements.js: {var}")
write(f"{version}/js/elements.js", el)

# 2. Templates: logos e textos fixos "Taiga".
tpl = (html / version / "js/templates.js").read_text(encoding="utf-8")
WS = r"(?:\\n|\s)*"  # templates.js guarda quebras de linha como o texto "\n"
tpl = sub(tpl, r'<svg id="logo-svg".*?</svg>' + WS, LOGO, 2, "logo do cabeçalho", re.S)
tpl = sub(tpl, r'href="https://taiga\.io/"', 'href="/"', 1, "link da logo para taiga.io")
tpl = sub(tpl, r'<div class="logo-svg">.*?</svg>' + WS + '</div>' + WS + '<h1 class="logo">Taiga</h1>',
          f'<h1 class="logo vetor-auth-logo">{LOGO}</h1>', 7, "logo das telas de acesso", re.S)
tpl = sub(tpl, r'<img src="v-[^"]*/svg/logo\.svg" alt="TAIGA" width="143px">' + WS + '<h1 class="logo">Taiga</h1>',
          f'<h1 class="logo vetor-auth-logo">{LOGO}</h1>', 1, "logo da tela de erro")
tpl = sub(tpl, r'<img (?:ng-)?src="v-[^"]*/svg/logo\.svg" alt="TAIGA"[^>]*>', LOGO, 2, "logo das telas de aviso")
tpl = sub(tpl, r'<div class="logo"><\?xml.*?</svg>' + WS + '</div>' + WS + '<h1>Taiga</h1>',
          f'<h1 class="logo vetor-auth-logo">{LOGO}</h1>', 1, "logo da autorização de app externo", re.S)
# "Taiga Logo" restante é o formato de arquivo do Taiga no importador: mantido.
write(f"{version}/js/templates.js", tpl)

# Criar projeto: a opção Kanban usa o modelo "Kanban (fluxo Vetor)" (migração vetor.0004, id 1001).
app = (html / version / "js/app.js").read_text(encoding="utf-8")
app = sub(app, r"this\.projectForm\.creation_template=2\b", "this.projectForm.creation_template=1001", 1, "modelo Kanban da Vetor")
write(f"{version}/js/app.js", app)

# 3. Textos pt-BR com a marca do Taiga (mescla só as chaves sobrescritas).
def merge(base, over, path=""):
    for k, v in over.items():
        if k not in base:
            sys.exit(f"build.py: chave inexistente no locale: {path}{k}")
        if isinstance(v, dict):
            merge(base[k], v, f"{path}{k}.")
        else:
            base[k] = v

def flat(o, p=""):
    for k, v in o.items():
        yield from flat(v, f"{p}{k}.") if isinstance(v, dict) else [(p + k, v)]

# Textos que citam o Taiga de propósito: importar arquivo do Taiga, newsletter/feedback/Tribe do taiga.io
# (desligados nesta instalação), mensagens de importadores e a atribuição no menu Ajuda.
KEEP_TAIGA = ("PROJECT.IMPORT.", "PROJECT.NEWSLETTER_OPENING.", "LIGHTBOX.FEEDBACK.", "US.TRIBE.",
              "PROJECT.NAVIGATION.TAIGA_RESOURCES", "PROJECT.NAVIGATION.TAIGA_COMMUNITY_TITLE", "HINTS.HINT1_TEXT", "USER_SETTINGS.EVENTS.",
              "ADMIN.PLUGINS.", "ADMIN.ROLES.NOTE_EXTERNAL_USERS", "LIGHTBOX.DELETE_ACCOUNT.BLOCK_PROJECT")

for loc in sorted((src / "locale").glob("*.json")):
    rel = f"{version}/locales/taiga/locale-{loc.stem}.json"
    data = json.loads((html / rel).read_text(encoding="utf-8"))
    merge(data, json.loads(loc.read_text(encoding="utf-8")))
    left = [k for k, v in flat(data) if re.search(r"taiga", str(v), re.I) and not k.startswith(KEEP_TAIGA)]
    if left:
        sys.exit(f"build.py: textos com Taiga sem tradução em {loc.name}: {left}")
    write(rel, json.dumps(data, ensure_ascii=False))

# 4. index.html: título, descrição e favicon.
idx = (html / "index.html").read_text(encoding="utf-8")
idx = sub(idx, r"<title>Taiga</title>", "<title>Vetor Sistemas</title>", 1, "título")
idx = sub(idx, r'<html lang="en"', '<html lang="pt-BR"', 1, "idioma do documento")
idx = sub(idx, r'<meta name="description" content="[^"]*">',
          '<meta name="description" content="Vetor Sistemas — CRM e Gestão de Projetos.">', 1, "descrição")
idx = sub(idx, r'<meta name="keywords" content="[^"]*">\s*', "", 1, "keywords")
idx = sub(idx, r'<link rel="icon" type="image/png" href="[^"]*">',
          '<link rel="icon" type="image/svg+xml" href="vetor/favicon.svg">', 1, "favicon")
# Celular: menu do projeto começa recolhido (recurso nativo), sem sobrescrever a escolha do usuário.
idx = sub(idx, r"(window\._taigaAvailableThemes = \[[^\]]*\];)",
          r"""\1
      try { if (innerWidth <= 600 && localStorage.getItem('projectnav-collapsed') === null) localStorage.setItem('projectnav-collapsed', 'true'); } catch (e) {}""",
          1, "menu recolhido no celular")
# Barra lateral global também no app do Taiga.
idx = sub(idx, r'(<link rel="stylesheet" href="v-[^"]+/styles/theme-taiga\.css">)',
          r'\1\n    <link rel="stylesheet" href="vetor/ui/shell.css">\n'
          f'    <script src="vetor/ui/shell.js" data-sprite="{version}/svg/sprite.svg" defer></script>', 1, "shell no app")
write("index.html", idx)

# 5. conf.json: ajuda aponta para o código-fonte e créditos (AGPL); feedback ia para support@taiga.io.
conf = (html / "conf.json.template").read_text(encoding="utf-8")
conf = sub(conf, r'"supportUrl": "[^"]*"', '"supportUrl": "${VETOR_SOURCE_URL}"', 1, "supportUrl")
conf = sub(conf, r'"feedbackEnabled": true', '"feedbackEnabled": false', 1, "feedback")
# isSaas só esconde a newsletter do taiga.io (pop-up ao criar projeto e bloco em Notificações): não é produto Taiga.
conf = sub(conf, r'"feedbackEnabled": false,', '"feedbackEnabled": false,\n    "isSaas": true,', 1, "newsletter do Taiga")
write("conf.json.template", conf)

(out / "vetor").mkdir(parents=True, exist_ok=True)
for name in ("logo-vetor-original.jpg", "favicon.svg"):
    shutil.copy(src / name, out / "vetor" / name)
# Telas próprias e a base compartilhada (ui/): o sprite de ícones do Taiga fica na pasta versionada.
for pasta in ("ui", "administracao", "clientes", "busca", "demandas", "minhas-demandas", "monitoramento"):
    for arq in (src / pasta).iterdir():
        texto = arq.read_text(encoding="utf-8").replace("__SPRITE__", f"{version}/svg/sprite.svg")
        write(f"vetor/{pasta}/{arq.name}", texto)
print(f"build.py: marca aplicada em {version}")
