# 0011 — Pós-venda: sinais separados e adoção só com telemetria do produto

- Data: 23/10/2026 • Estado: aceita

## Decisão
- **Painel do cliente** (aba Operação) com quatro blocos independentes:
  - **Relacionamento:** última reunião com link para a ata, próximo contato e pendências das demandas.
  - **Disponibilidade:** só incidentes de queda.
  - **Infraestrutura:** alertas de limite, com fonte e horário.
  - **Adoção.**

  Não há nota composta: a spec pede indicadores separados até a gestão validar pesos.
- **Disponibilidade ≠ infraestrutura:** um alerta de CPU ou memória aberto não deixa o recurso "fora do ar" no painel; a QA pegou essa confusão e ela foi corrigida.
- **Adoção:**
  - Só com eventos enviados pelo próprio produto (`docs/integracoes/telemetria-uso.md`).
  - Login é separado de atividade.
  - Janela por produto, no fuso America/Sao_Paulo.
  - Pseudônimo cifrado de novo por produto.
  - Lista fechada de campos.
  - Retenção de 180 dias.
- **Sem dados ≠ desuso:** um alerta de desuso exige alerta ligado, sem exceção ativa e **telemetria viva** (evento `pulso` ou outro nos últimos 2 dias). Se o produto parou de enviar, a tela diz "telemetria parada".
- **Isolamento:**
  - O painel parte do cliente que a pessoa vê (fora do acesso: 404).
  - Recursos e demandas só dos projetos desse cliente que a pessoa acompanha.
  - Pseudônimos nunca saem da API.
- **CPU/RAM não são adoção:** ficam em Infraestrutura, com aviso explícito.

## Pendências
- Qual produto do cliente vai enviar eventos, e qual o significado de "atividade" para ele: definir com cada produto.
- Último acesso **ao CRM** pelos usuários internos não é adoção do cliente e não entra aqui.
