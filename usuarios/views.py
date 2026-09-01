from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from empresas.models import Empresa, Sucursal
from .models import Perfil

class HomeView(LoginRequiredMixin, View):
    def get(self, request):
        if not request.session.get('sucursal_id'):
            return redirect('seleccion_empresa')
        return render(request, 'dashboard/index.html')

class SeleccionEmpresaView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user
        perfil = getattr(user, 'perfil', None)
        
        if user.is_staff or (perfil and perfil.es_admin_sistema):
            empresas = Empresa.objects.all().prefetch_related('sucursales')
        elif perfil:
            empresas = perfil.empresas.all().prefetch_related('sucursales')
        else:
            empresas = Empresa.objects.none()
            
        return render(request, 'usuarios/seleccion_empresa.html', {
            'empresas': empresas
        })

    def post(self, request):
        sucursal_id = request.POST.get('sucursal_id')
        empresa_id_auto = request.POST.get('empresa_id_auto')
        
        if sucursal_id:
            sucursal = Sucursal.objects.get(id=sucursal_id)
            request.session['empresa_id'] = sucursal.empresa.id
            request.session['sucursal_id'] = sucursal.id
            # Limpiar ejercicio anterior para que el context processor asigne el default de la nueva empresa
            if 'ejercicio_id' in request.session: del request.session['ejercicio_id']
            return redirect('home')
        elif empresa_id_auto:
            empresa = Empresa.objects.get(id=empresa_id_auto)
            sucursal = Sucursal.objects.create(
                empresa=empresa,
                nombre="Sede Central",
                direccion="Pendiente de configuración"
            )
            request.session['empresa_id'] = empresa.id
            request.session['sucursal_id'] = sucursal.id
            if 'ejercicio_id' in request.session: del request.session['ejercicio_id']
            return redirect('home')
            
        return redirect('seleccion_empresa')

class CambiarEjercicioView(LoginRequiredMixin, View):
    def post(self, request):
        ejercicio_id = request.POST.get('ejercicio_id')
        if ejercicio_id:
            request.session['ejercicio_id'] = ejercicio_id
        
        next_url = request.META.get('HTTP_REFERER', 'home')
        return redirect(next_url)
