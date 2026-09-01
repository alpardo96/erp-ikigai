"""Caja Diaria de Tesorería — reporte de movimientos de fondos y saldos disponibles.

Pantalla de control del tesorero: muestra los movimientos de la caja y los saldos, para verificar
si está todo registrado. No registra operaciones: los accesos rápidos llevan a Recibos y Órdenes
de Pago, que son los que efectivamente registran.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render

from empresas.models import Sucursal
from tesoreria.models import CajaSesion
from tesoreria.services.caja_diaria import (
    armar_caja_diaria, cerrar_caja, get_caja_tesoreria, get_o_abrir_caja,
)

MAX_CAJAS_LISTADO = 60


from tesoreria.permisos import bloquear_cajero

def _contexto_base(request):
    """Resuelve empresa, sucursal, listado de cajas y la caja seleccionada.

    Devuelve `None` si falta la selección de empresa/sucursal (el caller redirige).
    """
    empresa_id = request.session.get('empresa_id')
    if not empresa_id:
        return None

    sucursales = Sucursal.objects.filter(empresa_id=empresa_id).order_by('nombre')

    sucursal_id = request.GET.get('sucursal_id') or request.session.get('sucursal_id')
    if sucursal_id and not sucursales.filter(id=sucursal_id).exists():
        sucursal_id = None
    if not sucursal_id:
        primera = sucursales.first()
        if not primera:
            return None
        sucursal_id = primera.id

    caja = get_caja_tesoreria(empresa_id, sucursal_id)

    cajas = list(
        CajaSesion.objects
        .filter(caja=caja)
        .order_by('-estado', '-numero', '-id')[:MAX_CAJAS_LISTADO]
    )

    sesion_id = request.GET.get('sesion_id')
    sesion = None
    if sesion_id:
        sesion = next((s for s in cajas if str(s.id) == str(sesion_id)), None)
    if sesion is None:
        # Por defecto se muestra la caja activa; si no hay ninguna, se abre con el arrastre.
        sesion = next((s for s in cajas if s.estado == 'A'), None)
    if sesion is None:
        _, sesion = get_o_abrir_caja(empresa_id, sucursal_id, request.user)
        cajas.insert(0, sesion)

    condic_raw = request.GET.get('condic', '')
    condic = int(condic_raw) if condic_raw in ('1', '2') else None

    datos = armar_caja_diaria(sesion, condic=condic)

    return {
        'empresa_id': empresa_id,
        'sucursales': sucursales,
        'sucursal_id': int(sucursal_id),
        'caja': caja,
        'cajas': cajas,
        'sesion': sesion,
        'condic': condic_raw if condic else '',
        'movimientos': datos['movimientos'],
        'saldos': datos['saldos'],
    }


@login_required
@bloquear_cajero
def caja_diaria_index(request):
    contexto = _contexto_base(request)
    if contexto is None:
        messages.warning(request, "Seleccione una empresa y una sucursal para operar la Caja Diaria.")
        return redirect('seleccion_empresa')
    return render(request, 'tesoreria/caja_diaria.html', contexto)


@login_required
def caja_diaria_grilla(request):
    """Refresco HTMX de la grilla + panel de saldos (cambio de caja, sucursal o filtro)."""
    contexto = _contexto_base(request)
    if contexto is None:
        return HttpResponse("<div class='p-6 text-sm text-red-600'>Seleccione una empresa y sucursal.</div>")
    return render(request, 'tesoreria/partials/caja_diaria_grilla.html', contexto)


@login_required
def caja_diaria_cerrar(request):
    """Cierra la caja activa y abre la siguiente arrastrando los saldos."""
    if request.method != 'POST':
        return HttpResponse(status=405)

    empresa_id = request.session.get('empresa_id')
    sesion = CajaSesion.objects.filter(
        pk=request.POST.get('sesion_id'), caja__empresa_id=empresa_id, caja__tipo='T',
    ).first()

    if not sesion:
        messages.error(request, "No se encontró la caja a cerrar.")
        return redirect('caja_diaria_index')

    try:
        cerrada, nueva = cerrar_caja(sesion, request.user)
    except ValueError as error:
        messages.error(request, str(error))
        return redirect(f"{_url_index()}?sesion_id={sesion.id}")

    messages.success(
        request,
        f"Caja N° {cerrada.numero} cerrada con un saldo de $ {cerrada.saldo_final_neto:,.2f}. "
        f"Se abrió la caja N° {nueva.numero}."
    )
    return redirect(f"{_url_index()}?sesion_id={nueva.id}")


def _url_index():
    from django.urls import reverse
    return reverse('caja_diaria_index')


@login_required
def caja_diaria_excel(request):
    contexto = _contexto_base(request)
    if contexto is None:
        return HttpResponse(status=400)

    from tesoreria.services.caja_diaria_export import exportar_caja_diaria_excel
    return exportar_caja_diaria_excel(
        contexto['sesion'], contexto['movimientos'], contexto['saldos'],
    )


@login_required
def caja_diaria_pdf(request):
    contexto = _contexto_base(request)
    if contexto is None:
        return HttpResponse(status=400)

    from tesoreria.services.caja_diaria_export import exportar_caja_diaria_pdf
    return exportar_caja_diaria_pdf(
        contexto['sesion'], contexto['movimientos'], contexto['saldos'],
    )
