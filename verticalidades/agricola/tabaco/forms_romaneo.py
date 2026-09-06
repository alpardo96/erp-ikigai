"""Formularios del romaneo (Plan 082).

Se separan de `forms.py` —que es de maestros— porque son de otra naturaleza: acá no se administra
un catálogo, se captura una operación, y las validaciones que importan (clase compatible con la
variedad, estado del documento) viven en el servicio, no en el formulario.
"""
from django import forms

from core.forms import DateInputHTML5, DecimalARField
from facturacion.models import ClienteProveedor
from verticalidades.agricola.core_agricola.models import Campania

from .models import ClaseTabaco, RomaneoTabaco, VariedadTabaco

INPUT_CLASS = ("w-full rounded-xl border-gray-200 text-sm "
               "focus:ring-indigo-500 focus:border-indigo-500 transition-all")
CHECK_CLASS = "h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"

# El combo de `condic` no ofrece 5/6/7: esos los genera el sistema y no se cargan a mano.
CONDIC_CHOICES = [(1, 'Real'), (2, 'Presupuestado'), (3, 'Ajuste'), (4, 'Auditoría')]


def _estilar(form):
    for _nombre, field in form.fields.items():
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs['class'] = CHECK_CLASS
        else:
            actual = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{actual} {INPUT_CLASS}".strip()


class AbrirRomaneoForm(forms.Form):
    """Cabecera del romaneo. Sólo se usa para ABRIRLO; después la cabecera queda fija.

    El productor se elige con Typeahead + Lupa: el campo visible es un texto y este `productor`
    oculto recibe el id que despacha el buscador.
    """
    productor = forms.ModelChoiceField(queryset=ClienteProveedor.objects.none(),
                                       widget=forms.HiddenInput())
    variedad = forms.ModelChoiceField(queryset=VariedadTabaco.objects.none(), label="Variedad")
    campania = forms.ModelChoiceField(queryset=Campania.objects.none(), label="Campaña")
    fecha = forms.DateField(widget=DateInputHTML5(), label="Fecha")
    transporte = forms.CharField(required=False, max_length=120, label="Transporte / Vehículo",
                                 widget=forms.TextInput(attrs={'placeholder': 'Camión, patente'}))
    remito = forms.CharField(required=False, max_length=40, label="Remito o guía")
    condic = forms.ChoiceField(choices=CONDIC_CHOICES, initial=1, label="Condición")
    observaciones = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa_id = empresa_id
        self.fields['productor'].queryset = ClienteProveedor.objects.filter(empresa_id=empresa_id)
        self.fields['variedad'].queryset = VariedadTabaco.objects.filter(
            empresa_id=empresa_id, activa=True)
        self.fields['campania'].queryset = Campania.objects.filter(
            empresa_id=empresa_id, activa=True, estado=Campania.ABIERTA)
        _estilar(self)

    def clean_condic(self):
        return int(self.cleaned_data['condic'])


class FardoForm(forms.Form):
    """Alta de un fardo. La clase llega por id desde el typeahead."""
    clase = forms.ModelChoiceField(queryset=ClaseTabaco.objects.none(), widget=forms.HiddenInput())
    kilos = DecimalARField(max_digits=12, decimal_places=2, label="Kilos",
                           widget=forms.TextInput(attrs={'class': 'fInputAR',
                                                         'placeholder': '0,00'}))
    etiqueta = forms.CharField(required=False, max_length=40, label="Etiqueta",
                               widget=forms.TextInput(attrs={'placeholder': 'Opcional'}))
    adicional = DecimalARField(max_digits=15, decimal_places=2, required=False, initial=0,
                               label="Adicional",
                               widget=forms.TextInput(attrs={'class': 'fInputAR',
                                                             'placeholder': '0,00'}))

    def __init__(self, romaneo=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.romaneo = romaneo
        # El combo se acota a la variedad del romaneo: es la primera barrera contra clasificar
        # Burley con una clase de Virginia. El servicio lo vuelve a validar igual.
        if romaneo is not None:
            self.fields['clase'].queryset = ClaseTabaco.objects.filter(
                empresa_id=romaneo.empresa_id, variedad_id=romaneo.variedad_id, activa=True)
        _estilar(self)

    def clean_kilos(self):
        kilos = self.cleaned_data.get('kilos')
        if kilos is not None and kilos <= 0:
            raise forms.ValidationError("Los kilos deben ser mayores que cero.")
        return kilos


class ReclasificarForm(forms.Form):
    clase_nueva = forms.ModelChoiceField(queryset=ClaseTabaco.objects.none(), label="Clase nueva")
    motivo = forms.CharField(max_length=200, label="Motivo",
                             widget=forms.TextInput(attrs={'placeholder': 'Por qué se reclasifica'}))

    def __init__(self, fardo=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fardo = fardo
        if fardo is not None:
            self.fields['clase_nueva'].queryset = ClaseTabaco.objects.filter(
                empresa_id=fardo.romaneo.empresa_id,
                variedad_id=fardo.romaneo.variedad_id, activa=True).exclude(pk=fardo.clase_id)
        _estilar(self)


class AnularRomaneoForm(forms.Form):
    motivo = forms.CharField(max_length=200, label="Motivo de la anulación",
                             widget=forms.TextInput(attrs={'placeholder': 'Obligatorio'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilar(self)


class FiltroRomaneosForm(forms.Form):
    """Filtros del listado. Incluye `condic`, que el proyecto exige en todo listado con importes."""
    q = forms.CharField(required=False, label="Buscar")
    productor = forms.ModelChoiceField(queryset=ClienteProveedor.objects.none(), required=False)
    variedad = forms.ModelChoiceField(queryset=VariedadTabaco.objects.none(), required=False)
    campania = forms.ModelChoiceField(queryset=Campania.objects.none(), required=False)
    estado = forms.ChoiceField(required=False,
                               choices=[('', 'Todos')] + RomaneoTabaco.ESTADOS)
    condic = forms.ChoiceField(required=False, choices=[('', 'Todas')] + CONDIC_CHOICES)
    desde = forms.DateField(required=False, widget=DateInputHTML5())
    hasta = forms.DateField(required=False, widget=DateInputHTML5())

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['productor'].queryset = ClienteProveedor.objects.filter(empresa_id=empresa_id)
        self.fields['variedad'].queryset = VariedadTabaco.objects.filter(empresa_id=empresa_id)
        self.fields['campania'].queryset = Campania.objects.filter(empresa_id=empresa_id)
        _estilar(self)
