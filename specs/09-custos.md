# SPEC-09 — Estimativas e custos realizados

## Resultado
Comparar orçamento de infraestrutura/consumo com realizado por cliente, mantendo o sistema financeiro externo como fonte contratual.

## Implementação
Calculadora inicial manual: categorias, quantidades, unidades, preço unitário, moeda, validade e fonte. Separar custos fixos, variáveis, custos únicos e recorrentes; distinguir custo de preço de venda. Registrar versões da estimativa e premissas. Fórmula base de item variável: quantidade × preço unitário; impostos, descontos e conversão entram como linhas ou regras explícitas, sem dupla contagem.

Realizado manual/importado na primeira entrega; AWS/Oracle somente após credenciais e contrato técnico documentado. Armazenar decimais adequados a preços fracionários, moeda e período. Mostrar conversão apenas com taxa, data e origem registradas. Não apresentar consumo parcial do mês como fatura final.

Rateio de recursos compartilhados precisa de regra explícita por período; despesas sem tag/mapeamento ficam como não alocadas. Alertas por orçamento absoluto e desvio percentual com regra para orçamento zero. Não prometer corte automático de infraestrutura.

## Aceite
Exemplo de 100 unidades × R$ 0,20 + R$ 50 fixos resulta em R$ 70 antes de ajustes. Orçamento R$ 100 e realizado R$ 120 mostra +R$ 20 e +20%. Orçamento zero não divide por zero. Mesma importação não duplica custos. Ajuste e remoção são auditados. Somente usuários com permissão financeira consultam valores, inclusive por API/exportação.
