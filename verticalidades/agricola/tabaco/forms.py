"""Formularios de los maestros del acopio de tabaco (Plan 081).

Todos reciben `empresa_id` como primer argumento para acotar los combos a la empresa de la
sesión: regla inflexible de multi-tenant del proyecto.

IMPORTES Y COEFICIENTES: siempre `DecimalARField` + `.fInputAR`. Nunca un `NumberInput` suelto
ni parseo propio — el formato es-AR está centralizado en `static/js/formato_ar.js` y
`core.forms.DecimalARField`, y duplicarlo es lo que hace que dos pantallas discrepen.
"""
from django import forms

from contable.models import Cuenta
from core.forms import DateInputHTML5, DecimalARField
from verticalidades.agricola.core_agricola.models import Campania

from .models import (ClaseTabaco, ConfiguracionTabaco, ListaPrecioTabaco,
                     ProductorTabaco, TipoRetencionTabaco, VariedadTabaco)

INPUT_CLASS = ("w-full rounded-xl border-gray-200 text-sm "
               "focus:ring-indigo-500 focus:border-indigo-500 transition-all")
CHECK_CLASS = "h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"


class _BaseAgroForm(forms.ModelForm):
    """Aplica el estilo Tailwind estándar del panel de configuración."""

    def _estilar(self):
        for _nombre, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = CHECK_CLASS
            else:
                actual = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f"{actual} {INPUT_CLASS}".strip()

    def _cuentas_imputables(self, campo, empresa_id):
        """Acota un combo de cuentas a las imputables de la empresa.

        Sólo las imputables: una cuenta de agrupación no puede recibir un asiento, y ofrecerla
        deja configurar algo que después va a fallar recién al contabilizar.
        """
        if campo in self.fields:
            self.fields[campo].queryset = (Cuenta.objects
                                           .filter(empresa_id=empresa_id, imputable=1)
                                           .order_by('jerarquia'))


class CampaniaForm(_BaseAgroForm):
    class Meta:
        model = Campania
        fields = ['codigo', 'detalle', 'fecha_inicio', 'fecha_fin', 'ejercicio', 'estado', 'activa']
        widgets = {
            'codigo': forms.TextInput(attrs={'placeholder': '2026/2027'}),
            'detalle': forms.TextInput(attrs={'placeholder': 'CAMPAÑA 2026/2027'}),
            'fecha_inicio': DateInputHTML5(),
            'fecha_fin': DateInputHTML5(),
        }

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa_id = empresa_id
        from empresas.models import Ejercicio
        self.fields['ejercicio'].queryset = Ejercicio.objects.filter(empresa_id=empresa_id)
        self.fields['ejercicio'].required = False
        self._estilar()

    def clean_codigo(self):
        codigo = (self.cleaned_data.get('codigo') or '').strip().upper()
        qs = Campania.objects.filter(empresa_id=self.empresa_id, codigo=codigo)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe una campaña con ese código.")
        return codigo

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get('fecha_inicio'), datos.get('fecha_fin')
        if desde and hasta and hasta < desde:
            self.add_error('fecha_fin', "El fin no puede ser anterior al inicio.")
        return datos


class VariedadTabacoForm(_BaseAgroForm):
    class Meta:
        model = VariedadTabaco
        fields = ['codigo', 'detalle', 'producto', 'activa']
        widgets = {
            'codigo': forms.NumberInput(attrs={'min': 1}),
            'detalle': forms.TextInput(attrs={'placeholder': 'BURLEY'}),
        }

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa_id = empresa_id
        from productos.models import Producto
        self.fields['producto'].queryset = Producto.objects.filter(empresa_id=empresa_id)
        self.fields['producto'].required = False
        self._estilar()

    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo')
        qs = VariedadTabaco.objects.filter(empresa_id=self.empresa_id, codigo=codigo)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe una variedad con ese código.")
        return codigo


class ClaseTabacoForm(_BaseAgroForm):
    """Las 75 clases las crea el importador; acá se corrige puntualmente.

    El coeficiente es editable porque las listas se renegocian, pero eso NO reescribe el precio
    de lo ya comprado: el romaneo guarda copia del coeficiente que aplicó.
    """
    coeficiente = DecimalARField(
        max_digits=6, decimal_places=4, label="Coeficiente",
        widget=forms.TextInput(attrs={'class': 'fInputAR', 'placeholder': '0,8500'}))

    class Meta:
        model = ClaseTabaco
        fields = ['variedad', 'codigo', 'detalle', 'coeficiente', 'activa']
        widgets = {
            'codigo': forms.NumberInput(attrs={'min': 1}),
            'detalle': forms.TextInput(attrs={'placeholder': 'B1F'}),
        }

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa_id = empresa_id
        self.fields['variedad'].queryset = VariedadTabaco.objects.filter(
            empresa_id=empresa_id, activa=True)
        self._estilar()

    def clean_coeficiente(self):
        coeficiente = self.cleaned_data.get('coeficiente')
        if coeficiente is not None and coeficiente <= 0:
            raise forms.ValidationError("El coeficiente debe ser mayor que cero.")
        return coeficiente

    def clean(self):
        datos = super().clean()
        variedad, codigo = datos.get('variedad'), datos.get('codigo')
        detalle = (datos.get('detalle') or '').strip().upper()

        if variedad and codigo is not None:
            qs = ClaseTabaco.objects.filter(empresa_id=self.empresa_id,
                                            variedad=variedad, codigo=codigo)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('codigo', "Ya existe una clase con ese código en la variedad.")

        if variedad and detalle:
            qs = ClaseTabaco.objects.filter(empresa_id=self.empresa_id,
                                            variedad=variedad, detalle=detalle)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('detalle', "Ya existe esa clase en la variedad.")
        return datos


class ListaPrecioTabacoForm(_BaseAgroForm):
    precio_ponderante = DecimalARField(
        max_digits=15, decimal_places=2, label="Precio Ponderante ($/kg)",
        widget=forms.TextInput(attrs={'class': 'fInputAR', 'placeholder': '2.500,00'}))

    class Meta:
        model = ListaPrecioTabaco
        fields = ['variedad', 'campania', 'vigencia_desde', 'vigencia_hasta',
                  'moneda', 'precio_ponderante', 'aprobada']
        widgets = {
            'vigencia_desde': DateInputHTML5(),
            'vigencia_hasta': DateInputHTML5(),
        }

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa_id = empresa_id
        self.fields['variedad'].queryset = VariedadTabaco.objects.filter(
            empresa_id=empresa_id, activa=True)
        self.fields['campania'].queryset = Campania.objects.filter(
            empresa_id=empresa_id, activa=True)
        self._estilar()

    def clean_precio_ponderante(self):
        precio = self.cleaned_data.get('precio_ponderante')
        if precio is not None and precio <= 0:
            raise forms.ValidationError("El precio ponderante debe ser mayor que cero.")
        return precio

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get('vigencia_desde'), datos.get('vigencia_hasta')
        if desde and hasta and hasta < desde:
            self.add_error('vigencia_hasta', "El fin de vigencia no puede ser anterior al inicio.")
        return datos


class TipoRetencionTabacoForm(_BaseAgroForm):
    alicuota = DecimalARField(
        max_digits=7, decimal_places=4, required=False, initial=0, label="Alícuota %",
        widget=forms.TextInput(attrs={'class': 'fInputAR', 'placeholder': '0,5000'}))
    minimo_no_imponible = DecimalARField(
        max_digits=15, decimal_places=2, required=False, initial=0, label="Mínimo no imponible",
        widget=forms.TextInput(attrs={'class': 'fInputAR', 'placeholder': '224.000,00'}))

    class Meta:
        model = TipoRetencionTabaco
        fields = ['codigo', 'detalle', 'organismo', 'jurisdiccion', 'regimen',
                  'tipo_base', 'alicuota', 'minimo_no_imponible',
                  'momento', 'solo_responsable_inscripto', 'cuenta_contable',
                  'vigencia_desde', 'vigencia_hasta', 'activa']
        widgets = {
            'codigo': forms.TextInput(attrs={'placeholder': 'EEAOC'}),
            'detalle': forms.TextInput(attrs={'placeholder': 'RETENCION EEAOC'}),
            'organismo': forms.TextInput(attrs={'placeholder': 'EEAOC'}),
            'regimen': forms.TextInput(attrs={'placeholder': '78'}),
            'vigencia_desde': DateInputHTML5(),
            'vigencia_hasta': DateInputHTML5(),
        }

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa_id = empresa_id
        self._cuentas_imputables('cuenta_contable', empresa_id)
        self.fields['jurisdiccion'].required = False
        self._estilar()

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get('vigencia_desde'), datos.get('vigencia_hasta')
        if desde and hasta and hasta < desde:
            self.add_error('vigencia_hasta', "El fin de vigencia no puede ser anterior al inicio.")

        # Ganancias no puede practicarse al liquidar: su base es el acumulado mensual de lo
        # PAGADO. Si se retuviera en la liquidación, el acumulado se armaría sobre otra cosa y
        # el importe retenido sería incorrecto.
        if (datos.get('tipo_base') == TipoRetencionTabaco.ACUM_MENSUAL
                and datos.get('momento') != TipoRetencionTabaco.PAGO):
            self.add_error(
                'momento',
                "Una retención de base acumulada mensual sólo puede practicarse al pagar.")
        return datos


class ConfiguracionTabacoForm(_BaseAgroForm):
    tolerancia_pesaje = DecimalARField(
        max_digits=6, decimal_places=2, required=False, initial=0,
        label="Tolerancia de pesaje (kg)",
        widget=forms.TextInput(attrs={'class': 'fInputAR', 'placeholder': '0,00'}))

    class Meta:
        model = ConfiguracionTabaco
        fields = ['cuenta_bienes_cambio', 'punto_venta', 'modo_autorizacion',
                  'cai', 'cai_vencimiento', 'tolerancia_pesaje']
        widgets = {
            'punto_venta': forms.NumberInput(attrs={'min': 1}),
            'cai': forms.TextInput(attrs={'placeholder': '12345678901234'}),
            'cai_vencimiento': DateInputHTML5(),
        }

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa_id = empresa_id
        self._cuentas_imputables('cuenta_bienes_cambio', empresa_id)
        self._estilar()

    def clean(self):
        datos = super().clean()
        # En modo MANUAL el comprobante sale de un talonario o del comprobante en línea: sin CAI
        # no hay comprobante válido que emitir.
        if datos.get('modo_autorizacion') == ConfiguracionTabaco.MANUAL and not datos.get('cai'):
            self.add_error('cai', "En modo manual hay que cargar el CAI del talonario.")
        return datos


class ProductorTabacoForm(_BaseAgroForm):
    coeficiente = DecimalARField(
        max_digits=6, decimal_places=4, required=False, initial=1,
        label="Coeficiente del productor",
        widget=forms.TextInput(attrs={'class': 'fInputAR', 'placeholder': '1,0000'}))

    class Meta:
        model = ProductorTabaco
        fields = ['codigo_fet', 'finca_origen', 'coeficiente', 'habilitado', 'observaciones']
        widgets = {
            'codigo_fet': forms.TextInput(attrs={'placeholder': '569'}),
            'finca_origen': forms.TextInput(attrs={'placeholder': 'FINCA LA ESPERANZA'}),
            'observaciones': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa_id = empresa_id
        self._estilar()
