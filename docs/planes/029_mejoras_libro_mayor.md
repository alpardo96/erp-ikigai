# Plan de Implementación: Mejoras en el Libro Mayor

Este plan detalla los cambios necesarios para mejorar el filtro y la visualización del Libro Mayor, basándose en la funcionalidad del sistema FoxPro anterior y las reglas del nuevo ERP.

## Cambios Propuestos

### 1. `contable/views.py` (LibroMayorView)
Se actualizará el contexto inicial de la vista para enviar los datos necesarios para pre-poblar los filtros:
- **Fechas por Defecto:** Se obtendrá el `Ejercicio` activo de la empresa para enviar `fecha_inicio` y `fecha_cierre`.
- **Cuentas Desde/Hasta:** Se enviarán la primera y la última cuenta con `imputable=1` para marcarlas como predeterminadas.
- **Entidades:** Se enviará el listado de `ClienteProveedor` asociados a la empresa para el filtro de Cliente/Proveedor.

### 2. `templates/contable/partials/libro_mayor.html` (Formulario de Filtros)
Se rediseñará la barra de filtros para incluir:
- **Cuenta Desde y Cuenta Hasta:** Dos selectores de cuentas. Por defecto tomarán la primera y última cuenta imputable.
- **Fechas:** Se pre-cargarán vía JavaScript o HTML las fechas del ejercicio (Desde: inicio de ejercicio, Hasta: menor entre hoy y cierre).
- **Condición (Condic):** Se agregarán checkboxes para poder tildar las condiciones (1, 2 y 3).
- **Cliente / Proveedor:** Selector para poder filtrar los movimientos por una entidad particular.
- Se ajustará el script `getFiltrosMayorURL()` para enviar correctamente todos los nuevos parámetros (rangos, arrays de condiciones, entidad).

### 3. `contable/views_htmx.py` (get_mayor_context y libro_mayor_rows)
- **Rango de Cuentas:** En lugar de recibir un único `cuenta_id`, la vista `libro_mayor_rows` recibirá el rango y buscará todas las cuentas que pertenezcan a las jerarquías comprendidas entre `cuenta_desde` y `cuenta_hasta`.
- **Iteración:** Se iterará sobre cada cuenta encontrada, ejecutando la lógica de cálculo de saldos y movimientos (`get_mayor_context`).
- **Nuevos Filtros:** En `get_mayor_context`, se agregará el filtrado por `cli_pro_id` y por `condic` sobre los `AsientoLinea` y `Asiento`.
- El contexto resultante será una lista de diccionarios (un diccionario por cada cuenta contable solicitada).

### 4. `templates/contable/partials/libro_mayor_rows.html` (Vista de Tabla)
- Se adaptará la plantilla para iterar sobre la lista de cuentas.
- Por cada cuenta, se imprimirá una fila separadora a modo de encabezado (ej. `[1.1.1.01] - CAJA`).
- Luego se imprimirán los movimientos de esa cuenta (con su saldo anterior y acumulados).
- La funcionalidad de hacer click en el asiento para ver el detalle en modal (`detalle_asiento_modal`) ya está implementada y se mantendrá para cada renglón.

### 5. `contable/views_reportes.py` (Exportaciones PDF y Excel)
- Se ajustarán las funciones `exportar_mayor` y `exportar_mayor_pdf_view` para que reciban y procesen el rango de cuentas y los nuevos filtros (condición, fechas, entidad).
- El reporte resultante agrupará los movimientos por cuenta, tal como la vista en pantalla.

## Tareas de Validación (Verification Plan)
- Verificar que el cálculo de los saldos anteriores tome en cuenta correctamente los filtros aplicados.
- Confirmar que al filtrar por Cliente/Proveedor, el saldo arrastrado coincida con el histórico de esa entidad en esa cuenta.
- Validar las exportaciones a PDF y Excel con los nuevos parámetros múltiples.

> [!IMPORTANT]
> **Revisión del Usuario Requerida**
> Por favor, confirmame si estás de acuerdo con este plan. Una vez aprobado, guardaré una copia del plan en `docs/planes/` (siguiendo las reglas del proyecto) y procederé con los cambios en el código.
