import os
import sys
import csv
import django
from django.db import connection, transaction

# Configurar el entorno de Django
import pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from facturacion.models import TipoComprobante, Venta, Compra

def migrar_tipos_comprobante():
    print("=== MIGRACIÓN DE TIPOS DE COMPROBANTES DESDE CSV ===")
    csv_path = r"d:\borrador\facturacion_tipocomprobante.csv"
    
    if not os.path.exists(csv_path):
        print(f"ERROR: No se encontró el archivo {csv_path}")
        return

    with transaction.atomic():
        # 1. Leer el CSV
        with open(csv_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            filas_csv = list(reader)
        print(f"Total filas leídas del CSV: {len(filas_csv)}")

        # 2. Desactivar temporalmente FK checks para reconstruir la tabla limpiamente con los IDs exactos del CSV
        with connection.cursor() as cursor:
            # Crear tabla temporal o mapear registros viejos a los nuevos códigos
            # Venta: tipo__codigo actual -> nuevo codigo
            # FA -> 001
            # FB -> 006
            # CA -> 003
            # CB -> 008
            # PRE / SC -> PRE

            # Primero desvinculamos temporalmente ventas y compras para reasignar por código
            cursor.execute("""
                CREATE TEMP TABLE temp_venta_map AS
                SELECT v.ventas_id, tc.codigo as cod_ant
                FROM facturacion_venta v
                JOIN facturacion_tipocomprobante tc ON v.tipo_id = tc.id;
            """)
            
            cursor.execute("""
                CREATE TEMP TABLE temp_compra_map AS
                SELECT c.compras_id, tc.codigo as cod_ant
                FROM facturacion_compra c
                JOIN facturacion_tipocomprobante tc ON c.tipo_id = tc.id;
            """)

            cursor.execute("UPDATE facturacion_venta SET tipo_id = NULL;")
            cursor.execute("UPDATE facturacion_compra SET tipo_id = NULL;")

            # 3. Vaciar y repoblar facturacion_tipocomprobante con los datos del CSV
            cursor.execute("DELETE FROM facturacion_tipocomprobante;")
            
            for r in filas_csv:
                tipo_id = int(r['id'])
                codigo = str(r['codigo']).strip()
                detalle = str(r['detalle']).strip()
                signo = int(r['signo'])
                estado = (str(r['estado']).strip().lower() in ['true', '1', 't'])
                
                cursor.execute("""
                    INSERT INTO facturacion_tipocomprobante (id, codigo, detalle, signo, estado)
                    VALUES (%s, %s, %s, %s, %s);
                """, [tipo_id, codigo, detalle, signo, estado])
            
            print("OK: 91 Tipos de comprobante insertados en la base de datos.")

            # Reiniciar secuencia
            cursor.execute("""
                SELECT setval(pg_get_serial_sequence('facturacion_tipocomprobante', 'id'), COALESCE(max(id), 1)) 
                FROM facturacion_tipocomprobante;
            """)

            # 4. Reasignar Ventas a los nuevos tipos
            # Mapeo: FA -> 001, FB -> 006, CA -> 003, CB -> 008, PRE -> PRE, SC -> PRE
            map_codigos = {
                'FA': '001',
                'FB': '006',
                'CA': '003',
                'CB': '008',
                'PRE': 'PRE',
                'SC': 'PRE'
            }

            for cod_ant, cod_nuevo in map_codigos.items():
                cursor.execute("""
                    UPDATE facturacion_venta v
                    SET tipo_id = (SELECT id FROM facturacion_tipocomprobante WHERE codigo = %s)
                    FROM temp_venta_map m
                    WHERE v.ventas_id = m.ventas_id AND m.cod_ant = %s;
                """, [cod_nuevo, cod_ant])
                print(f"Ventas reasignadas de {cod_ant} a {cod_nuevo}: {cursor.rowcount}")

            # 5. Reasignar Compras a los nuevos tipos
            for cod_ant, cod_nuevo in map_codigos.items():
                cursor.execute("""
                    UPDATE facturacion_compra c
                    SET tipo_id = (SELECT id FROM facturacion_tipocomprobante WHERE codigo = %s)
                    FROM temp_compra_map m
                    WHERE c.compras_id = m.compras_id AND m.cod_ant = %s;
                """, [cod_nuevo, cod_ant])
                print(f"Compras reasignadas de {cod_ant} a {cod_nuevo}: {cursor.rowcount}")

    print("\n=== VERIFICACIÓN DE VENTAS CON NUEVOS TIPOS ===")
    from django.db.models import Count
    ventas_final = Venta.objects.values('tipo_id', 'tipo__codigo', 'tipo__detalle').annotate(total=Count('ventas_id')).order_by('tipo__codigo')
    for v in ventas_final:
        print(f"  Tipo ID: {v['tipo_id']} | Código: {v['tipo__codigo']} ({v['tipo__detalle']}) -> {v['total']} comprobantes")

    print("\n=== VERIFICACIÓN DE COMPRAS CON NUEVOS TIPOS ===")
    compras_final = Compra.objects.values('tipo_id', 'tipo__codigo', 'tipo__detalle').annotate(total=Count('compras_id')).order_by('tipo__codigo')
    for c in compras_final:
        print(f"  Tipo ID: {c['tipo_id']} | Código: {c['tipo__codigo']} ({c['tipo__detalle']}) -> {c['total']} comprobantes")

if __name__ == '__main__':
    migrar_tipos_comprobante()
