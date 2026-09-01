import json
import csv
from decimal import Decimal
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.db import transaction
from verticalidades.estudio.models import TarifaEstudio

@login_required
def actualizar_tarifas(request):
    """
    Renderiza la vista principal para actualizar tarifas de estudio.
    """
    empresa = getattr(request, 'empresa_actual', None)
    if not empresa:
        from empresas.models import Empresa
        empresa_id = request.session.get('empresa_id')
        if empresa_id:
            empresa = Empresa.objects.filter(id=empresa_id).first()
    from productos.models import Producto
    from contable.models import Cuenta
    from facturacion.models import ClienteProveedor
    
    productos = Producto.objects.filter(empresa=empresa).order_by('detalle')
    cuentas = Cuenta.objects.filter(empresa=empresa, imputable=True).order_by('codigo')
    clientes = ClienteProveedor.objects.filter(empresa=empresa, tipo_entidad=1).order_by('razon_social')

    return render(request, 'facturacion/estudio/actualizar_tarifas.html', {
        'empresa': empresa,
        'productos': productos,
        'cuentas': cuentas,
        'clientes': clientes
    })

@login_required
@require_GET
def api_tarifas(request):
    """
    Retorna la lista de tarifas para la empresa activa en formato JSON.
    """
    empresa = getattr(request, 'empresa_actual', None)
    if not empresa:
        from empresas.models import Empresa
        empresa_id = request.session.get('empresa_id')
        if empresa_id:
            empresa = Empresa.objects.filter(id=empresa_id).first()

    tarifas_qs = TarifaEstudio.objects.filter(empresa=empresa).select_related('cliente', 'producto')
    
    data = []
    for t in tarifas_qs:
        # Calcular el porcentaje de IVA del producto para la columna informativa
        alic_iva = float(t.producto.alic_iva_porc) if t.producto else 21.0
        
        data.append({
            'id': t.id,
            'cliente_id': t.cliente.codigo_id if t.cliente else '',
            'razon_social': t.cliente.razon_social if t.cliente else '',
            'tarifa_f_ant': float(t.tarifa_f),
            'tarifa_p_ant': float(t.tarifa_p),
            'tarifa_f_nueva': float(t.tarifa_f),
            'tarifa_p_nueva': float(t.tarifa_p),
            'alic_iva': alic_iva,
            'activo': t.activo,
            'activo_ant': t.activo,
            'producto_id': t.producto.id if t.producto else None,
            'producto_id_ant': t.producto.id if t.producto else None,
            'cuenta_id': t.cuenta.id if t.cuenta else None,
            'cuenta_id_ant': t.cuenta.id if t.cuenta else None,
            'producto_detalle': t.producto.detalle if t.producto else ''
        })
        
    # Ordenar por razón social
    data.sort(key=lambda x: x['razon_social'])
    
    return JsonResponse(data, safe=False)

@login_required
@require_POST
def guardar_tarifas(request):
    """
    Recibe un JSON con las tarifas modificadas y las actualiza masivamente.
    """
    empresa = getattr(request, 'empresa_actual', None)
    if not empresa:
        from empresas.models import Empresa
        empresa_id = request.session.get('empresa_id')
        if empresa_id:
            empresa = Empresa.objects.filter(id=empresa_id).first()

    try:
        data = json.loads(request.body)
        
        with transaction.atomic():
            for item in data:
                item_id = item.get('id')
                if item_id and not str(item_id).startswith('new_'):
                    tarifa = TarifaEstudio.objects.select_for_update().get(id=item_id, empresa=empresa)
                    modificado = False
                    
                    # Convertir a Decimal para la DB
                    t_f_nueva = Decimal(str(item.get('tarifa_f_nueva', 0)))
                    t_p_nueva = Decimal(str(item.get('tarifa_p_nueva', 0)))
                    
                    if tarifa.tarifa_f != t_f_nueva:
                        tarifa.tarifa_f = t_f_nueva
                        modificado = True
                        
                    if tarifa.tarifa_p != t_p_nueva:
                        tarifa.tarifa_p = t_p_nueva
                        modificado = True
                    
                    nuevo_producto_id = item.get('producto_id')
                    if nuevo_producto_id and tarifa.producto_id != nuevo_producto_id:
                        tarifa.producto_id = nuevo_producto_id
                        modificado = True

                    nuevo_cuenta_id = item.get('cuenta_id')
                    if tarifa.cuenta_id != nuevo_cuenta_id:
                        tarifa.cuenta_id = nuevo_cuenta_id
                        modificado = True

                    nuevo_activo = item.get('activo', tarifa.activo)
                    if tarifa.activo != nuevo_activo:
                        tarifa.activo = nuevo_activo
                        modificado = True
                        
                    if modificado:
                        tarifa.modificado_por = request.user
                        tarifa.save(update_fields=['tarifa_f', 'tarifa_p', 'activo', 'producto', 'cuenta', 'modificado_por', 'fecha_modificacion'])
                else:
                    # Crear nuevo registro
                    cliente_id = item.get('cliente_obj_id')
                    producto_id = item.get('producto_id')
                    if cliente_id and producto_id:
                        TarifaEstudio.objects.create(
                            empresa=empresa,
                            cliente_id=cliente_id,
                            producto_id=producto_id,
                            cuenta_id=item.get('cuenta_id') or None,
                            tarifa_f=Decimal(str(item.get('tarifa_f_nueva', 0))),
                            tarifa_p=Decimal(str(item.get('tarifa_p_nueva', 0))),
                            activo=item.get('activo', True),
                            creado_por=request.user
                        )
                        
        return JsonResponse({'status': 'success', 'message': 'Tarifas actualizadas correctamente.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
def facturacion_lotes(request):
    empresa = getattr(request, 'empresa_actual', None)
    if not empresa:
        from empresas.models import Empresa
        empresa_id = request.session.get('empresa_id')
        if empresa_id:
            empresa = Empresa.objects.filter(id=empresa_id).first()
            
    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa'}, status=400)
    
    # Obtener puntos de venta disponibles
    from empresas.models import PuntoVenta
    puntos_venta = PuntoVenta.objects.filter(empresa_id=empresa, activo=True)

    return render(request, 'facturacion/estudio/facturacion_lotes.html', {
        'empresa_activa': empresa,
        'puntos_venta': puntos_venta
    })


@login_required
def api_facturacion_lotes(request):
    empresa = getattr(request, 'empresa_actual', None)
    if not empresa:
        from empresas.models import Empresa
        empresa_id = request.session.get('empresa_id')
        if empresa_id:
            empresa = Empresa.objects.filter(id=empresa_id).first()
            
    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa'}, status=400)
    
    periodo = request.GET.get('periodo', '') # YYYYMM
    if not periodo:
        return JsonResponse({'error': 'Período no especificado'}, status=400)

    # Buscar ventas existentes para ese período y empresa
    from facturacion.models import Venta, VentaItem
    ventas_existentes = Venta.objects.filter(
        items__producto__empresa=empresa,
        periodo_facturado=periodo
    ).values(
        'cliente_id', 
        'items__producto_id',
        'ventas_id',
        'tipo__detalle',
        'punto',
        'numero',
        'cae',
        'vto_cae'
    )
    
    facturas_por_tarifa = {}
    for v in ventas_existentes:
        key = (v['cliente_id'], v['items__producto_id'])
        if key not in facturas_por_tarifa:
            facturas_por_tarifa[key] = []
            
        comp = {
            'id': v['ventas_id'],
            'detalle': f"{v['tipo__detalle']} {v['punto']:04d}-{v['numero']:08d}",
            'cae': v['cae'] if v['cae'] else '',
            'vto_cae': v['vto_cae'].strftime('%d/%m/%Y') if v['vto_cae'] else ''
        }
        if comp not in facturas_por_tarifa[key]:
            facturas_por_tarifa[key].append(comp)
            
    ventas_set = set(facturas_por_tarifa.keys())

    tarifas = TarifaEstudio.objects.filter(empresa=empresa, activo=True).select_related('cliente', 'producto', 'cuenta')
    data = []
    
    for t in tarifas:
        # Determinar si ya fue facturado en este período
        ya_facturado = (t.cliente_id, t.producto_id) in ventas_set
        
        # Calcular IVA para mostrar el costo real si es tarifa_f
        alic_iva = float(t.producto.alic_iva) if t.producto and t.producto.alic_iva else 21.0
        tarifa_f = float(t.tarifa_f)
        iva_calculado = tarifa_f * (alic_iva / 100.0)
        total_f = tarifa_f + iva_calculado

        data.append({
            'id': t.id,
            'cliente_id': t.cliente_id if t.cliente_id else '',
            'razon_social': t.cliente.razon_social if t.cliente else '',
            'cuit': t.cliente.cuit if t.cliente else '',
            'condicion_iva': t.cliente.condicion_iva if t.cliente else '',
            'producto_id': t.producto_id if t.producto_id else '',
            'producto_detalle': t.producto.detalle if t.producto else '',
            'cuenta_id': t.cuenta_id if t.cuenta_id else '',
            'tarifa_f': tarifa_f,
            'alic_iva': alic_iva,
            'total_f': total_f,
            'tarifa_p': float(t.tarifa_p),
            'ya_facturado': ya_facturado,
            'comprobantes': facturas_por_tarifa.get((t.cliente_id, t.producto_id), [])
        })
        
    return JsonResponse({'items': data})


@login_required
def generar_lote_facturacion(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    empresa = getattr(request, 'empresa_actual', None)
    if not empresa:
        from empresas.models import Empresa
        empresa_id = request.session.get('empresa_id')
        if empresa_id:
            empresa = Empresa.objects.filter(id=empresa_id).first()
            
    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa'}, status=400)
    empresa_id = empresa.id
        
    try:
        data = json.loads(request.body)
        lote = data.get('lote', [])
        periodo = data.get('periodo')
        pto_vta_id = data.get('pto_vta_id')
        
        if not periodo:
            return JsonResponse({'error': 'Período obligatorio'}, status=400)
            
        # Pasar la responsabilidad al servicio
        from facturacion.services.facturacion_lote_service import FacturacionLoteService
        servicio = FacturacionLoteService(empresa_id=empresa_id, usuario=request.user)

        # MODO PRUEBA: no llama a ARCA y estampa un CAE ficticio. Antes venía fijo en el
        # código, así que no había forma de emitir en serio y quedaban en la base
        # comprobantes "autorizados" que ARCA nunca vio. Ahora lo decide quien llama, y
        # el default sigue siendo el seguro (Plan 075 §5.3).
        modo_prueba = bool(data.get('modo_prueba', True))
        resultados = servicio.procesar_lote(lote, periodo, pto_vta_id,
                                            modo_prueba=modo_prueba)

        return JsonResponse({'status': 'success', 'resultados': resultados,
                             'modo_prueba': modo_prueba})
    except ValueError as e:
        # Errores de configuración esperados (falta el tipo PRE, punto de venta sin
        # resolver): son para que el usuario los corrija, no fallas del sistema.
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=400)
