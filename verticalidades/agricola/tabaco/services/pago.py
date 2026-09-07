"""Pago al productor y retención de Ganancias (Plan 084).

LA RETENCIÓN ES UN MEDIO DE PAGO, Y ESO ORDENA TODO
Ikigai ya sabe practicar retenciones en el pago: un `MedioPago` de categoría 'RET' que
`contabilizar_orden_pago()` acredita contra su cuenta contable. No se construye un mecanismo
nuevo; se usa el que existe. De ahí sale la ecuación del pago:

    OrdenPago.total = Σ medios entregados (efectivo, cheque, transferencia)
                    + retención de Ganancias     ← también es un "medio": no sale plata, pero cancela

    Σ imputaciones a liquidaciones = OrdenPago.total

Es además lo que hace cerrar el término de cuenta corriente del Plan 083: la liquidación aportó su
TOTAL y la OP lo cancela entero, retención incluida. Es el supuesto S-1 de `saldos.py`.

EL ACUMULADO MENSUAL SE DERIVA, NO SE ALMACENA
La base del mes se reconstruye sumando los certificados vigentes del productor en el período. No
hay contador que mantener sincronizado, y anular un pago baja el acumulado solo. El sistema
heredado hacía lo mismo: `liq_mes_ret_gcia` era una vista, no una tabla.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max, Q, Sum
from django.utils import timezone

from contable.services.contabilizacion import (anular_asiento_de_comprobante,
                                               contabilizar_orden_pago)
from contable.services.saldos import recalcular_saldo_cliente_proveedor

from ..models import (LiquidacionPago, LiquidacionTabaco, RetencionPago, TipoRetencionTabaco)
from .liquidacion import es_responsable_inscripto

CERO = Decimal('0.00')
DOS = Decimal('0.01')
CIEN = Decimal('100')


def _redondear(valor):
    return Decimal(valor).quantize(DOS, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Saldo de la liquidación
# ---------------------------------------------------------------------------

@transaction.atomic
def recalcular_saldo_liquidacion(liquidacion_id):
    """`pagado` = Σ imputaciones vigentes; `saldo` = total − pagado.

    Se DERIVA, nunca se decrementa: es el mismo criterio de `recalcular_saldo_compra()` del core.
    Un contador incremental no se puede reconstruir y termina derivando.
    """
    liq = LiquidacionTabaco.objects.select_for_update().get(pk=liquidacion_id)
    pagado = (LiquidacionPago.objects
              .filter(liquidacion_id=liquidacion_id, anulado=False,
                      orden_pago__anulado=False)
              .aggregate(s=Sum('importe'))['s'] or CERO)

    liq.pagado = pagado
    liq.saldo = (liq.total - pagado) if liq.estado == LiquidacionTabaco.CONFIRMADA else CERO
    liq.save(update_fields=['pagado', 'saldo'])
    return liq.saldo


def liquidaciones_pendientes(empresa_id, productor):
    """Liquidaciones confirmadas del productor con saldo a pagar."""
    return (LiquidacionTabaco.objects
            .filter(empresa_id=empresa_id, productor=productor,
                    estado=LiquidacionTabaco.CONFIRMADA, saldo__gt=0)
            .order_by('fecha', 'numero'))


# ---------------------------------------------------------------------------
# Retención de Ganancias
# ---------------------------------------------------------------------------

def concepto_ganancias(empresa_id, fecha):
    """Concepto de retención acumulativa vigente a la fecha, o `None`."""
    return (TipoRetencionTabaco.objects
            .filter(empresa_id=empresa_id, activa=True,
                    momento=TipoRetencionTabaco.PAGO,
                    tipo_base=TipoRetencionTabaco.ACUM_MENSUAL,
                    vigencia_desde__lte=fecha)
            .filter(Q(vigencia_hasta__isnull=True) | Q(vigencia_hasta__gte=fecha))
            .select_related('cuenta_contable')
            .first())


def acumulado_del_mes(empresa_id, productor, periodo):
    """Base y retenido ya acumulados del productor en el período, desde los certificados.

    Excluye los anulados y los de órdenes de pago anuladas: si un pago se dio de baja, sus
    importes no pueden seguir contando para el mes.
    """
    agregado = (RetencionPago.objects
                .filter(empresa_id=empresa_id, productor=productor, periodo=periodo,
                        anulado=False, orden_pago__anulado=False)
                .aggregate(base=Sum('base_del_pago'), retenido=Sum('importe')))
    return (agregado['base'] or CERO), (agregado['retenido'] or CERO)


def calcular_ganancias(*, empresa, productor, base_del_pago, fecha):
    """Retención a practicar ahora, según el acumulado del mes. No graba nada.

    Devuelve `None` cuando no corresponde retener (sin concepto vigente, productor que no es RI,
    o acumulado por debajo del mínimo). La pantalla usa esta misma función para previsualizar.
    """
    concepto = concepto_ganancias(empresa.pk, fecha)
    if concepto is None:
        return None
    if concepto.solo_responsable_inscripto and not es_responsable_inscripto(productor):
        return None

    periodo = fecha.strftime('%Y%m')
    base_previa, retenido_previo = acumulado_del_mes(empresa.pk, productor, periodo)
    base_acumulada = Decimal(base_del_pago) + base_previa
    mni = Decimal(concepto.minimo_no_imponible or 0)

    if base_acumulada <= mni:
        retencion_del_mes = CERO
    else:
        retencion_del_mes = _redondear((base_acumulada - mni) * Decimal(concepto.alicuota) / CIEN)

    a_retener = retencion_del_mes - retenido_previo
    # Nunca negativo: si por una anulación el acumulado bajó, no se "devuelve" plata en el pago
    # siguiente. La corrección se hace anulando el certificado que corresponda.
    if a_retener < 0:
        a_retener = CERO

    return {
        'concepto': concepto,
        'periodo': periodo,
        'base_del_pago': Decimal(base_del_pago),
        'base_acumulada': base_acumulada,
        'minimo_no_imponible': mni,
        'retencion_del_mes': retencion_del_mes,
        'retenido_previo': retenido_previo,
        'importe': _redondear(a_retener),
    }


def _medio_pago_de(concepto):
    """`MedioPago` de categoría RET para el concepto, creado al vuelo si no existe.

    La cuenta sale del propio concepto, que es donde el contador la definió. Pedirle al usuario
    que la configure otra vez en Medios de Pago sería duplicar el mismo dato en dos lugares y
    abrir la puerta a que discrepen.
    """
    from tesoreria.models import MedioPago

    codigo = f"RET-{concepto.codigo}".replace(' ', '')[:10]
    medio, creado = MedioPago.objects.get_or_create(
        empresa=concepto.empresa, codigo=codigo,
        defaults={'nombre': concepto.detalle[:100], 'categoria': 'RET',
                  'cuenta_contable': concepto.cuenta_contable, 'activo': True})

    # Si el concepto cambió de cuenta, el medio la sigue: la verdad está en el maestro.
    if not creado and medio.cuenta_contable_id != concepto.cuenta_contable_id:
        medio.cuenta_contable = concepto.cuenta_contable
        medio.save(update_fields=['cuenta_contable'])

    return medio


def _siguiente_certificado(empresa_id):
    ultimo = (RetencionPago.objects
              .filter(empresa_id=empresa_id, nro_certificado__isnull=False)
              .aggregate(m=Max('nro_certificado'))['m'] or 0)
    return ultimo + 1


# ---------------------------------------------------------------------------
# Pago
# ---------------------------------------------------------------------------

@transaction.atomic
def pagar_liquidaciones(*, empresa, sucursal, productor, liquidaciones, medios, fecha,
                        usuario, punto=1, condic=1, observaciones=''):
    """Cancela liquidaciones con una Orden de Pago, reteniendo Ganancias si corresponde.

    `medios` es una lista de `{'medio_pago': MedioPago, 'importe': Decimal}` con lo que se entrega
    realmente (efectivo, cheque, transferencia). La retención se agrega sola.

    Devuelve la `OrdenPago` creada.
    """
    from tesoreria.models import MovimientoCaja, MovimientoCajaDetalle, OrdenPago
    from tesoreria.services.caja_diaria import get_o_abrir_caja

    liquidaciones = _bloquear_y_validar(empresa, productor, liquidaciones)

    entregado = sum((Decimal(m['importe']) for m in medios), CERO)
    if entregado <= 0:
        raise ValidationError("Hay que indicar al menos un medio de pago con importe.")

    base_neta = sum((l.neto for l in liquidaciones), CERO)
    retencion = calcular_ganancias(empresa=empresa, productor=productor,
                                   base_del_pago=base_neta, fecha=fecha)
    importe_retenido = retencion['importe'] if retencion else CERO

    total = entregado + importe_retenido

    a_pagar = sum((l.saldo for l in liquidaciones), CERO)
    if total > a_pagar:
        raise ValidationError(
            f"El pago (${total}) supera el saldo de las liquidaciones seleccionadas (${a_pagar}).")

    _, sesion_caja = get_o_abrir_caja(empresa.pk, sucursal.pk, usuario)

    op = OrdenPago.objects.create(
        empresa=empresa, sucursal=sucursal, ejercicio=_ejercicio(empresa, fecha),
        sesion_caja=sesion_caja, proveedor=productor, fecha=fecha, punto=punto,
        total=total, condic=condic, tipo='P', observaciones=observaciones,
        creado_por=usuario, modificado_por=usuario)

    movimiento = MovimientoCaja.objects.create(
        sesion=sesion_caja, empresa=empresa, fecha=fecha, tipo='E', importe=total,
        concepto=f"Pago a productor de tabaco — OP {op.numero}",
        condic=condic, orden_pago=op, cli_pro=productor, creado_por=usuario)

    for m in medios:
        MovimientoCajaDetalle.objects.create(
            movimiento_caja=movimiento, medio_pago=m['medio_pago'],
            importe=Decimal(m['importe']))

    if retencion and importe_retenido > 0:
        # La retención entra como un medio de pago más: es lo que hace que
        # `contabilizar_orden_pago()` la acredite en su cuenta de pasivo sin saber nada de tabaco.
        MovimientoCajaDetalle.objects.create(
            movimiento_caja=movimiento, medio_pago=_medio_pago_de(retencion['concepto']),
            importe=importe_retenido)
        _emitir_certificado(op, productor, retencion, fecha)

    _imputar(op, liquidaciones, total)

    contabilizar_orden_pago(op)

    for liq in liquidaciones:
        recalcular_saldo_liquidacion(liq.pk)
    recalcular_saldo_cliente_proveedor(productor.pk)

    return op


def _bloquear_y_validar(empresa, productor, liquidaciones):
    """Relee con bloqueo y valida. Sin el `select_for_update()` dos pagos simultáneos podrían
    cancelar dos veces el mismo saldo."""
    if not liquidaciones:
        raise ValidationError("Hay que elegir al menos una liquidación.")

    frescas = list(LiquidacionTabaco.objects
                   .select_for_update()
                   .filter(pk__in=[l.pk for l in liquidaciones])
                   .order_by('fecha', 'numero'))

    for liq in frescas:
        if liq.empresa_id != empresa.pk:
            raise ValidationError(f"La liquidación {liq.numero} pertenece a otra empresa.")
        if liq.productor_id != productor.pk:
            raise ValidationError(
                f"La liquidación {liq.numero} es de otro productor: una Orden de Pago cancela "
                f"comprobantes de un solo tercero.")
        if liq.estado != LiquidacionTabaco.CONFIRMADA:
            raise ValidationError(
                f"La liquidación {liq.numero or '(borrador)'} está "
                f"«{liq.get_estado_display()}» y no se puede pagar.")
        if liq.saldo <= 0:
            raise ValidationError(f"La liquidación {liq.numero} ya está cancelada.")

    return frescas


def _imputar(op, liquidaciones, total):
    """Reparte el pago entre las liquidaciones, de la más vieja a la más nueva."""
    restante = total
    for liq in liquidaciones:
        if restante <= 0:
            break
        aplicado = min(restante, liq.saldo)
        LiquidacionPago.objects.create(liquidacion=liq, orden_pago=op, importe=aplicado)
        restante -= aplicado


def _emitir_certificado(op, productor, retencion, fecha):
    concepto = retencion['concepto']
    RetencionPago.objects.create(
        empresa=op.empresa, orden_pago=op, productor=productor, tipo_retencion=concepto,
        codigo=concepto.codigo, detalle=concepto.detalle, regimen=concepto.regimen,
        alicuota=concepto.alicuota, minimo_no_imponible=retencion['minimo_no_imponible'],
        cuenta_contable=concepto.cuenta_contable,
        periodo=retencion['periodo'],
        base_del_pago=retencion['base_del_pago'],
        base_acumulada=retencion['base_acumulada'],
        retencion_del_mes=retencion['retencion_del_mes'],
        retenido_previo=retencion['retenido_previo'],
        importe=retencion['importe'],
        nro_certificado=_siguiente_certificado(op.empresa_id),
        fecha=fecha)


def _ejercicio(empresa, fecha):
    from empresas.models import Ejercicio
    ejercicio = Ejercicio.objects.filter(
        empresa=empresa, inicio__lte=fecha, cierre__gte=fecha).first()
    if ejercicio is None:
        raise ValidationError(
            f"No hay un ejercicio fiscal que contenga la fecha {fecha:%d/%m/%Y}.")
    return ejercicio


# ---------------------------------------------------------------------------
# Anulación
# ---------------------------------------------------------------------------

@transaction.atomic
def anular_pago(orden_pago, motivo, usuario=None):
    """Anula la Orden de Pago, su asiento y su certificado, y restituye los saldos.

    El certificado se marca anulado y con eso el acumulado mensual baja SOLO, porque se deriva de
    los certificados vigentes. No hay ningún contador que corregir a mano.
    """
    from tesoreria.models import OrdenPago

    op = OrdenPago.objects.select_for_update().get(pk=orden_pago.pk)
    if op.anulado:
        return op
    if not (motivo or '').strip():
        raise ValidationError("La anulación exige un motivo.")

    if op.asiento_id:
        anular_asiento_de_comprobante(op.asiento_id)

    imputaciones = list(LiquidacionPago.objects.filter(orden_pago=op, anulado=False))
    LiquidacionPago.objects.filter(orden_pago=op).update(anulado=True)
    RetencionPago.objects.filter(orden_pago=op).update(anulado=True)

    op.anulado = True
    op.observaciones = f"{op.observaciones}\nANULADA: {motivo.strip()}".strip()
    op.modificado_por = usuario
    op.save(update_fields=['anulado', 'observaciones', 'modificado_por'])

    for imp in imputaciones:
        recalcular_saldo_liquidacion(imp.liquidacion_id)
    recalcular_saldo_cliente_proveedor(op.proveedor_id)

    return op
