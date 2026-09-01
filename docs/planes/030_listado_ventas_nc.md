# Listado de Ventas y Anulación (Notas de Crédito)

## Descripción
Creación de un listado interactivo en el módulo de Ventas que permita filtrar comprobantes emitidos por rango de fechas, cliente (todos o uno específico), sucursal, vendedor y tipo de comprobante.
Se integrará la funcionalidad para "anular" facturas, que consistirá en la emisión de Notas de Crédito parciales o totales. Esto se realizará a través de un modal interactivo donde el usuario podrá ver el detalle de los ítems facturados y elegir la cantidad a devolver de cada producto.

> [!WARNING]
> ## Revisión del Usuario Requerida
> **1. Mapeo de Comprobantes (AFIP):**
> Para saber qué Nota de Crédito corresponde a cada Factura (Ej: Factura A -> NC A), ¿utilizamos los códigos estándares de AFIP (001 -> 003, 006 -> 008, 011 -> 013) guardados en el modelo `TipoComprobante`?
> **2. Movimiento de Stock:**
> Al emitir una Nota de Crédito (devolución parcial o total), ¿debemos reingresar la mercadería al stock generando los movimientos correspondientes? (Asumo que sí).
> **3. Contabilidad / Saldos:**
> Se asume que la NC generada restará en el saldo adeudado por el cliente, ya que el `TipoComprobante` de la NC debería tener `signo = -1`.

## Cambios Propuestos

### Componente: Vistas y URLs

#### [MODIFY] config/urls.py o facturacion/urls_...
- Se añadirán las siguientes rutas:
  - `/ventas/listado/`: Para renderizar la nueva vista con filtros.
  - `/ventas/<int:id>/anular/modal/`: Para traer el formulario (vía HTMX) con el detalle de los productos.
  - `/ventas/<int:id>/anular/procesar/`: Endpoint POST para ejecutar la creación de la NC.

#### [MODIFY] facturacion/views.py y/o facturacion/views_htmx.py
- **`VentasListView`**: Vista basada en clases (espejada a `ComprasListView`) que recibirá y procesará los filtros (`desde`, `hasta`, `cliente`, `sucursal`, `vendedor`, `comprobante`).
- **`VentaAnularModalView`**: Devolverá el fragmento HTML del modal con los ítems y cantidades de la factura.
- **`VentaEmitirNotaCreditoView`**: Procesará el formulario, validará las cantidades solicitadas y llamará al servicio de negocio para emitir la NC.

---

### Componente: Plantillas (Templates)

#### [NEW] templates/facturacion/ventas_list.html
- Interfaz gráfica con buscador lateral/superior y tabla de resultados (fecha, tipo, número, cliente, total, acciones).
- Botón en cada fila para "Anular/NC" si el comprobante permite anulación.

#### [NEW] templates/facturacion/partials/venta_anular_modal.html
- Modal HTMX que contendrá el detalle del comprobante.
- Cada ítem mostrará: Producto, Precio, Cantidad Facturada, y un `input` numérico para "Cantidad a Devolver" (por defecto el total).

---

### Componente: Lógica de Negocio

#### [NEW] facturacion/services/notas_credito.py
- Se creará una capa de servicio `emitir_nota_credito(venta_original, devoluciones, usuario)` que centralice la creación:
  - Determinar el `TipoComprobante` (NC A, B o C según corresponda).
  - Instanciar la cabecera `Venta`.
  - Crear los `VentaItem` por las cantidades devueltas.
  - Ejecutar `recalcular_totales()`.
  - Actualizar saldo del cliente (la NC suma crédito).
  - Generar registros en `Movimiento` con stock entrante (reversión de salida).

## Plan de Verificación

### Pruebas Manuales
1. Crear una Factura A con 2 productos (Cantidades: 5 y 10).
2. Ir al listado de Ventas y aplicar los filtros correspondientes.
3. Hacer click en "Anular" y en el modal dejar 2 unidades del primer producto y 0 del segundo.
4. Confirmar y verificar la generación de la Nota de Crédito A con el saldo correcto y el stock reintegrado correctamente.
