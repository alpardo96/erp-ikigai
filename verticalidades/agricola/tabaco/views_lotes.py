"""Pantallas de lotes, acondicionamiento, venta y margen (Plan 086 — Etapa 5).

Las vistas NO contienen reglas de negocio: validan permisos y empresa, arman el formulario y
delegan en `services/lotes.py`, `services/acondicionamiento.py` y `services/margen.py`. Es lo que
permite que mañana la misma lógica sirva para una API o una importación sin duplicarla.

REGLA INFLEXIBLE: todo queryset se acota por `session['empresa_id']`.
"""
import json
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from urllib.parse import quote

from .forms_lotes import (AbrirLoteForm, AcondicionamientoForm, AsignarVentaForm, CostoForm,
                          CoproductoForm, FiltroLotesForm, FiltroMargenForm, MotivoForm)
from .models import (Acondicionamiento, AcondicionamientoCoproducto, AcondicionamientoCosto,
                     FardoTabaco, LoteAcopio)
from .services import acondicionamiento as ac_svc
from .services import lotes as svc
from .services import margen as margen_svc
from .views_romaneo import _aviso, _mensaje_de


def _empresa(request):
    return request.session.get('empresa_id')


def _lote(request, pk):
    return get_object_or_404(
        LoteAcopio.objects.select_related('variedad', 'campania', 'sucursal', 'venta'),
        pk=pk, empresa_id=_empresa(request))


def _acond(request, pk):
    return get_object_or_404(
        Acondicionamiento.objects.select_related('lote', 'lote__variedad', 'proceso'),
        pk=pk, lote__empresa_id=_empresa(request))


def _trigger(*eventos):
    respuesta = HttpResponse()
    respuesta['HX-Trigger'] = json.dumps({e: True for e in eventos})
    return respuesta


def _volver_a(url):
    """Cierra el modal y recarga la pantalla desde el servidor.

    Se usa `HX-Redirect` y no un evento propio porque después de anular o de vincular una venta
    cambian el estado, los totales y la botonera entera: repintar sólo un panel dejaría media
    pantalla mostrando datos viejos.
    """
    respuesta = HttpResponse()
    respuesta['HX-Redirect'] = url
    return respuesta


# ---------------------------------------------------------------------------
# Listado
# ---------------------------------------------------------------------------

@login_required
def lote_listado(request):
    filtros = FiltroLotesForm(_empresa(request), request.GET or None)
    return render(request, 'agricola/lote/listado.html', {
        'filtros': filtros,
        'lotes': _filtrar(request, filtros),
    })


@login_required
def lote_grilla(request):
    """Sólo las filas: es lo que refresca HTMX al cambiar un filtro."""
    filtros = FiltroLotesForm(_empresa(request), request.GET or None)
    return render(request, 'agricola/lote/listado_filas.html',
                  {'lotes': _filtrar(request, filtros)})


def _filtrar(request, filtros):
    qs = (LoteAcopio.objects
          .filter(empresa_id=_empresa(request))
          .select_related('variedad', 'campania', 'sucursal', 'venta'))

    if not filtros.is_valid():
        return qs.order_by('-fecha', '-numero')[:200]

    datos = filtros.cleaned_data
    if datos.get('q'):
        texto = datos['q'].strip()
        filtro = Q(descripcion__icontains=texto)
        if texto.isdigit():
            filtro |= Q(numero=int(texto))
        qs = qs.filter(filtro)
    if datos.get('sucursal'):
        qs = qs.filter(sucursal=datos['sucursal'])
    if datos.get('variedad'):
        qs = qs.filter(variedad=datos['variedad'])
    if datos.get('campania'):
        qs = qs.filter(campania=datos['campania'])
    if datos.get('estado'):
        qs = qs.filter(estado=int(datos['estado']))
    if datos.get('condic'):
        # La condición es la del romaneo de origen: el lote no tiene una propia.
        qs = qs.filter(fardos__romaneo__condic=int(datos['condic'])).distinct()
    if datos.get('desde'):
        qs = qs.filter(fecha__gte=datos['desde'])
    if datos.get('hasta'):
        qs = qs.filter(fecha__lte=datos['hasta'])

    return qs.order_by('-fecha', '-numero')[:200]


# ---------------------------------------------------------------------------
# Alta y armado
# ---------------------------------------------------------------------------

@login_required
def lote_nuevo(request):
    empresa_id = _empresa(request)

    if request.method == 'POST':
        form = AbrirLoteForm(empresa_id, request.POST)
        if form.is_valid():
            from empresas.models import Empresa
            try:
                lote = svc.abrir_lote(
                    empresa=Empresa.objects.get(pk=empresa_id),
                    sucursal=form.cleaned_data['sucursal'],
                    campania=form.cleaned_data['campania'],
                    variedad=form.cleaned_data['variedad'],
                    fecha=form.cleaned_data['fecha'],
                    descripcion=form.cleaned_data['descripcion'],
                    observaciones=form.cleaned_data['observaciones'],
                    usuario=request.user)
                return redirect('agro_lote_detalle', pk=lote.pk)
            except ValidationError as error:
                form.add_error(None, _mensaje_de(error))
    else:
        form = AbrirLoteForm(empresa_id, initial={'fecha': timezone.localdate()})

    return render(request, 'agricola/lote/nuevo.html', {'form': form})


@login_required
def lote_detalle(request, pk):
    lote = _lote(request, pk)
    return render(request, 'agricola/lote/detalle.html', _contexto_detalle(request, lote))


def _contexto_detalle(request, lote):
    return {
        'lote': lote,
        'error': request.GET.get('error', ''),
        'fardos': (lote.fardos.select_related('clase', 'romaneo', 'romaneo__productor')
                   .order_by('romaneo__numero', 'numero_fardo')),
        'acondicionamientos': (lote.acondicionamientos.select_related('proceso')
                               .prefetch_related('costos', 'coproductos__producto')
                               .order_by('numero')),
        'form_acond': AcondicionamientoForm(lote.empresa_id,
                                            initial={'fecha': timezone.localdate()}),
        'form_venta': AsignarVentaForm(lote.empresa_id),
        'hay_cerrados': lote.acondicionamientos.filter(
            estado=Acondicionamiento.CERRADO).exists(),
    }


@login_required
def lote_panel_fardos(request, pk):
    """Sólo el panel de fardos: lo que refresca HTMX al agregar o quitar."""
    lote = _lote(request, pk)
    return render(request, 'agricola/lote/panel_fardos.html', _contexto_detalle(request, lote))


@login_required
def fardo_typeahead(request, pk):
    """Fardos comprados todavía sin lote, acotados a la variedad y sucursal del lote."""
    lote = _lote(request, pk)
    fardos = svc.fardos_disponibles(
        lote.empresa_id, variedad_id=lote.variedad_id, sucursal_id=lote.sucursal_id,
        texto=request.GET.get('q', ''))[:30]
    return render(request, 'agricola/lote/fardo_sugerencias.html',
                  {'fardos': fardos, 'lote': lote})


@login_required
def fardo_agregar(request, pk):
    lote = _lote(request, pk)
    aviso = ''
    try:
        fardo = get_object_or_404(FardoTabaco, pk=request.POST.get('fardo'),
                                  romaneo__empresa_id=lote.empresa_id)
        svc.agregar_fardo(lote, fardo, request.user)
    except ValidationError as error:
        aviso = _aviso(_mensaje_de(error))

    lote.refresh_from_db()
    respuesta = render(request, 'agricola/lote/panel_fardos.html',
                       _contexto_detalle(request, lote))
    if aviso:
        respuesta.content = aviso.encode() + respuesta.content
    return respuesta


@login_required
def fardo_quitar(request, pk, fardo_pk):
    lote = _lote(request, pk)
    aviso = ''
    try:
        fardo = get_object_or_404(FardoTabaco, pk=fardo_pk, lote=lote)
        svc.quitar_fardo(lote, fardo, request.user)
    except ValidationError as error:
        aviso = _aviso(_mensaje_de(error))

    lote.refresh_from_db()
    respuesta = render(request, 'agricola/lote/panel_fardos.html',
                       _contexto_detalle(request, lote))
    if aviso:
        respuesta.content = aviso.encode() + respuesta.content
    return respuesta


@login_required
def lote_armar(request, pk):
    """Armar llega por un enlace normal, no por HTMX: en el error se vuelve al detalle entero.

    Devolver acá un fragmento reemplazaría la página completa por un pedazo de tabla. El motivo
    viaja por `?error=` y lo muestra el detalle.
    """
    lote = _lote(request, pk)
    try:
        svc.armar_lote(lote, request.user)
    except ValidationError as error:
        destino = reverse('agro_lote_detalle', args=[lote.pk])
        return redirect(f"{destino}?error={quote(_mensaje_de(error))}")
    return redirect('agro_lote_detalle', pk=lote.pk)


@login_required
def lote_anular(request, pk):
    lote = _lote(request, pk)

    if request.method == 'POST':
        form = MotivoForm(request.POST)
        if form.is_valid():
            try:
                svc.anular_lote(lote, form.cleaned_data['motivo'], request.user)
                return _volver_a(reverse('agro_lote_detalle', args=[lote.pk]))
            except ValidationError as error:
                form.add_error('motivo', _mensaje_de(error))
    else:
        form = MotivoForm()

    return render(request, 'agricola/lote/anular_modal.html', {'lote': lote, 'form': form})


# ---------------------------------------------------------------------------
# Venta
# ---------------------------------------------------------------------------

@login_required
def lote_venta(request, pk):
    """Vincula la venta ya emitida. NO la crea: eso es el circuito de `facturacion`."""
    lote = _lote(request, pk)

    if request.method == 'POST':
        form = AsignarVentaForm(lote.empresa_id, request.POST)
        if form.is_valid():
            try:
                svc.asignar_venta(lote, form.cleaned_data['venta'], request.user)
                return _volver_a(reverse('agro_lote_detalle', args=[lote.pk]))
            except ValidationError as error:
                form.add_error(None, _mensaje_de(error))
    else:
        form = AsignarVentaForm(lote.empresa_id)

    return render(request, 'agricola/lote/venta_modal.html', {
        'lote': lote, 'form': form, 'ventas': _ventas_candidatas(lote)})


def _ventas_candidatas(lote):
    """Ventas de la empresa que facturan el producto de la variedad y no tienen lote asignado."""
    from facturacion.models import Venta

    if not lote.variedad.producto_id:
        return Venta.objects.none()

    return (Venta.objects
            .filter(empresa_id=lote.empresa_id,
                    items__producto_id=lote.variedad.producto_id,
                    lotes_tabaco__isnull=True)
            .select_related('cliente', 'tipo')
            .distinct()
            .order_by('-fecha', '-numero')[:50])


@login_required
def lote_venta_quitar(request, pk):
    lote = _lote(request, pk)
    try:
        svc.quitar_venta(lote, request.user)
    except ValidationError as error:
        destino = reverse('agro_lote_detalle', args=[lote.pk])
        return redirect(f"{destino}?error={quote(_mensaje_de(error))}")
    return redirect('agro_lote_detalle', pk=lote.pk)


# ---------------------------------------------------------------------------
# Acondicionamiento
# ---------------------------------------------------------------------------

@login_required
def acond_nuevo(request, pk):
    lote = _lote(request, pk)

    if request.method == 'POST':
        form = AcondicionamientoForm(lote.empresa_id, request.POST)
        if form.is_valid():
            try:
                acond = ac_svc.abrir_acondicionamiento(
                    lote, proceso=form.cleaned_data['proceso'],
                    fecha=form.cleaned_data['fecha'],
                    kilos_entrada=form.cleaned_data['kilos_entrada'],
                    kilos_salida=form.cleaned_data['kilos_salida'],
                    motivo_merma=form.cleaned_data['motivo_merma'],
                    observaciones=form.cleaned_data['observaciones'],
                    usuario=request.user)
                return redirect('agro_acond_detalle', pk=acond.pk)
            except ValidationError as error:
                form.add_error(None, _mensaje_de(error))
    else:
        form = AcondicionamientoForm(lote.empresa_id, initial={'fecha': timezone.localdate()})

    return render(request, 'agricola/acond/nuevo.html', {'lote': lote, 'form': form})


@login_required
def acond_detalle(request, pk):
    acond = _acond(request, pk)
    return render(request, 'agricola/acond/detalle.html', _contexto_acond(request, acond))


def _contexto_acond(request, acond):
    empresa_id = acond.lote.empresa_id
    return {
        'acond': acond,
        'lote': acond.lote,
        'error': request.GET.get('error', ''),
        'costos': acond.costos.select_related('compra').order_by('id'),
        'coproductos': acond.coproductos.select_related('producto').order_by('id'),
        'form_costo': CostoForm(empresa_id),
        'form_coproducto': CoproductoForm(empresa_id),
    }


@login_required
def acond_panel(request, pk):
    """Sólo el panel de líneas: lo que refresca HTMX al cargar un costo o un coproducto."""
    acond = _acond(request, pk)
    return render(request, 'agricola/acond/panel.html', _contexto_acond(request, acond))


def _panel_con_aviso(request, acond, error=None):
    acond.refresh_from_db()
    respuesta = render(request, 'agricola/acond/panel.html', _contexto_acond(request, acond))
    if error is not None:
        respuesta.content = _aviso(_mensaje_de(error)).encode() + respuesta.content
    return respuesta


@login_required
def acond_costo_agregar(request, pk):
    acond = _acond(request, pk)
    form = CostoForm(acond.lote.empresa_id, request.POST)
    if not form.is_valid():
        return _panel_con_aviso(request, acond, ValidationError(
            "Revisá el concepto y el importe del costo."))
    try:
        ac_svc.agregar_costo(acond, concepto=form.cleaned_data['concepto'],
                             importe=form.cleaned_data['importe'],
                             compra=form.cleaned_data['compra'])
    except ValidationError as error:
        return _panel_con_aviso(request, acond, error)
    return _panel_con_aviso(request, acond)


@login_required
def acond_costo_quitar(request, pk, linea_pk):
    acond = _acond(request, pk)
    linea = get_object_or_404(AcondicionamientoCosto, pk=linea_pk, acondicionamiento=acond)
    try:
        ac_svc.quitar_costo(linea)
    except ValidationError as error:
        return _panel_con_aviso(request, acond, error)
    return _panel_con_aviso(request, acond)


@login_required
def acond_coproducto_agregar(request, pk):
    acond = _acond(request, pk)
    form = CoproductoForm(acond.lote.empresa_id, request.POST)
    if not form.is_valid():
        return _panel_con_aviso(request, acond, ValidationError(
            "Elegí un producto y cargá los kilos."))
    try:
        ac_svc.agregar_coproducto(acond, producto=form.cleaned_data['producto'],
                                  kilos=form.cleaned_data['kilos'],
                                  valor_estimado=form.cleaned_data['valor_estimado'] or Decimal(0),
                                  observaciones=form.cleaned_data['observaciones'])
    except ValidationError as error:
        return _panel_con_aviso(request, acond, error)
    return _panel_con_aviso(request, acond)


@login_required
def acond_coproducto_quitar(request, pk, linea_pk):
    acond = _acond(request, pk)
    linea = get_object_or_404(AcondicionamientoCoproducto, pk=linea_pk, acondicionamiento=acond)
    try:
        ac_svc.quitar_coproducto(linea)
    except ValidationError as error:
        return _panel_con_aviso(request, acond, error)
    return _panel_con_aviso(request, acond)


@login_required
def acond_cerrar(request, pk):
    acond = _acond(request, pk)
    try:
        ac_svc.cerrar_acondicionamiento(acond, request.user)
    except ValidationError as error:
        destino = reverse('agro_acond_detalle', args=[acond.pk])
        return redirect(f"{destino}?error={quote(_mensaje_de(error))}")
    return redirect('agro_acond_detalle', pk=acond.pk)


@login_required
def acond_anular(request, pk):
    acond = _acond(request, pk)

    if request.method == 'POST':
        form = MotivoForm(request.POST)
        if form.is_valid():
            try:
                ac_svc.anular_acondicionamiento(acond, form.cleaned_data['motivo'], request.user)
                return _volver_a(reverse('agro_acond_detalle', args=[acond.pk]))
            except ValidationError as error:
                form.add_error('motivo', _mensaje_de(error))
    else:
        form = MotivoForm()

    return render(request, 'agricola/acond/anular_modal.html', {'acond': acond, 'form': form})


@login_required
def producto_typeahead(request):
    """Productos de la empresa para elegir el coproducto (palo, descarte)."""
    from productos.models import Producto

    texto = (request.GET.get('q') or '').strip()
    qs = Producto.objects.filter(empresa_id=_empresa(request))
    if texto:
        filtro = Q(detalle__icontains=texto)
        if texto.isdigit():
            filtro |= Q(codigo=int(texto))
        qs = qs.filter(filtro)
    return render(request, 'agricola/acond/producto_sugerencias.html',
                  {'productos': qs.order_by('detalle')[:30]})


# ---------------------------------------------------------------------------
# Margen
# ---------------------------------------------------------------------------

@login_required
def margen_listado(request):
    empresa_id = _empresa(request)
    filtros = FiltroMargenForm(empresa_id, request.GET or None)
    filas = _filas_margen(empresa_id, filtros)
    return render(request, 'agricola/margen/listado.html', {
        'filtros': filtros, 'filas': filas, 'totales': margen_svc.totales(filas)})


@login_required
def margen_grilla(request):
    empresa_id = _empresa(request)
    filtros = FiltroMargenForm(empresa_id, request.GET or None)
    filas = _filas_margen(empresa_id, filtros)
    return render(request, 'agricola/margen/listado_filas.html',
                  {'filas': filas, 'totales': margen_svc.totales(filas)})


def _filas_margen(empresa_id, filtros):
    datos = filtros.cleaned_data if filtros.is_valid() else {}
    return margen_svc.margen_por_lote(
        empresa_id,
        campania_id=getattr(datos.get('campania'), 'pk', None),
        variedad_id=getattr(datos.get('variedad'), 'pk', None),
        sucursal_id=getattr(datos.get('sucursal'), 'pk', None),
        condic=int(datos['condic']) if datos.get('condic') else None,
        solo_vendidos=bool(datos.get('solo_vendidos')))


@login_required
def margen_del_lote(request, pk):
    """El entregable de la etapa: margen por fardo, con el resumen por clase."""
    lote = _lote(request, pk)
    return render(request, 'agricola/margen/detalle.html', {
        'lote': lote,
        'filas': margen_svc.margen_por_fardo(lote),
        'por_clase': margen_svc.resumen_por_clase(lote),
    })
