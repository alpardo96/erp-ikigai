# Plan de Implementación: Separador de Miles en Reportes en Pantalla (Acordado en Grill-Me)

**Fecha:** 19/09/2026  
**Objetivo:** Mostrar importes monetarios con separador de miles y 2 decimales fijos (ej: `$ 1.234.567,89`) en las pantallas y reportes de la interfaz visual, garantizando aislamiento total para no afectar capturas, importaciones, exportaciones a Excel ni CSV.

---

## 🎯 Decisiones Acordadas en Grill-Me

1. **Aislamiento Total del Backend:**
   - **No se modificarán `settings.py` ni variables de localización global de Django** para descartar cualquier interferencia en formularios, endpoints HTMX, capturas OCR/Excel o modelos.
   - El formateo se aplica **exclusivamente en la capa visual (Templates HTML)** a través del filtro de plantilla `formato_ar`.

2. **Comportamiento en Exportaciones (Excel / CSV):**
   - En **Excel (`.xlsx`)**, las celdas continúan escribiéndose con su valor numérico nativo `float`/`Decimal` y con la máscara de visualización estándar de hoja de cálculo (`#,##0.00`), permitiendo al usuario operar con fórmulas y configuraciones locales de su PC.
   - En **CSV**, se mantiene el formato de valor numérico puro.

3. **Formato de Cifras en Pantalla:**
   - Siempre **2 decimales fijos** (ej: `$ 1.234.567,89`, `$ 1.000,00`, `$ 0,00`) para mantener alineadas y legibles las columnas numéricas.
   - Si el valor es negativo, se muestra con signo menos adelante (ej: `-$ 1.500,00` o `$-1.500,00`).

4. **Alcance de Pantallas Prioritarias:**
   - **Listado General de Ventas** (`/ventas/listado/`)
   - **Listado General de Compras** (`/compras/listado/`)

---

## 📋 Cambios a Realizar

### 1. Robustecimiento del Filtro en [`core/templatetags/formato_tags.py`](file:///d:/JM_Soft/erp-ikigai/core/templatetags/formato_tags.py)
- Mejorar el algoritmo de `formato_ar` para formatear mediante sustitución directa de separadores (`f"{abs(num):,.{decimales}f}"`), manejando `Decimal`, `float`, `int`, valores `None`, vacíos y ceros sin pérdida de precisión de punto flotante.

---

### 2. Actualización de Templates de Listados

#### [MODIFY] [`templates/facturacion/ventas_listado.html`](file:///d:/JM_Soft/erp-ikigai/templates/facturacion/ventas_listado.html)
- Cargar `{% load formato_tags %}`.
- Reemplazar `|floatformat:2` por `|formato_ar` en:
  - Fila de cada venta: `v.neto|formato_ar`, `v.iva|formato_ar`, `v.total|formato_ar`.
  - Fila de pie de tabla (totales acumulados): `totales.neto|formato_ar`, `totales.iva|formato_ar`, `totales.total|formato_ar`.

#### [MODIFY] [`templates/facturacion/compras_listado.html`](file:///d:/JM_Soft/erp-ikigai/templates/facturacion/compras_listado.html)
- Cargar `{% load formato_tags %}`.
- Reemplazar `|floatformat:2` por `|formato_ar` en:
  - Fila de cada compra: `c.neto|formato_ar`, `c.iva|formato_ar`, `c.total|formato_ar`.
  - Fila de pie de tabla (totales acumulados): `totales.neto|formato_ar`, `totales.iva|formato_ar`, `totales.total|formato_ar`.

---

## 🧪 Plan de Verificación

1. **Prueba Automatizada de Formato:**
   - Ejecutar script que renderice `ventas_listado.html` y `compras_listado.html` con datos reales y verifique que las cadenas contengan puntos de miles y comas decimales (ej. `$ 84.981.702,00`, `$ 735.537,19`).
2. **Prueba de No Regresión en Capturas / Formularios:**
   - Verificar que los endpoints de captura y parseo de inputs `.fInputAR` sigan operando normalmente sin alteraciones.
3. **Prueba de Exportación:**
   - Confirmar que la exportación a Excel siga generando valores numéricos puros aptos para fórmulas.
