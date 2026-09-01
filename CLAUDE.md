# ERP Ikigai 2 — Instrucciones del Proyecto

Las reglas operativas, de documentación, de arquitectura y de UX de este proyecto
están definidas en `.cursorrules` y son de cumplimiento OBLIGATORIO. Se importan a
continuación como única fuente de verdad (editar siempre `.cursorrules`, no este archivo):

@.cursorrules

## Recordatorios clave (resumen — el detalle está en `.cursorrules`)
- **Idioma:** todo en español (comunicación, planes, walkthrough, documentación).
- **Bitácora:** registrar cada cambio de forma incremental en `docs/walkthrough.md` sin borrar historial.
- **Planes:** guardar copia numerada/fechada en `docs/planes/` antes de ejecutar.
- **Sin Django Admin:** todo el panel operativo va con HTML + Tailwind + HTMX.
- **Aprobación previa:** analizar el código relacionado y esperar OK explícito antes de modificar archivos.
- **Transaccionalidad:** `transaction.atomic()` + `select_for_update()` para saldos/asientos; CheckConstraints para reglas contables.
- **Higiene del repo:** temporales/scripts/dumps/logs van a `.gitignore` o a `scratch/`.
- **Búsqueda HTMX:** patrón obligatorio Typeahead + Lupa en todo selector de entidad.
- **`condic` (7 valores):** `1` = Real/Fiscal (90 % de los movimientos), `2` = Presupuestado/No Fiscal (gasto real sin respaldo), `3` = Ajuste (factura de la empresa pagada por el socio: va a IVA y Ganancias, se excluye del análisis de gastos), `4` = Auditoría (ajustes del estudio), `5` = Apertura, `6` = Refundición, `7` = Cierre. Libro IVA se puebla con `condic in (1, 3)`. Los `5/6/7` los genera el sistema y no se editan. **NUNCA** significa contado vs. cuenta corriente; el asiento hereda el `condic` del comprobante.
- **Importes:** siempre formato es-AR centralizado — clase `.fInputAR` con `static/js/formato_ar.js` en inputs (HTML y HTMX, sin JS extra) y filtro `{{ valor|formato_ar }}` en displays del servidor. Prohibido formatear a mano.
