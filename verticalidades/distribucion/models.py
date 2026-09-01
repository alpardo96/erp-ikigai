"""Modelos maestros del módulo Distribución (Plan 074).

Este módulo se activa por `Empresa.tipo_actividad = 'DISTRIBUIDORA'`, con el mismo
patrón condicional que usa ARMERÍA: una empresa estándar no ve ninguna de estas
pantallas.

Contiene por ahora sólo los MAESTROS (fase 1a del plan). Los modelos operativos
—`Reparto`, `RepartoParada`, `RecepcionDevolucion`, `ExtensionPedidoDistribucion`—
entran con la fase que los usa, para que ninguna migración quede sin código que la
respalde.
"""
from django.conf import settings
from django.db import models

from core.models import AuditModel
from empresas.models import Empresa, Sucursal
from facturacion.models import ClienteProveedor


class ZonaReparto(AuditModel):
    """Zona geográfica de reparto. Agrupa clientes y ordena la hoja de ruta."""

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='zonas_reparto')
    nombre = models.CharField(max_length=100, verbose_name="Nombre de la Zona")
    orden = models.IntegerField(default=0, verbose_name="Orden de Recorrido",
                                help_text="Define la secuencia sugerida al armar el reparto.")
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Zona de Reparto"
        verbose_name_plural = "Zonas de Reparto"
        ordering = ['orden', 'nombre']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'nombre'], name='uniq_zona_empresa_nombre'),
        ]
        indexes = [
            models.Index(fields=['empresa', 'activa']),
        ]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if self.nombre:
            self.nombre = self.nombre.upper().strip()
        super().save(*args, **kwargs)


class Personal(AuditModel):
    """Vendedores, repartidores y cobradores.

    Es una tabla PROPIA y no un atributo del usuario del sistema (Plan 074 §4.3).
    La razón de fondo: no todo el personal opera el ERP. El repartidor trabaja con la
    Hoja de Ruta en papel y puede no tocar nunca una pantalla, pero tiene que figurar
    igual en el documento. Modelarlo como `User` obligaría a crear credenciales para
    gente que nunca va a entrar, que es superficie de ataque a cambio de nada.

    Por eso `usuario` es NULLABLE: el vendedor con celular lo tiene, el repartidor no.

    Los tres roles son booleanos independientes y ACUMULABLES: en una distribuidora
    chica es habitual que la misma persona tome pedidos, reparta y cobre.
    """

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='personal_distribucion')
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='personal_distribucion', verbose_name="Usuario del Sistema",
        help_text="Sólo si la persona opera el ERP (ej. vendedor que carga pedidos "
                  "desde el celular). El repartidor que trabaja con la hoja de ruta "
                  "en papel no necesita usuario.")

    codigo = models.IntegerField(verbose_name="Código",
                                 help_text="Código con el que se lo identifica en pantallas y reportes.")
    nombre = models.CharField(max_length=150, verbose_name="Nombre y Apellido", db_index=True)
    documento = models.CharField(max_length=20, null=True, blank=True, verbose_name="Documento")
    telefono = models.CharField(max_length=50, null=True, blank=True)

    es_vendedor = models.BooleanField(default=False, verbose_name="Vendedor")
    es_repartidor = models.BooleanField(default=False, verbose_name="Repartidor")
    es_cobrador = models.BooleanField(default=False, verbose_name="Cobrador")

    comision_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                              verbose_name="Comisión (%)")
    zona = models.ForeignKey(ZonaReparto, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='personal', verbose_name="Zona Habitual")

    activo = models.BooleanField(default=True)
    fecha_alta = models.DateField(null=True, blank=True, verbose_name="Fecha de Alta")
    fecha_baja = models.DateField(null=True, blank=True, verbose_name="Fecha de Baja")

    codigo_anterior = models.CharField(
        max_length=50, null=True, blank=True, db_index=True,
        verbose_name="Código Sistema Anterior",
        help_text="Código del vendedor/repartidor en el sistema anterior, para la migración.")

    class Meta:
        verbose_name = "Personal de Distribución"
        verbose_name_plural = "Personal de Distribución"
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'codigo'], name='uniq_personal_empresa_codigo'),
        ]
        indexes = [
            models.Index(fields=['empresa', 'activo']),
            models.Index(fields=['empresa', 'es_vendedor']),
            models.Index(fields=['empresa', 'es_repartidor']),
        ]

    def __str__(self):
        return f"[{self.codigo}] {self.nombre}"

    @property
    def roles_display(self):
        roles = []
        if self.es_vendedor:
            roles.append("Vendedor")
        if self.es_repartidor:
            roles.append("Repartidor")
        if self.es_cobrador:
            roles.append("Cobrador")
        return " / ".join(roles) if roles else "Sin rol asignado"

    def save(self, *args, **kwargs):
        if self.nombre:
            self.nombre = self.nombre.upper().strip()
        if not self.codigo:
            # Comodidad de carga, no un número de documento: acá no hay control de
            # integridad que auditar. Por eso alcanza con "último + 1" sin bloqueo; si
            # dos altas simultáneas eligieran el mismo número, el UniqueConstraint de
            # Meta lo rechaza y el alta se reintenta. Nunca queda un duplicado.
            ultimo = (Personal.objects.filter(empresa_id=self.empresa_id)
                      .order_by('-codigo').values_list('codigo', flat=True).first())
            self.codigo = (ultimo or 0) + 1
        super().save(*args, **kwargs)


class Vehiculo(AuditModel):
    """Vehículo de reparto. `capacidad_kg` alerta la sobrecarga en el Consolidado."""

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='vehiculos')
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT, related_name='vehiculos',
                                 verbose_name="Sucursal Base")
    patente = models.CharField(max_length=20, verbose_name="Patente")
    descripcion = models.CharField(max_length=150, verbose_name="Descripción")
    capacidad_kg = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                       verbose_name="Capacidad (kg)")
    # Determina si la mercadería rechazada mantiene la cadena de frío durante el reparto
    # y, por lo tanto, si puede reingresar al stock vendible (Plan 074 §7.10).
    refrigerado = models.BooleanField(default=True, verbose_name="Refrigerado")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Vehículo"
        verbose_name_plural = "Vehículos"
        ordering = ['patente']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'patente'], name='uniq_vehiculo_empresa_patente'),
        ]
        indexes = [
            models.Index(fields=['empresa', 'activo']),
        ]

    def __str__(self):
        return f"{self.patente} - {self.descripcion}"

    def save(self, *args, **kwargs):
        if self.patente:
            self.patente = self.patente.upper().strip()
        if self.descripcion:
            self.descripcion = self.descripcion.upper().strip()
        super().save(*args, **kwargs)


class MotivoDevolucion(AuditModel):
    """Tipificación de por qué un pedido no se entrega o vuelve al depósito.

    El motivo estandariza la estadística; la observación libre que lo acompaña en cada
    documento captura lo que sólo el repartidor sabe.

    `sugiere_apto_reventa` precarga el `apto_reventa` del ítem de la Recepción de
    Devoluciones: un envase roto no vuelve al stock vendible, un negocio cerrado sí.
    """

    MOMENTO_PRE_CARGA = 'PRE_CARGA'
    MOMENTO_EN_ENTREGA = 'EN_ENTREGA'
    MOMENTO_AMBOS = 'AMBOS'
    MOMENTOS = [
        (MOMENTO_PRE_CARGA, 'Antes de cargar el vehículo'),
        (MOMENTO_EN_ENTREGA, 'En la entrega al cliente'),
        (MOMENTO_AMBOS, 'Ambos'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='motivos_devolucion')
    codigo = models.CharField(max_length=30, verbose_name="Código")
    descripcion = models.CharField(max_length=150, verbose_name="Descripción")
    momento = models.CharField(max_length=12, choices=MOMENTOS, default=MOMENTO_AMBOS,
                               verbose_name="Momento en que aplica")
    sugiere_apto_reventa = models.BooleanField(
        default=True, verbose_name="La mercadería vuelve al stock",
        help_text="Si se desmarca, la devolución con este motivo no reingresa al stock vendible.")
    requiere_observacion = models.BooleanField(
        default=False, verbose_name="Exige observación",
        help_text="Para motivos genéricos, donde el dato real está en el texto libre.")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Motivo de Devolución"
        verbose_name_plural = "Motivos de Devolución"
        ordering = ['codigo']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'codigo'], name='uniq_motivo_empresa_codigo'),
        ]
        indexes = [
            models.Index(fields=['empresa', 'activo']),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.descripcion}"

    def save(self, *args, **kwargs):
        if self.codigo:
            self.codigo = self.codigo.upper().strip().replace(' ', '_')
        super().save(*args, **kwargs)


class CarteraVendedor(AuditModel):
    """Asignación de un cliente a su vendedor.

    Un cliente tiene UN SOLO vendedor, porque es el responsable directo de su saldo.
    De esta regla se desprende el listado de saldos agrupado por vendedor.
    """

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='carteras')
    vendedor = models.ForeignKey(Personal, on_delete=models.PROTECT, related_name='cartera',
                                 limit_choices_to={'es_vendedor': True}, verbose_name="Vendedor")
    cliente = models.ForeignKey(ClienteProveedor, on_delete=models.CASCADE, related_name='cartera',
                                limit_choices_to={'tipo_entidad': 1}, verbose_name="Cliente")
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Cartera de Vendedor"
        verbose_name_plural = "Carteras de Vendedores"
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'cliente'], name='uniq_cartera_empresa_cliente'),
        ]
        indexes = [
            models.Index(fields=['empresa', 'vendedor']),
        ]

    def __str__(self):
        return f"{self.cliente.razon_social} -> {self.vendedor.nombre}"


class DomicilioEntrega(AuditModel):
    """Dónde se descarga la mercadería. Un cliente puede tener varios (Plan 074).

    NO es el domicilio fiscal. `ClienteProveedor.domicilio` es el legal, el que se
    imprime como domicilio del cliente en el comprobante; éste es el punto físico al que
    llega el camión, y un cliente con sucursales tiene uno por cada una.

    POR QUÉ LA ZONA Y LA AGENDA VIVEN ACÁ Y NO EN EL CLIENTE
    -------------------------------------------------------
    Una sucursal en San Cayetano y otra en Villa Luján entran en repartos distintos, en
    días distintos y con recorridos distintos. Son propiedades de DÓNDE SE ENTREGA, no
    de quién debe: colgarlas del cliente obligaría a que todas sus sucursales compartan
    zona y día, que es justamente lo que no pasa.

    Lo que sí queda en el cliente es el CRÉDITO: un CUIT, una cuenta corriente, un
    límite. Las entregas se reparten; la deuda no.

    Regla operativa: el domicilio principal se genera automáticamente a partir del
    fiscal, pero **es responsabilidad del vendedor** asegurarse de que cada pedido salga
    con el domicilio de entrega correcto.
    """

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='domicilios_entrega')
    cliente = models.ForeignKey(ClienteProveedor, on_delete=models.CASCADE,
                                related_name='domicilios_entrega',
                                limit_choices_to={'tipo_entidad': 1})

    nombre = models.CharField(max_length=100, verbose_name="Nombre del Punto",
                              help_text="Con lo que el repartidor lo identifica: "
                                        "'Sucursal Centro', 'Depósito', 'Casa Central'.")
    domicilio = models.CharField(max_length=255, verbose_name="Domicilio de Entrega")
    localidad = models.CharField(max_length=100, null=True, blank=True)
    codigo_postal = models.CharField(max_length=20, null=True, blank=True, verbose_name="C. Postal")

    zona = models.ForeignKey(ZonaReparto, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='domicilios', verbose_name="Zona de Reparto")

    contacto = models.CharField(max_length=150, null=True, blank=True,
                                verbose_name="A quién buscar")
    telefono = models.CharField(max_length=100, null=True, blank=True)
    horario_recepcion = models.CharField(
        max_length=100, null=True, blank=True, verbose_name="Horario de Recepción",
        help_text="Ej. 'Hasta las 13'. Evita el viaje perdido.")
    observaciones_entrega = models.TextField(
        null=True, blank=True, verbose_name="Indicaciones de Entrega",
        help_text="Ej. 'Entrar por la calle lateral', 'timbre del fondo'.")

    # El que se propone por defecto al tomar el pedido. Se genera a partir del domicilio
    # fiscal cuando el cliente no tiene ninguno cargado.
    es_principal = models.BooleanField(default=False, verbose_name="Principal")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Domicilio de Entrega"
        verbose_name_plural = "Domicilios de Entrega"
        ordering = ['-es_principal', 'nombre']
        constraints = [
            models.UniqueConstraint(fields=['cliente', 'nombre'],
                                    name='uniq_domicilio_cliente_nombre'),
        ]
        indexes = [
            models.Index(fields=['empresa', 'zona']),
            models.Index(fields=['cliente', 'activo']),
        ]

    def __str__(self):
        return f"{self.nombre} — {self.domicilio}"

    @property
    def texto_completo(self):
        """Una línea con todo lo que el repartidor necesita para llegar."""
        partes = [self.domicilio]
        if self.localidad:
            partes.append(self.localidad)
        return " - ".join(p for p in partes if p)

    def save(self, *args, **kwargs):
        for campo in ('nombre', 'domicilio', 'localidad'):
            valor = getattr(self, campo)
            if valor:
                setattr(self, campo, valor.upper().strip())
        super().save(*args, **kwargs)
        # Un cliente tiene un solo principal: marcar uno desmarca al anterior.
        if self.es_principal:
            DomicilioEntrega.objects.filter(cliente_id=self.cliente_id).exclude(
                pk=self.pk).update(es_principal=False)


class ExtensionPedidoDistribucion(models.Model):
    """Datos de distribución de un pedido, satélite de `Preventa` (Plan 074 §5.B).

    Mismo patrón que `ExtensionArmeria`: `Preventa` es un modelo compartido con otras
    actividades y no se contamina con campos de un rubro.

    NUMERACIÓN PROPIA (§4.2). `Preventa` sólo tiene `preventa_id`, que es una clave
    subrogada de la base y no una serie auditable por empresa y punto. El sistema
    anterior ya numeraba los pedidos y los imprimía en la hoja de ruta —el `ID 186276`
    con el que arranca cada cliente—, así que el número es el eslabón que une el pedido
    del cliente con su comprobante y con la devolución.

    Si más adelante se decide que TODO pedido del ERP lleve numeración, el campo se
    promueve a `Preventa` con una migración de datos simple.
    """

    ORIGEN_MOVIL = 'MOVIL'
    ORIGEN_PC = 'PC_TELEFONICO'
    ORIGEN_PLANILLA = 'PLANILLA_PAPEL'
    ORIGENES = [
        (ORIGEN_MOVIL, 'Móvil del vendedor'),
        (ORIGEN_PC, 'PC (pedido telefónico)'),
        (ORIGEN_PLANILLA, 'Planilla manual'),
    ]

    # 1 = Real (Factura fiscal) · 2 = Presupuestado (PRE, no fiscal). Ver `.cursorrules`.
    CONDIC_DESTINO = [
        (1, 'Factura (Real)'),
        (2, 'PRE (Presupuestado)'),
    ]

    preventa = models.OneToOneField('facturacion.Preventa', on_delete=models.CASCADE,
                                    related_name='distribucion')
    punto = models.IntegerField(verbose_name="Punto",
                                help_text="Sucursal emisora del pedido (sucursal_id).")
    numero = models.BigIntegerField(db_index=True, verbose_name="N° de Pedido")

    vendedor = models.ForeignKey(Personal, on_delete=models.PROTECT, related_name='pedidos',
                                 limit_choices_to={'es_vendedor': True},
                                 null=True, blank=True, verbose_name="Vendedor",
                                 help_text="Quién tomó el pedido. Es la fuente de verdad del "
                                           "vendedor de la operación: la venta llega a su "
                                           "vendedor a través del pedido.")

    # A dónde va la mercadería. Un pedido entrega en UN punto: de ahí sale un comprobante
    # y una parada de la hoja de ruta. Un cliente con tres sucursales hace tres pedidos.
    domicilio_entrega = models.ForeignKey(DomicilioEntrega, on_delete=models.PROTECT,
                                          related_name='pedidos', null=True, blank=True,
                                          verbose_name="Domicilio de Entrega")
    # Snapshot del domicilio al momento del pedido, con el mismo criterio que
    # `Preventa.cliente_razon_social`: si mañana se corrige la dirección, el comprobante
    # ya emitido tiene que seguir diciendo a dónde se entregó.
    domicilio_entrega_texto = models.CharField(max_length=255, null=True, blank=True,
                                               verbose_name="Domicilio de Entrega (texto)")

    # `Preventa.fecha` es `auto_now_add` (fecha de carga). La entrega es otra cosa.
    fecha_entrega = models.DateField(null=True, blank=True, db_index=True,
                                     verbose_name="Fecha de Entrega")
    origen = models.CharField(max_length=20, choices=ORIGENES, default=ORIGEN_PC)
    condic_destino = models.IntegerField(choices=CONDIC_DESTINO, default=1,
                                         verbose_name="Se facturará como")
    zona = models.ForeignKey(ZonaReparto, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='pedidos')

    # Define la prioridad en la asignación de stock escaso: el que pidió primero se sirve
    # primero. Es el criterio que se le puede explicar a un vendedor sin discusión.
    hora_carga = models.DateTimeField(auto_now_add=True, db_index=True,
                                      verbose_name="Hora de Carga")

    # Alertas informativas congeladas al momento de tomar el pedido. No bloquean: el
    # vendedor decide, y el pedido queda sujeto a disponibilidad.
    alerta_stock = models.BooleanField(default=False, verbose_name="Stock ajustado al tomarse")
    alerta_credito = models.BooleanField(default=False, verbose_name="Fuera de límite al tomarse")

    # Comprobante emitido a partir de este pedido. Es el eslabón que sigue en la cadena
    # Pedido → Comprobante → Hoja de Ruta → Recepción → NC.
    venta = models.OneToOneField('facturacion.Venta', on_delete=models.PROTECT,
                                 null=True, blank=True, related_name='pedido_distribucion',
                                 verbose_name="Comprobante Emitido")

    observaciones = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Pedido de Distribución"
        verbose_name_plural = "Pedidos de Distribución"
        constraints = [
            # Segunda barrera del control de integridad: aunque el contador falle, la base
            # no acepta dos pedidos con el mismo número en el mismo punto.
            models.UniqueConstraint(fields=['punto', 'numero'], name='uniq_pedido_punto_numero'),
        ]
        indexes = [
            models.Index(fields=['numero']),
            models.Index(fields=['fecha_entrega']),
            models.Index(fields=['zona']),
        ]

    def __str__(self):
        return f"Pedido {self.punto:04d}-{self.numero:08d}"

    @property
    def numero_formateado(self):
        return f"{self.punto:04d}-{self.numero:08d}"


class Reparto(AuditModel):
    """Cabecera de la Hoja de Ruta y del Consolidado de Artículos (Plan 074 §5.A).

    Es un DOCUMENTO EMITIDO: lleva numeración correlativa propia y auditable, igual que
    el `Reparto: 8639` que ya imprimía el sistema anterior.

    Se arma DESPUÉS de facturar: sus paradas son comprobantes ya emitidos, y el
    repartidor sale con la mercadería y el comprobante juntos.
    """

    ARMADO, CERRADO, RENDIDO, ANULADO = 0, 1, 2, 3
    ESTADOS = [
        (ARMADO, 'Armado'),
        (CERRADO, 'Cerrado (salió)'),
        (RENDIDO, 'Rendido'),
        (ANULADO, 'Anulado'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='repartos')
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT, related_name='repartos')
    punto = models.IntegerField(verbose_name="Punto",
                                help_text="Sucursal emisora (sucursal_id).")
    numero = models.BigIntegerField(db_index=True, verbose_name="N° de Reparto")

    fecha = models.DateField(db_index=True, verbose_name="Fecha de Salida")
    vehiculo = models.ForeignKey(Vehiculo, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='repartos')
    # M2M porque el papel del sistema anterior muestra "MAXIMILIANO + ROMINA": un reparto
    # puede llevar más de un responsable.
    responsables = models.ManyToManyField(Personal, blank=True, related_name='repartos',
                                          limit_choices_to={'es_repartidor': True},
                                          verbose_name="Repartidores")
    zona = models.ForeignKey(ZonaReparto, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='repartos')

    estado = models.IntegerField(choices=ESTADOS, default=ARMADO, db_index=True)

    # Se incrementa en cada reimpresión por anulación previa a la carga. El papel viejo
    # tiene que quedar identificable: si circulan dos hojas de ruta distintas, el control
    # contra la firma del cliente deja de servir.
    version_impresion = models.IntegerField(default=1, verbose_name="Versión de Impresión")

    # Caja RECAUDADORA del reparto. Se abre al cerrarlo y recibe todas sus cobranzas.
    # Nula mientras el reparto esta armado: todavia no hay plata que entre por el.
    sesion_caja = models.ForeignKey('tesoreria.CajaSesion', on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='repartos',
                                    verbose_name="Sesion de Caja Recaudadora")

    observaciones = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Reparto"
        verbose_name_plural = "Repartos"
        ordering = ['-fecha', '-numero']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'punto', 'numero'],
                                    name='uniq_reparto_empresa_punto_numero'),
        ]
        indexes = [
            models.Index(fields=['empresa', 'fecha']),
            models.Index(fields=['empresa', 'estado']),
        ]

    def __str__(self):
        return f"Reparto {self.numero}"

    @property
    def numero_formateado(self):
        return f"{self.punto:04d}-{self.numero:08d}"

    @property
    def responsables_display(self):
        """'MAXIMILIANO + ROMINA', como en el papel."""
        nombres = [p.nombre for p in self.responsables.all()]
        return " + ".join(nombres) if nombres else "Sin asignar"

    @property
    def editable(self):
        return self.estado == self.ARMADO


class RepartoParada(models.Model):
    """Una parada de la hoja de ruta. Hay dos clases, y no se comportan igual.

    - **ENTREGA:** un comprobante para dejar en un domicilio. Es la parada de siempre.
    - **COBRANZA:** un cliente con saldo que NO hizo pedido, al que se pasa sólo a
      cobrarle (Plan 076 §A). No tiene pedido ni comprobante, y por lo tanto tampoco
      artículos: no aparece en el Consolidado. Si TODAS las paradas de un reparto son de
      esta clase, el reparto es una ruta de cobranza pura.

    EL COBRO MÍNIMO DE UNA PARADA DE COBRANZA ES CERO
    -------------------------------------------------
    El cobro mínimo existe porque hay mercadería de por medio: es la condición para
    dejarla. Acá no se entrega nada, así que NO HAY PALANCA. El repartidor pide y se lleva
    lo que el cliente quiera darle, que la mayoría de las veces es nada o una parte —al
    cliente que no compró no le urge pagar, y el cierre lo suele terminar el vendedor—.
    Lo que se congela e imprime es el SALDO, como dato para ir a reclamar, no como
    obligación. Lo que traiga se imputa con el procedimiento estándar: FIFO de lo más
    antiguo, con el efectivo priorizando los `condic = 2`.

    LOS TRES IMPORTES SE CONGELAN al cerrar el reparto. El papel es la foto de un
    momento: si el reporte los recalculara al reimprimirse, un cobro posterior cambiaría
    el número y el control contra la firma del cliente se rompería.
    """

    ENTREGA, COBRANZA = 0, 1
    TIPOS = [
        (ENTREGA, 'Entrega de mercadería'),
        (COBRANZA, 'Sólo cobranza'),
    ]

    PENDIENTE, ENTREGADA, NO_ENTREGADA = 0, 1, 2
    ESTADOS_ENTREGA = [
        (PENDIENTE, 'Pendiente'),
        (ENTREGADA, 'Entregada'),
        (NO_ENTREGADA, 'No entregada'),
    ]

    reparto = models.ForeignKey(Reparto, on_delete=models.CASCADE, related_name='paradas')
    # Explícito y no inferido de `venta is None`: obligar a recordar esa convención en
    # cada lectura es la clase de detalle que después se olvida en un reporte.
    tipo = models.IntegerField(choices=TIPOS, default=ENTREGA, db_index=True)

    # El pedido aporta el N° con el que el cliente reclama; el comprobante, el que se le
    # deja. La hoja de ruta imprime los dos (Plan 074 §4.2). Nulos en una parada de
    # cobranza, que no tiene ninguno de los dos.
    pedido = models.ForeignKey(ExtensionPedidoDistribucion, on_delete=models.PROTECT,
                               null=True, blank=True,
                               related_name='paradas', verbose_name="Pedido")
    venta = models.ForeignKey('facturacion.Venta', on_delete=models.PROTECT,
                              null=True, blank=True,
                              related_name='paradas_reparto', verbose_name="Comprobante")

    # Campos propios, no derivados: sin comprobante no habría de dónde sacarlos. El
    # domicilio va congelado por el mismo motivo que los importes.
    cliente = models.ForeignKey(ClienteProveedor, on_delete=models.PROTECT,
                                related_name='paradas_reparto', verbose_name="Cliente")
    domicilio_texto = models.CharField(max_length=255, null=True, blank=True,
                                       verbose_name="Domicilio de Entrega")

    orden = models.IntegerField(default=0, verbose_name="Orden de Descarga")

    saldo_anterior = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                         verbose_name="Saldo Anterior")
    # Con signo: si es negativo, ése es el excedente que hay que cobrar.
    saldo_disponible = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                           verbose_name="Saldo Disponible")
    cobro_minimo = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                       verbose_name="Cobro Mínimo")

    estado_entrega = models.IntegerField(choices=ESTADOS_ENTREGA, default=PENDIENTE)
    observacion_repartidor = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Parada de Reparto"
        verbose_name_plural = "Paradas de Reparto"
        ordering = ['orden']
        constraints = [
            models.UniqueConstraint(fields=['reparto', 'venta'],
                                    condition=models.Q(venta__isnull=False),
                                    name='uniq_parada_reparto_venta'),
            # Un comprobante entra en UN solo reparto: si estuviera en dos, la mercadería
            # se cargaría dos veces y el consolidado mentiría. Condicionado porque ahora
            # hay nulos: PostgreSQL ya admite varios NULL en un índice único, pero así la
            # regla queda ESCRITA y no depende de un detalle del motor.
            models.UniqueConstraint(fields=['venta'],
                                    condition=models.Q(venta__isnull=False),
                                    name='uniq_parada_venta'),
            # Una entrega sin comprobante no tiene qué entregar; una cobranza con
            # comprobante es una entrega mal clasificada. Regla inflexible -> va a la base.
            models.CheckConstraint(
                condition=(models.Q(tipo=0, venta__isnull=False)
                           | models.Q(tipo=1, venta__isnull=True)),
                name='parada_entrega_con_comprobante'),
        ]
        indexes = [
            models.Index(fields=['reparto', 'orden']),
        ]

    def __str__(self):
        destino = self.venta if self.venta_id else f"cobranza a {self.cliente}"
        return f"{self.reparto} · {destino}"

    @property
    def es_cobranza(self):
        return self.tipo == self.COBRANZA

    @property
    def domicilio_entrega(self):
        """Dónde se descarga (o dónde se pasa a cobrar). Texto congelado, no el actual."""
        return self.domicilio_texto or ''


class RecepcionDevolucion(AuditModel):
    """Documento propio con el que el DEPOSITO declara que volvio (Plan 074 5.E).

    Es al reparto lo que el Informe de Recepcion es a la compra: el espejo fisico de la
    Nota de Credito. Uno dice que se le acredito al cliente; el otro, que entro de vuelta
    al deposito. DEBEN CONCILIAR, y esa conciliacion es el control de las devoluciones.

    SE EMITE UNA POR CADA PEDIDO DEVUELTO, no una por reparto. La devolucion se acredita
    a un cliente concreto con una NC contra UN comprobante, asi que la correspondencia
    1 Pedido -> 1 Comprobante -> 1 Recepcion -> 1 NC es lo que permite conciliar sin
    desarmar totales.

    PRIMERO SE CUENTA, DESPUES SE ACREDITA: la NC se emite DESDE la recepcion, con los
    datos ya cargados. Al reves se le acreditaria al cliente mercaderia que puede no
    haber vuelto, y el descalce apareceria recien en la conciliacion.
    """

    BORRADOR, CONFIRMADA, ANULADA = 0, 1, 2
    ESTADOS = [
        (BORRADOR, 'Borrador'),
        (CONFIRMADA, 'Confirmada'),
        (ANULADA, 'Anulada'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE,
                                related_name='recepciones_devolucion')
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT,
                                 related_name='recepciones_devolucion')
    punto = models.IntegerField(verbose_name="Punto")
    numero = models.BigIntegerField(db_index=True, verbose_name="N de Recepcion")

    # De la parada salen, en un solo salto, el N de Pedido, el del Comprobante y el
    # cliente: los tres datos que el documento tiene que imprimir.
    parada = models.ForeignKey('RepartoParada', on_delete=models.PROTECT,
                               related_name='recepciones', verbose_name="Parada")
    # Desnormalizado desde la parada, para filtrar y auditar por reparto sin JOIN.
    reparto = models.ForeignKey(Reparto, on_delete=models.PROTECT,
                                related_name='recepciones')

    fecha = models.DateField(db_index=True)
    # Quien cuenta OPERA el sistema, asi que es un User. Quien devuelve puede no operarlo
    # (el repartidor de la hoja de ruta en papel), asi que es Personal.
    recibido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     related_name='recepciones_devolucion',
                                     verbose_name="Recibido por (deposito)")
    entregado_por = models.ForeignKey(Personal, on_delete=models.SET_NULL, null=True,
                                      blank=True, related_name='devoluciones_entregadas',
                                      limit_choices_to={'es_repartidor': True},
                                      verbose_name="Entregado por (repartidor)")

    estado = models.IntegerField(choices=ESTADOS, default=BORRADOR, db_index=True)
    nota_credito = models.OneToOneField('facturacion.Venta', on_delete=models.PROTECT,
                                        null=True, blank=True,
                                        related_name='recepcion_devolucion',
                                        verbose_name="Nota de Credito emitida")
    observaciones = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Recepcion de Devoluciones"
        verbose_name_plural = "Recepciones de Devoluciones"
        ordering = ['-fecha', '-numero']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'punto', 'numero'],
                                    name='uniq_recepcion_empresa_punto_numero'),
            # Un pedido devuelto genera UNA recepcion. Si se anula, puede rehacerse.
            models.UniqueConstraint(fields=['parada'],
                                    condition=models.Q(estado__in=[0, 1]),
                                    name='uniq_recepcion_parada_vigente'),
        ]
        indexes = [
            models.Index(fields=['empresa', 'fecha']),
            models.Index(fields=['reparto']),
        ]

    def __str__(self):
        return f"Recepcion {self.numero_formateado}"

    @property
    def numero_formateado(self):
        return f"{self.punto:04d}-{self.numero:08d}"

    @property
    def editable(self):
        return self.estado == self.BORRADOR

    @property
    def total_devuelto(self):
        from decimal import Decimal
        return sum((i.subtotal for i in self.items.all()), Decimal('0.00'))


class RecepcionDevolucionItem(models.Model):
    """Un articulo que volvio al deposito, con lo que efectivamente se conto."""

    recepcion = models.ForeignKey(RecepcionDevolucion, on_delete=models.CASCADE,
                                  related_name='items')
    # Se apunta al item del comprobante para no perder el precio al que se facturo: la
    # NC tiene que acreditar exactamente lo mismo que se cobro.
    venta_item = models.ForeignKey('facturacion.VentaItem', on_delete=models.PROTECT,
                                   related_name='devoluciones')
    cantidad = models.DecimalField(max_digits=15, decimal_places=2,
                                   verbose_name="Cantidad Devuelta")
    motivo = models.ForeignKey(MotivoDevolucion, on_delete=models.PROTECT,
                               related_name='items_devueltos')
    # Se precarga desde `motivo.sugiere_apto_reventa`: un envase roto no vuelve al stock
    # vendible, un negocio cerrado si.
    apto_reventa = models.BooleanField(default=True, verbose_name="Apto para reventa")
    observacion = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = "Item de Recepcion de Devoluciones"
        verbose_name_plural = "Items de Recepcion de Devoluciones"
        constraints = [
            models.UniqueConstraint(fields=['recepcion', 'venta_item'],
                                    name='uniq_recepcion_item'),
        ]

    def __str__(self):
        return f"{self.venta_item.producto} x {self.cantidad}"

    @property
    def producto(self):
        return self.venta_item.producto

    @property
    def subtotal(self):
        """Lo que se le acredita al cliente por este renglon."""
        from decimal import Decimal
        precio = Decimal(str(self.venta_item.precio_unitario))
        descuento = Decimal(str(self.venta_item.porcentaje_descuento or 0))
        return (precio * Decimal(str(self.cantidad))
                * (Decimal('1') - descuento / Decimal('100'))).quantize(Decimal('0.01'))


class NotaCreditoDistribucion(models.Model):
    """Contexto operativo de una Nota de Credito de distribucion.

    Satelite de la `Venta` de tipo NC: le da el motivo, la observacion y el vinculo con
    la parada y la recepcion, sin tocar `Venta`, que es un modelo compartido.

    El motivo y la observacion se imprimen en el detalle de la NC, para que el documento
    explique por si solo por que existe.
    """

    PRE_CARGA = 'PRE_CARGA'
    EN_ENTREGA = 'EN_ENTREGA'
    MOMENTOS = [
        (PRE_CARGA, 'Antes de cargar el vehiculo'),
        (EN_ENTREGA, 'En la entrega al cliente'),
    ]

    nota_credito = models.OneToOneField('facturacion.Venta', on_delete=models.CASCADE,
                                        related_name='distribucion_nc')
    venta_origen = models.ForeignKey('facturacion.Venta', on_delete=models.PROTECT,
                                     related_name='notas_credito_distribucion',
                                     verbose_name="Comprobante acreditado")
    parada = models.ForeignKey('RepartoParada', on_delete=models.SET_NULL, null=True,
                               blank=True, related_name='notas_credito')
    recepcion = models.ForeignKey(RecepcionDevolucion, on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name='notas_credito',
                                  verbose_name="Recepcion que la origino")

    motivo = models.ForeignKey(MotivoDevolucion, on_delete=models.PROTECT,
                               related_name='notas_credito')
    observacion = models.TextField(null=True, blank=True)
    momento = models.CharField(max_length=12, choices=MOMENTOS, default=EN_ENTREGA)

    class Meta:
        verbose_name = "Nota de Credito de Distribucion"
        verbose_name_plural = "Notas de Credito de Distribucion"
        indexes = [
            models.Index(fields=['venta_origen']),
            models.Index(fields=['motivo']),
        ]

    def __str__(self):
        return f"NC de {self.venta_origen} - {self.motivo.codigo}"


class CobranzaDistribucion(models.Model):
    """Contexto operativo de un Recibo emitido en el circuito de reparto (Plan 074 7.7).

    Satelite de `tesoreria.Recibo`, igual que `NotaCreditoDistribucion` lo es de `Venta`:
    le da el reparto, la parada y el cobrador SIN tocar un modelo compartido por todo el ERP.

    POR QUE PUEDE HABER DOS POR COBRANZA: el usuario carga UN importe, pero el sistema lo
    parte por `condic` (Real y Presupuestado no se mezclan en un mismo recibo, porque cada
    uno alimenta un circuito contable distinto). Ambos recibos comparten reparto y parada.
    """

    TRAZABLE = 'TRAZABLE'
    EFECTIVO = 'EFECTIVO'
    MIXTO = 'MIXTO'
    TRAMOS = [
        (TRAZABLE, 'Medios con trazabilidad externa'),
        (EFECTIVO, 'Efectivo'),
        (MIXTO, 'Efectivo + trazables'),
    ]

    recibo = models.OneToOneField('tesoreria.Recibo', on_delete=models.CASCADE,
                                  related_name='distribucion_cobranza')
    # Nulo cuando cobra un VENDEDOR fuera de todo reparto (Plan 076 C): no tiene hoja de
    # ruta ni paradas, solo plata cobrada. En ese caso el `cobrador` es obligatorio: la
    # plata SIEMPRE tiene un responsable.
    reparto = models.ForeignKey(Reparto, on_delete=models.PROTECT, null=True, blank=True,
                                related_name='cobranzas')
    # Nulo cuando el cliente paga sin que su comprobante este en este reparto (por ejemplo
    # abona un saldo viejo al pasar el repartidor): la plata entra igual a la recaudadora.
    parada = models.ForeignKey('RepartoParada', on_delete=models.SET_NULL, null=True,
                               blank=True, related_name='cobranzas')
    # Quien cobro puede no operar el sistema: por eso es `Personal` y no `User` (4.3).
    cobrador = models.ForeignKey(Personal, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='cobranzas',
                                 limit_choices_to={'es_cobrador': True})
    tramo = models.CharField(max_length=10, choices=TRAMOS, default=EFECTIVO)
    # Lo que se cobro y NO se pudo imputar a ningun comprobante: queda como anticipo.
    excedente = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                    verbose_name="Excedente sin imputar")

    class Meta:
        verbose_name = "Cobranza de Distribucion"
        verbose_name_plural = "Cobranzas de Distribucion"
        constraints = [
            # O es de un reparto, o la trajo un cobrador identificado. Una cobranza sin
            # ninguno de los dos es plata sin responsable: no puede existir.
            models.CheckConstraint(
                condition=(models.Q(reparto__isnull=False)
                           | models.Q(cobrador__isnull=False)),
                name='cobranza_con_responsable'),
        ]
        indexes = [
            models.Index(fields=['reparto']),
            models.Index(fields=['cobrador']),
        ]

    def __str__(self):
        origen = (f"reparto {self.reparto.numero}" if self.reparto_id
                  else f"vendedor {self.cobrador}")
        return f"Cobranza {origen} - recibo {self.recibo_id}"


class RendicionReparto(models.Model):
    """De quien es la plata que entra por un `RetiroCaja` de distribucion (7.9 y 076 C).

    La rendicion en si la maneja `tesoreria.RetiroCaja`, que ya implementa los DOS PASOS
    (uno declara -> otro cuenta y acepta -> la diferencia genera su asiento). Este modelo
    solo dice DE QUIEN es esa plata, que es el dato que la sesion de caja NO puede dar:
    `CajaSesion.usuario` es un `User` y el repartidor puede no serlo (4.3).

    DOS ORIGENES POSIBLES, EXACTAMENTE UNO POR RENDICION:
      - `reparto`  : lo que trajo un camion, con su hoja de ruta y sus paradas.
      - `vendedor` : lo que trajo un vendedor por su cuenta, sin reparto. Cobra al cliente
                     que "esquiva el pago" y despues le hace la guardia; esa plata entra
                     igual a la Tesoreria de Reparto, pero en su condicion de vendedor.
    """

    reparto = models.ForeignKey(Reparto, on_delete=models.PROTECT, null=True, blank=True,
                                related_name='rendiciones')
    vendedor = models.ForeignKey(Personal, on_delete=models.PROTECT, null=True, blank=True,
                                 related_name='rendiciones', verbose_name="Vendedor")
    retiro = models.OneToOneField('tesoreria.RetiroCaja', on_delete=models.CASCADE,
                                  related_name='distribucion_rendicion')
    # Congelado al declarar: lo que el sistema esperaba de este reparto segun sus recibos.
    esperado = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                   verbose_name="Efectivo cobrado segun el sistema")
    observaciones = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Rendicion de Distribucion"
        verbose_name_plural = "Rendiciones de Distribucion"
        constraints = [
            # Exactamente UNO de los dos origenes. Sin ninguno la plata no tiene duenio;
            # con los dos, no se sabe a quien reclamarle un faltante.
            models.CheckConstraint(
                condition=(models.Q(reparto__isnull=False, vendedor__isnull=True)
                           | models.Q(reparto__isnull=True, vendedor__isnull=False)),
                name='rendicion_con_un_solo_origen'),
        ]
        indexes = [
            models.Index(fields=['reparto']),
            models.Index(fields=['vendedor']),
        ]

    def __str__(self):
        origen = (f"reparto {self.reparto.numero}" if self.reparto_id
                  else f"vendedor {self.vendedor}")
        return f"Rendicion {origen}"


class AjusteAsignacion(models.Model):
    """Registro de un recorte de cantidad por falta de stock (Plan 074 §7.3).

    Cuando el stock no alcanza para cubrir todos los pedidos, alguien decide quién
    recibe cuánto. Esa decisión NO puede quedar sin rastro: al vendedor hay que poder
    explicarle después por qué su cliente recibió menos de lo que pidió, y con qué
    criterio se repartió.

    Por eso cada ajuste guarda la cantidad original y la asignada, quién lo hizo y
    cuándo. Es auditoría, no cálculo: el pedido queda con la cantidad final.
    """

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='ajustes_asignacion')
    pedido = models.ForeignKey('ExtensionPedidoDistribucion', on_delete=models.CASCADE,
                               related_name='ajustes')
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT,
                                 related_name='ajustes_asignacion')

    cantidad_original = models.DecimalField(max_digits=15, decimal_places=2,
                                            verbose_name="Cantidad Pedida")
    cantidad_asignada = models.DecimalField(max_digits=15, decimal_places=2,
                                            verbose_name="Cantidad Asignada")

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name='ajustes_asignacion')
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    observacion = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = "Ajuste de Asignación"
        verbose_name_plural = "Ajustes de Asignación"
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['empresa', 'fecha']),
            models.Index(fields=['producto']),
        ]

    def __str__(self):
        return (f"{self.pedido.numero_formateado} · {self.producto_id}: "
                f"{self.cantidad_original} → {self.cantidad_asignada}")

    @property
    def recortado(self):
        return self.cantidad_original - self.cantidad_asignada


class DiaVisita(models.Model):
    """Agenda de visita de un DOMICILIO DE ENTREGA: qué día se pasa y con qué frecuencia.

    Cuelga del domicilio y no del cliente porque cada sucursal se visita su día, según la
    zona en la que esté. Admite VARIOS días por punto: con lácteos es habitual pasar dos
    o tres veces por semana.

    Alimenta la planilla manual del vendedor y la sugerencia de armado del reparto.
    """

    DIAS = [
        (1, 'Lunes'), (2, 'Martes'), (3, 'Miércoles'), (4, 'Jueves'),
        (5, 'Viernes'), (6, 'Sábado'), (7, 'Domingo'),
    ]
    FRECUENCIAS = [
        ('SEMANAL', 'Semanal'),
        ('QUINCENAL_1', 'Quincenal (1ª y 3ª semana)'),
        ('QUINCENAL_2', 'Quincenal (2ª y 4ª semana)'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='dias_visita')
    domicilio = models.ForeignKey(DomicilioEntrega, on_delete=models.CASCADE,
                                  related_name='dias_visita', verbose_name="Domicilio de Entrega")
    dia_semana = models.IntegerField(choices=DIAS, verbose_name="Día de Visita")
    frecuencia = models.CharField(max_length=15, choices=FRECUENCIAS, default='SEMANAL')

    class Meta:
        verbose_name = "Día de Visita"
        verbose_name_plural = "Días de Visita"
        ordering = ['dia_semana']
        constraints = [
            models.UniqueConstraint(fields=['domicilio', 'dia_semana'],
                                    name='uniq_diavisita_domicilio_dia'),
        ]
        indexes = [
            models.Index(fields=['empresa', 'dia_semana']),
        ]

    def __str__(self):
        return f"{self.domicilio.nombre} - {self.get_dia_semana_display()}"

class ExtensionDistribuidora(models.Model):
    """Tabla satélite del cliente para empresas tipo 'DISTRIBUIDORA' (Plan 074 §5.C)."""

    cliente = models.OneToOneField(ClienteProveedor, on_delete=models.CASCADE,
                                   related_name="distribuidora")
    clasificacion = models.CharField(max_length=50, null=True, blank=True,
                                     verbose_name="Clasificación",
                                     help_text="Agrupación del cliente para análisis y filtros.")
    coeficiente_mayorista = models.DecimalField(
        max_digits=10, decimal_places=4, default=1,
        verbose_name="Coeficiente Mayorista",
        help_text="Se aplica sobre el precio de lista con IVA del producto.")
    bloqueado_credito = models.BooleanField(default=False, verbose_name="Bloqueado para Crédito")

    class Meta:
        verbose_name = "Detalle Distribuidora"
        verbose_name_plural = "Detalles Distribuidora"
        db_table = 'facturacion_extensiondistribuidora'

    def __str__(self):
        return f"Distribuidora - {self.cliente.razon_social}"

    def save(self, *args, **kwargs):
        if self.clasificacion:
            self.clasificacion = self.clasificacion.upper().strip()
        super().save(*args, **kwargs)
