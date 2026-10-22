import json

import pytest
from django.urls import reverse

from tests import factories as f

pytestmark = pytest.mark.django_db
URL = "/api/v1/users/password_recovery"


def post(client, username):
    return client.post(URL, json.dumps({"username": username}), content_type="application/json")


def test_rota_oficial_aponta_para_a_versao_da_vetor():
    assert reverse("users-password-recovery") == URL


def test_conta_existente_e_inexistente_tem_a_mesma_resposta(client):
    f.UserFactory.create(username="maria", email="maria@example.com")
    existente, inexistente = post(client, "maria"), post(client, "ninguem@example.com")
    assert (existente.status_code, existente.json()) == (inexistente.status_code, inexistente.json())
    assert existente.status_code == 200


def test_so_envia_email_para_conta_existente(client, settings):
    from django.core import mail
    f.UserFactory.create(username="maria", email="maria@example.com")
    post(client, "ninguem")
    assert len(mail.outbox) == 0
    post(client, "maria")
    assert [m.to for m in mail.outbox] == [["maria@example.com"]]


def test_usuario_vazio_continua_invalido(client):
    assert post(client, "").status_code == 400
