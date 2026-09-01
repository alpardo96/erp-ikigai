from django.db import models
from django.conf import settings
from empresas.models import Empresa


class PeriodoIva(models.Model):
    """
    Gestión de Cierres de Períodos Fiscales IVA por Empresa.
    El período se almacena como string YYYYMM (ej: '202608').
    Un período cerrado bloquea la imputación fiscal de Compras y Ventas en dicho YYYYMM,
    forzando a que Compras de fechas en períodos cerrados se trasladen al primer período vigente.
    """
    ESTADOS = [
        ('CERRADO', 'Cerrado'),
        ('ABIERTO', 'Abierto'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='periodos_iva', verbose_name="Empresa")
    periodo = models.CharField(max_length=6, db_index=True, verbose_name="Período YYYYMM")
    estado = models.CharField(max_length=10, choices=ESTADOS, default='CERRADO', db_index=True)

    fecha_cierre = models.DateTimeField(auto_now_add=True, verbose_name="Fecha/Hora Cierre")
    usuario_cierre = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='periodos_iva_cerrados', verbose_name="Usuario Cierre")

    debito_fiscal = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Total Débito Fiscal (Ventas)")
    credito_fiscal = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Total Crédito Fiscal (Compras)")
    saldo_resultante = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Saldo Resultante")

    fecha_reapertura = models.DateTimeField(null=True, blank=True, verbose_name="Fecha/Hora Reapertura")
    usuario_reapertura = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='periodos_iva_reabiertos', verbose_name="Usuario Reapertura")

    class Meta:
        db_table = "impuestos_periodo_iva"
        verbose_name = "Período IVA"
        verbose_name_plural = "Períodos IVA"
        unique_together = ('empresa', 'periodo')
        indexes = [
            models.Index(fields=['empresa', 'periodo']),
            models.Index(fields=['empresa', 'estado']),
        ]

    def __str__(self):
        return f"Período {self.periodo} - {self.empresa.nombre} ({self.estado})"


class ArcaMisComprobantes(models.Model):
    """
    Almacena los comprobantes emitidos (Ventas) y recibidos (Compras)
    importados directamente desde las planillas de Mis Comprobantes ARCA / AFIP.
    """
    ORIGEN_CHOICES = [
        ('C', 'Compras (Comprobantes Recibidos)'),
        ('V', 'Ventas (Comprobantes Emitidos)'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='mis_comprobantes_arca', verbose_name="Empresa")
    origen = models.CharField(max_length=1, choices=ORIGEN_CHOICES, db_index=True, verbose_name="Origen (C=Compras, V=Ventas)")
    periodo = models.CharField(max_length=6, db_index=True, verbose_name="Período YYYYMM")
    fecha = models.DateField(db_index=True, verbose_name="Fecha Comprobante")

    codiva = models.CharField(max_length=3, db_index=True, verbose_name="Código Comprobante ARCA")
    punto = models.IntegerField(verbose_name="Punto de Venta")
    numero = models.BigIntegerField(verbose_name="Número Comprobante")
    numero_hasta = models.BigIntegerField(null=True, blank=True, verbose_name="Número Hasta")

    cuit_contraparte = models.CharField(max_length=11, db_index=True, verbose_name="CUIT Emisor/Receptor")
    razon_social_contraparte = models.CharField(max_length=200, blank=True, verbose_name="Denominación Emisor/Receptor")
    tipo_doc_contraparte = models.CharField(max_length=10, blank=True)
    nro_doc_contraparte = models.CharField(max_length=20, blank=True)

    tipo_cambio = models.DecimalField(max_digits=10, decimal_places=4, default=1.0)
    moneda = models.CharField(max_length=5, default='PES')

    neto_gravado = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    no_gravado = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    exento = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    iva_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    otros = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    cae = models.CharField(max_length=20, blank=True, db_index=True, verbose_name="CAE / CAI ARCA")

    # Campo de vinculación de conciliación con el sistema
    asiento_id = models.IntegerField(null=True, blank=True, db_index=True, verbose_name="ID Asiento Sistema (Conciliado)")

    fecha_importacion = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "arca_mis_comprobantes"
        verbose_name = "Mis Comprobantes ARCA"
        verbose_name_plural = "Mis Comprobantes ARCA"
        unique_together = ('empresa', 'origen', 'codiva', 'punto', 'numero', 'cuit_contraparte')
        indexes = [
            models.Index(fields=['empresa', 'origen', 'periodo']),
            models.Index(fields=['empresa', 'asiento_id']),
            models.Index(fields=['cae']),
        ]

    def __str__(self):
        return f"[{self.origen}] {self.codiva} {self.punto:04d}-{self.numero} | CUIT: {self.cuit_contraparte} | ${self.total}"
