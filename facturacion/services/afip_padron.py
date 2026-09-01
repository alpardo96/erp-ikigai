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
from arca_arg.settings import WSDL_PADRON_A13_HOM, WSDL_PADRON_A13_PROD

class AFIPPadronService:
    """
    Servicio para consultar el Padrón A13 de AFIP (ws_sr_padron_a13).
    Obtiene los datos de una persona/empresa a partir de su CUIT.
    Nota: A13 no devuelve la condición del IVA ni impuestos, sólo datos base.
    """
    def __init__(self, empresa):
        self.empresa = empresa
        aplicar_parche_ssl_afip()
        self._configurar_credenciales()
        wsdl = WSDL_PADRON_A13_PROD if arca_settings.PROD else WSDL_PADRON_A13_HOM
        self.ws = ArcaWebService(wsdl, 'ws_sr_padron_a13', enable_logging=True)

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

        ta_dir = os.path.join(django_settings.MEDIA_ROOT, 'arca_ta')
        os.makedirs(ta_dir, exist_ok=True)

        arca_settings.CUIT = cuit_limpio
        arca_settings.CERT_PATH = ruta_crt
        arca_settings.PRIVATE_KEY_PATH = ruta_key
        arca_settings.TA_FILES_PATH = os.path.join(ta_dir, '')
        arca_settings.PROD = (getattr(self.empresa, 'entorno_afip', 'HOM') == 'PROD')

    def consultar_cuit(self, cuit_buscar: str) -> dict:
        """
        Consulta el CUIT en el padrón A13 y devuelve un diccionario con los datos.
        """
        cuit_buscar = str(cuit_buscar).replace('-', '').strip()
        if not cuit_buscar.isdigit() or len(cuit_buscar) != 11:
            raise ValueError("El CUIT a buscar debe tener 11 dígitos numéricos.")

        req = {
            'sign': self.ws.sign,
            'token': self.ws.token,
            'cuitRepresentada': int(self.ws.cuit),
            'idPersona': int(cuit_buscar)
        }

        # Según la documentación de AFIP, el método getPersonaV2 (A13 v1.4) trae datos incluso si el CUIT está inactivo
        try:
            response = self.ws.send_request('getPersonaV2', req)
        except Exception as e:
            logger.exception(f"Error consultando AFIP getPersonaV2: {e}")
            raise Exception(str(e))

        # Inicializamos resultado
        result = {
            'cuit': cuit_buscar,
            'razon_social': '',
            'tipo_persona': 'J',
            'domicilio': '',
            'codigo_postal': '',
            'provincia': '',
            'localidad': '',
            'condicion_iva': 'CONSUMIDOR FINAL', # fallback for A13 as it doesn't return IVA
            'tipo_documento': '80' # Por defecto A13 maneja CUIT/CUIL, usamos 80 (CUIT)
        }
        
        if not response:
            raise Exception("No se encontró el CUIT en el padrón de AFIP (A13).")
            
        # Zeep puede desempacar la respuesta, así que `response` podría ser directamente `personaReturn`
        pr = response.personaReturn if hasattr(response, 'personaReturn') else response
        
        if not hasattr(pr, 'persona') or getattr(pr, 'persona', None) is None:
            # En caso de que sea un dict/OrderedDict tras usar serialize_object o versiones nuevas de Zeep
            if isinstance(pr, dict) and 'persona' in pr and pr['persona']:
                p = pr['persona']
            else:
                raise Exception("AFIP no devolvió detalles de persona para este CUIT.")
        else:
            p = pr.persona
            
        # Si p es un dict/OrderedDict, usamos .get(), si es un objeto Zeep usamos getattr
        def get_val(obj, key, default=''):
            if isinstance(obj, dict):
                val = obj.get(key, default)
            else:
                val = getattr(obj, key, default)
            return val if val is not None else default
            
        # Extraer posibles errores embebidos devueltos por AFIP (errorConstancia)
        errorConstancia = get_val(pr, 'errorConstancia', None)
        if errorConstancia:
            # errorConstancia puede ser una lista
            if isinstance(errorConstancia, list):
                errores = [get_val(e, 'error', '') for e in errorConstancia if get_val(e, 'error')]
                if errores:
                    raise Exception(" | ".join(errores))
            else:
                err = get_val(errorConstancia, 'error', '')
                if err:
                    raise Exception(err)
                    
        # Extraer otros posibles nodos de error
        errorMonotributo = get_val(pr, 'errorMonotributo', None)
        if errorMonotributo:
            if isinstance(errorMonotributo, list):
                errores = [get_val(e, 'error', '') for e in errorMonotributo if get_val(e, 'error')]
                if errores:
                    raise Exception(" | ".join(errores))
            else:
                err = get_val(errorMonotributo, 'error', '')
                if err:
                    raise Exception(err)
            
        # Nombre / Razón Social
        nombre = get_val(p, 'nombre')
        apellido = get_val(p, 'apellido')
        razon_social = get_val(p, 'razonSocial')
        
        if razon_social:
            result['razon_social'] = razon_social
            result['tipo_persona'] = 'J'
            result['nombre'] = ''
            result['apellido'] = ''
        elif nombre or apellido:
            result['razon_social'] = f"{apellido}, {nombre}".strip(', ')
            result['tipo_persona'] = 'F'
            result['nombre'] = nombre or ''
            result['apellido'] = apellido or ''
            
        # Mapeo interno de idProvincia AFIP a Códigos IIBB (Convenio Multilateral)
        MAPEO_AFIP_IIBB = {
            0: 901,  # CABA
            1: 902,  # Buenos Aires
            2: 903,  # Catamarca
            3: 904,  # Córdoba
            4: 905,  # Corrientes
            5: 908,  # Entre Ríos
            6: 910,  # Jujuy
            7: 913,  # Mendoza
            8: 912,  # La Rioja
            9: 917,  # Salta
            10: 918, # San Juan
            11: 919, # San Luis
            12: 921, # Santa Fe
            13: 922, # Santiago del Estero
            14: 924, # Tucumán
            16: 906, # Chaco
            17: 907, # Chubut
            18: 909, # Formosa
            19: 914, # Misiones
            20: 915, # Neuquén
            21: 911, # La Pampa
            22: 916, # Río Negro
            23: 920, # Santa Cruz
            24: 923, # Tierra del Fuego
        }
        
        # Determinar si es CUIT (80) o CUIL (86) a partir de los datos explícitos de ARCA
        tipo_doc = '80' # Por defecto CUIT
        tipo_clave = get_val(p, 'tipoClave', '')
        
        if isinstance(tipo_clave, str):
            tipo_clave_str = tipo_clave.upper()
            if tipo_clave_str == 'CUIL':
                tipo_doc = '86'
            elif tipo_clave_str == 'CUIT':
                tipo_doc = '80'
        elif tipo_clave == 2:
            tipo_doc = '86' # CUIL
        elif tipo_clave == 3:
            tipo_doc = '80' # CUIT
        result['tipo_documento'] = tipo_doc


        # Domicilio Fiscal
        doms = get_val(p, 'domicilio')
        if doms:
            # En A13 el domicilio es una lista (puede venir domicilio fiscal, legal, etc.)
            dom = doms[0] if len(doms) > 0 else None
            
            if dom:
                direccion = get_val(dom, 'direccion')
                if not direccion:
                    calle = get_val(dom, 'calle')
                    numero = get_val(dom, 'numero')
                    direccion = f"{calle} {numero}".strip()
                    
                result['domicilio'] = direccion
                result['codigo_postal'] = get_val(dom, 'codigoPostal')
                result['provincia'] = get_val(dom, 'descripcionProvincia')
                result['localidad'] = get_val(dom, 'localidad')
                
                # Mapeo de Jurisdicción
                id_provincia_afip = get_val(dom, 'idProvincia')
                if id_provincia_afip is not None:
                    try:
                        cod_iibb = MAPEO_AFIP_IIBB.get(int(id_provincia_afip))
                        if cod_iibb:
                            from facturacion.models import Jurisdiccion
                            jur = Jurisdiccion.objects.filter(codigo=cod_iibb).first()
                            if jur:
                                result['jurisdiccion_id'] = jur.id
                    except (ValueError, TypeError):
                        pass
                
        return result
