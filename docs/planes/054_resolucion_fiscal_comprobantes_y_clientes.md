# Plan de Implementación — 054: Resolución Fiscal de Comprobantes ARCA y Gestión de Clientes desde Condición IVA

## 1. Contexto y Objetivos
Corregir la resolución impositiva de tipos de comprobante (`TipoComprobante`) para la facturación electrónica ante ARCA/AFIP por parte de emisores Responsables Inscriptos:
1. **Emisor RI a Receptor:**
   - **Responsable Inscripto:** Factura A (`001`), `DocTipo = 80` (CUIT 11 dígitos).
   - **Monotributista:** Factura A (`001`), `DocTipo = 80` (CUIT 11 dígitos) según RG 5003 / 5022.
   - **Consumidor Final:** Factura B (`006`), `DocTipo = 99` (`DocNro = 0`) o `DocTipo = 96` (DNI).
   - **Exento / No Alcanzado:** Factura B (`006`), `DocTipo = 80` (CUIT 11 dígitos).
2. **Eliminar el Fallback Erróneo a `TipoComprobante.objects.first()`** que forzaba Factura A a Consumidores Finales debido a diferencias de padding (`'6'` vs `'006'`).
3. **Flujo Guiado de Clientes/Proveedores:** Al dar de alta o editar una entidad, definir primero la **Condición ante el IVA** y a partir de allí derivar y bloquear el Tipo de Documento (`80 - CUIT` obligatorio para RI, Monotributo y Exento; `99/96/80` para Consumidor Final).
4. **Opción de Consumo Propio en Preventas:** Checkbox `es_consumidor_final` en Preventa para que un cliente Monotributista o Responsable Inscripto pueda comprar artículos para consumo personal emitiéndole Factura B sin alterar su ficha impositiva maestra.

---

## 2. Archivos Afectados
- `facturacion/models.py` [MODIFY]: agregado de campo `es_consumidor_final` a `Preventa`.
- `facturacion/migrations/0048_preventa_es_consumidor_final.py` [NEW]: migración de base de datos.
- `facturacion/forms.py` [MODIFY]: validación integral de `ClienteProveedorForm` basada en condición IVA y campo en `PreventaForm`.
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]: reorganización visual poniendo la Condición IVA en el primer bloque y dinamismo Alpine.js.
- `templates/facturacion/preventa_carga.html` [MODIFY]: checkbox "Facturar como Consumidor Final (Factura B)".
- `facturacion/views.py` [MODIFY]: funciones centralizadas `resolver_tipo_comprobante_fiscal` y `validar_y_obtener_documento_receptor`.
- `tesoreria/views_htmx.py` [MODIFY]: cobro en Caja Mostrador respetando `es_consumidor_final` para emitir Factura B.
- `facturacion/views_trazabilidad.py` [MODIFY]: validación previa de comprobantes trazables.
- `templates/facturacion/ventas_carga.html` y `templates/facturacion/ventas_trazabilidad_carga.html` [MODIFY]: preselección y filtrado inteligente de comprobantes según condición fiscal.
- `docs/walkthrough.md` [MODIFY]: registro de desarrollo.

---

## 3. Plan de Verificación
- Pruebas con clientes Consumidores Finales, Monotributistas, Responsables Inscriptos y Exentos.
- Verificación de consultas sobre `TipoComprobante` garantizando coincidencia con `'001'` y `'006'`.
- Ejecución de suite de pruebas de facturación y tesorería.
