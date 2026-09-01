"""Listado de Facturas Pendientes — Plan 056.

Réplica del formulario VFP `tran_facturas_pendientes` (I-108): el estado de cancelación
de la cuenta corriente, comprobante por comprobante.

Tres diferencias de fondo con el original, documentadas en `docs/planes/056_...`:

1. **La fuente NO es el Libro IVA.** El VFP leía `lib_iva`; acá se lee `Compra` y `Venta`.
   El Libro IVA sólo se puebla con `condic in (1, 3)` y `LibroIvaVentas` ni siquiera se
   escribe, así que listar desde ahí escondería los `condic` 2 y 4 y dejaría Ventas vacío.
   Neto/IVA/No Gravado/Exento ya viven en Compra y Venta: no hace falta el subsistema fiscal.

2. **`pagado := total − saldo`,** para los dos lados. `Compra.pagado` existe y la identidad es
   exacta; `Venta` no tiene ese campo — tiene `cobrado` (cobro en el acto) y
   `saldo = total − cobrado − Σ ReciboAplicacion`. Con esta definición los totalizadores
   cierran por construcción (`Σ total = Σ pagado + Σ saldo`) en ambas operaciones.

3. **Sólo lectura.** El botón "Modificar" del VFP editaba `lib_iva.pagado` a mano porque el
   campo se desincronizaba. Acá `pagado`/`saldo` son derivados de las aplicaciones de OP y
   Recibos (`contable/services/saldos.py`): no hay nada que forzar y este módulo no escribe.

Multi-tenant: TODA consulta acotada a `empresa_id` — el filtro lo impone `FiltroFacturas`,
que no se puede construir sin empresa.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db.models import Sum

from contable.models import CONDIC_ASIENTO, CONDIC_MOVIMIENTO
from facturacion.models import Compra, Venta

CERO = Decimal('0.00')

#: Corte de la grilla en pantalla. Excel y PDF no truncan.
LIMITE_GRILLA = 500

#: Estado de cancelación. Réplica de los rangos de `saldo` del VFP (`opgPendientes`):
#: Pagadas ⇒ `saldo = 0`; Pendientes ⇒ `saldo <> 0` (el rango negativo es intencional:
#: así aparecen las notas de crédito todavía sin aplicar).
ESTADOS_PAGO = (
    ('todas', 'Todas'),
    ('pagadas', 'Pagadas'),
    ('pendientes', 'Pendientes'),
)

OPERACIONES = (
    ('C', 'Compras'),
    ('V', 'Ventas'),
)

CONDIC_NOMBRE = dict(CONDIC_ASIENTO)

#: `Venta.estado` == 1. Las `2` (Pend. Autorización) y `3` (Rechazada) sí se listan.
VENTA_ANULADA = 1


@dataclass
class FilaFactura:
    """Una fila del listado, ya normalizada: Compra y Venta se ven idénticas desde acá.

    `acum_global` y `acum_grupo` son las dos variantes de suma corrida de `saldo` que
    tenía el VFP: la global la usaba el Excel (columna `Acum.`) y la que reinicia por
    entidad, el reporte impreso.
    """
    pk: int
    asiento_id: int | None
    operacion: str
    condic: int
    fecha: date
    periodo: str
    comprobante: str
    entidad_id: int
    entidad_nombre: str
    entidad_clasificacion: str
    descripcion: str
    total: Decimal
    pagado: Decimal
    saldo: Decimal
    neto: Decimal
    iva: Decimal
    no_gravado: Decimal
    exento: Decimal
    otros: Decimal
    anulada: bool = False
    acum_global: Decimal = CERO
    acum_grupo: Decimal = CERO

    @property
    def condic_nombre(self) -> str:
        return CONDIC_NOMBRE.get(self.condic, str(self.condic))


@dataclass
class TotalesFacturas:
    """Totales del pie. Se calculan con `aggregate` sobre el conjunto COMPLETO, nunca
    sobre las filas truncadas: si no, el pie mentiría cada vez que se corta la grilla."""
    cantidad: int = 0
    total: Decimal = CERO
    pagado: Decimal = CERO
    saldo: Decimal = CERO


@dataclass
class FiltroFacturas:
    """Los cinco filtros de la pantalla original, más los dos que agregamos.

    `condics` e `incluir_anuladas` no existen en el VFP: el filtro de condición lo exige
    `.cursorrules` para todo listado con importes, y las anuladas son un concepto que el
    sistema viejo no tenía (allá se borraban).
    """
    empresa_id: int
    desde: date
    hasta: date
    operacion: str = 'C'
    entidad_id: int | None = None
    estado: str = 'todas'
    condics: tuple[int, ...] = field(default_factory=lambda: tuple(CONDIC_MOVIMIENTO))
    incluir_anuladas: bool = False

    @property
    def es_venta(self) -> bool:
        return self.operacion == 'V'

    def descripcion(self) -> str:
        """Línea de filtros que encabeza el Excel y el PDF (el `oApp.detalle` del VFP)."""
        etiqueta = dict(OPERACIONES).get(self.operacion, self.operacion)
        partes = [
            f"Comprobantes de {etiqueta} desde el "
            f"{self.desde.strftime('%d/%m/%Y')} al {self.hasta.strftime('%d/%m/%Y')}",
            dict(ESTADOS_PAGO).get(self.estado, self.estado),
        ]
        if self.condics and tuple(self.condics) != tuple(CONDIC_MOVIMIENTO):
            partes.append(
                "Condición: " + ", ".join(CONDIC_NOMBRE.get(c, str(c)) for c in self.condics))
        if self.incluir_anuladas:
            partes.append("Incluye anuladas")
        return "  |  ".join(partes)


def _queryset(f: FiltroFacturas):
    """Arma la consulta. Compras y Ventas son excluyentes (como el VFP): una sola tabla."""
    if f.es_venta:
        qs = Venta.objects.filter(empresa_id=f.empresa_id).select_related('tipo', 'cliente')
        if not f.incluir_anuladas:
            qs = qs.exclude(estado=VENTA_ANULADA)
        if f.entidad_id:
            qs = qs.filter(cliente_id=f.entidad_id)
        qs = qs.only(
            'ventas_id', 'asiento_id', 'fecha', 'periodo', 'punto', 'numero', 'condic',
            'estado', 'total', 'saldo', 'neto', 'iva', 'no_gravado', 'exento', 'otros',
            'tipo__codigo', 'cliente__codigo_id', 'cliente__razon_social',
            'cliente__clasificacion',
        ).order_by('cliente__razon_social', 'fecha', 'tipo__codigo', 'numero')
    else:
        qs = Compra.objects.filter(empresa_id=f.empresa_id).select_related('tipo', 'proveedor')
        if f.entidad_id:
            qs = qs.filter(proveedor_id=f.entidad_id)
        qs = qs.only(
            'compras_id', 'asiento_id', 'fecha', 'periodo', 'punto', 'numero', 'condic',
            'descripcion', 'total', 'pagado', 'saldo', 'neto', 'iva', 'no_gravado',
            'exento', 'otros', 'tipo__codigo', 'proveedor__codigo_id',
            'proveedor__razon_social', 'proveedor__clasificacion',
        ).order_by('proveedor__razon_social', 'fecha', 'tipo__codigo', 'numero')

    qs = qs.filter(fecha__gte=f.desde, fecha__lte=f.hasta)

    if f.condics:
        qs = qs.filter(condic__in=list(f.condics))

    # Réplica exacta de `opgPendientes` del VFP.
    if f.estado == 'pagadas':
        qs = qs.filter(saldo=0)
    elif f.estado == 'pendientes':
        qs = qs.exclude(saldo=0)

    return qs


def _comprobante(tipo, punto, numero) -> str:
    codigo = tipo.codigo if tipo else '--'
    return f"{codigo}-{punto or 0:04d}-{numero or 0:08d}"


def _a_decimal(valor) -> Decimal:
    return Decimal(str(valor or 0))


def _fila(obj, es_venta: bool) -> FilaFactura:
    entidad = obj.cliente if es_venta else obj.proveedor
    total = _a_decimal(obj.total)
    saldo = _a_decimal(obj.saldo)
    return FilaFactura(
        pk=obj.pk,
        asiento_id=obj.asiento_id,
        operacion='V' if es_venta else 'C',
        condic=obj.condic,
        fecha=obj.fecha,
        periodo=obj.periodo or '',
        comprobante=_comprobante(obj.tipo, obj.punto, obj.numero),
        entidad_id=entidad.codigo_id if entidad else 0,
        entidad_nombre=entidad.razon_social if entidad else '',
        entidad_clasificacion=(entidad.clasificacion or '') if entidad else '',
        descripcion='' if es_venta else (obj.descripcion or ''),
        total=total,
        # Regla unificadora: en Compra es identidad; en Venta equivale a
        # `cobrado + Σ aplicaciones de recibos`, que es justamente lo ya cobrado.
        pagado=total - saldo,
        saldo=saldo,
        neto=_a_decimal(obj.neto),
        iva=_a_decimal(obj.iva),
        no_gravado=_a_decimal(obj.no_gravado),
        exento=_a_decimal(obj.exento),
        otros=_a_decimal(obj.otros),
        anulada=bool(es_venta and obj.estado == VENTA_ANULADA),
    )


def calcular_totales(f: FiltroFacturas) -> TotalesFacturas:
    """Totales sobre el conjunto completo, en una sola consulta agregada."""
    qs = _queryset(f)
    agg = qs.aggregate(suma_total=Sum('total'), suma_saldo=Sum('saldo'))
    total = _a_decimal(agg['suma_total'])
    saldo = _a_decimal(agg['suma_saldo'])
    return TotalesFacturas(
        cantidad=qs.count(),
        total=total,
        pagado=total - saldo,
        saldo=saldo,
    )


def consultar(f: FiltroFacturas, limite: int | None = None):
    """Devuelve `(filas, totales, truncado)`.

    `limite` sólo recorta las filas devueltas: los totales siempre salen del conjunto
    completo. `truncado` avisa a la pantalla que hay más de lo que se ve.
    """
    qs = _queryset(f)
    totales = calcular_totales(f)

    if limite is not None:
        # Se pide uno de más para saber si hay que avisar del corte sin un COUNT extra.
        objetos = list(qs[:limite + 1])
        truncado = len(objetos) > limite
        objetos = objetos[:limite]
    else:
        objetos = list(qs)
        truncado = False

    filas = [_fila(o, f.es_venta) for o in objetos]

    # Sumas corridas. La global replica la columna `Acum.` del Excel del VFP; la de grupo,
    # el acumulado que el reporte impreso reinicia en cada cliente/proveedor.
    acum_global = CERO
    acum_grupo = CERO
    entidad_previa = None
    for fila in filas:
        if fila.entidad_id != entidad_previa:
            acum_grupo = CERO
            entidad_previa = fila.entidad_id
        acum_global += fila.saldo
        acum_grupo += fila.saldo
        fila.acum_global = acum_global
        fila.acum_grupo = acum_grupo

    return filas, totales, truncado


def agrupar_por_entidad(filas: list[FilaFactura]):
    """Corta las filas en grupos por cliente/proveedor para el PDF "RESUMEN DE CUENTAS".

    Las filas ya vienen ordenadas por razón social, así que alcanza con recorrerlas una vez.
    """
    grupos = []
    actual = None
    for fila in filas:
        if actual is None or fila.entidad_id != actual['entidad_id']:
            actual = {
                'entidad_id': fila.entidad_id,
                'entidad_nombre': fila.entidad_nombre,
                'filas': [],
                'total': CERO,
                'pagado': CERO,
                'saldo': CERO,
            }
            grupos.append(actual)
        actual['filas'].append(fila)
        actual['total'] += fila.total
        actual['pagado'] += fila.pagado
        actual['saldo'] += fila.saldo
    return grupos
