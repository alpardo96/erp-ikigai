"""Pantallas de la liquidación de compra de tabaco (Plan 083).

Las vistas no calculan nada: arman el formulario, delegan en `services/liquidacion.py` y muestran
el resultado. La previsualización usa la MISMA función `calcular()` que la confirmación, así que
lo que el operador ve antes de emitir es exactamente lo que se va a grabar.

REGLA INFLEXIBLE: todo queryset se acota por `session['empresa_id']`.
"""
import json

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

from .forms_romaneo import CONDIC_CHOICES, _estilar
from .models import LiquidacionTabaco, RomaneoTabaco
from .services import liquidacion as svc


# ---------------------------------------------------------------------------
# Formularios
# ---------------------------------------------------------------------------

class NuevaLiquidacionForm(forms.Form):
    """Cabecera. Los romaneos llegan como lista de ids desde la pantalla."""
    productor = forms.ModelChoiceField(queryset=ClienteProveedor.objects.none(),
                                       widget=forms.HiddenInput())
    fecha = forms.DateField(widget=DateInputHTML5(), label="Fecha")
    numero = forms.IntegerField(required=False, label="Número del comprobante",
                                widget=forms.NumberInput(attrs={'min': 1,
                                                                'placeholder': 'Se propone el siguiente'}))
    cai = forms.CharField(required=False, max_length=20, label="CAI")

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['productor'].queryset = ClienteProveedor.objects.filter(empresa_id=empresa_id)
        _estilar(self)


class AnularLiquidacionForm(forms.Form):
    motivo = forms.CharField(max_length=200, label="Motivo de la anulación",
                             widget=forms.TextInput(attrs={'placeholder': 'Obligatorio'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilar(self)


class FiltroLiquidacionesForm(forms.Form):
    q = forms.CharField(required=False, label="Buscar")
    productor = forms.ModelChoiceField(queryset=ClienteProveedor.objects.none(), required=False)
    letra = forms.ChoiceField(required=False, choices=[('', 'Todas')] + LiquidacionTabaco.LETRAS)
    estado = forms.ChoiceField(required=False,
                               choices=[('', 'Todos')] + LiquidacionTabaco.ESTADOS)
    condic = forms.ChoiceField(required=False, choices=[('', 'Todas')] + CONDIC_CHOICES)
    desde = forms.DateField(required=False, widget=DateInputHTML5())
    hasta = forms.DateField(required=False, widget=DateInputHTML5())

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['productor'].queryset = ClienteProveedor.objects.filter(empresa_id=empresa_id)
        _estilar(self)


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

def _empresa(request):
    return request.session.get('empresa_id')


def _liq(request, pk):
    return get_object_or_404(LiquidacionTabaco, pk=pk, empresa_id=_empresa(request))


def _mensaje_de(error):
    return ' '.join(error.messages) if hasattr(error, 'messages') else str(error)


def _trigger(*eventos):
    respuesta = HttpResponse()
    respuesta['HX-Trigger'] = json.dumps({e: True for e in eventos})
    return respuesta


# ---------------------------------------------------------------------------
# Listado
# ---------------------------------------------------------------------------

@login_required
def liquidacion_listado(request):
    filtros = FiltroLiquidacionesForm(_empresa(request), request.GET or None)
    return render(request, 'agricola/liquidacion/listado.html',
                  {'filtros': filtros, 'liquidaciones': _filtrar(request, filtros)})


@login_required
def liquidacion_grilla(request):
    filtros = FiltroLiquidacionesForm(_empresa(request), request.GET or None)
    return render(request, 'agricola/liquidacion/listado_filas.html',
                  {'liquidaciones': _filtrar(request, filtros)})


def _filtrar(request, filtros):
    qs = (LiquidacionTabaco.objects
          .filter(empresa_id=_empresa(request))
          .select_related('productor'))

    if not filtros.is_valid():
        return qs[:200]

    d = filtros.cleaned_data
    if d.get('q'):
        qs = qs.filter(Q(productor__razon_social__icontains=d['q']))
    if d.get('productor'):
        qs = qs.filter(productor=d['productor'])
    if d.get('letra'):
        qs = qs.filter(letra=d['letra'])
    if d.get('estado'):
        qs = qs.filter(estado=int(d['estado']))
    if d.get('condic'):
        qs = qs.filter(condic=int(d['condic']))
    if d.get('desde'):
        qs = qs.filter(fecha__gte=d['desde'])
    if d.get('hasta'):
        qs = qs.filter(fecha__lte=d['hasta'])

    return qs[:200]


# ---------------------------------------------------------------------------
# Emisión
# ---------------------------------------------------------------------------

@login_required
def liquidacion_nueva(request):
    """Elegir productor, ver sus romaneos pendientes y previsualizar antes de emitir."""
    empresa_id = _empresa(request)
    form = NuevaLiquidacionForm(empresa_id, request.POST or None,
                                initial={'fecha': timezone.now().date()})

    if request.method == 'POST' and form.is_valid():
        productor = form.cleaned_data['productor']
        ids = request.POST.getlist('romaneos')
        romaneos = list(svc.romaneos_liquidables(empresa_id, productor).filter(pk__in=ids))

        if not romaneos:
            return render(request, 'agricola/liquidacion/nueva.html',
                          {'form': form, 'error': "Elegí al menos un romaneo pendiente."})

        sucursal = Sucursal.objects.filter(empresa_id=empresa_id).first()
        try:
            # Preparar y confirmar van en UNA transacción. `preparar_liquidacion` ya deja los
            # romaneos tomados por el borrador; si después fallara la confirmación —falta el CAI,
            # falta una cuenta contable— y cada paso commiteara por su cuenta, quedaría un
            # borrador huérfano reteniendo esos romaneos: no volverían a figurar como pendientes
            # y no habría forma de liberarlos desde la pantalla.
            with transaction.atomic():
                liq = svc.preparar_liquidacion(
                    empresa=Empresa.objects.get(pk=empresa_id), sucursal=sucursal,
                    productor=productor, romaneos=romaneos, fecha=form.cleaned_data['fecha'],
                    usuario=request.user, numero=form.cleaned_data.get('numero'),
                    cai=form.cleaned_data.get('cai') or '')
                liq = svc.confirmar_liquidacion(liq, request.user)
        except ValidationError as e:
            return render(request, 'agricola/liquidacion/nueva.html',
                          {'form': form, 'error': _mensaje_de(e)})

        return redirect('agro_liquidacion_detalle', pk=liq.pk)

    return render(request, 'agricola/liquidacion/nueva.html', {'form': form})


@login_required
def liquidacion_pendientes(request):
    """Romaneos liquidables del productor elegido, con la previsualización de importes.

    El cálculo lo hace el SERVICIO, no la plantilla ni JavaScript: la fórmula tiene que vivir en
    un solo lugar o las dos versiones terminan discrepando.
    """
    empresa_id = _empresa(request)
    productor = ClienteProveedor.objects.filter(
        pk=request.GET.get('productor') or 0, empresa_id=empresa_id).first()

    if productor is None:
        return render(request, 'agricola/liquidacion/pendientes.html', {})

    romaneos = list(svc.romaneos_liquidables(empresa_id, productor))
    seleccionados = set(request.GET.getlist('romaneos'))
    neto = sum((r.total_importe for r in romaneos
                if not seleccionados or str(r.pk) in seleccionados), 0)

    calculo = None
    if neto:
        calculo = svc.calcular(empresa=Empresa.objects.get(pk=empresa_id), productor=productor,
                               neto=neto, fecha=timezone.now().date())

    return render(request, 'agricola/liquidacion/pendientes.html', {
        'productor': productor, 'romaneos': romaneos, 'seleccionados': seleccionados,
        'neto': neto, 'calculo': calculo,
    })


@login_required
def liquidacion_detalle(request, pk):
    liq = _liq(request, pk)
    return render(request, 'agricola/liquidacion/detalle.html', {
        'liquidacion': liq,
        'detalles': liq.detalles.select_related('clase', 'romaneo'),
        'retenciones': liq.retenciones_aplicadas.select_related('cuenta_contable'),
        'romaneos': liq.romaneos.all(),
    })


@login_required
def liquidacion_imprimir(request, pk):
    liq = _liq(request, pk)
    return render(request, 'agricola/liquidacion/imprimir.html', {
        'liquidacion': liq,
        'detalles': liq.detalles.select_related('clase', 'romaneo'),
        'retenciones': liq.retenciones_aplicadas.all(),
    })


@login_required
def liquidacion_anular(request, pk):
    liq = _liq(request, pk)

    if request.method == 'POST':
        form = AnularLiquidacionForm(request.POST)
        if form.is_valid():
            try:
                svc.anular_liquidacion(liq, form.cleaned_data['motivo'], request.user)
            except ValidationError as e:
                form.add_error('motivo', _mensaje_de(e))
            else:
                return _trigger('reloadLiquidacion', 'cerrarModal')
    else:
        form = AnularLiquidacionForm()

    return render(request, 'agricola/liquidacion/anular_modal.html',
                  {'form': form, 'liquidacion': liq})
