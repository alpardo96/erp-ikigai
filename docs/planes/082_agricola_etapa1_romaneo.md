# Plan 082 — Agrícola Etapa 1: Romaneo (Recepción y Clasificación)

## Estado: 🔶 En Progreso

**Fecha:** 2026-09-06
**Plan integral:** [`docs/agricola/plan inicial agricola.md`](../agricola/plan%20inicial%20agricola.md) — Etapa 1
**Requiere:** [Plan 080](080_terminos_enchufables_saldos_stock.md) ✅ · [Plan 081](081_agricola_etapa0_maestros_tabaco.md) ✅

---

## Objetivo

Registrar la recepción física del tabaco del productor y su clasificación **fardo por fardo**,
con el precio formado desde la lista vigente y **congelado** en cada fardo.

**Sin ningún efecto contable, de stock ni de cuenta corriente.** El romaneo es un hecho físico y
comercial; la deuda con el productor nace recién en la Etapa 2, al liquidar.

---

## 1. Alcance

### Incluido
- `RomaneoTabaco`, `FardoTabaco` y `ReclasificacionFardo`, con sus migraciones.
- Pantalla de carga tipo carrito: se elige clase, se tipean los kilos y el precio se calcula en
  vivo; los totales y la estadística por grupo se actualizan con cada fardo.
- Congelamiento de ponderante, coeficiente y precio.
- Confirmación con numeración correlativa atómica y bloqueo de edición.
- Anulación auditada; reclasificación que **no** sobrescribe el original.
- Listado, detalle e impresión del romaneo.

### Fuera de alcance
- Liquidación, comprobante, asiento, Libro IVA, retenciones (Etapa 2).
- Movimiento de stock (Etapa 4): el término del Plan 080 se registra ahí, no acá.
- Lotes de acopio y acondicionamiento (Etapa 5).

---

## 2. Decisiones de diseño

### 2.1 El borrador se persiste; no va a la sesión

El patrón de carrito del ERP (`facturacion/views_htmx.py`) guarda los ítems en
`request.session`. **Acá no sirve**: un romaneo real tiene cientos de fardos, y una sesión con
800 diccionarios se reescribe entera en cada alta.

El romaneo se crea en estado **BORRADOR** al abrir la pantalla y cada fardo se graba como fila.
Además de escalar, da recuperación ante caída: si el navegador se cierra con 300 fardos cargados,
no se perdió nada. Es el mismo criterio del sistema heredado, que usaba una tabla de staging
(`aux_tab_compra_mov`) y no memoria.

### 2.2 Un fardo es una fila del detalle

En el sistema heredado la cantidad de fardos era el `COUNT` de las líneas del detalle. Se
mantiene: **cada fila es un fardo**, con su clase, sus kilos y su precio. Es lo que después
permite el margen unitario por fardo (Etapa 5) y la trazabilidad hasta la venta.

### 2.3 Qué se congela y por qué

Al agregar un fardo se copian en la fila el **ponderante**, el **coeficiente** y el **precio
unitario** vigentes en ese momento. El precio de una operación es un hecho histórico: si en
agosto se renegocia la lista, un romaneo de marzo no puede cambiar de importe.

El romaneo guarda además la FK a la `ListaPrecioTabaco` aplicada, para poder reconstruir de dónde
salió cada número.

### 2.4 Numeración

Se usa el contador atómico del core (`core.services.numeracion.siguiente_numero`), con un tipo de
documento nuevo `ROMANEO_TABACO`. Es un agregado de una línea a `ContadorDocumento.TIPOS_DOCUMENTO`,
con el precedente de Distribución, que ya tiene ahí sus `PEDIDO`, `REPARTO` y
`RECEPCION_DEVOLUCION`.

El número se asigna **al confirmar**, no al abrir el borrador, para no dejar huecos en la serie.

### 2.5 La reclasificación no borra

Corregir la clase de un fardo genera una fila en `ReclasificacionFardo` con la clase, el
coeficiente y el precio anteriores y los nuevos, el motivo y el usuario. El fardo queda con los
valores nuevos, pero **el original es reconstruible**. Sólo se admite sobre romaneos confirmados
y no liquidados.

---

## 3. Modelos

| Modelo | `db_table` | Campos clave |
|---|---|---|
| `RomaneoTabaco` | `agricola_tabaco_romaneo` | empresa, sucursal, punto, numero, fecha, productor (FK `ClienteProveedor`), variedad, campania, lista_precio, **ponderante_aplicado**, coeficiente_productor, transporte, remito, total_kilos, total_fardos, total_importe, adicional, precio_promedio, porcentaje_ponderante, estado, `condic`, motivo_anulacion, auditoría |
| `FardoTabaco` | `agricola_tabaco_fardo` | romaneo, numero_fardo, etiqueta, clase, **coeficiente_aplicado**, **precio_aplicado**, kilos, importe, adicional, precio_final, estado, clasificado_por, clasificado_el |
| `ReclasificacionFardo` | `agricola_tabaco_reclasificacion` | fardo, clase_anterior, coeficiente_anterior, precio_anterior, clase_nueva, coeficiente_nuevo, precio_nuevo, kilos, motivo, usuario, fecha |

### Estados

`RomaneoTabaco`: `BORRADOR (1) → CONFIRMADO (2) → LIQUIDADO (3)` · `ANULADO (9)`
`FardoTabaco`: `RECIBIDO (1) → CLASIFICADO (2) → EN_LOTE (3) → ACONDICIONADO (4) → VENDIDO (5)`

Un romaneo confirmado no se edita. Un romaneo liquidado no se anula: se anula la liquidación
primero (Etapa 2).

### Restricciones

- `kilos > 0` e `importe >= 0` en `FardoTabaco`.
- `coeficiente_aplicado > 0` y `precio_aplicado >= 0`.
- `total_kilos >= 0`, `total_fardos >= 0` en el romaneo.
- Único `(empresa, punto, numero)` para romaneos con número asignado.
- Único `(romaneo, numero_fardo)`.
- Único `(empresa, etiqueta)` cuando la etiqueta no está vacía.

---

## 4. Servicios

| Servicio | Archivo | Qué hace |
|---|---|---|
| `abrir_romaneo` | `services/romaneo.py` | Crea el borrador con la lista de precio vigente congelada |
| `agregar_fardo` | idem | Valida clase/variedad, calcula y congela precio, recalcula totales |
| `editar_fardo` / `quitar_fardo` | idem | Sólo en borrador |
| `recalcular_totales` | idem | Kilos, fardos, importe, PPP y % sobre ponderante, desde el detalle |
| `confirmar_romaneo` | idem | Atómico: numera, cambia estado, bloquea edición |
| `anular_romaneo` | idem | Con motivo; no borra fardos |
| `reclasificar_fardo` | idem | Versiona la clasificación anterior y recalcula |
| `estadistica_por_grupo` | idem | Kilos, fardos y % por grupo de clase, derivado del maestro |

Todo servicio con múltiples efectos corre en `transaction.atomic()`; `confirmar_romaneo` toma
`select_for_update()` sobre el romaneo para que dos confirmaciones simultáneas no numeren dos veces.

---

## 5. Interfaz

- **Pantalla de carga**: cabecera (productor, variedad, campaña, fecha, transporte) + carrito de
  fardos. Al elegir la clase se muestran coeficiente y precio; al tipear los kilos se calcula el
  importe. Totales y estadística por grupo se refrescan con cada alta.
- **Typeahead + Lupa** obligatorio en productor y clase.
- **Formato es-AR**: `.fInputAR` en kilos e importes, `|formato_ar` en los displays.
- **Listado** con filtros por productor, variedad, campaña, estado y fechas, más el filtro de
  `condic` que exige el proyecto.
- **Impresión** del romaneo con el detalle por fardo y el resumen por grupo.

---

## 6. Tests mínimos

| Test | Qué verifica |
|---|---|
| `test_precio_se_congela_al_agregar` | Cambiar la lista después no altera el fardo ya cargado |
| `test_precio_contra_datos_reales` | Los 6 casos del sistema heredado, al centavo |
| `test_totales_se_derivan_del_detalle` | Kilos, fardos, importe, PPP y % sobre ponderante |
| `test_estadistica_por_grupo` | Incluye el grupo H, que el sistema heredado perdía |
| `test_no_se_puede_agregar_clase_de_otra_variedad` | Validación de coherencia |
| `test_sin_lista_aprobada_no_se_abre` | Sin ponderante vigente no hay precio posible |
| `test_confirmar_numera_correlativo` | Serie sin huecos |
| `test_confirmar_dos_veces_no_renumera` | Idempotencia |
| `test_romaneo_confirmado_no_admite_fardos` | Edición bloqueada |
| `test_anular_conserva_los_fardos` | La anulación no destruye el registro físico |
| `test_reclasificar_versiona_el_original` | La clasificación previa queda reconstruible |
| `test_reclasificar_recalcula_totales` | El importe del romaneo acompaña |
| `test_aislamiento_multiempresa` | No se ven ni se editan romaneos de otra empresa |
| `test_pantallas_renderizan` | Listado, carga, detalle e impresión |

---

## 7. Criterio de Hecho

- [ ] Modelos, restricciones y migraciones aplicados.
- [ ] `ROMANEO_TABACO` agregado al contador del core, con su migración.
- [ ] Servicios con transaccionalidad y bloqueo en la confirmación.
- [ ] Pantallas con Typeahead + Lupa y formato es-AR.
- [ ] Tests en verde.
- [ ] Prueba de desenchufe.
- [ ] Suite completa sin fallas nuevas (baseline: 15 preexistentes).
- [ ] `docs/walkthrough.md` actualizado.
