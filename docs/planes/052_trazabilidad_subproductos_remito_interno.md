# Trazabilidad de Subproductos (N° Serie y CUIM) en Remitos Internos y Recepción

Este plan detalla la solución técnica para gestionar la transferencia entre sucursales de productos trazables (`subprod = True / 1`). Al confeccionar un Remito Interno, se identificará el `Subproducto` en la sucursal de origen mediante su número de serie (`serie`), cargando su `subproducto_id` y `cuim`. Dicha información figurará en el remito impreso (PDF) y en la pantalla de recepción interna, y al confirmarse la recepción en la sucursal de destino, se actualizará automáticamente `subproducto.sucursal_id` al destino.

## Revisión del Usuario Requerida

> [!IMPORTANT]
> - **Campos en RemitoInternoItem:** Se agregan `subproducto` (FK), `serie` y `cuim` en `RemitoInternoItem`.
> - **Validación de Origen:** Al ingresar la serie en el formulario de Remito Interno, el sistema verificará que el subproducto pertenezca a la sucursal de origen especificada y se encuentre en stock.
> - **Actualización de Ubicación:** Al confirmarse la Recepción Interna por la sucursal de destino, se actualizará el campo `sucursal` de la instancia `Subproducto` para reflejar su nueva ubicación física.

## Preguntas Abiertas

*No se presentan ambigüedades. Los requerimientos concuerdan con la arquitectura de trazabilidad del sistema (`productos.models.Subproducto`).*

## Cambios Propuestos

### Módulo de Facturación (Modelos y Vistas)

#### [MODIFY] [models.py](file:///d:/JM_Soft/erp-ikigai-2/facturacion/models.py)
- Agregar a `RemitoInternoItem`:
  - `subproducto = models.ForeignKey('productos.Subproducto', on_delete=models.SET_NULL, null=True, blank=True, related_name='remitos_internos_items')`
  - `serie = models.CharField(max_length=50, null=True, blank=True, verbose_name="Nro. Serie")`
  - `cuim = models.CharField(max_length=50, null=True, blank=True, verbose_name="CUIM")`
- Crear migración de base de datos correspondiente con `python manage.py makemigrations facturacion`.

#### [MODIFY] [views_remito_interno.py](file:///d:/JM_Soft/erp-ikigai-2/facturacion/views_remito_interno.py)
- **`RiItemAddView`**:
  - Capturar `serie` y `sucursal_origen`.
  - Si `producto.subprod == True`:
    - Validar que se ingrese `serie`.
    - Buscar `Subproducto` en la sucursal de origen. Si no pertenece a dicha sucursal o no existe, devolver error descriptivo.
    - Obtener `subproducto_id = subproducto.subpro` y `cuim = subproducto.cuim`.
    - Almacenar `subproducto_id`, `serie` y `cuim` en la sesión temporal de ítems del remito.
- **`RemitoInternoCargaView.post`**:
  - Al instanciar cada `RemitoInternoItem`, guardar los campos `subproducto_id`, `serie` y `cuim`.
- **`RecepcionInternaVincularView.post`**:
  - Agrupar ítems considerando `(producto_id, subproducto_id)` para preservar la individualidad de cada subproducto trazable, arrastrando `serie` y `cuim` a la sesión de recepción.
- **`RecepcionInternaCargaView.post`**:
  - Al recepcionar un ítem vinculado a un `RemitoInternoItem` con `subproducto_id`:
    - Actualizar `subproducto.sucursal = destino` y guardar `update_fields=['sucursal']`.

### Plantillas HTML y Reportes PDF

#### [MODIFY] [remito_interno_carga.html](file:///d:/JM_Soft/erp-ikigai-2/templates/facturacion/remito_interno_carga.html)
- Agregar un campo para el ingreso de `N° Serie (si aplica)` en la barra de carga rápida.
- Pasar `#quick_serie` y `[name='sucursal_origen']` en la solicitud HTMX del botón **AÑADIR**.

#### [MODIFY] [ri_items_tabla.html](file:///d:/JM_Soft/erp-ikigai-2/templates/facturacion/partials/ri_items_tabla.html)
- Mostrar los datos de `Serie` y `CUIM` en la grilla de ítems del remito interno.

#### [MODIFY] [remito_interno_pdf.html](file:///d:/JM_Soft/erp-ikigai-2/templates/facturacion/pdf/remito_interno_pdf.html)
- Incluir la leyenda de `Serie` y `CUIM` en la tabla impresiva de ítems del Remito Interno en PDF.

#### [MODIFY] [recepcion_interna_items_tabla.html](file:///d:/JM_Soft/erp-ikigai-2/templates/facturacion/partials/recepcion_interna_items_tabla.html)
- Mostrar las columnas / etiquetas de `Serie` y `CUIM` en el formulario de recepción interna para que el receptor pueda cotejar los datos recibidos.

## Plan de Verificación

### Pruebas Automatizadas
- Crear caso de prueba en `facturacion/tests/test_plan028.py` (o módulo de pruebas específico):
  1. Crear un `Subproducto` en sucursal A con número de serie.
  2. Emitir un `RemitoInterno` desde sucursal A hacia sucursal B asociando dicho subproducto.
  3. Verificar que `RemitoInternoItem` contenga `subproducto_id`, `serie` y `cuim`.
  4. Procesar la `RecepcionInterna` en sucursal B.
  5. Comprobar que `subproducto.refresh_from_db().sucursal` haya cambiado a sucursal B.

### Verificación Manual
1. Ir a **Nuevo Remito Interno**, seleccionar sucursal Origen y Destino.
2. Cargar un producto que requiera trazabilidad (`subprod = True`), ingresando su N° de Serie.
3. Confirmar que el sistema traiga automáticamente el CUIM y valide que exista en la sucursal de origen.
4. Emitir el Remito Interno e imprimir el PDF -> Confirmar presencia de Serie y CUIM.
5. Ingresar a **Recepción Interna** desde la sucursal destino -> Vincular el remito y verificar que se muestre Serie y CUIM.
6. Guardar la recepción -> Verificar en la base de datos que `subproducto.sucursal_id` se haya actualizado a la sucursal de destino.
