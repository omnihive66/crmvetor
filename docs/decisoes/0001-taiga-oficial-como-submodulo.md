# 0001 — Taiga oficial como submódulo fixado, sem fork

- Data: 22/10/2026 • Estado: aceita

## Contexto
O pedido não indicou fork próprio. As specs pedem partir do código real e manter a possibilidade de atualizar.

## Decisão
Usar os repositórios oficiais `taigaio/*` como submódulos em `upstream/`, fixados em taiga-back 6.10.2, taiga-front 6.10.3, taiga-events 6.10.0, taiga-protected 6.10.1 e taiga-docker `main@e12c106`. Rodar as imagens oficiais com digest fixo. Nada dentro de `upstream/` é editado.

## Consequências
- Atualizar é trocar o commit do submódulo e os digests, e rodar migrações e testes.
- Se uma necessidade só puder ser atendida mudando o núcleo, isso vira nova decisão (fork ou patch versionado), com impacto em licença (MPL/AGPL) registrado.
