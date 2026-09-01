# Plan de Implementación - Optimización y Corrección en Consulta del Libro Mayor

Este plan detalla los cambios para solucionar la consulta y el rendimiento del Libro Mayor en el módulo contable:

1. **Consulta individual desde el Sumas y Saldos:** El modal del mayor general para una cuenta (`mayor_cuenta_modal`) solicita las filas a `libro_mayor_rows` enviando el parámetro `cuenta_id`. Modificaremos la vista `libro_mayor_rows` (y las vistas de exportación) para que si se recibe `cuenta_id`, se asigne este ID tanto a `cuenta_desde` como a `cuenta_hasta`.
2. **Problema de rendimiento (N+1) en el Libro Mayor General:** Al consultar el rango completo del Mayor (que por defecto incluye la primera y última cuenta contable de la empresa), el sistema itera secuencialmente por las 210 cuentas. Para cada cuenta, realiza 3 consultas SQL independientes (totales, saldo anterior y movimientos). Esto genera más de 600 consultas SQL, provocando un retraso masivo (casi 1 minuto) o timeouts de conexión, haciendo que la interfaz "no muestre nada".
   * **Solución de Optimización:** Cuando el rango consultado contenga más de una cuenta (es decir, `cuenta_desde != cuenta_hasta`), filtraremos el conjunto de cuentas para incluir únicamente aquellas que posean al menos un movimiento registrado en la base de datos de la empresa. Esto reduce el número de cuentas a iterar de 210 a solo 2 (las que tienen movimientos), haciendo la consulta instantánea. Si se consulta una sola cuenta (ej. desde el modal), no aplicaremos esta restricción para permitir visualizarla aun si no posee movimientos.

*Nota: Se pospone la modificación al listado del Diario General por indicación del usuario.*

---

## Cambios Propuestos

### Módulo Contable (HTMX & Reportes)

#### [MODIFY] [views_htmx.py](file:///d:/JM_Soft/erp-ikigai-2/contable/views_htmx.py)
* **Ubicación:** `libro_mayor_rows` (alrededor de la línea 291).
* **Lógica:**
  - Detectar el parámetro `cuenta_id` y usarlo para establecer `cuenta_desde_id` y `cuenta_hasta_id`.
  - Si `cuenta_desde_id != cuenta_hasta_id`, obtener la lista de IDs de cuentas con movimientos activos de la empresa para filtrar la consulta de cuentas, evitando el cuello de botella N+1.

#### [MODIFY] [views_reportes.py](file:///d:/JM_Soft/erp-ikigai-2/contable/views_reportes.py)
* **Ubicación:** `exportar_mayor` (línea 26) y `exportar_mayor_pdf_view` (línea 106).
* **Lógica:** Implementar exactamente el mismo soporte para `cuenta_id` y la optimización de consulta por rango para evitar ralentizaciones o timeouts durante la exportación a Excel y PDF.
