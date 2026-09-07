"""Acondicionamiento: procesos de planta, mermas y coproductos (Plan 086 — Etapa 5).

LA DISTINCIÓN QUE JUSTIFICA TODO EL MÓDULO
    merma      = kilos que DESAPARECEN
    coproducto = kilos que dejan de ser tabaco de la variedad y pasan a ser otra cosa vendible

Sin separarlos, el palo se registraría como merma y se perdería un activo real. Con la separación:

    stock(variedad)   = Σ fardos − Σ kilos_baja      # baja = entrada − salida
    stock(coproducto) = Σ coproducto.kilos           # reaparece en su propio producto

`kilos_baja` incluye los coproductos justamente porque ya no son tabaco de esa variedad.

NO GENERA ASIENTOS, Y ES A PROPÓSITO
Los insumos se compran con una `Compra` normal, que ya generó su asiento, su Libro IVA y su deuda.
Acá sólo se IMPUTA ese costo al lote para medir el margen. Contabilizarlo de nuevo duplicaría el
gasto en el balance. Ver la cabecera de `models.py`, §Etapa 5.

DA-07 SE RESUELVE POR CONFIGURACIÓN
Qué procesos existen es un dato del maestro `ProcesoAcondicionamiento`, no una decisión de código.
Este módulo sabe que un proceso toma kilos, devuelve kilos, consume plata y pierde peso; el resto
lo carga el usuario.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max, Sum
from django.utils import timezone

from ..models import (Acondicionamiento, AcondicionamientoCoproducto, AcondicionamientoCosto,
                      FardoTabaco, LoteAcopio)

CERO = Decimal('0.00')
DOS = Decimal('0.01')


# ---------------------------------------------------------------------------
# Alta y detalle
# ---------------------------------------------------------------------------

@transaction.atomic
def abrir_acondicionamiento(lote, *, proceso, fecha, kilos_entrada, kilos_salida,
                            motivo_merma='', observaciones='', usuario=None):
    """Crea la corrida en BORRADOR. No mueve stock hasta cerrarla."""
    lote = LoteAcopio.objects.select_for_update().get(pk=lote.pk)

    if lote.estado in (LoteAcopio.BORRADOR, LoteAcopio.ANULADO):
        raise ValidationError(
            f"El lote está en «{lote.get_estado_display()}»: armalo antes de acondicionarlo.")
    if proceso.empresa_id != lote.empresa_id:
        raise ValidationError("El proceso pertenece a otra empresa.")

    kilos_entrada = Decimal(kilos_entrada or 0)
    kilos_salida = Decimal(kilos_salida or 0)
    _validar_kilos(lote, kilos_entrada, kilos_salida)

    ultimo = lote.acondicionamientos.aggregate(m=Max('numero'))['m'] or 0

    acond = Acondicionamiento.objects.create(
        lote=lote,
        proceso=proceso,
        numero=ultimo + 1,
        fecha=fecha,
        kilos_entrada=kilos_entrada,
        kilos_salida=kilos_salida,
        # Se congela el % del maestro: si mañana se corrige el proceso, esta corrida no cambia.
        porcentaje_merma_normal_aplicado=proceso.merma_normal_porcentaje,
        motivo_merma=(motivo_merma or '').strip(),
        observaciones=(observaciones or '').strip(),
        estado=Acondicionamiento.BORRADOR,
        creado_por=usuario,
        modificado_por=usuario,
    )
    recalcular_acondicionamiento(acond)
    return acond


@transaction.atomic
def editar_acondicionamiento(acond, *, proceso=None, fecha=None, kilos_entrada=None,
                             kilos_salida=None, motivo_merma=None, observaciones=None,
                             usuario=None):
    acond = _exigir_borrador(acond)

    if proceso is not None:
        if proceso.empresa_id != acond.lote.empresa_id:
            raise ValidationError("El proceso pertenece a otra empresa.")
        acond.proceso = proceso
        acond.porcentaje_merma_normal_aplicado = proceso.merma_normal_porcentaje
    if fecha is not None:
        acond.fecha = fecha
    if kilos_entrada is not None:
        acond.kilos_entrada = Decimal(kilos_entrada or 0)
    if kilos_salida is not None:
        acond.kilos_salida = Decimal(kilos_salida or 0)
    if motivo_merma is not None:
        acond.motivo_merma = (motivo_merma or '').strip()
    if observaciones is not None:
        acond.observaciones = (observaciones or '').strip()

    _validar_kilos(acond.lote, acond.kilos_entrada, acond.kilos_salida, excluir=acond.pk)

    acond.modificado_por = usuario
    acond.save()
    recalcular_acondicionamiento(acond)
    return acond


@transaction.atomic
def agregar_coproducto(acond, *, producto, kilos, valor_estimado=CERO, observaciones=''):
    """Registra kilos que salen del proceso como otro producto vendible."""
    acond = _exigir_borrador(acond)

    kilos = Decimal(kilos or 0)
    if kilos <= 0:
        raise ValidationError("Los kilos del coproducto tienen que ser mayores que cero.")
    if producto.pk == acond.lote.variedad.producto_id:
        raise ValidationError(
            "El coproducto no puede ser el mismo producto que el tabaco del lote: "
            "esos kilos son la salida del proceso, no un coproducto.")
    if acond.coproductos.filter(producto=producto).exists():
        raise ValidationError(f"«{producto.detalle}» ya está cargado en este acondicionamiento.")

    linea = AcondicionamientoCoproducto.objects.create(
        acondicionamiento=acond, producto=producto, kilos=kilos,
        valor_estimado=Decimal(valor_estimado or 0),
        observaciones=(observaciones or '').strip())
    recalcular_acondicionamiento(acond)
    return linea


@transaction.atomic
def quitar_coproducto(linea):
    acond = _exigir_borrador(linea.acondicionamiento)
    linea.delete()
    recalcular_acondicionamiento(acond)
    return acond


@transaction.atomic
def agregar_costo(acond, *, concepto, importe, compra=None):
    """Imputa un costo directo al lote. `compra` es respaldo, no dispara contabilidad."""
    acond = _exigir_borrador(acond)

    importe = Decimal(importe or 0)
    if importe < 0:
        raise ValidationError("El importe del costo no puede ser negativo.")
    if not (concepto or '').strip():
        raise ValidationError("El costo necesita un concepto.")
    if compra is not None and compra.empresa_id != acond.lote.empresa_id:
        raise ValidationError("La compra de respaldo pertenece a otra empresa.")

    linea = AcondicionamientoCosto.objects.create(
        acondicionamiento=acond, concepto=concepto.strip(), importe=importe, compra=compra)
    recalcular_acondicionamiento(acond)
    return linea


@transaction.atomic
def quitar_costo(linea):
    acond = _exigir_borrador(linea.acondicionamiento)
    linea.delete()
    recalcular_acondicionamiento(acond)
    return acond


# ---------------------------------------------------------------------------
# Cierre y anulación — los dos momentos en que se mueve el stock
# ---------------------------------------------------------------------------

@transaction.atomic
def cerrar_acondicionamiento(acond, usuario=None):
    """Da por terminada la corrida: recién acá bajan los kilos y entran los coproductos.

    Es idempotente. Un borrador todavía se está cargando y no puede mover existencias: si lo
    hiciera, el stock bailaría mientras el operario tipea.
    """
    acond = Acondicionamiento.objects.select_for_update().select_related(
        'lote', 'lote__variedad', 'proceso').get(pk=acond.pk)

    if acond.estado == Acondicionamiento.ANULADO:
        raise ValidationError("El acondicionamiento está anulado: no se puede cerrar.")
    if acond.estado == Acondicionamiento.CERRADO:
        return acond

    recalcular_acondicionamiento(acond)

    # Se revalidan los kilos ACÁ y no sólo al abrir: dos borradores abiertos a la vez pueden
    # sumar, cada uno por su lado, más kilos de los que el lote tiene. Al abrirlos ninguno de los
    # dos podía saberlo, porque un borrador todavía no descuenta nada.
    _validar_kilos(acond.lote, acond.kilos_entrada, acond.kilos_salida, excluir=acond.pk)

    # La merma extraordinaria es la ÚNICA que el modelo obliga a justificar: lo que excede la
    # merma normal del proceso es una pérdida que alguien tiene que explicar.
    if acond.merma_extraordinaria > 0 and not acond.motivo_merma:
        raise ValidationError(
            f"La merma supera en {acond.merma_extraordinaria} kg la normal del proceso "
            f"({acond.porcentaje_merma_normal_aplicado} %). Indicá el motivo.")

    acond.estado = Acondicionamiento.CERRADO
    acond.modificado_por = usuario
    acond.save(update_fields=['estado', 'modificado_por'])

    _cerrar_efectos(acond, usuario)
    return acond


@transaction.atomic
def anular_acondicionamiento(acond, motivo, usuario=None):
    """Revierte los efectos de stock sin borrar el registro del proceso."""
    acond = Acondicionamiento.objects.select_for_update().select_related(
        'lote', 'lote__variedad').get(pk=acond.pk)

    if acond.estado == Acondicionamiento.ANULADO:
        return acond
    if not (motivo or '').strip():
        raise ValidationError("La anulación exige un motivo.")
    if acond.lote.venta_id:
        raise ValidationError(
            "El lote ya está vendido: quitá primero la venta para poder anular el proceso.")

    acond.estado = Acondicionamiento.ANULADO
    acond.motivo_anulacion = motivo.strip()
    acond.anulado_por = usuario
    acond.anulado_el = timezone.now()
    acond.modificado_por = usuario
    acond.save(update_fields=['estado', 'motivo_anulacion', 'anulado_por', 'anulado_el',
                              'modificado_por'])

    _cerrar_efectos(acond, usuario)
    return acond


def _cerrar_efectos(acond, usuario=None):
    """Recalcula stock y lote después de que la corrida cruzó el umbral de contar o no contar."""
    from .lotes import recalcular_lote
    from .stock import recalcular_stock_del_acondicionamiento

    lote = LoteAcopio.objects.select_for_update().get(pk=acond.lote_id)
    recalcular_lote(lote)

    hay_cerrados = lote.acondicionamientos.filter(estado=Acondicionamiento.CERRADO).exists()
    if lote.estado in (LoteAcopio.ARMADO, LoteAcopio.ACONDICIONADO):
        nuevo = LoteAcopio.ACONDICIONADO if hay_cerrados else LoteAcopio.ARMADO
        if lote.estado != nuevo:
            lote.estado = nuevo
            lote.modificado_por = usuario
            lote.save(update_fields=['estado', 'modificado_por'])
        lote.fardos.update(estado=FardoTabaco.ACONDICIONADO if hay_cerrados
                           else FardoTabaco.EN_LOTE)

    recalcular_stock_del_acondicionamiento(acond)


# ---------------------------------------------------------------------------
# Derivados
# ---------------------------------------------------------------------------

def recalcular_acondicionamiento(acond):
    """Reconstruye los kilos y los importes derivados desde las líneas. Nunca por delta."""
    coprod = acond.coproductos.aggregate(k=Sum('kilos'), v=Sum('valor_estimado'))
    acond.kilos_coproductos = coprod['k'] or CERO
    acond.valor_coproductos = coprod['v'] or CERO
    acond.costo_total = acond.costos.aggregate(s=Sum('importe'))['s'] or CERO

    # Todo lo que dejó de ser tabaco de esta variedad, coproductos incluidos.
    acond.kilos_baja = acond.kilos_entrada - acond.kilos_salida
    # La pérdida propiamente dicha: lo que no reapareció en ningún lado.
    acond.kilos_merma = acond.kilos_baja - acond.kilos_coproductos

    acond.merma_normal_esperada = (
        acond.kilos_entrada * acond.porcentaje_merma_normal_aplicado / Decimal('100')
    ).quantize(DOS)
    acond.merma_extraordinaria = max(CERO, acond.kilos_merma - acond.merma_normal_esperada)

    acond.save(update_fields=['kilos_coproductos', 'valor_coproductos', 'costo_total',
                              'kilos_baja', 'kilos_merma', 'merma_normal_esperada',
                              'merma_extraordinaria'])
    return acond


# ---------------------------------------------------------------------------
# Guardas
# ---------------------------------------------------------------------------

def _exigir_borrador(acond):
    """Relee con bloqueo: el objeto en memoria puede venir cacheado y estar cerrado hace rato."""
    acond = Acondicionamiento.objects.select_for_update().select_related(
        'lote', 'lote__variedad').get(pk=acond.pk)
    if not acond.editable:
        raise ValidationError(
            f"El acondicionamiento está en «{acond.get_estado_display()}» y no se edita.")
    return acond


def _validar_kilos(lote, kilos_entrada, kilos_salida, excluir=None):
    if kilos_entrada <= 0:
        raise ValidationError("Los kilos de entrada tienen que ser mayores que cero.")
    if kilos_salida < 0:
        raise ValidationError("Los kilos de salida no pueden ser negativos.")
    if kilos_salida > kilos_entrada:
        raise ValidationError(
            "No pueden salir más kilos de los que entraron: el proceso no crea materia.")

    # No se puede procesar más de lo que queda en el lote. `kilos_actuales` ya descontó las bajas
    # de los acondicionamientos cerrados anteriores.
    otros = lote.acondicionamientos.filter(estado=Acondicionamiento.CERRADO)
    if excluir:
        otros = otros.exclude(pk=excluir)
    bajas = otros.aggregate(s=Sum('kilos_baja'))['s'] or CERO
    disponibles = lote.total_kilos - bajas
    if kilos_entrada > disponibles:
        raise ValidationError(
            f"El lote tiene {disponibles} kg disponibles y se quieren procesar {kilos_entrada} kg.")
