"""Servicio de la Caja Diaria de Tesorería.

La Caja Diaria es un REPORTE: no genera asientos, los lee. Le permite al tesorero ver los
movimientos de fondos bajo su responsabilidad y verificar si tiene todo registrado.

FUENTES DEL DETALLE (se combinan, sin duplicar)
-----------------------------------------------
1. `Asiento.sesion_caja` — el vínculo por `asiento_id` es el común denominador que une caja,
   recibos, órdenes de pago, compras y libro IVA. Capta las compras de contado y los asientos
   manuales que mueven fondos.
2. `MovimientoCaja` de la sesión — capta lo que no llega por la fuente 1, principalmente los
   cobros de caja mostrador, cuyo asiento se arma a mano y no recibe `sesion_caja`.

Cuando un comprobante ya tiene su asiento estampado en la caja se usa el asiento —que trae mejor
información contable— y se omite el movimiento, para que nada se cuente dos veces.

Nota (Plan 049): desde agosto de 2026 `MovimientoCaja` tiene su propia FK `asiento`, poblada por
los seis circuitos que crean movimientos. Eso vuelve innecesaria la combinación de dos fuentes:
alcanza con leer los movimientos y seguir su asiento. La unificación se hace en un plan aparte,
para no mezclar el cambio de modelo con el del reporte.

Recibos y Órdenes de Pago SÍ generan asiento contable (`contabilizar_recibo()` y
`contabilizar_orden_pago()` se invocan desde `tesoreria/views_htmx.py`), y ambos comprobantes
tienen `asiento_id`. La versión anterior de esta nota afirmaba lo contrario.

Criterio de saldos (definido por el usuario):
    Neto disponible = Efectivo + Dólares + Valores en cartera.
    Banco, Tarjetas y Otros NO arrastran saldo, pero SÍ informan su movimiento neto del día.
    Todos los importes se expresan pesificados (política bimonetaria del ERP).
"""

from decimal import Decimal
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from tesoreria.models import Caja, CajaSesion

# Las constantes y la descomposición de asientos en movimientos de fondos viven en `fondos.py`,
# compartidas con el Estado de Origen y Aplicación de Fondos (Plan 050). Se reexportan acá para
# no romper a quien las venía importando desde este módulo.
from tesoreria.services.fondos import (  # noqa: F401
    CERO,
    TIPOS_CON_SALDO,
    TIPOS_DISPONIBILIDAD,
    TIPOS_SIN_SALDO,
    cuantizar as _cuantizar,
    fila_vacia as _fila_vacia,
    lineas_de_fondos,
)


# ---------------------------------------------------------------------------
# Obtención de la caja
# ---------------------------------------------------------------------------

def get_caja_tesoreria(empresa_id, sucursal_id):
    """Devuelve (creando si hace falta) la caja de TESORERÍA de una sucursal.

    Es distinta de las cajas mostrador (`tipo='M'`): la de tesorería es una por sucursal y no
    depende del cajero que la opere.
    """
    caja = Caja.objects.filter(
        empresa_id=empresa_id, sucursal_id=sucursal_id, tipo='T', activa=True
    ).first()

    if not caja:
        from empresas.models import Sucursal
        sucursal = Sucursal.objects.get(id=sucursal_id, empresa_id=empresa_id)
        caja = Caja.objects.create(
            empresa_id=empresa_id,
            sucursal_id=sucursal_id,
            nombre=f"Tesorería {sucursal.nombre}",
            tipo='T',
            activa=True,
        )
    return caja


def get_sesion_activa(caja):
    """La caja activa de la sucursal (la que recibe los movimientos). Puede no existir."""
    return CajaSesion.objects.filter(caja=caja, estado='A').order_by('-id').first()


@transaction.atomic
def abrir_caja(caja, usuario, si_efectivo=None, si_dolares=None, si_valores=None):
    """Abre la próxima caja de tesorería, arrastrando los saldos del último cierre.

    Se bloquea la fila de la `Caja` para que dos usuarios de la misma sucursal no puedan abrir
    dos cajas activas en paralelo (la numeración y el arrastre deben ser únicos).
    """
    caja = Caja.objects.select_for_update().get(pk=caja.pk)

    activa = get_sesion_activa(caja)
    if activa:
        return activa

    ultima_cerrada = CajaSesion.objects.filter(
        caja=caja, estado='C'
    ).order_by('-numero', '-id').first()

    if si_efectivo is None:
        si_efectivo = ultima_cerrada.sf_efectivo if ultima_cerrada else CERO
    if si_dolares is None:
        si_dolares = ultima_cerrada.sf_dolares if ultima_cerrada else CERO
    if si_valores is None:
        si_valores = ultima_cerrada.sf_valores if ultima_cerrada else CERO

    ultimo_numero = CajaSesion.objects.filter(
        caja__empresa_id=caja.empresa_id, caja__tipo='T'
    ).aggregate(m=Max('numero'))['m'] or 0

    return CajaSesion.objects.create(
        caja=caja,
        usuario=usuario,
        numero=ultimo_numero + 1,
        estado='A',
        si_efectivo=si_efectivo,
        si_dolares=si_dolares,
        si_valores=si_valores,
        saldo_inicial=si_efectivo + si_dolares + si_valores,
        creado_por=usuario,
        modificado_por=usuario,
    )


def get_o_abrir_caja(empresa_id, sucursal_id, usuario):
    """Atajo para la pantalla: caja de tesorería de la sucursal + su caja activa."""
    caja = get_caja_tesoreria(empresa_id, sucursal_id)
    sesion = get_sesion_activa(caja)
    if not sesion:
        sesion = abrir_caja(caja, usuario)
    return caja, sesion


# ---------------------------------------------------------------------------
# Armado del reporte
# ---------------------------------------------------------------------------

# `_fila_vacia` y `_cuantizar` ya vienen importados de `fondos.py` (arriba): tenerlos definidos
# también acá era la misma función escrita dos veces.

# Categoría del medio de pago -> columna del parte, cuando la cuenta contable del medio no
# está clasificada. La billetera digital se informa como Banco por ser dinero bancarizado.
MAPEO_CATEGORIA = {
    'EFE': 'EFE',
    'CHQ': 'VAL',
    'TRA': 'BCO',
    'TAR': 'TAR',
    'DIG': 'BCO',
    'RET': 'OTR',
    'OTR': 'OTR',
}


def _clasificar_detalle(detalle):
    """Columna del parte a la que corresponde un detalle de movimiento de caja."""
    medio = detalle.medio_pago
    cuenta = getattr(medio, 'cuenta_contable', None)
    if cuenta is not None and cuenta.tipo_disponibilidad:
        tipo = cuenta.tipo_disponibilidad
    else:
        tipo = MAPEO_CATEGORIA.get(medio.categoria, 'OTR')

    # El efectivo en moneda extranjera se informa en la columna Dólares (importe pesificado).
    if tipo == 'EFE' and detalle.importe_moneda_extranjera and detalle.importe_moneda_extranjera > 0:
        tipo = 'DOL'
    return tipo


def _contrapartidas_de_movimiento(movimiento, cuentas_por_pk):
    """Contrapartidas de un movimiento de caja: (cuenta, descripción, peso).

    Replica lo que el legado muestra en las columnas `cta` / `concepto contable`: la cuenta de
    gasto imputada, o la cuenta patrimonial del cliente/proveedor cuando el comprobante se aplica
    a facturas. El peso reparte el desglose por medio de pago cuando hay más de una imputación.
    """
    comprobante = movimiento.recibo or movimiento.orden_pago
    if comprobante is None:
        # Cobro directo de mostrador: la contrapartida es el cliente de la venta.
        if movimiento.venta_id:
            venta = movimiento.venta
            cuenta = cuentas_por_pk.get(venta.cliente.cta_pat) if venta.cliente_id and venta.cliente.cta_pat else None
            return [(cuenta, movimiento.concepto, abs(movimiento.importe or CERO))]
        return []

    imputaciones = list(comprobante.imputaciones_simples.select_related('cuenta_contable').all())
    if imputaciones:
        return [(i.cuenta_contable, i.leyenda or movimiento.concepto, abs(i.importe)) for i in imputaciones]

    aplicaciones = list(comprobante.aplicaciones.all())
    entidad = getattr(comprobante, 'cliente', None) or getattr(comprobante, 'proveedor', None)
    # `cta_pat` guarda el pk de la cuenta patrimonial del cliente/proveedor (no es una FK).
    cuenta = cuentas_por_pk.get(entidad.cta_pat) if entidad and entidad.cta_pat else None

    if aplicaciones:
        if movimiento.recibo_id:
            referencias = ".".join(f"{a.venta.tipo.codigo if a.venta.tipo else ''}{a.venta.numero}" for a in aplicaciones)
        else:
            referencias = ".".join(f"{a.compra.tipo.codigo if a.compra.tipo else ''}{a.compra.numero}" for a in aplicaciones)
        return [(cuenta, f"Paga: {referencias}", abs(comprobante.total or CERO))]

    return [(cuenta, movimiento.concepto, abs(comprobante.total or CERO))]


def _lineas_desde_movimientos(sesion, condic, asientos_ya_procesados):
    """Detalle a partir de `MovimientoCaja` (recibos y órdenes de pago, que hoy no asientan)."""
    from tesoreria.models import MovimientoCaja

    movimientos = list(
        MovimientoCaja.objects
        .filter(sesion=sesion)
        .select_related('recibo__cliente', 'orden_pago__proveedor', 'venta__cliente')
        .prefetch_related('detalles__medio_pago__cuenta_contable')
        .order_by('id')
    )
    if condic in (1, 2):
        movimientos = [m for m in movimientos if m.condic == condic]

    # Precarga de las cuentas patrimoniales (`cta_pat` es un pk, no una FK) en una sola consulta.
    pks_cuentas = set()
    for movimiento in movimientos:
        entidad = getattr(movimiento.recibo, 'cliente', None) if movimiento.recibo_id else None
        if entidad is None and movimiento.orden_pago_id:
            entidad = movimiento.orden_pago.proveedor
        if entidad is None and movimiento.venta_id:
            entidad = movimiento.venta.cliente
        if entidad is not None and entidad.cta_pat:
            pks_cuentas.add(entidad.cta_pat)

    from contable.models import Cuenta
    cuentas_por_pk = {
        c.pk: c for c in Cuenta.objects.filter(pk__in=pks_cuentas, empresa_id=sesion.caja.empresa_id)
    } if pks_cuentas else {}

    filas = []
    for movimiento in movimientos:
        comprobante = movimiento.recibo or movimiento.orden_pago
        # Si el movimiento ya generó un asiento estampado en esta caja, manda el asiento.
        #
        # Se consulta PRIMERO `movimiento.asiento_id` (Plan 049): antes se navegaba al
        # comprobante, y la cadena solo contemplaba `recibo` y `orden_pago`. Los cobros de caja
        # mostrador cuelgan de `venta`, así que quedaban fuera de la deduplicación y se contaban
        # dos veces en cuanto su asiento recibía `sesion_caja`.
        # El fallback al comprobante cubre los movimientos históricos anteriores al backfill.
        asiento_del_movimiento = (
            movimiento.asiento_id
            or getattr(comprobante, 'asiento_id', None)
            or getattr(movimiento.venta, 'asiento_id', None)
        )
        if asiento_del_movimiento and asiento_del_movimiento in asientos_ya_procesados:
            continue

        signo = Decimal('1') if movimiento.tipo in ('I', 'A') else Decimal('-1')

        netos = _fila_vacia()
        for detalle in movimiento.detalles.all():
            netos[_clasificar_detalle(detalle)] += signo * detalle.importe

        if all(v == CERO for v in netos.values()):
            continue

        contrapartidas = _contrapartidas_de_movimiento(movimiento, cuentas_por_pk)
        entidad = None
        if movimiento.recibo_id:
            entidad = movimiento.recibo.cliente
        elif movimiento.orden_pago_id:
            entidad = movimiento.orden_pago.proveedor
        elif movimiento.venta_id:
            entidad = movimiento.venta.cliente

        if not contrapartidas:
            repartos = [(None, movimiento.concepto, netos)]
        elif len(contrapartidas) == 1:
            cuenta, descripcion, _ = contrapartidas[0]
            repartos = [(cuenta, descripcion, netos)]
        else:
            repartos = []
            suma_pesos = sum((p for _, _, p in contrapartidas), CERO) or Decimal('1')
            acumulado = _fila_vacia()
            for indice, (cuenta, descripcion, peso) in enumerate(contrapartidas):
                if indice == len(contrapartidas) - 1:
                    parte = {t: netos[t] - acumulado[t] for t in TIPOS_DISPONIBILIDAD}
                else:
                    factor = peso / suma_pesos
                    parte = {t: _cuantizar(netos[t] * factor) for t in TIPOS_DISPONIBILIDAD}
                    for t in TIPOS_DISPONIBILIDAD:
                        acumulado[t] += parte[t]
                repartos.append((cuenta, descripcion, parte))

        for cuenta, descripcion, parte in repartos:
            filas.append({
                'orden': (movimiento.fecha, movimiento.id),
                'asiento_id': getattr(comprobante, 'asiento_id', None) if comprobante else None,
                'fecha': movimiento.fecha.date() if hasattr(movimiento.fecha, 'date') else movimiento.fecha,
                'codigo': entidad.codigo_id if entidad else '',
                'razon': entidad.razon_social if entidad else '',
                'cuenta_id': cuenta.id if cuenta else None,
                'jerarquia': cuenta.jerarquia if cuenta else '',
                'cuenta': cuenta.cuenta if cuenta else 'SIN IMPUTAR',
                'descripcion': descripcion or movimiento.concepto,
                'condic': movimiento.condic,
                'parte': parte,
            })
    return filas


def armar_caja_diaria(sesion, condic=None):
    """Arma el detalle y los saldos de una caja.

    `condic`: 1 = solo Real/Fiscal, 2 = solo Presupuestado/No Fiscal, None = ambos.

    Cada línea del detalle corresponde a una CONTRAPARTIDA del asiento (la cuenta de gasto,
    proveedor o cliente que se ve en las columnas `cta` y `concepto contable` del legado), con el
    desglose por medio de pago tomado del lado de las disponibilidades. Si un asiento tiene varias
    contrapartidas, el desglose se prorratea entre ellas según su importe.
    """
    filas, asientos_procesados = _lineas_desde_asientos(sesion, condic)
    filas += _lineas_desde_movimientos(sesion, condic, asientos_procesados)
    filas.sort(key=lambda f: f['orden'])

    movimientos = []
    totales = _fila_vacia()
    ingresos = CERO
    egresos = CERO

    # El saldo arranca en el neto inicial y se arrastra línea a línea, como el legado.
    saldo = sesion.si_efectivo + sesion.si_dolares + sesion.si_valores

    for fila in filas:
        parte = fila.pop('parte')
        fila.pop('orden')
        total_linea = sum(parte.values(), CERO)
        # Solo Efectivo + Dólares + Valores mueven el saldo disponible.
        saldo += parte['EFE'] + parte['DOL'] + parte['VAL']

        fila.update({
            'efectivo': parte['EFE'],
            'dolares': parte['DOL'],
            'valores': parte['VAL'],
            'banco': parte['BCO'],
            'tarjetas': parte['TAR'],
            'otros': parte['OTR'],
            'total': total_linea,
            'saldo': saldo,
        })
        movimientos.append(fila)

        for t in TIPOS_DISPONIBILIDAD:
            totales[t] += parte[t]
        if total_linea > 0:
            ingresos += total_linea
        else:
            egresos += -total_linea

    inicial = {
        'efectivo': sesion.si_efectivo,
        'dolares': sesion.si_dolares,
        'valores': sesion.si_valores,
        'banco': CERO,
        'tarjetas': CERO,
        'otros': CERO,
    }
    inicial['neto'] = inicial['efectivo'] + inicial['dolares'] + inicial['valores']

    movimiento = {
        'efectivo': totales['EFE'],
        'dolares': totales['DOL'],
        'valores': totales['VAL'],
        'banco': totales['BCO'],
        'tarjetas': totales['TAR'],
        'otros': totales['OTR'],
        'ingresos': ingresos,
        'egresos': egresos,
    }
    # El neto que arrastra es SOLO el de las disponibilidades con saldo. Banco y tarjetas quedan
    # informados aparte: por eso `inicial.neto + movimiento.neto == final.neto` siempre cierra.
    movimiento['neto'] = movimiento['efectivo'] + movimiento['dolares'] + movimiento['valores']

    final = {
        'efectivo': inicial['efectivo'] + movimiento['efectivo'],
        'dolares': inicial['dolares'] + movimiento['dolares'],
        'valores': inicial['valores'] + movimiento['valores'],
        'banco': movimiento['banco'],
        'tarjetas': movimiento['tarjetas'],
        'otros': movimiento['otros'],
    }
    final['neto'] = final['efectivo'] + final['dolares'] + final['valores']

    return {
        'sesion': sesion,
        'movimientos': movimientos,
        'saldos': {'inicial': inicial, 'movimiento': movimiento, 'final': final},
    }


def asientos_de_fondos(condic=None, **filtros):
    """Queryset base de asientos que pueden mover fondos, con lo necesario ya precargado.

    Los `filtros` los pone quien llama: `sesion_caja=...` para la Caja Diaria, `empresa` y rango
    de `fecha` para el Estado de Origen y Aplicación de Fondos.
    """
    from contable.models import Asiento

    asientos = (
        Asiento.objects
        .filter(anulado=False, **filtros)
        .select_related('cli_pro')
        .prefetch_related('lineas__cuenta', 'lineas__cli_pro')
        .order_by('asiento_id')
    )
    if condic in (1, 2):
        asientos = asientos.filter(condic=condic)
    return asientos


def _lineas_desde_asientos(sesion, condic):
    """Detalle a partir de los asientos estampados con la caja. Devuelve (filas, ids_procesados).

    La descomposición vive en `fondos.lineas_de_fondos()`, compartida con el EOAF (Plan 050).
    """
    return lineas_de_fondos(asientos_de_fondos(condic, sesion_caja=sesion))

    return filas, procesados


def agrupar_para_pdf(movimientos):
    """Agrupa el detalle en INGRESOS / EGRESOS y, dentro, por cuenta ordenada por jerarquía.

    A diferencia del reporte legado —que quebraba por cambio de cuenta consecutivo y repetía la
    misma cuenta varias veces— acá cada cuenta aparece UNA sola vez con su subtotal.
    """
    secciones = []
    for titulo, filtro in (('INGRESOS', lambda m: m['total'] > 0), ('EGRESOS', lambda m: m['total'] <= 0)):
        del_grupo = [m for m in movimientos if filtro(m)]
        if not del_grupo:
            continue

        cuentas = {}
        for mov in del_grupo:
            clave = (mov['jerarquia'], mov['cuenta'])
            cuentas.setdefault(clave, []).append(mov)

        grupos = []
        total_seccion = _fila_vacia()
        total_seccion_importe = CERO
        for (jerarquia, cuenta), movs in sorted(cuentas.items(), key=lambda kv: kv[0][0]):
            subtotal = {
                'efectivo': sum((m['efectivo'] for m in movs), CERO),
                'dolares': sum((m['dolares'] for m in movs), CERO),
                'valores': sum((m['valores'] for m in movs), CERO),
                'banco': sum((m['banco'] for m in movs), CERO),
                'tarjetas': sum((m['tarjetas'] for m in movs), CERO),
                'total': sum((m['total'] for m in movs), CERO),
            }
            grupos.append({
                'jerarquia': jerarquia, 'cuenta': cuenta,
                'movimientos': movs, 'subtotal': subtotal,
            })
            total_seccion_importe += subtotal['total']
            for campo, tipo in (('efectivo', 'EFE'), ('dolares', 'DOL'), ('valores', 'VAL'),
                                ('banco', 'BCO'), ('tarjetas', 'TAR')):
                total_seccion[tipo] += subtotal[campo]

        secciones.append({
            'titulo': titulo,
            'grupos': grupos,
            'total': {
                'efectivo': total_seccion['EFE'], 'dolares': total_seccion['DOL'],
                'valores': total_seccion['VAL'], 'banco': total_seccion['BCO'],
                'tarjetas': total_seccion['TAR'], 'total': total_seccion_importe,
            },
        })
    return secciones


# ---------------------------------------------------------------------------
# Cierre
# ---------------------------------------------------------------------------

@transaction.atomic
def cerrar_caja(sesion, usuario, fecha_operativa=None):
    """Cierra la caja, congela sus saldos finales y abre la siguiente con el arrastre.

    Se bloquea la fila con `select_for_update()` para impedir cierres concurrentes o que entren
    movimientos mientras se calculan los saldos definitivos.
    """
    sesion = CajaSesion.objects.select_for_update().get(pk=sesion.pk)

    if sesion.estado == 'C':
        raise ValueError("La caja ya se encuentra cerrada.")

    datos = armar_caja_diaria(sesion)
    final = datos['saldos']['final']

    sesion.sf_efectivo = final['efectivo']
    sesion.sf_dolares = final['dolares']
    sesion.sf_valores = final['valores']
    sesion.saldo_final_calculado = final['neto']
    sesion.fecha_operativa = fecha_operativa or timezone.localdate()
    sesion.fecha_cierre = timezone.localtime()
    sesion.estado = 'C'
    sesion.modificado_por = usuario
    sesion.save(update_fields=[
        'sf_efectivo', 'sf_dolares', 'sf_valores', 'saldo_final_calculado',
        'fecha_operativa', 'fecha_cierre', 'estado', 'modificado_por',
    ])

    nueva = abrir_caja(sesion.caja, usuario)
    return sesion, nueva
