import os
import sys
import re
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
    try: return Decimal(str(value))
    except: return Decimal('0.00')

MARCAS_CONOCIDAS = {
    'ORBEA', 'REMING', 'REMINGTON', 'ARMUSA', 'RD', 'FM', 'FIOCCHI', 'FALCO', 'HORNADY',
    'MAGTECH', 'MARLIN', 'ROSSI', 'RUGER', 'SAVAGE', 'LEGEND', 'KRAL', 'WEATH', 'ZASTAVA',
    'TAURUS', 'BERSA', 'GLOCK', 'CZ', 'BERETTA', 'BENELLI', 'BROWNING', 'WINCHESTER',
    'SMITH', 'WESSON', 'NORINCO', 'CANIK', 'STEYR', 'WALTHER', 'SIG', 'SAUER', 'HATSAN',
    'H&K', 'HK', 'BOITO', 'HUGAN', 'YILDIZ', 'MAVERICK', 'MOSSBERG', 'BAIKAL', 'DILLON',
    'LYMAN', 'IMAZ', 'STOP', 'POWER'
}

def extract_exact_calibre(detalle):
    """
    Deduce y extrae el calibre del producto a partir de su detalle
    para rubros específicos de Armería y Municiones.
    """
    if not detalle:
        return ""
    d = detalle.upper().strip()

    # 1. Detección con prefijo explícito (C., CAL., CALIBRE, C/)
    m = re.search(r'\b(?:CALIBRE|CAL\.|CAL|C\.|C/|C:)\s*([0-9A-Z\.\-\/\&]+(?:\s+[0-9A-Z\.\-\/\&]+)?)', d)
    if m:
        raw_val = m.group(1).strip()
        tokens = raw_val.split()
        first_token = tokens[0].strip(' .,-/:')
        second_token = tokens[1].strip(' .,-/:') if len(tokens) > 1 else ''
        
        valid_suffixes = {'LR', 'MG', 'MAG', 'MAGNUM', 'HMR', 'ACP', 'SPL', 'SP', 'WIN', 'REM', 'GOV', 'S&W', 'SW', 'WM', 'CREEDMOOR', 'MM', 'X19', '06', '70', '76'}
        
        if second_token and (second_token in valid_suffixes or (first_token in {'30', '45', '12', '16', '20', '28', '36'} and second_token in {'06', '70', '76', 'GOV', 'AT', 'PG', 'SLUG', 'POSTA', 'MAG', '410'})):
            if second_token in {'AT', 'PG', 'SLUG', 'POSTA'}:
                cal = first_token
            else:
                cal = f"{first_token} {second_token}"
        else:
            cal = first_token
            
        if cal in MARCAS_CONOCIDAS or cal in {'POSTA', 'CART', 'MUN', 'BALIN', 'PLOMO', 'TIRO', 'CAZA'}:
            cal = ""
            
        if cal:
            cal = cal.replace('CAL.', '').replace('CAL', '').strip()
            return f"C.{cal}"[:30]

    # 2. Aire comprimido / MUNI AA (4.5, 5.5, 6.35, etc.)
    m_aa = re.search(r'\b(4\.5|5\.5|6\.35|7\.62)\s*(?:MM)?\b', d)
    if m_aa and any(k in d for k in ['AA', 'BALIN', 'CO2', 'RESORTE', 'NITRO', 'PCP', 'AIR', 'G-MAGNUM', 'PRO-MAGNUM']):
        return f"C.{m_aa.group(1)} MM"

    # 3. Menciones directas de calibres conocidos
    direct_calibres = [
        (r'9\s*X\s*19', '9X19'), (r'9\s*MM', '9MM'), (r'40\s*S&W', '40 S&W'), (r'40\s*SW', '40 SW'),
        (r'45\s*ACP', '45 ACP'), (r'380\s*ACP', '380 ACP'), (r'38\s*SPL', '38 SPL'), (r'38\s*SP', '38 SP'),
        (r'357\s*MAG(?:NUM)?', '357 MAG'), (r'357\s*MG', '357 MG'), (r'44\s*MAG(?:NUM)?', '44 MAG'),
        (r'44\s*MG', '44 MG'), (r'44-40', '44-40'), (r'30-06', '30-06'), (r'30\s*06', '30-06'),
        (r'30-30', '30-30'), (r'308\s*WIN', '308 WIN'), (r'308', '308'), (r'223\s*REM', '223 REM'),
        (r'223', '223'), (r'22\s*LR', '22 LR'), (r'22\s*MAG', '22 MAG'), (r'22\s*MG', '22 MG'),
        (r'17\s*HMR', '17 HMR'), (r'12/70', '12/70'), (r'12/76', '12/76'), (r'16/70', '16/70'),
        (r'20/70', '20/70'), (r'28/70', '28/70'), (r'36/70', '36/70'), (r'410', '410')
    ]
    for pattern, name in direct_calibres:
        if re.search(r'\b' + pattern + r'\b', d):
            return f"C.{name}"

    return ""

def run():
    print("=== FASE 3: INVENTARIO (PRODUCTOS ARMERÍA + PRODUCTOS DSK + SUBPRODUCTOS ARMAS) ===")
    
    dir_comercio_255 = r'D:\jm_soft\net_comercio\eje_255'
    dir_comercio_170 = r'D:\jm_soft\net_comercio\eje_170'
    
    empresa = Empresa.objects.get(id=1)
    sucursal_central = Sucursal.objects.get(id=1)
    sucursal_secundaria = Sucursal.objects.get(id=2)
    sucursal_dsk = Sucursal.objects.get(id=3)

    # 1. Marcas (eje_255)
    marcas_dbf = os.path.join(dir_comercio_255, 'marcas.dbf')
    marcas_dict = {}
    if os.path.exists(marcas_dbf):
        table = DBF(marcas_dbf, ignore_missing_memofile=True, encoding='latin1')
        to_create = []
        for row in table:
            m = Marca(
                empresa=empresa,
                detalle=str(row.get('DETALLE', '')).strip()[:100],
                codigo_anterior=str(row['CODIGO']).strip()
            )
            to_create.append(m)
        Marca.objects.bulk_create(to_create, ignore_conflicts=True)
        for m in Marca.objects.filter(empresa=empresa).exclude(codigo_anterior__isnull=True):
            marcas_dict[m.codigo_anterior] = m
        print(f"OK: {len(to_create)} Marcas procesadas.")

    # 2. Rubros (eje_255)
    rubro_dbf = os.path.join(dir_comercio_255, 'rubro.dbf')
    rubros_dict = {}
    if os.path.exists(rubro_dbf):
        table = DBF(rubro_dbf, ignore_missing_memofile=True, encoding='latin1')
        to_create = []
        for row in table:
            r = Rubro(
                empresa=empresa,
                detalle=str(row.get('DETALLE', '')).strip()[:100],
                margen=parse_decimal(row.get('MARG')),
                codigo_anterior=str(row['CODIGO']).strip()
            )
            to_create.append(r)
        Rubro.objects.bulk_create(to_create, ignore_conflicts=True)
        for r in Rubro.objects.filter(empresa=empresa).exclude(codigo_anterior__isnull=True):
            rubros_dict[r.codigo_anterior] = r
        print(f"OK: {len(to_create)} Rubros procesados.")

    # 3. Familias (eje_255)
    fam_dbf = os.path.join(dir_comercio_255, 'familia.dbf')
    fam_dict = {}
    if os.path.exists(fam_dbf):
        table = DBF(fam_dbf, ignore_missing_memofile=True, encoding='latin1')
        to_create = []
        for row in table:
            rubro_id = str(row.get('RUBRO', '')).strip()
            f = Familia(
                empresa=empresa,
                detalle=str(row.get('DETALLE', '')).strip()[:100],
                margen=parse_decimal(row.get('MARGEN')),
                rubro=rubros_dict.get(rubro_id),
                codigo_anterior=str(row['CODIGO']).strip()
            )
            to_create.append(f)
        Familia.objects.bulk_create(to_create, ignore_conflicts=True)
        for f in Familia.objects.filter(empresa=empresa).exclude(codigo_anterior__isnull=True):
            fam_dict[f.codigo_anterior] = f
        print(f"OK: {len(to_create)} Familias procesadas.")

    # 4. Productos de Armería (eje_255)
    prod_255_dbf = os.path.join(dir_comercio_255, 'producto.dbf')
    prod_dict = {}
    stock_data_255 = []
    
    if os.path.exists(prod_255_dbf):
        table_255 = DBF(prod_255_dbf, ignore_missing_memofile=True, encoding='latin1')
        productos_to_create = []
        
        for row in table_255:
            cod_ant = str(row['CODIGO']).strip()
            rubro_obj = rubros_dict.get(str(row.get('ID_RUBRO', '')).strip())
            detalle_str = str(row.get('DETALLE', '')).strip()[:255]
            
            unidad_vta = 'UNIDAD'
            if rubro_obj and (rubro_obj.detalle.startswith('ARMA') or rubro_obj.detalle.startswith('MUNI')):
                cal_ext = extract_exact_calibre(detalle_str)
                if cal_ext:
                    unidad_vta = cal_ext
            
            p = Producto(
                empresa=empresa,
                detalle=detalle_str,
                cod_prov=str(row.get('COD_PROV', '')).strip()[:50],
                cod_fab=str(row.get('COD_FAB', '')).strip()[:50],
                minimo=parse_decimal(row.get('MINIMO')),
                ptopedir=parse_decimal(row.get('PTOPEDIR')),
                creden=bool(row.get('CREDEN', False)),
                alic_iva=(parse_decimal(row.get('ALIC_IVA')) * 100) if row.get('ALIC_IVA') and row.get('ALIC_IVA') < 1 else parse_decimal(row.get('ALIC_IVA', '21')),
                marca=marcas_dict.get(str(row.get('ID_MARCA', '')).strip()),
                rubro=rubro_obj,
                familia=fam_dict.get(str(row.get('ID_FLIA', '')).strip()),
                subprod=bool(row.get('SUBPROD', False)),
                unidad_venta=unidad_vta,
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
            stock_data_255.append((cod_ant, parse_decimal(row.get('STOCK')), parse_decimal(row.get('STKSUC1'))))
            
        Producto.objects.bulk_create(productos_to_create, ignore_conflicts=True, batch_size=1000)
        print(f"OK: {len(productos_to_create)} Productos de Armería (eje_255) insertados.")

    # 5. Productos de Sucursal DSK (eje_170) -> Artículos independientes
    prod_170_dbf = os.path.join(dir_comercio_170, 'producto.dbf')
    if os.path.exists(prod_170_dbf):
        table_170 = DBF(prod_170_dbf, ignore_missing_memofile=True, encoding='latin1')
        prods_dsk_to_create = []
        stock_data_dsk = []
        
        # Evitar colisión si algún código anterior ya existiera
        prods_existentes_cods = set(Producto.objects.filter(empresa=empresa).values_list('codigo_anterior', flat=True))
        
        for row in table_170:
            cod_ant = str(row['CODIGO']).strip()
            if cod_ant in prods_existentes_cods:
                continue
            
            rubro_obj = rubros_dict.get(str(row.get('ID_RUBRO', '')).strip())
            detalle_str = str(row.get('DETALLE', '')).strip()[:255]
            
            unidad_vta = 'UNIDAD'
            if rubro_obj and (rubro_obj.detalle.startswith('ARMA') or rubro_obj.detalle.startswith('MUNI')):
                cal_ext = extract_exact_calibre(detalle_str)
                if cal_ext:
                    unidad_vta = cal_ext
                
            p = Producto(
                empresa=empresa,
                detalle=detalle_str,
                cod_prov=str(row.get('COD_PROV', '')).strip()[:50],
                cod_fab=str(row.get('COD_FAB', '')).strip()[:50],
                minimo=parse_decimal(row.get('MINIMO')),
                ptopedir=parse_decimal(row.get('PTOPEDIR')),
                creden=bool(row.get('CREDEN', False)),
                alic_iva=(parse_decimal(row.get('ALIC_IVA')) * 100) if row.get('ALIC_IVA') and row.get('ALIC_IVA') < 1 else parse_decimal(row.get('ALIC_IVA', '21')),
                marca=marcas_dict.get(str(row.get('ID_MARCA', '')).strip()),
                rubro=rubro_obj,
                familia=fam_dict.get(str(row.get('ID_FLIA', '')).strip()),
                subprod=False,
                unidad_venta=unidad_vta,
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
            prods_dsk_to_create.append(p)
            stock_data_dsk.append((cod_ant, parse_decimal(row.get('STOCK'))))
            
        if prods_dsk_to_create:
            Producto.objects.bulk_create(prods_dsk_to_create, ignore_conflicts=True, batch_size=500)
            print(f"OK: {len(prods_dsk_to_create)} Productos propios de DSK (eje_170) insertados.")

    # 6. Mapear Productos cargados para Stock y Subproductos
    for db_p in Producto.objects.filter(empresa=empresa).only('id', 'codigo_anterior'):
        if db_p.codigo_anterior:
            prod_dict[db_p.codigo_anterior] = db_p

    # 7. Stock por Sucursal (Casa Central + Yerba Buena + DSK)
    stock_to_create = []
    for cod_ant, stk_central, stk_suc in stock_data_255:
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
                
    for cod_ant, stk_dsk in stock_data_dsk:
        p_obj = prod_dict.get(cod_ant)
        if p_obj and stk_dsk != 0:
            stock_to_create.append(StockSucursal(
                producto=p_obj, sucursal=sucursal_dsk, stock_inicial=stk_dsk, cantidad=stk_dsk
            ))

    StockSucursal.objects.bulk_create(stock_to_create, ignore_conflicts=True, batch_size=2000)
    print(f"OK: {len(stock_to_create)} Registros de Stock por Sucursal procesados.")

    # 8. Subproductos (Armas / Series / CUIMs)
    subprod_dbf = os.path.join(dir_comercio_255, 'subproducto.dbf')
    if os.path.exists(subprod_dbf):
        table_sub = DBF(subprod_dbf, ignore_missing_memofile=True, encoding='latin1')
        sub_to_create = []
        import re
        for row in table_sub:
            cod_prod_ant = str(row.get('CODIGO', '')).strip()
            p_obj = prod_dict.get(cod_prod_ant)
            if not p_obj: continue
            
            sucursal_sub = sucursal_central
            if str(row.get('SUC', '')).strip() == '2':
                sucursal_sub = sucursal_secundaria
            elif str(row.get('SUC', '')).strip() == '3':
                sucursal_sub = sucursal_dsk
                
            cuim_val = str(row.get('CUIM', '')).strip().upper()
            if not cuim_val or cuim_val == 'NONE' or not re.fullmatch(r'^[A-Z0-9]{6}$', cuim_val):
                cuim_val = None
                
            situacion = 'VENDIDA' if row.get('ID_VTA') and row.get('ID_VTA') > 0 else 'DEPOSITO'
                
            sub_to_create.append(Subproducto(
                subpro=row['SUBPRO'],
                empresa=empresa,
                producto=p_obj,
                sucursal=sucursal_sub,
                serie=str(row.get('SERIE', '')).strip()[:30] or "SIN SERIE",
                cuim=cuim_val,
                feccpra=row.get('FECCPRA') or date.today(),
                compra_id=None,
                cto_adq=parse_decimal(row.get('CTO_ADQ')),
                cotizadq=parse_decimal(row.get('COTIZADQ')),
                alic_iva=(parse_decimal(row.get('ALIC_IVA')) * 100) if row.get('ALIC_IVA') and row.get('ALIC_IVA') < 1 else parse_decimal(row.get('ALIC_IVA', '21')),
                margen=parse_decimal(row.get('MARGEN')),
                venta_id=None,
                fecvta=row.get('FECVTA') if str(row.get('FECVTA')) != 'None' else None,
                precio_total=parse_decimal(row.get('PCIOT')),
                estado='NUEVO' if str(row.get('COND', '')) == '1' else 'USADO',
                situacion=situacion
            ))
            
        Subproducto.objects.bulk_create(sub_to_create, ignore_conflicts=True, batch_size=1000)
        print(f"OK: {len(sub_to_create)} Subproductos (Armas/Series) procesados.")

    print("Fase 3 completada con éxito.")

if __name__ == '__main__':
    run()
