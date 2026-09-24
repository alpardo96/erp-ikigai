# Observaciones y Estado - Módulo Armería & ERP

---

## 1. GENERAL
- [ ] **1.1 Separador de miles:** Todos los números poner separador de miles `$1.000.000` (uniformar uso del filtro `formato_ar` en todas las grillas e inputs monetarios).
- [ ] **1.2 Formato de comprobantes impresos:** Comprobantes impresos deben tener logo y mantener el formato del anterior sistema (en recibos hay mucha info no útil).

---

## 2. DASHBOARD
- [ ] **2.1 Accesos rápidos:** Accesos rápidos si no funcionan los quitamos (no mostrarles algo que no funciona aún).
- [ ] **2.2 Configuración por rol:** Que se pueda configurar el dashboard según rol (o dejarlo fijo para los roles de vendedores/cajeros/admin).

---

## 3. ALTA CLIENTE / PROVEEDOR
- [x] **3.1 Lupa en CUIT (Consulta ARCA/AFIP):** Funcionalidad integrada en el modal de clientes (`consultar_padron_afip` vía Padrón A13). *(Pendiente de validación final con CUIT de prueba por el usuario)*.
- [x] **3.2 Bloqueo de eliminación de clientes:** En Armería los clientes no se borran de base de datos; se desactivan (`armeria.activo = False`) y quedan ocultos del listado y búsquedas operativas sin dejar movimientos huérfanos.
- [ ] **3.3 Autocompletado por Código Postal:** Cuando pones el código postal no se prellena la localidad/ciudad ni la provincia como el anterior sistema —> *Pendiente incorporar diccionario local de C.P.*
- [ ] **3.4 Nombre y Apellido unificados:** Apellido y nombre en Apellido solamente, ¿hacemos cambio masivo de los que tienen constancia ARCA? *(Pendiente definición / script masivo)*.

---

## 4. MANTENIMIENTO DE PRODUCTOS
- [ ] **4.1 Familias y subfamilias:** Pendiente cargar familias y subfamilias maestras.
- [x] **4.2 No permitir borrado físico de productos:** Implementado soft-delete (`producto.activo = False`) en lugar de eliminación física en cascada.
- [ ] **4.3 Códigos de producto vs ID:** Mal ingresados los códigos de productos, ejemplo: 5320 (`BINOC SAVAGE 8X21 M.RUBI (24300)`) en sistema nuevo dice ID 5289 (mostrar y priorizar código de proveedor/original `cod_prov`).
- [ ] **4.4 Inventarios parciales:** ¿Cómo se cargan los inventarios parciales? Municiones y Armas especialmente, pero todo sería bueno —> *Pendiente desarrollar módulo de inventario parcial*.
- [ ] **4.5 Actualización masiva de precios:** Nueva sección de actualización de precios masivo / individual.

---

## 5. TRAZABILIDAD DE SUBPRODUCTOS
- [ ] **5.1 Permisos de edición Serie/CUIM:** Limitar que no puedan editar los números de serie/CUIM los vendedores/cajeros (restringir `subproducto_editar_modal` exclusivamente a Administradores).
- [ ] **5.2 Conteo de disponibles:** En la búsqueda por nombre de producto el conteo de disponibles no siempre coincide (Ejemplo: `PIST BERSA C.22 M.THUNDER PAVON 6`).
- [ ] **5.3 Nro. de remito en ficha de venta:** Agregar el número de remito en la ficha de venta (se informa a la hora de entregar el producto).
- [ ] **5.4 Buscador de clientes/proveedor en trazabilidad:** Revisar y asegurar funcionamiento de búsqueda por Cliente o Proveedor.
- [ ] **5.5 Manejo de consignaciones:** ¿Cómo manejamos las consignaciones? —> Se registra como un nuevo producto / estado especial.

---

## 6. STOCK ARMAS
- **6.1 Objetivo:** Los vendedores deben poder ir filtrando los resultados rápidamente según solicite el cliente (ej. `PISTOLAS` - `BERSA` - `C.380`), y en ese listado poder ofrecerle los diferentes modelos.
- **6.2 Filtros:**
  - [x] Quitar filtro de cliente/proveedor de la vista de Stock de Armas.
  - [ ] Agregar filtro desplegable/buscador de Calibre y Marca.
- **6.3 Columnas del Listado:**
  - [ ] Quitar columnas fijas de marca y calibre.
  - [ ] Agregar Código de producto y Precio de lista/venta.
- [ ] **6.4 Estado inicial de armas:** Revisar por qué todas aparecen marcadas en "usadas".
- [ ] **6.5 Pestañas de categorías:** Agregar filtro/pestañas selectoras de categorías (`TODOS`, `PISTOLA`, `ESCOPETA`, `CARABINA`, `FUSIL`, `RECARGA`, `PISTOLON`, `USADAS`).
- [ ] **6.6 Búsqueda rápida multicriterio:** En detalle de productos, al escribir ej. `BERSA C.380` deben listarse automáticamente debajo las armas que cumplan con esa descripción en lugar de obligar a elegir un único producto.
- [ ] **6.7 Botón Generar Preventa desde el arma:** Botón para generar pedido de venta (PREVENTA) directo desde la fila del producto seleccionado, precargando el arma y restando solo elegir el cliente.
- **6.8 Detalle de Artículo (Modal):**
  - [ ] Revisar precios en dólares que se muestran en pesos sin realizar la conversión con cotización.
  - [ ] Dólares mostrados con formato pesos (y corregir cálculo de cambio).
  - [ ] Agregar atributos adicionales: código producto, estado (nueva o usada), observaciones/notas del producto si las hubiese.

---

## 7. RECEPCIÓN Y LOGÍSTICA
- [ ] **7.1 Circuitos de mercadería:** Recepción de mercadería, remitos internos, recepción interna, órdenes de compra —> *Pendiente revisión con Esteban*.

---

## 8. COMPRAS
- [ ] **8.1 Persistencia de cabecera en carga de compras:** Al modificar algo de los productos o ante un error de validación, evitar que se limpien los datos del proveedor, fecha y comprobante.
- [ ] **8.2 Validación de unicidad de Serie / CUIM:** Validar que no permita cargar números de serie o CUIM idénticos en la misma compra o ya existentes activos.
- [ ] **8.3 Carga de CUIM en Compras de Armas:** Error *"Debe ingresar el CUIM (6 dígitos) del artículo para compras de Armería"* pero no se visualiza el input de CUIM en el formulario de compras estándar.
- [ ] **8.4 Revisión complementaria:** *Pendiente revisión con Esteban*.

---

## 9. VENTAS
- [ ] **9.1 Menú Carga de Ventas:** Ocultar botón/tarjeta *"Generar Venta"* común en el módulo de Armería (solo usar Preventa y Venta Trazabilidad).
- **9.2 Facturación Trazabilidad:**
  - [ ] Validar estrictamente por sucursal: no permitir facturar desde sucursal Central armas que pertenecen físicamente a Yerba Buena y viceversa.
  - [ ] ¿Se puede facturar un arma sin que esté reservada?: Definición de regla (en teoría primero se genera la reserva SIGIMAC con su medio de pago y luego se habilita la facturación).
  - [ ] Corregir UI: El autocompletado de número de serie tapa la tabla inferior y al hacer clic en el precio se agregan dos ceros erróneamente.
- **9.3 Generar Pre Venta:**
  - [ ] Permitir crear un cliente nuevo directamente desde la pantalla de Preventa (botón `+` para abrir modal de alta rápida), no solo buscar y editar.
  - [ ] Corregir etiqueta en cabecera de grilla: cambiar `Pcio. Final ($)` por `Precio unitario ($)`.
  - [ ] Cartilla de consumo: Permitir editar la cartilla de consumo una vez agregado el producto (ya que suele entregarse con posterioridad).
  - [ ] Facturas pendientes: Evaluar uso o quitar del módulo si no aplica a la operativa diaria.

---

## 10. TESORERÍA & CAJA
- [ ] **10.1 Emitir Recibo:** Quitar del menú lateral principal; dejar únicamente el acceso integrado desde Caja Mostrador.
- [ ] **10.2 Medios de pago en Recibos:** Mostrar todos los medios de pago configurados en el listado de recibos.
- [ ] **10.3 Emitir Orden de Pago:** Evaluar casos de uso o simplificar circuito.
- **10.4 Caja Mostrador:**
  - [ ] Formato de retiros parciales: Imprimir comprobante en el formato homologado para firma del cajero.
  - [ ] Cierre de caja: Solicitar arqueo discriminando tarjetas, transferencias, cheques, efectivo ARS y dólares USD.
  - [ ] Reservas de armas: Añadir medio de pago Cuenta Corriente en la reserva de armas.
  - [ ] Tipo de cambio USD: Permitir ajustar la cotización del dólar al cobrar con método de pago Dólares.
  - [ ] Revisión visual y datos mostrados en la opción Reserva desde caja mostrador.
  - [ ] Autorización para anulación: Exigir autorización/clave para poder anular o borrar un pedido de venta.
  - [ ] Definición de circuito de gastos menores: ¿se continúan registrando vía Retiro Parcial?
  - [ ] Nomenclatura: Evaluar cambio de denominación de "Reserva" por término operativo equivalente si aplica.
- [ ] **10.5 Caja Diaria:** Revisar utilidad; si no se utiliza, remover del menú lateral.
- [ ] **10.6 Origen y Aplicación de Fondos (EOAF):** Si no se utiliza en la operativa, remover del menú lateral.
- [ ] **10.7 Recepción de Rendiciones:** Revisar flujo de recepción de cierres de caja (actualmente redirige al menú sin procesar la recepción).

