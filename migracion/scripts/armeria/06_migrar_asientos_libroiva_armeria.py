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

from empresas.models import Empresa, Ejercicio
from contable.models import Asiento, AsientoLinea, Cuenta, LibroIvaCompras, LibroIvaVentas, LibroIvaAlic
from facturacion.models import ClienteProveedor
from django.contrib.auth import get_user_model

User = get_user_model()

def parse_decimal(value):
    if value is None: return Decimal('0.00')
    try: return Decimal(str(value))
    except: return Decimal('0.00')

def run():
    print("=== FASE 6: ASIENTOS CONTABLES Y LIBRO IVA DIGITAL (EJERCICIO 2026) ===")
    dir_balance = r'D:\jm_soft\net_balances\eje_255'
    
    empresa = Empresa.objects.get(id=1)
    ejercicio = Ejercicio.objects.get(id=1)
    user = User.objects.get(username='ikigai')
    
    cuentas_validas = set(Cuenta.objects.filter(empresa=empresa).values_list('id', flat=True))
    default_cuenta = list(cuentas_validas)[0] if cuentas_validas else None
    
    clientes_validos = set(ClienteProveedor.objects.filter(empresa=empresa).values_list('codigo_id', flat=True))
    default_cliente = list(clientes_validos)[0] if clientes_validos else None

    # 1. Asientos Encabezados (asto_enc.dbf)
    asto_enc_dbf = os.path.join(dir_balance, 'asto_enc.dbf')
    asientos_to_create = []
    if os.path.exists(asto_enc_dbf):
        table_asto = DBF(asto_enc_dbf, ignore_missing_memofile=True, encoding='latin1')
        for row in table_asto:
            id_asto = row.get('ID_ASTO')
            if not id_asto: continue
            
            fecha = row.get('FECHA') or ejercicio.inicio
            numero = int(row.get('NUMERO') or id_asto)
            concepto = str(row.get('CONCEPTO', '')).strip()[:200] or "ASIENTO CONTABLE"
            monto = parse_decimal(row.get('DEBE'))
            if monto == Decimal('0.00'):
                monto = parse_decimal(row.get('HABER'))

            asientos_to_create.append(Asiento(
                asiento_id=id_asto,
                empresa=empresa,
                ejercicio=ejercicio,
                numero_diario=numero,
                fecha=fecha,
                concepto=concepto,
                condic=row.get('CONDIC', 1),
                monto=monto,
                modulo=row.get('MODULO', 1) or 1,
                anulado=False,
                creado_por=user,
                modificado_por=user
            ))
            
        Asiento.objects.bulk_create(asientos_to_create, ignore_conflicts=True, batch_size=1000)
        print(f"OK: {len(asientos_to_create)} Asientos Encabezados procesados.")

    # 2. Asientos Detalles (asto_mov.dbf)
    asto_mov_dbf = os.path.join(dir_balance, 'asto_mov.dbf')
    if os.path.exists(asto_mov_dbf):
        table_mov = DBF(asto_mov_dbf, ignore_missing_memofile=True, encoding='latin1')
        valid_astos = set(Asiento.objects.filter(empresa=empresa).values_list('asiento_id', flat=True))
        items_to_create = []
        
        orden_idx = 1
        for row in table_mov:
            id_asto = row.get('ID_ASTO')
            if id_asto not in valid_astos: continue
            
            cta_id = row.get('ID_CTA')
            if cta_id not in cuentas_validas:
                cta_id = default_cuenta
                
            debe_raw = parse_decimal(row.get('DEBE'))
            haber_raw = parse_decimal(row.get('HABER'))

            # Normalizar signos contables (un debe negativo pasa a haber positivo y viceversa)
            if debe_raw < 0:
                haber_raw += abs(debe_raw)
                debe_raw = Decimal('0.00')

            if haber_raw < 0:
                debe_raw += abs(haber_raw)
                haber_raw = Decimal('0.00')

            # Respetar constraint debe_xor_haber (no ambos > 0 simultáneamente)
            if debe_raw > 0 and haber_raw > 0:
                if debe_raw >= haber_raw:
                    debe_raw -= haber_raw
                    haber_raw = Decimal('0.00')
                else:
                    haber_raw -= debe_raw
                    debe_raw = Decimal('0.00')
            
            items_to_create.append(AsientoLinea(
                asiento_id=id_asto,
                orden=int(row.get('ORDEN') or orden_idx),
                cuenta_id=cta_id,
                leyenda=str(row.get('CONCEPTO', ''))[:200],
                debe=debe_raw,
                haber=haber_raw
            ))
            orden_idx += 1
            
        AsientoLinea.objects.bulk_create(items_to_create, ignore_conflicts=True, batch_size=2000)
        print(f"OK: {len(items_to_create)} Movimientos de Asiento procesados.")

    # 3. Libro IVA Digital (lib_iva.dbf)
    lib_iva_dbf = os.path.join(dir_balance, 'lib_iva.dbf')
    if os.path.exists(lib_iva_dbf):
        table_iva = DBF(lib_iva_dbf, ignore_missing_memofile=True, encoding='latin1')
        compras_to_create = []
        ventas_to_create = []
        procesados_compras = set()
        procesados_ventas = set()

        for row in table_iva:
            asiento_id = row.get('ID_ASTO')
            if not asiento_id: continue
                
            c_v = str(row.get('C_V', '')).strip().upper()
            if c_v == 'C' and asiento_id in procesados_compras: continue
            if c_v == 'V' and asiento_id in procesados_ventas: continue

            entidad_id = row.get('ID_COD')
            if not entidad_id or entidad_id not in clientes_validos:
                entidad_id = default_cliente

            f_doc = row.get('F_DOC')
            cuit = str(f_doc).strip() if f_doc else ''

            otros = (parse_decimal(row.get('ITC')) + parse_decimal(row.get('IMP_INT')) + 
                     parse_decimal(row.get('RET_IVA')) + parse_decimal(row.get('RET_GCIA')) + 
                     parse_decimal(row.get('RET_SUSS')) + parse_decimal(row.get('RET_IB')) + 
                     parse_decimal(row.get('IB_CBA')) + parse_decimal(row.get('SIRCREB')) + 
                     parse_decimal(row.get('RET_MUN')))

            codiva = str(row.get('COD_CITI', '')).strip()
            if not codiva:
                tipo = str(row.get('TIPO', '')).strip()
                if tipo == 'FA': codiva = '001'
                elif tipo == 'FB': codiva = '006'
                elif tipo == 'CA': codiva = '003'
                elif tipo == 'CB': codiva = '008'
                else: codiva = '000'

            base_data = {
                'empresa': empresa,
                'asiento_id': asiento_id,
                'fecha': row.get('FECHA') or datetime.today().date(),
                'periodo': str(row.get('MESANO', '')).strip(),
                'clienteproveedor_id': entidad_id,
                'codiva': codiva,
                'punto': int(row.get('PUNTO') or 0),
                'numero': int(row.get('NUMERO') or 0),
                'cuit': cuit[:11],
                'cae': str(row.get('CAE', '')).strip(),
                'neto_gravado': parse_decimal(row.get('NETO')),
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

        LibroIvaCompras.objects.bulk_create(compras_to_create, batch_size=1000)
        print(f"OK: {len(compras_to_create)} registros en Libro IVA Compras.")
        
        LibroIvaVentas.objects.bulk_create(ventas_to_create, batch_size=1000)
        print(f"OK: {len(ventas_to_create)} registros en Libro IVA Ventas.")

        # 4. Alícuotas de Libro IVA (lib_iva_alic.dbf)
        lib_iva_alic_dbf = os.path.join(dir_balance, 'lib_iva_alic.dbf')
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
                    computable=parse_decimal(row.get('CPTABLE')),
                    codiva=str(row.get('COD_ALIC', '')).strip()
                ))

            LibroIvaAlic.objects.bulk_create(alic_to_create, batch_size=2000)
            print(f"OK: {len(alic_to_create)} Alícuotas de IVA procesadas.")

    print("Fase 6 completada con éxito.")

if __name__ == '__main__':
    run()
