from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import UsuarioForm
import json
from django.contrib.auth.models import Group, Permission

def agrupar_permisos_menu(permisos_menu):
    agrupados = {}
    nombres = {
        'compras': 'Compras',
        'ventas': 'Ventas',
        'stock': 'Stock',
        'tesoreria': 'Tesorería',
        'contable': 'Contable',
        'impuestos': 'Impuestos',
        'configuracion': 'Configuración',
        'clientes': 'Clientes y Proveedores',
        'armeria': 'Armería (Verticalidad)',
    }
    for p in permisos_menu:
        partes = p.codename.split('_')
        modulo = partes[1] if len(partes) > 1 else 'otros'
        nombre_modulo = nombres.get(modulo, modulo.capitalize())
        if nombre_modulo not in agrupados:
            agrupados[nombre_modulo] = []
        agrupados[nombre_modulo].append(p)
    return agrupados

@login_required
def usuario_modal(request, id=None):
    """
    MANEJADOR DE MODAL DE USUARIO (GET/POST)
    - GET: Renderiza el formulario de creación o edición de usuario.
    - POST: Valida y guarda el usuario (User + Perfil vinculado).
    - HTMX: Al éxito, envía 'cerrarModal' y 'reloadUsuarios' para recargar la tabla sin refrescar la página.
    """
    if id:
        usuario = get_object_or_404(User, id=id)
        is_new = False
    else:
        usuario = None
        is_new = True

    if request.method == 'POST':
        form = UsuarioForm(request.POST, request.FILES, instance=usuario)
        if form.is_valid():
            user_obj = form.save()
            
            # Obtener IDs heredados (de los grupos seleccionados)
            permisos_heredados = set()
            for group in user_obj.groups.all():
                permisos_heredados.update(list(group.permissions.values_list('id', flat=True)))
                
            # Obtener IDs que vienen marcados en el formulario
            marcados = request.POST.getlist('user_permissions')
            marcados = set(map(int, marcados)) if marcados else set()
            
            # Extras: Marcados pero no heredados
            extras = marcados - permisos_heredados
            user_obj.user_permissions.set(extras)
            
            # Denegados: Heredados pero NO marcados
            denegados = permisos_heredados - marcados
            from usuarios.models import PermisoDenegado
            PermisoDenegado.objects.filter(usuario=user_obj).delete()
            if denegados:
                objetos_denegados = [PermisoDenegado(usuario=user_obj, permiso_id=pid) for pid in denegados]
                PermisoDenegado.objects.bulk_create(objetos_denegados)

            response = HttpResponse()
            response['HX-Trigger'] = json.dumps({'reloadUsuarios': True, 'cerrarModal': True})
            response['HX-Reswap'] = 'none'
            return response
    else:
        form = UsuarioForm(instance=usuario)

    apps_ignoradas = ['admin', 'auth', 'contenttypes', 'sessions']
    permisos = Permission.objects.exclude(content_type__app_label__in=apps_ignoradas).select_related('content_type')
    
    permisos_menu = [p for p in permisos if p.codename.startswith('menu_')]
    permisos_menu_agrupados = agrupar_permisos_menu(permisos_menu)
    permisos_usuario = list(usuario.user_permissions.values_list('id', flat=True)) if usuario else []
    
    permisos_heredados = []
    permisos_denegados = []
    if usuario:
        for group in usuario.groups.all():
            permisos_heredados.extend(list(group.permissions.values_list('id', flat=True)))
        permisos_denegados = list(usuario.permisos_denegados.values_list('permiso_id', flat=True))
    permisos_heredados = list(set(permisos_heredados))

    return render(request, 'configuracion/modals/usuario_form.html', {
        'form': form, 
        'is_new': is_new, 
        'usuario_obj': usuario,
        'permisos_menu_agrupados': permisos_menu_agrupados,
        'permisos_usuario': permisos_usuario,
        'permisos_heredados': permisos_heredados,
        'permisos_denegados': permisos_denegados
    })

@login_required
def buscar_usuarios(request):
    """
    BUSCADOR DINÁMICO DE USUARIOS
    - Recibe un parámetro 'q' desde el input de búsqueda parcial.
    - Filtra por nombre de usuario o email.
    - Renderiza ÚNICAMENTE las filas de la tabla (usuario_table_rows.html).
    """
    q = request.GET.get('q', '')
    if q:
        usuarios = User.objects.filter(username__icontains=q) | User.objects.filter(email__icontains=q)
    else:
        usuarios = User.objects.all().select_related('perfil') # Optimización de query
        
    return render(request, 'configuracion/partials/usuario_table_rows.html', {'usuarios': usuarios.distinct()})

@login_required
def eliminar_usuario(request, id):
    """
    ELIMINACIÓN ATÓMICA DE USUARIO
    - Requiere POST para evitar borrados accidentales vía GET.
    - Valida seguridad básica (no borrarse a uno mismo ni superusers).
    - HTMX: Dispara 'reloadUsuarios' al finalizar.
    """
    if request.method == 'POST':
        usuario = get_object_or_404(User, id=id)
        # Lógica de protección: El admin no puede borrarse a sí mismo ni a otros superusers
        if not usuario.is_superuser and request.user.id != usuario.id:
            usuario.delete()
            response = HttpResponse()
            response['HX-Trigger'] = json.dumps({'reloadUsuarios': True})
            return response
    return HttpResponse(status=400)

@login_required
def rol_modal(request, id=None):
    if id:
        grupo = get_object_or_404(Group, id=id)
        is_new = False
    else:
        grupo = None
        is_new = True

    if request.method == 'POST':
        nombre = request.POST.get('name')
        permisos_ids = request.POST.getlist('permissions')
        
        if is_new:
            grupo = Group.objects.create(name=nombre)
        else:
            grupo.name = nombre
            grupo.save()
            
        grupo.permissions.set(permisos_ids)
        
        response = HttpResponse()
        response['HX-Trigger'] = json.dumps({'reloadRoles': True, 'cerrarModal': True})
        return response

    # Agrupar permisos para la vista
    apps_ignoradas = ['admin', 'auth', 'contenttypes', 'sessions']
    permisos = Permission.objects.exclude(content_type__app_label__in=apps_ignoradas).select_related('content_type')
    
    agrupados = {}
    permisos_menu = []
    
    for p in permisos:
        if p.codename.startswith('menu_'):
            permisos_menu.append(p)
            continue
            
        app = p.content_type.app_label
        model = p.content_type.model
        action = p.codename.split('_')[0]
        
        if app not in agrupados:
            agrupados[app] = {}
        if model not in agrupados[app]:
            agrupados[app][model] = {'view': None, 'add': None, 'change': None, 'delete': None}
            
        if action in agrupados[app][model]:
            agrupados[app][model][action] = p

    permisos_menu_agrupados = agrupar_permisos_menu(permisos_menu)
    permisos_grupo = list(grupo.permissions.values_list('id', flat=True)) if grupo else []

    return render(request, 'configuracion/modals/rol_modal.html', {
        'grupo': grupo,
        'is_new': is_new,
        'agrupados': agrupados,
        'permisos_menu_agrupados': permisos_menu_agrupados,
        'permisos_grupo': permisos_grupo
    })

@login_required
def buscar_roles(request):
    q = request.GET.get('q', '')
    if q:
        roles = Group.objects.filter(name__icontains=q).prefetch_related('permissions')
    else:
        roles = Group.objects.all().prefetch_related('permissions')
        
    return render(request, 'configuracion/partials/rol_table_rows.html', {'roles': roles})

@login_required
def eliminar_rol(request, id):
    if request.method == 'POST':
        grupo = get_object_or_404(Group, id=id)
        grupo.delete()
        response = HttpResponse()
        response['HX-Trigger'] = json.dumps({'reloadRoles': True})
        return response
    return HttpResponse(status=400)

