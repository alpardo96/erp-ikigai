# Plan 001 — Automatización Contable en Compras y Ventas

## Estado: ✅ Completado (Fases 2-3 del walkthrough)

## Descripción del Objetivo
El objetivo es diseñar e implementar el servicio de contabilización automática de comprobantes de compras y ventas en el ERP.
Basándonos en la retroalimentación y previendo escenarios de gran volumen (por ejemplo, miles de tickets diarios en supermercados con múltiples sucursales), diseñamos una arquitectura flexible que soporta tanto la contabilización individual inmediata como la consolidación en un **Asiento Resumen Diario por Sucursal**.
Además, se añade soporte para multi-actividad asignando cuentas de ventas/compras a nivel de **Rubro de Producto**, con retrocompatibilidad usando las cuentas por defecto configuradas en `ParametrosContables`.

---

## User Review Required
> [!IMPORTANT]
> - **Inmutabilidad y No-Recursividad de Asientos:** Siguiendo la mejor práctica contable y tu observación, **no se realizarán modificaciones ni recálculos sobre asientos ya grabados**. 
>   * Si un comprobante se anula o se edita: el asiento original asociado se marca estrictamente como **Anulado** (`anulado = True`, `fec_anulacion = timezone.now()`).
>   * Si es una edición, se genera un **nuevo** asiento independiente desde cero reflejando los nuevos valores del comprobante, manteniendo el historial de auditoría intacto. No se eliminarán asientos físicos de la base de datos.
> - **Cuentas Contables por Rubro (Multi-Actividad):**
>   * Se agregará soporte en el modelo `Rubro` para definir `cta_ventas` y `cta_compras` específicas.
>   * Al facturar o comprar, el sistema totalizará los netos, no gravados y exentos agrupándolos por la cuenta del Rubro del Producto de cada ítem. Si el Rubro no tiene cuenta asignada, se recurre a la cuenta por defecto de `ParametrosContables`.
> - **Parámetro de Alta Transaccionalidad (Individual vs. Resumen):**
>   * Se agregará un campo `metodo_contabilizacion_ventas` en `ParametrosContables` por Empresa para elegir si se genera un asiento por comprobante o un asiento diario resumido por sucursal.

---

## Análisis de Alta Transaccionalidad (Individual vs. Resumen Diario)

Para prever la carga de miles de facturas/tickets diarios por sucursal, analizamos las opciones y diseñamos la siguiente solución:

| Opción | Pros | Contras |
| :--- | :--- | :--- |
| **A) Asiento Individual (1 a 1)** | Trazabilidad perfecta y directa de cada ticket. Fácil de auditar de forma unitaria. | Degradación de rendimiento y bloqueos de DB (*database locks*) en horas pico con miles de transacciones concurrentes. Libro Diario inmenso y poco práctico para contadores. |
| **B) Asiento Resumen Diario por Sucursal** | **Rendimiento ultra-alto.** Un solo asiento consolidado diario por sucursal y actividad. Evita bloqueos en DB. Limpieza absoluta en el Libro Diario. Práctica estándar homologada en grandes comercios. | Requiere un proceso en lote (ej. al Cierre de Caja o fin del día). La trazabilidad directa se realiza mediante reportes auxiliares que vinculan el lote con los comprobantes. |

### Propuesta de Configuración y Solución:
Agregamos a `ParametrosContables` la opción de definir el método:
1. `INDIVIDUAL`: Se contabiliza síncronamente al guardar la venta.
2. `RESUMEN_DIARIO`: Al facturar, el comprobante se guarda pero queda con `asiento_id = Null`. Al final del día o al realizar el **Cierre de Caja**, se dispara un proceso en lote que consolida todas las ventas pendientes del día por sucursal, agrupando por cuenta de venta (Rubro) e IVA, y genera un único asiento contable consolidado vinculando dicho `asiento_id` a todos los comprobantes del lote.

---

## Cambios Propuestos

### 1. Módulo Productos (`productos`)

#### [MODIFY] [models.py](file:///d:/PROGRAMACION/IA/erp-ikigai-2/productos/models.py)
* Modificar el modelo `Rubro` para incorporar las cuentas contables de ventas y compras:
  ```python
  cta_ventas = models.ForeignKey('contable.Cuenta', on_delete=models.SET_NULL, null=True, blank=True, related_name='rubros_ventas', verbose_name="Cuenta de Ventas")
  cta_compras = models.ForeignKey('contable.Cuenta', on_delete=models.SET_NULL, null=True, blank=True, related_name='rubros_compras', verbose_name="Cuenta de Compras")
  ```

---

### 2. Módulo Contable (`contable`)

#### [MODIFY] [models.py](file:///d:/PROGRAMACION/IA/erp-ikigai-2/contable/models.py)
* Incorporar en `ParametrosContables` el método de contabilización de ventas:
  ```python
  METODO_CONTAB_CHOICES = [
      (1, 'Individual (Por Comprobante)'),
      (2, 'Consolidado (Resumen Diario por Sucursal)'),
  ]
  metodo_contabilizacion_ventas = models.IntegerField(choices=METODO_CONTAB_CHOICES, default=1, verbose_name="Método Contabilización Ventas")
  ```

#### [NEW] [contabilizacion.py](file:///d:/PROGRAMACION/IA/erp-ikigai-2/contable/services/contabilizacion.py)
* **`contabilizar_venta_individual(venta: Venta) -> Asiento`**:
  * Verifica si la venta ya tiene `asiento_id`. De ser así, se anula el asiento anterior llamando a `anular_asiento_de_comprobante(venta.asiento_id)`.
  * Obtiene `ParametrosContables`.
  * Recorre los ítems de la venta agrupando la suma de `total_item` por la cuenta contable de ventas correspondiente (si el rubro del producto tiene `cta_ventas` se usa esa, si no, se usa `cta_ventas` de `ParametrosContables`).
  * Genera el asiento:
    * **Debe**: Cuenta de Deudores por Ventas del cliente (`cliente.cta_pat` si es imputable, de lo contrario `cta_clientes_default` de parámetros contables). Importe: `total` de la venta.
    * **Haber**: Cuentas de Ventas acumuladas por cuenta. Importe: `neto` de cada cuenta.
    * **Haber**: Cuenta de IVA Débito Fiscal (`cta_iva_debito`). Importe: `iva` total de la venta.
    * **Haber**: Cuentas de Percepciones/Impuestos si los hay (`cta_ret_iibb`, `cta_impuestos_internos` u `otros`).
  * Llama a `crear_asiento()`, asigna el `asiento_id` y guarda la venta.

* **`contabilizar_compras(compra: Compra) -> Asiento`**:
  * Las compras se procesan de forma individual debido a su menor frecuencia y mayor personalización.
  * Si ya posee `asiento_id`, primero se anula el asiento anterior.
  * Dos fuentes de cuenta de imputación:
    1. Si se define una cuenta directa en el formulario de carga.
    2. Si se discriminan productos, se agrupan los netos por la cuenta del rubro de cada producto (`cta_compras` de `Rubro`), o en su defecto `cta_compras` de `ParametrosContables`.
  * Genera el asiento:
    * **Debe**: Cuentas de Compras/Gastos agrupadas por cuenta. Importe: `neto`.
    * **Debe**: Cuenta de IVA Crédito Fiscal (`cta_iva_credito`). Importe: `iva` total.
    * **Debe**: Percepciones si las hay (`p_iva`, `p_iibb`, `p_gcia` contra sus respectivas cuentas parametrizadas).
    * **Haber**: Cuenta de proveedores (`proveedor.cta_pat` si es imputable, de lo contrario `cta_proveedores_default`). Importe: `total` de la compra.

* **`consolidar_ventas_diarias(empresa: Empresa, fecha: date, sucursal: Sucursal) -> Asiento`**:
  * Obtiene todas las ventas activas de la sucursal en esa fecha que tengan `asiento_id__isnull=True`.
  * Agrupa y consolida todos los importes (Debe a clientes/caja, Haber a cuentas de venta por rubro, Haber a IVA, etc.).
  * Genera un único Asiento de resumen diario.
  * Asocia el `asiento_id` creado a todas las ventas del lote de manera masiva.

* **`anular_asiento_de_comprobante(asiento_id: int) -> None`**:
  * Obtiene el asiento y establece `anulado = True` y `fec_anulacion = timezone.now()`.

---

### 3. Módulo de Facturación (`facturacion`)

#### [MODIFY] [signals.py](file:///d:/PROGRAMACION/IA/erp-ikigai-2/facturacion/signals.py)
* **`post_save` de `Venta`**:
  * Si la venta se marca como anulada (`estado = 1`), llama a `anular_asiento_de_comprobante(instance.asiento_id)` (si existe).
  * Si la venta está activa:
    * Si la configuración es `INDIVIDUAL`, llama a `contabilizar_venta_individual(instance)`.
    * Si la configuración es `RESUMEN_DIARIO`, no hace nada en tiempo real (queda para el lote diario).
* **`post_save` de `Compra`**:
  * Llama a `contabilizar_compras(instance)`.
* **`post_delete` de `Venta` o `Compra`**:
  * Si existe `asiento_id`, llama a `anular_asiento_de_comprobante(instance.asiento_id)`. **No se elimina el asiento de la DB física.**

---

## Plan de Verificación

### Pruebas Automatizadas (contable/tests/test_contabilizacion.py)
* `test_contabilizacion_individual_venta_por_rubros`: Verifica el desglose de importes en el Haber para distintas cuentas de venta según los rubros de los ítems de la factura.
* `test_contabilizacion_compra_por_rubros`: Verifica que la compra desglose los costos según los rubros de los productos comprados.
* `test_anulacion_de_comprobante_no_borra_sino_anula`: Verifica que al anular la venta, el asiento pase a `anulado = True` y mantenga sus movimientos en la base de datos de forma inmutable.
* `test_consolidacion_resumen_diario`: Simula 10 ventas del día bajo el método `RESUMEN_DIARIO`, ejecuta el servicio de consolidación diaria y valida que se cree un único asiento resumido que cuadre perfectamente, y que todos los tickets queden asociados a ese `asiento_id`.
