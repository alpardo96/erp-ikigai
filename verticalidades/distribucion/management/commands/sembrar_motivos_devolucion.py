"""Siembra el catálogo inicial de Motivos de Devolución (Plan 074).

Uso:
    manage.py sembrar_motivos_devolucion --empresa 3
    manage.py sembrar_motivos_devolucion            # todas las DISTRIBUIDORA

Es idempotente: se puede correr las veces que haga falta.
"""
from django.core.management.base import BaseCommand

from empresas.models import Empresa
from verticalidades.distribucion.services.catalogos import sembrar_motivos


class Command(BaseCommand):
    help = "Carga el catálogo inicial de motivos de devolución para empresas distribuidoras."

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=int, default=None,
                            help="ID de la empresa. Si se omite, se aplica a todas las DISTRIBUIDORA.")

    def handle(self, *args, **options):
        empresa_id = options['empresa']
        if empresa_id:
            empresas = Empresa.objects.filter(id=empresa_id)
            if not empresas.exists():
                self.stderr.write(self.style.ERROR(f"No existe la empresa {empresa_id}."))
                return
        else:
            empresas = Empresa.objects.filter(tipo_actividad='DISTRIBUIDORA')
            if not empresas.exists():
                self.stdout.write(self.style.WARNING(
                    "No hay empresas con tipo_actividad='DISTRIBUIDORA'. "
                    "Usá --empresa <id> para forzar una en particular."))
                return

        for empresa in empresas:
            creados = sembrar_motivos(empresa.id)
            self.stdout.write(self.style.SUCCESS(
                f"[{empresa.id}] {empresa.nombre}: {creados} motivo(s) creado(s)."))
