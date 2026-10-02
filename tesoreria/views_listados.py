"""Listados de Órdenes de Pago y Recibos: consulta, anulación y reimpresión (Plan 035 §6).

Además de las columnas habituales, el listado muestra el MONTO APLICADO y el PENDIENTE DE
APLICAR de cada comprobante: una orden puede emitirse sin imputar (anticipo) y aplicarse
después contra facturas que llegan más tarde. Ese pendiente es el insumo del formulario de
aplicación diferida.

La reimpresión saca el comprobante con todo lo vinculado: comprobantes aplicados, medios de
pago desglosados y los certificados de retención practicados.
"""
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from facturacion.models import ClienteProveedor
from tesoreria.models import OrdenPago, Recibo, ValorTerceros



def _rango_fechas(request):
    """Rango del filtro para listados de Tesorería (Recibos y Órdenes de Pago).
    Por defecto se establece la fecha del día de hoy tanto para 'desde' como para 'hasta'
    para evitar consultas masivas históricas en la apertura inicial (Plan 061).
    """
    hoy = timezone.localdate()
    desde = request.GET.get('desde') or hoy.isoformat()
    hasta = request.GET.get('hasta') or hoy.isoformat()
    return desde, hasta


def _anotar_aplicado(queryset, relacion):
    """Agrega `aplicado` (Σ de las imputaciones) en una sola consulta.

    El pendiente se calcula después en Python como `total - aplicado`, para no arrastrar la
    resta a la base y que quede legible en el template.
    """
    return queryset.annotate(
        aplicado=Coalesce(
            Sum(f'{relacion}__importe_pesos'),
            Decimal('0'),
            output_field=OrdenPago._meta.get_field('total'),
        )
    )


# ---------------------------------------------------------------- Órdenes de Pago

@login_required
def ordenes_pago_listado(request):
    empresa_id = request.session.get('empresa_id')
    desde, hasta = _rango_fechas(request)
    proveedor_id = request.GET.get('proveedor', '')
    proveedor_display = ''
    if proveedor_id:
        try:
            p_obj = ClienteProveedor.objects.get(pk=proveedor_id, empresa_id=empresa_id)
            proveedor_display = p_obj.razon_social
        except ClienteProveedor.DoesNotExist:
            proveedor_id = ''

    return render(request, 'tesoreria/ordenpago_listado.html', {
        'desde': desde,
        'hasta': hasta,
        'proveedor_id': proveedor_id,
        'proveedor_display': proveedor_display,
        'condic': request.GET.get('condic', ''),
        'proveedores': ClienteProveedor.objects.filter(
            empresa_id=empresa_id).order_by('razon_social'),
    })


@login_required
def ordenes_pago_grilla(request):
    """Filas del listado. Se sirve por HTMX para refrescar sin recargar la pantalla."""
    empresa_id = request.session.get('empresa_id')
    desde, hasta = _rango_fechas(request)

    ordenes = OrdenPago.objects.filter(
        empresa_id=empresa_id, fecha__gte=desde, fecha__lte=hasta
    ).select_related('proveedor', 'sucursal')

    if request.GET.get('proveedor'):
        ordenes = ordenes.filter(proveedor_id=request.GET['proveedor'])
    if request.GET.get('condic'):
        ordenes = ordenes.filter(condic=request.GET['condic'])
    if request.GET.get('q'):
        q = request.GET['q']
        ordenes = ordenes.filter(
            Q(proveedor__razon_social__icontains=q) | Q(observaciones__icontains=q))

    ordenes = _anotar_aplicado(ordenes, 'aplicaciones').order_by('-fecha', '-numero')

    filas = []
    for op in ordenes:
        aplicado = op.aplicado or Decimal('0')
        filas.append({
            'op': op,
            'aplicado': aplicado,
            # Una OP anulada no tiene nada pendiente de aplicar.
            'pendiente': (Decimal(str(op.total)) - aplicado) if not op.anulado else Decimal('0'),
        })

    return render(request, 'tesoreria/partials/ordenpago_grilla.html', {
        'filas': filas,
        'total_general': sum((Decimal(str(f['op'].total)) for f in filas if not f['op'].anulado), Decimal('0')),
        'total_pendiente': sum((f['pendiente'] for f in filas), Decimal('0')),
    })



@login_required
def orden_pago_detalle(request, pk):
    """Vista de detalle con todo lo vinculado. Sirve para revisar antes de reimprimir."""
    empresa_id = request.session.get('empresa_id')
    return render(request, 'tesoreria/modals/ordenpago_detalle.html',
                  _contexto_comprobante_op(pk, empresa_id))


@login_required
def orden_pago_pdf(request, pk):
    """Reimpresión del comprobante con todo lo vinculado."""
    from contable.services.reportes_pdf import render_pdf_response

    empresa_id = request.session.get('empresa_id')
    contexto = _contexto_comprobante_op(pk, empresa_id)
    op = contexto['op']
    return render_pdf_response(
        'tesoreria/pdf/orden_pago_pdf.html', contexto,
        f"OP_{op.punto:04d}-{op.numero:08d}.pdf")


def _contexto_comprobante_op(pk, empresa_id):
    """Arma la OP completa: aplicaciones, medios de pago desglosados y retenciones."""
    from contable.models import RetencionPracticada
    from tesoreria.models import MovimientoCajaDetalle, TransaccionBancaria, ValorTerceros

    op = get_object_or_404(
        OrdenPago.objects.select_related('proveedor', 'empresa', 'sucursal'),
        pk=pk, empresa_id=empresa_id)

    detalles = MovimientoCajaDetalle.objects.filter(
        movimiento_caja__orden_pago=op
    ).select_related('medio_pago').prefetch_related(
        'transacciones_bancarias__cuenta_bancaria')

    from core.utils.numeros_a_letras import numero_a_letras
    return {
        'op': op,
        'aplicaciones': op.aplicaciones.select_related('compra__tipo').all(),
        'imputaciones': op.imputaciones_simples.select_related('cuenta_contable').all(),
        'detalles': detalles,
        'transacciones': TransaccionBancaria.objects.filter(
            movimiento_detalle__movimiento_caja__orden_pago=op
        ).select_related('cuenta_bancaria'),
        'valores_entregados': ValorTerceros.objects.filter(orden_pago=op).select_related('banco'),
        'retenciones': RetencionPracticada.objects.filter(orden_pago=op),
        'total_letras': numero_a_letras(op.total),
        'fecha_impresion': timezone.localtime(),
    }


# ---------------------------------------------------------------------- Recibos

@login_required
def recibos_listado(request):
    empresa_id = request.session.get('empresa_id')
    desde, hasta = _rango_fechas(request)
    cliente_id = request.GET.get('cliente', '')
    cliente_display = ''
    if cliente_id:
        try:
            c_obj = ClienteProveedor.objects.get(pk=cliente_id, empresa_id=empresa_id)
            cliente_display = c_obj.razon_social
        except ClienteProveedor.DoesNotExist:
            cliente_id = ''

    return render(request, 'tesoreria/recibo_listado.html', {
        'desde': desde,
        'hasta': hasta,
        'cliente_id': cliente_id,
        'cliente_display': cliente_display,
        'condic': request.GET.get('condic', ''),
        'clientes': ClienteProveedor.objects.filter(
            empresa_id=empresa_id).order_by('razon_social'),
    })


@login_required
def recibos_grilla(request):
    empresa_id = request.session.get('empresa_id')
    desde, hasta = _rango_fechas(request)

    recibos = Recibo.objects.filter(
        empresa_id=empresa_id, fecha__gte=desde, fecha__lte=hasta
    ).select_related('cliente', 'sucursal')

    if request.GET.get('cliente'):
        recibos = recibos.filter(cliente_id=request.GET['cliente'])
    if request.GET.get('condic'):
        recibos = recibos.filter(condic=request.GET['condic'])
    if request.GET.get('q'):
        q = request.GET['q']
        recibos = recibos.filter(
            Q(cliente__razon_social__icontains=q) | Q(observaciones__icontains=q))

    recibos = _anotar_aplicado(recibos, 'aplicaciones').order_by('-fecha', '-numero')

    filas = []
    for rec in recibos:
        aplicado = rec.aplicado or Decimal('0')
        filas.append({
            'recibo': rec,
            'aplicado': aplicado,
            'pendiente': (Decimal(str(rec.total)) - aplicado) if not rec.anulado else Decimal('0'),
        })

    return render(request, 'tesoreria/partials/recibo_grilla.html', {
        'filas': filas,
        'total_general': sum((Decimal(str(f['recibo'].total)) for f in filas if not f['recibo'].anulado), Decimal('0')),
        'total_pendiente': sum((f['pendiente'] for f in filas), Decimal('0')),
    })



@login_required
def recibo_pdf(request, pk):
    from tesoreria.services.pdf_recibo import generar_pdf_recibo
    from django.http import HttpResponse

    empresa_id = request.session.get('empresa_id')
    recibo = get_object_or_404(Recibo, pk=pk, empresa_id=empresa_id)
    pdf_bytes = generar_pdf_recibo(recibo.pk)
    
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="RC_{recibo.punto:04d}-{recibo.numero:08d}.pdf"'
    return response


def _contexto_comprobante_recibo(pk, empresa_id):
    from tesoreria.models import MovimientoCajaDetalle, TransaccionBancaria, ValorTerceros
    from core.utils.numeros_a_letras import numero_a_letras

    recibo = get_object_or_404(
        Recibo.objects.select_related('cliente', 'empresa', 'sucursal'),
        pk=pk, empresa_id=empresa_id)

    return {
        'recibo': recibo,
        'aplicaciones': recibo.aplicaciones.select_related('venta__tipo').all(),
        'imputaciones': recibo.imputaciones_simples.select_related('cuenta_contable').all(),
        'detalles': MovimientoCajaDetalle.objects.filter(
            movimiento_caja__recibo=recibo).select_related('medio_pago'),
        'transacciones': TransaccionBancaria.objects.filter(
            movimiento_detalle__movimiento_caja__recibo=recibo).select_related('cuenta_bancaria'),
        'valores_recibidos': ValorTerceros.objects.filter(recibo=recibo).select_related('banco'),
        'total_letras': numero_a_letras(recibo.total),
        'fecha_impresion': timezone.localtime(),
    }

# ---------------------------------------------------------------- Valores de Terceros

from django.db.models import Sum

@login_required
def valores_terceros_listado(request):
    empresa_id = request.session.get('empresa_id')
    
    cliente_id = request.GET.get('cliente', '')
    cliente_display = ''
    if cliente_id:
        try:
            c_obj = ClienteProveedor.objects.get(pk=cliente_id, empresa_id=empresa_id)
            cliente_display = c_obj.razon_social
        except ClienteProveedor.DoesNotExist:
            cliente_id = ''

    proveedor_id = request.GET.get('proveedor', '')
    proveedor_display = ''
    if proveedor_id:
        try:
            p_obj = ClienteProveedor.objects.get(pk=proveedor_id, empresa_id=empresa_id)
            proveedor_display = p_obj.razon_social
        except ClienteProveedor.DoesNotExist:
            proveedor_id = ''

    estados = ValorTerceros.ESTADOS
    hoy = timezone.localdate().isoformat()
    
    return render(request, 'tesoreria/valores_terceros_listado.html', {
        'hoy': hoy,
        'cliente_id': cliente_id,
        'cliente_display': cliente_display,
        'proveedor_id': proveedor_id,
        'proveedor_display': proveedor_display,
        'estados': estados,
        'clientes': ClienteProveedor.objects.filter(empresa_id=empresa_id, tipo_entidad=1).order_by('razon_social'),
        'proveedores': ClienteProveedor.objects.filter(empresa_id=empresa_id, tipo_entidad=2).order_by('razon_social'),
    })


@login_required
def valores_terceros_grilla(request):
    empresa_id = request.session.get('empresa_id')
    
    valores = ValorTerceros.objects.filter(
        empresa_id=empresa_id
    ).select_related(
        'banco', 
        'recibo__cliente', 
        'orden_pago__proveedor'
    )

    if request.GET.get('vencimiento_desde'):
        valores = valores.filter(fecha_vencimiento__gte=request.GET['vencimiento_desde'])
    if request.GET.get('vencimiento_hasta'):
        valores = valores.filter(fecha_vencimiento__lte=request.GET['vencimiento_hasta'])
        
    if request.GET.get('estado'):
        valores = valores.filter(estado=request.GET['estado'])
        
    if request.GET.get('cliente'):
        valores = valores.filter(recibo__cliente_id=request.GET['cliente'])
        
    if request.GET.get('proveedor'):
        valores = valores.filter(orden_pago__proveedor_id=request.GET['proveedor'])
        
    if request.GET.get('q'):
        q = request.GET['q']
        valores = valores.filter(numero_cheque__icontains=q)
        
    if request.GET.get('asiento_id'):
        asiento_id = request.GET['asiento_id']
        if asiento_id.isdigit():
            valores = valores.filter(
                Q(asiento_recepcion_id=asiento_id) | Q(asiento_entrega_id=asiento_id)
            )

    total_importe = valores.aggregate(total=Sum('importe'))['total'] or Decimal('0')
    
    valores = list(valores.order_by('fecha_vencimiento', 'numero_cheque')[:500])

    # --- Bulk load origins and destinations from Asiento ---
    # Esto usa asiento_recepcion_id y asiento_entrega_id para sacar la razon_social
    from contable.models import Asiento
    
    asientos_ids = set()
    for v in valores:
        if v.asiento_recepcion_id: asientos_ids.add(v.asiento_recepcion_id)
        if v.asiento_entrega_id: asientos_ids.add(v.asiento_entrega_id)
        
    nombres_por_asiento = {}
    if asientos_ids:
        # Hacemos 1 sola query a Asiento trayendo el cli_pro asociado
        asientos = Asiento.objects.filter(asiento_id__in=asientos_ids).select_related('cli_pro')
        for ast in asientos:
            if ast.cli_pro:
                nombres_por_asiento[ast.asiento_id] = ast.cli_pro.razon_social
                
    for v in valores:
        v.origen_razon_social = nombres_por_asiento.get(v.asiento_recepcion_id)
        v.destino_razon_social = nombres_por_asiento.get(v.asiento_entrega_id)

    return render(request, 'tesoreria/partials/valores_terceros_grilla.html', {
        'valores': valores,
        'total_importe': total_importe,
    })
