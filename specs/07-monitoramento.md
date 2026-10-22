# SPEC-07 — Uptime Kuma e Beszel

## Resultado
Alertas de disponibilidade e infraestrutura geram incidentes acionáveis associados ao cliente e projeto corretos.

## Contrato conceitual de evento
Campos: provider, external_event_id, resource_id, occurred_at, received_at, status, severity, summary e URL de origem. Preservar payload necessário com dados sensíveis removidos e retenção definida. Mapear explicitamente cada monitor/host para projeto; evento sem mapeamento fica em triagem, sem associação inventada.

## Implementação
Inspecionar versões reais de Kuma e Beszel e seus canais/APIs documentados. Implementar adaptador conforme o transporte disponível; não pressupor API REST pública ou assinatura nativa. Se o provedor não assina webhooks, proteger recepção por mecanismo compatível com o conector, HTTPS e segredo no servidor, sem segredos em logs.

Deduplicar incidentes por provedor/recurso/tipo enquanto abertos; agrupar reincidências; permitir janela antirruído configurável; recovery atualiza o incidente e não conclui tarefa automaticamente por padrão. Responsável por projeto recebe notificação com controle de frequência. Retry com limite, fila de falhas, métricas e painel de diagnóstico.

## Aceite
Sequência queda → alertas repetidos → recuperação resulta em um incidente com linha do tempo. Eventos fora de ordem não revertem estado recente. Recurso desconhecido entra em triagem. Falha do conector aparece como telemetria indisponível; nunca como disponibilidade de 100%. Disponibilidade histórica só será calculada se houver dados suficientes e fórmula explícita. CPU/RAM não são indicadores de adoção do cliente.
