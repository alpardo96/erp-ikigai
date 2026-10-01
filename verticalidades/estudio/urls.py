from django.urls import path
from verticalidades.estudio.views import (
    actualizar_tarifas, api_tarifas, guardar_tarifas,
    exportar_tarifas_excel, importar_tarifas_excel,
    facturacion_lotes, api_facturacion_lotes, generar_lote_facturacion,
    envios_facturas, api_envios_facturas, api_enviar_pendientes, api_reenviar_factura,
    estudio_envio_editar_modal, estudio_envio_guardar_edicion,
    config_mails_modal, config_mails_guardar, config_mails_probar
)

urlpatterns = [
    path('estudio/tarifas/', actualizar_tarifas, name='estudio_actualizar_tarifas'),
    path('estudio/tarifas/api/', api_tarifas, name='estudio_api_tarifas'),
    path('estudio/tarifas/guardar/', guardar_tarifas, name='estudio_guardar_tarifas'),
    path('estudio/tarifas/exportar-excel/', exportar_tarifas_excel, name='estudio_exportar_tarifas_excel'),
    path('estudio/tarifas/importar-excel/', importar_tarifas_excel, name='estudio_importar_tarifas_excel'),
    
    path('estudio/facturacion-lotes/', facturacion_lotes, name='estudio_facturacion_lotes'),
    path('estudio/facturacion-lotes/api/', api_facturacion_lotes, name='estudio_api_facturacion_lotes'),
    path('estudio/facturacion-lotes/generar/', generar_lote_facturacion, name='estudio_generar_lote_facturacion'),

    path('estudio/envios-facturas/', envios_facturas, name='estudio_envios_facturas'),
    path('estudio/envios-facturas/api/', api_envios_facturas, name='estudio_api_envios_facturas'),
    path('estudio/envios-facturas/enviar-pendientes/', api_enviar_pendientes, name='estudio_api_enviar_pendientes'),
    path('estudio/envios-facturas/reenviar/<int:envio_id>/', api_reenviar_factura, name='estudio_api_reenviar_factura'),
    path('estudio/envios-facturas/editar/<int:envio_id>/', estudio_envio_editar_modal, name='estudio_envio_editar_modal'),
    path('estudio/envios-facturas/guardar-edicion/<int:envio_id>/', estudio_envio_guardar_edicion, name='estudio_envio_guardar_edicion'),

    path('estudio/config-mails/modal/', config_mails_modal, name='estudio_config_mails_modal'),
    path('estudio/config-mails/guardar/', config_mails_guardar, name='estudio_config_mails_guardar'),
    path('estudio/config-mails/probar/', config_mails_probar, name='estudio_config_mails_probar'),
]

