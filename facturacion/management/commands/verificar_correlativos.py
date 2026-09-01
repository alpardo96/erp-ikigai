"""Verifica la integridad de las series correlativas de los documentos prenumerados por
el sistema (Plan 028): Órdenes de Compra, Informes de Recepción y Remitos Internos.

Uso:
    python manage.py verificar_correlativos [--empresa <id>]

Reporta, por (empresa, punto, tipo), faltantes (huecos), duplicados y desfasajes contra
el contador. Devuelve exit code 1 si hay alguna serie inconsistente.
"""
from django.core.management.base import BaseCommand

from core.services.numeracion import auditar_correlativos


class Command(BaseCommand):
    help = "Verifica la continuidad de los correlativos de OC / Recepción / Remito Interno."

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=int, default=None, help="ID de empresa a auditar (opcional).")

    def handle(self, *args, **options):
        filas = auditar_correlativos(empresa_id=options.get('empresa'))
        if not filas:
            self.stdout.write("No hay documentos prenumerados para auditar.")
            return

        hay_error = False
        for f in filas:
            cab = (f"Empresa {f['empresa_id']} · {f['tipo_label']} · Punto {f['punto']:04d} "
                   f"→ {f['cantidad']} docs (1..{f['maximo']})")
            if f['ok']:
                self.stdout.write(self.style.SUCCESS(f"OK   {cab}"))
            else:
                hay_error = True
                detalle = []
                if f['minimo'] != 1:
                    detalle.append(f"no arranca en 1 (mín {f['minimo']})")
                if f['faltantes']:
                    detalle.append(f"faltantes: {f['faltantes']}")
                if f['duplicados']:
                    detalle.append(f"duplicados: {f['duplicados']}")
                if f['contador'] is not None and f['contador'] != f['maximo']:
                    detalle.append(f"contador={f['contador']} ≠ máx={f['maximo']}")
                self.stdout.write(self.style.ERROR(f"FALLA {cab} — " + "; ".join(detalle)))

        if hay_error:
            self.stderr.write(self.style.ERROR("\nSe detectaron series con inconsistencias."))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("\nTodas las series están correctas."))
