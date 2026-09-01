"""Estado de Origen y Aplicación de Fondos — vistas (Plan 050, fase 3 y 4).

Migra el formulario VFP `suma_saldo_fciero` (C-207). La grilla no se autoejecuta: el usuario fija
el período y la condición y presiona **Generar**, igual que el botón `cmdGenerar` del legado y que
el criterio adoptado en el Libro Mayor (Plan 048).
"""

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render

from contable.models import Cuenta
from empresas.models import Ejercicio
from tesoreria.services.eoaf import (
    CONDIC_FONDOS,
    detalle_de_cuenta,
    estado_origen_aplicacion_fondos,
)
from tesoreria.services.fondos import TIPOS_DISPONIBILIDAD

# Rótulos de los medios, en el orden en que se muestran las columnas.
MEDIOS = [
    ('EFE', 'Efectivo'),
    ('DOL', 'Dólares'),
    ('VAL', 'Valores'),
    ('BCO', 'Banco'),
    ('TAR', 'Tarjetas'),
    ('OTR', 'Otros'),
]

# Opciones del filtro por medio en el drill-down: el option-group `opgMoneda` del formulario
# legado (Todos / Efectivo / Banco / Valores), extendido a los seis tipos que sí manejamos.
FILTROS_MEDIO = [('', 'Todos')] + MEDIOS


from tesoreria.permisos import bloquear_cajero

def _con_medios_en_orden(filas):
    """Aplana el dict `medios` a una lista en el orden de `MEDIOS`.

    Los templates de Django no saben indexar un dict por una clave variable, y agregar un filtro
    sólo para eso sería peor: se resuelve acá y el template itera una lista.
    """
    for fila in filas:
        fila['medios_lista'] = [fila['medios'][clave] for clave, _ in MEDIOS]
    return filas


def _periodo(request, empresa_id):
    """Rango de fechas pedido, con el ejercicio vigente como valor por defecto."""
    desde_raw = request.GET.get('desde') or ''
    hasta_raw = request.GET.get('hasta') or ''

    def parsear(texto):
        try:
            return date.fromisoformat(texto)
        except (TypeError, ValueError):
            return None

    desde, hasta = parsear(desde_raw), parsear(hasta_raw)

    if not desde or not hasta:
        ejercicio = (
            Ejercicio.objects.filter(empresa_id=empresa_id).order_by('-inicio').first()
        )
        if ejercicio:
            desde = desde or ejercicio.inicio
            hasta = hasta or min(ejercicio.cierre, date.today())
        else:
            hoy = date.today()
            desde = desde or hoy.replace(day=1)
            hasta = hasta or hoy

    if desde > hasta:
        desde, hasta = hasta, desde
    return desde, hasta


def _condics(request):
    """Condiciones tildadas.

    Un checkbox sin tildar no se envía, así que "las dos destildadas" llega igual que "primera
    carga": sin ningún `condic` en la URL. El formulario manda un campo oculto `generado` para
    distinguir los dos casos; sin él la grilla mostraría todo contradiciendo a los checkboxes, y
    el usuario terminaría desconfiando de los totales.
    """
    elegidas = tuple(int(v) for v in request.GET.getlist('condic') if v in ('1', '2'))
    if elegidas:
        return elegidas
    # Primera carga (nadie tocó el formulario): van las dos, como el legado.
    return () if 'generado' in request.GET else CONDIC_FONDOS


def _contexto_base(request):
    empresa_id = request.session.get('empresa_id')
    if not empresa_id:
        return None

    desde, hasta = _periodo(request, empresa_id)
    condics = _condics(request)

    return {
        'empresa_id': empresa_id,
        'desde': desde,
        'hasta': hasta,
        'condics': condics,
        'medios': MEDIOS,
    }


@login_required
@bloquear_cajero
def eoaf_index(request):
    """Pantalla del reporte. NO ejecuta la consulta: espera el botón Generar."""
    contexto = _contexto_base(request)
    if contexto is None:
        messages.warning(
            request,
            "Seleccione una empresa para consultar el Estado de Origen y Aplicación de Fondos.")
        return redirect('seleccion_empresa')
    return render(request, 'tesoreria/eoaf.html', contexto)


@login_required
def eoaf_grilla(request):
    """Refresco HTMX de la grilla. Es lo que dispara el botón Generar."""
    contexto = _contexto_base(request)
    if contexto is None:
        return HttpResponse(
            "<div class='p-6 text-sm text-red-600'>Seleccione una empresa.</div>")

    datos = estado_origen_aplicacion_fondos(
        contexto['empresa_id'], contexto['desde'], contexto['hasta'], contexto['condics'])

    contexto.update({
        'filas': _con_medios_en_orden(datos['filas']),
        'totales': _con_medios_en_orden([datos['totales']])[0],
    })
    return render(request, 'tesoreria/partials/eoaf_grilla.html', contexto)


@login_required
def eoaf_cuenta_modal(request, cuenta_id):
    """Drill-down: movimientos de fondos de una cuenta (vista `cons_caja_diaria_cta` del legado)."""
    contexto = _contexto_base(request)
    if contexto is None:
        return HttpResponse(
            "<div class='p-6 text-sm text-red-600'>Seleccione una empresa.</div>")

    cuenta = Cuenta.objects.filter(pk=cuenta_id, empresa_id=contexto['empresa_id']).first()
    if not cuenta:
        return HttpResponse(
            "<div class='p-6 text-sm text-red-600'>La cuenta no pertenece a la empresa activa.</div>")

    medio = request.GET.get('medio') or ''
    if medio not in TIPOS_DISPONIBILIDAD:
        medio = ''

    datos = detalle_de_cuenta(
        contexto['empresa_id'], contexto['desde'], contexto['hasta'],
        cuenta.id, contexto['condics'], medio=medio or None)

    contexto.update({
        'cuenta': cuenta,
        'medio': medio,
        'filtros_medio': FILTROS_MEDIO,
        'filas': _con_medios_en_orden(datos['filas']),
        'totales': _con_medios_en_orden([datos['totales']])[0],
    })
    return render(request, 'tesoreria/modals/eoaf_cuenta_modal.html', contexto)


def _datos_para_exportar(request):
    """Recalcula el reporte con los mismos filtros que la grilla. Devuelve `(datos, error)`."""
    contexto = _contexto_base(request)
    if contexto is None:
        return None, HttpResponse("Seleccione una empresa.", status=400)

    datos = estado_origen_aplicacion_fondos(
        contexto['empresa_id'], contexto['desde'], contexto['hasta'], contexto['condics'])
    return datos, None


@login_required
def eoaf_excel(request):
    datos, error = _datos_para_exportar(request)
    if error:
        return error
    from tesoreria.services.eoaf_export import exportar_eoaf_excel
    return exportar_eoaf_excel(datos, MEDIOS)


@login_required
def eoaf_pdf(request):
    datos, error = _datos_para_exportar(request)
    if error:
        return error
    from tesoreria.services.eoaf_export import exportar_eoaf_pdf
    return exportar_eoaf_pdf(datos, MEDIOS)
