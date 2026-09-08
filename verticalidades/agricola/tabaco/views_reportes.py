"""Pantallas de los reportes del acopio (Plan 087 — Etapa 6).

Las vistas arman el filtro, delegan en los servicios y renderizan. La misma función alimenta la
pantalla, la grilla HTMX y la exportación: si el CSV se armara por otro camino, tarde o temprano
diría algo distinto de lo que el usuario vio en pantalla.

REGLA INFLEXIBLE: todo queryset se acota por `session['empresa_id']`.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from .forms_reportes import (FiltroAcopioForm, FiltroExistenciasForm, FiltroFETForm,
                             FiltroRetencionesForm, FiltroTableroForm)
from .services import exportaciones as exp
from .services import reportes as rep
from .services import retenciones_libro as libro_svc
from .services import tableros as tab_svc


def _empresa(request):
    return request.session.get('empresa_id')


@login_required
def reportes_index(request):
    """Portada del módulo de reportes: qué hay y para qué sirve cada uno."""
    return render(request, 'agricola/reportes/index.html')


# ---------------------------------------------------------------------------
# Planilla FET
# ---------------------------------------------------------------------------

ENCABEZADOS_FET = ['Romaneo', 'Asiento', 'Letra', 'Punto', 'Número', 'Fecha', 'Cód. FET',
                   'Productor', 'CUIT', 'Variedad', 'Campaña', 'Fardos', 'Kilos', 'Importe',
                   'Adicional', 'IVA', 'Ret. IVA', 'Ret. Ganancias', 'EEAOC', 'Salud Pública',
                   'Uso de Agua', 'Otras ret.', 'A pagar', 'Ponderante']

# Índices 0-based de las columnas numéricas y de fecha, para el formato de celda del XLSX.
IMPORTES_FET = tuple(range(12, 24))
FECHAS_FET = (5,)


def _filas_fet(request, filtros):
    return rep.planilla_fet(
        _empresa(request),
        desde=filtros.valor('desde'), hasta=filtros.valor('hasta'),
        campania_id=filtros.pk_de('campania'), variedad_id=filtros.pk_de('variedad'),
        productor_id=filtros.pk_de('productor'), condic=filtros.condic())


@login_required
def fet(request):
    filtros = FiltroFETForm(_empresa(request), request.GET or None)
    filas = _filas_fet(request, filtros)
    return render(request, 'agricola/reportes/fet.html', {
        'filtros': filtros, 'filas': filas, 'totales': rep.totales_fet(filas)})


@login_required
def fet_grilla(request):
    filtros = FiltroFETForm(_empresa(request), request.GET or None)
    filas = _filas_fet(request, filtros)
    return render(request, 'agricola/reportes/fet_filas.html',
                  {'filas': filas, 'totales': rep.totales_fet(filas)})


def _tupla_fet(f):
    return [f['id_romaneo'], f['asiento'], f['letra'], f['punto'], f['numero'], f['fecha'],
            f['codigo_fet'], f['productor'], f['cuit'], f['variedad'], f['campania'],
            f['fardos'], f['kilos'], f['importe'], f['adicional'], f['iva'], f['ret_iva'],
            f['ret_ganancias'], f['ret_eeaoc'], f['ret_salud'], f['ret_agua'],
            f['otras_retenciones'], f['a_pagar'], f['ponderante']]


@login_required
def fet_csv(request):
    filtros = FiltroFETForm(_empresa(request), request.GET or None)
    filas = [_tupla_fet(f) for f in _filas_fet(request, filtros)]
    return exp.csv_response('planilla_fet', ENCABEZADOS_FET, filas)


@login_required
def fet_xlsx(request):
    """El VFP entregaba Excel y el organismo lo espera así."""
    filtros = FiltroFETForm(_empresa(request), request.GET or None)
    crudas = _filas_fet(request, filtros)
    totales = rep.totales_fet(crudas)

    fila_totales = ['TOTALES', '', '', '', '', '', '', '', '', '', '',
                    totales['fardos'], totales['kilos'], totales['importe'],
                    totales['adicional'], totales['iva'], totales['ret_iva'],
                    totales['ret_ganancias'], totales['ret_eeaoc'], totales['ret_salud'],
                    totales['ret_agua'], totales['otras_retenciones'], totales['a_pagar'], '']

    return exp.xlsx_response('planilla_fet', 'Planilla FET', ENCABEZADOS_FET,
                             [_tupla_fet(f) for f in crudas],
                             columnas_importe=IMPORTES_FET, columnas_fecha=FECHAS_FET,
                             totales=fila_totales)


# ---------------------------------------------------------------------------
# Resumen de acopio
# ---------------------------------------------------------------------------

def _resumen(request, filtros):
    return rep.resumen_de_acopio(
        _empresa(request),
        desde=filtros.valor('desde'), hasta=filtros.valor('hasta'),
        campania_id=filtros.pk_de('campania'), variedad_id=filtros.pk_de('variedad'),
        sucursal_id=filtros.pk_de('sucursal'), condic=filtros.condic())


@login_required
def acopio(request):
    filtros = FiltroAcopioForm(_empresa(request), request.GET or None)
    variedades = _resumen(request, filtros)
    return render(request, 'agricola/reportes/acopio.html', {
        'filtros': filtros, 'variedades': variedades, 'totales': _totales_acopio(variedades)})


@login_required
def acopio_grilla(request):
    filtros = FiltroAcopioForm(_empresa(request), request.GET or None)
    variedades = _resumen(request, filtros)
    return render(request, 'agricola/reportes/acopio_filas.html',
                  {'variedades': variedades, 'totales': _totales_acopio(variedades)})


def _totales_acopio(variedades):
    from decimal import Decimal
    total = {'fardos': 0, 'kilos': Decimal('0.00'), 'importe': Decimal('0.00')}
    for variedad in variedades:
        total['fardos'] += variedad['fardos']
        total['kilos'] += variedad['kilos']
        total['importe'] += variedad['importe']
    total['precio_promedio'] = (
        (total['importe'] / total['kilos']).quantize(Decimal('0.01')) if total['kilos']
        else Decimal('0.00'))
    return total


@login_required
def acopio_csv(request):
    filtros = FiltroAcopioForm(_empresa(request), request.GET or None)
    encabezados = ['Variedad', 'Grupo', 'Código', 'Clase', 'Fardos', 'Kilos', 'Importe',
                   'Precio promedio']
    filas = []
    for variedad in _resumen(request, filtros):
        for clase in variedad['clases']:
            filas.append([variedad['variedad'], clase['grupo'], clase['codigo'], clase['clase'],
                          clase['fardos'], clase['kilos'], clase['importe'],
                          clase['precio_promedio']])
        filas.append([variedad['variedad'], '', '', 'SUBTOTAL', variedad['fardos'],
                      variedad['kilos'], variedad['importe'], variedad['precio_promedio']])
    return exp.csv_response('resumen_acopio', encabezados, filas)


# ---------------------------------------------------------------------------
# DDJJ de existencias
# ---------------------------------------------------------------------------

def _existencias(request, filtros):
    fecha = filtros.valor('fecha')
    if not fecha:
        return [], None
    return rep.existencias_a_fecha(
        _empresa(request), fecha,
        sucursal_id=filtros.pk_de('sucursal'), variedad_id=filtros.pk_de('variedad'),
        condic=filtros.condic()), fecha


@login_required
def existencias(request):
    filtros = FiltroExistenciasForm(
        _empresa(request), request.GET or {'fecha': timezone.localdate().isoformat(),
                                           'condic': '1'})
    filas, fecha = _existencias(request, filtros)
    return render(request, 'agricola/reportes/existencias.html', {
        'filtros': filtros, 'filas': filas, 'fecha': fecha,
        'totales': rep.totales_existencias(filas)})


@login_required
def existencias_grilla(request):
    filtros = FiltroExistenciasForm(_empresa(request), request.GET or None)
    filas, fecha = _existencias(request, filtros)
    return render(request, 'agricola/reportes/existencias_filas.html', {
        'filas': filas, 'fecha': fecha, 'totales': rep.totales_existencias(filas)})


@login_required
def existencias_csv(request):
    filtros = FiltroExistenciasForm(_empresa(request), request.GET or None)
    filas, _fecha = _existencias(request, filtros)
    encabezados = ['Variedad', 'Galpón', 'Fardos', 'Recibidos', 'Acondicionados', 'Vendidos',
                   'Existencia']
    datos = [[f['variedad'].detalle, f['sucursal'].nombre, f['fardos'], f['recibidos'],
              f['acondicionados'], f['vendidos'], f['existencia']] for f in filas]
    return exp.csv_response('ddjj_existencias', encabezados, datos)


# ---------------------------------------------------------------------------
# Libro de retenciones
# ---------------------------------------------------------------------------

def _libro(request, filtros):
    return libro_svc.libro(
        _empresa(request),
        desde=filtros.valor('desde'), hasta=filtros.valor('hasta'),
        codigo=filtros.valor('codigo'), productor_id=filtros.pk_de('productor'),
        condic=filtros.condic())


@login_required
def retenciones(request):
    filtros = FiltroRetencionesForm(_empresa(request), request.GET or None)
    filas = _libro(request, filtros)
    return render(request, 'agricola/reportes/retenciones.html', {
        'filtros': filtros, 'filas': filas,
        'por_organismo': libro_svc.totales_por_organismo(filas),
        'total': libro_svc.total_general(filas)})


@login_required
def retenciones_grilla(request):
    filtros = FiltroRetencionesForm(_empresa(request), request.GET or None)
    filas = _libro(request, filtros)
    return render(request, 'agricola/reportes/retenciones_filas.html', {
        'filas': filas, 'por_organismo': libro_svc.totales_por_organismo(filas),
        'total': libro_svc.total_general(filas)})


@login_required
def retenciones_csv(request):
    filtros = FiltroRetencionesForm(_empresa(request), request.GET or None)
    encabezados = ['Fecha', 'Período', 'Origen', 'Comprobante', 'Productor', 'CUIT', 'Código',
                   'Concepto', 'Organismo', 'Régimen', 'Base', 'Alícuota', 'Importe',
                   'Certificado', 'Cuenta']
    filas = [[f['fecha'], f['periodo'], f['origen_display'], f['comprobante'], f['productor'],
              f['cuit'], f['codigo'], f['detalle'], f['organismo'], f['regimen'], f['base'],
              f['alicuota'], f['importe'], f['certificado'], f['cuenta']]
             for f in _libro(request, filtros)]
    return exp.csv_response('libro_retenciones', encabezados, filas)


# ---------------------------------------------------------------------------
# Tableros de margen
# ---------------------------------------------------------------------------

_TABLEROS = {
    'campania': (tab_svc.por_campania, 'Campaña'),
    'variedad': (tab_svc.por_variedad, 'Variedad'),
    'productor': (tab_svc.por_productor, 'Productor'),
    'clase': (tab_svc.por_clase, 'Clase'),
}


def _tablero(request, filtros):
    agrupacion = filtros.agrupacion()
    funcion, rotulo = _TABLEROS[agrupacion]
    filas = funcion(
        _empresa(request),
        campania_id=filtros.pk_de('campania'), variedad_id=filtros.pk_de('variedad'),
        sucursal_id=filtros.pk_de('sucursal'), condic=filtros.condic(),
        solo_vendidos=bool(filtros.valor('solo_vendidos')))
    return filas, rotulo, agrupacion


@login_required
def tablero(request):
    filtros = FiltroTableroForm(_empresa(request), request.GET or None)
    filas, rotulo, agrupacion = _tablero(request, filtros)
    return render(request, 'agricola/reportes/tablero.html', {
        'filtros': filtros, 'filas': filas, 'rotulo': rotulo, 'agrupacion': agrupacion,
        'totales': tab_svc.totales(filas)})


@login_required
def tablero_grilla(request):
    filtros = FiltroTableroForm(_empresa(request), request.GET or None)
    filas, rotulo, agrupacion = _tablero(request, filtros)
    return render(request, 'agricola/reportes/tablero_filas.html', {
        'filas': filas, 'rotulo': rotulo, 'agrupacion': agrupacion,
        'totales': tab_svc.totales(filas)})


@login_required
def tablero_csv(request):
    filtros = FiltroTableroForm(_empresa(request), request.GET or None)
    filas, rotulo, _agrupacion = _tablero(request, filtros)
    encabezados = [rotulo, 'Lotes', 'Fardos', 'Kilos', 'Costo de compra', 'Acondicionamiento',
                   'Costo total', '$/kg', 'Ingreso', 'Margen', '%']
    datos = [[f['rotulo'], f['lotes'], f['fardos'], f['kilos'], f['costo_compra'],
              f['costo_acondicionamiento'], f['costo_total'], f['costo_por_kilo'],
              f['ingreso'], f['margen'], f['margen_porcentaje']] for f in filas]
    return exp.csv_response('tablero_margen', encabezados, datos)
