"""Exportações de projeto passam a exigir o mesmo token assinado dos anexos (taiga-protected 6.10.1).
Falha o build se o trecho esperado do server.py mudar numa atualização."""
import sys
from pathlib import Path

arq = Path(sys.argv[1])
src = arq.read_text()
TROCAS = [
    ('            "/<any(attachments, project, user):basepath>/<p1>/<p2>/<p3>/<p4>/<p5>/<basename>"\n        )\n    ]',
     '            "/<any(attachments, project, user):basepath>/<p1>/<p2>/<p3>/<p4>/<p5>/<basename>"\n        ),\n'
     '        Rule("/exports/<p1>/<basename>", endpoint="exports"),  # Vetor Sistemas\n    ]'),
    ('    path = build_path(args)\n\n    if args["basepath"] == "attachments":',
     '    path = f"exports/{args[\'p1\']}/{args[\'basename\']}" if endpoint == "exports" else build_path(args)\n\n'
     '    if endpoint == "exports" or args.get("basepath") == "attachments":'),
]
for de, para in TROCAS:
    if src.count(de) != 1:
        sys.exit(f"aplicar.py: trecho não encontrado uma única vez:\n{de}")
    src = src.replace(de, para)
arq.write_text(src)
print("aplicar.py: exportações protegidas por token")
