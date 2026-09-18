"""
Vistas del circuito de Órdenes de Compra (Plan 028 — Fase 2).

Incluye:
- Carga de OC (GET/POST) con ítems en sesión (key 'oc_items_temp') y patrón
  Typeahead + Lupa reutilizando los endpoints de productos/proveedor de compras.
- Listado con filtros y anulación lógica (conserva el número correlativo).
- Impresión PDF del documento.
- Endpoints HTMX de la grilla de ítems (agregar / editar / quitar).

El número se asigna al CONFIRMAR (siguiente_numero) dentro de la transacción de guardado.
"""
import json
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.db import transaction

from .models import OrdenCompra, OrdenCompraItem, ClienteProveedor
from empresas.models import Sucursal
from productos.models import Producto
from core.models import ContadorDocumento
from core.services.numeracion import siguiente_numero

SESSION_KEY = 'oc_items_temp'


def _num(raw, default='0'):
    """Convierte un importe a Decimal de forma robusta.
    - Si trae coma → formato es-AR ('1.234,56'): se quitan los puntos de miles y la coma pasa a punto.
    - Si NO trae coma → el punto (si hay) ya es el separador decimal (p. ej. el front lo limpió a
      '1234.56', o un input type=number manda '1.0000'): se respeta tal cual.
    Evita la doble limpieza que multiplicaba por 100."""
    s = (raw or '').strip()
    if not s:
        s = default
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return Decimal(default)


# ==============================================================================
# CARGA
# ==============================================================================

class OrdenCompraCargaView(LoginRequiredMixin, View):
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')
        if not empresa_id or not sucursal_id:
            messages.warning(request, "Por favor, seleccione una empresa y sucursal primero.")
            return redirect('seleccion_empresa')

        # Limpiar ítems temporales al iniciar carga nueva
        request.session[SESSION_KEY] = []

        sucursal = Sucursal.objects.filter(pk=sucursal_id).first()
        return render(request, 'facturacion/orden_compra_carga.html', {
            'fecha_hoy': timezone.localdate(),
            'punto': sucursal.punto if sucursal else 1,
        })

    def post(self, request):
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')
        if not empresa_id or not sucursal_id:
            messages.warning(request, "Seleccione empresa y sucursal.")
            return redirect('seleccion_empresa')

        proveedor_id = (request.POST.get('proveedor') or '').strip()
        items = request.session.get(SESSION_KEY, [])

        if not proveedor_id:
            messages.error(request, "Debe seleccionar un proveedor.")
            return redirect('oc_carga')
        if not items:
            messages.error(request, "Debe cargar al menos un producto en la orden.")
            return redirect('oc_carga')

        proveedor = get_object_or_404(ClienteProveedor, pk=proveedor_id, empresa_id=empresa_id)
        sucursal = get_object_or_404(Sucursal, pk=sucursal_id, empresa_id=empresa_id)

        carga_costos = request.POST.get('carga_costos') == 'on' or request.POST.get('carga_costos') == '1'
        condiciones_pago = (request.POST.get('condiciones_pago') or '').strip()
        observaciones = (request.POST.get('observaciones') or '').strip()
        moneda = (request.POST.get('moneda') or 'PES').strip()
        cotizacion = _num(request.POST.get('cotizacion'), '1')
        fecha = (request.POST.get('fecha') or '').strip() or timezone.localdate()

        with transaction.atomic():
            oc = OrdenCompra(
                empresa_id=empresa_id, sucursal=sucursal, punto=sucursal.punto,
                fecha=fecha, proveedor=proveedor, carga_costos=carga_costos,
                condiciones_pago=condiciones_pago,
                observaciones=observaciones, moneda=moneda, cotizacion=cotizacion,
                usuario=request.user, estado=OrdenCompra.CONFIRMADA,
                creado_por=request.user, modificado_por=request.user,
            )
            # Número correlativo al confirmar
            oc.numero = siguiente_numero(empresa_id, sucursal.punto, ContadorDocumento.ORDEN_COMPRA)
            oc.save()

            for it in items:
                cantidad = Decimal(str(it.get('cantidad') or 0))
                precio = Decimal(str(it.get('precio') or 0)) if carga_costos else Decimal('0')
                OrdenCompraItem.objects.create(
                    orden=oc, producto_id=it['producto_id'], cod_prov=it.get('cod_prov', ''),
                    cantidad=cantidad, cantidad_original=cantidad,
                    precio_unitario=precio, iva_alicuota=Decimal(str(it.get('iva') or 21)),
                )
            oc.recalcular_total()
            oc.save(update_fields=['total'])

        request.session[SESSION_KEY] = []
        request.session['auto_print_url'] = reverse('oc_imprimir', kwargs={'pk': oc.pk})
        messages.success(request, f"Orden de Compra {oc.punto:04d}-{oc.numero:08d} generada correctamente.")
        return redirect('oc_listado')


# ==============================================================================
# LISTADO / ANULACIÓN / IMPRESIÓN
# ==============================================================================

class OrdenCompraListView(LoginRequiredMixin, View):
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        if not empresa_id:
            messages.warning(request, "Seleccione una empresa primero.")
            return redirect('seleccion_empresa')

        desde = (request.GET.get('desde') or '').strip()
        hasta = (request.GET.get('hasta') or '').strip()
        proveedor_id = (request.GET.get('proveedor') or '').strip()
        estado = (request.GET.get('estado') or '').strip()

        # Primera entrada (sin parámetros en la URL): precargar el rango del ejercicio vigente.
        # DESDE = inicio del ejercicio; HASTA = menor entre cierre del ejercicio y hoy.
        # Con esto se listan todas las OC del ejercicio; los filtros quedan para búsquedas puntuales.
        if not request.GET:
            from empresas.models import Ejercicio
            ejercicio_id = request.session.get('ejercicio_id')
            ejercicio = None
            if ejercicio_id:
                ejercicio = Ejercicio.objects.filter(pk=ejercicio_id, empresa_id=empresa_id).first()
            if not ejercicio:
                ejercicio = Ejercicio.objects.filter(empresa_id=empresa_id).order_by('-inicio').first()
            if ejercicio:
                hoy = timezone.localdate()
                desde = ejercicio.inicio.isoformat()
                hasta = min(ejercicio.cierre, hoy).isoformat()

        ordenes = (OrdenCompra.objects.filter(empresa_id=empresa_id)
                   .select_related('proveedor', 'sucursal'))
        if desde:
            ordenes = ordenes.filter(fecha__gte=desde)
        if hasta:
            ordenes = ordenes.filter(fecha__lte=hasta)
        if proveedor_id:
            ordenes = ordenes.filter(proveedor_id=proveedor_id)
        if estado != '':
            ordenes = ordenes.filter(estado=estado)
        ordenes = ordenes.order_by('-fecha', '-oc_id')

        proveedores = (ClienteProveedor.objects
                       .filter(ordenes_compra__empresa_id=empresa_id).distinct()
                       .order_by('razon_social'))
        return render(request, 'facturacion/orden_compra_listado.html', {
            'ordenes': ordenes[:500],
            'proveedores': proveedores,
            'desde': desde, 'hasta': hasta, 'proveedor_id': proveedor_id, 'estado': estado,
            'ESTADOS': OrdenCompra.ESTADOS,
        })


class OrdenCompraBajaView(LoginRequiredMixin, View):
    """Anulación lógica de la OC (conserva el número correlativo). No se elimina el
    registro. En Fase 7 revertirá imputaciones si las hubiera."""
    def post(self, request, oc_id):
        empresa_id = request.session.get('empresa_id')
        oc = get_object_or_404(OrdenCompra, pk=oc_id, empresa_id=empresa_id)

        if oc.estado == OrdenCompra.ANULADA:
            pass  # idempotente
        elif oc.estado_recepcion != OrdenCompra.PENDIENTE or oc.estado_facturacion != OrdenCompra.PENDIENTE:
            return HttpResponse(
                f'<tr class="bg-red-50"><td colspan="7" class="px-4 py-3 text-red-700 font-bold '
                f'text-[11px] italic">No se puede anular la OC {oc.punto:04d}-{oc.numero}: '
                f'tiene recepciones o facturas asociadas.</td></tr>', status=200)
        else:
            oc.estado = OrdenCompra.ANULADA
            oc.modificado_por = request.user
            oc.save(update_fields=['estado', 'modificado_por', 'fecha_modificacion'])

        return render(request, 'facturacion/partials/oc_fila.html', {'oc': oc})


class OrdenCompraImprimirView(LoginRequiredMixin, View):
    def get(self, request, oc_id):
        empresa_id = request.session.get('empresa_id')
        oc = get_object_or_404(
            OrdenCompra.objects.select_related('proveedor', 'sucursal', 'empresa', 'medio_pago'),
            pk=oc_id, empresa_id=empresa_id)
        from facturacion.services.reportes_pdf import render_pdf_response
        return render_pdf_response(
            'facturacion/pdf/orden_compra_pdf.html',
            {'oc': oc, 'items': oc.items.select_related('producto').all()},
            f"OC_{oc.punto:04d}-{oc.numero:08d}.pdf",
        )


# ==============================================================================
# ÍTEMS EN SESIÓN (HTMX)
# ==============================================================================

def _render_tabla(request):
    items = request.session.get(SESSION_KEY, [])
    return render(request, 'facturacion/partials/oc_items_tabla.html', {'items': items})


class _ItemBase(LoginRequiredMixin, View):
    pass


class OcItemAddView(_ItemBase):
    def get(self, request):
        # Carga inicial de la grilla (hx-trigger="load")
        return _render_tabla(request)

    def post(self, request):
        producto_id = (request.POST.get('producto_id') or '').strip()
        cantidad = _num(request.POST.get('cantidad'), '1')
        neto = _num(request.POST.get('neto'), '0')
        precio = float(neto) / float(cantidad) if float(cantidad) > 0 else float(neto)

        if not producto_id:
            return _render_tabla(request)

        items = request.session.get(SESSION_KEY)
        if items is None:
            items = []

        if any(str(i['producto_id']) == str(producto_id) for i in items):
            return HttpResponse('<div class="p-4 bg-red-100 text-red-700 font-bold">Este producto ya está en la orden.</div>', status=200)

        try:
            producto = Producto.objects.get(id=producto_id, empresa_id=request.session.get('empresa_id'))
        except (Producto.DoesNotExist, ValueError):
            return HttpResponse(f'<div class="p-4 bg-red-100 text-red-700 font-bold">Producto ID [{producto_id}] inexistente.</div>', status=200)

        iva = float(producto.alic_iva_porc)
        total = float(cantidad) * float(precio)
        # Cód. del proveedor: se consigna SOLO si el proveedor de la OC es el habitual del
        # producto (producto.proveedor_id == proveedor seleccionado). Si no, queda vacío.
        proveedor_id = (request.POST.get('proveedor') or '').strip()
        cod_prov = ''
        if producto.proveedor_id and proveedor_id and str(producto.proveedor_id) == str(proveedor_id):
            cod_prov = producto.cod_prov or ''
        items.append({
            'index': len(items),
            'producto_id': producto.id,
            'codigo': cod_prov,          # vacío si el proveedor no es el habitual
            'cod_prov': cod_prov,
            'cod_fab': producto.cod_fab,
            'detalle': producto.detalle,
            'cantidad': float(cantidad),
            'precio': float(precio),
            'iva': iva,
            'total': round(total, 2),
        })
        request.session[SESSION_KEY] = items
        request.session.modified = True
        resp = _render_tabla(request)
        resp['HX-Trigger'] = 'limpiarInputsOC'
        return resp


class OcItemEditView(_ItemBase):
    def post(self, request, index):
        items = request.session.get(SESSION_KEY, [])
        if 0 <= index < len(items):
            cantidad = _num(request.POST.get('cantidad'), str(items[index]['cantidad']))
            neto = _num(request.POST.get('neto'), str(items[index]['total']))
            precio = float(neto) / float(cantidad) if float(cantidad) > 0 else float(neto)
            
            items[index]['cantidad'] = float(cantidad)
            items[index]['precio'] = float(precio)
            items[index]['total'] = round(float(cantidad) * float(precio), 2)
            request.session[SESSION_KEY] = items
        resp = _render_tabla(request)
        resp['HX-Trigger'] = json.dumps({'actualizarTotalesOC': True})
        return resp


class OcItemRemoveView(_ItemBase):
    def post(self, request, index):
        items = request.session.get(SESSION_KEY, [])
        if 0 <= index < len(items):
            items.pop(index)
            for i, it in enumerate(items):
                it['index'] = i
        request.session[SESSION_KEY] = items
        resp = _render_tabla(request)
        resp['HX-Trigger'] = json.dumps({'actualizarTotalesOC': True})
        return resp


# ==============================================================================
# INTEGRACIÓN CON LA FACTURA DE COMPRA (Plan 028 Fase 5)
# Aviso de OC pendientes + vinculación que puebla la grilla de la factura.
# ==============================================================================

def _ocs_pendientes_facturacion(empresa_id, proveedor_id):
    """OC del proveedor confirmadas y pendientes de facturar (no COMPLETA, no anuladas)."""
    return (OrdenCompra.objects
            .filter(empresa_id=empresa_id, proveedor_id=proveedor_id, estado=OrdenCompra.CONFIRMADA)
            .exclude(estado_facturacion=OrdenCompra.COMPLETA)
            .order_by('fecha', 'numero'))


class FacturaOcAvisoView(LoginRequiredMixin, View):
    """Devuelve un banner si el proveedor tiene OC pendientes de facturar (o vacío)."""
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        proveedor_id = (request.GET.get('proveedor') or '').strip()
        if not proveedor_id:
            return HttpResponse('')
        cant = _ocs_pendientes_facturacion(empresa_id, proveedor_id).count()
        from .models import Recepcion
        cant_rec = Recepcion.objects.filter(empresa_id=empresa_id, proveedor_id=proveedor_id, estado=Recepcion.ACTIVA, generada_por_factura__isnull=True).count()
        if not cant and not cant_rec:
            return HttpResponse('')
        return render(request, 'facturacion/partials/factura_oc_aviso.html', {'cant': cant, 'cant_rec': cant_rec})


class FacturaVincularOcModalView(LoginRequiredMixin, View):
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        proveedor_id = (request.GET.get('proveedor') or '').strip()
        if not proveedor_id:
            return HttpResponse("<div class='p-4 text-red-500 font-bold'>Seleccione un proveedor primero.</div>", status=400)
        ordenes = _ocs_pendientes_facturacion(empresa_id, proveedor_id)
        seleccionadas = set(request.session.get('compra_oc_ids', []))
        return render(request, 'facturacion/modals/factura_vincular_oc.html', {
            'ordenes': ordenes, 'seleccionadas': seleccionadas,
        })


class FacturaVincularOcView(LoginRequiredMixin, View):
    """Puebla la grilla de la factura (compra_items_temp) con las líneas pendientes de
    facturar de las OC seleccionadas, TOTALIZADAS POR CÓDIGO. Cada ítem lleva metadata
    'oc_fuentes' (líneas de OC en FIFO) y 'cantidad_recepcionada' para el cotejo."""
    def post(self, request):
        empresa_id = request.session.get('empresa_id')
        oc_ids = [int(x) for x in request.POST.getlist('oc_ids') if x.isdigit()]
        ocs = (OrdenCompra.objects
               .filter(empresa_id=empresa_id, oc_id__in=oc_ids)
               .prefetch_related('items__producto').order_by('fecha', 'numero'))

        por_prod = {}
        for oc in ocs:
            for li in oc.items.all():
                if li.pendiente_facturacion <= 0:
                    continue
                pid = li.producto_id
                if pid not in por_prod:
                    por_prod[pid] = {
                        'producto': li.producto,
                        'cantidad_oc': Decimal('0'),
                        'pend_fact': Decimal('0'),
                        'recibida': Decimal('0'),
                        'precio': Decimal('0'),
                        'fuentes': [],
                    }
                e = por_prod[pid]
                e['cantidad_oc'] += li.cantidad
                e['pend_fact'] += li.pendiente_facturacion
                e['recibida'] += li.cantidad_recibida
                if e['precio'] == 0 and li.precio_unitario:
                    e['precio'] = li.precio_unitario
                e['fuentes'].append({'oc_item_id': li.pk, 'pendiente_facturacion': float(li.pendiente_facturacion)})

        items = [_armar_item_oc(idx, e) for idx, e in enumerate(por_prod.values())]

        request.session['compra_items_temp'] = items
        request.session['compra_oc_ids'] = oc_ids
        request.session.modified = True

        resp = render(request, 'facturacion/partials/compra_cotejo_tabla.html', {'items': items})
        resp['HX-Trigger'] = json.dumps({'cerrarModal': True, 'actualizarTotales': True, 'ocVinculada': True})
        return resp


class FacturaVincularRecepcionModalView(LoginRequiredMixin, View):
    def get(self, request):
        from .models import Recepcion
        empresa_id = request.session.get('empresa_id')
        proveedor_id = (request.GET.get('proveedor') or '').strip()
        if not proveedor_id:
            return HttpResponse("<div class='p-4 text-red-500 font-bold'>Seleccione un proveedor primero.</div>", status=400)
        
        # Recepciones activas, que no provienen de facturas.
        recepciones = (Recepcion.objects
                       .filter(empresa_id=empresa_id, proveedor_id=proveedor_id, estado=Recepcion.ACTIVA, generada_por_factura__isnull=True)
                       .order_by('fecha', 'numero'))
        
        seleccionadas = set(request.session.get('compra_recepcion_ids', []))
        return render(request, 'facturacion/modals/factura_vincular_recepcion.html', {
            'recepciones': recepciones, 'seleccionadas': seleccionadas,
        })


class FacturaVincularRecepcionView(LoginRequiredMixin, View):
    """Puebla la grilla de la factura desde Remitos (Recepciones). 
    Busca las Órdenes de Compra vinculadas a estas Recepciones y arma la tabla
    respetando los precios si tenían carga_costos=True."""
    def post(self, request):
        from .models import RecepcionImputacion
        empresa_id = request.session.get('empresa_id')
        rec_ids = [int(x) for x in request.POST.getlist('recepcion_ids') if x.isdigit()]

        imps = (RecepcionImputacion.objects
               .filter(recepcion_item__recepcion__empresa_id=empresa_id, recepcion_item__recepcion_id__in=rec_ids)
               .select_related('orden_item__producto', 'orden_item__orden'))

        oc_item_cantidades = {}
        for imp in imps:
            li = imp.orden_item
            if not li or li.pendiente_facturacion <= 0:
                continue
            oc_item_cantidades[li] = oc_item_cantidades.get(li, Decimal('0')) + imp.cantidad

        por_prod = {}
        oc_ids_afectadas = set()
        
        for li, cant_en_recs in oc_item_cantidades.items():
            pid = li.producto_id
            if pid not in por_prod:
                por_prod[pid] = {
                    'producto': li.producto,
                    'cantidad_oc': Decimal('0'),
                    'pend_fact': Decimal('0'),
                    'recibida': Decimal('0'),
                    'precio': Decimal('0'),
                    'fuentes': [],
                    'precio_readonly': False,
                }
            e = por_prod[pid]
            e['cantidad_oc'] += li.cantidad
            e['recibida'] += li.cantidad_recibida
            
            cant_a_facturar = min(cant_en_recs, li.pendiente_facturacion)
            e['pend_fact'] += cant_a_facturar
            
            if e['precio'] == 0 and li.precio_unitario:
                e['precio'] = li.precio_unitario
                
            if getattr(li.orden, 'carga_costos', False):
                e['precio_readonly'] = True
                
            e['fuentes'].append({'oc_item_id': li.pk, 'pendiente_facturacion': float(li.pendiente_facturacion)})
            oc_ids_afectadas.add(li.orden_id)

        items = [_armar_item_oc(idx, e) for idx, e in enumerate(por_prod.values())]

        request.session['compra_items_temp'] = items
        # Almacenamos las recepciones y también los oc_ids para que _procesar_circuito_oc funcione igual
        request.session['compra_oc_ids'] = list(oc_ids_afectadas)
        request.session['compra_recepcion_ids'] = rec_ids
        request.session.modified = True

        resp = render(request, 'facturacion/partials/compra_cotejo_tabla.html', {'items': items})
        resp['HX-Trigger'] = json.dumps({'cerrarModal': True, 'actualizarTotales': True, 'ocVinculada': True})
        return resp


# ------------------------------------------------------------------------------
# COTEJO en la Factura (grilla inline con OC / recepcionada / facturada / precio)
# ------------------------------------------------------------------------------

def _recalcular_cotejo(item):
    """Recalcula total, pendiente de recepción y candidato a diferencia de un ítem OC."""
    cantidad = float(item.get('cantidad') or 0)          # facturada
    precio = float(item.get('precio') or 0)
    recep = float(item.get('cantidad_recepcionada') or 0)
    cant_oc = float(item.get('cantidad_oc') or 0)
    item['total'] = round(cantidad * precio, 2)
    item['cto_adq'] = precio
    item['cto_rep'] = precio
    # Pendiente de recepción: lo facturado que aún no fue recepcionado (rojo en la UI).
    item['pendiente_recep'] = round(cantidad - recep, 2)
    # Candidato a diferencia: facturado == recepcionado pero difieren de la cantidad de la OC.
    item['es_candidato'] = bool(item.get('oc_fuentes')) and cantidad == recep and cantidad != cant_oc
    return item


def _armar_item_oc(idx, e):
    prod = e['producto']
    cantidad = float(e['pend_fact'])
    precio = float(e['precio'])
    iva = float(prod.alic_iva_porc)
    margen = float(prod.margen or 0)
    item = {
        'index': idx,
        'producto_id': prod.id,
        'codigo': prod.cod_prov or prod.id,
        'cod_fab': prod.cod_fab,
        'detalle': prod.detalle,
        'cantidad': cantidad,          # facturada (editable)
        'precio': precio,              # precio facturado (editable)
        'iva': iva,
        'total': round(cantidad * precio, 2),
        'cto_adq': precio,
        'cto_rep': precio,
        'precio_lista': precio,
        'descuento': 0.0,
        'margen': margen,
        'precio_vta_actual': float(prod.precio_total or 0),
        'precio_vta_nuevo': round(precio * (1 + margen / 100) * (1 + iva / 100), 2),
        # Metadata del circuito OC:
        'oc_fuentes': e['fuentes'],
        'oc_item_ids': [f['oc_item_id'] for f in e['fuentes']],
        'cantidad_oc': float(e['cantidad_oc']),
        'cantidad_recepcionada': float(e['recibida']),
        'decision': 'marcar',
        'precio_readonly': e.get('precio_readonly', False),
    }
    return _recalcular_cotejo(item)


def _render_cotejo(request):
    return render(request, 'facturacion/partials/compra_cotejo_tabla.html',
                  {'items': request.session.get('compra_items_temp', [])})


class FacturaCotejoEditView(LoginRequiredMixin, View):
    def post(self, request, index):
        items = request.session.get('compra_items_temp', [])
        if 0 <= index < len(items):
            it = items[index]
            it['cantidad'] = float(_num(request.POST.get('cantidad'), str(it.get('cantidad', 0))))
            it['precio'] = float(_num(request.POST.get('precio'), str(it.get('precio', 0))))
            decision = (request.POST.get('decision') or '').strip()
            if decision in ('ajustar', 'marcar'):
                it['decision'] = decision
            _recalcular_cotejo(it)
            request.session['compra_items_temp'] = items
            request.session.modified = True
        resp = _render_cotejo(request)
        resp['HX-Trigger'] = json.dumps({'actualizarTotales': True})
        return resp


class FacturaCotejoRemoveView(LoginRequiredMixin, View):
    def post(self, request, index):
        items = request.session.get('compra_items_temp', [])
        if 0 <= index < len(items):
            items.pop(index)
            for i, it in enumerate(items):
                it['index'] = i
        request.session['compra_items_temp'] = items
        request.session.modified = True
        resp = _render_cotejo(request)
        resp['HX-Trigger'] = json.dumps({'actualizarTotales': True})
        return resp


# ==============================================================================
# LEGAJO DE OC + DESAFECTACIÓN (Plan 028 Fase 7)
# ==============================================================================

class OrdenCompraLegajoView(LoginRequiredMixin, View):
    """Muestra todos los documentos vinculados a una OC: líneas con avance, recepciones
    y facturas imputadas. Permite desafectar una factura (revierte su imputación sin
    borrarla) para el circuito NC-anula + nueva factura corregida."""
    def get(self, request, oc_id):
        from .models import RecepcionImputacion, CompraOCImputacion, Recepcion, Compra
        empresa_id = request.session.get('empresa_id')
        oc = get_object_or_404(
            OrdenCompra.objects.select_related('proveedor', 'sucursal', 'medio_pago'),
            pk=oc_id, empresa_id=empresa_id)

        # Recepciones vinculadas (por imputación de sus líneas).
        rec_ids = (RecepcionImputacion.objects
                   .filter(orden_item__orden=oc)
                   .values_list('recepcion_item__recepcion_id', flat=True).distinct())
        recepciones = Recepcion.objects.filter(recepcion_id__in=list(rec_ids)).order_by('fecha', 'numero')

        # Facturas vinculadas (por imputación de sus ítems) + total imputado a esta OC.
        fact_rows = {}
        for imp in (CompraOCImputacion.objects
                    .filter(orden_item__orden=oc)
                    .select_related('compra_item__compra__tipo')):
            compra = imp.compra_item.compra
            r = fact_rows.setdefault(compra.compras_id, {'compra': compra, 'imputado': Decimal('0')})
            r['imputado'] += imp.cantidad

        return render(request, 'facturacion/orden_compra_legajo.html', {
            'oc': oc,
            'items': oc.items.select_related('producto').all(),
            'recepciones': recepciones,
            'facturas': list(fact_rows.values()),
        })


class CorrelativosAuditoriaView(LoginRequiredMixin, View):
    """Vista de auditoría de integridad de correlativos (Plan 028 Fase 8)."""
    def get(self, request):
        from core.services.numeracion import auditar_correlativos
        empresa_id = request.session.get('empresa_id')
        if not empresa_id:
            return redirect('seleccion_empresa')
        filas = auditar_correlativos(empresa_id=empresa_id)
        return render(request, 'facturacion/correlativos_auditoria.html', {'filas': filas})


class FacturaDesafectarOcView(LoginRequiredMixin, View):
    """Desafecta una factura de una OC: revierte su cantidad_facturada imputada a esa OC
    y borra las imputaciones, SIN borrar la factura. Recalcula estados."""
    def post(self, request, oc_id, compra_id):
        from .models import CompraOCImputacion
        empresa_id = request.session.get('empresa_id')
        oc = get_object_or_404(OrdenCompra, pk=oc_id, empresa_id=empresa_id)
        with transaction.atomic():
            imps = (CompraOCImputacion.objects
                    .filter(orden_item__orden=oc, compra_item__compra_id=compra_id)
                    .select_related('orden_item'))
            for imp in imps:
                oi = imp.orden_item
                oi.cantidad_facturada = oi.cantidad_facturada - imp.cantidad
                oi.save(update_fields=['cantidad_facturada'])
            imps.delete()
            oc.recalcular_estados()
        messages.success(request, f"Factura desafectada de la OC {oc.punto:04d}-{oc.numero}.")
        return redirect('oc_legajo', oc_id=oc.oc_id)
