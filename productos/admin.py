from django.contrib import admin
from .models import Producto, StockSucursal, Subproducto, MovimientoStock, TomaInventario, TomaInventarioItem

class StockSucursalInline(admin.TabularInline):
    model = StockSucursal
    extra = 1

class TomaInventarioItemInline(admin.TabularInline):
    model = TomaInventarioItem
    extra = 0
    raw_id_fields = ('producto',)

@admin.register(TomaInventario)
class TomaInventarioAdmin(admin.ModelAdmin):
    list_display = ('numero', 'sucursal', 'fecha_toma', 'estado', 'terminal')
    list_filter = ('empresa', 'sucursal', 'estado', 'fecha_toma')
    search_fields = ('numero', 'observaciones', 'terminal')
    inlines = [TomaInventarioItemInline]

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('detalle', 'marca', 'get_stock_global', 'creden', 'moneda')
    search_fields = ('detalle', 'cod_prov', 'cod_fab')
    list_filter = ('marca', 'creden')
    inlines = [StockSucursalInline]

    def get_stock_global(self, obj):
        return obj.stock_global
    get_stock_global.short_description = 'Stock Global'

@admin.register(Subproducto)
class SubproductoAdmin(admin.ModelAdmin):
    list_display = ('serie', 'producto', 'sucursal', 'compra', 'venta', 'estado', 'propiedad', 'situacion')
    search_fields = ('serie', 'cuim', 'detalle')
    list_filter = ('sucursal', 'estado', 'situacion', 'propiedad', 'moneda')

@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ('producto', 'sucursal', 'tipo', 'cantidad', 'fecha_creacion', 'creado_por')
    list_filter = ('tipo', 'sucursal', 'fecha_creacion')
    readonly_fields = ('creado_por', 'modificado_por', 'fecha_creacion', 'fecha_modificacion')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.creado_por = request.user
        obj.modificado_por = request.user
        super().save_model(request, obj, form, change)

