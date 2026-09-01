# Plan de Implementación - 039: Reporte de Ventas por Producto

Fecha: 09/08/2026

Se implementará un nuevo reporte dentro del **Módulo de Ventas** denominado **"Reporte de Ventas por Producto"** ("Productos Vendidos"). Este reporte permitirá la consulta dinámica en pantalla con visibilidad configurable de columnas, así como la descarga en formatos **CSV** (con la totalidad de los 74 campos del estándar ERP legacy) y **Excel** (con diseño elegante, membrete, formateo numérico y totales).

---

## Requerimientos y Especificación

1. **Pantalla (HTML/HTMX):** 
   - Tabla interactiva con selector desplegable de columnas ("Columnas") para mostrar u ocultar campos dinámicamente según preferencia del usuario, persistiendo la selección en `localStorage`.
   - Búsqueda asíncrona mediante HTMX sin recarga de página.
2. **Filtros requeridos:**
   - Fecha desde y Fecha hasta.
   - Sucursal (Todas / Una específica).
   - Cliente (Todos / Uno específico).
   - Producto (Todos / Uno específico).
   - Rubro (Todos / Uno específico).
   - Familia (Todas / Una específica).
   - Vendedor (Todos / Uno específico).
   - Fiscal (`condic=1`, checkbox).
   - No Fiscal (`condic=2`, checkbox).
3. **Exportación CSV:** 
   - Contendrá la totalidad de los **74 campos** coincidiendo exactamente con la estructura de `productos_vendidos_1.csv`.
4. **Exportación Excel:** 
   - Contendrá las **38 columnas estructuradas** coincidiendo con el diseño elegante de `productos_vendidos.xlsx`, incluyendo el membrete superior de empresa/período y la fila final de totales calculados.

---

## Archivos Afectados / Creados

### Módulo `facturacion`
- `facturacion/services/ventas_reportes_excel.py` [NUEVO]
- `facturacion/views_reportes.py` [NUEVO]
- `templates/facturacion/reportes/ventas_por_producto.html` [NUEVO]
- `templates/facturacion/reportes/partials/tabla_ventas_producto.html` [NUEVO]
- `config/urls.py` [MODIFICACIÓN]
- `templates/facturacion/ventas_index.html` [MODIFICACIÓN]
- `templates/base.html` [MODIFICACIÓN]
- `facturacion/tests/test_reporte_ventas_producto.py` [NUEVO]

---

## Plan de Verificación

### Pruebas Automatizadas
- `python manage.py test facturacion.tests.test_reporte_ventas_producto`
  - Verificación de filtros por fecha, cliente, producto, rubro, familia, vendedor y tipo de condición fiscal/no fiscal.
  - Verificación del contenido y estructura de la exportación CSV (74 columnas).
  - Verificación del flujo de exportación Excel `.xlsx`.

### Pruebas Manuales
- Navegación al reporte `/ventas/reportes/productos-vendidos/`.
- Verificación del selector de columnas y persistencia en `localStorage`.
- Descarga y validación visual de los archivos CSV y Excel.
