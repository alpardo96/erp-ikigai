# Plan 004 — Vistas de Facturación HTMX y Alertas de Stock

## Estado: ✅ Completado (Fase 5B del walkthrough)

## Descripción del Objetivo
Mejorar y unificar las pantallas de Punto de Venta (`ventas_carga.html`) y Carga de Compras (`compras_carga.html`), introduciendo la funcionalidad de "Alerta visual de stock negativo" solicitada por el usuario, sin bloquear la operatoria. Adicionalmente, sentar las bases para la futura exportación a ARCA (AFIP) mediante generación de CSV.

## Estado Actual
- Las pantallas base existen con diseño Tailwind y HTMX (`ventas_carga.html`, `compras_carga.html`).
- Tienen modales de búsqueda rápida integrados y uso intensivo de sesiones.
- **Falta**: Alerta de stock negativo al momento de agregar un producto a la grilla de ventas.

## Cambios Propuestos

### 1. Modificar Controlador de Ventas (`facturacion/views_htmx.py`)
- Modificar `agregar_item_venta_sesion` para consultar el `StockSucursal` actual del producto antes de agregarlo.
- Calcular si la cantidad a vender superará el stock físico (`stock_actual < cantidad_pedida`).
- Guardar el flag `alerta_stock: True` y el valor real del stock dentro del diccionario del ítem en la variable de sesión `venta_items_temp`.

### 2. Modificar UI de Grilla de Ventas (`templates/facturacion/partials/venta_items_tabla.html`)
- Cambiar el color de fondo o el texto de la fila (ej. `bg-orange-50` o text-color específico) si el ítem tiene `alerta_stock`.
- Agregar un tooltip o ícono `⚠️` al lado del nombre del producto indicando: "Stock insuficiente (Disponible: X)".
- Esto cumple con la directiva: *"No deberíamos bloquear pero sí avisar"*.

### 3. Ajustes UI en Búsqueda y Carga
- Asegurarse de que el modal de búsqueda de ventas también muestre el stock disponible de forma más evidente.
- Aplicar la misma lógica en la edición rápida en grilla (`editar_item_venta_sesion`), recalculando el estado de la alerta.

### 4. Preparación para ARCA (AFIP)
- Dado el documento `Facturacion Electronica ARCA.md`, sabemos que se requiere exportar un CSV `plantilla_facturacion.csv` con formato específico.
- (Opcional por ahora) Crear un botón en la lista de comprobantes para "Exportar a Facturador ARCA", que iterará los comprobantes y generará el CSV en el formato requerido.

## Verificación
- Cargar un producto con stock suficiente: La fila debe ser normal.
- Cargar un producto donde la cantidad es mayor al stock: La fila debe marcar un *Warning* visual claro.
- Verificar que el cierre de la venta siga funcionando correctamente a pesar de la alerta de stock negativo.
