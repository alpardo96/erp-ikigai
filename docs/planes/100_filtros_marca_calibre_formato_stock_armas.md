# Plan de Implementación: Optimización de Filtros, Formato de Moneda AR y Selectores Excel para Marca/Calibre en Stock de Armas

- **Número de Plan**: 100
- **Fecha**: 30 de Septiembre de 2026
- **Responsable**: Cristian - PC CASA
- **Módulo**: Verticalidades / Armería (`verticalidades/armeria/`)

---

## 1. Objetivos

1. **Eliminar redundancia en filtro de condición:**
   - Quitar el botón `USADAS` del selector superior de pestañas/familias (`#familia-pills`), dejando exclusivamente las familias de armas (`TODOS`, `PISTOLA`, `ESCOPETA`, `CARABINA`, `FUSIL`, `PISTOLÓN`).
   - Mantener el control de condición (`Nuevo` / `Usado` / `Todas`) en el desplegable de filtros del formulario.

2. **Formato Argentino (`formato_ar`) en Precios y Cotizaciones:**
   - Cargar `{% load formato_tags %}` y aplicar el filtro `|formato_ar` tanto en la grilla (`stock_armas_grilla.html`) como en el modal de detalle (`stock_armas_detalle_modal.html`) para precios en pesos ($), dólares (U$S) y cotización de referencia.

3. **Rebalanceo Visual de Campos de Búsqueda:**
   - Asignar `maxlength="16"` y ancho visual de 16 caracteres al campo **Nro. Serie**.
   - Asignar `maxlength="9"` y ancho visual de 9 caracteres al campo **CUIM**.
   - Reducir el ancho de la **Búsqueda Rápida** eliminando su comportamiento expansivo desproporcionado.

4. **Filtros Múltiples con Buscador Tipo Excel (Marca y Calibre):**
   - Extraer Marca y Calibre de la búsqueda rápida y dotarlos de componentes de filtrado múltiple desplegable (estilo Excel / faceted filter) utilizando Alpine.js y HTMX.
   - Cada desplegable contará con:
     - Input de búsqueda rápida interna para filtrar opciones de la lista.
     - Botones "Seleccionar todo" y "Deseleccionar todo" / "Limpiar".
     - Lista con scroll y checkboxes individuales.
     - Contador de ítems seleccionados en el botón activador.
     - Disparo reactivo mediante HTMX al cambiar selecciones.
   - En el backend (`StockArmasListView`):
     - Recepción de listas `marcas` y `calibres` mediante `request.GET.getlist()`.
     - Filtrado exacto mediante `producto__marca_id__in` y `producto__unidad_venta__in`.
     - Entrega de catálogos dinámicos de marcas y calibres disponibles para la empresa en `get_context_data`.

---

## 2. Análisis de Archivos Involucrados

| Archivo | Acción | Descripción del Cambio |
|---------|--------|------------------------|
| `verticalidades/armeria/views.py` | Modificar | Agregar procesamiento de listas `marcas` y `calibres` en `get_queryset()`, y poblar catálogos en `get_context_data()`. Limpiar tokens de Marca/Calibre en búsqueda rápida. |
| `verticalidades/armeria/templates/armeria/stock_armas_list.html` | Modificar | Eliminar botón `USADAS` de pills. Redimensionar inputs de Serie (16 chars) y CUIM (9 chars). Incorporar selectores multichoice tipo Excel con Alpine.js para Marca y Calibre. Actualizar `resetFiltrosStock()`. |
| `verticalidades/armeria/templates/armeria/partials/stock_armas_grilla.html` | Modificar | Cargar `formato_tags` y formatear precios con `|formato_ar`. |
| `verticalidades/armeria/templates/armeria/partials/stock_armas_detalle_modal.html` | Modificar | Cargar `formato_tags` y formatear precios con `|formato_ar`. |
| `verticalidades/armeria/tests/test_stock_armas_filtros.py` | Crear | Pruebas unitarias para filtrado múltiple de marcas, calibres, serie, cuim y verificación del formato de precios. |

---

## 3. Plan de Pruebas

1. **Pruebas de Backend:**
   - Ejecutar `python manage.py test verticalidades.armeria.tests.test_stock_armas_filtros`.
   - Validar filtros combinados (familia + condición + marcas múltiples + calibres múltiples).
2. **Pruebas Visuales y de Interfaz:**
   - Probar en `http://localhost:8000/stock/armas/`:
     - Apertura y cierre de los dropdowns de Marca y Calibre.
     - Búsqueda en vivo dentro de los dropdowns.
     - Botones Seleccionar todo / Limpiar.
     - Ancho adecuado de los inputs Nro. Serie (16 caracteres) y CUIM (9 caracteres).
     - Visualización correcta de precios con separador de miles y coma decimal argentina (ej. `$ 1.250.000,00`).
