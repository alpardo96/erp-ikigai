# Facturación por Lotes (Tarifas Estudio)

Este plan aborda la construcción del módulo de Facturación Masiva (por Lotes) a partir de las tarifas vigentes cargadas en el sistema.

## Objetivos del Plan
1. Crear una interfaz visual (HTMX/AlpineJS) para seleccionar qué registros facturar.
2. Permitir la selección del **Período a facturar** (Ej. 202607) y el **Punto de Venta Fiscal** si aplica.
3. Prevenir la doble facturación de un mismo cliente/producto en el mismo período.
4. Conexión con AFIP (simulada para pruebas iniciales) para obtener CAE para comprobantes fiscales (`tarifa_f > 0`). La `tarifa_f` es el valor neto; el IVA se calculará en base al `alic_iva` del producto.
5. Generación de comprobantes internos (No Fiscales) para `tarifa_p > 0`. El asiento contable será Debe: `cta_pat` del cliente y Haber: `cuenta_id` del producto/tarifa (sin cálculo de IVA).
6. Trazabilidad contable total: Registros en Tablas de Ventas, Libros IVA (solo para los comprobantes fiscales), Asientos Contables, y Movimientos de Stock (servicios).

## Aclaraciones del Usuario (Feedback)
- **Asiento Comprobante Interno (tarifa_p):** Debe `clienteproveedor.cta_pat` y Haber `tarifaestudio.cuenta_id`. Sin cálculo de IVA.
- **Cálculo de IVA (tarifa_f):** El valor de `tarifa_f` es el valor neto. El IVA se calculará sobre esta base según la alícuota del producto (`productos_producto.alic_iva`).
- **Libros de IVA:** Solo se registran los comprobantes fiscales.
- **Pruebas (MODO TEST):** Toda la lógica se probará inicialmente *sin* impactar formalmente a ARCA, para verificar la correcta registración en la base de datos de manera segura.

## Detalles Técnicos
- **Vista Django:** `facturacion_lotes_view`
- **Template:** `facturacion/templates/facturacion/estudio/facturacion_lotes.html`
- **Servicio Backend:** `facturacion/services/facturacion_lote_service.py` con `transaction.atomic()`.

## Tareas a Realizar
1. Crear el HTML/Frontend para la visualización y selección de registros.
2. Crear la vista de Django para el renderizado inicial y el endpoint AJAX de generación.
3. Escribir el script del servicio (`facturacion_lote_service.py`) con simulación de AFIP.
4. Conectar el frontend con el backend.
5. Pruebas y validaciones.
