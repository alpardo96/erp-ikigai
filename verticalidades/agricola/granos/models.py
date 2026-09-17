"""
Modelos satélites para la verticalidad Agrícola -> Granos.

Define:
1. GranoMapeo (agricola_grano_mapeo):
   Vincula el código oficial de granos de ARCA/AFIP (ej. 19 - MAÍZ, 23 - SOJA)
   con el producto en el catálogo (productos.Producto) y la cuenta contable de ventas específica (contable.Cuenta).

2. GastoMapeo (agricola_gasto_mapeo):
   Vincula conceptos de gastos/deducciones comerciales presentes en las liquidaciones primarias de granos
   (mediante patrones de búsqueda como FLETE, COMISION, SELLADO, etc.) con su cuenta contable de gasto (contable.Cuenta).

IMPORTANTE: Todas las tablas llevan el prefijo obligatorio `agricola_`.
"""
from decimal import Decimal
from django.db import models
from core.models import AuditModel
from empresas.models import Empresa


class GranoMapeo(AuditModel):
    """
    Mapeo entre el nomenclador oficial de granos de ARCA/AFIP,
    el producto en el maestro de productos y su cuenta contable de ventas.
    
    Permite que al leer una Liquidación Primaria de Granos (LPG) con el código oficial
    de ARCA (ej. 19 para Maíz, 23 para Soja), el ERP identifique automáticamente el
    producto y la cuenta de ventas a imputar.
    """
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='agricola_granos_mapeos',
        verbose_name="Empresa"
    )
    codigo_arca = models.IntegerField(
        verbose_name="Cód. Grano ARCA",
        help_text="Código oficial de ARCA (ej. 19 para Maíz, 23 para Soja, 15 para Trigo)"
    )
    descripcion_arca = models.CharField(
        max_length=100,
        verbose_name="Descripción ARCA",
        help_text="Denominación oficial del cultivo en ARCA (ej. MAIZ, SOJA, TRIGO PAN)"
    )
    producto = models.ForeignKey(
        'productos.Producto',
        on_delete=models.PROTECT,
        related_name='mapeos_granos_arca',
        verbose_name="Producto ERP"
    )
    cta_ventas = models.ForeignKey(
        'contable.Cuenta',
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name="Cuenta Contable de Ventas",
        help_text="Cuenta contable de resultado positivo donde se imputa la venta del cultivo (ej. 51 Venta de Soja)"
    )

    class Meta:
        db_table = "agricola_grano_mapeo"
        verbose_name = "Mapeo de Grano ARCA"
        verbose_name_plural = "Mapeos de Granos ARCA"
        ordering = ['codigo_arca']
        constraints = [
            models.UniqueConstraint(
                fields=['empresa', 'codigo_arca'],
                name='agro_grano_mapeo_unico_por_empresa'
            )
        ]

    def __str__(self):
        return f"[{self.codigo_arca}] {self.descripcion_arca} -> {self.producto.detalle} (Cta: {self.cta_ventas.cuenta})"

    def save(self, *args, **kwargs):
        if self.descripcion_arca:
            self.descripcion_arca = self.descripcion_arca.strip().upper()
        super().save(*args, **kwargs)


class GastoMapeo(AuditModel):
    """
    Mapeo de conceptos de gastos/deducciones comerciales presentes en las liquidaciones
    con las cuentas contables de imputación de gasto (Fletes, Comisiones, Sellados, etc.).
    
    Funciona por coincidencia de subcadenas/patrones (ej. si el concepto del PDF contiene
    'FLETE', se imputa a la cuenta de Fletes de Granos).
    """
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='agricola_gastos_mapeos',
        verbose_name="Empresa"
    )
    patron = models.CharField(
        max_length=100,
        verbose_name="Patrón / Palabra Clave",
        help_text="Texto clave a buscar en la línea de deducción del PDF (ej. FLETE, COMISION, SELLADO, MERCADERIA EN FINAL)"
    )
    descripcion = models.CharField(
        max_length=150,
        verbose_name="Descripción del Concepto",
        help_text="Descripción legible para el usuario (ej. Fletes de Granos, Comisión Acopio, Impuesto de Sellos)"
    )
    cta_gasto = models.ForeignKey(
        'contable.Cuenta',
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name="Cuenta Contable de Gasto",
        help_text="Cuenta de resultado negativo / pérdida donde se imputa la deducción"
    )
    alicuota_sugerida = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.50'),
        verbose_name="Alícuota IVA Sugerida (%)",
        help_text="Alícuota de IVA por defecto para este gasto si el comprobante no la especifica"
    )

    class Meta:
        db_table = "agricola_gasto_mapeo"
        verbose_name = "Mapeo de Gasto de Liquidación"
        verbose_name_plural = "Mapeos de Gastos de Liquidaciones"
        ordering = ['patron']
        constraints = [
            models.UniqueConstraint(
                fields=['empresa', 'patron'],
                name='agro_gasto_mapeo_unico_por_empresa'
            )
        ]

    def __str__(self):
        return f"Patrón: '{self.patron}' -> {self.descripcion} (Cta: {self.cta_gasto.cuenta})"

    def save(self, *args, **kwargs):
        if self.patron:
            self.patron = self.patron.strip().upper()
        if self.descripcion:
            self.descripcion = self.descripcion.strip().upper()
        super().save(*args, **kwargs)
