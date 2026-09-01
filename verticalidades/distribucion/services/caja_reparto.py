"""Caja recaudadora del reparto y rendición a Tesorería (Plan 074 §7.9).

POR QUÉ UNA CAJA `'R'` Y NO LA MOSTRADOR
----------------------------------------
La mostrador se abre y cierra por TURNO DE CAJERO, con arqueo ciego, en un puesto fijo.
La recaudadora se abre y cierra por REPARTO, la maneja alguien que está en la calle, y su
cierre se concilia contra la Hoja de Ruta. Son dos reglas de negocio distintas sobre la
misma estructura: un `tipo` explícito evita ramificar el código de la mostrador con
condicionales que no tienen nada que ver con ella.

DE QUIÉN ES LA PLATA LO DICE EL REPARTO, NO LA SESIÓN DE CAJA
-------------------------------------------------------------
`CajaSesion.usuario` es un `User`, y el repartidor puede no serlo: trabaja con la hoja de
ruta en papel y no necesita credenciales (§4.3). En la práctica el administrativo abre la
sesión y el `Reparto` dice de quién es la recaudación, a través de sus `responsables`. Es
otra razón por la que la caja se abre por reparto y no por cajero.

LOS TRES NIVELES DEL CIRCUITO (Plan 076 §B)
-------------------------------------------
    cobranzas ─► CAJA RECAUDADORA 'R'      una sesión por reparto
                        │
                        │  rendición en 2 pasos: el repartidor declara,
                        │  el administrativo cuenta y acepta
                        ▼
                 TESORERÍA DE REPARTO 'D'  UNA POR SUCURSAL. Acumula todas las rendiciones
                        │
                        │  retiro / cierre de caja (circuito existente, sin código nuevo)
                        ▼
                 CAJA TESORERÍA 'T'

El nivel del medio existe porque quien recibe a los repartidores NO es el tesorero central:
es un administrativo que cuenta lo que cada uno trae, lo retiene, y después entrega el
consolidado. Su cierre es un arqueo propio. Es la misma razón por la que existe la caja
mostrador de armería.

LA RENDICIÓN LA HACE `RetiroCaja`, QUE YA EXISTE
------------------------------------------------
Los dos pasos —uno declara, otro cuenta y acepta, la diferencia genera su asiento— ya están
implementados y probados en Tesorería. Acá no se reimplementa el mecanismo: se abre el
retiro desde la sesión del reparto con destino la tesorería de reparto.
`RendicionReparto` sólo agrega de qué reparto es esa plata.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

CERO = Decimal('0.00')


def cuenta_de_reparto(empresa_id):
    """La cuenta contable del efectivo que está en la calle (Plan 076 §B).

    Sin fallback a la mostrador a propósito: si el sistema la sustituyera en silencio, el
    balance mezclaría la plata del repartidor con la del cajero, que es exactamente lo que
    esta cuenta viene a separar. Mejor un error claro una vez que un número mal agrupado
    para siempre.
    """
    from contable.models import ParametrosContables

    parametros = ParametrosContables.objects.filter(empresa_id=empresa_id).first()
    if not parametros:
        raise ValueError("Faltan los Parámetros Contables de la empresa.")
    if not parametros.cta_caja_reparto:
        raise ValueError(
            "Falta configurar la 'Cta. Caja de Reparto (Distribución)' en Parámetros "
            "Contables: es la cuenta del efectivo que llevan los repartidores y los "
            "vendedores, y va separada de la caja mostrador porque el responsable es otro.")
    return parametros.cta_caja_reparto


def medio_pago_efectivo(empresa_id):
    """El medio de pago con el que entra el efectivo de distribución: el genérico.

    YA NO HACE FALTA UNO PROPIO. El Plan 076 creaba un `EFE-REP` apuntado a
    `cta_caja_reparto` porque el asiento seguía al medio de pago; desde el Plan 077 §E la
    cuenta del efectivo la resuelve LA CAJA, así que el medio común alcanza y queda un solo
    mecanismo en vez de dos. La función sobrevive para no dispersar el conocimiento de cuál
    es el medio de efectivo de la empresa.
    """
    from tesoreria.models import MedioPago

    qs = MedioPago.objects.filter(empresa_id=empresa_id, activo=True)
    medio = qs.filter(codigo='EFE-ARS').first() or qs.filter(categoria='EFE').first()
    if not medio:
        raise ValueError(
            "La empresa no tiene ningún medio de pago en efectivo configurado.")
    return medio


def caja_recaudadora(empresa_id, sucursal_id):
    """La caja recaudadora de la sucursal, creándola la primera vez.

    Es una sola por sucursal: lo que separa un reparto de otro es la SESIÓN, no la caja.
    """
    from tesoreria.models import Caja

    caja, _ = Caja.objects.get_or_create(
        empresa_id=empresa_id, sucursal_id=sucursal_id, tipo='R',
        defaults={'nombre': 'Recaudadora de Reparto', 'activa': True})
    return caja


def tesoreria_reparto(empresa_id, sucursal_id):
    """La Tesorería de Reparto de la sucursal, creándola la primera vez (Plan 076 §B).

    Es UNA POR SUCURSAL: acá rinden todos los repartos y todos los vendedores, y de acá
    sale una sola rendición consolidada a Tesorería.
    """
    from tesoreria.models import Caja

    caja, _ = Caja.objects.get_or_create(
        empresa_id=empresa_id, sucursal_id=sucursal_id, tipo='D',
        defaults={'nombre': 'Tesorería de Reparto', 'activa': True})
    return caja


@transaction.atomic
def sesion_de_tesoreria_reparto(empresa_id, sucursal_id, usuario):
    """Sesión abierta de la Tesorería de Reparto, abriéndola si hace falta.

    No depende del cajero de turno: es la caja de la sucursal, y siempre hay una activa
    para que quien recibe a un repartidor nunca quede bloqueado. Mismo criterio que
    `get_o_abrir_caja` de Tesorería.
    """
    from tesoreria.models import CajaSesion

    caja = tesoreria_reparto(empresa_id, sucursal_id)
    sesion = CajaSesion.objects.filter(caja=caja, estado='A').first()
    if sesion:
        return sesion
    return CajaSesion.objects.create(
        caja=caja, usuario=usuario, saldo_inicial=CERO, si_efectivo=CERO,
        estado='A', creado_por=usuario, modificado_por=usuario)


@transaction.atomic
def abrir_caja_del_reparto(reparto, usuario):
    """Abre la sesión de la caja recaudadora sobre la que van a entrar las cobranzas.

    Idempotente: si el reparto ya tiene su sesión abierta, la devuelve. El saldo inicial
    es cero porque el repartidor sale sin plata; lo único que va a entrar es lo que cobre.
    """
    from tesoreria.models import CajaSesion

    if reparto.sesion_caja_id and reparto.sesion_caja.estado == 'A':
        return reparto.sesion_caja

    caja = caja_recaudadora(reparto.empresa_id, reparto.sucursal_id)
    sesion = CajaSesion.objects.create(
        caja=caja, usuario=usuario, saldo_inicial=CERO, si_efectivo=CERO,
        estado='A', creado_por=usuario, modificado_por=usuario)
    reparto.sesion_caja = sesion
    reparto.save(update_fields=['sesion_caja'])
    return sesion


@transaction.atomic
def abrir_caja_del_vendedor(vendedor, usuario, sucursal_id=None):
    """Sesión de la caja recaudadora a nombre de un VENDEDOR (Plan 076 §C).

    PARA PODER RENDIR HAY QUE HABER RETENIDO. El vendedor cobra por su cuenta, sin reparto:
    esa plata tiene que caer en algún lado antes de que la entregue, o no habría nada que
    rendir. Se le abre una sesión sobre la misma caja recaudadora, y se mantiene abierta
    hasta que rinde.

    Es la misma estructura que un reparto, con otro dueño: la sesión no dice de quién es la
    plata —su `usuario` es un `User` y el vendedor puede no serlo—, lo dice la rendición.
    """
    from tesoreria.models import CajaSesion

    # `Personal` no tiene sucursal: el vendedor recorre, no está asignado a un depósito.
    # La sucursal la aporta quien opera, que es la de su sesión de trabajo.
    if not sucursal_id:
        raise ValueError(
            "Falta la sucursal en la que el vendedor deposita lo que cobra.")

    abierta = sesion_abierta_del_vendedor(vendedor, sucursal_id)
    if abierta:
        return abierta

    caja = caja_recaudadora(vendedor.empresa_id, sucursal_id)
    sesion = CajaSesion.objects.create(
        caja=caja, usuario=usuario, saldo_inicial=CERO, si_efectivo=CERO,
        estado='A', creado_por=usuario, modificado_por=usuario)
    # El vínculo se crea recién al rendir; mientras tanto la sesión se identifica por sus
    # cobranzas, que ya llevan el `cobrador`.
    return sesion


def sesion_abierta_del_vendedor(vendedor, sucursal_id=None):
    """La sesión recaudadora donde está cayendo lo que cobra este vendedor, si hay alguna.

    Se identifica por sus cobranzas: son las que llevan el `cobrador`. Una sesión de
    reparto nunca entra acá, porque sus cobranzas tienen `reparto` seteado.
    """
    from verticalidades.distribucion.models import CobranzaDistribucion
    from tesoreria.models import CajaSesion

    ids = (CobranzaDistribucion.objects
           .filter(cobrador=vendedor, reparto__isnull=True, recibo__anulado=False)
           .values_list('recibo__sesion_caja_id', flat=True))
    return CajaSesion.objects.filter(
        id__in=list(ids), caja__tipo='R', estado='A').order_by('-id').first()


def resumen_vendedor(vendedor):
    """Lo que este vendedor cobró y todavía no rindió."""
    from verticalidades.distribucion.models import CobranzaDistribucion

    cobranzas = (CobranzaDistribucion.objects
                 .filter(cobrador=vendedor, reparto__isnull=True, recibo__anulado=False)
                 .select_related('recibo', 'recibo__cliente'))

    efectivo, cobrado = CERO, CERO
    for cobranza in cobranzas:
        cobrado += Decimal(str(cobranza.recibo.total or 0))
        for movimiento in cobranza.recibo.movimientocaja_set.prefetch_related(
                'detalles__medio_pago'):
            efectivo += _efectivo_de(movimiento)

    rendido = sum(
        (Decimal(str(r.retiro.efectivo_pesos or 0))
         for r in vendedor.rendiciones.select_related('retiro')), CERO)

    return {
        'cobranzas': cobranzas,
        'cobrado': cobrado,
        'efectivo_cobrado': efectivo,
        'declarado': rendido,
        'pendiente_de_rendir': efectivo - rendido,
    }


@transaction.atomic
def rendir_vendedor(vendedor, usuario, *, efectivo_pesos, sucursal_id,
                    observaciones=None):
    """El vendedor entrega a la Tesorería de Reparto lo que viene cobrando (Plan 076 §C).

    Mismo mecanismo de dos pasos que el reparto: acá declara, y el administrativo cuenta y
    acepta desde la misma bandeja. Lo único distinto es de quién es la plata.
    """
    from verticalidades.distribucion.models import RendicionReparto
    from tesoreria.models import (MedioPago, MovimientoCaja, MovimientoCajaDetalle,
                                  RetiroCaja)

    efectivo_pesos = Decimal(str(efectivo_pesos or 0))
    if efectivo_pesos <= CERO:
        raise ValueError("La rendición no tiene importe.")

    sesion = sesion_abierta_del_vendedor(vendedor, sucursal_id)
    if not sesion:
        raise ValueError(
            f"{vendedor.nombre} no tiene cobranzas sin rendir: no hay nada que entregar.")

    empresa_id = vendedor.empresa_id
    retiro = RetiroCaja.objects.create(
        sesion=sesion, tipo='C', usuario=usuario,
        sucursal_origen_id=sucursal_id, sucursal_destino_id=sucursal_id,
        efectivo_pesos=efectivo_pesos, efectivo_dolares=CERO,
        cotizacion_dolar=Decimal('1.0'),
        observaciones=observaciones or f"Rendición del vendedor {vendedor.nombre}",
        creado_por=usuario, modificado_por=usuario)

    movimiento = MovimientoCaja.objects.create(
        sesion=sesion, empresa_id=empresa_id, fecha=timezone.localdate(), tipo='R',
        importe=efectivo_pesos,
        concepto=f"Rendición vendedor {vendedor.nombre} #{retiro.id}",
        condic=1, creado_por=usuario)
    MovimientoCajaDetalle.objects.create(
        movimiento_caja=movimiento, medio_pago=medio_pago_efectivo(empresa_id),
        importe=efectivo_pesos, importe_moneda_extranjera=CERO,
        cotizacion=Decimal('1.0'))

    RendicionReparto.objects.create(
        reparto=None, vendedor=vendedor, retiro=retiro,
        esperado=resumen_vendedor(vendedor)['efectivo_cobrado'],
        observaciones=observaciones)

    _cerrar_sesion(sesion, usuario)
    return retiro


def _efectivo_de(movimiento):
    """Parte en efectivo de un movimiento de caja, leída de sus detalles."""
    return sum((Decimal(str(d.importe)) for d in movimiento.detalles.all()
                if d.medio_pago.categoria == 'EFE'), CERO)


def resumen(reparto):
    """Cuadro ESPERADO vs. COBRADO vs. RENDIDO (§7.9, punto 4).

    - **Esperado**: la suma de los `cobro_minimo` congelados al cerrar el reparto. Es lo
      que el sistema le dijo al repartidor que no podía dejar de traer.
    - **Cobrado**: lo que efectivamente entró, abierto por medio de pago.
    - **Rendido**: lo que se declaró a Tesorería y lo que el tesorero contó.

    El cuadro es el cierre del circuito: sin él la recaudación queda sin control.
    """
    from verticalidades.distribucion.models import CobranzaDistribucion

    esperado = sum((Decimal(str(p.cobro_minimo or 0))
                    for p in reparto.paradas.all()), CERO)

    cobranzas = (CobranzaDistribucion.objects
                 .filter(reparto=reparto, recibo__anulado=False)
                 .select_related('recibo', 'recibo__cliente', 'parada', 'cobrador'))

    por_medio, cobrado, efectivo_cobrado = {}, CERO, CERO
    por_condic = {1: CERO, 2: CERO}
    for cobranza in cobranzas:
        total = Decimal(str(cobranza.recibo.total or 0))
        cobrado += total
        por_condic[cobranza.recibo.condic] = por_condic.get(
            cobranza.recibo.condic, CERO) + total
        for movimiento in cobranza.recibo.movimientocaja_set.prefetch_related(
                'detalles__medio_pago'):
            for detalle in movimiento.detalles.all():
                nombre = detalle.medio_pago.nombre
                por_medio[nombre] = por_medio.get(nombre, CERO) + Decimal(str(detalle.importe))
                if detalle.medio_pago.categoria == 'EFE':
                    efectivo_cobrado += Decimal(str(detalle.importe))

    from verticalidades.distribucion.models import NotaCreditoDistribucion

    notas_credito = list(NotaCreditoDistribucion.objects
                         .filter(parada__reparto=reparto)
                         .exclude(nota_credito__estado=1)
                         .select_related('nota_credito', 'motivo', 'parada__cliente'))
    total_nc = sum((abs(Decimal(str(n.nota_credito.total or 0))) for n in notas_credito), CERO)

    rendiciones = list(reparto.rendiciones.select_related('retiro').all())
    declarado = sum((Decimal(str(r.retiro.efectivo_pesos or 0)) for r in rendiciones), CERO)
    recibido = sum((Decimal(str(r.retiro.efectivo_pesos_recibido or 0))
                    for r in rendiciones if r.retiro.estado == 'R'), CERO)

    return {
        'esperado': esperado,
        'cobrado': cobrado,
        'cobrado_por_medio': sorted(por_medio.items()),
        'cobrado_real': por_condic.get(1, CERO),
        'cobrado_presupuestado': por_condic.get(2, CERO),
        'efectivo_cobrado': efectivo_cobrado,
        'declarado': declarado,
        'recibido': recibido,
        'pendiente_de_rendir': efectivo_cobrado - declarado,
        'cobranzas': cobranzas,
        'rendiciones': rendiciones,
        # La devolución baja lo que había que cobrar: sin verlas acá, el importe de la
        # mercadería que volvió parecería un faltante del repartidor.
        'notas_credito': notas_credito,
        'total_notas_credito': total_nc,
    }


@transaction.atomic
def rendir(reparto, usuario, *, efectivo_pesos, sucursal_destino_id=None,
           observaciones=None):
    """Paso 1 de la rendición: el repartidor declara lo que trae.

    El destino es la **Tesorería de Reparto**, no Tesorería (Plan 076 §B): el repartidor le
    entrega al administrativo, que después rinde el consolidado. Crea el `RetiroCaja` en
    estado 'En Tránsito' con su egreso de caja y sus asientos de traslado. El paso 2 —el
    administrativo cuenta y acepta— es `recibir()`, más abajo.
    """
    from verticalidades.distribucion.models import RendicionReparto
    from tesoreria.models import (MedioPago, MovimientoCaja, MovimientoCajaDetalle,
                                  RetiroCaja)

    if reparto.estado != reparto.CERRADO:
        raise ValueError("Sólo se rinde un reparto cerrado que todavía no fue rendido.")
    if not reparto.sesion_caja_id:
        raise ValueError("El reparto no tiene caja recaudadora abierta.")

    efectivo_pesos = Decimal(str(efectivo_pesos or 0))
    if efectivo_pesos < CERO:
        raise ValueError("No se puede rendir un importe negativo.")

    empresa_id = reparto.empresa_id
    datos = resumen(reparto)
    destino_id = sucursal_destino_id or reparto.sucursal_id

    retiro = RetiroCaja.objects.create(
        sesion=reparto.sesion_caja, tipo='C', usuario=usuario,
        sucursal_origen_id=reparto.sucursal_id, sucursal_destino_id=destino_id,
        efectivo_pesos=efectivo_pesos, efectivo_dolares=CERO,
        cotizacion_dolar=Decimal('1.0'),
        observaciones=observaciones or f"Rendición del reparto {reparto.numero_formateado}",
        creado_por=usuario, modificado_por=usuario)

    movimiento = None
    if efectivo_pesos > CERO:
        movimiento = MovimientoCaja.objects.create(
            sesion=reparto.sesion_caja, empresa_id=empresa_id, fecha=timezone.localdate(),
            tipo='R', importe=efectivo_pesos,
            concepto=f"Rendición reparto {reparto.numero} #{retiro.id}",
            condic=1, creado_por=usuario)
        MovimientoCajaDetalle.objects.create(
            movimiento_caja=movimiento, medio_pago=medio_pago_efectivo(empresa_id),
            importe=efectivo_pesos, importe_moneda_extranjera=CERO,
            cotizacion=Decimal('1.0'))

    # SIN ASIENTO DE TRASLADO EN ESTE TRAMO, y es deliberado. La recaudadora y la Tesorería
    # de Reparto son las dos "efectivo fuera de Tesorería" y comparten cuenta contable
    # (`cta_caja_reparto`), así que el asiento sería Debe y Haber sobre la misma cuenta:
    # ruido. Peor todavía sería asentar contra Caja Central, porque estaría registrando en
    # Tesorería plata que sigue en la calle.
    # El movimiento contable REAL ocurre en el segundo tramo, cuando la Tesorería de
    # Reparto rinde a Caja Tesorería por el retiro/cierre de siempre. Acá sólo se mueven
    # las cajas, que es lo que hay que reflejar: salió de una y entra en la otra.

    RendicionReparto.objects.create(
        reparto=reparto, retiro=retiro, esperado=datos['efectivo_cobrado'],
        observaciones=observaciones)

    # El reparto queda RENDIDO aunque el tesorero todavía no haya contado: para el
    # repartidor el trabajo terminó. Lo que falta es el paso 2, que vive en el retiro.
    reparto.estado = reparto.RENDIDO
    reparto.modificado_por = usuario
    reparto.save(update_fields=['estado', 'modificado_por'])

    _cerrar_sesion(reparto.sesion_caja, usuario)
    return retiro


@transaction.atomic
def recibir(retiro, usuario, *, contado_pesos):
    """Paso 2: el administrativo de reparto CUENTA lo que el repartidor trajo y lo acepta.

    EL QUE DECLARA NO ES EL MISMO QUE CUENTA. La diferencia entre lo declarado y lo contado
    genera su asiento contra la cuenta de Diferencias de Caja, igual que en la mostrador:
    un faltante tiene que quedar registrado, no absorbido en silencio.
    """
    from contable.models import ParametrosContables
    from tesoreria.models import (MedioPago, MovimientoCaja, MovimientoCajaDetalle,
                                  RetiroCaja)
    from tesoreria.views_htmx import _generar_asiento_diferencia

    if retiro.estado != 'T':
        raise ValueError("La rendición ya fue recibida o anulada.")

    contado_pesos = Decimal(str(contado_pesos or 0))
    if contado_pesos < CERO:
        raise ValueError("No se puede recibir un importe negativo.")

    empresa_id = retiro.sesion.caja.empresa_id
    sucursal_id = retiro.sucursal_destino_id
    sesion = sesion_de_tesoreria_reparto(empresa_id, sucursal_id, usuario)
    declarado = Decimal(str(retiro.efectivo_pesos or 0))
    diferencia = declarado - contado_pesos          # faltante (+) / sobrante (−)

    # Ingreso en la intermedia POR LO CONTADO, no por lo declarado: la caja tiene que
    # reflejar la plata que efectivamente está adentro.
    movimiento = MovimientoCaja.objects.create(
        sesion=sesion, empresa_id=empresa_id, fecha=timezone.localdate(), tipo='I',
        importe=contado_pesos,
        concepto=f"Rendición de reparto #{retiro.id} recibida",
        condic=1, creado_por=usuario)
    if contado_pesos > CERO:
        MovimientoCajaDetalle.objects.create(
            movimiento_caja=movimiento, medio_pago=medio_pago_efectivo(empresa_id),
            importe=contado_pesos, importe_moneda_extranjera=CERO,
            cotizacion=Decimal('1.0'))

    asiento_diferencia = None
    if diferencia != CERO:
        parametros = ParametrosContables.objects.filter(empresa_id=empresa_id).first()
        if not parametros or not parametros.cta_diferencia_caja:
            raise ValueError(
                "Falta configurar la 'Cta. Diferencias de Caja' en Parámetros Contables.")
        # Ajusta la caja de REPARTO: la plata contada está en la Tesorería de Reparto,
        # no en Tesorería. Ajustar la Central movería una cuenta donde no pasó nada.
        asiento_diferencia = _generar_asiento_diferencia(
            empresa_id, _ejercicio_de(empresa_id), sucursal_id, diferencia, parametros,
            timezone.localdate(), retiro, usuario,
            cuenta_caja=cuenta_de_reparto(empresa_id))

    retiro.estado = 'R'
    retiro.sesion_recepcion = sesion
    retiro.usuario_recepcion = usuario
    retiro.fecha_recepcion = timezone.localtime()
    retiro.efectivo_pesos_recibido = contado_pesos
    retiro.diferencia_pesos = diferencia
    retiro.asiento_diferencia_id = asiento_diferencia
    retiro.save()
    return retiro


def rendiciones_por_recibir(empresa_id, sucursal_id):
    """Rendiciones de reparto EN TRÁNSITO: declaradas y todavía sin contar."""
    from verticalidades.distribucion.models import RendicionReparto

    from django.db.models import Q

    # Los dos orígenes en la misma bandeja: para quien recibe es el mismo acto —contar lo
    # que alguien trajo— y separarlos sólo agregaría una pantalla más.
    return (RendicionReparto.objects
            .filter(Q(reparto__empresa_id=empresa_id) | Q(vendedor__empresa_id=empresa_id),
                    retiro__estado='T', retiro__sucursal_destino_id=sucursal_id)
            .select_related('retiro', 'reparto', 'vendedor')
            .prefetch_related('reparto__responsables'))


def _cerrar_sesion(sesion, usuario):
    """Cierra la sesión recaudadora: el reparto terminó, no entra nada más por esa caja."""
    if sesion.estado != 'A':
        return sesion
    sesion.estado = 'C'
    sesion.fecha_cierre = timezone.localtime()
    sesion.fecha_operativa = timezone.localdate()
    sesion.modificado_por = usuario
    sesion.save(update_fields=['estado', 'fecha_cierre', 'fecha_operativa',
                               'modificado_por'])
    return sesion


def _ejercicio_de(empresa_id, fecha=None):
    from contable.models import Ejercicio

    fecha = fecha or timezone.localdate()
    ejercicio = Ejercicio.objects.filter(
        empresa_id=empresa_id, inicio__lte=fecha, cierre__gte=fecha).first()
    if not ejercicio:
        raise ValueError(f"No hay un ejercicio contable abierto para el {fecha:%d/%m/%Y}.")
    return ejercicio.id
