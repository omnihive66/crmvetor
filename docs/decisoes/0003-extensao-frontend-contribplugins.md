# 0003 — Extensão do frontend por contribPlugins

- Data: 22/10/2026 • Estado: proposta (confirmar na SPEC-01)

## Contexto
O taiga-front é uma SPA AngularJS compilada. O `app-loader` lê `conf.json` → `contribPlugins` e injeta JS, CSS, módulo AngularJS e templates de cada plugin, sem recompilar o núcleo. O nome "Taiga" está em textos do locale e em templates do núcleo.

## Decisão
Marca, tokens de cor, shell de navegação e telas novas entram como um plugin em `vetor-front/`, montado no container oficial com o `conf.json`. A SPEC-01 decide como trocar os textos do núcleo que dizem "Taiga": sobrescrever o locale pt-BR montado ou fazer build próprio do front.

## Consequências
- O taiga-front é AGPL-3.0: a interface modificada servida pela rede precisa oferecer o código-fonte aos usuários. O produto terá link para o repositório com o código correspondente.
- Atualizar o front exige conferir se os seletores e templates que o plugin usa continuam iguais.
