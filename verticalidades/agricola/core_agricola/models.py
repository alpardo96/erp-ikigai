"""Modelos transversales de la verticalidad Agrícola.

Acá vive lo que comparten tabaco, granos y —más adelante— caña. Lo específico de cada negocio
va en su sub-app. Todas las tablas llevan el prefijo `agricola_` (Plan 078).
"""
from django.db import models

from core.models import AuditModel
from empresas.models import Empresa


class EmpresaVertical(models.Model):
    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name="agricola_vertical")
    hace_tabaco = models.BooleanField(default=False, verbose_name="Tabaco")
    hace_granos = models.BooleanField(default=False, verbose_name="Granos (Soja, Maíz, Poroto, etc.)")

    class Meta:
        db_table = "agricola_empresa_vertical"
        verbose_name = "Configuración Agrícola"
        verbose_name_plural = "Configuraciones Agrícolas"

    def __str__(self):
        return f"Configuración Agrícola: {self.empresa.nombre}"


class Campania(AuditModel):
    """Campaña agrícola (ej. 2026/2027).

    Vive en el core de la verticalidad y no en `tabaco` porque granos y caña la comparten. En el
    acopio se usa como dimensión de la lista de precio ponderante: el precio se negocia por
    campaña, y el de una campaña cerrada no puede volver a aplicarse.

    NO es el `Ejercicio` contable. Una campaña puede atravesar dos ejercicios (se siembra en un
    ejercicio y se cosecha en el siguiente), así que el ejercicio es un dato opcional de
    referencia y nunca reemplaza a las fechas.
    """
    ABIERTA, CERRADA = 1, 2
    ESTADOS = [(ABIERTA, 'Abierta'), (CERRADA, 'Cerrada')]

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='campanias_agricolas')
    codigo = models.CharField(max_length=20, verbose_name="Código")
    detalle = models.CharField(max_length=100, verbose_name="Descripción")
    fecha_inicio = models.DateField(verbose_name="Inicio")
    fecha_fin = models.DateField(null=True, blank=True, verbose_name="Fin")
    ejercicio = models.ForeignKey(
        'empresas.Ejercicio', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='campanias_agricolas', verbose_name="Ejercicio de referencia",
        help_text="Sólo referencia: una campaña puede abarcar más de un ejercicio.",
    )
    estado = models.IntegerField(choices=ESTADOS, default=ABIERTA, db_index=True)
    activa = models.BooleanField(default=True, verbose_name="Activa")

    class Meta:
        db_table = "agricola_campania"
        verbose_name = "Campaña Agrícola"
        verbose_name_plural = "Campañas Agrícolas"
        ordering = ['-fecha_inicio', 'codigo']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'codigo'], name='agro_campania_codigo_unico'),
            models.CheckConstraint(
                condition=models.Q(fecha_fin__isnull=True) | models.Q(fecha_fin__gte=models.F('fecha_inicio')),
                name='agro_campania_fechas_coherentes',
            ),
        ]
        indexes = [models.Index(fields=['empresa', 'estado'])]

    def __str__(self):
        return f"{self.codigo} - {self.detalle}"

    def save(self, *args, **kwargs):
        # Mismo criterio de normalización que el resto del ERP: los códigos y descripciones se
        # guardan en mayúsculas para que la búsqueda no dependa de cómo tipeó el operador.
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        if self.detalle:
            self.detalle = self.detalle.strip().upper()
        super().save(*args, **kwargs)
