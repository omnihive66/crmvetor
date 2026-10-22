#!/usr/bin/env bash
# Roda a suíte pytest do taiga-back (upstream fixado) num Postgres descartável, sem tocar no banco de desenvolvimento.
# Uso: ./scripts/test-backend.sh [caminhos/args do pytest]
# Com o app da Vetor: ./scripts/test-backend.sh --ds=vetor.tests.settings vetor/tests tests/...
set -euo pipefail
cd "$(dirname "$0")/.."
IMG=taigaio/taiga-back:6.10.2@sha256:4beed8f62c9ffbbcea824aa01c48fa72a2c2f713be6732e2ee37d2e777843f51
DB="vetor-testdb-$$"  # nome por execução: rodadas em paralelo não derrubam o banco uma da outra
docker run -d --name "$DB" -e POSTGRES_USER=taiga -e POSTGRES_PASSWORD=taiga -e POSTGRES_DB=taiga postgres:12.3@sha256:a06e6e6e519b7a329c419f8221edec66cfc45511e8b80e262c12103ba745cf19 >/dev/null
trap 'docker rm -f "$DB" >/dev/null' EXIT
until docker exec "$DB" pg_isready -U taiga >/dev/null 2>&1; do sleep 1; done
# Ambientes com proxy TLS próprio: exporte PIP_CERT com o bundle de CA para o pip do container confiar nele.
CA=(); [ -n "${PIP_CERT:-}" ] && CA=(-v "$PIP_CERT:/ca.crt:ro" -e PIP_CERT=/ca.crt)
docker run --rm --network "container:$DB" "${CA[@]}" -v "$PWD/upstream/taiga-back:/src:ro" -v "$PWD/vetor-back/vetor:/vetor:ro" --entrypoint sh "$IMG" -c \
  "cp -a /src /work && cp -a /vetor /work/vetor && cd /work && cp settings/config.py.dev.example settings/config.py && pip install -q -r requirements-devel.txt && python -m pytest -q -p no:cacheprovider ${*:-tests}"
