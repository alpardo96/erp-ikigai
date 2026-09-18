import re
from django.shortcuts import redirect
from django.urls import resolve
from django.core.exceptions import PermissionDenied
from django.contrib import messages

class RolePermissionMiddleware:
    """
    Middleware global que audita cada petición y verifica si el usuario 
    tiene el permiso necesario según el url_name solicitado.
    """

    # Mapa exacto de URL_NAME -> PERMISO
    EXACT_MAP = {
        # Configuración (Solo Admins o con permiso)
        'configuracion_index': 'usuarios.menu_configuracion',
        'usuarios_listado': 'usuarios.menu_configuracion',
        'roles_listado': 'usuarios.menu_configuracion',

        # Ventas
        'ventas_carga': 'usuarios.menu_ventas_carga',
        'preventas_carga': 'usuarios.menu_ventas_preventas',
        'ventas_listado': 'usuarios.menu_ventas_listado',
        'reporte_ventas_producto': 'usuarios.menu_ventas_reportes',
        'autorizaciones_listado': 'usuarios.menu_ventas_autorizaciones',
        'venta_anular_modal': 'usuarios.menu_ventas_listado',
        'venta_emitir_nc': 'usuarios.menu_ventas_listado',
        'venta_previsualizar_modal': 'usuarios.menu_ventas_listado',

        # Compras
        'compras_carga': 'usuarios.menu_compras_carga',
        'compras_listado': 'usuarios.menu_compras_listado',
        'oc_listado': 'usuarios.menu_compras_oc',
        'compras_carga_automatica': 'usuarios.menu_compras_automatica',
        'compras_carga_ia': 'usuarios.menu_compras_ia',
        'compras_baja': 'usuarios.menu_compras_listado',

        # Stock y Productos
        'producto_listado': 'usuarios.menu_stock_dashboard',
        'recepcion_listado': 'usuarios.menu_stock_recepciones',
        'remito_interno_listado': 'usuarios.menu_stock_remitos_internos',
        'recepcion_interna_listado': 'usuarios.menu_stock_recepcion_interna',

        # Tesoreria
        'caja_diaria_index': 'usuarios.menu_tesoreria_caja_diaria',
        'eoaf_index': 'usuarios.menu_tesoreria_eoaf',
        'recibo_carga': 'usuarios.menu_tesoreria_recibos',
        'ordenpago_carga': 'usuarios.menu_tesoreria_orden_pago',
        'caja_mostrador_index': 'usuarios.menu_tesoreria_caja',
        'rendiciones_recepcion': 'usuarios.menu_tesoreria_rendiciones',
        'recibo_listado': 'usuarios.menu_tesoreria_recibos',
        'ordenpago_listado': 'usuarios.menu_tesoreria_orden_pago',

        # Contable
        'libro_diario': 'usuarios.menu_contable_libro_diario',
        'libro_mayor': 'usuarios.menu_contable_libro_mayor',
        'balance': 'usuarios.menu_contable_balance',
        'saldos': 'usuarios.menu_contable_saldos',

        # Impuestos
        'cierre_iva': 'usuarios.menu_impuestos_cierre_iva',
        'libro_ventas': 'usuarios.menu_impuestos_libro_ventas',
        'libro_compras': 'usuarios.menu_impuestos_libro_compras',
        'arca': 'usuarios.menu_impuestos_arca',
        'sicore': 'usuarios.menu_impuestos_sicore',

        # Clientes
        'cliente_search': 'usuarios.menu_clientes',
        'cliente_add': 'usuarios.permiso_clientes_editar',
        'cliente_edit': 'usuarios.permiso_clientes_editar',
        'cliente_delete': 'usuarios.permiso_clientes_editar',
    }

    # Prefijos para agrupar endpoints secundarios (modal, htmx, etc.)
    # Si un url_name empieza con X, requiere el permiso Y.
    PREFIX_MAP = {
        'config_': 'usuarios.menu_configuracion',
        'usuario_': 'usuarios.menu_configuracion',
        'rol_': 'usuarios.menu_configuracion',
        'permiso_': 'usuarios.menu_configuracion',
    }

    # Modulos generales (Cualquier permiso que empiece por este string habilita el acceso a rutas secundarias)
    MODULE_PREFIX_PERMS = {
        'ventas_': 'usuarios.menu_ventas',
        'venta_': 'usuarios.menu_ventas',
        'compras_': 'usuarios.menu_compras',
        'compra_': 'usuarios.menu_compras',
        'oc_': 'usuarios.menu_compras_oc',
        
        'tesoreria_': 'usuarios.menu_tesoreria',
        'caja_': 'usuarios.menu_tesoreria',
        'eoaf_': 'usuarios.menu_tesoreria',
        'recibo_': 'usuarios.menu_tesoreria',
        'ordenpago_': 'usuarios.menu_tesoreria',
        'rendicion_': 'usuarios.menu_tesoreria',
        'op_': 'usuarios.menu_tesoreria',

        'contable_': 'usuarios.menu_contable',
        'libro_': 'usuarios.menu_contable',
        'balance_': 'usuarios.menu_contable',
        'saldo_': 'usuarios.menu_contable',

        'impuestos_': 'usuarios.menu_impuestos',
        'arca_': 'usuarios.menu_impuestos',
        'sicore_': 'usuarios.menu_impuestos',
        
        'stock_': 'usuarios.menu_stock',
        'producto_': 'usuarios.menu_stock',
        'recepcion_': 'usuarios.menu_stock',
        'remito_': 'usuarios.menu_stock',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        perfil = getattr(request.user, 'perfil', None) if request.user.is_authenticated else None
        es_admin = request.user.is_superuser or (getattr(perfil, 'es_admin_sistema', False) if perfil else False)
        if request.user.is_authenticated and not es_admin:
            url_name = request.resolver_match.url_name if request.resolver_match else None
            
            if url_name:
                # 1. Chequeo Exacto
                if url_name in self.EXACT_MAP:
                    perm = self.EXACT_MAP[url_name]
                    if not request.user.has_perm(perm):
                        return self.deny_access(request)
                
                # 2. Chequeo por Prefijo Simple
                else:
                    prefix_matched = False
                    for prefix, perm in self.PREFIX_MAP.items():
                        if url_name.startswith(prefix):
                            prefix_matched = True
                            if not request.user.has_perm(perm):
                                return self.deny_access(request)
                            break

                    # 3. Chequeo por Módulo General
                    if not prefix_matched:
                        for prefix, base_perm in self.MODULE_PREFIX_PERMS.items():
                            if url_name.startswith(prefix):
                                has_any = False
                                for user_perm in request.user.get_all_permissions():
                                    if user_perm.startswith(base_perm):
                                        has_any = True
                                        break
                                if not has_any:
                                    return self.deny_access(request)
                                break

                # Caso Especial: facturas_pendientes
                if url_name == 'facturas_pendientes':
                    op = request.GET.get('operacion', 'V')
                    if op == 'C' and not request.user.has_perm('usuarios.menu_compras_listado'):
                        return self.deny_access(request)
                    elif op == 'V' and not request.user.has_perm('usuarios.menu_ventas_listado'):
                        return self.deny_access(request)
        return None

    def deny_access(self, request):
        if request.headers.get('HX-Request'):
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("Acceso Denegado: Permisos insuficientes.")
        else:
            messages.error(request, "Acceso denegado: No tienes permisos suficientes para acceder a esta vista.")
            return redirect('home')
