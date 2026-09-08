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
    # Parámetro y no constante: la alícuota puede cambiar por norma, y una liquidación ya emitida
    # conserva la que le aplicó (se copia en `LiquidacionTabaco.alicuota_iva`).
    alicuota_iva = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('21.00'),
        verbose_name="Alícuota de IVA (%)",
        help_text="Se aplica al liquidar a productores Responsables Inscriptos.",
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

    # A qué columna de la planilla FET aporta este concepto (Plan 087).
    #
    # ES UN DATO DEL MAESTRO Y NO UNA DEDUCCIÓN DEL CÓDIGO, y el motivo es concreto: la primera
    # versión del reporte mapeaba las columnas por código exacto —`IVA`, `GANANCIAS`, `AGUA`— y
    # los conceptos reales estaban cargados como `RET-IVA`, `RET-GCIAS` y `USO AGUA`. Tres de las
    # cinco retenciones caían en «otras» y NADA FALLABA A LA VISTA, porque la fila seguía sumando
    # bien: la planilla mentía en silencio.
    #
    # Ahora se ve en pantalla, se edita desde el ABM y un concepto nuevo se asigna a propósito.
    # Vacío significa «Otras retenciones», que es una columna real de la planilla y no un error.
    COLUMNAS_FET = [
        ('ret_iva', 'Ret. IVA'),
        ('ret_ganancias', 'Ret. Ganancias'),
        ('ret_eeaoc', 'EEAOC'),
        ('ret_salud', 'Salud Pública'),
        ('ret_agua', 'Uso de Agua'),
    ]
    columna_fet = models.CharField(
        max_length=15, choices=COLUMNAS_FET, blank=True, verbose_name="Columna en la planilla FET",
        help_text="A qué columna del informe FET aporta. Vacío = «Otras retenciones».")
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

    # La relación con la liquidación vive de ESTE lado a propósito: al ser una FK simple, un
    # romaneo pertenece a lo sumo a una liquidación, y "no liquidar dos veces los mismos kilos"
    # queda garantizado por el modelo en vez de por una validación que alguien puede olvidar.
    liquidacion = models.ForeignKey('LiquidacionTabaco', on_delete=models.PROTECT,
                                    null=True, blank=True, related_name='romaneos',
                                    verbose_name="Liquidación")

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
    # COMODÍN, HOY SIEMPRE EN CERO (decisión DA-05, cerrada). El circuito NO se lo paga al
    # productor: `LiquidacionDetalle.importe` es `Sum(fardo.importe)` y `liq.neto` se arma de ahí.
    # Por eso tampoco integra el costo del lote ni la columna «a pagar» de la planilla FET.
    # La pantalla de carga no lo dibuja; el campo queda para el día que se decida usarlo, y ese
    # día hay que tocar `preparar_liquidacion` y `recalcular_lote` JUNTOS.
    adicional = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    precio_final = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'),
                                       verbose_name="Precio final (con adicional)")

    # La pertenencia al lote vive de ESTE lado, igual que `RomaneoTabaco.liquidacion` y por la
    # misma razon: siendo un FK simple, un fardo pertenece a lo sumo a un lote, y "no vender dos
    # veces los mismos kilos" queda garantizado por el modelo en vez de por una validacion que
    # alguien puede olvidar. Se declara por nombre porque `LoteAcopio` se define mas abajo.
    lote = models.ForeignKey('LoteAcopio', on_delete=models.PROTECT, null=True, blank=True,
                             related_name='fardos', verbose_name="Lote de acopio")

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
            # Alimenta el armado del lote y el reporte de margen por fardo.
            models.Index(fields=['lote', 'estado']),
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


# ==============================================================================
# LIQUIDACIÓN DE COMPRA — el comprobante que emitimos al productor (Plan 083, Etapa 2)
# ==============================================================================
# Es la primera pieza con EFECTOS CONTABLES: genera asiento, alimenta el Libro IVA y hace nacer
# la deuda con el productor en la cuenta corriente.
#
# NO se apoya en `facturacion.Compra`. La liquidación tabacalera tiene su propia estructura —el
# detalle es por clase de tabaco, no por producto— y se engancha al subsistema fiscal por
# `asiento_id`, que es como `LibroIvaCompras` y `LibroIvaAlic` se cuelgan de cualquier asiento sin
# conocer al comprobante que lo originó.
#
# EL PAGO NO ESTÁ ACÁ. La Orden de Pago y la retención de Ganancias son la Etapa 3: liquidar y
# pagar son dos hechos distintos, en momentos distintos y hechos por personas distintas.


class LiquidacionTabaco(AuditModel):
    """Comprobante de compra de tabaco emitido al productor.

    Agrupa uno o varios romaneos confirmados del MISMO productor. La relación vive del lado del
    romaneo (`RomaneoTabaco.liquidacion`), lo que impide por construcción —y no por convención—
    liquidar dos veces los mismos kilos.
    """
    BORRADOR, CONFIRMADA, ANULADA = 1, 2, 9
    ESTADOS = [(BORRADOR, 'Borrador'), (CONFIRMADA, 'Confirmada'), (ANULADA, 'Anulada')]

    A, B = 'A', 'B'
    LETRAS = [(A, 'A'), (B, 'B')]

    # Códigos de comprobante ARCA de la liquidación de compra.
    CODIVA_POR_LETRA = {A: '150', B: '151'}

    MANUAL, WEBSERVICE = 'MANUAL', 'WEBSERVICE'
    ORIGENES = [(MANUAL, 'Manual (talonario con CAI o comprobante en línea)'),
                (WEBSERVICE, 'Webservice ARCA')]

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT,
                                related_name='liquidaciones_tabaco')
    sucursal = models.ForeignKey('empresas.Sucursal', on_delete=models.PROTECT,
                                 related_name='liquidaciones_tabaco')
    productor = models.ForeignKey('facturacion.ClienteProveedor', on_delete=models.PROTECT,
                                  related_name='liquidaciones_tabaco', verbose_name="Productor")

    # Identificación del comprobante. La letra sale de la condición de IVA del productor y el
    # código ARCA de la letra; se guardan ambos porque el comprobante ya emitido no puede cambiar
    # si mañana el productor cambia de categoría.
    letra = models.CharField(max_length=1, choices=LETRAS, default=A)
    codiva = models.CharField(max_length=3, default='150', verbose_name="Cód. Comprobante ARCA")
    punto = models.IntegerField(default=1, verbose_name="Punto de Venta")
    numero = models.BigIntegerField(null=True, blank=True, db_index=True, verbose_name="Número")

    fecha = models.DateField(db_index=True, verbose_name="Fecha")
    periodo = models.CharField(max_length=6, blank=True, db_index=True, verbose_name="Período YYYYMM")

    # Autorización: hoy se carga a mano desde talonario o comprobante en línea; el webservice
    # (WSLTV) queda previsto y se implementa más adelante.
    origen_autorizacion = models.CharField(max_length=12, choices=ORIGENES, default=MANUAL)
    cai = models.CharField(max_length=20, blank=True, verbose_name="CAI")
    cae = models.CharField(max_length=20, blank=True, verbose_name="CAE")
    vencimiento_autorizacion = models.DateField(null=True, blank=True, verbose_name="Vto. CAI/CAE")

    # Importes. Todos se derivan del detalle y de las reglas vigentes al confirmar.
    neto = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    alicuota_iva = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'),
                                       verbose_name="Alícuota IVA aplicada")
    iva = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    retenciones = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'),
                                      verbose_name="Retenciones practicadas al liquidar")
    total = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0'),
        verbose_name="Total (deuda con el productor)",
        help_text="neto + IVA − retenciones de liquidación. Es lo que suma la cuenta corriente y "
                  "lo que cancela la Orden de Pago; NO es el neto a pagar, porque Ganancias se "
                  "retiene recién al pagar.")

    # Caché del estado financiero. La fuente de verdad son las imputaciones de pago (Etapa 3);
    # no existe un booleano `pagado` a propósito.
    pagado = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    saldo = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))

    asiento_id = models.IntegerField(null=True, blank=True, db_index=True,
                                     verbose_name="ID Asiento Contable")
    # 1=Real, 2=Presupuestado, 3=Ajuste, 4=Auditoría. Se hereda del romaneo y lo hereda el asiento.
    condic = models.IntegerField(default=1, verbose_name="Condición")

    estado = models.IntegerField(choices=ESTADOS, default=BORRADOR, db_index=True)
    motivo_anulacion = models.CharField(max_length=200, blank=True)
    anulada_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='+')
    anulada_el = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agricola_tabaco_liquidacion"
        verbose_name = "Liquidación de Compra de Tabaco"
        verbose_name_plural = "Liquidaciones de Compra de Tabaco"
        ordering = ['-fecha', '-numero']
        constraints = [
            # Condicional: los borradores todavía no tienen número.
            models.UniqueConstraint(fields=['empresa', 'letra', 'punto', 'numero'],
                                    condition=models.Q(numero__isnull=False),
                                    name='agro_tab_liq_numero_unico'),
            models.CheckConstraint(condition=models.Q(neto__gte=0),
                                   name='agro_tab_liq_neto_no_neg'),
            models.CheckConstraint(condition=models.Q(iva__gte=0),
                                   name='agro_tab_liq_iva_no_neg'),
            models.CheckConstraint(condition=models.Q(retenciones__gte=0),
                                   name='agro_tab_liq_ret_no_neg'),
        ]
        indexes = [
            models.Index(fields=['empresa', 'estado', '-fecha']),
            models.Index(fields=['empresa', 'productor', '-fecha']),
            models.Index(fields=['empresa', 'periodo']),
        ]

    def __str__(self):
        numero = f"{self.punto:04d}-{self.numero:08d}" if self.numero else "BORRADOR"
        return f"Liquidación {self.letra} {numero} — {self.productor.razon_social}"

    @property
    def editable(self):
        return self.estado == self.BORRADOR

    @property
    def neto_a_pagar_estimado(self):
        """Informativo: el total menos lo que se retendrá al pagar.

        No se persiste porque depende del acumulado mensual de Ganancias, que sólo se conoce en el
        momento del pago. Lo calcula la Etapa 3.
        """
        return self.total


class LiquidacionDetalle(models.Model):
    """Renglón de la liquidación: kilos y precio de una clase dentro de un romaneo.

    Se agrupa por (romaneo, clase) y no por fardo porque es lo que se imprime y lo que el
    productor verifica con una calculadora. La trazabilidad al fardo no se pierde: el fardo apunta
    al romaneo y el romaneo a la liquidación.
    """
    liquidacion = models.ForeignKey(LiquidacionTabaco, on_delete=models.CASCADE,
                                    related_name='detalles')
    romaneo = models.ForeignKey('RomaneoTabaco', on_delete=models.PROTECT,
                                related_name='detalles_liquidacion')
    clase = models.ForeignKey(ClaseTabaco, on_delete=models.PROTECT, related_name='+')

    fardos = models.IntegerField(default=0)
    kilos = models.DecimalField(max_digits=15, decimal_places=2)
    coeficiente = models.DecimalField(max_digits=6, decimal_places=4)
    precio = models.DecimalField(max_digits=15, decimal_places=2)
    importe = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        db_table = "agricola_tabaco_liquidacion_detalle"
        verbose_name = "Detalle de Liquidación"
        verbose_name_plural = "Detalles de Liquidación"
        ordering = ['romaneo', 'clase']
        constraints = [
            models.UniqueConstraint(fields=['liquidacion', 'romaneo', 'clase'],
                                    name='agro_tab_liqdet_unico'),
            models.CheckConstraint(condition=models.Q(kilos__gt=0),
                                   name='agro_tab_liqdet_kilos_positivos'),
        ]

    def __str__(self):
        return f"{self.clase.detalle} — {self.kilos} kg"


class LiquidacionRetencion(models.Model):
    """Retención practicada al productor en la liquidación.

    Guarda una COPIA de la regla aplicada, no sólo la FK al concepto: alícuota, tipo de base,
    mínimo y cuenta contable. Si mañana cambia la alícuota, esta liquidación sigue siendo
    reconstruible y la conciliación contra el pasivo contable cierra.
    """
    liquidacion = models.ForeignKey(LiquidacionTabaco, on_delete=models.CASCADE,
                                    related_name='retenciones_aplicadas')
    tipo_retencion = models.ForeignKey(TipoRetencionTabaco, on_delete=models.PROTECT,
                                       related_name='+')

    # Copia congelada de la regla.
    codigo = models.CharField(max_length=15)
    detalle = models.CharField(max_length=80)
    tipo_base = models.CharField(max_length=12)
    alicuota = models.DecimalField(max_digits=7, decimal_places=4)
    minimo_no_imponible = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    cuenta_contable = models.ForeignKey('contable.Cuenta', on_delete=models.PROTECT,
                                        related_name='+')

    base = models.DecimalField(max_digits=15, decimal_places=2,
                               verbose_name="Base sobre la que se calculó")
    importe = models.DecimalField(max_digits=15, decimal_places=2)
    nro_certificado = models.CharField(max_length=30, blank=True, verbose_name="Nro. Certificado")

    class Meta:
        db_table = "agricola_tabaco_liquidacion_retencion"
        verbose_name = "Retención de Liquidación"
        verbose_name_plural = "Retenciones de Liquidación"
        ordering = ['codigo']
        constraints = [
            models.UniqueConstraint(fields=['liquidacion', 'tipo_retencion'],
                                    name='agro_tab_liqret_unica'),
            models.CheckConstraint(condition=models.Q(importe__gte=0),
                                   name='agro_tab_liqret_importe_no_neg'),
        ]

    def __str__(self):
        return f"{self.codigo}: {self.importe}"


# ==============================================================================
# PAGO AL PRODUCTOR — imputación y retención de Ganancias (Plan 084, Etapa 3)
# ==============================================================================
# La Orden de Pago la crea `tesoreria`; acá viven sólo las dos piezas que el core no puede tener:
# la imputación a una liquidación (porque `OrdenPagoAplicacion.compra` es un FK duro a `Compra`) y
# el certificado de la retención de Ganancias.
#
# LA RETENCIÓN ES UN MEDIO DE PAGO. Ikigai ya sabe practicarlas: un `MedioPago` de categoría 'RET'
# que `contabilizar_orden_pago()` acredita contra su cuenta. No se construye un mecanismo nuevo.


class LiquidacionPago(models.Model):
    """Imputación de una Orden de Pago a una liquidación.

    Existe de este lado porque `tesoreria.OrdenPagoAplicacion.compra` es un FK duro a `Compra` con
    `PROTECT`: no puede apuntar a una liquidación de tabaco. La dependencia va verticalidad → core
    y nunca al revés (Plan 075).

    Es la FUENTE DE VERDAD del saldo de la liquidación, igual que `OrdenPagoAplicacion` lo es del
    saldo de una compra: `pagado` y `saldo` se derivan de acá, nunca se decrementan.
    """
    liquidacion = models.ForeignKey('LiquidacionTabaco', on_delete=models.PROTECT,
                                    related_name='pagos')
    orden_pago = models.ForeignKey('tesoreria.OrdenPago', on_delete=models.PROTECT,
                                   related_name='pagos_liquidacion_tabaco')
    importe = models.DecimalField(max_digits=15, decimal_places=2)
    # Se marca en vez de borrarse: la imputación ocurrió y su rastro no se destruye.
    anulado = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = "agricola_tabaco_liquidacion_pago"
        verbose_name = "Imputación de Pago a Liquidación"
        verbose_name_plural = "Imputaciones de Pago a Liquidaciones"
        constraints = [
            models.UniqueConstraint(fields=['liquidacion', 'orden_pago'],
                                    name='agro_tab_liqpago_unico'),
        ]
        indexes = [
            models.Index(fields=['liquidacion', 'anulado']),
            models.Index(fields=['orden_pago']),
        ]

    def __str__(self):
        return f"OP {self.orden_pago_id} -> Liq {self.liquidacion_id}: {self.importe}"


class RetencionPago(models.Model):
    """Certificado de una retención practicada en el momento del pago.

    Cumple dos funciones a la vez, y es deliberado: es el comprobante que se le entrega al
    productor Y el registro del que se DERIVA el acumulado mensual. No hay una tabla de acumulados
    que mantener sincronizada; el acumulado se reconstruye sumando los certificados vigentes del
    período. El sistema heredado hacía lo mismo: `liq_mes_ret_gcia` era una vista, no una tabla.

    Consecuencia: al anular un pago se anula su certificado y el acumulado del mes baja solo.
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT,
                                related_name='retenciones_pago_tabaco')
    orden_pago = models.ForeignKey('tesoreria.OrdenPago', on_delete=models.PROTECT,
                                   related_name='retenciones_tabaco')
    productor = models.ForeignKey('facturacion.ClienteProveedor', on_delete=models.PROTECT,
                                  related_name='retenciones_tabaco')
    tipo_retencion = models.ForeignKey(TipoRetencionTabaco, on_delete=models.PROTECT,
                                       related_name='+')

    # Copia congelada de la regla aplicada.
    codigo = models.CharField(max_length=15)
    detalle = models.CharField(max_length=80)
    regimen = models.CharField(max_length=15, blank=True)
    alicuota = models.DecimalField(max_digits=7, decimal_places=4)
    minimo_no_imponible = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    cuenta_contable = models.ForeignKey('contable.Cuenta', on_delete=models.PROTECT,
                                        related_name='+')

    # Memoria del cálculo acumulativo, para que el certificado sea verificable a mano.
    periodo = models.CharField(max_length=6, db_index=True, verbose_name="Período YYYYMM")
    base_del_pago = models.DecimalField(max_digits=15, decimal_places=2,
                                        verbose_name="Neto liquidado en este pago")
    base_acumulada = models.DecimalField(max_digits=15, decimal_places=2,
                                         verbose_name="Neto acumulado del mes")
    retencion_del_mes = models.DecimalField(max_digits=15, decimal_places=2,
                                            verbose_name="Retención total del mes")
    retenido_previo = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'),
                                          verbose_name="Ya retenido en el mes")
    importe = models.DecimalField(max_digits=15, decimal_places=2,
                                  verbose_name="Importe retenido ahora")

    nro_certificado = models.BigIntegerField(null=True, blank=True, db_index=True,
                                             verbose_name="Nro. Certificado")
    fecha = models.DateField(db_index=True)
    anulado = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = "agricola_tabaco_retencion_pago"
        verbose_name = "Retención Practicada en el Pago"
        verbose_name_plural = "Retenciones Practicadas en el Pago"
        ordering = ['-fecha', '-nro_certificado']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'nro_certificado'],
                                    condition=models.Q(nro_certificado__isnull=False),
                                    name='agro_tab_retpago_certificado_unico'),
            models.CheckConstraint(condition=models.Q(importe__gte=0),
                                   name='agro_tab_retpago_importe_no_neg'),
        ]
        indexes = [
            # El índice que alimenta el cálculo del acumulado mensual.
            models.Index(fields=['empresa', 'productor', 'periodo', 'anulado']),
        ]

    def __str__(self):
        return f"Cert. {self.nro_certificado or 's/n'} — {self.codigo} — {self.importe}"


# ==============================================================================
# LOTES, ACONDICIONAMIENTO Y VENTA (Plan 086, Etapa 5)
# ==============================================================================
# Qué pasa con los kilos DESPUÉS de comprarlos: se agrupan en lotes comerciales, se acondicionan
# —perdiendo peso y consumiendo insumos— y se venden por el circuito de siempre.
#
# ESTA ETAPA NO GENERA UN SOLO ASIENTO, Y ES A PROPÓSITO.
# El ERP no contabiliza el stock: `StockSucursal` lleva cantidades y `VentaItem.cto_rep` guarda el
# costo sólo para análisis. Los insumos del acondicionamiento se compran con una `Compra` normal,
# que YA generó su asiento, su Libro IVA y su deuda con el proveedor. Lo que falta no es
# contabilizar de nuevo —eso duplicaría el gasto en el balance— sino IMPUTAR ese costo ya
# contabilizado a un lote para poder medir el margen. Por eso `AcondicionamientoCosto.compra` es
# un respaldo opcional y no un disparador contable.
#
# La venta sí genera asiento, pero por `facturacion`, sin una línea de código de esta etapa.


class LoteAcopio(AuditModel):
    """Agrupación comercial de fardos ya comprados.

    Un lote es de UNA variedad y UNA sucursal: el stock se lleva por variedad y por sucursal, así
    que un lote que mezclara cualquiera de las dos no se podría imputar a ningún producto.

    Se arma con fardos de romaneos ya confirmados —un borrador no existe físicamente y un anulado
    no ocurrió— y se vende entero.
    """
    BORRADOR, ARMADO, ACONDICIONADO, VENDIDO, ANULADO = 1, 2, 3, 4, 9
    ESTADOS = [
        (BORRADOR, 'Borrador'),
        (ARMADO, 'Armado'),
        (ACONDICIONADO, 'Acondicionado'),
        (VENDIDO, 'Vendido'),
        (ANULADO, 'Anulado'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='lotes_tabaco')
    sucursal = models.ForeignKey('empresas.Sucursal', on_delete=models.PROTECT,
                                 related_name='lotes_tabaco')

    punto = models.IntegerField(default=1, verbose_name="Punto")
    # Nulo en borrador: el número se toma al armar, para no dejar huecos en la serie.
    numero = models.BigIntegerField(null=True, blank=True, db_index=True, verbose_name="Número")

    fecha = models.DateField(db_index=True, verbose_name="Fecha")
    campania = models.ForeignKey(Campania, on_delete=models.PROTECT, related_name='lotes_tabaco')
    variedad = models.ForeignKey(VariedadTabaco, on_delete=models.PROTECT, related_name='lotes')
    descripcion = models.CharField(max_length=160, blank=True, verbose_name="Descripción")
    observaciones = models.TextField(blank=True)

    estado = models.IntegerField(choices=ESTADOS, default=BORRADOR, db_index=True)

    # UN LOTE, UNA VENTA. Siendo un FK simple, el modelo garantiza que los mismos kilos no se
    # vendan dos veces —igual que `RomaneoTabaco.liquidacion` garantiza no liquidarlos dos veces—.
    # Para vender la mitad se arman dos lotes; los fardos se pueden mover mientras el lote no
    # tenga un acondicionamiento cerrado.
    venta = models.ForeignKey('facturacion.Venta', on_delete=models.PROTECT, null=True, blank=True,
                              related_name='lotes_tabaco', verbose_name="Venta")

    # Derivados del detalle. Se materializan porque se leen en todo listado, pero la fuente de
    # verdad son los fardos y los acondicionamientos: `recalcular_lote()` los reconstruye
    # enteros, nunca por delta.
    total_fardos = models.IntegerField(default=0)
    total_kilos = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'),
                                      verbose_name="Kilos de compra")
    kilos_actuales = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0'), verbose_name="Kilos actuales",
        help_text="Kilos de compra menos las bajas de acondicionamiento.")
    costo_compra = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'),
                                       verbose_name="Costo de compra")
    costo_acondicionamiento = models.DecimalField(max_digits=15, decimal_places=2,
                                                  default=Decimal('0'),
                                                  verbose_name="Costo de acondicionamiento")
    valor_coproductos = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'),
                                            verbose_name="Valor de coproductos")
    importe_venta = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'),
                                        verbose_name="Importe de venta")

    motivo_anulacion = models.CharField(max_length=200, blank=True)
    anulado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='+')
    anulado_el = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agricola_tabaco_lote"
        verbose_name = "Lote de Acopio"
        verbose_name_plural = "Lotes de Acopio"
        ordering = ['-fecha', '-numero']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'punto', 'numero'],
                                    condition=models.Q(numero__isnull=False),
                                    name='agro_tab_lote_numero_unico'),
            models.CheckConstraint(condition=models.Q(total_kilos__gte=0),
                                   name='agro_tab_lote_kilos_no_neg'),
            models.CheckConstraint(condition=models.Q(total_fardos__gte=0),
                                   name='agro_tab_lote_fardos_no_neg'),
            models.CheckConstraint(condition=models.Q(costo_compra__gte=0),
                                   name='agro_tab_lote_costo_no_neg'),
        ]
        indexes = [
            models.Index(fields=['empresa', 'estado', '-fecha']),
            models.Index(fields=['empresa', 'campania', 'variedad']),
            models.Index(fields=['empresa', 'sucursal', 'estado']),
        ]

    def __str__(self):
        numero = f"{self.punto:04d}-{self.numero:08d}" if self.numero else "BORRADOR"
        return f"Lote {numero} - {self.variedad.detalle}"

    @property
    def editable(self):
        """Sólo se tocan los fardos mientras el lote no se vendió ni se anuló.

        El bloqueo fino —"no sacar un fardo si ya hay un acondicionamiento cerrado"— lo hace el
        servicio, porque depende de una consulta y no de un campo.
        """
        return self.estado in (self.BORRADOR, self.ARMADO, self.ACONDICIONADO)

    @property
    def adicional_informado(self):
        """Adicionales de los fardos del lote. NO integra el costo, y es a propósito.

        Hoy el circuito no se lo paga al productor: `LiquidacionDetalle.importe` es
        `Sum(fardo.importe)` y `liq.neto` se arma de ahí. Sumarlo al costo haría que el lote
        dijera una cosa y la liquidación otra. Se informa aparte hasta que se cierre la decisión
        DA-05 —qué es el adicional y si integra la base—.
        """
        from django.db.models import Sum
        return self.fardos.aggregate(s=Sum('adicional'))['s'] or Decimal('0')

    @property
    def costo_total(self):
        return self.costo_compra + self.costo_acondicionamiento

    @property
    def margen(self):
        """Venta más lo recuperado en coproductos, menos todo lo que costó."""
        return self.importe_venta + self.valor_coproductos - self.costo_total

    @property
    def margen_porcentaje(self):
        base = self.costo_total
        if not base:
            return Decimal('0')
        return (self.margen / base * Decimal('100')).quantize(Decimal('0.01'))


class ProcesoAcondicionamiento(AuditModel):
    """Maestro de procesos de planta — es la respuesta a la decisión abierta DA-07.

    El plan no adivina si la planta despalilla, seca o reenfarda: sabe que UN PROCESO TOMA KILOS,
    DEVUELVE KILOS, CONSUME PLATA Y PIERDE PESO. El resto es un alta en esta tabla, no una
    migración.

    `merma_normal_porcentaje` es la merma esperada del proceso. Lo que la excede es merma
    EXTRAORDINARIA y hay que explicarla: es la única que el modelo obliga a justificar.
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE,
                                related_name='procesos_acondicionamiento')
    codigo = models.CharField(max_length=12, verbose_name="Código")
    detalle = models.CharField(max_length=120, verbose_name="Detalle")
    merma_normal_porcentaje = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('0'),
        verbose_name="% de merma normal",
        help_text="Merma esperada del proceso. Lo que la exceda se marca como extraordinaria.")
    orden = models.IntegerField(default=0, verbose_name="Orden")
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "agricola_tabaco_proceso_acond"
        verbose_name = "Proceso de Acondicionamiento"
        verbose_name_plural = "Procesos de Acondicionamiento"
        ordering = ['orden', 'codigo']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'codigo'],
                                    name='agro_tab_proceso_codigo_unico'),
            models.CheckConstraint(
                condition=models.Q(merma_normal_porcentaje__gte=0,
                                   merma_normal_porcentaje__lte=100),
                name='agro_tab_proceso_merma_0_100'),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.detalle}"


class Acondicionamiento(AuditModel):
    """Una corrida de un proceso sobre un lote.

    LA DISTINCIÓN QUE JUSTIFICA EL MODELO
    Merma es lo que DESAPARECE. Coproducto es lo que deja de ser tabaco de esta variedad y pasa a
    ser otra cosa vendible —el palo, el descarte—. Sin separarlos, el usuario registraría el palo
    como merma y perdería un activo real.

    Por eso el stock se mueve así:
        stock(variedad)   = Σ fardos − Σ kilos_baja      # baja = entrada − salida
        stock(coproducto) = Σ coproducto.kilos           # reaparece en su propio producto

    `kilos_baja` incluye los coproductos justamente porque ya no son tabaco de esta variedad.
    """
    BORRADOR, CERRADO, ANULADO = 1, 2, 9
    ESTADOS = [(BORRADOR, 'Borrador'), (CERRADO, 'Cerrado'), (ANULADO, 'Anulado')]

    lote = models.ForeignKey(LoteAcopio, on_delete=models.PROTECT,
                             related_name='acondicionamientos')
    proceso = models.ForeignKey(ProcesoAcondicionamiento, on_delete=models.PROTECT,
                                related_name='acondicionamientos')
    # Correlativo DENTRO del lote: un proceso de planta no merece una serie global.
    numero = models.IntegerField(default=1, verbose_name="Nro")
    fecha = models.DateField(db_index=True, verbose_name="Fecha")

    kilos_entrada = models.DecimalField(max_digits=15, decimal_places=2,
                                        verbose_name="Kilos de entrada")
    kilos_salida = models.DecimalField(max_digits=15, decimal_places=2,
                                       verbose_name="Kilos de salida")

    # Derivados. `recalcular_acondicionamiento()` los reconstruye enteros.
    kilos_coproductos = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    kilos_baja = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0'),
        verbose_name="Kilos dados de baja",
        help_text="Entrada menos salida. Es lo que el término de stock resta de la variedad.")
    kilos_merma = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'),
                                      verbose_name="Merma")
    merma_normal_esperada = models.DecimalField(max_digits=15, decimal_places=2,
                                                default=Decimal('0'))
    merma_extraordinaria = models.DecimalField(max_digits=15, decimal_places=2,
                                               default=Decimal('0'))
    # Congelado del maestro: si mañana se corrige el % del proceso, esta corrida no cambia.
    porcentaje_merma_normal_aplicado = models.DecimalField(max_digits=6, decimal_places=3,
                                                           default=Decimal('0'))

    costo_total = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    valor_coproductos = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))

    motivo_merma = models.CharField(max_length=200, blank=True,
                                    verbose_name="Motivo de la merma extraordinaria")
    observaciones = models.TextField(blank=True)
    estado = models.IntegerField(choices=ESTADOS, default=BORRADOR, db_index=True)

    motivo_anulacion = models.CharField(max_length=200, blank=True)
    anulado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='+')
    anulado_el = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agricola_tabaco_acondicionamiento"
        verbose_name = "Acondicionamiento"
        verbose_name_plural = "Acondicionamientos"
        ordering = ['lote', 'numero']
        constraints = [
            models.UniqueConstraint(fields=['lote', 'numero'],
                                    name='agro_tab_acond_numero_unico'),
            models.CheckConstraint(condition=models.Q(kilos_entrada__gt=0),
                                   name='agro_tab_acond_entrada_positiva'),
            models.CheckConstraint(condition=models.Q(kilos_salida__gte=0),
                                   name='agro_tab_acond_salida_no_neg'),
            # Del proceso no puede salir más de lo que entró: sería crear materia.
            models.CheckConstraint(condition=models.Q(kilos_salida__lte=models.F('kilos_entrada')),
                                   name='agro_tab_acond_salida_menor_entrada'),
        ]
        indexes = [
            models.Index(fields=['lote', 'estado']),
            models.Index(fields=['estado', '-fecha']),
        ]

    def __str__(self):
        return f"Acond. {self.numero} - {self.proceso.detalle} - Lote {self.lote_id}"

    @property
    def editable(self):
        return self.estado == self.BORRADOR

    @property
    def porcentaje_merma_real(self):
        if not self.kilos_entrada:
            return Decimal('0')
        return (self.kilos_merma / self.kilos_entrada * Decimal('100')).quantize(Decimal('0.001'))


class AcondicionamientoCoproducto(models.Model):
    """Lo que sale del proceso y NO es tabaco de la variedad, pero sigue valiendo.

    Entra al stock de su propio `Producto` por un término de stock aparte. `valor_estimado` es
    gerencial: mejora el margen del lote sin generar ningún asiento —el ingreso real aparecerá
    cuando ese coproducto se venda—.
    """
    acondicionamiento = models.ForeignKey(Acondicionamiento, on_delete=models.CASCADE,
                                          related_name='coproductos')
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT,
                                 related_name='coproductos_tabaco')
    kilos = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Kilos")
    valor_estimado = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'),
                                         verbose_name="Valor estimado")
    observaciones = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "agricola_tabaco_acond_coproducto"
        verbose_name = "Coproducto de Acondicionamiento"
        verbose_name_plural = "Coproductos de Acondicionamiento"
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(fields=['acondicionamiento', 'producto'],
                                    name='agro_tab_coproducto_unico'),
            models.CheckConstraint(condition=models.Q(kilos__gt=0),
                                   name='agro_tab_coproducto_kilos_positivos'),
            models.CheckConstraint(condition=models.Q(valor_estimado__gte=0),
                                   name='agro_tab_coproducto_valor_no_neg'),
        ]
        indexes = [models.Index(fields=['acondicionamiento'])]

    def __str__(self):
        return f"{self.producto.detalle} - {self.kilos} kg"


class AcondicionamientoCosto(models.Model):
    """Costo directo imputado al lote a través del acondicionamiento.

    `compra` ES UN RESPALDO, NO UN DISPARADOR CONTABLE. La factura del insumo ya generó su asiento
    y su Libro IVA por el circuito de compras; acá sólo se dice a qué lote se le imputa ese gasto
    para poder medir el margen. Contabilizarlo de nuevo duplicaría el gasto en el balance.
    """
    acondicionamiento = models.ForeignKey(Acondicionamiento, on_delete=models.CASCADE,
                                          related_name='costos')
    concepto = models.CharField(max_length=160, verbose_name="Concepto")
    importe = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Importe")
    compra = models.ForeignKey('facturacion.Compra', on_delete=models.SET_NULL, null=True,
                               blank=True, related_name='costos_acondicionamiento',
                               verbose_name="Compra de respaldo")

    class Meta:
        db_table = "agricola_tabaco_acond_costo"
        verbose_name = "Costo de Acondicionamiento"
        verbose_name_plural = "Costos de Acondicionamiento"
        ordering = ['id']
        constraints = [
            models.CheckConstraint(condition=models.Q(importe__gte=0),
                                   name='agro_tab_acond_costo_no_neg'),
        ]
        indexes = [models.Index(fields=['acondicionamiento'])]

    def __str__(self):
        return f"{self.concepto} - {self.importe}"
