from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import UsuarioForm
import json

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
        # Instancia el formulario con datos del POST y archivos (si hubiera)
        form = UsuarioForm(request.POST, request.FILES, instance=usuario)
        if form.is_valid():
            form.save() # Guarda el usuario y actualiza los permisos del Perfil
            response = HttpResponse()
            # Triggers para recargar el listado y luego cerrar el modal
            response['HX-Trigger'] = json.dumps({'reloadUsuarios': True, 'cerrarModal': True})
            response['HX-Reswap'] = 'none' # Mantiene el DOM activo para la burbuja de eventos
            return response
    else:
        form = UsuarioForm(instance=usuario)

    return render(request, 'configuracion/modals/usuario_form.html', {
        'form': form, 
        'is_new': is_new, 
        'usuario_obj': usuario
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
