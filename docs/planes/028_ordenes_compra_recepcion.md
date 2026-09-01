# Plan 028 — Órdenes de Compra, Recepción (Informe de Recepción) y Circuito Interno de Stock

> **Estado:** ✅ Completado y verificado (2026-07-09). Fases 0–8 implementadas y testeadas.
> **Alcance:** Circuito de abastecimiento completo *aguas arriba* de la Factura de Compra ya existente (Plan 026):
> Orden de Compra → Informe de Recepción (remito proveedor) → cotejo en Factura, más el circuito
> interno de transferencias entre sucursales (Remito Interno + Informe de Recepción).
> **Memorias asociadas:** `compras-modulo-spec`, `compras-op-asignacion-circuito` (a extender al cerrar).

---

## 1. Objetivo

Formalizar el proceso de compras de mercaderías con documentos prenumerados por el sistema y
trazabilidad de tres vías (Orden de Compra ↔ Recepción ↔ Factura), soportando:

- **Orden de Compra (OC)** opcional según parámetro de la empresa; documento prenumerado
  (punto = sucursal, número correlativo del sistema).
- **Informe de Recepción** que vincula 1..N OC, recibe *totalizado por código* con posibilidad de
  **recepción parcial**, actualiza stock e imprime para el legajo.
- **Factura de compra** que detecta OC pendientes del proveedor, cotea cantidades pedidas /
  recepcionadas / facturadas y precios, alerta diferencias, y —cuando no hubo remito previo— genera
  el Informe de Recepción en el acto y actualiza stock.
- **Circuito interno**: una sucursal (p. ej. Depósito Central) envía mercadería a otra con un
  **Remito Interno** (salida de stock); la sucursal destino hace su **Informe de Recepción**
  (entrada de stock). Simétrico para devoluciones. Transferencia en 2 pasos, sin asiento contable.

## 2. Decisiones de diseño congeladas (acordadas con el usuario)

1. **Modelos nuevos dedicados** (no se reutiliza `Compra`): `OrdenCompra/OrdenCompraItem`,
   `Recepcion/RecepcionItem`, `RemitoInterno/RemitoInternoItem`, más tablas de imputación por línea.
   `Compra` (factura, Plan 026) queda intacta.
2. **⚠️ REVISADO (2026-07-09): el circuito de facturación/remito actual NO se toca.**
   Decisión original (descartar `tipo='Remito'` + `id_fac_rem` + `importar_remito_items` +
   `buscador_remitos_modal`) **anulada por el usuario**: si la empresa NO usa órdenes de compra,
   el circuito existente ya es completo y debe quedar intacto. El circuito nuevo (OC → Recepción →
   Factura) **convive** en paralelo y se habilita solo cuando `Empresa.usa_orden_compra = True`.
   La Fase 3 pasa a ser **puramente aditiva** (no elimina nada del flujo viejo).
3. **Numeración correlativa por `(empresa, punto, tipo_documento)`** con `tipo_documento ∈
   {ORDEN_COMPRA, INFORME_RECEPCION, REMITO_INTERNO}`. Contador transaccional
   (`select_for_update`) + `unique_together(empresa, punto, numero)` por modelo. El número se asigna
   **al confirmar** (no en borrador), para no dejar huecos.
4. **`punto` = sucursal**: se agrega `Sucursal.punto` (Integer). El punto de cada documento sale de
   la sucursal que lo emite (OC = sucursal de la OC; Remito Interno = origen; Informe = destino).
5. **Rastreo de pendientes por línea de OC** con imputación automática (FIFO) entre las OC
   seleccionadas. Acumuladores cacheados `cantidad_recibida` / `cantidad_facturada` por línea.
6. **Diferencias OC vs real** (facturado = recepcionado ≠ OC): el sistema marca la diferencia y pide
   confirmar el **ajuste de la OC** a la cantidad real (auditado). Si no se autoriza, la OC queda
   marcada `CON_DIFERENCIA`. Se conserva `cantidad_original` además de la vigente.
7. **Baja de documentos con numeración del sistema = anulación lógica** (estado `ANULADO`, conserva
   el número, revierte stock/imputaciones y reabre pendientes). La **factura de compra** mantiene su
   baja física (número del proveedor, Plan 026).
8. **Desafectación**: quitar el vínculo Factura↔OC (revierte imputación, reabre pendiente) **sin**
   borrar la factura. Permite el circuito NC-anula + nueva factura corregida.
9. **Recepción unificada**: un solo modelo `Recepcion` con `origen ∈ {PROVEEDOR_REMITO,
   PROVEEDOR_FACTURA, INTERNO}`.
10. **Circuito interno en 2 pasos, sin asiento**: emitir Remito Interno = SALIDA en origen (queda
    "en tránsito"); Informe de Recepción = ENTRADA en destino. No toca el mayor ni el costo del
    producto.
11. **Verificación de integridad**: comando de gestión + vista que detecta saltos/faltantes/
    duplicados en la serie por `(empresa, punto, tipo_documento)`.
12. **Parámetro** `Empresa.usa_orden_compra` (Boolean). **Medio de pago** = FK `MedioPago` opcional +
    `condiciones_pago` texto libre (medios/plazos informativos). **Sin unidad de medida** (no existe
    hoy; mejora futura).

## 3. Ubicación de los cambios (apps)

- **`empresas`**: `Empresa.usa_orden_compra`, `Sucursal.punto`, forms y modales de configuración.
- **`core`**: `ContadorDocumento` + servicio `siguiente_numero()` (infra reutilizable).
- **`facturacion`**: modelos de dominio nuevos, vistas/URLs/templates, señales de stock, servicios
  de imputación, ajuste de la carga de factura, baja del circuito viejo.
- **`productos`**: fix `MovimientoStock.cantidad` (Integer→Decimal); definición sobre `Producto.stock`
  plano (sincronizar vs deprecar).

## 4. Estado actual del código (puntos de anclaje verificados)

- `facturacion/models.py`: `Compra` (L167) y `CompraItem` (L275) completos (Plan 026). `Compra.id_fac_rem`
  (L205) y remito legacy a eliminar. `Movimiento` (L560) con choices `Remito`/`R.Interno`.
- `facturacion/views_htmx.py`: `importar_remito_items` (L577), `buscador_remitos_modal` (L628) → eliminar.
  Patrón de ítems en sesión (`agregar/editar/quitar_item_sesion`) a reutilizar para OC/Recepción.
- `facturacion/signals.py` (L162-189): señales `CompraItem`/`VentaItem` → `stock_service`.
- `productos/services/stock_service.py`: `aplicar_movimiento_stock(item, signo, sucursal, es_borrado)`;
  hoy saltea el movimiento si `id_fac_rem` (L29-32) → se reemplaza por "tiene recepción vinculada/generada".
- `productos/models.py`: `StockSucursal` (L150, fuente real por sucursal), `MovimientoStock` (L209,
  `cantidad` Integer = bug), `Producto.stock` plano (L96) no sincronizado.
- `empresas/models.py`: `Empresa` (L4), `Sucursal` (L33, sin `punto`). `empresas/forms.py`: `EmpresaForm`,
  `SucursalForm`.
- `core/models.py`: solo `AuditModel` (abstracto); `core/migrations` vacío.
- `config/urls.py`: rutas de compras (`# ── COMPRAS ──` L92). No hay `urls.py` por app.

---

## 5. Modelo de datos nuevo (resumen)

### Numeración (`core`)
- **`ContadorDocumento`**: `empresa` FK, `punto` Int, `tipo_documento` (choices), `ultimo_numero` BigInt.
  `unique_together(empresa, punto, tipo_documento)`. Servicio `siguiente_numero(empresa, punto, tipo)`:
  `get_or_create` + `select_for_update()` dentro de `transaction.atomic()`, incrementa y devuelve.

### Orden de Compra (`facturacion`)
- **`OrdenCompra`**: `empresa`, `sucursal`, `punto`, `numero`, `fecha`, `proveedor` FK `ClienteProveedor`,
  `carga_costos` Bool, `medio_pago` FK `tesoreria.MedioPago` null, `condiciones_pago` Text,
  `usuario` FK, `moneda`/`cotizacion`, `observaciones`, `estado` (BORRADOR/CONFIRMADA/CERRADA/ANULADA),
  `estado_recepcion` y `estado_facturacion` (PENDIENTE/PARCIAL/COMPLETA/CON_DIFERENCIA).
  `unique_together(empresa, punto, numero)`.
- **`OrdenCompraItem`**: `orden`, `producto`, `cantidad` (vigente), `cantidad_original` (snapshot),
  `precio_unitario`, `iva_alicuota`, `cantidad_recibida` (cache), `cantidad_facturada` (cache).
  Propiedades `pendiente_recepcion`, `pendiente_facturacion`, `tiene_diferencia`.

### Recepción / Informe de Recepción (`facturacion`)
- **`Recepcion`**: `empresa`, `sucursal` (destino), `punto`, `numero`, `fecha`, `proveedor` null,
  `usuario`, `origen` (PROVEEDOR_REMITO/PROVEEDOR_FACTURA/INTERNO), `remito_proveedor` Char,
  `generada_por_factura` FK `Compra` null, `remito_interno` FK `RemitoInterno` null, `observaciones`,
  `estado` (ACTIVA/ANULADA).
- **`RecepcionItem`**: `recepcion`, `producto`, `cantidad_recibida`.
- **`RecepcionImputacion`**: `recepcion_item`, `orden_item` FK null, `remito_interno_item` FK null,
  `cantidad`. (Exactamente uno de los dos orígenes seteado.) Acumula el cache de la línea de origen.

### Remito Interno (`facturacion`)
- **`RemitoInterno`**: `empresa`, `sucursal_origen`, `sucursal_destino`, `punto` (=origen), `numero`,
  `fecha`, `usuario`, `tipo` (ENVIO/DEVOLUCION), `observaciones`, `estado` (EMITIDO/REC_PARCIAL/
  RECEPCIONADO/ANULADO). `unique_together(empresa, punto, numero)`.
- **`RemitoInternoItem`**: `remito`, `producto`, `cantidad_enviada`, `cantidad_recibida` (cache).
  Propiedad `pendiente` (= en tránsito).

### Imputación Factura ↔ OC (`facturacion`)
- **`CompraOCImputacion`**: `compra_item` FK, `orden_item` FK, `cantidad`. Acumula
  `OrdenCompraItem.cantidad_facturada` (negativo para NC, que ya guardan ítems en negativo).

---

## 6. Fases de ejecución

### FASE 0 — Cimientos (parámetro + punto + numerador)
1. `empresas/models.py`: `Empresa.usa_orden_compra = BooleanField(default=False)`;
   `Sucursal.punto = IntegerField(default=1)`. Migración.
2. `empresas/forms.py`: agregar `usa_orden_compra` a `EmpresaForm`; `punto` a `SucursalForm`. Widgets.
3. Templates de configuración de Empresa/Sucursal: exponer los campos.
4. `core/models.py`: `ContadorDocumento`. `core/services/numeracion.py`: `siguiente_numero(...)`.
   Migración `core 0001`.
5. Registrar en `admin.py` para inspección.
- **Verificación:** alta concurrente (shell, 2 hilos simulados) no duplica número; `usa_orden_compra`
  y `punto` persisten y se editan desde la UI.

### FASE 1 — Modelos Orden de Compra
- Modelos + migración + admin. Sin UI todavía.
- **Verificación:** alta por shell; `pendiente_*` y `tiene_diferencia` correctos; `unique_together` frena
  número duplicado.

### FASE 2 — UI Orden de Compra (HTMX)
- Card en `compras_index.html`. Carga: proveedor por lupa (readonly, como factura), productos por
  Typeahead + Código Prov + Lupa, ítems en sesión (key propia), optiongroup `carga_costos`.
  Confirmar → `siguiente_numero()` asigna punto/número, estado CONFIRMADA.
- Listado con filtros (estado, proveedor); impresión PDF (patrón `services/reportes_pdf.py`);
  cierre/anulación lógica.
- **Verificación:** carga end-to-end en navegador; número correlativo por sucursal; impresión OK.

### FASE 3 — Modelos Recepción + imputación + señales de stock (proveedor) — **ADITIVA**
- `Recepcion/RecepcionItem/RecepcionImputacion` + migración + admin.
- Señal `RecepcionItem` post_save/post_delete → `stock_service.aplicar_movimiento_stock` (ENTRADA en
  `recepcion.sucursal`).
- Ampliar (NO reemplazar) el chequeo de la señal `CompraItem`: además del `id_fac_rem` legacy
  (circuito viejo, que se mantiene), saltear stock también si la compra tiene recepción vinculada/
  generada (circuito nuevo). Aditivo: no cambia el comportamiento del flujo viejo.
- **NO se elimina nada del circuito de factura/remito actual** (`tipo='Remito'`, `id_fac_rem`,
  `importar_remito_items`, `buscador_remitos_modal`, `buscador_remitos.html` quedan intactos). Los
  dos circuitos conviven; el nuevo se habilita con `Empresa.usa_orden_compra=True`.
- **Verificación:** recepción nueva mueve stock en la sucursal correcta; el flujo viejo
  (remito→factura por `id_fac_rem`) sigue funcionando sin cambios (regresión).

### FASE 4 — UI Recepción de proveedor
- Carga con selector de **sucursal (destino)** que define punto/número. Botón "Vincular OC" → modal
  Typeahead+Lupa de OC **pendientes de recepción** del proveedor → ítems totalizados por código con
  columna **cantidad recibida** editable (default = pendiente) y pendiente resultante. Guardar →
  imputa FIFO, mueve stock, recalcula estados de OC, imprime.
- **Verificación:** recepción parcial en 2 tandas reduce el pendiente correctamente; impresión OK.

### FASE 5 — Integración en la Factura de compra
- Al seleccionar proveedor: HX-Trigger consulta OC pendientes de facturar → aviso + modal de selección.
- Grilla de cotejo por código: cant. OC / recepcionada / **facturada (editable)** / **precio
  facturado (editable)**; **rojo** si facturado > recepcionado (pendiente de recepción).
- Detección facturado = recepcionado ≠ OC → modal "Ajustar OC a real / Dejar con diferencia"
  (auditado, conserva `cantidad_original`).
- Guardar → `CompraOCImputacion` acumula `cantidad_facturada`, recalcula estados. Si no hubo remito →
  genera `Recepcion(origen=PROVEEDOR_FACTURA)` (mueve stock). Si hubo remito → no genera ni mueve.
- **Verificación:** factura sin remito genera Informe + stock; factura con remito no toca stock;
  ajuste de OC actualiza cantidad vigente y conserva original.

### FASE 6 — Circuito interno de stock
- `RemitoInterno/RemitoInternoItem` + migración + admin.
- Señal `RemitoInternoItem` → SALIDA en `sucursal_origen` (emisión). `Recepcion.origen=INTERNO`
  imputa a `RemitoInternoItem` y hace ENTRADA en destino (misma señal de recepción).
- UI: carga de Remito Interno (origen = sucursal actual, destino selector, productos typeahead),
  recepción interna (vincular remito interno pendiente al destino), impresión, "stock en tránsito"
  (derivado de `RemitoInternoItem.pendiente`).
- **Verificación:** transferencia 2 pasos (origen baja al emitir, destino sube al recepcionar);
  devolución simétrica; sin asiento.

### FASE 7 — Bajas, desafectación y legajo
- Anulación lógica de OC/Recepción/Remito Interno (revierte stock/imputaciones, reabre pendientes,
  conserva número).
- Acción "Desafectar de OC" (revierte `CompraOCImputacion` sin borrar la factura).
- Vista **Legajo de OC**: todos los documentos vinculados (facturas, NC, recepciones/remitos) + estado
  consolidado; re-vinculación de NC / factura corregida / nuevo remito.
- Extender `dar_de_baja_compra` (Plan 026) para revertir imputaciones y borrar la recepción
  autogenerada.
- **Verificación:** NC anula + nueva factura corregida cierra el legajo; desafectar reabre pendiente.

### FASE 8 — Integridad, pruebas y documentación
- Comando `verificar_correlativos` + vista de auditoría (saltos/faltantes/duplicados por empresa/punto/tipo).
- Fix colateral `MovimientoStock.cantidad` → `DecimalField(15,2)`; decisión sobre `Producto.stock`.
- Tests (ver §7). Actualizar `docs/walkthrough.txt` (incremental) y `docs/GUIA_MODULAR.md`.

---

## 7. Plan de pruebas (automatizadas + manuales)

- **Numerador concurrente:** dos asignaciones simultáneas no duplican ni saltan número.
- **Recepción parcial:** recibir en 2 tandas contra una OC deja el pendiente exacto por línea.
- **Factura sin remito:** genera `Recepcion(PROVEEDOR_FACTURA)` y mueve stock una sola vez.
- **Factura con remito:** no genera Informe ni mueve stock (evita doble conteo).
- **Diferencia OC:** facturado = recepcionado ≠ OC → ajuste autorizado (cantidad vigente = real,
  `cantidad_original` intacta) vs no autorizado (OC `CON_DIFERENCIA`, pendiente vivo).
- **Transferencia interna:** SALIDA al emitir, ENTRADA al recepcionar; devolución simétrica; sin asiento.
- **Anulación lógica:** conserva número, revierte stock/imputaciones, reabre pendientes.
- **Desafectación:** revierte imputación factura↔OC sin borrar la factura.
- **Integridad:** `verificar_correlativos` detecta un hueco/duplicado insertado a mano.
- **Manual (navegador):** carga OC, recepción, factura con cotejo (rojo/diferencias), remito interno.

## 8. Riesgos / pendientes

- **Producto.stock plano** no sincronizado con `StockSucursal` (decidir en Fase 8).
- **Unidad de medida** inexistente (mejora futura; hoy cantidades decimales sin UdM).
- **Moneda extranjera** en OC: se guarda moneda/cotización; el impacto en costos ya lo maneja la
  factura (Plan 026); la OC es referencial.
- **Circuito Órdenes de Pago** (Plan 026 §10) sigue pendiente e independiente de este plan.
