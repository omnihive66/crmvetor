# Telemetria de uso dos produtos (SPEC-08)

Contrato para um produto entregue a um cliente informar **uso real**. Sem esse envio, a adoção aparece como **"Sem dados"**. Nenhum produto real está enviando eventos hoje.

## Autorização
- O Administrador cria o produto na aba **Operação** do cliente, em "Adicionar produto com telemetria". O token `vtpr_…` aparece uma única vez; o banco guarda só o hash.
- O token identifica **o produto e o cliente**: `client_id` e `product_id` vêm dele, e um valor diferente no evento é recusado.
- O token só vale nesta rota e não autentica pessoa nenhuma. Revogar invalida na hora.

## Envio
```
POST /api/v1/vetor/uso/eventos
Authorization: Produto vtpr_...
Content-Type: application/json

{"eventos": [
  {"id": "evt-123", "tipo": "login",     "usuario": "<pseudônimo>", "ocorrido_em": "2026-10-23T09:00:00-03:00"},
  {"id": "evt-124", "tipo": "atividade", "usuario": "<pseudônimo>", "funcionalidade": "emitir_nota", "ocorrido_em": "..."},
  {"id": "evt-125", "tipo": "pulso", "ocorrido_em": "..."}
]}
```
- **Campos aceitos:** `id`, `tipo`, `funcionalidade`, `usuario`, `ocorrido_em`, `sintetico`, `client_id`, `product_id`. Qualquer outro campo recusa o lote (minimização): não envie conteúdo de documentos, mensagens nem credenciais.
- **`id`:** único por evento. Reenviar o mesmo `id` não duplica, e a resposta traz `recebidos` e `duplicados`.
- **`tipo`:**
  - `login`: entrar no produto. **Não conta como uso.**
  - `atividade`: uso efetivo de uma funcionalidade. Exige `funcionalidade`, um identificador curto como `emitir_nota`.
  - `pulso`: "estou enviando", sem pessoa. Serve para separar "ninguém usou" de "a telemetria parou".
- **`usuario`:** pseudônimo do produto, de 8 a 128 caracteres. E-mail é recusado. A Vetor cifra o pseudônimo de novo com uma chave do servidor, **por produto**, então ele não cruza produtos nem clientes e nunca é mostrado na tela.
- **`ocorrido_em`:** ISO 8601 com fuso. Futuro (mais de 5 min) e anterior à retenção são recusados.
- **Lote:** de 1 a 500 eventos. Se um evento tiver erro, nada do lote é gravado e a resposta diz qual evento e por quê.
- **`sintetico`:** marca dados de validação. Um produto criado como sintético marca todos os eventos dele, e a tela mostra **"Dados sintéticos de validação"**.

## Métricas (aba Operação do cliente)
| Indicador | Regra |
|---|---|
| Último acesso | último `login`, com a **origem** (qual produto) e **atualizado em** (último recebimento) |
| Usuários ativos | pseudônimos distintos com `atividade` na janela: N dias (padrão 30, por produto), contados de 00:00 de Brasília do primeiro dia até agora |
| Logins no período | contados à parte, para não inflar "ativos" |
| Funcionalidades | top 10 por uso na janela, com pessoas distintas |
| Alerta de desuso | desligado por padrão. Ligado com N dias:<ul><li>**Exceção** até uma data, com motivo (contrato/contexto): "em exceção".</li><li>Sem nenhum evento (nem `pulso`) há mais de 2 dias: **"telemetria parada"**, nunca desuso.</li><li>Telemetria viva e nenhuma `atividade` há N dias: "possível desuso".</li></ul> |

- **Sem nota única de saúde.** Relacionamento, disponibilidade (queda), infraestrutura (CPU, memória…) e adoção são blocos separados. Um índice composto só entra se a gestão pedir, com pesos, regras e dados ausentes explícitos.
- **Retenção:** eventos mais antigos que `VETOR_USO_RETENCAO_DIAS` (padrão 180) são apagados por uma tarefa diária.
- **Acesso:** os números agregados aparecem para quem vê o cliente. Criar e revogar tokens é do Administrador. Ajustar o alerta é de quem edita o cliente.
