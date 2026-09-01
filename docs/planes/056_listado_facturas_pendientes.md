# Plan 056 — Listado de Facturas Pendientes (Compras / Ventas)

- **Fecha:** 2026-08-18
- **Estado:** ✅ APROBADO E IMPLEMENTADO (2026-08-18)
- **Origen:** réplica del formulario VFP `tran_facturas_pendientes.scx` (I-108) del sistema `c:\jm_soft\balances`
- **Módulo:** Facturación (transversal a Tesorería y Contabilidad)

---

## 1. Análisis del formulario VFP original

### 1.1 Fuente de datos

El formulario se apoya en una única vista SQL del `contable.dbc`, `cons_lib_iva_pendientes`,
extraída íntegra del contenedor de base de datos:

```sql
SELECT Cli_pro.detalle, Cli_pro.cuit, Lib_iva.id_iva, Lib_iva.id_vta, Lib_iva.fecha,
       Lib_iva.mesano, Lib_iva.tipo, Lib_iva.punto, Lib_iva.numero, Lib_iva.hasta,
       Lib_iva.id_cod, Lib_iva.cantidad, Lib_iva.litros, Lib_iva.neto, Lib_iva.alic_iva,
       Lib_iva.iva, Lib_iva.imp_int, Lib_iva.exento, Lib_iva.no_grav, Lib_iva.ret_iva,
       Lib_iva.ret_gcia, Lib_iva.ret_suss, Lib_iva.ret_ib, Lib_iva.ib_cba, Lib_iva.ret_mun,
       Lib_iva.redondeo, Lib_iva.total, Lib_iva.id_asto, Lib_iva.id_cta, Lib_iva.id_ccble,
       Lib_iva.c_v, Lib_iva.moneda, Lib_iva.neto_m, Lib_iva.cotiz, Lib_iva.condic,
       Lib_iva.vencim, Lib_iva.id_eje_a, Lib_iva.pagado, Lib_iva.saldo, Lib_iva.pto_r,
       Lib_iva.nro_r, Lib_iva.op_f, Lib_iva.lib_iva, Lib_iva.cod_citi, Lib_iva.carga_citi,
       Lib_iva.cpte_o_ib, Lib_iva.can_alic, Lib_iva.asignado, Lib_iva.itc, Lib_iva.f_p,
       Cli_pro.tipo, Lib_iva.pcia_o, Lib_iva.pcia_d, Lib_iva.concep
  FROM contable!cli_pro RIGHT OUTER JOIN contable!lib_iva
    ON Cli_pro.codigo = Lib_iva.id_cod
 WHERE ( Lib_iva.fecha  BETWEEN ?oApp.fec1 AND ?oApp.fec2
     AND Lib_iva.id_cod BETWEEN ?oApp.num1 AND ?oApp.num2 )
   AND Lib_iva.c_v = ( ?oApp.det1 )
   AND ( Lib_iva.saldo BETWEEN ?oApp.num3 AND ?oApp.num4
      OR Lib_iva.saldo BETWEEN ?oApp.num5 AND ?oApp.num6 )
 ORDER BY Lib_iva.id_cod, Lib_iva.fecha, Lib_iva.tipo, Lib_iva.numero
```

> Nota: los alias `tipo_a` / `tipo_b` que usan la grilla y el Excel son la desambiguación
> automática de VFP entre `Lib_iva.tipo` (tipo de comprobante) y `Cli_pro.tipo`
> (clasificación del cliente/proveedor: `CONSUMO`, `CLI 01`…`CLI 06`).

### 1.2 Traducción de los controles a parámetros (método `cmdGenerar.Click`)

| Control de pantalla | Variable VFP | Efecto en el `WHERE` |
|---|---|---|
| **Fecha desde / hasta** | `fec1`, `fec2` | `fecha BETWEEN fec1 AND fec2`. `Form.Init` los precarga con el ejercicio en curso (`oApp.inicio` … `min(oApp.cierre, DATE())`). |
| **Clientes/Proveedores → 1. Todos** | `num1=0`, `num2=999999999999` | sin restricción efectiva |
| **Clientes/Proveedores → 2. Uno** | `num1 = num2 = id_cod` | un solo cliente/proveedor. Al entrar con `0` abre `cons_cli_pro` (buscador ⇒ nuestro Typeahead + Lupa). |
| **3. Ventas / 4. Compras** | `det1 = 'V'` / `'C'` | `c_v = det1` — **excluyente** |
| **5. Todas** | `num3=-1e11, num4=1e10, num5=0, num6=0` | sin restricción efectiva |
| **6. Pagadas** | `num3=num4=num5=num6=0` | `saldo = 0` |
| **7. Pendientes** | `num3=-1e11, num4=-1e-10, num5=1e-10, num6=1e11` | `saldo <> 0` (**incluye saldos negativos**: NC no aplicadas) |

Tras el `REQUERY()` hace `COUNT` → *"N comprobantes seleccionados"* y
`SUM litros, total, pagado, saldo` → los cuatro totalizadores del pie.

**El formulario NO filtra por `condic`: sólo lo muestra.**

### 1.3 Grilla (16 columnas, en el orden real de `ColumnOrder`)

`id_asto · c_v · cond · fecha · vencim · mesano · tipo · punto · numero · id_cod · detalle ·
cantidad · litros · total · pagado · saldo`

Pie: 4 cajas — `litros`, `total`, `pagado`, `saldo`.

### 1.4 Botón **Excel** (`cmdExcel.Click`)

Dos modos según el radio inferior:

- **Rápido sin formato:** `EXPORT TO ... XL5` (volcado crudo del cursor).
- **Con formato:** automatiza `Excel.Application` — título, línea de filtros, anchos de columna,
  cabeceras en negrita, `Style = "Currency"` en importes. Emite **20 columnas**
  (A…T) e incorpora datos que **no están en la grilla**:

  `ID_Asto · Fecha · Vencim · Comprobante(tipo-punto-numero) · Cod · Cliente/Proveedor ·
  Cantidad · litros · Total · Pagado · Saldo · **Acum.** · Condic · c_v · F.Pago ·
  Neto · IVA · Imp.Int. · No Grav · Tipo(clasificación del cli_pro)`

  `Acum.` es una **suma corrida global de `saldo`** en el orden del listado
  (`xAcum = xAcum + saldo` dentro del `SCAN`).

  > El CSV de muestra (`d:\borrador\FacturasPendientes.csv`, 84 filas) confirma el layout,
  > salvo que la versión en producción ya no emite `Cantidad` ni `litros` (18 columnas).

### 1.5 Botón **Imprimir** (`cmdImprimir.Click` + `reports\cons_lib_iva_pendientes.frx`)

Reporte **"RESUMEN DE CUENTAS"**, agrupado en dos niveles: `c_v` y luego `id_cod`.

- Encabezado de página: razón social (`oApp.razon`), título, texto de filtro (`oApp.detalle`),
  `DATETIME()` y `Página _PAGENO`.
- Encabezado de grupo: `iif(c_v='C','Proveedor: ','Cliente: ') + id_cod + '-' + detalle`.
- Detalle: `id_asto · fecha · tipo-punto-numero.concep · Total · Pagado · Pendiente · Saldo`.

  ⚠️ Verificado sobre el PDF de muestra midiendo coordenadas: la columna rotulada
  **"Pendiente"** (x≈448) contiene el **saldo del comprobante**, y la rotulada **"Saldo"**
  (x≈524) contiene el **acumulado corrido dentro del grupo** — al revés de lo que sugieren
  los títulos. Es un error de rotulado del FRX que **no vamos a replicar**.
- Pie de grupo: `Total <id_cod>-<detalle>` + subtotales de total, pagado y saldo.
- Resumen final: `TOTALES:` (en el PDF de muestra: 28.032.419,59 / 10.976.503,43 / 17.055.916,16).

### 1.6 Botón **Modificar** (`cmdModificar.Click`) — DESCARTADO

Alterna a modo edición: desbloquea las columnas `cantidad`, `litros` y `pagado` de la grilla;
el `Valid` del textbox de `pagado` ejecuta `replace saldo WITH total - this.Value`; al grabar
pide confirmación (*"Desea Modificar la Base Lib_IVA ?"*) y hace `TABLEUPDATE` **directo sobre
`lib_iva`**.

Es un parche manual de datos, sin asiento, sin auditoría y sin contrapartida en Tesorería.

**Confirmado con el usuario (2026-08-18):** en el VFP existía porque el `pagado` de `lib_iva`
era un campo materializado que se desincronizaba, y había que forzar a mano el estado "pagado".
En nuestro ERP ese problema no se plantea: `pagado` y `saldo` son **valores derivados** de las
aplicaciones de Órdenes de Pago y Recibos (`contable/services/saldos.py`), recalculados por los
signals y por las propias operaciones de tesorería.

⇒ **El listado es de sólo lectura. No lleva edición de importes ni acción de recálculo.** Ver §3.6.

---

## 2. Impacto en el modelo del ERP — mapeo de campos

### 2.1 Decisión de fondo: la fuente NO es el Libro IVA

El VFP lee `lib_iva`. En nuestro ERP **eso sería incorrecto**, por tres razones:

1. `LibroIvaVentas` **nunca se puebla** — `contable/services/contabilizacion.py` sólo crea
   `LibroIvaCompras` (líneas 285, 297). El lado Ventas quedaría vacío.
2. El Libro IVA se puebla **sólo con `condic in (1, 3)`** (regla inflexible de `.cursorrules`).
   Listar desde ahí haría **desaparecer los comprobantes `condic = 2` (Presupuestado) y
   `4` (Auditoría)**, que son exactamente los que el usuario necesita ver en un listado de gestión.
3. `pagado` / `saldo` viven en `Compra` y `Venta`, no en el Libro IVA.

**Fuente elegida:** `facturacion.Compra` y `facturacion.Venta`, unificadas en el servicio.
Neto / IVA / No Gravado / Exento / Otros ya existen en ambos modelos, así que **no hace falta
tocar el Libro IVA para ninguna columna**.

### 2.2 Mapeo columna por columna

| VFP (`lib_iva`) | Compra | Venta | Observación |
|---|---|---|---|
| `id_asto` | `asiento_id` | `asiento_id` | IntegerField, no FK (así está hoy) |
| `c_v` | `'C'` | `'V'` | constante derivada del filtro |
| `condic` | `condic` | `condic` | mostrar el nombre (Real/Presup./Ajuste/Auditoría) |
| `fecha` | `fecha` | `fecha` | |
| `vencim` | — | — | **no existe** en el modelo → ver decisión D1 |
| `mesano` | `periodo` | `periodo` | CharField(7) |
| `tipo` | `tipo.codigo` | `tipo.codigo` | FK `TipoComprobante` (`codigo`, `detalle`, `signo`) |
| `punto` | `punto` | `punto` | |
| `numero` | `numero` | `numero` | |
| `id_cod` | `proveedor.codigo_id` | `cliente.codigo_id` | PK del `ClienteProveedor` |
| `detalle` | `proveedor.razon_social` | `cliente.razon_social` | |
| `cantidad`, `litros` | — | — | **DESCARTADAS** — ver §2.2.1 |
| `total` | `total` | `total` | |
| `pagado` | `pagado` | `total − saldo` | ver §2.3 |
| `saldo` | `saldo` | `saldo` | |
| `neto` | `neto` | `neto` | |
| `iva` | `iva` | `iva` | |
| `imp_int` | — | — | no existe → se reemplaza por `exento` y `otros` |
| `no_grav` | `no_gravado` | `no_gravado` | |
| `concep` | `descripcion` | — | Venta no tiene descripción de cabecera |
| `f_p` (forma de pago) | — | — | **se omite** (no existe; y `condic` NUNCA es contado/cta.cte.) |
| `Cli_pro.tipo` | `proveedor.clasificacion` | `cliente.clasificacion` | |
| — | — | `estado` | 0 Activa / 1 Anulada / 2 Pend. Aut. / 3 Rechazada → ver D3 |

#### 2.2.1 Columnas descartadas: `cantidad` y `litros`

**Confirmado con el usuario (2026-08-18):** son herencia de verticales anteriores del sistema
(GNC / combustibles / agro). En el uso actual salen **siempre en cero** — se comprueba tanto en
la captura de pantalla (`0.00` en las 407 filas y en el totalizador) como en el CSV de muestra,
donde la versión en producción del ejecutable ya **ni siquiera las exporta** (18 columnas en
lugar de las 20 que escribe el código VFP).

⇒ No se replican en ninguna de las tres salidas (grilla, Excel, PDF). Tampoco el totalizador de
`litros`, que en el VFP ocupa la primera de las cuatro cajas del pie: **el pie queda con tres
totales — Total, Pagado y Saldo.**

### 2.3 Cómo se obtiene `pagado` — asimetría Compra / Venta

`contable/services/saldos.py`:

- **Compra** (`recalcular_saldo_compra`, líneas 34-56):
  `pagado = Σ OrdenPagoAplicacion.importe (orden_pago__anulado=False)` · `saldo = total − pagado`.
- **Venta** (`recalcular_saldo_venta`, líneas 59-79):
  **no existe campo `pagado`**; hay `cobrado` (cobro en el acto, lo setea Caja Mostrador y
  *no se recalcula*) y `saldo = total − cobrado − Σ ReciboAplicacion.importe (recibo__anulado=False)`.

**Regla unificadora del listado:** `pagado := total − saldo`.
Para Compra es una identidad exacta; para Venta equivale a `cobrado + Σ aplicaciones`,
que es justamente "lo que ya se cobró". Se usa la misma expresión en ambos lados,
así los totalizadores cierran (`Σ total = Σ pagado + Σ saldo`) por construcción.

### 2.4 Multiempresa

Regla inflexible: **toda** consulta acotada a `request.session['empresa_id']`, con el guard
estándar de redirect a `seleccion_empresa` si no hay empresa (patrón de
`facturacion/views.py:456-459`). `Compra` y `Venta` ya tienen índice `(empresa, fecha)`.

---

## 3. Diseño de la implementación

### 3.1 Pantalla — `/facturas-pendientes/`

Patrón A del proyecto (shell + grilla HTMX), igual a `tesoreria/ordenpago_listado.html`.

Barra de filtros (un solo `<form>` con `hx-get`, `hx-trigger="load, change, submit"`):

1. **Fecha desde / hasta** — precargadas con el ejercicio activo acotado a hoy (réplica de `Form.Init`).
2. **Operación:** ⦿ Compras ⦿ Ventas (excluyente, como el VFP — ver D2).
3. **Cliente/Proveedor:** ⦿ Todos ⦿ Uno → al elegir "Uno" se habilita el
   **Typeahead + Lupa obligatorio** (`typeahead_clientes` + `buscador_clipro` ya existentes).
4. **Estado:** ⦿ Todas ⦿ Pagadas (`saldo = 0`) ⦿ Pendientes (`saldo <> 0`).
5. **Condición (NUEVO, exigido por `.cursorrules`):** checkboxes Real / Presupuestado / Ajuste /
   Auditoría, con `1,2,3,4` marcados por defecto. Usa `contable.models.condic_opciones()`.

Grilla: `id_asto · cond · fecha · periodo · comprobante · cod · cliente/proveedor · total ·
pagado · saldo`, ordenada por `razon_social, fecha, tipo, numero`.
Importes con `{{ v|formato_ar }}` (`{% load formato_tags %}`), saldos negativos en rojo.

Pie fijo: contador *"N comprobantes seleccionados"* + totales de **Total / Pagado / Saldo**
(tres cajas, no cuatro: se descarta el totalizador de `litros` — §2.2.1).

Botones: **Excel** y **PDF**. Nada más: la grilla es de sólo lectura (§3.6).

### 3.2 Servicio de consulta — `facturacion/services/facturas_pendientes.py` `[NEW]`

```python
@dataclass
class FiltroFacturasPendientes:
    empresa_id: int
    operacion: str          # 'C' | 'V'
    desde: date
    hasta: date
    entidad_id: int | None
    estado: str             # 'todas' | 'pagadas' | 'pendientes'
    condics: list[int]      # subconjunto de (1,2,3,4)

def consultar(f) -> tuple[list[FilaFactura], TotalesFacturas]
```

- Una sola query sobre `Compra` **o** `Venta` (no `UNION`: son excluyentes) con
  `select_related('tipo', 'proveedor'|'cliente')` y `.only(...)` de los campos usados.
- Filtro de estado: `estado='pagadas'` → `Q(saldo=0)`; `'pendientes'` → `~Q(saldo=0)`.
- Devuelve filas normalizadas (mismo `dataclass` para C y V) → los templates, el Excel y el PDF
  consumen **una sola estructura**, sin ramas por operación.
- Totales con `aggregate(Sum(...))` sobre el queryset **sin truncar**.
- El **acumulado corrido** (`Acum.`) se calcula en Python al iterar las filas ya ordenadas,
  y se expone en dos variantes: `acum_global` (como el Excel del VFP) y `acum_grupo`
  (reinicia por entidad, como el PDF).

### 3.3 Vistas — `facturacion/views_facturas_pendientes.py` `[NEW]`

| Función | Ruta | `name` |
|---|---|---|
| `facturas_pendientes_listado` | `facturas-pendientes/` | `facturas_pendientes` |
| `facturas_pendientes_grilla` | `facturas-pendientes/grilla/` | `facturas_pendientes_grilla` |
| `facturas_pendientes_excel` | `facturas-pendientes/exportar-excel/` | `facturas_pendientes_excel` |
| `facturas_pendientes_pdf` | `facturas-pendientes/exportar-pdf/` | `facturas_pendientes_pdf` |

> Se implementaron como **funciones** y no como CBV, para quedar alineadas con
> `tesoreria/views_listados.py`, que es el listado que sirve de modelo.

**Las cuatro son `GET` y de sólo lectura.** No hay ninguna ruta `POST`: el listado no escribe
en la base.

Todas con `@login_required` y el guard de `empresa_id`. Se registran en `config/urls.py`
(URLconf raíz monolítica, sin namespaces — convención vigente del proyecto).

### 3.4 Excel — `facturacion/services/facturas_pendientes_excel.py` `[NEW]`

`openpyxl`, calcando el estilo de `facturacion/services/clientes_excel.py`
(fila 1 empresa merged 14pt bold · fila 2 título · fila 3 filtros + fecha de emisión ·
**fila 5 headers `PatternFill("solid", fgColor="0F172A")` + fuente blanca bold** ·
datos desde la 6 · `number_format='#,##0.00'` · autoajuste de ancho).

Columnas (equivalente moderno de las 20 del VFP):

`ID Asiento · Fecha · Período · Comprobante · Cód. · Cliente/Proveedor · Total · Pagado ·
Saldo · Acum. · Condición · C/V · Neto · IVA · No Gravado · Exento · Otros · Clasificación ·
Descripción`

Fila final de totales en negrita. Sin límite de filas.

### 3.5 PDF — `templates/facturacion/pdf/facturas_pendientes.html` `[NEW]`

`xhtml2pdf` vía `facturacion/services/reportes_pdf.py::render_pdf_response` (ya existe).
Réplica del "RESUMEN DE CUENTAS" **con los rótulos corregidos**:

- Encabezado: empresa · "RESUMEN DE CUENTAS" · texto de filtros · fecha/hora · Página N de M.
- Un grupo por cliente/proveedor: `Proveedor: 6 - ZG MULTITEC SRL`.
- Detalle: `Id Asto · Fecha · Comprobante (+ descripción) · Total · Pagado · Saldo · Acumulado`.
- Subtotal por grupo y `TOTALES:` final.

### 3.6 Listado de sólo lectura — sin edición ni recálculo

El botón **Modificar** del VFP no tiene reemplazo (§1.6). El módulo **no escribe en la base**:

- ningún importe es editable en la grilla;
- no hay acción de "recalcular saldos" ni ninguna otra ruta `POST`;
- el único vínculo de escritura sigue siendo el circuito normal: aplicar una Orden de Pago o un
  Recibo dispara `recalcular_saldo_compra` / `recalcular_saldo_venta`
  (`tesoreria/views_htmx.py:441, 661`, `contable/services/reversion.py:95, 143`,
  `facturacion/signals.py`).

**Implicancia de diseño:** como el listado sólo lee, no necesita `transaction.atomic()` ni
`select_for_update()` — la regla de transaccionalidad de `.cursorrules` aplica a quien escribe
los saldos, no a quien los consulta. Sí conviene un `.only(...)` ajustado, porque el volumen es
alto (400+ filas por consulta) y las tablas son anchas.

Si en algún momento apareciera una desincronización real de saldos, la herramienta correcta es
un comando de management (`python manage.py recalcular_saldos --empresa N`), no un botón en un
reporte. Fuera del alcance de este plan.

### 3.7 Volumen y truncado

El VFP muestra 407 filas sin paginar. Nuestros listados truncan a 500 (`views.py:497`, `:1065`).
Se mantiene el corte en **500 filas en la grilla**, pero:

- los **totales y el contador se calculan sobre el conjunto completo** (`aggregate`), no sobre
  el slice — para que el pie nunca mienta;
- si hubo truncado se muestra un aviso explícito *"Se muestran las primeras 500 de N filas;
  el Excel y el PDF incluyen todas"*;
- **Excel y PDF no truncan.**

---

## 4. Consultas y validaciones de base de datos

- Índices existentes que cubren el filtro principal: `Compra (empresa, fecha)` y
  `Venta (empresa, fecha)` (`facturacion/models.py:276-280` y `:568-572`).
- El `ORDER BY razon_social` obliga a un JOIN con `facturacion_clienteproveedor`, que ya tiene
  `(empresa, razon_social)`.
- **A debatir (D4):** para el modo *Pendientes* sobre históricos largos podría convenir un
  **índice parcial** `CREATE INDEX ... ON facturacion_compra (empresa_id, fecha) WHERE saldo <> 0`.
  Propuesta: **no crearlo en esta iteración**; medir primero con `EXPLAIN ANALYZE` sobre datos
  reales y decidir en un plan aparte.
- Sin migraciones de esquema, **salvo** que se apruebe D1 (campo de vencimiento).

---

## 5. Archivos afectados

| Acción | Archivo |
|---|---|
| `[NEW]` | `facturacion/services/facturas_pendientes.py` |
| `[NEW]` | `facturacion/services/facturas_pendientes_excel.py` |
| `[NEW]` | `facturacion/views_facturas_pendientes.py` |
| `[NEW]` | `templates/facturacion/reportes/facturas_pendientes.html` |
| `[NEW]` | `templates/facturacion/reportes/partials/facturas_pendientes_grilla.html` |
| `[NEW]` | `templates/facturacion/pdf/facturas_pendientes.html` |
| `[NEW]` | `facturacion/tests/test_facturas_pendientes.py` |
| `[MODIFY]` | `config/urls.py` — 5 rutas nuevas |
| `[MODIFY]` | `templates/base.html` — ítem de sidebar (bajo Facturación o Reportes) |
| `[MODIFY]` | `docs/walkthrough.md` — entrada de bitácora |
| `[MODIFY]` | `docs/GUIA_MODULAR.md` — alta del módulo |

---

## 6. Plan de pruebas

### 6.1 Automatizadas — `facturacion/tests/test_facturas_pendientes.py`

1. **Aislamiento multiempresa:** comprobantes de dos empresas; el listado de la empresa A
   nunca devuelve filas de la B.
2. **Estado = Pagadas** ⇒ sólo `saldo == 0`.
3. **Estado = Pendientes** ⇒ sólo `saldo != 0`, **incluyendo una NC con saldo negativo**
   (réplica exacta del rango `-1e11..-1e-10 OR 1e-10..1e11`).
4. **Filtro `condic`:** una compra por cada valor 1/2/3/4; verificar que la selección los filtra
   y que el default (1,2,3,4) los trae a todos.
5. **`pagado = total − saldo`:** compra con OP parcial aplicada ⇒ `pagado` coincide con
   `Σ OrdenPagoAplicacion`; venta con `cobrado` + recibo aplicado ⇒ `pagado` coincide con la suma.
6. **Totales sobre el conjunto completo:** con más de 500 filas, `Σ total` del pie ≠ suma del slice.
7. **Acumulado:** la última fila de `acum_global` == `Σ saldo`.
8. **Excel:** status 200 y `Content-Type` de xlsx; **PDF:** status 200 y `application/pdf`.
9. **Sólo lectura:** tras recorrer las cuatro vistas (grilla, Excel, PDF y la página shell),
   los `total` / `pagado` / `saldo` de los comprobantes quedan intactos — el listado no escribe.
10. **Ventas anuladas:** una venta con `estado=1` no aparece por defecto **ni suma en los
    totalizadores**; con `incluir_anuladas=True` aparece marcada.

### 6.2 Manuales

1. Contra el VFP: mismo rango de fechas, Compras, Todas ⇒ comparar contador y los tres totales
   con la pantalla original (`379.985.633,53 / 250.090.908,81 / 129.894.724,72` en el ejemplo de
   Ventas; `28.032.419,59 / 10.976.503,43 / 17.055.916,16` en el PDF de Compras).
2. Typeahead + Lupa de cliente/proveedor: seleccionar uno y verificar que la grilla se acota.
3. Excel: abrir el `.xlsx` y verificar formato es-AR, columna `Acum.` y fila de totales.
4. PDF: verificar cortes de grupo, subtotales por entidad y `TOTALES:` final.
5. Verificar que ningún importe se formatea a mano (todo por `.fInputAR` / `|formato_ar`).

---

## 7. Decisiones

| # | Decisión | Resolución |
|---|---|---|
| **D1** | **Fecha de vencimiento.** El VFP muestra `vencim`; ni `Compra` ni `Venta` la tienen. | ✅ **RESUELTA (2026-08-18):** se omite la columna en v1. Agregar `fec_vto` a ambos modelos queda para un plan aparte (afecta carga, asiento y vencimientos de tesorería). Sin migraciones en este plan. |
| **D2** | **Ventas y Compras a la vez.** El VFP obliga a elegir una. | ✅ **RESUELTA (2026-08-18):** se mantiene excluyente (radio Compras \| Ventas), igual que el original. Una sola query por consulta, sin `UNION` ni unificación de signo. |
| **D3** | **Ventas anuladas** (`estado = 1`) y pendientes de autorización (`2`/`3`). | ✅ **RESUELTA (2026-08-18):** por defecto `estado != 1`, con checkbox **"Incluir anuladas"** apagado que permite verlas. Los estados `2` (Pend. Autorización) y `3` (Rechazada) **sí** se muestran siempre. |
| **D4** | **Índice parcial** para el modo Pendientes. | ⏳ Abierta, no bloqueante. No se crea ahora; medir con `EXPLAIN ANALYZE` sobre datos reales y decidir en un plan aparte. |
| **D5** | **Ubicación en el menú.** | ✅ **RESUELTA en la implementación:** "Facturas Pendientes" aparece en los dos submenús — en **Compras** con `?operacion=C` y en **Ventas** con `?operacion=V`. Es la misma pantalla; el querystring la abre con la operación ya elegida. |

### Consecuencias de D3 sobre el diseño

- `FiltroFacturasPendientes` suma el campo `incluir_anuladas: bool = False`.
- El filtro sólo aplica a `Venta` (`Compra` no tiene campo `estado`).
- La grilla muestra una columna/badge de estado **únicamente** cuando el checkbox está activo
  o cuando la fila no es Activa, para no ensuciar el caso normal.
- Test adicional: una venta anulada no aparece por defecto, aparece con el checkbox, y **no**
  contamina los totalizadores en el caso por defecto.
