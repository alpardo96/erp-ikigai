# Plan 075: Integridad de la numeración de comprobantes de venta (Factura / PRE / Nota de Crédito)

**Fecha:** 2026-08-28
**Estado:** BORRADOR PARA ANÁLISIS Y APROBACIÓN — **no se modificó ni una línea de código**.
**Origen:** hallazgo surgido al diseñar el [Plan 074 — Módulo Distribución](074_modulo_distribucion.md).
**Destinatario:** el desarrollador responsable del módulo de facturación / presupuestos.
**Alcance:** este plan **no** pertenece al módulo Distribución. Afecta a **todas las empresas del ERP** que emitan comprobantes de venta, y por eso se trata por separado y requiere aprobación propia.

---

## 1. Por qué existe este plan — el principio de control interno

El control de integridad de los comprobantes **sólo es posible mediante la numeración correlativa de los comprobantes que uno EMITE**. Ésa es la razón por la que existen los documentos "espejo" en cualquier sistema contable serio:

| Documento propio (numeración propia, auditable) | Documento de terceros (numeración ajena) |
|---|---|
| **Informe de Recepción** | Remito del proveedor |
| **Orden de Pago** | Recibo emitido por el proveedor |
| **Recibo** | Orden de pago emitida por el cliente |

Sobre el documento propio se puede auditar: si la serie va 1, 2, 3, 5, falta el 4 y hay que explicarlo. Sobre el número de un tercero no se puede auditar nada.

El ERP **ya implementa correctamente esta doctrina** para los documentos prenumerados por el sistema: `core.ContadorDocumento` + `core/services/numeracion.py`, con `select_for_update()`, `UniqueConstraint` en cada documento y una función `auditar_correlativos()` que detecta huecos, duplicados y desfasajes contra el contador.

**Los comprobantes de venta quedaron fuera de ese esquema.** Este plan los incorpora.

---

## 2. Cómo debe funcionar la numeración (definición del usuario)

| Comprobante | `punto` | `numero` |
|---|---|---|
| **Factura** (`condic = 1`) | Punto de venta **autorizado por ARCA**, definido por parámetro | **El que devuelve ARCA** por webservice |
| **Nota de Crédito fiscal** (`condic = 1`) | Ídem, por tipo de comprobante | Ídem, el que devuelve ARCA |
| **PRE** (`condic = 2`) | **`sucursal_id`** de la sucursal activa, la que emite el comprobante | **Correlativo propio del sistema** para ese punto |
| **NCI** — Nota de Crédito Interna (`condic = 2`) | **`sucursal_id`**, ídem PRE | **Correlativo propio, en serie independiente de la del PRE** |

De acá se desprende el reparto de responsabilidades:

- La **serie fiscal la gobierna ARCA** y el sistema la acompaña. El control local es de **consistencia** (que no haya duplicados ni saltos inexplicables frente a lo autorizado), no de generación.
- La **serie del PRE la gobierna enteramente el sistema**. No hay ninguna autoridad externa que la valide: que sea correlativa, sin huecos y sin duplicados es responsabilidad exclusiva nuestra. Es la que más protección necesita, justamente porque nadie más la controla.

---

## 3. Hallazgos verificados en el código actual

Revisión de `facturacion/services/facturacion_lote_service.py`, `facturacion/services/afip_service.py`, `facturacion/models.py` y `core/services/numeracion.py`.

### 3.1 — El camino correcto contra ARCA existe, pero la facturación por lote no lo usa

`facturacion/services/afip_service.py` **ya implementa lo que corresponde**: consulta `FECompUltimoAutorizado` (línea 100) y toma el número emitido de `CbteDesde` en la respuesta del CAE (línea 315). Es exactamente el circuito descripto en §2.

Sin embargo, `facturacion_lote_service.py` **no lo invoca**: calcula el número localmente (§3.2) y, en `modo_prueba`, estampa un CAE ficticio (`"12345678901234"`). Mientras el modo prueba sea el único uso el impacto es acotado, pero **el lote no está preparado para emitir contra ARCA**: al pasar a producción, el número local y el número autorizado pueden divergir.

### 3.2 — La numeración se calcula leyendo el último número, sin bloqueo

`facturacion/services/facturacion_lote_service.py`, tanto para el comprobante fiscal como para el PRE:

```python
ultimo_num = Venta.objects.filter(
    empresa_id=self.empresa_id, tipo=tipo_fiscal, punto=numero_pto
).order_by('-numero').first()
numero_fact = (ultimo_num.numero + 1) if ultimo_num else 1
```

Es el patrón "leo el último y le sumo uno", **sin `select_for_update()`**. Dos procesos que facturen a la vez leen el mismo último número y asignan el mismo siguiente. Para el PRE, que no tiene ninguna autoridad externa que lo corrija, esto es directamente el único control que existe.

### 3.3 — `Venta` no tiene restricción única de número en la base

`facturacion/models.py`, `class Venta` → `Meta` declara únicamente `indexes`:

```python
indexes = [
    models.Index(fields=['empresa', 'numero']),
    models.Index(fields=['empresa', 'cliente']),
    models.Index(fields=['empresa', 'fecha']),
]
```

No hay `unique_together` ni `UniqueConstraint`. **No existe segunda barrera**: si la lógica de aplicación falla, la base acepta el duplicado y el problema se descubre meses después, en una auditoría.

La comparación es elocuente dentro del propio proyecto:

| Modelo | Patrón de numeración | Protección en la base |
|---|---|---|
| `OrdenCompra` | `siguiente_numero()` con bloqueo | ✅ `UniqueConstraint (empresa, punto, numero)` |
| `Recepcion`, `RemitoInterno` | `siguiente_numero()` con bloqueo | ✅ `UniqueConstraint` |
| `Recibo` | "último + 1" en `save()`, sin bloqueo | ✅ `unique_together ('empresa','punto','numero')` |
| **`Venta`** | **"último + 1", sin bloqueo** | ❌ **ninguna** |

`Venta` es el único documento emitido del sistema sin ninguna de las dos protecciones.

### 3.4 — Fallback silencioso del punto de emisión a `1`

```python
pto_vta_obj = PuntoVenta.objects.filter(id=pto_vta_id).first()
numero_pto = pto_vta_obj.numero if pto_vta_obj else 1
```

Si el punto no se resuelve, el comprobante **se emite igual**, numerado en el punto `1`. Un error de configuración no interrumpe nada: produce comprobantes en una serie que no corresponde, y se descubre tarde.

Además, para el PRE el punto debería ser el **`sucursal_id`** (§2), no un `PuntoVenta.numero`: los puntos de venta son de ARCA y el PRE no es fiscal.

### 3.5 — El tipo PRE se resuelve con un fallback amplio

```python
tipo_interno = TipoComprobante.objects.filter(codigo='PRE').first()
if not tipo_interno:
    tipo_interno = TipoComprobante.objects.filter(estado=True)\
        .exclude(codigo__in=['001', '006', '011']).first()
```

Si no existe el tipo `'PRE'`, se toma **cualquier tipo activo que no sea A, B o C**. El comprobante sale emitido bajo un tipo elegido por descarte, y la serie de ese tipo queda contaminada.

---

## 4. Riesgos

| Riesgo | Severidad | Consecuencia |
|---|---|---|
| **Dos PRE con el mismo número** | **Alta** | Nadie lo corrige desde afuera: dos comprobantes distintos en la cuenta corriente de un cliente con el mismo número, imposibles de imputar y de reclamar |
| Huecos en la serie del PRE sin explicación | **Alta** | El control de integridad deja de ser posible; observación de auditoría |
| El lote emite un número fiscal distinto del autorizado por ARCA | **Alta** | Rechazo del webservice o comprobante local que no coincide con el declarado |
| Comprobantes numerados en el punto equivocado por el fallback | Media | Dos series mezcladas, difícil de desarmar una vez emitidas |
| Comprobante emitido bajo un tipo elegido por descarte | Media | Serie contaminada con comprobantes de otra naturaleza |

El riesgo se agrava en escenarios de **facturación por lote**, donde se emiten decenas de comprobantes seguidos, que es exactamente lo que necesita el módulo Distribución ([Plan 074](074_modulo_distribucion.md), §7.4).

---

## 5. Propuesta

### 5.1 — Auditoría previa de los datos existentes *(primer paso, antes de tocar nada)*

Antes de cualquier migración hay que saber si ya existen duplicados, porque de eso depende que el `UniqueConstraint` pueda aplicarse:

```sql
SELECT empresa_id, tipo_id, punto, numero, COUNT(*)
FROM facturacion_venta
GROUP BY empresa_id, tipo_id, punto, numero
HAVING COUNT(*) > 1
ORDER BY 1, 2, 3, 4;
```

Y el mapa de huecos por serie, para dimensionar el estado actual:

```sql
SELECT empresa_id, tipo_id, punto,
       MIN(numero) AS desde, MAX(numero) AS hasta,
       COUNT(*) AS emitidos,
       MAX(numero) - MIN(numero) + 1 - COUNT(*) AS faltantes
FROM facturacion_venta
GROUP BY empresa_id, tipo_id, punto
ORDER BY 1, 2, 3;
```

Si aparecen duplicados hay que resolverlos **antes** de la migración, con criterio contable caso por caso.

### 5.2 — Numeración del PRE y de la NCI por contador transaccional

Agregar a `core.ContadorDocumento.TIPOS_DOCUMENTO` los tipos **`VENTA_PRE`** y **`VENTA_NCI`**, y tomar el número con `core.services.numeracion.siguiente_numero(empresa, punto, tipo)`, que **ya está implementado, bloquea con `select_for_update()` y está cubierto por tests** (`facturacion/tests/test_plan028.py`).

**Punto de emisión: `sucursal_id`** de la sucursal activa (definición del usuario, §2). Los contadores quedan por `(empresa, sucursal_id, VENTA_PRE)` y `(empresa, sucursal_id, VENTA_NCI)`: un correlativo propio por sucursal emisora y por tipo de documento.

**Series separadas para PRE y NCI** (decisión tomada). Dos contadores en lugar de uno, a cambio de que cada serie se audite por `(empresa, tipo, punto)` — que es exactamente como ya agrupa `auditar_correlativos()`, sin ninguna excepción ni código especial. Es además el mismo criterio del lado fiscal, donde Factura y Nota de Crédito llevan series separadas por punto: un solo modelo mental para todo el sistema.

El `TipoComprobante` de la NCI debe llevar **`signo = -1`**, que es el campo que el modelo ya tiene para eso.

> Nota menor, ya conversada: `Sucursal.punto` es el campo que el proyecto usa para prenumerar OC, Informes de Recepción y Remitos Internos, y tiene la ventaja de ser editable. Se deja constancia por si en algún momento se quisiera unificar; la definición vigente es `sucursal_id`.

El número se asigna **al confirmar** el comprobante, no en borrador, que es la regla que el propio servicio documenta para no dejar huecos.

### 5.3 — Numeración fiscal: usar el número de ARCA

La serie fiscal **no** se lleva por `ContadorDocumento`: la gobierna ARCA. Lo que corresponde es que la facturación por lote **use `AfipService`** (§3.1) en lugar de calcular el número localmente, tomando `CbteDesde` de la respuesta del CAE, igual que ya hace la facturación individual.

El control local sobre la serie fiscal es de **consistencia**, no de generación: el `UniqueConstraint` (§5.4) y la auditoría (§5.6).

### 5.4 — Restricción única en la base

```python
constraints = [
    models.UniqueConstraint(
        fields=['empresa', 'tipo', 'punto', 'numero'],
        name='uniq_venta_empresa_tipo_punto_numero',
    ),
]
```

Es la segunda barrera que hoy falta y que el resto de los documentos del sistema ya tiene. Aplica por igual a Facturas, PRE y Notas de Crédito.

### 5.5 — Eliminar los fallbacks silenciosos

- **Punto de emisión:** si no se resuelve, **fallar con un error explícito** en lugar de asumir `1`. Un comprobante mal numerado es peor que un comprobante no emitido.
- **Tipo PRE:** si no existe el `TipoComprobante` con `codigo = 'PRE'`, **fallar con un mensaje claro** ("Falta configurar el tipo de comprobante PRE") en vez de elegir uno por descarte. Alternativamente, crearlo en la configuración inicial de la empresa.

### 5.6 — Extender la auditoría de correlativos

`core/services/numeracion.auditar_correlativos()` ya detecta huecos, duplicados y desfasajes contra el contador para OC, Informes de Recepción y Remitos Internos, con la regla correcta de que **un documento anulado conserva su número y no genera hueco**.

Agregar a la lista de `fuentes` los comprobantes de venta, agrupando por `(empresa, tipo, punto)`:
- **PRE y NCI** — cada uno contra su `ContadorDocumento`, en series independientes.
- **Factura y Nota de Crédito fiscal** — sin contador propio: se auditan huecos y duplicados de la serie, y se contrasta el máximo local contra `FECompUltimoAutorizado` de ARCA, que es el control cruzado más valioso de todos.

Con esto el sistema pasa a **poder demostrar su propia integridad**, que es el objetivo de fondo de este plan. Corresponde exponerlo como reporte en el panel, no sólo como función.

---

## 6. Plan de pruebas

- Dos procesos concurrentes emitiendo PRE **no** generan números duplicados.
- PRE y NCI de la misma sucursal avanzan en **series independientes**: emitir una NCI no consume un número de PRE.
- El `UniqueConstraint` rechaza el duplicado si la lógica de aplicación fallara.
- El lote fiscal toma el número de `AfipService` y no de una consulta local.
- Punto de emisión no resuelto → **error explícito**, no comprobante en el punto 1.
- Tipo `'PRE'` inexistente → **error explícito**, no un tipo elegido por descarte.
- PRE emitido desde dos sucursales distintas → dos series independientes, cada una correlativa desde 1.
- Anulación de un comprobante: **conserva su número** y no genera hueco.
- `auditar_correlativos()` detecta huecos, duplicados y desfasaje del contador sobre series de venta sembradas a propósito.
- Contraste del máximo local contra `FECompUltimoAutorizado` para la serie fiscal.
- Regresión: la facturación individual y por lote existente sigue funcionando igual para las empresas ya en producción.

---

## 7. Orden de ejecución sugerido

1. **Auditoría de datos** (§5.1) — sólo lectura, sin riesgo. Determina el alcance real del problema.
2. Resolución de los duplicados que aparezcan, con criterio contable caso por caso.
3. `UniqueConstraint` en `Venta` + eliminación de los fallbacks silenciosos (§5.4 y §5.5).
4. `ContadorDocumento.VENTA_PRE` y `VENTA_NCI`, y migración de la numeración del PRE a `sucursal_id` (§5.2).
5. Facturación por lote contra ARCA vía `AfipService` (§5.3).
6. Extensión de `auditar_correlativos()` y su reporte en el panel (§5.6).

Los pasos 3 a 5 tocan código en producción de todas las empresas: se ejecutan **sólo con aprobación explícita** y con su registro en `docs/walkthrough.md`.
