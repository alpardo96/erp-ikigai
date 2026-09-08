"""Libro de retenciones practicadas (Plan 087 — Etapa 6).

DOS ORÍGENES, UNA SOLA VISTA
El acopiador retiene en dos momentos distintos —es la decisión DA-01— y cada uno deja su rastro en
una tabla distinta:

    LiquidacionRetencion  al liquidar   EEAOC, IVA, Salud Pública, Uso de Agua
    RetencionPago         al pagar      Ganancias

Al organismo no le interesa esa distinción: quiere el listado cronológico de lo que se le retuvo a
cada productor. Este módulo los unifica sin fusionar las tablas, que seguirían siendo distintas
igual: una cuelga del comprobante de compra y la otra de la Orden de Pago.

SÓLO ENTRA LO VIGENTE
Una liquidación anulada o un certificado anulado no se declaran. El importe se depositó o no se
depositó, y lo que se anuló no generó pasivo.

LOS TOTALES POR ORGANISMO SON EL PUNTO
Es lo que se necesita antes de depositar: conciliar contra el saldo de la cuenta de pasivo que
`crear_asiento()` acreditó al retener.
"""
from decimal import Decimal

from ..models import LiquidacionRetencion, LiquidacionTabaco, RetencionPago

CERO = Decimal('0.00')

LIQUIDACION, PAGO = 'LIQUIDACION', 'PAGO'


def libro(empresa_id, *, desde=None, hasta=None, codigo=None, organismo=None,
          productor_id=None, condic=1):
    """Movimientos de retención practicados, ordenados por fecha.

    `condic` filtra por la condición del comprobante de origen. Para las retenciones del pago se
    aplica sobre la LIQUIDACIÓN que la Orden de Pago canceló, que es el hecho económico que las
    originó: la OP en sí no tiene condición propia de tabaco.
    """
    filas = _del_liquidar(empresa_id, desde=desde, hasta=hasta, codigo=codigo,
                          organismo=organismo, productor_id=productor_id, condic=condic)
    filas += _del_pagar(empresa_id, desde=desde, hasta=hasta, codigo=codigo,
                        organismo=organismo, productor_id=productor_id, condic=condic)

    filas.sort(key=lambda f: (f['fecha'], f['codigo'], f['comprobante']))
    return filas


def _del_liquidar(empresa_id, *, desde, hasta, codigo, organismo, productor_id, condic):
    qs = (LiquidacionRetencion.objects
          .filter(liquidacion__empresa_id=empresa_id,
                  liquidacion__estado=LiquidacionTabaco.CONFIRMADA)
          .select_related('liquidacion', 'liquidacion__productor', 'tipo_retencion',
                          'cuenta_contable'))

    if desde:
        qs = qs.filter(liquidacion__fecha__gte=desde)
    if hasta:
        qs = qs.filter(liquidacion__fecha__lte=hasta)
    if codigo:
        qs = qs.filter(codigo=codigo)
    if organismo:
        qs = qs.filter(tipo_retencion__organismo__icontains=organismo)
    if productor_id:
        qs = qs.filter(liquidacion__productor_id=productor_id)
    if condic:
        qs = qs.filter(liquidacion__condic=condic)

    filas = []
    for ret in qs:
        liq = ret.liquidacion
        filas.append({
            'origen': LIQUIDACION,
            'origen_display': 'Al liquidar',
            'fecha': liq.fecha,
            'periodo': liq.periodo or liq.fecha.strftime('%Y%m'),
            'comprobante': f"LIQ {liq.letra} {liq.punto:04d}-{liq.numero:08d}"
                           if liq.numero else "LIQ s/n",
            'productor': liq.productor.razon_social,
            'cuit': liq.productor.cuit or '',
            'codigo': ret.codigo,
            'detalle': ret.detalle,
            'organismo': ret.tipo_retencion.organismo or '',
            'regimen': ret.tipo_retencion.regimen or '',
            'base': ret.base,
            'alicuota': ret.alicuota,
            'importe': ret.importe,
            'certificado': ret.nro_certificado or '',
            'cuenta': ret.cuenta_contable.cuenta,
            'condic': liq.condic,
            'url_origen': ('agro_liquidacion_detalle', liq.pk),
        })
    return filas


def _del_pagar(empresa_id, *, desde, hasta, codigo, organismo, productor_id, condic):
    qs = (RetencionPago.objects
          .filter(empresa_id=empresa_id, anulado=False)
          .select_related('productor', 'tipo_retencion', 'cuenta_contable', 'orden_pago'))

    if desde:
        qs = qs.filter(fecha__gte=desde)
    if hasta:
        qs = qs.filter(fecha__lte=hasta)
    if codigo:
        qs = qs.filter(codigo=codigo)
    if organismo:
        qs = qs.filter(tipo_retencion__organismo__icontains=organismo)
    if productor_id:
        qs = qs.filter(productor_id=productor_id)
    if condic:
        # La condición del hecho económico que la originó: la liquidación que la OP canceló.
        qs = qs.filter(orden_pago__pagos_liquidacion_tabaco__anulado=False,
                       orden_pago__pagos_liquidacion_tabaco__liquidacion__condic=condic).distinct()

    filas = []
    for cert in qs:
        op = cert.orden_pago
        filas.append({
            'origen': PAGO,
            'origen_display': 'Al pagar',
            'fecha': cert.fecha,
            'periodo': cert.periodo,
            'comprobante': f"OP {op.punto:04d}-{op.numero:08d}" if op.numero else f"OP {op.pk}",
            'productor': cert.productor.razon_social,
            'cuit': cert.productor.cuit or '',
            'codigo': cert.codigo,
            'detalle': cert.detalle,
            'organismo': cert.tipo_retencion.organismo or '',
            'regimen': cert.regimen or cert.tipo_retencion.regimen or '',
            # La base declarable de Ganancias es el acumulado del mes, no lo de este pago: es la
            # base sobre la que efectivamente se calculó el importe.
            'base': cert.base_acumulada,
            'alicuota': cert.alicuota,
            'importe': cert.importe,
            'certificado': cert.nro_certificado or '',
            'cuenta': cert.cuenta_contable.cuenta,
            'condic': None,
            'url_origen': ('agro_pago_detalle', op.pk),
        })
    return filas


def totales_por_organismo(filas):
    """Lo que hay que depositar a cada organismo, que es para lo que sirve el libro."""
    acumulado = {}
    for fila in filas:
        clave = (fila['organismo'] or 'SIN ORGANISMO', fila['codigo'])
        grupo = acumulado.setdefault(clave, {
            'organismo': fila['organismo'] or 'SIN ORGANISMO',
            'codigo': fila['codigo'],
            'detalle': fila['detalle'],
            'cuenta': fila['cuenta'],
            'movimientos': 0,
            'base': CERO,
            'importe': CERO,
        })
        grupo['movimientos'] += 1
        grupo['base'] += fila['base']
        grupo['importe'] += fila['importe']

    return sorted(acumulado.values(), key=lambda g: (g['organismo'], g['codigo']))


def total_general(filas):
    return sum((f['importe'] for f in filas), CERO)
