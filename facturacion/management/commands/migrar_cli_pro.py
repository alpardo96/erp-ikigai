# -*- coding: utf-8 -*-
"""
Management Command: migrar_cli_pro
===================================
Migra los datos del archivo CSV legacy VSFox (cli_pro.csv) hacia la tabla
ClienteProveedor del ERP Ikigai 2.

Empresa destino: Armería Armar SAS (empresa_id=2)

Decisiones de diseño:
- INSC_IVA: 1→RI, 2→MONO, 3→EXENTO, 4→CF, 0→CF
- T_DOC vacío → '99' (Sin Identificar)
- Provincia texto → FK Jurisdicción por nombre normalizado
- El CODIGO legacy se pierde como PK; se genera un mapeo para vincular productos
"""

import csv
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from facturacion.models import ClienteProveedor, Jurisdiccion
from empresas.models import Empresa


class Command(BaseCommand):
    help = 'Migra clientes/proveedores desde Modelos/cli_pro.csv a la DB (empresa_id=2)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula la migración sin escribir en la DB',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        self.stdout.write(self.style.WARNING(
            '=== MIGRACION CLI_PRO.CSV -> ClienteProveedor ===\n'
            f'Modo: {"SIMULACION (dry-run)" if dry_run else "EJECUCION REAL"}'
        ))

        # ---------------------------------------------------------------
        # 1. Validar que exista la empresa destino
        # ---------------------------------------------------------------
        try:
            empresa = Empresa.objects.get(pk=2)
        except Empresa.DoesNotExist:
            self.stderr.write(self.style.ERROR('ERROR: No existe empresa_id=2'))
            return

        # ---------------------------------------------------------------
        # 2. Construir mapeo de Provincia (texto) → FK Jurisdicción
        #    Se normaliza el texto para hacer match fuzzy
        # ---------------------------------------------------------------
        jurisdicciones = {j.nombre.upper(): j for j in Jurisdiccion.objects.all()}
        # Alias comunes del legacy
        alias_jurisdiccion = {
            'BS AS': 'BUENOS AIRES',
            'CAPITAL FEDERAL': 'CIUDAD AUTONOMA DE BUENOS AIRES',
            'CIUDAD AUTÓNOMA DE B': 'CIUDAD AUTONOMA DE BUENOS AIRES',
            'CASTAMARCA': 'CATAMARCA',
            'S. ESTERO': 'SANTIAGO DEL ESTERO',
            'STGO DEL ESTERO': 'SANTIAGO DEL ESTERO',
            'SGO. DEL ESTERO': 'SANTIAGO DEL ESTERO',
            'SIMOCA': 'TUCUMAN',           # Simoca es localidad de Tucumán
            'TUCUMÁN': 'TUCUMAN',           # Acento
            'F': None,                      # Dato basura, se ignora
        }

        def resolver_jurisdiccion(provincia_texto):
            """Resuelve el texto de provincia a una FK Jurisdicción."""
            if not provincia_texto:
                return None
            prov = provincia_texto.strip().upper()
            # Primero verificar alias
            if prov in alias_jurisdiccion:
                mapped = alias_jurisdiccion[prov]
                if mapped is None:
                    return None
                prov = mapped
            # Buscar en jurisdicciones cargadas
            if prov in jurisdicciones:
                return jurisdicciones[prov]
            # Intento parcial (primeras 10 letras)
            for nombre, juris in jurisdicciones.items():
                if nombre.startswith(prov[:10]):
                    return juris
            return None

        # ---------------------------------------------------------------
        # 3. Mapeo de INSC_IVA → condicion_iva del modelo
        # ---------------------------------------------------------------
        MAPEO_IVA = {
            '1': 'RESPONSABLE INSCRIPTO',
            '2': 'MONOTRIBUTO',
            '3': 'EXENTO',
            '4': 'CONSUMIDOR FINAL',
            '0': 'CONSUMIDOR FINAL',      # Aprobado por el usuario
        }

        # ---------------------------------------------------------------
        # 4. Mapeo de T_DOC → tipo_documento del modelo
        # ---------------------------------------------------------------
        DOCS_VALIDOS = {'80', '86', '96', '99'}

        def resolver_tipo_doc(t_doc_csv):
            """Resuelve el tipo de documento del CSV al modelo."""
            td = t_doc_csv.strip() if t_doc_csv else ''
            if td in DOCS_VALIDOS:
                return td
            return '99'  # Sin identificar si está vacío o es inválido

        # ---------------------------------------------------------------
        # 5. Leer CSV y migrar
        # ---------------------------------------------------------------
        csv_path = os.path.join('Modelos', 'cli_pro.csv')
        if not os.path.exists(csv_path):
            self.stderr.write(self.style.ERROR(f'ERROR: No se encuentra {csv_path}'))
            return

        # Contadores para estadísticas
        stats = {
            'total': 0,
            'creados': 0,
            'existentes': 0,
            'errores': 0,
            'clientes': 0,
            'proveedores': 0,
            'jurisdiccion_no_resuelta': 0,
        }

        # Diccionario de mapeo legacy_codigo → nuevo_pk (para vincular productos luego)
        mapeo_legacy = {}

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')

            # Usamos transaction.atomic para garantizar atomicidad
            with transaction.atomic():
                # Si es dry-run, creamos un savepoint para revertir al final
                if dry_run:
                    sid = transaction.savepoint()

                for row in reader:
                    stats['total'] += 1
                    codigo_legacy = row.get('CODIGO', '').strip()
                    razon_social = row.get('DETALLE', '').strip()

                    # Saltar filas sin razón social
                    if not razon_social:
                        stats['errores'] += 1
                        self.stdout.write(self.style.WARNING(
                            f'  SKIP: Fila sin razón social (CODIGO={codigo_legacy})'
                        ))
                        continue

                    # Resolver campos
                    cuit = row.get('CUIT', '').strip() or None
                    tipo_entidad = int(row.get('CLI_PRO', '1').strip() or 1)
                    condicion_iva = MAPEO_IVA.get(
                        row.get('INSC_IVA', '0').strip(),
                        'CONSUMIDOR FINAL'
                    )
                    tipo_documento = resolver_tipo_doc(row.get('T_DOC', ''))
                    domicilio = row.get('DOMICILIO', '').strip() or None
                    codigo_postal = row.get('CPOSTAL', '').strip() or None
                    # Descartar código postal '0'
                    if codigo_postal == '0':
                        codigo_postal = None
                    localidad = row.get('LOCALIDAD', '').strip() or None
                    provincia_texto = row.get('PROVINCIA', '').strip()
                    jurisdiccion = resolver_jurisdiccion(provincia_texto)
                    if provincia_texto and not jurisdiccion:
                        stats['jurisdiccion_no_resuelta'] += 1
                    contacto = row.get('CONTACTO', '').strip() or None
                    telefono = row.get('TELEFONO', '').strip() or None
                    correo_raw = row.get('CORREO', '').strip() or None
                    # Validación básica de correo: debe tener @
                    correo = correo_raw if correo_raw and '@' in correo_raw else None

                    # Campos numéricos con manejo de errores
                    try:
                        saldo = float(row.get('SALDO', '0').strip() or 0)
                    except (ValueError, TypeError):
                        saldo = 0
                    try:
                        saldo_inicial = float(row.get('SI', '0').strip() or 0)
                    except (ValueError, TypeError):
                        saldo_inicial = 0
                    try:
                        limite = float(row.get('LIMITE', '0').strip() or 0)
                    except (ValueError, TypeError):
                        limite = 0
                    try:
                        cta_pat = int(row.get('CTA_PAT', '0').strip() or 0)
                    except (ValueError, TypeError):
                        cta_pat = 0
                    try:
                        cta_res = int(row.get('CTA_RES', '0').strip() or 0)
                    except (ValueError, TypeError):
                        cta_res = 0

                    try:
                        # Crear el registro
                        cp = ClienteProveedor(
                            razon_social=razon_social,
                            cuit=cuit,
                            tipo_entidad=tipo_entidad,
                            condicion_iva=condicion_iva,
                            tipo_documento=tipo_documento,
                            domicilio=domicilio,
                            codigo_postal=codigo_postal,
                            localidad=localidad,
                            jurisdiccion=jurisdiccion,
                            contacto=contacto,
                            telefono=telefono,
                            correo=correo,
                            saldo=saldo,
                            saldo_inicial=saldo_inicial,
                            limite=limite,
                            cta_pat=cta_pat,
                            cta_res=cta_res,
                            empresa=empresa,
                        )
                        cp.save()
                        mapeo_legacy[codigo_legacy] = cp.pk
                        stats['creados'] += 1

                        if tipo_entidad == 1:
                            stats['clientes'] += 1
                        else:
                            stats['proveedores'] += 1

                    except Exception as e:
                        stats['errores'] += 1
                        self.stderr.write(self.style.ERROR(
                            f'  ERROR en CODIGO={codigo_legacy}: {e}'
                        ))

                    # Progreso cada 2000 registros
                    if stats['total'] % 2000 == 0:
                        self.stdout.write(f'  ... procesados {stats["total"]} registros')

                # Si es dry-run, revertir todo
                if dry_run:
                    transaction.savepoint_rollback(sid)
                    self.stdout.write(self.style.WARNING('\n  SIMULACION: Todos los cambios revertidos'))

        # ---------------------------------------------------------------
        # 6. Guardar mapeo legacy → nuevo pk para uso posterior
        # ---------------------------------------------------------------
        if not dry_run:
            mapeo_path = os.path.join('scratch', 'mapeo_cli_pro.csv')
            os.makedirs('scratch', exist_ok=True)
            with open(mapeo_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(['CODIGO_LEGACY', 'NUEVO_PK'])
                for codigo, pk in mapeo_legacy.items():
                    writer.writerow([codigo, pk])
            self.stdout.write(f'\n  Mapeo guardado en: {mapeo_path}')

        # ---------------------------------------------------------------
        # 7. Reporte final
        # ---------------------------------------------------------------
        self.stdout.write(self.style.SUCCESS(f'\n=== RESUMEN MIGRACION CLI_PRO ==='))
        self.stdout.write(f'  Total procesados:       {stats["total"]}')
        self.stdout.write(f'  Creados:                {stats["creados"]}')
        self.stdout.write(f'    - Clientes:           {stats["clientes"]}')
        self.stdout.write(f'    - Proveedores:        {stats["proveedores"]}')
        self.stdout.write(f'  Ya existentes:          {stats["existentes"]}')
        self.stdout.write(f'  Errores:                {stats["errores"]}')
        self.stdout.write(f'  Jurisdiccion sin match: {stats["jurisdiccion_no_resuelta"]}')
