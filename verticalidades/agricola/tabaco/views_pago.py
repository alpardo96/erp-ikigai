"""Pantalla de pago al productor (Plan 084).

Es una pantalla PROPIA de la verticalidad y no una modificación del alta de Orden de Pago del
core: aquel endpoint es un API JSON con un frontend complejo que sólo entiende de `Compra`.

ALCANCE DE LOS MEDIOS DE PAGO: efectivo, transferencia, billetera y otros. Los CHEQUES quedan
fuera de esta etapa —propios y de terceros arrastran vencimiento, cuenta bancaria, estado en
cartera y conciliación—, y se avisa explícitamente en pantalla en vez de dejar que el operador
cargue algo a medias.
"""
import json
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from core.forms import DateInputHTML5
from empresas.models import Empresa, Sucursal
from facturacion.models import ClienteProveedor
from tesoreria.models import MedioPago, MovimientoCajaDetalle, OrdenPago

from .forms_romaneo import CONDIC_CHOICES, _estilar
from .models import LiquidacionPago, RetencionPago
from .services import pago as svc

# Categorías que esta pantalla sabe manejar. Los cheques (CHQ) exigen vencimiento, cartera y
# conciliación: se cargan por tesorería.
CATEGORIAS_SOPORTADAS = ('EFE', 'TRA', 'DIG', 'OTR')


class NuevoPagoForm(forms.Form):
    productor = forms.ModelChoiceField(queryset=ClienteProveedor.objects.none(),
                                       widget=forms.HiddenInput())
    fecha = forms.DateField(widget=DateInputHTML5(), label="Fecha")
    condic = forms.ChoiceField(choices=CONDIC_CHOICES, initial=1, label="Condición")
    observaciones = forms.CharField(required=False, max_length=200, label="Observaciones")

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['productor'].queryset = ClienteProveedor.objects.filter(empresa_id=empresa_id)
        _estilar(self)

    def clean_condic(self):
        return int(self.cleaned_data['condic'])


class AnularPagoForm(forms.Form):
    motivo = forms.CharField(max_length=200, label="Motivo de la anulación",
                             widget=forms.TextInput(attrs={'placeholder': 'Obligatorio'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilar(self)


class FiltroPagosForm(forms.Form):
    productor = forms.ModelChoiceField(queryset=ClienteProveedor.objects.none(), required=False)
    condic = forms.ChoiceField(required=False, choices=[('', 'Todas')] + CONDIC_CHOICES)
    desde = forms.DateField(required=False, widget=DateInputHTML5())
    hasta = forms.DateField(required=False, widget=DateInputHTML5())

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['productor'].queryset = ClienteProveedor.objects.filter(empresa_id=empresa_id)
        _estilar(self)


def _empresa(request):
    return request.session.get('empresa_id')


def _mensaje_de(error):
    return ' '.join(error.messages) if hasattr(error, 'messages') else str(error)


def _trigger(*eventos):
    r = HttpResponse()
    r['HX-Trigger'] = json.dumps({e: True for e in eventos})
    return r


def _decimal(texto):
    """Convierte un importe en formato es-AR. Devuelve 0 si no se puede."""
    try:
        return Decimal((texto or '0').replace('.', '').replace(',', '.'))
    except InvalidOperation:
        return Decimal('0')


def _medios_disponibles(empresa_id):
    return (MedioPago.objects
            .filter(empresa_id=empresa_id, activo=True,
                    categoria__in=CATEGORIAS_SOPORTADAS)
            .order_by('categoria', 'nombre'))


# ---------------------------------------------------------------------------
# Listado
# ---------------------------------------------------------------------------

@login_required
def pago_listado(request):
    filtros = FiltroPagosForm(_empresa(request), request.GET or None)
    return render(request, 'agricola/pago/listado.html',
                  {'filtros': filtros, 'pagos': _filtrar(request, filtros)})


@login_required
def pago_grilla(request):
    filtros = FiltroPagosForm(_empresa(request), request.GET or None)
    return render(request, 'agricola/pago/listado_filas.html',
                  {'pagos': _filtrar(request, filtros)})


def _filtrar(request, filtros):
    """Sólo las OP que cancelaron liquidaciones de tabaco."""
    ids = (LiquidacionPago.objects
           .filter(liquidacion__empresa_id=_empresa(request))
           .values_list('orden_pago_id', flat=True))
    qs = (OrdenPago.objects
          .filter(pk__in=ids, empresa_id=_empresa(request))
          .select_related('proveedor'))

    if filtros.is_valid():
        d = filtros.cleaned_data
        if d.get('productor'):
            qs = qs.filter(proveedor=d['productor'])
        if d.get('condic'):
            qs = qs.filter(condic=int(d['condic']))
        if d.get('desde'):
            qs = qs.filter(fecha__gte=d['desde'])
        if d.get('hasta'):
            qs = qs.filter(fecha__lte=d['hasta'])

    return qs.order_by('-fecha', '-numero')[:200]


# ---------------------------------------------------------------------------
# Emisión
# ---------------------------------------------------------------------------

@login_required
def pago_nuevo(request):
    empresa_id = _empresa(request)
    form = NuevoPagoForm(empresa_id, request.POST or None,
                         initial={'fecha': timezone.now().date()})
    contexto = {'form': form, 'medios': _medios_disponibles(empresa_id)}

    if request.method == 'POST' and form.is_valid():
        productor = form.cleaned_data['productor']
        ids = request.POST.getlist('liquidaciones')
        liquidaciones = list(
            svc.liquidaciones_pendientes(empresa_id, productor).filter(pk__in=ids))

        if not liquidaciones:
            contexto['error'] = "Elegí al menos una liquidación con saldo."
            return render(request, 'agricola/pago/nuevo.html', contexto)

        medios = _leer_medios(request, empresa_id)
        if not medios:
            contexto['error'] = "Cargá al menos un medio de pago con importe."
            return render(request, 'agricola/pago/nuevo.html', contexto)

        try:
            with transaction.atomic():
                op = svc.pagar_liquidaciones(
                    empresa=Empresa.objects.get(pk=empresa_id),
                    sucursal=Sucursal.objects.filter(empresa_id=empresa_id).first(),
                    productor=productor, liquidaciones=liquidaciones, medios=medios,
                    fecha=form.cleaned_data['fecha'], usuario=request.user,
                    condic=form.cleaned_data['condic'],
                    observaciones=form.cleaned_data.get('observaciones') or '')
        except ValidationError as e:
            contexto['error'] = _mensaje_de(e)
            return render(request, 'agricola/pago/nuevo.html', contexto)

        return redirect('agro_pago_detalle', pk=op.pk)

    return render(request, 'agricola/pago/nuevo.html', contexto)


def _leer_medios(request, empresa_id):
    """Lee las filas `medio_pago[]` / `importe[]` de la pantalla."""
    medios_id = request.POST.getlist('medio_pago')
    importes = request.POST.getlist('importe')
    disponibles = {m.pk: m for m in _medios_disponibles(empresa_id)}

    filas = []
    for mid, imp in zip(medios_id, importes):
        importe = _decimal(imp)
        if not mid or importe <= 0:
            continue
        medio = disponibles.get(int(mid))
        if medio is None:
            continue
        filas.append({'medio_pago': medio, 'importe': importe})
    return filas


@login_required
def pago_pendientes(request):
    """Liquidaciones con saldo del productor + previsualización de la retención.

    El cálculo lo hace el SERVICIO: es la misma función que usa el pago real, así que lo que el
    operador ve antes de confirmar es exactamente lo que se va a grabar.
    """
    empresa_id = _empresa(request)
    productor = ClienteProveedor.objects.filter(
        pk=request.GET.get('productor') or 0, empresa_id=empresa_id).first()

    if productor is None:
        return render(request, 'agricola/pago/pendientes.html', {})

    liquidaciones = list(svc.liquidaciones_pendientes(empresa_id, productor))
    elegidas = set(request.GET.getlist('liquidaciones'))
    seleccionadas = [l for l in liquidaciones
                     if not elegidas or str(l.pk) in elegidas]

    base = sum((l.neto for l in seleccionadas), Decimal('0'))
    saldo = sum((l.saldo for l in seleccionadas), Decimal('0'))

    try:
        fecha = timezone.datetime.strptime(request.GET.get('fecha', ''), '%Y-%m-%d').date()
    except ValueError:
        fecha = timezone.now().date()

    retencion = None
    if base:
        retencion = svc.calcular_ganancias(empresa=Empresa.objects.get(pk=empresa_id),
                                           productor=productor, base_del_pago=base, fecha=fecha)

    return render(request, 'agricola/pago/pendientes.html', {
        'productor': productor, 'liquidaciones': liquidaciones, 'elegidas': elegidas,
        'base': base, 'saldo': saldo, 'retencion': retencion,
        'a_entregar': saldo - (retencion['importe'] if retencion else Decimal('0')),
    })


@login_required
def pago_detalle(request, pk):
    op = get_object_or_404(OrdenPago, pk=pk, empresa_id=_empresa(request))
    return render(request, 'agricola/pago/detalle.html', {
        'op': op,
        'imputaciones': (LiquidacionPago.objects.filter(orden_pago=op)
                         .select_related('liquidacion')),
        'retenciones': RetencionPago.objects.filter(orden_pago=op),
        # `MovimientoCaja.orden_pago` no declara `related_name`, así que se consulta directo.
        'detalles': MovimientoCajaDetalle.objects.filter(
            movimiento_caja__orden_pago=op).select_related('medio_pago'),
    })


@login_required
def pago_certificado(request, pk):
    cert = get_object_or_404(RetencionPago, pk=pk, empresa_id=_empresa(request))
    return render(request, 'agricola/pago/certificado.html', {'cert': cert})


@login_required
def pago_anular(request, pk):
    op = get_object_or_404(OrdenPago, pk=pk, empresa_id=_empresa(request))

    if request.method == 'POST':
        form = AnularPagoForm(request.POST)
        if form.is_valid():
            try:
                svc.anular_pago(op, form.cleaned_data['motivo'], request.user)
            except ValidationError as e:
                form.add_error('motivo', _mensaje_de(e))
            else:
                return _trigger('reloadPago', 'cerrarModal')
    else:
        form = AnularPagoForm()

    return render(request, 'agricola/pago/anular_modal.html', {'form': form, 'op': op})


# ---------------------------------------------------------------------------
# Conciliación de stock (Plan 085)
# ---------------------------------------------------------------------------

@login_required
def stock_conciliacion(request):
    """Kilos del acopio contra el stock del ERP, por variedad y sucursal.

    La diferencia debe ser cero. Si no lo es, `recalcular_stock` la corrige —el stock es un valor
    derivado y autorreparable—; lo que este reporte aporta es DETECTARLA.
    """
    from .services.stock import conciliar

    empresa_id = _empresa(request)
    sucursal_id = request.GET.get('sucursal') or None
    filas = conciliar(empresa_id, int(sucursal_id) if sucursal_id else None)

    return render(request, 'agricola/stock/conciliacion.html', {
        'filas': filas,
        'sucursales': Sucursal.objects.filter(empresa_id=empresa_id).order_by('nombre'),
        'sucursal_id': sucursal_id,
        'hay_diferencias': any(f['diferencia'] for f in filas),
        'hay_sin_producto': any(f['sin_producto'] for f in filas),
    })


@login_required
def stock_recalcular(request):
    """Fuerza el recálculo de las variedades con producto asignado y vuelve a conciliar."""
    if request.method != 'POST':
        return HttpResponse(status=405)

    from productos.models import StockSucursal
    from productos.services.stock_service import recalcular_stock

    from .models import VariedadTabaco

    empresa_id = _empresa(request)
    for variedad in VariedadTabaco.objects.filter(empresa_id=empresa_id,
                                                  producto__isnull=False):
        for suc_id in (StockSucursal.objects
                       .filter(producto_id=variedad.producto_id)
                       .values_list('sucursal_id', flat=True)):
            recalcular_stock(variedad.producto_id, suc_id)

    return redirect('agro_stock_conciliacion')
