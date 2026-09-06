"""Maestros del acopio de tabaco (Plan 081 — Etapa 0).

Acá viven SOLO los maestros y la configuración. Nada de esto tiene efecto contable, de stock ni
de cuenta corriente: eso llega con el romaneo (Etapa 1) y la liquidación (Etapa 2).

REGLAS DE LA VERTICALIDAD (Planes 075 y 078)
- Toda tabla lleva el prefijo `agricola_`.
- Se depende del core (empresas, productos, facturacion, contable); el core NUNCA depende de acá.
- Todo queryset se acota por la empresa activa del middleware.

EL PRECIO SE CONGELA, NO SE RECALCULA
Los coeficientes y los precios ponderantes se versionan por vigencia, y el comprobante que los
usa guarda una copia del valor aplicado. Un romaneo de marzo no puede cambiar de importe porque
en agosto se renegoció la lista: el precio de una operación es un hecho histórico.
"""
from decimal import Decimal

from django.db import models

from core.models import AuditModel
from empresas.models import Empresa
from verticalidades.agricola.core_agricola.models import Campania


class ConfiguracionTabaco(AuditModel):
    """Parámetros del negocio de acopio, por empresa.

    Se separa de `EmpresaVertical` a propósito: aquélla es el interruptor de qué submódulos están
    activos y nada más; acá se acumulan los parámetros operativos, que van a seguir creciendo.
    """
    MANUAL, WEBSERVICE = 'MANUAL', 'WEBSERVICE'
    MODOS_AUTORIZACION = [
        (MANUAL, 'Manual (talonario con CAI o comprobante en línea)'),
        (WEBSERVICE, 'Webservice ARCA'),
    ]

    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name='config_tabaco')

    cuenta_bienes_cambio = models.ForeignKey(
        'contable.Cuenta', on_delete=models.PROTECT, null=True, blank=True,
        related_name='+', verbose_name="Cuenta de Bienes de Cambio (Tabaco)",
        help_text="Cuenta patrimonial que se debita al liquidar la compra al productor.",
    )
    punto_venta = models.IntegerField(default=1, verbose_name="Punto de Venta de la Liquidación")

    # La liquidación es un comprobante que EMITIMOS nosotros y que va al Libro IVA COMPRAS.
    # Hoy se carga a mano desde talonario o desde el comprobante en línea de ARCA; el webservice
    # (WSLTV) queda previsto en el modelo y se implementa más adelante.
    modo_autorizacion = models.CharField(
        max_length=12, choices=MODOS_AUTORIZACION, default=MANUAL,
        verbose_name="Modo de autorización",
    )
    cai = models.CharField(max_length=20, blank=True, verbose_name="CAI vigente")
    cai_vencimiento = models.DateField(null=True, blank=True, verbose_name="Vencimiento del CAI")

    tolerancia_pesaje = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0.00'),
        verbose_name="Tolerancia de pesaje (kg)",
        help_text="Diferencia admitida entre el peso declarado y el pesado en balanza.",
    )

    class Meta:
        db_table = "agricola_tabaco_configuracion"
        verbose_name = "Configuración de Acopio de Tabaco"
        verbose_name_plural = "Configuraciones de Acopio de Tabaco"

    def __str__(self):
        return f"Configuración de Acopio: {self.empresa.nombre}"


class VariedadTabaco(AuditModel):
    """Variedad de tabaco. En el maestro heredado hay dos: Burley y Virginia.

    `producto` es el enganche con el stock: la Etapa 4 va a registrar un término que mueve
    existencias por variedad, en kilos. La clase NO es un producto distinto — una reclasificación
    no cambia lo que hay en el galpón, así que no debe mover stock.
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='variedades_tabaco')
    codigo = models.IntegerField(verbose_name="Código")
    detalle = models.CharField(max_length=60, verbose_name="Variedad")
    producto = models.ForeignKey(
        'productos.Producto', on_delete=models.PROTECT, null=True, blank=True,
        related_name='variedades_tabaco', verbose_name="Producto de stock",
        help_text="Producto contra el que se acumulan los kilos de esta variedad.",
    )
    activa = models.BooleanField(default=True)

    class Meta:
        db_table = "agricola_tabaco_variedad"
        verbose_name = "Variedad de Tabaco"
        verbose_name_plural = "Variedades de Tabaco"
        ordering = ['codigo']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'codigo'], name='agro_tab_variedad_codigo_unico'),
        ]

    def __str__(self):
        return self.detalle

    def save(self, *args, **kwargs):
        if self.detalle:
            self.detalle = self.detalle.strip().upper()
        super().save(*args, **kwargs)


class ClaseTabaco(AuditModel):
    """Clase de tabaco y su coeficiente sobre el precio ponderante.

    El coeficiente va con 4 decimales aunque el maestro heredado traiga 2: multiplica un precio
    por miles de kilos, así que el redondeo se nota, y las listas negociadas pueden traer más
    precisión que la que hoy existe.

    `grupo` es la primera letra del código de clase (B, C, X, T, N, H). El sistema anterior
    agrupaba kilos y fardos por ese prefijo, pero lo tenía cableado como una lista fija de cinco
    letras y por eso dejaba afuera al grupo H de Virginia. Acá se deriva del dato.
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='clases_tabaco')
    variedad = models.ForeignKey(VariedadTabaco, on_delete=models.PROTECT, related_name='clases')
    codigo = models.IntegerField(verbose_name="Código")
    detalle = models.CharField(max_length=10, verbose_name="Clase")
    grupo = models.CharField(max_length=2, blank=True, db_index=True, verbose_name="Grupo")
    coeficiente = models.DecimalField(
        max_digits=6, decimal_places=4, verbose_name="Coeficiente",
        help_text="Proporción del precio ponderante. La clase índice vale 1,0000.",
    )
    activa = models.BooleanField(default=True)

    class Meta:
        db_table = "agricola_tabaco_clase"
        verbose_name = "Clase de Tabaco"
        verbose_name_plural = "Clases de Tabaco"
        ordering = ['variedad', 'codigo']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'variedad', 'codigo'],
                                    name='agro_tab_clase_codigo_unico'),
            models.UniqueConstraint(fields=['empresa', 'variedad', 'detalle'],
                                    name='agro_tab_clase_detalle_unico'),
            models.CheckConstraint(condition=models.Q(coeficiente__gt=0),
                                   name='agro_tab_clase_coeficiente_positivo'),
        ]
        indexes = [models.Index(fields=['empresa', 'variedad', 'activa'])]

    def __str__(self):
        return f"{self.detalle} ({self.coeficiente})"

    def save(self, *args, **kwargs):
        if self.detalle:
            self.detalle = self.detalle.strip().upper()
            if not self.grupo:
                self.grupo = self.detalle[:1]
        super().save(*args, **kwargs)


class ListaPrecioTabaco(AuditModel):
    """Precio ponderante por variedad y campaña, con vigencia.

    En el sistema heredado el ponderante era un campo suelto de la variedad: al cambiarlo se
    reescribía el precio de todo lo ya comprado. Acá se versiona, y el romaneo guarda copia del
    ponderante que aplicó.

    `aprobada` existe porque una lista en borrador no puede formar precios: el ponderante se
    negocia y hasta que no está cerrado no debe poder liquidarse contra él.
    """
    MONEDAS = [('PES', 'Peso'), ('DOL', 'Dólar'), ('EUR', 'Euro')]

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='listas_precio_tabaco')
    variedad = models.ForeignKey(VariedadTabaco, on_delete=models.PROTECT, related_name='listas_precio')
    campania = models.ForeignKey(Campania, on_delete=models.PROTECT, related_name='listas_precio_tabaco')

    vigencia_desde = models.DateField(verbose_name="Vigente desde")
    vigencia_hasta = models.DateField(null=True, blank=True, verbose_name="Vigente hasta")

    moneda = models.CharField(max_length=3, choices=MONEDAS, default='PES')
    precio_ponderante = models.DecimalField(max_digits=15, decimal_places=2,
                                            verbose_name="Precio Ponderante ($/kg)")

    aprobada = models.BooleanField(default=False, verbose_name="Aprobada")
    aprobada_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='+', verbose_name="Aprobada por")
    aprobada_el = models.DateTimeField(null=True, blank=True, verbose_name="Aprobada el")

    class Meta:
        db_table = "agricola_tabaco_lista_precio"
        verbose_name = "Lista de Precio de Tabaco"
        verbose_name_plural = "Listas de Precio de Tabaco"
        ordering = ['-vigencia_desde']
        constraints = [
            models.CheckConstraint(condition=models.Q(precio_ponderante__gt=0),
                                   name='agro_tab_lista_precio_positivo'),
            models.CheckConstraint(
                condition=models.Q(vigencia_hasta__isnull=True)
                | models.Q(vigencia_hasta__gte=models.F('vigencia_desde')),
                name='agro_tab_lista_vigencia_coherente',
            ),
        ]
        indexes = [models.Index(fields=['empresa', 'variedad', 'campania', 'vigencia_desde'])]

    def __str__(self):
        return f"{self.variedad} {self.campania} — {self.precio_ponderante}"


class TipoRetencionTabaco(AuditModel):
    """Concepto de retención que el acopiador practica al productor.

    NADA EN ESTE MODELO ES ESPECÍFICO DE TABACO, y es a propósito: hoy Ikigai no sabe practicar
    retenciones (`contable.RetPercSufrida` es explícitamente para las que nos practican a
    nosotros). Cuando otra empresa sea agente de retención, esta tabla se promueve al core sin
    reescribirla.

    `tipo_base` distingue las tres formas que se usan realmente:
      NETO         — porcentaje sobre el neto de la liquidación (EEAOC, Uso de Agua, Salud Pública)
      IVA          — porcentaje sobre el IVA del comprobante (Ret. IVA: 50 % del IVA)
      ACUM_MENSUAL — porcentaje sobre lo acumulado del mes menos el mínimo no imponible (Ganancias)

    `momento` decide dónde nace el pasivo. No es un detalle: si un concepto se practicara en la
    liquidación Y en el pago, se contabilizaría dos veces. Ganancias va en el pago porque su base
    es el acumulado mensual de lo pagado.
    """
    NETO, IVA, ACUM_MENSUAL = 'NETO', 'IVA', 'ACUM_MENSUAL'
    TIPOS_BASE = [
        (NETO, 'Porcentaje sobre el neto'),
        (IVA, 'Porcentaje sobre el IVA'),
        (ACUM_MENSUAL, 'Acumulado mensual menos mínimo no imponible'),
    ]

    LIQUIDACION, PAGO = 'LIQUIDACION', 'PAGO'
    MOMENTOS = [(LIQUIDACION, 'Al liquidar'), (PAGO, 'Al pagar')]

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='retenciones_tabaco')
    codigo = models.CharField(max_length=15, verbose_name="Código")
    detalle = models.CharField(max_length=80, verbose_name="Concepto")

    organismo = models.CharField(max_length=80, blank=True, verbose_name="Organismo recaudador")
    jurisdiccion = models.ForeignKey('facturacion.Jurisdiccion', on_delete=models.PROTECT,
                                     null=True, blank=True, related_name='+')
    regimen = models.CharField(max_length=15, blank=True, verbose_name="Régimen")

    tipo_base = models.CharField(max_length=12, choices=TIPOS_BASE, default=NETO,
                                 verbose_name="Base de cálculo")
    alicuota = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal('0'),
                                   verbose_name="Alícuota %")
    minimo_no_imponible = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'),
                                              verbose_name="Mínimo no imponible")

    momento = models.CharField(max_length=12, choices=MOMENTOS, default=LIQUIDACION,
                               verbose_name="Momento en que se practica")
    solo_responsable_inscripto = models.BooleanField(
        default=False, verbose_name="Sólo a Responsables Inscriptos",
        help_text="La retención de IVA y la de Ganancias sólo aplican a RI.",
    )

    cuenta_contable = models.ForeignKey(
        'contable.Cuenta', on_delete=models.PROTECT, related_name='+',
        verbose_name="Cuenta de pasivo",
        help_text="Cuenta que se acredita al retener y que se cancela al depositar al organismo.",
    )

    vigencia_desde = models.DateField(verbose_name="Vigente desde")
    vigencia_hasta = models.DateField(null=True, blank=True, verbose_name="Vigente hasta")
    activa = models.BooleanField(default=True)

    class Meta:
        db_table = "agricola_tabaco_tipo_retencion"
        verbose_name = "Concepto de Retención (Tabaco)"
        verbose_name_plural = "Conceptos de Retención (Tabaco)"
        ordering = ['codigo', '-vigencia_desde']
        constraints = [
            models.CheckConstraint(condition=models.Q(alicuota__gte=0),
                                   name='agro_tab_ret_alicuota_no_neg'),
            models.CheckConstraint(condition=models.Q(minimo_no_imponible__gte=0),
                                   name='agro_tab_ret_mni_no_neg'),
            models.CheckConstraint(
                condition=models.Q(vigencia_hasta__isnull=True)
                | models.Q(vigencia_hasta__gte=models.F('vigencia_desde')),
                name='agro_tab_ret_vigencia_coherente',
            ),
        ]
        indexes = [models.Index(fields=['empresa', 'momento', 'activa'])]

    def __str__(self):
        return f"{self.codigo} - {self.detalle}"

    def save(self, *args, **kwargs):
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        if self.detalle:
            self.detalle = self.detalle.strip().upper()
        super().save(*args, **kwargs)


class ProductorTabaco(AuditModel):
    """Extensión sectorial del productor. El tercero vive en `facturacion.ClienteProveedor`.

    Acá van SÓLO los atributos que el core no tiene: el código FET (Fondo Especial del Tabaco),
    la finca de origen y la habilitación. La razón social, el CUIT y la condición de IVA —de la
    que depende si la liquidación sale A o B— se leen del maestro de terceros, nunca se duplican.
    """
    cliente_proveedor = models.OneToOneField(
        'facturacion.ClienteProveedor', on_delete=models.CASCADE,
        related_name='productor_tabaco', verbose_name="Tercero",
    )
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='productores_tabaco')

    codigo_fet = models.CharField(max_length=20, blank=True, db_index=True,
                                  verbose_name="Código FET")
    finca_origen = models.CharField(max_length=120, blank=True, verbose_name="Finca / Origen")
    coeficiente = models.DecimalField(
        max_digits=6, decimal_places=4, default=Decimal('1'),
        verbose_name="Coeficiente del productor",
        help_text="Dato de referencia del productor. NO interviene en el cálculo del precio.",
    )
    habilitado = models.BooleanField(default=True, verbose_name="Habilitado para operar")
    observaciones = models.TextField(blank=True)

    class Meta:
        db_table = "agricola_tabaco_productor"
        verbose_name = "Productor de Tabaco"
        verbose_name_plural = "Productores de Tabaco"
        indexes = [models.Index(fields=['empresa', 'habilitado'])]

    def __str__(self):
        return f"{self.cliente_proveedor.razon_social}"


# ==============================================================================
# ROMANEO — recepción y clasificación por fardo (Plan 082, Etapa 1)
# ==============================================================================
# El romaneo es un hecho FÍSICO y COMERCIAL: entra la mercadería del productor, se pesa y se
# clasifica fardo por fardo. NO genera deuda, ni asiento, ni movimiento de stock. Eso llega al
# liquidar (Etapa 2) y al registrar el término de stock (Etapa 4).
#
# Separar el romaneo de la liquidación no es prolijidad: son hechos que ocurren en momentos
# distintos, los hacen personas distintas y se corrigen por separado. Un fardo mal clasificado se
# reclasifica sin tocar la deuda; una liquidación mal hecha se anula sin borrar la recepción.


class RomaneoTabaco(AuditModel):
    """Recepción y clasificación de una entrega del productor.

    Se abre en BORRADOR y se cargan los fardos como filas —no en sesión: un romaneo real tiene
    cientos de fardos, y si el navegador se cae no se puede perder el trabajo—. Al confirmar toma
    número de la serie correlativa y queda bloqueado para edición.
    """
    BORRADOR, CONFIRMADO, LIQUIDADO, ANULADO = 1, 2, 3, 9
    ESTADOS = [
        (BORRADOR, 'Borrador'),
        (CONFIRMADO, 'Confirmado'),
        (LIQUIDADO, 'Liquidado'),
        (ANULADO, 'Anulado'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='romaneos_tabaco')
    sucursal = models.ForeignKey('empresas.Sucursal', on_delete=models.PROTECT,
                                 related_name='romaneos_tabaco')

    punto = models.IntegerField(default=1, verbose_name="Punto")
    # Nulo mientras es borrador: el número se toma al confirmar para no dejar huecos en la serie.
    numero = models.BigIntegerField(null=True, blank=True, db_index=True, verbose_name="Número")

    fecha = models.DateField(db_index=True, verbose_name="Fecha")
    productor = models.ForeignKey('facturacion.ClienteProveedor', on_delete=models.PROTECT,
                                  related_name='romaneos_tabaco', verbose_name="Productor")
    variedad = models.ForeignKey(VariedadTabaco, on_delete=models.PROTECT, related_name='romaneos')
    campania = models.ForeignKey(Campania, on_delete=models.PROTECT, related_name='romaneos_tabaco')

    # LA LISTA Y EL PONDERANTE SE CONGELAN. Guardar sólo la FK no alcanza: alguien podría corregir
    # el precio de la lista y cambiar en silencio el importe de un romaneo ya cerrado.
    lista_precio = models.ForeignKey(ListaPrecioTabaco, on_delete=models.PROTECT,
                                     related_name='romaneos', verbose_name="Lista aplicada")
    ponderante_aplicado = models.DecimalField(max_digits=15, decimal_places=2,
                                              verbose_name="Ponderante aplicado")
    coeficiente_productor = models.DecimalField(
        max_digits=6, decimal_places=4, default=Decimal('1'),
        verbose_name="Coeficiente del productor",
        help_text="Dato informativo del productor. NO interviene en el cálculo del precio.")

    transporte = models.CharField(max_length=120, blank=True, verbose_name="Transporte / Vehículo")
    remito = models.CharField(max_length=40, blank=True, verbose_name="Remito o guía")
    observaciones = models.TextField(blank=True)

    # Derivados del detalle. Se materializan porque se leen en todo listado, pero la fuente de
    # verdad son los fardos: `recalcular_totales()` los reconstruye enteros, nunca por delta.
    total_kilos = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    total_fardos = models.IntegerField(default=0)
    total_importe = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    adicional = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    precio_promedio = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'),
                                          verbose_name="Precio promedio ponderado")
    porcentaje_ponderante = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'),
                                                verbose_name="% sobre el ponderante")

    estado = models.IntegerField(choices=ESTADOS, default=BORRADOR, db_index=True)
    # 1=Real, 2=Presupuestado, 3=Ajuste, 4=Auditoría. Lo hereda la liquidación y, con ella, el
    # asiento. Tabla completa en `.cursorrules`.
    condic = models.IntegerField(default=1, verbose_name="Condición")

    motivo_anulacion = models.CharField(max_length=200, blank=True)
    anulado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='+')
    anulado_el = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agricola_tabaco_romaneo"
        verbose_name = "Romaneo de Tabaco"
        verbose_name_plural = "Romaneos de Tabaco"
        ordering = ['-fecha', '-numero']
        constraints = [
            # Condicional: los borradores todavía no tienen número y no deben chocar entre sí.
            models.UniqueConstraint(fields=['empresa', 'punto', 'numero'],
                                    condition=models.Q(numero__isnull=False),
                                    name='agro_tab_romaneo_numero_unico'),
            models.CheckConstraint(condition=models.Q(total_kilos__gte=0),
                                   name='agro_tab_romaneo_kilos_no_neg'),
            models.CheckConstraint(condition=models.Q(total_fardos__gte=0),
                                   name='agro_tab_romaneo_fardos_no_neg'),
        ]
        indexes = [
            models.Index(fields=['empresa', 'estado', '-fecha']),
            models.Index(fields=['empresa', 'productor', '-fecha']),
            models.Index(fields=['empresa', 'campania', 'variedad']),
        ]

    def __str__(self):
        numero = f"{self.punto:04d}-{self.numero:08d}" if self.numero else "BORRADOR"
        return f"Romaneo {numero} - {self.productor.razon_social}"

    @property
    def editable(self):
        return self.estado == self.BORRADOR


class FardoTabaco(AuditModel):
    """Un fardo del romaneo. Cada fila del detalle es un fardo físico.

    Guarda el coeficiente y el precio con los que se valorizó, no sólo la FK a la clase: es lo que
    permite reconstruir el importe años después aunque el maestro haya cambiado, y lo que hace
    verificable la liquidación que se le entrega al productor.
    """
    RECIBIDO, CLASIFICADO, EN_LOTE, ACONDICIONADO, VENDIDO = 1, 2, 3, 4, 5
    ESTADOS = [
        (RECIBIDO, 'Recibido'),
        (CLASIFICADO, 'Clasificado'),
        (EN_LOTE, 'En lote de acopio'),
        (ACONDICIONADO, 'Acondicionado'),
        (VENDIDO, 'Vendido'),
    ]

    romaneo = models.ForeignKey(RomaneoTabaco, on_delete=models.CASCADE, related_name='fardos')
    numero_fardo = models.IntegerField(verbose_name="Nro de fardo")
    etiqueta = models.CharField(max_length=40, blank=True, db_index=True,
                                verbose_name="Etiqueta / código de barras")

    clase = models.ForeignKey(ClaseTabaco, on_delete=models.PROTECT, related_name='fardos')
    coeficiente_aplicado = models.DecimalField(max_digits=6, decimal_places=4,
                                               verbose_name="Coeficiente aplicado")
    precio_aplicado = models.DecimalField(max_digits=15, decimal_places=2,
                                          verbose_name="Precio unitario aplicado")

    kilos = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Kilos")
    importe = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    adicional = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    precio_final = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'),
                                       verbose_name="Precio final (con adicional)")

    estado = models.IntegerField(choices=ESTADOS, default=CLASIFICADO, db_index=True)
    clasificado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True,
                                        blank=True, related_name='+')
    clasificado_el = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agricola_tabaco_fardo"
        verbose_name = "Fardo de Tabaco"
        verbose_name_plural = "Fardos de Tabaco"
        ordering = ['romaneo', 'numero_fardo']
        constraints = [
            models.UniqueConstraint(fields=['romaneo', 'numero_fardo'],
                                    name='agro_tab_fardo_numero_unico'),
            models.CheckConstraint(condition=models.Q(kilos__gt=0),
                                   name='agro_tab_fardo_kilos_positivos'),
            models.CheckConstraint(condition=models.Q(importe__gte=0),
                                   name='agro_tab_fardo_importe_no_neg'),
            models.CheckConstraint(condition=models.Q(coeficiente_aplicado__gt=0),
                                   name='agro_tab_fardo_coeficiente_positivo'),
        ]
        indexes = [
            models.Index(fields=['romaneo', 'clase']),
            models.Index(fields=['estado']),
        ]

    def __str__(self):
        return f"Fardo {self.numero_fardo} - {self.clase.detalle} - {self.kilos} kg"


class ReclasificacionFardo(models.Model):
    """Versión anterior de la clasificación de un fardo.

    LA CLASIFICACIÓN ORIGINAL NO SE SOBRESCRIBE. Reclasificar deja acá la clase, el coeficiente y
    el precio que tenía antes, con motivo y usuario. El fardo queda con los valores nuevos, pero
    la historia es reconstruible: es la diferencia entre corregir un error y borrar la evidencia
    de que existió.
    """
    fardo = models.ForeignKey(FardoTabaco, on_delete=models.CASCADE,
                              related_name='reclasificaciones')

    clase_anterior = models.ForeignKey(ClaseTabaco, on_delete=models.PROTECT, related_name='+')
    coeficiente_anterior = models.DecimalField(max_digits=6, decimal_places=4)
    precio_anterior = models.DecimalField(max_digits=15, decimal_places=2)
    importe_anterior = models.DecimalField(max_digits=15, decimal_places=2)

    clase_nueva = models.ForeignKey(ClaseTabaco, on_delete=models.PROTECT, related_name='+')
    coeficiente_nuevo = models.DecimalField(max_digits=6, decimal_places=4)
    precio_nuevo = models.DecimalField(max_digits=15, decimal_places=2)
    importe_nuevo = models.DecimalField(max_digits=15, decimal_places=2)

    kilos = models.DecimalField(max_digits=12, decimal_places=2)
    motivo = models.CharField(max_length=200, verbose_name="Motivo")
    usuario = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='+')
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "agricola_tabaco_reclasificacion"
        verbose_name = "Reclasificación de Fardo"
        verbose_name_plural = "Reclasificaciones de Fardos"
        ordering = ['-fecha']
        indexes = [models.Index(fields=['fardo', '-fecha'])]

    def __str__(self):
        return (f"Fardo {self.fardo.numero_fardo}: "
                f"{self.clase_anterior.detalle} -> {self.clase_nueva.detalle}")
