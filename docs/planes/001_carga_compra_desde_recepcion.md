# Integración de Recepción en Carga de Compra

Se implementará el flujo solicitado para vincular un Informe de Recepción (Remito de Compra) directamente al cargar una Factura de Compra, respetando los precios de la Orden de Compra si ésta tenía carga de costos habilitada, o permitiendo su edición si no la tenía.

## User Review Required

Se requiere aprobación para añadir este nuevo modal y la lógica de vinculación. El flujo principal de guardado en `_procesar_circuito_oc` no se alterará, pero se nutrirá con datos provenientes de la `Recepción` en lugar de la `Orden de Compra` directa.

## Open Questions

- Actualmente la lógica asume que las Recepciones que se van a listar en el modal son las que pertenecen al `ClienteProveedor` seleccionado en la cabecera. ¿Esto es correcto?
- Si una sola factura engloba ítems de un remito que venía con precio (OC con costos) y de otro remito sin precio, el sistema bloqueará únicamente los precios de los ítems correspondientes a la OC con costos. ¿Está bien este comportamiento a nivel de ítem?

## Proposed Changes

### Vistas HTMX (`facturacion/views_recepcion.py` o `facturacion/views_oc.py`)

Se crearán dos nuevas vistas:

#### [NEW] `FacturaVincularRecepcionModalView`
Filtra las recepciones activas (`estado=Recepcion.ACTIVA`) del proveedor seleccionado que tengan cantidades pendientes de facturar.

#### [NEW] `FacturaVincularRecepcionView`
*   Busca los ítems de las recepciones seleccionadas y sus respectivas imputaciones a Órdenes de Compra.
*   Agrupa por producto para armar la tabla de cotejo (`compra_items_temp`).
*   Si la OC original tenía `carga_costos=True`, el precio se arrastra a la factura y se marca como `precio_readonly=True`. Si tenía `carga_costos=False`, el precio será `0` y editable.
*   Los ítems generados mantendrán la metadata `oc_fuentes` para que el método `_procesar_circuito_oc` existente procese correctamente la vinculación y actualice los saldos de facturación sin duplicar los remitos.

### Plantillas HTMX

#### [MODIFY] `facturacion/templates/facturacion/compras_carga.html`
* Se añadirá el botón "Vincular Recepción" en la sección de herramientas de la grilla.

#### [MODIFY] `facturacion/templates/facturacion/partials/compra_cotejo_tabla.html`
* Se actualizará el `<input>` del precio (`name="precio"`) para que incluya `readonly` y cambie visualmente (ej. fondo grisáceo o sin outline) cuando `item.precio_readonly` sea verdadero.

#### [NEW] `facturacion/templates/facturacion/modals/factura_vincular_recepcion.html`
* Plantilla del modal que listará los Informes de Recepción disponibles con checkboxes para seleccionar los deseados, con diseño idéntico al actual modal de `vincular_oc`.

### Enrutamiento (`config/urls.py`)

#### [MODIFY] `config/urls.py`
Se agregarán las rutas para las nuevas vistas del modal HTMX.

## Verification Plan

### Manual Verification
1. Crear OC sin precio (`carga_costos=False`).
2. Recepcionar la OC.
3. Ir a Carga Compra, seleccionar Proveedor, hacer clic en "Vincular Recepción".
4. Seleccionar la recepción. Verificar que los ítems se cargan, las cantidades concuerdan, el precio es 0 y es editable.
5. Crear OC con precio (`carga_costos=True`).
6. Recepcionar la OC.
7. En Carga Compra, vincular esa Recepción. Verificar que trae el importe de la OC y el campo está bloqueado (solo lectura).
8. Guardar la factura y verificar que se descontó el `pendiente_facturacion` correctamente y no se duplicó el stock ni el remito.
