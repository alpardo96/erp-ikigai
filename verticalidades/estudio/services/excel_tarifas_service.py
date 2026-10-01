"""
Servicio de Exportación e Importación de Tarifas de Estudio en Excel (.xlsx).
ERP Ikigai 2 - Verticalidad Estudio.
"""
import io
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from decimal import Decimal, InvalidOperation

from verticalidades.estudio.models import TarifaEstudio
from facturacion.models import ClienteProveedor


def generar_excel_tarifas_estudio(empresa) -> io.BytesIO:
    """
    Genera un libro de Excel (.xlsx) con el listado completo de tarifas pactadas
    de la empresa activa, incluyendo datos fiscales, de producto, domicilio y pago.
    """
    tarifas_qs = TarifaEstudio.objects.filter(empresa=empresa).select_related('cliente', 'producto', 'cuenta').order_by('cliente__razon_social')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Tarifas Estudio"

    # Estilos profesionales
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")  # Slate 900
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    data_font = Font(name="Arial", size=9)
    bold_font = Font(name="Arial", size=9, bold=True)
    border_light = Side(border_style="thin", color="CBD5E1")
    cell_border = Border(top=border_light, bottom=border_light, left=border_light, right=border_light)

    # Definición de Columnas completas para facturación
    headers = [
        "ID",
        "Cód. Cliente",
        "Razón Social",
        "CUIT",
        "Condición IVA",
        "Domicilio",
        "Localidad",
        "Forma de Pago",
        "Cód. Producto",
        "Servicio / Concepto",
        "Cuenta Imputación",
        "Tarifa F (Actual)",
        "Tarifa P (Actual)",
        "Tarifa F (Nueva)",
        "Tarifa P (Nueva)",
        "Activo"
    ]

    # Escribir Encabezados
    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Formato numérico de moneda / decimales
    number_format = "$ #,##0.00"

    # Escribir Filas de Datos
    for idx, t in enumerate(tarifas_qs, start=2):
        cli = t.cliente
        prod = t.producto
        cta = t.cuenta

        cta_str = f"{cta.jerarquia} - {cta.cuenta}" if cta else ""
        cuit_str = cli.cuit if cli and cli.cuit else ""
        cond_iva_str = cli.condicion_iva if cli and cli.condicion_iva else ""
        domicilio_str = cli.domicilio if cli and cli.domicilio else ""
        localidad_str = cli.localidad if cli and cli.localidad else ""

        row = [
            t.id,
            cli.codigo_id if cli else "",
            cli.razon_social if cli else "",
            cuit_str,
            cond_iva_str,
            domicilio_str,
            localidad_str,
            "Cuenta Corriente",
            prod.id if prod else "",
            prod.detalle if prod else "",
            cta_str,
            float(t.tarifa_f or 0),
            float(t.tarifa_p or 0),
            float(t.tarifa_f or 0),  # Nueva precargada para ajuste
            float(t.tarifa_p or 0),  # Nueva precargada para ajuste
            "SI" if t.activo else "NO"
        ]
        ws.append(row)

        # Aplicar estilos a cada celda de la fila
        for col_idx in range(1, len(headers) + 1):
            c = ws.cell(row=idx, column=col_idx)
            c.font = data_font
            c.border = cell_border

            # Alineaciones específicas
            if col_idx in (1, 2, 4, 5, 8, 9, 16):
                c.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx in (12, 13, 14, 15):
                c.alignment = Alignment(horizontal="right", vertical="center")
                c.number_format = number_format
                if col_idx in (14, 15):
                    c.font = bold_font
            else:
                c.alignment = Alignment(horizontal="left", vertical="center")

    # Ajuste automático del ancho de columnas
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or '')
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 10)

    # Ancho de columna ID
    ws.column_dimensions['A'].width = 8

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def parsear_excel_tarifas_estudio(archivo_excel, empresa) -> dict:
    """
    Lee un archivo Excel (.xlsx o .xls) cargado por el usuario, extrae las tarifas
    nuevas y las mapea contra los registros vigentes de la empresa.
    
    Retorna un diccionario con:
      - 'exito': bool
      - 'items': lista de items actualizados para la grilla Alpine.js
      - 'actualizados': int
      - 'no_encontrados': int
      - 'errores': list[str]
    """
    from productos.models import Producto

    try:
        wb = openpyxl.load_workbook(archivo_excel, data_only=True)
        ws = wb.active
    except Exception as e:
        return {
            'exito': False,
            'mensaje': f"Error al abrir el archivo Excel: {str(e)}",
            'items': [],
            'actualizados': 0
        }

    filas = list(ws.iter_rows(values_only=True))
    if not filas or len(filas) < 2:
        return {
            'exito': False,
            'mensaje': "El archivo Excel está vacío o no contiene filas de datos.",
            'items': [],
            'actualizados': 0
        }

    # Detectar índices de columnas dinámicamente según los encabezados
    header_row = [str(h or '').strip().upper() for h in filas[0]]
    
    col_map = {
        'id': 0,
        'cod_cli': 1,
        'cod_prod': None,
        'tf_nueva': None,
        'tp_nueva': None,
        'activo': None
    }

    for idx, h in enumerate(header_row):
        h_norm = f" {h} "
        if h == 'ID':
            col_map['id'] = idx
        elif ('CÓD' in h or 'COD' in h or 'CODIGO' in h) and ('CLI' in h or 'CLIENTE' in h):
            col_map['cod_cli'] = idx
        elif ('PROD' in h or 'PRODUCTO' in h) and ('CÓD' in h or 'COD' in h or 'ID' in h):
            col_map['cod_prod'] = idx
        elif ('TARIFA F' in h or ' F ' in h_norm or 'F (' in h or 'F(' in h) and 'NUEVA' in h:
            col_map['tf_nueva'] = idx
        elif ('TARIFA P' in h or ' P ' in h_norm or 'P (' in h or 'P(' in h) and 'NUEVA' in h:
            col_map['tp_nueva'] = idx
        elif 'ACTIVO' in h or 'ESTADO' in h:
            col_map['activo'] = idx

    # Fallbacks posicionales si no se detectaron por encabezado exacto
    if col_map['tf_nueva'] is None:
        col_map['tf_nueva'] = 13 if len(header_row) > 13 else 8
    if col_map['tp_nueva'] is None:
        col_map['tp_nueva'] = 14 if len(header_row) > 14 else 9
    if col_map['activo'] is None:
        col_map['activo'] = 15 if len(header_row) > 15 else 10

    # Mapa de tarifas vigentes por ID y por cliente_id para búsqueda rápida
    tarifas_db = {t.id: t for t in TarifaEstudio.objects.filter(empresa=empresa).select_related('cliente', 'producto', 'cuenta')}
    tarifas_por_cliente = {t.cliente_id: t for t in tarifas_db.values()}
    productos_cache = {p.id: p for p in Producto.objects.filter(empresa=empresa)}

    items_actualizados = []
    actualizados_count = 0
    no_encontrados = 0
    errores = []

    def _parse_dec(val):
        if val is None or val == '':
            return Decimal('0.00')
        if isinstance(val, (int, float)):
            return Decimal(str(val)).quantize(Decimal('0.01'))
        if isinstance(val, Decimal):
            return val.quantize(Decimal('0.01'))
        s = str(val).strip().replace('$', '').replace(' ', '')
        if ',' in s and '.' in s:
            s = s.replace('.', '').replace(',', '.')
        elif ',' in s:
            s = s.replace(',', '.')
        try:
            return Decimal(s).quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError):
            return Decimal('0.00')

    # Filas 2+: Datos (index 1 en adelante)
    for row_idx, row in enumerate(filas[1:], start=2):
        if not row or all(c is None or str(c).strip() == '' for c in row):
            continue

        raw_id = row[col_map['id']] if len(row) > col_map['id'] else None
        raw_cod_cli = row[col_map['cod_cli']] if len(row) > col_map['cod_cli'] else None
        
        raw_tf_nueva = row[col_map['tf_nueva']] if len(row) > col_map['tf_nueva'] else 0
        raw_tp_nueva = row[col_map['tp_nueva']] if len(row) > col_map['tp_nueva'] else 0
        raw_activo = row[col_map['activo']] if col_map['activo'] is not None and len(row) > col_map['activo'] else "SI"

        raw_cod_prod = None
        if col_map['cod_prod'] is not None and len(row) > col_map['cod_prod']:
            raw_cod_prod = row[col_map['cod_prod']]

        tarifa_obj = None

        # 1. Matching por ID de tarifa
        if raw_id is not None:
            try:
                tarifa_id = int(str(raw_id).strip())
                tarifa_obj = tarifas_db.get(tarifa_id)
            except ValueError:
                pass

        # 2. Matching por Código de Cliente
        if not tarifa_obj and raw_cod_cli is not None:
            try:
                cli_id = int(str(raw_cod_cli).strip())
                tarifa_obj = tarifas_por_cliente.get(cli_id)
            except ValueError:
                pass

        if not tarifa_obj:
            no_encontrados += 1
            continue

        tf_nueva = _parse_dec(raw_tf_nueva)
        tp_nueva = _parse_dec(raw_tp_nueva)

        activo_str = str(raw_activo or 'SI').strip().upper()
        activo_bool = activo_str in ('SI', 'S', 'TRUE', '1', 'ACTIVO', 'V', 'VERDADERO')

        # Producto asociado
        prod_obj = tarifa_obj.producto
        if raw_cod_prod is not None:
            try:
                pid = int(str(raw_cod_prod).strip())
                if pid in productos_cache:
                    prod_obj = productos_cache[pid]
            except ValueError:
                pass

        # Calcular alícuota de IVA informativa
        alic_iva = float(prod_obj.alic_iva_porc) if (prod_obj and hasattr(prod_obj, 'alic_iva_porc')) else 21.0

        items_actualizados.append({
            'id': tarifa_obj.id,
            'cliente_id': tarifa_obj.cliente.codigo_id if tarifa_obj.cliente else '',
            'razon_social': tarifa_obj.cliente.razon_social if tarifa_obj.cliente else '',
            'tarifa_f_ant': float(tarifa_obj.tarifa_f),
            'tarifa_p_ant': float(tarifa_obj.tarifa_p),
            'tarifa_f_nueva': float(tf_nueva),
            'tarifa_p_nueva': float(tp_nueva),
            'alic_iva': alic_iva,
            'activo': activo_bool,
            'activo_ant': tarifa_obj.activo,
            'producto_id': prod_obj.id if prod_obj else None,
            'producto_id_ant': tarifa_obj.producto.id if tarifa_obj.producto else None,
            'cuenta_id': tarifa_obj.cuenta.id if tarifa_obj.cuenta else None,
            'cuenta_id_ant': tarifa_obj.cuenta.id if tarifa_obj.cuenta else None,
            'producto_detalle': prod_obj.detalle if prod_obj else ''
        })
        actualizados_count += 1

    return {
        'exito': True,
        'items': items_actualizados,
        'actualizados': actualizados_count,
        'no_encontrados': no_encontrados,
        'errores': errores,
        'mensaje': f"Se leyeron {actualizados_count} tarifas actualizadas desde el archivo Excel."
    }
