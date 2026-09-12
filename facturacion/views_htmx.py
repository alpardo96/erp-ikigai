from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.db import transaction
import json

from .models import ClienteProveedor, Jurisdiccion, Compra, CompraItem, Venta, VentaItem
try:
    from verticalidades.armeria.models import ExtensionArmeria
    from verticalidades.armeria.forms import ExtensionArmeriaForm
except ImportError:
    ExtensionArmeria = None
    ExtensionArmeriaForm = None

try:
    from verticalidades.distribucion.models import ExtensionDistribuidora
    from verticalidades.distribucion.forms import ExtensionDistribuidoraForm
except ImportError:
    ExtensionDistribuidora = None
    ExtensionDistribuidoraForm = None

from .forms import ClienteProveedorForm, JurisdiccionForm

# --- CRUD DE JURISDICCIONES (AFIP) ---

@login_required
def jurisdiccion_modal(request, id=None):
    """
    MODAL DE JURISDICCIÓN (GET/POST)
    - Gestiona códigos AFIP por provincia.
    - HTMX: Dispara 'reloadJurisdicciones'.
    """
    juris = get_object_or_404(Jurisdiccion, id=id) if id else None
    if request.method == 'POST':
        form = JurisdiccionForm(request.POST, instance=juris)
        if form.is_valid():
            form.save()
            response = HttpResponse()
            # Recarga de tabla y cierre de modal
            response['HX-Trigger'] = json.dumps({'reloadJurisdicciones': True, 'cerrarModal': True})
            response['HX-Reswap'] = 'none'
            return response
    else:
        form = JurisdiccionForm(instance=juris)
    return render(request, 'configuracion/modals/jurisdiccion_form.html', {'form': form, 'jurisdiccion': juris})

@login_required
def buscar_jurisdicciones(request):
    """
    BUSCADOR DE PROVINCIAS AFIP
    """
    q = request.GET.get('q', '')
    juris = Jurisdiccion.objects.filter(nombre__icontains=q) if q else Jurisdiccion.objects.all()
    return render(request, 'configuracion/partials/jurisdiccion_table_rows.html', {'jurisdicciones': juris})

@login_required
def lista_productos_resultados(request):
    """
    Filtra productos por columnas específicas o búsqueda general.
    """
    q = request.GET.get('q', '').strip()
    f_id = request.GET.get('f_id', '').strip()
    f_prov = request.GET.get('f_prov', '').strip()
    f_prov_hab = request.GET.get('f_prov_hab', '').strip()
    f_det = request.GET.get('f_det', '').strip()

    filtros = Q()
    
    if q:
        if q.isdigit():
            filtros &= (Q(id=q) | Q(cod_prov__icontains=q) | Q(cod_fab__icontains=q) | Q(detalle__icontains=q))
        else:
            filtros &= (Q(cod_prov__icontains=q) | Q(cod_fab__icontains=q) | Q(detalle__icontains=q))
    
    if f_id:
        if f_id.isdigit():
            filtros &= Q(id=f_id)
        else:
            filtros &= Q(id=-1)
    if f_prov:
        filtros &= Q(cod_prov__icontains=f_prov)
    if f_prov_hab:
        filtros &= Q(proveedor__razon_social__icontains=f_prov_hab)
    if f_det:
        filtros &= Q(detalle__icontains=f_det)

    productos = Producto.objects.filter(filtros).select_related('proveedor').order_by('detalle')[:50]
    return render(request, 'facturacion/partials/productos_search_results.html', {'productos': productos})

@login_required
def eliminar_jurisdiccion(request, id):
    """
    BORRAR JURISDICCIÓN
    """
    if request.method == 'POST':
        juris = get_object_or_404(Jurisdiccion, id=id)
        juris.delete()
        response = HttpResponse()
        response['HX-Trigger'] = json.dumps({'reloadJurisdicciones': True})
        return response
    return HttpResponse(status=400)

# --- CRUD DE CLIENTES/PROVEEDORES (MÓDULO FACTURACIÓN) ---

def _obtener_empresa_id(request):
    """Auxiliar robusto para obtener empresa_id de la sesión o del perfil de usuario."""
    empresa_id = request.session.get('empresa_id')
    if not empresa_id and hasattr(request.user, 'perfil') and request.user.perfil and request.user.perfil.empresa_id:
        empresa_id = request.user.perfil.empresa_id
        request.session['empresa_id'] = empresa_id
    if not empresa_id:
        from empresas.models import Empresa
        emp = Empresa.objects.first()
        if emp:
            empresa_id = emp.id
            request.session['empresa_id'] = empresa_id
    return empresa_id

def buscar_clientes(request):
    """
    BUSCADOR DE CLIENTES Y PROVEEDORES
    - Filtra por Razón Social o CUIT.
    - Si no hay término de búsqueda 'q', ordena por -codigo_id para mostrar las entidades creadas recientemente arriba.
    """
    q = request.GET.get('q', '').strip()
    tipo_entidad = request.GET.get('tipo', '').strip()
    empresa_id = _obtener_empresa_id(request)
    clientes = ClienteProveedor.objects.filter(empresa_id=empresa_id)
    
    if q:
        clientes = clientes.filter(Q(razon_social__icontains=q) | Q(cuit__icontains=q)).order_by('razon_social')
    elif tipo_entidad in ('1', '2'):
        clientes = clientes.filter(tipo_entidad=int(tipo_entidad)).order_by('-codigo_id')
    else:
        clientes = clientes.order_by('-codigo_id')
    
    clientes = clientes.select_related('jurisdiccion', 'armeria')
    
    return render(request, 'facturacion/partials/cliente_table_rows.html', {'clientes': clientes[:100]})

from django.http import JsonResponse

@login_required
def verificar_documento_existente(request):
    """
    Recibe un CUIT/DNI por GET y verifica si ya existe un cliente en la empresa actual.
    Ignora valores vacíos o '0', '00'.
    Devuelve JSON con {"existe": true/false, "cliente": {...}}
    """
    cuit = request.GET.get('cuit', '').strip()
    empresa_id = _obtener_empresa_id(request)
    
    if not cuit or cuit in ['0', '00'] or not empresa_id:
        return JsonResponse({'existe': False})
        
    cliente = ClienteProveedor.objects.filter(
        empresa_id=empresa_id, 
        cuit=cuit, 
        tipo_entidad=1
    ).first()
    
    if cliente:
        return JsonResponse({
            'existe': True,
            'cliente': {
                'id': cliente.codigo_id,
                'razon_social': cliente.razon_social,
                'cuit': cliente.cuit,
                'condicion_iva': cliente.condicion_iva
            }
        })
    return JsonResponse({'existe': False})

@login_required
def consultar_padron_afip(request, cuit):
    """
    Consulta el CUIT en el Padrón A13 de AFIP y devuelve los datos en JSON.
    """
    from .services.afip_padron import AFIPPadronService
    from empresas.models import Empresa
    import traceback
    
    empresa_id = _obtener_empresa_id(request)
    if not empresa_id:
        return JsonResponse({'error': 'No hay empresa activa en la sesión.'}, status=400)
        
    try:
        empresa = Empresa.objects.get(id=empresa_id)
        servicio = AFIPPadronService(empresa)
        datos = servicio.consultar_cuit(cuit)
        return JsonResponse(datos)
    except Exception as e:
        print("AFIP PADRON ERROR:", str(e))
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=400)

def cliente_modal(request, id=None):
    """
    MODAL MAESTRO DE CLIENTE/PROVEEDOR
    - Maneja la lógica triple: Cliente Base + Extensión Armería + Extensión Josen.
    - Utiliza transacciones atómicas para asegurar que o se guarda todo o nada.
    - Verifica permisos granulares para mostrar/validar extensiones.
    """
    empresa_id = _obtener_empresa_id(request)
    cliente = get_object_or_404(ClienteProveedor, codigo_id=id, empresa_id=empresa_id) if id else None
    armeria = getattr(cliente, 'armeria', None) if cliente else None
    distribuidora = getattr(cliente, 'distribuidora', None) if cliente else None

    # puede_armeria depende de si la empresa tiene tipo de actividad ARMERIA
    puede_armeria = False
    # Ídem para DISTRIBUIDORA (Plan 074): coeficiente de precio, zona y bloqueo de crédito.
    puede_distribuidora = False
    if empresa_id:
        from empresas.models import Empresa
        try:
            empresa = Empresa.objects.get(id=empresa_id)
            puede_armeria = (empresa.tipo_actividad == 'ARMERIA')
            puede_distribuidora = (empresa.tipo_actividad == 'DISTRIBUIDORA')
        except Empresa.DoesNotExist:
            pass
            
    origen = request.GET.get('origen') or request.POST.get('origen')

    if request.method == 'POST':
        if puede_armeria:
            tipo_persona = request.POST.get('tipo_persona')
            if tipo_persona == 'F':
                apellido = request.POST.get('cli_apellido', '').strip()
                nombre = request.POST.get('cli_nombre', '').strip()
                if apellido or nombre:
                    request.POST._mutable = True
                    request.POST['razon_social'] = f"{apellido}, {nombre}".strip(', ')
                    request.POST._mutable = False

        form = ClienteProveedorForm(request.POST, instance=cliente, empresa_id=empresa_id)
        form_armeria = ExtensionArmeriaForm(request.POST, instance=armeria) if puede_armeria else None
        form_distribuidora = (ExtensionDistribuidoraForm(request.POST, instance=distribuidora,
                                                         empresa_id=empresa_id)
                              if puede_distribuidora else None)

        form_valid = form.is_valid()
        armeria_valid = (not puede_armeria) or (form_armeria is None) or (not form_armeria.has_changed()) or form_armeria.is_valid()
        distribuidora_valid = ((not puede_distribuidora) or (form_distribuidora is None)
                               or (not form_distribuidora.has_changed())
                               or form_distribuidora.is_valid())

        if form_valid and armeria_valid and distribuidora_valid:
            with transaction.atomic():
                # Lógica de guardado base
                obj = form.save(commit=False)
                # Selecciona clasificación según el radio button 'tipo_entidad' del form
                tipo = int(request.POST.get('tipo_entidad', 1))
                obj.tipo_entidad = tipo
                if tipo == 1:
                    obj.clasificacion = request.POST.get('clasificacion_cli')
                else:
                    obj.clasificacion = request.POST.get('clasificacion_pro')
                
                # CLIPRO: Forzar cuentas contables para Clientes desde parámetros.
                if tipo == 1:
                    from contable.models import ParametrosContables
                    _par = ParametrosContables.objects.filter(
                        empresa_id=empresa_id
                    ).first()
                    if _par:
                        if _par.cta_clientes_default_id:
                            obj.cta_pat = _par.cta_clientes_default_id
                        if _par.cta_ventas_id:
                            obj.cta_res = _par.cta_ventas_id

                if not obj.pk:
                    obj.creado_por = request.user
                    obj.empresa_id = empresa_id # Asignación automática de empresa
                obj.modificado_por = request.user
                obj.save()
                
                # Extensiones
                if puede_armeria and form_armeria and form_armeria.has_changed() and form_armeria.is_valid():
                    ext_a = form_armeria.save(commit=False)
                    ext_a.cliente = obj
                    ext_a.save()

                if (puede_distribuidora and form_distribuidora
                        and form_distribuidora.has_changed() and form_distribuidora.is_valid()):
                    ext_d = form_distribuidora.save(commit=False)
                    ext_d.cliente = obj
                    ext_d.save()
            
            response = HttpResponse()
            if origen in ('venta', 'preventa', 'compra'):
                response['HX-Trigger'] = json.dumps({
                    'clienteVentaSeleccionado': {'id': obj.codigo_id, 'razon_social': obj.razon_social, 'cta_res': obj.cta_res or 0, 'condicion_iva': obj.condicion_iva},
                    'cerrarModal': True
                })
            else:
                response['HX-Trigger'] = json.dumps({'reloadClientes': True, 'cerrarModal': True})
            return response
        else:
            # Si las extensiones fallaron, anexamos sus errores al form principal
            if form_armeria and form_armeria.errors:
                for f, errs in form_armeria.errors.items():
                    for err in errs:
                        form.add_error(None, f"Extensión Armería ({f}): {err}")
            if form_distribuidora and form_distribuidora.errors:
                for f, errs in form_distribuidora.errors.items():
                    for err in errs:
                        form.add_error(None, f"Distribución ({f}): {err}")
    else:
        # Modo GET: Carga forms vacíos o con instancia
        form = ClienteProveedorForm(instance=cliente, empresa_id=empresa_id)
        form_armeria = ExtensionArmeriaForm(instance=armeria) if puede_armeria else None
        form_distribuidora = (ExtensionDistribuidoraForm(instance=distribuidora,
                                                         empresa_id=empresa_id)
                              if puede_distribuidora else None)

        cli_apellido = ''
        cli_nombre = ''
        if cliente and armeria and armeria.tipo_persona == 'F':
            rs = cliente.razon_social or ''
            if ',' in rs:
                parts = rs.split(',', 1)
                cli_apellido = parts[0].strip()
                cli_nombre = parts[1].strip()
            else:
                cli_apellido = rs.strip()
        
    pedir_fecha_nacimiento = False
    if empresa_id:
        from empresas.models import Empresa
        try:
            empresa = Empresa.objects.get(id=empresa_id)
            pedir_fecha_nacimiento = empresa.pedir_fecha_nacimiento_cliente
        except Empresa.DoesNotExist:
            pass

    # Nombres de las cuentas patrimonial/resultado para mostrarlas al editar (el ID se
    # guarda en cta_pat/cta_res, pero el campo visible necesita el nombre) + defaults.
    from contable.models import Cuenta, ParametrosContables
    def _cta_nombre(pk):
        if not pk:
            return ''
        cta = Cuenta.objects.filter(pk=pk, empresa_id=empresa_id).first()
        return f"{cta.jerarquia} - {cta.cuenta}" if cta else ''
    form.cta_pat_nombre = _cta_nombre(getattr(cliente, 'cta_pat', 0)) if cliente else ''
    form.cta_res_nombre = _cta_nombre(getattr(cliente, 'cta_res', 0)) if cliente else ''
    _par = ParametrosContables.objects.filter(empresa_id=empresa_id).first()
    form.default_cta_cli_id = (_par.cta_clientes_default_id or '') if _par else ''
    form.default_cta_cli_nombre = _cta_nombre(_par.cta_clientes_default_id) if _par else ''
    form.default_cta_vta_id = (_par.cta_ventas_id or '') if _par else ''
    form.default_cta_vta_nombre = _cta_nombre(_par.cta_ventas_id) if _par else ''
    form.default_cta_prov_id = (_par.cta_proveedores_default_id or '') if _par else ''
    form.default_cta_prov_nombre = _cta_nombre(_par.cta_proveedores_default_id) if _par else ''

    context = {
        'form': form,
        'form_armeria': form_armeria,
        'form_distribuidora': form_distribuidora,
        'cliente': cliente,
        'puede_armeria': puede_armeria,
        'puede_distribuidora': puede_distribuidora,
        'origen': origen,
        'pedir_fecha_nacimiento': pedir_fecha_nacimiento,
        'cli_apellido': cli_apellido if request.method == 'GET' else '',
        'cli_nombre': cli_nombre if request.method == 'GET' else ''
    }
    return render(request, 'facturacion/modals/cliente_modal.html', context)

@login_required
def buscador_cuentas_modal(request):
    """
    Renderiza el modal de búsqueda de cuentas contables desde facturación.
    """
    return render(request, 'facturacion/modals/buscador_cuentas.html')

@login_required
def buscar_cuentas_facturacion(request):
    """
    Buscador de cuentas contables desde facturación.
    """
    from contable.models import Cuenta
    q = request.GET.get('q', '')
    empresa_id = request.session.get('empresa_id')
    cuentas = Cuenta.objects.filter(empresa_id=empresa_id, imputable=1)
    if q:
        cuentas = cuentas.filter(Q(cuenta__icontains=q) | Q(jerarquia__icontains=q))
    return render(request, 'facturacion/partials/cuentas_search_results.html', {'cuentas': cuentas[:20]})

@login_required
def eliminar_cliente(request, id):
    """
    ELIMINAR CLIENTE/PROVEEDOR
    """
    if request.method == 'POST':
        cliente = get_object_or_404(ClienteProveedor, codigo_id=id, empresa_id=request.session.get('empresa_id'))
        cliente.delete()
        response = HttpResponse()
        response['HX-Trigger'] = json.dumps({'reloadClientes': True})
        return response
    return HttpResponse(status=400)

from productos.models import Producto, StockSucursal
from productos.services.busqueda_service import buscar_productos_inteligente, construir_filtro_busqueda_producto
from empresas.models import Sucursal
from django.db.models import Q

# --- BÚSQUEDA DE PRODUCTOS PARA COMPRAS / REMITOS INTERNOS ---

@login_required
def buscador_productos_modal(request):
    """
    Renderiza el modal de búsqueda de productos.
    Recibe sucursal_origen y sucursal_destino si la búsqueda se inicia desde un formulario
    como Remito Interno. Si sucursal_origen no viene especificada, toma la sucursal activa de la sesión.
    """
    solo_trazables = request.GET.get('solo_trazables', '')
    sucursal_origen_id = request.GET.get('sucursal_origen', '').strip() or str(request.session.get('sucursal_id', ''))
    sucursal_destino_id = request.GET.get('sucursal_destino', '').strip()

    sucursal_origen_obj = None
    if sucursal_origen_id and sucursal_origen_id.isdigit():
        sucursal_origen_obj = Sucursal.objects.filter(id=sucursal_origen_id, empresa_id=request.session.get('empresa_id')).first()

    sucursal_destino_obj = None
    if sucursal_destino_id and sucursal_destino_id.isdigit():
        sucursal_destino_obj = Sucursal.objects.filter(id=sucursal_destino_id, empresa_id=request.session.get('empresa_id')).first()

    return render(request, 'facturacion/modals/buscador_productos.html', {
        'solo_trazables': solo_trazables,
        'sucursal_origen_id': sucursal_origen_id,
        'sucursal_destino_id': sucursal_destino_id,
        'sucursal_origen_obj': sucursal_origen_obj,
        'sucursal_destino_obj': sucursal_destino_obj,
    })

@login_required
def buscar_producto_por_codigo(request):
    """
    Busca un producto por ID, cod_prov o cod_fab y devuelve sus datos básicos.
    """
    q = request.GET.get('q', '').strip()
    if not q:
        return HttpResponse("", status=200)

    filtros = Q(id__iexact=q) | Q(cod_prov__iexact=q) | Q(cod_fab__iexact=q)
    if request.GET.get('solo_trazables') == '1':
        filtros &= Q(subprod=True)

    # Multi-tenant: SIEMPRE acotado a la empresa activa.
    producto = Producto.objects.filter(
        filtros,
        empresa_id=request.session.get('empresa_id'),
    ).first()

    if producto:
        data = {
            'id': producto.id,
            'detalle': producto.detalle.upper(),
            'precio_sugerido': float(producto.cto_rep or 0),
            'cod_prov': producto.cod_prov or '',
            'proveedor_id': producto.proveedor_id or 0,
        }
        response = HttpResponse()
        response['HX-Trigger'] = json.dumps({'productoEncontrado': data})
        return response
    
    return HttpResponse("<span class='text-red-500'>No encontrado</span>", status=200)


@login_required
def buscar_producto_por_codprov(request):
    """Entrada principal de la carga rápida de compras: busca un producto por
    (proveedor habitual seleccionado + cód. del proveedor tipeado de la factura).
    Si lo encuentra, lo carga; si no, avisa para buscar por descripción o crear uno nuevo."""
    q = request.GET.get('q', '').strip()
    proveedor_id = request.GET.get('proveedor', '').strip()
    empresa_id = request.session.get('empresa_id')
    if not q or not proveedor_id:
        return HttpResponse('', status=200)

    producto = Producto.objects.filter(
        empresa_id=empresa_id, proveedor_id=proveedor_id, cod_prov__iexact=q
    ).first()

    response = HttpResponse()
    if producto:
        response['HX-Trigger'] = json.dumps({'codprovEncontrado': {
            'id': producto.id, 'detalle': producto.detalle.upper(), 'cto_rep': float(producto.cto_rep or 0),
        }})
    else:
        response['HX-Trigger'] = json.dumps({'codprovNoExiste': {'cod': q}})
    return response


@login_required
def actualizar_proveedor_habitual(request):
    """Marca al proveedor seleccionado como habitual del producto: actualiza proveedor,
    cod_prov y (opcional) el detalle para igualarlo al de la factura."""
    if request.method != 'POST':
        return HttpResponse(status=405)
    producto = get_object_or_404(
        Producto, id=request.POST.get('producto_id'), empresa_id=request.session.get('empresa_id')
    )
    producto.proveedor_id = request.POST.get('proveedor_id') or None
    producto.cod_prov = (request.POST.get('cod_prov') or '').strip()
    campos = ['proveedor', 'cod_prov']
    detalle = (request.POST.get('detalle') or '').strip()
    if detalle:
        producto.detalle = detalle[:255]
        campos.append('detalle')
    producto.save(update_fields=campos)
    return HttpResponse('OK')


@login_required
def lista_productos_resultados(request):
    """
    Filtra productos por columnas específicas o búsqueda general y calcula
    el stock por sucursal activa/origen y sucursal destino.
    """
    f_id = request.GET.get('f_id', '').strip()
    f_prov = request.GET.get('f_prov', '').strip()
    f_prov_hab = request.GET.get('f_prov_hab', '').strip()
    f_det = request.GET.get('f_det', '').strip()

    filtros = Q()
    if f_id:
        if f_id.isdigit():
            filtros &= Q(id=f_id)
        else:
            filtros &= Q(id=-1)
    if f_prov:
        filtros &= Q(cod_prov__icontains=f_prov)
    if f_prov_hab:
        filtros &= Q(proveedor__razon_social__icontains=f_prov_hab)
    if f_det:
        terminos = [t for t in f_det.split() if t]
        for term in terminos:
            filtros &= (
                Q(detalle__icontains=term) |
                Q(cod_fab__icontains=term) |
                Q(cod_prov__icontains=term) |
                Q(codigo_anterior__icontains=term) |
                Q(marca__detalle__icontains=term)
            )
    if request.GET.get('solo_trazables') == '1':
        filtros &= Q(subprod=True)

    # Multi-tenant: SIEMPRE acotado a la empresa activa.
    productos = list(Producto.objects.filter(
        filtros, empresa_id=request.session.get('empresa_id')
    ).select_related('proveedor').order_by('detalle')[:100])

    items_temp = request.session.get('compra_items_temp', [])
    ids_cargados = [str(item['producto_id']) for item in items_temp]

    # Determinar sucursales a consultar stock
    sucursal_origen_id = request.GET.get('sucursal_origen', '').strip() or str(request.session.get('sucursal_id', ''))
    sucursal_destino_id = request.GET.get('sucursal_destino', '').strip()

    stock_map = {}
    suc_ids_a_consultar = []
    if sucursal_origen_id and sucursal_origen_id.isdigit():
        suc_ids_a_consultar.append(int(sucursal_origen_id))
    if sucursal_destino_id and sucursal_destino_id.isdigit():
        suc_ids_a_consultar.append(int(sucursal_destino_id))

    if productos and suc_ids_a_consultar:
        prod_ids = [p.id for p in productos]
        stocks = StockSucursal.objects.filter(
            producto_id__in=prod_ids,
            sucursal_id__in=suc_ids_a_consultar
        ).values('producto_id', 'sucursal_id', 'cantidad')

        for s in stocks:
            stock_map[(s['producto_id'], s['sucursal_id'])] = s['cantidad']

    for p in productos:
        # Stock sucursal origen / activa
        if sucursal_origen_id and sucursal_origen_id.isdigit():
            p.stock_origen = stock_map.get((p.id, int(sucursal_origen_id)), 0)
        else:
            p.stock_origen = None

        # Stock sucursal destino
        if sucursal_destino_id and sucursal_destino_id.isdigit():
            p.stock_destino = stock_map.get((p.id, int(sucursal_destino_id)), 0)
        else:
            p.stock_destino = None

    return render(request, 'facturacion/partials/productos_search_results.html', {
        'productos': productos,
        'ids_cargados': ids_cargados,
        'sucursal_origen_id': sucursal_origen_id,
        'sucursal_destino_id': sucursal_destino_id,
    })


@login_required
def agregar_item_sesion(request):
    """
    Añade un producto a la lista temporal de la sesión.
    Bloquea duplicados y trata el precio como Total de Línea.
    """
    producto_id = request.POST.get('producto_id', '').strip()
    raw_cantidad = request.POST.get('cantidad', '1').replace('.', '').replace(',', '.')
    raw_precio = request.POST.get('precio', '0').replace('.', '').replace(',', '.')
    raw_precio_lista = request.POST.get('precio_lista', '0').replace('.', '').replace(',', '.')
    try:
        cantidad = float(raw_cantidad or 1)
        total_linea_ingresado = float(raw_precio or 0)
        precio_lista_ingresado = float(raw_precio_lista or 0)
    except (ValueError, TypeError):
        return HttpResponse('<div class="p-4 bg-red-100 text-red-700 font-bold">VALORES INVALIDOS ENVIADOS.</div>', status=200)
    
    if not producto_id:
        items = request.session.get('compra_items_temp', [])
        return render(request, 'facturacion/partials/compra_items_tabla.html', {'items': items})

    items = request.session.get('compra_items_temp')
    if items is None:
        items = []
        request.session['compra_items_temp'] = items
    
    # BLOQUEO DE DUPLICADOS: Si ya está, no dejamos cargar
    if any(str(item['producto_id']) == str(producto_id) for item in items):
        html_error = '<div x-data="{ show: true }" x-show="show" x-init="setTimeout(() => show = false, 5000)" class="p-4 bg-red-100 text-red-700 font-bold mb-2 rounded shadow-sm">Este producto ya está en la lista.</div>'
        html_tabla = render(request, 'facturacion/partials/compra_items_tabla.html', {'items': items}).content.decode('utf-8')
        return HttpResponse(html_error + html_tabla, status=200)

    try:
        producto = Producto.objects.get(id=producto_id, empresa_id=request.session.get('empresa_id'))
    except (Producto.DoesNotExist, ValueError):
        html_error = f'<div x-data="{{ show: true }}" x-show="show" x-init="setTimeout(() => show = false, 5000)" class="p-4 bg-red-100 text-red-700 font-bold mb-2 rounded shadow-sm">Error: Producto ID [{producto_id}] no existe o formato inválido.</div>'
        html_tabla = render(request, 'facturacion/partials/compra_items_tabla.html', {'items': items}).content.decode('utf-8')
        return HttpResponse(html_error + html_tabla, status=200)

    iva_alicuota = float(producto.alic_iva_porc)

    # El precio unitario se calcula: Total / Cantidad
    precio_unitario = total_linea_ingresado / cantidad if cantidad > 0 else 0

    # --- Lógica de costos con bonificación (Fase 4) ---
    # cto_adq: costo de adquisición REAL = neto facturado de la línea / cantidad (ya con bonificación).
    cto_adq = round(precio_unitario, 2)
    # cto_rep: costo de reposición = precio de lista del proveedor. Si no se informa lista,
    # no hay bonificación a discriminar y rep = adq. Si se informa, rep conserva el precio de lista
    # (salvo que el usuario cargue como lista el propio cto_adq, trasladando el descuento al precio).
    cto_rep = round(precio_lista_ingresado, 2) if precio_lista_ingresado > 0 else cto_adq
    descuento = round((1 - cto_adq / cto_rep) * 100, 2) if cto_rep > 0 else 0.0
    # Precio de venta: se recalcula desde cto_rep con el margen del producto (editable en 4B).
    margen = float(producto.margen or 0)
    precio_vta_actual = float(producto.precio_total or 0)
    precio_neto_nuevo = cto_rep * (1 + margen / 100)
    precio_vta_nuevo = round(precio_neto_nuevo * (1 + iva_alicuota / 100), 2)

    # Añadimos nuevo
    items.append({
        'index': len(items),
        'producto_id': producto.id,
        'codigo': producto.cod_prov or producto.id,
        'cod_fab': producto.cod_fab,
        'detalle': producto.detalle,
        'cantidad': cantidad,
        'precio': precio_unitario, # Guardamos el unitario calculado (= cto_adq)
        'iva': iva_alicuota,
        'total': round(total_linea_ingresado, 2), # El total es lo que ingresó el usuario
        # Costos con bonificación (Fase 4)
        'cto_adq': cto_adq,
        'cto_rep': cto_rep,
        'precio_lista': round(precio_lista_ingresado, 2),
        'descuento': descuento,
        'margen': margen,
        'precio_vta_actual': precio_vta_actual,
        'precio_vta_nuevo': precio_vta_nuevo,
        'subprod': producto.subprod,
        'series': [],
    })
    
    request.session['compra_items_temp'] = items
    request.session.modified = True
    
    response = render(request, 'facturacion/partials/compra_items_tabla.html', {'items': items})
    response['HX-Trigger'] = 'limpiarInputsCarga'
    return response

@login_required
def editar_item_sesion(request, index):
    """
    Actualiza el TOTAL de un ítem en la sesión y recalcula su unitario.
    """
    items = request.session.get('compra_items_temp', [])
    if 0 <= index < len(items):
        try:
            total_linea = float(request.POST.get('total_linea', 0).replace('.', '').replace(',', '.') or 0)
            item = items[index]
            item['total'] = total_linea
            cant = float(item['cantidad'])
            # Recalculamos el unitario (= cto_adq) dividiendo por la cantidad
            unit = round(total_linea / cant, 2) if cant > 0 else 0
            item['precio'] = unit
            item['cto_adq'] = unit
            # cto_rep (precio de lista) se conserva; si no había, sigue el cto_adq
            cto_rep = item.get('cto_rep') or unit
            if not item.get('precio_lista'):
                item['cto_rep'] = unit
                cto_rep = unit
            item['descuento'] = round((1 - unit / cto_rep) * 100, 2) if cto_rep > 0 else 0.0
            request.session['compra_items_temp'] = items
        except (ValueError, TypeError):
            pass
            
    response = render(request, 'facturacion/partials/compra_items_tabla.html', {'items': items})
    response['HX-Trigger'] = json.dumps({'actualizarTotales': True})
    return response

@login_required
def quitar_item_sesion(request, index):
    """
    Elimina un ítem de la sesión.
    """
    items = request.session.get('compra_items_temp', [])
    if 0 <= index < len(items):
        items.pop(index)
        # Re-indexar
        for i, item in enumerate(items):
            item['index'] = i
    request.session['compra_items_temp'] = items
    response = render(request, 'facturacion/partials/compra_items_tabla.html', {'items': items})
    response['HX-Trigger'] = json.dumps({'actualizarTotales': True})
    return response

@login_required
def modal_series_item(request, index):
    """
    Retorna el modal para cargar números de serie y CUIM de un subproducto.
    """
    items = request.session.get('compra_items_temp', [])
    if 0 <= index < len(items):
        item = items[index]
        if not item.get('subprod'):
            return HttpResponse("El ítem no requiere series.", status=400)
            
        cantidad = int(float(item['cantidad']))
        series_actuales = item.get('series', [])
        
        # Rellenar con vacíos si faltan
        while len(series_actuales) < cantidad:
            series_actuales.append({'serie': '', 'cuim': ''})
            
        # Recortar si sobra
        if len(series_actuales) > cantidad:
            series_actuales = series_actuales[:cantidad]
            
        return render(request, 'facturacion/modals/compras_series_modal.html', {
            'item': item,
            'index': index,
            'series': series_actuales,
            'cantidad': range(cantidad)
        })
    return HttpResponse("Ítem no encontrado.", status=404)

@login_required
def guardar_series_item(request, index):
    """
    Guarda las series ingresadas en la sesión.
    """
    items = request.session.get('compra_items_temp', [])
    if 0 <= index < len(items):
        item = items[index]
        cantidad = int(float(item['cantidad']))
        
        nuevas_series = []
        for i in range(cantidad):
            serie = request.POST.get(f'serie_{i}', '').strip()
            cuim = request.POST.get(f'cuim_{i}', '').strip()
            if serie:
                from productos.models import Subproducto
                if Subproducto.objects.filter(serie__iexact=serie, empresa_id=request.session.get('empresa_id')).exclude(situacion='VENDIDA').exists():
                    return HttpResponse(f'<div class="p-4 mb-4 text-sm text-red-800 rounded-lg bg-red-50">Error: La serie {serie} ya se encuentra activa en el sistema y no ha sido vendida.</div>', status=400)
                nuevas_series.append({'serie': serie, 'cuim': cuim})
                
        item['series'] = nuevas_series
        request.session['compra_items_temp'] = items
        request.session.modified = True
        
        # Retornamos la tabla actualizada
        response = render(request, 'facturacion/partials/compra_items_tabla.html', {'items': items})
        return response
    return HttpResponse("Ítem no encontrado.", status=404)

@login_required
def compras_revisar_precios(request):
    """
    Modal de revisión de precios de venta antes de guardar la compra.
    Lista los productos de la sesión con el precio de venta actual y el nuevo
    (recalculado desde cto_rep × margen), editable y con redondeo, para confirmar.
    """
    items = request.session.get('compra_items_temp', [])
    return render(request, 'facturacion/modals/revisar_precios.html', {'items': items})


@login_required
def importar_remito_items(request):
    """
    Busca un remito por número y proveedor, y carga sus ítems en la sesión actual.
    """
    remito_num = request.GET.get('remito_num')
    proveedor_id = request.GET.get('proveedor')
    
    if not remito_num or not proveedor_id:
        return HttpResponse("Faltan datos para la búsqueda.", status=400)
    
    # Buscamos el remito
    from .models import Compra
    remito = Compra.objects.filter(
        tipo='Remito',
        numero=remito_num,
        proveedor_id=proveedor_id,
        empresa_id=request.session.get('empresa_id')
    ).first()
    
    if not remito:
        return HttpResponse("Remito no encontrado.", status=404)
        
    # LIMPIAMOS LA SESIÓN: Una factura nace de UN remito, no es un rejunte.
    items = []
    
    # Importamos cada item del remito a la sesión
    for ri in remito.items.all():
        items.append({
            'index': len(items),
            'producto_id': ri.producto.id,
            'codigo': ri.producto.cod_prov or ri.producto.id,
            'cod_fab': ri.producto.cod_fab,
            'detalle': ri.producto.detalle,
            'cantidad': float(ri.cantidad),
            'precio': float(ri.precio_unitario),
            'iva': float(ri.iva_alicuota),
            'total': float(ri.total)
        })
        
    request.session['compra_items_temp'] = items
    response = render(request, 'facturacion/partials/compra_items_tabla.html', {'items': items})
    response['HX-Trigger'] = json.dumps({
        'vincularRemitoID': remito.compras_id,
        'vincularRemitoData': f"{remito.punto:04d}-{remito.numero}",
        'actualizarTotales': True,
        'cerrarModal': True
    })
    return response

# --- BUSCADOR DE REMITOS PENDIENTES ---

@login_required
def buscador_remitos_modal(request):
    """
    Muestra un modal con la lista de remitos del proveedor seleccionado.
    """
    proveedor_id = request.GET.get('proveedor')
    if not proveedor_id:
        return HttpResponse("<div class='p-4 text-red-500 font-bold'>Seleccione un proveedor primero.</div>", status=400)
    
    proveedor = get_object_or_404(ClienteProveedor, codigo_id=proveedor_id, empresa_id=request.session.get('empresa_id'))
    sucursal_id = request.session.get('sucursal_id')

    from .models import Recepcion
    
    # Buscamos los remitos de este proveedor que NO hayan sido generados por factura y estén activos
    remitos = Recepcion.objects.filter(
        empresa_id=request.session.get('empresa_id'),
        proveedor=proveedor,
        estado=Recepcion.ACTIVA,
        generada_por_factura__isnull=True
    ).order_by('-fecha', '-numero')[:20]

    return render(request, 'facturacion/modals/buscador_remitos.html', {
        'remitos': remitos,
        'proveedor': proveedor
    })
# --- BÚSQUEDA DE PRODUCTOS PARA VENTAS ---

@login_required
def buscador_productos_venta_modal(request):
    """
    Modal de búsqueda de productos optimizado para ventas (muestra stock).
    """
    return render(request, 'facturacion/modals/buscador_productos_venta.html')

def calcular_precio_sugerido(producto, moneda_venta, cotizacion_dolar):
    """
    Sugiere el precio de lista según la moneda en la que se está operando (PES o DOL)
    y la moneda original del producto.
    """
    precio = float(producto.precio_total or 0)
    moneda_prod = getattr(producto, 'moneda', 'PES')
    if not cotizacion_dolar or cotizacion_dolar <= 0:
        cotizacion_dolar = 1.0
        
    if moneda_venta == 'DOL':
        if moneda_prod == 'DOL':
            return round(precio, 2)
        else:
            return round(precio / cotizacion_dolar, 2)
    else:  # 'PES'
        if moneda_prod == 'DOL':
            return round(precio * cotizacion_dolar, 2)
        else:
            return round(precio, 2)

@login_required
def buscar_producto_venta_por_codigo(request):
    """
    Busca producto para venta y devuelve stock en sucursal actual.
    """
    q = request.GET.get('q', '').strip()
    producto_id = request.GET.get('id') or request.GET.get('producto_id')
    moneda_venta = request.GET.get('moneda') or request.session.get('venta_moneda', 'PES')
    sucursal_id = request.session.get('sucursal_id')
    empresa_id = request.session.get('empresa_id')
    if not q and not producto_id:
        return HttpResponse("", status=200)

    from empresas.models import CotizacionMoneda
    cotizacion = 1.0
    if empresa_id:
        try:
            cot_obj = CotizacionMoneda.objects.get(empresa_id=empresa_id)
            cotizacion = float(cot_obj.dolar_venta)
        except CotizacionMoneda.DoesNotExist:
            pass

    # Multi-tenant: SIEMPRE acotado a la empresa activa.
    producto = None

    # Prioridad 0: Si viene id / producto_id explícito (desde modal o selector)
    if producto_id:
        producto = Producto.objects.filter(id=producto_id, empresa_id=empresa_id).first()

    # Prioridad 1: Si 'q' es un número entero, buscar coincidencia EXACTA por primary key ID
    if not producto and q and q.isdigit():
        producto = Producto.objects.filter(id=int(q), empresa_id=empresa_id).first()

    # Prioridad 2: Coincidencia EXACTA por cod_prov, cod_fab o codigo_anterior
    if not producto and q:
        producto = Producto.objects.filter(
            Q(cod_prov__iexact=q) | Q(cod_fab__iexact=q) | Q(codigo_anterior__iexact=q),
            empresa_id=empresa_id,
        ).first()

    # Prioridad 3: Fallback a búsqueda inteligente multi-término
    if not producto and q:
        producto = buscar_productos_inteligente(
            q=q,
            empresa_id=empresa_id,
            limit=1
        ).first()

    if producto:
        # Buscamos stock en sucursal
        from productos.models import StockSucursal
        stk = StockSucursal.objects.filter(producto=producto, sucursal_id=sucursal_id).first()
        stock_actual = float(stk.cantidad) if stk else 0
        
        precio_sug = calcular_precio_sugerido(producto, moneda_venta, cotizacion)
        data = {
            'id': producto.id,
            'detalle': producto.detalle.upper(),
            'precio_sugerido': float(precio_sug),
            'stock': stock_actual,
            'requiere_credencial': bool(producto.creden),
            'subprod': bool(producto.subprod)
        }
        response = HttpResponse()
        response['HX-Trigger'] = json.dumps({'productoVentaEncontrado': data})
        return response
    
    return HttpResponse("<span class='text-red-500'>No encontrado</span>", status=200)

@login_required
def lista_productos_venta_resultados(request):
    """
    Filtra productos para venta con stock y búsqueda inteligente multi-término.
    """
    f_id = request.GET.get('f_id', '').strip()
    f_fab = request.GET.get('f_fab', '').strip()
    f_det = request.GET.get('f_det', '').strip()
    sucursal_id = request.session.get('sucursal_id')
    empresa_id = request.session.get('empresa_id')

    if f_det:
        productos_qs, _ = construir_filtro_busqueda_producto(
            q=f_det,
            empresa_id=empresa_id,
            excluir_subprod=False
        )
    else:
        productos_qs = Producto.objects.filter(empresa_id=empresa_id).order_by('detalle')

    if f_id:
        if f_id.isdigit():
            productos_qs = productos_qs.filter(id=int(f_id))
        else:
            productos_qs = productos_qs.none()

    if f_fab:
        productos_qs = productos_qs.filter(cod_fab__icontains=f_fab)

    productos_qs = productos_qs.prefetch_related('existencias')[:100]

    # Obtener cotizacion actual
    from empresas.models import CotizacionMoneda
    empresa_id = request.session.get('empresa_id')
    cotizacion = 1.0
    if empresa_id:
        try:
            cotiz_obj = CotizacionMoneda.objects.get(empresa_id=empresa_id)
            cotizacion = float(cotiz_obj.dolar_venta)
        except CotizacionMoneda.DoesNotExist:
            pass

    moneda_venta = request.GET.get('moneda') or request.session.get('venta_moneda', 'PES')
    productos = []
    for p in productos_qs:
        p.precio_pesificado = float(p.precio_total or 0) * cotizacion if p.moneda == 'DOL' else float(p.precio_total or 0)
        p.precio_mostrar = calcular_precio_sugerido(p, moneda_venta, cotizacion)
        
        # Calcular stocks
        stock_local = 0
        stock_otros = 0
        for stk in p.existencias.all():
            if str(stk.sucursal_id) == str(sucursal_id):
                stock_local += stk.cantidad
            else:
                stock_otros += stk.cantidad
                
        p.stock_local = stock_local
        p.stock_otros = stock_otros
        productos.append(p)

    return render(request, 'facturacion/partials/productos_venta_search_results.html', {
        'productos': productos,
        'sucursal_id': sucursal_id,
        'cotizacion_dolar': cotizacion,
        'moneda_venta': moneda_venta
    })

@login_required
def agregar_item_venta_sesion(request):
    """
    Añade un producto a la venta en sesión.
    """
    producto_id = request.POST.get('producto_id')
    sucursal_id = request.session.get('sucursal_id')
    try:
        cantidad = float(request.POST.get('cantidad', 1) or 1)
        
        raw_precio = str(request.POST.get('precio', '0'))
        if ',' in raw_precio:
            raw_precio = raw_precio.replace('.', '').replace(',', '.')
        precio_lista = float(raw_precio or 0)
        
        raw_descuento = str(request.POST.get('descuento', '0'))
        if ',' in raw_descuento:
            raw_descuento = raw_descuento.replace('.', '').replace(',', '.')
        descuento = float(raw_descuento or 0)
        
        credencial = request.POST.get('credencial', '').strip()
        dmp = float(request.POST.get('dmp', 0) or 0)
    except (ValueError, TypeError):
        return HttpResponse("Valores inválidos.", status=400)
    
    moneda_anterior = request.session.get('venta_moneda', 'PES')
    moneda = request.POST.get('moneda') or request.GET.get('moneda') or moneda_anterior
    request.session['venta_moneda'] = moneda

    if not producto_id:
        items = request.session.get('venta_items_temp', [])
        if moneda != moneda_anterior and items:
            from empresas.models import CotizacionMoneda
            empresa_id = request.session.get('empresa_id')
            cotizacion_global = 1.0
            if empresa_id:
                try:
                    cot_obj = CotizacionMoneda.objects.get(empresa_id=empresa_id)
                    cotizacion_global = float(cot_obj.dolar_venta)
                except CotizacionMoneda.DoesNotExist:
                    cotizacion_global = 1.0
            
            if cotizacion_global > 0:
                for item in items:
                    precio_actual = float(item.get('precio', 0))
                    if moneda_anterior == 'PES' and moneda == 'DOL':
                        nuevo_precio = round(precio_actual / cotizacion_global, 2)
                    elif moneda_anterior == 'DOL' and moneda == 'PES':
                        nuevo_precio = round(precio_actual * cotizacion_global, 2)
                    else:
                        nuevo_precio = round(precio_actual, 2)
                    
                    cantidad = float(item.get('cantidad', 1))
                    descuento = float(item.get('descuento', 0))
                    subtotal = nuevo_precio * cantidad
                    total_final = subtotal * (1 - (descuento / 100.0))
                    
                    item['precio'] = nuevo_precio
                    item['total'] = round(total_final, 2)
                    item['cotizacion_aplicada'] = cotizacion_global
                
                request.session['venta_items_temp'] = items
                request.session.modified = True

        response = render(request, 'facturacion/partials/venta_items_tabla.html', {
            'items': items,
            'moneda': moneda
        })
        response['HX-Trigger'] = json.dumps({
            'actualizarTotalesVenta': {
                'requiere_autorizacion': any(i.get('requiere_autorizacion', False) for i in items)
            }
        })
        return response

    items = request.session.get('venta_items_temp', [])
    
    if any(str(item['producto_id']) == str(producto_id) for item in items):
        return HttpResponse("Este producto ya fue cargado.", status=400)

    producto = get_object_or_404(Producto, id=producto_id, empresa_id=request.session.get('empresa_id'))
    if producto.subprod:
        return HttpResponse('<div class="p-4 mb-4 text-sm text-red-800 rounded-lg bg-red-50">Este producto es trazable y debe cargarse por Venta Trazabilidad.</div>', status=400)
        
    iva_alicuota = float(producto.alic_iva_porc)
    
    if producto.creden and not credencial:
        return HttpResponse("Este producto requiere CREDENCIAL obligatoria.", status=400)

    if producto.creden or producto.subprod:
        cliente_id = request.POST.get('cliente') or request.POST.get('cliente_id')
        if cliente_id:
            from .helpers import validar_clu_cliente_armeria
            es_valido, msj_err = validar_clu_cliente_armeria(cliente_id, request.session.get('empresa_id'))
            if not es_valido:
                return HttpResponse(msj_err, status=400)
    
    # Base de precio de lista oficial desde el catálogo del producto
    precio_lista = float(producto.precio_total or 0.0)
    
    # Lógica de Pesificación (Bimonetarismo)
    from empresas.models import CotizacionMoneda, Empresa as _Empresa
    moneda_origen = producto.moneda
    cotizacion_aplicada = 1.0
    precio_origen = precio_lista  # El precio base en moneda origen
    
    if moneda == 'DOL':
        empresa_id = request.session.get('empresa_id')
        try:
            cot_obj = CotizacionMoneda.objects.get(empresa_id=empresa_id)
            cotizacion_aplicada = float(cot_obj.dolar_venta)
        except CotizacionMoneda.DoesNotExist:
            cotizacion_aplicada = 1.0
        precio_lista = round(precio_lista, 2)
    else:
        cotizacion_aplicada = 1.0
        if moneda_origen == 'DOL':
            empresa_id = request.session.get('empresa_id')
            try:
                cot_obj = CotizacionMoneda.objects.get(empresa_id=empresa_id)
                cotizacion_aplicada = float(cot_obj.dolar_venta)
            except CotizacionMoneda.DoesNotExist:
                cotizacion_aplicada = 1.0
            precio_lista = round(precio_lista * cotizacion_aplicada, 2)
        else:
            cotizacion_aplicada = 1.0
            precio_lista = round(precio_lista, 2)

    # Modo de edición en facturación (PRECIO o DESCUENTO)
    empresa_activa = _Empresa.objects.filter(pk=request.session.get('empresa_id')).first()
    modo_edicion = getattr(empresa_activa, 'modo_edicion_facturacion', 'DESCUENTO')
    
    alerta_precio_duplicado = False
    precio_base = precio_lista

    if modo_edicion == 'PRECIO':
        # En modo PRECIO se toma el precio ingresado por el usuario
        raw_precio = str(request.POST.get('precio', '')).strip().replace('.', '').replace(',', '.')
        if raw_precio != '':
            try:
                precio_ingresado = float(raw_precio)
            except (ValueError, TypeError):
                precio_ingresado = precio_lista
        else:
            precio_ingresado = precio_lista

        # Validaciones de precio mayor / menor
        if precio_ingresado < precio_lista and precio_lista > 0:
            precio_unitario_final = precio_lista
            descuento = round(((precio_lista - precio_ingresado) / precio_lista) * 100.0, 2)
            total_final = precio_ingresado * cantidad
        else:
            precio_unitario_final = precio_ingresado
            descuento = 0.0
            total_final = precio_unitario_final * cantidad

        if precio_ingresado > (precio_lista * 2) and precio_lista > 0:
            alerta_precio_duplicado = True
    else:
        # En modo DESCUENTO se utiliza el descuento ingresado por el usuario
        precio_unitario_final = precio_lista
        subtotal = precio_lista * cantidad
        total_final = subtotal * (1 - (descuento / 100.0))

    descuento_maximo = float(producto.rubro.descuento_maximo) if producto.rubro else 0.0
    requiere_autorizacion = descuento > descuento_maximo
    
    # Evaluar stock actual en la sucursal
    from productos.models import StockSucursal
    stk = StockSucursal.objects.filter(producto=producto, sucursal_id=sucursal_id).first()
    stock_actual = float(stk.cantidad) if stk else 0
    alerta_stock = cantidad > stock_actual
    
    items.append({
        'index': len(items),
        'producto_id': producto.id,
        'codigo': producto.id,
        'cod_prov': producto.cod_prov,
        'detalle': producto.detalle,
        'cantidad': cantidad,
        'precio': precio_unitario_final, # En PESOS
        'precio_base': precio_base,
        'descuento': descuento,
        'descuento_maximo': descuento_maximo,
        'iva': iva_alicuota,
        'total': round(total_final, 2), # En PESOS
        'requiere_autorizacion': requiere_autorizacion,
        'alerta_precio_duplicado': alerta_precio_duplicado,
        'credencial': credencial,
        'dmp': dmp,
        'alerta_stock': alerta_stock,
        'stock_disponible': stock_actual,
        'moneda_origen': moneda_origen,
        'cotizacion_aplicada': cotizacion_aplicada,
        'precio_origen': precio_origen
    })
    
    request.session['venta_items_temp'] = items
    response = render(request, 'facturacion/partials/venta_items_tabla.html', {
        'items': items,
        'moneda': request.session.get('venta_moneda', 'PES'),
        'modo_edicion': modo_edicion
    })
    response['HX-Trigger'] = json.dumps({
        'limpiarInputsCargaVenta': True,
        'actualizarTotalesVenta': {
            'requiere_autorizacion': any(i.get('requiere_autorizacion', False) for i in items),
            'alerta_precio_duplicado': alerta_precio_duplicado
        }
    })
    return response

@login_required
def quitar_item_venta_sesion(request, index):
    """
    Elimina un ítem de la venta en sesión.
    """
    from empresas.models import Empresa as _Empresa
    empresa_activa = _Empresa.objects.filter(pk=request.session.get('empresa_id')).first()
    modo_edicion = getattr(empresa_activa, 'modo_edicion_facturacion', 'DESCUENTO')

    items = request.session.get('venta_items_temp', [])
    if 0 <= index < len(items):
        items.pop(index)
        for i, item in enumerate(items):
            item['index'] = i
    request.session['venta_items_temp'] = items
    response = render(request, 'facturacion/partials/venta_items_tabla.html', {
        'items': items,
        'moneda': request.session.get('venta_moneda', 'PES'),
        'modo_edicion': modo_edicion
    })
    response['HX-Trigger'] = json.dumps({
        'actualizarTotalesVenta': {
            'requiere_autorizacion': any(i.get('requiere_autorizacion', False) for i in items)
        }
    })
    return response

@login_required
def editar_item_venta_sesion(request, index):
    """
    Actualiza precio unitario, descuento o total de un ítem de venta en la sesión.
    """
    from empresas.models import Empresa as _Empresa
    empresa_activa = _Empresa.objects.filter(pk=request.session.get('empresa_id')).first()
    modo_edicion = getattr(empresa_activa, 'modo_edicion_facturacion', 'DESCUENTO')

    items = request.session.get('venta_items_temp', [])
    if 0 <= index < len(items):
        try:
            item = items[index]
            precio_base = float(item.get('precio_base', item.get('precio', 0)) or 0)
            cantidad = float(item.get('cantidad', 1) or 1)

            if modo_edicion == 'PRECIO':
                if 'precio' in request.POST:
                    precio_ingresado = parsear_decimal_ar(request.POST.get('precio', '0'), default=precio_base)
                    if precio_ingresado < precio_base and precio_base > 0:
                        item['precio'] = precio_base
                        item['descuento'] = round(((precio_base - precio_ingresado) / precio_base) * 100.0, 2)
                        item['total'] = round(precio_ingresado * cantidad, 2)
                    else:
                        item['precio'] = precio_ingresado
                        item['descuento'] = 0.0
                        item['total'] = round(precio_ingresado * cantidad, 2)
                    item['alerta_precio_duplicado'] = precio_ingresado > (precio_base * 2) if precio_base > 0 else False
            else:
                if 'descuento' in request.POST:
                    item['descuento'] = parsear_decimal_ar(request.POST.get('descuento', '0'), default=0.0)
                if 'precio' in request.POST:
                    item['precio'] = parsear_decimal_ar(request.POST.get('precio', '0'), default=0.0)
                
                precio_lista = float(item.get('precio', 0) or 0)
                descuento = float(item.get('descuento', 0) or 0)
                subtotal = precio_lista * cantidad
                item['total'] = round(subtotal * (1 - (descuento / 100.0)), 2)
            
            descuento_maximo = float(item.get('descuento_maximo', 0))
            item['requiere_autorizacion'] = float(item.get('descuento', 0)) > descuento_maximo
            request.session['venta_items_temp'] = items
        except (ValueError, TypeError):
            pass
            
    response = render(request, 'facturacion/partials/venta_items_tabla.html', {
        'items': items,
        'moneda': request.session.get('venta_moneda', 'PES'),
        'modo_edicion': modo_edicion
    })
    response['HX-Trigger'] = json.dumps({
        'limpiarInputsCargaVenta': False,
        'actualizarTotalesVenta': {
            'requiere_autorizacion': any(i.get('requiere_autorizacion', False) for i in items)
        }
    })
    return response

# --- BÚSQUEDA DE CLIENTES PARA VENTAS ---

@login_required
def buscador_clientes_venta_modal(request):
    """
    Modal de búsqueda de clientes optimizado para ventas.
    """
    return render(request, 'facturacion/modals/buscador_clientes_venta.html')

@login_required
def lista_clientes_venta_resultados(request):
    """
    Filtra clientes para venta.
    """
    q = request.GET.get('q', '').strip()
    empresa_id = request.session.get('empresa_id')
    
    filtros = Q(empresa_id=empresa_id) 
    if q:
        filtros &= (Q(razon_social__icontains=q) | Q(cuit__icontains=q))

    clientes = ClienteProveedor.objects.filter(filtros).order_by('razon_social')[:30]
    
    return render(request, 'facturacion/partials/clientes_venta_search_results.html', {
        'clientes': clientes,
    })

@login_required
def venta_cliente_detalle(request, id):
    """
    Devuelve los detalles de un cliente para ser editados en la Carga de Ventas.
    """
    cliente = get_object_or_404(ClienteProveedor, pk=id)
    from .models import Jurisdiccion, ExtensionArmeria
    from empresas.models import Empresa
    from django.utils import timezone
    jurisdicciones = Jurisdiccion.objects.all()
    
    armeria = None
    empresa_id = request.session.get('empresa_id')
    if empresa_id:
        try:
            empresa = Empresa.objects.get(pk=empresa_id)
            if empresa.tipo_actividad and empresa.tipo_actividad.lower() == 'armeria':
                try:
                    armeria = ExtensionArmeria.objects.get(cliente=cliente)
                except ExtensionArmeria.DoesNotExist:
                    pass
        except Empresa.DoesNotExist:
            pass
    
    return render(request, 'facturacion/partials/venta_cliente_detalle.html', {
        'cliente': cliente,
        'doc_tipos': ClienteProveedor.DOC_TIPOS,
        'condicion_iva_choices': ClienteProveedor.CONDICION_IVA_CHOICES,
        'jurisdicciones': jurisdicciones,
        'armeria': armeria,
        'hoy': timezone.localdate(),
    })

# --- CRUD DE TIPOS DE COMPROBANTE ---

@login_required
def comprobante_modal(request, id=None):
    from .models import TipoComprobante
    from .forms import TipoComprobanteForm
    comprobante = get_object_or_404(TipoComprobante, id=id) if id else None
    if request.method == 'POST':
        form = TipoComprobanteForm(request.POST, instance=comprobante)
        if form.is_valid():
            form.save()
            response = HttpResponse()
            response['HX-Trigger'] = json.dumps({'reloadComprobantes': True, 'cerrarModal': True})
            response['HX-Reswap'] = 'none'
            return response
    else:
        form = TipoComprobanteForm(instance=comprobante)
    return render(request, 'configuracion/modals/comprobante_form.html', {'form': form, 'comprobante': comprobante})

@login_required
def buscar_comprobantes(request):
    from .models import TipoComprobante
    q = request.GET.get('q', '')
    comprobantes = TipoComprobante.objects.filter(detalle__icontains=q) if q else TipoComprobante.objects.all()
    return render(request, 'configuracion/partials/comprobante_table_rows.html', {'comprobantes': comprobantes})

@login_required
def eliminar_comprobante(request, id):
    from .models import TipoComprobante
    if request.method == 'POST':
        comprobante = get_object_or_404(TipoComprobante, id=id)
        comprobante.delete()
        response = HttpResponse()
        response['HX-Trigger'] = json.dumps({'reloadComprobantes': True})
        return response
    return HttpResponse(status=400)

@login_required
def preventas_item_add(request):
    producto_id = request.POST.get('producto_id')
    credencial = request.POST.get('credencial', '').strip()
    from .helpers import parsear_decimal_ar
    dmp = parsear_decimal_ar(request.POST.get('dmp', 0))
    try:
        cantidad = parsear_decimal_ar(request.POST.get('cantidad', '1'), default=1.0)
        precio_lista = parsear_decimal_ar(request.POST.get('precio', '0'), default=0.0)
        descuento = parsear_decimal_ar(request.POST.get('descuento', '0'), default=0.0)
    except (ValueError, TypeError):
        return HttpResponse("<div class='p-4 bg-red-100 text-red-700 font-bold'>Valores inválidos.</div>", status=200)
    
    items = request.session.get('preventa_items_temp', [])
    
    if not producto_id:
        return render(request, 'facturacion/partials/preventa_items_tabla.html', {
            'items': items,
            'moneda': 'PES'
        })

    if any(str(item['producto_id']) == str(producto_id) for item in items):
        return HttpResponse("<div class='p-4 bg-red-100 text-red-700 font-bold'>Este producto ya fue cargado.</div>", status=200)

    from productos.models import Producto
    from empresas.models import CotizacionMoneda
    from .helpers import validar_clu_cliente_armeria
    producto = get_object_or_404(Producto, id=producto_id, empresa_id=request.session.get('empresa_id'))

    # Validación de exclusividad de armas (SIGIMAC / subprod=True)
    if producto.subprod:
        if len(items) > 0:
            return HttpResponse("<div class='p-4 bg-red-100 text-red-700 font-bold'>Las armas/artículos trazables (SIGIMAC) deben reservarse en una preventa individual exclusiva.</div>", status=200)
        if cantidad != 1:
            return HttpResponse("<div class='p-4 bg-red-100 text-red-700 font-bold'>La cantidad de reserva para un arma trazable debe ser exactamente 1 unidad.</div>", status=200)
    else:
        if any(item.get('subprod', False) for item in items):
            return HttpResponse("<div class='p-4 bg-red-100 text-red-700 font-bold'>Esta preventa es exclusiva para la reserva de un arma. Para otros productos debe generar una preventa separada.</div>", status=200)

    # Validación para empresas tipo ARMERÍA:
    # No se permite facturar productos con creden = True a clientes sin identificar (tipo_documento = 99 / Consumidor Final)
    from empresas.models import Empresa as _Empresa
    from facturacion.models import ClienteProveedor
    empresa_id = request.session.get('empresa_id')
    es_armeria = _Empresa.objects.filter(id=empresa_id, tipo_actividad__iexact="ARMERIA").exists()

    if es_armeria and producto.creden:
        cliente_id = request.POST.get('cliente') or request.POST.get('cliente_id') or request.POST.get('id_cliente')
        cliente_obj = None
        if cliente_id:
            cliente_obj = ClienteProveedor.objects.filter(pk=cliente_id, empresa_id=empresa_id).first()
        if not cliente_obj or cliente_obj.tipo_documento == '99' or cliente_obj.codigo_id == 1:
            return HttpResponse(
                "<div class='p-3.5 bg-amber-50 border-l-4 border-amber-500 text-amber-900 font-black text-[11px] rounded shadow-sm'>"
                "⚠️ Debe identificar al cliente que compra este tipo de producto. Para poder avanzar debe seleccionar al cliente real."
                "</div>",
                status=200
            )

    # En Preventas, la credencial solo se exige cuando creden=True y subprod=False
    # (en armas/subprod=True es solo un anticipo/reserva y no aplica pedir credencial aquí)
    if producto.creden and not producto.subprod and not credencial:
        return HttpResponse("<div class='p-4 bg-red-100 text-red-700 font-bold'>Este producto requiere CREDENCIAL obligatoria.</div>", status=200)

    # Nota: En Preventas no opera la restricción de CLU vigente ya que aquí
    # no se factura ni entrega el arma, sólo se genera la preventa/reserva (la traba
    # opera en Ventas con Trazabilidad).

    # Base de precio de lista oficial desde el catálogo del producto
    precio_lista = float(producto.precio_total or 0.0)
    moneda_origen = producto.moneda
    cotizacion_aplicada = 1.0
    precio_origen = precio_lista
    
    if moneda_origen == 'DOL':
        empresa_id = request.session.get('empresa_id')
        try:
            cot_obj = CotizacionMoneda.objects.get(empresa_id=empresa_id)
            cotizacion_aplicada = float(cot_obj.dolar_venta)
        except CotizacionMoneda.DoesNotExist:
            cotizacion_aplicada = 1.0
            
        precio_lista = round(precio_lista * cotizacion_aplicada, 2)
    
    # --- Distribución (Plan 074): el precio lo define el coeficiente del cliente ---
    # Se recalcula en el servidor y no se confía en lo que mandó el navegador: el importe
    # que ve el vendedor tiene que ser exactamente el que después se factura.
    from empresas.models import Empresa as _Empresa
    empresa_id = request.session.get('empresa_id')
    disponible_producto = None
    if _Empresa.objects.filter(id=empresa_id, tipo_actividad='DISTRIBUIDORA').exists():
        from verticalidades.distribucion.services.precios import precio_para
        from productos.services.stock_service import disponible_real

        cliente_id_dist = request.POST.get('cliente') or request.POST.get('cliente_id')
        if cliente_id_dist:
            cliente_dist = ClienteProveedor.objects.filter(
                pk=cliente_id_dist, empresa_id=empresa_id).first()
            if cliente_dist:
                precio_lista = float(precio_para(producto, cliente_dist))
                precio_origen = precio_lista
        sucursal_id = request.session.get('sucursal_id')
        if sucursal_id:
            disponible_producto = float(disponible_real(producto.id, sucursal_id))

    # Modo de edición en facturación (PRECIO o DESCUENTO)
    empresa_activa = _Empresa.objects.filter(pk=request.session.get('empresa_id')).first()
    modo_edicion = getattr(empresa_activa, 'modo_edicion_facturacion', 'DESCUENTO')
    
    alerta_precio_duplicado = False
    precio_base = precio_lista

    if modo_edicion == 'PRECIO':
        # En modo PRECIO se toma el precio ingresado por el usuario
        raw_precio = request.POST.get('precio')
        if raw_precio is not None and str(raw_precio).strip() != '':
            precio_ingresado = parsear_decimal_ar(raw_precio, default=precio_lista)
        else:
            precio_ingresado = precio_lista

        # Validaciones de precio mayor / menor contra el precio de lista oficial
        if precio_ingresado < precio_lista and precio_lista > 0:
            # Se conserva el precio de lista base en precio_unitario y el total refleja el precio ingresado
            precio_unitario_final = precio_lista
            descuento = round(((precio_lista - precio_ingresado) / precio_lista) * 100.0, 2)
            total_final = precio_ingresado * cantidad
        else:
            precio_unitario_final = precio_ingresado
            descuento = 0.0
            total_final = precio_unitario_final * cantidad

        if precio_ingresado > (precio_lista * 2) and precio_lista > 0:
            alerta_precio_duplicado = True
    else:
        # En modo DESCUENTO se utiliza el descuento ingresado por el usuario
        precio_unitario_final = precio_lista
        subtotal = precio_lista * cantidad
        total_final = subtotal * (1 - (descuento / 100.0))

    descuento_maximo = float(producto.rubro.descuento_maximo) if producto.rubro else 0.0
    requiere_autorizacion = descuento > descuento_maximo

    items.append({
        'index': len(items),
        'producto_id': producto.id,
        'subprod': bool(producto.subprod),
        'codigo': producto.cod_prov or producto.id,
        # En distribución el código es `producto.id`, y se imprime junto al del sistema
        # anterior para que vendedores y facturadores se familiaricen con el nuevo.
        'codigo_erp': producto.id,
        'codigo_anterior': producto.codigo_anterior or '',
        'disponible': disponible_producto,
        'detalle': producto.detalle,
        'cantidad': cantidad,
        'precio_unitario': precio_unitario_final, # En PESOS
        'precio_base': precio_base,
        'descuento': descuento,
        'descuento_maximo': descuento_maximo,
        'total': round(total_final, 2), # En PESOS
        'requiere_autorizacion': requiere_autorizacion,
        'alerta_precio_duplicado': alerta_precio_duplicado,
        'moneda_origen': moneda_origen,
        'cotizacion_aplicada': cotizacion_aplicada,
        'precio_origen': precio_origen,
        'credencial': credencial,
        'dmp': dmp
    })
    
    request.session['preventa_items_temp'] = items
    response = render(request, 'facturacion/partials/preventa_items_tabla.html', {
        'items': items,
        'moneda': 'PES',
        'modo_edicion': modo_edicion
    })
    response['HX-Trigger'] = json.dumps({
        'limpiarInputsCargaPreventa': True,
        'actualizarTotalesPreventa': {
            'total': sum(i['total'] for i in items),
            'requiere_autorizacion': any(i['requiere_autorizacion'] for i in items),
            'alerta_precio_duplicado': alerta_precio_duplicado
        }
    })
    return response

@login_required
def preventas_item_remove(request, index):
    from empresas.models import Empresa as _Empresa
    empresa_activa = _Empresa.objects.filter(pk=request.session.get('empresa_id')).first()
    modo_edicion = getattr(empresa_activa, 'modo_edicion_facturacion', 'DESCUENTO')

    items = request.session.get('preventa_items_temp', [])
    if 0 <= index < len(items):
        items.pop(index)
        for i, item in enumerate(items):
            item['index'] = i
    request.session['preventa_items_temp'] = items
    response = render(request, 'facturacion/partials/preventa_items_tabla.html', {
        'items': items,
        'moneda': 'PES',
        'modo_edicion': modo_edicion
    })
    response['HX-Trigger'] = json.dumps({
        'actualizarTotalesPreventa': {
            'total': sum(i['total'] for i in items),
            'requiere_autorizacion': any(i['requiere_autorizacion'] for i in items)
        }
    })
    return response

@login_required
def editar_item_preventa_sesion(request, index):
    """
    Actualiza precio unitario o descuento de un ítem de preventa en la sesión.
    """
    from empresas.models import Empresa as _Empresa
    from .helpers import parsear_decimal_ar
    empresa_activa = _Empresa.objects.filter(pk=request.session.get('empresa_id')).first()
    modo_edicion = getattr(empresa_activa, 'modo_edicion_facturacion', 'DESCUENTO')

    items = request.session.get('preventa_items_temp', [])
    if 0 <= index < len(items):
        try:
            item = items[index]
            precio_base = float(item.get('precio_base', item.get('precio_unitario', 0)) or 0)
            cantidad = float(item.get('cantidad', 1) or 1)

            if modo_edicion == 'PRECIO':
                if 'precio' in request.POST:
                    precio_ingresado = parsear_decimal_ar(request.POST.get('precio', '0'), default=precio_base)
                    if precio_ingresado < precio_base and precio_base > 0:
                        item['precio_unitario'] = precio_base
                        item['descuento'] = round(((precio_base - precio_ingresado) / precio_base) * 100.0, 2)
                        item['total'] = round(precio_ingresado * cantidad, 2)
                    else:
                        item['precio_unitario'] = precio_ingresado
                        item['descuento'] = 0.0
                        item['total'] = round(precio_ingresado * cantidad, 2)
                    item['alerta_precio_duplicado'] = precio_ingresado > (precio_base * 2) if precio_base > 0 else False
            else:
                if 'descuento' in request.POST:
                    item['descuento'] = parsear_decimal_ar(request.POST.get('descuento', '0'), default=0.0)
                if 'precio' in request.POST:
                    item['precio_unitario'] = parsear_decimal_ar(request.POST.get('precio', '0'), default=0.0)
                
                precio_lista = float(item.get('precio_unitario', 0) or 0)
                descuento = float(item.get('descuento', 0) or 0)
                subtotal = precio_lista * cantidad
                item['total'] = round(subtotal * (1 - (descuento / 100.0)), 2)
            
            descuento_maximo = float(item.get('descuento_maximo', 0))
            item['requiere_autorizacion'] = float(item.get('descuento', 0)) > descuento_maximo
            request.session['preventa_items_temp'] = items
        except (ValueError, TypeError):
            pass
            
    response = render(request, 'facturacion/partials/preventa_items_tabla.html', {
        'items': items,
        'moneda': 'PES',
        'modo_edicion': modo_edicion
    })
    response['HX-Trigger'] = json.dumps({
        'limpiarInputsCargaPreventa': False,
        'actualizarTotalesPreventa': {
            'total': sum(i['total'] for i in items),
            'requiere_autorizacion': any(i['requiere_autorizacion'] for i in items)
        }
    })
    return response

@login_required
def info_cliente_preventa(request):
    """
    Retorna la ficha de datos fiscales y domicilio completo del cliente para la carga de Preventa.
    En Distribución incluye adicionalmente el panel de crédito, y en Armería los datos informativos de CLU.
    """
    cliente_id = request.GET.get('cliente') or request.GET.get('cliente_id')
    if not cliente_id:
        return HttpResponse("")
    
    try:
        from .models import ClienteProveedor
        from verticalidades.armeria.models import ExtensionArmeria
        from empresas.models import Empresa
        empresa_id = request.session.get('empresa_id')
        cliente = ClienteProveedor.objects.get(pk=cliente_id, empresa_id=empresa_id)

        # Si es Distribuidora, renderizamos el panel de situación crediticia
        if Empresa.objects.filter(id=empresa_id, tipo_actividad="DISTRIBUIDORA").exists():
            from verticalidades.distribucion.services.credito import situacion_crediticia
            return render(request, 'distribucion/partials/panel_credito.html', {
                'cliente': cliente,
                'credito': situacion_crediticia(cliente),
            })

        # Para Armería y resto de actividades: renderizamos la ficha con Tipo de Doc, CUIT, Condición IVA y Domicilio completo
        armeria = None
        if Empresa.objects.filter(id=empresa_id, tipo_actividad="ARMERIA").exists():
            armeria = ExtensionArmeria.objects.filter(cliente=cliente).first()

        return render(request, 'facturacion/partials/preventa_cliente_info.html', {
            'cliente': cliente,
            'armeria': armeria,
        })
    except ClienteProveedor.DoesNotExist:
        pass
    
    return HttpResponse("")

@login_required
def preventa_autorizacion_modal(request, id):
    perfil = getattr(request.user, 'perfil', None)
    tiene_permiso = perfil and (perfil.permiso_autorizar_descuentos or perfil.permiso_facturacion_autorizaciones or perfil.es_admin_sistema)
    if not (request.user.is_staff or tiene_permiso):
        return HttpResponse("<div class='p-4 text-red-500 font-bold'>No tienes permiso para autorizar descuentos.</div>", status=403)

    from .models import Preventa
    preventa = get_object_or_404(Preventa, preventa_id=id, empresa_id=request.session.get('empresa_id'))
    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'aprobar':
            preventa.estado = 2 # Autorizada
            preventa.save()
        elif accion == 'anular':
            preventa.estado = 4 # Anulada/Rechazada
            preventa.save()
        elif accion == 'forzar_lista':
            # Remove discounts and approve
            for item in preventa.items.all():
                if getattr(item, 'porcentaje_descuento', 0) > 0:
                    item.porcentaje_descuento = 0
                    item.total = item.cantidad * item.precio_unitario
                    item.save()
            preventa.estado = 2 # Autorizada
            preventa.save()
            preventa.recalcular_totales()
            
        response = HttpResponse()
        response['HX-Trigger'] = json.dumps({'reloadAutorizaciones': True, 'cerrarModal': True})
        return response
    return render(request, 'facturacion/modals/autorizar_preventa.html', {'preventa': preventa})

@login_required
def venta_autorizacion_modal(request, id):
    perfil = getattr(request.user, 'perfil', None)
    tiene_permiso = perfil and (perfil.permiso_autorizar_descuentos or perfil.permiso_facturacion_autorizaciones or perfil.es_admin_sistema)
    if not (request.user.is_staff or tiene_permiso):
        return HttpResponse("<div class='p-4 text-red-500 font-bold'>No tienes permiso para autorizar descuentos.</div>", status=403)

    from .models import Venta
    venta = get_object_or_404(Venta, ventas_id=id, empresa_id=request.session.get('empresa_id'))
    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'aprobar':
            venta.estado = 0 # Activa (aprobada)
            venta.save()
        elif accion == 'anular':
            venta.estado = 1 # Anulada/Rechazada
            venta.save()
        elif accion == 'forzar_lista':
            # Remove discounts and approve
            for item in venta.items.all():
                if getattr(item, 'porcentaje_descuento', 0) > 0:
                    item.porcentaje_descuento = 0
                    item.total = item.cantidad * item.precio_unitario
                    item.save()
            venta.estado = 0 # Activa (aprobada)
            venta.save()
            venta.recalcular_totales()
            
        response = HttpResponse()
        response['HX-Trigger'] = json.dumps({'reloadAutorizaciones': True, 'cerrarModal': True})
        return response
    return render(request, 'facturacion/modals/autorizar_venta.html', {'venta': venta})

@login_required
def buscador_comprobantes_modal(request):
    return render(request, 'facturacion/modals/buscador_comprobantes.html')


@login_required
def tipo_comprobante_modal(request):
    """Alta rápida de un Tipo de Comprobante cuando el recibido no está en la tabla
    (en compras cualquier comprobante es válido). Al guardar lo selecciona en la carga."""
    from .models import TipoComprobante
    if request.method == 'POST':
        codigo = (request.POST.get('codigo') or '').strip()
        detalle = (request.POST.get('detalle') or '').strip().upper()
        signo = request.POST.get('signo') or '1'
        if not codigo or not detalle:
            return render(request, 'facturacion/modals/tipo_comprobante_form.html', {
                'error': 'Código y detalle son obligatorios.', 'codigo': codigo, 'detalle': detalle, 'signo': signo,
            })
        tipo, _creado = TipoComprobante.objects.get_or_create(
            codigo=codigo, defaults={'detalle': detalle, 'signo': int(signo), 'estado': True}
        )
        response = HttpResponse()
        response['HX-Trigger'] = json.dumps({
            'comprobanteSeleccionado': {'codigo': tipo.codigo, 'detalle': tipo.detalle},
            'cerrarModal': True,
        })
        return response
    return render(request, 'facturacion/modals/tipo_comprobante_form.html', {
        'codigo': request.GET.get('codigo', ''), 'signo': '1',
    })

@login_required
def lista_comprobantes_resultados(request):
    """Lista TIPOS de comprobante para el buscador de la carga de compras.
    En compras NO hay filtro por estado: se muestran todos los tipos (cualquier
    comprobante recibido es válido), a diferencia de ventas (solo autorizados a emitir)."""
    from .models import TipoComprobante
    f_cod = request.GET.get('f_cod', '').strip()
    f_det = request.GET.get('f_det', '').strip()
    filtros = Q()
    if f_cod:
        filtros &= Q(codigo__icontains=f_cod)
    if f_det:
        filtros &= Q(detalle__icontains=f_det)
    comprobantes = TipoComprobante.objects.filter(filtros).order_by('codigo')[:50]
    return render(request, 'facturacion/partials/comprobantes_search_results.html', {
        'comprobantes': comprobantes,
    })

@login_required
def buscar_comprobante_por_codigo(request):
    from .models import Compra
    codigo = request.POST.get('codigo_comprobante', '').strip()
    empresa_id = request.session.get('empresa_id')
    if not codigo:
        return HttpResponse("")
    compra = Compra.objects.filter(empresa_id=empresa_id, numero_comprobante=codigo).first()
    if compra:
        data = {
            'id': compra.id,
            'numero': compra.numero_comprobante,
            'proveedor': compra.proveedor.razon_social,
            'fecha': compra.fecha_comprobante.strftime('%d/%m/%Y') if compra.fecha_comprobante else '',
            'total': float(compra.total_comprobante)
        }
        return HttpResponse(json.dumps(data), content_type='application/json')
    return HttpResponse(json.dumps({'error': 'Comprobante no encontrado'}), content_type='application/json', status=404)

# --- TYPEAHEAD VIEWS (Autocompletado Inline) ---

@login_required
def typeahead_clientes(request):
    """
    Autocompletado inline de Clientes/Proveedores
    """
    q = (request.GET.get('q') or request.GET.get('q_cliente') or request.GET.get('q_proveedor') or '').strip()
    empresa_id = request.session.get('empresa_id')
    
    filtros = Q(empresa_id=empresa_id) 
    if q:
        filtros &= (Q(razon_social__icontains=q) | Q(cuit__icontains=q))

    solo_trazabilidad = request.GET.get('solo_trazabilidad')
    
    if solo_trazabilidad == '1':
        from django.db.models import Exists, OuterRef
        from productos.models import Subproducto
        subproductos_con_cli = Subproducto.objects.filter(
            Q(empresa_id=empresa_id) & (
                Q(compra__proveedor_id=OuterRef('pk')) |
                Q(venta__cliente_id=OuterRef('pk'))
            )
        )
        clientes = ClienteProveedor.objects.filter(filtros).annotate(en_trazabilidad=Exists(subproductos_con_cli)).filter(en_trazabilidad=True).order_by('razon_social')[:20]
    else:
        clientes = ClienteProveedor.objects.filter(filtros).order_by('razon_social')[:20]
    
    return render(request, 'facturacion/partials/clientes_typeahead.html', {
        'clientes': clientes,
    })

@login_required
def typeahead_productos_venta(request):
    """
    Autocompletado inline de Productos para Venta (con stock y búsqueda inteligente multi-término)
    """
    q = request.GET.get('q', '').strip()
    sucursal_id = request.session.get('sucursal_id')
    empresa_id = request.session.get('empresa_id')
    solo_trazabilidad = request.GET.get('solo_trazabilidad') == '1'

    productos_qs = buscar_productos_inteligente(
        q=q,
        empresa_id=empresa_id,
        solo_trazabilidad=solo_trazabilidad,
        excluir_subprod=False,
        limit=100
    )

    from empresas.models import CotizacionMoneda
    cotizacion = 1.0
    if empresa_id:
        try:
            cotiz_obj = CotizacionMoneda.objects.get(empresa_id=empresa_id)
            cotizacion = float(cotiz_obj.dolar_venta)
        except CotizacionMoneda.DoesNotExist:
            pass

    moneda_venta = request.GET.get('moneda') or request.session.get('venta_moneda', 'PES')
    productos = []
    for p in productos_qs:
        p.precio_pesificado = float(p.precio_total or 0) * cotizacion if p.moneda == 'DOL' else float(p.precio_total or 0)
        p.precio_mostrar = calcular_precio_sugerido(p, moneda_venta, cotizacion)
        
        # Calcular stocks
        stock_local = 0
        for stk in p.existencias.all():
            if str(stk.sucursal_id) == str(sucursal_id):
                stock_local += stk.cantidad
                
        p.stock_local = stock_local
        productos.append(p)

    simple = request.GET.get('simple') == '1'

    return render(request, 'facturacion/partials/productos_venta_typeahead.html', {
        'productos': productos,
        'cotizacion_dolar': cotizacion,
        'moneda_venta': moneda_venta,
        'simple': simple
    })

@login_required
def typeahead_productos_compra(request):
    """
    Autocompletado inline de Productos para Compras (con búsqueda inteligente multi-término)
    """
    q = request.GET.get('q', '').strip()
    solo_trazables = request.GET.get('solo_trazables') == '1'
    empresa_id = request.session.get('empresa_id')

    productos = buscar_productos_inteligente(
        q=q,
        empresa_id=empresa_id,
        limit=100
    )
    if solo_trazables:
        productos = productos.filter(subprod=True)

    return render(request, 'facturacion/partials/productos_compra_typeahead.html', {
        'productos': productos,
    })

@login_required
def typeahead_comprobantes(request):
    """
    Autocompletado inline de Tipos de Comprobante
    """
    from .models import TipoComprobante
    q = request.GET.get('q', '').strip()
    
    filtros = Q()
    if q:
        filtros &= (Q(codigo__icontains=q) | Q(detalle__icontains=q))

    comprobantes = TipoComprobante.objects.filter(filtros).order_by('codigo')[:20]
    
    return render(request, 'facturacion/partials/comprobantes_typeahead.html', {
        'comprobantes': comprobantes,
    })
