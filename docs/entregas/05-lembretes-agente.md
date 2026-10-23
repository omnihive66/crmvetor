# Entrega 05 — Minhas demandas, lembretes e agente

Data: 23/10/2026 • Spec: `specs/05-lembretes-agente.md` • Branch: `spec-05-lembretes` (sobre `spec-04-projetos`)

## O que foi reaproveitado, configurado e desenvolvido
- **Reaproveitado (nativo):**
  - Worker Celery do Taiga, que já roda com beat (`taiga-async -B`).
  - Envio de e-mail do Taiga.
  - Histórias do Taiga como destino da conversão (com histórico e snapshot).
  - Regras de escopo da SPEC-03 (`projetos_visiveis`, `clientes_visiveis`) para referências e para o agente.
- **Configurado:** entrada `vetor-lembretes` no beat (a cada 60 s), `VETOR_AGENTE_LIMITE_MINUTO` (padrão 30) e logger `vetor` (o Taiga descarta loggers não declarados).
- **Desenvolvido** (decisão 0008):
  - **Lembrete privado** (`vetor_lembrete`) com título, notas, vencimento opcional, recorrência diária/semanal/mensal, e-mail opcional, estado e referência opcional a cliente, projeto ou história.
  - **Aviso idempotente:** a tarefa reserva cada vencimento com um UPDATE condicional e o aviso aparece como número em **Minhas demandas** na barra lateral.
  - **Conversão em demanda:** prévia, confirmação explícita, transação com lock e repetição segura.
  - **Tokens pessoais do agente** (`vetor_tokenagente`, só o hash) e **rotas do agente**:
    - `/vetor/agente/lembretes` e `/vetor/agente/demandas`.
    - Escopos separados, `Idempotency-Key`, limite por minuto e 422 de esclarecimento.
    - Contrato em `docs/agente.md`.
  - **Tela Minhas demandas** (`/vetor/minhas-demandas/`):
    - "Tarefas compartilhadas comigo", separado de "Meus lembretes (privados)".
    - Criar, editar, concluir, reabrir, excluir e "Virar demanda" com prévia.
    - Criar e revogar tokens do agente.

## Arquivos

| Arquivo | Mudança |
|---|---|
| `vetor-back/vetor/models.py`, `migrations/0006_lembretes_agente.py` | `Lembrete`, `TokenAgente`, `RequisicaoAgente` |
| `vetor-back/vetor/lembretes.py` | referências por acesso atual, aviso, recorrência no fuso, prévia e conversão |
| `vetor-back/vetor/api_lembretes.py`, `urls.py` | API de lembretes e tokens; autenticação e rotas do agente |
| `vetor-back/vetor/tasks.py`, `management/commands/vetor_lembretes.py`, `ajustes.py` | tarefa do beat, comando manual, configuração e logger |
| `vetor-back/vetor/tests/test_lembretes.py` | 18 testes novos |
| `vetor-front/minhas-demandas/index.html`, `ui/shell.js`, `ui/shell.css`, `build.py` | tela, item com aviso na barra lateral |
| `scripts/qa/lembretes.js` | QA pela interface |
| `docs/agente.md`, `docs/decisoes/0008-lembretes-e-agente.md`, `docs/arquitetura.md`, `RASTREABILIDADE.md` | contrato, decisão, atualizações |

**Migração:** `vetor.0006` cria três tabelas próprias (`vetor_lembrete`, `vetor_tokenagente`, `vetor_requisicaoagente`). Nenhuma tabela do Taiga é alterada.

## Configuração necessária
Nenhuma para funcionar. Opcional:
- `VETOR_AGENTE_LIMITE_MINUTO` (padrão 30).
- E-mail do Taiga configurado no `.env`, para o aviso por e-mail. Sem ele, o aviso interno funciona e o e-mail vai para o console.

## Critérios de aceite

| Critério | Resultado | Evidência |
|---|---|---|
| B, incluindo gestor, não consulta lembrete de A por lista, ID, exportação, busca ou notificação | **Atendido.** Gestor, administrador e superusuário recebem lista vazia e 404 em detalhe, edição, exclusão e prévia. A busca não traz o lembrete, e a exportação do projeto referenciado não o contém. Não há entrada de histórico nem notificação do Taiga, e a auditoria registra só ids. O resumo de avisos é por dono. | `test_ninguem_alem_do_dono_…`, `test_exportacao_do_projeto_…`, `test_aviso_uma_vez_…`, `qa.txt` (item 3) |
| Converter exige ação clara e gera um único item mesmo após retry | **Atendido.** Sem `confirmar` dá 400 e nada é criado. A prévia mostra destino, quem verá, campos e o que não é copiado. A primeira chamada dá 201, a repetida dá 200 com a mesma demanda, e fica 1 demanda. O lembrete continua privado e concluído. | `test_converter_…`, `conversao-previa-1440.png`, `qa.txt` (item 4) |
| Notificação no fuso esperado | **Atendido.** Vencimento às 09:00 de Brasília: nada às 11:59 UTC, aviso às 12:00 UTC, sem repetir depois. O e-mail mostra "09:00 (horário de Brasília)". A recorrência mantém a hora local, e a mensal o dia (31/jan → 28/fev → 31/mar). Na tela, o prazo da conversão saiu como 22/10 (dia em Brasília) para um vencimento às 21:20, que já é 23/10 em UTC. | `test_aviso_…`, `test_recorrencia_…`, `test_recorrente_…`, `aviso-barra-1440.png`, `logs.txt` |
| Integração sem token global capaz de assumir qualquer pessoa | **Atendido.** O token é pessoal e o dono vem sempre do token: `dono`/`owner_id` no corpo dá 400. Escopos são separados (token de lembrete não cria demanda e vice-versa), e demanda exige `add_us` do titular. O token não vale em outras rotas (401), revogado dá 401, e ninguém revoga o token de outra pessoa (404). | `test_agente_cria_…`, `test_agente_escopos_…`, `test_token_do_agente_…`, `qa.txt` (item 5) |
| Pedido ambíguo pede esclarecimento sem inventar | **Atendido.** "acme" com dois clientes parecidos dá 422 com as opções; nome inexistente dá 422 `nao_encontrado`. Em nenhum dos casos algo é criado. | `test_agente_pede_esclarecimento_…` |
| Idempotência, limite e logs sem conteúdo | **Atendido.** A mesma chave devolve a mesma resposta sem duplicar, e sem chave dá 400. Acima do limite dá 429, mas a repetição de uma chave já usada ainda responde. O log tem prefixo, escopo, status e ids; o título enviado aparece 0 vezes nos logs. | `test_agente_idempotencia_…`, `test_agente_limite_…`, `logs.txt` |
| Revogar acesso remove previews e dados derivados do vínculo | **Atendido.** Sem acesso ao projeto, a referência some ("referência sem acesso") e o assunto da história não aparece mais. O título e as notas da própria pessoa ficam. Não é possível referenciar o que não se vê (400). | `test_referencia_some_…`, `test_nao_referencia_…` |
| "Minhas demandas" separa tarefas compartilhadas de lembretes privados | **Atendido.** São duas seções, com o aviso "só seus" e o cadeado. | `minhas-demandas-1440.png`, `minhas-demandas-390.png` |

### QA pela interface (`qa.txt`)
```
1. lembrete criado pela tela → Venceu 22/10/2026, 21:20
2. aviso do worker → 1 · barra lateral: 1 · depois de abrir a lista → sumiu
3. outra pessoa → lista: 0 · por ID: 404 · busca: nada
4. prévia → destino, "Visível para as 2 pessoa(s) do projeto…", campos, não copiados · confirmado → #9 · repetição → 200, 1 demanda
5. agente cria → 201 · mesma chave → mesmo lembrete · projeto inexistente → esclarecimento · token em /users/me → 401 · revogado → 401
6. celular (390 px) → sem rolagem horizontal da página
```

### Testes automáticos
- `vetor/tests`: **76 passaram** (18 novos). O teste de CSRF das rotas do agente falha sem `@csrf_exempt` e passa com ele (conferido).
- Suíte oficial ampliada (mais `test_notifications.py`): ver `evidencias/05/pytest.txt`.

## Problemas encontrados e corrigidos no caminho
- **Recorrente sem vencimento:** a validação deixava passar um lembrete recorrente criado sem data. Os testes pegaram; agora a regra considera também o valor já gravado (PATCH).
- **Logs da Vetor descartados no taiga-back:** o Taiga usa `disable_existing_loggers` e só declara os próprios loggers. O logger `vetor` foi declarado.
- **Erro de sintaxe na tela:** um parêntese a mais travava todo o script da página. A QA pegou; corrigido e conferido com `node --check`.

## Riscos e pendências
- **Agente real não conectado.** A tecnologia não foi informada, então foi entregue o contrato (`docs/agente.md`). Nada foi apresentado como integração ativa.
- **Limite por minuto:** conta só chamadas que criaram algo. Erros e esclarecimentos não entram na conta (limitação conhecida, comentada no código).
- **Aviso só na barra lateral e por e-mail.** O sino de notificações do Taiga não mostra lembretes; de propósito, porque o Taiga o propaga por eventos.
- **Excluir lembrete é definitivo** (sem lixeira).
- **Fuso fixo em -03:00 no formulário:** o Brasil não tem horário de verão desde 2019. Se voltar a ter, o campo da tela precisa calcular o deslocamento.
- **Celular:** a tabela de lembretes rola na horizontal dentro do cartão (a página não), e os botões de ação ficam à direita.

## Reversão
Voltar a branch e rodar `./scripts/vetor.sh manage migrate vetor 0005`. Isso apaga lembretes e tokens do agente; as demandas criadas por conversão ou pelo agente continuam no Taiga.
