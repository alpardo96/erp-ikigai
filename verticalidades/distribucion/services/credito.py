"""Crédito del cliente de reparto (Plan 074 §7.3 y §7.4).

LA REGLA DEL SALDO DISPONIBLE NEGATIVO
--------------------------------------
    saldo_disponible = limite − saldo
    cobro_minimo     = max(0, −saldo_disponible)

Esa formulación absorbe los cuatro casos del negocio sin un solo condicional especial:

    | Situación                    | Disponible      | Cobro mínimo | Condición      |
    |------------------------------|-----------------|--------------|----------------|
    | Entra holgado en el límite   | positivo        | 0            | CUENTA CORRIENTE |
    | Se pasa parcialmente         | negativo parcial| el excedente | CUENTA CORRIENTE |
    | `limite = 0` (sólo contado)  | −total          | el total     | CONTADO        |
    | `bloqueado_credito`          | se fuerza −total| el total     | CONTADO        |

`limite = 0` significa SÓLO CONTADO (definición del usuario), no "sin límite". Un cliente
con crédito ilimitado se carga con un límite alto explícito.

DOS MOMENTOS DISTINTOS
----------------------
- Al TOMAR el pedido (`disponible_al_tomar`): es información para vender, no un bloqueo, y
  descuenta los pedidos que todavía no se facturaron. Sin ese término, tres pedidos del
  mismo día pasan todos el control porque ninguno llegó todavía a `saldo`.
- Al FACTURAR (fase 4 del plan): ahí el control es vinculante y ya no hay pedidos por
  delante, así que el término de pendientes vale cero por construcción.
"""
from decimal import Decimal

from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce

CERO = Decimal('0.00')
_DEC = DecimalField(max_digits=20, decimal_places=2)


def esta_bloqueado(cliente):
    """Corte manual de la administración, con independencia del límite cargado."""
    extension = getattr(cliente, 'distribuidora', None)
    return bool(extension and extension.bloqueado_credito)


def total_pedidos_sin_facturar(cliente):
    """Importe de los pedidos vivos del cliente que todavía no se facturaron.

    Es la pieza que falta en `limite − saldo` durante la ventana entre que el vendedor
    toma el pedido y la administración lo factura.
    """
    from facturacion.models import Preventa
    from productos.services.stock_service import ESTADOS_PEDIDO_COMPROMETEN

    total = Preventa.objects.filter(
        cliente=cliente, estado__in=ESTADOS_PEDIDO_COMPROMETEN
    ).aggregate(
        t=Coalesce(Sum('total', output_field=_DEC), Value(CERO), output_field=_DEC)
    )['t']
    return total or CERO


def situacion_crediticia(cliente, incluir_pedidos_pendientes=True):
    """Foto del crédito del cliente, lista para mostrar o para decidir.

    Devuelve un dict con:
      limite, saldo, pedidos_pendientes, disponible, cobro_minimo,
      bloqueado, solo_contado, excedido
    """
    limite = Decimal(str(cliente.limite or 0))
    saldo = Decimal(str(cliente.saldo or 0))
    pendientes = total_pedidos_sin_facturar(cliente) if incluir_pedidos_pendientes else CERO

    disponible = limite - saldo - pendientes
    bloqueado = esta_bloqueado(cliente)
    # Un cliente bloqueado no tiene crédito, sin importar el límite que tenga cargado.
    if bloqueado:
        disponible = min(disponible, CERO)

    return {
        'limite': limite,
        'saldo': saldo,
        'pedidos_pendientes': pendientes,
        'disponible': disponible,
        'cobro_minimo': max(CERO, -disponible),
        'bloqueado': bloqueado,
        # `limite = 0` es la forma de decir "este cliente compra sólo de contado".
        'solo_contado': limite == CERO or bloqueado,
        'excedido': disponible < CERO,
    }


def disponible_al_tomar(cliente):
    """Crédito disponible en el momento de tomar el pedido. Puede ser negativo."""
    return situacion_crediticia(cliente)['disponible']


def entra_en_el_credito(cliente, importe):
    """¿Un pedido de este importe entra en el crédito disponible del cliente?

    No bloquea nada por sí sola: al tomar el pedido es informativa (deja `alerta_credito`),
    y el control vinculante ocurre recién al facturar.
    """
    return disponible_al_tomar(cliente) >= Decimal(str(importe or 0))
