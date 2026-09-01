# Plan 058: Mejoras en Listados de Órdenes de Pago, Recibos y Carga de OP

Este plan ha sido actualizado atendiendo al feedback sobre la ubicación de la columna `Asiento` y la aclaración de perfiles de usuario.

---

## Aclaración sobre Perfiles y Permisos en el ERP

Actualmente en **ERP Ikigai 2** la seguridad y los permisos de usuario se componen de 3 niveles:

1. **`user.is_superuser`** (Nativo de Django):
   - Superusuario con control total sobre la base de datos y la administración de Django.
2. **`user.is_staff`** (Nativo de Django):
   - Identifica al usuario como personal administrativo/gerencial. Los usuarios operativos (cajeros, facturadores, vendedores) tienen `is_staff = False`.
3. **`perfil.es_admin_sistema`** (Campo del modelo `Perfil` en `usuarios/models.py`):
   - Casilla de verificación *"¿Es Administrador General?"* en el ABM de Usuarios del ERP. Otorga potestad administrativa completa dentro de las pantallas del ERP sin necesidad de ser un superusuario técnico de Django.

**Conclusión para la Anulación**:
Los usuarios operativos que **NO** están autorizados a anular comprobantes tienen `is_staff = False`, `is_superuser = False` y `es_admin_sistema = False`.
Por lo tanto, la condición:
`user.is_superuser or user.is_staff or (hasattr(user, 'perfil') and user.perfil.es_admin_sistema)`
garantiza que **únicamente** los Administradores puedan ver el botón y ejecutar la anulación en el backend.

---

## Summary of Proposed Changes

1. **Listado de Órdenes de Pago**:
   - Mantener la columna `Asiento` en su ubicación actual (columna 9).
   - Convertir el valor `asiento_id` en un enlace/botón interactivo HTMX que abre el modal con el detalle del asiento contable (`detalle_asiento_modal`).
   - Restringir la acción `ANULAR` en la columna de Acciones para que solo aparezca a usuarios Administradores.
   - En el backend (`orden_pago_anular`), validar que el usuario ejecutor sea Administrador, de lo contrario responder con `HTTP 403 Forbidden`.

2. **Listado de Recibos de Cobranza**:
   - Mantener la columna `Asiento` en su ubicación actual (columna 9).
   - Convertir `asiento_id` en botón interactivo HTMX para abrir el modal del asiento contable.
   - Restringir la acción `ANULAR` para usuarios Administradores en plantilla y backend (`recibo_anular`).

3. **Carga de Orden de Pago (Imputaciones Contables Manuales)**:
   - Reemplazar la etiqueta descompuesta `<i class="fas fa-trash"></i>` en `ordenpago_carga.html` por un botón de eliminación en color rojo con un icono SVG de basura visible.

4. **Modal de Detalle de Asiento**:
   - Ajustar el botón de cierre en `detalle_asiento_modal.html` para que utilice `onclick="this.closest('.fixed').remove()"` asegurando su cierre limpio sin importar el ID del contenedor modal.

---

## Proposed Changes File by File

### Tesorería / Backend

#### [MODIFY] [views_listados.py](file:///d:/JM_Soft/erp-ikigai-2/tesoreria/views_listados.py)
- En `orden_pago_anular(request, pk)`:
  - Verificar `is_admin = request.user.is_superuser or request.user.is_staff or (hasattr(request.user, 'perfil') and request.user.perfil.es_admin_sistema)`.
  - Si `not is_admin`: retornar `HttpResponse("Solamente los usuarios administradores pueden anular órdenes de pago.", status=403)`.
- En `recibo_anular(request, pk)`:
  - Verificar `is_admin`.
  - Si `not is_admin`: retornar `HttpResponse("Solamente los usuarios administradores pueden anular recibos.", status=403)`.

---

### Plantillas HTMX y Formularios de Tesorería

#### [MODIFY] [ordenpago_grilla.html](file:///d:/JM_Soft/erp-ikigai-2/templates/tesoreria/partials/ordenpago_grilla.html)
- En la columna 9 (`Asiento`):
  - Si `fila.op.asiento_id` existe, renderizar:
    ```html
    <button type="button"
            hx-get="{% url 'detalle_asiento_modal' fila.op.asiento_id %}"
            hx-target="#modal-container"
            hx-swap="innerHTML"
            class="text-indigo-600 hover:text-indigo-900 hover:underline font-bold transition-colors cursor-pointer"
            title="Ver detalle del asiento contable N° {{ fila.op.asiento_id }}">
        {{ fila.op.asiento_id }}
    </button>
    ```
  - Si es nulo o vacío, mostrar `—`.
- En la columna 10 (`Acciones`):
  - Envolver el botón de Anular con `{% if user.is_superuser or user.is_staff or user.perfil.es_admin_sistema %}`.

#### [MODIFY] [recibo_grilla.html](file:///d:/JM_Soft/erp-ikigai-2/templates/tesoreria/partials/recibo_grilla.html)
- En la columna 9 (`Asiento`):
  - Si `fila.recibo.asiento_id` existe, renderizar:
    ```html
    <button type="button"
            hx-get="{% url 'detalle_asiento_modal' fila.recibo.asiento_id %}"
            hx-target="#modal-container"
            hx-swap="innerHTML"
            class="text-indigo-600 hover:text-indigo-900 hover:underline font-bold transition-colors cursor-pointer"
            title="Ver detalle del asiento contable N° {{ fila.recibo.asiento_id }}">
        {{ fila.recibo.asiento_id }}
    </button>
    ```
  - Si es nulo o vacío, mostrar `—`.
- En la columna 10 (`Acciones`):
  - Envolver el botón de Anular con `{% if user.is_superuser or user.is_staff or user.perfil.es_admin_sistema %}`.

#### [MODIFY] [ordenpago_carga.html](file:///d:/JM_Soft/erp-ikigai-2/templates/tesoreria/ordenpago_carga.html)
- En la tabla de Imputaciones Contables Manuales, reemplazar `<i class="fas fa-trash"></i>` por:
  ```html
  <button type="button" @click="data.imputaciones.splice(index, 1)" title="Eliminar imputación" class="text-red-600 hover:text-red-800 transition-colors p-1 font-bold">
      <svg class="w-4 h-4 inline-block" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
      </svg>
  </button>
  ```

#### [MODIFY] [detalle_asiento_modal.html](file:///d:/JM_Soft/erp-ikigai-2/templates/contable/modals/detalle_asiento_modal.html)
- Reemplazar `onclick="document.getElementById('modal-container-2').innerHTML=''"` por `onclick="this.closest('.fixed').remove()"`.

---

## Verification Plan

### Automated Tests
- Ejecutar suite de pruebas de tesorería:
  `py manage.py test tesoreria.tests.test_reversion`

### Manual Verification
- Ingresar al listado de Órdenes de Pago y verificar que el número de asiento en la columna 9 sea cliqueable y abra el modal con el detalle contable.
- Verificar que el botón de `Anular` solo aparezca si el usuario es Administrador.
- Repetir la verificación en el listado de Recibos de Cobranza.
- Ingresar a Carga de OP -> Imputaciones Contables Manuales y verificar el botón rojo con icono SVG para eliminar filas.
