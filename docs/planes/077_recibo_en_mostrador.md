# Plan 077 — La cuenta del efectivo la define la caja, y el recibo del cajero

**Estado:** ✅ **IMPLEMENTADO** (31/08/2026) · **Depende de:** [Plan 076](076_circuito_fondos_distribucion.md)
**Alcance:** E toca el **motor contable** (todas las empresas). F y G son de Tesorería.

---

## 0. El diagnóstico

Al configurar `cta_caja_reparto` apareció que **el efectivo de mostrador tiene hoy tres destinos
contables distintos**, según por qué camino entre o salga:

| Camino | Cuenta que usa | Dónde |
|--------|----------------|-------|
| Venta de mostrador cobrada en el acto | `cta_caja` | `tesoreria/views_htmx.py:1246` |
| Recibo de cobranza | la del **medio de pago** (fallback `cta_caja_central`) | `contabilizacion.py:898/903` |
| Retiro / cierre de caja | `cta_caja_mostrador` | `generar_asientos_traslado()` |

Por eso `cta_caja_mostrador` **sólo recibe haber y nunca debe**: no es que no cierre en cero, es que
se vuelve cada vez más acreedora con cada cierre. En ARMERIA ya quedó en −$25.000 con una sola línea.

Definición del usuario: *"caja mostrador descarga sobre las cuentas definidas por parámetro
(cobranzas por un lado y retiros / cierre de caja por el otro), por lo que deberían quedar en cero o
lo que se defina como fondo fijo al final de cada cierre."*

---

## E — Para el efectivo, la cuenta la define la CAJA

### E.1 El principio

> Un cheque es un cheque entre donde entre; **el efectivo vive en un cajón concreto**. La cuenta no
> es un atributo del medio de pago ni del tipo de comprobante: es de la caja.

Y el criterio operativo que lo confirma, en palabras del usuario: **la cuenta la define quién tiene
que rendir la plata.** Un recibo hecho en el mostrador lo rinde el cajero → `cta_caja_mostrador`. El
mismo recibo hecho en Tesorería ya está en Tesorería → `cta_caja_central`.

### E.2 El helper

`cuenta_efectivo_de_caja(caja, parametros, en_divisa=False)`, único, en `contabilizacion.py`:

| `caja.tipo` | Pesos | Dólares |
|-------------|-------|---------|
| `'M'` Mostrador | `cta_caja_mostrador` | `cta_caja_mostrador_dolares` |
| `'R'` Recaudadora · `'D'` Tesorería de Reparto | `cta_caja_reparto` | — (el reparto cobra en pesos) |
| `'T'` Tesorería | `cta_caja_central` | `cta_caja_central_dolares` |

- Para `'R'`/`'D'` **sin parámetro configurado, lanza error**: sustituirlo en silencio mezclaría lo
  que ese parámetro vino a separar (Plan 076).
- Para `'M'`/`'T'` sin configurar, **devuelve `None` y la cadena sigue** como hasta hoy: es el estado
  heredado de empresas que nunca lo cargaron, y romperles la contabilización sería peor.

### E.3 Los tres call sites

1. `_cuenta_medio_cobro()` — nuevo paso **2**, sólo para categoría `EFE`, entre la cuenta bancaria
   concreta y la lógica de divisas. `DIG` (billetera digital) NO entra: no vive en un cajón.
2. `_crear_asientos_y_movimientos_cobro()` — la venta de mostrador deja de usar `cta_caja` fija.
3. `generar_asientos_traslado()` — ya recibe `cuenta_origen` desde el Plan 076; se unifica para que
   la resuelva el mismo helper y no una función paralela.

### E.4 Simplificación que se lleva puesta

El medio de pago `EFE-REP` que el Plan 076 creaba para distribución **deja de hacer falta**: la caja
ya dice la cuenta. Se elimina `medio_pago_efectivo()` y queda **un solo mecanismo** en vez de dos.

### E.5 La prueba que importa

No verifica la implementación sino **el requerimiento**: cobrar en el mostrador, cerrar la caja
dejando un fondo fijo, y comprobar que `cta_caja_mostrador` queda **exactamente en el fondo fijo**.

---

## F — Emitir Recibo desde Caja Mostrador

**Es el mismo recibo que ya existe**: cliente, aplicación a facturas con saldo, o recibo simple sin
aplicar. No hay pantalla nueva.

Definición del usuario: *"El recibo que está actualmente en base.html impacta en caja tesorería y es
lo correcto. Ese menú será para el Tesorero. El cajero todo lo que maneje será a través de su CAJA
MOSTRADOR."*

- `ReciboCargaView` gana un atributo `origen`, y una segunda URL apunta a **la misma vista y el mismo
  template** con `origen='MOSTRADOR'`.
- `procesar_recibo()` hoy resuelve la caja con `get_o_abrir_caja(...)`, que **siempre devuelve la de
  Tesorería**: ahí está la raíz de que un recibo nunca impacte el mostrador. Pasa a usar la sesión de
  mostrador abierta del cajero cuando el origen es el mostrador. **Si su caja está cerrada, falla**:
  no se puede meter plata en un cajón que no está abierto.
- Botón *Emitir Recibo* en `caja_mostrador_index.html`.

**La parte contable sale sola:** con E, el recibo del mostrador debita `cta_caja_mostrador` sin una
sola línea de lógica propia. Es el mismo mecanismo, no una excepción.

---

## G — El cajero opera sólo su Caja Mostrador

`Perfil.es_cajero_mostrador`, **`False` por defecto**: así nadie pierde accesos al aplicar el cambio y
sólo se restringe a quien se marque explícitamente. Al revés —un permiso que haya que otorgar— dejaría
a todos afuera hasta tildarlo uno por uno.

Con el flag en `True` se ocultan **y se bloquean**: Emitir Recibo (el de Tesorería), Emitir Orden de
Pago, sus listados, Caja Diaria, Recepción de Rendiciones y Origen y Aplicación de Fondos. Le queda
Caja Mostrador, con su botón nuevo.

> **El bloqueo va en las vistas, no sólo en el menú.** Esconder un link no es un permiso: la URL
> sigue estando ahí para quien la escriba.

---

## H — Orden y pruebas

1. **E** primero: F depende de que la cuenta la resuelva la caja.
2. **F**, que es una línea de lógica más el botón.
3. **G**, independiente de las dos.

Backup con `pg_dump -F c` antes de las migraciones y registro incremental en `docs/walkthrough.md`.
