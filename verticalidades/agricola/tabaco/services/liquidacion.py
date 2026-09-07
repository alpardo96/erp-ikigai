"""Liquidación de compra de tabaco: cálculo, contabilización y anulación (Plan 083).

Es el primer servicio de la verticalidad con EFECTOS CONTABLES. Todo lo que toca contabilidad pasa
por los servicios autorizados del core:

    asiento         -> `contable.services.asientos.crear_asiento()`
    anulación       -> `contable.services.contabilizacion.anular_asiento_de_comprobante()`
    saldo del tercero -> `contable.services.saldos.recalcular_saldo_cliente_proveedor()`

El Libro IVA se puebla directo sobre `LibroIvaCompras` / `LibroIvaAlic`, que se cuelgan del
`asiento_id` —un entero, no un FK—. Ése es el punto de enganche que permite a una verticalidad
participar del subsistema fiscal sin que el core la conozca.

QUÉ NO HACE, Y ES DELIBERADO
No paga. La Orden de Pago y la retención de Ganancias son la Etapa 3. Ganancias no puede
practicarse acá porque su base es el acumulado mensual de lo PAGADO.

QUÉ SE CONGELA
La alícuota de IVA y cada regla de retención (alícuota, base, mínimo, cuenta) se copian en la
liquidación al confirmar. Un comprobante emitido no puede cambiar de importe porque después se
haya corregido un maestro.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Max, Q, Sum
from django.utils import timezone

from contable.models import Cuenta, LibroIvaAlic, LibroIvaCompras, ParametrosContables
from contable.services.asientos import crear_asiento
from contable.services.contabilizacion import anular_asiento_de_comprobante
from contable.services.saldos import recalcular_saldo_cliente_proveedor

from ..models import (ConfiguracionTabaco, LiquidacionDetalle, LiquidacionRetencion,
                      LiquidacionTabaco, RomaneoTabaco, TipoRetencionTabaco)

CERO = Decimal('0.00')
DOS = Decimal('0.01')
CIEN = Decimal('100')

RESPONSABLE_INSCRIPTO = 'RESPONSABLE INSCRIPTO'

# Módulo 5 = Compras. La liquidación ES una compra, así que se ubica ahí y aparece junto al resto
# en el Libro Diario y en los reportes filtrados por módulo, sin inventar un módulo nuevo.
MODULO_COMPRAS = 5


def _redondear(valor):
    return Decimal(valor).quantize(DOS, rounding=ROUND_HALF_UP)


def es_responsable_inscripto(productor):
    return (productor.condicion_iva or '').strip().upper() == RESPONSABLE_INSCRIPTO


# ---------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------

def retenciones_vigentes(empresa_id, fecha, momento=TipoRetencionTabaco.LIQUIDACION):
    """Conceptos activos y vigentes a `fecha` para ese momento.

    Se excluye `ACUM_MENSUAL` aunque estuviera mal configurada como LIQUIDACION: su base es el
    acumulado de lo pagado y calcularla acá daría un importe incorrecto. El formulario ya lo
    impide, pero un dato viejo o una carga por consola podrían haberlo dejado pasar.
    """
    return (TipoRetencionTabaco.objects
            .filter(empresa_id=empresa_id, activa=True, momento=momento,
                    vigencia_desde__lte=fecha)
            .filter(Q(vigencia_hasta__isnull=True) | Q(vigencia_hasta__gte=fecha))
            .exclude(tipo_base=TipoRetencionTabaco.ACUM_MENSUAL)
            .select_related('cuenta_contable')
            .order_by('codigo'))


def calcular(*, empresa, productor, neto, fecha, alicuota_iva=None):
    """Devuelve `(letra, codiva, alicuota, iva, retenciones, total)` sin grabar nada.

    Lo usa la pantalla para previsualizar antes de confirmar y el propio servicio de confirmación,
    de modo que lo que el operador ve y lo que se graba salen de la MISMA función.
    """
    neto = Decimal(neto)

    if alicuota_iva is None:
        config = ConfiguracionTabaco.objects.filter(empresa=empresa).first()
        alicuota_iva = config.alicuota_iva if config else Decimal('21.00')

    ri = es_responsable_inscripto(productor)
    if ri:
        letra = LiquidacionTabaco.A
        iva = _redondear(neto * Decimal(alicuota_iva) / CIEN)
    else:
        letra = LiquidacionTabaco.B
        alicuota_iva = CERO
        iva = CERO

    aplicadas = []
    for regla in retenciones_vigentes(empresa.pk, fecha):
        if regla.solo_responsable_inscripto and not ri:
            continue

        base = iva if regla.tipo_base == TipoRetencionTabaco.IVA else neto
        if base <= 0:
            continue
        if regla.minimo_no_imponible and base <= regla.minimo_no_imponible:
            continue

        importe = _redondear(base * Decimal(regla.alicuota) / CIEN)
        if importe <= 0:
            continue
        aplicadas.append({'regla': regla, 'base': base, 'importe': importe})

    retenido = sum((a['importe'] for a in aplicadas), CERO)
    return {
        'letra': letra,
        'codiva': LiquidacionTabaco.CODIVA_POR_LETRA[letra],
        'alicuota_iva': Decimal(alicuota_iva),
        'iva': iva,
        'retenciones': aplicadas,
        'total_retenciones': retenido,
        'total': _redondear(neto + iva - retenido),
    }


# ---------------------------------------------------------------------------
# Preparación del borrador
# ---------------------------------------------------------------------------

def romaneos_liquidables(empresa_id, productor):
    """Romaneos confirmados del productor que todavía no fueron liquidados."""
    return (RomaneoTabaco.objects
            .filter(empresa_id=empresa_id, productor=productor,
                    estado=RomaneoTabaco.CONFIRMADO, liquidacion__isnull=True)
            .select_related('variedad', 'campania')
            .order_by('fecha', 'numero'))


@transaction.atomic
def preparar_liquidacion(*, empresa, sucursal, productor, romaneos, fecha,
                         usuario=None, punto=None, origen_autorizacion=None,
                         cai='', cae='', vencimiento_autorizacion=None, numero=None):
    """Arma el borrador con su detalle agrupado por (romaneo, clase).

    No numera ni contabiliza: eso ocurre al confirmar.
    """
    romaneos = list(romaneos)
    if not romaneos:
        raise ValidationError("Hay que incluir al menos un romaneo.")

    _validar_romaneos(empresa, productor, romaneos)

    config = ConfiguracionTabaco.objects.filter(empresa=empresa).first()
    if config is None:
        raise ValidationError(
            "Falta la configuración del acopio (cuenta de bienes de cambio, punto de venta y CAI). "
            "Cargala en Configuración → Configuración del Acopio.")

    liq = LiquidacionTabaco.objects.create(
        empresa=empresa, sucursal=sucursal, productor=productor, fecha=fecha,
        periodo=fecha.strftime('%Y%m'),
        punto=punto if punto is not None else config.punto_venta,
        origen_autorizacion=origen_autorizacion or config.modo_autorizacion,
        cai=cai or config.cai, cae=cae,
        vencimiento_autorizacion=vencimiento_autorizacion or config.cai_vencimiento,
        numero=numero,
        # El `condic` se hereda del romaneo, no se elige de nuevo: el comprobante y el asiento
        # tienen que mirar la misma realidad que la recepción que los originó.
        condic=romaneos[0].condic,
        estado=LiquidacionTabaco.BORRADOR,
        creado_por=usuario, modificado_por=usuario,
    )

    for romaneo in romaneos:
        agrupado = (romaneo.fardos
                    .values('clase_id', 'clase__detalle', 'coeficiente_aplicado', 'precio_aplicado')
                    .annotate(kilos=Sum('kilos'), importe=Sum('importe'), fardos=Count('id'))
                    .order_by('clase__detalle'))
        for fila in agrupado:
            LiquidacionDetalle.objects.create(
                liquidacion=liq, romaneo=romaneo, clase_id=fila['clase_id'],
                fardos=fila['fardos'], kilos=fila['kilos'],
                coeficiente=fila['coeficiente_aplicado'], precio=fila['precio_aplicado'],
                importe=fila['importe'])

        romaneo.liquidacion = liq
        romaneo.save(update_fields=['liquidacion'])

    _recalcular_importes(liq)
    return liq


def _validar_romaneos(empresa, productor, romaneos):
    for r in romaneos:
        if r.empresa_id != empresa.pk:
            raise ValidationError(f"El romaneo {r.numero} pertenece a otra empresa.")
        if r.productor_id != productor.pk:
            raise ValidationError(
                f"El romaneo {r.numero} es de otro productor: una liquidación agrupa romaneos de "
                f"un solo productor.")
        if r.estado != RomaneoTabaco.CONFIRMADO:
            raise ValidationError(
                f"El romaneo {r.numero or '(borrador)'} está en estado "
                f"«{r.get_estado_display()}» y no se puede liquidar.")
        if r.liquidacion_id:
            raise ValidationError(
                f"El romaneo {r.numero} ya fue liquidado en {r.liquidacion}. "
                f"No se pueden liquidar dos veces los mismos kilos.")


@transaction.atomic
def _recalcular_importes(liq):
    """Reconstruye neto, IVA, retenciones y total desde el detalle y las reglas vigentes."""
    liq.neto = liq.detalles.aggregate(s=Sum('importe'))['s'] or CERO
    calculo = calcular(empresa=liq.empresa, productor=liq.productor,
                       neto=liq.neto, fecha=liq.fecha)

    liq.letra = calculo['letra']
    liq.codiva = calculo['codiva']
    liq.alicuota_iva = calculo['alicuota_iva']
    liq.iva = calculo['iva']
    liq.retenciones = calculo['total_retenciones']
    liq.total = calculo['total']
    liq.saldo = liq.total
    liq.save(update_fields=['neto', 'letra', 'codiva', 'alicuota_iva', 'iva',
                            'retenciones', 'total', 'saldo'])
    return calculo


# ---------------------------------------------------------------------------
# Confirmación
# ---------------------------------------------------------------------------

def siguiente_numero_propuesto(empresa_id, letra, punto):
    """Próximo número de la serie (empresa, letra, punto).

    NO usa el contador atómico del core, y es deliberado: en modo MANUAL el número real viene del
    talonario impreso o del comprobante en línea de ARCA, y un contador interno derivaría de la
    serie física en cuanto el operador cargue un número distinto al propuesto. Acá se PROPONE el
    siguiente y la garantía de unicidad la da el índice único `(empresa, letra, punto, numero)`.

    Cada letra lleva su propia serie, como en el sistema heredado (`maestro_id.lcta` / `lctb`).
    """
    ultimo = (LiquidacionTabaco.objects
              .filter(empresa_id=empresa_id, letra=letra, punto=punto, numero__isnull=False)
              .aggregate(m=Max('numero'))['m'] or 0)
    return ultimo + 1


@transaction.atomic
def confirmar_liquidacion(liquidacion, usuario=None):
    """Numera, congela las reglas, contabiliza y hace nacer la deuda. Idempotente.

    Bloquea la fila y relee el estado: sin eso, dos confirmaciones simultáneas consumirían dos
    números de la serie y generarían dos asientos para el mismo comprobante.
    """
    liq = LiquidacionTabaco.objects.select_for_update().get(pk=liquidacion.pk)

    if liq.estado == LiquidacionTabaco.ANULADA:
        raise ValidationError("La liquidación está anulada: no se puede confirmar.")
    if liq.estado == LiquidacionTabaco.CONFIRMADA:
        return liq                                  # ya confirmada: no se renumera ni se duplica

    if not liq.detalles.exists():
        raise ValidationError("No se puede confirmar una liquidación sin detalle.")

    calculo = _recalcular_importes(liq)

    if liq.origen_autorizacion == LiquidacionTabaco.MANUAL and not liq.cai:
        raise ValidationError(
            "En modo manual hay que cargar el CAI del talonario antes de confirmar.")

    if liq.numero is None:
        liq.numero = siguiente_numero_propuesto(liq.empresa_id, liq.letra, liq.punto)

    _congelar_retenciones(liq, calculo['retenciones'])

    asiento = _contabilizar(liq, usuario)
    liq.asiento_id = asiento.asiento_id

    _poblar_libro_iva(liq, asiento)

    liq.estado = LiquidacionTabaco.CONFIRMADA
    liq.modificado_por = usuario
    liq.save(update_fields=['numero', 'asiento_id', 'estado', 'modificado_por'])

    # Los romaneos pasan a LIQUIDADO: a partir de acá no se reclasifican ni se anulan sin anular
    # antes la liquidación.
    liq.romaneos.update(estado=RomaneoTabaco.LIQUIDADO)

    recalcular_saldo_cliente_proveedor(liq.productor_id)
    return liq


def _congelar_retenciones(liq, aplicadas):
    """Graba las retenciones con una copia de la regla. Se rehace en cada confirmación."""
    liq.retenciones_aplicadas.all().delete()
    for a in aplicadas:
        regla = a['regla']
        LiquidacionRetencion.objects.create(
            liquidacion=liq, tipo_retencion=regla,
            codigo=regla.codigo, detalle=regla.detalle, tipo_base=regla.tipo_base,
            alicuota=regla.alicuota, minimo_no_imponible=regla.minimo_no_imponible,
            cuenta_contable=regla.cuenta_contable,
            base=a['base'], importe=a['importe'])


def _contabilizar(liq, usuario):
    """Arma el asiento y lo crea por el servicio del core, que valida la partida doble."""
    config = ConfiguracionTabaco.objects.filter(empresa=liq.empresa).first()
    if config is None or config.cuenta_bienes_cambio_id is None:
        raise ValidationError(
            "Falta configurar la cuenta de Bienes de Cambio del acopio para poder contabilizar.")

    parametros = ParametrosContables.objects.filter(empresa=liq.empresa).first()

    cuenta_productor = None
    if liq.productor.cta_pat:
        cuenta_productor = Cuenta.objects.filter(
            pk=liq.productor.cta_pat, empresa=liq.empresa, imputable=1).first()
    if cuenta_productor is None and parametros:
        cuenta_productor = parametros.cta_proveedores_default
    if cuenta_productor is None:
        raise ValidationError(
            "Falta la cuenta patrimonial del productor o la cuenta general de proveedores.")

    referencia = f"{liq.letra} {liq.punto:04d}-{liq.numero:08d}"
    concepto = (f"Productor: {liq.productor.razon_social}. "
                f"Liquidación Compra de Tabaco {referencia}")

    lineas = [{
        'cuenta': config.cuenta_bienes_cambio,
        'debe': liq.neto,
        'leyenda': f"Compra de tabaco {referencia}",
    }]

    if liq.iva > 0:
        if not parametros or not parametros.cta_iva_credito:
            raise ValidationError(
                "Falta configurar la cuenta de IVA Crédito Fiscal en los Parámetros Contables.")
        lineas.append({'cuenta': parametros.cta_iva_credito, 'debe': liq.iva,
                       'leyenda': f"IVA Crédito Fiscal {referencia}"})

    for ret in liq.retenciones_aplicadas.select_related('cuenta_contable'):
        lineas.append({'cuenta': ret.cuenta_contable, 'haber': ret.importe,
                       'leyenda': f"{ret.detalle} s/ {referencia}"})

    lineas.append({'cuenta': cuenta_productor, 'haber': liq.total,
                   'leyenda': concepto, 'cli_pro': liq.productor})

    return crear_asiento(
        empresa=liq.empresa, fecha=liq.fecha, concepto=concepto, lineas=lineas,
        condic=liq.condic, modulo=MODULO_COMPRAS, cli_pro=liq.productor, usuario=usuario)


def _poblar_libro_iva(liq, asiento):
    """Alimenta el subsistema fiscal. Idempotente: limpia antes de escribir.

    LETRA B: una compra a monotributista o exento no genera crédito fiscal, así que el importe va
    a `no_gravado` y NO se generan filas de alícuota. Es la única decisión fiscal de este módulo y
    está concentrada acá para poder cambiarla en un solo lugar si el estudio define otro criterio.
    """
    _limpiar_libro_iva(asiento.asiento_id)

    es_a = liq.letra == LiquidacionTabaco.A
    cuit = ''.join(filter(str.isdigit, (liq.productor.cuit or '')))[:11]

    LibroIvaCompras.objects.create(
        empresa=liq.empresa, asiento_id=asiento.asiento_id, fecha=liq.fecha,
        periodo=liq.periodo or liq.fecha.strftime('%Y%m'),
        clienteproveedor=liq.productor, codiva=liq.codiva,
        punto=liq.punto, numero=liq.numero, cuit=cuit,
        cae=liq.cae or liq.cai,
        neto_gravado=liq.neto if es_a else CERO,
        exento=CERO,
        no_gravado=CERO if es_a else liq.neto,
        iva_total=liq.iva,
        otros=liq.retenciones,
        total=liq.total,
    )

    if es_a and liq.iva > 0:
        LibroIvaAlic.objects.create(
            asiento_id=asiento.asiento_id, c_v='C', neto=liq.neto,
            alicuota=liq.alicuota_iva, iva=liq.iva, computable=liq.iva,
            codiva=liq.codiva)


def _limpiar_libro_iva(asiento_id):
    if not asiento_id:
        return
    LibroIvaCompras.objects.filter(asiento_id=asiento_id).delete()
    LibroIvaAlic.objects.filter(asiento_id=asiento_id, c_v='C').delete()


# ---------------------------------------------------------------------------
# Descarte de borradores
# ---------------------------------------------------------------------------

@transaction.atomic
def descartar_liquidacion(liquidacion):
    """Borra un borrador y libera sus romaneos.

    Existe como red de seguridad: `preparar_liquidacion` deja los romaneos tomados apenas se arma
    el borrador, así que un borrador abandonado los retendría —no volverían a figurar como
    pendientes— sin forma de recuperarlos. El circuito normal de la pantalla prepara y confirma en
    una sola transacción, pero un borrador puede llegar a existir por una carga por consola o por
    un flujo futuro que separe ambos pasos.

    Sólo aplica a BORRADORES: una liquidación confirmada se ANULA, no se borra, porque ya generó
    asiento y Libro IVA.
    """
    liq = LiquidacionTabaco.objects.select_for_update().get(pk=liquidacion.pk)

    if liq.estado != LiquidacionTabaco.BORRADOR:
        raise ValidationError(
            f"Sólo se descartan borradores. Esta liquidación está "
            f"«{liq.get_estado_display()}»: si querés dejarla sin efecto, anulala.")

    liq.romaneos.update(liquidacion=None)
    liq.delete()


# ---------------------------------------------------------------------------
# Anulación
# ---------------------------------------------------------------------------

@transaction.atomic
def anular_liquidacion(liquidacion, motivo, usuario=None):
    """Revierte la liquidación sin destruir la recepción física.

    Anula el asiento (que no se borra: se marca, por trazabilidad), limpia el Libro IVA, libera
    los romaneos para que puedan volver a liquidarse y recalcula el saldo del productor.

    Los FARDOS NO SE TOCAN: la mercadería entró y se pesó. Anular la liquidación dice que el
    comprobante no vale, no que la entrega no ocurrió.
    """
    liq = LiquidacionTabaco.objects.select_for_update().get(pk=liquidacion.pk)

    if liq.estado == LiquidacionTabaco.ANULADA:
        return liq
    if not (motivo or '').strip():
        raise ValidationError("La anulación exige un motivo.")
    if liq.pagado and liq.pagado > 0:
        raise ValidationError(
            "La liquidación tiene pagos imputados. Anulá primero la Orden de Pago.")

    if liq.asiento_id:
        anular_asiento_de_comprobante(liq.asiento_id)
        _limpiar_libro_iva(liq.asiento_id)

    # Los romaneos vuelven a CONFIRMADO y quedan disponibles para una liquidación nueva.
    liq.romaneos.update(estado=RomaneoTabaco.CONFIRMADO, liquidacion=None)

    liq.estado = LiquidacionTabaco.ANULADA
    liq.motivo_anulacion = motivo.strip()
    liq.anulada_por = usuario
    liq.anulada_el = timezone.now()
    liq.saldo = CERO
    liq.modificado_por = usuario
    liq.save(update_fields=['estado', 'motivo_anulacion', 'anulada_por', 'anulada_el',
                            'saldo', 'modificado_por'])

    recalcular_saldo_cliente_proveedor(liq.productor_id)
    return liq
