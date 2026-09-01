# Búsqueda y Autocarga por N° de Serie en Remitos Internos

Este plan actualiza el flujo de carga rápida de Remitos Internos conforme al requerimiento exacto:
Al ingresar o escanear un **N° de Serie** en el campo `Nº SERIE (si aplica)`, el sistema buscará el registro en la tabla `Subproducto`, verificará que no esté vendido (`situacion != 'VENDIDA'`), comprobará que pertenezca a la sucursal de origen (o sucursal activa), extraerá el `producto_id`, consultará la descripción en `Producto` y autocompletará todos los datos en el formulario.

## Revisión del Usuario Requerida

> [!IMPORTANT]
> - **Secuencia de Verificación por N° de Serie:**
>   1. Buscar en `Subproducto` por `serie__iexact = serie` y `empresa_id`.
>   2. Verificar que `situacion != 'VENDIDA'` (rechazar si ya fue vendida).
>   3. Verificar que `subproducto.sucursal_id == sucursal_origen` (o sucursal activa). Si pertenece a otra sucursal, informar la sucursal donde se ubica.
>   4. Obtener `producto_id = subproducto.producto_id`, buscar en `Producto` y obtener `detalle`.
>   5. Autocompletar en el formulario: `producto_id`, `detalle`, `serie` (formateada) y `cuim`.

## Preguntas Abiertas

*No se detectan ambigüedades. El flujo especificado por el usuario ha sido detallado paso a paso.*

## Cambios Propuestos

### Módulo de Facturación y Vistas HTMX

#### [MODIFY] [views_remito_interno.py](file:///d:/JM_Soft/erp-ikigai-2/facturacion/views_remito_interno.py)
- Crear/Actualizar la vista HTMX `buscar_subproducto_por_serie_ri`:
  - Recibe `serie` y `sucursal_origen`.
  - Ejecuta la consulta:
    ```python
    subp = Subproducto.objects.filter(
        serie__iexact=serie, empresa_id=empresa_id
    ).exclude(situacion='VENDIDA').select_related('producto', 'sucursal').first()
    ```
  - Validaciones:
    - Si no existe: responde aviso HTMX *"N° de Serie no encontrado o ya vendido."*
    - Si `subp.sucursal_id != sucursal_origen_id`: responde aviso HTMX *"El N° de Serie pertenece a [Sucursal], no a la sucursal de origen seleccionada."*
    - Si pasa las validaciones: responde con encabezado `HX-Trigger` enviando la carga útil JSON `{ id: subp.producto_id, detalle: subp.producto.detalle, serie: subp.serie, cuim: subp.cuim or '', subproducto_id: subp.subpro }`.

#### [MODIFY] [urls.py](file:///d:/JM_Soft/erp-ikigai-2/config/urls.py)
- Registrar la URL `compras/remitos-internos/buscar-serie/` con nombre `ri_buscar_serie`.

### Plantilla y JavaScript del Formulario

#### [MODIFY] [remito_interno_carga.html](file:///d:/JM_Soft/erp-ikigai-2/templates/facturacion/remito_interno_carga.html)
- En el input `quick_serie` (campo `Nº SERIE (si aplica)`), agregar eventos HTMX:
  - `hx-get="{% url 'ri_buscar_serie' %}"`
  - `hx-trigger="keyup delay:400ms changed, change, keydown[key=='Enter']"`
  - `hx-include="[name='sucursal_origen']"`
  - `hx-target="#serie-aviso-container"`
- Agregar contenedor de avisos `#serie-aviso-container` para mostrar alertas de validación de serie.
- Registrar el listener JS de `serieEncontradaRI`:
  - Rellena `quick_producto_id` con `data.id`.
  - Rellena `quick_producto_detalle` con `<span class="text-blue-600 font-black">${data.detalle}</span> <span class="text-[9px] bg-blue-100 text-blue-800 px-2 py-0.5 rounded ml-2">CUIM: ${data.cuim}</span>`.
  - Establece la cantidad en `1`.
  - Mueve el foco al botón **AÑADIR**.

## Plan de Verificación

### Pruebas Automatizadas
- Añadir pruebas unitarias en `facturacion/tests/test_plan028.py`:
  1. Test de serie no existente o vendida (`situacion='VENDIDA'`) -> verifica aviso de error.
  2. Test de serie en sucursal incorrecta -> verifica mensaje con nombre de la sucursal actual.
  3. Test de serie válida en sucursal de origen -> verifica autocompletado del `producto_id`, `detalle` y `cuim`.

### Verificación Manual
1. Abrir **Nuevo Remito Interno** y seleccionar sucursal Origen.
2. Tipear un N° de Serie en el campo `Nº SERIE (si aplica)` y presionar Enter o Tab.
3. Verificar que el sistema busque el subproducto, valide `situacion != 'VENDIDA'`, confirme la sucursal activa/origen y cargue automáticamente el ID del producto y su descripción.
