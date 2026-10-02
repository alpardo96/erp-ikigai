import json
from decimal import Decimal
from django.shortcuts import render
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.db import transaction
from django.conf import settings
from verticalidades.estudio.models import TarifaEstudio, EnvioFacturaEstudio, GrupoEnvioEstudio
from verticalidades.estudio.services.config_mail_service import (
    get_config_mail, guardar_config_mail, is_config_activa,
    guardar_logo_firma, eliminar_logo_firma
)
from verticalidades.estudio.services.smtp_service import SMTPService


def _get_empresa_estudio(request):
    """
    Obtiene la empresa activa para la verticalidad Estudio de forma segura.
    Prioridades:
    1. request.empresa_actual (si middleware o view previa lo inyectó)
    2. request.session.get('empresa_id')
    3. Empresa con tipo_actividad == 'ESTUDIO'
    4. Primera empresa disponible en la base de datos
    Garantiza que la sesión tenga 'empresa_id' para futuras peticiones AJAX.
    """
    empresa = getattr(request, 'empresa_actual', None)
    if empresa:
        return empresa
    from empresas.models import Empresa
    empresa_id = request.session.get('empresa_id') if hasattr(request, 'session') else None
    if empresa_id:
        empresa = Empresa.objects.filter(id=empresa_id).first()
        if empresa:
            return empresa
    empresa = Empresa.objects.filter(tipo_actividad='ESTUDIO').first() or Empresa.objects.first()
    if empresa and hasattr(request, 'session') and 'empresa_id' not in request.session:
        request.session['empresa_id'] = empresa.id
    return empresa


@login_required
def actualizar_tarifas(request):
    """
    Renderiza la vista principal para actualizar tarifas de estudio.
    """
    empresa = _get_empresa_estudio(request)
    from productos.models import Producto
    from contable.models import Cuenta
    from facturacion.models import ClienteProveedor
    
    # Optimización: precargar rubro y su cuenta contable de ventas para asignación automática en la UI
    productos = Producto.objects.filter(empresa=empresa).select_related('rubro', 'rubro__cta_ventas').order_by('detalle')
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

    def _parse_decimal(val):
        """Convierte cadenas con punto o coma a Decimal de forma segura."""
        if val is None or val == '':
            return Decimal('0')
        s = str(val).strip().replace(',', '.')
        try:
            return Decimal(s)
        except Exception:
            return Decimal('0')

    try:
        data = json.loads(request.body)
        
        with transaction.atomic():
            for item in data:
                item_id = item.get('id')
                if item_id and not str(item_id).startswith('new_'):
                    tarifa = TarifaEstudio.objects.select_for_update().get(id=item_id, empresa=empresa)
                    modificado = False
                    
                    # Convertir a Decimal para la DB sanitizando coma o punto
                    t_f_nueva = _parse_decimal(item.get('tarifa_f_nueva', 0))
                    t_p_nueva = _parse_decimal(item.get('tarifa_p_nueva', 0))
                    
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

                    nuevo_cuenta_id = item.get('cuenta_id') or None
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
                            tarifa_f=_parse_decimal(item.get('tarifa_f_nueva', 0)),
                            tarifa_p=_parse_decimal(item.get('tarifa_p_nueva', 0)),
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

    tarifas = TarifaEstudio.objects.filter(empresa=empresa, activo=True).select_related('cliente', 'producto', 'cuenta').order_by('cliente__razon_social')
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
    empresa = _get_empresa_estudio(request)
    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa en el sistema.'}, status=400)

    activa, motivo = is_config_activa(empresa.id)
    config = get_config_mail(empresa.id)

    return render(request, 'estudio/envios_facturas.html', {
        'empresa_activa': empresa,
        'config_mail': config,
        'config_activa': activa,
        'config_motivo': motivo,
    })


def _calcular_sugerencias_agrupacion(envios_qs):
    """
    Analiza los comprobantes facturados del período para detectar oportunidades de consolidación:
    1. MISMO_EMAIL: Dos o más comprobantes que comparten el mismo correo electrónico y no están ya agrupados juntos.
    2. CLIENTE_MULTIPLE: Un cliente con 2 o más facturas en el período que no han sido agrupadas en un grupo.
    """
    from collections import defaultdict
    sugerencias = []

    def _extraer_email_envio(e):
        if e.destinatarios and isinstance(e.destinatarios, str) and e.destinatarios.strip():
            return e.destinatarios.strip()
        if e.grupo and e.grupo.destinatarios and isinstance(e.grupo.destinatarios, str) and e.grupo.destinatarios.strip():
            return e.grupo.destinatarios.strip()
        if e.cliente and e.cliente.correo and isinstance(e.cliente.correo, str) and e.cliente.correo.strip():
            return e.cliente.correo.strip()
        return ''

    por_email = defaultdict(list)
    por_cliente = defaultdict(list)

    for e in envios_qs:
        correo_cand = _extraer_email_envio(e).lower()
        if correo_cand:
            casillas = [c.strip() for c in correo_cand.split(',') if c.strip()]
            for c_ind in casillas:
                por_email[c_ind].append(e)

        if e.cliente_id:
            por_cliente[e.cliente_id].append(e)

    sets_sugeridos = set()

    for email_key, lista in por_email.items():
        lista_unica = []
        vistos = set()
        for env in lista:
            if env.id not in vistos:
                vistos.add(env.id)
                lista_unica.append(env)

        if len(lista_unica) < 2:
            continue

        clientes_dict = {}
        for env in lista_unica:
            if env.cliente:
                clientes_dict[env.cliente.pk] = env.cliente

        grupos_ids = {env.grupo_id for env in lista_unica}
        ya_agrupados = (len(grupos_ids) == 1 and None not in grupos_ids)

        if not ya_agrupados:
            ids_tupla = tuple(sorted(env.id for env in lista_unica))
            if ids_tupla in sets_sugeridos:
                continue
            sets_sugeridos.add(ids_tupla)

            es_multicliente = len(clientes_dict) > 1
            nombres_cli = [c.razon_social for c in clientes_dict.values()]
            if es_multicliente:
                titulo = f"Mismo correo ({email_key}) en {len(nombres_cli)} clientes"
                desc = f"Comparten la casilla '{email_key}': {', '.join(nombres_cli)} ({len(lista_unica)} comprobantes)."
                nombre_sug = f"Grupo {', '.join(nombres_cli[:2])}" + ("..." if len(nombres_cli) > 2 else "")
            else:
                c_nom = nombres_cli[0] if nombres_cli else "Cliente"
                titulo = f"{c_nom} (Múltiples comprobantes)"
                desc = f"Tiene {len(lista_unica)} comprobantes dirigidos a '{email_key}'."
                nombre_sug = f"Grupo {c_nom}"

            total_monto = sum(float(env.venta.total) for env in lista_unica if env.venta)

            sugerencias.append({
                'id_sug': f"email_{email_key}_{len(lista_unica)}",
                'tipo': 'MISMO_EMAIL' if es_multicliente else 'CLIENTE_MULTIPLE',
                'titulo': titulo,
                'descripcion': desc,
                'email': email_key,
                'nombre_grupo_sugerido': nombre_sug,
                'clientes_ids': list(clientes_dict.keys()),
                'clientes_nombres': nombres_cli,
                'comprobantes_count': len(lista_unica),
                'envio_ids': list(ids_tupla),
                'total_importe': total_monto,
                'es_multicliente': es_multicliente,
                'ya_agrupados': False
            })

    for c_id, lista in por_cliente.items():
        if len(lista) < 2:
            continue
        grupos_ids = {env.grupo_id for env in lista}
        ya_agrupados = (len(grupos_ids) == 1 and None not in grupos_ids)
        if ya_agrupados:
            continue

        ids_tupla = tuple(sorted(env.id for env in lista))
        if ids_tupla in sets_sugeridos:
            continue
        sets_sugeridos.add(ids_tupla)

        cli = lista[0].cliente
        c_nom = cli.razon_social if cli else "Cliente"
        email_cli = _extraer_email_envio(lista[0])
        total_monto = sum(float(env.venta.total) for env in lista if env.venta)

        sugerencias.append({
            'id_sug': f"cli_{c_id}_{len(lista)}",
            'tipo': 'CLIENTE_MULTIPLE',
            'titulo': f"{c_nom} (Múltiples comprobantes)",
            'descripcion': f"Registra {len(lista)} comprobantes facturados en este período.",
            'email': email_cli,
            'nombre_grupo_sugerido': f"Grupo {c_nom}",
            'clientes_ids': [c_id],
            'clientes_nombres': [c_nom],
            'comprobantes_count': len(lista),
            'envio_ids': list(ids_tupla),
            'total_importe': total_monto,
            'es_multicliente': False,
            'ya_agrupados': False
        })

    return sugerencias


@login_required
@require_GET
def api_envios_facturas(request):
    """
    Retorna la lista de comprobantes emitidos en el período y su estado de envío por correo.
    Descubre automáticamente comprobantes generados previamente que aún no tengan registro en EnvioFacturaEstudio.
    """
    empresa = _get_empresa_estudio(request)
    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa en el sistema.'}, status=400)

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

    # Pre-cargar mapeo de clientes a grupos activos de la empresa
    grupos_qs = GrupoEnvioEstudio.objects.filter(empresa=empresa, activo=True).prefetch_related('clientes')
    cliente_a_grupo = {}
    for g in grupos_qs:
        for c in g.clientes.all():
            cliente_a_grupo[c.pk] = g

    nuevos_envios = []
    for v in ventas_sin_envio:
        g_auto = cliente_a_grupo.get(v.cliente_id) if v.cliente_id else None
        dest = ''
        if g_auto and g_auto.destinatarios:
            dest = g_auto.destinatarios
        elif v.cliente and v.cliente.correo:
            dest = v.cliente.correo

        nuevos_envios.append(EnvioFacturaEstudio(
            empresa=empresa,
            venta=v,
            cliente=v.cliente,
            grupo=g_auto,
            periodo=periodo,
            destinatarios=dest,
            estado='PENDIENTE',
            creado_por=request.user,
            modificado_por=request.user
        ))
    if nuevos_envios:
        EnvioFacturaEstudio.objects.bulk_create(nuevos_envios)

    # Consultar todos los envíos del período
    envios_qs = list(EnvioFacturaEstudio.objects.filter(
        empresa=empresa,
        periodo=periodo
    ).select_related('venta', 'venta__tipo', 'cliente', 'grupo').order_by('cliente__razon_social', 'venta__numero'))

    # Sincronización automática y persistencia en BD para envíos existentes sin destinatarios o sin grupo
    envios_a_actualizar = []
    for e in envios_qs:
        modificado = False
        if not e.grupo_id and e.cliente_id and e.cliente_id in cliente_a_grupo:
            e.grupo = cliente_a_grupo[e.cliente_id]
            e.grupo_id = e.grupo.id
            modificado = True

        if not e.destinatarios or not e.destinatarios.strip():
            cand = ''
            if e.grupo and e.grupo.destinatarios and e.grupo.destinatarios.strip():
                cand = e.grupo.destinatarios.strip()
            elif e.cliente and e.cliente.correo and e.cliente.correo.strip():
                cand = e.cliente.correo.strip()
            
            if cand:
                e.destinatarios = cand
                modificado = True

        if modificado:
            envios_a_actualizar.append(e)

    if envios_a_actualizar:
        EnvioFacturaEstudio.objects.bulk_update(envios_a_actualizar, ['grupo', 'destinatarios'])

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

        dest_final = e.destinatarios
        if not dest_final or not dest_final.strip():
            if e.grupo and e.grupo.destinatarios:
                dest_final = e.grupo.destinatarios
            elif v.cliente and v.cliente.correo:
                dest_final = v.cliente.correo
            else:
                dest_final = ''

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
            'destinatarios': (dest_final or '').strip(),
            'grupo_id': e.grupo_id,
            'grupo_nombre': e.grupo.nombre if e.grupo else '',
            'grupo_destinatarios': e.grupo.destinatarios if e.grupo else '',
            'modo_adjunto': e.modo_adjunto,
            'archivo_adjunto_url': e.archivo_adjunto.url if e.archivo_adjunto else '',
            'archivo_adjunto_nombre': e.archivo_adjunto.name.split('/')[-1] if e.archivo_adjunto else '',
            'estado': e.estado,
            'respuesta_smtp': e.respuesta_smtp or '',
            'fecha_envio': e.fecha_envio.strftime('%d/%m/%Y %H:%M') if e.fecha_envio else '',
            'intentos': e.intentos
        })

    grupos_data = [
        {
            'id': g.id,
            'nombre': g.nombre,
            'destinatarios': g.destinatarios,
            'clientes_ids': list(g.clientes.values_list('pk', flat=True)),
            'clientes_nombres': [c.razon_social for c in g.clientes.all()],
            'total_cbtes_periodo': sum(1 for e in envios_qs if e.grupo_id == g.id),
            'observaciones': g.observaciones or ''
        }
        for g in grupos_qs
    ]

    sugerencias = _calcular_sugerencias_agrupacion(envios_qs)

    return JsonResponse({
        'periodo': periodo,
        'metricas': {
            'total': conteo_total,
            'enviados': conteo_enviados,
            'pendientes': conteo_pendientes,
            'errores': conteo_errores,
        },
        'grupos': grupos_data,
        'sugerencias': sugerencias,
        'items': items
    })


@login_required
@require_POST
def api_enviar_pendientes(request):
    """
    Endpoint de streaming para enviar masivamente todos los comprobantes pendientes o con error.
    Utiliza StreamingHttpResponse con ndjson para actualización en tiempo real y bloqueo del frontend.
    """
    empresa = _get_empresa_estudio(request)
    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa en el sistema.'}, status=400)

    try:
        body = json.loads(request.body) if request.body else {}
    except Exception:
        body = {}
    periodo = body.get('periodo', request.POST.get('periodo', '')).strip()
    ids_seleccionados = body.get('ids', [])

    if not periodo and not ids_seleccionados:
        return JsonResponse({'error': 'Período o IDs no especificados'}, status=400)

    if ids_seleccionados:
        # Enviar exactamente los comprobantes seleccionados por el usuario
        envios_pendientes = EnvioFacturaEstudio.objects.filter(
            empresa=empresa,
            id__in=ids_seleccionados
        ).select_related('venta', 'venta__tipo', 'cliente', 'grupo').order_by('cliente__razon_social')
    else:
        # Fallback a todos los pendientes o con error del período
        envios_pendientes = EnvioFacturaEstudio.objects.filter(
            empresa=empresa,
            periodo=periodo,
            estado__in=['PENDIENTE', 'ERROR']
        ).select_related('venta', 'venta__tipo', 'cliente', 'grupo').order_by('cliente__razon_social')

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
    empresa = _get_empresa_estudio(request)
    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa en el sistema.'}, status=400)

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
    empresa = _get_empresa_estudio(request)
    if not empresa:
        return HttpResponse('<div class="p-6 text-red-500 font-bold">No hay empresa activa en el sistema.</div>')

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
    empresa = _get_empresa_estudio(request)
    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa en el sistema.'}, status=400)

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
    empresa = _get_empresa_estudio(request)
    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa en el sistema.'}, status=400)

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


@login_required
def estudio_envio_editar_modal(request, envio_id):
    """
    Renderiza el modal para configurar si se envía la factura del sistema,
    si se intercambia por un comprobante cargado (monotributo/presupuesto)
    o si se envían agregados (sistema + cargado).
    """
    empresa = _get_empresa_estudio(request)
    if not empresa:
        return HttpResponse('<div class="p-6 text-red-500 font-bold">No hay empresa activa en el sistema.</div>')

    envio = EnvioFacturaEstudio.objects.filter(
        id=envio_id,
        empresa=empresa
    ).select_related('venta', 'venta__tipo', 'cliente').first()

    if not envio:
        return HttpResponse('<div class="p-6 text-red-500 font-bold">Comprobante de envío no encontrado.</div>')

    return render(request, 'estudio/modals/editar_envio_modal.html', {
        'envio': envio,
        'venta': envio.venta,
        'cliente': envio.cliente,
    })


@login_required
@require_POST
def estudio_envio_guardar_edicion(request, envio_id):
    """
    Guarda los cambios de modo de comprobante, archivo adjunto y destinatarios.
    """
    empresa = _get_empresa_estudio(request)
    if not empresa:
        return JsonResponse({'status': 'error', 'error': 'No hay empresa activa en el sistema.'}, status=400)

    envio = EnvioFacturaEstudio.objects.filter(
        id=envio_id,
        empresa=empresa
    ).select_related('venta', 'cliente').first()

    if not envio:
        return JsonResponse({'status': 'error', 'error': 'Registro de envío no encontrado.'}, status=404)

    modo_adjunto = request.POST.get('modo_adjunto', 'SISTEMA').strip()
    destinatarios = request.POST.get('destinatarios', '').strip()
    eliminar_adjunto = request.POST.get('eliminar_adjunto') == '1'

    if modo_adjunto not in ['SISTEMA', 'REEMPLAZAR', 'AMBOS']:
        modo_adjunto = 'SISTEMA'

    envio.modo_adjunto = modo_adjunto
    if destinatarios:
        envio.destinatarios = destinatarios

    if eliminar_adjunto:
        if envio.archivo_adjunto:
            try:
                envio.archivo_adjunto.delete(save=False)
            except Exception:
                pass
        envio.archivo_adjunto = None

    if 'archivo_adjunto' in request.FILES:
        archivo = request.FILES['archivo_adjunto']
        envio.archivo_adjunto = archivo

    envio.modificado_por = request.user
    envio.save()

    return JsonResponse({
        'status': 'success',
        'mensaje': 'Configuración de envío actualizada exitosamente.',
        'envio_id': envio.id,
        'modo_adjunto': envio.modo_adjunto,
        'destinatarios': envio.destinatarios,
        'archivo_adjunto_url': envio.archivo_adjunto.url if envio.archivo_adjunto else '',
        'archivo_adjunto_nombre': envio.archivo_adjunto.name.split('/')[-1] if envio.archivo_adjunto else ''
    })


@login_required
def api_grupos_envio(request):
    """
    GET: Lista todos los grupos de envío de la empresa activa con sus clientes asociados.
    POST: Crea o edita un GrupoEnvioEstudio permanente.
    """
    empresa = _get_empresa_estudio(request)
    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa en el sistema.'}, status=400)

    if request.method == 'GET':
        periodo = request.GET.get('periodo', '').strip()
        grupos = GrupoEnvioEstudio.objects.filter(empresa=empresa, activo=True).prefetch_related('clientes')
        data = []
        for g in grupos:
            data.append({
                'id': g.id,
                'nombre': g.nombre,
                'destinatarios': g.destinatarios,
                'clientes': [
                    {'id': c.pk, 'razon_social': c.razon_social, 'cuit': c.cuit, 'correo': c.correo or ''}
                    for c in g.clientes.all()
                ],
                'clientes_ids': list(g.clientes.values_list('pk', flat=True)),
                'observaciones': g.observaciones or '',
                'activo': g.activo
            })

        from facturacion.models import ClienteProveedor, Venta
        from collections import Counter

        # Obtener envíos del período
        envios_periodo_qs = EnvioFacturaEstudio.objects.filter(empresa=empresa)
        if periodo:
            envios_periodo_qs = envios_periodo_qs.filter(periodo=periodo)
        
        envios_periodo_list = list(envios_periodo_qs.select_related('cliente', 'venta', 'grupo'))
        
        # Conteo de facturas por cliente en este período
        conteo_por_cli = Counter(e.cliente_id for e in envios_periodo_list if e.cliente_id)

        # Clientes facturados únicamente (más los ya asignados a algún grupo de la empresa)
        cliente_ids_validos = set(conteo_por_cli.keys())
        for g in grupos:
            cliente_ids_validos.update(g.clientes.values_list('pk', flat=True))

        clientes_disponibles = []
        if cliente_ids_validos:
            for c in ClienteProveedor.objects.filter(pk__in=cliente_ids_validos, empresa=empresa).order_by('razon_social'):
                cbtes = conteo_por_cli.get(c.pk, 0)
                clientes_disponibles.append({
                    'id': c.pk,
                    'razon_social': c.razon_social,
                    'cuit': c.cuit,
                    'correo': c.correo or '',
                    'cbtes_periodo': cbtes
                })

        sugerencias = _calcular_sugerencias_agrupacion(envios_periodo_list)

        return JsonResponse({
            'status': 'success',
            'grupos': data,
            'clientes_disponibles': clientes_disponibles,
            'sugerencias': sugerencias
        })

    elif request.method == 'POST':
        try:
            body = json.loads(request.body) if request.body else {}
        except Exception:
            body = {}

        grupo_id = body.get('id')
        nombre = body.get('nombre', '').strip()
        destinatarios = body.get('destinatarios', '').strip()
        clientes_ids = body.get('clientes_ids', [])
        observaciones = body.get('observaciones', '').strip()

        if not nombre:
            return JsonResponse({'error': 'El nombre del grupo es obligatorio.'}, status=400)

        # Normalizar y validar destinatarios
        lista_emails = [e.strip() for e in destinatarios.split(',') if e.strip()]
        for em in lista_emails:
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError
            try:
                validate_email(em)
            except ValidationError:
                return JsonResponse({'error': f"El correo '{em}' no tiene un formato válido."}, status=400)
        destinatarios_normalizado = ", ".join(lista_emails)

        with transaction.atomic():
            if grupo_id:
                grupo = GrupoEnvioEstudio.objects.filter(id=grupo_id, empresa=empresa).first()
                if not grupo:
                    return JsonResponse({'error': 'Grupo no encontrado.'}, status=404)
                grupo.nombre = nombre
                grupo.destinatarios = destinatarios_normalizado
                grupo.observaciones = observaciones
                grupo.modificado_por = request.user
                grupo.save()
            else:
                grupo = GrupoEnvioEstudio.objects.create(
                    empresa=empresa,
                    nombre=nombre,
                    destinatarios=destinatarios_normalizado,
                    observaciones=observaciones,
                    activo=True,
                    creado_por=request.user,
                    modificado_por=request.user
                )

            if isinstance(clientes_ids, list):
                from facturacion.models import ClienteProveedor
                clientes_validos = ClienteProveedor.objects.filter(pk__in=clientes_ids, empresa=empresa)
                grupo.clientes.set(clientes_validos)

        return JsonResponse({
            'status': 'success',
            'mensaje': 'Grupo guardado exitosamente.',
            'grupo': {
                'id': grupo.id,
                'nombre': grupo.nombre,
                'destinatarios': grupo.destinatarios,
                'clientes_ids': list(grupo.clientes.values_list('pk', flat=True)),
                'clientes_nombres': [c.razon_social for c in grupo.clientes.all()],
                'observaciones': grupo.observaciones or ''
            }
        })


@login_required
@require_POST
def api_asignar_grupo_envios(request):
    """
    Asigna o desasigna comprobantes del período a un grupo de envío.
    Body JSON:
    - envio_ids: lista de IDs de EnvioFacturaEstudio
    - grupo_id: ID de GrupoEnvioEstudio o null (para desasociar / individual)
    - actualizar_destinatarios: boolean opcional (default True) para reemplazar destinatarios con los del grupo
    """
    empresa = _get_empresa_estudio(request)
    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa en el sistema.'}, status=400)

    try:
        body = json.loads(request.body) if request.body else {}
    except Exception:
        body = {}

    envio_ids = body.get('envio_ids', [])
    grupo_id = body.get('grupo_id')
    actualizar_destinatarios = body.get('actualizar_destinatarios', True)

    if not envio_ids:
        return JsonResponse({'error': 'No se especificaron comprobantes.'}, status=400)

    qs = EnvioFacturaEstudio.objects.filter(id__in=envio_ids, empresa=empresa)

    if grupo_id:
        grupo = GrupoEnvioEstudio.objects.filter(id=grupo_id, empresa=empresa).first()
        if not grupo:
            return JsonResponse({'error': 'Grupo no encontrado.'}, status=404)
        
        with transaction.atomic():
            for envio in qs:
                envio.grupo = grupo
                if actualizar_destinatarios and grupo.destinatarios:
                    envio.destinatarios = grupo.destinatarios
                envio.modificado_por = request.user
                envio.save(update_fields=['grupo', 'destinatarios', 'modificado_por', 'fecha_modificacion'])
    else:
        # Desagrupar
        with transaction.atomic():
            for envio in qs:
                envio.grupo = None
                envio.modificado_por = request.user
                # Restaurar destinatario por defecto si el cliente tiene
                if not envio.destinatarios and envio.cliente and envio.cliente.correo:
                    envio.destinatarios = envio.cliente.correo
                envio.save(update_fields=['grupo', 'destinatarios', 'modificado_por', 'fecha_modificacion'])

    return JsonResponse({
        'status': 'success',
        'mensaje': 'Asignación de grupo actualizada correctamente.',
        'afectados': qs.count()
    })


@login_required
@require_POST
def api_eliminar_grupo_envio(request, grupo_id):
    """
    Elimina un grupo de envío. Los comprobantes asociados vuelven a ser individuales (SET_NULL).
    """
    empresa = _get_empresa_estudio(request)
    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa en el sistema.'}, status=400)

    grupo = GrupoEnvioEstudio.objects.filter(id=grupo_id, empresa=empresa).first()
    if not grupo:
        return JsonResponse({'error': 'Grupo no encontrado.'}, status=404)

    nombre_grupo = grupo.nombre
    grupo.delete()

    return JsonResponse({
        'status': 'success',
        'mensaje': f"Grupo '{nombre_grupo}' eliminado con éxito. Las facturas asociadas ahora son individuales."
    })


@login_required
@require_POST
def api_aplicar_sugerencia_grupo(request):
    """
    Crea o reutiliza un grupo a partir de una sugerencia automática y asigna de inmediato
    los comprobantes del lote en una sola operación atómica.
    """
    empresa = _get_empresa_estudio(request)
    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa en el sistema.'}, status=400)

    try:
        body = json.loads(request.body) if request.body else {}
    except Exception:
        body = {}

    nombre = body.get('nombre', '').strip()
    destinatarios = body.get('destinatarios', '').strip()
    clientes_ids = body.get('clientes_ids', [])
    envio_ids = body.get('envio_ids', [])
    observaciones = body.get('observaciones', 'Creado desde sugerencia automática').strip()

    if not nombre or not destinatarios:
        return JsonResponse({'error': 'Nombre y destinatarios son requeridos.'}, status=400)

    lista_emails = [e.strip() for e in destinatarios.split(',') if e.strip()]
    for em in lista_emails:
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        try:
            validate_email(em)
        except ValidationError:
            return JsonResponse({'error': f"El correo '{em}' no tiene formato válido."}, status=400)
    destinatarios_norm = ", ".join(lista_emails)

    with transaction.atomic():
        grupo = GrupoEnvioEstudio.objects.filter(empresa=empresa, nombre__iexact=nombre).first()
        if not grupo:
            grupo = GrupoEnvioEstudio.objects.create(
                empresa=empresa,
                nombre=nombre,
                destinatarios=destinatarios_norm,
                observaciones=observaciones,
                activo=True,
                creado_por=request.user,
                modificado_por=request.user
            )
        else:
            grupo.destinatarios = destinatarios_norm
            grupo.activo = True
            grupo.modificado_por = request.user
            grupo.save()

        if clientes_ids:
            from facturacion.models import ClienteProveedor
            clientes = ClienteProveedor.objects.filter(pk__in=clientes_ids, empresa=empresa)
            grupo.clientes.add(*clientes)

        if envio_ids:
            envios = EnvioFacturaEstudio.objects.filter(id__in=envio_ids, empresa=empresa)
            for env in envios:
                env.grupo = grupo
                env.destinatarios = grupo.destinatarios
                env.modificado_por = request.user
                env.save(update_fields=['grupo', 'destinatarios', 'modificado_por', 'fecha_modificacion'])

    return JsonResponse({
        'status': 'success',
        'mensaje': f"Grupo '{grupo.nombre}' creado y {len(envio_ids)} comprobantes agrupados exitosamente.",
        'grupo_id': grupo.id,
        'grupo_nombre': grupo.nombre
    })



