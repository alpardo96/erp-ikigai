from django import forms
from django.contrib.auth.models import User
from .models import Perfil
from empresas.models import Empresa

class UsuarioForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'}), required=False, label="Contraseña", help_text="Déjalo en blanco si no quieres cambiarla.")
    es_admin_sistema = forms.BooleanField(required=False, label="¿Es Administrador General?", widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded'}))
    
    es_cajero_mostrador = forms.BooleanField(required=False, label="Sólo Caja Mostrador", widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded'}))

    permiso_clientes_ver = forms.BooleanField(required=False, label="Ver Clientes/Proveedores", widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded'}))
    permiso_clientes_editar = forms.BooleanField(required=False, label="ABM Clientes/Proveedores", widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded'}))
    
    permiso_facturacion_compras = forms.BooleanField(required=False, label="Ver Compras", widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded'}))
    permiso_facturacion_lista_compras = forms.BooleanField(required=False, label="Lista de Compras", widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded'}))
    permiso_facturacion_autorizaciones = forms.BooleanField(required=False, label="Autorizaciones", widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded'}))
    permiso_facturacion_carga_ventas = forms.BooleanField(required=False, label="Carga de Ventas", widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded'}))
    permiso_facturacion_lista_ventas = forms.BooleanField(required=False, label="Lista de Ventas", widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded'}))


    empresas = forms.ModelMultipleChoiceField(
        queryset=Empresa.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'}),
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
            # Ya existe el usuario, poblamos datos del perfil si existe
            if hasattr(self.instance, 'perfil'):
                self.fields['es_admin_sistema'].initial = self.instance.perfil.es_admin_sistema
                self.fields['es_cajero_mostrador'].initial = self.instance.perfil.es_cajero_mostrador
                self.fields['permiso_clientes_ver'].initial = self.instance.perfil.permiso_clientes_ver
                self.fields['permiso_clientes_editar'].initial = self.instance.perfil.permiso_clientes_editar
                
                self.fields['permiso_facturacion_compras'].initial = self.instance.perfil.permiso_facturacion_compras
                self.fields['permiso_facturacion_lista_compras'].initial = self.instance.perfil.permiso_facturacion_lista_compras
                self.fields['permiso_facturacion_autorizaciones'].initial = self.instance.perfil.permiso_facturacion_autorizaciones
                self.fields['permiso_facturacion_carga_ventas'].initial = self.instance.perfil.permiso_facturacion_carga_ventas
                self.fields['permiso_facturacion_lista_ventas'].initial = self.instance.perfil.permiso_facturacion_lista_ventas
                
                self.fields['empresas'].initial = self.instance.perfil.empresas.all()
                
    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
            
        if commit:
            user.save()
            perfil, created = Perfil.objects.get_or_create(usuario=user)
            perfil.es_admin_sistema = self.cleaned_data.get('es_admin_sistema')
            perfil.es_cajero_mostrador = self.cleaned_data.get('es_cajero_mostrador')
            perfil.permiso_clientes_ver = self.cleaned_data.get('permiso_clientes_ver')
            perfil.permiso_clientes_editar = self.cleaned_data.get('permiso_clientes_editar')
            
            perfil.permiso_facturacion_compras = self.cleaned_data.get('permiso_facturacion_compras')
            perfil.permiso_facturacion_lista_compras = self.cleaned_data.get('permiso_facturacion_lista_compras')
            perfil.permiso_facturacion_autorizaciones = self.cleaned_data.get('permiso_facturacion_autorizaciones')
            perfil.permiso_facturacion_carga_ventas = self.cleaned_data.get('permiso_facturacion_carga_ventas')
            perfil.permiso_facturacion_lista_ventas = self.cleaned_data.get('permiso_facturacion_lista_ventas')
            
            perfil.empresas.set(self.cleaned_data.get('empresas'))
            perfil.save()
            
        return user
