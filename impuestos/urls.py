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
    ExportarLibroIvaVentasTxtView,
    ExportarLibroIvaComprasTxtView,
    ExportarLibroIvaVentasExcelView,
    ExportarLibroIvaVentasPdfView,
    ExportarLibroIvaComprasExcelView,
    ExportarLibroIvaComprasPdfView,
)

app_name = 'impuestos'

urlpatterns = [
    path('', ImpuestosIndexView.as_view(), name='impuestos_index'),
    path('cierre-periodo-iva/', CierrePeriodoIvaView.as_view(), name='cierre_periodo_iva'),
    path('periodos-cerrados/modal/', PeriodosCerradosModalView.as_view(), name='periodos_cerrados_modal'),
    path('reabrir-periodo-iva/', ReabrirPeriodoIvaView.as_view(), name='reabrir_periodo_iva'),
    path('libro-iva-ventas/', LibroIvaVentasView.as_view(), name='libro_iva_ventas'),
    path('libro-iva-ventas/exportar-txt/', ExportarLibroIvaVentasTxtView.as_view(), name='exportar_libro_iva_ventas_txt'),
    path('libro-iva-ventas/exportar-excel/', ExportarLibroIvaVentasExcelView.as_view(), name='exportar_libro_iva_ventas_excel'),
    path('libro-iva-ventas/exportar-pdf/', ExportarLibroIvaVentasPdfView.as_view(), name='exportar_libro_iva_ventas_pdf'),
    path('libro-iva-compras/', LibroIvaComprasView.as_view(), name='libro_iva_compras'),
    path('libro-iva-compras/exportar-txt/', ExportarLibroIvaComprasTxtView.as_view(), name='exportar_libro_iva_compras_txt'),
    path('libro-iva-compras/exportar-excel/', ExportarLibroIvaComprasExcelView.as_view(), name='exportar_libro_iva_compras_excel'),
    path('libro-iva-compras/exportar-pdf/', ExportarLibroIvaComprasPdfView.as_view(), name='exportar_libro_iva_compras_pdf'),
    path('mis-comprobantes-arca/', MisComprobantesArcaView.as_view(), name='mis_comprobantes_arca'),
    path('sicore-ganancias/', SicoreGananciasView.as_view(), name='sicore_ganancias'),
]

