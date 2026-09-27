from django import forms
from core.forms import DecimalARField
from .models import EmpresaVertical, Campania, Finca, Seccion

INPUT_CLASS = ("w-full rounded-xl border-gray-200 text-sm "
               "focus:ring-indigo-500 focus:border-indigo-500 transition-all")
CHECK_CLASS = "h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"


class _BaseAgroForm(forms.ModelForm):
    """Aplica el estilo Tailwind estándar del ERP."""
    def _estilar(self):
        for _nombre, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = CHECK_CLASS
            else:
                actual = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f"{actual} {INPUT_CLASS}".strip()


class EmpresaVerticalForm(forms.ModelForm):
    class Meta:
        model = EmpresaVertical
        fields = ['hace_acopio_tabaco', 'hace_granos', 'hace_tabaco', 'hace_cana']
        widgets = {
            'hace_acopio_tabaco': forms.CheckboxInput(attrs={'class': CHECK_CLASS}),
            'hace_granos': forms.CheckboxInput(attrs={'class': CHECK_CLASS}),
            'hace_tabaco': forms.CheckboxInput(attrs={'class': CHECK_CLASS}),
            'hace_cana': forms.CheckboxInput(attrs={'class': CHECK_CLASS}),
        }



class FincaForm(_BaseAgroForm):
    superficie_total_ha = DecimalARField(
        label="Superficie Total (Ha)",
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.TextInput(attrs={'placeholder': '0,00'})
    )

    class Meta:
        model = Finca
        fields = [
            'codigo', 'nombre', 'localidad', 'provincia',
            'superficie_total_ha', 'es_propia', 'arrendatario_titular',
            'activa', 'observaciones'
        ]
        widgets = {
            'codigo': forms.TextInput(attrs={'placeholder': 'Ej: F01'}),
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej: Finca La Esperanza'}),
            'localidad': forms.TextInput(attrs={'placeholder': 'Ej: El Carril'}),
            'provincia': forms.TextInput(attrs={'placeholder': 'Ej: Salta'}),
            'arrendatario_titular': forms.TextInput(attrs={'placeholder': 'Nombre o Razón Social del titular'}),
            'observaciones': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Observaciones adicionales...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._estilar()


class SeccionForm(_BaseAgroForm):
    superficie_ha = DecimalARField(
        label="Superficie Cultivable (Ha)",
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.TextInput(attrs={'placeholder': '0,00'})
    )
    metros_lineales_surco = DecimalARField(
        label="Metros Lineales de Surco",
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.TextInput(attrs={'placeholder': '0,00'})
    )
    distanciamiento_surco_m = DecimalARField(
        label="Distanciamiento entre Surcos (m)",
        decimal_places=2,
        required=False,
        initial=1.60,
        widget=forms.TextInput(attrs={'placeholder': '1,60'})
    )

    class Meta:
        model = Seccion
        fields = [
            'finca', 'codigo', 'nombre', 'superficie_ha',
            'metros_lineales_surco', 'distanciamiento_surco_m',
            'aptitud_principal', 'activa', 'observaciones'
        ]
        widgets = {
            'codigo': forms.TextInput(attrs={'placeholder': 'Ej: SEC-01 o LOTE-4'}),
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej: Cuadro Norte / Lote Represa'}),
            'observaciones': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Observaciones...'}),
        }


    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if empresa_id:
            self.fields['finca'].queryset = Finca.objects.filter(empresa_id=empresa_id, activa=True).order_by('codigo')
        self._estilar()


class CultivoForm(_BaseAgroForm):
    class Meta:
        from .models import Cultivo
        model = Cultivo
        fields = [
            'codigo', 'nombre', 'tipo', 'producto_cosecha',
            'ciclo_estimado_dias', 'color_identificador', 'activo', 'observaciones'
        ]
        widgets = {
            'codigo': forms.TextInput(attrs={'placeholder': 'Ej: SOJA-1RA, TAB-VIR, CANA'}),
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej: Soja de Primera / Tabaco Virginia'}),
            'color_identificador': forms.TextInput(attrs={'type': 'color', 'class': 'h-10 w-20 rounded-lg cursor-pointer'}),
            'observaciones': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Notas sobre el cultivo...'}),
        }

    def __init__(self, empresa_id=None, *args, **kwargs):
        from productos.models import Producto
        super().__init__(*args, **kwargs)
        if empresa_id:
            self.fields['producto_cosecha'].queryset = Producto.objects.filter(empresa_id=empresa_id, activo=True).order_by('detalle')
        self._estilar()


class TipoLaborForm(_BaseAgroForm):
    class Meta:
        from .models import TipoLabor
        model = TipoLabor
        fields = ['codigo', 'nombre', 'categoria', 'requiere_insumos', 'activa']
        widgets = {
            'codigo': forms.TextInput(attrs={'placeholder': 'Ej: PULV-HERB, FERT-BASE'}),
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej: Pulverización Herbicida / Desflore'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._estilar()

