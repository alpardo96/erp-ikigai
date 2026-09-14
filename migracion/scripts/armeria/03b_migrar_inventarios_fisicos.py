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

from empresas.models import Empresa, Sucursal
from productos.models import Producto, TomaInventario, TomaInventarioItem
from django.contrib.auth import get_user_model

User = get_user_model()

def parse_decimal(value):
    if value is None: return Decimal('0.00')
    try: return Decimal(str(value))
    except: return Decimal('0.00')

def run():
    print("=== FASE 3B: MIGRACIÓN DE TOMAS DE INVENTARIOS FÍSICOS (VFP) ===")
    
    empresa = Empresa.objects.get(id=1)
    sucursal_central = Sucursal.objects.get(id=1)
    default_user = User.objects.get(username='ikigai')
    
    # Mapa de productos por codigo_anterior
    prod_map = {p.codigo_anterior: p for p in Producto.objects.filter(empresa=empresa)}

    inventarios_fuentes = [
        {
            'path': r'D:\jm_soft\net_comercio\eje_171\inventario.dbf',
            'numero': 1,
            'nombre': 'Inventario Físico Diciembre 2023',
            'fecha_default': datetime(2023, 12, 16, 12, 0, 0)
        },
        {
            'path': r'D:\jm_soft\net_comercio\eje_255\inventario.dbf',
            'numero': 2,
            'nombre': 'Inventario Físico Octubre 2025',
            'fecha_default': datetime(2025, 10, 18, 12, 0, 0)
        }
    ]

    for fuente in inventarios_fuentes:
        fpath = fuente['path']
        if not os.path.exists(fpath):
            print(f"Aviso: No se encontró {fpath}")
            continue

        table = DBF(fpath, ignore_missing_memofile=True, encoding='latin1')
        records = list(table)
        if not records:
            continue

        primera_fecha = records[0].get('MODIFI') or fuente['fecha_default']
        terminal = str(records[0].get('TERMINAL') or 'TERMINAL-01').strip()

        toma_obj, created = TomaInventario.objects.get_or_create(
            empresa=empresa,
            sucursal=sucursal_central,
            numero=fuente['numero'],
            defaults={
                'fecha_toma': primera_fecha,
                'observaciones': fuente['nombre'],
                'estado': 'CONFIRMADO',
                'terminal': terminal,
                'creado_por': default_user,
                'modificado_por': default_user
            }
        )
        print(f"\nProcesando {fuente['nombre']} (ID: {toma_obj.id})...")

        items_to_create = []
        for row in records:
            cod_ant = str(row.get('CODIGO')).strip()
            p_obj = prod_map.get(cod_ant)
            if not p_obj:
                continue

            cant_contada = parse_decimal(row.get('CANTIDAD'))
            fec_item = row.get('MODIFI') or primera_fecha
            term_item = str(row.get('TERMINAL') or terminal).strip()

            items_to_create.append(TomaInventarioItem(
                inventario=toma_obj,
                producto=p_obj,
                cantidad_contada=cant_contada,
                stock_teorico=0,
                diferencia=cant_contada,
                usuario_conteo=default_user,
                fecha_hora=fec_item,
                terminal=term_item
            ))

        TomaInventarioItem.objects.bulk_create(items_to_create, ignore_conflicts=True, batch_size=1000)
        print(f"OK: {len(items_to_create)} Ítems de inventario físico registrados.")

    print("Fase 3B completada con éxito.")

if __name__ == '__main__':
    run()
