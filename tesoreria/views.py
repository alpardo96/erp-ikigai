from django.shortcuts import render
from django.views.generic import TemplateView, View
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from empresas.models import Sucursal
from tesoreria.models import MedioPago, CuentaBancaria, Banco

class TesoreriaIndexView(LoginRequiredMixin, TemplateView):
    template_name = 'tesoreria/index.html'

class ReciboCargaView(LoginRequiredMixin, TemplateView):
    """Emisión de recibos. La MISMA pantalla para el Tesorero y para el cajero.

    Lo único que cambia es DÓNDE cae la plata, y con eso la cuenta contable (Plan 077 §F):

      - `origen = 'TESORERIA'` → la caja de Tesorería. Es el del menú principal.
      - `origen = 'MOSTRADOR'` → la sesión de caja abierta del cajero, porque **él tiene que
        rendir lo que cobra**.

    No hay pantalla nueva ni lógica duplicada: dos URLs apuntan a esta vista con distinto
    `origen`, y `procesar_recibo()` resuelve la sesión con ese dato.
    """

    template_name = 'tesoreria/recibo_carga.html'
    origen = 'TESORERIA'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['origen'] = self.origen
        empresa_id = self.request.session.get('empresa_id')
        sucursales = Sucursal.objects.filter(empresa_id=empresa_id)
        sucursal_id = self.request.session.get('sucursal_id')
        if sucursal_id and not sucursales.filter(id=sucursal_id).exists():
            sucursal_id = None
        context['sucursales'] = sucursales
        context['selected_sucursal_id'] = sucursal_id or getattr(sucursales.first(), 'id', '')
        context['medios_pago'] = MedioPago.objects.filter(empresa_id=empresa_id, activo=True)
        context['cuentas_bancarias'] = CuentaBancaria.objects.filter(empresa_id=empresa_id)
        context['bancos'] = Banco.objects.all().order_by('nombre')
        from contable.models import Cuenta
        context['cuentas_contables'] = Cuenta.objects.filter(empresa_id=empresa_id, imputable=1).order_by('jerarquia')
        context['fecha_actual'] = timezone.localdate()
        
        from empresas.models import CotizacionMoneda
        cotiz = CotizacionMoneda.objects.filter(empresa_id=empresa_id).first()
        context['dolar_cobranza'] = cotiz.dolar_cobranza if cotiz else 1.0
        
        return context

class OrdenPagoCargaView(LoginRequiredMixin, TemplateView):
    template_name = 'tesoreria/ordenpago_carga.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        empresa_id = self.request.session.get('empresa_id')
        sucursales = Sucursal.objects.filter(empresa_id=empresa_id)
        sucursal_id = self.request.session.get('sucursal_id')
        if sucursal_id and not sucursales.filter(id=sucursal_id).exists():
            sucursal_id = None
        context['sucursales'] = sucursales
        context['selected_sucursal_id'] = sucursal_id or getattr(sucursales.first(), 'id', '')
        context['medios_pago'] = MedioPago.objects.filter(empresa_id=empresa_id, activo=True)
        context['cuentas_bancarias'] = CuentaBancaria.objects.filter(empresa_id=empresa_id)
        context['bancos'] = Banco.objects.all().order_by('nombre')
        from contable.models import Cuenta
        context['cuentas_contables'] = Cuenta.objects.filter(empresa_id=empresa_id, imputable=1).order_by('jerarquia')
        context['fecha_actual'] = timezone.localdate()
        # Cotización del dólar para pagos en USD (parámetro de la empresa). En OP se usa el
        # dólar VENTA (contrapartida del dólar COBRANZA que usan los recibos).
        from empresas.models import CotizacionMoneda
        cotiz = CotizacionMoneda.objects.filter(empresa_id=empresa_id).first()
        context['dolar_venta'] = cotiz.dolar_venta if cotiz else 1.0
        return context

from django.views import View
from django.shortcuts import redirect
from django.contrib import messages
from tesoreria.models import Caja, CajaSesion
from facturacion.models import Preventa

@method_decorator(never_cache, name='dispatch')
class CajaMostradorIndexView(LoginRequiredMixin, View):
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')
        
        if not empresa_id or not sucursal_id:
            messages.warning(request, "Por favor seleccione una empresa y sucursal.")
            return redirect('seleccion_empresa')
            
        caja = Caja.objects.filter(empresa_id=empresa_id, sucursal_id=sucursal_id, tipo='M', activa=True).first()
        
        if not caja:
            # Si no existe una caja, la creamos automáticamente para simplificar
            from empresas.models import Empresa, Sucursal
            empresa = Empresa.objects.get(id=empresa_id)
            sucursal = Sucursal.objects.get(id=sucursal_id)
            caja = Caja.objects.create(empresa=empresa, sucursal=sucursal, nombre=f"Caja {sucursal.nombre}")
            
        # Buscar sesión abierta para el usuario actual en esta caja
        sesion_activa = CajaSesion.objects.filter(
            caja=caja,
            usuario=request.user,
            estado='A'
        ).first()
        
        if not sesion_activa:
            return render(request, 'tesoreria/caja_mostrador_abrir.html', {'caja': caja})
            
        # Si la sesión está abierta, mostramos la bandeja de cobro
        from django.db.models import Exists, OuterRef
        from facturacion.models import PreventaItem
        subprod_item = PreventaItem.objects.filter(
            preventa_id=OuterRef('pk'),
            producto__subprod=True
        )
        preventas = Preventa.objects.filter(
            empresa_id=empresa_id,
            sucursal_id=sucursal_id,
            estado__in=[0, 2] # 0=Borrador, 2=Autorizada
        ).annotate(
            tiene_subprod=Exists(subprod_item)
        ).order_by('fecha', 'preventa_id')
        
        context = {
            'caja': caja,
            'sesion': sesion_activa,
            'preventas': preventas
        }
        return render(request, 'tesoreria/caja_mostrador_index.html', context)

class CajaMostradorAbrirView(LoginRequiredMixin, View):
    def post(self, request):
        from decimal import Decimal

        caja_id = request.POST.get('caja_id')
        saldo_raw = request.POST.get('saldo_inicial', '0').replace('.', '').replace(',', '.')
        try:
            saldo_inicial = Decimal(saldo_raw or '0')
        except Exception:
            saldo_inicial = Decimal('0')

        caja = Caja.objects.get(id=caja_id)

        # Validar que no tenga otra sesión abierta
        if CajaSesion.objects.filter(caja=caja, usuario=request.user, estado='A').exists():
            return redirect('caja_mostrador_index')

        # La apertura solo abre el turno con el fondo fijo que ya quedó físicamente en el cajón
        # (arrastre del cierre anterior). No mueve dinero entre cajas => NO genera asiento.
        # La inyección de fondos (alta/reposición de fondo fijo) es una acción aparte del tesorero.
        CajaSesion.objects.create(
            caja=caja,
            usuario=request.user,
            saldo_inicial=saldo_inicial,
            saldo_final_calculado=saldo_inicial,
            estado='A'
        )
        messages.success(request, f"Caja {caja.nombre} abierta exitosamente con saldo inicial ${saldo_inicial:.2f}")

        return redirect('caja_mostrador_index')
