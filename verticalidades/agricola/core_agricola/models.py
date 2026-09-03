from django.db import models
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
