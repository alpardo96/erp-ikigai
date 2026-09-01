"""Toma de pedidos desde el celular del vendedor (Plan 074, fase 2).

Vista mobile-first con HTMX, sin app nativa. El flujo está optimizado para el pulgar y
para la calle:

  1. Elegir el cliente, acotado a la CARTERA del vendedor.
  2. Ver arriba Límite / Saldo / Disponible, que es con lo que decide la venta.
  3. Cargar renglón por renglón: [código] [cantidad] ↵.
  4. Confirmar, y recibir el número de pedido.

Conectividad: ONLINE-ONLY en esta fase (decisión del usuario). La planilla de papel es el
plan B. Una sincronización offline exigiría numeración local, resolución de conflictos de
stock y cola de reintentos, y obligaría a mostrar stock y crédito desactualizados, que es
peor que no mostrarlos.
"""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from facturacion.models import ClienteProveedor

from .models import DomicilioEntrega
from .services import carrito
from .services.credito import situacion_crediticia
from .services.domicilios import asegurar_domicilio_principal, domicilios_de
from .services.pedidos import clientes_de_la_cartera, guardar_pedido


def _empresa(request):
    return request.session.get('empresa_id')


def _clientes_habilitados(request):
    """Clientes que este usuario puede ver: su cartera, o todos si es administrativo."""
    qs = ClienteProveedor.objects.filter(empresa_id=_empresa(request), tipo_entidad=1)
    cartera = clientes_de_la_cartera(request.user, _empresa(request))
    if cartera is not None:
        qs = qs.filter(codigo_id__in=cartera)
    return qs


def _cliente_en_sesion(request):
    cliente_id = request.session.get(carrito.CLAVE_CLIENTE)
    if not cliente_id:
        return None
    return _clientes_habilitados(request).filter(codigo_id=cliente_id).first()


def _domicilio_en_sesion(request):
    domicilio_id = request.session.get(carrito.CLAVE_DOMICILIO)
    if not domicilio_id:
        return None
    return DomicilioEntrega.objects.filter(
        id=domicilio_id, empresa_id=_empresa(request)).select_related('zona').first()


def _contexto_carrito(request, error=None):
    items = carrito.obtener_items(request.session)
    cliente = _cliente_en_sesion(request)
    return {
        'items': items,
        'totales': carrito.totales(items),
        'error': error,
        'cliente': cliente,
        'domicilio_elegido': _domicilio_en_sesion(request),
    }


@login_required
def pedido_movil(request):
    """Pantalla principal. Si venía un pedido a medias en la sesión, lo retoma."""
    cliente = _cliente_en_sesion(request)
    contexto = _contexto_carrito(request)
    contexto['credito'] = situacion_crediticia(cliente) if cliente else None
    contexto['domicilios'] = domicilios_de(cliente) if cliente else []
    contexto['hide_sidebar'] = True
    return render(request, 'distribucion/movil/pedido.html', contexto)


@login_required
def movil_buscar_clientes(request):
    """Typeahead de clientes, siempre acotado a la cartera del vendedor."""
    q = (request.GET.get('q') or '').strip()
    clientes = _clientes_habilitados(request)
    if q:
        from django.db.models import Q
        filtro = Q(razon_social__icontains=q)
        if q.isdigit():
            filtro |= Q(codigo_id=int(q))
        clientes = clientes.filter(filtro)
    return render(request, 'distribucion/movil/partials/clientes_sugerencias.html',
                  {'clientes': clientes.order_by('razon_social')[:25]})


@login_required
def movil_elegir_cliente(request, cliente_id):
    """Fija el cliente del pedido y devuelve la cabecera con su crédito.

    Cambiar de cliente con ítems cargados vaciaría el carrito sin aviso, así que se
    rechaza: primero se confirma o se descarta el pedido en curso.
    """
    if request.method != 'POST':
        return HttpResponse(status=400)

    cliente = get_object_or_404(_clientes_habilitados(request), codigo_id=cliente_id)
    actual = request.session.get(carrito.CLAVE_CLIENTE)
    if actual and int(actual) != cliente.codigo_id and carrito.obtener_items(request.session):
        contexto = _contexto_carrito(
            request, error="Ya hay un pedido en curso para otro cliente. Confirmalo o descartalo antes de cambiar.")
        contexto['credito'] = situacion_crediticia(contexto['cliente']) if contexto['cliente'] else None
        return render(request, 'distribucion/movil/partials/cabecera.html', contexto)

    request.session[carrito.CLAVE_CLIENTE] = cliente.codigo_id
    # Se garantiza que el cliente tenga al menos un punto de entrega (el fiscal), para
    # que el circuito nunca se trabe por un dato que se puede derivar.
    principal = asegurar_domicilio_principal(cliente, _empresa(request))
    request.session[carrito.CLAVE_DOMICILIO] = principal.id
    request.session.modified = True
    return render(request, 'distribucion/movil/partials/cabecera.html', {
        'cliente': cliente,
        'credito': situacion_crediticia(cliente),
        'domicilios': domicilios_de(cliente),
        'domicilio_elegido': principal,
        'items': carrito.obtener_items(request.session),
        'totales': carrito.totales(carrito.obtener_items(request.session)),
    })


@login_required
def movil_buscar_productos(request):
    """Typeahead por descripción, para cuando el vendedor no recuerda el código."""
    q = (request.GET.get('q') or '').strip()
    productos = carrito.buscar_productos(q, _empresa(request))
    sucursal_id = request.session.get('sucursal_id')
    cliente = _cliente_en_sesion(request)

    from .services.precios import precio_para
    from productos.services.stock_service import disponible_real
    filas = [{
        'producto': p,
        'precio': precio_para(p, cliente) if cliente else p.precio_total,
        'disponible': disponible_real(p.id, sucursal_id) if sucursal_id else None,
    } for p in productos]
    return render(request, 'distribucion/movil/partials/productos_sugerencias.html',
                  {'filas': filas})


@login_required
def movil_item_add(request):
    """Agrega un renglón por código (o por producto elegido del typeahead)."""
    if request.method != 'POST':
        return HttpResponse(status=400)

    cliente = _cliente_en_sesion(request)
    if not cliente:
        return render(request, 'distribucion/movil/partials/carrito.html',
                      _contexto_carrito(request, error="Elegí primero el cliente."))

    producto_id = (request.POST.get('producto_id') or '').strip()
    codigo = (request.POST.get('codigo') or '').strip()
    cantidad = request.POST.get('cantidad') or '1'

    if producto_id:
        from productos.models import Producto
        producto = Producto.objects.filter(id=producto_id, empresa_id=_empresa(request)).first()
    else:
        producto = carrito.buscar_producto_por_codigo(codigo, _empresa(request))

    if not producto:
        return render(request, 'distribucion/movil/partials/carrito.html',
                      _contexto_carrito(request, error=f"No existe el artículo «{codigo}»."))

    _, error = carrito.agregar_item(
        request.session, producto, cliente, cantidad, request.session.get('sucursal_id'))
    return render(request, 'distribucion/movil/partials/carrito.html',
                  _contexto_carrito(request, error=error))


@login_required
def movil_item_remove(request, index):
    if request.method != 'POST':
        return HttpResponse(status=400)
    carrito.quitar_item(request.session, index)
    return render(request, 'distribucion/movil/partials/carrito.html',
                  _contexto_carrito(request))


@login_required
def movil_descartar(request):
    if request.method != 'POST':
        return HttpResponse(status=400)
    carrito.limpiar(request.session)
    return render(request, 'distribucion/movil/partials/carrito.html',
                  _contexto_carrito(request))


@login_required
def movil_confirmar(request):
    """Cierra el pedido: lo persiste, lo numera y devuelve el comprobante en pantalla."""
    if request.method != 'POST':
        return HttpResponse(status=400)

    cliente = _cliente_en_sesion(request)
    items = carrito.obtener_items(request.session)
    if not cliente or not items:
        return render(request, 'distribucion/movil/partials/carrito.html',
                      _contexto_carrito(request, error="Falta el cliente o los artículos."))

    pedido = guardar_pedido(
        empresa_id=_empresa(request),
        sucursal_id=request.session.get('sucursal_id'),
        cliente=cliente,
        usuario=request.user,
        items=items,
        domicilio_entrega=_domicilio_en_sesion(request),
        condic_destino=int(request.POST.get('condic_destino') or 1),
        fecha_entrega=request.POST.get('fecha_entrega') or None,
        observaciones=request.POST.get('observaciones') or None,
    )
    carrito.limpiar(request.session)

    return render(request, 'distribucion/movil/partials/confirmacion.html', {
        'pedido': pedido,
        'cliente': cliente,
        'total': pedido.preventa.total,
    })


@login_required
def movil_elegir_domicilio(request, domicilio_id):
    """Cambia el punto de entrega del pedido en curso.

    El sistema propone el principal, pero **es responsabilidad del vendedor** que cada
    pedido salga con el domicilio correcto: por eso se puede cambiar en cualquier momento
    antes de confirmar, sin perder lo cargado.
    """
    if request.method != 'POST':
        return HttpResponse(status=400)

    cliente = _cliente_en_sesion(request)
    if not cliente:
        return render(request, 'distribucion/movil/partials/cabecera.html',
                      _contexto_carrito(request, error="Elegí primero el cliente."))

    domicilio = get_object_or_404(DomicilioEntrega, id=domicilio_id,
                                  cliente=cliente, activo=True)
    request.session[carrito.CLAVE_DOMICILIO] = domicilio.id
    request.session.modified = True

    return render(request, 'distribucion/movil/partials/cabecera.html', {
        'cliente': cliente,
        'credito': situacion_crediticia(cliente),
        'domicilios': domicilios_de(cliente),
        'domicilio_elegido': domicilio,
        'items': carrito.obtener_items(request.session),
        'totales': carrito.totales(carrito.obtener_items(request.session)),
    })
