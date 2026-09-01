from django.urls import path
from .views import (
    ImpuestosIndexView,
    CierrePeriodoIvaView,
    PeriodosCerradosModalView,
    ReabrirPeriodoIvaView,
    LibroIvaVentasView,
    LibroIvaComprasView,
    MisComprobantesArcaView,
    SicoreGananciasView,
)

app_name = 'impuestos'

urlpatterns = [
    path('', ImpuestosIndexView.as_view(), name='impuestos_index'),
    path('cierre-periodo-iva/', CierrePeriodoIvaView.as_view(), name='cierre_periodo_iva'),
    path('periodos-cerrados/modal/', PeriodosCerradosModalView.as_view(), name='periodos_cerrados_modal'),
    path('reabrir-periodo-iva/', ReabrirPeriodoIvaView.as_view(), name='reabrir_periodo_iva'),
    path('libro-iva-ventas/', LibroIvaVentasView.as_view(), name='libro_iva_ventas'),
    path('libro-iva-compras/', LibroIvaComprasView.as_view(), name='libro_iva_compras'),
    path('mis-comprobantes-arca/', MisComprobantesArcaView.as_view(), name='mis_comprobantes_arca'),
    path('sicore-ganancias/', SicoreGananciasView.as_view(), name='sicore_ganancias'),
]
