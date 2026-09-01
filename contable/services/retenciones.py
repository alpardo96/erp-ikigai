"""Retenciones practicadas: deducción del régimen y persistencia de los certificados.

El régimen de la RG 830 no se tipea: está configurado en el plan de cuentas. Cada cuenta de
compras (activo o egreso) lleva en `Cuenta.rg_830` el código de régimen que le corresponde, y
cada comprobante sabe con qué cuenta se imputó. Al pagar, se encadena:

    Compra.cta_imputacion → Cuenta.rg_830 → régimen

Así el operador no tiene que recordar qué régimen aplica a cada tipo de gasto: lo define una
sola vez al armar el plan de cuentas.
"""
from decimal import Decimal

from contable.models import Cuenta, RetencionPracticada


def regimen_rg830_de_compra(compra):
    """Código de régimen RG 830 que corresponde a una compra, o None si no se puede deducir.

    Primero mira la cuenta de imputación del comprobante (es la que usan los GASTOS). Si la
    compra vino con ítems de productos, esa cuenta suele estar vacía: en ese caso se cae a la
    cuenta de compras del rubro de los productos.
    """
    cuenta = None
    if compra.cta_imputacion:
        cuenta = Cuenta.objects.filter(
            pk=compra.cta_imputacion, empresa_id=compra.empresa_id
        ).only('rg_830').first()

    if cuenta is None:
        # Compra con ítems: el régimen sale de la cuenta de compras del rubro del producto.
        # Se toma la del primer ítem que tenga rubro con cuenta y régimen configurados.
        for item in compra.items.select_related('producto__rubro__cta_compras').all():
            rubro = getattr(item.producto, 'rubro', None)
            cta_rubro = getattr(rubro, 'cta_compras', None) if rubro else None
            if cta_rubro and cta_rubro.rg_830:
                cuenta = cta_rubro
                break

    if cuenta and cuenta.rg_830:
        return str(cuenta.rg_830)
    return None


def regimenes_de_aplicaciones(orden_pago):
    """Regímenes RG 830 involucrados en las facturas que paga una Orden de Pago.

    Devuelve {régimen: base_imponible} sumando lo aplicado a cada comprobante. Si las facturas
    caen en más de un régimen, corresponde una retención por cada uno; por eso se devuelve el
    desglose y no un único valor.

    Las aplicaciones negativas (Notas de Crédito) restan de la base, que es lo correcto: la
    retención se calcula sobre el neto efectivamente pagado.
    """
    bases = {}
    for aplicacion in orden_pago.aplicaciones.select_related('compra').all():
        regimen = regimen_rg830_de_compra(aplicacion.compra)
        if not regimen:
            continue
        bases[regimen] = bases.get(regimen, Decimal('0')) + Decimal(str(aplicacion.importe_pesos or 0))
    return bases


def registrar_retenciones_practicadas(orden_pago, retenciones, asiento_id=None):
    """Persiste los certificados de retención practicados en una Orden de Pago.

    `retenciones` es la lista de medios de pago de categoría RET que llegó del formulario.
    Cada uno trae impuesto, importe, número de certificado, fecha y CUIT; el régimen y la base
    se completan solos desde los comprobantes aplicados cuando el formulario no los trae.

    Antes estos datos se capturaban en pantalla y se descartaban: sólo quedaba el importe como
    un medio de pago más, de modo que la DDJJ de SICORE era imposible de armar.
    """
    if not retenciones:
        return []

    bases_por_regimen = regimenes_de_aplicaciones(orden_pago) if orden_pago.tipo == 'P' else {}
    # Si hay un único régimen involucrado, es el que corresponde a todas las retenciones de
    # esta orden. Con varios, se deja que lo defina el dato explícito del formulario.
    regimen_unico = next(iter(bases_por_regimen)) if len(bases_por_regimen) == 1 else None

    creadas = []
    for ret in retenciones:
        importe = Decimal(str(ret.get('importe') or 0))
        if importe == 0:
            continue

        regimen = (ret.get('regimen') or regimen_unico or '')
        base = ret.get('base')
        if base in (None, '', 0):
            base = bases_por_regimen.get(regimen, Decimal('0'))
        base = Decimal(str(base or 0))

        alicuota = ret.get('alicuota')
        if alicuota in (None, ''):
            # Se deriva de los importes para no pedirle al operador un dato redundante.
            alicuota = (importe / base * 100).quantize(Decimal('0.001')) if base else Decimal('0')

        creadas.append(RetencionPracticada.objects.create(
            empresa_id=orden_pago.empresa_id,
            orden_pago=orden_pago,
            proveedor=orden_pago.proveedor,
            impuesto=ret.get('impuesto') or 'GAN',
            regimen=str(regimen)[:10],
            nro_certificado=(ret.get('numero_comprobante') or '')[:30],
            fecha=ret.get('fecha') or orden_pago.fecha,
            base=base,
            alicuota=Decimal(str(alicuota)),
            importe=importe,
            cuit_retenido=(ret.get('cuit') or orden_pago.proveedor.cuit or '')[:20],
            asiento_id=asiento_id,
        ))
    return creadas
