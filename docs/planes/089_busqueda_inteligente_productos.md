# Plan de Implementación: Búsqueda Inteligente Multi-Término de Productos en Preventa y Ventas

**Fecha:** 2026-09-09  
**Autor:** Cristian - PC CASA  
**Referencia:** Plan 089  

## 1. Contexto y Diagnóstico
En la carga de preventa (y ventas generales), el buscador por autocompletado (`typeahead_productos_venta`) y el modal de búsqueda (`buscador_productos_venta` / `lista_productos_venta_resultados`) actualmente aplican un filtro rígido `icontains` sobre toda la cadena de texto ingresada (`Q(detalle__icontains=q)`).

### Problema:
Si el usuario escribe términos separados o en distinto orden (ejemplo: *"bersa 9mm"*, *"9mm bersa"*, *"tpr9 9"*, *"winchester 308"*, *"recargable linterna"*):
- Si el detalle en el catálogo es `"PISTOLA BERSA TPR9 CALIBRE 9X19MM"`, la búsqueda falla porque los términos *"bersa"* y *"9mm"* no aparecen de manera contigua y en ese orden exacto.
- No busca simultáneamente en campos clave como `marca__detalle`, `rubro__detalle`, `cod_prov`, `codigo_anterior`, etc.
- No ordena por relevancia (por ejemplo, si coincide el ID exacto o el código de fábrica, debería aparecer primero).

### Objetivo:
Hacer que el motor de búsqueda de productos sea **inteligente y multi-término**:
1. **Tokenización de términos:** Separar el texto en palabras individuales.
2. **Concatenación flexible (Adelante / En el medio / Atrás):** Exigir que todas las palabras buscadas estén presentes en los atributos del producto (`detalle`, `cod_fab`, `cod_prov`, `codigo_anterior`, `marca`, `rubro`, `familia`, `id`), sin importar el orden ni la posición en el texto.
3. **Priorización por Relevancia:** Ordenar los resultados para mostrar primero coincidencias exactas por ID o código, luego coincidencias que inician con el texto, luego coincidencias de frase completa y finalmente coincidencias de términos combinados, manteniendo el límite de resultados (20 para typeahead, 50 para modal) para mantener un rendimiento óptimo de base de datos sin sobrecargar la vista.

---

## 2. Propuesta Técnica

### A. Creación del Servicio de Búsqueda de Productos
Crear [`productos/services/busqueda_service.py`](file:///c:/Users/Cristian/Desktop/Proyectos%20Django/erp-ikigai/productos/services/busqueda_service.py) con funciones especializadas:
- `buscar_productos_inteligente(q, empresa_id, solo_subprod=None, excluir_subprod=False, limit=20)`:
  - Tokeniza `q` en palabras clave (`terminos = q.split()`).
  - Para cada término, genera un `Q` multi-campo:
    `Q(detalle__icontains=term) | Q(cod_fab__icontains=term) | Q(cod_prov__icontains=term) | Q(codigo_anterior__icontains=term) | Q(marca__detalle__icontains=term) | Q(rubro__detalle__icontains=term) | Q(familia__detalle__icontains=term)`
    (y `Q(id=int(term))` si el término es numérico).
  - Une todos los términos con `AND` (`filtro &= term_q`), permitiendo encontrar productos sin importar el orden de las palabras ingresadas.
  - Aplica ordenamiento por relevancia con `Case/When` en Django ORM:
    - **Prioridad 1:** Coincidencia exacta de `id`, `cod_prov`, `cod_fab` o `codigo_anterior`.
    - **Prioridad 2:** `detalle` comienza con la consulta completa (`istartswith`).
    - **Prioridad 3:** `detalle` contiene la frase completa (`icontains`).
    - **Prioridad 4:** Coincidencia de todos los términos distribuidos.
    - **Secundario:** Alfabético por `detalle`.

### B. Integración en Endpoints de Facturación y Preventa
1. **`typeahead_productos_venta`** en [`facturacion/views_htmx.py`](file:///c:/Users/Cristian/Desktop/Proyectos%20Django/erp-ikigai/facturacion/views_htmx.py):
   - Reemplazar el filtro rígido por `buscar_productos_inteligente` garantizando el multi-tenant y la lógica de trazabilidad/SIGIMAC.
2. **`buscar_producto_venta_por_codigo`** en [`facturacion/views_htmx.py`](file:///c:/Users/Cristian/Desktop/Proyectos%20Django/erp-ikigai/facturacion/views_htmx.py):
   - Al dar Enter directo en el input de carga rápida de preventa:
     - Buscar primero coincidencia exacta por `id`, `cod_prov`, `cod_fab` o `codigo_anterior`.
     - Si no hay match exacto pero el usuario tipeó términos (ej. *"bersa tpr9"* y apretó Enter), recuperar el primer resultado más relevante de la búsqueda inteligente.
3. **`lista_productos_venta_resultados`** en [`facturacion/views_htmx.py`](file:///c:/Users/Cristian/Desktop/Proyectos%20Django/erp-ikigai/facturacion/views_htmx.py):
   - Aplicar la búsqueda multi-término en el filtro de detalle `f_det`.
4. **`buscar_productos`** en [`productos/views_htmx.py`](file:///c:/Users/Cristian/Desktop/Proyectos%20Django/erp-ikigai/productos/views_htmx.py) y **`typeahead_productos_compra`**:
   - Actualizar para aprovechar la misma búsqueda inteligente multi-término.

---

## 3. Plan de Verificación

### Pruebas Automatizadas
- Crear tests unitarios en `productos/tests/test_busqueda_inteligente.py` cubriendo:
  1. Búsqueda con palabras en orden invertido (ej. *"9mm bersa"* encuentra *"Pistola Bersa TPR 9mm"*).
  2. Búsqueda con palabras intercaladas (ej. *"tpr 9mm"* encuentra *"Pistola Bersa TPR 9mm"*).
  3. Búsqueda combinando marca y detalle (ej. *"bersa cargador"* donde marca es *"BERSA"* y detalle es *"Cargador 17 tiros"*).
  4. Búsqueda por código anterior, código de fábrica o ID exacto.
  5. Prioridad de relevancia: un producto con coincidencia exacta debe figurar antes que uno con coincidencia parcial.
  6. Aislamiento multi-tenant por `empresa_id`.

### Pruebas Manuales / UI
- Probar el typeahead en la carga de preventa `/ventas/preventas/nueva/`.
- Probar la búsqueda en el modal de productos de ventas.
