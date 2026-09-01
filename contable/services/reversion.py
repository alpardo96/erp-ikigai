"""Reversión total de comprobantes de tesorería (Plan 035 §1.7).

Anular una Orden de Pago o un Recibo tiene que deshacer TODO lo que la operación dejó atrás,
no sólo el asiento: las aplicaciones a facturas, los cheques de terceros entregados, los
valores bancarios emitidos, las retenciones practicadas y los movimientos de caja.

Criterio adoptado:
  - El ASIENTO se ANULA, no se borra: la trazabilidad contable queda intacta (con su fecha de
    anulación), que es una regla del sistema.
  - Los EFECTOS se revierten físicamente: los cheques vuelven a cartera, las aplicaciones
    desaparecen y los saldos se recalculan. Que es el objetivo funcional pedido.

Antes esto no existía: `anular_asiento_de_comprobante` marcaba la cabecera del asiento y nada
más, así que la factura seguía figurando pagada y el cheque entregado seguía fuera de cartera.
"""
from django.db import transaction

from contable.services.contabilizacion import anular_asiento_de_comprobante
from contable.services.saldos import (
    recalcular_saldo_compra, recalcular_saldo_venta, recalcular_saldo_cliente_proveedor,
)


class ReversionBloqueada(Exception):
    """La operación no se puede revertir porque algo posterior ya depende de ella."""


def _borrar_movimientos_de_caja(comprobante, campo):
    """Borra los movimientos de caja del comprobante y sus detalles.

    El orden importa: los satélites (transacciones bancarias, valores) protegen al detalle con
    PROTECT, así que hay que haberlos resuelto antes de llegar acá.
    """
    from tesoreria.models import MovimientoCaja, MovimientoCajaDetalle

    movimientos = MovimientoCaja.objects.filter(**{campo: comprobante})
    MovimientoCajaDetalle.objects.filter(movimiento_caja__in=movimientos).delete()
    movimientos.delete()


@transaction.atomic
def revertir_orden_pago(orden_pago, usuario=None, forzar=False):
    """Deshace por completo una Orden de Pago y la deja anulada.

    `forzar=True` permite revertir aunque un cheque propio ya figure debitado por el banco.
    Por defecto eso se bloquea: si el banco ya lo pagó, anular la orden sin más dejaría la
    contabilidad discrepando del extracto.
    """
    from tesoreria.models import OrdenPago, TransaccionBancaria, ValorTerceros
    from contable.models import RetencionPracticada

    orden_pago = OrdenPago.objects.select_for_update().get(pk=orden_pago.pk)
    if orden_pago.anulado:
        return orden_pago

    transacciones = TransaccionBancaria.objects.filter(
        movimiento_detalle__movimiento_caja__orden_pago=orden_pago)

    if not forzar:
        debitadas = transacciones.filter(estado='D', tipo_transaccion='CP')
        if debitadas.exists():
            numeros = ", ".join(t.numero_operacion or str(t.pk) for t in debitadas)
            raise ReversionBloqueada(
                f"No se puede anular la Orden de Pago {orden_pago.numero}: el banco ya debitó "
                f"los cheques {numeros}. Regularice primero la conciliación bancaria."
            )

    # 1. Aplicaciones a comprobantes: se borran y se recalculan los saldos de cada factura.
    compras_afectadas = list(
        orden_pago.aplicaciones.values_list('compra_id', flat=True).distinct())
    orden_pago.aplicaciones.all().delete()

    # 2. Cheques de terceros entregados: vuelven a cartera, como si nunca hubieran salido.
    ValorTerceros.objects.filter(orden_pago=orden_pago).update(
        estado='C', orden_pago=None, fecha_entrega=None, asiento_entrega_id=None)

    # 3. Valores bancarios emitidos por esta orden y certificados de retención practicados.
    transacciones.delete()
    RetencionPracticada.objects.filter(orden_pago=orden_pago).delete()

    # 4. Movimientos de caja (ya sin satélites que los protejan).
    _borrar_movimientos_de_caja(orden_pago, 'orden_pago')

    # 5. El asiento se ANULA (no se borra): la auditoría contable queda intacta.
    if orden_pago.asiento_id:
        anular_asiento_de_comprobante(orden_pago.asiento_id)

    orden_pago.anulado = True
    if usuario:
        orden_pago.modificado_por = usuario
    orden_pago.save(update_fields=['anulado', 'modificado_por'] if usuario else ['anulado'])

    # 6. Saldos: primero cada factura, después la cuenta corriente del proveedor.
    for compra_id in compras_afectadas:
        recalcular_saldo_compra(compra_id)
    recalcular_saldo_cliente_proveedor(orden_pago.proveedor_id)

    return orden_pago


@transaction.atomic
def revertir_recibo(recibo, usuario=None, forzar=False):
    """Espejo de `revertir_orden_pago` para las cobranzas.

    Se bloquea si algún cheque recibido en este recibo ya salió de cartera (entregado en una
    orden de pago o depositado): borrar el recibo dejaría a ese valor sin origen.
    """
    from tesoreria.models import Recibo, TransaccionBancaria, ValorTerceros

    recibo = Recibo.objects.select_for_update().get(pk=recibo.pk)
    if recibo.anulado:
        return recibo

    valores = ValorTerceros.objects.filter(recibo=recibo)
    if not forzar:
        fuera_de_cartera = valores.exclude(estado='C')
        if fuera_de_cartera.exists():
            numeros = ", ".join(v.numero_cheque or str(v.pk) for v in fuera_de_cartera)
            raise ReversionBloqueada(
                f"No se puede anular el Recibo {recibo.numero}: los cheques {numeros} ya no "
                f"están en cartera (fueron entregados o depositados)."
            )

    ventas_afectadas = list(
        recibo.aplicaciones.values_list('venta_id', flat=True).distinct())
    recibo.aplicaciones.all().delete()

    valores.delete()
    TransaccionBancaria.objects.filter(
        movimiento_detalle__movimiento_caja__recibo=recibo).delete()

    _borrar_movimientos_de_caja(recibo, 'recibo')

    if recibo.asiento_id:
        anular_asiento_de_comprobante(recibo.asiento_id)

    recibo.anulado = True
    if usuario:
        recibo.modificado_por = usuario
    recibo.save(update_fields=['anulado', 'modificado_por'] if usuario else ['anulado'])

    for venta_id in ventas_afectadas:
        recalcular_saldo_venta(venta_id)
    recalcular_saldo_cliente_proveedor(recibo.cliente_id)

    return recibo


@transaction.atomic
def revertir_por_asiento(asiento_id, usuario=None, forzar=False):
    """Punto de entrada cuando la anulación se dispara desde el listado de ASIENTOS.

    Busca el comprobante de tesorería que originó el asiento y delega, de modo que borrar el
    asiento arrastre todo lo demás. Si el asiento no viene de tesorería, se limita a anularlo.
    """
    from tesoreria.models import OrdenPago, Recibo

    orden = OrdenPago.objects.filter(asiento_id=asiento_id, anulado=False).first()
    if orden:
        return revertir_orden_pago(orden, usuario=usuario, forzar=forzar)

    recibo = Recibo.objects.filter(asiento_id=asiento_id, anulado=False).first()
    if recibo:
        return revertir_recibo(recibo, usuario=usuario, forzar=forzar)

    anular_asiento_de_comprobante(asiento_id)
    return None
