import os
import sys
import django
from decimal import Decimal
from dbfread import DBF
import pathlib

# Configurar el entorno de Django
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from empresas.models import Empresa
from facturacion.models import ClienteProveedor, TipoComprobante, Jurisdiccion
from contable.models import Cuenta, ParametrosContables, AlicuotaIva

def parse_decimal(value):
    if value is None:
        return Decimal('0.00')
    return Decimal(str(value))

def get_tipo_cuenta(jerarquia):
    if not jerarquia:
        return 'R'
    first_digit = str(jerarquia)[0]
    mapping = {'1': 'A', '2': 'P', '3': 'N', '4': 'R', '5': 'R'}
    return mapping.get(first_digit, 'R')

def get_condicion_iva(insc_iva):
    mapping = {
        1: 'RESPONSABLE INSCRIPTO',
        2: 'MONOTRIBUTO',
        3: 'EXENTO',
        4: 'CONSUMIDOR FINAL'
    }
    return mapping.get(insc_iva, 'CONSUMIDOR FINAL')

def run():
    print("Iniciando Fase 1: Bloque Maestros y Parámetros (Armería)")
    
    dir_comercio = r'D:\OneDrive\Escritorio\Migracion\Armeria\Comercio\eje_255'
    dir_balance = r'D:\OneDrive\Escritorio\Migracion\Armeria\Balance\eje_255'
    
    empresa = Empresa.objects.get(id=1)

    # 1. Cuentas Contables (desde Balance)
    cuentas_dbf = os.path.join(dir_balance, 'cuentas.dbf')
    if os.path.exists(cuentas_dbf):
        table = DBF(cuentas_dbf, ignore_missing_memofile=True, encoding='latin1')
        cuentas_to_create = []
        for row in table:
            sumariza_id = row.get('SUMARIZA')
            if sumariza_id == 0:
                sumariza_id = None
                
            cuentas_to_create.append(Cuenta(
                id=row['CODIGO'],
                empresa=empresa,
                jerarquia=row.get('JERA_CTA', ''),
                cuenta=row.get('DETALLE', '')[:200],
                imputable=True if row.get('IMPUTABLE') else False,
                tipo=get_tipo_cuenta(row.get('JERA_CTA', '')),
                sumariza_id=sumariza_id
            ))
        Cuenta.objects.bulk_create(cuentas_to_create, ignore_conflicts=True)
        print(f"OK {len(cuentas_to_create)} cuentas procesadas.")

    # 2. Jurisdicciones (Provincias desde Balance)
    provincias_dbf = os.path.join(dir_balance, 'provincias.dbf')
    if os.path.exists(provincias_dbf):
        table = DBF(provincias_dbf, ignore_missing_memofile=True, encoding='latin1')
        juris_to_create = []
        for row in table:
            juris_to_create.append(Jurisdiccion(
                id=row['CODIGO'],
                codigo=row['CODIGO'],
                nombre=row.get('DETALLE', '')[:100]
            ))
        Jurisdiccion.objects.bulk_create(juris_to_create, ignore_conflicts=True)
        print(f"OK {len(juris_to_create)} jurisdicciones procesadas.")

    # 3. Alícuotas IVA (desde Balance)
    alicuotas_dbf = os.path.join(dir_balance, 'alicuotas_iva.dbf')
    if os.path.exists(alicuotas_dbf):
        table = DBF(alicuotas_dbf, ignore_missing_memofile=True, encoding='latin1')
        alics_to_create = []
        for row in table:
            alics_to_create.append(AlicuotaIva(
                codigo=str(row['COD_ALIC']),
                descripcion=f"Alícuota {row.get('ALICUOTA')}%",
                porcentaje=parse_decimal(row.get('ALICUOTA'))
            ))
        AlicuotaIva.objects.bulk_create(alics_to_create, ignore_conflicts=True)
        print(f"OK {len(alics_to_create)} alícuotas IVA procesadas.")

    # 4. Tipos de Comprobante (desde Balance)
    comprobantes_dbf = os.path.join(dir_balance, 'comprobantes.dbf')
    if os.path.exists(comprobantes_dbf):
        table = DBF(comprobantes_dbf, ignore_missing_memofile=True, encoding='latin1')
        tc_to_create = []
        for row in table:
            tc_to_create.append(TipoComprobante(
                codigo=row.get('CODIGO', '')[:2],
                detalle=row.get('DETALLE', '')[:100],
                signo=1,
                estado=True
            ))
        TipoComprobante.objects.bulk_create(tc_to_create, ignore_conflicts=True)
        print("OK Tipos de Comprobantes procesados.")

    # 5. Clientes y Proveedores (Merge Comercio + Balance)
    clipro_comercio_dbf = os.path.join(dir_comercio, 'cli_pro.dbf')
    clipro_balance_dbf = os.path.join(dir_balance, 'cli_pro.dbf')
    
    entidades_dict = {}

    # Primero cargamos todo lo de Comercio (Base)
    if os.path.exists(clipro_comercio_dbf):
        table_comercio = DBF(clipro_comercio_dbf, ignore_missing_memofile=True, encoding='latin1')
        for row in table_comercio:
            codigo = row['CODIGO']
            entidades_dict[codigo] = {
                'codigo_id': codigo,
                'empresa': empresa,
                'razon_social': row.get('DETALLE', '')[:200],
                'cuit': str(row.get('CUIT', '')).strip(),
                'tipo_entidad': 2 if str(row.get('CLI_PRO', '')).strip() == '2' else 1,
                'domicilio': row.get('DOMICILIO', '')[:200],
                'codigo_postal': str(row.get('CPOSTAL', ''))[:20],
                'localidad': row.get('LOCALIDAD', '')[:100],
                'condicion_iva': get_condicion_iva(row.get('CONDIVA', 4)),
            }
            if 'CLU' in row: entidades_dict[codigo]['clu'] = str(row['CLU'])[:50]
            if 'CLU_VTO' in row: entidades_dict[codigo]['clu_vto'] = row['CLU_VTO']

    # Luego completamos con Balance
    if os.path.exists(clipro_balance_dbf):
        table_balance = DBF(clipro_balance_dbf, ignore_missing_memofile=True, encoding='latin1')
        for row in table_balance:
            codigo = row['CODIGO']
            if codigo not in entidades_dict:
                entidades_dict[codigo] = {
                    'codigo_id': codigo,
                    'empresa': empresa,
                    'razon_social': row.get('DETALLE', '')[:200],
                    'cuit': str(row.get('CUIT', '')).strip(),
                    'tipo_entidad': 2 if str(row.get('CLI_PRO', '')).strip() == '2' else 1,
                    'domicilio': row.get('DOMICILIO', '')[:200],
                    'codigo_postal': str(row.get('CPOSTAL', ''))[:20],
                    'localidad': row.get('LOCALIDAD', '')[:100],
                    'condicion_iva': get_condicion_iva(row.get('INSC_IVA', 4)),
                }
            
            entidades_dict[codigo]['cta_pat'] = row.get('CTA_PAT', 0) if row.get('CTA_PAT') else 0
            entidades_dict[codigo]['cta_res'] = row.get('CTA_RES', 0) if row.get('CTA_RES') else 0

    # Creamos las instancias
    cp_to_create = []
    for cod, data in entidades_dict.items():
        kwargs = {
            'codigo_id': data['codigo_id'],
            'empresa': data['empresa'],
            'razon_social': data['razon_social'],
            'cuit': data['cuit'],
            'tipo_entidad': data['tipo_entidad'],
            'domicilio': data['domicilio'],
            'codigo_postal': data['codigo_postal'],
            'localidad': data['localidad'],
            'condicion_iva': data['condicion_iva'],
            'cta_pat': data.get('cta_pat', 0),
            'cta_res': data.get('cta_res', 0),
            'saldo_inicial': 0,
            'saldo': 0,
            'limite': 0,
            'objetivo_mensual': 0
        }
        cp_to_create.append(ClienteProveedor(**kwargs))

    ClienteProveedor.objects.bulk_create(cp_to_create, ignore_conflicts=True)
    print(f"OK {len(cp_to_create)} clientes/proveedores procesados tras fusión (Comercio + Balance).")

    # 6. Parámetros Contables (desde Balance)
    param_dbf = os.path.join(dir_balance, 'parametros_contables.dbf')
    if os.path.exists(param_dbf):
        table = DBF(param_dbf, ignore_missing_memofile=True, encoding='latin1')
        for row in table:
            def clean_fk(val):
                return val if val and val > 0 else None
                
            ParametrosContables.objects.update_or_create(
                empresa=empresa,
                defaults={
                    'cta_iva_credito_id': clean_fk(row.get('CTA_IVA_C')),
                    'cta_iva_debito_id': clean_fk(row.get('CTA_IVA_D')),
                    'cta_ret_iva_id': clean_fk(row.get('CTA_R_IVA')),
                    'cta_ret_ganancias_id': clean_fk(row.get('CTA_R_GCIA')),
                    'cta_ret_iibb_id': clean_fk(row.get('CTA_R_IB')),
                    'cta_ret_suss_id': clean_fk(row.get('CTA_R_SUSS')),
                    'cta_ret_mun_id': clean_fk(row.get('CTA_R_MUN')),
                    'cta_ret_practicada_ganancias_id': clean_fk(row.get('CTA_AR_GCI')),
                    'cta_ret_practicada_iva_id': clean_fk(row.get('CTA_AR_IVA')),
                    'cta_ret_practicada_iibb_id': clean_fk(row.get('CTA_AR_IB')),
                    'cta_caja_id': clean_fk(row.get('CTA_CAJA')),
                    'cta_dolar_id': clean_fk(row.get('CTA_DOLAR')),
                    'cta_valores_cartera_id': clean_fk(row.get('CTA_VAL_CA')),
                    'cta_tarjetas_a_cobrar_id': clean_fk(row.get('CTA_TAR')),
                    'cta_ventas_id': clean_fk(row.get('CTA_VTA')),
                    'cta_compras_id': clean_fk(row.get('CTA_CPRA')),
                    'cta_clientes_default_id': clean_fk(row.get('CTA_CLI')),
                    'cta_proveedores_default_id': clean_fk(row.get('CTA_PRO')),
                    'cta_impuestos_internos_id': clean_fk(row.get('CTA_IMPINT')),
                    'cta_itc_id': clean_fk(row.get('CTA_ITC')),
                    'cta_bonificaciones_id': clean_fk(row.get('CTA_BON')),
                    'cta_descuentos_obtenidos_id': clean_fk(row.get('CTA_DES')),
                }
            )
        print("OK Parámetros Contables procesados.")

    print("Fase 1 completada con éxito.")

if __name__ == '__main__':
    run()
