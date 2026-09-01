from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
import datetime
from django.utils import timezone
from core.models import AuditModel
from empresas.models import Empresa, Sucursal, Ejercicio
from facturacion.models import ClienteProveedor, Venta, Compra

class Banco(models.Model):
    codigo_bcra = models.CharField(max_length=10, null=True, blank=True, verbose_name="Código BCRA")
    nombre = models.CharField(max_length=150, verbose_name="Nombre del Banco")

    class Meta:
        db_table = "tesoreria_banco"
        verbose_name = "Banco"
        verbose_name_plural = "Bancos"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre}"

class Tarjeta(models.Model):
    codigo = models.CharField(max_length=50, verbose_name="Código")
    nombre = models.CharField(max_length=100, verbose_name="Nombre de la Tarjeta")
    TIPO_CHOICES = [('C', 'Crédito'), ('D', 'Débito')]
    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES, default='C', verbose_name="Tipo de Tarjeta")

    class Meta:
        db_table = "tesoreria_tarjeta"
        verbose_name = "Tarjeta"
        verbose_name_plural = "Tarjetas"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class MedioPago(AuditModel):
    CATEGORIAS = [
        ('EFE', 'Efectivo'),
        ('CHQ', 'Cheque'),
        ('TRA', 'Transferencia'),
        ('TAR', 'Tarjeta'),
        ('RET', 'Retención'),
        ('DIG', 'Billetera Digital'),
        ('OTR', 'Otros'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    codigo = models.CharField(max_length=10, verbose_name="Código")
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    categoria = models.CharField(max_length=3, choices=CATEGORIAS)
    cuenta_contable = models.ForeignKey(
        'contable.Cuenta', on_delete=models.PROTECT,
        null=True, blank=True,
        verbose_name="Cuenta Contable Vinculada"
    )
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "tesoreria_medio_pago"
        unique_together = ('empresa', 'codigo')
        verbose_name = "Medio de Pago"
        verbose_name_plural = "Medios de Pago"
        ordering = ['categoria', 'nombre']

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"

class CuentaBancaria(AuditModel):
    MONEDAS = [('PES', 'PESO'), ('DOL', 'DOLAR'), ('060', 'EURO')]

    cta_bc_id = models.AutoField(primary_key=True)
    banco = models.CharField(max_length=150, verbose_name="Banco")
    moneda = models.CharField(max_length=3, choices=MONEDAS, default='PES', verbose_name="Moneda")
    cta_numero = models.CharField(max_length=100, verbose_name="Número de Cuenta")
    cbu = models.CharField(max_length=100, null=True, blank=True, verbose_name="CBU/CVU")
    
    cli_pro = models.ForeignKey('facturacion.ClienteProveedor', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Cliente/Proveedor Vinculado")
    cuenta_contable = models.ForeignKey('contable.Cuenta', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Cuenta Contable Vinculada")

    # Circuito del cheque propio en DOS TRAMOS (Plan 035 §1.6). Al emitirlo, la Orden de Pago
    # acredita ESTA cuenta (pasivo "Cheques Emitidos a Pagar"), no la cuenta bancaria: el banco
    # todavía no debitó nada. Recién la conciliación bancaria, al registrar el débito real,
    # cancela este pasivo contra `cuenta_contable`.
    # Así el saldo contable del banco coincide con el extracto, y los cheques librados y no
    # debitados quedan visibles como deuda propia. Diferidos y al día se tratan igual.
    # Las transferencias NO usan esta cuenta: debitan de inmediato contra `cuenta_contable`.
    cuenta_contable_cheques = models.ForeignKey(
        'contable.Cuenta', on_delete=models.PROTECT, null=True, blank=True,
        related_name='cuentas_bancarias_cheques',
        verbose_name="Cta. Contable Cheques Emitidos")


    banco_id = models.IntegerField(null=True, blank=True, verbose_name="ID Banco Extra")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")

    class Meta:
        db_table = "cble_cuenta_bancaria"
        verbose_name = "Cuenta Bancaria"
        verbose_name_plural = "Cuentas Bancarias"

    def __str__(self):
        return f"{self.banco} - {self.cta_numero} ({self.moneda})"

class Recibo(AuditModel):
    TIPOS = [
        ('C', 'Cobranza Clientes'),
        ('S', 'Recibo Simple')
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT)
    ejercicio = models.ForeignKey(Ejercicio, on_delete=models.PROTECT)
    sesion_caja = models.ForeignKey('CajaSesion', on_delete=models.PROTECT, null=True, blank=True, verbose_name='Turno de Caja')
    
    tipo = models.CharField(max_length=1, choices=TIPOS, default='C')
    cliente = models.ForeignKey(ClienteProveedor, on_delete=models.PROTECT)
    fecha = models.DateField(db_index=True)
    punto = models.IntegerField(default=1)
    numero = models.BigIntegerField(db_index=True)
    
    moneda = models.CharField(max_length=3, default='PES', verbose_name='Moneda del Recibo')
    cotizacion = models.DecimalField(max_digits=15, decimal_places=4, default=1.0)
    
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    observaciones = models.TextField(null=True, blank=True)
    anulado = models.BooleanField(default=False)
    condic = models.IntegerField(default=1, verbose_name="Condición")
    
    asiento_id = models.IntegerField(null=True, blank=True, verbose_name="ID Asiento Contable")
    
    class Meta:
        verbose_name = "Recibo"
        verbose_name_plural = "Recibos"
        unique_together = ('empresa', 'punto', 'numero')
        indexes = [
            models.Index(fields=['empresa', 'fecha']),
        ]

    def __str__(self):
        return f"RC {self.punto:04d}-{self.numero:08d} | {self.cliente.razon_social}"

    def save(self, *args, **kwargs):
        if not self.numero:
            last = Recibo.objects.filter(empresa=self.empresa, punto=self.punto).order_by('-numero').first()
            self.numero = (last.numero + 1) if last else 1
        super().save(*args, **kwargs)


class ReciboImputacion(models.Model):
    recibo = models.ForeignKey(Recibo, on_delete=models.CASCADE, related_name='imputaciones_simples')
    cuenta_contable = models.ForeignKey('contable.Cuenta', on_delete=models.PROTECT)
    importe = models.DecimalField(max_digits=15, decimal_places=2)
    leyenda = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        verbose_name = "Imputación de Recibo Simple"
        verbose_name_plural = "Imputaciones de Recibos Simples"

    def __str__(self):
        return f"RC {self.recibo.numero} -> {self.cuenta_contable.cuenta}: ${self.importe}"


class ReciboAplicacion(models.Model):
    """Imputación de una cobranza a un comprobante concreto.

    Es la FUENTE DE VERDAD del saldo de la venta (Plan 035 §1.3): `Venta.saldo` se deriva
    sumando estas filas, nunca decrementando un contador.

    Dos importes porque conviven dos unidades de medida:
      - `importe`       → en la MONEDA DEL COMPROBANTE, que es la unidad en la que vive su
                          saldo. Es el que se suma para derivar el saldo.
      - `importe_pesos` → pesificado a la cotización con la que se cobró. Alimenta el asiento
                          y los reportes. En comprobantes en pesos ambos coinciden.
    """
    recibo = models.ForeignKey(Recibo, on_delete=models.CASCADE, related_name='aplicaciones')
    venta = models.ForeignKey('facturacion.Venta', on_delete=models.PROTECT, related_name='cobros_aplicados')
    importe = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Importe (moneda del comprobante)")
    importe_pesos = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Importe Pesificado")

    class Meta:
        verbose_name = "Aplicación de Recibo"
        verbose_name_plural = "Aplicaciones de Recibos"
        indexes = [
            models.Index(fields=['venta']),
            models.Index(fields=['recibo']),
        ]

    def __str__(self):
        return f"RC {self.recibo.numero} -> Fac {self.venta.numero}: ${self.importe}"


class OrdenPago(AuditModel):
    TIPOS = [
        ('P', 'Pago a Proveedor'),
        ('S', 'Orden de Pago Simple')
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT)
    ejercicio = models.ForeignKey(Ejercicio, on_delete=models.PROTECT)
    sesion_caja = models.ForeignKey('CajaSesion', on_delete=models.PROTECT, null=True, blank=True, verbose_name='Caja de Tesorería')

    tipo = models.CharField(max_length=1, choices=TIPOS, default='P')
    proveedor = models.ForeignKey(ClienteProveedor, on_delete=models.PROTECT)
    fecha = models.DateField(db_index=True)
    punto = models.IntegerField(default=1)
    numero = models.BigIntegerField(db_index=True)
    
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    observaciones = models.TextField(null=True, blank=True)
    anulado = models.BooleanField(default=False)
    condic = models.IntegerField(default=1, verbose_name="Condición")

    asiento_id = models.IntegerField(null=True, blank=True, verbose_name="ID Asiento Contable")

    class Meta:
        verbose_name = "Orden de Pago"
        verbose_name_plural = "Órdenes de Pago"
        unique_together = ('empresa', 'punto', 'numero')
        indexes = [
            models.Index(fields=['empresa', 'fecha']),
        ]

    def __str__(self):
        return f"OP {self.punto:04d}-{self.numero:08d} | {self.proveedor.razon_social}"

    def save(self, *args, **kwargs):
        if not self.numero:
            last = OrdenPago.objects.filter(empresa=self.empresa, punto=self.punto).order_by('-numero').first()
            self.numero = (last.numero + 1) if last else 1
        super().save(*args, **kwargs)


class OrdenPagoImputacion(models.Model):
    orden_pago = models.ForeignKey(OrdenPago, on_delete=models.CASCADE, related_name='imputaciones_simples')
    cuenta_contable = models.ForeignKey('contable.Cuenta', on_delete=models.PROTECT)
    importe = models.DecimalField(max_digits=15, decimal_places=2)
    leyenda = models.CharField(max_length=200, blank=True, null=True)

class OrdenPagoAplicacion(models.Model):
    """Imputación de un pago a un comprobante concreto del proveedor.

    Es la FUENTE DE VERDAD del saldo de la compra (Plan 035 §1.3) y el insumo del papel de
    trabajo "factura ↔ órdenes de pago que la cancelaron".

    El importe conserva el SIGNO del comprobante: aplicar una Nota de Crédito (que se graba en
    negativo) lleva importe negativo, de modo que el neto aplicado sea el que efectivamente se
    paga. Ver `importe` / `importe_pesos` en ReciboAplicacion.
    """
    orden_pago = models.ForeignKey(OrdenPago, on_delete=models.CASCADE, related_name='aplicaciones')
    compra = models.ForeignKey(Compra, on_delete=models.PROTECT, related_name='pagos_aplicados')
    importe = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Importe (moneda del comprobante)")
    importe_pesos = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Importe Pesificado")

    class Meta:
        verbose_name = "Aplicación de OP"
        verbose_name_plural = "Aplicaciones de OPs"
        indexes = [
            models.Index(fields=['compra']),
            models.Index(fields=['orden_pago']),
        ]

    def __str__(self):
        return f"OP {self.orden_pago.numero} -> Fac {self.compra.numero}: ${self.importe}"

class Caja(models.Model):
    TIPO_CAJA = [
        ('M', 'Mostrador'),
        ('T', 'Tesorería / Central'),
        # Distribución (Plan 074 §7.9): se abre y cierra por REPARTO, no por turno de
        # cajero, la maneja alguien que está en la calle y su cierre se concilia contra la
        # hoja de ruta. Un tipo explícito evita ramificar el código de la mostrador con
        # condicionales para una regla de negocio que es otra.
        ('R', 'Recaudadora / Reparto'),
        # El nivel INTERMEDIO del circuito de fondos de distribución (Plan 076 §B): acá
        # rinden los repartos y los vendedores, y de acá sale una sola rendición
        # consolidada a Tesorería. Se comporta igual que la mostrador —acumula y después
        # rinde por retiro/cierre—, pero la opera el administrativo de reparto, no un
        # cajero de turno. Es UNA POR SUCURSAL.
        ('D', 'Tesorería de Reparto'),
    ]
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=50, verbose_name="Nombre de la Caja")
    tipo = models.CharField(max_length=1, choices=TIPO_CAJA, default='M', verbose_name="Tipo de Caja")
    activa = models.BooleanField(default=True)
    
    class Meta:
        db_table = "tesoreria_caja"
        verbose_name = "Caja"
        verbose_name_plural = "Cajas"
        
    def __str__(self):
        return f"{self.nombre} ({self.sucursal.nombre})"

class CajaSesion(AuditModel):
    caja = models.ForeignKey(Caja, on_delete=models.PROTECT, related_name="sesiones")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Cajero")
    fecha_apertura = models.DateTimeField(auto_now_add=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)

    saldo_inicial = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    saldo_final_calculado = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    saldo_final_declarado = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    estado = models.CharField(max_length=1, choices=[('A', 'Abierta'), ('C', 'Cerrada')], default='A')

    # --- Caja Diaria de Tesorería (Caja.tipo='T') ---
    # Estos campos NO los usa la caja mostrador, que sigue trabajando con `saldo_inicial` y el
    # arqueo ciego. La caja de tesorería es por SUCURSAL (no por cajero) y lleva sus saldos
    # desglosados por tipo de disponibilidad, como el `enc_caja_diaria` del sistema legado.
    numero = models.IntegerField(null=True, blank=True, db_index=True, verbose_name="N° de Caja")
    # Se estampa recién al cerrar: mientras la caja está activa va en null (igual que el legado,
    # donde la caja abierta figura en la lista sin fecha).
    fecha_operativa = models.DateField(null=True, blank=True, db_index=True, verbose_name="Fecha de la Caja")

    si_efectivo = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Saldo Inicial Efectivo")
    si_dolares = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Saldo Inicial Dólares")
    si_valores = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Saldo Inicial Valores")

    # Congelados al cerrar, para no recalcular el histórico ni depender de asientos posteriores.
    sf_efectivo = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Saldo Final Efectivo")
    sf_dolares = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Saldo Final Dólares")
    sf_valores = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Saldo Final Valores")

    class Meta:
        db_table = "tesoreria_caja_sesion"
        verbose_name = "Sesión de Caja"
        verbose_name_plural = "Sesiones de Caja"
        indexes = [
            models.Index(fields=['caja', 'estado']),
        ]

    def __str__(self):
        return f"Sesión {self.id} - {self.caja.nombre} - {self.usuario.username}"

    @property
    def saldo_inicial_neto(self):
        """Neto disponible al abrir = Efectivo + Dólares + Valores (Banco y Tarjetas NO integran)."""
        return self.si_efectivo + self.si_dolares + self.si_valores

    @property
    def saldo_final_neto(self):
        return self.sf_efectivo + self.sf_dolares + self.sf_valores

    @property
    def abierta(self):
        return self.estado == 'A'

class MovimientoCaja(AuditModel):
    sesion = models.ForeignKey(CajaSesion, on_delete=models.PROTECT, related_name="movimientos")

    # Empresa desnormalizada (Plan 049). Toda consulta se acota por session['empresa_id'] y hasta
    # ahora había que llegar por sesion -> caja -> empresa: tres JOINs en cada reporte.
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, null=True, blank=True,
                                verbose_name="Empresa")

    # FECHA DEL COMPROBANTE que origina el movimiento (recibo, orden de pago, venta, retiro). Es
    # la misma que la del asiento contable, y la que usan los reportes para el rango desde/hasta.
    # NO es la fecha de carga: un comprobante fechado el 15/08 puede registrarse el 20/09, y antes
    # de este cambio (`auto_now_add`) caía en septiembre en cualquier reporte por período.
    # Cuándo se cargó el registro lo dice `fecha_creacion`, heredado de AuditModel.
    # Sin db_index propio: el índice compuesto (empresa, fecha) de Meta lo cubre, y por regla del
    # proyecto NINGUNA consulta se hace sin acotar por empresa.
    fecha = models.DateField(verbose_name="Fecha del Comprobante")

    TIPO_MOVIMIENTO = [
        ('I', 'Ingreso (Cobro Venta)'),
        ('E', 'Egreso (Pago)'),
        ('A', 'Apertura (Fondo Fijo)'),
        ('R', 'Retiro (Depósito/Arqueo)')
    ]
    tipo = models.CharField(max_length=1, choices=TIPO_MOVIMIENTO)
    importe = models.DecimalField(max_digits=15, decimal_places=2)
    concepto = models.CharField(max_length=200)
    # Solo 1 (Real) y 2 (Presupuestado): ver el CheckConstraint al pie.
    condic = models.IntegerField(default=1, verbose_name="Condición Movimiento")

    # --- Vínculo contable (Plan 049) ---
    # El asiento es la FUENTE DE VERDAD de las contrapartidas: sus líneas llevan cada cuenta con
    # su importe exacto. Los asientos nunca se borran (`anular_asiento_de_comprobante` solo marca
    # anulado=True), así que la FK no puede quedar colgada. Al recontabilizar un comprobante el
    # asiento cambia de número y este campo se re-estampa, igual que en TransaccionBancaria.
    asiento = models.ForeignKey('contable.Asiento', on_delete=models.PROTECT,
                                null=True, blank=True, related_name='movimientos_caja',
                                verbose_name="Asiento Contable")

    # Cuenta de imputación PRINCIPAL = la contrapartida de mayor importe del asiento.
    # Cuando el comprobante imputa a varias cuentas (recibo simple, orden de pago simple, venta
    # mostrador con varios rubros) este campo guarda SOLO la mayor: sirve para listados, filtros y
    # búsquedas, pero NO para cuadrar importes por cuenta. Para eso se leen las líneas del
    # asiento, que es donde está el desglose completo. Ver services/imputacion.py.
    cuenta = models.ForeignKey('contable.Cuenta', on_delete=models.PROTECT,
                               null=True, blank=True, related_name='movimientos_caja',
                               verbose_name="Cuenta de Imputación Principal")

    # Cliente/Proveedor del movimiento. Antes había que probar las tres FK nulleables de abajo y
    # seguir la que estuviera seteada. Nulo en los movimientos internos (retiro, cierre,
    # rendición), igual que el `id_cod` del sistema legado.
    cli_pro = models.ForeignKey('facturacion.ClienteProveedor', on_delete=models.PROTECT,
                                null=True, blank=True, related_name='movimientos_caja',
                                verbose_name="Cliente/Proveedor")

    # Vinculación
    recibo = models.ForeignKey(Recibo, on_delete=models.SET_NULL, null=True, blank=True)
    orden_pago = models.ForeignKey(OrdenPago, on_delete=models.SET_NULL, null=True, blank=True)
    venta = models.ForeignKey(Venta, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "tesoreria_movimiento_caja"
        verbose_name = "Movimiento de Caja"
        verbose_name_plural = "Movimientos de Caja"
        indexes = [
            # EOAF: rango de fechas por empresa, y agrupación por cuenta de imputación.
            # `asiento` y `cli_pro` NO llevan índice explícito: Django ya indexa toda FK, y
            # duplicarlo solo costaría escrituras.
            models.Index(fields=['empresa', 'fecha'], name='idx_movcaja_emp_fecha'),
            models.Index(fields=['empresa', 'cuenta'], name='idx_movcaja_emp_cuenta'),
        ]
        constraints = [
            # En movimientos de FONDOS solo existen Real y Presupuestado. El 3 (Ajuste) lo paga el
            # socio y no mueve plata de la empresa; el 4 son ajustes del estudio contable; los
            # 5/6/7 los genera el sistema y no tocan caja. Regla inflexible -> va a la base.
            models.CheckConstraint(condition=models.Q(condic__in=(1, 2)),
                                   name='mov_caja_condic_1_o_2'),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} - ${self.importe}"

class MovimientoCajaDetalle(models.Model):
    movimiento_caja = models.ForeignKey(MovimientoCaja, on_delete=models.CASCADE, related_name="detalles")
    medio_pago = models.ForeignKey(MedioPago, on_delete=models.PROTECT, verbose_name="Medio de Pago")
    importe = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Importe Base (ARS)")
    importe_moneda_extranjera = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Importe Extranjera (USD)")
    cotizacion = models.DecimalField(max_digits=15, decimal_places=4, default=1.0, verbose_name="Cotización")
    
    class Meta:
        db_table = "tesoreria_movimiento_caja_detalle"
        verbose_name = "Detalle Movimiento de Caja"
        verbose_name_plural = "Detalles Movimiento de Caja"
        
    def __str__(self):
        return f"Detalle de {self.movimiento_caja.id} - {self.medio_pago.nombre}"


class CobroTarjeta(models.Model):
    movimiento_detalle = models.ForeignKey('MovimientoCajaDetalle', on_delete=models.CASCADE, related_name='cobros_tarjeta', null=True, blank=True)
    tarjeta = models.ForeignKey(Tarjeta, on_delete=models.PROTECT)
    lote = models.CharField(max_length=50, null=True, blank=True)
    cupon = models.CharField(max_length=50, null=True, blank=True)
    cuotas = models.IntegerField(default=1)
    # se omite importe porque ya est en el detalle
    sucursal_id = models.IntegerField(null=True, blank=True)
    
    class Meta:
        db_table = "tesoreria_cobro_tarjeta"
        verbose_name = "Cobro con Tarjeta"
        verbose_name_plural = "Cobros con Tarjetas"

class TransaccionBancaria(models.Model):
    """Movimientos de valores bancarios propios (Plan 035 §1.2 y §5).

    Lleva EXCLUSIVAMENTE tres conceptos: cheque emitido, transferencia emitida y transferencia
    recibida. Los movimientos que informa el banco (comisiones, débitos automáticos, impuestos)
    NO van acá: son de la tabla de captura de homebanking del módulo de conciliación (plan 008).

    Es una entidad autónoma: tiene su propia `empresa`, su propio `importe` y sus propias
    fechas. Antes había que llegar a esos datos por cuatro JOINs
    (detalle → movimiento_caja → sesión → caja → empresa) y el importe ni siquiera existía.
    """
    TIPO_CHOICES = [
        ('TR', 'Transferencia Recibida'),
        ('TE', 'Transferencia Emitida'),
        ('CP', 'Cheque Propio')
    ]
    ESTADOS = [
        ('E', 'Emitida / Pendiente'),   # librada, el banco todavía no la debitó
        ('D', 'Debitada / Acreditada'), # confirmada por la conciliación bancaria
        ('R', 'Rechazada'),
        ('A', 'Anulada'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, null=True, blank=True, db_index=True, verbose_name="Empresa")
    tipo_transaccion = models.CharField(max_length=2, choices=TIPO_CHOICES, default='TR')
    movimiento_detalle = models.ForeignKey('MovimientoCajaDetalle', on_delete=models.PROTECT, related_name='transacciones_bancarias', null=True, blank=True)
    cuenta_bancaria = models.ForeignKey('CuentaBancaria', on_delete=models.PROTECT)
    numero_operacion = models.CharField(max_length=100, blank=True, null=True, verbose_name="Número de Operación / Cheque")
    importe = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Importe")
    cuit_contraparte = models.CharField(max_length=20, blank=True, verbose_name="CUIT Destino / Origen")

    # Fecha REAL del movimiento bancario (la del comprobante que lo origina), no la del día en
    # que se cargó: es la clave del matching contra el extracto.
    fecha_operacion = models.DateField(default=timezone.localdate, db_index=True)
    fecha_vencimiento = models.DateField(null=True, blank=True, verbose_name="Fecha Vencimiento (Cheque Propio)")

    # Tramo 2 del cheque propio: cuándo el banco lo debitó de verdad y con qué asiento se
    # canceló el pasivo "Cheques Emitidos a Pagar" contra la cuenta bancaria (§1.6).
    estado = models.CharField(max_length=1, choices=ESTADOS, default='E', verbose_name="Estado")
    fecha_debito = models.DateField(null=True, blank=True, verbose_name="Fecha de Débito en Cuenta")
    asiento_id = models.IntegerField(null=True, blank=True, db_index=True, verbose_name="ID Asiento de Emisión")
    asiento_debito_id = models.IntegerField(null=True, blank=True, verbose_name="ID Asiento de Débito")

    class Meta:
        db_table = "tesoreria_transaccion_bancaria"
        verbose_name = "Transacción Bancaria"
        verbose_name_plural = "Transacciones Bancarias"
        indexes = [
            models.Index(fields=['empresa', 'fecha_operacion']),
            models.Index(fields=['cuenta_bancaria', 'estado']),
        ]

    def __str__(self):
        return f"{self.get_tipo_transaccion_display()} {self.numero_operacion or ''} ${self.importe}"

class ValorTerceros(models.Model):
    """Cheque de tercero: entra por un Recibo y puede salir entregado en una Orden de Pago.

    Entidad autónoma con su historia completa (Plan 035 §5): guarda su propio `importe` y los
    dos momentos de su vida —recepción y entrega— cada uno con su fecha y su asiento.

    El `importe` es propio y NO se lee del movimiento de caja de recepción: era la única
    referencia del valor del cheque, así que al entregarlo el backend tomaba el importe que
    mandaba el navegador sin nada contra qué contrastarlo.
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, null=True, blank=True, db_index=True, verbose_name="Empresa")
    banco = models.ForeignKey('Banco', on_delete=models.PROTECT)
    numero_cheque = models.CharField(max_length=50)
    importe = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Importe del Valor")
    fecha_emision = models.DateField()
    fecha_vencimiento = models.DateField(db_index=True)
    cuit_firmante = models.CharField(max_length=20, blank=True)
    nombre_firmante = models.CharField(max_length=100, blank=True)
    sucursal_id = models.IntegerField(null=True, blank=True)

    # --- Recepción: de dónde vino ---
    recibo = models.ForeignKey('Recibo', on_delete=models.SET_NULL, null=True, blank=True, related_name='valores_recibidos')
    movimiento_detalle = models.ForeignKey('MovimientoCajaDetalle', on_delete=models.PROTECT, related_name='valores', null=True, blank=True)
    fecha_recepcion = models.DateField(null=True, blank=True, verbose_name="Fecha de Recepción")
    asiento_recepcion_id = models.IntegerField(null=True, blank=True, verbose_name="ID Asiento de Recepción")

    # --- Entrega: a dónde fue ---
    orden_pago = models.ForeignKey('OrdenPago', on_delete=models.SET_NULL, null=True, blank=True, related_name='valores_entregados')
    fecha_entrega = models.DateField(null=True, blank=True, verbose_name="Fecha de Entrega")
    asiento_entrega_id = models.IntegerField(null=True, blank=True, verbose_name="ID Asiento de Entrega")

    ESTADOS = [
        ('C', 'En Cartera'),
        ('D', 'Depositado'),
        ('E', 'Entregado (Pago)'),
        ('R', 'Rechazado')
    ]
    estado = models.CharField(max_length=1, choices=ESTADOS, default='C', db_index=True)

    class Meta:
        db_table = "tesoreria_valor_terceros"
        verbose_name = "Valor de Terceros"
        verbose_name_plural = "Valores de Terceros"
        indexes = [
            models.Index(fields=['empresa', 'estado']),
            models.Index(fields=['empresa', 'fecha_vencimiento']),
        ]

    def __str__(self):
        return f"Cheque {self.numero_cheque} - {self.banco} ${self.importe}"

class RetiroCaja(AuditModel):
    sesion = models.ForeignKey(CajaSesion, on_delete=models.PROTECT, related_name='retiros')
    tipo = models.CharField(max_length=1, choices=[('P', 'Parcial'), ('C', 'Cierre')])
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    sucursal_origen = models.ForeignKey(Sucursal, on_delete=models.PROTECT, related_name='retiros_enviados')
    sucursal_destino = models.ForeignKey(Sucursal, on_delete=models.PROTECT, related_name='retiros_recibidos')
    efectivo_pesos = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Efectivo Pesos Declarado")
    efectivo_dolares = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Efectivo Dólares Declarado")
    cotizacion_dolar = models.DecimalField(max_digits=15, decimal_places=4, default=1.0)
    observaciones = models.TextField(null=True, blank=True)
    anulado = models.BooleanField(default=False)

    # --- Rendición en 2 pasos (estado de recepción en Tesorería) ---
    ESTADO_RENDICION = [
        ('T', 'En Tránsito'),   # retirado de la mostrador, pendiente de recibir
        ('R', 'Recibida'),      # contada y aceptada por el tesorero
        ('A', 'Anulada'),
    ]
    estado = models.CharField(max_length=1, choices=ESTADO_RENDICION, default='T', verbose_name="Estado Rendición")
    sesion_recepcion = models.ForeignKey(
        CajaSesion, on_delete=models.PROTECT, null=True, blank=True,
        related_name='rendiciones_recibidas', verbose_name="Sesión de Tesorería que recibe")
    usuario_recepcion = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='rendiciones_recibidas', verbose_name="Tesorero que recibe")
    fecha_recepcion = models.DateTimeField(null=True, blank=True)
    efectivo_pesos_recibido = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Efectivo Pesos Contado")
    efectivo_dolares_recibido = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Efectivo Dólares Contado")
    diferencia_pesos = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Diferencia (faltante +, sobrante -)")
    asiento_diferencia_id = models.IntegerField(null=True, blank=True, verbose_name="ID Asiento de Diferencia")

    class Meta:
        db_table = "tesoreria_retiro_caja"
        verbose_name = "Retiro de Caja"
        verbose_name_plural = "Retiros de Caja"

class RetiroCajaValor(models.Model):
    retiro = models.ForeignKey('RetiroCaja', on_delete=models.CASCADE)
    valor = models.ForeignKey(ValorTerceros, on_delete=models.CASCADE)

    class Meta:
        db_table = "tesoreria_retiro_caja_valor"

class RetiroCajaTarjeta(models.Model):
    retiro = models.ForeignKey(RetiroCaja, on_delete=models.CASCADE, related_name='cupones')
    cobro_tarjeta = models.ForeignKey(CobroTarjeta, on_delete=models.PROTECT)

    class Meta:
        db_table = "tesoreria_retiro_caja_tarjeta"

class RetiroCajaAsiento(models.Model):
    retiro = models.ForeignKey(RetiroCaja, on_delete=models.CASCADE, related_name='asientos')
    asiento_id = models.IntegerField()

    class Meta:
        db_table = "tesoreria_retiro_caja_asiento"
