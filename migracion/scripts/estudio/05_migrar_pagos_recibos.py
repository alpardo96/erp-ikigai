import os
import sys
import django
from decimal import Decimal
from datetime import datetime
from dbfread import DBF

# Configurar el entorno de Django
import pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent.parent))
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
    print("Iniciando Fase 5: Tesorería - Órdenes de Pago y Recibos (Estudio)...")
    dir_path = r'D:\OneDrive\Escritorio\Migracion\Estudio\eje_272'
    
    empresa = Empresa.objects.get(id=1)
    sucursal = Sucursal.objects.get(id=1)
    ejercicios = list(Ejercicio.objects.filter(empresa=empresa).order_by('inicio'))
    ejercicio_default = ejercicios[-1] if ejercicios else None

    def resolver_ejercicio(fecha_doc):
        if not fecha_doc:
            return ejercicio_default
        for ej in ejercicios:
            if ej.inicio <= fecha_doc <= ej.cierre:
                return ej
        return ejercicio_default
        
    valid_entidades = set(ClienteProveedor.objects.filter(empresa=empresa).values_list('codigo_id', flat=True))
    default_entidad = ClienteProveedor.objects.filter(empresa=empresa).first()
    
    default_caja = CajaSesion.objects.first()
    valid_cajas = set(CajaSesion.objects.values_list('id', flat=True))
    asientos_validos = set(Asiento.objects.filter(empresa=empresa).values_list('asiento_id', flat=True))
    
    # 1. Órdenes de Pago
    op_dbf = os.path.join(dir_path, 'ord_pago.dbf')
    if os.path.exists(op_dbf):
        table = DBF(op_dbf, ignore_missing_memofile=True, encoding='latin1')
        ops_to_create = []
        
        for row in table:
            prov_id = row.get('ID_COD')
            if prov_id not in valid_entidades:
                prov_id = default_entidad.codigo_id if default_entidad else None
                    
            if not prov_id:
                continue
                
            caja_id = row.get('CAJA')
            if caja_id not in valid_cajas:
                caja_id = default_caja.id if default_caja else None
                
            fecha = row.get('FECHA') or (ejercicio_default.inicio if ejercicio_default else datetime(2026, 6, 1).date())
            ej = resolver_ejercicio(fecha)
            
            asiento_id = row.get('ID_ASTO')
            if asiento_id not in asientos_validos:
                asiento_id = None
                
            ops_to_create.append(OrdenPago(
                id=row['ID_OP'],
                empresa=empresa,
                sucursal=sucursal,
                ejercicio=ej,
                sesion_caja_id=caja_id,
                tipo='P',
                proveedor_id=prov_id,
                fecha=fecha,
                punto=safe_int(row.get('PUNTO'), 1),
                numero=safe_int(row.get('NUMERO'), row['ID_OP']),
                total=parse_decimal(row.get('IMPORTE') or row.get('EFECTIVO')),
                observaciones=str(row.get('DETALLE', ''))[:200],
                condic=int(row.get('CONDIC', 1) or 1),
                asiento_id=asiento_id
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
                cli_id = default_entidad.codigo_id if default_entidad else None
                    
            if not cli_id:
                continue
                
            caja_id = row.get('CAJA')
            if caja_id not in valid_cajas:
                caja_id = default_caja.id if default_caja else None
                
            fecha = row.get('FECHA') or (ejercicio_default.inicio if ejercicio_default else datetime(2026, 6, 1).date())
            ej = resolver_ejercicio(fecha)
            
            asiento_id = row.get('ID_ASTO')
            if asiento_id not in asientos_validos:
                asiento_id = None
                
            recs_to_create.append(Recibo(
                id=row['ID_REC'],
                empresa=empresa,
                sucursal=sucursal,
                ejercicio=ej,
                sesion_caja_id=caja_id,
                tipo='C',
                cliente_id=cli_id,
                fecha=fecha,
                punto=safe_int(row.get('PUNTO'), 1),
                numero=safe_int(row.get('NUMERO'), row['ID_REC']),
                total=parse_decimal(row.get('IMPORTE') or row.get('EFECTIVO')),
                observaciones=str(row.get('DETALLE', ''))[:200],
                condic=int(row.get('CONDIC', 1) or 1),
                asiento_id=asiento_id
            ))
            
        Recibo.objects.bulk_create(recs_to_create, ignore_conflicts=True, batch_size=1000)
        print(f"OK {len(recs_to_create)} Recibos procesados.")

    # 3. Aplicaciones (ord_pago_facturas.dbf)
    op_fact_dbf = os.path.join(dir_path, 'ord_pago_facturas.dbf')
    if os.path.exists(op_fact_dbf):
        table = DBF(op_fact_dbf, ignore_missing_memofile=True, encoding='latin1')
        
        op_aplic_to_create = []
        rec_aplic_to_create = []
        
        compras_map = {c.asiento_id: c.compras_id for c in Compra.objects.filter(empresa=empresa, asiento_id__isnull=False)}
        ventas_map = {v.asiento_id: v.ventas_id for v in Venta.objects.filter(empresa=empresa, asiento_id__isnull=False)}
        
        valid_ops = set(OrdenPago.objects.filter(empresa=empresa).values_list('id', flat=True))
        valid_recs = set(Recibo.objects.filter(empresa=empresa).values_list('id', flat=True))
        
        for row in table:
            id_op = row.get('ID_OP', 0)
            id_rec = row.get('ID_REC', 0)
            id_asto = row.get('ID_ASTO', 0)
            importe = parse_decimal(row.get('PAGA') or row.get('NETO'))
            
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
