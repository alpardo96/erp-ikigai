from django.db import models
from core.models import AuditModel
from facturacion.models import ClienteProveedor

class TarifaEstudio(AuditModel):
    """
    Tabla satélite exclusiva para empresas tipo 'ESTUDIO'.
    Almacena las tarifas pactadas por cliente/producto (honorarios) 
    y su imputación contable específica (sobreescribiendo la del rubro).
    """
    empresa = models.ForeignKey('empresas.Empresa', on_delete=models.CASCADE)
    cliente = models.ForeignKey(ClienteProveedor, on_delete=models.CASCADE, related_name='tarifas_estudio', verbose_name="Cliente")
    producto = models.ForeignKey('productos.Producto', on_delete=models.CASCADE, verbose_name="Servicio/Producto")
    
    # Imputación contable específica para este honorario
    cuenta = models.ForeignKey('contable.Cuenta', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Cuenta Contable")
    
    # Tarifas según condición (Fiscal / No Fiscal)
    tarifa_f = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Tarifa Fiscal (Condic=1)")
    tarifa_p = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Tarifa Gestión (Condic=2)")
    
    # Control de estado
    activo = models.BooleanField(default=True, verbose_name="Tarifa Activa")

    class Meta:
        verbose_name = "Tarifa de Estudio"
        verbose_name_plural = "Tarifas de Estudio"
        db_table = 'facturacion_tarifaestudio'

    def __str__(self):
        return f"{self.cliente.razon_social} - {self.producto.detalle}"


class EnvioFacturaEstudio(AuditModel):
    """
    Tabla satélite para el seguimiento y automatización de envíos
    de facturas por mail en la verticalidad Estudio.
    """
    ESTADOS = [
        ('PENDIENTE', 'Pendiente'),
        ('ENVIADO', 'Enviado'),
        ('ERROR', 'Error'),
    ]

    MODOS_ADJUNTO = [
        ('SISTEMA', 'Usar Factura del Sistema'),
        ('REEMPLAZAR', 'Intercambiar por Factura Cargada'),
        ('AMBOS', 'Enviar Agregadas (Sistema + Cargada)'),
    ]

    empresa = models.ForeignKey('empresas.Empresa', on_delete=models.CASCADE, related_name='envios_facturas_estudio')
    venta = models.OneToOneField('facturacion.Venta', on_delete=models.CASCADE, related_name='envio_estudio', verbose_name="Factura/Comprobante")
    cliente = models.ForeignKey(ClienteProveedor, on_delete=models.CASCADE, related_name='envios_facturas_estudio', verbose_name="Cliente")
    periodo = models.CharField(max_length=6, db_index=True, verbose_name="Período Facturado (YYYYMM)")
    destinatarios = models.CharField(max_length=500, blank=True, default='', verbose_name="Destinatarios (Mails)")
    archivo_adjunto = models.FileField(upload_to='estudio/facturas_adjuntas/', null=True, blank=True, verbose_name="Comprobante Adjunto Externo")
    modo_adjunto = models.CharField(max_length=20, choices=MODOS_ADJUNTO, default='SISTEMA', verbose_name="Modo de Adjuntos")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE', db_index=True, verbose_name="Estado de Envío")
    respuesta_smtp = models.TextField(null=True, blank=True, verbose_name="Respuesta SMTP / Registro")
    fecha_envio = models.DateTimeField(null=True, blank=True, verbose_name="Fecha y Hora de Envío")
    intentos = models.PositiveIntegerField(default=0, verbose_name="Intentos de Envío")

    class Meta:
        verbose_name = "Envío de Factura Estudio"
        verbose_name_plural = "Envíos de Facturas Estudio"
        db_table = 'estudio_envio_factura'
        indexes = [
            models.Index(fields=['empresa', 'estado']),
            models.Index(fields=['empresa', 'periodo']),
        ]

    def __str__(self):
        return f"Envío Venta {self.venta_id} ({self.cliente.razon_social}) - {self.estado}"

