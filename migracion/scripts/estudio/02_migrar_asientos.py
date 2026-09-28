import os
import sys
import django
from decimal import Decimal
from datetime import datetime
from dbfread import DBF

# Configurar el entorno de Django
import pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from empresas.models import Empresa, Sucursal, Ejercicio
from contable.models import Asiento, AsientoLinea, Cuenta
from facturacion.models import ClienteProveedor
from django.contrib.auth import get_user_model

User = get_user_model()

def parse_decimal(value):
    if value is None:
        return Decimal('0.00')
    return Decimal(str(value))

def safe_int(value, default=0):
    try:
        if not value: return default
        if isinstance(value, str):
            value = ''.join(c for c in value if c.isdigit())
        return int(value) if value else default
    except (ValueError, TypeError):
        return default

def resolver_usuario_id(id_usu):
    val = safe_int(id_usu, 1)
    if val == 2:
        return 3
    elif val == 4:
        return 4
    return 1

def run():
    print("Iniciando Fase 2: Bloque Contabilidad Core (Estudio)...")
    dir_path = r'D:\OneDrive\Escritorio\Migracion\Estudio\eje_272'
    
    empresa = Empresa.objects.get(id=1)
    sucursal = Sucursal.objects.get(id=1)
    user = User.objects.get(username='Ikigai')
    
    # Pre-cargar ejercicios de la empresa
    ejercicios = list(Ejercicio.objects.filter(empresa=empresa).order_by('inicio'))
    ejercicio_default = ejercicios[-1] if ejercicios else None

    def resolver_ejercicio(fecha_doc):
        if not fecha_doc:
            return ejercicio_default
        for ej in ejercicios:
            if ej.inicio <= fecha_doc <= ej.cierre:
                return ej
        return ejercicio_default

    # Pre-mapear ID_ASTO -> CAJA desde caja_diaria.dbf
    caja_por_asiento = {}
    caja_dbf = os.path.join(dir_path, 'caja_diaria.dbf')
    if os.path.exists(caja_dbf):
        t_caja = DBF(caja_dbf, ignore_missing_memofile=True, encoding='latin1')
        for r in t_caja:
            a = r.get('ID_ASTO')
            c = r.get('CAJA')
            if a and c:
                caja_por_asiento[a] = c

    # Pre-cargar IDs válidos
    cuentas_validas = set(Cuenta.objects.filter(empresa=empresa).values_list('id', flat=True))
    clipro_validos = set(ClienteProveedor.objects.filter(empresa=empresa).values_list('codigo_id', flat=True))

    # 1. Asiento de Apertura
    apertura_dbf = os.path.join(dir_path, 'apertura.dbf')
    if os.path.exists(apertura_dbf):
        table = DBF(apertura_dbf, ignore_missing_memofile=True, encoding='latin1')
        records = list(table)
        if records:
            ej_apertura = resolver_ejercicio(datetime(2026, 6, 1).date())
            asiento_apertura = Asiento.objects.create(
                asiento_id=16044,
                fecha=ej_apertura.inicio if ej_apertura else datetime(2026, 6, 1).date(),
                concepto="Asiento de Apertura Migrado",
                condic=5, # Apertura
                monto=0,
                modulo=1, # Manual
                anulado=False,
                empresa=empresa,
                sucursal=sucursal,
                ejercicio=ej_apertura,
                creado_por=user
            )
            
            lineas = []
            monto_total = Decimal('0.00')
            for i, row in enumerate(records):
                cta_id = row.get('ID_CTA') or row.get('CODIGO')
                if cta_id not in cuentas_validas:
                    continue
                    
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
                    cuenta_id=cta_id,
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
            asiento_id = row.get('ID_ASTO', 0)
            if not asiento_id or asiento_id == 0:
                continue
                
            fecha = row.get('FECHA')
            ej = resolver_ejercicio(fecha)
            
            cli_pro_id = row.get('CLI_PRO')
            if cli_pro_id not in clipro_validos:
                cli_pro_id = None
                
            caja_id = caja_por_asiento.get(asiento_id)
            usu_id = resolver_usuario_id(row.get('ID_USU'))

            asientos_to_create.append(Asiento(
                asiento_id=asiento_id,
                fecha=fecha or ej.inicio,
                concepto=str(row.get('CONCEPTO', ''))[:200],
                condic=int(row.get('CONDIC', 1) or 1),
                monto=parse_decimal(row.get('MONTO')),
                modulo=int(row.get('MODULO', 1) or 1),
                cli_pro_id=cli_pro_id,
                sesion_caja_id=None, # Se vincula en Fase 3 al crearse CajaSesion
                anulado=False,
                empresa=empresa,
                sucursal=sucursal,
                ejercicio=ej,
                creado_por_id=usu_id
            ))
            
        Asiento.objects.bulk_create(asientos_to_create, ignore_conflicts=True, batch_size=1000)
        print(f"OK {len(asientos_to_create)} cabeceras de asientos procesadas.")

    # 3. Líneas de Asientos
    asto_mov_dbf = os.path.join(dir_path, 'asto_mov.dbf')
    if os.path.exists(asto_mov_dbf):
        table = DBF(asto_mov_dbf, ignore_missing_memofile=True, encoding='latin1')
        lineas_to_create = []
        
        asientos_validos = set(Asiento.objects.filter(empresa=empresa).values_list('asiento_id', flat=True))
        
        for row in table:
            asiento_id = row.get('ID_ASTO')
            if asiento_id not in asientos_validos:
                continue
                
            cta_id = row.get('ID_CTA')
            if cta_id not in cuentas_validas:
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
                orden=int(row.get('ID_ASTO_MO', 1) or 1),
                cuenta_id=cta_id,
                leyenda=str(row.get('LEYENDA', ''))[:200],
                debe=debe,
                haber=haber
            ))
            
        AsientoLinea.objects.bulk_create(lineas_to_create, ignore_conflicts=True, batch_size=2000)
        print(f"OK {len(lineas_to_create)} líneas de asientos procesadas.")

    print("Fase 2 completada con éxito.")

if __name__ == '__main__':
    run()
