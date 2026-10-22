from django.apps import AppConfig


class VetorConfig(AppConfig):
    name = "vetor"
    verbose_name = "Vetor Sistemas"
    default_auto_field = "django.db.models.AutoField"

    def ready(self):
        from . import sinais
        sinais.conectar()
