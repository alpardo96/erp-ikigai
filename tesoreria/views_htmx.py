from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
import json
from .models import MedioPago, CuentaBancaria, Recibo, ReciboAplicacion, ValorTerceros, MovimientoCajaDetalle, TransaccionBancaria, OrdenPago, OrdenPagoAplicacion
from .models import CajaSesion, Caja, CobroTarjeta, MovimientoCaja
from .forms import MedioPagoForm, CuentaBancariaForm
from facturacion.models import ClienteProveedor, Venta, Compra
from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from decimal import Decimal
from contable.services.saldos import recalcular_saldo_compra, recalcular_saldo_venta
from contable.services.retenciones import regimen_rg830_de_compra

def _validar_entidad(entidad_id, empresa_id):
    """La entidad debe pertenecer a la empresa de la sesión (aislamiento multi-tenant).

    Los ids llegan por JSON desde el navegador: sin este control se podía emitir una Orden de
    Pago contra un proveedor de OTRA empresa.
    """
    if not entidad_id:
        raise Exception("Debe seleccionar una entidad (cliente/proveedor).")
    if not ClienteProveedor.objects.filter(pk=entidad_id, empresa_id=empresa_id).exists():
        raise Exception("La entidad seleccionada no pertenece a la empresa activa.")
    return entidad_id


def _validar_cuenta_bancaria(cuenta_id, empresa_id):
    """Ídem para las cuentas bancarias que se usan como origen de pagos y cobros."""
    if not cuenta_id:
        raise Exception("Debe seleccionar una cuenta bancaria.")
    if not CuentaBancaria.objects.filter(cta_bc_id=cuenta_id, empresa_id=empresa_id).exists():
        raise Exception("La cuenta bancaria seleccionada no pertenece a la empresa activa.")
    return cuenta_id


def _validar_cuenta_contable(cuenta_id, empresa_id):
    """Ídem para las cuentas de imputación manual de los comprobantes simples."""
    from contable.models import Cuenta

    if not cuenta_id:
        raise Exception("Debe seleccionar una cuenta contable para la imputación.")
    if not Cuenta.objects.filter(pk=cuenta_id, empresa_id=empresa_id, imputable=1).exists():
        raise Exception("La cuenta contable seleccionada no es válida para la empresa activa.")
    return cuenta_id


def _normalizar_aplicacion(comprobante, importe_aplicado, etiqueta):
    """Aplica el SIGNO del comprobante a una imputación y valida el tope (Plan 035 §2, B5).

    Los formularios cargan SIEMPRE importes positivos: el signo es un atributo del tipo de
    comprobante, no algo que el operador tipee. Las Notas de Crédito se graban en negativo
    (`TipoComprobante.signo = -1`), así que su saldo es negativo y la imputación que las
    cancela también debe serlo.

    El signo lo pone el SERVIDOR, derivándolo del saldo del comprobante. Así el front no puede
    mandar un signo equivocado ni fabricar saldo aplicando un positivo a una NC.

    Valida además que no se exceda el saldo en valor absoluto, para no sobrepagar.
    El comprobante debe venir bloqueado con `select_for_update()` por el llamador.

    Devuelve el importe con signo, listo para persistir.
    """
    saldo = Decimal(str(comprobante.saldo or 0))
    magnitud = abs(Decimal(str(importe_aplicado or 0)))

    if magnitud == 0:
        return Decimal('0.00')

    if saldo == 0:
        raise Exception(f"{etiqueta}: el comprobante no tiene saldo pendiente.")

    if magnitud > abs(saldo):
        raise Exception(
            f"{etiqueta}: se intenta aplicar {magnitud} sobre un saldo de {abs(saldo)}."
        )

    return magnitud if saldo > 0 else -magnitud

@login_required
def buscar_mediospago(request):
    empresa_id = request.session.get('empresa_id')
    q = request.GET.get('q', '')
    
    medios = MedioPago.objects.filter(empresa_id=empresa_id)
    if q:
        medios = medios.filter(nombre__icontains=q) | medios.filter(codigo__icontains=q)
        
    return render(request, 'configuracion/partials/mediopago_table_rows.html', {'medios_pago': medios.distinct()})

@login_required
def mediopago_modal(request, id=None):
    empresa_id = request.session.get('empresa_id')
    medio = get_object_or_404(MedioPago, id=id, empresa_id=empresa_id) if id else None
    
    if request.method == 'POST':
        form = MedioPagoForm(empresa_id, request.POST, instance=medio)
        if form.is_valid():
            nuevo_medio = form.save(commit=False)
            nuevo_medio.empresa_id = empresa_id
            nuevo_medio.save()
            response = HttpResponse()
            response['HX-Trigger'] = json.dumps({'reloadMediosPago': True, 'cerrarModal': True})
            response['HX-Reswap'] = 'none'
            return response
    else:
        form = MedioPagoForm(empresa_id, instance=medio)
        
    return render(request, 'configuracion/modals/mediopago_form.html', {'form': form, 'medio': medio})

@login_required
def eliminar_mediopago(request, id):
    empresa_id = request.session.get('empresa_id')
    if request.method == 'POST':
        medio = get_object_or_404(MedioPago, id=id, empresa_id=empresa_id)
        medio.delete()
        response = HttpResponse()
        response['HX-Trigger'] = json.dumps({'reloadMediosPago': True})
        return response
    return HttpResponse(status=400)

@login_required
def cuenta_bancaria_modal(request, id=None):
    empresa_id = request.session.get('empresa_id')
    cta_bc = get_object_or_404(CuentaBancaria.objects.select_related('cli_pro', 'cuenta_contable'), cta_bc_id=id, empresa_id=empresa_id) if id else None
    
    if request.method == 'POST':
        form = CuentaBancariaForm(empresa_id, request.POST, instance=cta_bc)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.pk:
                obj.creado_por = request.user
                obj.empresa_id = empresa_id
            obj.modificado_por = request.user
            obj.save()
            response = HttpResponse()
            response['HX-Trigger'] = json.dumps({'reloadCuentasBancarias': True, 'cerrarModal': True})
            response['HX-Reswap'] = 'none'
            return response
    else:
        form = CuentaBancariaForm(empresa_id, instance=cta_bc)
        
    banco_bcra = None
    if cta_bc and cta_bc.banco_id:
        from .models import Banco
        banco_bcra = Banco.objects.filter(pk=cta_bc.banco_id).first()

    return render(request, 'configuracion/modals/cuentabancaria_form.html', {
        'form': form,
        'cuenta_bancaria': cta_bc,
        'banco_bcra': banco_bcra
    })

@login_required
def buscar_cuentas_bancarias(request):
    q = request.GET.get('q', '')
    empresa_id = request.session.get('empresa_id')
    ctas = CuentaBancaria.objects.filter(empresa_id=empresa_id).select_related('cuenta_contable', 'cli_pro')
    if q:
        ctas = ctas.filter(banco__icontains=q)
    return render(request, 'configuracion/partials/cuentabancaria_table_rows.html', {'cuentas_bancarias': ctas})

@login_required
def eliminar_cuenta_bancaria(request, id):
    empresa_id = request.session.get('empresa_id')
    if request.method == 'POST':
        cta_bc = get_object_or_404(CuentaBancaria, cta_bc_id=id, empresa_id=empresa_id)
        cta_bc.delete()
        response = HttpResponse()
        response['HX-Trigger'] = json.dumps({'reloadCuentasBancarias': True})
        return response
    return HttpResponse(status=400)

@login_required
def buscar_cliente_proveedor(request, tipo):
    empresa_id = request.session.get('empresa_id')
    q = request.GET.get('q', '').strip()
    
    entidades = ClienteProveedor.objects.filter(empresa_id=empresa_id)
    if q:
        entidades = entidades.filter(Q(razon_social__icontains=q) | Q(cuit__icontains=q))
        
    return render(request, 'tesoreria/partials/cliente_proveedor_options.html', {'entidades': entidades})

@login_required
def buscador_clientes_recibo_modal(request):
    return render(request, 'tesoreria/modals/buscador_clientes_recibo.html')

def _adjuntar_nombres_de_cuentas(entidades, empresa_id):
    """Agrega a cada cli_pro el nombre visible de sus cuentas predeterminadas.

    `cta_pat` y `cta_res` son IntegerField con el pk de la cuenta (no son FK), así que hay que
    resolverlos a mano. Se hace en UNA sola consulta para toda la página de resultados.
    """
    from contable.models import Cuenta

    pks = {e.cta_pat for e in entidades if e.cta_pat} | {e.cta_res for e in entidades if e.cta_res}
    nombres = {}
    if pks:
        nombres = {
            c.pk: f"{c.jerarquia} - {c.cuenta}"
            for c in Cuenta.objects.filter(pk__in=pks, empresa_id=empresa_id)
        }

    for entidad in entidades:
        entidad.cta_pat_nombre = nombres.get(entidad.cta_pat, '')
        entidad.cta_res_nombre = nombres.get(entidad.cta_res, '')
    return entidades


@login_required
def lista_clientes_recibo_resultados(request):
    q = request.GET.get('q', '').strip()
    empresa_id = request.session.get('empresa_id')

    clientes = ClienteProveedor.objects.filter(empresa_id=empresa_id).annotate(
        saldo_pendiente=Coalesce(Sum('venta__saldo', filter=Q(venta__estado=0, venta__saldo__gt=0)), Decimal('0'))
    )
    if q:
        clientes = clientes.filter(Q(razon_social__icontains=q) | Q(cuit__icontains=q))

    return render(request, 'tesoreria/partials/clientes_recibo_search_results.html', {
        'clientes': _adjuntar_nombres_de_cuentas(list(clientes.order_by('razon_social')[:30]), empresa_id),
    })

@login_required
def buscador_cuentas_modal(request):
    """Modal de la lupa para elegir la cuenta de la imputación contable."""
    return render(request, 'tesoreria/modals/buscador_cuentas.html')


@login_required
def lista_cuentas_resultados(request):
    """Resultados de búsqueda de cuentas para el typeahead y para el modal.

    Solo cuentas IMPUTABLES de la empresa activa. Basta el primer dígito de la jerarquía para
    acotar al rubro (1 Activo, 4 Ingresos, etc.).
    """
    from contable.models import Cuenta

    q = request.GET.get('q', '').strip()
    empresa_id = request.session.get('empresa_id')

    cuentas = Cuenta.objects.filter(empresa_id=empresa_id, imputable=1)
    if q:
        cuentas = cuentas.filter(Q(jerarquia__icontains=q) | Q(cuenta__icontains=q))

    return render(request, 'tesoreria/partials/cuentas_search_results.html', {
        'cuentas': cuentas.order_by('jerarquia')[:30],
    })


@login_required
def lista_bancos_resultados(request):
    """Resultados de búsqueda de bancos para el typeahead."""
    from .models import Banco

    q = request.GET.get('q', '').strip()
    bancos = Banco.objects.all()
    if q:
        bancos = bancos.filter(Q(nombre__icontains=q) | Q(codigo_bcra__icontains=q))

    return render(request, 'tesoreria/partials/bancos_search_results.html', {
        'bancos': bancos.order_by('nombre')[:30],
    })


@login_required
def buscador_bancos_modal(request):
    """Modal de b├║squeda de entidades bancarias seg├║n cat├ílogo del BCRA."""
    return render(request, 'tesoreria/modals/buscador_bancos.html')


@login_required
def buscador_proveedores_op_modal(request):
    return render(request, 'tesoreria/modals/buscador_proveedores_op.html')

@login_required
def lista_proveedores_op_resultados(request):
    q = request.GET.get('q', '').strip()
    empresa_id = request.session.get('empresa_id')

    proveedores = ClienteProveedor.objects.filter(empresa_id=empresa_id).annotate(
        saldo_pendiente=Coalesce(Sum('compra__saldo', filter=Q(compra__saldo__gt=0)), Decimal('0'))
    )
    if q:
        proveedores = proveedores.filter(Q(razon_social__icontains=q) | Q(cuit__icontains=q))

    return render(request, 'tesoreria/partials/proveedores_op_search_results.html', {
        'proveedores': _adjuntar_nombres_de_cuentas(list(proveedores.order_by('razon_social')[:30]), empresa_id),
    })

@login_required
def buscador_valores_cartera_modal(request):
    return render(request, 'tesoreria/modals/buscador_valores_cartera_op.html')

@login_required
def lista_valores_cartera_resultados(request):
    q = request.GET.get('q', '').strip()
    
    # Sólo los que están en cartera (estado 'C') de la empresa activa. El filtro va contra el
    # campo propio `empresa`, no navegando hasta la caja donde se recibieron.
    valores = ValorTerceros.objects.filter(
        estado='C',
        empresa_id=request.session.get('empresa_id'),
    ).select_related('banco')
    if q:
        valores = valores.filter(Q(numero_cheque__icontains=q) | Q(nombre_firmante__icontains=q) | Q(cuit_firmante__icontains=q) | Q(banco__nombre__icontains=q))
        
    return render(request, 'tesoreria/partials/valores_cartera_search_results.html', {'valores': valores[:20]})


@login_required
def obtener_comprobantes_pendientes(request, tipo, id):
    empresa_id = request.session.get('empresa_id')
    
    from empresas.models import CotizacionMoneda
    cotiz = CotizacionMoneda.objects.filter(empresa_id=empresa_id).first()
    dolar_cobranza = cotiz.dolar_cobranza if cotiz else 1.0
    
    # `saldo != 0`, NO `saldo > 0` (Plan 035 §2, B3): las Notas de Crédito se graban con
    # importes negativos (`TipoComprobante.signo = -1`), igual que cualquier comprobante que
    # reste. Filtrarlas por saldo positivo las dejaba fuera del selector, de modo que nunca se
    # podían compensar y la factura quedaba eternamente con saldo impago.
    # Lo mismo vale para los certificados de retención/percepción que emite la contraparte,
    # que se cargan como Compra/Venta con su propio tipo de comprobante.
    if tipo == 'cliente':
        comprobantes = Venta.objects.filter(
            empresa_id=empresa_id, cliente_id=id, estado=0
        ).exclude(saldo=0).select_related('tipo').order_by('fecha')
        for c in comprobantes:
            if c.moneda == 'DOL':
                c.saldo_pesificado = round(c.saldo * dolar_cobranza, 2)
                c.total_pesificado = round(c.total * dolar_cobranza, 2)
            else:
                c.saldo_pesificado = c.saldo
                c.total_pesificado = c.total
        template = 'tesoreria/partials/comprobantes_pendientes_venta.html'
    else:
        comprobantes = Compra.objects.filter(
            empresa_id=empresa_id, proveedor_id=id
        ).exclude(saldo=0).select_related('tipo').order_by('fecha')
        # Cada compra en dólares se pesifica a SU PROPIA cotización (la de emisión), no a un
        # dólar global. Así el pago la cancela a cotización de origen, sin diferencia de cambio.
        for c in comprobantes:
            if c.moneda == 'DOL':
                cot = c.cotizacion or Decimal('1')
                c.cotiz_factura = cot
                c.saldo_pesificado = round(c.saldo * cot, 2)
                c.total_pesificado = round(c.total * cot, 2)
            else:
                c.cotiz_factura = Decimal('1')
                c.saldo_pesificado = c.saldo
                c.total_pesificado = c.total
            # El operador tipea magnitudes: el tope del input es el valor absoluto del saldo,
            # y el signo lo aporta el propio comprobante.
            c.saldo_pesificado_abs = abs(c.saldo_pesificado)
            # Régimen RG 830 que corresponde a este comprobante, deducido de la cuenta con la
            # que se imputó. Viaja al front para sugerir la retención sin que el operador tenga
            # que recordar qué régimen aplica a cada gasto.
            c.regimen_rg830 = regimen_rg830_de_compra(c) or ''
        template = 'tesoreria/partials/comprobantes_pendientes_compra.html'

    return render(request, template, {
        'comprobantes': comprobantes,
        'dolar_cobranza': dolar_cobranza
    })

@login_required
@transaction.atomic
def procesar_recibo(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            empresa_id = request.session.get('empresa_id')
            cliente_id = data.get('cliente_id')
            fecha = data.get('fecha')
            punto = data.get('punto', 1)
            observaciones = data.get('observaciones', '')
            tipo = data.get('tipo', 'C')
            condic = int(data.get('condic', 1))
            cotizacion_aplicada = Decimal(str(data.get('cotizacion', 1.0)))
            
            aplicaciones = data.get('aplicaciones', [])
            imputaciones = data.get('imputaciones', [])
            valores = data.get('valores', [])
            
            total = Decimal('0')
            for v in valores:
                if v.get('categoria') == 'EFE-USD':
                    total += Decimal(str(v['importe'])) * cotizacion_aplicada
                else:
                    total += Decimal(str(v['importe']))
            
            # DÓNDE CAE LA PLATA, que es lo único que distingue los dos recibos (Plan 077 §F).
            if data.get('origen') == 'MOSTRADOR':
                # Lo cobra el cajero y lo tiene que rendir: entra en SU caja, y por eso el
                # asiento va a debitar `cta_caja_mostrador`. Si su caja está cerrada, no hay
                # dónde meter la plata: se rechaza en vez de desviarla a Tesorería.
                caja = _caja_operable(request)
                sesion_caja = CajaSesion.objects.filter(
                    caja=caja, usuario=request.user, estado='A').first()
                if not sesion_caja:
                    raise Exception(
                        "No tenés una caja mostrador abierta: abrila antes de emitir el recibo.")
            else:
                # Caja de TESORERÍA de la sucursal: es por sucursal (no por cajero) y siempre hay una
                # activa. Si no existe se abre automáticamente arrastrando el cierre anterior, para que
                # el tesorero nunca quede bloqueado al querer registrar una cobranza.
                from tesoreria.services.caja_diaria import get_o_abrir_caja
                _, sesion_caja = get_o_abrir_caja(empresa_id, data.get('sucursal_id'), request.user)

            recibo = Recibo(
                empresa_id=empresa_id,
                sucursal_id=data.get('sucursal_id'),
                ejercicio_id=request.session.get('ejercicio_id'),
                sesion_caja=sesion_caja,
                cliente_id=cliente_id,
                fecha=fecha,
                punto=punto,
                tipo=tipo,
                total=total,
                condic=condic,
                observaciones=observaciones,
                creado_por=request.user,
                modificado_por=request.user
            )
            recibo.save()
            
            from tesoreria.models import ReciboImputacion
            for imp in imputaciones:
                ReciboImputacion.objects.create(
                    recibo=recibo,
                    cuenta_contable_id=imp['cuenta_contable_id'],
                    importe=Decimal(str(imp['importe'])),
                    leyenda=imp.get('leyenda', '')
                )
            
            for app in aplicaciones:
                venta = Venta.objects.select_for_update().get(ventas_id=app['id'], empresa_id=empresa_id)
                importe_aplicado_pesos = Decimal(str(app['importe']))

                if venta.moneda == 'DOL':
                    importe_aplicado = round(importe_aplicado_pesos / cotizacion_aplicada, 2)
                else:
                    importe_aplicado = importe_aplicado_pesos

                # El signo lo pone el servidor según el comprobante (NC de venta = negativa).
                importe_aplicado = _normalizar_aplicacion(venta, importe_aplicado, f"Venta {venta.numero}")
                if importe_aplicado == 0:
                    continue
                if importe_aplicado < 0:
                    importe_aplicado_pesos = -abs(importe_aplicado_pesos)

                # La aplicación se guarda en la MONEDA DEL COMPROBANTE, que es la unidad en la
                # que vive su saldo. Así el saldo se puede derivar sumando aplicaciones sin
                # arrastrar la cotización de cada cobranza.
                ReciboAplicacion.objects.create(
                    recibo=recibo,
                    venta=venta,
                    importe=importe_aplicado,
                    importe_pesos=importe_aplicado_pesos
                )

                # El saldo se DERIVA de las aplicaciones, nunca se decrementa (Plan 035 §1.3).
                recalcular_saldo_venta(venta.pk)
            
            mov_caja = MovimientoCaja.objects.create(
                sesion=sesion_caja,
                empresa_id=empresa_id,
                # Fecha DEL RECIBO, no la de carga: es la que usa el Estado de Origen y
                # Aplicación de Fondos para el rango desde/hasta (Plan 049).
                fecha=recibo.fecha,
                tipo='I',
                importe=total,
                concepto=f"Cobranza Recibo {recibo.numero}",
                condic=condic,
                recibo=recibo,
                cli_pro=recibo.cliente,
            )
            
            for val in valores:
                cat = val.get('categoria')
                importe_base = Decimal(str(val['importe']))
                
                medio_pago_id = val.get('medio_pago_id')
                importe_pesos = importe_base
                importe_dolares = Decimal('0')
                cotizacion_val = Decimal('1.0')
                
                if cat == 'EFE-ARS':
                    # Búsqueda precisa por código específico EFE-ARS, con fallback a cualquier caja en efectivo (EFE)
                    mp = MedioPago.objects.filter(empresa_id=empresa_id, codigo='EFE-ARS').first() or MedioPago.objects.filter(empresa_id=empresa_id, categoria='EFE').first()
                    medio_pago_id = mp.id if mp else None
                elif cat == 'EFE-USD':
                    # Búsqueda precisa por código específico EFE-USD, con fallback a cualquier caja en efectivo (EFE)
                    mp = MedioPago.objects.filter(empresa_id=empresa_id, codigo='EFE-USD').first() or MedioPago.objects.filter(empresa_id=empresa_id, categoria='EFE').first()
                    medio_pago_id = mp.id if mp else None
                    importe_dolares = importe_base
                    cotizacion_val = cotizacion_aplicada
                    importe_pesos = importe_base * cotizacion_aplicada
                elif cat == 'TRA':
                    # Búsqueda precisa por código TRA-BCO, con fallback a categoría TRA
                    mp = MedioPago.objects.filter(empresa_id=empresa_id, codigo='TRA-BCO').first() or MedioPago.objects.filter(empresa_id=empresa_id, categoria='TRA').first()
                    medio_pago_id = mp.id if mp else None
                elif cat == 'CHQ':
                    # Búsqueda precisa por código CHQ-TER, con fallback a categoría CHQ
                    mp = MedioPago.objects.filter(empresa_id=empresa_id, codigo='CHQ-TER').first() or MedioPago.objects.filter(empresa_id=empresa_id, categoria='CHQ').first()
                    medio_pago_id = mp.id if mp else None
                
                # 1. Crear el Detalle
                if not medio_pago_id:
                    raise Exception(f"No se encontró MedioPago configurado para la categoría {cat}")
                    
                detalle = MovimientoCajaDetalle.objects.create(
                    movimiento_caja=mov_caja,
                    medio_pago_id=medio_pago_id,
                    importe=importe_pesos,
                    importe_moneda_extranjera=importe_dolares,
                    cotizacion=cotizacion_val
                )
                
                # 2. Crear las entidades satélites. Se pueblan con datos PROPIOS (empresa,
                #    importe, fechas del comprobante): antes había que deducirlos navegando
                #    hasta el movimiento de caja, y el importe del cheque ni siquiera existía.
                if cat == 'CHQ':
                    ValorTerceros.objects.create(
                        empresa_id=empresa_id,
                        movimiento_detalle=detalle,
                        recibo=recibo,
                        banco_id=val.get('banco_id'),
                        numero_cheque=val.get('numero_comprobante', ''),
                        importe=importe_pesos,
                        fecha_emision=recibo.fecha,
                        fecha_vencimiento=val.get('fecha_vencimiento') if val.get('fecha_vencimiento') else recibo.fecha,
                        cuit_firmante=val.get('cuit_emisor', ''),
                        nombre_firmante=val.get('titular_emisor', ''),
                        # Sin sucursal el cheque quedaba invisible para el retiro y el cierre
                        # de caja, que filtran por ella.
                        sucursal_id=recibo.sucursal_id,
                        fecha_recepcion=recibo.fecha,
                        estado='C'
                    )
                elif cat == 'TRA':
                    cuenta_id = val.get('cuenta_bancaria_id')
                    if not cuenta_id:
                        raise Exception("Falta Cuenta Bancaria para la Transferencia.")
                    _validar_cuenta_bancaria(cuenta_id, empresa_id)
                    TransaccionBancaria.objects.create(
                        empresa_id=empresa_id,
                        movimiento_detalle=detalle,
                        cuenta_bancaria_id=cuenta_id,
                        numero_operacion=val.get('numero_comprobante', ''),
                        importe=importe_pesos,
                        cuit_contraparte=val.get('cuit_origen', ''),
                        fecha_operacion=recibo.fecha,
                        tipo_transaccion='TR',
                        # Una transferencia recibida ya está acreditada en el banco.
                        estado='D'
                    )

            # Registración contable. Va al final, cuando los detalles del movimiento de caja ya
            # existen: el DEBE del asiento se arma leyendo esos medios de cobro.
            from contable.services.contabilizacion import contabilizar_recibo
            asiento = contabilizar_recibo(recibo)

            # Vínculo contable del movimiento de fondos (Plan 049). Va acá, después de
            # contabilizar, porque el asiento recién existe ahora.
            from tesoreria.services.imputacion import estampar_asiento
            estampar_asiento(mov_caja, asiento)

            # Dato informativo para auditoría: con qué asiento entraron estos valores.
            if asiento:
                ValorTerceros.objects.filter(recibo=recibo).update(asiento_recepcion_id=asiento.asiento_id)
                TransaccionBancaria.objects.filter(
                    movimiento_detalle__movimiento_caja=mov_caja
                ).update(asiento_id=asiento.asiento_id)

            return HttpResponse(json.dumps({
                'status': 'success',
                'recibo_id': recibo.numero,
                'asiento_id': asiento.asiento_id if asiento else None,
            }), content_type="application/json")
        except Exception as e:
            # Asegura la reversión total de la transacción en la BD si ocurre cualquier error durante el proceso
            transaction.set_rollback(True)
            import traceback
            traceback.print_exc()
            return HttpResponse(json.dumps({'status': 'error', 'message': str(e)}), status=400, content_type="application/json")
    return HttpResponse(status=405)

@login_required
@transaction.atomic
def procesar_orden_pago(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            empresa_id = request.session.get('empresa_id')
            proveedor_id = data.get('proveedor_id')
            fecha = data.get('fecha')
            punto = data.get('punto', 1)
            observaciones = data.get('observaciones', '')
            condic = int(data.get('condic', 1))
            tipo = data.get('tipo', 'P')
            cotizacion_aplicada = Decimal(str(data.get('cotizacion', 1.0)))
            
            aplicaciones = data.get('aplicaciones', [])
            imputaciones = data.get('imputaciones', [])
            valores = data.get('valores', [])
            
            _validar_entidad(proveedor_id, empresa_id)

            # Cheques de terceros a entregar: se bloquean ANTES de calcular nada y se toma su
            # importe REAL de la base (Plan 035 §5). El navegador manda el id del cheque, no su
            # valor: sin este bloqueo dos órdenes simultáneas podían entregar el mismo cheque, y
            # sin leer el importe de la base se podía entregar uno de $100 valuándolo en $1.000.000.
            valores_cartera_tomados = {}
            for val in valores:
                if val.get('categoria') != 'CHQ-TER':
                    continue
                valor_id = val.get('id')
                try:
                    vt = ValorTerceros.objects.select_for_update().get(
                        pk=valor_id, estado='C', empresa_id=empresa_id)
                except ValorTerceros.DoesNotExist:
                    raise Exception(
                        f"El valor {valor_id} no está disponible en cartera "
                        f"(puede haber sido entregado o depositado en otra operación)."
                    )
                # El importe manda la base, no el payload.
                val['importe'] = vt.importe
                valores_cartera_tomados[valor_id] = vt

            total = Decimal('0')
            for v in valores:
                if v.get('categoria') == 'EFE-USD':
                    total += Decimal(str(v['importe'])) * cotizacion_aplicada
                else:
                    total += Decimal(str(v['importe']))

            # Misma caja de tesorería que usan los recibos (una por sucursal, siempre activa).
            from tesoreria.services.caja_diaria import get_o_abrir_caja
            _, sesion_caja = get_o_abrir_caja(empresa_id, data.get('sucursal_id'), request.user)

            op = OrdenPago(
                empresa_id=empresa_id,
                sucursal_id=data.get('sucursal_id'),
                ejercicio_id=request.session.get('ejercicio_id'),
                sesion_caja=sesion_caja,
                proveedor_id=proveedor_id,
                fecha=fecha,
                punto=punto,
                total=total,
                condic=condic,
                tipo=tipo,
                observaciones=observaciones,
                creado_por=request.user,
                modificado_por=request.user
            )
            op.save()
            
            if tipo == 'P':
                for app in aplicaciones:
                    compra = Compra.objects.select_for_update().get(compras_id=app['id'], empresa_id=empresa_id)
                    # El importe aplicado viene en PESOS (la factura USD ya se pesificó a SU cotización
                    # de origen en el selector). Se lleva a la moneda de la factura dividiendo por esa
                    # misma cotización de ORIGEN, no por la de la OP → cancela sin diferencia de cambio.
                    importe_aplicado_pesos = Decimal(str(app['importe']))
                    if getattr(compra, 'moneda', 'PES') == 'DOL':
                        cotiz_factura = Decimal(str(compra.cotizacion or 1))
                        importe_aplicado = round(importe_aplicado_pesos / cotiz_factura, 2)
                    else:
                        importe_aplicado = importe_aplicado_pesos

                    # El signo lo pone el servidor según el comprobante: una Nota de Crédito
                    # tiene saldo negativo y su aplicación resta del neto a pagar.
                    etiqueta = f"Comprobante {compra.punto:04d}-{compra.numero}"
                    importe_aplicado = _normalizar_aplicacion(compra, importe_aplicado, etiqueta)
                    if importe_aplicado == 0:
                        continue
                    if importe_aplicado < 0:
                        importe_aplicado_pesos = -abs(importe_aplicado_pesos)

                    OrdenPagoAplicacion.objects.create(
                        orden_pago=op,
                        compra=compra,
                        importe=importe_aplicado,
                        importe_pesos=importe_aplicado_pesos
                    )

                    # El saldo se DERIVA de las aplicaciones, nunca se decrementa (Plan 035 §1.3).
                    recalcular_saldo_compra(compra.pk)
            else:
                from tesoreria.models import OrdenPagoImputacion
                for imp in imputaciones:
                    OrdenPagoImputacion.objects.create(
                        orden_pago=op,
                        cuenta_contable_id=_validar_cuenta_contable(imp.get('cuenta_contable_id'), empresa_id),
                        importe=Decimal(str(imp['importe'])),
                        leyenda=imp.get('leyenda', '')
                    )

            # Movimiento de Caja (Egreso)
            mov_caja = MovimientoCaja.objects.create(
                sesion=sesion_caja,
                empresa_id=empresa_id,
                # Fecha DE LA ORDEN DE PAGO, no la de carga (Plan 049).
                fecha=op.fecha,
                tipo='E',
                importe=total,
                concepto=f"Orden de Pago {op.numero}",
                condic=condic,
                orden_pago=op,
                cli_pro=op.proveedor,
                creado_por=request.user
            )

            for val in valores:
                cat = val.get('categoria')
                importe_base = Decimal(str(val['importe']))
                medio_pago_id = val.get('medio_pago_id')
                importe_pesos = importe_base
                importe_dolares = Decimal('0')
                cotizacion_val = Decimal('1.0')
                
                if cat == 'EFE-ARS':
                    # Búsqueda precisa por código específico EFE-ARS, con fallback a categoría EFE
                    mp = MedioPago.objects.filter(empresa_id=empresa_id, codigo='EFE-ARS').first() or MedioPago.objects.filter(empresa_id=empresa_id, categoria='EFE').first()
                    medio_pago_id = mp.id if mp else None
                elif cat == 'EFE-USD':
                    # Búsqueda precisa por código específico EFE-USD, con fallback a categoría EFE
                    mp = MedioPago.objects.filter(empresa_id=empresa_id, codigo='EFE-USD').first() or MedioPago.objects.filter(empresa_id=empresa_id, categoria='EFE').first()
                    medio_pago_id = mp.id if mp else None
                    importe_pesos = importe_base * cotizacion_aplicada
                    importe_dolares = importe_base
                    cotizacion_val = cotizacion_aplicada
                elif cat == 'TRA':
                    # Búsqueda precisa por código TRA-BCO, con fallback a categoría TRA
                    mp = MedioPago.objects.filter(empresa_id=empresa_id, codigo='TRA-BCO').first() or MedioPago.objects.filter(empresa_id=empresa_id, categoria='TRA').first()
                    medio_pago_id = mp.id if mp else None
                elif cat == 'CP' or cat == 'CHQ-TER':
                    # Búsqueda precisa por código CHQ-TER, con fallback a categoría CHQ
                    mp = MedioPago.objects.filter(empresa_id=empresa_id, codigo='CHQ-TER').first() or MedioPago.objects.filter(empresa_id=empresa_id, categoria='CHQ').first()
                    medio_pago_id = mp.id if mp else None
                    
                if not medio_pago_id:
                    raise Exception(f"No se encontró un Medio de Pago válido configurado para la categoría {cat}.")
                
                # Detalle
                detalle = MovimientoCajaDetalle.objects.create(
                    movimiento_caja=mov_caja,
                    medio_pago_id=medio_pago_id,
                    importe=importe_pesos,
                    importe_moneda_extranjera=importe_dolares,
                    cotizacion=cotizacion_val
                )
                
                if cat == 'CHQ-TER':
                    # El cheque ya está bloqueado y su importe verificado más arriba.
                    vt = valores_cartera_tomados[val.get('id')]
                    vt.estado = 'E'
                    vt.orden_pago = op
                    vt.fecha_entrega = op.fecha
                    vt.save(update_fields=['estado', 'orden_pago', 'fecha_entrega'])
                elif cat == 'CP':
                    # Cheque propio: acredita el pasivo "Cheques Emitidos a Pagar" de la cuenta
                    # bancaria; el banco lo debitará después (tramo 2, ver §1.6 del plan).
                    cuenta_id = _validar_cuenta_bancaria(val.get('cuenta_bancaria_id'), empresa_id)
                    vto = val.get('fecha_vencimiento')
                    TransaccionBancaria.objects.create(
                        empresa_id=empresa_id,
                        movimiento_detalle=detalle,
                        cuenta_bancaria_id=cuenta_id,
                        numero_operacion=val.get('numero_comprobante', ''),
                        importe=importe_pesos,
                        cuit_contraparte=op.proveedor.cuit or '',
                        fecha_operacion=op.fecha,
                        tipo_transaccion='CP',
                        fecha_vencimiento=vto if vto else None,
                        estado='E'
                    )
                elif cat == 'TRA':
                    cuenta_id = _validar_cuenta_bancaria(val.get('cuenta_bancaria_id'), empresa_id)
                    nro = val.get('numero_comprobante', '')
                    # El control de duplicados va acotado a la empresa: dos empresas distintas
                    # pueden tener el mismo número de operación sin que sea un error.
                    if nro and TransaccionBancaria.objects.filter(
                        numero_operacion=nro, cuenta_bancaria_id=cuenta_id, empresa_id=empresa_id
                    ).exists():
                        raise Exception(f"El comprobante de transferencia {nro} ya fue ingresado anteriormente.")
                    TransaccionBancaria.objects.create(
                        empresa_id=empresa_id,
                        movimiento_detalle=detalle,
                        cuenta_bancaria_id=cuenta_id,
                        numero_operacion=nro,
                        importe=importe_pesos,
                        cuit_contraparte=val.get('cuit_destino', '') or (op.proveedor.cuit or ''),
                        fecha_operacion=op.fecha,
                        tipo_transaccion='TE',
                        # La transferencia sale del banco en el acto: nace conciliada.
                        estado='D'
                    )

            # Registración contable, al final: el HABER se arma leyendo los medios de pago que
            # acaban de quedar registrados como detalles del movimiento de caja.
            from contable.services.contabilizacion import contabilizar_orden_pago
            asiento = contabilizar_orden_pago(op)

            # Vínculo contable del movimiento de fondos (Plan 049).
            from tesoreria.services.imputacion import estampar_asiento
            estampar_asiento(mov_caja, asiento)

            # Certificados de retención practicada (RG 830 y demás). Los datos se capturaban en
            # pantalla y se descartaban: sin esta tabla la DDJJ de SICORE es imposible de armar.
            # El régimen se deduce de las facturas aplicadas (cta_imputacion -> Cuenta.rg_830).
            from contable.services.retenciones import registrar_retenciones_practicadas
            registrar_retenciones_practicadas(
                op,
                [v for v in valores if v.get('categoria') == 'RET'],
                asiento_id=asiento.asiento_id if asiento else None,
            )

            # Se estampa el asiento en los satélites recién ahora, cuando ya existe. Es un dato
            # INFORMATIVO para auditoría y para el papel de trabajo: el vínculo estructural es
            # la FK al comprobante, porque al recontabilizar el asiento cambia de número.
            if asiento:
                TransaccionBancaria.objects.filter(
                    movimiento_detalle__movimiento_caja=mov_caja
                ).update(asiento_id=asiento.asiento_id)
                if valores_cartera_tomados:
                    ValorTerceros.objects.filter(
                        pk__in=list(valores_cartera_tomados.keys())
                    ).update(asiento_entrega_id=asiento.asiento_id)

            return HttpResponse(json.dumps({
                'status': 'success',
                'op_id': op.numero,
                'asiento_id': asiento.asiento_id if asiento else None,
            }), content_type="application/json")
        except Exception as e:
            # Asegura la reversión total de la transacción en la BD si ocurre cualquier error durante el proceso
            transaction.set_rollback(True)
            import traceback
            traceback.print_exc()
            return HttpResponse(json.dumps({'status': 'error', 'message': str(e)}), status=400, content_type="application/json")
    return HttpResponse(status=405)

from django.utils import timezone
from tesoreria.models import RetiroCaja, RetiroCajaValor, RetiroCajaTarjeta, RetiroCajaAsiento
from tesoreria.models import CajaSesion, Caja, CobroTarjeta, MovimientoCaja
from contable.models import Asiento, AsientoLinea, ParametrosContables
from facturacion.models import Preventa

from django.views.decorators.cache import never_cache

@login_required
@never_cache
def caja_mostrador_cobrar_modal(request, preventa_id):
    empresa_id = request.session.get('empresa_id')
    sucursal_id = request.session.get('sucursal_id')
    preventa = get_object_or_404(Preventa, preventa_id=preventa_id, empresa_id=empresa_id)
    
    # Detección de armas trazables (SIGIMAC / subprod=True)
    item_subprod = preventa.items.filter(producto__subprod=True).first()
    es_reserva = bool(item_subprod)
    producto_reservado = item_subprod.producto if item_subprod else None

    # Cotizacion
    from empresas.models import CotizacionMoneda
    from tesoreria.models import Banco, Tarjeta
    cotiz = CotizacionMoneda.objects.filter(empresa_id=empresa_id).first()
    dolar_cobranza = cotiz.dolar_cobranza if cotiz else 1.0
    
    cuentas_bancarias = CuentaBancaria.objects.filter(empresa_id=empresa_id)
    bancos = Banco.objects.all()
    tarjetas = Tarjeta.objects.all()
    
    # Puede pagar en cta cte si cliente tipo_entidad=1 y NO es el cliente generico Consumidor Final (codigo_id=1)
    permite_ctacte = preventa.cliente.tipo_entidad == 1 and preventa.cliente.codigo_id != 1
    
    context = {
        'preventa': preventa,
        'es_reserva': es_reserva,
        'producto_reservado': producto_reservado,
        'dolar_cobranza': dolar_cobranza,
        'cuentas_bancarias': cuentas_bancarias,
        'bancos': bancos,
        'tarjetas': tarjetas,
        'permite_ctacte': permite_ctacte
    }
    return render(request, 'tesoreria/modals/caja_mostrador_cobrar.html', context)

@transaction.atomic
def _guardar_cobro_preventa_transaccional(
    request, preventa_id, empresa_id, sucursal_id, sesion_caja,
    efectivo, dolares, ctacte, saldo_a_favor,
    tarjetas, transferencias, valores,
    total_tarjetas, total_transferencias, total_valores, total_ingresado,
    condic, punto_venta_num, tipo_cbte, res_afip
):
    preventa = Preventa.objects.select_for_update().get(preventa_id=preventa_id, empresa_id=empresa_id)
    last_venta = Venta.objects.filter(empresa_id=empresa_id, sucursal_id=sucursal_id, punto=punto_venta_num).select_for_update().order_by('-numero').first()
    numero_venta = (last_venta.numero + 1) if last_venta and last_venta.numero else 1
    if condic == 1 and res_afip and res_afip.get('exito'):
        numero_venta = res_afip.get('numero_comprobante', numero_venta)
         
    venta = Venta(
        fecha=timezone.localdate(),
        punto=punto_venta_num,
        numero=numero_venta,
        tipo=tipo_cbte,
        condic=condic,
        cae=res_afip.get('cae') if res_afip else None,
        vto_cae=res_afip.get('vto_cae') if res_afip else None,
        cod_qr=res_afip.get('cod_qr') if res_afip else None,
        cliente=preventa.cliente,
        cliente_razon_social=preventa.cliente_razon_social,
        cliente_cuit=preventa.cliente_cuit,
        cliente_domicilio=preventa.cliente_domicilio,
        neto=preventa.neto,
        total=preventa.total,
        cobrado=preventa.total - ctacte,
        saldo=ctacte,
        efectivo=efectivo,
        dolares=dolares,
        tarjeta=total_tarjetas,
        transferencia=total_transferencias,
        valores=total_valores,
        usuario=request.user,
        cajero=request.user,
        vendedor=preventa.vendedor,
        sucursal_id=sucursal_id,
        empresa_id=empresa_id,
        estado=0
    )
    venta._no_contabilizar = True
    venta.save()
    _crear_asientos_y_movimientos_cobro(
        request, venta, preventa, empresa_id, sucursal_id, sesion_caja,
        efectivo, dolares, ctacte, saldo_a_favor,
        tarjetas, transferencias, valores,
        total_tarjetas, total_transferencias, total_valores, total_ingresado
    )
    return HttpResponse(json.dumps({'status': 'success'}), content_type="application/json")

@transaction.atomic
def _guardar_reserva_preventa_transaccional(
    request, preventa, producto_reservado, empresa_id, sucursal_id, sesion_caja,
    efectivo, dolares, tarjetas, transferencias, valores, total_ingresado
):
    """
    Registra el cobro de una Reserva de Arma (SIGIMAC).
    Emite un Recibo oficial por el importe señado, registra los fondos en la sesión de caja mostrador,
    crea el registro de control ReservaArma en estado PENDIENTE y marca la Preventa como cobrada.
    """
    from verticalidades.armeria.models import ReservaArma
    from contable.models import ParametrosContables, Cuenta
    from tesoreria.models import (
        Recibo, ReciboImputacion, MovimientoCaja, CobroTarjeta, 
        TransaccionBancaria, ValorTerceros, Tarjeta, CuentaBancaria, Banco
    )
    
    # 1. Obtener correlativo de Recibo
    last_rc = Recibo.objects.filter(empresa_id=empresa_id, sucursal_id=sucursal_id).select_for_update().order_by('-numero').first()
    nro_recibo = (last_rc.numero + 1) if (last_rc and last_rc.numero) else 1

    pv_caja = getattr(sesion_caja.caja, 'punto_venta', None)
    punto_rc = pv_caja.numero if pv_caja else 1

    # 2. Crear Recibo por Reserva
    recibo = Recibo(
        empresa_id=empresa_id,
        sucursal_id=sucursal_id,
        ejercicio_id=request.session.get('ejercicio_id'),
        sesion_caja=sesion_caja,
        cliente=preventa.cliente,
        fecha=timezone.localdate(),
        punto=punto_rc,
        numero=nro_recibo,
        tipo='C',
        total=total_ingresado,
        condic=1,
        observaciones=f"Reserva Preventa #{preventa.preventa_id} - {producto_reservado.detalle} (SIGIMAC)",
        creado_por=request.user,
        modificado_por=request.user
    )
    recibo.save()

    # 3. Imputación contable a la cuenta corriente del cliente
    param_c = ParametrosContables.objects.filter(empresa_id=empresa_id).first()
    cta_imputar = None
    if preventa.cliente.cta_pat:
        cta_imputar = Cuenta.objects.filter(empresa_id=empresa_id, codigo=preventa.cliente.cta_pat).first()
    if not cta_imputar and param_c:
        cta_imputar = param_c.cta_clientes_default

    if cta_imputar:
        ReciboImputacion.objects.create(
            recibo=recibo,
            cuenta_contable=cta_imputar,
            importe=total_ingresado,
            leyenda=f"Reserva SIGIMAC Prev #{preventa.preventa_id}"
        )

    concepto_cobro = f"Cobranza Reserva Recibo #{recibo.numero} (Prev #{preventa.preventa_id})"

    # 4. Movimientos en Caja Mostrador
    mov_caja = MovimientoCaja.objects.create(
        sesion=sesion_caja,
        empresa_id=empresa_id,
        fecha=recibo.fecha,
        tipo='I',
        importe=total_ingresado,
        concepto=f"Cobranza Reserva Recibo {recibo.numero}",
        condic=1,
        recibo=recibo,
        cli_pro=preventa.cliente,
    )

    # Efectivo ARS
    if efectivo > 0:
        mp_efe = MedioPago.objects.filter(empresa_id=empresa_id, codigo='EFE-ARS').first() or MedioPago.objects.filter(empresa_id=empresa_id, categoria='EFE').first()
        if mp_efe:
            MovimientoCajaDetalle.objects.create(
                movimiento_caja=mov_caja,
                medio_pago=mp_efe,
                importe=efectivo,
                importe_moneda_extranjera=0,
                cotizacion=1.0
            )

    # Efectivo USD
    if dolares > 0:
        mp_efe = MedioPago.objects.filter(empresa_id=empresa_id, codigo='EFE-USD').first() or MedioPago.objects.filter(empresa_id=empresa_id, categoria='EFE').first()
        from empresas.models import CotizacionMoneda
        cotiz = CotizacionMoneda.objects.filter(empresa_id=empresa_id).first()
        dolar_cobranza = cotiz.dolar_cobranza if cotiz else Decimal('1.0')
        if mp_efe:
            MovimientoCajaDetalle.objects.create(
                movimiento_caja=mov_caja,
                medio_pago=mp_efe,
                importe=dolares * Decimal(str(dolar_cobranza)),
                importe_moneda_extranjera=dolares,
                cotizacion=dolar_cobranza
            )

    # Tarjetas
    if tarjetas:
        mp_tarjeta = MedioPago.objects.filter(empresa_id=empresa_id, categoria='TAR').first()
        for tarj in tarjetas:
            t_imp = Decimal(str(tarj.get('importe', 0) or 0))
            if t_imp > 0 and mp_tarjeta:
                detalle = MovimientoCajaDetalle.objects.create(
                    movimiento_caja=mov_caja,
                    medio_pago=mp_tarjeta,
                    importe=t_imp,
                    importe_moneda_extranjera=0,
                    cotizacion=1.0
                )
                CobroTarjeta.objects.create(
                    movimiento_detalle=detalle,
                    tarjeta_id=tarj.get('tarjeta_id'),
                    lote=tarj.get('lote', ''),
                    cupon=tarj.get('cupon', ''),
                    cuotas=1,
                    sucursal_id=sucursal_id
                )

    # Transferencias
    if transferencias:
        mp_tra = MedioPago.objects.filter(empresa_id=empresa_id, categoria='TRA').first()
        for transf in transferencias:
            tr_imp = Decimal(str(transf.get('importe', 0) or 0))
            if tr_imp > 0 and mp_tra:
                cta_bc_id = transf.get('cuenta_id') or transf.get('id')
                detalle = MovimientoCajaDetalle.objects.create(
                    movimiento_caja=mov_caja,
                    medio_pago=mp_tra,
                    importe=tr_imp,
                    importe_moneda_extranjera=0,
                    cotizacion=1.0
                )
                TransaccionBancaria.objects.create(
                    empresa_id=empresa_id,
                    movimiento_detalle=detalle,
                    cuenta_bancaria_id=cta_bc_id,
                    numero_operacion='',
                    importe=tr_imp,
                    cuit_contraparte=transf.get('cuit', ''),
                    fecha_operacion=recibo.fecha,
                    tipo_transaccion='TR',
                    estado='D'
                )

    # Valores (Cheques)
    if valores:
        mp_chq = MedioPago.objects.filter(empresa_id=empresa_id, categoria='CHQ').first()
        for ch in valores:
            ch_imp = Decimal(str(ch.get('importe', 0) or 0))
            if ch_imp > 0 and mp_chq:
                detalle = MovimientoCajaDetalle.objects.create(
                    movimiento_caja=mov_caja,
                    medio_pago=mp_chq,
                    importe=ch_imp,
                    importe_moneda_extranjera=0,
                    cotizacion=1.0
                )
                ValorTerceros.objects.create(
                    empresa_id=empresa_id,
                    movimiento_detalle=detalle,
                    recibo=recibo,
                    banco_id=ch.get('banco_id'),
                    numero_cheque=ch.get('numero', ''),
                    importe=ch_imp,
                    fecha_emision=recibo.fecha,
                    fecha_vencimiento=ch.get('vto') if ch.get('vto') else recibo.fecha,
                    cuit_firmante=ch.get('cuit', ''),
                    nombre_firmante=ch.get('titular', ''),
                    sucursal_id=sucursal_id,
                    fecha_recepcion=recibo.fecha,
                    estado='C'
                )

    # Contabilización del Recibo
    from contable.services.contabilizacion import contabilizar_recibo
    asiento = contabilizar_recibo(recibo)
    if asiento:
        from tesoreria.services.imputacion import estampar_asiento
        estampar_asiento(mov_caja, asiento)

    # 5. Crear o actualizar registro ReservaArma
    ReservaArma.objects.update_or_create(
        preventa=preventa,
        defaults={
            'empresa_id': empresa_id,
            'sucursal_id': sucursal_id,
            'cliente': preventa.cliente,
            'producto': producto_reservado,
            'recibo_reserva': recibo,
            'monto_reservado': total_ingresado,
            'monto_total': preventa.total,
            'estado': 'PENDIENTE'
        }
    )

    # 6. Marcar la preventa como cobrada/procesada (estado 3)
    preventa.estado = 3
    preventa.save(update_fields=['estado'])

    return HttpResponse(json.dumps({'status': 'success', 'message': f'Reserva registrada exitosamente. Recibo #{recibo.numero} emitido.'}), content_type="application/json")

@login_required
def caja_mostrador_procesar_cobro(request, preventa_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            empresa_id = request.session.get('empresa_id')
            sucursal_id = request.session.get('sucursal_id')
            
            preventa = Preventa.objects.get(preventa_id=preventa_id, empresa_id=empresa_id)
            caja = Caja.objects.filter(empresa_id=empresa_id, sucursal_id=sucursal_id, tipo='M', activa=True).first()
            sesion_caja = CajaSesion.objects.filter(caja=caja, usuario=request.user, estado='A').first()
            
            if not sesion_caja:
                return HttpResponse(json.dumps({'status': 'error', 'message': 'Caja cerrada o sesión inválida.'}), status=400)
                
            efectivo = Decimal(str(data.get('efectivo', 0) or 0))
            dolares = Decimal(str(data.get('dolares', 0) or 0))
            ctacte = Decimal(str(data.get('ctacte', 0) or 0))
            saldo_a_favor = Decimal(str(data.get('saldo_a_favor_ctacte', 0) or 0))
            
            if saldo_a_favor > 0 and preventa.cliente.codigo_id == 1:
                return HttpResponse(json.dumps({'status': 'error', 'message': 'No se puede dejar saldo a favor a un Consumidor Final.'}), status=400)
                
            if ctacte > 0 and preventa.cliente.codigo_id == 1:
                return HttpResponse(json.dumps({'status': 'error', 'message': 'No se puede dejar saldo en cuenta corriente al cliente genérico (Consumidor Final).'}), status=400)
            
            tarjetas = data.get('tarjetas', [])
            transferencias = data.get('transferencias', [])
            valores = data.get('valores', [])
            
            total_tarjetas = sum(Decimal(str(t.get('importe', 0) or 0)) for t in tarjetas)
            total_transferencias = sum(Decimal(str(t.get('importe', 0) or 0)) for t in transferencias)
            total_valores = sum(Decimal(str(v.get('importe', 0) or 0)) for v in valores)
            
            total_ingresado = efectivo + dolares + total_tarjetas + total_transferencias + total_valores + ctacte

            # Detección de armas trazables (SIGIMAC / subprod=True)
            item_subprod = preventa.items.filter(producto__subprod=True).first()
            if item_subprod:
                if total_ingresado <= Decimal("0.00"):
                    return HttpResponse(json.dumps({'status': 'error', 'message': 'Debe ingresar un monto mayor a cero para registrar la reserva.'}), status=400)
                
                return _guardar_reserva_preventa_transaccional(
                    request, preventa, item_subprod.producto, empresa_id, sucursal_id, sesion_caja,
                    efectivo, dolares, tarjetas, transferencias, valores, total_ingresado
                )
            
            if total_ingresado < (preventa.total - Decimal("0.05")):
                 return HttpResponse(json.dumps({'status': 'error', 'message': 'Monto insuficiente para cubrir el total de la Preventa.'}), status=400)
            
            condic = int(data.get('condic', 1))
            
            punto_venta_num = 1
            if condic == 2:
                punto_venta_num = 0
            else:
                from empresas.models import PuntoVenta
                pv_default = PuntoVenta.objects.filter(sucursal_id=sucursal_id, activo=True, caja_mostrador_default=True).first()
                if pv_default:
                    punto_venta_num = pv_default.numero
                else:
                    pv_any = PuntoVenta.objects.filter(sucursal_id=sucursal_id, activo=True).first()
                    if pv_any:
                        punto_venta_num = pv_any.numero

            tipo_cbte = None
            res_afip = None
            if condic == 1:
                from facturacion.models import TipoComprobante
                from empresas.models import Empresa
                from facturacion.services.afip_service import AFIPService
                from facturacion.views import ALICUOTAS_ARCA_MAP, resolver_tipo_comprobante_fiscal, validar_y_obtener_documento_receptor
                
                empresa_obj = get_object_or_404(Empresa, id=empresa_id)
                
                # Si la preventa se marcó como "Consumidor Final" (consumo propio), se fuerza Factura B
                condicion_iva_op = 'CONSUMIDOR FINAL' if getattr(preventa, 'es_consumidor_final', False) else preventa.cliente.condicion_iva

                # Resolución robusta del comprobante fiscal (Factura A para RI/Monotributo, Factura B para Consumidor Final/Exento)
                tipo_cbte = resolver_tipo_comprobante_fiscal(condicion_iva_op, tipo_operacion='FACTURA')
                if not tipo_cbte:
                    return HttpResponse(json.dumps({'status': 'error', 'message': 'No se encontró un Tipo de Comprobante fiscal activo (Factura A / B) en el sistema.'}), status=400)

                try:
                    if getattr(preventa, 'es_consumidor_final', False):
                        # Para consumo propio de un RI/Monotributista, se emite Factura B con condición Consumidor Final (5)
                        cuit_raw = str(preventa.cliente.cuit or '').replace('-', '').strip()
                        tipo_doc_raw = str(preventa.cliente.tipo_documento or '').strip()
                        if cuit_raw.isdigit() and len(cuit_raw) == 11:
                            doc_tipo, doc_nro = 80, int(cuit_raw)
                        elif cuit_raw.isdigit() and len(cuit_raw) in [7, 8]:
                            doc_tipo, doc_nro = 96, int(cuit_raw)
                        elif not cuit_raw or cuit_raw in ['0', '00'] or tipo_doc_raw == '99':
                            doc_tipo, doc_nro = 99, 0
                        else:
                            doc_tipo, doc_nro = int(tipo_doc_raw or 99), int(cuit_raw)
                        cond_iva_rec = 5  # Consumidor Final
                    else:
                        doc_tipo, doc_nro, cond_iva_rec = validar_y_obtener_documento_receptor(preventa.cliente)
                except ValidationError as ve:
                    return HttpResponse(json.dumps({'status': 'error', 'message': ve.message if hasattr(ve, 'message') else str(ve)}), status=400)
                
                if str(tipo_cbte.codigo).isdigit():
                    alicuotas_dict = {}
                    for item in preventa.items.all():
                        alic_val = Decimal(str(item.producto.alic_iva_porc if hasattr(item.producto, 'alic_iva_porc') else '21.00'))
                        alicuota_factor = Decimal("1.00") + (alic_val / Decimal("100.00"))
                        item_total = Decimal(str(item.total))
                        neto_item = (item_total / alicuota_factor).quantize(Decimal("0.01"))
                        iva_item = item_total - neto_item
                        
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
                    
                    tot_neto_alic = sum((a['base_imponible'] for a in alicuotas_list), Decimal('0.00'))
                    tot_iva_alic = sum((a['importe_iva'] for a in alicuotas_list), Decimal('0.00'))
                    
                    datos_afip = {
                        'pto_vta': punto_venta_num,
                        'cbte_tipo': int(tipo_cbte.codigo),
                        'concepto': 1,
                        'doc_tipo': doc_tipo,
                        'doc_nro': doc_nro,
                        'cbte_fch': timezone.localdate().strftime('%Y%m%d'),
                        'imp_total': float(tot_neto_alic + tot_iva_alic),
                        'imp_tot_conc': 0.0,
                        'imp_neto': float(tot_neto_alic),
                        'imp_op_ex': 0.0,
                        'imp_iva': float(tot_iva_alic),
                        'condicion_iva_receptor_id': cond_iva_rec,
                        'mon_id': 'PES',
                        'mon_cotiz': 1.0
                    }
                    try:
                        afip_service = AFIPService(empresa_obj)
                        res_afip = afip_service.emitir_comprobante(datos_afip, alicuotas_list)
                        if not res_afip['exito']:
                            return HttpResponse(json.dumps({'status': 'error', 'message': f"Rechazo ARCA: {res_afip['error']}"}), status=400)
                    except Exception as e:
                        return HttpResponse(json.dumps({'status': 'error', 'message': f"Error en comunicación con ARCA: {str(e)}"}), status=400)
            elif condic == 2:
                from facturacion.models import TipoComprobante
                tipo_cbte = TipoComprobante.objects.filter(codigo='PRE').first()

            return _guardar_cobro_preventa_transaccional(
                request, preventa_id, empresa_id, sucursal_id, sesion_caja,
                efectivo, dolares, ctacte, saldo_a_favor,
                tarjetas, transferencias, valores,
                total_tarjetas, total_transferencias, total_valores, total_ingresado,
                condic, punto_venta_num, tipo_cbte, res_afip
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            return HttpResponse(json.dumps({'status': 'error', 'message': str(e)}), status=400, content_type="application/json")
    return HttpResponse(status=405)

def _crear_asientos_y_movimientos_cobro(
    request, venta, preventa, empresa_id, sucursal_id, sesion_caja,
    efectivo, dolares, ctacte, saldo_a_favor,
    tarjetas, transferencias, valores,
    total_tarjetas, total_transferencias, total_valores, total_ingresado
):
            from facturacion.models import VentaItem
            ventas_por_rubro = {}
            iva_total = Decimal("0")
            for item in preventa.items.all():
                v_item = VentaItem.objects.create(
                    venta=venta,
                    producto=item.producto,
                    cantidad=item.cantidad,
                    precio_unitario=item.precio_unitario,
                    total=item.total,
                    iva_alicuota=item.producto.alic_iva_porc if hasattr(item.producto, 'alic_iva_porc') else Decimal('21.00'),
                    credencial=item.credencial,
                    dmp=item.dmp or Decimal('0.00')
                )

                
                alicuota_factor = Decimal("1.00") + (Decimal(str(v_item.iva_alicuota)) / Decimal("100.00"))
                neto_item = v_item.total / alicuota_factor
                iva_item = v_item.total - neto_item
                iva_total += iva_item
                
                cta_ventas = item.producto.rubro.cta_ventas if item.producto.rubro and item.producto.rubro.cta_ventas else None
                rubro_id = cta_ventas.id if cta_ventas else "DEFAULT"
                ventas_por_rubro[rubro_id] = ventas_por_rubro.get(rubro_id, Decimal("0")) + neto_item
                
            preventa.estado = 3 # Facturada/Cobrada
            preventa.save()
            
            # 2. Registros de tesoreria
            from empresas.models import CotizacionMoneda
            cotiz = CotizacionMoneda.objects.filter(empresa_id=empresa_id).first()
            dolar_cobranza = cotiz.dolar_cobranza if cotiz else Decimal('1.0')

            # Condición del movimiento de fondos según el TIPO DE COMPROBANTE (Plan 049):
            # PRE (Presupuesto) -> Presupuestado (2); cualquier otro -> Real (1). Antes estaba
            # fijo en 1, así que una venta presupuestada quedaba registrada como Real y el
            # filtro Real/Presupuestado de los reportes de fondos la clasificaba mal.
            from tesoreria.services.imputacion import condic_por_comprobante
            condic_mov = condic_por_comprobante(venta.tipo)

            mov_caja = MovimientoCaja.objects.create(
                sesion=sesion_caja,
                empresa_id=empresa_id,
                fecha=venta.fecha,
                tipo='I',
                importe=total_ingresado - ctacte,
                concepto=f"Cobro Venta {venta.numero}",
                condic=condic_mov,
                venta=venta,
                cli_pro=venta.cliente,
            )

            # Efectivo ARS
            if efectivo > 0:
                mp_efe = MedioPago.objects.filter(empresa_id=empresa_id, categoria='EFE').first()
                if mp_efe:
                    MovimientoCajaDetalle.objects.create(
                        movimiento_caja=mov_caja,
                        medio_pago=mp_efe,
                        importe=efectivo,
                        importe_moneda_extranjera=0,
                        cotizacion=1.0
                    )
            
            # Efectivo USD
            if dolares > 0:
                mp_efe = MedioPago.objects.filter(empresa_id=empresa_id, categoria='EFE').first()
                if mp_efe:
                    MovimientoCajaDetalle.objects.create(
                        movimiento_caja=mov_caja,
                        medio_pago=mp_efe,
                        importe=dolares * Decimal(str(dolar_cobranza)),
                        importe_moneda_extranjera=dolares,
                        cotizacion=dolar_cobranza
                    )
            
            # Tarjetas
            mp_tarjeta = MedioPago.objects.filter(empresa_id=empresa_id, categoria='TAR').first()
            for t in tarjetas:
                imp = Decimal(str(t.get('importe', 0) or 0))
                if imp > 0 and mp_tarjeta:
                    detalle = MovimientoCajaDetalle.objects.create(
                        movimiento_caja=mov_caja,
                        medio_pago=mp_tarjeta,
                        importe=imp,
                        importe_moneda_extranjera=0,
                        cotizacion=1.0
                    )
                    CobroTarjeta.objects.create(
                        movimiento_detalle=detalle,
                        tarjeta_id=t.get('tarjeta_id'),
                        lote=t.get('lote', ''),
                        cupon=t.get('cupon', ''),
                        cuotas=1,
                        sucursal_id=sucursal_id
                    )
            
            # Valores a Terceros (Cheques)
            mp_chq = MedioPago.objects.filter(empresa_id=empresa_id, categoria='CHQ').first()
            for v in valores:
                imp = Decimal(str(v.get('importe', 0) or 0))
                if imp > 0 and mp_chq:
                    detalle = MovimientoCajaDetalle.objects.create(
                        movimiento_caja=mov_caja,
                        medio_pago=mp_chq,
                        importe=imp,
                        importe_moneda_extranjera=0,
                        cotizacion=1.0
                    )
                    ValorTerceros.objects.create(
                        empresa_id=empresa_id,
                        movimiento_detalle=detalle,
                        banco_id=v.get('banco_id'),
                        numero_cheque=v.get('numero', ''),
                        importe=imp,
                        fecha_emision=venta.fecha,
                        fecha_vencimiento=v.get('vto') if v.get('vto') else venta.fecha,
                        fecha_recepcion=venta.fecha,
                        estado='C',
                        sucursal_id=sucursal_id
                    )
                    
            # Transferencias
            mp_tra = MedioPago.objects.filter(empresa_id=empresa_id, categoria='TRA').first()
            for t in transferencias:
                imp = Decimal(str(t.get('importe', 0) or 0))
                if imp > 0 and mp_tra:
                    detalle = MovimientoCajaDetalle.objects.create(
                        movimiento_caja=mov_caja,
                        medio_pago=mp_tra,
                        importe=imp,
                        importe_moneda_extranjera=0,
                        cotizacion=1.0
                    )
                    TransaccionBancaria.objects.create(
                        empresa_id=empresa_id,
                        movimiento_detalle=detalle,
                        cuenta_bancaria_id=t.get('cuenta_id'),
                        numero_operacion='',
                        importe=imp,
                        fecha_operacion=venta.fecha,
                        tipo_transaccion='TR',
                        estado='D'
                    )
                
            # 3. Asiento Contable
            param = ParametrosContables.objects.filter(empresa_id=empresa_id).first()
            if param:
                asiento = Asiento.objects.create(
                    empresa_id=empresa_id,
                    ejercicio_id=request.session.get('ejercicio_id'),
                    fecha=venta.fecha,
                    concepto=f"VENTA MOSTRADOR {venta.numero}",
                    monto=venta.total,
                    modulo=2, # Modulo Tesoreria/Ventas
                    # El asiento HEREDA el condic del comprobante que lo origina (`.cursorrules`).
                    # Antes quedaba en el default 1, así que una venta presupuestada generaba un
                    # asiento marcado como Real.
                    condic=venta.condic,
                    cli_pro=venta.cliente,
                    # Sin esta caja el cobro de mostrador no aparecía en el reporte de Caja
                    # Diaria, que filtra los asientos por `sesion_caja`.
                    sesion_caja=sesion_caja,
                    creado_por=request.user
                )
                
                orden = 1
                from contable.services.contabilizacion import cuenta_efectivo_de_caja

                # La cuenta del efectivo la define LA CAJA, no un parámetro fijo (Plan 077
                # §E): esta venta la cobró un cajero que después tiene que rendirla, así que
                # el debe va a su caja. Antes iba a `cta_caja` y el retiro acreditaba
                # `cta_caja_mostrador`, dos cuentas distintas que nunca netearon.
                cta_efectivo = cuenta_efectivo_de_caja(
                    sesion_caja.caja, param) or param.cta_caja
                if efectivo > 0 and cta_efectivo:
                    AsientoLinea.objects.create(asiento=asiento, orden=orden, cuenta=cta_efectivo, debe=efectivo, haber=0)
                    orden+=1
                cta_dolares = cuenta_efectivo_de_caja(
                    sesion_caja.caja, param, en_divisa=True) or param.cta_dolar
                if dolares > 0 and cta_dolares:
                    AsientoLinea.objects.create(asiento=asiento, orden=orden, cuenta=cta_dolares, debe=dolares, haber=0)
                    orden+=1
                if total_tarjetas > 0 and param.cta_tarjetas_a_cobrar:
                    AsientoLinea.objects.create(asiento=asiento, orden=orden, cuenta=param.cta_tarjetas_a_cobrar, debe=total_tarjetas, haber=0)
                    orden+=1
                if total_valores > 0 and param.cta_valores_cartera:
                    AsientoLinea.objects.create(asiento=asiento, orden=orden, cuenta=param.cta_valores_cartera, debe=total_valores, haber=0)
                    orden+=1
                    
                # Si el cliente paga parte con CtaCte (O sea, dice "Anótame $1000 en mi cuenta")
                if ctacte > 0 and param.cta_clientes_default:
                    AsientoLinea.objects.create(asiento=asiento, orden=orden, cuenta=param.cta_clientes_default, debe=ctacte, haber=0)
                    orden+=1
                    
                for t in transferencias:
                    imp = Decimal(str(t.get('importe', 0) or 0))
                    cuenta_id = t.get('cuenta_id')
                    if imp > 0 and cuenta_id:
                        cta_bc = CuentaBancaria.objects.filter(cta_bc_id=cuenta_id).first()
                        if cta_bc and cta_bc.cuenta_contable:
                            AsientoLinea.objects.create(asiento=asiento, orden=orden, cuenta=cta_bc.cuenta_contable, debe=imp, haber=0)
                            orden+=1
                
                # Haber: Rubros de Ventas
                for cta_id, monto in ventas_por_rubro.items():
                    cta_id_final = param.cta_ventas_id if cta_id == "DEFAULT" else cta_id
                    if cta_id_final:
                        AsientoLinea.objects.create(asiento=asiento, orden=orden, cuenta_id=cta_id_final, debe=0, haber=monto)
                        orden+=1
                        
                # Haber: IVA
                if iva_total > 0 and param.cta_iva_debito:
                    AsientoLinea.objects.create(asiento=asiento, orden=orden, cuenta=param.cta_iva_debito, debe=0, haber=iva_total)
                    orden+=1
                    
                # Haber: Saldo a Favor del Cliente (Si dejó vuelto a su favor con cheques)
                if saldo_a_favor > 0 and param.cta_clientes_default:
                    AsientoLinea.objects.create(asiento=asiento, orden=orden, cuenta=param.cta_clientes_default, debe=0, haber=saldo_a_favor)
                    orden+=1
                    
                venta.asiento_id = asiento.asiento_id
                venta.save(update_fields=['asiento_id'])

                # Vínculo contable del movimiento de fondos (Plan 049). El asiento en sí se deja
                # como está —armado a mano, sin `sesion_caja` ni `condic`—: queda anotado como
                # deuda técnica en el plan, fuera del alcance de este cambio.
                from tesoreria.services.imputacion import estampar_asiento
                estampar_asiento(mov_caja, asiento)


@login_required
@transaction.atomic
def caja_mostrador_anular_preventa(request, preventa_id):
    if request.method == 'POST':
        from facturacion.models import Preventa
        empresa_id = request.session.get('empresa_id')
        preventa = get_object_or_404(Preventa, preventa_id=preventa_id, empresa_id=empresa_id)
        
        # Validar que no esté ya cobrada o anulada
        if preventa.estado in [3, 4]:
            return HttpResponse("<script>alert('Esta preventa ya fue procesada o anulada.'); location.reload();</script>")
            
        preventa.estado = 4  # 4 = Anulada
        preventa.save()
        
        response = HttpResponse()
        # Disparamos el refresco de la página para actualizar la tabla
        response['HX-Refresh'] = "true"
        return response
    return HttpResponse(status=405)


# --- Qué caja se opera (Plan 076 §B) ----------------------------------------------------
# Hasta la fase 7 de distribución había UNA sola caja por sucursal, así que alcanzaba con
# `filter(empresa, sucursal, activa).first()`. Ahora conviven la MOSTRADOR ('M'), la
# recaudadora de cada reparto ('R') y la TESORERÍA DE REPARTO ('D'), y ese `.first()` sin
# tipo podía devolver cualquiera: el cierre de mostrador llegaba a tomar la sesión de un
# reparto y rendía esa plata por el circuito equivocado. De ahí el filtro explícito.
CAJAS_OPERABLES = ('M', 'D')


def _caja_operable(request, caja_id=None):
    """La caja sobre la que se está operando: mostrador por defecto, o la que se elija.

    Sólo se operan a mano la mostrador y la tesorería de reparto. La recaudadora ('R') NO:
    sus sesiones las abre y las cierra el reparto, no una persona.
    """
    empresa_id = request.session.get('empresa_id')
    sucursal_id = request.session.get('sucursal_id')
    caja_id = caja_id or request.GET.get('caja') or request.POST.get('caja')

    if caja_id:
        return Caja.objects.filter(
            pk=caja_id, empresa_id=empresa_id, sucursal_id=sucursal_id,
            tipo__in=CAJAS_OPERABLES, activa=True).first()
    return Caja.objects.filter(
        empresa_id=empresa_id, sucursal_id=sucursal_id, tipo='M', activa=True).first()


def cuenta_origen_de_caja(caja, param):
    """De qué cuenta contable sale el efectivo de esta caja.

    Delega en el motor contable para que la respuesta sea LA MISMA que usa el asiento del
    recibo o de la venta (Plan 077 §E). Si el retiro acreditara una cuenta distinta de la que
    debitó la cobranza, la caja no cerraría nunca en cero.
    """
    from contable.services.contabilizacion import cuenta_efectivo_de_caja

    return cuenta_efectivo_de_caja(caja, param) or param.cta_caja_mostrador


def _cajas_operables(request):
    """Las cajas entre las que puede elegir quien opera, para el selector del modal."""
    return Caja.objects.filter(
        empresa_id=request.session.get('empresa_id'),
        sucursal_id=request.session.get('sucursal_id'),
        tipo__in=CAJAS_OPERABLES, activa=True).order_by('tipo', 'nombre')


@login_required
def caja_retiro_modal(request):
    empresa_id = request.session.get('empresa_id')
    sucursal_id = request.session.get('sucursal_id')
    
    # Obtener caja activa y sesión
    caja = _caja_operable(request)
    sesion_caja = CajaSesion.objects.filter(caja=caja, usuario=request.user, estado='A').first()
    
    if not sesion_caja:
        return HttpResponse("No hay sesión de caja abierta.", status=400)
    # Obtener valores en cartera de esta sucursal
    # Nota: Filtramos por la sucursal actual
    valores = ValorTerceros.objects.filter(sucursal_id=sucursal_id, retirocajavalor__isnull=True)
    cupones = CobroTarjeta.objects.filter(movimiento_detalle__movimiento_caja__sesion=sesion_caja, sucursal_id=sucursal_id, retirocajatarjeta__isnull=True)
    
    context = {
        'sesion': sesion_caja,
        'valores': valores,
        'cupones': cupones
    }
    return render(request, 'tesoreria/modals/caja_retiro.html', context)

@login_required
@transaction.atomic
def caja_retiro_procesar(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            empresa_id = request.session.get('empresa_id')
            sucursal_id = request.session.get('sucursal_id')
            
            caja = _caja_operable(request)
            sesion_caja = CajaSesion.objects.filter(caja=caja, usuario=request.user, estado='A').first()
            
            if not sesion_caja:
                return HttpResponse(json.dumps({'status': 'error', 'message': 'Caja cerrada o sesión inválida.'}), status=400)
                
            efectivo_pesos = Decimal(str(data.get('efectivo_pesos', 0) or 0))
            efectivo_dolares = Decimal(str(data.get('efectivo_dolares', 0) or 0))
            observaciones = data.get('observaciones', '')
            valores_ids = data.get('valores_ids', [])
            cupones_ids = data.get('cupones_ids', [])
            
            # Sucursal destino (por defecto la central 1)
            # Podría venir del form, pero el requerimiento dice "default suc 1"
            destino_id = 1 
            from empresas.models import Sucursal
            suc_destino = Sucursal.objects.get(pk=destino_id)
            
            retiro = RetiroCaja.objects.create(
                sesion=sesion_caja,
                tipo='P',
                usuario=request.user,
                sucursal_origen_id=sucursal_id,
                sucursal_destino=suc_destino,
                efectivo_pesos=efectivo_pesos,
                efectivo_dolares=efectivo_dolares,
                cotizacion_dolar=Decimal("1.0"), # Opcional: obtener de BD
                observaciones=observaciones,
                creado_por=request.user
            )
            
            # Registrar egreso en MovimientoCaja de la sesión para descontar efectivo retirado
            mov_retiro = None
            if efectivo_pesos > 0 or efectivo_dolares > 0:
                mov_retiro = MovimientoCaja.objects.create(
                    sesion=sesion_caja,
                    empresa_id=empresa_id,
                    # Movimiento interno: se registra en el día, así que la fecha de la
                    # operación y la de carga coinciden. `cli_pro` queda nulo (no hay entidad).
                    fecha=timezone.localdate(),
                    tipo='R', # Retiro
                    importe=efectivo_pesos + (efectivo_dolares * Decimal("1.0")),
                    concepto=f"Retiro de Efectivo #{retiro.id}",
                    condic=1
                )
                if efectivo_pesos > 0:
                    mp_efe = MedioPago.objects.filter(empresa_id=empresa_id, categoria='EFE').first()
                    if mp_efe:
                        MovimientoCajaDetalle.objects.create(
                            movimiento_caja=mov_retiro,
                            medio_pago=mp_efe,
                            importe=efectivo_pesos,
                            importe_moneda_extranjera=0,
                            cotizacion=1.0
                        )
                if efectivo_dolares > 0:
                    mp_efe = MedioPago.objects.filter(empresa_id=empresa_id, categoria='EFE').first()
                    if mp_efe:
                        MovimientoCajaDetalle.objects.create(
                            movimiento_caja=mov_retiro,
                            medio_pago=mp_efe,
                            importe=efectivo_dolares * Decimal("1.0"),
                            importe_moneda_extranjera=efectivo_dolares,
                            cotizacion=1.0
                        )
            
            # Mover Valores
            for v_id in valores_ids:
                valor = ValorTerceros.objects.get(pk=v_id, sucursal_id=sucursal_id)
                RetiroCajaValor.objects.create(retiro=retiro, valor=valor)
                valor.sucursal_id = destino_id
                valor.save(update_fields=['sucursal_id'])
                
            # Mover Cupones
            for c_id in cupones_ids:
                cupon = CobroTarjeta.objects.get(pk=c_id, sucursal_id=sucursal_id)
                RetiroCajaTarjeta.objects.create(retiro=retiro, cobro_tarjeta=cupon)
                cupon.sucursal_id = destino_id
                cupon.save(update_fields=['sucursal_id'])
                
            # Si hay pesos o dólares, hacer asiento(s)
            param = ParametrosContables.objects.filter(empresa_id=empresa_id).first()
            if not param:
                raise Exception("Faltan Parámetros Contables")
                
            asientos_ids = generar_asientos_traslado(
                empresa_id=empresa_id, 
                ejercicio_id=request.session.get('ejercicio_id'),
                suc_origen_id=sucursal_id, 
                suc_destino_id=destino_id, 
                pesos=efectivo_pesos, 
                dolares=efectivo_dolares, 
                param=param, 
                fecha=timezone.localdate(),
                concepto_base=f"RETIRO CAJA {retiro.id}",
                usuario=request.user,
                cuenta_origen=cuenta_origen_de_caja(caja, param)
            )
            
            for asid in asientos_ids:
                RetiroCajaAsiento.objects.create(retiro=retiro, asiento_id=asid)

            # Vínculo contable del movimiento de fondos (Plan 049). Un traslado puede generar
            # hasta cuatro asientos (pesos/dólares × origen/destino). Se vincula el PRIMERO, que
            # es el del lado ORIGEN en pesos: el que refleja la salida de esta sesión. La lista
            # completa queda en `RetiroCajaAsiento`.
            if mov_retiro and asientos_ids:
                from tesoreria.services.imputacion import estampar_asiento
                estampar_asiento(mov_retiro, Asiento.objects.filter(pk=asientos_ids[0]).first())

            # La rendición queda 'En Tránsito' (estado='T' por defecto): el ingreso en
            # Tesorería (fila 2) se genera recién cuando el tesorero la recibe y cuenta.
            return HttpResponse(json.dumps({'status': 'success'}), content_type="application/json")
        except Exception as e:
            import traceback
            traceback.print_exc()
            return HttpResponse(json.dumps({'status': 'error', 'message': str(e)}), status=400, content_type="application/json")
    return HttpResponse(status=405)


@login_required
def caja_cierre_modal(request):
    empresa_id = request.session.get('empresa_id')
    sucursal_id = request.session.get('sucursal_id')
    caja = _caja_operable(request)
    sesion_caja = CajaSesion.objects.filter(caja=caja, usuario=request.user, estado='A').first()
    
    if not sesion_caja:
        return HttpResponse("No hay sesión de caja abierta.", status=400)
        
    # Modal ciego
    context = {
        'sesion': sesion_caja,
    }
    return render(request, 'tesoreria/modals/caja_cierre.html', context)

@login_required
@transaction.atomic
def caja_cierre_procesar(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            empresa_id = request.session.get('empresa_id')
            sucursal_id = request.session.get('sucursal_id')
            
            caja = _caja_operable(request)
            sesion_caja = CajaSesion.objects.select_for_update().filter(caja=caja, usuario=request.user, estado='A').first()
            
            if not sesion_caja:
                return HttpResponse(json.dumps({'status': 'error', 'message': 'Caja cerrada o sesión inválida.'}), status=400)
                
            contado_pesos = Decimal(str(data.get('contado_pesos', 0) or 0))
            contado_dolares = Decimal(str(data.get('contado_dolares', 0) or 0))
            fondo_fijo = Decimal(str(data.get('fondo_fijo', 0) or 0))
            observaciones = data.get('observaciones', '')

            if fondo_fijo > contado_pesos:
                return HttpResponse(json.dumps({'status': 'error', 'message': 'El fondo fijo no puede superar lo contado en pesos.'}), status=400, content_type="application/json")

            # El fondo fijo (sencillo) se queda físicamente en el cajón; a Tesorería se rinde solo el resto.
            efectivo_pesos = contado_pesos - fondo_fijo
            efectivo_dolares = contado_dolares

            destino_id = 1
            from empresas.models import Sucursal
            suc_destino = Sucursal.objects.get(pk=destino_id)
            
            retiro = RetiroCaja.objects.create(
                sesion=sesion_caja,
                tipo='C',
                usuario=request.user,
                sucursal_origen_id=sucursal_id,
                sucursal_destino=suc_destino,
                efectivo_pesos=efectivo_pesos,
                efectivo_dolares=efectivo_dolares,
                cotizacion_dolar=Decimal("1.0"),
                observaciones=observaciones,
                creado_por=request.user
            )

            # Egreso (fila 1) en el cuaderno de la caja mostrador: el efectivo sale de la sesión al cerrar.
            mov_cierre = None
            if efectivo_pesos > 0 or efectivo_dolares > 0:
                mov_cierre = MovimientoCaja.objects.create(
                    sesion=sesion_caja,
                    empresa_id=empresa_id,
                    # Movimiento interno del día; `cli_pro` nulo (no hay entidad).
                    fecha=timezone.localdate(),
                    tipo='R',
                    importe=efectivo_pesos + (efectivo_dolares * Decimal("1.0")),
                    concepto=f"Cierre de caja - Rendición #{retiro.id}",
                    condic=1,
                    creado_por=request.user,
                )
                medio_efe = MedioPago.objects.filter(empresa_id=empresa_id, categoria='EFE').first()
                if medio_efe and efectivo_pesos > 0:
                    MovimientoCajaDetalle.objects.create(
                        movimiento_caja=mov_cierre, medio_pago=medio_efe,
                        importe=efectivo_pesos, importe_moneda_extranjera=0, cotizacion=1.0)
                if medio_efe and efectivo_dolares > 0:
                    MovimientoCajaDetalle.objects.create(
                        movimiento_caja=mov_cierre, medio_pago=medio_efe,
                        importe=efectivo_dolares * Decimal("1.0"), importe_moneda_extranjera=efectivo_dolares, cotizacion=1.0)

            # Obtener TODOS los valores de esta sesión que aún están en esta sucursal (no retirados antes)
            # Ahora ValorTerceros y CobroTarjeta se vinculan a través de MovimientoCajaDetalle -> MovimientoCaja -> Sesion
            valores = ValorTerceros.objects.filter(movimiento_detalle__movimiento_caja__sesion=sesion_caja, sucursal_id=sucursal_id)
            
            for valor in valores:
                RetiroCajaValor.objects.create(retiro=retiro, valor=valor)
                valor.sucursal_id = destino_id
                valor.save(update_fields=['sucursal_id'])
                
            cupones = CobroTarjeta.objects.filter(movimiento_detalle__movimiento_caja__sesion=sesion_caja, sucursal_id=sucursal_id)
            for cupon in cupones:
                RetiroCajaTarjeta.objects.create(retiro=retiro, cobro_tarjeta=cupon)
                cupon.sucursal_id = destino_id
                cupon.save(update_fields=['sucursal_id'])
                
            # Generar Asientos
            param = ParametrosContables.objects.filter(empresa_id=empresa_id).first()
            if not param:
                raise Exception("Faltan Parámetros Contables")
                
            asientos_ids = generar_asientos_traslado(
                empresa_id=empresa_id, 
                ejercicio_id=request.session.get('ejercicio_id'),
                suc_origen_id=sucursal_id, 
                suc_destino_id=destino_id, 
                pesos=efectivo_pesos, 
                dolares=efectivo_dolares, 
                param=param, 
                fecha=timezone.localdate(),
                concepto_base=f"CIERRE CAJA {sesion_caja.id}",
                usuario=request.user,
                cuenta_origen=cuenta_origen_de_caja(caja, param)
            )
            
            for asid in asientos_ids:
                RetiroCajaAsiento.objects.create(retiro=retiro, asiento_id=asid)

            # Vínculo contable del movimiento de fondos (Plan 049): el primer asiento del
            # traslado, que es el del lado origen. Ver el comentario del retiro parcial.
            if mov_cierre and asientos_ids:
                from tesoreria.services.imputacion import estampar_asiento
                estampar_asiento(mov_cierre, Asiento.objects.filter(pk=asientos_ids[0]).first())

            # Cerrar sesión (ciego). Lo declarado que QUEDA en la caja es el fondo fijo.
            sesion_caja.estado = 'C'
            sesion_caja.fecha_cierre = timezone.localtime()
            sesion_caja.saldo_final_declarado = fondo_fijo
            sesion_caja.save(update_fields=['estado', 'fecha_cierre', 'saldo_final_declarado'])
            
            return HttpResponse(json.dumps({'status': 'success'}), content_type="application/json")
        except Exception as e:
            import traceback
            traceback.print_exc()
            return HttpResponse(json.dumps({'status': 'error', 'message': str(e)}), status=400, content_type="application/json")
    return HttpResponse(status=405)


def generar_asientos_traslado(empresa_id, ejercicio_id, suc_origen_id, suc_destino_id, pesos, dolares, param, fecha, concepto_base, usuario, cuenta_origen=None):
    """Asienta el traslado de efectivo de una caja a otra.

    `cuenta_origen` permite decir DE QUÉ CAJA sale la plata. Por omisión es la
    mostrador, que era el único caso hasta el Plan 076; el circuito de distribución
    pasa `cta_caja_reparto`, porque el efectivo que está en la calle es de otro
    responsable y el balance tiene que poder mostrarlo por separado.
    """
    # Lógica de uno o dos asientos según documento:
    asientos_creados = []
    
    # helper
    def crear_asiento_moneda(monto, cuenta_origen, cuenta_destino, cuenta_puente, moneda_desc):
        if monto <= 0: return
        
        if not cuenta_origen:
            raise Exception(f"Falta configurar la cuenta de origen para {moneda_desc} en Parámetros Contables.")
        if not cuenta_destino:
            raise Exception(f"Falta configurar la cuenta de destino para {moneda_desc} en Parámetros Contables.")
        if suc_origen_id != suc_destino_id and not cuenta_puente:
            raise Exception("Falta configurar la cuenta de Transferencias entre Sucursales en Parámetros Contables.")
        
        if suc_origen_id == suc_destino_id:
            # 1 Asiento
            asiento = Asiento.objects.create(
                empresa_id=empresa_id, ejercicio_id=ejercicio_id, sucursal_id=suc_origen_id,
                fecha=fecha, concepto=f"{concepto_base} {moneda_desc}", monto=monto, modulo=2, creado_por=usuario
            )
            AsientoLinea.objects.create(asiento=asiento, orden=1, cuenta=cuenta_destino, debe=monto, haber=0)
            AsientoLinea.objects.create(asiento=asiento, orden=2, cuenta=cuenta_origen, debe=0, haber=monto)
            asientos_creados.append(asiento.asiento_id)
        else:
            # 2 Asientos vía puente
            # A (origen)
            asientoA = Asiento.objects.create(
                empresa_id=empresa_id, ejercicio_id=ejercicio_id, sucursal_id=suc_origen_id,
                fecha=fecha, concepto=f"{concepto_base} {moneda_desc} ORIGEN", monto=monto, modulo=2, creado_por=usuario
            )
            AsientoLinea.objects.create(asiento=asientoA, orden=1, cuenta=cuenta_puente, debe=monto, haber=0)
            AsientoLinea.objects.create(asiento=asientoA, orden=2, cuenta=cuenta_origen, debe=0, haber=monto)
            asientos_creados.append(asientoA.asiento_id)
            
            # B (destino)
            asientoB = Asiento.objects.create(
                empresa_id=empresa_id, ejercicio_id=ejercicio_id, sucursal_id=suc_destino_id,
                fecha=fecha, concepto=f"{concepto_base} {moneda_desc} DESTINO", monto=monto, modulo=2, creado_por=usuario
            )
            AsientoLinea.objects.create(asiento=asientoB, orden=1, cuenta=cuenta_destino, debe=monto, haber=0)
            AsientoLinea.objects.create(asiento=asientoB, orden=2, cuenta=cuenta_puente, debe=0, haber=monto)
            asientos_creados.append(asientoB.asiento_id)

    # PESOS
    crear_asiento_moneda(pesos, cuenta_origen or param.cta_caja_mostrador, param.cta_caja_central, param.cta_transferencias_sucursal, "ARS")
    # DOLARES
    crear_asiento_moneda(dolares, param.cta_caja_mostrador_dolares, param.cta_caja_central_dolares, param.cta_transferencias_sucursal, "USD")
    
    return asientos_creados


@login_required
def caja_retiro_anular(request, retiro_id):
    return HttpResponse(json.dumps({"status": "error", "message": "Anulacion pendiente"}), status=400, content_type="application/json")


# =========================================================================
# RECEPCIÓN DE RENDICIONES (TESORERO) - Paso 2 de la rendición
# =========================================================================

def _get_sesion_tesoreria(request, empresa_id, sucursal_id):
    """Asegura una Caja de tipo Tesorería en la sucursal y una sesión abierta del tesorero.
    (La apertura formal de la caja de tesorería se hará en una UI propia más adelante.)"""
    caja_tes = Caja.objects.filter(empresa_id=empresa_id, sucursal_id=sucursal_id, tipo='T', activa=True).first()
    if not caja_tes:
        caja_tes = Caja.objects.create(
            empresa_id=empresa_id, sucursal_id=sucursal_id, tipo='T',
            nombre="Tesorería")
    sesion = CajaSesion.objects.filter(caja=caja_tes, usuario=request.user, estado='A').first()
    if not sesion:
        sesion = CajaSesion.objects.create(caja=caja_tes, usuario=request.user, saldo_inicial=0, estado='A')
    return sesion


@login_required
def rendiciones_recepcion(request):
    """Bandeja del tesorero: rendiciones En Tránsito destinadas a su sucursal."""
    empresa_id = request.session.get('empresa_id')
    sucursal_id = request.session.get('sucursal_id')
    rendiciones = RetiroCaja.objects.filter(
        estado='T',
        sucursal_destino_id=sucursal_id,
        sesion__caja__empresa_id=empresa_id,
    ).select_related('sesion__caja', 'usuario', 'sucursal_origen').order_by('fecha')
    return render(request, 'tesoreria/rendiciones_recepcion.html', {'rendiciones': rendiciones})


@login_required
def rendicion_recibir_modal(request, retiro_id):
    empresa_id = request.session.get('empresa_id')
    sucursal_id = request.session.get('sucursal_id')
    retiro = get_object_or_404(
        RetiroCaja, pk=retiro_id, estado='T',
        sucursal_destino_id=sucursal_id, sesion__caja__empresa_id=empresa_id)
    valores = ValorTerceros.objects.filter(retirocajavalor__retiro=retiro)
    cupones = CobroTarjeta.objects.filter(retirocajatarjeta__retiro=retiro)
    return render(request, 'tesoreria/modals/rendicion_recibir.html', {
        'retiro': retiro, 'valores': valores, 'cupones': cupones,
    })


@login_required
@transaction.atomic
def rendicion_recibir_procesar(request, retiro_id):
    if request.method != 'POST':
        return HttpResponse(status=405)
    try:
        data = json.loads(request.body)
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')
        ejercicio_id = request.session.get('ejercicio_id')

        retiro = RetiroCaja.objects.select_for_update().get(
            pk=retiro_id, estado='T',
            sucursal_destino_id=sucursal_id, sesion__caja__empresa_id=empresa_id)

        contado_pesos = Decimal(str(data.get('efectivo_pesos', 0) or 0))
        contado_dolares = Decimal(str(data.get('efectivo_dolares', 0) or 0))

        sesion_tes = _get_sesion_tesoreria(request, empresa_id, sucursal_id)

        cot = retiro.cotizacion_dolar or Decimal('1.0')
        declarado_total = retiro.efectivo_pesos + retiro.efectivo_dolares * cot
        contado_total = contado_pesos + contado_dolares * cot
        diferencia = declarado_total - contado_total  # faltante (+) / sobrante (-)

        # --- Fila 2: ingreso (recibo de rendición) en la sesión de Tesorería, por lo CONTADO ---
        # `asiento` queda NULO a propósito: el movimiento de fondos que corresponde a esta
        # rendición es el traslado que se asentó al retirar (queda en `RetiroCajaAsiento`), no el
        # asiento de diferencia de arqueo que se genera más abajo, que es otra cosa.
        mov_ing = MovimientoCaja.objects.create(
            sesion=sesion_tes,
            empresa_id=empresa_id,
            fecha=timezone.localdate(),
            tipo='I',
            importe=contado_total,
            concepto=f"Rendición caja mostrador #{retiro.id} ({retiro.sucursal_origen.nombre})",
            condic=1,
            creado_por=request.user,
        )
        medio_efe = MedioPago.objects.filter(empresa_id=empresa_id, categoria='EFE').first()
        if medio_efe and contado_pesos > 0:
            MovimientoCajaDetalle.objects.create(
                movimiento_caja=mov_ing, medio_pago=medio_efe,
                importe=contado_pesos, importe_moneda_extranjera=0, cotizacion=1.0)
        if medio_efe and contado_dolares > 0:
            MovimientoCajaDetalle.objects.create(
                movimiento_caja=mov_ing, medio_pago=medio_efe,
                importe=contado_dolares * cot, importe_moneda_extranjera=contado_dolares, cotizacion=cot)

        # --- Asiento de diferencia (faltante/sobrante) contra cuenta patrimonial transitoria ---
        asiento_dif_id = None
        if diferencia != 0:
            param = ParametrosContables.objects.filter(empresa_id=empresa_id).first()
            if not param or not param.cta_diferencia_caja:
                raise Exception("Falta configurar la 'Cta. Diferencias de Caja' en Parámetros Contables.")
            if not param.cta_caja_central:
                raise Exception("Falta configurar la 'Cta. Caja Central' en Parámetros Contables.")
            asiento_dif_id = _generar_asiento_diferencia(
                empresa_id, ejercicio_id, sucursal_id, diferencia, param,
                timezone.localdate(), retiro, request.user)

        # --- Cerrar la rendición ---
        retiro.estado = 'R'
        retiro.sesion_recepcion = sesion_tes
        retiro.usuario_recepcion = request.user
        retiro.fecha_recepcion = timezone.localtime()
        retiro.efectivo_pesos_recibido = contado_pesos
        retiro.efectivo_dolares_recibido = contado_dolares
        retiro.diferencia_pesos = diferencia
        retiro.asiento_diferencia_id = asiento_dif_id
        retiro.save()

        return HttpResponse(json.dumps({'status': 'success', 'diferencia': str(diferencia)}), content_type="application/json")
    except RetiroCaja.DoesNotExist:
        return HttpResponse(json.dumps({'status': 'error', 'message': 'Rendición inexistente o ya recibida.'}), status=400, content_type="application/json")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return HttpResponse(json.dumps({'status': 'error', 'message': str(e)}), status=400, content_type="application/json")


def _generar_asiento_diferencia(empresa_id, ejercicio_id, sucursal_id, diferencia, param, fecha, retiro, usuario, cuenta_caja=None):
    """Ajusta la caja que recibió al efectivo realmente contado, estacionando el gap en
    Diferencias de Caja.

    diferencia > 0 (faltante): Debe Diferencias de Caja / Haber la caja.
    diferencia < 0 (sobrante): Debe la caja / Haber Diferencias de Caja.

    `cuenta_caja` dice CUÁL caja se ajusta. Por omisión es la Caja Central, que era el único
    destino hasta el Plan 076; cuando quien recibe es la Tesorería de Reparto se pasa
    `cta_caja_reparto`, porque la plata contada está ahí y no en Tesorería.
    """
    monto = abs(diferencia)
    es_faltante = diferencia > 0
    cuenta_caja = cuenta_caja or param.cta_caja_central
    asiento = Asiento.objects.create(
        empresa_id=empresa_id, ejercicio_id=ejercicio_id, sucursal_id=sucursal_id,
        fecha=fecha,
        concepto=f"DIFERENCIA DE CAJA ({'FALTANTE' if es_faltante else 'SOBRANTE'}) - Rendición #{retiro.id}",
        monto=monto, modulo=2, creado_por=usuario)
    if es_faltante:
        AsientoLinea.objects.create(asiento=asiento, orden=1, cuenta=param.cta_diferencia_caja, debe=monto, haber=0)
        AsientoLinea.objects.create(asiento=asiento, orden=2, cuenta=cuenta_caja, debe=0, haber=monto)
    else:
        AsientoLinea.objects.create(asiento=asiento, orden=1, cuenta=cuenta_caja, debe=monto, haber=0)
        AsientoLinea.objects.create(asiento=asiento, orden=2, cuenta=param.cta_diferencia_caja, debe=0, haber=monto)
    return asiento.asiento_id
