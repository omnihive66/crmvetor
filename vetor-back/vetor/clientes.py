"""Regras do CRM (SPEC-03): quem vê e quem altera clientes, contatos, documentos e reuniões.

Escopo = clientes de que a pessoa é responsável ou que têm projeto onde ela é membro com view_project.
Administrador: todos. Gestor: altera no escopo. Desenvolvedor e Observador: só leitura no escopo.
Documento ligado a projeto exige também acesso ao projeto (salvo administrador e responsável pelo cliente).
"""
import re

from django.db.models import Q

from taiga.base import exceptions as exc
from taiga.projects.models import Project

from . import permissoes
from .models import Cliente, Documento, Perfil


def projetos_visiveis(user, *permissoes_extras):
    """Projetos onde a própria pessoa tem as permissões. Tudo num filter() só: filtros separados sobre
    memberships viram joins diferentes e aceitariam a permissão de outro membro."""
    if user.is_superuser:
        return Project.objects.all()
    return Project.objects.filter(memberships__user=user,
                                  memberships__role__permissions__contains=["view_project", *permissoes_extras])


def clientes_visiveis(user):
    if not user.is_authenticated or not user.is_active:
        return Cliente.objects.none()
    if permissoes.e_administrador(user):
        return Cliente.objects.all()
    ids = projetos_visiveis(user).values("id")
    return Cliente.objects.filter(Q(responsavel=user) | Q(projetos__project_id__in=ids)).distinct()


def documentos_visiveis(user):
    qs = Documento.objects.filter(cliente__in=clientes_visiveis(user))
    if permissoes.e_administrador(user):
        return qs
    return qs.filter(Q(projeto__isnull=True) | Q(projeto__in=projetos_visiveis(user)) | Q(cliente__responsavel=user))


def pode_criar_cliente(user):
    return permissoes.e_administrador(user) or permissoes.papel(user) == Perfil.GESTOR


def exigir_edicao(user, cliente):
    """Para escrita em qualquer coisa do cliente. Cliente fora do escopo responde 404 (não revela que existe)."""
    if not clientes_visiveis(user).filter(pk=cliente.pk).exists():
        raise exc.NotFound()
    if not (permissoes.e_administrador(user) or permissoes.papel(user) == Perfil.GESTOR):
        raise exc.PermissionDenied("Seu papel permite só consultar clientes.")


def cnpj_valido(digitos):
    if len(digitos) != 14 or len(set(digitos)) == 1:
        return False
    def dv(base, pesos):
        resto = sum(int(d) * p for d, p in zip(base, pesos)) % 11
        return "0" if resto < 2 else str(11 - resto)
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = dv(digitos[:12], p1)
    return digitos[12:] == d1 + dv(digitos[:12] + d1, [6] + p1)


def normalizar_cnpj(valor):
    return re.sub(r"\D", "", valor or "")
