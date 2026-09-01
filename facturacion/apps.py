from django.apps import AppConfig


class FacturacionConfig(AppConfig):
    name = 'facturacion'

    def ready(self):
        import facturacion.signals

