from django.contrib import admin
from .models import Empresa, Sucursal

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cuit', 'condicion_iibb', 'correo', 'fecha_creacion')
    list_filter = ('condicion_iibb',)
    search_fields = ('nombre', 'cuit')
    readonly_fields = ('fecha_creacion', 'fecha_modificacion')
    filter_horizontal = ('jurisdicciones_iibb',)

@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'empresa', 'telefono')
    list_filter = ('empresa',)
    search_fields = ('nombre',)
