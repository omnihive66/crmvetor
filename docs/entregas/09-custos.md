# Entrega 09 — Estimativas e custos realizados

Data: 23/10/2026 • Spec: `specs/09-custos.md` • Branch: `spec-09-custos` (sobre `spec-08-pos-venda`)

## O que foi reaproveitado, configurado e desenvolvido
- **Reaproveitado:**
  - Permissão "Ver custos" do perfil (SPEC-02).
  - Escopo de clientes (SPEC-03).
  - Auditoria e o padrão de importação tudo ou nada com deduplicação (SPEC-06/07).
- **Configurado:** nada novo.
- **Desenvolvido** (decisão 0012, `docs/integracoes/custos.md`):
  - **Calculadora por estimativa versionada.** Cada versão guarda moeda, validade, fonte e premissas, e a versão anterior fica congelada.
    - **Itens:** custo ou preço de venda; fixo, variável ou ajuste em % sobre a base do grupo; único ou mensal.
    - **Cálculo:** quantidade × preço unitário, com decimais de 6 casas.
    - **Totais:** por grupo, com fixo, variável, antes de ajustes, ajustes e total.
  - **Taxas de câmbio** com par, data e origem. Item ou realizado em outra moeda só entra com taxa; sem ela, fica fora do total com o motivo.
  - **Realizado:**
    - Lançado à mão ou importado por CSV. O lote + id evita duplicar, e um erro recusa o arquivo inteiro.
    - A marca "parcial" identifica o consumo do mês em curso.
    - Custo sem cliente é **não alocado** até existir uma **regra de rateio** do mês, com partes que somam 100%.
  - **Orçamento × realizado** por cliente e mês:
    - Diferença em R$ e em %.
    - Orçamento zero sem divisão.
    - Alertas absoluto e de desvio percentual.
    - Aviso de parcial; sem corte automático.
  - **Telas:**
    - Aba **Custos** no cliente: estimativas e orçamento × realizado.
    - Página **Custos**: importação, não alocados, rateio, taxas e exportação CSV.
    - Item na barra lateral.
    - Tudo só para quem tem "Ver custos".

## Arquivos

| Arquivo | Mudança |
|---|---|
| `vetor-back/vetor/models.py`, `migrations/0010_custos.py` | `TaxaCambio`, `Estimativa`, `ItemEstimativa`, `CustoRealizado`, `RegraRateio`, `Orcamento` |
| `vetor-back/vetor/custos.py` | cálculo, conversão, realizado com rateio, comparação, leitura de CSV |
| `vetor-back/vetor/api_custos.py`, `urls.py` | rotas `/vetor/custos/*` com a trava `ver_custos` única |
| `vetor-back/vetor/tests/test_custos.py` | 11 testes novos |
| `vetor-front/clientes/cliente.html`, `vetor-front/custos/index.html`, `ui/shell.js`, `build.py` | aba Custos, página Custos, menu |
| `scripts/qa/custos.js` | QA pela tela |
| `docs/integracoes/custos.md`, `docs/decisoes/0012-custos.md`, `docs/arquitetura.md`, `RASTREABILIDADE.md` | regras, CSV, AWS/Oracle e decisão |

**Migração:** `vetor.0010` cria seis tabelas próprias. Nenhuma tabela do Taiga é alterada.

## Configuração necessária
O financeiro fica **fechado para o usuário matriz**. Informe o login dele em `VETOR_FINANCEIRO_USUARIOS` no `.env` do servidor e rode `./scripts/vetor.sh up`. Vazio deixa fechado para todos.
- No ambiente de desenvolvimento, o matriz é `admin.dev`.
- A antiga opção "Ver custos" da Administração foi removida da tela e não libera mais nada.

## Critérios de aceite

| Critério | Resultado | Evidência |
|---|---|---|
| 100 × R$ 0,20 + R$ 50 fixos = R$ 70 antes de ajustes | **Atendido.** Na tela: Fixo R$ 50,00 · Variável R$ 20,00 · Antes de ajustes **R$ 70,00**. Um ajuste de 10% dá R$ 7,00 (total R$ 77,00). No teste, +10% e −5% juntos dão R$ 3,50, ou seja, ajuste não incide sobre ajuste. | `test_100_unidades_…`, `estimativa-1440.png`, `qa.txt` (item 1) |
| Orçamento 100 e realizado 120 mostram +R$ 20 e +20% | **Atendido:** "Diferença +R$ 20,00 · +20,00%", com os alertas "acima do orçamento" e "desvio de 20,00% (limite 10,00%)". | `test_orcamento_100_…`, `orcamento-realizado-1440.png`, `qa.txt` (item 2) |
| Orçamento zero não divide por zero | **Atendido.** O percentual "não se aplica", e com gasto aparece o alerta "orçamento zero". | `test_orcamento_zero_…` |
| Mesma importação não duplica | **Atendido.** A segunda importação do mesmo lote dá "0 importado(s), 2 já existia(m)". Um arquivo com uma linha inválida não grava nada. | `test_mesma_importacao_…`, `qa.txt` (item 3) |
| Ajuste e remoção são auditados | **Atendido.** Alteração e remoção de item e de realizado ficam na auditoria **sem os valores** (verificado). | `test_ajuste_e_remocao_…` |
| Só quem tem permissão financeira consulta, inclusive por API/exportação, **fechado para o usuário matriz** | **Atendido:** <ul><li>Administrador ou gestor que não é o matriz recebe 403 em todas as rotas (8 verificadas, inclusive a exportação), mesmo com a antiga "Ver custos" ligada. Sem sessão, 401.</li><li>Com a lista vazia, nem o matriz anterior entra.</li><li>Tentar liberar pela API dá 400.</li><li>Na tela, sem aba nem menu.</li><li>Valores não aparecem no cliente, no painel nem na busca.</li><li>O matriz não vê cliente fora do seu escopo.</li></ul>A trava foi desligada de propósito e o teste falhou. | `test_so_quem_tem_permissao_…`, `qa.txt` (item 5) |
| Decimais, moeda e período; conversão só com taxa, data e origem | **Atendido.** R$ 0,000125 preservado. USD sem taxa fica pendente; com a taxa PTAX registrada, a conversão mostra taxa, data e origem. | `test_conversao_…`, `test_mesma_importacao_…` |
| Custo ≠ preço; fixo, variável, único e recorrente separados | **Atendido** | `test_custo_e_preco_…` |
| Versões e premissas | **Atendido.** A v1 fica congelada (edição dá 400) e a v2 copia os itens. | `test_versoes_…` |
| Rateio por regra explícita do período; sem mapeamento = não alocado | **Atendido.** Partes que não somam 100 dão 400. Com regra 60/40, o cliente recebe 60% e a linha diz "rateio 60% de cluster". A regra vale só para o mês dela. | `test_rateio_…`, `qa.txt` (item 3) |
| Consumo parcial não é fatura final | **Atendido:** "Inclui consumo parcial do mês: não é fatura final." | `test_consumo_parcial_…`, `qa.txt` |
| Sem corte automático | **Atendido:** só alertas (`corte_automatico: false`), dito na tela. | — |

### QA (`qa.txt`)
```
1. totais (Custo mensal) → Fixo R$ 50,00 · Variável R$ 20,00 · Antes de ajustes R$ 70,00 · Ajustes R$ 7,00 · Total R$ 77,00
2. comparação → Orçamento R$ 100,00 · Realizado R$ 120,00 · Diferença +R$ 20,00 · +20,00% · alertas absoluto e percentual
3. importação 1 → 2 importados, 1 não alocado · importação 2 → 0 importados, 2 já existiam
   não alocados → cluster R$ 300,00 (parcial) · rateio 100% → nada não alocado · "não é fatura final"
4. exportação → custos-2026-10.csv
0. liberar o financeiro pela API → 400
5. observador.dev (não é o matriz, "ver custos" antigo ligado) → sem aba, sem menu, API 403, exportação 403
```

### Testes automáticos
- `vetor/tests`: **123 passaram** (11 novos; o de permissão cobre a regra do usuário matriz).
- Suíte oficial ampliada: **1026 passaram, 17 falharam**. As 17 são as mesmas divergências intencionais da SPEC-08, sem nenhuma falha nova (`evidencias/09/pytest.txt`).

## Problemas encontrados e corrigidos no caminho
- **"null" escrito na tela:** `replaceChildren` escreve `null` como texto (o `el()` descarta, mas o `replaceChildren` não). Apareceu na aba Custos e existia desde a SPEC-03 na aba Resumo do cliente, quando não havia observações. Corrigido nos quatro pontos.
- **Preço fracionário arredondado na tela:** R$ 0,000125 apareceria como R$ 0,00. Agora o preço unitário mostra até 6 casas, e quantidades e percentuais aparecem sem zeros à direita.
- **Alertas com ponto decimal** ("20.00 BRL"): agora no formato brasileiro.
- **Docker:** o daemon caiu ao retomar a sessão e foi religado. Os volumes e as imagens ficaram intactos.

## Riscos e pendências
- **AWS e Oracle:** dependem de credencial de leitura, do mapeamento tag → cliente e de um contrato técnico (`docs/integracoes/custos.md`). Até lá, importação por CSV.
- **Nome do sistema financeiro:** ainda não informado.
- **Orçamento:** é digitado à mão (pode citar a estimativa em "origem"). Não é gerado sozinho a partir da estimativa.
- **Taxas:** a taxa vale como registrada. Não há cotação automática (PTAX); quem registra informa a origem.

## Reversão
Voltar a branch e rodar `./scripts/vetor.sh manage migrate vetor 0009`. Isso apaga estimativas, realizados, rateios, orçamentos e taxas. O sistema financeiro externo não é afetado.
