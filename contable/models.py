from django.db import models
from django.conf import settings
from core.models import AuditModel
from empresas.models import Empresa, Ejercicio, Sucursal

class Cuenta(AuditModel):
    TIPO_CUENTA = [
        ('A', 'Activo'),
        ('P', 'Pasivo'),
        ('N', 'Patrimonio Neto'),
        ('R', 'Resultado')
    ]

    id = models.AutoField(primary_key=True)
    codigo = models.IntegerField(verbose_name="Código (Legacy)", null=True, blank=True)
    sumariza = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subcuentas', verbose_name="Sumariza en")
    jerarquia = models.CharField(max_length=20, verbose_name="Jerarquía", db_index=True)
    cuenta = models.CharField(max_length=50, verbose_name="Nombre de la Cuenta", db_index=True)
    imputable = models.IntegerField(choices=[(0, 'No imputable'), (1, 'Imputable')], default=0, verbose_name="Imputable")
    tipo = models.CharField(max_length=1, choices=TIPO_CUENTA, verbose_name="Tipo de Cuenta")
    
    rg_830 = models.IntegerField(null=True, blank=True, verbose_name="RG 830 (Ret. Ganancias)", help_text="relacionado con la tabla de rg_830_ret_gcias")
    
    id_pre = models.IntegerField(null=True, blank=True)
    id_bce = models.IntegerField(null=True, blank=True)
    id_ec = models.IntegerField(null=True, blank=True)
    id_fc = models.IntegerField(null=True, blank=True)

    # Clasificación de disponibilidades para el reporte de Caja Diaria (Tesorería).
    # Vacío = la cuenta NO es de disponibilidad (es una contrapartida: gasto, proveedor, cliente...).
    # Solo EFE, DOL y VAL arrastran saldo; BCO, TAR y OTR informan el movimiento neto del día.
    TIPO_DISPONIBILIDAD = [
        ('EFE', 'Efectivo'),
        ('DOL', 'Dólares'),
        ('VAL', 'Valores en Cartera'),
        ('BCO', 'Banco'),
        ('TAR', 'Tarjetas'),
        ('OTR', 'Otros'),
    ]
    tipo_disponibilidad = models.CharField(
        max_length=3, choices=TIPO_DISPONIBILIDAD, blank=True, default='', db_index=True,
        verbose_name="Tipo de Disponibilidad (Caja Diaria)"
    )

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")

    class Meta:
        db_table = "cble_cuentas"
        verbose_name = "Cuenta Contable"
        verbose_name_plural = "Cuentas Contables"

    def __str__(self):
        return f"{self.jerarquia} - {self.cuenta}"


# =============================================================================
# CONDIC — fuente única de verdad de los rótulos (ver `.cursorrules`)
# =============================================================================
# Se define acá y no en cada template para que agregar o renombrar un valor sea
# un solo cambio. `CONDIC_CARGA` es lo que puede elegir un operador; el resto lo
# genera el sistema y no se ofrece nunca en un combo.
CONDIC_ASIENTO = [
    (1, 'Real'),
    (2, 'Presupuestado'),
    (3, 'Ajuste'),
    (4, 'Auditoría'),
    (5, 'Apertura'),
    (6, 'Refundición'),
    (7, 'Cierre'),
]

# Movimientos del período: los que puede registrar la operatoria. Es el universo
# de los filtros de listados y de las columnas mensuales de los reportes.
CONDIC_MOVIMIENTO = (1, 2, 3, 4)

# Generados por el sistema. Un asiento con condic >= 5 no se edita: se anula y se
# regenera el proceso que lo creó.
CONDIC_ESTRUCTURAL = (5, 6, 7)

# Alimentan el subsistema fiscal (Libro IVA, LibroIvaAlic, RetPercSufrida).
CONDIC_FISCAL = (1, 3)


def condic_opciones(valores=None):
    """[{'valor': 1, 'nombre': 'Real'}, ...] para pintar checkboxes/selects."""
    permitidos = valores if valores is not None else [v for v, _ in CONDIC_ASIENTO]
    return [{'valor': v, 'nombre': n} for v, n in CONDIC_ASIENTO if v in permitidos]


class Asiento(AuditModel):
    asiento_id = models.AutoField(primary_key=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, verbose_name="Empresa")
    ejercicio = models.ForeignKey(Ejercicio, on_delete=models.PROTECT, verbose_name="Ejercicio Fiscal")
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT, null=True, blank=True, verbose_name="Sucursal")
    numero_diario = models.IntegerField(null=True, blank=True, db_index=True, verbose_name="Número en Diario")
    fecha = models.DateField(db_index=True, verbose_name="Fecha")
    concepto = models.CharField(max_length=200, verbose_name="Concepto")
    # condic NO indica contado/cuenta corriente. Clasifica el asiento dentro del circuito contable
    # y se hereda del comprobante que lo origina (venta.condic, compra.condic, recibo.condic,
    # orden_pago.condic). Los valores 1 a 4 coinciden con la numeración del sistema VFP anterior:
    #   1 = Real         -> fiscal; el 90% de los movimientos. Alimenta Libro IVA y DDJJ.
    #   2 = Presupuestado-> NO fiscal. Gasto REAL de la empresa sin respaldo documental válido
    #                       (servimoto, almacén del barrio, taxi). Solo análisis de gestión.
    #   3 = Ajuste       -> factura válida a nombre de la empresa pero pagada por el dueño con
    #                       fondos propios (no sale plata de la empresa). SÍ va a contabilidad y a
    #                       las DDJJ de IVA/Ganancias; se EXCLUYE del análisis de gastos.
    #   4 = Auditoría    -> ajustes que el estudio contable remite tras armar los estados contables.
    #   5 = Apertura     -> asiento de apertura de ejercicio (lo usa el Balance). Sistema.
    #   6 = Refundición  -> refundición de cuentas de resultado. Sistema.
    #   7 = Cierre       -> cierre de ejercicio. Sistema.
    #
    # Las tres lentes: gestión = {1,2} | fiscal = {1,3} | estados contables = {1,3,4}.
    # Los 5/6/7 los genera el sistema: no se ofrecen en combos de carga ni se editan a mano.
    condic = models.IntegerField(default=1, verbose_name="Condición Asiento")
    monto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Monto Total")
    modulo = models.IntegerField(default=1, verbose_name="Módulo Origen")  # 1=manual, 2=ventas, 5=compras, 6=banco
    cli_pro = models.ForeignKey('facturacion.ClienteProveedor', on_delete=models.PROTECT, null=True, blank=True, verbose_name="Cliente/Proveedor")
    fec_vto = models.DateField(null=True, blank=True, verbose_name="Vencimiento")
    anulado = models.BooleanField(default=False, verbose_name="Anulado")
    fec_anulacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Anulación")

    # Caja de Tesorería a la que pertenece el asiento. Es el motor del reporte de Caja Diaria:
    # el asiento_id es el común denominador que vincula caja, recibos, órdenes de pago, compras
    # y libro IVA. Queda en null en los asientos que no mueven fondos de la caja de tesorería.
    sesion_caja = models.ForeignKey(
        'tesoreria.CajaSesion', on_delete=models.PROTECT, null=True, blank=True,
        related_name='asientos', verbose_name="Caja de Tesorería"
    )

    class Meta:
        db_table = "cble_asiento_enc"
        verbose_name = "Asiento Contable"
        verbose_name_plural = "Asientos Contables"
        indexes = [
            models.Index(fields=['empresa', 'ejercicio', 'fecha']),
            models.Index(fields=['empresa', 'cli_pro']),
            # Caja Diaria: el reporte trae todos los asientos de una caja ordenados por asiento_id.
            models.Index(fields=['sesion_caja', 'asiento_id'], name='idx_asiento_caja'),
        ]

    def __str__(self):
        return f"Asiento {self.asiento_id} - {self.fecha.strftime('%d/%m/%Y')} - {self.concepto}"

    def save(self, *args, **kwargs):
        # Forzar mayúsculas en el concepto
        if self.concepto and isinstance(self.concepto, str):
            self.concepto = self.concepto.upper()
        super().save(*args, **kwargs)

class AsientoLinea(models.Model):
    asiento = models.ForeignKey(Asiento, on_delete=models.CASCADE, related_name='lineas', verbose_name="Asiento")
    orden = models.IntegerField(default=0, verbose_name="Orden")
    cuenta = models.ForeignKey(Cuenta, on_delete=models.PROTECT, verbose_name="Cuenta Contable")
    leyenda = models.CharField(max_length=200, blank=True, verbose_name="Leyenda")
    debe = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Debe")
    haber = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Haber")
    
    # Soporte Multimoneda
    divisa = models.CharField(max_length=3, default='PES', verbose_name="Divisa")
    cotizacion = models.DecimalField(max_digits=15, decimal_places=4, default=1.0, verbose_name="Cotización")
    debe_divisa = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Debe Divisa")
    haber_divisa = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Haber Divisa")
    
    fec_vto = models.DateField(null=True, blank=True, verbose_name="Vencimiento")
    cli_pro = models.ForeignKey('facturacion.ClienteProveedor', on_delete=models.PROTECT, null=True, blank=True, verbose_name="Cliente/Proveedor Auxiliar")

    class Meta:
        db_table = "cble_asiento_mov"
        verbose_name = "Línea de Asiento"
        verbose_name_plural = "Líneas de Asiento"
        ordering = ['orden']
        constraints = [
            models.CheckConstraint(condition=models.Q(debe__gte=0) & models.Q(haber__gte=0), name='debe_haber_no_neg'),
            models.CheckConstraint(condition=~(models.Q(debe__gt=0) & models.Q(haber__gt=0)), name='debe_xor_haber'),
        ]

    def __str__(self):
        return f"Línea {self.orden} - Cta {self.cuenta.jerarquia} - D:{self.debe} H:{self.haber}"

class ParametrosContables(models.Model):
    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, primary_key=True, verbose_name="Empresa")
    
    # Cuentas de IVA
    cta_iva_credito = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. IVA Crédito (compras)')
    cta_iva_debito = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. IVA Débito (ventas)')
    
    # Retenciones y percepciones SUFRIDAS (nos las practican terceros).
    # Son un CRÉDITO fiscal: van al DEBE. No confundir con las practicadas de más abajo.
    cta_ret_iva = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Retención IVA (sufrida)')
    cta_ret_ganancias = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Retención Ganancias (sufrida)')
    cta_ret_iibb = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Retención IIBB (sufrida)')
    cta_ret_suss = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Retención SUSS (sufrida)')
    cta_ret_mun = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Retención Municipal (sufrida)')

    # Retenciones PRACTICADAS (nosotros somos agentes de retención).
    # Son una DEUDA con el fisco hasta depositarlas: van al HABER. Las usa la Orden de Pago
    # cuando el medio de pago es una retención (Plan 035 §1.2).
    cta_ret_practicada_ganancias = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Retenciones Practicadas Ganancias (RG 830)')
    cta_ret_practicada_iva = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Retenciones Practicadas IVA')
    cta_ret_practicada_iibb = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Retenciones Practicadas IIBB')
    cta_ret_practicada_suss = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Retenciones Practicadas SUSS')


    # Caja y bancos
    cta_caja = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Caja Principal')
    cta_dolar = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Caja Dólares')
    
    # Caja Mostrador y Tesorería
    cta_caja_mostrador = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Caja Mostrador')
    cta_caja_mostrador_dolares = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Caja Mostrador Dólares')
    # Efectivo del circuito de DISTRIBUCIÓN: la caja recaudadora de cada reparto y la
    # Tesorería de Reparto (Plan 076 §B). Va aparte de la mostrador porque los responsables
    # son personas distintas —el cajero de mostrador y el repartidor/administrativo de
    # reparto— y el balance tiene que poder mostrar por separado la plata que está en la
    # calle. Las dos cajas de distribución comparten esta cuenta: entre ellas el traslado no
    # genera asiento, porque el dinero no cambia de naturaleza contable.
    cta_caja_reparto = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Caja de Reparto (Distribución)')
    cta_caja_central = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Caja Central (Tesorería)')
    cta_caja_central_dolares = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Caja Central Dólares')
    cta_transferencias_sucursal = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Transferencias entre Sucursales')
    cta_valores_cartera = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Valores a Depositar')
    cta_tarjetas_a_cobrar = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Tarjetas a Cobrar')
    # Cuenta patrimonial transitoria donde se estaciona el faltante/sobrante detectado al
    # recibir una rendición de caja. Se reclasifica luego (al cajero o a resultados) con un ajuste aparte.
    cta_diferencia_caja = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Diferencias de Caja (Patrimonial)')

    # Operación
    cta_ventas = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Ventas (Default)')
    cta_compras = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Compras (Default)')
    cta_clientes_default = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Deudores por Ventas (Default)')
    cta_proveedores_default = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Proveedores (Default)')
    cta_impuestos_internos = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Impuestos Internos')
    cta_itc = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. ITC Combustibles')
    cta_bonificaciones = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Bonificaciones')
    cta_descuentos_obtenidos = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Descuentos Obtenidos (compras)')
    
    # Cierres Contables
    cta_resultado_ejercicio = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='+', null=True, blank=True, verbose_name='Cta. Resultado del Ejercicio')

    # =========================================================================
    # CONFIGURACIÓN DE VOLUMEN / ALTA TRANSACCIONALIDAD
    # =========================================================================
    # Permite al sistema definir si las ventas de la empresa generan asientos inmediatos
    # (uno a uno por cada ticket) o si se acumulan para generar un Asiento Resumen Diario
    # consolidando todos los comprobantes por sucursal al final de la jornada.
    METODO_CONTAB_CHOICES = [
        (1, 'Individual (Por Comprobante)'),
        (2, 'Consolidado (Resumen Diario por Sucursal)'),
    ]
    metodo_contabilizacion_ventas = models.IntegerField(
        choices=METODO_CONTAB_CHOICES,
        default=1,
        verbose_name="Método Contabilización Ventas",
        help_text="Establece si se genera un asiento individual por cada ticket o un único asiento diario consolidado"
    )

    class Meta:
        db_table = "cble_parametros"
        verbose_name = "Parámetros Contables"
        verbose_name_plural = "Parámetros Contables"

    def __str__(self):
        return f"Parámetros Contables - {self.empresa.nombre}"


# =============================================================================
# SUBSISTEMA FISCAL — Libro IVA Digital (ARCA) + Retenciones/Percepciones
# =============================================================================
# Diseño: cabecera abstracta común a Compras y Ventas (tablas físicas separadas,
# sin campos vacíos) + dos satélites vinculados por asiento_id (igual que VFP):
#   - LibroIvaAlic        : desglose del IVA por alícuota (para el TXT de ARCA)
#   - RetPercSufrida      : retenciones/percepciones que TERCEROS nos practican
# Solo se generan registros cuando Compra/Venta.condic in (1, 3): el 1 es el circuito fiscal normal
# y el 3 (Ajuste) es una factura válida a nombre de la empresa que el dueño pagó de su bolsillo —
# no es gasto de la empresa, pero la factura SÍ se computa en IVA y Ganancias. El 2 (sin respaldo)
# y el 4 (ajuste de auditoría, que no genera comprobante) nunca alimentan el subsistema fiscal.

IMPUESTOS_RET_PERC = [
    ('IVA', 'IVA'),
    ('GAN', 'Ganancias'),
    ('IIBB', 'Ingresos Brutos'),
    ('TEM', 'Tasa Específica / TEM'),
    ('SIRCREB', 'SIRCREB'),
    ('SUSS', 'SUSS'),
    ('MUN', 'Municipal'),
    ('OTRO', 'Otro'),
]


class LibroIvaBase(models.Model):
    """Cabecera fiscal del Libro IVA Digital. Base abstracta común a Compras y Ventas:
    define los campos compartidos (y luego el pipeline de exportación) una sola vez,
    pero genera tablas físicas separadas para no arrastrar columnas vacías."""
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, verbose_name="Empresa")
    asiento_id = models.IntegerField(db_index=True, verbose_name="ID Asiento Contable")
    fecha = models.DateField(db_index=True, verbose_name="Fecha")
    periodo = models.CharField(max_length=6, default='', blank=True, db_index=True, verbose_name="Período YYYYMM")
    clienteproveedor = models.ForeignKey('facturacion.ClienteProveedor', on_delete=models.PROTECT, verbose_name="Cliente/Proveedor")

    # Identificación del comprobante
    codiva = models.CharField(max_length=3, verbose_name="Cód. Comprobante ARCA")  # '001'=Factura A
    punto = models.IntegerField(default=0, verbose_name="Punto de Venta")
    numero = models.BigIntegerField(verbose_name="Número")
    cuit = models.CharField(max_length=11, blank=True, verbose_name="CUIT")
    cae = models.CharField(max_length=20, default='', blank=True, db_index=True, verbose_name="CAE / CAI ARCA")

    # Importes (la cabecera totaliza; el detalle por alícuota vive en LibroIvaAlic)
    neto_gravado = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    exento = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    no_gravado = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    iva_total = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="IVA Total")
    otros = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Otros (ret/perc)")
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.codiva} {self.punto:04d}-{self.numero} | {self.clienteproveedor_id}"


class LibroIvaCompras(LibroIvaBase):
    class Meta:
        db_table = "cble_libro_iva_compras"
        verbose_name = "Libro IVA Compras"
        verbose_name_plural = "Libro IVA Compras"
        indexes = [
            models.Index(fields=['empresa', 'fecha']),
            models.Index(fields=['asiento_id']),
        ]


class LibroIvaVentas(LibroIvaBase):
    # Campos propios de comprobantes EMITIDOS (no aplican a compras)
    vto_cae = models.DateField(null=True, blank=True, verbose_name="Vto. CAE")
    codigo_qr = models.TextField(blank=True, verbose_name="Código QR")

    class Meta:
        db_table = "cble_libro_iva_ventas"
        verbose_name = "Libro IVA Ventas"
        verbose_name_plural = "Libro IVA Ventas"
        indexes = [
            models.Index(fields=['empresa', 'fecha']),
            models.Index(fields=['asiento_id']),
        ]


class LibroIvaAlic(models.Model):
    """Satélite único: desglose del IVA por alícuota, para el TXT de alícuotas de ARCA.
    Vinculado por asiento_id; `c_v` discrimina el libro de origen."""
    C_V = [('C', 'Compras'), ('V', 'Ventas')]

    asiento_id = models.IntegerField(db_index=True, verbose_name="ID Asiento Contable")
    c_v = models.CharField(max_length=1, choices=C_V, db_index=True)
    neto = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    alicuota = models.DecimalField(max_digits=6, decimal_places=2, default=0)  # 21.00, 10.50, 27.00...
    iva = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    # Crédito/débito computable. En compras = neto*alicuota; en ventas siempre = iva.
    computable = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    # En gastos guarda el código de alícuota ARCA (4 díg: 0003..0009); en bienes, el de comprobante.
    codiva = models.CharField(max_length=4, blank=True, verbose_name="Cód. Alícuota / Comprobante ARCA")

    class Meta:
        db_table = "cble_libro_iva_alic"
        verbose_name = "Alícuota Libro IVA"
        verbose_name_plural = "Alícuotas Libro IVA"

    def __str__(self):
        return f"[{self.c_v}] As.{self.asiento_id} {self.alicuota}% IVA {self.iva}"


class RetPercSufrida(models.Model):
    """Retenciones/percepciones que TERCEROS nos practican (sufridas).
    Tabla única vinculada por asiento_id, lo que la cuelga de las 4 tablas madre
    (compras, ventas, recibos, órdenes de pago). NO se usa cuando NOSOTROS somos
    agentes (ventas/OP), que tienen su propia estructura."""
    ORIGEN = [('C', 'Compra'), ('V', 'Venta'), ('R', 'Recibo'), ('OP', 'Orden de Pago')]
    TIPO = [('R', 'Retención'), ('P', 'Percepción')]

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, verbose_name="Empresa")
    asiento_id = models.IntegerField(db_index=True, verbose_name="ID Asiento Contable")
    origen = models.CharField(max_length=2, choices=ORIGEN, db_index=True)
    tipo = models.CharField(max_length=1, choices=TIPO)
    impuesto = models.CharField(max_length=10, choices=IMPUESTOS_RET_PERC, db_index=True)

    base = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Base imponible")
    alicuota = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    importe = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # IIBB/SIRCREB: convenio multilateral admite varias filas por jurisdicción.
    jurisdiccion = models.ForeignKey('facturacion.Jurisdiccion', on_delete=models.PROTECT, null=True, blank=True, verbose_name="Jurisdicción")

    # Datos del certificado, para conciliar con reportes de organismos (SICORE, DGR, municipios)
    nro_certificado = models.CharField(max_length=30, blank=True, verbose_name="Nro. Certificado")
    fecha = models.DateField(null=True, blank=True, verbose_name="Fecha Certificado")
    cuit_agente = models.CharField(max_length=11, blank=True, verbose_name="CUIT Agente")
    razon_social_agente = models.CharField(max_length=200, blank=True, verbose_name="Razón Social Agente")
    regimen = models.CharField(max_length=10, blank=True, verbose_name="Régimen", help_text="Código de régimen ARCA/DGR")

    class Meta:
        db_table = "cble_ret_perc_sufrida"
        verbose_name = "Retención/Percepción Sufrida"
        verbose_name_plural = "Retenciones/Percepciones Sufridas"
        indexes = [
            models.Index(fields=['empresa', 'fecha']),
            models.Index(fields=['asiento_id']),
            models.Index(fields=['empresa', 'impuesto']),
        ]

    def __str__(self):
        signo = "Ret" if self.tipo == 'R' else "Perc"
        return f"{signo} {self.impuesto} ${self.importe} (As.{self.asiento_id})"


class RetencionPracticada(models.Model):
    """Retenciones que NOSOTROS practicamos al pagar (somos agentes de retención).

    Es la contracara de `RetPercSufrida`: aquélla registra lo que terceros nos retienen (crédito
    fiscal); ésta, lo que retenemos al proveedor y quedamos debiendo al fisco hasta depositarlo.
    Las retenciones sufridas NO se cargan acá: llegan como Compra/Venta con su comprobante.

    Es la base de la DDJJ SICORE. Principal caso: Ganancias RG 830.

    El `regimen` no lo tipea el operador: se deduce de la cuenta imputada en las facturas que
    se están pagando, encadenando `Compra.cta_imputacion → Cuenta.rg_830` (ver
    `contable.services.retenciones.regimen_rg830_de_compra`).
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, verbose_name="Empresa")
    orden_pago = models.ForeignKey(
        'tesoreria.OrdenPago', on_delete=models.CASCADE,
        related_name='retenciones_practicadas', verbose_name="Orden de Pago")
    proveedor = models.ForeignKey('facturacion.ClienteProveedor', on_delete=models.PROTECT, verbose_name="Proveedor Retenido")

    impuesto = models.CharField(max_length=10, choices=IMPUESTOS_RET_PERC, default='GAN', db_index=True)
    regimen = models.CharField(max_length=10, blank=True, verbose_name="Régimen", help_text="Código de régimen ARCA (RG 830). Se sugiere desde la cuenta imputada en las facturas pagadas.")

    nro_certificado = models.CharField(max_length=30, blank=True, verbose_name="Nro. Certificado")
    fecha = models.DateField(db_index=True, verbose_name="Fecha del Certificado")
    base = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Base imponible")
    alicuota = models.DecimalField(max_digits=6, decimal_places=3, default=0, verbose_name="Alícuota %")
    importe = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Importe Retenido")

    cuit_retenido = models.CharField(max_length=20, blank=True, verbose_name="CUIT del Retenido")
    asiento_id = models.IntegerField(null=True, blank=True, db_index=True, verbose_name="ID Asiento Contable")

    class Meta:
        db_table = "cble_retencion_practicada"
        verbose_name = "Retención Practicada"
        verbose_name_plural = "Retenciones Practicadas"
        indexes = [
            models.Index(fields=['empresa', 'fecha']),
            models.Index(fields=['empresa', 'impuesto']),
        ]

    def __str__(self):
        return f"Ret. {self.impuesto} {self.nro_certificado} ${self.importe}"


class AlicuotaIva(models.Model):
    """Tabla de referencia (configurable) de las alícuotas de IVA con su código ARCA.
    Códigos oficiales: 0003=0%, 0004=10,5%, 0005=21%, 0006=27%, 0008=5%, 0009=2,5%.
    Es nacional (no por empresa). Alimenta el selector de alícuotas en la carga de gastos."""
    codigo = models.CharField(max_length=4, unique=True, verbose_name="Cód. Alícuota ARCA")
    descripcion = models.CharField(max_length=50, verbose_name="Descripción")
    porcentaje = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Alícuota %")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    orden = models.IntegerField(default=0, verbose_name="Orden")

    class Meta:
        db_table = "cble_alicuotas_iva"
        verbose_name = "Alícuota de IVA"
        verbose_name_plural = "Alícuotas de IVA"
        ordering = ['orden', 'codigo']

    def __str__(self):
        return f"{self.codigo} · {self.descripcion}"
