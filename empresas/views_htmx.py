from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
import json
from .models import Empresa, Sucursal, Ejercicio, CotizacionMoneda
from .forms import EmpresaForm, SucursalForm, EjercicioForm, CotizacionMonedaForm
from django.template.loader import render_to_string

@login_required
def empresa_modal(request, id=None):
    """
    MODAL DE COMPAÑÍA (GET/POST)
    - GET: Carga el formulario para nueva empresa o edición de existente.
    - POST: Procesa el guardado. 
    - HTMX: Responde con triggers para refrescar la lista de empresas.
    """
    if id:
        empresa = get_object_or_404(Empresa, id=id)
        is_new = False
    else:
        empresa = None
        is_new = True

    if request.method == 'POST':
        form = EmpresaForm(request.POST, request.FILES, instance=empresa)
        if form.is_valid():
            form.save()
            # Evento para cerrar modal y recargar tabla (hx-trigger)
            response = HttpResponse()
            # Primero disparamos la recarga y luego el cierre para asegurar la propagación
            response['HX-Trigger'] = json.dumps({'reloadEmpresas': True, 'cerrarModal': True})
            response['HX-Reswap'] = 'none' # Evita que HTMX limpie el modal antes de que los eventos burbujeen
            return response
    else:
        form = EmpresaForm(instance=empresa)

    return render(request, 'configuracion/modals/empresa_form.html', {
        'form': form, 
        'is_new': is_new, 
        'empresa': empresa
    })

@login_required
def sucursal_modal(request, id=None):
    """
    MODAL DE SUCURSAL / PUNTO DE VENTA
    - GET: Formulario vinculado a una Empresa.
    - POST: Registro de sucursal.
    - HTMX: Dispara 'reloadSucursales' para actualizar el listado reactivo.
    """
    if id:
        sucursal = get_object_or_404(Sucursal, id=id, empresa_id=request.session.get('empresa_id'))
        is_new = False
    else:
        sucursal = None
        is_new = True

    if request.method == 'POST':
        form = SucursalForm(request.POST, instance=sucursal)
        if form.is_valid():
            form.save()
            response = HttpResponse()
            # Priorizamos la recarga de la tabla antes de cerrar el modal
            response['HX-Trigger'] = json.dumps({'reloadSucursales': True, 'cerrarModal': True})
            response['HX-Reswap'] = 'none'
            return response
    else:
        form = SucursalForm(instance=sucursal)

    return render(request, 'configuracion/modals/sucursal_form.html', {
        'form': form, 
        'is_new': is_new, 
        'sucursal': sucursal
    })

@login_required
def buscar_sucursales(request):
    """
    BUSCADOR DE PUNTOS DE VENTA
    - Filtra por nombre de sucursal o nombre de la empresa dueña.
    """
    q = request.GET.get('q', '')
    sucursales = Sucursal.objects.filter(empresa_id=request.session.get('empresa_id')).select_related('empresa')
    if q:
        sucursales = sucursales.filter(nombre__icontains=q)

    return render(request, 'configuracion/partials/sucursal_table_rows.html', {'sucursales': sucursales.distinct()})

@login_required
def buscar_empresas(request):
    """
    BUSCADOR DE EMPRESAS
    - Búsqueda por Razón Social o CUIT.
    """
    q = request.GET.get('q', '')
    if q:
        empresas = Empresa.objects.filter(nombre__icontains=q) | Empresa.objects.filter(cuit__icontains=q)
    else:
        empresas = Empresa.objects.all()
        
    # Renderizamos sólo los TRs para que HTMX los inyecte en el tbody detectado
    return render(request, 'configuracion/partials/empresa_table_rows.html', {'empresas': empresas.distinct()})

@login_required
def eliminar_empresa(request, id):
    """
    BORRADO DE EMPRESA
    - Elimina la entidad y dispara recarga de tabla.
    """
    if request.method == 'POST':
        empresa = get_object_or_404(Empresa, id=id)
        empresa.delete()
        response = HttpResponse()
        response['HX-Trigger'] = json.dumps({'reloadEmpresas': True})
        return response
    return HttpResponse(status=400)

@login_required
def eliminar_sucursal(request, id):
    """
    BORRADO DE SUCURSAL
    - Elimina el punto de venta y dispara recarga de tabla.
    """
    if request.method == 'POST':
        sucursal = get_object_or_404(Sucursal, id=id, empresa_id=request.session.get('empresa_id'))
        sucursal.delete()
        response = HttpResponse()
        response['HX-Trigger'] = json.dumps({'reloadSucursales': True})
        return response
    return HttpResponse(status=400)

# ═══════════════════════════════════════════════════════════════
# EJERCICIOS FISCALES - CRUD HTMX
# ═══════════════════════════════════════════════════════════════

@login_required
def ejercicio_modal(request, id=None):
    """
    MODAL DE EJERCICIO FISCAL (GET/POST)
    - GET: Carga el formulario para nuevo ejercicio o edición de existente.
    - POST: Procesa el guardado.
    - HTMX: Responde con triggers para refrescar la lista de ejercicios.
    """
    if id:
        ejercicio = get_object_or_404(Ejercicio, id=id, empresa_id=request.session.get('empresa_id'))
        is_new = False
    else:
        ejercicio = None
        is_new = True

    if request.method == 'POST':
        form = EjercicioForm(request.POST, instance=ejercicio)
        if form.is_valid():
            form.save()
            # Evento para cerrar modal y recargar tabla (hx-trigger)
            response = HttpResponse()
            response['HX-Trigger'] = json.dumps({'reloadEjercicios': True, 'cerrarModal': True})
            response['HX-Reswap'] = 'none'
            return response
    else:
        form = EjercicioForm(instance=ejercicio)

    return render(request, 'configuracion/modals/ejercicio_form.html', {
        'form': form,
        'is_new': is_new,
        'ejercicio': ejercicio
    })

@login_required
def buscar_ejercicios(request):
    """
    BUSCADOR DE EJERCICIOS FISCALES
    - Filtra por nombre de ejercicio o nombre de la empresa.
    """
    q = request.GET.get('q', '')
    ejercicios = Ejercicio.objects.filter(empresa_id=request.session.get('empresa_id')).select_related('empresa')
    if q:
        ejercicios = ejercicios.filter(ejercicio__icontains=q)

    return render(request, 'configuracion/partials/ejercicio_table_rows.html', {'ejercicios': ejercicios.distinct()})

@login_required
def eliminar_ejercicio(request, id):
    """
    BORRADO DE EJERCICIO FISCAL
    - Elimina el ejercicio y dispara recarga de tabla.
    """
    if request.method == 'POST':
        ejercicio = get_object_or_404(Ejercicio, id=id, empresa_id=request.session.get('empresa_id'))
        ejercicio.delete()
        response = HttpResponse()
        response['HX-Trigger'] = json.dumps({'reloadEjercicios': True})
        return response
    return HttpResponse(status=400)

@login_required
def cotizaciones_modal(request):
    """
    MODAL DE COTIZACIONES (GET/POST)
    - GET: Carga el formulario de cotizaciones para la empresa actual.
    - POST: Guarda las nuevas cotizaciones.
    """
    # Verificamos permiso
    if not request.user.is_staff and not getattr(request.user.perfil, 'permiso_cotizaciones_editar', False) and not getattr(request.user.perfil, 'es_admin_sistema', False):
        return HttpResponse("<div class='p-4 text-red-600 font-bold'>No tienes permiso para editar cotizaciones.</div>")

    empresa_id = request.session.get('empresa_id')
    if not empresa_id:
        return HttpResponse("<div class='p-4 text-red-600 font-bold'>Debes seleccionar una empresa primero.</div>")
        
    empresa = get_object_or_404(Empresa, id=empresa_id)
    cotizacion, created = CotizacionMoneda.objects.get_or_create(empresa=empresa)

    if request.method == 'POST':
        form = CotizacionMonedaForm(request.POST, instance=cotizacion)
        if form.is_valid():
            cotizacion = form.save(commit=False)
            cotizacion.modificado_por = request.user
            cotizacion.save()
            response = HttpResponse()
            response['HX-Trigger'] = json.dumps({'cerrarModal': True})
            response['HX-Reswap'] = 'none'
            return response
    else:
        form = CotizacionMonedaForm(instance=cotizacion)

    return render(request, 'configuracion/modals/cotizaciones_form.html', {
        'form': form,
        'empresa': empresa
    })
# -*- coding: utf-8 -*-
from .models import PuntoVenta
from .forms import PuntoVentaForm

def punto_venta_modal(request, id=None):
    if id:
        punto = get_object_or_404(PuntoVenta, id=id, empresa_id=request.session.get('empresa_id'))
        is_new = False
    else:
        punto = None
        is_new = True

    if request.method == 'POST':
        form = PuntoVentaForm(request.POST, instance=punto, empresa_id=request.session.get('empresa_id'))
        if form.is_valid():
            obj = form.save(commit=False)
            obj.empresa_id = request.session.get('empresa_id')
            obj.save()
            response = HttpResponse()
            response['HX-Trigger'] = json.dumps({'reloadPuntosVenta': True, 'cerrarModal': True})
            return response
    else:
        form = PuntoVentaForm(instance=punto, empresa_id=request.session.get('empresa_id'))

    return render(request, 'configuracion/partials/punto_venta_modal.html', {
        'form': form,
        'is_new': is_new,
        'punto': punto
    })

def buscar_puntos_venta(request):
    empresa_id = request.session.get('empresa_id')
    query = request.GET.get('q', '').strip()
    
    puntos = PuntoVenta.objects.filter(empresa_id=empresa_id).select_related('sucursal')
    if query:
        puntos = puntos.filter(Q(numero__icontains=query) | Q(sucursal__nombre__icontains=query))
        
    return render(request, 'configuracion/partials/puntos_venta_lista.html', {
        'puntos_venta': puntos
    })

@require_POST
def eliminar_punto_venta(request, id):
    punto = get_object_or_404(PuntoVenta, id=id, empresa_id=request.session.get('empresa_id'))
    punto.delete()
    response = HttpResponse()
    response['HX-Trigger'] = 'reloadPuntosVenta'
    return response
