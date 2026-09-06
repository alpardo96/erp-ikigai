"""ABM de los maestros del acopio de tabaco, integrados al panel de Configuración (Plan 081).

Sigue el patrón HTMX ya establecido en `verticalidades/distribucion/views_htmx.py`: modal para
alta/edición que responde con `HX-Trigger` para recargar la tabla y cerrar el modal, un buscador
que devuelve sólo las filas del `<tbody>`, y un borrado por POST.

REGLA INFLEXIBLE: toda consulta se acota por `session['empresa_id']`.
"""
import json

from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from verticalidades.agricola.core_agricola.models import Campania

from .forms import (CampaniaForm, ClaseTabacoForm, ConfiguracionTabacoForm,
                    ListaPrecioTabacoForm, TipoRetencionTabacoForm, VariedadTabacoForm)
from .models import (ClaseTabaco, ConfiguracionTabaco, ListaPrecioTabaco,
                     TipoRetencionTabaco, VariedadTabaco)


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
    """Aviso modal cuando el borrado no se puede hacer."""
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


def _guardar(request, form, evento):
    """Alta/edición común: sella empresa y auditoría, y dispara el refresco."""
    obj = form.save(commit=False)
    if not obj.pk:
        obj.empresa_id = request.session.get('empresa_id')
        obj.creado_por = request.user
    obj.modificado_por = request.user
    obj.save()
    return _trigger(evento, cerrar_modal=True)


def _modal(request, form, titulo, url_post, objeto=None):
    """Render del modal de alta/edición.

    Se usa una sola plantilla para los cinco maestros en vez de cinco casi idénticas: los
    formularios ya traen sus labels, sus widgets y sus errores, así que una plantilla que itere
    los campos da el mismo resultado y evita que arreglar el modal signifique arreglarlo cinco
    veces.
    """
    return render(request, 'agricola/modals/maestro_form.html', {
        'form': form, 'titulo': titulo, 'url_post': url_post, 'objeto': objeto,
    })


# --------------------------------------------------------------------- Campañas

@login_required
def campania_modal(request, id=None):
    empresa_id = request.session.get('empresa_id')
    campania = get_object_or_404(Campania, id=id, empresa_id=empresa_id) if id else None

    if request.method == 'POST':
        form = CampaniaForm(empresa_id, request.POST, instance=campania)
        if form.is_valid():
            return _guardar(request, form, 'reloadCampanias')
    else:
        form = CampaniaForm(empresa_id, instance=campania)

    return _modal(request, form,
                  'Editar Campaña' if campania else 'Nueva Campaña',
                  reverse('agro_campania_edit', args=[campania.id]) if campania
                  else reverse('agro_campania_add'),
                  campania)


@login_required
def buscar_campanias(request):
    q = (request.GET.get('q') or '').strip()
    qs = Campania.objects.filter(empresa_id=request.session.get('empresa_id'))
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(detalle__icontains=q))
    return render(request, 'agricola/partials/campania_table_rows.html',
                  {'campanias': qs.select_related('ejercicio')})


@login_required
def eliminar_campania(request, id):
    if request.method != 'POST':
        return HttpResponse(status=400)
    campania = get_object_or_404(Campania, id=id, empresa_id=request.session.get('empresa_id'))
    try:
        campania.delete()
    except ProtectedError:
        return _error("No se puede eliminar la campaña: tiene listas de precio u operaciones asociadas.")
    return _trigger('reloadCampanias')


# ------------------------------------------------------------------- Variedades

@login_required
def variedad_modal(request, id=None):
    empresa_id = request.session.get('empresa_id')
    variedad = get_object_or_404(VariedadTabaco, id=id, empresa_id=empresa_id) if id else None

    if request.method == 'POST':
        form = VariedadTabacoForm(empresa_id, request.POST, instance=variedad)
        if form.is_valid():
            return _guardar(request, form, 'reloadVariedades')
    else:
        form = VariedadTabacoForm(empresa_id, instance=variedad)

    return _modal(request, form,
                  'Editar Variedad' if variedad else 'Nueva Variedad',
                  reverse('agro_variedad_edit', args=[variedad.id]) if variedad
                  else reverse('agro_variedad_add'),
                  variedad)


@login_required
def buscar_variedades(request):
    q = (request.GET.get('q') or '').strip()
    qs = VariedadTabaco.objects.filter(empresa_id=request.session.get('empresa_id'))
    if q:
        qs = qs.filter(detalle__icontains=q)
    return render(request, 'agricola/partials/variedad_table_rows.html',
                  {'variedades': qs.select_related('producto')})


@login_required
def eliminar_variedad(request, id):
    if request.method != 'POST':
        return HttpResponse(status=400)
    variedad = get_object_or_404(VariedadTabaco, id=id,
                                 empresa_id=request.session.get('empresa_id'))
    try:
        variedad.delete()
    except ProtectedError:
        return _error("No se puede eliminar la variedad: tiene clases o listas de precio asociadas.")
    return _trigger('reloadVariedades')


# ----------------------------------------------------------------------- Clases

@login_required
def clase_modal(request, id=None):
    empresa_id = request.session.get('empresa_id')
    clase = get_object_or_404(ClaseTabaco, id=id, empresa_id=empresa_id) if id else None

    if request.method == 'POST':
        form = ClaseTabacoForm(empresa_id, request.POST, instance=clase)
        if form.is_valid():
            return _guardar(request, form, 'reloadClases')
    else:
        form = ClaseTabacoForm(empresa_id, instance=clase)

    return _modal(request, form,
                  'Editar Clase de Tabaco' if clase else 'Nueva Clase de Tabaco',
                  reverse('agro_clase_edit', args=[clase.id]) if clase
                  else reverse('agro_clase_add'),
                  clase)


@login_required
def buscar_clases(request):
    """Filtra por texto y, opcionalmente, por variedad.

    Son 75 filas: entran de una sola vez, así que no hace falta paginar. El filtro por variedad
    existe porque en la práctica se trabaja sobre una sola.
    """
    empresa_id = request.session.get('empresa_id')
    q = (request.GET.get('q') or '').strip()
    variedad_id = (request.GET.get('variedad') or '').strip()

    qs = ClaseTabaco.objects.filter(empresa_id=empresa_id).select_related('variedad')
    if variedad_id.isdigit():
        qs = qs.filter(variedad_id=int(variedad_id))
    if q:
        qs = qs.filter(Q(detalle__icontains=q) | Q(grupo__iexact=q))

    return render(request, 'agricola/partials/clase_table_rows.html', {'clases': qs})


@login_required
def eliminar_clase(request, id):
    if request.method != 'POST':
        return HttpResponse(status=400)
    clase = get_object_or_404(ClaseTabaco, id=id, empresa_id=request.session.get('empresa_id'))
    try:
        clase.delete()
    except ProtectedError:
        return _error("No se puede eliminar la clase: está usada en romaneos o liquidaciones.")
    return _trigger('reloadClases')


# ------------------------------------------------------------ Listas de precio

@login_required
def lista_precio_modal(request, id=None):
    empresa_id = request.session.get('empresa_id')
    lista = get_object_or_404(ListaPrecioTabaco, id=id, empresa_id=empresa_id) if id else None

    if request.method == 'POST':
        form = ListaPrecioTabacoForm(empresa_id, request.POST, instance=lista)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.pk:
                obj.empresa_id = empresa_id
                obj.creado_por = request.user
            obj.modificado_por = request.user
            # La aprobación deja rastro de quién y cuándo: es lo que habilita a formar precios.
            if obj.aprobada and not obj.aprobada_el:
                obj.aprobada_por = request.user
                obj.aprobada_el = timezone.now()
            elif not obj.aprobada:
                obj.aprobada_por = None
                obj.aprobada_el = None
            obj.save()
            return _trigger('reloadListasPrecio', cerrar_modal=True)
    else:
        form = ListaPrecioTabacoForm(empresa_id, instance=lista)

    return _modal(request, form,
                  'Editar Lista de Precio' if lista else 'Nueva Lista de Precio',
                  reverse('agro_lista_precio_edit', args=[lista.id]) if lista
                  else reverse('agro_lista_precio_add'),
                  lista)


@login_required
def buscar_listas_precio(request):
    q = (request.GET.get('q') or '').strip()
    qs = (ListaPrecioTabaco.objects
          .filter(empresa_id=request.session.get('empresa_id'))
          .select_related('variedad', 'campania'))
    if q:
        qs = qs.filter(Q(variedad__detalle__icontains=q) | Q(campania__codigo__icontains=q))
    return render(request, 'agricola/partials/lista_precio_table_rows.html', {'listas': qs})


@login_required
def eliminar_lista_precio(request, id):
    if request.method != 'POST':
        return HttpResponse(status=400)
    lista = get_object_or_404(ListaPrecioTabaco, id=id,
                              empresa_id=request.session.get('empresa_id'))
    if lista.aprobada:
        return _error("No se puede eliminar una lista aprobada: puede haber comprobantes "
                      "formados con ella. Cerrá su vigencia en lugar de borrarla.")
    try:
        lista.delete()
    except ProtectedError:
        return _error("No se puede eliminar la lista: tiene comprobantes asociados.")
    return _trigger('reloadListasPrecio')


# --------------------------------------------------------- Conceptos de retención

@login_required
def retencion_modal(request, id=None):
    empresa_id = request.session.get('empresa_id')
    retencion = (get_object_or_404(TipoRetencionTabaco, id=id, empresa_id=empresa_id)
                 if id else None)

    if request.method == 'POST':
        form = TipoRetencionTabacoForm(empresa_id, request.POST, instance=retencion)
        if form.is_valid():
            return _guardar(request, form, 'reloadRetenciones')
    else:
        form = TipoRetencionTabacoForm(empresa_id, instance=retencion)

    return _modal(request, form,
                  'Editar Concepto de Retención' if retencion else 'Nuevo Concepto de Retención',
                  reverse('agro_retencion_edit', args=[retencion.id]) if retencion
                  else reverse('agro_retencion_add'),
                  retencion)


@login_required
def buscar_retenciones(request):
    q = (request.GET.get('q') or '').strip()
    qs = (TipoRetencionTabaco.objects
          .filter(empresa_id=request.session.get('empresa_id'))
          .select_related('cuenta_contable', 'jurisdiccion'))
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(detalle__icontains=q)
                       | Q(organismo__icontains=q))
    return render(request, 'agricola/partials/retencion_table_rows.html', {'retenciones': qs})


@login_required
def eliminar_retencion(request, id):
    if request.method != 'POST':
        return HttpResponse(status=400)
    retencion = get_object_or_404(TipoRetencionTabaco, id=id,
                                  empresa_id=request.session.get('empresa_id'))
    try:
        retencion.delete()
    except ProtectedError:
        return _error("No se puede eliminar el concepto: fue aplicado en liquidaciones. "
                      "Cerrá su vigencia en lugar de borrarlo.")
    return _trigger('reloadRetenciones')


# --------------------------------------------------------- Configuración general

@login_required
def configuracion_tabaco(request):
    """Formulario único por empresa. Se crea al primer guardado, no antes."""
    empresa_id = request.session.get('empresa_id')
    config = ConfiguracionTabaco.objects.filter(empresa_id=empresa_id).first()

    if request.method == 'POST':
        form = ConfiguracionTabacoForm(empresa_id, request.POST, instance=config)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.pk:
                obj.empresa_id = empresa_id
                obj.creado_por = request.user
            obj.modificado_por = request.user
            obj.save()
            return _trigger('configTabacoGuardada')
    else:
        form = ConfiguracionTabacoForm(empresa_id, instance=config)

    return render(request, 'agricola/partials/config_tabaco_form.html',
                  {'form': form, 'config': config, 'guardado': request.method == 'POST'})
