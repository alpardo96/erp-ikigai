"""Entrega, devoluciones y notas de crédito (Plan 074 §7.10).

El comprobante ya está emitido cuando el camión sale, así que **todo lo que no se
entrega llega con la factura hecha**. Deja de ser un caso marginal: es parte del
circuito diario.

EL ORDEN IMPORTA: PRIMERO SE CUENTA, DESPUÉS SE ACREDITA
--------------------------------------------------------
1. En la calle, el repartidor marca la parada como no entregada, con motivo y observación.
2. En el depósito se emite la **Recepción de Devoluciones**, numerada, donde el encargado
   cuenta lo que efectivamente volvió.
3. Desde esa recepción se emite la **Nota de Crédito**, con todo precargado.

Si se acreditara primero y se contara después, se le acreditaría al cliente mercadería
que puede no haber vuelto, y el descalce aparecería recién en la conciliación. Es la
misma lógica por la que el Informe de Recepción precede a la registración de la factura
del proveedor.

EL STOCK LO DEVUELVE LA NOTA DE CRÉDITO, NO LA RECEPCIÓN
--------------------------------------------------------
`productos.services.stock_service` deriva el stock de los COMPROBANTES, y las notas de
crédito ya invierten el movimiento por el `signo = -1` de su tipo. Hacer que la recepción
también moviera stock lo contaría dos veces. La recepción es el control físico; la NC es
el hecho que mueve el inventario.

Consecuencia conocida: la mercadería marcada como NO APTA para reventa vuelve igual al
stock, porque la NC acredita todo lo devuelto —el cliente no paga lo que devolvió, esté
roto o no—. Darla de baja es un AJUSTE DE INVENTARIO, que es el término que
`stock_service` todavía no tiene. Queda registrado en `apto_reventa` para cuando exista.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.models import ContadorDocumento
from core.services.numeracion import siguiente_numero
from verticalidades.distribucion.models import (MotivoDevolucion, NotaCreditoDistribucion,
                                 RecepcionDevolucion, RecepcionDevolucionItem,
                                 RepartoParada)

CERO = Decimal('0.00')


def _validar_es_de_entrega(parada):
    """Entrega y devoluciones sólo existen donde hubo mercadería (Plan 076 §A)."""
    if parada.es_cobranza:
        raise ValueError(
            "Es una parada de sólo cobranza: no se entrega mercadería, así que no hay "
            "entrega que registrar ni devolución que recibir.")


@transaction.atomic
def marcar_entregada(parada, usuario=None):
    """La entrega salió bien: no hay nada más que hacer con esta parada."""
    _validar_es_de_entrega(parada)
    parada.estado_entrega = RepartoParada.ENTREGADA
    parada.save(update_fields=['estado_entrega'])
    return parada


@transaction.atomic
def marcar_no_entregada(parada, observacion=None):
    """El cliente no recibió. Queda pendiente de que la mercadería vuelva al depósito."""
    _validar_es_de_entrega(parada)
    parada.estado_entrega = RepartoParada.NO_ENTREGADA
    if observacion:
        parada.observacion_repartidor = observacion
    parada.save(update_fields=['estado_entrega', 'observacion_repartidor'])
    return parada


def paradas_por_recibir(reparto):
    """Paradas marcadas como no entregadas que todavía no tienen recepción vigente."""
    return (reparto.paradas
            .filter(tipo=RepartoParada.ENTREGA,
                    estado_entrega=RepartoParada.NO_ENTREGADA)
            .exclude(recepciones__estado__in=[RecepcionDevolucion.BORRADOR,
                                              RecepcionDevolucion.CONFIRMADA])
            .select_related('venta', 'cliente', 'pedido'))


@transaction.atomic
def crear_recepcion(parada, usuario, *, entregado_por=None, observaciones=None):
    """Abre la Recepción de Devoluciones de UNA parada, con su número correlativo."""
    _validar_es_de_entrega(parada)
    vigente = parada.recepciones.filter(
        estado__in=[RecepcionDevolucion.BORRADOR, RecepcionDevolucion.CONFIRMADA]).first()
    if vigente:
        return vigente

    reparto = parada.reparto
    numero = siguiente_numero(reparto.empresa_id, reparto.sucursal_id,
                              ContadorDocumento.RECEPCION_DEVOLUCION)
    return RecepcionDevolucion.objects.create(
        empresa_id=reparto.empresa_id, sucursal_id=reparto.sucursal_id,
        punto=reparto.sucursal_id, numero=numero,
        parada=parada, reparto=reparto,
        fecha=timezone.localdate(),
        recibido_por=usuario, entregado_por=entregado_por,
        observaciones=observaciones,
        creado_por=usuario, modificado_por=usuario)


@transaction.atomic
def cargar_items(recepcion, cantidades, motivo_por_item=None, observaciones=None):
    """Registra lo que efectivamente volvió. `cantidades` es {venta_item_id: cantidad}.

    Una cantidad en cero borra el renglón: el depósito contó y no volvió nada de ese
    artículo. `apto_reventa` se precarga desde el motivo.
    """
    from facturacion.models import VentaItem

    if not recepcion.editable:
        raise ValueError("La recepción ya fue confirmada: no se pueden cambiar las cantidades.")

    motivo_por_item = motivo_por_item or {}
    observaciones = observaciones or {}
    items_venta = {i.id: i for i in VentaItem.objects.filter(venta=recepcion.parada.venta)}

    for item_id, cantidad in cantidades.items():
        item_venta = items_venta.get(int(item_id))
        if not item_venta:
            continue

        cantidad = Decimal(str(cantidad or 0))
        if cantidad < CERO:
            raise ValueError("No se puede devolver una cantidad negativa.")
        if cantidad > Decimal(str(item_venta.cantidad)):
            raise ValueError(
                f"No se pueden devolver {cantidad} de {item_venta.producto.detalle}: "
                f"se entregaron {item_venta.cantidad}.")

        if cantidad == CERO:
            RecepcionDevolucionItem.objects.filter(
                recepcion=recepcion, venta_item=item_venta).delete()
            continue

        motivo_id = motivo_por_item.get(str(item_id)) or motivo_por_item.get(int(item_id))
        motivo = (MotivoDevolucion.objects.filter(
            id=motivo_id, empresa_id=recepcion.empresa_id).first() if motivo_id else None)
        if not motivo:
            raise ValueError(
                f"Falta el motivo de devolución de {item_venta.producto.detalle}.")

        RecepcionDevolucionItem.objects.update_or_create(
            recepcion=recepcion, venta_item=item_venta,
            defaults={
                'cantidad': cantidad,
                'motivo': motivo,
                # El motivo sabe si la mercadería vuelve al stock vendible: no se deja
                # librado al criterio de quien carga.
                'apto_reventa': motivo.sugiere_apto_reventa,
                'observacion': observaciones.get(str(item_id)) or None,
            })
    return recepcion


@transaction.atomic
def confirmar_recepcion(recepcion, usuario=None):
    """Cierra el conteo. A partir de acá se puede emitir la Nota de Crédito."""
    if recepcion.estado != RecepcionDevolucion.BORRADOR:
        raise ValueError("La recepción ya fue confirmada o anulada.")
    if not recepcion.items.exists():
        raise ValueError("La recepción no tiene artículos: no hay nada que recibir.")

    recepcion.estado = RecepcionDevolucion.CONFIRMADA
    recepcion.modificado_por = usuario
    recepcion.save(update_fields=['estado', 'modificado_por'])
    return recepcion


@transaction.atomic
def emitir_nota_credito(recepcion, usuario, *, motivo=None, observacion=None):
    """Emite la NC a partir de lo que el depósito contó.

    El stock vuelve por acá: la NC lleva `signo = -1` y `stock_service` invierte el
    movimiento. La recepción es el control físico; este es el hecho que mueve inventario.
    """
    from facturacion.services.notas_credito import emitir_nota_credito_desde_venta

    if recepcion.estado != RecepcionDevolucion.CONFIRMADA:
        raise ValueError(
            "Primero hay que confirmar la recepción: sólo se acredita mercadería que "
            "efectivamente volvió al depósito.")
    if recepcion.nota_credito_id:
        return recepcion.nota_credito

    venta_origen = recepcion.parada.venta
    items = {i.venta_item_id: i.cantidad for i in recepcion.items.all()}
    if not items:
        raise ValueError("La recepción no tiene artículos.")

    # Serie NO FISCAL: el número lo da el contador. En la fiscal lo da ARCA junto al CAE.
    numero = punto = None
    if venta_origen.condic == 2:
        punto = recepcion.sucursal_id
        numero = siguiente_numero(recepcion.empresa_id, punto,
                                  ContadorDocumento.VENTA_NCI)

    nota = emitir_nota_credito_desde_venta(
        venta_origen, items, usuario, numero_nc=numero, punto_nc=punto)

    motivo = motivo or recepcion.items.first().motivo
    NotaCreditoDistribucion.objects.create(
        nota_credito=nota, venta_origen=venta_origen, parada=recepcion.parada,
        recepcion=recepcion, motivo=motivo, observacion=observacion,
        momento=NotaCreditoDistribucion.EN_ENTREGA)

    recepcion.nota_credito = nota
    recepcion.save(update_fields=['nota_credito'])
    return nota


def conciliacion(reparto):
    """Confronta lo ACREDITADO al cliente con lo RECIBIDO en el depósito.

    Es el control de fondo de todo el circuito de devoluciones: un descalce señala
    mercadería que se acreditó pero no volvió, o que volvió sin acreditarse. Sin este par
    de documentos, la devolución es un acto de fe.
    """
    filas = []
    for recepcion in (reparto.recepciones
                      .exclude(estado=RecepcionDevolucion.ANULADA)
                      .select_related('parada__venta__cliente', 'nota_credito')
                      .prefetch_related('items__venta_item__producto')):
        recibido = recepcion.total_devuelto
        acreditado = (Decimal(str(recepcion.nota_credito.total))
                      if recepcion.nota_credito_id else CERO)
        filas.append({
            'recepcion': recepcion,
            'cliente': recepcion.parada.cliente,
            'recibido': recibido,
            'acreditado': acreditado,
            'diferencia': acreditado - recibido,
            'concilia': abs(acreditado - recibido) < Decimal('0.01'),
            'sin_nc': not recepcion.nota_credito_id,
        })

    # Paradas no entregadas que todavía no tienen recepción: mercadería que el cliente
    # no recibió y que nadie declaró de vuelta en el depósito.
    pendientes = list(paradas_por_recibir(reparto))

    return {
        'filas': filas,
        'pendientes_de_recibir': pendientes,
        'total_recibido': sum((f['recibido'] for f in filas), CERO),
        'total_acreditado': sum((f['acreditado'] for f in filas), CERO),
        'con_descalce': [f for f in filas if not f['concilia']],
    }
