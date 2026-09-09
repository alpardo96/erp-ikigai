"""Rutas del acopio de tabaco (Plan 081).

Nombres planos con prefijo `agro_`, siguiendo la convención del proyecto (`config_zona_add`,
`distribucion_index`) en lugar de un namespace: los ABMs se renderizan dentro de plantillas
compartidas del panel de Configuración, que resuelven las URL por nombre.
"""
from django.urls import path

from . import views
from . import views_htmx as htmx
from . import views_liquidacion as liq
from . import views_lotes as lot
from . import views_reportes as rpt
from . import views_pago as pag
from . import views_romaneo as rom

urlpatterns = [
    # Hub Principal
    path('agro/', views.agro_index, name='agro_index'),

    # Campañas
    path('agro/campanias/nueva/', htmx.campania_modal, name='agro_campania_add'),
    path('agro/campanias/<int:id>/editar/', htmx.campania_modal, name='agro_campania_edit'),
    path('agro/campanias/buscar/', htmx.buscar_campanias, name='agro_campania_buscar'),
    path('agro/campanias/<int:id>/eliminar/', htmx.eliminar_campania, name='agro_campania_del'),

    # Variedades
    path('agro/variedades/nueva/', htmx.variedad_modal, name='agro_variedad_add'),
    path('agro/variedades/<int:id>/editar/', htmx.variedad_modal, name='agro_variedad_edit'),
    path('agro/variedades/buscar/', htmx.buscar_variedades, name='agro_variedad_buscar'),
    path('agro/variedades/<int:id>/eliminar/', htmx.eliminar_variedad, name='agro_variedad_del'),

    # Clases
    path('agro/clases/nueva/', htmx.clase_modal, name='agro_clase_add'),
    path('agro/clases/<int:id>/editar/', htmx.clase_modal, name='agro_clase_edit'),
    path('agro/clases/buscar/', htmx.buscar_clases, name='agro_clase_buscar'),
    path('agro/clases/<int:id>/eliminar/', htmx.eliminar_clase, name='agro_clase_del'),

    # Listas de precio
    path('agro/listas-precio/nueva/', htmx.lista_precio_modal, name='agro_lista_precio_add'),
    path('agro/listas-precio/<int:id>/editar/', htmx.lista_precio_modal, name='agro_lista_precio_edit'),
    path('agro/listas-precio/buscar/', htmx.buscar_listas_precio, name='agro_lista_precio_buscar'),
    path('agro/listas-precio/<int:id>/eliminar/', htmx.eliminar_lista_precio, name='agro_lista_precio_del'),

    # Conceptos de retención
    path('agro/retenciones/nueva/', htmx.retencion_modal, name='agro_retencion_add'),
    path('agro/retenciones/<int:id>/editar/', htmx.retencion_modal, name='agro_retencion_edit'),
    path('agro/retenciones/buscar/', htmx.buscar_retenciones, name='agro_retencion_buscar'),
    path('agro/retenciones/<int:id>/eliminar/', htmx.eliminar_retencion, name='agro_retencion_del'),

    # Configuración del acopio
    path('agro/config-tabaco/', htmx.configuracion_tabaco, name='agro_config_tabaco_guardar'),

    # --- ROMANEO (Plan 082) -------------------------------------------------
    path('agro/romaneos/', rom.romaneo_listado, name='agro_romaneo_listado'),
    path('agro/romaneos/grilla/', rom.romaneo_grilla, name='agro_romaneo_grilla'),
    path('agro/romaneos/nuevo/', rom.romaneo_nuevo, name='agro_romaneo_nuevo'),
    path('agro/romaneos/<int:pk>/carga/', rom.romaneo_carga, name='agro_romaneo_carga'),
    path('agro/romaneos/<int:pk>/', rom.romaneo_detalle, name='agro_romaneo_detalle'),
    path('agro/romaneos/<int:pk>/imprimir/', rom.romaneo_imprimir, name='agro_romaneo_imprimir'),
    path('agro/romaneos/<int:pk>/confirmar/', rom.romaneo_confirmar, name='agro_romaneo_confirmar'),
    path('agro/romaneos/<int:pk>/anular/', rom.romaneo_anular, name='agro_romaneo_anular'),

    # Fardos
    path('agro/romaneos/<int:pk>/fardos/cotizar/', rom.fardo_cotizar, name='agro_fardo_cotizar'),
    path('agro/romaneos/<int:pk>/fardos/agregar/', rom.fardo_agregar, name='agro_fardo_agregar'),
    path('agro/romaneos/<int:pk>/clases/typeahead/', rom.clase_typeahead, name='agro_clase_typeahead'),
    path('agro/fardos/<int:pk>/quitar/', rom.fardo_quitar, name='agro_fardo_quitar'),
    path('agro/fardos/<int:pk>/reclasificar/', rom.fardo_reclasificar, name='agro_fardo_reclasificar'),

    # --- LIQUIDACIÓN DE COMPRA (Plan 083) -----------------------------------
    path('agro/liquidaciones/', liq.liquidacion_listado, name='agro_liquidacion_listado'),
    path('agro/liquidaciones/grilla/', liq.liquidacion_grilla, name='agro_liquidacion_grilla'),
    path('agro/liquidaciones/nueva/', liq.liquidacion_nueva, name='agro_liquidacion_nueva'),
    path('agro/liquidaciones/pendientes/', liq.liquidacion_pendientes, name='agro_liquidacion_pendientes'),
    path('agro/liquidaciones/<int:pk>/', liq.liquidacion_detalle, name='agro_liquidacion_detalle'),
    path('agro/liquidaciones/<int:pk>/imprimir/', liq.liquidacion_imprimir, name='agro_liquidacion_imprimir'),
    path('agro/liquidaciones/<int:pk>/anular/', liq.liquidacion_anular, name='agro_liquidacion_anular'),

    # --- PAGO AL PRODUCTOR (Plan 084) ---------------------------------------
    path('agro/pagos/', pag.pago_listado, name='agro_pago_listado'),
    path('agro/pagos/grilla/', pag.pago_grilla, name='agro_pago_grilla'),
    path('agro/pagos/nuevo/', pag.pago_nuevo, name='agro_pago_nuevo'),
    path('agro/pagos/pendientes/', pag.pago_pendientes, name='agro_pago_pendientes'),
    path('agro/pagos/<int:pk>/', pag.pago_detalle, name='agro_pago_detalle'),
    path('agro/pagos/<int:pk>/anular/', pag.pago_anular, name='agro_pago_anular'),
    path('agro/certificados/<int:pk>/', pag.pago_certificado, name='agro_pago_certificado'),

    # --- STOCK (Plan 085) ---------------------------------------------------
    path('agro/stock/conciliacion/', pag.stock_conciliacion, name='agro_stock_conciliacion'),
    path('agro/stock/recalcular/', pag.stock_recalcular, name='agro_stock_recalcular'),

    # --- LOTES DE ACOPIO (Plan 086) -----------------------------------------
    path('agro/lotes/', lot.lote_listado, name='agro_lote_listado'),
    path('agro/lotes/grilla/', lot.lote_grilla, name='agro_lote_grilla'),
    path('agro/lotes/nuevo/', lot.lote_nuevo, name='agro_lote_nuevo'),
    path('agro/lotes/<int:pk>/', lot.lote_detalle, name='agro_lote_detalle'),
    path('agro/lotes/<int:pk>/panel/', lot.lote_panel_fardos, name='agro_lote_panel'),
    path('agro/lotes/<int:pk>/armar/', lot.lote_armar, name='agro_lote_armar'),
    path('agro/lotes/<int:pk>/anular/', lot.lote_anular, name='agro_lote_anular'),

    # Armado: Typeahead + Lupa sobre los fardos comprados sin lote
    path('agro/lotes/<int:pk>/fardos/typeahead/', lot.fardo_typeahead,
         name='agro_lote_fardo_typeahead'),
    path('agro/lotes/<int:pk>/fardos/agregar/', lot.fardo_agregar, name='agro_lote_fardo_agregar'),
    path('agro/lotes/<int:pk>/fardos/<int:fardo_pk>/quitar/', lot.fardo_quitar,
         name='agro_lote_fardo_quitar'),

    # Venta: vincula la factura ya emitida por el circuito de siempre
    path('agro/lotes/<int:pk>/venta/', lot.lote_venta, name='agro_lote_venta'),
    path('agro/lotes/<int:pk>/venta/quitar/', lot.lote_venta_quitar,
         name='agro_lote_venta_quitar'),

    # --- ACONDICIONAMIENTO (Plan 086) ---------------------------------------
    path('agro/lotes/<int:pk>/acondicionar/', lot.acond_nuevo, name='agro_acond_nuevo'),
    path('agro/acondicionamientos/<int:pk>/', lot.acond_detalle, name='agro_acond_detalle'),
    path('agro/acondicionamientos/<int:pk>/panel/', lot.acond_panel, name='agro_acond_panel'),
    path('agro/acondicionamientos/<int:pk>/cerrar/', lot.acond_cerrar, name='agro_acond_cerrar'),
    path('agro/acondicionamientos/<int:pk>/anular/', lot.acond_anular, name='agro_acond_anular'),
    path('agro/acondicionamientos/<int:pk>/costos/agregar/', lot.acond_costo_agregar,
         name='agro_acond_costo_agregar'),
    path('agro/acondicionamientos/<int:pk>/costos/<int:linea_pk>/quitar/', lot.acond_costo_quitar,
         name='agro_acond_costo_quitar'),
    path('agro/acondicionamientos/<int:pk>/coproductos/agregar/', lot.acond_coproducto_agregar,
         name='agro_acond_coproducto_agregar'),
    path('agro/acondicionamientos/<int:pk>/coproductos/<int:linea_pk>/quitar/',
         lot.acond_coproducto_quitar, name='agro_acond_coproducto_quitar'),
    path('agro/productos/typeahead/', lot.producto_typeahead, name='agro_producto_typeahead'),

    # --- MARGEN (Plan 086) --------------------------------------------------
    path('agro/margen/', lot.margen_listado, name='agro_margen'),
    path('agro/margen/grilla/', lot.margen_grilla, name='agro_margen_grilla'),
    path('agro/margen/lote/<int:pk>/', lot.margen_del_lote, name='agro_margen_lote'),

    # --- REPORTES OFICIALES Y GERENCIALES (Plan 087) ------------------------
    path('agro/reportes/', rpt.reportes_index, name='agro_reportes'),

    # Planilla FET — el reformateo del `Informe_fet` heredado
    path('agro/reportes/fet/', rpt.fet, name='agro_reporte_fet'),
    path('agro/reportes/fet/grilla/', rpt.fet_grilla, name='agro_reporte_fet_grilla'),
    path('agro/reportes/fet/csv/', rpt.fet_csv, name='agro_reporte_fet_csv'),
    path('agro/reportes/fet/xlsx/', rpt.fet_xlsx, name='agro_reporte_fet_xlsx'),

    # Resumen de acopio por variedad y clase
    path('agro/reportes/acopio/', rpt.acopio, name='agro_reporte_acopio'),
    path('agro/reportes/acopio/grilla/', rpt.acopio_grilla, name='agro_reporte_acopio_grilla'),
    path('agro/reportes/acopio/csv/', rpt.acopio_csv, name='agro_reporte_acopio_csv'),

    # DDJJ de existencias por galpón, a una fecha de corte
    path('agro/reportes/existencias/', rpt.existencias, name='agro_reporte_existencias'),
    path('agro/reportes/existencias/grilla/', rpt.existencias_grilla,
         name='agro_reporte_existencias_grilla'),
    path('agro/reportes/existencias/csv/', rpt.existencias_csv,
         name='agro_reporte_existencias_csv'),

    # Libro de retenciones practicadas
    path('agro/reportes/retenciones/', rpt.retenciones, name='agro_reporte_retenciones'),
    path('agro/reportes/retenciones/grilla/', rpt.retenciones_grilla,
         name='agro_reporte_retenciones_grilla'),
    path('agro/reportes/retenciones/csv/', rpt.retenciones_csv,
         name='agro_reporte_retenciones_csv'),

    # Tableros de margen
    path('agro/reportes/tablero/', rpt.tablero, name='agro_reporte_tablero'),
    path('agro/reportes/tablero/grilla/', rpt.tablero_grilla, name='agro_reporte_tablero_grilla'),
    path('agro/reportes/tablero/csv/', rpt.tablero_csv, name='agro_reporte_tablero_csv'),

    # Procesos de acondicionamiento (maestro — resuelve DA-07 por configuración)
    path('agro/procesos/nuevo/', htmx.proceso_modal, name='agro_proceso_add'),
    path('agro/procesos/<int:id>/editar/', htmx.proceso_modal, name='agro_proceso_edit'),
    path('agro/procesos/buscar/', htmx.buscar_procesos, name='agro_proceso_buscar'),
    path('agro/procesos/<int:id>/eliminar/', htmx.eliminar_proceso, name='agro_proceso_del'),
]
