"""Modelo de projeto "Kanban (fluxo Vetor)" (SPEC-04). Parte do kanban oficial (fixture do Taiga, já que
numa instalação nova o loaddata roda depois do migrate) e troca etapas, papéis e o campo Prioridade.
ID fixo: o formulário do front usa o id do modelo (vetor-front/build.py troca 2 por este)."""
import json
from pathlib import Path

from django.db import migrations
from django.utils import timezone

ID = 1001
ETAPAS = [  # nome, cor (texto ≥ 4,5:1 sobre branco), concluída, arquivada
    ("Entrada", "#52645A", False, False), ("Refinamento", "#175CD3", False, False), ("A fazer", "#6941C6", False, False),
    ("Desenvolvimento", "#B54708", False, False), ("Revisão", "#C11574", False, False), ("Testes", "#0E7090", False, False),
    ("Concluído", "#087443", True, False), ("Arquivado", "#667085", True, True),
]
TAREFAS = [("Nova", "#52645A", False), ("Em andamento", "#B54708", False), ("Pronta para revisão", "#0E7090", False),
           ("Concluída", "#087443", True), ("Precisa de informação", "#C11574", False)]


def criar(apps, schema_editor):
    from taiga.permissions.choices import MEMBERS_PERMISSIONS
    import taiga.projects
    ProjectTemplate = apps.get_model("projects", "ProjectTemplate")
    if ProjectTemplate.objects.filter(pk=ID).exists():
        return
    fixture = Path(taiga.projects.__file__).parent / "fixtures/initial_project_templates.json"
    kanban = next(t["fields"] for t in json.loads(fixture.read_text()) if t["fields"]["slug"] == "kanban")
    todas = [p for p, _ in MEMBERS_PERMISSIONS]
    campos = {**kanban,
              "name": "Kanban (fluxo Vetor)", "slug": "vetor-kanban", "order": 0,
              "description": "Entrada → Refinamento → A fazer → Desenvolvimento → Revisão → Testes → Concluído. "
                             "Bloqueio é sinalização com motivo, sem mudar de etapa.",
              "created_date": timezone.now(), "modified_date": timezone.now(),
              "us_statuses": [{"name": n, "slug": n.lower().replace(" ", "-").replace("ã", "a").replace("í", "i"),
                               "order": i + 1, "color": c, "is_closed": fechada, "is_archived": arq, "wip_limit": None}
                              for i, (n, c, fechada, arq) in enumerate(ETAPAS)],
              "task_statuses": [{"name": n, "slug": f"t{i}", "order": i + 1, "color": c, "is_closed": f}
                                for i, (n, c, f) in enumerate(TAREFAS)],
              "roles": [
                  {"name": "Gestão", "slug": "gestao", "order": 10, "computable": False, "permissions": todas},
                  {"name": "Desenvolvimento", "slug": "desenvolvimento", "order": 20, "computable": True, "permissions": todas},
                  {"name": "Observação", "slug": "observacao", "order": 30, "computable": False,
                   "permissions": [p for p in todas if p.startswith("view_")]},
              ],
              "default_owner_role": "gestao",
              "us_custom_attributes": [{"name": "Prioridade", "description": "Opcional; não bloqueia o avanço.",
                                        "type": "dropdown", "order": 1}],
              "default_options": {**kanban["default_options"], "us_status": "Entrada", "task_status": "Nova"}}
    campos.pop("tags", None)
    campos.pop("tags_colors", None)
    ProjectTemplate.objects.create(pk=ID, **campos)


def remover(apps, schema_editor):
    apps.get_model("projects", "ProjectTemplate").objects.filter(pk=ID).delete()


class Migration(migrations.Migration):
    dependencies = [("vetor", "0003_crm"), ("projects", "0068_project_archived_code")]
    operations = [migrations.RunPython(criar, remover)]
