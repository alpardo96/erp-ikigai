"""Suscripción a los puntos de extensión del core (Plan 080).

Es el lado CONSUMIDOR del Plan 080: acá la verticalidad se anuncia. El core nunca importa nada de
`verticalidades.*`; si esta carpeta no está, su app no entra a `INSTALLED_APPS`, `ready()` no
corre, no se registra nada y el core calcula como si el módulo no existiera.

El `try/except ImportError` cubre el despliegue escalonado: si el core todavía no tuviera los
puntos de extensión, la verticalidad arranca igual y simplemente no aporta sus términos.
"""
import logging

logger = logging.getLogger(__name__)


def registrar_todo():
    """Registra los orígenes que la verticalidad aporta a los servicios del core."""
    _registrar_cuenta_corriente()


def _registrar_cuenta_corriente():
    """La liquidación de compra genera deuda con el productor.

    Aporta el TOTAL del comprobante, no el neto a pagar: la retención de Ganancias se practica al
    pagar y `OrdenPago.total` ya la incluye como medio de pago. Si acá se declarara el neto de
    Ganancias, la OP cancelaría de más y el productor quedaría con un crédito falso (es el
    supuesto S-1 documentado en `contable/services/saldos.py`).
    """
    try:
        from contable.services.saldos import registrar_termino_ctacte
    except ImportError:
        logger.warning("El core no expone `registrar_termino_ctacte`: la deuda de las "
                       "liquidaciones de tabaco NO se reflejará en la cuenta corriente.")
        return

    from django.db.models import Q

    from .models import LiquidacionTabaco

    registrar_termino_ctacte({
        'nombre': 'agricola_tabaco_liquidaciones',
        'modelo': LiquidacionTabaco,
        'campo_entidad': 'productor',
        'campo_empresa': 'empresa_id',
        'campo_importe': 'total',
        'signo': -1,                       # mismo signo que compras: nos genera deuda
        # Sólo las confirmadas son deuda: un borrador todavía no es un comprobante y una anulada
        # dejó de serlo.
        'excluir': ~Q(estado=LiquidacionTabaco.CONFIRMADA),
    })
