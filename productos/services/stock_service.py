"""Stock por sucursal — cálculo y movimientos (Plan 053).

EL STOCK ES UN VALOR DERIVADO
-----------------------------
    stock_disponible = stock_inicial
                     + compras            (facturas que mueven stock ellas mismas)
                     + recepciones        (mercadería del proveedor, y la entrada de los
                                           remitos internos en la sucursal de destino)
                     − ventas
                     − remitos internos   (la salida, en la sucursal de origen)

`StockSucursal.cantidad` se materializa porque se lee en toda la operatoria, pero **no se ajusta
por delta**: se RECALCULA completo para ese (producto, sucursal) cada vez que algo lo afecta. Es
el mismo criterio con el que `contable.services.saldos.recalcular_saldo_cliente_proveedor()`
maneja la cuenta corriente.

Por qué se cambió: antes cada función sumaba o restaba un delta sobre el contador. Si una señal no
corría —un borrado masivo, una importación, un proceso que las desactiva, un error a mitad de
camino— el stock quedaba mal **y no había desde dónde reconstruirlo**. Ahora se corrige con
`recalcular_stock()` o con el comando `manage.py recalcular_stock`.

`MovimientoStock` se sigue escribiendo, pero como registro de AUDITORÍA: el stock no se deriva de
él, se deriva de los comprobantes.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce

from productos.models import MovimientoStock, StockSucursal

logger = logging.getLogger(__name__)

CERO = Decimal('0.00')
_DEC = DecimalField(max_digits=20, decimal_places=2)


# ---------------------------------------------------------------------------
# Los términos de la fórmula
# ---------------------------------------------------------------------------
# Se declaran como datos y no cableados en el cuerpo de `recalcular_stock()`, para que sumar un
# término nuevo —el de AJUSTES DE INVENTARIO, cuando se haga el formulario de toma física— sea
# agregar una entrada acá y no reescribir la función revalidando los cuatro que ya funcionan.
#
# Cada término declara:
#   modelo      : el modelo de ítem que mueve stock
#   signo       : +1 entra, −1 sale
#   cantidad    : campo con la cantidad del ítem
#   producto    : ruta al producto
#   sucursal    : ruta a la sucursal donde impacta
#   signo_cbte  : ruta al `TipoComprobante.signo` (las NC invierten), o None
#   excluir     : Q() de comprobantes que NO mueven stock

# ---------------------------------------------------------------------------
# Términos que aportan las VERTICALIDADES (Plan 080)
# ---------------------------------------------------------------------------
# Una verticalidad puede mover stock con comprobantes propios que no son compras ni ventas —el
# acopio de tabaco descarga por fardo, no por `CompraItem`—. En vez de que este módulo importe
# `verticalidades.*` (que rompería el Modo Enchufe del Plan 075 en cuanto alguien desenchufe la
# carpeta), es la verticalidad la que se ANUNCIA desde su `apps.py::ready()`.
#
# Si la carpeta no está, su app no entra a INSTALLED_APPS, `ready()` no corre, no se registra
# nada y el stock se calcula exactamente como si el Plan 080 no existiera.

_TERMINOS_EXTRA = []

_CLAVES_TERMINO = {'nombre', 'modelo', 'signo', 'cantidad', 'producto', 'sucursal',
                   'signo_cbte', 'excluir'}


def registrar_termino_stock(termino):
    """Agrega un origen al cálculo del stock. Lo llaman las verticalidades desde `ready()`.

    Es IDEMPOTENTE POR `nombre` a propósito: `ready()` puede correr más de una vez —el
    autoreload del runserver, ciertos runners de test— y un término duplicado haría que esas
    cantidades se contaran dos veces sin que nada fallara a la vista.

    Valida acá, al arrancar, y no al calcular: un término mal formado que se descubriera dentro
    de `recalcular_stock()` rompería el stock de TODO el ERP en medio de una operación. Es
    preferible que el servidor no levante.

    `excluir` acepta `None` o un `Q()` vacío para "no excluir nada".
    """
    faltan = _CLAVES_TERMINO - set(termino)
    if faltan:
        raise ValueError(f"Término de stock incompleto, faltan claves: {sorted(faltan)}")

    if termino['excluir'] is None:
        termino = dict(termino, excluir=Q())
    elif not isinstance(termino['excluir'], Q):
        raise ValueError(
            f"Término de stock '{termino['nombre']}': 'excluir' debe ser un Q() o None, "
            f"no {type(termino['excluir']).__name__}."
        )

    if any(t['nombre'] == termino['nombre'] for t in _TERMINOS_EXTRA):
        logger.warning("Término de stock '%s' ya estaba registrado; se ignora el alta repetida.",
                       termino['nombre'])
        return

    _TERMINOS_EXTRA.append(termino)


def _terminos():
    """Se arma adentro de la función para no importar `facturacion` al cargar el módulo."""
    from facturacion.models import CompraItem, RecepcionItem, RemitoInternoItem, VentaItem

    base = [
        {
            'nombre': 'compras',
            'modelo': CompraItem,
            'signo': 1,
            'cantidad': 'cantidad',
            'producto': 'producto_id',
            'sucursal': 'compra__sucursal_id',
            'signo_cbte': 'compra__tipo__signo',
            # La factura no mueve stock si ya lo movió un remito previo, ni en el circuito de
            # Órdenes de Compra, donde el stock lo da la Recepción (Plan 028).
            'excluir': Q(compra__id_fac_rem__isnull=False) | Q(compra__gestion_stock_por_recepcion=True),
        },
        {
            'nombre': 'recepciones',
            'modelo': RecepcionItem,
            'signo': 1,
            'cantidad': 'cantidad_recibida',
            'producto': 'producto_id',
            'sucursal': 'recepcion__sucursal_id',
            'signo_cbte': None,
            'excluir': Q(recepcion__estado=1),          # 1 = Anulada
        },
        {
            'nombre': 'ventas',
            'modelo': VentaItem,
            'signo': -1,
            'cantidad': 'cantidad',
            'producto': 'producto_id',
            'sucursal': 'venta__sucursal_id',
            'signo_cbte': 'venta__tipo__signo',
            'excluir': Q(venta__estado=1) | Q(venta__id_fac_rem__isnull=False),   # 1 = Anulada
        },
        {
            'nombre': 'remitos_internos',
            'modelo': RemitoInternoItem,
            'signo': -1,
            'cantidad': 'cantidad_enviada',
            'producto': 'producto_id',
            'sucursal': 'remito__sucursal_origen_id',
            'signo_cbte': None,
            'excluir': Q(remito__estado=3),             # 3 = Anulado
        },
    ]

    return base + list(_TERMINOS_EXTRA)


def _sumar_termino(termino, producto_id, sucursal_id) -> Decimal:
    """Total aportado por un término, ya con su signo y el del comprobante aplicados."""
    filtros = {termino['producto']: producto_id, termino['sucursal']: sucursal_id}
    qs = termino['modelo'].objects.filter(**filtros).exclude(termino['excluir'])

    if termino['signo_cbte']:
        # Las notas de crédito invierten el movimiento: una NC de venta DEVUELVE stock y una NC de
        # compra lo saca. `TipoComprobante.signo` vale −1 en esos casos.
        expresion = F(termino['cantidad']) * Coalesce(F(termino['signo_cbte']), Value(1))
    else:
        expresion = F(termino['cantidad'])

    total = qs.aggregate(t=Coalesce(Sum(expresion, output_field=_DEC), Value(CERO), output_field=_DEC))['t']
    return (total or CERO) * termino['signo']


@transaction.atomic
def recalcular_stock(producto_id, sucursal_id) -> Decimal:
    """Recalcula y guarda el stock disponible de un (producto, sucursal). Devuelve la cantidad.

    Es idempotente y autorreparable: no importa en qué estado esté `cantidad`, el resultado sale
    de `stock_inicial` más los comprobantes vigentes.
    """
    registro, _ = StockSucursal.objects.select_for_update().get_or_create(
        producto_id=producto_id, sucursal_id=sucursal_id,
        defaults={'cantidad': CERO, 'stock_inicial': CERO},
    )

    total = registro.stock_inicial or CERO
    for termino in _terminos():
        total += _sumar_termino(termino, producto_id, sucursal_id)

    if registro.cantidad != total:
        registro.cantidad = total
        registro.save(update_fields=['cantidad'])
    return total


# Estados de `Preventa` que COMPROMETEN stock: el pedido está vivo y todavía no se facturó.
# 0 Borrador · 1 Pendiente Autorización · 2 Autorizada.
# El 3 (Facturada) ya descontó stock real y el 4 (Anulada) no compromete nada.
ESTADOS_PEDIDO_COMPROMETEN = (0, 1, 2)


@transaction.atomic
def recalcular_comprometido(producto_id, sucursal_id) -> Decimal:
    """Recalcula y guarda la cantidad comprometida en pedidos de un (producto, sucursal).

    Mismo criterio que `recalcular_stock()`: es un valor DERIVADO y se recalcula entero, nunca se
    ajusta por delta, así que es idempotente y autorreparable.

    Se separa de `recalcular_stock()` a propósito. `cantidad` es lo que hay en el depósito y sale
    de comprobantes emitidos; `comprometido` es una promesa que todavía no movió mercadería.
    Mezclarlos haría que un pedido pareciera una salida de stock, y el depósito dejaría de cuadrar
    contra el conteo físico.
    """
    from facturacion.models import PreventaItem

    registro, _ = StockSucursal.objects.select_for_update().get_or_create(
        producto_id=producto_id, sucursal_id=sucursal_id,
        defaults={'cantidad': CERO, 'stock_inicial': CERO},
    )

    total = PreventaItem.objects.filter(
        producto_id=producto_id,
        preventa__sucursal_id=sucursal_id,
        preventa__estado__in=ESTADOS_PEDIDO_COMPROMETEN,
    ).aggregate(
        t=Coalesce(Sum('cantidad', output_field=_DEC), Value(CERO), output_field=_DEC)
    )['t'] or CERO

    if registro.comprometido != total:
        registro.comprometido = total
        registro.save(update_fields=['comprometido'])
    return total


def disponible_real(producto_id, sucursal_id) -> Decimal:
    """Stock que se puede prometer: el físico menos lo ya tomado en pedidos sin facturar."""
    fila = (StockSucursal.objects
            .filter(producto_id=producto_id, sucursal_id=sucursal_id)
            .values('cantidad', 'comprometido').first())
    if not fila:
        return CERO
    return (fila['cantidad'] or CERO) - (fila['comprometido'] or CERO)


def recalcular_stock_masivo(empresa_id, sucursal_id=None, producto_id=None):
    """Recalcula muchos registros de una, para el comando de mantenimiento.

    `recalcular_stock()` hace cuatro consultas por (producto, sucursal): perfecto para el guardado
    de un comprobante, inviable para un inventario entero —13.600 registros serían ~54.000
    consultas—. Acá los cuatro términos se agrupan por (producto, sucursal) en **cuatro consultas
    en total** y el reparto se resuelve en memoria.

    Devuelve `[(producto_id, sucursal_id, antes, despues), ...]` con las filas que NO coincidían.
    No escribe: quien llama decide si guardar.
    """
    registros = StockSucursal.objects.filter(producto__empresa_id=empresa_id)
    if sucursal_id:
        registros = registros.filter(sucursal_id=sucursal_id)
    if producto_id:
        registros = registros.filter(producto_id=producto_id)

    movimientos = {}
    for termino in _terminos():
        filtros = {f"{termino['producto']}__in": set(registros.values_list('producto_id', flat=True))}
        qs = termino['modelo'].objects.filter(**filtros).exclude(termino['excluir'])

        if termino['signo_cbte']:
            expresion = F(termino['cantidad']) * Coalesce(F(termino['signo_cbte']), Value(1))
        else:
            expresion = F(termino['cantidad'])

        agrupado = qs.values(termino['producto'], termino['sucursal']).annotate(
            t=Coalesce(Sum(expresion, output_field=_DEC), Value(CERO), output_field=_DEC))
        for fila in agrupado:
            clave = (fila[termino['producto']], fila[termino['sucursal']])
            movimientos[clave] = movimientos.get(clave, CERO) + (fila['t'] or CERO) * termino['signo']

    diferencias = []
    for pid, sid, inicial, cantidad in registros.values_list(
            'producto_id', 'sucursal_id', 'stock_inicial', 'cantidad'):
        esperado = (inicial or CERO) + movimientos.get((pid, sid), CERO)
        if esperado != cantidad:
            diferencias.append((pid, sid, cantidad, esperado))
    return diferencias


def _auditar(producto_id, sucursal_id, tipo, cantidad, observacion):
    """Deja la huella del movimiento. No participa del cálculo del stock."""
    if not cantidad:
        return
    MovimientoStock.objects.create(
        producto_id=producto_id, sucursal_id=sucursal_id,
        tipo=tipo, cantidad=abs(cantidad), observacion=observacion,
    )


# ---------------------------------------------------------------------------
# Puntos de entrada desde las señales (firmas sin cambios)
# ---------------------------------------------------------------------------

@transaction.atomic
def aplicar_movimiento_stock(item_instance, signo: int, sucursal, es_borrado=False):
    """Recalcula el stock tras guardar o borrar un `VentaItem` / `CompraItem`.

    `signo` y `es_borrado` ya no se usan para aritmética —el stock se recalcula entero—, pero se
    conservan en la firma porque los pasan las señales de `facturacion.signals`, y `signo` sigue
    sirviendo para rotular el movimiento de auditoría.
    """
    if not getattr(item_instance, 'producto_id', None) or not sucursal:
        return

    sucursal_id = getattr(sucursal, 'pk', sucursal)
    cantidad = Decimal(str(item_instance.cantidad or 0))

    comp_signo = 1
    observacion = ''
    if getattr(item_instance, 'venta_id', None) and getattr(item_instance, 'venta', None):
        v = item_instance.venta
        comp_signo = v.tipo.signo if v.tipo else 1
        cli = v.cliente_razon_social or (v.cliente.razon_social if getattr(v, 'cliente', None) else 'Consumidor Final')
        observacion = f"{'NC ' if comp_signo < 0 else ''}Venta Nro: {v.punto:04d}-{v.numero} - Cli: {cli}"
    elif getattr(item_instance, 'compra_id', None) and getattr(item_instance, 'compra', None):
        c = item_instance.compra
        comp_signo = c.tipo.signo if c.tipo else 1
        prov = c.proveedor.razon_social if getattr(c, 'proveedor', None) else 'Proveedor'
        observacion = f"{'NC ' if comp_signo < 0 else ''}Compra Nro: {c.numero} - Prov: {prov}"

    final_signo = signo * comp_signo
    if es_borrado:
        observacion = f"ANULADO/BORRADO — {observacion}" if observacion else "ANULADO/BORRADO"
    _auditar(item_instance.producto_id, sucursal_id,
             'ENTRADA' if final_signo > 0 else 'SALIDA', cantidad, observacion)

    recalcular_stock(item_instance.producto_id, sucursal_id)

    if not es_borrado:
        item_instance._original_cantidad = cantidad


@transaction.atomic
def aplicar_movimiento_recepcion(recepcion_item, es_borrado=False):
    """Recalcula el stock tras guardar o borrar un `RecepcionItem` (Plan 028).

    La Recepción da ENTRADA en su sucursal de destino, tanto de proveedor como de transferencia
    interna (la SALIDA del origen la genera el Remito Interno).
    """
    if not getattr(recepcion_item, 'producto_id', None):
        return
    recepcion = getattr(recepcion_item, 'recepcion', None)
    if not recepcion or not getattr(recepcion, 'sucursal_id', None):
        return

    cantidad = Decimal(str(recepcion_item.cantidad_recibida or 0))
    num = recepcion.numero if recepcion.numero else 's/n'
    detalle = f"Recepción {recepcion.punto:04d}-{num} ({recepcion.get_origen_display()})"
    if es_borrado:
        detalle = f"ANULADO/BORRADO — {detalle}"
    _auditar(recepcion_item.producto_id, recepcion.sucursal_id, 'ENTRADA', cantidad, detalle)

    recalcular_stock(recepcion_item.producto_id, recepcion.sucursal_id)

    if not es_borrado:
        recepcion_item._original_cantidad = cantidad


@transaction.atomic
def aplicar_movimiento_remito_interno(remito_item, es_borrado=False):
    """Recalcula el stock tras guardar o borrar un `RemitoInternoItem` (Plan 028 Fase 6).

    Al emitirlo la mercadería SALE de la sucursal de origen y queda en tránsito; la ENTRADA en el
    destino la genera después el Informe de Recepción. Transferencia en dos pasos.
    """
    if not getattr(remito_item, 'producto_id', None):
        return
    remito = getattr(remito_item, 'remito', None)
    if not remito or not getattr(remito, 'sucursal_origen_id', None):
        return

    cantidad = Decimal(str(remito_item.cantidad_enviada or 0))
    num = remito.numero if remito.numero else 's/n'
    detalle = f"Remito Interno {remito.punto:04d}-{num} → {remito.sucursal_destino.nombre}"
    if es_borrado:
        detalle = f"ANULADO/BORRADO — {detalle}"
    _auditar(remito_item.producto_id, remito.sucursal_origen_id,
             'TRANSFERENCIA', cantidad, detalle)

    recalcular_stock(remito_item.producto_id, remito.sucursal_origen_id)

    if not es_borrado:
        remito_item._original_cantidad = cantidad
