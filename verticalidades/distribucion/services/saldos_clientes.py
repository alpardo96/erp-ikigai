"""Listado de saldos pendientes por cliente, agrupado por vendedor (Plan 074 §7.8).

POR QUÉ AGRUPADO POR VENDEDOR
-----------------------------
El vendedor es el responsable directo del saldo de su cartera: es quien decide a quién le
vende y con qué límite. Un listado ordenado por cliente sirve para consultar un caso; uno
agrupado por vendedor sirve para dirigir el negocio, que es lo que se pide acá.

LAS DOS LENTES, OTRA VEZ
------------------------
El saldo que manda en este reporte es el **operativo** (`condic 1 + 2`): al cliente hay que
cobrarle todo lo que debe, tenga o no respaldo fiscal. La columna que marca cuáles
comprobantes **sólo se pueden cobrar en efectivo** es la traducción práctica de la regla de
§7.7: un PRE no se cancela con una transferencia.
"""
from decimal import Decimal

from django.utils import timezone

CERO = Decimal('0.00')

# Los mismos cortes que usa el sistema anterior. El +90 es el que dispara la gestión.
TRAMOS = ((0, 30, '0-30'), (31, 60, '31-60'), (61, 90, '61-90'), (91, None, '+90'))


def _tramo(dias):
    for desde, hasta, etiqueta in TRAMOS:
        if dias >= desde and (hasta is None or dias <= hasta):
            return etiqueta
    return TRAMOS[-1][2]


def listado(empresa_id, *, vendedor_id=None, zona_id=None, dia_visita=None,
            condics=(1, 2), solo_con_saldo=True, hoy=None):
    """Devuelve los grupos por vendedor con sus clientes y la composición del saldo.

    Cada cliente trae sus comprobantes abiertos, con la antigüedad en días y el tramo, y
    una marca `solo_efectivo` sobre los `condic = 2`.
    """
    from facturacion.models import Venta
    from verticalidades.distribucion.models import CarteraVendedor

    hoy = hoy or timezone.localdate()

    comprobantes = (Venta.objects
                    .filter(empresa_id=empresa_id, estado=0, saldo__gt=0,
                            condic__in=condics, cliente__isnull=False)
                    .select_related('cliente', 'tipo')
                    .order_by('cliente__razon_social', 'fecha', 'numero'))

    # La cartera dice de quién es cada cliente. Un cliente sin vendedor asignado no
    # desaparece del reporte: cae en un grupo propio, porque un saldo sin responsable es
    # justamente lo que hay que ver.
    cartera = {c.cliente_id: c for c in CarteraVendedor.objects
               .filter(empresa_id=empresa_id, activa=True)
               .select_related('vendedor')}

    por_cliente = {}
    for venta in comprobantes:
        cliente = venta.cliente
        asignacion = cartera.get(cliente.pk)
        if vendedor_id and (not asignacion or asignacion.vendedor_id != int(vendedor_id)):
            continue

        ficha = por_cliente.setdefault(cliente.pk, {
            'cliente': cliente,
            'vendedor': asignacion.vendedor if asignacion else None,
            'limite': Decimal(str(cliente.limite or 0)),
            'saldo': CERO,
            'saldo_real': CERO,
            'saldo_presupuestado': CERO,
            'comprobantes': [],
            'tramos': {etiqueta: CERO for _, _, etiqueta in TRAMOS},
        })

        saldo = Decimal(str(venta.saldo or 0))
        dias = (hoy - venta.fecha).days if venta.fecha else 0
        etiqueta = _tramo(dias)
        ficha['saldo'] += saldo
        if venta.condic == 2:
            ficha['saldo_presupuestado'] += saldo
        else:
            ficha['saldo_real'] += saldo
        ficha['tramos'][etiqueta] += saldo
        ficha['comprobantes'].append({
            'venta': venta,
            'dias': dias,
            'tramo': etiqueta,
            'saldo': saldo,
            # Un PRE no se cancela con una transferencia: la plata que deja rastro no
            # puede cancelar una operación que para el fisco no existe (§7.7).
            'solo_efectivo': venta.condic == 2,
        })

    fichas = list(por_cliente.values())
    if zona_id or dia_visita is not None:
        fichas = [f for f in fichas
                  if _pasa_filtro_domicilio(f['cliente'], zona_id, dia_visita)]
    for ficha in fichas:
        ficha['disponible'] = ficha['limite'] - ficha['saldo']
    if solo_con_saldo:
        fichas = [f for f in fichas if f['saldo'] > CERO]

    grupos = {}
    for ficha in fichas:
        clave = ficha['vendedor'].id if ficha['vendedor'] else 0
        grupo = grupos.setdefault(clave, {
            'vendedor': ficha['vendedor'],
            'clientes': [],
            'total': CERO,
            'tramos': {etiqueta: CERO for _, _, etiqueta in TRAMOS},
        })
        grupo['clientes'].append(ficha)
        grupo['total'] += ficha['saldo']
        for etiqueta, importe in ficha['tramos'].items():
            grupo['tramos'][etiqueta] += importe

    for grupo in grupos.values():
        grupo['clientes'].sort(key=lambda f: f['cliente'].razon_social or '')

    ordenados = sorted(
        grupos.values(),
        key=lambda g: (g['vendedor'].nombre if g['vendedor'] else 'ZZZ Sin vendedor'))

    return {
        'grupos': ordenados,
        'total': sum((g['total'] for g in ordenados), CERO),
        # Lista de pares y no diccionario: Django no tiene lookup por clave en templates.
        'tramos': [(etiqueta, sum((g['tramos'][etiqueta] for g in ordenados), CERO))
                   for _, _, etiqueta in TRAMOS],
    }


def _pasa_filtro_domicilio(cliente, zona_id, dia_visita):
    """Zona y día de visita viven en el DOMICILIO DE ENTREGA, no en el cliente.

    Un cliente con sucursales tiene domicilios en zonas y días distintos, así que alcanza
    con que UNO de ellos cumpla para que el cliente entre en el listado.
    """
    domicilios = cliente.domicilios_entrega.filter(activo=True)
    if zona_id:
        domicilios = domicilios.filter(zona_id=zona_id)
    if dia_visita is not None and dia_visita != '':
        domicilios = domicilios.filter(dias_visita__dia_semana=int(dia_visita))
    return domicilios.exists()
