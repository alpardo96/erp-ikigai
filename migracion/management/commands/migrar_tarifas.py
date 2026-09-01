import os
import csv
from decimal import Decimal
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from facturacion.models import TarifaEstudio
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Migra tarifas de estudio desde un archivo CSV heredado'

    def add_arguments(self, parser):
        parser.add_argument(
            '--empresa', 
            type=int, 
            required=True, 
            help='ID de la Empresa destino'
        )
        parser.add_argument(
            '--archivo', 
            type=str, 
            required=True, 
            help='Ruta absoluta al archivo CSV'
        )

    def handle(self, *args, **options):
        empresa_id_target = options['empresa']
        csv_path = options['archivo']
        
        self.stdout.write(f"[{datetime.now()}] Iniciando importación desde {csv_path}")

        if not os.path.exists(csv_path):
            raise CommandError(f"ERROR: No se encontró el archivo {csv_path}")

        User = get_user_model()
        valid_users = set(User.objects.values_list('id', flat=True))

        try:
            with transaction.atomic():
                with open(csv_path, newline='', encoding='utf-8-sig') as csvfile:
                    reader = csv.DictReader(csvfile, delimiter=';')
                    
                    created_count = 0
                    for row in reader:
                        # Filtrar por empresa_id objetivo (si el csv no tiene empresa_id, se asume la ingresada)
                        empresa_id_val = row.get('empresa_id')
                        if empresa_id_val and int(empresa_id_val) != empresa_id_target:
                            continue 
                        
                        # Limpieza de valores numéricos
                        tarifa_f_str = row.get('tarifa_f', '0').replace(',', '.') if row.get('tarifa_f') else '0'
                        tarifa_p_str = row.get('tarifa_p', '0').replace(',', '.') if row.get('tarifa_p') else '0'
                        
                        # Booleanos
                        # Si 'activo' viene vacío en el CSV, asumimos True (default del modelo)
                        activo_val = str(row.get('activo', '')).strip().lower()
                        if activo_val == '':
                            activo = True
                        else:
                            activo = activo_val in ['t', 'true', '1', 'v', 'verdadero', 'y', 'yes']

                        cliente_id = int(row['cliente_id']) if row.get('cliente_id') else None
                        producto_id = int(row['producto_id']) if row.get('producto_id') else None
                        cuenta_id = int(row['cuenta_id']) if row.get('cuenta_id') else None

                        if not cliente_id or not producto_id:
                            self.stdout.write(self.style.WARNING(f"Fila sin cliente o producto, omitiendo: {row}"))
                            continue

                        # Creación de la instancia sin autoincrementales
                        tarifa = TarifaEstudio(
                            empresa_id=empresa_id_target,
                            cliente_id=cliente_id,
                            producto_id=producto_id,
                            cuenta_id=cuenta_id,
                            tarifa_f=Decimal(tarifa_f_str),
                            tarifa_p=Decimal(tarifa_p_str),
                            activo=activo
                        )
                        
                        if row.get('creado_por_id') and int(row['creado_por_id']) in valid_users:
                            tarifa.creado_por_id = int(row['creado_por_id'])
                        if row.get('modificado_por_id') and int(row['modificado_por_id']) in valid_users:
                            tarifa.modificado_por_id = int(row['modificado_por_id'])
                            
                        tarifa.save()
                        created_count += 1
                        
            self.stdout.write(self.style.SUCCESS(f"Importación exitosa. Se procesaron {created_count} tarifas de estudio."))
            
        except Exception as e:
            raise CommandError(f"ERROR durante la importación: {e}")
