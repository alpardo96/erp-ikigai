"""Estado de Origen y Aplicación de Fondos (Plan 050).

Un sumas y saldos que corre sobre los MOVIMIENTOS DE FONDOS en lugar de sobre los asientos. Para
cada cuenta del plan responde cuánta plata entró por ella, cuánta salió y cuál fue el flujo neto
en un rango de fechas. Es el `suma_saldo_fciero` del sistema VFP.

CÓMO SE LEE EL SIGNO
--------------------
La descomposición la hace `fondos.lineas_de_fondos()`: cada fila trae el desglose por medio
(`parte`) con el signo visto desde la caja —positivo entra, negativo sale—. De ahí sale todo:

- fila con total **positivo** -> la cuenta fue **ORIGEN** de fondos    -> Ingresos
- fila con total **negativo** -> la cuenta fue **APLICACIÓN** de fondos -> Egresos

Que es lo mismo que decir que la contrapartida al HABER es un origen (una cobranza deja al
cliente en el haber) y al DEBE una aplicación (un pago deja al proveedor en el debe).

LO QUE NO ENTRA
---------------
Los traslados entre disponibilidades —retiro de caja mostrador a tesorería, depósito bancario,
cierre de caja—. Sus dos puntas son cuentas de disponibilidad, así que no tienen contrapartida y
`lineas_de_fondos` las emite con `cuenta_id = None`. Mover plata de un bolsillo a otro no es ni
origen ni aplicación: se descartan. El sistema legado, en cambio, las mostraba mezcladas en el
cuerpo del reporte.

SIN "DISPONIBILIDAD INICIAL"
----------------------------
Por decisión del usuario el reporte mide el flujo ENTRE DOS FECHAS y no arrastra el acumulado
anterior. Además, en el legado esa columna estaba rota: las cuentas imputables la sumaban al
flujo neto y las sumarizadoras no, así que una sumarizadora nunca coincidía con sus hijas.
"""

from tesoreria.services.fondos import (
    CERO,
    TIPOS_DISPONIBILIDAD,
    asientos_de_fondos_por_fecha,
    fila_vacia,
    lineas_de_fondos,
)

# En movimientos de fondos solo existen Real y Presupuestado (ver el CheckConstraint
# `mov_caja_condic_1_o_2` y la lente de Gestión de `.cursorrules`).
CONDIC_FONDOS = (1, 2)


def _celda(cuenta=None):
    return {
        'cuenta_id': cuenta.id if cuenta else None,
        'codigo': cuenta.codigo if cuenta else None,
        'jerarquia': cuenta.jerarquia if cuenta else '',
        'detalle': cuenta.cuenta if cuenta else '',
        'imputable': bool(cuenta.imputable) if cuenta else True,
        'ingresos': CERO,
        'egresos': CERO,
        'neto': CERO,
        'medios': fila_vacia(),
    }


def _acumular(destino, origen):
    destino['ingresos'] += origen['ingresos']
    destino['egresos'] += origen['egresos']
    destino['neto'] += origen['neto']
    for t in TIPOS_DISPONIBILIDAD:
        destino['medios'][t] += origen['medios'][t]


def estado_origen_aplicacion_fondos(empresa_id, desde, hasta, condics=CONDIC_FONDOS):
    """Arma el EOAF de una empresa entre dos fechas.

    Devuelve `{'filas': [...], 'totales': {...}, 'periodo': (desde, hasta), 'condics': (...)}`.

    Las filas vienen ordenadas por `jerarquia` e incluyen las cuentas sumarizadoras, que acumulan
    a sus descendientes IMPUTABLES por prefijo de jerarquía. Se acumula solo sobre imputables para
    que un nivel intermedio no se cuente dos veces.

    Se usa el prefijo de `jerarquia` y no la FK `Cuenta.sumariza` porque en los datos migrados del
    sistema legado `sumariza` quedó desfasado (cuentas 113204…113300 apuntan a la 75 pero cuelgan
    de la 113). El legado tampoco lo nota: acumula por prefijo, igual que acá.

    Las cuentas sin movimiento en el período no se devuelven.
    """
    condics = tuple(c for c in (condics or ()) if c in CONDIC_FONDOS)
    if not condics:
        return {'filas': [], 'totales': _celda(), 'periodo': (desde, hasta), 'condics': ()}

    from contable.models import Cuenta

    asientos = asientos_de_fondos_por_fecha(empresa_id, desde, hasta, condics)
    filas_detalle, _ = lineas_de_fondos(asientos)

    # --- 1. Agregación por cuenta de contrapartida ---------------------------------------
    cuentas = {
        c.id: c for c in Cuenta.objects.filter(empresa_id=empresa_id)
    }
    acumulado = {}

    for fila in filas_detalle:
        # Sin contrapartida = traslado entre disponibilidades: no es origen ni aplicación.
        if not fila['cuenta_id']:
            continue
        cuenta = cuentas.get(fila['cuenta_id'])
        if cuenta is None:
            continue

        celda = acumulado.setdefault(cuenta.id, _celda(cuenta))
        total = sum(fila['parte'].values(), CERO)
        if total > 0:
            celda['ingresos'] += total
        else:
            celda['egresos'] += -total
        celda['neto'] += total
        for t in TIPOS_DISPONIBILIDAD:
            celda['medios'][t] += fila['parte'][t]

    if not acumulado:
        return {'filas': [], 'totales': _celda(), 'periodo': (desde, hasta), 'condics': condics}

    # --- 2. Rollup jerárquico sobre las sumarizadoras --------------------------------------
    # Se recorre cada sumarizadora una sola vez contra las imputables con movimiento, que son
    # pocas: no hace falta armar el árbol.
    # Solo las IMPUTABLES alimentan el rollup: si se sumaran también los niveles intermedios,
    # una sumarizadora de arriba contaría dos veces lo mismo. Es el `and imputable = .T.` del
    # bucle del legado.
    imputables = [(cuentas[cid], celda) for cid, celda in acumulado.items()
                  if cuentas[cid].imputable]

    resultado = {cid: celda for cid, celda in acumulado.items()}

    for cuenta in cuentas.values():
        if cuenta.imputable or cuenta.id in resultado:
            continue
        prefijo = (cuenta.jerarquia or '').strip()
        if not prefijo:
            continue

        celda = _celda(cuenta)
        hubo = False
        for hija, celda_hija in imputables:
            jerarquia_hija = (hija.jerarquia or '').strip()
            if jerarquia_hija != prefijo and jerarquia_hija.startswith(prefijo):
                _acumular(celda, celda_hija)
                hubo = True
        if hubo:
            resultado[cuenta.id] = celda

    # --- 3. Filas ordenadas y totales ------------------------------------------------------
    filas = [c for c in resultado.values() if c['ingresos'] or c['egresos']]
    filas.sort(key=lambda c: (c['jerarquia'], c['codigo'] or 0))

    # Los totales suman SOLO las imputables: las sumarizadoras ya las contienen.
    totales = _celda()
    for celda in filas:
        if celda['imputable']:
            _acumular(totales, celda)

    return {
        'filas': filas,
        'totales': totales,
        'periodo': (desde, hasta),
        'condics': condics,
    }


def detalle_de_cuenta(empresa_id, desde, hasta, cuenta_id, condics=CONDIC_FONDOS, medio=None):
    """Movimientos de fondos de UNA cuenta, para el drill-down.

    Es la vista `cons_caja_diaria_cta` del legado. `medio` filtra por tipo de disponibilidad
    ('EFE', 'BCO', 'VAL'...), como el option-group Todos/Efectivo/Banco/Valores del formulario.
    Devuelve las filas con su saldo corrido.
    """
    condics = tuple(c for c in (condics or ()) if c in CONDIC_FONDOS)
    if not condics:
        return {'filas': [], 'totales': _celda()}

    asientos = asientos_de_fondos_por_fecha(empresa_id, desde, hasta, condics)
    filas_detalle, _ = lineas_de_fondos(asientos)

    filas = [f for f in filas_detalle if f['cuenta_id'] == cuenta_id]
    if medio in TIPOS_DISPONIBILIDAD:
        filas = [f for f in filas if f['parte'][medio] != CERO]

    filas.sort(key=lambda f: f['orden'])

    totales = _celda()
    saldo = CERO
    for fila in filas:
        total = sum(fila['parte'].values(), CERO)
        fila['ingresos'] = total if total > 0 else CERO
        fila['egresos'] = -total if total < 0 else CERO
        saldo += total
        fila['saldo'] = saldo
        fila['neto'] = total
        fila['medios'] = fila['parte']
        _acumular(totales, fila)

    return {'filas': filas, 'totales': totales}
