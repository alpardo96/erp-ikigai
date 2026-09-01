"""Reconstruye el stock disponible a partir de `stock_inicial` y los comprobantes (Plan 053).

Es la red de seguridad que antes no existía: mientras el stock fue un contador incremental, un
movimiento perdido —un borrado masivo, una importación, un proceso con las señales desactivadas—
lo dejaba mal para siempre y sin forma de detectarlo.

    python manage.py recalcular_stock --empresa 2
    python manage.py recalcular_stock --empresa 2 --sucursal 3
    python manage.py recalcular_stock --empresa 2 --producto 1234
    python manage.py recalcular_stock --empresa 2 --dry-run      # sólo informa diferencias
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from productos.models import StockSucursal
from productos.services.stock_service import recalcular_stock, recalcular_stock_masivo


class Command(BaseCommand):
    help = "Recalcula StockSucursal.cantidad desde stock_inicial + comprobantes."

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=int, required=True,
                            help="ID de empresa (obligatorio: el stock nunca se toca sin acotar).")
        parser.add_argument('--sucursal', type=int, help="Acotar a una sucursal.")
        parser.add_argument('--producto', type=int, help="Acotar a un producto.")
        parser.add_argument('--dry-run', action='store_true',
                            help="Informa las diferencias sin escribir nada.")

    def handle(self, *args, **opciones):
        empresa_id = opciones['empresa']
        registros = StockSucursal.objects.filter(producto__empresa_id=empresa_id)
        if opciones.get('sucursal'):
            registros = registros.filter(sucursal_id=opciones['sucursal'])
        if opciones.get('producto'):
            registros = registros.filter(producto_id=opciones['producto'])

        total = registros.count()
        if not total:
            raise CommandError("No hay registros de stock con esos filtros.")

        seco = opciones['dry_run']
        self.stdout.write(
            f"{'Simulando' if seco else 'Recalculando'} {total} registros de stock "
            f"de la empresa {empresa_id}…")

        # Se detectan las diferencias en cuatro consultas agrupadas y sólo se reescriben las filas
        # que efectivamente no coinciden: recalcular una por una serían ~4 consultas × 13.600 filas.
        diferencias = recalcular_stock_masivo(
            empresa_id, opciones.get('sucursal'), opciones.get('producto'))

        if diferencias and not seco:
            with transaction.atomic():
                for producto_id, sucursal_id, _antes, _despues in diferencias:
                    recalcular_stock(producto_id, sucursal_id)

        if diferencias:
            self.stdout.write(self.style.WARNING(
                f"\n{len(diferencias)} registros no coincidían:"))
            self.stdout.write(f"  {'producto':>9} {'sucursal':>9} {'antes':>14} {'después':>14}")
            for producto_id, sucursal_id, antes, despues in diferencias[:50]:
                self.stdout.write(
                    f"  {producto_id:>9} {sucursal_id:>9} {antes:>14} {despues:>14}")
            if len(diferencias) > 50:
                self.stdout.write(f"  … y {len(diferencias) - 50} más")
        else:
            self.stdout.write(self.style.SUCCESS(
                "\nTodos los registros ya estaban correctos."))

        if seco:
            self.stdout.write(self.style.NOTICE("\nSimulación: no se escribió nada."))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\nListo. {total} registros verificados, {len(diferencias)} corregidos."))
