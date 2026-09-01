"""Domicilios de entrega del cliente (Plan 074).

Regla operativa definida por el usuario: **el domicilio predeterminado es el fiscal**,
pero **es responsabilidad del vendedor** asegurarse de que cada pedido salga con el
domicilio de entrega correcto. El sistema propone; no adivina.

Por eso el principal se genera solo a partir del domicilio fiscal —así ningún cliente
queda sin punto de entrega y el circuito nunca se traba—, y el vendedor elige
explícitamente cuando el cliente tiene más de uno.
"""
from verticalidades.distribucion.models import DomicilioEntrega

NOMBRE_PRINCIPAL = 'CASA CENTRAL'


def asegurar_domicilio_principal(cliente, empresa_id=None):
    """Devuelve el domicilio principal del cliente, creándolo del fiscal si no hay ninguno.

    Idempotente: si el cliente ya tiene domicilios, no toca nada y devuelve el principal
    (o el primero activo, si ninguno está marcado).
    """
    existentes = DomicilioEntrega.objects.filter(cliente=cliente, activo=True)
    principal = existentes.filter(es_principal=True).first()
    if principal:
        return principal

    primero = existentes.first()
    if primero:
        # Hay domicilios pero ninguno marcado: se promueve el primero para que el pedido
        # siempre tenga una propuesta por defecto.
        primero.es_principal = True
        primero.save(update_fields=['es_principal'])
        return primero

    return DomicilioEntrega.objects.create(
        empresa_id=empresa_id or cliente.empresa_id,
        cliente=cliente,
        nombre=NOMBRE_PRINCIPAL,
        domicilio=cliente.domicilio or 'SIN DOMICILIO CARGADO',
        localidad=cliente.localidad,
        codigo_postal=cliente.codigo_postal,
        contacto=cliente.contacto,
        telefono=cliente.telefono,
        es_principal=True,
    )


def domicilios_de(cliente):
    """Domicilios activos del cliente, con el principal primero."""
    return DomicilioEntrega.objects.filter(cliente=cliente, activo=True).select_related('zona')


def sembrar_domicilios_faltantes(empresa_id):
    """Crea el domicilio principal de todos los clientes que no tengan ninguno.

    Para la carga inicial de datos: se corre una vez después de importar los clientes.
    Devuelve cuántos creó.
    """
    from facturacion.models import ClienteProveedor

    clientes = ClienteProveedor.objects.filter(
        empresa_id=empresa_id, tipo_entidad=1).exclude(domicilios_entrega__isnull=False)
    creados = 0
    for cliente in clientes.distinct():
        asegurar_domicilio_principal(cliente, empresa_id)
        creados += 1
    return creados
