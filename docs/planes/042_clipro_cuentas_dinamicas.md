# Lógica Dinámica de Cuentas Contables en CLIPRO según Rol Comercial

## Contexto

El formulario de alta/edición de Cliente/Proveedor ([cliente_modal.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/facturacion/modals/cliente_modal.html)) actualmente permite editar libremente los campos `cta_pat` y `cta_res` sin importar el rol comercial (`tipo_entidad`). Se necesita aplicar reglas de negocio dinámicas que bloqueen/desbloqueen estos campos según el rol seleccionado.

## Reglas de Negocio

| Rol | `cta_pat` (Patrimonial) | `cta_res` (Resultado) |
|-----|------------------------|----------------------|
| **Cliente** (tipo=1) | 🔒 Bloqueado. Se auto-asigna `cta_clientes_default_id` de los parámetros contables. Se muestra pero no se puede editar. | 🔒 Bloqueado. Se auto-asigna `cta_ventas_id` de los parámetros contables. Se muestra pero no se puede editar. |
| **Proveedor** (tipo=2) | 🔓 Desbloqueado. Se sugiere `cta_proveedores_default_id` como valor inicial pero se permite cambiar. | 🔓 Desbloqueado. Se pide siempre (sin default). El usuario debe elegir manualmente. |

> [!IMPORTANT]
> **Pre-requisito**: Los parámetros contables de la empresa deben estar configurados para que los defaults funcionen. Si no están configurados, los campos quedarán vacíos y se mostrará una advertencia visual.

## Comportamiento Detallado

### Alta (nuevo registro, sin PK)
1. Se carga el modal con `tipo_entidad = 1 (Cliente)` por defecto.
2. Los campos `cta_pat` y `cta_res` se rellenan automáticamente con los defaults del parámetro contable y se **bloquean** (read-only + sin botón de búsqueda).
3. Si el usuario cambia a `Proveedor (tipo=2)`, los campos se **desbloquean**:
   - `cta_pat` se pre-rellena con `cta_proveedores_default_id` pero permite cambio.
   - `cta_res` se limpia y se pide al usuario que elija.
4. Si vuelve a `Cliente`, se vuelven a bloquear con los defaults.

### Edición (registro existente, con PK)
1. Si `tipo_entidad = 1 (Cliente)`: los campos muestran las cuentas ya guardadas pero están **bloqueados**. No se aplican defaults sobre valores existentes.
2. Si `tipo_entidad = 2 (Proveedor)`: los campos muestran las cuentas ya guardadas y están **desbloqueados** para edición.
3. Si el usuario cambia el rol comercial de un registro existente, se aplica la misma lógica de bloqueo/desbloqueo pero **no se sobrescriben** los valores ya guardados — solo se ajusta si pueden editar o no.

### Parámetros no configurados
- Si `ParametrosContables` no existe para la empresa, se muestra un aviso amarillo (alerta) indicando que deben configurarse los parámetros contables.
- Los campos quedan visibles pero vacíos. En modo Cliente siguen bloqueados (sin valor). En modo Proveedor siguen editables.

---

## Cambios Propuestos

### Template (Frontend dinámico con Alpine.js)

#### [MODIFY] [cliente_modal.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/facturacion/modals/cliente_modal.html)

Cambios en la sección de cuentas contables (líneas ~214-305):

1. **Agregar propiedad reactiva `tipo`** al bloque `x-data` de cuentas: vinculada al select `tipo_entidad`, se sincroniza con `@cambio-tipo-entidad.window`.

2. **Propiedad `locked`** (computed/derivada): `true` cuando `tipo == '1'` (Cliente), `false` cuando `tipo == '2'` (Proveedor).

3. **Propiedad `paramsFaltantes`**: `true` si `defaultCliId` está vacío (indica que los parámetros contables no están configurados).

4. **Sobre los inputs de `cta_pat` y `cta_res`**: 
   - Agregar `x-bind:class` para cambiar visualmente entre bloqueado (fondo gris, candado) y editable (fondo blanco).
   - El botón de búsqueda (🔍) se oculta con `x-show="!locked"` cuando es Cliente.
   - Cuando está desbloqueado (Proveedor), el input deja de tener estilo `cursor-not-allowed`.

5. **Alerta de parámetros no configurados**: Un `<div>` condicional con `x-show="paramsFaltantes"` que muestra un mensaje de advertencia.

6. **Ajuste en `aplicarDefaults()`**: 
   - Ya existe y funciona correctamente para alta (sin PK).  
   - Se mantiene sin cambios — solo se aplica defaults al crear nuevo.

7. **Ajuste en el script final** (líneas ~408-473):
   - En `actualizarInterfaz()`, se despacha el evento `cambio-tipo-entidad` que Alpine ya escucha.
   - No hace falta HTMX adicional aquí porque la lógica es 100% frontend (Alpine.js ya tiene los datos de defaults inyectados desde Django).

### Backend (Vista)

#### [MODIFY] [views_htmx.py](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/facturacion/views_htmx.py)

Cambios en la función `cliente_modal()` (líneas ~203-288):

1. **En el POST** (línea ~211): Antes de guardar, si `tipo_entidad == 1` (Cliente), **forzar** `cta_pat` y `cta_res` con los valores de los parámetros contables, ignorando lo que venga del formulario. Esto es una validación del lado servidor para evitar manipulación del DOM.

2. **Pasar flag `params_configurados`** al contexto del template para que el frontend pueda mostrar la alerta.

### Backend (Form)

#### [MODIFY] [forms.py](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/facturacion/forms.py)

1. **En `clean()`** (línea ~217-222): Si `tipo_entidad == 1`, forzar `cta_pat` y `cta_res` desde los parámetros contables de la empresa (doble validación servidor).

---

## Resumen de Archivos a Modificar

| Archivo | Tipo de Cambio | Impacto |
|---------|---------------|---------|
| `templates/facturacion/modals/cliente_modal.html` | Lógica Alpine.js para lock/unlock | Solo visual/UX |
| `facturacion/views_htmx.py` | Forzar cuentas en POST para clientes | Validación servidor |
| `facturacion/forms.py` | Validación en clean() | Seguridad datos |

## Verificación

### Manual
- Crear un nuevo **Cliente**: verificar que `cta_pat` y `cta_res` se auto-rellenan y están bloqueados.
- Crear un nuevo **Proveedor**: verificar que `cta_pat` tiene default editable y `cta_res` está vacío y editable.
- Alternar entre Cliente/Proveedor en el modal y verificar el comportamiento dinámico.
- Editar un cliente existente: verificar campos bloqueados con valores existentes.
- Editar un proveedor existente: verificar campos desbloqueados con valores existentes.
- Verificar con parámetros contables NO configurados: debe mostrar alerta.

> [!NOTE]
> **No se requieren migraciones de base de datos.** Los cambios son puramente de lógica de presentación (frontend) y validación (backend). Los campos `cta_pat` y `cta_res` ya existen en el modelo `ClienteProveedor`.

## Pregunta Abierta

> [!IMPORTANT]
> **¿Qué pasa con los clientes ya existentes que tienen `cta_pat` o `cta_res` distinto al default?**
> Cuando se editen clientes existentes, los campos estarán bloqueados pero mostrarán los valores que ya tienen guardados (no se sobreescriben con los defaults). ¿Está bien este comportamiento o prefieres que al guardar un cliente existente también se fuercen los defaults?
