from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from decimal import Decimal

from verticalidades.agricola.core_agricola.models import Finca, Seccion, Campania, Cultivo, ParteTrabajo
from verticalidades.agricola.tabaco.models import RomaneoTabaco, LiquidacionTabaco, LoteAcopio


@login_required
def agro_index(request):
    """Hub principal con accesos por tarjeta y resumen operativo del Módulo Agrícola."""
    empresa_id = request.session.get('empresa_id')

    # Métricas de Estructura de Campo
    fincas = Finca.objects.filter(empresa_id=empresa_id, activa=True)
    total_fincas = fincas.count()
    total_ha = sum((f.superficie_total_ha for f in fincas), Decimal('0.00'))

    secciones = Seccion.objects.filter(empresa_id=empresa_id, activa=True)
    total_secciones = secciones.count()
    total_ha_cultivables = sum((s.superficie_ha for s in secciones), Decimal('0.00'))

    # Métricas de Cultivos y Labores
    total_cultivos = Cultivo.objects.filter(empresa_id=empresa_id, activo=True).count()
    total_labores = ParteTrabajo.objects.filter(empresa_id=empresa_id).count()

    # Campaña activa
    campania_activa = Campania.objects.filter(empresa_id=empresa_id, activa=True, estado=Campania.ABIERTA).first()

    # Métricas de Tabaco
    romaneos_count = RomaneoTabaco.objects.filter(empresa_id=empresa_id).count()
    liquidaciones_count = LiquidacionTabaco.objects.filter(empresa_id=empresa_id).count()
    lotes_count = LoteAcopio.objects.filter(empresa_id=empresa_id).count()

    context = {
        'total_fincas': total_fincas,
        'total_ha': total_ha,
        'total_secciones': total_secciones,
        'total_ha_cultivables': total_ha_cultivables,
        'total_cultivos': total_cultivos,
        'total_labores': total_labores,
        'campania_activa': campania_activa,
        'romaneos_count': romaneos_count,
        'liquidaciones_count': liquidaciones_count,
        'lotes_count': lotes_count,
    }
    return render(request, 'agricola/index.html', context)


@login_required
def acopio_parametros_view(request):
    """Panel centralizado de Parámetros, Variedades, Clases, Precios y FET de Acopio de Tabaco."""
    empresa_id = request.session.get('empresa_id')
    tab = request.GET.get('tab', 'agro_config_tabaco')

    from verticalidades.agricola.core_agricola.models import Campania
    from verticalidades.agricola.tabaco.forms import ConfiguracionTabacoForm
    from verticalidades.agricola.tabaco.models import (
        ClaseTabaco, ConfiguracionTabaco, ListaPrecioTabaco,
        ProcesoAcondicionamiento, TipoRetencionTabaco, VariedadTabaco,
    )

    context = {
        'active_tab': tab,
    }

    if tab == 'agro_campanias':
        context['campanias'] = Campania.objects.filter(empresa_id=empresa_id).order_by('-fecha_inicio')
    elif tab == 'agro_variedades':
        context['variedades'] = VariedadTabaco.objects.filter(empresa_id=empresa_id).select_related('producto')
    elif tab == 'agro_clases':
        context['clases'] = ClaseTabaco.objects.filter(empresa_id=empresa_id).select_related('variedad')
        context['agro_variedades'] = VariedadTabaco.objects.filter(empresa_id=empresa_id, activa=True)
    elif tab == 'agro_listas_precio':
        context['listas'] = (
            ListaPrecioTabaco.objects.filter(empresa_id=empresa_id)
            .select_related('variedad', 'campania')
            .order_by('-vigencia_desde', 'variedad__codigo')
        )
    elif tab == 'agro_retenciones':
        context['retenciones'] = TipoRetencionTabaco.objects.filter(empresa_id=empresa_id).select_related('cuenta_contable', 'jurisdiccion')
    elif tab == 'agro_procesos':
        context['procesos'] = ProcesoAcondicionamiento.objects.filter(empresa_id=empresa_id)
    elif tab == 'agro_config_tabaco':
        cfg = ConfiguracionTabaco.objects.filter(empresa_id=empresa_id).first()
        if not cfg and empresa_id:
            cfg = ConfiguracionTabaco.objects.create(empresa_id=empresa_id)
        context['config'] = cfg
        context['form'] = ConfiguracionTabacoForm(empresa_id, instance=cfg)


    if request.headers.get('HX-Request') == 'true':
        return render(request, f'configuracion/partials/{tab}.html', context)

    return render(request, 'agricola/acopio_parametros.html', context)


