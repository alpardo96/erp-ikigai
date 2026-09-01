import os
import sys
import django
from decimal import Decimal

# Configurar el entorno de Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from dbfread import DBF
from facturacion.models import ClienteProveedor, Venta, Compra, TipoComprobante, VentaItem, CompraItem
from productos.models import Producto

def safe_int(value, default=0):
    try:
        if not value: return default
        if isinstance(value, str):
            value = ''.join(c for c in value if c.isdigit())
        return int(value) if value else default
    except (ValueError, TypeError):
        return default

def run():
    print("Iniciando Correcciones Fase 4...")
    dir_eje = r'D:\OneDrive\Escritorio\Migracion\eje_272'
    
    # 1. Corregir ClienteProveedor tipo_entidad
    print("\n--- 1. Corrigiendo tipo_entidad en ClienteProveedor ---")
    cli_pro_dbf = DBF(os.path.join(dir_eje, 'cli_pro.dbf'))
    tipo_map = {int(r['CODIGO']): safe_int(r.get('CLI_PRO'), 1) for r in cli_pro_dbf}
    
    updates_cp = []
    for cp in ClienteProveedor.objects.all():
        tipo = tipo_map.get(cp.codigo_id)
        if tipo in [1, 2]:
            cp.tipo_entidad = tipo
            updates_cp.append(cp)
    
    ClienteProveedor.objects.bulk_update(updates_cp, ['tipo_entidad'], batch_size=1000)
    print(f"OK: Actualizados {len(updates_cp)} Clientes/Proveedores con su tipo_entidad correcto.")
    
    # Asegurar que el Producto 1 existe
    producto_defecto, _ = Producto.objects.get_or_create(
        id=1,
        defaults={
            'nombre': 'Honorarios / Servicios Contables',
            'tipo_producto': 2, # Servicio
            'iva_alicuota_id': 1
        }
    )

    # 2. Corregir Venta y Compra
    print("\n--- 2. Corrigiendo Venta y Compra (punto, numero, tipo_id, e items) ---")
    lib_iva_dbf = DBF(os.path.join(dir_eje, 'lib_iva.dbf'))
    
    tipos_db = {t.codigo: t.id for t in TipoComprobante.objects.all()}
    
    ventas_map = {v.asiento_id: v for v in Venta.objects.exclude(asiento_id__isnull=True)}
    compras_map = {c.asiento_id: c for c in Compra.objects.exclude(asiento_id__isnull=True)}
    
    ventas_to_update = []
    compras_to_update = []
    ventas_items = []
    compras_items = []
    
    for row in lib_iva_dbf:
        id_asto = row.get('ID_ASTO')
        c_v = row.get('C_V', '').strip().upper()
        
        # Mapear Codigo de Comprobante
        cod_citi = row.get('COD_CITI', '').strip()
        tipo_str = row.get('TIPO', '').strip().upper()
        
        if not cod_citi:
            if tipo_str == 'SC':
                cod_citi = 'PRE'
            elif tipo_str == 'RT':
                cod_citi = '090'
            else:
                cod_citi = '000' # No definido?
                
        tipo_id = tipos_db.get(cod_citi)
        
        punto = safe_int(row.get('PUNTO'), 1)
        numero = safe_int(row.get('NUMERO'), 0)
        neto = Decimal(str(row.get('NETO') or 0))
        
        if c_v == 'V' and id_asto in ventas_map:
            v = ventas_map[id_asto]
            v.punto = punto
            v.numero = numero
            if tipo_id:
                v.tipo_id = tipo_id
            ventas_to_update.append(v)
            
            ventas_items.append(VentaItem(
                venta_id=v.ventas_id,
                producto_id=1,
                cantidad=Decimal('1.00'),
                precio_unitario=neto,
                total=neto
            ))
            
        elif c_v == 'C' and id_asto in compras_map:
            c = compras_map[id_asto]
            c.punto = punto
            c.numero = numero
            if tipo_id:
                c.tipo_id = tipo_id
            compras_to_update.append(c)
            
            compras_items.append(CompraItem(
                compra_id=c.compras_id,
                producto_id=1,
                cantidad=Decimal('1.00'),
                precio_unitario=neto,
                total=neto
            ))
            
    # Limpiar Items previos si existen
    VentaItem.objects.all().delete()
    CompraItem.objects.all().delete()
    
    # Actualizar Comprobantes
    Venta.objects.bulk_update(ventas_to_update, ['punto', 'numero', 'tipo_id'], batch_size=1000)
    Compra.objects.bulk_update(compras_to_update, ['punto', 'numero', 'tipo_id'], batch_size=1000)
    print(f"OK: Actualizadas {len(ventas_to_update)} Ventas y {len(compras_to_update)} Compras.")
    
    # Crear Items
    VentaItem.objects.bulk_create(ventas_items, batch_size=1000)
    CompraItem.objects.bulk_create(compras_items, batch_size=1000)
    print(f"OK: Creados {len(ventas_items)} VentaItems y {len(compras_items)} CompraItems vinculados al Producto 1.")

if __name__ == '__main__':
    run()
