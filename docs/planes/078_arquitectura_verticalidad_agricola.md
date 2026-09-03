# Arquitectura de Verticalidad Agrícola (Modo Enchufe)

Este documento establece la arquitectura definitiva para la verticalidad "Agrícola", incorporando sub-aplicaciones (Tabaco, Granos), reglas estrictas de nomenclatura de base de datos y respetando la arquitectura de "Modo Enchufe".

## Reglas Globales de la Verticalidad
1. **Nomenclatura de Tablas:** Absolutamente TODAS las tablas que se generen para esta verticalidad (ya sea en el core agrícola, tabaco o granos) **deberán empezar con el prefijo `agricola_`** (ej. `db_table = 'agricola_empresa_vertical'`, `db_table = 'agricola_tabaco_lote'`). Esto es innegociable para mantener el aislamiento a nivel de base de datos.
2. **Encapsulamiento:** Todo lo referido a agrícola se trabajará de forma aislada sobre su propia app (la carpeta `verticalidades/agricola`). Ningún modelo, vista o formulario debe "ensuciar" el sistema central.

## Arquitectura Propuesta

### 1. Auto-Descubrimiento de Sub-Apps en `settings.py`
Dado que `agricola` funcionará como un contenedor de múltiples módulos, se modifica `config/settings.py`. Si el auto-descubridor detecta la carpeta `agricola`, escaneará sus subdirectorios buscando archivos `__init__.py` y registrará las sub-apps en `INSTALLED_APPS` (ej. `verticalidades.agricola.tabaco`, `verticalidades.agricola.granos`).

### 2. Estructura de Carpetas (Esqueleto Inicial)
Se crea el siguiente árbol de directorios:

- `verticalidades/agricola/__init__.py`
- `verticalidades/agricola/core_agricola/__init__.py`, `apps.py`, `models.py`, `forms.py`
- `verticalidades/agricola/tabaco/__init__.py`, `apps.py`, `models.py`, `views.py`, `urls.py`
- `verticalidades/agricola/granos/__init__.py`, `apps.py`, `models.py`, `views.py`, `urls.py`

*(Los archivos de Tabaco y Granos nacen con la estructura mínima vacía, para luego ir dándoles lógica individualmente).*

### 3. Modelo `EmpresaVertical` (Tabla Satélite)
Dentro de `verticalidades/agricola/core_agricola/models.py`, se crea la tabla para gestionar las subactividades:

```python
from django.db import models
from empresas.models import Empresa

class EmpresaVertical(models.Model):
    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name="agricola_vertical")
    hace_tabaco = models.BooleanField(default=False, verbose_name="Tabaco")
    hace_granos = models.BooleanField(default=False, verbose_name="Granos (Soja, Maíz, Poroto, etc.)")

    class Meta:
        db_table = "agricola_empresa_vertical"
        verbose_name = "Configuración Agrícola"
        verbose_name_plural = "Configuraciones Agrícolas"
```

### 4. Inyección en la Vista de Empresas (Modo Enchufe Seguro)
Para que los checkboxes de Tabaco y Granos aparezcan en el ABM de Empresas (Core) cuando se seleccione "Agrícola":
1. **En `verticalidades/agricola/core_agricola/forms.py`:** Se crea un `EmpresaVerticalForm`.
2. **En `empresas/views.py` (Core):** Se utiliza el patrón `try/except ImportError` para importar el formulario de la verticalidad de forma segura. Si el módulo existe, el formulario se pasa al contexto.
3. **En `empresas/.../form.html` (Core):** Se renderiza el formulario satélite **solo si** existe en el contexto. Mediante JS (Alpine/Vanilla), se muestra u oculta dinámicamente este bloque cuando el `tipo_actividad` sea igual a `AGRICOLA`.
4. **Al guardar:** La vista de Empresa guarda tanto la Empresa principal como su configuración vertical asociada.
