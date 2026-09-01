# Plan 072: Columnas de Armería y Campo 'Es Policía' en Clientes y Proveedores (Combobox)

## Descripción
Este cambio extiende la gestión de Clientes y Proveedores en empresas cuya actividad es **Armería** (`tipo_actividad == 'ARMERIA'`), incorporando:
1. **Selector de Columnas y Grilla Principal:** Selección y visualización de columnas específicas de armería (`CLU`, `Vencimiento CLU` y `Es Policía`) en la tabla de Clientes y Proveedores (`clientes_index.html` y `cliente_table_rows.html`).
2. **Formulario y Modal de Alta/Edición (Combobox 'Es Policía'):** Dado que "Es Policía" es un dato crítico y sensible por concesiones de ropa oficial y normativas, se implementa como un **selector desplegable (Combobox / Select)** en lugar de un checkbox, con opciones explícitas (`NO` y `SÍ`) donde `NO` es el valor predeterminado.
3. **Exportación a Excel:** Extensión del servicio de exportación Excel de clientes (`clientes_excel.py`) para incluir las columnas de CLU, Vencimiento CLU y Es Policía cuando la empresa activa sea de tipo Armería.
4. **Optimización ORM:** Incorporación de `select_related('armeria')` en la consulta del listado y búsqueda para evitar problemas de N+1 queries.

---

## Archivos a Modificar

### Backend & Formularios
- `facturacion/forms.py`: Inclusión de `es_policia` como `TypedChoiceField` (Select) en `ExtensionArmeriaForm`.
- `facturacion/views.py`: Adición de `select_related('armeria')` en `ClientesProveedoresIndexView`.
- `facturacion/views_htmx.py`: Adición de `select_related('armeria')` en `buscar_clientes`.
- `facturacion/views_reportes.py` y `facturacion/services/clientes_excel.py`: Soporte de columnas Armería en exportación Excel.

### Frontend / Plantillas
- `templates/facturacion/modals/cliente_modal.html`: Selector desplegable `es_policia` en la sección "Registro de Armería".
- `templates/facturacion/clientes_index.html`: Checkboxes de columnas `col-clu`, `col-clu-vto`, `col-policia` en el dropdown y encabezados de tabla `<th>` para empresas de tipo Armería.
- `templates/facturacion/partials/cliente_table_rows.html`: Celdas `<td>` correspondientes a las 3 columnas de Armería.

---

## Plan de Pruebas
- Pruebas automatizadas de renderizado del formulario e inserción de registros con `es_policia=True` / `False`.
- Verificación manual de visibilidad de columnas y exportación Excel en entorno con empresa de tipo Armería.
