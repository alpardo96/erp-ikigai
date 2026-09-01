# Configuración de Fecha de Nacimiento para Clientes

El objetivo es agregar una configuración a nivel de Empresa que determine si se debe solicitar o no la **Fecha de Nacimiento** al momento de dar de alta o editar una entidad. Esta regla aplica **únicamente para Clientes**; para Proveedores este dato nunca se debe solicitar.

## Proposed Changes

### 1. Módulo Empresas
Se agregará la configuración en el modelo `Empresa` para que cada razón social tenga la libertad de elegir si activa esta opción.

#### [MODIFY] empresas/models.py
- Agregar el campo `pedir_fecha_nacimiento_cliente = models.BooleanField(default=False, verbose_name="Pedir Fecha Nacimiento en Clientes")` en la clase `Empresa`.

#### [MODIFY] empresas/forms.py
- Agregar el campo `pedir_fecha_nacimiento_cliente` al `EmpresaForm` (tanto en `fields` como en los `widgets` de ser necesario, usando un CheckboxInput) para que pueda gestionarse desde Configuración -> Empresas.

### 2. Módulo Facturación (Vistas y Plantillas)
Se integrará la lectura de esta configuración en el modal de Clientes/Proveedores y se aplicará la lógica en el Frontend.

#### [MODIFY] facturacion/views_htmx.py
- En la vista `cliente_modal`, se obtendrá el objeto `Empresa` a partir de `request.session.get('empresa_id')` y se pasará al contexto el valor de `empresa.pedir_fecha_nacimiento_cliente` bajo el nombre `pedir_fecha_nacimiento`.

#### [MODIFY] templates/facturacion/modals/cliente_modal.html
- Se modificará el contenedor del campo `fecha_nacimiento` asignándole un ID o clase específica.
- En la función de JavaScript `actualizarInterfaz()`, se añadirá la siguiente lógica:
  - Si el `tipo_entidad` seleccionado es Proveedor (2), se ocultará el contenedor de `fecha_nacimiento`.
  - Si el `tipo_entidad` seleccionado es Cliente (1), se mostrará el contenedor **solo si** la variable inyectada desde el contexto `pedir_fecha_nacimiento` es Verdadera (`True`).

## User Review Required
> [!IMPORTANT]
> Confirmar si el valor por defecto para las empresas existentes debe ser `False` (no pedir) o `True` (pedir). En el plan actual se asume `False` para no interrumpir el flujo normal.

## Verification Plan
1. Ejecutar las migraciones de la base de datos para agregar el campo en la tabla de Empresas.
2. Ingresar a la sección de Configuración -> Empresas y verificar que el checkbox exista y guarde su estado.
3. Al dar de alta un Cliente: comprobar que la fecha de nacimiento se oculta o muestra dinámicamente según la configuración.
4. Al dar de alta un Proveedor: comprobar que la fecha de nacimiento siempre esté oculta independientemente de la configuración.
