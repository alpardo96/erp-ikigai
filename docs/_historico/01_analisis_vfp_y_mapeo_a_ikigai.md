# Análisis del Sistema VFP "Balances" y mapeo a ERP Ikigai (Django + PostgreSQL)

> Documento técnico de migración. Fuente: `C:\JM_Soft\Balances` (Visual FoxPro 9, ~30 años de historia, compilado en `contable.exe`) y `D:\JM_Soft\erp-ikigai` (Django 6.0.4 + PostgreSQL + django-htmx + Tailwind).
> Alcance del análisis: procesos en uso actual (filtrado por fecha de última modificación de los `.prg`), modelo de datos y lógica de negocio. La capa de UI/forms VFP queda fuera de alcance.

---

## 1. Resumen ejecutivo

El sistema **Balances / contable.exe** es un ERP contable multiempresa y multivertical desarrollado en Visual FoxPro 9 sobre bases DBF. Su arquitectura central gira alrededor de:

- Un objeto singleton `oApp` (clase `entorno` definida en `Clases/libclas.vcx`) que actúa como contenedor de configuración, conexiones, secuencias y métodos compartidos (`setup`, `abrirbases`, `selec_menu`, `nuevo_asto`, `cons_cli_pro`).
- Una base de datos por ejercicio fiscal en `D:\jm_soft\net_balances\eje_NNN\contable`. Cada ejercicio es una carpeta completa: el cierre de ejercicio se materializa físicamente clonando carpetas y reasignando registros por fecha de corte (ver `nuevo_ejercicio.prg`).
- Una tabla `parametros_contables` (1 sola fila) que combina **configuración** (cuentas contables claves: `cta_iva_c`, `cta_iva_d`, `cta_r_iva`, `cta_r_gcia`, `cta_r_ib`, `cta_caja`, `cta_dolar`, etc.) y **secuencias** (próximos IDs: `id_asto`, `id_op`, `id_oe`, `id_rem`, `id_rec`, `id_mov`).
- Multi-empresa por CUIT: el mismo binario `contable.exe` atiende a 6+ empresas (Lopez Rios y Asoc, Spector Esteban, Armería Armar SAS, Toulet, IPJA, AgroJas), seleccionando el `.pfx` de AFIP y los textos de cabecera según `oApp.cuit` en `balances.prg`.
- 20+ verticales habilitables por menú: contable básico, transporte, transporte tokio, colegio, ingenio, cañero, granos, fraccionadora, distribuidora, GNC, combustibles, inmobiliaria, peluquería, tornería, carnicería, camiones, armería, etc. Cada vertical es un `principal_<rubro>.mnx`/`MPR`.

El ERP Ikigai ya tiene resueltas las piezas de base (Empresa, Sucursal, Ejercicio con validación de solapamiento, Plan de cuentas jerárquico, ClienteProveedor unificado con extensiones por rubro, Compra/Venta/Items, Productos con stock por sucursal, Subproductos identificables por serie/CUIM). Los huecos principales son: **modelo de asientos**, **libro IVA digital**, **servicio atómico de saldos**, **señales de stock/movimientos**, **integración AFIP (CAE)**, **secuencias por empresa**, y los **módulos verticales no-armería**.

---

## 2. Métricas del sistema legacy

| Métrica | Valor |
|---|---|
| Archivos totales | 6.139 |
| Programas `.prg` | 192 |
| Formularios `.scx` | 931 |
| Tablas `.dbf` | 706 (429 en `Data/`) |
| Reportes `.frx` | 219 |
| Menús `.mnx` | 23 (`principal_*` por vertical) |
| Tamaño del `.exe` | ~26 MB |
| Mainprog declarado | `prgs/balances.prg` |

Las DBF más grandes (>5 MB) son `aux_captura_asientos_txt.dbf` (140 MB), `captura_credimas.dbf` (72 MB), `aux_diario_gral.DBF` (62 MB), `aux_cons_asientos.dbf` (36 MB), `er_captura_asientos.dbf` (16 MB). El sufijo `aux_` indica tablas de trabajo (scratch) que el sistema rearma con `ZAP` antes de cada operación; el sufijo `tot_` indica acumulados/snapshots.

---

## 3. Procesos en uso actual (por fecha de modificación)

Solo se consideran los `.prg` del directorio activo (excluyendo `Prgs/Respaldo/`). Estas son las fechas reales de la última modificación, no del compilado:

| Fecha | Programa | Función |
|---|---|---|
| 2026-05-05 | `contabiliza_res_bcario.prg` | Importa resúmenes bancarios desde Excel y genera asiento por cada movimiento (débito/crédito) contra la cuenta del banco |
| 2026-02-10 | `genera_vista_colegio.prg` | Arma la vista (cursor materializado) para el módulo colegio |
| 2026-01-25 | `nuevo_ejercicio.prg` | Cierre anual: clona carpeta `eje_223 → eje_255`, parte asientos por fecha de corte, hace PACK |
| 2026-01-10 | `genera_vista_contable.prg` | Vista materializada del módulo contable |
| 2025-11-25 | `diario_gral_marcantonio.prg` | Diario general formato específico cliente "Marcantonio" |
| 2025-08-12 | `contabiliza_libro_iva.prg` | Toma `lib_iva_capturar.xls`, genera asientos contables automáticos para cada factura (neto, IVA discriminado por alícuota, retenciones, total contra cliente/proveedor) |
| 2025-08-12 | `contabiliza_cheques.prg` | Asiento de movimientos de cartera de cheques |
| 2025-08-12 | `carga_libro_iva_xls.prg` | Importa libro IVA desde Excel con manejo de Condic (contado/cta cte), CITI, alícuotas múltiples |
| 2025-08-06 | `col_actualiza_devenga_cobros.prg` | Devengamiento de cobros en módulo colegio |
| 2025-08-01 | `balances.prg` | Programa principal (`MAINPROG`). Inicializa, selecciona PFX según CUIT, lanza menú |
| 2025-07-31 | `activa_entorno.prg` | Activa entorno: crea `oApp`, abre `parametros_contables`, carga cuentas claves |
| 2025-07-18 | `Facturacion_AFIP/afip_autorizacion.prg` | Autoriza CAE contra WSFEv1 (AFIP) |
| 2025-05-15 | `er_carga_compras_id_cta.prg` | Carga de compras con imputación contable (ER = Estudio Lopez Rios) |
| 2025-03-29 | `genera_vista_transporte.prg` | Vista materializada módulo transporte |
| 2025-02-13 | `diario_gral.prg` | Diario general estándar: numera asientos secuencialmente, inserta asiento de apertura, emite reporte |

**Conclusión**: el núcleo activo es **contabilidad central + libro IVA + AFIP + bancos + dos verticales (colegio, transporte)**. Los otros 18 verticales del menú (`principal_camiones`, `principal_ingenio`, `principal_carniceria`, etc.) son código histórico no tocado hace 5+ años; algunos pueden seguir corriendo, pero no son prioritarios para migración.

---

## 4. Arquitectura del legacy

### 4.1. Bootstrap y entorno (`oApp`)

El sistema arranca con `balances.prg` (MAINPROG):

```foxpro
oApp = CREATEOBJECT("entorno")   && Singleton global, definido en libclas.vcx
oApp.setup                       && Lee parametros, abre bases por ejercicio
oApp.selec_menu                  && Decide qué principal_*.mnx cargar según menú
DO CASE
    CASE oApp.cuit = '30708395206'   && Lopez Rios y Asoc
        vpfx = "...lopezrios2024.pfx"
        oApp.cond_iva = 'Responsable Inscripto'
    CASE oApp.cuit = '30638118382'   && IPJA
        vpfx = "...IPJA20241.pfx"
        oApp.cond_iva = 'Exento'
    ...
ENDCASE
READ EVENTS
```

`oApp` expone, entre otros, los atributos públicos:

- **Conexión / rutas**: `net` (path a bases), `Sistema` (path al exe), `net_pri`
- **Empresa**: `cuit`, `razon`, `cond_iva`, `id_eje`, `inicio`, `cierre`
- **Cuentas claves leídas de `parametros_contables`**: `cta_iva_c`, `cta_iva_d`, `cta_r_iva`, `cta_r_gcia`, `cta_r_ib`, `cta_caja`, `cta_dolar`, `cta_val_car`, `cta_r_mun`, `cta_bon`, `cta_cus`, `cta_vta`, `cta_cli`, `cta_pro`, `cta_impint`, `cta_itc`
- **Secuencias**: `codigo` (próximo `id_asto`), `num1`, `num2`, `num8`
- **Usuario / sesión**: `xId_Usu`
- **Métodos**: `nuevo_asto` (asigna próximo `id_asto` atómicamente vía `flock`), `cons_cli_pro` (lookup de cliente/proveedor por código), `abrirbases`, `selec_menu`

### 4.2. Patrón de transacción contable

El patrón se repite literalmente en `contabiliza_libro_iva.prg`, `contabiliza_res_bcario.prg`, `contabiliza_cheques.prg`:

```foxpro
BEGIN TRANSACTION
    oApp.nuevo_asto                       && reserva próximo ID
    FLOCK('asto_enc')
    INSERT INTO asto_enc VALUES(oApp.codigo, 0, m.fecha, xConcepto, m.condic, m.total, 6, oApp.xId_Usu, DATETIME(), m.id_cod, m.fecha, oApp.id_eje)
    UNLOCK IN asto_enc
    FLOCK('asto_mov')
    INSERT INTO asto_mov(id_asto, id_cta, leyenda, debe, haber, divisa, cotiz, monto, fec_vto) VALUES(...)
    INSERT INTO asto_mov(...) VALUES(...)   && más líneas
    IF TABLEUPDATE(0, .t.)
        END TRANSACTION
    ELSE
        ROLLBACK
    ENDIF
```

Lecciones para Django:

1. **Cada operación contable es atómica**. Debe envolverse en `transaction.atomic()` con `select_for_update()` sobre la fila de secuencia.
2. **Las cuentas claves vienen de configuración por empresa**, no son constantes. Migrar a un modelo `ParametrosContables` (1 fila por empresa) que contenga FKs a `Cuenta`.
3. **Secuencias por empresa**: el VFP usa `nuevo_asto` para producir IDs aplicación-lado, no DB-lado. En Postgres esto se reemplaza por una secuencia por empresa (CREATE SEQUENCE) o por una tabla `Secuencias(empresa, tipo, ultimo)` con `SELECT ... FOR UPDATE`.

### 4.3. Cierre de ejercicio (`nuevo_ejercicio.prg`)

El cierre es **físico**, no lógico:

1. Define carpeta destino `eje_XXX` y fecha de corte.
2. Copia toda la carpeta del ejercicio anterior a una nueva.
3. En la carpeta vieja, **borra los asientos posteriores a la fecha de corte**.
4. En la carpeta nueva, **borra los asientos anteriores o iguales a la fecha de corte**.
5. `PACK` ambas (compacta DBFs eliminando registros marcados).

En Ikigai esto desaparece: el modelo `Ejercicio` ya existe como FK en `Compra`, `Venta`, `Movimiento`. Cada operación pertenece a un solo ejercicio, y "cerrar" un ejercicio es una bandera lógica + asiento de cierre/apertura, no un movimiento de archivos.

### 4.4. Multi-empresa y multi-vertical

- **Multi-empresa**: hoy es un `DO CASE` sobre `oApp.cuit` que cambia `.pfx`, logo y condición IVA. En Ikigai ya existe el modelo `Empresa` con `cuit` único y FKs en todo. La equivalencia es directa.
- **Multi-vertical**: 23 archivos `principal_<rubro>.mnx`. Cada uno habilita un subconjunto de formularios. El control de acceso a opciones del menú está en `aux_acceso.dbf` (91 entradas, ID jerárquico `A-`, `B-`, `C-`, `I-`, `M-`, `N-`, `O-`). En Ikigai esto debe migrarse al esquema flexible que propone `PLAN_MEJORAS.md` 3.4: tablas `ModuloNegocio` + `PermisoUsuarioModulo`, en lugar de campos hardcoded por rubro.

### 4.5. Mapa de módulos según `aux_acceso.dbf`

| Letra | Módulo | Funciones principales |
|---|---|---|
| `A-` | Archivo (maestros) | Tablas, alta de clientes, alta de usuarios, autorización de accesos |
| `B-` | Gestión | Facturas Vta/Cpra, factura electrónica, lotes, reimpresión, tarifas, liquidación de tarjetas, recibos, OP, OP múltiple, caja diaria, valores de terceros, conciliación bancaria, devengamiento gastos bancarios |
| `C-` | Contabilidad | Asientos manuales, diario general, sumas y saldos, saldos mensuales, libro IVA, mayor general, AFIP cpras/vtas, financiero mensual, captura mis cptes AFIP, control de facturación contra AFIP, generación SICORE |
| `Z-` | Utilidades | Limpieza/captura, rutas, asientos desbalanceados, captura libro IVA desde Excel, captura ajustes desde Excel, reindexación, consulta errores del sistema, captura asientos desde TXT |
| `I-` | Transporte | Facturas pendientes, facturas detalladas, rendición de choferes, hoja de ruta, paquetes |
| `M-` | Tabaco | Compra de tabaco, romaneos |
| `N-` | Colegio | Alta alumnos, alta matrículas, cobranzas, actualiza precios, listados, estado de cuentas alumnos, caja colegio |
| `O-` | JOSEN (cliente específico) | Capturas de libro IVA, OP, recibos (subconjunto adaptado) |

---

## 5. Modelo de datos legacy (esquema clave)

### 5.1. Tablas estructurales

**`parametros.dbf`** (1 fila, configuración de instalación)
- `RAZON`, `DOMICILIO`, `CUIT`, `IIBB`, `INIACT`, `COND_IVA`
- `SISTEMA`, `NET`, `RUTA_PRI`, `RUTA_NET`, `RUTA_COM` (paths)
- `ID_USU`, `ID_EJE`, `EJERCICIO`, `INICIO`, `CIERRE`
- `SUC`, `SUCURSAL`, `CVERSION`, `MODIFI`

**`parametros_contables.dbf`** (1 fila por ejercicio, cuentas y secuencias)
- Cuentas: `CTA_IVA_C`, `CTA_IVA_D`, `CTA_R_IVA`, `CTA_R_GCIA`, `CTA_R_IB`, `CTA_R_SUSS`, `CTA_CAJA`, `CTA_DOLAR`, `CTA_VAL_CA`, `CTA_CPRA`, `CTA_DES`, `CTA_COM`
- Secuencias: `ID_ASTO`, `ID_OP`, `ID_OE`, `ID_REM`, `ID_REC`, `ID_MOV`, `ID_UREA`, `ID_INV`

**`aux_acceso.dbf`** — control de menú/permisos (sin granularidad por usuario; es global por instalación)
- `ID_FORM` (`A-`, `B-103`, `C-205`, etc.), `TEXT` (etiqueta visible), `VIGENTE` (lógico), `ACCESO` (lógico)

### 5.2. Asientos contables

El sistema separa **encabezado** (`asto_enc`, "asiento_enc" → cabecera) y **movimientos** (`asto_mov`, líneas del asiento). En las tablas auxiliares `tot_asto`, `tot_asto_mov`, `tot_asto_cli_pro` aparecen juntas para informes.

**`asto_enc`** (cabecera de asiento, inferida de `INSERT INTO asto_enc` en `contabiliza_libro_iva.prg`)
- `ID_ASTO` (PK aplicación-lado), `ASIENTO` (número de orden en diario general, asignado al imprimir), `FECHA`, `CONCEPTO` (C50), `CONDIC` (1=contado, 2=cta cte, 3=apertura, 5=compra, 6=banco), `MONTO`, `MODULO` (origen: 1=manual, etc.), `ID_USU`, `FEC_MOD`, `CLI_PRO`, `FEC_VTO`, `ID_EJE`

**`asto_mov`** (líneas del asiento, partida doble)
- `ID_ASTO` (FK a asto_enc), `ID_CTA` (cuenta contable), `LEYENDA` (C150), `DEBE` (Currency), `HABER` (Currency), `DIVISA` (C10, "PES"/"DOL"/...), `COTIZ` (Currency), `MONTO` (Currency en divisa, =0 si moneda local), `ID_ASTO_MO` (orden), `FEC_VTO` (vencimiento por línea), `ID_COD` (cliente/proveedor de la línea)

**`tot_asto_cli_pro`** (vista materializada para informes de cuenta corriente, 13 mil registros)
- Combina cabecera y movimiento: agrega `CLI_PRO`, `JERA_CTA` (jerarquía de cuenta), `MONTO_A`/`MONTO_B`, etc.

### 5.3. Plan de cuentas

Inferido del campo `JERARQUIA` que aparece en `asiento.DBF` y otras tablas:

- Estructura jerárquica por strings de 3+3+3 caracteres (ej. `001003001` = nivel 1 cta 1, nivel 2 cta 3, nivel 3 cta 1).
- Campos clave: `KEY` (id propio), `PARENT` (id del padre), `JERARQUIA` (path), `NIVEL` (1..5), `IMPUTABLE` (lógico, solo cuentas hoja imputan), `DESCRIPCIO`, `DIBUJO` (icono).
- Tipo de cuenta (A/P/N/R) no está en el esquema observado, se infiere por convención de jerarquía (1=Activo, 2=Pasivo, 3=PN, 4=R+, 5=R-).

### 5.4. Libro IVA y libro IVA digital (AFIP)

**`lib_iva`** (libro IVA operativo del sistema)
- `ID_IVA`, `ID_VTA`, `FECHA`, `MESANO`, `TIPO` (FA/FB/FC/NC/ND/RC), `PUNTO`, `NUMERO`, `HASTA` (rango), `F_P` (forma de pago), `ID_COD` (cli/prov), `RAZON`, `CUIT`, `CANTIDAD`, `LITROS`, **importes por alícuota** (`NETO`, `ALIC_IVA`, `IVA`, `ITC`, `IMP_INT`, `EXENTO`, `NO_GRAV`), **retenciones** (`RET_IVA`, `RET_GCIA`, `RET_SUSS`, `RET_IB`, `IB_CBA`, `SIRCREB`, `RET_MUN`), `TOTAL`, `MONEDA`, `NETO_M`, `COTIZ`, `CONDIC`, `VENCIM`, `PAGADO`, `SALDO`, `PTO_R`/`NRO_R` (recibo asociado), `LIB_IVA` (lógico, marca si va al libro), `COD_CITI`, `CARGA_CITI` (lógico), `CPTE_O_IB`, `CAE`

**`aux_lib_iva_afip_c.dbf` / `aux_lib_iva_afip_v.dbf`** (Libro IVA Digital RG 5616/4690)
- `FECHA`, `TIPO_A`, `PUNTO_A`, `NUMERO_A`, `HASTA_A` (campos AFIP), `CAE`, `T_DOC`, `CUIT`, `RAZON`, `COTIZ`, `MONEDA`
- **Neto e IVA por alícuota AFIP**: `NETO_0`, `NETO_25`, `IVA_25`, `NETO_5`, `IVA_5`, `NETO_105`, `IVA_105`, `NETO_21`, `IVA_21`, `NETO_27`, `IVA_27` (alícuotas 0%, 2.5%, 5%, 10.5%, 21%, 27%)
- `NO_GRAV`, `EXENTAS`, `OTROS`, `TOTAL`, `C_V` (C=compras, V=ventas), `PERIODO`, `ID_ASTO` (asiento contable asociado), `PAGADO`, `SALDO`, `FEC_REC`/`FEC_REP` (fechas de recibo/reporte), `RESUMEN`

### 5.5. Clientes / Proveedores

Una sola tabla `cli_pro` con campos:
- `CODIGO` (PK), `DETALLE` (razón social), `CUIT`, `DIVISA`, `COTIZ`, `SALDO`, `SALDO_INI`
- `CTA_PAT` (cuenta patrimonial - activo si cliente, pasivo si proveedor), `CTA_RES` (cuenta de resultado)
- Campos de tipo discriminador (cliente/proveedor)
- Extensiones específicas por vertical (cliente_armeria, cliente_colegio, etc.) en tablas separadas

### 5.6. Caja diaria

**`caja_diaria`**: `CAJA`, `FECHA`, `SI`, `SI_EFE`, `SI_BCO`, `SI_VAL` (saldos iniciales por tipo), `EFECTIVO`, `BANCO`, `VALORES`, `ENTRADAS`, `SALIDAS`, `MONTO`, `SDO_EFE`/`SDO_BCO`/`SDO_VAL`/`SALDO`, `ID_EJE_A`, `ID_USU`

**`aux_caja_diaria`** (detalle): `CAJA`, `ID_CAJ`, `FECHA`, `ID_ASTO`, `ID_COD`, `DETALLE_A`, `ID_CTA`, `JERA_CTA`, `INGRESOS`, `EGRESOS`, `EFECTIVO`, `BANCO`, `VALORES`, `RETEN`, `ORDEN`, `SALDO`, `CONDIC`

### 5.7. Patrones recurrentes en los DBFs

1. **`DIVISA`/`MONEDA` + `COTIZ` + `MONTO`**: presente en casi todas las tablas operativas. Soporta multi-moneda; cuando `MONEDA = 'PES'`, `MONTO = 0`; cuando es divisa extranjera, `MONTO = importe/COTIZ`.
2. **`ID_USU` + `FEC_MOD`**: auditoría simple en cada operación.
3. **`ID_EJE_A`**: ejercicio fiscal redundante en cada registro (para filtros rápidos sin necesidad de JOIN).
4. **`CONDIC`** (entero): 1=contado, 2=cta corriente, 3=apertura, 5=compra, 6=banco. Es semánticamente sobrecargado; en Ikigai conviene desnormalizar en banderas separadas (`es_contado`, `tipo_origen`).
5. **Sufijos**: `aux_*` = scratch (se hace `ZAP` antes de usar), `tot_*` = acumulados/snapshots para reportes, `er_*` = específico del Estudio Lopez Rios, `col_*` = colegio, `tran_*` = transporte, `fra_*` = fraccionadora, `oc_*` = orden de compra, `res_*` = resumen.

---

## 6. Estado actual del ERP Ikigai

### 6.1. Stack y dependencias

- **Django 6.0.4** + **PostgreSQL** (psycopg-binary 3.3)
- **django-htmx 1.27** para parciales sin SPA framework
- **django-extensions** para utilidades de dev
- **Tailwind CSS** (build vía Node, `tailwind.config.js`)
- **Procesamiento de datos**: pandas 3.0.2, openpyxl 3.1.5, xlsxwriter 3.2.9, pdfplumber 0.11.9, pdfminer.six (necesarios para capturar libros IVA desde Excel y procesar PDFs)
- **Packaging**: pyinstaller (objetivo de distribución como `.exe` standalone, replicando el modelo de distribución del legacy)
- Base: `gestion` en `localhost:5432`, usuario `postgres` (¡credenciales en repo — ver Prioridad 6 del `PLAN_MEJORAS.md`!)

### 6.2. Apps existentes

| App | Modelos | Estado |
|---|---|---|
| `core` | `AuditModel` (abstract) | OK, base sólida con auditoría |
| `empresas` | `Empresa`, `Sucursal`, `Ejercicio` | OK. `Ejercicio` valida solapamiento de fechas en `clean()` |
| `usuarios` | `Perfil` (M2M empresas + permisos hardcoded armeria/josen) | **Necesita refactor a `ModuloNegocio` + `PermisoUsuarioModulo`** |
| `facturacion` | `TipoComprobante`, `Jurisdiccion`, `RubroJosen`, `ClienteProveedor`, `ExtensionArmeria`, `ExtensionJosen`, `Compra`, `CompraItem`, `Venta`, `VentaItem`, `Movimiento` | Avanzado. Falta lógica de signals/services |
| `contable` | `Cuenta` (jerárquico, sumariza self-FK), `CuentaBancaria` | OK. Falta `Asiento`, `AsientoLinea`, `ParametrosContables` |
| `productos` | `Marca`, `Rubro`, `Familia`, `Producto`, `StockSucursal`, `Subproducto`, `MovimientoStock` | OK. Falta signals para mantener stock consistente |

### 6.3. Decisiones de diseño ya tomadas (importantes para mantener)

- **PK explícita por modelo de dominio**: `ClienteProveedor.codigo_id`, `Compra.compras_id`, `Venta.ventas_id`, `Subproducto.subpro` (no se usa `id` por defecto en modelos de negocio — replica nombres del legacy).
- **`Cliente/Proveedor unificado`** en `ClienteProveedor` con `tipo_entidad` (1=cliente, 2=proveedor) y clasificaciones distintas por tipo (`CLASIFICACION_CLI` vs `CLASIFICACION_PRO`).
- **Texto en mayúsculas**: `ClienteProveedor.save()` fuerza uppercase salvo campos exentos (`correo`, `tipo_documento`, `tipo_iibb`). Mantener este comportamiento en todos los modelos donde aplique.
- **Tipo doc '99' (sin identificar)**: en save fuerza `tipo_entidad=1`, `clasificacion='MINORISTA'`, `cuit='0'` (regla AFIP).
- **`Ejercicio`**: validación de no-solapamiento en `clean()` por empresa.
- **`Movimiento`** existe como tabla aparte, pero hoy duplica datos de `Compra`/`Venta` y no se actualiza por signals. El `PLAN_MEJORAS.md` decide tratarlo como **vista materializada (camino A)** — regenerar desde signals, no permitir edición manual.
- **Subproducto**: identifica bienes registrables individuales (armas con CUIM, etc.) — un solo `serie` único, vinculado a `compra` y opcionalmente `venta`.
- **`saldo` único como en stock**: `PLAN_MEJORAS.md` 1.1 decide que `ClienteProveedor.saldo` es el único saldo del sistema (se elimina `saldo_inicial`/separación), recalculado atómicamente desde un servicio.

### 6.4. Plan de mejoras ya documentado (resumido)

El archivo `PLAN_MEJORAS.md` define 6 prioridades, ya aceptadas por el desarrollador:

1. **Integridad transaccional**: servicio único `contable/services/saldos.py` atómico; `Movimiento` como vista materializada vía signals; stock en signals; totales en cabecera vía `recalcular_totales()`.
2. **Tests críticos**: 8 tests mínimos en `empresas`, `contable`, `productos`, `facturacion`.
3. **Normalización**: FK en `Movimiento.tipo`; `clean()` para `clasificacion`; `MONEDA_CHOICES` único en `core/constants.py`; permisos modulares flexibles.
4. **Higiene**: respaldos fuera del repo, squashmigrations, pre-commit hooks, logging.
5. **Documentación**: README, CHANGELOG, diagrama de entidades.
6. **Seguridad**: django-environ, `.env`, DEBUG=False, CSRF/SESSION secure, backup cifrado, permisos DB granulares, auditoría de accesos.

---

## 7. Mapeo VFP → Django (tabla maestra)

### 7.1. Estructurales

| VFP (DBF / módulo) | Ikigai (modelo Django) | Estado | Notas |
|---|---|---|---|
| `parametros.dbf` (instalación) | `empresas.Empresa` + `empresas.Sucursal` | ✅ Hecho | Ya soporta multi-empresa y multi-sucursal |
| `parametros_contables.dbf` (cuentas+secuencias por ejercicio) | **FALTA**: `contable.ParametrosContables` (FK Empresa, FKs a Cuenta) + `core.Secuencia` o `pg_sequence` | ❌ Pendiente | Las cuentas claves deben ser FKs a `contable.Cuenta`. Las secuencias se reemplazan por `BigAutoField` o secuencias Postgres por empresa |
| `aux_acceso.dbf` (menú) | `usuarios.ModuloNegocio` + `usuarios.PermisoUsuarioModulo` | ❌ Pendiente | Refactor según `PLAN_MEJORAS.md` 3.4 |
| `eje_NNN/` (cierre físico por carpeta) | `empresas.Ejercicio` + bandera `cerrado` | ✅ Hecho parcialmente | Falta el flujo de cierre lógico (asiento de cierre/apertura) |
| `principal_*.mnx` (verticales) | `usuarios.ModuloNegocio` + apps específicas por vertical | ❌ Pendiente | Solo armería y josen tienen extensión hoy |

### 7.2. Plan de cuentas y asientos

| VFP | Ikigai | Estado |
|---|---|---|
| `cuentas` (plan jerárquico) | `contable.Cuenta` (`jerarquia`, `sumariza` self-FK, `imputable`, `tipo` A/P/N/R) | ✅ Hecho. Jerarquía como string `001003001` mantenida |
| `asto_enc` (cabecera asiento) | **FALTA**: `contable.Asiento` (`asiento_id` PK, `fecha`, `concepto`, `condic`, `monto`, `modulo`, `cli_pro` FK, `fec_vto`, `ejercicio` FK, `empresa` FK, `usuario` FK, auditoría) | ❌ Pendiente |
| `asto_mov` (líneas) | **FALTA**: `contable.AsientoLinea` (FK Asiento, FK Cuenta, `debe`, `haber`, `divisa`, `cotizacion`, `monto_divisa`, `fec_vto`, `cli_pro` FK opcional, `leyenda`, `orden`) | ❌ Pendiente |
| Secuencia `id_asto` en `parametros_contables` | `Asiento.asiento_id = AutoField` o secuencia Postgres por empresa | ❌ Pendiente |
| Numeración `ASIENTO` (orden en diario) | Campo `numero_diario` calculado al emitir el diario, no al cargar | ❌ Pendiente |
| `tot_asto_cli_pro`, `tot_asto_mov` (vistas materializadas) | Vistas SQL (`CREATE MATERIALIZED VIEW`) o querysets directos | ❌ Pendiente |

### 7.3. Libro IVA / AFIP

| VFP | Ikigai | Estado |
|---|---|---|
| `lib_iva` (libro operativo) | Hoy: campos de IVA en `facturacion.Compra` y `facturacion.Venta`. **Falta**: `facturacion.LibroIvaItem` (alícuotas múltiples por comprobante) | Parcial |
| `lib_iva_alic` (alícuotas múltiples por comprobante) | **FALTA**: `facturacion.AlicuotaIva` (`compra_id`/`venta_id`, `alicuota`, `neto`, `iva`) | ❌ Pendiente |
| `aux_lib_iva_afip_c/v` (Libro IVA Digital RG 5616) | **FALTA**: export en formato AFIP desde Compra/Venta | ❌ Pendiente |
| `carga_libro_iva_xls.prg` (import Excel) | **FALTA**: management command + view `import_libro_iva_excel` con pdfplumber/openpyxl | ❌ Pendiente |
| `contabiliza_libro_iva.prg` (genera asiento) | **FALTA**: `contable.services.contabiliza_factura(compra_o_venta)` | ❌ Pendiente |
| `afip_autorizacion.prg` (WSFEv1 CAE) | **FALTA**: `facturacion.services.afip.solicitar_cae(venta)` con WSAA + WSFEv1 (zeep o requests + cryptography) | ❌ Pendiente. Los campos `cae`, `vto_cae`, `cod_qr` ya están en `Venta` |
| Multi-CUIT con .pfx por empresa | **FALTA**: `empresas.CertificadoAfip(empresa, pfx_file, password, ambiente)` | ❌ Pendiente |

### 7.4. Cobranzas y pagos

| VFP | Ikigai | Estado |
|---|---|---|
| `recibos_propios`, `recibos_clientes` | **FALTA**: `facturacion.Recibo`, `facturacion.ReciboAplicacion` | ❌ Pendiente. Hoy `Venta.cobrado`/`saldo` se actualizan ad-hoc |
| `ord_pago`, `ord_pago_facturas`, `aux_ord_pago_facturas` | **FALTA**: `facturacion.OrdenPago`, `facturacion.OrdenPagoAplicacion` | ❌ Pendiente. Hoy `Compra.pagado`/`saldo` se actualizan ad-hoc |
| OP múltiple (varios proveedores en un solo pago) | **FALTA**: relación M2M en `OrdenPago` | ❌ Pendiente |
| Valores de terceros (cheques) | **FALTA**: `facturacion.Cheque`, `facturacion.CarteraValores` | ❌ Pendiente |
| `caja_diaria` + `aux_caja_diaria` | **FALTA**: `contable.CajaDiaria`, `contable.CajaMovimiento` | ❌ Pendiente |
| `res_bcario` (resumen bancario) + conciliación | **FALTA**: `contable.ResumenBancario`, `contable.ResumenItem`, lógica de conciliación | ❌ Pendiente |

### 7.5. Verticales

| Vertical | VFP | Ikigai | Prioridad |
|---|---|---|---|
| Armería | `forms/*arma*.scx`, `inventario_armas.scx` | `facturacion.ExtensionArmeria`, `productos.Subproducto` con serie/CUIM | ✅ Avanzado |
| Josen (cliente) | `principal_josen.mnx`, `jos_cap_*.dbf` | `facturacion.ExtensionJosen`, `facturacion.RubroJosen` | ✅ Avanzado |
| Colegio | `principal_colegio.mnx`, `col_*.prg`, `est_captura_clientes.dbf` | **FALTA**: app `colegio` con `Alumno`, `Matricula`, `Cobranza`, `CajaColegio` | Media |
| Transporte | `principal_transporte.mnx`, `tran_*.scx`, ~100 forms | **FALTA**: app `transporte` con `Chofer`, `Movil`, `OrdenCarga`, `HojaRuta`, `Rendicion`, `Paquete` | Media |
| Tabaco | `M-` en aux_acceso, `compra_tabaco` | No prioritario | Baja |
| Resto (camiones, ingenio, granos, fraccionadora, distribuidora, GNC, combustibles, inmobiliaria, peluquería, tornería, carnicería) | Existen en menús, código frío | No prioritario | Baja |

### 7.6. Reportes

| VFP `.frx` | Ikigai |
|---|---|
| `diario_gral.frx`, `diario_gral_reducido.frx` | View que pagine con WeasyPrint/ReportLab |
| `mayor_g.frx`, `mayor_c.frx` (mayor general/compras) | View con queryset por cuenta + período |
| `libros_iva1.frx`, `libros_iva2.frx` | xlsxwriter para libro IVA y export AFIP RG 5616 |
| `fact_elec_*.frx` (facturas electrónicas, varios formatos por empresa) | Plantillas Jinja/Django + WeasyPrint, una por empresa |
| `suma_saldo_*.scx`, `sum_sal_fciero_mov.scx` | View con aggregations por jerarquía |

---

## 8. Conversiones de tipos DBF → Postgres / Django

| DBF tipo | Django field |
|---|---|
| `C(n)` (Character) | `CharField(max_length=n)` |
| `N(n)` (Numeric int) | `IntegerField` o `BigIntegerField` |
| `N(n,d)` (Numeric decimal) | `DecimalField(max_digits=n, decimal_places=d)` |
| `I(4)` (Integer 32-bit) | `IntegerField` |
| `Y(8)` (Currency) | `DecimalField(max_digits=15, decimal_places=2)` |
| `D(8)` (Date) | `DateField` |
| `T(8)` (DateTime) | `DateTimeField` |
| `L(1)` (Logical) | `BooleanField` |
| `M` (Memo) | `TextField` |
| `M` (Picture) | `BinaryField` o `ImageField` |
| `_NullFlags` | (descartar, lo maneja Postgres con `NULL`) |

Para los campos `CHAR` que en realidad contienen códigos enumerados (ej. `C_V` = "C"/"V", `DIVISA` = "PES"/"DOL"/"60"), migrar a `choices=` con constantes en `core/constants.py`.

---

## 9. Riesgos y advertencias

1. **Pérdida de simultaneidad lógica**: el legacy hace `FLOCK()` por tabla y trabaja con `BUFFERING=5` (optimistic row-level). Postgres con `SELECT FOR UPDATE` + `transaction.atomic()` da garantías más fuertes, pero **bloquea**. Las operaciones largas (importación de Excel) deben ejecutarse en background (Celery o `django-q`), no en el request.

2. **Asientos desbalanceados**: la opción `Z-103 Asientos Desbalanceados` del menú existe porque ocurre. Hay que hacer **constraint** a nivel base (`CHECK (SUM(debe) = SUM(haber))`) o validar en `Asiento.clean()` con un test que falle si no balancea. Migrar registros legacy puede requerir tolerancia inicial.

3. **Multi-divisa**: el campo `MONTO` en `asto_mov` guarda el valor en divisa extranjera (=0 si pesos). Esto NO es estándar contable moderno. En Ikigai conviene:
   - `debe`, `haber`: en moneda funcional (pesos), siempre.
   - `debe_divisa`, `haber_divisa`: en moneda extranjera, si aplica.
   - `cotizacion`: cotización del día.

4. **Cuentas claves hardcoded**: el legacy lee `cta_iva_c`, `cta_iva_d`, etc. de `parametros_contables`. Si en Ikigai esta config no está completa, los procesos automáticos fallan. Validar con `Empresa.parametros.full_clean()` antes de permitir contabilizaciones.

5. **Migración de datos históricos**: 1.086 registros en `asiento.DBF`, 41.846 movimientos en `tot_asto_mov`, ~140K en `aux_captura_asientos_txt`. La migración inicial debe hacerse con un management command (`python manage.py importar_legacy_dbf`) usando `dbfread` y procesando en lotes con `bulk_create(batch_size=1000)`.

6. **AFIP y entornos**: el legacy usa `wsaahomo.afip.gov.ar` para testing y `wsaa.afip.gov.ar` para producción, con un flag `xPrueba`. En Ikigai esto debe ser una variable de entorno por empresa: `AFIP_AMBIENTE = 'homologacion' | 'produccion'`.

7. **PFX y secretos**: los `.pfx` viven en `Facturacion_AFIP/Certificados/Definitivo/`. En Ikigai deben subirse como archivos del modelo `CertificadoAfip` (con la password cifrada — `cryptography.fernet`), NO en el repo.

8. **Reproducibilidad de saldos**: el legacy mantiene saldos calculados (`SALDO` en `cli_pro`, `Compra`/`Venta`) y los actualiza en cada operación. El `PLAN_MEJORAS.md` decide recalcular siempre desde el servicio. Esto significa que **un test de regresión que importe los datos legacy y compare saldos contra los del legacy es crítico** para detectar inconsistencias preexistentes.

---

## 10. Hoja de ruta sugerida (alineada con `PLAN_MEJORAS.md`)

### Fase 1 — Núcleo contable (4–6 semanas)

1. Modelos faltantes: `contable.Asiento`, `contable.AsientoLinea`, `contable.ParametrosContables`, `core.Secuencia`.
2. Servicio `contable.services.asientos.crear_asiento(empresa, fecha, concepto, lineas, ...)` atómico con `select_for_update()` y validación de balance débito=crédito.
3. Servicio `contable.services.saldos.recalcular_saldo_cliente()` (`PLAN_MEJORAS.md` 1.1).
4. Signals para `Compra`/`Venta` → genera/regenera `Movimiento` y dispara `recalcular_saldo_cliente()`.
5. Signals para `CompraItem`/`VentaItem` → actualiza `StockSucursal` y dispara `Compra.recalcular_totales()`.
6. Tests críticos de `PLAN_MEJORAS.md` 2.

### Fase 2 — Libro IVA y AFIP (4–6 semanas)

1. `facturacion.AlicuotaIva` (alícuotas múltiples por comprobante).
2. Service `facturacion.services.libro_iva.exportar_aplicativo_afip(empresa, periodo)` → genera txt RG 5616.
3. Service `facturacion.services.afip.solicitar_cae(venta)` con WSAA + WSFEv1 usando `cryptography` + `zeep`.
4. Modelo `empresas.CertificadoAfip` con upload de `.pfx`, password cifrada con Fernet, ambiente (homo/prod).
5. Import de libro IVA desde Excel: management command `python manage.py importar_libro_iva --empresa=X --periodo=YYYYMM --archivo=path`.
6. Service `contable.services.contabilizar_factura(compra_o_venta)` que crea el asiento usando las cuentas claves de `ParametrosContables`.

### Fase 3 — Cobranzas, pagos, bancos, caja (4 semanas)

1. `facturacion.Recibo`, `facturacion.OrdenPago`, aplicaciones a comprobantes.
2. `contable.CajaDiaria`, `contable.CajaMovimiento`.
3. `contable.ResumenBancario`, conciliación bancaria.
4. Migración del flujo `contabiliza_res_bcario.prg`.

### Fase 4 — Cierre de ejercicio y reportes (3 semanas)

1. Flujo de cierre lógico: asiento de cierre de resultados, asiento de apertura del ejercicio siguiente.
2. Reportes: diario general, mayor general, sumas y saldos, financiero mensual, mayor por cuenta.
3. Exportación SICORE (`C-213` en menú legacy).

### Fase 5 — Permisos modulares y verticales (continuo)

1. `ModuloNegocio` + `PermisoUsuarioModulo` (`PLAN_MEJORAS.md` 3.4).
2. App `colegio` (Alumno, Matricula, Cobranza, CajaColegio).
3. App `transporte` (Chofer, Movil, OrdenCarga, HojaRuta, Rendicion, Paquete).
4. Otros verticales según demanda real (priorizar por uso del cliente).

### Fase 6 — Migración de datos y seguridad (antes de go-live)

1. Management command `importar_legacy_dbf` con `dbfread`, validaciones y reconciliación.
2. `django-environ` + `.env` (mover `SECRET_KEY`, credenciales DB).
3. Rotar password de Postgres (hoy `JM_Soft` en repo).
4. `DEBUG=False`, `ALLOWED_HOSTS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`.
5. Backup automático cifrado de Postgres.
6. Auditoría de accesos (login + operaciones sensibles).

---

## 11. Glosario VFP → Django

| Término VFP | Equivalente Django/Postgres |
|---|---|
| `BEGIN TRANSACTION` / `END TRANSACTION` / `ROLLBACK` | `with transaction.atomic():` |
| `FLOCK('tabla')` | `Model.objects.select_for_update()` dentro de `transaction.atomic()` |
| `TABLEUPDATE(0, .t.)` | `obj.save()` (es automático con `atomic`) |
| `INSERT INTO ... VALUES(...)` | `Model.objects.create(...)` o `bulk_create` |
| `REPLACE campo WITH valor` | `obj.campo = valor; obj.save(update_fields=['campo'])` |
| `SCATTER MEMVAR` / `GATHER MEMVAR` | (no aplica; en Python se usan dicts) |
| `SCAN ... ENDSCAN` | `for obj in queryset:` |
| `LOCATE FOR cond` | `Model.objects.filter(cond).first()` |
| `SET ORDER TO indice` | `Meta.indexes = [...]` + `order_by()` |
| `PACK` | (no aplica; Postgres con `VACUUM`) |
| `ZAP` | `Model.objects.all().delete()` (¡cuidado en producción!) |
| `CURSORSETPROP('buffering', 5, 'tabla')` | (no aplica; Postgres maneja MVCC) |
| `oApp.codigo = id_asto` | Sequence en Postgres o `select_for_update()` sobre tabla `Secuencia` |
| `SET DATE DMY` / `SET CENTURY ON` | Localización en `settings.LANGUAGE_CODE = 'es-ar'` y `USE_TZ = True` |
| Memo (`M`) | `TextField` |
| Currency (`Y`) | `DecimalField(max_digits=15, decimal_places=2)` |

---

## 12. Convenciones de naming a mantener en Ikigai

Para reducir fricción cognitiva con el legacy:

- PK explícita por modelo: `<modelo>_id` (ya hecho: `compras_id`, `ventas_id`, `codigo_id`).
- Tablas con `db_table` explícito para colisiones (ya hecho: `cble_cuentas`, `cble_cuenta_bancaria`, `facturacion_movimiento`, `empresas_ejercicio`).
- Para los nuevos modelos contables, sugerir: `cble_asiento_enc` y `cble_asiento_mov` (mismo prefijo `cble_` que ya usa `contable.Cuenta`).
- Mantener nombres legacy en campos donde haya import directo desde DBF: `id_asto`, `id_cta`, `id_eje_a`, `cli_pro`, `condic`, `divisa`, `cotiz`, `c_v`, `cod_citi`.

---

## 13. Archivos de referencia para profundizar

En el legacy:

- `Prgs/balances.prg` — entry point, configuración por CUIT.
- `Prgs/activa_entorno.prg` — bootstrap del objeto `oApp`.
- `Prgs/nuevo_ejercicio.prg` — patrón de cierre de ejercicio.
- `Prgs/contabiliza_libro_iva.prg` — patrón completo de asiento automático desde libro IVA.
- `Prgs/contabiliza_res_bcario.prg` — patrón de asiento desde resumen bancario.
- `Prgs/diario_gral.prg` — numeración de diario general y reporte.
- `Otros/rutas.h` — constantes de paths (#define).
- `Facturacion_AFIP/afip_autorizacion.prg` — patrón WSAA + WSFEv1.
- `Data/aux_acceso.dbf` — mapa de menú/permisos.
- `Data/parametros_contables.dbf` — cuentas claves y secuencias.
- `Net_Instalador/Eje_001/parametros_contables.dbf` — ejemplo "limpio" de instalación.

En Ikigai:

- `PLAN_MEJORAS.md` — roadmap detallado con criterios de hecho.
- `config/settings.py` — apps registradas, base.
- `facturacion/models.py` — modelos más maduros del sistema.
- `core/models.py` — `AuditModel` reutilizable.
- `Modelos/` — capturas y planillas Excel que documentan los modelos visualmente.

---

**Fin del documento técnico.**

El super prompt para LLM derivado de este análisis está en `docs/02_super_prompt_continuar_ikigai.md`.
