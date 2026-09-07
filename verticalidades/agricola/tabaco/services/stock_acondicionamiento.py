"""Los dos términos de stock que aporta el acondicionamiento (Plan 086 — Etapa 5).

Se suman a `agricola_tabaco_fardos` (Plan 085), que es el que hace ENTRAR los kilos comprados.
La fórmula completa del tabaco queda así:

    stock(variedad)   = Σ fardos de romaneos vigentes    (+, Plan 085)
                      − Σ kilos_baja de acondicionamientos cerrados   (−, este módulo)
                      − Σ ventas                          (término `ventas` del core, de siempre)

    stock(coproducto) = Σ coproducto.kilos                (+, este módulo)
                      − Σ ventas                          (término `ventas` del core)

POR QUÉ `kilos_baja` Y NO `kilos_merma`
`kilos_baja` = entrada − salida: TODO lo que dejó de ser tabaco de esa variedad, coproductos
incluidos. Si acá se restara sólo la merma, los kilos del palo quedarían contados dos veces —una
como tabaco y otra como coproducto—.

`registrar_termino_stock` acepta varios términos: `_TERMINOS_EXTRA` es una lista y sólo rechaza
nombres repetidos.
"""
from django.db.models import Q

from ..models import Acondicionamiento, AcondicionamientoCoproducto

# Sólo el acondicionamiento CERRADO mueve existencias. Un borrador todavía se está cargando —el
# stock no puede bailar mientras el operario tipea— y un anulado dejó de valer.
ESTADOS_SIN_STOCK = (Acondicionamiento.BORRADOR, Acondicionamiento.ANULADO)


def termino_de_bajas():
    """Los kilos que salen de la variedad al acondicionar."""
    return {
        'nombre': 'agricola_tabaco_acond_bajas',
        'modelo': Acondicionamiento,
        'signo': -1,
        'cantidad': 'kilos_baja',
        'producto': 'lote__variedad__producto_id',
        'sucursal': 'lote__sucursal_id',
        'signo_cbte': None,
        'excluir': Q(estado__in=ESTADOS_SIN_STOCK),
    }


def termino_de_coproductos():
    """Los kilos que reaparecen como otro producto: el palo, el descarte."""
    return {
        'nombre': 'agricola_tabaco_acond_coproductos',
        'modelo': AcondicionamientoCoproducto,
        'signo': 1,
        'cantidad': 'kilos',
        'producto': 'producto_id',
        'sucursal': 'acondicionamiento__lote__sucursal_id',
        'signo_cbte': None,
        'excluir': Q(acondicionamiento__estado__in=ESTADOS_SIN_STOCK),
    }
