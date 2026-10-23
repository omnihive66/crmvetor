import json

from django.core.management.base import BaseCommand

from vetor.auditoria import registrar
from vetor.models import BackupRegistro


class Command(BaseCommand):
    help = "Registra um backup ou uma restauração de teste (chamado pelo scripts/vetor.sh; alimenta a saúde operacional)."

    def add_arguments(self, parser):
        parser.add_argument("--tipo", choices=[BackupRegistro.BACKUP, BackupRegistro.RESTAURACAO], required=True)
        parser.add_argument("--local", required=True)
        parser.add_argument("--resultado", choices=["ok", "falhou"], required=True)
        parser.add_argument("--cifrado", action="store_true")
        parser.add_argument("--detalhes", default="{}", help="JSON com tamanhos, contagens e duração (sem segredos)")

    def handle(self, *args, **o):
        b = BackupRegistro.objects.create(tipo=o["tipo"], local=o["local"][:300], resultado=o["resultado"], cifrado=o["cifrado"],
                                          detalhes=json.loads(o["detalhes"]))
        registrar(f"{o['tipo']}.registrado", b, resultado=b.resultado, cifrado=b.cifrado)
        self.stdout.write(f"registrado {b.tipo} #{b.id}: {b.resultado}")
