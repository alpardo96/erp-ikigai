"""Lotes de acopio: armado, venta y totales derivados (Plan 086 — Etapa 5).

QUÉ ES UN LOTE
Un lote agrupa fardos YA COMPRADOS para venderlos juntos, sin perder la trazabilidad de cada
componente: el fardo sigue siendo el fardo, con su romaneo, su clase y su precio de compra.

TODO LO QUE SE MATERIALIZA SE RECONSTRUYE ENTERO
`total_kilos`, `costo_compra`, `importe_venta` y los demás no se ajustan por delta: los recalcula
`recalcular_lote()` desde los fardos y los acondicionamientos. Es el mismo criterio con el que el
core maneja el stock y la cuenta corriente, y por la misma razón: si una llamada no corre, el
valor queda mal y no hay desde dónde reconstruirlo.

ESTE MÓDULO NO GENERA ASIENTOS. Ver la cabecera de `models.py`, §Etapa 5.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from core.models import ContadorDocumento
from core.services.numeracion import siguiente_numero

from ..models import Acondicionamiento, FardoTabaco, LoteAcopio, RomaneoTabaco

CERO = Decimal('0.00')

# Un fardo sólo entra a un lote si su romaneo existe físicamente: el borrador todavía se está
# cargando y el anulado no ocurrió. Es la misma frontera que usa el término de stock.
ESTADOS_ROMANEO_VALIDOS = (RomaneoTabaco.CONFIRMADO, RomaneoTabaco.LIQUIDADO)


# ---------------------------------------------------------------------------
# Alta y armado
# ---------------------------------------------------------------------------

@transaction.atomic
def abrir_lote(*, empresa, sucursal, campania, variedad, fecha, descripcion='',
               observaciones='', punto=None, usuario=None):
    """Crea el lote en BORRADOR. El número se toma recién al armarlo."""
    if variedad.empresa_id != empresa.pk:
        raise ValidationError("La variedad pertenece a otra empresa.")

    return LoteAcopio.objects.create(
        empresa=empresa,
        sucursal=sucursal,
        punto=punto if punto is not None else getattr(sucursal, 'punto', 1) or 1,
        fecha=fecha,
        campania=campania,
        variedad=variedad,
        descripcion=(descripcion or '').strip(),
        observaciones=(observaciones or '').strip(),
        estado=LoteAcopio.BORRADOR,
        creado_por=usuario,
        modificado_por=usuario,
    )


@transaction.atomic
def agregar_fardo(lote, fardo, usuario=None):
    """Suma un fardo al lote validando que sea del mismo tabaco y del mismo galpón.

    Las tres validaciones no son burocracia:
    - **Variedad**: el stock se lleva por variedad; un lote mezclado no se podría imputar.
    - **Sucursal**: el stock es por sucursal; los kilos tienen que estar donde dice el lote.
    - **Romaneo vigente**: sólo se agrupa lo que existe físicamente.
    """
    lote = _exigir_editable(lote)
    fardo = FardoTabaco.objects.select_for_update().select_related('romaneo').get(pk=fardo.pk)

    if fardo.lote_id == lote.pk:
        return fardo                                     # idempotente: ya estaba
    if fardo.lote_id:
        raise ValidationError(
            f"El fardo {fardo.numero_fardo} ya pertenece al lote {fardo.lote}. "
            "Quitalo de ahí antes de agregarlo acá.")

    romaneo = fardo.romaneo
    if romaneo.estado not in ESTADOS_ROMANEO_VALIDOS:
        raise ValidationError(
            f"El romaneo del fardo {fardo.numero_fardo} está en «{romaneo.get_estado_display()}»: "
            "sólo se agrupan fardos de romaneos confirmados.")
    if romaneo.variedad_id != lote.variedad_id:
        raise ValidationError(
            f"El fardo es de {romaneo.variedad.detalle} y el lote es de {lote.variedad.detalle}. "
            "Un lote es de una sola variedad.")
    if romaneo.sucursal_id != lote.sucursal_id:
        raise ValidationError(
            "El fardo está en otra sucursal que el lote. El stock se lleva por sucursal.")

    fardo.lote = lote
    fardo.estado = FardoTabaco.EN_LOTE
    fardo.modificado_por = usuario
    fardo.save(update_fields=['lote', 'estado', 'modificado_por'])

    recalcular_lote(lote)
    return fardo


@transaction.atomic
def quitar_fardo(lote, fardo, usuario=None):
    """Saca un fardo del lote.

    Se prohíbe si el lote ya tiene un acondicionamiento cerrado: los costos y las mermas se
    prorratean por kilos, así que sacar un fardo después reescribiría en silencio el margen de
    todos los demás.
    """
    lote = _exigir_editable(lote)
    _exigir_sin_acondicionamiento_cerrado(lote, "quitar un fardo")

    fardo = FardoTabaco.objects.select_for_update().get(pk=fardo.pk)
    if fardo.lote_id != lote.pk:
        raise ValidationError("El fardo no pertenece a este lote.")

    fardo.lote = None
    fardo.estado = FardoTabaco.CLASIFICADO
    fardo.modificado_por = usuario
    fardo.save(update_fields=['lote', 'estado', 'modificado_por'])

    recalcular_lote(lote)
    return fardo


@transaction.atomic
def armar_lote(lote, usuario=None):
    """Numera el lote y lo da por armado.

    Bloquea la fila y relee el estado: sin eso, dos usuarios apretando Armar a la vez consumirían
    dos números de la serie para el mismo lote. Es idempotente.
    """
    lote = LoteAcopio.objects.select_for_update().get(pk=lote.pk)

    if lote.estado == LoteAcopio.ANULADO:
        raise ValidationError("El lote está anulado: no se puede armar.")
    if lote.estado != LoteAcopio.BORRADOR:
        return lote                                      # ya armado: no se renumera

    if not lote.fardos.exists():
        raise ValidationError("No se puede armar un lote sin fardos.")

    recalcular_lote(lote)
    lote.numero = siguiente_numero(lote.empresa, lote.punto, ContadorDocumento.LOTE_TABACO)
    lote.estado = LoteAcopio.ARMADO
    lote.modificado_por = usuario
    lote.save(update_fields=['numero', 'estado', 'modificado_por'])
    return lote


@transaction.atomic
def anular_lote(lote, motivo, usuario=None):
    """Anula el lote y libera sus fardos.

    A diferencia del romaneo, acá SÍ se sueltan los fardos: el lote es una agrupación comercial,
    no un hecho físico. Deshacerla devuelve los fardos a disponibles; no borra nada.
    """
    lote = LoteAcopio.objects.select_for_update().get(pk=lote.pk)

    if lote.estado == LoteAcopio.ANULADO:
        return lote
    if lote.venta_id:
        raise ValidationError(
            "El lote está vendido. Quitá primero la venta asociada.")
    if lote.acondicionamientos.filter(estado=Acondicionamiento.CERRADO).exists():
        raise ValidationError(
            "El lote tiene acondicionamientos cerrados que movieron stock. "
            "Anulalos primero.")
    if not (motivo or '').strip():
        raise ValidationError("La anulación exige un motivo.")

    lote.fardos.update(lote=None, estado=FardoTabaco.CLASIFICADO)

    lote.estado = LoteAcopio.ANULADO
    lote.motivo_anulacion = motivo.strip()
    lote.anulado_por = usuario
    lote.anulado_el = timezone.now()
    lote.modificado_por = usuario
    lote.save(update_fields=['estado', 'motivo_anulacion', 'anulado_por', 'anulado_el',
                             'modificado_por'])
    recalcular_lote(lote)
    return lote


# ---------------------------------------------------------------------------
# Venta
# ---------------------------------------------------------------------------

@transaction.atomic
def asignar_venta(lote, venta, usuario=None):
    """Vincula la venta que despachó el lote.

    NO CREA LA VENTA NI SU ASIENTO: la venta se emite por el circuito de siempre
    (`facturacion`), con el `Producto` de la variedad. Acá sólo se dice qué fardos salieron con
    ella, que es lo que permite cerrar la trazabilidad y calcular el margen.
    """
    lote = LoteAcopio.objects.select_for_update().get(pk=lote.pk)

    if lote.estado == LoteAcopio.ANULADO:
        raise ValidationError("El lote está anulado.")
    if lote.estado == LoteAcopio.BORRADOR:
        raise ValidationError("Armá el lote antes de venderlo.")
    if lote.venta_id and lote.venta_id != venta.pk:
        raise ValidationError(f"El lote ya está asociado a la venta {lote.venta}.")
    if venta.empresa_id != lote.empresa_id:
        raise ValidationError("La venta pertenece a otra empresa.")

    lote.venta = venta
    lote.estado = LoteAcopio.VENDIDO
    lote.modificado_por = usuario
    lote.save(update_fields=['venta', 'estado', 'modificado_por'])

    lote.fardos.update(estado=FardoTabaco.VENDIDO)
    recalcular_lote(lote)
    return lote


@transaction.atomic
def quitar_venta(lote, usuario=None):
    """Desvincula la venta. No la anula: anular una factura es asunto de `facturacion`."""
    lote = LoteAcopio.objects.select_for_update().get(pk=lote.pk)
    if not lote.venta_id:
        return lote

    hubo_acondicionamiento = lote.acondicionamientos.filter(
        estado=Acondicionamiento.CERRADO).exists()

    lote.venta = None
    lote.estado = LoteAcopio.ACONDICIONADO if hubo_acondicionamiento else LoteAcopio.ARMADO
    lote.modificado_por = usuario
    lote.save(update_fields=['venta', 'estado', 'modificado_por'])

    lote.fardos.update(estado=FardoTabaco.ACONDICIONADO if hubo_acondicionamiento
                       else FardoTabaco.EN_LOTE)
    recalcular_lote(lote)
    return lote


def importe_de_venta(lote):
    """Neto de la venta atribuible al tabaco de ESTE lote.

    Suma sólo las líneas cuyo producto es el de la variedad. Si en la misma factura se cobró un
    flete o un servicio, ese importe NO es ingreso del tabaco y contarlo inflaría el margen.
    """
    if not lote.venta_id or not lote.variedad.producto_id:
        return CERO

    from facturacion.models import VentaItem

    total = (VentaItem.objects
             .filter(venta_id=lote.venta_id, producto_id=lote.variedad.producto_id)
             .aggregate(s=Sum('total'))['s'])
    return total or CERO


# ---------------------------------------------------------------------------
# Derivados
# ---------------------------------------------------------------------------

def recalcular_lote(lote):
    """Reconstruye TODOS los derivados del lote desde sus fardos y acondicionamientos."""
    fardos = lote.fardos.aggregate(
        kilos=Sum('kilos'), importe=Sum('importe'), adicional=Sum('adicional'), n=Count('id'))

    lote.total_fardos = fardos['n'] or 0
    lote.total_kilos = fardos['kilos'] or CERO

    # EL ADICIONAL QUEDA AFUERA DEL COSTO, y no es un olvido.
    # `LiquidacionDetalle.importe` es `Σ fardo.importe` y `liq.neto` se arma de ahí: hoy el
    # circuito NO le paga el adicional al productor. Sumarlo acá haría que el costo del lote
    # dijera una cosa y la liquidación otra, y el margen saldría subestimado contra plata que
    # nunca salió. Sigue guardado en `fardo.adicional` y se informa aparte.
    # Cuando se cierre la decisión DA-05 —qué es el adicional y si integra la base— se cambian
    # LOS DOS lugares juntos: `services/liquidacion.py::preparar_liquidacion` y esta línea.
    lote.costo_compra = fardos['importe'] or CERO

    cerrados = lote.acondicionamientos.filter(estado=Acondicionamiento.CERRADO).aggregate(
        baja=Sum('kilos_baja'), costo=Sum('costo_total'), coprod=Sum('valor_coproductos'))

    lote.kilos_actuales = lote.total_kilos - (cerrados['baja'] or CERO)
    lote.costo_acondicionamiento = cerrados['costo'] or CERO
    lote.valor_coproductos = cerrados['coprod'] or CERO
    lote.importe_venta = importe_de_venta(lote)

    lote.save(update_fields=['total_fardos', 'total_kilos', 'costo_compra', 'kilos_actuales',
                             'costo_acondicionamiento', 'valor_coproductos', 'importe_venta'])
    return lote


def fardos_disponibles(empresa_id, *, variedad_id=None, sucursal_id=None, texto=''):
    """Fardos comprados que todavía no están en ningún lote. Alimenta el Typeahead del armado."""
    qs = (FardoTabaco.objects
          .filter(romaneo__empresa_id=empresa_id, lote__isnull=True,
                  romaneo__estado__in=ESTADOS_ROMANEO_VALIDOS)
          .select_related('romaneo', 'romaneo__productor', 'clase'))

    if variedad_id:
        qs = qs.filter(romaneo__variedad_id=variedad_id)
    if sucursal_id:
        qs = qs.filter(romaneo__sucursal_id=sucursal_id)

    texto = (texto or '').strip()
    if texto:
        from django.db.models import Q
        filtro = Q(etiqueta__icontains=texto) | Q(clase__codigo__icontains=texto)
        if texto.isdigit():
            filtro |= Q(numero_fardo=int(texto)) | Q(romaneo__numero=int(texto))
        qs = qs.filter(filtro)

    return qs.order_by('romaneo__numero', 'numero_fardo')


# ---------------------------------------------------------------------------
# Guardas
# ---------------------------------------------------------------------------

def _exigir_editable(lote):
    """Relee el lote con bloqueo antes de decidir si se puede tocar.

    Leer `lote.estado` del objeto en memoria no alcanza: puede venir cacheado de hace varios
    segundos y otro usuario haberlo vendido en el medio. Es el mismo problema que se corrigió en
    el romaneo con `_exigir_borrador()`.
    """
    lote = LoteAcopio.objects.select_for_update().get(pk=lote.pk)
    if not lote.editable:
        raise ValidationError(
            f"El lote está en «{lote.get_estado_display()}» y no admite cambios de fardos.")
    return lote


def _exigir_sin_acondicionamiento_cerrado(lote, accion):
    if lote.acondicionamientos.filter(estado=Acondicionamiento.CERRADO).exists():
        raise ValidationError(
            f"No se puede {accion}: el lote ya tiene acondicionamientos cerrados y los costos "
            "se prorratean por kilos. Anulá el acondicionamiento primero.")
