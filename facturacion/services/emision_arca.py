"""Solicitud del CAE a ARCA para una `Venta` ya persistida (Plan 075 §5.3).

El circuito real de emisión existía sólo dentro de `VentasCargaView.post`, embebido en el
manejo del formulario, así que ningún otro proceso podía emitir. Acá se lo expone como
servicio para que la facturación por lote —y cualquier otro emisor futuro— use exactamente
el mismo camino en lugar de reimplementarlo.

REGLA CENTRAL: en la serie fiscal **el número lo da ARCA**, no el sistema. Se toma de
`CbteDesde` en la respuesta del CAE. Numerar localmente y después pedir autorización es
justamente lo que produce comprobantes que no coinciden con lo declarado.
"""
from decimal import Decimal

from facturacion.services.afip_service import AFIPService


class ErrorEmisionARCA(Exception):
    """Rechazo de ARCA o configuración incompleta. Lleva el mensaje para el usuario."""


def _alicuotas_de(venta):
    """Alícuotas en el formato que espera `AFIPService`, desde las ya guardadas."""
    return [{
        'id_iva': a.id_iva,
        'alicuota': a.alicuota,
        'base_imponible': a.base_imponible,
        'importe_iva': a.importe_iva,
    } for a in venta.alicuotas_iva.all()]


def emitir_cae(venta, alicuotas=None):
    """Pide el CAE y estampa en la venta el número, el CAE, su vencimiento y el QR.

    NO guarda, y **acepta una venta todavía sin persistir**: el número de la serie fiscal
    lo da ARCA, así que hay que pedirlo ANTES de guardar. Guardar con un número
    provisorio y corregirlo después deja, aunque sea por un instante, dos comprobantes
    con el mismo número en la misma serie.

    Por eso `alicuotas` se puede pasar explícita: si la venta no está guardada todavía,
    no tiene `alicuotas_iva` que leer.

    Levanta `ErrorEmisionARCA` con el motivo si ARCA rechaza o falta configuración.
    """
    # Import local: `views.py` importa este módulo indirectamente y al revés también.
    from facturacion.views import validar_y_obtener_documento_receptor

    if alicuotas is None:
        alicuotas = _alicuotas_de(venta)
    if not alicuotas:
        raise ErrorEmisionARCA(
            f"El comprobante de {venta.cliente.razon_social} no tiene alícuotas de IVA "
            "calculadas: no se puede solicitar el CAE.")

    if not (venta.tipo and str(venta.tipo.codigo).isdigit()):
        raise ErrorEmisionARCA(
            "El tipo de comprobante no es fiscal: no corresponde solicitar CAE.")

    try:
        doc_tipo, doc_nro, cond_iva_rec = validar_y_obtener_documento_receptor(venta.cliente)
    except Exception as error:
        raise ErrorEmisionARCA(f"Receptor inválido para ARCA: {error}") from error

    cbte_tipo = int(venta.tipo.codigo)

    # Coherencia fiscal: mismas reglas que aplica la carga individual de ventas.
    if cbte_tipo == 1 and cond_iva_rec not in (1, 6):
        raise ErrorEmisionARCA(
            f"{venta.cliente.razon_social}: no se puede emitir Factura A a un Consumidor "
            "Final o Exento. Corresponde Factura B.")
    if cbte_tipo == 6 and cond_iva_rec in (1, 6):
        raise ErrorEmisionARCA(
            f"{venta.cliente.razon_social}: a Responsables Inscriptos y Monotributistas "
            "corresponde Factura A.")

    neto = sum((Decimal(str(a['base_imponible'])) for a in alicuotas), Decimal('0.00'))
    iva = sum((Decimal(str(a['importe_iva'])) for a in alicuotas), Decimal('0.00'))

    datos = {
        'pto_vta': venta.punto,
        'cbte_tipo': cbte_tipo,
        'concepto': 1,
        'doc_tipo': doc_tipo,
        'doc_nro': doc_nro,
        'cbte_fch': venta.fecha.strftime('%Y%m%d'),
        'imp_total': float(neto + iva),
        'imp_tot_conc': 0.0,
        'imp_neto': float(neto),
        'imp_op_ex': 0.0,
        'imp_iva': float(iva),
        'condicion_iva_receptor_id': cond_iva_rec,
        'mon_id': 'DOL' if venta.moneda == 'DOL' else 'PES',
        'mon_cotiz': float(venta.cotizacion) if venta.moneda == 'DOL' else 1.0,
    }

    try:
        resultado = AFIPService(venta.empresa).emitir_comprobante(datos, alicuotas)
    except (ValueError, FileNotFoundError) as error:
        raise ErrorEmisionARCA(f"Configuración ARCA incompleta: {error}") from error

    if not resultado.get('exito'):
        raise ErrorEmisionARCA(
            f"Rechazo ARCA para {venta.cliente.razon_social}: {resultado.get('error')}")

    venta.cae = resultado['cae']
    venta.vto_cae = resultado['vto_cae']
    # El número SIEMPRE sale de ARCA: es la autoridad de la serie fiscal.
    venta.numero = resultado['numero_comprobante']
    venta.cod_qr = resultado.get('cod_qr')
    return venta
