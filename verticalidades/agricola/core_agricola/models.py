"""Modelos transversales de la verticalidad Agrícola.

Acá vive lo que comparten tabaco, granos y —más adelante— caña. Lo específico de cada negocio
va en su sub-app. Todas las tablas llevan el prefijo `agricola_` (Plan 078).
"""
from decimal import Decimal
from django.db import models

from core.models import AuditModel
from empresas.models import Empresa



class EmpresaVertical(models.Model):
    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name="agricola_vertical")
    hace_acopio_tabaco = models.BooleanField(default=False, verbose_name="Acopio de Tabaco")
    hace_granos = models.BooleanField(default=False, verbose_name="Granos (Soja, Maíz, Poroto, etc.)")
    hace_tabaco = models.BooleanField(default=False, verbose_name="Tabaco (Cultivo)")
    hace_cana = models.BooleanField(default=False, verbose_name="Caña de Azúcar")

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


class Finca(AuditModel):
    """Establecimiento / Campo de la empresa agrícola."""
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='fincas_agricolas')
    codigo = models.CharField(max_length=20, verbose_name="Código")
    nombre = models.CharField(max_length=150, verbose_name="Nombre del Establecimiento / Finca")
    localidad = models.CharField(max_length=100, blank=True, verbose_name="Localidad")
    provincia = models.CharField(max_length=100, blank=True, verbose_name="Provincia")
    superficie_total_ha = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Superficie Total (Ha)")
    es_propia = models.BooleanField(default=True, verbose_name="Campo Propio", help_text="Marcar si es propio o desmarcar si es arrendado")
    arrendatario_titular = models.CharField(max_length=150, blank=True, verbose_name="Titular / Propietario (si es arrendado)")
    activa = models.BooleanField(default=True, verbose_name="Activa")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        db_table = "agricola_finca"
        verbose_name = "Finca / Establecimiento"
        verbose_name_plural = "Fincas / Establecimientos"
        ordering = ['codigo', 'nombre']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'codigo'], name='agro_finca_codigo_unico'),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    @property
    def superficie_cultivable_ha(self):
        from decimal import Decimal
        return sum((s.superficie_ha for s in self.secciones.filter(activa=True)), Decimal('0.00'))

    def save(self, *args, **kwargs):
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        if self.nombre:
            self.nombre = self.nombre.strip().upper()
        super().save(*args, **kwargs)


class Seccion(AuditModel):
    """Sección / Lote Productivo / Cuadro dentro de una Finca."""
    APTITUD_CHOICES = [
        ('TABACO', 'Tabaco'),
        ('SOJA', 'Soja'),
        ('MAIZ', 'Maíz'),
        ('CANA', 'Caña de Azúcar'),
        ('POROTO', 'Poroto / Legumbres'),
        ('TRIGO', 'Trigo / Cereales'),
        ('PASTURA', 'Pastura / Ganadería'),
        ('MIXTO', 'Mixto / Rotación'),
        ('DESCANSO', 'En Descanso / Barbecho'),
        ('OTRO', 'Otro'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='secciones_agricolas')
    finca = models.ForeignKey(Finca, on_delete=models.CASCADE, related_name='secciones', verbose_name="Finca / Establecimiento")
    codigo = models.CharField(max_length=20, verbose_name="Código de Lote/Sección")
    nombre = models.CharField(max_length=150, verbose_name="Nombre / Identificación")
    superficie_ha = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Superficie Cultivable (Ha)")
    metros_lineales_surco = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name="Metros Lineales de Surco",
        help_text="Metros totales de surco en el lote (clave para análisis en Caña de Azúcar y Tabaco)."
    )
    distanciamiento_surco_m = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('1.60'),
        verbose_name="Distanciamiento entre Surcos (m)",
        help_text="Distancia entre centros de surco (ej. 1.60 m para Caña, 1.20 m para Tabaco)."
    )
    aptitud_principal = models.CharField(max_length=20, choices=APTITUD_CHOICES, default='MIXTO', verbose_name="Aptitud / Cultivo Principal")
    activa = models.BooleanField(default=True, verbose_name="Activa")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        db_table = "agricola_seccion"
        verbose_name = "Sección / Lote Productivo"
        verbose_name_plural = "Secciones / Lotes Productivos"
        ordering = ['finca', 'codigo']
        constraints = [
            models.UniqueConstraint(fields=['finca', 'codigo'], name='agro_seccion_codigo_unico'),
        ]

    def __str__(self):
        return f"{self.finca.codigo} / {self.codigo} - {self.nombre}"

    def save(self, *args, **kwargs):
        if self.finca_id and not self.empresa_id:
            self.empresa_id = self.finca.empresa_id
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        if self.nombre:
            self.nombre = self.nombre.strip().upper()
        super().save(*args, **kwargs)


# ==============================================================================
# CULTIVOS Y PLANIFICACIÓN DE SIEMBRAS
# ==============================================================================

class Cultivo(AuditModel):
    """Maestro de Cultivos / Especies agrícolas."""
    TIPO_CHOICES = [
        ('GRANO', 'Granos y Cereales (Soja, Maíz, Trigo, etc.)'),
        ('TABACO', 'Tabaco (Virginia, Burley, Criollo)'),
        ('CANA', 'Caña de Azúcar'),
        ('LEGUMBRE', 'Legumbres (Poroto Negro, Alubia, Garbanzo)'),
        ('FORRAJE', 'Forrajeras y Pasturas'),
        ('HORTICOLA', 'Hortícola / Frutícola'),
        ('OTRO', 'Otro Cultivo'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='cultivos_agricolas')
    codigo = models.CharField(max_length=20, verbose_name="Código")
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Cultivo / Variedad")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='GRANO', verbose_name="Tipo de Cultivo")
    producto_cosecha = models.ForeignKey(
        'productos.Producto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cultivos_cosechados',
        verbose_name="Producto de Stock Cosechado",
        help_text="Producto final del catálogo que se incrementa al cosechar"
    )
    ciclo_estimado_dias = models.IntegerField(default=120, verbose_name="Ciclo Estimado (Días)")
    color_identificador = models.CharField(max_length=20, default="#10b981", verbose_name="Color de Identificación")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        db_table = "agricola_cultivo"
        verbose_name = "Cultivo / Variedad"
        verbose_name_plural = "Cultivos / Variedades"
        ordering = ['tipo', 'nombre']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'codigo'], name='agro_cultivo_codigo_unico'),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    def save(self, *args, **kwargs):
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        if self.nombre:
            self.nombre = self.nombre.strip().upper()
        super().save(*args, **kwargs)


class LoteCampania(AuditModel):
    """Asignación de un Cultivo a un Lote/Sección en una Campaña específica."""
    ESTADO_CHOICES = [
        ('PLANIFICADO', 'Planificado'),
        ('SEMBRADO', 'Sembrado / En Crecimiento'),
        ('EN_COSECHA', 'En Cosecha'),
        ('COSECHADO', 'Cosechado / Finalizado'),
        ('FRACASADO', 'Fracasado / Pérdida'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='lotes_campania_agricolas')
    campania = models.ForeignKey(Campania, on_delete=models.PROTECT, related_name='lotes_asignados', verbose_name="Campaña")
    seccion = models.ForeignKey(Seccion, on_delete=models.CASCADE, related_name='campanias_asignadas', verbose_name="Sección / Lote")
    cultivo = models.ForeignKey(Cultivo, on_delete=models.PROTECT, related_name='lotes_sembrados', verbose_name="Cultivo")
    superficie_sembrada_ha = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Superficie Sembrada (Ha)")
    fecha_siembra = models.DateField(null=True, blank=True, verbose_name="Fecha de Siembra")
    fecha_cosecha_estimada = models.DateField(null=True, blank=True, verbose_name="Fecha Cosecha Estimada")
    fecha_cosecha_real = models.DateField(null=True, blank=True, verbose_name="Fecha Cosecha Real")
    rinde_estimado_kg_ha = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Rinde Estimado (kg/ha)")
    rinde_obtenido_kg_ha = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Rinde Obtenido (kg/ha)")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PLANIFICADO', verbose_name="Estado del Lote")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        db_table = "agricola_lote_campania"
        verbose_name = "Planificación de Lote por Campaña"
        verbose_name_plural = "Planificaciones de Lotes por Campaña"
        ordering = ['campania', 'seccion__finca', 'seccion']

    def __str__(self):
        return f"{self.campania.codigo} - {self.seccion} [{self.cultivo.nombre}]"


# ==============================================================================
# LABORES Y TAREAS CULTURALES (ÓRDENES DE TRABAJO / APLICACIONES)
# ==============================================================================

class TipoLabor(AuditModel):
    """Catálogo de tipos de labores agrícolas y tareas culturales."""
    CATEGORIA_CHOICES = [
        ('PREPARACION', 'Preparación de Suelo / Barbecho'),
        ('SIEMBRA', 'Siembra / Plantación / Almácigo'),
        ('PROTECCION', 'Protección / Pulverización / Fitosanitarios'),
        ('NUTRICION', 'Fertilización y Enmiendas'),
        ('MANEJO', 'Manejo Cultural / Desflore / Riego / Carpidas'),
        ('COSECHA', 'Cosecha / Zafra / Corte'),
        ('TRANSPORTE', 'Transporte y Logística'),
        ('OTRO', 'Otras Tareas'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='tipos_labor_agricolas')
    codigo = models.CharField(max_length=20, verbose_name="Código")
    nombre = models.CharField(max_length=120, verbose_name="Nombre de la Labor")
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='PROTECCION', verbose_name="Categoría")
    requiere_insumos = models.BooleanField(default=True, verbose_name="Consume Insumos / Agroquímicos")
    activa = models.BooleanField(default=True, verbose_name="Activa")

    class Meta:
        db_table = "agricola_tipo_labor"
        verbose_name = "Tipo de Labor Agrícola"
        verbose_name_plural = "Tipos de Labores Agrícolas"
        ordering = ['categoria', 'nombre']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'codigo'], name='agro_tipo_labor_codigo_unico'),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.get_categoria_display()})"

    def save(self, *args, **kwargs):
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        if self.nombre:
            self.nombre = self.nombre.strip().upper()
        super().save(*args, **kwargs)


class ParteTrabajo(AuditModel):
    """Registro de labor realizada u Orden de Trabajo en campo."""
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Planificada / Pendiente'),
        ('EN_PROCESO', 'En Proceso'),
        ('COMPLETADA', 'Completada / Aplicada'),
        ('ANULADA', 'Anulada'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='partes_trabajo_agricolas')
    numero = models.IntegerField(verbose_name="N° de Parte / Orden")
    campania = models.ForeignKey(Campania, on_delete=models.PROTECT, related_name='partes_trabajo', verbose_name="Campaña")
    finca = models.ForeignKey(Finca, on_delete=models.PROTECT, related_name='partes_trabajo', verbose_name="Finca / Establecimiento")
    seccion = models.ForeignKey(Seccion, on_delete=models.PROTECT, related_name='partes_trabajo', verbose_name="Sección / Lote")
    lote_campania = models.ForeignKey(LoteCampania, on_delete=models.SET_NULL, null=True, blank=True, related_name='partes_trabajo', verbose_name="Cultivo Lote Asignado")
    tipo_labor = models.ForeignKey(TipoLabor, on_delete=models.PROTECT, related_name='partes_trabajo', verbose_name="Tipo de Labor")
    fecha = models.DateField(verbose_name="Fecha de Ejecución")
    superficie_ha = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Superficie Trabajada (Ha)")
    metros_surco_trabajados = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name="Metros de Surco Trabajados",
        help_text="Metros lineales de surco ejecutados en la labor."
    )
    cantidad_surcos = models.IntegerField(
        default=0,
        verbose_name="Cantidad de Surcos",
        help_text="Número de surcos intervenidos en la tarea."
    )
    responsable = models.CharField(max_length=120, blank=True, verbose_name="Responsable / Capataz")
    contratista = models.ForeignKey(
        'facturacion.ClienteProveedor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='labores_contratadas',
        verbose_name="Contratista / Prestador de Servicio"
    )
    maquinaria = models.CharField(max_length=120, blank=True, verbose_name="Maquinaria / Equipo Utilizado")
    costo_servicio_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Costo Servicio/Labor ($)")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='COMPLETADA', verbose_name="Estado")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones / Condiciones climáticas")

    class Meta:
        db_table = "agricola_parte_trabajo"
        verbose_name = "Parte de Trabajo / Labor"
        verbose_name_plural = "Partes de Trabajo / Labores"
        ordering = ['-fecha', '-numero']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'numero'], name='agro_parte_trabajo_numero_unico'),
        ]

    def __str__(self):
        return f"Parte N° {self.numero:05d} - {self.finca.codigo} / {self.seccion.codigo} - {self.tipo_labor.nombre}"


class ParteTrabajoInsumo(models.Model):
    """Insumos aplicados / consumidos en una labor específica."""
    parte_trabajo = models.ForeignKey(ParteTrabajo, on_delete=models.CASCADE, related_name='insumos_aplicados')
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT, related_name='aplicaciones_agricolas', verbose_name="Insumo / Agroquímico")
    deposito_origen = models.ForeignKey('empresas.Sucursal', on_delete=models.PROTECT, null=True, blank=True, related_name='egresos_labores_agricolas', verbose_name="Depósito / Galpón Origen")
    dosis_ha = models.DecimalField(max_digits=10, decimal_places=3, default=0, verbose_name="Dosis por Ha")
    unidad_medida = models.CharField(max_length=30, default="LTS/HA", verbose_name="Unidad de Medida")
    cantidad_total = models.DecimalField(max_digits=12, decimal_places=3, default=0, verbose_name="Cantidad Total Aplicada")
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Costo Unitario ($)")
    costo_total = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name="Costo Total Insumo ($)")

    class Meta:
        db_table = "agricola_parte_trabajo_insumo"
        verbose_name = "Insumo Aplicado en Labor"
        verbose_name_plural = "Insumos Aplicados en Labores"

    def __str__(self):
        return f"{self.producto.detalle} ({self.cantidad_total} {self.unidad_medida})"

