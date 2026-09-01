# Diseño — Gestión de Caja Mostrador por Sucursal: Retiros y Cierre

> Documento de diseño consensuado. Sirve como prompt/spec para el desarrollo.
> Estado: diseño cerrado, pendiente de implementación.

## Contexto

ERP Django. El núcleo contable usa **plan de cuentas único por empresa**
(`contable/models.py`: `Cuenta`, sin `sucursal_id`), asientos por empresa
(`Asiento`, `AsientoLinea` con soporte multimoneda: `divisa`, `cotizacion`,
`debe_divisa`, `haber_divisa`) y parámetros en `ParametrosContables`. La
tesorería (`tesoreria/models.py`) tiene `Caja` (por sucursal), `CajaSesion`,
`MovimientoCaja`, `Valor` (cheques/valores), `CobroTarjeta` y `Recibo`. Los
asientos automáticos se generan en `contable/services/contabilizacion.py`. El
cobro de mostrador vive en `tesoreria/views_htmx.py::caja_mostrador_procesar_cobro`
con template `templates/tesoreria/modals/caja_mostrador_cobrar.html`.

## Modelo conceptual acordado

La sucursal es una **dimensión analítica a nivel de encabezado de asiento**, NO
una multiplicación del plan de cuentas. Las cuentas se distinguen por **función**
(Mostrador vs Central/Tesorería) y **moneda**, nunca por sucursal. Casa Central
(`sucursal_id = 1`) tiene **mostrador propio Y tesorería**, ambos suc 1.

**Tratamiento por instrumento:**

| Instrumento | Cuenta | Traslado mostrador→central (retiro/cierre) |
|---|---|---|
| **Efectivo pesos** | `Caja Mostrador` (única) → `Caja Central` (única) | **Genera asiento(s)** de traslado. Saldo exacto por sucursal vía header. |
| **Dólares** | `Caja Mostrador Dólares` → `Caja Central Dólares` | **Genera asiento(s)** de traslado (con divisa/cotización). |
| **Cheques / valores** | `Valores en Cartera` (única) | **NO genera asiento.** Solo actualiza `Valor.sucursal_id` (custodia). |
| **Tarjetas / cupones** | `Tarjetas a Cobrar` (única) | **NO genera asiento.** Solo actualiza `CobroTarjeta.sucursal_id` + listado de cupones. |

### Asimetría aceptada conscientemente

El **efectivo queda exacto por sucursal en el mayor** (porque sí hace asiento de
traslado). Los **cheques y tarjetas se controlan por sucursal en lo operativo**
(`Valor.sucursal_id` / `CobroTarjeta.sucursal_id`), no en el sumas y saldos: a
nivel empresa el saldo de `Valores en Cartera` / `Tarjetas a Cobrar` siempre es
correcto, pero el mayor por sucursal de esas cuentas refleja la sucursal de
**origen** (donde se cobró), no la ubicación física actual. El dato físico vive
en lo operativo.

## Regla de asientos de traslado (efectivo y dólares)

Por cada moneda, comparar sucursal del mostrador origen vs sucursal de la
tesorería destino (normalmente suc 1):

- **Misma sucursal** (ej. mostrador casa central → tesorería casa central, ambos
  suc 1): **UN asiento**, header = esa sucursal:
  `Debe Caja Central / Haber Caja Mostrador` (por el importe de la moneda).
- **Sucursales distintas** (ej. mostrador suc 2 → tesorería suc 1): **DOS asientos**
  vía cuenta puente:
  - Asiento A — header = sucursal origen: `Debe Transferencias entre sucursales / Haber Caja Mostrador`.
  - Asiento B — header = sucursal central: `Debe Caja Central / Haber Transferencias entre sucursales`.

Cada asiento debe **balancear por sí solo en pesos** (así el sumas y saldos por
sucursal cuadra). Pesos y dólares se tratan en **asientos separados por moneda**;
las líneas en dólares llevan `divisa='USD'`, `cotizacion`, `debe_divisa`/
`haber_divisa`, y la cuenta puente netea a cero en ambas monedas (misma
cotización en ambas patas). La cuenta `Transferencias entre sucursales` netea a
cero en el consolidado.

## Cambios de modelo de datos

1. **`Asiento`** (`contable/models.py`): agregar
   `sucursal = ForeignKey(Sucursal, null=True, blank=True)` (header). Migración:
   nullable; data migration opcional para backfill desde la venta vinculada en
   asientos de ventas.

2. **`ParametrosContables`** (`contable/models.py`): agregar cuentas:
   - `cta_caja_mostrador`, `cta_caja_mostrador_dolares`
   - `cta_caja_central`, `cta_caja_central_dolares`
   - `cta_transferencias_sucursal` (cuenta puente)
   - (reutilizar las existentes `cta_valores_cartera` y `cta_tarjetas_a_cobrar`)

3. **`Valor`** (`tesoreria/models.py`): agregar
   `sucursal = ForeignKey(Sucursal, null=True, blank=True)` (custodia actual). Al
   crearse en el cobro = `caja.sucursal`. Backfill desde `recibo.sucursal` /
   `venta.sucursal`.

4. **`CobroTarjeta`** (`tesoreria/models.py`): agregar
   `sucursal = ForeignKey(Sucursal, null=True, blank=True)` (ubicación actual). Al
   crearse = `sesion_caja.caja.sucursal`. Backfill desde `sesion_caja`.

5. **Nuevos modelos** (`tesoreria/models.py`):

   ```python
   class RetiroCaja(AuditModel):
       sesion = FK CajaSesion (related_name='retiros')
       tipo = Char [('P', 'Parcial'), ('C', 'Cierre')]
       fecha = DateTimeField
       usuario = FK User
       sucursal_origen = FK Sucursal
       sucursal_destino = FK Sucursal       # tesorería (default suc 1)
       efectivo_pesos = Decimal(15, 2) default 0      # entregado/declarado
       efectivo_dolares = Decimal(15, 2) default 0    # entregado/declarado
       cotizacion_dolar = Decimal(15, 4)
       observaciones = Text(null)
       anulado = Bool default False

   class RetiroCajaValor:        # cheques incluidos
       retiro = FK RetiroCaja (related_name='valores')
       valor = FK Valor

   class RetiroCajaTarjeta:      # cupones incluidos
       retiro = FK RetiroCaja (related_name='cupones')
       cobro_tarjeta = FK CobroTarjeta

   class RetiroCajaAsiento:      # trazabilidad de asientos generados
       retiro = FK RetiroCaja (related_name='asientos')
       asiento_id = IntegerField
   ```

   > Nota: `RetiroCajaAsiento` sigue la convención del proyecto de guardar
   > `asiento_id` suelto (como `Venta.asiento_id` y `CobroTarjeta.asiento_id`),
   > permitiendo que un retiro registre varios asientos (pesos + dólares, A + B).

## Lógica de negocio

### Cobro de mostrador (ajuste al flujo existente)

En `caja_mostrador_procesar_cobro` / `contabilizacion.py`: las cobranzas de
mostrador deben imputar a las **cuentas de mostrador** (`cta_caja_mostrador`,
`cta_caja_mostrador_dolares`), setear `Asiento.sucursal = caja.sucursal`, y
setear `sucursal` en los `Valor` y `CobroTarjeta` creados = `caja.sucursal`.

### Retiro parcial (botón "Retiros") — NO ciego

Durante la sesión abierta, el cajero registra un retiro hacia la tesorería:

- Ingresa importe de **efectivo pesos** y **dólares** a entregar.
- **Selecciona** qué cheques (`Valor`) y qué cupones (`CobroTarjeta`) entrega.
- Al confirmar:
  - Crea `RetiroCaja(tipo='P')` + detalle (`RetiroCajaValor`, `RetiroCajaTarjeta`).
  - Genera el/los **asiento(s) de traslado de efectivo y dólares** según la regla
    anterior; registra sus ids en `RetiroCajaAsiento`.
  - Actualiza `sucursal` de los `Valor` y `CobroTarjeta` seleccionados =
    `sucursal_destino` (**sin asiento**).
  - Registra `MovimientoCaja(tipo='R')` para reflejar la salida en la sesión.

### Cierre de caja — CIEGO

- El cajero **cuenta y declara** el efectivo/dólares que tiene; **la pantalla NO
  le muestra el saldo calculado** por el sistema.
- El sistema guarda en `CajaSesion`: `saldo_final_declarado` (lo contado) y
  `saldo_final_calculado` (lo que el sistema esperaba). La **diferencia
  (calculado − declarado) = faltante/sobrante**.
- Al cerrar:
  - Crea `RetiroCaja(tipo='C')`.
  - Genera el/los **asiento(s) de traslado por el importe DECLARADO** (efectivo y
    dólares) mostrador→central, según la regla. → La diferencia faltante/sobrante
    **queda con saldo en `Caja Mostrador` de esa sucursal** (vía header),
    pendiente de ajuste futuro. NO generar asiento de ajuste ahora.
  - Mueve a central **todos los cheques y cupones remanentes** de la sesión:
    actualiza su `sucursal` = destino (sin asiento) y genera el **listado de
    cupones de tarjeta**.
  - Marca `CajaSesion.estado = 'C'` y `fecha_cierre`.

### Anulación

Anular un `RetiroCaja` debe: marcar `anulado=True`, anular (no borrar) sus
asientos, y **revertir** la `sucursal` de los `Valor`/`CobroTarjeta` involucrados
a la sucursal de origen.

## Consultas / reportes afectados

- **Valores en cartera**: agregar filtro por `Valor.sucursal` (custodia actual).
- **Cupones de tarjeta**: filtro por `CobroTarjeta.sucursal`.
- **Mayor / sumas y saldos**: permitir filtro por `Asiento.sucursal`. Validar que
  cada sucursal cuadre por sí sola (todo asiento es de una sola sucursal; los
  traslados cruzados usan la cuenta puente).

## Fuera de alcance (NO implementar ahora)

- **Faltantes y sobrantes**: análisis y asiento de ajuste de la diferencia
  declarado vs calculado → módulo posterior.
- **Punto de venta por caja / facturación por webservice** → etapa posterior;
  dejar el modelo preparado pero sin configurar.

## Criterios de aceptación

1. Cobro de mostrador imputa a cuentas de mostrador y setea `sucursal` en asiento,
   valores y cupones.
2. Retiro parcial y cierre generan los asientos de efectivo/dólares correctos
   (1 asiento si misma sucursal, 2 + puente si cruza) y cuadran por sucursal en el
   sumas y saldos.
3. Cheques y cupones cambian `sucursal` sin generar asiento; la cartera filtra por
   sucursal correctamente.
4. El cierre es ciego (no expone el calculado) y deja la diferencia estacionada en
   Caja Mostrador sin asiento de ajuste.
5. La cuenta `Transferencias entre sucursales` netea a cero en el consolidado.
6. Migraciones nullable + backfill; no rompe asientos ni flujos existentes.
