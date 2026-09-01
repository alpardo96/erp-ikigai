"""
Motor de Extracción de Facturas con IA (Google Gemini).
Complementa el motor regex de AFIP y el OCR manual de Tesseract.

Usa el modelo gemini-2.5-flash con respuesta JSON estructurada
para extraer datos de facturas argentinas desde imágenes o PDFs.
"""
import os
import io
import json
import base64
from PIL import Image

# Schema de respuesta para Gemini (sin Pydantic para evitar dependencias innecesarias)
SCHEMA_FACTURA = {
    "type": "object",
    "properties": {
        "cuit": {
            "type": "string",
            "description": "CUIT del emisor/proveedor, solo dígitos (11 caracteres). Ej: 30712345678"
        },
        "fecha": {
            "type": "string",
            "description": "Fecha de emisión en formato DD/MM/YYYY. Ej: 15/06/2026"
        },
        "tipo": {
            "type": "string",
            "description": "Letra del comprobante: A, B, C o M"
        },
        "punto": {
            "type": "string",
            "description": "Punto de venta (4 o 5 dígitos). Ej: 0001"
        },
        "numero": {
            "type": "string",
            "description": "Número de comprobante (hasta 8 dígitos). Ej: 00012345"
        },
        "neto": {
            "type": "number",
            "description": "Importe Neto Gravado como número decimal. Ej: 12345.67"
        },
        "iva": {
            "type": "number",
            "description": "Total del IVA como número decimal. Ej: 2592.59"
        },
        "total": {
            "type": "number",
            "description": "Importe Total de la factura como número decimal. Ej: 14938.26"
        },
    },
    "required": ["cuit", "fecha", "tipo", "punto", "numero", "neto", "iva", "total"],
}

PROMPT_FACTURA = """Sos un extractor experto de datos de facturas argentinas (AFIP/ARCA).
Analizá esta imagen de factura y extraé los siguientes datos con la mayor precisión posible:

1. **CUIT del emisor/proveedor**: Solo dígitos, 11 caracteres. Buscá el CUIT que aparece junto al nombre del emisor, NO el del receptor.
2. **Fecha de emisión**: En formato DD/MM/YYYY.
3. **Tipo/Letra del comprobante**: A, B, C o M. Suele aparecer en grande en el encabezado.
4. **Punto de venta**: Los primeros 4-5 dígitos del número de factura (antes del guión).
5. **Número de comprobante**: Los dígitos después del guión en el número de factura.
6. **Neto Gravado**: El importe neto gravado (sin IVA). Como número decimal (usar punto como separador decimal).
7. **IVA**: El total del IVA. Como número decimal.
8. **Total**: El importe total de la factura. Como número decimal.

Si un campo no es visible o legible, devolvé string vacío para textos o 0 para números.
Los montos deben ser números con punto decimal (ej: 12345.67), NO usar coma como decimal."""


def _get_gemini_client():
    """
    Crea y retorna el cliente de Gemini.
    Retorna None si la API key no está configurada.
    """
    api_key = os.getenv('GEMINI_API_KEY', '')
    if not api_key:
        print("[Gemini] API Key no configurada en .env (GEMINI_API_KEY)")
        return None

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        return client
    except ImportError:
        print("[Gemini] La librería 'google-genai' no está instalada. Ejecutar: pip install google-genai")
        return None
    except Exception as e:
        print(f"[Gemini] Error al crear cliente: {e}")
        return None


def extraccion_gemini(file_bytes, filename):
    """
    Extrae datos de una factura usando Google Gemini (visión + JSON estructurado).

    Args:
        file_bytes: Bytes del archivo (PDF o imagen)
        filename: Nombre del archivo (para determinar el tipo)

    Returns:
        dict con los campos extraídos (mismo formato que extraccion_inteligente_afip_doc)
        o None si falla.
    """
    client = _get_gemini_client()
    if not client:
        return None

    try:
        from google.genai import types
        import fitz  # PyMuPDF

        # Convertir el archivo a imagen PIL
        is_pdf = filename.lower().endswith('.pdf')

        if is_pdf:
            # Renderizar primera página del PDF como imagen
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc.load_page(0)
            pix = page.get_pixmap(dpi=200)  # Mayor DPI para mejor lectura por IA
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))
        else:
            # Es una imagen directa
            img = Image.open(io.BytesIO(file_bytes))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

        # Llamar a Gemini con la imagen y el prompt
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[img, PROMPT_FACTURA],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SCHEMA_FACTURA,
                temperature=0.1,  # Baja temperatura para máxima precisión
            ),
        )

        # Parsear la respuesta JSON
        resultado_raw = json.loads(response.text)

        # Normalizar al formato que usa el sistema
        resultado = {}
        if resultado_raw.get('cuit'):
            # Limpiar CUIT: solo dígitos
            cuit_limpio = ''.join(c for c in str(resultado_raw['cuit']) if c.isdigit())
            if len(cuit_limpio) == 11:
                resultado['cuit'] = cuit_limpio
            elif cuit_limpio:
                resultado['cuit'] = cuit_limpio

        if resultado_raw.get('fecha'):
            resultado['fecha'] = str(resultado_raw['fecha'])

        if resultado_raw.get('tipo'):
            tipo = str(resultado_raw['tipo']).upper().strip()
            if tipo in ('A', 'B', 'C', 'M'):
                resultado['tipo'] = tipo

        if resultado_raw.get('punto'):
            resultado['punto'] = str(resultado_raw['punto']).lstrip('0') or '0'

        if resultado_raw.get('numero'):
            resultado['numero'] = str(resultado_raw['numero']).lstrip('0') or '0'

        # Montos numéricos
        for campo in ('neto', 'iva', 'total'):
            val = resultado_raw.get(campo, 0)
            try:
                val_float = float(val)
                if val_float > 0:
                    resultado[campo] = val_float
            except (ValueError, TypeError):
                pass

        print(f"[Gemini] Extracción exitosa: {len(resultado)} campos encontrados")
        return resultado if resultado else None

    except json.JSONDecodeError as e:
        print(f"[Gemini] Error parseando respuesta JSON: {e}")
        return None
    except Exception as e:
        error_msg = str(e).lower()
        if 'api_key' in error_msg or 'invalid' in error_msg:
            print(f"[Gemini] Error de autenticación - verificar GEMINI_API_KEY: {e}")
        elif 'quota' in error_msg or 'rate' in error_msg:
            print(f"[Gemini] Límite de uso alcanzado: {e}")
        else:
            print(f"[Gemini] Error en extracción: {e}")
        return None


def extraccion_gemini_recorte(image_base64_crop):
    """
    Usa Gemini para leer el texto de un recorte de imagen (alternativa a Tesseract).

    Args:
        image_base64_crop: String base64 de la imagen recortada

    Returns:
        str con el texto detectado, o cadena vacía si falla.
    """
    client = _get_gemini_client()
    if not client:
        return ""

    try:
        from google.genai import types

        # Decodificar base64
        if image_base64_crop.startswith('data:image'):
            image_base64_crop = image_base64_crop.split(',')[1]

        img_bytes = base64.b64decode(image_base64_crop)
        img = Image.open(io.BytesIO(img_bytes))

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[img, "Leé el texto visible en esta imagen. Devolvé SOLO el texto, sin explicaciones ni formato adicional. Si hay números con decimales, conservá el formato original."],
            config=types.GenerateContentConfig(
                temperature=0.0,
            ),
        )

        return response.text.strip() if response.text else ""

    except Exception as e:
        print(f"[Gemini] Error en OCR de recorte: {e}")
        return ""
