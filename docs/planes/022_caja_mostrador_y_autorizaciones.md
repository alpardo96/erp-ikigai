# Plan 022: Circuito de Mostrador: Autorización de Descuentos y Caja

El objetivo es emular y modernizar la operativa de dos pasos que actualmente tienes en Visual FoxPro:
1. **Puesto de Venta**: El vendedor crea una *Preventa*. Si otorga un descuento superior al máximo permitido por el rubro del producto, la preventa se bloquea en estado "Pendiente de Autorización".
2. **Autorización**: El supervisor ingresa al "Formulario de Autorización de Descuentos" para revisar y liberar esa preventa.
3. **Caja Mostrador**: El cajero visualiza las preventas listas (Autorizadas o sin excesos), realiza el cobro, emite el comprobante y descuenta el stock.

### Fase 1: Formulario de Autorización de Descuentos
1. Integrar un acceso directo en el menú lateral para que el Supervisor vea la Bandeja de Autorizaciones.
2. Afinar la interfaz de Autorización para que muestre el cálculo bimonetario correctamente (pesificación) y permita aprobar o rechazar preventas excedidas.

### Fase 2: Caja Mostrador
1. **Modelo de CajaSesion**: Se implementará en `tesoreria` una apertura por sucursal. En este caso puntual existe una caja en cada sucursal y los usuarios son variables. Puede haber varias aperturas y cierres en un mismo día por la rotación de cajeros.
2. **Vista de Caja Mostrador**: Una pantalla dedicada donde el cajero activo en la caja de la sucursal visualizará todas las Preventas del día cuyo estado sea `0` (Borrador sin excesos) o `2` (Autorizada).
3. **Modal de Cobro**: Al seleccionar una preventa, se abrirá un modal para registrar el cobro utilizando los medios de pago.
4. **Facturación y Descarga de Stock**: Una vez cobrado, el sistema transformará la `Preventa` en una `Venta`, generará los movimientos de `Stock` negativos e insertará el cobro en la caja de la sucursal.
