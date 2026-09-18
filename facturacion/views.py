from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Max
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.views.generic import TemplateView
from django.urls import reverse
from decimal import Decimal

from .models import ClienteProveedor, Compra, CompraItem, CompraAlicuota, CompraRetPerc, Venta, VentaItem, Preventa, PreventaItem, TipoComprobante, VentaAlicuotaIva
from .forms import CompraForm, ClienteProveedorForm, VentaForm, PreventaForm
from empresas.models import Ejercicio
from productos.models import Producto, StockSucursal, MovimientoStock, ALICUOTAS_ARCA_MAP
from empresas.models import Empresa, Sucursal
from contable.models import Cuenta, AlicuotaIva
from .services.afip_service import AFIPService
from impuestos.services import obtener_primer_periodo_vigente_compra, es_periodo_cerrado

import json

def mapear_condicion_iva_receptor(condicion_str):
    cond = str(condicion_str or '').upper().strip()
    if 'RESPONSABLE INSCRIPTO' in cond or cond == 'RI' or cond == '1':
        return 1
    if 'MONOTRIBUTO' in cond or 'MONOTRIBUTISTA' in cond or cond == '6' or 'MONO' in cond:
        return 6
    if 'EXENTO' in cond or cond == '4':
        return 4
    if 'CONSUMIDOR FINAL' in cond or cond == 'CF' or cond == '5':
        return 5
    if 'NO RESPONSABLE' in cond or cond == '3':
        return 3
    if 'NO CATEGORIZADO' in cond or cond == '7':
        return 7
    if 'PROVEEDOR DEL EXTERIOR' in cond or cond == '8':
        return 8
    if 'CLIENTE DEL EXTERIOR' in cond or cond == '9':
        return 9
    return 5  # Por defecto Consumidor Final

def resolver_tipo_comprobante_fiscal(condicion_iva_str, tipo_operacion='FACTURA'):
    """
    Determina el TipoComprobante para una venta fiscal emitida por un Responsable Inscripto:
    - Receptor RI (1) o Monotributo (6) -> Factura A ('001'), NC A ('003'), ND A ('002')
    - Receptor Consumidor Final (5), Exento (4) y demás -> Factura B ('006'), NC B ('008'), ND B ('007')
    """
    cond_id = mapear_condicion_iva_receptor(condicion_iva_str)
    
    if tipo_operacion == 'NC':
        cod_num = 3 if cond_id in [1, 6] else 8
    elif tipo_operacion == 'ND':
        cod_num = 2 if cond_id in [1, 6] else 7
    else:  # FACTURA
        cod_num = 1 if cond_id in [1, 6] else 6
        
    codigos_posibles = [str(cod_num), f"{cod_num:03d}"]
    tipo_cbte = TipoComprobante.objects.filter(codigo__in=codigos_posibles).first()
    return tipo_cbte

def validar_y_obtener_documento_receptor(cliente):
    """
    Valida y obtiene la tupla (doc_tipo, doc_nro, condicion_iva_receptor_id) para ARCA/AFIP:
    - RI, Monotributo, Exento: Requieren obligatoriamente CUIT de 11 dígitos y DocTipo 80.
    - Consumidor Final:
      * Con CUIT (11 dígitos): DocTipo 80
      * Con DNI (7 u 8 dígitos): DocTipo 96
      * Sin identificar o vacío: DocTipo 99, DocNro 0
    """
    if not cliente:
        return 99, 0, 5

    cond_iva_rec = mapear_condicion_iva_receptor(cliente.condicion_iva)
    cuit_raw = str(cliente.cuit or '').replace('-', '').strip()
    tipo_doc_raw = str(cliente.tipo_documento or '').strip()

    # 1. Reglas estrictas para Entidades Fiscales (RI, Monotributo, Exento)
    if cond_iva_rec in [1, 6, 4]:
        if not cuit_raw.isdigit() or len(cuit_raw) != 11:
            cond_nombre = "Responsable Inscripto" if cond_iva_rec == 1 else ("Monotributista" if cond_iva_rec == 6 else "Exento")
            raise ValidationError(
                f"El cliente '{cliente.razon_social}' es {cond_nombre} y requiere obligatoriamente CUIT de 11 dígitos con Tipo Doc 80."
            )
        return 80, int(cuit_raw), cond_iva_rec

    # 2. Consumidor Final / Otros
    if not cuit_raw or cuit_raw in ['0', '00'] or tipo_doc_raw == '99':
        return 99, 0, cond_iva_rec
    elif tipo_doc_raw == '96' or (len(cuit_raw) in [7, 8] and cuit_raw.isdigit()):
        return 96, int(cuit_raw), cond_iva_rec
    elif len(cuit_raw) == 11 and cuit_raw.isdigit():
        return 80, int(cuit_raw), cond_iva_rec
    
    return 99, 0, cond_iva_rec

def agrupar_alicuotas_iva_items(items_temp):
    from decimal import Decimal
    alicuotas_dict = {}
    for item in items_temp:
        alic_val = Decimal(str(item['iva']).replace(',', '.'))
        alicuota_factor = Decimal("1.00") + (alic_val / Decimal("100.00"))
        item_total = Decimal(str(item['total']).replace(',', '.'))
        neto_item = (item_total / alicuota_factor).quantize(Decimal("0.01"))
        iva_item = item_total - neto_item
        
        id_iva = 3  # Por defecto 0% exento
        for k, v in ALICUOTAS_ARCA_MAP.items():
            if abs(k - alic_val) < Decimal("0.05"):
                id_iva = v
                break
                
        if id_iva not in alicuotas_dict:
            alicuotas_dict[id_iva] = {
                'id_iva': id_iva,
                'alicuota': alic_val,
                'base_imponible': Decimal("0.00"),
                'importe_iva': Decimal("0.00")
            }
        alicuotas_dict[id_iva]['base_imponible'] += neto_item
        alicuotas_dict[id_iva]['importe_iva'] += iva_item
        
    return list(alicuotas_dict.values())

class VentasCargaView(LoginRequiredMixin, View):
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')
        
        if not empresa_id or not sucursal_id:
            messages.warning(request, "Por favor, seleccione una empresa y sucursal primero.")
            return redirect('seleccion_empresa')

        # Limpiar Ã­items temporales al iniciar carga nueva
        request.session['venta_items_temp'] = []

        initial_data = {
            'empresa': empresa_id,
            'sucursal': sucursal_id,
            'fecha': timezone.localdate()
        }
        form = VentaForm(initial=initial_data)
        from empresas.models import PuntoVenta, Empresa as _Empresa
        puntos_venta = PuntoVenta.objects.filter(sucursal_id=sucursal_id, activo=True)
        empresa_activa = _Empresa.objects.filter(pk=empresa_id).first()
        modo_edicion = getattr(empresa_activa, 'modo_edicion_facturacion', 'DESCUENTO')
        return render(request, 'facturacion/ventas_carga.html', {
            'form': form,
            'puntos_venta': puntos_venta,
            'modo_edicion': modo_edicion
        })

    def post(self, request):
        data = request.POST.copy()
        # Limpieza de datos (Formato AR -> Float)
        campos_monetarios = ['neto', 'iva', 'p_iibb', 'p_iva', 'otros', 'total', 'cotizacion', 'efectivo', 'tarjeta', 'transferencia', 'valores']
        
        for campo in campos_monetarios:
            val = data.get(campo, '').strip()
            if val:
                data[campo] = val.replace('.', '').replace(',', '.')
            else:
                data[campo] = '0'

        form = VentaForm(data)
        items_temp = request.session.get('venta_items_temp', [])

        if not items_temp:
            messages.error(request, "Debe cargar al menos un producto en la grilla.")
            return render(request, 'facturacion/ventas_carga.html', {'form': form})

        if form.is_valid():
            try:
                venta = form.save(commit=False)
                venta.empresa_id = request.session.get('empresa_id')
                venta.sucursal_id = request.session.get('sucursal_id')
                # Forzar punto de venta exactamente de la lista desplegable seleccionada
                if data.get('punto'):
                    venta.punto = int(data.get('punto'))
                if data.get('punto'):
                    venta.punto = int(data.get('punto'))
                if venta.moneda == 'PES':
                    venta.cotizacion = Decimal('1.0000')
                
                # Lógica de Condición (Fiscal o No Fiscal)
                if venta.tipo and venta.tipo.codigo == 'PRE':
                    venta.condic = 2
                else:
                    venta.condic = 1

                # Agrupar alícuotas
                alicuotas_list = agrupar_alicuotas_iva_items(items_temp)

                # Autorización externa ante ARCA si es Fiscal (condic == 1) y tiene código numérico (ej. 1, 6, 11)
                if venta.condic == 1 and venta.tipo and str(venta.tipo.codigo).isdigit():
                    empresa_obj = get_object_or_404(Empresa, id=venta.empresa_id)
                    try:
                        doc_tipo, doc_nro, cond_iva_rec = validar_y_obtener_documento_receptor(venta.cliente)
                        cbte_tipo_num = int(venta.tipo.codigo)

                        # Validación de coherencia fiscal previa a ARCA
                        if cbte_tipo_num == 1 and cond_iva_rec not in [1, 6]:
                            messages.error(request, "Inconsistencia fiscal: No se puede emitir Factura A a un Consumidor Final o Exento. Debe emitir Factura B.")
                            return render(request, 'facturacion/ventas_carga.html', {'form': form})
                        
                        if cbte_tipo_num == 6 and cond_iva_rec in [1, 6]:
                            messages.error(request, "Inconsistencia fiscal: A Responsables Inscriptos y Monotributistas corresponde emitirles Factura A.")
                            return render(request, 'facturacion/ventas_carga.html', {'form': form})

                        tot_neto_alic = sum((a['base_imponible'] for a in alicuotas_list), Decimal('0.00'))
                        tot_iva_alic = sum((a['importe_iva'] for a in alicuotas_list), Decimal('0.00'))

                        datos_afip = {
                            'pto_vta': venta.punto,
                            'cbte_tipo': cbte_tipo_num,
                            'concepto': 1,
                            'doc_tipo': doc_tipo,
                            'doc_nro': doc_nro,
                            'cbte_fch': venta.fecha.strftime('%Y%m%d'),
                            'imp_total': float(tot_neto_alic + tot_iva_alic),
                            'imp_tot_conc': 0.0,
                            'imp_neto': float(tot_neto_alic),
                            'imp_op_ex': 0.0,
                            'imp_iva': float(tot_iva_alic),
                            'condicion_iva_receptor_id': cond_iva_rec,
                            'mon_id': 'DOL' if venta.moneda == 'DOL' else 'PES',
                            'mon_cotiz': float(venta.cotizacion) if venta.moneda == 'DOL' else 1.0,
                        }

                        afip_service = AFIPService(empresa_obj)
                        res_afip = afip_service.emitir_comprobante(datos_afip, alicuotas_list)

                        if not res_afip['exito']:
                            messages.error(request, f"Rechazo ARCA: {res_afip['error']}")
                            return render(request, 'facturacion/ventas_carga.html', {'form': form})

                        venta.cae = res_afip['cae']
                        venta.vto_cae = res_afip['vto_cae']
                        venta.numero = res_afip['numero_comprobante']
                        venta.cod_qr = res_afip['cod_qr']

                    except ValidationError as e:
                        messages.error(request, f"Validación de Receptor: {e.message if hasattr(e, 'message') else str(e)}")
                        return render(request, 'facturacion/ventas_carga.html', {'form': form})
                    except (ValueError, FileNotFoundError) as e:
                        messages.error(request, f"Configuración ARCA incompleta: {str(e)}")
                        return render(request, 'facturacion/ventas_carga.html', {'form': form})

                with transaction.atomic():
                    if not venta.numero:
                        ultimo = Venta.objects.filter(
                            empresa_id=request.session.get('empresa_id'),
                            tipo=venta.tipo,
                            punto=venta.punto
                        ).aggregate(Max('numero'))['numero__max']
                        venta.numero = (ultimo or 0) + 1
                        
                    periodo_vta = venta.fecha.strftime('%Y%m')
                    if es_periodo_cerrado(venta.empresa_id, periodo_vta):
                        messages.error(request, f"Error: El período IVA ({periodo_vta}) se encuentra cerrado por liquidación fiscal. No es posible emitir ventas en un período cerrado.")
                        return render(request, 'facturacion/ventas_carga.html', ctx_base)
                    
                    venta.usuario = request.user
                    venta.periodo = periodo_vta
                    venta.ejercicio = Ejercicio.objects.filter(
                        empresa_id=venta.empresa_id,
                        inicio__lte=venta.fecha,
                        cierre__gte=venta.fecha
                    ).first()
                    
                    requiere_autorizacion = any(item.get('requiere_autorizacion', False) for item in items_temp)
                    venta.estado = 2 if requiere_autorizacion else 0
                    
                    venta.cobrado = 0
                    venta.saldo = venta.total
                    venta.efectivo = 0
                    venta.tarjeta = 0
                    venta.transferencia = 0
                    venta.valores = 0
                    
                    venta.save()

                    for item in items_temp:
                        producto = get_object_or_404(Producto, id=item['producto_id'], empresa_id=request.session.get('empresa_id'))
                        cantidad = float(item['cantidad'])
                        
                        VentaItem.objects.create(
                            venta=venta,
                            producto=producto,
                            cantidad=cantidad,
                            precio_unitario=item['precio'],
                            porcentaje_descuento=item.get('descuento', 0),
                            iva_alicuota=item['iva'],
                            total=item['total'],
                            credencial=item.get('credencial', ''),
                            dmp=item.get('dmp', 0),
                            moneda_origen=item.get('moneda_origen', 'PES'),
                            cotizacion_aplicada=item.get('cotizacion_aplicada', 1.0),
                            precio_origen=item.get('precio_origen', item['precio'])
                        )

                    for a in alicuotas_list:
                        VentaAlicuotaIva.objects.create(
                            venta=venta,
                            id_iva=a['id_iva'],
                            alicuota=a['alicuota'],
                            base_imponible=a['base_imponible'],
                            importe_iva=a['importe_iva']
                        )

                    request.session['venta_items_temp'] = []
                    if venta.condic != 2:
                        request.session['auto_print_url'] = reverse('imprimir_factura', kwargs={'venta_id': venta.ventas_id})
                    messages.success(request, f"¡Venta {venta.numero} registrada con éxito! Stock actualizado.")
                    return redirect('ventas_carga')

            except Exception as e:
                messages.error(request, f"Error crÃ­tico al guardar la venta: {str(e)}")
        
        if not form.is_valid():
            messages.error(request, f"Error en los datos del comprobante: {form.errors.as_text()}")
        
        return render(request, 'facturacion/ventas_carga.html', {'form': form})

    
class PreventaCargaView(LoginRequiredMixin, View):
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')
        
        if not empresa_id or not sucursal_id:
            messages.warning(request, "Por favor, seleccione una empresa y sucursal primero.")
            return redirect('seleccion_empresa')

        # Limpiar Ã­items temporales al iniciar carga nueva
        request.session['preventa_items_temp'] = []

        # Obtener cliente predeterminado (ID 1 / Consumidor Final)
        cliente_default = ClienteProveedor.objects.filter(empresa_id=empresa_id, codigo_id=1).first()
        if not cliente_default:
            cliente_default = ClienteProveedor.objects.filter(empresa_id=empresa_id, tipo_documento='99').order_by('codigo_id').first()

        initial_data = {
            'vendedor': request.user.id,
            'cliente': cliente_default.codigo_id if cliente_default else 1
        }
        form = PreventaForm(initial=initial_data)
        
        # Filtrar clientes por empresa
        form.fields['cliente'].queryset = ClienteProveedor.objects.filter(empresa_id=empresa_id, tipo_entidad=1).order_by('razon_social')
        
        es_distribuidora = Empresa.objects.filter(
            id=empresa_id, tipo_actividad="DISTRIBUIDORA").exists()

        # El vendedor sólo ve su cartera; un administrativo sin `Personal` asociado ve
        # todos los clientes, porque es quien toma los pedidos telefónicos (Plan 074).
        if es_distribuidora:
            from verticalidades.distribucion.services.pedidos import clientes_de_la_cartera
            cartera = clientes_de_la_cartera(request.user, empresa_id)
            if cartera is not None:
                form.fields['cliente'].queryset = form.fields['cliente'].queryset.filter(
                    codigo_id__in=cartera)

        empresa_activa = Empresa.objects.filter(pk=empresa_id).first()
        modo_edicion = getattr(empresa_activa, 'modo_edicion_facturacion', 'DESCUENTO')

        context = {
            'form': form,
            'cliente_default': cliente_default,
            'is_armeria': Empresa.objects.filter(id=empresa_id, tipo_actividad="ARMERIA").exists(),
            'is_distribuidora': es_distribuidora,
            'modo_edicion': modo_edicion,
        }
        return render(request, 'facturacion/preventa_carga.html', context)

    def post(self, request):
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')
        
        items_temp = request.session.get('preventa_items_temp', [])
        if not items_temp:
            messages.error(request, "Debe cargar al menos un producto en la grilla.")
            return redirect('preventas_carga')

        post_data = request.POST.copy()
        cliente_id_raw = post_data.get('cliente')
        if not cliente_id_raw or str(cliente_id_raw).strip() in ('', 'None'):
            # Si el usuario editó el nombre de Consumidor Final sin seleccionar un cliente específico,
            # se asigna automáticamente el cliente genérico (ID 1 / Doc 99)
            cliente_default = ClienteProveedor.objects.filter(empresa_id=empresa_id, codigo_id=1).first()
            if not cliente_default:
                cliente_default = ClienteProveedor.objects.filter(empresa_id=empresa_id, tipo_documento='99').order_by('codigo_id').first()
            if cliente_default:
                post_data['cliente'] = str(cliente_default.codigo_id)

        form = PreventaForm(post_data)
        if form.is_valid():
            try:
                # Validación de exclusividad para productos trazables (SIGIMAC / subprod=True)
                tiene_subprod = False
                for item_t in items_temp:
                    p_obj = Producto.objects.filter(id=item_t['producto_id']).first()
                    if p_obj and p_obj.subprod:
                        tiene_subprod = True
                        break
                
                if tiene_subprod:
                    if len(items_temp) > 1:
                        messages.error(request, "Las armas/artículos trazables (SIGIMAC) deben reservarse en una preventa individual exclusiva.")
                        return redirect('preventas_carga')
                    if float(items_temp[0].get('cantidad', 1)) != 1.0:
                        messages.error(request, "La cantidad de reserva para un arma trazable debe ser exactamente 1 unidad.")
                        return redirect('preventas_carga')

                # Validación Armería: no permitir productos con creden=True para clientes sin identificar (tipo_doc='99' / Consumidor Final)
                es_armeria = Empresa.objects.filter(id=empresa_id, tipo_actividad__iexact="ARMERIA").exists()
                if es_armeria:
                    cliente_sel = form.cleaned_data.get('cliente')
                    
                    tiene_municion = False
                    
                    if cliente_sel and (cliente_sel.tipo_documento == '99' or cliente_sel.codigo_id == 1):
                        tiene_creden = False
                        for item_t in items_temp:
                            p_obj = Producto.objects.filter(id=item_t['producto_id']).first()
                            if p_obj and p_obj.creden:
                                tiene_creden = True
                            if p_obj and (
                                (p_obj.rubro and 'MUNICION' in p_obj.rubro.detalle.upper()) or 
                                (p_obj.familia and 'MUNICION' in p_obj.familia.detalle.upper()) or 
                                'MUNICION' in p_obj.detalle.upper()
                            ):
                                tiene_municion = True
                                
                        if tiene_creden:
                            messages.error(request, "Debe identificar al cliente que compra este tipo de producto. Para poder avanzar debe seleccionar al cliente real.")
                            return redirect('preventas_carga')
                    else:
                        for item_t in items_temp:
                            p_obj = Producto.objects.filter(id=item_t['producto_id']).first()
                            if p_obj and (
                                (p_obj.rubro and 'MUNICION' in p_obj.rubro.detalle.upper()) or 
                                (p_obj.familia and 'MUNICION' in p_obj.familia.detalle.upper()) or 
                                'MUNICION' in p_obj.detalle.upper()
                            ):
                                tiene_municion = True
                                break

                    if tiene_municion and cliente_sel:
                        from facturacion.helpers import validar_clu_cliente_armeria
                        es_valido, msj_err = validar_clu_cliente_armeria(cliente_sel, empresa_id)
                        if not es_valido:
                            messages.error(request, f"Error (Munición): {msj_err}")
                            return redirect('preventas_carga')

                # Nota: En Preventas no opera la restricción de CLU vigente ya que aquí
                # no se factura ni entrega el arma, sólo se genera la preventa/reserva (la traba
                # opera de forma estricta en Ventas con Trazabilidad al facturar). Sin embargo,
                # para Munición sí se bloquea desde la preventa según las reglas de Armería.

                with transaction.atomic():
                    preventa = form.save(commit=False)
                    preventa.empresa_id = empresa_id
                    preventa.sucursal_id = sucursal_id
                    
                    # Snapshot del cliente o Consumidor Final ocasional
                    if preventa.cliente.tipo_entidad == 1 and preventa.cliente.cuit in [None, '', '0', '00'] and (preventa.cliente.codigo_id == 1 or preventa.cliente.tipo_documento == '99'):
                        # Si es consumidor final genérico (asumiendo ID 1 o Doc 99), usamos el nombre ocasional ingresado
                        ocasional = (request.POST.get('q') or request.POST.get('cliente_nombre_display') or request.POST.get('cliente_ocasional') or '').strip()
                        preventa.cliente_razon_social = ocasional.upper() if ocasional else "CONSUMIDOR FINAL"
                    else:
                        preventa.cliente_razon_social = preventa.cliente.razon_social
                        preventa.cliente_cuit = preventa.cliente.cuit
                        preventa.cliente_domicilio = preventa.cliente.domicilio
                    
                    # Requiere autorización?
                    requiere_autorizacion = any(item.get('requiere_autorizacion', False) for item in items_temp)
                    preventa.estado = 1 if requiere_autorizacion else 2 # 1=Pendiente, 2=Autorizada
                    
                    # Notas SIGIMAC
                    notas_sigimac = request.POST.get('notas_sigimac', '').strip()
                    if notas_sigimac:
                        preventa.notas_sigimac = notas_sigimac
                        
                    preventa.save()
                    
                    for item in items_temp:
                        producto = get_object_or_404(Producto, id=item['producto_id'], empresa_id=request.session.get('empresa_id'))
                        PreventaItem.objects.create(
                            preventa=preventa,
                            producto=producto,
                            cantidad=item['cantidad'],
                            precio_unitario=item['precio_unitario'],
                            porcentaje_descuento=item['descuento'],
                            total=item['total'],
                            moneda_origen=item.get('moneda_origen', 'PES'),
                            cotizacion_aplicada=item.get('cotizacion_aplicada', 1.0),
                            precio_origen=item.get('precio_origen', item['precio_unitario']),
                            credencial=item.get('credencial', ''),
                            dmp=item.get('dmp', 0)
                        )

                    
                    preventa.recalcular_totales()

                    # --- Distribución (Plan 074): el pedido es un documento EMITIDO y
                    # lleva su número correlativo propio, que es el eslabón entre el
                    # pedido del cliente, su comprobante y la devolución.
                    pedido_dist = None
                    if Empresa.objects.filter(id=empresa_id, tipo_actividad='DISTRIBUIDORA').exists():
                        from verticalidades.distribucion.services.pedidos import registrar_pedido
                        pedido_dist = registrar_pedido(
                            preventa,
                            usuario=request.user,
                            condic_destino=int(request.POST.get('condic_destino') or 1),
                            fecha_entrega=request.POST.get('fecha_entrega') or None,
                            observaciones=request.POST.get('observaciones_pedido') or None,
                        )

                    request.session['preventa_items_temp'] = []

                    if pedido_dist:
                        if requiere_autorizacion:
                            messages.warning(request, f"Pedido N° {pedido_dist.numero_formateado} guardado, PENDIENTE DE AUTORIZACIÓN por exceder límite de descuentos.")
                        else:
                            messages.success(request, f"¡Pedido N° {pedido_dist.numero_formateado} registrado con éxito!")
                        if pedido_dist.alerta_credito:
                            messages.warning(request, "El cliente queda EXCEDIDO en su límite de crédito con este pedido.")
                        if pedido_dist.alerta_stock:
                            messages.warning(request, "Hay ítems sin stock suficiente: el pedido queda sujeto a disponibilidad.")
                        return redirect('preventas_carga')

                    if requiere_autorizacion:
                        messages.warning(request, f"Preventa NÂ° {preventa.preventa_id} guardada, PENDIENTE DE AUTORIZACIÃN por exceder lÃ­mite de descuentos.")
                    else:
                        messages.success(request, f"Â¡Preventa NÂ° {preventa.preventa_id} autorizada y registrada con Ã©xito!")
                        
                    return redirect('preventas_carga')

            except Exception as e:
                messages.error(request, f"Error crÃ­tico al guardar la preventa: {str(e)}")
        else:
            messages.error(request, f"Error en los datos de cabecera: {form.errors.as_text()}")
            
        return redirect('preventas_carga')

class AutorizacionesIndexView(LoginRequiredMixin, View):
    def get(self, request):
        perfil = getattr(request.user, 'perfil', None)
        tiene_permiso = perfil and (perfil.permiso_autorizar_descuentos or perfil.permiso_facturacion_autorizaciones or perfil.es_admin_sistema)
        if not (request.user.is_staff or tiene_permiso):
            messages.error(request, "No tienes permiso para autorizar descuentos.")
            return redirect('ventas_index')
            
        empresa_id = request.session.get('empresa_id')
        preventas = Preventa.objects.filter(empresa_id=empresa_id, estado=1).order_by('-preventa_id')
        ventas = Venta.objects.filter(empresa_id=empresa_id, estado=2).order_by('-ventas_id')
        
        return render(request, 'facturacion/autorizaciones_index.html', {
            'preventas': preventas,
            'ventas': ventas
        })

class ClientesProveedoresIndexView(LoginRequiredMixin, TemplateView):
    template_name = 'facturacion/clientes_index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        empresa_id = self.request.session.get('empresa_id')
        if not empresa_id and hasattr(self.request.user, 'perfil') and self.request.user.perfil and self.request.user.perfil.empresa_id:
            empresa_id = self.request.user.perfil.empresa_id
            self.request.session['empresa_id'] = empresa_id
        select_fields = ['jurisdiccion']
        try:
            ClienteProveedor._meta.get_field('armeria')
            select_fields.append('armeria')
        except:
            pass
        context['clientes'] = ClienteProveedor.objects.filter(empresa_id=empresa_id).select_related(*select_fields).order_by('-codigo_id')[:100]
        return context

class ComprasIndexView(LoginRequiredMixin, TemplateView):
    template_name = 'facturacion/compras_index.html'

class VentasIndexView(LoginRequiredMixin, TemplateView):
    template_name = 'facturacion/ventas_index.html'


class ComprasListView(LoginRequiredMixin, View):
    """Listado de compras con filtros (rango de fechas + proveedor), totales, baja fÃ­sica
    y exportaciÃ³n a Excel (?export=excel)."""
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        if not empresa_id:
            messages.warning(request, "Por favor, seleccione una empresa primero.")
            return redirect('seleccion_empresa')

        # Por defecto, se establece la fecha del día de hoy en 'desde' y 'hasta'
        # para evitar consultas pesadas históricas al abrir el listado (Plan 061).
        hoy = timezone.localdate().isoformat()
        desde = (request.GET.get('desde') or hoy).strip()
        hasta = (request.GET.get('hasta') or hoy).strip()
        proveedor_id = (request.GET.get('proveedor') or '').strip()
        condic = (request.GET.get('condic') or '').strip()
        compra_id_q = (request.GET.get('compra_id') or '').strip()

        compras = (Compra.objects.filter(empresa_id=empresa_id)
                   .select_related('tipo', 'proveedor'))
        if compra_id_q:
            compras = compras.filter(compras_id=compra_id_q)
        else:
            if desde:
                compras = compras.filter(fecha__gte=desde)
            if hasta:
                compras = compras.filter(fecha__lte=hasta)
            if proveedor_id:
                compras = compras.filter(proveedor_id=proveedor_id)
            if condic in ('1', '2'):
                compras = compras.filter(condic=condic)
        compras = compras.order_by('-fecha', '-compras_id')

        # Exportación a Excel: respeta los filtros, sin límite de filas.
        if request.GET.get('export') == 'excel':
            from facturacion.services.compras_excel import exportar_compras_excel
            empresa = Empresa.objects.filter(pk=empresa_id).first()
            prov_nombre = None
            if proveedor_id:
                p = ClienteProveedor.objects.filter(pk=proveedor_id, empresa_id=empresa_id).first()
                prov_nombre = p.razon_social if p else None
            condic_nombre = {'1': 'Real', '2': 'Presupuesto'}.get(condic, 'Todas')
            return exportar_compras_excel(compras, empresa, {
                'desde': desde, 'hasta': hasta,
                'proveedor_nombre': prov_nombre, 'condic_nombre': condic_nombre,
            })

        totales = compras.aggregate(neto=Sum('neto'), iva=Sum('iva'), total=Sum('total'))
        proveedores = (ClienteProveedor.objects
                       .filter(compra__empresa_id=empresa_id).distinct()
                       .order_by('razon_social'))

        proveedor_display = ''
        if proveedor_id:
            prov_obj = ClienteProveedor.objects.filter(pk=proveedor_id, empresa_id=empresa_id).first()
            if prov_obj:
                proveedor_display = prov_obj.razon_social

        return render(request, 'facturacion/compras_listado.html', {
            'compras': compras[:500],
            'proveedores': proveedores,
            'desde': desde, 'hasta': hasta, 'proveedor_id': proveedor_id, 'condic': condic,
            'proveedor_display': proveedor_display,
            'compra_id_q': compra_id_q,
            'totales': totales,
        })


class CompraBajaView(LoginRequiredMixin, View):
    """Baja FÃSICA de una compra (errores de carga): borra el comprobante completo,
    revierte stock y limpia asiento/fiscal. Entrada vÃ­a HTMX desde el listado."""
    def post(self, request, compra_id):
        empresa_id = request.session.get('empresa_id')
        compra = get_object_or_404(Compra, pk=compra_id, empresa_id=empresa_id)
        numero = compra.numero
        from contable.services.contabilizacion import dar_de_baja_compra
        try:
            dar_de_baja_compra(compra)
            return HttpResponse('')  # HTMX elimina la fila (hx-swap=outerHTML)
        except Exception as e:
            return HttpResponse(
                f'<tr class="bg-red-50"><td colspan="8" class="px-4 py-3 text-red-700 font-bold '
                f'text-[11px] italic">No se pudo dar de baja la compra NÂº {numero}: {e}</td></tr>',
                status=200
            )


class ComprasCargaView(LoginRequiredMixin, View):
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')
        
        if not empresa_id or not sucursal_id:
            messages.warning(request, "Por favor, seleccione una empresa y sucursal primero.")
            return redirect('seleccion_empresa')

        if not request.GET.get('from_ocr'):
            # Limpiar Ã­items temporales al iniciar carga nueva
            request.session['compra_items_temp'] = []
            request.session['compra_oc_ids'] = []  # circuito OC (Plan 028)

        initial_data = {
            'empresa': empresa_id,
            'sucursal': sucursal_id,
            'fecha': timezone.localdate()
        }
        form = CompraForm(initial=initial_data)
        form.fields['proveedor'].queryset = ClienteProveedor.objects.filter(empresa_id=empresa_id).order_by('razon_social')
        cuentas = Cuenta.objects.filter(empresa_id=empresa_id, imputable=1).order_by('jerarquia')
        alicuotas_iva = AlicuotaIva.objects.filter(activo=True).order_by('orden', 'codigo')
        empresa = Empresa.objects.filter(pk=empresa_id).first()
        jurisdicciones = empresa.jurisdicciones_iibb.order_by('codigo') if empresa else []
        periodo_sugerido = obtener_primer_periodo_vigente_compra(empresa_id, initial_data['fecha'])
        return render(request, 'facturacion/compras_carga.html', {
            'form': form, 'cuentas': cuentas, 'alicuotas_iva': alicuotas_iva,
            'condicion_iibb': empresa.condicion_iibb if empresa else 'LOCAL',
            'jurisdicciones_iibb': jurisdicciones,
            'empresa_usa_oc': empresa.usa_orden_compra if empresa else False,
            'periodo_sugerido': periodo_sugerido,
        })

    def post(self, request):
        data = request.POST.copy()
        campos_monetarios = ['subtotal', 'neto', 'descuento', 'iva', 'no_gravado', 'exento', 'p_iibb', 'p_iva', 'otros', 'total', 'cotizacion']

        for campo in campos_monetarios:
            val = data.get(campo, '').strip()
            if val:
                data[campo] = val.replace('.', '').replace(',', '.')
            else:
                data[campo] = '0'

        form = CompraForm(data)
        form.fields['proveedor'].queryset = ClienteProveedor.objects.filter(empresa_id=request.session.get('empresa_id')).order_by('razon_social')
        cuentas = Cuenta.objects.filter(empresa_id=request.session.get('empresa_id'), imputable=1).order_by('jerarquia')
        alicuotas_iva = AlicuotaIva.objects.filter(activo=True).order_by('orden', 'codigo')
        empresa_ctx = Empresa.objects.filter(pk=request.session.get('empresa_id')).first()
        ctx_base = {
            'form': form, 'cuentas': cuentas, 'alicuotas_iva': alicuotas_iva,
            'condicion_iibb': empresa_ctx.condicion_iibb if empresa_ctx else 'LOCAL',
            'jurisdicciones_iibb': empresa_ctx.jurisdicciones_iibb.order_by('codigo') if empresa_ctx else [],
        }
        items_temp = request.session.get('compra_items_temp', [])
        es_gasto = request.POST.get('modo') == 'gasto'

        if not items_temp and not es_gasto:
            messages.error(request, "Debe cargar al menos un producto en la grilla.")
            return render(request, 'facturacion/compras_carga.html', ctx_base)

        if form.is_valid():
            # ValidaciÃ³n de Duplicados
            empresa_id = request.session.get('empresa_id')
            proveedor_id = data.get('proveedor')
            punto = data.get('punto', '').strip()
            numero = data.get('numero', '').strip()
            
            if punto and numero and Compra.objects.filter(empresa_id=empresa_id, proveedor_id=proveedor_id, punto=punto, numero=numero).exists():
                messages.error(request, f"Â¡AtenciÃ³n! La factura {punto}-{numero} de este proveedor ya se encuentra cargada en el sisitema.")
                return render(request, 'facturacion/compras_carga.html', ctx_base)

            # Validación de Series Obligatorias para Subproductos
            for item in items_temp:
                if item.get('subprod'):
                    cant = int(float(item.get('cantidad', 1)))
                    series = item.get('series', [])
                    if len(series) < cant:
                        messages.error(request, f"Debe cargar todas las Series/CUIM para el producto {item.get('detalle')} (Faltan {cant - len(series)}).")
                        return render(request, 'facturacion/compras_carga.html', ctx_base)
                    for s in series:
                        if not s.get('serie') or not s.get('cuim'):
                            messages.error(request, f"Debe cargar SERIE y CUIM completos para el producto {item.get('detalle')}.")
                            return render(request, 'facturacion/compras_carga.html', ctx_base)
                        from productos.models import Subproducto
                        if Subproducto.objects.filter(serie__iexact=s.get('serie').strip(), empresa_id=request.session.get('empresa_id')).exclude(situacion='VENDIDA').exists():
                            messages.error(request, f"Error: La serie {s.get('serie')} ya se encuentra activa en el inventario.")
                            return render(request, 'facturacion/compras_carga.html', ctx_base)

            try:
                with transaction.atomic():
                    compra = form.save(commit=False)
                    compra.usuario = request.user
                    compra.empresa_id = request.session.get('empresa_id')
                    compra.sucursal_id = request.session.get('sucursal_id')
                    
                    # Lógica estricta de Período IVA para Compras:
                    fecha_yyyymm = compra.fecha.strftime('%Y%m')
                    periodo_manual = data.get('periodo', '').replace('-', '').strip()

                    if periodo_manual:
                        if periodo_manual < fecha_yyyymm:
                            messages.error(request, f"Error: El período IVA ({periodo_manual}) no puede ser anterior al período de su fecha de emisión ({fecha_yyyymm}).")
                            return render(request, 'facturacion/compras_carga.html', ctx_base)
                        if es_periodo_cerrado(compra.empresa_id, periodo_manual):
                            messages.error(request, f"Error: El período IVA ({periodo_manual}) se encuentra cerrado.")
                            return render(request, 'facturacion/compras_carga.html', ctx_base)
                        compra.periodo = periodo_manual
                    else:
                        compra.periodo = obtener_primer_periodo_vigente_compra(compra.empresa_id, compra.fecha)

                    compra.ejercicio = Ejercicio.objects.filter(
                        empresa_id=compra.empresa_id,
                        inicio__lte=compra.fecha,
                        cierre__gte=compra.fecha
                    ).first()

                    # Nota de CrÃ©dito (tipo.signo = -1): los importes se almacenan en negativo.
                    from decimal import Decimal
                    signo = compra.tipo.signo if compra.tipo else 1

                    # Circuito OC (Plan 028): activo solo si hay OC vinculadas en sesión,
                    # no es gasto y no es NC. En ese caso el stock lo maneja la Recepción.
                    oc_ids_sesion = request.session.get('compra_oc_ids') or []
                    es_circuito_oc = bool(oc_ids_sesion) and not es_gasto and signo > 0
                    
                    # Vinculación manual a remito (recepción): para auditoría
                    rec_ids_sesion = request.session.get('compra_recepcion_ids') or []
                    if rec_ids_sesion and len(rec_ids_sesion) > 0:
                        compra.id_fac_rem = rec_ids_sesion[0]
                        
                    if signo < 0:
                        for _f in ['subtotal', 'neto', 'descuento', 'iva', 'no_gravado', 'exento', 'p_iva', 'p_gcia',
                                   'p_iibb', 'p_recbc', 'p_sircreb', 'p_mun', 'otros', 'total']:
                            _v = getattr(compra, _f, 0) or 0
                            setattr(compra, _f, -abs(Decimal(str(_v))))

                    # Gasto (sin Ã­items): el Neto y el IVA salen del desglose por alÃ­cuota cargado
                    # a mano (codiva ARCA + neto + alÃ­cuota â IVA computable, editable). recalcular_totales
                    # no se dispara sin Ã­items, asÃ­ que la cabecera y el saldo se arman acÃ¡.
                    if not es_gasto and items_temp:
                        from productos.models import Producto
                        from contable.models import ParametrosContables
                        prod = Producto.objects.filter(id=items_temp[0].get('producto_id')).select_related('rubro').first()
                        if prod and prod.rubro and prod.rubro.cta_compras_id:
                            compra.cta_imputacion = prod.rubro.cta_compras_id
                        else:
                            parametros = ParametrosContables.objects.filter(empresa_id=compra.empresa_id).first()
                            compra.cta_imputacion = parametros.cta_compras_id if parametros else None

                    if es_gasto:
                        def _num(v):
                            v = (v or '').strip()
                            return Decimal(v.replace('.', '').replace(',', '.')) if v else Decimal('0')

                        codigos = request.POST.getlist('alic_codigo')
                        porcentajes = request.POST.getlist('alic_porcentaje')
                        netos = request.POST.getlist('alic_neto')
                        ivas = request.POST.getlist('alic_iva')

                        alic_rows = []
                        total_neto = Decimal('0')
                        total_iva = Decimal('0')
                        for i, cod in enumerate(codigos):
                            neto_i = _num(netos[i] if i < len(netos) else '')
                            iva_i = _num(ivas[i] if i < len(ivas) else '')
                            if neto_i == 0 and iva_i == 0:
                                continue  # fila sin cargar
                            alic_rows.append({
                                'codigo': cod,
                                'porcentaje': _num(porcentajes[i] if i < len(porcentajes) else ''),
                                'neto': neto_i * signo,   # NC: negativo
                                'iva': iva_i * signo,
                            })
                            total_neto += neto_i
                            total_iva += iva_i

                        # Cabecera de IVA = suma del desglose (server-authoritative), con signo de NC.
                        compra.neto = total_neto * signo
                        compra.iva = total_iva * signo
                        compra.descuento = Decimal('0')  # los gastos NO tienen descuento global
                        compra.subtotal = compra.neto    # sin descuento â subtotal = neto

                        # 1) Guardar SIN contabilizar (necesitamos el PK para colgar los detalles).
                        compra._no_contabilizar = True
                        compra.save()
                        compra._no_contabilizar = False
                        # 2) Persistir desglose de alÃ­cuotas + detalle de ret/perc (setea p_iva/p_iibb/otros).
                        CompraAlicuota.objects.filter(compra=compra).delete()
                        for r in alic_rows:
                            CompraAlicuota.objects.create(compra=compra, **r)
                        self._aplicar_retperc(request, compra, signo)
                        # 3) Total con ret/perc ya resueltas.
                        otros_conceptos = sum(
                            (Decimal(str(getattr(compra, f, 0) or 0)) for f in
                             ['no_gravado', 'exento', 'p_iva', 'p_iibb', 'otros']),
                            Decimal('0'),
                        )
                        compra.total = compra.neto + compra.iva + otros_conceptos
                        compra.saldo = compra.total - Decimal(str(compra.pagado or 0))
                        # 4) Contabilizar ahora que alÃ­cuotas y ret/perc existen.
                        compra.save()
                    else:
                        # Circuito OC: el stock lo mueve la RecepciÃ³n, no la factura.
                        compra.gestion_stock_por_recepcion = es_circuito_oc
                        compra.save()
                        # Detalle de ret/perc (modales de IIBB/Otros) â para Bienes tambiÃ©n.
                        self._aplicar_retperc(request, compra, signo)
                        # Persistir los totales de cabecera para que recalcular_totales (disparado por
                        # los Ã­items) calcule el total con las percepciones, sin recontabilizar acÃ¡.
                        compra._no_contabilizar = True
                        compra.save(update_fields=['p_iva', 'p_iibb', 'otros'])
                        compra._no_contabilizar = False

                    for item in items_temp:
                        producto = get_object_or_404(Producto, id=item['producto_id'], empresa_id=request.session.get('empresa_id'))
                        cantidad = float(item['cantidad'])
                        precio_unitario = float(item['precio'])
                        
                        CompraItem.objects.create(
                            compra=compra,
                            producto=producto,
                            cantidad=cantidad,
                            precio_unitario=precio_unitario,
                            iva_alicuota=item['iva'],
                            total=Decimal(str(item['total'])) * signo  # negativo para NC
                        )

                        # Trazabilidad de Subproductos (Plan 002)
                        if producto.subprod and item.get('series') and signo > 0:
                            from productos.models import Subproducto
                            for s in item['series'][:int(cantidad)]:
                                if s.get('serie'):
                                    Subproducto.objects.create(
                                        empresa_id=request.session.get('empresa_id'),
                                        producto=producto,
                                        sucursal_id=request.session.get('sucursal_id'),
                                        serie=s['serie'].upper(),
                                        cuim=s.get('cuim', '').upper() if s.get('cuim') else None,
                                        compra=compra,
                                        feccpra=compra.fecha,
                                        cto_adq=Decimal(str(item.get('cto_adq', precio_unitario))),
                                        cotizadq=compra.cotizacion,
                                        moneda=producto.moneda,
                                        alic_iva=Decimal(str(item['iva'])),
                                        margen=Decimal(str(producto.margen or 0))
                                    )

                        # NC: no actualiza costos ni precios del producto (una devoluciÃ³n no es el Ãºltimo precio).
                        if signo < 0:
                            continue

                        # --- Costos con bonificaciÃ³n (Fase 4) ---
                        # cto_adq (con bonificaciÃ³n) y cto_rep (precio de lista) vienen calculados
                        # desde la grilla; se mantiene fallback al unitario para Ã­items sin esos datos.
                        cto_adq = Decimal(str(item.get('cto_adq', precio_unitario)))
                        cto_rep = Decimal(str(item.get('cto_rep', cto_adq)))
                        producto.cto_adq = cto_adq
                        producto.fec_adq = compra.fecha
                        producto.cto_rep = cto_rep
                        producto.fec_act = timezone.localdate()
                        producto.compra_id = compra.compras_id
                        producto.cotiz_cpra = compra.cotizacion
                        # Precio de venta (en moneda de origen; se pesifica al vender).
                        alic = Decimal(str(producto.alic_iva or 0))
                        factor_iva = Decimal('1') + alic / Decimal('100')
                        precio_nuevo_raw = (request.POST.get(f'precio_nuevo_{producto.id}', '') or '').strip()
                        if precio_nuevo_raw:
                            # Precio confirmado/editado por el usuario en el modal de revisiÃ³n (IVA incluido).
                            precio_total_final = Decimal(precio_nuevo_raw)
                            producto.precio_total = precio_total_final.quantize(Decimal('0.01'))
                            producto.precio_neto = (precio_total_final / factor_iva).quantize(Decimal('0.01'))
                        else:
                            # Fallback: recÃ¡lculo automÃ¡tico desde cto_rep Ã margen.
                            margen = Decimal(str(producto.margen or 0))
                            precio_neto = (cto_rep * (Decimal('1') + margen / Decimal('100'))).quantize(Decimal('0.01'))
                            producto.precio_neto = precio_neto
                            producto.precio_total = (precio_neto * factor_iva).quantize(Decimal('0.01'))
                        producto.save()
                    
                    # Circuito OC (Plan 028): imputar a las OC, generar Informe de RecepciÃ³n
                    # cuando la factura hace de remito, y resolver diferencias.
                    if es_circuito_oc:
                        self._procesar_circuito_oc(request, compra, items_temp)

                    # Guardar archivo PDF/WEBP si vino desde carga automática
                    pdf_temp_path = request.POST.get('pdf_temp_path')
                    if pdf_temp_path:
                        import os
                        from django.conf import settings
                        from django.core.files import File
                        
                        full_temp_path = os.path.join(settings.MEDIA_ROOT, pdf_temp_path)
                        if os.path.exists(full_temp_path):
                            with open(full_temp_path, 'rb') as f:
                                asiento = compra.asiento_id or '0'
                                ejercicio = compra.ejercicio_id if compra.ejercicio else '0'
                                nombre_final = f"{compra.empresa_id}.{ejercicio}.{asiento}.webp"
                                compra.archivo_pdf.save(nombre_final, File(f), save=True)
                            try:
                                os.remove(full_temp_path)
                            except:
                                pass

                    request.session['compra_items_temp'] = []
                    request.session['compra_oc_ids'] = []
                    request.session['compra_recepcion_ids'] = []
                    if es_gasto:
                        messages.success(request, f"Â¡Factura de gasto {compra.numero} cargada con Ã©xito!")
                    elif es_circuito_oc:
                        messages.success(request, f"Â¡Factura {compra.numero} cargada e imputada a las Ã³rdenes de compra!")
                    else:
                        messages.success(request, f"Â¡Factura {compra.numero} cargada con Ã©xito! Stock y costos actualizados.")
                    return redirect('compras_carga')

            except Exception as e:
                messages.error(request, f"Error crÃ­tico al guardar en el motor: {str(e)}")
        
        if not form.is_valid():
            messages.error(request, f"Error en los datos del comprobante: {form.errors.as_text()}")

        return render(request, 'facturacion/compras_carga.html', ctx_base)

    def _procesar_circuito_oc(self, request, compra, items_temp):
        """Circuito OC (Plan 028 Fase 5). Sobre una factura de Bienes ya guardada con sus
        CompraItem creados (y con gestion_stock_por_recepcion=True):

        1. Imputa cada lÃ­nea de factura a las lÃ­neas de OC (FIFO) â CompraOCImputacion,
           acumulando OrdenCompraItem.cantidad_facturada.
        2. Genera el Informe de RecepciÃ³n (origen=PROVEEDOR_FACTURA) por lo facturado de
           lÃ­neas SIN remito previo (la factura hace de remito) â stock por la RecepciÃ³n.
           Si hubo remito (cantidad_recibida>0), NO se genera ni se toca stock (queda como
           pendiente de recepciÃ³n si facturado>recibido).
        3. Resuelve la diferencia facturado=recibidoâ OC por lÃ­nea: 'ajustar' la OC a la
           cantidad real o 'marcar' la diferencia (default). DecisiÃ³n desde el POST.
        4. Recalcula estados de las OC afectadas.
        """
        from decimal import Decimal
        from .models import (OrdenCompra, OrdenCompraItem, CompraOCImputacion,
                             Recepcion, RecepcionItem, RecepcionImputacion)
        from core.models import ContadorDocumento
        from core.services.numeracion import siguiente_numero

        citems = {ci.producto_id: ci for ci in compra.items.all()}
        ocs_afectadas = set()
        recep_por_prod = {}   # producto_id -> Decimal (cantidad a recepcionar por la factura-remito)
        recep_imputs = []     # (producto_id, oc_item, cantidad) para imputar la recepciÃ³n a la OC

        for it in items_temp:
            pid = int(it['producto_id'])
            citem = citems.get(pid)
            if not citem:
                continue
            fuentes = it.get('oc_fuentes')
            if not fuentes:
                # Ãitem manual dentro del circuito OC: la factura hace de remito por todo.
                recep_por_prod[pid] = recep_por_prod.get(pid, Decimal('0')) + Decimal(str(citem.cantidad))
                continue
            restante = Decimal(str(citem.cantidad))
            for f in fuentes:
                if restante <= 0:
                    break
                try:
                    oc_item = OrdenCompraItem.objects.select_for_update().get(pk=f['oc_item_id'])
                except OrdenCompraItem.DoesNotExist:
                    continue
                pend_fact = oc_item.pendiente_facturacion
                if pend_fact <= 0:
                    continue
                tenia_remito = oc_item.cantidad_recibida > 0
                imp = min(restante, pend_fact)
                CompraOCImputacion.objects.create(compra_item=citem, orden_item=oc_item, cantidad=imp)
                oc_item.cantidad_facturada = oc_item.cantidad_facturada + imp
                oc_item.save(update_fields=['cantidad_facturada'])
                ocs_afectadas.add(oc_item.orden_id)
                restante -= imp
                if not tenia_remito:
                    # Sin remito â la factura hace de remito por lo facturado de esta lÃ­nea.
                    recep_por_prod[pid] = recep_por_prod.get(pid, Decimal('0')) + imp
                    recep_imputs.append((pid, oc_item, imp))

        # Generar el Informe de RecepciÃ³n (factura como remito) por lo no recibido con remito.
        if any(v > 0 for v in recep_por_prod.values()):
            recepcion = Recepcion(
                empresa_id=compra.empresa_id, sucursal=compra.sucursal, punto=compra.sucursal.punto,
                fecha=compra.fecha, origen=Recepcion.PROVEEDOR_FACTURA, proveedor=compra.proveedor,
                generada_por_factura=compra, estado=Recepcion.ACTIVA, usuario=request.user,
                creado_por=request.user, modificado_por=request.user,
                observaciones=f"Generado automÃ¡ticamente por la Factura {compra.numero}",
            )
            recepcion.numero = siguiente_numero(compra.empresa_id, compra.sucursal.punto,
                                                ContadorDocumento.INFORME_RECEPCION)
            recepcion.save()
            ritems = {}
            for pid, cant in recep_por_prod.items():
                if cant > 0:
                    ritems[pid] = RecepcionItem.objects.create(
                        recepcion=recepcion, producto_id=pid, cantidad_recibida=cant)
            for pid, oc_item, cant in recep_imputs:
                ri = ritems.get(pid)
                if not ri:
                    continue
                RecepcionImputacion.objects.create(recepcion_item=ri, orden_item=oc_item, cantidad=cant)
                oc_item.cantidad_recibida = oc_item.cantidad_recibida + cant
                oc_item.save(update_fields=['cantidad_recibida'])

        # Diferencia por lÃ­nea (facturado == recibido â  OC) + recÃ¡lculo de estados.
        for oc_id in ocs_afectadas:
            oc = OrdenCompra.objects.get(pk=oc_id)
            for li in oc.items.all():
                if li.es_candidato_diferencia:
                    decision = (request.POST.get(f'oc_ajuste_{li.pk}') or 'marcar').strip()
                    if decision == 'ajustar':
                        li.cantidad = li.cantidad_facturada
                        li.marcado_diferencia = False
                        li.save(update_fields=['cantidad', 'marcado_diferencia'])
                    else:
                        li.marcado_diferencia = True
                        li.save(update_fields=['marcado_diferencia'])
            oc.recalcular_estados()

    def _juris_automatica(self, empresa):
        """JurisdicciÃ³n por defecto para IIBB Local: la Ãºnica inscripta, o 999 (Sede Local/Ãnica)."""
        from .models import Jurisdiccion
        j = empresa.jurisdicciones_iibb.first()
        return j or Jurisdiccion.objects.filter(codigo='999').first()

    def _aplicar_retperc(self, request, compra, signo):
        """Persiste el detalle de ret/perc sufridas (CompraRetPerc) desde los campos/modales y
        deja `compra.p_iva/p_iibb/otros` como totales de cabecera (server-authoritative).
          - Perc. IVA: campo simple â 1 fila IVA.
          - Perc. IIBB: si la empresa es CM y vino el modal â 1 fila por jurisdicciÃ³n; si no,
            1 fila a la jurisdicciÃ³n automÃ¡tica (Local).
          - Otros Imp.: si vino el modal â 1 fila por impuesto (SIRCREB/TEM/SUSS/MUN/OTRO...);
            si no, queda como Impuestos Internos (sin ret/perc)."""
        def _num(v):
            v = (v or '').strip()
            return Decimal(v.replace('.', '').replace(',', '.')) if v else Decimal('0')

        empresa = compra.empresa
        es_cm = empresa.condicion_iibb == 'CM'
        filas = []

        # Perc. IVA (campo simple de la fila de cierre)
        p_iva = _num(request.POST.get('p_iva'))
        if p_iva:
            filas.append({'impuesto': 'IVA', 'jurisdiccion_id': None, 'importe': p_iva})

        # Perc. IIBB
        iibb_total = Decimal('0')
        juris_ids = request.POST.getlist('iibb_juris')
        juris_imps = request.POST.getlist('iibb_importe')
        if es_cm and any((j or '').strip() for j in juris_ids):
            for i, jid in enumerate(juris_ids):
                imp = _num(juris_imps[i] if i < len(juris_imps) else '')
                if imp == 0 or not (jid or '').strip():
                    continue
                filas.append({'impuesto': 'IIBB', 'jurisdiccion_id': int(jid), 'importe': imp})
                iibb_total += imp
        else:
            p_iibb = _num(request.POST.get('p_iibb'))
            if p_iibb:
                jur = self._juris_automatica(empresa)
                filas.append({'impuesto': 'IIBB', 'jurisdiccion_id': jur.pk if jur else None, 'importe': p_iibb})
                iibb_total = p_iibb

        # Otros Imp. (desglosado por impuesto)
        otros_total = Decimal('0')
        otros_detallado = False
        otros_imps = request.POST.getlist('otros_impuesto')
        otros_vals = request.POST.getlist('otros_importe')
        for i, cod in enumerate(otros_imps):
            val = _num(otros_vals[i] if i < len(otros_vals) else '')
            if val == 0 or not (cod or '').strip():
                continue
            otros_detallado = True
            filas.append({'impuesto': cod, 'jurisdiccion_id': None, 'importe': val})
            otros_total += val
        if not otros_detallado:
            otros_total = _num(request.POST.get('otros'))  # sin desglose â Impuestos Internos

        # Totales de cabecera (con signo de NC)
        compra.p_iva = p_iva * signo
        compra.p_iibb = iibb_total * signo
        compra.otros = otros_total * signo

        # Reescribir el detalle
        CompraRetPerc.objects.filter(compra=compra).delete()
        for f in filas:
            CompraRetPerc.objects.create(
                compra=compra, impuesto=f['impuesto'], tipo='P',
                jurisdiccion_id=f['jurisdiccion_id'], importe=f['importe'] * signo,
            )

class VentasListView(LoginRequiredMixin, View):
    """Listado de ventas con filtros (rango de fechas, cliente, sucursal, vendedor, comprobante), 
    totales y acciones como emitir NC."""
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        if not empresa_id:
            messages.warning(request, "Por favor, seleccione una empresa primero.")
            return redirect('seleccion_empresa')

        # Por defecto, se establece la fecha del día de hoy en 'desde' y 'hasta'
        # para evitar consultas pesadas históricas al abrir el listado (Plan 061).
        hoy = timezone.localdate().isoformat()
        desde = (request.GET.get('desde') or hoy).strip()
        hasta = (request.GET.get('hasta') or hoy).strip()

        cliente_id = (request.GET.get('cliente') or '').strip()
        sucursal_id = (request.GET.get('sucursal') or '').strip()
        vendedor_id = (request.GET.get('vendedor') or '').strip()
        tipo_id = (request.GET.get('tipo') or '').strip()
        condic = (request.GET.get('condic') or '').strip()

        venta_id_q = (request.GET.get('venta_id') or '').strip()

        ventas = (Venta.objects.filter(empresa_id=empresa_id)
                   .select_related('tipo', 'cliente', 'sucursal', 'vendedor'))
        
        if venta_id_q:
            ventas = ventas.filter(ventas_id=venta_id_q)
        else:
            if desde:
                ventas = ventas.filter(fecha__gte=desde)
            if hasta:
                ventas = ventas.filter(fecha__lte=hasta)
            if cliente_id:
                ventas = ventas.filter(cliente_id=cliente_id)
            if sucursal_id:
                ventas = ventas.filter(sucursal_id=sucursal_id)
            if vendedor_id:
                ventas = ventas.filter(vendedor_id=vendedor_id)
            if tipo_id:
                ventas = ventas.filter(tipo_id=tipo_id)
            if condic in ('1', '2'):
                ventas = ventas.filter(condic=condic)
            
        ventas = ventas.order_by('-fecha', '-ventas_id')

        totales = ventas.aggregate(neto=Sum('neto'), iva=Sum('iva'), total=Sum('total'))
        
        # Opciones para filtros
        from empresas.models import Sucursal
        clientes = ClienteProveedor.objects.filter(empresa_id=empresa_id, tipo_entidad=1).order_by('razon_social')
        sucursales = Sucursal.objects.filter(empresa_id=empresa_id)
        from django.contrib.auth import get_user_model
        vendedores = get_user_model().objects.filter(ventas_vendedor__empresa_id=empresa_id).distinct()
        tipos = TipoComprobante.objects.filter(venta__empresa_id=empresa_id).distinct()

        cliente_display = ''
        if cliente_id:
            cliente_obj = ClienteProveedor.objects.filter(pk=cliente_id, empresa_id=empresa_id).first()
            if cliente_obj:
                cliente_display = cliente_obj.razon_social

        return render(request, 'facturacion/ventas_listado.html', {
            'ventas': ventas[:500],
            'clientes': clientes,
            'sucursales': sucursales,
            'vendedores': vendedores,
            'tipos': tipos,
            'desde': desde, 'hasta': hasta, 
            'cliente_id': cliente_id, 'sucursal_id': sucursal_id,
            'cliente_display': cliente_display,
            'vendedor_id': vendedor_id, 'tipo_id': tipo_id,
            'condic': condic,
            'venta_id_q': venta_id_q,
            'totales': totales,
        })


class VentaAnularModalView(LoginRequiredMixin, View):
    """Devuelve el modal HTMX para anular una factura (NC)."""
    def get(self, request, id):
        empresa_id = request.session.get('empresa_id')
        venta = get_object_or_404(Venta, pk=id, empresa_id=empresa_id)
        
        return render(request, 'facturacion/partials/venta_anular_modal.html', {
            'venta': venta,
            'items': venta.items.all()
        })


class VentaEmitirNotaCreditoView(LoginRequiredMixin, View):
    """Procesa el formulario del modal para emitir la NC."""
    def post(self, request, id):
        empresa_id = request.session.get('empresa_id')
        venta_original = get_object_or_404(Venta, pk=id, empresa_id=empresa_id)
        
        # Extraer cantidades a devolver del POST
        items_devolucion = {}
        for key, value in request.POST.items():
            if key.startswith('cant_devolver_'):
                item_id = int(key.replace('cant_devolver_', ''))
                try:
                    cant = Decimal(str(value).replace(',', '.'))
                    if cant > 0:
                        items_devolucion[item_id] = cant
                except:
                    pass
        
        if not items_devolucion:
            messages.error(request, "Debe especificar al menos un item a devolver.")
            response = HttpResponse()
            response['HX-Redirect'] = reverse('ventas_listado')
            return response
            
        from facturacion.services.notas_credito import MAPEO_NC
        from facturacion.models import TipoComprobante
        from empresas.models import Empresa
        from facturacion.services.afip_service import AFIPService
        from facturacion.views import ALICUOTAS_ARCA_MAP, mapear_condicion_iva_receptor
        
        if not venta_original.tipo or venta_original.tipo.codigo not in MAPEO_NC:
            messages.error(request, "El tipo de comprobante no es válido o no tiene una Nota de Crédito asociada soportada.")
            response = HttpResponse()
            response['HX-Redirect'] = reverse('ventas_listado')
            return response
            
        codigo_nc = MAPEO_NC[venta_original.tipo.codigo]
        tipo_nc = TipoComprobante.objects.filter(codigo=codigo_nc).first()
        if not tipo_nc:
            messages.error(request, f"No existe el tipo de comprobante Nota de Crédito asociado al código '{codigo_nc}'.")
            response = HttpResponse()
            response['HX-Redirect'] = reverse('ventas_listado')
            return response

        # Obtener el punto de venta de la tabla (Sucursal activa de la sesión)
        sucursal_id = request.session.get('sucursal_id')
        from empresas.models import PuntoVenta
        pv_default = PuntoVenta.objects.filter(sucursal_id=sucursal_id, activo=True, caja_mostrador_default=True).first()
        if not pv_default:
            pv_default = PuntoVenta.objects.filter(sucursal_id=sucursal_id, activo=True).first()
        punto_venta_num = pv_default.numero if pv_default else venta_original.punto

        res_afip = None
        if venta_original.condic == 1 and tipo_nc.codigo.isdigit():
            empresa_obj = get_object_or_404(Empresa, id=empresa_id)
            
            tot_neto = Decimal('0.00')
            tot_iva = Decimal('0.00')
            alicuotas_dict = {}
            
            from facturacion.models import VentaItem
            for item_id, cantidad in items_devolucion.items():
                orig_item = VentaItem.objects.filter(id=item_id, venta=venta_original).first()
                if orig_item:
                    cant_dec = Decimal(str(cantidad))
                    precio = orig_item.precio_unitario
                    desc = orig_item.porcentaje_descuento or Decimal('0.00')
                    total_item = (precio * cant_dec) * (Decimal('1') - (desc / Decimal('100')))
                    
                    alic_val = Decimal(str(orig_item.iva_alicuota or '21.00'))
                    alicuota_factor = Decimal("1.00") + (alic_val / Decimal("100.00"))
                    neto_item = (total_item / alicuota_factor).quantize(Decimal("0.01"))
                    iva_item = total_item - neto_item
                    
                    tot_neto += neto_item
                    tot_iva += iva_item
                    
                    id_iva = 3
                    for k, v in ALICUOTAS_ARCA_MAP.items():
                        if abs(k - alic_val) < Decimal("0.05"):
                            id_iva = v
                            break
                    if id_iva not in alicuotas_dict:
                        alicuotas_dict[id_iva] = {
                            'id_iva': id_iva,
                            'alicuota': alic_val,
                            'base_imponible': Decimal("0.00"),
                            'importe_iva': Decimal("0.00")
                        }
                    alicuotas_dict[id_iva]['base_imponible'] += neto_item
                    alicuotas_dict[id_iva]['importe_iva'] += iva_item
                    
            alicuotas_list = list(alicuotas_dict.values())
            cond_iva_rec = mapear_condicion_iva_receptor(venta_original.cliente.condicion_iva)
            
            cuit_doc = str(venta_original.cliente.cuit or '0').replace('-', '').strip()
            if not cuit_doc.isdigit() or len(cuit_doc) == 0 or int(cuit_doc) == 0:
                doc_tipo = 99
                doc_nro = 0
            else:
                doc_tipo = int(venta_original.cliente.tipo_documento or 80)
                doc_nro = int(cuit_doc)
                
            datos_afip = {
                'pto_vta': punto_venta_num,
                'cbte_tipo': int(tipo_nc.codigo),
                'concepto': 1,
                'doc_tipo': doc_tipo,
                'doc_nro': doc_nro,
                'cbte_fch': timezone.localdate().strftime('%Y%m%d'),
                'imp_total': float(tot_neto + tot_iva),
                'imp_tot_conc': 0.0,
                'imp_neto': float(tot_neto),
                'imp_op_ex': 0.0,
                'imp_iva': float(tot_iva),
                'condicion_iva_receptor_id': cond_iva_rec,
                'mon_id': 'PES',
                'mon_cotiz': 1.0,
                'cbte_asoc_tipo': int(venta_original.tipo.codigo),
                'cbte_asoc_pto_vta': int(venta_original.punto),
                'cbte_asoc_nro': int(venta_original.numero),
            }
            
            try:
                afip_service = AFIPService(empresa_obj)
                res_afip = afip_service.emitir_comprobante(datos_afip, alicuotas_list)
                if not res_afip['exito']:
                    messages.error(request, f"Rechazo ARCA al emitir NC: {res_afip['error']}")
                    response = HttpResponse()
                    response['HX-Redirect'] = reverse('ventas_listado')
                    return response
            except Exception as e:
                messages.error(request, f"Error en comunicación con ARCA: {str(e)}")
                response = HttpResponse()
                response['HX-Redirect'] = reverse('ventas_listado')
                return response
                
        from facturacion.services.notas_credito import emitir_nota_credito_desde_venta
        try:
            with transaction.atomic():
                numero_nc = res_afip.get('numero_comprobante') if res_afip and res_afip.get('exito') else None
                nc = emitir_nota_credito_desde_venta(venta_original, items_devolucion, request.user, numero_nc=numero_nc, punto_nc=punto_venta_num)
                if res_afip and res_afip.get('exito'):
                    nc.cae = res_afip.get('cae')
                    nc.vto_cae = res_afip.get('vto_cae')
                    nc.cod_qr = res_afip.get('cod_qr')
                    nc.save(update_fields=['cae', 'vto_cae', 'cod_qr'])
                if nc.condic != 2:
                    request.session['auto_print_url'] = reverse('imprimir_factura', kwargs={'venta_id': nc.ventas_id})
                messages.success(request, f"Nota de Crédito generada exitosamente: {nc.tipo.detalle} {nc.punto:04d}-{nc.numero}")
        except ValidationError as e:
            error_msg = e.message if hasattr(e, 'message') else (e.messages[0] if hasattr(e, 'messages') and e.messages else str(e))
            messages.error(request, f"Error al emitir Nota de Crédito: {error_msg}")
        except Exception as e:
            messages.error(request, f"Ocurrió un error inesperado al guardar la Nota de Crédito: {str(e)}")
            
        response = HttpResponse()
        response['HX-Redirect'] = reverse('ventas_listado')
        return response

class VentaPrevisualizarModalView(LoginRequiredMixin, View):
    """Devuelve el modal HTMX para previsualizar los datos fiscales (QR/CAE)."""
    def get(self, request, id):
        empresa_id = request.session.get('empresa_id')
        venta = get_object_or_404(Venta, pk=id, empresa_id=empresa_id)
        return render(request, 'facturacion/partials/venta_previsualizar_modal.html', {
            'venta': venta
        })



class CompraDetalleModalView(LoginRequiredMixin, View):
    def get(self, request, compra_id):
        empresa_id = request.session.get('empresa_id')
        compra = get_object_or_404(Compra, pk=compra_id, empresa_id=empresa_id)
        
        # Desglose de impuestos/percepciones/conceptos
        impuestos = []
        if compra.no_gravado > 0: impuestos.append({'nombre': 'No Gravado', 'monto': compra.no_gravado})
        if compra.exento > 0: impuestos.append({'nombre': 'Exento', 'monto': compra.exento})
        if compra.iva > 0: impuestos.append({'nombre': 'IVA', 'monto': compra.iva})
        if compra.p_iva > 0: impuestos.append({'nombre': 'Perc. IVA', 'monto': compra.p_iva})
        if compra.p_iibb > 0: impuestos.append({'nombre': 'Perc. IIBB', 'monto': compra.p_iibb})
        if compra.p_gcia > 0: impuestos.append({'nombre': 'Perc. Gcia', 'monto': compra.p_gcia})
        if compra.p_mun > 0: impuestos.append({'nombre': 'Perc. Mun.', 'monto': compra.p_mun})
        if compra.p_sircreb > 0: impuestos.append({'nombre': 'SIRCREB', 'monto': compra.p_sircreb})
        if compra.p_recbc > 0: impuestos.append({'nombre': 'Rec. Bancario', 'monto': compra.p_recbc})
        if compra.otros > 0: impuestos.append({'nombre': 'Otros', 'monto': compra.otros})
        
        # Items de la compra
        items = compra.items.all().select_related('producto')

        # Asiento
        tiene_asiento = compra.asiento_id is not None
        
        return render(request, 'facturacion/partials/compra_detalle_modal.html', {
            'compra': compra,
            'items': items,
            'impuestos': impuestos,
            'tiene_asiento': tiene_asiento,
        })


class VentaSincronizarClienteView(LoginRequiredMixin, View):
    """
    Sincroniza y actualiza los datos personales congelados en la Venta (razón social, CUIT, domicilio)
    a partir de los datos vigentes del maestro ClienteProveedor.
    """
    def post(self, request, id):
        empresa_id = request.session.get('empresa_id')
        venta = get_object_or_404(Venta, pk=id, empresa_id=empresa_id)
        
        if venta.cliente:
            cli = venta.cliente
            venta.cliente_razon_social = cli.razon_social
            venta.cliente_cuit = cli.cuit
            venta.cliente_domicilio = cli.domicilio_completo or cli.domicilio or ''
            venta.save(update_fields=['cliente_razon_social', 'cliente_cuit', 'cliente_domicilio'])
            messages.success(request, f"Datos de cliente actualizados en la venta #{venta.ventas_id}: {cli.razon_social} ({cli.cuit}).")
        else:
            messages.warning(request, f"La venta #{venta.ventas_id} no posee cliente asignado en el maestro.")
            
        referer = request.META.get('HTTP_REFERER', '')
        if request.headers.get('HX-Request'):
            response = HttpResponse()
            if 'reportes/productos-vendidos' in referer or 'productos-vendidos' in referer:
                response['HX-Trigger'] = 'ventaClienteActualizado'
            else:
                response['HX-Redirect'] = referer or reverse('ventas_listado')
            return response
            
        return redirect(referer or 'ventas_listado')


