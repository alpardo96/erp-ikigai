# Plan de Implementación - Mejoras y Optimización en Libro Diario (Plan 040)

Este plan abarca las 6 mejoras solicitadas para el **Libro Diario y la gestión de Asientos Contables** dentro del módulo `contable`.

---

## 1. Requerimientos a Implementar

1. **Carga Diferida en Libro Diario & Filtro por `asiento_id`:**
   - Evitar la ejecución automática de consultas en la carga inicial de la pantalla. El Libro Diario permanecerá limpio hasta que el usuario defina los filtros y presione **Filtrar**.
   - Incorporar controles de filtro por rango de número de asiento (`asiento_desde` y `asiento_hasta`).
2. **Columna Primera: `asiento_id`:**
   - Reemplazar la columna `Nº Diario` por `ID Asiento` (`cble_asiento_enc.asiento_id`) como primera columna identificadora en el listado del diario.
3. **Despliegue de Movimientos del Asiento (`cble_asiento_mov`):**
   - Al hacer clic sobre cualquier fila del asiento, desplegar el detalle completo de sus líneas (`AsientoLinea`: cuenta con jerarquía y nombre, leyenda, debe y haber), ajustando los textos de condición (1=Real, 2=Proyectado, 3=Apertura).
4. **Selector de Condición en Modal Nuevo Asiento (OptionGroup / Choices 1 y 2):**
   - Configurar el campo `condic` en `AsientoEncForm` y en la plantilla del modal para ofrecer las opciones explícitas `1 - Real` y `2 - Proyectado`.
5. **Textbox Inteligente (Typeahead) para Cliente / Proveedor:**
   - Integrar el componente de búsqueda asíncrona tipo autocompletado inteligente (`typeahead_clientes`) en la selección de `cli_pro` en la cabecera del asiento.
6. **Textbox Inteligente (Typeahead) para Cuentas Contables en Líneas de Asiento:**
   - Reemplazar los `<select>` tradicionales de cuentas contables en la grilla dinámica del modal por el buscador inteligente (`typeahead_cuentas_contable`), facilitando la búsqueda por jerarquía o nombre de la cuenta.

---

## User Review Required

- La carga inicial del Libro Diario ya no traerá automáticamente los primeros 200 asientos, garantizando respuesta instantánea.
- La columna `Nº Diario` será sustituida en la grilla por `ID Asiento` (`asiento_id`).

---

## Proposed Changes

### Módulo Contable (`contable/`)

#### [MODIFY] [forms.py](file:///d:/JM_Soft/erp-ikigai-2/contable/forms.py)
- Actualizar `AsientoEncForm` para definir las opciones explícitas de `condic` como `[(1, '1 - Real'), (2, '2 - Proyectado')]`.

#### [MODIFY] [views_htmx.py](file:///d:/JM_Soft/erp-ikigai-2/contable/views_htmx.py)
- En `libro_diario_rows`:
  - Retornar `Asiento.objects.none()` si no se ha enviado el parámetro `filtering=1` o submiteado el formulario.
  - Soportar filtrado por `asiento_desde` (`asiento_id__gte`) y `asiento_hasta` (`asiento_id__lte`).
- En `detalle_asiento`:
  - Asegurar la carga optimizada con `select_related('cuenta', 'cli_pro')` y corregir las etiquetas de condición (1=Real, 2=Proyectado, 3=Apertura).

---

### Plantillas del Módulo Contable (`templates/contable/`)

#### [MODIFY] [libro_diario.html](file:///d:/JM_Soft/erp-ikigai-2/templates/contable/partials/libro_diario.html)
- Quitar `hx-trigger="load"` automático para evitar consultas iniciales.
- Agregar botón explícito **Filtrar** y controles de rango para `asiento_desde` y `asiento_hasta`.
- Cambiar encabezado de tabla `Nº Diario` por `ID Asiento`.

#### [MODIFY] [libro_diario_rows.html](file:///d:/JM_Soft/erp-ikigai-2/templates/contable/partials/libro_diario_rows.html)
- Mostrar `asiento.asiento_id` en la primera columna visible.
- Agregar mensaje de bienvenida en estado vacío cuando no se han aplicado filtros.

#### [MODIFY] [detalle_asiento.html](file:///d:/JM_Soft/erp-ikigai-2/templates/contable/partials/detalle_asiento.html)
- Perfeccionar la estructura de la grilla desplegable de movimientos con etiquetas precisas de condición y totales.

#### [MODIFY] [asiento_form.html](file:///d:/JM_Soft/erp-ikigai-2/templates/contable/modals/asiento_form.html)
- Implementar el buscador inteligente (typeahead) de `Cliente/Proveedor`.
- Reemplazar la selección de cuentas en la tabla de líneas por el buscador inteligente de cuentas contables por jerarquía y nombre.
- Ajustar el selector de condición a `1 - Real` y `2 - Proyectado`.

---

### Pruebas Automatizadas

#### [NEW] [test_libro_diario_mejoras.py](file:///d:/JM_Soft/erp-ikigai-2/contable/tests/test_libro_diario_mejoras.py)
- Pruebas para:
  1. Carga inicial diferida (0 resultados en GET limpio).
  2. Búsqueda por rango de `asiento_id` (desde / hasta).
  3. Despliegue de movimientos del asiento.
  4. Creación de asiento con `condic=1` y `condic=2`.
  5. Respuestas de typeahead para clientes y cuentas contables.

---

## Verification Plan

### Automated Tests
```bash
.\venv\Scripts\python.exe manage.py test contable.tests.test_libro_diario_mejoras --keepdb
```

### Manual Verification
1. Abrir `/contable/libro-diario/` y verificar que la pantalla carga de forma instantánea sin traer asientos previa filtración.
2. Filtrar por rango de `ID Asiento` (ej: desde 1 hasta 10) y verificar la grilla.
3. Hacer clic sobre un asiento y comprobar la apertura limpia de sus movimientos.
4. Presionar **Nuevo Asiento**, validar el selector `1 - Real / 2 - Proyectado`, y probar los dos buscadores inteligentes (Cliente/Proveedor y Cuenta Contable en cada línea).
