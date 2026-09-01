# Plan 047 — Reporte "Balance de Saldos Mensuales" (Sumas y Saldos Anual)

- **Fecha:** 15/08/2026
- **Módulo:** Contable → Reportes
- **Origen:** migración del formulario VFP `c:\jm_soft\balances\forms\sum_sal_anual.scx` (C-204)
- **Estado:** FASES 1 a 7 EJECUTADAS (15/08/2026) — pendientes: 8 (medición del índice) y 9 (contraste manual)

---

## 1. Objetivo

Incorporar al módulo contable un reporte tipo **sumas y saldos anual**, que para cada cuenta del
plan muestre en una sola grilla:

1. **Saldo de apertura** del ejercicio.
2. **Movimiento neto mensual** (debe − haber) de cada mes del ejercicio.
3. **Saldo al cierre** = apertura + Σ de los movimientos netos mensuales.

Es el reporte que hoy resuelve el formulario `sum_sal_anual` del sistema VFP, y que el usuario
utiliza como base del análisis de gestión (evolución mensual de resultados) y de armado de balance.

### Muestras de referencia analizadas

| Archivo | Contenido |
|---------|-----------|
| `d:\borrador\saldos_mensuales.csv` | Export completo (todas las cuentas), signo contable natural |
| `d:\borrador\saldos_mensuales_resultados.csv` | Export filtrado `tipo='R'`, con importes multiplicados por −1 |

El fuente VFP fue leído y verificado; la comparación completa está en el **Anexo A**.

---

## 2. PRERREQUISITO — Renumeración y semántica del campo `condic`

Este reporte no se puede construir sobre la semántica actual de `condic`. La fase 1 redefine el
campo por completo. **Es un cambio transversal y es la primera entrega.**

### 2.1 La tabla definitiva

| Valor | Nombre en UI | Significado operativo |
|:-----:|--------------|-----------------------|
| **1** | **Real** | Registros fiscales. El **90 % de los movimientos**. Circuito completo: contabilidad, Libro IVA, DDJJ, estados contables. |
| **2** | **Presupuestado** | Movimientos **no fiscales**. Gastos **reales** de la empresa sin respaldo documental válido (servimoto, almacén del barrio, taxi por un trámite). No se declaran en impuestos ni en los estados contables formales. Sirven **sólo para el análisis de gestión**. |
| **3** | **Ajuste** | Factura **válida y a nombre de la empresa**, pero cuyo pago **no sale de la empresa**: el dueño la abona con fondos propios (típico: combustible del vehículo particular usado para trabajar) y no retira el dinero. **Se toma en contabilidad y en las DDJJ de IVA y Ganancias**, porque la factura es de la empresa, pero **se excluye del análisis de gastos** porque no es una erogación de la empresa. |
| **4** | **Auditoría** | **Ajustes de auditoría**: los que el estudio contable remite a la empresa para su registración una vez confeccionados los estados contables. Deben poder filtrarse e identificarse fácilmente. |
| **5** | **Apertura** | Asiento de apertura del ejercicio. |
| **6** | **Refundición** | Asiento de refundición de cuentas de resultado. |
| **7** | **Cierre** | Asiento de cierre del ejercicio. |

> Los valores **1 a 4 coinciden exactamente con la numeración del VFP** (Real / Presupuestado /
> Ajuste / Auditoría), con lo cual los reportes y la operatoria del usuario mapean 1:1 con el
> sistema anterior.

### 2.2 Cómo se registra cada uno

- **`condic = 3` se carga como cualquier otra factura**, contra proveedores varios, con el mismo
  circuito contable que una compra normal. **No** va contra cuenta particular de socios. El `condic`
  es únicamente la etiqueta que la distingue; el ajuste patrimonial lo terminan de acomodar los
  auditores con un asiento `condic = 4`.
- **`condic = 4` no se carga por la operatoria normal.** Más adelante se construirá una *captura de
  asientos de auditoría* que escribe **únicamente** en `cble_asiento_enc` y `cble_asiento_mov`. Estos
  asientos **no generan registros en ninguna otra tabla** (ni Libro IVA, ni retenciones).
- **`condic = 5, 6 y 7` los genera el sistema**, nunca un combo de usuario.

### 2.3 El mecanismo de compensación 2 ↔ 3

Vale documentarlo porque explica por qué existen ambos:

- El **`2`** baja el resultado **real** pero no el fiscal (gasto real sin factura).
- El **`3`** baja el resultado **fiscal** sin que salga plata de la empresa (factura sin erogación).

Uno amortigua al otro, y el resultado fiscal termina aproximándose al real.

### 2.4 Las tres lentes

De la semántica anterior se desprenden tres vistas distintas sobre los mismos asientos. Es la clave
para entender cualquier filtro de `condic` del sistema:

| Lente | `condic` | Para qué |
|-------|:--------:|----------|
| **Gestión** | **1 + 2** | Gastos reales de la empresa. Excluye el `3`: lo paga el socio. |
| **Fiscal** (Libro IVA, DDJJ IVA/Ganancias) | **1 + 3** | Facturas válidas a nombre de la empresa. Excluye el `2`: sin respaldo. |
| **Estados contables formales** | **1 + 3 + 4** | Todo lo respaldado, más los ajustes del estudio. |
| *(Estructurales)* | 5, 6, 7 | Apertura, refundición y cierre. |

### 2.5 Impacto — auditoría de todos los usos de `condic`

Relevamiento completo del código. Son **11 puntos**, todos inventariados:

| Archivo | Situación actual | Acción |
|---------|------------------|--------|
| `.cursorrules` | Tabla de `condic` con 1/2/3 | **Reescribir** con la tabla de §2.1 + las tres lentes de §2.4 (fuente de verdad) |
| `CLAUDE.md` | Bullet resumen que enumera 1/2/3 | Actualizar |
| `contable/models.py:64-70` | Comentario del campo `condic` | Reescribir con los 7 valores |
| `contable/models.py:222` | *"Solo se generan registros para comprobantes FISCALES (condic=1)"* | Corregir: `condic ∈ {1, 3}` |
| **`contable/services/contabilizacion.py:542-544`** | `if compra.condic == 1:` → alimenta Libro IVA | **`if compra.condic in (1, 3):`** — el `3` va a Libro IVA y DDJJ (§2.1) |
| `contable/services/cierre.py:98-105` | Crea el asiento sin `condic` → queda en `1` | `condic=6` (es una **refundición**, no un cierre — ver §2.6) |
| `contable/views_htmx.py:385,387,392,396` | `_calcular_balance` referencia `condic=3` como apertura | `condic=5` |
| `migracion/scripts/02_migrar_asientos.py:50` | `condic=3, # Apertura` | `condic=5` |
| `templates/contable/partials/detalle_asiento.html:11` | Badge `{% elif asiento.condic == 3 %}` | Badges para los 7 valores |
| `templates/contable/partials/libro_diario.html:52-62` | Checkboxes 1, 2, 3 | Checkboxes 1, 2, 3, 4 + 5, 6, 7 |
| `templates/contable/partials/libro_mayor.html:123` | Checkbox `value="3"` rotulado *Apertura* | Idem |
| **Data migration** | — | `UPDATE ... SET condic=5 WHERE condic=3` y `SET condic=6 WHERE concepto ILIKE 'CIERRE DE EJERCICIO%'` |

**Sin cambios (verificado):**

- `contable/forms.py:90-93` — `CONDIC_CHOICES` con 1 y 2. El `3` se habilitará más adelante para
  ciertos usuarios como tercera opción "Ajuste"; el `4` nunca se carga a mano.
- `facturacion/views.py:136` — autorización ARCA con `venta.condic == 1`. **Correcto tal cual**: una
  venta `condic = 3` se emite siempre primero como `1` (fiscal, autorizada ante ARCA) y recién
  después un usuario habilitado le cambia el `condic` en todas las tablas intervinientes. Ese
  desarrollo es posterior y ajeno a este plan.
- Subsistema de retenciones y `RetPercSufrida` — no los toca el `3`.

### 2.6 El costo de la renumeración: prácticamente nulo

| Factor | Estado |
|--------|--------|
| Migración de esquema | **No hace falta.** `condic` es un `IntegerField` pelado, sin `choices` ni `CheckConstraint`. Es un `UPDATE`, no un `ALTER TABLE`. |
| Datos a migrar | **Ninguno.** Conteo real de la base: `condic=1` → 40 asientos, `condic=2` → 6. **Cero** con `condic=3`, **cero** asientos de cierre. La data migration se escribe igual (idempotente) por si otra base sí tiene datos. |
| Estado a medio construir | **No hay.** El `condic=4` todavía no se implementó, así que no hay nada que desenredar. |

### 2.7 El `condic = 7` (Cierre) todavía no existe como funcionalidad

Hoy `procesar_cierre_ejercicio` (`contable/services/cierre.py:31`) hace **sólo la refundición**:
toma las cuentas `tipo='R'`, las cancela y manda la diferencia a `cta_resultado_ejercicio`. **No
existe ningún asiento que cierre las cuentas patrimoniales.**

Por eso el reparto queda:

- **`condic = 6`** → renombrar lo que ya existe (la refundición actual).
- **`condic = 7`** → **desarrollo nuevo**, fuera del alcance de este plan.

El diseño previsto por el usuario para más adelante: al crear un ejercicio nuevo, el sistema toma el
asiento `condic = 7` del anterior y lo copia como `condic = 5` (apertura) en el nuevo. Para que eso
funcione, el cierre debe cancelar **todas** las cuentas, patrimoniales incluidas, de modo que la
apertura sea su contra-asiento. Es un buen diseño: garantiza que la apertura balancee sola y
coincida exactamente con el saldo de cierre, sin recalcular nada. El número queda reservado desde ya.

---

## 3. Estructura del reporte

### 3.1 Columnas

| Columna | Origen | Observaciones |
|---------|--------|---------------|
| `Codigo` | `Cuenta.id` | En VFP es el `codigo` legacy |
| `Sumariza` | `Cuenta.sumariza_id` | Sólo para el rollup; en pantalla no se muestra |
| `Jerarquia` | `Cuenta.jerarquia` | Define el nivel de indentación (`1`, `11`, `111`, `111001`) |
| `Detalle` | `Cuenta.cuenta` | |
| `Imp` | `Cuenta.imputable` | `1` = imputable (hoja), `0` = sumarizadora |
| `Apertura` | calculado | Ver §3.3 |
| `AAAAMM` × N | calculado | Una columna por mes del ejercicio. Ver §3.2 |
| `Total` | calculado | `Apertura + Σ meses` |
| `Tipo` | `Cuenta.tipo` | `A`/`P`/`N`/`R` |
| `Bce`, `Pres`, `Econ`, `Fciero` | `id_bce`, `id_pre`, `id_ec`, `id_fc` | Sólo en el export Excel, por compatibilidad |

### 3.2 Columnas mensuales dinámicas

La cantidad y el rótulo de las columnas **dependen del ejercicio seleccionado**; no son doce
columnas fijas. Se recorre año-mes desde `Ejercicio.inicio` hasta `Ejercicio.cierre` inclusive:

```python
def periodos_ejercicio(ejercicio, tope=24):
    """[(2025, 4), (2025, 5), ..., (2026, 3)] para un ejercicio abr/2025 - mar/2026."""
    y, m = ejercicio.inicio.year, ejercicio.inicio.month
    fin = (ejercicio.cierre.year, ejercicio.cierre.month)
    out = []
    while (y, m) <= fin and len(out) < tope:
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out
```

Casos cubiertos:

- Ejercicio ene/2025 – dic/2025 → `202501 … 202512` (caso de la captura).
- Ejercicio abr/2025 – mar/2026 → `202504 … 202603` (arranca en abril).
- Primer ejercicio irregular (sep/2025 – dic/2025) → `202509 … 202512` (4 columnas).

El tope de 24 es un cortafuegos ante un `Ejercicio` mal cargado; no un límite funcional.

### 3.3 Reparto por `condic` — REGLA CENTRAL DEL REPORTE

```
Columna Apertura   ←  condic = 5              (siempre, y sólo esto)
Columnas mensuales ←  condic ∈ {1, 2, 3, 4}   (el usuario elige cuáles ver — §5.1)
Nunca entran       ←  condic ∈ {6, 7}         (anularían los resultados del ejercicio)
```

Universos disjuntos que **no dependen de la fecha**: un asiento de apertura fechado 01/01/2025 va a
la columna Apertura, nunca a `202501`.

**Cuentas de resultado:** tienen Apertura 0 por naturaleza (se verifica en el CSV de muestra:
`INGRESOS … Apertura = 0,00`). No se fuerza por código, sale solo.

#### No hay ningún otro cálculo

El reporte es **sobre el ejercicio contable activo**. Por lo tanto:

> **Apertura + 12 meses = saldo al cierre.**
> Exactamente el mismo número que el Sumas y Saldos muestra en su saldo final
> (con los cuatro `condic` tildados).

No se arrastran movimientos anteriores al inicio del ejercicio, no hay fallback, no hay saldo
inferido. Apertura es un asiento `condic = 5`; los meses son el movimiento neto de cada mes.

Es una **diferencia deliberada** con `_calcular_balance` (`contable/views_htmx.py:385`), que además
del asiento de apertura suma los movimientos anteriores a `fecha_desde`. Ese comportamiento **no se
replica acá**, y el servicio nuevo no debe reusar esa parte del balance.

### 3.4 Movimiento mensual

```
mes(AAAAMM) = Σ(debe − haber) de líneas de asientos con:
    asiento.anulado  = False
    asiento.ejercicio = <el activo>            (§5.0)
    asiento.condic   ∈ condics_tildados        (subconjunto de {1,2,3,4} — §5.1)
    asiento.fecha    dentro del mes AAAAMM
    + filtros de sucursal y módulo
```

### 3.5 Rollup jerárquico

Sólo se agrega contra la base de datos por **cuentas imputables**. Las sumarizadoras se completan
acumulando de abajo hacia arriba por `sumariza_id`, recorriendo las cuentas ordenadas por
`jerarquia` descendente — el mecanismo ya probado en `_calcular_balance` y el mismo del VFP.

Verificado contra el CSV: `CAJA Y BANCOS (111)` = suma exacta de sus hijas `111001…111018` en todas
las columnas.

### 3.6 Signo

Comparando ambos CSV quedó determinada la regla, y el fuente VFP la confirma:

| Modo | Signo | Fila TOTALES |
|------|-------|--------------|
| **Todas las cuentas** | Natural (`debe − haber`) | **0,00 en cada mes** → control de partida doble |
| **Solo Resultados** (`tipo='R'`) | Invertido (`× −1`) | **Resultado neto del mes** (ganancia positiva) |

Comprobación numérica sobre las muestras:

- `saldos_mensuales.csv` → `INGRESOS` 202501 = `-45.192.021,77`; TOTALES = `0,00` en los 12 meses.
- `saldos_mensuales_resultados.csv` → `INGRESOS` 202501 = `45.192.021,77`; TOTALES 202501 =
  `-4.195.090,32` y Total anual `191.359.116,16` (= 1.683.427.656,03 − 1.492.068.539,87).

#### Dónde se aplica la inversión

**Sólo en la exportación a Excel. En pantalla, siempre signo contable natural.**

Motivo: el operador de esta pantalla necesita ver el movimiento **tal cual quedó registrado**, porque
el signo es el dato que le permite detectar si se cargó bien. Un ingreso tiene que verse en el haber
(negativo); si aparece positivo, hay un error de carga. Invertirlo en pantalla escondería justamente
el error que el usuario está buscando.

Coincide con el fuente VFP (Anexo A): `xSig` sólo existe dentro del procedimiento de exportación a
Excel; el `Click` del radio `opgResultado` se limita a `SET FILTER TO tipo = 'R'`.

| Salida | Modo "Todas" | Modo "Solo Resultados" |
|--------|--------------|------------------------|
| **Pantalla** | Signo natural | Signo natural |
| **Excel** | Signo natural | × (−1) |

---

## 4. Impacto en archivos

### 4.1 Nuevos

| Archivo | Contenido |
|---------|-----------|
| `contable/services/saldos_mensuales.py` | **Núcleo de cálculo.** `calcular_saldos_mensuales(...)`, función pura sin `request` |
| `templates/contable/saldos_mensuales.html` | Página con encabezado + panel de filtros |
| `templates/contable/partials/saldos_mensuales.html` | Grilla (target HTMX) |
| `contable/tests/test_saldos_mensuales.py` | Suite de pruebas (§7) |
| `contable/migrations/00XX_renumerar_condic.py` | Data migration de §2.5 |

### 4.2 Modificados

Todo lo listado en §2.5, más:

| Archivo | Cambio |
|---------|--------|
| `contable/views.py` | `SaldosMensualesView` (TemplateView de la página) |
| `contable/views_htmx.py` | `saldos_mensuales_datos` (partial HTMX) + filtros `modulo` y `ejercicio_id` en `get_mayor_context` (§6.5) |
| `contable/views_reportes.py` | `exportar_saldos_mensuales` (Excel) |
| `contable/services/reportes_excel.py` | `exportar_saldos_mensuales_excel(...)`, reusando `_configurar_hoja` |
| `contable/services/asientos.py` | `editar_asiento`: validar fecha vs. ejercicio (D-9) y bloquear `condic ≥ 5` (D-6) |
| `contable/urls.py` | 3 rutas nuevas |
| `templates/contable/index.html` | Tarjeta de acceso al nuevo reporte |
| `docs/walkthrough.md` | Bitácora de la implementación |

---

## 5. Filtros de la pantalla

Mapeo contra el formulario VFP de la captura:

| VFP | Acá | Detalle |
|-----|-----|---------|
| Desde / Hasta | **Ejercicio** (SIEMPRE PRESENTE) | §5.0 |
| Todas / Sucursal | **Sucursal** | `Todas` o una `Sucursal` de la empresa |
| 6.Todas / 7.Módulo | **Módulo** | `Asiento.modulo` (1=manual, 2=ventas, 5=compras, 6=banco) |
| `chkReal` · `chkPresupuestado` · `chkAjuste` · `chkAuditoria` | **4 checkboxes de `condic`** | §5.1 |
| `chkCierre` | — | Innecesario: los `condic` 6 y 7 quedan fuera por la regla §3.3 |
| 8.Todas / 9.Resultado | **Alcance** | `Todas` / `Solo Resultados (R)` / `Solo Patrimoniales (A,P,N)` |
| — | **Mostrar sumarizadoras** | Encendido por defecto (el CSV las incluye) |
| — | **Omitir cuentas sin movimiento** | Encendido por defecto |

Todos los filtros disparan por HTMX sobre el partial de la grilla, sin recargar la página.

### 5.0 El Ejercicio — filtro SIEMPRE PRESENTE

El **ejercicio con el que se está trabajando** es un filtro permanente, del mismo rango que el
`empresa_id`: no es opcional, no admite "Todos", no se puede desactivar.

**Se filtra por la FK, no sólo por fechas:** `asiento__ejercicio_id=ejercicio_id`. `Asiento` tiene FK
obligatoria a `Ejercicio` (`contable/models.py:59`) y es la fuente de verdad del período. Se aplica
la FK **y** el rango de fechas, que además es lo que define las columnas (§3.2).

En pantalla es un selector de los ejercicios de la empresa, inicializado en el activo, para poder
consultar uno anterior sin cambiar el contexto de trabajo. Lo que **no** existe es correrlo sin
ejercicio o sobre varios a la vez.

#### El invariante: toda transacción pertenece a su ejercicio

Regla de negocio: **no se puede registrar una transacción cuya fecha no pertenezca al ejercicio.**
Las fechas `inicio` y `cierre` del `Ejercicio` son los parámetros que lo validan.

Caso cotidiano: una factura del ejercicio anterior que no se registró y se necesita cargar para tomar
el crédito fiscal. Se registra con **la fecha del primer día del ejercicio actual**, y por lo tanto
cae legítimamente en la **primera columna mensual**. Es la práctica correcta, no una anomalía.

**Verificación en el código — se cumple al crear, pero NO al editar:**

| Operación | Estado |
|-----------|--------|
| `crear_asiento` (`asientos.py:44-53`) | ✅ Deriva el ejercicio **desde la fecha** y aborta si no hay ninguno. Los 6 llamadores productivos no pasan `ejercicio` explícito. |
| `editar_asiento` (`asientos.py:222-224`) | ❌ Hace `asiento.fecha = fecha` y guarda **sin revalidar** que la fecha nueva pertenezca a `asiento.ejercicio`. |

Se corrige en la fase 1 (D-9).

### 5.1 El filtro de `condic` — cuatro checkboxes

Réplica de `chkReal` / `chkPresupuestado` / `chkAjuste` / `chkAuditoria` del VFP, y cumplimiento de
la regla de `.cursorrules` (todo listado con importes ofrece el filtro de condición):

| ☑ | Rótulo | `condic` |
|:-:|--------|:--------:|
| ☑ | Real | 1 |
| ☑ | Presupuestado | 2 |
| ☑ | Ajuste | 3 |
| ☑ | Auditoría | 4 |

Los cuatro tildados por defecto. Combinaciones de uso, dictadas por el usuario:

| Objetivo | Tildar |
|----------|--------|
| Análisis de **gestión** | 1 + 2 |
| Ver cómo queda el **balance** | 1 + 3 + 4 |
| Ver **sólo los ajustes de los auditores** | 4 |
| Ver los comprobantes **fuera de la operatoria** de la empresa | 3 |

Con los cuatro destildados la grilla queda vacía con un aviso, sin ejecutar la consulta.

**La columna Apertura no se ve afectada por estos checkboxes:** siempre es `condic = 5`, íntegra
(§3.3). Destildar "Real" no recorta la apertura.

**La identidad `Apertura + meses = saldo al cierre` se verifica con los cuatro tildados.** Con un
subconjunto, el reporte es una vista parcial deliberada, no un descuadre.

Reutiliza el patrón de checkboxes `name="condic"` de
`templates/contable/partials/libro_diario.html:52-62`, con lo cual el querystring
(`?condic=1&condic=2&…`) es directamente compatible con `get_mayor_context` para el drill-down (§6.5).

---

## 6. Diseño técnico

### 6.1 Una sola consulta pivoteada en Python

Se descarta anotar 13+ `Sum(...)` condicionales sobre `Cuenta` (extrapolación del patrón del balance
actual): con 13 columnas serían 13 sub-agregados sobre el mismo join y el plan de PostgreSQL se
degrada. En su lugar, **una consulta agrupada por (cuenta, mes)** y el pivot en memoria:

```python
from django.db.models import Sum, F
from django.db.models.functions import TruncMonth

movs = (AsientoLinea.objects
    .filter(
        cuenta__empresa_id=empresa_id,
        asiento__empresa_id=empresa_id,          # multi-tenant, doble candado
        asiento__ejercicio=ejercicio,            # SIEMPRE PRESENTE — §5.0
        asiento__anulado=False,
        asiento__condic__in=condics,             # subconjunto de {1,2,3,4} — §5.1
        asiento__fecha__gte=ejercicio.inicio,
        asiento__fecha__lte=ejercicio.cierre,
    )
    .annotate(periodo=TruncMonth('asiento__fecha'))
    .values('cuenta_id', 'periodo')
    .annotate(neto=Sum(F('debe') - F('haber')))
)
```

Y la apertura, con el mismo `shape` pero sin `TruncMonth` y con su propio universo de `condic`:

```python
apert = (AsientoLinea.objects
    .filter(
        cuenta__empresa_id=empresa_id,
        asiento__empresa_id=empresa_id,
        asiento__ejercicio=ejercicio,
        asiento__anulado=False,
        asiento__condic=5,                       # regla estricta — §3.3
    )
    .values('cuenta_id')
    .annotate(neto=Sum(F('debe') - F('haber')))
)
```

La primera devuelve como máximo `cuentas_imputables × meses` filas (en la muestra: ~120 × 12 ≈ 1.400).
El pivot y el rollup se hacen en Python sobre un dict, igual que `_calcular_balance`.

Total: **2 consultas agregadas + 1 consulta del plan de cuentas.**

Las dos consultas son mutuamente excluyentes por `condic`, así que ningún movimiento se computa dos
veces ni se pierde: es la regla §3.3 expresada en el ORM.

### 6.2 Índice propuesto (a medir, según `.cursorrules` §4)

La consulta filtra por `cble_asiento_enc` (empresa, ejercicio, fecha, anulado, condic) y agrupa por
`cble_asiento_mov.cuenta_id`. El índice existente `('empresa','ejercicio','fecha')` en `Asiento`
cubre bien la cabecera. Del lado del detalle, PostgreSQL usa el índice de FK
`cble_asiento_mov.asiento_id` pero debe ir a la tabla a buscar `cuenta_id`, `debe` y `haber`.

Se evaluará un índice de cobertura:

```python
models.Index(fields=['asiento', 'cuenta'], include=['debe', 'haber'], name='idx_mov_asiento_cta_cov')
```

**Aprobado con la condición de medirlo primero con `EXPLAIN ANALYZE` sobre datos reales.** Un índice
de cobertura sobre la tabla más escrita del sistema tiene costo en cada alta de asiento: si el
reporte responde bien sin él, no se crea. Se documenta la medición en el walkthrough.

### 6.3 Firma del servicio

```python
def calcular_saldos_mensuales(
    empresa_id: int,
    ejercicio,                             # instancia de Ejercicio — obligatorio (§5.0)
    condics=(1, 2, 3, 4),                  # checkboxes de §5.1
    sucursal_id: int | None = None,
    modulo: int | None = None,
    alcance: str = 'todas',                # 'todas' | 'resultados' | 'patrimoniales'
    mostrar_sumarizadoras: bool = True,
    omitir_sin_movimiento: bool = True,
) -> dict:
    """
    {
      'periodos':  [{'clave': '202501', 'label': 'Ene-25', 'anio': 2025, 'mes': 1,
                     'primer_dia': date, 'ultimo_dia': date}, ...],
      'filas':     [{'cuenta': <Cuenta>, 'nivel': 2, 'apertura': Decimal,
                     'meses': [Decimal, ...],   # mismo largo y orden que 'periodos'
                     'total': Decimal}, ...],
      'totales':   {'apertura': Decimal, 'meses': [Decimal, ...], 'total': Decimal},
      'ejercicio': <Ejercicio>,
      ... (filtros aplicados, para repintar el panel)
    }
    """
```

Todas las cifras en `Decimal` de punta a punta (nunca `float`), respetando la convención de 2
decimales del proyecto.

**Saneamiento de `condics`:** el servicio intersecta lo recibido con `{1,2,3,4}`
(`condics = [c for c in condics if c in (1,2,3,4)]`). Así un querystring armado a mano
(`?condic=5&condic=6`) no puede meter la apertura ni la refundición en las columnas mensuales. Si la
intersección queda vacía, devuelve la grilla vacía con el aviso, sin ejecutar la consulta.

### 6.4 Interfaz (HTML + Tailwind + HTMX)

- Página `templates/contable/saldos_mensuales.html`: encabezado, "Volver a Contable", panel de
  filtros y contenedor `#saldos-mensuales-content`.
- Partial `templates/contable/partials/saldos_mensuales.html`: la grilla con la fila TOTALES al pie.

**La grilla ancha** (15+ columnas numéricas):

- Contenedor `overflow-x-auto`; la página **no** scrollea horizontalmente.
- `Jerarquía` y `Detalle` **sticky a la izquierda** (`sticky left-0 bg-white z-10`).
- Encabezado `sticky top-0`; fila TOTALES `sticky bottom-0`.
- Números en `tabular-nums text-right`, negativos en rojo.

**Jerarquía visual** (replicando VFP): indentación por nivel calculada desde `len(cuenta.jerarquia)`;
sumarizadoras en **negrita y azul**; nivel 1 (ACTIVO, INGRESOS…) con fondo suave.

**Formato de importes:** filtro `{{ valor|formato_ar }}` de `core/templatetags/formato_tags.py` en
todos los displays, con su `{% load formato_tags %}`. Cero formateo manual. El reporte no tiene
inputs numéricos, así que no interviene `.fInputAR`.

> **Recordatorio operativo:** si se usa alguna clase Tailwind que no esté en el CSS purgado (probable
> con `sticky left-0`, `tabular-nums`), hay que correr `npm run build` o el layout se rompe.

### 6.5 Drill-down: importe → Mayor del mes → Asiento

Requisito: las mismas prestaciones que el Sumas y Saldos, con una diferencia — **el mayor que se abre
está acotado al mes de la celda clickeada**.

```
click en la celda (cuenta, mes)  →  Mayor de esa cuenta, del 1° al último día de ese mes
       click en un movimiento    →  Asiento contable completo
```

**No hace falta ningún endpoint nuevo.** La cadena ya existe y está probada:

1. `mayor_cuenta_modal(cuenta_id)` (`contable/urls.py:33`) acepta `fecha_desde`/`fecha_hasta` y los
   reenvía a `libro_mayor_rows`.
2. `templates/contable/partials/libro_mayor_rows.html:31` ya trae en cada fila el botón
   `hx-get="{% url 'detalle_asiento_modal' mov.asiento.asiento_id %}"`.

Cada celda de importe se renderiza como:

```html
<button hx-get="{% url 'mayor_cuenta_modal' fila.cuenta.id %}?fecha_desde={{ p.primer_dia|date:'Y-m-d' }}&fecha_hasta={{ p.ultimo_dia|date:'Y-m-d' }}&{{ filtros_qs }}"
        hx-target="#modal-container"
        class="w-full text-right tabular-nums hover:bg-indigo-50 hover:underline">
  {{ valor|formato_ar }}
</button>
```

También se hacen clickeables **Apertura** (mayor de los asientos de apertura) y **Total** (mayor del
ejercicio completo), como hace hoy el Sumas y Saldos.

#### Consistencia con los filtros (crítico)

Si la celda dice `1.234,56`, el mayor **tiene que sumar exactamente eso**. Faltan dos cosas:

1. **Propagar siempre el `condic` explícito, nunca vacío**, según la regla §3.3:

   | Celda | Querystring |
   |-------|-------------|
   | Mes `AAAAMM` | los tildados (`?condic=1&condic=2&…`) + rango del mes |
   | Apertura | `?condic=5` + rango del ejercicio |
   | Total | los tildados **y** `condic=5` + rango del ejercicio |

   Sin esto se rompe justo en el primer mes: un asiento `condic=5` fechado 01/01/2025 cae dentro del
   rango de `202501` y el mayor lo mostraría, mientras la columna `202501` lo excluye.

2. **Agregar a `get_mayor_context` (`contable/views_htmx.py:220`) dos filtros que hoy no tiene:**
   `modulo` y **`ejercicio_id`**. Ambos con el mismo patrón de 3 líneas que `sucursal_id`. El de
   `ejercicio_id` es el importante: el mayor se acota hoy sólo por fechas, así que un asiento de otro
   ejercicio con fecha solapada aparecería en el mayor sin estar en la celda.

#### Diferencia de signo entre la celda y el mayor

`get_mayor_context:255-259` calcula la columna *Saldo* del mayor **según el tipo de cuenta** (`A`/`R`
deudor; `P`/`N` acreedor), mientras que la celda es siempre `debe − haber`. En una cuenta de ingresos
la celda dirá `-45.192.021,77` y el mayor mostrará `45.192.021,77`.

Las columnas Debe y Haber del mayor no tienen ambigüedad, así que la conciliación es verificable.
**Decidido: no se toca el mayor** (lo consumen el Libro Mayor y sus exports); queda documentado.

### 6.6 Export Excel

`exportar_saldos_mensuales_excel(...)` en `contable/services/reportes_excel.py`, reusando
`_configurar_hoja`. Columnas idénticas al VFP (Anexo A): A=codigo, B=sumariza, C=jerarquia,
D=detalle, E=imp, F=apertura, G..R=meses, S=total, T=tipo, U=id_bce, V=id_pre, W=id_ec, X=id_fc.
`number_format` `#,##0.00` en las columnas de importe y `000000` en los encabezados de mes. Se
escriben `Decimal` y el formato lo pone Excel. Acá se aplica el `× −1` de §3.6.

**Sin PDF:** 15+ columnas no entran de forma legible. Excel es el canal natural de este reporte.

---

## 7. Plan de pruebas

### 7.1 Automatizadas — `contable/tests/test_saldos_mensuales.py`

**Columnas dinámicas**
1. Ejercicio ene/2025–dic/2025 → 12 períodos, `202501 … 202512`.
2. Ejercicio abr/2025–mar/2026 → 12 períodos, primero `202504`, último `202603`.
3. Ejercicio irregular sep/2025–dic/2025 → 4 períodos.

**Regla de `condic` (§3.3), el corazón del reporte**
4. Un asiento `condic=5` impacta en `Apertura` y **en ningún mes**, aunque su fecha caiga dentro del
   primer mes del ejercicio.
5. Un asiento `condic ∈ {1,2,3,4}` impacta en su mes y **nunca** en `Apertura`, aunque su fecha sea
   la del primer día del ejercicio.
6. Los asientos `condic` 6 y 7 no aparecen en ninguna columna.
7. Un movimiento del mes N impacta sólo en la columna del mes N.
8. `Total == Apertura + Σ meses` para toda fila, **y con los cuatro `condic` tildados ese `Total` es
   idéntico al saldo final que `_calcular_balance` devuelve para la misma cuenta y ejercicio**. Es la
   prueba cruzada que ata este reporte al Sumas y Saldos.
9. Rollup: el valor de una sumarizadora es la Σ exacta de sus hijas, en cada columna, con jerarquía
   de 3 niveles.

**Signo**
10. Modo "Todas": la fila TOTALES da 0 en cada mes, y en Apertura y Total.
11. **El servicio devuelve siempre signo natural**, en los dos modos.
12. La inversión vive **sólo en el export Excel**: ingresos positivos y egresos negativos en modo
    Resultados; sin invertir en modo "Todas".
13. Modo "Solo Resultados" en Excel: el total mensual equivale a `ingresos − egresos` del mes.

**Filtros (§5.1)**
14. Cada una de las cuatro combinaciones de uso de §5.1 devuelve el subconjunto correcto.
15. **La columna Apertura es idéntica en las cuatro**: no la tocan los checkboxes.
16. `condics=[]` → grilla vacía con aviso, sin ejecutar la consulta.
17. **Saneamiento:** `condics=[5, 6]` se intersecta a vacío.
18. Los asientos anulados nunca se computan.
19. Filtro por sucursal y por módulo.
20. **Omitir sin movimiento**: una cuenta cuyas columnas netean cero pero **tuvo** movimiento se
    conserva (criterio `ABS` del VFP, Anexo A); una sin ningún movimiento se omite.

**Drill-down (§6.5)**
21. La celda `(cuenta, mes)` genera el link con el rango del mes y el `condic` explícito de la tabla.
22. **Conciliación:** la Σ(debe − haber) de `get_mayor_context` con los parámetros del link es
    **exactamente igual** al valor de la celda. Se prueba en el primer mes con un asiento `condic=5`
    presente, que es el caso donde se rompería.

**Alcances inflexibles**
23. Cuentas y asientos de otra **empresa** no aparecen ni alteran ninguna cifra.
24. Asientos de **otro ejercicio** no aparecen, **incluso si su `fecha` cae dentro del rango del
    ejercicio consultado** (el caso que un filtro sólo por fechas dejaría pasar).
25. El servicio exige `ejercicio`: no se puede invocar sin él ni sobre varios a la vez.

**Invariante fecha↔ejercicio (§5.0)**
26. Una factura del ejercicio anterior cargada con fecha del **primer día** del ejercicio actual
    aparece en la **primera columna mensual**.
27. `editar_asiento` rechaza una fecha fuera de `asiento.ejercicio.inicio … .cierre` (D-9).

**Excel**
28. El export responde 200 con el `Content-Type` de xlsx y la cantidad de columnas coincide con la
    cantidad de períodos del ejercicio.

**Regresión de la renumeración de `condic` (fase 1)**
29. `procesar_cierre_ejercicio` crea el asiento con `condic=6`.
30. **Una compra `condic=3` genera registros en Libro IVA y `LibroIvaAlic`** (§2.5); una `condic=2`
    no; una `condic=4` tampoco.
31. El asiento `condic=6` **sí** entra al período de `_calcular_balance` y **no** aparece en Libro IVA.
32. `editar_asiento` rechaza editar un asiento con `condic ≥ 5` (D-6).
33. La data migration reetiqueta `3→5` y los cierres históricos a `6`, sin tocar ningún otro asiento.

### 7.2 Manuales

1. Cargar el ejercicio 2025 de una empresa con datos y contrastar contra
   `d:\borrador\saldos_mensuales.csv`: fila `ACTIVO` (apertura `222.308.213,34`, total
   `536.370.572,95`) y fila `CAJA Y BANCOS`.
2. Modo "Solo Resultados" y contrastar contra `saldos_mensuales_resultados.csv`: `INGRESOS` total
   `1.683.427.656,03`, `EGRESOS` `-1.492.068.539,87`, TOTALES `191.359.116,16`.
3. Verificar que en modo "Todas" la fila TOTALES da 0,00 en todas las columnas.
4. Probar con un ejercicio que no cierre en diciembre y confirmar el corrimiento de columnas.
5. Verificar el scroll horizontal con las columnas sticky en pantalla chica.
6. Recorrer las cuatro combinaciones de checkboxes de §5.1 y validar que cada lente da lo esperado.

---

## 8. Fases de ejecución

| # | Fase | Entregable |
|---|------|-----------|
| ✅ **1** | **Renumeración de `condic`** (§2): `.cursorrules`, `CLAUDE.md`, `models.py`, `contabilizacion.py` (Libro IVA → `{1,3}`), `cierre.py` → `condic=6`, `_calcular_balance`, script de migración, templates de badges y checkboxes, data migration. Más las dos validaciones de `editar_asiento` (D-6 y D-9). Tests 27 y 29-33 | Semántica e invariantes cerrados |
| ✅ 2 | `services/saldos_mensuales.py` | Servicio puro |
| ✅ 3 | Tests del servicio (§7.1: 1-11, 14-20, 23-26) | Suite en verde — 27 tests OK |
| ✅ 4 | Vistas (página + partial HTMX) y URLs | Navegable |
| ✅ 5 | Templates + tarjeta en el índice + `npm run build` | UI funcionando |
| 6 | Drill-down + filtros `modulo`/`ejercicio_id` en `get_mayor_context`. Tests 21-22 | Mayor del mes y asiento |
| ✅ 7 | Export Excel (con el × −1). Tests 12-13 y 28 | Descarga operativa |
| 8 | Medición `EXPLAIN ANALYZE` y decisión del índice (§6.2) | Documentada en el walkthrough |
| 9 | Contraste manual contra los CSV (§7.2) | Validación numérica |
| 10 | Bitácora en `docs/walkthrough.md` | Documentado |

La **fase 1 es autónoma**: cierra bugs preexistentes (asiento de cierre indistinguible, `condic`
degradado al editar, fecha sin revalidar) con independencia del reporte nuevo.

---

## 9. Decisiones

| ID | Punto | Estado |
|----|-------|--------|
| **D-1** | ¿Dónde se aplica el × −1? | ✅ Sólo en el Excel. En pantalla, signo natural: el operador necesita ver el movimiento tal cual se registró para detectar errores de carga. |
| **D-2** | ¿Cómo se identifican los asientos estructurales? | ✅ Renumeración completa: 5=Apertura, 6=Refundición, 7=Cierre (§2). |
| **D-3** | Índice de cobertura en `cble_asiento_mov` | ✅ Aprobado, **midiendo antes** con `EXPLAIN ANALYZE` (§6.2). |
| **D-4** | ¿Export a PDF? | ✅ No. 15+ columnas no entran legibles; Excel es el canal natural. |
| **D-5** | ¿Alcance "Solo Patrimoniales"? | ✅ Sí. No está en VFP, sale gratis. |
| **D-6** | La edición degrada el `condic` de un asiento estructural | ✅ Bloquear la edición para `condic ≥ 5`. |
| **D-7** | Signo del *Saldo* del mayor vs. la celda | ✅ No se toca el mayor; queda documentado (§6.5). |
| **D-8** | ¿Se arrastran a Apertura los movimientos previos al ejercicio? | ✅ **No, bajo ningún aspecto.** Apertura = asiento `condic=5`, punto (§3.3). |
| **D-9** | `editar_asiento` permite mover la fecha fuera del ejercicio | ✅ Agregar la validación que ya tiene `crear_asiento` (§5.0). |

### Fuera del alcance de este plan (registrados para después)

- **`condic = 7` (Cierre)**: desarrollo nuevo. Hoy sólo existe la refundición (§2.7).
- **Copia automática del cierre del ejercicio anterior como apertura del nuevo** (§2.7).
- **Captura de asientos de auditoría** (`condic = 4`), que escribe sólo en `cble_asiento_enc` y
  `cble_asiento_mov`.
- **Habilitar `condic = 3` en la carga** para ciertos usuarios: tercera opción "Ajuste" en el
  optiongroup Real/Proyectado.
- **Cambio de `condic` posterior a la emisión** en ventas, por usuario autorizado, propagado a todas
  las tablas intervinientes. *Nota de diseño:* ese proceso deberá resincronizar el subsistema fiscal
  — pasar de `1`/`3` a `2` tiene que **borrar** el registro de Libro IVA, y a la inversa crearlo.
- **Selector de `condic` del Balance** (`templates/contable/partials/balance.html:31-34`): hoy ofrece
  "Todas / 1 / 2" y queda corto frente a las tres lentes de §2.4.

---

## Anexo A — Verificación contra el fuente VFP

`c:\jm_soft\balances\forms\sum_sal_anual.SCT` fue leído y **confirma la especificación derivada de
los CSV**:

| Aspecto | Código VFP | Coincide |
|---------|-----------|----------|
| Agrupación | `TOTAL ON PADL(id_cta,5,'0')+LEFT(DTOS(fecha),6) FIELDS debe,haber` | ✅ = `values('cuenta_id', TruncMonth('fecha'))` |
| Movimiento | `replace &xCampo WITH m.debe - m.haber` | ✅ neto `debe − haber` |
| Apertura | Tabla física aparte `contable!apertura`, campo `saldo` por `id_cta` | ✅ acá es el asiento `condic=5` |
| Rollup | `SET ORDER TO jera_cta DESC` + `SCAN FOR imputable=.f.` + `SUM ... FOR sumariza = m.codigo` | ✅ bottom-up sumando hijas directas |
| Total | `replace ALL total WITH apertura+mes_01+...+mes_12` | ✅ |
| Omitir sin movimiento | `DELETE FOR (ABS(apertura)+...+ABS(total)) = 0` | ✅ usa `ABS`: una fila que netea cero pero tuvo movimiento **se conserva** |
| Totales del pie | `SUM mes_XX FOR ... AND imputable = .t.` | ✅ sólo imputables, para no duplicar |
| Color sumarizadoras | `DynamicForeColor iif(imputable=.f., RGB(0,0,255), RGB(0,0,0))` | ✅ azul y negrita |
| Modo Resultados | `SET FILTER TO tipo = 'R'` | ✅ |
| Signo | `xSig = -1` sólo dentro del `PROCEDURE` de Excel | ✅ §3.6 |
| Columnas Excel | A..X según §6.6 | ✅ idéntico al header del CSV |
| Formato Excel | `.Columns("F:S").NumberFormat = "#,##0.00"`, encabezados de mes `"000000"` | ✅ a replicar en openpyxl |

### Diferencia de diseño deliberada: cómo se ordenan los meses

VFP tiene **12 columnas físicas fijas** `mes_01…mes_12` indexadas por el **número de mes calendario**
(`'mes_'+PADL(MONTH(m.fecha),2,'0')`), y en `Init` reordena visualmente la grilla arrancando por el
mes de inicio del ejercicio:

```foxpro
xMes = MONTH(oApp.inicio)
FOR xOrden = 4 TO 15
    xCol = 8 + xMes
    &xColum.ColumnOrder = xOrden
    IF xMes = 12 THEN xMes = 1 ELSE xMes = xMes + 1
ENDFOR
```

**El año nunca se guarda en la columna.** Funciona porque el rango siempre abarca exactamente 12
meses. Un ejercicio irregular, o un rango que exceda el año, haría colisionar dos meses iguales de
años distintos en la misma columna, sumándolos en silencio.

El diseño propuesto genera la lista de `(año, mes)` reales (§3.2): soporta ejercicios irregulares sin
columnas fantasma, no puede colisionar `202501` con `202601`, y el rótulo es el período real.

### Filtros del VFP no portados

`oApp.num8/num9` (rango de nro. de asiento) y `oApp.num11/num12` (rango de `id_cod`) existen en el
formulario pero se setean fijos en `0 … 99999999`: **nunca filtran nada**. No se portan.
