"""Faltantes y asignación de stock escaso (Plan 074 §7.3).

EL PROBLEMA
-----------
Entre que el vendedor toma el pedido y la administración lo factura pasa la noche
entera. Durante esa ventana los pedidos compiten por el mismo stock, y a las 6 de la
mañana alguien tiene que decidir quién recibe cuánto.

Como la toma de pedidos es EN LÍNEA, el vendedor ve el stock actual y el riesgo es bajo:
se reduce a la demora entre consultar y grabar, y a pedidos casi simultáneos. Además el
pedido queda siempre **sujeto a disponibilidad** cuando el stock está ajustado. Pero
cuando el faltante existe, hay que resolverlo con un criterio explicable.

EL CRITERIO: ORDEN DE LLEGADA
-----------------------------
El que pidió primero se sirve primero, y el faltante lo absorben los últimos. Es el
único criterio que se le puede explicar a un vendedor sin discusión, y el que el usuario
eligió. La sugerencia es sólo un punto de partida: la pantalla permite ajustar a mano,
y cada ajuste queda auditado en `AjusteAsignacion`.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce

from verticalidades.distribucion.models import AjusteAsignacion, ExtensionPedidoDistribucion
from productos.models import StockSucursal
from productos.services.stock_service import ESTADOS_PEDIDO_COMPROMETEN

CERO = Decimal('0.00')
_DEC = DecimalField(max_digits=20, decimal_places=2)


def _pedidos_vivos(empresa_id, sucursal_id):
    """Pedidos que compiten por el stock: tomados y todavía sin facturar."""
    from facturacion.models import PreventaItem

    return PreventaItem.objects.filter(
        preventa__empresa_id=empresa_id,
        preventa__sucursal_id=sucursal_id,
        preventa__estado__in=ESTADOS_PEDIDO_COMPROMETEN,
    )


def detectar_faltantes(empresa_id, sucursal_id):
    """Productos cuyo stock no alcanza para cubrir todos los pedidos vivos.

    Devuelve una lista de dicts ordenada por déficit (el más grave primero):
        {producto, stock, pedido, deficit}

    `stock` es el FÍSICO (`StockSucursal.cantidad`), no el disponible: acá se compara
    contra la demanda total, y el comprometido ES esa demanda. Restarlo sería contarlo
    dos veces.
    """
    demanda = (_pedidos_vivos(empresa_id, sucursal_id)
               .values('producto_id')
               .annotate(pedido=Coalesce(Sum('cantidad', output_field=_DEC),
                                         Value(CERO), output_field=_DEC)))

    pedido_por_producto = {d['producto_id']: d['pedido'] or CERO for d in demanda}
    if not pedido_por_producto:
        return []

    stock_por_producto = {
        fila['producto_id']: fila['cantidad'] or CERO
        for fila in StockSucursal.objects.filter(
            producto_id__in=pedido_por_producto.keys(), sucursal_id=sucursal_id
        ).values('producto_id', 'cantidad')
    }

    from productos.models import Producto
    productos = {p.id: p for p in Producto.objects.filter(id__in=pedido_por_producto.keys())}

    faltantes = []
    for producto_id, pedido in pedido_por_producto.items():
        stock = stock_por_producto.get(producto_id, CERO)
        if pedido > stock:
            faltantes.append({
                'producto': productos.get(producto_id),
                'stock': stock,
                'pedido': pedido,
                'deficit': pedido - stock,
            })

    return sorted(faltantes, key=lambda f: f['deficit'], reverse=True)


def detalle_por_pedido(empresa_id, sucursal_id, producto_id):
    """Quién pidió ese producto, **en orden de llegada**.

    Cada fila trae lo necesario para decidir: el pedido, el cliente, el vendedor, la
    hora de carga y la cantidad. Es la base de la pantalla de asignación.
    """
    items = (_pedidos_vivos(empresa_id, sucursal_id)
             .filter(producto_id=producto_id)
             .select_related('preventa', 'preventa__cliente',
                             'preventa__distribucion',
                             'preventa__distribucion__vendedor')
             .order_by('preventa__distribucion__hora_carga', 'preventa_id'))

    filas = []
    for item in items:
        pedido = getattr(item.preventa, 'distribucion', None)
        filas.append({
            'item': item,
            'pedido': pedido,
            'cliente': item.preventa.cliente,
            'vendedor': pedido.vendedor if pedido else None,
            'hora_carga': pedido.hora_carga if pedido else None,
            'cantidad': item.cantidad,
        })
    return filas


def sugerir_asignacion(empresa_id, sucursal_id, producto_id):
    """Reparte el stock por ORDEN DE LLEGADA y devuelve las filas con su sugerencia.

    El primero se lleva todo lo que pidió mientras haya stock; el faltante lo absorben
    los últimos. Cada fila suma la clave `sugerido`.
    """
    filas = detalle_por_pedido(empresa_id, sucursal_id, producto_id)

    fila_stock = (StockSucursal.objects
                  .filter(producto_id=producto_id, sucursal_id=sucursal_id)
                  .values('cantidad').first())
    disponible = (fila_stock['cantidad'] if fila_stock else CERO) or CERO

    for fila in filas:
        pedida = Decimal(str(fila['cantidad']))
        asignada = min(pedida, disponible) if disponible > CERO else CERO
        fila['sugerido'] = asignada
        disponible -= asignada

    return filas


@transaction.atomic
def aplicar_asignacion(empresa_id, sucursal_id, producto_id, asignaciones, usuario,
                       observacion=None):
    """Aplica el reparto: recorta las cantidades de los ítems y audita cada cambio.

    `asignaciones` es {preventa_item_id: cantidad_asignada}.

    Sólo se toca lo que cambia: un ítem al que se le asigna lo que pedía no genera
    ajuste ni escritura. Devuelve la cantidad de ajustes registrados.
    """
    from facturacion.models import PreventaItem

    items = {
        item.id: item
        for item in (_pedidos_vivos(empresa_id, sucursal_id)
                     .filter(producto_id=producto_id, id__in=asignaciones.keys())
                     .select_related('preventa', 'preventa__distribucion'))
    }

    ajustes = 0
    preventas_tocadas = set()

    for item_id, cantidad in asignaciones.items():
        item = items.get(int(item_id))
        if not item:
            continue

        nueva = Decimal(str(cantidad))
        original = Decimal(str(item.cantidad))
        if nueva == original:
            continue
        if nueva < CERO:
            raise ValueError("No se puede asignar una cantidad negativa.")

        pedido = getattr(item.preventa, 'distribucion', None)
        if pedido:
            AjusteAsignacion.objects.create(
                empresa_id=empresa_id, pedido=pedido, producto_id=producto_id,
                cantidad_original=original, cantidad_asignada=nueva,
                usuario=usuario, observacion=observacion)

        if nueva == CERO:
            # Asignar cero es sacar el artículo del pedido: dejar un renglón en cero
            # ensuciaría el comprobante y la hoja de ruta con una línea sin sentido.
            item.delete()
        else:
            item.cantidad = nueva
            item.total = (nueva * Decimal(str(item.precio_unitario))
                          * (Decimal('1') - Decimal(str(item.porcentaje_descuento or 0)) / 100))
            item.save(update_fields=['cantidad', 'total'])

        preventas_tocadas.add(item.preventa)
        ajustes += 1

    # Los totales del pedido tienen que reflejar el recorte.
    for preventa in preventas_tocadas:
        preventa.recalcular_totales()

    return ajustes


def hay_faltantes(empresa_id, sucursal_id):
    """Atajo para el aviso del panel: ¿queda algo por resolver antes de facturar?"""
    return bool(detectar_faltantes(empresa_id, sucursal_id))
