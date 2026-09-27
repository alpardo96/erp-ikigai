from django.urls import path
from . import views

urlpatterns = [
    # Fincas / Establecimientos
    path('agro/fincas/', views.fincas_listado, name='agro_fincas_listado'),
    path('agro/fincas/nueva/', views.finca_modal, name='agro_finca_add'),
    path('agro/fincas/<int:id>/editar/', views.finca_modal, name='agro_finca_edit'),
    path('agro/fincas/<int:id>/eliminar/', views.finca_eliminar, name='agro_finca_del'),

    # Secciones / Lotes de Cultivo
    path('agro/secciones/', views.secciones_listado, name='agro_secciones_listado'),
    path('agro/secciones/nueva/', views.seccion_modal, name='agro_seccion_add'),
    path('agro/secciones/<int:id>/editar/', views.seccion_modal, name='agro_seccion_edit'),
    path('agro/secciones/<int:id>/eliminar/', views.seccion_eliminar, name='agro_seccion_del'),

    # Cultivos / Variedades
    path('agro/cultivos/', views.cultivos_listado, name='agro_cultivos_listado'),
    path('agro/cultivos/nuevo/', views.cultivo_modal, name='agro_cultivo_add'),
    path('agro/cultivos/<int:id>/editar/', views.cultivo_modal, name='agro_cultivo_edit'),
    path('agro/cultivos/<int:id>/eliminar/', views.cultivo_eliminar, name='agro_cultivo_del'),

    # Labores y Tareas Culturales en Campo
    path('agro/labores/', views.labores_listado, name='agro_labores_listado'),
]

