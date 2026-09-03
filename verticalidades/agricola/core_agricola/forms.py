from django import forms
from .models import EmpresaVertical

class EmpresaVerticalForm(forms.ModelForm):
    class Meta:
        model = EmpresaVertical
        fields = ['hace_tabaco', 'hace_granos']
        widgets = {
            'hace_tabaco': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'hace_granos': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
