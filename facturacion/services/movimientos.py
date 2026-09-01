from django.db import transaction
from decimal import Decimal
from facturacion.models import Movimiento, Venta, Compra

@transaction.atomic
def regenerar_movimientos_venta(venta: Venta):
    """
    Regenera la vista materializada de 'Movimiento' para una Venta.
    """
    Movimiento.objects.filter(venta=venta).delete()
    
    # Si está anulada, no generamos movimientos físicos/contables activos
    if venta.estado == 1:
        return
        
    movimientos = []
    for item in venta.items.select_related('producto').all():
        neto_item = item.total / (Decimal("1.00") + (Decimal(str(item.iva_alicuota)) / Decimal("100.00")))
        
        # En AFIP, los tipos de comprobantes suelen ser enteros (ej 1, 6, 11). 
        # Si venta.tipo.codigo no es entero, ponemos 0 y evitamos crash.
        try:
            tipo_int = int(venta.tipo.codigo) if venta.tipo else 0
        except ValueError:
            tipo_int = 0

        movimientos.append(Movimiento(
            asiento_id=venta.asiento_id,
            venta=venta,
            producto=item.producto,
            fecha=venta.fecha,
            tipo=tipo_int,
            punto=venta.punto,
            numero=venta.numero,
            cli_pro=venta.cliente,
            tipo_mov='Venta',
            entrada=Decimal("0.00"),
            salida=item.cantidad,
            precio=item.precio_unitario,
            neto=neto_item.quantize(Decimal("0.01")),
            usuario=venta.usuario,
            sucursal=venta.sucursal,
            empresa=venta.empresa,
            ejercicio=venta.ejercicio
        ))
    
    if movimientos:
        Movimiento.objects.bulk_create(movimientos)

@transaction.atomic
def regenerar_movimientos_compra(compra: Compra):
    """
    Regenera la vista materializada de 'Movimiento' para una Compra.
    """
    Movimiento.objects.filter(compra=compra).delete()
    
    movimientos = []
    for item in compra.items.select_related('producto').all():
        neto_item = item.total / (Decimal("1.00") + (Decimal(str(item.iva_alicuota)) / Decimal("100.00")))
        
        try:
            tipo_int = int(compra.tipo.codigo) if compra.tipo else 0
        except ValueError:
            tipo_int = 0

        movimientos.append(Movimiento(
            asiento_id=compra.asiento_id,
            compra=compra,
            producto=item.producto,
            fecha=compra.fecha,
            tipo=tipo_int,
            punto=compra.punto,
            numero=compra.numero,
            cli_pro=compra.proveedor,
            tipo_mov='Compra',
            entrada=item.cantidad,
            salida=Decimal("0.00"),
            precio=item.precio_unitario,
            neto=neto_item.quantize(Decimal("0.01")),
            usuario=compra.usuario,
            sucursal=compra.sucursal,
            empresa=compra.empresa,
            ejercicio=compra.ejercicio
        ))
    
    if movimientos:
        Movimiento.objects.bulk_create(movimientos)
