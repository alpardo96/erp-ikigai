from django.db import models
from core.models import AuditModel

class Empresa(AuditModel):
    nombre = models.CharField(max_length=150, verbose_name="Nombre de la Empresa")
    cuit = models.CharField(max_length=11, unique=True, verbose_name="CUIT")
    logo = models.ImageField(upload_to='logos/', null=True, blank=True, verbose_name="Logo")
    direccion = models.CharField(max_length=255, null=True, blank=True, verbose_name="Dirección")
    correo = models.EmailField(null=True, blank=True, verbose_name="Correo Electrónico")
    telefono = models.CharField(max_length=255, null=True, blank=True, verbose_name="Teléfono(s)")
    TIPO_ACTIVIDAD_CHOICES = [
        ('', 'Estándar (General)'),
        ('ARMERIA', 'Armería'),
        ('DISTRIBUCION', 'Distribución'),
        ('ESTUDIO', 'Estudio Contable / Jurídico'),
        ('AGRICOLA', 'Empresa Agrícola'),
        ('COLEGIO', 'Colegio'),
    ]
    tipo_actividad = models.CharField(
        max_length=100, null=True, blank=True,
        choices=TIPO_ACTIVIDAD_CHOICES,
        verbose_name="Tipo de Actividad Especial",
        help_text="Filtro para habilitar funcionalidades específicas de una verticalidad."
    )
    pedir_fecha_nacimiento_cliente = models.BooleanField(default=False, verbose_name="Pedir Fecha Nacimiento en Clientes")
    usa_orden_compra = models.BooleanField(
        default=False,
        verbose_name="Usa Órdenes de Compra",
        help_text="Si está activo, el circuito de compras inicia por una Orden de Compra prenumerada."
    )
    usa_trazabilidad = models.BooleanField(
        default=False,
        verbose_name="Usa Trazabilidad de Productos",
        help_text="Si está activo, se habilita la carga y control por número de serie en compras y ventas."
    )
    MODO_EDICION_CHOICES = [
        ('DESCUENTO', 'Editar Descuento (%)'),
        ('PRECIO', 'Editar Precio Unitario'),
    ]
    modo_edicion_facturacion = models.CharField(
        max_length=10,
        choices=MODO_EDICION_CHOICES,
        default='DESCUENTO',
        verbose_name="Modo de Edición en Facturación",
        help_text="Define si en Preventas, Ventas y Trazabilidad se edita el precio unitario directamente o el descuento porcentual."
    )

    # Datos Impositivos de la Empresa
    CONDICION_IVA_CHOICES = [
        ('RESPONSABLE INSCRIPTO', 'Responsable Inscripto'),
        ('MONOTRIBUTO', 'Monotributo'),
        ('EXENTO', 'Exento'),
        ('CONSUMIDOR FINAL', 'Consumidor Final'),
    ]
    condicion_iva = models.CharField(
        max_length=50,
        choices=CONDICION_IVA_CHOICES,
        default='CONSUMIDOR FINAL',
        verbose_name="Condición IVA"
    )
    fecha_inicio_actividades = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Inicio de Actividades"
    )

    # Ingresos Brutos
    CONDICION_IIBB = [
        ('LOCAL', 'Contribuyente Local'),
        ('CM', 'Convenio Multilateral'),
        ('EXENTO', 'Exento / No Inscripto'),
    ]
    condicion_iibb = models.CharField(max_length=10, choices=CONDICION_IIBB, default='LOCAL', verbose_name="Condición Ingresos Brutos")
    jurisdicciones_iibb = models.ManyToManyField(
        'facturacion.Jurisdiccion', blank=True, related_name='empresas',
        verbose_name="Jurisdicciones IIBB inscriptas",
        help_text="Contribuyente Local: una jurisdicción. Convenio Multilateral: todas las inscriptas."
    )

    # Configuración ARCA (Facturación Electrónica WSFEv1)
    ENTORNO_AFIP_CHOICES = [
        ('HOMO', 'Homologación (Testing)'),
        ('PROD', 'Producción'),
    ]
    entorno_afip = models.CharField(max_length=4, choices=ENTORNO_AFIP_CHOICES, default='HOMO', verbose_name="Entorno ARCA (WSFEv1)")
    crt_afip = models.FileField(upload_to='certificados_afip/', null=True, blank=True, verbose_name="Certificado ARCA (.crt)")
    key_afip = models.FileField(upload_to='certificados_afip/', null=True, blank=True, verbose_name="Clave Privada ARCA (.key)")
    vencimiento_crt_afip = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Vencimiento Certificado ARCA",
        help_text="Fecha de expiración del certificado digital ARCA (.crt). Se autodetecta al subir el certificado."
    )

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"

    def __str__(self):
        return f"{self.nombre} ({self.cuit})"

    def extraer_vencimiento_crt(self):
        """
        Extrae la fecha de vencimiento del certificado digital (.crt) almacenado en self.crt_afip.
        Usa la librería cryptography para inspeccionar la validez (notAfter / not_valid_after_utc).
        Retorna un objeto date o None si falla.
        """
        if not self.crt_afip:
            return None
        try:
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend
            import os

            if not os.path.exists(self.crt_afip.path):
                return None

            with open(self.crt_afip.path, 'rb') as f:
                cert_data = f.read()

            try:
                cert = x509.load_pem_x509_certificate(cert_data, default_backend())
            except Exception:
                cert = x509.load_der_x509_certificate(cert_data, default_backend())

            try:
                dt = cert.not_valid_after_utc
            except AttributeError:
                dt = cert.not_valid_after
            return dt.date()
        except Exception:
            return None

    @property
    def dias_hasta_vencimiento_crt(self):
        """
        Calcula la cantidad de días enteros faltantes desde hoy hasta la fecha de vencimiento del certificado.
        - Retorna >= 0 si vigencia es hoy o futura.
        - Retorna < 0 si el certificado ya expiró.
        - Retorna None si no hay fecha definida.
        """
        if not self.vencimiento_crt_afip:
            return None
        from datetime import date
        return (self.vencimiento_crt_afip - date.today()).days

    @property
    def estado_vencimiento_crt(self):
        """
        Retorna un diccionario estructurado con el estado de vigencia del certificado:
        - tiene_certificado: bool
        - vencimiento: date o None
        - dias: int o None
        - es_vencido: bool
        - es_advertencia: bool (se activa con <= 15 días)
        - nivel: 'danger' | 'warning' | 'success' | 'none'
        - mensaje: str
        """
        if not self.crt_afip or not self.vencimiento_crt_afip:
            return {
                'tiene_certificado': bool(self.crt_afip),
                'vencimiento': self.vencimiento_crt_afip,
                'dias': None,
                'es_vencido': False,
                'es_advertencia': False,
                'nivel': 'none',
                'mensaje': 'No hay fecha de vencimiento configurada para el certificado digital ARCA.'
            }

        dias = self.dias_hasta_vencimiento_crt
        fecha_str = self.vencimiento_crt_afip.strftime('%d/%m/%Y')

        if dias < 0:
            dias_vencido = abs(dias)
            return {
                'tiene_certificado': True,
                'vencimiento': self.vencimiento_crt_afip,
                'dias': dias,
                'es_vencido': True,
                'es_advertencia': True,
                'nivel': 'danger',
                'mensaje': f'El certificado digital ARCA VENCIÓ hace {dias_vencido} día(s) (el {fecha_str}). La facturación electrónica puede estar inhabilitada.'
            }
        elif dias <= 15:
            nivel = 'danger' if dias <= 3 else 'warning'
            msg_dias = "HOY" if dias == 0 else f"en {dias} día(s)"
            return {
                'tiene_certificado': True,
                'vencimiento': self.vencimiento_crt_afip,
                'dias': dias,
                'es_vencido': False,
                'es_advertencia': True,
                'nivel': nivel,
                'mensaje': f'El certificado digital ARCA vencerá {msg_dias} (el {fecha_str}). Por favor renovarlo a la brevedad.'
            }
        else:
            return {
                'tiene_certificado': True,
                'vencimiento': self.vencimiento_crt_afip,
                'dias': dias,
                'es_vencido': False,
                'es_advertencia': False,
                'nivel': 'success',
                'mensaje': f'Certificado digital ARCA vigente hasta el {fecha_str} ({dias} días restantes).'
            }

    def save(self, *args, **kwargs):
        """
        Sobrescribe save para autodetectar la fecha de vencimiento si se cargó un .crt y vencimiento_crt_afip no fue provisto.
        """
        super().save(*args, **kwargs)
        if self.crt_afip and not self.vencimiento_crt_afip:
            fecha_venc = self.extraer_vencimiento_crt()
            if fecha_venc:
                self.vencimiento_crt_afip = fecha_venc
                super().save(update_fields=['vencimiento_crt_afip'])

class Sucursal(AuditModel):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="sucursales")
    nombre = models.CharField(max_length=150, verbose_name="Nombre de la Sucursal")
    direccion = models.CharField(max_length=255, null=True, blank=True, verbose_name="Dirección")
    telefono = models.CharField(max_length=50, null=True, blank=True, verbose_name="Teléfono")
    punto = models.IntegerField(
        default=1,
        verbose_name="Punto (numeración)",
        help_text="Número de punto de venta/emisión de la sucursal. Prenumera OC, Informes de Recepción y Remitos Internos."
    )

    class Meta:
        verbose_name = "Sucursal"
        verbose_name_plural = "Sucursales"

    def __str__(self):
        return f"{self.empresa.nombre} - {self.nombre}"

class PuntoVenta(AuditModel):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="puntos_venta")
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE, related_name="puntos_venta")
    numero = models.IntegerField(verbose_name="Punto de Venta", help_text="Número del punto de venta (hasta 5 dígitos)")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    caja_mostrador_default = models.BooleanField(
        default=False, 
        verbose_name="Predeterminado para Caja Mostrador",
        help_text="Si se marca, este será el punto de venta automático al facturar desde Caja Mostrador en esta sucursal."
    )

    class Meta:
        verbose_name = "Punto de Venta"
        verbose_name_plural = "Puntos de Venta"
        unique_together = ('empresa', 'sucursal', 'numero')
        
    def __str__(self):
        return f"{self.sucursal.nombre} - Punto {self.numero:04d}"
        
    def save(self, *args, **kwargs):
        if self.caja_mostrador_default:
            # Desmarcar otros puntos de la misma sucursal
            PuntoVenta.objects.filter(sucursal=self.sucursal).exclude(pk=self.pk).update(caja_mostrador_default=False)
        super().save(*args, **kwargs)

class Ejercicio(models.Model):
    """
    Ejercicio fiscal vinculado a una empresa.
    Define el período contable (inicio-cierre) para trazabilidad.
    Se usa como filtro general y se asigna silenciosamente en compras/ventas/movimientos.
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="ejercicios", verbose_name="Empresa")
    ejercicio = models.CharField(max_length=100, verbose_name="Nombre del Ejercicio")  # Ej: "Ikigai - 2026"
    inicio = models.DateField(verbose_name="Fecha de Inicio")
    cierre = models.DateField(verbose_name="Fecha de Cierre")

    class Meta:
        db_table = "empresas_ejercicio"
        verbose_name = "Ejercicio"
        verbose_name_plural = "Ejercicios"
        ordering = ['-inicio']  # Más reciente primero

    def __str__(self):
        return f"{self.ejercicio} ({self.inicio.strftime('%d/%m/%Y')} → {self.cierre.strftime('%d/%m/%Y')})"

    def clean(self):
        from django.core.exceptions import ValidationError
        # 1. Validar orden de fechas
        if self.inicio and self.cierre and self.inicio > self.cierre:
            raise ValidationError("La fecha de cierre debe ser posterior a la fecha de inicio.")

        # 2. Validar solapamientos para la misma empresa
        # Un rango (A, B) se solapa con (C, D) si: A <= D y C <= B
        overlaps = Ejercicio.objects.filter(
            empresa=self.empresa,
            inicio__lte=self.cierre,
            cierre__gte=self.inicio
        )

        if self.pk:
            overlaps = overlaps.exclude(pk=self.pk)

        if overlaps.exists():
            overlap = overlaps.first()
            raise ValidationError(
                f"Error: Las fechas elegidas se solapan con el ejercicio '{overlap.ejercicio}' "
                f"({overlap.inicio.strftime('%d/%m/%Y')} - {overlap.cierre.strftime('%d/%m/%Y')})."
            )

class CotizacionMoneda(AuditModel):
    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name="cotizacion_moneda")
    dolar_venta = models.DecimalField(max_digits=15, decimal_places=2, default=1.0, verbose_name="Dólar Venta")
    dolar_cobranza = models.DecimalField(max_digits=15, decimal_places=2, default=1.0, verbose_name="Dólar Cobranza")

    class Meta:
        verbose_name = "Cotización Moneda"
        verbose_name_plural = "Cotizaciones Moneda"

    def __str__(self):
        return f"Cotización de {self.empresa.nombre} (Venta: {self.dolar_venta}, Cobranza: {self.dolar_cobranza})"


class EmpresaTrazabilidad(AuditModel):
    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name="config_trazabilidad", verbose_name="Empresa")
    pedir_situacion = models.BooleanField(default=False, verbose_name="Pedir Situación al comprar subproductos")
    pedir_estado = models.BooleanField(default=False, verbose_name="Pedir Estado al comprar subproductos")
    pedir_cuim = models.BooleanField(default=False, verbose_name="Pedir CUIM/Dominio al comprar subproductos")

    class Meta:
        verbose_name = "Configuración de Trazabilidad"
        verbose_name_plural = "Configuraciones de Trazabilidad"

    def __str__(self):
        return f"Trazabilidad de {self.empresa.nombre}"

