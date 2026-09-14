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
from facturacion.models import ClienteProveedor, Jurisdiccion
from contable.models import Cuenta, ParametrosContables, AlicuotaIva
from verticalidades.armeria.models import ExtensionArmeria

def parse_decimal(value):
    if value is None: return Decimal('0.00')
    try: return Decimal(str(value))
    except: return Decimal('0.00')

def get_tipo_cuenta(jerarquia):
    if not jerarquia: return 'R'
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

def normalizar_identificacion(cuit_raw):
    """
    Normalización estricta de CUIT / DNI según reglas de negocio:
    - 11 dígitos que inician con 3 -> CUIT (80), Persona Jurídica (J)
    - 11 dígitos que inician con 2 -> CUIT (80), Persona Física (F)
    - 7 u 8 dígitos -> DNI (96), Persona Física (F)
    - 9 o 10 dígitos -> Error de carga -> Tipo 99, CUIT '0', Persona Física (F)
    - Menos de 7 dígitos -> Tipo 99, CUIT '0', Persona Física (F)
    """
    digits = ''.join(c for c in str(cuit_raw or '') if c.isdigit())
    n = len(digits)
    
    if n == 11:
        if digits.startswith('3'):
            return '80', digits, 'J'
        else:
            return '80', digits, 'F'
    elif 7 <= n <= 8:
        return '96', digits, 'F'
    elif 9 <= n <= 10:
        return '99', '0', 'F'
    else:
        return '99', '0', 'F'

def run():
    print("=== FASE 2: MAESTROS CONTABLES, CLIENTES/PROVEEDORES Y EXTENSIÓN ARMERÍA ===")
    
    dir_balance = r'D:\jm_soft\net_balances\eje_255'
    dir_comercio = r'D:\jm_soft\net_comercio\eje_255'
    
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
                jerarquia=str(row.get('JERA_CTA', '')).strip(),
                cuenta=str(row.get('DETALLE', '')).strip()[:200],
                imputable=bool(row.get('IMPUTABLE', False)),
                tipo=get_tipo_cuenta(row.get('JERA_CTA', '')),
                sumariza_id=sumariza_id
            ))
        Cuenta.objects.bulk_create(cuentas_to_create, ignore_conflicts=True)
        print(f"OK: {len(cuentas_to_create)} Cuentas Contables procesadas.")

    # 2. Jurisdicciones / Provincias (desde Balance)
    provincias_dbf = os.path.join(dir_balance, 'provincias.dbf')
    if os.path.exists(provincias_dbf):
        table = DBF(provincias_dbf, ignore_missing_memofile=True, encoding='latin1')
        juris_to_create = []
        for row in table:
            juris_to_create.append(Jurisdiccion(
                id=row['CODIGO'],
                codigo=row['CODIGO'],
                nombre=str(row.get('DETALLE', '')).strip()[:100]
            ))
        Jurisdiccion.objects.bulk_create(juris_to_create, ignore_conflicts=True)
        print(f"OK: {len(juris_to_create)} Jurisdicciones/Provincias procesadas.")

    # 3. Alícuotas IVA (desde Balance)
    alicuotas_dbf = os.path.join(dir_balance, 'alicuotas_iva.dbf')
    if os.path.exists(alicuotas_dbf):
        table = DBF(alicuotas_dbf, ignore_missing_memofile=True, encoding='latin1')
        alics_to_create = []
        for row in table:
            alics_to_create.append(AlicuotaIva(
                codigo=str(row['COD_ALIC']).strip(),
                descripcion=f"Alícuota {row.get('ALICUOTA')}%",
                porcentaje=parse_decimal(row.get('ALICUOTA'))
            ))
        AlicuotaIva.objects.bulk_create(alics_to_create, ignore_conflicts=True)
        print(f"OK: {len(alics_to_create)} Alícuotas IVA procesadas.")

    # 4. Parámetros Contables (desde Balance)
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
        print("OK: Parámetros Contables configurados.")

    # 5. Clientes y Proveedores (Fuente de Verdad: CONTABLE eje_255)
    clipro_balance_dbf = os.path.join(dir_balance, 'cli_pro.dbf')
    entidades_to_create = []
    map_personas = {} # map codigo -> tipo_persona (J/F)
    
    if os.path.exists(clipro_balance_dbf):
        table_balance = DBF(clipro_balance_dbf, ignore_missing_memofile=True, encoding='latin1')
        for row in table_balance:
            codigo = row['CODIGO']
            t_doc, cuit_clean, tipo_persona = normalizar_identificacion(row.get('CUIT'))
            map_personas[codigo] = tipo_persona
            
            tipo_entidad = 2 if str(row.get('CLI_PRO', '')).strip() == '2' else 1
            cond_iva = get_condicion_iva(row.get('INSC_IVA', 4))
            
            entidades_to_create.append(ClienteProveedor(
                codigo_id=codigo,
                empresa=empresa,
                razon_social=str(row.get('DETALLE', '')).strip()[:200] or f"ENTIDAD {codigo}",
                tipo_documento=t_doc,
                cuit=cuit_clean,
                tipo_entidad=tipo_entidad,
                domicilio=str(row.get('DOMICILIO', '')).strip()[:255],
                codigo_postal=str(row.get('CPOSTAL', '')).strip()[:20],
                localidad=str(row.get('LOCALIDAD', '')).strip()[:100],
                jurisdiccion_id=row.get('ID_PCIA') if row.get('ID_PCIA') and row.get('ID_PCIA') > 0 else None,
                contacto=str(row.get('CONTACTO', '')).strip()[:150],
                telefono=str(row.get('TELEFONO', '')).strip()[:100],
                correo=str(row.get('CORREO', '')).strip()[:254],
                condicion_iva=cond_iva,
                cta_pat=row.get('CTA_PAT', 0) or 0,
                cta_res=row.get('CTA_RES', 0) or 0,
                saldo_inicial=0,
                saldo=0,
                limite=parse_decimal(row.get('LIMITE')),
                codigo_anterior=str(codigo)
            ))
            
        ClienteProveedor.objects.bulk_create(entidades_to_create, ignore_conflicts=True, batch_size=1000)
        print(f"OK: {len(entidades_to_create)} Clientes y Proveedores migrados desde CONTABLE.")

    # 6. Extensión Armería y Observaciones / Notas (desde COMERCIO eje_255)
    clipro_comercio_dbf = os.path.join(dir_comercio, 'cli_pro.dbf')
    if os.path.exists(clipro_comercio_dbf):
        table_com = DBF(clipro_comercio_dbf, ignore_missing_memofile=True, encoding='latin1')
        valid_clientes = set(ClienteProveedor.objects.filter(empresa=empresa).values_list('codigo_id', flat=True))
        ext_to_create = []
        observaciones_dict = {}
        
        for row in table_com:
            codigo = row.get('CODIGO')
            if not codigo or codigo not in valid_clientes:
                continue
                
            clu = str(row.get('CLU', '')).strip()[:20]
            clu_vto = row.get('CLU_VTO')
            es_policia = bool(row.get('POLICIA', False))
            tipo_persona = map_personas.get(codigo, 'F')
            observa = str(row.get('OBSERVA', '')).strip()
            if observa:
                observaciones_dict[codigo] = observa
            
            ext_to_create.append(ExtensionArmeria(
                cliente_id=codigo,
                tipo_persona=tipo_persona,
                clu=clu,
                clu_vto=clu_vto,
                es_policia=es_policia
            ))
            
        ExtensionArmeria.objects.bulk_create(ext_to_create, ignore_conflicts=True, batch_size=1000)
        print(f"OK: {len(ext_to_create)} Registros de Extensión Armería (CLU, Vencimiento, Policía) creados.")

        if observaciones_dict:
            for cod, obs in observaciones_dict.items():
                ClienteProveedor.objects.filter(codigo_id=cod, empresa=empresa).update(observaciones=obs)
            print(f"OK: {len(observaciones_dict)} Notas/Observaciones particulares actualizadas en Clientes.")

    print("Fase 2 completada con éxito.")

if __name__ == '__main__':
    run()
