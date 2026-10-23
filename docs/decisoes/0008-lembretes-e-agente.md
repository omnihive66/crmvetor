# 0008 — Lembretes privados e agente externo

- Data: 23/10/2026 • Estado: aceita (o contrato do agente vale até a tecnologia real ser informada)

## Lembretes
- **Tabela própria** (`vetor_lembrete`), fora do Taiga. Assim, lembretes não entram no histórico, nas notificações, nos eventos em tempo real, na busca nem na exportação de projeto. Toda leitura parte de `dono = usuário da requisição`, sem exceção para administrador ou superusuário. Outra pessoa recebe 404, como se o lembrete não existisse.
- **Referências** a cliente, projeto ou história guardam só o id. O nome e o assunto são lidos na hora e só aparecem se o dono ainda tiver acesso. Ao perder o acesso, a referência some da tela ("referência sem acesso"), e o texto que a própria pessoa escreveu fica.
- **Aviso:**
  - Uma tarefa Celery (beat no `taiga-async`, a cada 60 s) marca os lembretes vencidos.
  - A reserva é um `UPDATE ... WHERE notificado_em IS NULL`, então dois workers ou duas rodadas não avisam duas vezes.
  - O canal inicial é o número na barra lateral ("Minhas demandas"), que some quando a pessoa abre a lista. O e-mail é opcional por lembrete.
  - Reagendar zera o aviso.
- **Fuso:** guardado em UTC. Exibição, e-mail, prazo da conversão e recorrência usam America/Sao_Paulo. A recorrência mantém a hora local, e a mensal mantém o dia (31/jan → 28/fev → 31/mar).
- **Conversão:**
  - A prévia mostra destino, quem verá, os campos copiados e o que não é copiado. As notas são copiadas só se a pessoa marcar.
  - Criar exige `confirmar: true`.
  - Roda numa transação com lock no lembrete. A segunda chamada devolve a mesma demanda (200), sem criar outra.
  - O lembrete fica concluído e privado, com o vínculo.
  - A auditoria registra só os ids.

## Agente
A tecnologia do agente existente não foi informada. Em vez de supor uma, a Vetor expõe um contrato HTTP genérico (`docs/agente.md`):
- tokens pessoais com escopos `lembretes` e `demandas`, guardados como hash;
- o dono vem sempre do token;
- chave de idempotência obrigatória, limite por minuto e 422 com pedido de esclarecimento em vez de adivinhar.

Quando a tecnologia for conhecida, a integração é um cliente desse contrato. Se ela exigir OAuth ou webhook de entrada, isso será uma decisão nova.

## Alternativas descartadas
- **Usar história do Taiga marcada como privada:** os mecanismos do Taiga (projeto, membros, admins, eventos, exportação) a exporiam.
- **Token de aplicação do Taiga (`external-apps`):** dá acesso à API inteira como o usuário, sem escopo.
