from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from usuarios.views import HomeView, SeleccionEmpresaView, CambiarEjercicioView
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from core.views_config import ConfiguracionIndexView, guardar_configuracion_trazabilidad
from empresas.views_htmx import empresa_modal, buscar_empresas, eliminar_empresa, sucursal_modal, buscar_sucursales, eliminar_sucursal, ejercicio_modal, buscar_ejercicios, eliminar_ejercicio, cotizaciones_modal, punto_venta_modal, buscar_puntos_venta, eliminar_punto_venta
from usuarios.views_htmx import usuario_modal, buscar_usuarios, eliminar_usuario, rol_modal, buscar_roles, eliminar_rol
from facturacion.views import ClientesProveedoresIndexView, ComprasIndexView, VentasIndexView, ComprasCargaView, VentasCargaView, PreventaCargaView, AutorizacionesIndexView, ComprasListView, CompraBajaView, CompraDetalleModalView, VentasListView, VentaAnularModalView, VentaEmitirNotaCreditoView, VentaPrevisualizarModalView, VentaSincronizarClienteView
from facturacion.views_procesamiento import CargaCompraAutomaticaView, ProcesarRecorteOCRView
from facturacion.views_ia import CargaCompraIAView, ProcesarFacturaIAView
from facturacion.views_impresion import imprimir_factura, imprimir_preventa
from facturacion.views_reportes import (
    ReporteVentasProductoView, buscar_reporte_ventas_producto,
    exportar_ventas_producto_csv, exportar_ventas_producto_excel,
    exportar_clientes_excel
)
from facturacion.views_oc import (
    OrdenCompraCargaView, OrdenCompraListView, OrdenCompraBajaView, OrdenCompraImprimirView,
    OcItemAddView, OcItemEditView, OcItemRemoveView,
    FacturaOcAvisoView, FacturaVincularOcModalView, FacturaVincularOcView,
    FacturaVincularRecepcionModalView, FacturaVincularRecepcionView,
    FacturaCotejoEditView, FacturaCotejoRemoveView,
    OrdenCompraLegajoView, FacturaDesafectarOcView, CorrelativosAuditoriaView,
)
from facturacion.views_recepcion import (
    RecepcionCargaView, RecepcionListView, RecepcionImprimirView,
    RecepcionVincularOcModalView, RecepcionVincularOcView,
    RecItemAddView, RecItemEditView, RecItemRemoveView, RecepcionBajaView,
)
from facturacion.views_remito_interno import (
    RemitoInternoCargaView, RemitoInternoListView, RemitoInternoBajaView, RemitoInternoImprimirView,
    RiItemAddView, RiItemEditView, RiItemRemoveView, ri_buscar_subproducto_por_serie, ri_buscar_producto_por_id,
    RecepcionInternaCargaView, RecepcionInternaListView, RecepcionInternaVincularModalView, RecepcionInternaVincularView,
    ReciItemEditView, ReciItemRemoveView, StockTransitoView, RecepcionInternaImprimirView,
)

from productos.views import StockDashboardView, ProductoListView
from facturacion.views_htmx import (
    jurisdiccion_modal, buscar_jurisdicciones, eliminar_jurisdiccion,
    cliente_modal, buscar_clientes, eliminar_cliente, buscar_cuentas_facturacion, buscador_cuentas_modal,
    verificar_documento_existente, consultar_padron_afip,
    comprobante_modal, buscar_comprobantes, eliminar_comprobante,
    buscador_productos_modal, lista_productos_resultados, buscar_producto_por_codigo, buscar_producto_por_codprov, actualizar_proveedor_habitual, agregar_item_sesion, quitar_item_sesion, editar_item_sesion, modal_series_item, guardar_series_item,
    importar_remito_items, buscador_remitos_modal, compras_revisar_precios,
    buscador_productos_venta_modal, buscar_producto_venta_por_codigo, lista_productos_venta_resultados,
    agregar_item_venta_sesion, quitar_item_venta_sesion, editar_item_venta_sesion,
    buscador_clientes_venta_modal, lista_clientes_venta_resultados, info_cliente_preventa, venta_cliente_detalle,
    preventas_item_add, preventas_item_remove, editar_item_preventa_sesion, preventa_autorizacion_modal, venta_autorizacion_modal,
    buscar_comprobante_por_codigo, buscador_comprobantes_modal, lista_comprobantes_resultados, tipo_comprobante_modal,
    typeahead_clientes, typeahead_productos_venta, typeahead_productos_compra, typeahead_comprobantes
)
from facturacion.views_facturas_pendientes import (
    facturas_pendientes_listado, facturas_pendientes_grilla,
    facturas_pendientes_excel, facturas_pendientes_pdf,
)
from productos.views_htmx import (
    buscar_productos, producto_modal, eliminar_producto,
    marca_modal, buscar_marcas, eliminar_marca,
    rubro_prod_modal, buscar_rubros_prod, eliminar_rubro_prod,
    familia_modal, buscar_familias, eliminar_familia,
    subfamilia_modal, buscar_subfamilias, eliminar_subfamilia,
    obtener_margen, filtrar_familias, filtrar_subfamilias,
    exportar_productos_excel_completo,
    modal_capturar_excel, capturar_productos_excel
)
from tesoreria.views_htmx import (
    buscar_mediospago, mediopago_modal, eliminar_mediopago,
    buscar_cuentas_bancarias, cuenta_bancaria_modal, eliminar_cuenta_bancaria
)
from contable.views_htmx import (
    cuenta_modal, buscar_cuentas, eliminar_cuenta, parametros_contables_modal,
    exportar_cuentas_excel_completo, modal_capturar_cuentas_excel, capturar_cuentas_excel
)


urlpatterns = [
    path('admin/', admin.site.norm_admin_site.urls if hasattr(admin.site, 'norm_admin_site') else admin.site.urls),
    
    # Auth
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Core
    path('', HomeView.as_view(), name='home'),
    path('seleccion/', SeleccionEmpresaView.as_view(), name='seleccion_empresa'),
    path('cambiar-ejercicio/', CambiarEjercicioView.as_view(), name='cambiar_ejercicio'),
    # Configuración Custom (HTMX y UI)
    path('configuracion/', ConfiguracionIndexView.as_view(), name='configuracion_index'),
    path('configuracion/parametros-contables/', parametros_contables_modal, name='config_parametros_contables'),
    path('configuracion/cotizaciones/', cotizaciones_modal, name='config_cotizaciones'),
    path('configuracion/trazabilidad-guardar/', guardar_configuracion_trazabilidad, name='config_trazabilidad_save'),
    
    # Empresas HTMX
    path('configuracion/empresas/buscar/', buscar_empresas, name='config_empresa_search'),
    path('configuracion/empresas/crear/', empresa_modal, name='config_empresa_add'),
    path('configuracion/empresas/<int:id>/editar/', empresa_modal, name='config_empresa_edit'),
    path('configuracion/empresas/<int:id>/eliminar/', eliminar_empresa, name='config_empresa_delete'),

    # Sucursales HTMX
    path('configuracion/sucursales/buscar/', buscar_sucursales, name='config_sucursal_search'),
    path('configuracion/sucursales/crear/', sucursal_modal, name='config_sucursal_add'),
    path('configuracion/sucursales/<int:id>/editar/', sucursal_modal, name='config_sucursal_edit'),
    path('configuracion/sucursales/<int:id>/eliminar/', eliminar_sucursal, name='config_sucursal_delete'),

    # Puntos de Venta HTMX
    path('configuracion/puntos_venta/buscar/', buscar_puntos_venta, name='config_puntoventa_search'),
    path('configuracion/puntos_venta/crear/', punto_venta_modal, name='config_puntoventa_add'),
    path('configuracion/puntos_venta/<int:id>/editar/', punto_venta_modal, name='config_puntoventa_edit'),
    path('configuracion/puntos_venta/<int:id>/eliminar/', eliminar_punto_venta, name='config_puntoventa_delete'),

    # Ejercicios Fiscales HTMX
    path('configuracion/ejercicios/buscar/', buscar_ejercicios, name='config_ejercicio_search'),
    path('configuracion/ejercicios/crear/', ejercicio_modal, name='config_ejercicio_add'),
    path('configuracion/ejercicios/<int:id>/editar/', ejercicio_modal, name='config_ejercicio_edit'),
    path('configuracion/ejercicios/<int:id>/eliminar/', eliminar_ejercicio, name='config_ejercicio_delete'),

    # Usuarios HTMX
    path('configuracion/usuarios/buscar/', buscar_usuarios, name='config_usuario_search'),
    path('configuracion/usuarios/crear/', usuario_modal, name='config_usuario_add'),
    path('configuracion/usuarios/<int:id>/editar/', usuario_modal, name='config_usuario_edit'),
    path('configuracion/usuarios/<int:id>/eliminar/', eliminar_usuario, name='config_usuario_delete'),

    # Roles HTMX
    path('configuracion/roles/buscar/', buscar_roles, name='config_rol_search'),
    path('configuracion/roles/crear/', rol_modal, name='config_rol_add'),
    path('configuracion/roles/<int:id>/editar/', rol_modal, name='config_rol_edit'),
    path('configuracion/roles/<int:id>/eliminar/', eliminar_rol, name='config_rol_delete'),

    # Módulos Core
    path('clientes/', ClientesProveedoresIndexView.as_view(), name='clientes_index'),
    path('stock/', StockDashboardView.as_view(), name='stock_index'),
    path('stock/productos/', ProductoListView.as_view(), name='producto_listado'),
    path('stock/', StockDashboardView.as_view(), name='stock_index'),
    path('stock/productos/', ProductoListView.as_view(), name='producto_listado'),


    # ── COMPRAS ──────────────────────────────────────────────────
    path('compras/', ComprasIndexView.as_view(), name='compras_index'),
    path('compras/carga/', ComprasCargaView.as_view(), name='compras_carga'),

    # ── ÓRDENES DE COMPRA (Plan 028) ─────────────────────────────
    path('compras/ordenes/', OrdenCompraListView.as_view(), name='oc_listado'),
    path('compras/ordenes/nueva/', OrdenCompraCargaView.as_view(), name='oc_carga'),
    path('compras/ordenes/<int:oc_id>/anular/', OrdenCompraBajaView.as_view(), name='oc_baja'),
    path('compras/ordenes/<int:oc_id>/imprimir/', OrdenCompraImprimirView.as_view(), name='oc_imprimir'),
    path('compras/ordenes/item/agregar/', OcItemAddView.as_view(), name='oc_item_add'),
    path('compras/ordenes/item/<int:index>/editar/', OcItemEditView.as_view(), name='oc_item_edit'),
    path('compras/ordenes/item/<int:index>/quitar/', OcItemRemoveView.as_view(), name='oc_item_remove'),
    # Integración OC ↔ Factura de compra (Fase 5)
    path('compras/factura/oc-aviso/', FacturaOcAvisoView.as_view(), name='factura_oc_aviso'),
    path('compras/factura/vincular-oc/modal/', FacturaVincularOcModalView.as_view(), name='factura_vincular_oc_modal'),
    path('compras/factura/vincular-oc/', FacturaVincularOcView.as_view(), name='factura_vincular_oc'),
    path('compras/factura/vincular-recepcion/modal/', FacturaVincularRecepcionModalView.as_view(), name='factura_vincular_recepcion_modal'),
    path('compras/factura/vincular-recepcion/', FacturaVincularRecepcionView.as_view(), name='factura_vincular_recepcion'),
    path('compras/factura/cotejo/<int:index>/editar/', FacturaCotejoEditView.as_view(), name='factura_cotejo_edit'),
    path('compras/factura/cotejo/<int:index>/quitar/', FacturaCotejoRemoveView.as_view(), name='factura_cotejo_remove'),
    # Legajo de OC + desafectación (Fase 7)
    path('compras/ordenes/<int:oc_id>/legajo/', OrdenCompraLegajoView.as_view(), name='oc_legajo'),
    path('compras/correlativos/auditoria/', CorrelativosAuditoriaView.as_view(), name='correlativos_auditoria'),
    path('compras/ordenes/<int:oc_id>/desafectar-factura/<int:compra_id>/', FacturaDesafectarOcView.as_view(), name='factura_desafectar_oc'),

    # ── CIRCUITO INTERNO: REMITO INTERNO + RECEPCIÓN INTERNA (Plan 028 Fase 6) ──
    path('compras/remitos-internos/', RemitoInternoListView.as_view(), name='remito_interno_listado'),
    path('compras/remitos-internos/nuevo/', RemitoInternoCargaView.as_view(), name='remito_interno_carga'),
    path('compras/remitos-internos/<int:ri_id>/anular/', RemitoInternoBajaView.as_view(), name='remito_interno_baja'),
    path('compras/remitos-internos/<int:ri_id>/imprimir/', RemitoInternoImprimirView.as_view(), name='remito_interno_imprimir'),
    path('compras/remitos-internos/item/agregar/', RiItemAddView.as_view(), name='ri_item_add'),
    path('compras/remitos-internos/buscar-serie/', ri_buscar_subproducto_por_serie, name='ri_buscar_serie'),
    path('compras/remitos-internos/buscar-producto-id/', ri_buscar_producto_por_id, name='ri_buscar_producto_id'),
    path('compras/remitos-internos/item/<int:index>/editar/', RiItemEditView.as_view(), name='ri_item_edit'),
    path('compras/remitos-internos/item/<int:index>/quitar/', RiItemRemoveView.as_view(), name='ri_item_remove'),
    path('compras/recepcion-interna/', RecepcionInternaListView.as_view(), name='recepcion_interna_listado'),
    path('compras/recepcion-interna/nueva/', RecepcionInternaCargaView.as_view(), name='recepcion_interna_carga'),
    path('compras/recepcion-interna/<int:rec_id>/imprimir/', RecepcionInternaImprimirView.as_view(), name='recepcion_interna_imprimir'),
    path('compras/recepcion-interna/vincular/modal/', RecepcionInternaVincularModalView.as_view(), name='recepcion_interna_vincular_modal'),
    path('compras/recepcion-interna/vincular/', RecepcionInternaVincularView.as_view(), name='recepcion_interna_vincular'),
    path('compras/recepcion-interna/item/<int:index>/editar/', ReciItemEditView.as_view(), name='reci_item_edit'),
    path('compras/recepcion-interna/item/<int:index>/quitar/', ReciItemRemoveView.as_view(), name='reci_item_remove'),
    path('compras/stock-transito/', StockTransitoView.as_view(), name='stock_transito'),

    # ── INFORMES DE RECEPCIÓN (Plan 028) ─────────────────────────
    path('compras/recepciones/', RecepcionListView.as_view(), name='recepcion_listado'),
    path('compras/recepciones/nueva/', RecepcionCargaView.as_view(), name='recepcion_carga'),
    path('compras/recepciones/<int:recepcion_id>/anular/', RecepcionBajaView.as_view(), name='recepcion_baja'),
    path('compras/recepciones/<int:recepcion_id>/imprimir/', RecepcionImprimirView.as_view(), name='recepcion_imprimir'),
    path('compras/recepciones/vincular-oc/modal/', RecepcionVincularOcModalView.as_view(), name='recepcion_vincular_oc_modal'),
    path('compras/recepciones/vincular-oc/', RecepcionVincularOcView.as_view(), name='recepcion_vincular_oc'),
    path('compras/recepciones/item/agregar/', RecItemAddView.as_view(), name='rec_item_add'),
    path('compras/recepciones/item/<int:index>/editar/', RecItemEditView.as_view(), name='rec_item_edit'),
    path('compras/recepciones/item/<int:index>/quitar/', RecItemRemoveView.as_view(), name='rec_item_remove'),
    path('compras/listado/', ComprasListView.as_view(), name='compras_listado'),
    path('compras/<int:compra_id>/baja/', CompraBajaView.as_view(), name='compras_baja'),
    path('compras/<int:compra_id>/detalle/modal/', CompraDetalleModalView.as_view(), name='compras_detalle_modal'),
    path('compras/carga-automatica/', CargaCompraAutomaticaView.as_view(), name='compras_carga_automatica'),
    path('compras/procesar-recorte/', ProcesarRecorteOCRView.as_view(), name='procesar_recorte_ocr'),
    path('compras/carga-ia/', CargaCompraIAView.as_view(), name='compras_carga_ia'),
    path('compras/procesar-ia/', ProcesarFacturaIAView.as_view(), name='compras_procesar_ia'),
    path('compras/procesar-ia/', ProcesarFacturaIAView.as_view(), name='compras_procesar_ia'),

    # 🔹 VENTAS 🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹
    path('ventas/', VentasIndexView.as_view(), name='ventas_index'),
    path('ventas/listado/', VentasListView.as_view(), name='ventas_listado'),
    path('ventas/<int:id>/sincronizar-cliente/', VentaSincronizarClienteView.as_view(), name='venta_sincronizar_cliente'),
    path('ventas/<int:id>/anular/modal/', VentaAnularModalView.as_view(), name='venta_anular_modal'),
    path('ventas/<int:id>/previsualizar/modal/', VentaPrevisualizarModalView.as_view(), name='venta_previsualizar_modal'),
    path('ventas/<int:id>/anular/procesar/', VentaEmitirNotaCreditoView.as_view(), name='venta_emitir_nc'),
    path('ventas/carga/', VentasCargaView.as_view(), name='ventas_carga'),
    path('ventas/carga/', VentasCargaView.as_view(), name='ventas_carga'),
    path('ventas/autorizaciones/', AutorizacionesIndexView.as_view(), name='autorizaciones_index'),
    path('ventas/preventas/autorizaciones/<int:id>/modal/', preventa_autorizacion_modal, name='preventas_autorizacion_modal'),
    path('ventas/preventas/carga/', PreventaCargaView.as_view(), name='preventas_carga'),
    path('ventas/preventas/cliente-info/', info_cliente_preventa, name='preventas_cliente_info'),
    path('ventas/preventas/item/agregar/', preventas_item_add, name='preventas_item_add'),
    path('ventas/preventas/item/<int:index>/editar/', editar_item_preventa_sesion, name='preventas_item_edit'),
    path('ventas/preventas/item/<int:index>/quitar/', preventas_item_remove, name='preventas_item_remove'),
    path('ventas/productos/buscar-modal/', buscador_productos_venta_modal, name='ventas_producto_buscar_modal'),
    path('ventas/productos/buscar-codigo/', buscar_producto_venta_por_codigo, name='ventas_producto_buscar_codigo'),
    path('ventas/productos/buscar-lista/', lista_productos_venta_resultados, name='ventas_producto_buscar_lista'),
    path('ventas/item/agregar/', agregar_item_venta_sesion, name='ventas_item_add'),
    path('ventas/item/<int:index>/editar/', editar_item_venta_sesion, name='ventas_item_edit'),
    path('ventas/autorizaciones-venta/<int:id>/modal/', venta_autorizacion_modal, name='ventas_autorizacion_modal'),
    path('ventas/item/<int:index>/quitar/', quitar_item_venta_sesion, name='ventas_item_remove'),
    path('ventas/clientes/buscar-modal/', buscador_clientes_venta_modal, name='ventas_cliente_buscar_modal'),
    path('ventas/clientes/buscar-lista/', lista_clientes_venta_resultados, name='ventas_cliente_buscar_lista'),
    path('ventas/cliente-detalle/<int:id>/', venta_cliente_detalle, name='venta_cliente_detalle'),

    # ── REPORTE DE VENTAS POR PRODUCTO (Plan 039) ──
    path('ventas/reportes/productos-vendidos/', ReporteVentasProductoView.as_view(), name='reporte_ventas_producto'),
    path('ventas/reportes/productos-vendidos/buscar/', buscar_reporte_ventas_producto, name='reporte_ventas_producto_search'),
    path('ventas/reportes/productos-vendidos/exportar-csv/', exportar_ventas_producto_csv, name='reporte_ventas_producto_csv'),
    path('ventas/reportes/productos-vendidos/exportar-excel/', exportar_ventas_producto_excel, name='reporte_ventas_producto_excel'),

    # ── FACTURAS PENDIENTES (Plan 056 — réplica del VFP `tran_facturas_pendientes`) ──
    # Las cuatro son GET y de sólo lectura: el listado no escribe en la base.
    path('facturas-pendientes/', facturas_pendientes_listado, name='facturas_pendientes'),
    path('facturas-pendientes/grilla/', facturas_pendientes_grilla, name='facturas_pendientes_grilla'),
    path('facturas-pendientes/exportar-excel/', facturas_pendientes_excel, name='facturas_pendientes_excel'),
    path('facturas-pendientes/exportar-pdf/', facturas_pendientes_pdf, name='facturas_pendientes_pdf'),

    path('facturacion/imprimir/<int:venta_id>/', imprimir_factura, name='imprimir_factura'),
    path('facturacion/imprimir-preventa/<int:preventa_id>/', imprimir_preventa, name='imprimir_preventa'),

    path('contable/', include('contable.urls')),
    path('tesoreria/', include('tesoreria.urls')),
    path('impuestos/', include('impuestos.urls')),


    # Clientes/Proveedores ABM (HTMX)
    path('clientes/buscar/', buscar_clientes, name='cliente_search'),
    path('clientes/exportar-excel/', exportar_clientes_excel, name='clientes_exportar_excel'),
    path('clientes/buscar_cuentas/', buscar_cuentas_facturacion, name='buscar_cuentas_facturacion'),
    path('clientes/buscar_cuentas_modal/', buscador_cuentas_modal, name='buscador_cuentas_modal'),

    path('clientes/crear/', cliente_modal, name='cliente_add'),
    path('clientes/<int:id>/editar/', cliente_modal, name='cliente_edit'),
    path('htmx/verificar-documento/', verificar_documento_existente, name='htmx_verificar_documento'),
    path('htmx/consultar-afip/<str:cuit>/', consultar_padron_afip, name='htmx_consultar_afip'),
    path('clientes/<int:id>/eliminar/', eliminar_cliente, name='cliente_delete'),

    # Configuración: Jurisdicciones
    path('configuracion/jurisdicciones/buscar/', buscar_jurisdicciones, name='config_jurisdiccion_search'),
    path('configuracion/jurisdicciones/crear/', jurisdiccion_modal, name='config_jurisdiccion_add'),
    path('configuracion/jurisdicciones/<int:id>/editar/', jurisdiccion_modal, name='config_jurisdiccion_edit'),
    path('configuracion/jurisdicciones/<int:id>/eliminar/', eliminar_jurisdiccion, name='config_jurisdiccion_delete'),

    # Configuración: Tipos de Comprobante
    path('configuracion/comprobantes/buscar/', buscar_comprobantes, name='config_comprobante_search'),
    path('configuracion/comprobantes/crear/', comprobante_modal, name='config_comprobante_add'),
    path('configuracion/comprobantes/<int:id>/editar/', comprobante_modal, name='config_comprobante_edit'),
    path('configuracion/comprobantes/<int:id>/eliminar/', eliminar_comprobante, name='config_comprobante_delete'),

    # Configuración: Medios de Pago (Tesorería)
    path('configuracion/mediospago/buscar/', buscar_mediospago, name='config_mediopago_search'),
    path('configuracion/mediospago/crear/', mediopago_modal, name='config_mediopago_add'),
    path('configuracion/mediospago/<int:id>/editar/', mediopago_modal, name='config_mediopago_edit'),
    path('configuracion/mediospago/<int:id>/eliminar/', eliminar_mediopago, name='config_mediopago_delete'),
    # Configuración: Cuentas Bancarias (Tesorería)
    path('configuracion/cuentasbancarias/buscar/', buscar_cuentas_bancarias, name='config_cuentabancaria_search'),
    path('configuracion/cuentasbancarias/crear/', cuenta_bancaria_modal, name='config_cuentabancaria_add'),
    path('configuracion/cuentasbancarias/<int:id>/editar/', cuenta_bancaria_modal, name='config_cuentabancaria_edit'),
    path('configuracion/cuentasbancarias/<int:id>/eliminar/', eliminar_cuenta_bancaria, name='config_cuentabancaria_delete'),

    # Configuración: Cuentas Contables (Contabilidad)
    path('configuracion/cuentascontables/buscar/', buscar_cuentas, name='config_cuentacontable_search'),
    path('configuracion/cuentascontables/crear/', cuenta_modal, name='config_cuentacontable_add'),
    path('configuracion/cuentascontables/<int:id>/editar/', cuenta_modal, name='config_cuentacontable_edit'),
    path('configuracion/cuentascontables/<int:id>/eliminar/', eliminar_cuenta, name='config_cuentacontable_delete'),
    path('configuracion/cuentascontables/exportar-excel/', exportar_cuentas_excel_completo, name='config_cuentacontable_exportar_excel'),
    path('configuracion/cuentascontables/capturar-modal/', modal_capturar_cuentas_excel, name='config_cuentacontable_modal_capturar_excel'),
    path('configuracion/cuentascontables/capturar/', capturar_cuentas_excel, name='config_cuentacontable_capturar_excel'),

    # Configuración Productos (Marca, Rubro, Familia)
    path('configuracion/marcas/buscar/', buscar_marcas, name='config_marca_search'),
    path('configuracion/marcas/crear/', marca_modal, name='config_marca_add'),
    path('configuracion/marcas/<int:id>/editar/', marca_modal, name='config_marca_edit'),
    path('configuracion/marcas/<int:id>/eliminar/', eliminar_marca, name='config_marca_delete'),

    path('configuracion/rubros-prod/buscar/', buscar_rubros_prod, name='config_rubro_prod_search'),
    path('configuracion/rubros-prod/crear/', rubro_prod_modal, name='config_rubro_prod_add'),
    path('configuracion/rubros-prod/<int:id>/editar/', rubro_prod_modal, name='config_rubro_prod_edit'),
    path('configuracion/rubros-prod/<int:id>/eliminar/', eliminar_rubro_prod, name='config_rubro_prod_delete'),

    path('configuracion/familias/buscar/', buscar_familias, name='config_familia_search'),
    path('configuracion/familias/crear/', familia_modal, name='config_familia_add'),
    path('configuracion/familias/<int:id>/editar/', familia_modal, name='config_familia_edit'),
    path('configuracion/familias/<int:id>/eliminar/', eliminar_familia, name='config_familia_delete'),

    path('configuracion/subfamilias/buscar/', buscar_subfamilias, name='config_subfamilia_search'),
    path('configuracion/subfamilias/crear/', subfamilia_modal, name='config_subfamilia_add'),
    path('configuracion/subfamilias/<int:id>/editar/', subfamilia_modal, name='config_subfamilia_edit'),
    path('configuracion/subfamilias/<int:id>/eliminar/', eliminar_subfamilia, name='config_subfamilia_delete'),

    path('productos/obtener-margen/', obtener_margen, name='producto_obtener_margen'),
    path('productos/filtrar-familias/', filtrar_familias, name='producto_filtrar_familias'),
    path('productos/filtrar-subfamilias/', filtrar_subfamilias, name='producto_filtrar_subfamilias'),

    # Productos HTMX
    path('productos/buscar/', buscar_productos, name='producto_search'),
    path('productos/crear/', producto_modal, name='producto_add'),
    path('productos/<int:id>/editar/', producto_modal, name='producto_edit'),
    path('productos/<int:id>/eliminar/', eliminar_producto, name='producto_delete'),
    path('productos/excel/exportar-completo/', exportar_productos_excel_completo, name='producto_exportar_excel_completo'),
    path('productos/excel/modal-capturar/', modal_capturar_excel, name='producto_modal_capturar_excel'),
    path('productos/excel/capturar/', capturar_productos_excel, name='producto_capturar_excel'),

    # Productos Compras HTMX
    path('compras/productos/buscar-modal/', buscador_productos_modal, name='compras_producto_buscar_modal'),
    path('compras/productos/buscar-codigo/', buscar_producto_por_codigo, name='compras_producto_buscar_codigo'),
    path('compras/productos/buscar-codprov/', buscar_producto_por_codprov, name='compras_producto_buscar_codprov'),
    path('compras/productos/actualizar-habitual/', actualizar_proveedor_habitual, name='compras_producto_actualizar_habitual'),
    path('compras/productos/buscar-lista/', lista_productos_resultados, name='compras_producto_buscar_lista'),
    path('compras/item/agregar/', agregar_item_sesion, name='compras_item_add'),
    path('compras/item/<int:index>/editar/', editar_item_sesion, name='compras_item_edit'),
    path('compras/item/<int:index>/quitar/', quitar_item_sesion, name='compras_item_remove'),
    path('compras/item/<int:index>/series/', modal_series_item, name='compras_item_series_modal'),
    path('compras/item/<int:index>/series/guardar/', guardar_series_item, name='compras_item_series_save'),
    path('compras/revisar-precios/', compras_revisar_precios, name='compras_revisar_precios'),
    path('compras/remito/importar/', importar_remito_items, name='compras_remito_importar'),
    path('compras/remito/buscar-modal/', buscador_remitos_modal, name='compras_remito_buscar_modal'),
    path('compras/comprobantes/buscar-codigo/', buscar_comprobante_por_codigo, name='compras_comprobante_buscar_codigo'),
    path('compras/comprobantes/buscar-modal/', buscador_comprobantes_modal, name='compras_comprobante_buscar_modal'),
    path('compras/comprobantes/nuevo/', tipo_comprobante_modal, name='tipo_comprobante_add'),
    path('compras/comprobantes/buscar-lista/', lista_comprobantes_resultados, name='compras_comprobante_buscar_lista'),

    # Typeahead (autocompletado inline)
    path('htmx/typeahead/clientes/', typeahead_clientes, name='typeahead_clientes'),
    path('htmx/typeahead/productos-venta/', typeahead_productos_venta, name='typeahead_productos_venta'),
    path('htmx/typeahead/productos-compra/', typeahead_productos_compra, name='typeahead_productos_compra'),
    path('htmx/typeahead/comprobantes/', typeahead_comprobantes, name='typeahead_comprobantes'),
]

# AUTO-DESCUBRIMIENTO DE RUTAS DE VERTICALIDADES
# =========================================================================
from pathlib import Path
verticalidades_path = Path(settings.BASE_DIR) / 'verticalidades'
if verticalidades_path.exists() and verticalidades_path.is_dir():
    for item in verticalidades_path.iterdir():
        if item.is_dir() and (item / '__init__.py').exists() and (item / 'urls.py').exists():
            app_name = item.name
            urlpatterns.append(
                path('', include(f'verticalidades.{app_name}.urls'))
            )

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
