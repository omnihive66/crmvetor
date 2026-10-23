from taiga.celery import app

from . import lembretes


@app.task(name="vetor.tasks.avisar_lembretes")
def avisar_lembretes():
    return lembretes.avisar_vencidos()
