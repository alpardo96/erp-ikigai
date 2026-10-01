import json
from decimal import Decimal
from django.shortcuts import render
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.db import transaction
from django.conf import settings
from verticalidades.estudio.models import TarifaEstudio, EnvioFacturaEstudio
from verticalidades.estudio.services.config_mail_service import (
    get_config_mail, guardar_config_mail, is_config_activa,
    guardar_logo_firma, eliminar_logo_firma
)
from verticalidades.estudio.services.smtp_service import SMTPService


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

    return render(request, 'estudio/actualizar_tarifas.html', {
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
@require_GET
def exportar_tarifas_excel(request):
    """
    Exporta todas las tarifas de estudio de la empresa en un archivo Excel (.xlsx) estilizado.
    """
    empresa = getattr(request, 'empresa_actual', None)
    if not empresa:
        from empresas.models import Empresa
        empresa_id = request.session.get('empresa_id')
        if empresa_id:
            empresa = Empresa.objects.filter(id=empresa_id).first()

    if not empresa:
        return HttpResponse("No se encontró empresa activa", status=400)

    from verticalidades.estudio.services.excel_tarifas_service import generar_excel_tarifas_estudio

    excel_buffer = generar_excel_tarifas_estudio(empresa)
    response = HttpResponse(
        excel_buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="actualizacion_tarifas_estudio.xlsx"'
    return response


@login_required
@require_POST
def importar_tarifas_excel(request):
    """
    Recibe un archivo Excel (.xlsx o .xls) con tarifas modificadas, las procesa y devuelve
    la lista actualizada en JSON para volcarla a la grilla interactiva de Alpine.js.
    """
    empresa = getattr(request, 'empresa_actual', None)
    if not empresa:
        from empresas.models import Empresa
        empresa_id = request.session.get('empresa_id')
        if empresa_id:
            empresa = Empresa.objects.filter(id=empresa_id).first()

    if not empresa:
        return JsonResponse({'exito': False, 'mensaje': 'No hay empresa activa'}, status=400)

    archivo = request.FILES.get('archivo')
    if not archivo:
        return JsonResponse({'exito': False, 'mensaje': 'No se adjuntó ningún archivo de Excel.'}, status=400)

    from verticalidades.estudio.services.excel_tarifas_service import parsear_excel_tarifas_estudio

    resultado = parsear_excel_tarifas_estudio(archivo, empresa)
    return JsonResponse(resultado)


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

    return render(request, 'estudio/facturacion_lotes.html', {
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
    from facturacion.models import Venta
    ventas_existentes = Venta.objects.filter(
        empresa=empresa,
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
            
        # Pasar la responsabilidad al nuevo servicio
        from verticalidades.estudio.services.facturacion_lote_estudio import FacturacionLoteEstudioService
        servicio = FacturacionLoteEstudioService(empresa_id=empresa_id, usuario=request.user)

        modo_prueba = bool(data.get('modo_prueba', False))
        resultados = servicio.procesar_lote(lote, periodo, pto_vta_id,
                                            modo_prueba=modo_prueba)

        return JsonResponse({'status': 'success', 'resultados': resultados,
                             'modo_prueba': modo_prueba})
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=400)


# =========================================================================
# VISTAS DE ENVÍO DE FACTURAS POR CORREO ELECTRÓNICO (ESTUDIO)
# =========================================================================

@login_required
def envios_facturas(request):
    """
    Renderiza la vista principal para gestión y envío de facturas por mail.
    """
    empresa = getattr(request, 'empresa_actual', None)
    if not empresa:
        from empresas.models import Empresa
        empresa_id = request.session.get('empresa_id')
        if empresa_id:
            empresa = Empresa.objects.filter(id=empresa_id).first()

    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa'}, status=400)

    activa, motivo = is_config_activa(empresa.id)
    config = get_config_mail(empresa.id)

    return render(request, 'estudio/envios_facturas.html', {
        'empresa_activa': empresa,
        'config_mail': config,
        'config_activa': activa,
        'config_motivo': motivo,
    })


@login_required
@require_GET
def api_envios_facturas(request):
    """
    Retorna la lista de comprobantes emitidos en el período y su estado de envío por correo.
    Descubre automáticamente comprobantes generados previamente que aún no tengan registro en EnvioFacturaEstudio.
    """
    empresa = getattr(request, 'empresa_actual', None)
    if not empresa:
        from empresas.models import Empresa
        empresa_id = request.session.get('empresa_id')
        if empresa_id:
            empresa = Empresa.objects.filter(id=empresa_id).first()

    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa'}, status=400)

    periodo = request.GET.get('periodo', '').strip()
    if not periodo or len(periodo) != 6:
        return JsonResponse({'error': 'Período inválido (formato YYYYMM requerido)'}, status=400)

    from facturacion.models import Venta
    # Descubrir comprobantes del período sin registro de envío
    ventas_sin_envio = Venta.objects.filter(
        empresa=empresa,
        periodo_facturado=periodo,
        envio_estudio__isnull=True
    ).select_related('cliente', 'tipo')

    nuevos_envios = []
    for v in ventas_sin_envio:
        dest = v.cliente.correo if v.cliente and v.cliente.correo else ''
        nuevos_envios.append(EnvioFacturaEstudio(
            empresa=empresa,
            venta=v,
            cliente=v.cliente,
            periodo=periodo,
            destinatarios=dest,
            estado='PENDIENTE',
            creado_por=request.user,
            modificado_por=request.user
        ))
    if nuevos_envios:
        EnvioFacturaEstudio.objects.bulk_create(nuevos_envios)

    # Consultar todos los envíos del período
    envios_qs = EnvioFacturaEstudio.objects.filter(
        empresa=empresa,
        periodo=periodo
    ).select_related('venta', 'venta__tipo', 'cliente').order_by('cliente__razon_social', 'venta__numero')

    items = []
    conteo_total = 0
    conteo_enviados = 0
    conteo_pendientes = 0
    conteo_errores = 0

    for e in envios_qs:
        v = e.venta
        conteo_total += 1
        if e.estado == 'ENVIADO':
            conteo_enviados += 1
        elif e.estado == 'PENDIENTE':
            conteo_pendientes += 1
        elif e.estado == 'ERROR':
            conteo_errores += 1

        tipo_cbte = v.tipo.detalle if v.tipo else 'Comprobante'
        cbte_str = f"{tipo_cbte} {v.punto:04d}-{v.numero:08d}"
        cliente_nombre = v.cliente_razon_social or (v.cliente.razon_social if v.cliente else 'Sin Identificar')

        items.append({
            'id': e.id,
            'venta_id': v.ventas_id,
            'fecha': v.fecha.strftime('%d/%m/%Y') if v.fecha else '',
            'comprobante': cbte_str,
            'tipo_codigo': v.tipo.codigo if v.tipo else '',
            'cae': v.cae or '',
            'total': float(v.total),
            'cliente_id': v.cliente_id or '',
            'cliente_razon': cliente_nombre,
            'cliente_cuit': v.cliente_cuit or (v.cliente.cuit if v.cliente else ''),
            'destinatarios': e.destinatarios or (v.cliente.correo if v.cliente else ''),
            'estado': e.estado,
            'respuesta_smtp': e.respuesta_smtp or '',
            'fecha_envio': e.fecha_envio.strftime('%d/%m/%Y %H:%M') if e.fecha_envio else '',
            'intentos': e.intentos
        })

    return JsonResponse({
        'periodo': periodo,
        'metricas': {
            'total': conteo_total,
            'enviados': conteo_enviados,
            'pendientes': conteo_pendientes,
            'errores': conteo_errores,
        },
        'items': items
    })


@login_required
@require_POST
def api_enviar_pendientes(request):
    """
    Endpoint de streaming para enviar masivamente todos los comprobantes pendientes o con error.
    Utiliza StreamingHttpResponse con ndjson para actualización en tiempo real y bloqueo del frontend.
    """
    empresa = getattr(request, 'empresa_actual', None)
    if not empresa:
        from empresas.models import Empresa
        empresa_id = request.session.get('empresa_id')
        if empresa_id:
            empresa = Empresa.objects.filter(id=empresa_id).first()

    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa'}, status=400)

    try:
        body = json.loads(request.body) if request.body else {}
    except Exception:
        body = {}
    periodo = body.get('periodo', request.POST.get('periodo', '')).strip()

    if not periodo:
        return JsonResponse({'error': 'Período no especificado'}, status=400)

    envios_pendientes = EnvioFacturaEstudio.objects.filter(
        empresa=empresa,
        periodo=periodo,
        estado__in=['PENDIENTE', 'ERROR']
    ).select_related('venta', 'venta__tipo', 'cliente').order_by('cliente__razon_social')

    service = SMTPService(empresa.id)

    def event_generator():
        for event in service.procesar_lote_pendientes_streaming(envios_pendientes, usuario=request.user):
            yield json.dumps(event, ensure_ascii=False) + "\n"

    response = StreamingHttpResponse(event_generator(), content_type='application/x-ndjson')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@login_required
@require_POST
def api_reenviar_factura(request, envio_id):
    """
    Reenvía un comprobante individual específico.
    Solo disponible cuando el comprobante no está en estado ENVIADO.
    """
    empresa = getattr(request, 'empresa_actual', None)
    if not empresa:
        from empresas.models import Empresa
        empresa_id = request.session.get('empresa_id')
        if empresa_id:
            empresa = Empresa.objects.filter(id=empresa_id).first()

    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa'}, status=400)

    envio = EnvioFacturaEstudio.objects.filter(
        id=envio_id,
        empresa=empresa
    ).select_related('venta', 'venta__tipo', 'cliente').first()

    if not envio:
        return JsonResponse({'error': 'Registro de envío no encontrado'}, status=404)

    service = SMTPService(empresa.id)
    ok, respuesta = service.enviar_factura_individual(envio, usuario=request.user)

    return JsonResponse({
        'status': 'success' if ok else 'error',
        'envio_id': envio.id,
        'estado': envio.estado,
        'respuesta_smtp': envio.respuesta_smtp,
        'fecha_envio': envio.fecha_envio.strftime('%d/%m/%Y %H:%M') if envio.fecha_envio else '',
        'intentos': envio.intentos,
        'mensaje': respuesta
    })


# =========================================================================
# CONFIGURACIÓN DE CORREO POR EMPRESA (MODAL Y GUARDADO EN MEDIA)
# =========================================================================

@login_required
def config_mails_modal(request):
    """
    Renderiza el modal para configurar los datos SMTP y plantillas de correo de la empresa.
    """
    empresa = getattr(request, 'empresa_actual', None)
    if not empresa:
        from empresas.models import Empresa
        empresa_id = request.session.get('empresa_id')
        if empresa_id:
            empresa = Empresa.objects.filter(id=empresa_id).first()

    if not empresa:
        return HttpResponse('<div class="p-6 text-red-500 font-bold">No hay empresa activa.</div>')

    config = get_config_mail(empresa.id)
    return render(request, 'estudio/modals/config_mails_modal.html', {
        'empresa': empresa,
        'config': config,
        'usuario': request.user,
        'MEDIA_URL': settings.MEDIA_URL,
    })


@login_required
@require_POST
def config_mails_guardar(request):
    """
    Guarda la configuración SMTP y plantillas en el archivo JSON dentro de media/config_mails/.
    """
    empresa = getattr(request, 'empresa_actual', None)
    if not empresa:
        from empresas.models import Empresa
        empresa_id = request.session.get('empresa_id')
        if empresa_id:
            empresa = Empresa.objects.filter(id=empresa_id).first()

    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa'}, status=400)

    try:
        data = {
            'activo': request.POST.get('activo') in ['on', 'true', True],
            'email_remitente': request.POST.get('email_remitente', '').strip(),
            'nombre_remitente': request.POST.get('nombre_remitente', '').strip(),
            'servidor_smtp': request.POST.get('servidor_smtp', '').strip(),
            'puerto_smtp': request.POST.get('puerto_smtp', '465').strip(),
            'usuario_smtp': request.POST.get('usuario_smtp', '').strip(),
            'password_smtp': request.POST.get('password_smtp', '').strip(),
            'usar_tls': request.POST.get('usar_tls') in ['on', 'true', True],
            'usar_ssl': request.POST.get('usar_ssl') in ['on', 'true', True],
            'asunto': request.POST.get('asunto', '').strip(),
            'mensaje': request.POST.get('mensaje', '').strip(),
            'firma': request.POST.get('firma', '').strip(),
        }

        # Conservar contraseña anterior si se dejó vacía en el formulario
        if not data['password_smtp']:
            cfg_previa = get_config_mail(empresa.id)
            data['password_smtp'] = cfg_previa.get('password_smtp', '')

        # Manejo de logo de firma
        if request.POST.get('eliminar_logo') == 'true':
            eliminar_logo_firma(empresa.id)
            data['logo_firma'] = ''
        elif 'logo_firma' in request.FILES:
            logo_rel = guardar_logo_firma(empresa.id, request.FILES['logo_firma'])
            data['logo_firma'] = logo_rel
        else:
            cfg_previa = get_config_mail(empresa.id)
            data['logo_firma'] = cfg_previa.get('logo_firma', '')

        guardar_config_mail(empresa.id, data)
        return JsonResponse({'status': 'success', 'message': 'Configuración de correo guardada con éxito.'})
    except Exception as e:
        return JsonResponse({'error': f"Error guardando configuración: {str(e)}"}, status=400)


@login_required
@require_POST
def config_mails_probar(request):
    """
    Verifica las credenciales y conectividad SMTP sin realizar envíos a destinatarios.
    """
    empresa = getattr(request, 'empresa_actual', None)
    if not empresa:
        from empresas.models import Empresa
        empresa_id = request.session.get('empresa_id')
        if empresa_id:
            empresa = Empresa.objects.filter(id=empresa_id).first()

    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa'}, status=400)

    data = {
        'servidor_smtp': request.POST.get('servidor_smtp', '').strip(),
        'puerto_smtp': request.POST.get('puerto_smtp', '587').strip(),
        'usuario_smtp': request.POST.get('usuario_smtp', '').strip(),
        'password_smtp': request.POST.get('password_smtp', '').strip(),
        'usar_tls': request.POST.get('usar_tls') == 'on',
        'usar_ssl': request.POST.get('usar_ssl') == 'on',
    }

    # Si la contraseña vino vacía en la prueba, usar la guardada previamente
    if not data['password_smtp']:
        cfg_previa = get_config_mail(empresa.id)
        data['password_smtp'] = cfg_previa.get('password_smtp', '')

    ok, mensaje = SMTPService.probar_conexion(data)
    if ok:
        return JsonResponse({'status': 'success', 'message': mensaje})
    else:
        return JsonResponse({'status': 'error', 'message': mensaje}, status=400)

