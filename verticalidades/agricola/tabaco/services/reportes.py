"""Reportes oficiales del acopio (Plan 087 — Etapa 6).

ESTA ETAPA NO CREA UNA SOLA TABLA
Todo sale de lo que ya registraron las Etapas 0 a 5. Es la prueba de que aquel modelo estaba bien
planteado: si para emitir la planilla FET hubiera que agregar campos, sería señal de que algo no
se estaba capturando cuando correspondía. No hace falta ninguno.

LO QUE SE DECLARA ES LA LENTE FISCAL
La planilla FET y el libro de retenciones son declaraciones: lo que se declara es
`condic in (1, 3)`. El filtro existe igual —regla del proyecto para todo reporte con importes—
pero arranca en Real.
"""
from decimal import Decimal

from django.db.models import Count, Sum

from ..models import (Acondicionamiento, FardoTabaco, LiquidacionPago,
                      LiquidacionTabaco, RetencionPago, RomaneoTabaco)

CERO = Decimal('0.00')
DOS = Decimal('0.01')

# Columnas de retención de la planilla, en el orden del Excel heredado.
#
# LA COLUMNA ES UN DATO DEL MAESTRO, NO UNA DEDUCCIÓN DE ESTE MÓDULO.
# La primera versión mapeaba por código exacto —`IVA`, `GANANCIAS`, `AGUA`— y los conceptos reales
# estaban cargados como `RET-IVA`, `RET-GCIAS` y `USO AGUA`: tres de las cinco retenciones caían
# en «otras» y NADA FALLABA A LA VISTA, porque la fila seguía sumando bien. La planilla mentía en
# silencio, que es la peor forma de fallar en una declaración.
#
# Ahora cada concepto declara su columna en `TipoRetencionTabaco.columna_fet`, se ve en el ABM y
# se corrige sin tocar código. `_deducir_columna()` queda sólo como red: cubre las filas que
# entren por una importación o una carga directa sin pasar por el ABM.
COLUMNAS_RETENCION = [
    ('ret_iva', "Ret. IVA"),
    ('ret_ganancias', "Ret. Ganancias"),
    ('ret_eeaoc', "EEAOC"),
    ('ret_salud', "Salud Pública"),
    ('ret_agua', "Uso de Agua"),
]

CLAVES_RETENCION = [c for c, _r in COLUMNAS_RETENCION]

# Red de deducción: bases estructurales y palabras clave. Mismo criterio que la migración
# `0007_sembrar_columna_fet`, que es la que dejó el dato cargado de una vez.
_DEDUCCION = [
    ('ret_iva', {'IVA'}, ()),
    ('ret_ganancias', {'ACUM_MENSUAL'}, ()),
    ('ret_eeaoc', set(), ('EEAOC',)),
    ('ret_salud', set(), ('SALUD',)),
    ('ret_agua', set(), ('AGUA',)),
]


def _deducir_columna(codigo, detalle, tipo_base):
    """Deduce la columna cuando el maestro no la declara. Es la red, no el camino principal."""
    for columna, bases, _claves in _DEDUCCION:
        if tipo_base and tipo_base in bases:
            return columna

    texto = f"{codigo or ''} {detalle or ''}".upper()
    for columna, bases, claves in _DEDUCCION:
        if bases:
            continue
        if any(palabra in texto for palabra in claves):
            return columna

    return 'otras'


def columna_de(tipo_retencion, codigo='', detalle='', tipo_base=''):
    """A qué columna de la planilla va una retención.

    Manda lo que declara el maestro. Si está vacío se deduce, y si no se puede deducir va a
    «otras», que es una columna real de la planilla y no un error.
    """
    declarada = getattr(tipo_retencion, 'columna_fet', '') if tipo_retencion else ''
    if declarada:
        return declarada

    base = tipo_base or (getattr(tipo_retencion, 'tipo_base', '') if tipo_retencion else '')
    return _deducir_columna(codigo, detalle, base)


# ---------------------------------------------------------------------------
# 2.1 Planilla FET
# ---------------------------------------------------------------------------

def planilla_fet(empresa_id, *, desde=None, hasta=None, campania_id=None, variedad_id=None,
                 productor_id=None, condic=1):
    """Una fila por ROMANEO, con los datos del comprobante que lo liquidó.

    LA GRANULARIDAD ES EL ROMANEO porque así lo encabeza el Excel heredado (`id_romaneo`). En el
    VFP eso era trivial —un romaneo era una liquidación, el sistema hacía todo en un solo acto—;
    acá una liquidación puede agrupar varios romaneos y las retenciones se calculan sobre el
    comprobante entero. Por eso se prorratean por la participación del romaneo en el neto: el dato
    existe a nivel comprobante, y así la suma de las filas reconstruye el total exacto.
    """
    liquidaciones = (LiquidacionTabaco.objects
                     .filter(empresa_id=empresa_id, estado=LiquidacionTabaco.CONFIRMADA)
                     .select_related('productor', 'productor__productor_tabaco')
                     .prefetch_related('retenciones_aplicadas__tipo_retencion'))

    if desde:
        liquidaciones = liquidaciones.filter(fecha__gte=desde)
    if hasta:
        liquidaciones = liquidaciones.filter(fecha__lte=hasta)
    if productor_id:
        liquidaciones = liquidaciones.filter(productor_id=productor_id)
    if condic:
        liquidaciones = liquidaciones.filter(condic=condic)

    filas = []
    for liq in liquidaciones.order_by('fecha', 'punto', 'numero'):
        romaneos = (liq.romaneos
                    .select_related('variedad', 'campania')
                    .order_by('numero'))
        if campania_id:
            romaneos = romaneos.filter(campania_id=campania_id)
        if variedad_id:
            romaneos = romaneos.filter(variedad_id=variedad_id)

        retenciones = _retenciones_de(liq)
        base_neto = liq.neto or CERO

        for romaneo in romaneos:
            # El aporte del romaneo al neto del comprobante. `liq.neto` es `Σ fardo.importe`
            # —el adicional NO entra, ver la columna `adicional` más abajo—, así que la base del
            # prorrateo es `total_importe` a secas. Con esto la suma de las filas reconstruye
            # exactamente el IVA y las retenciones de la liquidación.
            proporcion = ((romaneo.total_importe or CERO) / base_neto) if base_neto else CERO

            fila = {
                'romaneo': romaneo,
                'liquidacion': liq,
                'id_romaneo': romaneo.numero,
                'asiento': liq.asiento_id or '',
                'letra': liq.letra,
                'punto': liq.punto,
                'numero': liq.numero,
                'fecha': liq.fecha,
                'codigo_fet': _codigo_fet(liq.productor),
                'productor': liq.productor.razon_social,
                'cuit': liq.productor.cuit or '',
                'variedad': romaneo.variedad.detalle,
                'campania': romaneo.campania.codigo,
                'fardos': romaneo.total_fardos,
                'kilos': romaneo.total_kilos or CERO,
                'importe': romaneo.total_importe or CERO,
                # INFORMATIVA. Se muestra porque la planilla heredada la traía, pero HOY NO SE
                # PAGA: la liquidación no la incluye en el neto (decisión DA-05 todavía abierta).
                # Por eso tampoco entra en `a_pagar`: si entrara, la planilla declararía un
                # importe que el comprobante no dice.
                'adicional': romaneo.adicional or CERO,
                'iva': _prorratear(liq.iva, proporcion),
                'ponderante': romaneo.ponderante_aplicado or CERO,
                'condic': liq.condic,
            }

            total_retenido = CERO
            for clave in CLAVES_RETENCION:
                importe = _prorratear(retenciones.get(clave, CERO), proporcion)
                fila[clave] = importe
                total_retenido += importe
            fila['otras_retenciones'] = _prorratear(retenciones.get('otras', CERO), proporcion)
            total_retenido += fila['otras_retenciones']

            fila['retenciones'] = total_retenido
            fila['a_pagar'] = fila['importe'] + fila['iva'] - total_retenido
            filas.append(fila)

    return filas


def _retenciones_de(liq):
    """Retenciones de la liquidación, mapeadas a las columnas de la planilla.

    Junta los DOS orígenes: las que se practicaron al liquidar (EEAOC, IVA, Salud, Agua) y las que
    se practicaron al pagar (Ganancias, por DA-01). Un concepto que no esté en el mapa de columnas
    cae en «otras», así que la fila sigue sumando aunque el cliente agregue conceptos nuevos.
    """
    acumulado = {clave: CERO for clave in CLAVES_RETENCION}
    acumulado['otras'] = CERO

    for aplicada in liq.retenciones_aplicadas.all():
        # `aplicada` guarda una copia congelada de la regla; la columna se lee del maestro, que
        # es donde el usuario la puede corregir sin reescribir comprobantes ya emitidos.
        clave = columna_de(aplicada.tipo_retencion, aplicada.codigo, aplicada.detalle,
                           aplicada.tipo_base)
        acumulado[clave] += aplicada.importe

    for clave, importe in _retenciones_del_pago(liq).items():
        acumulado[clave] += importe

    return acumulado


def _retenciones_del_pago(liq):
    """Lo retenido al PAGAR esta liquidación, prorrateado por lo imputado a ella.

    Ganancias se practica al pagar y su base es el acumulado mensual del productor, no esta
    liquidación: el certificado cuelga de la Orden de Pago, que puede cancelar varias. Se reparte
    por lo que la OP imputó a cada una.

    Una liquidación sin pagar da CERO, y es lo correcto: todavía no se le retuvo nada. Estimar acá
    sería declarar ante el FET una retención que no se practicó.
    """
    acumulado = {}

    imputaciones = (LiquidacionPago.objects
                    .filter(liquidacion=liq, anulado=False)
                    .select_related('orden_pago'))

    for imputacion in imputaciones:
        op = imputacion.orden_pago
        total_op = (LiquidacionPago.objects
                    .filter(orden_pago=op, anulado=False)
                    .aggregate(s=Sum('importe'))['s'] or CERO)
        parte = (imputacion.importe / total_op) if total_op else CERO

        certificados = (RetencionPago.objects
                        .filter(orden_pago=op, anulado=False)
                        .select_related('tipo_retencion'))
        for cert in certificados:
            clave = columna_de(cert.tipo_retencion, cert.codigo, cert.detalle)
            acumulado[clave] = acumulado.get(clave, CERO) + _prorratear(cert.importe, parte)

    return acumulado


def totales_fet(filas):
    """Suma las columnas de importe de la planilla."""
    claves = (['fardos', 'kilos', 'importe', 'adicional', 'iva', 'retenciones', 'a_pagar',
               'otras_retenciones'] + list(CLAVES_RETENCION))
    acumulado = {c: CERO for c in claves}
    for fila in filas:
        for clave in claves:
            acumulado[clave] += fila[clave]
    acumulado['fardos'] = int(acumulado['fardos'])
    return acumulado


# ---------------------------------------------------------------------------
# 2.2 Resumen de acopio por variedad y clase
# ---------------------------------------------------------------------------

def resumen_de_acopio(empresa_id, *, desde=None, hasta=None, campania_id=None, variedad_id=None,
                      sucursal_id=None, condic=None):
    """Fardos, kilos, importe y precio promedio por variedad y clase, con subtotal por variedad.

    El precio promedio es PONDERADO POR KILOS (`importe / kilos`), no el promedio de los precios
    de cada fardo: un fardo de 5 kg y otro de 500 no pesan lo mismo en el precio de la campaña.
    """
    qs = (FardoTabaco.objects
          .filter(romaneo__empresa_id=empresa_id)
          .exclude(romaneo__estado__in=(RomaneoTabaco.BORRADOR, RomaneoTabaco.ANULADO)))

    if desde:
        qs = qs.filter(romaneo__fecha__gte=desde)
    if hasta:
        qs = qs.filter(romaneo__fecha__lte=hasta)
    if campania_id:
        qs = qs.filter(romaneo__campania_id=campania_id)
    if variedad_id:
        qs = qs.filter(romaneo__variedad_id=variedad_id)
    if sucursal_id:
        qs = qs.filter(romaneo__sucursal_id=sucursal_id)
    if condic:
        qs = qs.filter(romaneo__condic=condic)

    agrupado = (qs.values('romaneo__variedad__id', 'romaneo__variedad__detalle',
                          'clase__id', 'clase__codigo', 'clase__detalle', 'clase__grupo')
                .annotate(fardos=Count('id'), kilos=Sum('kilos'), importe=Sum('importe'))
                .order_by('romaneo__variedad__detalle', 'clase__codigo'))

    variedades, actual = [], None
    for fila in agrupado:
        if actual is None or actual['variedad_id'] != fila['romaneo__variedad__id']:
            actual = {
                'variedad_id': fila['romaneo__variedad__id'],
                'variedad': fila['romaneo__variedad__detalle'],
                'clases': [], 'fardos': 0, 'kilos': CERO, 'importe': CERO,
            }
            variedades.append(actual)

        kilos = fila['kilos'] or CERO
        importe = fila['importe'] or CERO
        actual['clases'].append({
            'codigo': fila['clase__codigo'],
            'clase': fila['clase__detalle'],
            'grupo': fila['clase__grupo'],
            'fardos': fila['fardos'],
            'kilos': kilos,
            'importe': importe,
            'precio_promedio': _dividir(importe, kilos),
        })
        actual['fardos'] += fila['fardos']
        actual['kilos'] += kilos
        actual['importe'] += importe

    for variedad in variedades:
        variedad['precio_promedio'] = _dividir(variedad['importe'], variedad['kilos'])

    return variedades


# ---------------------------------------------------------------------------
# 2.3 DDJJ de existencias — a una FECHA, no de hoy
# ---------------------------------------------------------------------------

def existencias_a_fecha(empresa_id, fecha, *, sucursal_id=None, variedad_id=None, condic=None):
    """Existencia declarable por variedad y galpón a la fecha de corte.

        existencia = Σ fardos de romaneos vigentes con fecha ≤ F
                   − Σ kilos_baja de acondicionamientos cerrados con fecha ≤ F
                   − Σ kilos vendidos con fecha ≤ F

    SE RECONSTRUYE Y NO SE LEE DE `StockSucursal` porque `StockSucursal` sólo sabe el presente. Una
    DDJJ que se presenta en octubre por las existencias al 30 de septiembre necesita el pasado, y
    el pasado está en los comprobantes. Es el mismo criterio con el que el ERP deriva el stock,
    con un corte de fecha encima.
    """
    from empresas.models import Sucursal
    from facturacion.models import VentaItem

    from ..models import VariedadTabaco

    variedades = VariedadTabaco.objects.filter(empresa_id=empresa_id).select_related('producto')
    if variedad_id:
        variedades = variedades.filter(pk=variedad_id)

    sucursales = Sucursal.objects.filter(empresa_id=empresa_id)
    if sucursal_id:
        sucursales = sucursales.filter(pk=sucursal_id)

    filas = []
    for variedad in variedades.order_by('codigo'):
        for sucursal in sucursales.order_by('nombre'):
            recibidos_qs = (FardoTabaco.objects
                            .filter(romaneo__variedad=variedad, romaneo__sucursal=sucursal,
                                    romaneo__fecha__lte=fecha)
                            .exclude(romaneo__estado__in=(RomaneoTabaco.BORRADOR,
                                                          RomaneoTabaco.ANULADO)))
            if condic:
                recibidos_qs = recibidos_qs.filter(romaneo__condic=condic)

            recibidos = recibidos_qs.aggregate(k=Sum('kilos'), f=Count('id'))
            kilos_recibidos = recibidos['k'] or CERO

            acondicionados = (Acondicionamiento.objects
                              .filter(lote__variedad=variedad, lote__sucursal=sucursal,
                                      estado=Acondicionamiento.CERRADO, fecha__lte=fecha)
                              .aggregate(s=Sum('kilos_baja'))['s'] or CERO)

            vendidos = CERO
            if variedad.producto_id:
                vendidos_qs = (VentaItem.objects
                               .filter(producto_id=variedad.producto_id,
                                       venta__sucursal=sucursal, venta__fecha__lte=fecha)
                               .exclude(venta__estado=1)
                               .exclude(venta__id_fac_rem__isnull=False))
                if condic:
                    vendidos_qs = vendidos_qs.filter(venta__condic=condic)
                vendidos = vendidos_qs.aggregate(s=Sum('cantidad'))['s'] or CERO

            existencia = kilos_recibidos - acondicionados - vendidos
            if not (kilos_recibidos or acondicionados or vendidos):
                continue                      # nada que declarar en ese galpón

            filas.append({
                'variedad': variedad,
                'sucursal': sucursal,
                'fardos': recibidos['f'] or 0,
                'recibidos': kilos_recibidos,
                'acondicionados': acondicionados,
                'vendidos': vendidos,
                'existencia': existencia,
                'sin_producto': variedad.producto_id is None,
            })

    return filas


def totales_existencias(filas):
    acumulado = {c: CERO for c in ('recibidos', 'acondicionados', 'vendidos', 'existencia')}
    acumulado['fardos'] = 0
    for fila in filas:
        acumulado['fardos'] += fila['fardos']
        for clave in ('recibidos', 'acondicionados', 'vendidos', 'existencia'):
            acumulado[clave] += fila[clave]
    return acumulado


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _codigo_fet(cliente_proveedor):
    """Código FET del productor. Vive en la extensión sectorial, no en el maestro de terceros."""
    extension = getattr(cliente_proveedor, 'productor_tabaco', None)
    return extension.codigo_fet if extension else ''


def _prorratear(importe, proporcion):
    return ((importe or CERO) * proporcion).quantize(DOS)


def _dividir(importe, cantidad):
    if not cantidad:
        return CERO
    return (importe / cantidad).quantize(DOS)
