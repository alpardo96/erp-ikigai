from django.db import models
from django.contrib.auth.models import User
from empresas.models import Empresa, Sucursal

class Perfil(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil")
    empresas = models.ManyToManyField(Empresa, blank=True, related_name="usuarios")
    es_admin_sistema = models.BooleanField(default=False, verbose_name="Es Administrador de Sistema")

    # El cajero opera TODO desde su Caja Mostrador (Plan 077 §G): cobra con el recibo que
    # sale de esa pantalla y rinde al cerrar. No emite recibos ni órdenes de pago de
    # Tesorería, ni entra a la caja de Tesorería.
    #
    # ES UNA RESTRICCIÓN, NO UN PERMISO, y por eso arranca en False: así nadie pierde
    # accesos al aplicar el cambio y sólo queda acotado quien se marque. Al revés —un
    # permiso que hubiera que otorgar— dejaría a todos afuera hasta tildarlo uno por uno.
    es_cajero_mostrador = models.BooleanField(
        default=False, verbose_name="Sólo Caja Mostrador",
        help_text="Restringe al usuario a su caja: no ve Recibos, Órdenes de Pago ni "
                  "Tesorería.")
    
    # Permisos Modulares Dedicados
    permiso_clientes_ver = models.BooleanField(default=False, verbose_name="Ver Clientes y Proveedores")
    permiso_clientes_editar = models.BooleanField(default=False, verbose_name="ABM Clientes y Proveedores")
    
    permiso_facturacion_compras = models.BooleanField(default=False, verbose_name="Módulo Compras")
    permiso_facturacion_lista_compras = models.BooleanField(default=False, verbose_name="Módulo Lista de Compras")
    permiso_facturacion_autorizaciones = models.BooleanField(default=False, verbose_name="Módulo Autorizaciones")
    permiso_facturacion_carga_ventas = models.BooleanField(default=False, verbose_name="Módulo Carga de Ventas")
    permiso_facturacion_lista_ventas = models.BooleanField(default=False, verbose_name="Módulo Lista de Ventas")

    
    permiso_autorizar_descuentos = models.BooleanField(default=False, verbose_name="Autorizar Descuentos en Preventas")
    
    permiso_cotizaciones_editar = models.BooleanField(default=False, verbose_name="Editar Cotizaciones de Moneda")

    # --- Distribución (Plan 074) ---
    # Repartir el stock escaso decide qué cliente recibe menos: es una decisión
    # comercial, no una tarea de carga, y por eso lleva permiso propio.
    permiso_distribucion_asignar_stock = models.BooleanField(
        default=False, verbose_name="Asignar Stock Escaso (Distribución)")
    # Emitir comprobantes fiscales tampoco es una tarea de carga: una vez emitidos,
    # corregirlos cuesta una nota de crédito.
    permiso_distribucion_facturar_lote = models.BooleanField(
        default=False, verbose_name="Facturación Masiva (Distribución)")

    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuarios"

    def __str__(self):
        return f"Perfil de {self.usuario.username}"
