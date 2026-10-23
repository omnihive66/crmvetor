#!/usr/bin/env bash
# Atalhos da instalação local. Uso: ./scripts/vetor.sh {init-env|up|down|manage ...|i18n|backup|restore <dir>|restaurar-teste <dir>|logs}
set -euo pipefail
cd "$(dirname "$0")/.."
DC=(docker compose --env-file .env -p vetor -f upstream/taiga-docker/docker-compose.yml
    -f upstream/taiga-docker/docker-compose-inits.yml -f infra/docker-compose.override.yml)
PG=postgres:12.3@sha256:a06e6e6e519b7a329c419f8221edec66cfc45511e8b80e262c12103ba745cf19
# Chave do backup (SPEC-10): arquivo FORA do repositório e do diretório de backup; guarde uma cópia offline.
CHAVE=$( [ -f .env ] && sed -n 's/^VETOR_BACKUP_CHAVE_ARQUIVO=//p' .env || true)
cifrar()   { openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass "file:$CHAVE" -in "$1" -out "$1.enc" && rm -f "$1"; }
decifrar() { openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass "file:$CHAVE" -in "$1.enc" -out "$2"; }
# Arquivo do backup ($1/$2): o original ou, se cifrado, uma cópia decifrada em $3.
arquivo()  { if [ -f "$1/$2.enc" ]; then [ -f "$CHAVE" ] || { echo "backup cifrado: defina VETOR_BACKUP_CHAVE_ARQUIVO" >&2; exit 1; }
               decifrar "$1/$2" "$3/$2"; echo "$3/$2"; else echo "$1/$2"; fi; }
registrar() { "${DC[@]}" exec -T taiga-back python manage.py vetor_registrar_backup "$@" >/dev/null || echo "aviso: registro do backup não gravado" >&2; }

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
    umask 077; out="backups/$(date -u +%Y%m%dT%H%M%SZ)"; mkdir -p "$out"  # só o dono lê o backup
    "${DC[@]}" exec -T taiga-db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc taiga' > "$out/taiga.dump"
    "${DC[@]}" exec -T taiga-back tar -C /taiga-back -czf - media > "$out/media.tar.gz"
    cp .env "$out/env.backup"; chmod 600 "$out/env.backup"  # material de recuperação dos segredos
    tam=$(stat -c %s "$out/taiga.dump"); tmed=$(stat -c %s "$out/media.tar.gz"); cif=()
    if [ -n "$CHAVE" ] && [ -f "$CHAVE" ]; then
      for f in taiga.dump media.tar.gz env.backup; do cifrar "$out/$f"; done; cif=(--cifrado)
      (cd "$out" && sha256sum taiga.dump.enc media.tar.gz.enc env.backup.enc > SHA256SUMS)
    else
      echo "AVISO: backup SEM criptografia (defina VETOR_BACKUP_CHAVE_ARQUIVO no .env)" >&2
      (cd "$out" && sha256sum taiga.dump media.tar.gz env.backup > SHA256SUMS)
    fi
    registrar --tipo backup --local "$out" --resultado ok "${cif[@]}" --detalhes "{\"banco_bytes\": $tam, \"media_bytes\": $tmed}"
    echo "Backup em $out" ;;
  restore)
    dir="${2:?informe o diretório do backup}"; (cd "$dir" && sha256sum -c SHA256SUMS)
    tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
    dump=$(arquivo "$dir" taiga.dump "$tmp"); media=$(arquivo "$dir" media.tar.gz "$tmp")
    "${DC[@]}" stop taiga-back taiga-async
    "${DC[@]}" exec -T taiga-db sh -c 'pg_restore -U "$POSTGRES_USER" -d taiga --clean --if-exists --no-owner' < "$dump"
    "${DC[@]}" run --rm -T --entrypoint sh taiga-manage -c 'rm -rf /taiga-back/media/* && tar -C /taiga-back -xzf -' < "$media"
    "${DC[@]}" start taiga-back taiga-async
    "${DC[@]}" restart taiga-gateway  # o nginx guarda o IP antigo do taiga-back
    echo "Restaurado de $dir" ;;
  restaurar-teste)
    # Restauração ISOLADA (SPEC-10): banco descartável fora da rede da instalação; nada da produção é tocado.
    dir="${2:?informe o diretório do backup}"; inicio=$(date +%s); (cd "$dir" && sha256sum -c --quiet SHA256SUMS)
    tmp=$(mktemp -d); rede="vetor-restauracao-$$"; db="vetor-restauracao-db-$$"
    trap 'docker rm -f "$db" >/dev/null 2>&1; docker network rm "$rede" >/dev/null 2>&1; rm -rf "$tmp"' EXIT
    dump=$(arquivo "$dir" taiga.dump "$tmp"); media=$(arquivo "$dir" media.tar.gz "$tmp")
    docker network create --internal "$rede" >/dev/null
    docker run -d --name "$db" --network "$rede" -e POSTGRES_USER=taiga -e POSTGRES_PASSWORD=restauracao -e POSTGRES_DB=taiga "$PG" >/dev/null
    until docker exec "$db" pg_isready -U taiga -d taiga >/dev/null 2>&1; do sleep 1; done; sleep 2
    docker exec -i "$db" pg_restore -U taiga -d taiga --no-owner < "$dump" 2>"$tmp/erros.txt" || true
    TABELAS="users_user projects_project userstories_userstory tasks_task attachments_attachment vetor_cliente vetor_documento vetor_reuniao vetor_lembrete vetor_auditoria"
    contar() { for t in $TABELAS; do printf '%s=%s ' "$t" "$("$@" psql -U taiga -d taiga -Atc "select count(*) from $t" 2>/dev/null || echo erro)"; done; }
    restaurado=$(contar docker exec "$db"); echo "restaurado: $restaurado"
    # Esquema: a imagem atual do back roda contra o banco restaurado e não pode ter migração pendente.
    plano=$(docker run --rm --network "$rede" -e POSTGRES_HOST="$db" -e POSTGRES_DB=taiga -e POSTGRES_USER=taiga -e POSTGRES_PASSWORD=restauracao \
      -e TAIGA_SECRET_KEY=restauracao --entrypoint python vetor/taiga-back:6.10.2-vetor manage.py migrate --plan 2>&1 | tail -3)
    echo "migrações pendentes: $plano"
    arquivos=$(tar -tzf "$media" | grep -vc '/$' || true); echo "arquivos de mídia no backup: $arquivos"
    fim=$(date +%s); ok=ok
    echo "$plano" | grep -q "No planned migration operations" || ok=falhou
    echo "$restaurado" | grep -q "=erro" && ok=falhou
    echo "erros do pg_restore: $(grep -c . "$tmp/erros.txt" || true) linha(s)"
    det="{\"duracao_s\": $((fim - inicio)), \"arquivos_midia\": $arquivos, \"contagens\": \"${restaurado% }\"}"
    registrar --tipo restauracao_teste --local "$dir" --resultado "$ok" --detalhes "$det"
    echo "Restauração isolada: $ok em $((fim - inicio)) s"; [ "$ok" = ok ] ;;
  *) sed -n 2p "$0"; exit 1 ;;
esac
