# -*- coding: utf-8 -*-
"""
Management Command: migrar_productos
======================================
Migra los datos del archivo CSV legacy VSFox (producto.csv) hacia las tablas
Producto, StockSucursal, Marca, Rubro y Familia del ERP Ikigai 2.

Empresa destino: Armería Armar SAS (empresa_id=2)
Sucursales destino:
  - Casa Central (sucursal_id=3) ← campo STOCK del CSV
  - Yerba Buena  (sucursal_id=4) ← campo STKSUC1 del CSV

Prerrequisito: ejecutar primero 'migrar_cli_pro' para que existan los
proveedores en la tabla ClienteProveedor.

Decisiones de diseño:
- Moneda: PES→PES, USD→DOL, US→DOL
- Stock negativo: se migra tal cual (dato histórico del legacy)
- Proveedores: match por nombre (razón social) contra ClienteProveedor
- SubFamilia (ID_SFLIA): se ignora (no hay modelo correspondiente)
- Datos maestros (Marca, Rubro, Familia): se crean para empresa_id=2
  copiando nombres de empresa_id=1 que son los mismos del legacy
"""

import csv
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction
from empresas.models import Empresa, Sucursal
from facturacion.models import ClienteProveedor
from productos.models import Marca, Rubro, Familia, Producto, StockSucursal


class Command(BaseCommand):
    help = 'Migra productos desde Modelos/producto.csv a la DB (empresa_id=2)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula la migración sin escribir en la DB',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        self.stdout.write(self.style.WARNING(
            '=== MIGRACION PRODUCTO.CSV -> Productos ===\n'
            f'Modo: {"SIMULACION (dry-run)" if dry_run else "EJECUCION REAL"}'
        ))

        # ---------------------------------------------------------------
        # 1. Validar que existan empresa y sucursales destino
        # ---------------------------------------------------------------
        try:
            empresa = Empresa.objects.get(pk=2)
        except Empresa.DoesNotExist:
            self.stderr.write(self.style.ERROR('ERROR: No existe empresa_id=2'))
            return

        try:
            suc_central = Sucursal.objects.get(pk=3)  # Casa Central
            suc_yb = Sucursal.objects.get(pk=4)        # Yerba Buena
        except Sucursal.DoesNotExist as e:
            self.stderr.write(self.style.ERROR(f'ERROR: Sucursal no encontrada: {e}'))
            return

        self.stdout.write(f'  Empresa: {empresa}')
        self.stdout.write(f'  Sucursal Central: {suc_central}')
        self.stdout.write(f'  Sucursal YB: {suc_yb}')

        csv_path = os.path.join('Modelos', 'producto.csv')
        if not os.path.exists(csv_path):
            self.stderr.write(self.style.ERROR(f'ERROR: No se encuentra {csv_path}'))
            return

        # ---------------------------------------------------------------
        # 2. Crear/obtener datos maestros (Marca, Rubro, Familia)
        #    Los datos maestros de empresa_id=1 son idénticos en nombre
        #    a los del legacy. Creamos copias para empresa_id=2.
        # ---------------------------------------------------------------
        self.stdout.write('\n--- Fase 1: Datos Maestros ---')

        # 2a. RUBROS: Copiar de empresa_id=1 a empresa_id=2
        # Los IDs legacy (1-12) corresponden al orden de los rubros existentes
        rubros_emp1 = list(Rubro.objects.filter(empresa_id=1).order_by('id'))
        mapeo_rubros = {}  # legacy_id (str) → Rubro nuevo
        for rubro_orig in rubros_emp1:
            # El id del rubro en empresa_id=1 coincide con el ID_RUBRO del legacy
            legacy_id = str(rubro_orig.id)
            rubro_nuevo, created = Rubro.objects.get_or_create(
                empresa=empresa,
                detalle=rubro_orig.detalle,
                defaults={
                    'margen': rubro_orig.margen,
                    'descuento_maximo': rubro_orig.descuento_maximo,
                }
            )
            # Catálogo unificado a nivel Empresa (sin M2M sucursales)
            mapeo_rubros[legacy_id] = rubro_nuevo
            if created:
                self.stdout.write(f'  Rubro creado: {rubro_nuevo.detalle} (legacy={legacy_id})')

        self.stdout.write(f'  Rubros mapeados: {len(mapeo_rubros)}')

        # 2b. FAMILIAS: Copiar de empresa_id=1 a empresa_id=2
        # Las familias del legacy tienen un ID que corresponde al ID de familia en empresa_id=1
        familias_emp1 = list(Familia.objects.filter(empresa_id=1).order_by('id'))
        mapeo_familias = {}  # legacy_id (str) → Familia nueva
        for fam_orig in familias_emp1:
            legacy_id = str(fam_orig.id)
            # Resolver el rubro para la nueva familia
            rubro_para_fam = None
            if fam_orig.rubro_id:
                legacy_rubro_id = str(fam_orig.rubro_id)
                rubro_para_fam = mapeo_rubros.get(legacy_rubro_id)

            fam_nueva, created = Familia.objects.get_or_create(
                empresa=empresa,
                detalle=fam_orig.detalle,
                defaults={
                    'margen': fam_orig.margen,
                    'rubro': rubro_para_fam,
                }
            )
            # Catálogo unificado a nivel Empresa (sin M2M sucursales)
            mapeo_familias[legacy_id] = fam_nueva
            if created:
                self.stdout.write(f'  Familia creada: {fam_nueva.detalle} (legacy={legacy_id})')

        self.stdout.write(f'  Familias mapeadas: {len(mapeo_familias)}')

        # 2c. MARCAS: Extraer del CSV (ID_MARCA → MARCA nombre) y crear
        marcas_csv = {}  # legacy_id → nombre
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                id_marca = row.get('ID_MARCA', '').strip()
                marca_name = row.get('MARCA', '').strip()
                if id_marca and marca_name and id_marca != '0':
                    marcas_csv[id_marca] = marca_name

        mapeo_marcas = {}  # legacy_id (str) → Marca nueva
        for legacy_id, nombre in marcas_csv.items():
            marca_nueva, created = Marca.objects.get_or_create(
                empresa=empresa,
                detalle=nombre,
                defaults={'margen': 0}
            )
            # Catálogo unificado a nivel Empresa (sin M2M sucursales)
            mapeo_marcas[legacy_id] = marca_nueva
            if created:
                self.stdout.write(f'  Marca creada: {nombre} (legacy={legacy_id})')

        self.stdout.write(f'  Marcas mapeadas: {len(mapeo_marcas)}')

        # ---------------------------------------------------------------
        # 3. Construir índice de proveedores por nombre para match
        #    Se buscan todos los ClienteProveedor de empresa_id=2
        # ---------------------------------------------------------------
        self.stdout.write('\n--- Fase 2: Índice de Proveedores ---')

        # Construir índice por nombre normalizado (primeros 20 chars uppercase)
        proveedores_por_nombre = {}
        for cp in ClienteProveedor.objects.filter(empresa_id=2):
            nombre_norm = cp.razon_social.upper().strip()
            proveedores_por_nombre[nombre_norm] = cp
            # También índice por prefijo (20 chars) para match parcial
            if len(nombre_norm) > 10:
                proveedores_por_nombre[nombre_norm[:20]] = cp

        self.stdout.write(f'  Proveedores indexados: {ClienteProveedor.objects.filter(empresa_id=2).count()}')

        # Lista de proveedores que no se encontrarán en cli_pro y deben crearse
        PROVEEDORES_FALTANTES = [
            'ABACA NORBERTO GUSTAVO',
            'ARTERO',
            'CAMPINOX SRL',
            'HOUSTON',
            'REBORN S.R.L.',
            'VIDAL GRANDE LUCAS SEBASTIAN',
        ]

        # Crear los 6 proveedores faltantes (aprobado por el usuario)
        for nombre in PROVEEDORES_FALTANTES:
            if nombre.upper() not in proveedores_por_nombre:
                cp_faltante = ClienteProveedor(
                    razon_social=nombre,
                    tipo_entidad=2,         # Proveedor
                    tipo_documento='99',    # Sin identificar
                    condicion_iva='CONSUMIDOR FINAL',
                    empresa=empresa,
                )
                cp_faltante.save()
                proveedores_por_nombre[nombre.upper()] = cp_faltante
                if len(nombre) > 10:
                    proveedores_por_nombre[nombre.upper()[:20]] = cp_faltante
                self.stdout.write(f'  Proveedor faltante creado: {nombre}')

        def resolver_proveedor(prove_nombre):
            """
            Busca un ClienteProveedor por nombre.
            Intenta match exacto primero, luego por prefijo de 20 chars.
            """
            if not prove_nombre:
                return None
            nombre = prove_nombre.upper().strip()
            # Match exacto
            if nombre in proveedores_por_nombre:
                return proveedores_por_nombre[nombre]
            # Match por prefijo (20 chars)
            if len(nombre) > 10:
                prefijo = nombre[:20]
                if prefijo in proveedores_por_nombre:
                    return proveedores_por_nombre[prefijo]
            return None

        # ---------------------------------------------------------------
        # 4. Mapeo de moneda CSV → modelo
        # ---------------------------------------------------------------
        MAPEO_MONEDA = {
            'PES': 'PES',
            'USD': 'DOL',
            'US': 'DOL',   # Aprobado por el usuario: US = USD = DOL
        }

        # ---------------------------------------------------------------
        # 5. Funciones auxiliares para parseo seguro
        # ---------------------------------------------------------------
        def parse_decimal(value, default=Decimal('0')):
            """Convierte un string a Decimal de forma segura."""
            try:
                v = value.strip() if value else ''
                if not v:
                    return default
                return Decimal(v.replace(',', '.'))
            except (InvalidOperation, ValueError):
                return default

        def parse_date(value):
            """Convierte un string de fecha (YYYY-MM-DD) a date o None."""
            try:
                v = value.strip() if value else ''
                if not v:
                    return None
                return datetime.strptime(v, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                return None

        # ---------------------------------------------------------------
        # 6. Leer CSV y migrar productos
        # ---------------------------------------------------------------
        self.stdout.write('\n--- Fase 3: Migración de Productos ---')

        stats = {
            'total': 0,
            'creados': 0,
            'errores': 0,
            'sin_proveedor': 0,
            'sin_marca': 0,
            'stock_suc3': 0,
            'stock_suc4': 0,
            'stock_negativos': 0,
        }

        proveedores_no_encontrados = Counter()

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')

            with transaction.atomic():
                if dry_run:
                    sid = transaction.savepoint()

                for row in reader:
                    stats['total'] += 1
                    codigo_legacy = row.get('CODIGO', '').strip()
                    detalle = row.get('DETALLE', '').strip()

                    if not detalle:
                        stats['errores'] += 1
                        self.stdout.write(self.style.WARNING(
                            f'  SKIP: Sin detalle (CODIGO={codigo_legacy})'
                        ))
                        continue

                    # --- Resolver relaciones ---
                    # Proveedor
                    prove_nombre = row.get('PROVE', '').strip()
                    id_prov = row.get('ID_PROV', '').strip()
                    proveedor = None
                    if prove_nombre and id_prov != '0':
                        proveedor = resolver_proveedor(prove_nombre)
                        if not proveedor:
                            stats['sin_proveedor'] += 1
                            proveedores_no_encontrados[prove_nombre] += 1

                    # Marca
                    id_marca = row.get('ID_MARCA', '').strip()
                    marca = mapeo_marcas.get(id_marca)
                    if id_marca and id_marca != '0' and not marca:
                        stats['sin_marca'] += 1

                    # Rubro y Familia
                    id_rubro = row.get('ID_RUBRO', '').strip()
                    rubro = mapeo_rubros.get(id_rubro)

                    id_flia = row.get('ID_FLIA', '').strip()
                    familia = mapeo_familias.get(id_flia)

                    # --- Parsear campos numéricos ---
                    moneda_csv = row.get('MONEDA', 'PES').strip()
                    moneda = MAPEO_MONEDA.get(moneda_csv, 'PES')

                    cto_adq = parse_decimal(row.get('CTO_ADQ', '0'))
                    cto_rep = parse_decimal(row.get('CTO_REP', '0'))
                    margen = parse_decimal(row.get('MARGEN', '0'))
                    precio_neto = parse_decimal(row.get('PRECIO', '0'))
                    alic_iva = parse_decimal(row.get('ALIC_IVA', '0'))
                    if Decimal('0.00') < alic_iva < Decimal('1.00'):
                        alic_iva = (alic_iva * Decimal('100.00')).quantize(Decimal('0.01'))
                    elif alic_iva == Decimal('0.00') and 'ESTAMPILLA' not in row.get('DETALLE', '').upper():
                        alic_iva = Decimal('21.00')
                    precio_total = parse_decimal(row.get('PCIOT', '0'))
                    cotiz_cpra = parse_decimal(row.get('COTIZ', '0'))
                    minimo = parse_decimal(row.get('MINIMO', '0'))
                    ptopedir = parse_decimal(row.get('PTOPEDIR', '0'))

                    # Booleanos
                    creden = row.get('CREDEN', '0').strip() == '1'
                    subprod = row.get('SUBPROD', '0').strip() == '1'

                    # Fechas
                    fec_adq = parse_date(row.get('FEC_ADQ', ''))
                    fec_act = parse_date(row.get('FEC_ACT', ''))

                    # Campos de texto
                    cod_prov = row.get('COD_PROV', '').strip() or None
                    cod_fab = row.get('COD_FAB', '').strip() or None

                    # Stock (migrado tal cual, incluso negativos)
                    stock_central = parse_decimal(row.get('STOCK', '0'))
                    stock_yb = parse_decimal(row.get('STKSUC1', '0'))

                    if stock_central < 0 or stock_yb < 0:
                        stats['stock_negativos'] += 1

                    try:
                        # Crear producto
                        producto = Producto(
                            empresa=empresa,
                            cod_prov=cod_prov,
                            cod_fab=cod_fab,
                            detalle=detalle,
                            proveedor=proveedor,
                            minimo=minimo,
                            ptopedir=ptopedir,
                            creden=creden,
                            moneda=moneda,
                            marca=marca,
                            rubro=rubro,
                            familia=familia,
                            subprod=subprod,
                            # `stock` y `stkcons` se dieron de baja (Plan 053): eran los campos
                            # que actualizaba el ERP en VFP. Hoy el stock se lleva por sucursal y
                            # se calcula; el valor del legacy va a `StockSucursal.stock_inicial`,
                            # más abajo.
                            # Campos de costo/precio
                            cto_adq=cto_adq,
                            fec_adq=fec_adq,
                            cto_rep=cto_rep,
                            fec_act=fec_act,
                            margen=margen,
                            precio_neto=precio_neto,
                            alic_iva=alic_iva,
                            precio_total=precio_total,
                            cotiz_cpra=cotiz_cpra,
                        )
                        producto.save()
                        stats['creados'] += 1

                        # --- Crear StockSucursal ---
                        # El stock del sistema anterior es el STOCK INICIAL de cada sucursal
                        # (Plan 053): es la existencia al momento de instalar, y el punto de
                        # partida del cálculo. `cantidad` arranca igual porque todavía no hay
                        # ningún comprobante cargado; de ahí en más la recalcula
                        # `productos.services.stock_service.recalcular_stock()`.
                        # Casa Central (sucursal_id=3) ← STOCK del CSV
                        StockSucursal.objects.create(
                            producto=producto,
                            sucursal=suc_central,
                            stock_inicial=stock_central,
                            cantidad=stock_central,
                        )
                        stats['stock_suc3'] += 1

                        # Yerba Buena (sucursal_id=4) ← STKSUC1 del CSV
                        StockSucursal.objects.create(
                            producto=producto,
                            sucursal=suc_yb,
                            stock_inicial=stock_yb,
                            cantidad=stock_yb,
                        )
                        stats['stock_suc4'] += 1

                    except Exception as e:
                        stats['errores'] += 1
                        self.stderr.write(self.style.ERROR(
                            f'  ERROR COD={codigo_legacy}: {e}'
                        ))

                    # Progreso cada 1000 registros
                    if stats['total'] % 1000 == 0:
                        self.stdout.write(f'  ... procesados {stats["total"]} productos')

                if dry_run:
                    transaction.savepoint_rollback(sid)
                    self.stdout.write(self.style.WARNING(
                        '\n  SIMULACION: Todos los cambios revertidos'
                    ))

        # ---------------------------------------------------------------
        # 7. Reporte final
        # ---------------------------------------------------------------
        self.stdout.write(self.style.SUCCESS('\n=== RESUMEN MIGRACION PRODUCTOS ==='))
        self.stdout.write(f'  Total procesados:      {stats["total"]}')
        self.stdout.write(f'  Creados:               {stats["creados"]}')
        self.stdout.write(f'  Errores:               {stats["errores"]}')
        self.stdout.write(f'  Sin proveedor match:   {stats["sin_proveedor"]}')
        self.stdout.write(f'  Sin marca:             {stats["sin_marca"]}')
        self.stdout.write(f'  StockSucursal suc=3:   {stats["stock_suc3"]}')
        self.stdout.write(f'  StockSucursal suc=4:   {stats["stock_suc4"]}')
        self.stdout.write(f'  Stocks negativos:      {stats["stock_negativos"]}')

        if proveedores_no_encontrados:
            self.stdout.write(self.style.WARNING(
                f'\n  Proveedores no encontrados ({len(proveedores_no_encontrados)}):'
            ))
            for nombre, count in proveedores_no_encontrados.most_common(20):
                self.stdout.write(f'    - {nombre} ({count} productos)')
