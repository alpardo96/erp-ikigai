"""
Circuito interno de stock (Plan 028 — Fase 6): transferencia entre sucursales en 2 pasos.

- Remito Interno: la sucursal ORIGEN emite; el stock SALE del origen (queda en tránsito).
- Informe de Recepción (origen=INTERNO): la sucursal DESTINO recibe; el stock ENTRA al destino.

Ambos documentos prenumerados por el sistema. Sin asiento contable. Baja = anulación lógica.
Reutiliza el modelo Recepcion + su señal de stock (ENTRADA) para la recepción interna.
"""
import json
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.db.models import F, Q

from .models import (
    RemitoInterno, RemitoInternoItem, Recepcion, RecepcionItem, RecepcionImputacion,
)
from empresas.models import Sucursal, Ejercicio
from productos.models import Producto, Subproducto
from core.models import ContadorDocumento
from core.services.numeracion import siguiente_numero

RI_ITEMS = 'ri_items_temp'          # ítems de la carga de Remito Interno
RECI_ITEMS = 'reci_items_temp'      # ítems de la recepción interna
RECI_RIS = 'reci_ri_ids'            # remitos internos vinculados a la recepción


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


# ==============================================================================
# REMITO INTERNO — carga / grilla / listado / anulación / impresión
# ==============================================================================

class RemitoInternoCargaView(LoginRequiredMixin, View):
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')
        if not empresa_id or not sucursal_id:
            messages.warning(request, "Seleccione empresa y sucursal primero.")
            return redirect('seleccion_empresa')
        request.session[RI_ITEMS] = []
        sucursales = Sucursal.objects.filter(empresa_id=empresa_id).order_by('nombre')
        return render(request, 'facturacion/remito_interno_carga.html', {
            'fecha_hoy': timezone.localdate(),
            'sucursales': sucursales,
            'sucursal_id': int(sucursal_id),
            'TIPOS': RemitoInterno.TIPOS,
        })

    def post(self, request):
        empresa_id = request.session.get('empresa_id')
        origen_id = (request.POST.get('sucursal_origen') or '').strip()
        destino_id = (request.POST.get('sucursal_destino') or '').strip()
        items = request.session.get(RI_ITEMS, [])

        if not origen_id or not destino_id:
            messages.error(request, "Debe indicar sucursal de origen y destino.")
            return redirect('remito_interno_carga')
        if origen_id == destino_id:
            messages.error(request, "El origen y el destino no pueden ser la misma sucursal.")
            return redirect('remito_interno_carga')
        if not items:
            messages.error(request, "Debe cargar al menos un producto.")
            return redirect('remito_interno_carga')

        origen = get_object_or_404(Sucursal, pk=origen_id, empresa_id=empresa_id)
        destino = get_object_or_404(Sucursal, pk=destino_id, empresa_id=empresa_id)
        fecha = (request.POST.get('fecha') or '').strip() or timezone.localdate()
        tipo = (request.POST.get('tipo') or RemitoInterno.ENVIO).strip()
        observaciones = (request.POST.get('observaciones') or '').strip()

        with transaction.atomic():
            ri = RemitoInterno(
                empresa_id=empresa_id, sucursal_origen=origen, sucursal_destino=destino,
                punto=origen.punto, fecha=fecha, tipo=tipo, estado=RemitoInterno.EMITIDO,
                observaciones=observaciones, usuario=request.user,
                creado_por=request.user, modificado_por=request.user,
            )
            ri.numero = siguiente_numero(empresa_id, origen.punto, ContadorDocumento.REMITO_INTERNO)
            ri.save()
            for it in items:
                cant = Decimal(str(it.get('cantidad') or 0))
                if cant <= 0:
                    continue
                # Trazabilidad Plan 052: se guardan subproducto_id, serie y cuim si corresponden
                RemitoInternoItem.objects.create(
                    remito=ri,
                    producto_id=it['producto_id'],
                    subproducto_id=it.get('subproducto_id'),
                    serie=it.get('serie'),
                    cuim=it.get('cuim'),
                    cantidad_enviada=cant
                )

        request.session[RI_ITEMS] = []
        messages.success(request, f"Remito Interno {ri.punto:04d}-{ri.numero:08d} emitido. Stock en tránsito.")
        return redirect('remito_interno_listado')


def _render_ri_tabla(request):
    return render(request, 'facturacion/partials/ri_items_tabla.html',
                  {'items': request.session.get(RI_ITEMS, [])})


class RiItemAddView(LoginRequiredMixin, View):
    def get(self, request):
        return _render_ri_tabla(request)

    def post(self, request):
        empresa_id = request.session.get('empresa_id')
        producto_id = (request.POST.get('producto_id') or '').strip()
        cantidad = _num(request.POST.get('cantidad'), '1')
        serie = (request.POST.get('serie') or '').strip()
        sucursal_origen_id = (request.POST.get('sucursal_origen') or '').strip() or str(request.session.get('sucursal_id', ''))

        # Trazabilidad Plan 053: Si producto_id está vacío pero ingresó la serie, lo resolvemos automáticamente
        if not producto_id and serie:
            subp_auto = Subproducto.objects.filter(
                serie__iexact=serie, empresa_id=empresa_id
            ).exclude(situacion='VENDIDA').first()
            if subp_auto:
                producto_id = str(subp_auto.producto_id)

        if not producto_id:
            return _render_ri_tabla(request)
        items = request.session.get(RI_ITEMS) or []

        # Búsqueda con prioridad absoluta para el ID primario (productos_producto.id)
        producto = None
        if producto_id.isdigit():
            producto = Producto.objects.filter(id=int(producto_id), empresa_id=empresa_id).first()
        if not producto:
            producto = Producto.objects.filter(cod_prov__iexact=producto_id, empresa_id=empresa_id).first()

        if not producto:
            return HttpResponse(f'<div class="p-4 bg-red-100 text-red-700 font-bold">Producto ID [{producto_id}] inexistente.</div>', status=200)

        subproducto_obj = None
        # Validación de Trazabilidad (Plan 052): si el producto es subproducto (subprod = True / 1)
        if producto.subprod:
            if not serie:
                return HttpResponse('<div class="p-4 bg-red-100 text-red-700 font-bold">Este producto requiere ingresar el Número de Serie.</div>', status=200)

            # Buscar subproducto por serie activo en la empresa (excluyendo situacion='VENDIDA')
            subprod_query = Subproducto.objects.filter(
                producto=producto, serie__iexact=serie, empresa_id=empresa_id
            ).exclude(situacion='VENDIDA').select_related('sucursal')
            subproducto_obj = subprod_query.first()

            if not subproducto_obj:
                if Subproducto.objects.filter(producto=producto, serie__iexact=serie, empresa_id=empresa_id, situacion='VENDIDA').exists():
                    return HttpResponse(f'<div class="p-4 bg-red-100 text-red-700 font-bold">El N° de Serie "{serie}" figura como VENDIDA.</div>', status=200)
                return HttpResponse(f'<div class="p-4 bg-red-100 text-red-700 font-bold">El N° de Serie "{serie}" no existe para este producto.</div>', status=200)

            if str(subproducto_obj.sucursal_id) != str(sucursal_origen_id):
                suc_nombre = subproducto_obj.sucursal.nombre if subproducto_obj.sucursal else "otra sucursal"
                return HttpResponse(f'<div class="p-4 bg-red-100 text-red-700 font-bold">El N° de Serie "{serie}" pertenece a {suc_nombre}, no a la sucursal de origen elegida.</div>', status=200)

            if any(i.get('subproducto_id') == subproducto_obj.subpro for i in items):
                return HttpResponse(f'<div class="p-4 bg-red-100 text-red-700 font-bold">El N° de Serie "{serie}" ya fue agregado a este remito.</div>', status=200)

            cantidad = Decimal('1.00')

        else:
            # Para productos no trazables, bloqueamos duplicados generales
            if any(str(i['producto_id']) == str(producto_id) and not i.get('subproducto_id') for i in items):
                return HttpResponse('<div class="p-4 bg-red-100 text-red-700 font-bold">Este producto ya está en el remito.</div>', status=200)

        items.append({
            'index': len(items),
            'producto_id': producto.id,
            'subproducto_id': subproducto_obj.subpro if subproducto_obj else None,
            'serie': subproducto_obj.serie if subproducto_obj else '',
            'cuim': subproducto_obj.cuim or '' if subproducto_obj else '',
            'codigo': producto.id,
            'detalle': producto.detalle,
            'cantidad': float(cantidad),
        })
        request.session[RI_ITEMS] = items
        request.session.modified = True
        resp = _render_ri_tabla(request)
        resp['HX-Trigger'] = 'limpiarInputsRI'
        return resp


class RiItemEditView(LoginRequiredMixin, View):
    def post(self, request, index):
        items = request.session.get(RI_ITEMS, [])
        if 0 <= index < len(items):
            items[index]['cantidad'] = float(_num(request.POST.get('cantidad'), str(items[index]['cantidad'])))
            request.session[RI_ITEMS] = items
        return _render_ri_tabla(request)


class RiItemRemoveView(LoginRequiredMixin, View):
    def post(self, request, index):
        items = request.session.get(RI_ITEMS, [])
        if 0 <= index < len(items):
            items.pop(index)
            for i, it in enumerate(items):
                it['index'] = i
        request.session[RI_ITEMS] = items
        return _render_ri_tabla(request)


@login_required
def ri_buscar_subproducto_por_serie(request):
    """
    Busca un Subproducto por N° de Serie para la carga de Remitos Internos (Plan 053).
    Verifica:
    1. Coincidencia por serie en la empresa activa con situacion != 'VENDIDA' (soporta armas usadas/recompradas).
    2. sucursal_id == sucursal_origen (o sucursal activa).
    3. Carga de productos_subproducto.cuim y productos_producto.detalle.
    """
    serie = (request.GET.get('serie') or request.POST.get('serie') or '').strip()
    sucursal_origen_id = (request.GET.get('sucursal_origen') or request.POST.get('sucursal_origen') or '').strip() or str(request.session.get('sucursal_id', ''))
    empresa_id = request.session.get('empresa_id')

    if not serie:
        return HttpResponse("", status=200)

    # 1. Buscar en Subproducto excluyendo situacion='VENDIDA'
    subp = Subproducto.objects.filter(
        serie__iexact=serie,
        empresa_id=empresa_id
    ).exclude(situacion='VENDIDA').select_related('producto', 'sucursal').first()

    if not subp:
        # Si existe pero figura como VENDIDA, alertar específicamente
        if Subproducto.objects.filter(serie__iexact=serie, empresa_id=empresa_id, situacion='VENDIDA').exists():
            return HttpResponse('<div class="p-2 bg-red-100 text-red-700 font-bold text-xs rounded">La serie ingresada ya figura como VENDIDA.</div>', status=200)
        return HttpResponse('<div class="p-2 bg-red-100 text-red-700 font-bold text-xs rounded">N° de Serie no encontrado.</div>', status=200)

    if subp.situacion == 'VENDIDA':
        return HttpResponse('<div class="p-2 bg-red-100 text-red-700 font-bold text-xs rounded">La serie ingresada ya figura como VENDIDA.</div>', status=200)

    # 2. Verificar sucursal activa / origen
    if sucursal_origen_id and str(subp.sucursal_id) != str(sucursal_origen_id):
        suc_nombre = subp.sucursal.nombre if subp.sucursal else "otra sucursal"
        return HttpResponse(f'<div class="p-2 bg-amber-100 text-amber-800 font-bold text-xs rounded">La serie pertenece a {suc_nombre}, no a la sucursal de origen elegida.</div>', status=200)

    # 3. Éxito: autocompletar producto_id, detalle, cuim y serie
    data = {
        'id': subp.producto_id,
        'detalle': subp.producto.detalle.upper(),
        'serie': subp.serie,
        'cuim': subp.cuim or '',
        'subproducto_id': subp.subpro,
    }

    response = HttpResponse(f'<div class="p-2 bg-emerald-100 text-emerald-800 font-bold text-xs rounded">Serie autodetectada: {subp.serie} (CUIM: {subp.cuim or "s/c"})</div>', status=200)
    response['HX-Trigger'] = json.dumps({'serieEncontradaRI': data})
    return response


@login_required
def ri_buscar_producto_por_id(request):
    """
    Búsqueda directa instantánea por ID primario (productos_producto.id) o Cód. Proveedor.
    Responde con la carga útil 'productoEncontrado' para autocompletar la descripción sin demoras.
    """
    q = (request.GET.get('q') or '').strip()
    empresa_id = request.session.get('empresa_id')
    if not q:
        return HttpResponse("", status=200)

    p = None
    if q.isdigit():
        p = Producto.objects.filter(id=int(q), empresa_id=empresa_id).first()
    if not p:
        p = Producto.objects.filter(cod_prov__iexact=q, empresa_id=empresa_id).first()

    if not p:
        return HttpResponse('<div class="p-2 bg-red-100 text-red-700 font-bold text-xs rounded">Producto no encontrado.</div>', status=200)

    data = {
        'id': p.id,
        'detalle': p.detalle.upper(),
        'subprod': p.subprod,
        'cod_prov': p.cod_prov or str(p.id),
    }
    response = HttpResponse(f'<div class="p-2 bg-blue-50 text-blue-800 font-bold text-xs rounded">Producto: {p.detalle} (ID: #{p.id})</div>', status=200)
    response['HX-Trigger'] = json.dumps({'productoEncontrado': data})
    return response


class RemitoInternoListView(LoginRequiredMixin, View):
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
        estado = (request.GET.get('estado') or '').strip()
        remitos = (RemitoInterno.objects.filter(empresa_id=empresa_id)
                   .select_related('sucursal_origen', 'sucursal_destino'))
        if desde:
            remitos = remitos.filter(fecha__gte=desde)
        if hasta:
            remitos = remitos.filter(fecha__lte=hasta)
        if estado != '':
            remitos = remitos.filter(estado=estado)
        remitos = remitos.order_by('-fecha', '-ri_id')
        return render(request, 'facturacion/remito_interno_listado.html', {
            'remitos': remitos[:500], 'desde': desde, 'hasta': hasta, 'estado': estado,
            'ESTADOS': RemitoInterno.ESTADOS,
        })


class RemitoInternoBajaView(LoginRequiredMixin, View):
    """Anulación lógica (conserva el número). Bloquea si ya tiene recepciones."""
    def post(self, request, ri_id):
        empresa_id = request.session.get('empresa_id')
        ri = get_object_or_404(RemitoInterno, pk=ri_id, empresa_id=empresa_id)
        if ri.estado == RemitoInterno.ANULADO:
            pass
        elif any(li.cantidad_recibida > 0 for li in ri.items.all()):
            return HttpResponse(
                f'<tr class="bg-red-50"><td colspan="7" class="px-4 py-3 text-red-700 font-bold text-[11px] italic">'
                f'No se puede anular el Remito Interno {ri.punto:04d}-{ri.numero}: ya tiene recepciones.</td></tr>',
                status=200)
        else:
            # Revertir el stock que salió del origen (borrar ítems dispara la señal post_delete).
            with transaction.atomic():
                ri.items.all().delete()
                ri.estado = RemitoInterno.ANULADO
                ri.modificado_por = request.user
                ri.save(update_fields=['estado', 'modificado_por', 'fecha_modificacion'])
        return render(request, 'facturacion/partials/ri_fila.html', {'ri': ri})


class RemitoInternoImprimirView(LoginRequiredMixin, View):
    def get(self, request, ri_id):
        empresa_id = request.session.get('empresa_id')
        ri = get_object_or_404(
            RemitoInterno.objects.select_related('sucursal_origen', 'sucursal_destino', 'empresa'),
            pk=ri_id, empresa_id=empresa_id)
        from facturacion.services.reportes_pdf import render_pdf_response
        return render_pdf_response(
            'facturacion/pdf/remito_interno_pdf.html',
            {'ri': ri, 'items': ri.items.select_related('producto').all()},
            f"RemitoInterno_{ri.punto:04d}-{ri.numero:08d}.pdf",
        )


# ==============================================================================
# RECEPCIÓN INTERNA — Informe de Recepción origen=INTERNO (vincula Remito Interno)
# ==============================================================================

def _render_reci_tabla(request):
    return render(request, 'facturacion/partials/recepcion_interna_items_tabla.html',
                  {'items': request.session.get(RECI_ITEMS, [])})


class RecepcionInternaListView(LoginRequiredMixin, View):
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
                hasta = ejercicio.cierre.isoformat()

        filtros = Q(empresa_id=empresa_id, origen=Recepcion.INTERNO)
        if desde:
            filtros &= Q(fecha__gte=desde)
        if hasta:
            filtros &= Q(fecha__lte=hasta)

        recepciones = Recepcion.objects.filter(filtros).select_related('sucursal', 'usuario').order_by('-fecha', '-numero')
        return render(request, 'facturacion/recepcion_interna_listado.html', {
            'recepciones': recepciones, 'desde': desde, 'hasta': hasta,
        })


class RecepcionInternaCargaView(LoginRequiredMixin, View):
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')
        if not empresa_id or not sucursal_id:
            messages.warning(request, "Seleccione empresa y sucursal primero.")
            return redirect('seleccion_empresa')
        request.session[RECI_ITEMS] = []
        request.session[RECI_RIS] = []
        sucursal_activa = get_object_or_404(Sucursal, pk=sucursal_id, empresa_id=empresa_id)
        return render(request, 'facturacion/recepcion_interna_carga.html', {
            'fecha_hoy': timezone.localdate(),
            'sucursal_activa': sucursal_activa,
            'sucursal_id': int(sucursal_id),
        })

    def post(self, request):
        empresa_id = request.session.get('empresa_id')
        # Seguridad: La sucursal de destino es FIJA y corresponde obligatoriamente a la sucursal activa del usuario logueado
        destino_id = request.session.get('sucursal_id')
        items = request.session.get(RECI_ITEMS, [])
        if not destino_id:
            messages.error(request, "Debe seleccionar sucursal en su sesión.")
            return redirect('recepcion_interna_carga')
        if not items:
            messages.error(request, "No hay productos para recepcionar.")
            return redirect('recepcion_interna_carga')

        destino = get_object_or_404(Sucursal, pk=destino_id, empresa_id=empresa_id)
        fecha = (request.POST.get('fecha') or '').strip() or timezone.localdate()
        observaciones = (request.POST.get('observaciones') or '').strip()
        remitos_afectados = set()

        with transaction.atomic():
            recepcion = Recepcion(
                empresa_id=empresa_id, sucursal=destino, punto=destino.punto, fecha=fecha,
                origen=Recepcion.INTERNO, proveedor=None, observaciones=observaciones,
                estado=Recepcion.ACTIVA, usuario=request.user,
                creado_por=request.user, modificado_por=request.user,
            )
            recepcion.numero = siguiente_numero(empresa_id, destino.punto, ContadorDocumento.INFORME_RECEPCION)
            recepcion.save()

            for it in items:
                recibida = Decimal(str(it.get('cantidad_recibida') or 0))
                if recibida <= 0:
                    continue
                ritem = RecepcionItem.objects.create(
                    recepcion=recepcion, producto_id=it['producto_id'], cantidad_recibida=recibida)
                restante = recibida
                for f in it.get('fuentes', []):
                    if restante <= 0:
                        break
                    try:
                        ri_item = RemitoInternoItem.objects.select_for_update().get(pk=f['ri_item_id'])
                    except RemitoInternoItem.DoesNotExist:
                        continue
                    pend = ri_item.pendiente
                    if pend <= 0:
                        continue
                    imp = min(restante, pend)
                    RecepcionImputacion.objects.create(
                        recepcion_item=ritem, remito_interno_item=ri_item, cantidad=imp)
                    ri_item.cantidad_recibida = ri_item.cantidad_recibida + imp
                    ri_item.save(update_fields=['cantidad_recibida'])

                    # Trazabilidad Plan 052: Si el ítem recepcionado está vinculado a un Subproducto, actualizamos su sucursal a destino
                    if ri_item.subproducto and imp > 0:
                        subp = ri_item.subproducto
                        subp.sucursal = destino
                        subp.save(update_fields=['sucursal'])

                    remitos_afectados.add(ri_item.remito_id)
                    restante -= imp

            for rid in remitos_afectados:
                RemitoInterno.objects.get(pk=rid).recalcular_estado()

        request.session[RECI_ITEMS] = []
        request.session[RECI_RIS] = []
        messages.success(request, f"Informe de Recepción {recepcion.punto:04d}-{recepcion.numero:08d} (interno) generado. Stock actualizado.")
        return redirect('recepcion_interna_imprimir', rec_id=recepcion.pk)


class RecepcionInternaVincularModalView(LoginRequiredMixin, View):
    """Remitos internos dirigidos OBLIGATORIAMENTE a la sucursal activa logueada, pendientes de recepción."""
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        destino_id = request.session.get('sucursal_id')
        if not destino_id:
            return HttpResponse("<div class='p-4 text-red-500 font-bold'>Seleccione la sucursal en su sesión.</div>", status=400)
        remitos = (RemitoInterno.objects
                   .filter(empresa_id=empresa_id, sucursal_destino_id=destino_id)
                   .exclude(estado__in=[RemitoInterno.RECEPCIONADO, RemitoInterno.ANULADO])
                   .select_related('sucursal_origen').order_by('fecha', 'numero'))
        seleccionados = set(request.session.get(RECI_RIS, []))
        return render(request, 'facturacion/modals/recepcion_interna_vincular.html', {
            'remitos': remitos, 'seleccionados': seleccionados,
        })


class RecepcionInternaVincularView(LoginRequiredMixin, View):
    def get(self, request):
        # Carga inicial de la grilla (hx-trigger="load")
        return _render_reci_tabla(request)

    def post(self, request):
        empresa_id = request.session.get('empresa_id')
        destino_id = request.session.get('sucursal_id')
        ri_ids = [int(x) for x in request.POST.getlist('ri_ids') if x.isdigit()]
        remitos = (RemitoInterno.objects
                   .filter(empresa_id=empresa_id, sucursal_destino_id=destino_id, ri_id__in=ri_ids)
                   .prefetch_related('items__producto', 'items__subproducto').order_by('fecha', 'numero'))
        por_prod = {}
        for ri in remitos:
            for li in ri.items.all():
                if li.pendiente <= 0:
                    continue
                # Trazabilidad Plan 052: la clave agrupa por producto y subproducto para mantener la individualidad de cada serie
                key = (li.producto_id, li.subproducto_id)
                if key not in por_prod:
                    por_prod[key] = {
                        'producto': li.producto,
                        'subproducto_id': li.subproducto_id,
                        'serie': li.serie or '',
                        'cuim': li.cuim or '',
                        'pend': Decimal('0'),
                        'fuentes': []
                    }
                e = por_prod[key]
                e['pend'] += li.pendiente
                e['fuentes'].append({'ri_item_id': li.pk, 'pendiente': float(li.pendiente)})
        items = []
        for idx, e in enumerate(por_prod.values()):
            prod = e['producto']
            items.append({
                'index': idx,
                'producto_id': prod.id,
                'subproducto_id': e['subproducto_id'],
                'serie': e['serie'],
                'cuim': e['cuim'],
                'codigo': prod.id,
                'detalle': prod.detalle,
                'cantidad_enviada': float(e['pend']),
                'cantidad_recibida': float(e['pend']),
                'pendiente': 0.0,
                'fuentes': e['fuentes'],
            })
        request.session[RECI_ITEMS] = items
        request.session[RECI_RIS] = ri_ids
        request.session.modified = True
        resp = _render_reci_tabla(request)
        resp['HX-Trigger'] = json.dumps({'cerrarModal': True})
        return resp


class ReciItemEditView(LoginRequiredMixin, View):
    def post(self, request, index):
        items = request.session.get(RECI_ITEMS, [])
        if 0 <= index < len(items):
            recibida = float(_num(request.POST.get('cantidad_recibida'), str(items[index]['cantidad_recibida'])))
            items[index]['cantidad_recibida'] = recibida
            items[index]['pendiente'] = round(items[index]['cantidad_enviada'] - recibida, 2)
            request.session[RECI_ITEMS] = items
        return _render_reci_tabla(request)


class ReciItemRemoveView(LoginRequiredMixin, View):
    def post(self, request, index):
        items = request.session.get(RECI_ITEMS, [])
        if 0 <= index < len(items):
            items.pop(index)
            for i, it in enumerate(items):
                it['index'] = i
        request.session[RECI_ITEMS] = items
        return _render_reci_tabla(request)


# ==============================================================================
# STOCK EN TRÁNSITO
# ==============================================================================

class StockTransitoView(LoginRequiredMixin, View):
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        if not empresa_id:
            return redirect('seleccion_empresa')
        # Líneas de remitos internos no anulados con pendiente (enviada > recibida).
        filas = (RemitoInternoItem.objects
                 .filter(remito__empresa_id=empresa_id)
                 .exclude(remito__estado=RemitoInterno.ANULADO)
                 .filter(cantidad_enviada__gt=F('cantidad_recibida'))
                 .select_related('producto', 'remito__sucursal_origen', 'remito__sucursal_destino')
                 .order_by('remito__fecha'))
        return render(request, 'facturacion/stock_transito.html', {'filas': filas})


class RecepcionInternaImprimirView(LoginRequiredMixin, View):
    """Genera el PDF del Informe de Recepción Interna con firmas y comprobantes vinculados."""
    def get(self, request, rec_id):
        empresa_id = request.session.get('empresa_id')
        rec = get_object_or_404(
            Recepcion.objects.select_related('sucursal', 'empresa', 'usuario'),
            pk=rec_id, empresa_id=empresa_id, origen=Recepcion.INTERNO
        )
        items = rec.items.select_related('producto').all()
        # Obtener remitos internos imputados
        imputaciones = RecepcionImputacion.objects.filter(recepcion_item__recepcion=rec).select_related(
            'remito_interno_item__remito__sucursal_origen', 'remito_interno_item__subproducto'
        )
        remitos_dict = {}
        for imp in imputaciones:
            ri = imp.remito_interno_item.remito
            if ri.pk not in remitos_dict:
                remitos_dict[ri.pk] = ri

        from facturacion.services.reportes_pdf import render_pdf_response
        return render_pdf_response(
            'facturacion/pdf/recepcion_interna_pdf.html',
            {
                'rec': rec,
                'items': items,
                'imputaciones': imputaciones,
                'remitos': list(remitos_dict.values()),
            },
            f"InformeRecepcionInterna_{rec.punto:04d}-{rec.numero:08d}.pdf",
        )
