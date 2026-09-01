# Plan de Implementación: Cotizaciones Bimonetarias (Pesos / Dólares)

El objetivo de este plan es adaptar el sistema para soportar productos con precios de lista en Dólares (DOL), que al momento de facturarse (Ventas/Preventas) o cobrarse se pesifiquen utilizando una cotización administrada de forma centralizada por usuarios autorizados.

## User Review Required

> [!IMPORTANT]
> **Modelo de Cotizaciones Centralizadas:**
> Voy a crear un panel de control exclusivo para usuarios autorizados donde podrán definir la "Cotización Venta" y la "Cotización Cobranza" vigentes. 
> Cuando un vendedor cargue un producto en Dólares, el sistema leerá la *Cotización Venta* vigente en ese momento, pesificará el precio y guardará en el renglón de la factura el precio pesificado, indicando que el origen fue "DOL" y la cotización que se utilizó ese día.
> ¿Estás de acuerdo con este enfoque?

## Open Questions

> [!WARNING]
> 1. **Módulo de Compras:** Me indicaste esto para los ítems "facturados" (Ventas/Preventas). ¿El módulo de Compras también deberá pesificar productos en dólares usando una "Cotización Compra", o por ahora esto es exclusivo para Ventas y Cobranzas?
> 2. **Cobranzas (Tesorería):** Mencionaste "una cotización para cobranzas". Entiendo que esto impactará en el módulo de Tesorería, de modo que si un cliente nos entrega un billete de 100 USD (Medio de Pago: Dólares), el recibo sumará en pesos usando esa cotización específica de cobranza. ¿Es correcto?

## Proposed Changes

### Módulo `facturacion` y `empresas` (models.py)

#### [NEW] empresas/models.py (o nueva tabla de Configuración)
- Crear el modelo `CotizacionMoneda` (campos: `empresa`, `dolar_venta`, `dolar_cobranza`, `modificado_por`, `fecha_actualizacion`).
- Asegurar que haya un solo registro activo por empresa (o un histórico).

#### [MODIFY] usuarios/models.py
- Agregar el permiso booleano `permiso_cotizaciones_editar` en el perfil del usuario.

#### [MODIFY] facturacion/models.py
- En `VentaItem` y `PreventaItem`: Agregar campos `moneda_origen` (Char, max=3, default='PES'), `cotizacion_aplicada` (Decimal, default=1.0) y `precio_origen` (Decimal, el valor en dólares antes de pesificar). Los campos `precio_unitario` y `total` seguirán guardando estrictamente PESOS.

### Flujo de Vistas (HTMX) y UI

#### [NEW] Pantalla de Configuración de Cotizaciones
- Crear una vista HTMX/Modal accesible solo por usuarios con el permiso habilitado, donde podrán actualizar rápidamente los valores de `dolar_venta` y `dolar_cobranza`.
- Integrarlo en el menú superior o en un panel de administración.

#### [MODIFY] facturacion/views_htmx.py (Carga de ítems)
- En las funciones `agregar_item_venta_sesion` y `preventas_item_add`:
  - Obtener la cotización vigente para Venta.
  - Si el `producto.moneda == 'DOL'`, calcular `precio_unitario_pesos = producto.precio_total * dolar_venta`.
  - Guardar el ítem en la tabla de la base de datos (o sesión) con los campos pesificados para que todos los cálculos de IVA, subtotales y totales generales de la factura sigan funcionando sin alteraciones, pero con el registro de la cotización aplicada.

## Verification Plan
1. **Configuración:** Ingresar con usuario administrador y definir Dólar Venta = $1200 y Dólar Cobranza = $1100.
2. **Preventa/Venta:** Cargar un producto que está en Dólares (ej. precio de lista = 100 DOL). El renglón deberá mostrarse en Pesos ($120.000) de forma automática.
3. **Auditoría:** Verificar en la base de datos que el `PreventaItem` guardó `precio_unitario=120000`, `moneda_origen='DOL'` y `cotizacion_aplicada=1200`.
