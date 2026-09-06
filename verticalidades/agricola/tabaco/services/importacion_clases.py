"""Importación del maestro de clases de tabaco desde CSV (Plan 081).

FORMATO DEL ARCHIVO — las tres cosas que lo rompen si no se contemplan:
    - UTF-8 **con BOM**: hay que abrirlo con `utf-8-sig` o la primera columna sale como
      `\\ufeffcodigo` y el lector no la encuentra.
    - separador `;`
    - decimal con **coma** (`0,85`)

CLAVE DE NEGOCIO
Se busca y se actualiza por `codigo` (1-75), que es estable y viene del sistema heredado. NUNCA
por pk: el id de Django no tiene ninguna relación con el código del maestro, y asumir que
coinciden es el error clásico de este tipo de importaciones.

TODO O NADA
Primero se valida el archivo entero y recién después se escribe, dentro de una transacción. Un
CSV con una fila mal no debe dejar el maestro a medio cargar: son 75 clases que forman precios.
"""
import csv
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db import transaction

from verticalidades.agricola.tabaco.models import ClaseTabaco, VariedadTabaco

# El CSV identifica la variedad con un entero. El mapeo lo confirmó el usuario y es la única
# interpretación válida: no se deduce del archivo.
VARIEDADES = {1: 'BURLEY', 2: 'VIRGINIA'}

COLUMNAS = ['codigo', 'id_var', 'detalle', 'porciento']


class ErrorImportacion(Exception):
    """El archivo no está en condiciones de importarse. No se escribió nada."""


@dataclass
class Resultado:
    creadas: int = 0
    actualizadas: int = 0
    sin_cambios: int = 0
    variedades_creadas: int = 0
    detalle: list = field(default_factory=list)

    @property
    def total(self):
        return self.creadas + self.actualizadas + self.sin_cambios


def leer_csv(ruta):
    """Devuelve las filas normalizadas. Levanta `ErrorImportacion` si el archivo no sirve."""
    try:
        with open(ruta, encoding='utf-8-sig', newline='') as f:
            lector = csv.DictReader(f, delimiter=';')
            if lector.fieldnames != COLUMNAS:
                raise ErrorImportacion(
                    f"Cabecera inesperada: se esperaba {COLUMNAS} y vino {lector.fieldnames}. "
                    f"Verificá que el separador sea ';' y que el archivo esté en UTF-8."
                )
            crudas = list(lector)
    except FileNotFoundError:
        raise ErrorImportacion(f"No se encontró el archivo: {ruta}")

    if not crudas:
        raise ErrorImportacion("El archivo no tiene filas.")

    filas, vistos = [], set()
    for n, cruda in enumerate(crudas, start=2):          # 2 = primera fila de datos
        try:
            codigo = int(cruda['codigo'])
            id_var = int(cruda['id_var'])
        except (TypeError, ValueError):
            raise ErrorImportacion(f"Línea {n}: 'codigo' e 'id_var' deben ser enteros.")

        if id_var not in VARIEDADES:
            raise ErrorImportacion(
                f"Línea {n}: id_var={id_var} desconocido. Los válidos son {sorted(VARIEDADES)}."
            )

        detalle = (cruda['detalle'] or '').strip().upper()
        if not detalle:
            raise ErrorImportacion(f"Línea {n}: la clase no puede estar vacía.")

        try:
            coeficiente = Decimal((cruda['porciento'] or '').strip().replace(',', '.'))
        except (InvalidOperation, AttributeError):
            raise ErrorImportacion(f"Línea {n}: coeficiente ilegible ({cruda['porciento']!r}).")
        if coeficiente <= 0:
            raise ErrorImportacion(f"Línea {n}: el coeficiente debe ser mayor que cero.")

        if codigo in vistos:
            raise ErrorImportacion(f"Línea {n}: el código {codigo} está duplicado en el archivo.")
        vistos.add(codigo)

        # Dentro de una misma variedad la clase tampoco puede repetirse. Es la validación que
        # detectó el `N5K` duplicado del maestro heredado (códigos 38 y 72, con coeficientes
        # distintos); el 72 correspondía al grupo T y se corrigió a `N5T`.
        clave = (id_var, detalle)
        if clave in vistos:
            raise ErrorImportacion(
                f"Línea {n}: la clase '{detalle}' ya aparece en la variedad "
                f"{VARIEDADES[id_var]}. Dos clases de la misma variedad no pueden llamarse igual."
            )
        vistos.add(clave)

        filas.append({'codigo': codigo, 'id_var': id_var,
                      'detalle': detalle, 'coeficiente': coeficiente})

    return filas


@transaction.atomic
def importar_clases(empresa, ruta, usuario=None, dry_run=False):
    """Carga o actualiza el maestro de clases. Idempotente: reejecutar no duplica.

    Devuelve un `Resultado` con el detalle de lo que pasó con cada clase.
    """
    filas = leer_csv(ruta)                    # valida TODO antes de tocar la base
    resultado = Resultado()

    variedades = {}
    for id_var, nombre in VARIEDADES.items():
        variedad, creada = VariedadTabaco.objects.get_or_create(
            empresa=empresa, codigo=id_var,
            defaults={'detalle': nombre, 'creado_por': usuario, 'modificado_por': usuario},
        )
        variedades[id_var] = variedad
        if creada:
            resultado.variedades_creadas += 1

    for fila in filas:
        variedad = variedades[fila['id_var']]
        clase = ClaseTabaco.objects.filter(
            empresa=empresa, variedad=variedad, codigo=fila['codigo']).first()

        if clase is None:
            ClaseTabaco.objects.create(
                empresa=empresa, variedad=variedad, codigo=fila['codigo'],
                detalle=fila['detalle'], coeficiente=fila['coeficiente'],
                creado_por=usuario, modificado_por=usuario,
            )
            resultado.creadas += 1
            resultado.detalle.append(f"ALTA    {variedad.detalle:9} {fila['detalle']:5} {fila['coeficiente']}")
            continue

        cambios = []
        if clase.detalle != fila['detalle']:
            cambios.append(f"clase {clase.detalle} -> {fila['detalle']}")
            clase.detalle = fila['detalle']
            clase.grupo = fila['detalle'][:1]
        if clase.coeficiente != fila['coeficiente']:
            cambios.append(f"coeficiente {clase.coeficiente} -> {fila['coeficiente']}")
            clase.coeficiente = fila['coeficiente']

        if cambios:
            clase.modificado_por = usuario
            clase.save()
            resultado.actualizadas += 1
            resultado.detalle.append(
                f"UPDATE  {variedad.detalle:9} cod.{fila['codigo']:<3} {', '.join(cambios)}")
        else:
            resultado.sin_cambios += 1

    if dry_run:
        transaction.set_rollback(True)

    return resultado
