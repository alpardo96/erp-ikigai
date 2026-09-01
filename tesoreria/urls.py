from django.urls import path
from . import views
from . import views_htmx
from . import views_caja_diaria
from . import views_eoaf
from . import views_listados

urlpatterns = [
    path('', views.TesoreriaIndexView.as_view(), name='tesoreria_index'),

    # Caja Diaria (Tesorería) — reporte de movimientos de fondos y saldos disponibles
    path('caja-diaria/', views_caja_diaria.caja_diaria_index, name='caja_diaria_index'),
    path('caja-diaria/grilla/', views_caja_diaria.caja_diaria_grilla, name='caja_diaria_grilla'),
    path('caja-diaria/cerrar/', views_caja_diaria.caja_diaria_cerrar, name='caja_diaria_cerrar'),
    path('caja-diaria/excel/', views_caja_diaria.caja_diaria_excel, name='caja_diaria_excel'),
    path('caja-diaria/pdf/', views_caja_diaria.caja_diaria_pdf, name='caja_diaria_pdf'),

    # Estado de Origen y Aplicación de Fondos — el `suma_saldo_fciero` del sistema VFP
    path('origen-aplicacion-fondos/', views_eoaf.eoaf_index, name='eoaf_index'),
    path('origen-aplicacion-fondos/grilla/', views_eoaf.eoaf_grilla, name='eoaf_grilla'),
    path('origen-aplicacion-fondos/cuenta/<int:cuenta_id>/', views_eoaf.eoaf_cuenta_modal,
         name='eoaf_cuenta_modal'),
    path('origen-aplicacion-fondos/excel/', views_eoaf.eoaf_excel, name='eoaf_excel'),
    path('origen-aplicacion-fondos/pdf/', views_eoaf.eoaf_pdf, name='eoaf_pdf'),
    path('recibos/carga/', views.ReciboCargaView.as_view(), name='recibo_carga'),
    # Misma vista y mismo template: sólo cambia dónde cae la plata (Plan 077 §F).
    path('caja-mostrador/recibo/',
         views.ReciboCargaView.as_view(origen='MOSTRADOR'), name='recibo_carga_mostrador'),
    path('orden-pago/', views.OrdenPagoCargaView.as_view(), name='ordenpago_carga'),

    # Listados de comprobantes de tesorería: consulta, anulación y reimpresión (Plan 035)
    path('ordenes-pago/', views_listados.ordenes_pago_listado, name='ordenpago_listado'),
    path('ordenes-pago/grilla/', views_listados.ordenes_pago_grilla, name='ordenpago_grilla'),
    path('ordenes-pago/<int:pk>/detalle/', views_listados.orden_pago_detalle, name='ordenpago_detalle'),
    path('ordenes-pago/<int:pk>/anular/', views_listados.orden_pago_anular, name='ordenpago_anular'),
    path('ordenes-pago/<int:pk>/pdf/', views_listados.orden_pago_pdf, name='ordenpago_pdf'),

    path('recibos/', views_listados.recibos_listado, name='recibo_listado'),
    path('recibos/grilla/', views_listados.recibos_grilla, name='recibo_grilla'),
    path('recibos/<int:pk>/anular/', views_listados.recibo_anular, name='recibo_anular'),
    path('recibos/<int:pk>/pdf/', views_listados.recibo_pdf, name='recibo_pdf'),


    # Caja Mostrador
    path('caja-mostrador/', views.CajaMostradorIndexView.as_view(), name='caja_mostrador_index'),
    path('caja-mostrador/abrir/', views.CajaMostradorAbrirView.as_view(), name='caja_mostrador_abrir'),

    # HTMX
    path('htmx/buscar-entidad/<str:tipo>/', views_htmx.buscar_cliente_proveedor, name='htmx_buscar_entidad'),
    path('htmx/recibos/clientes/buscar-modal/', views_htmx.buscador_clientes_recibo_modal, name='recibo_cliente_buscar_modal'),
    path('htmx/recibos/clientes/buscar-lista/', views_htmx.lista_clientes_recibo_resultados, name='recibo_cliente_buscar_lista'),
    # Búsqueda de cuentas contables para la imputación (typeahead + lupa), compartida por
    # Recibo Simple y Orden de Pago Simple.
    path('htmx/cuentas/buscar-modal/', views_htmx.buscador_cuentas_modal, name='tesoreria_cuentas_buscar_modal'),
    path('htmx/cuentas/buscar-lista/', views_htmx.lista_cuentas_resultados, name='tesoreria_cuentas_buscar_lista'),

    path('htmx/bancos/buscar-lista/', views_htmx.lista_bancos_resultados, name='tesoreria_bancos_buscar_lista'),

    path('htmx/ordenes-pago/proveedores/buscar-modal/', views_htmx.buscador_proveedores_op_modal, name='op_proveedor_buscar_modal'),
    path('htmx/ordenes-pago/proveedores/buscar-lista/', views_htmx.lista_proveedores_op_resultados, name='op_proveedor_buscar_lista'),
    path('htmx/ordenes-pago/valores-cartera/buscar-modal/', views_htmx.buscador_valores_cartera_modal, name='op_valores_cartera_buscar_modal'),
    path('htmx/ordenes-pago/valores-cartera/buscar-lista/', views_htmx.lista_valores_cartera_resultados, name='op_valores_cartera_buscar_lista'),
    path('htmx/comprobantes-pendientes/<str:tipo>/<int:id>/', views_htmx.obtener_comprobantes_pendientes, name='htmx_comprobantes_pendientes'),
    path('htmx/procesar-recibo/', views_htmx.procesar_recibo, name='htmx_procesar_recibo'),
    path('htmx/procesar-orden-pago/', views_htmx.procesar_orden_pago, name='htmx_procesar_orden_pago'),
    path('htmx/caja-mostrador/cobrar/<int:preventa_id>/', views_htmx.caja_mostrador_cobrar_modal, name='htmx_caja_mostrador_cobrar_modal'),
    path('htmx/caja-mostrador/procesar/<int:preventa_id>/', views_htmx.caja_mostrador_procesar_cobro, name='htmx_caja_mostrador_procesar_cobro'),
    path('htmx/caja-mostrador/anular/<int:preventa_id>/', views_htmx.caja_mostrador_anular_preventa, name='htmx_caja_mostrador_anular_preventa'),
    
    # Retiros y Cierres
    path('htmx/caja-mostrador/retiro-modal/', views_htmx.caja_retiro_modal, name='caja_retiro_modal'),
    path('htmx/caja-mostrador/retiro-procesar/', views_htmx.caja_retiro_procesar, name='caja_retiro_procesar'),
    path('htmx/caja-mostrador/retiro-anular/<int:retiro_id>/', views_htmx.caja_retiro_anular, name='caja_retiro_anular'),
    path('htmx/caja-mostrador/cierre-modal/', views_htmx.caja_cierre_modal, name='caja_cierre_modal'),
    path('htmx/caja-mostrador/cierre-procesar/', views_htmx.caja_cierre_procesar, name='caja_cierre_procesar'),

    # Recepción de Rendiciones (Tesorería)
    path('rendiciones/recepcion/', views_htmx.rendiciones_recepcion, name='rendiciones_recepcion'),
    path('htmx/rendiciones/recibir-modal/<int:retiro_id>/', views_htmx.rendicion_recibir_modal, name='rendicion_recibir_modal'),
    path('htmx/rendiciones/recibir-procesar/<int:retiro_id>/', views_htmx.rendicion_recibir_procesar, name='rendicion_recibir_procesar'),
]
