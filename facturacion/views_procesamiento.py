from django.shortcuts import render
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from .services.extractor_facturas import procesar_factura_archivo, procesar_recorte_memoria
import json
import os
import uuid
from django.conf import settings
import time

def _limpiar_temp_facturas(temp_dir):
    try:
        now = time.time()
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            if os.path.isfile(file_path):
                if os.stat(file_path).st_mtime < now - 3600:
                    try:
                        os.remove(file_path)
                    except:
                        pass
    except Exception as e:
        print(f"Error limpiando temp_facturas: {e}")

class CargaCompraAutomaticaView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, 'facturacion/carga_compra_automatica.html')

    def post(self, request):
        if 'archivo_factura' in request.FILES:
            archivo = request.FILES['archivo_factura']
            file_bytes = archivo.read()
            
            # Guardamos físicamente en temp_facturas
            temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_facturas')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Limpiar archivos huérfanos más antiguos a 1 hora
            _limpiar_temp_facturas(temp_dir)
            
            file_uuid = uuid.uuid4().hex
            file_ext = os.path.splitext(archivo.name)[1]
            temp_filename = f"{file_uuid}{file_ext}"
            temp_filepath = os.path.join(temp_dir, temp_filename)
            
            with open(temp_filepath, 'wb') as f:
                f.write(file_bytes)
                
            pdf_temp_path = f"temp_facturas/{temp_filename}"
            
            # Obtener tipo_actividad para inyectar el perfil correcto
            from empresas.models import Empresa
            empresa_id = request.session.get('empresa_id')
            tipo_actividad = None
            if empresa_id:
                empresa = Empresa.objects.filter(id=empresa_id).first()
                if empresa and empresa.tipo_actividad:
                    tipo_actividad = empresa.tipo_actividad.lower()
            
            # Procesar el archivo pasándole la ruta, no los bytes
            resultado = procesar_factura_archivo(temp_filepath, archivo.name, tipo_actividad=tipo_actividad)
            
            # Borrar el archivo original PDF/Imagen ya que nos quedamos con el WEBP
            try:
                os.remove(temp_filepath)
            except:
                pass
            
            # Agregamos el path al resultado apuntando al WEBP generado
            pdf_temp_path = f"temp_facturas/{os.path.splitext(temp_filename)[0]}.webp"
            resultado['pdf_temp_path'] = pdf_temp_path
            
            # Si el perfil cargó ítems, los buscamos y los guardamos en la sesión
            if resultado.get('datos') and 'items' in resultado['datos']:
                items_extraidos = resultado['datos']['items']
                items_sesion = []
                from productos.models import Producto
                empresa_id = request.session.get('empresa_id')
                for i, it in enumerate(items_extraidos):
                    prod = Producto.objects.filter(empresa_id=empresa_id, cod_prov=it['codigo']).first()
                    if not prod and it.get('codigo_alt'):
                        prod = Producto.objects.filter(empresa_id=empresa_id, cod_prov=it['codigo_alt']).first()
                        
                    if not prod:
                        prod = Producto.objects.filter(empresa_id=empresa_id, detalle__icontains=it['codigo']).first()
                    if not prod and it.get('codigo_alt'):
                        prod = Producto.objects.filter(empresa_id=empresa_id, detalle__icontains=it['codigo_alt']).first()
                        
                    if prod:
                        items_sesion.append({
                            'index': len(items_sesion),
                            'producto_id': prod.id,
                            'codigo': prod.cod_prov or '',
                            'detalle': prod.detalle,
                            'cantidad': float(it['cantidad']),
                            'precio': float(it['precio_unitario']),
                            'total': float(it['total']),
                            'iva': float(it.get('iva_porc') if it.get('iva_porc') is not None else prod.alic_iva_porc),
                            'cto_adq': float(it['precio_unitario']),
                            'cto_rep': float(prod.cto_rep or it['precio_unitario']),
                            'descuento': 0.0,
                            'precio_venta': float(prod.precio_total or 0.0),
                            'margen': float(prod.margen or 0.0),
                            'moneda': resultado['datos'].get('moneda') or prod.moneda,
                            'subprod': prod.subprod,
                            'series': it.get('subproductos', []),
                        })
                request.session['compra_items_temp'] = items_sesion
                request.session.modified = True
                
            # Buscar el proveedor por CUIT para autocompletar
            if resultado.get('datos'):
                if 'cuit' in resultado['datos']:
                    from facturacion.models import ClienteProveedor
                    cuit = resultado['datos']['cuit']
                    prov = ClienteProveedor.objects.filter(empresa_id=request.session.get('empresa_id'), cuit=cuit, tipo_entidad=2).first()
                    if prov:
                        resultado['datos']['proveedor_id'] = prov.codigo_id
                        resultado['datos']['proveedor_nombre'] = prov.razon_social
                        resultado['datos']['proveedor_cta_res'] = prov.cta_res or ''
                        
                if 'tipo_comprobante_afip' in resultado['datos']:
                    from facturacion.models import TipoComprobante
                    codigo_buscar = str(resultado['datos']['tipo_comprobante_afip']).zfill(3)
                    tc = TipoComprobante.objects.filter(codigo=codigo_buscar).first()
                    if tc:
                        resultado['datos']['tipo_comprobante_codigo'] = tc.codigo
                        resultado['datos']['tipo_comprobante_detalle'] = tc.detalle
                elif 'tipo_comprobante_codigo' in resultado['datos']:
                    from facturacion.models import TipoComprobante
                    tc = TipoComprobante.objects.filter(codigo=resultado['datos']['tipo_comprobante_codigo']).first()
                    if tc:
                        resultado['datos']['tipo_comprobante_detalle'] = tc.detalle
            
            return JsonResponse({
                'status': 'ok',
                'image_url': resultado.get('image_url'),
                'pdf_temp_path': resultado.get('pdf_temp_path'),
                'datos': resultado.get('datos')
            })
            
        return JsonResponse({'status': 'error', 'message': 'No se envió archivo'}, status=400)

class ProcesarRecorteOCRView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            image_crop = data.get('image_crop')
            
            if not image_crop:
                return JsonResponse({'status': 'error', 'message': 'Falta image_crop'})
            
            # El OCR se hace 100% sobre el recorte recibido (Base64)
            texto = procesar_recorte_memoria(image_crop)
                
            if texto.startswith("ERROR: Tesseract"):
                return JsonResponse({'status': 'error', 'message': texto})
                
            return JsonResponse({'status': 'ok', 'texto': texto})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
