from django.shortcuts import render
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin


class ContableIndexView(LoginRequiredMixin, TemplateView):
    """Vista landing del módulo contable con tarjetas de acceso."""
    template_name = 'contable/index.html'


class LibroDiarioView(LoginRequiredMixin, TemplateView):
    """Vista dedicada del Libro Diario."""
    template_name = 'contable/libro_diario.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from empresas.models import Ejercicio
        from contable.models import condic_opciones
        from django.utils import timezone

        # El Libro Diario muestra TODOS los condic, estructurales incluidos: es el registro
        # cronológico completo y la apertura/refundición/cierre tienen que poder verse.
        context['condic_opciones'] = condic_opciones()

        empresa_id = self.request.session.get('empresa_id')
        ejercicio = Ejercicio.objects.filter(empresa_id=empresa_id).order_by('-inicio').first()
        if ejercicio:
            context['fecha_inicio'] = ejercicio.inicio.strftime('%Y-%m-%d')
            fecha_hasta = min(ejercicio.cierre, timezone.localdate())
            context['fecha_cierre'] = fecha_hasta.strftime('%Y-%m-%d')
        else:
            hoy = timezone.localdate()
            context['fecha_inicio'] = hoy.replace(day=1).strftime('%Y-%m-%d')
            context['fecha_cierre'] = hoy.strftime('%Y-%m-%d')

        return context


class LibroMayorView(LoginRequiredMixin, TemplateView):
    """Vista dedicada del Libro Mayor."""
    template_name = 'contable/libro_mayor.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from contable.models import Cuenta, condic_opciones
        from facturacion.models import ClienteProveedor
        from empresas.models import Ejercicio, Sucursal
        from contable.services.reportes_mayor import COLUMNAS_MAYOR_CATALOGO, obtener_columnas_seleccionadas
        from django.utils import timezone

        context['condic_opciones'] = condic_opciones()
        context['condics_predeterminados'] = ['1', '2', '5']
        context['catalogo_columnas'] = COLUMNAS_MAYOR_CATALOGO
        context['columnas_seleccionadas'] = obtener_columnas_seleccionadas(self.request)

        empresa_id = self.request.session.get('empresa_id')

        cuentas_imputables = Cuenta.objects.filter(
            empresa_id=empresa_id, imputable=1
        ).order_by('jerarquia')
        
        context['cuentas_imputables'] = cuentas_imputables
        context['clientes_proveedores'] = ClienteProveedor.objects.filter(
            empresa_id=empresa_id
        ).order_by('razon_social')
        
        context['sucursales'] = Sucursal.objects.filter(empresa_id=empresa_id).order_by('nombre')
        
        if cuentas_imputables.exists():
            primera = cuentas_imputables.first()
            ultima = cuentas_imputables.last()
            context['primera_cuenta_id'] = primera.id
            context['primera_cuenta_display'] = f"{primera.jerarquia} - {primera.cuenta}"
            context['ultima_cuenta_id'] = ultima.id
            context['ultima_cuenta_display'] = f"{ultima.jerarquia} - {ultima.cuenta}"
        
        ejercicio = Ejercicio.objects.filter(empresa_id=empresa_id).order_by('-inicio').first()
        if ejercicio:
            context['fecha_inicio'] = ejercicio.inicio.strftime('%Y-%m-%d')
            fecha_hasta = min(ejercicio.cierre, timezone.localdate())
            context['fecha_cierre'] = fecha_hasta.strftime('%Y-%m-%d')
            
        return context


class SaldosMensualesView(LoginRequiredMixin, TemplateView):
    """Balance de Saldos Mensuales: apertura + movimiento neto de cada mes + saldo al cierre."""
    template_name = 'contable/saldos_mensuales.html'

    def get(self, request, *args, **kwargs):
        # Los filtros llegan por HTMX y sólo repintan la grilla.
        if request.headers.get('HX-Request') == 'true':
            from contable.views_htmx import saldos_mensuales_datos
            return saldos_mensuales_datos(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from contable.views_htmx import get_saldos_mensuales_context
        context.update(get_saldos_mensuales_context(self.request))
        return context


class BalanceView(LoginRequiredMixin, TemplateView):
    """Vista dedicada del Balance de Sumas y Saldos."""
    template_name = 'contable/balance.html'

    def get(self, request, *args, **kwargs):
        # Si es petición HTMX (filtro de fecha), devolver solo el partial
        if request.headers.get('HX-Request') == 'true':
            from contable.views_htmx import balance_sumas_saldos
            return balance_sumas_saldos(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from contable.views_htmx import get_balance_context
        balance_context = get_balance_context(self.request)
        context.update(balance_context)
        return context
