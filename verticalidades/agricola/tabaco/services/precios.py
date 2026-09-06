"""Formación del precio del tabaco (Plan 081).

    precio_unitario = REDONDEO(precio_ponderante × coeficiente_de_clase, 2)
    importe         = REDONDEO(precio_unitario × kilos, 2)

Ambas fórmulas se validaron contra 132 registros reales del sistema heredado (marzo 2024,
Burley, ponderante 2.500): 132/132 exactas.

POR QUÉ ESTÁ ACÁ Y NO EN EL MODELO
El precio depende de la lista VIGENTE Y APROBADA a una fecha, que es una decisión de aplicación,
no un atributo de la clase. Y porque el romaneo tiene que poder pedir el precio ANTES de existir,
mientras el operador carga fardos en pantalla.

EL REDONDEO ES A DOS DECIMALES Y ES DELIBERADO
El coeficiente tiene cuatro decimales, pero el precio unitario que se le informa al productor y
que se imprime en la liquidación tiene dos. Si se redondeara recién en el importe final, el
precio impreso no multiplicaría exacto por los kilos y el productor no podría verificar su
propia liquidación con una calculadora. Se redondea el precio, y el importe sale de ese precio
redondeado.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Q
from django.utils import timezone

from verticalidades.agricola.tabaco.models import ListaPrecioTabaco

DOS_DECIMALES = Decimal('0.01')


def _redondear(valor):
    return Decimal(valor).quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


def lista_vigente(empresa_id, variedad, campania, fecha=None):
    """Lista de precio aprobada y vigente a `fecha` para esa variedad y campaña.

    Devuelve `None` si no hay ninguna. Es un caso normal, no un error: al abrir una campaña
    todavía no se negoció el ponderante, y la pantalla tiene que poder decirlo.

    Si hubiera más de una vigente —no debería, pero el maestro lo permite mientras se corrige
    una lista mal cargada— gana la de `vigencia_desde` más reciente.
    """
    fecha = fecha or timezone.now().date()

    # `vigencia_hasta` nula significa "sin fecha de corte", no "vencida".
    return (ListaPrecioTabaco.objects
            .filter(empresa_id=empresa_id, variedad=variedad, campania=campania,
                    aprobada=True, vigencia_desde__lte=fecha)
            .filter(Q(vigencia_hasta__isnull=True) | Q(vigencia_hasta__gte=fecha))
            .order_by('-vigencia_desde', '-id')
            .first())


def precio_de_clase(lista, clase):
    """`REDONDEO(ponderante × coeficiente, 2)`.

    No valida que la clase pertenezca a la variedad de la lista: de eso se encarga el modelo del
    romaneo, que es quien tiene el contexto para dar un mensaje útil.
    """
    return _redondear(Decimal(lista.precio_ponderante) * Decimal(clase.coeficiente))


def importe_de_linea(precio_unitario, kilos):
    """`REDONDEO(precio × kilos, 2)`, sobre el precio YA redondeado."""
    return _redondear(Decimal(precio_unitario) * Decimal(kilos))


def cotizar(empresa_id, variedad, campania, clase, kilos, fecha=None):
    """Atajo para la pantalla de carga: devuelve `(lista, precio_unitario, importe)`.

    Con `(None, None, None)` cuando no hay lista aprobada vigente.
    """
    lista = lista_vigente(empresa_id, variedad, campania, fecha)
    if lista is None:
        return None, None, None

    precio = precio_de_clase(lista, clase)
    return lista, precio, importe_de_linea(precio, kilos)
