from django.urls import path
from .views import (
    SubproductoTrazabilidadListView, trazabilidad_modal_timeline,
    subproducto_detalle_modal, movimiento_detalle_modal, subproducto_editar_modal,
    ComprasTrazabilidadCargaView, compras_trazabilidad_item_add,
    compras_trazabilidad_item_remove, typeahead_series_trazabilidad,
    VentasTrazabilidadCargaView, agregar_item_venta_trazabilidad,
    editar_item_venta_trazabilidad, quitar_item_venta_trazabilidad,
    verificar_reserva_cliente, ReservaArmaListView,
    reserva_arma_anular_modal, reserva_arma_anular_procesar
)

urlpatterns = [
    # Stock Trazabilidad
    path('stock/trazabilidad/', SubproductoTrazabilidadListView.as_view(), name='subproducto_trazabilidad_listado'),
    path('stock/trazabilidad/modal/<str:serie>/', trazabilidad_modal_timeline, name='subproducto_trazabilidad_modal'),
    path('stock/trazabilidad/subproducto/<int:subpro_id>/detalle/', subproducto_detalle_modal, name='subproducto_detalle_modal'),
    path('stock/trazabilidad/movimiento/<int:subpro_id>/detalle/', movimiento_detalle_modal, name='movimiento_detalle_modal'),
    path('stock/trazabilidad/subproducto/<int:subpro_id>/editar/', subproducto_editar_modal, name='subproducto_editar_modal'),

    # Compras Trazabilidad
    path('compras/trazabilidad/carga/', ComprasTrazabilidadCargaView.as_view(), name='compras_trazabilidad_carga'),
    path('compras/trazabilidad/item/agregar/', compras_trazabilidad_item_add, name='compras_trazabilidad_item_add'),
    path('compras/trazabilidad/item/<int:index>/quitar/', compras_trazabilidad_item_remove, name='compras_trazabilidad_item_remove'),
    path('series/trazabilidad/typeahead/', typeahead_series_trazabilidad, name='typeahead_series_trazabilidad'),

    # Ventas Trazabilidad
    path('ventas/trazabilidad/carga/', VentasTrazabilidadCargaView.as_view(), name='ventas_trazabilidad_carga'),
    path('ventas/trazabilidad/item/agregar/', agregar_item_venta_trazabilidad, name='ventas_trazabilidad_item_add'),
    path('ventas/trazabilidad/item/<int:index>/editar/', editar_item_venta_trazabilidad, name='ventas_trazabilidad_item_edit'),
    path('ventas/trazabilidad/item/<int:index>/quitar/', quitar_item_venta_trazabilidad, name='ventas_trazabilidad_item_remove'),
    path('ventas/trazabilidad/verificar-reserva/', verificar_reserva_cliente, name='armeria_verificar_reserva_cliente'),

    # Reservas de Armas (SIGIMAC)
    path('reservas/sigimac/', ReservaArmaListView.as_view(), name='armeria_reservas_list'),
    path('reservas/sigimac/<int:reserva_id>/anular/modal/', reserva_arma_anular_modal, name='armeria_reserva_anular_modal'),
    path('reservas/sigimac/<int:reserva_id>/anular/procesar/', reserva_arma_anular_procesar, name='armeria_reserva_anular_procesar'),
]
