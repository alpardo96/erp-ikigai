import os
import sys
import django
from decimal import Decimal
from datetime import datetime
from dbfread import DBF
import pathlib

# Configurar el entorno de Django
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from empresas.models import Empresa
from contable.models import LibroIvaCompras, LibroIvaVentas, LibroIvaAlic
from facturacion.models import ClienteProveedor

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

def run():
    print("Iniciando Migración Libro IVA Digital - Compras, Ventas y Alícuotas (Estudio)...")
    dir_path = r'D:\OneDrive\Escritorio\Migracion\Estudio\eje_272'
    
    empresa = Empresa.objects.get(id=1)
    
    # Cache valid clientes
    clientes_validos = set(ClienteProveedor.objects.filter(empresa=empresa).values_list('codigo_id', flat=True))
    default_cliente = list(clientes_validos)[0] if clientes_validos else None

    lib_iva_dbf = os.path.join(dir_path, 'lib_iva.dbf')
    if not os.path.exists(lib_iva_dbf):
        print(f"No se encontró {lib_iva_dbf}")
        return

    table_iva = DBF(lib_iva_dbf, ignore_missing_memofile=True, encoding='latin1')
    
    compras_to_create = []
    ventas_to_create = []

    procesados_compras = set()
    procesados_ventas = set()

    for row in table_iva:
        asiento_id = row.get('ID_ASTO')
        if not asiento_id:
            continue
            
        c_v = str(row.get('C_V', '')).strip().upper()
        
        if c_v == 'C' and asiento_id in procesados_compras:
            continue
        if c_v == 'V' and asiento_id in procesados_ventas:
            continue

        entidad_id = row.get('ID_COD')
        if not entidad_id or entidad_id not in clientes_validos:
            entidad_id = default_cliente

        f_doc = row.get('F_DOC') or row.get('CUIT')
        cuit = str(f_doc).strip() if f_doc else ''

        otros = (parse_decimal(row.get('ITC')) + parse_decimal(row.get('IMP_INT')) + 
                 parse_decimal(row.get('RET_IVA')) + parse_decimal(row.get('RET_GCIA')) + 
                 parse_decimal(row.get('RET_SUSS')) + parse_decimal(row.get('RET_IB')) + 
                 parse_decimal(row.get('IB_CBA')) + parse_decimal(row.get('SIRCREB')) + 
                 parse_decimal(row.get('RET_MUN')))

        codiva = str(row.get('COD_CITI', '')).strip()
        if not codiva:
            tipo = str(row.get('TIPO', '')).strip().upper()
            if tipo in ['FA', 'FC_A']: codiva = '001'
            elif tipo in ['ND', 'ND_A']: codiva = '002'
            elif tipo in ['NC', 'NC_A']: codiva = '003'
            elif tipo in ['FB', 'FC_B']: codiva = '006'
            elif tipo in ['FC', 'FC_C']: codiva = '011'
            elif tipo == 'SC': codiva = 'PRE'
            elif tipo == 'RT': codiva = '090'
            else: codiva = str(row.get('T_DOC', '000')).strip()

        fecha = row.get('FECHA') or datetime.today().date()
        mesano = str(row.get('MESANO', '')).strip()
        periodo = mesano if len(mesano) == 6 else fecha.strftime('%Y%m')

        base_data = {
            'empresa': empresa,
            'asiento_id': asiento_id,
            'fecha': fecha,
            'periodo': periodo,
            'clienteproveedor_id': entidad_id,
            'codiva': codiva[:3] if len(codiva) > 3 and codiva.isdigit() else codiva[:3],
            'punto': safe_int(row.get('PUNTO') or row.get('PTO_R'), 0),
            'numero': safe_int(row.get('NUMERO') or row.get('NRO_R'), 0),
            'cuit': cuit[:11],
            'cae': str(row.get('CAE', '')).strip()[:20],
            'neto_gravado': parse_decimal(row.get('NETO_M') or row.get('NETO')),
            'exento': parse_decimal(row.get('EXENTO')),
            'no_gravado': parse_decimal(row.get('NO_GRAV')),
            'iva_total': parse_decimal(row.get('IVA')),
            'otros': otros,
            'total': parse_decimal(row.get('TOTAL'))
        }

        if c_v == 'C':
            compras_to_create.append(LibroIvaCompras(**base_data))
            procesados_compras.add(asiento_id)
        elif c_v == 'V':
            base_data['vto_cae'] = row.get('VTO_CAE')
            base_data['codigo_qr'] = str(row.get('COD_QR', '')).strip()
            ventas_to_create.append(LibroIvaVentas(**base_data))
            procesados_ventas.add(asiento_id)

    print(f"Insertando {len(compras_to_create)} registros en Libro IVA Compras...")
    LibroIvaCompras.objects.bulk_create(compras_to_create, ignore_conflicts=True, batch_size=1000)
    print("OK")
    
    print(f"Insertando {len(ventas_to_create)} registros en Libro IVA Ventas...")
    LibroIvaVentas.objects.bulk_create(ventas_to_create, ignore_conflicts=True, batch_size=1000)
    print("OK")

    # ALICUOTAS (lib_iva_alic.dbf)
    lib_iva_alic_dbf = os.path.join(dir_path, 'lib_iva_alic.dbf')
    if os.path.exists(lib_iva_alic_dbf):
        table_alic = DBF(lib_iva_alic_dbf, ignore_missing_memofile=True, encoding='latin1')
        alic_to_create = []
        for row in table_alic:
            asiento_id = row.get('ID_ASTO')
            c_v = str(row.get('C_V', '')).strip().upper()
            
            if c_v == 'C' and asiento_id not in procesados_compras: continue
            if c_v == 'V' and asiento_id not in procesados_ventas: continue

            alic_to_create.append(LibroIvaAlic(
                asiento_id=asiento_id,
                c_v=c_v,
                neto=parse_decimal(row.get('NETO')),
                alicuota=parse_decimal(row.get('ALICUOTA')),
                iva=parse_decimal(row.get('IVA')),
                computable=parse_decimal(row.get('CPTABLE') or row.get('IVA')),
                codiva=str(row.get('COD_ALIC', '')).strip()[:4]
            ))

        print(f"Insertando {len(alic_to_create)} alícuotas en LibroIvaAlic...")
        LibroIvaAlic.objects.bulk_create(alic_to_create, ignore_conflicts=True, batch_size=2000)
        print("OK")

    print("Fase 7 (Libro IVA Digital) completada con éxito.")

if __name__ == '__main__':
    run()
