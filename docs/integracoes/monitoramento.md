# Uptime Kuma e Beszel — configuração e regras (SPEC-07)

Formatos conferidos no código-fonte das versões **Uptime Kuma 2.5.7** e **Beszel v0.21.1**, as atuais em 23/10/2026. Nenhum dos dois assina webhooks. Por isso a Vetor exige o cabeçalho `X-Vetor-Token`, com um token por provedor guardado no servidor e comparado em tempo constante, e a URL deve ser HTTPS em produção.

## Contrato do evento
| Campo | Kuma | Beszel |
|---|---|---|
| provider | `kuma` | `beszel` |
| external_event_id | `<monitorID>:<heartbeat.time>:<status>`: reenvio do mesmo heartbeat não duplica | — (o Beszel não manda id): cada entrega é um evento; repetições se agrupam no incidente |
| resource_id | `monitor.id` | id do sistema, tirado do link `…/system/<id>` da mensagem |
| occurred_at | `heartbeat.time` (UTC) | horário do recebimento (o Beszel não manda horário) |
| received_at | recebimento | recebimento |
| status | `down`, `up`, `pendente`, `manutencao`; sem heartbeat (teste, certificado) = `info` | `down`/`up` ("Connection to X is …"); `alerta`/`normal` (limites, bateria invertida); outros alertas (containers, SMART…) = `info` |
| severity | down = crítica; pendente = aviso; demais = info | down = crítica; limite = aviso; demais = info |
| summary | `heartbeat.msg` | título |
| URL de origem | URL do monitor **sem usuário, senha e query string** | link do sistema no Beszel |

O **payload guardado** é só uma lista de campos permitidos:
- **Kuma:** id, nome, tipo, host, porta e URL limpa do monitor, mais status, horário, mensagem, ping e duração do heartbeat.
- **Beszel:** título e mensagem.

Depois de `VETOR_MONITOR_RETENCAO_DIAS` (padrão 90), o payload é apagado por uma tarefa diária, e a linha do tempo continua com os campos normalizados.

## Regras de incidente
- **Mapeamento explícito:**
  - Cada monitor ou servidor novo chega **em triagem**, sem projeto.
  - O Administrador escolhe o projeto em Monitoramento → Recursos monitorados.
  - Antes disso, o incidente existe mas não cria demanda nem avisa ninguém. Ao mapear, os incidentes abertos ganham a demanda e o aviso.
- **Deduplicação:**
  - Um incidente aberto por recurso e tipo (disponibilidade ou cada métrica de limite).
  - Alertas repetidos somam ocorrências e entram na linha do tempo.
- **Janela antirruído** (`VETOR_MONITOR_JANELA_MIN`, padrão 15): uma nova queda até N minutos depois da recuperação **reabre o mesmo incidente** (reincidência). Depois disso, abre um novo.
- **Fora de ordem:** cada incidente guarda o horário do evento mais novo aplicado.
  - Uma queda anterior à recuperação já registrada não reabre.
  - Uma recuperação anterior à última queda não fecha.
  - Os dois entram na linha do tempo na posição em que ocorreram.
- **Recuperação:** marca o incidente como recuperado e **não conclui a demanda**; quem acompanha decide.
- **Demanda:**
  - Criada no projeto do recurso: "[Incidente] <recurso> fora do ar" ou "<métrica> fora do limite".
  - Atribuída ao dono do projeto, com o link para a linha do tempo.
- **Aviso:**
  - E-mail ao dono do projeto na abertura, na reincidência e na recuperação.
  - No máximo 1 por incidente a cada `VETOR_MONITOR_AVISO_MIN` (padrão 30). Num pisca-pisca, só o primeiro sai; o resto fica na linha do tempo.

## Falhas e diagnóstico
- O webhook responde 202 assim que guarda o evento. O processamento é feito no worker, com até 5 tentativas (2, 4, 8 e 16 min). Depois disso, o evento fica em "Eventos com falha", com o botão Reprocessar.
- **Telemetria:**
  - Um conector aparece como **"Telemetria indisponível"** quando não está configurado, quando nunca recebeu nada ou quando tem uma falha mais nova que o último sucesso.
  - Nesse caso, os recursos dele também mostram "Telemetria indisponível". **Nunca "no ar" nem 100%.**
- Kuma e Beszel só avisam **mudanças**. Silêncio não é prova de que está tudo no ar, e a tela diz isso.
- **Disponibilidade histórica não é calculada.** Sem amostras contínuas não há dado suficiente; uma fórmula como (tempo total − tempo em incidente) ÷ tempo total só valeria com heartbeats periódicos. Decisão 0010.
- **CPU, memória, disco etc. não são indicadores de adoção do cliente.** São saúde de infraestrutura e não entram em pós-venda (SPEC-08).

## Configurar
**Servidor:** gere `openssl rand -hex 32` para `VETOR_KUMA_TOKEN` e para `VETOR_BESZEL_TOKEN` no `.env` e rode `./scripts/vetor.sh up`. Vazio deixa o conector desligado (503).

**Uptime Kuma 2.x:**
1. Em Settings → Notifications → Setup Notification, escolha **Webhook**.
2. Configure:
   - **Post URL:** `https://<seu-domínio>/api/v1/vetor/monitoramento/kuma/webhook`.
   - **Request Body:** "Preset - application/json".
   - **Additional Headers:** `{"X-Vetor-Token": "<VETOR_KUMA_TOKEN>"}`.
3. Ative a notificação nos monitores. Opcional: "Resend Notification if Down X times consecutively", que gera os alertas repetidos agrupados.

**Beszel (hub v0.21):**
1. Em Settings → Notifications → Webhook / Push notifications, adicione a URL:
   `generic://<seu-domínio>/api/v1/vetor/monitoramento/beszel/webhook?template=json&@X-Vetor-Token=<VETOR_BESZEL_TOKEN>`
   O `@` vira cabeçalho no Shoutrrr v0.22. Para HTTP sem TLS, só em teste local, acrescente `&disabletls=yes`.
2. O dono dessa configuração precisa ter o papel **admin** no Beszel. Para usuários comuns, o Beszel bloqueia destinos internos (`sendPublicNotification`), então a Vetor teria de ter URL pública.
3. Ative os alertas desejados no sistema: status (down/up) e limites.

**Rotação:** mova o token atual para `_ANTERIOR`, ponha o novo, rode `up`, troque nos provedores e esvazie `_ANTERIOR`.

Nada foi configurado em nenhum Kuma ou Beszel real. A QA usou entregas simuladas no formato exato das versões acima.
