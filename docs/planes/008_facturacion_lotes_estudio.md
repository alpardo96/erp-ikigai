# Refactorización Facturación Lotes para Estudio y Emisión ARCA Servicios

El objetivo es trasladar la lógica de facturación de lotes y actualización de tarifas desde el *core* de facturación hacia la verticalidad **Estudio**, sin romper el funcionamiento actual. Además, se ajustará la interfaz para ingresar el período (Mes y Año por separado) y se creará un servicio específico para emitir facturas a ARCA bajo el concepto de **Servicios** (Concepto = 2), enviando las fechas desde/hasta del servicio y vencimiento de pago.

## Proposed Changes

---

### Módulo Verticalidad Estudio (Vistas y Rutas)

Se trasladarán las vistas desde `facturacion/views_estudio.py` hacia `verticalidades/estudio/views.py`.

#### [MODIFY] `verticalidades/estudio/views.py`
- Mover el contenido completo a este archivo.
- Cambiar las referencias de renderizado de templates para que apunten a `estudio/...`.
- Cambiar la instanciación del servicio de facturación en `generar_lote_facturacion` para que utilice el nuevo `FacturacionLoteEstudioService`.

#### [MODIFY] `verticalidades/estudio/urls.py`
- Actualizar los *imports* para que las vistas se traigan desde `verticalidades.estudio.views` en lugar de `facturacion.views_estudio`.

---

### Módulo Verticalidad Estudio (Templates)

#### [NEW] `verticalidades/estudio/templates/estudio/facturacion_lotes.html`
- **Ajuste de Período**: Reemplazar el input único de texto por dos inputs (Mes y Año) que concatenan vía JS a `YYYYMM`.
- Achicar los campos para que se ajusten al largo del contenido, agregando margen prolijo y centrado.

#### [NEW] `verticalidades/estudio/templates/estudio/actualizar_tarifas.html`
- Copia fiel del archivo actual.

#### [DELETE] `facturacion/templates/facturacion/estudio/facturacion_lotes.html`
#### [DELETE] `facturacion/templates/facturacion/estudio/actualizar_tarifas.html`
#### [DELETE] `facturacion/views_estudio.py`

---

### Módulo Verticalidad Estudio (Servicio de Facturación)

#### [NEW] `verticalidades/estudio/services/facturacion_lote_estudio.py`
- **Lógica de Fechas**: Extraer el año y mes del parámetro `periodo` (YYYYMM). Calcular `FchServDesde`, `FchServHasta` y `FchVtoPago`.
- **Llamada a AFIP (ARCA)**: 
  - Generar el objeto `Venta` en memoria.
  - Llamar a ARCA con `concepto = 2` y pasarle las fechas.
  - Esperar el CAE y solo entonces hacer el `.save()` para persistir en BD.
- **Comprobantes Internos (PRE)**: Mantener la lógica intacta para no romper la contabilidad. Se hace el `.save()` en memoria, se crean los ítems y luego otro `.save()` para que actúe la señal contable.
