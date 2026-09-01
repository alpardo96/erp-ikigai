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
from tesoreria.models import Banco, CuentaBancaria, Tarjeta, Caja, CajaSesion, MovimientoCaja
from contable.models import Cuenta
from django.contrib.auth import get_user_model

User = get_user_model()

def parse_decimal(value):
    if value is None:
        return Decimal('0.00')
    return Decimal(str(value))

def run():
    print("Iniciando Fase 3: Bloque Tesorería y Flujos")
    dir_path = r'D:\OneDrive\Escritorio\Migracion\eje_272'
    
    empresa = Empresa.objects.get(id=1)
    sucursal = Sucursal.objects.get(id=1)
    ejercicio = Ejercicio.objects.get(id=1)
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
    if os.path.exists(cta_cte_dbf):
        table = DBF(cta_cte_dbf, ignore_missing_memofile=True, encoding='latin1')
        ctas_to_create = []
        for row in table:
            banco_nombre = bancos_dict.get(row.get('COD_BCO'), 'Banco Migrado')
            ctas_to_create.append(CuentaBancaria(
                cta_bc_id=row['CODIGO'],
                empresa=empresa,
                banco=banco_nombre,
                moneda='PES',
                cta_numero=str(row.get('DETALLE', ''))[:100],
                cbu=str(row.get('CBU', ''))[:100],
                cuenta_contable_id=row.get('ID_CTA'),
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
            sesiones_to_create.append(CajaSesion(
                id=row['CAJA'],
                caja=caja_tesoreria,
                usuario=user,
                fecha_apertura=row.get('FECHA') or ejercicio.inicio,
                fecha_cierre=row.get('FECHA') or ejercicio.inicio,
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
    # Aca el dbf tiene los detalles: CAJA_MOV, CAJA, FECHA, ID_CON, DETALLE, ENTRADA, SALIDA
    caja_mov_dbf = os.path.join(dir_path, 'caja_diaria.dbf')
    if os.path.exists(caja_mov_dbf):
        table = DBF(caja_mov_dbf, ignore_missing_memofile=True, encoding='latin1')
        movs_to_create = []
        valid_sesiones = set(CajaSesion.objects.values_list('id', flat=True))

        # Plan 049: `caja_diaria` ya trae los tres vínculos que antes se descartaban.
        #   ID_CTA  -> Cuenta (por `codigo`, que es el código legado del plan de cuentas)
        #   ID_COD  -> ClienteProveedor (su PK `codigo_id` conserva el código legado)
        #   ID_ASTO -> Asiento
        # Se validan contra lo ya migrado: lo que no resuelve queda en null en vez de romper.
        from facturacion.models import ClienteProveedor
        from contable.models import Asiento
        cuentas_por_codigo = dict(
            Cuenta.objects.filter(empresa=empresa).exclude(codigo=None)
            .values_list('codigo', 'id'))
        clipro_validos = set(ClienteProveedor.objects.values_list('codigo_id', flat=True))
        asientos_validos = set(Asiento.objects.values_list('asiento_id', flat=True))

        # El layout del DBF varía entre versiones del sistema legado: en `eje_236` las columnas
        # son INGRESOS/EGRESOS/CONCEPTO/CONDIC, en otras ENTRADA/SALIDA/DETALLE/ID_CON.
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

            # Determinar tipo
            tipo = 'I'
            importe = entrada
            if salida > 0:
                tipo = 'E'
                importe = salida

            # `fecha` es obligatoria y es la del comprobante: en el legado ya viene así.
            fecha_mov = col(row, 'FECHA')
            if not fecha_mov:
                continue

            condic = int(col(row, 'CONDIC', 'ID_CON', default=1) or 1)
            if condic not in (1, 2):
                # Un movimiento de fondos solo puede ser Real o Presupuestado; el resto no
                # debería existir en caja_diaria y lo rechazaría el CheckConstraint.
                condic = 1

            asiento_legado = col(row, 'ID_ASTO')
            cli_pro_legado = col(row, 'ID_COD')

            movs_to_create.append(MovimientoCaja(
                id=row['ID_CAJ'],
                sesion_id=caja_id,
                empresa=empresa,
                fecha=fecha_mov,
                tipo=tipo,
                importe=importe,
                concepto=str(col(row, 'CONCEPTO', 'DETALLE', default='') or '')[:200],
                condic=condic,
                cuenta_id=cuentas_por_codigo.get(col(row, 'ID_CTA')),
                cli_pro_id=cli_pro_legado if cli_pro_legado in clipro_validos else None,
                asiento_id=asiento_legado if asiento_legado in asientos_validos else None,
                creado_por=user
            ))

        MovimientoCaja.objects.bulk_create(movs_to_create, ignore_conflicts=True, batch_size=2000)
        print(f"OK {len(movs_to_create)} Movimientos de Caja procesados.")

    print("Fase 3 completada con éxito.")

if __name__ == '__main__':
    run()
