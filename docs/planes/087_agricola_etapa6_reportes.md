# Plan 087 — Agrícola Etapa 6: Reportes oficiales y gerenciales

## Estado: ✅ Completado (2026-09-07)

**Fecha:** 2026-09-07
**Plan integral:** [`docs/agricola/plan inicial agricola.md`](../agricola/plan%20inicial%20agricola.md) — Etapa 6
**Requiere:** [081](081_agricola_etapa0_maestros_tabaco.md) ✅ · [082](082_agricola_etapa1_romaneo.md) ✅ · [083](083_agricola_etapa2_liquidacion.md) ✅ · [084](084_agricola_etapa3_pago.md) ✅ · [085](085_agricola_etapa4_stock.md) ✅ · [086](086_agricola_etapa5_lotes_acondicionamiento_venta.md) ✅

---

## Objetivo

Lo que el acopio tiene que **entregar hacia afuera** —FET, Secretaría de la Producción, organismos
recaudadores— y lo que el dueño necesita para **decidir**: márgenes por campaña, por productor y
por clase.

---

## 1. Esta etapa no crea una sola tabla

Todo sale de lo que ya está registrado en las Etapas 0 a 5. No hay modelos, no hay migraciones y
no hay estado nuevo que mantener sincronizado.

Es la prueba de que el modelo de las etapas anteriores estaba bien planteado: si para emitir la
planilla FET hubiera que agregar campos, sería señal de que algo no se estaba capturando cuando
correspondía. **No hace falta ninguno.**

---

## 2. Los cinco reportes

### 2.1 Planilla FET — el reformateo del `Informe_fet` del VFP

Reproduce las columnas exactas de la exportación Excel del sistema heredado:

```
id_romaneo · asiento · letra · punto · número · fecha · cod.FET · productor · variedad ·
fardos · kilos · importe · adicional · IVA · Ret.IVA · Ret.Gcias · EEAOC · Sal.Púb ·
Uso Agua · a pagar · ponderante
```

#### Dos decisiones que el VFP no tuvo que tomar

**Granularidad: una fila por ROMANEO.** La columna encabezada es `id_romaneo`, así que la unidad
de la planilla es el romaneo. En el VFP eso era trivial porque un romaneo era una liquidación —el
sistema hacía todo en un solo acto—. En Ikigai **una liquidación puede agrupar varios romaneos**,
y las retenciones se calculan sobre el comprobante entero.

Solución: la fila lleva los datos del comprobante y las retenciones **prorrateadas por la
participación del romaneo en el neto de la liquidación**. Se prorratea porque el dato existe a
nivel comprobante y no a nivel romaneo; y la suma de las filas reconstruye exactamente el total de
la liquidación. Hay un test que lo verifica.

**`Ret.Gcias` sale del PAGO, no de la liquidación.** Por la decisión DA-01, Ganancias se practica
al pagar y su base es el acumulado mensual. Una liquidación todavía no pagada tiene **Ganancias en
cero**, y eso es lo correcto: todavía no se retuvo nada.

La columna se llena con los certificados `RetencionPago` vigentes de las Órdenes de Pago que
cancelaron esa liquidación, prorrateados por lo imputado a ella. Poner ahí una estimación sería
declarar ante el FET una retención que no se practicó.

**`a pagar`** = `importe + IVA − (Ret.IVA + Ret.Gcias + EEAOC + Salud + Agua)`.

**El `adicional` es informativo y NO entra en `a pagar`.** Al armar este reporte se verificó que
`LiquidacionDetalle.importe` es `Sum(fardo.importe)` y que `liq.neto` se arma de ahí: **hoy el
circuito no le paga el adicional al productor**. Se muestra la columna porque la planilla heredada
la traía, pero incluirla en `a pagar` haría que la planilla declarara un importe que el
comprobante no dice. Es consecuencia directa de que **DA-05 sigue abierta**.

> Efecto colateral detectado y corregido: la Etapa 5 sumaba el adicional a `LoteAcopio.costo_compra`.
> Ahora no —el costo del lote dice lo mismo que la liquidación— y el adicional se expone aparte en
> la property `LoteAcopio.adicional_informado`. Cuando se cierre DA-05 hay que tocar **los dos**
> lugares juntos: `services/liquidacion.py::preparar_liquidacion` y `services/lotes.py::recalcular_lote`.

**Las columnas de retención no están cableadas.** Los cinco conceptos del cliente se resuelven por
el **código** del maestro `TipoRetencionTabaco`; los que no estén cargados salen en cero, y los
que el cliente agregue aparecen en una columna `Otras retenciones` para que la fila siga sumando.
El maestro es extensible por decisión del plan integral: la planilla no puede dejar de serlo.

### 2.2 Resumen de acopio por variedad y clase

Fardos, kilos, importe y precio promedio ponderado, agrupado por variedad y clase, con subtotales
por variedad. Es lo que piden los organismos como resumen de campaña.

### 2.3 DDJJ de existencias por galpón — **a una fecha**

No es el stock de hoy: es la existencia **a la fecha de la declaración**, reconstruida desde los
comprobantes:

```
existencia(variedad, sucursal, fecha) = Σ fardos de romaneos vigentes con fecha ≤ F
                                      − Σ kilos_baja de acondicionamientos cerrados con fecha ≤ F
                                      − Σ kilos vendidos con fecha ≤ F
```

Se reconstruye y no se lee de `StockSucursal` porque **`StockSucursal` sólo sabe el presente**.
Una DDJJ que se presenta en octubre por las existencias al 30 de septiembre necesita el pasado, y
el pasado está en los comprobantes: es exactamente el mismo criterio con el que el ERP deriva el
stock, sólo que con un corte de fecha.

### 2.4 Libro de retenciones practicadas

Unifica los dos orígenes en una sola vista cronológica:

| Origen | Modelo | Momento |
|---|---|---|
| Retenidas al liquidar | `LiquidacionRetencion` | EEAOC, IVA, Salud Pública, Uso de Agua |
| Retenidas al pagar | `RetencionPago` | Ganancias |

Columnas: fecha · comprobante · productor · CUIT · concepto · organismo · régimen · base ·
alícuota · importe · certificado. Con **totales por organismo**, que es lo que se necesita para
conciliar contra la cuenta de pasivo antes de depositar.

Sólo entran las retenciones de comprobantes **vigentes**: una liquidación anulada o un certificado
anulado no se declaran.

### 2.5 Tableros de margen

Tres agregaciones sobre lo que la Etapa 5 ya calcula: por **campaña**, por **productor** y por
**clase de tabaco**. La lectura que importa es la última: dice qué clases dejaron plata y cuáles
se pagaron de más.

---

## 3. Reglas transversales

**Filtro de `condic` en todos.** Es regla del proyecto para cualquier listado con importes, y acá
tiene además un sentido fiscal: la planilla FET y el libro de retenciones son **declaraciones**, y
lo que se declara es `condic in (1, 3)` —la lente fiscal—. El filtro arranca en **Real** por
defecto en los dos reportes oficiales; en los gerenciales, en Todas.

**Exportación.** CSV con `;` y BOM UTF-8, que es la convención ya establecida en
`contable/views_reportes.py`, más XLSX con `openpyxl` para la planilla FET, porque el VFP entregaba
Excel y el organismo lo espera así.

**Formato es-AR** en pantalla vía `|formato_ar`. En el CSV y el XLSX van números crudos: un
`1.234,56` dentro de un CSV con separador `;` es ambiguo, y en XLSX el formato lo pone la celda.

---

## 4. Archivos

| Archivo | Qué |
|---|---|
| `services/reportes.py` | Planilla FET, resumen de acopio, existencias a fecha |
| `services/retenciones_libro.py` | Libro de retenciones practicadas |
| `services/tableros.py` | Margen por campaña, productor y clase |
| `services/exportaciones.py` | CSV y XLSX |
| `views_reportes.py` · `forms_reportes.py` | Pantallas |
| `templates/agricola/reportes/*` | 9 plantillas |

---

## 5. Plan de pruebas

| Test | Qué verifica |
|---|---|
| `test_planilla_fet_una_fila_por_romaneo` | Granularidad |
| `test_las_retenciones_se_prorratean_entre_romaneos` | Y la suma reconstruye el total |
| `test_ganancias_es_cero_si_no_se_pago` | DA-01: se retiene al pagar |
| `test_ganancias_aparece_despues_del_pago` | |
| `test_a_pagar_cierra_contra_la_liquidacion` | La aritmética de la fila |
| `test_una_retencion_nueva_del_maestro_no_rompe_la_planilla` | Va a «Otras» |
| `test_la_planilla_excluye_anuladas` | |
| `test_la_planilla_filtra_por_condic` | |
| `test_resumen_por_variedad_y_clase` | |
| `test_precio_promedio_es_ponderado_por_kilos` | No promedio de promedios |
| `test_existencias_a_una_fecha_pasada` | Ignora lo posterior al corte |
| `test_existencias_descuentan_mermas_y_ventas` | |
| `test_libro_une_los_dos_origenes` | Liquidación + pago |
| `test_libro_excluye_certificados_anulados` | |
| `test_totales_por_organismo` | |
| `test_tablero_por_campania_y_productor` | |
| `test_export_csv_tiene_bom_y_punto_y_coma` | Convención del proyecto |
| `test_export_xlsx_responde` | |
| Humo de las 5 pantallas + filtro de `condic` | |

---

## 6. Criterio de Hecho

- [x] Los cinco reportes, **sin una tabla nueva**. Hay un test que lo fija enumerando las 19
      tablas de las etapas 0 a 5.
- [x] Filtro de `condic` en todos; los oficiales arrancan en Real.
- [x] Exportación CSV (`;` + BOM) y XLSX con formato numérico en la celda.
- [x] Tests en verde — **61/61** (34 de servicio + 27 de pantalla).
- [x] `makemigrations --check` → `No changes detected`. **La etapa no genera ninguna migración.**
- [x] Prueba de desenchufe: sin la carpeta, `check` pasa, el stock vuelve a los cuatro términos de
      siempre, los tres registros quedan en cero y las URLs `agro_` dejan de resolver.
- [x] `docs/walkthrough.md` actualizado.

---

## 7. Dos hallazgos del desarrollo

### 7.1 El adicional no se paga — y la Etapa 5 lo estaba costeando

Al armar la planilla se verificó que `LiquidacionDetalle.importe` es `Sum(fardo.importe)` y que
`liq.neto` se arma de ahí: **el adicional se captura pero no se liquida**. Es consecuencia directa
de que DA-05 sigue abierta.

La Etapa 5 lo sumaba a `LoteAcopio.costo_compra`: el costo del lote decía una cosa y la liquidación
otra, y el margen salía subestimado contra plata que nunca salió. Corregido; el adicional se
expone aparte en `LoteAcopio.adicional_informado`.

### 7.2 Los códigos de retención no se pueden cablear

La primera versión mapeaba las columnas de la planilla por código exacto (`IVA`, `GANANCIAS`,
`AGUA`). El cliente cargó los suyos como **`RET-IVA`, `RET-GCIAS` y `USO AGUA`**: tres de las cinco
caían en «otras» y —esto es lo grave— **nada fallaba a la vista**, porque la fila seguía sumando
bien. La planilla mentía en silencio.

**El error de fondo no fue el mapa: fue que el mapa era implícito.** Se le pidió al usuario que
cargara los conceptos sin decirle qué códigos usar, y después se escribió un reporte que asumía
códigos. La corrección no es adivinar mejor ni cambiarle los datos: es hacer el mapeo **explícito
y visible**.

`TipoRetencionTabaco.columna_fet` declara a qué columna aporta cada concepto. Se ve en la pestaña
de Configuración, se edita desde el ABM y un concepto nuevo se asigna a propósito. La migración de
datos `0007_sembrar_columna_fet` lo dejó cargado de una vez para los conceptos existentes, así que
**el usuario no tuvo que tocar nada**: los cinco quedaron mapeados con sus códigos reales.

La deducción por `tipo_base` + palabra clave sobrevive como **red**, no como camino principal:
cubre lo que entre por una importación sin pasar por el ABM.

> Costo consciente: esta corrección rompe la propiedad «la Etapa 6 no genera migraciones». Se
> aceptó porque la alternativa era dejar una declaración legal apoyada en una heurística.

---

## 8. Decisiones que el usuario cerró después de la primera entrega

| Tema | Resolución |
|---|---|
| **Adicional** *(DA-05)* | **Comodín en cero, no se usa.** La pantalla de carga de fardos **ya no lo dibuja**; el campo sobrevive en el modelo y el servicio. No integra el neto, ni el costo del lote, ni «a pagar» |
| **`condic` de las liquidaciones** | **Siempre 1 (Real/Fiscal).** El alta de romaneo ya no ofrece el combo: era una trampa, porque un Presupuestado desaparecería en silencio de la planilla FET. El campo sigue en el modelo, lo hereda el asiento y los listados conservan el filtro |
| **Ret. Ganancias del pago** | Confirmado |
| **DDJJ reconstruida desde comprobantes** | Confirmado |
| **CSV sin separador de miles** | Confirmado |
