from django import forms
from .models import MedioPago, CuentaBancaria
from contable.models import Cuenta

class MedioPagoForm(forms.ModelForm):
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
        if empresa:
            self.fields['cuenta_contable'].queryset = Cuenta.objects.filter(empresa=empresa, imputable=1).order_by('jerarquia')
            
        for field_name, field in self.fields.items():
            if field_name != 'activo':
                clase_actual = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f"{clase_actual} w-full rounded-xl border-gray-200 text-sm focus:ring-indigo-500 focus:border-indigo-500 transition-all".strip()
            else:
                field.widget.attrs['class'] = "h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"

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
            cuentas_imputables = Cuenta.objects.filter(empresa=empresa, imputable=1).order_by('jerarquia')
            self.fields['cuenta_contable'].queryset = cuentas_imputables
            self.fields['cuenta_contable_cheques'].queryset = cuentas_imputables

        for field_name, field in self.fields.items():
            clase_actual = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{clase_actual} w-full rounded-xl border-gray-200 text-sm focus:ring-indigo-500 focus:border-indigo-500 transition-all".strip()
