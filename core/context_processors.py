import os
from django.conf import settings
from empresas.models import Empresa, Sucursal, Ejercicio


def _css_version():
    """Versión de assets para cache-busting de <link>/<script> (CSS y JS propios).
    Es el mayor mtime entre output.css y formato_ar.js, así cambia al recompilar Tailwind
    O al editar el JS global. Si no hay archivos, '' (no rompe)."""
    mtimes = []
    for rel in (('static', 'css', 'output.css'), ('static', 'js', 'formato_ar.js')):
        try:
            mtimes.append(os.path.getmtime(os.path.join(settings.BASE_DIR, *rel)))
        except OSError:
            pass
    return str(int(max(mtimes))) if mtimes else ''


def context_context(request):
    empresa_id = request.session.get('empresa_id')
    sucursal_id = request.session.get('sucursal_id')
    ejercicio_id = request.session.get('ejercicio_id')
    
    empresa_actual = None
    sucursal_actual = None
    ejercicio_actual = None
    ejercicios_disponibles = []
    
    if empresa_id:
        empresa_actual = Empresa.objects.filter(id=empresa_id).first()
        if not empresa_actual:
            if 'empresa_id' in request.session: del request.session['empresa_id']
        else:
            # Obtener ejercicios de la empresa
            ejercicios_disponibles = Ejercicio.objects.filter(empresa=empresa_actual).order_by('-inicio')
            
    if sucursal_id:
        sucursal_actual = Sucursal.objects.filter(id=sucursal_id).first()
        if not sucursal_actual:
            if 'sucursal_id' in request.session: del request.session['sucursal_id']
        elif request.user.is_authenticated:
            # Validar que el usuario tenga acceso a esta sucursal
            user = request.user
            perfil = getattr(user, 'perfil', None)
            es_valida = False
            
            if user.is_staff or (perfil and perfil.es_admin_sistema):
                es_valida = True
            elif perfil:
                permitidas = perfil.sucursales.all()
                if permitidas.exists():
                    es_valida = permitidas.filter(id=sucursal_actual.id).exists()
                else:
                    # Fallback a Sede Central si no tiene ninguna explícita
                    es_valida = 'central' in sucursal_actual.nombre.lower()

            if not es_valida:
                sucursal_actual = None
                if 'sucursal_id' in request.session: del request.session['sucursal_id']

    if ejercicio_id:
        ejercicio_actual = Ejercicio.objects.filter(id=ejercicio_id).first()
        if not ejercicio_actual:
            if 'ejercicio_id' in request.session: del request.session['ejercicio_id']
    
    # Asignación automática de ejercicio si no hay uno en sesión pero sí hay empresa
    if not ejercicio_actual and empresa_actual and ejercicios_disponibles.exists():
        ejercicio_actual = ejercicios_disponibles.first() # El más reciente por el order_by('-inicio')
        request.session['ejercicio_id'] = ejercicio_actual.id
        
    # Evaluación de alerta de vencimiento de certificado digital ARCA (.crt)
    alerta_certificado_afip = None
    if empresa_actual and empresa_actual.crt_afip:
        # Autodetección si aún no se ha guardado la fecha en la BD pero el archivo existe
        if not empresa_actual.vencimiento_crt_afip:
            fecha_v = empresa_actual.extraer_vencimiento_crt()
            if fecha_v:
                empresa_actual.vencimiento_crt_afip = fecha_v
                empresa_actual.save(update_fields=['vencimiento_crt_afip'])

        estado_crt = empresa_actual.estado_vencimiento_crt
        if estado_crt.get('es_advertencia'):
            alerta_certificado_afip = estado_crt

    # Auto-impresión de comprobantes emitidos
    auto_print_url = request.session.pop('auto_print_url', None)

    return {
        'empresa_actual': empresa_actual,
        'sucursal_actual': sucursal_actual,
        'ejercicio_actual': ejercicio_actual,
        'ejercicios_disponibles': ejercicios_disponibles,
        'alerta_certificado_afip': alerta_certificado_afip,
        'auto_print_url': auto_print_url,
        'css_version': _css_version(),
    }
