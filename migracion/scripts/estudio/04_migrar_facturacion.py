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
from facturacion.models import (
    Venta, Compra, TipoComprobante, ClienteProveedor,
    VentaAlicuotaIva, CompraAlicuota, VentaItem, CompraItem
)
from contable.models import Asiento
from productos.models import Producto
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
    print("Iniciando Fase 4: Bloque Facturación y Libro IVA (Estudio)...")
    dir_path = r'D:\OneDrive\Escritorio\Migracion\Estudio\eje_272'
    
    empresa = Empresa.objects.get(id=1)
    sucursal = Sucursal.objects.get(id=1)
    ejercicios = list(Ejercicio.objects.filter(empresa=empresa).order_by('inicio'))
    ejercicio_default = ejercicios[-1] if ejercicios else None
    user = User.objects.get(username='Ikigai')

    def resolver_ejercicio(fecha_doc):
        if not fecha_doc:
            return ejercicio_default
        for ej in ejercicios:
            if ej.inicio <= fecha_doc <= ej.cierre:
                return ej
        return ejercicio_default
    
    # Pre-cargar Tipos de Comprobantes
    tipos_dict = {tc.codigo: tc for tc in TipoComprobante.objects.all()}
    default_tipo = TipoComprobante.objects.first()

    # Pre-mapear ID_ASTO -> ID_USU desde asto_enc y caja_diaria
    usuario_por_asiento = {}
    asto_dbf = os.path.join(dir_path, 'asto_enc.dbf')
    if os.path.exists(asto_dbf):
        t_asto = DBF(asto_dbf, ignore_missing_memofile=True, encoding='latin1')
        for r in t_asto:
            a = r.get('ID_ASTO')
            u = r.get('ID_USU')
            if a and u:
                usuario_por_asiento[abs(a)] = resolver_usuario_id(u)

    caja_dbf = os.path.join(dir_path, 'caja_diaria.dbf')
    if os.path.exists(caja_dbf):
        t_caja = DBF(caja_dbf, ignore_missing_memofile=True, encoding='latin1')
        for r in t_caja:
            a = r.get('ID_ASTO')
            u = r.get('ID_USU')
            if a and u and abs(safe_int(a)) not in usuario_por_asiento:
                usuario_por_asiento[abs(safe_int(a))] = resolver_usuario_id(u)

    for dbf_name in ['recibos.dbf', 'ord_pago.dbf', 'cheques.dbf']:
        p = os.path.join(dir_path, dbf_name)
        if os.path.exists(p):
            t_aux = DBF(p, ignore_missing_memofile=True, encoding='latin1')
            for r in t_aux:
                a = r.get('ID_ASTO')
                u = r.get('ID_USU')
                if a and u and abs(safe_int(a)) not in usuario_por_asiento:
                    usuario_por_asiento[abs(safe_int(a))] = resolver_usuario_id(u)

    # Pre-cargar IDs válidos
    asientos_validos = set(Asiento.objects.filter(empresa=empresa).values_list('asiento_id', flat=True))
    clientes_validos = set(ClienteProveedor.objects.filter(empresa=empresa).values_list('codigo_id', flat=True))

    # Asegurar producto default para items
    producto_defecto, _ = Producto.objects.get_or_create(
        id=1,
        defaults={
            'empresa': empresa,
            'detalle': 'Honorarios / Servicios Contables',
            'alic_iva': Decimal('21.00'),
            'moneda': 'PES',
            'creado_por': user,
            'activo': True
        }
    )

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
                entidad_id = None
                
            raw_asto = row.get('ID_ASTO')
            asiento_id = abs(safe_int(raw_asto)) if raw_asto else None
            usu_id = usuario_por_asiento.get(asiento_id, 1) if asiento_id else 1
                
            cod_citi = str(row.get('COD_CITI', '')).strip()
            tipo_str = str(row.get('TIPO', '')).strip().upper()
            
            if not cod_citi:
                if tipo_str == 'SC':
                    cod_citi = 'PRE'
                elif tipo_str == 'RT':
                    cod_citi = '090'
                else:
                    cod_citi = str(row.get('T_DOC', '')).strip()
                    
            tipo = tipos_dict.get(cod_citi) or tipos_dict.get(tipo_str) or default_tipo
            
            fecha = row.get('FECHA') or (ejercicio_default.inicio if ejercicio_default else datetime(2026, 6, 1).date())
            ej = resolver_ejercicio(fecha)
            periodo = fecha.strftime('%Y%m') # Formato YYYYMM (6 caracteres)
            
            punto = safe_int(row.get('PUNTO') or row.get('PTO_R'), 1)
            numero = safe_int(row.get('NUMERO') or row.get('NRO_R'), 0)
            neto = parse_decimal(row.get('NETO_M') or row.get('NETO'))
            
            if c_v == 'V':
                ventas_to_create.append(Venta(
                    asiento_id=asiento_id,
                    fecha=fecha,
                    periodo=periodo,
                    tipo=tipo,
                    punto=punto,
                    numero=numero,
                    cliente_id=entidad_id,
                    moneda='PES',
                    cotizacion=parse_decimal(row.get('COTIZ')),
                    condic=int(row.get('CONDIC', 1) or 1),
                    neto=neto,
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
                    usuario_id=usu_id,
                    sucursal=sucursal,
                    empresa=empresa,
                    ejercicio=ej
                ))
            elif c_v == 'C':
                compras_to_create.append(Compra(
                    asiento_id=asiento_id,
                    fecha=fecha,
                    periodo=periodo,
                    tipo=tipo,
                    punto=punto,
                    numero=numero,
                    proveedor_id=entidad_id,
                    moneda='PES',
                    cotizacion=parse_decimal(row.get('COTIZ')),
                    condic=int(row.get('CONDIC', 1) or 1),
                    neto=neto,
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
                    usuario_id=usu_id,
                    sucursal=sucursal,
                    empresa=empresa,
                    ejercicio=ej
                ))
                
        if ventas_to_create:
            Venta.objects.bulk_create(ventas_to_create, ignore_conflicts=True, batch_size=1000)
            print(f"OK {len(ventas_to_create)} Ventas procesadas.")
        if compras_to_create:
            Compra.objects.bulk_create(compras_to_create, ignore_conflicts=True, batch_size=1000)
            print(f"OK {len(compras_to_create)} Compras procesadas.")
            
        # 2. Generar VentaItem y CompraItem
        ventas_db = list(Venta.objects.filter(empresa=empresa))
        compras_db = list(Compra.objects.filter(empresa=empresa))
        
        ventas_items = [
            VentaItem(
                venta_id=v.ventas_id,
                producto_id=1,
                cantidad=Decimal('1.00'),
                precio_unitario=v.neto,
                total=v.neto
            ) for v in ventas_db
        ]
        compras_items = [
            CompraItem(
                compra_id=c.compras_id,
                producto_id=1,
                cantidad=Decimal('1.00'),
                precio_unitario=c.neto,
                total=c.neto
            ) for c in compras_db
        ]
        
        VentaItem.objects.bulk_create(ventas_items, ignore_conflicts=True, batch_size=2000)
        CompraItem.objects.bulk_create(compras_items, ignore_conflicts=True, batch_size=2000)
        print(f"OK {len(ventas_items)} VentaItems y {len(compras_items)} CompraItems generados.")

    # 3. Alicuotas (lib_iva_alic.dbf)
    lib_iva_alic_dbf = os.path.join(dir_path, 'lib_iva_alic.dbf')
    if os.path.exists(lib_iva_alic_dbf):
        table = DBF(lib_iva_alic_dbf, ignore_missing_memofile=True, encoding='latin1')
        ventas_alic = []
        compras_alic = []
        
        ventas_map = {v.asiento_id: v.ventas_id for v in Venta.objects.filter(empresa=empresa, asiento_id__isnull=False)}
        compras_map = {c.asiento_id: c.compras_id for c in Compra.objects.filter(empresa=empresa, asiento_id__isnull=False)}
        
        for row in table:
            asiento_id = row.get('ID_ASTO')
            if not asiento_id:
                continue
                
            c_v = str(row.get('C_V', '')).strip().upper()
            
            if c_v == 'V' and asiento_id in ventas_map:
                try:
                    codigo_arca = int(row.get('COD_ALIC', 5))
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
