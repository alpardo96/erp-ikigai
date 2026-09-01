# ERP IKIGAI — Documento Integral de Arquitectura y Visión Global

> **Dueño:** Claude Opus (IA estratégica)
> **Versión:** 1.0 — 2026-06-04
> **Propósito:** Fuente única de verdad sobre visión, arquitectura, reglas y estado del proyecto.
> **Cuándo se lee:** Al inicio de cada sesión estratégica. NO se lee para implementar código.
> **Documentos complementarios:** `GUIA_MODULAR.md` (Gemini) y `docs/planes/` (Gemini+Codex).

---

## 1. Qué es ERP Ikigai

Un ERP de gestión administrativa y contable para PyMEs argentinas, multiempresa, multiejercicio y multivertical. Migra un sistema legacy de Visual FoxPro 9.0 (~30 años en producción) a Django + PostgreSQL.

| Eje | Definición |
|-----|-----------|
| **Producto** | ERP contable con facturación, tesorería, impuestos, stock y verticales sectoriales |
| **Usuario principal** | Contador Público que opera múltiples empresas simultáneamente |
| **Activo estratégico** | Combinar criterio contable profesional + automatización + captura de datos externos + control operativo en una sola plataforma |
| **Lo que NO debe ser** | Un facturador aislado, una colección de pantallas inconexas, ni una copia literal del VFP |

---

## 2. Stack Técnico (no negociable)

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.10+, Django 6.0.4, PostgreSQL 14+ (psycopg-binary 3.3) |
| Frontend | HTML semántico + Tailwind CSS + HTMX 1.27 (+ Alpine.js donde haga falta) |
| Procesamiento | pandas 3.0.2, openpyxl, xlsxwriter, pdfplumber, pdfminer.six |
| AFIP | cryptography 46.0.7 (certificados .pfx/.key/.crt) |
| Distribución | pyinstaller 6.19.0 (objetivo: .exe standalone) |
| Testing | pytest-django o runner nativo de Django |
| UI | Interfaz unificada propia. **NO se usa Django Admin** para operaciones |

---

## 3. Arquitectura de Apps

```
erp-ikigai-2/
├── config/          → settings, urls, wsgi
├── core/            → AuditModel, constants, middleware, servicios compartidos
├── empresas/        → Empresa, Sucursal, Ejercicio
├── usuarios/        → Perfil, permisos modulares
├── contable/        → Cuenta, Asiento, AsientoLinea, ParametrosContables, CuentaBancaria
│   └── services/    → asientos.py, saldos.py, contabilizacion.py
├── facturacion/     → TipoComprobante, ClienteProveedor, Compra, Venta, Items, Movimiento
│   └── services/    → (futuro: afip/, libro_iva/)
├── productos/       → Producto, StockSucursal, Subproducto, Marca, Rubro, Familia
│   └── services/    → stock_service.py
├── tesoreria/       → Recibo, OrdenPago, Valor, MedioPago, CuentaBancaria (movida aquí)
├── templates/       → Plantillas Django + partials HTMX
├── static/          → CSS compilado, JS, imágenes
└── docs/            → Esta documentación
```

**Principio rector:** La app `contable` es el centro de servicios críticos. Todas las demás impactan contabilidad a través de sus servicios, nunca directamente.

---

## 4. Reglas de Oro (innegociables)

### 4.1. Integridad Transaccional

- **Saldos:** Se recalculan EXCLUSIVAMENTE vía `contable/services/saldos.py`. Cualquier `cliente.saldo = X` fuera del servicio es un bug.
- **Stock:** Se actualiza SOLO desde signals de `CompraItem`/`VentaItem` vía `productos/services/stock_service.py`.
- **Totales cabecera:** `Compra.total` / `Venta.total` se recalculan desde items vía `recalcular_totales()`.
- **Atomicidad:** Toda operación multi-modelo usa `transaction.atomic()` + `select_for_update()`.

### 4.2. Asientos Contables

- Se crean SOLO vía `contable/services/asientos.crear_asiento()`. Valida partida doble (débito=crédito).
- Contabilización automática vía `contable/services/contabilizacion.py`.
- NUNCA insertar líneas contables directamente saltándose el servicio.
- Asientos contabilizados no se editan: se anulan y regeneran.

### 4.3. Multitenencia

- Todo queryset filtra por `empresa`. Middleware coloca `request.empresa` activa.
- Cada operación lleva FK a `Ejercicio`. Cierre de ejercicio es lógico (no físico como en VFP).

### 4.4. Auditoría

- Modelos extienden `core.AuditModel` (campos `creado_por`/`modificado_por` automáticos).
- Operaciones críticas dejan registro en `AuditLog` con before/after.

### 4.5. Convenciones

- PK explícita por modelo de dominio (`compras_id`, `ventas_id`, `codigo_id`).
- `db_table` explícito donde haya colisión (`cble_cuentas`, `cble_asiento_enc`).
- Texto en mayúsculas en `save()` para razones sociales, productos, conceptos (excepto correo, enums).
- Tipo documento '99' fuerza `tipo_entidad=1`, `clasificacion='MINORISTA'`, `cuit='0'`.

---

## 5. Herencia del VFP: Qué se preserva y qué se supera

| Elemento VFP | Se preserva | Se supera |
|-------------|-------------|-----------|
| `oApp` (singleton global) | Configuración por empresa, cuentas claves, secuencias | Ya no es objeto global; son modelos `Empresa`, `ParametrosContables`, `Secuencia` |
| `parametros_contables.dbf` | Cuentas claves por empresa | `ParametrosContables` con FKs a `Cuenta` (ya implementado) |
| `asto_enc` / `asto_mov` | Partida doble, transaccionalidad | `Asiento` + `AsientoLinea` con constraints DB (ya implementado) |
| Multi-empresa por carpetas | Multi-empresa obligatorio | Lógico por filas con FK, no físico por carpetas |
| `lib_iva.dbf` | Libro IVA con alícuotas y percepciones | Se deriva de `Compra`/`Venta` validadas (pendiente) |
| `principal_*.mnx` (verticales) | Verticales habilitables | `ModuloNegocio` + `PermisoUsuarioModulo` (pendiente) |
| `aux_*` / `tot_*` (scratch/snapshots) | Concepto de vistas rápidas | Management commands, vistas materializadas o `Movimiento` read-only |
| Cierre de ejercicio por clonación de carpetas | Asiento cierre/apertura | Bandera lógica `cerrado` + asiento automático |

---

## 6. Estado Actual del Proyecto (Junio 2026)

### Fases Completadas ✅

| Fase | Qué se hizo | Archivos clave |
|------|------------|----------------|
| **1: Saldos atómicos** | Servicio centralizado `recalcular_saldo_cliente()`, signals en compras/ventas | `contable/services/saldos.py` |
| **2: Núcleo contable** | Modelos `Asiento`, `AsientoLinea`, `ParametrosContables`. Servicio `crear_asiento()` con validación de partida doble | `contable/models.py`, `contable/services/asientos.py` |
| **3: Contabilización automática** | Contabilización de compras/ventas individual y consolidación diaria. Anulación inmutable. Multi-actividad por rubro | `contable/services/contabilizacion.py` |
| **4: Stock y totales** | Signals para stock en `StockSucursal`. Recálculo de totales en cabecera. `Movimiento` como vista materializada | `productos/services/stock_service.py` |
| **5: Vistas HTMX contables** | Libro Diario, Mayor, Balance de Sumas y Saldos. Carga manual de asientos con modal HTMX + Alpine.js | Templates en `contable/` |
| **5b: Vistas HTMX facturación** | Punto de Venta unificado con alertas de stock negativo | Templates en `facturacion/` |

### En Progreso 🔶

| Módulo | Estado | Detalle |
|--------|--------|---------|
| **Tesorería** | Modelado + frontend inicial | App creada. Recibo, OrdenPago, Valor, MedioPago, CuentaBancaria (movida de contable). ABM de Medios de Pago en Hub de Configuración. Falta: vista de emisión de Recibos/OP |

### Pendiente ❌

| Módulo | Prioridad |
|--------|-----------|
| Permisos modulares (reemplazo de hardcoded) | Alta |
| Libro IVA Digital + AFIP CAE | Alta |
| Bancos y conciliación | Alta |
| Reportes gerenciales | Media |
| Cierre de ejercicio lógico | Media |
| Verticales (armería, colegio, transporte) | Media-Baja |
| Migración de datos VFP | Antes de go-live |
| Seguridad y deploy | Antes de go-live |

### Tests

- **11 tests unitarios** pasan correctamente (saldos, asientos, contabilización, stock, totales).
- Comando: `python manage.py test contable productos`

---

## 7. Decisiones ya tomadas

| Decisión | Resolución | Dónde |
|----------|-----------|-------|
| `Movimiento` como fuente o vista | **Vista materializada (camino A)** — read-only, regenerado por signals | walkthrough Fase 4 |
| Stock negativo | **Se permite** (no bloquea operatoria) con warning visual en HTMX | walkthrough Fase 4 |
| Saldo único vs saldo_inicial separado | **Saldo único** recalculado por servicio | walkthrough Fase 1 |
| Contabilización síncrona vs lote | **Ambas** — campo `metodo_contabilizacion_ventas` en ParametrosContables | walkthrough Fase 3 |
| Django Admin | **No se usa** para operaciones. Todo en UI propia HTMX | .cursorrules |
| CuentaBancaria | **Movida de contable a tesorería** | walkthrough Fase 6 |

### Decisiones pendientes de consenso

| Decisión | Opciones | Impacto |
|----------|---------|---------|
| Tesorería como app propia o dentro de contable | Ya resuelta: **app propia** `tesoreria` | — |
| Impuestos como app propia | Puede iniciar derivado de facturación, crecer a app | Media |
| Secuencias: Postgres native o tabla `Secuencia` | Tabla más portable y auditable; sequence DB más eficiente | Alta |
| Cierre de ejercicio: modelo lógico exacto | Bloqueo + asiento cierre/apertura + reapertura controlada | Alta |

---

## 8. Criterios de Aceptación del Core

El core se considera completo cuando:

- [ ] Una venta con productos recalcula totales, baja stock, actualiza saldo del cliente, genera Movimiento y genera asiento balanceado ✅
- [ ] Una compra con productos recalcula totales, sube stock, actualiza saldo del proveedor, genera Movimiento y genera asiento balanceado ✅
- [ ] Un recibo aplicado a facturas baja saldo del cliente, registra medio de cobro y genera asiento ❌ (tesorería en progreso)
- [ ] Una orden de pago aplicada baja saldo del proveedor, registra medio de pago y genera asiento ❌
- [ ] El libro IVA se obtiene desde comprobantes validados y cuadra con los asientos ❌
- [ ] El sistema impide asientos desbalanceados y cuentas no imputables ✅
- [ ] Todo queryset operativo filtra por empresa y ejercicio ✅
- [ ] Las operaciones críticas dejan trazabilidad ✅

---

## 9. Riesgos y Mitigación

| Riesgo | Causa probable | Mitigación |
|--------|---------------|-----------|
| Saldos inconsistentes | Asignaciones directas fuera del servicio | Servicio único + grep + tests ✅ |
| Stock duplicado | Updates sin delta | pre_save/delta + signals ✅ |
| Asientos desbalanceados | Creación libre de líneas | `crear_asiento()` obligatorio + constraints DB ✅ |
| Fuga multiempresa | Querysets sin filtro | Middleware + filtros + tests |
| Migración sucia | Importar datos sin control | Lotes auditados (pendiente) |
| Verticales que deforman core | Campos sectoriales en modelos generales | Extensiones OneToOne |
| Dependencia de UI | Reglas en formularios | Reglas en modelos/servicios/signals ✅ |

---

## 10. Asignación de IAs

| IA | Rol | Lee | Crea/Mantiene |
|----|-----|-----|---------------|
| 🟣 **Claude Opus** | El Jefe — visión, arquitectura, priorización | Este documento | Este documento |
| 🔵 **Gemini** | El Patrón — diseño modular, planificación técnica | `GUIA_MODULAR.md` + planes | `GUIA_MODULAR.md` + `docs/planes/*.md` |
| 🟢 **Codex** | El Operario — implementación, debugging, tests | Plan del módulo + código .py | Código + `walkthrough.txt` |

**Flujo:** Opus decide qué → Gemini diseña cómo → Codex implementa.

---

## 11. Conocimiento del Dominio Argentino (referencia rápida)

| Término | Definición |
|---------|-----------|
| AFIP/ARCA | Organismo de recaudación. Facturas electrónicas requieren CAE vía WSFEv1 |
| CUIT | ID tributaria, 11 dígitos. Sin CUIT → CUIT='0' + tipo_doc='99' |
| Tipos comprobante | FA(1), FB(6), FC(11), NCA(3), NCB(8), NCC(13), NDA(2), NDB(7), NDC(12) |
| IVA | Alícuotas: 0%, 2.5%, 5%, 10.5%, 21% (general), 27% |
| Retenciones | IVA, Ganancias, IIBB (provinciales), SUSS, Municipales |
| Libro IVA Digital | RG 5616. Archivo TXT con compras/ventas para AFIP |
| SICORE | Régimen de retenciones practicadas |
| Responsable Inscripto | IVA general, emite FA a otros RI, FB a CF |
| Monotributo | Régimen simplificado, no emite FA |

---

## Anexo: Glosario Técnico VFP → Django

| VFP | Django/Postgres |
|-----|----------------|
| `BEGIN TRANSACTION` | `with transaction.atomic():` |
| `FLOCK('tabla')` | `Model.objects.select_for_update()` |
| `INSERT INTO` | `Model.objects.create()` o `bulk_create` |
| `SCAN ... ENDSCAN` | `for obj in queryset:` |
| `LOCATE FOR cond` | `Model.objects.filter(cond).first()` |
| `ZAP` | `Model.objects.all().delete()` |
| `oApp.codigo` | Secuencia en Postgres o `select_for_update()` |
| Currency `Y(8)` | `DecimalField(max_digits=15, decimal_places=2)` |
| `C(n)` Character | `CharField(max_length=n)` |
