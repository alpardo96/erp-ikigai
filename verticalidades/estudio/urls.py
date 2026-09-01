from django.urls import path
from facturacion.views_estudio import actualizar_tarifas, api_tarifas, guardar_tarifas, facturacion_lotes, api_facturacion_lotes, generar_lote_facturacion

urlpatterns = [
    path('estudio/tarifas/', actualizar_tarifas, name='estudio_actualizar_tarifas'),
    path('estudio/tarifas/api/', api_tarifas, name='estudio_api_tarifas'),
    path('estudio/tarifas/guardar/', guardar_tarifas, name='estudio_guardar_tarifas'),
    
    path('estudio/facturacion-lotes/', facturacion_lotes, name='estudio_facturacion_lotes'),
    path('estudio/facturacion-lotes/api/', api_facturacion_lotes, name='estudio_api_facturacion_lotes'),
    path('estudio/facturacion-lotes/generar/', generar_lote_facturacion, name='estudio_generar_lote_facturacion'),
]
