import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Any, List
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError

from .models import PeriodoIva, ArcaMisComprobantes
from contable.models import LibroIvaCompras, LibroIvaVentas
from facturacion.models import Compra, Venta


def es_periodo_cerrado(empresa_id: int, periodo_yyyymm: str) -> bool:
    """
    Indica si un período fiscal (YYYYMM, ej: '202605') se encuentra cerrado para la empresa especificada.
    """
    if not periodo_yyyymm:
        return False
    return PeriodoIva.objects.filter(
        empresa_id=empresa_id,
        periodo=periodo_yyyymm,
        estado='CERRADO'
    ).exists()


def obtener_primer_periodo_vigente_compra(empresa_id: int, fecha_comprobante: date) -> str:
    """
    Calcula el período IVA (YYYYMM) asignable a una factura de compra.
    
    Regla de negocio:
    1. Predeterminado: Año y Mes (YYYYMM) de la fecha de la factura.
    2. Si el período de la fecha de la factura está ABIERTO, se asigna dicho YYYYMM.
    3. Si el período de la fecha de la factura está CERRADO (ej: factura de mayo 2026 '202605' 
       y los períodos 202601 a 202607 ya fueron cerrados por vencimiento de DDJJ IVA), 
       el sistema busca automáticamente el primer período Abierto / Vigente que sea >= YYYYMM (ej: '202608').
    """
    if not fecha_comprobante:
        fecha_comprobante = timezone.localdate()

    year = fecha_comprobante.year
    month = fecha_comprobante.month
    yyyymm = f"{year}{month:02d}"

    # Si no está cerrado, el período es exactamente el de la fecha de la factura
    if not es_periodo_cerrado(empresa_id, yyyymm):
        return yyyymm

    # Si está cerrado, avanzamos mes a mes hasta encontrar el primer período Abierto (vigente)
    current_year = year
    current_month = month
    
    # Límite preventivo de búsqueda (hasta 36 meses a futuro)
    for _ in range(36):
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1
        
        candidato = f"{current_year}{current_month:02d}"
        if not es_periodo_cerrado(empresa_id, candidato):
            return candidato

    return yyyymm


def calcular_liquidacion_iva(empresa_id: int, anio: int, mes: int) -> Dict[str, Any]:
    """
    Calcula la liquidación de IVA para la empresa en el período anio/mes.
    Débito Fiscal = Suma IVA de Ventas (condic 1 ó 3) en el período.
    Crédito Fiscal = Suma IVA de Compras (condic 1 ó 3) en el período.
    """
    periodo_yyyymm = f"{anio}{mes:02d}"

    # Ventas del período (Débito Fiscal)
    ventas_periodo = Venta.objects.filter(
        empresa_id=empresa_id,
        periodo=periodo_yyyymm,
        estado=0,  # Activa
        condic__in=[1, 3]  # Fiscales
    )
    debito_fiscal = sum((v.iva for v in ventas_periodo), Decimal('0.00'))

    # Compras del período (Crédito Fiscal)
    compras_periodo = Compra.objects.filter(
        empresa_id=empresa_id,
        periodo=periodo_yyyymm,
        condic__in=[1, 3]  # Fiscales
    )
    credito_fiscal = sum((c.iva for c in compras_periodo), Decimal('0.00'))

    saldo_resultante = debito_fiscal - credito_fiscal
    periodo_obj = PeriodoIva.objects.filter(empresa_id=empresa_id, periodo=periodo_yyyymm).first()
    esta_cerrado = periodo_obj is not None and periodo_obj.estado == 'CERRADO'

    return {
        'periodo': periodo_yyyymm,
        'anio': anio,
        'mes': mes,
        'debito_fiscal': debito_fiscal,
        'credito_fiscal': credito_fiscal,
        'saldo_resultante': saldo_resultante,
        'esta_cerrado': esta_cerrado,
        'periodo_obj': periodo_obj,
        'total_ventas_cant': ventas_periodo.count(),
        'total_compras_cant': compras_periodo.count(),
    }


@transaction.atomic
def cerrar_periodo_iva(empresa_id: int, anio: int, mes: int, usuario) -> PeriodoIva:
    """
    Registra el cierre definitivo del Período IVA para la empresa.
    """
    liq = calcular_liquidacion_iva(empresa_id, anio, mes)
    periodo_yyyymm = liq['periodo']

    periodo_obj, created = PeriodoIva.objects.get_or_create(
        empresa_id=empresa_id,
        periodo=periodo_yyyymm,
        defaults={
            'estado': 'CERRADO',
            'usuario_cierre': usuario,
            'debito_fiscal': liq['debito_fiscal'],
            'credito_fiscal': liq['credito_fiscal'],
            'saldo_resultante': liq['saldo_resultante'],
        }
    )

    if not created:
        periodo_obj.estado = 'CERRADO'
        periodo_obj.usuario_cierre = usuario
        periodo_obj.fecha_cierre = timezone.now()
        periodo_obj.debito_fiscal = liq['debito_fiscal']
        periodo_obj.credito_fiscal = liq['credito_fiscal']
        periodo_obj.saldo_resultante = liq['saldo_resultante']
        periodo_obj.save()

    return periodo_obj


@transaction.atomic
def reabrir_periodo_iva(empresa_id: int, periodo_yyyymm: str, usuario) -> PeriodoIva:
    """
    Reabre un período IVA previamente cerrado para la empresa especificada.
    """
    periodo_obj = PeriodoIva.objects.filter(empresa_id=empresa_id, periodo=periodo_yyyymm).first()
    if not periodo_obj:
        raise ValidationError(f"No se encontró el registro del período {periodo_yyyymm}.")

    periodo_obj.estado = 'ABIERTO'
    periodo_obj.usuario_reapertura = usuario
    periodo_obj.fecha_reapertura = timezone.now()
    periodo_obj.save()

    return periodo_obj


def obtener_periodos_cerrados(empresa_id: int):
    """
    Retorna la lista de períodos IVA cerrados de la empresa ordenados descendentemente.
    """
    return PeriodoIva.objects.filter(
        empresa_id=empresa_id,
        estado='CERRADO'
    ).select_related('usuario_cierre').order_by('-periodo')


# =========================================================================
# MOTOR DE CAPTURA Y CONCILIACIÓN ARCA vs LIBRO IVA
# =========================================================================

def _parse_decimal(val) -> Decimal:
    """Parsea importes numéricos formateados en planillas ARCA (ej: '1.234,56' o '1234.56')."""
    if not val:
        return Decimal('0.00')
    s = str(val).strip()
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return Decimal(s).quantize(Decimal('0.01'))
    except Exception:
        return Decimal('0.00')


def _extraer_codiva(tipo_str) -> str:
    """Extrae el código numérico de 3 dígitos del tipo de comprobante de ARCA (ej: '1 - Factura A' -> '001')."""
    if not tipo_str:
        return '001'
    match = re.search(r'^\s*(\d+)', str(tipo_str))
    if match:
        num = int(match.group(1))
        return f"{num:03d}"
    return '001'


@transaction.atomic
def importar_archivo_mis_comprobantes_arca(empresa_id: int, origen: str, archivo, usuario) -> Dict[str, Any]:
    """
    Importa comprobantes desde una planilla CSV o Excel exportada de AFIP/ARCA
    y actualiza o crea las filas en ArcaMisComprobantes.
    origen: 'C' (Compras/Recibidos) | 'V' (Ventas/Emitidos)
    """
    content = archivo.read()
    filas = []

    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = content.decode('latin-1')

    sample = text[:2000]
    delimiter = ';' if ';' in sample else ','
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)

    headers = None
    for raw_row in reader:
        if not raw_row or not any(raw_row):
            continue
        row_str = ' '.join(str(c).lower() for c in raw_row)
        if ('fecha' in row_str) and ('número' in row_str or 'numero' in row_str or 'comprobante' in row_str or 'cuit' in row_str):
            headers = [str(c).strip().lower() for c in raw_row]
            continue

        if not headers:
            continue

        row_dict = {}
        for idx, val in enumerate(raw_row):
            if idx < len(headers):
                row_dict[headers[idx]] = str(val).strip()

        fecha_val = None
        fecha_str = row_dict.get('fecha', '')
        for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
            try:
                fecha_val = datetime.strptime(fecha_str, fmt).date()
                break
            except Exception:
                pass

        if not fecha_val:
            continue

        tipo_str = row_dict.get('tipo', '') or row_dict.get('tipo comprobante', '')
        codiva = _extraer_codiva(tipo_str)
        punto = int(re.sub(r'\D', '', row_dict.get('punto de venta', '0')) or '0')
        numero = int(re.sub(r'\D', '', row_dict.get('número desde', '') or row_dict.get('numero desde', '') or row_dict.get('número', '') or row_dict.get('numero', '') or '0') or '0')
        numero_hasta = int(re.sub(r'\D', '', row_dict.get('número hasta', '') or row_dict.get('numero hasta', '') or '0') or '0') or None
        cuit = re.sub(r'\D', '', row_dict.get('cuit emisor', '') or row_dict.get('cuit receptor', '') or row_dict.get('nro. doc. emisor', '') or row_dict.get('nro. doc. receptor', '') or '')[:11]
        razon_social = row_dict.get('denominación emisor', '') or row_dict.get('denominación receptor', '') or row_dict.get('razón social', '') or ''
        cae = re.sub(r'\D', '', row_dict.get('nro. autorización', '') or row_dict.get('cae', '') or '')
        periodo = fecha_val.strftime('%Y%m')

        neto = _parse_decimal(row_dict.get('imp. neto gravado', '') or row_dict.get('neto gravado', '0'))
        no_grav = _parse_decimal(row_dict.get('imp. total de conceptos que no integran el precio neto gravado', '') or row_dict.get('no gravado', '0'))
        exento = _parse_decimal(row_dict.get('imp. op. exentas', '') or row_dict.get('exento', '0'))
        iva = _parse_decimal(row_dict.get('iva', '0'))
        otros = _parse_decimal(row_dict.get('otros tributos', '') or row_dict.get('otros', '0'))
        total = _parse_decimal(row_dict.get('imp. total', '') or row_dict.get('total', '0'))

        obj, _ = ArcaMisComprobantes.objects.update_or_create(
            empresa_id=empresa_id,
            origen=origen,
            codiva=codiva,
            punto=punto,
            numero=numero,
            cuit_contraparte=cuit,
            defaults={
                'periodo': periodo,
                'fecha': fecha_val,
                'numero_hasta': numero_hasta,
                'razon_social_contraparte': razon_social,
                'neto_gravado': neto,
                'no_gravado': no_grav,
                'exento': exento,
                'iva_total': iva,
                'otros': otros,
                'total': total,
                'cae': cae,
                'usuario': usuario,
            }
        )
        filas.append(obj)

    if filas:
        periodos_procesados = {f.periodo for f in filas}
        for p in periodos_procesados:
            conciliar_mis_comprobantes_arca(empresa_id, origen, p)

    return {'total_importados': len(filas)}


@transaction.atomic
def conciliar_mis_comprobantes_arca(empresa_id: int, origen: str, periodo_yyyymm: str) -> Dict[str, int]:
    """
    Ejecuta el matcheo bi-direccional entre ArcaMisComprobantes y el Libro IVA (Compras o Ventas).
    Al conciliar:
    1. ArcaMisComprobantes.asiento_id = match.asiento_id
    2. ArcaMisComprobantes.periodo = match.periodo (registra el período exacto en el que fue declarado en Libro IVA)
    3. LibroIva.cae = arca.cae (si no lo tenía previamente)
    """
    arca_items = ArcaMisComprobantes.objects.filter(
        empresa_id=empresa_id,
        origen=origen
    )

    # Considerar comprobantes de ARCA cuyo período o fecha coincida con la consulta
    arca_items_periodo = [a for a in arca_items if a.periodo == periodo_yyyymm or a.fecha.strftime('%Y%m') == periodo_yyyymm]

    conciliados_cnt = 0

    if origen == 'C':
        libros_empresa = LibroIvaCompras.objects.filter(empresa_id=empresa_id)
        for arca in arca_items_periodo:
            match = None
            if arca.cae:
                match = libros_empresa.filter(cae=arca.cae).first()
            if not match:
                match = libros_empresa.filter(punto=arca.punto, numero=arca.numero, cuit=arca.cuit_contraparte).first()

            if match:
                arca.asiento_id = match.asiento_id
                if match.periodo:
                    arca.periodo = match.periodo
                arca.save(update_fields=['asiento_id', 'periodo'])

                if arca.cae and match.cae != arca.cae:
                    match.cae = arca.cae
                    match.save(update_fields=['cae'])
                conciliados_cnt += 1

    else:
        libros_empresa = LibroIvaVentas.objects.filter(empresa_id=empresa_id)
        for arca in arca_items_periodo:
            match = None
            if arca.cae:
                match = libros_empresa.filter(cae=arca.cae).first()
            if not match:
                match = libros_empresa.filter(punto=arca.punto, numero=arca.numero).first()

            if match:
                arca.asiento_id = match.asiento_id
                if match.periodo:
                    arca.periodo = match.periodo
                arca.save(update_fields=['asiento_id', 'periodo'])

                if arca.cae and getattr(match, 'cae', '') != arca.cae:
                    match.cae = arca.cae
                    match.save(update_fields=['cae'])
                conciliados_cnt += 1

    return {'conciliados': conciliados_cnt}


def obtener_reporte_conciliacion_arca(empresa_id: int, origen: str, periodo_yyyymm: str) -> Dict[str, Any]:
    """
    Retorna los 3 conjuntos de comprobantes para la pantalla de conciliación:
    1. conciliados: Registros pareados (asiento_id presente).
    2. solo_libro_iva: Registros en Libro IVA que NO tienen asiento_id pareado en ArcaMisComprobantes.
    3. solo_arca: Registros de ArcaMisComprobantes pendientes (asiento_id es nulo).
    """
    arca_qs = ArcaMisComprobantes.objects.filter(empresa_id=empresa_id, origen=origen, periodo=periodo_yyyymm)
    conciliados = arca_qs.filter(asiento_id__isnull=False).order_by('fecha', 'punto', 'numero')
    solo_arca = arca_qs.filter(asiento_id__isnull=True).order_by('fecha', 'punto', 'numero')

    asientos_conciliados_ids = set(conciliados.values_list('asiento_id', flat=True))

    if origen == 'C':
        libro_qs = LibroIvaCompras.objects.filter(empresa_id=empresa_id, periodo=periodo_yyyymm)
    else:
        libro_qs = LibroIvaVentas.objects.filter(empresa_id=empresa_id, periodo=periodo_yyyymm)

    solo_libro_iva = [item for item in libro_qs if item.asiento_id not in asientos_conciliados_ids]

    return {
        'periodo': periodo_yyyymm,
        'origen': origen,
        'conciliados': conciliados,
        'solo_libro_iva': solo_libro_iva,
        'solo_arca': solo_arca,
        'cant_conciliados': len(conciliados),
        'cant_solo_libro': len(solo_libro_iva),
        'cant_solo_arca': len(solo_arca),
    }
