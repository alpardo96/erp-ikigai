from django.contrib import admin
from .models import (
    ClienteProveedor, Movimiento, Compra, Venta,
    Jurisdiccion, CompraAlicuota, CompraRetPerc, OrdenCompra, OrdenCompraItem,
    Recepcion, RecepcionItem, RecepcionImputacion, CompraOCImputacion,
    RemitoInterno, RemitoInternoItem,
)


@admin.register(Jurisdiccion)
class JurisdiccionAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre')
    search_fields = ('codigo', 'nombre')
    ordering = ('codigo',)


@admin.register(ClienteProveedor)
class ClienteProveedorAdmin(admin.ModelAdmin):
    list_display = ('codigo_id', 'razon_social', 'cuit', 'tipo_entidad', 'jurisdiccion', 'saldo')
    search_fields = ('razon_social', 'cuit')
    list_filter = ('tipo_entidad', 'jurisdiccion', 'condicion_iva')

@admin.register(Movimiento)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = ('movimiento_id', 'fecha', 'tipo_mov', 'producto', 'cli_pro', 'entrada', 'salida', 'saldo')
    list_filter = ('tipo_mov', 'fecha', 'sucursal', 'empresa')
    search_fields = ('producto__nombre', 'cli_pro__razon_social', 'numero')
    readonly_fields = ('modificado',)

class CompraAlicuotaInline(admin.TabularInline):
    model = CompraAlicuota
    extra = 0


class CompraRetPercInline(admin.TabularInline):
    model = CompraRetPerc
    extra = 0


@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    list_display = ('compras_id', 'fecha', 'tipo', 'numero', 'proveedor', 'total')
    list_filter = ('tipo', 'fecha', 'empresa')
    search_fields = ('numero', 'proveedor__razon_social')
    inlines = [CompraAlicuotaInline, CompraRetPercInline]

@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ('ventas_id', 'fecha', 'tipo', 'numero', 'cliente', 'total', 'estado')
    list_filter = ('tipo', 'fecha', 'estado', 'empresa')
    search_fields = ('numero', 'cliente__razon_social')


class OrdenCompraItemInline(admin.TabularInline):
    model = OrdenCompraItem
    extra = 0
    readonly_fields = ('cantidad_recibida', 'cantidad_facturada')


@admin.register(OrdenCompra)
class OrdenCompraAdmin(admin.ModelAdmin):
    list_display = ('oc_id', 'fecha', 'punto', 'numero', 'proveedor', 'total',
                    'estado', 'estado_recepcion', 'estado_facturacion')
    list_filter = ('estado', 'estado_recepcion', 'estado_facturacion', 'fecha', 'empresa', 'sucursal')
    search_fields = ('numero', 'proveedor__razon_social')
    inlines = [OrdenCompraItemInline]


class RecepcionItemInline(admin.TabularInline):
    model = RecepcionItem
    extra = 0


@admin.register(Recepcion)
class RecepcionAdmin(admin.ModelAdmin):
    list_display = ('recepcion_id', 'fecha', 'punto', 'numero', 'origen', 'proveedor',
                    'sucursal', 'estado')
    list_filter = ('origen', 'estado', 'fecha', 'empresa', 'sucursal')
    search_fields = ('numero', 'proveedor__razon_social', 'remito_proveedor')
    inlines = [RecepcionItemInline]


@admin.register(RecepcionImputacion)
class RecepcionImputacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'recepcion_item', 'orden_item', 'cantidad')


@admin.register(CompraOCImputacion)
class CompraOCImputacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'compra_item', 'orden_item', 'cantidad')


class RemitoInternoItemInline(admin.TabularInline):
    model = RemitoInternoItem
    extra = 0
    readonly_fields = ('cantidad_recibida',)


@admin.register(RemitoInterno)
class RemitoInternoAdmin(admin.ModelAdmin):
    list_display = ('ri_id', 'fecha', 'punto', 'numero', 'sucursal_origen', 'sucursal_destino',
                    'tipo', 'estado')
    list_filter = ('estado', 'tipo', 'fecha', 'empresa', 'sucursal_origen', 'sucursal_destino')
    search_fields = ('numero',)
    inlines = [RemitoInternoItemInline]
