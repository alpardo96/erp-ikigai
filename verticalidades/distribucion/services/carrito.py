"""Carrito del pedido en sesión (Plan 074, fase 2).

Comparte la clave de sesión `preventa_items_temp` con la pantalla de PC a propósito: un
pedido empezado en un lado se puede terminar en el otro, y el formato del ítem es el
mismo, así que el guardado es común.

El precio NUNCA viene del navegador: se resuelve acá con el coeficiente del cliente. El
importe que ve el vendedor tiene que ser exactamente el que después se factura.
"""
from decimal import Decimal, InvalidOperation

from django.db.models import Q

from verticalidades.distribucion.services.precios import precio_para
from productos.models import Producto
from productos.services.stock_service import disponible_real

CLAVE_ITEMS = 'preventa_items_temp'
CLAVE_CLIENTE = 'distribucion_movil_cliente'
CLAVE_DOMICILIO = 'distribucion_movil_domicilio'


def buscar_producto_por_codigo(codigo, empresa_id):
    """Resuelve un producto por el código que el vendedor tiene en la lista de precios.

    Acepta indistintamente el ID del ERP y el código del sistema anterior, porque durante
    la transición conviven los dos y el vendedor usa el que recuerda. Se prioriza el ID
    del ERP, que es el código definitivo.
    """
    codigo = (codigo or '').strip().upper()
    if not codigo:
        return None

    if codigo.isdigit():
        producto = Producto.objects.filter(id=int(codigo), empresa_id=empresa_id).first()
        if producto:
            return producto

    return Producto.objects.filter(
        Q(codigo_anterior=codigo) | Q(cod_fab=codigo),
        empresa_id=empresa_id).first()


def buscar_productos(texto, empresa_id, limite=25):
    """Typeahead por descripción, para cuando el vendedor no recuerda el código."""
    texto = (texto or '').strip()
    if not texto:
        return Producto.objects.none()
    filtro = Q(detalle__icontains=texto) | Q(codigo_anterior__icontains=texto)
    if texto.isdigit():
        filtro |= Q(id=int(texto))
    return Producto.objects.filter(filtro, empresa_id=empresa_id).order_by('detalle')[:limite]


def _a_decimal(valor, defecto=Decimal('0')):
    """Convierte un valor del formulario, aceptando el formato es-AR (1.234,56)."""
    if valor in (None, ''):
        return defecto
    if isinstance(valor, Decimal):
        return valor
    texto = str(valor).strip().replace('.', '').replace(',', '.')
    try:
        return Decimal(texto)
    except (InvalidOperation, ValueError):
        return defecto


def obtener_items(session):
    return session.get(CLAVE_ITEMS, [])


def limpiar(session):
    session[CLAVE_ITEMS] = []
    session.pop(CLAVE_CLIENTE, None)
    session.pop(CLAVE_DOMICILIO, None)
    session.modified = True


def totales(items):
    total = sum(Decimal(str(i['total'])) for i in items) if items else Decimal('0')
    return {
        'cantidad_items': len(items),
        'total': total,
        'requiere_autorizacion': any(i.get('requiere_autorizacion') for i in items),
    }


def agregar_item(session, producto, cliente, cantidad, sucursal_id):
    """Suma un renglón al carrito. Devuelve (items, error).

    Si el producto ya estaba, ACUMULA la cantidad en lugar de rechazar: en la calle el
    vendedor va cantando lo que el cliente pide y es normal que vuelva sobre un artículo.
    """
    cantidad = _a_decimal(cantidad, Decimal('1'))
    if cantidad <= 0:
        return obtener_items(session), "La cantidad tiene que ser mayor a cero."

    items = obtener_items(session)
    precio = precio_para(producto, cliente)
    disponible = disponible_real(producto.id, sucursal_id) if sucursal_id else None

    existente = next((i for i in items if str(i['producto_id']) == str(producto.id)), None)
    if existente:
        nueva_cantidad = Decimal(str(existente['cantidad'])) + cantidad
        existente['cantidad'] = float(nueva_cantidad)
        existente['total'] = float((nueva_cantidad * precio).quantize(Decimal('0.01')))
        existente['precio_unitario'] = float(precio)
    else:
        items.append({
            'index': len(items),
            'producto_id': producto.id,
            'codigo': producto.cod_prov or producto.id,
            'codigo_erp': producto.id,
            'codigo_anterior': producto.codigo_anterior or '',
            'detalle': producto.detalle,
            'cantidad': float(cantidad),
            'precio_unitario': float(precio),
            'descuento': 0,
            'descuento_maximo': float(producto.rubro.descuento_maximo) if producto.rubro else 0.0,
            'total': float((cantidad * precio).quantize(Decimal('0.01'))),
            'requiere_autorizacion': False,
            'moneda_origen': producto.moneda,
            'cotizacion_aplicada': 1.0,
            'precio_origen': float(precio),
            'credencial': '',
            'dmp': 0,
            'disponible': float(disponible) if disponible is not None else None,
        })

    for i, item in enumerate(items):
        item['index'] = i
    session[CLAVE_ITEMS] = items
    session.modified = True
    return items, None


def quitar_item(session, index):
    items = obtener_items(session)
    if 0 <= index < len(items):
        items.pop(index)
        for i, item in enumerate(items):
            item['index'] = i
    session[CLAVE_ITEMS] = items
    session.modified = True
    return items
