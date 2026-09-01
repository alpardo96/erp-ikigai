# Plan 024 — Recibos de Cobranza (Revisión VFP)

## Análisis de Retroalimentación y Equivalencias VFP vs Ikigai

Has tocado puntos críticos de la migración de la lógica de VFP al nuevo ERP. Aquí detallamos cómo se mapean tus requerimientos a la nueva arquitectura relacional:

### 1. Imputación Contable del Haber (Cuenta Patrimonial)
- **VFP:** Sugería la `cta_pat` de `cli_pro` (si `condic=1`) o `cta_res` (si `condic=2`).
- **Ikigai:** Totalmente de acuerdo. El Haber del asiento contable de cobranza utilizará la cuenta `cuenta_contable` asignada en el maestro del `ClienteProveedor` seleccionado en el Recibo, en lugar de una cuenta general por defecto.

### 2. Cliente Obligatorio
- **Ikigai:** Dado que confirmas que siempre se usará un `ClienteProveedor` (ej: "1 - Consumidor Final", o "999 - Banco X"), **NO modificaremos el modelo `Recibo`**. El campo `cliente` seguirá siendo **obligatorio**. Los "Recibos Simples" simplemente se le asignarán a un Cliente/Proveedor comodín creado para ese fin (ej. "Aportes Societarios").

### 3. Caja Diaria vs MovimientoCaja (Estructura de Datos)
- **VFP:** La tabla `aux_caja_diaria` tenía columnas desnormalizadas (`efectivo`, `banco`, `valores`, `dolares`, `tarjetas`, `retenciones`, `importe`).
- **Ikigai:** Hemos modernizado este enfoque (Normalización de Base de Datos). 
  - **`MovimientoCaja`** funciona como la cabecera operativa del movimiento dentro del turno y guarda únicamente el dinero **fungible** (Efectivo ARS y USD).
  - **`Valor`** guarda el dinero **trazable** (Transferencias, Cheques, Tarjetas, Retenciones) en filas individuales.
  - **¿Por qué?** Porque en un recibo el cliente te puede dar 3 cheques distintos. En VFP sumabas los 3 al campo `valores`, perdiendo el detalle fino a nivel de caja diaria. En Ikigai, creamos 3 filas en `Valor`.
  - **Tranquilidad para los Reportes:** Cuando diseñemos el reporte de "Caja Diaria" para imprimir, el sistema unirá `MovimientoCaja` y `Valor` para mostrarte exactamente las mismas columnas que tenías en VFP (`Efectivo: $X`, `Valores: $Y`, `Transferencias: $Z`), sin necesidad de tener esas columnas rígidas en la tabla de la base de datos.

### 4. Tratamiento de Retenciones
- **VFP:** Consultabas si usar la tabla de facturas (`ventas_enc`) o una específica.
- **Ikigai:** Utilizaremos la tabla universal **`Valor`** apoyada en el maestro **`MedioPago`**.
  - **Punto y Número:** Se guardará en el campo `numero_comprobante` de la tabla `Valor`.
  - **Tipo de Retención:** Estará definido por el `MedioPago` asociado (ej. "Retención IIBB BA", "Retención Ganancias").
  - **Fecha:** Añadiremos el campo `fecha_comprobante` a la tabla `Valor`.
  - **Importe:** Campo `importe` de la tabla `Valor`.
  - **Imputación Contable:** Se tomará de la `cuenta_contable` asignada al `MedioPago` en el maestro (la cuenta de Activo de la retención).
  - **Asiento_id:** La retención formará parte del asiento global del `Recibo`.

---

## Cambios Propuestos Definitivos

### 1. Modelos de Datos
- **Añadir a `Valor`:** `fecha_comprobante = models.DateField(null=True, blank=True)` para las fechas de los certificados de retención o cheques diferidos.
- **Crear `ReciboImputacion`:** Modelo auxiliar para cuando el usuario requiera múltiples imputaciones manuales al Haber en un "Recibo Simple" (`recibo`, `cuenta_contable`, `importe`).

### 2. Contabilización (`contabilizar_recibo`)
- **Debe (Pesos):** Iteración de `Valores` (Retenciones, Cheques, Transferencias usando la cuenta de su `MedioPago`) + Efectivo de `MovimientoCaja` (usando cuenta de Parámetros).
- **Haber (Pesos):**
  - Si es Cobranza de Facturas: Toma el total y acredita a la `cuenta_contable` del `ClienteProveedor`.
  - Si es Recibo Simple: Itera las líneas de `ReciboImputacion` y acredita a cada cuenta específica.
- **Multimoneda:** Si la cobranza es en Dólares, el sistema convierte el monto a Pesos usando la cotización del día/ingresada para sumar al Haber/Debe, pero registra `divisa='USD'` y la `cotizacion` en los campos auxiliares de `AsientoLinea`.

### 3. Interfaz de Recibo (UI)
- Sección 1: Selección de Cliente (Obligatorio).
- Sección 2: Selector visual (Switch) entre **"Aplicar a Facturas"** o **"Imputación Manual (Recibo Simple)"**.
- Sección 3: Grilla de carga de Valores (Efectivo, Dólares, Transferencias, Cheques, y Certificados de Retención).

---

> [!TIP]
> **Conclusión del Análisis:** El motor de base de datos actual de Ikigai ya tiene la potencia estructural para soportar tu visión exacta de VFP. Solo debemos añadir la tabla `ReciboImputacion` para los recibos simples y el campo `fecha_comprobante` a `Valor` para el control de retenciones.

¿Procedo con la creación de la tabla y la lógica de backend en base a este acuerdo definitivo?
