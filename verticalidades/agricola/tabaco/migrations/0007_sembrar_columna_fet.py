"""Siembra `columna_fet` en los conceptos ya cargados (Plan 087).

POR QUÉ EXISTE ESTA MIGRACIÓN
El usuario cargó sus conceptos de retención antes de que la planilla FET existiera, y los bautizó
con SUS códigos: `RET-IVA`, `RET-GCIAS`, `USO AGUA`, `EEAOC`, `SALUD`. Pedirle ahora que entre a
cada uno a decir en qué columna va sería trasladarle el costo de una decisión de diseño que se
tomó tarde. Se resuelve acá, una sola vez.

CÓMO SE DEDUCE, DEL CRITERIO MÁS FIRME AL MÁS LAXO
1. Por `tipo_base`, que es ESTRUCTURAL y no depende de cómo se haya bautizado el concepto: sólo la
   retención de IVA se calcula sobre el IVA (`tipo_base='IVA'`) y sólo Ganancias sobre el
   acumulado mensual (`ACUM_MENSUAL`). Esas dos quedan resueltas sin mirar un solo nombre.
2. Por palabra clave en el código o el detalle, para las tres que comparten base `NETO` y no se
   pueden distinguir de otra forma.

Lo que no encaja queda VACÍO, que significa «Otras retenciones» — una columna real de la planilla,
no un error. El usuario lo puede corregir desde el ABM en cualquier momento.

La reversa deja el campo vacío: es un dato derivado, no información que se pierda.
"""
from django.db import migrations

# (columna, bases estructurales que la resuelven, palabras clave del nombre)
REGLAS = [
    ('ret_iva', {'IVA'}, ()),
    ('ret_ganancias', {'ACUM_MENSUAL'}, ()),
    ('ret_eeaoc', set(), ('EEAOC',)),
    ('ret_salud', set(), ('SALUD',)),
    ('ret_agua', set(), ('AGUA',)),
]


def columna_de(codigo, detalle, tipo_base):
    for columna, bases, _claves in REGLAS:
        if tipo_base and tipo_base in bases:
            return columna

    texto = f"{codigo or ''} {detalle or ''}".upper()
    for columna, bases, claves in REGLAS:
        # Las que se resuelven por base NO se buscan por nombre: una retención con base NETO
        # llamada «IVA PROVINCIAL» caería en la columna equivocada.
        if bases:
            continue
        if any(palabra in texto for palabra in claves):
            return columna

    return ''


def sembrar(apps, schema_editor):
    TipoRetencionTabaco = apps.get_model('tabaco', 'TipoRetencionTabaco')

    for concepto in TipoRetencionTabaco.objects.all():
        columna = columna_de(concepto.codigo, concepto.detalle, concepto.tipo_base)
        if columna and concepto.columna_fet != columna:
            concepto.columna_fet = columna
            concepto.save(update_fields=['columna_fet'])


def limpiar(apps, schema_editor):
    TipoRetencionTabaco = apps.get_model('tabaco', 'TipoRetencionTabaco')
    TipoRetencionTabaco.objects.update(columna_fet='')


class Migration(migrations.Migration):

    dependencies = [
        ('tabaco', '0006_columna_fet'),
    ]

    operations = [
        migrations.RunPython(sembrar, limpiar),
    ]
