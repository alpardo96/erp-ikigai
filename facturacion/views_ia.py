"""
Vista independiente para la Carga de Compras con IA (Google Gemini).
No modifica ni depende de las vistas de carga automática existentes.
"""
from django.shortcuts import render
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from .services.extractor_ia import extraccion_gemini
import json
import io
import base64
import fitz  # PyMuPDF
from PIL import Image


class CargaCompraIAView(LoginRequiredMixin, View):
    """Vista GET para renderizar el template de carga con IA."""
    def get(self, request):
        return render(request, 'facturacion/carga_compra_ia.html')


class ProcesarFacturaIAView(LoginRequiredMixin, View):
    """
    Vista POST que recibe un archivo (PDF o imagen) y lo procesa
    usando Gemini para extraer los datos de la factura.
    Retorna JSON con la imagen en base64 y los datos extraídos.
    """
    def post(self, request):
        if 'archivo_factura' not in request.FILES:
            return JsonResponse({'status': 'error', 'message': 'No se envió archivo'}, status=400)

        archivo = request.FILES['archivo_factura']
        file_bytes = archivo.read()
        filename = archivo.name

        # 1. Convertir a imagen base64 para el frontend
        base64_image = ""
        try:
            is_pdf = filename.lower().endswith('.pdf')
            if is_pdf:
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                page = doc.load_page(0)
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                base64_image = "data:image/png;base64," + base64.b64encode(img_bytes).decode('utf-8')
            else:
                img = Image.open(io.BytesIO(file_bytes))
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_bytes = buffered.getvalue()
                base64_image = "data:image/png;base64," + base64.b64encode(img_bytes).decode('utf-8')
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Error al procesar imagen: {e}'}, status=400)

        # 2. Extraer datos con Gemini IA
        datos = extraccion_gemini(file_bytes, filename)

        if datos is None:
            return JsonResponse({
                'status': 'ok',
                'image_url': base64_image,
                'datos': {},
                'error_ia': 'No se pudo conectar con Gemini. Verificar GEMINI_API_KEY en .env'
            })

        return JsonResponse({
            'status': 'ok',
            'image_url': base64_image,
            'datos': datos
        })
