# Plan de Implementación 060: Corrección de Columna de Apertura y Acotamiento de Ejercicio en Sumas y Saldos

Fecha: 2026-08-21

Analizado el código actual en `contable/views_htmx.py` (`_calcular_balance` y `get_balance_context`), confirmamos la necesidad de reestructurar la lógica de cálculo del Balance de Sumas y Saldos para alinearlo rigurosamente con los 4 requerimientos conceptuales indicados.

---

## Análisis Técnico y Cambios Propuestos

### 1. Acotamiento Estricto al Ejercicio Activo
- **Problema actual:** `_calcular_balance` no acotaba la consulta por el `ejercicio_id` activo de la sesión ni restringía el rango de fechas seleccionable (`fecha_desde` / `fecha_hasta`) al inicio y cierre del ejercicio.
- **Solución:**
  - `fecha_desde` se delimitará dentro del rango `[ejercicio.inicio, ejercicio.cierre]`.
  - `fecha_hasta` se delimitará dentro del rango `[fecha_desde, ejercicio.cierre]`.
  - Todas las consultas ORM a `AsientoLinea` filtrarán obligatoriamente por `asientolinea__asiento__ejercicio_id = ejercicio.id` y por las fechas dentro de `[ejercicio.inicio, ejercicio.cierre]`.

### 2. Cálculo de la Columna Apertura (`condic = 5`)
- La columna **Apertura** para cada cuenta contable imputable se calculará como:
  - `Importe Asiento Apertura` = `Debe - Haber` de los asientos con `condic = 5` pertenecientes al `ejercicio_id` activo (siempre que el selector `mostrar_apertura` esté tildado).

### 3. Selector de Inclusión de Asiento de Apertura
- Se incorporará el parámetro y control UI `mostrar_apertura` (por defecto `True` / tildado).
- En `templates/contable/partials/balance.html`, se agregará un checkbox de control `<input type="checkbox" name="mostrar_apertura">` que permitirá habilitar o deshabilitar la inclusión del asiento de apertura.
- Si `mostrar_apertura` está desmarcado (`False`), el asiento de apertura (`condic = 5`) aportará `$0.00` a la columna de Apertura.

### 4. Cálculo de Apertura con `fecha_desde > ejercicio.inicio`
- Si la `fecha_desde` seleccionada es strictly posterior a `ejercicio.inicio`:
  - **Apertura Acumulada** = `(Asiento Apertura condic=5 [si mostrar_apertura=True])` + `(Movimientos Netos [Debe - Haber] entre ejercicio.inicio y fecha_desde - 1 día para condic != 5)`.
- El movimiento del período (`Debe` y `Haber`) comprenderá los asientos registrados con `condic != 5` en el rango de fechas `[fecha_desde, fecha_hasta]`.
- **Saldo Final** = `Apertura + Debe_periodo - Haber_periodo`.

---

## Archivos a Modificar

### [MODIFY] [views_htmx.py](file:///d:/JM_Soft/erp-ikigai-2/contable/views_htmx.py)
- Modificar `get_balance_context(request)` para procesar `mostrar_apertura` y delimitar estrictamente `fecha_desde` y `fecha_hasta` al `ejercicio.inicio` y `ejercicio.cierre`.
- Modificar `_calcular_balance(...)` para incorporar `ejercicio` obligatorio, filtrar por `ejercicio_id`, diferenciar `q_apertura_condic5`, `q_movimientos_previos` (cuando `fecha_desde > ejercicio.inicio`) y `q_periodo`, agregando la acumulación correcta a la columna `apertura`.

### [MODIFY] [balance.html](file:///d:/JM_Soft/erp-ikigai-2/templates/contable/partials/balance.html)
- Agregar el campo hidden `filtros_aplicados` y el checkbox de UI `<input type="checkbox" name="mostrar_apertura">` (con label *"Incluir Asiento de Apertura"*).

---

## Plan de Pruebas y Verificación

1. **Pruebas de Vistas / HTTP:**
   - Ejecutar la suite de pruebas contables para asegurar no romper tests existentes (`py manage.py test contable`).
   - Agregar pruebas unitarias específicas para verificar los 4 puntos.

2. **Verificación Manual:**
   - Cargar la vista de Balance de Sumas y Saldos por HTMX y verificar los valores con el checkbox activado/desactivado y cambiando la fecha desde.
