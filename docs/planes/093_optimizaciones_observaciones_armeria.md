# Plan 093: Optimizaciones y Blindaje Armería & ERP

**Fecha:** 24 de Septiembre de 2026  
**Documento de Referencia:** [ObservacionesArmeria.md](file:///d:/Proyectos%20Django/erp-ikigai/docs/ObservacionesArmeria.md)  
**Operador:** Cristian - PC CASA  

---

## 1. Objetivos y Alcance

Abordar de forma integral y blindada los siguientes requerimientos acordados:
- **5.6**: Corrección de Ficha Historial / Ficha de Trazabilidad (aparición de cliente, tipo y número de comprobante, precio neto y total).
- **6.2**: Habilitar ordenamiento por Calibre y Marca al hacer clic en las columnas de la tabla de Stock de Armas.
- **6.3**: Mantener las columnas actuales (Marca, Calibre) e incorporar la columna `Precio` (con ordenamiento).
- **6.5**: Pestañas de filtrado rápido por **Familia** (`TODOS`, `PISTOLA`, `ESCOPETA`, `CARABINA`, `FUSIL`, `PISTOLON`, `USADAS`).
- **6.6**: Búsqueda rápida multicriterio en vivo sin popovers desplegables que tapen o fuercen a elegir un producto.
- **6.7**: Botón verde en el detalle "Generar Preventa" condicionado a que la sucursal del arma coincida con la sucursal seleccionada en la vista global.
- **6.8**: Tratamiento de Dólares con parámetro global `Dólar Cobranza` (pesificación + desglose por medio de pago), e incorporación de notas/observaciones del producto en el modelo `Producto` y en el modal.
- **8.1**: Persistencia integral de cabecera en carga de compras (evitar borrado de proveedor, fecha y comprobante ante re-renders o validaciones).
- **8.2 y 8.3**: Blindaje de unicidad de Serie y CUIM en compras (tanto contra base de datos como dentro de la misma compra) y destaque visual del botón de carga de CUIM/Series.
- **9.2**: Blindaje de Facturación por Trazabilidad (exigir Reserva SIGIMAC pendiente para grabar venta, límite estricto de 1 arma por comprobante deshabilitando escaneo sucesivo, cierre de dropdown de serie al hacer clic fuera, y solución definitiva del bug de "dos ceros" al editar precios).
- **9.3**: Corrección de etiqueta `Precio Un` por `Precio Unitario ($)` en la cabecera de la grilla de Preventa y Trazabilidad.

---

## 2. Diagnóstico Técnico y Causa Raíz

### 5.6 Ficha Historial (Trazabilidad)
- **Causa raíz:** En `verticalidades/armeria/views.py` (`subproducto_detalle_modal`), no se realizaba `select_related('venta', 'venta__cliente', 'venta__tipo', 'compra', 'compra__proveedor')` y en el contexto de render **no se pasaban `compra` ni `venta`**. Por ello, en `subproducto_detalle_modal.html` las condiciones `{% if venta and venta.cliente %}` fallaban siempre, mostrando `"Sin Cliente Asociado"` y `"N/A"`. Asimismo, en subproductos migrados `precio_neto` figura en `0.00`, debiendo rescatarse del ítem de venta (`VentaItem`) o calcularse.

### 6.2 y 6.3 Stock de Armas: Ordenamiento y Columna Precio
- **Causa raíz:** `StockArmasListView` no poseía `marca`, `calibre` ni `precio` en su diccionario `sort_map`. Además, las cabeceras `<th>` en `stock_armas_list.html` no invocaban a `toggleSort('marca')` ni `toggleSort('calibre')`, y faltaba la columna `Precio` en `stock_armas_list.html` y `stock_armas_grilla.html`.

### 6.5 Pestañas de Familia
- **Causa raíz:** En el modelo `Producto`, la clasificación armamentística primaria es la `Familia` (`PISTOLA`, `ESCOPETA`, `CARABINA`, `FUSIL`, `PISTOLON`). No existía una barra de pestañas visual para filtrar rápidamente por este campo sin tener que escribirlo a mano.

### 6.6 Búsqueda rápida multicriterio en vivo
- **Causa raíz:** El input `producto_input` en `stock_armas_list.html` utilizaba `typeahead_productos_venta` apuntando a un dropdown flotante (`#producto_suggestions`). Al escribir, abría sugerencias en vez de disparar el filtrado reactivo directo sobre `#stock-armas-rows`. Además, `qs.filter(producto__detalle__icontains=...)` requería coincidencia exacta de la frase, impidiendo filtrar por tokens separados (ej. `BERSA C.380`).

### 6.7 Botón "Generar Preventa" en Detalle
- **Causa raíz:** `stock_armas_detalle_modal.html` solo tenía el botón "Cerrar". Se requiere un botón en verde `Generar Preventa` visible únicamente cuando la sucursal del arma coincida con la sucursal seleccionada en el filtro global. Al pulsarlo, debe enviar a `preventas_carga?subpro_id=...` precargando el arma.

### 6.8 Dólares con Dólar Cobranza y Notas del Producto
- **Causa raíz:**
  1. `stock_armas_detalle_modal` utilizaba `cotiz.dolar_venta` en lugar de `cotiz.dolar_cobranza`.
  2. Los productos y subproductos cargados en dólares (`moneda == 'DOL'` o con cotización histórica) mostraban precios sin discriminar la moneda original ni calcular la pesificación al Dólar Cobranza para los medios de pago en pesos.
  3. El modelo `Producto` no tenía un campo `observaciones` para registrar notas particulares del arma/artículo.

### 8.1 Persistencia de Cabecera en Compras
- **Causa raíz:** En `templates/facturacion/compras_carga.html`, inputs críticos como `id_proveedor`, `proveedor_nombre_display`, `id_tipo`, `quick_comprobante_display`, `punto` y `numero` no tenían bindeado el valor `value="{{ form.campo.value|default:'' }}"`. Ante un error de validación del formulario o posteo con error, la vista re-renderizaba la página y todos los campos quedaban en blanco.

### 8.2 y 8.3 Blindaje de Series y CUIM en Compras
- **Causa raíz:** 
  1. `guardar_series_item` en `facturacion/views_htmx.py` y `ComprasCargaView.post` no validaban duplicados entre los mismos ítems de la compra, ni validaban si el `CUIM` ya existía activo en otro subproducto.
  2. En `compra_items_tabla.html`, el botón de Series/CUIM pasaba desapercibido como un texto azul pequeño en vez de una alerta visible cuando faltan cargar series obligatorias.

### 9.2 Blindaje Facturación Trazabilidad (Reserva, Escaneo, Dos Ceros)
- **Causa raíz:**
  1. No se exigía estrictamente la existencia y selección de una `ReservaArma` en estado `PENDIENTE`.
  2. El dropdown `#serie-typeahead-results` no tenía listener de `click outside` para cerrarse al hacer clic fuera, tapando la grilla.
  3. No se bloqueaba el escaneo cuando ya había un arma en la grilla temporal.
  4. **Bug de los dos ceros:** `editar_item_venta_trazabilidad` hacía `raw_precio.replace('.', '').replace(',', '.')` sobre un valor que `htmx:configRequest` ya había normalizado con punto decimal (`200000.00` -> `20000000`), multiplicando por 100 el valor.

### 9.3 Etiqueta Precio Unitario
- **Causa raíz:** La cabecera decía `Precio Un` en `preventa_items_tabla.html` y en `venta_trazabilidad_items_tabla.html`. Debe decir `Precio Unitario ($)`.

---

## 3. Plan Detallado de Cambios por Archivo

### A. Trazabilidad y Stock de Armas (`verticalidades/armeria/`)
1. **`verticalidades/armeria/views.py`**:
   - En `StockArmasListView.get_queryset`:
     - Agregar filtro multicriterio por tokens en `search_producto`.
     - Agregar filtro por `familia` (o `estado='USADO'` si se selecciona la pestaña Usadas).
     - Incorporar en `sort_map`: `marca`, `-marca`, `calibre`, `-calibre`, `precio`, `-precio`.
   - En `stock_armas_detalle_modal`:
     - Usar `cotiz.dolar_cobranza`.
     - Detectar si el artículo está en dólares (`moneda == 'DOL'` o `cotiz_cpra > 1`). Calcular `precio_pesos = precio_usd * dolar_cobranza`.
     - Ajustar desglose para que medios de pago "Dólares" muestren monto en USD y medios en pesos muestren monto pesificado con ajuste.
     - Pasar `puede_vender` evaluando si la sucursal seleccionada en el filtro global coincide con `subproducto.sucursal_id`.
   - En `subproducto_detalle_modal`:
     - Agregar `select_related('venta', 'venta__cliente', 'venta__tipo', 'compra', 'compra__proveedor')`.
     - Pasar al contexto `compra`, `venta`, y resolver `precio_neto` (desde subproducto o `VentaItem`).
   - En `editar_item_venta_trazabilidad` y `VentasTrazabilidadCargaView.post`:
     - Reemplazar parseos manuales con `parsear_decimal_ar(val)` de `facturacion/helpers.py`.
     - Exigir `reserva_id` obligatorio y validar que pertenezca a la misma sucursal física del subproducto.

2. **`verticalidades/armeria/templates/armeria/stock_armas_list.html`**:
   - Incorporar barra de pestañas (pills) de Familia: `TODOS`, `PISTOLA`, `ESCOPETA`, `CARABINA`, `FUSIL`, `PISTOLON`, `USADAS`.
   - Modificar `producto_input`: eliminar popover de sugerencias, transformar en input reactivo con `hx-get` directo a la grilla y debounce 300ms.
   - Habilitar `onclick="toggleSort('marca')"` y `onclick="toggleSort('calibre')"` en las cabeceras.
   - Agregar columna `Precio` con `onclick="toggleSort('precio')"`.

3. **`verticalidades/armeria/templates/armeria/partials/stock_armas_grilla.html`**:
   - Añadir celda `Precio` mostrando moneda ($ o USD) y monto formateado.
   - En la fila, pasar `hx-include="#form-filtros-stock-armas"` para que el modal de detalle reciba los filtros aplicados.

4. **`verticalidades/armeria/templates/armeria/partials/stock_armas_detalle_modal.html`**:
   - En el footer, al lado de Cerrar, agregar botón en Verde **"Generar Preventa"** cuando `puede_vender` sea True.
   - Mostrar sección de **Notas/Observaciones del Producto** si existen en `subproducto.producto.observaciones`.
   - Mostrar precio en USD y cotización Dólar Cobranza cuando aplique.

5. **`verticalidades/armeria/templates/armeria/partials/subproducto_detalle_modal.html`**:
   - Mostrar correctamente datos del cliente (`venta.cliente.razon_social` o `venta.cliente_razon_social`), comprobante, precio neto y total, más botón directo a PDF de factura.

6. **`verticalidades/armeria/templates/armeria/ventas_trazabilidad_carga.html`**:
   - Escaneo de serie: deshabilitar cuando ya hay 1 ítem en el carro, informando límite de 1 arma.
   - Listener de `click outside` para ocultar `#serie-typeahead-results`.
   - Validar obligatoriedad de Reserva SIGIMAC: deshabilitar o alertar si no se seleccionó reserva activa.

### B. Mantenimiento de Productos (`productos/`)
1. **`productos/models.py`**:
   - Agregar campo `observaciones = models.TextField(null=True, blank=True, verbose_name="Observaciones / Notas")` en `Producto`.
2. **`productos/forms.py`**:
   - Incluir `observaciones` en `ProductoForm`.
3. **`templates/productos/modals/producto_modal.html`**:
   - Agregar textarea para cargar y editar `observaciones`.

### C. Módulo Compras (`facturacion/`)
1. **`templates/facturacion/compras_carga.html`**:
   - Bindeo de `value` en todos los campos de cabecera (`id_proveedor`, `proveedor_nombre_display`, `id_tipo`, `quick_comprobante_display`, `punto`, `numero`, `moneda`, `cotizacion`).
   - Implementar persistencia y restauración en `sessionStorage` para no perder la cabecera al interactuar con ítems o recargar.
2. **`facturacion/views_htmx.py`** (`guardar_series_item`):
   - Validar unicidad de Serie y CUIM dentro de la lista de series cargadas.
   - Validar unicidad de Serie y CUIM contra la base de datos (`Subproducto.objects.filter(...).exclude(situacion='VENDIDA')`).
   - Validar formato de 6 caracteres alfanuméricos para CUIM.
3. **`facturacion/views.py`** (`ComprasCargaView.post`):
   - Replicar validaciones estrictas de duplicidad y formato de series y CUIM al confirmar la compra.
4. **`templates/facturacion/partials/compra_items_tabla.html`**:
   - Mejorar visibilidad del botón de series para ítems trazables cuando están pendientes (badge ámbar/rojo `⚠️ Cargar Series/CUIM`).

### D. Módulo Preventas (`facturacion/`)
1. **`facturacion/views.py`** (`PreventaCargaView.get`):
   - Si recibe `subpro_id`, precargar el arma (`Subproducto`) en `preventa_items_temp` de la sesión y redirigir con el ítem listo en la grilla.
2. **`templates/facturacion/partials/preventa_items_tabla.html` y `venta_trazabilidad_items_tabla.html`**:
   - Cambiar `Precio Un` por `Precio Unitario ($)`.

---

## 4. Plan de Pruebas y Validación

1. **Pruebas de Ficha Historial (5.6)**:
   - Abrir trazabilidad de un arma vendida y verificar que en la ficha se muestre Razón Social del cliente, Comprobante y Precio Neto correcto.
2. **Pruebas de Stock de Armas (6.2, 6.3, 6.5, 6.6, 6.7, 6.8)**:
   - Ordenar por Marca, Calibre y Precio en orden ascendente y descendente.
   - Filtrar con las pestañas de Familia (`PISTOLA`, `ESCOPETA`, `USADAS`).
   - Escribir `BERSA C.380` en el buscador en vivo y comprobar que filtre la grilla directamente sin abrir popovers.
   - Abrir detalle de un arma de Central estando en filtro Yerba Buena: comprobar que NO aparezca el botón verde. Cambiar filtro a Central: comprobar que APARECE el botón verde "Generar Preventa" y al hacer clic precarga el arma en la Preventa.
   - Verificar cálculo de Dólar Cobranza para productos cotizados en USD y visualización de notas del producto.
3. **Pruebas de Compras (8.1, 8.2, 8.3)**:
   - Cargar cabecera de compra, añadir ítems y provocar error de validación: comprobar que proveedor, fecha y comprobante no se limpien.
   - Intentar ingresar series o CUIMs duplicados o ya existentes activos: verificar que bloquee con mensaje descriptivo.
4. **Pruebas de Venta Trazabilidad (9.2)**:
   - Comprobar que no permita grabar venta sin reserva SIGIMAC seleccionada.
   - Escanear 1 arma y comprobar que el input se deshabilite impidiendo agregar una segunda.
   - Editar el precio de venta y comprobar que NO se agreguen dos ceros erróneos.
5. **Pruebas de Preventa (9.3)**:
   - Verificar que la grilla muestre `Precio Unitario ($)`.
