import os
import sys
import ssl
import json
import base64
import logging
from datetime import datetime, date
from decimal import Decimal
import requests
from django.conf import settings as django_settings

logger = logging.getLogger(__name__)

# ============================================================================
# PARCHE SSL PARA AFIP (Diffie-Hellman SECLEVEL=1)
# ============================================================================
_ssl_parcheado = False
def aplicar_parche_ssl_afip():
    global _ssl_parcheado
    if _ssl_parcheado:
        return
    orig_init_poolmanager = requests.adapters.HTTPAdapter.init_poolmanager
    def patched_init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context()
        context.set_ciphers('DEFAULT@SECLEVEL=1')
        kwargs['ssl_context'] = context
        return orig_init_poolmanager(self, *args, **kwargs)
    requests.adapters.HTTPAdapter.init_poolmanager = patched_init_poolmanager
    _ssl_parcheado = True


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
from arca_arg.settings import WSDL_FEV1_HOM, WSDL_FEV1_PROD


class AFIPService:
    """
    Servicio de integración con ARCA/AFIP (WSFEv1) para emisión y autorización
    de comprobantes electrónicos en modalidad 1x1 en tiempo real.
    """
    def __init__(self, empresa):
        self.empresa = empresa
        aplicar_parche_ssl_afip()
        self._configurar_credenciales()
        wsdl = WSDL_FEV1_PROD if arca_settings.PROD else WSDL_FEV1_HOM
        self.wsfe = ArcaWebService(wsdl, 'wsfe', enable_logging=True)

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

    def obtener_ultimo_comprobante(self, pto_vta: int, cbte_tipo: int) -> int:
        """
        Consulta el último número de comprobante autorizado en AFIP para
        el punto de venta y tipo de comprobante dados.
        """
        req = {
            'Auth': {
                'Token': self.wsfe.token,
                'Sign': self.wsfe.sign,
                'Cuit': self.wsfe.cuit
            },
            'PtoVta': int(pto_vta),
            'CbteTipo': int(cbte_tipo)
        }
        res_ultimo = self.wsfe.send_request('FECompUltimoAutorizado', req)

        if hasattr(res_ultimo, 'FECompUltimoAutorizadoResult') and res_ultimo.FECompUltimoAutorizadoResult:
            res_ult = res_ultimo.FECompUltimoAutorizadoResult
        else:
            res_ult = res_ultimo

        if hasattr(res_ult, 'CbteNro'):
            return int(res_ult.CbteNro)
        return 0

    def emitir_comprobante(self, datos_factura: dict, alicuotas_list: list, tributos_list: list = None, max_reintentos: int = 3) -> dict:
        """
        Autoriza un comprobante ante ARCA/AFIP en tiempo real (1x1).
        Maneja reintentos en caso de colisión en el número de comprobante.
        
        datos_factura keys requeridas:
          - pto_vta (int)
          - cbte_tipo (int)
          - concepto (int: 1=Productos, 2=Servicios, 3=Productos y Servicios)
          - doc_tipo (int: 80=CUIT, 96=DNI, 99=Consumidor Final, etc.)
          - doc_nro (int)
          - cbte_fch (str YYYYMMDD)
          - imp_total (float/Decimal)
          - imp_tot_conc (float/Decimal)
          - imp_neto (float/Decimal)
          - imp_op_ex (float/Decimal)
          - imp_iva (float/Decimal)
          - imp_trib (float/Decimal opcional)
        """
        pto_vta = int(datos_factura['pto_vta'])
        cbte_tipo = int(datos_factura['cbte_tipo'])
        concepto = int(datos_factura.get('concepto', 1))

        for intento in range(1, max_reintentos + 1):
            try:
                ultimo_nro = self.obtener_ultimo_comprobante(pto_vta, cbte_tipo)
                nuevo_nro = ultimo_nro + 1

                cabecera = {
                    'CantReg': 1,
                    'PtoVta': pto_vta,
                    'CbteTipo': cbte_tipo
                }

                imp_neto = float(datos_factura.get('imp_neto', 0))
                imp_op_ex = float(datos_factura.get('imp_op_ex', 0))
                imp_iva = float(datos_factura.get('imp_iva', 0))
                imp_tot_conc = float(datos_factura.get('imp_tot_conc', 0))
                
                total_tributos = 0.0
                tributos_payload = []
                if tributos_list:
                    for t in tributos_list:
                        importe_t = float(t['importe'])
                        tributos_payload.append({
                            'Id': int(t['id']),
                            'Desc': str(t['desc']).strip(),
                            'BaseImp': float(t['base_imp']),
                            'Alic': float(t['alic']),
                            'Importe': importe_t
                        })
                        total_tributos += importe_t

                imp_total_calculado = round(imp_neto + imp_op_ex + imp_iva + total_tributos + imp_tot_conc, 2)

                detalle = {
                    'Concepto': concepto,
                    'DocTipo': int(datos_factura['doc_tipo']),
                    'DocNro': int(datos_factura['doc_nro']),
                    'CbteDesde': nuevo_nro,
                    'CbteHasta': nuevo_nro,
                    'CbteFch': str(datos_factura['cbte_fch']),
                    'ImpTotal': imp_total_calculado,
                    'ImpTotConc': imp_tot_conc,
                    'ImpNeto': imp_neto,
                    'ImpOpEx': imp_op_ex,
                    'ImpTrib': round(total_tributos, 2),
                    'ImpIVA': imp_iva,
                    'MonId': str(datos_factura.get('mon_id', 'PES')),
                    'MonCotiz': float(datos_factura.get('mon_cotiz', 1))
                }

                # RG 5616 - Condición IVA Receptor
                if 'condicion_iva_receptor_id' in datos_factura and datos_factura['condicion_iva_receptor_id']:
                    detalle['CondicionIVAReceptorId'] = int(datos_factura['condicion_iva_receptor_id'])

                if concepto in (2, 3):
                    detalle['FchServDesde'] = datos_factura.get('fch_serv_desde', datos_factura['cbte_fch'])
                    detalle['FchServHasta'] = datos_factura.get('fch_serv_hasta', datos_factura['cbte_fch'])
                    detalle['FchVtoPago'] = datos_factura.get('fch_vto_pago', datos_factura['cbte_fch'])

                # Comprobantes asociados (Notas de Crédito / Débito)
                if cbte_tipo in (2, 3, 7, 8, 12, 13):
                    if 'cbte_asoc_tipo' in datos_factura and datos_factura['cbte_asoc_tipo']:
                        detalle['CbtesAsoc'] = {
                            'CbteAsoc': [{
                                'Tipo': int(datos_factura['cbte_asoc_tipo']),
                                'PtoVta': int(datos_factura['cbte_asoc_pto_vta']),
                                'Nro': int(datos_factura['cbte_asoc_nro']),
                                'Cuit': str(self.wsfe.cuit)
                            }]
                        }
                    else:
                        return {
                            'exito': False,
                            'cae': '',
                            'vto_cae': None,
                            'numero_comprobante': None,
                            'cod_qr': '',
                            'error': "Faltan datos del comprobante asociado requeridos para emitir Notas de Crédito/Débito."
                        }

                # Desglose Multi-Alícuota IVA
                alic_iva_payload = []
                for a in alicuotas_list:
                    base_imp = float(a['base_imponible'])
                    imp_iva_a = float(a['importe_iva'])
                    if base_imp > 0:
                        alic_iva_payload.append({
                            'Id': int(a['id_iva']),
                            'BaseImp': round(base_imp, 2),
                            'Importe': round(imp_iva_a, 2)
                        })
                if alic_iva_payload:
                    detalle['Iva'] = {'AlicIva': alic_iva_payload}

                if tributos_payload:
                    detalle['Tributos'] = {'Tributo': tributos_payload}

                req_payload = {
                    'Auth': {
                        'Token': self.wsfe.token,
                        'Sign': self.wsfe.sign,
                        'Cuit': self.wsfe.cuit
                    },
                    'FeCAEReq': {
                        'FeCabReq': cabecera,
                        'FeDetReq': {'FECAEDetRequest': [detalle]}
                    }
                }

                resultado = self.wsfe.send_request('FECAESolicitar', req_payload)

                if hasattr(resultado, 'FECAESolicitarResult'):
                    res = resultado.FECAESolicitarResult
                elif hasattr(resultado, 'FeDetResp') or hasattr(resultado, 'Errors'):
                    res = resultado
                else:
                    return {
                        'exito': False,
                        'cae': '',
                        'vto_cae': None,
                        'numero_comprobante': None,
                        'cod_qr': '',
                        'error': f"Respuesta inesperada de AFIP: {resultado}"
                    }

                if hasattr(res, 'Errors') and res.Errors:
                    errs = res.Errors.Err
                    if not isinstance(errs, list):
                        errs = [errs]
                    error_msg = "; ".join([f"Err {err.Code}: {err.Msg}" for err in errs])
                    
                    # Si es error de numeración desincronizada, reintentamos
                    if any(str(err.Code) == '10016' for err in errs) and intento < max_reintentos:
                        logger.warning(f"Intento {intento}: colisión en número {nuevo_nro}. Sincronizando y reintentando...")
                        continue

                    return {
                        'exito': False,
                        'cae': '',
                        'vto_cae': None,
                        'numero_comprobante': None,
                        'cod_qr': '',
                        'error': error_msg
                    }

                if hasattr(res, 'FeDetResp') and res.FeDetResp:
                    det_responses = res.FeDetResp.FECAEDetResponse
                    det_resp = det_responses[0] if isinstance(det_responses, list) else det_responses

                    if det_resp.Resultado == 'A':
                        fch_str = str(datos_factura['cbte_fch'])
                        fch_formateada = f"{fch_str[:4]}-{fch_str[4:6]}-{fch_str[6:]}"
                        
                        datos_qr = {
                            "ver": 1,
                            "fecha": fch_formateada,
                            "cuit": int(self.wsfe.cuit),
                            "ptoVta": int(pto_vta),
                            "tipoCmp": int(cbte_tipo),
                            "nroCmp": int(det_resp.CbteDesde),
                            "importe": float(imp_total_calculado),
                            "moneda": "PES",
                            "ctz": 1.0,
                            "tipoDocRec": int(datos_factura['doc_tipo']),
                            "nroDocRec": int(datos_factura['doc_nro']),
                            "tipoCodAut": "E",
                            "codAut": int(det_resp.CAE)
                        }
                        json_str = json.dumps(datos_qr)
                        b64_str = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
                        cod_qr_url = f"https://www.afip.gob.ar/fe/qr/?p={b64_str}"

                        vto_cae_str = str(det_resp.CAEFchVto)
                        try:
                            vto_cae_date = datetime.strptime(vto_cae_str, '%Y%m%d').date()
                        except (ValueError, TypeError):
                            vto_cae_date = None

                        return {
                            'exito': True,
                            'cae': str(det_resp.CAE),
                            'vto_cae': vto_cae_date,
                            'numero_comprobante': int(det_resp.CbteDesde),
                            'cod_qr': cod_qr_url,
                            'error': ''
                        }
                    else:
                        obs_msg = ""
                        if hasattr(det_resp, 'Observaciones') and det_resp.Observaciones:
                            obs_list = det_resp.Observaciones.Obs
                            if not isinstance(obs_list, list):
                                obs_list = [obs_list]
                            obs_msg = "; ".join([f"Obs {o.Code}: {o.Msg}" for o in obs_list])
                        return {
                            'exito': False,
                            'cae': '',
                            'vto_cae': None,
                            'numero_comprobante': None,
                            'cod_qr': '',
                            'error': f"Comprobante rechazado por AFIP. {obs_msg}"
                        }

            except Exception as e:
                logger.exception(f"Error al emitir comprobante ante AFIP (Intento {intento}/{max_reintentos}): {e}")
                if intento == max_reintentos:
                    return {
                        'exito': False,
                        'cae': '',
                        'vto_cae': None,
                        'numero_comprobante': None,
                        'cod_qr': '',
                        'error': f"Error de comunicación con el servicio AFIP: {str(e)}"
                    }
                continue

        return {
            'exito': False,
            'cae': '',
            'vto_cae': None,
            'numero_comprobante': None,
            'cod_qr': '',
            'error': "No se pudo autorizar el comprobante tras múltiples reintentos."
        }
