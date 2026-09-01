from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()


@register.filter(name='formato_ar')
def formato_ar(value, decimales=2):
    """
    Formatea un número al estilo argentino: 1.234.567,89
    Uso: {{ valor|formato_ar }} o {{ valor|formato_ar:0 }}
    """
    try:
        num = float(value)
    except (ValueError, TypeError, InvalidOperation):
        return value

    decimales = int(decimales)
    # Formateamos con punto como separador de miles y coma como decimal
    if decimales > 0:
        parte_entera = int(abs(num))
        parte_decimal = round(abs(num) - parte_entera, decimales)
        dec_str = f"{parte_decimal:.{decimales}f}"[2:]  # quitar "0."
        int_str = f"{parte_entera:,}".replace(",", ".")
        resultado = f"{int_str},{dec_str}"
    else:
        resultado = f"{int(abs(num)):,}".replace(",", ".")

    if num < 0:
        resultado = f"-{resultado}"

    return resultado
