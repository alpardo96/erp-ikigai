"""Tableros de gestión del acopio (Plan 087 — Etapa 6).

Tres lecturas del mismo margen que ya calcula la Etapa 5, agrupado por lo que sirve para decidir:

    por CAMPAÑA    cómo cerró cada ciclo
    por PRODUCTOR  a quién conviene comprarle
    por CLASE      qué calidades dejaron plata y cuáles se pagaron de más

La tercera es la que más rinde: el precio de una clase sale de un coeficiente sobre el ponderante,
y recién al vender se sabe si ese coeficiente estaba bien puesto.

TODO SE DERIVA, NADA SE GUARDA. Estos tableros no materializan un solo campo: si el margen de un
lote cambia porque se anuló un acondicionamiento, el tablero lo refleja en la consulta siguiente.
"""
from decimal import Decimal

from ..models import LoteAcopio
from .margen import margen_por_fardo

CERO = Decimal('0.00')
DOS = Decimal('0.01')


def _lotes(empresa_id, *, campania_id=None, variedad_id=None, sucursal_id=None, condic=None,
           solo_vendidos=False):
    qs = (LoteAcopio.objects
          .filter(empresa_id=empresa_id)
          .exclude(estado=LoteAcopio.ANULADO)
          .select_related('campania', 'variedad', 'sucursal'))

    if campania_id:
        qs = qs.filter(campania_id=campania_id)
    if variedad_id:
        qs = qs.filter(variedad_id=variedad_id)
    if sucursal_id:
        qs = qs.filter(sucursal_id=sucursal_id)
    if solo_vendidos:
        qs = qs.filter(venta__isnull=False)
    if condic:
        qs = qs.filter(fardos__romaneo__condic=condic).distinct()
    return qs


def por_campania(empresa_id, **filtros):
    """Cómo cerró cada campaña."""
    acumulado = {}
    for lote in _lotes(empresa_id, **filtros):
        grupo = acumulado.setdefault(lote.campania_id, _grupo(lote.campania.codigo))
        _sumar_lote(grupo, lote)
    return _cerrar(acumulado.values(), clave=lambda g: g['rotulo'])


def por_variedad(empresa_id, **filtros):
    acumulado = {}
    for lote in _lotes(empresa_id, **filtros):
        grupo = acumulado.setdefault(lote.variedad_id, _grupo(lote.variedad.detalle))
        _sumar_lote(grupo, lote)
    return _cerrar(acumulado.values(), clave=lambda g: g['rotulo'])


def por_productor(empresa_id, **filtros):
    """A quién conviene comprarle.

    El costo de compra SÍ es atribuible por productor: es el fardo que él entregó. El costo de
    acondicionamiento y el ingreso se prorratean por kilos, igual que en el margen por fardo, con
    la misma justificación: en la máquina los fardos se mezclan.
    """
    acumulado = {}
    for lote in _lotes(empresa_id, **filtros):
        for fila in margen_por_fardo(lote):
            productor = fila['fardo'].romaneo.productor
            grupo = acumulado.setdefault(productor.pk, _grupo(productor.razon_social))
            grupo['cuit'] = productor.cuit or ''
            grupo['lotes'].add(lote.pk)
            grupo['fardos'] += 1
            grupo['kilos'] += fila['kilos']
            grupo['costo_compra'] += fila['costo_compra']
            grupo['costo_acondicionamiento'] += fila['costo_acondicionamiento']
            grupo['ingreso'] += fila['ingreso']
    return _cerrar(acumulado.values(), clave=lambda g: g['rotulo'])


def por_clase(empresa_id, **filtros):
    """Qué clases dejaron plata. Es la lectura que sirve para comprar mejor el año que viene."""
    acumulado = {}
    for lote in _lotes(empresa_id, **filtros):
        for fila in margen_por_fardo(lote):
            clase = fila['fardo'].clase
            grupo = acumulado.setdefault(clase.pk, _grupo(clase.detalle))
            grupo['grupo_clase'] = clase.grupo
            grupo['coeficiente'] = clase.coeficiente
            grupo['lotes'].add(lote.pk)
            grupo['fardos'] += 1
            grupo['kilos'] += fila['kilos']
            grupo['costo_compra'] += fila['costo_compra']
            grupo['costo_acondicionamiento'] += fila['costo_acondicionamiento']
            grupo['ingreso'] += fila['ingreso']
    return _cerrar(acumulado.values(), clave=lambda g: g['rotulo'])


# ---------------------------------------------------------------------------

def _grupo(rotulo):
    return {
        'rotulo': rotulo, 'cuit': '', 'grupo_clase': '', 'coeficiente': None,
        'lotes': set(), 'fardos': 0, 'kilos': CERO,
        'costo_compra': CERO, 'costo_acondicionamiento': CERO, 'ingreso': CERO,
    }


def _sumar_lote(grupo, lote):
    grupo['lotes'].add(lote.pk)
    grupo['fardos'] += lote.total_fardos
    grupo['kilos'] += lote.total_kilos
    grupo['costo_compra'] += lote.costo_compra
    grupo['costo_acondicionamiento'] += lote.costo_acondicionamiento
    # El valor recuperado en coproductos abarata el lote: se suma al ingreso, igual que en
    # `margen_por_fardo()`, para que las dos lecturas den el mismo margen.
    grupo['ingreso'] += lote.importe_venta + lote.valor_coproductos


def _cerrar(grupos, clave):
    filas = []
    for grupo in grupos:
        grupo['lotes'] = len(grupo['lotes'])
        grupo['costo_total'] = grupo['costo_compra'] + grupo['costo_acondicionamiento']
        grupo['margen'] = grupo['ingreso'] - grupo['costo_total']
        base = grupo['costo_total']
        grupo['margen_porcentaje'] = ((grupo['margen'] / base * Decimal('100')).quantize(DOS)
                                      if base else CERO)
        grupo['costo_por_kilo'] = _dividir(grupo['costo_total'], grupo['kilos'])
        grupo['venta_por_kilo'] = _dividir(grupo['ingreso'], grupo['kilos'])
        filas.append(grupo)
    return sorted(filas, key=clave)


def totales(filas):
    """El porcentaje se recalcula sobre los totales; promediar porcentajes no significa nada."""
    acumulado = {c: CERO for c in ('kilos', 'costo_compra', 'costo_acondicionamiento',
                                   'costo_total', 'ingreso', 'margen')}
    acumulado['fardos'] = 0
    acumulado['lotes'] = 0
    for fila in filas:
        acumulado['fardos'] += fila['fardos']
        acumulado['lotes'] += fila['lotes']
        for clave in ('kilos', 'costo_compra', 'costo_acondicionamiento', 'costo_total',
                      'ingreso', 'margen'):
            acumulado[clave] += fila[clave]

    base = acumulado['costo_total']
    acumulado['margen_porcentaje'] = ((acumulado['margen'] / base * Decimal('100')).quantize(DOS)
                                      if base else CERO)
    return acumulado


def _dividir(importe, cantidad):
    if not cantidad:
        return CERO
    return (importe / cantidad).quantize(DOS)
