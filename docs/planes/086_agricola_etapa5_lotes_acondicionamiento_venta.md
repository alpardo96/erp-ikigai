# Plan 086 — Agrícola Etapa 5: Lotes de acopio, acondicionamiento y venta

## Estado: ✅ Completado (2026-09-07)

**Fecha:** 2026-09-07
**Plan integral:** [`docs/agricola/plan inicial agricola.md`](../agricola/plan%20inicial%20agricola.md) — Etapa 5
**Requiere:** [080](080_terminos_enchufables_saldos_stock.md) ✅ · [081](081_agricola_etapa0_maestros_tabaco.md) ✅ · [082](082_agricola_etapa1_romaneo.md) ✅ · [083](083_agricola_etapa2_liquidacion.md) ✅ · [084](084_agricola_etapa3_pago.md) ✅ · [085](085_agricola_etapa4_stock.md) ✅

---

## Objetivo

Cerrar el circuito comercial del acopio: **agrupar** los fardos comprados en lotes,
**acondicionarlos** registrando insumos y mermas, **venderlos** por el circuito de siempre y
**medir el margen** — por lote y por fardo.

Hasta acá el tabaco entraba (romaneo), se facturaba al productor (liquidación), se pagaba (orden
de pago) y sumaba kilos al stock. Lo que faltaba es qué pasa con esos kilos **después**.

---

## 1. DA-07 se resuelve por configuración, no por código

El plan integral deja abierta la decisión **DA-07 — "procesos reales de acondicionamiento, mermas
normales y coproductos"**. No la resuelvo adivinando qué hace la planta: la convierto en un
**maestro que el usuario carga**.

`ProcesoAcondicionamiento` es una tabla de configuración con el nombre del proceso y su merma
normal esperada. Si mañana aparece un proceso nuevo, es un alta en una pantalla, no una migración.

**Consecuencia deliberada:** este plan no sabe —ni necesita saber— si la planta despalilla, seca o
reenfarda. Sabe que *un proceso toma kilos, devuelve kilos, consume plata y pierde peso*. Eso es
todo lo que el modelo necesita para ser correcto.

Lo único que queda pendiente de DA-07 es **cargar los procesos reales**, que es dato operativo.

---

## 2. Alcance contable: esta etapa NO genera asientos

Es la decisión más importante del plan y merece justificarse, porque es contraintuitiva.

El ERP **no contabiliza el stock**: `StockSucursal` lleva cantidades, y `VentaItem.cto_rep` guarda
el costo sólo para análisis de rentabilidad. No hay asiento de costo de mercadería vendida ni
valuación de existencias.

Entonces, ¿de dónde sale la contabilidad del acondicionamiento? **Ya está.** Los insumos, la mano
de obra y los servicios se compran con una `Compra` normal —el usuario lo dejó dicho: *"Por ahí
irán todas las compras de insumos, agroquímicos, etc."*— y esa compra ya generó su asiento, su
Libro IVA y su deuda con el proveedor.

Lo que falta no es contabilizar de nuevo: es **imputar** ese costo ya contabilizado a un lote para
poder calcular el margen. Por eso `AcondicionamientoCosto` tiene un FK **opcional** a `Compra`:
sirve de respaldo y de trazabilidad, pero la línea de costo no crea ni modifica un solo asiento.

> Contabilizar dos veces el mismo insumo —una por la compra y otra por el acondicionamiento—
> duplicaría el gasto en el balance. La imputación al lote es **gerencial**, no contable.

La venta sí genera asiento, pero por el circuito de siempre (`facturacion`), sin una línea de
código nueva de esta etapa.

---

## 3. Modelo de datos

### 3.1 `LoteAcopio` — el lote comercial

| Campo | Tipo | Nota |
|---|---|---|
| `empresa`, `sucursal` | FK | |
| `punto`, `numero` | int | Serie propia, contador `LOTE_TABACO` |
| `fecha`, `campania`, `variedad` | | Un lote es de **una** variedad: el stock se lleva por variedad |
| `descripcion` | Char | |
| `estado` | int | `1` Borrador · `2` Armado · `3` Acondicionado · `4` Vendido · `9` Anulado |
| `venta` | FK `facturacion.Venta` null | La venta que lo despachó |
| `total_fardos`, `total_kilos` | derivados | Kilos **de compra** |
| `kilos_actuales` | derivado | `total_kilos − bajas de acondicionamiento` |
| `costo_compra` | derivado | `Σ fardo.importe + Σ fardo.adicional` |
| `costo_acondicionamiento` | derivado | `Σ` líneas de costo de acondicionamientos cerrados |
| `importe_venta` | derivado | Neto de la venta, **sólo las líneas del producto de la variedad** |

### 3.2 La pertenencia vive en el fardo

```python
FardoTabaco.lote = FK(LoteAcopio, null=True, related_name='fardos')
```

Igual que `RomaneoTabaco.liquidacion`, y por la misma razón que está documentada ahí: siendo un
FK simple, **un fardo pertenece a lo sumo a un lote** y "no vender dos veces los mismos kilos"
queda garantizado por el modelo, no por una validación que alguien puede olvidar.

`FardoTabaco.ESTADOS` ya preveía `EN_LOTE`, `ACONDICIONADO` y `VENDIDO` desde la Etapa 1.

**Qué fardos pueden entrar:** sólo de romaneos `CONFIRMADO` o `LIQUIDADO` —un borrador no existe
físicamente y un anulado no ocurrió—, de la **misma variedad y la misma sucursal** que el lote.

### 3.3 `ProcesoAcondicionamiento` — el maestro (DA-07)

`empresa`, `codigo`, `detalle`, `merma_normal_porcentaje`, `orden`, `activo`.

### 3.4 `Acondicionamiento` — la corrida del proceso sobre un lote

| Campo | Nota |
|---|---|
| `lote`, `proceso`, `fecha`, `numero` | `numero` correlativo **dentro del lote**: no merece una serie global |
| `kilos_entrada`, `kilos_salida` | Los pesa el operario |
| `kilos_coproductos` | derivado de las líneas |
| `kilos_baja` | derivado = `entrada − salida`. **Es lo que el término de stock resta** |
| `kilos_merma` | derivado = `entrada − salida − coproductos`. La pérdida real |
| `merma_normal_esperada` | derivado = `entrada × proceso.merma_normal_porcentaje` |
| `merma_extraordinaria` | derivado = `max(0, merma − esperada)`. **Es lo que hay que explicar** |
| `motivo_merma` | Obligatorio si hay merma extraordinaria |
| `estado` | `1` Borrador · `2` Cerrado · `9` Anulado |

`AcondicionamientoCoproducto`: `producto` (FK core), `kilos`, `valor_estimado`.
`AcondicionamientoCosto`: `concepto`, `importe`, `compra` (FK opcional, respaldo).

#### La distinción que justifica el modelo

**Merma** = kilos que desaparecen. **Coproducto** = kilos que dejan de ser tabaco de esa variedad
y pasan a ser *otra cosa vendible* (el palo, el descarte). Sin esta distinción el usuario
registraría el palo como merma y perdería un activo real.

Por eso el stock se mueve así:

```
stock(variedad)   = Σ fardos − Σ kilos_baja        # baja = entrada − salida: TODO lo que salió
stock(coproducto) = Σ coproducto.kilos             # y reaparece en su propio producto
```

`kilos_baja` incluye los coproductos justamente porque **ya no son tabaco de esa variedad**.

### 3.5 Un lote, una venta

`LoteAcopio.venta` es un FK simple: un lote se vende entero. Es la contrapartida natural de
*"lote comercial"* —el lote se arma **para** una venta— y hereda la misma garantía de modelo que
`romaneo.liquidacion`.

**Limitación conocida y su salida:** para vender la mitad, se arman dos lotes. Los fardos se
pueden mover mientras el lote no tenga un acondicionamiento cerrado.

---

## 4. Margen

```
margen(lote)  = importe_venta + valor de coproductos − (costo_compra + costo_acondicionamiento)
```

**Margen por fardo** — el entregable que pide el plan integral:

| Componente | Cómo se obtiene |
|---|---|
| Costo de compra | `fardo.importe + fardo.adicional` — **exacto**, no prorrateado |
| Costo de acondicionamiento | Prorrateado por `fardo.kilos / lote.total_kilos` |
| Ingreso | Prorrateado por `fardo.kilos / lote.total_kilos` |
| Margen | `ingreso − (compra + acondicionamiento)` |

El costo de compra es exacto porque **existe por fardo**: es lo que se le pagó al productor por
ese fardo. Lo de acondicionamiento se prorratea porque una merma de proceso no es atribuible a un
fardo individual: los fardos se mezclan en la máquina.

---

## 5. Cambios al core

**Uno solo, aditivo:** `ContadorDocumento.TIPOS_DOCUMENTO += LOTE_TABACO`, igual que se hizo con
`ROMANEO_TABACO` en la Etapa 0.

Los dos términos de stock nuevos entran por `registrar_termino_stock`, que ya existe desde el
Plan 080 y **soporta varios términos**: `_TERMINOS_EXTRA` es una lista y sólo rechaza nombres
repetidos.

---

## 6. Pantallas

| Pantalla | Ruta |
|---|---|
| Listado de lotes + grilla HTMX con filtro de `condic` | `agro_lote_listado` |
| Alta de lote | `agro_lote_nuevo` |
| Detalle / armado: agregar y quitar fardos con Typeahead + Lupa | `agro_lote_detalle` |
| Armar / anular lote | `agro_lote_armar`, `agro_lote_anular` |
| Alta de acondicionamiento con costos y coproductos | `agro_acond_nuevo` |
| Cerrar / anular acondicionamiento | `agro_acond_cerrar`, `agro_acond_anular` |
| Asignar y quitar la venta del lote | `agro_lote_venta`, `agro_lote_venta_quitar` |
| **Reporte de margen** por lote y por fardo | `agro_margen` |
| ABM de procesos (pestaña de Configuración) | `agro_proceso_*` |

Todas con `.fInputAR` y `{{ valor|formato_ar }}`, Typeahead + Lupa en cada selector, y filtro de
`condic` en todo listado con importes.

---

## 7. Plan de pruebas

| Test | Qué verifica |
|---|---|
| `test_armar_lote_marca_los_fardos` | Los fardos pasan a `EN_LOTE` |
| `test_un_fardo_no_entra_a_dos_lotes` | Garantía del modelo |
| `test_fardo_de_romaneo_borrador_rechazado` | Sólo lo que existe físicamente |
| `test_fardo_de_otra_variedad_rechazado` | Un lote es de una variedad |
| `test_fardo_de_otra_sucursal_rechazado` | El stock es por sucursal |
| `test_totales_del_lote_se_reconstruyen` | Derivados, nunca por delta |
| `test_merma_baja_el_stock_de_la_variedad` | Término nuevo (−) |
| `test_coproducto_entra_a_su_producto` | Término nuevo (+) |
| `test_borrador_de_acondicionamiento_no_mueve_stock` | Sólo cuenta cerrado |
| `test_anular_acondicionamiento_devuelve_el_stock` | |
| `test_merma_extraordinaria_exige_motivo` | |
| `test_merma_dentro_de_lo_normal_no_es_extraordinaria` | |
| `test_no_se_puede_sacar_fardo_con_acondicionamiento_cerrado` | Rompería el prorrateo |
| `test_venta_calcula_importe_solo_del_producto_de_la_variedad` | Un flete en la misma factura no es ingreso de tabaco |
| `test_margen_por_lote` | |
| `test_margen_por_fardo_prorratea_por_kilos` | |
| `test_margen_por_fardo_usa_costo_exacto_de_compra` | No prorratea lo que ya es por fardo |
| `test_acondicionamiento_no_genera_asientos` | §2 — la regla más importante del plan |
| `test_conciliacion_contempla_mermas_y_coproductos` | La Etapa 4 sigue cerrando en cero |
| `test_desenchufe` | Sin la carpeta, el stock vuelve a los cuatro términos de siempre |

---

## 8. Criterio de Hecho

- [x] Modelos, migración y constraints — 5 tablas, 6 índices, 12 constraints.
- [x] Dos términos de stock nuevos, registrados con importación tolerante.
- [x] Servicios atómicos con `select_for_update()` y derivados reconstruidos enteros.
- [x] Pantallas HTMX + Tailwind, sin Django Admin, con Typeahead + Lupa y formato es-AR.
- [x] Reporte de margen por lote, por fardo y por clase, con filtro de `condic`.
- [x] Tests en verde — **77/77** (43 de servicio + 34 de pantalla).
- [x] Prueba de desenchufe: sin la carpeta, el stock vuelve **exactamente** a los cuatro términos
      de siempre, los tres extras en 0, y `recalcular_stock()` sigue funcionando.
- [x] `makemigrations --check` sin cambios pendientes.
- [x] `manage.py test verticalidades` → 611 tests, 3 errores, los tres preexistentes de
      distribución.
- [x] Suite completa: **954 tests, 13 errores** — lista **idéntica** al baseline, cero fallas
      nuevas y cero caídas de conexión (1.289 s, corriendo sola).
- [x] `docs/walkthrough.md` actualizado.

---

## 9. Lo que queda abierto

| Tema | Estado |
|---|---|
| Cargar los procesos reales de la planta | **Dato operativo**, no desarrollo. Es lo único que resta de DA-07 |
| Venta parcial de un lote | Limitación conocida: se arman dos lotes. `LoteAcopio.venta` es un FK simple a propósito |
| Valuación contable del stock | Fuera del alcance del ERP entero, no sólo de esta etapa (§2) |
