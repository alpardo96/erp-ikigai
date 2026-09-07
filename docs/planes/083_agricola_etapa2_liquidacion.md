# Plan 083 — Agrícola Etapa 2: Liquidación de Compra de Tabaco

## Estado: 🔶 En Progreso

**Fecha:** 2026-09-06
**Plan integral:** [`docs/agricola/plan inicial agricola.md`](../agricola/plan%20inicial%20agricola.md) — Etapa 2
**Requiere:** [Plan 080](080_terminos_enchufables_saldos_stock.md) ✅ · [081](081_agricola_etapa0_maestros_tabaco.md) ✅ · [082](082_agricola_etapa1_romaneo.md) ✅

---

## Objetivo

Convertir uno o varios romaneos confirmados en el **comprobante de compra** que la empresa emite
al productor: calcular IVA y retenciones, generar el asiento, alimentar el Libro IVA y hacer
nacer la deuda en la cuenta corriente.

Es la primera etapa con **efectos contables reales**. Acá se usa, por fin, el término de cuenta
corriente que el Plan 080 dejó preparado.

---

## 1. Alcance

### Incluido
- `LiquidacionTabaco`, `LiquidacionDetalle` y `LiquidacionRetencion`.
- Cálculo de IVA y de las retenciones de momento `LIQUIDACION`, con la regla **congelada**.
- Asiento por `contable.services.asientos.crear_asiento()`.
- `LibroIvaCompras` + `LibroIvaAlic` colgados del `asiento_id`.
- Registro del término de cuenta corriente (Plan 080) y recálculo del saldo del productor.
- Anulación con reversión del asiento y del Libro IVA, sin tocar el romaneo.
- Pantallas: listado, emisión, detalle e impresión.

### Fuera de alcance
- **Pago** e imputación de la Orden de Pago (Etapa 3), y con él la retención de Ganancias.
- Movimiento de stock (Etapa 4).
- Notas de crédito de liquidación (mejora MP-01) y emisión por webservice (MP-02).

---

## 2. Cálculo

Sea `neto` la suma de los importes de los romaneos incluidos.

### 2.1 IVA y letra del comprobante

```
SI productor.condicion_iva == 'RESPONSABLE INSCRIPTO':
        iva   = REDONDEO(neto × alicuota_iva, 2)     → letra A · código ARCA 150
SI NO:
        iva   = 0                                     → letra B · código ARCA 151
```

`alicuota_iva` es un parámetro nuevo de `ConfiguracionTabaco` (default 21,00), no una constante.

### 2.2 Retenciones de liquidación

Se aplican los conceptos **vigentes a la fecha** con `momento = LIQUIDACION`, salteando los que
tienen `solo_responsable_inscripto` cuando el productor no lo es:

| `tipo_base` | Base | En esta etapa |
|---|---|---|
| `NETO` | el neto de la liquidación | ✅ se aplica |
| `IVA` | el IVA del comprobante | ✅ se aplica |
| `ACUM_MENSUAL` | acumulado mensual − MNI | ❌ **no**: su momento es el PAGO (Etapa 3) |

```
importe = REDONDEO(base × alicuota / 100, 2)
```

Cada retención aplicada guarda una **copia de la regla** (alícuota, tipo de base, mínimo y cuenta)
además de la FK al concepto. Si mañana cambia la alícuota, la liquidación sigue siendo
reconstruible.

### 2.3 Importes de cierre

```
retenciones_liquidacion = Σ importes de las retenciones aplicadas
total                   = neto + iva − retenciones_liquidacion     ← DEUDA con el productor
```

`total` es lo que se acredita al productor en el asiento, lo que suma el término de cuenta
corriente y lo que después cancela la Orden de Pago. **No es el neto a pagar**: la retención de
Ganancias se practica al pagar y `OrdenPago.total` ya la incluye como medio de pago, así que si el
término sumara el neto de Ganancias la OP cancelaría de más (supuesto S-1 de `saldos.py`).

---

## 3. Asiento

`crear_asiento(..., condic=liquidacion.condic, modulo=5, cli_pro=productor)`.
`modulo=5` es Compras: hace que la liquidación aparezca junto a las compras en el Libro Diario y
en los reportes filtrados por módulo, sin inventar un módulo nuevo.

| | Cuenta | Importe |
|---|---|---|
| **DEBE** | Bienes de Cambio – Tabaco (`ConfiguracionTabaco`) | neto |
| **DEBE** | IVA Crédito Fiscal (`ParametrosContables.cta_iva_credito`) *(sólo letra A)* | iva |
| **HABER** | Cuenta de pasivo de cada retención *(una línea por concepto)* | importe |
| **HABER** | Cuenta patrimonial del productor (`cta_pat`, o `cta_proveedores_default`) | total |

`DEBE = neto + iva` · `HABER = Σretenciones + total = neto + iva`. ✔

---

## 4. Libro IVA

Sin ningún cambio en el core: se cuelga del `asiento_id`, que no es un FK.

| Campo | Letra A | Letra B |
|---|---|---|
| `codiva` | 150 | 151 |
| `neto_gravado` | neto | 0 |
| `no_gravado` | 0 | neto |
| `iva_total` | iva | 0 |
| `otros` | Σ retenciones | Σ retenciones |
| `total` | total | total |
| `LibroIvaAlic` | 1 fila con la alícuota | **ninguna** |

> **Decisión a confirmar con el contador.** Una compra a monotributista o exento no genera crédito
> fiscal, por eso en letra B el importe va a `no_gravado` y no se generan filas de alícuota. Si el
> criterio del estudio fuera otro, se cambia en un solo lugar.

---

## 5. Modelos

| Modelo | `db_table` | Campos clave |
|---|---|---|
| `LiquidacionTabaco` | `agricola_tabaco_liquidacion` | empresa, sucursal, productor, letra, codiva, punto, numero, fecha, periodo, `origen_autorizacion`, cai/cae + vencimiento, neto, alicuota_iva, iva, retenciones, **total**, pagado, saldo, `asiento_id`, `condic`, estado, motivo_anulacion |
| `LiquidacionDetalle` | `agricola_tabaco_liquidacion_detalle` | liquidación, romaneo, clase, kilos, fardos, precio, importe |
| `LiquidacionRetencion` | `agricola_tabaco_liquidacion_retencion` | liquidación, tipo_retencion, **copia de la regla**, base, alícuota, importe, cuenta_contable, nro_certificado |

`RomaneoTabaco` gana una FK `liquidacion` (nullable, `PROTECT`). **Es lo que impide liquidar dos
veces los mismos kilos**, por construcción y no por convención: un romaneo pertenece a lo sumo a
una liquidación.

El detalle se agrupa **por (romaneo, clase)** y no por fardo: es lo que se imprime y lo que el
productor verifica. La trazabilidad al fardo no se pierde — el fardo apunta al romaneo y el
romaneo a la liquidación.

### Estados

`BORRADOR (1) → CONFIRMADA (2)` · `ANULADA (9)`

---

## 6. Servicios

| Servicio | Qué hace |
|---|---|
| `preparar_liquidacion` | Arma el borrador desde romaneos confirmados y sin liquidar del mismo productor |
| `calcular` | Neto, IVA y retenciones vigentes, sin grabar (para previsualizar en pantalla) |
| `confirmar_liquidacion` | Atómico: numera, congela reglas, crea asiento, puebla Libro IVA, marca romaneos, recalcula saldo |
| `anular_liquidacion` | Anula el asiento, limpia el Libro IVA, libera los romaneos, recalcula saldo |

`confirmar_liquidacion` toma `select_for_update()` sobre la liquidación y es **idempotente**: si ya
estaba confirmada, devuelve la misma sin renumerar ni duplicar asiento.

---

## 7. Integración con el Plan 080

```python
registrar_termino_ctacte({
    'nombre':        'agricola_tabaco_liquidaciones',
    'modelo':        LiquidacionTabaco,
    'campo_entidad': 'productor',
    'campo_empresa': 'empresa_id',
    'campo_importe': 'total',
    'signo':         -1,                       # mismo signo que compras: nos genera deuda
    'excluir':       ~Q(estado=CONFIRMADA),    # borradores y anuladas no son deuda
})
```

Se registra desde `verticalidades/agricola/tabaco/apps.py::ready()` con importación tolerante.
Al desenchufar la carpeta el término no se registra y el saldo se calcula como antes.

---

## 8. Tests mínimos

| Test | Qué verifica |
|---|---|
| `test_letra_a_para_responsable_inscripto` | 150, IVA discriminado |
| `test_letra_b_para_monotributista` | 151, IVA en cero |
| `test_retenciones_de_liquidacion` | EEAOC, Uso de Agua, Salud Pública sobre el neto; Ret. IVA sobre el IVA |
| `test_ganancias_no_se_practica_al_liquidar` | Su momento es el PAGO |
| `test_retenciones_solo_ri_no_aplican_a_monotributo` | El flag se respeta |
| `test_reglas_congeladas` | Cambiar la alícuota después no altera la liquidación |
| `test_asiento_balanceado` | Y con las cuentas correctas por concepto |
| `test_libro_iva_a_y_b` | Campos y alícuotas según letra |
| `test_saldo_del_productor` | La deuda aparece por el término del Plan 080 |
| `test_confirmar_es_idempotente` | Un reintento no duplica asiento ni renumera |
| `test_no_se_liquida_dos_veces_el_mismo_romaneo` | La FK lo impide |
| `test_solo_romaneos_confirmados` | Borradores y anulados quedan fuera |
| `test_anular_revierte_todo` | Asiento anulado, Libro IVA limpio, romaneos liberados, saldo en cero |
| `test_anular_no_toca_los_fardos` | La recepción física sobrevive |
| `test_aislamiento_multiempresa` | No se liquidan romaneos de otra empresa |
| `test_pantallas` | Listado, emisión, detalle e impresión |

---

## 9. Criterio de Hecho

- [ ] Modelos, restricciones y migraciones aplicados.
- [ ] `alicuota_iva` agregada a `ConfiguracionTabaco` (aditiva, default 21).
- [ ] Servicios atómicos, idempotentes y con bloqueo.
- [ ] Asiento por `crear_asiento()`; Libro IVA por `asiento_id`. **Cero cambios al core.**
- [ ] Término de cuenta corriente registrado con importación tolerante.
- [ ] Pantallas con Typeahead + Lupa, formato es-AR y filtro de `condic`.
- [ ] Tests en verde.
- [ ] Prueba de desenchufe.
- [ ] Suite completa sin fallas nuevas (baseline actual: 13 preexistentes).
- [ ] `docs/walkthrough.md` actualizado.
