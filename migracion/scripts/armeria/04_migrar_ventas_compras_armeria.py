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
from productos.models import Producto, Subproducto
from django.contrib.auth import get_user_model

User = get_user_model()

def parse_decimal(value):
    if value is None: return Decimal('0.00')
    try: return Decimal(str(value))
    except: return Decimal('0.00')

def run():
    print("=== FASE 4: MIGRACIÓN DE VENTAS Y COMPRAS HISTÓRICAS (2024, 2025, 2026 Y DSK) ===")
    
    empresa = Empresa.objects.get(id=1)
    sucursal_central = Sucursal.objects.get(id=1) # PV 4
    sucursal_yb = Sucursal.objects.get(id=2)      # PV 6
    sucursal_dsk = Sucursal.objects.get(id=3)     # DSK
    ejercicio = Ejercicio.objects.get(id=1)
    user = User.objects.get(username='ikigai')
    
    tipos_dict = {tc.codigo: tc for tc in TipoComprobante.objects.all()}
    clientes_validos = set(ClienteProveedor.objects.filter(empresa=empresa).values_list('codigo_id', flat=True))
    default_cliente = list(clientes_validos)[0] if clientes_validos else None
    
    productos_dict = {str(p.codigo_anterior).strip(): p for p in Producto.objects.filter(empresa=empresa)}
    default_prod = list(productos_dict.values())[0] if productos_dict else None
    valid_subprods = set(Subproducto.objects.filter(empresa=empresa).values_list('subpro', flat=True))

    # Mapeo de tipos VFP a codigos oficiales ARCA
    map_tipos_vfp_arca = {
        'FA': '001',
        'FB': '006',
        'CA': '003',
        'CB': '008',
        'SC': 'PRE'
    }

    periodos_cache = {p.periodo: p for p in Periodo.objects.filter(empresa=empresa)}

    def get_or_create_periodo(mesano):
        if not mesano: return None
        mesano = str(mesano).strip()
        if len(mesano) == 6:
            if mesano in periodos_cache:
                return periodos_cache[mesano]
            p, _ = Periodo.objects.get_or_create(
                empresa=empresa,
                periodo=mesano,
                defaults={'estado': 'ABIERTO', 'usuario_cierre': user}
            )
            periodos_cache[mesano] = p
            return p
        return None

    # -------------------------------------------------------------
    # 1. VENTAS
    # -------------------------------------------------------------
    ventas_fuentes = [
        {'path': r'D:\jm_soft\net_comercio\eje_255', 'nombre': '2025-2026 (eje_255)', 'es_dsk': False},
        {'path': r'D:\jm_soft\net_comercio\eje_171', 'nombre': '2024 (eje_171)', 'es_dsk': False},
        {'path': r'D:\jm_soft\net_comercio\eje_170', 'nombre': 'DSK Histórico (eje_170)', 'es_dsk': True},
    ]

    ventas_procesadas_keys = set() # (tipo_arca, punto, numero)
    ventas_to_create = []
    ventas_mov_buffer = [] # (id_vta_nuevo, folder_path, id_vta_original, es_dsk, fecha)
    
    current_venta_id = 1

    for f_info in ventas_fuentes:
        folder = f_info['path']
        vta_enc_path = os.path.join(folder, 'ventas_enc.dbf')
        if not os.path.exists(vta_enc_path):
            continue

        print(f"\nProcesando ventas de {f_info['nombre']}...")
        table_enc = DBF(vta_enc_path, ignore_missing_memofile=True, encoding='latin1')
        
        cant_carpeta = 0
        for row in table_enc:
            tipo_vfp = str(row.get('TIPO', '')).strip().upper()
            if tipo_vfp not in map_tipos_vfp_arca:
                continue # Se ignoran RC, RV, EM, XR, RN, etc.
                
            cod_arca = map_tipos_vfp_arca[tipo_vfp]
            tipo_obj = tipos_dict.get(cod_arca)
            if not tipo_obj:
                continue

            punto = int(row.get('PUNTO') or 0)
            numero = int(row.get('NUMERO') or 0)
            fecha = row.get('FECHA') or datetime.today().date()
            
            # Determinar sucursal
            if f_info['es_dsk']:
                suc = sucursal_dsk
            else:
                suc_vfp = row.get('SUC')
                if suc_vfp == 2 or punto == 6:
                    suc = sucursal_yb
                else:
                    suc = sucursal_central

            key_unica = (cod_arca, punto, numero)
            if key_unica in ventas_procesadas_keys:
                continue # Evitar duplicados respetando constraint unico en PostgreSQL
            ventas_procesadas_keys.add(key_unica)

            entidad_id = row.get('ID_COD')
            if not entidad_id or entidad_id not in clientes_validos:
                entidad_id = default_cliente

            periodo = get_or_create_periodo(row.get('MESANO'))
            
            v = Venta(
                ventas_id=current_venta_id,
                empresa=empresa,
                sucursal=suc,
                ejercicio=ejercicio,
                periodo=periodo.periodo if periodo else None,
                tipo=tipo_obj,
                punto=punto,
                numero=numero,
                cliente_id=entidad_id,
                asiento_id=row.get('ID_ASTO') if row.get('ID_ASTO', 0) > 0 else None,
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
            ventas_mov_buffer.append((current_venta_id, folder, row.get('ID_VTA'), f_info['es_dsk'], fecha))
            current_venta_id += 1
            cant_carpeta += 1

        print(f"  OK: {cant_carpeta} ventas válidas extraídas de {f_info['nombre']}.")

    print(f"\nInsertando {len(ventas_to_create)} ventas en PostgreSQL...")
    Venta.objects.bulk_create(ventas_to_create, batch_size=1000)
    print("OK: Cabeceras de ventas insertadas con éxito.")

    # -------------------------------------------------------------
    # 2. DETALLES DE VENTAS (ventas_mov) CON TRAZABILIDAD (CREDENCIAL, SERIE, CUIM, SPROD)
    # -------------------------------------------------------------
    print("\nProcesando ítems de ventas (ventas_mov)...")
    # Agrupar por carpeta para leer cada ventas_mov.dbf una sola vez
    buffer_por_carpeta = {}
    for vid_nuevo, folder, id_vta_orig, es_dsk, f_vta in ventas_mov_buffer:
        if folder not in buffer_por_carpeta:
            buffer_por_carpeta[folder] = {}
        buffer_por_carpeta[folder][id_vta_orig] = (vid_nuevo, es_dsk, f_vta)

    items_to_create = []
    subprods_to_update = []
    for folder, map_vta in buffer_por_carpeta.items():
        vta_mov_path = os.path.join(folder, 'ventas_mov.dbf')
        if not os.path.exists(vta_mov_path):
            continue

        print(f"  Leyendo detalles de {folder}...")
        table_mov = DBF(vta_mov_path, ignore_missing_memofile=True, encoding='latin1')
        
        for row in table_mov:
            id_vta_orig = row.get('ID_VTA')
            if id_vta_orig not in map_vta:
                continue

            vid_nuevo, es_dsk, fecha_vta = map_vta[id_vta_orig]
            cod_prod_raw = str(row.get('COD_PROD', '')).strip()
            
            prod_obj = productos_dict.get(cod_prod_raw)
            if not prod_obj:
                prod_obj = default_prod

            credencial_val = str(row.get('CREDENCIAL', '')).strip() or None
            serie_val = str(row.get('SERIE', '')).strip() or None
            cuim_val = str(row.get('CUIM', '')).strip() or None
            if cuim_val:
                cuim_val = cuim_val.upper()

            id_sprod_val = row.get('ID_SPROD')
            sprod_fk = id_sprod_val if (id_sprod_val and id_sprod_val in valid_subprods) else None

            items_to_create.append(VentaItem(
                venta_id=vid_nuevo,
                producto=prod_obj,
                concepto=str(row.get('DETALLE', ''))[:255] or (prod_obj.detalle if prod_obj else 'PRODUCTO'),
                cantidad=parse_decimal(row.get('CANTIDAD')),
                precio_unitario=parse_decimal(row.get('PCIOV')),
                total=parse_decimal(row.get('TOTAL')),
                iva_alicuota=parse_decimal(row.get('ALIC_IVA')),
                credencial=credencial_val,
                serie=serie_val,
                cuim=cuim_val,
                subproducto_id=sprod_fk
            ))

            if sprod_fk:
                subprods_to_update.append((sprod_fk, vid_nuevo, fecha_vta))

    print(f"Insertando {len(items_to_create)} ítems de venta con trazabilidad...")
    VentaItem.objects.bulk_create(items_to_create, batch_size=2000)
    print("OK: Detalles de ventas insertados.")

    if subprods_to_update:
        print(f"Actualizando {len(subprods_to_update)} Subproductos vinculados a sus ventas...")
        for sp_id, vid_nuevo, f_vta in subprods_to_update:
            Subproducto.objects.filter(subpro=sp_id).update(
                venta_id=vid_nuevo,
                fecvta=f_vta,
                situacion='VENDIDA'
            )
        print("OK: Subproductos vinculados a sus ventas con éxito.")

    # -------------------------------------------------------------
    # 3. COMPRAS Y CRUCE CON LIBRO IVA
    # -------------------------------------------------------------
    print("\n=== PROCESANDO COMPRAS Y CRUCE CON LIBRO IVA ===")
    lib_iva_path = r'D:\jm_soft\net_balances\eje_255\lib_iva.dbf'
    compras_lib_iva_map = {} # (tipo_vfp, punto, numero) -> id_asto
    
    if os.path.exists(lib_iva_path):
        t_iva = DBF(lib_iva_path, ignore_missing_memofile=True, encoding='latin1')
        for r in t_iva:
            if str(r.get('C_V', '')).strip().upper() == 'C':
                t = str(r.get('TIPO', '')).strip().upper()
                p = int(r.get('PUNTO') or 0)
                n = int(r.get('NUMERO') or 0)
                id_asto = r.get('ID_ASTO')
                if id_asto and id_asto > 0:
                    compras_lib_iva_map[(t, p, n)] = id_asto
        print(f"OK: {len(compras_lib_iva_map)} Compras indexadas desde Libro IVA 2026 para cruce contable.")

    compras_fuentes = [
        {'path': r'D:\jm_soft\net_comercio\eje_171', 'nombre': '2024 (eje_171)', 'es_dsk': False},
        {'path': r'D:\jm_soft\net_comercio\eje_223', 'nombre': '2025 (eje_223)', 'es_dsk': False},
        {'path': r'D:\jm_soft\net_comercio\eje_255', 'nombre': '2026 (eje_255)', 'es_dsk': False},
        {'path': r'D:\jm_soft\net_comercio\eje_170', 'nombre': 'DSK (eje_170)', 'es_dsk': True},
    ]

    compras_procesadas_keys = set()
    compras_to_create = []
    compras_mov_buffer = []
    current_compra_id = 1

    for c_info in compras_fuentes:
        folder = c_info['path']
        cpra_enc_path = os.path.join(folder, 'compras_enc.dbf')
        if not os.path.exists(cpra_enc_path):
            continue

        print(f"Procesando compras de {c_info['nombre']}...")
        table_cpra = DBF(cpra_enc_path, ignore_missing_memofile=True, encoding='latin1')
        
        cant_cpras = 0
        for row in table_cpra:
            tipo_vfp = str(row.get('TIPO', '')).strip().upper()
            cod_arca = map_tipos_vfp_arca.get(tipo_vfp, '001') # default 001
            tipo_obj = tipos_dict.get(cod_arca) or tipos_dict.get('001')
            
            punto = int(row.get('PUNTO') or 0)
            numero = int(row.get('NUMERO') or 0)
            fecha = row.get('FECHA') or datetime.today().date()
            
            entidad_id = row.get('ID_COD')
            if not entidad_id or entidad_id not in clientes_validos:
                entidad_id = default_cliente

            suc = sucursal_dsk if c_info['es_dsk'] else (sucursal_yb if punto == 6 else sucursal_central)
            
            key_cpra = (cod_arca, punto, numero, entidad_id, str(fecha))
            if key_cpra in compras_procesadas_keys:
                continue
            compras_procesadas_keys.add(key_cpra)

            # Cruce de ID_ASTO
            id_asto = row.get('ID_ASTO')
            if not id_asto or id_asto == 0:
                id_asto = compras_lib_iva_map.get((tipo_vfp, punto, numero))

            periodo = get_or_create_periodo(row.get('MESANO'))
            
            c = Compra(
                compras_id=current_compra_id,
                empresa=empresa,
                sucursal=suc,
                ejercicio=ejercicio,
                periodo=periodo.periodo if periodo else None,
                tipo=tipo_obj,
                punto=punto,
                numero=numero,
                proveedor_id=entidad_id,
                asiento_id=id_asto if id_asto and id_asto > 0 else None,
                fecha=fecha,
                condic=row.get('CONDIC', 1),
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
            compras_mov_buffer.append((current_compra_id, folder, row.get('ID_CPRA')))
            current_compra_id += 1
            cant_cpras += 1

        print(f"  OK: {cant_cpras} compras procesadas de {c_info['nombre']}.")

    print(f"\nInsertando {len(compras_to_create)} compras en PostgreSQL...")
    Compra.objects.bulk_create(compras_to_create, batch_size=1000)
    print("OK: Compras insertadas.")

    # Detalles de compras
    cpras_por_carpeta = {}
    for cid_nuevo, folder, id_cpra_orig in compras_mov_buffer:
        if folder not in cpras_por_carpeta:
            cpras_por_carpeta[folder] = {}
        cpras_por_carpeta[folder][id_cpra_orig] = cid_nuevo

    items_c_to_create = []
    for folder, map_cpra in cpras_por_carpeta.items():
        cpra_mov_path = os.path.join(folder, 'compras_mov.dbf')
        if not os.path.exists(cpra_mov_path):
            continue

        print(f"  Leyendo detalles de compras de {folder}...")
        table_c_mov = DBF(cpra_mov_path, ignore_missing_memofile=True, encoding='latin1')
        for row in table_c_mov:
            id_cpra_orig = row.get('ID_CPRA')
            if id_cpra_orig not in map_cpra:
                continue

            cid_nuevo = map_cpra[id_cpra_orig]
            cod_prod_raw = str(row.get('COD_PROD', '')).strip()
            prod_obj = productos_dict.get(cod_prod_raw) or default_prod

            items_c_to_create.append(CompraItem(
                compra_id=cid_nuevo,
                producto=prod_obj,
                cantidad=parse_decimal(row.get('CANTIDAD')),
                precio_unitario=parse_decimal(row.get('COSTO_F')),
                total=parse_decimal(row.get('TOTAL')),
                iva_alicuota=parse_decimal(row.get('ALIC_IVA'))
            ))

    print(f"Insertando {len(items_c_to_create)} ítems de compra...")
    CompraItem.objects.bulk_create(items_c_to_create, batch_size=2000)
    print("OK: Detalles de compras insertados.")

    print("Fase 4 completada con éxito.")

if __name__ == '__main__':
    run()
