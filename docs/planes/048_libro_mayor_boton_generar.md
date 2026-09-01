# Plan 048 — Libro Mayor: Selección de Columnas (Pantalla, Excel y CSV), Botón Generar y Valores Predeterminados

## Estado: ✅ Aprobado por el usuario (15/08/2026)

## Descripción de las Mejoras

1. **Selección Dinámica de Columnas (Pantalla, Excel y CSV):**
   - El usuario podrá elegir qué columnas desea visibilizar en la grilla del Libro Mayor.
   - Las columnas seleccionadas se conservan al exportar el reporte a **Excel** (en formato de Tabla estructurada) y a un nuevo formato **CSV** (para integrar con otras aplicaciones).
   - **Columnas predeterminadas activas (10 campos):** `asiento_id`, `fecha`, `concepto`, `cuenta_id`, `cuenta`, `debe`, `haber`, `saldo`, `condic`, `sucursal_id`.
   - **`leyenda`:** Predeterminado en **No** (opcional para activar).
   - **Columnas opcionales disponibles para agregar:**
     - De `cble_asiento_enc`: `numero_diario`, `monto` (monto total del asiento), `modulo`, `cli_pro` (cliente/proveedor del asiento), `fec_vto` (vencimiento), `anulado`, `fec_anulacion`, `ejercicio`, `sesion_caja`.
     - De `cble_asiento_mov`: `orden` (orden de línea), `leyenda`, `divisa`, `cotizacion`, `debe_divisa`, `haber_divisa`, `fec_vto` (vencimiento de línea), `cli_pro` (auxiliar de línea).
     - De `cble_cuentas`: `jerarquia`, `tipo` (A, P, N, R), `imputable`, `codigo_legacy`, `tipo_disponibilidad`, `rg_830`.

2. **Valores Predeterminados de Condición (`condic`):**
   - En la pantalla principal y en el modal, los checkboxes de condición vendrán tildados por defecto en: **1 (Real)**, **2 (Presupuestado)** y **5 (Apertura)**.

3. **Sin Ejecuciones Automáticas / Botón "Consultar" / "Generar Reporte":**
   - Al abrir la pantalla del Libro Mayor o el modal de una cuenta, **NO** se ejecutará ninguna consulta pesada a la base de datos automáticamente (`hx-trigger="load"` eliminado).
   - La consulta se disparará **únicamente** cuando el usuario revise sus parámetros y presione el botón **"Consultar"** (en la pantalla) o **"Generar Reporte"** (en el modal).

---

## Solución Detallada

### 1. Definición de Catálogo de Columnas (`contable/services/reportes_excel.py` / `contable/views_htmx.py`)
Se estructurará una lista maestra de columnas configurables con sus claves, nombres y visibilidad por defecto:
- `asiento_id`: ID Asiento (Default: Sí)
- `fecha`: Fecha (Default: Sí)
- `concepto`: Concepto (Default: Sí)
- `leyenda`: Leyenda (Default: No)
- `cuenta_id`: ID Cuenta / Código (Default: Sí)
- `jerarquia`: Jerarquía Cuenta (Default: No)
- `cuenta`: Nombre Cuenta (Default: Sí)
- `tipo`: Tipo Cuenta (Default: No)
- `debe`: Debe (Default: Sí)
- `haber`: Haber (Default: Sí)
- `saldo`: Saldo Acumulado (Default: Sí)
- `condic`: Condición (Default: Sí)
- `sucursal`: Sucursal (Default: Sí)
- *... y el resto de campos opcionales especificados.*

### 2. Selector de Columnas en Interfaz (HTML + Alpine.js)
En `templates/contable/partials/libro_mayor.html` y `templates/contable/modals/mayor_cuenta_modal.html`:
- Se agrega un menú desplegable interactivo de configuración de columnas (**"Columnas"**).
- Permite tildar/destildar campos individuales o aplicar presets.
- La lista de columnas seleccionadas se envía en el formulario GET (`columnas=asiento_id&columnas=fecha...`).

### 3. Exportación a CSV (`exportar_mayor_csv`)
En `contable/views_reportes.py`:
- Nuevo endpoint `exportar_mayor_csv(request)` que genera un archivo CSV (`text/csv` con BOM UTF-8 `\ufeff` para apertura limpia en Excel/PowerBI).
- Exporta únicamente las columnas seleccionadas por el usuario con encabezados claros y delimitador `;`.

### 4. Exportación a Excel (`exportar_mayor_excel`)
- En `contable/services/reportes_excel.py`:
  - Se adapta `exportar_mayor_excel` para construir dinámicamente los encabezados y datos según las `columnas` elegidas.
  - Formatea la grilla como **Tabla de Excel (`openpyxl.worksheet.table.Table`)** permitiendo filtros de Excel en las columnas.

---

## Cambios Propuestos

### Módulo Contable (`contable`)

#### [MODIFY] [views_htmx.py](file:///d:/JM_Soft/erp-ikigai-2/contable/views_htmx.py)
- `get_mayor_context`: Adaptar el armado de movimientos para incluir los campos extendidos de `Asiento`, `AsientoLinea` y `Cuenta`.
- `libro_mayor_rows`: Recibir lista de `columnas` a renderizar y pasarla a la plantilla.
- `mayor_cuenta_modal`: Pasar `condics_seleccionados` por defecto con `[1, 2, 5]`.

#### [MODIFY] [views_reportes.py](file:///d:/JM_Soft/erp-ikigai-2/contable/views_reportes.py)
- Actualizar `exportar_mayor` (Excel) para aceptar `columnas` seleccionadas.
- Nuevo endpoint `exportar_mayor_csv` para descarga en formato CSV.

#### [MODIFY] [urls.py](file:///d:/JM_Soft/erp-ikigai-2/contable/urls.py)
- Agregar la ruta: `path('mayor/exportar-csv/', exportar_mayor_csv, name='exportar_mayor_csv')`.

#### [MODIFY] [libro_mayor.html](file:///d:/JM_Soft/erp-ikigai-2/templates/contable/partials/libro_mayor.html)
- Agregar el selector desplegable de columnas.
- Agregar el botón **CSV** junto a PDF y Excel.
- Predeterminar checkboxes de `condic` en 1, 2 y 5.

#### [MODIFY] [mayor_cuenta_modal.html](file:///d:/JM_Soft/erp-ikigai-2/templates/contable/modals/mayor_cuenta_modal.html)
- Agregar la barra de verificación de parámetros con el botón **"Generar Reporte"**, selector de columnas y botón **CSV**.
- Predeterminar checkboxes de `condic` en 1, 2 y 5.

---

## Plan de Verificación

### Pruebas Automatizadas
- Ejecutar la suite de pruebas del módulo contable:
  `.\venv\Scripts\python.exe manage.py test contable.tests`

### Pruebas Manuales
1. **Selección de Columnas:**
   - Desplegar el selector de columnas y ocultar/mostrar campos (ej. agregar `jerarquia` y `tipo`).
   - Hacer clic en "Consultar" y verificar que la tabla en pantalla muestre únicamente las columnas elegidas.
2. **Exportaciones Excel y CSV:**
   - Hacer clic en el botón **CSV** y abrir el archivo generado en un editor de texto o Excel; verificar delimitadores y columnas.
   - Hacer clic en el botón **Excel** y verificar que genere el `.xlsx` tipo tabla con las columnas exactas elegidas.
3. **Verificación de `condic` predeterminados:**
   - Confirmar que al abrir el formulario o modal, los checkboxes `1 - Real`, `2 - Presupuestado` y `5 - Apertura` vienen tildados.
4. **Modal:**
   - Verificar que no auto-ejecuta al abrir y que el botón "Generar Reporte" funciona correctamente.
