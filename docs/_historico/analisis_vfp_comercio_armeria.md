# Análisis del sistema VFP "Comercio SAS" (Armería) y su repercusión en el ERP nuevo

> Documento de ingeniería inversa del sistema legacy en Visual FoxPro `c:\jm_soft\Comercio_sas`,
> con datos del ejercicio vigente en `d:\jm_soft\net_comercio\eje_255` (módulo gestión) y
> `d:\jm_soft\net_balances\eje_255` (módulo contable/balances).
>
> Objetivo: interpretar **qué hace hoy** el sistema (su lógica/esencia), **qué conviene conservar**
> y **cómo impacta** en lo que estamos construyendo en `erp-ikigai-2` (Django).
>
> Fecha de análisis: 2026-06-06. Las tablas del ejercicio estaban **en uso (bloqueadas en exclusivo)**
> por la aplicación corriendo; la estructura se leyó de `eje_255` en vivo y, donde estaba bloqueada,
> del espejo `eje_255_01`. Los formularios se leyeron de `c:\jm_soft\Comercio_sas\Forms`.

---

## 1. Resumen ejecutivo

`Comercio SAS` es una **adaptación del ERP genérico de JM_Soft a la operatoria de una armería**.
La gestión comercial (productos, stock, ventas, compras) vive en el contenedor de datos
`mantenimientos.dbc` (en `net_comercio\eje_255`), y **cada operación comercial genera automáticamente
su asiento contable** en `contable.dbc` (en `net_balances\eje_255`), que es el corazón del ERP de balances.
Es decir: **un solo acto de facturar/comprar mueve stock, cuenta corriente, libro IVA y contabilidad a la vez.**

La particularidad de armería se apoya en tres pilares:

1. **Venta de mostrador en dos pasos**: el vendedor arma una *preventa* en `puestoventas`
   (comprobante interno tipo `PR`), y recién cuando el cliente **paga en caja** (`caja_mostrador`)
   se emite la factura fiscal con CAE de ARCA/AFIP, se descuenta stock y se asienta contablemente.
2. **Trazabilidad individual de armas**: los productos marcados como `subprod = 1` (armas) no se
   venden por stock genérico sino por **unidad serializada** (tabla `subproducto`, con `serie` y `cuim`).
   La facturación de armas tiene su propio formulario `facturaarmas`.
3. **Control regulatorio del cliente**: el cliente armero tiene **CLU** (Certificado de Legítimo Usuario)
   con vencimiento, y el sistema **bloquea** ventas de productos con credencial a Consumidor Final y
   **avisa/impide** vender un arma si la CLU está vencida.

El sistema nuevo (`erp-ikigai-2`) **ya tiene buena parte de la base** (modelos `Venta/VentaItem`,
`Compra/CompraItem`, `Producto/Subproducto/MovimientoStock`, `ClienteProveedor/ExtensionArmeria`,
multi‑empresa/sucursal/ejercicio). Lo que falta es, sobre todo, **el flujo operativo de mostrador
(preventa → caja), el enlace trazable VentaItem↔Subproducto, las reglas CLU y la sesión de caja**.

---

## 2. Metodología: cómo se determinó qué está vigente

Según la consigna, el **menú principal es la única fuente de verdad** de los formularios vigentes.
El menú generado `Menus\menu_principal.mpr` no llama a los formularios por nombre directo, sino que
para cada opción setea un **código** (`oApp.xForm = 'B-108'`, etc.), abre el formulario `acceso` que:

1. Pide contraseña → identifica usuario y `nivel` (tabla `usuarios`).
2. Verifica permiso en la tabla `acceso` (clave `id_usu(6)-cod_form`, p. ej. `000003-B-108`).
3. Resuelve el **nombre real** del formulario contra `mantenimientos!formularios` (campo `id_form` → `formulario`).
4. Devuelve la ruta `…\forms\<formulario>` y el menú hace `DO FORM`.

Cruzando `menu_principal.mpr` con `formularios.dbf` se obtiene el inventario exacto de lo vigente.
**Confirmación clave:** el viejo `facturacion` (id `B-101`) figura como **`VIGENTE = F`**: fue reemplazado
por el circuito `puestoventas` + `caja_mostrador`. También se descartan, por consigna,
`compras_mercaderia_anterior`, `estado_cta_cli_proi`, `puestopreventa` y todo `*_anterior`/`*_ant`/`*_01`.

### Formularios VIGENTES (por menú) y su tabla principal

| Menú | Código | Formulario (.scx) | Función | Tabla(s) núcleo |
|------|--------|-------------------|---------|-----------------|
| Archivos › Clientes/Prov. | — (directo) | `alta_cli_pro` | ABM cliente/proveedor (CLU, límite, lista) | `cli_pro` |
| Archivos › Productos | — (directo) | `alta_producto_armeria` | ABM producto (incluye `subprod`) | `producto` |
| Archivos › Marcas / Rubros / Familia | — | `alta_marca` / `alta_rubro` / `alta_familia` | ABM auxiliares | `marcas`,`rubro`,`familia` |
| Archivos › Usuarios / Accesos | A‑101 / A‑102 | `alta_usuario` / `otorga_acceso` | Usuarios y permisos por formulario | `usuarios`,`acceso` |
| Archivos › Cambio Contraseña | — | `cambia_contrasena` | — | `usuarios` |
| **Procesos › Venta Mostrador** | **B‑108** | **`puestoventas`** | **Preventa de mostrador (tipo `PR`)** | `aux_ventas_enc/mov`, `producto` |
| **Procesos › Caja Mostrador** | **B‑109** | **`caja_mostrador`** | **Cobro + emisión de factura (CAE) + asiento** | `ventas_enc/mov`, `caja_mostrador`, `contable` |
| Procesos › Cotización Dólar | B‑110 | `cotizacion_dolar` | Carga cotización USD del día | `t_moneda`,`historial_moneda` |
| **Procesos › Factura Armas** | **B‑111** | **`facturaarmas`** | **Facturación con trazabilidad serie/CUIM** | `subproducto`,`ventas_enc/mov` |
| Procesos › Compra Bienes de Cambio / c/Precio | B‑106 | `compras_mercaderias` | Compra: stock + alta de subproductos + asiento | `compras_enc/mov`,`producto`,`subproducto` |
| Procesos › Ajuste de Precios | B‑103 | `ajuste_compras_precios` | Ajuste de precios desde compras | `producto` |
| Procesos › Modificación Datos Armas | B‑112 | `mod_subproducto` | Edición de datos de armas (serie/cuim/estado) | `subproducto` |
| Procesos › Actualiza Descuentos | B‑113 | `actualiza_descuentos` | Descuentos por producto | `producto` |
| Procesos › Envío Mercadería Interno | B‑201 | `emision_remitos` | Remito interno entre sucursales (salida) | `ventas_enc/mov` (tipo `RI`) |
| Procesos › Recepción Mercadería Interno | B‑202 | `recepcion_remitos_internos` | Recepción remito interno | `transf_recibidas`,`producto` |
| Procesos › Remitos a Terceros | B‑203 | `puestoventasremitos` | Remito de venta a terceros (tipo `RV`) | `ventas_enc/mov` |
| Procesos › Inventario | B‑301 | `inventario` | Toma de inventario físico → ajuste de stock | `inventario`,`producto` |
| Informes › Comprobantes Ventas | C‑103 | `consulta_ventas_enc` | Consulta/anulación de facturas | `ventas_enc/mov` |
| Informes › Productos Vendidos | C‑104 | `consulta_ventas_prod` | Ranking/listado de ventas por producto | `ventas_mov` |
| Informes › Compras B. de Cambio | C‑105 | `consulta_compras_bcambio` | Consulta de compras | `compras_enc/mov` |
| Informes › Cierres de Caja | C‑106 | `cons_caja_m` | Consulta de cierres de caja | `caja_mostrador`,`retiro_caja` |
| Informes › Ajuste Grupal de Precios | C‑107 | `actualiza_precios_grupal` | Recalcular precios por grupo | `producto` |
| Informes › Comisión Vendedores | C‑108 | `liq_comision` | Liquidación de comisiones | `ventas_mov` |
| Informes › Control Stock | C‑109 | `control_stock` | Control/valuación de stock | `producto`,`control_stock` |
| Utilidades › Control/Corrige AFIP | — | `consulta_afip` / `afip_error.prg` | Estado de comprobantes ARCA | `ventas_enc` |
| Utilidades › Errores / Ruta / Terminales | D‑101/D‑102/— | `cons_errores` / `ruta_acceso` / `terminales_encendidas` | Diagnóstico | `base_error`,`terminales` |

Formularios de **consulta** invocados *dentro* de los anteriores (también vigentes): `cons_cli_pro`,
`cons_cli_pro_ctable`, `cons_producto`, `cons_producto_1`, `cons_cod_barras_cpra/vta`, `cobro_tarjeta`,
`ventasubproducto` (selector de arma disponible), `cons_caja_m`.

---

## 3. Modelo de datos legacy (tablas clave de `mantenimientos.dbc`)

> Tipos VFP: `I`=entero, `Y`=currency (8,4), `C`=texto, `D`=fecha, `T`=datetime, `L`=lógico, `N`=numérico.

### 3.1 `producto` (6.567 reg.) — maestro de artículos
Campos relevantes: `CODIGO`(PK), `COD_PROV`/`COD_FAB`, `TIPO`/`MARCA`/`PRESENT`/`DETALLE`,
`STOCK`,`MINIMO`,`PTOPEDIR`, `STKSUC1/2/3` (stock por sucursal), costos `CTO_ADQ`/`CTO_REP` + fechas,
precios `LISTA`/`MARGEN`/`PRECIO`/`PCIOT` (con IVA), `ALIC_IVA`/`CODIVA`, descuentos
`DTOMAX`/`DTOEFE`/`DTOTAR`/`DTOTARC`, multimoneda `MONEDA`/`COTIZ`, FKs `ID_MARCA`/`ID_RUBRO`/`ID_FLIA`/`ID_SFLIA`,
**`SUBPROD` (N,1) = 1 si el producto requiere trazabilidad (arma)**, **`CREDEN` (N,2)** = exige credencial/CLU.

### 3.2 `subproducto` (2.392 reg.) — **unidad serializada (cada arma)**
`SUBPRO`(PK) · `CODIGO`(FK→producto, el modelo) · `DETALLE`/`DETADIC` · **`SERIE`** · **`CUIM`** ·
`ID_CPRA`/`FECCPRA` (compra que la ingresó) · costos `CTO_ADQ`/`COTIZADQ`/`MONEDA` · `ALIC_IVA`/`CODIVA` ·
`MARGEN`/`PRECIO`/`PCIOT` · **`ID_VTA`/`FECVTA`** (venta que la egresó) · `COTIZVTA`/`FECENT` ·
**`ESTA`** (estado físico) · `COND` · **`CREDENCIAL`** · **`SITUAC`** (`'VENDIDA'` al facturar) · `SUC`.
> Es el espejo exacto del modelo nuevo `productos.Subproducto`.

### 3.3 `ventas_enc` / `ventas_mov` — comprobantes de venta
`ventas_enc`: cabecera con identidad fiscal (`TIPO` `PR`/`FA`/`FB`/`CA`/`CB`/`RV`/`RI`/`SC`, `PUNTO`,`NUMERO`),
cliente desnormalizado, totales (`NETO`/`IVA`/`EXENTO`/`NO_GRAV`/percepciones), desglose de IVA
(`IVA105`/`IVA21`/`IVA27`), **medios de pago desglosados** (`EFECTIVO`/`BANCO`/`VALORES`/`TARJETA`/`DOLARES`),
`COBRADO`/`SALDO`, **`CAE`/`VTO_CAE`/`COD_QR`**, `ID_ASTO` (asiento contable), `ID_COB`/`FEC_COB`,
**`CAJA_M`** (sesión de caja), `SUBFAC` (sub‑facturación), `SUC_O`/`SUC_D`/`SUC`.
`ventas_mov`: línea con `COD_PROD`,`CANTIDAD`, precios `PCIOV`/`PCIOF`/`PCIOP`/`PCIOD`, `ALIC_IVA`/`CODIVA`,
**trazabilidad denormalizada en la línea**: `SUBPROD`,`SERIE`,`CUIM`,`ID_SPROD`(→subproducto), `CREDENCIAL`.

### 3.4 `compras_enc` / `compras_mov` — comprobantes de compra
Cabecera con IVA/percepciones multi‑alícuota, `ID_ASTO`, `VENCIM`, `SUC`. Líneas con costos, `ALIC_IVA`,
recálculo de `PRECIO`/`PCIOT`/`MARGEN` y `STOCK`.

### 3.5 `caja_mostrador` (8.735 reg.) — **sesión/cierre de caja**
`CAJA_M`(PK),`FECHA`,`ID_USU`,`INICIAL`,`ARQUEO`,`GASTOS`,`RETIRO`,`DISPONIBLE`,`RECAUDADO`,`FACTURAS`,
`SINCPTE`,`NCREDITO`,`COBRANZAS`,`DIFERENCIA`,`SUC`. Cada venta cobrada se asocia a una `CAJA_M`.
Apoyos: `retiro_caja` (retiros por forma de cobro), `transf_recibidas` (valores/cheques/transferencias recibidos).

### 3.6 `cli_pro` (12.608 reg.) — cliente/proveedor **con campos de armería**
Además de lo comercial (`DESCUENT`,`LIMITE`,`SALDO`,`LISTA`,`COEF`), trae **`CLU`**, **`CLU_VTO`** (vencimiento)
y **`POLICIA`** (lógico). El CLU vive en el propio maestro de cliente (en el sistema nuevo se separó en `ExtensionArmeria`).

### 3.7 `maestro_id` (1 reg.) y `sucursales` (2 reg.) — **secuencias y numeración**
`maestro_id` es el singleton de contadores globales (`ID_VTA`,`ID_CPRA`,`ID_ASTO`,`CAJA_M`,…) y de
**números de comprobante por tipo** (`N_FA`,`N_FB`,`N_CA`,`N_CB`,`N_RV`,`N_RI`,`N_SC`) + config AFIP
(`RUTA_CAE`,`AUTORIZA`,`DGIMAXEFE`,`DGIMAXTAR`, certificados). **`sucursales` replica los mismos contadores
por sucursal** (`ID_VTA`,`CAJA_M`,`PVFE`,`N_FA…N_RI`,`ID_RETIRO`): **la numeración real se toma por sucursal**,
no del global. La generación usa `FLOCK` (bloqueo pesimista) para evitar saltos/duplicados.

### 3.8 Auxiliares de moneda
`t_moneda` (cotización vigente) e `historial_moneda` (histórico `COTIZ_O/M/B/C/V`). La armería **opera con
precios en USD** y cotización diaria; `puestoventas` toma `t_moneda` (`USD`) para convertir a pesos.

---

## 4. Flujos de negocio (la "esencia" a preservar)

### 4.1 Compra de bienes de cambio (`compras_mercaderias`)
1. Cabecera: proveedor (`cons_cli_pro_ctable`), tipo/punto/número (con **chequeo de duplicado**), IVA y percepciones.
2. Líneas (`aux_cpra`): por producto, costo, alícuota, **flag `subprod`**, recálculo de precio/margen.
   Si `subprod=1`, el botón **Subproducto** abre `alta_subproducto` y carga **serie/cuim** en `aux_alta_subproducto`.
3. Al **Grabar** (transacción):
   - `oApp.nuevo_id_cpra` → `id_cpra`; `INSERT compras_enc` + `compras_mov`.
   - **Stock**: `producto.stock += cantidad` y actualización de costos/precios.
   - **Subproductos**: `APPEND FROM aux_alta_subproducto` a `subproducto` con `id_cpra`/`feccpra` (una fila por arma).
   - **Asiento contable** (`asto_enc`/`asto_mov` en `contable.dbc`): `cta_cpra` (debe), `cta_iva_c` (IVA crédito),
     retenciones/percepciones (`cta_r_iva`/`cta_r_gcia`/`cta_r_ib`/`cta_p_ib` por jurisdicción), `cta_cli` (haber, proveedor).

### 4.2 Venta de mostrador en DOS pasos
**Paso 1 — Preventa (`puestoventas`, tipo `PR`)** — la hace el **vendedor**:
- Cliente por defecto **CONSUMIDOR FINAL** (`id_cod=1`); medio de pago `1.-Contado` / `2.-Cta.Cte.`.
- Carga de líneas por **código o código de barras** (vistas `cons_producto_vta`/`cons_prod_barra1`).
- **Reglas de armería en el alta de línea** (las dos validaciones clave):
  - Si `producto.creden > 0` y el cliente es Consumidor Final → **bloquea**:
    *"No está permitido vender este producto a Consumidores Finales… ingrese o dé de alta un cliente"*.
  - Si `producto.creden > 0` **y** `CLU_Vto < hoy` **y** `subprod > 0` → **bloquea**:
    *"El Certificado de Legítimo Usuario está vencido"*.
- Grabar: escribe en **tablas de staging** `aux_ventas_enc`/`aux_ventas_mov` (alias `ventas_enc`/`ventas_mov`
  dentro del form) con `tipo='PR'`. **Todavía no hay factura, ni CAE, ni baja de stock, ni asiento.**

**Paso 2 — Caja (`caja_mostrador`)** — la hace el **cajero**:
- Recupera la preventa (`aux_ventas_enc`), define **`tipo_grabacion`**: `1`=Factura, `2`=Remito(`RV`), `3`=Sin comprobante(`SC`).
- `factura_afip`: según condición de IVA del cliente mapea **Factura A (cód. AFIP '1')** o **Factura B ('6')**
  (y `CA`/`CB` para notas de crédito); llama al **web service de ARCA/AFIP**, obtiene **CAE** y genera el **PDF**.
  El comprobante pasa de `PR` → `FA`/`FB`.
- **Asiento contable** (`caja_asto_enc`/`caja_asto_mov`): líneas por cada medio de pago
  (`cta_caja` efectivo, `dolares`, `cta_tar` tarjeta, `cta_bco` transferencias, `cta_val_car` valores),
  `cta_cli` (saldo a cta cte), `cta_bon` (recargo/bonif.), `cta_vta` (haber, ventas neto), `cta_iva_d` (IVA débito).
- **Stock**: baja de `producto.stock` por cada línea.
- **Libro IVA**: `INSERT lib_iva_alic` (neto/alícuota/iva por comprobante).
- **Numeración**: incrementa `N_FA`/`N_FB`/… (por sucursal).
- Mueve de staging a definitivo: `INSERT ventas_enc FROM aux_ventas_enc` + `ventas_mov`; registra
  `tarjetas_mov`, `transf_recibidas`, `valores_terceros`, todo enlazado a `id_asto` y `caja_m`.

> **Por qué dos pasos**: refleja la operatoria real del mostrador de armería — el vendedor atiende y arma
> el pedido; el cobro y la emisión fiscal se centralizan en caja (control de efectivo, arqueo, cierre).

### 4.3 Venta de armas con trazabilidad (`facturaarmas`)
Camino **separado** (no usa el circuito preventa/caja) para vender unidades serializadas:
- Alta de línea de **dos maneras**:
  1. Por **serie**: `SEEK subproducto` por `serie`; si `id_vta` está vacío (no vendida) carga
     `cod_prod`/`detalle`/`id_sprod`/`serie`/`cuim`/costos/precio. Si ya tiene `id_vta` →
     *"El arma ya fue facturada bajo el id_vta X el dd/mm/aaaa"* (**evita doble venta**).
  2. Por **código de producto**: si `producto.subprod=1`, abre la vista `venta_subproducto` (armas disponibles)
     y el form `ventasubproducto` para **elegir la unidad** concreta.
- `credencial = CLU` del cliente en la línea.
- Grabar: `factura_afip` (CAE) → `id_vta`; `INSERT ventas_enc`+`ventas_mov` (y copia a `aux_ventas_enc` con `estado=1`);
  **agrega serie/cuim al detalle**; asiento (`asto_enc`/`asto_mov`), libro IVA.
- **Cierre de trazabilidad**: por cada línea, `subproducto`: `id_vta = venta`, `fecvta = hoy`,
  `pciot`/`cotizvta`, **`situac = 'VENDIDA'`**. Así la unidad queda marcada como vendida y enlazada a su venta.

### 4.4 Otros flujos vigentes
- **Inventario** (`inventario`): toma física por terminal/usuario → ajusta `producto.stock`.
- **Remitos internos** (`emision_remitos`/`recepcion_remitos_internos`): transferencias entre sucursales
  (salida tipo `RI` + recepción que suma stock destino vía `transf_recibidas`).
- **Cierre de caja** (`cons_caja_m`): arqueo, retiros, diferencia, recaudación por medio de pago.
- **Cotización dólar** (`cotizacion_dolar`): actualiza `t_moneda`/`historial_moneda` (base del precio en USD).
- **Comisiones** (`liq_comision`): por vendedor sobre `ventas_mov`.

---

## 5. Integración con el ERP de Balances (contable)

Esta es la pieza más importante de "no perder la esencia": **el comercio no es una isla**.

| Concepto | Legacy |
|---|---|
| Path datos comercio | `oApp.Net` = `…\net_comercio\eje_255\` → `mantenimientos.dbc` |
| Path datos contable | `oApp.Netctable` = `…\net_balances\eje_255\` → `contable.dbc` |
| Asientos | `asto_enc`/`asto_mov` (definitivos) y `caja_asto_enc`/`caja_asto_mov` (desde caja) |
| ID de asiento | `oApp.nuevo_id_asto` lee/incrementa **`contable!parametros_contables.id_asto`** (¡en la base de balances!) |
| Libro IVA | `lib_iva` / `lib_iva_alic` / `lib_iva_afip` (en `contable.dbc`) |
| Plan de cuentas | `cuentas.dbf` (en `contable.dbc`) |
| Mapeo operación→cuenta | propiedades `oApp.cta_*` cargadas por `carga_variables_contables` |

**Mapa de cuentas** (`oApp.cta_*`, usado al asentar): `cta_caja`, `cta_vta`, `cta_iva_d` (IVA débito),
`cta_iva_c` (IVA crédito), `cta_cli` (deudores), `cta_pro`/`cta_cpra` (proveedores/compras), `cta_tar` (tarjetas),
`cta_val_car` (valores en cartera), `cta_bon` (bonif./recargo), `cta_r_iva`/`cta_r_gcia`/`cta_r_ib`/`cta_r_mun`/`cta_r_suss`
(retenciones), `cta_ar_*`/`cta_ap_*` (ajustes), etc.

> **Consecuencia para el diseño nuevo**: cada `Venta`/`Compra` debe poder **generar un asiento** en el módulo
> `contable`, con un mapeo configurable operación→cuenta. Los modelos nuevos ya prevén `asiento_id` en
> `Venta`/`Compra`/`Movimiento`; falta el **servicio de asentado** y la **tabla de parámetros contables**
> (equivalente a `cta_*`). Ver `docs/planes/001_automatizacion_contable.md`.

### 5.1 Mejora propuesta: cuenta contable por rubro (ventas y compras)

**Problema actual.** Todo el neto de una venta se asienta contra **una única** cuenta `oApp.cta_vta`, y
todo el neto de una compra contra **una única** `oApp.cta_cpra`. No hay forma de discriminar el resultado
por línea de negocio (rubro): el Estado de Resultados no refleja el *mix* real de lo facturado/comprado.

**Mejora.** Que la tabla `rubro` tenga **dos cuentas configurables** y que el asiento **descomponga el neto**
según la mezcla de productos del comprobante. Es el patrón "cuenta de resultado por rubro/línea de negocio".

**Alcance preciso (decidido con el usuario):**
- La descomposición aplica **sólo al NETO** (cuenta de resultado): renglones de venta contra `cta_vta` del
  rubro, renglones de compra contra `cta_cpra` del rubro.
- El **IVA NO se descompone** en el asiento: el **IVA Débito Fiscal** (ventas) va en **un único** `asto_mov`
  contra `cta_iva_d`, y el **IVA Crédito Fiscal** (compras) en **un único** `asto_mov` contra `cta_iva_c`.
- El desglose por alícuota **sigue viviendo en `contable.lib_iva_alic`** (en `\BALANCES\`), que continúa
  agrupando por alícuota para luego **generar el TXT del Libro IVA que solicita ARCA**. Son destinos
  distintos: el **asiento** lleva el IVA consolidado; el **Libro IVA** mantiene el detalle por alícuota.

**Cambios en el legacy VFP (5 puntos):**

1. **`rubro.dbf`**: agregar `CTA_VTA  I(4)` y `CTA_CPRA  I(4)`. ABM en `alta_rubro`. Fallback: si la cuenta
   del rubro es `0`, usar `oApp.cta_vta` / `oApp.cta_cpra` respectivamente ("la misma o una específica").
2. **Línea de venta** (`aux_vta` → `ventas_mov`): agregar `CTA_VTA` y cargarla al seleccionar el producto
   desde `rubro.cta_vta` (la vista `cons_producto_vta` debe exponer la cuenta vía join producto→rubro).
   `ventas_mov` ya trae `ID_RUBRO` como respaldo; conviene **denormalizar la cuenta en la línea** para
   integridad histórica (si mañana cambia la cuenta del rubro, los asientos viejos no se alteran).
3. **Línea de compra** (`aux_cpra` → `compras_mov`): agregar `CTA_CPRA` (y `ID_RUBRO` como respaldo, porque
   hoy `compras_mov` **no** lleva rubro) y cargarla al seleccionar el producto desde `rubro.cta_cpra`.
4. **`caja_mostrador`** (y **`facturaarmas`**, que asienta en `asto_mov`): reemplazar el renglón único de
   ventas por un `GROUP BY` del neto por cuenta:

   ```foxpro
   SELECT IIF(cta_vta>0, cta_vta, oApp.cta_vta) AS cta, SUM(neto) AS neto ;
      FROM aux_ventas_mov WHERE !DELETED() AND total != 0 ;
      INTO CURSOR cur_ctavta GROUP BY 1
   SELECT cur_ctavta
   SCAN
      INSERT INTO caja_asto_mov (id_asto, id_cta, haber, debe) ;
         VALUES (xaux_ventas_enc.id_asto, cur_ctavta.cta, ;
                 IIF(xaux_ventas_enc.tipo='C', 0, cur_ctavta.neto), ;
                 IIF(xaux_ventas_enc.tipo='C', cur_ctavta.neto, 0))
   ENDSCAN
   ```
   El renglón de IVA (`cta_iva_d`, total) y los cobros quedan **sin cambios**.
5. **`compras_mercaderias`**: ídem, agrupando el neto por `cta_cpra`; el IVA crédito (`cta_iva_c`, total) y
   las retenciones/percepciones quedan **sin cambios**.

**Por qué sigue cuadrando**: la suma de los netos por cuenta = neto total del comprobante; sólo se "abre"
en varios renglones lo que antes era uno. Nada cambia en IVA, cobros, retenciones ni cliente/proveedor.

**Repercusión en el sistema nuevo (`erp-ikigai-2`)**: `productos.Rubro` debe tener `cuenta_venta` y
`cuenta_compra` (FK al plan de cuentas de `contable`); `VentaItem`/`CompraItem` copian la cuenta al
cargar la línea; y el **servicio de asentado** (Plan 001) agrupa los netos por cuenta vía `GROUP BY` del ORM,
dejando el IVA en **un solo** apunte. El `lib_iva` por alícuota (Plan 007) se mantiene independiente para el
TXT de ARCA.

---

## 6. Arquitectura/runtime del legacy (lo que condiciona el diseño)

- **`oApp` (clase `entorno` en `clases\basico.vcx`)** es el contexto global: paths, identidad y utilidades.
  Se inicializa en `setup` leyendo `data\parametros.dbf` (que define `net`, `netctable`, `sistema`, `cuit`, `suc`).
- **Identidad de terminal**: `oApp.terminal = COMPUTERNAME` → `terminales` → `estacion`; marca encendida/cerrada.
  Por eso existe "Terminales encendidas" y el control de no abrir dos veces.
- **Sucursal**: `oApp.suc` define la sucursal activa; de `sucursales` toma `pvfe` (punto de venta FE),
  `caja_m`, domicilio y **los contadores de numeración**.
- **Generación de IDs (concurrencia)**: `nuevo_id_vta` (de `sucursales`, con `FLOCK`), `nuevo_id_cpra`,
  `nuevo_id_asto` (de `contable!parametros_contables`). **Numeración pesimista por sucursal**.
- **CUIT multi‑empresa en un mismo binario**: el `comercio.prg` elige certificado AFIP, fondo y ejercicio
  según `oApp.cuit` (Armar SAS = `30718098226`, ejercicio `255`). Es decir, **un mismo código sirve a varias
  empresas** cambiando parámetros — ya resuelto en el nuevo con `empresas.Empresa`/`Sucursal`/`Ejercicio`.
- **Seguridad**: contraseña en texto plano (`usuarios.contrasena`, 10 char), permisos **por formulario**
  (`acceso` = `id_usu`+`cod_form`), y `nivel` para autorizaciones (p. ej. ver código de autorización de descuento).
- **Sub‑facturación (`SUBFAC`)**: campo presente en cabecera y línea de ventas — porción **no facturada**
  de una operación (operatoria informal). **Recomendación: NO portar como feature**; documentar y decidir
  explícitamente su exclusión.

---

## 7. Repercusión en el sistema nuevo (`erp-ikigai-2`)

### 7.1 Qué ya está cubierto (no rehacer)
- `facturacion.Venta`/`VentaItem`, `Compra`/`CompraItem` con totales, IVA, percepciones, CAE, QR, multi‑moneda,
  multi‑empresa/sucursal/ejercicio, `asiento_id`, medios de pago desglosados (`efectivo/tarjeta/transferencia/valores`),
  `vendedor`/`cajero`, `estado`.
- `facturacion.ClienteProveedor` + **`ExtensionArmeria(clu, clu_vto)`**.
- `productos.Producto` (con **`subprod`**, `stock`, `StockSucursal`, `MovimientoStock`) y **`Subproducto`**
  (serie único, cuim, `compra` FK, `venta` FK, sucursal).
- `facturacion.VentaItem` ya trae **`credencial`** y **`dmp`**.
- `tesoreria`: `MedioPago`, `CuentaBancaria`, `Recibo`, `OrdenPago`, `Valor`.

### 7.2 Brechas a cubrir (mapeo legacy → Django)

| # | Necesidad (legacy) | Estado nuevo | Acción recomendada |
|---|---|---|---|
| 1 | **Trazabilidad en la línea de venta** (`ventas_mov.id_sprod/serie/cuim`) | `VentaItem` **no** enlaza `Subproducto` | Agregar FK/M2M `VentaItem → productos.Subproducto` (o `VentaItemSubproducto`), con serie/cuim copiados; 1 línea por unidad. |
| 2 | **Marcar arma como vendida** (`subproducto.situac='VENDIDA'`, `id_vta`,`fecvta`) | `Subproducto.venta` existe, falta `estado`/lógica | Añadir `Subproducto.estado` (EN_STOCK/RESERVADO/VENDIDO) + servicio que al facturar setee `venta`, `fecha_vta`, estado. |
| 3 | **Validación CLU vencida** y **bloqueo credencial→Consumidor Final** | reglas no implementadas | Implementar en el servicio de venta: si `producto.creden`/`subprod` y cliente CF → bloquear; si CLU vencida → bloquear/avisar. (Plan 010) |
| 4 | **Preventa → Caja** (dos pasos `PR`→`FA/FB`) | `Venta.estado` existe pero sin flujo | Definir estados de `Venta` (PREVENTA → FACTURADA/ANULADA) y dos vistas: mostrador (vendedor) y caja (cajero). |
| 5 | **Sesión/cierre de caja** (`caja_mostrador`,`retiro_caja`) | **no existe** en `tesoreria` | Crear `CajaSesion` (apertura/arqueo/retiros/diferencia, por sucursal/usuario) y enlazar `Venta.caja`. (Plan 005) |
| 6 | **Alta de subproductos desde la compra** (serie/cuim al comprar arma) | `Subproducto.compra` existe, falta UI/flujo | Al guardar `CompraItem` con producto `subprod=1`, capturar N series/cuim y crear `Subproducto` (estado EN_STOCK). |
| 7 | **Asentado contable automático** (`cta_*`, `nuevo_id_asto`) | `asiento_id` reservado; falta servicio | Servicio `generar_asiento(venta/compra)` + tabla `ParametrosContables` (mapeo cuenta por concepto). (Plan 001) |
| 8 | **Libro IVA por alícuota** (`lib_iva_alic`) | — | Modelo/registro por alícuota al facturar. (Plan 007) |
| 9 | **Numeración por sucursal+tipo** (contadores `sucursales.N_FA…`) | `Venta.numero` libre | Secuenciador atómico por `(empresa, sucursal, tipo, punto)` con `select_for_update` (equivalente al `FLOCK`). |
| 10 | **Precio en USD + cotización diaria** (`t_moneda`/`historial_moneda`) | `Venta.moneda/cotizacion` existe | Modelo de cotización diaria + precio de producto en USD y conversión al vender. |
| 11 | **Inventario físico** (`inventario`) y **control de stock** | `MovimientoStock` existe | Flujo de toma de inventario → ajuste de `StockSucursal` con `MovimientoStock`. (Plan 002) |
| 12 | **Remitos internos / transferencias** entre sucursales | — | Modelar transferencia (salida/recepción) que mueva `StockSucursal`. |
| 13 | **Permisos por formulario/opción** (`acceso`) | — | `006_permisos_modulares.md`: permisos por módulo/acción y por sucursal. |

### 7.3 Decisiones explícitas a tomar
- **`SUBFAC` (sub‑facturación)**: confirmar que **no** se replica (recomendado).
- **CLU**: ¿se mantiene separada en `ExtensionArmeria` (ya hecho) o se evalúa traer también `POLICIA` y otros
  campos del cliente armero? El legacy lo tenía todo en `cli_pro`.
- **DMP**: el campo `VentaItem.dmp` es **nuevo** (no estaba en `ventas_mov`); confirmar su origen/uso regulatorio
  (ANMaC) y si va por línea o por comprobante.
- **CLU vencida**: ¿bloqueo duro (como legacy) o advertencia con autorización por nivel? El legacy bloquea.
- **Asiento desde caja vs. desde la venta**: el legacy usa `caja_asto_*` para la venta de mostrador (cobro)
  y `asto_*` directo en `facturaarmas`/compras. Unificar el criterio en el servicio de asentado.

---

## 8. Anexo — Tipos de comprobante (legacy)

`PR` preventa interna · `FA`/`FB` factura A/B · `CA`/`CB` nota de crédito A/B · `SC` sin comprobante (interno) ·
`RV` remito de venta/terceros · `RI` remito interno entre sucursales.

## 9. Anexo — Correspondencia de tablas legacy → modelos nuevos

| Legacy (`mantenimientos.dbc`) | Nuevo (Django) |
|---|---|
| `producto` | `productos.Producto` (+ `StockSucursal`) |
| `subproducto` | `productos.Subproducto` |
| `marcas`/`rubro`/`familia`/`subfamilia` | `productos.Marca`/`Rubro`/`Familia` |
| `cli_pro` (+ `CLU`/`CLU_VTO`) | `facturacion.ClienteProveedor` + `ExtensionArmeria` |
| `ventas_enc`/`ventas_mov` | `facturacion.Venta`/`VentaItem` |
| `compras_enc`/`compras_mov` | `facturacion.Compra`/`CompraItem` |
| `caja_mostrador`/`retiro_caja` | **(falta)** `tesoreria.CajaSesion` (a crear) |
| `maestro_id`/`sucursales` (contadores) | `empresas.*` + secuenciador por sucursal (a crear) |
| `t_moneda`/`historial_moneda` | cotización (a crear) |
| `acceso`/`usuarios` | `usuarios.*` + permisos modulares (Plan 006) |
| `contable!asto_enc/mov`, `lib_iva*`, `cuentas` | `contable.*` (Plan 001/007/009) |

---

*Documento generado a partir de la inspección de los `.scx`/`.dbf` del sistema VFP vigente. Para regenerar
las extracciones se usó un lector DBF/FPT/SCT propio (`tmp_dbftool.py`).*
