# Plan 049 — Enriquecimiento de `tesoreria_movimiento_caja` (asiento, cuenta, cli/pro, fecha)

- **Fecha:** 15/08/2026
- **Módulo:** Tesorería → modelo de datos · Contable → contabilización
- **Origen:** prerrequisito del **Estado de Origen y Aplicación de Fondos** (migración de los
  formularios VFP `c:\jm_soft\balances\forms\suma_saldo_fciero.scx` y `sum_sal_fciero_mov.scx`)
- **Estado:** **EJECUTADO (16/08/2026)** — código, migraciones y pruebas completos.
  `tesoreria.tests.test_plan049_movimiento_caja`: **15/15 OK**.
  Regresión `tesoreria` + `contable`: **142/142 OK**.
  Las migraciones 0013/0014/0015 quedan **sin aplicar en producción**: el backfill reencuadra
  fechas históricas y correrlo requiere la ventana del usuario.

---

## 1. Objetivo

Dotar a `tesoreria_movimiento_caja` de los cuatro datos que hoy no tiene y que son
imprescindibles para construir el Estado de Origen y Aplicación de Fondos (EOAF), además de
corregir el tipo y la semántica del campo `fecha`:

| Campo | Qué aporta |
|-------|------------|
| `asiento` (FK) | Vincula el movimiento de fondos con su asiento contable. Es el nexo que hoy solo existe en sentido inverso y parcial |
| `cuenta` (FK) | Cuenta contable de imputación principal (contrapartida) |
| `cli_pro` (FK) | Cliente/Proveedor del movimiento, hoy alcanzable solo por tres FK nulleables distintas |
| `empresa` (FK) | Aislamiento multi-tenant sin tres JOINs |
| `fecha` | Pasa de `timestamp` a **`date`** y guarda la **fecha del comprobante**, no la de carga |

El equivalente en el sistema VFP es la tabla `caja_diaria`, cuya estructura fue leída
directamente del DBF (`d:\jm_soft\Net_Balances\eje_236\caja_diaria.dbf`):

```
CAJA, ID_CAJ, FECHA (D), ID_ASTO (I), ID_CTA (I), ID_COD (I), CONCEPTO,
INGRESOS, EGRESOS, COTIZ, CONDIC, ID_USU, MODIFICADO (T), ...
EFECTIVO, DOLARES, BANCO, VALORES, TARJETAS, RECARGO, RETEN, I_E, MESANO, MONEDA
```

Nuestro `MovimientoCaja` tiene hoy el equivalente de `CAJA` (vía sesión), `CONCEPTO`, `CONDIC` y
los medios de pago (vía `MovimientoCajaDetalle`), pero le faltan **`ID_ASTO`, `ID_CTA`, `ID_COD`**
y su `FECHA` es de otro tipo y significa otra cosa.

---

## 2. Análisis de la situación actual

### 2.1 Los seis orígenes de un `MovimientoCaja`

Relevados uno por uno sobre `tesoreria/views_htmx.py`:

| # | Origen | Línea | Asiento | Contrapartida contable |
|---|--------|-------|---------|------------------------|
| 1 | Recibo | 443 | `contabilizar_recibo` (:531) | Tipo C: **1** (cta. del cliente) · Tipo S: **N** (`ReciboImputacion`) |
| 2 | Orden de Pago | 663 | `contabilizar_orden_pago` (:758) | Tipo P: **1** (cta. del proveedor) · Tipo S: **N** (`OrdenPagoImputacion`) |
| 3 | Caja mostrador | 1071 | inline (:1176), **no** vía `crear_asiento()` | **N** (ventas por rubro + IVA débito) |
| 4 | Retiro parcial | 1323 | `generar_asientos_traslado` (:1378) | 1 (traslado entre disponibilidades) |
| 5 | Cierre de caja | 1458 | `generar_asientos_traslado` (:1504) | 1 (ídem) |
| 6 | Rendición (ingreso Tesorería) | 1654 | `_generar_asiento_diferencia` (:1680), solo si hay diferencia | 1 |

### 2.2 Problemas detectados

1. **`fecha` es la fecha de carga.** `fecha = DateTimeField(auto_now_add=True)`
   (`tesoreria/models.py:343`). Un recibo fechado el 15/08 cargado el 20/09 queda registrado en
   septiembre. Cualquier reporte "entre dos fechas" que lea este campo da mal.
2. **`fecha` está duplicado.** `MovimientoCaja` hereda de `AuditModel`, que ya aporta
   `fecha_creacion = DateTimeField(auto_now_add=True)` (`core/models.py:54`). Hoy hay dos campos
   con exactamente el mismo contenido y ninguno con la fecha del comprobante. Al convertir
   `fecha` a `date`, el momento de carga queda **íntegro en `fecha_creacion`**: no se pierde
   ningún dato y no hace falta un tercer campo.
3. **`condic` hardcodeado en caja mostrador.** `views_htmx.py:1076` fija `condic=1` aunque la
   vista ya calculó el valor real, que puede ser 2. **Una venta mostrador presupuestada queda hoy
   registrada como Real en el movimiento de caja.**
4. **El asiento de caja mostrador se arma a mano.** `views_htmx.py:1176` usa
   `Asiento.objects.create` en vez de `crear_asiento()` y **no asigna `sesion_caja`**, por lo que
   esos cobros no aparecen en la Caja Diaria. **Fuera del alcance de este plan** por decisión del
   usuario (ver §6.3 y §10): se deja como está.
5. **Docstring desactualizada.** `tesoreria/services/caja_diaria.py:11-18` afirma que recibos y
   órdenes de pago "NO generan asiento contable" y que "`OrdenPago` no tiene `asiento_id`". Ambas
   cosas son falsas desde hace tiempo; el reporte combina dos fuentes por esa creencia.

### 2.3 Decisiones tomadas por el usuario

- **`fecha`** → cambia de `timestamp` a **`date`** y guarda la fecha del comprobante que lo
  origina, **la misma que la del asiento contable**. No se agrega ningún campo de hora.
- **`cuenta`** → guarda la **cuenta de mayor importe** cuando hay varias contrapartidas.
- **`asiento`** → **FK real** (el objetivo declarado es poder vincular las tablas).
- **`condic`** → en movimientos de fondos solo existen los valores **1 (Real)** y **2
  (Presupuestado)**. Verificado contra la UI: `ordenpago_carga.html:48-52`,
  `ordenpago_listado.html:72-73`, `caja_diaria.html:61-71` y la bifurcación de caja mostrador
  (`views_htmx.py:940-1015`). Es coherente con la doctrina: el `3` no mueve fondos de la empresa,
  el `4` son ajustes del estudio y los `5/6/7` los genera el sistema.
  En **caja mostrador** la regla es: tipo de comprobante **PRE (Presupuesto) → `condic = 2`**;
  todos los demás → **`condic = 1`** (ver §6.3).
- **Alcance acotado** → el asiento contable de caja mostrador **se deja como viene**. Este plan
  solo agrega y puebla los campos nuevos de `tesoreria_movimiento_caja`.

---

## 3. Cambios de modelo — `tesoreria/models.py`

```python
class MovimientoCaja(AuditModel):
    sesion = models.ForeignKey(CajaSesion, on_delete=models.PROTECT, related_name="movimientos")

    # Empresa desnormalizada: toda consulta se acota por session['empresa_id'] y hoy había que
    # llegar por sesion -> caja -> empresa (tres JOINs en cada reporte).
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, null=True, blank=True,
                                db_index=True, verbose_name="Empresa")

    # FECHA DEL COMPROBANTE que origina el movimiento (recibo, OP, venta, retiro). Es la misma
    # que la del asiento contable y la que usan los reportes para el rango desde/hasta.
    # NO es la fecha de carga: un comprobante fechado el 15/08 puede registrarse el 20/09.
    # Cuándo se cargó el registro lo dice `fecha_creacion`, heredado de AuditModel.
    fecha = models.DateField(db_index=True, verbose_name="Fecha del Comprobante")

    tipo = models.CharField(max_length=1, choices=TIPO_MOVIMIENTO)
    importe = models.DecimalField(max_digits=15, decimal_places=2)
    concepto = models.CharField(max_length=200)
    condic = models.IntegerField(default=1, verbose_name="Condición Movimiento")

    # --- Vínculo contable (Plan 049) ---
    # El asiento es la FUENTE DE VERDAD de las contrapartidas: sus líneas llevan cada cuenta con
    # su importe exacto. Los asientos nunca se borran (solo se marcan anulado=True), así que la
    # FK no puede quedar colgada. Al recontabilizar, el comprobante re-estampa este campo.
    asiento = models.ForeignKey('contable.Asiento', on_delete=models.PROTECT,
                                null=True, blank=True, related_name='movimientos_caja',
                                verbose_name="Asiento Contable")

    # Cuenta de imputación PRINCIPAL = la contrapartida de mayor importe del asiento.
    # Cuando el comprobante imputa a varias cuentas (recibo simple, OP simple, venta mostrador
    # con varios rubros) este campo guarda solo la mayor: sirve para listados, filtros y
    # búsquedas, pero NO para cuadrar importes por cuenta. Para eso se leen las líneas del
    # asiento, que es donde está el desglose completo.
    cuenta = models.ForeignKey('contable.Cuenta', on_delete=models.PROTECT,
                               null=True, blank=True, related_name='movimientos_caja',
                               verbose_name="Cuenta de Imputación Principal")

    # Cliente/Proveedor del movimiento. Antes había que probar tres FK nulleables (recibo,
    # orden_pago, venta) y seguir la que estuviera seteada. Nulo en los movimientos internos
    # (retiro, cierre, rendición), igual que el id_cod del sistema legado.
    cli_pro = models.ForeignKey('facturacion.ClienteProveedor', on_delete=models.PROTECT,
                                null=True, blank=True, related_name='movimientos_caja',
                                verbose_name="Cliente/Proveedor")

    # Vinculación a comprobantes (sin cambios)
    recibo = models.ForeignKey(Recibo, on_delete=models.SET_NULL, null=True, blank=True)
    orden_pago = models.ForeignKey(OrdenPago, on_delete=models.SET_NULL, null=True, blank=True)
    venta = models.ForeignKey(Venta, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "tesoreria_movimiento_caja"
        verbose_name = "Movimiento de Caja"
        verbose_name_plural = "Movimientos de Caja"
        indexes = [
            models.Index(fields=['empresa', 'fecha']),      # EOAF: rango de fechas por empresa
            models.Index(fields=['empresa', 'cuenta']),     # EOAF: agrupación por cuenta
            models.Index(fields=['asiento']),               # join movimiento <-> asiento
            models.Index(fields=['cli_pro']),               # drill-down por entidad
        ]
        constraints = [
            # En movimientos de FONDOS solo existen Real y Presupuestado. El 3 (Ajuste) lo paga
            # el socio y no mueve plata de la empresa; el 4 son ajustes del estudio; los 5/6/7
            # los genera el sistema. Regla inflexible -> va a la base, no solo a la vista.
            models.CheckConstraint(condition=models.Q(condic__in=(1, 2)),
                                   name='mov_caja_condic_1_o_2'),
        ]
```

---

## 4. Migraciones

Tres migraciones separadas para que el backfill corra con el esquema ya alterado y sea
reejecutable.

### 4.1 `00XX_plan049_esquema.py` — esquema

1. `AlterField('MovimientoCaja', 'fecha', DateField(db_index=True))` — de `timestamp` a `date`.
   PostgreSQL castea con `USING fecha::date`, que es lo que emite Django. El campo ya está
   poblado en todas las filas (venía con `auto_now_add`), así que **no hace falta pasar por
   nullable**: el valor queda con la fecha de carga y el backfill lo corrige a continuación.
   El timestamp completo no se pierde: sigue en `fecha_creacion`.
2. `AddField` de `empresa`, `asiento`, `cuenta`, `cli_pro` (todas nullable).
3. Índices nuevos.

> El `CheckConstraint` de `condic` **no** se agrega acá: primero hay que verificar que no existan
> filas con otro valor (ver 4.2, paso 5).

### 4.2 `00XX_plan049_backfill.py` — datos (`RunPython`, con `reverse_code=noop`)

Recorre en lotes (`iterator()` + `bulk_update`, batch 2000) y completa:

1. **`empresa`** ← `sesion.caja.empresa_id`. Siempre resoluble.
2. **`fecha`** ← por orden de prioridad:
   - `recibo.fecha` si hay recibo
   - `orden_pago.fecha` si hay OP
   - `venta.fecha` si hay venta
   - en su defecto, se **deja como está** (ya es la fecha de carga casteada a `date`, que para
     los movimientos internos —retiro, cierre, rendición— es la fecha correcta)
3. **`cli_pro`** ← `recibo.cliente_id` / `orden_pago.proveedor_id` / `venta.cliente_id`. Null en
   los internos.
4. **`asiento`** ← `recibo.asiento_id` / `orden_pago.asiento_id` / `venta.asiento_id`.
   **Corrección sobre el análisis inicial:** la caja mostrador SÍ estampa el asiento en la venta
   (`views_htmx.py`, `venta.asiento_id = asiento.asiento_id`), así que el backfill también la
   resuelve. Solo quedan en null los movimientos internos (que no tienen comprobante) y los
   importados de VFP sin `ID_ASTO`.
   Los tres comprobantes guardan el asiento en un `IntegerField` sin FK, de modo que puede
   apuntar a un asiento inexistente: como el campo nuevo **sí** es FK, el backfill valida cada id
   contra la tabla de asientos y descarta los que no resuelven.
5. **`cuenta`** ← regla de la §5 aplicada sobre el asiento, solo para las filas que quedaron con
   asiento.
6. **Verificación previa al constraint:** contar filas con `condic NOT IN (1,2)`. Si hay, la
   migración aborta con el listado para revisión manual. **No se corrigen automáticamente.**

La migración informa por consola cuántas filas cambiaron de `fecha`, para dejar constancia del
alcance del reencuadre de períodos.

### 4.3 `00XX_plan049_constraints.py`

`AddConstraint('mov_caja_condic_1_o_2')`.

---

## 5. Regla de cálculo de `cuenta` — servicio único

Se implementa **una sola vez**, en `tesoreria/services/imputacion.py` (nuevo), y la usan los seis
circuitos. Evita mantener lógica distinta por comprobante.

```python
def cuenta_principal_del_asiento(asiento):
    """Cuenta de CONTRAPARTIDA de mayor importe de un asiento.

    Contrapartida = línea cuya cuenta NO es de disponibilidad (`tipo_disponibilidad = ''`).
    Las de disponibilidad son el lado de los fondos (caja, banco, valores), no el origen ni la
    aplicación. Si el asiento imputa a varias cuentas, devuelve la de mayor movimiento; el
    desglose completo queda en las líneas del asiento.
    """
```

Agrupa por `cuenta_id`, suma `debe + haber` por cuenta, descarta las de disponibilidad y devuelve
la de mayor total. Desempate determinístico por `cuenta_id` ascendente. Si el asiento no tiene
ninguna línea de contrapartida (caso teórico: traslado puro entre disponibilidades), devuelve
`None`.

El módulo expone además otras dos funciones:

- **`estampar_asiento(mov_caja, asiento)`** — asigna `asiento` + `cuenta` y guarda. Concentra en
  un solo lugar las tres líneas que si no habría que repetir en los seis circuitos. Tolera
  `asiento = None` (hay circuitos que no siempre asientan).
- **`condic_por_comprobante(tipo_comprobante)`** — la regla de §6.3.3: `PRE` → 2, el resto → 1.
  Se extrajo de la vista para poder probarla sin levantar el circuito completo de facturación,
  que exige preventa y respuesta de ARCA. Acepta el objeto `TipoComprobante` o su código.

---

## 6. Cambios en los circuitos

En los seis casos el asiento se genera **después** del `MovimientoCaja` (a propósito: el debe/haber
se arma leyendo los detalles de medios de pago). Por eso `asiento` y `cuenta` se estampan con un
`update_fields` posterior, dentro del mismo `transaction.atomic`, exactamente igual a como ya se
hace hoy con `TransaccionBancaria` y `ValorTerceros`.

### 6.1 Recibo — `views_htmx.py:443` y `:531`

- En el `create`: `empresa_id`, `fecha=recibo.fecha`, `cli_pro=recibo.cliente`.
- Después de `contabilizar_recibo`: `mov_caja.asiento = asiento`,
  `mov_caja.cuenta = cuenta_principal_del_asiento(asiento)`, `save(update_fields=[...])`.

### 6.2 Orden de Pago — `views_htmx.py:663` y `:758`

Simétrico: `fecha=op.fecha`, `cli_pro=op.proveedor`, y el mismo estampado posterior.

### 6.3 Caja mostrador — `views_htmx.py:1071`

**Alcance acotado por decisión del usuario: el asiento se deja exactamente como está.** No se
reemplaza el `Asiento.objects.create` manual de `:1176` por `crear_asiento()`, no se le asigna
`sesion_caja` y no se le pasa `condic`. Los cambios se limitan a `tesoreria_movimiento_caja`:

1. En el `create`: `empresa_id`, `fecha=venta.fecha`, `cli_pro=venta.cliente`.
2. Estampado posterior de `asiento` y `cuenta`, igual que en recibos y órdenes de pago.
3. **`condic` según el tipo de comprobante** (hoy está hardcodeado en 1 — bug §2.2.3):

   > Si el tipo de comprobante es **PRE (Presupuesto) → `condic = 2`**; para todos los demás,
   > **`condic = 1`**.

   Se calcula en el servidor a partir de `tipo_cbte`, no del `condic` que manda el navegador:

   ```python
   condic_mov = 2 if (tipo_cbte and str(tipo_cbte.codigo).upper() == 'PRE') else 1
   ```

   Las dos expresiones son equivalentes por construcción —`views_htmx.py:1017` asigna el tipo
   `PRE` exactamente cuando `condic == 2`, y la rama de AFIP corre solo con `condic == 1`—, pero
   derivarlo del comprobante no depende del payload del cliente.

   **Este punto sí entra en el alcance acotado**, porque `condic` es un campo de
   `tesoreria_movimiento_caja` y sin corregirlo el filtro Real/Presupuestado del EOAF clasifica
   mal todas las ventas presupuestadas.

Con `MovimientoCaja.asiento` poblado, el EOAF llega a las líneas del asiento a través del
movimiento y no necesita `sesion_caja`, así que la limitación no afecta a este plan. Lo que queda
pendiente se registra en §10.

### 6.4 Retiro parcial (:1323), Cierre (:1458) y Rendición (:1654)

- `empresa_id`, `fecha=timezone.localdate()`, `cli_pro=None`.
- `asiento`: son movimientos que generan **varios** asientos (traslado origen + destino) o
  ninguno (rendición sin diferencia). Se vincula el asiento del **lado que corresponde a la
  sesión del movimiento**; si no hay asiento, queda null.
- El `condic=1` de estos tres es **correcto** y no se toca: son movimientos internos, siempre
  reales.

---

## 7. Ajustes colaterales

1. **`contable/services/reversion.py:34-37`** — borra `MovimientoCaja` y sus detalles al revertir
   un comprobante. Verificar que no queden referencias colgadas y que el `PROTECT` del asiento no
   bloquee la reversión (no debería: se borra el movimiento, no el asiento).
2. **`tesoreria/services/caja_diaria.py:11-18`** — actualizar la docstring (§2.2.5) y evaluar la
   simplificación a **una sola fuente**: con `MovimientoCaja.asiento` poblado, la lógica de
   "si el comprobante ya tiene asiento estampado usá el asiento y omití el movimiento" se vuelve
   un simple filtro. Se hace en un plan aparte para no mezclar cambios de modelo con cambios de
   reporte.
3. **Consumidores de `MovimientoCaja.fecha`** — al pasar de `datetime` a `date` hay que revisar
   todo `order_by('fecha')`, comparación o formateo del campo. Relevado: `views_htmx.py:317,329`
   (listados de valores, ordenan por otro modelo) y `views_htmx.py:1610` (retiros, ordena por
   `RetiroCaja.fecha`, que **no** se toca).

   **Hallazgo durante la ejecución — bug latente que este cambio corrige.**
   `tesoreria/services/caja_diaria.py` arma una sola lista con las filas de las dos fuentes y la
   ordena por la tupla `(fecha, id)`:

   - fuente asientos → `'orden': (asiento.fecha, asiento.asiento_id)` — `asiento.fecha` es `date`
   - fuente movimientos → `'orden': (movimiento.fecha, movimiento.id)` — era `datetime`

   Ordenar esa lista mezclada lanza
   `TypeError: '<' not supported between instances of 'datetime.datetime' and 'datetime.date'`
   en cuanto una caja tiene movimientos de **ambas** fuentes, que es el caso normal apenas
   conviven un cobro de mostrador y un recibo. Al pasar `fecha` a `DateField` los dos lados
   quedan del mismo tipo y el reporte deja de romperse. Cubierto por el test 13.
4. **`migracion/scripts/03_migrar_tesoreria.py:139`** — el `bulk_create` deberá informar `fecha`
   desde `CAJA_DIARIA.FECHA` (que ya es `date` en el origen). El script legado **sí** tiene
   `ID_ASTO`, `ID_CTA` e `ID_COD`, así que en una remigración los tres campos nuevos se pueden
   poblar correctamente desde el origen.

---

## 8. Plan de pruebas

### 8.1 Automatizadas (`tesoreria/tests/test_plan049_movimiento_caja.py`, nuevo)

| # | Caso | Verifica |
|---|------|----------|
| 1 | Recibo tipo C con **fecha retroactiva** | `mov.fecha == recibo.fecha == asiento.fecha` (no la de carga) y `mov.fecha_creacion.date() == hoy` |
| 2 | Recibo tipo C | `mov.cli_pro == recibo.cliente`, `mov.asiento == asiento`, `mov.cuenta` = cta. patrimonial del cliente |
| 3 | Recibo Simple con imputaciones 60/40 | `mov.cuenta` = la del 60 %; las **dos** cuentas siguen en las líneas del asiento |
| 4 | Orden de Pago tipo P | Espejo del caso 2 con el proveedor |
| 5 | OP Simple 60/40 | Espejo del caso 3 |
| 6 | Venta mostrador con comprobante **PRE** | `mov.condic == 2` (regresión del bug §2.2.3) |
| 6b | Venta mostrador con comprobante fiscal (FA/FB/FC) | `mov.condic == 1` |
| 7 | Venta mostrador multi-rubro | `mov.cuenta` = rubro de mayor importe; `mov.asiento` apunta al asiento generado |
| 8 | Retiro y cierre | `cli_pro` null, `condic == 1`, `fecha` = fecha operativa |
| 9 | `condic = 3` | El `CheckConstraint` rechaza el INSERT (`IntegrityError`) |
| 10 | Recontabilización de un recibo | El asiento viejo queda `anulado=True` y `mov.asiento` apunta al **nuevo** |
| 11 | `cuenta_principal_del_asiento` | Descarta líneas de disponibilidad; desempate determinístico; `None` si no hay contrapartida |
| 12 | `condic_por_comprobante` | `PRE`/`pre` → 2; `6`, `FA`, `None` → 1 |
| 13 | **Caja Diaria con las dos fuentes** | `armar_caja_diaria` no rompe al ordenar filas de asientos junto a filas de movimientos (regresión del bug de §7.3) |
| 14 | Reversión de un recibo | No quedan referencias colgadas |

Ejecución: `python manage.py test tesoreria.tests.test_plan049_movimiento_caja`, más la suite
completa de `tesoreria` y `contable` para detectar regresiones.

### 8.2 Manuales

1. Cargar un recibo **con fecha de un mes anterior** y verificar en base que `fecha` sea la del
   recibo y `fecha_creacion` la de hoy.
2. Cobrar una venta mostrador en modo **Presupuestado** y confirmar `condic = 2` en el movimiento.
3. Verificar que la Caja Diaria siga mostrando lo mismo que antes del cambio (no regresión).
4. Sobre la base migrada, contar movimientos con `asiento IS NULL` y confirmar que se corresponden
   con caja mostrador previa y registros importados de VFP.

---

## 9. Riesgos

| Riesgo | Mitigación |
|--------|------------|
| El backfill de `fecha` cambia el período de movimientos históricos | Es la corrección buscada. La migración informa el recuento de filas alteradas |
| El cambio de `datetime` a `date` rompe algún consumidor del campo | Relevamiento en §7.3 + suite completa de tests |
| `PROTECT` en `asiento` bloquea algún borrado existente | Los asientos no se borran nunca (verificado en `anular_asiento_de_comprobante`). Cubierto por el test 12 |
| Tocar el circuito de facturación de caja mostrador | Evitado: el asiento se deja intacto (§6.3). Solo se agregan campos a `tesoreria_movimiento_caja` |
| Filas históricas con `condic` fuera de (1,2) | La migración de backfill aborta y las lista antes de aplicar el constraint |

---

## 10. Estado y siguientes pasos

Este plan es el **prerrequisito** del Estado de Origen y Aplicación de Fondos. Una vez ejecutado:

- **Plan 050 — EOAF:** grilla jerárquica sobre el plan de cuentas con **Ingresos de Fondos /
  Egresos de Fondos / Flujo Neto** (sin Disponibilidad Inicial, por decisión del usuario:
  el reporte analiza el flujo entre dos fechas y el acumulado anterior está fuera de lugar),
  filtro Real/Presupuestado, desglose por medio (efectivo, valores, banco, dólares, tarjetas,
  retenciones), drill-down por cuenta y exportación a Excel y PDF.
- **Plan 051 (opcional):** unificación de las dos fuentes del reporte de Caja Diaria (§7.2).

### Deuda técnica — CERRADA (16/08/2026, a pedido del usuario)

Tras la ejecución inicial se decidió corregir también el asiento de caja mostrador. Se le agregó:

- **`condic=venta.condic`** — el asiento hereda la condición del comprobante, como manda
  `.cursorrules`. Antes quedaba en el default 1 aunque la venta fuera presupuestada.
- **`sesion_caja=sesion_caja`** — sin esto los cobros de mostrador no aparecían en el reporte de
  Caja Diaria, que filtra los asientos por ese campo.
- **`fecha=venta.fecha`** en lugar de `timezone.localdate()`, para que el asiento, el movimiento
  de caja y el comprobante lleven siempre la misma fecha.

**Efecto colateral que hubo que resolver.** Al estampar `sesion_caja`, el cobro de mostrador pasa
a llegar al reporte por sus **dos** fuentes. La deduplicación de `_lineas_desde_movimientos()`
navegaba al comprobante y su cadena solo contemplaba `recibo` y `orden_pago`: los cobros de
mostrador cuelgan de `venta`, así que **se habrían contado dos veces**. Ahora se deduplica por
`MovimientoCaja.asiento_id` —el campo que crea este mismo plan—, con el comprobante como
fallback para los movimientos históricos anteriores al backfill. Cubierto por el test 18.

Lo único que NO se tocó es la forma de armar el asiento: sigue con `Asiento.objects.create` +
`AsientoLinea.objects.create` en vez de `crear_asiento()`. Es un refactor del circuito de
facturación, sin impacto funcional pendiente.

---

## Anexo A — Correspondencia con el sistema VFP

| `caja_diaria` (VFP) | `tesoreria_movimiento_caja` (después de este plan) |
|---------------------|-----------------------------------------------------|
| `CAJA` | `sesion.caja` |
| `FECHA` (D) | `fecha` ✔ ahora `date`, con la fecha del comprobante |
| `MODIFICADO` (T) | `fecha_creacion` / `fecha_modificacion` (AuditModel) |
| `ID_ASTO` | `asiento` ✔ nuevo |
| `ID_CTA` | `cuenta` ✔ nuevo (mayor importe; el desglose vive en las líneas del asiento) |
| `ID_COD` | `cli_pro` ✔ nuevo |
| `CONCEPTO` | `concepto` |
| `CONDIC` | `condic` (restringido a 1 y 2) |
| `INGRESOS` / `EGRESOS` | `importe` + `tipo` |
| `EFECTIVO`, `DOLARES`, `BANCO`, `VALORES`, `TARJETAS` | `MovimientoCajaDetalle.medio_pago` → `MedioPago.cuenta_contable` |
| `ID_USU` | `creado_por` (AuditModel) |
| — | `empresa` ✔ nuevo (el legado es mono-empresa por carpeta de ejercicio) |
