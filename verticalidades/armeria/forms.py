from django import forms
from .models import ExtensionArmeria

class ExtensionArmeriaForm(forms.ModelForm):
    tipo_persona = forms.ChoiceField(
        choices=[('', "Seleccione tipo"), ('F', 'Persona Física'), ('J', 'Persona Jurídica')],
        required=True,
        widget=forms.Select(),
        label="Tipo de Persona"
    )
    es_policia = forms.TypedChoiceField(
        choices=[('', "Seleccione una opción"), ('false', "NO (Civil / Particular)"), ('true', "SÍ (Policía / Fuerza de Seguridad)")],
        coerce=lambda x: str(x).lower() in ('true', '1'),
        required=True,
        widget=forms.Select(),
        label="Es Policía / Fuerza de Seguridad"
    )

    class Meta:
        model = ExtensionArmeria
        fields = ['tipo_persona', 'clu', 'clu_vto', 'es_policia']
        widgets = {
            'clu': forms.TextInput(),
            'clu_vto': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['clu'].required = False
        self.fields['clu_vto'].required = False
        if self.instance and self.instance.pk:
            self.fields['es_policia'].initial = 'true' if self.instance.es_policia else 'false'
        else:
            self.fields['es_policia'].initial = ''

        for field_name, field in self.fields.items():
            clase_actual = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{clase_actual} w-full rounded-xl border-gray-200 text-sm focus:ring-indigo-500 focus:border-indigo-500 transition-all".strip()




