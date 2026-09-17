from django.db import models
from django.conf import settings
from core.models import AuditModel
from empresas.models import Ejercicio

class TipoComprobante(models.Model):
    id = models.AutoField(primary_key=True)
    codigo = models.CharField(max_length=3, verbose_name="Código", unique=True)
    detalle = models.CharField(max_length=100, verbose_name="Detalle")
    signo = models.SmallIntegerField(default=1, verbose_name="Signo Contable")
    estado = models.BooleanField(default=True, verbose_name="Estado")

    class Meta:
        verbose_name = "Tipo de Comprobante"
        verbose_name_plural = "Tipos de Comprobantes"
        ordering = ['codigo']

    def __str__(self):
        return f"[{self.codigo}] {self.detalle}"

class Jurisdiccion(models.Model):
    codigo = models.IntegerField(unique=True, verbose_name="Código Jurisdicción")
    nombre = models.CharField(max_length=100, verbose_name="Nombre Jurisdicción")

    class Meta:
        verbose_name = "Jurisdicción"
        verbose_name_plural = "Jurisdicciones"

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

class ClienteProveedor(AuditModel):
    TIPOS = [(1, 'Cliente'), (2, 'Proveedor')]
    CLASIFICACION_CLI = [('MINORISTA', 'Minorista'), ('MAYORISTA', 'Mayorista')]
    CLASIFICACION_PRO = [
        ('BIENES DE CAMBIO', 'Bienes de Cambio e Insumos'),
        ('GASTOS', 'Gastos'),
        ('LOCACIONES', 'Locaciones'),
        ('SERVICIOS', 'Servicios'),
        ('BIENES DE USO', 'Bienes de Uso'),
        ('OTROS', 'Otros')
    ]
    IIBB_TIPOS = [('LOCAL', 'Contribuyente Local'), ('CONVENIO', 'Convenio Multilateral')]
    DOC_TIPOS = [
        ('80', '80 - CUIT'),
        ('86', '86 - CUIL'),
        ('96', '96 - DNI'),
        ('99', '99 - SIN IDENTIFICAR')
    ]
    CONDICION_IVA_CHOICES = [
        ('RESPONSABLE INSCRIPTO', 'Responsable Inscripto'),
        ('MONOTRIBUTO', 'Monotributo'),
        ('EXENTO', 'Exento'),
        ('CONSUMIDOR FINAL', 'Consumidor Final'),
    ]

    # Identificación
    codigo_id = models.AutoField(primary_key=True) # El ID se llamará codigo_id por pedido del usuario
    razon_social = models.CharField(max_length=200, verbose_name="Razón Social", db_index=True)
    tipo_documento = models.CharField(max_length=5, choices=DOC_TIPOS, default="80", verbose_name="Tipo Doc (ARCA)")
    cuit = models.CharField(max_length=11, verbose_name="CUIT/DNI/Cero", blank=True, null=True, db_index=True)
    fecha_nacimiento = models.DateField(null=True, blank=True, verbose_name="Fecha de Nacimiento")
    tipo_entidad = models.IntegerField(choices=TIPOS, default=1, verbose_name="Tipo (1:Cli, 2:Pro)")
    
    # Ubicación
    domicilio = models.CharField(max_length=255, null=True, blank=True)
    codigo_postal = models.CharField(max_length=20, null=True, blank=True, verbose_name="C. Postal")
    localidad = models.CharField(max_length=100, null=True, blank=True)
    jurisdiccion = models.ForeignKey(Jurisdiccion, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Provincia/Jurisdicción")
    
    # Contacto
    contacto = models.CharField(max_length=150, null=True, blank=True)
    telefono = models.CharField(max_length=100, null=True, blank=True)
    correo = models.EmailField(null=True, blank=True, help_text="Para envío automático de facturas")
    
    # Fiscal / Contable
    condicion_iva = models.CharField(max_length=50, choices=CONDICION_IVA_CHOICES, default="CONSUMIDOR FINAL", verbose_name="Cond. IVA")
    tipo_iibb = models.CharField(max_length=20, choices=IIBB_TIPOS, default='LOCAL', verbose_name="Ingresos Brutos")
    saldo_inicial = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    saldo = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    limite = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Límite")
    
    # Gestión
    objetivo_mensual = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Objetivo Venta")
    clasificacion = models.CharField(max_length=50, null=True, blank=True) # Se definirá por Choice en Form según tipo_entidad
    observaciones = models.TextField(null=True, blank=True, verbose_name="Observaciones Particulares")
    usa_orden_compra = models.BooleanField(default=False, verbose_name="Exige Orden de Compra")
    
    # Contabilidad y Multi-empresa
    cta_pat = models.IntegerField(default=0, verbose_name="Cta. Patrimonial", help_text="Código de Cuenta Patrimonial")
    cta_res = models.IntegerField(default=0, verbose_name="Cta. Resultado", help_text="Código de Cuenta de Resultado")
    empresa = models.ForeignKey('empresas.Empresa', on_delete=models.CASCADE, null=True, blank=True, verbose_name="Empresa")
    codigo_anterior = models.CharField(
        max_length=50, 
        null=True, 
        blank=True, 
        verbose_name="Código Sistema Anterior", 
        help_text="ID histórico del sistema anterior utilizado para la migración de datos",
        db_index=True
    )
    
    class Meta:
        verbose_name = "Cliente/Proveedor"
        verbose_name_plural = "Clientes y Proveedores"
        indexes = [
            models.Index(fields=['empresa', 'razon_social']),
            models.Index(fields=['empresa', 'tipo_entidad']),
        ]

    def __str__(self):
        return f"[{self.codigo_id}] {self.razon_social}"

    @property
    def domicilio_completo(self):
        """
        Retorna la concatenación limpia de domicilio + CP + localidad + provincia.
        Ejemplo: 'AV SAN MARTIN 1234 - CP: 1405 - CABALLITO, CAPITAL FEDERAL'
        """
        partes = []
        if self.domicilio and self.domicilio.strip():
            partes.append(self.domicilio.strip())
        if self.codigo_postal and self.codigo_postal.strip():
            partes.append(f"CP: {self.codigo_postal.strip()}")
        loc_prov = []
        if self.localidad and self.localidad.strip():
            loc_prov.append(self.localidad.strip())
        if self.jurisdiccion and self.jurisdiccion.nombre and self.jurisdiccion.nombre.strip():
            loc_prov.append(self.jurisdiccion.nombre.strip())
        if loc_prov:
            partes.append(", ".join(loc_prov))
        return " - ".join(partes) if partes else ""

    def save(self, *args, **kwargs):
        # 1. Convertir campos de texto a mayúsculas (excepto emails o códigos específicos)
        exclude_fields = ['correo', 'tipo_documento', 'tipo_iibb']
        for field in self._meta.fields:
            if isinstance(field, (models.CharField, models.TextField)) and field.name not in exclude_fields:
                value = getattr(self, field.name)
                if value and isinstance(value, str):
                    setattr(self, field.name, value.upper())

        # 2. Lógica para Tipo 99 (Sin Identificar) - Aplica solo a Clientes si no es explícitamente Proveedor
        if self.tipo_documento == '99' and self.tipo_entidad != 2:
            self.tipo_entidad = 1  # Forzamos rol Cliente
            self.clasificacion = 'MINORISTA'
            # Si no hay CUIT/DNI, ARCA suele pedir '0' para el tipo 99
            if not self.cuit:
                self.cuit = '0'
        
        super().save(*args, **kwargs)



class TemplateFacturaProveedor(models.Model):
    """
    Guarda las coordenadas relativas de los recortes de cada campo
    para automatizar la lectura OCR en futuras facturas del mismo proveedor.
    """
    proveedor = models.ForeignKey(ClienteProveedor, on_delete=models.CASCADE, related_name="templates_facturas")
    nombre_template = models.CharField(max_length=100, default="Predeterminado")
    coordenadas = models.JSONField(help_text="Diccionario con campos y sus coordenadas {x, y, width, height, image_width, image_height}")
    creado = models.DateTimeField(auto_now_add=True)
    modificado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plantilla de Factura (Proveedor)"
        verbose_name_plural = "Plantillas de Facturas"

    def __str__(self):
        return f"Plantilla {self.nombre_template} - {self.proveedor.razon_social}"

def compras_pdf_path(instance, filename):
    return f'compras_archivosWEBP/{filename}'

class Compra(models.Model):
    MONEDAS = [('PES', 'PESO'), ('DOL', 'DOLAR'), ('60', 'EURO')]

    archivo_pdf = models.FileField(upload_to=compras_pdf_path, null=True, blank=True, verbose_name="Comprobante Original")

    compras_id = models.AutoField(primary_key=True)
    asiento_id = models.IntegerField(null=True, blank=True)
    fecha = models.DateField(db_index=True)
    fec_cpra = models.DateTimeField(auto_now_add=True, null=True, blank=True) # Fecha real de carga del comprobante en el sistema
    periodo = models.CharField(max_length=6, null=True, blank=True, db_index=True, verbose_name="Período YYYYMM")
    tipo = models.ForeignKey(TipoComprobante, on_delete=models.PROTECT, null=True)
    punto = models.IntegerField()
    numero = models.BigIntegerField(db_index=True)
    proveedor = models.ForeignKey(ClienteProveedor, on_delete=models.PROTECT)
    moneda = models.CharField(max_length=3, choices=MONEDAS, default='PES')
    cotizacion = models.DecimalField(max_digits=15, decimal_places=4, default=1.0)
    # 1=Real, 2=Presupuestado, 3=Ajuste (factura de la empresa pagada por el socio: va a Libro IVA
    # y DDJJ pero se excluye del análisis de gastos), 4=Auditoría. Tabla completa en `.cursorrules`.
    condic = models.IntegerField(default=1, verbose_name="Condición")
    # Gastos (compras sin detalle de productos)
    descripcion = models.CharField(max_length=255, null=True, blank=True, verbose_name="Detalle del Gasto")
    cta_imputacion = models.IntegerField(null=True, blank=True, verbose_name="Cta. Imputación (Gasto)")

    # Bloque 2
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Subtotal Neto")  # Σ líneas, antes del descuento global
    descuento = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Descuento Global")
    neto = models.DecimalField(max_digits=15, decimal_places=2, default=0)  # Neto Gravado = subtotal − descuento (base del IVA)
    iva = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    no_gravado = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    exento = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    p_iva = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    p_gcia = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    p_iibb = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    p_recbc = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    p_sircreb = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    p_mun = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    otros = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    pagado = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    saldo = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    modificado = models.DateTimeField(auto_now=True)
    id_fac_rem = models.IntegerField(null=True, blank=True)
    # Circuito OC (Plan 028): si True, el stock NO lo mueve la factura (lo mueve la
    # Recepción vinculada o la que la propia factura genera). Default False = flujo clásico intacto.
    gestion_stock_por_recepcion = models.BooleanField(default=False)
    sucursal = models.ForeignKey('empresas.Sucursal', on_delete=models.PROTECT)
    empresa = models.ForeignKey('empresas.Empresa', on_delete=models.PROTECT)
    ejercicio = models.ForeignKey(Ejercicio, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Ejercicio Fiscal")

    class Meta:
        verbose_name = "Compra"
        verbose_name_plural = "Compras"
        indexes = [
            models.Index(fields=['empresa', 'numero']),
            models.Index(fields=['empresa', 'proveedor']),
            models.Index(fields=['empresa', 'fecha']),
        ]

    def desglose_alicuotas(self):
        """Desglose por alícuota aplicando el prorrateo del descuento global.
        Cada ítem aporta su neto de línea (sin IVA); el descuento global se reparte
        proporcionalmente entre los netos de cada alícuota y el IVA se recalcula sobre
        el neto descontado. Devuelve [{'alicuota', 'neto', 'iva', 'codiva'}].

        En GASTOS (sin ítems) el desglose se captura a mano y se persiste en
        `CompraAlicuota`: se devuelve tal cual fue cargado (el IVA es editable para
        cuadrar con el comprobante), sin prorrateo de descuento."""
        from decimal import Decimal
        if self.alicuotas.exists():
            return [
                {'alicuota': a.porcentaje, 'neto': a.neto, 'iva': a.iva, 'codiva': a.codigo}
                for a in self.alicuotas.all()
            ]
        por_alic = {}
        subtotal = Decimal("0.00")
        for item in self.items.all():
            alic = Decimal(str(item.iva_alicuota))
            neto = Decimal(str(item.total))
            por_alic[alic] = por_alic.get(alic, Decimal("0.00")) + neto
            subtotal += neto
        desc = Decimal(str(self.descuento or 0))
        factor = (Decimal("1") - desc / subtotal) if subtotal else Decimal("1")
        salida = []
        for alic, neto_sub in por_alic.items():
            neto_desc = (neto_sub * factor).quantize(Decimal("0.01"))
            iva = (neto_desc * alic / Decimal("100")).quantize(Decimal("0.01"))
            salida.append({'alicuota': alic, 'neto': neto_desc, 'iva': iva})
        return salida

    def recalcular_totales(self):
        from decimal import Decimal
        # Subtotal = suma de netos de línea (antes del descuento global).
        subtotal = sum((Decimal(str(i.total)) for i in self.items.all()), Decimal("0.00"))
        self.subtotal = subtotal
        # IVA prorrateado sobre el neto descontado, por alícuota.
        self.iva = sum((d['iva'] for d in self.desglose_alicuotas()), Decimal("0.00"))
        # Neto Gravado = subtotal − descuento global (base del IVA).
        self.neto = (subtotal - Decimal(str(self.descuento or 0))).quantize(Decimal("0.01"))

        # El total es la suma de los calculados + otros conceptos fijos en cabecera
        total_calculado = (
            self.neto + self.iva +
            Decimal(str(self.no_gravado or 0)) + Decimal(str(self.exento or 0)) +
            Decimal(str(self.p_iva or 0)) + Decimal(str(self.p_gcia or 0)) +
            Decimal(str(self.p_iibb or 0)) + Decimal(str(self.p_recbc or 0)) +
            Decimal(str(self.p_sircreb or 0)) + Decimal(str(self.p_mun or 0)) +
            Decimal(str(self.otros or 0))
        )
        self.total = total_calculado
        self.save(update_fields=['neto', 'iva', 'total', 'subtotal'])

        # El saldo NO se calcula acá: se deriva de las aplicaciones de Órdenes de Pago
        # (Plan 035 §1.3). Antes esta línea hacía `saldo = total - pagado` con `pagado`
        # siempre en 0, así que editar una compra ya pagada la dejaba figurando impaga por
        # su total. El servicio recalcula ambos campos desde el detalle.
        from contable.services.saldos import recalcular_saldo_compra
        recalcular_saldo_compra(self.pk)
        self.refresh_from_db(fields=['pagado', 'saldo'])

class CompraItem(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=15, decimal_places=2, default=1)
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    iva_alicuota = models.DecimalField(max_digits=5, decimal_places=2, default=21.0)
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Ítem de Compra"
        verbose_name_plural = "Ítems de Compra"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.pk:
            self._original_cantidad = self.cantidad
        else:
            self._original_cantidad = 0


class CompraAlicuota(models.Model):
    """Desglose de IVA por alícuota de una compra de GASTO (sin ítems).
    Se captura a mano en la carga (código ARCA + neto + alícuota → IVA calculado,
    editable para cuadrar con la factura por redondeo). Persistido para que el
    Libro IVA Digital refleje el detalle real, no una alícuota inferida.
    En Bienes de Cambio el desglose sale de los ítems, no de esta tabla."""
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name='alicuotas')
    codigo = models.CharField(max_length=4, verbose_name="Cód. Alícuota ARCA")
    porcentaje = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Alícuota %")
    neto = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Neto Gravado")
    iva = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="IVA (computable)")

    class Meta:
        verbose_name = "Alícuota de Compra"
        verbose_name_plural = "Alícuotas de Compra"

    def __str__(self):
        return f"{self.codigo} {self.porcentaje}% · neto {self.neto} · iva {self.iva}"


class CompraRetPerc(models.Model):
    """Detalle capturado de retenciones/percepciones SUFRIDAS en una compra.
    Reemplaza a los campos p_* como fuente del asiento + RetPercSufrida.
    - IIBB con Convenio Multilateral: una fila por jurisdicción (importe repartido).
    - 'Otros Imp.' desglosado por impuesto (SIRCREB, TEM, SUSS, MUN, OTRO...).
    En compras las sufridas son percepciones ('P'); las retenciones las practicamos
    nosotros (van por Órdenes de Pago, no acá)."""
    IMPUESTOS = [
        ('IVA', 'IVA'), ('GAN', 'Ganancias'), ('IIBB', 'Ingresos Brutos'),
        ('TEM', 'Tasa Específica / TEM'), ('SIRCREB', 'SIRCREB'),
        ('SUSS', 'SUSS'), ('MUN', 'Municipal'), ('OTRO', 'Otro'),
    ]
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name='retpercs')
    impuesto = models.CharField(max_length=10, choices=IMPUESTOS)
    tipo = models.CharField(max_length=1, default='P')  # 'P' percepción / 'R' retención
    jurisdiccion = models.ForeignKey('facturacion.Jurisdiccion', on_delete=models.PROTECT,
                                     null=True, blank=True, verbose_name="Jurisdicción")
    importe = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Ret/Perc de Compra"
        verbose_name_plural = "Ret/Perc de Compra"

    def __str__(self):
        j = f" [{self.jurisdiccion.codigo}]" if self.jurisdiccion_id else ""
        return f"{self.impuesto}{j} · {self.importe}"


class Preventa(models.Model):
    ESTADOS = [
        (0, 'Borrador'),
        (1, 'Pendiente Autorización'),
        (2, 'Autorizada'),
        (3, 'Facturada'),
        (4, 'Anulada')
    ]
    
    preventa_id = models.AutoField(primary_key=True)
    fecha = models.DateField(auto_now_add=True, db_index=True)
    cliente = models.ForeignKey(ClienteProveedor, on_delete=models.PROTECT, related_name='preventas')
    cliente_razon_social = models.CharField(max_length=200, null=True, blank=True)
    cliente_cuit = models.CharField(max_length=20, null=True, blank=True)
    cliente_domicilio = models.CharField(max_length=255, null=True, blank=True)
    vendedor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='preventas')
    empresa = models.ForeignKey('empresas.Empresa', on_delete=models.PROTECT)
    sucursal = models.ForeignKey('empresas.Sucursal', on_delete=models.PROTECT)
    
    estado = models.IntegerField(choices=ESTADOS, default=0, db_index=True)
    es_consumidor_final = models.BooleanField(default=False, verbose_name="Facturar como Consumidor Final (Consumo Propio)")
    notas_sigimac = models.TextField(null=True, blank=True, verbose_name="Notas SIGIMAC (Uso Interno)")
    
    # Importes
    neto = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    descuento_global = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Suma de los descuentos de los ítems")
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    modificado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Preventa"
        verbose_name_plural = "Preventas"
        indexes = [
            models.Index(fields=['empresa', 'fecha']),
            models.Index(fields=['empresa', 'estado']),
        ]

    def __str__(self):
        return f"Preventa {self.preventa_id} - {self.cliente.razon_social}"

    def recalcular_totales(self):
        from decimal import Decimal
        neto_total = Decimal("0.00")
        descuento_total = Decimal("0.00")
        
        for item in self.items.all():
            neto_total += Decimal(str(item.total))  # El total del ítem ya tiene el descuento aplicado
            monto_original = Decimal(str(item.precio_unitario)) * Decimal(str(item.cantidad))
            descuento_total += monto_original - Decimal(str(item.total))
            
        self.neto = neto_total
        self.descuento_global = descuento_total
        self.total = neto_total
        self.save(update_fields=['neto', 'descuento_global', 'total'])


class PreventaItem(models.Model):
    preventa = models.ForeignKey(Preventa, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=15, decimal_places=2, default=1)
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    porcentaje_descuento = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Bimonetarismo
    moneda_origen = models.CharField(max_length=3, default='PES', verbose_name="Moneda Origen")
    cotizacion_aplicada = models.DecimalField(max_digits=15, decimal_places=4, default=1.0, verbose_name="Cotización")
    precio_origen = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Precio en Moneda Origen")
    
    # Campos específicos Armería
    credencial = models.CharField(max_length=50, null=True, blank=True, verbose_name="Credencial")
    dmp = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="DMP")

    class Meta:
        verbose_name = "Ítem de Preventa"
        verbose_name_plural = "Ítems de Preventa"

    def save(self, *args, **kwargs):
        from decimal import Decimal
        if self.total is None or self.total == Decimal('0.00'):
            precio = Decimal(str(self.precio_unitario))
            cant = Decimal(str(self.cantidad))
            desc = Decimal(str(self.porcentaje_descuento))
            subtotal = precio * cant
            self.total = round(subtotal * (Decimal('1') - (desc / Decimal('100'))), 2)
        super().save(*args, **kwargs)


class Venta(models.Model):
    MONEDAS = [('PES', 'PESO'), ('DOL', 'DOLAR'), ('60', 'EURO')]

    ventas_id = models.AutoField(primary_key=True)
    asiento_id = models.IntegerField(null=True, blank=True)
    fecha = models.DateField(db_index=True)
    fec_vta = models.DateTimeField(auto_now_add=True) # Fecha y hora de carga
    periodo = models.CharField(max_length=6, null=True, blank=True, db_index=True, verbose_name="Período YYYYMM") # AñoMes (YYYYMM)
    periodo_facturado = models.CharField(max_length=6, null=True, blank=True, help_text="Formato YYYYMM, para bloqueo de facturación por lote de honorarios")
    tipo = models.ForeignKey(TipoComprobante, on_delete=models.PROTECT, null=True)
    punto = models.IntegerField()
    numero = models.BigIntegerField(db_index=True)
    #Para cliente y proveedor se puede hacer un FK con limit_choices_to={'tipo_entidad': 1} o {'tipo_entidad': 2}
    #cliente = models.ForeignKey(ClienteProveedor, on_delete=models.PROTECT, limit_choices_to={'tipo_entidad':}
    #Y comentar el de abajo
    cliente = models.ForeignKey(ClienteProveedor, on_delete=models.PROTECT)
    cliente_razon_social = models.CharField(max_length=200, null=True, blank=True)
    cliente_cuit = models.CharField(max_length=20, null=True, blank=True)
    cliente_domicilio = models.CharField(max_length=255, null=True, blank=True)
    moneda = models.CharField(max_length=3, choices=MONEDAS, default='PES')
    cotizacion = models.DecimalField(max_digits=15, decimal_places=4, default=1.0)
    # 1=Real, 2=Presupuestado, 3=Ajuste (factura de la empresa pagada por el socio: va a Libro IVA
    # y DDJJ pero se excluye del análisis de gastos), 4=Auditoría. Tabla completa en `.cursorrules`.
    condic = models.IntegerField(default=1, verbose_name="Condición")

    # Importes
    neto = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    iva = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    no_gravado = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    exento = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    p_iva = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    p_gcia = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    p_iibb = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    p_recbc = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    p_sircreb = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    p_mun = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    otros = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Cobranza
    cobrado = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    saldo = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    efectivo = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tarjeta = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    transferencia = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    valores = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    dolares = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Dólares (Pesificados)")
    fec_cob = models.DateTimeField(null=True, blank=True)

    # Estado y Auditoría
    estado = models.IntegerField(default=0, db_index=True) # 0: Activa, 1: Anulada, 2: Pendiente Autorización, 3: Rechazada
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ventas_cargadas')
    vendedor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ventas_vendedor', null=True, blank=True)
    cajero = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ventas_cajero', null=True, blank=True)
    sucursal = models.ForeignKey('empresas.Sucursal', on_delete=models.PROTECT)
    empresa = models.ForeignKey('empresas.Empresa', on_delete=models.PROTECT)
    ejercicio = models.ForeignKey(Ejercicio, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Ejercicio Fiscal")
    
    # Datos ARCA (Futuro)
    cae = models.CharField(max_length=20, null=True, blank=True)
    vto_cae = models.DateField(null=True, blank=True)
    cod_qr = models.TextField(null=True, blank=True)

    # Trazabilidad
    id_fac_rem = models.IntegerField(null=True, blank=True) # ID de la factura (solo se carga en remitos)

    # --- Distribución (Plan 074 §5.F) ---
    # CONTADO o CUENTA CORRIENTE. Es el "Condición Venta" que la propia factura imprime.
    #
    # No se deriva de `saldo`/`cobrado` —que es la regla general del proyecto— porque en
    # distribución el comprobante se emite DE MADRUGADA y se cobra recién a la tarde en
    # la casa del cliente: en ese intervalo una venta de contado y una de cuenta corriente
    # tienen idéntico `saldo = total`, así que la condición no es derivable justo cuando
    # la hoja de ruta la necesita impresa. Se resuelve al facturar con la regla del saldo
    # disponible y queda congelada.
    #
    # `condic` NO se toca: son cosas distintas y sigue significando fiscal/no fiscal.
    CONDICION_VENTA_CHOICES = [
        ('CONTADO', 'Contado'),
        ('CTA_CTE', 'Cuenta Corriente'),
    ]
    condicion_venta = models.CharField(
        max_length=10, choices=CONDICION_VENTA_CHOICES, null=True, blank=True,
        verbose_name="Condición de Venta")

    # --- Nota de Crédito → comprobante que le dio origen (Plan 076 §D) ---
    # Sólo la usan los comprobantes con `tipo.signo = -1`. Es lo que permite que el saldo
    # REAL de la factura sea `total − cobrado − recibos − NC relacionadas`, y que la NC
    # quede en cero por haberse aplicado por completo a su origen.
    # Antes de este campo el vínculo no se persistía en ningún lado: la factura quedaba con
    # saldo completo y la NC con saldo negativo, y había que cruzarlas a mano.
    venta_origen = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='notas_credito', verbose_name="Comprobante acreditado")

    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        indexes = [
            models.Index(fields=['empresa', 'numero']),
            models.Index(fields=['empresa', 'cliente']),
            models.Index(fields=['empresa', 'fecha']),
        ]
        constraints = [
            # Plan 075. Segunda barrera del control de integridad: aunque la lógica de
            # aplicación falle, la base no acepta dos comprobantes con el mismo número
            # en la misma serie. Es la protección que `OrdenCompra`, `Recepcion`,
            # `RemitoInterno` y `Recibo` ya tenían y a `Venta` le faltaba: era el único
            # documento emitido del sistema sin ninguna.
            #
            # `tipo` es nullable y en PostgreSQL los NULL no colisionan entre sí, así que
            # los comprobantes sin tipo quedan fuera del control. Es una limitación
            # conocida: la solución de fondo es que `tipo` deje de ser opcional, y eso
            # excede este plan.
            models.UniqueConstraint(
                fields=['empresa', 'tipo', 'punto', 'numero'],
                name='uniq_venta_empresa_tipo_punto_numero',
            ),
        ]

    def __str__(self):
        return f"{self.tipo} {self.punto:05d}-{self.numero}"

    def save(self, *args, **kwargs):
        from decimal import Decimal
        if not kwargs.get('update_fields') or 'total' in kwargs.get('update_fields', []):
            self.total = (
                Decimal(str(self.neto or 0)) + Decimal(str(self.iva or 0)) +
                Decimal(str(self.no_gravado or 0)) + Decimal(str(self.exento or 0)) +
                Decimal(str(self.p_iva or 0)) + Decimal(str(self.p_gcia or 0)) +
                Decimal(str(self.p_iibb or 0)) + Decimal(str(self.p_recbc or 0)) +
                Decimal(str(self.p_sircreb or 0)) + Decimal(str(self.p_mun or 0)) +
                Decimal(str(self.otros or 0))
            )
        super().save(*args, **kwargs)

    def recalcular_totales(self):
        from decimal import Decimal
        neto_total = Decimal("0.00")
        iva_total = Decimal("0.00")
        
        for item in self.items.all():
            alicuota_factor = Decimal("1.00") + (Decimal(str(item.iva_alicuota)) / Decimal("100.00"))
            item_total = Decimal(str(item.total))
            neto_item = item_total / alicuota_factor
            neto_item = neto_item.quantize(Decimal("0.01"))
            iva_item = item_total - neto_item
            
            neto_total += neto_item
            iva_total += iva_item
            
        self.neto = neto_total
        self.iva = iva_total
        
        total_calculado = (
            self.neto + self.iva + 
            Decimal(str(self.no_gravado or 0)) + Decimal(str(self.exento or 0)) + 
            Decimal(str(self.p_iva or 0)) + Decimal(str(self.p_gcia or 0)) + 
            Decimal(str(self.p_iibb or 0)) + Decimal(str(self.p_recbc or 0)) + 
            Decimal(str(self.p_sircreb or 0)) + Decimal(str(self.p_mun or 0)) + 
            Decimal(str(self.otros or 0))
        )
        self.total = total_calculado
        self.save(update_fields=['neto', 'iva', 'total'])

    @property
    def total_costo_reposicion(self):
        """Calcula el costo de reposición acumulado de todos los ítems de la venta."""
        from decimal import Decimal
        return sum((item.subtotal_costo_reposicion for item in self.items.all()), Decimal('0.00'))

    @property
    def contribucion_marginal_total(self):
        """Calcula la contribución marginal total acumulada de los ítems de la venta."""
        from decimal import Decimal
        return sum((item.contribucion_marginal_total for item in self.items.all()), Decimal('0.00'))

    @property
    def margen_bruto_porcentaje(self):
        """Calcula el margen bruto en porcentaje sobre el total neto de la venta."""
        from decimal import Decimal
        if not self.neto or Decimal(str(self.neto)) == 0:
            return Decimal('0.00')
        cm_total = self.contribucion_marginal_total
        return (cm_total / Decimal(str(self.neto))) * Decimal('100.00')

    @property
    def domicilio_completo_cliente(self):
        """
        Retorna el domicilio completo del cliente asignado o el snapshot de la venta si no está disponible.
        """
        if self.cliente:
            dom = self.cliente.domicilio_completo
            if dom:
                return dom
        return self.cliente_domicilio or ""

class VentaItem(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT)
    concepto = models.CharField(max_length=255, null=True, blank=True, verbose_name="Concepto a facturar")
    cantidad = models.DecimalField(max_digits=15, decimal_places=2, default=1)
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    porcentaje_descuento = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    iva_alicuota = models.DecimalField(max_digits=5, decimal_places=2, default=21.0)
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Costo de reposición al momento de la venta (para análisis de rentabilidad / contribución marginal)
    cto_rep = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name="Costo de Reposición",
        help_text="Costo de reposición vigente del producto al momento de realizar la venta"
    )
    
    # Bimonetarismo
    moneda_origen = models.CharField(max_length=3, default='PES', verbose_name="Moneda Origen")
    cotizacion_aplicada = models.DecimalField(max_digits=15, decimal_places=4, default=1.0, verbose_name="Cotización")
    precio_origen = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Precio en Moneda Origen")
    
    # Campos específicos Armería (Municiones y Armas)
    credencial = models.CharField(max_length=50, null=True, blank=True, verbose_name="Credencial")
    serie = models.CharField(max_length=50, null=True, blank=True, verbose_name="Nro. Serie")
    cuim = models.CharField(max_length=50, null=True, blank=True, verbose_name="CUIM")
    subproducto = models.ForeignKey('productos.Subproducto', on_delete=models.SET_NULL, null=True, blank=True, related_name='ventas_items', verbose_name="Subproducto / Arma")
    dmp = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="DMP")

    class Meta:
        verbose_name = "Ítem de Venta"
        verbose_name_plural = "Ítems de Venta"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.pk:
            self._original_cantidad = self.cantidad
        else:
            self._original_cantidad = 0

    def save(self, *args, **kwargs):
        # Si cto_rep no fue especificado o es 0 y se tiene producto asignado, se carga el cto_rep vigente del producto
        if (self.cto_rep is None or self.cto_rep == 0) and self.producto_id:
            self.cto_rep = self.producto.cto_rep
        super().save(*args, **kwargs)

    @property
    def subtotal_costo_reposicion(self):
        """Calcula el costo total de reposición para el ítem (cantidad * cto_rep)."""
        from decimal import Decimal
        return Decimal(str(self.cantidad or 0)) * Decimal(str(self.cto_rep or 0))

    @property
    def contribucion_marginal_unitaria(self):
        """Calcula la contribución marginal por unidad (precio unitario neto con descuento - cto_rep)."""
        from decimal import Decimal
        precio_desc = Decimal(str(self.precio_unitario or 0)) * (Decimal('1') - (Decimal(str(self.porcentaje_descuento or 0)) / Decimal('100')))
        return precio_desc - Decimal(str(self.cto_rep or 0))

    @property
    def contribucion_marginal_total(self):
        """Calcula la contribución marginal total para la cantidad vendida."""
        from decimal import Decimal
        return self.contribucion_marginal_unitaria * Decimal(str(self.cantidad or 0))


class VentaAlicuotaIva(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='alicuotas_iva')
    id_iva = models.IntegerField(verbose_name="ID Alícuota ARCA")  # 3=0%, 4=10.5%, 5=21%, 6=27%, 8=5%, 9=2.5%
    alicuota = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Porcentaje (%)")
    base_imponible = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    importe_iva = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Alícuota IVA de Venta"
        verbose_name_plural = "Alícuotas IVA de Venta"

    def __str__(self):
        return f"Venta {self.venta_id} - IVA {self.alicuota}%"


class Movimiento(models.Model):
    """
    Modelo para la trazabilidad de movimientos de compra y venta.
    Diseñado para alimentar futuros informes y auditorías.
    """
    TIPO_MOV_CHOICES = [
        ('Compra', 'Compra'),
        ('Venta', 'Venta'),
        ('Remito', 'Remito'),
        ('R.Interno', 'R. Interno'),
        ('Ajuste', 'Ajuste'),
    ]

    movimiento_id = models.AutoField(primary_key=True)
    # Vinculaciones
    asiento_id = models.IntegerField(null=True, blank=True, verbose_name="ID Asiento (cble_asiento_enc)")
    compra = models.ForeignKey('Compra', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Compra Relacionada")
    venta = models.ForeignKey('Venta', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Venta Relacionada")
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT, verbose_name="Producto")
    
    # Datos del Movimiento
    fecha = models.DateField(verbose_name="Fecha", db_index=True)
    tipo = models.IntegerField(verbose_name="Tipo Factura") # Según Excel es entero (posible código AFIP)
    punto = models.IntegerField(verbose_name="Punto de Venta")
    numero = models.IntegerField(verbose_name="Número de Factura")
    cli_pro = models.ForeignKey('ClienteProveedor', on_delete=models.PROTECT, verbose_name="Cliente/Proveedor")
    tipo_mov = models.CharField(max_length=20, choices=TIPO_MOV_CHOICES, verbose_name="Tipo de Movimiento", db_index=True)
    
    # Valores y Cantidades
    entrada = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Entrada (Cantidad)")
    salida = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Salida (Cantidad)")
    saldo = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Saldo Cliente/Prov")
    precio = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Precio Unitario")
    neto = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Neto")
    stock = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Stock al momento")
    
    # Auditoría y Contexto
    modificado = models.DateTimeField(auto_now=True, verbose_name="Fecha de Modificación")
    ejercicio = models.ForeignKey(Ejercicio, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Ejercicio Fiscal")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Usuario")
    sucursal = models.ForeignKey('empresas.Sucursal', on_delete=models.PROTECT, verbose_name="Sucursal")
    empresa = models.ForeignKey('empresas.Empresa', on_delete=models.PROTECT, verbose_name="Empresa")

    class Meta:
        verbose_name = "Movimiento"
        verbose_name_plural = "Movimientos"
        db_table = "facturacion_movimiento" # Nombre especificado en el Excel
        indexes = [
            models.Index(fields=['empresa', 'producto', 'fecha']),
            models.Index(fields=['empresa', 'sucursal', 'producto']),
            models.Index(fields=['empresa', 'tipo_mov']),
        ]

    def __str__(self):
        return f"Mov {self.movimiento_id} - {self.tipo_mov} - {self.fecha}"


# ==============================================================================
# CIRCUITO DE ABASTECIMIENTO — Plan 028
# Orden de Compra → Informe de Recepción → cotejo en Factura (+ circuito interno)
# ==============================================================================

class OrdenCompra(AuditModel):
    """Orden de Compra: documento prenumerado por el sistema que inicia el circuito de
    abastecimiento (opcional según Empresa.usa_orden_compra).

    Numeración correlativa por (empresa, punto, ORDEN_COMPRA) vía
    core.services.numeracion.siguiente_numero; el número se asigna al CONFIRMAR
    (estado BORRADOR → CONFIRMADA). Baja = anulación lógica (conserva el número)."""

    MONEDAS = [('PES', 'PESO'), ('DOL', 'DOLAR'), ('60', 'EURO')]

    # Estado general del documento
    BORRADOR = 0
    CONFIRMADA = 1
    CERRADA = 2
    ANULADA = 3
    ESTADOS = [
        (BORRADOR, 'Borrador'),
        (CONFIRMADA, 'Confirmada'),
        (CERRADA, 'Cerrada'),
        (ANULADA, 'Anulada'),
    ]

    # Ejes de avance (recepción / facturación)
    PENDIENTE = 0
    PARCIAL = 1
    COMPLETA = 2
    CON_DIFERENCIA = 3
    ESTADOS_AVANCE = [
        (PENDIENTE, 'Pendiente'),
        (PARCIAL, 'Parcial'),
        (COMPLETA, 'Completa'),
        (CON_DIFERENCIA, 'Con Diferencia'),
    ]

    oc_id = models.AutoField(primary_key=True)
    empresa = models.ForeignKey('empresas.Empresa', on_delete=models.PROTECT, related_name='ordenes_compra')
    sucursal = models.ForeignKey('empresas.Sucursal', on_delete=models.PROTECT, related_name='ordenes_compra')
    punto = models.IntegerField(verbose_name="Punto")
    numero = models.BigIntegerField(null=True, blank=True, db_index=True, verbose_name="Número")  # se asigna al confirmar
    fecha = models.DateField(db_index=True)
    proveedor = models.ForeignKey(ClienteProveedor, on_delete=models.PROTECT, related_name='ordenes_compra')

    # Costos opcionales (optiongroup): si carga_costos=False, precio_unitario queda en 0 y lo completa la factura
    carga_costos = models.BooleanField(default=True, verbose_name="Carga Costos")

    # Condiciones comerciales (informativas)
    medio_pago = models.ForeignKey('tesoreria.MedioPago', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='ordenes_compra', verbose_name="Medio de Pago")
    condiciones_pago = models.TextField(null=True, blank=True, verbose_name="Condiciones de Pago",
                                        help_text="Combinaciones de medios de pago y plazos (informativo).")

    moneda = models.CharField(max_length=3, choices=MONEDAS, default='PES')
    cotizacion = models.DecimalField(max_digits=15, decimal_places=4, default=1.0)

    observaciones = models.TextField(null=True, blank=True)

    estado = models.IntegerField(choices=ESTADOS, default=BORRADOR, db_index=True)
    estado_recepcion = models.IntegerField(choices=ESTADOS_AVANCE, default=PENDIENTE)
    estado_facturacion = models.IntegerField(choices=ESTADOS_AVANCE, default=PENDIENTE)

    total = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Total Estimado")

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name='ordenes_compra', verbose_name="Usuario que acuerda")

    class Meta:
        verbose_name = "Orden de Compra"
        verbose_name_plural = "Órdenes de Compra"
        constraints = [
            # Correlativo único por empresa/punto una vez asignado (numero NULL en borrador no colisiona)
            models.UniqueConstraint(
                fields=['empresa', 'punto', 'numero'],
                name='uq_ordencompra_empresa_punto_numero',
            ),
        ]
        indexes = [
            models.Index(fields=['empresa', 'proveedor']),
            models.Index(fields=['empresa', 'fecha']),
            models.Index(fields=['empresa', 'estado']),
        ]

    def __str__(self):
        num = f"{self.numero}" if self.numero else "s/n"
        return f"OC {self.punto:04d}-{num} · {self.proveedor.razon_social}"

    def recalcular_total(self):
        """Recalcula el total estimado a partir de las líneas (solo si carga costos)."""
        from decimal import Decimal
        total = sum(
            (Decimal(str(i.cantidad)) * Decimal(str(i.precio_unitario)) for i in self.items.all()),
            Decimal("0.00"),
        )
        self.total = total
        return total

    def _avance(self, campo_cache):
        """Determina el estado de avance de un eje ('cantidad_recibida' o 'cantidad_facturada')
        agregando las líneas: PENDIENTE / PARCIAL / COMPLETA / CON_DIFERENCIA.

        Una línea con `marcado_diferencia` y pendiente sin resolver arrastra CON_DIFERENCIA
        (el proveedor cerró con otra cantidad y la OC no se ajustó)."""
        items = list(self.items.all())
        if not items:
            return self.PENDIENTE
        estados = set()
        for it in items:
            hecho = getattr(it, campo_cache)
            if it.marcado_diferencia and hecho != it.cantidad:
                estados.add(self.CON_DIFERENCIA)
            elif hecho <= 0:
                estados.add(self.PENDIENTE)
            elif hecho < it.cantidad:
                estados.add(self.PARCIAL)
            else:
                estados.add(self.COMPLETA)
        if self.CON_DIFERENCIA in estados:
            return self.CON_DIFERENCIA
        if estados == {self.COMPLETA}:
            return self.COMPLETA
        if estados == {self.PENDIENTE}:
            return self.PENDIENTE
        return self.PARCIAL

    def recalcular_estados(self, guardar=True):
        """Recalcula estado_recepcion / estado_facturacion y, si ambos están COMPLETA,
        marca la OC como CERRADA. No reabre una OC ANULADA.

        Normaliza: si una línea marcada con diferencia quedó sin pendiente (recibido y
        facturado alcanzaron la cantidad vigente, p. ej. tras ajustar la OC), limpia el flag."""
        for it in self.items.all():
            if it.marcado_diferencia and it.pendiente_recepcion == 0 and it.pendiente_facturacion == 0:
                it.marcado_diferencia = False
                it.save(update_fields=['marcado_diferencia'])
        self.estado_recepcion = self._avance('cantidad_recibida')
        self.estado_facturacion = self._avance('cantidad_facturada')
        if self.estado != self.ANULADA:
            if self.estado_recepcion == self.COMPLETA and self.estado_facturacion == self.COMPLETA:
                self.estado = self.CERRADA
            elif self.estado == self.CERRADA:
                # se reabrió por desafectación / nueva diferencia
                self.estado = self.CONFIRMADA
        if guardar:
            self.save(update_fields=['estado_recepcion', 'estado_facturacion', 'estado'])


class OrdenCompraItem(models.Model):
    """Línea de Orden de Compra. Lleva la cantidad vigente (ajustable) y el snapshot
    original, más los acumuladores cacheados de recibido/facturado (imputación por línea)."""

    orden = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT)
    # Cód. del proveedor para el producto: se consigna SOLO si el proveedor de la OC es el
    # habitual del producto (productos_producto.proveedor_id == orden.proveedor). Si no, vacío.
    cod_prov = models.CharField(max_length=50, blank=True, default='', verbose_name="Cód. Proveedor")
    cantidad = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                   verbose_name="Cantidad (vigente)")
    cantidad_original = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                            verbose_name="Cantidad Original (snapshot)")
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    iva_alicuota = models.DecimalField(max_digits=5, decimal_places=2, default=21.0)

    # Acumuladores cacheados (se mantienen por imputación FIFO desde recepciones/facturas)
    cantidad_recibida = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    cantidad_facturada = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Diferencia confirmada por el usuario: el proveedor entregó/facturó otra cantidad y
    # NO se autorizó ajustar la OC → la línea queda marcada con diferencia (pendiente vivo).
    marcado_diferencia = models.BooleanField(default=False, verbose_name="Marcado con Diferencia")

    class Meta:
        verbose_name = "Ítem de Orden de Compra"
        verbose_name_plural = "Ítems de Orden de Compra"
        indexes = [
            models.Index(fields=['orden', 'producto']),
        ]

    def __str__(self):
        return f"OC {self.orden_id} · {self.producto_id} x {self.cantidad}"

    @property
    def pendiente_recepcion(self):
        return self.cantidad - self.cantidad_recibida

    @property
    def pendiente_facturacion(self):
        return self.cantidad - self.cantidad_facturada

    @property
    def es_candidato_diferencia(self):
        """La cantidad facturada coincide con la recepcionada pero difiere de la pedida
        (vigente). NO decide el estado por sí sola: es la señal para que la UI de carga de
        factura pregunte si se ajusta la OC a la cantidad real o se marca la diferencia."""
        return (
            self.cantidad_facturada == self.cantidad_recibida
            and self.cantidad_facturada != self.cantidad
            and self.cantidad_facturada > 0
        )


# ------------------------------------------------------------------------------
# RECEPCIÓN (Informe de Recepción) — Plan 028 Fase 3
# Modelo único con `origen`: recepción de proveedor (con remito o generada por la
# factura) e —en Fase 6— transferencias internas entre sucursales. Prenumerado por
# (empresa, punto=sucursal destino, INFORME_RECEPCION). Baja = anulación lógica.
# ------------------------------------------------------------------------------

class Recepcion(AuditModel):
    # Origen de la recepción
    PROVEEDOR_REMITO = 'PROVEEDOR_REMITO'
    PROVEEDOR_FACTURA = 'PROVEEDOR_FACTURA'
    INTERNO = 'INTERNO'
    ORIGENES = [
        (PROVEEDOR_REMITO, 'Remito de Proveedor'),
        (PROVEEDOR_FACTURA, 'Generada por Factura'),
        (INTERNO, 'Transferencia Interna'),
    ]

    # Estado
    ACTIVA = 0
    ANULADA = 1
    ESTADOS = [(ACTIVA, 'Activa'), (ANULADA, 'Anulada')]

    recepcion_id = models.AutoField(primary_key=True)
    empresa = models.ForeignKey('empresas.Empresa', on_delete=models.PROTECT, related_name='recepciones')
    sucursal = models.ForeignKey('empresas.Sucursal', on_delete=models.PROTECT, related_name='recepciones',
                                 verbose_name="Sucursal (destino / stock)")
    punto = models.IntegerField(verbose_name="Punto")
    numero = models.BigIntegerField(null=True, blank=True, db_index=True, verbose_name="Número")
    fecha = models.DateField(db_index=True)

    origen = models.CharField(max_length=20, choices=ORIGENES, default=PROVEEDOR_REMITO, db_index=True)
    proveedor = models.ForeignKey(ClienteProveedor, on_delete=models.PROTECT, null=True, blank=True,
                                  related_name='recepciones')
    remito_proveedor = models.CharField(max_length=50, null=True, blank=True,
                                        verbose_name="N° Remito del Proveedor")
    # Cuando la factura hace de remito (no hubo recepción previa) genera esta recepción:
    generada_por_factura = models.ForeignKey('Compra', on_delete=models.SET_NULL, null=True, blank=True,
                                             related_name='recepciones_generadas')
    # (Fase 6) remito_interno FK a RemitoInterno cuando origen=INTERNO.

    observaciones = models.TextField(null=True, blank=True)
    estado = models.IntegerField(choices=ESTADOS, default=ACTIVA, db_index=True)

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='recepciones')

    class Meta:
        verbose_name = "Informe de Recepción"
        verbose_name_plural = "Informes de Recepción"
        constraints = [
            models.UniqueConstraint(
                fields=['empresa', 'punto', 'numero'],
                name='uq_recepcion_empresa_punto_numero',
            ),
        ]
        indexes = [
            models.Index(fields=['empresa', 'fecha']),
            models.Index(fields=['empresa', 'proveedor']),
            models.Index(fields=['empresa', 'origen']),
        ]

    def __str__(self):
        num = f"{self.numero}" if self.numero else "s/n"
        return f"Recepción {self.punto:04d}-{num} ({self.get_origen_display()})"


class RecepcionItem(models.Model):
    recepcion = models.ForeignKey(Recepcion, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT)
    cantidad_recibida = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Ítem de Recepción"
        verbose_name_plural = "Ítems de Recepción"
        indexes = [
            models.Index(fields=['recepcion', 'producto']),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Snapshot para el cálculo de delta de stock (creación/edición/borrado)
        self._original_cantidad = self.cantidad_recibida if self.pk else 0

    def __str__(self):
        return f"Rec {self.recepcion_id} · {self.producto_id} x {self.cantidad_recibida}"


class RecepcionImputacion(models.Model):
    """Reparte lo recibido en cada línea de recepción contra las líneas de origen
    (Orden de Compra en el circuito de proveedor; en Fase 6, también Remito Interno).
    Exactamente uno de los orígenes queda seteado. Acumula el cache de la línea de origen."""
    recepcion_item = models.ForeignKey(RecepcionItem, on_delete=models.CASCADE, related_name='imputaciones')
    orden_item = models.ForeignKey(OrdenCompraItem, on_delete=models.PROTECT, null=True, blank=True,
                                   related_name='imputaciones_recepcion')
    remito_interno_item = models.ForeignKey('RemitoInternoItem', on_delete=models.PROTECT, null=True, blank=True,
                                            related_name='imputaciones_recepcion')
    cantidad = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Imputación de Recepción"
        verbose_name_plural = "Imputaciones de Recepción"
        indexes = [
            models.Index(fields=['orden_item']),
            models.Index(fields=['remito_interno_item']),
        ]

    def __str__(self):
        return f"Imput. rec_item {self.recepcion_item_id} → {self.cantidad}"


# ------------------------------------------------------------------------------
# CIRCUITO INTERNO — Remito Interno (transferencia entre sucursales) — Plan 028 Fase 6
# Transferencia en 2 pasos: emitir Remito Interno = SALIDA del origen (en tránsito);
# el Informe de Recepción (origen=INTERNO) en el destino = ENTRADA. Sin asiento contable.
# Prenumerado por (empresa, punto=sucursal origen, REMITO_INTERNO). Baja = anulación lógica.
# ------------------------------------------------------------------------------

class RemitoInterno(AuditModel):
    ENVIO = 'ENVIO'
    DEVOLUCION = 'DEVOLUCION'
    TIPOS = [(ENVIO, 'Envío'), (DEVOLUCION, 'Devolución')]

    EMITIDO = 0
    REC_PARCIAL = 1
    RECEPCIONADO = 2
    ANULADO = 3
    ESTADOS = [
        (EMITIDO, 'Emitido'),
        (REC_PARCIAL, 'Recepción Parcial'),
        (RECEPCIONADO, 'Recepcionado'),
        (ANULADO, 'Anulado'),
    ]

    ri_id = models.AutoField(primary_key=True)
    empresa = models.ForeignKey('empresas.Empresa', on_delete=models.PROTECT, related_name='remitos_internos')
    sucursal_origen = models.ForeignKey('empresas.Sucursal', on_delete=models.PROTECT,
                                        related_name='remitos_internos_emitidos', verbose_name="Sucursal Origen")
    sucursal_destino = models.ForeignKey('empresas.Sucursal', on_delete=models.PROTECT,
                                         related_name='remitos_internos_recibidos', verbose_name="Sucursal Destino")
    punto = models.IntegerField(verbose_name="Punto (origen)")
    numero = models.BigIntegerField(null=True, blank=True, db_index=True, verbose_name="Número")
    fecha = models.DateField(db_index=True)
    tipo = models.CharField(max_length=12, choices=TIPOS, default=ENVIO)
    estado = models.IntegerField(choices=ESTADOS, default=EMITIDO, db_index=True)
    observaciones = models.TextField(null=True, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='remitos_internos')

    class Meta:
        verbose_name = "Remito Interno"
        verbose_name_plural = "Remitos Internos"
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'punto', 'numero'],
                                    name='uq_remitointerno_empresa_punto_numero'),
        ]
        indexes = [
            models.Index(fields=['empresa', 'fecha']),
            models.Index(fields=['empresa', 'sucursal_destino']),
            models.Index(fields=['empresa', 'estado']),
        ]

    def __str__(self):
        num = f"{self.numero}" if self.numero else "s/n"
        return f"Remito Interno {self.punto:04d}-{num}"

    def recalcular_estado(self, guardar=True):
        """EMITIDO / REC_PARCIAL / RECEPCIONADO según lo recibido de sus líneas (no reabre ANULADO)."""
        if self.estado == self.ANULADO:
            return
        lineas = list(self.items.all())
        if lineas and all(li.cantidad_recibida >= li.cantidad_enviada for li in lineas):
            self.estado = self.RECEPCIONADO
        elif any(li.cantidad_recibida > 0 for li in lineas):
            self.estado = self.REC_PARCIAL
        else:
            self.estado = self.EMITIDO
        if guardar:
            self.save(update_fields=['estado'])


class RemitoInternoItem(models.Model):
    remito = models.ForeignKey(RemitoInterno, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT)
    # Trazabilidad de Subproductos (Plan 052): vinculo con la instancia de Subproducto, Nro de Serie y CUIM
    subproducto = models.ForeignKey('productos.Subproducto', on_delete=models.SET_NULL, null=True, blank=True, related_name='remitos_internos_items')
    serie = models.CharField(max_length=50, null=True, blank=True, verbose_name="Nro. Serie")
    cuim = models.CharField(max_length=50, null=True, blank=True, verbose_name="CUIM")
    cantidad_enviada = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    cantidad_recibida = models.DecimalField(max_digits=15, decimal_places=2, default=0)  # cache

    class Meta:
        verbose_name = "Ítem de Remito Interno"
        verbose_name_plural = "Ítems de Remito Interno"
        indexes = [
            models.Index(fields=['remito', 'producto']),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_cantidad = self.cantidad_enviada if self.pk else 0

    @property
    def pendiente(self):
        """Unidades enviadas aún no recepcionadas por el destino (en tránsito)."""
        return self.cantidad_enviada - self.cantidad_recibida

    def __str__(self):
        return f"RI {self.remito_id} · {self.producto_id} x {self.cantidad_enviada}"


class CompraOCImputacion(models.Model):
    """Imputación de una línea de Factura de compra a una línea de Orden de Compra
    (Plan 028 Fase 5). Acumula OrdenCompraItem.cantidad_facturada (negativo para NC en Fase 7)."""
    compra_item = models.ForeignKey(CompraItem, on_delete=models.CASCADE, related_name='imputaciones_oc')
    orden_item = models.ForeignKey(OrdenCompraItem, on_delete=models.PROTECT, related_name='imputaciones_factura')
    cantidad = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Imputación Factura → OC"
        verbose_name_plural = "Imputaciones Factura → OC"
        indexes = [
            models.Index(fields=['orden_item']),
        ]

    def __str__(self):
        return f"Imput. compra_item {self.compra_item_id} → oc_item {self.orden_item_id}: {self.cantidad}"
