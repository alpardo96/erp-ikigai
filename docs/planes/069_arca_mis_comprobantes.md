# Plan de Implementación: Modelo `ArcaMisComprobantes` y Motor de Conciliación ARCA vs. Libro IVA

Este plan aborda la creación de la tabla física `arca_mis_comprobantes` para almacenar los comprobantes emitidos y recibidos capturados desde el portal de **Mis Comprobantes ARCA / AFIP**, junto con el proceso de importación y el motor de conciliación bi-direccional contra `cble_libro_iva_ventas` y `cble_libro_iva_compras`.

## User Review Required

> [!IMPORTANT]
> **Estructura de Vinculación Bi-direccional**:
> 1. En **`ArcaMisComprobantes`**: Al conciliar un registro importado de ARCA con el sistema, se estampa su `asiento_id` correspondiente.
> 2. En **`cble_libro_iva_compras` / `cble_libro_iva_ventas`**: Al conciliar, se estampa el `cae` obtenido del archivo de ARCA.
> 3. **Criterios de Estado**:
>    - **Conciliados**: `asiento_id` completado en ARCA y `cae` completado en Libro IVA.
>    - **Solo en Libro IVA**: Registros del sistema cuyo `cae` no se encontró en la captura de ARCA.
>    - **Solo en Mis Comprobantes**: Registros importados de ARCA cuyo `asiento_id` permanece nulo (pendientes de cargar o importar al ERP).

---

## Proposed Changes

### 1. Modelo `ArcaMisComprobantes` (`impuestos/models.py`)

#### [NEW] [`impuestos/models.py`](file:///d:/JM_Soft/erp-ikigai-2/impuestos/models.py)
Creación del modelo `ArcaMisComprobantes`:
- `empresa`: ForeignKey a `Empresa`.
- `origen`: `'C'` (Compras / Comprobantes Recibidos) | `'V'` (Ventas / Comprobantes Emitidos).
- `fecha`: DateField (fecha del comprobante en ARCA).
- `periodo`: CharField(max_length=6, db_index=True) (`YYYYMM`).
- `codiva`: CharField(max_length=3) (código de comprobante ARCA, ej: `'001'`, `'006'`, `'011'`).
- `punto`: IntegerField (punto de venta).
- `numero`: BigIntegerField (número de comprobante).
- `numero_hasta`: BigIntegerField(null=True, blank=True).
- `cuit_contraparte`: CharField(max_length=11, db_index=True) (CUIT de emisor en compras o receptor en ventas).
- `razon_social_contraparte`: CharField(max_length=200, blank=True).
- `tipo_doc_contraparte`: CharField(max_length=10, blank=True).
- `nro_doc_contraparte`: CharField(max_length=20, blank=True).
- `tipo_cambio`: DecimalField(max_digits=10, decimal_places=4, default=1.0).
- `moneda`: CharField(max_length=5, default='PES').
- `neto_gravado`: DecimalField(max_digits=15, decimal_places=2, default=0).
- `no_gravado`: DecimalField(max_digits=15, decimal_places=2, default=0).
- `exento`: DecimalField(max_digits=15, decimal_places=2, default=0).
- `iva_total`: DecimalField(max_digits=15, decimal_places=2, default=0).
- `otros`: DecimalField(max_digits=15, decimal_places=2, default=0).
- `total`: DecimalField(max_digits=15, decimal_places=2, default=0).
- `cae`: CharField(max_length=20, blank=True, db_index=True) (CAE / Nro. Autorización ARCA).
- `asiento_id`: IntegerField(null=True, blank=True, db_index=True) (ID de asiento contable/comprobante en el ERP al conciliar).
- `fecha_importacion`: DateTimeField(auto_now_add=True).
- `usuario`: ForeignKey a `User`.

---

### 2. Servicios de Importación y Conciliación (`impuestos/services.py`)

#### [NEW] Funciones de Conciliación y Parseo
- `importar_archivo_mis_comprobantes_arca(empresa_id, tipo_operacion, archivo, usuario)`:
  - Lee y procesa planillas `.csv`, `.xlsx` o `.xls` exportadas de AFIP/ARCA (comprobantes emitidos y recibidos).
  - Almacena/actualiza las filas en `ArcaMisComprobantes`.
- `conciliar_mis_comprobantes_arca(empresa_id, origen, periodo)`:
  - Matchea registros de `ArcaMisComprobantes` contra `LibroIvaCompras` (para `'C'`) o `LibroIvaVentas` (para `'V'`) comparando por:
    1. CUIT contraparte.
    2. Código de comprobante (`codiva`).
    3. Punto de venta y Número (o CAE cuando esté disponible).
  - Al encontrar coincidencia:
    - En `ArcaMisComprobantes`: guarda `asiento_id = libro_item.asiento_id`.
    - En `LibroIvaCompras` / `LibroIvaVentas`: actualiza `cae = arca_item.cae`.
- `obtener_reporte_conciliacion_arca(empresa_id, origen, periodo)`:
  - Devuelve los 3 conjuntos:
    - `conciliados`: Registros pareados exitosamente.
    - `solo_libro_iva`: Registros en Libro IVA con `cae` vacío/sin matchear.
    - `solo_arca`: Registros en `ArcaMisComprobantes` con `asiento_id` nulo.

---

### 3. Vistas y Plantillas (`impuestos/views.py` y `templates/impuestos/mis_comprobantes_arca.html`)

#### [MODIFY] [`impuestos/views.py`](file:///d:/JM_Soft/erp-ikigai-2/impuestos/views.py)
- `MisComprobantesArcaView`:
  - `GET`: Muestra formulario de importación por Período Fiscal (`YYYYMM`) y pestañas de resultados (Conciliados, Solo Libro IVA, Solo ARCA).
  - `POST`: Procesa el archivo subido (Excel/CSV), ejecuta la conciliación automática y retorna el resumen con mensajes informativos.

#### [MODIFY] [`templates/impuestos/mis_comprobantes_arca.html`](file:///d:/JM_Soft/erp-ikigai-2/templates/impuestos/mis_comprobantes_arca.html)
- Rediseño con pestañas interactivas:
  - 🟢 **Conciliados** (Verdes).
  - 🟡 **Solo en Libro IVA (Sin CAE vinculada)**.
  - 🔵 **Solo en Mis Comprobantes ARCA (Pendientes de ingresar al ERP)**.

---

## Verification Plan

### Automated Tests
- Ejecución de tests en `impuestos/tests/test_mis_comprobantes_arca.py`:
  - Test de importación y persistencia en `ArcaMisComprobantes`.
  - Test de matcheo y actualización bi-direccional de `asiento_id` y `cae`.
  - Test de segregación de estados: Conciliados, Solo en Libro IVA y Solo en ARCA.

### Manual Verification
- Carga de un archivo de prueba desde la interfaz `/impuestos/mis-comprobantes-arca/` y verificación del estado de conciliación.
