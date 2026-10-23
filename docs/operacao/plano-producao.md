# Plano de publicação em produção (para revisão)

**Estado: NÃO EXECUTADO.** A publicação exige **autorização explícita** de vocês (specs 00 e 10), com este plano revisado e um backup verificado. Nada foi publicado e nenhum servidor, domínio ou credencial de produção foi usado.

## O que precisa estar decidido antes
| Item | Quem decide | Situação |
|---|---|---|
| Servidor/infraestrutura (Azure, outro provedor ou servidor próprio) | gestão | **pendente** (o serviço Azure não foi definido) |
| Domínio e certificado TLS | gestão / TI | pendente |
| SMTP para e-mails (convites, recuperação de senha, alertas) | TI | pendente |
| Login do **usuário matriz** do financeiro (`VETOR_FINANCEIRO_USUARIOS`) | gestão | pendente |
| Destino do backup fora do servidor e guarda da chave do backup | gestão / TI | pendente |
| RPO 24 h / RTO 2 h (propostos) | gestão | validar |
| Nome do sistema financeiro, provedor de MFA/SSO, antivírus para uploads, retenções | gestão | pendentes (RASTREABILIDADE) |
| Licença dos arquivos próprios da Vetor | gestão | pendente |
| Repositório público (`omnihive66/crmvetor`) | gestão | **confirmar**: com o repositório público, qualquer pessoa vê o código (nunca os segredos) |

## Requisitos do servidor (proposta inicial)
Linux com Docker 24 ou mais novo e Compose v2. Para começar: 4 vCPU, 8 GB de RAM e 60 GB de disco, **com disco cifrado**. A linha de base de desempenho foi medida em 4 vCPU e 15 GB, com p95 abaixo de 100 ms nas listas de 50 itens (`docs/entregas/evidencias/10/desempenho.txt`). A meta de 800 ms é proposta, não garantia. Portas externas: só 443 (e 80 redirecionando), no proxy TLS.

## Passo a passo (depois da autorização)
1. **Preparar:**
   - Clonar com submódulos na branch aprovada.
   - Rodar `./scripts/vetor.sh init-env`.
   - Preencher o `.env` de produção:
     - endereço: `TAIGA_SCHEME=https`, `TAIGA_DOMAIN`, `WEBSOCKETS_SCHEME=wss`, `COOKIES_SECURE=True`;
     - SMTP e `VETOR_FINANCEIRO_USUARIOS`;
     - `VETOR_BACKUP_CHAVE_ARQUIVO`, com a chave gerada e a cópia offline entregue ao responsável.
   - Conectores (GitHub, Kuma, Beszel): só se forem usados; vazio deixa desligado.
2. **Proxy TLS** (nginx, Caddy ou o balanceador do provedor) na frente do gateway (`VETOR_HTTP_PORT`), repassando `X-Forwarded-Proto` e WebSocket em `/events`.
3. **Subir:**
   - `./scripts/vetor.sh up`.
   - `./scripts/vetor.sh manage createsuperuser` para a conta técnica.
   - Criar as pessoas pela Administração, cada uma define a própria senha.
4. **Verificar antes de liberar:**
   - Login, HTTPS e cookies `Secure`.
   - Saúde operacional sem alertas, exceto os conectores que não forem usados.
   - Um backup e `./scripts/vetor.sh restaurar-teste <backup>` com resultado **ok**.
   - CI verde no commit publicado.
5. **Agendar:**
   - Backup diário (cron) e cópia para fora do servidor.
   - `restaurar-teste` mensal.
6. **Liberar** para as pessoas e acompanhar a Saúde operacional na primeira semana.

## Dados
A produção começa **vazia**. Os dados `[FICTÍCIO]` de desenvolvimento **não** vão para a produção, e nenhum dado ou segredo de produção vem para o desenvolvimento sem autorização.

## Rollback da publicação
- **Antes da liberação:** basta `./scripts/vetor.sh down`; não há dados reais ainda.
- **Depois da liberação:** voltar para a versão anterior com `./scripts/vetor.sh restore <backup de antes da atualização>`. Não há downgrade automático de esquema (manual de operação §5).
