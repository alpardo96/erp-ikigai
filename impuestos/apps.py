from django.apps import AppConfig


class ImpuestosConfig(AppConfig):
    """
    Configuración de la aplicación de Impuestos para el ERP Ikigai 2.
    Gestiona reportes fiscales, cierres de IVA, Libros IVA Ventas/Compras (Portal IVA ARCA),
    Captura de Mis Comprobantes y generación de archivos SICORE.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'impuestos'
    verbose_name = 'Gestión de Impuestos'
