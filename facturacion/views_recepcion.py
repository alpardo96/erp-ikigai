"""
Vistas del Informe de Recepción (Plan 028 — Fase 4, circuito de proveedor).

Flujo:
- Cabecera: sucursal destino (define punto/número), proveedor (lupa), N° remito del proveedor.
- "Vincular OC": trae las líneas pendientes de recepción de las OC seleccionadas,
  TOTALIZADAS POR CÓDIGO, con la cantidad recibida editable (default = pendiente).
- Ítems manuales opcionales (recepción sin OC) vía Typeahead + Lupa.
- Al confirmar: se asigna número, se crean RecepcionItem (→ ENTRADA de stock por señal),
  se imputa lo recibido a las líneas de OC en FIFO (acumula cantidad_recibida) y se
  recalculan los estados de las OC afectadas. Se imprime el Informe.

Baja = anulación lógica (Fase 7).
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

from .models import (
    Recepcion, RecepcionItem, RecepcionImputacion,
    OrdenCompra, OrdenCompraItem, ClienteProveedor, RemitoInterno,
)
from empresas.models import Sucursal, Ejercicio
from productos.models import Producto
from core.models import ContadorDocumento
from core.services.numeracion import siguiente_numero

SESSION_ITEMS = 'recepcion_items_temp'
SESSION_OCS = 'recepcion_oc_ids'


def _num(raw, default='0'):
    """Parse robusto: si trae coma → es-AR (quita miles, coma→punto); si no, el punto ya es
    decimal (el front lo limpia a '1234.56'). Evita la doble limpieza que multiplicaba por 100."""
    s = (raw or '').strip() or default
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return Decimal(default)


def _render_tabla(request):
    return render(request, 'facturacion/partials/recepcion_items_tabla.html',
                  {'items': request.session.get(SESSION_ITEMS, [])})


# ==============================================================================
# CARGA
# ==============================================================================

class RecepcionCargaView(LoginRequiredMixin, View):
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')
        if not empresa_id or not sucursal_id:
            messages.warning(request, "Seleccione empresa y sucursal primero.")
            return redirect('seleccion_empresa')

        request.session[SESSION_ITEMS] = []
        request.session[SESSION_OCS] = []

        sucursales = Sucursal.objects.filter(empresa_id=empresa_id).order_by('nombre')
        return render(request, 'facturacion/recepcion_carga.html', {
            'fecha_hoy': timezone.localdate(),
            'sucursales': sucursales,
            'sucursal_id': int(sucursal_id),
        })

    def post(self, request):
        empresa_id = request.session.get('empresa_id')
        if not empresa_id:
            return redirect('seleccion_empresa')

        proveedor_id = (request.POST.get('proveedor') or '').strip()
        sucursal_id = (request.POST.get('sucursal') or '').strip()
        items = request.session.get(SESSION_ITEMS, [])

        if not proveedor_id:
            messages.error(request, "Debe seleccionar un proveedor.")
            return redirect('recepcion_carga')
        if not sucursal_id:
            messages.error(request, "Debe seleccionar la sucursal de destino.")
            return redirect('recepcion_carga')
        if not items:
            messages.error(request, "No hay productos para recepcionar.")
            return redirect('recepcion_carga')

        proveedor = get_object_or_404(ClienteProveedor, pk=proveedor_id, empresa_id=empresa_id)
        sucursal = get_object_or_404(Sucursal, pk=sucursal_id, empresa_id=empresa_id)
        fecha = (request.POST.get('fecha') or '').strip() or timezone.localdate()
        remito_prov = (request.POST.get('remito_proveedor') or '').strip()
        observaciones = (request.POST.get('observaciones') or '').strip()

        ocs_afectadas = set()

        with transaction.atomic():
            recepcion = Recepcion(
                empresa_id=empresa_id, sucursal=sucursal, punto=sucursal.punto,
                fecha=fecha, origen=Recepcion.PROVEEDOR_REMITO, proveedor=proveedor,
                remito_proveedor=remito_prov, observaciones=observaciones,
                estado=Recepcion.ACTIVA, usuario=request.user,
                creado_por=request.user, modificado_por=request.user,
            )
            recepcion.numero = siguiente_numero(empresa_id, sucursal.punto, ContadorDocumento.INFORME_RECEPCION)
            recepcion.save()

            for it in items:
                recibida = Decimal(str(it.get('cantidad_recibida') or 0))
                if recibida <= 0:
                    continue
                ritem = RecepcionItem.objects.create(
                    recepcion=recepcion, producto_id=it['producto_id'],
                    cantidad_recibida=recibida,
                )
                # Imputación FIFO contra las líneas de OC que componen este código
                restante = recibida
                for fuente in it.get('fuentes', []):
                    if restante <= 0:
                        break
                    try:
                        oc_item = OrdenCompraItem.objects.select_for_update().get(pk=fuente['oc_item_id'])
                    except OrdenCompraItem.DoesNotExist:
                        continue
                    pendiente = oc_item.pendiente_recepcion
                    if pendiente <= 0:
                        continue
                    imputar = min(restante, pendiente)
                    RecepcionImputacion.objects.create(
                        recepcion_item=ritem, orden_item=oc_item, cantidad=imputar,
                    )
                    oc_item.cantidad_recibida = oc_item.cantidad_recibida + imputar
                    oc_item.save(update_fields=['cantidad_recibida'])
                    ocs_afectadas.add(oc_item.orden_id)
                    restante -= imputar

            # Recalcular estados de las OC afectadas
            for oc_id in ocs_afectadas:
                OrdenCompra.objects.get(pk=oc_id).recalcular_estados()

        request.session[SESSION_ITEMS] = []
        request.session[SESSION_OCS] = []
        messages.success(request, f"Informe de Recepción {recepcion.punto:04d}-{recepcion.numero:08d} generado. Stock actualizado.")
        return redirect('recepcion_listado')


# ==============================================================================
# VINCULAR OC
# ==============================================================================

class RecepcionVincularOcModalView(LoginRequiredMixin, View):
    """Modal con las OC del proveedor pendientes de recepción (checkboxes)."""
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        proveedor_id = (request.GET.get('proveedor') or '').strip()
        if not proveedor_id:
            return HttpResponse("<div class='p-4 text-red-500 font-bold'>Seleccione un proveedor primero.</div>", status=400)

        ordenes = (OrdenCompra.objects
                   .filter(empresa_id=empresa_id, proveedor_id=proveedor_id,
                           estado=OrdenCompra.CONFIRMADA)
                   .exclude(estado_recepcion=OrdenCompra.COMPLETA)
                   .order_by('fecha', 'numero'))
        seleccionadas = set(request.session.get(SESSION_OCS, []))
        return render(request, 'facturacion/modals/recepcion_vincular_oc.html', {
            'ordenes': ordenes, 'seleccionadas': seleccionadas,
        })


class RecepcionVincularOcView(LoginRequiredMixin, View):
    """Construye los ítems de la recepción TOTALIZADOS POR CÓDIGO a partir de las OC
    seleccionadas (solo líneas con pendiente de recepción). Guarda en sesión."""
    def post(self, request):
        empresa_id = request.session.get('empresa_id')
        oc_ids = request.POST.getlist('oc_ids')
        oc_ids = [int(x) for x in oc_ids if x.isdigit()]

        ocs = (OrdenCompra.objects
               .filter(empresa_id=empresa_id, oc_id__in=oc_ids)
               .prefetch_related('items__producto'))

        # Ítems ya cargados manualmente (sin fuentes) se conservan
        prev = request.session.get(SESSION_ITEMS, [])
        manuales = [it for it in prev if not it.get('fuentes')]

        # Totalizar por producto las líneas pendientes, en orden FIFO (fecha, numero, id)
        por_producto = {}
        oc_lines = []
        for oc in ocs.order_by('fecha', 'numero'):
            for li in oc.items.all():
                if li.pendiente_recepcion > 0:
                    oc_lines.append(li)
        for li in oc_lines:
            pid = li.producto_id
            if pid not in por_producto:
                por_producto[pid] = {
                    'producto_id': pid,
                    'codigo': li.producto.cod_prov or pid,
                    'detalle': li.producto.detalle,
                    'cantidad_pedida': Decimal('0'),
                    'fuentes': [],
                }
            entry = por_producto[pid]
            entry['cantidad_pedida'] += li.pendiente_recepcion
            entry['fuentes'].append({'oc_item_id': li.pk, 'pendiente': float(li.pendiente_recepcion)})

        items = []
        idx = 0
        for pid, entry in por_producto.items():
            items.append({
                'index': idx,
                'producto_id': entry['producto_id'],
                'codigo': entry['codigo'],
                'detalle': entry['detalle'],
                'cantidad_pedida': float(entry['cantidad_pedida']),
                'cantidad_recibida': float(entry['cantidad_pedida']),  # default = pendiente
                'pendiente': 0.0,  # recibida = pedida por defecto
                'fuentes': entry['fuentes'],
            })
            idx += 1
        # Reanexar manuales al final, re-indexando
        for it in manuales:
            it['index'] = idx
            items.append(it)
            idx += 1

        request.session[SESSION_ITEMS] = items
        request.session[SESSION_OCS] = oc_ids
        request.session.modified = True

        resp = _render_tabla(request)
        resp['HX-Trigger'] = json.dumps({'cerrarModal': True})
        return resp


# ==============================================================================
# ÍTEMS MANUALES (recepción sin OC / ítems extra)
# ==============================================================================

class RecItemAddView(LoginRequiredMixin, View):
    def get(self, request):
        return _render_tabla(request)

    def post(self, request):
        producto_id = (request.POST.get('producto_id') or '').strip()
        cantidad = _num(request.POST.get('cantidad'), '1')
        if not producto_id:
            return _render_tabla(request)

        items = request.session.get(SESSION_ITEMS) or []
        if any(str(i['producto_id']) == str(producto_id) for i in items):
            return HttpResponse('<div class="p-4 bg-red-100 text-red-700 font-bold">Este producto ya está en la recepción.</div>', status=200)
        try:
            producto = Producto.objects.get(id=producto_id, empresa_id=request.session.get('empresa_id'))
        except (Producto.DoesNotExist, ValueError):
            return HttpResponse(f'<div class="p-4 bg-red-100 text-red-700 font-bold">Producto ID [{producto_id}] inexistente.</div>', status=200)

        items.append({
            'index': len(items),
            'producto_id': producto.id,
            'codigo': producto.cod_prov or producto.id,
            'detalle': producto.detalle,
            'cantidad_pedida': 0,
            'cantidad_recibida': float(cantidad),
            'pendiente': 0.0,
            'fuentes': [],
        })
        request.session[SESSION_ITEMS] = items
        request.session.modified = True
        resp = _render_tabla(request)
        resp['HX-Trigger'] = 'limpiarInputsRec'
        return resp


class RecItemEditView(LoginRequiredMixin, View):
    def post(self, request, index):
        items = request.session.get(SESSION_ITEMS, [])
        if 0 <= index < len(items):
            recibida = float(_num(request.POST.get('cantidad_recibida'),
                                  str(items[index]['cantidad_recibida'])))
            items[index]['cantidad_recibida'] = recibida
            if items[index].get('fuentes'):
                items[index]['pendiente'] = round(items[index]['cantidad_pedida'] - recibida, 2)
            request.session[SESSION_ITEMS] = items
        resp = _render_tabla(request)
        resp['HX-Trigger'] = json.dumps({'actualizarTotalesRec': True})
        return resp


class RecItemRemoveView(LoginRequiredMixin, View):
    def post(self, request, index):
        items = request.session.get(SESSION_ITEMS, [])
        if 0 <= index < len(items):
            items.pop(index)
            for i, it in enumerate(items):
                it['index'] = i
        request.session[SESSION_ITEMS] = items
        resp = _render_tabla(request)
        resp['HX-Trigger'] = json.dumps({'actualizarTotalesRec': True})
        return resp


# ==============================================================================
# LISTADO / IMPRESIÓN
# ==============================================================================

class RecepcionListView(LoginRequiredMixin, View):
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        if not empresa_id:
            return redirect('seleccion_empresa')

        desde = (request.GET.get('desde') or '').strip()
        hasta = (request.GET.get('hasta') or '').strip()
        
        ejercicio_id = request.session.get('ejercicio_id')
        if not desde and not hasta and ejercicio_id:
            ejercicio = Ejercicio.objects.filter(id=ejercicio_id, empresa_id=empresa_id).first()
            if ejercicio:
                desde = ejercicio.inicio.isoformat()
                hasta = min(ejercicio.cierre, timezone.localdate()).isoformat()

        proveedor_id = (request.GET.get('proveedor') or '').strip()

        recepciones = (Recepcion.objects.filter(empresa_id=empresa_id, origen__in=[Recepcion.PROVEEDOR_REMITO, Recepcion.PROVEEDOR_FACTURA])
                       .select_related('proveedor', 'sucursal'))
        if desde:
            recepciones = recepciones.filter(fecha__gte=desde)
        if hasta:
            recepciones = recepciones.filter(fecha__lte=hasta)
        if proveedor_id:
            recepciones = recepciones.filter(proveedor_id=proveedor_id)
        recepciones = recepciones.order_by('-fecha', '-recepcion_id')

        proveedores = (ClienteProveedor.objects
                       .filter(recepciones__empresa_id=empresa_id).distinct()
                       .order_by('razon_social'))
        return render(request, 'facturacion/recepcion_listado.html', {
            'recepciones': recepciones[:500],
            'proveedores': proveedores,
            'desde': desde, 'hasta': hasta, 'proveedor_id': proveedor_id,
        })


def anular_recepcion(rec, user):
    """Anulación lógica de una Recepción (conserva el número): revierte el stock (borra los
    RecepcionItem → post_delete), revierte las imputaciones (cantidad_recibida de OC y/o de
    Remito Interno), reabre pendientes y recalcula estados. Deja la recepción en ANULADA."""
    ocs, ris = set(), set()
    for rimp in RecepcionImputacion.objects.filter(
            recepcion_item__recepcion=rec).select_related('orden_item', 'remito_interno_item'):
        if rimp.orden_item_id:
            oi = rimp.orden_item
            oi.cantidad_recibida = oi.cantidad_recibida - rimp.cantidad
            oi.save(update_fields=['cantidad_recibida'])
            ocs.add(oi.orden_id)
        if rimp.remito_interno_item_id:
            ri = rimp.remito_interno_item
            ri.cantidad_recibida = ri.cantidad_recibida - rimp.cantidad
            ri.save(update_fields=['cantidad_recibida'])
            ris.add(ri.remito_id)
    RecepcionImputacion.objects.filter(recepcion_item__recepcion=rec).delete()
    rec.items.all().delete()  # post_delete de RecepcionItem revierte el stock (ENTRADA)
    rec.estado = Recepcion.ANULADA
    rec.modificado_por = user
    rec.save(update_fields=['estado', 'modificado_por', 'fecha_modificacion'])
    for oc_id in ocs:
        OrdenCompra.objects.get(pk=oc_id).recalcular_estados()
    for ri_id in ris:
        RemitoInterno.objects.get(pk=ri_id).recalcular_estado()


class RecepcionBajaView(LoginRequiredMixin, View):
    """Anulación lógica de una Recepción desde el listado (HTMX)."""
    def post(self, request, recepcion_id):
        empresa_id = request.session.get('empresa_id')
        rec = get_object_or_404(Recepcion, pk=recepcion_id, empresa_id=empresa_id)
        if rec.estado == Recepcion.ANULADA:
            pass
        elif rec.generada_por_factura_id:
            return HttpResponse(
                f'<tr class="bg-red-50"><td colspan="8" class="px-4 py-3 text-red-700 font-bold text-[11px] italic">'
                f'La recepción {rec.punto:04d}-{rec.numero} fue generada por una factura; se revierte dando de baja esa factura.</td></tr>',
                status=200)
        else:
            with transaction.atomic():
                anular_recepcion(rec, request.user)
        return render(request, 'facturacion/partials/recepcion_fila.html', {'r': rec})


class RecepcionImprimirView(LoginRequiredMixin, View):
    def get(self, request, recepcion_id):
        empresa_id = request.session.get('empresa_id')
        rec = get_object_or_404(
            Recepcion.objects.select_related('proveedor', 'sucursal', 'empresa'),
            pk=recepcion_id, empresa_id=empresa_id)
        from facturacion.services.reportes_pdf import render_pdf_response
        items = rec.items.select_related('producto').prefetch_related('imputaciones__orden_item__orden')
        return render_pdf_response(
            'facturacion/pdf/recepcion_pdf.html',
            {'rec': rec, 'items': items},
            f"Recepcion_{rec.punto:04d}-{rec.numero:08d}.pdf",
        )
