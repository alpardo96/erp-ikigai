"""Cobranza del repartidor con imputación FIFO segmentada por medio de pago (Plan 074 §7.7).

EL USUARIO CARGA UN IMPORTE; EL CORTE LO HACE EL SISTEMA
--------------------------------------------------------
El repartidor vuelve y dice "de González traje $40.000 en efectivo y un cheque de $66.000".
Nadie le va a preguntar cuánto de eso cancela facturas y cuánto cancela PRE: esa decisión
la toma el sistema, con dos reglas que no se negocian.

    1. Los medios con TRAZABILIDAD EXTERNA (transferencia, cheque, tarjeta, billetera
       digital, retención) se aplican SIEMPRE a `condic = 1`. Un movimiento que el banco
       registra no puede cancelar una operación que para el fisco no existe.

    2. El EFECTIVO se imputa PRIMERO al saldo más antiguo de `condic = 2` (PRE) y sólo
       una vez cubiertos todos los PRE continúa con `condic = 1`. Es la única plata que
       puede cancelar lo que no está documentado, así que se usa donde hace falta.

Todo lo que no sea explícitamente trazable se trata como efectivo, incluida la categoría
`OTR`: si no deja rastro externo verificable, no puede respaldar una operación fiscal.

DOS RECIBOS COMO MÁXIMO, UNO POR `condic`
-----------------------------------------
Real y Presupuestado no se mezclan en un mismo recibo porque cada uno alimenta un circuito
contable distinto, y el asiento hereda el `condic` del comprobante. El efectivo puede
partirse entre los dos; los medios trazables van enteros al de `condic = 1`.

LAS NOTAS DE CRÉDITO NO ENTRAN EN EL FIFO
-----------------------------------------
Acreditar una NC contra una factura es una IMPUTACIÓN entre comprobantes, no una cobranza:
no entra plata. Mezclarla acá obligaría a manejar signos cruzados en el mismo recorrido y
volvería ilegible el algoritmo. El FIFO recorre sólo comprobantes con saldo deudor.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

CERO = Decimal('0.00')

# Medios que dejan rastro en un tercero verificable (banco, tarjeta, fisco). Cualquier
# categoría que no esté acá se trata como efectivo, incluida `OTR`.
CATEGORIAS_TRAZABLES = ('TRA', 'CHQ', 'TAR', 'DIG', 'RET')

REAL = 1
PRESUPUESTADO = 2


# ---------------------------------------------------------------------------
# Las dos lentes sobre el saldo del cliente (§7.7)
# ---------------------------------------------------------------------------

def _saldo_por_condic(cliente, empresa_id, condics):
    """Saldo de cuenta corriente restringido a ciertos `condic`.

    `ClienteProveedor.saldo` es la suma de todo y no distingue: sirve como lente
    OPERATIVA. Para la lente FISCAL hay que recorrer los comprobantes.
    """
    from django.db.models import F, Sum
    from django.db.models.functions import Coalesce
    from django.db import models as djmodels
    from facturacion.models import Venta
    from tesoreria.models import Recibo

    campo = djmodels.DecimalField(max_digits=15, decimal_places=2)
    ventas = Venta.objects.filter(
        cliente=cliente, empresa_id=empresa_id, estado=0, condic__in=condics
    ).aggregate(s=Coalesce(Sum(F('total') - F('cobrado')), Decimal('0'),
                           output_field=campo))['s']
    recibos = Recibo.objects.filter(
        cliente=cliente, empresa_id=empresa_id, anulado=False, condic__in=condics
    ).aggregate(s=Coalesce(Sum('total'), Decimal('0'), output_field=campo))['s']
    return Decimal(str(ventas or 0)) - Decimal(str(recibos or 0))


def saldo_fiscal(cliente, empresa_id):
    """Lente CONTABLE / FISCAL: sólo `condic = 1`. Es la que va a los estados contables."""
    return _saldo_por_condic(cliente, empresa_id, (REAL,))


def saldo_operativo(cliente, empresa_id):
    """Lente OPERATIVA: `condic 1 + 2` netos entre sí.

    Es la que ve el vendedor, la que usa el límite de crédito y la que sale impresa en la
    Hoja de Ruta: al cliente hay que cobrarle todo lo que debe, tenga o no respaldo fiscal.
    """
    return _saldo_por_condic(cliente, empresa_id, (REAL, PRESUPUESTADO))


# ---------------------------------------------------------------------------
# El FIFO
# ---------------------------------------------------------------------------

def comprobantes_abiertos(cliente, empresa_id, condic=None):
    """Comprobantes con saldo deudor, del más viejo al más nuevo.

    El orden es el del FIFO: primero la fecha, después el número, para que dos
    comprobantes del mismo día se cancelen en el orden en que se emitieron. La venta del
    propio reparto entra por su fecha —la más reciente— y por eso se cancela al final,
    salvo que sea el único comprobante abierto.
    """
    from facturacion.models import Venta

    qs = (Venta.objects
          .filter(cliente=cliente, empresa_id=empresa_id, estado=0, saldo__gt=0)
          .select_related('tipo'))
    if condic is not None:
        qs = qs.filter(condic=condic)
    return qs.order_by('fecha', 'numero')


def _imputar(saldos, disponible, condics):
    """Recorre los comprobantes de esos `condic` aplicando lo que haya, hasta agotarlo.

    `saldos` es {venta: saldo_pendiente} y se MUTA: así el tramo trazable y el de efectivo
    comparten el estado y ninguno de los dos puede aplicar dos veces sobre el mismo peso.
    Devuelve `(aplicaciones, sobrante)`.
    """
    aplicaciones = []
    for venta in list(saldos.keys()):
        if disponible <= CERO:
            break
        if venta.condic not in condics:
            continue
        pendiente = saldos[venta]
        if pendiente <= CERO:
            continue
        importe = min(disponible, pendiente)
        aplicaciones.append({'venta': venta, 'importe': importe, 'condic': venta.condic})
        saldos[venta] = pendiente - importe
        disponible -= importe
    return aplicaciones, disponible


def planificar(cliente, empresa_id, valores):
    """Calcula la imputación SIN persistir nada. Es lo que se muestra en pantalla.

    `valores` es una lista de dicts con al menos `categoria` e `importe`, tal como los
    arma el formulario de cobranza del ERP.

    Devuelve un dict con los dos tramos, las aplicaciones resultantes por `condic`, el
    excedente y los totales, listo para previsualizar o para pasarle a `registrar()`.
    """
    trazable = CERO
    efectivo = CERO
    for valor in valores:
        importe = Decimal(str(valor.get('importe') or 0))
        if importe <= CERO:
            continue
        if (valor.get('categoria') or '').upper() in CATEGORIAS_TRAZABLES:
            trazable += importe
        else:
            efectivo += importe

    # Un único diccionario de saldos compartido por los dos tramos: es lo que garantiza
    # que el efectivo no vuelva a aplicar sobre lo que ya canceló el cheque.
    abiertos = list(comprobantes_abiertos(cliente, empresa_id))
    saldos = {v: Decimal(str(v.saldo or 0)) for v in abiertos}

    # 1. Tramo trazable → sólo Real. Lo que sobre queda como anticipo en el circuito fiscal.
    aplic_trazable, sobra_trazable = _imputar(saldos, trazable, (REAL,))

    # 2. Tramo efectivo → primero todos los PRE, después las facturas.
    aplic_pre, resto = _imputar(saldos, efectivo, (PRESUPUESTADO,))
    aplic_efe_real, sobra_efectivo = _imputar(saldos, resto, (REAL,))

    # Las aplicaciones se agrupan por el `condic` del COMPROBANTE, que es el que define en
    # qué recibo entra cada una: el asiento hereda el condic del comprobante.
    por_condic = {REAL: [], PRESUPUESTADO: []}
    for aplicacion in aplic_trazable + aplic_efe_real + aplic_pre:
        por_condic[aplicacion['condic']].append(aplicacion)

    aplicado_real = sum((a['importe'] for a in por_condic[REAL]), CERO)
    aplicado_pre = sum((a['importe'] for a in por_condic[PRESUPUESTADO]), CERO)

    return {
        'trazable': trazable,
        'efectivo': efectivo,
        'total': trazable + efectivo,
        'aplicaciones': por_condic,
        'aplicado_real': aplicado_real,
        'aplicado_presupuestado': aplicado_pre,
        # Todo el excedente queda en el circuito FISCAL, como anticipo del cliente: es
        # donde se puede justificar de dónde salió la plata. Si sobró efectivo es porque
        # ya no quedaba ningún PRE que cancelar, así que no hay otro lugar donde ponerlo.
        'excedente': sobra_trazable + sobra_efectivo,
        # Efectivo que terminó cancelando comprobantes Reales.
        'efectivo_a_real': sum((a['importe'] for a in aplic_efe_real), CERO),
        'efectivo_a_presupuestado': aplicado_pre,
        # Efectivo que VIAJA en el recibo Real: todo el que no cancela PRE, incluido el
        # sobrante. Es lo que hace que la suma de los detalles dé el total del recibo.
        'efectivo_en_recibo_real': efectivo - aplicado_pre,
        'comprobantes': abiertos,
    }


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------

def _medio_pago(empresa_id, categoria, codigo_preferido=None):
    """Medio de pago de la empresa para esa categoría, con el código exacto si existe.

    El EFECTIVO no pasa por acá: tiene su propio medio, apuntado a `cta_caja_reparto`, para
    que el asiento del recibo no lo mande a la cuenta de la caja mostrador (ver
    `caja_reparto.medio_pago_efectivo`). Los medios trazables sí son los generales: una
    transferencia entra al banco, no a una caja.
    """
    from tesoreria.models import MedioPago

    qs = MedioPago.objects.filter(empresa_id=empresa_id, activo=True)
    medio = qs.filter(codigo=codigo_preferido).first() if codigo_preferido else None
    return medio or qs.filter(categoria=categoria).first()


def _crear_recibo(*, empresa_id, sucursal_id, ejercicio_id, cliente, sesion_caja, fecha,
                  punto, total, condic, usuario, observaciones):
    from tesoreria.models import Recibo

    recibo = Recibo(
        empresa_id=empresa_id, sucursal_id=sucursal_id, ejercicio_id=ejercicio_id,
        sesion_caja=sesion_caja, cliente=cliente, fecha=fecha, punto=punto,
        tipo='C', total=total, condic=condic, observaciones=observaciones,
        creado_por=usuario, modificado_por=usuario)
    # El número lo pone `Recibo.save()`, que es el mecanismo del ERP para este documento:
    # continúa la serie de (empresa, punto) sin abrir una paralela.
    recibo.save()
    return recibo


@transaction.atomic
def registrar(reparto, cliente, valores, usuario, *, parada=None, cobrador=None,
              fecha=None, observaciones=None, sucursal_id=None):
    """Registra la cobranza completa: hasta dos recibos, con sus aplicaciones y asientos.

    `reparto` puede ser None: es la cobranza que hace un VENDEDOR por su cuenta, sin hoja
    de ruta (Plan 076 §C). En ese caso el `cobrador` es obligatorio —la plata siempre tiene
    un responsable— y cae en la sesión recaudadora abierta a su nombre. El FIFO y las dos
    reglas de imputación son exactamente los mismos: no hay caso especial.

    Devuelve la lista de recibos creados, del `condic = 1` al `condic = 2`.
    """
    from contable.services.contabilizacion import contabilizar_recibo
    from contable.services.saldos import (recalcular_saldo_cliente_proveedor,
                                          recalcular_saldo_venta)
    from verticalidades.distribucion.models import CobranzaDistribucion
    from tesoreria.models import (MovimientoCaja, MovimientoCajaDetalle,
                                  ReciboAplicacion)
    from tesoreria.services.imputacion import estampar_asiento

    from verticalidades.distribucion.services.caja_reparto import abrir_caja_del_vendedor

    if reparto is not None:
        if reparto.estado not in (reparto.CERRADO, reparto.RENDIDO):
            raise ValueError(
                "Sólo se cobra sobre un reparto que ya salió: cerralo antes de cargar la cobranza.")
        if not reparto.sesion_caja_id:
            raise ValueError("El reparto no tiene abierta su caja recaudadora.")
        if reparto.sesion_caja.estado != 'A':
            raise ValueError("La caja recaudadora del reparto ya está cerrada.")
        empresa_id = reparto.empresa_id
        sesion = reparto.sesion_caja
        sucursal_id = reparto.sucursal_id
    else:
        # Cobranza de un vendedor, sin reparto. Sin responsable identificado la plata no
        # tiene dueño y no se puede reclamar un faltante: por eso el cobrador es obligatorio.
        if cobrador is None:
            raise ValueError(
                "Una cobranza sin reparto tiene que decir qué vendedor la trajo.")
        empresa_id = cobrador.empresa_id
        if not sucursal_id:
            raise ValueError(
                "Falta la sucursal en la que el vendedor deposita lo que cobra.")
        sesion = abrir_caja_del_vendedor(cobrador, usuario, sucursal_id)
        parada = None
    plan = planificar(cliente, empresa_id, valores)
    if plan['total'] <= CERO:
        raise ValueError("La cobranza no tiene importe.")

    fecha = fecha or timezone.localdate()
    ejercicio_id = _ejercicio_de(empresa_id, fecha)

    # Cuánto viaja en cada recibo. El recibo Presupuestado lleva EXACTAMENTE el efectivo
    # que canceló PRE; todo el resto —trazables, efectivo aplicado a facturas y el
    # excedente— va al recibo Real. Así los dos totales suman lo que entró en la caja.
    total_pre = plan['efectivo_a_presupuestado']
    total_real = plan['total'] - total_pre

    recibos = []
    for condic, total in ((REAL, total_real), (PRESUPUESTADO, total_pre)):
        if total <= CERO:
            continue

        recibo = _crear_recibo(
            empresa_id=empresa_id, sucursal_id=sucursal_id,
            ejercicio_id=ejercicio_id, cliente=cliente,
            sesion_caja=sesion, fecha=fecha, punto=sucursal_id,
            total=total, condic=condic, usuario=usuario, observaciones=observaciones)

        for aplicacion in plan['aplicaciones'][condic]:
            if aplicacion['importe'] <= CERO:
                continue
            ReciboAplicacion.objects.create(
                recibo=recibo, venta=aplicacion['venta'],
                importe=aplicacion['importe'], importe_pesos=aplicacion['importe'])
            # El saldo se DERIVA de las aplicaciones, nunca se decrementa (Plan 035 §1.3).
            recalcular_saldo_venta(aplicacion['venta'].pk)

        origen = (f"reparto {reparto.numero}" if reparto is not None
                  else f"vendedor {cobrador.nombre}")
        movimiento = MovimientoCaja.objects.create(
            sesion=sesion, empresa_id=empresa_id, fecha=fecha, tipo='I',
            importe=total,
            concepto=f"Cobranza {origen} - Recibo {recibo.numero}",
            condic=condic, recibo=recibo, cli_pro=cliente, creado_por=usuario)

        for medio_id, importe in _detalles_del_recibo(empresa_id, valores, plan, condic).items():
            MovimientoCajaDetalle.objects.create(
                movimiento_caja=movimiento, medio_pago_id=medio_id,
                importe=importe, importe_moneda_extranjera=CERO, cotizacion=Decimal('1.0'))

        # Va al final: el DEBE del asiento se arma leyendo los medios de cobro, que recién
        # ahora existen.
        asiento = contabilizar_recibo(recibo)
        estampar_asiento(movimiento, asiento)

        CobranzaDistribucion.objects.create(
            recibo=recibo, reparto=reparto, parada=parada, cobrador=cobrador,
            tramo=_tramo_de(plan, condic),
            excedente=plan['excedente'] if condic == REAL else CERO)
        recibos.append(recibo)

    recalcular_saldo_cliente_proveedor(cliente.pk)
    return recibos


def _tramo_de(plan, condic):
    from verticalidades.distribucion.models import CobranzaDistribucion

    if condic == PRESUPUESTADO:
        return CobranzaDistribucion.EFECTIVO
    if plan['trazable'] > CERO and plan['efectivo_en_recibo_real'] > CERO:
        return CobranzaDistribucion.MIXTO
    return (CobranzaDistribucion.TRAZABLE if plan['trazable'] > CERO
            else CobranzaDistribucion.EFECTIVO)


def _detalles_del_recibo(empresa_id, valores, plan, condic):
    """Reparte los medios de pago entre los dos recibos. Devuelve {medio_pago_id: importe}.

    Los trazables van enteros al recibo Real; el efectivo se prorratea según cuánto de él
    terminó en cada `condic`. La suma de los detalles tiene que dar el total del recibo:
    si no, el asiento no cierra.
    """
    detalles = {}

    def sumar(medio, importe):
        if not medio:
            raise ValueError(
                "No hay un medio de pago configurado para uno de los valores cobrados.")
        detalles[medio.id] = detalles.get(medio.id, CERO) + importe

    if condic == REAL:
        for valor in valores:
            importe = Decimal(str(valor.get('importe') or 0))
            categoria = (valor.get('categoria') or '').upper()
            if importe <= CERO or categoria not in CATEGORIAS_TRAZABLES:
                continue
            sumar(_medio_pago(empresa_id, categoria, valor.get('codigo_medio')), importe)
        efectivo = plan['efectivo_en_recibo_real']
    else:
        efectivo = plan['efectivo_a_presupuestado']

    if efectivo > CERO:
        from verticalidades.distribucion.services.caja_reparto import medio_pago_efectivo
        sumar(medio_pago_efectivo(empresa_id), efectivo)
    return detalles


def _ejercicio_de(empresa_id, fecha):
    from contable.models import Ejercicio

    ejercicio = Ejercicio.objects.filter(
        empresa_id=empresa_id, inicio__lte=fecha, cierre__gte=fecha).first()
    if not ejercicio:
        raise ValueError(f"No hay un ejercicio contable abierto para el {fecha:%d/%m/%Y}.")
    return ejercicio.id
