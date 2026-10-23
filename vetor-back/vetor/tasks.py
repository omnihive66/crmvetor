from taiga.celery import app

from . import lembretes


@app.task(name="vetor.tasks.avisar_lembretes")
def avisar_lembretes():
    return lembretes.avisar_vencidos()


@app.task(name="vetor.tasks.processar_evento_github", bind=True)
def processar_evento_github(self, evento_id):
    from . import github
    ev = github.processar(evento_id)
    if ev.status == ev.FALHOU and ev.tentativas < github.MAX_TENTATIVAS:
        raise self.retry(countdown=60 * 2 ** ev.tentativas)  # 2, 4, 8, 16 min; depois fica na fila de falhas


@app.task(name="vetor.tasks.processar_evento_monitoramento", bind=True)
def processar_evento_monitoramento(self, evento_id):
    from . import monitoramento
    ev = monitoramento.processar(evento_id)
    if ev.processamento == ev.FALHOU and ev.tentativas < monitoramento.MAX_TENTATIVAS:
        raise self.retry(countdown=60 * 2 ** ev.tentativas)


@app.task(name="vetor.tasks.limpar_monitoramento")
def limpar_monitoramento():
    from . import monitoramento
    return monitoramento.limpar_payloads()


@app.task(name="vetor.tasks.limpar_uso")
def limpar_uso():
    from . import operacao
    return operacao.limpar_uso()


@app.task(name="vetor.tasks.avisos_operacao")
def avisos_operacao():
    from . import saude
    return [a["codigo"] for a in saude.avisar()]
