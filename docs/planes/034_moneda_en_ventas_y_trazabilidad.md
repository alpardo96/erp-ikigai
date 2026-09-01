# Plan de Implementación - Moneda y Cotización en Ventas y Venta por Trazabilidad (034)

## Objetivo
Unificar y perfeccionar la lógica operativa de Moneda (Pesos ARS vs. Dólares USD), conversión mediante cotización global del sistema y emisión fiscal (número otorgado por AFIP/ARCA) tanto en **Carga Venta (`VentasCargaView`)** como en **Venta Trazabilidad (`VentasTrazabilidadCargaView`)**.

---

## Análisis de la Situación Actual

### 1. Carga Venta (`VentasCargaView` / `views_htmx.py`)
- **Cotización y Búsqueda:** El buscador/typeahead de productos y `calcular_precio_sugerido` convierten el precio del producto según si el producto está en USD/PES y la venta se opera en USD/PES, utilizando la cotización global configurable en Parámetros (`CotizacionMoneda.dolar_venta`).
- **Cambio de Moneda en caliente:** Cuando el usuario tiene productos cargados en la grilla y cambia el selector de Moneda (de ARS a USD o viceversa), el backend (`agregar_item_venta_sesion`) actualmente actualiza la moneda en la sesión pero **no recalcula ni convierte el precio unitario y total** de los ítems ya presentes en la grilla.
- **Grabación DB y AFIP:** El comprobante se emite previamente ante ARCA/AFIP (fuera del bloque atómico). Al recibir éxito, se obtiene y guarda el número real (`res_afip['numero_comprobante']`), CAE y vencimiento dentro de un bloque `transaction.atomic()`, registrando importe, moneda (`mon_id`) y cotización (`mon_cotiz`).

### 2. Venta Trazabilidad (`VentasTrazabilidadCargaView` / `views_trazabilidad.py`)
- **Campo Número Manual:** Actualmente en el formulario (`ventas_trazabilidad_carga.html`) existe un campo de entrada manual para `Número`. En las operaciones de trazabilidad, el comprobante siempre es fiscal (`condic = 1`), por lo que el número lo genera y asigna AFIP al confirmar la factura.
- **Selector de Moneda sin disparador HTMX:** El selector de Moneda en `ventas_trazabilidad_carga.html` carece de evento `onchange` o llamada HTMX, por lo que no actualiza la sesión ni recalcula la grilla al cambiar entre Pesos y USD.
- **Carga de ítems sin conversión de cotización:** La vista `agregar_item_venta_trazabilidad` toma los importes del producto (`precio_neto`, `precio_total`) de forma directa sin pesificar o dolarizar en función de la moneda operativa elegida en la venta y la cotización global (`CotizacionMoneda`).

---

## Propuesta de Solución y Detalle Técnico

### A. Módulo de Carga Venta Normal (`facturacion/views_htmx.py`)
1. **Recálculo dinámico de grilla al cambiar Moneda:**
   - Modificar la función `agregar_item_venta_sesion` para detectar cuando la petición es un cambio de moneda (sin `producto_id` pero con parámetro `moneda` que difiere de la sesión previa).
   - Recorrer `request.session['venta_items_temp']` y recalcular `precio` (unitario) y `total` de cada ítem:
     - De **PES a DOL**: dividir el importe por la cotización global del dólar (`round(importe / cotizacion, 2)`).
     - De **DOL a PES**: multiplicar el importe por la cotización global del dólar (`round(importe * cotizacion, 2)`).
   - Actualizar los totales y la grilla con los símbolos visuales correspondientes (`$` o `USD`).

### B. Módulo de Venta por Trazabilidad (`facturacion/views_trazabilidad.py` y templates)
1. **Eliminar entrada manual de Número en `ventas_trazabilidad_carga.html`:**
   - Quitar el campo `<input type="text" name="numero" ...>` de la interfaz, dejando exclusivamente la selección del Punto de Venta (idéntico a `ventas_carga.html`).
   - Mantener intacto el flujo donde el número de comprobante es asignado por ARCA/AFIP (`res_afip['numero_comprobante']`) tras la emisión exitosa y se guarda de forma atómica en la base de datos con `condic = 1`.

2. **Lógica completa de Moneda y Cotización en Trazabilidad:**
   - Agregar en `ventas_trazabilidad_carga.html` en el `<select name="moneda" id="id_moneda">` el trigger HTMX para conectarlo con la grilla:  
     `hx-get="{% url 'ventas_trazabilidad_item_add' %}" hx-target="#items-tabla-container" hx-include="#venta-form" hx-trigger="change"`.
   - Actualizar `agregar_item_venta_trazabilidad` en `views_trazabilidad.py`:
     - Obtener la cotización global en `CotizacionMoneda` de la empresa activa.
     - Gestionar en la sesión la moneda operativa (`venta_trazabilidad_moneda`).
     - Si el usuario cambia la moneda en la pantalla (petición sin nueva serie escaneada), recorrer los ítems de `venta_trazabilidad_items_temp` y convertir los importes de todos los subproductos cargados de PES a DOL o de DOL a PES según la cotización global.
     - Al escanear una nueva serie, convertir el precio original de lista del producto (`producto.moneda`) hacia la moneda seleccionada de la venta (`PES` o `DOL`) utilizando el mismo cálculo de cotización global de `calcular_precio_sugerido`.
     - Guardar en el diccionario temporal del ítem los atributos contables: `moneda_origen`, `cotizacion_aplicada` y `precio_origen`.

3. **Consistencia visual en plantillas (`venta_trazabilidad_items_tabla.html`):**
   - Reflejar dinámicamente en los encabezados y filas de importes el símbolo de la moneda operativa activa (`$` para Pesos, `USD` para Dólares).

---

## Archivos a Modificar

#### [MODIFY] [views_htmx.py](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/facturacion/views_htmx.py)
- En `agregar_item_venta_sesion`: implementar el recálculo de precios de ítems temporales en sesión cuando el usuario cambia el selector de Moneda (ARS/USD).

#### [MODIFY] [views_trazabilidad.py](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/facturacion/views_trazabilidad.py)
- En `agregar_item_venta_trazabilidad`: añadir soporte para cambio de moneda (`venta_trazabilidad_moneda`), conversión de ítems según cotización global (`CotizacionMoneda`) al agregar series o cambiar de moneda y guardado de metadatos de cotización.
- En `VentasTrazabilidadCargaView.post`: verificar que la cotización y moneda guardadas en `Venta` y en los importes de `VentaItem` sigan estrictamente la moneda seleccionada (`DOL` o `PES`) con la validación de AFIP previa a la transacción atómica.

#### [MODIFY] [ventas_trazabilidad_carga.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/facturacion/ventas_trazabilidad_carga.html)
- Eliminar el campo `<input name="numero">` del formulario de cabecera.
- Añadir el atributo `hx-get` en el `<select name="moneda">` para reaccionar al cambio de moneda en la grilla de ítems.

#### [MODIFY] [venta_trazabilidad_items_tabla.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/facturacion/partials/venta_trazabilidad_items_tabla.html)
- Ajustar la visualización del símbolo de moneda (`$` / `USD`) para que responda a la moneda elegida en la venta.

---

## Plan de Verificación

### Pruebas Automatizadas / de Sintaxis
- `py manage.py check` para validar que no haya errores de importación o sintaxis en vistas y modelos.

### Pruebas Funcionales y Manuales
1. **Carga Venta Normal:**
   - Cargar un producto con precio en PES y otro con precio en DOL estando en moneda `ARS`. Verificar importes.
   - Cambiar el selector de Moneda a `USD`. Verificar que los precios e importes de la grilla se dividan automáticamente por la cotización global.
   - Volver a cambiar a `ARS` y verificar que retornen al valor pesificado.
2. **Venta Trazabilidad:**
   - Confirmar que el campo `Número` ya no es visible en el formulario, manteniéndose sólo Punto de Venta.
   - Escanear una serie con producto en PES/DOL estando en moneda `ARS`. Verificar importe y símbolo `$`.
   - Cambiar el selector de Moneda a `USD`. Verificar que el ítem del subproducto en la grilla recalcule su importe en USD y el símbolo se actualice a `USD`.
   - Guardar una venta por trazabilidad y comprobar en la BD (`Venta` y `VentaItem`) que se guarden `moneda`, `cotizacion`, importes e información que trae AFIP de forma correcta.
