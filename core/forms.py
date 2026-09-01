"""Campos de formulario compartidos por todo el ERP.

Contrapartida en el backend de `static/js/formato_ar.js`: los inputs con la clase
`.fInputAR` llegan al servidor como texto en formato es-AR (`1.234,56`), que Django
rechazaría antes de ejecutar `clean_<campo>`. La conversión tiene que ocurrir en
`to_python`.

Es la única fuente de verdad del desformateo en formularios: si hace falta un
comportamiento nuevo, se extiende acá y no se reimplementa en cada form.
"""
from django import forms


class DecimalARField(forms.DecimalField):
    """`DecimalField` que acepta el formato es-AR de los inputs `.fInputAR`."""

    def to_python(self, value):
        if isinstance(value, str):
            valor = value.strip()
            if valor:
                # Los puntos son separadores de miles y la coma es el decimal.
                value = valor.replace('.', '').replace(',', '.')
            else:
                value = valor
        return super().to_python(value)


class DateInputHTML5(forms.DateInput):
    """`<input type="date">` que muestra la fecha guardada al editar.

    LA TRAMPA: con `LANGUAGE_CODE = 'es-ar'`, Django renderiza el valor con el formato
    local (`28/08/2026`). Un input HTML5 de tipo `date` **sólo acepta `YYYY-MM-DD` en su
    atributo `value`** y descarta en silencio cualquier otra cosa: el campo aparece
    VACÍO. El registro tenía la fecha bien guardada, pero al editarlo parecía no tenerla,
    y si el usuario grababa así, la borraba sin querer.

    Del lado de la ENTRADA no hay problema: Django 5 agrega `%Y-%m-%d` a los
    `DATE_INPUT_FORMATS` del locale, así que lo que manda el navegador se parsea bien.
    El defecto es sólo de renderizado, que es lo que lo hace difícil de ver.

    Se usa en lugar de `forms.DateInput(attrs={'type': 'date'})` en todo formulario con
    fecha editable.
    """

    def __init__(self, attrs=None, format=None):
        atributos = {'type': 'date'}
        if attrs:
            atributos.update(attrs)
        super().__init__(attrs=atributos, format=format or '%Y-%m-%d')
