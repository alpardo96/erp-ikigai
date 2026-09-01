# Plan de Implementación: Caja Mostrador - Acciones de Cobro y Asientos Contables

Este plan detalla la incorporación de los distintos medios de pago a la Caja Mostrador y la **generación inmediata del Asiento Contable** de la factura cobrada, respetando los parámetros contables, las cuentas de los rubros y las cuentas bancarias vinculadas.

## ⚠️ User Review Required
> [!IMPORTANT]
> Se han incorporado tus indicaciones. Por favor revisa si la distribución del asiento es exactamente como la necesitas:
> - **Generación Inmediata de Asiento**: Al cobrar, se creará un registro en `Asiento` y sus `AsientoLinea`.
> - **DEBE**: 
>   - Efectivo: `ParametrosContables.cta_caja`
>   - Dólares: `ParametrosContables.cta_dolar`
>   - Tarjetas: `ParametrosContables.cta_tarjetas_a_cobrar` (Se agregará este parámetro contable).
>   - Cheques/Valores: `ParametrosContables.cta_valores_cartera`
>   - Transferencia: `CuentaBancaria.cuenta_contable` (de la cuenta elegida al cobrar).
>   - Cta Cte: `ParametrosContables.cta_clientes_default`
> - **HABER**:
>   - IVA: `ParametrosContables.cta_iva_debito`
>   - Ventas Netas: Desglosadas según la `cta_ventas` del `Rubro` de cada producto vendido. (Si un rubro no tiene cuenta, se usará `ParametrosContables.cta_ventas` por defecto).

## Proposed Changes

### 1. Modelos Contables (`contable/models.py`)
- **[MODIFY] `ParametrosContables`**:
  - Agregar el campo `cta_tarjetas_a_cobrar = models.ForeignKey(Cuenta, ...)` para poder asignarlo en el plan de cuentas.

### 2. Modelos de Facturación y Tesorería (`facturacion/models.py`, `tesoreria/models.py`)
- **[MODIFY] `facturacion.Venta`**:
  - Agregar el campo `dolares = models.DecimalField(max_digits=15, decimal_places=2, default=0)` para almacenar el monto pesificado cobrado en dólares. (Se usará junto al campo `cotizacion` ya existente).
- **[NEW] `tesoreria.CobroTarjeta`**:
  - `venta`: ForeignKey a `facturacion.Venta`
  - `asiento_id`: IntegerField (Se guardará aquí el ID del asiento generado)
  - `caja_sesion`: ForeignKey a `CajaSesion`
  - `tarjeta`: CharField (marca/nombre)
  - `lote`: CharField
  - `cupon`: CharField
  - `importe`: DecimalField
- **[MODIFY] `tesoreria.Valor`**:
  - Agregar ForeignKey `venta` a `facturacion.Venta` para relacionar cheques recibidos en ventas de mostrador.
- **[MODIFY] `tesoreria.MovimientoCaja`**:
  - Agregar ForeignKey a `CuentaBancaria` (null=True) para las transferencias.

### 3. Vistas y Endpoints (`tesoreria/urls.py` & `tesoreria/views_htmx.py`)
- **[NEW] `caja_mostrador_cobrar_modal`**: Modal HTMX con pestañas/acordeones para los medios de cobro (Efectivo, Dólares, Tarjetas, Cheques, Transferencias, Cta Cte).
- **[NEW] Lógica de Contabilización en `procesar_cobro_caja`**:
  1. Validar que la suma de cobros >= total de Preventa.
  2. Transformar Preventa en Venta.
  3. Crear los registros de tesorería (`CobroTarjeta`, `Valor`, `MovimientoCaja`).
  4. **Generar Asiento**:
     - Insertar cabecera en `Asiento` (`concepto` = Venta Mostrador, `monto` = total).
     - Generar líneas de HABER: Agrupar el neto de los ítems por Rubro y asignar a la `cta_ventas` de cada Rubro. Calcular el IVA Débito total y asignar a `cta_iva_debito`.
     - Generar líneas de DEBE: Por cada medio de pago que tenga monto > 0, usar la cuenta contable correspondiente según el parámetro / banco.
     - Asignar el `asiento.pk` al campo `asiento_id` de la `Venta` y de `CobroTarjeta`.

---

### Frontend (`templates/tesoreria/`)
- **[MODIFY] `caja_mostrador_index.html`**: Botón "Cobrar" en cada Preventa.
- **[NEW] `modal_cobrar.html`**: Interfaz con Alpine.js para calcular "Total a Cobrar", "Monto Ingresado" y "Vuelto / Faltante".

## Verification Plan
1. Configurar un `Rubro` de producto de prueba asignándole una cuenta de ventas.
2. Asegurar que `ParametrosContables` tiene las cuentas asignadas (Caja, IVA Débito, etc.).
3. Generar una Preventa y cobrarla en Caja Mostrador con múltiples medios (Efectivo y Transferencia).
4. Verificar que se cree la `Venta` con sus campos de cobranza (`efectivo`, `transferencia`) actualizados.
5. Verificar la creación exacta del `Asiento` contable, comprobando que "Debe = Haber" y que las cuentas imputadas correspondan a las reglas de negocio dictadas.
