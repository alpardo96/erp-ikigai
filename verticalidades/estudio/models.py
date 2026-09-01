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
