# Plan de Implementación: Mudar y Consolidar `formato_ar.js` en `core/static/js/formato_ar.js`

**Fecha:** 19/09/2026  
**Objetivo:** Mudar y consolidar el script JavaScript de formateo a `core/static/js/formato_ar.js` (para que esté versionado en Git dentro del módulo `core` y no en la carpeta raíz `static/` que está excluida en `.gitignore`), dejándolo como la **única fuente de verdad** del ERP para JavaScript.

---

## 🔍 Diagnóstico y Justificación

1. **Exclusión de `static/` en Git:**
   - En el archivo `.gitignore`, la carpeta raíz `static/` está excluida.
   - Al ubicar el archivo en `core/static/js/formato_ar.js`, Django lo descubre automáticamente mediante `AppDirectoriesFinder` con el tag `{% static 'js/formato_ar.js' %}` y queda **100% versionado y preservado en el repositorio Git**.

2. **Consolidación de Funcionalidades en el JS Definitivo:**
   - `desformatearAR(entrada)`: normaliza textos (`"1.234.567,89"`, `"$ 5.000,00"`, inputs HTML, valores vacíos/nulos) a `Number` puro.
   - `formatearAR(numero, decimales = 2)`: convierte a `"1.234.567,89"`.
   - `formatoMonedaAR(numero, simbolo = '$ ')`: antepone símbolo de moneda (`"$ 1.234.567,89"`).
   - Eventos de teclado numérico: transforma tecla `.` en `,` en inputs `.fInputAR`.
   - Formateo en vivo preservando la posición exacta del cursor.
   - Soporte automático para HTMX (`htmx:afterOnLoad`, `htmx:afterSwap`) y mutaciones dinámicas de DOM (`MutationObserver`).
   - Exposición global de alias de retrocompatibilidad:
     ```javascript
     window.formatearAR = formatearAR;
     window.desformatearAR = desformatearAR;
     window.formatoMonedaAR = formatoMonedaAR;
     window.parseAR = desformatearAR;  // Alias retrocompatible
     window.fMiles = formatearAR;      // Alias retrocompatible
     window.inicializarFormatoAR = inicializarFormatoAR;
     ```

---

## 📋 Cambios a Realizar

### 1. Creación del Archivo Definitivo
- **`core/static/js/formato_ar.js`**: Implementación completa y robusta en el módulo `core`.

---

### 2. Actualización de Context Processor
- **`core/context_processors.py`**: Actualizar la búsqueda del mtime de `formato_ar.js` apuntando a `('core', 'static', 'js', 'formato_ar.js')` para el cache-busting automático.

---

### 3. Limpieza de Declaraciones Redundantes en Templates
Remover `function parseAR` y `function fMiles` locales en:
- `templates/facturacion/ventas_carga.html`
- `templates/facturacion/ventas_trazabilidad_carga.html`
- `templates/facturacion/compras_carga.html`
- `templates/facturacion/preventa_carga.html`

---

### 4. Actualización de Documentación y Reglas
- `.cursorrules` y `CLAUDE.md`: Actualizar la ruta oficial a `core/static/js/formato_ar.js` como regla maestra del ERP.

---

## 🧪 Plan de Verificación

1. **Resolución de Estáticos de Django:**
   - Comprobar con `django.contrib.staticfiles.finders.find('js/formato_ar.js')` que Django resuelve correctamente el archivo desde `core/static/js/formato_ar.js`.
2. **Pruebas Automatizadas de Funciones JS:**
   - Validar parseos y formateos con casos extremos (strings con comas, puntos, `$`, números negativos, ceros, etc.).
3. **Verificación de Git:**
   - Confirmar que el archivo `core/static/js/formato_ar.js` no sea ignorado por git.
