"""Ajustes de settings da Vetor, aplicados por settings/config.py (produção) e vetor/tests/settings.py."""
import os


def aplicar(s):
    s["INSTALLED_APPS"] = ["vetor"] + s["INSTALLED_APPS"]  # primeiro: templates e estáticos da Vetor vencem
    s["ROOT_URLCONF"] = "vetor.urls"
    s["LOCALE_PATHS"] = (os.path.join(s["BASE_DIR"], "vetor", "locale"),) + tuple(s["LOCALE_PATHS"])
    s["MIDDLEWARE"] = ["vetor.correlacao.CorrelacaoMiddleware", "vetor.ator.LimparAtorMiddleware"] + s["MIDDLEWARE"]
    # Mesmas classes do Taiga, mas registrando quem agiu (auditoria).
    s["REST_FRAMEWORK"]["DEFAULT_AUTHENTICATION_CLASSES"] = (
        "vetor.ator.JWTAuthentication", "vetor.ator.Session", "vetor.ator.Token")
    s["VETOR_PAPEL_SEM_PERFIL"] = "observador"  # conta sem perfil: só leitura até o administrador definir
    s["FEEDBACK_ENABLED"] = False
    # Documentos de cliente (SPEC-03). Sem antivírus na infraestrutura atual: só tipos de documento comuns.
    s["VETOR_DOCUMENTO_MAX_MB"] = int(os.getenv("VETOR_DOCUMENTO_MAX_MB", "25"))
    s["VETOR_DOCUMENTO_EXTENSOES"] = ["pdf", "doc", "docx", "odt", "xls", "xlsx", "ods", "csv", "ppt", "pptx", "odp",
                                      "txt", "md", "png", "jpg", "jpeg", "zip"]
    # Lembretes (SPEC-05): o worker do Taiga roda com beat (-B); a Vetor só acrescenta esta entrada.
    s["CELERY_BEAT_SCHEDULE"] = {**s.get("CELERY_BEAT_SCHEDULE", {}),
                                 "vetor-lembretes": {"task": "vetor.tasks.avisar_lembretes", "schedule": 60.0}}
    s["VETOR_AGENTE_LIMITE_MINUTO"] = int(os.getenv("VETOR_AGENTE_LIMITE_MINUTO", "30"))
    # GitHub (SPEC-06): só o segredo do webhook. O _ANTERIOR continua valendo durante a troca (rotação).
    s["VETOR_GITHUB_WEBHOOK_SEGREDOS"] = [v for v in (os.getenv("VETOR_GITHUB_WEBHOOK_SECRET", ""),
                                                      os.getenv("VETOR_GITHUB_WEBHOOK_SECRET_ANTERIOR", "")) if v]
    # Monitoramento (SPEC-07): token por provedor no cabeçalho X-Vetor-Token (Kuma e Beszel não assinam webhooks).
    s["VETOR_MONITOR_TOKENS"] = {p: [v for v in (os.getenv(f"VETOR_{p.upper()}_TOKEN", ""), os.getenv(f"VETOR_{p.upper()}_TOKEN_ANTERIOR", "")) if v]
                                 for p in ("kuma", "beszel")}
    s["VETOR_MONITOR_JANELA_MIN"] = int(os.getenv("VETOR_MONITOR_JANELA_MIN", "15"))  # reincidência reabre o mesmo incidente
    s["VETOR_MONITOR_AVISO_MIN"] = int(os.getenv("VETOR_MONITOR_AVISO_MIN", "30"))    # no máximo 1 e-mail por incidente nesse intervalo
    s["VETOR_MONITOR_RETENCAO_DIAS"] = int(os.getenv("VETOR_MONITOR_RETENCAO_DIAS", "90"))  # depois disso, payload apagado
    s["CELERY_BEAT_SCHEDULE"]["vetor-monitoramento-retencao"] = {"task": "vetor.tasks.limpar_monitoramento", "schedule": 86400.0}
    # Adoção (SPEC-08): eventos de uso mais antigos que isto são apagados (tarefa diária).
    s["VETOR_USO_RETENCAO_DIAS"] = int(os.getenv("VETOR_USO_RETENCAO_DIAS", "180"))
    s["CELERY_BEAT_SCHEDULE"]["vetor-uso-retencao"] = {"task": "vetor.tasks.limpar_uso", "schedule": 86400.0}
    # Financeiro (SPEC-09): fechado; só estes usuários (o "matriz") consultam e alteram custos. Vazio = ninguém.
    s["VETOR_FINANCEIRO_USUARIOS"] = [u.strip().lower() for u in os.getenv("VETOR_FINANCEIRO_USUARIOS", "").split(",") if u.strip()]
    # Operação (SPEC-10): alerta se o último backup bem-sucedido for mais velho que isto; verificação a cada hora.
    s["VETOR_BACKUP_MAX_HORAS"] = int(os.getenv("VETOR_BACKUP_MAX_HORAS", "26"))
    s["CELERY_BEAT_SCHEDULE"]["vetor-avisos-operacao"] = {"task": "vetor.tasks.avisos_operacao", "schedule": 3600.0}
    # O Taiga desliga loggers não declarados: sem isto, vetor.agente e vetor.lembretes não aparecem (só ids, nunca conteúdo).
    s["LOGGING"]["loggers"]["vetor"] = {"handlers": ["console"], "level": "INFO", "propagate": False}
    # SPEC-10: toda linha do console com o correlation_id da requisição (X-Request-ID; "-" fora de requisição).
    s["LOGGING"]["filters"]["correlacao"] = {"()": "vetor.correlacao.Filtro"}
    s["LOGGING"]["handlers"]["console"]["filters"] = ["correlacao"]
    s["LOGGING"]["formatters"]["simple"]["format"] = "%(levelname)s:%(asctime)s:[%(correlation_id)s] %(message)s"
    # Nome do sistema financeiro/contratual externo ainda não confirmado (README): fica configurável.
    s["VETOR_SISTEMA_FINANCEIRO"] = {"nome": os.getenv("VETOR_SISTEMA_FINANCEIRO_NOME", ""),
                                     "url": os.getenv("VETOR_SISTEMA_FINANCEIRO_URL", "")}  # o feedback oficial envia para support@taiga.io
