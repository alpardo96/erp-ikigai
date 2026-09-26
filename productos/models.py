from django.db import models
from django.conf import settings
from decimal import Decimal, InvalidOperation
from core.models import AuditModel
from empresas.models import Empresa, Sucursal
from facturacion.models import ClienteProveedor
from django.db.models import Sum

ALICUOTAS_IVA_CHOICES = [
    (Decimal('21.00'), '21%'),
    (Decimal('10.50'), '10.5%'),
    (Decimal('0.00'), '0%'),
    (Decimal('27.00'), '27%'),
    (Decimal('5.00'), '5%'),
    (Decimal('2.50'), '2.5%'),
]

ALICUOTAS_ARCA_MAP = {
    Decimal('0.00'): 3,   # 0%
    Decimal('10.50'): 4,  # 10.5%
    Decimal('21.00'): 5,  # 21%
    Decimal('27.00'): 6,  # 27%
    Decimal('5.00'): 8,   # 5%
    Decimal('2.50'): 9,   # 2.5%
}

class Marca(AuditModel):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    # Nota: El catálogo de marcas pertenece globalmente a la Empresa. El stock e inventario se segmentan por sucursal.
    detalle = models.CharField(max_length=100)
    margen = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Trazabilidad: ID original del sistema VFP anterior, para la migración de datos.
    codigo_anterior = models.CharField(
        max_length=50, null=True, blank=True,
        verbose_name="Código Sistema Anterior",
        help_text="ID histórico del sistema VFP para trazabilidad de migración",
        db_index=True
    )

    class Meta:
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"

    def save(self, *args, **kwargs):
        if self.detalle:
            self.detalle = self.detalle.upper().strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.detalle

class Rubro(AuditModel):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    # Nota: El catálogo de rubros pertenece globalmente a la Empresa. El stock e inventario se segmentan por sucursal.
    detalle = models.CharField(max_length=100)
    margen = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    descuento_maximo = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Descuento Máximo Autorizado (%)")
    # Trazabilidad: ID original del sistema VFP anterior, para la migración de datos.
    codigo_anterior = models.CharField(
        max_length=50, null=True, blank=True,
        verbose_name="Código Sistema Anterior",
        help_text="ID histórico del sistema VFP para trazabilidad de migración",
        db_index=True
    )

    # =========================================================================
    # CONFIGURACIÓN CONTABLE POR ACTIVIDAD/RUBRO (Para escenarios multi-actividad)
    # =========================================================================
    # Si un producto de este rubro se vende, se imputará a esta cuenta contable de ventas.
    # Si está vacía (Null), el sistema utilizará la cuenta de ventas general por defecto.
    cta_ventas = models.ForeignKey(
        'contable.Cuenta',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rubros_ventas',
        verbose_name="Cuenta de Ventas"
    )
    # Si un producto de este rubro se compra en un comprobante discriminado, se imputará a esta cuenta de compras.
    # Si está vacía (Null), se recurre a la cuenta de compras general por defecto.
    cta_compras = models.ForeignKey(
        'contable.Cuenta',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rubros_compras',
        verbose_name="Cuenta de Compras"
    )

    class Meta:
        verbose_name = "Rubro"
        verbose_name_plural = "Rubros"

    def save(self, *args, **kwargs):
        if self.detalle:
            self.detalle = self.detalle.upper().strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.detalle

class Familia(AuditModel):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    # Nota: El catálogo de familias pertenece globalmente a la Empresa. El stock e inventario se segmentan por sucursal.
    detalle = models.CharField(max_length=100)
    margen = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rubro = models.ForeignKey(Rubro, on_delete=models.SET_NULL, null=True, blank=True, related_name="familias")
    # Trazabilidad: ID original del sistema VFP anterior, para la migración de datos.
    codigo_anterior = models.CharField(
        max_length=50, null=True, blank=True,
        verbose_name="Código Sistema Anterior",
        help_text="ID histórico del sistema VFP para trazabilidad de migración",
        db_index=True
    )

    class Meta:
        verbose_name = "Familia"
        verbose_name_plural = "Familias"

    def save(self, *args, **kwargs):
        if self.detalle:
            self.detalle = self.detalle.upper().strip()
        super().save(*args, **kwargs)

class Subfamilia(AuditModel):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    # Nota: El catálogo de subfamilias pertenece globalmente a la Empresa y se desprende de una Familia.
    familia = models.ForeignKey(Familia, on_delete=models.CASCADE, related_name="subfamilias", verbose_name="Familia")
    detalle = models.CharField(max_length=100, verbose_name="Detalle de Subfamilia")
    margen = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Margen Sugerido (%)")
    # Trazabilidad: ID original del sistema VFP anterior, para la migración de datos.
    codigo_anterior = models.CharField(
        max_length=50, null=True, blank=True,
        verbose_name="Código Sistema Anterior",
        help_text="ID histórico del sistema VFP para trazabilidad de migración",
        db_index=True
    )

    class Meta:
        db_table = "productos_subfamilia"
        verbose_name = "Subfamilia"
        verbose_name_plural = "Subfamilias"
        ordering = ['familia__detalle', 'detalle']

    def save(self, *args, **kwargs):
        if self.detalle:
            self.detalle = self.detalle.upper().strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.familia.detalle} - {self.detalle}" if self.familia else self.detalle

class Producto(AuditModel):
    MONEDA_CHOICES = [
        ('PES', 'PESO'),
        ('DOL', 'DOLAR'),
        ('60', 'EURO')
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    activo = models.BooleanField(default=True, verbose_name="Activo", db_index=True)
    
    # Campos para Carga
    cod_prov = models.CharField(max_length=50, null=True, blank=True, verbose_name="Cód. Prov", db_index=True)
    cod_fab = models.CharField(max_length=50, null=True, blank=True, verbose_name="Cód. Fábrica", db_index=True)
    detalle = models.CharField(max_length=255, verbose_name="Detalle del Producto", db_index=True)
    proveedor = models.ForeignKey(ClienteProveedor, on_delete=models.SET_NULL, null=True, blank=True, related_name='productos_provistos')
    minimo = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ptopedir = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    creden = models.BooleanField(default=False)
    moneda = models.CharField(max_length=3, choices=MONEDA_CHOICES, default='PES')
    alic_iva = models.DecimalField(max_digits=5, decimal_places=2, choices=ALICUOTAS_IVA_CHOICES, default=Decimal('21.00'), verbose_name="Alícuota IVA")
    marca = models.ForeignKey(Marca, on_delete=models.SET_NULL, null=True, blank=True)
    rubro = models.ForeignKey(Rubro, on_delete=models.SET_NULL, null=True, blank=True)
    familia = models.ForeignKey(Familia, on_delete=models.SET_NULL, null=True, blank=True)
    subfamilia = models.ForeignKey(Subfamilia, on_delete=models.SET_NULL, null=True, blank=True, related_name="productos", verbose_name="Subfamilia")
    subprod = models.BooleanField(default=False)
    activo = models.BooleanField(default=True, db_index=True, verbose_name="Activo")

    # --- Distribución (Plan 074 §5.F) ---
    # `peso_unitario_kg` es la columna "Kgs" del Consolidado de Artículos, con el que el
    # depósito controla la carga del vehículo. Sin este dato el reporte no existe. Se
    # expresa SIEMPRE en la unidad de venta declarada abajo: si se vende por bulto, es el
    # peso del bulto.
    UNIDAD_VENTA_CHOICES = [
        ('UNIDAD', 'Unidad'),
        ('BULTO', 'Bulto / Cajón'),
        ('KG', 'Kilogramo'),
    ]
    peso_unitario_kg = models.DecimalField(
        max_digits=10, decimal_places=3, default=0, verbose_name="Peso por Unidad de Venta (kg)")
    # `blank=True` porque el campo SÓLO se dibuja en el modal cuando la empresa es DISTRIBUCION
    # (lo inyecta el hook `ui_producto_modal_campos`). Sin esto el form lo exigía igual en
    # ARMERIA, ESTUDIO o AGRICOLA, donde no está en pantalla: el alta de producto fallaba con
    # "Este campo es obligatorio" y el usuario no tenía dónde verlo. El default cubre el valor.
    unidad_venta = models.CharField(
        max_length=30, default='UNIDAD', blank=True,
        verbose_name="Unidad de Venta")
    unidades_por_bulto = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Unidades por Bulto",
        help_text="Cuántas unidades trae un bulto. El vendedor pide '3 cajones', no '36 unidades'.")

    # Código del producto en el sistema anterior. Vendedores y facturadores ya están
    # familiarizados con él y figura en la lista de precios impresa que llevan a la calle,
    # así que se imprime junto al ID del ERP y la búsqueda rápida resuelve por cualquiera
    # de los dos. Mismo patrón que `ClienteProveedor.codigo_anterior`.
    codigo_anterior = models.CharField(
        max_length=50, null=True, blank=True, db_index=True,
        verbose_name="Código Sistema Anterior",
        help_text="Código histórico del sistema anterior, utilizado para la migración.")

    # Campos que NO van para Carga (Se relacionarán/completarán luego)
    # `stock` y `stkcons` se eliminaron en el Plan 053: eran los campos que actualizaba el ERP en
    # VFP, donde el stock se llevaba sobre el producto. Hoy se lleva por sucursal en
    # `StockSucursal` y se CALCULA. El total consolidado está en la property `stock_global`.
    compra_id = models.IntegerField(null=True, blank=True)
    cto_adq = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    fec_adq = models.DateField(null=True, blank=True)
    cto_rep = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    fec_act = models.DateField(null=True, blank=True)
    margen = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Margen (%)")
    precio_neto = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    precio_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    cotiz_cpra = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    observaciones = models.TextField(null=True, blank=True, verbose_name="Observaciones / Notas")

    @property
    def alic_iva_porc(self):
        """Devuelve el porcentaje de IVA normalizado (ej. Decimal('21.00'), Decimal('10.50'), Decimal('0.00'))."""
        val = self.alic_iva
        if val is None:
            return Decimal('21.00')
        try:
            val = Decimal(str(val))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal('21.00')
        codigo_a_porc = {
            Decimal('3'): Decimal('0.00'),
            Decimal('4'): Decimal('10.50'),
            Decimal('5'): Decimal('21.00'),
            Decimal('6'): Decimal('27.00'),
            Decimal('8'): Decimal('5.00'),
            Decimal('9'): Decimal('2.50'),
        }
        if val in codigo_a_porc:
            return codigo_a_porc[val]
        if Decimal('0.00') < val < Decimal('1.00'):
            return (val * Decimal('100.00')).quantize(Decimal('0.01'))
        return val.quantize(Decimal('0.01'))

    @property
    def id_arca_iva(self):
        return ALICUOTAS_ARCA_MAP.get(self.alic_iva_porc, 5)

    def get_unidad_venta_display(self):
        """Retorna la representación legible de la unidad de venta o el calibre."""
        dict_choices = dict(self.UNIDAD_VENTA_CHOICES)
        return dict_choices.get(self.unidad_venta, self.unidad_venta or '')

    def clean(self):
        super().clean()
        self.alic_iva = self.alic_iva_porc

    def save(self, *args, **kwargs):
        if self.detalle:
            self.detalle = self.detalle.upper().strip()
        if self.cod_prov:
            self.cod_prov = self.cod_prov.upper().strip()
        if self.cod_fab:
            self.cod_fab = self.cod_fab.upper().strip()
        if self.codigo_anterior:
            self.codigo_anterior = self.codigo_anterior.upper().strip()
        self.alic_iva = self.alic_iva_porc
        super().save(*args, **kwargs)

    @property
    def stock_global(self):
        # Si el stock total vino precalculado con Subquery en la búsqueda/listado, lo retornamos directo en memoria
        if hasattr(self, 'stock_total_calc') and self.stock_total_calc is not None:
            return self.stock_total_calc
        # Suma de stock de todas las sucursales (fallback)
        return self.existencias.aggregate(total=Sum('cantidad'))['total'] or 0

    @property
    def margen_aplicable(self):
        """
        Retorna el margen de ganancia configurado para el producto.
        """
        return self.margen or 0

    @property
    def precio_venta_sugerido(self):
        """
        Calcula el precio de venta sugerido (IVA incluido) basado en el costo de adquisición
        y el margen aplicable.
        """
        costo = float(self.cto_adq or 0)
        margen = float(self.margen_aplicable or 0)
        alic_iva = float(self.alic_iva or 0)
        
        # Precio Neto = Costo * (1 + Margen/100)
        neto = costo * (1 + margen / 100)
        # Precio Final = Neto * (1 + IVA/100)
        final = neto * (1 + alic_iva / 100)
        
        return round(final, 2)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        indexes = [
            models.Index(fields=['empresa', 'detalle']),
            models.Index(fields=['empresa', 'cod_prov']),
            models.Index(fields=['empresa', 'cod_fab']),
            # Búsqueda rápida por el código del sistema anterior, que es el que el
            # vendedor tiene en la lista de precios impresa (Plan 074).
            models.Index(fields=['empresa', 'codigo_anterior']),
        ]

    def __str__(self):
        return self.detalle

class StockSucursal(AuditModel):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="existencias")
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE, related_name="stock_productos")

    # Existencia al momento de instalar el sistema en el cliente, por sucursal (Plan 053). Es el
    # punto de partida del stock: se carga en la migración desde el sistema anterior y los
    # circuitos operativos NO lo tocan. Sin él, `cantidad` era un contador sin origen y un
    # movimiento perdido dejaba el stock mal para siempre, sin forma de reconstruirlo.
    stock_inicial = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                        verbose_name="Stock Inicial")

    # Stock disponible. Es un valor DERIVADO y materializado (se lee en toda la operatoria, por eso
    # se guarda): lo calcula `productos.services.stock_service.recalcular_stock()` como
    #     stock_inicial + compras + recepciones − ventas − remitos internos
    # No se ajusta por delta. Si algo lo deja mal, se corrige volviendo a recalcular.
    cantidad = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                   verbose_name="Stock Disponible (calculado)")

    # Cantidad tomada en PEDIDOS todavía no facturados (Plan 074 §5.F). Es un valor DERIVADO y
    # materializado, exactamente igual que `cantidad`: lo recalcula
    # `productos.services.stock_service.recalcular_comprometido()`, nunca se ajusta por delta.
    #
    # Existe por la ventana entre que el vendedor toma el pedido y la administración lo factura
    # —en una distribuidora, la noche entera—. Durante esa ventana dos vendedores pueden
    # comprometer el mismo stock sin verse. El disponible real es `cantidad − comprometido`.
    comprometido = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                       verbose_name="Comprometido en Pedidos (calculado)")

    @property
    def disponible(self):
        """Lo que realmente se puede prometer: descuenta lo ya tomado en pedidos."""
        return (self.cantidad or 0) - (self.comprometido or 0)

    class Meta:
        unique_together = ('producto', 'sucursal')
        verbose_name = "Stock por Sucursal"
        verbose_name_plural = "Stocks por Sucursal"

class Subproducto(AuditModel):
    MONEDA_CHOICES = [('PES', 'PESO'), ('DOL', 'DOLAR'), ('EUR', 'EURO')]
    ESTADO_CHOICES = [('NUEVO', 'Nuevo'), ('USADO', 'Usado')]
    PROPIEDAD_CHOICES = [('PROPIA', 'Propia'), ('CONSIGNADA', 'Consignada'), ('CUSTODIA', 'Custodia')]
    SITUACION_CHOICES = [('DEPOSITO', 'En Depósito'), ('VENDIDA', 'Vendida')]

    subpro = models.AutoField(primary_key=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name="subproductos", editable=False)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="subproductos")
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT, related_name="subproductos", verbose_name="Sucursal Actual")
    serie = models.CharField(max_length=30, verbose_name="Nro Serie / Identificador")
    cuim = models.CharField(max_length=30, null=True, blank=True, verbose_name="CUIM")

    # Datos de compra
    compra = models.ForeignKey('facturacion.Compra', on_delete=models.PROTECT, null=True, blank=True, related_name="subproductos", verbose_name="Compra")
    feccpra = models.DateField(verbose_name="Fecha de Compra")
    cto_adq = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Costo de Adquisición")
    cotizadq = models.DecimalField(max_digits=15, decimal_places=4, default=1, verbose_name="Cotización Compra")
    moneda = models.CharField(max_length=3, choices=MONEDA_CHOICES, default='PES')
    alic_iva = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name="Alícuota IVA")
    margen = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    # Datos de venta
    venta = models.ForeignKey('facturacion.Venta', on_delete=models.SET_NULL, null=True, blank=True, related_name="subproductos", db_column="id_vta", verbose_name="Venta")
    fecvta = models.DateField(null=True, blank=True, verbose_name="Fecha de Venta")
    precio_neto = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    precio_total = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Precio Total IVA Incluido")
    cotizvta = models.DecimalField(max_digits=15, decimal_places=4, default=1, verbose_name="Cotización Venta")
    fecent = models.DateField(null=True, blank=True, verbose_name="Fecha de Entrega")

    # Estado
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='NUEVO', db_index=True)
    propiedad = models.CharField(max_length=15, choices=PROPIEDAD_CHOICES, default='PROPIA')
    situacion = models.CharField(max_length=15, choices=SITUACION_CHOICES, default='DEPOSITO')

    class Meta:
        verbose_name = "Subproducto"
        verbose_name_plural = "Subproductos"
        indexes = [
            models.Index(fields=['empresa', 'producto']),
            models.Index(fields=['sucursal', 'producto']),
            models.Index(fields=['sucursal', 'estado']),
            models.Index(fields=['empresa', 'serie', '-feccpra']),
            models.Index(fields=['empresa', 'cuim']),
        ]

    @property
    def es_moneda_dolar(self):
        return (self.moneda == 'DOL' or 
                (self.cotizadq and self.cotizadq > 1) or 
                (self.producto and (self.producto.moneda == 'DOL' or (self.producto.cotiz_cpra and self.producto.cotiz_cpra > 1))))

    @property
    def precio_pesos(self):
        base = float(self.producto.precio_neto or self.producto.pr_vta1 or 0)
        if self.es_moneda_dolar:
            cotiz = getattr(self.empresa, 'cotizacion_moneda', None)
            dc = float(cotiz.dolar_cobranza) if cotiz and cotiz.dolar_cobranza else 1.0
            return round(base * dc, 2)
        return round(base, 2)

    def calcular_precio_pesos(self, dolar_cobranza=1.0):
        base = float(self.producto.precio_neto or self.producto.pr_vta1 or 0)
        if self.es_moneda_dolar:
            dc = float(dolar_cobranza) if (dolar_cobranza and float(dolar_cobranza) > 0) else 1.0
            return round(base * dc, 2)
        return round(base, 2)

    @property
    def precio_usd_referencia(self):
        base = float(self.producto.precio_neto or self.producto.pr_vta1 or 0)
        return round(base, 2)

    def clean(self):
        super().clean()
        if self.cuim:
            self.cuim = str(self.cuim).strip().upper()
            import re
            if not re.fullmatch(r'^[A-Z0-9_\-]{1,30}$', self.cuim):
                from django.core.exceptions import ValidationError
                raise ValidationError({'cuim': 'El CUIM debe contener solo caracteres alfanuméricos o guiones (máx 30).'})

    def save(self, *args, **kwargs):
        self.clean()
        self.empresa = self.producto.empresa
        super().save(*args, **kwargs)

class MovimientoStock(AuditModel):
    TIPOS = [('ENTRADA', 'Entrada'), ('SALIDA', 'Salida'), ('TRANSFERENCIA', 'Transferencia')]
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=20, choices=TIPOS)
    cantidad = models.DecimalField(max_digits=15, decimal_places=2, default=0)  # Plan 028: soporta cantidades decimales
    observacion = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Movimiento de Stock"
        verbose_name_plural = "Movimientos de Stock"
        indexes = [
            models.Index(fields=['producto', 'sucursal', '-fecha_creacion']),
        ]

class TomaInventario(AuditModel):
    """
    Cabecera de Toma / Recuento Físico de Inventario por Sucursal.
    Módulo general aplicable a todas las empresas del ERP (Armería, Distribución, etc.).
    """
    ESTADOS = [
        ('BORRADOR', 'Borrador / En Conteo'),
        ('PENDIENTE', 'Pendiente de Autorización'),
        ('APLICADO', 'Aplicado al Stock'),
        ('RECHAZADO', 'Rechazado'),
        ('ANULADO', 'Anulado')
    ]
    ALCANCES = [
        ('GENERAL', 'Inventario General'),
        ('PARCIAL', 'Inventario Parcial'),
    ]
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE, related_name="inventarios", verbose_name="Sucursal")
    numero = models.IntegerField(default=1, verbose_name="N° de Inventario")
    fecha_toma = models.DateTimeField(verbose_name="Fecha y Hora de la Toma")
    tipo_alcance = models.CharField(max_length=15, choices=ALCANCES, default='PARCIAL', verbose_name="Alcance")
    filtros_aplicados = models.TextField(null=True, blank=True, verbose_name="Filtros aplicados")
    observaciones = models.TextField(null=True, blank=True, verbose_name="Observaciones")
    estado = models.CharField(max_length=15, choices=ESTADOS, default='BORRADOR', db_index=True, verbose_name="Estado")
    terminal = models.CharField(max_length=50, null=True, blank=True, verbose_name="Terminal / Estación")
    
    # Auditoría de autorización
    usuario_autorizo = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="inventarios_autorizados", verbose_name="Usuario que autorizó")
    fecha_autorizo = models.DateTimeField(null=True, blank=True, verbose_name="Fecha/Hora de Autorización")
    motivo_rechazo = models.TextField(null=True, blank=True, verbose_name="Motivo de Rechazo / Devolución")
    
    class Meta:
        verbose_name = "Toma de Inventario"
        verbose_name_plural = "Tomas de Inventario"
        ordering = ['-fecha_toma', 'sucursal']
        indexes = [
            models.Index(fields=['empresa', 'sucursal', '-fecha_toma']),
            models.Index(fields=['empresa', 'estado']),
        ]

    def __str__(self):
        return f"Inventario N° {self.numero} - {self.sucursal.nombre} ({self.fecha_toma.strftime('%d/%m/%Y') if self.fecha_toma else 'Sin fecha'})"

class TomaInventarioItem(models.Model):
    """
    Detalle de ítems contados físicamente en una toma de inventario.
    """
    inventario = models.ForeignKey(TomaInventario, on_delete=models.CASCADE, related_name="items", verbose_name="Toma de Inventario")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="conteos_inventario", verbose_name="Producto")
    stock_teorico = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Stock Teórico al momento")
    cantidad_contada = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Cantidad Contada (Física)")
    diferencia = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Diferencia (Contada - Teórico)")
    
    # Auditoría y modificaciones
    modificado_por_autorizador = models.BooleanField(default=False, verbose_name="Modificado por Autorizador")
    cantidad_original_operador = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Cantidad Original Operador")
    observaciones = models.CharField(max_length=255, null=True, blank=True, verbose_name="Observaciones")
    
    # Metadatos del conteo
    usuario_conteo = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuario que contó")
    fecha_hora = models.DateTimeField(null=True, blank=True, verbose_name="Fecha/Hora de Conteo")
    terminal = models.CharField(max_length=50, null=True, blank=True, verbose_name="Terminal / Estación")

    class Meta:
        verbose_name = "Ítem de Inventario"
        verbose_name_plural = "Ítems de Inventario"
        unique_together = ('inventario', 'producto')
        indexes = [
            models.Index(fields=['inventario', 'producto']),
        ]

    def save(self, *args, **kwargs):
        # Calcular diferencia automáticamente
        self.diferencia = (self.cantidad_contada or 0) - (self.stock_teorico or 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.producto.detalle} - Contado: {self.cantidad_contada}"


