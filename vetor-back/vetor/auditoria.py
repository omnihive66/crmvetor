from .ator import ATOR
from .models import Auditoria


def registrar(acao, alvo, **detalhes):
    ator = ATOR.get()
    if ator is not None and not ator.is_authenticated:
        ator = None
    Auditoria.objects.create(
        ator=ator, ator_nome=ator.username if ator else "sistema", acao=acao,
        alvo_tipo=alvo._meta.label_lower, alvo_id=str(alvo.pk), detalhes=detalhes)
