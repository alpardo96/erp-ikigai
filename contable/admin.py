from django.contrib import admin
from .models import LibroIvaCompras, LibroIvaVentas, LibroIvaAlic, RetPercSufrida, AlicuotaIva


@admin.register(AlicuotaIva)
class AlicuotaIvaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descripcion', 'porcentaje', 'activo', 'orden')
    list_editable = ('descripcion', 'porcentaje', 'activo', 'orden')
    ordering = ('orden', 'codigo')


@admin.register(LibroIvaCompras)
class LibroIvaComprasAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'codiva', 'punto', 'numero', 'clienteproveedor', 'neto_gravado', 'iva_total', 'otros', 'total', 'asiento_id')
    list_filter = ('empresa', 'fecha')
    search_fields = ('numero', 'cuit', 'asiento_id')


@admin.register(LibroIvaVentas)
class LibroIvaVentasAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'codiva', 'punto', 'numero', 'clienteproveedor', 'neto_gravado', 'iva_total', 'otros', 'total', 'cae', 'asiento_id')
    list_filter = ('empresa', 'fecha')
    search_fields = ('numero', 'cuit', 'cae', 'asiento_id')


@admin.register(LibroIvaAlic)
class LibroIvaAlicAdmin(admin.ModelAdmin):
    list_display = ('asiento_id', 'c_v', 'neto', 'alicuota', 'iva', 'computable', 'codiva')
    list_filter = ('c_v', 'alicuota')
    search_fields = ('asiento_id',)


@admin.register(RetPercSufrida)
class RetPercSufridaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'origen', 'tipo', 'impuesto', 'base', 'alicuota', 'importe', 'jurisdiccion', 'nro_certificado', 'asiento_id')
    list_filter = ('empresa', 'origen', 'tipo', 'impuesto')
    search_fields = ('nro_certificado', 'cuit_agente', 'asiento_id')
