from django.core.management.base import BaseCommand

from vetor.lembretes import avisar_vencidos


class Command(BaseCommand):
    help = "Avisa lembretes vencidos (o Celery beat já roda isto a cada minuto; útil para teste e operação)."

    def handle(self, *args, **options):
        self.stdout.write(f"{avisar_vencidos()} lembrete(s) avisado(s)")
