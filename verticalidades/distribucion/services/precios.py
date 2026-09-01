"""Precio de venta al cliente de reparto (Plan 074 §5.C).

    precio_unitario = Producto.precio_total * ExtensionDistribuidora.coeficiente_mayorista

La base es `precio_total`: el precio de lista CON IVA incluido. Es el que se muestra en
la hoja de ruta y el que, sumado, conforma el total facturado que consume el crédito
disponible del cliente.

`cto_rep` NO interviene acá. Es el costo de reposición, al que se le aplica el `margen`
para definir el precio de venta cuando se carga una compra: es una entrada del circuito
de compras, no de facturación.

Un solo coeficiente porque todos los clientes de reparto son revendedores. La venta a
consumidor final se hace en el local, con el circuito de descuentos autorizados y el tope
de `Rubro.descuento_maximo`, que no se toca.

Este módulo es la ÚNICA fuente de verdad del precio de distribución: ninguna vista debe
calcularlo por su cuenta.
"""
from decimal import Decimal, ROUND_HALF_UP

COEFICIENTE_NEUTRO = Decimal('1')
DOS_DECIMALES = Decimal('0.01')


def coeficiente_de(cliente):
    """Coeficiente del cliente. Sin extensión cargada, el precio de lista tal cual."""
    extension = getattr(cliente, 'distribuidora', None)
    if not extension or not extension.coeficiente_mayorista:
        return COEFICIENTE_NEUTRO
    return Decimal(str(extension.coeficiente_mayorista))


def precio_para(producto, cliente):
    """Precio unitario que le corresponde a este cliente por este producto.

    Se redondea a dos decimales acá y no en la vista: el importe que ve el vendedor en el
    celular tiene que ser exactamente el que después se factura, o el cliente reclama.
    """
    base = Decimal(str(producto.precio_total or 0))
    precio = base * coeficiente_de(cliente)
    return precio.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


def es_cliente_de_distribucion(cliente):
    """True si el cliente tiene cargada su extensión de distribución."""
    return getattr(cliente, 'distribuidora', None) is not None
