# Imagem do frontend da Vetor Sistemas: taiga-front oficial + marca aplicada no build.
# Contexto de build: raiz do repositório. Arquivos do Taiga derivados aqui continuam AGPL-3.0.
FROM taigaio/taiga-front:6.10.3@sha256:570c8792ce802ff803a2275967e1d593cdd7c748e2d63163c4dab35fe2d2d646 AS taiga

# Etapa só de build: reaproveita a imagem do taiga-back (Python 3.11), já baixada.
FROM taigaio/taiga-back:6.10.2@sha256:4beed8f62c9ffbbcea824aa01c48fa72a2c2f713be6732e2ee37d2e777843f51 AS build
COPY --from=taiga /usr/share/nginx/html /html
COPY vetor-front /vetor-front
COPY assets/logo-vetor-original.jpg /vetor-front/logo-vetor-original.jpg
RUN python /vetor-front/build.py /html /vetor-front /out && chmod -R a+rX /out

FROM taiga
COPY --from=build /out/ /usr/share/nginx/html/
