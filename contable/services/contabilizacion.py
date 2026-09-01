from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from datetime import date
from typing import List, Dict, Any

from empresas.models import Empresa, Sucursal
from contable.models import (
    Asiento, AsientoLinea, Cuenta, ParametrosContables,
    LibroIvaCompras, LibroIvaVentas, LibroIvaAlic, RetPercSufrida,
)
from facturacion.models import Venta, Compra, TipoComprobante, ClienteProveedor
from contable.services.asientos import crear_asiento

# =========================================================================
# SERVICIOS CONTABLES DE AUTOMATIZACIÓN - ERP IKIGAI 2
# =========================================================================

@transaction.atomic
def anular_asiento_de_comprobante(asiento_id: int) -> None:
    """
    Marca un asiento contable como ANULADO en la base de datos de forma inmutable.
    
    Siguiendo las mejores prácticas contables y la directiva de negocio,
    bajo ningún concepto se borran registros físicos ni líneas de asiento,
    sino que se marca la cabecera como anulada ('anulado = True') y se registra
    la fecha/hora en que ocurrió la anulación. Esto mantiene la trazabilidad
    histórica de auditoría intacta.
    """
    if not asiento_id:
        return
        
    try:
        # Se bloquea la fila del asiento usando select_for_update para evitar condiciones de carrera
        asiento = Asiento.objects.select_for_update().get(pk=asiento_id)
        if not asiento.anulado:
            asiento.anulado = True
            asiento.fec_anulacion = timezone.localtime()
            asiento.save(update_fields=['anulado', 'fec_anulacion'])
    except Asiento.DoesNotExist:
        # Si el asiento no existe por algún motivo, se ignora de forma segura
        pass


@transaction.atomic
def _limpiar_libro_iva_venta(asiento_id: int) -> None:
    """Borra los registros fiscales de un asiento de venta (para re-contabilización)."""
    LibroIvaVentas.objects.filter(asiento_id=asiento_id).delete()
    LibroIvaAlic.objects.filter(asiento_id=asiento_id, c_v='V').delete()


def _poblar_libro_iva_venta(venta: Venta, asiento: Asiento) -> None:
    """Pobla el subsistema fiscal (Libro IVA Ventas + alícuotas) de una venta con respaldo fiscal (condic 1 o 3)."""
    cuit = ''.join(filter(str.isdigit, (venta.cliente_cuit or venta.cliente.cuit or '')))[:11]
    periodo_val = (venta.periodo or venta.fecha.strftime('%Y%m'))[:6]

    LibroIvaVentas.objects.create(
        empresa=venta.empresa, asiento_id=asiento.asiento_id, fecha=venta.fecha,
        periodo=periodo_val,
        clienteproveedor=venta.cliente, codiva=venta.tipo.codigo if venta.tipo else '001',
        punto=venta.punto, numero=venta.numero, cuit=cuit,
        neto_gravado=venta.neto, exento=(venta.exento or 0), no_gravado=(venta.no_gravado or 0),
        iva_total=venta.iva, otros=(venta.otros or 0), total=venta.total,
        cae=getattr(venta, 'cae', '') or '',
    )

    for item in venta.items.all():
        alic = item.iva_alicuota
        if alic > 0:
            neto_item = item.total / (Decimal("1.00") + (alic / Decimal("100.00")))
            neto_item = neto_item.quantize(Decimal("0.01"))
            iva_item = (item.total - neto_item).quantize(Decimal("0.01"))
        else:
            neto_item = Decimal("0.00")
            iva_item = Decimal("0.00")

        LibroIvaAlic.objects.create(
            asiento_id=asiento.asiento_id, c_v='V', neto=neto_item, alicuota=alic,
            iva=iva_item, computable=iva_item, codiva=venta.tipo.codigo if venta.tipo else '001',
        )


def contabilizar_venta_individual(venta: Venta) -> Asiento:
    """
    Genera de forma atómica el asiento contable de una venta individual.
    """
    if not venta.items.exists():
        return None

    if venta.asiento_id:
        _limpiar_libro_iva_venta(venta.asiento_id)
        anular_asiento_de_comprobante(venta.asiento_id)
        venta.asiento_id = None
        venta.save(update_fields=['asiento_id'])

    # 2. Recuperar parámetros contables de la empresa emisora
    parametros = ParametrosContables.objects.filter(empresa=venta.empresa).first()
    if not parametros:
        raise ValidationError(
            f"No se encontraron Parámetros Contables configurados para la empresa {venta.empresa.nombre}. "
            "Es necesario parametrizar las cuentas por defecto antes de contabilizar."
        )

    # 3. Determinar la cuenta contable de Clientes (imputable al DEBE)
    cta_cliente = None
    if venta.cliente.cta_pat:
        # Si el cliente tiene cuenta específica, la recuperamos validando la pertenencia a la empresa
        cta_cliente = Cuenta.objects.filter(pk=venta.cliente.cta_pat, empresa=venta.empresa, imputable=1).first()
    if not cta_cliente:
        # De lo contrario, usamos la cuenta general de deudores por ventas de la parametrización
        cta_cliente = parametros.cta_clientes_default

    if not cta_cliente:
        raise ValidationError(
            "No se ha definido una cuenta contable de Clientes válida (cta_clientes_default) "
            f"para la empresa {venta.empresa.nombre}."
        )

    # 4. Agrupar los importes del HABER (Ventas de los ítems agrupadas por cuenta del Rubro)
    # Esto da soporte completo al escenario de multi-actividad contable.
    ventas_por_cuenta = {}
    for item in venta.items.select_related('producto__rubro').all():
        # Priorizar la cuenta de ventas del rubro del producto, si no usar la general
        cta_venta_item = None
        if item.producto.rubro and item.producto.rubro.cta_ventas:
            cta_venta_item = item.producto.rubro.cta_ventas
        else:
            cta_venta_item = parametros.cta_ventas

        if not cta_venta_item:
            raise ValidationError(
                f"No se ha configurado la cuenta de Ventas para el rubro '{item.producto.rubro}' "
                "ni una cuenta de Ventas general en los Parámetros Contables."
            )

        # Para asegurar que la suma de netos del asiento coincida con venta.neto,
        # calculamos el neto del ítem: neto = total / (1 + iva_alicuota/100)
        neto_item = item.total / (Decimal("1.00") + (item.iva_alicuota / Decimal("100.00")))
        neto_item = neto_item.quantize(Decimal("0.01"))

        cta_id = cta_venta_item.pk
        if cta_id not in ventas_por_cuenta:
            ventas_por_cuenta[cta_id] = {
                'cuenta': cta_venta_item,
                'monto': Decimal("0.00")
            }
        ventas_por_cuenta[cta_id]['monto'] += neto_item

    # Para evitar diferencias de centavos por redondeos matemáticos entre cabecera y detalle,
    # comparamos el total neto consolidado del comprobante y ajustamos la diferencia en la primera cuenta.
    suma_netos_items = sum(v['monto'] for v in ventas_por_cuenta.values())
    diferencia = venta.neto - suma_netos_items
    if diferencia != 0 and ventas_por_cuenta:
        primera_cta_id = list(ventas_por_cuenta.keys())[0]
        ventas_por_cuenta[primera_cta_id]['monto'] += diferencia

    # 5. Estructurar las líneas del Asiento Contable
    lineas_asiento = []

    # DEBE: Clientes (Importe total del comprobante)
    lineas_asiento.append({
        'cuenta': cta_cliente,
        'debe': venta.total,
        'haber': Decimal("0.00"),
        'leyenda': f"VENTA COMP. {venta.tipo.codigo} {venta.punto:04d}-{venta.numero}",
        'cli_pro': venta.cliente
    })

    # HABER: Ventas por actividad desglosadas
    for cta_data in ventas_por_cuenta.values():
        if cta_data['monto'] > 0:
            lineas_asiento.append({
                'cuenta': cta_data['cuenta'],
                'debe': Decimal("0.00"),
                'haber': cta_data['monto'],
                'leyenda': f"REGISTRO NETO VTA. COMP. {venta.numero}"
            })

    # HABER: IVA Débito Fiscal
    if venta.iva > 0:
        if not parametros.cta_iva_debito:
            raise ValidationError(
                f"No se ha configurado la cuenta de IVA Débito Fiscal (cta_iva_debito) en la empresa {venta.empresa.nombre}."
            )
        lineas_asiento.append({
            'cuenta': parametros.cta_iva_debito,
            'debe': Decimal("0.00"),
            'haber': venta.iva,
            'leyenda': f"IVA DEBITO FISCAL COMP. {venta.numero}"
        })

    # HABER: Percepciones IIBB si corresponden
    if venta.p_iibb > 0:
        if not parametros.cta_ret_iibb:
            raise ValidationError(
                f"No se ha configurado la cuenta de Percepción IIBB (cta_ret_iibb) en la empresa {venta.empresa.nombre}."
            )
        lineas_asiento.append({
            'cuenta': parametros.cta_ret_iibb,
            'debe': Decimal("0.00"),
            'haber': venta.p_iibb,
            'leyenda': f"PERCEP. IIBB VTA COMP. {venta.numero}"
        })

    # HABER: Impuestos Internos / Otros si corresponden
    if (venta.otros or 0) > 0:
        if not parametros.cta_impuestos_internos:
            raise ValidationError(
                f"No se ha configurado la cuenta de Impuestos Internos (cta_impuestos_internos) en la empresa {venta.empresa.nombre}."
            )
        lineas_asiento.append({
            'cuenta': parametros.cta_impuestos_internos,
            'debe': Decimal("0.00"),
            'haber': venta.otros,
            'leyenda': f"IMP. INTERNOS COMP. {venta.numero}"
        })

    # 6. Crear Asiento Contable
    asiento = crear_asiento(
        empresa=venta.empresa,
        fecha=venta.fecha,
        concepto=f"VENTAS COMPROBANTE {venta.tipo.codigo} {venta.punto:04d}-{venta.numero}",
        lineas=lineas_asiento,
        condic=venta.condic,  # FISCAL(1)/NO FISCAL(2) — refleja la condición del comprobante
        modulo=2,  # Ventas
        cli_pro=venta.cliente,
        usuario=venta.usuario
    )

    # 7. Registrar el id del asiento en el comprobante y poblar Libro IVA Ventas si es fiscal
    venta._no_contabilizar = True
    venta.asiento_id = asiento.asiento_id
    venta.save(update_fields=['asiento_id'])
    venta._no_contabilizar = False

    if venta.condic in (1, 3):
        _poblar_libro_iva_venta(venta, asiento)

    return asiento


# Mapeo TRANSITORIO: hoy las percepciones sufridas se capturan en los campos p_* de la
# cabecera de Compra. Cuando exista la grilla de detalle (Fase 4) se reemplaza la FUENTE
# por el detalle capturado, manteniendo esta misma estructura de salida.
# Fallback legacy: campos p_* de la cabecera (compras sin detalle capturado).
_MAPEO_PERCEPCIONES_COMPRA = [
    ('p_iva',  'cta_ret_iva',       'IVA',  'PERCEPCION IVA'),
    ('p_iibb', 'cta_ret_iibb',      'IIBB', 'PERCEPCION IIBB'),
    ('p_gcia', 'cta_ret_ganancias', 'GAN',  'PERCEPCION GANANCIAS'),
    ('p_mun',  'cta_ret_mun',       'MUN',  'PERCEPCION MUNICIPAL'),
]

# Mapeo impuesto → parámetro contable de su cuenta. SIRCREB es un régimen de IIBB;
# TEM/OTRO caen a Impuestos Internos (fallback general).
_CTA_POR_IMPUESTO = {
    'IVA': 'cta_ret_iva', 'GAN': 'cta_ret_ganancias', 'IIBB': 'cta_ret_iibb',
    'SIRCREB': 'cta_ret_iibb', 'SUSS': 'cta_ret_suss', 'MUN': 'cta_ret_mun',
    'TEM': 'cta_impuestos_internos', 'OTRO': 'cta_impuestos_internos',
}

# Impuestos que se acumulan en el campo de cabecera "otros" (no son IVA ni IIBB propios).
_OTROS_BUCKET = {'TEM', 'SIRCREB', 'SUSS', 'MUN', 'OTRO', 'GAN'}


def _cuenta_impuesto(impuesto: str, parametros: ParametrosContables):
    cta = getattr(parametros, _CTA_POR_IMPUESTO.get(impuesto, 'cta_impuestos_internos'), None)
    return cta or parametros.cta_impuestos_internos


def _armar_retperc_compra(compra: Compra, parametros: ParametrosContables) -> List[Dict[str, Any]]:
    """Fuente ÚNICA de retenciones/percepciones sufridas de la compra.
    Alimenta a la vez los renglones del asiento y la tabla RetPercSufrida.
    Fuente: detalle capturado `CompraRetPerc` (con jurisdicción para IIBB CM); si no hay
    detalle, fallback a los campos p_* de la cabecera (compras legacy / sin modal)."""
    items: List[Dict[str, Any]] = []
    if compra.retpercs.exists():
        for rp in compra.retpercs.select_related('jurisdiccion').all():
            importe = Decimal(str(rp.importe or 0))
            if importe == 0:
                continue
            cuenta = _cuenta_impuesto(rp.impuesto, parametros)
            if not cuenta:
                raise ValidationError(
                    f"No se configuró la cuenta contable para {rp.get_impuesto_display()} "
                    f"(ni Impuestos Internos como alternativa) en la empresa {compra.empresa.nombre}."
                )
            jur = f" {rp.jurisdiccion.codigo}" if rp.jurisdiccion_id else ""
            items.append({'impuesto': rp.impuesto, 'tipo': rp.tipo or 'P', 'importe': importe,
                          'cuenta': cuenta, 'leyenda': f"PERCEPCION {rp.get_impuesto_display()}{jur}",
                          'jurisdiccion': rp.jurisdiccion})
        return items
    # Fallback legacy
    for campo, cta_param, impuesto, leyenda in _MAPEO_PERCEPCIONES_COMPRA:
        importe = Decimal(str(getattr(compra, campo, 0) or 0))
        if importe <= 0:
            continue
        cuenta = getattr(parametros, cta_param)
        if not cuenta:
            raise ValidationError(
                f"Se registró un valor de {leyenda} pero no se configuró su cuenta contable "
                f"en la empresa {compra.empresa.nombre}."
            )
        items.append({'impuesto': impuesto, 'tipo': 'P', 'importe': importe,
                      'cuenta': cuenta, 'leyenda': leyenda, 'jurisdiccion': None})
    return items


def _limpiar_libro_iva_compra(asiento_id: int) -> None:
    """Borra los registros fiscales de un asiento (para re-contabilización idempotente)."""
    LibroIvaCompras.objects.filter(asiento_id=asiento_id).delete()
    LibroIvaAlic.objects.filter(asiento_id=asiento_id, c_v='C').delete()
    RetPercSufrida.objects.filter(asiento_id=asiento_id, origen='C').delete()


def _poblar_libro_iva_compra(compra: Compra, asiento: Asiento, retperc_items: List[Dict[str, Any]]) -> None:
    """Pobla el subsistema fiscal (Libro IVA Compras + alícuotas + ret/perc) de una compra con
    respaldo documental válido, o sea condic 1 (Real) o 3 (Ajuste). Vinculado por asiento_id.
    Idempotente: limpiar antes con _limpiar_libro_iva_compra."""
    cuit = ''.join(filter(str.isdigit, (compra.proveedor.cuit or '')))[:11]
    otros_retperc = sum((rp['importe'] for rp in retperc_items), Decimal('0.00'))

    periodo_val = (compra.periodo or compra.fecha.strftime('%Y%m'))[:6]

    LibroIvaCompras.objects.create(
        empresa=compra.empresa, asiento_id=asiento.asiento_id, fecha=compra.fecha,
        periodo=periodo_val,
        clienteproveedor=compra.proveedor, codiva=compra.tipo.codigo,
        punto=compra.punto, numero=compra.numero, cuit=cuit,
        neto_gravado=compra.neto, exento=(compra.exento or 0), no_gravado=(compra.no_gravado or 0),
        iva_total=compra.iva, otros=otros_retperc, total=compra.total,
    )

    # Alícuotas: desglose por alícuota con el prorrateo del descuento global ya aplicado.
    desglose = compra.desglose_alicuotas()
    # Gastos sin ítems: inferir una única alícuota desde neto/iva de cabecera.
    if not desglose and compra.iva and compra.neto:
        alic_inf = (Decimal(str(compra.iva)) / Decimal(str(compra.neto)) * Decimal('100')).quantize(Decimal('0.01'))
        desglose = [{'alicuota': alic_inf, 'neto': Decimal(str(compra.neto)), 'iva': Decimal(str(compra.iva))}]
    for d in desglose:
        LibroIvaAlic.objects.create(
            asiento_id=asiento.asiento_id, c_v='C', neto=d['neto'], alicuota=d['alicuota'],
            # Gastos traen el código de alícuota ARCA cargado a mano; bienes no lo desglosan
            # a ese nivel, así que cae al código de comprobante (comportamiento previo).
            iva=d['iva'], computable=d['iva'], codiva=d.get('codiva') or compra.tipo.codigo,
        )

    # Retenciones/percepciones sufridas. Multi-fila por jurisdicción para IIBB (Convenio Multilateral).
    for rp in retperc_items:
        RetPercSufrida.objects.create(
            empresa=compra.empresa, asiento_id=asiento.asiento_id, origen='C',
            tipo=rp['tipo'], impuesto=rp['impuesto'], jurisdiccion=rp.get('jurisdiccion'),
            base=Decimal('0.00'), alicuota=Decimal('0.000'), importe=rp['importe'],
        )


@transaction.atomic
def contabilizar_compras(compra: Compra) -> Asiento:
    """
    Genera de forma atómica el asiento contable de una compra.
    
    1. Si ya tiene asiento asignado, se anula.
    2. Soporta dos fuentes de cuentas de compras/gastos:
       - Si la compra es manual y el usuario especificó una cuenta en el formulario.
       - Si discrimina productos, se agrupan los importes por la cuenta del Rubro
         de cada producto, usando la de parámetros contables como alternativa.
    3. Registra el IVA Crédito Fiscal, percepciones sufridas y la cuenta de proveedores (Haber).
    """
    # Asiento vigente leído desde la BD (no del objeto en memoria, que puede estar
    # desactualizado cuando la contabilización se dispara de forma reentrante por señales).
    asiento_vigente = Compra.objects.filter(pk=compra.pk).values_list('asiento_id', flat=True).first()
    if asiento_vigente:
        _limpiar_libro_iva_compra(asiento_vigente)
        anular_asiento_de_comprobante(asiento_vigente)
        # El reset debe ir con el guard: sin él, este save re-dispara la señal y genera
        # una contabilización reentrante que deja asientos activos huérfanos (doble conteo).
        compra._no_contabilizar = True
        compra.asiento_id = None
        compra.save(update_fields=['asiento_id'])
        compra._no_contabilizar = False

    parametros = ParametrosContables.objects.filter(empresa=compra.empresa).first()
    if not parametros:
        raise ValidationError(
            f"No se encontraron Parámetros Contables configurados para la empresa {compra.empresa.nombre}."
        )

    # Determinar la cuenta contable de Proveedores (imputable al HABER)
    cta_proveedor = None
    if compra.proveedor.cta_pat:
        cta_proveedor = Cuenta.objects.filter(pk=compra.proveedor.cta_pat, empresa=compra.empresa, imputable=1).first()
    if not cta_proveedor:
        cta_proveedor = parametros.cta_proveedores_default

    if not cta_proveedor:
        raise ValidationError(
            "No se ha definido una cuenta contable de Proveedores válida (cta_proveedores_default) "
            f"para la empresa {compra.empresa.nombre}."
        )

    # Agrupar los netos del DEBE por cuenta de compras (por rubro o general)
    compras_por_cuenta = {}
    
    # Verificamos si la compra tiene ítems discriminados
    items = compra.items.select_related('producto__rubro').all()
    if items.exists():
        # Escenario A: Carga discriminada por producto
        for item in items:
            cta_compra_item = None
            if item.producto.rubro and item.producto.rubro.cta_compras:
                cta_compra_item = item.producto.rubro.cta_compras
            else:
                cta_compra_item = parametros.cta_compras

            if not cta_compra_item:
                raise ValidationError(
                    f"No se ha configurado la cuenta de Compras para el rubro '{item.producto.rubro}' "
                    "ni una cuenta de Compras general en los Parámetros Contables."
                )

            # El total del ítem es el NETO de la línea (sin IVA), por convención de carga.
            neto_item = Decimal(str(item.total))

            cta_id = cta_compra_item.pk
            if cta_id not in compras_por_cuenta:
                compras_por_cuenta[cta_id] = {
                    'cuenta': cta_compra_item,
                    'monto': Decimal("0.00")
                }
            compras_por_cuenta[cta_id]['monto'] += neto_item
            
        # Cuadrar centavos: el DEBE de Mercaderías va al SUBTOTAL (antes del descuento global).
        suma_netos_items = sum(c['monto'] for c in compras_por_cuenta.values())
        diferencia = (compra.subtotal or compra.neto) - suma_netos_items
        if diferencia != 0 and compras_por_cuenta:
            primera_cta_id = list(compras_por_cuenta.keys())[0]
            compras_por_cuenta[primera_cta_id]['monto'] += diferencia
    else:
        # Escenario B: sin ítems (GASTO o carga global). DEBE a la cuenta de imputación del
        # comprobante (gasto: sugerida cta_res del proveedor) o, en su defecto, a Compras general.
        cta_debe = None
        if compra.cta_imputacion:
            cta_debe = Cuenta.objects.filter(pk=compra.cta_imputacion, empresa=compra.empresa, imputable=1).first()
        if not cta_debe:
            cta_debe = parametros.cta_compras
        if not cta_debe:
            raise ValidationError(
                "No se definió una cuenta de imputación (gasto) ni la cuenta de Compras general "
                f"(cta_compras) en los Parámetros Contables de {compra.empresa.nombre}."
            )
        compras_por_cuenta[cta_debe.pk] = {
            'cuenta': cta_debe,
            'monto': (compra.subtotal or compra.neto)
        }

    # No Gravado + Exento van al DEBE de la imputación (gasto) / primera cuenta de compras (bienes),
    # junto al neto. Sin esto, el HABER (proveedor por el TOTAL, que los incluye) queda descalzado.
    extra_debe = Decimal(str(compra.no_gravado or 0)) + Decimal(str(compra.exento or 0))
    if extra_debe != 0 and compras_por_cuenta:
        primera_cta_id = list(compras_por_cuenta.keys())[0]
        compras_por_cuenta[primera_cta_id]['monto'] += extra_debe

    # Estructurar las líneas del Asiento Contable
    lineas_asiento = []

    # HABER: Proveedores (Importe total del comprobante)
    lineas_asiento.append({
        'cuenta': cta_proveedor,
        'debe': Decimal("0.00"),
        'haber': compra.total,
        'leyenda': f"COMPRA COMP. {compra.tipo.codigo} {compra.punto:04d}-{compra.numero}",
        'cli_pro': compra.proveedor
    })

    # DEBE: Compras desglosadas por cuenta de rubro / general
    for cta_data in compras_por_cuenta.values():
        if cta_data['monto'] != 0:
            lineas_asiento.append({
                'cuenta': cta_data['cuenta'],
                'debe': cta_data['monto'],
                'haber': Decimal("0.00"),
                'leyenda': f"REGISTRO GASTO COMP. {compra.numero}"
            })

    # DEBE: IVA Crédito Fiscal
    if compra.iva != 0:
        if not parametros.cta_iva_credito:
            raise ValidationError(
                f"No se ha configurado la cuenta de IVA Crédito Fiscal (cta_iva_credito) en la empresa {compra.empresa.nombre}."
            )
        lineas_asiento.append({
            'cuenta': parametros.cta_iva_credito,
            'debe': compra.iva,
            'haber': Decimal("0.00"),
            'leyenda': f"IVA CREDITO FISCAL COMP. {compra.numero}"
        })

    # DEBE: Retenciones / Percepciones Sufridas — fuente ÚNICA que alimenta asiento + Libro IVA
    retperc_items = _armar_retperc_compra(compra, parametros)
    for rp in retperc_items:
        lineas_asiento.append({
            'cuenta': rp['cuenta'],
            'debe': rp['importe'],
            'haber': Decimal("0.00"),
            'leyenda': f"{rp['leyenda']} COMP. {compra.numero}"
        })

    # DEBE: Impuestos Internos / Otros — SOLO el resto de "otros" no representado en el
    # detalle de ret/perc (impuestos del bucket de "otros": TEM/SIRCREB/SUSS/MUN/OTRO/GAN).
    # Si "otros" se desglosó por el modal, esas filas ya están en las líneas de percepción
    # de arriba; emitir además la línea completa duplicaría el importe en el DEBE.
    otros_en_retperc = sum(
        (rp['importe'] for rp in retperc_items if rp['impuesto'] in _OTROS_BUCKET),
        Decimal('0.00'),
    )
    resto_internos = Decimal(str(compra.otros or 0)) - otros_en_retperc
    if resto_internos != 0:
        if not parametros.cta_impuestos_internos:
            raise ValidationError(
                f"No se ha configurado la cuenta de Impuestos Internos (cta_impuestos_internos) en la empresa {compra.empresa.nombre}."
            )
        lineas_asiento.append({
            'cuenta': parametros.cta_impuestos_internos,
            'debe': resto_internos,
            'haber': Decimal("0.00"),
            'leyenda': f"IMP. INTERNOS COMP. {compra.numero}"
        })

    # HABER: Descuentos Obtenidos (descuento global de la factura — Opción 2).
    # Mercaderías va al SUBTOTAL (DEBE) y el descuento se reconoce como recupero acá.
    if (compra.descuento or 0) != 0:
        if not parametros.cta_descuentos_obtenidos:
            raise ValidationError(
                "Se registró un descuento global pero no se configuró la cuenta de Descuentos "
                f"Obtenidos (cta_descuentos_obtenidos) en la empresa {compra.empresa.nombre}."
            )
        lineas_asiento.append({
            'cuenta': parametros.cta_descuentos_obtenidos,
            'debe': Decimal("0.00"),
            'haber': compra.descuento,
            'leyenda': f"DESCUENTO OBTENIDO COMP. {compra.numero}"
        })

    # Normalización débito/crédito: reubica cada línea según el signo de su neto.
    # Esto INVIERTE automáticamente las Notas de Crédito (importes negativos) — el proveedor
    # pasa al DEBE y compras/IVA al HABER — sin lógica especial por tipo de comprobante.
    for l in lineas_asiento:
        neto = l['debe'] - l['haber']
        if neto >= 0:
            l['debe'], l['haber'] = neto, Decimal("0.00")
        else:
            l['debe'], l['haber'] = Decimal("0.00"), -neto

    # Crear Asiento Contable
    asiento = crear_asiento(
        empresa=compra.empresa,
        fecha=compra.fecha,
        concepto=f"COMPRAS PROVEEDOR {compra.proveedor.razon_social} COMP. {compra.tipo.codigo} {compra.punto:04d}-{compra.numero}",
        lineas=lineas_asiento,
        condic=compra.condic,  # FISCAL(1)/NO FISCAL(2) — refleja la condición del comprobante
        modulo=5,  # Compras
        cli_pro=compra.proveedor,
        usuario=compra.usuario
    )

    # Evitamos la recursión infinita en las señales marcando la instancia
    compra._no_contabilizar = True
    compra.asiento_id = asiento.asiento_id
    compra.save(update_fields=['asiento_id'])
    compra._no_contabilizar = False

    # Subsistema fiscal: alimentan el Libro IVA los comprobantes con respaldo documental válido,
    # o sea condic 1 (Real) y 3 (Ajuste). El 3 es una factura a nombre de la empresa que el dueño
    # pagó con fondos propios: no es gasto de la empresa —queda fuera del análisis de gestión—
    # pero la factura le pertenece y se computa en las DDJJ de IVA y Ganancias.
    # El 2 (sin respaldo) y el 4 (ajuste de auditoría) quedan excluidos de los reportes impositivos.
    if compra.condic in (1, 3):
        _poblar_libro_iva_compra(compra, asiento, retperc_items)

    return asiento


def _revertir_circuito_oc_de_compra(compra: Compra) -> None:
    """Deshace el circuito OC de una factura (Plan 028) antes de su baja física:
    - Revierte cantidad_facturada de las líneas de OC (borra CompraOCImputacion).
    - Borra las Recepciones que la factura generó (factura-como-remito): revierte su stock
      (por la señal post_delete de RecepcionItem) y su cantidad_recibida en las OC.
    - Recalcula los estados de las OC afectadas (reabre pendientes).
    Debe ejecutarse dentro de la transacción de la baja."""
    from facturacion.models import (
        CompraOCImputacion, RecepcionImputacion, Recepcion, OrdenCompra,
    )
    ocs = set()

    # a) Revertir facturación imputada.
    imps = CompraOCImputacion.objects.filter(compra_item__compra=compra).select_related('orden_item')
    for imp in imps:
        oi = imp.orden_item
        oi.cantidad_facturada = oi.cantidad_facturada - imp.cantidad
        oi.save(update_fields=['cantidad_facturada'])
        ocs.add(oi.orden_id)
    imps.delete()

    # b) Recepciones generadas por esta factura.
    for rec in Recepcion.objects.filter(generada_por_factura=compra):
        for rimp in RecepcionImputacion.objects.filter(
                recepcion_item__recepcion=rec).select_related('orden_item'):
            if rimp.orden_item_id:
                oi = rimp.orden_item
                oi.cantidad_recibida = oi.cantidad_recibida - rimp.cantidad
                oi.save(update_fields=['cantidad_recibida'])
                ocs.add(oi.orden_id)
        RecepcionImputacion.objects.filter(recepcion_item__recepcion=rec).delete()
        rec.items.all().delete()   # post_delete de RecepcionItem revierte el stock (ENTRADA)
        rec.delete()

    # c) Recalcular estados de las OC afectadas.
    for oc_id in ocs:
        OrdenCompra.objects.get(pk=oc_id).recalcular_estados()


@transaction.atomic
def dar_de_baja_compra(compra: Compra) -> None:
    """Baja FÍSICA de una compra cargada con error: revierte stock y borra el comprobante
    completo (ítems, asiento, líneas y registros fiscales — todo vinculado por asiento_id)
    SIN dejar contra-asientos ni huérfanos. Es para recargar limpio, no una anulación fiscal
    con trazabilidad. El borrado se hace con _raw_delete para no disparar las señales (que
    re-contabilizarían la compra moribunda ni revertirían stock por duplicado)."""
    from facturacion.models import CompraItem, CompraAlicuota, CompraRetPerc
    from productos.models import StockSucursal
    from contable.services.saldos import recalcular_saldo_cliente_proveedor

    proveedor_id = compra.proveedor_id
    aid = compra.asiento_id
    signo = compra.tipo.signo if compra.tipo else 1

    # 1. Revertir stock (inverso EXACTO de lo que aplicó la carga; solo bienes de cambio
    #    sin remito vinculado — con remito el stock lo movió el remito, no esta factura).
    #    En el circuito OC (gestion_stock_por_recepcion) la factura tampoco movió stock:
    #    lo movió la Recepción (remito o la autogenerada), que se revierte en el paso 1.bis.
    if not compra.id_fac_rem and not compra.gestion_stock_por_recepcion:
        for item in compra.items.select_related('producto'):
            try:
                stk = StockSucursal.objects.select_for_update().get(
                    producto=item.producto, sucursal=compra.sucursal
                )
            except StockSucursal.DoesNotExist:
                continue
            stk.cantidad = stk.cantidad - int(item.cantidad) * signo
            stk.save(update_fields=['cantidad'])

    # 1.bis Circuito OC (Plan 028): revertir imputaciones de facturación y las recepciones
    #    que esta factura generó (factura-como-remito), reabriendo pendientes de las OC.
    _revertir_circuito_oc_de_compra(compra)

    # 2. Borrar registros fiscales + asientos + líneas. Incluye el asiento vigente y los
    #    intermedios anulados que dejó la re-contabilización (mismo comprobante en el concepto),
    #    para no ensuciar la contabilidad con asientos de algo que ya no existe.
    asiento_ids = set()
    if aid:
        asiento_ids.add(aid)
    if compra.tipo:
        marca = f"COMP. {compra.tipo.codigo} {compra.punto:04d}-{compra.numero}"
        asiento_ids.update(
            Asiento.objects.filter(
                empresa=compra.empresa, modulo=5, cli_pro_id=compra.proveedor_id,
                concepto__contains=marca,
            ).values_list('asiento_id', flat=True)
        )
    for a_id in asiento_ids:
        _limpiar_libro_iva_compra(a_id)
        AsientoLinea.objects.filter(asiento_id=a_id).delete()
        Asiento.objects.filter(asiento_id=a_id).delete()

    # 3. Borrar la vista materializada de movimientos del comprobante (FK a Compra).
    from facturacion.models import Movimiento
    Movimiento.objects.filter(compra=compra).delete()

    # 4. Borrar ítems, alícuotas, ret/perc y compra SIN disparar señales.
    CompraItem.objects.filter(compra=compra)._raw_delete(using=CompraItem.objects.db)
    CompraAlicuota.objects.filter(compra=compra)._raw_delete(using=CompraAlicuota.objects.db)
    CompraRetPerc.objects.filter(compra=compra)._raw_delete(using=CompraRetPerc.objects.db)
    Compra.objects.filter(pk=compra.pk)._raw_delete(using=Compra.objects.db)

    # 5. Recalcular el saldo del proveedor.
    recalcular_saldo_cliente_proveedor(proveedor_id)


@transaction.atomic
def consolidar_ventas_diarias(empresa: Empresa, fecha: date, sucursal: Sucursal) -> Asiento:
    """
    Agrupa y consolida todas las ventas del día para una sucursal en un único Asiento Resumen Diario.
    
    Este método es el núcleo del diseño para alta transaccionalidad (ej. supermercados con miles
    de tickets diarios). En lugar de escribir miles de asientos, se genera un único asiento contable
    consolidando los totales y asociando dicho asiento masivamente a todas las ventas procesadas.
    """
    # 1. Recuperar todas las ventas activas de la fecha y sucursal sin asiento contable asignado
    ventas = Venta.objects.select_for_update().filter(
        empresa=empresa,
        sucursal=sucursal,
        fecha=fecha,
        estado=0,  # Solo ventas activas (no anuladas)
        asiento_id__isnull=True
    ).select_related('cliente')

    if not ventas.exists():
        return None

    parametros = ParametrosContables.objects.filter(empresa=empresa).first()
    if not parametros:
        raise ValidationError(
            f"No se encontraron Parámetros Contables configurados para la empresa {empresa.nombre}."
        )

    # Cuentas Contables y Acumuladores
    debe_caja_bancos = {}       # Agrupado por cuenta de cobro del cliente/empresa (Debe)
    haber_ventas_rubros = {}    # Agrupado por cuenta contable de ventas por rubro (Haber)
    
    total_iva = Decimal("0.00")
    total_iibb = Decimal("0.00")
    total_otros = Decimal("0.00")
    total_general = Decimal("0.00")

    # 2. Consolidar importes recorriendo las facturas y sus ítems
    for venta in ventas:
        total_general += venta.total
        total_iva += venta.iva
        total_iibb += venta.p_iibb
        total_otros += (venta.otros or 0)

        # A. Determinar e imputar cuenta de cobro / cliente (DEBE)
        cta_cliente = None
        if venta.cliente.cta_pat:
            cta_cliente = Cuenta.objects.filter(pk=venta.cliente.cta_pat, empresa=empresa, imputable=1).first()
        if not cta_cliente:
            cta_cliente = parametros.cta_clientes_default

        if not cta_cliente:
            raise ValidationError(
                "No se ha definido la cuenta de Clientes (cta_clientes_default) en la parametrización."
            )

        cta_cli_id = cta_cliente.pk
        if cta_cli_id not in debe_caja_bancos:
            debe_caja_bancos[cta_cli_id] = {
                'cuenta': cta_cliente,
                'monto': Decimal("0.00")
            }
        debe_caja_bancos[cta_cli_id]['monto'] += venta.total

        # B. Imputar neto a cuentas de ventas de rubros (HABER)
        for item in venta.items.select_related('producto__rubro').all():
            cta_venta_item = None
            if item.producto.rubro and item.producto.rubro.cta_ventas:
                cta_venta_item = item.producto.rubro.cta_ventas
            else:
                cta_venta_item = parametros.cta_ventas

            if not cta_venta_item:
                raise ValidationError(
                    f"No se ha configurado la cuenta de Ventas para el rubro '{item.producto.rubro}' "
                    "ni una cuenta de Ventas general en los Parámetros Contables."
                )

            neto_item = item.total / (Decimal("1.00") + (item.iva_alicuota / Decimal("100.00")))
            neto_item = neto_item.quantize(Decimal("0.01"))

            cta_id = cta_venta_item.pk
            if cta_id not in haber_ventas_rubros:
                haber_ventas_rubros[cta_id] = {
                    'cuenta': cta_venta_item,
                    'monto': Decimal("0.00")
                }
            haber_ventas_rubros[cta_id]['monto'] += neto_item

    # 3. Cuadrar centavos de neto consolidado frente a la suma matemática de los ítems
    suma_total_neto = sum(v.neto for v in ventas)
    suma_netos_desglosados = sum(h['monto'] for h in haber_ventas_rubros.values())
    diferencia_neto = suma_total_neto - suma_netos_desglosados
    if diferencia_neto != 0 and haber_ventas_rubros:
        primera_cta_id = list(haber_ventas_rubros.keys())[0]
        haber_ventas_rubros[primera_cta_id]['monto'] += diferencia_neto

    # 4. Estructurar líneas de asiento
    lineas_asiento = []

    # DEBE: Total consolidado imputado a cuentas de clientes / cajas
    for cta_data in debe_caja_bancos.values():
        if cta_data['monto'] > 0:
            lineas_asiento.append({
                'cuenta': cta_data['cuenta'],
                'debe': cta_data['monto'],
                'haber': Decimal("0.00"),
                'leyenda': f"RESUMEN DIARIO VENTAS SUC. {sucursal.nombre} - FECHA {fecha.strftime('%d/%m/%Y')}"
            })

    # HABER: Ventas por rubro/actividad
    for cta_data in haber_ventas_rubros.values():
        if cta_data['monto'] > 0:
            lineas_asiento.append({
                'cuenta': cta_data['cuenta'],
                'debe': Decimal("0.00"),
                'haber': cta_data['monto'],
                'leyenda': f"VENTAS DIARIAS CONS. SUC. {sucursal.nombre}"
            })

    # HABER: IVA Débito Fiscal
    if total_iva > 0:
        if not parametros.cta_iva_debito:
            raise ValidationError("No se configuró la cuenta de IVA Débito Fiscal (cta_iva_debito).")
        lineas_asiento.append({
            'cuenta': parametros.cta_iva_debito,
            'debe': Decimal("0.00"),
            'haber': total_iva,
            'leyenda': f"IVA DEBITO FISCAL DIARIO SUC. {sucursal.nombre}"
        })

    # HABER: Percepciones IIBB
    if total_iibb > 0:
        if not parametros.cta_ret_iibb:
            raise ValidationError("No se configuró la cuenta de Percepción IIBB (cta_ret_iibb).")
        lineas_asiento.append({
            'cuenta': parametros.cta_ret_iibb,
            'debe': Decimal("0.00"),
            'haber': total_iibb,
            'leyenda': f"PERCEP. IIBB DIARIAS SUC. {sucursal.nombre}"
        })

    # HABER: Impuestos Internos / Otros
    if total_otros > 0:
        if not parametros.cta_impuestos_internos:
            raise ValidationError("No se configuró la cuenta de Impuestos Internos (cta_impuestos_internos).")
        lineas_asiento.append({
            'cuenta': parametros.cta_impuestos_internos,
            'debe': Decimal("0.00"),
            'haber': total_otros,
            'leyenda': f"IMP. INTERNOS DIARIOS SUC. {sucursal.nombre}"
        })

    # 5. Crear Asiento Único Consolidado
    # Tomamos el usuario de la primera venta para registrar el creador
    primer_usuario = ventas.first().usuario
    asiento = crear_asiento(
        empresa=empresa,
        fecha=fecha,
        concepto=f"ASIENTO RESUMEN DIARIO - SUC. {sucursal.nombre.upper()} - {fecha.strftime('%d/%m/%Y')}",
        lineas=lineas_asiento,
        condic=1,  # Resumen general
        modulo=2,  # Ventas
        usuario=primer_usuario
    )

    # 6. Vincular de forma masiva el ID del asiento a todas las ventas procesadas
    ventas.update(asiento_id=asiento.asiento_id)

    return asiento

@transaction.atomic
def cuenta_efectivo_de_caja(caja, parametros, en_divisa=False):
    """La cuenta del EFECTIVO sale de la CAJA donde está, no del medio de pago (Plan 077 §E).

    Un cheque es un cheque entre donde entre; el efectivo vive en un cajón concreto. Dicho de
    otra forma, y es el criterio que lo ordena todo: **la cuenta la define quién tiene que
    rendir la plata**. Un recibo hecho en el mostrador lo rinde el cajero, así que está en
    `cta_caja_mostrador`; el mismo recibo hecho en Tesorería ya está en Tesorería.

    Antes de esto el efectivo tenía TRES destinos según por dónde entrara —`cta_caja` en la
    venta de mostrador, la cuenta del medio de pago en el recibo, `cta_caja_mostrador` en el
    retiro—, de modo que la cuenta del mostrador sólo recibía haber y nunca debe: no podía
    cerrar en cero ni en el fondo fijo, se volvía cada vez más acreedora.

    Devuelve `None` cuando la caja es de mostrador o tesorería y su parámetro no está
    cargado: es el estado heredado de las empresas que nunca lo configuraron, y romperles la
    contabilización sería peor que dejar la cadena de resolución seguir como hasta hoy. Para
    las cajas de DISTRIBUCIÓN sí lanza error, porque sustituir esa cuenta en silencio
    mezclaría la plata de la calle con la del cajero, que es justo lo que vino a separar.
    """
    if not caja:
        return None

    if caja.tipo in ('R', 'D'):
        if not parametros.cta_caja_reparto:
            raise ValidationError(
                "Falta configurar la 'Cta. Caja de Reparto (Distribución)' en Parámetros "
                "Contables: es la cuenta del efectivo que llevan los repartidores y los "
                "vendedores, y va separada de la caja mostrador porque el responsable es otro.")
        # El reparto cobra en pesos: sin cuenta propia de dólares, la divisa sigue su curso
        # por la parametrización general.
        return None if en_divisa else parametros.cta_caja_reparto

    if caja.tipo == 'M':
        return (parametros.cta_caja_mostrador_dolares if en_divisa
                else parametros.cta_caja_mostrador)
    if caja.tipo == 'T':
        return (parametros.cta_caja_central_dolares if en_divisa
                else parametros.cta_caja_central)
    return None


def _cuenta_medio_cobro(detalle, parametros, es_pago=False):
    """Cuenta contable de la contrapartida de un medio de cobro/pago.

    `es_pago=True` cuando se contabiliza una Orden de Pago (el medio SALE) y False cuando se
    contabiliza un Recibo (el medio ENTRA). Sólo cambia el sentido de las retenciones, que
    según quién sea el agente son una deuda propia o un crédito fiscal.

    Orden de resolución, del dato más específico al más general:
      1. La cuenta de la cuenta bancaria concreta, si el movimiento fue por transferencia o cheque propio.
      2. EFECTIVO: la cuenta de la CAJA donde entró o de la que salió (Plan 077 §E). Va antes
         que el medio de pago porque el mismo "Efectivo" vale para todas las cajas y sólo la
         caja sabe de quién es esa plata. `DIG` (billetera digital) no entra acá: no vive en
         un cajón que alguien tenga que rendir.
      3. La cuenta de dólares, cuando el detalle trae importe en moneda extranjera (el medio de pago
         suele apuntar a la caja en pesos, así que acá manda la parametrización de divisas).
      4. La cuenta configurada en el propio Medio de Pago.
      5. La cuenta general de la categoría, según ParametrosContables.
    """
    medio = detalle.medio_pago
    en_divisa = (detalle.importe_moneda_extranjera or Decimal("0.00")) > 0

    transaccion = detalle.transacciones_bancarias.first()
    if transaccion and transaccion.cuenta_bancaria:
        cta_bancaria = transaccion.cuenta_bancaria
        # CHEQUE PROPIO: no toca el banco todavía (Plan 035 §1.6). Al librarlo se genera un
        # pasivo "Cheques Emitidos a Pagar"; recién la conciliación, cuando el banco debita de
        # verdad, cancela ese pasivo contra la cuenta bancaria. Diferidos y al día, igual.
        if transaccion.tipo_transaccion == 'CP':
            if not cta_bancaria.cuenta_contable_cheques:
                raise ValidationError(
                    f"Falta configurar la 'Cta. Contable Cheques Emitidos' en la cuenta "
                    f"bancaria {cta_bancaria.banco} - {cta_bancaria.cta_numero}."
                )
            return cta_bancaria.cuenta_contable_cheques
        # Transferencias (emitidas o recibidas): el débito/crédito es inmediato.
        if cta_bancaria.cuenta_contable:
            return cta_bancaria.cuenta_contable

    if medio.categoria == 'EFE':
        cuenta_caja = cuenta_efectivo_de_caja(
            detalle.movimiento_caja.sesion.caja, parametros, en_divisa=en_divisa)
        if cuenta_caja:
            return cuenta_caja

    if en_divisa:
        cuenta = parametros.cta_caja_central_dolares or parametros.cta_dolar
        if cuenta:
            return cuenta

    if medio.cuenta_contable:
        return medio.cuenta_contable

    por_categoria = {
        'EFE': parametros.cta_caja_central or parametros.cta_caja,
        'CHQ': parametros.cta_valores_cartera,
        'TAR': parametros.cta_tarjetas_a_cobrar,
        'DIG': parametros.cta_caja_central or parametros.cta_caja,
        # Retenciones. El sentido depende de quién es el agente de retención:
        #   - En una ORDEN DE PAGO la practicamos nosotros -> DEUDA con el fisco (practicada).
        #   - En un RECIBO nos la practica el cliente      -> CRÉDITO fiscal (sufrida).
        # Sin este fallback el comprobante explotaba si el Medio de Pago no tenía cuenta
        # contable cargada a mano.
        'RET': (parametros.cta_ret_practicada_ganancias if es_pago
                else parametros.cta_ret_ganancias),
    }
    return por_categoria.get(medio.categoria)


def contabilizar_recibo(recibo) -> Asiento:
    """Genera el asiento contable de un Recibo, con lógica bimonetaria.

    DEBE : los medios de cobro recibidos (caja, dólares, banco, valores en cartera, tarjetas...).
    HABER: - Cobranza a Cliente  -> la cuenta patrimonial del cliente.
           - Recibo Simple       -> la/s cuenta/s elegidas en "Imputación Contable (Haber)".
    """
    from tesoreria.models import MovimientoCajaDetalle
    # Si ya tenía asiento, lo anula
    if getattr(recibo, 'asiento_id', None):
        anular_asiento_de_comprobante(recibo.asiento_id)
        recibo.asiento_id = None
        recibo.save(update_fields=['asiento_id'])

    parametros = ParametrosContables.objects.filter(empresa=recibo.empresa).first()
    if not parametros:
        raise ValidationError(f"No se encontraron Parámetros Contables para la empresa {recibo.empresa.nombre}.")

    lineas_asiento = []
    total_debe = Decimal("0.00")
    agrupado_debe = {}

    # 1. DEBE: los medios de cobro recibidos (caja, dólares, banco, valores, tarjetas,
    #    retenciones). Se leen de los detalles del Movimiento de Caja del recibo, que es donde
    #    queda registrado el desglose por medio de pago con sus satélites.
    detalles = MovimientoCajaDetalle.objects.filter(
        movimiento_caja__recibo=recibo
    ).select_related('medio_pago__cuenta_contable',
                    'movimiento_caja__sesion__caja').prefetch_related(
        'transacciones_bancarias__cuenta_bancaria__cuenta_contable'
    ).order_by('id')

    # Se agrupan por cuenta: si entraron cinco cheques de terceros, el asiento lleva UNA sola línea
    # contra Valores en Cartera por la suma. El detalle individual de cada cheque queda en
    # `tesoreria_valor_terceros`, que es donde corresponde seguirlos uno por uno.
    for detalle in detalles:
        cuenta_debe = _cuenta_medio_cobro(detalle, parametros)
        if not cuenta_debe:
            raise ValidationError(
                f"Falta configurar la cuenta contable del medio de pago "
                f"'{detalle.medio_pago.nombre}' (o la cuenta general de su categoría)."
            )

        # `detalle.importe` YA viene pesificado por la vista que registra el recibo, así que no se
        # vuelve a multiplicar por la cotización: en `cble_asiento_mov` el debe y el haber van
        # SIEMPRE en pesos, y la divisa original queda en `divisa` + `cotizacion` + `*_divisa`.
        importe_ars = detalle.importe
        en_divisa = detalle.importe_moneda_extranjera or Decimal("0.00")
        divisa = 'DOL' if en_divisa > 0 else 'PES'
        cotizacion = detalle.cotizacion or Decimal("1.0")

        # La clave incluye divisa y cotización para no fusionar cobros valuados a distinto tipo.
        clave = (cuenta_debe.id, divisa, cotizacion)
        if clave in agrupado_debe:
            agrupado_debe[clave]['debe'] += importe_ars
            agrupado_debe[clave]['debe_divisa'] += en_divisa
            agrupado_debe[clave]['medios'].add(detalle.medio_pago.nombre)
        else:
            agrupado_debe[clave] = {
                'cuenta': cuenta_debe,
                'debe': importe_ars,
                'haber': 0,
                'divisa': divisa,
                'cotizacion': cotizacion,
                'debe_divisa': en_divisa,
                'haber_divisa': 0,
                'cli_pro': recibo.cliente,
                'medios': {detalle.medio_pago.nombre},
            }
        total_debe += importe_ars

    for linea in agrupado_debe.values():
        medios = ", ".join(sorted(linea.pop('medios')))
        linea['leyenda'] = f"Recibo Nro {recibo.numero} - {medios}"
        lineas_asiento.append(linea)

    # 2. HABER: Cuentas de Imputación (Cobranza a Cliente vs Recibo Simple)
    total_haber = Decimal("0.00")
    
    if recibo.tipo == 'C':
        # Cobranza a Clientes
        cuenta_haber = None
        if recibo.cliente and recibo.cliente.cta_pat:
            cuenta_haber = Cuenta.objects.filter(pk=recibo.cliente.cta_pat, empresa=recibo.empresa, imputable=1).first()
        if not cuenta_haber:
            cuenta_haber = parametros.cta_clientes_default
        
        if not cuenta_haber:
            raise ValidationError("Falta configurar la cuenta patrimonial del cliente o la cuenta general de clientes.")
        
        # El haber cancela exactamente el total de los medios de cobro (siempre en PESOS), de modo
        # que el asiento cierre sin residuos de redondeo. Si el recibo es en moneda extranjera, la
        # divisa y su cotización quedan registradas en las columnas bimonetarias.
        es_divisa = recibo.moneda and recibo.moneda != 'PES' and recibo.cotizacion
        haber_divisa = (total_debe / recibo.cotizacion).quantize(Decimal("0.01")) if es_divisa else 0

        lineas_asiento.append({
            'cuenta': cuenta_haber,
            'debe': 0,
            'haber': total_debe,
            'leyenda': f"Cobranza Recibo Nro {recibo.numero}",
            'divisa': recibo.moneda if es_divisa else 'PES',
            'cotizacion': recibo.cotizacion if es_divisa else Decimal("1.0"),
            'debe_divisa': 0,
            'haber_divisa': haber_divisa,
            'cli_pro': recibo.cliente
        })
        total_haber += total_debe

    else:
        # Recibo Simple: una línea por cada cuenta elegida en "Imputación Contable (Haber)".
        # Los importes de las imputaciones YA vienen en pesos (el formulario valida que su suma
        # coincida con el total de valores, que también está pesificado), así que NO se vuelven a
        # multiplicar por la cotización.
        imputaciones = recibo.imputaciones_simples.select_related('cuenta_contable').all()
        for imp in imputaciones:
            lineas_asiento.append({
                'cuenta': imp.cuenta_contable,
                'debe': 0,
                'haber': imp.importe,
                'leyenda': imp.leyenda or f"Recibo Simple Nro {recibo.numero}",
                'divisa': 'PES',
                'cotizacion': Decimal("1.0"),
                'debe_divisa': 0,
                'haber_divisa': 0,
                'cli_pro': recibo.cliente
            })
            total_haber += imp.importe

    # Si no hay importes, no hay nada que contabilizar.
    if total_debe <= 0:
        return None

    # Balance: se admite una diferencia de centavos por redondeo de la conversión de divisas y se
    # absorbe en la última línea del haber. Cualquier desvío mayor es un error de carga real.
    diferencia = total_debe - total_haber
    if diferencia != 0:
        if abs(diferencia) > Decimal("0.05"):
            raise ValidationError(
                f"Recibo {recibo.numero} desbalanceado: Debe {total_debe} vs Haber {total_haber}"
            )
        lineas_asiento[-1]['haber'] += diferencia
        total_haber += diferencia

    # 3. Crear el Asiento
    razon_social = recibo.cliente.razon_social[:50] if recibo.cliente else "N/A"
    concepto = f"RC {recibo.numero} - {razon_social}"

    asiento = crear_asiento(
        empresa=recibo.empresa,
        fecha=recibo.fecha,
        concepto=concepto,
        lineas=lineas_asiento,
        condic=recibo.condic,
        modulo=4, # Modulo Tesorería
        cli_pro=recibo.cliente,
        ejercicio=recibo.ejercicio,
        usuario=recibo.creado_por
    )

    # El asiento queda vinculado a la caja de tesorería del recibo: así aparece en la Caja Diaria
    # y el asiento_id sirve de nexo entre el comprobante, la caja y la contabilidad.
    if recibo.sesion_caja_id:
        asiento.sesion_caja_id = recibo.sesion_caja_id
        asiento.save(update_fields=['sesion_caja'])

    recibo.asiento_id = asiento.asiento_id
    recibo.save(update_fields=['asiento_id'])

    return asiento


@transaction.atomic
def contabilizar_orden_pago(orden_pago) -> Asiento:
    """Genera el asiento contable de una Orden de Pago. Es el espejo exacto del Recibo.

    DEBE : - Pago a Proveedor -> la cuenta patrimonial del proveedor.
           - Pago Simple      -> la/s cuenta/s elegidas en "Imputaciones Contables Manuales".
    HABER: los medios de pago entregados (caja, dólares, banco, valores, retenciones).

    Igual que en el recibo, el debe y el haber van SIEMPRE en pesos; la moneda original queda en
    `divisa` + `cotizacion` + las columnas `*_divisa`.
    """
    from tesoreria.models import MovimientoCajaDetalle

    if getattr(orden_pago, 'asiento_id', None):
        anular_asiento_de_comprobante(orden_pago.asiento_id)
        orden_pago.asiento_id = None
        orden_pago.save(update_fields=['asiento_id'])

    parametros = ParametrosContables.objects.filter(empresa=orden_pago.empresa).first()
    if not parametros:
        raise ValidationError(
            f"No se encontraron Parámetros Contables para la empresa {orden_pago.empresa.nombre}."
        )

    lineas_asiento = []
    total_haber = Decimal("0.00")
    agrupado_haber = {}

    # 1. HABER: los medios de pago entregados, agrupados por cuenta (varios cheques entregados =
    #    una sola línea contra Valores en Cartera; el detalle de cada cheque vive en ValorTerceros).
    detalles = MovimientoCajaDetalle.objects.filter(
        movimiento_caja__orden_pago=orden_pago
    ).select_related('medio_pago__cuenta_contable',
                    'movimiento_caja__sesion__caja').prefetch_related(
        'transacciones_bancarias__cuenta_bancaria__cuenta_contable'
    ).order_by('id')

    for detalle in detalles:
        cuenta_haber = _cuenta_medio_cobro(detalle, parametros, es_pago=True)
        if not cuenta_haber:
            raise ValidationError(
                f"Falta configurar la cuenta contable del medio de pago "
                f"'{detalle.medio_pago.nombre}' (o la cuenta general de su categoría)."
            )

        importe_ars = detalle.importe
        en_divisa = detalle.importe_moneda_extranjera or Decimal("0.00")
        divisa = 'DOL' if en_divisa > 0 else 'PES'
        cotizacion = detalle.cotizacion or Decimal("1.0")

        clave = (cuenta_haber.id, divisa, cotizacion)
        if clave in agrupado_haber:
            agrupado_haber[clave]['haber'] += importe_ars
            agrupado_haber[clave]['haber_divisa'] += en_divisa
            agrupado_haber[clave]['medios'].add(detalle.medio_pago.nombre)
        else:
            agrupado_haber[clave] = {
                'cuenta': cuenta_haber,
                'debe': 0,
                'haber': importe_ars,
                'divisa': divisa,
                'cotizacion': cotizacion,
                'debe_divisa': 0,
                'haber_divisa': en_divisa,
                'cli_pro': orden_pago.proveedor,
                'medios': {detalle.medio_pago.nombre},
            }
        total_haber += importe_ars

    # 2. DEBE: proveedor (pago a proveedor) o las cuentas imputadas (pago simple).
    total_debe = Decimal("0.00")

    if orden_pago.tipo == 'P':
        cuenta_debe = None
        if orden_pago.proveedor and orden_pago.proveedor.cta_pat:
            cuenta_debe = Cuenta.objects.filter(
                pk=orden_pago.proveedor.cta_pat, empresa=orden_pago.empresa, imputable=1
            ).first()
        if not cuenta_debe:
            cuenta_debe = parametros.cta_proveedores_default
        if not cuenta_debe:
            raise ValidationError(
                "Falta configurar la cuenta patrimonial del proveedor o la cuenta general de proveedores."
            )

        lineas_asiento.append({
            'cuenta': cuenta_debe,
            'debe': total_haber,
            'haber': 0,
            'leyenda': f"Orden de Pago Nro {orden_pago.numero}",
            'divisa': 'PES',
            'cotizacion': Decimal("1.0"),
            'debe_divisa': 0,
            'haber_divisa': 0,
            'cli_pro': orden_pago.proveedor
        })
        total_debe += total_haber

    else:
        # Pago Simple: admite más de una cuenta imputada. Los importes ya vienen en pesos.
        imputaciones = orden_pago.imputaciones_simples.select_related('cuenta_contable').all()
        for imp in imputaciones:
            lineas_asiento.append({
                'cuenta': imp.cuenta_contable,
                'debe': imp.importe,
                'haber': 0,
                'leyenda': imp.leyenda or f"Orden de Pago Nro {orden_pago.numero}",
                'divisa': 'PES',
                'cotizacion': Decimal("1.0"),
                'debe_divisa': 0,
                'haber_divisa': 0,
                'cli_pro': orden_pago.proveedor
            })
            total_debe += imp.importe

    for linea in agrupado_haber.values():
        medios = ", ".join(sorted(linea.pop('medios')))
        linea['leyenda'] = f"Orden de Pago Nro {orden_pago.numero} - {medios}"
        lineas_asiento.append(linea)

    if total_haber <= 0:
        return None

    diferencia = total_haber - total_debe
    if diferencia != 0:
        if abs(diferencia) > Decimal("0.05"):
            raise ValidationError(
                f"Orden de Pago {orden_pago.numero} desbalanceada: "
                f"Debe {total_debe} vs Haber {total_haber}"
            )
        # El residuo de redondeo se absorbe en la última línea del DEBE.
        for linea in lineas_asiento:
            if linea['debe']:
                linea['debe'] += diferencia
                break
        total_debe += diferencia

    razon_social = orden_pago.proveedor.razon_social[:50] if orden_pago.proveedor else "N/A"
    concepto = f"OP {orden_pago.numero} - {razon_social}"

    asiento = crear_asiento(
        empresa=orden_pago.empresa,
        fecha=orden_pago.fecha,
        concepto=concepto,
        lineas=lineas_asiento,
        condic=orden_pago.condic,
        modulo=4, # Modulo Tesorería
        cli_pro=orden_pago.proveedor,
        ejercicio=orden_pago.ejercicio,
        usuario=orden_pago.creado_por
    )

    if orden_pago.sesion_caja_id:
        asiento.sesion_caja_id = orden_pago.sesion_caja_id
        asiento.save(update_fields=['sesion_caja'])

    orden_pago.asiento_id = asiento.asiento_id
    orden_pago.save(update_fields=['asiento_id'])

    return asiento
