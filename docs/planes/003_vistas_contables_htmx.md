# Plan 003 — Vistas Contables HTMX

## Estado: ✅ Completado (Fase 5A del walkthrough)

## Descripción del Objetivo
Crear las interfaces de consulta contable (Libro Diario, Mayor, Balance de Sumas y Saldos) y la pantalla de carga manual de Asientos Contables, integradas en el módulo contable existente (`/contable/`) usando el patrón ya establecido: Tailwind CSS + HTMX + Alpine.js.

## Arquitectura Existente (lo que ya tenemos)
- **`contable/index.html`**: Layout con sidebar lateral (tabs) + área de contenido `#contable-content`.
- **Tabs existentes**: "Cuentas Contables" y "Cuentas Bancarias" (ya funcionan con HTMX).
- **Patrón de modales**: Se inyectan en `#modal-container` del `base.html`, con backdrop y triggers HTMX.
- **Servicio `crear_asiento()`**: Ya validado y testeado (partida doble, ejercicio, cuentas imputables).

## Cambios Propuestos

### 1. Sidebar: Nuevas pestañas en `contable/index.html`
Agregar 4 tabs nuevos al menú lateral del módulo contable:
- **Libro Diario** → `?tab=diario`
- **Libro Mayor** → `?tab=mayor`
- **Balance de Sumas y Saldos** → `?tab=balance`
- **Carga Manual de Asiento** → `?tab=asiento_nuevo`

### 2. Vista principal (`contable/views.py`)
Ampliar `ContableIndexView.get()` para manejar los nuevos tabs y devolver los partials correspondientes.

### 3. Vistas HTMX (`contable/views_htmx.py`)
- **`libro_diario(request)`**: Lista paginada de asientos del ejercicio activo con filtros de fecha (desde/hasta). Cada fila expandible con HTMX para ver las líneas del asiento.
- **`libro_mayor(request)`**: Filtro por cuenta contable + rango de fechas. Muestra movimientos agrupados con saldo progresivo.
- **`balance_sumas_saldos(request)`**: Todas las cuentas imputables con sus totales Debe/Haber y Saldo Deudor/Acreedor. Filtro por fecha de corte.
- **`asiento_form(request)`**: Modal o pantalla para carga manual de asientos con líneas dinámicas (agregar/quitar filas con HTMX/Alpine.js). Al guardar, llama al servicio `crear_asiento()`.
- **`detalle_asiento(request, id)`**: Partial que muestra las líneas de un asiento para expandir en el Libro Diario.
- **`anular_asiento(request, id)`**: Endpoint POST para anular un asiento desde la UI.

### 4. Templates (Partials y Modales)
- `templates/contable/partials/libro_diario.html` — Tabla con filtros y filas expandibles.
- `templates/contable/partials/libro_diario_rows.html` — Filas de asientos (recargable por HTMX al filtrar).
- `templates/contable/partials/detalle_asiento.html` — Líneas de un asiento (se inyecta al expandir la fila).
- `templates/contable/partials/libro_mayor.html` — Tabla con selector de cuenta y saldo progresivo.
- `templates/contable/partials/libro_mayor_rows.html` — Filas de movimientos del mayor.
- `templates/contable/partials/balance.html` — Tabla resumen del balance.
- `templates/contable/modals/asiento_form.html` — Modal de carga manual con líneas dinámicas.

### 5. URLs (`contable/urls.py`)
```
contable/diario/              → libro_diario
contable/diario/filas/        → libro_diario_rows (HTMX)
contable/diario/<id>/detalle/ → detalle_asiento (HTMX)
contable/diario/<id>/anular/  → anular_asiento (POST)
contable/mayor/               → libro_mayor
contable/mayor/filas/         → libro_mayor_rows (HTMX)
contable/balance/             → balance_sumas_saldos
contable/asientos/crear/      → asiento_form (GET/POST)
```

### 6. Forms (`contable/forms.py`)
- **`AsientoEncForm`**: Campos: fecha, concepto, condición, cliente/proveedor (opcional).
- **`AsientoLineaForm`**: Campos: cuenta (select con búsqueda), debe, haber, leyenda.

## Verificación
- Navegación fluida entre todas las pestañas del módulo contable sin recargar la página.
- Carga manual de un asiento balanceado y visualización inmediata en el Libro Diario.
- Expandir filas del Libro Diario para ver las líneas del asiento.
- Filtrar el Mayor por una cuenta y verificar que el saldo progresivo cuadre.
- Balance de Sumas y Saldos: suma total de Deudores = suma total de Acreedores.
