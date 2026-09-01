# Plan 033 — Caja Diaria de Tesorería

**Fecha:** 28/07/2026
**Origen:** Migración de la operatoria del formulario VFP `B-304: tran_caja` (Caja Diaria).
**Referencia legacy:** tablas `enc_caja_diaria` / `aux_caja_diaria`; salidas `CajaDiaria.xlsx` y `CajaDiaria.pdf`.

---

## 1. Qué es (y qué NO es)

La Caja Diaria **es un reporte de pantalla** de los movimientos de fondos de la caja de tesorería y de
los saldos disponibles. Le permite al tesorero ver los movimientos bajo su responsabilidad y verificar
si tiene todo registrado o le falta algo.

**NO es** un circuito nuevo de carga, ni un módulo con lógica contable propia. No genera asientos: los
lee. Toda la registración sigue ocurriendo en Recibos, Órdenes de Pago y Compras.

### Distinción clave: caja tesorería ≠ caja mostrador

| | Caja Mostrador | Caja Tesorería (esta) |
|---|---|---|
| Alcance | Por cajero y turno | **Por sucursal** |
| Apertura | Fondo fijo del cajón | Arrastre del cierre anterior |
| Control | Arqueo ciego + rendición | Sin arqueo: control por reporte |
| Modelo | `Caja.tipo = 'M'` | `Caja.tipo = 'T'` |

Ambas conviven sin mezclarse. La caja de tesorería **activa** de una sucursal es la `CajaSesion` con
`estado='A'` de su `Caja` de tipo `'T'`.

---

## 2. Decisiones de diseño acordadas con el usuario

1. **`asiento_id` es el común denominador.** Vincula caja diaria, compras, libro IVA, asiento
   enc/mov, recibos y órdenes de pago. El reporte se arma sobre los asientos de la caja.
2. **Saldos:** `Neto = Efectivo + Dólares + Valores`. Banco, Tarjetas y Otros **NO** arrastran saldo,
   pero **sí** informan su movimiento neto del día. Esto corrige la inconsistencia del legado, donde el
   "Neto" de Saldos Finales en pantalla restaba el movimiento bancario (mostraba 4.237.293,60) mientras
   el Excel y el arrastre al día siguiente usaban Efectivo+Valores (9.737.293,60, valor correcto).
3. **PDF agrupado y ordenado por jerarquía contable**, con un único subtotal por cuenta. El legado
   quebraba por cambio de cuenta consecutivo y repetía la misma cuenta varias veces (ej. *113 - SUELDOS
   Y JORNALES A PAGAR* aparecía 3 veces en la caja 980); se corrige.
4. **Filtro Real / Presupuestado / Ambos** sobre `condic` (1=Real/Fiscal, 2=Presupuestado/No Fiscal).
5. **Accesos rápidos:** en VFP eran 5 formularios (Recibos, Recibo Clientes, Orden Pago, Ord.Pago Prov.,
   Compras Ctado). En el ERP están unificados en `Recibo.tipo` (C/S) y `OrdenPago.tipo` (P/S), por lo que
   quedan **3 accesos**: Recibo, Orden de Pago y Compra Contado.
6. **Selector de sucursal**, para que el administrador controle cajas de tesorería de otras sucursales.

---

## 3. Impacto en archivos

### 3.1 Modelos

**`contable/models.py`**
- `Cuenta.tipo_disponibilidad` (nuevo, `CharField(max_length=3, blank=True)`): clasifica la cuenta en
  una columna del parte. Choices: `EFE` Efectivo, `DOL` Dólares, `VAL` Valores en cartera, `BCO` Banco,
  `TAR` Tarjetas, `OTR` Otros. Vacío = no es cuenta de disponibilidad. Indexado.
- `Asiento.sesion_caja` (nuevo, FK a `tesoreria.CajaSesion`, null): la caja a la que pertenece el
  asiento. **Es el motor del reporte.** Null en asientos que no tocan caja.

**`tesoreria/models.py`**
- `CajaSesion`: se agregan `numero` (correlativo por empresa, equivale al 980/981/982 del VFP),
  `fecha_operativa` (se estampa al cerrar; mientras está abierta va en null, igual que la caja 982),
  saldos iniciales desglosados `si_efectivo` / `si_dolares` / `si_valores` y finales congelados
  `sf_efectivo` / `sf_dolares` / `sf_valores`. El `saldo_inicial` existente **no se toca** (lo usa la
  caja mostrador).
- `OrdenPago.sesion_caja` (nuevo, FK, null): `Recibo` ya la tiene ([tesoreria/models.py:102]) pero no
  se completaba; `OrdenPago` no la tenía.

**Migraciones:** una de esquema + una de datos que hace el backfill de `tipo_disponibilidad` leyendo
`ParametrosContables` (`cta_caja`, `cta_caja_mostrador`, `cta_caja_central` → EFE; `cta_dolar`,
`cta_caja_mostrador_dolares`, `cta_caja_central_dolares` → DOL; `cta_valores_cartera` → VAL;
`cta_tarjetas_a_cobrar` → TAR) y `CuentaBancaria.cuenta_contable` → BCO.

### 3.2 Servicio

**`tesoreria/services/caja_diaria.py`** (nuevo):
- `get_caja_tesoreria(empresa_id, sucursal_id)` — devuelve/crea la `Caja` tipo `'T'` de la sucursal.
- `get_o_crear_sesion_activa(caja, usuario)` — la caja activa, creándola con arrastre si no existe.
- `armar_caja_diaria(sesion, condic=None)` — el corazón del reporte.
- `cerrar_caja(sesion, usuario)` — cierre transaccional.

**Regla de armado de cada línea del detalle:** por cada asiento de la caja se separan sus líneas en
*disponibilidades* (las que tienen `tipo_disponibilidad`) y *contrapartidas* (el resto, que es lo que el
VFP muestra en las columnas `cta` y `concepto contable`). Se emite **una línea por contrapartida**, con
el desglose por medio tomado del lado de disponibilidades. Con una sola contrapartida (el caso normal)
es directo; con varias se prorratea por su importe. Signo: positivo = ingreso a la caja.

### 3.3 Vistas, URLs y templates

- `tesoreria/views_caja_diaria.py` (nuevo): pantalla, refresco HTMX de la grilla, cierre, Excel y PDF.
- `tesoreria/urls.py`: 6 rutas nuevas bajo `caja-diaria/`.
- `templates/tesoreria/caja_diaria.html` + `partials/caja_diaria_grilla.html` (nuevo).
- `templates/tesoreria/pdf/caja_diaria_pdf.html` (nuevo), sobre `xhtml2pdf` como el resto de reportes.
- `tesoreria/services/caja_diaria_export.py` (nuevo): Excel con `openpyxl`, replicando el layout actual
  del usuario (encabezado "Caja N° X de fecha DD/MM/AAAA - Sucursal", grilla y bloque de saldos).
- `templates/tesoreria/index.html`: tarjeta de acceso al nuevo módulo.

### 3.4 Estampado del `caja_id`

- `tesoreria/views_htmx.py`: `procesar_recibo` y `procesar_orden_pago` ya buscan la `CajaSesion` activa
  pero **no la guardaban en el comprobante**. Se estampa en el comprobante y en el asiento.
- Las funciones de contabilización aceptan la sesión para grabarla en el `Asiento`.

---

## 4. Reglas de negocio y validaciones

1. **Multi-tenant:** toda consulta filtra por `empresa_id` de sesión (regla inflexible del proyecto).
2. **Transaccionalidad:** `cerrar_caja()` corre en `transaction.atomic()` con `select_for_update()`
   sobre la sesión, para impedir cierres concurrentes o movimientos durante el cierre.
3. **Una sola caja activa por sucursal:** validado antes de abrir.
4. **Sobre cajas cerradas** solo se consulta, imprime y exporta; los accesos de carga se deshabilitan
   (igual que el VFP, que grisa los botones en las cajas ya cerradas).
5. **Importes:** todos con `{{ valor|formato_ar }}` en displays y `.fInputAR` en inputs, según la regla
   de formato del proyecto.

## 5. Plan de pruebas

**Automatizadas** (`tesoreria/tests/test_caja_diaria.py`):
1. Arrastre encadenado de saldos entre cajas sucesivas.
2. Banco/Tarjetas mueven el neto del día pero **no** alteran el saldo final.
3. Clasificación correcta de un asiento con varias contrapartidas (prorrateo).
4. Filtro `condic` (Real / Presupuestado / Ambos).
5. Cierre: congela saldos, estampa fecha y abre la siguiente caja con el arrastre.
6. Aislamiento multiempresa y por sucursal.

**Manuales:** cargar un recibo y una OP con la caja abierta, verificar que aparezcan en la grilla con su
cuenta de contrapartida, contrastar el bloque de saldos, exportar a Excel y PDF.
