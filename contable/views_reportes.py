from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Q
from datetime import date

from .models import Asiento, AsientoLinea, Cuenta
from .services.reportes_excel import (
    exportar_diario_excel, exportar_mayor_excel, exportar_balance_excel,
    exportar_saldos_mensuales_excel,
)


@login_required
def exportar_saldos_mensuales(request):
    """Descarga la grilla de Saldos Mensuales tal cual se está viendo.

    Reusa el mismo contexto que arma la pantalla, así que el Excel refleja exactamente los
    filtros aplicados. La única diferencia con lo que se ve es el signo: en modo 'Sólo
    Resultados' el servicio de exportación invierte los importes (Plan 047 §3.6).
    """
    from empresas.models import Empresa
    from contable.views_htmx import get_saldos_mensuales_context

    empresa = Empresa.objects.filter(id=request.session.get('empresa_id')).first()
    datos = get_saldos_mensuales_context(request)
    return exportar_saldos_mensuales_excel(datos, empresa)

@login_required
def exportar_diario(request):
    empresa_id = request.session.get('empresa_id')
    from empresas.models import Empresa
    empresa = Empresa.objects.filter(id=empresa_id).first()
    
    asientos = Asiento.objects.filter(empresa_id=empresa_id)
    
    estado = request.GET.get('estado', '1')
    if estado == '1':
        asientos = asientos.filter(anulado=False)
    elif estado == '2':
        asientos = asientos.filter(anulado=True)

    condics = request.GET.getlist('condic')
    if condics:
        asientos = asientos.filter(condic__in=condics)

    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    if fecha_desde: asientos = asientos.filter(fecha__gte=fecha_desde)
    if fecha_hasta: asientos = asientos.filter(fecha__lte=fecha_hasta)
    
    asiento_desde = (request.GET.get('asiento_desde') or '').strip()
    asiento_hasta = (request.GET.get('asiento_hasta') or '').strip()
    if asiento_desde and asiento_desde.isdigit():
        asientos = asientos.filter(asiento_id__gte=int(asiento_desde))
    if asiento_hasta and asiento_hasta.isdigit():
        asientos = asientos.filter(asiento_id__lte=int(asiento_hasta))

    asientos = asientos.order_by('fecha', 'asiento_id')
    
    return exportar_diario_excel(asientos, empresa)

@login_required
def exportar_mayor(request):
    empresa_id = request.session.get('empresa_id')
    from empresas.models import Empresa, Ejercicio
    from contable.models import Cuenta, AsientoLinea
    from contable.services.reportes_mayor import obtener_columnas_seleccionadas
    from django.shortcuts import get_object_or_404
    from contable.views_htmx import get_mayor_context

    empresa = Empresa.objects.filter(id=empresa_id).first()
    ejercicio_id = request.session.get('ejercicio_id')
    ejercicio = Ejercicio.objects.filter(pk=ejercicio_id).first() if ejercicio_id else None
    
    cuenta_id = request.GET.get('cuenta_id')
    cuenta_desde_id = request.GET.get('cuenta_desde')
    cuenta_hasta_id = request.GET.get('cuenta_hasta')
    
    if cuenta_id:
        cuenta_desde_id = cuenta_id
        cuenta_hasta_id = cuenta_id
        
    if not cuenta_desde_id or not cuenta_hasta_id:
        primera = Cuenta.objects.filter(empresa_id=empresa_id, imputable=1).order_by('jerarquia').first()
        ultima = Cuenta.objects.filter(empresa_id=empresa_id, imputable=1).order_by('jerarquia').last()
        if primera and ultima:
            cuenta_desde_id = primera.id
            cuenta_hasta_id = ultima.id
        else:
            from django.http import HttpResponseBadRequest
            return HttpResponseBadRequest("Faltan las cuentas contables de la empresa")
        
    cuenta_desde = get_object_or_404(Cuenta, pk=cuenta_desde_id, empresa_id=empresa_id)
    cuenta_hasta = get_object_or_404(Cuenta, pk=cuenta_hasta_id, empresa_id=empresa_id)
    
    jerarquias = sorted([cuenta_desde.jerarquia, cuenta_hasta.jerarquia])
    filtros_cuenta = {
        'empresa_id': empresa_id,
        'imputable': 1,
        'jerarquia__gte': jerarquias[0],
        'jerarquia__lte': jerarquias[1]
    }
    
    if cuenta_desde_id != cuenta_hasta_id:
        cuentas_con_movs = AsientoLinea.objects.filter(
            cuenta__empresa_id=empresa_id,
            asiento__anulado=False
        ).values_list('cuenta_id', flat=True).distinct()
        filtros_cuenta['id__in'] = cuentas_con_movs
        
    cuentas = Cuenta.objects.filter(**filtros_cuenta).order_by('jerarquia')
    
    cuentas_data = []
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    for cta in cuentas:
        ctx = get_mayor_context(request, cta, limit_rows=False)
        if ctx['movimientos'] or ctx['saldo_anterior'] != 0:
            cuentas_data.append(ctx)
            
    columnas_sel = obtener_columnas_seleccionadas(request)
    return exportar_mayor_excel(cuentas_data, empresa, ejercicio, fecha_desde, fecha_hasta, columnas_sel=columnas_sel)


@login_required
def exportar_mayor_csv(request):
    import csv
    from django.http import HttpResponse, HttpResponseBadRequest
    from django.shortcuts import get_object_or_404
    from django.utils import timezone
    from empresas.models import Empresa
    from contable.models import Cuenta, AsientoLinea
    from contable.views_htmx import get_mayor_context
    from contable.services.reportes_mayor import (
        COLUMNAS_MAYOR_CATALOGO, obtener_columnas_seleccionadas, obtener_valor_columna_movimiento
    )

    empresa_id = request.session.get('empresa_id')
    empresa = Empresa.objects.filter(id=empresa_id).first()
    
    cuenta_id = request.GET.get('cuenta_id')
    cuenta_desde_id = request.GET.get('cuenta_desde')
    cuenta_hasta_id = request.GET.get('cuenta_hasta')
    
    if cuenta_id:
        cuenta_desde_id = cuenta_id
        cuenta_hasta_id = cuenta_id
        
    if not cuenta_desde_id or not cuenta_hasta_id:
        primera = Cuenta.objects.filter(empresa_id=empresa_id, imputable=1).order_by('jerarquia').first()
        ultima = Cuenta.objects.filter(empresa_id=empresa_id, imputable=1).order_by('jerarquia').last()
        if primera and ultima:
            cuenta_desde_id = primera.id
            cuenta_hasta_id = ultima.id
        else:
            return HttpResponseBadRequest("Faltan las cuentas contables de la empresa")
        
    cuenta_desde = get_object_or_404(Cuenta, pk=cuenta_desde_id, empresa_id=empresa_id)
    cuenta_hasta = get_object_or_404(Cuenta, pk=cuenta_hasta_id, empresa_id=empresa_id)
    
    jerarquias = sorted([cuenta_desde.jerarquia, cuenta_hasta.jerarquia])
    filtros_cuenta = {
        'empresa_id': empresa_id,
        'imputable': 1,
        'jerarquia__gte': jerarquias[0],
        'jerarquia__lte': jerarquias[1]
    }
    
    if cuenta_desde_id != cuenta_hasta_id:
        cuentas_con_movs = AsientoLinea.objects.filter(
            cuenta__empresa_id=empresa_id,
            asiento__anulado=False
        ).values_list('cuenta_id', flat=True).distinct()
        filtros_cuenta['id__in'] = cuentas_con_movs
        
    cuentas = Cuenta.objects.filter(**filtros_cuenta).order_by('jerarquia')
    
    cuentas_data = []
    for cta in cuentas:
        ctx = get_mayor_context(request, cta, limit_rows=False)
        if ctx['movimientos'] or ctx['saldo_anterior'] != 0:
            cuentas_data.append(ctx)
            
    columnas_sel = obtener_columnas_seleccionadas(request)
    headers = [c['nombre'] for c in COLUMNAS_MAYOR_CATALOGO if c['clave'] in columnas_sel]
    keys = [c['clave'] for c in COLUMNAS_MAYOR_CATALOGO if c['clave'] in columnas_sel]
    
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="libro_mayor_{timezone.localdate().strftime("%Y%m%d")}.csv"'
    
    # BOM UTF-8 para apertura limpia en Excel / PowerBI
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(headers)
    
    for cta_data in cuentas_data:
        for mov in cta_data['movimientos']:
            row = [obtener_valor_columna_movimiento(mov, cta_data, key) for key in keys]
            writer.writerow(row)
            
    return response


@login_required
def exportar_balance(request):
    empresa_id = request.session.get('empresa_id')
    from empresas.models import Empresa
    empresa = Empresa.objects.filter(id=empresa_id).first()
    
    ejercicio_id = request.session.get('ejercicio_id')
    from empresas.models import Ejercicio
    ejercicio = Ejercicio.objects.filter(pk=ejercicio_id).first() if ejercicio_id else None
    
    from contable.views_htmx import get_balance_context
    context = get_balance_context(request)
    
    return exportar_balance_excel(context['balance'], empresa, context['fecha_hasta'], context, ejercicio, context['fecha_desde'])

# ==========================================
# EXPORTACIÓN PDF
# ==========================================
from .services.reportes_pdf import (
    exportar_diario_pdf as service_diario_pdf,
    exportar_mayor_pdf as service_mayor_pdf,
    exportar_balance_pdf as service_balance_pdf
)

@login_required
def exportar_diario_pdf_view(request):
    empresa_id = request.session.get('empresa_id')
    from empresas.models import Empresa
    from datetime import datetime
    empresa = Empresa.objects.filter(id=empresa_id).first()
    
    asientos = Asiento.objects.filter(empresa_id=empresa_id)
    
    estado = request.GET.get('estado', '1')
    if estado == '1':
        asientos = asientos.filter(anulado=False)
    elif estado == '2':
        asientos = asientos.filter(anulado=True)

    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    asiento_desde = request.GET.get('asiento_desde')
    asiento_hasta = request.GET.get('asiento_hasta')
    condic = request.GET.get('condic')
    
    dt_desde = None
    dt_hasta = None
    if fecha_desde:
        asientos = asientos.filter(fecha__gte=fecha_desde)
        try: dt_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        except ValueError: pass

    if fecha_hasta:
        asientos = asientos.filter(fecha__lte=fecha_hasta)
        try: dt_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
        except ValueError: pass

    if asiento_desde and asiento_desde.isdigit():
        asientos = asientos.filter(asiento_id__gte=int(asiento_desde))
    if asiento_hasta and asiento_hasta.isdigit():
        asientos = asientos.filter(asiento_id__lte=int(asiento_hasta))
    
    condics = request.GET.getlist('condic')
    if condics:
        asientos = asientos.filter(condic__in=condics)
    
    asientos = asientos.order_by('fecha', 'asiento_id')
    
    return service_diario_pdf(asientos, empresa, fecha_desde=dt_desde, fecha_hasta=dt_hasta)

@login_required
def exportar_mayor_pdf_view(request):
    empresa_id = request.session.get('empresa_id')
    from empresas.models import Empresa
    empresa = Empresa.objects.filter(id=empresa_id).first()
    
    ejercicio_id = request.session.get('ejercicio_id')
    from empresas.models import Ejercicio
    ejercicio = Ejercicio.objects.filter(pk=ejercicio_id).first() if ejercicio_id else None
    
    cuenta_id = request.GET.get('cuenta_id')
    cuenta_desde_id = request.GET.get('cuenta_desde')
    cuenta_hasta_id = request.GET.get('cuenta_hasta')
    
    if cuenta_id:
        cuenta_desde_id = cuenta_id
        cuenta_hasta_id = cuenta_id
        
    if not cuenta_desde_id or not cuenta_hasta_id:
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest("Faltan los parámetros cuenta_desde y cuenta_hasta")
        
    from django.shortcuts import get_object_or_404
    cuenta_desde = get_object_or_404(Cuenta, pk=cuenta_desde_id, empresa_id=empresa_id)
    cuenta_hasta = get_object_or_404(Cuenta, pk=cuenta_hasta_id, empresa_id=empresa_id)
    
    jerarquias = sorted([cuenta_desde.jerarquia, cuenta_hasta.jerarquia])
    filtros_cuenta = {
        'empresa_id': empresa_id,
        'imputable': 1,
        'jerarquia__gte': jerarquias[0],
        'jerarquia__lte': jerarquias[1]
    }
    
    if cuenta_desde_id != cuenta_hasta_id:
        from contable.models import AsientoLinea
        cuentas_con_movs = AsientoLinea.objects.filter(
            cuenta__empresa_id=empresa_id,
            asiento__anulado=False
        ).values_list('cuenta_id', flat=True).distinct()
        filtros_cuenta['id__in'] = cuentas_con_movs
        
    cuentas = Cuenta.objects.filter(**filtros_cuenta).order_by('jerarquia')
    
    from contable.views_htmx import get_mayor_context
    cuentas_data = []
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    for cta in cuentas:
        ctx = get_mayor_context(request, cta, limit_rows=False)
        if ctx['movimientos'] or ctx['saldo_anterior'] != 0:
            cuentas_data.append(ctx)
            
    return service_mayor_pdf(cuentas_data, empresa, ejercicio, fecha_desde, fecha_hasta)

@login_required
def exportar_balance_pdf_view(request):
    empresa_id = request.session.get('empresa_id')
    from empresas.models import Empresa
    empresa = Empresa.objects.filter(id=empresa_id).first()
    
    ejercicio_id = request.session.get('ejercicio_id')
    from empresas.models import Ejercicio
    ejercicio = Ejercicio.objects.filter(pk=ejercicio_id).first() if ejercicio_id else None
    
    from contable.views_htmx import get_balance_context
    context = get_balance_context(request)
        
    return service_balance_pdf(context['balance'], empresa, context['fecha_hasta'], context, ejercicio, context['fecha_desde'])
