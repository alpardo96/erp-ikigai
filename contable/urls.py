from django.urls import path
from .views import (
    ContableIndexView, LibroDiarioView, LibroMayorView, BalanceView, SaldosMensualesView,
)
from .views_htmx import (
    libro_diario_rows, detalle_asiento, anular_asiento, asiento_modal, detalle_asiento_modal, asiento_editar_modal,
    libro_mayor_rows, mayor_cuenta_modal, balance_sumas_saldos, typeahead_cuentas,
    saldos_mensuales_datos, exportar_cuentas_excel_completo, modal_capturar_cuentas_excel, capturar_cuentas_excel
)
from .views_reportes import (
    exportar_diario, exportar_mayor, exportar_balance, exportar_saldos_mensuales,
    exportar_diario_pdf_view, exportar_mayor_pdf_view, exportar_balance_pdf_view,
    exportar_mayor_csv
)
from .views_htmx import cerrar_ejercicio_modal, ejecutar_cierre_ejercicio

urlpatterns = [
    path('', ContableIndexView.as_view(), name='contable_index'),

    # Vistas dedicadas (páginas completas con tarjetas)
    path('libro-diario/', LibroDiarioView.as_view(), name='contable_libro_diario'),
    path('libro-mayor/', LibroMayorView.as_view(), name='contable_libro_mayor'),
    path('balance/', BalanceView.as_view(), name='contable_balance'),

    # Libro Diario y Asientos (HTMX)
    path('diario/filas/', libro_diario_rows, name='libro_diario_rows'),
    path('diario/<int:id>/detalle/', detalle_asiento, name='detalle_asiento'),
    path('diario/<int:id>/anular/', anular_asiento, name='anular_asiento'),
    path('asientos/crear/', asiento_modal, name='asiento_add'),
    path('asientos/modal/<int:asiento_id>/', detalle_asiento_modal, name='detalle_asiento_modal'),
    path('asientos/<int:asiento_id>/editar/modal/', asiento_editar_modal, name='asiento_editar_modal'),
    path('diario/exportar-excel/', exportar_diario, name='exportar_diario_excel'),
    path('diario/exportar-pdf/', exportar_diario_pdf_view, name='exportar_diario_pdf'),

    # Libro Mayor (HTMX)
    path('mayor/filas/', libro_mayor_rows, name='libro_mayor_rows'),
    path('mayor/modal/<int:cuenta_id>/', mayor_cuenta_modal, name='mayor_cuenta_modal'),
    path('mayor/exportar-excel/', exportar_mayor, name='exportar_mayor_excel'),
    path('mayor/exportar-csv/', exportar_mayor_csv, name='exportar_mayor_csv'),
    path('mayor/exportar-pdf/', exportar_mayor_pdf_view, name='exportar_mayor_pdf'),

    # Balance de Saldos Mensuales (Plan 047)
    path('saldos-mensuales/', SaldosMensualesView.as_view(), name='contable_saldos_mensuales'),
    path('saldos-mensuales/datos/', saldos_mensuales_datos, name='saldos_mensuales_datos'),
    path('saldos-mensuales/exportar-excel/', exportar_saldos_mensuales, name='exportar_saldos_mensuales_excel'),

    # Balance (HTMX)
    path('balance/datos/', balance_sumas_saldos, name='balance_sumas_saldos'),
    path('balance/exportar-excel/', exportar_balance, name='exportar_balance_excel'),
    path('balance/exportar-pdf/', exportar_balance_pdf_view, name='exportar_balance_pdf'),

    # Typeahead
    path('htmx/typeahead/cuentas/', typeahead_cuentas, name='typeahead_cuentas_contable'),

    # Cierre de Ejercicio
    path('ejercicio/cierre/modal/', cerrar_ejercicio_modal, name='cerrar_ejercicio_modal'),
    path('ejercicio/cierre/ejecutar/', ejecutar_cierre_ejercicio, name='ejecutar_cierre_ejercicio'),

    # Excel Plan de Cuentas
    path('cuentas/exportar-excel/', exportar_cuentas_excel_completo, name='contable_cuentas_exportar_excel'),
    path('cuentas/capturar-modal/', modal_capturar_cuentas_excel, name='contable_cuentas_modal_capturar_excel'),
    path('cuentas/capturar/', capturar_cuentas_excel, name='contable_cuentas_capturar_excel'),
]
