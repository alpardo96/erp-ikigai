"""Armado del reparto, Hoja de Ruta y Consolidado de Artículos (Plan 074 §7.5 y §7.6).

El reparto se arma DESPUÉS de facturar: sus paradas son comprobantes ya emitidos, y el
repartidor sale con la mercadería y el comprobante juntos.

POR QUÉ SE CONGELAN LOS IMPORTES AL CERRAR
------------------------------------------
El papel es la foto de un momento. Si la Hoja de Ruta recalculara el saldo y el cobro
mínimo cada vez que se reimprime, un cobro posterior cambiaría el número y el control
contra la firma del cliente dejaría de servir. Por eso `saldo_anterior`,
`saldo_disponible` y `cobro_minimo` se calculan una vez, al cerrar, y quedan grabados.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from core.models import ContadorDocumento
from core.services.numeracion import siguiente_numero
from verticalidades.distribucion.models import Reparto, RepartoParada

CERO = Decimal('0.00')


def comprobantes_sin_reparto(empresa_id, sucursal_id, zona_id=None):
    """Comprobantes emitidos que todavía no están en ningún reparto.

    Son los candidatos a cargar en el camión. Se excluyen los anulados: no se despacha
    mercadería de un comprobante que se dio de baja.
    """
    from verticalidades.distribucion.models import ExtensionPedidoDistribucion

    qs = (ExtensionPedidoDistribucion.objects
          .filter(preventa__empresa_id=empresa_id,
                  preventa__sucursal_id=sucursal_id,
                  venta__isnull=False,
                  paradas__isnull=True)
          .exclude(venta__estado=1)
          .select_related('venta', 'venta__cliente', 'venta__tipo',
                          'domicilio_entrega', 'zona', 'vendedor'))
    if zona_id:
        qs = qs.filter(zona_id=zona_id)
    return qs.order_by('venta__cliente__razon_social')


@transaction.atomic
def crear_reparto(empresa_id, sucursal_id, usuario, *, fecha=None, vehiculo=None,
                  zona=None, responsables=None, observaciones=None):
    """Abre un reparto vacío con su número correlativo."""
    numero = siguiente_numero(empresa_id, sucursal_id, ContadorDocumento.REPARTO)
    reparto = Reparto.objects.create(
        empresa_id=empresa_id, sucursal_id=sucursal_id,
        punto=sucursal_id, numero=numero,
        fecha=fecha or timezone.localdate(),
        vehiculo=vehiculo, zona=zona, observaciones=observaciones,
        creado_por=usuario, modificado_por=usuario)
    if responsables:
        reparto.responsables.set(responsables)
    return reparto


@transaction.atomic
def agregar_paradas(reparto, pedidos, usuario=None):
    """Suma comprobantes al reparto. Devuelve cuántos agregó.

    Un comprobante entra en UN solo reparto (`UniqueConstraint` sobre `venta`): si
    estuviera en dos, la mercadería se cargaría dos veces y el consolidado mentiría.
    """
    if not reparto.editable:
        raise ValueError("El reparto ya está cerrado: no se le pueden agregar paradas.")

    ultimo_orden = (reparto.paradas.aggregate(m=Sum('orden'))['m'] or 0)
    agregados = 0
    for pedido in pedidos:
        if not pedido.venta_id:
            continue
        if RepartoParada.objects.filter(venta_id=pedido.venta_id).exists():
            continue
        ultimo_orden += 1
        RepartoParada.objects.create(
            reparto=reparto, tipo=RepartoParada.ENTREGA,
            pedido=pedido, venta=pedido.venta,
            cliente=pedido.venta.cliente,
            # Congelado, igual que los importes: si el cliente cambia su domicilio
            # después, el papel que firmó tiene que seguir diciendo dónde se descargó.
            domicilio_texto=(pedido.domicilio_entrega_texto
                             or pedido.venta.cliente_domicilio),
            orden=ultimo_orden)
        agregados += 1
    return agregados


@transaction.atomic
def agregar_parada_de_cobranza(reparto, cliente, usuario=None, domicilio=None):
    """Suma a la hoja de ruta un cliente con saldo que NO hizo pedido (Plan 076 §A).

    No lleva mercadería: el repartidor pasa sólo a cobrarle. Por eso no tiene pedido ni
    comprobante y no aparece en el Consolidado de Artículos. Si todas las paradas del
    reparto son de esta clase, el reparto es una ruta de cobranza pura.
    """
    from verticalidades.distribucion.services.domicilios import asegurar_domicilio_principal

    if not reparto.editable:
        raise ValueError("El reparto ya está cerrado: no se le pueden agregar paradas.")
    if reparto.paradas.filter(tipo=RepartoParada.COBRANZA, cliente=cliente).exists():
        raise ValueError(
            f"{cliente.razon_social} ya está en este reparto como parada de cobranza.")

    domicilio = domicilio or asegurar_domicilio_principal(cliente, reparto.empresa_id)
    ultimo_orden = (reparto.paradas.aggregate(m=Sum('orden'))['m'] or 0) + 1
    return RepartoParada.objects.create(
        reparto=reparto, tipo=RepartoParada.COBRANZA,
        pedido=None, venta=None, cliente=cliente,
        domicilio_texto=(domicilio.texto_completo if domicilio else cliente.domicilio),
        orden=ultimo_orden)


@transaction.atomic
def quitar_parada(parada):
    if not parada.reparto.editable:
        raise ValueError("El reparto ya está cerrado: no se le pueden quitar paradas.")
    parada.delete()


@transaction.atomic
def cerrar_reparto(reparto, usuario=None):
    """Cierra el reparto y CONGELA los importes de cada parada.

    A partir de acá la Hoja de Ruta se puede reimprimir las veces que haga falta y va a
    decir siempre lo mismo, que es lo que permite controlarla contra la firma del cliente.
    """
    from verticalidades.distribucion.services.facturacion import evaluar_credito

    if reparto.estado != Reparto.ARMADO:
        raise ValueError("El reparto ya fue cerrado.")
    if not reparto.paradas.exists():
        raise ValueError("El reparto no tiene paradas: no hay nada que cargar.")

    from verticalidades.distribucion.services.credito import esta_bloqueado

    for parada in reparto.paradas.select_related('venta', 'cliente'):
        cliente = parada.cliente
        saldo_actual = Decimal(str(cliente.saldo or 0))
        limite = Decimal(str(cliente.limite or 0))

        if parada.es_cobranza:
            # NO HAY PALANCA: no se entrega mercadería, así que no hay nada que condicionar.
            # Se congela el saldo como DATO para ir a reclamar, y el cobro mínimo es cero.
            # Lo que el cliente entregue —si entrega algo— se imputa por el FIFO estándar.
            parada.saldo_anterior = saldo_actual
            parada.saldo_disponible = limite - saldo_actual
            parada.cobro_minimo = CERO
            parada.save(update_fields=['saldo_anterior', 'saldo_disponible', 'cobro_minimo'])
            continue

        total = Decimal(str(parada.venta.total or 0))
        # El saldo del cliente YA incluye este comprobante (se facturó antes de armar el
        # reparto), así que el saldo anterior es el de antes de esta carga.
        disponible = limite - saldo_actual

        if esta_bloqueado(cliente):
            disponible = min(disponible, -total)

        parada.saldo_anterior = saldo_actual - total
        parada.saldo_disponible = disponible
        parada.cobro_minimo = max(CERO, -disponible)
        parada.save(update_fields=['saldo_anterior', 'saldo_disponible', 'cobro_minimo'])

    reparto.estado = Reparto.CERRADO
    reparto.modificado_por = usuario
    reparto.save(update_fields=['estado', 'modificado_por'])

    # El camión sale y a partir de ahora puede entrar plata por este reparto: la caja
    # recaudadora se abre acá para que ninguna cobranza quede sin sesión donde caer.
    if usuario is not None:
        from verticalidades.distribucion.services.caja_reparto import abrir_caja_del_reparto
        abrir_caja_del_reparto(reparto, usuario)
    return reparto


def hoja_de_ruta(reparto):
    """Paradas ORDENADAS ALFABÉTICAMENTE POR CLIENTE, como el papel del sistema anterior.

    El orden alfabético es el del control: el repartidor busca al cliente por nombre, no
    por número de comprobante.
    """
    return (reparto.paradas
            .select_related('cliente', 'venta', 'venta__tipo',
                            'pedido', 'pedido__domicilio_entrega', 'pedido__vendedor')
            .prefetch_related('venta__items__producto')
            # Por el cliente PROPIO de la parada y no por el del comprobante: una parada
            # de cobranza no tiene comprobante y quedaría al final de la lista.
            .order_by('cliente__razon_social'))


def consolidado(reparto):
    """Total por artículo de todo lo que se carga al vehículo (hoja 4 del papel).

    Devuelve `(filas, totales)`. Cada fila trae el producto, la cantidad y los kilos.
    Sin `peso_unitario_kg` cargado los kilos dan 0: el reporte no rompe, pero avisa.
    """
    from facturacion.models import VentaItem

    # Sólo las paradas de ENTREGA aportan artículos. Un reparto de pura cobranza da
    # consolidado vacío, que es exactamente lo correcto: no se carga nada al vehículo.
    ventas = reparto.paradas.exclude(venta__isnull=True).values_list('venta_id', flat=True)
    items = (VentaItem.objects
             .filter(venta_id__in=ventas)
             .exclude(venta__estado=1)
             .select_related('producto'))

    acumulado = {}
    for item in items:
        clave = item.producto_id
        fila = acumulado.setdefault(clave, {
            'producto': item.producto, 'cantidad': CERO, 'kilos': CERO})
        cantidad = Decimal(str(item.cantidad or 0))
        fila['cantidad'] += cantidad
        fila['kilos'] += cantidad * Decimal(str(item.producto.peso_unitario_kg or 0))

    filas = sorted(acumulado.values(), key=lambda f: f['producto'].id)
    totales = {
        'cantidad': sum((f['cantidad'] for f in filas), CERO),
        'kilos': sum((f['kilos'] for f in filas), CERO),
        'articulos': len(filas),
        'sin_peso': sum(1 for f in filas if not f['producto'].peso_unitario_kg),
    }

    capacidad = Decimal(str(reparto.vehiculo.capacidad_kg or 0)) if reparto.vehiculo else CERO
    totales['capacidad_kg'] = capacidad
    totales['excede_capacidad'] = bool(capacidad and totales['kilos'] > capacidad)

    return filas, totales


def totales_hoja_de_ruta(reparto):
    """Resumen del pie de la hoja de ruta."""
    paradas = list(reparto.paradas.select_related('venta'))
    con_entrega = [p for p in paradas if p.venta_id]
    return {
        'paradas': len(paradas),
        'paradas_de_cobranza': len(paradas) - len(con_entrega),
        'total': sum((Decimal(str(p.venta.total or 0)) for p in con_entrega), CERO),
        # Las paradas de cobranza aportan CERO: no hay mercadería con que exigir.
        'cobro_minimo': sum((Decimal(str(p.cobro_minimo or 0)) for p in paradas), CERO),
        # Lo que se va a reclamar en las paradas de cobranza, como dato del pie.
        'saldo_a_reclamar': sum((Decimal(str(p.saldo_anterior or 0))
                                 for p in paradas if not p.venta_id), CERO),
    }
