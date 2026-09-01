from datetime import datetime
from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Sum

from contable.models import LibroIvaCompras, LibroIvaVentas
from .services import (
    calcular_liquidacion_iva,
    cerrar_periodo_iva,
    reabrir_periodo_iva,
    obtener_periodos_cerrados,
    importar_archivo_mis_comprobantes_arca,
    conciliar_mis_comprobantes_arca,
    obtener_reporte_conciliacion_arca,
)

# =========================================================================
# VISTAS DEL MÓDULO DE IMPUESTOS
# =========================================================================

class ImpuestosIndexView(LoginRequiredMixin, TemplateView):
    """
    Vista principal/Dashboard del módulo de Impuestos.
    Muestra accesos rápidos e información resumida de los procesos fiscales.
    """
    template_name = 'impuestos/index.html'


class CierrePeriodoIvaView(LoginRequiredMixin, View):
    """
    Vista para la consulta, liquidación mensual y cierre de Período IVA.
    """
    template_name = 'impuestos/cierre_periodo_iva.html'

    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        if not empresa_id:
            messages.warning(request, "Por favor, seleccione una empresa primero.")
            return redirect('seleccion_empresa')

        now = datetime.now()
        try:
            anio = int(request.GET.get('anio', now.year))
        except (TypeError, ValueError):
            anio = now.year

        try:
            mes = int(request.GET.get('mes', now.month))
        except (TypeError, ValueError):
            mes = now.month

        liquidacion = calcular_liquidacion_iva(empresa_id, anio, mes)

        return render(request, self.template_name, {
            'anio': anio,
            'mes': mes,
            'liq': liquidacion,
        })

    def post(self, request):
        empresa_id = request.session.get('empresa_id')
        if not empresa_id:
            messages.warning(request, "Por favor, seleccione una empresa primero.")
            return redirect('seleccion_empresa')

        now = datetime.now()
        anio = int(request.POST.get('anio', now.year))
        mes = int(request.POST.get('mes', now.month))

        try:
            periodo_cerrado = cerrar_periodo_iva(empresa_id, anio, mes, request.user)
            messages.success(request, f"¡Éxito! El período IVA {periodo_cerrado.periodo} fue cerrado correctamente.")
        except Exception as e:
            messages.error(request, f"Error al cerrar el período IVA: {str(e)}")

        return redirect(f"{request.path}?anio={anio}&mes={mes}")


class PeriodosCerradosModalView(LoginRequiredMixin, View):
    """
    Modal HTMX que despliega el listado de todos los períodos IVA cerrados de la empresa.
    """
    template_name = 'impuestos/modals/periodos_cerrados_modal.html'

    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        periodos = obtener_periodos_cerrados(empresa_id) if empresa_id else []
        return render(request, self.template_name, {'periodos': periodos})


class ReabrirPeriodoIvaView(LoginRequiredMixin, View):
    """
    Acción POST para reabrir un período IVA previamente cerrado.
    """
    def post(self, request):
        empresa_id = request.session.get('empresa_id')
        periodo_yyyymm = request.POST.get('periodo', '').strip()

        if not empresa_id or not periodo_yyyymm:
            messages.error(request, "Parámetros insuficientes para reabrir el período.")
            return redirect('impuestos:cierre_periodo_iva')

        try:
            reabrir_periodo_iva(empresa_id, periodo_yyyymm, request.user)
            messages.success(request, f"El período IVA {periodo_yyyymm} ha sido reabierto exitosamente.")
        except Exception as e:
            messages.error(request, f"Error al reabrir el período IVA: {str(e)}")

        return redirect('impuestos:cierre_periodo_iva')


class LibroIvaVentasView(LoginRequiredMixin, View):
    """
    Vista para la consulta y exportación del Libro IVA Ventas por Período Fiscal (YYYYMM).
    """
    template_name = 'impuestos/libro_iva_ventas.html'

    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        if not empresa_id:
            messages.warning(request, "Por favor, seleccione una empresa primero.")
            return redirect('seleccion_empresa')

        now = datetime.now()
        try:
            anio = int(request.GET.get('anio', now.year))
        except (TypeError, ValueError):
            anio = now.year

        try:
            mes = int(request.GET.get('mes', now.month))
        except (TypeError, ValueError):
            mes = now.month

        periodo_yyyymm = f"{anio}{mes:02d}"

        # Consulta de Libro IVA Ventas filtrada por Período Fiscal YYYYMM
        comprobantes = LibroIvaVentas.objects.filter(
            empresa_id=empresa_id,
            periodo=periodo_yyyymm
        ).select_related('clienteproveedor').order_by('fecha', 'punto', 'numero')

        # Fallback de seguridad por fecha del mes si el campo periodo aún no estuviese poblado
        if not comprobantes.exists():
            comprobantes = LibroIvaVentas.objects.filter(
                empresa_id=empresa_id,
                fecha__year=anio,
                fecha__month=mes
            ).select_related('clienteproveedor').order_by('fecha', 'punto', 'numero')

        totales = comprobantes.aggregate(
            tot_neto=Sum('neto_gravado'),
            tot_exento=Sum('exento'),
            tot_no_gravado=Sum('no_gravado'),
            tot_iva=Sum('iva_total'),
            tot_otros=Sum('otros'),
            tot_total=Sum('total')
        )

        return render(request, self.template_name, {
            'anio': anio,
            'mes': mes,
            'periodo': periodo_yyyymm,
            'comprobantes': comprobantes,
            'totales': totales,
        })


class LibroIvaComprasView(LoginRequiredMixin, View):
    """
    Vista para la consulta y exportación del Libro IVA Compras por Período Fiscal (YYYYMM).
    """
    template_name = 'impuestos/libro_iva_compras.html'

    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        if not empresa_id:
            messages.warning(request, "Por favor, seleccione una empresa primero.")
            return redirect('seleccion_empresa')

        now = datetime.now()
        try:
            anio = int(request.GET.get('anio', now.year))
        except (TypeError, ValueError):
            anio = now.year

        try:
            mes = int(request.GET.get('mes', now.month))
        except (TypeError, ValueError):
            mes = now.month

        periodo_yyyymm = f"{anio}{mes:02d}"

        # Consulta de Libro IVA Compras filtrada por Período Fiscal YYYYMM
        comprobantes = LibroIvaCompras.objects.filter(
            empresa_id=empresa_id,
            periodo=periodo_yyyymm
        ).select_related('clienteproveedor').order_by('fecha', 'punto', 'numero')

        # Fallback por fecha si se requiere
        if not comprobantes.exists():
            comprobantes = LibroIvaCompras.objects.filter(
                empresa_id=empresa_id,
                fecha__year=anio,
                fecha__month=mes
            ).select_related('clienteproveedor').order_by('fecha', 'punto', 'numero')

        totales = comprobantes.aggregate(
            tot_neto=Sum('neto_gravado'),
            tot_exento=Sum('exento'),
            tot_no_gravado=Sum('no_gravado'),
            tot_iva=Sum('iva_total'),
            tot_otros=Sum('otros'),
            tot_total=Sum('total')
        )

        return render(request, self.template_name, {
            'anio': anio,
            'mes': mes,
            'periodo': periodo_yyyymm,
            'comprobantes': comprobantes,
            'totales': totales,
        })


class MisComprobantesArcaView(LoginRequiredMixin, View):
    """
    Vista para la captura, importación y conciliación bi-direccional
    de Mis Comprobantes ARCA (Emitidos y Recibidos) vs Libro IVA.
    """
    template_name = 'impuestos/mis_comprobantes_arca.html'

    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        if not empresa_id:
            messages.warning(request, "Por favor, seleccione una empresa primero.")
            return redirect('seleccion_empresa')

        now = datetime.now()
        try:
            anio = int(request.GET.get('anio', now.year))
        except (TypeError, ValueError):
            anio = now.year

        try:
            mes = int(request.GET.get('mes', now.month))
        except (TypeError, ValueError):
            mes = now.month

        origen = request.GET.get('origen', 'C').upper().strip()
        if origen not in ('C', 'V'):
            origen = 'C'

        periodo_yyyymm = f"{anio}{mes:02d}"

        # Re-conciliar automáticamente para refrescar coincidencias
        conciliar_mis_comprobantes_arca(empresa_id, origen, periodo_yyyymm)

        reporte = obtener_reporte_conciliacion_arca(empresa_id, origen, periodo_yyyymm)

        return render(request, self.template_name, {
            'anio': anio,
            'mes': mes,
            'periodo': periodo_yyyymm,
            'origen': origen,
            'reporte': reporte,
        })

    def post(self, request):
        empresa_id = request.session.get('empresa_id')
        if not empresa_id:
            messages.warning(request, "Por favor, seleccione una empresa primero.")
            return redirect('seleccion_empresa')

        origen = request.POST.get('tipo_operacion', 'C').upper().strip()
        if origen not in ('C', 'V'):
            origen = 'C'

        archivo = request.FILES.get('archivo_arca')
        if not archivo:
            messages.error(request, "Por favor, adjunte un archivo CSV o Excel de Mis Comprobantes ARCA.")
            return redirect('impuestos:mis_comprobantes_arca')

        try:
            res = importar_archivo_mis_comprobantes_arca(empresa_id, origen, archivo, request.user)
            messages.success(
                request,
                f"¡Procesamiento exitoso! Se importaron {res['total_importados']} comprobantes "
                f"y se ejecutó la conciliación bi-direccional con el Libro IVA."
            )
        except Exception as e:
            messages.error(request, f"Error al procesar la planilla de ARCA: {str(e)}")

        return redirect(f"{request.path}?origen={origen}")


class SicoreGananciasView(LoginRequiredMixin, TemplateView):
    """
    Vista para la exportación de retenciones practicadas SICORE (Impuesto a las Ganancias RG 830).
    """
    template_name = 'impuestos/sicore_ganancias.html'
