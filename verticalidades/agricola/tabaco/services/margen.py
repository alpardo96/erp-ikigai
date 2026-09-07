"""Margen del acopio, por lote y por fardo (Plan 086 — Etapa 5).

    margen(lote) = importe_venta + valor_coproductos − (costo_compra + costo_acondicionamiento)

QUÉ SE PRORRATEA Y QUÉ NO — es la decisión de fondo de este módulo

    Costo de compra          EXACTO por fardo. Existe: es lo que se le pagó al productor por ESE
                             fardo, con su clase y su precio congelados desde el romaneo.
    Costo de acondicionar    PRORRATEADO por kilos. Una merma de proceso no es atribuible a un
                             fardo individual: los fardos se mezclan en la máquina.
    Ingreso de la venta      PRORRATEADO por kilos, por la misma razón.

Prorratear el costo de compra cuando existe el dato exacto sería perder información a cambio de
nada: dos fardos del mismo peso pueden haberse pagado a precios muy distintos según su clase, y
esa diferencia es justamente lo que el reporte tiene que mostrar.

EL INGRESO SE MIDE SOBRE LAS LÍNEAS DEL PRODUCTO DE LA VARIEDAD
Si en la misma factura se cobró un flete o un servicio, ese importe no es ingreso del tabaco.
Contarlo inflaría el margen. Lo resuelve `lotes.importe_de_venta()`.
"""
from decimal import Decimal



from ..models import LoteAcopio

CERO = Decimal('0.00')
DOS = Decimal('0.01')


def margen_por_lote(empresa_id, *, campania_id=None, variedad_id=None, sucursal_id=None,
                    estado=None, condic=None, solo_vendidos=False):
    """Una fila por lote, con costo, venta y margen.

    `condic` filtra por la condición de los ROMANEOS que aportaron los fardos: es la condición del
    hecho económico de origen. Un lote puede mezclar romaneos de distinta condición, así que el
    filtro se aplica con `distinct()` sobre la existencia de al menos un fardo que la cumpla.
    """
    qs = (LoteAcopio.objects
          .filter(empresa_id=empresa_id)
          .exclude(estado=LoteAcopio.ANULADO)
          .select_related('variedad', 'campania', 'sucursal', 'venta'))

    if campania_id:
        qs = qs.filter(campania_id=campania_id)
    if variedad_id:
        qs = qs.filter(variedad_id=variedad_id)
    if sucursal_id:
        qs = qs.filter(sucursal_id=sucursal_id)
    if estado:
        qs = qs.filter(estado=estado)
    if solo_vendidos:
        qs = qs.filter(venta__isnull=False)
    if condic:
        qs = qs.filter(fardos__romaneo__condic=condic).distinct()

    filas = []
    for lote in qs.order_by('-fecha', '-numero'):
        filas.append({
            'lote': lote,
            'kilos': lote.total_kilos,
            'kilos_actuales': lote.kilos_actuales,
            'costo_compra': lote.costo_compra,
            'costo_acondicionamiento': lote.costo_acondicionamiento,
            'costo_total': lote.costo_total,
            'valor_coproductos': lote.valor_coproductos,
            'importe_venta': lote.importe_venta,
            'margen': lote.margen,
            'margen_porcentaje': lote.margen_porcentaje,
            'costo_por_kilo': _dividir(lote.costo_total, lote.total_kilos),
            'venta_por_kilo': _dividir(lote.importe_venta, lote.kilos_actuales),
        })
    return filas


def totales(filas):
    """Suma las columnas de importe. El % se recalcula sobre los totales, nunca se promedia."""
    acumulado = {c: CERO for c in ('kilos', 'kilos_actuales', 'costo_compra',
                                   'costo_acondicionamiento', 'costo_total', 'valor_coproductos',
                                   'importe_venta', 'margen')}
    for fila in filas:
        for clave in acumulado:
            acumulado[clave] += fila[clave]

    base = acumulado['costo_total']
    acumulado['margen_porcentaje'] = (
        (acumulado['margen'] / base * Decimal('100')).quantize(DOS) if base else CERO)
    return acumulado


def margen_por_fardo(lote):
    """Desagrega el margen del lote a cada fardo.

    El prorrateo usa los kilos DE COMPRA (`total_kilos`) y no los actuales: los kilos actuales ya
    descontaron la merma, que es precisamente uno de los costos que se están repartiendo. Repartir
    sobre una base ya neteada le cargaría la merma dos veces a los fardos que quedaron.
    """
    base_kilos = lote.total_kilos or CERO
    costo_acond = lote.costo_acondicionamiento
    # El valor recuperado en coproductos abarata el lote: se reparte junto con el ingreso.
    ingreso = lote.importe_venta + lote.valor_coproductos

    filas = []
    for fardo in (lote.fardos
                  .select_related('clase', 'romaneo', 'romaneo__productor')
                  .order_by('romaneo__numero', 'numero_fardo')):

        proporcion = (fardo.kilos / base_kilos) if base_kilos else CERO
        compra = fardo.importe + fardo.adicional
        acond = (costo_acond * proporcion).quantize(DOS)
        venta = (ingreso * proporcion).quantize(DOS)
        costo = compra + acond
        margen = venta - costo

        filas.append({
            'fardo': fardo,
            'kilos': fardo.kilos,
            'proporcion': proporcion,
            'costo_compra': compra,
            'costo_acondicionamiento': acond,
            'costo_total': costo,
            'ingreso': venta,
            'margen': margen,
            'margen_porcentaje': ((margen / costo * Decimal('100')).quantize(DOS)
                                  if costo else CERO),
            'costo_por_kilo': _dividir(costo, fardo.kilos),
        })
    return filas


def resumen_por_clase(lote):
    """Agrupa el margen del lote por clase de tabaco.

    Es la lectura que sirve para comprar mejor el año que viene: dice qué clases dejaron plata y
    cuáles se pagaron de más.
    """
    acumulado = {}
    for fila in margen_por_fardo(lote):
        clase = fila['fardo'].clase
        grupo = acumulado.setdefault(clase.pk, {
            'clase': clase, 'fardos': 0, 'kilos': CERO, 'costo_total': CERO,
            'ingreso': CERO, 'margen': CERO})
        grupo['fardos'] += 1
        grupo['kilos'] += fila['kilos']
        grupo['costo_total'] += fila['costo_total']
        grupo['ingreso'] += fila['ingreso']
        grupo['margen'] += fila['margen']

    filas = sorted(acumulado.values(), key=lambda g: g['clase'].codigo)
    for grupo in filas:
        base = grupo['costo_total']
        grupo['margen_porcentaje'] = ((grupo['margen'] / base * Decimal('100')).quantize(DOS)
                                      if base else CERO)
    return filas


def _dividir(importe, cantidad):
    if not cantidad:
        return CERO
    return (importe / cantidad).quantize(DOS)
