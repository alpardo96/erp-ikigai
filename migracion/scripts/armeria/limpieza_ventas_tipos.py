import os
import sys
import django
from django.db import connection, transaction

# Configurar el entorno de Django
import pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from facturacion.models import TipoComprobante, Venta
from django.db.models import Count

def ejecutar_limpieza_optimizada():
    print("=== INICIANDO LIMPIEZA Y HOMOLOGACIÓN DE VENTAS ===")
    
    with transaction.atomic():
        # 1. Asegurar tipo PRE
        tipo_pre, created = TipoComprobante.objects.get_or_create(
            codigo='PRE',
            defaults={
                'detalle': 'PRESUPUESTO X',
                'signo': 1,
                'estado': True
            }
        )
        print(f"Tipo PRE ID: {tipo_pre.id}")

        # 2. Actualizar SC -> PRE
        with connection.cursor() as cursor:
            # Obtener ID de tipo SC si existe
            cursor.execute("SELECT id FROM facturacion_tipocomprobante WHERE codigo = 'SC';")
            row_sc = cursor.fetchone()
            if row_sc:
                id_sc = row_sc[0]
                cursor.execute("UPDATE facturacion_venta SET tipo_id = %s WHERE tipo_id = %s;", [tipo_pre.id, id_sc])
                print(f"Actualizadas ventas de SC (ID {id_sc}) a PRE (ID {tipo_pre.id}): {cursor.rowcount} filas")

            # 3. Obtener los IDs de los tipos validos a conservar: FA, FB, CA, CB, PRE
            cursor.execute("SELECT id, codigo FROM facturacion_tipocomprobante WHERE codigo IN ('FA', 'FB', 'CA', 'CB', 'PRE');")
            valid_tipos = cursor.fetchall()
            valid_tipo_ids = [r[0] for r in valid_tipos]
            print(f"Tipos válidos a conservar: {valid_tipos}")

            # 4. Desvincular subproductos (armas) que apuntan a ventas no válidas (columna id_vta)
            cursor.execute("""
                UPDATE productos_subproducto SET id_vta = NULL 
                WHERE id_vta IN (
                    SELECT ventas_id FROM facturacion_venta 
                    WHERE tipo_id IS NULL OR NOT (tipo_id = ANY(%s))
                );
            """, [valid_tipo_ids])
            print(f"Subproductos desvinculados de ventas no válidas: {cursor.rowcount}")

            # 5. Desvincular reservas de armas si hubiera
            cursor.execute("""
                UPDATE armeria_reservaarma SET venta_aplicada_id = NULL 
                WHERE venta_aplicada_id IN (
                    SELECT ventas_id FROM facturacion_venta 
                    WHERE tipo_id IS NULL OR NOT (tipo_id = ANY(%s))
                );
            """, [valid_tipo_ids])

            # 6. Eliminar items de ventas no válidas
            cursor.execute("""
                DELETE FROM facturacion_ventaitem 
                WHERE venta_id IN (
                    SELECT ventas_id FROM facturacion_venta 
                    WHERE tipo_id IS NULL OR NOT (tipo_id = ANY(%s))
                );
            """, [valid_tipo_ids])
            print(f"VentaItems eliminados: {cursor.rowcount}")

            # 7. Eliminar alícuotas IVA si las hubiera
            cursor.execute("""
                DELETE FROM facturacion_ventaalicuotaiva 
                WHERE venta_id IN (
                    SELECT ventas_id FROM facturacion_venta 
                    WHERE tipo_id IS NULL OR NOT (tipo_id = ANY(%s))
                );
            """, [valid_tipo_ids])
            print(f"VentaAlicuotaIva eliminadas: {cursor.rowcount}")

            # 8. Desvincular movimientos de facturación
            cursor.execute("""
                UPDATE facturacion_movimiento SET venta_id = NULL
                WHERE venta_id IN (
                    SELECT ventas_id FROM facturacion_venta 
                    WHERE tipo_id IS NULL OR NOT (tipo_id = ANY(%s))
                );
            """, [valid_tipo_ids])

            # 9. Desvincular movimientos de caja
            cursor.execute("""
                UPDATE tesoreria_movimiento_caja SET venta_id = NULL
                WHERE venta_id IN (
                    SELECT ventas_id FROM facturacion_venta 
                    WHERE tipo_id IS NULL OR NOT (tipo_id = ANY(%s))
                );
            """, [valid_tipo_ids])

            # 10. Desvincular ventas origen en NC si las hubiera
            cursor.execute("""
                UPDATE facturacion_venta SET venta_origen_id = NULL
                WHERE venta_origen_id IN (
                    SELECT ventas_id FROM facturacion_venta 
                    WHERE tipo_id IS NULL OR NOT (tipo_id = ANY(%s))
                );
            """, [valid_tipo_ids])

            # 11. Eliminar ventas no válidas
            cursor.execute("""
                DELETE FROM facturacion_venta 
                WHERE tipo_id IS NULL OR NOT (tipo_id = ANY(%s));
            """, [valid_tipo_ids])
            print(f"Ventas no válidas eliminadas (RC, RB, EM, XR, RV, RN, DA, etc.): {cursor.rowcount}")

    print("\n=== ESTADO FINAL EN BASE DE DATOS ===")
    ventas_final = Venta.objects.values('tipo__codigo', 'tipo__detalle').annotate(total=Count('ventas_id')).order_by('-total')
    total = 0
    for v in ventas_final:
        total += v['total']
        print(f"  Tipo: {v['tipo__codigo']} ({v['tipo__detalle']}) -> {v['total']}")
    print(f"Total de comprobantes en Venta: {total}")

if __name__ == '__main__':
    ejecutar_limpieza_optimizada()
