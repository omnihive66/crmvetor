# taiga-protected oficial + exportações de projeto com token assinado. Contexto: raiz do repositório.
FROM taigaio/taiga-protected:6.10.1@sha256:fd4568a97a59225db90f422594cf0e05010be50c9a2a383c01477c5ee521d393
COPY vetor-protected/aplicar.py /tmp/aplicar.py
RUN python /tmp/aplicar.py server.py && rm /tmp/aplicar.py
