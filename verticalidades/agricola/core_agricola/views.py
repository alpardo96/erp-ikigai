from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from decimal import Decimal

from empresas.models import Empresa
from .models import Finca, Seccion, Campania
from .forms import FincaForm, SeccionForm


def _empresa(request):
    return request.session.get('empresa_id')


# =========================================================================
# FINCAS / ESTABLECIMIENTOS
# =========================================================================

@login_required
def fincas_listado(request):
    """Listado y panel de gestión de Fincas y Establecimientos."""
    empresa_id = _empresa(request)
    fincas = Finca.objects.filter(empresa_id=empresa_id).prefetch_related('secciones').order_by('codigo')
    
    total_fincas = fincas.count()
    total_ha = sum((f.superficie_total_ha for f in fincas), Decimal('0.00'))
    total_ha_cultivables = sum((f.superficie_cultivable_ha for f in fincas), Decimal('0.00'))

    context = {
        'fincas': fincas,
        'total_fincas': total_fincas,
        'total_ha': total_ha,
        'total_ha_cultivables': total_ha_cultivables,
    }
    return render(request, 'agricola/fincas/fincas_listado.html', context)


@login_required
def finca_modal(request, id=None):
    """Modal HTMX para crear o editar una Finca."""
    empresa_id = _empresa(request)
    finca = get_object_or_404(Finca, pk=id, empresa_id=empresa_id) if id else None

    if request.method == 'POST':
        form = FincaForm(request.POST, instance=finca)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.empresa_id = empresa_id
            obj.save()
            return HttpResponse(status=204, headers={'HX-Refresh': 'true'})
        return render(request, 'agricola/fincas/finca_modal.html', {'form': form, 'finca': finca})

    form = FincaForm(instance=finca)
    return render(request, 'agricola/fincas/finca_modal.html', {'form': form, 'finca': finca})


@login_required
@require_POST
def finca_eliminar(request, id):
    """Elimina o desactiva una Finca si no tiene historial."""
    empresa_id = _empresa(request)
    finca = get_object_or_404(Finca, pk=id, empresa_id=empresa_id)
    try:
        finca.delete()
        messages.success(request, f"Finca {finca.codigo} eliminada correctamente.")
    except Exception:
        finca.activa = False
        finca.save()
        messages.warning(request, f"La finca posee datos asociados y fue desactivada.")
    return redirect('agro_fincas_listado')


# =========================================================================
# SECCIONES / LOTES PRODUCTIVOS
# =========================================================================

@login_required
def secciones_listado(request):
    """Listado de Secciones / Lotes de cultivo con filtro por Finca."""
    empresa_id = _empresa(request)
    finca_id = request.GET.get('finca')
    
    fincas = Finca.objects.filter(empresa_id=empresa_id, activa=True).order_by('codigo')
    secciones = Seccion.objects.filter(empresa_id=empresa_id).select_related('finca').order_by('finca__codigo', 'codigo')

    if finca_id:
        secciones = secciones.filter(finca_id=finca_id)

    total_secciones = secciones.count()
    total_ha = sum((s.superficie_ha for s in secciones), Decimal('0.00'))

    context = {
        'secciones': secciones,
        'fincas': fincas,
        'finca_seleccionada': int(finca_id) if finca_id else None,
        'total_secciones': total_secciones,
        'total_ha': total_ha,
    }
    return render(request, 'agricola/secciones/secciones_listado.html', context)


@login_required
def seccion_modal(request, id=None):
    """Modal HTMX para crear o editar una Sección/Lote."""
    empresa_id = _empresa(request)
    seccion = get_object_or_404(Seccion, pk=id, empresa_id=empresa_id) if id else None

    if request.method == 'POST':
        form = SeccionForm(request.POST, instance=seccion, empresa_id=empresa_id)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.empresa_id = empresa_id
            obj.save()
            return HttpResponse(status=204, headers={'HX-Refresh': 'true'})
        return render(request, 'agricola/secciones/seccion_modal.html', {'form': form, 'seccion': seccion})

    initial = {}
    if not seccion and request.GET.get('finca'):
        initial['finca'] = request.GET.get('finca')

    form = SeccionForm(instance=seccion, empresa_id=empresa_id, initial=initial)
    return render(request, 'agricola/secciones/seccion_modal.html', {'form': form, 'seccion': seccion})


@login_required
@require_POST
def seccion_eliminar(request, id):
    """Elimina o desactiva una Sección/Lote."""
    empresa_id = _empresa(request)
    seccion = get_object_or_404(Seccion, pk=id, empresa_id=empresa_id)
    try:
        seccion.delete()
        messages.success(request, f"Lote/Sección {seccion.codigo} eliminado correctamente.")
    except Exception:
        seccion.activa = False
        seccion.save()
        messages.warning(request, f"El lote posee datos asociados y fue desactivado.")
    return redirect('agro_secciones_listado')


# =========================================================================
# CULTIVOS / ESPECIES AGRÍCOLAS
# =========================================================================

@login_required
def cultivos_listado(request):
    """Listado del maestro de Cultivos y Variedades."""
    empresa_id = _empresa(request)
    from .models import Cultivo
    cultivos = Cultivo.objects.filter(empresa_id=empresa_id).select_related('producto_cosecha').order_by('tipo', 'nombre')
    
    context = {
        'cultivos': cultivos,
        'total_cultivos': cultivos.count(),
    }
    return render(request, 'agricola/cultivos/cultivos_listado.html', context)


@login_required
def cultivo_modal(request, id=None):
    """Modal HTMX para crear o editar un Cultivo."""
    empresa_id = _empresa(request)
    from .models import Cultivo
    from .forms import CultivoForm
    cultivo = get_object_or_404(Cultivo, pk=id, empresa_id=empresa_id) if id else None

    if request.method == 'POST':
        form = CultivoForm(request.POST, instance=cultivo, empresa_id=empresa_id)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.empresa_id = empresa_id
            obj.save()
            return HttpResponse(status=204, headers={'HX-Refresh': 'true'})
        return render(request, 'agricola/cultivos/cultivo_modal.html', {'form': form, 'cultivo': cultivo})

    form = CultivoForm(instance=cultivo, empresa_id=empresa_id)
    return render(request, 'agricola/cultivos/cultivo_modal.html', {'form': form, 'cultivo': cultivo})


@login_required
@require_POST
def cultivo_eliminar(request, id):
    """Elimina o desactiva un Cultivo."""
    empresa_id = _empresa(request)
    from .models import Cultivo
    cultivo = get_object_or_404(Cultivo, pk=id, empresa_id=empresa_id)
    try:
        cultivo.delete()
        messages.success(request, f"Cultivo {cultivo.nombre} eliminado correctamente.")
    except Exception:
        cultivo.activo = False
        cultivo.save()
        messages.warning(request, f"El cultivo posee movimientos asociados y fue desactivado.")
    return redirect('agro_cultivos_listado')


# =========================================================================
# LABORES Y TAREAS CULTURALES EN FINCA
# =========================================================================

@login_required
def labores_listado(request):
    """Listado y gestión de Órdenes de Trabajo / Labores culturales en campo."""
    empresa_id = _empresa(request)
    from .models import ParteTrabajo, Finca, Campania
    partes = (
        ParteTrabajo.objects.filter(empresa_id=empresa_id)
        .select_related('campania', 'finca', 'seccion', 'tipo_labor', 'contratista')
        .prefetch_related('insumos_aplicados__producto')
        .order_by('-fecha', '-numero')
    )
    campanias = Campania.objects.filter(empresa_id=empresa_id).order_by('-fecha_inicio')
    fincas = Finca.objects.filter(empresa_id=empresa_id, activa=True).order_by('codigo')

    context = {
        'partes': partes,
        'campanias': campanias,
        'fincas': fincas,
        'total_partes': partes.count(),
    }
    return render(request, 'agricola/labores/labores_listado.html', context)

