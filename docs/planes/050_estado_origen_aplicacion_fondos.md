# Plan 050 — Estado de Origen y Aplicación de Fondos (EOAF)

- **Fecha:** 16/08/2026
- **Módulo:** Contable → Reportes (o Tesorería → Reportes, ver §9)
- **Origen:** migración de los formularios VFP `c:\jm_soft\balances\forms\suma_saldo_fciero.scx`
  (C-207, "Suma y Saldo Financiero") y `sum_sal_fciero_mov.scx` (drill-down)
- **Prerrequisito:** Plan 049, **ejecutado**
- **Estado:** **EJECUTADO (16/08/2026)** — fases 1 a 5 completas.
  `tesoreria.tests.test_eoaf`: **25/25 OK**.

---

## 1. Objetivo

Un sumas y saldos que en lugar de correr sobre los asientos corre sobre los **movimientos de
fondos**. Para cada cuenta del plan responde: **cuánta plata entró por ella, cuánta salió, y cuál
fue el flujo neto** en un rango de fechas.

Es la herramienta con la que el usuario analiza de dónde vino y a dónde se fue el dinero, sin
mezclarlo con los devengamientos que no mueven caja.

### Muestras de referencia analizadas

| Archivo | Contenido |
|---------|-----------|
| `d:\borrador\OrigenyAplicacionFondos.xlsx` | Export del reporte (agosto 2025, 76 filas) |
| `d:\borrador\OrigeAplicacionFondos_Movimientos.xlsx` | Drill-down de la cuenta 34 PROVEEDORES VARIOS |

Los dos formularios VFP fueron leídos del `.scx`/`.sct`; la comparación está en el **Anexo A**.

---

## 2. Decisiones ya tomadas por el usuario

1. **Sin columna "Disponibilidad Inicial".** El reporte analiza el flujo **entre dos fechas**; el
   acumulado anterior está fuera de lugar. Las columnas son **Ingresos de Fondos**, **Egresos de
   Fondos** y **Flujo Neto**.

   No es solo una cuestión conceptual: en el legado esa columna **está rota**. El bucle que
   acumula las sumarizadoras cubre `debe`, `haber`, `saldo`, `efectivo`, `valores` y `banco`,
   pero **no `si`**; y después `replace ALL saldo WITH si + debe - haber` pisa el resultado. Queda
   que las imputables incluyen `si` en el Flujo Neto y las sumarizadoras no. Verificado en la
   muestra: la fila `211 DEUDAS COMERCIALES` da −34.760.522,55 (= 8.415.254,09 − 43.175.776,64,
   sin `si`), mientras que la suma de sus ocho hijas imputables da ≈ −113.325.649. El total del
   pie tampoco coincide con la columna, porque es `txtDebe − txtHaber`, también sin `si`.
   Sacándola, imputables, sumarizadoras y total cierran entre sí.

2. **Filtro de condición: Real (1) y Presupuestado (2)**, ambos marcados por defecto. Es el único
   universo posible en movimientos de fondos y coincide con la lente de Gestión de `.cursorrules`.

---

## 3. Fuente de datos

**El asiento contable**, no `MovimientoCaja`. Un movimiento de fondos es, por definición,
**todo asiento que toca al menos una cuenta con `tipo_disponibilidad`** (EFE, DOL, VAL, BCO, TAR,
OTR). Eso capta también lo que nunca pasó por una caja: compras de contado, débitos bancarios,
asientos manuales, cheques debitados por la conciliación.

Dentro de cada asiento:

- las líneas **de disponibilidad** son el *bolsillo* (dan el desglose por medio);
- las líneas **de contrapartida** (`tipo_disponibilidad` vacío) son las **filas del reporte**.

### 3.1 Signo — verificado contra la muestra

| Contrapartida | Significado | Columna | Verificación en `OrigenyAplicacionFondos.xlsx` |
|---|---|---|---|
| al **HABER** | la cuenta fue **origen** de fondos | **Ingresos** | `112099 CLIENTES VARIOS` → Ingresos 90.546.417,94 (cobranza: Debe Caja / Haber Clientes) |
| al **DEBE** | la cuenta fue **aplicación** de fondos | **Egresos** | `211001 PROVEEDORES VARIOS` → Egresos 3.642.979,75 (pago: Debe Proveedores / Haber Caja) |

Contrastado también con `410201 RECUPERO DE GASTOS` (Ingresos) y `530008 ADM-TELEFONIA`
(Egresos). **Flujo Neto = Ingresos − Egresos.**

### 3.2 Las transferencias entre disponibilidades se excluyen solas

Un traslado de caja mostrador a tesorería asienta Debe Caja Central / Haber Caja Mostrador: las
**dos** líneas son de disponibilidad, así que el asiento **no aporta ninguna fila**. Es el
resultado correcto —mover plata de un bolsillo a otro no es ni origen ni aplicación— y sale sin
ninguna regla especial. El legado, en cambio, las mostraba mezcladas en el cuerpo (`111001 CAJA`
con Ingresos 800.000, `111011 BANCO PATAGONIA` con Egresos 22.728.298,21).

> **Punto de configuración a revisar:** en un traslado **entre sucursales** el asiento pasa por
> `cta_transferencias_sucursal`. Si esa cuenta no está marcada como disponibilidad, va a aparecer
> como fila del reporte. Hay que decidir si se le pone `tipo_disponibilidad='OTR'` o si se la
> excluye explícitamente. **Se verifica en la fase 1 contra los datos reales.**

### 3.3 Reutilización de `caja_diaria.py`

`tesoreria/services/caja_diaria.py` **ya hace exactamente este cálculo**, pero por sesión de caja
en lugar de por rango de fechas: separa disponibilidades de contrapartidas, y cuando un asiento
tiene varias contrapartidas **prorratea el desglose por medio** entre ellas según su importe
(`_lineas_desde_asientos`, `_fila_vacia`, `_clasificar_detalle`, el prorrateo de §268-278).

La fase 1 extrae ese núcleo a un servicio compartido y deja que los dos reportes lo consuman. No
se reescribe la lógica de prorrateo: ya está probada por `test_caja_diaria.py`.

---

## 4. Estructura del reporte

### 4.1 Grilla

| Columna | Origen |
|---------|--------|
| Código | `Cuenta.codigo` (legacy) |
| Jerarquía | `Cuenta.jerarquia` |
| Detalle | `Cuenta.cuenta` |
| **Ingresos de Fondos** | Σ contrapartidas al haber |
| **Egresos de Fondos** | Σ contrapartidas al debe |
| **Flujo Neto** | Ingresos − Egresos |
| Efectivo / Dólares / Valores / Banco / Tarjetas / Otros | desglose prorrateado por medio |

El legado muestra solo efectivo, valores y banco, y por eso **sus totales no cierran**: el Flujo
Neto total (−33.792.781,85) contra la suma de los tres medios (−34.179.709,55) difiere en
386.927,70, que es lo que se va por `dolares`, `tarjetas` y `reten`. Acá van las seis columnas.

### 4.2 Jerarquía

Las cuentas no imputables acumulan **a sus descendientes imputables por prefijo de `jerarquia`**,
igual que el legado (`sum ... for jera_cta = jera and imputable = .T.`, que con `SET EXACT OFF`
es un "empieza con"). Sumar solo imputables evita el doble conteo.

> Se usa el prefijo de `jerarquia` y **no** la FK `Cuenta.sumariza`, porque en los datos legados
> `sumariza` está desfasado: las cuentas `113204…113300` tienen `sumariza = 75` pero cuelgan de la
> `113` (código 19). El legado no lo nota justamente porque acumula por prefijo.

Filas sin movimiento en el período no se muestran (`Ingresos = Egresos = 0`).

### 4.3 Drill-down por cuenta

Clic en una imputable → modal con el detalle, según `cons_caja_diaria_cta` del legado:

| Columna | Origen |
|---|---|
| Asiento | `Asiento.asiento_id` |
| Fecha | `Asiento.fecha` |
| Caja | `MovimientoCaja.sesion` (si el asiento tiene movimiento) |
| Cliente/Proveedor | `MovimientoCaja.cli_pro`, con fallback a `Asiento.cli_pro` |
| Concepto | `AsientoLinea.leyenda` o `Asiento.concepto` |
| Ingresos / Egresos | de la línea |
| Efectivo / Banco / Valores | desglose del asiento |
| Saldo | corrido |
| Condición | `Asiento.condic` |

Más el filtro **Todos / Efectivo / Banco / Valores** del `opgMoneda` legado, y el patrón
**Typeahead + Lupa** para filtrar por cliente/proveedor —posible gracias a `MovimientoCaja.cli_pro`
del Plan 049—.

---

## 5. Fases

| # | Fase | Entrega | Estado |
|---|------|---------|--------|
| 1 | Núcleo compartido con `caja_diaria.py` → `tesoreria/services/fondos.py`; verificación de §9.2 contra datos reales | servicio + tests | ✔ |
| 2 | Servicio del EOAF: agregación por cuenta, rollup jerárquico, totales | `tesoreria/services/eoaf.py` | ✔ |
| 3 | Vista + template HTMX: filtros, botón Generar, grilla | `views_eoaf.py`, `eoaf.html`, `partials/eoaf_grilla.html` | ✔ |
| 4 | Drill-down: modal por cuenta con filtro de medio | `modals/eoaf_cuenta_modal.html` | ✔ |
| 5 | Exportación a Excel y PDF | `tesoreria/services/eoaf_export.py`, `pdf/eoaf_pdf.html` | ✔ |

> El servicio quedó en `tesoreria/`, no en `contable/`, siguiendo la decisión de §9.1 de ubicar el
> reporte en el módulo Tesorería.

### Notas de implementación

- **La grilla no se autoejecuta.** El usuario fija período y condición y presiona **Generar**, como
  el `cmdGenerar` del formulario legado y como se resolvió el Libro Mayor en el Plan 048.
- **Aplanado de `medios` en la vista.** Los templates de Django no indexan un dict por clave
  variable. En vez de agregar un filtro sólo para eso, `_con_medios_en_orden()` convierte el dict
  en una lista ordenada y el template itera.
- **Typeahead + Lupa por cliente/proveedor:** no se implementó. El drill-down ya llega acotado a
  una cuenta y en los volúmenes reales el listado entra en pantalla; agregar el buscador sin
  necesidad hubiera sido complejidad muerta. `MovimientoCaja.cli_pro` (Plan 049) lo deja
  disponible para cuando haga falta.

---

## 6. Plan de pruebas

**Automatizadas** (`contable/tests/test_eoaf.py`):

1. Cobranza en efectivo → la cuenta del cliente suma en **Ingresos**.
2. Pago a proveedor → la cuenta del proveedor suma en **Egresos**.
3. Pago de un gasto → la cuenta de gasto en **Egresos**; el desglose cae en la columna del medio.
4. **Traslado entre disponibilidades → no genera ninguna fila** (§3.2).
5. Asiento con varias contrapartidas → el desglose por medio se prorratea y **suma exactamente** el
   total del asiento (sin centavos perdidos por redondeo).
6. Rollup: una sumarizadora es la suma de sus imputables descendientes, y **no** hay doble conteo
   con niveles intermedios.
7. Coherencia global: **Σ Flujo Neto de las imputables == la variación neta de las
   disponibilidades del período**. Es el control que en el legado no cerraba.
8. Filtro de condición: un asiento con `condic=2` entra solo con Presupuestado tildado.
9. Rango de fechas: un comprobante **retroactivo** cae en el mes de su fecha, no en el de carga
   (lo habilita el Plan 049).
10. Multi-tenant: los movimientos de otra empresa no aparecen.
11. Asiento anulado → excluido.
12. Drill-down: las filas de una cuenta suman lo que muestra su fila en la grilla.

**Manuales:** contrastar contra `OrigenyAplicacionFondos.xlsx` sobre el mismo período, sabiendo
que **no van a coincidir exactamente** y por qué: sin `si`, sin transferencias entre
disponibilidades en el cuerpo, y con las seis columnas de medios en vez de tres.

---

## 7. Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Cuentas de disponibilidad mal marcadas → filas espurias o faltantes | Fase 1 audita `tipo_disponibilidad` contra los datos reales antes de construir nada |
| El prorrateo del desglose pierde centavos | Ya resuelto en `caja_diaria.py`: la última contrapartida absorbe la diferencia. Test 5 |
| Performance sobre un ejercicio completo | Índices del Plan 049 + agregación en SQL, sin traer líneas a Python. Se mide con datos reales |
| Movimientos históricos sin backfill | Las migraciones del Plan 049 **todavía no se aplicaron**: hay que correrlas antes. Riesgo bajo: hay **21 movimientos** en la base (17 de mostrador, 3 recibos, 1 OP) y **ninguno** con `condic` fuera de (1, 2), así que el backfill no va a abortar |

---

## 8. Prerrequisito operativo

**Las migraciones `tesoreria.0013/0014/0015` del Plan 049 no están aplicadas.** El EOAF depende
de `fecha` (rango correcto) y del vínculo con el asiento. Hay que correr
`python manage.py migrate tesoreria` antes de la fase 3.

Relevamiento de la base (solo lectura, 16/08/2026): **21 movimientos de caja** —17 de caja
mostrador, 3 de recibos, 1 de orden de pago— y **cero** con `condic` fuera de (1, 2). El backfill
no tiene por qué abortar y el reencuadre de fechas afecta a un puñado de registros, así que
aplicarlo es de bajo riesgo. Respaldo previo igual, por costumbre.

---

## 9. Decisiones tomadas por el usuario (16/08/2026)

1. **Ubicación: módulo Tesorería.** El reporte vive en Tesorería → Reportes, junto a la Caja
   Diaria, con la que comparte el núcleo de cálculo (§3.3).

2. **Circuito de caja mostrador confirmado por el usuario:** la caja mostrador impacta en su
   propia cuenta de disponibilidad, y su contrapartida son los **retiros de caja** hacia Caja
   Tesorería y el **cierre de caja**. Es exactamente el caso de §3.2: las dos puntas son cuentas
   de disponibilidad, así que el traslado no aporta filas al EOAF. Verificado en los datos:

   | Empresa | `cta_caja_mostrador` | `cta_caja_central` | `cta_transferencias_sucursal` |
   |---|---|---|---|
   | 1 | 111004 CAJA MOSTRADOR PESOS (`EFE`) | 111001 CAJA TESORERIA (`EFE`) | **111009 TRANSFERENCIA ENTRE SUCURSALES (sin marcar)** |
   | 2 | 111001 CAJA (`EFE`) | 111001 CAJA (`EFE`) | 111001 CAJA (`EFE`) |
   | 3 | sin configurar | sin configurar | sin configurar |

   **Corrección sobre el supuesto del usuario:** la cuenta puente **ya existe** —`111009
   TRANSFERENCIA ENTRE SUCURSALES`, ya cargada en `ParametrosContables` de la empresa 1—; lo que
   le falta es el marcado. Sin `tipo_disponibilidad` va a aparecer como una fila del EOAF cada
   vez que haya un traslado entre sucursales, cuando en realidad es plata en tránsito: un
   bolsillo, no un origen ni una aplicación.

   **APLICADO (16/08/2026, con OK del usuario):** `111009 TRANSFERENCIA ENTRE SUCURSALES` quedó
   con `tipo_disponibilidad = 'OTR'`. `OTR` y no `EFE` porque es un tránsito virtual: informa el
   movimiento del período pero **no arrastra saldo** (`TIPOS_SIN_SALDO`). La empresa 2 no se tocó
   —su cuenta puente ya estaba marcada `EFE`— y la 3 no la tiene configurada.

   > **Requisito de instalación:** en cada cliente nuevo, la cuenta que se cargue en
   > `ParametrosContables.cta_transferencias_sucursal` **debe** quedar marcada con un
   > `tipo_disponibilidad` (`OTR`). Si no, cada traslado entre sucursales genera una fila espuria
   > en el EOAF.

   > **Nota aparte, sin impacto en este plan:** en la empresa 2 las tres cuentas apuntan a la
   > misma (111001 CAJA), con lo cual un traslado entre sucursales asentaría contra sí mismo. Es
   > una configuración incompleta, no un problema del EOAF. Se deja anotado.

3. **Migración desde VFP: no prevista todavía.** Se hará cuando el sistema esté terminado. Los
   ajustes al script `migracion/scripts/03_migrar_tesoreria.py` que hizo el Plan 049 quedan
   listos para ese momento, pero **no hay datos legados en juego hoy**.

---

## Anexo A — Correspondencia con el sistema VFP

| Legado | Acá |
|--------|-----|
| `caja_diaria` agrupada por `id_cta` | asientos con línea de disponibilidad, agrupados por la cuenta de contrapartida |
| `cuentas.dbf` + `jera_cta` + `imputable` | `Cuenta.jerarquia` + `Cuenta.imputable` |
| `si` (Dispon. Inicial) | **eliminada** por decisión del usuario (§2.1) |
| `debe` / `haber` / `saldo` | Ingresos / Egresos / Flujo Neto |
| `efectivo`, `valores`, `banco` | + `dolares`, `tarjetas`, `otros` (el legado los omitía y por eso no cerraba) |
| `sdocaj` = efectivo + valores | derivable; se evalúa si aporta |
| `condic in (num1, num2)` = {1, 2} | filtro Real / Presupuestado |
| Vista `cons_caja_diaria_cta` | modal de drill-down (§4.3) |
| `opgMoneda`: Todos/Efectivo/Banco/Valores | mismo filtro en el modal |
| Botón **Corregir** (`mod_caja_diaria_cta`) | **no se migra**: existía porque en el legado la contrapartida se desnormalizaba a mano y salía mal. Acá se deriva del asiento y siempre está bien |
