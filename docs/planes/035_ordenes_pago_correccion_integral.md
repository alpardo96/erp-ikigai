# Plan 035 — Órdenes de Pago y Recibos: Corrección Integral del Circuito

## Estado: ✅ Fases 1 a 9 implementadas (02/08/2026)
## Fecha: 2026-08-01

> **Avance:** las nueve fases del §5 están implementadas, migradas y con pruebas.
> Quedan fuera de alcance, con plan propio: el **formulario de aplicación diferida** de OP y
> Recibos (el listado ya expone el pendiente que lo alimenta) y la **conciliación bancaria**
> del plan 008, que cierra el tramo 2 del circuito del cheque propio.

## Origen
Auditoría del circuito de Órdenes de Pago contrastando la operatoria definida por el usuario
contra lo efectivamente implementado. Se detectaron desvíos funcionales, bugs que corrompen
datos en producción y estructuras de datos incompletas.

---

## 1. Reglas de negocio consolidadas (fuente de verdad)

Estas reglas son la especificación funcional acordada. Todo el código de este plan las respeta.

### 1.1 Tipos de Orden de Pago
| Tipo | Descripción | Imputación contable |
|------|-------------|---------------------|
| `P` — Pago a Proveedor | Tras elegir el proveedor, se despliegan sus comprobantes con saldo pendiente y se aplican importes a cada uno | Cuenta patrimonial del proveedor (`cta_pat`) |
| `S` — Pago Simple | Sin aplicación a comprobantes; se imputa manualmente a una o varias cuentas (ej. VEP SUSS → Seguridad Social a Pagar, Obra Social a Pagar, ART a Pagar, Intereses Fiscales) | Cuentas elegidas por el operador |

Sugerencia de cuenta en la OP Simple, según `condic`:
- `condic = 1` (Real/Fiscal) → sugiere `cta_pat` del cliente/proveedor.
- `condic = 2` (Presupuestado/No Fiscal) → sugiere `cta_res`.

Es **sugerencia**: el operador puede cambiarla.

### 1.2 Medios de pago
1. Efectivo (ARS).
2. Dólares — con tipo de moneda y cotización pactada (parámetro `CotizacionMoneda`).
3. Transferencias — cuenta bancaria origen, número de comprobante, CUIT destino, importe.
4. Cheques propios — cuenta bancaria girada, fecha de vencimiento, número, importe.
5. Retenciones practicadas — principalmente Ganancias RG 830.
6. Cheques de terceros (valores en cartera) — se entregan valores recibidos previamente por recibo.

Los puntos 3 y 4 se registran en la tabla satélite `TransaccionBancaria`, que lleva
**exclusivamente tres conceptos**: cheque emitido, transferencia emitida, transferencia recibida.
La conciliación con homebanking será otra tabla (plan 008), fuera del alcance de este plan.

### 1.3 Saldo de comprobante (REGLA CENTRAL)
> El saldo pendiente de una factura (emitida a clientes o recibida de proveedores) **se deriva**
> de restar al total del comprobante los pagos aplicados **con imputación a ese comprobante**.

Consecuencias:
- Las aplicaciones (`OrdenPagoAplicacion` / `ReciboAplicacion`) son la **fuente de verdad**.
- `Compra.pagado` / `Compra.saldo` (ídem `Venta.cobrado` / `Venta.saldo`) son **caché derivado**,
  recalculado **siempre desde cero** por un servicio. Nunca se hace `saldo -= importe`.
- Habilita el **papel de trabajo**: por cada factura, el detalle de las OP que la cancelaron con
  el importe aplicado en cada una (y viceversa).

### 1.4 Saldo de entidad (distinto del saldo de comprobante)
Convención de signos: **negativo = le debemos** (proveedores, o anticipos de clientes).

```
saldo_entidad = saldo_inicial
              + facturas de ventas
              − facturas de compras
              − recibos
              + órdenes de pago
```

Donde "facturas" incluye facturas, notas de crédito, notas de débito y comprobantes de
retención/percepción emitidos por la contraparte (todos con su signo).

**Supuesto declarado (S-1):** `OrdenPago.total` **incluye** las retenciones practicadas, tal
como se calcula hoy (la retención es un medio de pago más). Por lo tanto la fórmula suma la OP
**una sola vez** y NO agrega un término separado por retenciones: ya están dentro del total.
Sumarlas aparte las contaría dos veces. El resultado numérico es idéntico a la formulación
alternativa (total sin retenciones + retenciones aparte). Si se prefiere que `OrdenPago.total`
excluya las retenciones, se cambia en un único punto: `_saldo_entidad()` en
`contable/services/saldos.py`.

### 1.4.bis Signos: el operador siempre carga positivo
Los formularios (carga de NC, aplicación en OP/Recibo) capturan **siempre importes positivos**.
El signo es un atributo del **tipo de comprobante** (`TipoComprobante.signo`) y lo aplica el
sistema al persistir:

- En la carga de comprobantes, `facturacion/views.py` ya multiplica por `signo` (las NC quedan
  grabadas en negativo).
- En la **aplicación** a una OP/Recibo, el signo lo deriva el **servidor** del saldo del
  comprobante (`_normalizar_aplicacion`). El front envía magnitudes: así no puede aplicar un
  positivo a una Nota de Crédito ni fabricar saldo.

En pantalla, los comprobantes que restan se marcan visualmente (badge "RESTA") y el total
aplicado suma algebraicamente vía `data-signo`.

### 1.4.ter Régimen de retención RG 830 — se DEDUCE, no se tipea
`contable.Cuenta.rg_830` (ya existente) guarda, en cada cuenta de compras (activo y egresos),
el **código de régimen** de retención de ganancias que le corresponde.

`facturacion.Compra.cta_imputacion` guarda la cuenta imputada del comprobante. Por lo tanto, al
aplicar facturas a una Orden de Pago, el régimen a practicar **se deduce** encadenando:

```
Compra.cta_imputacion → Cuenta.rg_830 → régimen RG 830
```

Consecuencia de diseño: el campo `regimen` de `RetencionPracticada` se **sugiere
automáticamente** a partir de los comprobantes aplicados, no lo tipea el operador. Si las
facturas aplicadas caen en más de un régimen, se propone una retención por régimen.

Para compras con ítems (no gastos), `cta_imputacion` puede venir vacío: en ese caso el régimen
se deduce de la cuenta de compras del rubro del producto, y si tampoco resuelve, queda a cargo
del operador.

### 1.5 Comprobantes de retención/percepción recibidos
Los certificados que **nos emiten** proveedores/clientes se cargan como `Compra`/`Venta` según
corresponda, con su `TipoComprobante`. Por lo tanto **aparecen en el selector de aplicación** de
la OP/Recibo como cualquier otro comprobante con saldo. No requieren estructura nueva.

La tabla nueva `RetencionPracticada` (RG 830) es **solo para las que NOSOTROS practicamos**.
Las sufridas siguen en `RetPercSufrida` + campos `p_*` de la cabecera de compras.

### 1.6 Cheques propios: circuito en dos tramos
Diferidos y al día se tratan **igual**. Ambos van contra la cuenta de cheques emitidos del banco
respectivo. La cuenta se define **por cuenta bancaria** (nuevo campo), sin fallback global.

**Tramo 1 — Emisión (OP):**
```
Debe   Proveedor (cta_pat)              8.000.000
Haber    Cheques Emitidos a Pagar         5.000.000   ← CuentaBancaria.cuenta_contable_cheques
Haber    Ret. Ganancias a Depositar       1.000.000
Haber    Caja                             2.000.000
```

**Tramo 2 — Débito en cuenta (conciliación bancaria, plan 008):**
```
Debe   Cheques Emitidos a Pagar         5.000.000
Haber    Banco X Cta. Cte.                5.000.000   ← CuentaBancaria.cuenta_contable
```

Efecto: el saldo contable del banco coincide con el extracto; los cheques librados y no
debitados quedan visibles como pasivo propio.

Las **transferencias** no tienen tramo intermedio: debitan de inmediato contra
`CuentaBancaria.cuenta_contable`.

### 1.7 Reversión total
Al borrar/anular un asiento, un recibo o una orden de pago desde el listado, se revierte
**todo lo vinculado**:
- Asiento: cabecera anulada + líneas.
- Aplicaciones borradas y saldos de comprobantes recalculados.
- `ValorTerceros` entregados vuelven a `'C'` (En Cartera).
- `TransaccionBancaria` borrada.
- `RetencionPracticada` borrada.
- `MovimientoCaja` + detalles borrados.
- Comprobante marcado como anulado.

**Criterio adoptado:** el asiento se **anula** (trazabilidad de auditoría intacta, con fecha y
usuario) pero **todos sus efectos se revierten físicamente**. Es el objetivo funcional pedido
sin perder el rastro contable.

**Supuesto declarado (S-2):** la aplicación diferida de una OP/Recibo ya emitido contra
comprobantes (formulario de aplicación posterior) **no genera asiento**: el asiento se hizo al
emitir el comprobante contra `cta_pat`; la aplicación sólo reordena la cuenta corriente por
comprobante, sin efecto patrimonial.

---

## 2. Desvíos y bugs detectados (qué corrige este plan)

| # | Problema | Archivo | Gravedad |
|---|----------|---------|----------|
| B1 | `Compra.pagado` nunca se actualiza; `saldos.py` calcula deuda como `Σ(total − pagado)` ⇒ ignora todos los pagos | `tesoreria/views_htmx.py:482`, `contable/services/saldos.py:27` | 🔴 Corrompe datos |
| B2 | `recalcular_totales()` hace `saldo = total − pagado` con `pagado=0` ⇒ editar una compra pagada la deja impaga por su total | `facturacion/models.py:325` | 🔴 Corrompe datos |
| B3 | El selector de comprobantes filtra `saldo__gt=0` ⇒ **las NC nunca aparecen** para compensar | `tesoreria/views_htmx.py:235` | 🔴 Funcional |
| B4 | `submitForm` filtra `if (val > 0)` ⇒ una aplicación negativa se cae del payload silenciosamente | `templates/tesoreria/ordenpago_carga.html:708` | 🔴 Funcional |
| B5 | Sin validación server-side de signo ni tope de aplicación | `tesoreria/views_htmx.py:463-483` | 🟠 Seguridad |
| B6 | `ValorTerceros` sin campo `importe`: el valor del cheque se lee del detalle de caja de recepción; el front manda el importe y el backend lo usa sin contrastar | `tesoreria/models.py:374`, `views_htmx.py:507` | 🔴 Seguridad |
| B7 | Sin `select_for_update()` al entregar un valor ⇒ doble entrega del mismo cheque | `tesoreria/views_htmx.py:543` | 🟠 Concurrencia |
| B8 | `ValorTerceros.movimiento_detalle` con `CASCADE` ⇒ borrar el detalle de recepción borra el cheque ya entregado | `tesoreria/models.py:376` | 🟠 Integridad |
| B9 | `procesar_recibo` crea `ValorTerceros` sin `sucursal_id` ⇒ esos cheques nunca aparecen para rendir | `tesoreria/views_htmx.py:379` | 🟠 Funcional |
| B10 | `TransaccionBancaria` sin `importe`, sin `empresa`, sin estado; `fecha_operacion` hardcodeada a hoy | `tesoreria/models.py:356` | 🟠 Estructural |
| B11 | Datos de la retención (nro, fecha, CUIT) capturados en el form y **descartados** por el backend; no existe tabla de practicadas ⇒ SICORE imposible | `tesoreria/views_htmx.py:505-573` | 🔴 Funcional |
| B12 | `_cuenta_medio_cobro` no contempla categoría `RET` ⇒ ValidationError si el MedioPago no tiene cuenta | `contable/services/contabilizacion.py:852` | 🟠 Funcional |
| B13 | `_cuenta_medio_cobro` devuelve siempre `cuenta_contable` sin mirar `tipo_transaccion` ⇒ el cheque diferido debita el banco de inmediato | `contable/services/contabilizacion.py:840` | 🟠 Contable |
| B14 | `proveedor_id`, `cuenta_bancaria_id` y `cuenta_contable_id` llegan por JSON sin validar contra `session['empresa_id']` | `tesoreria/views_htmx.py:418-492` | 🔴 Multi-tenant |
| B15 | `anular_asiento_de_comprobante` sólo marca la cabecera; no revierte ningún efecto | `contable/services/contabilizacion.py:21` | 🔴 Funcional |
| B16 | No existe listado ni anulación ni reimpresión de OP/Recibos | — | 🟠 Funcional |
| B17 | Importes con `toLocaleString`/`floatformat` propios en vez del estándar `formato_ar` | `templates/tesoreria/*` | 🟡 Norma |
| B18 | `recalcular_saldo_cliente_proveedor` bifurca por `tipo_entidad` con fórmulas erróneas; ignora recibos y OP; una entidad cliente+proveedor computa una sola punta | `contable/services/saldos.py:14-29` | 🔴 Corrompe datos |

**Descartado tras revisión:** la fecha de `MovimientoCaja` (`auto_now_add`) NO es un bug — la
caja diaria se analiza por sesión (`caja_id`), nunca por fecha. Verificado en
`tesoreria/services/caja_diaria.py:206,386`.

---

## 3. Cambios de modelo y migraciones

### 3.1 `tesoreria.CuentaBancaria`
```python
cuenta_contable_cheques = FK(contable.Cuenta, PROTECT, null=True, blank=True,
                             verbose_name="Cta. Contable Cheques Emitidos")
```
Impacto: `CuentaBancariaForm` tiene `fields` explícitos → agregar en `fields`, en `widgets` y
filtrar el queryset por empresa e `imputable=1`. El modal renderiza campo por campo → agregar
el bloque en `templates/configuracion/modals/cuentabancaria_form.html`.

### 3.2 `tesoreria.TransaccionBancaria`
Alcance acotado a 3 conceptos (`TR`, `TE`, `CP`) — ya coincide con `TIPO_CHOICES`.
```python
empresa          = FK(Empresa, PROTECT, db_index=True)      # nuevo — evita 4 JOINs
importe          = Decimal(15,2)                             # nuevo — dato propio
cuit_contraparte = CharField(20, blank=True)                 # nuevo — hoy se descarta
estado           = 'E' Emitida | 'D' Debitada | 'A' Anulada | 'R' Rechazada   # nuevo
fecha_debito     = Date(null=True)                           # nuevo — tramo 2
asiento_id       = Integer(null=True, db_index=True)         # nuevo — asiento de emisión
asiento_debito_id= Integer(null=True)                        # nuevo — asiento del tramo 2
fecha_operacion  → default = fecha del comprobante (no `timezone.localdate()`)
movimiento_detalle → PROTECT (era CASCADE)
```
Índices: `(empresa, fecha_operacion)`, `(cuenta_bancaria, estado)`, `(asiento_id)`.

### 3.3 `tesoreria.ValorTerceros`
```python
empresa              = FK(Empresa, PROTECT, db_index=True)   # nuevo
importe              = Decimal(15,2)                          # nuevo — dato propio del cheque
sucursal             = FK(Sucursal, PROTECT)                  # era IntegerField suelto
recibo               = FK(Recibo, SET_NULL, null=True)        # nuevo — origen
fecha_recepcion      = Date(null=True)                        # nuevo
asiento_recepcion_id = Integer(null=True)                     # nuevo — informativo
fecha_entrega        = Date(null=True)                        # nuevo
asiento_entrega_id   = Integer(null=True)                     # nuevo — informativo
movimiento_detalle   → PROTECT (era CASCADE)
```
`orden_pago` ya existe. Índices: `(empresa, estado)`, `(empresa, fecha_vencimiento)`.

### 3.4 `contable.ParametrosContables`
```python
cta_ret_practicada_ganancias = FK(Cuenta, ...)  # RG 830 — el pedido concreto
cta_ret_practicada_iva       = FK(Cuenta, ...)
cta_ret_practicada_iibb      = FK(Cuenta, ...)
cta_ret_practicada_suss      = FK(Cuenta, ...)
```
Se agregan las cuatro en la misma migración (modelo idéntico, evita una segunda migración).
**No confundir** con las `cta_ret_*` existentes: ésas son las **sufridas** (crédito fiscal, DEBE).
La UI sale sola: `ParametrosContablesForm` usa `exclude = ['empresa']` y asigna el widget de
búsqueda a todo campo `cta_*`.

### 3.5 `contable.RetencionPracticada` (nueva)
```python
empresa        = FK(Empresa, PROTECT)
orden_pago     = FK(tesoreria.OrdenPago, CASCADE, related_name='retenciones_practicadas')
proveedor      = FK(ClienteProveedor, PROTECT)
impuesto       = choices IMPUESTOS_RET_PERC  (default 'GAN')
regimen        = CharField(10)      # código de régimen ARCA
nro_certificado= CharField(30)
fecha          = Date
base           = Decimal(15,2)
alicuota       = Decimal(6,3)
importe        = Decimal(15,2)
cuit_retenido  = CharField(11)
asiento_id     = Integer(null=True, db_index=True)
```
Índices: `(empresa, fecha)`, `(empresa, impuesto)`, `(asiento_id)`.
Base de la futura DDJJ SICORE.

---

## 4. Servicios nuevos y modificados

| Servicio | Archivo | Responsabilidad |
|----------|---------|-----------------|
| `recalcular_saldo_compra(compra_id)` | `contable/services/saldos.py` | `pagado = Σ OrdenPagoAplicacion.importe`; `saldo = total − pagado`. Siempre desde cero. |
| `recalcular_saldo_venta(venta_id)` | idem | `cobrado = Σ ReciboAplicacion.importe`; `saldo = total − cobrado`. |
| `recalcular_saldo_cliente_proveedor()` | idem (reescritura) | Fórmula unificada §1.4, sin bifurcar por `tipo_entidad`. |
| `pendiente_de_aplicar(comprobante)` | idem | `total − Σ aplicaciones` — alimenta la columna del listado y el formulario de aplicación diferida. |
| `revertir_operacion(...)` | `contable/services/reversion.py` (nuevo) | Reversión total §1.7, transaccional. |
| `_cuenta_medio_cobro` | `contable/services/contabilizacion.py` | Bifurca por `tipo_transaccion` (B13) y contempla `RET` (B12). |

---

## 5. Fases de ejecución

| Fase | Contenido | Corrige | Estado |
|------|-----------|---------|--------|
| 1 | Servicios de saldo (comprobante + entidad) y reemplazo del `-=` | B1, B2, B18 | ✅ |
| 2 | Aplicación con signo: NC/ND/certificados, validación server-side | B3, B4, B5 | ✅ |
| 3 | Parámetros de retenciones practicadas + cta. cheques emitidos + `_cuenta_medio_cobro` | B12, B13 | ✅ |
| 4 | `TransaccionBancaria` robustecida | B10 | ✅ |
| 5 | `ValorTerceros` robustecido | B6, B7, B8, B9 | ✅ |
| 6 | `RetencionPracticada` + captura en la OP | B11 | ✅ |
| 7 | Servicio único de reversión | B15 | ✅ |
| 8 | Listados OP/Recibo con monto aplicado y pendiente, anulación, reimpresión PDF, formato es-AR | B16, B17 | ✅ |
| 9 | Validación multi-tenant transversal + tests | B14 | ✅ |

### Migraciones aplicadas
| Migración | Contenido |
|-----------|-----------|
| `tesoreria/0010_aplicaciones_importe_moneda` | `importe` en moneda del comprobante + `importe_pesos`, con **backfill** que reexpresa los importes históricos y reconstruye todos los saldos |
| `contable/0017` y `tesoreria/0011` | Cuentas de retenciones practicadas + `cuenta_contable_cheques` |
| `tesoreria/0012_plan035_satelites_bancarios_y_valores` | Campos propios de `TransaccionBancaria` y `ValorTerceros`, con **backfill** desde los datos existentes |
| `contable/0018_plan035_retencion_practicada` | Tabla `RetencionPracticada` |

Fuera de alcance (planes propios): formulario de aplicación diferida (a diseñar) y conciliación
bancaria con homebanking (plan 008).

---

## 6. Reimpresión de comprobantes

Desde el listado de OP y de Recibos, reimprimir el comprobante con **todo lo vinculado**:
cabecera, comprobantes aplicados, medios de pago desglosados (efectivo, dólares con cotización,
transferencias, cheques propios, valores de terceros), retenciones practicadas y el
**certificado de retención de Ganancias RG 830** cuando corresponda.

Infraestructura: `xhtml2pdf` vía `render_pdf_response()` de `contable/services/reportes_pdf.py`.

---

## 7. Plan de pruebas

### Automatizadas
| Test | Verifica |
|------|----------|
| `test_saldo_compra_derivado_de_aplicaciones` | `saldo = total − Σ aplicaciones` tras N pagos parciales |
| `test_editar_compra_pagada_no_resetea_saldo` | B2: `recalcular_totales` respeta lo aplicado |
| `test_aplicacion_nota_credito_negativa` | Factura 10.000.000 + NC −2.000.000 ⇒ neto 8.000.000 = medios de pago |
| `test_nc_aparece_en_selector` | B3: el selector devuelve comprobantes con `saldo != 0` |
| `test_aplicacion_rechaza_signo_invalido` | B5: no se puede aplicar positivo a una NC ni exceder el saldo |
| `test_valor_terceros_importe_no_manipulable` | B6: el backend ignora el importe del payload y usa el del cheque |
| `test_cheque_propio_imputa_cuenta_cheques` | Tramo 1: acredita `cuenta_contable_cheques`, no el banco |
| `test_transferencia_imputa_cuenta_banco` | La transferencia sigue debitando el banco |
| `test_retencion_practicada_se_persiste` | B11: nro, fecha, régimen, base y alícuota quedan guardados |
| `test_reversion_devuelve_cheque_a_cartera` | B15: `estado` vuelve a `'C'` y se limpia `orden_pago` |
| `test_reversion_recalcula_saldos` | Las facturas vuelven a su saldo previo |
| `test_saldo_entidad_formula_unificada` | §1.4 con entidad cliente+proveedor simultánea |
| `test_op_de_otra_empresa_rechazada` | B14: aislamiento multi-tenant |

### Manuales
- [ ] OP a proveedor aplicando factura + NC, cancelando con efectivo + cheque propio + retención.
- [ ] Verificar asiento: `cta_pat` al debe; caja, cheques emitidos y retención a depositar al haber.
- [ ] Anular la OP desde el listado y verificar que todo vuelve atrás.
- [ ] Reimprimir la OP con su certificado de retención.
- [ ] Confirmar que los importes muestran formato es-AR en todas las pantallas tocadas.

---

## 8. Criterio de Hecho
- [ ] Los 18 bugs listados corregidos y cubiertos por test.
- [ ] Migraciones aplicadas sin pérdida de datos (con backfill de los campos nuevos).
- [ ] Tests en verde.
- [ ] `docs/walkthrough.txt` actualizado por fase.
