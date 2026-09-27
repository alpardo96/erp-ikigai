import re
import unicodedata
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from django.db import transaction
from contable.models import Cuenta

# Mapeo de columnas disponibles para exportación y captura de Cuentas Contables
COLUMNAS_CUENTA_MAP = {
    'id': 'ID',
    'sumariza_id': 'Sumariza ID',
    'jerarquia': 'Jerarquía',
    'cuenta': 'Nombre Cuenta',
    'imputable': 'Imputable (1=Sí, 0=No)',
    'tipo': 'Tipo (A/P/N/R)',
    'codigo': 'Código (Legacy)',
    'rg_830': 'RG 830',
    'tipo_disponibilidad': 'Tipo Disponibilidad',
    'id_pre': 'ID Pre',
    'id_bce': 'ID Bce',
    'id_ec': 'ID EC',
    'id_fc': 'ID FC',
}


def _normalizar_texto(texto):
    """
    Elimina acentos, caracteres especiales y convierte a minúsculas para comparaciones robustas.
    Ejemplo: 'Jerarquía' -> 'jerarquia', 'Código (Legacy)' -> 'codigolegacy'
    """
    if not texto:
        return ""
    s = unicodedata.normalize('NFKD', str(texto)).encode('ascii', 'ignore').decode('utf-8')
    return re.sub(r'[^a-zA-Z0-9_]', '', s).lower()


def _mapear_encabezado_columna(header_str):
    """
    Mapea de forma segura el texto de un encabezado de columna al nombre de campo correspondiente,
    evitando colisiones como la subcadena 'id' en 'disponibilidad'.
    """
    norm = _normalizar_texto(header_str)
    if not norm:
        return None

    # 1. Coincidencia exacta con campos conocidos
    for k, v in COLUMNAS_CUENTA_MAP.items():
        if norm == _normalizar_texto(k) or norm == _normalizar_texto(v):
            return k

    # 2. Coincidencia exclusiva para ID de base de datos
    if norm in ['id', 'idcuenta', 'cuentaid', 'idcta', 'identificador', 'pk']:
        return 'id'

    # 3. Sumariza / Cuenta Padre
    if 'sumariza' in norm or 'padre' in norm or 'ctapadre' in norm:
        return 'sumariza_id'

    # 4. Jerarquía
    if 'jerarq' in norm or 'codigojer' in norm or 'estructura' in norm or 'arbol' in norm:
        return 'jerarquia'

    # 5. Nombre / Descripción de la cuenta
    if 'nombre' in norm or 'cuenta' in norm or 'descripcion' in norm or 'denominacion' in norm or 'detalle' in norm:
        return 'cuenta'

    # 6. Imputable
    if 'imput' in norm or 'asienta' in norm or 'movimiento' in norm:
        return 'imputable'

    # 7. Tipo Disponibilidad (Tesorería / Caja Diaria)
    if 'disponib' in norm or 'tesoreria' in norm or 'cajabanco' in norm:
        return 'tipo_disponibilidad'

    # 8. Mapeos de Balances y Estados Financieros
    if 'pre' in norm:
        return 'id_pre'
    if 'bce' in norm:
        return 'id_bce'
    if 'ec' in norm:
        return 'id_ec'
    if 'fc' in norm:
        return 'id_fc'

    # 9. RG 830 Retenciones Ganancias
    if 'rg' in norm or '830' in norm or 'ganancia' in norm:
        return 'rg_830'

    # 10. Código Legacy / Anterior
    if 'legacy' in norm or 'codigo' in norm or 'cod' in norm:
        return 'codigo'

    # 11. Tipo Contable (Activo / Pasivo / PN / Resultado)
    if 'tipo' in norm or 'clase' in norm or 'rubro' in norm:
        return 'tipo'

    return None


def generar_excel_cuentas(queryset):
    """
    Genera un libro de Excel (.xlsx) con el plan de cuentas provisto en el queryset.
    """
    columnas_keys = list(COLUMNAS_CUENTA_MAP.keys())

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Plan de Cuentas"

    # Estilos del encabezado (Dark slate slate-900)
    header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    data_font = Font(name="Arial", size=9)
    border_light = Side(border_style="thin", color="CBD5E1")
    cell_border = Border(top=border_light, bottom=border_light, left=border_light, right=border_light)

    # Escribir Encabezados
    headers = [COLUMNAS_CUENTA_MAP[k] for k in columnas_keys]
    ws.append(headers)

    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Escribir Filas de Datos
    for cta in queryset:
        row_data = [
            cta.id,
            cta.sumariza_id if cta.sumariza_id is not None else '',
            cta.jerarquia or '',
            (cta.cuenta or '').upper(),
            cta.imputable if cta.imputable is not None else 0,
            cta.tipo or '',
            cta.codigo if cta.codigo is not None else '',
            cta.rg_830 if cta.rg_830 is not None else '',
            cta.tipo_disponibilidad or '',
            cta.id_pre if cta.id_pre is not None else '',
            cta.id_bce if cta.id_bce is not None else '',
            cta.id_ec if cta.id_ec is not None else '',
            cta.id_fc if cta.id_fc is not None else '',
        ]
        ws.append(row_data)

    # Formatear filas y autoajustar anchos
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=len(columnas_keys)):
        for cell in row:
            cell.font = data_font
            cell.border = cell_border
            if isinstance(cell.value, (int, float)):
                cell.alignment = Alignment(horizontal="right", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    return wb


def procesar_captura_excel_cuentas(empresa, usuario, archivo_excel):
    """
    Procesa la captura e importación masiva de cuentas contables desde un archivo Excel.

    Reglas de negocio y robustez:
    1. Convierte a MAYÚSCULAS el nombre de la cuenta (campo `cuenta`) y trunca al límite VARCHAR(50).
    2. Si 'ID' viene y EXISTE en la empresa activa -> Actualiza los campos excepto el ID.
    3. Si 'ID' no se encuentra en la empresa activa (o está vacío/inválido) -> Trata la fila como una
       cuenta NUEVA y deja que la base de datos asigne automáticamente el ID.
    4. Resuelve dinámicamente el vínculo `sumariza` tanto por `sumariza_id` como por jerarquía padre (ej. 1.1 padre de 1.1.01).
    5. Deduce de forma inteligente el tipo contable (A/P/N/R) en caso de venir con descripciones en texto o vacío.
    """
    resultado = {
        'actualizados': 0,
        'creados': 0,
        'errores': []
    }

    try:
        wb = openpyxl.load_workbook(archivo_excel, data_only=True)
        ws = wb.active
    except Exception as e:
        resultado['errores'].append(f"Error al abrir el archivo Excel: {str(e)}")
        return resultado

    # Leer encabezados (primera fila)
    headers = []
    for cell in ws[1]:
        val = str(cell.value or '').strip()
        headers.append(val)

    if not headers or not any(headers):
        resultado['errores'].append("El archivo Excel está vacío o no contiene encabezados válidos.")
        return resultado

    # Mapeo de columnas del archivo
    normalized_headers = {}
    for idx, h in enumerate(headers):
        campo = _mapear_encabezado_columna(h)
        if campo:
            normalized_headers[idx] = campo

    if 'jerarquia' not in normalized_headers.values() or 'cuenta' not in normalized_headers.values():
        resultado['errores'].append(
            "No se encontraron las columnas obligatorias 'Jerarquía' y 'Nombre Cuenta' en el encabezado del archivo."
        )
        return resultado

    # Cache preexistente de cuentas de la empresa por ID y por Jerarquía
    cuentas_por_id = {c.id: c for c in Cuenta.objects.filter(empresa=empresa)}
    cuentas_por_jerarquia = {c.jerarquia: c for c in Cuenta.objects.filter(empresa=empresa)}

    # Cuentas a las que se les verificará o completará el vínculo de sumariza en segundo paso
    cuentas_procesadas = []

    with transaction.atomic():
        row_idx = 1
        for row in ws.iter_rows(min_row=2, values_only=True):
            row_idx += 1

            # Filtrar filas completamente vacías o compuestas solo por espacios en blanco
            valores_fila = [str(c).strip() for c in row if c is not None and str(c).strip() != '']
            if not valores_fila:
                continue

            row_dict = {}
            for col_idx, val in enumerate(row):
                if col_idx in normalized_headers:
                    row_dict[normalized_headers[col_idx]] = val

            # Helper para limpiar texto
            def _clean_str(val):
                if val is None:
                    return ''
                if isinstance(val, float) and val.is_integer():
                    return str(int(val)).strip()
                return str(val).strip()

            jerarquia_val = _clean_str(row_dict.get('jerarquia'))[:20]
            cuenta_val = _clean_str(row_dict.get('cuenta')).upper()[:50]

            if not jerarquia_val or not cuenta_val:
                resultado['errores'].append(
                    f"Fila {row_idx}: Omitida por no contar con 'Jerarquía' o 'Nombre Cuenta' válido."
                )
                continue

            # Parsear Imputable (1 o 0)
            raw_imp = row_dict.get('imputable')
            norm_imp = _normalizar_texto(raw_imp)
            if norm_imp in ['1', 'si', 'true', 's', 'imputable', 'asienta']:
                imputable_val = 1
            else:
                try:
                    imputable_val = int(float(str(raw_imp).strip()))
                    imputable_val = 1 if imputable_val != 0 else 0
                except (ValueError, TypeError):
                    imputable_val = 0

            # Parsear Tipo (A, P, N, R) con deducción inteligente
            tipo_raw = _clean_str(row_dict.get('tipo')).upper()
            norm_tipo = _normalizar_texto(tipo_raw)

            if norm_tipo.startswith('act') or norm_tipo == 'a':
                tipo_val = 'A'
            elif norm_tipo.startswith('pas') or norm_tipo == 'p':
                tipo_val = 'P'
            elif 'patrimonio' in norm_tipo or 'neto' in norm_tipo or norm_tipo in ['n', 'pn']:
                tipo_val = 'N'
            elif any(r in norm_tipo for r in ['resultado', 'perdida', 'ganancia', 'gasto', 'ingreso', 'costo', 'egreso']) or norm_tipo in ['r', 'rp', 'rn']:
                tipo_val = 'R'
            elif jerarquia_val:
                # Deducir según el primer dígito jerárquico estándar (1=Activo, 2=Pasivo, 3=Patrimonio Neto, 4/5=Resultados)
                primer_digito = jerarquia_val[0]
                if primer_digito == '1': tipo_val = 'A'
                elif primer_digito == '2': tipo_val = 'P'
                elif primer_digito == '3': tipo_val = 'N'
                elif primer_digito in ['4', '5', '6', '7', '8', '9']: tipo_val = 'R'
                else: tipo_val = 'A'
            else:
                tipo_val = 'A'

            # Helper para enteros opcionales
            def _clean_int(v):
                if v is None or str(v).strip() == '':
                    return None
                try:
                    return int(float(str(v).strip()))
                except (ValueError, TypeError):
                    return None

            codigo_val = _clean_int(row_dict.get('codigo'))
            sumariza_id_val = _clean_int(row_dict.get('sumariza_id'))
            rg_830_val = _clean_int(row_dict.get('rg_830'))
            id_pre_val = _clean_int(row_dict.get('id_pre'))
            id_bce_val = _clean_int(row_dict.get('id_bce'))
            id_ec_val = _clean_int(row_dict.get('id_ec'))
            id_fc_val = _clean_int(row_dict.get('id_fc'))

            # Parsear tipo_disponibilidad
            disp_raw = _clean_str(row_dict.get('tipo_disponibilidad')).upper()
            valid_disps = ['EFE', 'DOL', 'VAL', 'BCO', 'TAR', 'OTR']
            tipo_disp_val = disp_raw[:3] if disp_raw in valid_disps else ''

            # Buscar ID si viene especificado
            raw_id = row_dict.get('id')
            cta_id = _clean_int(raw_id)

            # Buscar si la cuenta ya existe en la empresa activa por ID
            cuenta_obj = None
            if cta_id and cta_id in cuentas_por_id:
                cuenta_obj = cuentas_por_id[cta_id]

            # Buscar cuenta padre (sumariza) por ID explícito o por prefijo de jerarquía
            sumariza_obj = None
            if sumariza_id_val and sumariza_id_val in cuentas_por_id:
                sumariza_obj = cuentas_por_id[sumariza_id_val]
            elif '.' in jerarquia_val:
                padre_jerarquia = jerarquia_val.rsplit('.', 1)[0]
                if padre_jerarquia in cuentas_por_jerarquia:
                    sumariza_obj = cuentas_por_jerarquia[padre_jerarquia]

            if cuenta_obj:
                # --- ACTUALIZACIÓN DE CUENTA EXISTENTE ---
                cuenta_obj.jerarquia = jerarquia_val
                cuenta_obj.cuenta = cuenta_val
                cuenta_obj.imputable = imputable_val
                cuenta_obj.tipo = tipo_val
                cuenta_obj.codigo = codigo_val
                cuenta_obj.rg_830 = rg_830_val
                cuenta_obj.tipo_disponibilidad = tipo_disp_val
                cuenta_obj.id_pre = id_pre_val
                cuenta_obj.id_bce = id_bce_val
                cuenta_obj.id_ec = id_ec_val
                cuenta_obj.id_fc = id_fc_val
                if sumariza_obj:
                    cuenta_obj.sumariza = sumariza_obj
                if usuario:
                    cuenta_obj.modificado_por = usuario
                cuenta_obj.save()

                resultado['actualizados'] += 1
                cuentas_por_jerarquia[jerarquia_val] = cuenta_obj
                cuentas_procesadas.append(cuenta_obj)
            else:
                # --- CREACIÓN DE NUEVA CUENTA ---
                nueva_cta = Cuenta.objects.create(
                    empresa=empresa,
                    jerarquia=jerarquia_val,
                    cuenta=cuenta_val,
                    imputable=imputable_val,
                    tipo=tipo_val,
                    codigo=codigo_val,
                    rg_830=rg_830_val,
                    tipo_disponibilidad=tipo_disp_val,
                    id_pre=id_pre_val,
                    id_bce=id_bce_val,
                    id_ec=id_ec_val,
                    id_fc=id_fc_val,
                    sumariza=sumariza_obj,
                    creado_por=usuario if usuario else None,
                    modificado_por=usuario if usuario else None,
                )
                resultado['creados'] += 1
                cuentas_por_id[nueva_cta.id] = nueva_cta
                cuentas_por_jerarquia[jerarquia_val] = nueva_cta
                cuentas_procesadas.append(nueva_cta)

        # Segundo paso: Asegurar la resolución del vínculo jerárquico padre ('sumariza')
        # para cuentas cuyos padres hayan sido creados en filas posteriores del archivo
        for cta in cuentas_procesadas:
            if cta.sumariza is None and '.' in cta.jerarquia:
                padre_jerarquia = cta.jerarquia.rsplit('.', 1)[0]
                if padre_jerarquia in cuentas_por_jerarquia:
                    cta.sumariza = cuentas_por_jerarquia[padre_jerarquia]
                    cta.save(update_fields=['sumariza'])

    return resultado

