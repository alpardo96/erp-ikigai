"""Catálogos iniciales del módulo Distribución (Plan 074).

La siembra es IDEMPOTENTE (`get_or_create` por `empresa` + `codigo`): se puede
ejecutar las veces que haga falta sin duplicar ni pisar lo que el usuario haya
editado a mano.

No se hace por migración de datos a propósito: los motivos son por empresa y una
empresa puede pasar a ser DISTRIBUIDORA mucho después de esta migración. Se siembra
bajo demanda, desde el botón de la pantalla de Motivos o con el comando
`manage.py sembrar_motivos_devolucion`.
"""
from verticalidades.distribucion.models import MotivoDevolucion

# (codigo, descripcion, momento, sugiere_apto_reventa, requiere_observacion)
#
# Los tres motivos con `apto_reventa = False` son los que sacan la mercadería del
# stock vendible. PROXIMO_A_VENCER y CADENA_DE_FRIO se mantienen separados de
# PRODUCTO_DAÑADO a propósito: son propios del rubro lácteo y, agrupados bajo un
# genérico, se pierde la información que después explica una merma.
MOTIVOS_INICIALES = [
    ('CLIENTE_ANULO', 'El cliente anuló el pedido', 'PRE_CARGA', True, False),
    ('CLIENTE_REDUJO', 'El cliente redujo el pedido', 'PRE_CARGA', True, False),
    ('PEDIDO_DUPLICADO', 'Pedido cargado dos veces', 'PRE_CARGA', True, False),
    ('ERROR_DE_CARGA', 'Error al cargar el pedido (producto o cantidad)', 'AMBOS', True, False),
    ('ERROR_FACTURACION', 'Comprobante mal emitido (datos o precio)', 'AMBOS', True, False),
    ('NEGOCIO_CERRADO', 'El negocio estaba cerrado', 'EN_ENTREGA', True, False),
    ('CLIENTE_AUSENTE', 'No estaba quien recibe', 'EN_ENTREGA', True, False),
    ('NO_TENIA_DINERO', 'No reunió el cobro mínimo exigido', 'EN_ENTREGA', True, False),
    ('RECHAZA_PRODUCTO', 'No lo quiere o dice no haberlo pedido', 'EN_ENTREGA', True, False),
    ('RECHAZA_PRECIO', 'No acepta el precio facturado', 'EN_ENTREGA', True, False),
    ('DIRECCION_INCORRECTA', 'No se ubicó el domicilio', 'EN_ENTREGA', True, False),
    ('NO_SE_LLEGO', 'No se alcanzó a pasar en el recorrido', 'EN_ENTREGA', True, False),
    ('FALTANTE_DE_CARGA', 'No subió al vehículo', 'EN_ENTREGA', True, False),
    ('PRODUCTO_DANADO', 'Envase roto o mercadería en mal estado', 'AMBOS', False, False),
    ('PROXIMO_A_VENCER', 'Vencimiento corto, el cliente no lo acepta', 'EN_ENTREGA', False, False),
    ('CADENA_DE_FRIO', 'Temperatura fuera de rango', 'AMBOS', False, False),
    ('OTROS', 'Otro motivo', 'AMBOS', True, True),
]


def sembrar_motivos(empresa_id, usuario=None):
    """Crea los motivos que falten para la empresa. Devuelve cuántos creó."""
    creados = 0
    for codigo, descripcion, momento, apto, obs in MOTIVOS_INICIALES:
        _, creado = MotivoDevolucion.objects.get_or_create(
            empresa_id=empresa_id,
            codigo=codigo,
            defaults={
                'descripcion': descripcion,
                'momento': momento,
                'sugiere_apto_reventa': apto,
                'requiere_observacion': obs,
                'activo': True,
                'creado_por': usuario,
            },
        )
        if creado:
            creados += 1
    return creados
