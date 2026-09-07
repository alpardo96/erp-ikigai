"""Formularios de lotes, acondicionamiento y margen (Plan 086 — Etapa 5).

Van aparte de `forms.py` (maestros) y de `forms_romaneo.py` (recepción) por la misma razón que
aquéllos entre sí: capturan otra cosa. Acá se agrupa, se procesa y se vende.

Las validaciones de negocio —variedad y sucursal del fardo, kilos disponibles, motivo de la merma
extraordinaria— viven en los servicios, no acá. El formulario sólo verifica formato y pertenencia
a la empresa, que es lo que puede resolver sin conocer el estado del documento.
"""
from django import forms

from core.forms import DateInputHTML5, DecimalARField
from empresas.models import Sucursal
from productos.models import Producto
from verticalidades.agricola.core_agricola.models import Campania

from .forms_romaneo import CONDIC_CHOICES, _estilar
from .models import Acondicionamiento, LoteAcopio, ProcesoAcondicionamiento, VariedadTabaco


class AbrirLoteForm(forms.Form):
    """Cabecera del lote. Después de armarlo, variedad y sucursal quedan fijas."""
    sucursal = forms.ModelChoiceField(queryset=Sucursal.objects.none(), label="Sucursal")
    variedad = forms.ModelChoiceField(queryset=VariedadTabaco.objects.none(), label="Variedad")
    campania = forms.ModelChoiceField(queryset=Campania.objects.none(), label="Campaña")
    fecha = forms.DateField(widget=DateInputHTML5(), label="Fecha")
    descripcion = forms.CharField(
        required=False, max_length=160, label="Descripción",
        widget=forms.TextInput(attrs={'placeholder': 'Cómo identifica el lote la planta'}))
    observaciones = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa_id = empresa_id
        self.fields['sucursal'].queryset = Sucursal.objects.filter(empresa_id=empresa_id)
        self.fields['variedad'].queryset = VariedadTabaco.objects.filter(
            empresa_id=empresa_id, activa=True)
        self.fields['campania'].queryset = Campania.objects.filter(
            empresa_id=empresa_id, activa=True, estado=Campania.ABIERTA)
        _estilar(self)


class AcondicionamientoForm(forms.Form):
    """Una corrida de proceso. Los kilos los pesa el operario; el resto lo deriva el servicio."""
    proceso = forms.ModelChoiceField(queryset=ProcesoAcondicionamiento.objects.none(),
                                     label="Proceso")
    fecha = forms.DateField(widget=DateInputHTML5(), label="Fecha")
    kilos_entrada = DecimalARField(max_digits=15, decimal_places=2, label="Kilos de entrada",
                                   widget=forms.TextInput(attrs={'class': 'fInputAR',
                                                                 'placeholder': '0,00'}))
    kilos_salida = DecimalARField(max_digits=15, decimal_places=2, label="Kilos de salida",
                                  widget=forms.TextInput(attrs={'class': 'fInputAR',
                                                                'placeholder': '0,00'}))
    motivo_merma = forms.CharField(
        required=False, max_length=200, label="Motivo de la merma extraordinaria",
        widget=forms.TextInput(attrs={'placeholder': 'Obligatorio sólo si excede la merma normal'}))
    observaciones = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['proceso'].queryset = ProcesoAcondicionamiento.objects.filter(
            empresa_id=empresa_id, activo=True)
        _estilar(self)

    def clean_kilos_entrada(self):
        kilos = self.cleaned_data.get('kilos_entrada')
        if kilos is not None and kilos <= 0:
            raise forms.ValidationError("Los kilos de entrada deben ser mayores que cero.")
        return kilos


class CoproductoForm(forms.Form):
    """El palo, el descarte: kilos que dejan de ser tabaco pero siguen valiendo."""
    producto = forms.ModelChoiceField(queryset=Producto.objects.none(),
                                      widget=forms.HiddenInput())
    kilos = DecimalARField(max_digits=15, decimal_places=2, label="Kilos",
                           widget=forms.TextInput(attrs={'class': 'fInputAR',
                                                         'placeholder': '0,00'}))
    valor_estimado = DecimalARField(max_digits=15, decimal_places=2, required=False, initial=0,
                                    label="Valor estimado",
                                    widget=forms.TextInput(attrs={'class': 'fInputAR',
                                                                  'placeholder': '0,00'}))
    observaciones = forms.CharField(required=False, max_length=200)

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto'].queryset = Producto.objects.filter(empresa_id=empresa_id)
        _estilar(self)


class CostoForm(forms.Form):
    """Costo directo imputado al lote.

    `compra` es RESPALDO: la factura ya se contabilizó por el circuito de compras. Acá sólo se
    dice a qué lote se imputa ese gasto para poder medir el margen.
    """
    concepto = forms.CharField(max_length=160, label="Concepto",
                               widget=forms.TextInput(attrs={'placeholder': 'Mano de obra, energía, insumo'}))
    importe = DecimalARField(max_digits=15, decimal_places=2, label="Importe",
                             widget=forms.TextInput(attrs={'class': 'fInputAR',
                                                           'placeholder': '0,00'}))
    compra = forms.IntegerField(required=False, widget=forms.HiddenInput())

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa_id = empresa_id
        _estilar(self)

    def clean_compra(self):
        """Resuelve la compra de respaldo acotada a la empresa activa."""
        pk = self.cleaned_data.get('compra')
        if not pk:
            return None

        from facturacion.models import Compra

        compra = Compra.objects.filter(pk=pk, empresa_id=self.empresa_id).first()
        if compra is None:
            raise forms.ValidationError("La compra de respaldo no existe en esta empresa.")
        return compra


class AsignarVentaForm(forms.Form):
    """Vincula la venta que despachó el lote. NO la emite: eso es `facturacion`."""
    venta = forms.IntegerField(widget=forms.HiddenInput())

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa_id = empresa_id
        _estilar(self)

    def clean_venta(self):
        from facturacion.models import Venta

        venta = Venta.objects.filter(pk=self.cleaned_data['venta'],
                                     empresa_id=self.empresa_id).first()
        if venta is None:
            raise forms.ValidationError("La venta no existe en esta empresa.")
        return venta


class MotivoForm(forms.Form):
    motivo = forms.CharField(max_length=200, label="Motivo",
                             widget=forms.TextInput(attrs={'placeholder': 'Obligatorio'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilar(self)


class FiltroLotesForm(forms.Form):
    """Filtros del listado. Con `condic`, que el proyecto exige en todo listado con importes.

    `condic` se aplica sobre los ROMANEOS que aportaron los fardos: es la condición del hecho
    económico de origen. El lote en sí no tiene condición propia.
    """
    q = forms.CharField(required=False, label="Buscar")
    sucursal = forms.ModelChoiceField(queryset=Sucursal.objects.none(), required=False)
    variedad = forms.ModelChoiceField(queryset=VariedadTabaco.objects.none(), required=False)
    campania = forms.ModelChoiceField(queryset=Campania.objects.none(), required=False)
    estado = forms.ChoiceField(required=False, choices=[('', 'Todos')] + LoteAcopio.ESTADOS)
    condic = forms.ChoiceField(required=False, choices=[('', 'Todas')] + CONDIC_CHOICES)
    desde = forms.DateField(required=False, widget=DateInputHTML5())
    hasta = forms.DateField(required=False, widget=DateInputHTML5())

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sucursal'].queryset = Sucursal.objects.filter(empresa_id=empresa_id)
        self.fields['variedad'].queryset = VariedadTabaco.objects.filter(empresa_id=empresa_id)
        self.fields['campania'].queryset = Campania.objects.filter(empresa_id=empresa_id)
        _estilar(self)


class FiltroMargenForm(forms.Form):
    """Filtros del reporte de margen."""
    sucursal = forms.ModelChoiceField(queryset=Sucursal.objects.none(), required=False)
    variedad = forms.ModelChoiceField(queryset=VariedadTabaco.objects.none(), required=False)
    campania = forms.ModelChoiceField(queryset=Campania.objects.none(), required=False)
    condic = forms.ChoiceField(required=False, choices=[('', 'Todas')] + CONDIC_CHOICES)
    solo_vendidos = forms.BooleanField(required=False, label="Sólo lotes vendidos")

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sucursal'].queryset = Sucursal.objects.filter(empresa_id=empresa_id)
        self.fields['variedad'].queryset = VariedadTabaco.objects.filter(empresa_id=empresa_id)
        self.fields['campania'].queryset = Campania.objects.filter(empresa_id=empresa_id)
        _estilar(self)


class ProcesoForm(forms.ModelForm):
    """ABM del maestro que resuelve DA-07: qué procesos existen es un dato, no código."""

    merma_normal_porcentaje = DecimalARField(
        max_digits=6, decimal_places=3, label="% de merma normal", initial=0,
        widget=forms.TextInput(attrs={'class': 'fInputAR', 'placeholder': '0,000'}))

    class Meta:
        model = ProcesoAcondicionamiento
        fields = ['codigo', 'detalle', 'merma_normal_porcentaje', 'orden', 'activo']

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa_id = empresa_id
        _estilar(self)

    def clean_codigo(self):
        codigo = (self.cleaned_data['codigo'] or '').strip().upper()
        existente = ProcesoAcondicionamiento.objects.filter(
            empresa_id=self.empresa_id, codigo=codigo)
        if self.instance.pk:
            existente = existente.exclude(pk=self.instance.pk)
        if existente.exists():
            raise forms.ValidationError("Ya hay un proceso con ese código en esta empresa.")
        return codigo

    def clean_merma_normal_porcentaje(self):
        valor = self.cleaned_data.get('merma_normal_porcentaje')
        if valor is not None and not (0 <= valor <= 100):
            raise forms.ValidationError("El porcentaje debe estar entre 0 y 100.")
        return valor
