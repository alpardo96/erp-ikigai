from django import forms
from .models import Cuenta, Asiento, AsientoLinea, ParametrosContables
from tesoreria.models import CuentaBancaria
from django.utils.safestring import mark_safe

class DatalistCuentaWidget(forms.Widget):
    def render(self, name, value, attrs=None, renderer=None):
        cuenta_str = ""
        cuenta_id = value or ""
        if value:
            from contable.models import Cuenta
            cta = Cuenta.objects.filter(pk=value).first()
            if cta:
                cuenta_str = f"{cta.jerarquia} - {cta.cuenta}"
        
        # El input hidden guarda el ID real de la cuenta. El input text muestra el texto y busca en el datalist.
        return mark_safe(f'''
        <div x-data="{{ id: '{cuenta_id}', text: '{cuenta_str}' }}">
            <input type="hidden" name="{name}" x-model="id">
            <input type="text" list="cuentas_list" x-model="text" 
                   @change="
                       let found = false;
                       let opts = document.getElementById('cuentas_list').options;
                       for(let i=0; i<opts.length; i++) {{
                           if(opts[i].value === $event.target.value) {{
                               id = opts[i].dataset.id;
                               found = true;
                               break;
                           }}
                       }}
                       if(!found) id = '';
                   "
                   class="w-full rounded-xl border-gray-200 text-sm focus:ring-indigo-500 focus:border-indigo-500 transition-all"
                   placeholder="Buscar cuenta...">
        </div>
        ''')

class CuentaForm(forms.ModelForm):
    class Meta:
        model = Cuenta
        fields = [
            'sumariza', 'jerarquia', 'cuenta', 'imputable', 'tipo',
            'rg_830', 'id_pre', 'id_bce', 'id_ec', 'id_fc'
        ]
        widgets = {
            'sumariza': forms.Select(),
            'jerarquia': forms.TextInput(),
            'cuenta': forms.TextInput(),
            'imputable': forms.Select(),
            'tipo': forms.Select(),
            'rg_830': forms.NumberInput(),
            'id_pre': forms.NumberInput(),
            'id_bce': forms.NumberInput(),
            'id_ec': forms.NumberInput(),
            'id_fc': forms.NumberInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aplicamos diseño premium (Tailwind)
        for field_name, field in self.fields.items():
            clase_actual = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{clase_actual} w-full rounded-xl border-gray-200 text-sm focus:ring-indigo-500 focus:border-indigo-500 transition-all".strip()
            
class CuentaBancariaForm(forms.ModelForm):
    class Meta:
        model = CuentaBancaria
        fields = [
            'banco', 'moneda', 'cta_numero', 'cbu',
            'cli_pro', 'cuenta_contable', 'banco_id'
        ]
        widgets = {
            'banco': forms.TextInput(),
            'moneda': forms.Select(),
            'cta_numero': forms.TextInput(),
            'cbu': forms.TextInput(),
            'cli_pro': forms.Select(),
            'cuenta_contable': forms.Select(),
            'banco_id': forms.NumberInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            clase_actual = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{clase_actual} w-full rounded-xl border-gray-200 text-sm focus:ring-indigo-500 focus:border-indigo-500 transition-all".strip()

class AsientoEncForm(forms.ModelForm):
    # Sólo los condic que puede elegir un operador en la carga manual. El 3 (Ajuste) se habilitará
    # para usuarios autorizados; el 4 (Auditoría) llega por la captura de asientos de auditoría, y
    # los estructurales 5/6/7 los genera el sistema. Ver la tabla completa en `.cursorrules`.
    CONDIC_CHOICES = [
        (1, '1 - Real'),
        (2, '2 - Presupuestado'),
    ]
    condic = forms.ChoiceField(choices=CONDIC_CHOICES, widget=forms.Select(), label="Condición Asiento")

    class Meta:
        model = Asiento
        fields = ['fecha', 'concepto', 'condic', 'cli_pro']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'concepto': forms.TextInput(attrs={'placeholder': 'Ej. COMPRAS DE MERCADERÍA'}),
            'cli_pro': forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            clase_actual = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{clase_actual} w-full rounded-xl border-gray-200 text-sm focus:ring-indigo-500 focus:border-indigo-500 transition-all".strip()

class AsientoLineaForm(forms.ModelForm):
    class Meta:
        model = AsientoLinea
        fields = ['cuenta', 'leyenda', 'debe', 'haber']
        widgets = {
            'cuenta': forms.Select(),
            'leyenda': forms.TextInput(attrs={'placeholder': 'Leyenda opcional'}),
            'debe': forms.NumberInput(attrs={'step': '0.01'}),
            'haber': forms.NumberInput(attrs={'step': '0.01'}),
        }

    def __init__(self, empresa=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if empresa:
            self.fields['cuenta'].queryset = Cuenta.objects.filter(empresa=empresa, imputable=1).order_by('jerarquia')
        for field_name, field in self.fields.items():
            clase_actual = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{clase_actual} w-full rounded-xl border-gray-200 text-sm focus:ring-indigo-500 focus:border-indigo-500 transition-all".strip()



class ParametrosContablesForm(forms.ModelForm):
    class Meta:
        model = ParametrosContables
        exclude = ['empresa']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if 'cta_' in field_name:
                field.widget = DatalistCuentaWidget()
                field.required = False # We don't want validation errors if they leave it empty, as it's optional config.
            else:
                clase_actual = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f"{clase_actual} w-full rounded-xl border-gray-200 text-sm focus:ring-indigo-500 focus:border-indigo-500 transition-all".strip()
