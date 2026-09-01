"""Imputación contable de los movimientos de caja (Plan 049).

`MovimientoCaja` guarda una referencia a su asiento y a la cuenta de imputación PRINCIPAL. Este
módulo concentra las dos reglas que definen esa vinculación, para que los seis circuitos que
crean movimientos de caja (recibo, orden de pago, caja mostrador, retiro, cierre y rendición) no
mantengan cada uno su propia versión.

Por qué "principal" y no "la" cuenta: un movimiento de caja es UNO por comprobante, pero la
contrapartida contable puede ser VARIAS cuentas (un recibo simple imputado a tres cuentas de
gasto, una venta mostrador con productos de distintos rubros). El sistema legado resolvía esto
con una tabla de una fila por contrapartida (`caja_diaria.id_cta`); acá la cabecera es 1:1 con el
comprobante, así que `cuenta` guarda la de mayor importe y el desglose completo queda en las
líneas del asiento, que es lo que leen los reportes de fondos.
"""

from django.db.models import F, Q, Sum


def cuenta_principal_del_asiento(asiento):
    """Cuenta de CONTRAPARTIDA de mayor importe de un asiento.

    Contrapartida = línea cuya cuenta NO es de disponibilidad (`tipo_disponibilidad` vacío). Las
    cuentas de disponibilidad (caja, banco, valores, dólares, tarjetas) son el lado de los
    FONDOS: no son ni el origen ni la aplicación, sino el bolsillo por donde pasa la plata.

    Devuelve `None` si el asiento no existe o si no tiene ninguna línea de contrapartida (caso
    del traslado puro entre disponibilidades: retiro de caja mostrador a tesorería).

    El desempate es por `cuenta_id` ascendente para que el resultado sea determinístico: si dos
    cuentas empatan en importe, dos corridas del backfill tienen que dar lo mismo.
    """
    if not asiento:
        return None

    from contable.models import AsientoLinea, Cuenta

    fila = (
        AsientoLinea.objects
        .filter(asiento=asiento)
        .filter(Q(cuenta__tipo_disponibilidad='') | Q(cuenta__tipo_disponibilidad__isnull=True))
        .values('cuenta_id')
        .annotate(total=Sum(F('debe') + F('haber')))
        .order_by('-total', 'cuenta_id')
        .first()
    )
    if not fila:
        return None

    return Cuenta.objects.filter(pk=fila['cuenta_id']).first()


def condic_por_comprobante(tipo_comprobante):
    """`condic` del movimiento de fondos según el TIPO DE COMPROBANTE.

    PRE (Presupuesto) -> 2 (Presupuestado). Cualquier otro -> 1 (Real).

    En movimientos de fondos solo existen esos dos valores (lo garantiza el CheckConstraint
    `mov_caja_condic_1_o_2`): el 3 (Ajuste) lo paga el socio y no mueve plata de la empresa, el 4
    son ajustes del estudio contable y los 5/6/7 los genera el sistema.

    Se deriva del comprobante y no del `condic` que manda el navegador, para no depender del
    payload del cliente. Acepta el objeto TipoComprobante o su código.
    """
    codigo = getattr(tipo_comprobante, 'codigo', tipo_comprobante)
    return 2 if codigo and str(codigo).upper() == 'PRE' else 1


def estampar_asiento(mov_caja, asiento):
    """Vincula un movimiento de caja con su asiento y su cuenta principal.

    Se llama DESPUÉS de contabilizar, porque en los seis circuitos el asiento se genera una vez
    que existen los detalles del movimiento (el debe/haber se arma leyendo los medios de pago).
    Es el mismo patrón con el que ya se estampa el asiento en `TransaccionBancaria` y
    `ValorTerceros`.

    Tolera `asiento = None`: hay circuitos que no siempre generan asiento (la rendición solo
    asienta si hubo diferencia de arqueo).
    """
    if not asiento:
        return

    mov_caja.asiento = asiento
    mov_caja.cuenta = cuenta_principal_del_asiento(asiento)
    mov_caja.save(update_fields=['asiento', 'cuenta'])
