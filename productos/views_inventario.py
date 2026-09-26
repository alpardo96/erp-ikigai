import json
import logging
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.db.models import Q, F
from django.utils import timezone
from facturacion.helpers import parsear_decimal_ar
from empresas.models import Empresa, Sucursal
from productos.models import Producto, StockSucursal, TomaInventario, TomaInventarioItem, Rubro, Familia, Subfamilia, Marca
from productos.forms import TomaInventarioFiltroForm, TomaInventarioItemEditForm, TomaInventarioRechazoForm
from productos.services.stock_service import aplicar_inventario_al_stock, recalcular_stock

logger = logging.getLogger(__name__)


def _obtener_empresa_request(request):
    empresa = getattr(request, 'empresa', None)
    if not empresa:
        empresa_id = request.session.get('empresa_id')
        if empresa_id:
            empresa = Empresa.objects.filter(id=empresa_id).first()
        else:
            empresa = Empresa.objects.first()
    return empresa


class InventarioListView(LoginRequiredMixin, TemplateView):
    """
    Listado histórico de Tomas de Inventario por Sucursal/Empresa (Plan 095).
    """
    template_name = 'productos/inventario/inventario_listado.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        empresa = _obtener_empresa_request(self.request)
        sucursal_id = self.request.session.get('sucursal_id')
        
        sucursales = Sucursal.objects.filter(empresa=empresa)
        sucursal_actual = None
        if sucursal_id:
            sucursal_actual = sucursales.filter(id=sucursal_id).first()
        if not sucursal_actual:
            sucursal_actual = sucursales.first()

        estado_filtro = self.request.GET.get('estado', '')
        qs = TomaInventario.objects.filter(empresa=empresa)
        if sucursal_actual:
            qs = qs.filter(sucursal=sucursal_actual)
        if estado_filtro:
            qs = qs.filter(estado=estado_filtro)

        ctx['inventarios'] = qs.select_related('sucursal', 'usuario_autorizo').prefetch_related('items').order_by('-fecha_toma', '-numero')
        ctx['sucursales'] = sucursales
        ctx['sucursal_actual'] = sucursal_actual
        ctx['estado_filtro'] = estado_filtro
        return ctx


class InventarioCargaView(LoginRequiredMixin, TemplateView):
    """
    Pantalla de creación y recuento interactivo de Inventario (General o Parcial).
    """
    template_name = 'productos/inventario/inventario_carga.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        empresa = _obtener_empresa_request(self.request)
        sucursal_id = self.request.session.get('sucursal_id')
        sucursales = Sucursal.objects.filter(empresa=empresa)
        sucursal_actual = sucursales.filter(id=sucursal_id).first() if sucursal_id else sucursales.first()

        inventario_id = self.kwargs.get('pk')
        inventario = None
        if inventario_id:
            inventario = get_object_or_404(TomaInventario, pk=inventario_id, empresa=empresa)
        
        ctx['filtro_form'] = TomaInventarioFiltroForm(empresa=empresa)
        ctx['sucursal_actual'] = sucursal_actual
        ctx['inventario'] = inventario
        if inventario:
            ctx['items'] = inventario.items.select_related('producto', 'producto__rubro', 'producto__familia', 'producto__subfamilia', 'producto__marca').order_by('producto__rubro__detalle', 'producto__familia__detalle', 'producto__subfamilia__detalle', 'producto__detalle')
        return ctx


@login_required
def inventario_iniciar_o_generar(request):
    """
    Inicia una nueva toma de inventario o genera la grilla de productos según filtros.
    """
    empresa = _obtener_empresa_request(request)
    if not empresa:
        return HttpResponse('<div class="p-4 text-red-600">Empresa no seleccionada</div>', status=400)

    sucursal_id = request.session.get('sucursal_id')
    sucursal = Sucursal.objects.filter(empresa=empresa, id=sucursal_id).first()
    if not sucursal:
        sucursal = Sucursal.objects.filter(empresa=empresa).first()

    if request.method == 'POST':
        tipo_alcance = request.POST.get('tipo_alcance', 'PARCIAL')
        rubro_id = request.POST.get('rubro')
        familia_id = request.POST.get('familia')
        subfamilia_id = request.POST.get('subfamilia')
        marca_id = request.POST.get('marca')
        proveedor_id = request.POST.get('proveedor')
        buscar_texto = request.POST.get('buscar_texto', '').strip()
        observaciones = request.POST.get('observaciones', '').strip()

        # Obtener siguiente número correlativo
        ultimo_num = TomaInventario.objects.filter(empresa=empresa, sucursal=sucursal).order_by('-numero').values_list('numero', flat=True).first() or 0
        nuevo_num = ultimo_num + 1

        # Construir resumen de filtros
        filtros_desc = []
        if tipo_alcance == 'GENERAL':
            filtros_desc.append("Todos los productos")
        else:
            if rubro_id:
                r = Rubro.objects.filter(id=rubro_id).first()
                if r: filtros_desc.append(f"Rubro: {r.detalle}")
            if familia_id:
                f = Familia.objects.filter(id=familia_id).first()
                if f: filtros_desc.append(f"Familia: {f.detalle}")
            if subfamilia_id:
                sf = Subfamilia.objects.filter(id=subfamilia_id).first()
                if sf: filtros_desc.append(f"Subfamilia: {sf.detalle}")
            if marca_id:
                m = Marca.objects.filter(id=marca_id).first()
                if m: filtros_desc.append(f"Marca: {m.detalle}")
            if buscar_texto:
                filtros_desc.append(f"Búsqueda: '{buscar_texto}'")

        inventario = TomaInventario.objects.create(
            empresa=empresa,
            sucursal=sucursal,
            numero=nuevo_num,
            fecha_toma=timezone.now(),
            tipo_alcance=tipo_alcance,
            filtros_aplicados=" | ".join(filtros_desc) if filtros_desc else "Sin filtros específicos",
            observaciones=observaciones,
            estado='BORRADOR',
            creado_por=request.user
        )

        # Poblar productos según filtro si se solicitó generar
        qs_prod = Producto.objects.filter(empresa=empresa, activo=True)
        if tipo_alcance == 'PARCIAL':
            if rubro_id:
                qs_prod = qs_prod.filter(rubro_id=rubro_id)
            if familia_id:
                qs_prod = qs_prod.filter(familia_id=familia_id)
            if subfamilia_id:
                qs_prod = qs_prod.filter(subfamilia_id=subfamilia_id)
            if marca_id:
                qs_prod = qs_prod.filter(marca_id=marca_id)
            if proveedor_id:
                qs_prod = qs_prod.filter(proveedor_id=proveedor_id)
            if buscar_texto:
                qs_prod = qs_prod.filter(
                    Q(detalle__icontains=buscar_texto) |
                    Q(cod_prov__icontains=buscar_texto) |
                    Q(cod_fab__icontains=buscar_texto) |
                    Q(codigo_anterior__icontains=buscar_texto)
                )

        # Cargar productos en la toma física con su stock teórico actual
        # Consultar stock por sucursal
        stock_map = {
            stk.producto_id: stk.cantidad
            for stk in StockSucursal.objects.filter(sucursal=sucursal, producto__in=qs_prod)
        }

        items_to_create = []
        for prod in qs_prod.order_by('rubro__detalle', 'familia__detalle', 'subfamilia__detalle', 'detalle'):
            stk_actual = stock_map.get(prod.id, Decimal('0.00'))
            items_to_create.append(TomaInventarioItem(
                inventario=inventario,
                producto=prod,
                stock_teorico=stk_actual,
                cantidad_contada=stk_actual, # Inicializa con stock teórico para agilizar
                diferencia=Decimal('0.00'),
                usuario_conteo=request.user,
                fecha_hora=timezone.now()
            ))

        if items_to_create:
            TomaInventarioItem.objects.bulk_create(items_to_create)

        return redirect('inventario_editar', pk=inventario.pk)

    return redirect('inventario_listado')


@login_required
def inventario_item_agregar_rapido(request, pk):
    """
    Agrega un producto puntual por ID o buscador typeahead a la grilla de un inventario existente.
    """
    empresa = _obtener_empresa_request(request)
    inventario = get_object_or_404(TomaInventario, pk=pk, empresa=empresa)
    if inventario.estado != 'BORRADOR':
        return HttpResponse('<div class="text-red-500 text-xs">El inventario ya no está en borrador</div>', status=400)

    producto_id = request.POST.get('producto_id')
    if not producto_id:
        return HttpResponse('<div class="text-red-500 text-xs">Seleccione un producto</div>', status=400)

    producto = get_object_or_404(Producto, pk=producto_id, empresa=empresa)
    
    # Obtener stock teórico
    stk_suc = StockSucursal.objects.filter(sucursal=inventario.sucursal, producto=producto).first()
    stk_teorico = stk_suc.cantidad if stk_suc else Decimal('0.00')

    # Si ya existe, no duplicar, sino traerlo
    item, created = TomaInventarioItem.objects.get_or_create(
        inventario=inventario,
        producto=producto,
        defaults={
            'stock_teorico': stk_teorico,
            'cantidad_contada': stk_teorico,
            'diferencia': Decimal('0.00'),
            'usuario_conteo': request.user,
            'fecha_hora': timezone.now()
        }
    )

    items = inventario.items.select_related('producto', 'producto__rubro', 'producto__familia', 'producto__subfamilia', 'producto__marca').order_by('producto__rubro__detalle', 'producto__familia__detalle', 'producto__subfamilia__detalle', 'producto__detalle')
    return render(request, 'productos/inventario/partials/grilla_items.html', {
        'inventario': inventario,
        'items': items,
        'highlight_item_id': item.id
    })


@login_required
def inventario_item_actualizar_cantidad(request, item_id):
    """
    Actualiza la cantidad contada de una fila de la grilla vía HTMX con cálculo inmediato de diferencia.
    """
    empresa = _obtener_empresa_request(request)
    item = get_object_or_404(TomaInventarioItem, pk=item_id, inventario__empresa=empresa)
    inventario = item.inventario
    
    # Verificar si es el operador en borrador o el autorizador
    es_autorizador = request.user.has_perm('productos.can_authorize_inventario') or request.user.is_superuser or getattr(request.user, 'rol_id', None) == 1
    
    if inventario.estado not in ['BORRADOR', 'PENDIENTE']:
        return HttpResponse('<div class="text-red-500 text-xs">Inventario cerrado</div>', status=400)

    if inventario.estado == 'PENDIENTE' and not es_autorizador:
        return HttpResponse('<div class="text-red-500 text-xs">Solo autorizadores pueden editar en estado pendiente</div>', status=403)

    valor_raw = request.POST.get('cantidad_contada', '').strip()
    nueva_cant = parsear_decimal_ar(valor_raw)

    if inventario.estado == 'PENDIENTE' and es_autorizador:
        if not item.modificado_por_autorizador:
            item.cantidad_original_operador = item.cantidad_contada
            item.modificado_por_autorizador = True

    item.cantidad_contada = nueva_cant
    item.diferencia = nueva_cant - (item.stock_teorico or Decimal('0.00'))
    item.usuario_conteo = request.user
    item.fecha_hora = timezone.now()
    item.save()

    return render(request, 'productos/inventario/partials/fila_item.html', {
        'inventario': inventario,
        'item': item,
        'es_autorizador': es_autorizador
    })


@login_required
def inventario_item_eliminar(request, item_id):
    """
    Elimina un ítem de la toma de inventario en borrador.
    """
    empresa = _obtener_empresa_request(request)
    item = get_object_or_404(TomaInventarioItem, pk=item_id, inventario__empresa=empresa)
    inventario = item.inventario
    if inventario.estado != 'BORRADOR':
        return HttpResponse('<div class="text-red-500 text-xs">No se puede eliminar de un inventario cerrado</div>', status=400)

    item.delete()
    items = inventario.items.select_related('producto', 'producto__rubro', 'producto__familia', 'producto__subfamilia', 'producto__marca').order_by('producto__rubro__detalle', 'producto__familia__detalle', 'producto__subfamilia__detalle', 'producto__detalle')
    return render(request, 'productos/inventario/partials/grilla_items.html', {
        'inventario': inventario,
        'items': items
    })


@login_required
def inventario_enviar_autorizacion(request, pk):
    """
    Cierra la toma de inventario por parte del operador y la envía para autorización.
    """
    empresa = _obtener_empresa_request(request)
    inventario = get_object_or_404(TomaInventario, pk=pk, empresa=empresa)
    if inventario.estado != 'BORRADOR':
        messages.error(request, "El inventario no se encuentra en estado Borrador.")
        return redirect('inventario_listado')

    if not inventario.items.exists():
        messages.error(request, "No puede enviar un inventario sin productos contados.")
        return redirect('inventario_editar', pk=pk)

    inventario.estado = 'PENDIENTE'
    inventario.save(update_fields=['estado'])
    messages.success(request, f"Inventario N° {inventario.numero:04d} enviado a Autorización exitosamente.")
    return redirect('inventario_listado')


@login_required
def inventario_autorizar_modal(request, pk):
    """
    Modal para que el supervisor o administrador revise diferencias, ajuste cantidades si es necesario y autorice.
    """
    empresa = _obtener_empresa_request(request)
    inventario = get_object_or_404(TomaInventario, pk=pk, empresa=empresa)
    items = inventario.items.select_related('producto', 'producto__rubro', 'producto__familia', 'producto__subfamilia').order_by('producto__rubro__detalle', 'producto__detalle')
    
    # Métricas del inventario
    total_items = items.count()
    sobrantes = items.filter(diferencia__gt=0).count()
    faltantes = items.filter(diferencia__lt=0).count()
    sin_dif = items.filter(diferencia=0).count()

    return render(request, 'productos/inventario/modals/autorizar_modal.html', {
        'inventario': inventario,
        'items': items,
        'total_items': total_items,
        'sobrantes': sobrantes,
        'faltantes': faltantes,
        'sin_dif': sin_dif,
        'form_rechazo': TomaInventarioRechazoForm()
    })


@login_required
def inventario_autorizar_procesar(request, pk):
    """
    Aprueba el inventario, cambia su estado a 'APLICADO' e impacta en el stock disponible (Plan 095).
    """
    if request.method != 'POST':
        return HttpResponse('Método no permitido', status=405)

    empresa = _obtener_empresa_request(request)
    inventario = get_object_or_404(TomaInventario, pk=pk, empresa=empresa)
    if inventario.estado not in ['PENDIENTE', 'BORRADOR']:
        return JsonResponse({'success': False, 'error': 'El inventario ya fue procesado o anulado.'}, status=400)

    # Aplicar al stock y generar auditoría
    aplicar_inventario_al_stock(inventario, usuario_autorizo=request.user)

    messages.success(request, f"Inventario N° {inventario.numero:04d} APROBADO y aplicado al stock con éxito.")
    return HttpResponse(
        '<script>window.location.reload();</script>',
        content_type='text/html'
    )


@login_required
def inventario_rechazar_procesar(request, pk):
    """
    Rechaza el inventario o lo devuelve a borrador para reconteo con observaciones.
    """
    if request.method != 'POST':
        return HttpResponse('Método no permitido', status=405)

    empresa = _obtener_empresa_request(request)
    inventario = get_object_or_404(TomaInventario, pk=pk, empresa=empresa)
    motivo = request.POST.get('motivo_rechazo', '').strip()
    accion = request.POST.get('accion', 'DEVOLVER') # 'DEVOLVER' o 'RECHAZAR'

    if accion == 'DEVOLVER':
        inventario.estado = 'BORRADOR'
    else:
        inventario.estado = 'RECHAZADO'

    inventario.motivo_rechazo = motivo
    inventario.usuario_autorizo = request.user
    inventario.fecha_autorizo = timezone.now()
    inventario.save(update_fields=['estado', 'motivo_rechazo', 'usuario_autorizo', 'fecha_autorizo'])

    msg = f"Inventario N° {inventario.numero:04d} devuelto a Conteo para revisión." if accion == 'DEVOLVER' else f"Inventario N° {inventario.numero:04d} RECHAZADO."
    messages.warning(request, msg)
    return HttpResponse(
        '<script>window.location.reload();</script>',
        content_type='text/html'
    )


@login_required
def inventario_anular(request, pk):
    """
    Anula una toma de inventario en borrador o pendiente.
    """
    empresa = _obtener_empresa_request(request)
    inventario = get_object_or_404(TomaInventario, pk=pk, empresa=empresa)
    if inventario.estado == 'APLICADO':
        messages.error(request, "No se puede anular un inventario que ya fue aplicado al stock.")
        return redirect('inventario_listado')

    inventario.estado = 'ANULADO'
    inventario.save(update_fields=['estado'])
    messages.info(request, f"Inventario N° {inventario.numero:04d} anulado.")
    return redirect('inventario_listado')


@login_required
def inventario_imprimir_planilla(request, pk):
    """
    Genera la Planilla de Conteo Físico en PDF optimizada para impresión (Plan 095).
    Orden jerárquico estricto: Rubro -> Familia -> Subfamilia -> Detalle.
    """
    import io
    from django.template.loader import get_template
    from xhtml2pdf import pisa

    empresa = _obtener_empresa_request(request)
    inventario = get_object_or_404(TomaInventario, pk=pk, empresa=empresa)
    items = inventario.items.select_related(
        'producto', 'producto__rubro', 'producto__familia', 'producto__subfamilia', 'producto__marca'
    ).order_by(
        'producto__rubro__detalle',
        'producto__familia__detalle',
        'producto__subfamilia__detalle',
        'producto__detalle'
    )

    items_list = list(items)
    items_pares = []
    for i in range(0, len(items_list), 2):
        izq = items_list[i]
        der = items_list[i+1] if (i+1) < len(items_list) else None
        items_pares.append((izq, der))

    template = get_template('productos/inventario/pdf/planilla_conteo_pdf.html')
    html = template.render({
        'inventario': inventario,
        'items': items,
        'items_pares': items_pares,
        'empresa': empresa,
        'fecha_impresion': timezone.now()
    })

    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        filename = f"Planilla_Inventario_{inventario.numero:04d}_{inventario.sucursal.nombre}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    return HttpResponse('Error generando PDF', status=500)

