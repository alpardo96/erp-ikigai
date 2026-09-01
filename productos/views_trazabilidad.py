from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from productos.models import Subproducto
from empresas.models import Empresa, Sucursal

class SubproductoTrazabilidadListView(LoginRequiredMixin, ListView):
    template_name = "productos/trazabilidad_list.html"
    context_object_name = "subproductos"

    def dispatch(self, request, *args, **kwargs):
        empresa_id = request.session.get('empresa_id')
        if not empresa_id:
            return redirect('seleccion_empresa')
        
        empresa = Empresa.objects.filter(pk=empresa_id).first()
        if not empresa or (empresa.tipo_actividad and empresa.tipo_actividad.lower() not in ['armeria', 'automotor']):
            # Si no es de este rubro, no permitir acceso
            from django.contrib import messages
            messages.warning(request, "El módulo de Trazabilidad es exclusivo para empresas tipo Armería o Automotor.")
            return redirect('stock_index')

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        empresa_id = self.request.session.get('empresa_id')
        
        # Filtros
        search_clipro = self.request.GET.get('clipro', '').strip()
        search_serie = self.request.GET.get('serie', '').strip()
        search_cuim = self.request.GET.get('cuim', '').strip()
        search_producto = self.request.GET.get('producto', '').strip()
        search_situacion = self.request.GET.get('situacion', '').strip()
        search_sucursal = self.request.GET.get('sucursal', '').strip()

        qs = Subproducto.objects.filter(empresa_id=empresa_id)

        # Si se busca por CliPro, primero encontramos las series que tienen ese CliPro en su historia
        if search_clipro:
            series_con_clipro = Subproducto.objects.filter(
                Q(empresa_id=empresa_id) & (
                    Q(compra__proveedor__razon_social__icontains=search_clipro) |
                    Q(venta__cliente__razon_social__icontains=search_clipro)
                )
            ).values('serie')
            qs = qs.filter(serie__in=series_con_clipro)

        if search_serie and len(search_serie) >= 3:
            qs = qs.filter(serie__icontains=search_serie)
        if search_cuim and len(search_cuim) >= 3:
            qs = qs.filter(cuim__icontains=search_cuim)
        if search_producto:
            qs = qs.filter(producto__detalle__icontains=search_producto)
        if search_situacion:
            qs = qs.filter(situacion=search_situacion)
        if search_sucursal:
            qs = qs.filter(sucursal_id=search_sucursal)

        # Obtenemos solo el estado más reciente de cada serie utilizando DISTINCT ON
        # Para usar distinct() con order_by, los campos del distinct deben ser los primeros en el order_by
        qs = qs.select_related('producto', 'compra', 'compra__proveedor', 'venta', 'venta__cliente')
        qs = qs.order_by('serie', '-feccpra', '-subpro').distinct('serie')
        
        # Limitamos a 50 registros para optimizar carga (evitando el COUNT(*) de paginate_by)
        return qs[:50]

    def get_template_names(self):
        if self.request.headers.get('HX-Request') or self.request.META.get('HTTP_HX_REQUEST'):
            return ["productos/partials/trazabilidad_grilla.html"]
        return super().get_template_names()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        empresa_id = self.request.session.get('empresa_id')
        if empresa_id:
            context['sucursales'] = Sucursal.objects.filter(empresa_id=empresa_id).order_by('nombre')
        return context


def trazabilidad_modal_timeline(request, serie):
    """
    Muestra el historial completo de movimientos (multiciclo) de una serie y/o CUIM en la empresa.
    """
    empresa_id = request.session.get('empresa_id')
    if not empresa_id:
        return render(request, 'core/partials/mensaje_error.html', {'mensaje': "Empresa no seleccionada"})

    # Obtenemos los registros que coincidan con la serie o con el cuim asociado a esta serie
    subproductos_serie = Subproducto.objects.filter(empresa_id=empresa_id, serie=serie)
    cuims_asociados = [sp.cuim for sp in subproductos_serie if sp.cuim]

    filtro = Q(serie=serie)
    if cuims_asociados:
        filtro |= Q(cuim__in=cuims_asociados)

    movimientos = Subproducto.objects.filter(
        Q(empresa_id=empresa_id) & filtro
    ).select_related('producto', 'compra', 'compra__proveedor', 'venta', 'venta__cliente').order_by('feccpra', 'subpro')

    if not movimientos.exists():
        return render(request, 'core/partials/mensaje_error.html', {'mensaje': "No se encontraron movimientos para esta serie."})

    subproducto_actual = movimientos.last()

    return render(request, 'productos/partials/trazabilidad_modal_timeline.html', {
        'serie': serie,
        'movimientos': movimientos,
        'subproducto_actual': subproducto_actual
    })


@login_required
def subproducto_detalle_modal(request, subpro_id):
    """
    Renderiza el modal con los detalles completos del registro de trazabilidad seleccionado.
    Toma los datos de la compra (compra_id) y, si id_vta > 0 (venta no nula), los datos de la venta.
    """
    empresa_id = request.session.get('empresa_id')
    if not empresa_id:
        return render(request, 'core/partials/mensaje_error.html', {'mensaje': "Empresa no seleccionada"})

    subproducto = get_object_or_404(
        Subproducto.objects.select_related('producto', 'compra', 'compra__proveedor', 'venta', 'venta__cliente'),
        subpro=subpro_id,
        empresa_id=empresa_id
    )

    return render(request, 'productos/partials/subproducto_detalle_modal.html', {
        'subproducto': subproducto,
        'compra': subproducto.compra,
        'venta': subproducto.venta,
    })


@login_required
def subproducto_editar_modal(request, subpro_id):
    """
    Permite la edición exclusiva de los campos SERIE y CUIM de un registro de subproducto.
    Esto permite corregir errores de tipeo necesarios para la facturación y trámites correspondientes.
    """
    empresa_id = request.session.get('empresa_id')
    if not empresa_id:
        return render(request, 'core/partials/mensaje_error.html', {'mensaje': "Empresa no seleccionada"})

    subproducto = get_object_or_404(Subproducto, subpro=subpro_id, empresa_id=empresa_id)

    if request.method == 'POST':
        nueva_serie = request.POST.get('serie', '').strip().upper()
        nuevo_cuim = request.POST.get('cuim', '').strip().upper()

        if not nueva_serie:
            return render(request, 'productos/partials/subproducto_editar_modal.html', {
                'subproducto': subproducto,
                'error': "El número de SERIE es obligatorio."
            })

        # Actualizamos únicamente SERIE y CUIM
        subproducto.serie = nueva_serie
        subproducto.cuim = nuevo_cuim if nuevo_cuim else None
        subproducto.save(update_fields=['serie', 'cuim'])

        from django.http import HttpResponse
        import json
        response = HttpResponse(f'<div class="p-4 bg-green-100 text-green-800 rounded-xl font-bold">Subproducto serie "{subproducto.serie}" actualizado correctamente.</div>')
        response['HX-Trigger'] = json.dumps({
            'subproductoActualizado': True,
            'closeModal': True
        })
        return response

    return render(request, 'productos/partials/subproducto_editar_modal.html', {
        'subproducto': subproducto
    })

