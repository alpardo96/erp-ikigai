# Plan de Implementación: Autocompletado y Lupa en Reporte de Ventas por Producto

Este plan detalla los cambios para reemplazar los selectores desplegables tradicionales (comboboxes) de **Cliente** y **Producto** en el reporte de ventas por producto (`/ventas/reportes/productos-vendidos/`) por búsquedas optimizadas mediante autocompletado (typeahead) en tiempo real, agregando una lupa para búsqueda avanzada de clientes, y removiendo las consultas pesadas al cargar la página inicialmente. Además, se aplican mejoras de diseño y diagramación premium al panel de filtros.

## Requerimientos
1. **Cliente:** Autocompletado (typeahead) y botón de lupa (modal de búsqueda avanzada).
2. **Producto:** Solo autocompletado (typeahead), sin lupa.
3. **Optimización:** Quitar la carga completa de clientes y productos de la base de datos en la vista del reporte (`ReporteVentasProductoView`), mejorando significativamente el tiempo de respuesta inicial.
4. **Diseño:** 
   - Alinear los botones de Filtrar y Columnas a la derecha de la fila inferior.
   - Darle un estilo premium y formal a la selección de condición ("Real" / "Proyectado") usando toggle chips reactivos y balas dinámicas.

---

## Cambios Propuestos

### Componente: Facturación (Reportes)

#### [MODIFY] [views_reportes.py](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/facturacion/views_reportes.py)
* Modificar `obtener_items_ventas_filtrados` para resolver y guardar el nombre del producto seleccionado en `filtros_dict` como `producto_nombre` (similar a cómo se hace con `cliente_nombre`).
* Modificar `ReporteVentasProductoView.get` para no consultar `clientes` ni `productos` en la base de datos ni pasarlos en el contexto de renderizado, liberando memoria y agilizando la carga.

#### [MODIFY] [ventas_por_producto.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/facturacion/reportes/ventas_por_producto.html)
* Cambiar la distribución de la grilla de campos a `lg:grid-cols-4` para agrupar los 8 filtros principales de forma simétrica.
* Reemplazar el elemento `<select name="cliente">` por un input oculto para `cliente` (ID) y un input de texto para autocompletado (`typeahead_clientes`). Agregar el botón de la lupa (`ventas_cliente_buscar_modal`) apuntando al contenedor de modales.
* Reemplazar el elemento `<select name="producto">` por un input oculto para `producto` (ID) y un input de texto para autocompletado (`typeahead_productos_venta`).
* Diseñar la sección de Condición ("Real" / "Proyectado") a modo de toggle chips premium con estados reactivos utilizando `peer-checked` de Tailwind y `bg-current`.
* Ubicar el bloque de Condición a la izquierda de la fila inferior y los botones de acción ("Filtrar" y "Columnas") a la derecha, forzados a quedar alineados horizontalmente en la misma línea y divididos del resto del formulario por una línea sutil.
* Agregar un elemento `<div id="modal-container"></div>` al final de la plantilla para que sirva de destino para el modal de clientes.
* En el bloque `extra_js`, añadir los escuchas de eventos (`clienteVentaSeleccionado` y `productoVentaEncontrado`) para capturar la selección e impactar los valores correspondientes en el formulario.
* Asegurar que al borrar el contenido de los inputs de texto, se borre el ID oculto para poder buscar por "Todos".

#### [MODIFY] [tabla_ventas_producto.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/facturacion/reportes/partials/tabla_ventas_producto.html)
* Envolver la sección de tarjetas KPI en un condicional `{% if filtros.ejecutado %}` para que no se muestren datos vacíos ni KPI en cero en la pantalla de inicio limpia.
* Mover los botones de exportación (CSV / Excel) a una barra de cabecera dedicada en la tarjeta de la tabla, de modo que se sitúen arriba a la derecha de la tabla.
* Condicionar el bloque de exportación a `{% if filtros.ejecutado and items %}` para que los botones solo se muestren cuando el usuario haya ejecutado un filtro y existan registros, logrando que la vista de inicio no se rompa ni exponga enlaces vacíos.

---

## Plan de Verificación

### Pruebas Manuales
1. **Acceso inicial:** Ingresar a `/ventas/reportes/productos-vendidos/` y verificar que la carga sea instantánea, limpia de KPIs y botones vacíos de exportación.
2. **Distribución del formulario:** Validar que los campos principales formen una grilla compacta de 4 columnas en desktop, y los botones de acción se alineen a la derecha al final, con la condición a la izquierda.
3. **Estilo de Condición (Chips):** Seleccionar y deseleccionar "Real" y "Proyectado" validando que el color cambie de blanco a índigo y la bala interna cambie de color de forma fluida.
4. **Autocompletados:** Probar la selección de sugerencias y modal avanzado de clientes.
5. **Filtrado:** Presionar "Filtrar" y verificar la correcta consulta y actualización.
