"""Stock del tabaco: ingreso por romaneo y conciliación (Plan 085).

GRANULARIDAD: UN PRODUCTO POR VARIEDAD, EN KILOS
La clase vive en el fardo, no en el producto. Si hubiera un producto por clase serían 75, y —lo
que importa de verdad— una reclasificación tendría que mover stock de uno a otro. Pero
reclasificar NO cambia lo que hay en el galpón: son los mismos kilos, mejor descriptos. Un modelo
que obligue a mover stock para corregir una etiqueta está mal planteado.

SÓLO ENTRADA
El término aporta los kilos que ENTRAN. La salida ya la resuelve el término `ventas` que existe
desde siempre: al vender tabaco se factura el `Producto` de la variedad y `VentaItem` lo descuenta.
Un segundo término de egreso duplicaría la baja.
"""
from decimal import Decimal

from django.db.models import Sum

from ..models import FardoTabaco, RomaneoTabaco, VariedadTabaco

CERO = Decimal('0.00')

# Estados de romaneo que NO cuentan para el stock: el borrador todavía se está cargando y el
# anulado no ocurrió. Cuentan CONFIRMADO y LIQUIDADO —liquidar factura, no mueve mercadería—.
ESTADOS_SIN_STOCK = (RomaneoTabaco.BORRADOR, RomaneoTabaco.ANULADO)


def termino_de_stock():
    """Descriptor del término que la verticalidad aporta al motor de stock del core."""
    from django.db.models import Q

    return {
        'nombre': 'agricola_tabaco_fardos',
        'modelo': FardoTabaco,
        'signo': 1,
        'cantidad': 'kilos',
        'producto': 'romaneo__variedad__producto_id',
        'sucursal': 'romaneo__sucursal_id',
        'signo_cbte': None,
        'excluir': Q(romaneo__estado__in=ESTADOS_SIN_STOCK),
    }


def recalcular_stock_del_romaneo(romaneo):
    """Recalcula el stock del producto de la variedad en la sucursal del romaneo.

    Se llama al CONFIRMAR y al ANULAR, que son los dos únicos momentos en que un romaneo cruza el
    umbral de contar o no contar. Agregar o quitar fardos ocurre en borrador, que no cuenta.

    Si la variedad no tiene producto asignado no hay nada que recalcular: el término no encuentra
    a qué imputar y el resto del ERP sigue igual. La conciliación lo señala.
    """
    producto_id = romaneo.variedad.producto_id
    if not producto_id:
        return None

    from productos.services.stock_service import recalcular_stock
    return recalcular_stock(producto_id, romaneo.sucursal_id)


# ---------------------------------------------------------------------------
# Conciliación
# ---------------------------------------------------------------------------

def conciliar(empresa_id, sucursal_id=None):
    """Compara los kilos del acopio contra el stock del ERP, por variedad y sucursal.

    La diferencia debe ser CERO. Si no lo es, `recalcular_stock()` la corrige: el stock es un
    valor derivado y autorreparable. Lo que este reporte aporta es DETECTARLA.
    """
    from productos.models import StockSucursal

    filas = []
    variedades = (VariedadTabaco.objects
                  .filter(empresa_id=empresa_id)
                  .select_related('producto')
                  .order_by('codigo'))

    for variedad in variedades:
        if variedad.producto_id is None:
            # Causa más probable de que los kilos no aparezcan en el stock. Se informa como fila
            # aparte en vez de omitirla: un silencio acá se lee como "está todo bien".
            filas.append(_fila_sin_producto(variedad, empresa_id))
            continue

        existencias = StockSucursal.objects.filter(producto_id=variedad.producto_id)
        if sucursal_id:
            existencias = existencias.filter(sucursal_id=sucursal_id)

        sucursales = set(existencias.values_list('sucursal_id', flat=True))
        sucursales |= set(_romaneos_vigentes(variedad, sucursal_id)
                          .values_list('sucursal_id', flat=True))

        for suc_id in sorted(s for s in sucursales if s):
            filas.append(_fila(variedad, suc_id))

    return filas


def _romaneos_vigentes(variedad, sucursal_id=None):
    qs = (RomaneoTabaco.objects
          .filter(variedad=variedad)
          .exclude(estado__in=ESTADOS_SIN_STOCK))
    return qs.filter(sucursal_id=sucursal_id) if sucursal_id else qs


def _fila_sin_producto(variedad, empresa_id):
    recibidos = (FardoTabaco.objects
                 .filter(romaneo__variedad=variedad)
                 .exclude(romaneo__estado__in=ESTADOS_SIN_STOCK)
                 .aggregate(s=Sum('kilos'))['s'] or CERO)
    return {
        'variedad': variedad, 'sucursal': None, 'sin_producto': True,
        'recibidos': recibidos, 'acondicionados': CERO, 'vendidos': CERO,
        'stock_inicial': CERO,
        'esperado': CERO, 'en_erp': CERO, 'diferencia': CERO,
    }


def _fila(variedad, sucursal_id):
    from empresas.models import Sucursal
    from facturacion.models import VentaItem
    from productos.models import StockSucursal

    from ..models import Acondicionamiento

    recibidos = (FardoTabaco.objects
                 .filter(romaneo__variedad=variedad, romaneo__sucursal_id=sucursal_id)
                 .exclude(romaneo__estado__in=ESTADOS_SIN_STOCK)
                 .aggregate(s=Sum('kilos'))['s'] or CERO)

    # Plan 086: lo que sale de la variedad al acondicionar. `kilos_baja` incluye los coproductos
    # porque ya no son tabaco de esta variedad: reaparecen en su propio producto, no acá.
    acondicionados = (Acondicionamiento.objects
                      .filter(lote__variedad=variedad, lote__sucursal_id=sucursal_id,
                              estado=Acondicionamiento.CERRADO)
                      .aggregate(s=Sum('kilos_baja'))['s'] or CERO)

    # La salida se mide con el mismo criterio que usa el motor de stock: ventas vigentes del
    # producto en esa sucursal. Si acá se contara de otra forma, la conciliación mentiría.
    vendidos = (VentaItem.objects
                .filter(producto_id=variedad.producto_id, venta__sucursal_id=sucursal_id)
                .exclude(venta__estado=1)
                .exclude(venta__id_fac_rem__isnull=False)
                .aggregate(s=Sum('cantidad'))['s'] or CERO)

    existencia = (StockSucursal.objects
                  .filter(producto_id=variedad.producto_id, sucursal_id=sucursal_id)
                  .first())
    inicial = (existencia.stock_inicial if existencia else CERO) or CERO
    en_erp = (existencia.cantidad if existencia else CERO) or CERO
    esperado = inicial + recibidos - acondicionados - vendidos

    return {
        'variedad': variedad,
        'sucursal': Sucursal.objects.filter(pk=sucursal_id).first(),
        'sin_producto': False,
        'recibidos': recibidos,
        'acondicionados': acondicionados,
        'vendidos': vendidos,
        'stock_inicial': inicial,
        'esperado': esperado,
        'en_erp': en_erp,
        'diferencia': esperado - en_erp,
    }


# ---------------------------------------------------------------------------
# Acondicionamiento (Plan 086)
# ---------------------------------------------------------------------------

def recalcular_stock_del_acondicionamiento(acond):
    """Recalcula la variedad del lote y cada producto coproducto de la corrida.

    Se llama al CERRAR y al ANULAR, que son los dos únicos momentos en que un acondicionamiento
    cruza el umbral de contar o no contar. Agregar líneas ocurre en borrador, que no cuenta.

    Recalcula también los coproductos ANULADOS: si no se tocaran, al anular la corrida sus kilos
    quedarían para siempre en el stock del palo.
    """
    from productos.services.stock_service import recalcular_stock

    lote = acond.lote
    afectados = set()

    if lote.variedad.producto_id:
        afectados.add(lote.variedad.producto_id)
    afectados |= set(acond.coproductos.values_list('producto_id', flat=True))

    for producto_id in afectados:
        recalcular_stock(producto_id, lote.sucursal_id)

    return afectados
