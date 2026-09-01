# Visualización de Stock Activo y Stock Destino en Buscador Avanzado de Productos

Este plan de implementación ha sido actualizado con las especificaciones acordadas:
1. **Comportamiento Estándar (Compras, Ventas, Recepción, OC, etc.):** El modal de búsqueda de productos muestra la columna de **Stock** correspondiente a la sucursal activa en la sesión.
2. **Comportamiento para Remitos Internos:** Se muestra la columna de **Stock** de la sucursal de origen (activa) y se añade una columna adicional de **Stock Destino** para verificar existencias y necesidad de reposición en destino.

## Revisión del Usuario Requerida

> [!NOTE]
> - **Estándar:** Se agrega la visualización de Stock de la sucursal activa en el modal de búsqueda general.
> - **Remitos Internos:** Se pasa `sucursal_origen` (o sucursal activa) y `sucursal_destino`, visualizando dos columnas de stock: **Stk. Origen/Activa** y **Stk. Destino**.

## Preguntas Abiertas

*No se detectan dudas. Las especificaciones han sido confirmadas por el usuario.*

## Cambios Propuestos

### Módulo de Facturación y Plantillas HTMX

#### [MODIFY] [remito_interno_carga.html](file:///d:/JM_Soft/erp-ikigai-2/templates/facturacion/remito_interno_carga.html)
- Modificar el botón de la lupa que abre `compras_producto_buscar_modal` agregando `hx-include="[name='sucursal_origen'], [name='sucursal_destino']"` para transmitir las sucursales elegidas en el formulario.

#### [MODIFY] [views_htmx.py](file:///d:/JM_Soft/erp-ikigai-2/facturacion/views_htmx.py)
- **`buscador_productos_modal(request)`**:
  - Capturar `sucursal_origen` (o default `request.session.get('sucursal_id')`) y `sucursal_destino` de `request.GET`.
  - Obtener las instancias de `Sucursal` de origen/activa y destino.
  - Pasar IDs y objetos de las sucursales al contexto de `buscador_productos.html`.
- **`lista_productos_resultados(request)`**:
  - Determinar `sucursal_origen_id` = `request.GET.get('sucursal_origen')` o `request.session.get('sucursal_id')`.
  - Determinar `sucursal_destino_id` = `request.GET.get('sucursal_destino')`.
  - Consultar en `StockSucursal` para la lista de productos (hasta 50).
  - Asignar `stock_actual` (o `stock_origen`) y `stock_destino` (si aplica) a cada objeto `Producto`.
  - Pasar los datos de sucursales y stock a `productos_search_results.html`.

#### [MODIFY] [buscador_productos.html](file:///d:/JM_Soft/erp-ikigai-2/templates/facturacion/modals/buscador_productos.html)
- Incluir inputs ocultos en `thead` (`sucursal_origen` y `sucursal_destino`) para que los filtros de búsqueda preserven las sucursales.
- Actualizar el `hx-get` inicial del `tbody` con los parámetros correspondientes.
- Ajustar cabecera `thead`:
  - Columna **Stock** (Stock en sucursal activa u origen).
  - Columna **Stk. Destino** (solo cuando `sucursal_destino` está presente).

#### [MODIFY] [productos_search_results.html](file:///d:/JM_Soft/erp-ikigai-2/templates/facturacion/partials/productos_search_results.html)
- Renderizar la celda con el **Stock** de la sucursal activa con insignias de color (verde si > 0, rojo si <= 0).
- Renderizar la celda **Stk. Destino** si está presente en el contexto.
- Ajustar `colspan` en mensaje vacío (6 columnas en modo estándar con Stock activo, 7 columnas cuando se incluya Stock Destino).

## Plan de Verificación

### Pruebas Automatizadas
- Ejecutar pruebas unitarias del módulo de facturación: `pytest facturacion/tests/` o `python manage.py test facturacion`.

### Verificación Manual
1. Abrir **Buscador Avanzado de Productos** en Carga de Compras tradicional -> Verificar que muestre el Stock de la sucursal activa.
2. Abrir **Buscador Avanzado de Productos** en **Remito Interno** -> Verificar que muestre Stock Origen (activa) y Stock Destino.
