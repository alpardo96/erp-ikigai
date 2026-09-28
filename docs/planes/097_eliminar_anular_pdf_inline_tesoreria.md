# Plan de Implementación: 097 - Eliminación de Acción Anular y Visualización PDF Inline en Tesorería

**Fecha:** 2026-09-28  
**Autor:** Codex / Antigravity  
**Estado:** Aprobado / En ejecución  

---

## 1. Contexto y Objetivos

En el módulo de Tesorería (`tesoreria`):
1. **Eliminar el botón de "Anular" y toda su lógica web/endpoints** en el **Listado de Recibos** y **Listado de Órdenes de Pago**. Esta funcionalidad no es viable operativamente y debe removerse de la interfaz de usuario, rutas y vistas.
2. **Modificar el botón "PDF"** en ambos listados para que **no fuerce la descarga automática** (`Content-Disposition: attachment`), sino que abra directamente la previsualización / visor PDF en una nueva pestaña del navegador (`Content-Disposition: inline`), de idéntica forma a la lista de ventas de facturación.
3. **Mejorar el diseño visual del botón PDF** en las grillas de Recibos y Órdenes de Pago para que cuente con el ícono y estilo uniforme del ERP (similar a `ventas_listado.html`).

---

## 2. Análisis de Archivos e Impacto

### A. Servicios de Generación PDF (`contable/services/reportes_pdf.py` y `facturacion/services/reportes_pdf.py`)
- Modificar la función `render_pdf_response(template_name, context, filename, as_attachment=False)`:
  - Por defecto, generar cabecera `Content-Disposition: inline; filename="..."` para permitir la visualización directa en el navegador.
  - Si `as_attachment=True`, mantener `Content-Disposition: attachment; filename="..."`.

### B. Vistas de Listados de Tesorería (`tesoreria/views_listados.py`)
- Eliminar las funciones `orden_pago_anular(request, pk)` y `recibo_anular(request, pk)`.
- En `orden_pago_pdf` y `recibo_pdf`, asegurar el retorno de `render_pdf_response` en modo inline.
- Limpiar importaciones que ya no se utilicen (`revertir_orden_pago`, `revertir_recibo`, `ReversionBloqueada`).

### C. URLs de Tesorería (`tesoreria/urls.py`)
- Remover los paths:
  - `path('ordenes-pago/<int:pk>/anular/', views_listados.orden_pago_anular, name='ordenpago_anular'),`
  - `path('recibos/<int:pk>/anular/', views_listados.recibo_anular, name='recibo_anular'),`

### D. Plantillas HTML (`templates/tesoreria/partials/ordenpago_grilla.html` y `recibo_grilla.html`)
- Quitar el botón HTMX `<button ...>Anular</button>` y su lógica condicional.
- Modernizar el enlace `<a href="{% url '...' %}">PDF</a>` con ícono SVG y estilo Tailwind estilizado con `target="_blank"`.

### E. Tests Automatizados (`tesoreria/tests/test_reversion.py`)
- Adaptar las pruebas unitarias que llamaban a las URLs de anulación eliminadas (`ordenpago_anular`), enfocando las pruebas de reversión al nivel de servicio en caso de corresponder y verificando que la generación de PDF retorne cabeceras `inline`.

---

## 3. Plan de Pruebas y Validación

1. **Ejecución de Tests Automatizados de Tesorería:**
   - Correr `python manage.py test tesoreria` y verificar 100% de tests pasando.
2. **Validación de PDF Inline:**
   - Probar endpoint `ordenpago_pdf` y `recibo_pdf` verificando que la cabecera `Content-Disposition` sea `inline`.
3. **Validación Visual de Grillas:**
   - Verificar que no aparezca el botón Anular en ninguna fila de la grilla de Órdenes de Pago ni Recibos.
   - Verificar que el botón PDF abra una nueva pestaña con el visor de PDF integrado.
