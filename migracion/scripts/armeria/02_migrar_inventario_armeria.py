import os
import sys
import django
from decimal import Decimal
from datetime import date
from dbfread import DBF
import pathlib

# Configurar el entorno de Django
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from empresas.models import Empresa, Sucursal
from productos.models import Marca, Rubro, Familia, Producto, StockSucursal, Subproducto

def parse_decimal(value):
    if value is None: return Decimal('0.00')
    try:
        return Decimal(str(value))
    except:
        return Decimal('0.00')

def run():
    print("Iniciando Fase 2: Bloque Inventario (Armería)")
    
    dir_comercio = r'D:\OneDrive\Escritorio\Migracion\Armeria\Comercio\eje_255'
    
    if not os.path.exists(dir_comercio):
        print(f"Error: No se encontró la ruta {dir_comercio}")
        return

    empresa = Empresa.objects.get(id=1)
    sucursal_central = Sucursal.objects.get(id=1)
    sucursal_secundaria = Sucursal.objects.get(id=2)

    # 1. Marcas
    marcas_dbf = os.path.join(dir_comercio, 'marcas.dbf')
    marcas_dict = {}
    if os.path.exists(marcas_dbf):
        table = DBF(marcas_dbf, ignore_missing_memofile=True, encoding='latin1')
        to_create = []
        for row in table:
            m = Marca(
                empresa=empresa,
                detalle=row.get('DETALLE', '')[:100],
                codigo_anterior=str(row['CODIGO']).strip()
            )
            to_create.append(m)
        Marca.objects.bulk_create(to_create, ignore_conflicts=True)
        # Recargar para tener IDs
        for m in Marca.objects.filter(empresa=empresa).exclude(codigo_anterior__isnull=True):
            marcas_dict[m.codigo_anterior] = m
        print(f"OK {len(to_create)} marcas procesadas.")

    # 2. Rubros
    rubro_dbf = os.path.join(dir_comercio, 'rubro.dbf')
    rubros_dict = {}
    if os.path.exists(rubro_dbf):
        table = DBF(rubro_dbf, ignore_missing_memofile=True, encoding='latin1')
        to_create = []
        for row in table:
            r = Rubro(
                empresa=empresa,
                detalle=row.get('DETALLE', '')[:100],
                margen=parse_decimal(row.get('MARG')),
                codigo_anterior=str(row['CODIGO']).strip()
            )
            to_create.append(r)
        Rubro.objects.bulk_create(to_create, ignore_conflicts=True)
        for r in Rubro.objects.filter(empresa=empresa).exclude(codigo_anterior__isnull=True):
            rubros_dict[r.codigo_anterior] = r
        print(f"OK {len(to_create)} rubros procesados.")

    # 3. Familias
    fam_dbf = os.path.join(dir_comercio, 'familia.dbf')
    fam_dict = {}
    if os.path.exists(fam_dbf):
        table = DBF(fam_dbf, ignore_missing_memofile=True, encoding='latin1')
        to_create = []
        for row in table:
            rubro_id = str(row.get('RUBRO', '')).strip()
            f = Familia(
                empresa=empresa,
                detalle=row.get('DETALLE', '')[:100],
                margen=parse_decimal(row.get('MARGEN')),
                rubro=rubros_dict.get(rubro_id),
                codigo_anterior=str(row['CODIGO']).strip()
            )
            to_create.append(f)
        Familia.objects.bulk_create(to_create, ignore_conflicts=True)
        for f in Familia.objects.filter(empresa=empresa).exclude(codigo_anterior__isnull=True):
            fam_dict[f.codigo_anterior] = f
        print(f"OK {len(to_create)} familias procesadas.")

    # 4. Productos y StockSucursal
    prod_dbf = os.path.join(dir_comercio, 'producto.dbf')
    prod_dict = {} # map codigo -> Producto.id
    if os.path.exists(prod_dbf):
        table = DBF(prod_dbf, ignore_missing_memofile=True, encoding='latin1')
        productos_to_create = []
        stock_data = [] # (codigo_anterior, stock_central, stock_suc)
        
        for row in table:
            cod_ant = str(row['CODIGO']).strip()
            
            p = Producto(
                empresa=empresa,
                detalle=row.get('DETALLE', '')[:255],
                cod_prov=str(row.get('COD_PROV', ''))[:50],
                cod_fab=str(row.get('COD_FAB', ''))[:50],
                minimo=parse_decimal(row.get('MINIMO')),
                ptopedir=parse_decimal(row.get('PTOPEDIR')),
                creden=bool(row.get('CREDEN', False)),
                alic_iva=(parse_decimal(row.get('ALIC_IVA')) * 100) if row.get('ALIC_IVA') else parse_decimal('0'),
                marca=marcas_dict.get(str(row.get('ID_MARCA', '')).strip()),
                rubro=rubros_dict.get(str(row.get('ID_RUBRO', '')).strip()),
                familia=fam_dict.get(str(row.get('ID_FLIA', '')).strip()),
                subprod=bool(row.get('SUBPROD', False)),
                codigo_anterior=cod_ant,
                cto_adq=parse_decimal(row.get('CTO_ADQ')),
                fec_adq=row.get('FEC_ADQ') if str(row.get('FEC_ADQ')) != 'None' else None,
                cto_rep=parse_decimal(row.get('CTO_REP')),
                fec_act=row.get('FEC_ACT') if str(row.get('FEC_ACT')) != 'None' else None,
                margen=parse_decimal(row.get('MARGEN')),
                precio_neto=parse_decimal(row.get('PRECIO')),
                precio_total=parse_decimal(row.get('PCIOT')),
                cotiz_cpra=parse_decimal(row.get('COTIZ'))
            )
            productos_to_create.append(p)
            stock_data.append((cod_ant, parse_decimal(row.get('STOCK')), parse_decimal(row.get('STKSUC1'))))
            
        Producto.objects.bulk_create(productos_to_create, ignore_conflicts=True, batch_size=1000)
        print(f"OK {len(productos_to_create)} productos insertados.")
        
        # Recuperar para inyectar Stock y hacer mapeo para Subproductos
        stock_to_create = []
        db_productos = Producto.objects.filter(empresa=empresa).only('id', 'codigo_anterior')
        
        for db_p in db_productos:
            if db_p.codigo_anterior:
                prod_dict[db_p.codigo_anterior] = db_p
                
        # Crear StockSucursal
        for cod_ant, stk_central, stk_suc in stock_data:
            p_obj = prod_dict.get(cod_ant)
            if p_obj:
                if stk_central != 0:
                    stock_to_create.append(StockSucursal(
                        producto=p_obj, sucursal=sucursal_central, stock_inicial=stk_central, cantidad=stk_central
                    ))
                if stk_suc != 0:
                    stock_to_create.append(StockSucursal(
                        producto=p_obj, sucursal=sucursal_secundaria, stock_inicial=stk_suc, cantidad=stk_suc
                    ))
                    
        StockSucursal.objects.bulk_create(stock_to_create, ignore_conflicts=True, batch_size=2000)
        print(f"OK {len(stock_to_create)} registros de Stock (Casa Central + Sucursal) procesados.")

    # 5. Subproductos (Armas / Series)
    subprod_dbf = os.path.join(dir_comercio, 'subproducto.dbf')
    if os.path.exists(subprod_dbf):
        table = DBF(subprod_dbf, ignore_missing_memofile=True, encoding='latin1')
        sub_to_create = []
        for row in table:
            cod_prod_ant = str(row.get('CODIGO', '')).strip()
            p_obj = prod_dict.get(cod_prod_ant)
            if not p_obj: continue
            
            sucursal_sub = sucursal_central
            if str(row.get('SUC', '')) == '2':
                sucursal_sub = sucursal_secundaria
                
            cuim_val = str(row.get('CUIM', '')).strip().upper()
            if not cuim_val or cuim_val == 'NONE': cuim_val = None
            # Evitamos que se rompa el validado de regex (alfanumerico 6 chars)
            # Solo migramos si es valido o nulo. Si no es valido lo pasamos a nulo y guardamos la serie
            import re
            if cuim_val and not re.fullmatch(r'^[A-Z0-9]{6}$', cuim_val):
                cuim_val = None
                
            situacion = 'VENDIDA' if row.get('ID_VTA') and row.get('ID_VTA') > 0 else 'DEPOSITO'
                
            sub_to_create.append(Subproducto(
                empresa=empresa,
                producto=p_obj,
                sucursal=sucursal_sub,
                serie=str(row.get('SERIE', ''))[:30] or "SIN SERIE",
                cuim=cuim_val,
                feccpra=row.get('FECCPRA') or date.today(),
                compra_id=row.get('ID_CPRA') or None,
                cto_adq=parse_decimal(row.get('CTO_ADQ')),
                cotizadq=parse_decimal(row.get('COTIZADQ')),
                alic_iva=(parse_decimal(row.get('ALIC_IVA')) * 100) if row.get('ALIC_IVA') else parse_decimal('0'),
                margen=parse_decimal(row.get('MARGEN')),
                venta_id=row.get('ID_VTA') or None,
                fecvta=row.get('FECVTA') if str(row.get('FECVTA')) != 'None' else None,
                precio_total=parse_decimal(row.get('PCIOT')),
                estado='NUEVO' if str(row.get('COND', '')) == '1' else 'USADO',
                situacion=situacion
            ))
            
        Subproducto.objects.bulk_create(sub_to_create, ignore_conflicts=True, batch_size=1000)
        print(f"OK {len(sub_to_create)} subproductos (armas/series) procesados.")

    print("Fase 2 completada con éxito.")

if __name__ == '__main__':
    run()
