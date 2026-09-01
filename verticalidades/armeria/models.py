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

    class Meta:
        verbose_name = "Detalle Armería"
        db_table = 'facturacion_extensionarmeria'

    @property
    def esta_vencida(self):
        from django.utils import timezone
        if not self.clu_vto:
            return True
        return self.clu_vto < timezone.localdate()
