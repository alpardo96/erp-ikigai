"""Servicios de saldos: por comprobante y por entidad (cliente/proveedor).

REGLA CENTRAL (Plan 035 §1.3)
El saldo pendiente de un comprobante NO es un contador que se decrementa: se DERIVA de las
aplicaciones imputadas a ese comprobante. Las tablas `OrdenPagoAplicacion` / `ReciboAplicacion`
son la fuente de verdad; `Compra.pagado`, `Compra.saldo` y `Venta.saldo` son caché.

Por eso todos los recálculos suman DESDE CERO y nunca hacen `saldo -= importe`: un contador
incremental no se puede reconstruir y termina derivando (era el bug que dejaba facturas pagadas
figurando impagas y viceversa).
"""
import logging
from decimal import Decimal

from django.db import transaction, models
from django.db.models import Q, Sum, F
from django.db.models.functions import Coalesce

from facturacion.models import ClienteProveedor, Venta, Compra

logger = logging.getLogger(__name__)

CERO = Decimal("0.00")


def _suma(queryset, campo='importe'):
    """Σ de un campo decimal, siempre Decimal (nunca None)."""
    return queryset.aggregate(
        s=Coalesce(Sum(campo), Decimal('0'), output_field=models.DecimalField(max_digits=15, decimal_places=2))
    )['s']


# ---------------------------------------------------------------------------
# Puntos de extensión para las VERTICALIDADES (Plan 080)
# ---------------------------------------------------------------------------
# Una verticalidad puede tener comprobantes propios que generan deuda o crédito con un tercero
# sin pasar por `Compra`/`Venta` —la liquidación de compra de tabaco no es un `CompraItem`: es
# un comprobante sectorial con su propia tabla—. Este módulo NO puede importar `verticalidades.*`
# sin romper el Modo Enchufe del Plan 075: es la verticalidad la que se anuncia desde su
# `apps.py::ready()`.
#
# Si la carpeta de la verticalidad no está, su app no entra a INSTALLED_APPS, `ready()` no corre
# y estos servicios calculan exactamente como antes del Plan 080.
#
# IMPORTANTE — qué importe declarar en `campo_importe`: el TOTAL del comprobante (la deuda), no
# el neto a pagar. Es el mismo criterio del supuesto S-1 documentado más abajo: `OrdenPago.total`
# ya incluye las retenciones practicadas como medio de pago, así que si el comprobante aportara
# el neto de retenciones, la OP cancelaría de más y el tercero quedaría con un crédito falso.

_TERMINOS_CTACTE_EXTRA = []
_APLICACIONES_OP_EXTRA = []

_CLAVES_TERMINO_CTACTE = {'nombre', 'modelo', 'campo_entidad', 'campo_empresa',
                          'campo_importe', 'signo', 'excluir'}
_CLAVES_APLICACION_OP = {'nombre', 'modelo', 'campo_op', 'campo_importe'}


def _registrar(destino, item, claves, que):
    """Alta idempotente por `nombre` en un registro de extensión.

    La idempotencia no es un lujo: `ready()` puede correr más de una vez y un origen duplicado
    haría que la deuda se contara dos veces sin que nada fallara a la vista.
    """
    faltan = claves - set(item)
    if faltan:
        raise ValueError(f"{que} incompleto, faltan claves: {sorted(faltan)}")

    if any(x['nombre'] == item['nombre'] for x in destino):
        logger.warning("%s '%s' ya estaba registrado; se ignora el alta repetida.", que, item['nombre'])
        return

    destino.append(item)


def registrar_termino_ctacte(termino):
    """Agrega un origen al saldo de cuenta corriente de un tercero.

    `signo`: −1 si el comprobante nos genera deuda (mismo signo que una compra), +1 si nos
    genera crédito. Ver la convención de signos en `recalcular_saldo_cliente_proveedor()`.

    `excluir` acepta `None` o un `Q()` para no excluir nada. Se valida acá y no al calcular: un
    término mal formado descubierto dentro de `recalcular_saldo_cliente_proveedor()` rompería la
    cuenta corriente de todo el ERP en medio de una operación.
    """
    faltan = _CLAVES_TERMINO_CTACTE - set(termino)
    if faltan:
        raise ValueError(f"Término de cuenta corriente incompleto, faltan claves: {sorted(faltan)}")

    if termino['excluir'] is not None and not isinstance(termino['excluir'], Q):
        raise ValueError(
            f"Término de cuenta corriente '{termino['nombre']}': 'excluir' debe ser un Q() "
            f"o None, no {type(termino['excluir']).__name__}."
        )
    if termino['signo'] not in (1, -1):
        raise ValueError(
            f"Término de cuenta corriente '{termino['nombre']}': 'signo' debe ser 1 o −1."
        )
    _registrar(_TERMINOS_CTACTE_EXTRA, termino, _CLAVES_TERMINO_CTACTE, "Término de cuenta corriente")


def registrar_aplicacion_op(aplicacion):
    """Agrega una tabla de imputación de Órdenes de Pago.

    `OrdenPagoAplicacion.compra` es un FK duro a `Compra`, así que una OP que cancela un
    comprobante sectorial se imputa en una tabla de la verticalidad. Sin registrarla acá, esa OP
    figuraría para siempre como "sin aplicar".
    """
    _registrar(_APLICACIONES_OP_EXTRA, aplicacion, _CLAVES_APLICACION_OP, "Aplicación de OP")


# ---------------------------------------------------------------------------
# Saldo por COMPROBANTE
# ---------------------------------------------------------------------------

@transaction.atomic
def recalcular_saldo_compra(compra_id: int) -> Decimal:
    """`pagado` = Σ aplicaciones de OP activas; `saldo` = total − pagado.

    Las compras no se pagan en el acto de la carga (el form excluye `pagado`), así que todo lo
    pagado proviene de Órdenes de Pago. Las OP anuladas no cuentan.

    El saldo conserva el SIGNO del comprobante: una Nota de Crédito tiene total negativo y por
    lo tanto saldo negativo hasta que se la aplica.
    """
    from tesoreria.models import OrdenPagoAplicacion

    compra = Compra.objects.select_for_update().get(pk=compra_id)
    pagado = _suma(OrdenPagoAplicacion.objects.filter(
        compra_id=compra_id, orden_pago__anulado=False
    ))
    saldo = Decimal(str(compra.total)) - pagado

    # UPDATE directo, NO `save()`: actualizar un caché derivado no debe disparar el post_save
    # de Compra, que reconstruye el asiento contable. Con `save()` se encadenaba una segunda
    # contabilización sobre un estado intermedio y el asiento salía por un importe equivocado.
    Compra.objects.filter(pk=compra_id).update(pagado=pagado, saldo=saldo)
    return saldo


@transaction.atomic
def recalcular_saldo_venta(venta_id: int) -> Decimal:
    """`saldo` = total − cobrado en el acto − Σ recibos − Σ notas de crédito relacionadas.

    LA NC DESCUENTA EL SALDO DE SU FACTURA (Plan 076 §D). Como la NC está vinculada al
    comprobante que le dio origen, el saldo REAL de la factura sale de restarle lo
    acreditado, y la NC queda ella misma en CERO por haberse aplicado por completo.

    El saldo por ENTIDAD no se toca por esto: `recalcular_saldo_cliente_proveedor()` suma
    `total − cobrado` sobre todas las ventas y la NC ya entra en negativo por su signo.
    Descontarla también allá la contaría dos veces.

    OJO con `cobrado`: a diferencia de compras, una venta SÍ puede cobrarse en el momento de
    emitirse (caja mostrador setea `cobrado = total − ctacte`). Ese campo registra ese cobro
    inicial y NO se recalcula acá; sobre él se descuentan además las cobranzas posteriores
    hechas por Recibo. Pisar `cobrado` con la Σ de aplicaciones dejaría toda venta de mostrador
    figurando impaga.
    """
    from tesoreria.models import ReciboAplicacion

    venta = Venta.objects.select_for_update().get(pk=venta_id)
    aplicado = _suma(ReciboAplicacion.objects.filter(
        venta_id=venta_id, recibo__anulado=False
    ))

    # Una NC vinculada a su origen se aplicó POR COMPLETO a ese comprobante: su saldo es
    # cero, y lo que descuenta vive en el saldo de la factura (abajo). Sin esto la factura
    # quedaba con saldo completo y la NC con saldo negativo, y había que cruzarlas a mano.
    if venta.venta_origen_id:
        Venta.objects.filter(pk=venta_id).update(saldo=CERO)
        return CERO

    # Las NC que referencian este comprobante lo descuentan. Se guardan con total POSITIVO
    # —el signo es un atributo del TIPO, no del importe—, así que acá se RESTAN.
    acreditado = _suma(
        Venta.objects.filter(venta_origen_id=venta_id).exclude(estado=1), 'total')

    saldo = (Decimal(str(venta.total)) - Decimal(str(venta.cobrado or 0))
             - aplicado - acreditado)

    # UPDATE directo por el mismo motivo que en compras: no re-disparar la contabilización.
    Venta.objects.filter(pk=venta_id).update(saldo=saldo)
    return saldo


def pendiente_de_aplicar_op(orden_pago) -> Decimal:
    """Importe de una OP que todavía no fue imputado a ningún comprobante.

    Alimenta la columna del listado de OP y el formulario de aplicación diferida: una OP puede
    emitirse sin aplicar (anticipo) y aplicarse contra facturas que llegan después.
    """
    from tesoreria.models import OrdenPagoAplicacion

    if orden_pago.anulado:
        return CERO
    aplicado = _suma(OrdenPagoAplicacion.objects.filter(orden_pago=orden_pago))

    # Imputaciones que aportan las verticalidades (Plan 080).
    for extra in _APLICACIONES_OP_EXTRA:
        aplicado += _suma(
            extra['modelo'].objects.filter(**{extra['campo_op']: orden_pago}),
            extra['campo_importe'],
        )

    return Decimal(str(orden_pago.total)) - aplicado


def pendiente_de_aplicar_recibo(recibo) -> Decimal:
    """Espejo de `pendiente_de_aplicar_op` del lado de las cobranzas."""
    from tesoreria.models import ReciboAplicacion

    if recibo.anulado:
        return CERO
    aplicado = _suma(ReciboAplicacion.objects.filter(recibo=recibo))
    return Decimal(str(recibo.total)) - aplicado


# ---------------------------------------------------------------------------
# Saldo por ENTIDAD
# ---------------------------------------------------------------------------

@transaction.atomic
def recalcular_saldo_cliente_proveedor(entidad_id: int) -> Decimal:
    """Saldo de cuenta corriente de una entidad (Plan 035 §1.4).

        saldo = saldo_inicial
              + facturas de ventas − lo cobrado al emitirlas
              − facturas de compras
              − recibos
              + órdenes de pago

    Convención de signos: NEGATIVO = le debemos (deuda a proveedores, anticipos de clientes).

    "Facturas" incluye facturas, notas de crédito, notas de débito y los comprobantes de
    retención/percepción que la contraparte nos emite: todos son Venta/Compra y ya vienen con su
    propio signo (las NC se graban en negativo vía `TipoComprobante.signo = -1`), así que basta
    con sumar los totales sin discriminar el tipo.

    El término "− lo cobrado al emitirlas" es lo que hace que una venta de mostrador cobrada en
    el acto no infle la cuenta corriente: aporta +total y −total = 0. Una venta en cuenta
    corriente aporta +total y se cancela después con el recibo.

    NOTA (supuesto S-1 del plan): `OrdenPago.total` YA incluye las retenciones practicadas
    (son un medio de pago más), por eso la OP se suma una sola vez y no hay un término separado
    por retenciones: sumarlas aparte las contaría dos veces. Si algún día `OrdenPago.total`
    pasara a excluirlas, el ajuste va acá y en ningún otro lado.
    """
    from tesoreria.models import Recibo, OrdenPago

    entidad = ClienteProveedor.objects.select_for_update().get(pk=entidad_id)
    empresa_id = entidad.empresa_id

    # Ventas activas (estado 0). `cobrado` descuenta lo percibido al emitir el comprobante.
    #
    # EL SIGNO SE APLICA ACÁ, no viene en el importe (Plan 076 §D). Los comprobantes se
    # guardan SIEMPRE con total positivo —así los emite `emitir_nota_credito_desde_venta()`
    # y así están los datos— y el signo es un atributo del TIPO. Antes esta suma tomaba el
    # total tal cual, de modo que una Nota de Crédito AUMENTABA la deuda del cliente en vez
    # de bajarla. Es el mismo criterio que ya usa `productos.services.stock_service`, que
    # multiplica por `tipo__signo` para que la NC invierta el movimiento.
    ventas = Venta.objects.filter(cliente=entidad, empresa_id=empresa_id, estado=0).aggregate(
        s=Coalesce(Sum((F('total') - F('cobrado'))
                       * Coalesce(F('tipo__signo'), models.Value(1))), Decimal('0'),
                   output_field=models.DecimalField(max_digits=15, decimal_places=2))
    )['s']

    compras = _suma(Compra.objects.filter(proveedor=entidad, empresa_id=empresa_id), 'total')
    recibos = _suma(Recibo.objects.filter(cliente=entidad, empresa_id=empresa_id, anulado=False), 'total')
    ordenes = _suma(OrdenPago.objects.filter(proveedor=entidad, empresa_id=empresa_id, anulado=False), 'total')

    # Comprobantes sectoriales de las verticalidades (Plan 080). Con el registro vacío —que es
    # el caso de cualquier empresa sin verticalidades enchufadas— este bloque no hace nada y el
    # saldo sale de los cuatro términos de siempre.
    extras = CERO
    for termino in _TERMINOS_CTACTE_EXTRA:
        qs = termino['modelo'].objects.filter(**{
            termino['campo_entidad']: entidad,
            termino['campo_empresa']: empresa_id,
        })
        if termino['excluir'] is not None:
            qs = qs.exclude(termino['excluir'])
        extras += termino['signo'] * _suma(qs, termino['campo_importe'])

    entidad.saldo = (Decimal(str(entidad.saldo_inicial or 0))
                     + ventas - compras - recibos + ordenes + extras)
    entidad.save(update_fields=['saldo'])
    return entidad.saldo


@transaction.atomic
def recalcular_saldos_empresa(empresa_id: int) -> None:
    """Recalcula los saldos de todas las entidades de una empresa."""
    entidades_ids = ClienteProveedor.objects.filter(empresa_id=empresa_id).values_list('pk', flat=True)
    for entidad_id in entidades_ids:
        recalcular_saldo_cliente_proveedor(entidad_id)
