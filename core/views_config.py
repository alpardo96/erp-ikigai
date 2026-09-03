from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from empresas.models import Empresa, Sucursal, Ejercicio, PuntoVenta
from django.contrib.auth.models import User
from facturacion.models import Jurisdiccion, TipoComprobante

from productos.models import Marca, Rubro, Familia

class ConfiguracionIndexView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'configuracion/index.html'

    def test_func(self):
        return self.request.user.is_staff or (hasattr(self.request.user, 'perfil') and self.request.user.perfil.es_admin_sistema)

    def get_template_names(self):
        if self.request.headers.get('HX-Request') == 'true':
            tab = self.request.GET.get('tab', 'hub')
            return [f'configuracion/partials/{tab}.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tab = self.request.GET.get('tab', 'hub')
        empresa_id = self.request.session.get('empresa_id')
        context['active_tab'] = tab
        context['hide_sidebar'] = True

        if tab == 'empresas':
            context['empresas'] = Empresa.objects.all()
        elif tab == 'sucursales':
            context['sucursales'] = Sucursal.objects.filter(empresa_id=empresa_id).select_related('empresa')
        elif tab == 'ejercicios':
            context['ejercicios'] = Ejercicio.objects.filter(empresa_id=empresa_id).select_related('empresa')
        elif tab == 'puntos_venta':
            context['puntos_venta'] = PuntoVenta.objects.filter(empresa_id=empresa_id).select_related('sucursal').order_by('sucursal__nombre', 'numero')
        elif tab == 'usuarios':
            context['usuarios'] = User.objects.all().select_related('perfil')

        elif tab == 'jurisdicciones':
            context['jurisdicciones'] = Jurisdiccion.objects.all()
        elif tab == 'marcas':
            # Marca pertenece a Empresa; no tiene relación con sucursales
            context['marcas'] = Marca.objects.filter(empresa_id=empresa_id).order_by('detalle')
        elif tab == 'rubros_prod':
            # Rubro pertenece a Empresa; select_related para cuentas de ventas y compras
            context['rubros_prod'] = Rubro.objects.filter(empresa_id=empresa_id).select_related('cta_ventas', 'cta_compras').order_by('detalle')
        elif tab == 'familias':
            # Familia pertenece a Empresa y se relaciona con Rubro
            context['familias'] = Familia.objects.filter(empresa_id=empresa_id).select_related('rubro').order_by('rubro__detalle', 'detalle')
        elif tab == 'comprobantes':
            context['comprobantes'] = TipoComprobante.objects.all()
        # --- Maestros de Distribución (Plan 074). Sólo se muestran en el hub si la
        # empresa es DISTRIBUIDORA, pero el contexto se resuelve igual si se entra
        # por URL directa.
        elif tab == 'zonas_reparto':
            from verticalidades.distribucion.models import ZonaReparto
            context['zonas'] = ZonaReparto.objects.filter(empresa_id=empresa_id).order_by('orden', 'nombre')
        elif tab == 'personal_distribucion':
            from verticalidades.distribucion.models import Personal
            context['personal'] = (Personal.objects.filter(empresa_id=empresa_id)
                                   .select_related('zona', 'usuario').order_by('nombre'))
        elif tab == 'vehiculos':
            from verticalidades.distribucion.models import Vehiculo
            context['vehiculos'] = (Vehiculo.objects.filter(empresa_id=empresa_id)
                                    .select_related('sucursal').order_by('patente'))
        elif tab == 'motivos_devolucion':
            from verticalidades.distribucion.models import MotivoDevolucion
            context['motivos'] = MotivoDevolucion.objects.filter(empresa_id=empresa_id).order_by('codigo')

        elif tab == 'mediospago':
            from tesoreria.models import MedioPago
            context['medios_pago'] = MedioPago.objects.filter(empresa_id=self.request.session.get('empresa_id'))
        elif tab == 'cuentasbancarias':
            from tesoreria.models import CuentaBancaria
            context['cuentas_bancarias'] = CuentaBancaria.objects.filter(empresa_id=self.request.session.get('empresa_id'))
        elif tab == 'cuentascontables':
            from contable.models import Cuenta
            context['cuentas'] = Cuenta.objects.filter(empresa_id=self.request.session.get('empresa_id')).order_by('jerarquia')
        elif tab == 'compra_trazabilidad':
            from empresas.models import EmpresaTrazabilidad
            empresa = Empresa.objects.filter(pk=empresa_id).first()
            if empresa:
                config_traz, _ = EmpresaTrazabilidad.objects.get_or_create(empresa=empresa)
                context['empresa'] = empresa
                context['config_trazabilidad'] = config_traz
        
        elif tab == 'roles':
            from django.contrib.auth.models import Group
            context['roles'] = Group.objects.all().prefetch_related('permissions')
            
        return context


from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.http import HttpResponse

def _es_admin_func(user):
    return user.is_staff or (hasattr(user, 'perfil') and user.perfil.es_admin_sistema)

@login_required
@user_passes_test(_es_admin_func)
def guardar_configuracion_trazabilidad(request):
    if request.method != 'POST':
        return HttpResponse(status=405)
    from django.http import HttpResponse
    from empresas.models import EmpresaTrazabilidad
    empresa_id = request.session.get('empresa_id')
    empresa = Empresa.objects.filter(pk=empresa_id).first()
    if not empresa:
        return HttpResponse("Empresa no seleccionada", status=400)

    empresa.usa_trazabilidad = (request.POST.get('usa_trazabilidad') == 'on')
    empresa.save(update_fields=['usa_trazabilidad'])

    config_traz, _ = EmpresaTrazabilidad.objects.get_or_create(empresa=empresa)
    config_traz.pedir_situacion = (request.POST.get('pedir_situacion') == 'on')
    config_traz.pedir_estado = (request.POST.get('pedir_estado') == 'on')
    config_traz.pedir_cuim = (request.POST.get('pedir_cuim') == 'on')
    config_traz.save()

    return render(request, 'configuracion/partials/compra_trazabilidad.html', {
        'empresa': empresa,
        'config_trazabilidad': config_traz,
        'mensaje_exito': '¡Configuración de trazabilidad actualizada correctamente!'
    })

