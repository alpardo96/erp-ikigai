from django.urls import path
from .views_htmx import (
    zona_modal as dist_zona_modal, buscar_zonas as dist_buscar_zonas, eliminar_zona as dist_eliminar_zona,
    personal_modal as dist_personal_modal, buscar_personal as dist_buscar_personal, eliminar_personal as dist_eliminar_personal,
    vehiculo_modal as dist_vehiculo_modal, buscar_vehiculos as dist_buscar_vehiculos, eliminar_vehiculo as dist_eliminar_vehiculo,
    motivo_modal as dist_motivo_modal, buscar_motivos as dist_buscar_motivos, eliminar_motivo as dist_eliminar_motivo,
    sembrar_motivos_iniciales as dist_sembrar_motivos,
    asignar_vendedor as dist_asignar_vendedor,
    domicilio_modal as dist_domicilio_modal, eliminar_domicilio as dist_eliminar_domicilio,
    domicilio_dias as dist_domicilio_dias,
)
from .views import (DistribucionIndexView, AsignacionStockView, CarteraIndexView,
                                CobranzaRepartoView, ConsolidadoView, EntregaView,
                                FacturacionLoteView, FaltantesIndexView, HojaDeRutaView,
                                CobranzaVendedorView, CorrelativosDistribucionView,
                                DevolucionesReporteView, RecepcionDevolucionView,
                                RecepcionRendicionesView, RendicionRepartoView,
                                RepartoDetalleView, RepartoListView, SaldosClientesView)
from .views_movil import (
    pedido_movil as movil_pedido, movil_buscar_clientes, movil_elegir_cliente,
    movil_buscar_productos, movil_item_add, movil_item_remove, movil_descartar,
    movil_confirmar, movil_elegir_domicilio,
)

urlpatterns = [
    path('distribucion/', DistribucionIndexView.as_view(), name='distribucion_index'),

    # Distribución: toma de pedidos desde el celular del vendedor (Plan 074, fase 2)
    path('distribucion/movil/', movil_pedido, name='distribucion_movil_pedido'),
    path('distribucion/movil/clientes/', movil_buscar_clientes, name='distribucion_movil_clientes'),
    path('distribucion/movil/clientes/<int:cliente_id>/elegir/', movil_elegir_cliente, name='distribucion_movil_elegir_cliente'),
    path('distribucion/movil/domicilio/<int:domicilio_id>/elegir/', movil_elegir_domicilio, name='distribucion_movil_elegir_domicilio'),
    path('distribucion/movil/productos/', movil_buscar_productos, name='distribucion_movil_productos'),
    path('distribucion/movil/item/agregar/', movil_item_add, name='distribucion_movil_item_add'),
    path('distribucion/movil/item/<int:index>/quitar/', movil_item_remove, name='distribucion_movil_item_remove'),
    path('distribucion/movil/descartar/', movil_descartar, name='distribucion_movil_descartar'),
    path('distribucion/movil/confirmar/', movil_confirmar, name='distribucion_movil_confirmar'),

    # Distribución: repartos, hoja de ruta y consolidado (Plan 074, fase 5)
    path('distribucion/repartos/', RepartoListView.as_view(), name='distribucion_repartos'),
    path('distribucion/repartos/<int:reparto_id>/', RepartoDetalleView.as_view(), name='distribucion_reparto_detalle'),
    path('distribucion/repartos/<int:reparto_id>/hoja-de-ruta/', HojaDeRutaView.as_view(), name='distribucion_hoja_de_ruta'),
    path('distribucion/repartos/<int:reparto_id>/consolidado/', ConsolidadoView.as_view(), name='distribucion_consolidado'),

    # Distribución: entrega, devoluciones y notas de crédito (Plan 074, fase 6)
    path('distribucion/repartos/<int:reparto_id>/entrega/', EntregaView.as_view(), name='distribucion_entrega'),
    path('distribucion/paradas/<int:parada_id>/recepcion/', RecepcionDevolucionView.as_view(), name='distribucion_recepcion'),

    # Distribucion: cobranza del repartidor, rendicion y saldos (Plan 074, fase 7)
    path('distribucion/repartos/<int:reparto_id>/cobranza/', CobranzaRepartoView.as_view(), name='distribucion_cobranza'),
    path('distribucion/repartos/<int:reparto_id>/rendicion/', RendicionRepartoView.as_view(), name='distribucion_rendicion'),
    path('distribucion/saldos/', SaldosClientesView.as_view(), name='distribucion_saldos'),
    path('distribucion/rendiciones/', RecepcionRendicionesView.as_view(), name='distribucion_recepcion_rendiciones'),
    path('distribucion/cobranza-vendedor/', CobranzaVendedorView.as_view(), name='distribucion_cobranza_vendedor'),

    # Distribucion: reportes de control (Plan 074, fase 8)
    path('distribucion/devoluciones/', DevolucionesReporteView.as_view(), name='distribucion_reporte_devoluciones'),
    path('distribucion/correlativos/', CorrelativosDistribucionView.as_view(), name='distribucion_correlativos'),

    # Distribución: facturación masiva (Plan 074, fase 4)
    path('distribucion/facturacion/', FacturacionLoteView.as_view(), name='distribucion_facturacion'),

    # Distribución: faltantes y asignación de stock escaso (Plan 074, fase 3)
    path('distribucion/faltantes/', FaltantesIndexView.as_view(), name='distribucion_faltantes'),
    path('distribucion/faltantes/<int:producto_id>/asignar/', AsignacionStockView.as_view(), name='distribucion_asignacion'),

    # Distribución: cartera de vendedores y agenda de visitas (Plan 074)
    path('distribucion/cartera/', CarteraIndexView.as_view(), name='distribucion_cartera'),
    path('distribucion/cartera/<int:cliente_id>/vendedor/', dist_asignar_vendedor, name='distribucion_asignar_vendedor'),
    path('distribucion/cartera/<int:cliente_id>/domicilio/nuevo/', dist_domicilio_modal, name='distribucion_domicilio_add'),
    path('distribucion/domicilio/<int:id>/editar/', dist_domicilio_modal, name='distribucion_domicilio_edit'),
    path('distribucion/domicilio/<int:id>/eliminar/', dist_eliminar_domicilio, name='distribucion_domicilio_delete'),
    path('distribucion/domicilio/<int:id>/dias/', dist_domicilio_dias, name='distribucion_domicilio_dias'),

    # Configuración: Maestros de Distribución (Plan 074)
    path('configuracion/distribucion/zonas/buscar/', dist_buscar_zonas, name='config_zona_search'),
    path('configuracion/distribucion/zonas/crear/', dist_zona_modal, name='config_zona_add'),
    path('configuracion/distribucion/zonas/<int:id>/editar/', dist_zona_modal, name='config_zona_edit'),
    path('configuracion/distribucion/zonas/<int:id>/eliminar/', dist_eliminar_zona, name='config_zona_delete'),

    path('configuracion/distribucion/personal/buscar/', dist_buscar_personal, name='config_personal_search'),
    path('configuracion/distribucion/personal/crear/', dist_personal_modal, name='config_personal_add'),
    path('configuracion/distribucion/personal/<int:id>/editar/', dist_personal_modal, name='config_personal_edit'),
    path('configuracion/distribucion/personal/<int:id>/eliminar/', dist_eliminar_personal, name='config_personal_delete'),

    path('configuracion/distribucion/vehiculos/buscar/', dist_buscar_vehiculos, name='config_vehiculo_search'),
    path('configuracion/distribucion/vehiculos/crear/', dist_vehiculo_modal, name='config_vehiculo_add'),
    path('configuracion/distribucion/vehiculos/<int:id>/editar/', dist_vehiculo_modal, name='config_vehiculo_edit'),
    path('configuracion/distribucion/vehiculos/<int:id>/eliminar/', dist_eliminar_vehiculo, name='config_vehiculo_delete'),

    path('configuracion/distribucion/motivos/buscar/', dist_buscar_motivos, name='config_motivo_search'),
    path('configuracion/distribucion/motivos/crear/', dist_motivo_modal, name='config_motivo_add'),
    path('configuracion/distribucion/motivos/<int:id>/editar/', dist_motivo_modal, name='config_motivo_edit'),
    path('configuracion/distribucion/motivos/<int:id>/eliminar/', dist_eliminar_motivo, name='config_motivo_delete'),
    path('configuracion/distribucion/motivos/sembrar/', dist_sembrar_motivos, name='config_motivo_sembrar'),
]
