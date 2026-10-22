import re
from pathlib import Path

from django.conf import settings
from django.utils import translation

VETOR_PO = Path(__file__).resolve().parents[1] / "locale/pt_BR/LC_MESSAGES/django.po"
TAIGA_PO = Path(settings.BASE_DIR) / "taiga/locale/pt_BR/LC_MESSAGES/django.po"


def msgids(path):
    text = path.read_text(encoding="utf-8")
    return {"".join(re.findall(r'"(.*)"', m)) for m in re.findall(r'^msgid ((?:".*"\n)+)', text, re.M)} - {""}


def test_todo_msgid_da_vetor_existe_no_taiga():
    # Se o Taiga mudar um texto, a tradução da Vetor deixa de valer em silêncio: falhar aqui.
    assert msgids(VETOR_PO) - msgids(TAIGA_PO) == set()


def test_traducao_da_vetor_vence_a_do_taiga():
    with translation.override("pt-br"):
        assert translation.gettext("[Taiga] Password recovery") == "[Vetor Sistemas] Recuperação de acesso"
        assert translation.gettext("Taiga") == "Vetor Sistemas"
