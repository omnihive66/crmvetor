# 0012 — Custos: estimativa versionada, realizado importado e acesso só com "ver custos"

- Data: 23/10/2026 • Estado: aceita

## Decisão
- **Dados:** tabelas próprias (estimativa, item, realizado, rateio, orçamento, taxa de câmbio), com `Decimal(20,6)`. Nunca float, nem na API: valores saem como texto.
- **Regras explícitas:**
  - Ajuste é linha percentual sobre a base do grupo, sem incidir sobre outro ajuste.
  - Conversão só com taxa registrada (par, data, origem).
  - Custo e preço, único e mensal, não se somam.
- **Versões:** cada versão é um registro; a anterior congela. Mais simples que histórico de campo, e responde "o que estava combinado na v2".
- **Realizado:**
  - Manual ou CSV na primeira entrega (spec). Deduplicação por lote + id; importação tudo ou nada.
  - Sem cliente = não alocado, até uma regra de rateio do mês.
- **Orçamento:**
  - Diferença absoluta e percentual. Orçamento zero não divide.
  - Alerta absoluto e percentual.
  - Parcial do mês sempre sinalizado.
  - Sem corte automático.
- **Acesso: fechado para o usuário matriz** (pedido da gestão, 23/10/2026):
  - Uma trava única na entrada de todas as rotas de custo (`initial`): só os logins de `VETOR_FINANCEIRO_USUARIOS` (servidor) leem e alteram. Os demais recebem 403, inclusive outros administradores.
  - A opção "Ver custos" por pessoa (SPEC-02) foi desativada: liberar o financeiro exige mudar o servidor, não um clique.
  - A auditoria registra campos e ids, nunca valores.
  - Aba e menu só aparecem com a permissão, e o servidor confere de novo.

## Alternativas descartadas
- **Calcular impostos em cascata ou automáticos:** a spec pede regra explícita. Linhas de ajuste deixam a regra visível.
- **Integrar AWS/Oracle agora:** sem credenciais nem contrato técnico. Fica o formato de importação e a lista do que falta.
