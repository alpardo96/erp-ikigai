import os
import csv
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from contable.models import Cuenta
from empresas.models import Empresa

def clean_int(val):
    if not val:
        return 0
    try:
        return int(val)
    except ValueError:
        return 0

class Command(BaseCommand):
    help = 'Migra el plan de cuentas desde un archivo CSV heredado'

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
        empresa_id = options['empresa']
        csv_path = options['archivo']

        self.stdout.write(f"[{datetime.now()}] Iniciando importación desde {csv_path}")
        
        if not os.path.exists(csv_path):
            raise CommandError(f"ERROR: No se encontró el archivo {csv_path}")

        try:
            empresa = Empresa.objects.get(id=empresa_id)
        except Empresa.DoesNotExist:
            raise CommandError(f"ERROR: La Empresa con ID={empresa_id} no existe en la base de datos.")

        try:
            with transaction.atomic():
                with open(csv_path, 'r', encoding='utf-8-sig', errors='replace') as f:
                    # 'utf-8-sig' handles BOM automatically, errors='replace' handles minor encoding issues
                    reader = csv.DictReader(f, delimiter=';')
                    rows = list(reader)
                    
                    cuentas_creadas = 0
                    
                    # Pasada 1: Crear las cuentas sin establecer relaciones de jerarquía
                    self.stdout.write("Fase 1: Creando cuentas...")
                    for row in rows:
                        # Depending on the CSV version (cuentas.csv vs cble_cuentas_estudio.csv)
                        codigo_str = row.get('codigo') or row.get('cuenta_id')
                        codigo = clean_int(codigo_str)
                        if not codigo:
                            continue # Saltamos filas sin código válido
                            
                        jerarquia = row.get('jerarquia') or row.get('Jerarquia') or ''
                        cuenta_nombre = row.get('cuenta') or row.get('Imputacion Contable') or ''
                        imputable_str = row.get('imputable') or row.get('Imputable')
                        tipo_str = row.get('tipo') or row.get('Tipo') or 'A'
                        
                        jerarquia = jerarquia.strip()
                        cuenta_nombre = cuenta_nombre.strip().upper()
                        tipo_str = tipo_str.strip().upper()
                        imputable = clean_int(imputable_str)

                        cuenta_obj = Cuenta.objects.filter(empresa=empresa, codigo=codigo).first()
                        if not cuenta_obj:
                            Cuenta.objects.create(
                                empresa=empresa,
                                codigo=codigo,
                                jerarquia=jerarquia,
                                cuenta=cuenta_nombre,
                                imputable=imputable,
                                tipo=tipo_str,
                                rg_830=clean_int(row.get('rg_830')) if row.get('rg_830') else None,
                                id_pre=clean_int(row.get('id_pre')) if row.get('id_pre') else None,
                                id_bce=clean_int(row.get('id_bce')) if row.get('id_bce') else None,
                                id_ec=clean_int(row.get('id_ec')) if row.get('id_ec') else None,
                                id_fc=clean_int(row.get('id_fc')) if row.get('id_fc') else None,
                            )
                            cuentas_creadas += 1
                    
                    self.stdout.write(self.style.SUCCESS(f"Cuentas creadas/validadas: {cuentas_creadas} / {len(rows)}"))

                    # Pasada 2: Asignar jerarquías (sumariza_id) mapeando el ID viejo al nuevo
                    self.stdout.write("Fase 2: Asignando relaciones jerárquicas...")
                    relaciones_asignadas = 0
                    for row in rows:
                        sumariza_str = row.get('sumariza_id') or row.get('sumariza')
                        sumariza_id_legacy = clean_int(sumariza_str)
                        
                        if sumariza_id_legacy > 0:
                            codigo_str = row.get('codigo') or row.get('cuenta_id')
                            codigo = clean_int(codigo_str)
                            
                            try:
                                cuenta_hija = Cuenta.objects.get(empresa=empresa, codigo=codigo)
                                cuenta_padre = Cuenta.objects.get(empresa=empresa, codigo=sumariza_id_legacy)
                                
                                # Django asigna automáticamente el ID nuevo de Postgres al Foreign Key "sumariza"
                                cuenta_hija.sumariza = cuenta_padre
                                cuenta_hija.save(update_fields=['sumariza'])
                                relaciones_asignadas += 1
                            except Cuenta.DoesNotExist as e:
                                self.stdout.write(self.style.WARNING(f"Advertencia: Problema con la relación (hija cod:{codigo} -> padre cod:{sumariza_id_legacy}): {e}"))

                    self.stdout.write(self.style.SUCCESS(f"Relaciones asignadas: {relaciones_asignadas}"))
                
            self.stdout.write(self.style.SUCCESS(f"[{datetime.now()}] Importación de cuentas finalizada exitosamente."))

        except Exception as e:
            raise CommandError(f"ERROR durante la importación: {e}")
