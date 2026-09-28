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
from tesoreria.models import (
    Banco, CuentaBancaria, Tarjeta, Caja, CajaSesion, MovimientoCaja,
    ValorTerceros, TransaccionBancaria, CobroTarjeta
)
from contable.models import Cuenta, Asiento
from facturacion.models import ClienteProveedor
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
    print("Iniciando Fase 3: Bloque Tesorería y Flujos (Estudio)...")
    dir_path = r'D:\OneDrive\Escritorio\Migracion\Estudio\eje_272'
    
    empresa = Empresa.objects.get(id=1)
    sucursal = Sucursal.objects.get(id=1)
    ejercicios = list(Ejercicio.objects.filter(empresa=empresa).order_by('inicio'))
    ejercicio_default = ejercicios[-1] if ejercicios else None
    user = User.objects.get(username='Ikigai')
    
    caja_tesoreria = Caja.objects.get(id=1) # Creada en Fase 0

    # 1. Bancos
    bancos_dbf = os.path.join(dir_path, 'bancos.dbf')
    bancos_dict = {}
    if os.path.exists(bancos_dbf):
        table = DBF(bancos_dbf, ignore_missing_memofile=True, encoding='latin1')
        bancos_to_create = []
        for row in table:
            banco = Banco(
                id=row['CODIGO'],
                nombre=row.get('DETALLE', '')[:150]
            )
            bancos_to_create.append(banco)
            bancos_dict[row['CODIGO']] = banco.nombre
        Banco.objects.bulk_create(bancos_to_create, ignore_conflicts=True)
        print(f"OK {len(bancos_to_create)} Bancos procesados.")

    # 2. Cuentas Bancarias
    cta_cte_dbf = os.path.join(dir_path, 'cta_cte.dbf')
    cuentas_validas = set(Cuenta.objects.filter(empresa=empresa).values_list('id', flat=True))
    
    if os.path.exists(cta_cte_dbf):
        table = DBF(cta_cte_dbf, ignore_missing_memofile=True, encoding='latin1')
        ctas_to_create = []
        for row in table:
            banco_nombre = bancos_dict.get(row.get('COD_BCO'), 'Banco Migrado')
            cta_contable_id = row.get('ID_CTA')
            if cta_contable_id not in cuentas_validas:
                cta_contable_id = None
                
            ctas_to_create.append(CuentaBancaria(
                cta_bc_id=row['CODIGO'],
                empresa=empresa,
                banco=banco_nombre,
                moneda='PES',
                cta_numero=str(row.get('DETALLE', ''))[:100],
                cbu=str(row.get('CBU', ''))[:100],
                cuenta_contable_id=cta_contable_id,
                creado_por=user
            ))
        CuentaBancaria.objects.bulk_create(ctas_to_create, ignore_conflicts=True)
        print(f"OK {len(ctas_to_create)} Cuentas Bancarias procesadas.")

    # 3. Tarjetas
    tarjetas_dbf = os.path.join(dir_path, 'tarjetas.dbf')
    if os.path.exists(tarjetas_dbf):
        table = DBF(tarjetas_dbf, ignore_missing_memofile=True, encoding='latin1')
        tarjetas_to_create = []
        for row in table:
            tarjetas_to_create.append(Tarjeta(
                id=row['CODIGO'],
                codigo=str(row['CODIGO']),
                nombre=row.get('DETALLE', '')[:100],
                tipo='C' if 'CREDITO' in str(row.get('TIPO', '')).upper() else 'D'
            ))
        Tarjeta.objects.bulk_create(tarjetas_to_create, ignore_conflicts=True)
        print(f"OK {len(tarjetas_to_create)} Tarjetas procesadas.")

    # 4. Caja Diaria (Sesiones de Caja)
    enc_caja_dbf = os.path.join(dir_path, 'enc_caja_diaria.dbf')
    if os.path.exists(enc_caja_dbf):
        table = DBF(enc_caja_dbf, ignore_missing_memofile=True, encoding='latin1')
        sesiones_to_create = []
        for row in table:
            fec = row.get('FECHA') or (ejercicio_default.inicio if ejercicio_default else datetime(2026, 6, 1).date())
            sesiones_to_create.append(CajaSesion(
                id=row['CAJA'],
                caja=caja_tesoreria,
                usuario=user,
                fecha_apertura=fec,
                fecha_cierre=fec,
                estado='C', # Todas cerradas
                numero=row['CAJA'],
                fecha_operativa=row.get('FECHA'),
                si_efectivo=parse_decimal(row.get('SI_EFE')),
                si_dolares=parse_decimal(row.get('SI_BCO')),
                si_valores=parse_decimal(row.get('SI_VAL')),
                sf_efectivo=parse_decimal(row.get('SDO_EFE')),
                sf_dolares=parse_decimal(row.get('SDO_BCO')),
                sf_valores=parse_decimal(row.get('SDO_VAL')),
                saldo_inicial=parse_decimal(row.get('SI')),
                saldo_final_calculado=parse_decimal(row.get('SALDO')),
                saldo_final_declarado=parse_decimal(row.get('SALDO')),
                creado_por=user
            ))
        CajaSesion.objects.bulk_create(sesiones_to_create, ignore_conflicts=True)
        print(f"OK {len(sesiones_to_create)} Sesiones de Caja procesadas.")

    # 5. Movimientos Caja (caja_diaria.dbf)
    caja_mov_dbf = os.path.join(dir_path, 'caja_diaria.dbf')
    if os.path.exists(caja_mov_dbf):
        table = DBF(caja_mov_dbf, ignore_missing_memofile=True, encoding='latin1')
        movs_to_create = []
        valid_sesiones = set(CajaSesion.objects.values_list('id', flat=True))
        clipro_validos = set(ClienteProveedor.objects.filter(empresa=empresa).values_list('codigo_id', flat=True))
        asientos_validos = set(Asiento.objects.filter(empresa=empresa).values_list('asiento_id', flat=True))

        def col(row, *nombres, default=None):
            for n in nombres:
                if row.get(n) is not None:
                    return row[n]
            return default

        for row in table:
            caja_id = row.get('CAJA')
            if caja_id not in valid_sesiones:
                continue

            entrada = parse_decimal(col(row, 'INGRESOS', 'ENTRADA'))
            salida = parse_decimal(col(row, 'EGRESOS', 'SALIDA'))

            tipo = 'I'
            importe = entrada
            if salida > 0:
                tipo = 'E'
                importe = salida

            fecha_mov = col(row, 'FECHA')
            if not fecha_mov:
                continue

            condic = safe_int(col(row, 'CONDIC', 'ID_CON'), 1)
            if condic not in (1, 2):
                condic = 1

            asiento_legado = col(row, 'ID_ASTO')
            cli_pro_legado = col(row, 'ID_COD')
            cta_legado = col(row, 'ID_CTA')

            movs_to_create.append(MovimientoCaja(
                id=row['ID_CAJ'],
                sesion_id=caja_id,
                empresa=empresa,
                fecha=fecha_mov,
                tipo=tipo,
                importe=importe,
                concepto=str(col(row, 'CONCEPTO', 'DETALLE', default='') or '')[:200],
                condic=condic,
                cuenta_id=cta_legado if cta_legado in cuentas_validas else None,
                cli_pro_id=cli_pro_legado if cli_pro_legado in clipro_validos else None,
                asiento_id=asiento_legado if asiento_legado in asientos_validos else None,
                creado_por=user
            ))

        MovimientoCaja.objects.bulk_create(movs_to_create, ignore_conflicts=True, batch_size=2000)
        print(f"OK {len(movs_to_create)} Movimientos de Caja procesados.")

    # 6. Valores de Terceros (valores_terceros.dbf)
    vt_dbf = os.path.join(dir_path, 'valores_terceros.dbf')
    if os.path.exists(vt_dbf):
        table = DBF(vt_dbf, ignore_missing_memofile=True, encoding='latin1')
        bancos_validos = set(Banco.objects.values_list('id', flat=True))
        default_banco = Banco.objects.first()
        
        vt_to_create = []
        for row in table:
            banco_id = row.get('ID_BCO')
            if banco_id not in bancos_validos:
                banco_id = default_banco.id if default_banco else None
                
            if not banco_id:
                continue
                
            fec_emision = row.get('FEC_OP_O') or (ejercicio_default.inicio if ejercicio_default else datetime(2026, 6, 1).date())
            fec_vto = row.get('FEC_VTO') or fec_emision
            
            estado = 'C' # Cartera
            if row.get('FEC_OP_D') or (row.get('ID_PRO') and row.get('ID_PRO') > 0):
                estado = 'E' # Entregado
                
            asiento_rec = row.get('ID_ASTO_O')
            if asiento_rec and asiento_rec < 0:
                asiento_rec = abs(asiento_rec)
                
            vt_to_create.append(ValorTerceros(
                id=row['ID_V_T'],
                empresa=empresa,
                banco_id=banco_id,
                numero_cheque=str(row.get('NUMERO', ''))[:50],
                importe=parse_decimal(row.get('IMPORTE')),
                fecha_emision=fec_emision,
                fecha_vencimiento=fec_vto,
                cuit_firmante=str(row.get('CUIT_LIB', ''))[:20],
                nombre_firmante=str(row.get('LIBRADOR', ''))[:100],
                fecha_recepcion=fec_emision,
                asiento_recepcion_id=asiento_rec if asiento_rec and asiento_rec > 0 else None,
                fecha_entrega=row.get('FEC_OP_D'),
                asiento_entrega_id=row.get('ID_ASTO_D') if row.get('ID_ASTO_D', 0) > 0 else None,
                estado=estado
            ))
            
        ValorTerceros.objects.bulk_create(vt_to_create, ignore_conflicts=True, batch_size=1000)
        print(f"OK {len(vt_to_create)} Valores de Terceros (Cheques Cartera) procesados.")

    # 7. Cheques Propios y Transacciones Bancarias (cheques.dbf)
    ch_dbf = os.path.join(dir_path, 'cheques.dbf')
    if os.path.exists(ch_dbf):
        table = DBF(ch_dbf, ignore_missing_memofile=True, encoding='latin1')
        ctas_bancarias_validas = set(CuentaBancaria.objects.filter(empresa=empresa).values_list('cta_bc_id', flat=True))
        default_cta_bc = CuentaBancaria.objects.filter(empresa=empresa).first()
        
        tb_to_create = []
        for row in table:
            cta_bc_id = row.get('ID_CCTE')
            if cta_bc_id not in ctas_bancarias_validas:
                cta_bc_id = default_cta_bc.cta_bc_id if default_cta_bc else None
                
            if not cta_bc_id:
                continue
                
            f_pago = str(row.get('F_PAGO', '')).upper()
            tipo_tx = 'CP' if 'CHEQ' in f_pago or row.get('CHEQ') == 1 else 'TE'
            
            fec_op = row.get('FEC_OP') or (ejercicio_default.inicio if ejercicio_default else datetime(2026, 6, 1).date())
            fec_vto = row.get('FEC_VTO') or fec_op
            
            tb_to_create.append(TransaccionBancaria(
                id=row['ID_CH'],
                empresa=empresa,
                tipo_transaccion=tipo_tx,
                cuenta_bancaria_id=cta_bc_id,
                numero_operacion=str(row.get('NUMERO', ''))[:100],
                importe=parse_decimal(row.get('IMPORTE')),
                fecha_operacion=fec_op,
                fecha_vencimiento=fec_vto,
                estado='D' if row.get('ESTADO') == 'D' else 'E',
                asiento_id=row.get('ID_ASTO') if row.get('ID_ASTO', 0) > 0 else None
            ))
            
        TransaccionBancaria.objects.bulk_create(tb_to_create, ignore_conflicts=True, batch_size=1000)
        print(f"OK {len(tb_to_create)} Transacciones Bancarias (Cheques Propios/Transf) procesadas.")

    print("Fase 3 completada con éxito.")

if __name__ == '__main__':
    run()
