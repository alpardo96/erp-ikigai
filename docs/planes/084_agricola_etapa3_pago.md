# Plan 084 — Agrícola Etapa 3: Pago al Productor y Retención de Ganancias

## Estado: ✅ Completado (2026-09-07)

**Fecha:** 2026-09-07
**Plan integral:** [`docs/agricola/plan inicial agricola.md`](../agricola/plan%20inicial%20agricola.md) — Etapa 3
**Requiere:** [080](080_terminos_enchufables_saldos_stock.md) ✅ · [081](081_agricola_etapa0_maestros_tabaco.md) ✅ · [082](082_agricola_etapa1_romaneo.md) ✅ · [083](083_agricola_etapa2_liquidacion.md) ✅

---

## Objetivo

Cancelar las liquidaciones del productor con una Orden de Pago, practicando la **retención de
Ganancias sobre el acumulado mensual** y emitiendo su certificado.

Cierra el circuito del acopio: `romaneo → liquidación → pago`.

---

## 1. La decisión que ordena todo: la retención es un medio de pago

Ikigai ya sabe practicar retenciones **en el pago**: `MedioPago` de categoría `RET`, que
`contabilizar_orden_pago()` acredita contra la cuenta configurada. No hay que construir un
mecanismo nuevo — hay que **usar el que existe**.

Eso decide la forma del módulo:

```
OrdenPago.total = Σ medios de pago entregados (efectivo, cheque, transferencia)
                + retención de Ganancias   ← también es un "medio", sólo que no sale plata

Σ aplicaciones a liquidaciones = OrdenPago.total
```

El asiento lo arma el core sin cambios: DEBE la cuenta del productor por el total, HABER cada
medio de pago —incluida la retención, que va a su cuenta de pasivo—.

Es además lo que hace que el término de cuenta corriente del Plan 083 cierre exacto: la
liquidación aportó el **total** (neto + IVA − retenciones de liquidación) y la OP lo cancela
entero, retención incluida. Es el supuesto S-1 de `saldos.py`, ahora del lado de la verticalidad.

---

## 2. Cálculo de la retención de Ganancias

Es la única con base **acumulada mensual**, y por eso su momento es el PAGO y no la liquidación.

```
base_mes  = Σ netos de las liquidaciones que se pagan ahora
          + Σ netos de las liquidaciones del productor ya pagadas en el mismo mes

SI base_mes > MNI:
        retención_del_mes = REDONDEO((base_mes − MNI) × alícuota / 100, 2)
        a_retener         = retención_del_mes − ya_retenido_en_el_mes
SI NO:
        a_retener = 0
```

Con los valores cargados: alícuota **2 %**, MNI **224.000**, régimen **78**, sólo a Responsables
Inscriptos. Son datos del maestro, no constantes.

**El acumulado se DERIVA, no se almacena.** Se reconstruye sumando los certificados ya emitidos
del productor en el período. El sistema heredado hacía lo mismo: `liq_mes_ret_gcia` era una vista,
no una tabla. Un contador incremental no se puede reconstruir y termina derivando.

> Consecuencia deliberada: si se anula un pago, su certificado se anula y el acumulado del mes
> baja solo. No hay nada que "descontar a mano".

---

## 3. Modelos

| Modelo | `db_table` | Campos clave |
|---|---|---|
| `LiquidacionPago` | `agricola_tabaco_liquidacion_pago` | liquidacion, orden_pago (FK `tesoreria.OrdenPago`), importe, anulado |
| `RetencionPago` | `agricola_tabaco_retencion_pago` | orden_pago, productor, tipo_retencion + **copia de la regla**, periodo, base_del_pago, base_acumulada, minimo_no_imponible, retencion_del_mes, retenido_previo, **importe**, nro_certificado, fecha, anulado |

`LiquidacionPago` vive **del lado de la verticalidad**: `tesoreria.OrdenPagoAplicacion.compra` es
un FK duro a `Compra` con `PROTECT` y no puede apuntar a una liquidación. La dependencia va
verticalidad → core, nunca al revés (Plan 075).

`RetencionPago` es a la vez el certificado y el registro que alimenta el acumulado del mes.

---

## 4. Servicios

| Servicio | Qué hace |
|---|---|
| `liquidaciones_pendientes` | Liquidaciones confirmadas del productor con saldo > 0 |
| `calcular_ganancias` | Base acumulada, MNI, retención del mes y a retener, sin grabar |
| `pagar_liquidaciones` | Atómico: crea la OP, sus medios de pago, la retención, las imputaciones y el certificado; contabiliza y recalcula saldos |
| `anular_pago` | Anula la OP y su asiento, libera las liquidaciones y anula el certificado |
| `recalcular_saldo_liquidacion` | `pagado` = Σ imputaciones activas; `saldo` = total − pagado |

`pagar_liquidaciones` toma `select_for_update()` sobre cada liquidación: sin eso, dos pagos
simultáneos podrían cancelar dos veces el mismo saldo.

### El medio de pago de la retención

Se resuelve con `get_or_create` de un `MedioPago` de categoría `RET` por concepto, con la
**cuenta contable del propio concepto**. Así el asiento del core deposita la retención en la
cuenta que el contador definió en el maestro, sin pedirle al usuario que configure dos veces lo
mismo.

---

## 5. Integración con el Plan 080

Se estrena el tercer punto de extensión, el único que quedaba sin usar:

```python
registrar_aplicacion_op({
    'nombre':        'agricola_tabaco_liquidacion_pago',
    'modelo':        LiquidacionPago,
    'campo_op':      'orden_pago',
    'campo_importe': 'importe',
})
```

Sin esto, una OP que cancela liquidaciones figuraría **eternamente como "sin aplicar"** en el
listado de tesorería.

---

## 6. Interfaz

Pantalla propia de la verticalidad, **no** una modificación del alta de OP del core: ese
endpoint es un API JSON con un frontend complejo y sólo entiende de `Compra`. Acá el operador:

1. elige el productor (Typeahead + Lupa);
2. ve sus liquidaciones con saldo y las tilda;
3. ve **en vivo** la retención de Ganancias calculada sobre el acumulado del mes;
4. carga los medios de pago (efectivo, transferencia o cheque);
5. confirma: se crea la OP, se imputa, se retiene y se contabiliza.

Con formato es-AR y el filtro de `condic` en el listado, como todo el módulo.

---

## 7. Tests mínimos

| Test | Qué verifica |
|---|---|
| `test_pago_total_deja_la_liquidacion_en_cero` | `pagado` y `saldo` derivados de las imputaciones |
| `test_pago_parcial` | Saldo remanente correcto |
| `test_ganancias_bajo_el_minimo_no_retiene` | Base ≤ MNI → 0 |
| `test_ganancias_sobre_el_minimo` | `(base − MNI) × 2 %` |
| `test_acumulado_mensual_de_dos_pagos` | El segundo pago descuenta lo ya retenido |
| `test_acumulado_no_cruza_de_mes` | Otro período arranca de cero |
| `test_monotributista_no_sufre_ganancias` | El flag `solo_responsable_inscripto` se respeta |
| `test_la_retencion_es_un_medio_de_pago` | Aparece como `MovimientoCajaDetalle` categoría RET |
| `test_asiento_de_la_op_balanceado` | DEBE productor = HABER medios + retención |
| `test_la_op_no_queda_sin_aplicar` | `pendiente_de_aplicar_op()` da 0 (Plan 080) |
| `test_saldo_del_productor_vuelve_a_cero` | Liquidación + pago se compensan |
| `test_certificado_se_numera` | Serie por empresa |
| `test_anular_pago_revierte_todo` | Asiento anulado, saldo restituido, certificado anulado |
| `test_anular_baja_el_acumulado_del_mes` | El siguiente pago recalcula bien |
| `test_no_se_paga_una_liquidacion_anulada` | Ni en borrador |
| `test_aislamiento_multiempresa` | No se pagan liquidaciones de otra empresa |

---

## 8. Criterio de Hecho

- [x] Modelos, restricciones y migraciones aplicados — `LiquidacionPago` y `RetencionPago`.
- [x] Acumulado mensual **derivado** de los certificados vigentes, no almacenado.
- [x] Retención como `MedioPago` categoría RET; asiento por `contabilizar_orden_pago()` del core.
      **Cero cambios al core.**
- [x] `registrar_aplicacion_op` registrado con importación tolerante — **el tercer y último punto
      de extensión del Plan 080 queda en uso**.
- [x] Pantalla propia con Typeahead + Lupa, formato es-AR y filtro de `condic`.
- [x] Tests en verde — **29/29** de servicio y **20/20** de pantalla.
- [x] Prueba de desenchufe: los tres registros en 0; saldo y pendiente de OP siguen calculando.
- [x] `makemigrations --check` sin cambios pendientes.
- [x] `docs/walkthrough.md` actualizado.

### Prueba de humo del circuito completo (datos reales, revertida)

```
LIQUIDACIÓN A 0002-00000001   neto $ 3.250.000   total $ 3.532.750
  saldo del productor tras liquidar          $ −3.532.750

RETENCIÓN GANANCIAS
  base acumulada del mes      $ 3.250.000
  mínimo no imponible        − $   224.000
  alícuota 2 %      →  a retener $ 60.520

ORDEN DE PAGO 0001-00010002   total $ 3.532.750
  211001  PROVEEDORES VARIOS            D 3.532.750
  111001  CAJA TESORERIA                              H 3.472.230
  214005  AFIP-RET.GCIAS.PRACTICADAS                  H    60.520
                                        D 3.532.750   H 3.532.750   BALANCEA

  Certificado Nº 1 · régimen 78 · período 202609 · $ 60.520
  Saldo de la liquidación : $ 0,00
  Saldo del productor     : $ 0,00
  Pendiente de aplicar OP : $ 0,00
```

Las tres últimas líneas son el cierre del negocio: la liquidación queda cancelada, el productor
en cero y la Orden de Pago **no figura como "sin aplicar"** —eso último gracias al punto de
extensión del Plan 080—.

### Alcance de los medios de pago

La pantalla maneja efectivo, transferencia, billetera y otros. **Los cheques quedan fuera**:
propios y de terceros arrastran vencimiento, cuenta bancaria, estado en cartera y conciliación,
y se cargan por Tesorería. Se avisa en pantalla en vez de dejar cargar algo a medias.

### Observación de entorno — la causa de las caídas de PostgreSQL

Durante las Etapas 0, 2 y 3 el backend de PostgreSQL se cayó varias veces
(`server closed the connection unexpectedly`) en corridas largas. **La causa era la concurrencia,
no el servidor**: esas corridas competían contra otras suites que se estaban ejecutando en
paralelo sobre la misma instancia.

La corrida final de esta etapa, con la máquina para ella sola, lo confirma:

| Corrida | Tests | Tiempo | Caídas |
|---|---|---|---|
| Etapa 1 (con suites en paralelo) | 729 | 6.395 s | — |
| Etapa 2 (con suites en paralelo) | 793 | 6.415 s | 1 |
| **Etapa 3 (sin competencia)** | **846** | **1.156 s** | **0** |

Más tests en **la quinta parte del tiempo** y sin una sola caída. La recomendación cambia: no hay
que revisar el servidor, hay que **no correr suites concurrentes** contra la misma instancia.
