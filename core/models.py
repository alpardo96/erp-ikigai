from django.db import models
from django.conf import settings


class ContadorDocumento(models.Model):
    """
    Contador de numeración correlativa por (empresa, punto, tipo de documento).

    Garantiza series sin huecos ni duplicados para los documentos prenumerados por el
    sistema (Orden de Compra, Informe de Recepción, Remito Interno). El número se toma
    de forma transaccional mediante `core.services.numeracion.siguiente_numero`, que
    bloquea la fila con `select_for_update()`. La restricción de unicidad a nivel de BD
    del propio documento (unique_together empresa/punto/numero) actúa como segunda barrera.
    """
    ORDEN_COMPRA = 'ORDEN_COMPRA'
    INFORME_RECEPCION = 'INFORME_RECEPCION'
    REMITO_INTERNO = 'REMITO_INTERNO'
    # Distribución (Plan 074 §4.2): el control de integridad sólo es posible sobre los
    # comprobantes que uno EMITE, con numeración correlativa propia y auditable.
    PEDIDO = 'PEDIDO'
    REPARTO = 'REPARTO'
    RECEPCION_DEVOLUCION = 'RECEPCION_DEVOLUCION'
    # Series NO FISCALES de venta (Plan 075). La serie fiscal la gobierna ARCA y el
    # sistema la acompaña; estas dos no tienen ninguna autoridad externa que las valide,
    # así que su correlatividad es responsabilidad exclusiva nuestra.
    VENTA_PRE = 'VENTA_PRE'
    VENTA_NCI = 'VENTA_NCI'
    # Espejo LOCAL de la serie fiscal. La serie real la gobierna ARCA —el número sale de
    # `CbteDesde` en la respuesta del CAE—; este contador numera en modo prueba, cuando
    # no se llama a ARCA, y sirve de control cruzado contra `FECompUltimoAutorizado`.
    # Nunca reemplaza al número autorizado: en emisión real, ARCA lo pisa.
    VENTA_FISCAL = 'VENTA_FISCAL'
    # Acopio de tabaco (Plan 082). El romaneo es un documento que emitimos nosotros y cuya
    # correlatividad no gobierna nadie más, igual que los tres de Distribución de arriba.
    ROMANEO_TABACO = 'ROMANEO_TABACO'
    LOTE_TABACO = 'LOTE_TABACO'
    TIPOS_DOCUMENTO = [
        (ORDEN_COMPRA, 'Orden de Compra'),
        (INFORME_RECEPCION, 'Informe de Recepción'),
        (REMITO_INTERNO, 'Remito Interno'),
        (PEDIDO, 'Pedido de Cliente'),
        (REPARTO, 'Reparto / Hoja de Ruta'),
        (RECEPCION_DEVOLUCION, 'Recepcion de Devoluciones'),
        (VENTA_PRE, 'Presupuesto / PRE (no fiscal)'),
        (VENTA_NCI, 'Nota de Crédito Interna (no fiscal)'),
        (VENTA_FISCAL, 'Serie fiscal (espejo local / modo prueba)'),
        (ROMANEO_TABACO, 'Romaneo de Tabaco'),
        (LOTE_TABACO, 'Lote de Acopio de Tabaco'),
    ]

    empresa = models.ForeignKey('empresas.Empresa', on_delete=models.CASCADE, related_name='contadores')
    punto = models.IntegerField(verbose_name="Punto")
    tipo_documento = models.CharField(max_length=30, choices=TIPOS_DOCUMENTO, verbose_name="Tipo de Documento")
    ultimo_numero = models.BigIntegerField(default=0, verbose_name="Último Número Asignado")

    class Meta:
        verbose_name = "Contador de Documento"
        verbose_name_plural = "Contadores de Documentos"
        unique_together = ('empresa', 'punto', 'tipo_documento')
        indexes = [
            models.Index(fields=['empresa', 'punto', 'tipo_documento']),
        ]

    def __str__(self):
        return f"{self.get_tipo_documento_display()} - Empresa {self.empresa_id} / Punto {self.punto}: {self.ultimo_numero}"


class AuditModel(models.Model):
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name="%(class)s_creados"
    )
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name="%(class)s_modificados"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
