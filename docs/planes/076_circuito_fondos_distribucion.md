# Plan 076 — Circuito de fondos de Distribución y saldo real de la factura

**Estado:** ✅ **IMPLEMENTADO** (31/08/2026) · **Depende de:** [Plan 074](074_modulo_distribucion.md) fases 1 a 7
**Alcance:** A, B y C son de Distribución. **D afecta a todo el ERP.**

---

## 0. Por qué existe este plan

Al cerrar la fase 7 el usuario hizo dos observaciones que corrigen el diseño implementado:

1. **Falta un nivel en el circuito del dinero.** Las rendiciones de repartos y vendedores no van
   directo a Tesorería: pasan por una **Tesorería de Reparto intermedia**, que se comporta como la
   caja mostrador de armería —acumula, y después rinde por retiro/cierre a Caja Tesorería—.
2. **La Nota de Crédito debe descontar el saldo de la factura que le dio origen**, y quedar ella
   misma en cero por haberse aplicado totalmente.

A eso se suman dos requerimientos nuevos que surgieron de la misma conversación:

3. Una hoja de ruta puede incluir **clientes que no hicieron pedido**, sólo para cobrarles el saldo.
4. Los **vendedores** también rinden a la caja intermedia, en su condición de vendedores.

Y una **regresión que introdujo la fase 7**, detectada al analizar el punto 1 (§B.2).

---

## A — Parada de sólo cobranza

### A.1 El problema

`RepartoParada` nació como *"un comprobante para entregar en un domicilio"*: `pedido` y `venta` son
obligatorios, y `cliente` y `domicilio_entrega` son **properties** derivadas de ellos. Un cliente al
que sólo se va a cobrar no tiene ni pedido ni comprobante, así que hoy no puede entrar en una hoja
de ruta.

### A.2 El diseño

| Campo | Cambio | Por qué |
|-------|--------|---------|
| `tipo` | **NUEVO** — `ENTREGA = 0` / `COBRANZA = 1` | Explícito. Inferirlo de `venta is None` obliga a recordar la convención en cada lectura |
| `pedido`, `venta` | pasan a **nullable** | La parada de cobranza no tiene ninguno de los dos |
| `cliente` | **NUEVO** — FK obligatoria | Hoy es una *property* que sale de `venta.cliente`. Sin comprobante no hay de dónde sacarla |
| `domicilio_texto` | **NUEVO** — congelado | Ídem: hoy sale de `pedido.domicilio_entrega_texto` |

**Restricciones de base** (las reglas matemáticas van a la base, no al código):

```python
CheckConstraint(
    condition=(Q(tipo=0, venta__isnull=False) | Q(tipo=1, venta__isnull=True)),
    name='parada_entrega_con_comprobante')
UniqueConstraint(fields=['venta'], condition=Q(venta__isnull=False),
                 name='uniq_parada_venta')
```

El `UniqueConstraint` se condiciona porque ahora hay nulos. PostgreSQL ya admite varios NULL en un
índice único, pero la condición deja la regla **escrita** en vez de depender de un detalle del motor.

### A.3 El cobro mínimo de una parada de cobranza es CERO

Es la corrección más importante de este plan, y va contra lo que se había asumido primero.

> **El cobro mínimo existe porque hay mercadería de por medio: es la condición para dejarla.**
> En una parada de cobranza no se entrega nada, así que **no hay palanca**. El repartidor pide y se
> lleva lo que el cliente quiera darle, que la mayoría de las veces es nada o una parte.

Definición del usuario: *"Cliente que no hizo pedido es más que probable que no esté entre sus
prioridades el pagarnos. Seguramente el pago final lo terminará haciendo el vendedor que le hará la
'guardia' cuando el cliente esté esquivando el pago."*

En consecuencia:

- `cobro_minimo = 0`. Lo que se congela e imprime es el **saldo pendiente**, como dato para ir a
  reclamar, **no como obligación**.
- Lo que traiga se imputa con el **procedimiento estándar**: FIFO de lo más antiguo, con el efectivo
  priorizando los `condic = 2`. Sin caso especial: es exactamente lo que ya hace `registrar()`.
- El cuadro de la rendición queda coherente: `esperado = Σ cobro_minimo`, así que estas paradas
  aportan cero. **No se puede esperar lo que no se tiene con qué exigir.**

### A.4 Impacto en el resto del módulo

| Función | Cambio |
|---------|--------|
| `agregar_parada_de_cobranza()` | **NUEVA.** Suma un cliente con saldo, sin comprobante |
| `cerrar_reparto()` | Lee `parada.cliente` (campo) en vez de `parada.venta.cliente`. En las de cobranza congela el saldo y deja `cobro_minimo = 0` |
| `hoja_de_ruta()` | Ordena por `cliente__razon_social` directo. La parada de cobranza se imprime sin comprobante y con su saldo |
| `consolidado()` | Sin cambios: las paradas sin comprobante no aportan artículos. **Un reparto todo de cobranza da consolidado vacío**, que es lo correcto |
| Entrega y devoluciones | Sólo aplican a paradas de ENTREGA. La pantalla no ofrece «entregada / no entregada» en una de cobranza |

**El "reparto especial" no es un tipo aparte:** es el caso en que todas sus paradas son de cobranza.
Un solo mecanismo cubre los dos escenarios que planteó el usuario.

### A.5 Migración de datos

Poblar `cliente` y `domicilio_texto` en las paradas existentes desde `venta.cliente` y
`pedido.domicilio_entrega_texto`, y `tipo = ENTREGA` en todas. Sin pérdida: son los mismos valores
que hoy devuelven las properties.

---

## B — Tesorería de Reparto (`Caja.tipo = 'D'`)

### B.1 Los tres niveles

```
cobranzas ─► CAJA RECAUDADORA 'R'        una sesión por reparto (y por vendedor, §C)
                    │
                    │  rendición en 2 pasos: el repartidor declara → el administrativo cuenta
                    ▼
             TESORERÍA DE REPARTO 'D'    UNA POR SUCURSAL. Acumula todas las rendiciones
                    │
                    │  retiro / cierre de caja (circuito existente, sin código nuevo)
                    ▼
             CAJA TESORERÍA 'T'
```

La fase 7 saltea el nivel del medio y manda el reparto directo a Tesorería.

**Por qué el intermedio.** Quien recibe a los repartidores no es el tesorero central: es un
administrativo que cuenta lo que cada uno trae, lo retiene, y después entrega el consolidado. Su
cierre es un arqueo propio. Es exactamente la razón por la que existe la caja mostrador de armería.

**Y los dos pasos ya estaban descritos, mal ubicados.** El Plan 074 §7.9 pedía que el repartidor
declarara y otro contara y aceptara. Ésos son los dos pasos **de este tramo**, no del que va a
Tesorería. El tramo de la intermedia a Tesorería es el retiro/cierre que ya existe.

### B.2 La regresión que introdujo la fase 7

`caja_recaudadora()` crea una caja `tipo='R'` en la misma sucursal donde vive la mostrador. Cinco
lugares de Tesorería buscan «la caja de la sucursal» **sin filtrar por tipo**:

```python
Caja.objects.filter(empresa_id=..., sucursal_id=..., activa=True).first()
```

`tesoreria/views.py:79` y `tesoreria/views_htmx.py` líneas 923, 1328, 1354, 1477 y 1498 — el panel de
caja, el retiro y el cierre de mostrador. `Caja` no tiene `ordering` en su `Meta`, así que hoy
funciona sólo porque la mostrador tiene `pk` más bajo.

**El riesgo concreto:** la sesión se busca con `usuario=request.user, estado='A'`. Un cajero que
además cerró un reparto tiene DOS sesiones abiertas a su nombre, y el cierre de mostrador podría
tomar la del reparto y rendir esa plata por el circuito equivocado.

**Corrección:** filtrar `tipo='M'` en los cinco lugares. Es lo que esos llamados siempre quisieron
decir. `get_caja_tesoreria()` ya lo hace bien y sirve de modelo.

### B.3 Cambios

- `Caja.TIPO_CAJA` += `('D', 'Tesorería de Reparto')`.
- `tesoreria_reparto(empresa_id, sucursal_id)`: get-or-create, una por sucursal, con su sesión
  abierta (mismo patrón que `get_o_abrir_caja` de Tesorería).
- `rendir()` cambia de destino: el `RetiroCaja` del reparto apunta a la sesión de la intermedia, no
  a Tesorería. Queda EN TRÁNSITO hasta que el administrativo lo cuenta y acepta.
- Bandeja de recepción propia de la Tesorería de Reparto, con el mismo mecanismo de diferencia y
  asiento que ya usa `rendicion_recibir_procesar`.
- Retiro y cierre pasan a preguntar **sobre qué caja se opera** (mostrador o tesorería de reparto).

---

## C — Rendición del vendedor

Definición del usuario: *"los vendedores rendirán a esta caja intermedia pero en su condición de
vendedores por los fondos que traen, no como reparto."*

**Para poder rendir hay que haber retenido.** El vendedor necesita su propia sesión sobre la caja
recaudadora, igual que un reparto: ahí caen sus cobranzas y de ahí rinde. Sin eso no habría nada que
entregar, porque la plata ya estaría en la intermedia.

- `RendicionReparto` se generaliza a **`RendicionDistribucion`**, con `reparto` **o** `vendedor`
  (`Personal`) — exactamente uno de los dos, por CheckConstraint.
- `CobranzaDistribucion.reparto` pasa a nullable, con `cobrador` obligatorio cuando no hay reparto:
  la plata siempre tiene un responsable.
- La cobranza del vendedor usa **el mismo FIFO y las mismas dos reglas**, sin parada. El servicio ya
  acepta `parada=None`; lo que falta es que acepte `reparto=None` y resuelva la sesión por vendedor.

---

## D — La Nota de Crédito descuenta el saldo de su factura

> **Afecta a todo el ERP, no sólo a Distribución.**

### D.1 La regla

Definición del usuario: *"Las notas de crédito, como están vinculadas a la factura que le dio
origen, deben computarse en el saldo pendiente de la factura (factura − NC relacionadas) y de ahí
sale el saldo real de la factura. La NC queda con saldo cero porque se aplicó totalmente a la
factura de origen."*

### D.2 Lo que falta hoy

- **No existe vínculo genérico NC → factura.** `Venta` no tiene ningún campo que lo guarde.
  `emitir_nota_credito_desde_venta()` recibe la venta original, copia sus ítems y **no persiste de
  dónde vino**. El único vínculo es `distribucion.NotaCreditoDistribucion.venta_origen`, satélite
  del módulo, que no sirve para armería ni para el resto del ERP.
- `recalcular_saldo_venta()` calcula `total − cobrado − Σ aplicaciones de recibos`. **No conoce las
  NC**, así que hoy la factura queda con saldo completo y la NC con saldo negativo.

### D.3 El diseño

1. `Venta.venta_origen`: FK a sí misma, nullable, `related_name='notas_credito'`. Sólo la usan los
   comprobantes con `tipo.signo = -1`.
2. `emitir_nota_credito_desde_venta()` la estampa.
3. `recalcular_saldo_venta()` suma un término:
   - Para una **factura**: `total − cobrado − Σ recibos − Σ NC que la referencian`.
   - Para una **NC con `venta_origen`**: `saldo = 0`, porque se aplicó por completo a su factura.
4. **El saldo por entidad no se toca.** `recalcular_saldo_cliente_proveedor()` suma
   `total − cobrado` sobre todas las ventas, y la NC ya entra en negativo por su `signo = -1`. Netea
   bien sin cambiar nada. Tocarlo la contaría dos veces.

### D.4 Efecto lateral que limpia el diseño de la fase 7

La fase 7 documentó *"las notas de crédito no entran en el FIFO"* como decisión de diseño, para no
manejar signos cruzados en el mismo recorrido. Con esta regla **deja de ser un compromiso**: la NC
baja el saldo de su factura y queda en cero, así que el filtro `saldo > 0` de
`comprobantes_abiertos()` es correcto **por construcción** y no por conveniencia.

### D.5 Impacto de datos

Consulta de sólo lectura sobre la base de producción:

```
NC activas en el sistema: 2
NC con saldo != 0        : 1
```

La migración de datos es de dos filas. **Limitación conocida:** las NC históricas no tienen
`venta_origen` (el campo es nuevo). Se puede rellenar desde `NotaCreditoDistribucion.venta_origen`
para las de Distribución; para el resto no hay de dónde deducirlo y quedan sin vincular. Con dos NC
en todo el sistema, es un problema teórico.

---

## E — Orden de ejecución y pruebas

| # | Bloque | Por qué en ese orden |
|---|--------|----------------------|
| 1 | **D** | El FIFO y todo reporte de saldos dependen de que el saldo de la factura sea el correcto |
| 2 | **A** | Independiente de los demás; habilita el reparto de cobranza |
| 3 | **B** | Incluye la corrección de la regresión (§B.2), que conviene no dejar viva |
| 4 | **C** | Se apoya en la caja intermedia de B |

**Pruebas por bloque:**

- **D:** la NC baja el saldo de su factura; la NC queda en cero; el saldo por entidad no cambia; una
  NC parcial deja saldo remanente; el FIFO no ofrece una factura ya cubierta por una NC.
- **A:** parada de cobranza sin comprobante; `cobro_minimo = 0`; el CheckConstraint rechaza las dos
  combinaciones inválidas; consolidado vacío en un reparto todo de cobranza; entrega y devoluciones
  no se ofrecen; la imputación de lo cobrado usa el FIFO estándar.
- **B:** el retiro del reparto va a la intermedia y no a Tesorería; los dos pasos con su diferencia;
  la intermedia rinde a Tesorería por el circuito existente; **el cierre de mostrador no toma la
  sesión de un reparto** (la prueba de la regresión).
- **C:** el vendedor tiene sesión propia; cobra sin reparto; rinde a la intermedia; el
  CheckConstraint exige exactamente un origen.

Backup con `pg_dump -F c` antes de cada tanda de migraciones, y registro incremental en
`docs/walkthrough.md` al cerrar cada bloque.

---

## F. Resultado de la implementación (31/08/2026)

| Bloque | Pruebas nuevas | Migraciones aplicadas |
|--------|---------------|-----------------------|
| **D** — NC descuenta su factura | 11 | `facturacion/0059`, `facturacion/0060` |
| **A** — Parada de sólo cobranza | 27 | `distribucion/0009` |
| **B** — Tesorería de Reparto | 20 | `tesoreria/0017` |
| **C** — Rendición del vendedor | 23 | `distribucion/0010` |

**Hallazgo no previsto en el plan (bloque D):** la convención de signo de las notas de crédito estaba
**documentada pero no implementada**. `saldos.py` y `tesoreria/views_htmx.py` decían que las NC *"se
graban en negativo vía `TipoComprobante.signo = -1`"*, pero los datos y el emisor las guardan con total
**positivo**. Como `recalcular_saldo_cliente_proveedor()` sumaba `total − cobrado` sin aplicar el signo,
**una Nota de Crédito AUMENTABA la deuda del cliente**. Se corrigió aplicando `tipo__signo` en la suma,
que es el criterio que ya usaba `productos.services.stock_service`. Verificación sobre la base real: el
saldo del único cliente con NC pasó de $599,00 a $515,00, exactamente 2 × $42,00 (las dos NC del sistema,
antes sumadas y ahora restadas).

**Decisión contable RESUELTA (addenda del 31/08/2026):** el usuario definió que las cajas de distribución
llevan **cuenta propia**, *"porque incluso ambos responsables son totalmente distintos"*. Se agregó
`ParametrosContables.cta_caja_reparto`, que usan la recaudadora `'R'` y la Tesorería de Reparto `'D'`.

Al implementarlo apareció que **el parámetro solo no alcanzaba**: `contabilizar_recibo()` arma el DEBE con
la cuenta del **medio de pago**, no con la de la caja, así que la cobranza habría seguido cayendo en la
cuenta de la mostrador. Se resolvió con un medio de pago propio `EFE-REP` apuntado a `cta_caja_reparto` y
mantenido en sincronía con él, sin tocar el motor contable. `cuenta_de_reparto()` **no hace fallback** a la
mostrador: sustituirla en silencio mezclaría lo que esta cuenta viene a separar.

Las dos cajas de distribución comparten la cuenta, así que el traslado entre ellas sigue sin generar
asiento. El movimiento contable aparece en el segundo tramo: **Debe Caja Central / Haber Caja de Reparto**.
