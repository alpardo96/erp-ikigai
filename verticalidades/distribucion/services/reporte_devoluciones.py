"""Reporte de devoluciones (Plan 074 §7.10, fase 8).

Definición del plan: *"por período, motivo, momento, repartidor, cliente y producto: muestra
si el problema es de crédito, de calidad, de carga o de un repartidor puntual."*

LA PREGUNTA QUE RESPONDE NO ES CUÁNTO, ES POR QUÉ
--------------------------------------------------
Un total de devoluciones no sirve para decidir nada. Lo que cambia una conducta es ver que
el 60 % son «negocio cerrado» —problema de agenda de visitas—, o que se concentran en un
repartidor, o en un producto que llega roto. Por eso el reporte es un conjunto de cortes
sobre los mismos renglones, y no una lista.

EL GRANO ES EL RENGLÓN DE LA RECEPCIÓN, NO LA NOTA DE CRÉDITO
-------------------------------------------------------------
`RecepcionDevolucionItem` es el único lugar donde conviven motivo, producto, cantidad y
`apto_reventa`. La NC acredita un importe; la recepción explica qué volvió y por qué.

Las NC de **PRE-CARGA** —el cliente anula antes de que salga el camión— no pasan por ninguna
recepción, porque la mercadería nunca se cargó. Se listan aparte, con su propio total: si se
las mezclara con lo devuelto se estaría contando como «vuelto del reparto» algo que nunca
salió, y si se las omitiera desaparecerían del análisis.
"""
from decimal import Decimal

from django.utils import timezone

CERO = Decimal('0.00')


def _porcentaje(parte, total):
    if not total:
        return CERO
    return (parte * Decimal('100') / total).quantize(Decimal('0.01'))


def _repartidor_de(recepcion):
    """Quién trajo la devolución.

    `entregado_por` es opcional, así que cuando falta se cae a los responsables del reparto:
    si hay exactamente uno, la devolución es suya sin ambigüedad. Con varios responsables no
    se le atribuye a ninguno —repartir la culpa por partes iguales sería inventar un dato—,
    y queda como «Sin identificar», que es lo que efectivamente se sabe.
    """
    if recepcion.entregado_por_id:
        return recepcion.entregado_por
    responsables = list(recepcion.reparto.responsables.all())
    return responsables[0] if len(responsables) == 1 else None


def reporte(empresa_id, *, desde=None, hasta=None, motivo_id=None, repartidor_id=None,
            cliente_id=None, producto_id=None, solo_no_apto=False):
    """Devuelve los cortes del reporte sobre las recepciones confirmadas del período."""
    from verticalidades.distribucion.models import (NotaCreditoDistribucion, RecepcionDevolucion,
                                     RecepcionDevolucionItem)

    hasta = hasta or timezone.localdate()

    items = (RecepcionDevolucionItem.objects
             .filter(recepcion__empresa_id=empresa_id)
             # Una recepción anulada no devolvió nada: contarla inflaría todos los cortes.
             .exclude(recepcion__estado=RecepcionDevolucion.ANULADA)
             .select_related('motivo', 'venta_item__producto',
                             'recepcion__parada__cliente',
                             'recepcion__entregado_por', 'recepcion__nota_credito')
             .prefetch_related('recepcion__reparto__responsables'))

    if desde:
        items = items.filter(recepcion__fecha__gte=desde)
    if hasta:
        items = items.filter(recepcion__fecha__lte=hasta)
    if motivo_id:
        items = items.filter(motivo_id=motivo_id)
    if cliente_id:
        items = items.filter(recepcion__parada__cliente_id=cliente_id)
    if producto_id:
        items = items.filter(venta_item__producto_id=producto_id)
    if solo_no_apto:
        items = items.filter(apto_reventa=False)

    por_motivo, por_repartidor, por_cliente, por_producto = {}, {}, {}, {}
    total_importe, total_cantidad, total_no_apto = CERO, CERO, CERO
    filas = []

    for item in items:
        repartidor = _repartidor_de(item.recepcion)
        if repartidor_id and (not repartidor or repartidor.id != int(repartidor_id)):
            continue

        cantidad = Decimal(str(item.cantidad or 0))
        importe = item.subtotal
        cliente = item.recepcion.parada.cliente
        producto = item.venta_item.producto

        total_importe += importe
        total_cantidad += cantidad
        if not item.apto_reventa:
            total_no_apto += importe

        _acumular(por_motivo, item.motivo, cantidad, importe)
        _acumular(por_repartidor, repartidor, cantidad, importe)
        _acumular(por_cliente, cliente, cantidad, importe)
        _acumular(por_producto, producto, cantidad, importe)

        filas.append({
            'recepcion': item.recepcion,
            'fecha': item.recepcion.fecha,
            'cliente': cliente,
            'repartidor': repartidor,
            'producto': producto,
            'cantidad': cantidad,
            'importe': importe,
            'motivo': item.motivo,
            'apto_reventa': item.apto_reventa,
            'observacion': item.observacion,
        })

    # Las anulaciones ANTES de cargar el camión: la mercadería nunca salió, así que no hay
    # recepción. Van aparte para no contaminar los cortes de lo que sí volvió.
    pre_carga = list(NotaCreditoDistribucion.objects
                     .filter(venta_origen__empresa_id=empresa_id,
                             momento=NotaCreditoDistribucion.PRE_CARGA)
                     .exclude(nota_credito__estado=1)
                     .select_related('nota_credito', 'motivo', 'venta_origen__cliente'))
    if desde:
        pre_carga = [n for n in pre_carga if n.nota_credito.fecha >= desde]
    if hasta:
        pre_carga = [n for n in pre_carga if n.nota_credito.fecha <= hasta]

    return {
        'filas': sorted(filas, key=lambda f: (f['fecha'], f['recepcion'].numero),
                        reverse=True),
        'por_motivo': _ordenar(por_motivo, total_importe),
        'por_repartidor': _ordenar(por_repartidor, total_importe),
        'por_cliente': _ordenar(por_cliente, total_importe)[:20],
        'por_producto': _ordenar(por_producto, total_importe)[:20],
        'total_importe': total_importe,
        'total_cantidad': total_cantidad,
        'total_no_apto': total_no_apto,
        # Lo que volvió roto es pérdida, no una devolución más: merece su propio número.
        'porcentaje_no_apto': _porcentaje(total_no_apto, total_importe),
        'pre_carga': pre_carga,
        'total_pre_carga': sum(
            (abs(Decimal(str(n.nota_credito.total or 0))) for n in pre_carga), CERO),
    }


def _acumular(acumulador, clave, cantidad, importe):
    """Suma en el corte. `clave` puede ser None: es el grupo «Sin identificar»."""
    id_clave = clave.pk if clave is not None else None
    fila = acumulador.setdefault(id_clave, {
        'entidad': clave, 'cantidad': CERO, 'importe': CERO, 'casos': 0})
    fila['cantidad'] += cantidad
    fila['importe'] += importe
    fila['casos'] += 1


def _ordenar(acumulador, total):
    """De mayor a menor importe: el reporte tiene que empezar por lo que más pesa."""
    filas = list(acumulador.values())
    for fila in filas:
        fila['porcentaje'] = _porcentaje(fila['importe'], total)
    return sorted(filas, key=lambda f: f['importe'], reverse=True)
