"""Carga el maestro de 75 clases de tabaco con sus coeficientes (Plan 081).

Uso:
    manage.py importar_clases_tabaco --empresa 3
    manage.py importar_clases_tabaco --empresa 3 --dry-run
    manage.py importar_clases_tabaco --empresa 3 --archivo otra/ruta.csv

Es idempotente: se puede correr las veces que haga falta. Informa altas, actualizaciones y
filas sin cambios, y si el archivo tiene algún problema no escribe nada.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from empresas.models import Empresa
from verticalidades.agricola.tabaco.services.importacion_clases import (
    ErrorImportacion, importar_clases,
)

ARCHIVO_POR_DEFECTO = Path(settings.BASE_DIR) / 'docs' / 'agricola' / 'tabaco_clase.csv'


class Command(BaseCommand):
    help = "Importa el maestro de clases de tabaco desde el CSV, de forma idempotente."

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=int, required=True,
                            help="ID de la empresa sobre la que se carga el maestro.")
        parser.add_argument('--archivo', type=str, default=None,
                            help=f"Ruta del CSV. Por defecto: {ARCHIVO_POR_DEFECTO}")
        parser.add_argument('--dry-run', action='store_true',
                            help="Valida e informa lo que haría, sin escribir en la base.")
        parser.add_argument('--detalle', action='store_true',
                            help="Lista una línea por cada alta y actualización.")

    def handle(self, *args, **options):
        empresa = Empresa.objects.filter(pk=options['empresa']).first()
        if not empresa:
            raise CommandError(f"No existe la empresa {options['empresa']}.")

        ruta = Path(options['archivo']) if options['archivo'] else ARCHIVO_POR_DEFECTO
        dry_run = options['dry_run']

        self.stdout.write(f"Empresa : [{empresa.pk}] {empresa.nombre}")
        self.stdout.write(f"Archivo : {ruta}")
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo --dry-run: no se escribe nada."))

        try:
            resultado = importar_clases(empresa, ruta, dry_run=dry_run)
        except ErrorImportacion as e:
            raise CommandError(f"No se importó nada. {e}")

        if options['detalle']:
            for linea in resultado.detalle:
                self.stdout.write(f"  {linea}")

        if resultado.variedades_creadas:
            self.stdout.write(f"Variedades creadas : {resultado.variedades_creadas}")

        self.stdout.write(
            f"Altas {resultado.creadas} | "
            f"Actualizadas {resultado.actualizadas} | "
            f"Sin cambios {resultado.sin_cambios} | "
            f"Total {resultado.total}"
        )

        if resultado.total != 75:
            self.stdout.write(self.style.WARNING(
                f"El maestro heredado tiene 75 clases y se procesaron {resultado.total}. "
                f"Verificá el archivo."))

        estilo = self.style.WARNING if dry_run else self.style.SUCCESS
        self.stdout.write(estilo("Simulación terminada." if dry_run else "Importación terminada."))
