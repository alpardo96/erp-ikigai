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

from empresas.models import Empresa, Sucursal, Ejercicio
from facturacion.models import Venta, VentaItem, Compra, CompraItem, TipoComprobante, ClienteProveedor
from impuestos.models import PeriodoIva as Periodo
from contable.models import Asiento
from productos.models import Producto, Subproducto
from django.contrib.auth import get_user_model

User = get_user_model()

def parse_decimal(value):
    if value is None:
        return Decimal('0.00')
    return Decimal(str(value))

def run():
    print("Iniciando Fase 4: Bloque Operativo de Facturación (Armería)")
    dir_comercio = r'D:\OneDrive\Escritorio\Migracion\Armeria\Comercio\eje_255'
    
    empresa = Empresa.objects.get(id=1)
    sucursal_central = Sucursal.objects.get(id=1)  # PV: 4
    sucursal_sucursal = Sucursal.objects.get(id=2) # PV: 6
    ejercicio = Ejercicio.objects.get(id=1)
    user = User.objects.get(username='ikigai')
    
    tipos_dict = {tc.codigo: tc for tc in TipoComprobante.objects.all()}
    clientes_validos = set(ClienteProveedor.objects.values_list('codigo_id', flat=True))
    productos_dict = {str(p.codigo_anterior).strip(): p for p in Producto.objects.filter(empresa=empresa)}

    # Periodos
    def get_or_create_periodo(mesano):
        if not mesano:
            return None
        mesano = str(mesano).strip()
        if len(mesano) == 6:
            mes = int(mesano[4:6])
            anio = int(mesano[0:4])
            p, _ = Periodo.objects.get_or_create(
                empresa=empresa,
                periodo=mesano,
                defaults={
                    'estado': 'ABIERTO',
                    'usuario_cierre': user,
                }
            )
            return p
        return None

    # 1. Ventas Encabezado
    vta_enc_dbf = os.path.join(dir_comercio, 'ventas_enc.dbf')
    ventas_map = {} # para los items
    if os.path.exists(vta_enc_dbf):
        table = DBF(vta_enc_dbf, ignore_missing_memofile=True, encoding='latin1')
        ventas_to_create = []
        for row in table:
            id_vta = row.get('ID_VTA')
            entidad_id = row.get('ID_COD')
            if not entidad_id or entidad_id not in clientes_validos:
                entidad_id = list(clientes_validos)[0] if clientes_validos else None
                
            punto = int(row.get('PUNTO') or 0)
            suc = sucursal_central
            if punto == 6: suc = sucursal_sucursal
            elif punto == 0: suc = sucursal_central # Presupuestos

            tipo = tipos_dict.get(str(row.get('TIPO', '')).strip())
            fecha = row.get('FECHA') or datetime.today().date()
            periodo = get_or_create_periodo(row.get('MESANO'))
            
            v = Venta(
                ventas_id=id_vta, # Forzamos el ID original para enganchar items
                empresa=empresa,
                sucursal=suc,
                ejercicio=ejercicio,
                periodo=periodo.periodo if periodo else None,
                tipo=tipo,
                punto=punto,
                numero=int(row.get('NUMERO') or 0),
                cliente_id=entidad_id,
                asiento_id=row.get('ID_ASTO'),
                fecha=fecha,
                condic=row.get('CONDIC', 1),
                moneda='PES',
                cotizacion=parse_decimal(row.get('COTIZ')),
                neto=parse_decimal(row.get('NETO')),
                iva=parse_decimal(row.get('IVA')),
                no_gravado=parse_decimal(row.get('NO_GRAV')),
                exento=parse_decimal(row.get('EXENTO')),
                p_iva=parse_decimal(row.get('PERC_IVA')),
                p_gcia=parse_decimal(row.get('PERC_GCIA')),
                p_iibb=parse_decimal(row.get('PERC_IB')),
                total=parse_decimal(row.get('TOTAL')),
                saldo=parse_decimal(row.get('SALDO')),
                cobrado=parse_decimal(row.get('COBRADO')),
                cae=str(row.get('CAE', '')).strip() or None,
                vto_cae=row.get('VTO_CAE'),
                usuario=user
            )
            ventas_to_create.append(v)
            ventas_map[id_vta] = v

        Venta.objects.bulk_create(ventas_to_create, ignore_conflicts=True, batch_size=1000)
        print(f"OK {len(ventas_to_create)} Ventas procesadas.")

        valid_venta_ids = set(Venta.objects.filter(empresa=empresa, ventas_id__in=ventas_map.keys()).values_list('ventas_id', flat=True))

    # 2. Ventas Detalles
    vta_mov_dbf = os.path.join(dir_comercio, 'ventas_mov.dbf')
    if os.path.exists(vta_mov_dbf):
        table = DBF(vta_mov_dbf, ignore_missing_memofile=True, encoding='latin1')
        items_to_create = []
        for row in table:
            id_vta = row.get('ID_VTA')
            if id_vta not in valid_venta_ids: continue
            
            cod_prod = str(row.get('COD_PROD', '')).strip()
            prod_obj = productos_dict.get(cod_prod)
            if not prod_obj:
                prod_obj = list(productos_dict.values())[0] if productos_dict else None
            
            items_to_create.append(VentaItem(
                venta_id=id_vta,
                producto=prod_obj,
                concepto=str(row.get('DETALLE', ''))[:255] if not prod_obj else prod_obj.detalle,
                cantidad=parse_decimal(row.get('CANTIDAD')),
                precio_unitario=parse_decimal(row.get('PCIOV')),
                total=parse_decimal(row.get('TOTAL')),
                iva_alicuota=parse_decimal(row.get('ALIC_IVA'))
            ))
        VentaItem.objects.bulk_create(items_to_create, ignore_conflicts=True, batch_size=2000)
        print(f"OK {len(items_to_create)} Detalles de Venta procesados.")

    # 3. Compras Encabezado
    cpra_enc_dbf = os.path.join(dir_comercio, 'compras_enc.dbf')
    compras_map = {}
    if os.path.exists(cpra_enc_dbf):
        table = DBF(cpra_enc_dbf, ignore_missing_memofile=True, encoding='latin1')
        compras_to_create = []
        for row in table:
            id_cpra = row.get('ID_CPRA')
            entidad_id = row.get('ID_COD')
            if not entidad_id or entidad_id not in clientes_validos:
                entidad_id = list(clientes_validos)[0] if clientes_validos else None
                
            punto = int(row.get('PUNTO') or 0)
            suc = sucursal_central
            if punto == 6: suc = sucursal_sucursal

            tipo = tipos_dict.get(str(row.get('TIPO', '')).strip())
            fecha = row.get('FECHA') or datetime.today().date()
            periodo = get_or_create_periodo(row.get('MESANO'))
            
            c = Compra(
                compras_id=id_cpra,
                empresa=empresa,
                sucursal=suc,
                ejercicio=ejercicio,
                periodo=periodo.periodo if periodo else None,
                tipo=tipo,
                punto=punto,
                numero=int(row.get('NUMERO') or 0),
                proveedor_id=entidad_id,
                asiento_id=row.get('ID_ASTO'),
                fecha=fecha,
                condic=row.get('CONDIC') if row.get('CONDIC') else 1,
                moneda='PES',
                cotizacion=parse_decimal(row.get('COTIZ')),
                neto=parse_decimal(row.get('NETO')),
                iva=parse_decimal(row.get('IVA')),
                no_gravado=parse_decimal(row.get('NO_GRAV')),
                exento=parse_decimal(row.get('EXENTO')),
                p_iva=parse_decimal(row.get('P_IVA')),
                p_gcia=parse_decimal(row.get('P_GCIA')),
                p_iibb=parse_decimal(row.get('P_IB')),
                p_mun=parse_decimal(row.get('P_MUN')),
                total=parse_decimal(row.get('TOTAL')),
                usuario=user
            )
            compras_to_create.append(c)
            compras_map[id_cpra] = c

        Compra.objects.bulk_create(compras_to_create, ignore_conflicts=True, batch_size=1000)
        print(f"OK {len(compras_to_create)} Compras procesadas.")

        valid_compra_ids = set(Compra.objects.filter(empresa=empresa, compras_id__in=compras_map.keys()).values_list('compras_id', flat=True))

    # 4. Compras Detalles
    cpra_mov_dbf = os.path.join(dir_comercio, 'compras_mov.dbf')
    if os.path.exists(cpra_mov_dbf):
        table = DBF(cpra_mov_dbf, ignore_missing_memofile=True, encoding='latin1')
        items_c_to_create = []
        for row in table:
            id_cpra = row.get('ID_CPRA')
            if id_cpra not in valid_compra_ids: continue
            
            cod_prod = str(row.get('COD_PROD', '')).strip()
            prod_obj = productos_dict.get(cod_prod)
            if not prod_obj:
                prod_obj = list(productos_dict.values())[0] if productos_dict else None
            
            items_c_to_create.append(CompraItem(
                compra_id=id_cpra,
                producto=prod_obj,
                cantidad=parse_decimal(row.get('CANTIDAD')),
                precio_unitario=parse_decimal(row.get('COSTO_F')),
                total=parse_decimal(row.get('TOTAL')),
                iva_alicuota=parse_decimal(row.get('ALIC_IVA'))
            ))
        CompraItem.objects.bulk_create(items_c_to_create, ignore_conflicts=True, batch_size=2000)
        print(f"OK {len(items_c_to_create)} Detalles de Compra procesados.")

    print("Fase 4 completada con éxito.")

if __name__ == '__main__':
    run()
