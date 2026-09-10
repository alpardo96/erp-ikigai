from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Max
from decimal import Decimal
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
import json
from facturacion.models import Venta, VentaItem, Compra, CompraItem, TipoComprobante, ClienteProveedor
from productos.models import Producto, Subproducto, ALICUOTAS_ARCA_MAP
from contable.models import AlicuotaIva
from empresas.models import Ejercicio, Empresa, PuntoVenta, EmpresaTrazabilidad
from facturacion.forms import VentaForm, CompraForm

class VentasTrazabilidadCargaView(LoginRequiredMixin, View):
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')
        
        if not empresa_id or not sucursal_id:
            messages.warning(request, "Por favor, seleccione una empresa y sucursal primero.")
            return redirect('seleccion_empresa')

        # Limpiar ítems temporales al iniciar carga nueva
        request.session['venta_trazabilidad_items_temp'] = []

        initial_data = {
            'empresa': empresa_id,
            'sucursal': sucursal_id,
            'fecha': timezone.localdate()
        }
        form = VentaForm(initial=initial_data)
        
        from empresas.models import Empresa
        try:
            empresa = Empresa.objects.get(pk=empresa_id)
            if empresa.tipo_actividad and empresa.tipo_actividad.lower() == 'armeria':
                form.fields['tipo'].queryset = form.fields['tipo'].queryset.exclude(codigo__startswith='PRE')
        except Empresa.DoesNotExist:
            pass
        
        puntos_venta = PuntoVenta.objects.filter(sucursal_id=sucursal_id, activo=True)
        modo_edicion = getattr(empresa, 'modo_edicion_facturacion', 'DESCUENTO') if empresa else 'DESCUENTO'
        
        return render(request, 'armeria/ventas_trazabilidad_carga.html', {
            'form': form,
            'puntos_venta': puntos_venta,
            'modo_edicion': modo_edicion
        })

    def post(self, request):
        data = request.POST.copy()
        campos_monetarios = ['neto', 'iva', 'p_iibb', 'p_iva', 'otros', 'total', 'cotizacion', 'efectivo', 'tarjeta', 'transferencia', 'valores']
        
        for campo in campos_monetarios:
            val = data.get(campo, '').strip()
            if val:
                data[campo] = val.replace('.', '').replace(',', '.')
            else:
                data[campo] = '0'

        form = VentaForm(data)
        items_temp = request.session.get('venta_trazabilidad_items_temp', [])

        if not items_temp:
            messages.error(request, "Debe cargar al menos un producto en la grilla.")
            
            from empresas.models import Empresa
            try:
                empresa = Empresa.objects.get(pk=request.session.get('empresa_id'))
                if empresa.tipo_actividad and empresa.tipo_actividad.lower() == 'armeria':
                    form.fields['tipo'].queryset = form.fields['tipo'].queryset.exclude(codigo__startswith='PRE')
            except Empresa.DoesNotExist:
                pass
                
            from empresas.models import PuntoVenta
            puntos_venta = PuntoVenta.objects.filter(sucursal_id=request.session.get('sucursal_id'), activo=True)
            return render(request, 'armeria/ventas_trazabilidad_carga.html', {'form': form, 'puntos_venta': puntos_venta})

        if form.is_valid():
            cliente = form.cleaned_data['cliente']
            empresa_id = request.session.get('empresa_id')
            
            # Validacion CLU para Armeria
            from facturacion.helpers import validar_clu_cliente_armeria
            es_valido, msj_err = validar_clu_cliente_armeria(cliente, empresa_id)
            if not es_valido:
                messages.error(request, f"Error: {msj_err}")
                from empresas.models import Empresa, PuntoVenta
                try:
                    emp_activa = Empresa.objects.get(pk=empresa_id)
                    if emp_activa.tipo_actividad and emp_activa.tipo_actividad.lower() == 'armeria':
                        form.fields['tipo'].queryset = form.fields['tipo'].queryset.exclude(codigo__startswith='PRE')
                except Empresa.DoesNotExist:
                    pass
                puntos_venta = PuntoVenta.objects.filter(sucursal_id=request.session.get('sucursal_id'), activo=True)
                return render(request, 'armeria/ventas_trazabilidad_carga.html', {'form': form, 'puntos_venta': puntos_venta})


            try:
                empresa_id = request.session.get('empresa_id')
                empresa_obj = Empresa.objects.get(pk=empresa_id)
                venta_temp = form.save(commit=False)
                cae_afip, vto_cae_afip, numero_afip, cod_qr_afip = None, None, None, None

                # En Venta Trazabilidad fiscal (condic == 1), AFIP es OBLIGATORIO Y ESTRICTO.
                if venta_temp.condic == 1 and venta_temp.tipo.codigo.isdigit():
                    from facturacion.services.afip_service import AFIPService
                    from facturacion.views import validar_y_obtener_documento_receptor
                    try:
                        doc_tipo, doc_nro, cond_iva_rec = validar_y_obtener_documento_receptor(cliente)
                        cbte_tipo_num = int(venta_temp.tipo.codigo)

                        # Validación de coherencia fiscal previa a ARCA
                        if cbte_tipo_num == 1 and cond_iva_rec not in [1, 6]:
                            messages.error(request, "Inconsistencia fiscal: No se puede emitir Factura A a un Consumidor Final o Exento. Debe emitir Factura B.")
                            return render(request, 'armeria/ventas_trazabilidad_carga.html', {'form': form, 'puntos_venta': PuntoVenta.objects.filter(sucursal_id=request.session.get('sucursal_id'), activo=True)})
                        
                        if cbte_tipo_num == 6 and cond_iva_rec in [1, 6]:
                            messages.error(request, "Inconsistencia fiscal: A Responsables Inscriptos y Monotributistas corresponde emitirles Factura A.")
                            return render(request, 'armeria/ventas_trazabilidad_carga.html', {'form': form, 'puntos_venta': PuntoVenta.objects.filter(sucursal_id=request.session.get('sucursal_id'), activo=True)})

                        alicuotas_dict = {}
                        tot_neto_alic = Decimal('0.00')
                        tot_iva_alic = Decimal('0.00')
                        for item in items_temp:
                            alic = Decimal(str(item['iva']))
                            precio_tot = Decimal(str(item['total']))
                            factor_iva = Decimal('1') + alic / Decimal('100')
                            neto_item = (precio_tot / factor_iva).quantize(Decimal('0.01'))
                            iva_item = precio_tot - neto_item
                            
                            if alic not in alicuotas_dict:
                                alicuotas_dict[alic] = {
                                    'Id': ALICUOTAS_ARCA_MAP.get(alic, 5),
                                    'BaseImp': Decimal('0.00'),
                                    'Importe': Decimal('0.00')
                                }
                            alicuotas_dict[alic]['BaseImp'] += neto_item
                            alicuotas_dict[alic]['Importe'] += iva_item
                            tot_neto_alic += neto_item
                            tot_iva_alic += iva_item

                        alicuotas_list = [
                            {
                                'id_arca': v['Id'],
                                'base_imponible': float(v['BaseImp']),
                                'importe_iva': float(v['Importe'])
                            }
                            for k, v in alicuotas_dict.items() if k > 0
                        ]

                        datos_afip = {
                            'pto_vta': venta_temp.punto,
                            'cbte_tipo': int(venta_temp.tipo.codigo),
                            'concepto': 1,
                            'doc_tipo': doc_tipo,
                            'doc_nro': doc_nro,
                            'cbte_fch': venta_temp.fecha.strftime('%Y%m%d'),
                            'imp_total': float(tot_neto_alic + tot_iva_alic),
                            'imp_tot_conc': 0.0,
                            'imp_neto': float(tot_neto_alic),
                            'imp_op_ex': 0.0,
                            'imp_iva': float(tot_iva_alic),
                            'condicion_iva_receptor_id': cond_iva_rec,
                            'mon_id': 'DOL' if venta_temp.moneda == 'DOL' else 'PES',
                            'mon_cotiz': float(venta_temp.cotizacion) if venta_temp.moneda == 'DOL' else 1.0,
                        }

                        afip_service = AFIPService(empresa_obj)
                        res_afip = afip_service.emitir_comprobante(datos_afip, alicuotas_list)

                        if not res_afip['exito']:
                            messages.error(request, f"Rechazo ARCA/AFIP: {res_afip['error']}. No es posible emitir comprobantes de trazabilidad sin aprobación de AFIP.")
                            return render(request, 'armeria/ventas_trazabilidad_carga.html', {'form': form, 'puntos_venta': PuntoVenta.objects.filter(sucursal_id=request.session.get('sucursal_id'), activo=True)})

                        cae_afip = res_afip['cae']
                        vto_cae_afip = res_afip['vto_cae']
                        numero_afip = res_afip['numero_comprobante']
                        cod_qr_afip = res_afip['cod_qr']

                    except Exception as e:
                        messages.error(request, f"Error de conexión con ARCA/AFIP: {str(e)}. La facturación fiscal por trazabilidad requiere AFIP conectado y funcional.")
                        return render(request, 'armeria/ventas_trazabilidad_carga.html', {'form': form, 'puntos_venta': PuntoVenta.objects.filter(sucursal_id=request.session.get('sucursal_id'), activo=True)})

                with transaction.atomic():
                    venta = form.save(commit=False)
                    venta.condic = 1
                    venta.usuario = request.user
                    venta.empresa_id = request.session.get('empresa_id')
                    venta.sucursal_id = request.session.get('sucursal_id')
                    venta.periodo = venta.fecha.strftime('%Y-%m')
                    venta.ejercicio = Ejercicio.objects.filter(
                        empresa_id=venta.empresa_id,
                        inicio__lte=venta.fecha,
                        cierre__gte=venta.fecha
                    ).first()
                    venta.estado = 0
                    venta.cobrado = 0
                    venta.saldo = venta.total
                    venta.efectivo = 0
                    venta.tarjeta = 0
                    venta.transferencia = 0
                    venta.valores = 0
                    if cae_afip and numero_afip:
                        venta.cae = cae_afip
                        venta.vto_cae = vto_cae_afip
                        venta.numero = numero_afip
                        venta.cod_qr = cod_qr_afip
                    elif not venta.numero:
                        ultimo = Venta.objects.filter(
                            empresa_id=venta.empresa_id,
                            tipo=venta.tipo,
                            punto=venta.punto
                        ).aggregate(max_num=Max('numero'))['max_num'] or 0
                        venta.numero = ultimo + 1
                    
                    venta.save()

                    for item in items_temp:
                        subproducto = get_object_or_404(Subproducto, serie=item['serie'], empresa_id=request.session.get('empresa_id'))
                        producto = subproducto.producto
                        
                        # 1. Crear ítem de venta
                        VentaItem.objects.create(
                            venta=venta,
                            producto=producto,
                            cantidad=1,
                            precio_unitario=item['precio'],
                            porcentaje_descuento=item.get('descuento', 0),
                            iva_alicuota=item['iva'],
                            total=item['total'],
                            moneda_origen=item.get('moneda_origen', 'PES'),
                            cotizacion_aplicada=item.get('cotizacion_aplicada', 1.0),
                            precio_origen=item.get('precio_origen', item['precio'])
                        )
                        
                        # 2. Vincular subproducto y marcarlo como VENDIDO
                        subproducto.situacion = 'VENDIDA'
                        subproducto.venta = venta
                        subproducto.fecvta = venta.fecha
                        subproducto.precio_neto = Decimal(str(item['precio']))
                        subproducto.precio_total = Decimal(str(item['total']))
                        subproducto.save()

                    # 3. Si se aplicó una Reserva SIGIMAC, netear el recibo contra la factura
                    reserva_id = request.POST.get('reserva_id')
                    if reserva_id:
                        from verticalidades.armeria.models import ReservaArma
                        from tesoreria.models import ReciboAplicacion
                        from contable.services.saldos import recalcular_saldo_venta
                        reserva = ReservaArma.objects.filter(id=reserva_id, empresa_id=venta.empresa_id, estado='PENDIENTE').first()
                        if reserva:
                            monto_aplicar = min(reserva.monto_reservado, venta.total)
                            ReciboAplicacion.objects.create(
                                recibo=reserva.recibo_reserva,
                                venta=venta,
                                importe=monto_aplicar,
                                importe_pesos=monto_aplicar
                            )
                            recalcular_saldo_venta(venta.pk)
                            reserva.estado = 'APLICADA'
                            reserva.venta_aplicada = venta
                            reserva.fecha_resolucion = timezone.localdate()
                            reserva.save()

                    request.session['venta_trazabilidad_items_temp'] = []
                    messages.success(request, f"¡Facturación por Trazabilidad {venta.numero} registrada con éxito! Series dadas de baja.")
                    return redirect('ventas_trazabilidad_carga')

            except Exception as e:
                messages.error(request, f"Error crítico al guardar la venta: {str(e)}")
        
        if not form.is_valid():
            messages.error(request, f"Error en los datos del comprobante: {form.errors.as_text()}")
        
        from empresas.models import Empresa
        try:
            empresa = Empresa.objects.get(pk=request.session.get('empresa_id'))
            if empresa.tipo_actividad and empresa.tipo_actividad.lower() == 'armeria':
                form.fields['tipo'].queryset = form.fields['tipo'].queryset.exclude(codigo__startswith='PRE')
        except Empresa.DoesNotExist:
            pass
            
        from empresas.models import PuntoVenta
        puntos_venta = PuntoVenta.objects.filter(sucursal_id=request.session.get('sucursal_id'), activo=True)
        return render(request, 'armeria/ventas_trazabilidad_carga.html', {'form': form, 'puntos_venta': puntos_venta})

@login_required
def agregar_item_venta_trazabilidad(request):
    """
    Busca el subproducto por serie y lo agrega a la grilla de ventas.
    """
    from empresas.models import Empresa as _Empresa
    empresa_activa = _Empresa.objects.filter(pk=request.session.get('empresa_id')).first()
    modo_edicion = getattr(empresa_activa, 'modo_edicion_facturacion', 'DESCUENTO')

    moneda_anterior = request.session.get('venta_trazabilidad_moneda', 'PES')
    moneda = request.POST.get('moneda') or request.GET.get('moneda') or moneda_anterior
    request.session['venta_trazabilidad_moneda'] = moneda

    from empresas.models import CotizacionMoneda
    empresa_id = request.session.get('empresa_id')
    cotizacion_global = 1.0
    if empresa_id:
        try:
            cot_obj = CotizacionMoneda.objects.get(empresa_id=empresa_id)
            cotizacion_global = float(cot_obj.dolar_venta)
        except CotizacionMoneda.DoesNotExist:
            cotizacion_global = 1.0

    if request.method == 'GET' or not request.POST.get('serie_escaneada'):
        items = request.session.get('venta_trazabilidad_items_temp', [])
        if moneda != moneda_anterior and items and cotizacion_global > 0:
            for item in items:
                precio_actual = float(item.get('precio', 0))
                if moneda_anterior == 'PES' and moneda == 'DOL':
                    nuevo_precio = round(precio_actual / cotizacion_global, 2)
                elif moneda_anterior == 'DOL' and moneda == 'PES':
                    nuevo_precio = round(precio_actual * cotizacion_global, 2)
                else:
                    nuevo_precio = round(precio_actual, 2)
                
                item['precio'] = nuevo_precio
                item['precio_base'] = nuevo_precio
                item['total'] = nuevo_precio
                item['cotizacion_aplicada'] = cotizacion_global
            
            request.session['venta_trazabilidad_items_temp'] = items
            request.session.modified = True

        response = render(request, 'armeria/partials/venta_trazabilidad_items_tabla.html', {
            'items': items,
            'moneda': moneda,
            'modo_edicion': modo_edicion
        })
        response['HX-Trigger'] = json.dumps({'actualizarTotales': True})
        return response

    serie = request.POST.get('serie_escaneada', '').strip().upper()

    subproducto = Subproducto.objects.filter(serie=serie, empresa_id=request.session.get('empresa_id')).exclude(situacion='VENDIDA').first()
    if not subproducto:
        return HttpResponse('<div class="p-4 bg-red-100 text-red-700 font-bold">Serie no encontrada o ya vendida.</div>', status=200)

    items = request.session.get('venta_trazabilidad_items_temp')
    if items is None:
        items = []
        request.session['venta_trazabilidad_items_temp'] = items

    # Evitar duplicados en grilla
    if any(item['serie'] == serie for item in items):
        return HttpResponse('<div class="p-4 bg-red-100 text-red-700 font-bold">Esta serie ya está en la lista de ventas.</div>', status=200)

    producto = subproducto.producto
    iva_alicuota = float(producto.alic_iva_porc)
    precio_lista = float(producto.precio_total or 0)
    moneda_origen = getattr(producto, 'moneda', 'PES')

    if moneda == 'DOL':
        if moneda_origen == 'PES' and cotizacion_global > 0:
            precio_unitario = round(precio_lista / cotizacion_global, 2)
        else:
            precio_unitario = round(precio_lista, 2)
    else:
        if moneda_origen == 'DOL':
            precio_unitario = round(precio_lista * cotizacion_global, 2)
        else:
            precio_unitario = round(precio_lista, 2)

    total_linea = precio_unitario
    descuento_maximo = float(producto.rubro.descuento_maximo) if producto.rubro else 0.0

    items.append({
        'index': len(items),
        'producto_id': producto.id,
        'codigo': producto.cod_prov or producto.id,
        'detalle': producto.detalle,
        'serie': serie,
        'cuim': subproducto.cuim,
        'cantidad': 1,
        'precio': precio_unitario,
        'precio_base': precio_unitario,
        'iva': iva_alicuota,
        'total': total_linea,
        'descuento': 0.0,
        'descuento_maximo': descuento_maximo,
        'requiere_autorizacion': False,
        'alerta_precio_duplicado': False,
        'moneda_origen': moneda_origen,
        'cotizacion_aplicada': cotizacion_global,
        'precio_origen': precio_lista,
    })
    
    request.session['venta_trazabilidad_items_temp'] = items
    request.session.modified = True
    
    response = render(request, 'armeria/partials/venta_trazabilidad_items_tabla.html', {
        'items': items,
        'moneda': moneda,
        'modo_edicion': modo_edicion
    })
    response['HX-Trigger'] = json.dumps({
        'limpiarInputsTrazabilidad': True,
        'actualizarTotales': True
    })
    return response

@login_required
def editar_item_venta_trazabilidad(request, index):
    from empresas.models import Empresa as _Empresa
    empresa_activa = _Empresa.objects.filter(pk=request.session.get('empresa_id')).first()
    modo_edicion = getattr(empresa_activa, 'modo_edicion_facturacion', 'DESCUENTO')

    items = request.session.get('venta_trazabilidad_items_temp', [])
    moneda = request.session.get('venta_trazabilidad_moneda', 'PES')
    if 0 <= index < len(items):
        try:
            item = items[index]
            precio_base = float(item.get('precio_base', item.get('precio', 0)) or 0)
            descuento_maximo = float(item.get('descuento_maximo', 0))

            if modo_edicion == 'PRECIO':
                raw_precio = str(request.POST.get('precio', request.POST.get('total_linea', '0'))).replace('.', '').replace(',', '.')
                precio_ingresado = float(raw_precio or 0)
                item['precio'] = precio_ingresado
                item['total'] = precio_ingresado
                if precio_ingresado < precio_base and precio_base > 0:
                    item['descuento'] = round(((precio_base - precio_ingresado) / precio_base) * 100.0, 2)
                else:
                    item['descuento'] = 0.0
                item['alerta_precio_duplicado'] = precio_ingresado > (precio_base * 2) if precio_base > 0 else False
            else:
                raw_descuento = str(request.POST.get('descuento', '0')).replace('.', '').replace(',', '.')
                descuento = float(raw_descuento or 0)
                item['descuento'] = descuento
                item['total'] = round(precio_base * (1 - (descuento / 100.0)), 2)

            item['requiere_autorizacion'] = float(item.get('descuento', 0)) > descuento_maximo
            request.session['venta_trazabilidad_items_temp'] = items
            request.session.modified = True
        except (ValueError, TypeError):
            pass

    response = render(request, 'armeria/partials/venta_trazabilidad_items_tabla.html', {
        'items': items,
        'moneda': moneda,
        'modo_edicion': modo_edicion
    })
    response['HX-Trigger'] = json.dumps({
        'actualizarTotales': {
            'requiere_autorizacion': any(i.get('requiere_autorizacion', False) for i in items)
        }
    })
    return response

@login_required
def quitar_item_venta_trazabilidad(request, index):
    from empresas.models import Empresa as _Empresa
    empresa_activa = _Empresa.objects.filter(pk=request.session.get('empresa_id')).first()
    modo_edicion = getattr(empresa_activa, 'modo_edicion_facturacion', 'DESCUENTO')

    items = request.session.get('venta_trazabilidad_items_temp', [])
    moneda = request.session.get('venta_trazabilidad_moneda', 'PES')
    if 0 <= index < len(items):
        items.pop(index)
        for i, item in enumerate(items):
            item['index'] = i
    request.session['venta_trazabilidad_items_temp'] = items
    response = render(request, 'armeria/partials/venta_trazabilidad_items_tabla.html', {
        'items': items,
        'moneda': moneda,
        'modo_edicion': modo_edicion
    })
    response['HX-Trigger'] = json.dumps({'actualizarTotales': True})
    return response


# =========================================================================
# COMPRA TRAZABILIDAD (Carga de Compras con Número de Serie / CUIM / Estado)
# =========================================================================

class ComprasTrazabilidadCargaView(LoginRequiredMixin, View):
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')
        
        if not empresa_id or not sucursal_id:
            messages.warning(request, "Por favor, seleccione una empresa y sucursal primero.")
            return redirect('seleccion_empresa')

        request.session['compra_trazabilidad_items_temp'] = []

        tipo_30 = TipoComprobante.objects.filter(codigo__in=['030', '30']).first()
        if not tipo_30:
            messages.error(request, "No se encontró el Tipo de Comprobante '030' (Comprobantes de Compra de Bienes Usados). Configúrelo antes de continuar.")
            return redirect('compras_index')

        initial_data = {
            'empresa': empresa_id,
            'sucursal': sucursal_id,
            'fecha': timezone.localdate(),
            'moneda': 'PES',
            'cotizacion': Decimal('1.0'),
            'tipo': tipo_30.id,
        }
        form = CompraForm(initial=initial_data)
        form.fields['proveedor'].queryset = ClienteProveedor.objects.filter(empresa_id=empresa_id).order_by('razon_social')
        
        empresa = Empresa.objects.filter(pk=empresa_id).first()
        config_traz, _ = EmpresaTrazabilidad.objects.get_or_create(empresa_id=empresa_id, defaults={'empresa': empresa})
        alicuotas_iva = AlicuotaIva.objects.filter(activo=True).order_by('orden', 'codigo')

        return render(request, 'armeria/compras_trazabilidad_carga.html', {
            'form': form,
            'empresa': empresa,
            'config_trazabilidad': config_traz,
            'alicuotas_iva': alicuotas_iva,
            'puntos_venta': PuntoVenta.objects.filter(sucursal_id=sucursal_id, activo=True),
            'tipo_30': tipo_30,
        })

    def post(self, request):
        data = request.POST.copy()
        campos_monetarios = ['neto', 'iva', 'p_iibb', 'p_iva', 'otros', 'total', 'cotizacion', 'exento', 'no_gravado', 'descuento', 'subtotal']
        for campo in campos_monetarios:
            val = data.get(campo, '').strip()
            if val:
                data[campo] = val.replace('.', '').replace(',', '.')
            else:
                data[campo] = '0'
        
        data['condic'] = '1'

        form = CompraForm(data)
        items_temp = request.session.get('compra_trazabilidad_items_temp', [])
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')

        if not items_temp:
            messages.error(request, "Debe cargar al menos un subproducto en la grilla.")
            empresa = Empresa.objects.filter(pk=empresa_id).first()
            config_traz, _ = EmpresaTrazabilidad.objects.get_or_create(empresa_id=empresa_id, defaults={'empresa': empresa})
            form.fields['proveedor'].queryset = ClienteProveedor.objects.filter(empresa_id=empresa_id).order_by('razon_social')
            return render(request, 'armeria/compras_trazabilidad_carga.html', {
                'form': form,
                'empresa': empresa,
                'config_trazabilidad': config_traz,
                'alicuotas_iva': AlicuotaIva.objects.filter(activo=True).order_by('orden', 'codigo'),
                'puntos_venta': PuntoVenta.objects.filter(sucursal_id=sucursal_id, activo=True),
            })

        if form.is_valid():
            try:
                tipo_30 = TipoComprobante.objects.filter(codigo__in=['030', '30']).first()
                if not tipo_30:
                    messages.error(request, "No se encontró el Tipo de Comprobante '030'.")
                    return redirect('compras_index')

                proveedor = form.cleaned_data.get('proveedor')
                punto = form.cleaned_data.get('punto')
                numero = form.cleaned_data.get('numero')

                if Compra.objects.filter(proveedor=proveedor, tipo=tipo_30, punto=punto, numero=numero, empresa_id=empresa_id).exists():
                    messages.error(request, f"Ya existe una factura registrada para el proveedor seleccionado con el comprobante {tipo_30.codigo}-{punto:04d}-{numero:08d}.")
                    empresa = Empresa.objects.filter(pk=empresa_id).first()
                    config_traz, _ = EmpresaTrazabilidad.objects.get_or_create(empresa_id=empresa_id, defaults={'empresa': empresa})
                    form.fields['proveedor'].queryset = ClienteProveedor.objects.filter(empresa_id=empresa_id).order_by('razon_social')
                    return render(request, 'armeria/compras_trazabilidad_carga.html', {
                        'form': form,
                        'empresa': empresa,
                        'config_trazabilidad': config_traz,
                        'alicuotas_iva': AlicuotaIva.objects.filter(activo=True).order_by('orden', 'codigo'),
                        'puntos_venta': PuntoVenta.objects.filter(sucursal_id=sucursal_id, activo=True),
                        'tipo_30': tipo_30,
                    })

                with transaction.atomic():
                    compra = form.save(commit=False)
                    compra.usuario = request.user
                    compra.empresa_id = empresa_id
                    compra.sucursal_id = sucursal_id
                    compra.tipo = tipo_30
                    compra.condic = 1
                    compra.periodo = compra.fecha.strftime('%Y-%m')
                    compra.ejercicio = Ejercicio.objects.filter(
                        empresa_id=empresa_id,
                        inicio__lte=compra.fecha,
                        cierre__gte=compra.fecha
                    ).first()
                    compra.moneda = request.POST.get('moneda', 'PES')
                    cotiz_val = request.POST.get('cotizacion', '1.0').replace('.', '').replace(',', '.')
                    try:
                        compra.cotizacion = Decimal(cotiz_val)
                    except (ValueError, TypeError, Decimal.InvalidOperation):
                        compra.cotizacion = Decimal('1.0')

                    compra.save()

                    for item in items_temp:
                        producto = get_object_or_404(Producto, id=item['producto_id'], empresa_id=empresa_id)
                        cantidad = Decimal('1.0')
                        precio_unitario = Decimal(str(item['precio']))
                        iva_alic = Decimal(str(item['iva']))
                        total_item = Decimal(str(item['total']))

                        # 1. Crear CompraItem (La señal post_save automáticamente aumenta StockSucursal +1 y recalcula totales)
                        comp_item = CompraItem(
                            compra=compra,
                            producto=producto,
                            cantidad=cantidad,
                            precio_unitario=precio_unitario,
                            iva_alicuota=iva_alic,
                            total=total_item
                        )
                        comp_item.save()

                        # 2. Crear Subproducto (Con la moneda y cotización idénticas a la factura)
                        Subproducto.objects.create(
                            empresa_id=empresa_id,
                            producto=producto,
                            sucursal_id=sucursal_id,
                            serie=item['serie'].upper(),
                            cuim=item.get('cuim', '').upper() if item.get('cuim') else None,
                            compra=compra,
                            feccpra=compra.fecha,
                            cto_adq=precio_unitario,
                            cotizadq=compra.cotizacion,
                            moneda=compra.moneda,
                            alic_iva=iva_alic,
                            margen=Decimal(str(producto.margen or 0)),
                            situacion=item.get('situacion', 'DEPOSITO'),
                            estado=item.get('estado', 'NUEVO')
                        )

                        # 3. Actualizar último costo y fecha de compra en el producto base
                        producto.cto_adq = precio_unitario
                        producto.fec_adq = compra.fecha
                        producto.compra_id = compra.compras_id
                        producto.cotiz_cpra = compra.cotizacion
                        producto.save(update_fields=['cto_adq', 'fec_adq', 'compra_id', 'cotiz_cpra'])

                    request.session['compra_trazabilidad_items_temp'] = []
                    messages.success(request, f"¡Factura de compra trazable {compra.numero} cargada con éxito! Subproductos y stock generados correctamente.")
                    return redirect('compras_index')

            except Exception as e:
                messages.error(request, f"Error al guardar la compra trazable: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Error de validación ({field}): {error}")

        empresa = Empresa.objects.filter(pk=empresa_id).first()
        config_traz, _ = EmpresaTrazabilidad.objects.get_or_create(empresa_id=empresa_id, defaults={'empresa': empresa})
        form.fields['proveedor'].queryset = ClienteProveedor.objects.filter(empresa_id=empresa_id).order_by('razon_social')
        tipo_30 = TipoComprobante.objects.filter(codigo__in=['030', '30']).first()
        return render(request, 'armeria/compras_trazabilidad_carga.html', {
            'form': form,
            'empresa': empresa,
            'config_trazabilidad': config_traz,
            'alicuotas_iva': AlicuotaIva.objects.filter(activo=True).order_by('orden', 'codigo'),
            'puntos_venta': PuntoVenta.objects.filter(sucursal_id=sucursal_id, activo=True),
            'tipo_30': tipo_30,
        })


@login_required
def compras_trazabilidad_item_add(request):
    if request.method != 'POST':
        return HttpResponse(status=405)

    empresa_id = request.session.get('empresa_id')
    config_traz = EmpresaTrazabilidad.objects.filter(empresa_id=empresa_id).first()

    producto_id = request.POST.get('producto_id')
    serie = (request.POST.get('serie') or '').strip().upper()
    situacion = 'DEPOSITO'
    estado = (request.POST.get('estado') or 'NUEVO').strip()
    cuim = (request.POST.get('cuim') or '').strip().upper()

    if not producto_id:
        return HttpResponse("Debe seleccionar un producto que sea trazable (Subproducto activo).", status=400)

    producto = get_object_or_404(Producto, pk=producto_id, empresa_id=empresa_id)
    if not producto.subprod:
        return HttpResponse("El producto seleccionado no tiene habilitada la opción de subproducto/trazabilidad.", status=400)

    try:
        total_ingresado = float((request.POST.get('precio') or '0').replace('.', '').replace(',', '.'))
        iva = float(producto.alic_iva or 0.0)
    except ValueError:
        return HttpResponse("Error en formato numérico de precio", status=400)

    if not serie:
        return HttpResponse("El Nro. de Serie / Identificador es obligatorio en toda carga de trazabilidad.", status=400)

    # Validaciones obligatorias dinámicas configuradas por la empresa
    if config_traz and config_traz.pedir_estado and not estado:
        return HttpResponse("Debe indicar el Estado físico (Nuevo / Usado) del subproducto.", status=400)
    if config_traz and config_traz.pedir_cuim and not cuim:
        return HttpResponse("Debe ingresar el CUIM / Patente / Dominio para este subproducto.", status=400)

    if cuim:
        import re
        if not re.fullmatch(r'^[A-Z0-9]{6}$', cuim):
            return HttpResponse("El CUIM debe tener exactamente 6 caracteres alfanuméricos, sin símbolos.", status=400)

    # Verificar que la serie no exista previamente en la empresa activa (no vendida)
    if Subproducto.objects.filter(serie__iexact=serie, empresa_id=empresa_id).exclude(situacion='VENDIDA').exists():
        return HttpResponse(f"El número de serie '{serie}' ya se encuentra activo en la empresa (no ha sido vendido).", status=400)

    items = request.session.get('compra_trazabilidad_items_temp', [])

    # Verificar duplicado en la grilla en sesión
    for it in items:
        if it['serie'] == serie:
            return HttpResponse(f"La serie '{serie}' ya fue agregada en esta grilla de compra.", status=400)

    precio_neto = round(total_ingresado / (1 + iva / 100.0), 2)
    total_item = total_ingresado

    nuevo_item = {
        'index': len(items),
        'producto_id': producto.id,
        'producto_detalle': producto.detalle.upper(),
        'serie': serie,
        'situacion': situacion,
        'estado': estado,
        'cuim': cuim,
        'precio': precio_neto,
        'iva': iva,
        'total': total_item,
    }

    items.append(nuevo_item)
    request.session['compra_trazabilidad_items_temp'] = items
    request.session.modified = True

    response = render(request, 'armeria/partials/compra_trazabilidad_items_tabla.html', {'items': items})
    response['HX-Trigger'] = 'limpiarInputsTrazabilidadCompra'
    return response


@login_required
def compras_trazabilidad_item_remove(request, index):
    items = request.session.get('compra_trazabilidad_items_temp', [])
    if 0 <= index < len(items):
        items.pop(index)
        for i, it in enumerate(items):
            it['index'] = i
    request.session['compra_trazabilidad_items_temp'] = items
    request.session.modified = True
    return render(request, 'armeria/partials/compra_trazabilidad_items_tabla.html', {'items': items})


# =========================================================================
# AUTO-RELLENADO EN BUSCADOR DE SERIE (VENTAS TRAZABILIDAD)
# =========================================================================

@login_required
def typeahead_series_trazabilidad(request):
    """
    Sugerencias interactivas de series disponibles en depósito para Venta Trazabilidad.
    """
    q = request.GET.get('serie_escaneada', '').strip().upper()
    empresa_id = request.session.get('empresa_id')
    sucursal_id = request.session.get('sucursal_id')

    if not q or not empresa_id:
        return HttpResponse('', status=200)

    todas = request.GET.get('todas') == '1'
    
    subproductos = Subproducto.objects.filter(empresa_id=empresa_id)
    if not todas:
        subproductos = subproductos.filter(situacion='DEPOSITO')

    subproductos = subproductos.filter(
        Q(serie__icontains=q) | Q(cuim__icontains=q) | Q(producto__detalle__icontains=q)
    ).select_related('producto').order_by('serie')[:10]

    return render(request, 'armeria/partials/serie_typeahead.html', {
        'subproductos': subproductos,
    })



# --- Desde productos/views_trazabilidad.py ---

from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from productos.models import Subproducto
from empresas.models import Empresa, Sucursal

class SubproductoTrazabilidadListView(LoginRequiredMixin, ListView):
    template_name = "armeria/trazabilidad_list.html"
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

        from django.db.models import Subquery, Q
        
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
        if search_sucursal:
            qs = qs.filter(sucursal_id=search_sucursal)

        # Filtramos para obtener SÓLO el estado más reciente de cada serie
        latest_ids = qs.order_by('serie', '-feccpra', '-subpro').distinct('serie').values('subpro')
        
        # Ahora trabajamos sobre un queryset limpio con solo los últimos estados
        qs = Subproducto.objects.filter(subpro__in=Subquery(latest_ids))

        # Aplicamos el filtro de situación AL ESTADO ACTUAL (antes fallaba porque filtraba toda la historia)
        if search_situacion:
            qs = qs.filter(situacion=search_situacion)

        # Ordenamiento dinámico
        sort = self.request.GET.get('sort', '-fecha')
        sort_map = {
            'producto': 'producto__detalle',
            '-producto': '-producto__detalle',
            'serie': 'serie',
            '-serie': '-serie',
            'cuim': 'cuim',
            '-cuim': '-cuim',
            'sucursal': 'sucursal__nombre',
            '-sucursal': '-sucursal__nombre',
            'situacion': 'situacion',
            '-situacion': '-situacion',
            'fecha': 'feccpra',
            '-fecha': '-feccpra',
        }
        
        qs = qs.select_related('producto', 'compra', 'compra__proveedor', 'venta', 'venta__cliente')
        qs = qs.order_by(sort_map.get(sort, '-feccpra'))
        
        # Limitamos a 50 registros para optimizar carga
        return qs[:50]

    def get_template_names(self):
        if self.request.headers.get('HX-Request') or self.request.META.get('HTTP_HX_REQUEST'):
            return ["armeria/partials/trazabilidad_grilla.html"]
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

    return render(request, 'armeria/partials/trazabilidad_modal_timeline.html', {
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

    return render(request, 'armeria/partials/subproducto_detalle_modal.html', {
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
            return render(request, 'armeria/partials/subproducto_editar_modal.html', {
                'subproducto': subproducto,
                'error': "El número de SERIE es obligatorio."
            })

        if nuevo_cuim:
            import re
            if not re.fullmatch(r'^[A-Z0-9]{6}$', nuevo_cuim):
                return render(request, 'armeria/partials/subproducto_editar_modal.html', {
                    'subproducto': subproducto,
                    'error': "El CUIM debe tener exactamente 6 caracteres alfanuméricos, sin símbolos."
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

    return render(request, 'armeria/partials/subproducto_editar_modal.html', {
        'subproducto': subproducto
    })

# ==============================================================================
# GESTIÓN DE RESERVAS DE ARMAS (SIGIMAC)
# ==============================================================================

@login_required
def verificar_reserva_cliente(request):
    """
    Consulta si el cliente seleccionado posee reservas activas de armas (SIGIMAC).
    Devuelve un snippet HTML con la alerta y checkbox para aplicar la reserva a la venta actual.
    """
    cliente_id = request.GET.get('cliente_id')
    empresa_id = request.session.get('empresa_id')
    if not cliente_id or not empresa_id:
        return HttpResponse("")
    
    from verticalidades.armeria.models import ReservaArma
    reservas = ReservaArma.objects.filter(
        cliente_id=cliente_id,
        empresa_id=empresa_id,
        estado='PENDIENTE'
    ).select_related('producto', 'recibo_reserva')
    
    if not reservas.exists():
        return HttpResponse("")
        
    return render(request, 'armeria/partials/reserva_cliente_alerta.html', {'reservas': reservas})

class ReservaArmaListView(LoginRequiredMixin, ListView):
    """
    Listado y panel de control de Reservas de Armas sujetas a trámite SIGIMAC.
    Permite auditar el estado de los trámites (Pendientes, Aplicadas, Devueltas).
    Soporta búsqueda multi-criterio y refrescos reactivos HTMX.
    """
    template_name = 'armeria/reservas_list.html'
    context_object_name = 'reservas'

    def get_template_names(self):
        if self.request.headers.get('HX-Request') or self.request.META.get('HTTP_HX_REQUEST'):
            return ["armeria/partials/reservas_tabla_parcial.html"]
        return super().get_template_names()

    def get_queryset(self):
        empresa_id = self.request.session.get('empresa_id')
        from verticalidades.armeria.models import ReservaArma
        qs = ReservaArma.objects.filter(empresa_id=empresa_id).select_related(
            'cliente', 'producto', 'recibo_reserva', 'venta_aplicada', 'venta_aplicada__tipo', 'orden_pago_devolucion', 'sucursal', 'preventa'
        )

        estado = self.request.GET.get('estado')
        if estado and estado != 'TODAS':
            qs = qs.filter(estado=estado)

        q = self.request.GET.get('q', '').strip()
        if q:
            terms = q.split()
            for term in terms:
                term_clean = term.strip()
                if not term_clean:
                    continue
                term_q = (
                    # Búsqueda por Cliente (completo)
                    Q(cliente__razon_social__icontains=term_clean) |
                    Q(cliente__cuit__icontains=term_clean) |
                    Q(cliente__telefono__icontains=term_clean) |
                    Q(cliente__correo__icontains=term_clean) |
                    Q(cliente__domicilio__icontains=term_clean) |
                    Q(cliente__contacto__icontains=term_clean) |
                    # Búsqueda por Producto y Subproducto (serie, CUIM, códigos)
                    Q(producto__detalle__icontains=term_clean) |
                    Q(producto__cod_prov__icontains=term_clean) |
                    Q(producto__cod_fab__icontains=term_clean) |
                    Q(producto__subproductos__serie__icontains=term_clean) |
                    Q(producto__subproductos__cuim__icontains=term_clean) |
                    # Búsqueda por Recibo y Observaciones
                    Q(recibo_reserva__numero__icontains=term_clean) |
                    Q(recibo_reserva__observaciones__icontains=term_clean) |
                    Q(observaciones__icontains=term_clean)
                )

                num_part = term_clean.lstrip('#')
                if num_part.isdigit():
                    num_val = int(num_part)
                    term_q |= Q(id=num_val) | Q(preventa__preventa_id=num_val) | Q(recibo_reserva__numero=num_val)

                qs = qs.filter(term_q)

            qs = qs.distinct()

        f_desde = self.request.GET.get('desde')
        f_hasta = self.request.GET.get('hasta')
        if f_desde:
            qs = qs.filter(fecha_reserva__gte=f_desde)
        if f_hasta:
            qs = qs.filter(fecha_reserva__lte=f_hasta)

        return qs.order_by('-fecha_reserva', '-id')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        empresa_id = self.request.session.get('empresa_id')
        from verticalidades.armeria.models import ReservaArma
        from django.db.models import Sum, Count

        resumen = ReservaArma.objects.filter(empresa_id=empresa_id).aggregate(
            pendientes_count=Count('id', filter=Q(estado='PENDIENTE')),
            pendientes_monto=Sum('monto_reservado', filter=Q(estado='PENDIENTE')),
            aplicadas_count=Count('id', filter=Q(estado='APLICADA')),
            devueltas_count=Count('id', filter=Q(estado='DEVUELTA'))
        )
        ctx['resumen'] = resumen
        ctx['estado_actual'] = self.request.GET.get('estado', 'PENDIENTE')
        ctx['q'] = self.request.GET.get('q', '')
        ctx['desde'] = self.request.GET.get('desde', '')
        ctx['hasta'] = self.request.GET.get('hasta', '')
        return ctx

@login_required
def reserva_arma_anular_modal(request, reserva_id):
    """
    Despliega el modal de confirmación de anulación y devolución de una Reserva SIGIMAC.
    Permite seleccionar el medio de pago con el que se restituyen los fondos al cliente.
    """
    empresa_id = request.session.get('empresa_id')
    from verticalidades.armeria.models import ReservaArma
    from tesoreria.models import CuentaBancaria
    reserva = get_object_or_404(ReservaArma, id=reserva_id, empresa_id=empresa_id)

    cuentas_bancarias = CuentaBancaria.objects.filter(empresa_id=empresa_id)

    return render(request, 'armeria/modals/reserva_anular_modal.html', {
        'reserva': reserva,
        'cuentas_bancarias': cuentas_bancarias
    })

@login_required
@transaction.atomic
def reserva_arma_anular_procesar(request, reserva_id):
    """
    Procesa la anulación de la Reserva de Arma (por denegación de SIGIMAC o cancelación).
    Genera automáticamente una Orden de Pago a favor del cliente para devolver los fondos señados
    y netear contablemente el Recibo de Reserva en la cuenta corriente.
    """
    if request.method != 'POST':
        return HttpResponse("Método no permitido", status=405)

    empresa_id = request.session.get('empresa_id')
    sucursal_id = request.session.get('sucursal_id')
    from verticalidades.armeria.models import ReservaArma
    from tesoreria.models import (
        OrdenPago, OrdenPagoImputacion, Caja, CajaSesion, MovimientoCaja,
        TransaccionBancaria, CuentaBancaria
    )
    from contable.models import ParametrosContables, Cuenta
    from empresas.models import Ejercicio

    reserva = get_object_or_404(ReservaArma.objects.select_for_update(), id=reserva_id, empresa_id=empresa_id)

    if reserva.estado != 'PENDIENTE':
        return HttpResponse(json.dumps({'status': 'error', 'message': 'Solo se pueden anular reservas en estado Pendiente.'}), status=400, content_type="application/json")

    medio_devolucion = request.POST.get('medio_devolucion', 'EFECTIVO') # EFECTIVO / TRANSFERENCIA
    cuenta_bancaria_id = request.POST.get('cuenta_bancaria_id')
    motivo = request.POST.get('motivo', 'Trámite SIGIMAC denegado / Cancelación').strip()

    ejercicio = Ejercicio.objects.filter(
        empresa_id=empresa_id,
        inicio__lte=timezone.localdate(),
        cierre__gte=timezone.localdate()
    ).first()

    # Obtener caja activa para la devolución
    caja = Caja.objects.filter(empresa_id=empresa_id, sucursal_id=sucursal_id, tipo='M', activa=True).first()
    sesion_caja = CajaSesion.objects.filter(caja=caja, usuario=request.user, estado='A').first()

    # 1. Crear Orden de Pago para el cliente
    last_op = OrdenPago.objects.filter(empresa_id=empresa_id, sucursal_id=sucursal_id).order_by('-numero').first()
    nro_op = (last_op.numero + 1) if (last_op and last_op.numero) else 1

    op = OrdenPago.objects.create(
        empresa_id=empresa_id,
        sucursal_id=sucursal_id,
        ejercicio=ejercicio,
        sesion_caja=sesion_caja,
        tipo='S',
        proveedor=reserva.cliente, # ClienteProveedor
        fecha=timezone.localdate(),
        punto=1,
        numero=nro_op,
        total=reserva.monto_reservado,
        observaciones=f"Devolución Reserva SIGIMAC #{reserva.id} (Prev #{reserva.preventa.preventa_id}) - {motivo}",
        condic=1
    )

    # 2. Imputación contable contra la cuenta deudores / cta corriente del cliente
    param_c = ParametrosContables.objects.filter(empresa_id=empresa_id).first()
    cta_imputar = None
    if reserva.cliente.cta_pat:
        cta_imputar = Cuenta.objects.filter(empresa_id=empresa_id, codigo=reserva.cliente.cta_pat).first()
    if not cta_imputar and param_c:
        cta_imputar = param_c.cta_clientes_default

    if cta_imputar:
        OrdenPagoImputacion.objects.create(
            orden_pago=op,
            cuenta_contable=cta_imputar,
            importe=reserva.monto_reservado,
            leyenda=f"Devolución Reserva SIGIMAC #{reserva.id}"
        )

    # 3. Registrar egreso de fondos
    concepto_egreso = f"Devolución Reserva SIGIMAC #{reserva.id} OP #{op.numero}"
    if medio_devolucion == 'EFECTIVO' and sesion_caja:
        mov = MovimientoCaja.objects.create(
            sesion=sesion_caja,
            empresa_id=empresa_id,
            fecha=op.fecha,
            tipo='E',
            importe=reserva.monto_reservado,
            concepto=concepto_egreso,
            condic=1,
            cli_pro=reserva.cliente,
            orden_pago=op
        )
    elif medio_devolucion == 'TRANSFERENCIA' and cuenta_bancaria_id:
        cta_bc = CuentaBancaria.objects.filter(cta_bc_id=cuenta_bancaria_id, empresa_id=empresa_id).first()
        if cta_bc:
            TransaccionBancaria.objects.create(
                empresa_id=empresa_id,
                cuenta_bancaria=cta_bc,
                tipo_transaccion='TE',
                importe=reserva.monto_reservado,
                fecha_operacion=op.fecha,
                numero_operacion=f"OP-{op.numero}"
            )

    # 4. Actualizar estado de ReservaArma y Preventa
    reserva.estado = 'DEVUELTA'
    reserva.orden_pago_devolucion = op
    reserva.fecha_resolucion = timezone.localdate()
    reserva.observaciones = f"{reserva.observaciones or ''}\nAnulada: {motivo}".strip()
    reserva.save()

    reserva.preventa.estado = 4 # Anulada
    reserva.preventa.save(update_fields=['estado'])

    messages.success(request, f"Reserva #{reserva.id} anulada con éxito. Se emitió la Orden de Pago #{op.numero} por $ {reserva.monto_reservado:,.2f}.")
    return redirect('armeria_reservas_list')


