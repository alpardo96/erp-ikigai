from django.db import models
from facturacion.models import ClienteProveedor

class ExtensionArmeria(models.Model):
    TIPO_PERSONA_CHOICES = [
        ('F', 'Persona Física'),
        ('J', 'Persona Jurídica'),
    ]

    cliente = models.OneToOneField(ClienteProveedor, on_delete=models.CASCADE, related_name="armeria")
    tipo_persona = models.CharField(max_length=1, choices=TIPO_PERSONA_CHOICES, null=True, blank=True, verbose_name="Tipo de Persona")
    clu = models.CharField(max_length=20, verbose_name="CLU")
    clu_vto = models.DateField(null=True, blank=True, verbose_name="Vencimiento CLU")
    es_policia = models.BooleanField(default=False, verbose_name="Es Policía")
    activo = models.BooleanField(null=True, default=True, verbose_name="Activo en Armería", db_index=True)

    class Meta:
        verbose_name = "Detalle Armería"
        db_table = 'facturacion_extensionarmeria'
        permissions = [
            ('menu_armeria_compras', 'Acceso: Compra de Armas'),
            ('menu_armeria_ventas', 'Acceso: Venta Trazabilidad (Armas)'),
            ('menu_armeria_trazabilidad', 'Acceso: Trazabilidad Productos'),
            ('menu_armeria_reservas', 'Acceso: Reservas por Venta de Armas'),
            ('menu_armeria_stock', 'Acceso: Stock de Armas'),
        ]

    @property
    def esta_vencida(self):
        from django.utils import timezone
        if not self.clu_vto:
            return True
        return self.clu_vto < timezone.localdate()

class ReservaArma(models.Model):
    """
    Control de Reservas de Armas (SIGIMAC).
    Permite registrar la seña/reserva de un producto trazable (arma) antes de la autorización
    de SIGIMAC, emitiendo un Recibo por Reserva y aplicando el comprobante al momento de facturar
    por Venta Trazabilidad o emitiendo Orden de Pago si el trámite resulta denegado.
    """
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente Autorización SIGIMAC'),
        ('APLICADA', 'Aplicada en Factura de Venta'),
        ('DEVUELTA', 'Anulada y Devuelta (Rechazo SIGIMAC)'),
    ]

    empresa = models.ForeignKey('empresas.Empresa', on_delete=models.CASCADE, related_name="reservas_armas")
    sucursal = models.ForeignKey('empresas.Sucursal', on_delete=models.CASCADE, related_name="reservas_armas")
    preventa = models.OneToOneField('facturacion.Preventa', on_delete=models.PROTECT, related_name="reserva_arma", verbose_name="Preventa Origen")
    cliente = models.ForeignKey(ClienteProveedor, on_delete=models.PROTECT, related_name="reservas_armas", verbose_name="Cliente")
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT, related_name="reservas_armas", verbose_name="Producto Reservado")
    recibo_reserva = models.ForeignKey('tesoreria.Recibo', on_delete=models.PROTECT, related_name="reservas_armas", verbose_name="Recibo de Reserva")
    
    monto_reservado = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Monto Señado / Reservado")
    monto_total = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Monto Total Preventa")
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE', db_index=True, verbose_name="Estado de Reserva")
    
    venta_aplicada = models.ForeignKey('facturacion.Venta', on_delete=models.SET_NULL, null=True, blank=True, related_name="reserva_arma_aplicada", verbose_name="Factura de Venta Trazabilidad")
    orden_pago_devolucion = models.ForeignKey('tesoreria.OrdenPago', on_delete=models.SET_NULL, null=True, blank=True, related_name="reserva_arma_devuelta", verbose_name="Orden de Pago Devolución")
    
    notas = models.TextField(null=True, blank=True, verbose_name="Notas de Preventa")
    
    fecha_reserva = models.DateField(auto_now_add=True, verbose_name="Fecha de Reserva")
    fecha_resolucion = models.DateField(null=True, blank=True, verbose_name="Fecha Resolución SIGIMAC")
    observaciones = models.TextField(null=True, blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Reserva de Arma (SIGIMAC)"
        verbose_name_plural = "Reservas de Armas (SIGIMAC)"
        ordering = ['-fecha_reserva', '-id']
        indexes = [
            models.Index(fields=['empresa', 'estado']),
            models.Index(fields=['cliente', 'estado']),
        ]

    def __str__(self):
        return f"Reserva #{self.id} - {self.cliente.razon_social} - {self.producto.detalle} ({self.get_estado_display()})"

