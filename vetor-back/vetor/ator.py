"""Quem está agindo na requisição atual (para a auditoria). Sem modelos: carregado com os settings.

O Request do Taiga não repassa o usuário autenticado para o request do Django, então o ator é
capturado na própria autenticação da API (classes abaixo, usadas no lugar das oficiais).
"""
import contextvars

from taiga.auth.authentication import JWTAuthentication as _JWT
from taiga.auth.backends import Session as _Session
from taiga.external_apps.auth_backends import Token as _Token

ATOR = contextvars.ContextVar("vetor_ator", default=None)


def _com_ator(base):
    class Auth(base):
        def authenticate(self, request):
            result = super().authenticate(request)
            if result:
                ATOR.set(result[0])
            return result
    Auth.__name__ = Auth.__qualname__ = base.__name__
    return Auth


JWTAuthentication, Session, Token = map(_com_ator, (_JWT, _Session, _Token))


class LimparAtorMiddleware:
    """O ator vale só durante a requisição (os workers do gunicorn reaproveitam a thread)."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = ATOR.set(None)
        try:
            return self.get_response(request)
        finally:
            ATOR.reset(token)
