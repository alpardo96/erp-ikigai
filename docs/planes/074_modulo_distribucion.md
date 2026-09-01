# Plan 074: Módulo Distribución (Distribuidora de Lácteos)

**Fecha:** 2026-08-28
**Versión:** v9
**Estado:** BORRADOR PARA ANÁLISIS Y APROBACIÓN — **no se modificó ni una línea de código del sistema**.
**Autor del diseño:** Claude Opus (nivel Global / arquitectura)
**Fuente funcional:** `D:\ERP-Ikigai\Distribuidora\Distribuidora-Sistema-Anterior.pdf` (4 hojas del sistema VFP en uso) + relevamiento de los 9 procesos.
**Plan relacionado:** [075 — Integridad de la numeración de comprobantes de venta](075_integridad_numeracion_comprobantes_venta.md) (afecta a todo el ERP, se aprueba por separado).

### Historial de versiones
- **v1** — Borrador inicial sobre el relevamiento y el PDF.
- **v2** — La Hoja de Ruta se genera **después** de facturar; medios de pago trazables siempre a `condic = 1`; precios por coeficiente; la condición de venta es del comprobante.
- **v3** — Regla del **saldo disponible negativo**; coeficiente mayorista único sobre `precio_total`; reporte de faltantes; `codigo_anterior` en `Producto`.
- **v4** — Asignación de stock por **orden de llegada**; stock devuelto vuelve a disponible (vehículos refrigerados); se imprimen **los dos códigos**; un cliente, un solo vendedor.
- **v5** — **El control de integridad por numeración correlativa pasa a ser principio rector del módulo** (§4.2). Toda no entrega o anulación posterior a la facturación se instrumenta con **NOTA DE CRÉDITO con su CAE** (§7.10). Nuevo documento propio: **Recepción de Devoluciones**, vinculado a la Hoja de Ruta (§5.E). El **Pedido pasa a ser un documento numerado**. Los hallazgos sobre la numeración del PRE se trasladan al **Plan 075**.
- **v9** — **`Personal` como tabla propia** para vendedores, repartidores y cobradores, con `usuario` OneToOne nullable (§4.3 y §5.A). `Venta.vendedor` y `Preventa.vendedor` quedan intactos; en distribución el vendedor se obtiene por el pedido.
- **v8** — Catálogo inicial de `MotivoDevolucion` aprobado, con `sugiere_apto_reventa` (§5.A). NC del PRE = tipo **`NCI`**, `signo = -1`, **serie independiente** de la del PRE. Queda una sola decisión abierta (§11.1), que no condiciona el diseño.
- **v11** — *Implementadas las fases 7 y 8 (cobranzas y saldos).* Tres precisiones que surgieron al escribir el algoritmo (§7.7): **(a)** todo medio que no sea explícitamente trazable —incluido `OTR`— se trata como EFECTIVO, porque sin rastro externo verificable no puede respaldar una operación fiscal; **(b)** las **notas de crédito no entran en el FIFO**: acreditar una NC contra una factura es una imputación entre comprobantes, no una cobranza, y mezclarla obligaría a manejar signos cruzados en el mismo recorrido; **(c)** el recibo `condic = 2` lleva EXACTAMENTE el efectivo que canceló PRE y todo lo demás —trazables, efectivo aplicado a facturas y excedente— va al recibo `condic = 1`, que es lo que hace que los detalles de cada movimiento de caja cuadren con el total de su recibo. Además, la rendición usa `cta_caja_mostrador` como cuenta de origen del traslado: **la caja recaudadora no tiene parámetro contable propio** (decisión revisable, §7.9).
- **v10** — *Implementada la fase 6.* El **stock lo devuelve la Nota de Crédito, no la Recepción de Devoluciones** (§7.10, caso B, paso 3): `stock_service` deriva el stock de los comprobantes y la NC ya invierte por signo, así que hacerlo en los dos lados lo contaría dos veces.
- **v7** — El `ID` que encabeza cada cliente en la Hoja de Ruta del sistema anterior **es el N° de Pedido** (§2, obs. 7): el sistema viejo ya numeraba los pedidos. La **Recepción de Devoluciones es una por cada Pedido**, no una por reparto (§5.E y §7.10), y la Hoja de Ruta lleva una **casilla de DEVOLUCIÓN** que el repartidor marca en la calle (§7.6).
- **v6** — Definida la **numeración de `Venta`**: Factura con punto ARCA y número del webservice; PRE con `punto = sucursal_id` y correlativo propio (mismo criterio para los tres documentos internos). Se explicita la **cadena de trazabilidad** Pedido → Comprobante → Hoja de Ruta → Recepción → NC: la Hoja de Ruta imprime **N° de Pedido junto al del comprobante** (§7.6) y la Recepción de Devoluciones los referencia por su parada (§5.E). Se **invierte el orden de la devolución**: primero se cuenta, después se acredita (§7.10).

---

## 1. Objetivo y alcance

Incorporar al ERP el circuito completo de una **distribuidora de productos lácteos y comestibles**:

**Pedido → Asignación de stock → Facturación (control de crédito) → Reparto → Entrega y cobranza → Recepción de devoluciones y Notas de Crédito → Rendición a Tesorería.**

Se activa por `Empresa.tipo_actividad = 'DISTRIBUIDORA'` (valor que **ya existe** desde el Plan 070), con el mismo patrón condicional que hoy usa ARMERÍA. Una empresa estándar no ve nada nuevo.

**Fuera de alcance:** portal de autogestión del cliente; ruteo geográfico (GPS); facturación electrónica desde el celular (el CAE se pide desde el servidor).

**Nota de encuadre:** todos los clientes de reparto son **revendedores**. La venta a consumidor final se hace en el local, con el circuito de descuentos autorizados y tope por `productos_rubro.descuento_maximo` **ya desarrollado**, y no se toca en este plan.

---

## 2. Lectura del sistema anterior

| Hoja | Reporte | Datos que expone | Traducción al ERP |
|------|---------|------------------|-------------------|
| 1 | **Factura B fiscal** con CAE y QR | Cliente, **"Condición Venta: Contado"**, detalle, cantidad, precio, total | `Venta` con `condic = 1` |
| 2 | **"PR" — Comprobante NO válido como factura** | Código de cliente `(399)`, domicilio, **Saldo: 0**, **CONTADO**, detalle **con código de artículo**, descuentos, total | `Venta` con `condic = 2` |
| 3 | **Hoja de Ruta** — `Reparto: 8639`, "JUAN", fecha | Por cliente: **`ID 186276` = el número de PEDIDO del cliente**, código y nombre, **Saldo CC**, Total $, detalle con código/cantidad/precio/total. Anotaciones manuscritas de cobranza y firma | Nuevo: `Reparto` + `RepartoParada` |
| 4 | **Consolidado de Artículos** — `Reparto: 8638`, "MAXIMILIANO + ROMINA" | Por artículo: ID, descripción, **Cantidad** y **Kgs**, totales (781,98 un. / 407,26 kg) | Reporte agregado del `Reparto` |

**Observaciones que salen del papel:**
1. Vendedores y repartidores **trabajan por código de artículo**; la lista de precios impresa lo lleva.
2. El **peso en kilos** es dato de control de carga del vehículo. Hoy `Producto` no tiene peso.
3. Un reparto puede tener **más de un responsable** ("MAXIMILIANO + ROMINA").
4. La hoja de ruta es el documento de **control físico y de cobranza**: el cliente firma sobre ella.
5. Los horarios de las tres hojas del 01/08/2026 son **06:21, 06:49 y 06:58**: se factura, se consolida y se arma la hoja de ruta de madrugada, sobre pedidos tomados el día anterior.
6. **El `Reparto: 8639` del papel ya es un número correlativo.** El sistema anterior lo tenía; el nuevo también debe tenerlo (§4.2).
7. **El `ID 186276` con el que arranca cada cliente en la Hoja de Ruta es el número de PEDIDO**, no el del comprobante. El sistema anterior ya numeraba los pedidos y los imprimía en la hoja de ruta: es el eslabón que une el pedido del cliente con su comprobante y con la devolución. Lo llamamos **Pedido**.

---

## 3. Qué ya existe en el ERP y se reutiliza

| Necesidad | Ya existe | Ubicación |
|-----------|-----------|-----------|
| Pedido con estados y autorización | `Preventa` / `PreventaItem` | `facturacion/models.py:391` |
| Comprobante fiscal y no fiscal | `Venta` con `condic`, `VentaItem`, alícuotas, CAE | `facturacion/models.py:479` |
| **Nota de crédito** | `facturacion/services/notas_credito.py` | — |
| **Facturación por lote** (patrón a extender) | `facturacion/services/facturacion_lote_service.py` | — |
| **Numeración correlativa con bloqueo + auditoría de integridad** | `core.ContadorDocumento`, `core/services/numeracion.py` (`siguiente_numero`, `auditar_correlativos`) | `core/models.py:5` |
| Documento propio espejo del de un tercero (patrón) | `Recepcion` (Informe de Recepción) frente al remito del proveedor | `facturacion/models.py:968` |
| Stock por sucursal calculado | `StockSucursal`, `productos/services/stock_service.py` | `productos/models.py:248` |
| Límite de crédito y saldo del cliente | `ClienteProveedor.limite` y `.saldo` | `facturacion/models.py:32` |
| Extensión de cliente por actividad (patrón) | `ExtensionArmeria` | `facturacion/models.py:132` |
| Precio de lista con IVA | `Producto.precio_total` | `productos/models.py:127` |
| Cobranza imputada a comprobantes | `Recibo` + `ReciboAplicacion` | `tesoreria/models.py:107` |
| Medios de pago desglosados | `MovimientoCaja` + `MovimientoCajaDetalle` + `MedioPago` | `tesoreria/models.py:341` |
| **Rendición en dos pasos** | `RetiroCaja` | `tesoreria/models.py:558` |
| `codigo_anterior` (patrón de migración) | `ClienteProveedor`, `Marca`, `Rubro`, `Familia` | varios |

---

## 4. Principios rectores

### 4.1 — Vocabulario

- **Pedido (`Preventa`)**: documento **interno**, sin valor para el cliente ni para la contabilidad. *Preventa es un proceso dentro del sistema.* Lleva **numeración propia** (§4.2).
- **PRE**: comprobante **entregado al cliente**, genera cuenta corriente y asiento. Es una **`Venta` con `condic = 2`**. *PRE es una operación No Fiscal.*
- **Condición de venta**: CONTADO o CUENTA CORRIENTE. **No tiene relación con `condic`** (regla inflexible). Se resuelve al facturar.
- **Saldo disponible**: `limite − saldo`. **Puede ser negativo**, y ése es el número que gobierna la cobranza del repartidor (§7.4).
- **Anular el reparto de un cliente**: el cliente avisa antes de que salga el camión. Si ya estaba facturado, **se emite Nota de Crédito** y se reimprimen Hoja de Ruta y Consolidado.
- **No entrega**: el cliente no recibe la mercadería (cerrado, sin dinero, rechazo). **Se emite Nota de Crédito** por el total.

### 4.2 — Control de integridad por numeración correlativa

> El control de integridad **sólo es posible sobre los comprobantes que uno EMITE, con numeración correlativa propia**. Por eso existe el **Informe de Recepción** frente al remito que envía el proveedor, y la **Orden de Pago** frente al recibo que emite el tercero: sobre el documento propio se puede auditar la serie; sobre el número de un tercero no se puede auditar nada.

Este módulo emite **seis documentos**, y **todos** deben llevar numeración correlativa auditable:

| # | Documento | Numeración | Estado en el ERP |
|---|-----------|-----------|------------------|
| 1 | **Pedido** (nota de pedido) | `ContadorDocumento.PEDIDO` | ✅ Implementado (fase 1) y auditado (fase 8) |
| 2 | **Hoja de Ruta / Reparto** | `ContadorDocumento.REPARTO` | ✅ Implementado (fase 5) y auditado (fase 8) |
| 3 | **Recepción de Devoluciones** | `ContadorDocumento.RECEPCION_DEVOLUCION` | ✅ Implementado (fase 6) y auditado (fase 8) |
| 4 | **Factura** (`condic = 1`) | `punto` = punto de venta **autorizado por ARCA** (por parámetro); `numero` = **el que devuelve ARCA** por webservice | ⚠️ Existe, pero el lote no usa `AfipService` y no hay restricción única → **Plan 075** |
| 5 | **Presupuesto / PRE** (`condic = 2`) | `punto` = **`sucursal_id`** de la sucursal emisora; `numero` = **correlativo propio del sistema** para ese punto | ⚠️ Existe, con los mismos problemas → **Plan 075** |
| 6 | **Nota de Crédito** | `condic = 1`: serie fiscal con CAE. `condic = 2`: tipo **`NCI`** (Nota de Crédito Interna), `punto = sucursal_id` y **serie propia**, independiente de la del PRE | ⚠️ → **Plan 075** |

**La diferencia de fondo entre 4 y 5:** la serie fiscal la gobierna ARCA y el sistema la acompaña; **la del PRE la gobierna enteramente el sistema**, sin ninguna autoridad externa que la valide. Es la que más protección necesita, justamente porque nadie más la controla.

**La cadena de trazabilidad del módulo** — es la que permite emitir la Nota de Crédito con todos los datos:

```
PEDIDO Nº ──► COMPROBANTE Nº (Factura o PRE) ──► HOJA DE RUTA (muestra ambos)
                                                        │
                                          RECEPCIÓN DE DEVOLUCIONES Nº
                                          (reparto + pedido + comprobante)
                                                        │
                                                  NOTA DE CRÉDITO Nº
```

Cada eslabón referencia al anterior por su número. Por eso la Hoja de Ruta debe imprimir **el número de pedido junto al del comprobante** (§7.6): es el dato con el que el repartidor y el depósito arman la devolución.

Los tres documentos nuevos se construyen desde el arranque sobre `core.ContadorDocumento` y `siguiente_numero()`, que **ya bloquea con `select_for_update()`** y está probado. Y los tres se incorporan a **`auditar_correlativos()`**, de modo que el sistema pueda demostrar su propia integridad sin trabajo manual.

Los tres documentos que ya existen (Factura, PRE, NC) arrastran un problema de numeración que **excede a este módulo y afecta a todo el ERP**: se trata en el [Plan 075](075_integridad_numeracion_comprobantes_venta.md), con aprobación separada.

**El par de control de este módulo:** la **Nota de Crédito** (documento fiscal, va al cliente) y la **Recepción de Devoluciones** (documento interno del depósito, numerado). Uno dice qué se le acreditó al cliente; el otro, qué volvió físicamente al depósito. **Deben conciliar**, y esa conciliación es el control de las devoluciones.

### 4.3 — Usuario ≠ Persona del negocio

El vendedor, el repartidor y el cobrador se modelan en una tabla propia (`Personal`, §5.A), **no como un atributo del usuario del sistema**. La distinción es:

| | `auth_user` + `usuarios.Perfil` | `distribucion.Personal` |
|---|---|---|
| Qué representa | **Quién opera el sistema**: credenciales, empresas habilitadas, permisos | **Quién es la persona en el negocio**: vendedor, repartidor, cobrador |
| Pregunta que responde | ¿Puede entrar y qué puede hacer? | ¿De quién es esta cartera? ¿Quién llevó este reparto? |
| Ciclo de vida | Alta/baja de acceso | Alta/baja laboral, comisión, zona |

**Tres razones, en orden de peso:**

1. **No todo el personal opera el sistema.** El repartidor trabaja con la Hoja de Ruta en papel y puede no tocar una pantalla en su vida; el "MAXIMILIANO + ROMINA" del reparto 8638 tiene que figurar en el documento igual. Modelarlo como usuario obligaría a **crear credenciales para gente que nunca va a entrar**, que es superficie de ataque a cambio de nada. Por eso `Personal.usuario` es **nullable**: el vendedor con celular lo tiene, el repartidor no.
2. **Un vendedor tiene atributos de negocio** —comisión, zona, legajo, fecha de baja, código del sistema anterior— que **no tienen nada que ver con la autenticación**. Ponerlos en `Perfil` sería meter campos de un rubro en un modelo genérico, exactamente lo que el proyecto evita con `ExtensionArmeria`.
3. **La cartera y el reparto necesitan una FK estable** a una entidad que existe aunque la persona pierda el acceso al sistema.

> **Matiz sobre "no ensuciar la tabla usuarios":** el proyecto ya resuelve eso con `usuarios.Perfil`, que es OneToOne con `User` y donde ya viven los `permiso_*`. Un `es_vendedor` ahí no tocaría `auth_user`. Así que la tabla propia **no se justifica por eso**, sino por las tres razones de arriba — sobre todo la primera, que es la que decide.

**Lo que NO se toca:** `Venta.vendedor` y `Preventa.vendedor` siguen apuntando a `User` como hoy, porque los usan los filtros y reportes de otras actividades (`views.py:1063`, `views_reportes.py:124`, `ventas_reportes_excel.py`). En distribución **el vendedor de una venta se obtiene a través de su pedido**, que es donde vive el dato: una sola fuente de verdad, y cero migración sobre datos existentes.

---

## 5. Modelo de datos

### 5.A. App nueva: `distribucion`

```
distribucion/
    models.py     -> Personal, Vehiculo, ZonaReparto, DiaVisita, CarteraVendedor,
                     Reparto, RepartoParada, MotivoDevolucion,
                     RecepcionDevolucion, RecepcionDevolucionItem,
                     NotaCreditoDistribucion, ExtensionPedidoDistribucion
    services/     -> precios.py, credito.py, asignacion.py, consolidado.py,
                     reparto.py, cobranza_fifo.py, devoluciones.py
    views*.py     -> pedidos (PC), pedidos_movil, asignacion, repartos,
                     cobranzas, devoluciones
    templates/
```

> `ExtensionDistribuidora` (§5.C) es la excepción: va en la app `facturacion`, junto a `ExtensionArmeria`, para que la tabla quede como `facturacion_extensiondistribuidora`.

#### `Personal` — vendedores, repartidores y cobradores

Tabla propia, **no un atributo de `Usuario`**. El fundamento está en §4.3.

| Campo | Tipo | Nota |
|-------|------|------|
| `empresa` | FK | |
| `usuario` | OneToOne User, **null** | **Sólo si la persona opera el sistema.** El vendedor con celular lo tiene; el repartidor que trabaja con la hoja de ruta en papel, no |
| `codigo` | Int | correlativo por empresa, el que se usa en pantalla y en los reportes |
| `nombre` | Char | "JUAN", "MAXIMILIANO", "ROMINA" — como figura en el papel |
| `documento`, `telefono` | Char, null | |
| `es_vendedor` | Bool | |
| `es_repartidor` | Bool | |
| `es_cobrador` | Bool | |
| `comision_porcentaje` | Decimal(5,2), default 0 | |
| `zona` | FK ZonaReparto, null | zona habitual |
| `activo` | Bool | |
| `fecha_alta`, `fecha_baja` | Date, null | |
| `codigo_anterior` | Char, indexado, null | código del vendedor en el sistema VFP |

Los tres roles son **booleanos independientes y acumulables**: en una distribuidora chica es habitual que la misma persona tome pedidos, reparta y cobre. Tres tablas separadas obligarían a cargar a esa persona tres veces.

#### `Vehiculo`
`empresa`, `sucursal`, `patente`, `descripcion`, `capacidad_kg`, `refrigerado` (Bool, default True), `activo`.

#### `ZonaReparto`
`empresa`, `nombre` (ej. "SAN CAYETANO"), `orden`, `activa`.

#### `DiaVisita`
`cliente` FK, `dia_semana` (1-7), `frecuencia` (semanal / quincenal).

#### `CarteraVendedor`
`empresa`, `vendedor` **FK Personal** (`limit_choices_to={'es_vendedor': True}`), `cliente` FK, `activa`.
**`unique_together = (empresa, cliente)`** — un cliente tiene **un solo vendedor**, porque es el responsable directo de su saldo. De ahí sale el listado de saldos agrupado por vendedor (§7.8).

#### `MotivoDevolucion` — tipificación para el análisis estadístico
| Campo | Tipo | Nota |
|-------|------|------|
| `empresa` | FK | |
| `codigo`, `descripcion` | Char | |
| `momento` | Char | PRE_CARGA (antes de salir) / EN_ENTREGA (en la puerta) / AMBOS |
| `sugiere_apto_reventa` | Bool, default True | **precarga el `apto_reventa` del ítem de la recepción.** Un envase roto no vuelve al stock vendible; un negocio cerrado sí |
| `requiere_observacion` | Bool, default False | para los motivos genéricos, donde el dato real está en el texto libre |
| `activo` | Bool | |

Catálogo editable, **siempre acompañado de observación libre**: el motivo estandariza la estadística, la observación captura lo que sólo el repartidor sabe.

**Catálogo inicial propuesto.** Cubre lo que se ve en un reparto de lácteos; se agrega lo que falte a medida que aparezca en la operación real.

| Código | Descripción | Momento | Apto reventa |
|---|---|---|---|
| `CLIENTE_ANULO` | El cliente anuló el pedido | PRE_CARGA | ✅ |
| `CLIENTE_REDUJO` | El cliente redujo el pedido | PRE_CARGA | ✅ |
| `PEDIDO_DUPLICADO` | Pedido cargado dos veces | PRE_CARGA | ✅ |
| `ERROR_DE_CARGA` | Error al cargar el pedido (producto o cantidad) | AMBOS | ✅ |
| `ERROR_FACTURACION` | Comprobante mal emitido (datos, precio) | AMBOS | ✅ |
| `NEGOCIO_CERRADO` | El negocio estaba cerrado | EN_ENTREGA | ✅ |
| `CLIENTE_AUSENTE` | No estaba quien recibe | EN_ENTREGA | ✅ |
| `NO_TENIA_DINERO` | No reunió el cobro mínimo exigido | EN_ENTREGA | ✅ |
| `RECHAZA_PRODUCTO` | No lo quiere / dice no haberlo pedido | EN_ENTREGA | ✅ |
| `RECHAZA_PRECIO` | No acepta el precio facturado | EN_ENTREGA | ✅ |
| `DIRECCION_INCORRECTA` | No se ubicó el domicilio | EN_ENTREGA | ✅ |
| `NO_SE_LLEGO` | No se alcanzó a pasar en el recorrido | EN_ENTREGA | ✅ |
| `FALTANTE_DE_CARGA` | No subió al vehículo | EN_ENTREGA | ✅ |
| `PRODUCTO_DAÑADO` | Envase roto o mercadería en mal estado | AMBOS | ❌ |
| `PROXIMO_A_VENCER` | Vencimiento corto, el cliente no lo acepta | EN_ENTREGA | ❌ |
| `CADENA_DE_FRIO` | Temperatura fuera de rango | AMBOS | ❌ |
| `OTROS` | Otro motivo *(observación obligatoria)* | AMBOS | ✅ |

Los tres motivos con ❌ son los que sacan la mercadería del stock vendible: por eso el `apto_reventa` se precarga desde el motivo en lugar de dejarlo al criterio del que carga la recepción. `PROXIMO_A_VENCER` y `CADENA_DE_FRIO` son específicos del rubro y conviene tenerlos separados desde el inicio: agrupados bajo "producto dañado" se pierde la información que después explica una merma.

#### `Reparto` — **documento numerado**
| Campo | Tipo | Nota |
|-------|------|------|
| `empresa`, `sucursal` | FK | |
| `punto` | Int | punto de emisión = **`sucursal_id`**, la sucursal que arma el reparto |
| `numero` | BigInt | **correlativo vía `ContadorDocumento.REPARTO`** — el "Reparto: 8639" del papel |
| `fecha` | Date, indexado | fecha operativa de salida |
| `vehiculo` | FK Vehiculo, null | |
| `responsables` | **M2M Personal** (`es_repartidor=True`) | soporta "MAXIMILIANO + ROMINA" |
| `zona` | FK ZonaReparto, null | |
| `estado` | Int | 0 Armado / 1 Cerrado (salió) / 2 Rendido / 3 Anulado |
| `version_impresion` | Int, default 1 | se incrementa en cada reimpresión por NC pre-carga (§7.10) |
| `caja_sesion` | FK CajaSesion, null | sesión de la **caja recaudadora** |
| `observaciones` | Text | |

`UniqueConstraint (empresa, punto, numero)`. Un reparto anulado **conserva su número**: no genera hueco.

#### `RepartoParada` (una fila por comprobante)
| Campo | Tipo | Nota |
|-------|------|------|
| `reparto` | FK, related_name `paradas` | |
| `pedido` | FK Preventa | **el pedido que originó el comprobante.** Es el eslabón que la Recepción de Devoluciones necesita (§4.2) |
| `venta` | FK Venta | comprobante **ya emitido** (condic 1 o 2) |
| `orden` | Int | orden de descarga; el reporte sale alfabético, pero se puede reordenar |
| `saldo_anterior` | Decimal | **congelado** al cerrar el reparto (el "Saldo CC" del papel) |
| `saldo_disponible` | Decimal | **congelado**, con signo: `limite − saldo` posterior a la facturación |
| `cobro_minimo` | Decimal | **congelado** = `max(0, −saldo_disponible)` |
| `estado_entrega` | Int | 0 Pendiente / 1 Entregada / 2 No entregada |
| `observacion_repartidor` | Text | libre |

> **Por qué se congelan los tres importes:** el papel es la foto de un momento. Si el reporte los recalculara al reimprimirse, un cobro posterior cambiaría el número y el control contra la firma del cliente se rompería.

### 5.B. `ExtensionPedidoDistribucion` (OneToOne con `Preventa`)

| Campo | Tipo | Nota |
|-------|------|------|
| `preventa` | OneToOne Preventa | |
| `vendedor` | **FK Personal** (`es_vendedor=True`) | quién tomó el pedido. **Es la fuente de verdad del vendedor de la operación**: la venta llega a su vendedor a través del pedido, sin duplicar el dato (§4.3) |
| `punto` | Int | punto de emisión = **`sucursal_id`**, la sucursal que toma el pedido |
| `numero` | BigInt, indexado | **correlativo vía `ContadorDocumento.PEDIDO`** (§4.2) |
| `fecha_entrega` | Date, indexado | `Preventa.fecha` es `auto_now_add` (fecha de carga) |
| `origen` | Char | MOVIL / PC_TELEFONICO / PLANILLA_PAPEL |
| `condic_destino` | Int (1 o 2) | con qué condición se facturará |
| `zona` | FK ZonaReparto, null | |
| `hora_carga` | DateTime, indexado | **define la prioridad en la asignación de stock escaso** (§7.3) |
| `alerta_stock` | Bool | stock ajustado al tomarse: pedido **sujeto a disponibilidad** |
| `alerta_credito` | Bool | informativa |
| `observaciones` | Text | |

`UniqueConstraint (preventa.empresa, punto, numero)`. El número se asigna **al confirmar** el pedido, no en borrador, para no dejar huecos — misma regla que el resto de los documentos del sistema.

> **Por qué el número no va en `Preventa`:** el modelo es compartido con otras actividades que hoy no numeran pedidos. Poner la serie en la extensión mantiene la regla del proyecto de no contaminar un modelo común con campos de un rubro. Si más adelante se decide que **todo** pedido del ERP lleve numeración, se promueve el campo a `Preventa` con una migración de datos simple.

### 5.C. `ExtensionDistribuidora` — app `facturacion`, tabla `facturacion_extensiondistribuidora`

| Campo | Tipo | Nota |
|-------|------|------|
| `cliente` | OneToOne ClienteProveedor, related_name `distribuidora` | |
| `clasificacion` | Char | **descriptiva**: agrupa clientes para análisis y filtros. **No calcula el coeficiente** |
| `coeficiente_mayorista` | Decimal(10,4) | se carga **siempre a mano**, cliente por cliente |
| `zona` | FK ZonaReparto, null | |
| `bloqueado_credito` | Bool, default False | corte manual de la administración |

**Precio de venta al cliente de reparto:**

```
precio_unitario = Producto.precio_total × ExtensionDistribuidora.coeficiente_mayorista
```

- La base es **`precio_total`**, el precio de lista **con IVA incluido**: el que se muestra en los cuatro reportes y el que, sumado, conforma el total facturado que consume el crédito disponible.
- **`cto_rep` no interviene en la venta.** Es el costo de reposición, al que se le aplica el `margen` para definir el precio cuando se carga una compra: es una entrada del circuito de compras.
- Un solo coeficiente porque **todos los clientes de reparto son revendedores**.
- El servicio `distribucion/services/precios.py` centraliza el cálculo: ninguna vista calcula precios por su cuenta.

### 5.D. `NotaCreditoDistribucion` (OneToOne con la `Venta` de tipo NC)

Satélite que le da a la Nota de Crédito el contexto operativo que el circuito necesita, sin tocar `Venta`:

| Campo | Tipo | Nota |
|-------|------|------|
| `nota_credito` | OneToOne Venta | la NC emitida |
| `venta_origen` | FK Venta | el comprobante que se acredita |
| `parada` | FK RepartoParada, null | |
| `motivo` | FK MotivoDevolucion | **obligatorio** |
| `observacion` | Text | libre, del repartidor |
| `momento` | Char | PRE_CARGA / EN_ENTREGA |
| `recepcion` | FK RecepcionDevolucion, null | el documento con el que la mercadería volvió al depósito |

**El motivo y la observación se imprimen en el detalle de la NC**, para que el documento explique por sí solo por qué existe.

### 5.E. `RecepcionDevolucion` — documento propio numerado, espejo físico de las NC

Es al reparto lo que el **Informe de Recepción** es a la compra: el documento con el que **el depósito declara qué volvió**, con su propia serie auditable.

| Campo | Tipo | Nota |
|-------|------|------|
**Se emite una Recepción de Devoluciones por cada PEDIDO devuelto**, no una por reparto. El repartidor entrega la mercadería en el depósito y, pedido por pedido, se va chequeando contra lo que la Hoja de Ruta trae marcado y generando el Informe correspondiente.

| Campo | Tipo | Nota |
|-------|------|------|
| `empresa`, `sucursal` | FK | |
| `punto` | Int | `sucursal_id` de la sucursal que recibe |
| `numero` | BigInt | **correlativo vía `ContadorDocumento.RECEPCION_DEVOLUCION`** |
| `parada` | FK RepartoParada | **vínculo con el pedido devuelto.** De acá salen, en un solo salto, el **N° de Pedido**, el **N° de Comprobante** y el cliente |
| `reparto` | FK Reparto | desnormalizado desde la parada, para filtrar y auditar por reparto sin JOIN |
| `fecha` | Date, indexado | |
| `recibido_por` | FK User | encargado de depósito que cuenta — **es User porque opera el sistema** |
| `entregado_por` | **FK Personal**, null | repartidor que devuelve — **es Personal porque puede no operar el sistema** |
| `estado` | Int | 0 Borrador / 1 Confirmada / 2 Anulada |
| `nota_credito` | FK Venta, null | la NC emitida a partir de esta recepción |
| `observaciones` | Text | |

`UniqueConstraint (empresa, punto, numero)` y `UniqueConstraint (parada)` **sólo entre las no anuladas**: un pedido devuelto genera una recepción, y si se anula puede rehacerse.

#### `RecepcionDevolucionItem`
`recepcion` FK, `producto` FK, `cantidad` (lo que efectivamente volvió), `motivo` FK MotivoDevolucion, `apto_reventa` Bool (default True, excepción para mercadería dañada), `observacion`.

**Lo que imprime el documento:** **N° de Recepción**, N° de Reparto, **N° de Pedido**, **N° de Comprobante** (Factura o PRE), cliente, repartidor que entrega y encargado que recibe; y el detalle de artículos con `ID | código anterior`, cantidad devuelta y motivo. Con ese papel el depósito tiene todo lo necesario para emitir la Nota de Crédito, sin reconstruir nada.

> **Por qué una por pedido y no una por reparto:** la devolución se acredita a un cliente concreto mediante una Nota de Crédito que se emite contra **un** comprobante. Un documento por pedido mantiene la correspondencia **1 Pedido → 1 Comprobante → 1 Recepción → 1 NC**, que es lo que hace posible conciliar sin desarmar totales. Un documento por reparto obligaría a repartir después sus renglones entre varios clientes, que es exactamente donde se pierde la trazabilidad.

**Al confirmar la recepción, el stock reingresa.** Los vehículos son refrigerados y el producto rechazado no bajó del camión (o bajó unos minutos), así que **no hubo interrupción de la cadena de frío** y vuelve a disponible. `apto_reventa` queda como excepción para mercadería dañada, que no debe volver al stock vendible.

**Conciliación NC ↔ Recepción:** reporte que confronta lo acreditado al cliente con lo efectivamente recibido en el depósito. Un descalce señala mercadería que se acreditó pero no volvió, que es exactamente lo que este par de documentos existe para detectar.

### 5.F. Campos nuevos en modelos existentes

Todos **nullables o con default**, ninguno destructivo:

**`productos.Producto`**
| Campo | Tipo | Por qué |
|-------|------|---------|
| `peso_unitario_kg` | Decimal(10,3), default 0 | **peso por unidad de venta**; columna "Kgs" del Consolidado |
| `unidad_venta` | Char | UNIDAD / BULTO / KG — define a qué se refiere el peso |
| `unidades_por_bulto` | Decimal(10,2), default 0 | el vendedor pide "3 cajones", no "36 unidades" |
| `codigo_anterior` | Char, indexado, null | código del sistema VFP. Mismo patrón que `ClienteProveedor.codigo_anterior` |

**Impresión de códigos:** todos los listados y comprobantes del módulo muestran **`ID | código anterior`** en dos columnas, para que vendedores y facturadores se familiaricen con el código nuevo sin perder el que ya conocen. La búsqueda rápida **resuelve indistintamente por cualquiera de los dos**.

**`facturacion.Venta`**
| Campo | Tipo | Por qué |
|-------|------|---------|
| `condicion_venta` | Char (CONTADO / CTA_CTE), null | Es el "Condición Venta: Contado" que la propia factura imprime. Se resuelve al facturar (§7.4). Queda `null` fuera de la actividad DISTRIBUIDORA |

> **Por qué es un campo y no se deriva:** la regla del proyecto dice que contado vs. cuenta corriente sale de `saldo`/`cobrado` y nunca de `condic` — y se respeta, `condic` no se toca. Pero acá el comprobante se emite **de madrugada y se cobra a la tarde en la casa del cliente**: en ese intervalo una venta de contado y una de cuenta corriente tienen idéntico `saldo = total`. La condición no es derivable justo en el intervalo en que la hoja de ruta la necesita impresa.

**`tesoreria.Caja`** — agregar `('R', 'Recaudadora / Repartidor')` a `TIPO_CAJA` (fundamento en §7.9).

**`productos.StockSucursal`** — agregar `comprometido` Decimal(15,2) default 0: cantidad tomada en pedidos aún no facturados. **Valor derivado y materializado**, igual que `cantidad`.

**`core.ContadorDocumento`** — agregar a `TIPOS_DOCUMENTO`: `PEDIDO`, `REPARTO`, `RECEPCION_DEVOLUCION`. (`VENTA_PRE` y `VENTA_NCI` corresponden al Plan 075.)

**`core/services/numeracion.auditar_correlativos()`** — agregar los tres documentos nuevos a la lista de `fuentes`, para que la auditoría de integridad los cubra desde el día uno.

**`facturacion.ClienteProveedor`** — **sin cambios**.

---

## 6. Diagrama del circuito

```
 DÍA 1 — LA CALLE
 ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
 │ Móvil (vendedor) │   │ PC (telefónico)  │   │ Planilla papel   │
 └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘
          └──────────────────────┼──────────────────────┘
                                 ▼
              [1] PEDIDO Nº ....  + stock COMPROMETIDO
                                 │
 ──────────────────────────────  │  ─────────────────────────────────
 DÍA 2, 06:00 — ADMINISTRACIÓN   ▼
        REPORTE DE FALTANTES ──► ASIGNACIÓN FINAL (orden de llegada)
                                 ▼
        FACTURACIÓN POR LOTE  ──► CONTROL DE CRÉDITO
                                 │   SALDO DISPONIBLE (puede ser < 0)
                                 │   → COBRO MÍNIMO
                                 ├──► [4] FACTURA Nº ....  (CAE)
                                 └──► [5] PRE Nº ....      (no fiscal)
                                 ▼
                      [2] HOJA DE RUTA / REPARTO Nº ....
                  ┌──────────────┴──────────────┐
                  ▼                             ▼
       Consolidado de Artículos        Hoja de Ruta por cliente
                  │
      ┌───────────┴── el cliente anula antes de salir:
      │               [6] NOTA DE CRÉDITO + reimpresión (v2, v3…)
      ▼
 ──────────────────────────────────────────────────────────────────
 DÍA 2, A LA VUELTA
   ENTREGA ──► entregada
        └────► no entregada ──► se MARCA en la Hoja de Ruta
                                 (motivo + observación)
                                        │
                                        ▼
                      [3] RECEPCIÓN DE DEVOLUCIONES Nº ....
                          UNA POR CADA PEDIDO devuelto
                          el depósito CUENTA lo que volvió
                                        │
                                        ├──► stock reingresa
                                        ▼
                              [6] NOTA DE CRÉDITO Nº .... (CAE)
                          ── se concilian entre sí ──
        ▼
   COBRANZA ──► efectivo ────► PRE (condic 2) más antiguos primero,
             │                  y recién después condic 1
             └─► trazables ───► SIEMPRE condic 1
                     ▼
            Recibos (uno por condic) ──► Caja Recaudadora
                     ▼
            RENDICIÓN ──► RetiroCaja ──► Caja Tesorería

 [n] = documento con numeración correlativa propia y auditable (§4.2)
```

---

## 7. Diseño detallado por proceso

### 7.1 — Toma de pedidos (proceso 1)

Tres canales, **un solo modelo** (`Preventa` + extensión):

**a) Móvil del vendedor (prioridad alta).** Vista mobile-first HTMX, sin app nativa:
1. Cliente por typeahead (código o nombre), limitado a su cartera y a `session['empresa_id']`.
2. Panel fijo: **Límite**, **Saldo**, **Saldo disponible**. En rojo si es negativo. Información para vender, no un bloqueo.
3. Carga renglón por renglón: `[código] [cantidad] ↵`, con precio ya afectado por el coeficiente. El código resuelve por `id` **o** por `codigo_anterior`. Si no lo recuerda, typeahead por descripción (patrón Typeahead + Lupa obligatorio).
4. Cada renglón muestra el stock disponible **en línea**; si la cantidad lo deja ajustado se marca en ámbar **sin bloquear**, queda `alerta_stock` y el pedido se registra como **sujeto a disponibilidad**. Es responsabilidad del vendedor advertirlo al cliente.
5. Total en vivo con formato es-AR (`.fInputAR` / `|formato_ar`).
6. Al confirmar, el pedido **toma su número correlativo** y se le informa al vendedor: es el número con el que el cliente puede reclamar.

**Conectividad: online-only en fase 1.** La planilla de papel es el plan B.

**b) PC en el negocio (telefónico).** Misma pantalla en escritorio: código + Tab + cantidad + Enter. Sin mouse.

**c) Planilla manual imprimible.** PDF por vendedor y por día: encabezado con vendedor/fecha/zona; bloque por cliente de la cartera del día (`DiaVisita`) con código, nombre, **saldo y disponible impresos**; grilla de artículos con **ID | código anterior**, ordenada por código, con columna de cantidad en blanco.

### 7.2 — Captura / edición (proceso 2)

Listado de pedidos con filtros por número, fecha, vendedor, zona, estado y `condic_destino`; edición mientras no esté facturado. Un pedido anulado **conserva su número**.

### 7.3 — Reporte de faltantes y asignación final de stock (proceso 3)

Como la toma de pedidos es **en línea**, el vendedor ve el stock actual y el riesgo de sobreventa es bajo: se reduce a la demora entre consultar y grabar, y a pedidos casi simultáneos. **El pedido queda siempre sujeto a disponibilidad** cuando el stock está ajustado. Aun así, entre el día 1 y las 06:00 del día 2 los pedidos compiten por el mismo stock.

**Reporte de alerta — pedidos que no pueden cumplirse completamente:**

| ID \| Cód. ant. | Producto | Stock disponible | Total pedido | **Déficit** | Desglose |
|---|---|---|---|---|---|
| 3002 \| 3002 | YOGUR X 900 VAINILLA | 60 | 101 | **−41** | Pedido 812 · ROMANO LILIANA · 20 · JUAN · 14:32 … |

- Una fila por producto en déficit, expandible al detalle **por pedido y por cliente**, con cantidad, vendedor y **hora de carga**. Ordenable y exportable a PDF y Excel.

**Pantalla de asignación final:** el usuario autorizado (`permiso_distribucion_asignar_stock`) reparte el stock escaso editando cantidades, con el saldo a asignar visible y validación de que no se asigne más de lo que hay.

**Criterio de sugerencia: orden de llegada del pedido** (`hora_carga` ascendente) — el que pidió primero se sirve primero, y el faltante lo absorben los últimos. Es el criterio que se le puede explicar a un vendedor sin discusión. La pantalla permite ajustar a mano.

Cada ajuste queda registrado (quién, cuándo, cantidad original y asignada). La facturación por lote se habilita con la asignación cerrada.

### 7.4 — Facturación y control de crédito (proceso 4) — **el corazón del módulo**

Facturación **masiva por lote** al arranque del día, en `transaction.atomic()` con `select_for_update()` sobre el cliente, el stock y el contador. Extiende el patrón de `facturacion_lote_service.py`.

**La regla del saldo disponible negativo** (fórmula única de todo el control):

```
saldo_disponible = limite − saldo        (posterior a la facturación de esta carga)
cobro_minimo     = max(0, −saldo_disponible)
```

Ejemplo: límite 100.000, saldo previo 60.000, carga nueva 50.000 → disponible antes 40.000; saldo posterior 110.000 → **saldo disponible = −10.000**. El comprobante sale **CUENTA CORRIENTE**, la hoja de ruta muestra **Saldo Disponible: $ -10.000**, y **el repartidor no puede dejar la mercadería sin cobrar al menos $ 10.000**.

La formulación **absorbe todos los casos sin condicionales especiales**:

| Situación | Saldo disponible | Cobro mínimo | Condición |
|---|---|---|---|
| Entra holgado en el límite | positivo | 0 | CUENTA CORRIENTE |
| Se pasa parcialmente | negativo parcial | el excedente | CUENTA CORRIENTE |
| `limite = 0` (sólo contado) | −total | **el total** | CONTADO |
| `bloqueado_credito` | se fuerza −total | el total | CONTADO |

`condicion_venta` queda como derivado del mismo cálculo, congelado en el comprobante: `CONTADO` si `cobro_minimo ≥ total`, `CTA_CTE` en cualquier otro caso.

**Emisión** según `condic_destino`: `1` → Factura fiscal con CAE, formato hoja 1. `2` → PRE, numeración propia, formato hoja 2 con **"COMPROBANTE NO VÁLIDO COMO FACTURA"** y con **ID | código anterior**.

Se descarga el stock, se libera el `comprometido`, `Preventa.estado = 3`. Reglas inflexibles respetadas: el asiento **hereda** `condic`; el Libro IVA se puebla sólo con `condic in (1, 3)`, así que el PRE nunca lo alimenta.

### 7.5 — Consolidado de Artículos (proceso 5)

Reporte agregado sobre las ventas **vigentes** del `Reparto`, replicando la hoja 4:

| ID \| Cód. ant. | Artículo | Cantidad | Kgs |
|----|----------|----------|-----|

- Agrupado por producto, ordenado por código. `Kgs = Σ (cantidad × producto.peso_unitario_kg)`.
- Totales generales de unidades y kilos al pie. Alerta si supera `Vehiculo.capacidad_kg`.
- PDF (reutilizando `facturacion/services/reportes_pdf.py`) y Excel.
- Encabezado con `Reparto: <numero>`, responsables, fecha y **versión de impresión**.

### 7.6 — Hoja de Ruta (proceso 6)

Reporte por `Reparto`, **ordenado alfabéticamente por cliente**, sobre comprobantes vigentes.

Por parada:
- **N° de Pedido** y **N° de Comprobante** (Factura o PRE) — los dos, juntos. Es el eslabón de la cadena de trazabilidad (§4.2): con esos dos números el repartidor y el depósito arman después la Recepción de Devoluciones y la Nota de Crédito, sin tener que reconstruir nada.
- Código y razón social del cliente, domicilio.
- **Condición de venta**; **saldo anterior**; **total de la carga**.
- **Saldo Disponible con signo** (`$ -10.000`, destacado cuando es negativo).
- Detalle de artículos con **ID | código anterior**, descripción, cantidad, precio y total.
- Espacio para importe cobrado, **medios de pago** y **firma del cliente**.
- **Casilla de DEVOLUCIÓN** con espacio para motivo y observación. Es la marca que el repartidor hace en la calle y que después, en el depósito, dispara el chequeo pedido por pedido y la emisión del Informe de Recepción de Devoluciones (§7.10).

Al cerrar el reparto (estado 1) se congelan los importes y se imprime.

### 7.7 — Cobranzas del repartidor (proceso 7) — segmentada por medio de pago

**Invariantes del módulo:**

> 1. Los medios con **trazabilidad externa** (transferencia, cheque electrónico, tarjeta) se aplican **siempre a `condic = 1`**. Un movimiento que el banco registra no puede cancelar una operación que no existe para el fisco.
> 2. El **efectivo** se imputa **primero al saldo más antiguo de `condic = 2` (PRE)**, y **sólo una vez cubiertos todos los PRE** continúa con `condic = 1`.

**Algoritmo de `cobranza_fifo.py`:**
1. Se carga lo que trajo el repartidor **desglosado por medio de pago** ("$40.000 efectivo, $66.000 cheque").
2. **Tramo trazable** → FIFO restringido a `condic = 1`. El excedente queda como **saldo a favor en el circuito fiscal** (anticipo).
3. **Tramo efectivo** → FIFO sobre `condic = 2`; agotados los PRE, continúa sobre `condic = 1`.
4. La venta del propio reparto entra en el FIFO por su fecha, la más reciente: se cancela al final, salvo que sea el único comprobante abierto.
5. Se emiten **dos recibos como máximo**, uno por `condic`, cada uno con sus `ReciboAplicacion` y su asiento. El usuario carga un solo importe; el corte lo hace el sistema.

**Las dos lentes sobre el saldo del cliente:**

| Lente | Qué muestra | Dónde se usa |
|-------|-------------|--------------|
| **Contable / fiscal** | Sólo `condic = 1`, incluido el saldo a favor por excedente trazable | Contabilidad, estados contables, DDJJ |
| **Operativa** | **Saldo combinado 1 + 2**, netos entre sí | Hoja de ruta, límite de crédito, listado de cobranza, pantalla del vendedor |

Cada recibo genera su `MovimientoCaja` con `MovimientoCajaDetalle` por medio de pago, en la caja recaudadora del reparto.

### 7.8 — Listado de saldos pendientes (proceso 8)

Reporte "Clientes a cobrar", **agrupado por vendedor** (responsable directo del saldo de su cartera), filtrable por zona, día de visita y antigüedad:

| Cliente | Zona | Límite | Saldo operativo (1+2) | Disponible | Comprobantes con saldo (nro, fecha, total, saldo, días, condic) |

- Composición del saldo abierta por comprobante, distinguiendo `condic` 1 y 2 y marcando cuáles **sólo se pueden cobrar en efectivo**.
- Antigüedad en tramos (0-30 / 31-60 / 61-90 / +90) y **totales por vendedor**.
- PDF (para que el vendedor lo lleve) y Excel. Filtro de condición obligatorio.

### 7.9 — Caja recaudadora y rendición (proceso 9)

**Por qué un tipo `'R'` y no la caja mostrador `'M'`:** la mostrador se abre y cierra por **turno de cajero**, con arqueo ciego, en un puesto fijo. La recaudadora se abre y cierra por **reparto**, la maneja alguien que está en la calle, y su cierre se concilia contra la hoja de ruta. Dos reglas de negocio distintas sobre la misma estructura; un `tipo` explícito evita ramificar el código de la mostrador con condicionales.

1. Al cerrar el `Reparto` se abre una `CajaSesion` sobre la caja recaudadora del repartidor.

> **Consecuencia de §4.3 que conviene tener a la vista:** `CajaSesion.usuario` es un `User`, y el repartidor puede no serlo. La atribución de la recaudación **no pasa por la sesión de caja sino por el `Reparto`**, que es el que vincula la sesión con sus `responsables` (Personal). En la práctica el administrativo abre la sesión y el reparto dice de quién es la plata. Es, además, otra razón por la que la caja recaudadora se abre por reparto y no por cajero.

2. Los recibos del proceso 7 impactan en esa sesión.
3. **Rendición total a Tesorería** con el `RetiroCaja` existente, en dos pasos: el repartidor declara → el tesorero cuenta y acepta → la diferencia genera su asiento automático. La rendición del reparto aparece en **la misma bandeja de recepción** que las de mostrador: el paso 2 no tiene código propio.
   - *Implementación (v11):* el traslado usa **`cta_caja_mostrador` como cuenta de ORIGEN**, que es la cuenta de efectivo fuera de Tesorería. La recaudadora no tiene parámetro contable propio; agregarlo sólo tendría sentido si la empresa quisiera ver por separado en el balance la plata que está en la calle.
4. Cierre del reparto (estado 2 = Rendido) con el cuadro **esperado vs. cobrado vs. rendido** por medio de pago, y el detalle de las NC emitidas con sus motivos.

### 7.10 — Notas de Crédito y Recepción de Devoluciones (proceso nuevo)

**Definición del usuario:** en los tres casos —el cliente no recibe el reparto, no se le puede entregar por estar cerrado, o lo anula antes de que salga pero ya estaba facturado— **se emite NOTA DE CRÉDITO anulando la Factura, con el CAE correspondiente.**

**Caso A — el cliente anula antes de que salga el camión.**
1. Se emite la **NC** contra el comprobante, con `NotaCreditoDistribucion` (motivo + observación, `momento = PRE_CARGA`).
2. La mercadería nunca se cargó: el stock vuelve a disponible directamente, **sin Recepción de Devoluciones** (no hay nada que recibir).
3. Se quita la parada del reparto, se incrementa `version_impresion` y se **reimprimen la Hoja de Ruta y el Consolidado de Artículos**, porque esos productos ya no se cargan. La versión impresa evita que quede circulando el papel viejo.

**Caso B — el cliente no recibe la mercadería (cerrado, sin dinero, rechazo).**
El orden importa: **primero se cuenta lo que volvió, después se acredita.** Sólo se emite Nota de Crédito por mercadería que efectivamente reingresó al depósito.

1. **En la calle:** el repartidor **marca en la Hoja de Ruta** el pedido que no se entregó, con el motivo y la observación.
2. **En el depósito:** el repartidor entrega la mercadería y, **pedido por pedido**, se chequea contra lo marcado en la Hoja de Ruta y se genera **una Recepción de Devoluciones por cada pedido** (§5.E), donde el encargado **cuenta lo que efectivamente volvió**.
3. **El stock reingresa con la Nota de Crédito** (paso 4), no al confirmar la recepción. *Corregido en la implementación (v10):* `productos.services.stock_service` **deriva** el stock de los COMPROBANTES, y la NC ya invierte el movimiento por el `signo = -1` de su tipo; si la recepción también moviera stock se contaría dos veces. La recepción es el **control físico**; la NC es el **hecho que mueve el inventario**. Como ambos pasos ocurren en el mismo momento operativo —el depósito cuenta y acredita seguido—, la disponibilidad se recupera igual de rápido. Vehículos refrigerados, sin interrupción de cadena de frío.
   - *Consecuencia conocida:* la mercadería marcada como **no apta para reventa** vuelve igual al stock, porque la NC acredita todo lo devuelto —el cliente no paga lo que devolvió, esté roto o no—. Darla de baja es un **ajuste de inventario**, término que `stock_service` todavía no tiene. Queda registrado en `apto_reventa` para cuando exista.
4. **Desde la recepción se emite la Nota de Crédito** (`momento = EN_ENTREGA`), con su CAE: la pantalla ya tiene el pedido, el comprobante, los artículos, las cantidades y el motivo. El operador no vuelve a tipear nada, que es donde se cometen los errores.
5. El asiento de la NC revierte el saldo del cliente por el mecanismo contable ya existente.

La correspondencia queda **1 Pedido → 1 Comprobante → 1 Recepción → 1 NC**, y el circuito se cierra pedido por pedido en lugar de en un único acto al final del día.

> **Por qué la recepción va antes que la NC.** Si se acredita primero y se cuenta después, se le acredita al cliente mercadería que puede no haber vuelto, y el descalce aparece recién en la conciliación. Contando primero, la NC nace de un hecho verificado. Es la misma lógica por la que el Informe de Recepción precede a la registración de la factura del proveedor.

**El control:** la NC dice qué se le acreditó al cliente; la Recepción de Devoluciones dice qué volvió al depósito. **El reporte de conciliación confronta ambos** y expone los descalces: mercadería acreditada que no volvió, o mercadería que volvió sin NC. Ése es el punto de control interno de todo el proceso de devoluciones, y la razón de ser del documento nuevo.

**Reporte de devoluciones** por período, motivo, momento, repartidor, cliente y producto: muestra si el problema es de crédito, de calidad, de carga o de un repartidor puntual.

**Anulación del reparto completo** (se rompió el camión, no salió): el reparto pasa a estado 3 **conservando su número**, y sus comprobantes vuelven a quedar sin reparto, reasignables a otro. No se emiten NC: la mercadería nunca salió y los comprobantes siguen vigentes.

### 7.11 — Numeración de Factura, PRE y NC → **Plan 075**

La verificación del código encontró cuatro cosas: que la numeración se calcula leyendo el último número **sin bloqueo**; que `Venta` **no tiene restricción única** de `(empresa, tipo, punto, numero)`; que hay **fallbacks silenciosos** en el punto de emisión (asume `1`) y en el tipo de comprobante (elige uno por descarte); y que **la facturación por lote no usa `AfipService`**, que ya implementa correctamente `FECompUltimoAutorizado` y toma el número de `CbteDesde` — el lote calcula el número localmente y estampa un CAE ficticio en modo prueba.

Como **afecta a todas las empresas del ERP** y no sólo a este módulo, se trata en un plan separado: **[075 — Integridad de la numeración de comprobantes de venta](075_integridad_numeracion_comprobantes_venta.md)**, para compartir con el desarrollador responsable de facturación.

El módulo Distribución **depende** de ese plan: la facturación por lote de madrugada es justamente el escenario donde el problema se manifiesta.

---

## 8. Permisos, multiempresa e índices

**Permisos nuevos en `usuarios.Perfil`:** `permiso_distribucion_pedidos`, `permiso_distribucion_asignar_stock`, `permiso_distribucion_facturar_lote`, `permiso_distribucion_repartos`, `permiso_distribucion_cobranzas`, `permiso_distribucion_devoluciones`, `permiso_distribucion_rendicion`.

**Multi-tenant (regla inflexible):** toda consulta se acota por `session['empresa_id']`. El vendedor sólo ve su cartera. Test específico: un vendedor de la empresa A no puede leer un pedido, un cliente ni un stock de la empresa B.

**Índices y restricciones:**
- `Reparto`: `UniqueConstraint (empresa, punto, numero)`; `(empresa, fecha)`, `(empresa, estado)`.
- `RecepcionDevolucion`: `UniqueConstraint (empresa, punto, numero)`; `(empresa, fecha)`, `reparto`.
- `ExtensionPedidoDistribucion`: `UniqueConstraint (empresa, punto, numero)`; `fecha_entrega`, `hora_carga`, `zona`.
- `RepartoParada`: `(reparto, orden)`, `venta`.
- `NotaCreditoDistribucion`: `nota_credito` único, `venta_origen`, `motivo`, `recepcion`.
- `CarteraVendedor`: `(empresa, vendedor)`, **`(empresa, cliente)` único**.
- `Producto`: `(empresa, codigo_anterior)`.
- Listado de saldos: se apoya en `(empresa, cliente)` **ya existente** en `Venta`.

**Transaccionalidad:** `transaction.atomic()` + `select_for_update()` en la asignación de stock escaso, en la facturación por lote (cliente + stock + contador), en la imputación de cobranzas y en la confirmación de la Recepción de Devoluciones con reingreso de stock.

---

## 9. Plan de pruebas

**Unitarias**
- `saldo_disponible` y `cobro_minimo` en los cuatro casos de §7.4, incluido `limite = 0` y `bloqueado_credito`.
- `condicion_venta` derivada: CONTADO exactamente cuando `cobro_minimo ≥ total`.
- **FIFO segmentado**: que un medio trazable nunca toque un `condic = 2`; que el efectivo cancele primero los PRE más antiguos; que el excedente trazable quede como saldo a favor fiscal; cobro mixto en una operación.
- Que un cobro mixto genere **dos recibos** con el `condic` correcto y asientos independientes.
- Saldo operativo combinado vs. saldo contable con anticipo, sobre el mismo juego de datos.
- Precio: `precio_total × coeficiente`; cliente sin extensión cargada.
- Asignación de stock escaso: suma asignada nunca superior al disponible; orden por `hora_carga`; ajuste auditado.
- **Numeración correlativa** de Pedido, Reparto y Recepción de Devoluciones: sin huecos, sin duplicados bajo concurrencia, y **el documento anulado conserva su número**.
- **`auditar_correlativos()`** detecta huecos, duplicados y desfasaje del contador en los tres documentos nuevos.
- NC: caso A (stock vuelve sin recepción, parada quitada, `version_impresion` incrementada), caso B (NC + recepción, stock reingresa al confirmar), motivo obligatorio.
- Conciliación NC ↔ Recepción: detecta mercadería acreditada que no volvió y mercadería devuelta sin NC.
- Búsqueda de producto por `id` y por `codigo_anterior`.
- Consolidado: kg con productos sin `peso_unitario_kg` (debe dar 0, no romper).
- `comprometido`: tomar, asignar, anular y facturar deja el stock correcto en los cuatro casos.

**Integración**
- Circuito completo de dos días: pedidos numerados día 1 → faltantes y asignación → facturación de madrugada → una NC pre-carga con reimpresión → reparto → una no entrega con NC y recepción → cobranza mixta → rendición. Verificar saldo del cliente (ambas lentes), stock y saldo de caja en cada paso.
- Aislamiento multiempresa.
- Que una venta `condic = 2` **no** aparezca en el Libro IVA, y que su NC tampoco.
- Que el asiento de cada recibo y de cada NC herede el `condic` correcto.

**Manuales**
- Impresión de las 4 hojas contra los originales del PDF.
- Carga de un pedido completo en un celular real, cronometrada contra el tiempo del papel.
- Auditoría de correlativos sobre un mes de operación real.

---

## 10. Fases de implementación

| Fase | Contenido | Depende de |
|------|-----------|-----------|
| **0** | Decisiones de §11 + datos maestros: `peso_unitario_kg`, unidad de venta, coeficientes y clasificación, zonas, cartera, días de visita, catálogo de motivos. **Migración de `codigo_anterior` de productos** | Usuario |
| **0-bis** | **[Plan 075](075_integridad_numeracion_comprobantes_venta.md)** — integridad de numeración de Factura / PRE / NC. *Afecta a todo el ERP: plan y aprobación aparte* | Usuario + dev de facturación |
| **1** | `ExtensionDistribuidora`, `ExtensionPedidoDistribucion` **con numeración**, precios por coeficiente, pantalla de pedido en PC, servicio de crédito, stock comprometido, planilla manual PDF. Nuevos tipos en `ContadorDocumento` y extensión de `auditar_correlativos()` | Fase 0 |
| **2** | Pantalla móvil de carga rápida por código | Fase 1 |
| **3** | Reporte de faltantes + asignación final de stock | Fase 1 |
| **4** | Facturación masiva con la regla del saldo disponible; impresión de Factura y de PRE | Fases 0-bis y 3 |
| **5** | `Reparto` numerado, Consolidado de Artículos y Hoja de Ruta | Fase 4 |
| **6** | Entrega, Notas de Crédito con motivo, **Recepción de Devoluciones** y conciliación | Fase 5 |
| **7** | Cobranzas segmentadas + caja recaudadora + rendición | Fase 5 |
| **8** | Listado de saldos por vendedor + reporte de devoluciones + reporte de correlativos | Fase 6 |
| **9** *(futuro)* | Sucursal-vehículo con `RemitoInterno` para control de carga; portal del cliente | Fase 7 |

Cada fase cierra con su registro incremental en `docs/walkthrough.md` y su plan detallado en `docs/planes/`.

---

## 11. Decisiones abiertas

**11.1 — Valores de `ExtensionDistribuidora.clasificacion`.** *(única pendiente)*
Es descriptiva y no interviene en el precio, pero hay que definir sus valores para filtros y reportes. Es un dato de carga de la **fase 0**, no un condicionante del diseño: el módulo se puede construir con el campo vacío y poblarlo después.

---

### Decisiones ya cerradas

| Tema | Definición |
|---|---|
| Control interno | **Todo documento emitido lleva numeración correlativa propia y auditable** |
| Documentos del módulo | Pedido, Hoja de Ruta (Reparto), Recepción de Devoluciones, Factura, Presupuesto (PRE), Nota de Crédito |
| Numeración de la Factura | `punto` = punto de venta autorizado por ARCA (por parámetro); `numero` = el que devuelve ARCA por webservice |
| Numeración del PRE y de los documentos internos | `punto` = **`sucursal_id`** de la sucursal emisora; `numero` = correlativo propio del sistema para ese punto |
| Cadena de trazabilidad | Pedido Nº → Comprobante Nº → Hoja de Ruta (imprime ambos) → Recepción de Devoluciones → Nota de Crédito |
| Orden de la devolución | **Primero se cuenta (Recepción), después se acredita (NC)** |
| Alcance de la Recepción de Devoluciones | **Una por cada Pedido devuelto**, no una por reparto: 1 Pedido → 1 Comprobante → 1 Recepción → 1 NC |
| N° de Pedido en la Hoja de Ruta | Es el `ID` con el que arranca cada cliente en el reporte del sistema anterior |
| NC de un PRE | Tipo de comprobante **`NCI`**, `condic = 2`, numerada por `sucursal_id`, con `signo = -1` |
| Serie de la NCI | **Independiente de la del PRE**: contador propio, auditada por `(empresa, tipo, punto)` como el resto |
| Catálogo de motivos | Lista inicial propuesta en §5.A; se amplía con lo que aparezca en la operación real |
| Vendedores y repartidores | **Tabla propia `Personal`**, con `usuario` OneToOne nullable. `Venta.vendedor` y `Preventa.vendedor` no se tocan (§4.3) |
| Precio | `Producto.precio_total × coeficiente_mayorista`, cargado a mano por cliente |
| Clasificación de cliente | Descriptiva; no interviene en el precio |
| Crédito | `saldo_disponible = limite − saldo`, puede ser negativo; `cobro_minimo = max(0, −saldo_disponible)` |
| `limite = 0` | Sólo contado |
| Asignación de stock escaso | Orden de llegada del pedido; pedido siempre **sujeto a disponibilidad** |
| Medios trazables | Siempre `condic = 1` |
| Efectivo | Primero los PRE más antiguos; agotados, sigue con `condic = 1` |
| No entrega y anulación post-facturación | **Nota de Crédito con su CAE**, con motivo tipificado y observación |
| Devolución física | **Recepción de Devoluciones** numerada, vinculada a la Hoja de Ruta, que concilia contra las NC |
| Stock devuelto | Vuelve a disponible (vehículos refrigerados) |
| Devolución de repartos anteriores | No se aceptan |
| Códigos | Se imprimen **los dos**: `ID | código anterior` |
| Vendedor | Un cliente, **un solo vendedor** (responsable de su saldo) |
| Conectividad | Online-only en fase 1; planilla de papel como plan B |

---

## 12. Riesgos identificados

| Riesgo | Mitigación |
|--------|-----------|
| **Imposibilidad de auditar la integridad de los comprobantes emitidos** | Numeración correlativa en los seis documentos + `auditar_correlativos()` extendida (§4.2) |
| **Números duplicados en la facturación por lote** | Plan 075: `ContadorDocumento` con bloqueo + `UniqueConstraint` en `Venta` |
| Mercadería acreditada por NC que no vuelve al depósito | Conciliación NC ↔ Recepción de Devoluciones (§7.10) |
| Dos vendedores comprometen el mismo stock entre el pedido y la facturación | `comprometido` + reporte de faltantes + asignación por orden de llegada |
| Sobreventa por facturación simultánea del mismo artículo | `select_for_update()` sobre `StockSucursal` en el lote |
| Un medio trazable termina cancelando una operación no fiscal | Segmentación por medio de pago en el servicio FIFO + tests dedicados |
| La deuda `condic = 2` se vuelve incobrable | El efectivo ataca primero los PRE más antiguos |
| Circula una Hoja de Ruta desactualizada tras una NC pre-carga | `version_impresion` visible en el encabezado del papel |
| Datos maestros incompletos (peso, coeficientes, códigos) | Fase 0 explícita, previa a todo desarrollo |
| El vendedor pierde tiempo con la pantalla y vuelve al papel | Carga por código, sin mouse, cronometrada contra el papel antes de liberar |
