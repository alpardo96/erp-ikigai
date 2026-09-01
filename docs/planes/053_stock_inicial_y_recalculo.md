# Plan 053 — `stock_inicial` en `StockSucursal` y recálculo del stock disponible

- **Fecha:** 16/08/2026
- **Módulo:** Productos → stock · Facturación (señales de los circuitos que mueven stock)
- **Origen:** pedido del usuario tras detectar que el stock es un contador incremental sin punto
  de partida, a diferencia de la cuenta corriente, que sí se recalcula desde `saldo_inicial`
- **Estado:** **EJECUTADO (16/08/2026)** — fases 1 a 4 completas.
  `productos.tests.test_stock_inicial`: **20/20 OK**.
  Migraciones aplicadas: 13.596 filas de stock inicializadas, **0 cantidades modificadas**.
  Verificación en la base real: `recalcular_stock` reproduce el stock de las 3 empresas sin una
  sola diferencia.

---

## 1. Objetivo

Que el stock disponible de una sucursal **se derive** de un punto de partida más los movimientos,
y no de un contador que se va empujando a ciegas:

```
stock_disponible = stock_inicial
                 + compras            (facturas que mueven stock ellas mismas)
                 + recepciones        (mercadería del proveedor con remito)
                 + recepciones internas (la pata de entrada del remito interno)
                 − ventas
                 − remitos internos   (la pata de salida, en la sucursal de origen)
```

`stock_inicial` es la existencia al momento de instalar el sistema en el cliente.

---

## 2. Por qué — el problema real

Hoy el stock y la cuenta corriente usan **dos modelos distintos**, y solo uno es reconstruible:

| | Campo inicial | Cómo se mantiene | ¿Se puede reconstruir? |
|---|---|---|---|
| `ClienteProveedor.saldo` | **`saldo_inicial`** | `recalcular_saldo_cliente_proveedor()` recalcula **todo** desde el inicial | **Sí** |
| `StockSucursal.cantidad` | **no existe** | `aplicar_movimiento_stock()` y compañía suman/restan un delta | **No** |

Las tres funciones de `productos/services/stock_service.py` operan por delta contra
`_original_cantidad` y escriben `stock_record.cantidad = stock_record.cantidad ± delta`. No hay
ninguna función que reconstruya el stock, y `MovimientoStock` es un registro histórico del que el
contador **no se deriva**.

Consecuencia práctica: si una señal no corre —un borrado masivo, una importación, un proceso que
las desactiva, un error a mitad de camino— el stock queda mal **y no hay desde dónde recomponerlo**.
Es exactamente lo que pasó en la limpieza de la empresa 1: se borraron 23 ítems de venta y 5 de
compra con las señales apagadas y el stock no se devolvió. Ahí no tuvo consecuencias porque la
empresa 1 tenía todo en cero, pero con stock real habría quedado una diferencia de 14 productos y
−15 unidades **imposible de detectar y de corregir**.

Con este plan, ese mismo escenario se arregla corriendo el recálculo.

---

## 3. Diseño

### 3.1 Derivado, no incremental

`StockSucursal.cantidad` **sigue siendo un campo materializado** —se lee en el buscador de
productos, en el remito interno y en toda la operatoria, y recalcular al vuelo sería caro—, pero
deja de actualizarse por delta: pasa a **recalcularse completo para ese (producto, sucursal)** cada
vez que algo lo afecta. Es el mismo patrón de `recalcular_saldo_cliente_proveedor()`.

El costo es acotado: el recálculo se acota a un producto y una sucursal, sobre FK indexadas.
No se recalcula todo el inventario en cada guardado.

### 3.2 La fórmula, con todas sus exclusiones

Relevadas del código actual, que ya las contempla en las guardas de `aplicar_movimiento_stock`:

| Término | Modelo | Sucursal | Se EXCLUYE cuando |
|---|---|---|---|
| **+ compras** | `CompraItem` | `compra.sucursal` | `compra.id_fac_rem` (ya lo movió el remito) · `compra.gestion_stock_por_recepcion` (circuito OC: lo mueve la recepción) |
| **+ recepciones** | `RecepcionItem` (`cantidad_recibida`) | `recepcion.sucursal` | `recepcion.estado = 1` (anulada) |
| **− ventas** | `VentaItem` | `venta.sucursal` | `venta.estado = 1` (anulada) · `venta.id_fac_rem` |
| **− remitos internos** | `RemitoInternoItem` (`cantidad_enviada`) | `remito.sucursal_origen` | `remito.estado = 3` (anulado) |

> Las recepciones de proveedor y las internas son **el mismo término**: las dos son
> `RecepcionItem`, y se distinguen por `Recepcion.origen`. No hacen falta dos sumandos.

**Notas de crédito.** Ventas y compras llevan el signo de su comprobante
(`TipoComprobante.signo = −1` en las NC), así que cada término se pondera por
`tipo.signo`: una NC de venta **devuelve** stock y una NC de compra lo **saca**. Hoy esto ya está
resuelto con `comp_signo` y hay que conservarlo idéntico.

### 3.3 Modelo

```python
class StockSucursal(AuditModel):
    producto = models.ForeignKey(Producto, ...)
    sucursal = models.ForeignKey(Sucursal, ...)

    # Existencia al momento de instalar el sistema en el cliente. Es el punto de partida del
    # stock: todo lo posterior son movimientos que se suman o restan sobre él.
    # Se carga una vez y NO lo tocan los circuitos operativos.
    stock_inicial = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                        verbose_name="Stock Inicial")

    # Stock disponible. Es un valor DERIVADO y materializado: lo recalcula
    # `recalcular_stock()` a partir de `stock_inicial` más los movimientos. No se ajusta por
    # delta: si algo lo deja mal, se corrige volviendo a recalcular.
    cantidad = models.DecimalField(max_digits=15, decimal_places=2, default=0)
```

### 3.4 Servicio

En `productos/services/stock_service.py`:

```python
def recalcular_stock(producto_id, sucursal_id) -> Decimal:
    """Stock disponible = stock_inicial + compras + recepciones − ventas − remitos internos."""
```

Cuatro agregados acotados por `producto` y `sucursal`, con sus exclusiones. Guarda el resultado en
`cantidad` y lo devuelve. Con `select_for_update()`, como hoy.

**Los términos se declaran como una lista, no cableados en el cuerpo de la función.** Cada entrada
dice qué modelo agrega, con qué signo, por qué campo de cantidad, cómo llega a la sucursal y qué
excluye. Es lo que va a permitir sumar el término de **ajustes de inventario** (§8 bis) agregando
una entrada, sin reescribir la función ni volver a validar los cuatro términos existentes.

Las tres funciones actuales (`aplicar_movimiento_stock`, `aplicar_movimiento_recepcion`,
`aplicar_movimiento_remito_interno`) **conservan su firma y sus señales**: dejan de hacer la
aritmética de delta y pasan a (a) registrar el `MovimientoStock` de auditoría —que se mantiene tal
cual— y (b) llamar a `recalcular_stock()`. Así ningún llamador cambia.

Se agrega además un comando de mantenimiento:

```bash
python manage.py recalcular_stock --empresa 2 [--sucursal N] [--producto N]
```

para reconstruir el inventario completo cuando haga falta. Es la red de seguridad que hoy no existe.

---

## 4. Migraciones

### 4.1 Esquema
`AddField StockSucursal.stock_inicial` (`decimal(15,2)`, default 0).

### 4.2 Backfill — **preserva el stock actual**

No se puede poner `stock_inicial = 0` porque el stock quedaría en la suma de los movimientos y
**se perdería la existencia importada**. Tampoco `stock_inicial = cantidad`, porque los
movimientos ya registrados se contarían dos veces.

La migración calcula, por cada fila:

```
stock_inicial = cantidad_actual − (compras + recepciones − ventas − remitos internos)
```

Así el primer recálculo reproduce **exactamente** la `cantidad` que hay hoy: el cambio es
invisible en los números y a partir de ahí el stock queda reconstruible.

La migración informa por consola cuántas filas quedaron con `stock_inicial` distinto de la
`cantidad` (es decir, cuántas tenían movimientos aplicados).

---

## 5. Eliminación de `Producto.stock` y `Producto.stkcons`

**Decisión del usuario (16/08/2026): se eliminan.** Son campos heredados del ERP en VFP, donde el
stock se actualizaba sobre el producto. La estrategia cambió: hoy el stock se lleva por sucursal y
se calcula. Ya no cumplen ninguna función.

### 5.1 Relevamiento de usos — el borrado es limpio

| Uso | Resultado |
|---|---|
| **Escrituras** en `productos/` y `facturacion/` | **ninguna** fuera de migraciones |
| **Templates** | **ninguno**. `producto_list.html` usa `stock_global`; el buscador usa `stock_origen`/`stock_destino`, todos calculados |
| **Forms / admin / vistas de productos** | **ninguno**. El admin usa `stock_global` |
| **Lecturas** | **una sola**: `exportar_ventas_producto_csv` (§5.2) |
| **Escritura del importador VFP** | `productos/management/commands/migrar_productos.py:332,371` |

El consolidado ya está resuelto: `Producto.stock_global` es una property que suma
`StockSucursal.cantidad` de todas las sucursales. **No hace falta materializar nada** — era la
alternativa que se había propuesto y queda descartada.

### 5.2 El único consumidor: el CSV legacy de 74 columnas

`facturacion/views_reportes.py` → `exportar_ventas_producto_csv` reproduce el archivo de 74
columnas del sistema VFP, y dos de ellas salen de estos campos:

- columna `stock` ← `float(prod.stock)` — hoy emite el **valor congelado de la importación**
- columna `stkcons` ← `float(prod.stkcons)` — ídem

**Se conservan las 74 columnas** para no romper a quien consuma el archivo, y cambia lo que las
llena:

- **`stock`** → el stock **real**, tomado de `StockSucursal`. Además de destrabar la eliminación,
  **corrige el reporte**: hoy exporta un número viejo.
- **`stkcons`** → `0.0`. Era el stock en consignación del VFP y no tiene equivalente en el esquema
  actual. La columna queda como relleno posicional.

> **Cuidado con el N+1.** `prod.stock_global` dispara una consulta por producto, y este export
> recorre todos los ítems de venta del período. Hay que precargar el stock en **un** query y
> resolverlo en memoria, con el mismo patrón que el Plan 051 usó para el modal de productos:
> un dict `(producto_id, sucursal_id) -> cantidad`. Como el CSV ya trae la columna `suc` por fila,
> conviene informar el stock **de la sucursal de la venta**, más útil que el global.

### 5.3 Cambios

1. `facturacion/views_reportes.py` — reemplazar las dos celdas y precargar el stock (§5.2).
2. `productos/management/commands/migrar_productos.py` — dejar de escribir `stkcons` y `stock`.
3. Migración `RemoveField` de `Producto.stock` y `Producto.stkcons`.

Va **después** del recálculo (§3 y §4): primero el stock nuevo funciona y está probado, recién
después se quitan los campos viejos. Así el reporte nunca queda sin fuente de datos.

---

## 6. Plan de pruebas

`productos/tests/test_stock_inicial.py` (nuevo):

| # | Caso | Verifica |
|---|------|----------|
| 1 | Solo `stock_inicial`, sin movimientos | `cantidad == stock_inicial` |
| 2 | Compra que mueve stock | suma |
| 3 | Compra con `gestion_stock_por_recepcion` | **no** suma (lo hace la recepción) |
| 4 | Compra con `id_fac_rem` | **no** suma |
| 5 | Recepción de proveedor | suma |
| 6 | Recepción anulada (`estado=1`) | no suma |
| 7 | Venta | resta |
| 8 | Venta anulada (`estado=1`) | no resta |
| 9 | Venta con `id_fac_rem` | no resta |
| 10 | **NC de venta** (`tipo.signo = −1`) | **devuelve** stock |
| 11 | **NC de compra** | saca stock |
| 12 | Remito interno | resta en origen, no toca destino |
| 13 | Remito interno + su recepción | origen −N, destino +N; el total no cambia |
| 14 | Remito interno anulado (`estado=3`) | no resta |
| 15 | **Borrar un ítem** | el stock vuelve a su valor previo |
| 16 | **Recálculo es idempotente** | correrlo dos veces da lo mismo |
| 17 | **Autorreparación** | tras romper `cantidad` a mano, el recálculo la corrige |
| 18 | Aislamiento por sucursal | un movimiento en una sucursal no afecta a la otra |

El caso 17 es el que da sentido a todo el plan: hoy es imposible.

**Regresión obligatoria:** `productos`, `facturacion` y `tesoreria` completos, más una
comparación antes/después de las 13.596 filas de `StockSucursal` para confirmar que **ninguna
cantidad cambió** con la migración.

---

## 7. Riesgos

| Riesgo | Mitigación |
|--------|------------|
| El backfill altera stocks reales de la empresa 2 | Se calcula el inicial "hacia atrás" para que la cantidad no se mueva, y se compara fila por fila antes/después |
| Perder una exclusión al pasar de delta a recálculo (`id_fac_rem`, OC, anulados, signo de NC) | Cada exclusión tiene su test (casos 3, 4, 6, 8, 9, 10, 11, 14) |
| Performance en guardados masivos | El recálculo se acota a (producto, sucursal). Si algún proceso masivo lo sufre, se agrega un modo diferido |
| Doble conteo entre recepción interna y remito interno | Caso 13: son las dos patas de la misma transferencia y el total debe quedar igual |

---

## 8. Decisiones

1. **`Producto.stock` y `Producto.stkcons`** → **se eliminan** (§5). Resuelto por el usuario el
   16/08/2026: son campos heredados del VFP, donde el stock se actualizaba sobre el producto. Hoy
   se lleva por sucursal y se calcula.

2. **`stock_inicial` va en `StockSucursal`, no en `Producto`** — cada sucursal tiene el suyo. Se
   carga **en la migración desde el sistema anterior**, al instalar. No se hace pantalla ahora.

---

## 8 bis. PENDIENTE registrado: formulario de inventarios

El usuario dejó asentado que más adelante hará falta un **formulario de carga de inventarios**,
tanto **generales** (toma física completa) como **periódicos**, al estilo del "arreglo de stock".
Se hará en un plan aparte.

### Por qué conviene tenerlo en cuenta desde ahora

Un ajuste de inventario **no encaja en ninguno de los cinco términos** de la fórmula de §3.2: no
es una compra, ni una recepción, ni una venta, ni un remito. Es una corrección contra la realidad
física. Cuando llegue va a necesitar su propio término:

```
stock = stock_inicial + compras + recepciones − ventas − remitos internos  ± AJUSTES
```

Eso **no cambia nada de este plan**, pero sí condiciona cómo se escribe `recalcular_stock()`:
la función se arma con los términos como una **lista de sumandos declarativa**, de modo que sumar
el de ajustes sea agregar una entrada y no reescribir la función. Es gratis hacerlo así ahora y
caro hacerlo después.

Dos decisiones quedan para ese plan, no para éste:

- Si el ajuste se modela como un comprobante propio (`AjusteStock` cabecera + ítems, con su
  asiento contable por diferencia de inventario) o como filas sueltas.
- Si al cerrar un inventario general se **recarga `stock_inicial`** —cortando el histórico— o se
  registra la diferencia como un ajuste más, conservándolo. Contablemente lo segundo es más sano;
  operativamente lo primero es más simple.

---

## 9. Orden de ejecución

| Fase | Contenido |
|---|---|
| 1 | `stock_inicial` + `recalcular_stock()` + migración de backfill que preserva las cantidades |
| 2 | Reescritura de las tres funciones de `stock_service.py` para que recalculen en vez de acumular |
| 3 | Comando `recalcular_stock` y batería de tests (§6) |
| 4 | Corrección del CSV legacy (§5.2) y baja de `stock` / `stkcons` |

La fase 4 va última **a propósito**: hasta que el stock calculado no esté probado, el reporte
sigue teniendo de dónde leer.
