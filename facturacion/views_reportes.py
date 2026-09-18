import csv
from decimal import Decimal
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db.models import Sum, Q
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required

from facturacion.models import VentaItem, ClienteProveedor, Venta
from productos.models import Producto, Rubro, Familia, Subfamilia
from empresas.models import Sucursal, Ejercicio, Empresa
from facturacion.services.ventas_reportes_excel import exportar_ventas_producto_excel_service
from facturacion.services.clientes_excel import exportar_clientes_excel_service

User = get_user_model()


def obtener_items_ventas_filtrados(request):
    """
    Filtra los ítems de venta (VentaItem) según los parámetros de la solicitud HTTP.
    Si NO es una petición con el parámetro 'filtering', devuelve un queryset vacío para evitar
    demoras en la carga inicial de la pantalla. La consulta se ejecuta al presionar 'Filtrar'.
    """
    empresa_id = request.session.get('empresa_id')
    if not empresa_id:
        return VentaItem.objects.none(), {'ejecutado': False}

    GET = request.GET
    desde = (GET.get('desde') or '').strip()
    hasta = (GET.get('hasta') or '').strip()

    # Si no se pasan fechas, establecer por defecto el 1er día del mes actual hasta hoy
    hoy = timezone.localdate()
    if not desde:
        desde = hoy.replace(day=1).strftime('%Y-%m-%d')
    if not hasta:
        hasta = hoy.strftime('%Y-%m-%d')

    cliente_id = (GET.get('cliente') or '').strip()
    producto_id = (GET.get('producto') or '').strip()
    sucursal_id = (GET.get('sucursal') or '').strip()
    rubro_id = (GET.get('rubro') or '').strip()
    familia_id = (GET.get('familia') or '').strip()
    subfamilia_id = (GET.get('subfamilia') or '').strip()
    vendedor_id = (GET.get('vendedor') or '').strip()

    is_filtered_request = 'filtering' in GET or 'desde' in GET and ('cliente' in GET or 'sucursal' in GET or 'producto' in GET or 'rubro' in GET)

    # Nombres descriptivos de filtros para encabezados de exportación y resumen
    sucursal_nombre = "Todas"
    if sucursal_id:
        suc_obj = Sucursal.objects.filter(pk=sucursal_id).only('id', 'nombre').first()
        if suc_obj:
            sucursal_nombre = suc_obj.nombre

    cliente_nombre = "Todos"
    if cliente_id:
        cli_obj = ClienteProveedor.objects.filter(pk=cliente_id).only('codigo_id', 'razon_social').first()
        if cli_obj:
            cliente_nombre = cli_obj.razon_social

    producto_nombre = "Todos"
    if producto_id:
        prod_obj = Producto.objects.filter(pk=producto_id).only('id', 'detalle').first()
        if prod_obj:
            producto_nombre = prod_obj.detalle

    fiscal = GET.get('fiscal') == 'on' or GET.get('fiscal') == 'true' or GET.get('fiscal') == '1' if 'filtering' in GET else True
    no_fiscal = GET.get('no_fiscal') == 'on' or GET.get('no_fiscal') == 'true' or GET.get('no_fiscal') == '1' if 'filtering' in GET else True

    filtros_dict = {
        'desde': desde,
        'hasta': hasta,
        'sucursal_id': sucursal_id,
        'sucursal_nombre': sucursal_nombre,
        'cliente_id': cliente_id,
        'cliente_nombre': cliente_nombre,
        'producto_id': producto_id,
        'producto_nombre': producto_nombre,
        'rubro_id': rubro_id,
        'familia_id': familia_id,
        'subfamilia_id': subfamilia_id,
        'vendedor_id': vendedor_id,
        'fiscal': fiscal,
        'no_fiscal': no_fiscal,
        'ejecutado': is_filtered_request,
    }

    if not is_filtered_request:
        # Carga inicial: NO ejecutar la consulta a la base de datos hasta que el usuario filtre
        return VentaItem.objects.none(), filtros_dict

    # Base Queryset con select_related optimizado para base de datos e índices
    items = (
        VentaItem.objects.filter(
            venta__empresa_id=empresa_id,
            venta__estado=0  # Ventas activas (se excluyen anuladas)
        )
        .select_related(
            'venta', 'venta__cliente', 'venta__tipo', 'venta__sucursal', 'venta__vendedor',
            'venta__cliente__jurisdiccion', 'producto', 'producto__rubro', 'producto__familia',
            'producto__subfamilia', 'producto__marca', 'producto__proveedor', 'subproducto'
        )
    )

    # Aplicación de filtros opcionales
    if desde:
        items = items.filter(venta__fecha__gte=desde)
    if hasta:
        items = items.filter(venta__fecha__lte=hasta)
    if sucursal_id:
        items = items.filter(venta__sucursal_id=sucursal_id)
    if cliente_id:
        items = items.filter(venta__cliente_id=cliente_id)
    if producto_id:
        items = items.filter(producto_id=producto_id)
    if rubro_id:
        items = items.filter(producto__rubro_id=rubro_id)
    if familia_id:
        items = items.filter(producto__familia_id=familia_id)
    if subfamilia_id:
        items = items.filter(producto__subfamilia_id=subfamilia_id)
    if vendedor_id:
        items = items.filter(venta__vendedor_id=vendedor_id)

    # Filtrado por condición Fiscal / No Fiscal
    condiciones = []
    if fiscal:
        condiciones.append(1)  # Fiscal
    if no_fiscal:
        condiciones.append(2)  # No Fiscal

    if condiciones:
        items = items.filter(venta__condic__in=condiciones)
    else:
        items = items.none()

    items = items.order_by('-venta__fecha', '-venta__ventas_id', 'id')

    return items, filtros_dict


class ReporteVentasProductoView(LoginRequiredMixin, View):
    """
    Vista principal que renderiza el formulario de reporte de ventas por producto.
    No ejecuta consultas pesadas al entrar, esperando a que el usuario filtre.
    """
    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        if not empresa_id:
            messages.warning(request, "Por favor, seleccione una empresa primero.")
            return redirect('seleccion_empresa')

        items, filtros = obtener_items_ventas_filtrados(request)

        # Opciones optimizadas para selectores desplegables (campos estrictamente necesarios)
        sucursales = Sucursal.objects.filter(empresa_id=empresa_id).only('id', 'nombre')
        rubros = Rubro.objects.filter(empresa_id=empresa_id).only('id', 'detalle')
        familias = Familia.objects.filter(empresa_id=empresa_id).only('id', 'detalle')
        subfamilias = Subfamilia.objects.filter(empresa_id=empresa_id).only('id', 'detalle')
        vendedores = User.objects.filter(is_active=True).only('id', 'username').order_by('username')

        # Totales calculados para resumen superior
        totales_resumen = calcular_totales_items(items)

        context = {
            'items': items,
            'filtros': filtros,
            'sucursales': sucursales,
            'rubros': rubros,
            'familias': familias,
            'subfamilias': subfamilias,
            'vendedores': vendedores,
            'totales': totales_resumen,
        }

        return render(request, 'facturacion/reportes/ventas_por_producto.html', context)


def buscar_reporte_ventas_producto(request):
    """
    Endpoint HTMX para búsqueda asíncrona y refresco dinámico de la tabla.
    """
    items, filtros = obtener_items_ventas_filtrados(request)
    totales_resumen = calcular_totales_items(items)

    context = {
        'items': items,
        'filtros': filtros,
        'totales': totales_resumen,
    }
    return render(request, 'facturacion/reportes/partials/tabla_ventas_producto.html', context)


def calcular_totales_items(items):
    """
    Calcula los acumuladores globales para la fila de totales del reporte.
    """
    total_cant = Decimal("0.00")
    total_neto = Decimal("0.00")
    total_iva = Decimal("0.00")
    total_general = Decimal("0.00")

    for item in items:
        cant = Decimal(str(item.cantidad or 0))
        tot = Decimal(str(item.total or 0))
        alic = Decimal(str(item.iva_alicuota or 0))

        factor = Decimal("1.00") + (alic / Decimal("100.00"))
        neto = (tot / factor).quantize(Decimal("0.01")) if factor else tot
        iva = tot - neto

        total_cant += cant
        total_neto += neto
        total_iva += iva
        total_general += tot

    return {
        'cantidad': total_cant,
        'neto': total_neto,
        'iva': total_iva,
        'total': total_general,
    }


def exportar_ventas_producto_csv(request):
    """
    Genera y descarga un archivo CSV que contiene la totalidad de los 74 campos
    coincidiendo exactamente con el formato legacy productos_vendidos_1.csv.
    """
    items, filtros = obtener_items_ventas_filtrados(request)

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    timestamp = timezone.localtime().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="productos_vendidos_{timestamp}.csv"'

    writer = csv.writer(response, delimiter=',')

    # Cabecera de campos del archivo CSV
    header_csv = [
        'id_vta', 'fecha', 'tipo', 'punto', 'numero', 'id_cod', 'cliente',
        't_doc', 'cuit', 'domicilio', 'cpostal', 'localidad', 'provincia',
        'condiva', 'f_p', 'modificado', 'id_usu', 'usuario', 'estacion',
        'moneda', 'cotiz', 'id_asto', 'id_cob', 'fec_cob', 'caja_m', 'cod_qr',
        'iva105', 'iva21', 'iva27', 'cotiz_c', 'n_lista', 'cto_rep', 'fec_act',
        'condic', 'cod_prod', 'cantidad', 'pciot', 'cto_adq', 'neto', 'iva',
        'total', 'pciov', 'fec_adq', 'pciof', 'pciop', 'pciod', 'marca', 'suc',
        'credencial', 'alic_iva', 'stock', 'id_marca', 'serie', 'cuim',
        'cod_prov', 'cod_fab', 'detalle', 'id_prov', 'prove', 'id_sprod',
        'minimo', 'ptopedir', 'stkcons', 'id_rubro', 'id_flia',
        'subprod', 'rubro', 'familia', 'margen', 'mg_rubro',
        'telefono', 'observa'
    ]
    writer.writerow(header_csv)

    # Stock por (producto, sucursal) en UNA consulta (Plan 053).
    from productos.models import StockSucursal
    claves_producto = {i.producto_id for i in items if i.producto_id}
    claves_sucursal = {i.venta.sucursal_id for i in items if i.venta_id and i.venta.sucursal_id}
    stock_por_clave = {}
    if claves_producto and claves_sucursal:
        stock_por_clave = {
            (s['producto_id'], s['sucursal_id']): s['cantidad']
            for s in StockSucursal.objects.filter(
                producto_id__in=claves_producto, sucursal_id__in=claves_sucursal
            ).values('producto_id', 'sucursal_id', 'cantidad')
        }

    for item in items:
        vta = item.venta
        prod = item.producto
        cli = vta.cliente if vta else None
        prov = prod.proveedor if prod else None
        rubro = prod.rubro if prod else None
        flia = prod.familia if prod else None
        marca = prod.marca if prod else None

        cant = Decimal(str(item.cantidad or 0))
        tot = Decimal(str(item.total or 0))
        alic = Decimal(str(item.iva_alicuota or 0))

        factor = Decimal("1.00") + (alic / Decimal("100.00"))
        neto = (tot / factor).quantize(Decimal("0.01")) if factor else tot
        iva = tot - neto

        pcio_t = (tot / cant).quantize(Decimal("0.01")) if cant else Decimal(str(item.precio_unitario or 0))

        # Mapeo a los campos
        row = [
            vta.ventas_id if vta else '',
            vta.fecha.strftime('%d/%m/%Y') if vta and vta.fecha else '',
            vta.tipo.codigo if vta and vta.tipo else '',
            vta.punto if vta else 0,
            vta.numero if vta else 0,
            cli.codigo_id if cli else '',
            vta.cliente_razon_social or (cli.razon_social if cli else ''),
            cli.tipo_documento if cli else '',
            vta.cliente_cuit or (cli.cuit if cli else ''),
            vta.cliente_domicilio or (cli.domicilio if cli else ''),
            cli.codigo_postal if cli else '',
            cli.localidad if cli else '',
            cli.jurisdiccion.nombre if cli and cli.jurisdiccion else '',
            cli.condicion_iva if cli else '',
            1, # f_p
            vta.fec_vta.strftime('%d/%m/%Y %H:%M:%S') if vta and vta.fec_vta else '',
            vta.usuario_id if vta else '',
            vta.usuario.username if vta and vta.usuario else '',
            vta.sucursal_id if vta else 1, # estacion
            item.moneda_origen or (vta.moneda if vta else 'PES'),
            float(vta.cotizacion) if vta else 1.0,
            vta.asiento_id or '',
            '', # id_cob
            vta.fec_cob.strftime('%d/%m/%Y %H:%M:%S') if vta and vta.fec_cob else '',
            '', # caja_m
            vta.cod_qr or '',
            0.0, # iva105
            0.0, # iva21
            0.0, # iva27
            0.0, # cotiz_c
            1,   # n_lista
            float(prod.cto_rep) if prod and prod.cto_rep else 0.0,
            prod.fec_act.strftime('%d/%m/%Y') if prod and prod.fec_act else '',
            vta.condic if vta else 1,
            prod.pk if prod else '',
            float(cant),
            float(pcio_t),
            float(prod.cto_adq) if prod and prod.cto_adq else 0.0,
            float(neto),
            float(iva),
            float(tot),
            float(item.precio_unitario or 0),
            prod.fec_adq.strftime('%d/%m/%Y') if prod and prod.fec_adq else '',
            float(item.precio_unitario or 0), # pciof
            float(item.precio_unitario or 0), # pciop
            0.0, # pciod
            marca.detalle if marca else '',
            vta.sucursal_id if vta else '',
            item.credencial or '',
            float(alic / Decimal("100.00")), # alic_iva en decimal (ej. 0.21)
            # Stock REAL de la sucursal de la venta (Plan 053).
            float(stock_por_clave.get((item.producto_id, vta.sucursal_id if vta else None), 0) or 0),
            marca.pk if marca else 0,
            item.serie or (item.subproducto.serie if item.subproducto else '') or '', # serie
            item.cuim or (item.subproducto.cuim if item.subproducto else '') or '', # cuim
            prod.cod_prov if prod and prod.cod_prov else '',
            prod.cod_fab if prod and prod.cod_fab else '',
            item.concepto or (prod.detalle if prod else ''),
            prov.codigo_id if prov else '',
            prov.razon_social if prov else '',
            item.subproducto_id or 0,  # id_sprod
            float(prod.minimo) if prod and prod.minimo else 0.0,
            float(prod.ptopedir) if prod and prod.ptopedir else 0.0,
            0.0, # stkcons
            rubro.pk if rubro else 0,
            flia.pk if flia else 0,
            1 if prod and prod.subprod else 0,
            rubro.detalle if rubro else '',
            flia.detalle if flia else '',
            float(prod.margen) if prod and prod.margen else 0.0,
            float(rubro.margen) if rubro and rubro.margen else 0.0,
            cli.telefono if cli else '',
            cli.observaciones if cli else ''
        ]
        writer.writerow(row)

    return response


def exportar_ventas_producto_excel(request):
    """
    Endpoint HTTP para descargar el archivo Excel estilizado del reporte.
    """
    empresa_id = request.session.get('empresa_id')
    empresa = Empresa.objects.filter(pk=empresa_id).first() if empresa_id else None
    items, filtros = obtener_items_ventas_filtrados(request)

    return exportar_ventas_producto_excel_service(items, empresa, filtros)


@login_required
def exportar_clientes_excel(request):
    """
    Endpoint HTTP para exportar el listado completo de Clientes y Proveedores en formato Excel.
    Respeta los filtros 'q' y 'tipo', exportando el 100% de los registros sin el límite de 50 filas de la pantalla.
    """
    empresa_id = request.session.get('empresa_id')
    if not empresa_id:
        messages.warning(request, "Por favor, seleccione una empresa primero.")
        return redirect('seleccion_empresa')

    empresa = Empresa.objects.filter(pk=empresa_id).first()

    q = (request.GET.get('q') or '').strip()
    tipo_entidad = (request.GET.get('tipo') or '').strip()

    clientes = ClienteProveedor.objects.filter(empresa_id=empresa_id)

    if q:
        clientes = clientes.filter(Q(razon_social__icontains=q) | Q(cuit__icontains=q))

    tipo_nombre = "Todos"
    if tipo_entidad in ('1', '2'):
        tipo_int = int(tipo_entidad)
        clientes = clientes.filter(tipo_entidad=tipo_int)
        tipo_nombre = "Clientes" if tipo_int == 1 else "Proveedores"

    clientes = clientes.select_related('jurisdiccion', 'armeria').order_by('razon_social')

    filtros = {
        'q': q,
        'tipo_nombre': tipo_nombre
    }

    return exportar_clientes_excel_service(clientes, empresa, filtros)

