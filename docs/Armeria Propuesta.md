# Propuesta y Seguimiento de Tareas - Módulo Armería & General

## Clientes / Proveedores (Clipro)
- [x] **Clipro no se borra se desactiva:** Solo el admin puede desactivar. La idea es no borrar y dejar movimientos huérfanos, por lo cual directamente lo desactivamos y se deja de ver en el ABM pero no se borra.
- [x] **CUIT no permite duplicar cliente/proveedor:** Alerta de duplicado cuando el cliente ya existe (burbuja/toast arriba a la derecha).
- [x] **Validación de Email y Teléfono:** Email con '@' y punto, teléfono estrictamente numérico sin spinners numéricos en el input.
- [x] **Código Postal y Localidad:** Autorelleno/sugerencias de localidades para agilizar la carga.
- [x] **Campo Contacto:** Oculto cuando la verticalidad activa sea Armería.

## Trazabilidad, Preventa y Reservas SIGIMAC
- [x] **Trazabilidad y Flujo de Reservas SIGIMAC:**
  - Botón Facturar en Reservas con pase de ID (?cliente_id=X) y precarga automática de cliente e impuestos en Trazabilidad.
  - Typeahead de series que sugiere directamente las armas reservadas activas del cliente.
  - Alerta de reserva pendiente al seleccionar cliente en Trazabilidad.
  - Control de concurrencia: Verificación previa de estado de reserva para evitar doble venta simultánea.
- [x] **Notas de Reservas SIGIMAC en Preventa y Bandeja:**
  - Intercepción modal (Swal.fire) obligatoria al confirmar preventa con armas trazables para que el vendedor registre indicaciones al cajero.
  - Traspaso automático de notas a la reserva al cobrar en Tesorería.
  - Columna de Notas con botón (SVG interactivo) y modal en la bandeja de Reservas SIGIMAC.
- [ ] **Trazabilidad Armas (Detalle/Historial/Factura):** Detalle mostrar pendiente y el historial es detalles el card. Cuando le demos click al card de la línea de tiempo, este abre el detalle editable. Agregar botón de Factura a la card del historial para rearmar la factura de venta sin tener que buscarlo en el listado de ventas.
- [ ] **Aislamiento por Sucursal (Preventa y Trazabilidad):** No facturar de otra sucursal en Trazabilidad ni Preventa. Si estoy en sucursal 0 no puedo operar movimientos ni clientes de sucursal 2. Todo lo que tenga sucursal_id pertenece estrictamente a esa sucursal.
- [ ] **CUIM:** 6 dígitos obligatorio en compra a proveedores (si el clipro es Cliente, sí se permite).
- [x] **CLU obligatorio para Municiones en Preventa:** Validar CLU al vender munición. Permitir al vendedor abrir modal rápido de edición de cliente para actualizar CLU y vencimiento en ese instante.
- [x] **Bucle en credencial fallida en venta:** Corregir bucle de alerta continua cuando se ingresa una credencial de 6 dígitos o menos.
- [ ] **Mapeo de Teclado:** Navegación fluida en formularios mediante Tab, Enter y Flechas (baja prioridad / punto fino).


Roles
- Usuarios:
    - Eduardo Odone: Cajero
    - Santiago Mozzoni: Cajero
    - Alicia Mercado: Contabilidad + Cajero
    - Nicolas Spector: Admin
    - Esteban Spector: Admin
    - Alicia Toulet: Admin
    - Jorge Armas: Vendedor
    - Mario Barthaburu: Vendedor
    - Nahuel Consalvo: Vendedor
    - Walter Bounar: Vendedor
- Roles:
    - Vendedor: Generar Pedido de Venta (PREVENTA), Listado Clientes, Dashboard de Armas Disponibles (nueva vista de lectura con las armas que estan a la venta, sus precios y caracteristicas),
    - Cajero: Todo lo del vendedor + Trazabilidad de armas, Caja Mostrador, Stock Armas, Venta trazabilidad, Reserva por venta de armas, Listado de ventas, Ventas por producto, Facturas pendientes,
    - Contabilidad: Ver con Juan
    - Admin: Todo