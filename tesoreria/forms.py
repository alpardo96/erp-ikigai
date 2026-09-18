from django import forms
from .models import MedioPago, CuentaBancaria
from contable.models import Cuenta

class MedioPagoForm(forms.ModelForm):
    TIPO_AJUSTE_CHOICES = [('N', 'Ninguno'), ('R', 'Recargo'), ('D', 'Descuento')]
    tipo_ajuste = forms.ChoiceField(choices=TIPO_AJUSTE_CHOICES, required=False, widget=forms.Select(), label="Tipo de Ajuste")
    porcentaje_ajuste = forms.DecimalField(max_digits=5, decimal_places=2, required=False, min_value=0, label="Porcentaje (%)")

    class Meta:
        model = MedioPago
        fields = ['codigo', 'nombre', 'categoria', 'cuenta_contable', 'activo']
        widgets = {
            'codigo': forms.TextInput(attrs={'placeholder': 'EFE, MP, etc.'}),
            'nombre': forms.TextInput(attrs={'placeholder': 'Efectivo, Mercado Pago...'}),
            'categoria': forms.Select(),
            'cuenta_contable': forms.Select(),
        }

    def __init__(self, empresa=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.pk:
            ajuste = self.instance.ajuste
            if ajuste > 0:
                self.initial['tipo_ajuste'] = 'R'
                self.initial['porcentaje_ajuste'] = ajuste / 10
            elif ajuste < 0:
                self.initial['tipo_ajuste'] = 'D'
                self.initial['porcentaje_ajuste'] = abs(ajuste) / 10
            else:
                self.initial['tipo_ajuste'] = 'N'
                self.initial['porcentaje_ajuste'] = None
        else:
            self.initial['tipo_ajuste'] = 'N'

        if empresa:
            self.fields['cuenta_contable'].queryset = Cuenta.objects.filter(empresa=empresa, imputable=1).order_by('jerarquia')
            
        for field_name, field in self.fields.items():
            if field_name != 'activo':
                clase_actual = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f"{clase_actual} w-full rounded-xl border-gray-200 text-sm focus:ring-indigo-500 focus:border-indigo-500 transition-all".strip()
            else:
                field.widget.attrs['class'] = "h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"

    def clean(self):
        cleaned_data = super().clean()
        tipo_ajuste = cleaned_data.get('tipo_ajuste')
        porcentaje_ajuste = cleaned_data.get('porcentaje_ajuste')
        
        if tipo_ajuste in ['R', 'D'] and not porcentaje_ajuste:
            self.add_error('porcentaje_ajuste', 'Debe ingresar un porcentaje.')
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        tipo_ajuste = self.cleaned_data.get('tipo_ajuste')
        porcentaje_ajuste = self.cleaned_data.get('porcentaje_ajuste')

        if tipo_ajuste == 'R' and porcentaje_ajuste:
            instance.ajuste = int(porcentaje_ajuste * 10)
        elif tipo_ajuste == 'D' and porcentaje_ajuste:
            instance.ajuste = -int(porcentaje_ajuste * 10)
        else:
            instance.ajuste = 0

        if commit:
            instance.save()
        return instance

class CuentaBancariaForm(forms.ModelForm):
    class Meta:
        model = CuentaBancaria
        fields = [
            'banco', 'moneda', 'cta_numero', 'cbu',
            'cli_pro', 'cuenta_contable', 'cuenta_contable_cheques', 'banco_id'
        ]
        widgets = {
            'banco': forms.TextInput(),
            'moneda': forms.Select(),
            'cta_numero': forms.TextInput(),
            'cbu': forms.TextInput(),
            'cli_pro': forms.Select(),
            'cuenta_contable': forms.Select(),
            'cuenta_contable_cheques': forms.Select(),
            'banco_id': forms.NumberInput(),
        }

    def __init__(self, empresa=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if empresa:
            from facturacion.models import ClienteProveedor
            cuentas_imputables = Cuenta.objects.filter(empresa=empresa, imputable=1).order_by('jerarquia')
            self.fields['cuenta_contable'].queryset = cuentas_imputables
            self.fields['cuenta_contable_cheques'].queryset = cuentas_imputables
            self.fields['cli_pro'].queryset = ClienteProveedor.objects.filter(empresa=empresa).order_by('razon_social')
            self.fields['cli_pro'].required = False
            self.fields['banco_id'].required = False

        for field_name, field in self.fields.items():
            clase_actual = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{clase_actual} w-full rounded-xl border-gray-200 text-sm focus:ring-indigo-500 focus:border-indigo-500 transition-all".strip()
