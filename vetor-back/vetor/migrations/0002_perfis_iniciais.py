"""Dá a cada conta existente o papel compatível com o acesso que ela já tem, para a regra de teto
(SPEC-02) não tirar acesso de ninguém na atualização. Os papéis devem ser revistos pelo administrador."""
from django.db import migrations


def criar(apps, schema_editor):
    User = apps.get_model("users", "User")
    Membership = apps.get_model("projects", "Membership")
    Perfil = apps.get_model("vetor", "Perfil")
    Auditoria = apps.get_model("vetor", "Auditoria")
    contagem = {}
    for user in User.objects.filter(is_system=False, vetor_perfil__isnull=True):
        ms = Membership.objects.filter(user=user).select_related("role")
        if user.is_superuser:
            papel = "administrador"
        elif any(m.is_admin for m in ms):
            papel = "gestor"
        elif any(set(m.role.permissions or []) - {p for p in (m.role.permissions or []) if p.startswith("view_")}
                 for m in ms if m.role_id):
            papel = "desenvolvedor"
        else:
            papel = "observador"
        Perfil.objects.create(user=user, papel=papel)
        contagem[papel] = contagem.get(papel, 0) + 1
    if contagem:
        Auditoria.objects.create(ator_nome="sistema", acao="perfil.migracao_inicial", alvo_tipo="vetor.perfil",
                                 alvo_id="*", detalhes={"perfis_criados": contagem})


class Migration(migrations.Migration):
    dependencies = [("vetor", "0001_initial"), ("projects", "0068_project_archived_code")]
    operations = [migrations.RunPython(criar, migrations.RunPython.noop)]
