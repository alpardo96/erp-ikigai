# Plan 017 — Asignación de Cuentas Predeterminadas para Clientes y Proveedores

## Objetivo
Configurar cuentas contables predeterminadas (Patrimonial y Resultado) sugeridas automáticamente al crear un Cliente o Proveedor, según la lógica del sistema VFP heredado (`oApp.cta_cli`, `oApp.cta_vta`, `oApp.cta_prov`), extraídas de la tabla `ParametrosContables`. Además, se reemplazará la entrada manual del ID de la cuenta por un buscador modal amigable e interactivo sobre la tabla de Cuentas Contables.

## Lógica de Asignación
- **Cliente (`tipo_entidad = 1`)**:
  - `cta_pat` (Patrimonial) sugerida: `cta_clientes_default` (equivale a `oApp.cta_cli`).
  - `cta_res` (Resultado) sugerida: `cta_ventas` (equivale a `oApp.cta_vta`).
- **Proveedor (`tipo_entidad = 2`)**:
  - `cta_pat` (Patrimonial) sugerida: `cta_proveedores_default` (equivale a `oApp.cta_prov`).

## User Review Required
> [!IMPORTANT]
> - ¿Estás de acuerdo con que cuando el usuario cambie el tipo de entidad (Cliente a Proveedor y viceversa) dentro del formulario de Alta, el sistema actualice dinámicamente las cuentas sugeridas en la pantalla mediante JavaScript, o prefieres que solo se sugieran al abrir la ventana por primera vez?
> - Las cuentas predeterminadas se buscarán en la tabla `ParametrosContables` (que deberás configurar previamente para la empresa). Si no están configuradas, se sugerirá dejar las cuentas en blanco (0) hasta que se seleccionen manualmente.

## Proposed Changes

### `facturacion/forms.py`
#### [MODIFY] facturacion/forms.py
- Modificar el método `__init__` de `ClienteProveedorForm` para:
  - Leer `ParametrosContables` de la empresa actual (requerirá recibir `empresa_id` en el `kwargs` o extraerlo del `request`).
  - Cargar los `cuenta_id` y `cuenta_nombre` de las cuentas por defecto y pasarlas como datos (dataset o variables) para el frontend.
  - Al editar un cliente existente, buscar el nombre de las cuentas guardadas (`cta_pat` y `cta_res`) para mostrarlas correctamente en la interfaz (ya que en la BD se guarda solo el número ID).

### Modal y Búsqueda de Cuentas
#### [NEW] templates/facturacion/modals/buscador_cuentas.html
- Crear un modal (similar a los de tesorería) para buscar cuentas contables.
- Contendrá un input de búsqueda con HTMX que apunte a la vista de búsqueda de cuentas.

#### [NEW] templates/facturacion/partials/cuentas_search_results.html
- Crear la fila de resultados de la búsqueda de cuentas.
- Al hacer clic, disparará un evento de Alpine.js (`cuentaSeleccionada`) con el ID y el Nombre de la cuenta, y cerrará el modal.

### `facturacion/views_htmx.py`
#### [MODIFY] facturacion/views_htmx.py
- Modificar la vista de creación/edición de cliente (`cliente_modal`) para pasar el `empresa_id` al formulario.
- Añadir vista ligera `buscar_cuentas_facturacion` para que el modal de clientes pueda consultar las cuentas filtrando por empresa.

### Vista del Formulario
#### [MODIFY] templates/facturacion/modals/cliente_modal.html
- Envolver la sección de cuentas con Alpine.js (`x-data="{ ctaPatId: '', ctaPatNombre: '', ctaResId: '', ctaResNombre: '' }"`).
- Reemplazar los inputs estándar de `cta_pat` y `cta_res` (que actualmente son de texto libre) por inputs visuales de solo lectura con un botón de "lupa" para abrir el `buscador_cuentas.html`.
- Incorporar la lógica JavaScript/Alpine para que al cambiar `tipo_entidad` en el selector principal, se pisen los valores de cuenta sugeridos utilizando los valores extraídos desde el Formulario (Parámetros Contables).

## Verification Plan
### Pruebas Manuales
1. Configurar `ParametrosContables` para la Empresa de prueba.
2. Ir a Alta de Cliente y verificar que se sugieren automáticamente la cuenta Patrimonial de Cliente y de Resultado de Venta configuradas.
3. Cambiar en el combo a "Proveedor" y verificar que la cuenta Patrimonial cambie automáticamente a la de Proveedores y la de resultado se limpie.
4. Usar el botón de la lupa en `cta_pat` y `cta_res`, abrir el modal de cuentas, buscar "Caja" o "Ventas", seleccionarla y verificar que se cierra el modal y se actualiza el ID y el nombre en el formulario principal.
5. Guardar y verificar que los IDs de las cuentas se persisten correctamente en la tabla `ClienteProveedor`.
