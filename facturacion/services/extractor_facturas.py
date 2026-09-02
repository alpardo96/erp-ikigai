# pyrefly: ignore [missing-import]
import pytesseract
from PIL import Image, ImageOps
# pyrefly: ignore [missing-import]
import fitz  # PyMuPDF
import os
import platform
import re
import io
import base64

# Configurar la ruta de Tesseract en Windows automáticamente
if platform.system() == 'Windows':
    _posibles_rutas = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Tesseract-OCR', 'tesseract.exe'),
    ]
    for ruta in _posibles_rutas:
        if os.path.exists(ruta):
            pytesseract.pytesseract.tesseract_cmd = ruta
            break

def parse_monto(texto):
    """
    Toma un texto como '$ 12.345,67', '12345.67', '12,345.67' y lo limpia para devolver float
    """
    if not texto:
        return 0.0
    texto = texto.strip().replace('$', '').strip()
    
    last_comma = texto.rfind(',')
    last_dot = texto.rfind('.')
    
    if last_comma > last_dot:
        # Formato ej. 12.345,67 o 12345,67
        texto = texto.replace('.', '')
        texto = texto.replace(',', '.')
    elif last_dot > last_comma and last_comma != -1:
        # Formato ej. 12,345.67
        texto = texto.replace(',', '')
    else:
        # Solo hay un tipo de separador
        if last_comma != -1:
            if len(texto) - last_comma - 1 <= 2:
                texto = texto.replace(',', '.')
            else:
                texto = texto.replace(',', '')
        elif last_dot != -1:
            if len(texto) - last_dot - 1 == 2:
                # Es un decimal
                pass
            else:
                texto = texto.replace('.', '')
                
    try:
        return float(texto)
    except:
        return 0.0

def procesar_factura_archivo(file_path, filename, tipo_actividad=None):
    """
    Procesa un archivo PDF o Imagen desde el disco.
    Retorna un diccionario con:
      - 'image_url': URL de la vista previa temporal generada
      - 'datos': Diccionario con la extracción inteligente
    """
    is_pdf = filename.lower().endswith('.pdf')
    datos_extraidos = {}
    image_url = ""
    
    try:
        import os
        from django.conf import settings
        import uuid
        
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_facturas')
        os.makedirs(temp_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        img_filename = f"{base_name}.webp"
        img_filepath = os.path.join(temp_dir, img_filename)
        image_url = f"/media/temp_facturas/{img_filename}"
        
        if is_pdf:
            # Abrir PDF desde archivo
            doc = fitz.open(file_path)
            
            # Extracción inteligente
            datos_extraidos = extraccion_inteligente_afip_doc(doc)
            
            if datos_extraidos and 'cuit' in datos_extraidos:
                cuit_limpio = datos_extraidos['cuit']
                try:
                    import importlib
                    perfil_modulo = None
                    if tipo_actividad:
                        try:
                            # Intentar buscar el perfil específico de la verticalidad
                            perfil_modulo = importlib.import_module(f"verticalidades.{tipo_actividad}.perfiles_lectura.cuit_{cuit_limpio}")
                        except ImportError:
                            pass
                    
                    if not perfil_modulo:
                        # Fallback al directorio genérico (aunque esté vacío ahora)
                        perfil_modulo = importlib.import_module(f"facturacion.services.perfiles_lectura.cuit_{cuit_limpio}")

                    
                    texto_completo = ""
                    for page in doc:
                        texto_completo += page.get_text("text", sort=True) + "\n"
                    
                    perfil_resultado = perfil_modulo.procesar_perfil(texto_completo)
                    items = perfil_resultado.get('items', [])
                    datos_extraidos['items'] = items
                    if 'cabecera_overrides' in perfil_resultado:
                        datos_extraidos.update(perfil_resultado['cabecera_overrides'])
                        
                    print(f"Perfil de lectura cargado para CUIT {cuit_limpio}. Items extraídos: {len(items)}")
                except ModuleNotFoundError:
                    pass
                except Exception as e:
                    print(f"Error ejecutando perfil para CUIT {cuit_limpio}: {e}")
            
            # Convertir todas las páginas a imagen (máximo 5) y unirlas
            max_pages = min(5, len(doc))
            images = []
            for i in range(max_pages):
                page = doc.load_page(i)
                pix = page.get_pixmap(dpi=150) # 150 DPI es buen balance para web
                mode = "RGBA" if pix.alpha else "RGB"
                img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
                images.append(img)
                
            if images:
                total_width = max(img.width for img in images)
                total_height = sum(img.height for img in images)
                stitched = Image.new('RGB', (total_width, total_height), (255, 255, 255))
                y_offset = 0
                for img in images:
                    if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                    stitched.paste(img, (0, y_offset))
                    y_offset += img.height
                
                stitched.save(img_filepath, format="WEBP", quality=85)
            
        else:
            # Es una imagen
            img = Image.open(file_path)
            # La extracción inteligente por ahora solo funciona con texto PDF
            # Pero podemos devolver la imagen temporal
            if img.mode in ("RGBA", "P"): img = img.convert("RGB")
            img.save(img_filepath, format="WEBP", quality=85)
            
    except Exception as e:
        print(f"Error procesando factura en memoria: {e}")
        
    return {
        'image_url': image_url,
        'datos': datos_extraidos if datos_extraidos else {}
    }

def procesar_recorte_memoria(image_base64_crop):
    """
    Recibe un string base64 de un recorte de imagen, y aplica OCR (Tesseract).
    """
    try:
        if image_base64_crop.startswith('data:image'):
            # Remover header
            image_base64_crop = image_base64_crop.split(',')[1]
            
        img_bytes = base64.b64decode(image_base64_crop)
        img = Image.open(io.BytesIO(img_bytes))
        
        # Preprocesamiento
        img = img.convert('L')
        img = img.point(lambda p: p > 150 and 255)
        img = ImageOps.expand(img, border=10, fill='white')
        
        texto = pytesseract.image_to_string(img, config='--psm 7').strip()
        if not texto or len(texto) < 2:
            texto = pytesseract.image_to_string(img, config='--psm 6').strip()
            
        return texto
    except Exception as e:
        if "tesseract is not installed" in str(e).lower():
            return "ERROR: Tesseract OCR no está instalado en Windows."
        print(f"Error en OCR memoria: {e}")
        return ""

def extraccion_inteligente_afip_doc(doc):
    """
    Extrae datos fijos de una factura de AFIP escaneando el texto de un objeto fitz.Document.
    """
    try:
        texto = ""
        for page in doc:
            texto += page.get_text("text", sort=True) + "\n"
            
        resultados = {}
        
        # CUIT
        cuit_match = re.search(r'C\.?U\.?I\.?T\.?[:\s]+(\d{2}-\d{8}-\d{1}|\d{11})', texto)
        if cuit_match:
            cuit_raw = cuit_match.group(1)
            cuit_limpio = re.sub(r"[^\d]", "", cuit_raw)
            resultados['cuit'] = cuit_limpio
            resultados['cuit_raw'] = cuit_raw
            
        # Fecha
        fecha_match = re.search(r'\bFecha(?:\s+de)?(?:\s+Emisi[oó]n)?\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})', texto)
        if fecha_match:
            resultados['fecha'] = fecha_match.group(1)
            
        # Punto y Comprobante
        punto_match = re.search(r'Punto de Venta[:\s]+(\d{4,5})', texto)
        comp_match = re.search(r'Comp\. Nro[:\s]+(\d{8})', texto)
        if punto_match: resultados['punto'] = punto_match.group(1)
        if comp_match: resultados['numero'] = comp_match.group(1)
        
        if 'punto' not in resultados or 'numero' not in resultados:
            nro_match = re.search(r'(\d{4,5})-(\d{6,10})', texto)
            if nro_match:
                resultados['punto'] = nro_match.group(1)
                resultados['numero'] = nro_match.group(2)

        # Tipo
        cod_match = re.search(r'COD(?:IGO)?[.\s\r\n]*(?:N[°ºo.]*)?[.\s\r\n]*0*(\d{1,3})', texto, re.IGNORECASE)
        if cod_match:
            codigo = int(cod_match.group(1))
            resultados['tipo_comprobante_afip'] = str(codigo)
            if codigo in [1, 2, 3, 4, 5, 39, 60, 63]: resultados['tipo'] = 'A'
            elif codigo in [6, 7, 8, 9, 10, 40, 61, 64]: resultados['tipo'] = 'B'
            elif codigo in [11, 12, 13, 15]: resultados['tipo'] = 'C'
            elif codigo in [51, 52, 53, 54]: resultados['tipo'] = 'M'
            else: resultados['tipo'] = str(codigo)
        else:
            tipo_match = re.search(r'\b([ABCM])\b', texto)
            if tipo_match:
                resultados['tipo'] = tipo_match.group(1).upper()
            
        # NETO
        neto_match = re.search(r'(Importe\s+Neto\s+Gravado|Neto\s+Gravado|SUB\s*TOTAL|SUBTOTAL|Sub-Total|Subtotal)\s*[:\-]?\s*\$?\s*([\d\.\,]+)', texto)
        if neto_match:
            resultados['neto'] = parse_monto(neto_match.group(2))
        else:
            lineas = texto.splitlines()
            candidatos = []
            for i, line in enumerate(lineas):
                if re.search(r'SUB\s*TOTAL|SUBTOTAL|Sub-Total|Subtotal:', line, re.IGNORECASE):
                    nums = re.findall(r'\$?\s*([\d\.\.]*\,?\d{2})', line)
                    for n in nums:
                        candidatos.append(parse_monto(n))

            if candidatos:
                resultados['neto'] = max(candidatos)
            else:
                resultados['neto'] = 0.0
        
        # IVA
        iva_matches = re.findall(r'IVA\s*\d+(?:[.,]\d+)?\s*%?[^0-9]{0,20}\$?\s*([\d\.\,]+)', texto)
        if iva_matches:
            total_iva = 0.0
            for iva in iva_matches:
                val = parse_monto(iva)
                total_iva += val
            resultados['iva'] = total_iva
        else:
            resultados['iva'] = 0.0

        # Total        
        total_match = re.search(r'(Importe\s+Total|Total\s+A\s+Pagar|\bTOTAL\b|\bTotal\b)\s*[:\s]*\$?\s*([\d\.\,]+)', texto)
        if total_match:
            resultados['total'] = parse_monto(total_match.group(2))
            
        return resultados
    except Exception as e:
        print(f"Error en extracción AFIP doc: {e}")
        return None
