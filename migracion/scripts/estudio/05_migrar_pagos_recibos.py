import os
import sys
import django
from decimal import Decimal
from datetime import datetime
from dbfread import DBF

# Configurar el entorno de Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from empresas.models import Empresa, Sucursal, Ejercicio
from tesoreria.models import OrdenPago, Recibo, OrdenPagoAplicacion, ReciboAplicacion, CajaSesion
from facturacion.models import Compra, Venta, ClienteProveedor
from contable.models import Asiento
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

def run():
    print("Iniciando Fase 5: Tesorería - Órdenes de Pago y Recibos")
    dir_path = r'D:\OneDrive\Escritorio\Migracion\eje_272'
    
    empresa = Empresa.objects.get(id=1)
    sucursal = Sucursal.objects.get(id=1)
    ejercicio = Ejercicio.objects.get(id=1)
    
    # 1. Órdenes de Pago
    op_dbf = os.path.join(dir_path, 'ord_pago.dbf')
    if os.path.exists(op_dbf):
        table = DBF(op_dbf, ignore_missing_memofile=True, encoding='latin1')
        ops_to_create = []
        valid_entidades = set(ClienteProveedor.objects.values_list('codigo_id', flat=True))
        # Algunos IDs de CAJA pueden no existir, agarramos una default por las dudas
        default_caja = CajaSesion.objects.first()
        valid_cajas = set(CajaSesion.objects.values_list('id', flat=True))
        
        for row in table:
            prov_id = row.get('ID_COD')
            if prov_id not in valid_entidades:
                # Fallback a un proveedor válido si no existe (no debería pasar por integridad de DBF pero por las dudas)
                if valid_entidades:
                    prov_id = list(valid_entidades)[0]
                else:
                    prov_id = None
                    
            caja_id = row.get('CAJA')
            if caja_id not in valid_cajas:
                caja_id = default_caja.id if default_caja else None
                
            ops_to_create.append(OrdenPago(
                id=row['ID_OP'],
                empresa=empresa,
                sucursal=sucursal,
                ejercicio=ejercicio,
                sesion_caja_id=caja_id,
                tipo='P',
                proveedor_id=prov_id,
                fecha=row.get('FECHA') or ejercicio.inicio,
                punto=safe_int(row.get('PUNTO'), 1),
                numero=safe_int(row.get('NUMERO'), row['ID_OP']),
                total=parse_decimal(row.get('IMPORTE')),
                observaciones=row.get('DETALLE', '')[:200],
                condic=row.get('CONDIC', 1),
                asiento_id=row.get('ID_ASTO') if row.get('ID_ASTO', 0) > 0 else None
            ))
            
        OrdenPago.objects.bulk_create(ops_to_create, ignore_conflicts=True, batch_size=1000)
        print(f"OK {len(ops_to_create)} Órdenes de Pago procesadas.")

    # 2. Recibos
    rec_dbf = os.path.join(dir_path, 'recibos.dbf')
    if os.path.exists(rec_dbf):
        table = DBF(rec_dbf, ignore_missing_memofile=True, encoding='latin1')
        recs_to_create = []
        
        for row in table:
            cli_id = row.get('ID_COD')
            if cli_id not in valid_entidades:
                if valid_entidades:
                    cli_id = list(valid_entidades)[0]
                else:
                    cli_id = None
                    
            caja_id = row.get('CAJA')
            if caja_id not in valid_cajas:
                caja_id = default_caja.id if default_caja else None
                
            recs_to_create.append(Recibo(
                id=row['ID_REC'],
                empresa=empresa,
                sucursal=sucursal,
                ejercicio=ejercicio,
                sesion_caja_id=caja_id,
                tipo='C',
                cliente_id=cli_id,
                fecha=row.get('FECHA') or ejercicio.inicio,
                punto=safe_int(row.get('PUNTO'), 1),
                numero=safe_int(row.get('NUMERO'), row['ID_REC']),
                total=parse_decimal(row.get('IMPORTE')),
                observaciones=row.get('DETALLE', '')[:200],
                condic=row.get('CONDIC', 1),
                asiento_id=row.get('ID_ASTO') if row.get('ID_ASTO', 0) > 0 else None
            ))
            
        Recibo.objects.bulk_create(recs_to_create, ignore_conflicts=True, batch_size=1000)
        print(f"OK {len(recs_to_create)} Recibos procesados.")

    # 3. Aplicaciones (ord_pago_facturas.dbf)
    # Esta tabla tiene tanto las aplicaciones de OPs (ID_OP) como las de Recibos (ID_REC)
    op_fact_dbf = os.path.join(dir_path, 'ord_pago_facturas.dbf')
    if os.path.exists(op_fact_dbf):
        table = DBF(op_fact_dbf, ignore_missing_memofile=True, encoding='latin1')
        
        op_aplic_to_create = []
        rec_aplic_to_create = []
        
        # Mapeos rapidos
        compras_map = {c.asiento_id: c.compras_id for c in Compra.objects.filter(asiento_id__isnull=False)}
        ventas_map = {v.asiento_id: v.ventas_id for v in Venta.objects.filter(asiento_id__isnull=False)}
        
        valid_ops = set(OrdenPago.objects.values_list('id', flat=True))
        valid_recs = set(Recibo.objects.values_list('id', flat=True))
        
        for row in table:
            id_op = row.get('ID_OP', 0)
            id_rec = row.get('ID_REC', 0)
            id_asto = row.get('ID_ASTO', 0)
            importe = parse_decimal(row.get('PAGA')) # 'PAGA' parece ser el campo con el importe pagado
            
            if id_op > 0 and id_op in valid_ops and id_asto in compras_map:
                op_aplic_to_create.append(OrdenPagoAplicacion(
                    orden_pago_id=id_op,
                    compra_id=compras_map[id_asto],
                    importe=importe,
                    importe_pesos=importe
                ))
            
            if id_rec > 0 and id_rec in valid_recs and id_asto in ventas_map:
                rec_aplic_to_create.append(ReciboAplicacion(
                    recibo_id=id_rec,
                    venta_id=ventas_map[id_asto],
                    importe=importe,
                    importe_pesos=importe
                ))
                
        if op_aplic_to_create:
            OrdenPagoAplicacion.objects.bulk_create(op_aplic_to_create, ignore_conflicts=True, batch_size=2000)
            print(f"OK {len(op_aplic_to_create)} Aplicaciones de Órdenes de Pago procesadas.")
        if rec_aplic_to_create:
            ReciboAplicacion.objects.bulk_create(rec_aplic_to_create, ignore_conflicts=True, batch_size=2000)
            print(f"OK {len(rec_aplic_to_create)} Aplicaciones de Recibos procesadas.")

    print("Fase 5 completada con éxito.")

if __name__ == '__main__':
    run()
