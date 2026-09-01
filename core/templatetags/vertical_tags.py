import os
from django import template
from django.conf import settings
from django.template.loader import render_to_string
from django.template.exceptions import TemplateDoesNotExist
from django.utils.safestring import mark_safe
from pathlib import Path

register = template.Library()

@register.simple_tag(takes_context=True)
def hook_menu(context, hook_name):
    """
    Escanea las aplicaciones instaladas en verticalidades y busca el template
    <app_name>/hooks/menu_<hook_name>.html para renderizarlo.
    El filtrado por tipo_actividad se hace DENTRO de cada hook template,
    no aquí, permitiendo que cada verticalidad decida cuándo mostrarse.
    """
    html_output = ""
    verticalidades_path = Path(settings.BASE_DIR) / 'verticalidades'
    
    if not verticalidades_path.exists() or not verticalidades_path.is_dir():
        return ""

    for item in verticalidades_path.iterdir():
        if item.is_dir() and (item / '__init__.py').exists():
            app_name = item.name
            template_name = f"{app_name}/hooks/menu_{hook_name}.html"
            try:
                # Renderizamos cada template encontrado pasandole el contexto actual
                html_output += render_to_string(template_name, context.flatten())
            except TemplateDoesNotExist:
                pass

    return mark_safe(html_output)

@register.simple_tag(takes_context=True)
def hook_ui(context, hook_name, **kwargs):
    """
    Escanea las aplicaciones instaladas en verticalidades y busca el template
    <app_name>/hooks/ui_<hook_name>.html para inyectar componentes UI genéricos.
    El filtrado por tipo_actividad se hace DENTRO de cada hook template.
    Permite pasar kwargs adicionales que se mezclarán con el contexto.
    """
    html_output = ""
    verticalidades_path = Path(settings.BASE_DIR) / 'verticalidades'
    
    if not verticalidades_path.exists() or not verticalidades_path.is_dir():
        return ""

    ctx = context.flatten()
    ctx.update(kwargs)

    for item in verticalidades_path.iterdir():
        if item.is_dir() and (item / '__init__.py').exists():
            app_name = item.name
            template_name = f"{app_name}/hooks/ui_{hook_name}.html"
            try:
                html_output += render_to_string(template_name, ctx)
            except TemplateDoesNotExist:
                pass

    return mark_safe(html_output)
