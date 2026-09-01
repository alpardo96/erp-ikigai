"""Registro del pedido de distribución sobre una `Preventa` (Plan 074, fase 1).

El módulo NO crea un circuito paralelo de pedidos: reutiliza `Preventa`, que ya tiene
estados, autorización de descuentos e ítems, y le cuelga la extensión con lo propio de la
distribución — sobre todo su NÚMERO CORRELATIVO.

El número se toma con `core.services.numeracion.siguiente_numero()`, que bloquea el
contador con `select_for_update()`. Se asigna al CONFIRMAR el pedido, no en borrador, para
no dejar huecos en la serie.
"""
from decimal import Decimal

from django.db import transaction

from core.models import ContadorDocumento
from core.services.numeracion import siguiente_numero
from verticalidades.distribucion.models import CarteraVendedor, ExtensionPedidoDistribucion, Personal
from verticalidades.distribucion.services import credito
from verticalidades.distribucion.services.domicilios import asegurar_domicilio_principal


def vendedor_de(cliente, empresa_id):
    """Vendedor responsable del cliente, según su cartera.

    Un cliente tiene un solo vendedor porque es el responsable directo de su saldo.
    """
    asignacion = (CarteraVendedor.objects
                  .filter(empresa_id=empresa_id, cliente=cliente, activa=True)
                  .select_related('vendedor').first())
    return asignacion.vendedor if asignacion else None


def vendedor_del_usuario(usuario, empresa_id):
    """`Personal` vinculado al usuario logueado, si lo hay.

    Devuelve None para quien opera el sistema sin ser vendedor (un administrativo que
    carga un pedido telefónico), que es un caso normal y no un error.
    """
    if not usuario or not usuario.is_authenticated:
        return None
    return Personal.objects.filter(
        empresa_id=empresa_id, usuario=usuario, es_vendedor=True, activo=True).first()


def clientes_de_la_cartera(usuario, empresa_id):
    """IDs de los clientes que este usuario puede ver, o None si ve todos.

    El vendedor sólo ve su cartera. Un administrativo sin `Personal` asociado ve todo:
    es quien toma los pedidos telefónicos de cualquier cliente.
    """
    vendedor = vendedor_del_usuario(usuario, empresa_id)
    if not vendedor:
        return None
    return set(CarteraVendedor.objects
               .filter(empresa_id=empresa_id, vendedor=vendedor, activa=True)
               .values_list('cliente_id', flat=True))


def _hay_alerta_de_stock(preventa):
    """True si algún ítem del pedido deja el disponible en negativo.

    No bloquea: el vendedor decide y el pedido queda sujeto a disponibilidad. Queda
    registrado para que el reporte de faltantes lo pueda mostrar después.
    """
    from productos.services.stock_service import disponible_real

    for item in preventa.items.all():
        # `disponible_real` ya descuenta lo comprometido por este mismo pedido, así que
        # un pedido que consume justo el stock disponible da 0 y no dispara la alerta.
        if disponible_real(item.producto_id, preventa.sucursal_id) < 0:
            return True
    return False


@transaction.atomic
def guardar_pedido(*, empresa_id, sucursal_id, cliente, usuario, items,
                   condic_destino=1, fecha_entrega=None, observaciones=None,
                   domicilio_entrega=None,
                   origen=ExtensionPedidoDistribucion.ORIGEN_MOVIL):
    """Persiste un pedido completo desde el carrito y lo numera.

    Es el guardado del canal móvil. La pantalla de PC sigue usando `PreventaCargaView`,
    que arrastra validaciones de otras actividades; acá el circuito es sólo distribución
    y por eso queda más corto.

    La fecha NO se recibe: `Preventa.fecha` es `auto_now_add`, la pone el sistema.
    """
    from facturacion.models import Preventa, PreventaItem
    from productos.models import Producto

    if not items:
        raise ValueError("El pedido no tiene ítems.")

    requiere_autorizacion = any(i.get('requiere_autorizacion') for i in items)

    preventa = Preventa.objects.create(
        cliente=cliente,
        cliente_razon_social=cliente.razon_social,
        cliente_cuit=cliente.cuit,
        cliente_domicilio=cliente.domicilio,
        vendedor=usuario,
        empresa_id=empresa_id,
        sucursal_id=sucursal_id,
        estado=1 if requiere_autorizacion else 2,
    )

    for item in items:
        producto = Producto.objects.get(id=item['producto_id'], empresa_id=empresa_id)
        PreventaItem.objects.create(
            preventa=preventa,
            producto=producto,
            cantidad=item['cantidad'],
            precio_unitario=item['precio_unitario'],
            porcentaje_descuento=item.get('descuento', 0),
            total=item['total'],
            moneda_origen=item.get('moneda_origen', 'PES'),
            cotizacion_aplicada=item.get('cotizacion_aplicada', 1.0),
            precio_origen=item.get('precio_origen', item['precio_unitario']),
        )

    preventa.recalcular_totales()

    return registrar_pedido(
        preventa, usuario=usuario, condic_destino=condic_destino,
        fecha_entrega=fecha_entrega, origen=origen, observaciones=observaciones,
        domicilio_entrega=domicilio_entrega)


@transaction.atomic
def registrar_pedido(preventa, *, usuario=None, condic_destino=1, fecha_entrega=None,
                     origen=ExtensionPedidoDistribucion.ORIGEN_PC, observaciones=None,
                     domicilio_entrega=None):
    """Crea la extensión de distribución de una preventa y le asigna su número.

    Idempotente: si el pedido ya tiene extensión, no vuelve a numerarlo. Un pedido que se
    edita conserva su número, igual que cualquier documento emitido.

    El punto de emisión es `sucursal_id`, la sucursal que toma el pedido (definición del
    usuario, misma convención que el PRE).
    """
    existente = ExtensionPedidoDistribucion.objects.filter(preventa=preventa).first()
    if existente:
        return existente

    empresa_id = preventa.empresa_id
    punto = preventa.sucursal_id
    numero = siguiente_numero(empresa_id, punto, ContadorDocumento.PEDIDO)

    cliente = preventa.cliente
    vendedor = vendedor_de(cliente, empresa_id) or vendedor_del_usuario(usuario, empresa_id)

    # A dónde se entrega. Si no se indicó, se propone el principal (que sale del
    # domicilio fiscal), pero la responsabilidad de que sea el correcto es del vendedor.
    if domicilio_entrega is None:
        domicilio_entrega = asegurar_domicilio_principal(cliente, empresa_id)

    situacion = credito.situacion_crediticia(cliente)
    # El pedido que se está registrando ya está contado en `pedidos_pendientes`, así que
    # `disponible` es el crédito que queda DESPUÉS de tomarlo: si es negativo, este pedido
    # es el que se pasó.
    alerta_credito = situacion['disponible'] < Decimal('0')

    return ExtensionPedidoDistribucion.objects.create(
        preventa=preventa,
        punto=punto,
        numero=numero,
        vendedor=vendedor,
        domicilio_entrega=domicilio_entrega,
        domicilio_entrega_texto=domicilio_entrega.texto_completo if domicilio_entrega else None,
        fecha_entrega=fecha_entrega,
        origen=origen,
        condic_destino=condic_destino,
        # La zona sale del domicilio de entrega: es la que define en qué reparto entra.
        zona=domicilio_entrega.zona if domicilio_entrega else None,
        alerta_stock=_hay_alerta_de_stock(preventa),
        alerta_credito=alerta_credito,
        observaciones=observaciones,
    )
