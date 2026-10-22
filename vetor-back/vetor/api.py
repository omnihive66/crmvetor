from django.utils.translation import gettext as _

from taiga.base import exceptions as exc
from taiga.base import response
from taiga.users import api as users_api


class UsersViewSet(users_api.UsersViewSet):
    def password_recovery(self, request, pk=None):
        # Mesma resposta para conta existente ou não: não revela quem tem acesso (DESIGN.md, tela de login).
        try:
            return super().password_recovery(request, pk)
        except exc.WrongArguments:
            if not request.DATA.get("username"):
                raise
            return response.Ok({"detail": _("Mail sent successfully!")})
