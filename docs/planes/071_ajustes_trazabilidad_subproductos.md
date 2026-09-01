# Plan 071: Ajustes en Trazabilidad de Subproductos (/stock/trazabilidad/)

Este plan de implementación responde a las tres necesidades planteadas sobre el módulo de **Trazabilidad de Subproductos**:
1. Ampliación del historial de trazabilidad por **Serie y CUIM** (multiciclo) y apertura de modal de detalle de compra (`compra_id`) y venta (`id_vta > 0`).
2. Botón y modal de **Edición exclusiva de SERIE y CUIM** para corregir errores de carga antes de facturar.
3. Análisis y corrección de la **Anulación de Operaciones (Notas de Crédito)** para revertir automáticamente la situación del subproducto de `'VENDIDA'` a `'DEPOSITO'` y limpiar la vinculación con la venta.

---

## Análisis del Código Actual y Hallazgos

1. **Consulta del Historial por Serie y CUIM:**
   - En `productos/views_trazabilidad.py` (`trazabilidad_modal_timeline`), la vista busca la trazabilidad únicamente filtrando por `serie`.
   - Se debe ampliar el filtro para buscar todos los registros de la tabla `Subproducto` asociados a esa `serie` o `cuim` en la empresa (soportando reingresos y múltiples ciclos de compra-venta de una misma unidad).

2. **Detalles Completos de Compra y Venta:**
   - Actualmente el timeline muestra información resumida. Se requiere que al hacer click en cualquier registro del historial, se abra un modal específico de detalles que consulte:
     - **Compra (`compra_id`):** Fecha (`feccpra`), Proveedor (`compra.proveedor.razon_social`), Comprobante (`tipo-punto-numero`), Costo Adquisición (`cto_adq`), Moneda (`moneda`), Cotización (`cotizadq`).
     - **Venta (`id_vta > 0`):** Si tiene una venta vinculada, consultar Fecha de Venta (`fecvta`), Cliente (`venta.cliente.razon_social`), Comprobante de venta (`tipo-punto-numero`), Precio Neto (`precio_neto`), Precio Total (`precio_total`).

3. **Edición Exclusiva de SERIE y CUIM:**
   - No existía un endpoint de modificación directa de trazabilidad. Se habilitará un modal de edición en el que los **únicos campos editables** serán `SERIE` y `CUIM`.
   - Al guardar, se actualizarán dichos campos en el objeto `Subproducto` permitiendo corregir errores tipográficos sin alterar los montos ni las facturas históricas.

4. **Análisis de Anulación / Nota de Crédito (Reversión a DEPOSITO):**
   - **Resultado del Análisis:** Al examinar `facturacion/services/notas_credito.py` (`emitir_nota_credito_desde_venta`), se constató que al emitir una Nota de Crédito por devolución de un ítem de venta, el sistema restaba cantidades y generaba el comprobante fiscal, **pero NO estaba actualizando los registros de la tabla `Subproducto`**.
   - Por ende, el subproducto quedaba erróneamente con `situacion = 'VENDIDA'` y vinculado al `id_vta` anterior.
   - **Solución a implementar:** En la emisión de la Nota de Crédito (y/o anulación de la venta), para cada producto devuelto con trazabilidad activa (`producto.subprod == True`), se buscarán los subproductos con `venta = venta_original` y se revertirán:
     - `situacion = 'DEPOSITO'`
     - `venta = None` (`id_vta = NULL`)
     - `fecvta = None`
     - `precio_neto = Decimal('0.00')`
     - `precio_total = Decimal('0.00')`
     - `cotizvta = Decimal('1.0000')`
     - `fecent = None`

---

## Cambios Propuestos

### Componente: Módulo de Productos (Trazabilidad)

#### [MODIFY] [productos/views_trazabilidad.py](file:///d:/JM_Soft/erp-ikigai-2/productos/views_trazabilidad.py)
- **`trazabilidad_modal_timeline(request, serie)`**:
  - Ampliar para aceptar búsqueda por `serie` o por `subpro_id`/`cuim`. Obtener todos los subproductos de la empresa que coincidan con la serie o el cuim.
- **`subproducto_detalle_modal(request, subpro_id)` [NUEVO]**:
  - Vista HTMX para renderizar el modal con los detalles de compra (`compra_id`) y venta (`id_vta > 0`).
- **`subproducto_editar_modal(request, subpro_id)` [NUEVO]**:
  - Vista GET para cargar el modal de edición de `serie` y `cuim`.
  - Vista POST para guardar únicamente `serie` y `cuim` del subproducto, validando que no quede vacía la serie.

#### [NEW] [templates/productos/partials/subproducto_detalle_modal.html](file:///d:/JM_Soft/erp-ikigai-2/templates/productos/partials/subproducto_detalle_modal.html)
- Plantilla HTMX con diseño estructurado y moderno que muestra:
  - Tarjeta de Datos de Compra (Fecha, Proveedor, Tipo/Punto/Número, Costo Adq, Moneda, Cotiz Adq).
  - Tarjeta de Datos de Venta (si `id_vta > 0`): Fecha Venta, Cliente, Tipo/Punto/Número, Precio Neto, Precio Total.

#### [NEW] [templates/productos/partials/subproducto_editar_modal.html](file:///d:/JM_Soft/erp-ikigai-2/templates/productos/partials/subproducto_editar_modal.html)
- Formulario modal HTMX con inputs únicamente para `SERIE` y `CUIM`.
- Botón Guardar que hace POST via HTMX y actualiza el valor reflejado en la grilla y modales.

#### [MODIFY] [templates/productos/partials/trazabilidad_grilla.html](file:///d:/JM_Soft/erp-ikigai-2/templates/productos/partials/trazabilidad_grilla.html)
- Añadir el botón/icono de "Editar" (SERIE y CUIM) directamente en cada fila de la grilla principal de trazabilidad.

#### [MODIFY] [templates/productos/partials/trazabilidad_modal_timeline.html](file:///d:/JM_Soft/erp-ikigai-2/templates/productos/partials/trazabilidad_modal_timeline.html)
- Permitir hacer click en cualquiera de los registros del timeline o grilla para abrir el modal de detalles (`subproducto_detalle_modal`).
- Añadir botón de "Editar Serie/CUIM".

---

### Componente: Módulo de Facturación (Notas de Crédito / Reversión)

#### [MODIFY] [facturacion/services/notas_credito.py](file:///d:/JM_Soft/erp-ikigai-2/facturacion/services/notas_credito.py)
- En `emitir_nota_credito_desde_venta`, al procesar los ítems de devolución:
  - Verificar si `original_item.producto.subprod` es verdadero.
  - Buscar los subproductos asociados: `Subproducto.objects.filter(venta=venta_original, producto=original_item.producto)` (limitados a la cantidad devuelta).
  - Revertir su estado a `situacion = 'DEPOSITO'`, desvincular `venta = None` (`id_vta = null`), limpiar `fecvta = None`, `precio_neto = 0`, `precio_total = 0`, `cotizvta = 1`, `fecent = None`.

---

### Componente: Configuración de Rutas

#### [MODIFY] [config/urls.py](file:///d:/JM_Soft/erp-ikigai-2/config/urls.py)
- Registrar las URLs:
  - `path('stock/trazabilidad/subproducto/<int:subpro_id>/detalle/', subproducto_detalle_modal, name='subproducto_detalle_modal')`
  - `path('stock/trazabilidad/subproducto/<int:subpro_id>/editar/', subproducto_editar_modal, name='subproducto_editar_modal')`

---

## Plan de Verificación

### Pruebas Automatizadas / Django Test:
- Crear o actualizar tests en `facturacion/tests/` o `productos/tests/` para verificar:
  1. Que la emisión de una Nota de Crédito sobre una Venta con Subproductos cambie la situación de `'VENDIDA'` a `'DEPOSITO'` y deje `venta = None`.
  2. Que la edición de un `Subproducto` actualice solo `serie` y `cuim`.

### Verificación Manual UI:
- Ingresar a `/stock/trazabilidad/`.
- Buscar una serie o cuim y presionar "Historial".
- Probar el click en uno de los registros para abrir el modal de detalles completos (compra/venta).
- Probar la edición de SERIE y CUIM desde el modal y la grilla.
