"""correlation_id (SPEC-10): o mesmo id liga a linha do gateway, os logs do back e a resposta (X-Request-ID)."""
import contextvars
import logging
import re
import uuid

ID = contextvars.ContextVar("correlation_id", default="-")
VALIDO = re.compile(r"^[A-Za-z0-9._-]{8,64}$")  # id vindo de fora só se for seguro para log


class CorrelacaoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cid = request.headers.get("X-Request-ID", "")
        cid = cid if VALIDO.match(cid) else uuid.uuid4().hex
        token = ID.set(cid)
        try:
            resposta = self.get_response(request)
        finally:
            ID.reset(token)
        resposta["X-Request-ID"] = cid
        return resposta


class Filtro(logging.Filter):
    def filter(self, record):
        record.correlation_id = ID.get()
        return True
