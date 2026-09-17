"""
Rutas del submódulo Agrícola -> Granos.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('granos/mapeos/', views.mapeos_config_view, name='agricola_granos_mapeos'),
    path('granos/liquidaciones/importar/', views.importar_lpg_view, name='agricola_granos_importar_lpg'),
]
