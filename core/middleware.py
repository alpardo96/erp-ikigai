from django.shortcuts import redirect
from django.urls import reverse

class SucursalRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Lista de nombres de URL que no requieren sucursal
            exempt_urls = [
                reverse('seleccion_empresa'),
                reverse('logout'),
                # Agregamos admin por si el admin necesita entrar sin sucursal primero
            ]
            
            # Permitir admin o configuración si es staff
            if request.path.startswith('/admin/') or request.path.startswith('/configuracion/'):
                return self.get_response(request)

            if not request.session.get('sucursal_id') and request.path not in exempt_urls:
                return redirect('seleccion_empresa')

        response = self.get_response(request)
        return response
