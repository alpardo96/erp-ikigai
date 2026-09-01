"""Balance de Saldos Mensuales — núcleo de cálculo (Plan 047).

Para cada cuenta del plan devuelve el saldo de apertura, el movimiento neto de cada mes del
ejercicio y el saldo al cierre.

REGLA CENTRAL — reparto por `condic` (§3.3 del plan)
----------------------------------------------------
    Columna Apertura   <-  condic = 5              (siempre, y sólo esto)
    Columnas mensuales <-  condic in {1, 2, 3, 4}  (el usuario elige cuáles ver)
    Nunca entran       <-  condic in {6, 7}        (anularían los resultados del ejercicio)

Universos disjuntos que NO dependen de la fecha: un asiento de apertura fechado el 01/01/2025 va
a la columna Apertura, nunca a la columna `202501`.

De ahí sale la identidad que define el reporte:

    Apertura + N meses = saldo al cierre

que es el mismo número que el Sumas y Saldos muestra en su saldo final (con los cuatro `condic`
tildados). No se arrastran movimientos anteriores al inicio del ejercicio, no hay fallback y no
hay saldo inferido: es una diferencia DELIBERADA con `_calcular_balance`, que sí los suma porque
corre sobre un rango de fechas arbitrario y no sobre un ejercicio.

SIGNO
-----
Este servicio devuelve SIEMPRE el signo contable natural (`debe − haber`), en todos los modos.
La inversión (× −1) de las cuentas de resultado vive únicamente en la exportación a Excel: en
pantalla el operador necesita ver el movimiento tal cual quedó registrado, porque el signo es el
dato que le permite detectar un error de carga.
"""
from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db.models import F, Sum
from django.db.models.functions import TruncMonth

from contable.models import AsientoLinea, Cuenta

CERO = Decimal("0.00")

#: `condic` que puede mostrar una columna mensual. Ver `contable.models.CONDIC_MOVIMIENTO`.
CONDICS_MENSUALES = (1, 2, 3, 4)

#: `condic` del asiento de apertura. Alimenta la columna Apertura y nada más.
CONDIC_APERTURA = 5

#: Cortafuegos ante un `Ejercicio` mal cargado. No es un límite funcional.
TOPE_PERIODOS = 24

MESES_ABREV = ('Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
               'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic')

#: Tipos de cuenta por alcance. El modo 'resultados' replica el `SET FILTER TO tipo = 'R'` del VFP.
TIPOS_POR_ALCANCE = {
    'todas': None,
    'resultados': ('R',),
    'patrimoniales': ('A', 'P', 'N'),
}


def periodos_ejercicio(ejercicio, tope=TOPE_PERIODOS):
    """Columnas mensuales del ejercicio, en orden.

    La cantidad y el rótulo dependen del ejercicio: no son doce columnas fijas. Un ejercicio
    abr/2025-mar/2026 arranca en `202504` y termina en `202603`; uno irregular de cuatro meses
    genera cuatro columnas.

    Se guarda el (año, mes) real y no sólo el número de mes calendario como hace el VFP —que
    reordena doce columnas físicas `mes_01..mes_12`—, para que dos meses homónimos de años
    distintos no puedan colisionar en la misma columna.
    """
    anio, mes = ejercicio.inicio.year, ejercicio.inicio.month
    fin = (ejercicio.cierre.year, ejercicio.cierre.month)
    periodos = []
    while (anio, mes) <= fin and len(periodos) < tope:
        periodos.append({
            'clave': f"{anio}{mes:02d}",
            'label': f"{MESES_ABREV[mes - 1]}-{anio % 100:02d}",
            'anio': anio,
            'mes': mes,
            'primer_dia': date(anio, mes, 1),
            'ultimo_dia': date(anio, mes, monthrange(anio, mes)[1]),
        })
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return periodos


def _sanear_condics(condics):
    """Intersecta lo recibido con {1,2,3,4}, preservando el orden canónico.

    Sin esto, un querystring armado a mano (`?condic=5&condic=6`) metería la apertura o la
    refundición dentro de una columna mensual y rompería la identidad del reporte.
    """
    if condics is None:
        return list(CONDICS_MENSUALES)
    pedidos = set()
    for c in condics:
        try:
            pedidos.add(int(c))
        except (TypeError, ValueError):
            continue
    return [c for c in CONDICS_MENSUALES if c in pedidos]


def _profundidad(cuentas):
    """Nivel de cada cuenta siguiendo la cadena `sumariza`, para indentar y ordenar el rollup.

    Se calcula sobre el árbol y no sobre `len(jerarquia)`: la longitud del código depende de la
    convención de numeración de cada empresa, el árbol no. Tolera ciclos y padres colgados.
    """
    padres = {c.id: c.sumariza_id for c in cuentas}
    nivel = {}

    for cid in padres:
        cadena = []
        actual = cid
        while actual is not None and actual not in nivel and actual not in cadena:
            cadena.append(actual)
            actual = padres.get(actual)
        base = nivel.get(actual, 0) if actual is not None else 0
        for paso, nodo in enumerate(reversed(cadena)):
            nivel[nodo] = base + paso + 1
    return nivel


def calcular_saldos_mensuales(
    empresa_id,
    ejercicio,
    condics=CONDICS_MENSUALES,
    sucursal_id=None,
    modulo=None,
    alcance='todas',
    mostrar_sumarizadoras=True,
    omitir_sin_movimiento=True,
):
    """Devuelve la grilla completa del reporte.

    `ejercicio` es obligatorio: el reporte es siempre sobre un ejercicio contable, nunca sobre
    varios ni sobre un rango libre de fechas.

    Estructura devuelta::

        {
          'periodos': [{'clave','label','anio','mes','primer_dia','ultimo_dia'}, ...],
          'filas':    [{'cuenta','nivel','apertura','meses':[Decimal,...],'total'}, ...],
          'totales':  {'apertura','meses':[Decimal,...],'total'},
          'ejercicio', 'condics', 'aviso', ...filtros aplicados
        }

    `filas.meses` tiene siempre el mismo largo y orden que `periodos`.
    """
    if ejercicio is None:
        raise ValueError("El reporte de Saldos Mensuales requiere un ejercicio.")

    periodos = periodos_ejercicio(ejercicio)
    indice_periodo = {p['clave']: i for i, p in enumerate(periodos)}
    condics = _sanear_condics(condics)

    base = {
        'periodos': periodos,
        'ejercicio': ejercicio,
        'condics': condics,
        'sucursal_id': sucursal_id,
        'modulo': modulo,
        'alcance': alcance,
        'mostrar_sumarizadoras': mostrar_sumarizadoras,
        'omitir_sin_movimiento': omitir_sin_movimiento,
        'aviso': '',
    }

    if not condics:
        # Ninguna condición tildada: no se ejecuta la consulta, se avisa y se corta.
        return {
            **base,
            'filas': [],
            'totales': {'apertura': CERO, 'meses': [CERO] * len(periodos), 'total': CERO},
            'aviso': 'Seleccione al menos una condición para ver movimientos.',
        }

    cuentas = list(Cuenta.objects.filter(empresa_id=empresa_id).order_by('jerarquia'))
    nivel = _profundidad(cuentas)

    datos = {
        c.id: {
            'cuenta': c,
            'nivel': nivel.get(c.id, 1),
            'apertura': CERO,
            'meses': [CERO] * len(periodos),
            'total': CERO,
        }
        for c in cuentas
    }

    # --- Consulta 1: movimiento neto por cuenta y mes -----------------------------------------
    # Se filtra por la FK `ejercicio` ADEMÁS del rango de fechas: la FK es la fuente de verdad
    # del período al que pertenece el asiento, y acotar sólo por fechas dejaría entrar asientos
    # de otro ejercicio ante cualquier solapamiento.
    movs = (AsientoLinea.objects
            .filter(
                cuenta__empresa_id=empresa_id,
                asiento__empresa_id=empresa_id,
                asiento__ejercicio=ejercicio,
                asiento__anulado=False,
                asiento__condic__in=condics,
                asiento__fecha__gte=ejercicio.inicio,
                asiento__fecha__lte=ejercicio.cierre,
            ))

    # --- Consulta 2: apertura -----------------------------------------------------------------
    # Universo disjunto del anterior por `condic`: ningún movimiento se computa dos veces ni se
    # pierde. Se acota explícitamente por ejercicio y por el rango de fechas del ejercicio activo.
    apert = (AsientoLinea.objects
             .filter(
                 cuenta__empresa_id=empresa_id,
                 asiento__empresa_id=empresa_id,
                 asiento__ejercicio=ejercicio,
                 asiento__anulado=False,
                 asiento__condic=CONDIC_APERTURA,
                 asiento__fecha__gte=ejercicio.inicio,
                 asiento__fecha__lte=ejercicio.cierre,
             ))

    if sucursal_id:
        movs = movs.filter(asiento__sucursal_id=sucursal_id)
        apert = apert.filter(asiento__sucursal_id=sucursal_id)
    if modulo:
        movs = movs.filter(asiento__modulo=modulo)
        apert = apert.filter(asiento__modulo=modulo)

    movs = (movs
            .annotate(periodo=TruncMonth('asiento__fecha'))
            .values('cuenta_id', 'periodo')
            .annotate(neto=Sum(F('debe') - F('haber'))))

    apert = apert.values('cuenta_id').annotate(neto=Sum(F('debe') - F('haber')))

    for fila in movs:
        destino = datos.get(fila['cuenta_id'])
        if destino is None:
            continue
        periodo = fila['periodo']
        i = indice_periodo.get(f"{periodo.year}{periodo.month:02d}")
        if i is None:
            # Un asiento cuya fecha cae fuera del rango de su propio ejercicio no tiene columna.
            # El sistema no permite registrarlo (crear_asiento deriva el ejercicio desde la fecha
            # y editar_asiento revalida), así que esto no debería ocurrir nunca.
            continue
        destino['meses'][i] += fila['neto'] or CERO

    for fila in apert:
        destino = datos.get(fila['cuenta_id'])
        if destino is not None:
            destino['apertura'] += fila['neto'] or CERO

    # --- Rollup jerárquico --------------------------------------------------------------------
    # Sólo se agregó contra la base por cuentas imputables (las hojas). Las sumarizadoras se
    # completan de abajo hacia arriba, de mayor a menor profundidad, de modo que cuando se
    # procesa un padre sus hijas ya están consolidadas. Es el mismo mecanismo del VFP
    # (`SET ORDER TO jera_cta DESC` + `SUM ... FOR sumariza = m.codigo`).
    for cid in sorted(datos, key=lambda c: datos[c]['nivel'], reverse=True):
        origen = datos[cid]
        padre = datos.get(origen['cuenta'].sumariza_id)
        if padre is None:
            continue
        padre['apertura'] += origen['apertura']
        for i in range(len(periodos)):
            padre['meses'][i] += origen['meses'][i]

    for info in datos.values():
        info['total'] = info['apertura'] + sum(info['meses'], CERO)

    # --- Armado de la grilla ------------------------------------------------------------------
    tipos = TIPOS_POR_ALCANCE.get(alcance)
    filas = []
    total_apertura = CERO
    total_meses = [CERO] * len(periodos)

    for cuenta in cuentas:
        info = datos[cuenta.id]

        # Criterio del VFP: se omite sólo si TODAS las columnas son cero. Se usa el valor
        # absoluto, así que una cuenta que netea cero pero tuvo movimiento se conserva —es
        # justamente la que el operador quiere ver para controlar la carga.
        if omitir_sin_movimiento:
            magnitud = abs(info['apertura']) + abs(info['total']) + sum(
                (abs(m) for m in info['meses']), CERO)
            if magnitud == CERO:
                continue

        if tipos is not None and cuenta.tipo not in tipos:
            continue
        if cuenta.imputable != 1 and not mostrar_sumarizadoras:
            continue

        filas.append(info)

        # Los totales acumulan SÓLO cuentas imputables: sumar también las sumarizadoras contaría
        # cada importe una vez por nivel de la jerarquía.
        if cuenta.imputable == 1:
            total_apertura += info['apertura']
            for i in range(len(periodos)):
                total_meses[i] += info['meses'][i]

    return {
        **base,
        'filas': filas,
        'totales': {
            'apertura': total_apertura,
            'meses': total_meses,
            'total': total_apertura + sum(total_meses, CERO),
        },
    }
