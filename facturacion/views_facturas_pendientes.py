"""Listado de Facturas Pendientes — Plan 056.

Cuatro vistas, las cuatro `GET` y de SÓLO LECTURA: la pantalla, la grilla HTMX, el Excel y
el PDF. No hay ninguna ruta que escriba: `pagado` y `saldo` son derivados de las aplicaciones
de Órdenes de Pago y Recibos, y los mantiene `contable/services/saldos.py`.
"""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from contable.models import CONDIC_MOVIMIENTO, condic_opciones
from empresas.models import Empresa, Ejercicio
from facturacion.models import ClienteProveedor
from facturacion.services.facturas_pendientes import (
    ESTADOS_PAGO, LIMITE_GRILLA, OPERACIONES, FiltroFacturas, agrupar_por_entidad,
    consultar,
)
from facturacion.services.facturas_pendientes_excel import exportar_facturas_pendientes_excel
from facturacion.services.reportes_pdf import render_pdf_response


def _rango_por_defecto(request):
    """Réplica del `Form.Init` del VFP: el ejercicio en curso, acotado a hoy.

    Sin ejercicio en sesión cae al mes corriente, para no devolver un rango vacío.
    """
    hoy = timezone.localdate()
    ejercicio_id = request.session.get('ejercicio_id')
    if ejercicio_id:
        ejercicio = Ejercicio.objects.filter(pk=ejercicio_id).first()
        if ejercicio:
            return ejercicio.inicio, min(ejercicio.cierre, hoy)
    return hoy.replace(day=1), hoy


def _fecha(valor, por_defecto):
    if not valor:
        return por_defecto
    try:
        return date.fromisoformat(valor)
    except (TypeError, ValueError):
        return por_defecto


def _filtro_desde_request(request, empresa_id):
    """Traduce el querystring al filtro del servicio, saneando todo lo que llega."""
    desde_def, hasta_def = _rango_por_defecto(request)

    operacion = request.GET.get('operacion', 'C')
    if operacion not in dict(OPERACIONES):
        operacion = 'C'

    estado = request.GET.get('estado', 'todas')
    if estado not in dict(ESTADOS_PAGO):
        estado = 'todas'

    # Sin ningún checkbox marcado se entiende "todas las condiciones", no "ninguna":
    # un listado en blanco sólo confundiría.
    condics = tuple(
        int(v) for v in request.GET.getlist('condic')
        if v.isdigit() and int(v) in CONDIC_MOVIMIENTO
    ) or tuple(CONDIC_MOVIMIENTO)

    entidad_id = request.GET.get('entidad') or None
    if entidad_id:
        # Multi-tenant: una entidad de otra empresa se descarta, no se filtra por ella.
        if not ClienteProveedor.objects.filter(
                pk=entidad_id, empresa_id=empresa_id).exists():
            entidad_id = None

    return FiltroFacturas(
        empresa_id=empresa_id,
        desde=_fecha(request.GET.get('desde'), desde_def),
        hasta=_fecha(request.GET.get('hasta'), hasta_def),
        operacion=operacion,
        entidad_id=int(entidad_id) if entidad_id else None,
        estado=estado,
        condics=condics,
        incluir_anuladas=request.GET.get('incluir_anuladas') == '1',
    )


def _empresa_o_redirect(request):
    empresa_id = request.session.get('empresa_id')
    if not empresa_id:
        messages.warning(request, "Por favor, seleccione una empresa primero.")
        return None, redirect('seleccion_empresa')
    return empresa_id, None


@login_required
def facturas_pendientes_listado(request):
    """Pantalla con la barra de filtros. La grilla la trae HTMX (`hx-trigger="load"`)."""
    empresa_id, salida = _empresa_o_redirect(request)
    if salida:
        return salida

    filtro = _filtro_desde_request(request, empresa_id)

    entidad_display = ''
    if filtro.entidad_id:
        entidad = ClienteProveedor.objects.filter(
            pk=filtro.entidad_id, empresa_id=empresa_id).first()
        entidad_display = entidad.razon_social if entidad else ''

    return render(request, 'facturacion/reportes/facturas_pendientes.html', {
        'filtro': filtro,
        'desde': filtro.desde.isoformat(),
        'hasta': filtro.hasta.isoformat(),
        'entidad_display': entidad_display,
        'operaciones': OPERACIONES,
        'estados': ESTADOS_PAGO,
        'condic_opciones': condic_opciones(CONDIC_MOVIMIENTO),
    })


@login_required
def facturas_pendientes_grilla(request):
    """Filas del listado, servidas por HTMX.

    Se truncan a `LIMITE_GRILLA`, pero los totales salen del conjunto completo.
    """
    empresa_id, salida = _empresa_o_redirect(request)
    if salida:
        return salida

    filtro = _filtro_desde_request(request, empresa_id)
    filas, totales, truncado = consultar(filtro, limite=LIMITE_GRILLA)

    return render(request, 'facturacion/reportes/partials/facturas_pendientes_grilla.html', {
        'filas': filas,
        'totales': totales,
        'truncado': truncado,
        'limite': LIMITE_GRILLA,
        'filtro': filtro,
    })


@login_required
def facturas_pendientes_excel(request):
    """Excel sin truncar, con la columna `Acum.` global (como el VFP)."""
    empresa_id, salida = _empresa_o_redirect(request)
    if salida:
        return salida

    filtro = _filtro_desde_request(request, empresa_id)
    filas, totales, _ = consultar(filtro)
    empresa = Empresa.objects.filter(pk=empresa_id).first()
    return exportar_facturas_pendientes_excel(filas, totales, empresa, filtro)


@login_required
def facturas_pendientes_pdf(request):
    """"RESUMEN DE CUENTAS": agrupado por cliente/proveedor, con subtotales y total final."""
    empresa_id, salida = _empresa_o_redirect(request)
    if salida:
        return salida

    filtro = _filtro_desde_request(request, empresa_id)
    filas, totales, _ = consultar(filtro)

    contexto = {
        'empresa': Empresa.objects.filter(pk=empresa_id).first(),
        'grupos': agrupar_por_entidad(filas),
        'totales': totales,
        'filtro': filtro,
        'etiqueta_entidad': 'Cliente' if filtro.es_venta else 'Proveedor',
        'fecha_desde': filtro.desde,
        'fecha_hasta': filtro.hasta,
        'fecha_emision': timezone.localtime(),
    }
    nombre = f"facturas_pendientes_{'ventas' if filtro.es_venta else 'compras'}.pdf"
    return render_pdf_response('facturacion/pdf/facturas_pendientes.html', contexto, nombre)
