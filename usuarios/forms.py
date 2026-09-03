from django import forms
from django.contrib.auth.models import User, Group, Permission
from .models import Perfil
from empresas.models import Empresa

class UsuarioForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'}), required=False, label="Contraseña", help_text="Déjalo en blanco si no quieres cambiarla.")
    es_admin_sistema = forms.BooleanField(required=False, label="¿Es Administrador General?", widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded'}))
    
    es_cajero_mostrador = forms.BooleanField(required=False, label="Sólo Caja Mostrador", widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded'}))

    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        label="Roles Asignados",
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded mr-2'}),
        help_text="Selecciona los roles que determinan los permisos base del usuario."
    )

    user_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.exclude(content_type__app_label__in=['admin', 'auth', 'contenttypes', 'sessions']),
        required=False,
        label="Permisos Individuales Adicionales",
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded mr-2'}),
        help_text="Permisos específicos asignados directamente, además de los que hereda por sus roles."
    )

    empresas = forms.ModelMultipleChoiceField(
        queryset=Empresa.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded mr-2'}),
        help_text="Selecciona las empresas a las que este usuario tendrá acceso."
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm', 'required': 'required'}),
            'email': forms.EmailInput(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['groups'].initial = self.instance.groups.all()
            self.fields['user_permissions'].initial = self.instance.user_permissions.all()
            if hasattr(self.instance, 'perfil'):
                self.fields['es_admin_sistema'].initial = self.instance.perfil.es_admin_sistema
                self.fields['es_cajero_mostrador'].initial = self.instance.perfil.es_cajero_mostrador
                self.fields['empresas'].initial = self.instance.perfil.empresas.all()
                
    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
            
        if commit:
            user.save()
            user.groups.set(self.cleaned_data.get('groups'))
            user.user_permissions.set(self.cleaned_data.get('user_permissions'))
            
            perfil, created = Perfil.objects.get_or_create(usuario=user)
            perfil.es_admin_sistema = self.cleaned_data.get('es_admin_sistema')
            perfil.es_cajero_mostrador = self.cleaned_data.get('es_cajero_mostrador')
            perfil.empresas.set(self.cleaned_data.get('empresas'))
            perfil.save()
            
        return user
