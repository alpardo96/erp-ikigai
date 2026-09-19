from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()


@register.filter(name='formato_ar')
def formato_ar(value, decimales=2):
    """
    Formatea un número al estilo argentino: 1.234.567,89
    Uso: {{ valor|formato_ar }} o {{ valor|formato_ar:0 }}
    """
    if value is None or value == '':
        return '0,00' if int(decimales) == 2 else '0'

    try:
        num = float(value)
    except (ValueError, TypeError, InvalidOperation):
        return value

    decimales = int(decimales)
    # Formateamos con punto como separador de miles y coma como decimal
    if decimales > 0:
        num_str = f"{abs(num):,.{decimales}f}"
        # Intercambiamos comas (miles en inglés) por puntos y punto (decimal en inglés) por coma
        resultado = num_str.replace(',', 'X').replace('.', ',').replace('X', '.')
    else:
        resultado = f"{int(round(abs(num))):,}".replace(',', '.')

    if num < 0:
        resultado = f"-{resultado}"

    return resultado

