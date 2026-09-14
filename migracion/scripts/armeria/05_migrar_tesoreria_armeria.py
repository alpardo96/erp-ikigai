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
from tesoreria.models import OrdenPago, Recibo, OrdenPagoAplicacion, ReciboAplicacion, Caja, CajaSesion
from facturacion.models import Compra, Venta, ClienteProveedor
from contable.models import Asiento
from django.contrib.auth import get_user_model

User = get_user_model()

def parse_decimal(value):
    if value is None: return Decimal('0.00')
    try: return Decimal(str(value))
    except: return Decimal('0.00')

def safe_int(value, default=0):
    try:
        if not value: return default
        if isinstance(value, str):
            value = ''.join(c for c in value if c.isdigit())
        return int(value) if value else default
    except (ValueError, TypeError):
        return default

def run():
    print("=== FASE 5: TESORERÍA (RECIBOS, ANTICIPOS DE ARMAS Y ÓRDENES DE PAGO) ===")
    dir_balance = r'D:\jm_soft\net_balances\eje_255'
    dir_comercio = r'D:\jm_soft\net_comercio\eje_255'
    
    empresa = Empresa.objects.get(id=1)
    sucursal_central = Sucursal.objects.get(id=1)
    sucursal_yb = Sucursal.objects.get(id=2)
    ejercicio = Ejercicio.objects.get(id=1)
    user = User.objects.get(username='ikigai')
    
    valid_entidades = set(ClienteProveedor.objects.filter(empresa=empresa).values_list('codigo_id', flat=True))
    default_entidad = list(valid_entidades)[0] if valid_entidades else None
    
    caja_central = Caja.objects.filter(empresa=empresa, sucursal=sucursal_central).first()
    sesion_caja = CajaSesion.objects.filter(caja=caja_central, estado='A').first()
    if not sesion_caja:
        sesion_caja = CajaSesion.objects.create(
            caja=caja_central,
            usuario=user,
            saldo_inicial=Decimal('0.00'),
            estado='A',
            creado_por=user,
            modificado_por=user
        )

    # 1. Órdenes de Pago (eje_255)
    op_dbf = os.path.join(dir_balance, 'ord_pago.dbf')
    if os.path.exists(op_dbf):
        table_op = DBF(op_dbf, ignore_missing_memofile=True, encoding='latin1')
        ops_to_create = []
        for row in table_op:
            prov_id = row.get('ID_COD')
            if prov_id not in valid_entidades:
                prov_id = default_entidad
                
            punto = safe_int(row.get('PUNTO'), 1)
            suc = sucursal_yb if punto == 6 else sucursal_central

            ops_to_create.append(OrdenPago(
                id=row['ID_OP'],
                empresa=empresa,
                sucursal=suc,
                ejercicio=ejercicio,
                sesion_caja=sesion_caja,
                tipo='P',
                proveedor_id=prov_id,
                fecha=row.get('FECHA') or ejercicio.inicio,
                punto=punto,
                numero=safe_int(row.get('NUMERO'), row['ID_OP']),
                total=parse_decimal(row.get('IMPORTE')),
                observaciones=str(row.get('DETALLE', '')).strip()[:200],
                condic=row.get('CONDIC', 1),
                asiento_id=row.get('ID_ASTO') if row.get('ID_ASTO', 0) > 0 else None,
                creado_por=user,
                modificado_por=user
            ))
            
        OrdenPago.objects.bulk_create(ops_to_create, ignore_conflicts=True, batch_size=1000)
        print(f"OK: {len(ops_to_create)} Órdenes de Pago procesadas.")

    # 2. Recibos a Clientes (RC desde Balance eje_255)
    rec_dbf = os.path.join(dir_balance, 'recibos.dbf')
    recs_to_create = []
    rec_ids_procesados = set()
    
    if os.path.exists(rec_dbf):
        table_rec = DBF(rec_dbf, ignore_missing_memofile=True, encoding='latin1')
        for row in table_rec:
            cli_id = row.get('ID_COD')
            if cli_id not in valid_entidades:
                cli_id = default_entidad
                
            punto = safe_int(row.get('PUNTO'), 1)
            suc = sucursal_yb if punto == 6 else sucursal_central
            id_rec = row['ID_REC']
            rec_ids_procesados.add(id_rec)

            recs_to_create.append(Recibo(
                id=id_rec,
                empresa=empresa,
                sucursal=suc,
                ejercicio=ejercicio,
                sesion_caja=sesion_caja,
                tipo='C',
                cliente_id=cli_id,
                fecha=row.get('FECHA') or ejercicio.inicio,
                punto=punto,
                numero=safe_int(row.get('NUMERO'), id_rec),
                total=parse_decimal(row.get('IMPORTE')),
                observaciones=str(row.get('DETALLE', '')).strip()[:200],
                condic=row.get('CONDIC', 1),
                asiento_id=row.get('ID_ASTO') if row.get('ID_ASTO', 0) > 0 else None,
                creado_por=user,
                modificado_por=user
            ))
            
        print(f"OK: {len(recs_to_create)} Recibos de cobranza (RC) preparados desde Balance.")

    # 3. Anticipos por Reserva de Armas (RV desde Comercio eje_255)
    vta_enc_255 = os.path.join(dir_comercio, 'ventas_enc.dbf')
    cant_rv = 0
    if os.path.exists(vta_enc_255):
        t_vta = DBF(vta_enc_255, ignore_missing_memofile=True, encoding='latin1')
        current_next_rec_id = (max(rec_ids_procesados) + 1) if rec_ids_procesados else 100000
        
        for row in t_vta:
            if str(row.get('TIPO', '')).strip().upper() == 'RV':
                cli_id = row.get('ID_COD')
                if cli_id not in valid_entidades:
                    cli_id = default_entidad
                
                punto = safe_int(row.get('PUNTO'), 1)
                suc = sucursal_yb if punto == 6 else sucursal_central
                num = safe_int(row.get('NUMERO'), row.get('ID_VTA', 0))

                recs_to_create.append(Recibo(
                    id=current_next_rec_id,
                    empresa=empresa,
                    sucursal=suc,
                    ejercicio=ejercicio,
                    sesion_caja=sesion_caja,
                    tipo='C',
                    cliente_id=cli_id,
                    fecha=row.get('FECHA') or ejercicio.inicio,
                    punto=punto,
                    numero=num,
                    total=parse_decimal(row.get('TOTAL')),
                    observaciones=f"ANTICIPO RESERVA DE ARMA (VTA ORIG: {row.get('ID_VTA')})",
                    condic=row.get('CONDIC', 1),
                    asiento_id=row.get('ID_ASTO') if row.get('ID_ASTO', 0) > 0 else None,
                    creado_por=user,
                    modificado_por=user
                ))
                current_next_rec_id += 1
                cant_rv += 1
                
        print(f"OK: {cant_rv} Anticipos por Reserva de Armas (RV) migrados a Recibos de Tesorería.")

    if recs_to_create:
        Recibo.objects.bulk_create(recs_to_create, ignore_conflicts=True, batch_size=1000)
        print(f"OK: {len(recs_to_create)} Total de Recibos insertados en PostgreSQL.")

    # 4. Aplicaciones (ord_pago_facturas.dbf)
    op_fact_dbf = os.path.join(dir_balance, 'ord_pago_facturas.dbf')
    if os.path.exists(op_fact_dbf):
        table_opf = DBF(op_fact_dbf, ignore_missing_memofile=True, encoding='latin1')
        op_aplic_to_create = []
        rec_aplic_to_create = []
        
        valid_ops = set(OrdenPago.objects.filter(empresa=empresa).values_list('id', flat=True))
        valid_recs = set(Recibo.objects.filter(empresa=empresa).values_list('id', flat=True))
        
        map_compras_asto = {c.asiento_id: c.compras_id for c in Compra.objects.filter(empresa=empresa, asiento_id__isnull=False)}
        map_ventas_asto = {v.asiento_id: v.ventas_id for v in Venta.objects.filter(empresa=empresa, asiento_id__isnull=False)}
        
        for row in table_opf:
            id_op = row.get('ID_OP', 0)
            id_rec = row.get('ID_REC', 0)
            id_asto = row.get('ID_ASTO', 0)
            importe = parse_decimal(row.get('PAGA'))
            
            if id_op > 0 and id_op in valid_ops:
                c_id = map_compras_asto.get(id_asto)
                if c_id:
                    op_aplic_to_create.append(OrdenPagoAplicacion(
                        orden_pago_id=id_op, compra_id=c_id, importe=importe, importe_pesos=importe
                    ))
            
            if id_rec > 0 and id_rec in valid_recs:
                v_id = map_ventas_asto.get(id_asto)
                if v_id:
                    rec_aplic_to_create.append(ReciboAplicacion(
                        recibo_id=id_rec, venta_id=v_id, importe=importe, importe_pesos=importe
                    ))
                
        if op_aplic_to_create:
            OrdenPagoAplicacion.objects.bulk_create(op_aplic_to_create, ignore_conflicts=True, batch_size=2000)
            print(f"OK: {len(op_aplic_to_create)} Aplicaciones de Órdenes de Pago procesadas.")
        if rec_aplic_to_create:
            ReciboAplicacion.objects.bulk_create(rec_aplic_to_create, ignore_conflicts=True, batch_size=2000)
            print(f"OK: {len(rec_aplic_to_create)} Aplicaciones de Recibos procesadas.")

    print("Fase 5 completada con éxito.")

if __name__ == '__main__':
    run()
