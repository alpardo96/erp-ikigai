# Arquitectura "Modo Enchufe" (Plug & Play) para Verticalidades

Este documento establece la arquitectura definitiva y las reglas inflexibles para el desarrollo de módulos verticales (Armería, Distribución, Estudio, etc.) en el ERP Ikigai, garantizando que el sistema principal (Core) sea verdaderamente desacoplado y tolerante a fallos.

## 1. El Concepto Fundamental
- **Core (Estándar):** El motor principal (facturación, empresas, clientes, tesorería, contabilidad). Nunca depende rígidamente de una verticalidad.
- **Verticalidad:** Un módulo especializado que amplía las reglas del negocio, añade modelos satélites y pantallas propias.
- **La Regla de Oro:** Si la carpeta física de una verticalidad (ej. `verticalidades/distribucion/`) se elimina o se mueve del disco duro ("se desenchufa"), el sistema principal **DEBE** seguir arrancando y operando con normalidad. Prohibido arrojar `ModuleNotFoundError`.

## 2. Anatomía de una Verticalidad
Toda verticalidad es una Django App independiente que reside bajo el directorio `verticalidades/`. No debe dejar "residuos" de sus modelos o formularios en el Core.

Una verticalidad estándar contiene:
- `models.py`: Modelos propios y tablas satélites (ej. `ExtensionDistribuidora` con un `OneToOneField` hacia `facturacion.ClienteProveedor`).
- `forms.py`: Los formularios nativos de la verticalidad.
- `views.py` / `views_htmx.py`: Su lógica y renderizado HTMX.
- `urls.py`: Rutas propias.
- `migrations/`: Su historial de migraciones aislado.

## 3. Dinámica de Acople (Cómo el Core interactúa con el Enchufe)

### A. Auto-Descubrimiento (Settings y URLs)
El Core descubre automáticamente los módulos instalados. En `config/settings.py` (y de forma análoga en `config/urls.py`), se escanea el disco: si la carpeta existe y tiene la estructura correcta, se inyecta en `INSTALLED_APPS` y se exponen sus rutas. Si la carpeta se borra, Django deja de verla y el esquema SQL subyacente queda simplemente inactivo.

### B. Filtro Dinámico en Formularios del Core
Para evitar ofrecer módulos desinstalados, formularios como `empresas.forms.EmpresaForm` construyen dinámicamente sus opciones (`choices` del `tipo_actividad`) iterando sobre las carpetas que realmente existen en `verticalidades/`, contrastándolas con `Empresa.TIPO_ACTIVIDAD_CHOICES`.

### C. Importaciones Tolerantes a Fallos (Crucial)
Cuando una vista del Core (ej. el alta de clientes en `facturacion/views_htmx.py`) necesita instanciar o guardar información de un modelo satélite, **NUNCA** debe hacer una importación estática.

> [!WARNING] 
> **Forma Incorrecta (Rompe el enchufe):**
> ```python
> from verticalidades.armeria.models import ExtensionArmeria
> ```
> Si la carpeta no existe, Python arroja un `ModuleNotFoundError` en el arranque del servidor y el ERP entero crashea.

> [!TIP]
> **Forma Correcta (Modo Enchufe):**
> ```python
> try:
>     from verticalidades.armeria.models import ExtensionArmeria
>     from verticalidades.armeria.forms import ExtensionArmeriaForm
> except ImportError:
>     ExtensionArmeria = None
>     ExtensionArmeriaForm = None
> ```
> Luego, en la lógica de procesamiento, simplemente se valida la existencia de la clase:
> ```python
> puede_armeria = (empresa.tipo_actividad == 'ARMERIA') and (ExtensionArmeriaForm is not None)
> if puede_armeria:
>     # lógica específica de armería...
> ```

## 4. Guía de Implementación para FUTURAS Verticalidades
Si en el futuro se desea agregar una nueva verticalidad (por ejemplo, `agricola`), se deben seguir estos pasos rigurosamente para no romper la arquitectura:

1. **Creación del Módulo:** Crear el paquete `verticalidades/agricola/` con sus archivos base (`models.py`, `forms.py`, `views.py`, `urls.py`, `__init__.py`, `apps.py`).
2. **Registro de la Actividad:** En `empresas/models.py`, agregar a `TIPO_ACTIVIDAD_CHOICES` la constante para la nueva rama: `('AGRICOLA', 'Agrícola')`.
3. **Aislamiento de Modelos:** Definir cualquier modelo satélite estrictamente en `verticalidades/agricola/models.py`. Si requiere vincularse a un cliente o comprobante, usar ForeignKey hacia el modelo del Core.
4. **Aislamiento de Formularios:** Crear los formularios en `verticalidades/agricola/forms.py`.
5. **Inyección Cautelosa:** Si el Core necesita interactuar directamente con estos formularios o modelos, importar usando exclusivamente el patrón `try/except ImportError` documentado arriba.
6. **Migración Aislada:** Ejecutar `python manage.py makemigrations agricola` (para que su esquema de base de datos se maneje independientemente del facturador).
7. **Prueba de Fuego:** Terminado el desarrollo, mover temporalmente la carpeta `verticalidades/agricola/` a otra ubicación, correr `python manage.py check` y confirmar que el ERP principal sigue funcionando sin el módulo.

## Aprobación Requerida
Este plan refleja las normas que se aplicarán y respetarán estrictamente de aquí en adelante. Si estás de acuerdo con esta política arquitectónica, procederé a guardarla permanentemente en `docs/planes/075_arquitectura_modo_enchufe.md` (o el número que prefieras) para que sea la guía oficial del proyecto.
