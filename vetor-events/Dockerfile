# taiga-events oficial + autorização de assinaturas (vetor-events/assinatura.js). Contexto: raiz do repositório.
FROM taigaio/taiga-events:6.10.0@sha256:92fc0822564f891700d74d23fa44951adf2845cf50c9e56bfd0ef29abdc1ab40
COPY vetor-events/assinatura.js src/ws/assinatura.js
COPY vetor-events/aplicar.js /tmp/aplicar.js
RUN node /tmp/aplicar.js src/ws/client.js && rm /tmp/aplicar.js && chown -R taiga:taiga src/ws
