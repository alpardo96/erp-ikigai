"""Rutas del acopio de tabaco (Plan 081).

Nombres planos con prefijo `agro_`, siguiendo la convención del proyecto (`config_zona_add`,
`distribucion_index`) en lugar de un namespace: los ABMs se renderizan dentro de plantillas
compartidas del panel de Configuración, que resuelven las URL por nombre.
"""
from django.urls import path

from . import views_htmx as htmx

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
]
