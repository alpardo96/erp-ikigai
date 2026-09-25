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
- [x] **3.2 Deshabilitar/Habilitar clientes (Solo Administrador, sin basurero):** Se removió el botón de eliminar y el símbolo del basurero de la grilla de clientes (quedando solo Editar). Se incorporó el campo `activo` en `ClienteProveedor` (migración `0005_clienteproveedor_activo`). Exclusivamente los Administradores pueden ver y accionar los botones de Deshabilitar/Habilitar y el selector de filtrado (Habilitados / Deshabilitados / Todos). Para los demás roles no se muestra el filtro y siempre se listan únicamente los clientes habilitados.
- [ ] **3.3 Autocompletado por Código Postal:** Cuando pones el código postal no se prellena la localidad/ciudad ni la provincia como el anterior sistema —> *Pendiente incorporar diccionario local de C.P.*
- [ ] **3.4 Nombre y Apellido unificados:** Apellido y nombre en Apellido solamente, ¿hacemos cambio masivo de los que tienen constancia ARCA? *(Pendiente definición / script masivo)*.

---

## 4. MANTENIMIENTO DE PRODUCTOS
- [ ] **4.1 Familias y subfamilias:** Pendiente cargar familias y subfamilias maestras.
- [x] **4.2 Deshabilitar/Habilitar productos (Solo Administrador, sin basurero):** Se eliminó el botón de eliminar y el símbolo del basurero del catálogo de stock/productos (quedando solo Editar y Duplicar). Únicamente los Administradores pueden Deshabilitar o Habilitar productos y acceder al filtro de estado (Habilitados / Deshabilitados / Todos). Los roles operativos (vendedores, cajeros) no ven el selector de estados y el sistema les restringe en backend y frontend la visualización exclusivamente a productos habilitados.
- [ ] **4.3 Códigos de producto vs ID:** Mal ingresados los códigos de productos, ejemplo: 5320 (`BINOC SAVAGE 8X21 M.RUBI (24300)`) en sistema nuevo dice ID 5289 (mostrar y priorizar código de proveedor/original `cod_prov`).
- [ ] **4.4 Inventarios parciales:** ¿Cómo se cargan los inventarios parciales? Municiones y Armas especialmente, pero todo sería bueno —> *Pendiente desarrollar módulo de inventario parcial*.
- [ ] **4.5 Actualización masiva de precios:** Nueva sección de actualización de precios masivo / individual.

---

## 5. TRAZABILIDAD DE SUBPRODUCTOS
- [X] **5.1 Permisos de edición Serie/CUIM:** Limitar que no puedan editar los números de serie/CUIM los vendedores/cajeros (restringir `subproducto_editar_modal` exclusivamente a Administradores).
- [x] **5.2 Conteo de disponibles:** En la búsqueda por nombre de producto el conteo de disponibles no siempre coincide (Ejemplo: `PIST BERSA C.22 M.THUNDER PAVON 6`).
- [ ] **5.3 Nro. de remito en ficha de venta:** Agregar el número de remito en la ficha de venta (se informa a la hora de entregar el producto).
- [X] **5.4 Buscador de clientes/proveedor en trazabilidad:** Revisar y asegurar funcionamiento de búsqueda por Cliente o Proveedor.
- [ ] **5.5 Manejo de consignaciones:** ¿Cómo manejamos las consignaciones? —> Se registra como un nuevo producto / estado especial.
- [x] **5.6 Ficha Historial:** Implementado en `subproducto_detalle_modal.html` y `trazabilidad_modal_timeline.html`. Ahora se visualiza el Cliente, Comprobante de venta (con enlace directo al visor/PDF), Precio Neto y Total facturado.

---

## 6. STOCK ARMAS
- **6.1 Objetivo:** Los vendedores deben poder ir filtrando los resultados rápidamente según solicite el cliente (ej. `PISTOLAS` - `BERSA` - `C.380`), y en ese listado poder ofrecerle los diferentes modelos.
- **6.2 Filtros & Ordenamiento:**
  - [x] Quitar filtro de cliente/proveedor de la vista de Stock de Armas.
  - [x] Mantener columnas de Marca y Calibre y habilitar ordenamiento interactivo al hacer clic en sus cabeceras.
- **6.3 Columnas del Listado:**
  - [x] Se mantienen las columnas descriptivas (Marca, Calibre, Serie, CUIM).
  - [x] Se agregó la columna ordenable `Precio ($)` que muestra el precio de venta en pesos (pesificado con Dólar Cobranza si el producto cotiza en USD, mostrando además la referencia en dólares debajo).
- [X] **6.4 Estado inicial de armas:** Revisar por qué todas aparecen marcadas en "usadas".
- [x] **6.5 Pestañas de categorías (Familias):** Se implementó barra interactiva de pills con las familias: `TODOS`, `PISTOLA`, `ESCOPETA`, `CARABINA`, `FUSIL`, `PISTOLON`, `USADAS`, con conteo y filtrado en vivo vía HTMX.
- [x] **6.6 Búsqueda rápida multicriterio:** El buscador en vivo filtra directamente sobre la grilla al tipear con debounce de 350ms, sin desplegable emergente ni labels flotantes.
- [x] **6.7 Botón Generar Preventa desde el arma:** Botón en Verde "Generar Preventa" incorporado en el modal de detalle del arma. Se muestra **únicamente** si la sucursal del arma coincide con la sucursal seleccionada en la vista global / sesión. Al pulsarlo, precarga el arma directamente en la Preventa.
- **6.8 Detalle de Artículo (Modal) & Dólares:**
  - [x] Normalización de productos y subproductos a moneda `DOL` donde correspondía.
  - [x] Implementación de pesificación utilizando el parámetro global de la empresa `Dólar Cobranza` (mostrando el cálculo pesificado y la referencia en USD).
  - [x] Se añadió el campo `observaciones` en el modelo `Producto`, en el formulario/modal de carga y edición de productos, y en el modal de detalle del Stock de Armas.

---

## 7. RECEPCIÓN Y LOGÍSTICA
- [ ] **7.1 Circuitos de mercadería:** Recepción de mercadería, remitos internos, recepción interna, órdenes de compra —> *Pendiente revisión con Esteban*.

---

## 8. COMPRAS
- [x] **8.1 Persistencia de cabecera en carga de compras:** Se aseguraron los bindeos de valor en inputs de proveedor, tipo de comprobante, punto, número, moneda y cotización. Además, se integró persistencia automática y restauración transparente mediante `sessionStorage` ante recargas o desconexiones.
- [x] **8.2 Validación de unicidad de Serie / CUIM:** Se blindó la validación en compras tanto dentro del mismo ítem, entre ítems de la sesión y contra la base de datos de subproductos activos (`situacion != 'VENDIDA'`). Formato de CUIM estricto a 6 caracteres alfanuméricos.
- [x] **8.3 Carga de CUIM y Series en Compras de Armas:** Botón en la grilla destacado con `⚠️ Cargar Series/CUIM (0/1)` con animación visual de alerta cuando faltan registrar series, y cambio de estado a `✓ Series/CUIM`. Los errores de validación se reportan dentro del modal sin cerrarlo ni perder datos.
- [ ] **8.4 Revisión complementaria:** *Pendiente revisión con Esteban*.

---

## 9. VENTAS
- [x] **9.1 Menú Carga de Ventas:** Ocultado el botón/tarjeta *"Carga de Ventas"* y *"Nueva Venta"* en el sidebar, index de ventas y listado cuando la empresa activa es de tipo ARMERIA. Además, se protegió la vista `VentasCargaView` para redirigir a Preventas ante accesos directos por URL.
- **9.2 Facturación Trazabilidad:**
  - [x] Validación estricta por sucursal: se valida que el arma pertenezca a la sucursal de la sesión actual al facturar.
  - [x] Exigencia de Reserva SIGIMAC: no se permite "Grabar Venta" sin seleccionar una reserva pendiente del cliente (se añadió selector de reservas asociadas al cliente).
  - [x] Restricción a máximo 1 arma en la grilla y deshabilitación del input de escaneo de series cuando ya hay un arma en el carro.
  - [x] Corrección UI: el dropdown de autocompletado de series se cierra al hacer clic fuera del control.
  - [x] Corrección en edición de precios: uso de `parsear_decimal_ar` para eliminar el bug de duplicación de ceros al editar el monto.
- **9.3 Generar Pre Venta:**
  - [ ] Permitir crear un cliente nuevo directamente desde la pantalla de Preventa (botón `+` para abrir modal de alta rápida), no solo buscar y editar. *(Punto postergado por indicación del usuario)*.
  - [x] Corregir etiqueta en cabecera de grilla: cambiado `Precio Un` por `Precio Unitario ($)` en las tablas de Preventa y Venta Trazabilidad.
  - [ ] Cartilla de consumo: Permitir editar la cartilla de consumo una vez agregado el producto (ya que suele entregarse con posterioridad). *(Punto postergado por indicación del usuario)*.
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

