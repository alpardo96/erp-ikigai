import json
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from .models import Producto, Marca, Rubro, Familia
from .forms import ProductoForm, MarcaForm, RubroForm, FamiliaForm
from .services.busqueda_service import buscar_productos_inteligente
from empresas.models import Empresa

def producto_modal(request, id=None):
    empresa_id = request.session.get('empresa_id')
    if not empresa_id:
        return HttpResponse("Debe seleccionar una empresa primero.", status=400)
        
    empresa = get_object_or_404(Empresa, id=empresa_id)

    producto_base = None
    if id:
        producto = get_object_or_404(Producto, id=id, empresa=empresa)
    else:
        producto = None
        duplicar_de = request.GET.get('duplicar_de')
        if duplicar_de:
            producto_base = get_object_or_404(Producto, id=duplicar_de, empresa=empresa)

    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto, empresa=empresa)
        if form.is_valid():
            nuevo_producto = form.save(commit=False)
            nuevo_producto.empresa = empresa
            # Set created/modified by (AuditModel)
            if not id:
                nuevo_producto.creado_por = request.user
            nuevo_producto.modificado_por = request.user
            nuevo_producto.save()

            # Si el alta vino desde la carga de compra, devolvemos el producto para
            # cargarlo directo en el ítem (evento codprovEncontrado) y cerrar el modal.
            response = HttpResponse()
            if request.POST.get('origen') == 'compra':
                response['HX-Trigger'] = json.dumps({
                    'codprovEncontrado': {
                        'id': nuevo_producto.id,
                        'detalle': nuevo_producto.detalle.upper(),
                        'cto_rep': float(nuevo_producto.cto_rep or 0),
                    },
                    'cerrarModal': True,
                })
            else:
                response['HX-Trigger'] = 'productosActualizados'
            return response
    else:
        initial = {}
        if producto_base:
            # Duplicación inteligente: pre-cargamos todos los atributos del producto original
            initial = {
                'detalle': producto_base.detalle,
                'cod_prov': producto_base.cod_prov or '',
                'cod_fab': producto_base.cod_fab or '',
                'proveedor': producto_base.proveedor_id,
                'minimo': producto_base.minimo,
                'ptopedir': producto_base.ptopedir,
                'creden': producto_base.creden,
                'subprod': producto_base.subprod,
                'moneda': producto_base.moneda,
                'alic_iva': producto_base.alic_iva_porc,
                'margen': producto_base.margen,
                'marca': producto_base.marca_id,
                'rubro': producto_base.rubro_id,
                'familia': producto_base.familia_id,
                'unidad_venta': producto_base.unidad_venta or '',
                'peso_unitario_kg': producto_base.peso_unitario_kg,
                'unidades_por_bulto': producto_base.unidades_por_bulto,
            }
        elif not id:
            if request.GET.get('cod_prov'):
                initial['cod_prov'] = request.GET.get('cod_prov')
            if request.GET.get('proveedor'):
                initial['proveedor'] = request.GET.get('proveedor')

        form = ProductoForm(instance=producto, initial=initial, empresa=empresa)

    return render(request, 'productos/modals/producto_modal.html', {
        'form': form,
        'producto': producto,
        'producto_base': producto_base,
        'es_duplicado': bool(producto_base),
        'origen': request.GET.get('origen') or request.POST.get('origen') or '',
        'tipo_actividad': empresa.tipo_actividad or '',
    })

def buscar_productos(request):
    empresa_id = request.session.get('empresa_id')
    if not empresa_id:
        return HttpResponse("<tr><td colspan='100%' class='text-center p-4 text-red-500'>Debe seleccionar una empresa</td></tr>")

    q = request.GET.get('q', '').strip()
    campo = request.GET.get('campo', 'todos').strip()
    productos = buscar_productos_inteligente(q=q, empresa_id=empresa_id, campo=campo, limit=100)

    return render(request, 'productos/partials/producto_list.html', {'productos': productos})

def eliminar_producto(request, id):
    empresa_id = request.session.get('empresa_id')
    if request.method == 'DELETE' and empresa_id:
        producto = get_object_or_404(Producto, id=id, empresa_id=empresa_id)
        producto.delete()
        response = HttpResponse()
        response['HX-Trigger'] = 'productosActualizados'
        return response
    return HttpResponse(status=400)
# --- GESTIÓN DE MARCAS ---
def marca_modal(request, id=None):
    empresa_id = request.session.get('empresa_id')
    empresa = get_object_or_404(Empresa, id=empresa_id)
    marca = get_object_or_404(Marca, id=id, empresa=empresa) if id else None

    if request.method == 'POST':
        form = MarcaForm(request.POST, instance=marca, empresa=empresa)
        if form.is_valid():
            instancia = form.save(commit=False)
            instancia.empresa = empresa
            if not id: instancia.creado_por = request.user
            instancia.modificado_por = request.user
            instancia.save()
            # Marca pertenece unificadamente a Empresa (sin M2M sucursales)
            response = HttpResponse()
            response['HX-Trigger'] = 'marcasActualizadas'
            return response
    else:
        form = MarcaForm(instance=marca, empresa=empresa)

    return render(request, 'productos/modals/marca_modal.html', {'form': form, 'marca': marca})

def buscar_marcas(request):
    empresa_id = request.session.get('empresa_id')
    q = request.GET.get('q', '').strip()
    marcas = Marca.objects.filter(empresa_id=empresa_id)
    if q: marcas = marcas.filter(detalle__icontains=q)
    return render(request, 'configuracion/partials/marcas_list.html', {'marcas': marcas})

def eliminar_marca(request, id):
    empresa_id = request.session.get('empresa_id')
    if request.method == 'DELETE' and empresa_id:
        get_object_or_404(Marca, id=id, empresa_id=empresa_id).delete()
        response = HttpResponse()
        response['HX-Trigger'] = 'marcasActualizadas'
        return response
    return HttpResponse(status=400)

# --- GESTIÓN DE RUBROS PRODUCTOS ---
def rubro_prod_modal(request, id=None):
    empresa_id = request.session.get('empresa_id')
    empresa = get_object_or_404(Empresa, id=empresa_id)
    rubro = get_object_or_404(Rubro, id=id, empresa=empresa) if id else None

    if request.method == 'POST':
        form = RubroForm(request.POST, instance=rubro, empresa=empresa)
        if form.is_valid():
            instancia = form.save(commit=False)
            instancia.empresa = empresa
            if not id: instancia.creado_por = request.user
            instancia.modificado_por = request.user
            instancia.save()
            # Rubro pertenece unificadamente a Empresa (sin M2M sucursales)
            response = HttpResponse()
            response['HX-Trigger'] = 'rubrosProdActualizados'
            return response
    else:
        form = RubroForm(instance=rubro, empresa=empresa)

    return render(request, 'productos/modals/rubro_prod_modal.html', {'form': form, 'rubro': rubro})

def buscar_rubros_prod(request):
    empresa_id = request.session.get('empresa_id')
    q = request.GET.get('q', '').strip()
    rubros = Rubro.objects.filter(empresa_id=empresa_id).select_related('cta_ventas', 'cta_compras')
    if q: rubros = rubros.filter(detalle__icontains=q)
    return render(request, 'configuracion/partials/rubros_prod_list.html', {'rubros_prod': rubros})

def eliminar_rubro_prod(request, id):
    empresa_id = request.session.get('empresa_id')
    if request.method == 'DELETE' and empresa_id:
        get_object_or_404(Rubro, id=id, empresa_id=empresa_id).delete()
        response = HttpResponse()
        response['HX-Trigger'] = 'rubrosProdActualizados'
        return response
    return HttpResponse(status=400)

# --- GESTIÓN DE FAMILIAS ---
def familia_modal(request, id=None):
    empresa_id = request.session.get('empresa_id')
    empresa = get_object_or_404(Empresa, id=empresa_id)
    familia = get_object_or_404(Familia, id=id, empresa=empresa) if id else None

    if request.method == 'POST':
        form = FamiliaForm(request.POST, instance=familia, empresa=empresa)
        if form.is_valid():
            instancia = form.save(commit=False)
            instancia.empresa = empresa
            if not id: instancia.creado_por = request.user
            instancia.modificado_por = request.user
            instancia.save()
            # Familia pertenece unificadamente a Empresa (sin M2M sucursales)
            response = HttpResponse()
            response['HX-Trigger'] = 'familiasActualizadas'
            return response
    else:
        form = FamiliaForm(instance=familia, empresa=empresa)

    return render(request, 'productos/modals/familia_modal.html', {'form': form, 'familia': familia})

def buscar_familias(request):
    empresa_id = request.session.get('empresa_id')
    q = request.GET.get('q', '').strip()
    familias = Familia.objects.filter(empresa_id=empresa_id)
    if q: familias = familias.filter(detalle__icontains=q)
    return render(request, 'configuracion/partials/familias_list.html', {'familias': familias})

def eliminar_familia(request, id):
    empresa_id = request.session.get('empresa_id')
    if request.method == 'DELETE' and empresa_id:
        get_object_or_404(Familia, id=id, empresa_id=empresa_id).delete()
        response = HttpResponse()
        response['HX-Trigger'] = 'familiasActualizadas'
        return response
    return HttpResponse(status=400)


def obtener_margen(request):
    tipo = request.GET.get('tipo')
    id_obj = request.GET.get('id')
    
    if not id_obj or not tipo or id_obj == "":
        return HttpResponse("0")

    try:
        if tipo == 'marca':
            obj = Marca.objects.get(id=id_obj, empresa_id=request.session.get('empresa_id'))
        elif tipo == 'rubro':
            obj = Rubro.objects.get(id=id_obj, empresa_id=request.session.get('empresa_id'))
            response = HttpResponse(str(obj.margen))
            response['HX-Trigger'] = 'rubroCambiado'
            return response
        elif tipo == 'familia':
            obj = Familia.objects.get(id=id_obj, empresa_id=request.session.get('empresa_id'))
        else:
            return HttpResponse("0")
        return HttpResponse(str(obj.margen))
    except:
        return HttpResponse("0")

def filtrar_familias(request):
    rubro_id = request.GET.get('id')
    if not rubro_id:
        familias = Familia.objects.filter(empresa_id=request.session.get('empresa_id'))
    else:
        familias = Familia.objects.filter(rubro_id=rubro_id, empresa_id=request.session.get('empresa_id'))
    
    return render(request, 'productos/partials/familia_options.html', {'familias': familias})


# --- EXPORTACIÓN E IMPORTACIÓN EN EXCEL DE PRODUCTOS ---
from io import BytesIO
from django.utils.timezone import now
from .services.excel_service import (
    generar_excel_productos,
    procesar_captura_excel_productos
)

def exportar_productos_excel_completo(request):
    """
    Exporta la lista completa de productos de la empresa en un archivo Excel (.xlsx).
    """
    empresa_id = request.session.get('empresa_id')
    if not empresa_id:
        return HttpResponse("Debe seleccionar una empresa primero.", status=400)
    
    empresa = get_object_or_404(Empresa, id=empresa_id)
    q = request.GET.get('q', '').strip()
    productos = Producto.objects.filter(empresa=empresa)
    if q:
        productos = productos.filter(
            Producto.objects.filter(detalle__icontains=q) |
            Producto.objects.filter(cod_prov__icontains=q) |
            Producto.objects.filter(cod_fab__icontains=q)
        )
    productos = productos.order_by('detalle')

    empresa = get_object_or_404(Empresa, id=empresa_id)
    wb = generar_excel_productos(productos, empresa)
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"Productos_Completo_{now().strftime('%Y%m%d_%H%M')}.xlsx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def modal_capturar_excel(request):
    """
    Despliega el modal para subir y capturar el archivo Excel de Productos.
    """
    return render(request, 'productos/modals/capturar_excel_modal.html')


def capturar_productos_excel(request):
    """
    Procesa el archivo Excel subido, actualizando los productos por ID y creando los nuevos.
    """
    empresa_id = request.session.get('empresa_id')
    if not empresa_id:
        return HttpResponse("Debe seleccionar una empresa primero.", status=400)
    
    empresa = get_object_or_404(Empresa, id=empresa_id)

    if request.method != 'POST' or 'archivo_excel' not in request.FILES:
        return render(request, 'productos/modals/capturar_resultado_modal.html', {
            'resultado': {'errores': ['No se ha seleccionado ningún archivo Excel validó.']}
        })

    archivo = request.FILES['archivo_excel']
    if not archivo.name.endswith(('.xlsx', '.xls')):
        return render(request, 'productos/modals/capturar_resultado_modal.html', {
            'resultado': {'errores': ['El archivo debe tener extensión .xlsx o .xls.']}
        })

    resultado = procesar_captura_excel_productos(empresa, request.user, archivo)

    response = render(request, 'productos/modals/capturar_resultado_modal.html', {
        'resultado': resultado
    })
    response['HX-Trigger'] = 'productosActualizados'
    return response

