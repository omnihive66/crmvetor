# 0013 — Operação: saúde num painel, backup cifrado com restauração isolada, CI e publicação só com autorização

- Data: 23/10/2026 • Estado: aceita

## Decisão
- **Saúde operacional:** uma rota e uma tela do Administrador reúnem filas com falha, worker, e-mail, backup, restauração testada e o estado de cada conector. Uma tarefa horária manda e-mail com os alertas novos, no máximo um por problema por dia. Conector sem credencial é "não configurado", nunca "ativo".
- **correlation_id:**
  - O `request_id` do nginx vai como `X-Request-ID` ao back.
  - O back coloca o id em toda linha de log e o devolve na resposta.
  - Um id externo só é aceito se for seguro para log.
- **Retenção de logs:** rotação por container (5 × 10 MB). A retenção longa é de um coletor externo, a definir com a infraestrutura.
- **Backup:**
  - Banco, anexos e `.env` (o material de recuperação dos segredos), cifrados com AES-256 e chave fora do repositório.
  - Permissões 600/700 e somas SHA-256.
  - Registro no banco para o painel.
- **Restauração isolada:** `restaurar-teste` restaura num PostgreSQL descartável, numa rede interna sem acesso à instalação, e confere contagens, migrações e mídia. É a demonstração exigida antes da produção.
- **CI:**
  - Testes da Vetor contra o taiga-back oficial fixado.
  - Sintaxe de shell, JavaScript e Python, mais validação do compose.
  - Busca de segredos versionados.
  - Build das imagens derivadas.
  - Ações fixadas por commit.
- **Produção:** plano revisável (`docs/operacao/plano-producao.md`). Nada é publicado sem autorização explícita.

## Alternativas descartadas
- **Prometheus/Grafana agora:** é mais um serviço para operar. O painel e os e-mails cobrem os alertas pedidos, e a coleta externa entra com a infraestrutura definida.
- **Cifrar só o `.env`:** o dump contém dados pessoais e hashes. Cifrar tudo tem o mesmo custo.
