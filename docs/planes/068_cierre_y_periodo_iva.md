# Plan de Implementación: Gestión de Períodos IVA, Cierre, Reapertura y Reglas Fiscales en Compras y Ventas

Este plan detalla las modificaciones de base de datos, lógica de negocio y vistas para soportar la gestión completa de **Períodos IVA (YYYYMM)**, liquidación mensual, cierres y reaperturas fiscales, y su integración estricta en las operaciones de Compras y Ventas.

---

## 📌 Objetivos y Alcance

1. **Modelo de Base de Datos `PeriodoIva`**:
   - Crear el modelo `PeriodoIva` en `impuestos/models.py` para registrar el estado de cada período fiscal (`YYYYMM`) por empresa: `CERRADO` o `ABIERTO`, fecha y usuario de cierre/reapertura, débito fiscal, crédito fiscal y saldo resultante.

2. **Incorporación del Campo `periodo` en Tablas de Libro IVA y Comprobantes**:
   - **`LibroIvaBase`** (`contable/models.py`): Añadir `periodo = models.CharField(max_length=6, db_index=True)` heredado por `cble_libro_iva_compras` y `cble_libro_iva_ventas`.
   - **`Compra`** (`facturacion/models.py`): Normalizar `periodo` a `CharField(max_length=6, db_index=True)`.
   - **`Venta`** (`facturacion/models.py`): Normalizar `periodo` a `CharField(max_length=6, db_index=True)`.

3. **Lógica Estricta de Asignación de Períodos IVA**:
   - **Ventas**: El período predeterminado SIEMPRE es el año y mes (`YYYYMM`) de la fecha de la venta. Si el período ya fue cerrado, se rechaza/alerta la emisión en período cerrado.
   - **Compras**:
     - El período predeterminado de una compra es el `YYYYMM` de la fecha del comprobante de compra.
     - **Regla de Cierres**: Si el `YYYYMM` de la fecha de la compra ya fue cerrado (ej. factura del 22/05/2026 y los períodos 202601 a 202607 están cerrados), el sistema asigna automáticamente el **primer período vigente (no cerrado)** que sea `>= YYYYMM` (ej. `202608`).
     - **Restricción**: NUNCA se permite asignar un período anterior al `YYYYMM` de la fecha de emisión del comprobante (`periodo >= YYYYMM_fecha`).
     - **Visualización en Carga de Compras**: Mostrar en los formularios de Carga de Compras (manual, automática/OCR e IA) el selector/indicador del Período IVA asignado.

4. **Cierre y Reapertura de Períodos IVA (`/impuestos/cierre-periodo-iva/`)**:
   - Botón **"Calcular Liquidación"**: Muestra el resumen de Débito Fiscal, Crédito Fiscal y Saldo del período `YYYYMM`.
   - Botón **"Ejecutar Cierre de Período"**: Registra el período como `CERRADO` y genera el asiento contable de liquidación si corresponde.
   - Botón **"Ver Períodos Cerrados"**: Abre una vista/modal con el listado de todos los períodos cerrados de la empresa, mostrando usuario, fecha de cierre y acción de reapertura.
   - Botón **"Reabrir Período"**: Permite reabrir un período cerrado previa confirmación, registrando la reapertura en la auditoría.

---

## 🛠️ Arquitectura y Modificaciones Propuestas

### 1. Modelos y Base de Datos
- **[NEW] `impuestos/models.py`**:
  - Definición de `PeriodoIva` con campos: `empresa`, `periodo` (max_length=6), `estado` ('ABIERTO'/'CERRADO'), `fecha_cierre`, `usuario_cierre`, `debito_fiscal`, `credito_fiscal`, `saldo_resultante`, `fecha_reapertura`, `usuario_reapertura`.
- **[MODIFY] `contable/models.py`**:
  - Adición de `periodo = models.CharField(max_length=6, db_index=True)` en `LibroIvaBase`.
- **[MODIFY] `facturacion/models.py`**:
  - Ajuste del campo `periodo` en `Compra` y `Venta` a `max_length=6`.
- **[NEW MIGRATION]**: Migraciones en `impuestos`, `contable` y `facturacion`.

### 2. Servicios de Negocio (`impuestos/services.py`)
- `es_periodo_cerrado(empresa_id, periodo_yyyymm)`
- `obtener_periodo_vigente_compra(empresa_id, fecha_comprobante)`
- `calcular_liquidacion_iva(empresa_id, anio, mes)`
- `cerrar_periodo_iva(empresa_id, anio, mes, usuario)`
- `reabrir_periodo_iva(empresa_id, periodo_yyyymm, usuario)`

### 3. Actualización en Servicios de Contabilización
- **[MODIFY] `contable/services/contabilizacion.py`**:
  - Actualizar `_poblar_libro_iva_compra` para estampar `periodo` (`YYYYMM`) en `LibroIvaCompras`.
  - Crear e integrar `_poblar_libro_iva_venta` en `contabilizar_venta_individual` para estampar el registro fiscal en `LibroIvaVentas` con su correspondiente `periodo`.

### 4. Vistas e Interfaces de Usuario
- **[MODIFY] `impuestos/views.py`**:
  - Actualizar `CierrePeriodoIvaView` para manejar cálculo de liquidación, listado de períodos cerrados por HTMX/Modal y reapertura.
- **[MODIFY] `facturacion/views.py` y `templates/facturacion/compras_carga.html`**:
  - Incluir el campo `periodo` en la vista de carga de compras y calcular la sugerencia inteligente de período vigente en base a la fecha ingresada y los cierres de IVA.
- **[MODIFY] `templates/impuestos/cierre_periodo_iva.html`**:
  - Agregar botón "Ver Períodos Cerrados", tabla de liquidación, botones de Cierre y Reapertura de período.
- **[NEW] `templates/impuestos/modals/periodos_cerrados_modal.html`**: Modal HTMX con la lista de períodos cerrados y botones para reabrir.

---

## 📋 Plan de Verificación

### Pruebas Automatizadas
1. **Tests Unitarios en `impuestos/tests/test_periodo_iva.py`**:
   - Test de cálculo de período predeterminado en Ventas (siempre `YYYYMM` de la fecha).
   - Test de sugerencia de período en Compras con períodos cerrados (sugiere primer período abierto `>= YYYYMM`).
   - Test de restricción en Compras (impide asignar período anterior a la fecha de la factura).
   - Test de cierre y reapertura de Período IVA.

### Verificación Manual
1. Ingresar a **Impuestos > Cierre Periodo IVA**.
2. Simular el cierre del período `202605`.
3. Intentar cargar una compra con fecha `22/05/2026` y verificar que el sistema sugiera el período vigente `202608`.
4. Abrir la ventana de "Ver Períodos Cerrados", constatar que figura `202605` y probar la acción de "Reabrir Período".
