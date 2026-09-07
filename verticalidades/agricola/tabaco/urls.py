"""Rutas del acopio de tabaco (Plan 081).

Nombres planos con prefijo `agro_`, siguiendo la convención del proyecto (`config_zona_add`,
`distribucion_index`) en lugar de un namespace: los ABMs se renderizan dentro de plantillas
compartidas del panel de Configuración, que resuelven las URL por nombre.
"""
from django.urls import path

from . import views_htmx as htmx
from . import views_liquidacion as liq
from . import views_romaneo as rom

urlpatterns = [
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
]
