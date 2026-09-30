from django.core.management.base import BaseCommand
from django.db import transaction
from productos.models import Subproducto

class Command(BaseCommand):
    help = "Actualiza todos los subproductos marcados como 'USADO' a 'NUEVO'."

    def add_arguments(self, parser):
        parser.add_argument(
            '--empresa-id',
            type=int,
            help='Opcional: ID de la empresa a filtrar. Si no se especifica, actualiza todas.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula la actualización sin realizar cambios en la base de datos.',
        )

    def handle(self, *args, **options):
        empresa_id = options.get('empresa_id')
        dry_run = options.get('dry_run')

        qs = Subproducto.objects.all()
        if empresa_id:
            qs = qs.filter(empresa_id=empresa_id)

        total_subproductos = qs.count()
        usados_qs = qs.filter(estado='USADO')
        cantidad_usados = usados_qs.count()
        ya_nuevos = total_subproductos - cantidad_usados

        self.stdout.write(self.style.NOTICE(f"=== Actualización de Subproductos a 'NUEVO' ==="))
        self.stdout.write(f"Total de subproductos encontrados: {total_subproductos}")
        self.stdout.write(f"Subproductos en estado 'NUEVO': {ya_nuevos}")
        self.stdout.write(f"Subproductos en estado 'USADO' a actualizar: {cantidad_usados}")

        if cantidad_usados == 0:
            self.stdout.write(self.style.SUCCESS("Todos los subproductos ya se encuentran en estado 'NUEVO'."))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(f"[DRY-RUN] Se actualizarían {cantidad_usados} subproductos a 'NUEVO'."))
            return

        with transaction.atomic():
            actualizados = usados_qs.update(estado='NUEVO')

        self.stdout.write(self.style.SUCCESS(f"¡Éxito! Se actualizaron {actualizados} subproductos a estado 'NUEVO'."))
