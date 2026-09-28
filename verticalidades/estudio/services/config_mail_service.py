import os
import json
from pathlib import Path
from django.conf import settings

CONFIG_DIR = Path(settings.MEDIA_ROOT) / 'config_mails'
FIRMAS_DIR = CONFIG_DIR / 'firmas'

DEFAULT_CONFIG = {
    'activo': True,
    'email_remitente': '',
    'nombre_remitente': '',
    'servidor_smtp': 'mail.lopez-rios.com',
    'puerto_smtp': 465,
    'usuario_smtp': '',
    'password_smtp': '',
    'usar_tls': False,
    'usar_ssl': True,
    'asunto': 'Factura {comprobante} - {empresa}',
    'mensaje': (
        'Estimado/a {cliente}:\n\n'
        'Le hacemos llegar adjunto a este correo su factura ({comprobante}) '
        'correspondiente al período {periodo}.\n\n'
        'Ante cualquier consulta o inquietud, quedamos a su entera disposición.'
    ),
    'firma': (
        'Atentamente,\n'
        '<b>{first_name} {last_name}</b>\n'
        '{empresa}'
    ),
    'logo_firma': '',
    'delay_segundos': 1.0,
}

def get_config_file_path(empresa_id: int) -> Path:
    return CONFIG_DIR / f'empresa_{empresa_id}_mails.json'

def get_config_mail(empresa_id: int) -> dict:
    """
    Obtiene la configuración de envío de correos para una empresa.
    Si el archivo no existe, retorna los valores predeterminados.
    """
    file_path = get_config_file_path(empresa_id)
    if not file_path.exists():
        cfg = DEFAULT_CONFIG.copy()
        return cfg

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Combinar con defaults para campos faltantes
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)
            return merged
    except Exception as ex:
        print(f"[config_mail_service] Error leyendo configuración para empresa {empresa_id}: {ex}")
        return DEFAULT_CONFIG.copy()

def guardar_config_mail(empresa_id: int, data: dict) -> bool:
    """
    Guarda los datos de configuración de correo en un archivo JSON en media/config_mails/.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    file_path = get_config_file_path(empresa_id)

    cfg = get_config_mail(empresa_id)
    cfg.update(data)
    
    # Sanitizaciones de tipos
    cfg['activo'] = bool(cfg.get('activo', False))
    cfg['usar_tls'] = bool(cfg.get('usar_tls', False))
    cfg['usar_ssl'] = bool(cfg.get('usar_ssl', True))
    cfg['firma'] = str(cfg.get('firma', '') or '').strip()
    cfg['logo_firma'] = str(cfg.get('logo_firma', '') or '').strip()

    try:
        cfg['puerto_smtp'] = int(cfg.get('puerto_smtp', 465))
    except (ValueError, TypeError):
        cfg['puerto_smtp'] = 465
        
    try:
        cfg['delay_segundos'] = float(cfg.get('delay_segundos', 1.0))
    except (ValueError, TypeError):
        cfg['delay_segundos'] = 1.0

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)
        
    return True

def guardar_logo_firma(empresa_id: int, uploaded_file) -> str:
    """
    Guarda una imagen de logo/firma para la empresa en media/config_mails/firmas/.
    Retorna la ruta relativa dentro de MEDIA_ROOT o string vacío en caso de error.
    """
    if not uploaded_file:
        return ""
    
    FIRMAS_DIR.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in ['.png', '.jpg', '.jpeg', '.webp', '.svg']:
        ext = '.png'
        
    # Eliminar posibles versiones anteriores con diferente extensión
    eliminar_logo_firma(empresa_id)

    nombre_archivo = f'firma_{empresa_id}{ext}'
    destino = FIRMAS_DIR / nombre_archivo
    
    with open(destino, 'wb+') as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)
            
    rel_path = f'config_mails/firmas/{nombre_archivo}'
    
    # Actualizar en la configuración
    cfg = get_config_mail(empresa_id)
    cfg['logo_firma'] = rel_path
    guardar_config_mail(empresa_id, cfg)
    return rel_path

def eliminar_logo_firma(empresa_id: int) -> bool:
    """
    Elimina físicamente el archivo de logo de firma de la empresa si existe.
    """
    if not FIRMAS_DIR.exists():
        return False
    
    eliminado = False
    for ext in ['.png', '.jpg', '.jpeg', '.webp', '.svg']:
        f = FIRMAS_DIR / f'firma_{empresa_id}{ext}'
        if f.exists():
            try:
                f.unlink()
                eliminado = True
            except Exception:
                pass
                
    cfg = get_config_mail(empresa_id)
    if cfg.get('logo_firma'):
        cfg['logo_firma'] = ''
        guardar_config_mail(empresa_id, cfg)
        
    return eliminado

def is_config_activa(empresa_id: int) -> tuple[bool, str]:
    """
    Verifica si el servicio de correo para la empresa está activo y cuenta con los parámetros mínimos.
    Retorna (True, "") si está listo, o (False, "Motivo") si no.
    """
    cfg = get_config_mail(empresa_id)
    if not cfg.get('activo'):
        return False, "El servicio de envíos de facturas por mail está desactivado."
    if not cfg.get('servidor_smtp'):
        return False, "Falta configurar el servidor SMTP."
    if not cfg.get('usuario_smtp'):
        return False, "Falta configurar el usuario o correo remitente SMTP."
    if not cfg.get('password_smtp'):
        return False, "Falta configurar la contraseña del servidor SMTP."
    return True, ""
