# Plan 002 — Automatización de Stock y Totales

## Estado: ✅ Completado (Fase 4 del walkthrough)

## Descripción del Objetivo
Este plan aborda los puntos críticos 1.3 y 1.4 del `PLAN_MEJORAS.md`. El objetivo es garantizar la consistencia absoluta en el cálculo del inventario (stock) y en los importes totales (cabecera) de las Compras y Ventas. 
Adicionalmente se consolida el modelo `Movimiento` como una **vista materializada (read-only)** mantenida a través de señales (Punto 1.2).

## Decisiones de Diseño Acordadas
1. **Modelo Movimiento (Punto 1.2)**: Se mantendrá la estructura actual y los campos redundantes, ya que hay flujos de Facturación Electrónica ARCA (`FacturacionARCA.exe`) que podrían requerirlo. Su actualización quedará encapsulada y automatizada a través de señales `post_save` / `post_delete` en Compras y Ventas.
2. **Stock Negativo**: No se bloqueará la base de datos (Database Constraint) al vender con stock negativo, pero se emitirán advertencias lógicas desde los servicios a las futuras vistas de frontend.

## Cambios a Realizar

### Módulo Productos (`productos`)
- **`productos/services/stock_service.py`**:
  Implementar `@transaction.atomic def aplicar_movimiento(item, signo, sucursal=None)` que actualice `StockSucursal` y lleve trazabilidad en `MovimientoStock`. Para actualizaciones de ítems (edición), se calculará el `delta` de cantidad comparado con el valor anterior.

### Módulo Facturación (`facturacion`)
- **`facturacion/models.py`**:
  Crear los métodos `recalcular_totales()` en `Compra` y `Venta` para que la cabecera autocalcule los campos `neto`, `iva`, `total`, etc. a partir de la suma matemática de sus ítems asociados.
- **`facturacion/signals.py`**:
  - `post_save` y `post_delete` en `CompraItem` y `VentaItem` para actualizar stock y disparar `recalcular_totales()`.
  - `post_save` en `Compra` y `Venta` para mantener actualizado el modelo histórico `Movimiento`.

## Verificación (Tests)
- `productos/tests/test_stock.py`: Pruebas del ciclo de vida del ítem (creación, edición, borrado) y su reflejo en `StockSucursal`.
- `facturacion/tests/test_totales.py`: Test unitario validando sumatorias e impuestos.
