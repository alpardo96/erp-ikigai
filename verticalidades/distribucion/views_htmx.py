"""ABM de los maestros de Distribución, integrados al panel de Configuración.

Sigue el patrón HTMX ya establecido en el proyecto (`empresas/views_htmx.py`,
`tesoreria/views_htmx.py`): modal para alta/edición que responde con `HX-Trigger`
para recargar la tabla y cerrar el modal, un buscador que devuelve sólo las filas
del `<tbody>`, y un borrado por POST.

REGLA INFLEXIBLE: toda consulta se acota por `session['empresa_id']`.
"""
import json

from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.html import escape

from facturacion.models import ClienteProveedor

from .forms import (DomicilioEntregaForm, MotivoDevolucionForm, PersonalForm,
                    VehiculoForm, ZonaRepartoForm)
from .models import (CarteraVendedor, DiaVisita, DomicilioEntrega, MotivoDevolucion,
                     Personal, Vehiculo, ZonaReparto)
from .services.catalogos import sembrar_motivos


def _trigger(*eventos, cerrar_modal=False):
    """Respuesta vacía que dispara los eventos HTMX de refresco."""
    payload = {evento: True for evento in eventos}
    if cerrar_modal:
        payload['cerrarModal'] = True
    response = HttpResponse()
    response['HX-Trigger'] = json.dumps(payload)
    if cerrar_modal:
        # Evita que HTMX limpie el modal antes de que los eventos burbujeen.
        response['HX-Reswap'] = 'none'
    return response


def _error(mensaje):
    """Aviso modal cuando el borrado no se puede hacer.

    Se devuelve al `#modal-container` como un modal propio: un div suelto quedaría
    inyectado fuera de contexto y el usuario no entendería por qué no pasó nada.
    """
    return HttpResponse(
        '<div class="fixed inset-0 z-[100] flex items-center justify-center '
        'bg-slate-900/60 backdrop-blur-sm px-4">'
        '  <div class="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden '
        'border border-gray-100">'
        '    <div class="px-8 py-6 border-b border-gray-100">'
        '      <h3 class="text-lg font-bold text-gray-900">No se puede eliminar</h3>'
        '    </div>'
        f'    <div class="px-8 py-6 text-sm text-gray-600">{escape(mensaje)}</div>'
        '    <div class="bg-gray-50 px-8 py-4 flex justify-end">'
        '      <button type="button" class="px-6 py-2 text-sm font-bold text-white '
        'bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow" '
        'onclick="document.getElementById(\'modal-container\').innerHTML = \'\'">'
        'Entendido</button>'
        '    </div>'
        '  </div>'
        '</div>')


# ---------------------------------------------------------------- Zonas de reparto

@login_required
def zona_modal(request, id=None):
    empresa_id = request.session.get('empresa_id')
    zona = get_object_or_404(ZonaReparto, id=id, empresa_id=empresa_id) if id else None

    if request.method == 'POST':
        form = ZonaRepartoForm(empresa_id, request.POST, instance=zona)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.pk:
                obj.empresa_id = empresa_id
                obj.creado_por = request.user
            obj.modificado_por = request.user
            obj.save()
            return _trigger('reloadZonas', cerrar_modal=True)
    else:
        form = ZonaRepartoForm(empresa_id, instance=zona)

    return render(request, 'configuracion/modals/zona_form.html', {'form': form, 'zona': zona})


@login_required
def buscar_zonas(request):
    q = (request.GET.get('q') or '').strip()
    zonas = ZonaReparto.objects.filter(empresa_id=request.session.get('empresa_id'))
    if q:
        zonas = zonas.filter(nombre__icontains=q)
    return render(request, 'configuracion/partials/zona_table_rows.html',
                  {'zonas': zonas.order_by('orden', 'nombre')})


@login_required
def eliminar_zona(request, id):
    if request.method != 'POST':
        return HttpResponse(status=400)
    zona = get_object_or_404(ZonaReparto, id=id, empresa_id=request.session.get('empresa_id'))
    try:
        zona.delete()
    except ProtectedError:
        return _error("No se puede eliminar la zona: tiene personal o clientes asignados.")
    return _trigger('reloadZonas')


# --------------------------------------------------------------------- Personal

@login_required
def personal_modal(request, id=None):
    empresa_id = request.session.get('empresa_id')
    persona = get_object_or_404(Personal, id=id, empresa_id=empresa_id) if id else None

    if request.method == 'POST':
        form = PersonalForm(empresa_id, request.POST, instance=persona)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.pk:
                obj.empresa_id = empresa_id
                obj.creado_por = request.user
            obj.modificado_por = request.user
            obj.save()
            return _trigger('reloadPersonal', cerrar_modal=True)
    else:
        form = PersonalForm(empresa_id, instance=persona)

    return render(request, 'configuracion/modals/personal_form.html',
                  {'form': form, 'persona': persona})


@login_required
def buscar_personal(request):
    q = (request.GET.get('q') or '').strip()
    personal = (Personal.objects
                .filter(empresa_id=request.session.get('empresa_id'))
                .select_related('zona', 'usuario'))
    if q:
        filtro = Q(nombre__icontains=q) | Q(documento__icontains=q)
        if q.isdigit():
            filtro |= Q(codigo=int(q))
        personal = personal.filter(filtro)
    return render(request, 'configuracion/partials/personal_table_rows.html',
                  {'personal': personal.order_by('nombre')})


@login_required
def eliminar_personal(request, id):
    if request.method != 'POST':
        return HttpResponse(status=400)
    persona = get_object_or_404(Personal, id=id, empresa_id=request.session.get('empresa_id'))
    try:
        persona.delete()
    except ProtectedError:
        return _error("No se puede eliminar: tiene clientes en cartera o repartos asociados. "
                      "Desmarcá 'Activo' en lugar de borrarlo, para no perder el historial.")
    return _trigger('reloadPersonal')


# --------------------------------------------------------------------- Vehículos

@login_required
def vehiculo_modal(request, id=None):
    empresa_id = request.session.get('empresa_id')
    vehiculo = get_object_or_404(Vehiculo, id=id, empresa_id=empresa_id) if id else None

    if request.method == 'POST':
        form = VehiculoForm(empresa_id, request.POST, instance=vehiculo)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.pk:
                obj.empresa_id = empresa_id
                obj.creado_por = request.user
            obj.modificado_por = request.user
            obj.save()
            return _trigger('reloadVehiculos', cerrar_modal=True)
    else:
        form = VehiculoForm(empresa_id, instance=vehiculo)

    return render(request, 'configuracion/modals/vehiculo_form.html',
                  {'form': form, 'vehiculo': vehiculo})


@login_required
def buscar_vehiculos(request):
    q = (request.GET.get('q') or '').strip()
    vehiculos = (Vehiculo.objects
                 .filter(empresa_id=request.session.get('empresa_id'))
                 .select_related('sucursal'))
    if q:
        vehiculos = vehiculos.filter(Q(patente__icontains=q) | Q(descripcion__icontains=q))
    return render(request, 'configuracion/partials/vehiculo_table_rows.html',
                  {'vehiculos': vehiculos.order_by('patente')})


@login_required
def eliminar_vehiculo(request, id):
    if request.method != 'POST':
        return HttpResponse(status=400)
    vehiculo = get_object_or_404(Vehiculo, id=id, empresa_id=request.session.get('empresa_id'))
    try:
        vehiculo.delete()
    except ProtectedError:
        return _error("No se puede eliminar el vehículo: tiene repartos asociados.")
    return _trigger('reloadVehiculos')


# ------------------------------------------------------- Motivos de devolución

@login_required
def motivo_modal(request, id=None):
    empresa_id = request.session.get('empresa_id')
    motivo = get_object_or_404(MotivoDevolucion, id=id, empresa_id=empresa_id) if id else None

    if request.method == 'POST':
        form = MotivoDevolucionForm(empresa_id, request.POST, instance=motivo)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.pk:
                obj.empresa_id = empresa_id
                obj.creado_por = request.user
            obj.modificado_por = request.user
            obj.save()
            return _trigger('reloadMotivos', cerrar_modal=True)
    else:
        form = MotivoDevolucionForm(empresa_id, instance=motivo)

    return render(request, 'configuracion/modals/motivo_form.html',
                  {'form': form, 'motivo': motivo})


@login_required
def buscar_motivos(request):
    q = (request.GET.get('q') or '').strip()
    motivos = MotivoDevolucion.objects.filter(empresa_id=request.session.get('empresa_id'))
    if q:
        motivos = motivos.filter(Q(codigo__icontains=q) | Q(descripcion__icontains=q))
    return render(request, 'configuracion/partials/motivo_table_rows.html',
                  {'motivos': motivos.order_by('codigo')})


@login_required
def eliminar_motivo(request, id):
    if request.method != 'POST':
        return HttpResponse(status=400)
    motivo = get_object_or_404(MotivoDevolucion, id=id,
                               empresa_id=request.session.get('empresa_id'))
    try:
        motivo.delete()
    except ProtectedError:
        return _error("No se puede eliminar el motivo: ya fue usado en devoluciones. "
                      "Desmarcá 'Activo' para que deje de ofrecerse.")
    return _trigger('reloadMotivos')


@login_required
def sembrar_motivos_iniciales(request):
    """Carga el catálogo inicial de motivos sugerido en el Plan 074.

    Es idempotente: sólo crea los que faltan y no pisa lo que el usuario haya editado.
    """
    if request.method != 'POST':
        return HttpResponse(status=400)
    sembrar_motivos(request.session.get('empresa_id'), usuario=request.user)
    return _trigger('reloadMotivos')


# --------------------------------------------------- Cartera y agenda de visitas

@login_required
def asignar_vendedor(request, cliente_id):
    """Asigna (o desasigna) el vendedor responsable de un cliente.

    Un cliente tiene UN SOLO vendedor porque es el responsable directo de su saldo, así
    que la asignación se reemplaza en lugar de acumularse.
    """
    if request.method != 'POST':
        return HttpResponse(status=400)

    empresa_id = request.session.get('empresa_id')
    cliente = get_object_or_404(ClienteProveedor, codigo_id=cliente_id,
                                empresa_id=empresa_id, tipo_entidad=1)
    vendedor_id = (request.POST.get('vendedor') or '').strip()

    if vendedor_id:
        vendedor = get_object_or_404(Personal, id=vendedor_id, empresa_id=empresa_id,
                                     es_vendedor=True)
        CarteraVendedor.objects.update_or_create(
            empresa_id=empresa_id, cliente=cliente,
            defaults={'vendedor': vendedor, 'activa': True,
                      'modificado_por': request.user},
        )
    else:
        CarteraVendedor.objects.filter(empresa_id=empresa_id, cliente=cliente).delete()

    return _fila_cartera(request, cliente)


def _fila_cartera(request, cliente):
    """Vuelve a renderizar la fila del cliente, para que HTMX la reemplace en el lugar."""
    empresa_id = request.session.get('empresa_id')
    cliente = (ClienteProveedor.objects
               .select_related('distribuidora')
               .prefetch_related('cartera__vendedor', 'domicilios_entrega__zona',
                                 'domicilios_entrega__dias_visita')
               .get(pk=cliente.pk))
    return render(request, 'distribucion/partials/cartera_fila.html', {
        'cliente': cliente,
        'vendedores': Personal.objects.filter(
            empresa_id=empresa_id, es_vendedor=True, activo=True).order_by('nombre'),
        'dias': DiaVisita.DIAS,
        'frecuencias': DiaVisita.FRECUENCIAS,
    })


# ------------------------------------------------------- Domicilios de entrega

@login_required
def domicilio_modal(request, cliente_id=None, id=None):
    """Alta y edición de un punto de entrega del cliente."""
    empresa_id = request.session.get('empresa_id')
    if id:
        domicilio = get_object_or_404(DomicilioEntrega, id=id, empresa_id=empresa_id)
        cliente = domicilio.cliente
    else:
        domicilio = None
        cliente = get_object_or_404(ClienteProveedor, codigo_id=cliente_id,
                                    empresa_id=empresa_id, tipo_entidad=1)

    if request.method == 'POST':
        form = DomicilioEntregaForm(empresa_id, cliente, request.POST, instance=domicilio)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.pk:
                obj.empresa_id = empresa_id
                obj.cliente = cliente
                obj.creado_por = request.user
                # El primero que se carga queda como principal, para que el pedido
                # siempre tenga una propuesta por defecto.
                if not DomicilioEntrega.objects.filter(cliente=cliente).exists():
                    obj.es_principal = True
            obj.modificado_por = request.user
            obj.save()
            return _trigger('reloadCartera', cerrar_modal=True)
    else:
        form = DomicilioEntregaForm(empresa_id, cliente, instance=domicilio)

    return render(request, 'distribucion/modals/domicilio_form.html',
                  {'form': form, 'domicilio': domicilio, 'cliente': cliente})


@login_required
def eliminar_domicilio(request, id):
    if request.method != 'POST':
        return HttpResponse(status=400)
    domicilio = get_object_or_404(DomicilioEntrega, id=id,
                                  empresa_id=request.session.get('empresa_id'))
    try:
        domicilio.delete()
    except ProtectedError:
        return _error("No se puede eliminar: tiene pedidos asociados. "
                      "Desmarcá 'Activo' para que deje de ofrecerse en la carga.")
    return _trigger('reloadCartera')


@login_required
def domicilio_dias(request, id):
    """Fija los días de visita de un punto de entrega.

    Admite varios: con lácteos es habitual pasar dos o tres veces por semana.
    """
    if request.method != 'POST':
        return HttpResponse(status=400)

    empresa_id = request.session.get('empresa_id')
    domicilio = get_object_or_404(DomicilioEntrega, id=id, empresa_id=empresa_id)
    dias = request.POST.getlist('dias')
    frecuencia = (request.POST.get('frecuencia') or 'SEMANAL').strip()

    DiaVisita.objects.filter(domicilio=domicilio).delete()
    for dia in dias:
        DiaVisita.objects.create(empresa_id=empresa_id, domicilio=domicilio,
                                 dia_semana=int(dia), frecuencia=frecuencia)

    return _trigger('reloadCartera')
