# Plan 046 — Credencial Obligatoria en Preventa y Validación de CLU en Ventas de Armería

Este plan detalla los cambios técnicos necesarios para:
1. Exigir la carga de **Credencial** en **Preventa** para productos que tengan `creden = True`.
2. Validar en **Venta Directa, Venta Trazabilidad y Preventa** que el cliente posea una **CLU vigente (no vencida)** antes de permitir agregar o facturar productos con `creden = True` y/o `subprod = True`.

---

## User Review Required

> [!IMPORTANT]
> - **Cambio en Modelo `PreventaItem`:** Se agregará el campo `credencial` y `dmp` al modelo `PreventaItem`, requiriendo ejecutar una migración de base de datos.
> - **Bloqueo de Venta por CLU Vencido/Faltante:** Si el cliente seleccionado no posee CLU registrado en Armería o su CLU se encuentra vencida (y no es Policía), el sistema **bloqueará la incorporación** de productos que exijan credencial o trazabilidad de armas en Preventa, Venta Directa y Venta Trazabilidad.

---

## Proposed Changes

### 1. Modelo y Propiedades (`facturacion/models.py`)

#### [MODIFY] [`facturacion/models.py`](file:///d:/JM_Soft/erp-ikigai-2/facturacion/models.py)
- Agregar la propiedad `@property def esta_vencida(self)` al modelo `ExtensionArmeria`:
  ```python
  @property
  def esta_vencida(self):
      from django.utils import timezone
      if not self.clu_vto:
          return True
      return self.clu_vto < timezone.localdate()
  ```
- Agregar campos a `PreventaItem`:
  ```python
  credencial = models.CharField(max_length=50, null=True, blank=True, verbose_name="Credencial")
  dmp = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="DMP")
  ```

#### [NEW] [`facturacion/migrations/0042_preventaitem_credencial_dmp.py`](file:///d:/JM_Soft/erp-ikigai-2/facturacion/migrations/0042_preventaitem_credencial_dmp.py)
- Archivo de migración generado con `python manage.py makemigrations`.

---

### 2. Helper de Validación de CLU (`facturacion/helpers.py`)

#### [NEW] [`facturacion/helpers.py`](file:///d:/JM_Soft/erp-ikigai-2/facturacion/helpers.py)
- Crear una función reutilizable `validar_clu_cliente_armeria(cliente_id_or_obj, empresa_id)`:
  - Verifica si la empresa es de rubro `ARMERIA`.
  - Si es Armería y el producto requiere `creden` o `subprod`:
    - Verifica si el cliente existe.
    - Consulta `ExtensionArmeria`. Si no tiene registro, bloquea con error: *"El cliente no tiene CLU registrado."*
    - Si `ext.es_policia` es `True`, permite continuar.
    - Si `ext.esta_vencida` es `True`, bloquea con error: *"El CLU del cliente está VENCIDO (dd/mm/yyyy)."*

---

### 3. Plantillas de Frontend

#### [MODIFY] [`templates/facturacion/preventa_carga.html`](file:///d:/JM_Soft/erp-ikigai-2/templates/facturacion/preventa_carga.html)
- Incorporar el bloque `#div_credencial` e input `#quick_credencial` en la barra de carga rápida de la Preventa.
- Incluir `#id_cliente` en el `hx-include` del botón **+ Añadir** para que el backend reciba el cliente seleccionado al agregar el ítem.
- Actualizar el evento JS `productoVentaEncontrado`:
  - Si `data.requiere_credencial` es `true`, hacer visible `#div_credencial`, establecer `required = true`, borrar su valor y hacer foco en `#quick_credencial`.
  - Si no requiere credencial, ocultar `#div_credencial`, quitar `required` y enfocar `#quick_cantidad`.
- Actualizar el evento `limpiarInputsCargaPreventa` para resetear el input `#quick_credencial`.

#### [MODIFY] [`templates/facturacion/partials/preventa_items_tabla.html`](file:///d:/JM_Soft/erp-ikigai-2/templates/facturacion/partials/preventa_items_tabla.html)
- Agregar la columna `<th class="px-2 py-1.5 border-r border-slate-700 text-center">Credencial</th>` en el `<thead>`.
- Renderizar `<td class="px-2 py-1.5 text-center text-slate-500 font-bold border-r border-slate-50">{{ item.credencial|default:"-" }}</td>` en las filas de ítems.

---

### 4. Lógica de Vistas Backend (HTMX y Django Views)

#### [MODIFY] [`facturacion/views_htmx.py`](file:///d:/JM_Soft/erp-ikigai-2/facturacion/views_htmx.py)
- **En `preventas_item_add`:**
  - Leer `request.POST.get('credencial')` y `request.POST.get('dmp')`.
  - Si `producto.creden` es `True`:
    - Validar que se haya ingresado la credencial (`if not credencial:` -> Retornar mensaje de error HTTP).
    - Ejecutar `validar_clu_cliente_armeria(cliente_id, empresa_id)`. Si la CLU está vencida o no existe, retornar mensaje de error HTTP.
  - Almacenar `'credencial': credencial` y `'dmp': dmp` en la estructura de la sesión `preventa_items_temp`.
- **En `agregar_item_venta_sesion` (Venta Directa):**
  - Si `producto.creden` es `True`:
    - Ejecutar `validar_clu_cliente_armeria(cliente_id, empresa_id)`. Si la CLU está vencida o no existe, retornar mensaje de error HTTP 400.

#### [MODIFY] [`facturacion/views.py`](file:///d:/JM_Soft/erp-ikigai-2/facturacion/views.py)
- **En `PreventaCargaView.post`:**
  - Al recorrer `items_temp` para persistir `PreventaItem`, asignar:
    `credencial=item.get('credencial', '')` y `dmp=item.get('dmp', 0)`.

#### [MODIFY] [`facturacion/views_trazabilidad.py`](file:///d:/JM_Soft/erp-ikigai-2/facturacion/views_trazabilidad.py)
- En `agregar_item_trazabilidad` y en la validación de cabecera:
  - Ejecutar `validar_clu_cliente_armeria(cliente_id, empresa_id)` cuando el producto sea de armería (`subprod = True` o `creden = True`).

#### [MODIFY] [`tesoreria/views_htmx.py`](file:///d:/JM_Soft/erp-ikigai-2/tesoreria/views_htmx.py)
- En `_crear_asientos_y_movimientos_cobro` (al facturar la preventa desde la Caja Mostrador):
  - Al copiar `PreventaItem` a `VentaItem`, asignar `credencial=item.credencial` y `dmp=item.dmp`.

---

## Verification Plan

### Automated Tests
- Ejecutar `python manage.py makemigrations` y `python manage.py migrate` para verificar la integridad de la base de datos.
- Ejecutar suite de pruebas: `python manage.py test facturacion` para asegurar no haber roto otros componentes.

### Manual Verification
1. **Carga de Preventa con Credencial:**
   - Seleccionar un producto con `creden = True`.
   - Verificar que aparezca el campo de credencial en rojo en la pantalla de preventa.
   - Intentar agregar sin credencial -> Debe mostrar error.
   - Agregar con credencial -> Debe incluirse en la grilla y mostrarse la columna "Credencial".
2. **Validación de CLU Vencido:**
   - Seleccionar un cliente con CLU vencido o sin CLU en una Empresa de rubro Armería.
   - Intentar cargar un producto con `creden = True` o `subprod = True` en Preventa, Venta Directa y Venta Trazabilidad.
   - Verificar que el sistema bloquee el agregado del producto con un mensaje de alerta claro.
3. **Facturación desde Caja:**
   - Cobrar una preventa cargada con credencial y verificar en la base de datos y detalle de la venta que la `VentaItem` guarde el número de credencial correspondiente.
