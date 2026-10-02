import os
import sys
import logging
from django.conf import settings as django_settings

logger = logging.getLogger(__name__)

# Reutilizar el parche de SSL que está en afip_service
from facturacion.services.afip_service import aplicar_parche_ssl_afip

# ============================================================================
# RESOLUCIÓN RUTA ARCA_ARG
# ============================================================================
RUTA_MODELOS_AFIP = os.path.join(django_settings.BASE_DIR, 'Modelos', 'Facturacion AFIP')
if RUTA_MODELOS_AFIP not in sys.path:
    sys.path.insert(0, RUTA_MODELOS_AFIP)

# pyrefly: ignore [missing-import]
import arca_arg.settings as arca_settings
# pyrefly: ignore [missing-import]
from arca_arg.webservice import ArcaWebService
# pyrefly: ignore [missing-import]
from arca_arg.settings import (
    WSDL_PADRON_A13_HOM, WSDL_PADRON_A13_PROD,
    WSDL_CONSTANCIA_HOM, WSDL_CONSTANCIA_PROD,
    WSDL_PADRON_A4_HOM, WSDL_PADRON_A4_PROD
)

MAPEO_AFIP_PROVINCIA = {
    0: 2,   # CABA / Capital Federal
    1: 1,   # Buenos Aires
    2: 3,   # Catamarca
    3: 6,   # Córdoba
    4: 7,   # Corrientes
    5: 8,   # Entre Ríos
    6: 10,  # Jujuy
    7: 13,  # Mendoza
    8: 12,  # La Rioja
    9: 17,  # Salta
    10: 18, # San Juan
    11: 19, # San Luis
    12: 21, # Santa Fe
    13: 22, # Santiago del Estero
    14: 24, # Tucumán
    16: 4,  # Chaco
    17: 5,  # Chubut
    18: 9,  # Formosa
    19: 14, # Misiones
    20: 15, # Neuquén
    21: 11, # La Pampa
    22: 16, # Río Negro
    23: 20, # Santa Cruz
    24: 23, # Tierra del Fuego
}


class AFIPPadronService:
    """
    Servicio de consulta híbrida de Padrón y Constancia de AFIP/ARCA.
    Combina:
    1. Constancia de Inscripción (A5 / A4): Validez del CUIT, Condición de IVA real y Actividades.
    2. Padrón A13: Identidad normalizada, separación física/jurídica y domicilio fiscal detallado.
    Tolerante a fallos: Si uno de los servicios no está autorizado o no responde, utiliza el otro
    sin interrumpir la consulta ni fallar en silencio.
    """
    def __init__(self, empresa):
        self.empresa = empresa
        aplicar_parche_ssl_afip()
        self._configurar_credenciales()

    def _configurar_credenciales(self):
        if not self.empresa.crt_afip or not self.empresa.key_afip:
            raise ValueError(
                f"La empresa '{self.empresa.nombre}' no tiene configurado el Certificado (.crt) o la Clave Privada (.key) de ARCA."
            )

        ruta_crt = self.empresa.crt_afip.path
        ruta_key = self.empresa.key_afip.path

        if not os.path.exists(ruta_crt):
            raise FileNotFoundError(f"Archivo de certificado ARCA no encontrado en: {ruta_crt}")
        if not os.path.exists(ruta_key):
            raise FileNotFoundError(f"Archivo de clave privada ARCA no encontrado en: {ruta_key}")

        cuit_limpio = str(self.empresa.cuit).replace('-', '').strip()
        if not cuit_limpio.isdigit() or len(cuit_limpio) != 11:
            raise ValueError(f"CUIT de empresa inválido: '{self.empresa.cuit}'. Debe contener 11 dígitos numéricos.")

        # Entorno dinámico: override opcional por .env o por configuración de Empresa
        entorno_env = os.getenv('AFIP_ENTORNO')
        if entorno_env:
            es_prod = (str(entorno_env).strip().upper() == 'PROD')
        else:
            entorno_empresa = getattr(self.empresa, 'entorno_afip', 'HOMO')
            es_prod = (str(entorno_empresa).upper() == 'PROD')

        entorno_tag = 'prod' if es_prod else 'homo'
        ta_dir = os.path.join(django_settings.MEDIA_ROOT, 'arca_ta', f"{cuit_limpio}_{entorno_tag}")
        os.makedirs(ta_dir, exist_ok=True)

        arca_settings.CUIT = cuit_limpio
        arca_settings.CERT_PATH = ruta_crt
        arca_settings.PRIVATE_KEY_PATH = ruta_key
        arca_settings.TA_FILES_PATH = os.path.join(ta_dir, '')
        arca_settings.PROD = es_prod

    def _get_val(self, obj, key, default=None):
        if isinstance(obj, dict):
            val = obj.get(key, default)
        else:
            val = getattr(obj, key, default)
        return val if val is not None else default

    def _formatear_fecha(self, val):
        if not val:
            return ''
        if hasattr(val, 'strftime'):
            return val.strftime('%Y-%m-%d')
        val_str = str(val).strip()
        if len(val_str) >= 10 and val_str[4] == '-' and val_str[7] == '-':
            return val_str[:10]
        return ''

    def _consultar_constancia(self, cuit_buscar: str) -> dict:
        """
        Consulta la Constancia de Inscripción en AFIP (ws_sr_constancia_inscripcion / A5)
        o fallback a ws_sr_padron_a4 para obtener la validez fiscal y condición de IVA real.
        """
        ws = None
        # 1. Intentar ws_sr_padron_a5 (Nombre de servicio oficial en WSAA)
        try:
            wsdl_a5 = WSDL_CONSTANCIA_PROD if arca_settings.PROD else WSDL_CONSTANCIA_HOM
            ws = ArcaWebService(wsdl_a5, 'ws_sr_padron_a5', enable_logging=False)
        except Exception as e:
            logger.info(f"ws_sr_padron_a5 no disponible, probando alias ws_sr_constancia_inscripcion: {e}")
            try:
                ws = ArcaWebService(wsdl_a5, 'ws_sr_constancia_inscripcion', enable_logging=False)
            except Exception as e2:
                logger.warning(f"No se pudo inicializar A5: {e2}")
                ws = None

        # 2. Si A5 falló, intentar ws_sr_padron_a4
        if not ws:
            try:
                wsdl_a4 = WSDL_PADRON_A4_PROD if arca_settings.PROD else WSDL_PADRON_A4_HOM
                ws = ArcaWebService(wsdl_a4, 'ws_sr_padron_a4', enable_logging=False)
            except Exception as e:
                logger.warning(f"No se pudo inicializar ws_sr_padron_a4: {e}")
                ws = None

        if not ws:
            raise Exception("No fue posible inicializar ws_sr_padron_a5 ni ws_sr_padron_a4")

        req = {
            'sign': ws.sign,
            'token': ws.token,
            'cuitRepresentada': int(ws.cuit),
            'idPersona': int(cuit_buscar)
        }

        try:
            response = ws.send_request('getPersona', req)
        except Exception as e:
            logger.warning(f"Error en llamada getPersona (A5/A4): {e}")
            raise Exception(str(e))

        if not response:
            raise Exception("AFIP no devolvió respuesta para la constancia de inscripción.")

        pr = response.personaReturn if hasattr(response, 'personaReturn') else response

        # Verificar errorConstancia devuelto por AFIP
        err_constancia = self._get_val(pr, 'errorConstancia')
        if err_constancia:
            if isinstance(err_constancia, list):
                msgs = [self._get_val(x, 'error', '') for x in err_constancia if self._get_val(x, 'error')]
                if msgs:
                    raise Exception(" | ".join(msgs))
            else:
                err = self._get_val(err_constancia, 'error')
                if err:
                    raise Exception(str(err))

        dg = self._get_val(pr, 'datosGenerales') or self._get_val(pr, 'persona')
        if not dg:
            raise Exception("AFIP no devolvió datos generales en la constancia de inscripción.")

        estado_clave = str(self._get_val(dg, 'estadoClave', '')).upper().strip()
        es_valido = (estado_clave == 'ACTIVO')

        # Fecha de Nacimiento (Personas físicas)
        fecha_nac = self._formatear_fecha(self._get_val(dg, 'fechaNacimiento'))

        # Razón Social / Nombre
        razon_social = self._get_val(dg, 'razonSocial')
        nombre = self._get_val(dg, 'nombre')
        apellido = self._get_val(dg, 'apellido')
        if not razon_social and (nombre or apellido):
            razon_social = f"{apellido or ''}, {nombre or ''}".strip(', ')

        tipo_persona_raw = str(self._get_val(dg, 'tipoPersona', '')).upper()
        tipo_persona = 'J' if 'JURIDICA' in tipo_persona_raw else 'F'

        # Determinar Condición de IVA Oficial a partir de Impuestos y Monotributo
        condicion_iva = 'CONSUMIDOR FINAL'

        # Verificar Monotributo
        datos_mono = self._get_val(pr, 'datosMonotributo')
        es_monotributo = False
        if datos_mono:
            cat_mono = self._get_val(datos_mono, 'categoriaMonotributo')
            act_mono = self._get_val(datos_mono, 'actividadMonotributo')
            if cat_mono or act_mono:
                es_monotributo = True
                condicion_iva = 'MONOTRIBUTO'

        # Verificar Régimen General (Impuestos)
        datos_rg = self._get_val(pr, 'datosRegimenGeneral')
        impuestos_list = []
        actividades_list = []

        if datos_rg:
            imps = self._get_val(datos_rg, 'impuesto')
            if imps:
                if not isinstance(imps, list):
                    imps = [imps]
                for imp in imps:
                    id_imp = self._get_val(imp, 'idImpuesto')
                    desc_imp = self._get_val(imp, 'descripcionImpuesto', '')
                    estado_imp = str(self._get_val(imp, 'estadoImpuesto', '')).upper()
                    impuestos_list.append({'id': id_imp, 'descripcion': desc_imp, 'estado': estado_imp})

            acts = self._get_val(datos_rg, 'actividad')
            if acts:
                if not isinstance(acts, list):
                    acts = [acts]
                for act in acts:
                    desc_act = self._get_val(act, 'descripcionActividad', '')
                    if desc_act:
                        actividades_list.append(str(desc_act).strip())

        if not es_monotributo and impuestos_list:
            for imp in impuestos_list:
                id_imp = str(imp.get('id', '')).strip()
                # 30 = IVA, 32 = IVA Exento, 20/21 = Monotributo
                if id_imp == '30':
                    condicion_iva = 'RESPONSABLE INSCRIPTO'
                    break
                elif id_imp == '32':
                    condicion_iva = 'EXENTO'
                    break
                elif id_imp in ('20', '21', '22', '23', '24'):
                    condicion_iva = 'MONOTRIBUTO'
                    break

        # Domicilio Fiscal
        dom = self._get_val(dg, 'domicilioFiscal')
        domicilio = ''
        cod_postal = ''
        localidad = ''
        provincia = ''
        id_provincia = None
        if dom:
            domicilio = self._get_val(dom, 'direccion', '')
            cod_postal = self._get_val(dom, 'codPostal', '')
            localidad = self._get_val(dom, 'localidad', '')
            provincia = self._get_val(dom, 'descripcionProvincia', '')
            id_provincia = self._get_val(dom, 'idProvincia')

        return {
            'cuit': cuit_buscar,
            'razon_social': razon_social or '',
            'tipo_persona': tipo_persona,
            'condicion_iva': condicion_iva,
            'estado_afip': estado_clave or ('ACTIVO' if es_valido else 'DESCONOCIDO'),
            'es_valido_afip': es_valido,
            'domicilio': domicilio or '',
            'codigo_postal': cod_postal or '',
            'localidad': localidad or '',
            'provincia': provincia or '',
            'id_provincia_afip': id_provincia,
            'actividades': actividades_list,
            'fecha_nacimiento': fecha_nac or ''
        }

    def _consultar_padron_a13(self, cuit_buscar: str) -> dict:
        """
        Consulta el CUIT en el padrón A13 (ws_sr_padron_a13 getPersonaV2)
        y devuelve un diccionario estructurado con los datos de identidad y domicilio.
        """
        wsdl = WSDL_PADRON_A13_PROD if arca_settings.PROD else WSDL_PADRON_A13_HOM
        ws = ArcaWebService(wsdl, 'ws_sr_padron_a13', enable_logging=False)

        req = {
            'sign': ws.sign,
            'token': ws.token,
            'cuitRepresentada': int(ws.cuit),
            'idPersona': int(cuit_buscar)
        }

        try:
            response = ws.send_request('getPersonaV2', req)
        except Exception as e:
            logger.warning(f"Error consultando AFIP getPersonaV2: {e}")
            raise Exception(str(e))

        result = {
            'cuit': cuit_buscar,
            'razon_social': '',
            'tipo_persona': 'J',
            'domicilio': '',
            'codigo_postal': '',
            'provincia': '',
            'localidad': '',
            'condicion_iva': 'CONSUMIDOR FINAL',
            'tipo_documento': '80',
            'apellido': '',
            'nombre': ''
        }

        if not response:
            raise Exception("No se encontró el CUIT en el padrón de AFIP (A13).")

        pr = response.personaReturn if hasattr(response, 'personaReturn') else response

        if not hasattr(pr, 'persona') or getattr(pr, 'persona', None) is None:
            if isinstance(pr, dict) and 'persona' in pr and pr['persona']:
                p = pr['persona']
            else:
                raise Exception("AFIP no devolvió detalles de persona para este CUIT.")
        else:
            p = pr.persona

        # Errores embebidos
        errorConstancia = self._get_val(pr, 'errorConstancia')
        if errorConstancia:
            if isinstance(errorConstancia, list):
                errores = [self._get_val(e, 'error', '') for e in errorConstancia if self._get_val(e, 'error')]
                if errores:
                    raise Exception(" | ".join(errores))
            else:
                err = self._get_val(errorConstancia, 'error')
                if err:
                    raise Exception(str(err))

        errorMonotributo = self._get_val(pr, 'errorMonotributo')
        if errorMonotributo:
            if isinstance(errorMonotributo, list):
                errores = [self._get_val(e, 'error', '') for e in errorMonotributo if self._get_val(e, 'error')]
                if errores:
                    raise Exception(" | ".join(errores))
            else:
                err = self._get_val(errorMonotributo, 'error')
                if err:
                    raise Exception(str(err))

        # Nombre / Razón Social
        nombre = self._get_val(p, 'nombre')
        apellido = self._get_val(p, 'apellido')
        razon_social = self._get_val(p, 'razonSocial')

        if razon_social:
            result['razon_social'] = razon_social
            result['tipo_persona'] = 'J'
            result['nombre'] = ''
            result['apellido'] = ''
        elif nombre or apellido:
            result['razon_social'] = f"{apellido or ''}, {nombre or ''}".strip(', ')
            result['tipo_persona'] = 'F'
            result['nombre'] = nombre or ''
            result['apellido'] = apellido or ''

        # Fecha de Nacimiento en A13
        result['fecha_nacimiento'] = self._formatear_fecha(self._get_val(p, 'fechaNacimiento'))

        # Inferencia por defecto para A13 (será superada si responde A5)
        tipo_persona_arca = str(self._get_val(p, 'tipoPersona', '')).upper()
        if tipo_persona_arca == 'JURIDICA' or result.get('tipo_persona') == 'J' or cuit_buscar.startswith(('30', '33', '34')):
            result['condicion_iva'] = 'RESPONSABLE INSCRIPTO'
        elif self._get_val(p, 'idActividadPrincipal'):
            result['condicion_iva'] = 'RESPONSABLE INSCRIPTO'
        else:
            result['condicion_iva'] = 'CONSUMIDOR FINAL'

        # Determinar si es CUIT (80) o CUIL (86)
        tipo_doc = '80'
        tipo_clave = self._get_val(p, 'tipoClave', '')
        if isinstance(tipo_clave, str):
            tipo_clave_str = tipo_clave.upper()
            if tipo_clave_str == 'CUIL':
                tipo_doc = '86'
            elif tipo_clave_str == 'CUIT':
                tipo_doc = '80'
        elif tipo_clave == 2:
            tipo_doc = '86'
        elif tipo_clave == 3:
            tipo_doc = '80'
        result['tipo_documento'] = tipo_doc

        # Domicilio Fiscal
        doms = self._get_val(p, 'domicilio')
        if doms:
            dom = doms[0] if len(doms) > 0 else None
            if dom:
                direccion = self._get_val(dom, 'direccion')
                if not direccion:
                    calle = self._get_val(dom, 'calle')
                    numero = self._get_val(dom, 'numero')
                    direccion = f"{calle or ''} {numero or ''}".strip()

                result['domicilio'] = direccion
                result['codigo_postal'] = self._get_val(dom, 'codigoPostal')
                desc_pcia = self._get_val(dom, 'descripcionProvincia')
                result['provincia'] = desc_pcia
                result['localidad'] = self._get_val(dom, 'localidad')

                # Mapeo de Jurisdicción
                id_provincia_afip = self._get_val(dom, 'idProvincia')
                from facturacion.models import Jurisdiccion
                jur = None
                if id_provincia_afip is not None:
                    try:
                        cod_interno = MAPEO_AFIP_PROVINCIA.get(int(id_provincia_afip))
                        if cod_interno:
                            jur = Jurisdiccion.objects.filter(codigo=cod_interno).first()
                    except (ValueError, TypeError):
                        pass
                if not jur and desc_pcia:
                    desc_clean = str(desc_pcia).strip().upper()
                    if any(k in desc_clean for k in ['BUENOS AIRES', 'BS AS', 'BSAS']) and 'CIUDAD' not in desc_clean and 'CABA' not in desc_clean:
                        jur = Jurisdiccion.objects.filter(codigo=1).first()
                    elif any(k in desc_clean for k in ['CIUDAD AUTONOMA', 'CAPITAL FEDERAL', 'CABA']):
                        jur = Jurisdiccion.objects.filter(codigo=2).first()
                    elif 'SANTIAGO' in desc_clean:
                        jur = Jurisdiccion.objects.filter(codigo=22).first()
                    elif 'TIERRA DEL FUEGO' in desc_clean:
                        jur = Jurisdiccion.objects.filter(codigo=23).first()
                    else:
                        jur = Jurisdiccion.objects.filter(nombre__icontains=desc_clean).first()
                if jur:
                    result['jurisdiccion_id'] = jur.id

        return result

    def consultar_cuit(self, cuit_buscar: str) -> dict:
        """
        Consulta de CUIT híbrida tolerante a fallos:
        1. Intenta consultar Constancia de Inscripción (A5 / A4) para validez tributaria e IVA.
        2. Intenta consultar Padrón A13 para datos de identidad y domicilio estructurado.
        3. Si alguno de los dos falla o no está autorizado en AFIP, continúa con el otro sin romper ni fallar en silencio.
        """
        cuit_buscar = str(cuit_buscar).replace('-', '').strip()
        if not cuit_buscar.isdigit() or len(cuit_buscar) != 11:
            raise ValueError("El CUIT a buscar debe tener 11 dígitos numéricos.")

        datos_constancia = None
        error_constancia = None
        datos_a13 = None
        error_a13 = None

        # 1. Consulta Constancia A5 / A4
        try:
            datos_constancia = self._consultar_constancia(cuit_buscar)
        except Exception as e:
            error_constancia = str(e)
            logger.warning(f"Consulta Constancia AFIP (A5/A4) para CUIT {cuit_buscar} no disponible: {e}")

        # 2. Consulta Padrón A13
        try:
            datos_a13 = self._consultar_padron_a13(cuit_buscar)
        except Exception as e:
            error_a13 = str(e)
            logger.warning(f"Consulta Padrón AFIP (A13) para CUIT {cuit_buscar} no disponible: {e}")

        # Si ninguno respondió, lanzar excepción clara
        if not datos_constancia and not datos_a13:
            raise Exception(f"AFIP no respondió a la consulta del CUIT {cuit_buscar}. "
                            f"(Constancia A5/A4: {error_constancia} | Padrón A13: {error_a13})")

        # 3. Combinación inteligente de datos
        if datos_a13:
            result = dict(datos_a13)
            if datos_constancia:
                # Potenciamos A13 con los datos fiscales certeros de A5
                result['condicion_iva'] = datos_constancia.get('condicion_iva', result.get('condicion_iva'))
                result['es_valido_afip'] = datos_constancia.get('es_valido_afip', True)
                result['estado_afip'] = datos_constancia.get('estado_afip', 'ACTIVO')
                result['actividades'] = datos_constancia.get('actividades', [])
                if not result.get('fecha_nacimiento') and datos_constancia.get('fecha_nacimiento'):
                    result['fecha_nacimiento'] = datos_constancia['fecha_nacimiento']
                result['fuente'] = 'A5+A13'
                result['aviso'] = None
            else:
                # Solo respondió A13 (no romper, avisar claramente sin fallar en silencio)
                result['es_valido_afip'] = True
                result['estado_afip'] = 'NO_VERIFICADO_A5'
                result['fuente'] = 'A13'
                result['aviso'] = 'Padrón A4/A5 no activo en AFIP (servicio no delegado o sin respuesta). Se autocompletaron los datos desde Padrón A13 (verifique la Condición de IVA).'
        else:
            # Solo respondió A5
            result = dict(datos_constancia)
            result['fuente'] = 'A5'
            result['aviso'] = 'Padrón A13 no disponible en AFIP. Se autocompletaron los datos desde Constancia de Inscripción (A5/A4).'

            # Mapear jurisdicción si vino de A5
            id_prov = datos_constancia.get('id_provincia_afip')
            desc_pcia = datos_constancia.get('provincia')
            from facturacion.models import Jurisdiccion
            jur = None
            if id_prov is not None:
                try:
                    cod_interno = MAPEO_AFIP_PROVINCIA.get(int(id_prov))
                    if cod_interno:
                        jur = Jurisdiccion.objects.filter(codigo=cod_interno).first()
                except (ValueError, TypeError):
                    pass
            if not jur and desc_pcia:
                desc_clean = str(desc_pcia).strip().upper()
                if any(k in desc_clean for k in ['BUENOS AIRES', 'BS AS', 'BSAS']) and 'CIUDAD' not in desc_clean and 'CABA' not in desc_clean:
                    jur = Jurisdiccion.objects.filter(codigo=1).first()
                elif any(k in desc_clean for k in ['CIUDAD AUTONOMA', 'CAPITAL FEDERAL', 'CABA']):
                    jur = Jurisdiccion.objects.filter(codigo=2).first()
                elif 'SANTIAGO' in desc_clean:
                    jur = Jurisdiccion.objects.filter(codigo=22).first()
                elif 'TIERRA DEL FUEGO' in desc_clean:
                    jur = Jurisdiccion.objects.filter(codigo=23).first()
                else:
                    jur = Jurisdiccion.objects.filter(nombre__icontains=desc_clean).first()
            if jur:
                result['jurisdiccion_id'] = jur.id

        return result
