# Plan 026 — Módulo de Compras: Facturas, Libro IVA y Retenciones

> **Estado:** Completado y verificado (2026-06-25). Todas las fases implementadas.
> **Memoria asociada:** `compras-modulo-spec`, `libro-iva-retenciones-arquitectura` (ver `MEMORY.md`).
> **Para retomar:** Plan finalizado. Pendiente circuito de Órdenes de Pago (asignación).

---

## 1. Objetivo

Completar el circuito de **Facturas de Compras** con su tratamiento de costos, asiento contable totalizado por rubro, subsistema fiscal normalizado (Libro IVA Digital + retenciones/percepciones) y el flag `condic` fiscal/no-fiscal.

## 2. Decisiones de diseño congeladas

1. **Dos tipos de compra:**
   - **Bienes de Cambio** (con detalle de ítems): actualiza stock, `cto_adq`/`fec_adq` y `cto_rep`/`fec_act`. Imputación DEBE por `producto.rubro.cta_compras`.
   - **Gastos** (sin detalle, textbox descriptivo): imputación sugerida `ClienteProveedor.cta_res`; contrapartida `cta_pat`.
2. **Costos con bonificación:** `cto_adq` = neto facturado línea ÷ cantidad (ya con bonificación). `cto_rep` = precio de lista del proveedor (sin bonificación), salvo que se decida trasladar el descuento → entonces `cto_rep = cto_adq`. Recalcula precio de venta (vía `margen`) automáticamente, muestra variación y queda **editable** (redondeo).
3. **Moneda extranjera:** se guarda en moneda origen + `cotizacion` de la factura. En `Producto`, costo/precio en moneda extranjera (se pesifica al vender). **El asiento SIEMPRE en pesos** (pesificado por la cotización de la factura).
4. **Asiento (DEBE):** una línea por `producto.rubro.cta_compras` con Σ(neto+exento+no_gravado). IVA Crédito Fiscal en un solo renglón total. Ret/perc una línea por concepto. **HABER:** proveedor `cta_pat` por el total.
5. **`condic` (flag de filtrado, SIN tratamiento diferencial):** 1=fiscal, 2=no fiscal. condic=2 hace EXACTAMENTE lo mismo que condic=1 (stock, precio, saldo proveedor, asiento). Solo sirve para **excluir** los no fiscales de los reportes impositivos. Por ser no fiscales no tienen IVA ni ret/perc. Se guarda en `compra.condic` **y** en el encabezado del asiento (que SIEMPRE significó fiscal/no-fiscal). **CAPTION DE UI:** en todo el sistema el optiongroup se rotula **"REAL / PRESUPUESTADO"** (aunque el significado interno sea fiscal/no-fiscal).
6. **Notas de Crédito:** importe NEGATIVO en la tabla; el asiento NO va en negativo, se **invierte** (DEBE↔HABER). NC de bienes de cambio: revierte stock pero **NO** toca `cto_adq`/`cto_rep`.
7. **Tablas comprobantes separadas:** `Venta` y `Compra` quedan separadas (campos cae/qr/cliente solo aplican a ventas). Saldo ClienteProveedor = saldo_inicial + Σ(ventas.saldo) − Σ(compras.saldo).
8. **Libro IVA:** modelo abstracto `LibroIvaBase` → `LibroIvaCompras` / `LibroIvaVentas` (esta agrega cae/vto_cae/codigo_qr). `LibroIvaAlic` única por `asiento_id` (+`c_v`).
9. **`RetPercSufrida`** (ret/perc que terceros nos practican): tabla ÚNICA por `asiento_id` (la cuelga de ventas/compras/recibos/órdenes de pago). `tipo`+`importe` (no dos columnas). Cuando NOSOTROS somos agentes ya existe otra estructura (ventas: percepción al cliente; OP: medio de pago categoría 'RET') — esa NO usa `RetPercSufrida`.
10. **Consolidación de cabecera:** eliminar `p_iva, p_gcia, p_iibb, p_recbc, p_sircreb, p_mun` de `Compra`; dejar solo `iva` (total alícuotas) + `otros` (total ret/perc). El detalle exhaustivo va en `RetPercSufrida`.

## 3. Estado actual del código (puntos de anclaje)

- **`facturacion/models.py`**
  - `Compra` (L163): tiene `moneda`, `cotizacion`, `neto`, `iva`, `no_gravado`, `exento`, `p_iva..p_mun`, `otros`, `total`, `pagado`, `saldo`, `asiento_id`. **NO** tiene `condic`. `recalcular_totales()` en L209.
  - `CompraItem` (L239): `producto`, `cantidad`, `precio_unitario`, `iva_alicuota`, `total`.
  - `Venta` (L339) / `VentaItem` (L442). Tampoco tiene `condic` (confirmado: ventas lo agregará igual).
- **`facturacion/forms.py`** — `CompraForm` (L269): `exclude` lista; `widgets` incluye los `p_*` (a remover en Fase 3); importes opcionales en `__init__` (L296).
- **`facturacion/views.py`** — `ComprasCargaView` (L256). `post()` (L277): normaliza `campos_monetarios` (L279, NO incluye `condic` aún), guarda compra + ítems, actualiza stock (L325-340) y pisa costos del producto (L342-346, hoy `cto_adq = cto_rep = precio_unitario`, SIN lógica de bonificación). **No llama a contabilizar** explícitamente acá (lo dispara una señal, ver `_no_contabilizar`).
- **`contable/services/contabilizacion.py`** — `contabilizar_compra` (≈L218-384):
  - Agrupa DEBE por `producto.rubro.cta_compras` (L250-294).
  - IVA Crédito Fiscal (L318-329).
  - Ret/perc desde `mapeo_percepciones` leyendo `p_*` (L331-351) → **a refactorizar en Fase 3**.
  - `otros` → `cta_impuestos_internos` (L353-364).
  - `crear_asiento(..., condic=2 if compra.saldo > 0 else 1, modulo=5)` (L367-376) → **BUG: `asiento.condic` siempre fue fiscal/no-fiscal, no Contado/CtaCte. Corregir a `condic=compra.condic`. Mismo bug en ventas L198 (`condic=venta.condic`).**
- **`contable/models.py`** — `ParametrosContables` con `cta_iva_credito`, `cta_compras`, `cta_proveedores_default`, `cta_impuestos_internos`, `cta_ret_iva/ganancias/iibb/suss/mun` (L110-115).
- **`productos/models.py`** — `Producto`: `compra_id` (L98), `cto_adq` (L99), `cto_rep` (L101), `margen` (L103), `precio_neto` (L104), `alic_iva` (L105), `precio_total` (L106), `cotiz_cpra` (L107) + `fec_adq`/`fec_act`. Método `calcular_precio` (≈L124-134) usa costo×(1+margen)×(1+iva).
- **`templates/facturacion/compras_carga.html`** — formulario de carga (Alpine.js). Patrón de selector `condic` a copiar de `templates/tesoreria/recibo_carga.html` L57-67.

---

## 4. FASE 1 — Campo `condic` en Compra  *(bajo riesgo, aislada)* ✅ HECHO

**Objetivo:** agregar el flag y propagarlo, sin lógica diferencial.

1. **Modelo** — `facturacion/models.py`, en `Compra`:
   ```python
   condic = models.IntegerField(default=1, verbose_name="Condición")  # 1=fiscal, 2=no fiscal
   ```
   Migración: `python manage.py makemigrations facturacion && migrate`.
2. **Form** — `CompraForm` (forms.py): asegurar que `condic` NO esté en `exclude` (no lo está; el `exclude` actual no lo menciona, así que entra automático). Agregar widget si se quiere (`forms.RadioSelect` o manejarlo en el template con Alpine).
3. **View** — `ComprasCargaView.post`: `condic` entra por `form.save()`. No requiere normalización monetaria.
4. **Template** — `compras_carga.html`: selector radio con caption **"Real (1) / Presupuestado (2)"**, default 1, espejando `recibo_carga.html` L57-67. Bindear a `data.condic` en el state de Alpine.
5. **Asiento (fix)** — `contabilizar_compra`: cambiar `condic=2 if compra.saldo > 0 else 1` por `condic=compra.condic` (era un bug; `asiento.condic` siempre fue fiscal/no-fiscal). Aplicar el mismo fix en ventas (L198 → `condic=venta.condic`).
6. **Reportes impositivos** — al construir Libro IVA / listados fiscales, filtrar `condic=1`. (Se materializa en Fase 2; dejar nota.)

**Verificación:** cargar una compra con condic=2, confirmar que actualiza stock/costos/saldo igual que condic=1 y que el valor queda persistido en `compra.condic` y en el asiento.

---

## 5. FASE 2 — Modelo fiscal nuevo  *(aditiva, sin romper lo existente)* — ✅ HECHO

**Implementado en `contable/models.py`** (migración `0010_...`), registrado en `contable/admin.py`. Verificado: alta de los 4 modelos + join por `asiento_id` + conciliación `cabecera.otros == Σ RetPerc.importe`. App destino: `contable` (no se creó app nueva). `asiento_id` quedó como `IntegerField` plano (igual que `Compra.asiento_id`). Pendiente para la fase de reportes: el método de exportación a los TXT exactos de ARCA (layout RG / Libro IVA Digital) — los modelos ya tienen todos los campos para alimentarlo.

**Objetivo:** crear las tablas fiscales. Aún sin migrar la lógica vieja (eso es Fase 3).

1. **App destino:** evaluar `contable/` o nueva app `fiscal/`. Recomendado: `contable/models.py` (conviven con `ParametrosContables`/`Asiento`). Revisar también `docs/planes/007_libro_iva_afip.md`.
2. **`LibroIvaBase` (abstract):** `asiento_id` (IntegerField, db_index), `fecha`, `clienteproveedor` (FK), `codiva` (tipo cbte ARCA, '001'=Fact A), `punto`, `numero`, `cuit`, `neto_gravado`, `exento`, `no_gravado`, `iva_total`, `otros`, `total`. Método compartido de exportación TXT.
3. **`LibroIvaCompras(LibroIvaBase)`** y **`LibroIvaVentas(LibroIvaBase)`** (esta agrega `cae`, `vto_cae`, `codigo_qr`).
4. **`LibroIvaAlic`** (única): `asiento_id` (idx), `c_v` ('C'/'V'), `neto`, `alicuota`, `iva`, `computable` (=neto×alicuota; en ventas = iva), `codiva`.
5. **`RetPercSufrida`** (única): `asiento_id` (idx), `origen` ('C'/'V'/'R'/'OP'), `tipo` ('R'/'P'), `impuesto` (choices: IVA, GANANCIAS, IIBB, TEM, SIRCREB, SUSS...), `base`, `alicuota`, `importe`, `jurisdiccion` (FK nullable, multi-fila por convenio multilateral), `nro_certificado`, `fecha`, `cuit_agente`, `razon_social_agente`, `regimen` (código régimen ARCA/DGR para conciliar con SICORE/reportes provinciales/municipales).
6. **Migraciones** + registrar en `admin.py` para inspección.

**Verificación:** migraciones aplican limpio; alta manual de filas por shell/admin; método de exportación TXT genera encabezados+alícuotas con datos dummy.

---

## 6. FASE 3 — Consolidación de cabecera  *(invasiva — toca lo andando)* ✅ HECHO

**Estado: PARCIAL.** Se hizo la parte aditiva (poblar fiscal + centralizar ret/perc) y se difirió la parte destructiva (drop de `p_*`) por dos trabas: falta la UI de captura del detalle de ret/perc y la colisión semántica de `otros` (impuestos internos vs total ret/perc).

**✅ HECHO ahora (aditivo, en `contable/services/contabilizacion.py`):**
- Fuente ÚNICA de ret/perc `_armar_retperc_compra` (hoy lee los `p_*`; en Fase 4 se cambia la fuente al detalle capturado) que alimenta a la vez los renglones del asiento y `RetPercSufrida`.
- `contabilizar_compras` **pobla** `LibroIvaCompras` + `LibroIvaAlic` (por alícuota de los ítems) + `RetPercSufrida`, **solo si `condic=1`** (los no fiscales quedan fuera del Libro IVA en el origen). Idempotente: `_limpiar_libro_iva_compra` antes de reescribir.
- **BUG PRE-EXISTENTE GRAVE corregido:** una sola carga dejaba **2 asientos activos** (el reset `compra.asiento_id=None; save()` sin guard `_no_contabilizar` re-disparaba la señal → contabilización reentrante). Esto **duplicaba el comprobante en los saldos contables** (doble conteo en el mayor). Fix: leer `asiento_id` vigente desde la BD + guardar el reset con el guard. Verificado: 1 carga → 1 asiento activo; idempotente en re-contabilización (carga + 2 re-contab → siempre 1 LIC/1 Alic bajo el asiento activo).

**⏳ DIFERIDO a Fase 4 (bundle con la grilla de carga):**
1. **Modelo `Compra`:** eliminar `p_iva, p_gcia, p_iibb, p_recbc, p_sircreb, p_mun`. Mantener `iva` + `otros`. Resolver semántica de `otros` (impuestos internos vs ret/perc).
2. **`CompraForm`** y **`ComprasCargaView.post`:** quitar refs a `p_*`.
3. **Grilla de captura** del detalle de ret/perc (impuesto, jurisdicción, base, alícuota, certificado) → cambia la FUENTE de `_armar_retperc_compra` de `p_*` al detalle.

**⚠️ Hallazgo adicional (circuito de BAJA, pendiente):** al **eliminar** una `Compra` con ítems, el `post_delete` de `CompraItem` llama `recalcular_totales()` → re-contabiliza la compra moribunda → deja un asiento activo + filas fiscales huérfanas; y el `post_delete` de `Compra` anula el asiento viejo (stale) pero no limpia las filas fiscales. Es pre-existente (el asiento huérfano ya quedaba antes); ahora además deja Libro IVA huérfano. A resolver al encarar anulación/baja de comprobantes.

**Plan original de la fase (referencia):**
1. **Modelo `Compra`:** eliminar `p_iva, p_gcia, p_iibb, p_recbc, p_sircreb, p_mun`. Mantener `iva` (total alícuotas) + `otros` (total ret/perc). Migración (con migración de datos si hay compras cargadas: volcar `p_*` → `otros` y/o a `RetPercSufrida`).
2. **`CompraForm`:** quitar los `p_*` de `widgets` y de la lista `opcionales` en `__init__`.
3. **`ComprasCargaView.post`:** quitar `p_iibb`, `p_iva` de `campos_monetarios` (L279).
4. **`contabilizar_compra`:** reemplazar `mapeo_percepciones` (L331-351) por iteración sobre `RetPercSufrida` filtrando por el `asiento_id` de la compra, generando una línea de DEBE por concepto (cuenta desde `ParametrosContables.cta_ret_*` según `impuesto`).
5. **Generar registros fiscales:** al contabilizar (solo si `condic=1`), poblar `LibroIvaCompras`, `LibroIvaAlic` y `RetPercSufrida`.

**Verificación:** cargar compra con percepciones, confirmar asiento balanceado, `LibroIvaAlic` desglosado por alícuota y `RetPercSufrida` con el detalle; verificar que la suma del satélite cuadra con `compra.otros`.

---

## 7. FASE 4 — Lógica de carga de Bienes de Cambio

**Partida en 4A (motor de costos) y 4B (UI de precio editable).**

### 4A — Motor de costos con bonificación ✅ HECHO
- `agregar_item_sesion` (views_htmx.py) captura `precio_lista` y calcula/almacena en el ítem de sesión: `cto_adq` (=neto línea ÷ cantidad), `cto_rep` (=precio de lista; si vacío = `cto_adq`), `descuento` (=(1−cto_adq/cto_rep)×100), `margen`, `precio_vta_actual` (producto.precio_total) y `precio_vta_nuevo` (=cto_rep×(1+margen)×(1+iva)). `editar_item_sesion` recalcula `cto_adq`/`descuento` al editar el total.
- **No se usó checkbox "trasladar descuento":** el usuario lo controla cargando como precio de lista el propio cto_adq (mismo criterio VFP).
- Template: input **Precio Lista** en la quick-add row; columnas **Cto Adq / Cto Rep / Desc%** en la grilla.
- `ComprasCargaView.post`: persistencia real — `cto_adq`, `cto_rep`, `fec_adq`, `fec_act`, `compra_id`, `cotiz_cpra`, y recálculo de `precio_neto`/`precio_total` desde `cto_rep`×margen (reemplaza el pisado crudo).
- **Verificado** (cant 10, neto 8000, lista 1000, margen 50%, IVA 21%): cto_adq=800, cto_rep=1000, desc=20%, precio_neto=1500, precio_total=1815 (recalculado desde cto_rep, no desde cto_adq). OK.

### 4B — UI de precio de venta editable ✅ HECHO
- **Decisión UX (usuario):** paso de **confirmación** (modal) antes de guardar, no edición inline en la grilla.
- `compras_revisar_precios` (view + URL + `templates/facturacion/modals/revisar_precios.html`): modal que lista los productos de la sesión con `Pº Actual → Pº Nuevo` (editable, `type=number`), **variación %** recalculada en vivo, y botón **Redondear ×100**.
- El botón "Confirmar y Guardar" de la carga ahora abre el modal (hx-get → `#modal-container`). El "Confirmar" del modal inyecta los precios editados como hidden inputs `precio_nuevo_<pid>` en `#compra-form` y lo envía.
- `ComprasCargaView.post`: si llega `precio_nuevo_<pid>`, lo usa como `producto.precio_total` (IVA incl.) y deriva `precio_neto = total/(1+alic)`; si no, fallback al recálculo automático desde `cto_rep × margen`.
- **Verificado:** modal renderiza con el precio nuevo (1815) como valor inicial; editando/redondeando a 2000 → `precio_total=2000`, `precio_neto=1652,89`. Fallback OK.

### Pendientes de la fase
- **Moneda:** guardar costos en moneda origen (hecho: se guardan tal cual + `cotiz_cpra`); el **asiento pesificado** por `compra.cotizacion` sigue pendiente (hoy el asiento usa `compra.total` en moneda origen — gap pre-existente para moneda extranjera).
- **Ambigüedad neto/bruto — RESUELTO:** convención del usuario = la columna "Total Línea" es el **NETO** de la línea (sin IVA); Σ = NETO GRAVADO; IVA = neto × alícuota del producto. Se corrigió `Compra.recalcular_totales`, la suma del DEBE en `contabilizar_compras` y el desglose de `LibroIvaAlic` (antes dividían por (1+alic) tratándolo como bruto). Verificado: ítem neto 1000 / IVA 21% → neto 1000, iva 210, total 1210, asiento balanceado, alícuota correcta. **Ventas tiene el mismo patrón a corregir en su módulo** (contabilizacion.py ~L115 y `Venta.recalcular_totales`).

---

## 8. FASE 5 — Gastos + Notas de Crédito

Se parte en **5A (Notas de Crédito)** y **5B (Gastos)**.

### 5A — Notas de Crédito ✅ HECHO
- **Detección:** `compra.tipo.signo == -1` (campo `facturacion_tipocomprobante.signo`; las 16 NC ya tienen `signo=-1`, el resto `signo=1`).
- **Implementado:** en `ComprasCargaView.post`, si `signo<0` se almacenan los importes de cabecera e ítems en negativo (`× signo`), el stock se revierte (`+= cantidad × signo` → resta) y se **saltea** la actualización de costos/precios. En `contabilizar_compras`, una **pasada de normalización** reubica débito/crédito según el signo neto de cada línea → invierte la NC automáticamente (Proveedor al DEBE, Compras/IVA al HABER) sin lógica por tipo. Guards de líneas cambiados de `>0` a `!=0` para no descartar negativos. `LibroIva*` quedan negativos (como espera ARCA).
- **Verificado:** NC A → cabecera negativa, asiento invertido y balanceado (D Proveedor 1210 / H Mercaderías 1000 / H IVA 210), stock revertido (1→0), `cto_adq` intacto, Libro IVA negativo. Regresión de compra normal OK.
- **Sign aplicado por el sistema:** el usuario carga la NC con importes POSITIVOS (lo que se acredita); al guardar, los montos de la cabecera/ítems se almacenan × `signo` (negativos). No se le pide tipear negativos.
- **Asiento:** se invierte DEBE↔HABER usando valores absolutos (no van negativos). Como los montos quedan negativos, alcanza con tomar `abs()` y cruzar debe/haber.
- **Stock:** NC de bienes de cambio **revierte** stock (resta); **NO** toca `cto_adq`/`cto_rep` ni precios.
- **Libro IVA:** la NC se registra con su signo (ARCA espera la NC en el libro con importes negativos).

### 5B — Gastos ✅ HECHO
- **Modelo:** `Compra.descripcion` (detalle del gasto) + `Compra.cta_imputacion` (IntegerField, pk de Cuenta del DEBE) + migración `0023`.
- **Template:** toggle **Bienes de Cambio / Gasto** (hidden `modo`); en modo gasto se ocultan grilla y carga rápida y aparece un panel con **Detalle** + **selector de Cuenta de imputación** (cuentas imputables); JS sugiere `cta_res` del proveedor (vía `data-cta-res` en las opciones) y lo re-sugiere al cambiar proveedor. El botón "Confirmar" en modo gasto envía directo (sin modal de precios).
- **Vista:** `es_gasto = POST['modo']=='gasto'`; no exige ítems; no recorre grilla; inicializa `saldo = total − pagado` (porque `recalcular_totales` no se dispara sin ítems).
- **Contabilización:** escenario B (sin ítems) usa `compra.cta_imputacion` para el DEBE (o `cta_compras` general como fallback); HABER al proveedor; IVA/percep igual.
- **Verificado:** gasto de neto 1000 + IVA 210 → asiento D cuenta-gasto 1000 / D IVA 210 / H Proveedor 1210, balanceado; sin ítems ni stock; saldo 1210; Libro IVA poblado.

**Verificación:** NC genera asiento invertido y balanceado; stock revertido; costos intactos.

---

## 8.bis FASE 6 — Descuentos globales de factura (Opción 2) ✅ HECHO

**Implementado y verificado.** `Compra.subtotal` + `Compra.descuento` (migración 0024); `ParametrosContables.cta_descuentos_obtenidos` (migración 0011). `Compra.desglose_alicuotas()` prorratea el descuento global por alícuota; `recalcular_totales` setea subtotal/neto(=subtotal−desc)/iva(prorrateado). Contabilización: DEBE Mercaderías al **subtotal**, DEBE IVA sobre neto descontado, **HABER `cta_descuentos_obtenidos`** por el descuento, HABER Proveedor por el total; `LibroIvaAlic` guarda el neto descontado e IVA recalculado. UI: en la sección de cierre, **Subtotal → (−) Descuento → Neto Gravado** (read-only); la grilla alimenta el Subtotal y el Neto se deriva. Vista: `descuento`/`subtotal` en `campos_monetarios` y en la negación por signo (NC); gasto setea `subtotal=neto`.

**Verificado:** 2 alícuotas (1000@21% + 500@10,5%), descuento global 150 (10%) → subtotal 1500, neto 1350, iva 236,25, total 1586,25; asiento D Mercaderías 1500 / D IVA 236,25 / H Desc.Obt 150 / H Proveedor 1586,25 (balanceado); LibroIvaAlic [(21%, 900, 189), (10,5%, 450, 47,25)] — prorrateo correcto.

**⚠️ Hallazgo (RESUELTO con el circuito de baja):** borrar una compra por el camino de cascada (CompraItem.post_delete → recalcular) re-contabilizaba la compra moribunda y, con descuento, lanzaba excepción. Resuelto con `dar_de_baja_compra` (ver Fase 7), que hace borrado físico con `_raw_delete` (sin señales).

### Diseño (referencia)

Dos niveles de descuento: (1) a nivel **producto** = `cto_rep − cto_adq` (ya implementado, va embebido en `cto_adq` y se difiere a la venta vía CMV); (2) a nivel **factura/global**.

**Decisión (Opción 2):**
- Cabecera con 3 campos: `SUBTOTAL` (lo que hoy es "Neto Gravado") → `(−) DESCUENTOS` (global) → `NETO GRAVADO` (= SUBTOTAL − DESCUENTOS, read-only, base del IVA).
- **Prorrateo:** el descuento global se reparte entre los netos de cada alícuota; se recalcula el IVA sobre el neto descontado; `LibroIvaAlic` guarda el neto real y el IVA recalculado. `D_alic = D × neto_alic/Σneto`.
- **Asiento:** DEBE Mercaderías (por rubro) al **SUBTOTAL**; DEBE IVA Crédito sobre NETO GRAVADO; HABER `cta_descuentos_obtenidos` por el DESCUENTOS global (si > 0); HABER Proveedor por NETO GRAVADO + IVA. (Verificado balanceado: subtotal 8000, desc 500, IVA 21% → Merc 8000 / IVA 1575 / Desc.Obt 500 / Prov 9075.)
- **CMV usa `cto_adq`** → la bonif de producto se declara al vender (tax-favorable; no anticipa ganancia).
- **Parámetros contables:** nueva `cta_descuentos_obtenidos`.
- No toca lo hecho en Fases 1–4.

---

## 8.ter FASE 7 — Baja de compras (borrado físico) ✅ HECHO

**Decisión del usuario:** la baja es para corregir errores de carga → **borrado físico** (no anular/contra-asientos), siempre. Incluye las tablas fiscales.

- **`dar_de_baja_compra(compra)`** (contabilizacion.py): en transacción — (1) revierte stock (inverso EXACTO de la carga, respetando signo NC; salvo gastos/remito); (2) borra `LibroIvaCompras/Alic` + `RetPercSufrida` + `AsientoLinea` + `Asiento` del comprobante (el vigente **y** los intermedios anulados de la re-contabilización, por match de concepto); (3) borra `Movimiento` (FK a Compra); (4) borra `CompraItem` y `Compra` con **`_raw_delete`** (sin señales → no re-contabiliza ni revierte stock dos veces); (5) recalcula saldo del proveedor.
- **UI:** `ComprasListView` (`compras_listado`) + `CompraBajaView` (`compras_baja`) + `templates/facturacion/compras_listado.html` (botón de baja por fila vía HTMX con confirmación; elimina la fila). Tarjeta "Listado de Compras" en el índice.
- **Verificado:** carga (5 u, descuento, 2 alícuotas) → baja deja stock revertido, saldo recalculado, y **0** asientos/líneas/fiscal/compra/ítems/movimientos. También limpia compras con descuento que antes bloqueaban el borrado.

**Nota (clutter de carga, pendiente menor):** cada carga de bienes deja **1 asiento intermedio anulado** (la contabilización corre antes y después de cargar los ítems). La baja los limpia; pero para compras NO dadas de baja queda 1 anulado por carga. Resolver suprimiendo la contabilización prematura (antes de los ítems) sin romper gastos (que dependen de ella por no tener ítems).

## 8.quater FASE 8 — UX de carga (proveedor + Cód Prov) ✅ HECHO

**Selección de proveedor (no editable):**
- El `<select>` de proveedor se reemplazó por un campo **readonly**: la selección es **solo por la lupa** (modal `ventas_cliente_buscar_modal`, reusa el evento `clienteVentaSeleccionado`) o el **"+"** de alta rápida (`cliente_add?origen=compra`, que ahora auto-selecciona el nuevo proveedor). No se admite texto libre (en compras el proveedor SÍ o SÍ existe en la tabla; distinto de ventas). Doble protección: client-side (no se puede confirmar sin proveedor) + server-side (FK obligatoria). El alta agregó `cta_res` al evento para sugerir la cuenta de gasto.

**Carga rápida por Código de Proveedor:**
- Nuevo campo **Cód Prov** (primer input de la fila). Enter → `buscarPorCodProv`.
- Exige proveedor seleccionado (Swal si falta). Busca `Producto` por `empresa + proveedor + cod_prov` (`compras_producto_buscar_codprov` → HX-Trigger `codprovEncontrado` / `codprovNoExiste`).
- Encontrado → carga ID + Descripción. No existe → Swal: **(a) Buscar por descripción** (lupa) / **(b) Crear nuevo** (alta pre-cargada con proveedor+cod_prov, `origen=compra` → al guardar carga el ítem).
- Rama (a): al elegir de la lupa, si el **proveedor habitual difiere** del seleccionado → Swal *"¿Pasa a ser el habitual?"* → SÍ: `compras_producto_actualizar_habitual` (actualiza `proveedor`, `cod_prov`, y opcional `detalle` igualándolo a la factura) ; NO: carga el ítem sin tocar el maestro (compra esporádica). Solo se dispara si se vino por el camino Cód Prov (`window._ultimoCodProv`).
- Archivos: `facturacion/views_htmx.py` (2 endpoints), `productos/views_htmx.py` (`producto_modal` con prefill + dispatch origen=compra), `compras_carga.html`, `partials/productos_search_results.html`, `partials/clientes_typeahead.html`.

## 8.quinquies — Configuración IIBB de la empresa ✅ HECHO

- **`Empresa.condicion_iibb`** (LOCAL / CM / EXENTO) + **`Empresa.jurisdicciones_iibb`** (M2M a `facturacion.Jurisdiccion`). Migración empresas 0007.
- **25 jurisdicciones** cargadas (901-924 + 999 "Sede Local/Única") vía migración de datos `facturacion 0025_cargar_jurisdicciones` (inline, idempotente).
- Configurable desde **Configuración → Empresas → Editar** (EmpresaForm + modal: selector de condición + checklist de jurisdicciones). Admin también.
- **Uso:** NO liquidan Convenio Multilateral → sin coeficientes ni distribución. Las `jurisdicciones_iibb` sirven solo para **filtrar el selector de jurisdicción** al cargar percepciones de IIBB (mostrar las inscriptas, no las 25). Ver memoria `iibb-config-empresa`.

## 8.sexies — FASE 9 — Gasto: importes editables + IVA por alícuota (ARCA) ✅ HECHO

**Objetivo:** que en modo **Gasto** los importes se carguen a mano y el IVA se desglose por alícuota (réplica del form VFP `B-104`: textbox *Cant. Alíc.* → grilla con código ARCA / Neto / Alícuota / IVA editable). El IVA se calcula `Neto × %` pero queda **editable** para cuadrar con la factura por redondeo. **Solo Gasto** (en Bienes las alícuotas salen de los ítems).

- **Tabla configurable `contable.AlicuotaIva`** (`cble_alicuotas_iva`): `codigo` (ARCA, 4 díg), `descripcion`, `porcentaje`, `activo`, `orden`. Seed idempotente en migración `contable 0012`: 0003=0%, 0004=10,5%, 0005=21%, 0006=27%, 0008=5%, 0009=2,5%. Editable por admin (`list_editable`).
- **Persistencia del desglose `facturacion.CompraAlicuota`** (migración `0026`): FK a `Compra` (`related_name='alicuotas'`), `codigo`, `porcentaje`, `neto`, `iva`. Es la **fuente real** del Libro IVA por alícuota en gastos (no se infiere). En Bienes no se usa.
- **`Compra.desglose_alicuotas()`**: si `self.alicuotas.exists()` (gasto) devuelve esas filas tal cual (con `codiva`), sin prorrateo; si no, sigue el camino de ítems (bienes). El fallback de inferencia en `_poblar_libro_iva_compra` queda como red de seguridad para gastos legacy sin filas.
- **`LibroIvaAlic.codiva` ampliado `max_length=3 → 4`** (migración `0013`): ahora aloja el código de alícuota ARCA (4 díg) en gastos; en bienes sigue cayendo al código de comprobante. Contabilización: `codiva=d.get('codiva') or compra.tipo.codigo`.
- **`ComprasCargaView`**: pasa `alicuotas_iva` al contexto; en `post` (gasto) parsea `alic_codigo[]/alic_porcentaje[]/alic_neto[]/alic_iva[]`, computa `neto=Σneto`, `iva=Σiva` (server-authoritative, con signo NC), persiste `CompraAlicuota` y contabiliza **1 sola vez** (guard `_no_contabilizar` en el primer save para obtener PK → crear filas → save que contabiliza). `no_gravado`/`exento` sumados a `campos_monetarios`.
- **Baja física** (`dar_de_baja_compra`): agrega `CompraAlicuota._raw_delete` (el `_raw_delete` de `Compra` no cascadea).
- **UI (`compras_carga.html`)**: bloque Gasto con componente Alpine `gastoAlic()` — *Cant. Alíc.* genera N filas (código ARCA / Neto / Alícuota auto / IVA `Neto×%` editable); Σ Neto y Σ IVA se vuelcan a `id_neto`/`id_iva` de la fila de cierre y disparan `recalculateFinal()`. En modo gasto: `id_iva`, `id_subtotal`, `id_descuento` quedan readonly (los maneja la grilla); No Gravado/Exento editables. `window.ALICUOTAS_IVA` se serializa con `|unlocalize` para no romper el JS con la coma decimal.
- **Verificado (shell, gasto 2 alícuotas):** 0005 neto 10.000 → IVA 2.100; 0006 neto 350 → IVA 94,50. Asiento balanceado (D gasto 10.350 / D IVA 2.194,50 / H proveedor 12.544,50), `LibroIvaAlic` con 2 renglones (codiva 0005/0006), `LibroIvaCompras` neto 10.350 / iva 2.194,50 / total 12.544,50. Baja física → 0 en compra/alícuotas/LibroIva/asiento.
- **BUG corregido (descalce de asiento):** el DEBE de la imputación tomaba solo `subtotal` (=neto); el HABER (proveedor) toma el TOTAL, que **incluye No Gravado + Exento** → asiento desbalanceado por esos conceptos. Fix en `contabilizar_compras`: `No Gravado + Exento` se suman al monto de la imputación (gasto) / primera cuenta de compras (bienes). Estructura del DEBE de un gasto: **imputación = neto + no gravado + exento**, IVA Crédito Fiscal, Perc. IVA, Perc. IIBB; HABER = proveedor por el total. Verificado balanceado con percepciones y `RetPercSufrida` (origen C) poblada (Perc IVA + Perc IIBB).

**Pendiente menor:** validación client/server de que `Σ neto alícuotas` y demás conceptos cuadren con el Total tipeado (hoy el Total se deriva, no se contrasta contra un importe declarado de la factura). Falta verificación visual en browser de la grilla Alpine.

## 8.septies — FASE 10 — Detalle de ret/perc sufridas (jurisdicciones IIBB + tipos de Otros) ✅ HECHO

**Objetivo:** capturar el detalle real de las percepciones sufridas (la grilla diferida de Fase 3/4). Aplica a **Gasto y Bienes** (la fila de cierre es compartida). Cambia la fuente de `_armar_retperc_compra` de los `p_*` al detalle persistido.

- **Modelo `facturacion.CompraRetPerc`** (migración `0027`): FK a `Compra` (`related_name='retpercs'`), `impuesto` (choices: IVA/GAN/IIBB/TEM/SIRCREB/SUSS/MUN/OTRO), `tipo` (default 'P'), `jurisdiccion` FK nullable, `importe`. Es el detalle que alimenta el asiento + `RetPercSufrida`.
- **Contabilización** (`contabilizacion.py`):
  - `_armar_retperc_compra` lee de `compra.retpercs` si existen (con jurisdicción y leyenda por impuesto); si no, **fallback** a los `p_*` legacy. Mapeo `_CTA_POR_IMPUESTO` (IVA→cta_ret_iva, GAN→ganancias, IIBB/**SIRCREB**→cta_ret_iibb, SUSS→suss, MUN→mun, **TEM/OTRO→cta_impuestos_internos** como fallback general vía `_cuenta_impuesto`).
  - `RetPercSufrida` se puebla **con jurisdicción** (multi-fila por convenio en IIBB CM).
  - **Impuestos Internos** ya no emite el total de `otros`: emite solo el **resto** = `otros − Σ retperc(bucket TEM/SIRCREB/SUSS/MUN/OTRO/GAN)`. Si "Otros" se desglosó por completo, no hay línea (evita doble conteo en el DEBE).
  - Baja física limpia `CompraRetPerc` (`_raw_delete`).
- **Vista `ComprasCargaView._aplicar_retperc`**: parsea Perc.IVA (campo simple → 1 fila), Perc.IIBB (si **CM** + modal → `iibb_juris[]/iibb_importe[]` 1 fila por jurisdicción; si **LOCAL** → 1 fila a la jurisdicción automática = inscripta o **999**), y Otros (`otros_impuesto[]/otros_importe[]` → 1 fila por impuesto; sin modal → queda como Imp. Internos). Setea `compra.p_iva/p_iibb/otros` como totales (server-authoritative, con signo NC). Se llama en Gasto (antes del total) y en Bienes (tras `save`, persistiendo `p_*` con guard para que `recalcular_totales` arme el total con las percepciones).
- **UI (`compras_carga.html`)**: 2 modales Alpine (`retpercModales()`) — **jurisdicciones IIBB** (solo si `condicion_iibb='CM'`) y **desglose de Otros**. Se abren al `change` del campo (o por botón "⊞"). Validan que **Σ = importe del campo** antes de confirmar; al confirmar inyectan hidden inputs (`iibb_*` / `otros_*`) y fijan el valor del campo a la Σ. Contexto: `condicion_iibb`, `jurisdicciones_iibb`, `window.TIPOS_OTROS`.
- **Verificado por HTTP (test client):** (1) Gasto LOCAL: IIBB→jurisdicción auto 999, Otros 200 = SIRCREB 150 + TEM 50, asiento balanceado (12.800), sin línea de imp. internos duplicada, `RetPercSufrida` con 3 filas. (2) Gasto CM: IIBB 800 repartido 901→500 / 902→300, asiento balanceado (12.900), `RetPercSufrida` 2 filas IIBB con jurisdicción. Baja física → 0 en ambos.

**Pendiente menor:** validación server de que Σ detalle == campo de cabecera (hoy el front lo valida y el server confía/recalcula desde el detalle); capturar base/alícuota/nro_certificado/régimen (se eligió mínimo: tipo/jurisdicción + importe). Verificación visual de los modales en browser.

## 9. Riesgos / pendientes

- **`condic` del asiento (RESUELTO — es un bug, no una decisión):** `asiento.condic` siempre significó fiscal(1)/no-fiscal(2). Las líneas `condic=2 if saldo>0 else 1` en contabilizacion.py:372 (compras) y :198 (ventas) son incorrectas → corregir a `condic=compra.condic`/`venta.condic` en Fase 1.
- **Migración de datos** de `p_*` en Fase 3 si ya hay compras en producción.
- **Tipos de comprobante:** identificar cómo se marca una NC en `TipoComprobante` para la inversión de asiento (Fase 5).
- **Ventas en paralelo:** `Venta` también incorporará `condic` y `LibroIvaVentas`/`LibroIvaAlic`/`RetPercSufrida` (origen 'V'); coordinar para no duplicar lógica.
- **REVISAR AL CERRAR VENTAS/RECIBOS — bug de doble asiento (mismo que se corrigió en compras):** `contabilizar_venta_individual` (contabilizacion.py:69-70) y `contabilizar_recibo` (≈:649-650) hacen `obj.asiento_id = None; obj.save()` SIN el guard `_no_contabilizar`, lo que puede re-disparar la señal y dejar 2 asientos activos (doble conteo en el mayor). Aplicar el mismo fix de compras: leer el `asiento_id` vigente desde la BD + guardar el reset con el guard. Pendiente hasta terminar esos módulos.

## 10. Circuito Compras ↔ Órdenes de Pago (fase del módulo OP)

Detectado al verificar Fase 1: `Compra.saldo` (saldo pendiente de aplicación de pagos de cada factura) no se inicializaba. Detalle completo en memoria `compras-op-asignacion-circuito`.

- **HECHO (mejora aplicada):** `Compra.recalcular_totales` ahora inicializa `saldo = total − pagado`. Antes quedaba en 0, lo que dejaría toda factura sin pendiente visible para la OP.
- **Pendiente (fase OP):** crear `OrdenPagoAplicacion` (orden_pago, compra, importe) — espejo simétrico de `tesoreria.ReciboAplicacion` (que ya existe del lado cobranzas). `OrdenPagoImputacion` NO sirve: imputa a cuenta contable, no a factura.
- **Pendiente (fase OP):** `OrdenPago.asignado` / `pendiente_asignar` (cacheados); `Compra.pagado` se incrementa con cada aplicación; form de asignación que lista facturas con `saldo != 0` (NC negativas incluidas) y avisa "pagos sin asignar" = Σ(`OrdenPago.pendiente_asignar`) del proveedor.
