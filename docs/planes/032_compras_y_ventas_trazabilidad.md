# Plan de Implementación (032 - 27/07/2026): Compra Trazabilidad, Configuración en EmpresaTrazabilidad y Mejoras en Venta Trazabilidad

Este plan detalla el diseño técnico para implementar el circuito integral de **Compra Trazabilidad**, la nueva sección de **Configuración de Trazabilidad en Productos** mediante una tabla separada `EmpresaTrazabilidad`, y las evoluciones en **Venta Trazabilidad** (eliminación de carga manual de número, obligación estricta de emisión con AFIP/ARCA sin excepción, y auto-completado en el buscador de series).

---

## Decisiones Arquitectónicas y de Revisión

1. **Modelo EmpresaTrazabilidad**: Para mantener limpia la tabla `Empresa`, se agrega un solo campo `usa_trazabilidad = models.BooleanField(default=False)` en `Empresa` y se crea una tabla dedicada `EmpresaTrazabilidad` (`OneToOneField(Empresa)`) con los campos `pedir_situacion`, `pedir_estado` y `pedir_cuim`.
2. **Venta Trazabilidad - AFIP/ARCA Estricto**: Al operar con comprobantes fiscales (`condic == 1`), la respuesta exitosa de ARCA/AFIP (`AFIPService`) será indispensable. **Nunca se avanzará ni se guardará la factura si AFIP no responde o falla**. No existe facturación en trazabilidad sin conexión AFIP.
3. **Moneda y Cotización en Compra Trazable**: Se conservarán exactamente la moneda (`PES`, `DOL`, `60`/EUR) y cotización ingresada en la cabecera de la factura en los atributos de cada `Subproducto` creado.

---

## Cambios y Detalle Técnico por Módulo

### 1. Módulo de Empresas y Base de Datos
- **`empresas/models.py`**:
  - Agregar `usa_trazabilidad = models.BooleanField(default=False, verbose_name="Usa Trazabilidad de Productos")` en `Empresa`.
  - Crear el modelo dedicado `EmpresaTrazabilidad` con un `OneToOneField` a `Empresa` y los flags:
    - `pedir_situacion = models.BooleanField(default=False)`
    - `pedir_estado = models.BooleanField(default=False)`
    - `pedir_cuim = models.BooleanField(default=False)`
- **`productos/models.py`**:
  - Modificar `cotizadq` en `Subproducto` a `decimal_places=4` para homologar precisión con `Compra.cotizacion`.

### 2. Módulo de Configuración (UI y Backend)
- **`templates/configuracion/partials/hub.html`**: Incorporar la tarjeta de **Compra Trazabilidad** (`hx-get="{% url 'configuracion_index' %}?tab=compra_trazabilidad"`).
- **`templates/configuracion/partials/compra_trazabilidad.html`**: Formulario HTMX para activar/desactivar `usa_trazabilidad` en la empresa y alternar `pedir_situacion`, `pedir_estado`, `pedir_cuim`.
- **`core/views_config.py`**: Agregar soporte al tab `compra_trazabilidad` en `ConfiguracionIndexView` y endpoint POST `guardar_configuracion_trazabilidad`.

### 3. Módulo de Compra Trazabilidad
- **`facturacion/views_htmx.py`**: Soporte para filtro `solo_trazables=1` (`Q(subprod=True)`) en el typeahead y buscador de productos.
- **`facturacion/views_trazabilidad.py`**:
  - `ComprasTrazabilidadCargaView` (GET/POST) para cabecera fiscal con moneda y cotización, generando `CompraItem` y `Subproducto` (que por señal transaccional actualiza `StockSucursal` +1 y recálculo total).
  - Endpoints HTMX: `compras_trazabilidad_item_add`, `compras_trazabilidad_item_remove` y `typeahead_series_trazabilidad`.
- **`templates/facturacion/compras_trazabilidad_carga.html`**: Interfaz de compra trazable moderna con validación en cliente/servidor.
- **`templates/facturacion/partials/compra_trazabilidad_items_tabla.html`**: Grilla interactiva de ítems temporales en sesión.

### 4. Mejoras en Venta Trazabilidad
- **`templates/facturacion/ventas_trazabilidad_carga.html`**: Eliminar input visual de Número de comprobante. Integrar auto-completado de series en `#serie_escaneada`.
- **`facturacion/views_trazabilidad.py`**: Implementación estricta de `AFIPService.emitir_comprobante` al emitir comprobantes fiscales reales (`condic == 1`), denegando la venta ante fallas o falta de conexión de ARCA/AFIP.
- **`templates/facturacion/partials/serie_typeahead.html`**: Menú flotante HTMX de sugerencias para auto-rellenado del número de serie.

---

## Verificación y Pruebas
- Validación de sintaxis e importaciones (`python manage.py check`).
- Ejecución de migraciones y pruebas de stock automáticas (`python manage.py test productos.tests.test_stock`).
- Verificación manual completa en entorno de desarrollo.
