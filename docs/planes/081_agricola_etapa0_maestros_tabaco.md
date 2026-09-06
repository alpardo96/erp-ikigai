# Plan 081 — Agrícola Etapa 0: Maestros y Configuración del Acopio de Tabaco

## Estado: ✅ Completado (2026-09-06)

**Fecha:** 2026-09-06
**Plan integral:** [`docs/agricola/plan inicial agricola.md`](../agricola/plan%20inicial%20agricola.md) — Etapa 0
**Requiere:** [Plan 080](080_terminos_enchufables_saldos_stock.md) ✅ completado

---

## Objetivo

Dejar cargables y administrables los maestros del acopio de tabaco: campañas, variedades, las 75
clases con sus coeficientes, las listas de precio ponderante, los conceptos de retención con su
cuenta contable y la extensión sectorial del productor.

**Sin ningún efecto** contable, de stock ni de cuenta corriente. Es la base de datos maestra sobre
la que se apoyan el romaneo (Etapa 1) y la liquidación (Etapa 2).

---

## 1. Alcance

### Incluido
- Modelos de maestros y configuración, con sus migraciones.
- Comando idempotente de importación de las 75 clases desde `docs/agricola/tabaco_clase.csv`.
- ABMs HTMX + Tailwind integrados al panel de Configuración, con Typeahead + Lupa y formato es-AR.
- `verticalidades/agricola/urls.py` para que el auto-descubrimiento publique las rutas.
- Tests de modelos, restricciones e importación.

### Fuera de alcance
- Romaneo, fardos, clasificación (Etapa 1).
- Liquidación, asientos, Libro IVA, retenciones aplicadas (Etapa 2).
- Registro de términos de stock y cuenta corriente del Plan 080: se hace cuando existan los
  modelos que los alimentan (Etapas 1 y 2).

---

## 2. Hallazgo previo — las rutas de `agricola` no se publican

El auto-descubrimiento de `config/urls.py` recorre `verticalidades/<app>/` y sólo incluye la app
si encuentra un `urls.py` **en ese primer nivel**. Como `agricola` es un contenedor de sub-apps,
tiene `tabaco/urls.py` y `granos/urls.py` pero **no un `urls.py` propio**: hoy ninguna ruta de la
verticalidad agrícola llega a Django.

Se resuelve creando `verticalidades/agricola/urls.py` que incluya a sus sub-apps. **No se toca
`config/urls.py`**: el mecanismo existente ya sirve.

---

## 3. Modelos

Todos con prefijo `agricola_`, sobre `core.AuditModel`, con FK a `Empresa` y filtrado por la
empresa activa del middleware.

### En `verticalidades/agricola/core_agricola/` — compartido con granos

| Modelo | `db_table` | Campos clave |
|---|---|---|
| `Campania` | `agricola_campania` | empresa, codigo, detalle, fecha_inicio, fecha_fin, ejercicio (FK `empresas.Ejercicio`, opcional), estado, activa · **único (empresa, codigo)** |

La campaña vive acá y no en `tabaco` porque granos y caña la comparten. La lista de precio
ponderante es por campaña, por eso se adelanta a esta etapa.

### En `verticalidades/agricola/tabaco/`

| Modelo | `db_table` | Campos clave |
|---|---|---|
| `ConfiguracionTabaco` | `agricola_tabaco_configuracion` | empresa (OneToOne), cuenta_bienes_cambio (FK `contable.Cuenta`), punto_venta, modo_autorizacion (MANUAL/WEBSERVICE), cai, cai_vencimiento, tolerancia_pesaje |
| `VariedadTabaco` | `agricola_tabaco_variedad` | empresa, codigo, detalle, producto (FK `productos.Producto`, opcional — lo usará el término de stock de la Etapa 4), activa · **único (empresa, codigo)** |
| `ClaseTabaco` | `agricola_tabaco_clase` | empresa, variedad, codigo (1-75), detalle, grupo (derivado), coeficiente `Decimal(6,4)`, activa · **único (empresa, variedad, codigo)** y **(empresa, variedad, detalle)** |
| `ListaPrecioTabaco` | `agricola_tabaco_lista_precio` | empresa, variedad, campania, vigencia_desde, vigencia_hasta, moneda, precio_ponderante, aprobada, aprobada_por, aprobada_el |
| `TipoRetencionTabaco` | `agricola_tabaco_tipo_retencion` | empresa, codigo, detalle, organismo, jurisdiccion (FK `facturacion.Jurisdiccion`, opcional), regimen, tipo_base (NETO/IVA/ACUM_MENSUAL), alicuota, minimo_no_imponible, momento (LIQUIDACION/PAGO), solo_responsable_inscripto, cuenta_contable (FK `contable.Cuenta`), vigencia_desde, vigencia_hasta, activa |
| `ProductorTabaco` | `agricola_tabaco_productor` | cliente_proveedor (OneToOne a `facturacion.ClienteProveedor`), empresa, codigo_fet, finca_origen, coeficiente, habilitado, observaciones |

### Restricciones (`CheckConstraint`)

- `coeficiente > 0` en `ClaseTabaco`.
- `precio_ponderante > 0` en `ListaPrecioTabaco`.
- `alicuota >= 0` y `minimo_no_imponible >= 0` en `TipoRetencionTabaco`.
- `vigencia_hasta` nula o `>= vigencia_desde` en listas de precio y retenciones.
- `fecha_fin` nula o `>= fecha_inicio` en `Campania`.

### Índices

`(empresa, codigo)` en maestros · `(empresa, variedad, activa)` en clases ·
`(empresa, variedad, campania, vigencia_desde)` en listas de precio ·
`(empresa, momento, activa)` en retenciones · `codigo_fet` en productores.

---

## 4. Servicios y comandos

| Servicio | Archivo | Firma | Qué hace |
|---|---|---|---|
| `importar_clases_tabaco` | `verticalidades/agricola/tabaco/management/commands/importar_clases_tabaco.py` | `--empresa <id> [--archivo <ruta>] [--dry-run]` | Carga idempotente de las 75 clases |
| `precio_vigente` | `verticalidades/agricola/tabaco/services/precios.py` | `(empresa_id, variedad, campania, fecha) -> ListaPrecioTabaco` | Devuelve la lista de precio aprobada y vigente |
| `precio_de_clase` | idem | `(lista, clase) -> Decimal` | `REDONDEO(ponderante × coeficiente, 2)` |

### Reglas de la importación

- Encoding **UTF-8 con BOM** (`utf-8-sig`), separador `;`, decimal con coma, CRLF.
- Busca por `codigo`, **nunca por pk**.
- Crea la variedad si no existe: `id_var 1 → BURLEY`, `id_var 2 → VIRGINIA`.
- Valida 75 filas, códigos únicos y coeficientes positivos **antes** de escribir; si algo falla,
  no escribe nada (`transaction.atomic()`).
- Informa altas, actualizaciones, sin cambios y errores.
- `--dry-run` valida e informa sin tocar la base.

---

## 5. Interfaz

ABMs integrados al panel de Configuración, siguiendo el patrón ya establecido en
`verticalidades/distribucion/views_htmx.py`: modal para alta/edición que responde con
`HX-Trigger`, buscador que devuelve sólo las filas del `<tbody>`, borrado por POST.

| Pestaña | Modelo |
|---|---|
| `agro_campanias` | `Campania` |
| `agro_variedades` | `VariedadTabaco` |
| `agro_clases` | `ClaseTabaco` |
| `agro_listas_precio` | `ListaPrecioTabaco` |
| `agro_retenciones` | `TipoRetencionTabaco` |
| `agro_config_tabaco` | `ConfiguracionTabaco` |

**Obligaciones de UX del proyecto:**
- Selector de cuenta contable, variedad, campaña y productor con **Typeahead + Lupa**.
- Todo importe, coeficiente y alícuota con clase `.fInputAR` en inputs y `|formato_ar` en displays.
- Sin Django Admin.

**Modo Enchufe:** el hub de configuración importa los modelos agrícolas con `try/except
ImportError` y sólo muestra las pestañas si `EmpresaVertical.hace_tabaco`.

> Nota: `core/views_config.py` hoy importa `verticalidades.distribucion.models` **sin**
> `try/except`. No se copia ese patrón y no se corrige acá (fuera de alcance).

---

## 6. Tests mínimos

| Test | Qué verifica |
|---|---|
| `test_importacion_carga_75_clases` | 27 Burley + 48 Virginia, coeficientes 0,10 a 1,05 |
| `test_importacion_es_idempotente` | Reejecutar no duplica ni altera |
| `test_importacion_actualiza_coeficiente` | Un coeficiente cambiado en el CSV se actualiza y se informa |
| `test_importacion_rechaza_csv_invalido` | Coeficiente ≤ 0 o código duplicado: no escribe nada |
| `test_clase_unica_por_variedad` | `(empresa, variedad, codigo)` único |
| `test_coeficiente_positivo` | El `CheckConstraint` rechaza 0 y negativos |
| `test_precio_de_clase` | `ROUND(ponderante × coeficiente, 2)` contra los casos reales del VFP |
| `test_precio_vigente_respeta_fechas` | No devuelve listas vencidas ni no aprobadas |
| `test_aislamiento_multiempresa` | Una empresa no ve clases ni listas de otra |
| `test_desenchufe` | Movida la carpeta, `manage.py check` sigue limpio |

---

## 7. Criterio de Hecho

- [x] Modelos y migraciones aplicados, con `db_table` prefijado `agricola_` — 7 tablas.
- [x] `verticalidades/agricola/urls.py` creado; las rutas se publican y resuelven.
- [x] Comando de importación idempotente: 75 clases (27 Burley + 48 Virginia), segunda corrida
      con 0 altas y 75 sin cambios. `--dry-run` verificado: no escribe.
- [x] ABMs operativos con búsqueda typeahead, lupa, `.fInputAR` y `|formato_ar`.
- [x] Tests en verde — **23/23** de maestros y **14/14** de pantallas.
- [x] Prueba de desenchufe: `check` limpio, 0 apps agrícolas, rutas inexistentes, contexto vacío.
- [x] Suite completa **sin fallas nuevas**: 640 tests (603 + 37 nuevos), los mismos 15 errores
      preexistentes. Ver la nota de abajo sobre el evento de infraestructura.
- [x] `makemigrations --check` sin cambios pendientes.
- [x] `docs/walkthrough.md` actualizado.

### Nota sobre la corrida completa

La suite reportó 17 errores en vez de 15. Los 2 extra fueron **un único evento de
infraestructura**, no una regresión: el backend de PostgreSQL se cayó
(`server closed the connection unexpectedly — server terminated abnormally`) durante
`test_plan074_cobranzas.test_rendir_desde_la_pantalla`, lo que arrastró también a su
`tearDownClass`.

Verificación: ese módulo re-corrido aislado da **43/43 OK y cero caídas de conexión**. Además,
la Etapa 0 **no registra ningún término** en los registros del Plan 080 —eso llega en las Etapas
1 y 2—, así que el camino de código de stock y cuenta corriente que ejecutó esta suite es
idéntico al de la corrida anterior, que no tuvo ninguna caída.
