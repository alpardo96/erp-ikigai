from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.db.models import Q, Sum
from django.contrib.auth.decorators import login_required
from datetime import date
from django.utils import timezone
import json

from .models import Cuenta
from .forms import CuentaForm

# --- CRUD DE CUENTAS CONTABLES ---
@login_required
def cuenta_modal(request, id=None):
    cuenta = get_object_or_404(Cuenta, id=id, empresa_id=request.session.get('empresa_id')) if id else None
    empresa_id = request.session.get('empresa_id')
    
    if request.method == 'POST':
        form = CuentaForm(request.POST, instance=cuenta)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.pk:
                obj.creado_por = request.user
                obj.empresa_id = empresa_id
            obj.modificado_por = request.user
            obj.save()
            response = HttpResponse()
            response['HX-Trigger'] = json.dumps({'reloadCuentas': True, 'cerrarModal': True})
            response['HX-Reswap'] = 'none'
            return response
    else:
        form = CuentaForm(instance=cuenta)
        
    cuentas_padres = Cuenta.objects.filter(empresa_id=empresa_id, imputable=0).order_by('jerarquia')
    form.fields['sumariza'].queryset = cuentas_padres
    
    return render(request, 'configuracion/modals/cuentacontable_form.html', {
        'form': form, 
        'cuenta': cuenta,
        'cuentas_padres': cuentas_padres
    })

@login_required
def buscar_cuentas(request):
    q = request.GET.get('q', '')
    empresa_id = request.session.get('empresa_id')
    cuentas = Cuenta.objects.filter(empresa_id=empresa_id).order_by('jerarquia')
    if q:
        cuentas = cuentas.filter(cuenta__icontains=q)
    return render(request, 'configuracion/partials/cuentacontable_table_rows.html', {'cuentas': cuentas})

@login_required
def eliminar_cuenta(request, id):
    if request.method == 'POST':
        cuenta = get_object_or_404(Cuenta, id=id, empresa_id=request.session.get('empresa_id'))
        cuenta.delete()
        response = HttpResponse()
        response['HX-Trigger'] = json.dumps({'reloadCuentas': True})
        return response
    return HttpResponse(status=400)



# =========================================================================
# LIBRO DIARIO Y ASIENTOS
# =========================================================================
from django.db.models import Sum, Q, F, Case, When, DecimalField
from datetime import date
from django.utils import timezone
from .models import Asiento, AsientoLinea
from .forms import AsientoEncForm
from .services.asientos import crear_asiento
from contable.services.contabilizacion import anular_asiento_de_comprobante
from django.contrib import messages

@login_required
def libro_diario_rows(request):
    """
    Retorna las filas del Libro Diario (tabla cble_asiento_enc).
    Implementa consulta diferida: sólo ejecuta el query si el usuario envió parámetros de búsqueda (filtering=1).
    Soporta filtros por fecha desde/hasta, condición (los 7 valores de `CONDIC_ASIENTO`) y rango de ID Asiento (asiento_desde, asiento_hasta).
    """
    empresa_id = request.session.get('empresa_id')
    if not empresa_id:
        return render(request, 'contable/partials/libro_diario_rows.html', {'asientos': Asiento.objects.none(), 'ejecutado': False})

    GET = request.GET
    is_filtered_request = 'filtering' in GET or ('fecha_desde' in GET and GET.get('fecha_desde')) or ('asiento_desde' in GET and GET.get('asiento_desde')) or ('asiento_hasta' in GET and GET.get('asiento_hasta'))

    if not is_filtered_request:
        return render(request, 'contable/partials/libro_diario_rows.html', {'asientos': Asiento.objects.none(), 'ejecutado': False})

    asientos = Asiento.objects.filter(empresa_id=empresa_id)
    
    # Filtro por estado del asiento (1=Sólo Activos, 2=Sólo Anulados, 0=Todos)
    estado = GET.get('estado', '1')
    if estado == '1':
        asientos = asientos.filter(anulado=False)
    elif estado == '2':
        asientos = asientos.filter(anulado=True)

    condics = GET.getlist('condic')
    if condics:
        asientos = asientos.filter(condic__in=condics)
    
    fecha_desde = GET.get('fecha_desde')
    fecha_hasta = GET.get('fecha_hasta')
    if fecha_desde:
        asientos = asientos.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        asientos = asientos.filter(fecha__lte=fecha_hasta)

    asiento_desde = (GET.get('asiento_desde') or '').strip()
    asiento_hasta = (GET.get('asiento_hasta') or '').strip()
    if asiento_desde and asiento_desde.isdigit():
        asientos = asientos.filter(asiento_id__gte=int(asiento_desde))
    if asiento_hasta and asiento_hasta.isdigit():
        asientos = asientos.filter(asiento_id__lte=int(asiento_hasta))
    
    asientos = asientos.order_by('fecha', 'asiento_id')
    
    return render(request, 'contable/partials/libro_diario_rows.html', {'asientos': asientos[:500], 'ejecutado': True})

@login_required
def detalle_asiento(request, id):
    """
    Retorna la grilla desplegable de movimientos del asiento (tabla cble_asiento_mov).
    """
    asiento = get_object_or_404(Asiento, pk=id, empresa_id=request.session.get('empresa_id'))
    lineas = asiento.lineas.select_related('cuenta', 'cli_pro').all().order_by('orden')
    
    total_debe = sum(l.debe for l in lineas)
    total_haber = sum(l.haber for l in lineas)
    
    return render(request, 'contable/partials/detalle_asiento.html', {
        'asiento': asiento, 'lineas': lineas, 'total_debe': total_debe, 'total_haber': total_haber
    })

@login_required
def anular_asiento(request, id):
    if request.method == 'POST':
        get_object_or_404(Asiento, pk=id, empresa_id=request.session.get('empresa_id'))
        anular_asiento_de_comprobante(id)
        messages.success(request, f"Asiento {id} anulado correctamente.")
        response = HttpResponse()
        response['HX-Trigger'] = json.dumps({'reloadDiario': True})
        return response
    return HttpResponse(status=400)

@login_required
def asiento_modal(request):
    empresa_id = request.session.get('empresa_id')
    empresa = request.user.perfil.empresas.filter(pk=empresa_id).first()
    
    if request.method == 'POST':
        form = AsientoEncForm(request.POST)
        if form.is_valid():
            try:
                lineas = []
                total_lineas = int(request.POST.get('total_lineas', 0))
                
                for i in range(total_lineas):
                    cta_id = request.POST.get(f'linea_cuenta_{i}')
                    if cta_id:
                        lineas.append({
                            'cuenta': int(cta_id),
                            'leyenda': request.POST.get(f'linea_leyenda_{i}', ''),
                            'debe': request.POST.get(f'linea_debe_{i}', 0),
                            'haber': request.POST.get(f'linea_haber_{i}', 0),
                        })
                
                crear_asiento(
                    empresa=empresa,
                    fecha=form.cleaned_data['fecha'],
                    concepto=form.cleaned_data['concepto'],
                    lineas=lineas,
                    condic=form.cleaned_data['condic'],
                    modulo=1, # Manual
                    cli_pro=form.cleaned_data['cli_pro'],
                    usuario=request.user
                )
                
                messages.success(request, "Asiento contable creado exitosamente.")
                response = HttpResponse()
                response['HX-Trigger'] = json.dumps({'reloadDiario': True, 'cerrarModal': True})
                response['HX-Reswap'] = 'none'
                return response
            except Exception as e:
                # Si hay error (ej. desbalanceado), re-renderizamos con mensaje de error
                cuentas = Cuenta.objects.filter(empresa=empresa, imputable=1).order_by('jerarquia')
                return render(request, 'contable/modals/asiento_form.html', {
                    'form': form, 'cuentas_imputables': cuentas, 'error': str(e)
                })
    else:
        form = AsientoEncForm(initial={'fecha': timezone.localdate()})
        
    cuentas = Cuenta.objects.filter(empresa=empresa, imputable=1).order_by('jerarquia')
    return render(request, 'contable/modals/asiento_form.html', {'form': form, 'cuentas_imputables': cuentas})

@login_required
def detalle_asiento_modal(request, asiento_id):
    empresa_id = request.session.get('empresa_id')
    from django.shortcuts import get_object_or_404
    asiento = get_object_or_404(Asiento, pk=asiento_id, empresa_id=empresa_id)
    lineas = asiento.lineas.all().select_related('cuenta')
    
    total_debe = sum(l.debe for l in lineas)
    total_haber = sum(l.haber for l in lineas)
    
    context = {
        'asiento': asiento,
        'lineas': lineas,
        'total_debe': total_debe,
        'total_haber': total_haber
    }
    return render(request, 'contable/modals/detalle_asiento_modal.html', context)

# =========================================================================
# MAYOR Y BALANCE
# =========================================================================

def get_mayor_context(request, cuenta, limit_rows=False):
    empresa_id = request.session.get('empresa_id')
    from django.db.models import Sum
    
    # Empezamos con los movimientos de esta cuenta o sus subcuentas
    if cuenta.imputable == 1:
        movimientos = AsientoLinea.objects.filter(
            cuenta_id=cuenta.id,
            cuenta__empresa_id=empresa_id,
            asiento__anulado=False
        ).select_related('asiento').order_by('asiento__fecha', 'asiento__asiento_id')
    else:
        movimientos = AsientoLinea.objects.filter(
            cuenta__jerarquia__startswith=cuenta.jerarquia,
            cuenta__empresa_id=empresa_id,
            asiento__anulado=False
        ).select_related('asiento', 'cuenta').order_by('asiento__fecha', 'asiento__asiento_id')
    
    # Filtros adicionales
    condics = request.GET.getlist('condic')
    if condics:
        movimientos = movimientos.filter(asiento__condic__in=condics)
        
    cli_pro_id = request.GET.get('cli_pro_id')
    if cli_pro_id:
        movimientos = movimientos.filter(asiento__cli_pro_id=cli_pro_id)
        
    sucursal_id = request.GET.get('sucursal_id')
    if sucursal_id:
        movimientos = movimientos.filter(asiento__sucursal_id=sucursal_id)

    modulo = request.GET.get('modulo')
    if modulo:
        movimientos = movimientos.filter(asiento__modulo=modulo)

    # Acotar por la FK del ejercicio, no sólo por fechas: un asiento de otro ejercicio con fecha
    # solapada aparecería en el mayor sin estar en la celda que lo abrió (Plan 047 §6.5).
    ejercicio_id = request.GET.get('ejercicio_id')
    if ejercicio_id:
        movimientos = movimientos.filter(asiento__ejercicio_id=ejercicio_id)

    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    saldo_anterior = 0
    if fecha_desde:
        movs_ant = movimientos.filter(asiento__fecha__lt=fecha_desde).order_by().aggregate(
            t_debe=Sum('debe', default=0), t_haber=Sum('haber', default=0)
        )
        t_debe_ant = movs_ant['t_debe'] or 0
        t_haber_ant = movs_ant['t_haber'] or 0
        
        if cuenta.tipo in ['A', 'R']: # Si es Activo/Resultado(Egreso)
            saldo_anterior = t_debe_ant - t_haber_ant
        else: # Pasivo, P.Neto, Ingreso
            saldo_anterior = t_haber_ant - t_debe_ant
            
        movimientos = movimientos.filter(asiento__fecha__gte=fecha_desde)
        
    if fecha_hasta:
        movimientos = movimientos.filter(asiento__fecha__lte=fecha_hasta)
        
    saldo_acumulado = saldo_anterior
    
    totales_periodo = movimientos.order_by().aggregate(
        t_debe=Sum('debe', default=0), 
        t_haber=Sum('haber', default=0)
    )
    suma_debe_total = totales_periodo['t_debe'] or 0
    suma_haber_total = totales_periodo['t_haber'] or 0
    
    if cuenta.tipo in ['A', 'R']:
        saldo_final = saldo_anterior + suma_debe_total - suma_haber_total
    else:
        saldo_final = saldo_anterior + suma_haber_total - suma_debe_total

    hay_mas = False
    if limit_rows:
        movimientos_lista = list(movimientos[:501])
        hay_mas = len(movimientos_lista) > 500
        if hay_mas:
            movimientos_lista = movimientos_lista[:500]
    else:
        movimientos_lista = list(movimientos)

    lista_movs = []
    suma_debe = 0
    suma_haber = 0
    
    for mov in movimientos_lista:
        suma_debe += mov.debe
        suma_haber += mov.haber
        if cuenta.tipo in ['A', 'R']: 
            saldo_acumulado += (mov.debe - mov.haber)
        else:
            saldo_acumulado += (mov.haber - mov.debe)
            
        mov.saldo_acumulado = saldo_acumulado
        lista_movs.append(mov)
        
    return {
        'cuenta': cuenta,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'movimientos': lista_movs,
        'saldo_anterior': saldo_anterior,
        'suma_debe': suma_debe_total,
        'suma_haber': suma_haber_total,
        'saldo_final': saldo_final,
        'hay_mas': hay_mas,
        'empresa_id': empresa_id
    }

@login_required
def libro_mayor_rows(request):
    empresa_id = request.session.get('empresa_id')
    cuenta_id = request.GET.get('cuenta_id')
    cuenta_desde_id = request.GET.get('cuenta_desde')
    cuenta_hasta_id = request.GET.get('cuenta_hasta')
    
    # Si se recibe cuenta_id (consulta individual desde modal), la asignamos como inicio y fin del rango
    if cuenta_id:
        cuenta_desde_id = cuenta_id
        cuenta_hasta_id = cuenta_id
        
    if not cuenta_desde_id or not cuenta_hasta_id:
        primera = Cuenta.objects.filter(empresa_id=empresa_id, imputable=1).order_by('jerarquia').first()
        ultima = Cuenta.objects.filter(empresa_id=empresa_id, imputable=1).order_by('jerarquia').last()
        if primera and ultima:
            cuenta_desde_id = cuenta_desde_id or primera.id
            cuenta_hasta_id = cuenta_hasta_id or ultima.id
        else:
            return render(request, 'contable/partials/libro_mayor_rows.html', {'cuentas_data': []})
        
    cuenta_desde = get_object_or_404(Cuenta, pk=cuenta_desde_id, empresa_id=empresa_id)
    cuenta_hasta = get_object_or_404(Cuenta, pk=cuenta_hasta_id, empresa_id=empresa_id)
    
    jerarquias = sorted([cuenta_desde.jerarquia, cuenta_hasta.jerarquia])
    
    # Filtro base de cuentas imputables de la empresa
    filtros_cuenta = {
        'empresa_id': empresa_id,
        'imputable': 1,
        'jerarquia__gte': jerarquias[0],
        'jerarquia__lte': jerarquias[1]
    }
    
    # Si es un rango de múltiples cuentas (es decir, no es la misma cuenta),
    # optimizamos filtrando solo aquellas que tengan movimientos registrados.
    if cuenta_desde_id != cuenta_hasta_id:
        cuentas_con_movs = AsientoLinea.objects.filter(
            cuenta__empresa_id=empresa_id,
            asiento__anulado=False
        ).values_list('cuenta_id', flat=True).distinct()
        filtros_cuenta['id__in'] = cuentas_con_movs
        
    cuentas = Cuenta.objects.filter(**filtros_cuenta).order_by('jerarquia')
    
    cuentas_data = []
    for cta in cuentas:
        ctx = get_mayor_context(request, cta, limit_rows=True)
        if ctx['movimientos'] or ctx['saldo_anterior'] != 0:
            cuentas_data.append(ctx)
            
    from contable.services.reportes_mayor import (
        COLUMNAS_MAYOR_CATALOGO, obtener_columnas_seleccionadas, obtener_valor_columna_movimiento
    )
    columnas_sel = obtener_columnas_seleccionadas(request)
    columnas_info = [c for c in COLUMNAS_MAYOR_CATALOGO if c['clave'] in columnas_sel]

    # Pre-calcular valores por columna para cada movimiento para agilizar renderizado en template
    for cta_data in cuentas_data:
        for mov in cta_data['movimientos']:
            mov.valores_columnas = [
                {'clave': c['clave'], 'valor': obtener_valor_columna_movimiento(mov, cta_data, c['clave'])}
                for c in columnas_info
            ]

    return render(request, 'contable/partials/libro_mayor_rows.html', {
        'cuentas_data': cuentas_data,
        'columnas_info': columnas_info,
        'columnas_sel': columnas_sel,
    })



def _calcular_balance(
    empresa_id,
    ejercicio=None,
    fecha_desde=None,
    fecha_hasta=None,
    sucursal_id=None,
    condic=None,
    mostrar_sumarizadoras=False,
    mostrar_apertura=True,
):
    """Calcula el balance de sumas y saldos para el ejercicio activo y rango de fechas dado.

    Reglas de cálculo:
    1. El Sumas y Saldos siempre está estrictamente limitado al ejercicio activo (ejercicio_id).
    2. La columna Apertura:
       - Si mostrar_apertura=True: Incluye debe - haber del asiento contable de apertura (condic = 5) del ejercicio.
       - Si fecha_desde > ejercicio.inicio: Incluye además el movimiento neto (debe - haber) entre
         ejercicio.inicio y (fecha_desde - 1 día) del mismo ejercicio.
    3. Período (Debe y Haber):
       - Asientos con fecha_desde <= fecha <= fecha_hasta y condic != 5 del ejercicio activo.
    """
    if not ejercicio:
        from empresas.models import Ejercicio
        if fecha_desde:
            ejercicio = Ejercicio.objects.filter(empresa_id=empresa_id, inicio__lte=fecha_desde, cierre__gte=fecha_desde).first()
        if not ejercicio and fecha_hasta:
            ejercicio = Ejercicio.objects.filter(empresa_id=empresa_id, inicio__lte=fecha_hasta, cierre__gte=fecha_hasta).first()
        if not ejercicio:
            ejercicio = Ejercicio.objects.filter(empresa_id=empresa_id).order_by('-inicio').first()

    if not ejercicio:
        # Fallback de seguridad si la empresa no posee ningún ejercicio contable cargado.
        return {
            'balance': [],
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta,
            'condic': condic,
            'sucursal_id': sucursal_id,
            'mostrar_sumarizadoras': mostrar_sumarizadoras,
            'mostrar_apertura': mostrar_apertura,
            'total_apertura': Decimal('0.00'),
            'total_debe': Decimal('0.00'),
            'total_haber': Decimal('0.00'),
            'total_saldo': Decimal('0.00'),
        }

    # Delimitar fechas al rango del ejercicio activo
    if not fecha_desde:
        fecha_desde = ejercicio.inicio
    else:
        fecha_desde = max(ejercicio.inicio, min(fecha_desde, ejercicio.cierre))

    if not fecha_hasta:
        fecha_hasta = min(timezone.localdate(), ejercicio.cierre)
    else:
        fecha_hasta = min(ejercicio.cierre, max(fecha_hasta, fecha_desde))

    # --- 1. Asiento de Apertura del ejercicio (condic = 5) ---
    q_apertura_condic5 = Q(
        asientolinea__asiento__anulado=False,
        asientolinea__asiento__empresa_id=empresa_id,
        asientolinea__asiento__ejercicio_id=ejercicio.id,
        asientolinea__asiento__condic=5,
    )

    # --- 2. Movimientos netos acumulados previos a fecha_desde (si fecha_desde > inicio) ---
    q_movimientos_previos = Q(
        asientolinea__asiento__anulado=False,
        asientolinea__asiento__empresa_id=empresa_id,
        asientolinea__asiento__ejercicio_id=ejercicio.id,
        asientolinea__asiento__fecha__gte=ejercicio.inicio,
        asientolinea__asiento__fecha__lt=fecha_desde,
    ) & ~Q(asientolinea__asiento__condic=5)

    # --- 3. Movimientos del período (fecha_desde <= fecha <= fecha_hasta) ---
    q_periodo = Q(
        asientolinea__asiento__anulado=False,
        asientolinea__asiento__empresa_id=empresa_id,
        asientolinea__asiento__ejercicio_id=ejercicio.id,
        asientolinea__asiento__fecha__gte=fecha_desde,
        asientolinea__asiento__fecha__lte=fecha_hasta,
    ) & ~Q(asientolinea__asiento__condic=5)

    if condic:
        q_periodo &= Q(asientolinea__asiento__condic=condic)
        q_movimientos_previos &= Q(asientolinea__asiento__condic=condic)

    if sucursal_id:
        q_apertura_condic5 &= Q(asientolinea__asiento__sucursal_id=sucursal_id)
        q_movimientos_previos &= Q(asientolinea__asiento__sucursal_id=sucursal_id)
        q_periodo &= Q(asientolinea__asiento__sucursal_id=sucursal_id)

    # Obtener todas las cuentas para rollup jerárquico
    cuentas = list(Cuenta.objects.filter(empresa_id=empresa_id).order_by('-jerarquia'))

    # Anotar sumas en cuentas imputables (hojas)
    imputables = Cuenta.objects.filter(empresa_id=empresa_id, imputable=1).annotate(
        apertura_c5_debe=Sum('asientolinea__debe', filter=q_apertura_condic5, default=0),
        apertura_c5_haber=Sum('asientolinea__haber', filter=q_apertura_condic5, default=0),
        previos_debe=Sum('asientolinea__debe', filter=q_movimientos_previos, default=0),
        previos_haber=Sum('asientolinea__haber', filter=q_movimientos_previos, default=0),
        periodo_debe=Sum('asientolinea__debe', filter=q_periodo, default=0),
        periodo_haber=Sum('asientolinea__haber', filter=q_periodo, default=0),
    )

    cuentas_dict = {
        c.id: {
            'cuenta': c,
            'apertura': Decimal('0.00'),
            'periodo_debe': Decimal('0.00'),
            'periodo_haber': Decimal('0.00'),
            'saldo': Decimal('0.00')
        } for c in cuentas
    }

    # Poblar cuentas imputables aplicando las reglas conceptuales de Apertura
    for c_imp in imputables:
        if c_imp.id in cuentas_dict:
            # 1. Asiento de apertura (condic=5): sólo si mostrar_apertura=True
            ap_c5 = (c_imp.apertura_c5_debe or Decimal('0.00')) - (c_imp.apertura_c5_haber or Decimal('0.00')) if mostrar_apertura else Decimal('0.00')
            
            # 2. Movimientos acumulados entre ejercicio.inicio y fecha_desde (sólo si fecha_desde > inicio)
            previos_neto = (c_imp.previos_debe or Decimal('0.00')) - (c_imp.previos_haber or Decimal('0.00')) if fecha_desde > ejercicio.inicio else Decimal('0.00')

            cuentas_dict[c_imp.id]['apertura'] = ap_c5 + previos_neto
            cuentas_dict[c_imp.id]['periodo_debe'] = c_imp.periodo_debe or Decimal('0.00')
            cuentas_dict[c_imp.id]['periodo_haber'] = c_imp.periodo_haber or Decimal('0.00')

    # Rollup jerárquico bottom-up
    for cta in cuentas:
        data = cuentas_dict[cta.id]
        if cta.sumariza_id and cta.sumariza_id in cuentas_dict:
            parent_data = cuentas_dict[cta.sumariza_id]
            parent_data['apertura'] += data['apertura']
            parent_data['periodo_debe'] += data['periodo_debe']
            parent_data['periodo_haber'] += data['periodo_haber']

    # Calcular saldos finales y armar filas
    balance = []
    total_apertura = total_debe = total_haber = total_saldo = Decimal('0.00')

    for cta in reversed(cuentas):  # Revertir para orden jerárquico ascendente
        data = cuentas_dict[cta.id]
        ap = data['apertura']
        pd = data['periodo_debe']
        ph = data['periodo_haber']
        saldo = ap + pd - ph

        # Omitir cuentas completamente en cero
        if ap == 0 and pd == 0 and ph == 0 and saldo == 0:
            continue

        # Omitir cuentas sumarizadoras si no fueron solicitadas
        if cta.imputable == 0 and not mostrar_sumarizadoras:
            continue

        data['saldo'] = saldo
        balance.append(data)

        # Acumular totales de reporte únicamente sobre cuentas imputables para evitar duplicación jerárquica
        if cta.imputable == 1:
            total_apertura += ap
            total_debe += pd
            total_haber += ph
            total_saldo += saldo

    return {
        'balance': balance,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'condic': condic,
        'sucursal_id': sucursal_id,
        'mostrar_sumarizadoras': mostrar_sumarizadoras,
        'mostrar_apertura': mostrar_apertura,
        'total_apertura': total_apertura,
        'total_debe': total_debe,
        'total_haber': total_haber,
        'total_saldo': total_saldo,
    }


@login_required
def get_balance_context(request):
    empresa_id = request.session.get('empresa_id')
    ejercicio_id = request.session.get('ejercicio_id')

    fecha_desde_str = request.GET.get('fecha_desde')
    fecha_hasta_str = request.GET.get('fecha_hasta')

    ejercicio = None
    if ejercicio_id:
        from empresas.models import Ejercicio
        ejercicio = Ejercicio.objects.filter(id=ejercicio_id).first()

    fecha_desde = None
    if fecha_desde_str:
        try:
            fecha_desde = date.fromisoformat(fecha_desde_str)
        except ValueError:
            try:
                from datetime import datetime
                fecha_desde = datetime.strptime(fecha_desde_str, '%d/%m/%Y').date()
            except ValueError:
                pass

    if ejercicio:
        if not fecha_desde:
            fecha_desde = ejercicio.inicio
        else:
            fecha_desde = max(ejercicio.inicio, min(fecha_desde, ejercicio.cierre))

    fecha_hasta = timezone.localdate()
    if fecha_hasta_str:
        try:
            fecha_hasta = date.fromisoformat(fecha_hasta_str)
        except ValueError:
            try:
                from datetime import datetime
                fecha_hasta = datetime.strptime(fecha_hasta_str, '%d/%m/%Y').date()
            except ValueError:
                pass

    if ejercicio:
        if not fecha_hasta:
            fecha_hasta = min(timezone.localdate(), ejercicio.cierre)
        else:
            fecha_hasta = min(ejercicio.cierre, max(fecha_hasta, fecha_desde))

    sucursal_id = request.GET.get('sucursal')
    if sucursal_id:
        sucursal_id = int(sucursal_id)

    condic = request.GET.get('condic')
    if condic:
        condic = int(condic)

    mostrar_sumarizadoras = request.GET.get('mostrar_sumarizadoras') == 'on'

    # Selector de Asiento de Apertura (predeterminado activado)
    if 'filtros_aplicados' in request.GET or 'mostrar_apertura' in request.GET:
        mostrar_apertura = request.GET.get('mostrar_apertura') == 'on'
    else:
        mostrar_apertura = True

    context = _calcular_balance(
        empresa_id,
        ejercicio=ejercicio,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        sucursal_id=sucursal_id,
        condic=condic,
        mostrar_sumarizadoras=mostrar_sumarizadoras,
        mostrar_apertura=mostrar_apertura,
    )

    from empresas.models import Sucursal
    context['sucursales'] = Sucursal.objects.filter(empresa_id=empresa_id)
    context['ejercicio'] = ejercicio
    return context


@login_required
def balance_sumas_saldos(request):
    context = get_balance_context(request)
    return render(request, 'contable/partials/balance.html', context)

# =========================================================================
# BALANCE DE SALDOS MENSUALES (Plan 047)
# =========================================================================

def get_saldos_mensuales_context(request):
    """Traduce el querystring al contrato del servicio y agrega lo que necesita el panel.

    El **ejercicio es un filtro siempre presente**: si el querystring no trae uno, se toma el
    activo de la sesión. No existe forma de correr el reporte sin ejercicio ni sobre varios.
    """
    from empresas.models import Ejercicio, Sucursal
    from contable.models import CONDIC_MOVIMIENTO, condic_opciones
    from contable.services.saldos_mensuales import calcular_saldos_mensuales

    empresa_id = request.session.get('empresa_id')

    ejercicios = list(Ejercicio.objects.filter(empresa_id=empresa_id).order_by('-inicio'))
    ejercicio_id = request.GET.get('ejercicio') or request.session.get('ejercicio_id')
    ejercicio = next((e for e in ejercicios if str(e.pk) == str(ejercicio_id)), None)
    if ejercicio is None:
        ejercicio = ejercicios[0] if ejercicios else None

    extras = {
        'ejercicios': ejercicios,
        'sucursales': Sucursal.objects.filter(empresa_id=empresa_id).order_by('nombre'),
        'condic_opciones': condic_opciones(CONDIC_MOVIMIENTO),
        'modulos': [(1, 'Manual'), (2, 'Ventas'), (5, 'Compras'), (6, 'Banco')],
    }

    if ejercicio is None:
        return {
            **extras, 'ejercicio': None, 'periodos': [], 'filas': [],
            'totales': {'apertura': 0, 'meses': [], 'total': 0},
            'condics': list(CONDIC_MOVIMIENTO), 'alcance': 'todas',
            'sucursal_id': None, 'modulo': None,
            'mostrar_sumarizadoras': True, 'omitir_sin_movimiento': True,
            'aviso': 'La empresa no tiene ejercicios contables cargados.',
        }

    def entero(nombre):
        valor = (request.GET.get(nombre) or '').strip()
        return int(valor) if valor.isdigit() else None

    # `condic` sin tildar en un GET con filtros significa "ninguna"; en la primera carga (sin
    # querystring) significa "todas". Se distingue por la presencia del testigo del formulario.
    if request.GET.get('filtros_aplicados'):
        condics = request.GET.getlist('condic')
        mostrar_sumarizadoras = bool(request.GET.get('mostrar_sumarizadoras'))
        omitir_sin_movimiento = bool(request.GET.get('omitir_sin_movimiento'))
    else:
        condics = list(CONDIC_MOVIMIENTO)
        mostrar_sumarizadoras = True
        omitir_sin_movimiento = True

    sucursal_id = entero('sucursal')
    modulo = entero('modulo')

    datos = calcular_saldos_mensuales(
        empresa_id=empresa_id,
        ejercicio=ejercicio,
        condics=condics,
        sucursal_id=sucursal_id,
        modulo=modulo,
        alcance=request.GET.get('alcance') or 'todas',
        mostrar_sumarizadoras=mostrar_sumarizadoras,
        omitir_sin_movimiento=omitir_sin_movimiento,
    )

    # Cada fila lleva sus celdas ya apareadas con el período, porque el template no puede hacer
    # zip y cada celda necesita el rango de fechas de su mes para el drill-down.
    for fila in datos['filas']:
        fila['celdas'] = list(zip(datos['periodos'], fila['meses']))

    datos.update(_querystrings_drilldown(datos, ejercicio, sucursal_id, modulo))
    return {**extras, **datos}


def _querystrings_drilldown(datos, ejercicio, sucursal_id, modulo):
    """Querystrings que abren el Mayor conciliando EXACTAMENTE con el valor de la celda.

    La clave es mandar siempre el `condic` explícito, nunca vacío: si no, un asiento de apertura
    fechado el primer día del ejercicio aparecería en el mayor de la primera columna mensual
    —cae dentro del rango de fechas— mientras que la celda lo excluye, y los números no cerrarían.
    """
    from urllib.parse import urlencode

    from contable.services.saldos_mensuales import CONDIC_APERTURA

    comunes = [('ejercicio_id', ejercicio.pk)]
    if sucursal_id:
        comunes.append(('sucursal_id', sucursal_id))
    if modulo:
        comunes.append(('modulo', modulo))

    tildados = [('condic', c) for c in datos['condics']]
    apertura = [('condic', CONDIC_APERTURA)]

    return {
        'qs_meses': urlencode(tildados + comunes),
        'qs_apertura': urlencode(apertura + comunes),
        'qs_total': urlencode(tildados + apertura + comunes),
    }


@login_required
def saldos_mensuales_datos(request):
    context = get_saldos_mensuales_context(request)
    return render(request, 'contable/partials/saldos_mensuales.html', context)


@login_required
def mayor_cuenta_modal(request, cuenta_id):
    empresa_id = request.session.get('empresa_id')
    cuenta = get_object_or_404(Cuenta, pk=cuenta_id, empresa_id=empresa_id)
    
    from empresas.models import Sucursal, Ejercicio
    from contable.models import condic_opciones
    from contable.services.reportes_mayor import (
        COLUMNAS_MAYOR_CATALOGO, obtener_columnas_seleccionadas
    )
    from django.utils import timezone

    sucursales = Sucursal.objects.filter(empresa_id=empresa_id).order_by('nombre')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')

    if not fecha_desde or not fecha_hasta:
        ejercicio = Ejercicio.objects.filter(empresa_id=empresa_id).order_by('-inicio').first()
        if ejercicio:
            if not fecha_desde:
                fecha_desde = ejercicio.inicio.strftime('%Y-%m-%d')
            if not fecha_hasta:
                fecha_hasta = min(ejercicio.cierre, timezone.localdate()).strftime('%Y-%m-%d')

    condics_sel = request.GET.getlist('condic')
    if not condics_sel:
        condics_sel = ['1', '2', '5']

    columnas_sel = obtener_columnas_seleccionadas(request)

    context = {
        'cuenta': cuenta,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'sucursales': sucursales,
        'sucursal_id': request.GET.get('sucursal_id', ''),
        'condic_opciones': condic_opciones(),
        'condics_seleccionados': condics_sel,
        'catalogo_columnas': COLUMNAS_MAYOR_CATALOGO,
        'columnas_seleccionadas': columnas_sel,
    }
    return render(request, 'contable/modals/mayor_cuenta_modal.html', context)

from django.http import HttpResponse
import json
from .forms import ParametrosContablesForm
from .models import ParametrosContables

def parametros_contables_modal(request):
    empresa_id = request.session.get('empresa_id', 1)
    
    # Obtenemos o creamos los parametros para la empresa activa
    from empresas.models import Empresa
    empresa = Empresa.objects.filter(id=empresa_id).first()
    if not empresa:
        return HttpResponse(json.dumps({'status': 'error', 'message': 'Empresa no encontrada'}), status=400, content_type='application/json')
        
    param, created = ParametrosContables.objects.get_or_create(empresa=empresa)
    
    if request.method == 'POST':
        form = ParametrosContablesForm(request.POST, instance=param)
        if form.is_valid():
            form.save()
            response = HttpResponse()
            response['HX-Trigger'] = json.dumps({'cerrarModal': True, 'parametrosGuardados': True})
            response['HX-Reswap'] = 'none'
            return response
            
    else:
        form = ParametrosContablesForm(instance=param)
        
        # Enviar todas las cuentas para poblar el datalist
        cuentas_imputables = Cuenta.objects.filter(empresa=empresa, imputable=1).order_by('jerarquia')
        
        return render(request, 'configuracion/modals/parametros_contables_form.html', {
            'form': form,
            'cuentas_imputables': cuentas_imputables
        })

# =========================================================================
# CIERRE DE EJERCICIO
# =========================================================================
from .services.cierre import procesar_cierre_ejercicio

@login_required
def cerrar_ejercicio_modal(request):
    empresa_id = request.session.get('empresa_id')
    from empresas.models import Ejercicio
    ejercicios = Ejercicio.objects.filter(empresa_id=empresa_id).order_by('-inicio')
    
    # Validar que tenga la cuenta Resultado del Ejercicio
    parametros = ParametrosContables.objects.filter(empresa_id=empresa_id).first()
    cta_resultado_ok = parametros and parametros.cta_resultado_ejercicio is not None
    
    return render(request, 'contable/modals/cierre_ejercicio_modal.html', {
        'ejercicios': ejercicios,
        'cta_resultado_ok': cta_resultado_ok
    })

@login_required
def ejecutar_cierre_ejercicio(request):
    if request.method == 'POST':
        ejercicio_id = request.POST.get('ejercicio_id')
        empresa_id = request.session.get('empresa_id')
        
        try:
            asiento = procesar_cierre_ejercicio(ejercicio_id, empresa_id, request.user)
            from django.contrib import messages
            messages.success(request, f"Ejercicio cerrado correctamente. Se generó el asiento compensador #{asiento.asiento_id}.")
            response = HttpResponse()
            response['HX-Trigger'] = json.dumps({'cerrarModal': True, 'reloadDiario': True})
            return response
        except ValueError as e:
            return HttpResponse(f"<div class='p-4 bg-red-100 text-red-800 rounded-xl mb-4'>{str(e)}</div>", status=400)
        except Exception as e:
            return HttpResponse(f"<div class='p-4 bg-red-100 text-red-800 rounded-xl mb-4'>Error inesperado: {str(e)}</div>", status=500)
    return HttpResponse(status=405)


@login_required
def typeahead_cuentas(request):
    q = request.GET.get('q', '').strip()
    empresa_id = request.session.get('empresa_id')
    
    filtros = Q(empresa_id=empresa_id, imputable=1)
    if q:
        filtros &= (Q(jerarquia__icontains=q) | Q(cuenta__icontains=q))

    cuentas = Cuenta.objects.filter(filtros).order_by('jerarquia')[:20]
    
    target = request.GET.get('target', 'desde') # 'desde' o 'hasta'
    
    return render(request, 'contable/partials/cuentas_typeahead.html', {
        'cuentas': cuentas,
        'target': target
    })


@login_required
def asiento_editar_modal(request, asiento_id):
    empresa_id = request.session.get('empresa_id')
    asiento = get_object_or_404(Asiento, pk=asiento_id, empresa_id=empresa_id)
    empresa = asiento.empresa
    
    from contable.services.asientos import editar_asiento
    
    if request.method == 'POST':
        form = AsientoEncForm(request.POST, instance=asiento)
        if form.is_valid():
            try:
                lineas = []
                total_lineas = int(request.POST.get('total_lineas', 0))
                
                for i in range(total_lineas):
                    cta_id = request.POST.get(f'linea_cuenta_{i}')
                    if cta_id:
                        lineas.append({
                            'cuenta': int(cta_id),
                            'leyenda': request.POST.get(f'linea_leyenda_{i}', ''),
                            'debe': request.POST.get(f'linea_debe_{i}', 0),
                            'haber': request.POST.get(f'linea_haber_{i}', 0),
                        })
                
                editar_asiento(
                    asiento=asiento,
                    fecha=form.cleaned_data['fecha'],
                    concepto=form.cleaned_data['concepto'],
                    lineas=lineas,
                    usuario=request.user
                )
                
                messages.success(request, "Asiento contable actualizado exitosamente.")
                response = HttpResponse()
                response['HX-Trigger'] = json.dumps({'reloadDiario': True, 'cerrarModal': True})
                response['HX-Reswap'] = 'none'
                return response
            except Exception as e:
                # `str(ValidationError)` devuelve "['mensaje']". Se desarma para que el operador
                # lea el motivo y no la repr de una lista de Python.
                from django.core.exceptions import ValidationError
                error = '; '.join(e.messages) if isinstance(e, ValidationError) else str(e)
                cuentas = Cuenta.objects.filter(empresa=empresa, imputable=1).order_by('jerarquia')
                return render(request, 'contable/modals/asiento_form.html', {
                    'form': form, 'cuentas_imputables': cuentas, 'error': error, 'asiento': asiento
                })
    else:
        form = AsientoEncForm(instance=asiento)
        
    cuentas = Cuenta.objects.filter(empresa=empresa, imputable=1).order_by('jerarquia')
    return render(request, 'contable/modals/asiento_form.html', {'form': form, 'cuentas_imputables': cuentas, 'asiento': asiento})


# --- EXPORTACIÓN E IMPORTACIÓN EN EXCEL DE CUENTAS CONTABLES ---
from .services.excel_service import (
    generar_excel_cuentas,
    procesar_captura_excel_cuentas
)

@login_required
def exportar_cuentas_excel_completo(request):
    """
    Exporta la lista completa de cuentas contables de la empresa en un archivo Excel (.xlsx).
    """
    empresa_id = request.session.get('empresa_id')
    if not empresa_id:
        return HttpResponse("Empresa no seleccionada en la sesión.", status=400)

    cuentas = Cuenta.objects.filter(empresa_id=empresa_id).order_by('jerarquia')
    wb = generar_excel_cuentas(cuentas)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"plan_de_cuentas_empresa_{empresa_id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@login_required
def modal_capturar_cuentas_excel(request):
    """
    Despliega el modal para subir y recapturar el archivo Excel del Plan de Cuentas.
    """
    return render(request, 'contable/modals/capturar_excel_modal.html')


@login_required
def capturar_cuentas_excel(request):
    """
    Procesa el archivo Excel subido, actualizando las cuentas existentes por ID
    y creando las nuevas (con asignación automática de ID por el sistema).
    """
    empresa_id = request.session.get('empresa_id')
    if not empresa_id:
        return HttpResponse("Empresa no seleccionada en la sesión.", status=400)

    from empresas.models import Empresa
    empresa = get_object_or_404(Empresa, id=empresa_id)

    if request.method != 'POST' or 'archivo_excel' not in request.FILES:
        return render(request, 'contable/modals/capturar_excel_modal.html', {
            'resultado': {'errores': ['No se ha seleccionado ningún archivo Excel válido.']}
        })

    archivo = request.FILES['archivo_excel']
    if not archivo.name.endswith(('.xlsx', '.xls')):
        return render(request, 'contable/modals/capturar_excel_modal.html', {
            'resultado': {'errores': ['El archivo debe tener extensión .xlsx o .xls.']}
        })

    resultado = procesar_captura_excel_cuentas(empresa, request.user, archivo)

    response = render(request, 'contable/modals/capturar_excel_modal.html', {
        'resultado': resultado
    })
    
    # Se notifica a HTMX para recargar la tabla de cuentas si se procesaron cambios
    if resultado.get('actualizados', 0) > 0 or resultado.get('creados', 0) > 0:
        response['HX-Trigger'] = json.dumps({'reloadCuentas': True})

    return response


