"""
actualizar_ids_contables.py
===========================
Management command que corrige los IDs de cuentas contables en las tablas que fueron
migradas desde el ERP VFP anterior.

PROBLEMA:
  Al migrar desde VFP, los campos que referencian cuentas (cta_pat, cta_res en
  ClienteProveedor y cta_ventas_id, cta_compras_id en Rubro) quedaron con los IDs
  del sistema anterior. En Django/PostgreSQL, las cuentas tienen nuevos IDs
  auto-incrementales (Cuenta.id), y el ID viejo se preservó en Cuenta.codigo.

SOLUCIÓN:
  Se construye un mapa de traducción { Cuenta.codigo (VFP) → Cuenta.id (Django) }
  y se actualizan los campos afectados en ClienteProveedor y Rubro.

USO:
  # Modo simulación (no modifica la BD):
  python manage.py actualizar_ids_contables --empresa 1 --dry-run

  # Ejecución real:
  python manage.py actualizar_ids_contables --empresa 1
"""
import os
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = (
        'Actualiza los IDs de cuentas contables en ClienteProveedor y Rubro, '
        'traduciendo los códigos VFP heredados a los nuevos IDs de Django/PostgreSQL.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--empresa',
            type=int,
            required=True,
            help='ID de la Empresa destino (obligatorio).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Modo simulación: muestra los cambios sin aplicarlos.',
        )

    def handle(self, *args, **options):
        empresa_id = options['empresa']
        dry_run = options['dry_run']

        # Importaciones tardías para evitar problemas de inicialización circular.
        from contable.models import Cuenta
        from facturacion.models import ClienteProveedor
        from productos.models import Rubro
        from empresas.models import Empresa

        # Verificar que la empresa existe.
        try:
            empresa = Empresa.objects.get(id=empresa_id)
        except Empresa.DoesNotExist:
            raise CommandError(f'La Empresa con ID={empresa_id} no existe.')

        def safe_text(text):
            if not text:
                return ""
            # Reemplaza cualquier caracter no-ASCII por "?"
            return str(text).encode('ascii', errors='replace').decode('ascii')

        modo = 'SIMULACIÓN (--dry-run)' if dry_run else 'EJECUCIÓN REAL'
        self.stdout.write(self.style.HTTP_INFO(
            f'\n{"=" * 70}\n'
            f'  Actualizacion de IDs Contables Post-Migracion VFP\n'
            f'  Empresa: {safe_text(empresa.nombre)} (ID={empresa_id})\n'
            f'  Modo: {modo}\n'
            f'  Fecha: {datetime.now()}\n'
            f'{"=" * 70}\n'
        ))

        # =====================================================================
        # FASE 1: Construir el mapa de traducción { codigo_vfp → id_nuevo }
        # =====================================================================
        self.stdout.write(self.style.MIGRATE_HEADING(
            '\nFASE 1: Construyendo mapa de traduccion (Cuenta.codigo -> Cuenta.id)...'
        ))

        # Solo cuentas que tienen un código VFP asignado (no NULL, no 0).
        cuentas = Cuenta.objects.filter(
            empresa_id=empresa_id,
            codigo__isnull=False,
        ).exclude(codigo=0)

        # El mapa traduce: { codigo_vfp (int) → id_nuevo (int) }
        # Ejemplo: { 157: 42, 203: 89, 310: 5 }
        mapa = {}
        duplicados = {}
        for cuenta in cuentas:
            if cuenta.codigo in mapa:
                # Si hay códigos VFP duplicados, registrar la colisión para reportarla.
                duplicados.setdefault(cuenta.codigo, [mapa[cuenta.codigo]]).append(cuenta.id)
            else:
                mapa[cuenta.codigo] = cuenta.id

        self.stdout.write(f'  Cuentas con código VFP encontradas: {len(mapa)}')

        if duplicados:
            self.stdout.write(self.style.WARNING(
                f'  [!] ADVERTENCIA: {len(duplicados)} codigo(s) VFP duplicado(s):'
            ))
            for cod_vfp, ids_nuevos in duplicados.items():
                self.stdout.write(self.style.WARNING(
                    f'    codigo VFP={cod_vfp} -> IDs nuevos: {ids_nuevos} '
                    f'(se usara el primero: {ids_nuevos[0]})'
                ))

        if not mapa:
            raise CommandError(
                'No se encontraron cuentas con código VFP. '
                '¿Se ejecutó primero la migración de cble_cuentas?'
            )

        # =====================================================================
        # FASE 2: Actualizar ClienteProveedor (cta_pat, cta_res)
        # =====================================================================
        self.stdout.write(self.style.MIGRATE_HEADING(
            '\nFASE 2: Actualizando ClienteProveedor (cta_pat, cta_res)...'
        ))

        cli_pros = ClienteProveedor.objects.filter(empresa_id=empresa_id)
        total_cli = cli_pros.count()
        actualizados_cli = 0
        sin_match_cli = []  # Registros cuyo cta_pat/cta_res no está en el mapa.
        ya_correctos_cli = 0
        objs_to_update_cli = []

        with transaction.atomic():
            for cp in cli_pros:
                cambios = False
                detalle_cambio = []

                # --- cta_pat ---
                if cp.cta_pat and cp.cta_pat != 0:
                    if cp.cta_pat in mapa:
                        nuevo_id = mapa[cp.cta_pat]
                        if nuevo_id != cp.cta_pat:
                            # El valor actual es un código VFP -> traducir al ID nuevo.
                            detalle_cambio.append(
                                f'cta_pat: {cp.cta_pat} -> {nuevo_id}'
                            )
                            cp.cta_pat = nuevo_id
                            cambios = True
                        else:
                            # El código VFP coincide con el ID nuevo (caso poco probable).
                            ya_correctos_cli += 1
                    else:
                        # El valor no está en el mapa: podría ser un ID ya actualizado,
                        # o un dato huérfano. Se registra para revisión.
                        sin_match_cli.append({
                            'pk': cp.pk,
                            'razon_social': cp.razon_social,
                            'campo': 'cta_pat',
                            'valor': cp.cta_pat,
                        })

                # --- cta_res ---
                if cp.cta_res and cp.cta_res != 0:
                    if cp.cta_res in mapa:
                        nuevo_id = mapa[cp.cta_res]
                        if nuevo_id != cp.cta_res:
                            detalle_cambio.append(
                                f'cta_res: {cp.cta_res} -> {nuevo_id}'
                            )
                            cp.cta_res = nuevo_id
                            cambios = True
                        else:
                            ya_correctos_cli += 1
                    else:
                        sin_match_cli.append({
                            'pk': cp.pk,
                            'razon_social': cp.razon_social,
                            'campo': 'cta_res',
                            'valor': cp.cta_res,
                        })

                if cambios:
                    actualizados_cli += 1
                    if not dry_run:
                        objs_to_update_cli.append(cp)
                    self.stdout.write(
                        f'  {"[SIM]" if dry_run else "[OK]"} '
                        f'#{cp.pk} {safe_text(cp.razon_social)}: {", ".join(detalle_cambio)}'
                    )

            if not dry_run and objs_to_update_cli:
                self.stdout.write(self.style.MIGRATE_HEADING(f'  Guardando {len(objs_to_update_cli)} cambios en base de datos...'))
                ClienteProveedor.objects.bulk_update(objs_to_update_cli, ['cta_pat', 'cta_res'], batch_size=1000)

            # Reporte de la Fase 2
            self.stdout.write(f'\n  Resumen ClienteProveedor:')
            self.stdout.write(f'    Total evaluados: {total_cli}')
            self.stdout.write(self.style.SUCCESS(f'    Actualizados: {actualizados_cli}'))
            if ya_correctos_cli:
                self.stdout.write(f'    Ya correctos (sin cambio): {ya_correctos_cli}')

            if sin_match_cli:
                self.stdout.write(self.style.WARNING(
                    f'    [!] Sin coincidencia en mapa: {len(sin_match_cli)} campo(s)'
                ))
                for item in sin_match_cli[:20]:  # Limitar a 20 para no saturar la consola.
                    self.stdout.write(self.style.WARNING(
                        f'      #{item["pk"]} {safe_text(item["razon_social"])}: '
                        f'{item["campo"]}={item["valor"]} (no existe en Cuenta.codigo)'
                    ))
                if len(sin_match_cli) > 20:
                    self.stdout.write(self.style.WARNING(
                        f'      ... y {len(sin_match_cli) - 20} más.'
                    ))

        # =====================================================================
        # FASE 3: Actualizar Rubro (cta_ventas_id, cta_compras_id)
        # =====================================================================
        self.stdout.write(self.style.MIGRATE_HEADING(
            '\nFASE 3: Actualizando Rubro (cta_ventas, cta_compras)...'
        ))

        rubros = Rubro.objects.filter(empresa_id=empresa_id)
        total_rub = rubros.count()
        actualizados_rub = 0
        sin_match_rub = []
        objs_to_update_rub = []

        with transaction.atomic():
            for rubro in rubros:
                cambios = False
                detalle_cambio = []

                # --- cta_ventas_id ---
                # cta_ventas es ForeignKey → Django guarda el _id en la columna cta_ventas_id.
                if rubro.cta_ventas_id and rubro.cta_ventas_id != 0:
                    if rubro.cta_ventas_id in mapa:
                        nuevo_id = mapa[rubro.cta_ventas_id]
                        if nuevo_id != rubro.cta_ventas_id:
                            detalle_cambio.append(
                                f'cta_ventas: {rubro.cta_ventas_id} -> {nuevo_id}'
                            )
                            rubro.cta_ventas_id = nuevo_id
                            cambios = True
                    else:
                        sin_match_rub.append({
                            'pk': rubro.pk,
                            'detalle': rubro.detalle,
                            'campo': 'cta_ventas_id',
                            'valor': rubro.cta_ventas_id,
                        })

                # --- cta_compras_id ---
                if rubro.cta_compras_id and rubro.cta_compras_id != 0:
                    if rubro.cta_compras_id in mapa:
                        nuevo_id = mapa[rubro.cta_compras_id]
                        if nuevo_id != rubro.cta_compras_id:
                            detalle_cambio.append(
                                f'cta_compras: {rubro.cta_compras_id} -> {nuevo_id}'
                            )
                            rubro.cta_compras_id = nuevo_id
                            cambios = True
                    else:
                        sin_match_rub.append({
                            'pk': rubro.pk,
                            'detalle': rubro.detalle,
                            'campo': 'cta_compras_id',
                            'valor': rubro.cta_compras_id,
                        })

                if cambios:
                    actualizados_rub += 1
                    if not dry_run:
                        objs_to_update_rub.append(rubro)
                    self.stdout.write(
                        f'  {"[SIM]" if dry_run else "[OK]"} '
                        f'#{rubro.pk} {safe_text(rubro.detalle)}: {", ".join(detalle_cambio)}'
                    )

            if not dry_run and objs_to_update_rub:
                self.stdout.write(self.style.MIGRATE_HEADING(f'  Guardando {len(objs_to_update_rub)} cambios en base de datos...'))
                Rubro.objects.bulk_update(objs_to_update_rub, ['cta_ventas_id', 'cta_compras_id'], batch_size=100)

            # Reporte de la Fase 3
            self.stdout.write(f'\n  Resumen Rubro:')
            self.stdout.write(f'    Total evaluados: {total_rub}')
            self.stdout.write(self.style.SUCCESS(f'    Actualizados: {actualizados_rub}'))

            if sin_match_rub:
                self.stdout.write(self.style.WARNING(
                    f'    [!] Sin coincidencia en mapa: {len(sin_match_rub)} campo(s)'
                ))
                for item in sin_match_rub[:20]:
                    self.stdout.write(self.style.WARNING(
                        f'      #{item["pk"]} {safe_text(item["detalle"])}: '
                        f'{item["campo"]}={item["valor"]} (no existe en Cuenta.codigo)'
                    ))

        # =====================================================================
        # RESUMEN FINAL
        # =====================================================================
        total_actualizados = actualizados_cli + actualizados_rub
        total_sin_match = len(sin_match_cli) + len(sin_match_rub)

        self.stdout.write(self.style.HTTP_INFO(
            f'\n{"=" * 70}\n'
            f'  RESUMEN FINAL\n'
            f'{"=" * 70}'
        ))
        self.stdout.write(f'  Registros actualizados: {total_actualizados}')
        self.stdout.write(f'    - ClienteProveedor: {actualizados_cli}')
        self.stdout.write(f'    - Rubro: {actualizados_rub}')

        if total_sin_match:
            self.stdout.write(self.style.WARNING(
                f'  Campos sin coincidencia en mapa: {total_sin_match}'
            ))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                '\n  [SIM] MODO SIMULACION: No se modifico la base de datos.'
                '\n     Ejecute sin --dry-run para aplicar los cambios.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\n  [OK] Actualizacion completada exitosamente.'
            ))
