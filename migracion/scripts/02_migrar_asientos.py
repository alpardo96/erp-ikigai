import os
import sys
import django
from decimal import Decimal
from datetime import datetime
from dbfread import DBF

# Configurar el entorno de Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from empresas.models import Empresa, Sucursal, Ejercicio
from contable.models import Asiento, AsientoLinea
from django.contrib.auth import get_user_model

User = get_user_model()

def parse_decimal(value):
    if value is None:
        return Decimal('0.00')
    return Decimal(str(value))

def get_modulo_int(modulo_str):
    m = str(modulo_str).strip().upper()
    if 'VENTA' in m: return 2
    if 'COMPRA' in m: return 5
    if 'BANCO' in m or 'CAJA' in m or 'RECIBO' in m or 'ORD_PAGO' in m: return 6
    return 1

def run():
    print("Iniciando Fase 2: Bloque Contabilidad Core")
    dir_path = r'D:\OneDrive\Escritorio\Migracion\eje_272'
    
    empresa = Empresa.objects.get(id=1)
    sucursal = Sucursal.objects.get(id=1)
    ejercicio = Ejercicio.objects.get(id=1)
    user = User.objects.get(username='Ikigai')

    # 1. Asiento de Apertura
    apertura_dbf = os.path.join(dir_path, 'apertura.dbf')
    if os.path.exists(apertura_dbf):
        table = DBF(apertura_dbf, ignore_missing_memofile=True, encoding='latin1')
        records = list(table)
        if records:
            asiento_apertura = Asiento.objects.create(
                asiento_id=99999999,
                fecha=ejercicio.inicio,
                concepto="Asiento de Apertura Migrado",
                condic=5, # Apertura
                monto=0,
                modulo=1, # Manual
                anulado=False,
                empresa=empresa,
                sucursal=sucursal,
                ejercicio=ejercicio,
                creado_por=user
            )
            
            lineas = []
            monto_total = Decimal('0.00')
            for i, row in enumerate(records):
                debe = parse_decimal(row.get('DEBE'))
                haber = parse_decimal(row.get('HABER'))
                
                if debe < 0:
                    haber += abs(debe)
                    debe = Decimal('0.00')
                if haber < 0:
                    debe += abs(haber)
                    haber = Decimal('0.00')
                    
                if debe > 0 and haber > 0:
                    if debe > haber:
                        debe -= haber
                        haber = Decimal('0.00')
                    else:
                        haber -= debe
                        debe = Decimal('0.00')
                        
                if debe == 0 and haber == 0:
                    continue
                    
                lineas.append(AsientoLinea(
                    asiento=asiento_apertura,
                    orden=i+1,
                    cuenta_id=row.get('ID_CTA') or row.get('CODIGO'),
                    leyenda="Saldo Inicial",
                    debe=debe,
                    haber=haber
                ))
                monto_total += debe
                
            AsientoLinea.objects.bulk_create(lineas)
            asiento_apertura.monto = monto_total
            asiento_apertura.save()
            print(f"OK Asiento de apertura generado con {len(lineas)} líneas.")

    # 2. Cabecera Asientos
    asto_enc_dbf = os.path.join(dir_path, 'asto_enc.dbf')
    if os.path.exists(asto_enc_dbf):
        table = DBF(asto_enc_dbf, ignore_missing_memofile=True, encoding='latin1')
        asientos_to_create = []
        for row in table:
            if row.get('ID_ASTO', 0) == 0:
                continue
                
            fecha = row.get('FECHA')
            if not fecha:
                fecha = ejercicio.inicio
                
            cli_pro_id = row.get('CLI_PRO')
            if cli_pro_id == 0:
                cli_pro_id = None
                
            asientos_to_create.append(Asiento(
                asiento_id=row['ID_ASTO'],
                fecha=fecha,
                concepto=row.get('CONCEPTO', '')[:200],
                condic=row.get('CONDIC', 1),
                monto=parse_decimal(row.get('MONTO')),
                modulo=row.get('MODULO', 1),
                cli_pro_id=cli_pro_id,
                anulado=False, # En este DBF no hay campo anulado
                empresa=empresa,
                sucursal=sucursal,
                ejercicio=ejercicio,
                creado_por=user
            ))
            
        Asiento.objects.bulk_create(asientos_to_create, batch_size=1000)
        print(f"OK {len(asientos_to_create)} cabeceras de asientos procesadas.")

    # 3. Líneas de Asientos
    asto_mov_dbf = os.path.join(dir_path, 'asto_mov.dbf')
    if os.path.exists(asto_mov_dbf):
        table = DBF(asto_mov_dbf, ignore_missing_memofile=True, encoding='latin1')
        lineas_to_create = []
        
        # Guardamos en set los IDs validos de asientos para no romper FK
        asientos_validos = set(Asiento.objects.values_list('asiento_id', flat=True))
        
        for row in table:
            asiento_id = row.get('ID_ASTO')
            if asiento_id not in asientos_validos:
                continue
                
            debe = parse_decimal(row.get('DEBE'))
            haber = parse_decimal(row.get('HABER'))
            
            if debe < 0:
                haber += abs(debe)
                debe = Decimal('0.00')
            if haber < 0:
                debe += abs(haber)
                haber = Decimal('0.00')
            
            # Constraint DB debe_xor_haber
            if debe > 0 and haber > 0:
                # Si ambos tienen valor por algún error, nos quedamos con el neto
                if debe > haber:
                    debe -= haber
                    haber = Decimal('0.00')
                else:
                    haber -= debe
                    debe = Decimal('0.00')
                    
            if debe == 0 and haber == 0:
                continue
                
            lineas_to_create.append(AsientoLinea(
                asiento_id=asiento_id,
                orden=row.get('ID_ASTO_MO', 1),
                cuenta_id=row.get('ID_CTA'),
                leyenda=row.get('LEYENDA', '')[:200],
                debe=debe,
                haber=haber
            ))
            
        AsientoLinea.objects.bulk_create(lineas_to_create, batch_size=2000)
        print(f"OK {len(lineas_to_create)} líneas de asientos procesadas.")

    print("Fase 2 completada con éxito.")

if __name__ == '__main__':
    run()
