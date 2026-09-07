"""Servicios del romaneo: apertura, carga de fardos, confirmación y reclasificación (Plan 082).

QUÉ NO HACE ESTE MÓDULO, Y ES DELIBERADO
No toca contabilidad, ni stock, ni cuenta corriente. El romaneo es el hecho físico; la deuda con
el productor nace al liquidar (Etapa 2) y los kilos entran al stock cuando se registre el término
del Plan 080 (Etapa 4). Mezclarlo acá haría imposible corregir una clasificación sin mover plata.

DÓNDE ESTÁ LA VERDAD DE CADA NÚMERO
Los totales del romaneo (`total_kilos`, `total_fardos`, `total_importe`, `precio_promedio`) son
CACHÉ: se materializan porque se leen en todo listado, pero se reconstruyen enteros desde los
fardos con `recalcular_totales()`, nunca por delta. Es el mismo criterio con el que el ERP maneja
el stock y los saldos de cuenta corriente: un contador incremental no se puede reconstruir y
termina derivando.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Max, Sum
from django.utils import timezone

from core.models import ContadorDocumento
from core.services.numeracion import siguiente_numero

from ..models import FardoTabaco, ReclasificacionFardo, RomaneoTabaco
from .precios import importe_de_linea, lista_vigente

CERO = Decimal('0.00')
DOS = Decimal('0.01')


# ---------------------------------------------------------------------------
# Apertura
# ---------------------------------------------------------------------------

@transaction.atomic
def abrir_romaneo(*, empresa, sucursal, productor, variedad, campania, fecha,
                  usuario=None, transporte='', remito='', observaciones='',
                  condic=1, punto=None):
    """Crea el romaneo en BORRADOR con la lista de precio vigente congelada.

    Falla si no hay lista aprobada y vigente: sin ponderante no hay precio posible, y dejar
    abrir el romaneo igual sólo trasladaría el problema a la carga del primer fardo, con cien
    kilos ya pesados y la balanza ocupada.
    """
    lista = lista_vigente(empresa.pk, variedad, campania, fecha)
    if lista is None:
        raise ValidationError(
            f"No hay lista de precio aprobada y vigente para {variedad} en la campaña "
            f"{campania} al {fecha:%d/%m/%Y}. Cargala y aprobala antes de abrir el romaneo."
        )

    coeficiente_productor = Decimal('1')
    extension = getattr(productor, 'productor_tabaco', None)
    if extension is not None:
        if not extension.habilitado:
            raise ValidationError(
                f"El productor {productor.razon_social} no está habilitado para operar.")
        coeficiente_productor = extension.coeficiente

    # El punto sale de la SUCURSAL, no de un default fijo: su `help_text` dice literalmente que
    # prenumera este tipo de documentos, y así cada sucursal lleva su propia serie correlativa en
    # lugar de competir todas por la misma.
    if punto is None:
        punto = getattr(sucursal, 'punto', None) or 1

    return RomaneoTabaco.objects.create(
        empresa=empresa, sucursal=sucursal, punto=punto, fecha=fecha,
        productor=productor, variedad=variedad, campania=campania,
        lista_precio=lista, ponderante_aplicado=lista.precio_ponderante,
        coeficiente_productor=coeficiente_productor,
        transporte=transporte, remito=remito, observaciones=observaciones, condic=condic,
        estado=RomaneoTabaco.BORRADOR,
        creado_por=usuario, modificado_por=usuario,
    )


# ---------------------------------------------------------------------------
# Carga de fardos
# ---------------------------------------------------------------------------

def cotizar_clase(romaneo, clase, kilos):
    """Precio e importe que le corresponderían a un fardo, sin grabarlo.

    Lo usa la pantalla para mostrar el número mientras el operador tipea, antes de confirmar el
    fardo. Usa el ponderante CONGELADO del romaneo, no el vigente hoy: si la lista cambió a mitad
    de una carga, los fardos de ese romaneo tienen que seguir saliendo al mismo precio.
    """
    precio = (Decimal(romaneo.ponderante_aplicado) * Decimal(clase.coeficiente)
              ).quantize(DOS, rounding=ROUND_HALF_UP)
    return precio, importe_de_linea(precio, kilos)


@transaction.atomic
def agregar_fardo(romaneo, *, clase, kilos, etiqueta='', adicional=CERO, usuario=None,
                  numero_fardo=None):
    """Agrega un fardo al romaneo en borrador, con el precio congelado."""
    romaneo = _exigir_borrador(romaneo)
    _validar_clase(romaneo, clase)

    kilos = Decimal(kilos)
    if kilos <= 0:
        raise ValidationError("Los kilos del fardo deben ser mayores que cero.")

    if numero_fardo is None:
        # Se numera desde el máximo existente y no desde el `count`: si se borró un fardo del
        # medio, contar daría un número ya usado y chocaría con el índice único.
        ultimo = romaneo.fardos.aggregate(m=Max('numero_fardo'))['m'] or 0
        numero_fardo = ultimo + 1

    adicional = Decimal(adicional or 0)
    precio, importe = cotizar_clase(romaneo, clase, kilos)

    fardo = FardoTabaco.objects.create(
        romaneo=romaneo, numero_fardo=numero_fardo, etiqueta=etiqueta.strip().upper(),
        clase=clase, coeficiente_aplicado=clase.coeficiente, precio_aplicado=precio,
        kilos=kilos, importe=importe, adicional=adicional,
        precio_final=(precio + (adicional / kilos if kilos else CERO)).quantize(DOS),
        estado=FardoTabaco.CLASIFICADO,
        clasificado_por=usuario, clasificado_el=timezone.now(),
        creado_por=usuario, modificado_por=usuario,
    )
    recalcular_totales(romaneo)
    return fardo


@transaction.atomic
def editar_fardo(fardo, *, clase=None, kilos=None, etiqueta=None, adicional=None, usuario=None):
    """Corrige un fardo mientras el romaneo sigue en borrador.

    Una vez confirmado el romaneo, cambiar la clase ya no es "editar": es RECLASIFICAR, y va por
    `reclasificar_fardo()`, que deja constancia de lo que había antes.
    """
    romaneo = _exigir_borrador(fardo.romaneo)

    if clase is not None:
        _validar_clase(romaneo, clase)
        fardo.clase = clase
        fardo.coeficiente_aplicado = clase.coeficiente
    if kilos is not None:
        kilos = Decimal(kilos)
        if kilos <= 0:
            raise ValidationError("Los kilos del fardo deben ser mayores que cero.")
        fardo.kilos = kilos
    if etiqueta is not None:
        fardo.etiqueta = etiqueta.strip().upper()
    if adicional is not None:
        fardo.adicional = Decimal(adicional or 0)

    fardo.precio_aplicado, fardo.importe = cotizar_clase(romaneo, fardo.clase, fardo.kilos)
    fardo.precio_final = (fardo.precio_aplicado
                          + (fardo.adicional / fardo.kilos if fardo.kilos else CERO)).quantize(DOS)
    fardo.modificado_por = usuario
    fardo.save()

    recalcular_totales(romaneo)
    return fardo


@transaction.atomic
def quitar_fardo(fardo):
    """Elimina un fardo del borrador. Después de confirmar ya no se puede: se anula el romaneo."""
    romaneo = _exigir_borrador(fardo.romaneo)
    fardo.delete()
    recalcular_totales(romaneo)
    return romaneo


# ---------------------------------------------------------------------------
# Totales y estadística
# ---------------------------------------------------------------------------

@transaction.atomic
def recalcular_totales(romaneo):
    """Reconstruye los totales ENTEROS desde los fardos. Idempotente y autorreparable."""
    agregado = romaneo.fardos.aggregate(
        kilos=Sum('kilos'), importe=Sum('importe'),
        adicional=Sum('adicional'), fardos=Count('id'))

    romaneo.total_kilos = agregado['kilos'] or CERO
    romaneo.total_importe = agregado['importe'] or CERO
    romaneo.adicional = agregado['adicional'] or CERO
    romaneo.total_fardos = agregado['fardos'] or 0

    if romaneo.total_kilos:
        romaneo.precio_promedio = (romaneo.total_importe / romaneo.total_kilos
                                   ).quantize(DOS, rounding=ROUND_HALF_UP)
        romaneo.porcentaje_ponderante = (
            romaneo.precio_promedio * Decimal('100') / romaneo.ponderante_aplicado
        ).quantize(DOS, rounding=ROUND_HALF_UP) if romaneo.ponderante_aplicado else CERO
    else:
        romaneo.precio_promedio = CERO
        romaneo.porcentaje_ponderante = CERO

    romaneo.save(update_fields=['total_kilos', 'total_importe', 'adicional', 'total_fardos',
                                'precio_promedio', 'porcentaje_ponderante'])
    return romaneo


def estadistica_por_grupo(romaneo):
    """Kilos, fardos y participación por grupo de clase (B, C, X, T, N, H).

    Los grupos se DERIVAN de las clases cargadas. El sistema heredado los tenía cableados en una
    lista fija de cinco letras y por eso perdía el grupo H de Virginia: sus kilos no aparecían en
    ningún subtotal aunque sí en el total general.
    """
    filas = (romaneo.fardos
             .values('clase__grupo')
             .annotate(kilos=Sum('kilos'), importe=Sum('importe'), fardos=Count('id'))
             .order_by('clase__grupo'))

    total_kilos = romaneo.total_kilos or CERO
    resultado = []
    for fila in filas:
        kilos = fila['kilos'] or CERO
        resultado.append({
            'grupo': fila['clase__grupo'] or '?',
            'kilos': kilos,
            'fardos': fila['fardos'],
            'importe': fila['importe'] or CERO,
            'porcentaje': ((kilos * Decimal('100') / total_kilos).quantize(DOS)
                           if total_kilos else CERO),
        })
    return resultado


# ---------------------------------------------------------------------------
# Confirmación y anulación
# ---------------------------------------------------------------------------

@transaction.atomic
def confirmar_romaneo(romaneo, usuario=None):
    """Numera el romaneo y lo cierra a edición.

    Bloquea la fila con `select_for_update()` y vuelve a leer el estado: sin eso, dos usuarios
    apretando Confirmar a la vez consumirían dos números de la serie para el mismo romaneo.
    Es idempotente: si ya estaba confirmado, devuelve el mismo número.
    """
    romaneo = RomaneoTabaco.objects.select_for_update().get(pk=romaneo.pk)

    if romaneo.estado == RomaneoTabaco.ANULADO:
        raise ValidationError("El romaneo está anulado: no se puede confirmar.")
    if romaneo.estado != RomaneoTabaco.BORRADOR:
        return romaneo                       # ya confirmado o liquidado: no se renumera

    if not romaneo.fardos.exists():
        raise ValidationError("No se puede confirmar un romaneo sin fardos.")

    recalcular_totales(romaneo)
    romaneo.numero = siguiente_numero(romaneo.empresa, romaneo.punto,
                                      ContadorDocumento.ROMANEO_TABACO)
    romaneo.estado = RomaneoTabaco.CONFIRMADO
    romaneo.modificado_por = usuario
    romaneo.save(update_fields=['numero', 'estado', 'modificado_por'])
    return romaneo


@transaction.atomic
def anular_romaneo(romaneo, motivo, usuario=None):
    """Anula el romaneo SIN borrar los fardos.

    La recepción ocurrió: la mercadería entró y se pesó. Anular es decir que el documento no vale,
    no que el hecho no pasó. Borrar los fardos destruiría la evidencia de una entrega real.
    """
    romaneo = RomaneoTabaco.objects.select_for_update().get(pk=romaneo.pk)

    if romaneo.estado == RomaneoTabaco.LIQUIDADO:
        raise ValidationError(
            "El romaneo ya fue liquidado. Anulá primero la liquidación que lo incluye.")
    if romaneo.estado == RomaneoTabaco.ANULADO:
        return romaneo

    if not (motivo or '').strip():
        raise ValidationError("La anulación exige un motivo.")

    romaneo.estado = RomaneoTabaco.ANULADO
    romaneo.motivo_anulacion = motivo.strip()
    romaneo.anulado_por = usuario
    romaneo.anulado_el = timezone.now()
    romaneo.modificado_por = usuario
    romaneo.save(update_fields=['estado', 'motivo_anulacion', 'anulado_por', 'anulado_el',
                                'modificado_por'])
    return romaneo


# ---------------------------------------------------------------------------
# Reclasificación
# ---------------------------------------------------------------------------

@transaction.atomic
def reclasificar_fardo(fardo, *, clase_nueva, motivo, usuario):
    """Cambia la clase de un fardo dejando constancia de la anterior.

    NO sobrescribe la clasificación original: la guarda en `ReclasificacionFardo` con motivo y
    usuario. Un fardo puede reclasificarse varias veces y la cadena completa queda reconstruible.
    """
    # Se relee y se bloquea por el mismo motivo que en `_exigir_borrador`: `fardo.romaneo` es
    # una relación cacheada y podría estar mostrando un estado viejo.
    romaneo = RomaneoTabaco.objects.select_for_update().get(pk=fardo.romaneo_id)

    if romaneo.estado == RomaneoTabaco.ANULADO:
        raise ValidationError("No se reclasifican fardos de un romaneo anulado.")
    if romaneo.estado == RomaneoTabaco.LIQUIDADO:
        raise ValidationError(
            "El romaneo ya fue liquidado: reclasificar cambiaría un importe ya facturado. "
            "Anulá la liquidación primero.")
    if not (motivo or '').strip():
        raise ValidationError("La reclasificación exige un motivo.")

    _validar_clase(romaneo, clase_nueva)
    if clase_nueva.pk == fardo.clase_id:
        raise ValidationError("La clase nueva es la misma que la actual.")

    precio_nuevo, importe_nuevo = cotizar_clase(romaneo, clase_nueva, fardo.kilos)

    ReclasificacionFardo.objects.create(
        fardo=fardo,
        clase_anterior=fardo.clase, coeficiente_anterior=fardo.coeficiente_aplicado,
        precio_anterior=fardo.precio_aplicado, importe_anterior=fardo.importe,
        clase_nueva=clase_nueva, coeficiente_nuevo=clase_nueva.coeficiente,
        precio_nuevo=precio_nuevo, importe_nuevo=importe_nuevo,
        kilos=fardo.kilos, motivo=motivo.strip(), usuario=usuario,
    )

    fardo.clase = clase_nueva
    fardo.coeficiente_aplicado = clase_nueva.coeficiente
    fardo.precio_aplicado = precio_nuevo
    fardo.importe = importe_nuevo
    fardo.precio_final = (precio_nuevo
                          + (fardo.adicional / fardo.kilos if fardo.kilos else CERO)).quantize(DOS)
    fardo.modificado_por = usuario
    fardo.save()

    recalcular_totales(romaneo)
    return fardo


# ---------------------------------------------------------------------------
# Validaciones compartidas
# ---------------------------------------------------------------------------

def _exigir_borrador(romaneo):
    """Relee el estado desde la base y bloquea la fila. Devuelve el romaneo fresco.

    NO alcanza con mirar `romaneo.estado` del objeto que llega: puede venir de una instancia
    cargada hace rato —o de `fardo.romaneo`, que Django cachea— y estar mostrando BORRADOR cuando
    el documento ya se confirmó. Sin esta relectura se podían editar o borrar fardos de un romaneo
    cerrado con sólo tener el objeto viejo en memoria, que es exactamente el agujero por el que se
    corrompen los documentos confirmados.

    El `select_for_update()` además serializa contra una confirmación concurrente: si otro usuario
    está confirmando, esta operación espera y encuentra el estado ya cambiado.
    """
    fresco = RomaneoTabaco.objects.select_for_update().get(pk=romaneo.pk)
    if fresco.estado != RomaneoTabaco.BORRADOR:
        raise ValidationError(
            f"El romaneo está en estado «{fresco.get_estado_display()}» y no admite cambios "
            f"en su detalle.")
    return fresco


def _validar_clase(romaneo, clase):
    """La clase tiene que ser de la variedad del romaneo y de la misma empresa.

    Sin esto se podría clasificar tabaco Burley con una clase de Virginia y el precio saldría de
    un coeficiente que no corresponde, sin que nada avise.
    """
    if clase.variedad_id != romaneo.variedad_id:
        raise ValidationError(
            f"La clase {clase.detalle} pertenece a {clase.variedad}, y el romaneo es de "
            f"{romaneo.variedad}.")
    if clase.empresa_id != romaneo.empresa_id:
        raise ValidationError("La clase pertenece a otra empresa.")
    if not clase.activa:
        raise ValidationError(f"La clase {clase.detalle} está inactiva.")
