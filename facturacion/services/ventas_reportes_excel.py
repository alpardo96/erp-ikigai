import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from django.http import HttpResponse
from django.utils import timezone
from decimal import Decimal

def exportar_ventas_producto_excel_service(items, empresa, filtros):
    """
    Genera y devuelve una respuesta HttpResponse con la planilla .xlsx estilizada
    del Reporte de Ventas por Producto, coincidiendo con la plantilla de productos_vendidos.xlsx.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Productos Vendidos"

    # Encabezados de 38 columnas según productos_vendidos.xlsx
    headers = [
        'ID.Vta', 'ID.Asto', 'Fecha', 'Comprobante', 'id.cod', 'Cliente', 'Credencial',
        'Codigo', 'Cod Prov', 'Producto', 'Serie', 'CUIM', 'Cantidad', 'cto.Rep.',
        'fec.Act.', 'moneda', 'cotiz', 'alic.iva', 'pcio.T.', 'Neto', 'Total',
        'Stock', 'id.pro', 'Proveedor', 'id.rubro', 'rubro', 'id.flia', 'familia',
        'id.subflia', 'subfamilia', 'id.marca', 'marca', 'id.vdor', 'Vendedor',
        'Cto.Adq.', 'Margen', 'Mg.Rubro', 'Sucursal'
    ]

    ncols = len(headers)
    ultima_col = get_column_letter(ncols)

    # Fila 1: Título institucional
    ws.merge_cells(f'A1:{ultima_col}1')
    empresa_nombre = empresa.nombre.upper() if empresa else 'ERP IKIGAI'
    ws['A1'] = f"{empresa_nombre} - LISTADO DE PRODUCTOS VENDIDOS"
    ws['A1'].font = Font(size=14, bold=True, color="1E293B")
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')

    # Fila 2: Subtítulo con parámetros de período y filtros
    desde = filtros.get('desde') or '—'
    hasta = filtros.get('hasta') or '—'
    suc = filtros.get('sucursal_nombre') or 'Todas'
    cli = filtros.get('cliente_nombre') or 'Todos'
    ws.merge_cells(f'A2:{ultima_col}2')
    ws['A2'] = (f"Periodo: {desde} al {hasta} | Sucursal: {suc} | Cliente: {cli} | "
                f"Emisión: {timezone.localtime().strftime('%d/%m/%Y %H:%M')}")
    ws['A2'].font = Font(size=10, italic=True, color="64748B")
    ws['A2'].alignment = Alignment(horizontal='center', vertical='center')

    # Fila 4: Encabezados de la tabla
    header_fill = PatternFill("solid", fgColor="0F172A") # slate-900 elegante
    header_font = Font(bold=True, color="FFFFFF", size=10)
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    # Filas de datos (empezando en fila 5)
    row_idx = 5
    tot_cant = Decimal("0.00")
    tot_neto = Decimal("0.00")
    tot_total = Decimal("0.00")

    border_light = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    # Stock por (producto, sucursal) en UNA consulta (Plan 053). La columna Stock salía de
    # `Producto.stock`, un campo heredado del VFP que ya nadie actualizaba: exportaba el valor
    # congelado de la importación. Ahora sale del stock real de la sucursal de la venta, y se
    # precarga acá porque leerlo fila por fila dispararía una consulta por ítem.
    from productos.models import StockSucursal
    _productos = {i.producto_id for i in items if i.producto_id}
    _sucursales = {i.venta.sucursal_id for i in items if i.venta_id and i.venta.sucursal_id}
    stock_por_clave = {}
    if _productos and _sucursales:
        stock_por_clave = {
            (s['producto_id'], s['sucursal_id']): s['cantidad']
            for s in StockSucursal.objects.filter(
                producto_id__in=_productos, sucursal_id__in=_sucursales
            ).values('producto_id', 'sucursal_id', 'cantidad')
        }

    for item in items:
        vta = item.venta
        prod = item.producto
        cli_obj = vta.cliente if vta else None
        prov_obj = prod.proveedor if prod else None
        rubro_obj = prod.rubro if prod else None
        flia_obj = prod.familia if prod else None
        marca_obj = prod.marca if prod else None
        vendedor_obj = vta.vendedor if vta else None

        cant = Decimal(str(item.cantidad or 0))
        pcio_vta = Decimal(str(item.precio_unitario or 0))
        total = Decimal(str(item.total or 0))
        alic_iva = Decimal(str(item.iva_alicuota or 0))

        # Neto de la línea
        factor_iva = Decimal("1.00") + (alic_iva / Decimal("100.00"))
        neto = (total / factor_iva).quantize(Decimal("0.01")) if factor_iva else total

        pcio_t = (total / cant).quantize(Decimal("0.01")) if cant else pcio_vta

        # Acumuladores
        tot_cant += cant
        tot_neto += neto
        tot_total += total

        comprobante_str = f"{vta.tipo.codigo if vta.tipo else ''} {vta.punto:05d}-{vta.numero:08d}" if vta else ''
        fecha_str = vta.fecha.strftime('%Y-%m-%d %H:%M:%S') if vta and vta.fecha else ''
        fec_act_str = prod.fec_act.strftime('%Y-%m-%d %H:%M:%S') if prod and prod.fec_act else ''

        row_data = [
            vta.ventas_id if vta else '',                             # ID.Vta
            vta.asiento_id if vta and vta.asiento_id else '',        # ID.Asto
            fecha_str,                                               # Fecha
            comprobante_str,                                         # Comprobante
            cli_obj.codigo_id if cli_obj else '',                    # id.cod
            vta.cliente_razon_social or (cli_obj.razon_social if cli_obj else ''), # Cliente
            item.credencial or '',                                   # Credencial
            prod.pk if prod else '',                                 # Codigo
            prod.cod_prov if prod and prod.cod_prov else '',         # Cod Prov
            item.concepto or (prod.detalle if prod else ''),         # Producto
            '',                                                      # Serie
            '',                                                      # CUIM
            float(cant),                                             # Cantidad
            float(prod.cto_rep) if prod and prod.cto_rep else 0.0,   # cto.Rep.
            fec_act_str,                                             # fec.Act.
            item.moneda_origen or (vta.moneda if vta else 'PES'),    # moneda
            float(vta.cotizacion) if vta else 1.0,                   # cotiz
            float(alic_iva),                                         # alic.iva
            float(pcio_t),                                           # pcio.T.
            float(neto),                                             # Neto
            float(total),                                            # Total
            # Stock REAL de la sucursal de la venta (Plan 053).
            float(stock_por_clave.get(
                (item.producto_id, vta.sucursal_id if vta else None), 0) or 0),   # Stock
            prov_obj.codigo_id if prov_obj else '',                  # id.pro
            prov_obj.razon_social if prov_obj else '',               # Proveedor
            rubro_obj.pk if rubro_obj else '',                       # id.rubro
            rubro_obj.detalle if rubro_obj else '',                  # rubro
            flia_obj.pk if flia_obj else '',                         # id.flia
            flia_obj.detalle if flia_obj else '',                    # familia
            0,                                                       # id.subflia
            'VARIOS',                                                # subfamilia
            marca_obj.pk if marca_obj else '',                       # id.marca
            marca_obj.detalle if marca_obj else '',                  # marca
            vendedor_obj.pk if vendedor_obj else '',                 # id.vdor
            vendedor_obj.username if vendedor_obj else '',           # Vendedor
            float(prod.cto_adq) if prod and prod.cto_adq else 0.0,   # Cto.Adq.
            float(prod.margen) if prod and prod.margen else 0.0,     # Margen
            float(rubro_obj.margen) if rubro_obj and rubro_obj.margen else 0.0, # Mg.Rubro
            vta.sucursal.nombre if vta and vta.sucursal else ''      # Sucursal
        ]

        for col_idx, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.border = border_light
            # Formatos numéricos
            if col_idx in [13]:  # Cantidad
                cell.number_format = '#,##0.00'
                cell.alignment = Alignment(horizontal='right')
            elif col_idx in [14, 17, 18, 19, 20, 21, 22, 35, 36, 37]:  # Moneda / importes
                cell.number_format = '#,##0.00'
                cell.alignment = Alignment(horizontal='right')

        row_idx += 1

    # Fila final de Totales
    ws.cell(row=row_idx, column=10, value="TOTALES GENERALES").font = Font(bold=True)
    ws.cell(row=row_idx, column=10).alignment = Alignment(horizontal='right')

    cell_cant = ws.cell(row=row_idx, column=13, value=float(tot_cant))
    cell_cant.number_format = '#,##0.00'
    cell_cant.font = Font(bold=True)

    cell_neto = ws.cell(row=row_idx, column=20, value=float(tot_neto))
    cell_neto.number_format = '#,##0.00'
    cell_neto.font = Font(bold=True)

    cell_total = ws.cell(row=row_idx, column=21, value=float(tot_total))
    cell_total.number_format = '#,##0.00'
    cell_total.font = Font(bold=True)

    border_total = Border(top=Side(style='double'), bottom=Side(style='double'))
    for c in range(1, ncols + 1):
        ws.cell(row=row_idx, column=c).border = border_total

    # Ajuste automático del ancho de columnas
    for col_idx in range(1, ncols + 1):
        col_letter = get_column_letter(col_idx)
        max_len = len(str(headers[col_idx - 1]))
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    timestamp = timezone.localtime().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="productos_vendidos_{timestamp}.xlsx"'
    wb.save(response)
    return response
