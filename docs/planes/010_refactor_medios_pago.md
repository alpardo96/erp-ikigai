# Refactorización de Arquitectura: Movimientos de Caja y Medios de Pago

Este plan aborda la reestructuración completa de los modelos de base de datos en Tesorería para lograr una trazabilidad limpia, jerárquica y escalable de los cobros y pagos, tal como analizaste.

Tienes muchísima razón en tu observación: la estructura actual mezclaba conceptos al intentar poner `medio_pago_id` en la cabecera del `MovimientoCaja` y sobrecargar la tabla `Valor`. La nueva estructura adoptará un diseño **Cabecera-Detalle** con entidades satélites.

## Estructura Propuesta

1. **`MovimientoCaja` (Cabecera Principal)**
   - Representará un flujo de fondos global (Ej. "Cobro de Recibo", "Cierre de Caja", "Pago a Proveedor").
   - **Campos:** `sesion`, `tipo`, `concepto`, `recibo`, `orden_pago`, `venta`, `fecha` (los campos de sucursal/empresa se heredan a través de `sesion -> caja`, esto es correcto).
   - **Removidos:** `medio_pago` y `cuenta_bancaria`.

2. **`MovimientoCajaDetalle` (NUEVA TABLA - Detalle de Medios de Pago)**
   - Aquí se alojarán los distintos medios con los que se compone el movimiento global.
   - **Campos:** `movimiento_caja` (FK a MovimientoCaja), `medio_pago` (FK a MedioPago), `importe` (en ARS siempre, según política), `cotizacion` (para registrar el valor de la divisa en ese instante exacto), `importe_moneda_extranjera` (para dólares físicos).

3. **`CobroTarjeta`**
   - Vinculada al detalle específico.
   - **Campos nuevos:** `movimiento_detalle` (FK a MovimientoCajaDetalle).
   - Se mantendrán los datos del cupón y lote.

4. **`ValorTerceros` (Anteriormente `Valor`)**
   - Destinada EXCLUSIVAMENTE a Cheques de Terceros (Físicos o Echeqs).
   - **Campos nuevos:** `movimiento_detalle` (FK a MovimientoCajaDetalle).
   - **Removidos:** `importe_dolares`, `cotizacion`, `cuenta_bancaria`.

5. **`TransaccionBancaria` (NUEVA TABLA)**
   - Agrupará Transferencias, Depósitos y Cheques Propios Emitidos.
   - **Campos:** `movimiento_detalle` (FK a MovimientoCajaDetalle), `cuenta_bancaria` (FK a nuestra cuenta), `tipo` (`'TRA': Transferencia`, `'CHP': Cheque Propio`), `numero_comprobante`, `fecha_vencimiento` (para cheques propios), `cuit_titular`.

## Open Questions

> [!WARNING]
> Por favor, aclara los siguientes puntos antes de proceder:

1. **Recibos y Órdenes de Pago vs Caja:** Cuando ingresa un Recibo que se paga 100% mediante Transferencia Bancaria, ¿se generará igualmente un `MovimientoCaja` (cabecera) en la Sesión de Caja actual del operador para dejar registro de la operatoria del día, o debe saltarse la caja e ir directo a contabilidad? Asumiré que **TODO** movimiento financiero genera un `MovimientoCaja` en la sesión del cajero, y sus detalles dictarán si es efectivo, banco o cheque. ¿Es correcto?
2. **Impacto en Venta de Caja Mostrador:** En "Caja Mostrador", actualmente un cobro generaba un `MovimientoCaja` para Efectivo y un `CobroTarjeta` independiente. Ahora el cobro en mostrador generará *un solo `MovimientoCaja`* cabecera por toda la Venta, y dentro sus detalles de Efectivo y Tarjeta. ¿De acuerdo?
3. **Migración de Datos:** Esto implicará borrar las migraciones conflictivas o hacer un reset local de la base de datos (si estás en desarrollo). ¿Estás de acuerdo en que modifique los archivos de modelos y aplique los cambios estructurales, asumiendo que los datos de prueba actuales en tesorería pueden ser reseteados o migrados destructivamente?
