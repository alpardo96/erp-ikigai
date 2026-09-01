import os
import csv
from decimal import Decimal
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from facturacion.models import ClienteProveedor, Jurisdiccion
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Migra clientes y proveedores desde un archivo CSV heredado'

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
        valid_jurisdicciones = set(Jurisdiccion.objects.values_list('id', flat=True))
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
                        saldo_inicial_str = row['saldo_inicial'].replace(',', '.') if row.get('saldo_inicial') else '0'
                        saldo_str = row['saldo'].replace(',', '.') if row.get('saldo') else '0'
                        objetivo_mensual_str = row['objetivo_mensual'].replace(',', '.') if row.get('objetivo_mensual') else '0'
                        limite_str = row['limite'].replace(',', '.') if row.get('limite') else '0'
                        
                        # Booleanos
                        usa_orden_compra = str(row.get('usa_orden_compra', '')).strip().lower() in ['t', 'true', '1', 'v', 'verdadero']
                        
                        # Enteros / Claves Foráneas
                        cta_pat = int(row['cta_pat']) if row.get('cta_pat') else 0
                        cta_res = int(row['cta_res']) if row.get('cta_res') else 0
                        
                        jurisdiccion_id = int(row['jurisdiccion_id']) if row.get('jurisdiccion_id') else None
                        if jurisdiccion_id not in valid_jurisdicciones:
                            jurisdiccion_id = None
                            
                        tipo_entidad = int(row['tipo_entidad']) if row.get('tipo_entidad') else 1
                        
                        fecha_nac_str = row.get('fecha_nacimiento')
                        fecha_nacimiento = None
                        if fecha_nac_str:
                            try:
                                fecha_nacimiento = datetime.strptime(fecha_nac_str, '%Y-%m-%d').date()
                            except ValueError:
                                try:
                                    fecha_nacimiento = datetime.strptime(fecha_nac_str, '%d/%m/%Y').date()
                                except ValueError:
                                    pass
                        
                        # Creación de la instancia
                        cliente = ClienteProveedor(
                            razon_social=row['razon_social'],
                            tipo_documento=row.get('tipo_documento') or "80",
                            cuit=row.get('cuit') or None,
                            tipo_entidad=tipo_entidad,
                            domicilio=row.get('domicilio') or None,
                            codigo_postal=row.get('codigo_postal') or None,
                            localidad=row.get('localidad') or None,
                            contacto=row.get('contacto') or None,
                            telefono=row.get('telefono') or None,
                            correo=row.get('correo') or None,
                            condicion_iva=row.get('condicion_iva') or "CONSUMIDOR FINAL",
                            tipo_iibb=row.get('tipo_iibb') or "LOCAL",
                            saldo_inicial=Decimal(saldo_inicial_str),
                            saldo=Decimal(saldo_str),
                            objetivo_mensual=Decimal(objetivo_mensual_str),
                            clasificacion=row.get('clasificacion') or None,
                            observaciones=row.get('observaciones') or None,
                            jurisdiccion_id=jurisdiccion_id,
                            fecha_nacimiento=fecha_nacimiento,
                            limite=Decimal(limite_str),
                            cta_pat=cta_pat,
                            cta_res=cta_res,
                            empresa_id=empresa_id_target,
                            usa_orden_compra=usa_orden_compra,
                            codigo_anterior=row.get('codigo_anterior') or None
                        )
                        
                        if row.get('creado_por_id') and int(row['creado_por_id']) in valid_users:
                            cliente.creado_por_id = int(row['creado_por_id'])
                        if row.get('modificado_por_id') and int(row['modificado_por_id']) in valid_users:
                            cliente.modificado_por_id = int(row['modificado_por_id'])
                            
                        cliente.save()
                        created_count += 1
                        
            self.stdout.write(self.style.SUCCESS(f"Importación exitosa. Se procesaron {created_count} clientes/proveedores."))
            
        except Exception as e:
            raise CommandError(f"ERROR durante la importación: {e}")
