from django.db import models
from django.contrib.auth.models import User, Permission
from empresas.models import Empresa, Sucursal

class Perfil(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil")
    empresas = models.ManyToManyField(Empresa, blank=True, related_name="usuarios")
    es_admin_sistema = models.BooleanField(default=False, verbose_name="Es Administrador de Sistema")

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
        permissions = [
            ('menu_clientes', 'Acceso: Clientes y Proveedores'),

            # Facturación / Compras
            ('menu_compras', 'Acceso: Módulo Compras (Padre)'),
            ('menu_compras_carga', 'Acceso: Carga Manual de Compras'),
            ('menu_compras_oc', 'Acceso: Órdenes de Compra'),
            ('menu_compras_automatica', 'Acceso: Carga Automática (OCR)'),
            ('menu_compras_ia', 'Acceso: Carga por IA'),
            ('menu_compras_listado', 'Acceso: Listado de Compras y Facturas Pendientes'),
            
            # Facturación / Ventas
            ('menu_ventas', 'Acceso: Módulo Ventas (Padre)'),
            ('menu_ventas_carga', 'Acceso: Carga de Ventas'),
            ('menu_ventas_preventas', 'Acceso: Carga de PreVentas'),
            ('menu_ventas_listado', 'Acceso: Listado de Ventas'),
            ('menu_ventas_reportes', 'Acceso: Reportes de Ventas'),
            ('menu_ventas_autorizaciones', 'Acceso: Lista de Autorizaciones'),
            
            # Stock y Logística
            ('menu_stock', 'Acceso: Módulo Stock (Padre)'),
            ('menu_stock_dashboard', 'Acceso: Mantenimiento de Productos y Stock'),
            ('menu_stock_recepciones', 'Acceso: Recepción de Mercadería'),
            ('menu_stock_remitos_internos', 'Acceso: Remitos Internos'),
            ('menu_stock_recepcion_interna', 'Acceso: Recepción Interna'),
            
            # Tesorería
            ('menu_tesoreria', 'Acceso: Módulo Tesorería (Padre)'),
            ('menu_tesoreria_recibos', 'Acceso: Emitir Recibo'),
            ('menu_tesoreria_orden_pago', 'Acceso: Emitir Orden Pago'),
            ('menu_tesoreria_caja', 'Acceso: Operar Caja Mostrador'),
            ('menu_tesoreria_caja_diaria', 'Acceso: Caja Diaria'),
            ('menu_tesoreria_eoaf', 'Acceso: Origen y Aplicación de Fondos'),
            ('menu_tesoreria_rendiciones', 'Acceso: Recepción de Rendiciones'),

            # Contable
            ('menu_contable', 'Acceso: Módulo Contable (Padre)'),
            ('menu_contable_libro_diario', 'Acceso: Libro Diario'),
            ('menu_contable_libro_mayor', 'Acceso: Libro Mayor'),
            ('menu_contable_balance', 'Acceso: Balance de Sumas y Saldos'),
            ('menu_contable_saldos', 'Acceso: Saldos Mensuales'),

            # Impuestos
            ('menu_impuestos', 'Acceso: Módulo Impuestos (Padre)'),
            ('menu_impuestos_cierre_iva', 'Acceso: Cierre Periodo IVA'),
            ('menu_impuestos_libro_ventas', 'Acceso: Libro IVA Ventas'),
            ('menu_impuestos_libro_compras', 'Acceso: Libro IVA Compras'),
            ('menu_impuestos_arca', 'Acceso: Captura Mis Comprobantes ARCA'),
            ('menu_impuestos_sicore', 'Acceso: SICORE - Retención Impuesto a las Ganancias'),

            # Configuración
            ('menu_configuracion', 'Acceso: Módulo Configuración (Solo Administradores)'),
        ]

    def __str__(self):
        return f"{self.usuario.username} - Perfil"

class PermisoDenegado(models.Model):
    """
    Registra permisos que han sido explícitamente denegados a un usuario,
    incluso si los hereda a través de un rol (grupo).
    """
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='permisos_denegados')
    permiso = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Permiso Denegado'
        verbose_name_plural = 'Permisos Denegados'
        unique_together = ('usuario', 'permiso')

    def __str__(self):
        return f"{self.usuario.username} denegado: {self.permiso.codename}"
