"""Núcleo de los reportes de MOVIMIENTOS DE FONDOS (Plan 050, fase 1).

Acá vive la lógica que comparten la **Caja Diaria** (`caja_diaria.py`, por sesión de caja) y el
**Estado de Origen y Aplicación de Fondos** (por rango de fechas). Las dos hacen la misma
descomposición y solo difieren en qué asientos miran.

QUÉ ES UN MOVIMIENTO DE FONDOS
------------------------------
Todo asiento que toca al menos una cuenta con `tipo_disponibilidad` (efectivo, dólares, valores,
banco, tarjetas, otros). Dentro de ese asiento:

- las líneas **de disponibilidad** son el BOLSILLO: dicen por qué medio se movió la plata;
- las líneas **de contrapartida** (`tipo_disponibilidad` vacío) dicen DE DÓNDE vino o A DÓNDE fue.

La contrapartida al HABER es un **origen** de fondos (una cobranza deja al cliente en el haber);
al DEBE es una **aplicación** (un pago deja al proveedor en el debe).

Un asiento cuyas dos puntas son de disponibilidad —un retiro de caja mostrador a tesorería, un
depósito bancario— no tiene contrapartida: no es ni origen ni aplicación, es plata cambiando de
bolsillo. Se emite igual como una fila con `cuenta_id = None`, porque la Caja Diaria necesita
mostrarlo en el cuaderno del tesorero; el EOAF, que mide orígenes y aplicaciones, las descarta.
"""

from decimal import Decimal

CERO = Decimal('0.00')

# Tipos que arrastran saldo de un día al siguiente.
TIPOS_CON_SALDO = ('EFE', 'DOL', 'VAL')
# Tipos que solo informan el movimiento neto del período.
TIPOS_SIN_SALDO = ('BCO', 'TAR', 'OTR')
TIPOS_DISPONIBILIDAD = TIPOS_CON_SALDO + TIPOS_SIN_SALDO


def fila_vacia():
    return {t: CERO for t in TIPOS_DISPONIBILIDAD}


def cuantizar(valor):
    return Decimal(valor).quantize(Decimal('0.01'))


def prorratear(netos, items):
    """Reparte el desglose por medio entre varias contrapartidas, según su peso.

    `items` es una lista de `(objeto, peso)`. Devuelve `[(objeto, parte), ...]`, donde cada
    `parte` es un dict por tipo de disponibilidad.

    **La última contrapartida absorbe el residuo del redondeo**, de modo que la suma de las partes
    reproduzca exactamente el neto del asiento y no se pierdan centavos. Con una sola
    contrapartida se le asigna el neto completo, sin dividir.

    Devuelve **lista vacía** cuando no hay items o cuando los pesos suman cero: en ese caso no hay
    contrapartida identificable y es quien llama el que decide qué hacer (emitir una fila suelta,
    descartar el asiento). No se reparte por partes iguales ni se asigna al primero, porque un
    reparto arbitrario imputaría fondos a una cuenta que no los movió.
    """
    if not items:
        return []

    suma_pesos = sum((p for _, p in items), CERO)
    if suma_pesos == CERO:
        return []

    if len(items) == 1:
        return [(items[0][0], dict(netos))]

    repartos = []
    acumulado = fila_vacia()
    ultimo = len(items) - 1
    for indice, (objeto, peso) in enumerate(items):
        if indice == ultimo:
            parte = {t: netos[t] - acumulado[t] for t in TIPOS_DISPONIBILIDAD}
        else:
            factor = peso / suma_pesos
            parte = {t: cuantizar(netos[t] * factor) for t in TIPOS_DISPONIBILIDAD}
            for t in TIPOS_DISPONIBILIDAD:
                acumulado[t] += parte[t]
        repartos.append((objeto, parte))
    return repartos


def asientos_de_fondos_por_fecha(empresa_id, desde, hasta, condics):
    """Queryset de asientos que pueden mover fondos, en un rango de fechas. Lo usa el EOAF.

    La Caja Diaria tiene su propio armador (`caja_diaria.asientos_de_fondos`), que filtra por
    sesión de caja en vez de por fecha.
    """
    from contable.models import Asiento

    return (
        Asiento.objects
        .filter(empresa_id=empresa_id, anulado=False,
                fecha__gte=desde, fecha__lte=hasta,
                condic__in=condics)
        .select_related('cli_pro')
        .prefetch_related('lineas__cuenta', 'lineas__cli_pro')
        .order_by('fecha', 'asiento_id')
    )


def lineas_de_fondos(asientos):
    """Descompone asientos que mueven fondos en una fila por contrapartida.

    `asientos` es un queryset YA filtrado por quien llama (por sesión de caja, por rango de
    fechas, por empresa...). Debe traer `lineas__cuenta` y `lineas__cli_pro` precargados.

    Devuelve `(filas, ids_de_asientos_procesados)`. Cada fila lleva el desglose por medio en
    `parte` y, en `cuenta_id`, la contrapartida —o `None` si el asiento no tiene ninguna—.
    """
    filas = []
    procesados = set()

    for asiento in asientos:
        lineas = list(asiento.lineas.all())
        disponibilidades = [l for l in lineas if l.cuenta.tipo_disponibilidad]
        contrapartidas = [l for l in lineas if not l.cuenta.tipo_disponibilidad]

        # Un asiento sin disponibilidades no es un movimiento de fondos: no va al reporte.
        if not disponibilidades:
            continue

        # Neto por tipo. Signo: positivo = entra a la caja (debe), negativo = sale (haber).
        netos = fila_vacia()
        for linea in disponibilidades:
            netos[linea.cuenta.tipo_disponibilidad] += (linea.debe - linea.haber)

        # Peso de cada contrapartida, con el mismo signo que el neto de disponibilidades: un
        # cobro deja la contrapartida en el HABER, un pago la deja en el DEBE.
        pesos = [(l, l.haber - l.debe) for l in contrapartidas]
        repartos = prorratear(netos, pesos) or [(None, netos)]

        procesados.add(asiento.asiento_id)

        for linea_cp, parte in repartos:
            cuenta_cp = linea_cp.cuenta if linea_cp is not None else None
            entidad = (linea_cp.cli_pro if linea_cp is not None and linea_cp.cli_pro
                       else asiento.cli_pro)

            filas.append({
                'orden': (asiento.fecha, asiento.asiento_id),
                'asiento_id': asiento.asiento_id,
                'fecha': asiento.fecha,
                'codigo': entidad.codigo_id if entidad else '',
                'razon': entidad.razon_social if entidad else '',
                'cuenta_id': cuenta_cp.id if cuenta_cp else None,
                'jerarquia': cuenta_cp.jerarquia if cuenta_cp else '',
                'cuenta': cuenta_cp.cuenta if cuenta_cp else 'SIN CONTRAPARTIDA',
                'descripcion': (linea_cp.leyenda if linea_cp is not None and linea_cp.leyenda
                                else asiento.concepto),
                'condic': asiento.condic,
                'parte': parte,
            })

    return filas, procesados
