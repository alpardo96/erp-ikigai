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

def get_config_file_path(empresa_id: int = None, for_write: bool = False) -> Path:
    """
    Obtiene la ruta del archivo de configuración JSON en media/config_mails/.
    - Si for_write=True: devuelve la ruta destino específica para guardar (empresa_{id}_mails.json).
    - Si for_write=False (lectura / vinculación):
        1. Si se provee empresa_id y existe empresa_{empresa_id}_mails.json, lo usa.
        2. Si no existe, busca si existe empresa_1_mails.json en media/config_mails/ (configuración que ya vive en media).
        3. Si no existe, busca si existe cualquier archivo empresa_*_mails.json en media/config_mails/.
        4. Si no hay ninguno, retorna empresa_{empresa_id or 1}_mails.json (no existe aún en disco).
    """
    eid = empresa_id if empresa_id else 1
    if for_write:
        return CONFIG_DIR / f'empresa_{eid}_mails.json'

    # 1. Archivo específico de la empresa
    if empresa_id:
        especifico = CONFIG_DIR / f'empresa_{empresa_id}_mails.json'
        if especifico.exists():
            return especifico

    # 2. Archivo empresa_1_mails.json (configuración principal que ya vive en media)
    empresa_1_path = CONFIG_DIR / 'empresa_1_mails.json'
    if empresa_1_path.exists():
        return empresa_1_path

    # 3. Cualquier archivo empresa_*_mails.json existente en media/config_mails/
    if CONFIG_DIR.exists():
        existentes = sorted(list(CONFIG_DIR.glob('empresa_*_mails.json')))
        if existentes:
            return existentes[0]

    return CONFIG_DIR / f'empresa_{eid}_mails.json'

def get_logo_firma_path(empresa_id: int = None) -> str:
    """
    Busca si existe el archivo de imagen de la firma en media/config_mails/firmas/
    siguiendo la convención firma_{empresa_id}.{ext} (donde el número es el ID de la empresa).
    Retorna la ruta relativa dentro de MEDIA_ROOT (ej: 'config_mails/firmas/firma_1.jpg')
    o cadena vacía si no existe.
    """
    if not FIRMAS_DIR.exists():
        return ""

    eid = empresa_id if empresa_id else 1
    extensiones = ['.jpg', '.jpeg', '.png', '.webp', '.svg']

    # 1. Buscar firma_{empresa_id}.ext
    for ext in extensiones:
        f = FIRMAS_DIR / f'firma_{eid}{ext}'
        if f.exists():
            return f'config_mails/firmas/{f.name}'
    return ""

def existe_config_en_media(empresa_id: int = None) -> bool:
    """
    Retorna True si ya existe un archivo de configuración de correo en media/config_mails/.
    """
    file_path = get_config_file_path(empresa_id, for_write=False)
    return file_path.exists()

def get_config_mail(empresa_id: int = None) -> dict:
    """
    Obtiene la configuración de envío de correos vinculándose prioritariamente
    a la configuración que ya vive en media/config_mails/.
    Si no existe ningún archivo en media, retorna los valores predeterminados.
    """
    file_path = get_config_file_path(empresa_id, for_write=False)
    logo_disco = get_logo_firma_path(empresa_id)

    if not file_path.exists():
        cfg = DEFAULT_CONFIG.copy()
        if logo_disco:
            cfg['logo_firma'] = logo_disco
        return cfg

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Combinar con defaults para campos faltantes
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)

            # Auto-vincular logo de firma directamente desde media/config_mails/firmas/firma_{id}.*
            if logo_disco:
                merged['logo_firma'] = logo_disco
            elif not merged.get('logo_firma'):
                merged['logo_firma'] = ""

            return merged
    except Exception as ex:
        print(f"[config_mail_service] Error leyendo configuración para empresa {empresa_id} desde {file_path}: {ex}")
        cfg = DEFAULT_CONFIG.copy()
        if logo_disco:
            cfg['logo_firma'] = logo_disco
        return cfg

def guardar_config_mail(empresa_id: int = None, data: dict = None) -> bool:
    """
    Guarda los datos de configuración de correo en un archivo JSON en media/config_mails/.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    eid = empresa_id if empresa_id else 1
    file_path = get_config_file_path(eid, for_write=True)

    cfg = get_config_mail(eid)
    if data:
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

def guardar_logo_firma(empresa_id: int = None, uploaded_file = None) -> str:
    """
    Guarda una imagen de logo/firma para la empresa en media/config_mails/firmas/.
    Retorna la ruta relativa dentro de MEDIA_ROOT o string vacío en caso de error.
    """
    if not uploaded_file:
        return ""
    
    FIRMAS_DIR.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.webp', '.svg']:
        ext = '.jpg'
        
    eid = empresa_id if empresa_id else 1
    # Eliminar posibles versiones anteriores con diferente extensión
    eliminar_logo_firma(eid)

    nombre_archivo = f'firma_{eid}{ext}'
    destino = FIRMAS_DIR / nombre_archivo
    
    with open(destino, 'wb+') as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)
            
    rel_path = f'config_mails/firmas/{nombre_archivo}'
    
    # Actualizar en la configuración
    cfg = get_config_mail(eid)
    cfg['logo_firma'] = rel_path
    guardar_config_mail(eid, cfg)
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

def is_config_activa(empresa_id: int = None) -> tuple[bool, str]:
    """
    Verifica si el servicio de correo para la empresa está activo y cuenta con los parámetros mínimos.
    Si ya existe un archivo de configuración en media/config_mails/, se vincula a él.
    Retorna (True, "") si está listo, o (False, "Motivo") si no.
    """
    if not existe_config_en_media(empresa_id):
        return False, "Aún no se ha guardado una configuración de correo en media/config_mails/."

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
