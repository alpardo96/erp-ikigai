"""Pantallas del romaneo (Plan 082).

Las vistas NO contienen reglas de negocio: validan permisos y empresa, arman el formulario y
delegan en `services/romaneo.py`. Es lo que permite que la misma lógica sirva mañana para una API
o una importación masiva sin duplicarla.

REGLA INFLEXIBLE: todo queryset se acota por `session['empresa_id']`.
"""
import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from .forms_romaneo import (AbrirRomaneoForm, AnularRomaneoForm, FardoForm, FiltroRomaneosForm,
                            ReclasificarForm)
from .models import ClaseTabaco, FardoTabaco, ReclasificacionFardo, RomaneoTabaco
from .services import romaneo as svc


def _empresa(request):
    return request.session.get('empresa_id')


def _romaneo(request, pk):
    return get_object_or_404(RomaneoTabaco, pk=pk, empresa_id=_empresa(request))


def _trigger(*eventos):
    respuesta = HttpResponse()
    respuesta['HX-Trigger'] = json.dumps({e: True for e in eventos})
    return respuesta


def _aviso(mensaje, tono='red'):
    """HTML de la franja de aviso que se autodescarta.

    Devuelve TEXTO, no una respuesta: se antepone al panel de fardos para que el usuario vea el
    error y, al mismo tiempo, la grilla quede consistente con lo que hay en la base.
    """
    return (f'<div x-data="{{ show: true }}" x-show="show" '
            f'x-init="setTimeout(() => show = false, 6000)" '
            f'class="p-3 mb-3 rounded-xl bg-{tono}-50 border border-{tono}-200 '
            f'text-sm text-{tono}-700 font-medium">{escape(mensaje)}</div>')


def _mensaje_de(error):
    """Texto plano de un `ValidationError`, venga como lista o como mensaje suelto."""
    if hasattr(error, 'messages'):
        return ' '.join(error.messages)
    return str(error)


# ---------------------------------------------------------------------------
# Listado
# ---------------------------------------------------------------------------

@login_required
def romaneo_listado(request):
    empresa_id = _empresa(request)
    filtros = FiltroRomaneosForm(empresa_id, request.GET or None)
    return render(request, 'agricola/romaneo/listado.html', {
        'filtros': filtros,
        'romaneos': _filtrar(request, filtros),
    })


@login_required
def romaneo_grilla(request):
    """Sólo las filas: es lo que refresca HTMX al cambiar un filtro."""
    filtros = FiltroRomaneosForm(_empresa(request), request.GET or None)
    return render(request, 'agricola/romaneo/listado_filas.html',
                  {'romaneos': _filtrar(request, filtros)})


def _filtrar(request, filtros):
    qs = (RomaneoTabaco.objects
          .filter(empresa_id=_empresa(request))
          .select_related('productor', 'variedad', 'campania'))

    if not filtros.is_valid():
        return qs[:200]

    datos = filtros.cleaned_data
    if datos.get('q'):
        q = datos['q']
        qs = qs.filter(Q(productor__razon_social__icontains=q) | Q(remito__icontains=q)
                       | Q(transporte__icontains=q))
    for campo in ('productor', 'variedad', 'campania'):
        if datos.get(campo):
            qs = qs.filter(**{campo: datos[campo]})
    if datos.get('estado'):
        qs = qs.filter(estado=int(datos['estado']))
    if datos.get('condic'):
        qs = qs.filter(condic=int(datos['condic']))
    if datos.get('desde'):
        qs = qs.filter(fecha__gte=datos['desde'])
    if datos.get('hasta'):
        qs = qs.filter(fecha__lte=datos['hasta'])

    return qs[:200]


# ---------------------------------------------------------------------------
# Apertura y carga
# ---------------------------------------------------------------------------

@login_required
def romaneo_nuevo(request):
    empresa_id = _empresa(request)

    if request.method == 'POST':
        form = AbrirRomaneoForm(empresa_id, request.POST)
        if form.is_valid():
            from empresas.models import Empresa, Sucursal
            sucursal = Sucursal.objects.filter(empresa_id=empresa_id).first()
            if sucursal is None:
                return render(request, 'agricola/romaneo/nuevo.html',
                              {'form': form, 'error': "La empresa no tiene sucursales cargadas."})
            try:
                romaneo = svc.abrir_romaneo(
                    empresa=Empresa.objects.get(pk=empresa_id), sucursal=sucursal,
                    usuario=request.user, **form.cleaned_data)
            except ValidationError as e:
                return render(request, 'agricola/romaneo/nuevo.html',
                              {'form': form, 'error': _mensaje_de(e)})
            return redirect('agro_romaneo_carga', pk=romaneo.pk)
    else:
        form = AbrirRomaneoForm(empresa_id, initial={'fecha': timezone.now().date()})

    return render(request, 'agricola/romaneo/nuevo.html', {'form': form})


@login_required
def romaneo_carga(request, pk):
    """Pantalla de carga de fardos. Si el romaneo ya no es borrador, muestra el detalle."""
    romaneo = _romaneo(request, pk)
    if not romaneo.editable:
        return redirect('agro_romaneo_detalle', pk=romaneo.pk)

    return render(request, 'agricola/romaneo/carga.html', {
        'romaneo': romaneo,
        'form': FardoForm(romaneo),
        'fardos': romaneo.fardos.select_related('clase'),
        'grupos': svc.estadistica_por_grupo(romaneo),
    })


@login_required
def romaneo_detalle(request, pk):
    romaneo = _romaneo(request, pk)
    return render(request, 'agricola/romaneo/detalle.html', {
        'romaneo': romaneo,
        'fardos': romaneo.fardos.select_related('clase'),
        'grupos': svc.estadistica_por_grupo(romaneo),
        # Lista plana y ordenada: recorrer fardo por fardo en la plantilla para juntarlas
        # obligaría a anidar dos bucles y dejaría el HTML dependiendo de `forloop.first`.
        'reclasificaciones': (ReclasificacionFardo.objects
                              .filter(fardo__romaneo=romaneo)
                              .select_related('fardo', 'clase_anterior', 'clase_nueva', 'usuario')
                              .order_by('fardo__numero_fardo', 'fecha')),
    })


@login_required
def romaneo_imprimir(request, pk):
    romaneo = _romaneo(request, pk)
    return render(request, 'agricola/romaneo/imprimir.html', {
        'romaneo': romaneo,
        'fardos': romaneo.fardos.select_related('clase'),
        'grupos': svc.estadistica_por_grupo(romaneo),
    })


# ---------------------------------------------------------------------------
# Fardos (HTMX)
# ---------------------------------------------------------------------------

def _panel_fardos(request, romaneo, aviso=''):
    """Detalle + totales + estadística, que es lo que cambia con cada alta o baja."""
    romaneo.refresh_from_db()
    html = render(request, 'agricola/romaneo/panel_fardos.html', {
        'romaneo': romaneo,
        'fardos': romaneo.fardos.select_related('clase'),
        'grupos': svc.estadistica_por_grupo(romaneo),
    }).content.decode('utf-8')
    return HttpResponse(aviso + html)


@login_required
def fardo_cotizar(request, pk):
    """Devuelve precio e importe mientras el operador tipea, antes de grabar el fardo."""
    romaneo = _romaneo(request, pk)
    clase = ClaseTabaco.objects.filter(pk=request.GET.get('clase') or 0,
                                       empresa_id=romaneo.empresa_id,
                                       variedad_id=romaneo.variedad_id).first()
    try:
        kilos = Decimal((request.GET.get('kilos') or '0').replace('.', '').replace(',', '.'))
    except InvalidOperation:
        kilos = Decimal('0')

    precio = importe = None
    if clase is not None:
        precio, importe = svc.cotizar_clase(romaneo, clase, kilos)

    return render(request, 'agricola/romaneo/cotizacion.html',
                  {'clase': clase, 'precio': precio, 'importe': importe, 'kilos': kilos})


@login_required
def fardo_agregar(request, pk):
    romaneo = _romaneo(request, pk)
    if request.method != 'POST':
        return HttpResponse(status=405)

    form = FardoForm(romaneo, request.POST)
    if not form.is_valid():
        primero = next(iter(form.errors.values()))[0]
        return _panel_fardos(request, romaneo, _aviso(primero))

    try:
        svc.agregar_fardo(romaneo, usuario=request.user, **form.cleaned_data)
    except ValidationError as e:
        return _panel_fardos(request, romaneo, _aviso(_mensaje_de(e)))

    return _panel_fardos(request, romaneo)


@login_required
def fardo_quitar(request, pk):
    if request.method != 'POST':
        return HttpResponse(status=405)
    fardo = get_object_or_404(FardoTabaco, pk=pk, romaneo__empresa_id=_empresa(request))
    romaneo = fardo.romaneo

    try:
        svc.quitar_fardo(fardo)
    except ValidationError as e:
        return _panel_fardos(request, romaneo, _aviso(_mensaje_de(e)))

    return _panel_fardos(request, romaneo)


@login_required
def clase_typeahead(request, pk):
    """Sugerencias de clase acotadas a la variedad del romaneo (patrón Typeahead + Lupa)."""
    romaneo = _romaneo(request, pk)
    q = (request.GET.get('q') or '').strip()

    clases = ClaseTabaco.objects.filter(empresa_id=romaneo.empresa_id,
                                        variedad_id=romaneo.variedad_id, activa=True)
    if q:
        clases = clases.filter(Q(detalle__istartswith=q) | Q(grupo__iexact=q))

    return render(request, 'agricola/romaneo/clase_sugerencias.html',
                  {'clases': clases[:30], 'romaneo': romaneo})


# ---------------------------------------------------------------------------
# Confirmación, anulación y reclasificación
# ---------------------------------------------------------------------------

@login_required
def romaneo_confirmar(request, pk):
    romaneo = _romaneo(request, pk)
    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        svc.confirmar_romaneo(romaneo, request.user)
    except ValidationError as e:
        return _panel_fardos(request, romaneo, _aviso(_mensaje_de(e)))

    respuesta = HttpResponse()
    respuesta['HX-Redirect'] = reverse('agro_romaneo_detalle', args=[romaneo.pk])
    return respuesta


@login_required
def romaneo_anular(request, pk):
    romaneo = _romaneo(request, pk)

    if request.method == 'POST':
        form = AnularRomaneoForm(request.POST)
        if form.is_valid():
            try:
                svc.anular_romaneo(romaneo, form.cleaned_data['motivo'], request.user)
            except ValidationError as e:
                form.add_error('motivo', _mensaje_de(e))
            else:
                return _trigger('reloadRomaneo', 'cerrarModal')
    else:
        form = AnularRomaneoForm()

    return render(request, 'agricola/romaneo/anular_modal.html',
                  {'form': form, 'romaneo': romaneo})


@login_required
def fardo_reclasificar(request, pk):
    fardo = get_object_or_404(FardoTabaco, pk=pk, romaneo__empresa_id=_empresa(request))

    if request.method == 'POST':
        form = ReclasificarForm(fardo, request.POST)
        if form.is_valid():
            try:
                svc.reclasificar_fardo(fardo, clase_nueva=form.cleaned_data['clase_nueva'],
                                       motivo=form.cleaned_data['motivo'], usuario=request.user)
            except ValidationError as e:
                form.add_error(None, _mensaje_de(e))
            else:
                return _trigger('reloadRomaneo', 'cerrarModal')
    else:
        form = ReclasificarForm(fardo)

    return render(request, 'agricola/romaneo/reclasificar_modal.html',
                  {'form': form, 'fardo': fardo})
