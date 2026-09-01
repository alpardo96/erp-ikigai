# Plan 027 — Módulo de Carga de Ventas

> **Estado:** Diseño aprobado (2026-06-29). Pendiente de ejecución.
> **Memoria asociada:** `compras-modulo-spec`, `libro-iva-retenciones-arquitectura`, `tesoreria-arquitectura-cajas`, `preferencia-ux-simple-por-fuera` (ver `MEMORY.md`).
> **Planes relacionados:** 019 (Preventa y Autorizaciones), 022 (Caja Mostrador y Autorizaciones), 026 (Compras, Libro IVA y `condic`).
> **Para retomar:** Sesión de estructuración (no de código). El diseño quedó congelado en este documento; falta implementar.

---

## 1. Objetivo

Estructurar el módulo de **Carga de Ventas** (facturación directa, no minorista de mostrador) sobre la tabla `Venta`/`VentaItem` ya existente, incorporando:

- Selector **REAL / PRESUPUESTADO** (`condic`) con doble circuito contable/no-fiscal.
- Entidad **`PuntoVenta`** colgada de `Sucursal` (desacople de la numeración respecto de la sucursal).
- **Letra** del comprobante (A/B/X) derivada de la condición IVA del cliente.
- **Precio no editable** (traído de lista de precios) con **descuento** sujeto a **autorización en tiempo real** reutilizando el formulario de autorización de Caja Mostrador.
- **Numeración automática** por punto de venta.

> **Alcance:** Este módulo es la **carga directa/administrativa** de una factura de venta. NO es el circuito minorista Preventa → Caja Mostrador (planes 019/022); ese ya está resuelto y tiene su propia autorización aguas arriba (en Preventa). Acá no hay cliente parado en un mostrador.

---

## 2. Decisiones de diseño congeladas

1. **REAL / PRESUPUESTADO (`condic`):** optiongroup en la cabecera → `condic` (1=Real/fiscal, 2=Presupuestado/no-fiscal). Se reusa la **convención de UI ya establecida** (rótulo "REAL / PRESUPUESTADO" aunque el significado interno sea fiscal/no-fiscal — ver plan 026 §5). Hoy `Venta` **no tiene** `condic` (sí lo tiene `Compra`): se agrega.

2. **Doctrina del doble circuito (fijada "de una vez por todas", para compras Y ventas):**

   | `condic` | Contabiliza (asiento) | Stock | Tratamiento fiscal | IVA / ret-perc |
   |---|---|---|---|---|
   | **1 — Real** | Sí | Sí | **Sí** (Libro IVA, posiciones) | Sí |
   | **2 — Presupuestado** | **Sí** | **Sí** | **No** | **No** |

   - **El Libro IVA (compras y ventas) SIEMPRE filtra `condic = 1`.**
   - Las `condic = 2` son **operaciones verdaderas**, contabilizadas y con stock real, **sujetas a análisis gerencial/interno**, pero **sin tratamiento impositivo** (no discriminan IVA, no llevan ret/perc — consistente con plan 026 §5).
   - El `condic` se guarda en `Venta.condic` **y** se etiqueta en el encabezado del asiento (que siempre significó fiscal/no-fiscal), para poder separar circuitos en reportes.

3. **Una sola tabla, dos lentes:** `condic = 2` se almacena en `Venta`/`VentaItem` igual que `condic = 1`. No hay tabla ni circuito de almacenamiento paralelo. El filtro impositivo las ignora; los listados de gestión las incluyen mediante **filtro opcional** (Real / Presupuesto / **Todas**), igual que hoy en Compras (`facturacion/views.py:246`).

4. **`PuntoVenta` desacoplado de `Sucursal`:** se crea el modelo `PuntoVenta` (FK a `Sucursal`). La numeración del comprobante cuelga del **punto de venta**, no de la sucursal. Hoy se crea **un** PV por sucursal (operación idéntica a la actual); el día que aparezca un segundo PV es un alta de registro, sin refactor. El flag **`es_fiscal`** ata el doble circuito: PV fiscal → comprobantes REAL; PV no-fiscal dedicado → comprobantes PRESUPUESTADO.

5. **Letra del comprobante (derivada, sin AFIP):** se calcula al confirmar la Venta y se persiste en `Venta.letra`:

   ```
   si condic == 2 (Presupuestado)                         → "X"
   si condic == 1 y cliente.condicion_iva == "CONSUMIDOR FINAL" → "B"
   en cualquier otro caso (RI / Monotributo / Exento)     → "A"
   ```

   - El `TipoComprobante` sigue siendo el **"qué"** (Factura, NC, Remito); la **letra es un atributo derivado aparte** sobre la `Venta`.
   - En **Compras** la letra **no se deriva** (viene en la factura del proveedor). Esta regla es exclusiva de Ventas.
   - Decisión literal del usuario: Monotributo y Exento → **"A"** (no se contempla el caso de empresa emisora Monotributo, que emitiría "C"; el sistema asume empresa Responsable Inscripto).

6. **Precio no editable:** en la carga, `precio_unitario` se trae **bloqueado (readonly)** de la lista de precios del producto. El operador nunca tipea precio; lo único editable a nivel línea es el **descuento %**.

7. **Descuento con autorización en tiempo real:**
   - Se agrega `porcentaje_descuento` a `VentaItem` (hoy solo lo tiene `PreventaItem`).
   - Si algún ítem supera `Rubro.descuento_maximo`, la Venta requiere autorización **a nivel comprobante** (criterio idéntico a Preventa: `facturacion/views_htmx.py:960`).
   - **Flujo remoto sincrónico:** la factura queda **retenida** (sin número fiscal, sin asiento, sin stock), aparece en el **formulario de autorización de Caja Mostrador** (compartido — "en definitiva es lo mismo"); el responsable autoriza **desde su propia PC**; la pantalla del operador hace **polling HTMX** y **cierra la factura sola** al detectar la aprobación. El responsable **no se traslada**.
   - **El listado de autorización identifica al vendedor.**
   - **Auditoría:** la Venta guarda `autorizado_por` (FK User) y `fecha_autorizacion`.

8. **Permisos de autorización (ya existen, sin modelos nuevos):**
   - `Perfil.es_admin_sistema` → **potestad permanente** (uno o varios administradores; siempre pueden autorizar).
   - `Perfil.permiso_autorizar_descuentos` → **facultad delegable y revocable** que un administrador enciende/apaga por usuario. La "temporalidad" (viajes/vacaciones) se maneja a mano (otorgar y revocar), sin rango de fechas ni caducidad automática.
   - El "dueño" es un concepto **informativo**, no un rol del sistema. La validación reusa la existente: `perfil.permiso_autorizar_descuentos or perfil.es_admin_sistema` (`facturacion/views.py:211`).

9. **Numeración automática:** secuencial por **`(empresa, punto_venta, tipo)`**, replicando el patrón ya probado en Recibos (`tesoreria/models.py:131`). El número se asigna **al confirmar** (después de la autorización, si la hubo).

10. **Diferido a etapa AFIP:** CAE, vencimiento de CAE y código QR (los campos `cae`, `vto_cae`, `cod_qr` ya existen en `Venta`, pero quedan sin uso en este plan). La **letra NO está diferida** (es determinística, ver §5).

---

## 3. Estado actual del código (puntos de anclaje)

- **`facturacion/models.py`**
  - `Venta` (`:422`): ya tiene `tipo` (FK `TipoComprobante`), `punto` (IntegerField suelto), `numero`, `sucursal`, `cliente`, importes, `estado` (0=Activa / 1=Anulada), `cae/vto_cae/cod_qr`. **Falta:** `condic`, `punto_venta`, `letra`, estado de autorización, `autorizado_por`, `fecha_autorizacion`.
  - `VentaItem` (`:525`): tiene `precio_unitario`, `iva_alicuota`, bimonetarismo. **Falta:** `porcentaje_descuento`.
  - `TipoComprobante` (`:6`): `codigo`, `detalle`, `signo`, `estado`. Sin letra (correcto: la letra va en `Venta`).
  - `ClienteProveedor.condicion_iva` (`:87`): choices `RESPONSABLE INSCRIPTO` / `MONOTRIBUTO` / `EXENTO` / `CONSUMIDOR FINAL`. **Insumo de la regla de letra.**
  - `Compra.condic` (`:176`): `IntegerField(default=1)` sin choices — modelo a homologar con el `IntegerChoices` compartido.
- **`empresas/models.py`**
  - `Sucursal` (`:33`): solo `empresa`, `nombre`, `direccion`, `telefono`. **Sin punto de venta** → aquí cuelga el nuevo `PuntoVenta`.
- **`productos/models.py`**
  - `Rubro.descuento_maximo` (`:25`): tope de descuento por rubro (ya existente).
- **`facturacion/views.py`**
  - `AutorizacionesPreventaView` (`:208`): bandeja/ventana de autorización a reutilizar/ampliar.
  - Validación de permiso (`:211`) y filtro `condic` en grilla (`:246`).
- **`facturacion/views_htmx.py`**
  - Evaluación de exceso de descuento (`:960`), modal de autorización (`:1031`).
- **`tesoreria/models.py`**
  - Auto-numeración de Recibos (`:131`) — patrón a replicar.
- **`facturacion/signals.py`**
  - El asiento se anula con `estado = 1` (`:55`). **Atención:** ampliar estados de `Venta` sin romper esta lógica (ver §5 de Riesgos).

---

## 4. Cambios en Modelos

### 4.1 `IntegerChoices` compartido (nuevo, p. ej. `facturacion/choices.py`)

```python
class Condicion(models.IntegerChoices):
    REAL = 1, "Real"
    PRESUPUESTADO = 2, "Presupuestado"
```

Se aplica a `Venta.condic` (nuevo) y se homologa `Compra.condic` (hoy sin choices). Reusable también en Tesorería.

### 4.2 `empresas/models.py` — `PuntoVenta` (nuevo)

```
PuntoVenta(AuditModel)
├─ sucursal       (FK → Sucursal, PROTECT)
├─ numero         (IntegerField)            # los 4 dígitos del PV
├─ es_fiscal      (BooleanField, default=True)
├─ tipo_emision   (CharField choices: ELECTRONICO / CONTROLADOR / MANUAL)
├─ descripcion    (CharField, nullable)
├─ predeterminado (BooleanField, default=False)
└─ estado         (BooleanField, default=True)
Meta: unique_together = ('sucursal', 'numero')
```

### 4.3 `facturacion/models.py` — `Venta` (ampliar)

- `condic` → `IntegerField(choices=Condicion.choices, default=Condicion.REAL)`.
- `punto_venta` → `FK(PuntoVenta, PROTECT, null=True)` (fuente de verdad de la numeración).
- `punto` → se conserva como **mirror denormalizado** (`punto_venta.numero`) para compatibilidad con consultas/plantillas existentes.
- `letra` → `CharField(max_length=1)` (A/B/X), calculado al confirmar.
- **Estado de autorización** → ver §5 de Riesgos (se resuelve con campo separado para no romper `signals.py`).
- `autorizado_por` → `FK(User, null=True, SET_NULL)`.
- `fecha_autorizacion` → `DateTimeField(null=True)`.

### 4.4 `facturacion/models.py` — `VentaItem` (ampliar)

- `porcentaje_descuento` → `DecimalField(max_digits=5, decimal_places=2, default=0)`.

---

## 5. Migraciones y riesgos

1. **Schema:** alta de `PuntoVenta`; alta de campos en `Venta`/`VentaItem`; choices en `Compra.condic`.
2. **Data migration `PuntoVenta`:** crear un `PuntoVenta` por cada `(sucursal, punto)` distinto presente en `Venta` (y un PV no-fiscal dedicado donde corresponda); backfill de `Venta.punto_venta`. Marcar un `predeterminado` por sucursal.
3. **Backfill `letra`:** recalcular para ventas históricas según la regla §2.5 (con la `condicion_iva` del cliente vigente).
4. **RIESGO — colisión de estados:** `Venta.estado` hoy es 0=Activa / 1=Anulada y `signals.py:55` anula el asiento con `estado = 1`. **No** se reutiliza ese campo para "Pendiente Autorización". Se resuelve con un **campo/estado separado** (p. ej. `requiere_autorizacion` + `autorizada`, o un `estado_aut`) que **bloquee la confirmación** (número/asiento/stock) hasta la aprobación, dejando `estado` intacto para el ciclo fiscal Activa/Anulada. La generación de asiento y el movimiento de stock se **guardan** detrás de "venta confirmada".

---

## 6. Lógica de negocio

- **Derivación de letra:** método en `Venta` (`_calcular_letra()`), invocado al confirmar.
- **Numeración:** en el `save()`/confirmación, secuencia `(empresa, punto_venta, tipo)` con `select_for_update()` dentro de `transaction.atomic()` para evitar duplicados (patrón Recibos).
- **Asiento + Stock:** se disparan **solo al confirmar** (post-autorización). El asiento se etiqueta con `condic`. `condic = 2` genera asiento y mueve stock pero **no** alimenta Libro IVA ni discrimina IVA/ret-perc.
- **Autorización (tiempo real):**
  - Al cerrar con exceso → Venta retenida + solicitud visible en la ventana de autorización (compartida con Caja Mostrador), con **vendedor** identificado.
  - Responsable autoriza desde su PC (`permiso_autorizar_descuentos or es_admin_sistema`).
  - Pantalla del operador con `hx-trigger="every Ns"` sobre su solicitud → al detectar aprobación, confirma y cierra.
  - Rechazo → el operador vuelve a editar el descuento.

---

## 7. Flujo de vistas (HTMX)

1. **Cabecera de Venta:** optiongroup REAL/PRESUPUESTADO; selector de Cliente (Typeahead + Lupa) que setea `condicion_iva` para la letra; selector de **PuntoVenta** (Typeahead + Lupa) **filtrado por `es_fiscal` según `condic`**.
2. **Ítems:** búsqueda de producto (Typeahead + Lupa); `precio_unitario` **readonly**; input de **descuento %** con validación contra `Rubro.descuento_maximo` (badge "requiere autorización").
3. **Cierre:** si no hay exceso → confirma directo (numera, asienta, stock). Si hay exceso → retiene y entra al flujo de autorización en tiempo real.
4. **Ventana de autorización (compartida):** ampliar `AutorizacionesPreventaView` para listar también solicitudes de Venta, mostrando el **vendedor**; aprobar/rechazar.
5. **Grilla de Ventas:** filtro `condic` (Real / Presupuesto / Todas) con la letra y el punto de venta visibles.

---

## 8. Validaciones de base de datos

- `PuntoVenta`: `unique_together('sucursal', 'numero')`.
- `Venta`: unicidad de numeración por `(empresa, punto_venta, tipo, numero)` (CheckConstraint/unique sobre el confirmado).
- Coherencia `condic` ↔ `punto_venta.es_fiscal` (validación a nivel form/clean: REAL exige PV fiscal; PRESUPUESTADO exige PV no-fiscal).
- `porcentaje_descuento` entre 0 y 100.

---

## 9. Plan de pruebas

**Automatizadas (pytest/Django TestCase):**
- Derivación de letra: CF→B, RI/Mono/Exento→A, condic=2→X.
- Numeración secuencial concurrente por `(empresa, punto_venta, tipo)` (sin duplicados bajo `select_for_update`).
- `condic=2` genera asiento + stock pero **no** aparece en Libro IVA (query filtra `condic=1`).
- Filtro `es_fiscal` del selector de PV según `condic`.
- Autorización: venta con descuento > tope queda retenida (sin número/asiento/stock) hasta aprobación; tras aprobar, confirma; `autorizado_por`/`fecha_autorizacion` quedan registrados.
- Permisos: usuario sin `permiso_autorizar_descuentos` ni `es_admin_sistema` no puede autorizar; admin siempre puede.

**Manuales:**
- Carga REAL a Consumidor Final (letra B), a RI (letra A), y PRESUPUESTADO (letra X).
- Flujo de autorización entre dos PCs (operador retiene; responsable aprueba; pantalla del operador cierra sola por polling).
- Listado con filtro Real / Presupuesto / Todas.

---

## 10. Fuera de alcance (diferido)

- Facturación electrónica AFIP: CAE, vencimiento de CAE, código QR.
- Reposición/gestión avanzada de múltiples puntos de venta por sucursal (queda habilitado el modelo, pero la operación arranca con 1 PV por sucursal).
