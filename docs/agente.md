# Contrato do agente externo (SPEC-05)

A tecnologia do agente da Vetor ainda não foi informada. Este é o contrato que a Vetor Sistemas oferece: qualquer agente (assistente de chat, automação, script) que fale HTTP pode usá-lo. **Nenhuma integração com um agente específico está ativa.**

## Autorização
- Cada pessoa cria os próprios tokens em **Minhas demandas → Agente externo**. O token aparece uma única vez; o banco guarda só o hash (SHA-256) e um prefixo para identificação.
- O token **age só como o dono**: o dono nunca vem da requisição. Não existe token global nem troca de identidade.
- Escopos separados:
  - `lembretes`: criar lembrete privado do dono.
  - `demandas`: criar demanda num projeto. Vale só onde o dono pode criar histórias (`add_us`), e o resultado é visível para o projeto.
- O token só é aceito nas rotas `/api/v1/vetor/agente/...`. Em qualquer outra rota da API ele é ignorado (401). A sessão normal do navegador também não serve nessas rotas.
- Revogar na mesma tela invalida o token na hora. Conta desativada também invalida.

## Requisição
```
POST /api/v1/vetor/agente/lembretes      (escopo lembretes)
POST /api/v1/vetor/agente/demandas       (escopo demandas)
Authorization: Agente vtag_...
Idempotency-Key: <até 100 caracteres, único por pedido>
Content-Type: application/json
```

**Lembrete:**
```json
{"titulo": "Ligar para a ACME", "notas": "opcional", "vencimento": "2026-11-10T09:00:00-03:00",
 "recorrencia": "" | "diaria" | "semanal" | "mensal", "avisar_email": false,
 "cliente": 12 | "ACME", "projeto": 7 | "Portal"}
```

**Demanda:**
```json
{"projeto": 7 | "Portal", "assunto": "Corrigir boleto", "descricao": "opcional"}
```

- `cliente` e `projeto` aceitam id ou nome. O nome é procurado só no que o dono do token pode ver: primeiro igual (sem diferenciar maiúsculas), depois "contém".
- `vencimento` exige fuso (ISO 8601). Os avisos usam o horário de Brasília.
- Enviar `dono` ou `owner_id` dá 400.

## Respostas
| Status | Quando | Corpo |
|---|---|---|
| 201 | criado | `{"id", "tipo": "lembrete", "privado": true}` ou `{"id", "ref", "projeto", "tipo": "demanda", "privado": false}` |
| 201 (repetido) | mesma `Idempotency-Key` do mesmo token | a mesma resposta da primeira vez; nada novo é criado |
| 422 | pedido ambíguo ou referência inexistente | `{"esclarecimento": {"campo", "motivo": "ambiguo" \| "nao_encontrado" \| "obrigatorio", "valor", "opcoes": [{"id", "nome"}]}}`. Nada é criado; pergunte à pessoa e reenvie com o id. |
| 400 | campo inválido, sem `Idempotency-Key`, tentativa de definir o dono | mensagens por campo |
| 401 | token ausente, inválido, revogado ou de conta inativa | |
| 403 | token sem o escopo, ou dono sem permissão no projeto | |
| 429 | mais de `VETOR_AGENTE_LIMITE_MINUTO` (padrão 30) criações por minuto por token | cabeçalho `X-Throttle-Wait-Seconds: 60` (padrão do Taiga) |

## Logs
O log `vetor.agente` registra prefixo do token, escopo e status. Título, notas e assunto nunca entram no log.
