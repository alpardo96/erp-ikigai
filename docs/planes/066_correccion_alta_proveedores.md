# Plan de Implementación: Corrección del Alta de Proveedores y Reactividad Comercial/Fiscal

Permitir la creación y edición fluida de proveedores en el formulario modal `ClienteProveedor`, eliminando el rebote automático a rol "Cliente" provocado por scripts de frontend y previniendo la conversión silenciosa a rol Cliente en las reglas del modelo backend.

## User Review Required

> [!IMPORTANT]
> **Regla de Negocio AFIP/ARCA para Proveedores:**
> Un proveedor en el ERP Ikigai **no puede ser registrado como "Consumidor Final" ni con Tipo de Documento "99 - Sin Identificar"**. Todo proveedor debe poseer una condición fiscal ante el IVA válida (Responsable Inscripto, Monotributo, Exento) y un CUIT de 11 dígitos.
> Al cambiar el selector de *Rol Comercial* a **Proveedor**, el formulario cambiará automáticamente la Condición IVA a `RESPONSABLE INSCRIPTO` y el Tipo de Documento a `80 - CUIT`.

## Open Questions

- Ninguna por el momento. La solución respeta las reglas contables y fiscales del proyecto ERP Ikigai 2.

## Proposed Changes

---

### Módulo Facturación (Frontend / Plantilla Modal)

#### [MODIFY] [cliente_modal.html](file:///d:/JM_Soft/erp-ikigai-2/templates/facturacion/modals/cliente_modal.html)

- **Eliminar el bucle de reconversión a Cliente**: En la función `actualizarInterfaz()` (línea ~527), remover la condición que asignaba `tipoEntidadSelect.value = '1'` cuando `docValue == '99'`.
- **Sincronización Automática de Rol Comercial**:
  - Al cambiar `tipo_entidad` a `2` (Proveedor):
    - Si `condicion_iva` era `CONSUMIDOR FINAL`, actualizar automáticamente a `RESPONSABLE INSCRIPTO`.
    - Si `tipo_documento` era `99` (Sin Identificar), actualizar automáticamente a `80` (CUIT).
    - Notificar a la instancia de Alpine.js (`condicionIva = 'RESPONSABLE INSCRIPTO'`, `tipoDoc = '80'`) para habilitar la máscara y obligatoriedad de CUIT (11 dígitos).

---

### Módulo Facturación (Formularios Backend)

#### [MODIFY] [forms.py](file:///d:/JM_Soft/erp-ikigai-2/facturacion/forms.py)

- **Validación Estricta en `ClienteProveedorForm.clean()`**:
  - Si `tipo_entidad == 2` (Proveedor):
    - Verificar que `condicion_iva` sea distinta de `CONSUMIDOR FINAL`. Si es Consumidor Final, agregar error de campo: `"Un proveedor debe ser Responsable Inscripto, Monotributo o Exento."`
    - Verificar que `tipo_documento` sea `80` (o `86`) y que el `cuit` contenga exactamente 11 dígitos numéricos.

---

### Módulo Facturación (Modelo de Datos)

#### [MODIFY] [models.py](file:///d:/JM_Soft/erp-ikigai-2/facturacion/models.py)

- **Proteger `ClienteProveedor.save()`**:
  - Condicionar la reescritura de `tipo_entidad = 1` únicamente a cuando la entidad NO haya sido explícitamente guardada como Proveedor (`tipo_entidad != 2`).

---

### Documentación e Histórico de Planes

#### [NEW] [066_correccion_alta_proveedores.md](file:///d:/JM_Soft/erp-ikigai-2/docs/planes/066_correccion_alta_proveedores.md)

- Copia estática indexada del plan en la carpeta de historial de planes `docs/planes/`.

---

## Verification Plan

### Automated Tests
- Ejecutar pruebas unitarias de facturación:
  ```powershell
  py manage.py test facturacion
  ```

### Manual Verification
1. Abrir la ventana de **Alta Cliente / Proveedor** desde `/clientes/` o desde el botón **"+"** en Carga de Compras.
2. Cambiar el selector **Rol Comercial** a **Proveedor**.
3. Comprobar que el desplegable **permanece en Proveedor** y que la Condición IVA se actualiza a `RESPONSABLE INSCRIPTO` y el Documento a `80 - CUIT`.
4. Ingresar una Razón Social y CUIT válido (11 dígitos), seleccionar cuentas contables o guardar.
5. Confirmar que el Proveedor se guarda correctamente con `tipo_entidad = 2` y aparece inmediatamente en los listados de Proveedores y en los buscadores de Compras y Órdenes de Pago.
