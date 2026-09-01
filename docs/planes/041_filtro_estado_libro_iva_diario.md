# Plan 041 — Filtro de Estado en Libro Diario / Libro IVA y Explicación de Movimientos Anulados

## Estado: ⏳ Pendiente de Aprobación

## 1. Explicación Técnica y Contable para el Usuario

### ¿Por qué aparecen los movimientos con Estado Anulado?
En la normativa fiscal (ARCA / AFIP) y en los principios de auditoría contable inmutable:
1. **Correlatividad e Integridad de Secuencia:** Los asientos contables y comprobantes fiscales numerados (facturas, notas de crédito/débito, asientos del diario) deben mantener la correlatividad de sus números. Si un movimiento o comprobante se elimina físicamente o se borra de la secuencia, se generarían "huecos" en la numeración, lo cual está prohibido por los reglamentos de fiscalización.
2. **Pista de Auditoría:** Al anular un movimiento, el sistema conserva el registro con la marca `anulado = True` y la fecha de anulación (`fec_anulacion`), impidiendo que afecte los saldos o totales de IVA, pero dejando constancia de que ese número existió y fue anulado.

### ¿Se puede "volver atrás" con la anulación (des-anular)?
**No, la anulación es un proceso definitivo e irreversible.**
- Por reglas contables e impositivas inflexibles, **no existe ni debe existir una función para "des-anular"** o reactivar un asiento/comprobante anulado. 
- Si un movimiento se anuló por error, la buena práctica contable y legal exige volver a cargar o emitir un nuevo asiento/comprobante.

---

## 2. Propuesta de Solución: Filtro de Estado en Libro Diario / Libro IVA

Para responder a la necesidad de no ver los movimientos anulados mezclados con los activos (o poder filtrar explícitamente los anulados para auditoría), se propone incorporar un **Filtro de Estado** en la interfaz de consulta del Libro Diario / IVA.

### Opciones del Filtro de Estado:
- **Sólo Activos (predeterminado):** Muestra únicamente los asientos válidos y vigentes.
- **Sólo Anulados:** Muestra exclusivamente los asientos que fueron anulados (para revisar qué se anuló).
- **Todos (Activos + Anulados):** Muestra el listado completo respetando la secuencia correlativa.

---

## Cambios Propuestos

### Módulo Contable (`contable`)

#### [MODIFY] [views_htmx.py](file:///d:/JM_Soft/erp-ikigai-2/contable/views_htmx.py)
- En `libro_diario_rows(request)`: capturar el parámetro `estado` enviado en la URL/formulario HTMX.
- Aplicar filtrado sobre el queryset `Asiento`:
  - `estado == '1'` (o `'activos'`): `.filter(anulado=False)`
  - `estado == '2'` (o `'anulados'`): `.filter(anulado=True)`
  - `estado == '0'` (o `'todos'`): sin filtro sobre `anulado`.

#### [MODIFY] [libro_diario.html](file:///d:/JM_Soft/erp-ikigai-2/templates/contable/partials/libro_diario.html)
- En el bloque de filtros superiores del Libro Diario, agregar un selector desplegable (`<select name="estado">`):
  - Opción `1`: **Sólo Activos** (seleccionada por defecto).
  - Opción `2`: **Sólo Anulados**.
  - Opción `0`: **Todos (Activos y Anulados)**.

#### [MODIFY] [views_reportes.py](file:///d:/JM_Soft/erp-ikigai-2/contable/views_reportes.py)
- En `exportar_diario` (exportación Excel) y `exportar_diario_pdf_view` (exportación PDF):
  - Capturar el parámetro `estado` de `request.GET`.
  - Aplicar el mismo filtro sobre los asientos antes de generar los documentos Excel o PDF, asegurando que las exportaciones coincidan exactamente con lo que el usuario ve en pantalla.

---

## Plan de Verificación

### Pruebas Manuales
1. **Filtro "Sólo Activos":** Acceder al Libro Diario, presionar "Filtrar" con el estado por defecto ("Sólo Activos") y verificar que no aparezcan filas marcadas como "Anulado".
2. **Filtro "Sólo Anulados":** Cambiar el filtro a "Sólo Anulados" y presionar "Filtrar". Verificar que la grilla únicamente muestre los asientos anulados.
3. **Filtro "Todos":** Seleccionar "Todos" y confirmar que se visualizan asientos activos y anulados con sus respectivas etiquetas de estado.
4. **Exportaciones (Excel y PDF):** Exportar en PDF y Excel bajo cada opción del filtro y comprobar que el reporte generado respete la selección del estado.
