# Custos — regras, importação e o que falta para AWS/Oracle (SPEC-09)

**Acesso: fechado para o usuário matriz.**
- Só o(s) usuário(s) listados em `VETOR_FINANCEIRO_USUARIOS`, no `.env` do servidor, consultam e alteram custos. A listagem e a exportação seguem a mesma regra.
- Vazio deixa o financeiro fechado para todos.
- Quem não está na lista recebe 403, inclusive outros administradores e gestores. Sem sessão: 401.
- Não há opção na tela para liberar outras pessoas. A antiga "Ver custos" por pessoa (SPEC-02) não tem mais efeito, e tentar ligá-la pela API dá 400.
- O matriz vê os clientes do seu escopo (SPEC-03); sendo Administrador, todos.
- A auditoria registra quem alterou, o que e quando, **sem valores**, porque a auditoria é vista por quem não tem a permissão financeira.

**Fonte contratual:** o sistema financeiro externo, cujo nome ainda está em aberto (`VETOR_SISTEMA_FINANCEIRO_*`). Os valores daqui são internos, para estimar e comparar.

## Estimativa
- **Versões:** "Criar nova versão" congela a atual e copia cabeçalho e itens. Só a mais nova é editável. Moeda, validade, fonte e premissas ficam em cada versão.
- **Item:**
  - **Tipo:** custo ou preço de venda.
  - **Natureza:** fixo, variável ou ajuste.
  - **Recorrência:** único ou mensal.
  - Os totais saem por grupo (tipo × recorrência); custo e preço, único e mensal, nunca se somam.
- **Fórmula:** o valor de fixo e de variável é `quantidade × preço unitário`, em decimal com 6 casas (preços fracionários, como R$ 0,000125 por requisição). Por grupo:
  - Antes de ajustes = fixo + variável.
  - Ajuste (imposto, desconto) = **antes de ajustes × percentual / 100**. Incide só sobre essa base, nunca sobre outro ajuste, então não há dupla contagem.
  - Total = antes de ajustes + ajustes.
- **Exemplo do aceite:** 100 × R$ 0,20 + R$ 50 fixos = R$ 70,00 antes de ajustes.
- **Moeda diferente:**
  - O item precisa apontar para uma **taxa registrada** (par, taxa, data e origem, ex.: "PTAX BCB venda"), e a conversão aparece com esses dados.
  - Sem taxa, o item fica **fora do total** e a tela diz por quê.

## Realizado
- **Entrada:** manual ou importação CSV. AWS e Oracle só depois de credenciais e contrato técnico (abaixo).
- **Período:** mensal (1º dia do mês).
- **"Parcial":** marca o consumo do mês em curso. A comparação avisa "não é fatura final".
- **Sem cliente** é **não alocado**: compartilhado ou sem tag.
  - Só entra num cliente por uma **regra de rateio** da categoria **naquele mês**, com partes por cliente que somam 100%.
  - Sem regra, aparece em "Não alocados" e não entra em ninguém.

### CSV
```
id;periodo;categoria;descricao;valor;moeda;cliente;parcial
fatura-123-l1;2026-10;infra;EC2 produção;1.234,56;BRL;12;não
fatura-123-l2;2026-10;cluster;Kubernetes compartilhado;300,00;BRL;;sim
```
- **Formato:** separador `;` ou `,`.
- **`valor`:** aceita `1234.56`, `1234,56` ou `1.234,56`.
- **`cliente`:** id do cliente; vazio = não alocado.
- **`parcial`:** sim/não.
- **Lote** (nome da fonte + mês, ex.: `aws-2026-10`) + `id` identificam a linha. **Reimportar não duplica.**
- **Tudo ou nada:** qualquer linha com erro recusa o arquivo inteiro, com a lista de linhas e motivos.

## Orçamento × realizado
- Orçamento por cliente e mês, com valor, moeda e limite de alerta em % (padrão 10).
- **Diferença** = realizado − orçamento. **Percentual** = diferença ÷ orçamento × 100. Exemplo do aceite: 100 × 120 dá +R$ 20,00 e +20%.
- **Orçamento zero:** o percentual "não se aplica" (sem divisão por zero). Qualquer gasto gera o alerta "orçamento zero".
- **Alertas:** acima do orçamento (absoluto) e desvio acima do limite (%). **A Vetor só alerta: não há corte automático de infraestrutura.**
- Realizado em outra moeda sem taxa fica fora da soma e aparece em "pendentes".

## AWS e Oracle (não implementado)
Para importar automaticamente, falta:
1. **Credencial de leitura** do faturamento, guardada só no servidor:
   - AWS: Cost Explorer, ou exportação CUR para S3, com política mínima.
   - Oracle: Usage/Cost Reports com política de leitura.
2. **Mapeamento de tags/compartimentos → cliente.** Sem tag ou fora do mapeamento, o custo é "não alocado".
3. **Contrato técnico documentado:**
   - frequência;
   - período fechado × parcial;
   - moeda;
   - chave de deduplicação (id da linha do relatório).

Até lá, exporte o relatório do provedor e importe pelo CSV acima. O `lote` + `id` evita duplicar.
