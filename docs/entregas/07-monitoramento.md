# Entrega 07 — Uptime Kuma e Beszel

Data: 23/10/2026 • Branch: `spec-07-monitoramento` (sobre `spec-06-github`)

## O que foi reaproveitado, configurado e desenvolvido
- **Inspecionado antes de implementar:** o código-fonte do **Uptime Kuma 2.5.7** e do **Beszel v0.21.1** (versões atuais), e do Shoutrrr v0.22 que o Beszel usa.
  - **Kuma:** webhook JSON `{heartbeat, monitor, msg}`, horário em UTC, cabeçalhos extras; sem assinatura.
  - **Beszel:** `{title, message}` via Shoutrrr com `template=json`; sem id nem horário; cabeçalho pelo prefixo `@`; usuário não admin não pode enviar para endereço interno.

  Nada foi suposto: os testes usam esses formatos.
- **Reaproveitado:** worker e beat do Taiga, e-mail, demandas (histórias) e o padrão de fila de falhas da SPEC-06.
- **Configurado:** tokens por provedor (`VETOR_KUMA_TOKEN`, `VETOR_BESZEL_TOKEN`, com `_ANTERIOR` para rotação), janela antirruído (15 min), frequência de aviso (30 min) e retenção do conteúdo bruto (90 dias). Tokens vazios deixam o conector desligado.
- **Desenvolvido** (decisão 0010, `docs/integracoes/monitoramento.md`):
  - **Webhook por provedor** com `X-Vetor-Token`. O corpo é normalizado para o contrato da spec, com só os campos permitidos e URLs sem credenciais. Reenvio do mesmo heartbeat do Kuma não duplica.
  - **Incidentes:**
    - Um aberto por recurso e tipo; alertas repetidos são agrupados.
    - Reincidência dentro da janela reabre o mesmo incidente.
    - Evento fora de ordem não reverte o estado.
    - A recuperação não conclui a demanda.
  - **Triagem:** recurso novo chega sem projeto e não ganha demanda nem aviso. O Administrador mapeia o projeto; aí os incidentes abertos ganham a demanda e o aviso.
  - **Aviso por e-mail** ao dono do projeto: no máximo 1 por incidente a cada 30 min.
  - **Processamento no worker** com 5 tentativas, fila de falhas e reprocessamento.
  - **Diagnóstico por conector:** configurado, telemetria recebida ou indisponível, último sucesso, última falha, recebidos em 24 h, falhas pendentes, recursos em triagem e incidentes abertos.
  - **Tela Monitoramento** (item na barra lateral):
    - Incidentes dos projetos da pessoa, com linha do tempo.
    - Para o Administrador: conectores, recursos com mapeamento e eventos com falha.

## Arquivos

| Arquivo | Mudança |
|---|---|
| `vetor-back/vetor/models.py`, `migrations/0008_monitoramento.py` | `RecursoMonitorado`, `Incidente`, `EventoMonitoramento` |
| `vetor-back/vetor/monitoramento.py` | webhook, normalização Kuma/Beszel, regras de incidente, demanda, aviso, mapeamento e retenção |
| `vetor-back/vetor/api_monitoramento.py`, `urls.py` | incidentes, recursos, eventos, diagnóstico e reprocessar |
| `vetor-back/vetor/tasks.py`, `ajustes.py` | tarefa com novas tentativas, limpeza diária e configuração |
| `vetor-back/vetor/tests/test_monitoramento.py` | 12 testes novos |
| `vetor-front/monitoramento/index.html`, `ui/shell.js`, `build.py` | tela e item na barra lateral |
| `infra/docker-compose.override.yml`, `.env.example` | variáveis |
| `scripts/qa/monitoramento.js` | QA com entregas no formato real e worker real |
| `docs/integracoes/monitoramento.md`, `docs/decisoes/0010-monitoramento.md`, `docs/arquitetura.md`, `docs/entregas/README.md` | contrato, regras, configuração e decisão |

**Migração:** `vetor.0008` cria três tabelas próprias. Nenhuma tabela do Taiga é alterada.

## Configuração necessária
Para ativar:
1. Gere os tokens e ponha no `.env`.
2. Configure a notificação no Kuma (Webhook com cabeçalho) e no Beszel (URL `generic://…?template=json&@X-Vetor-Token=…`, com dono admin no Beszel), conforme `docs/integracoes/monitoramento.md`.
3. Mapeie os recursos na tela.

Os provedores precisam alcançar a Vetor por HTTPS, o que depende da publicação autorizada (SPEC-10). **Nenhum Kuma ou Beszel real foi configurado.**

## Critérios de aceite

| Critério | Resultado | Evidência |
|---|---|---|
| Queda → alertas repetidos → recuperação = um incidente com linha do tempo | **Atendido.** 3 quedas e a recuperação viram 1 incidente (3 alertas, recuperado) com a linha do tempo down, down, down, up. A demanda "[Incidente] … fora do ar" continua aberta. | `test_queda_alertas_repetidos_…`, `linha-do-tempo-1440.png`, `qa.txt` (item 2) |
| Eventos fora de ordem não revertem o estado | **Atendido.** Uma queda das 09:15 chegando depois da recuperação das 09:20 entra na linha do tempo e o incidente continua recuperado. Uma recuperação antiga também não fecha um incidente novo. | `test_eventos_fora_de_ordem_…`, `qa.txt` |
| Recurso desconhecido entra em triagem | **Atendido.** Fica sem projeto e sem demanda nem e-mail, e só o Administrador vê. Ao mapear pela tela, o incidente aberto ganha a demanda e o aviso. | `test_recurso_desconhecido_…`, `test_notificacao_…`, `qa.txt` (itens 1 e 3) |
| Falha do conector = telemetria indisponível, nunca 100% | **Atendido.** Sem nenhuma entrega, ou com falha mais nova que o último sucesso, o conector e os recursos dele mostram "Telemetria indisponível". Não há porcentagem na tela (verificado). | `test_falha_fica_na_fila_…`, `painel-1440.png`, `qa.txt` (itens 0 e 4) |
| Disponibilidade histórica só com dados suficientes e fórmula explícita | **Atendido: não calculada.** Os provedores só avisam mudanças, e a tela e a API dizem isso. A fórmula e a fonte necessária estão na decisão 0010. | decisão 0010 |
| CPU/RAM não são indicadores de adoção | **Atendido:** documentado. Métricas de limite só geram incidente de infraestrutura. | `docs/integracoes/monitoramento.md` |
| Deduplicação, agrupamento e janela antirruído configurável | **Atendido.** Reenvio do mesmo heartbeat responde `duplicado`. Repetidos se somam no incidente. Reincidência em até 15 min reabre o mesmo; depois disso, abre outro. | `test_reenvio_…`, `test_reincidencia_…` |
| Recovery atualiza o incidente e não conclui tarefa | **Atendido** | `test_queda_…`, `qa.txt` ("demanda continua aberta → true") |
| Responsável notificado com controle de frequência | **Atendido.** O dono do projeto recebe e-mail na abertura (ou ao sair da triagem); um pisca-pisca dentro de 30 min não gera outro. | `test_notificacao_…`, `qa.txt` (e-mails) |
| Retry com limite, fila de falhas, métricas e painel | **Atendido.** 5 tentativas no worker, depois "Eventos com falha" com Reprocessar a partir do conteúdo guardado. Diagnóstico por conector. | `test_falha_fica_na_fila_…`, `painel-1440.png` |
| Sem assinatura nativa: mecanismo compatível, segredo no servidor, fora dos logs | **Atendido.** Sem token, com token errado ou com o token do outro provedor dá 401. Conector não configurado dá 503. Os tokens aparecem 0 vezes nos logs. | `test_sem_token_…`, `test_payload_sem_credenciais_…`, `logs.txt` |
| Payload sem dados sensíveis e com retenção definida | **Atendido.** A URL `https://usuario:segredo@…?chave=abc` ficou guardada como `https://api.ficticio.example/saude`. Depois de 90 dias o payload é apagado e o evento normalizado fica. | `test_payload_sem_credenciais_…`, `qa.txt` |

### QA (`qa.txt`)
```
0. conectores sem nenhuma entrega → Telemetria indisponível | Telemetria indisponível · sem token → 401
1. queda de monitor desconhecido → 202 · em triagem (projeto: null) · mapeado pela tela → Salvo.
2. 1 incidente · recuperado · 3 alertas · demanda "[Incidente] … fora do ar"
   linha do tempo → 09:00 down, 09:05 down, 09:10 down, 09:15 down (atrasado), 09:20 up · demanda continua aberta
3. Beszel → 3 eventos · recurso em triagem · disponibilidade: recuperado, limite:cpu: aberto · nenhuma demanda (triagem)
4. conectores → Telemetria recebida · nenhuma porcentagem na tela · celular sem rolagem horizontal
e-mails: 1 "Incidente aberto" ao mapear; a recuperação, dentro de 30 min, ficou retida pelo controle de frequência
```

### Testes automáticos
- `vetor/tests`: **103 passaram** (12 novos).
- Suíte oficial ampliada: **1006 passaram, 17 falharam**. As 17 são as mesmas divergências intencionais da SPEC-06, comparadas linha a linha, sem nenhuma falha nova (`evidencias/07/pytest.txt`).

## Problemas encontrados e corrigidos no caminho
- **Limite do Beszel com nome de servidor com espaço:** a métrica saía errada ("web-249341 cpu"). A QA pegou. Agora a métrica é tirada da lista fixa de métricas do Beszel; teste com nomes compostos e "15m load".
- **Aviso perdido na triagem:** um incidente aberto em triagem não avisava ninguém ao ser mapeado. A QA pegou; agora o mapeamento avisa.
- **Trava no banco:** o `select_for_update` com relação opcional falhava no PostgreSQL. Agora trava só o evento.
- **Corpo qualquer aceito como teste do Kuma:** agora é recusado (400).

## Riscos e pendências
- **Beszel sem horário:** a linha do tempo dele usa o recebimento. Atraso de entrega muda a hora registrada.
- **Kuma "pendente" e "manutenção"** ficam só na linha do tempo e não abrem nem fecham incidente.
- **Mapeamento na tela:** a lista de projetos mostra os que o Administrador enxerga. A API aceita qualquer projeto.
- **Controle de frequência:** é um intervalo por incidente para todos os avisos. Uma recuperação logo depois da abertura não gera e-mail; aparece na tela.
- **Dados de teste:** os dados de teste da primeira rodada (incidente com a métrica errada) foram apagados do ambiente de desenvolvimento.

## Reversão
Voltar a branch e rodar `./scripts/vetor.sh manage migrate vetor 0007`. Isso apaga recursos, incidentes e eventos; as demandas criadas continuam. Esvazie os tokens para recusar entregas (503).
