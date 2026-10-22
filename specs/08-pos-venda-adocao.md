# SPEC-08 — Operação, pós-venda e adoção

## Resultado
Gestor acompanha relacionamento, disponibilidade técnica e uso real sem confundir sinais distintos.

## Dados e telas
Cliente: última reunião, próximo contato e pendências. Produto: disponibilidade e incidentes por monitor. Infraestrutura: métricas com fonte e timestamp. Adoção: último acesso, usuários ativos e utilização de funcionalidades, somente quando o produto cliente disponibilizar esses eventos.

Instrumentação proposta: eventos pseudonimizados com client_id, product_id, event_type e occurred_at; deduplicação e minimização de dados. Autenticar ingestão, definir retenção e limitar acesso. Não enviar conteúdo de documentos, mensagens ou credenciais como telemetria. Separar evento de login de atividade efetiva do produto. Definir janela de usuários ativos e timezone antes de exibir métrica.

## Saúde do cliente
Começar com indicadores separados, não uma nota opaca. Se um índice composto for solicitado, apresentar pesos, regras, dados ausentes e justificativa; validar com a gestão. Falta de telemetria aparece como “sem dados”. Alertas de desuso devem permitir exceções e ajuste por contrato/contexto.

## Aceite
Última reunião abre a ata correspondente. Último acesso informa origem e atualização. Dados sintéticos de validação são identificados. Ausência de eventos não vira automaticamente desuso nem falha. Painel diferencia queda, CPU alta e baixa adoção. Visão por cliente não permite inferir dados de outro cliente.
