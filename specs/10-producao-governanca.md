# SPEC-10 — Qualidade, operação e produção

## Resultado
Entrega mantível, observável e recuperável, com evidências proporcionais aos riscos.

## Implementação
Ambientes separados, configuração por variáveis, migrations revisadas, armazenamento privado, HTTPS, cookies seguros e proteção CSRF conforme arquitetura. Sanitizar conteúdo rico, validar uploads e proteger integrações contra SSRF quando houver URLs configuráveis. Criptografar segredos em repouso com gestão de chaves definida; nunca versionar credenciais. Dependências e imagens fixadas e inventariadas.

Auditoria de mudanças relevantes: ator, ação, alvo, horário e resultado, sem senha, token ou conteúdo de lembrete privado. Logs operacionais com correlation_id e retenção definida. Alertas para falhas de filas, webhooks, envio e backup. Exportação respeita permissão e minimização.

Backup deve cobrir banco, anexos, configuração e material de recuperação de segredos. Definir RPO/RTO e demonstrar restauração isolada antes da produção. Rollback precisa prever compatibilidade de esquema e dados; não prometer downgrade destrutivo automático.

## Verificação
Testes de autorização, privacidade, webhook, deduplicação, concorrência, cálculos e migrações. Fluxo ponta a ponta: cliente → projeto → tarefa → colaboração → código → incidente → resolução. QA visual e acessibilidade conforme DESIGN.md. Baseline de desempenho com volume acordado; proposta inicial: lista de 50 itens com p95 de API inferior a 800 ms no ambiente de referência, excluindo chamadas externas. Registrar hardware, dataset e resultados; meta é proposta, não garantia.

## Aceite
CI relevante passa, licenças/avisos preservados, manual do usuário e operação entregues, restauração demonstrada, riscos/pendências documentados. Conectores sem credenciais ficam claramente não configurados. Deploy de produção somente após autorização explícita, com plano revisável e backup verificado.
