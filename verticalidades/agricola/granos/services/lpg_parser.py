"""
Servicio de extracción y análisis de Liquidaciones Primarias de Granos (LPG)
y Ajustes Débito/Crédito en formato PDF emitidos bajo normativa de ARCA/AFIP.

Utiliza PyMuPDF (fitz) para extraer texto y bloques de coordenadas de forma robusta,
sin dependencias externas pesadas y con alta tolerancia a variaciones visuales.
"""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
import fitz  # PyMuPDF


# Nomenclador de cultivos oficiales ARCA más habituales
GRANOS_ARCA_MAP = {
    15: 'TRIGO PAN',
    16: 'TRIGO CANDEAL',
    19: 'MAIZ',
    21: 'GIRASOL',
    22: 'SORGO',
    23: 'SOJA',
    31: 'POROTO',
    32: 'CEBADA CERVECERA',
    33: 'CEBADA FORRAJERA',
    34: 'ARROZ',
    35: 'AVENA',
    36: 'CENTENO',
    37: 'COLZA',
    38: 'LINO',
    39: 'MANI',
    40: 'MIJO',
    41: 'CARTAMO',
    42: 'ALGODON',
}


def parse_decimal(val_str, default=Decimal('0.00')):
    """
    Convierte cadenas con formato numérico argentino (ej. '$ 51.122.620,80' o '$51122620.80')
    a Decimal estándar de Python.
    """
    if val_str is None or val_str == '':
        return default
    if isinstance(val_str, (int, float, Decimal)):
        return Decimal(str(val_str))
    
    # Limpiar signos monetarios, espacios y caracteres extraños
    s = str(val_str).replace('$', '').replace('Kg', '').replace('kg', '').replace('%', '').strip()
    if not s:
        return default
    
    # Si tiene coma y punto:
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            # Formato 1.234.567,89
            s = s.replace('.', '').replace(',', '.')
        else:
            # Formato 1,234,567.89
            s = s.replace(',', '')
    elif ',' in s:
        # Solo coma: 1234,56
        s = s.replace(',', '.')
    elif s.count('.') > 1:
        # Múltiples puntos como separador de miles: 51.122.620
        partes = s.split('.')
        s = "".join(partes[:-1]) + "." + partes[-1] if len(partes[-1]) == 2 else "".join(partes)

    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return default


def parse_fecha(fecha_str):
    """Convierte cadenas de fecha (ej. '28/07/2026') a objeto date."""
    if not fecha_str:
        return None
    m = re.search(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})', str(fecha_str))
    if m:
        dia, mes, anio = m.groups()
        try:
            return datetime(int(anio), int(mes), int(dia)).date()
        except ValueError:
            return None
    return None


class LpgPdfParser:
    """
    Parser especializado para Liquidaciones Primarias de Granos y Ajustes de ARCA.
    """

    @classmethod
    def parse_pdf(cls, file_or_path):
        """
        Lee el PDF (desde ruta de archivo, objeto File de Django o bytes)
        y devuelve un diccionario estructurado con todos los campos de la liquidación.
        """
        if isinstance(file_or_path, (str, bytes)):
            if isinstance(file_or_path, bytes):
                doc = fitz.open(stream=file_or_path, filetype="pdf")
            else:
                doc = fitz.open(file_or_path)
        elif hasattr(file_or_path, 'read'):
            content = file_or_path.read()
            doc = fitz.open(stream=content, filetype="pdf")
        else:
            raise ValueError("Tipo de archivo no soportado para parse_pdf")

        full_text = ""
        all_blocks = []
        for pno in range(len(doc)):
            page = doc[pno]
            full_text += page.get_text("text") + "\n"
            blocks = page.get_text("blocks")
            for b in blocks:
                # b = (x0, y0, x1, y1, text, block_no, block_type)
                all_blocks.append((pno, b[0], b[1], b[2], b[3], b[4]))
        doc.close()

        data = {
            'es_lpg': False,
            'es_ajuste': False,
            'tipo_ajuste': None,  # 'DEBITO', 'CREDITO' o None
            'tipo_operacion': '',
            'coe': '',
            'coe_original': '',
            'fecha': None,
            'periodo': '',
            'comprador': {},
            'vendedor': {},
            'grano': {},
            'deducciones': [],
            'retenciones': [],
            'totales': {},
            'datos_adicionales': {},
            'raw_text': full_text
        }

        # 1. Identificación básica y Tipo de Comprobante
        if "LIQUIDACIÓN PRIMARIA DE GRANOS" in full_text.upper() or "LIQUIDACION PRIMARIA" in full_text.upper():
            data['es_lpg'] = True

        if "AJUSTE" in full_text.upper():
            data['es_ajuste'] = True
            if "AJUSTE DÉBITO" in full_text.upper() or "AJUSTE DEBITO" in full_text.upper() or "AJUSTE DBITO" in full_text.upper():
                data['tipo_ajuste'] = 'DEBITO'
            elif "AJUSTE CRÉDITO" in full_text.upper() or "AJUSTE CREDITO" in full_text.upper() or "AJUSTE CRDITO" in full_text.upper():
                data['tipo_ajuste'] = 'CREDITO'
            else:
                data['tipo_ajuste'] = 'DEBITO'

        # Tipo de Operación
        m_tipo_op = re.search(r'Tipo de operaci[óo\?]n:\s*([^\n]+)', full_text, re.IGNORECASE)
        if m_tipo_op:
            data['tipo_operacion'] = m_tipo_op.group(1).strip()

        # COE (Código de Operación Electrónica)
        m_coe = re.search(r'C\.?O\.?E\.?:\s*(\d{12})', full_text, re.IGNORECASE)
        if m_coe:
            data['coe'] = m_coe.group(1).strip()
        else:
            m_coe_alt = re.search(r'\b(330\d{9})\b', full_text)
            if m_coe_alt:
                data['coe'] = m_coe_alt.group(1).strip()

        # COE Original (en caso de ajustes)
        m_coe_orig = re.search(r'COE ORIGINAL:\s*(\d{12})', full_text, re.IGNORECASE)
        if m_coe_orig:
            data['coe_original'] = m_coe_orig.group(1).strip()

        # Fecha de emisión
        m_fecha = re.search(r'(\d{1,2}/\d{1,2}/\d{4}),\s*[A-ZÁÉÍÓÚÑ\s]+', full_text)
        if m_fecha:
            data['fecha'] = parse_fecha(m_fecha.group(1))
        else:
            m_fecha_alt = re.search(r'Fecha:\s*(\d{1,2}/\d{1,2}/\d{4})', full_text, re.IGNORECASE)
            if m_fecha_alt:
                data['fecha'] = parse_fecha(m_fecha_alt.group(1))

        if data['fecha']:
            data['periodo'] = data['fecha'].strftime('%Y%m')

        # 2. Sujetos: COMPRADOR (izquierda, x < 260) y VENDEDOR (derecha, x >= 260)
        cls._parse_sujetos_blocks(all_blocks, full_text, data)

        # 3. Grano / Cultivo y Datos de la Operación
        cls._parse_grano(all_blocks, full_text, data)

        # 4. Deducciones Comerciales
        cls._parse_deducciones(full_text, data)

        # 5. Retenciones Fiscales
        cls._parse_retenciones(full_text, data)

        # 6. Totales Generales
        cls._parse_totales(full_text, data)

        # 7. Datos Adicionales (Contrato, Campaña, Tipo de Cambio)
        cls._parse_datos_adicionales(full_text, data)

        return data

    @classmethod
    def _parse_sujetos_blocks(cls, blocks, full_text, data):
        """
        Extrae Comprador y Vendedor utilizando la segmentación espacial de bloques
        (Comprador está en la columna izquierda x < 260; Vendedor en la columna derecha x >= 260).
        """
        comp_info = {}
        vend_info = {}

        for pno, x0, y0, x1, y1, text in blocks:
            if pno == 0 and 100 <= y0 <= 250:
                if 'Raz' in text or 'C.U.I.T.' in text or 'CUIT' in text:
                    m_rs = re.search(r'Raz[óo\?]n Social:\s*([^\n]+)', text, re.IGNORECASE)
                    m_cuit = re.search(r'C\.?U\.?I\.?T\.?:\s*(\d{11})', text, re.IGNORECASE)
                    m_dom = re.search(r'Domicilio:\s*([^\n]+)', text, re.IGNORECASE)
                    m_loc = re.search(r'Localidad:\s*([^\n]+)', text, re.IGNORECASE)
                    m_iva = re.search(r'I\.?V\.?A\.?:\s*([^\n]+)', text, re.IGNORECASE)
                    m_iibb = re.search(r'Ingresos Brutos N[º°\?]?\s*([^\n]+)', text, re.IGNORECASE)

                    info = {}
                    if m_rs: info['razon_social'] = m_rs.group(1).strip().upper()
                    if m_cuit: info['cuit'] = m_cuit.group(1).strip()
                    if m_dom: info['domicilio'] = m_dom.group(1).strip().upper()
                    if m_loc: info['localidad'] = m_loc.group(1).strip().upper()
                    if m_iva: info['condicion_iva'] = m_iva.group(1).strip().upper()
                    if m_iibb: info['iibb'] = m_iibb.group(1).strip()

                    if x0 < 260:
                        comp_info.update(info)
                    else:
                        vend_info.update(info)

        if not comp_info.get('cuit'):
            m_comp_hdr = re.search(r'CUIT:\s*(\d{11})\s+Raz[óo\?]n Social:\s*([^\n]+)', full_text)
            if m_comp_hdr:
                comp_info['cuit'] = m_comp_hdr.group(1).strip()
                comp_info['razon_social'] = m_comp_hdr.group(2).strip().upper()

        data['comprador'] = comp_info
        data['vendedor'] = vend_info

    @classmethod
    def _parse_grano(cls, blocks, text, data):
        """Extrae el código y nombre del cultivo, kilos, precios y subtotal."""
        data['grano'] = {
            'codigo_arca': 0,
            'descripcion_arca': 'SIN IDENTIFICAR',
            'kilos': Decimal('0.00'),
            'precio_unitario': Decimal('0.00'),
            'subtotal': Decimal('0.00'),
            'alicuota_iva': Decimal('10.50'),
            'importe_iva': Decimal('0.00'),
            'total_operacion': Decimal('0.00')
        }

        # Buscar grano en bloques o texto
        # 1. Búsqueda explícita de "XX - SOJA", "XX - MAIZ", etc.
        for cod, nom in GRANOS_ARCA_MAP.items():
            if re.search(rf'\b{cod}\s*-\s*{nom}\b', text, re.IGNORECASE) or re.search(rf'\b{cod}\s*-\s*{nom.split()[0]}\b', text, re.IGNORECASE):
                data['grano']['codigo_arca'] = cod
                data['grano']['descripcion_arca'] = nom
                break

        # Fallback genérico si no encontró en el mapa
        if data['grano']['codigo_arca'] == 0:
            m_grano = re.search(r'Grano[\s\S]*?(\d{1,3})\s*-\s*([A-ZÁÉÍÓÚÑ]+)', text)
            if m_grano:
                data['grano']['codigo_arca'] = int(m_grano.group(1))
                data['grano']['descripcion_arca'] = m_grano.group(2).strip().upper()

        # Extraer números de la tabla OPERACIÓN
        m_operacion = re.search(
            r'(\d+)\s*Kg[\s\n]+\$?\s*([\d.,]+)[\s\n]+\$?\s*([\d.,]+)[\s\n]+([\d.,]+)[\s\n]+\$?\s*([\d.,]+)[\s\n]+\$?\s*([\d.,]+)',
            text
        )
        if m_operacion:
            data['grano']['kilos'] = parse_decimal(m_operacion.group(1))
            data['grano']['precio_unitario'] = parse_decimal(m_operacion.group(2))
            data['grano']['subtotal'] = parse_decimal(m_operacion.group(3))
            data['grano']['alicuota_iva'] = parse_decimal(m_operacion.group(4))
            data['grano']['importe_iva'] = parse_decimal(m_operacion.group(5))
            data['grano']['total_operacion'] = parse_decimal(m_operacion.group(6))
        else:
            m_op_ajuste = re.search(
                r'(\d+)\s*Kg[\s\n]+\$?\s*([\d.,]+)[\s\n]+\$?\s*([\d.,]+)[\s\n]+\$?\s*([\d.,]+)[\s\n]+\$?\s*([\d.,]+)',
                text
            )
            if m_op_ajuste:
                data['grano']['kilos'] = parse_decimal(m_op_ajuste.group(1))
                data['grano']['precio_unitario'] = parse_decimal(m_op_ajuste.group(2))
                data['grano']['subtotal'] = parse_decimal(m_op_ajuste.group(3))
                data['grano']['importe_iva'] = parse_decimal(m_op_ajuste.group(4))
                data['grano']['total_operacion'] = parse_decimal(m_op_ajuste.group(5))

    @classmethod
    def _parse_deducciones(cls, text, data):
        """Extrae la lista de deducciones comerciales (fletes, comisiones, sellados, etc.)."""
        deducciones = []
        
        patron_ded = re.compile(
            r'(Otras Deducciones|Comision o Gastos Administrativos|Servicios de Acondicionamiento|Paritarias)[\s\n]+'
            r'([^\n]+(?:(?!\d+(?:\.\d+)?%)[\s\S])*?)[\s\n]+'
            r'(\d+(?:[.,]\d+)?)\s*%[\s\n]+'
            r'\$?\s*([\d.,]+)[\s\n]+'
            r'\$?\s*([\d.,]+)[\s\n]+'
            r'\$?\s*([\d.,]+)',
            re.MULTILINE
        )
        
        for m in patron_ded.finditer(text):
            tipo_ded = m.group(1).strip()
            concepto_raw = m.group(2).strip()
            concepto = ' '.join(concepto_raw.split())
            alicuota = parse_decimal(m.group(3))
            imp_iva = parse_decimal(m.group(4))
            base_calc = parse_decimal(m.group(5))
            total_ded = parse_decimal(m.group(6))
            
            if base_calc == Decimal('0.00') and total_ded == Decimal('0.00'):
                continue
                
            deducciones.append({
                'tipo_deduccion': tipo_ded,
                'concepto': concepto,
                'alicuota_iva': alicuota,
                'base_calculo': base_calc,
                'importe_iva': imp_iva,
                'total': total_ded
            })

        data['deducciones'] = deducciones

    @classmethod
    def _parse_retenciones(cls, text, data):
        """Extrae las retenciones impositivas (IVA RG 4310/2300, Ganancias, etc.)."""
        retenciones = []
        
        # Retención IVA
        m_ret_iva = re.search(
            r'RETENCI[ÓO\?]N\s+I\.?V\.?A\.?[\s\S]*?\$?\s*([\d.,]+)[\s\n]+(\d+(?:[.,]\d+)?)\s*%[\s\n]+\$?\s*([\d.,]+)',
            text, re.IGNORECASE
        )
        if m_ret_iva:
            base = parse_decimal(m_ret_iva.group(1))
            alic = parse_decimal(m_ret_iva.group(2))
            imp = parse_decimal(m_ret_iva.group(3))
            if imp > Decimal('0.00'):
                retenciones.append({
                    'impuesto': 'IVA',
                    'tipo': 'R',
                    'concepto': 'RETENCION IVA RG 4310',
                    'base_calculo': base,
                    'alicuota': alic,
                    'importe': imp
                })

        # Retención Ganancias
        m_ret_gan = re.search(
            r'RETENCI[ÓO\?]N\s+GANANCIAS?[\s\S]*?\$?\s*([\d.,]+)[\s\n]+(\d+(?:[.,]\d+)?)\s*%[\s\n]+\$?\s*([\d.,]+)',
            text, re.IGNORECASE
        )
        if m_ret_gan:
            base = parse_decimal(m_ret_gan.group(1))
            alic = parse_decimal(m_ret_gan.group(2))
            imp = parse_decimal(m_ret_gan.group(3))
            if imp > Decimal('0.00'):
                retenciones.append({
                    'impuesto': 'GAN',
                    'tipo': 'R',
                    'concepto': 'RETENCION GANANCIAS',
                    'base_calculo': base,
                    'alicuota': alic,
                    'importe': imp
                })

        data['retenciones'] = retenciones

    @classmethod
    def _parse_totales(cls, text, data):
        """Extrae los totales generales del comprobante."""
        totales = {
            'total_operacion': Decimal('0.00'),
            'total_deducciones': Decimal('0.00'),
            'total_retenciones_afip': Decimal('0.00'),
            'total_otras_retenciones': Decimal('0.00'),
            'total_percepciones': Decimal('0.00'),
            'importe_neto_pagar': Decimal('0.00')
        }

        # Total Operación
        m_tot_op = re.search(r'Total Operaci[óo\?]n:\s*\n?\s*\$?\s*([\d.,]+)', text, re.IGNORECASE)
        if m_tot_op:
            totales['total_operacion'] = parse_decimal(m_tot_op.group(1))
        elif data['grano'].get('total_operacion'):
            totales['total_operacion'] = data['grano']['total_operacion']

        # Total Deducciones
        m_tot_ded = re.search(r'Total Deducciones:\s*\n?\s*\$?\s*([\d.,]+)', text, re.IGNORECASE)
        if m_tot_ded:
            totales['total_deducciones'] = parse_decimal(m_tot_ded.group(1))

        # Total Retenciones AFIP
        m_tot_ret_afip = re.search(r'Total Retenciones Afip:\s*\n?\s*\$?\s*([\d.,]+)', text, re.IGNORECASE)
        if m_tot_ret_afip:
            totales['total_retenciones_afip'] = parse_decimal(m_tot_ret_afip.group(1))

        # Total Otras Retenciones
        m_tot_ret_otras = re.search(r'Total Otras Retenciones:\s*\n?\s*\$?\s*([\d.,]+)', text, re.IGNORECASE)
        if m_tot_ret_otras:
            totales['total_otras_retenciones'] = parse_decimal(m_tot_ret_otras.group(1))

        # Total Percepciones
        m_tot_perc = re.search(r'Total Percepciones:\s*\n?\s*\$?\s*([\d.,]+)', text, re.IGNORECASE)
        if m_tot_perc:
            totales['total_percepciones'] = parse_decimal(m_tot_perc.group(1))

        # Importe Neto a Pagar / Pago según condiciones
        m_neto_pagar = re.search(r'Importe Neto a Pagar:[\s\S]*?\$?\s*([\d.,]+)', text, re.IGNORECASE)
        if m_neto_pagar:
            totales['importe_neto_pagar'] = parse_decimal(m_neto_pagar.group(1))
        else:
            m_pago_cond = re.search(r'Pago seg[úu\?]n condiciones:\s*\n?\s*\$?\s*([\d.,]+)', text, re.IGNORECASE)
            if m_pago_cond:
                totales['importe_neto_pagar'] = parse_decimal(m_pago_cond.group(1))

        data['totales'] = totales

    @classmethod
    def _parse_datos_adicionales(cls, text, data):
        """Extrae Contrato, Campaña, Tipo de Cambio y desglose de IVA de Datos Adicionales."""
        adicionales = {}
        
        m_contrato = re.search(r'Contrato Nro\.:\s*([^\s-]+)', text)
        if m_contrato:
            adicionales['contrato'] = m_contrato.group(1).strip()

        m_campania = re.search(r'Campa[ñn\?]a:\s*([^\s-]+)', text)
        if m_campania:
            adicionales['campania'] = m_campania.group(1).strip()

        m_tc = re.search(r'Tipo Cambio\s*=\s*([\d.,]+)', text, re.IGNORECASE)
        if m_tc:
            adicionales['tipo_cambio'] = parse_decimal(m_tc.group(1), default=Decimal('1.00'))
        else:
            m_tc_alt = re.search(r'TC\s+([\d.,]+)', text, re.IGNORECASE)
            if m_tc_alt:
                adicionales['tipo_cambio'] = parse_decimal(m_tc_alt.group(1), default=Decimal('1.00'))
            else:
                adicionales['tipo_cambio'] = Decimal('1.00')

        data['datos_adicionales'] = adicionales
