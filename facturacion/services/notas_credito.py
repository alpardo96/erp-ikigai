from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from facturacion.models import Venta, VentaItem, TipoComprobante
from productos.models import Subproducto

# Mapeo estático de AFIP para comprobantes de Venta
# (Factura A -> NC A, etc.)
MAPEO_NC = {
    '001': '003', # Factura A -> Nota de Crédito A
    '006': '008', # Factura B -> Nota de Crédito B
    '011': '013', # Factura C -> Nota de Crédito C
    # Distribución (Plan 074): el PRE es un comprobante NO fiscal y su contracara es la
    # Nota de Crédito Interna. Serie propia, numerada por el sistema, con `signo = -1`
    # para que el stock vuelva por el mismo mecanismo que las NC fiscales.
    'PRE': 'NCI',
}

@transaction.atomic
def emitir_nota_credito_desde_venta(venta_original: Venta, items_devolucion: dict, usuario, numero_nc=None, punto_nc=None):
    """
    Genera una Nota de Crédito a partir de una Venta original.
    
    :param venta_original: Instancia de Venta (Factura original).
    :param items_devolucion: Diccionario {venta_item_id: cantidad_a_devolver} (decimal/str).
    :param usuario: Usuario que emite la NC.
    :param numero_nc: Número definitivo de comprobante provisto por AFIP/ARCA (opcional).
    :param punto_nc: Punto de venta a asignar al comprobante (opcional).
    :return: Instancia de Venta correspondiente a la Nota de Crédito generada.
    """
    
    if not venta_original.tipo or venta_original.tipo.codigo not in MAPEO_NC:
        raise ValidationError("El tipo de comprobante no es válido o no tiene una Nota de Crédito asociada soportada.")
        
    codigo_nc = MAPEO_NC[venta_original.tipo.codigo]
    try:
        tipo_nc = TipoComprobante.objects.get(codigo=codigo_nc)
    except TipoComprobante.DoesNotExist:
        raise ValidationError(f"No existe el tipo de comprobante Nota de Crédito asociado al código '{codigo_nc}'.")

    if tipo_nc.signo != -1:
        raise ValidationError("El tipo de comprobante de Nota de Crédito debe tener signo -1 configurado en la base de datos.")

    punto_NC = int(punto_nc) if punto_nc is not None else venta_original.punto

    if numero_nc is not None:
        nuevo_numero = int(numero_nc)
    else:
        # Buscamos el último número para ese tipo y punto en la empresa
        ultimo = Venta.objects.filter(empresa=venta_original.empresa, punto=punto_NC, tipo=tipo_nc).order_by('-numero').first()
        nuevo_numero = (ultimo.numero + 1) if ultimo else 1


    # Generamos la nueva cabecera (Nota de Crédito)
    nueva_nc = Venta(
        fecha=timezone.localdate(),
        periodo=timezone.localtime().strftime("%Y%m"),
        tipo=tipo_nc,
        punto=punto_NC,
        numero=nuevo_numero, 
        cliente=venta_original.cliente,
        # El vínculo con el comprobante acreditado (Plan 076 §D). De acá sale el saldo REAL
        # de la factura: `total − cobrado − recibos − NC relacionadas`. La NC queda en cero.
        venta_origen=venta_original,
        cliente_razon_social=venta_original.cliente_razon_social,
        cliente_cuit=venta_original.cliente_cuit,
        cliente_domicilio=venta_original.cliente_domicilio,
        moneda=venta_original.moneda,
        cotizacion=venta_original.cotizacion,
        condic=venta_original.condic,
        usuario=usuario,
        vendedor=venta_original.vendedor,
        cajero=usuario,
        sucursal=venta_original.sucursal,
        empresa=venta_original.empresa,
        ejercicio=venta_original.ejercicio,
        estado=0 # Activa
    )
    
    nueva_nc.save()

    # Agregar los ítems
    hay_items = False
    for item_id, cantidad in items_devolucion.items():
        cantidad_decimal = Decimal(str(cantidad))
        if cantidad_decimal <= 0:
            continue
            
        try:
            original_item = VentaItem.objects.get(id=item_id, venta=venta_original)
        except VentaItem.DoesNotExist:
            continue
            
        if cantidad_decimal > original_item.cantidad:
            raise ValidationError(f"La cantidad a devolver ({cantidad_decimal}) para el producto {original_item.producto.nombre} excede la facturada ({original_item.cantidad}).")
            
        hay_items = True
        
        # El subtotal se recalcula en base a la cantidad devuelta
        precio = original_item.precio_unitario
        desc = original_item.porcentaje_descuento
        total_item = (precio * cantidad_decimal) * (Decimal('1') - (desc / Decimal('100')))
            
        VentaItem.objects.create(
            venta=nueva_nc,
            producto=original_item.producto,
            cantidad=cantidad_decimal,
            precio_unitario=original_item.precio_unitario,
            porcentaje_descuento=original_item.porcentaje_descuento,
            iva_alicuota=original_item.iva_alicuota,
            total=total_item,
            cto_rep=original_item.cto_rep,
            moneda_origen=original_item.moneda_origen,
            cotizacion_aplicada=original_item.cotizacion_aplicada,
            precio_origen=original_item.precio_origen
        )

        # -------------------------------------------------------------------------
        # REVERSIÓN DE TRAZABILIDAD (Plan 071 / Requerimiento 3):
        # Si el producto es trazable (subprod == True), revertir la situación del
        # Subproducto de 'VENDIDA' a 'DEPOSITO' y limpiar los datos de la venta.
        # -------------------------------------------------------------------------
        if original_item.producto and getattr(original_item.producto, 'subprod', False):
            cant_revertir = int(cantidad_decimal)
            subprods_afectados = Subproducto.objects.filter(
                venta=venta_original,
                producto=original_item.producto,
                situacion='VENDIDA'
            )[:cant_revertir]

            for sp in subprods_afectados:
                sp.situacion = 'DEPOSITO'
                sp.venta = None
                sp.fecvta = None
                sp.precio_neto = Decimal('0.00')
                sp.precio_total = Decimal('0.00')
                sp.cotizvta = Decimal('1.0000')
                sp.fecent = None
                sp.save(update_fields=['situacion', 'venta', 'fecvta', 'precio_neto', 'precio_total', 'cotizvta', 'fecent'])
        
    if not hay_items:
        nueva_nc.delete()
        raise ValidationError("Debe especificar al menos un producto con cantidad a devolver mayor a cero.")
        
    # Recalcular totales e impuestos en la NC
    nueva_nc.recalcular_totales()
    
    return nueva_nc


