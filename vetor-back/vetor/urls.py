from django.urls import include, re_path

from taiga.base import routers
from taiga.urls import urlpatterns as taiga_urlpatterns

from . import api, api_clientes, api_github, api_lembretes, api_projetos, github

router = routers.DefaultRouter(trailing_slash=False)
router.include_root_view = False  # a raiz /api/v1/ continua sendo a do Taiga
router.register(r"vetor/perfis", api.PerfilViewSet, base_name="vetor-perfis")
router.register(r"vetor/auditoria", api.AuditoriaViewSet, base_name="vetor-auditoria")
router.register(r"vetor/clientes", api_clientes.ClienteViewSet, base_name="vetor-clientes")
router.register(r"vetor/contatos", api_clientes.ContatoViewSet, base_name="vetor-contatos")
router.register(r"vetor/documentos", api_clientes.DocumentoViewSet, base_name="vetor-documentos")
router.register(r"vetor/reunioes", api_clientes.ReuniaoViewSet, base_name="vetor-reunioes")
router.register(r"vetor/busca", api_clientes.BuscaViewSet, base_name="vetor-busca")
router.register(r"vetor/demandas", api_projetos.DemandaViewSet, base_name="vetor-demandas")
router.register(r"vetor/participacoes", api_projetos.ParticipacaoViewSet, base_name="vetor-participacoes")
router.register(r"vetor/lembretes", api_lembretes.LembreteViewSet, base_name="vetor-lembretes")
router.register(r"vetor/tokens-agente", api_lembretes.TokenAgenteViewSet, base_name="vetor-tokens-agente")
router.register(r"vetor/repositorios", api_github.RepositorioViewSet, base_name="vetor-repositorios")
router.register(r"vetor/vinculos-codigo", api_github.VinculoViewSet, base_name="vetor-vinculos-codigo")
router.register(r"vetor/eventos-github", api_github.EventoViewSet, base_name="vetor-eventos-github")
# Mesmos prefixos do Taiga: as versões da Vetor respondem antes das oficiais.
router.register(r"webhooks", api.WebhookViewSet, base_name="vetor-webhooks")
router.register(r"webhooklogs", api.WebhookLogViewSet, base_name="vetor-webhooklogs")
router.register(r"projects", api.ProjectViewSet, base_name="vetor-projects")
router.register(r"memberships", api.MembershipViewSet, base_name="vetor-memberships")
router.register(r"roles", api.RolesViewSet, base_name="vetor-roles")

urlpatterns = [
    re_path(r"^api/v1/users/password_recovery/?$",
            api.UsersViewSet.as_view({"post": "password_recovery"}), name="vetor-password-recovery"),
    re_path(r"^api/v1/projects/(?P<pk>\d+)/modules/?$",
            api.ProjectModulesViewSet.as_view({"get": "modules", "patch": "modules"}), name="vetor-project-modules"),
    re_path(r"^api/v1/vetor/agente/lembretes/?$", api_lembretes.AgenteLembretesView.as_view(), name="vetor-agente-lembretes"),
    re_path(r"^api/v1/vetor/agente/demandas/?$", api_lembretes.AgenteDemandasView.as_view(), name="vetor-agente-demandas"),
    re_path(r"^api/v1/vetor/github/webhook/?$", github.webhook, name="vetor-github-webhook"),
    re_path(r"^api/v1/", include(router.urls)),
    *taiga_urlpatterns,
]
