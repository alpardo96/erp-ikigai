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
from facturacion.models import Venta, Compra, TipoComprobante, ClienteProveedor, VentaAlicuotaIva, CompraAlicuota
from contable.models import Asiento
from django.contrib.auth import get_user_model

User = get_user_model()

def parse_decimal(value):
    if value is None:
        return Decimal('0.00')
    return Decimal(str(value))

def get_tipo_comprobante(codigo):
    if not codigo:
        return None
    try:
        return TipoComprobante.objects.get(codigo=codigo.strip())
    except TipoComprobante.DoesNotExist:
        return None

def run():
    print("Iniciando Fase 4: Bloque Facturación (lib_iva y lib_iva_alic)")
    dir_path = r'D:\OneDrive\Escritorio\Migracion\eje_272'
    
    empresa = Empresa.objects.get(id=1)
    sucursal = Sucursal.objects.get(id=1)
    ejercicio = Ejercicio.objects.get(id=1)
    user = User.objects.get(username='Ikigai')
    
    # Pre-cargar Tipos de Comprobantes para evitar consultas en el loop
    tipos_dict = {tc.codigo: tc for tc in TipoComprobante.objects.all()}
    # Pre-cargar IDs válidos de Asientos, Clientes y Proveedores
    asientos_validos = set(Asiento.objects.values_list('asiento_id', flat=True))
    clientes_validos = set(ClienteProveedor.objects.values_list('codigo_id', flat=True))
    
    # 1. Facturación (lib_iva.dbf)
    lib_iva_dbf = os.path.join(dir_path, 'lib_iva.dbf')
    if os.path.exists(lib_iva_dbf):
        table = DBF(lib_iva_dbf, ignore_missing_memofile=True, encoding='latin1')
        ventas_to_create = []
        compras_to_create = []
        
        for row in table:
            c_v = str(row.get('C_V', '')).strip().upper()
            entidad_id = row.get('ID_COD')
            if not entidad_id or entidad_id not in clientes_validos:
                entidad_id = None # Podria ser un Consumidor Final sin ID
                
            asiento_id = row.get('ID_ASTO')
                
            tipo = tipos_dict.get(str(row.get('T_DOC', '')).strip())
            fecha = row.get('FECHA') or ejercicio.inicio
            
            # Formatear el periodo AAAA-MM si es posible, sino AAAA-MM de la fecha
            periodo = fecha.strftime('%Y-%m')
            
            if c_v == 'V':
                ventas_to_create.append(Venta(
                    asiento_id=asiento_id,
                    fecha=fecha,
                    periodo=periodo,
                    tipo=tipo,
                    punto=int(row.get('PTO_R') or 1),
                    numero=int(row.get('NRO_R') or 0),
                    cliente_id=entidad_id,
                    moneda='PES',
                    cotizacion=parse_decimal(row.get('COTIZ')),
                    condic=row.get('CONDIC', 1),
                    neto=parse_decimal(row.get('NETO_M') or row.get('NETO')),
                    iva=parse_decimal(row.get('IVA')),
                    no_gravado=parse_decimal(row.get('NO_GRAV')),
                    exento=parse_decimal(row.get('EXENTO')),
                    p_iva=parse_decimal(row.get('RET_IVA')),
                    p_gcia=parse_decimal(row.get('RET_GCIAS')),
                    p_iibb=parse_decimal(row.get('RET_IIBB')),
                    p_sircreb=parse_decimal(row.get('SIRCREB')),
                    p_mun=parse_decimal(row.get('RET_MUN')),
                    total=parse_decimal(row.get('TOTAL')),
                    saldo=parse_decimal(row.get('SALDO')),
                    cobrado=parse_decimal(row.get('PAGADO')),
                    cae=str(row.get('CAE', '')).strip() or None,
                    vto_cae=row.get('VTO_CAE'),
                    cod_qr=str(row.get('COD_QR', '')).strip() or None,
                    usuario=user,
                    sucursal=sucursal,
                    empresa=empresa,
                    ejercicio=ejercicio
                ))
            elif c_v == 'C':
                compras_to_create.append(Compra(
                    asiento_id=asiento_id,
                    fecha=fecha,
                    periodo=periodo,
                    tipo=tipo,
                    punto=int(row.get('PTO_R') or 1),
                    numero=int(row.get('NRO_R') or 0),
                    proveedor_id=entidad_id,
                    moneda='PES',
                    cotizacion=parse_decimal(row.get('COTIZ')),
                    condic=row.get('CONDIC', 1),
                    neto=parse_decimal(row.get('NETO_M') or row.get('NETO')),
                    iva=parse_decimal(row.get('IVA')),
                    no_gravado=parse_decimal(row.get('NO_GRAV')),
                    exento=parse_decimal(row.get('EXENTO')),
                    p_iva=parse_decimal(row.get('RET_IVA')),
                    p_gcia=parse_decimal(row.get('RET_GCIAS')),
                    p_iibb=parse_decimal(row.get('RET_IIBB')),
                    p_sircreb=parse_decimal(row.get('SIRCREB')),
                    p_mun=parse_decimal(row.get('RET_MUN')),
                    total=parse_decimal(row.get('TOTAL')),
                    saldo=parse_decimal(row.get('SALDO')),
                    pagado=parse_decimal(row.get('PAGADO')),
                    usuario=user,
                    sucursal=sucursal,
                    empresa=empresa,
                    ejercicio=ejercicio
                ))
                
        if ventas_to_create:
            # bulk_create no devuelve IDs en Postgres si ignore_conflicts=True (a menos que se use algo mas complejo)
            # Como vamos a procesar alicuotas despues usando el ID_ASTO, guardaremos Venta y Compra
            # Wait, Venta no tiene el campo id forzado, se autoincrementa. Para vincular las alicuotas, 
            # buscaremos la Venta por asiento_id
            Venta.objects.bulk_create(ventas_to_create, ignore_conflicts=True, batch_size=1000)
            print(f"OK {len(ventas_to_create)} Ventas procesadas.")
        if compras_to_create:
            Compra.objects.bulk_create(compras_to_create, ignore_conflicts=True, batch_size=1000)
            print(f"OK {len(compras_to_create)} Compras procesadas.")
            
    # 2. Alicuotas (lib_iva_alic.dbf)
    lib_iva_alic_dbf = os.path.join(dir_path, 'lib_iva_alic.dbf')
    if os.path.exists(lib_iva_alic_dbf):
        table = DBF(lib_iva_alic_dbf, ignore_missing_memofile=True, encoding='latin1')
        ventas_alic = []
        compras_alic = []
        
        # Diccionarios rapidos para mapear asiento_id -> venta_id o compra_id
        ventas_map = {v.asiento_id: v.ventas_id for v in Venta.objects.filter(asiento_id__isnull=False)}
        compras_map = {c.asiento_id: c.compras_id for c in Compra.objects.filter(asiento_id__isnull=False)}
        
        for row in table:
            asiento_id = row.get('ID_ASTO')
            if not asiento_id:
                continue
                
            c_v = str(row.get('C_V', '')).strip().upper()
            
            if c_v == 'V' and asiento_id in ventas_map:
                try:
                    codigo_arca = int(row.get('COD_ALIC', 5)) # Default a 21%
                except:
                    codigo_arca = 5
                    
                ventas_alic.append(VentaAlicuotaIva(
                    venta_id=ventas_map[asiento_id],
                    id_iva=codigo_arca,
                    alicuota=parse_decimal(row.get('ALICUOTA')),
                    base_imponible=parse_decimal(row.get('NETO')),
                    importe_iva=parse_decimal(row.get('IVA'))
                ))
            elif c_v == 'C' and asiento_id in compras_map:
                compras_alic.append(CompraAlicuota(
                    compra_id=compras_map[asiento_id],
                    codigo=str(row.get('COD_ALIC', '5'))[:4],
                    porcentaje=parse_decimal(row.get('ALICUOTA')),
                    neto=parse_decimal(row.get('NETO')),
                    iva=parse_decimal(row.get('IVA'))
                ))
                
        if ventas_alic:
            VentaAlicuotaIva.objects.bulk_create(ventas_alic, ignore_conflicts=True, batch_size=2000)
            print(f"OK {len(ventas_alic)} Alícuotas de Ventas procesadas.")
        if compras_alic:
            CompraAlicuota.objects.bulk_create(compras_alic, ignore_conflicts=True, batch_size=2000)
            print(f"OK {len(compras_alic)} Alícuotas de Compras procesadas.")

    print("Fase 4 completada con éxito.")

if __name__ == '__main__':
    run()
