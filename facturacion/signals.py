from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from .models import Venta, Compra, Preventa, PreventaItem
from contable.services.saldos import recalcular_saldo_cliente_proveedor

@receiver(pre_save, sender=Venta)
def detectar_cambio_cliente(sender, instance, **kwargs):
    """
    Guarda el cliente anterior si la venta ya existía para poder recalcular su saldo
    en caso de que se cambie el cliente asignado al comprobante.
    """
    if instance.pk:
        try:
            old_instance = Venta.objects.get(pk=instance.pk)
            instance._old_cliente_id = old_instance.cliente_id
        except Venta.DoesNotExist:
            instance._old_cliente_id = None
    else:
        instance._old_cliente_id = None

@receiver(post_save, sender=Venta)
def actualizar_saldo_cliente_post_save(sender, instance, **kwargs):
    """
    Signal disparada al guardar una Venta. Recalcula el saldo del cliente asociado,
    y también del cliente anterior si cambió.
    Adicionalmente, conecta la automatización contable en tiempo real.
    """
    # Evitar la recursión infinita cuando el propio servicio contable actualiza el comprobante
    if getattr(instance, '_no_contabilizar', False):
        return

    # Recalcular cliente actual
    recalcular_saldo_cliente_proveedor(instance.cliente.pk)
    
    # Recalcular cliente anterior si cambió
    old_cliente_id = getattr(instance, '_old_cliente_id', None)
    if old_cliente_id and old_cliente_id != instance.cliente_id:
        recalcular_saldo_cliente_proveedor(old_cliente_id)

    # Una NC vinculada a su origen DESCUENTA el saldo de esa factura (Plan 076 §D), así que
    # hay que recalcular los dos. Va acá y no en el emisor de la NC para que valga también
    # al ANULARLA, que es cuando el descuento se revierte. No hay recursión: el servicio
    # escribe con `.update()`, que no dispara señales.
    if instance.venta_origen_id:
        from contable.services.saldos import recalcular_saldo_venta
        recalcular_saldo_venta(instance.pk)
        recalcular_saldo_venta(instance.venta_origen_id)

    update_fields = kwargs.get('update_fields')
    if update_fields and set(update_fields) == {'saldo'}:
        return

    # =========================================================================
    # AUTOMATIZACIÓN CONTABLE (Fase 3)
    # =========================================================================
    # Realizamos importación local de servicios para evitar colisiones/dependencias circulares al inicio
    from contable.services.contabilizacion import (
        contabilizar_venta_individual,
        anular_asiento_de_comprobante,
        ParametrosContables
    )
    
    if instance.estado == 1:
        # Si el comprobante se marca como ANULADO (estado = 1), se anula el asiento asociado
        if instance.asiento_id:
            anular_asiento_de_comprobante(instance.asiento_id)
    elif instance.estado == 0:
        # Si el comprobante está ACTIVO, verificamos el método de contabilización configurado para la empresa
        parametros = ParametrosContables.objects.filter(empresa=instance.empresa).first()
        if parametros and parametros.metodo_contabilizacion_ventas == 1:
            # Método 1 = Individual: Contabilizar síncronamente al guardar
            contabilizar_venta_individual(instance)

    # Actualizar la vista materializada de Movimientos
    from facturacion.services.movimientos import regenerar_movimientos_venta
    regenerar_movimientos_venta(instance)


@receiver(post_delete, sender=Venta)
def actualizar_saldo_cliente_post_delete(sender, instance, **kwargs):
    """
    Signal disparada al eliminar una Venta. Recalcula el saldo del cliente asociado.
    Adicionalmente, anula de forma inmutable el asiento contable (sin borrarlo físicamente).
    """
    # Verificamos si el cliente sigue existiendo en DB para evitar IntegrityError
    if instance.cliente_id:
        try:
            recalcular_saldo_cliente_proveedor(instance.cliente_id)
        except Exception:
            pass

    # =========================================================================
    # AUTOMATIZACIÓN CONTABLE (Baja física de comprobante -> Anulación de asiento)
    # =========================================================================
    if instance.asiento_id:
        from contable.services.contabilizacion import anular_asiento_de_comprobante
        anular_asiento_de_comprobante(instance.asiento_id)


@receiver(pre_save, sender=Compra)
def detectar_cambio_proveedor(sender, instance, **kwargs):
    """
    Guarda el proveedor anterior si la compra ya existía para poder recalcular su saldo
    en caso de que se cambie el proveedor asignado al comprobante.
    """
    if instance.pk:
        try:
            old_instance = Compra.objects.get(pk=instance.pk)
            instance._old_proveedor_id = old_instance.proveedor_id
        except Compra.DoesNotExist:
            instance._old_proveedor_id = None
    else:
        instance._old_proveedor_id = None


@receiver(post_save, sender=Compra)
def actualizar_saldo_proveedor_post_save(sender, instance, **kwargs):
    """
    Signal disparada al guardar una Compra. Recalcula el saldo del proveedor asociado,
    y también del proveedor anterior si cambió.
    Adicionalmente, dispara la contabilización automática.
    """
    # Evitar la recursión infinita cuando el propio servicio contable actualiza el comprobante
    if getattr(instance, '_no_contabilizar', False):
        return

    # Recalcular proveedor actual
    recalcular_saldo_cliente_proveedor(instance.proveedor.pk)
    
    # Recalcular proveedor anterior si cambió
    old_proveedor_id = getattr(instance, '_old_proveedor_id', None)
    if old_proveedor_id and old_proveedor_id != instance.proveedor_id:
        recalcular_saldo_cliente_proveedor(old_proveedor_id)

    update_fields = kwargs.get('update_fields')
    if update_fields and set(update_fields) == {'saldo'}:
        return

    # =========================================================================
    # AUTOMATIZACIÓN CONTABLE (Fase 3 - Se verifica la existencia de parámetros contables)
    # =========================================================================
    from contable.services.contabilizacion import ParametrosContables, contabilizar_compras
    if ParametrosContables.objects.filter(empresa=instance.empresa).exists():
        contabilizar_compras(instance)
        
    # Actualizar la vista materializada de Movimientos
    from facturacion.services.movimientos import regenerar_movimientos_compra
    regenerar_movimientos_compra(instance)


@receiver(post_delete, sender=Compra)
def actualizar_saldo_proveedor_post_delete(sender, instance, **kwargs):
    """
    Signal disparada al eliminar una Compra. Recalcula el saldo del proveedor asociado.
    Adicionalmente, anula de forma inmutable el asiento contable (sin borrarlo físicamente).
    """
    if instance.proveedor_id:
        try:
            recalcular_saldo_cliente_proveedor(instance.proveedor_id)
        except Exception:
            pass

    # =========================================================================
    # AUTOMATIZACIÓN CONTABLE (Baja física de compra -> Anulación de asiento)
    # =========================================================================
    if instance.asiento_id:
        from contable.services.contabilizacion import ParametrosContables, anular_asiento_de_comprobante
        if ParametrosContables.objects.filter(empresa=instance.empresa).exists():
            anular_asiento_de_comprobante(instance.asiento_id)

# =========================================================================
# SEÑALES PARA ÍTEMS (Stock y Recálculo de Totales)
# =========================================================================
from .models import VentaItem, CompraItem

@receiver(post_save, sender=VentaItem)
def actualizar_stock_totales_venta_post_save(sender, instance, created, **kwargs):
    from productos.services.stock_service import aplicar_movimiento_stock
    aplicar_movimiento_stock(instance, signo=-1, sucursal=instance.venta.sucursal, es_borrado=False)
    instance.venta.recalcular_totales()

@receiver(post_delete, sender=VentaItem)
def actualizar_stock_totales_venta_post_delete(sender, instance, **kwargs):
    from productos.services.stock_service import aplicar_movimiento_stock
    aplicar_movimiento_stock(instance, signo=-1, sucursal=instance.venta.sucursal, es_borrado=True)
    instance.venta.recalcular_totales()

@receiver(post_save, sender=CompraItem)
def actualizar_stock_totales_compra_post_save(sender, instance, created, **kwargs):
    from productos.services.stock_service import aplicar_movimiento_stock
    aplicar_movimiento_stock(instance, signo=1, sucursal=instance.compra.sucursal, es_borrado=False)
    instance.compra.recalcular_totales()

@receiver(post_delete, sender=CompraItem)
def actualizar_stock_totales_compra_post_delete(sender, instance, **kwargs):
    from productos.services.stock_service import aplicar_movimiento_stock
    aplicar_movimiento_stock(instance, signo=1, sucursal=instance.compra.sucursal, es_borrado=True)
    instance.compra.recalcular_totales()


# =========================================================================
# SEÑALES DE STOCK PARA RECEPCIÓN (Plan 028 — circuito OC/Recepción, aditivo)
# La Recepción da ENTRADA al stock en su sucursal de destino. No afecta el
# circuito de factura/remito existente (opera sobre otro modelo).
# =========================================================================
from .models import RecepcionItem

@receiver(post_save, sender=RecepcionItem)
def actualizar_stock_recepcion_post_save(sender, instance, created, **kwargs):
    from productos.services.stock_service import aplicar_movimiento_recepcion
    aplicar_movimiento_recepcion(instance, es_borrado=False)

@receiver(post_delete, sender=RecepcionItem)
def actualizar_stock_recepcion_post_delete(sender, instance, **kwargs):
    from productos.services.stock_service import aplicar_movimiento_recepcion
    aplicar_movimiento_recepcion(instance, es_borrado=True)


# Remito Interno (Fase 6): SALIDA del stock en la sucursal de origen al emitir.
from .models import RemitoInternoItem

@receiver(post_save, sender=RemitoInternoItem)
def actualizar_stock_remito_interno_post_save(sender, instance, created, **kwargs):
    from productos.services.stock_service import aplicar_movimiento_remito_interno
    aplicar_movimiento_remito_interno(instance, es_borrado=False)

@receiver(post_delete, sender=RemitoInternoItem)
def actualizar_stock_remito_interno_post_delete(sender, instance, **kwargs):
    from productos.services.stock_service import aplicar_movimiento_remito_interno
    aplicar_movimiento_remito_interno(instance, es_borrado=True)


# ---------------------------------------------------------------------------
# Stock COMPROMETIDO en pedidos (Plan 074)
# ---------------------------------------------------------------------------
# El pedido no mueve stock físico, pero sí lo compromete: entre que el vendedor lo toma y la
# administración lo factura —en una distribuidora, la noche entera— dos vendedores pueden
# prometer la misma mercadería sin verse. Por eso `StockSucursal.comprometido` se mantiene al
# día con las mismas reglas que `cantidad`: se RECALCULA entero, nunca se ajusta por delta.

@receiver(post_save, sender=PreventaItem)
def actualizar_comprometido_post_save(sender, instance, created, **kwargs):
    from productos.services.stock_service import recalcular_comprometido
    if instance.producto_id and instance.preventa_id:
        recalcular_comprometido(instance.producto_id, instance.preventa.sucursal_id)


@receiver(post_delete, sender=PreventaItem)
def actualizar_comprometido_post_delete(sender, instance, **kwargs):
    from productos.services.stock_service import recalcular_comprometido
    if instance.producto_id and instance.preventa_id:
        recalcular_comprometido(instance.producto_id, instance.preventa.sucursal_id)


@receiver(post_save, sender=Preventa)
def actualizar_comprometido_por_cambio_estado(sender, instance, **kwargs):
    """Al facturar o anular un pedido, su stock deja de estar comprometido.

    El cambio no ocurre en los ítems sino en la CABECERA, así que sin esta señal el
    comprometido quedaría inflado para siempre después de facturar.
    """
    from productos.services.stock_service import recalcular_comprometido
    for producto_id in instance.items.values_list('producto_id', flat=True).distinct():
        recalcular_comprometido(producto_id, instance.sucursal_id)
