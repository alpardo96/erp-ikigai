from django import forms
from .models import Empresa, Sucursal, Ejercicio, CotizacionMoneda, PuntoVenta

class EmpresaForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = ['nombre', 'cuit', 'logo', 'direccion', 'correo', 'telefono', 'tipo_actividad', 'pedir_fecha_nacimiento_cliente',
                  'usa_orden_compra', 'condicion_iva', 'fecha_inicio_actividades', 'condicion_iibb', 'jurisdicciones_iibb', 'entorno_afip', 'crt_afip', 'key_afip', 'vencimiento_crt_afip']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'w-full rounded-xl border-gray-200 text-sm', 'required': 'required'}),
            'cuit': forms.TextInput(attrs={'class': 'w-full rounded-xl border-gray-200 text-sm', 'required': 'required'}),
            'logo': forms.FileInput(attrs={'class': 'file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 transition-colors'}),
            'direccion': forms.TextInput(attrs={'class': 'w-full rounded-xl border-gray-200 text-sm'}),
            'correo': forms.EmailInput(attrs={'class': 'w-full rounded-xl border-gray-200 text-sm'}),
            'telefono': forms.TextInput(attrs={'class': 'w-full rounded-xl border-gray-200 text-sm'}),
            'tipo_actividad': forms.Select(attrs={'class': 'w-full rounded-xl border-gray-200 text-sm'}),
            'pedir_fecha_nacimiento_cliente': forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500'}),
            'usa_orden_compra': forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500'}),
            'condicion_iva': forms.Select(attrs={'class': 'w-full rounded-xl border-gray-200 text-sm'}),
            'fecha_inicio_actividades': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'w-full rounded-xl border-gray-200 text-sm'}),
            'condicion_iibb': forms.Select(attrs={'class': 'w-full rounded-xl border-gray-200 text-sm'}),
            'jurisdicciones_iibb': forms.CheckboxSelectMultiple(attrs={'class': 'h-4 w-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500'}),
            'entorno_afip': forms.Select(attrs={'class': 'w-full rounded-xl border-gray-200 text-sm'}),
            'crt_afip': forms.FileInput(attrs={'accept': '.crt', 'class': 'file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-semibold file:bg-emerald-50 file:text-emerald-700 hover:file:bg-emerald-100 transition-colors'}),
            'key_afip': forms.FileInput(attrs={'accept': '.key', 'class': 'file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-semibold file:bg-emerald-50 file:text-emerald-700 hover:file:bg-emerald-100 transition-colors'}),
            'vencimiento_crt_afip': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'w-full rounded-xl border-gray-200 text-sm'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from facturacion.models import Jurisdiccion
        self.fields['jurisdicciones_iibb'].queryset = Jurisdiccion.objects.order_by('codigo')
        self.fields['jurisdicciones_iibb'].required = False

        from django.apps import apps
        opciones_permitidas = [('', 'Estándar (General)')]
        
        # Iterar sobre las aplicaciones instaladas y auto-descubrir las verticalidades
        for app_config in apps.get_app_configs():
            if app_config.name.startswith('verticalidades.'):
                # Utilizar el tipo_actividad_code si existe, sino el label en mayúsculas
                codigo = getattr(app_config, 'tipo_actividad_code', app_config.label.upper())
                nombre = getattr(app_config, 'verbose_name', app_config.label.title())
                opciones_permitidas.append((codigo, nombre))
                
        self.fields['tipo_actividad'].widget.choices = opciones_permitidas

    def save(self, commit=True):
        import os
        if self.instance.pk:
            try:
                empresa_vieja = Empresa.objects.get(pk=self.instance.pk)
                if 'crt_afip' in self.changed_data and empresa_vieja.crt_afip:
                    try:
                        if os.path.isfile(empresa_vieja.crt_afip.path):
                            os.remove(empresa_vieja.crt_afip.path)
                    except Exception:
                        pass
                if 'key_afip' in self.changed_data and empresa_vieja.key_afip:
                    try:
                        if os.path.isfile(empresa_vieja.key_afip.path):
                            os.remove(empresa_vieja.key_afip.path)
                    except Exception:
                        pass
            except Empresa.DoesNotExist:
                pass
        return super().save(commit=commit)

class SucursalForm(forms.ModelForm):
    class Meta:
        model = Sucursal
        fields = ['empresa', 'nombre', 'direccion', 'telefono', 'punto']
        widgets = {
            'empresa': forms.Select(attrs={'required': 'required'}),
            'nombre': forms.TextInput(attrs={'required': 'required'}),
            'direccion': forms.TextInput(),
            'telefono': forms.TextInput(),
            'punto': forms.NumberInput(attrs={'min': '1', 'required': 'required'}),
        }

class EjercicioForm(forms.ModelForm):
    """
    Formulario para crear/editar ejercicios fiscales.
    Los campos de fecha usan widget HTML5 date para mejor UX.
    """
    class Meta:
        model = Ejercicio
        fields = ['empresa', 'ejercicio', 'inicio', 'cierre']
        widgets = {
            'empresa': forms.Select(attrs={'required': 'required'}),
            'ejercicio': forms.TextInput(attrs={'required': 'required', 'placeholder': 'Ej: Ikigai - 2026'}),
            'inicio': forms.DateInput(attrs={'type': 'date', 'required': 'required'}),
            'cierre': forms.DateInput(attrs={'type': 'date', 'required': 'required'}),
        }

class CotizacionMonedaForm(forms.ModelForm):
    dolar_venta = forms.CharField(widget=forms.TextInput(attrs={'class': 'fInputCotiz text-right', 'placeholder': 'Ej: 1400.50'}))
    dolar_cobranza = forms.CharField(widget=forms.TextInput(attrs={'class': 'fInputCotiz text-right', 'placeholder': 'Ej: 1400.50'}))

    class Meta:
        model = CotizacionMoneda
        fields = ['dolar_venta', 'dolar_cobranza']

    def clean_dolar_venta(self):
        val = self.cleaned_data.get('dolar_venta')
        from decimal import Decimal, InvalidOperation
        if isinstance(val, str):
            val = val.replace(',', '.')
        try:
            return Decimal(val)
        except InvalidOperation:
            raise forms.ValidationError("Número inválido")

    def clean_dolar_cobranza(self):
        val = self.cleaned_data.get('dolar_cobranza')
        from decimal import Decimal, InvalidOperation
        if isinstance(val, str):
            val = val.replace(',', '.')
        try:
            return Decimal(val)
        except InvalidOperation:
            raise forms.ValidationError("Número inválido")
class PuntoVentaForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        empresa_id = kwargs.pop('empresa_id', None)
        super().__init__(*args, **kwargs)
        if empresa_id:
            from empresas.models import Sucursal
            self.fields['sucursal'].queryset = Sucursal.objects.filter(empresa_id=empresa_id)

    class Meta:
        model = PuntoVenta
        fields = ['sucursal', 'numero', 'activo', 'caja_mostrador_default']
        widgets = {
            'sucursal': forms.Select(attrs={'required': 'required'}),
            'numero': forms.NumberInput(attrs={'min': '1', 'max': '99999', 'required': 'required'}),
            'activo': forms.CheckboxInput(),
            'caja_mostrador_default': forms.CheckboxInput(),
        }
