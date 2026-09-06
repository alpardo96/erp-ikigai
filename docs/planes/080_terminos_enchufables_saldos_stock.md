# Plan 080 — Términos enchufables en Stock y Cuenta Corriente

## Estado: ✅ Completado (2026-09-06)

**Fecha:** 2026-09-06
**Origen:** requisito de la verticalidad Agrícola — ver [`docs/agricola/plan inicial agricola.md`](../agricola/plan%20inicial%20agricola.md)

---

## Objetivo

Abrir tres servicios del core para que una verticalidad pueda **sumar sus propios orígenes** de
stock y de cuenta corriente, sin que el core la importe y sin romper la arquitectura *Modo
Enchufe* del [Plan 075](075_arquitectura_modo_enchufe.md).

Es el **único cambio al core** que necesita todo el módulo agrícola. Sin él, la liquidación de
tabaco no genera deuda con el productor ni ingresa el tabaco al stock.

---

## 1. El problema

### 1.1 Stock

`productos/services/stock_service.py` deriva el stock de una **lista declarativa de términos**
(`_terminos()`): compras, recepciones, ventas y remitos internos. El propio docstring del archivo
anticipa la extensión:

> *"Se declaran como datos y no cableados en el cuerpo de `recalcular_stock()`, para que sumar un
> término nuevo —el de AJUSTES DE INVENTARIO, cuando se haga el formulario de toma física— sea
> agregar una entrada acá y no reescribir la función revalidando los cuatro que ya funcionan."*

El acopio de tabaco **no pasa por `CompraItem`**: usa tablas propias. Por lo tanto no entra al
stock por ningún término existente y necesita el suyo.

**Pero** `_terminos()` importa modelos concretos. Si se le agregara un `import` de
`verticalidades.agricola`, al desenchufar la carpeta se caería el cálculo de stock **de todo el
ERP**.

### 1.2 Cuenta corriente

`contable/services/saldos.py::recalcular_saldo_cliente_proveedor()` suma **cuatro orígenes fijos,
cableados en el cuerpo de la función**:

```
saldo = saldo_inicial + ventas − compras − recibos + órdenes_de_pago
```

La liquidación de tabaco necesita ser un quinto término con el mismo signo que compras. Mismo
problema de acoplamiento, pero agravado: acá no hay lista declarativa que extender.

### 1.3 Imputación de pagos

`pendiente_de_aplicar_op()` calcula lo no imputado de una Orden de Pago como
`OrdenPago.total − Σ OrdenPagoAplicacion`. Como `OrdenPagoAplicacion.compra` es un **FK duro a
`Compra` con `PROTECT`**, una OP que cancela una liquidación de tabaco se imputa en una tabla de
la verticalidad y figuraría eternamente como "sin aplicar".

---

## 2. La solución: tres registros de extensión

Un **registro** al que cada verticalidad se suscribe desde su `apps.py::ready()`, con importación
tolerante. La dependencia va **verticalidad → core**, nunca al revés.

Si la carpeta de la verticalidad no está, su app no entra a `INSTALLED_APPS` (el
auto-descubrimiento de `config/settings.py` no la ve), `ready()` no corre, no se registra nada y
los servicios del core calculan exactamente como hoy.

### 2.1 Regla de oro de los registros

**El registro es idempotente por `nombre`.** `ready()` puede ejecutarse más de una vez (recarga
del autoreload, ciertos runners de test). Si un término se registrara dos veces, el stock y los
saldos se **duplicarían en silencio**. El registro descarta el alta repetida del mismo nombre y
deja un `logger.warning`.

---

## 3. Servicios

| Servicio | Archivo | Firma | Qué hace |
|---|---|---|---|
| `registrar_termino_stock` | `productos/services/stock_service.py` | `(termino: dict) -> None` | Suma un origen al cálculo de `StockSucursal.cantidad` |
| `registrar_termino_ctacte` | `contable/services/saldos.py` | `(termino: dict) -> None` | Suma un origen al saldo de cuenta corriente de un tercero |
| `registrar_aplicacion_op` | `contable/services/saldos.py` | `(aplicacion: dict) -> None` | Suma una tabla de imputación al cálculo de lo aplicado de una OP |

### 3.1 Contrato de un término de stock

Idéntico al de los cuatro términos actuales, más `nombre` obligatorio:

```python
{
    'nombre':     'agricola_tabaco_fardos',      # único; clave de idempotencia
    'modelo':     FardoTabaco,                   # modelo de ítem que mueve stock
    'signo':      1,                             # +1 entra, −1 sale
    'cantidad':   'kilos',                       # campo con la cantidad
    'producto':   'romaneo__variedad__producto_id',
    'sucursal':   'romaneo__sucursal_id',
    'signo_cbte': None,                          # ruta a TipoComprobante.signo, o None
    'excluir':    Q(romaneo__estado=ROMANEO_ANULADO),
}
```

### 3.2 Contrato de un término de cuenta corriente

```python
{
    'nombre':         'agricola_tabaco_liquidaciones',
    'modelo':         LiquidacionTabaco,
    'campo_entidad':  'productor',       # FK a facturacion.ClienteProveedor
    'campo_empresa':  'empresa_id',
    'campo_importe':  'total',           # el TOTAL del comprobante, no el neto a pagar
    'signo':          -1,                # mismo signo que compras: nos genera deuda
    'excluir':        Q(estado=LIQUIDACION_ANULADA),   # `None` = no excluir nada
}
```

`campo_empresa` no es decorativo: sin él, un tercero que opera con dos empresas arrastraría a la
cuenta corriente comprobantes de la otra. Hay un test dedicado a eso.

### 3.3 Contrato de una tabla de imputación de OP

```python
{
    'nombre':        'agricola_tabaco_liquidacion_pago',
    'modelo':        LiquidacionPago,
    'campo_op':      'orden_pago',
    'campo_importe': 'importe',
}
```

---

## 4. Archivos a crear/modificar

### `productos/services/stock_service.py`

- Agregar el registro `_TERMINOS_EXTRA` y la función pública `registrar_termino_stock()`.
- `_terminos()` devuelve los cuatro de siempre **+ los registrados**.
- **No se toca** `_sumar_termino()`, `recalcular_stock()`, `recalcular_comprometido()`,
  `disponible_real()` ni ninguno de los puntos de entrada de las señales.
- `recalcular_stock_masivo()` ya itera `_terminos()`: hereda la extensión sin cambios.

```python
_TERMINOS_EXTRA = []          # los que registran las verticalidades

_CLAVES_TERMINO = {'nombre', 'modelo', 'signo', 'cantidad', 'producto', 'sucursal',
                   'signo_cbte', 'excluir'}


def registrar_termino_stock(termino):
    """Punto de extensión público: agrega un origen al cálculo del stock.

    Lo llaman las verticalidades desde `apps.py::ready()`. El core NUNCA importa una
    verticalidad: es la verticalidad la que se anuncia. Si su carpeta no está, su app no
    entra a INSTALLED_APPS, `ready()` no corre y el stock se calcula sin ese término.

    Es idempotente por 'nombre': `ready()` puede correr más de una vez y un término
    duplicado haría que el stock se contara dos veces.
    """
    faltan = _CLAVES_TERMINO - set(termino)
    if faltan:
        raise ValueError(f"Término de stock incompleto, faltan claves: {sorted(faltan)}")
    if any(t['nombre'] == termino['nombre'] for t in _TERMINOS_EXTRA):
        logger.warning("Término de stock '%s' ya registrado; se ignora el alta repetida.",
                       termino['nombre'])
        return
    _TERMINOS_EXTRA.append(termino)


def _terminos():
    """Se arma adentro de la función para no importar `facturacion` al cargar el módulo."""
    from facturacion.models import CompraItem, RecepcionItem, RemitoInternoItem, VentaItem

    base = [
        # ... los cuatro términos actuales, SIN TOCAR, con 'nombre' ya presente ...
    ]
    return base + list(_TERMINOS_EXTRA)
```

### `contable/services/saldos.py`

- Registros `_TERMINOS_CTACTE_EXTRA` y `_APLICACIONES_OP_EXTRA`, con sus funciones públicas.
- `recalcular_saldo_cliente_proveedor()`: después de los cuatro términos actuales, iterar los
  registrados. **Los cuatro cálculos existentes no se modifican.**
- `pendiente_de_aplicar_op()`: sumar también las aplicaciones registradas.
- Actualizar el docstring del "supuesto S-1" para dejar dicho que los términos de verticalidad
  aportan el **total del comprobante** (deuda), no el neto a pagar, para no descuadrar contra
  `OrdenPago.total`, que ya incluye las retenciones practicadas.

### El lado consumidor — **no es parte de este plan**

La suscripción concreta de la verticalidad (`verticalidades/agricola/tabaco/apps.py::ready()` +
`registros.py`) se entrega junto con los modelos que registra, en las **Etapas 1 y 2** del plan
agrícola. No puede escribirse antes: los modelos `FardoTabaco` y `LiquidacionTabaco` todavía no
existen.

Este plan entrega **sólo los tres puntos de extensión del core y sus pruebas**. Queda operativo y
verificado con el registro vacío, que es exactamente el estado en que se despliega.

La forma que tendrá el consumidor, para referencia:

```python
# verticalidades/agricola/tabaco/apps.py
class TabacoConfig(AppConfig):
    name = 'verticalidades.agricola.tabaco'

    def ready(self):
        from . import registros          # el import dispara las suscripciones
```

`registros.py` concentra las suscripciones con `try/except ImportError`, por si el core todavía
no tuviera el punto de extensión (despliegue escalonado).

---

## 5. Tests mínimos

### No regresión del core (obligatorios, se ejecutan primero)

| Test | Qué verifica |
|---|---|
| `test_stock_sin_terminos_extra` | Con el registro vacío, `recalcular_stock()` da idéntico a hoy para compra, venta, recepción y remito interno |
| `test_stock_masivo_sin_terminos_extra` | `recalcular_stock_masivo()` no reporta diferencias sobre un dataset estable |
| `test_nc_sigue_invirtiendo` | Una NC de venta devuelve stock y una NC de compra lo saca (`tipo__signo = −1`) |
| `test_saldo_ctacte_sin_terminos_extra` | El saldo de un tercero con ventas, compras, recibos y OP da idéntico al baseline |
| `test_pendiente_op_sin_aplicaciones_extra` | `pendiente_de_aplicar_op()` no cambia |

### Del mecanismo

| Test | Qué verifica |
|---|---|
| `test_registro_idempotente` | Registrar dos veces el mismo `nombre` no duplica el término ni el importe |
| `test_registro_valida_claves` | Un término incompleto levanta `ValueError` |
| `test_termino_extra_suma_stock` | Un término de prueba aporta su cantidad a `recalcular_stock()` |
| `test_termino_extra_suma_ctacte` | Un término de prueba con signo −1 baja el saldo del tercero |
| `test_aplicacion_extra_reduce_pendiente` | Una aplicación registrada reduce `pendiente_de_aplicar_op()` |
| `test_excluir_respetado` | El `Q()` de exclusión deja fuera los anulados |

### Prueba de fuego (manual, documentada en la entrega)

1. Mover `verticalidades/agricola/` fuera del proyecto.
2. `python manage.py check` → sin errores.
3. `python manage.py recalcular_stock` → corre y no reporta diferencias.
4. Abrir una compra, una venta y una cuenta corriente → operan con normalidad.
5. Restaurar la carpeta y verificar que el término vuelve a registrarse una sola vez.

---

## 6. Dependencias

- **Requiere:** `productos`, `contable`, `facturacion`, `tesoreria` (todos ya operativos).
- **Habilita:** Etapa 2 (Liquidación) y Etapa 4 (Stock) de la verticalidad Agrícola.

---

## 7. Riesgos y mitigación

| Riesgo | Mitigación |
|---|---|
| Doble registro → stock y saldos contados dos veces | Idempotencia por `nombre` + test dedicado |
| Un término mal formado rompe el stock de todo el ERP | Validación de claves obligatorias al registrar, con `ValueError` explícito |
| Import circular core ↔ verticalidad | El core nunca importa; la verticalidad se anuncia desde `ready()`, cuando los modelos ya están cargados |
| Verticalidad desenchufada | Su app no entra a `INSTALLED_APPS`; `ready()` no corre; el core calcula sin el término |
| Costo de consulta | `recalcular_stock()` suma una consulta por término extra; `recalcular_stock_masivo()` una agrupada. Se mide con `EXPLAIN ANALYZE` antes de aprobar |

---

## 8. Criterio de Hecho

- [x] Suite completa ejecutada **antes** del cambio y registrada como baseline — **577 tests, 15 errores, 5.454 s**.
- [x] Los tres puntos de extensión implementados, documentados y con docstring que explique el porqué.
- [x] Ningún cálculo existente modificado: los cuatro términos de stock y los cuatro de cuenta
      corriente quedan textualmente iguales.
- [x] Tests de no regresión y de mecanismo en verde — **26/26**.
- [x] Prueba de fuego de desenchufe ejecutada y documentada.
- [x] Suite completa ejecutada **después** — **603 tests (577 + 26), 15 errores, 5.568 s**: mismo
      conteo que el baseline, sin fallas nuevas.
- [x] **Comparación dirigida**: 9 módulos / 90 tests corridos con los servicios revertidos a
      `7e0b322` y con el Plan 080. Ambos 8 errores, listas **idénticas** (el diff sólo difiere en
      el tiempo transcurrido).
- [x] Sin migraciones del core: el plan **no crea ni altera tablas**.
- [x] `docs/walkthrough.md` actualizado.

### Nota de ejecución

Para poder obtener el baseline hubo que reparar un bloqueante preexistente: la suite **no podía
correr** porque `verticalidades/estudio` no tenía migraciones y su modelo, que hereda de
`AuditModel`, choca con `auth_user` durante el `sync_apps` previo a las migraciones. Se generó
`verticalidades/estudio/migrations/0001_initial.py` (aditiva, sin `--fake`).

El baseline dejó al descubierto **15 errores preexistentes** ajenos a este plan, clasificados en
`docs/walkthrough.md`. Uno de ellos no es sólo de tests:
`facturacion/services/facturacion_lote_service.py` importa `TarifaEstudio` desde
`facturacion.models`, de donde ese modelo ya no existe — **código de producción roto en tiempo de
importación**, y la misma clase de violación del Modo Enchufe que el Plan 075 prohíbe. Queda
señalado, sin corregir, por estar fuera del alcance.
