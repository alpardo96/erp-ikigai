# Plan de Implementación 064: Refactorización y Limpieza de Catálogos (Eliminación de M2M Sucursales en Marcas, Rubros y Familias)
Fecha: 2026-08-22

## Resumen del Cambio
Eliminar las relaciones ManyToMany `sucursales` en los modelos `Marca`, `Rubro` y `Familia` en la app `productos`. Con este cambio, el catálogo maestro (Marcas, Rubros, Familias y Productos) pertenecerá de forma unificada e indivisible a la `Empresa`. La diferenciación por sucursal se mantiene de manera exclusiva en el inventario físico (`StockSucursal`), movimientos de stock, operaciones de caja y comprobantes.

---

## User Review Required

> [!IMPORTANT]
> **Cambio de Esquema en Base de Datos (Migración):**
> Al aplicar este cambio, Django generará una migración que eliminará las 3 tablas intermedias pivote (`productos_marca_sucursales`, `productos_rubro_sucursales`, `productos_familia_sucursales`). Esto **NO** afecta los datos principales de las marcas, rubros o familias existentes ni los productos asociados.

---

## Proposed Changes

### Módulo `productos`

#### [MODIFY] [`models.py`](file:///d:/JM_Soft/erp-ikigai-2/productos/models.py)
- Remover la definición `sucursales = models.ManyToManyField(Sucursal, related_name="marcas_disponibles")` del modelo `Marca`.
- Remover la definición `sucursales = models.ManyToManyField(Sucursal, related_name="rubros_disponibles")` del modelo `Rubro`.
- Remover la definición `sucursales = models.ManyToManyField(Sucursal, related_name="familias_disponibles")` del modelo `Familia`.

#### [NEW] [`migrations/XXXX_remove_sucursales_marca_rubro_familia.py`](file:///d:/JM_Soft/erp-ikigai-2/productos/migrations/)
- Migración autogenerada por Django mediante `python manage.py makemigrations` que remueve los campos M2M `sucursales`.

#### [MODIFY] [`forms.py`](file:///d:/JM_Soft/erp-ikigai-2/productos/forms.py)
- `MarcaForm`: Remover `'sucursales'` de `fields` y `widgets`. Quitar del `__init__` la inicialización de `sucursales`.
- `RubroForm`: Remover `'sucursales'` de `fields` y `widgets`. Quitar del `__init__` la inicialización de `sucursales`.
- `FamiliaForm`: Remover `'sucursales'` de `fields` y `widgets`. Quitar del `__init__` la inicialización de `sucursales`.

#### [MODIFY] [`views_htmx.py`](file:///d:/JM_Soft/erp-ikigai-2/productos/views_htmx.py)
- En `marca_modal`, `rubro_prod_modal` y `familia_modal`, remover la llamada redundante `form.save_m2m()`.

#### [MODIFY] [`migrar_productos.py`](file:///d:/JM_Soft/erp-ikigai-2/productos/management/commands/migrar_productos.py)
- Remover las asignaciones `.sucursales.add(suc_central, suc_yb)` en la creación de rubros, familias y marcas.

---

### Modales y Plantillas HTML

#### [MODIFY] [`marca_modal.html`](file:///d:/JM_Soft/erp-ikigai-2/templates/productos/modals/marca_modal.html)
- Remover el bloque visual `<div class="bg-slate-50...>` con el label *"Habilitar en Sucursales"*.

#### [MODIFY] [`rubro_prod_modal.html`](file:///d:/JM_Soft/erp-ikigai-2/templates/productos/modals/rubro_prod_modal.html)
- Remover el bloque visual con el label *"Habilitar en Sucursales"*.

#### [MODIFY] [`familia_modal.html`](file:///d:/JM_Soft/erp-ikigai-2/templates/productos/modals/familia_modal.html)
- Remover el bloque visual con el label *"Habilitar en Sucursales"*.

#### [MODIFY] [`marcas.html`](file:///d:/JM_Soft/erp-ikigai-2/templates/configuracion/partials/marcas.html)
- Quitar la columna del encabezado `<th>Sucursales</th>` de la tabla.

#### [MODIFY] [`marcas_list.html`](file:///d:/JM_Soft/erp-ikigai-2/templates/configuracion/partials/marcas_list.html)
- Quitar la celda `<td>` que itera `marca.sucursales.all`.

#### [MODIFY] [`rubros_prod.html`](file:///d:/JM_Soft/erp-ikigai-2/templates/configuracion/partials/rubros_prod.html)
- Quitar la columna del encabezado `<th>Sucursales</th>`.

#### [MODIFY] [`rubros_prod_list.html`](file:///d:/JM_Soft/erp-ikigai-2/templates/configuracion/partials/rubros_prod_list.html)
- Quitar la celda `<td>` que itera `rubro.sucursales.all`.

#### [MODIFY] [`familias.html`](file:///d:/JM_Soft/erp-ikigai-2/templates/configuracion/partials/familias.html)
- Quitar la columna del encabezado `<th>Sucursales</th>`.

#### [MODIFY] [`familias_list.html`](file:///d:/JM_Soft/erp-ikigai-2/templates/configuracion/partials/familias_list.html)
- Quitar la celda `<td>` que itera `familia.sucursales.all`.

---

## Verification Plan

### Automated Tests
- Ejecutar la suite completa de pruebas unitarias:
  `python manage.py test`
- Verificar que no haya errores de importación ni referencias rotas a `sucursales`.

### Manual Verification
- Ingresar al panel de Configuración -> Marcas / Rubros / Familias.
- Probar el alta y la edición de una Marca, Rubro y Familia comprobando que los modales se abren y guardan correctamente sin pedir sucursales.
- Verificar que las tablas de listados se renderizan limpias y ordenadas sin la columna "Sucursales".
