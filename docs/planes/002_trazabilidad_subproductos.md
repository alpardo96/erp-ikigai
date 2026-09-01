# Plan de Implementación: Trazabilidad de Subproductos (Armería / Concesionaria)

Este plan detalla los pasos para incorporar la gestión individualizada de productos mediante número de serie, CUIM o dominio, integrando este requerimiento en los flujos de compras y ventas de acuerdo a la lógica solicitada.

## User Review Required

> [!WARNING]
> **Campo redundante en Subproducto**: El campo `detalle` en la tabla `Subproducto` será eliminado ya que esta información se hereda de la relación con `Producto` (`producto.detalle`). Si hay migraciones o vistas actuales que dependan fuertemente de este campo sin hacer el join con producto, deberán ser ajustadas.
> 
> **Marcado de Empresas**: Actualmente existe el campo `es_armeria` (booleano) en el modelo `Empresa`. Para englobar tanto armerías como concesionarias u otros rubros de trazabilidad, propongo reemplazarlo (o añadir) un campo `usa_trazabilidad` (booleano) o un campo de opciones `tipo_actividad` (Ej: Estándar, Armería, Concesionaria). De momento, el plan asume renombrar/crear `usa_trazabilidad`.

## Open Questions

> [!IMPORTANT]
> 1. **Definición de Empresa**: ¿Prefieres que usemos un booleano genérico `usa_trazabilidad = True` o que configuremos un campo de opciones `tipo_actividad` para distinguir si es Armería (pide CUIM) vs Concesionaria (pide Motor/Chasis/Patente)?
> 2. **Formulario de Ventas**: Mencionas un "formulario único para este tipo de facturación" (Ventas). ¿Deseas que este formulario sea una pantalla completamente separada en el menú (ej. "Facturación Armería"), o que sea el mismo formulario de ventas estándar pero que al detectar que la empresa "usa trazabilidad" habilite un campo especial para "Escanear Serie"?

## Proposed Changes

### Modelos (Base de Datos)

#### [MODIFY] [empresas/models.py](file:///d:/JM_Soft/erp-ikigai-2/empresas/models.py)
- Modificar el modelo `Empresa` para incluir el flag o tipo de actividad que habilita la trazabilidad (ej. `usa_trazabilidad = models.BooleanField(default=False)`).

#### [MODIFY] [productos/models.py](file:///d:/JM_Soft/erp-ikigai-2/productos/models.py)
- En el modelo `Subproducto`, eliminar el campo `detalle` (`detalle = models.CharField(...)`).
- Crear las migraciones correspondientes (`python manage.py makemigrations` y `migrate`).

---

### Módulo de Compras (Recepción)

#### [MODIFY] facturacion/views.py (o donde resida la lógica de guardado de Compras)
- Al procesar y confirmar la carga de una Compra, el backend interceptará los ítems. Si alguno pertenece a un `Producto` con `subprod=True`, se validará que vengan los datos de serie/cuim correspondientes desde el frontend.
- Se crearán los registros en la tabla `Subproducto` con los datos de costo, fecha y la relación `compra_id`.

#### [MODIFY] templates/facturacion/compras_carga.html (o equivalente)
- Se añadirá lógica HTMX/JS: Si el usuario añade a la grilla un ítem que tiene `subprod=True`, se abrirá un **Modal de Carga de Series**.
- Este modal solicitará tantas Series/CUIM como cantidad se haya puesto en la compra (ej. si compra 3 pistolas, el modal pedirá 3 series).
- Estos datos se almacenarán temporalmente en el form/sessionStorage para enviarse junto con la compra al guardar.

---

### Módulo de Ventas (Facturación de Subproductos)

#### [NEW] facturacion/views_trazabilidad.py (o añadido en views.py)
- Crear una vista específica (o adaptar la existente) para la "Venta por Serie".
- Un endpoint que reciba una `serie` escaneada, busque en `Subproducto` donde `situacion='DEPOSITO'`, y retorne los datos del `Producto` asociado, su precio, etc., para agregarlo al carrito de ventas.

#### [NEW/MODIFY] templates/facturacion/ventas_trazabilidad.html
- Diseñar la interfaz de facturación rápida por serie.
- Al confirmar la venta:
  - Se vincula el `Subproducto` con el `venta_id`.
  - Se actualiza el estado de `Subproducto` a `situacion='VENDIDA'`.
  - Se da de baja el `stock` en la tabla `Producto`.

## Verification Plan

### Automated Tests
- No se prevén tests automatizados en esta fase a menos que ya exista una suite de tests de integracion para facturacion. En ese caso, se crearán tests para el flujo de carga y descarga de subproductos.

### Manual Verification
1. **Configuración**: Marcar una empresa de prueba como "usa_trazabilidad".
2. **Productos**: Crear un producto con `subprod=True`.
3. **Compra**: Registrar una compra de 2 unidades del producto. Verificar que el sistema exija cargar 2 series y guarde 2 registros en `Subproducto`.
4. **Base de Datos**: Confirmar que `Subproducto` se grabó sin el campo `detalle` y que el stock general del `Producto` subió.
5. **Venta**: Ir al formulario de ventas, ingresar una de las series recién compradas. Confirmar que trae el producto correcto, realizar la venta, y verificar que la serie quedó marcada como "Vendida" y el stock disminuyó en 1.
