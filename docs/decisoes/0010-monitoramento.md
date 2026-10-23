# 0010 — Incidentes de monitoramento (Uptime Kuma e Beszel)

- Data: 23/10/2026 • Estado: aceita

## Contexto
O código-fonte das versões atuais foi inspecionado (`docs/integracoes/monitoramento.md`):
- **Kuma 2.5.7:** notificação "Webhook" com JSON `{heartbeat, monitor, msg}`; cabeçalhos extras configuráveis; sem assinatura. O monitor enviado já exclui campos sensíveis (`includeSensitiveData=false`).
- **Beszel v0.21.1:** alertas pelo Shoutrrr, com `generic` e `template=json`, que manda `{title, message}`. Não há id de evento nem horário; o id do sistema vem só no link. Cabeçalhos pelo prefixo `@`. Sem assinatura.
- Os dois só notificam **mudanças**, não há amostras periódicas.

## Decisão
- **Recepção:**
  - Um webhook por provedor, com cabeçalho `X-Vetor-Token` (segredo no servidor, rotação com `_ANTERIOR`) e HTTPS em produção. É o mecanismo que os dois suportam sem plugin.
  - O corpo é normalizado na chegada para o contrato da spec. Formato não reconhecido dá 400. O processamento é feito no worker, com novas tentativas e fila de falhas.
- **Dados:**
  - Só uma lista de campos permitidos do payload; URLs sem credenciais nem query.
  - Retenção de 90 dias para o conteúdo bruto.
  - Os logs têm ids e status, nunca o token.
- **Incidente:**
  - Um aberto por recurso e tipo; repetidos são agrupados.
  - Janela de reincidência de 15 min.
  - Estado só muda com evento mais novo.
  - A recuperação não conclui a demanda.
- **Triagem:**
  - Recurso desconhecido nunca é associado por nome ou suposição. Fica sem projeto até o Administrador mapear.
  - Os incidentes dele existem, mas sem demanda e sem aviso até o mapeamento.
- **Aviso:** e-mail ao dono do projeto, no máximo um por incidente a cada 30 min.
- **Disponibilidade:**
  - Não calculamos porcentagem: com eventos só de mudança, qualquer número seria inventado.
  - Conector sem dados ou com falha mais nova que o último sucesso aparece como "Telemetria indisponível", nunca como "no ar".
  - **Para calcular depois:** coletar periodicamente o `/metrics` do Kuma (chave de API) ou a API da página de status, com a fórmula documentada.

## Alternativas descartadas
- **Ler o Kuma ativamente agora:** o Kuma oferece `/metrics` (Prometheus, com chave de API) e a API das páginas de status, mas isso exige guardar uma credencial do Kuma no CRM ou publicar uma página de status. Fica para quando o cálculo de disponibilidade histórica for pedido.
- **Associar recurso a projeto pelo nome:** inventa associação, e a spec proíbe.
- **Concluir a demanda na recuperação:** a spec proíbe por padrão.
