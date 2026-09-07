# Plan 085 — Agrícola Etapa 4: Stock del Tabaco

## Estado: ✅ Completado (2026-09-07)

**Fecha:** 2026-09-07
**Plan integral:** [`docs/agricola/plan inicial agricola.md`](../agricola/plan%20inicial%20agricola.md) — Etapa 4
**Requiere:** [080](080_terminos_enchufables_saldos_stock.md) ✅ · [081](081_agricola_etapa0_maestros_tabaco.md) ✅ · [082](082_agricola_etapa1_romaneo.md) ✅ · [083](083_agricola_etapa2_liquidacion.md) ✅ · [084](084_agricola_etapa3_pago.md) ✅

---

## Objetivo

Que los kilos recibidos entren al stock del ERP y salgan al venderse, usando el motor existente.

Consume el **último punto de extensión del Plan 080 que quedaba sin estrenar**:
`registrar_termino_stock`.

---

## 1. La decisión de granularidad: un producto por VARIEDAD

El stock se lleva por **variedad** (Tabaco Burley, Tabaco Virginia), en **kilos**. La clase vive
en el fardo, no en el producto.

**Por qué no un producto por clase.** Serían 75 productos, y —lo que importa de verdad— una
reclasificación tendría que mover stock de un producto a otro. Pero reclasificar **no cambia lo
que hay en el galpón**: son los mismos kilos, mejor descriptos. Un modelo que obligue a mover
stock para corregir una etiqueta está mal planteado.

`VariedadTabaco.producto` ya existe desde el Plan 081, nullable. Si una variedad no tiene producto
asignado, simplemente no mueve stock: el término no encuentra a qué producto imputar y el resto
del ERP sigue igual. Es degradación silenciosa y deliberada, pero se hace visible en la
conciliación (§4).

---

## 2. El término de stock

```python
{
    'nombre':     'agricola_tabaco_fardos',
    'modelo':     FardoTabaco,
    'signo':      1,                                  # los kilos ENTRAN
    'cantidad':   'kilos',
    'producto':   'romaneo__variedad__producto_id',
    'sucursal':   'romaneo__sucursal_id',
    'signo_cbte': None,
    'excluir':    Q(romaneo__estado__in=[BORRADOR, ANULADO]),
}
```

**Sólo entrada.** La salida ya la resuelve el término `ventas` que existe desde siempre: al vender
tabaco se factura el `Producto` de la variedad y `VentaItem` lo descuenta. No hace falta —ni
sería correcto— un segundo término de egreso.

**Cuándo entra:** al CONFIRMAR el romaneo. Un borrador todavía se está cargando y un romaneo
anulado no ocurrió. Los estados que cuentan son `CONFIRMADO` y `LIQUIDADO`: liquidar no mueve
mercadería, sólo la factura.

### Quién dispara el recálculo

`recalcular_stock()` corre por signals de `CompraItem`/`VentaItem`, que no aplican acá. Lo llaman
explícitamente `confirmar_romaneo()` y `anular_romaneo()`, que son los dos únicos momentos en que
un romaneo cruza el umbral de contar o no contar.

Agregar, editar o quitar fardos ocurre en BORRADOR, que no cuenta: no hay nada que recalcular.

---

## 3. Asignación del producto

Comando `manage.py crear_productos_tabaco --empresa <id>`, idempotente: crea un `Producto` por
variedad sin producto asignado, en kilos, y lo vincula. También se puede elegir uno existente
desde el ABM de variedades, que ya tiene el campo.

El producto se crea con `unidad_venta = 'KG'` y `alic_iva` tomada de la configuración del acopio,
para que al venderlo la alícuota salga bien sin cargarla otra vez.

---

## 4. Conciliación

Servicio y pantalla que comparan, por variedad y sucursal:

| Concepto | De dónde sale |
|---|---|
| Kilos recibidos | Σ `FardoTabaco.kilos` de romaneos vigentes |
| Kilos vendidos | Σ `VentaItem.cantidad` del producto de la variedad |
| Stock esperado | recibidos − vendidos + stock inicial |
| Stock del ERP | `StockSucursal.cantidad` |
| Diferencia | esperado − ERP |

La diferencia debe ser **cero**. Si no lo es, el reporte lo muestra y `recalcular_stock` lo
corrige, porque el stock es un valor derivado y autorreparable.

También señala las **variedades sin producto asignado**, que son la causa más probable de que los
kilos no aparezcan.

---

## 5. Tests mínimos

| Test | Qué verifica |
|---|---|
| `test_confirmar_romaneo_ingresa_los_kilos` | El stock sube por los kilos del romaneo |
| `test_un_borrador_no_mueve_stock` | Sólo cuenta al confirmar |
| `test_anular_romaneo_saca_los_kilos` | Y el stock vuelve al valor previo |
| `test_liquidar_no_mueve_stock` | Liquidar factura, no mueve mercadería |
| `test_reclasificar_no_mueve_stock` | Son los mismos kilos, mejor descriptos |
| `test_la_venta_descuenta_por_el_termino_de_siempre` | Sin término de egreso propio |
| `test_variedad_sin_producto_no_rompe` | Degrada en silencio y no afecta al resto |
| `test_stock_se_reconstruye_solo` | `recalcular_stock` es autorreparable |
| `test_recalculo_masivo_incluye_los_fardos` | `recalcular_stock_masivo` hereda el término |
| `test_no_regresion_de_compras_y_ventas` | Los cuatro términos de siempre dan idéntico |
| `test_conciliacion_en_cero` | Recibidos − vendidos = stock del ERP |
| `test_conciliacion_detecta_diferencia` | Y la muestra cuando la hay |
| `test_comando_crea_productos_idempotente` | Reejecutar no duplica |

---

## 6. Criterio de Hecho

- [x] Término de stock registrado con importación tolerante — **el tercer y último punto de
      extensión del Plan 080 queda en uso**.
- [x] Recálculo disparado al confirmar y al anular el romaneo.
- [x] Comando idempotente `crear_productos_tabaco`, con `--dry-run` y respeto de `verbosity`.
- [x] Pantalla de conciliación con formato es-AR y botón de recálculo.
- [x] Tests en verde — **26/26**.
- [x] Prueba de desenchufe: el stock **vuelve exactamente a los cuatro términos de siempre**
      (`compras`, `recepciones`, `ventas`, `remitos_internos`), los tres registros en 0 y
      `recalcular_stock()` sigue funcionando.
- [x] `makemigrations --check` sin cambios pendientes. **Esta etapa no crea ni altera tablas.**
- [x] `docs/walkthrough.md` actualizado.

### Los tres puntos de extensión del Plan 080, todos en uso

| Punto | Consumido en |
|---|---|
| `registrar_termino_ctacte` | Plan 083 — la deuda de la liquidación |
| `registrar_aplicacion_op` | Plan 084 — la imputación del pago |
| `registrar_termino_stock` | **Plan 085 — esta etapa** |

El Plan 080 se diseñó al principio de todo, antes de que existiera un solo modelo de tabaco.
Cierra sin haber necesitado un cambio.

### Sin migraciones

La etapa no agrega tablas ni campos: `VariedadTabaco.producto` ya existía desde el Plan 081,
previsto justamente para esto. Todo lo demás es servicio, registro y pantalla.
