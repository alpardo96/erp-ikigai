"""Filtros de los reportes del acopio (Plan 087 — Etapa 6).

TODOS OFRECEN `condic`, que es regla del proyecto para cualquier pantalla con importes. La
diferencia está en el valor inicial: los reportes OFICIALES arrancan en **Real**, porque lo que se
declara es la lente fiscal (`condic in (1, 3)`); los gerenciales arrancan en Todas, porque para
analizar la gestión interesa también lo presupuestado.
"""
from django import forms

from core.forms import DateInputHTML5
from empresas.models import Sucursal
from facturacion.models import ClienteProveedor
from verticalidades.agricola.core_agricola.models import Campania

from .forms_romaneo import CONDIC_CHOICES, _estilar
from .models import TipoRetencionTabaco, VariedadTabaco


class _FiltroBase(forms.Form):
    """Campos comunes. La empresa acota TODOS los combos: regla inflexible del proyecto."""

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa_id = empresa_id
        if 'sucursal' in self.fields:
            self.fields['sucursal'].queryset = Sucursal.objects.filter(empresa_id=empresa_id)
        if 'variedad' in self.fields:
            self.fields['variedad'].queryset = VariedadTabaco.objects.filter(empresa_id=empresa_id)
        if 'campania' in self.fields:
            self.fields['campania'].queryset = Campania.objects.filter(empresa_id=empresa_id)
        if 'productor' in self.fields:
            self.fields['productor'].queryset = ClienteProveedor.objects.filter(
                empresa_id=empresa_id, tipo_entidad=2)
        _estilar(self)

    def valor(self, nombre):
        """Valor limpio o `None`. Evita repetir el `cleaned_data.get(...) if is_valid()`."""
        if not self.is_valid():
            return None
        return self.cleaned_data.get(nombre) or None

    def pk_de(self, nombre):
        return getattr(self.valor(nombre), 'pk', None)

    def condic(self):
        valor = self.valor('condic')
        return int(valor) if valor else None


class FiltroFETForm(_FiltroBase):
    """Planilla FET. Arranca en Real: es una declaración, no un análisis."""
    desde = forms.DateField(required=False, widget=DateInputHTML5())
    hasta = forms.DateField(required=False, widget=DateInputHTML5())
    campania = forms.ModelChoiceField(queryset=Campania.objects.none(), required=False)
    variedad = forms.ModelChoiceField(queryset=VariedadTabaco.objects.none(), required=False)
    productor = forms.ModelChoiceField(queryset=ClienteProveedor.objects.none(), required=False)
    condic = forms.ChoiceField(required=False, initial='1',
                               choices=[('', 'Todas')] + CONDIC_CHOICES)


class FiltroAcopioForm(_FiltroBase):
    """Resumen por variedad y clase."""
    desde = forms.DateField(required=False, widget=DateInputHTML5())
    hasta = forms.DateField(required=False, widget=DateInputHTML5())
    campania = forms.ModelChoiceField(queryset=Campania.objects.none(), required=False)
    variedad = forms.ModelChoiceField(queryset=VariedadTabaco.objects.none(), required=False)
    sucursal = forms.ModelChoiceField(queryset=Sucursal.objects.none(), required=False)
    condic = forms.ChoiceField(required=False, initial='1',
                               choices=[('', 'Todas')] + CONDIC_CHOICES)


class FiltroExistenciasForm(_FiltroBase):
    """DDJJ de existencias. La FECHA DE CORTE es obligatoria: es el sentido del reporte."""
    fecha = forms.DateField(widget=DateInputHTML5(), label="Existencias al")
    sucursal = forms.ModelChoiceField(queryset=Sucursal.objects.none(), required=False)
    variedad = forms.ModelChoiceField(queryset=VariedadTabaco.objects.none(), required=False)
    condic = forms.ChoiceField(required=False, initial='1',
                               choices=[('', 'Todas')] + CONDIC_CHOICES)


class FiltroRetencionesForm(_FiltroBase):
    """Libro de retenciones practicadas."""
    desde = forms.DateField(required=False, widget=DateInputHTML5())
    hasta = forms.DateField(required=False, widget=DateInputHTML5())
    codigo = forms.ChoiceField(required=False, choices=[('', 'Todos')], label="Concepto")
    productor = forms.ModelChoiceField(queryset=ClienteProveedor.objects.none(), required=False)
    condic = forms.ChoiceField(required=False, initial='1',
                               choices=[('', 'Todas')] + CONDIC_CHOICES)

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(empresa_id, *args, **kwargs)
        # Los conceptos salen del MAESTRO, no de una lista fija: es extensible por diseño.
        codigos = (TipoRetencionTabaco.objects
                   .filter(empresa_id=empresa_id)
                   .values_list('codigo', 'detalle')
                   .order_by('codigo').distinct())
        self.fields['codigo'].choices = [('', 'Todos')] + list(codigos)


class FiltroTableroForm(_FiltroBase):
    """Tableros de margen. Arrancan en Todas: para gestionar interesa también lo presupuestado."""
    AGRUPACIONES = [
        ('campania', 'Por campaña'),
        ('variedad', 'Por variedad'),
        ('productor', 'Por productor'),
        ('clase', 'Por clase de tabaco'),
    ]

    agrupar = forms.ChoiceField(choices=AGRUPACIONES, initial='campania', label="Agrupar")
    campania = forms.ModelChoiceField(queryset=Campania.objects.none(), required=False)
    variedad = forms.ModelChoiceField(queryset=VariedadTabaco.objects.none(), required=False)
    sucursal = forms.ModelChoiceField(queryset=Sucursal.objects.none(), required=False)
    condic = forms.ChoiceField(required=False, choices=[('', 'Todas')] + CONDIC_CHOICES)
    solo_vendidos = forms.BooleanField(required=False, label="Sólo lotes vendidos")

    def agrupacion(self):
        return self.valor('agrupar') or 'campania'
