# Implementación de Lógica Bimonetaria en Recibos de Cobranza

Implementar el soporte completo para cobranzas bimonetarias (Pesos y Dólares) en el módulo de Tesorería, siguiendo la regla estricta de que **todos los registros contables y de caja se pesifican**, mientras que las deudas (Facturas/Ventas) mantienen sus saldos en su moneda de origen.

## Open Questions

> [!WARNING]
> Por favor, aclara los siguientes puntos de diseño antes de que comience a programar:

1. **Tabla MovimientoCaja:** Mencionaste *"en la caja registro en el campo dolares pesificado y por supuesto la cotizacion utilizada"*. Actualmente la tabla `MovimientoCaja` solo tiene un campo `importe` general. ¿Deseas que agregue las columnas `importe_dolares` (para guardar la cantidad de billetes físicos en USD ingresados) y `cotizacion` a la tabla `MovimientoCaja`?
2. **Total del Recibo:** Si un cliente tiene tanto facturas en Dólares como en Pesos y decide pagar ambas en un solo recibo, ¿la interfaz del Recibo debe sumar y mostrar el "Total del Recibo" unificado en Pesos (pesificando al vuelo las facturas en USD para el cálculo de cuánto debe ingresar el cajero)?
3. **Ingreso de Cotización:** ¿El valor de la cotización para el recibo se tomará siempre e inflexiblemente de la tabla `CotizacionMoneda` (dolar_cobranza) en el backend, o deseas que el cajero pueda ver y modificar opcionalmente la cotización en la pantalla al emitir el recibo?

## Proposed Changes

---

### Modelos de Tesorería (`tesoreria/models.py`)

Se adaptarán los modelos para guardar el historial bimonetario.

#### [MODIFY] `tesoreria/models.py`
- En `MovimientoCaja`, agregar los campos:
  - `importe_dolares = models.DecimalField(...)` (Para registrar la cantidad física de billetes USD ingresados, si el medio de pago es USD).
  - `cotizacion = models.DecimalField(...)` (La cotización utilizada en el momento exacto del cobro).

---

### Vistas y Lógica de Negocio (`tesoreria/views_htmx.py`)

Se implementará el núcleo de conversión monetaria.

#### [MODIFY] `tesoreria/views_htmx.py`
- En `obtener_comprobantes_pendientes`:
  - Leer la `CotizacionMoneda` vigente (`dolar_cobranza`) y pasarla en el contexto al template para que la vista pueda pesificar al vuelo.
- En `procesar_recibo`:
  - **Conversión de Cobro en Dólares:** Si la lista de `valores` incluye un pago físico en dólares, multiplicar por la cotización para registrar su equivalente en Pesos en el `MovimientoCaja.importe` y en el `AsientoContable`. El valor original en USD se guardará en `importe_dolares`.
  - **Aplicación a Facturas (Venta):**
    - Si la factura original es en `DOL`: y se está aplicando un monto cobrado (que siempre fluye en Pesos dentro del backend), dividir ese monto en Pesos por la cotización para saber cuántos Dólares descontar del `Venta.saldo`.
    - Si la factura original es en `PES`: aplicar directamente el monto en Pesos al saldo.

---

### Interfaz de Usuario (`templates/tesoreria/`)

Se ajustará la tabla de facturas pendientes para mostrar ambas monedas.

#### [MODIFY] `templates/tesoreria/partials/comprobantes_pendientes_venta.html`
- Si `comprobante.moneda == 'DOL'`, mostrar en la columna de Saldo el valor en Dólares (ej. `USD 100.00`) y debajo su equivalente pesificado (`(ARS 142,000.00)`), utilizando la cotización enviada por la vista.
- Modificar el campo `input` donde el cajero decide cuánto aplicar a la factura, asegurándose de que la interfaz maneje claramente si el cajero está escribiendo el monto a aplicar en USD o en ARS para evitar confusiones.

#### [MODIFY] `templates/tesoreria/recibo_carga.html`
- Mostrar visualmente en la cabecera de la pantalla la "Cotización Vigente" para darle previsibilidad al cajero.

## Verification Plan

### Manual Verification
1. Ingresar a "Emitir Recibo" para un cliente que tenga facturas en PES y en DOL.
2. Verificar que la grilla muestre la factura en DOL con su saldo en dólares y la traducción al vuelo en Pesos.
3. Imputar un cobro combinando medios de pago (ej. Efectivo Pesos y Efectivo Dólares).
4. Completar el recibo y verificar la base de datos:
   - Que `MovimientoCaja` haya registrado `importe` en Pesos.
   - Que `Venta.saldo` en USD haya bajado correctamente la porción exacta de dólares.
   - Que el `AsientoContable` haya balanceado todo en Pesos.
