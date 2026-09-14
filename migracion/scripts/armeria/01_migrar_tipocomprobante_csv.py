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

from facturacion.models import TipoComprobante

def migrar_tipos_comprobante():
    print("=== FASE 1: MIGRACIÓN DE TIPOS DE COMPROBANTES OFICIALES ARCA ===")
    csv_path = r"d:\borrador\facturacion_tipocomprobante.csv"
    
    if not os.path.exists(csv_path):
        print(f"ERROR: No se encontró el archivo {csv_path}")
        return

    with transaction.atomic():
        with open(csv_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            filas_csv = list(reader)
        print(f"Total filas leídas del CSV: {len(filas_csv)}")

        with connection.cursor() as cursor:
            # Reconstruir facturacion_tipocomprobante con IDs exactos del CSV
            for r in filas_csv:
                tipo_id = int(r['id'])
                codigo = str(r['codigo']).strip()
                detalle = str(r['detalle']).strip()
                signo = int(r['signo'])
                estado = (str(r['estado']).strip().lower() in ['true', '1', 't'])
                
                cursor.execute("""
                    INSERT INTO facturacion_tipocomprobante (id, codigo, detalle, signo, estado)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        codigo = EXCLUDED.codigo,
                        detalle = EXCLUDED.detalle,
                        signo = EXCLUDED.signo,
                        estado = EXCLUDED.estado;
                """, [tipo_id, codigo, detalle, signo, estado])
            
            # Ajustar la secuencia en PostgreSQL
            cursor.execute("""
                SELECT setval(pg_get_serial_sequence('facturacion_tipocomprobante', 'id'), COALESCE(max(id), 1)) 
                FROM facturacion_tipocomprobante;
            """)
            print(f"OK: {len(filas_csv)} Tipos de comprobante sincronizados con éxito.")

if __name__ == '__main__':
    migrar_tipos_comprobante()
