# Inventário de dependências e imagens (SPEC-10)

Gerado de `infra/docker-compose.override.yml`, dos `Dockerfile` e dos submódulos em 23/10/2026. As imagens são fixadas por **digest**, e uma troca de versão é uma mudança revisada no repositório.

## Imagens em execução
| Serviço | Imagem | Base fixada |
|---|---|---|
| taiga-back, taiga-async, taiga-manage | `vetor/taiga-back:6.10.2-vetor` | `taigaio/taiga-back:6.10.2@sha256:4beed8f62c9ffbbcea824aa01c48fa72a2c2f713be6732e2ee37d2e777843f51` |
| taiga-front | `vetor/taiga-front:6.10.3-vetor` | `taigaio/taiga-front:6.10.3@sha256:570c8792ce802ff803a2275967e1d593cdd7c748e2d63163c4dab35fe2d2d646` (build usa a do back acima) |
| taiga-events | `vetor/taiga-events:6.10.0-vetor` | `taigaio/taiga-events:6.10.0@sha256:92fc0822564f891700d74d23fa44951adf2845cf50c9e56bfd0ef29abdc1ab40` |
| taiga-protected | `vetor/taiga-protected:6.10.1-vetor` | `taigaio/taiga-protected:6.10.1@sha256:fd4568a97a59225db90f422594cf0e05010be50c9a2a383c01477c5ee521d393` |
| taiga-db | `postgres:12.3@sha256:a06e6e6e519b7a329c419f8221edec66cfc45511e8b80e262c12103ba745cf19` | — |
| taiga-async-rabbitmq, taiga-events-rabbitmq | `rabbitmq:3.8-management-alpine@sha256:c3e526769bfd885c898d1132e1008b216800e8543619c30d5959b220285564ef` | — |
| taiga-gateway | `nginx:1.19-alpine@sha256:07ab71a2c8e4ecb19a5a5abcfb3a4f175946c001c8af288b1aa766d67b0d05d2` | — |

## Código-fonte oficial (submódulos, só leitura)
| Submódulo | Versão | Commit | Licença |
|---|---|---|---|
| `upstream/taiga-back` | 6.10.2 | 4b023d8414fc | MPL-2.0 (`LICENSE`) |
| `upstream/taiga-front` | 6.10.3 | a17d8c91070b | AGPL-3.0 (`LICENSE`) |
| `upstream/taiga-events` | 6.10.0 | e411856df465 | MPL-2.0 (`LICENSE`) |
| `upstream/taiga-protected` | 6.10.1 | 3fc1f92b7529 | MPL-2.0 (`LICENSE`) |
| `upstream/taiga-docker` | 6.9.0 | e12c106b265a | MPL-2.0 (`LICENSE`) |

As dependências Python do back são as do `requirements.txt` oficial, já dentro da imagem. A Vetor **não acrescenta pacote Python nem JavaScript em produção**: as telas próprias não têm dependências e o app `vetor` usa só o que o Taiga traz.

## Ferramentas só de desenvolvimento e QA (fora da produção)
| Ferramenta | Versão | Uso |
|---|---|---|
| `polib` | 1.2.0 | compilar traduções (`vetor.sh i18n`, em container descartável) |
| Playwright + Chromium | 1.56.1 | QA visual e de teclado (`scripts/qa/*.js`) |
| axe-core | 4.10.2 | auditoria de acessibilidade (`scripts/qa/acessibilidade.js`) |
| `actions/checkout` | v4.3.1 (`34e114876b0b11c390a56381ad16ebd13914f8d5`) | CI (`.github/workflows/ci.yml`), fixado por commit |

## Licenças e avisos
Os avisos de licença e as atribuições do Taiga estão preservados (README → "Créditos e licenças"; cabeçalhos dos arquivos derivados, como `infra/taiga-gateway.conf`). O front é AGPL-3.0: quem usa pela rede tem acesso ao código pelo link em "Código-fonte" (`VETOR_SOURCE_URL`). A licença dos arquivos próprios da Vetor ainda está **pendente de decisão**.
