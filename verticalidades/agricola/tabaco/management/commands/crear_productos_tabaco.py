"""Crea el `Producto` de stock de cada variedad de tabaco (Plan 085).

Uso:
    manage.py crear_productos_tabaco --empresa 1
    manage.py crear_productos_tabaco --empresa 1 --dry-run

Es idempotente: sólo toca las variedades que todavía no tienen producto asignado. Si preferís usar
un producto que ya existe, asignalo desde el ABM de variedades y este comando lo respeta.

Sin producto asignado, los kilos del acopio NO entran al stock: el término no encuentra a qué
imputar. La pantalla de conciliación lo señala.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from empresas.models import Empresa
from productos.models import Producto
from verticalidades.agricola.tabaco.models import ConfiguracionTabaco, VariedadTabaco


class Command(BaseCommand):
    help = "Crea y vincula el producto de stock de cada variedad de tabaco (en kilos)."

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=int, required=True)
        parser.add_argument('--dry-run', action='store_true',
                            help="Informa lo que haría, sin escribir en la base.")

    @transaction.atomic
    def handle(self, *args, **options):
        empresa = Empresa.objects.filter(pk=options['empresa']).first()
        if not empresa:
            raise CommandError(f"No existe la empresa {options['empresa']}.")

        # La alícuota sale de la configuración del acopio para que, al vender, el IVA salga bien
        # sin tener que cargarlo de nuevo en el producto.
        config = ConfiguracionTabaco.objects.filter(empresa=empresa).first()
        alicuota = config.alicuota_iva if config else Decimal('21.00')

        # `call_command(..., verbosity=0)` no silencia `self.stdout.write` por sí solo: hay que
        # mirarlo. Sin esto, los tests que invocan el comando llenan la salida de ruido.
        hablar = options.get('verbosity', 1) >= 1

        creados = vinculados = ya_tenian = 0
        for variedad in VariedadTabaco.objects.filter(empresa=empresa).order_by('codigo'):
            if variedad.producto_id:
                ya_tenian += 1
                if hablar:
                    self.stdout.write(f"  = {variedad.detalle:12} ya usa «{variedad.producto.detalle}»")
                continue

            detalle = f"TABACO {variedad.detalle}"
            producto = Producto.objects.filter(empresa=empresa, detalle=detalle).first()
            if producto is None:
                producto = Producto(empresa=empresa, detalle=detalle, unidad_venta='KG',
                                    alic_iva=alicuota, peso_unitario_kg=Decimal('1.000'))
                if not options['dry_run']:
                    producto.save()
                creados += 1
                if hablar:
                    self.stdout.write(self.style.SUCCESS(
                        f"  + {variedad.detalle:12} producto «{detalle}» creado"))
            elif hablar:
                self.stdout.write(f"  ~ {variedad.detalle:12} reutiliza «{detalle}»")

            variedad.producto = producto
            if not options['dry_run']:
                variedad.save(update_fields=['producto'])
            vinculados += 1

        if hablar:
            self.stdout.write("")
            self.stdout.write(f"Productos creados {creados} | Variedades vinculadas {vinculados} | "
                              f"Ya tenían {ya_tenian}")

        if options['dry_run']:
            transaction.set_rollback(True)
            if hablar:
                self.stdout.write(self.style.WARNING("Modo --dry-run: no se escribió nada."))
        elif hablar:
            self.stdout.write(self.style.SUCCESS("Listo."))
