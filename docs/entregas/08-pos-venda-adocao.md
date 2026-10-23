# Entrega 08 — Operação, pós-venda e adoção

Data: 23/10/2026 • Branch: `spec-08-pos-venda` (sobre `spec-07-monitoramento`)

## O que foi reaproveitado, configurado e desenvolvido
- **Reaproveitado:**
  - Reuniões e atas e o escopo de clientes (SPEC-03).
  - Demandas e bloqueios (SPEC-04).
  - Incidentes, recursos e estado dos conectores (SPEC-07).
  - Padrão de token mostrado uma vez e guardado como hash (SPEC-05).
- **Configurado:** `VETOR_USO_RETENCAO_DIAS` (180) e limpeza diária no beat.
- **Desenvolvido** (decisão 0011, `docs/integracoes/telemetria-uso.md`):
  - **Aba Operação no cliente**, com quatro blocos separados e sem nota única:
    - **Relacionamento:** última reunião com "abrir ata", **próximo contato** (campo novo, editável no Resumo) e pendências (abertas, bloqueadas, vencidas), mais os próximos passos da última ata.
    - **Disponibilidade:** monitores dos projetos do cliente, com a situação só de queda, quedas abertas e quedas em 30 dias.
    - **Infraestrutura:** alertas de limite com fonte e horário, com o aviso de que não indicam uso.
    - **Adoção:** último acesso com origem e atualização, usuários ativos na janela (Brasília), logins à parte, funcionalidades e alerta de desuso. Mostra o selo "Dados sintéticos de validação" quando for o caso.
  - **Ingestão de uso** (`POST /api/v1/vetor/uso/eventos`):
    - Token por produto e lista fechada de campos.
    - Pseudônimo cifrado de novo por produto; e-mail é recusado.
    - Deduplicação por `id` e lote recusado inteiro em caso de erro.
    - `login`, `atividade` e `pulso` separados.
  - **Produtos com telemetria:** o Administrador cria e revoga o token. Quem edita o cliente ajusta a janela e o alerta de desuso, com exceção por data e motivo.

## Arquivos

| Arquivo | Mudança |
|---|---|
| `vetor-back/vetor/models.py`, `migrations/0009_pos_venda.py` | `Cliente.proximo_contato`, `ProdutoTelemetria`, `EventoUso` |
| `vetor-back/vetor/operacao.py` | ingestão, métricas de adoção, alerta, retenção e painel |
| `vetor-back/vetor/api_operacao.py`, `api_clientes.py`, `urls.py` | produtos, rota de ingestão, `clientes/<id>/painel`, próximo contato |
| `vetor-back/vetor/tasks.py`, `ajustes.py` | limpeza diária e configuração |
| `vetor-back/vetor/tests/test_pos_venda.py` | 9 testes novos |
| `vetor-front/clientes/cliente.html` | aba Operação, próximo contato, produtos e alerta |
| `infra/docker-compose.override.yml`, `.env.example` | retenção |
| `scripts/qa/pos-venda.js` | QA pela tela, com eventos sintéticos |
| `docs/integracoes/telemetria-uso.md`, `docs/decisoes/0011-pos-venda-e-adocao.md`, `docs/arquitetura.md`, `docs/entregas/README.md` | contrato, decisão e atualizações |

**Migração:** `vetor.0009` acrescenta uma coluna opcional em `vetor_cliente` e cria duas tabelas. Nenhuma tabela do Taiga é alterada.

## Configuração necessária
Nenhuma para o painel. Para adoção, o produto do cliente precisa enviar eventos conforme `docs/integracoes/telemetria-uso.md`, com o token gerado na aba Operação. **Nenhum produto real envia eventos hoje:** a QA usou eventos sintéticos, identificados como tal.

## Critérios de aceite

| Critério | Resultado | Evidência |
|---|---|---|
| Última reunião abre a ata correspondente | **Atendido.** "abrir ata" leva à aba Reuniões, na reunião mais recente (`#reuniao-<id>`, elemento presente). | `test_relacionamento_…`, `qa.txt` (item 6) |
| Último acesso informa origem e atualização | **Atendido:** "23/10/2026, 03:45 · login no produto [FICTÍCIO] ERP Web", com "Atualizado em" separado. | `test_ultimo_acesso_…`, `adocao-1440.png` |
| Dados sintéticos identificados | **Atendido.** O produto marcado como sintético mostra o selo em todos os eventos. | `adocao-1440.png`, `test_ultimo_acesso_…` |
| Ausência de eventos não vira desuso nem falha | **Atendido.** Sem produto ou sem eventos: "Sem dados". Com alerta ligado, mas o produto parado: "telemetria parada". "Possível desuso" só aparece com o produto enviando `pulso` e sem atividade, e a exceção por contrato suspende o alerta. | `test_sem_eventos_…`, `test_alerta_de_desuso_…`, `qa.txt` (1ª rodada) |
| Painel diferencia queda, CPU alta e baixa adoção | **Atendido.** São blocos separados. Um servidor com CPU alta aparece em Infraestrutura e continua "no ar" em Disponibilidade, e a adoção tem bloco próprio. Não há nota única (verificado). | `test_painel_separa_…`, `operacao-1440.png`, `qa.txt` (item 5) |
| Visão por cliente não permite inferir outro cliente | **Atendido:** <ul><li>O painel de outro cliente dá 404 e nada do outro cliente aparece.</li><li>Quem vê o cliente mas não o projeto não vê os monitores do projeto.</li><li>Pseudônimos não saem da API e não cruzam produtos.</li><li>O token do produto não autentica em nenhuma outra rota.</li></ul> | `test_painel_separa_…`, `test_pseudonimo_nao_cruza_…`, `test_token_do_produto_…` |
| Instrumentação pseudonimizada, deduplicada e mínima; ingestão autenticada; retenção; acesso limitado | **Atendido:** <ul><li>Token inválido ou revogado dá 401.</li><li>Lote com campo de conteúdo (`mensagem`), e-mail, cliente trocado, sem fuso, futuro, tipo ou funcionalidade inválidos dá 400, e nada é gravado.</li><li>Reenvio não duplica.</li><li>Retenção de 180 dias.</li><li>Só o Administrador emite tokens.</li></ul> | `test_ingestao_…`, `test_retencao_…`, `qa.txt` (item 4) |
| Login separado de atividade; janela e fuso definidos | **Atendido.** Quem só fez login não conta como ativo. A janela (30 dias, ajustável) e o fuso aparecem junto do número. | `test_ultimo_acesso_…` |

### QA (`qa.txt`)
```
1. adoção sem produto → "Sem dados: nenhum produto deste cliente envia eventos de uso." (1ª rodada)
2. próximo contato pelo Resumo → 2026-11-05
3. produto sintético criado pela tela → token vtpr_… mostrado uma vez
4. ingestão → 200 {"recebidos": 5, "duplicados": 0} · evento com "mensagem" → 400
5. Relacionamento: última reunião · abrir ata · próximo contato 05/11/2026 · pendências
   Disponibilidade: monitores "no ar" (alerta de CPU não conta como queda)
   Infraestrutura: "web-…: cpu · acima do limite · Fonte: Beszel · último alerta …"
   Adoção: último acesso com origem · 2 ativos (30 dias, Brasília) · 2 logins · funcionalidades · "Dados sintéticos"
   nota única de saúde na tela? false
6. abrir ata → aba Reuniões, #reuniao-1 presente · 7. celular sem rolagem horizontal
```

### Testes automáticos
- `vetor/tests`: **112 passaram** (9 novos).
- Suíte oficial ampliada: **1015 passaram, 17 falharam**. As 17 são as mesmas divergências intencionais da SPEC-07, comparadas linha a linha, sem nenhuma falha nova (`evidencias/08/pytest.txt`).

## Problemas encontrados e corrigidos no caminho
- **Queda × CPU misturadas:** o bloco Disponibilidade mostrava "Fora do ar agora" para um servidor que só tinha CPU alta, porque reaproveitava a situação genérica da tela de Monitoramento. A QA pegou. Agora o bloco considera só quedas; teste com memória alta em outro servidor.
- **Formulário de alerta poluindo o cartão:** recolhido em "Ajustar alerta de desuso".
- **Data inexistente no próximo contato** (30/02): era aceita como erro interno; agora dá 400 com mensagem.
- **Dados de teste:** os produtos repetidos criados pelas rodadas de QA foram apagados do ambiente de desenvolvimento.

## Riscos e pendências
- **Produtos reais:** é preciso definir com cada produto o que é "atividade" e implementar o envio. Até lá, a adoção mostra "Sem dados".
- **Ver números de adoção:** os agregados aparecem para quem vê o cliente. Se a gestão quiser restringir mais (ex.: só gestores), é um ajuste de uma linha.
- **Métricas de infraestrutura contínuas** (séries de CPU/RAM) não são coletadas, só os alertas de limite do Beszel. A tela diz isso.
- **Índice de saúde composto:** não implementado, de propósito (spec). Precisa de pesos validados pela gestão.

## Reversão
Voltar a branch e rodar `./scripts/vetor.sh manage migrate vetor 0008`. Isso apaga produtos, eventos de uso e o próximo contato; o resto não muda.
