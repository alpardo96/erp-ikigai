"""Facturación masiva de pedidos de distribución (Plan 074 §7.4).

Es el corazón del módulo: al arranque del día se toman los pedidos y se emiten los
comprobantes que después salen en el camión.

LA REGLA DEL SALDO DISPONIBLE NEGATIVO
--------------------------------------
    saldo_disponible = limite − saldo    (POSTERIOR a facturar esta carga)
    cobro_minimo     = max(0, −saldo_disponible)

Absorbe los cuatro casos del negocio sin un solo condicional especial:

    | Situación                   | Disponible       | Cobro mínimo | Condición        |
    |-----------------------------|------------------|--------------|------------------|
    | Entra holgado en el límite  | positivo         | 0            | CUENTA CORRIENTE |
    | Se pasa parcialmente        | negativo parcial | el excedente | CUENTA CORRIENTE |
    | `limite = 0` (sólo contado) | −total           | el total     | CONTADO          |
    | `bloqueado_credito`         | se fuerza −total | el total     | CONTADO          |

`condicion_venta` es un derivado del mismo cálculo, no una decisión aparte: es CONTADO
exactamente cuando el cobro mínimo cubre todo el comprobante.

LA FECHA LA PONE EL SISTEMA. No se recibe ni se ofrece: es la del día de emisión.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.models import ContadorDocumento
from core.services.numeracion import siguiente_numero
from verticalidades.distribucion.models import ExtensionPedidoDistribucion
from productos.services.stock_service import ESTADOS_PEDIDO_COMPROMETEN

CERO = Decimal('0.00')

CONTADO = 'CONTADO'
CTA_CTE = 'CTA_CTE'

# Código de `TipoComprobante` según la condición de IVA del receptor.
TIPO_FISCAL_POR_IVA = {
    'RESPONSABLE INSCRIPTO': '001',   # Factura A
    'MONOTRIBUTO': '006',             # Factura B
    'EXENTO': '006',
    'CONSUMIDOR FINAL': '006',
}
TIPO_FISCAL_DEFECTO = '011'           # Factura C
CODIGO_PRE = 'PRE'


def pedidos_pendientes(empresa_id, sucursal_id):
    """Pedidos listos para facturar: tomados, vivos y sin comprobante emitido."""
    return (ExtensionPedidoDistribucion.objects
            .filter(preventa__empresa_id=empresa_id,
                    preventa__sucursal_id=sucursal_id,
                    preventa__estado__in=ESTADOS_PEDIDO_COMPROMETEN,
                    venta__isnull=True)
            .select_related('preventa', 'preventa__cliente',
                            'preventa__cliente__distribuidora',
                            'vendedor', 'domicilio_entrega', 'zona')
            .order_by('hora_carga'))


def evaluar_credito(cliente, total_pedido):
    """Aplica la regla del saldo disponible negativo a un pedido concreto.

    `total_pedido` es lo que se va a facturar ahora; el saldo del cliente todavía no lo
    incluye, así que se lo suma para mirar la foto POSTERIOR a la facturación.
    """
    from verticalidades.distribucion.services.credito import esta_bloqueado

    limite = Decimal(str(cliente.limite or 0))
    saldo_posterior = Decimal(str(cliente.saldo or 0)) + Decimal(str(total_pedido or 0))
    disponible = limite - saldo_posterior

    # Un cliente bloqueado no tiene crédito, sin importar el límite cargado: se fuerza el
    # peor caso para que el comprobante salga de contado por el total.
    bloqueado = esta_bloqueado(cliente)
    if bloqueado:
        disponible = min(disponible, -Decimal(str(total_pedido or 0)))

    cobro_minimo = max(CERO, -disponible)
    return {
        'limite': limite,
        'saldo_anterior': Decimal(str(cliente.saldo or 0)),
        'total': Decimal(str(total_pedido or 0)),
        'saldo_disponible': disponible,
        'cobro_minimo': cobro_minimo,
        'bloqueado': bloqueado,
        # CONTADO exactamente cuando hay que cobrar todo el comprobante para dejarlo.
        'condicion_venta': CONTADO if cobro_minimo >= Decimal(str(total_pedido or 0)) else CTA_CTE,
    }


def previsualizar(empresa_id, sucursal_id):
    """Arma la grilla que el usuario revisa ANTES de emitir.

    Que se pueda mirar antes de facturar no es un lujo: una vez emitido el comprobante
    fiscal, corregirlo cuesta una nota de crédito.
    """
    filas = []
    for pedido in pedidos_pendientes(empresa_id, sucursal_id):
        preventa = pedido.preventa
        credito = evaluar_credito(preventa.cliente, preventa.total)
        filas.append({
            'pedido': pedido,
            'preventa': preventa,
            'cliente': preventa.cliente,
            'total': preventa.total,
            'credito': credito,
            'items': preventa.items.count(),
        })
    return filas


def _tipo_comprobante(condic_destino, cliente):
    """Resuelve el `TipoComprobante`. Sin fallbacks silenciosos (Plan 075)."""
    from facturacion.models import TipoComprobante

    if condic_destino == 2:
        tipo = TipoComprobante.objects.filter(codigo=CODIGO_PRE).first()
        if not tipo:
            raise ValueError(
                "Falta configurar el tipo de comprobante 'PRE'. Cargalo en "
                "Configuración → Tipos de Comprobante antes de facturar.")
        return tipo

    codigo = TIPO_FISCAL_POR_IVA.get(cliente.condicion_iva, TIPO_FISCAL_DEFECTO)
    tipo = TipoComprobante.objects.filter(codigo=codigo).first()
    if not tipo:
        raise ValueError(
            f"Falta configurar el tipo de comprobante '{codigo}' que corresponde a un "
            f"cliente {cliente.condicion_iva}.")
    return tipo


def _calcular_importes(preventa, es_fiscal):
    """Neto, IVA y alícuotas del comprobante, ANTES de persistir nada.

    Se calcula primero porque el número de la serie fiscal lo da ARCA y ARCA necesita los
    importes: guardar la venta con un número provisorio para corregirlo después dejaría,
    aunque sea un instante, dos comprobantes con el mismo número en la misma serie.
    """
    renglones, alicuotas = [], {}
    neto_total = iva_total = CERO

    for item in preventa.items.select_related('producto').all():
        # El PRE no discrimina IVA: no es un comprobante fiscal.
        alic = Decimal(str(item.producto.alic_iva_porc)) if es_fiscal else CERO
        total_item = Decimal(str(item.total))
        neto_item = (total_item / (Decimal('1') + alic / Decimal('100'))).quantize(Decimal('0.01'))
        iva_item = total_item - neto_item

        renglones.append({'item': item, 'alicuota': alic, 'total': total_item})
        neto_total += neto_item
        iva_total += iva_item
        if alic > 0:
            acumulado = alicuotas.setdefault(alic, {'base': CERO, 'iva': CERO})
            acumulado['base'] += neto_item
            acumulado['iva'] += iva_item

    lista_alicuotas = [{
        'id_iva': _id_arca_alicuota(alic),
        'alicuota': alic,
        'base_imponible': importes['base'],
        'importe_iva': importes['iva'],
    } for alic, importes in alicuotas.items()]

    return renglones, lista_alicuotas, neto_total, iva_total


@transaction.atomic
def facturar_pedido(pedido, usuario, *, modo_prueba=True):
    """Emite el comprobante de UN pedido y lo deja vinculado.

    Todo en una transacción: si falla el CAE, no queda un pedido a medio facturar.
    """
    from facturacion.models import ClienteProveedor, Venta, VentaAlicuotaIva, VentaItem
    from facturacion.services.emision_arca import emitir_cae

    preventa = pedido.preventa
    if pedido.venta_id:
        return pedido.venta
    if not preventa.items.exists():
        raise ValueError(f"El pedido {pedido.numero_formateado} no tiene artículos.")

    # Se bloquea el cliente: dos pedidos suyos facturándose a la vez leerían el mismo
    # saldo y los dos creerían entrar en el límite.
    cliente = ClienteProveedor.objects.select_for_update().get(pk=preventa.cliente_id)

    credito = evaluar_credito(cliente, preventa.total)
    tipo = _tipo_comprobante(pedido.condic_destino, cliente)
    es_fiscal = pedido.condic_destino == 1

    renglones, alicuotas, neto_total, iva_total = _calcular_importes(preventa, es_fiscal)
    total = neto_total + iva_total

    venta = Venta(
        empresa_id=preventa.empresa_id,
        sucursal_id=preventa.sucursal_id,
        usuario=usuario,
        cliente=cliente,
        cliente_razon_social=cliente.razon_social,
        cliente_cuit=cliente.cuit,
        cliente_domicilio=cliente.domicilio,
        tipo=tipo,
        # La fecha la pone el SISTEMA: es la del día de emisión, no se elige.
        fecha=timezone.localdate(),
        periodo=timezone.localdate().strftime('%Y%m'),
        # 1 = Real (fiscal) · 2 = Presupuestado (PRE, no fiscal). El asiento hereda esto.
        condic=pedido.condic_destino,
        condicion_venta=credito['condicion_venta'],
        moneda='PES',
        cotizacion=Decimal('1.0000'),
        neto=neto_total, iva=iva_total, total=total, saldo=total,
    )

    # --- NUMERACIÓN: se resuelve ANTES del primer save ---
    if not es_fiscal:
        # Serie no fiscal: la gobierna el sistema, punto = sucursal emisora.
        venta.punto = preventa.sucursal_id
        venta.numero = siguiente_numero(
            preventa.empresa_id, preventa.sucursal_id, ContadorDocumento.VENTA_PRE)
    else:
        venta.punto = _punto_fiscal(preventa)
        if modo_prueba:
            # CAE ficticio para probar el circuito sin tocar ARCA. NO usar en producción:
            # un comprobante con este CAE figura como autorizado y no lo está.
            venta.cae = "12345678901234"
            venta.vto_cae = timezone.localdate()
            venta.numero = siguiente_numero(
                preventa.empresa_id, venta.punto, ContadorDocumento.VENTA_FISCAL)
        else:
            # ARCA es la autoridad de la serie: el número sale de su respuesta.
            emitir_cae(venta, alicuotas=alicuotas)

    venta.save()

    for renglon in renglones:
        item = renglon['item']
        VentaItem.objects.create(
            venta=venta, producto=item.producto, concepto=item.producto.detalle,
            cantidad=item.cantidad, precio_unitario=item.precio_unitario,
            porcentaje_descuento=item.porcentaje_descuento,
            iva_alicuota=renglon['alicuota'], total=renglon['total'])

    for alic in alicuotas:
        VentaAlicuotaIva.objects.create(
            venta=venta, id_iva=alic['id_iva'], alicuota=alic['alicuota'],
            base_imponible=alic['base_imponible'], importe_iva=alic['importe_iva'])

    # Este save dispara la señal con los ítems ya creados, que es lo que genera el
    # asiento. Guardar antes de tener ítems deja el comprobante SIN registración: es el
    # defecto que tenía el lote de ESTUDIO.
    venta.save()

    pedido.venta = venta
    pedido.save(update_fields=['venta'])

    # FACTURADO: deja de comprometer stock y de descontar crédito. El stock real lo
    # descuenta la señal de `VentaItem`.
    preventa.estado = 3
    preventa.save(update_fields=['estado'])

    return venta


def _punto_fiscal(preventa):
    """Punto de venta autorizado por ARCA para la sucursal que emite."""
    from empresas.models import PuntoVenta

    punto = (PuntoVenta.objects
             .filter(empresa_id=preventa.empresa_id, sucursal_id=preventa.sucursal_id,
                     activo=True)
             .order_by('-caja_mostrador_default', 'numero').first())
    if not punto:
        raise ValueError(
            "La sucursal no tiene punto de venta habilitado para emitir comprobantes "
            "fiscales. Configuralo en Configuración → Puntos de Venta.")
    return punto.numero


def _id_arca_alicuota(alicuota):
    """Código de alícuota de ARCA. 5 = 21 % es el más frecuente."""
    return {Decimal('0.00'): 3, Decimal('10.50'): 4, Decimal('21.00'): 5,
            Decimal('27.00'): 6, Decimal('5.00'): 8, Decimal('2.50'): 9}.get(alicuota, 5)


def facturar_lote(pedidos, usuario, *, modo_prueba=True):
    """Factura varios pedidos y devuelve el resultado de cada uno.

    Cada pedido va en SU PROPIA transacción (`facturar_pedido` es atómica) y los errores
    se acumulan: un cliente mal configurado no puede frenar el reparto de todos los demás.
    Es la diferencia con el lote de ESTUDIO, donde el `atomic` envolvía el bucle entero y
    el primer error abortaba la transacción completa.
    """
    from facturacion.services.emision_arca import ErrorEmisionARCA

    resultados = []
    for pedido in pedidos:
        try:
            venta = facturar_pedido(pedido, usuario, modo_prueba=modo_prueba)
            resultados.append({
                'pedido': pedido, 'ok': True, 'venta': venta,
                'mensaje': f"{venta.tipo.detalle} {venta.punto:04d}-{venta.numero:08d}",
            })
        except (ErrorEmisionARCA, ValueError) as error:
            resultados.append({'pedido': pedido, 'ok': False, 'venta': None,
                               'mensaje': str(error)})
        except Exception as error:   # noqa: BLE001 — se reporta y se sigue con el resto
            resultados.append({'pedido': pedido, 'ok': False, 'venta': None,
                               'mensaje': f"Error inesperado: {error}"})
    return resultados
