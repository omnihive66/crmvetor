#!/usr/bin/env bash
# Atalhos da instalação local. Uso: ./scripts/vetor.sh {init-env|up|down|manage ...|i18n|backup|restore <dir>|logs}
set -euo pipefail
cd "$(dirname "$0")/.."
DC=(docker compose --env-file .env -p vetor -f upstream/taiga-docker/docker-compose.yml
    -f upstream/taiga-docker/docker-compose-inits.yml -f infra/docker-compose.override.yml)

case "${1:-}" in
  init-env)
    [ -e .env ] && { echo ".env já existe; não sobrescrito." >&2; exit 1; }
    awk '{ while (sub(/CHANGE_ME/, r())) ; print } function r(  c) { c = "openssl rand -hex 32"; c | getline s; close(c); return s }' .env.example > .env
    chmod 600 .env; echo ".env criado com segredos aleatórios." ;;
  up)      "${DC[@]}" up -d --build --scale taiga-manage=0
           "${DC[@]}" restart taiga-gateway ;;  # o nginx guarda o IP dos containers recriados
  down)    "${DC[@]}" down ;;
  logs)    "${DC[@]}" logs -f "${@:2}" ;;
  manage)  "${DC[@]}" run --rm taiga-manage "${@:2}" ;;
  i18n)    # compila as traduções da Vetor (vetor-back/vetor/locale); a imagem oficial não traz msgfmt
    CA=(); [ -n "${PIP_CERT:-}" ] && CA=(-v "$PIP_CERT:/ca.crt:ro" -e PIP_CERT=/ca.crt)
    docker run --rm "${CA[@]}" -v "$PWD/vetor-back/vetor/locale:/l" --entrypoint sh taigaio/taiga-back:6.10.2 -c \
      'pip install -q polib==1.2.0 && python -c "import glob, polib; [polib.pofile(f).save_as_mofile(f[:-3] + \".mo\") for f in glob.glob(\"/l/*/LC_MESSAGES/django.po\")]"' ;;
  backup)
    out="backups/$(date -u +%Y%m%dT%H%M%SZ)"; mkdir -p "$out"
    "${DC[@]}" exec -T taiga-db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc taiga' > "$out/taiga.dump"
    "${DC[@]}" exec -T taiga-back tar -C /taiga-back -czf - media > "$out/media.tar.gz"
    cp .env "$out/env.backup"; chmod 600 "$out/env.backup"
    (cd "$out" && sha256sum taiga.dump media.tar.gz > SHA256SUMS)
    echo "Backup em $out" ;;
  restore)
    dir="${2:?informe o diretório do backup}"; (cd "$dir" && sha256sum -c SHA256SUMS)
    "${DC[@]}" stop taiga-back taiga-async
    "${DC[@]}" exec -T taiga-db sh -c 'pg_restore -U "$POSTGRES_USER" -d taiga --clean --if-exists --no-owner' < "$dir/taiga.dump"
    "${DC[@]}" run --rm -T --entrypoint sh taiga-manage -c 'rm -rf /taiga-back/media/* && tar -C /taiga-back -xzf -' < "$dir/media.tar.gz"
    "${DC[@]}" start taiga-back taiga-async
    "${DC[@]}" restart taiga-gateway  # o nginx guarda o IP antigo do taiga-back
    echo "Restaurado de $dir" ;;
  *) sed -n 2p "$0"; exit 1 ;;
esac
