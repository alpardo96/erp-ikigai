# Papel de Trabajo — SQL en pgAdmin 4 (ERP Ikigai 2)

**Base:** PostgreSQL (motor `django.db.backends.postgresql`, credenciales en `.env`: `DB_NAME`, `DB_USER`, `DB_HOST`, `DB_PORT`).
**Herramienta:** pgAdmin 4 → clic derecho sobre la base → **Query Tool** (o `Alt+Shift+Q`).

---

## 0. REGLAS DE ORO (leer antes de tocar nada)

| # | Regla | Motivo |
|---|-------|--------|
| 1 | **SIEMPRE filtrar por `empresa_id`** en todo SELECT/UPDATE/DELETE | El ERP es multi-empresa. Sin ese filtro tocás datos de otro cliente. |
| 2 | **Primero `SELECT`, después `UPDATE`/`DELETE`** con el MISMO `WHERE` | Ver exactamente qué filas vas a afectar antes de afectarlas. |
| 3 | **Trabajar dentro de `BEGIN; ... ROLLBACK;`** hasta estar seguro | Permite deshacer. Ver §5. |
| 4 | **Backup antes de cualquier UPDATE/DELETE masivo** | Ver §11 (`respaldo_diario.bat` o `pg_dump`). |
| 5 | **Editar por SQL SALTEA la lógica de Django** | No corren `save()`, señales, `recalcular_totales()`, ni auditoría. Si tocás importes, recalculá vos los agregados (ver §9). |
| 6 | Nunca `UPDATE`/`DELETE` **sin `WHERE`** | Afecta la tabla entera. |

> **Tip pgAdmin:** en el Query Tool podés seleccionar con el mouse *solo un fragmento* del script y ejecutar con `F5`. Usalo para correr únicamente el `SELECT` de control antes del `UPDATE`.

---

## 1. MAPA DE TABLAS DEL ERP

### Contabilidad (app `contable`)
| Tabla | Modelo | PK | Notas |
|-------|--------|----|-------|
| `cble_cuentas` | Cuenta | `id` | `jerarquia`, `cuenta`, `tipo` (A/P/N/R), `imputable`, `sumariza_id`, `empresa_id` |
| `cble_asiento_enc` | Asiento | `asiento_id` | Cabecera: `fecha`, `concepto`, `monto`, `condic`, `modulo`, `anulado`, `ejercicio_id`, `cli_pro_id` |
| `cble_asiento_mov` | AsientoLinea | `id` | Renglones: `asiento_id`, `orden`, `cuenta_id`, `debe`, `haber`, `divisa` |
| `cble_libro_iva_compras` / `cble_libro_iva_ventas` | LibroIva* | `id` | |
| `cble_libro_iva_alic` | LibroIvaAlic | `id` | Desglose por alícuota |
| `cble_ret_perc_sufrida` | RetPercSufrida | `id` | Única por `asiento_id` |
| `cble_alicuotas_iva` | AlicuotaIva | `id` | |
| `cble_parametros` | ParametrosContables | `empresa_id` | 1 fila por empresa |

### Facturación (app `facturacion`)
| Tabla | Modelo | PK | Campos clave |
|-------|--------|----|--------------|
| `facturacion_clienteproveedor` | ClienteProveedor | `codigo_id` | `razon_social`, `cuit`, `tipo_entidad` (1=Cli, 2=Pro), `condicion_iva`, `saldo` |
| `facturacion_compra` | Compra | `compras_id` | `fecha`, `punto`, `numero`, `proveedor_id`, `neto`, `iva`, `total`, `pagado`, `saldo`, `condic`, `asiento_id` |
| `facturacion_compraitem` | CompraItem | `id` | `compra_id`, `producto_id`, `cantidad`, `precio_unitario`, `total` |
| `facturacion_venta` | Venta | `ventas_id` | `fecha`, `punto`, `numero`, `cliente_id`, `neto`, `iva`, `total`, `cobrado`, `saldo`, `estado` (0=Activa,1=Anulada,2=Pend,3=Rech) |
| `facturacion_ventaitem` | VentaItem | `id` | `venta_id`, `producto_id`, `cantidad`, `precio_unitario`, `total` |
| `facturacion_tipocomprobante` | TipoComprobante | `id` | |
| `facturacion_movimiento` | Movimiento | `id` | Cuenta corriente |
| `facturacion_ordencompra` / `_ordencompraitem` | OrdenCompra | | |
| `facturacion_recepcion` / `_recepcionitem` | Recepcion | | |

### Productos (app `productos`)
`productos_producto` (`id`; `detalle`, `cod_prov`, `cod_fab`, `stock`, `cto_adq`, `precio_neto`, `precio_total`, `marca_id`, `rubro_id`, `empresa_id`), `productos_marca`, `productos_rubro`, `productos_familia`, `productos_stocksucursal`, `productos_movimientostock`.

### Tesorería (app `tesoreria`)
`tesoreria_medio_pago`, `tesoreria_caja`, `tesoreria_caja_sesion`, `tesoreria_movimiento_caja`, `tesoreria_movimiento_caja_detalle`, `tesoreria_valor_terceros`, `tesoreria_transaccion_bancaria`, `tesoreria_cobro_tarjeta`, `tesoreria_retiro_caja` (+ `_valor`, `_tarjeta`, `_asiento`), `cble_cuenta_bancaria`, `tesoreria_banco`, `tesoreria_tarjeta`.
Recibos / Órdenes de Pago: `tesoreria_recibo`, `tesoreria_reciboimputacion`, `tesoreria_reciboaplicacion`, `tesoreria_ordenpago`, `tesoreria_ordenpagoimputacion`, `tesoreria_ordenpagoaplicacion`.

### Empresas / Usuarios
`empresas_empresa`, `empresas_sucursal`, `empresas_puntoventa`, `empresas_ejercicio`, `empresas_cotizacionmoneda`, `usuarios_perfil`, `auth_user`.

> **Regla Django:** salvo `db_table` explícito, la tabla es `app_modeloenminuscula` y las FK terminan en `_id`.

---

## 2. CONSULTAS (SELECT) CON CONDICIONALES

### 2.1 Base
```sql
SELECT compras_id, fecha, punto, numero, total
FROM facturacion_compra
WHERE empresa_id = 1
ORDER BY fecha DESC, compras_id DESC
LIMIT 100;
```

### 2.2 Operadores de condición

```sql
-- Igualdad / desigualdad / comparación
WHERE total > 100000
WHERE estado <> 1
WHERE fecha >= '2026-01-01'

-- Rango (inclusivo en ambos extremos)
WHERE fecha BETWEEN '2026-01-01' AND '2026-06-30'

-- Lista de valores
WHERE condic IN (1, 2)
WHERE tipo_entidad NOT IN (2)

-- Nulos (NUNCA usar "= NULL")
WHERE asiento_id IS NULL
WHERE cuit IS NOT NULL

-- Texto: LIKE distingue mayúsculas, ILIKE no
WHERE razon_social ILIKE '%lopez%'      -- contiene
WHERE razon_social ILIKE 'DIST%'        -- empieza con
WHERE cuit LIKE '20%'
WHERE cod_prov ~ '^[A-Z]{3}[0-9]+$'     -- expresión regular

-- Combinaciones: OJO con la precedencia, usar paréntesis
WHERE empresa_id = 1
  AND (condicion_iva = 'RESPONSABLE INSCRIPTO' OR condicion_iva = 'MONOTRIBUTO')
  AND saldo <> 0;
```

### 2.3 Fechas (muy usado en el ERP)
```sql
-- Mes en curso
WHERE fecha >= date_trunc('month', CURRENT_DATE)
  AND fecha <  date_trunc('month', CURRENT_DATE) + INTERVAL '1 month'

-- Últimos 30 días
WHERE fecha >= CURRENT_DATE - INTERVAL '30 days'

-- Un mes puntual por período AAAA-MM
WHERE to_char(fecha, 'YYYY-MM') = '2026-07'
-- (más rápido, usa índice:)
WHERE fecha >= '2026-07-01' AND fecha < '2026-08-01'

-- Ejercicio fiscal (según empresas_ejercicio)
WHERE fecha BETWEEN (SELECT fecha_inicio FROM empresas_ejercicio WHERE id = 3)
                AND (SELECT fecha_fin    FROM empresas_ejercicio WHERE id = 3)
```

### 2.4 Condicionales dentro del SELECT — `CASE`
```sql
SELECT v.ventas_id,
       v.fecha,
       v.total,
       CASE v.estado
            WHEN 0 THEN 'ACTIVA'
            WHEN 1 THEN 'ANULADA'
            WHEN 2 THEN 'PENDIENTE AUTORIZACIÓN'
            WHEN 3 THEN 'RECHAZADA'
            ELSE 'DESCONOCIDO'
       END AS estado_desc,
       CASE WHEN v.saldo > 0 THEN 'ADEUDA' ELSE 'CANCELADA' END AS situacion
FROM facturacion_venta v
WHERE v.empresa_id = 1;
```

### 2.5 Nulos y defaults
```sql
COALESCE(saldo, 0)                       -- si es NULL devuelve 0
NULLIF(cuit, '')                         -- si es cadena vacía devuelve NULL
GREATEST(total - pagado, 0)              -- piso en cero
```

### 2.6 JOINs
```sql
SELECT c.compras_id, c.fecha, c.numero,
       p.razon_social AS proveedor,
       t.descripcion  AS comprobante,     -- ajustar al nombre real de la columna
       c.total, c.saldo
FROM facturacion_compra c
JOIN  facturacion_clienteproveedor p ON p.codigo_id = c.proveedor_id
LEFT JOIN facturacion_tipocomprobante t ON t.id = c.tipo_id
WHERE c.empresa_id = 1
  AND c.fecha >= '2026-01-01'
ORDER BY c.fecha;
```
- `JOIN` (INNER): sólo filas con coincidencia en ambas tablas.
- `LEFT JOIN`: todas las de la izquierda; si no hay match, columnas de la derecha en NULL.
- **Truco para encontrar huérfanos:** `LEFT JOIN ... WHERE derecha.id IS NULL`.

### 2.7 Agrupaciones y `HAVING` (condición sobre el agregado)
```sql
SELECT p.razon_social,
       COUNT(*)          AS cant_facturas,
       SUM(c.total)      AS total_comprado,
       SUM(c.saldo)      AS deuda
FROM facturacion_compra c
JOIN facturacion_clienteproveedor p ON p.codigo_id = c.proveedor_id
WHERE c.empresa_id = 1
  AND c.fecha >= '2026-01-01'
GROUP BY p.razon_social
HAVING SUM(c.saldo) > 0            -- HAVING filtra DESPUÉS de agrupar
ORDER BY deuda DESC;
```

### 2.8 Agregados condicionales (`FILTER`) — muy útil para papeles de trabajo
```sql
SELECT to_char(fecha, 'YYYY-MM') AS periodo,
       SUM(total) FILTER (WHERE condic = 1) AS fiscal,
       SUM(total) FILTER (WHERE condic = 2) AS no_fiscal,
       COUNT(*)   FILTER (WHERE estado = 1) AS anuladas,
       SUM(total)                            AS total_general
FROM facturacion_venta
WHERE empresa_id = 1
GROUP BY 1
ORDER BY 1;
```

### 2.9 Subconsultas: `EXISTS` / `NOT EXISTS` / `IN`
```sql
-- Clientes que compraron en 2026
SELECT * FROM facturacion_clienteproveedor cp
WHERE cp.empresa_id = 1
  AND EXISTS (SELECT 1 FROM facturacion_venta v
              WHERE v.cliente_id = cp.codigo_id AND v.fecha >= '2026-01-01');

-- Productos que NUNCA se vendieron
SELECT pr.id, pr.detalle FROM productos_producto pr
WHERE pr.empresa_id = 1
  AND NOT EXISTS (SELECT 1 FROM facturacion_ventaitem vi WHERE vi.producto_id = pr.id);
```

### 2.10 CTE (`WITH`) — encadenar pasos legibles
```sql
WITH ventas_mes AS (
    SELECT cliente_id, SUM(total) AS facturado
    FROM facturacion_venta
    WHERE empresa_id = 1 AND estado = 0
      AND fecha >= date_trunc('month', CURRENT_DATE)
    GROUP BY cliente_id
)
SELECT cp.razon_social, vm.facturado, cp.objetivo_mensual,
       ROUND(vm.facturado * 100 / NULLIF(cp.objetivo_mensual, 0), 2) AS cumplimiento_pct
FROM ventas_mes vm
JOIN facturacion_clienteproveedor cp ON cp.codigo_id = vm.cliente_id
ORDER BY vm.facturado DESC;
```

### 2.11 Funciones de ventana (saldos acumulados, rankings)
```sql
-- Mayor de una cuenta con saldo acumulado
SELECT a.fecha, a.asiento_id, a.concepto, m.debe, m.haber,
       SUM(m.debe - m.haber) OVER (ORDER BY a.fecha, a.asiento_id, m.id) AS saldo_acum
FROM cble_asiento_mov m
JOIN cble_asiento_enc a ON a.asiento_id = m.asiento_id
WHERE a.empresa_id = 1 AND m.cuenta_id = 105 AND a.anulado = false
ORDER BY a.fecha, a.asiento_id, m.id;

-- Top 3 productos por rubro
SELECT * FROM (
  SELECT pr.rubro_id, pr.detalle, SUM(vi.total) AS vendido,
         ROW_NUMBER() OVER (PARTITION BY pr.rubro_id ORDER BY SUM(vi.total) DESC) AS rk
  FROM facturacion_ventaitem vi
  JOIN productos_producto pr ON pr.id = vi.producto_id
  WHERE pr.empresa_id = 1
  GROUP BY pr.rubro_id, pr.detalle
) t WHERE rk <= 3;
```

### 2.12 Jerarquía de cuentas (recursivo)
```sql
WITH RECURSIVE arbol AS (
    SELECT id, jerarquia, cuenta, sumariza_id, 1 AS nivel
    FROM cble_cuentas
    WHERE empresa_id = 1 AND sumariza_id IS NULL
  UNION ALL
    SELECT c.id, c.jerarquia, c.cuenta, c.sumariza_id, a.nivel + 1
    FROM cble_cuentas c
    JOIN arbol a ON c.sumariza_id = a.id
)
SELECT repeat('    ', nivel - 1) || jerarquia || ' - ' || cuenta AS arbol_cuentas
FROM arbol ORDER BY jerarquia;
```

---

## 3. MODIFICACIONES (UPDATE) CON CONDICIONALES

### 3.1 Protocolo obligatorio (3 pasos)
```sql
-- PASO 1: ver qué voy a tocar
SELECT compras_id, numero, total, saldo
FROM facturacion_compra
WHERE empresa_id = 1 AND proveedor_id = 45 AND saldo < 0;

-- PASO 2: modificar en transacción abierta
BEGIN;
UPDATE facturacion_compra
SET    saldo = 0
WHERE  empresa_id = 1 AND proveedor_id = 45 AND saldo < 0;
-- pgAdmin informa "UPDATE n" → ¿n coincide con las filas del PASO 1?

-- PASO 3: si está bien COMMIT, si no ROLLBACK
COMMIT;   -- o  ROLLBACK;
```

### 3.2 `UPDATE ... RETURNING` (ver el resultado sin consultar de nuevo)
```sql
BEGIN;
UPDATE productos_producto
SET    precio_neto  = ROUND(precio_neto * 1.15, 2),
       precio_total = ROUND(precio_neto * 1.15 * (1 + alic_iva/100), 2),
       fec_act      = CURRENT_DATE
WHERE  empresa_id = 1 AND rubro_id = 7
RETURNING id, detalle, precio_neto, precio_total;
ROLLBACK;   -- cambiar a COMMIT cuando la salida sea la esperada
```

### 3.3 `UPDATE` condicional con `CASE` (distinto valor según la fila)
```sql
UPDATE productos_producto
SET margen = CASE
        WHEN cto_adq < 10000            THEN 60
        WHEN cto_adq BETWEEN 10000 AND 50000 THEN 45
        ELSE 30
     END
WHERE empresa_id = 1 AND rubro_id = 3;
```

### 3.4 `UPDATE` con `FROM` (tomando valores de otra tabla)
```sql
-- Copiar la razón social actual del cliente a la venta (campos desnormalizados)
UPDATE facturacion_venta v
SET    cliente_razon_social = cp.razon_social,
       cliente_cuit         = cp.cuit,
       cliente_domicilio    = cp.domicilio
FROM   facturacion_clienteproveedor cp
WHERE  cp.codigo_id = v.cliente_id
  AND  v.empresa_id = 1
  AND  v.cliente_razon_social IS NULL;
```

### 3.5 `UPDATE` con subconsulta correlacionada (recalcular agregados)
```sql
-- Recalcular el saldo de cada factura de compra = total - pagado
UPDATE facturacion_compra
SET    saldo = total - COALESCE(pagado, 0)
WHERE  empresa_id = 1
  AND  saldo <> total - COALESCE(pagado, 0);

-- Recalcular el total de cabecera desde los ítems
UPDATE facturacion_venta v
SET    total = sub.suma
FROM  (SELECT venta_id, SUM(total) AS suma
       FROM facturacion_ventaitem GROUP BY venta_id) sub
WHERE sub.venta_id = v.ventas_id
  AND v.empresa_id = 1
  AND v.total <> sub.suma;
```

### 3.6 Actualización masiva desde una lista de valores
```sql
UPDATE productos_producto p
SET    cto_adq = v.costo
FROM  (VALUES (101, 15000.00),
              (102, 22500.50),
              (103,  9800.00)) AS v(id, costo)
WHERE p.id = v.id AND p.empresa_id = 1;
```

### 3.7 `INSERT ... ON CONFLICT` (upsert)
```sql
INSERT INTO productos_stocksucursal (producto_id, sucursal_id, cantidad)
VALUES (101, 1, 25)
ON CONFLICT (producto_id, sucursal_id)          -- requiere índice único
DO UPDATE SET cantidad = productos_stocksucursal.cantidad + EXCLUDED.cantidad;
```

### 3.8 Bloqueo de filas para cálculos críticos (saldos / asientos)
```sql
BEGIN;
SELECT saldo FROM facturacion_clienteproveedor
WHERE codigo_id = 45 AND empresa_id = 1
FOR UPDATE;                       -- bloquea la fila hasta el COMMIT

UPDATE facturacion_clienteproveedor
SET saldo = saldo - 15000
WHERE codigo_id = 45 AND empresa_id = 1;
COMMIT;
```

---

## 4. BORRADOS (DELETE) CON CONDICIONALES

> ⚠️ Es la operación más peligrosa. **Backup + `BEGIN` + contar antes.**

### 4.1 Protocolo
```sql
-- 1) Contar
SELECT COUNT(*) FROM facturacion_venta
WHERE empresa_id = 1 AND estado = 3 AND fecha < '2025-01-01';

-- 2) Ver una muestra
SELECT * FROM facturacion_venta
WHERE empresa_id = 1 AND estado = 3 AND fecha < '2025-01-01'
LIMIT 20;

-- 3) Borrar en transacción
BEGIN;
DELETE FROM facturacion_venta
WHERE empresa_id = 1 AND estado = 3 AND fecha < '2025-01-01'
RETURNING ventas_id, fecha, numero;
-- verificar el conteo devuelto
ROLLBACK;   -- → COMMIT sólo si coincide
```

### 4.2 `DELETE` con `USING` (condición en otra tabla)
```sql
-- Borrar ítems cuyas ventas fueron rechazadas
BEGIN;
DELETE FROM facturacion_ventaitem vi
USING facturacion_venta v
WHERE v.ventas_id = vi.venta_id
  AND v.empresa_id = 1
  AND v.estado = 3;
ROLLBACK;
```

### 4.3 `DELETE` de huérfanos
```sql
-- Renglones de asiento sin cabecera
BEGIN;
DELETE FROM cble_asiento_mov m
WHERE NOT EXISTS (SELECT 1 FROM cble_asiento_enc a WHERE a.asiento_id = m.asiento_id);
ROLLBACK;
```

### 4.4 Borrar duplicados dejando el más reciente
```sql
BEGIN;
WITH dup AS (
  SELECT codigo_id,
         ROW_NUMBER() OVER (PARTITION BY empresa_id, cuit ORDER BY codigo_id DESC) AS rn
  FROM facturacion_clienteproveedor
  WHERE empresa_id = 1 AND cuit IS NOT NULL AND cuit <> ''
)
DELETE FROM facturacion_clienteproveedor
WHERE codigo_id IN (SELECT codigo_id FROM dup WHERE rn > 1);
ROLLBACK;
```

### 4.5 Alternativa recomendada: **baja lógica**
En el ERP casi nunca conviene borrar. Preferir marcar:
```sql
UPDATE facturacion_venta SET estado = 1 WHERE ventas_id = 998 AND empresa_id = 1;
UPDATE cble_asiento_enc
SET anulado = true, fec_anulacion = NOW()
WHERE asiento_id = 4521 AND empresa_id = 1;
```

### 4.6 Vaciar una tabla completa (sólo en desarrollo)
```sql
TRUNCATE TABLE productos_movimientostock RESTART IDENTITY CASCADE;
```
`CASCADE` arrastra las tablas que la referencian. **Irreversible fuera de transacción.**

### 4.7 Errores típicos de borrado
| Mensaje | Causa | Solución |
|---------|-------|----------|
| `violates foreign key constraint` | Hay hijos apuntando a la fila (`on_delete=PROTECT`) | Borrar primero los hijos, o hacer baja lógica |
| `deadlock detected` | Dos sesiones se bloquean | Reintentar; ordenar siempre igual los updates |
| `current transaction is aborted` | Falló una sentencia dentro del `BEGIN` | `ROLLBACK;` y empezar de nuevo |

---

## 5. TRANSACCIONES Y SEGURIDAD

```sql
BEGIN;                       -- abre transacción
  SAVEPOINT antes_del_paso2; -- punto de retorno intermedio
  -- ... sentencias ...
  ROLLBACK TO antes_del_paso2;   -- deshace sólo hasta ahí
COMMIT;                      -- confirma todo
ROLLBACK;                    -- descarta todo
```

**Modo seguro permanente en pgAdmin:** Query Tool → menú **Edit → Preferences → Query Tool → Auto commit = OFF**. Así toda ejecución queda abierta hasta que hagas `COMMIT` explícito.

**Simulacro sin riesgo — copiar la tabla antes de tocarla:**
```sql
CREATE TABLE bkp_compra_20260725 AS
SELECT * FROM facturacion_compra WHERE empresa_id = 1;
-- ... hacer los cambios ...
-- restaurar si algo salió mal:
-- DELETE FROM facturacion_compra WHERE empresa_id = 1;
-- INSERT INTO facturacion_compra SELECT * FROM bkp_compra_20260725;
DROP TABLE bkp_compra_20260725;   -- limpiar cuando ya no haga falta
```

---

## 6. INSPECCIÓN DEL ESQUEMA (catálogo)

```sql
-- Todas las tablas con su tamaño
SELECT tablename,
       pg_size_pretty(pg_total_relation_size(quote_ident(tablename))) AS tamanio
FROM pg_tables WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(quote_ident(tablename)) DESC;

-- Columnas de una tabla
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'facturacion_compra'
ORDER BY ordinal_position;

-- Claves foráneas que apuntan a una tabla (¿qué me impide borrar?)
SELECT tc.table_name AS tabla_hija, kcu.column_name AS columna
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu ON kcu.constraint_name = tc.constraint_name
JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND ccu.table_name = 'facturacion_clienteproveedor';

-- Índices existentes
SELECT tablename, indexname, indexdef FROM pg_indexes
WHERE schemaname = 'public' AND tablename = 'cble_asiento_mov';

-- CheckConstraints (reglas contables como debe_xor_haber)
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint WHERE conrelid = 'cble_asiento_mov'::regclass;

-- Buscar una columna en toda la base
SELECT table_name, column_name FROM information_schema.columns
WHERE column_name ILIKE '%saldo%' AND table_schema = 'public';
```

---

## 7. RENDIMIENTO

```sql
-- Ver el plan de ejecución real
EXPLAIN ANALYZE
SELECT * FROM facturacion_venta
WHERE empresa_id = 1 AND fecha BETWEEN '2026-01-01' AND '2026-06-30';
```
- `Seq Scan` sobre tabla grande = falta índice.
- `Index Scan` / `Bitmap Heap Scan` = está usando índice.

```sql
-- Crear índice sin bloquear la tabla (producción)
CREATE INDEX CONCURRENTLY idx_venta_emp_fecha
ON facturacion_venta (empresa_id, fecha);

-- Índice parcial (sólo filas relevantes, mucho más chico)
CREATE INDEX idx_compra_pendientes
ON facturacion_compra (empresa_id, proveedor_id) WHERE saldo > 0;

-- Estadísticas y mantenimiento
ANALYZE facturacion_venta;
VACUUM ANALYZE facturacion_venta;

-- Índices que nunca se usan
SELECT relname, indexrelname, idx_scan FROM pg_stat_user_indexes
WHERE idx_scan = 0 ORDER BY relname;
```

**Consultas y bloqueos activos:**
```sql
SELECT pid, state, now() - query_start AS duracion, query
FROM pg_stat_activity
WHERE state <> 'idle' AND pid <> pg_backend_pid()
ORDER BY duracion DESC;

-- Cancelar / matar una consulta colgada
SELECT pg_cancel_backend(12345);     -- suave
SELECT pg_terminate_backend(12345);  -- forzado
```

---

## 8. CONTROLES CONTABLES LISTOS PARA USAR

### 8.1 Asientos descuadrados (Debe ≠ Haber)
```sql
SELECT a.asiento_id, a.fecha, a.concepto,
       SUM(m.debe) AS total_debe, SUM(m.haber) AS total_haber,
       SUM(m.debe) - SUM(m.haber) AS diferencia
FROM cble_asiento_enc a
JOIN cble_asiento_mov m ON m.asiento_id = a.asiento_id
WHERE a.empresa_id = 1 AND a.anulado = false
GROUP BY a.asiento_id, a.fecha, a.concepto
HAVING SUM(m.debe) <> SUM(m.haber)
ORDER BY a.fecha;
```

### 8.2 Sumas y saldos por cuenta
```sql
SELECT c.jerarquia, c.cuenta, c.tipo,
       SUM(m.debe) AS debe, SUM(m.haber) AS haber,
       SUM(m.debe) - SUM(m.haber) AS saldo
FROM cble_asiento_mov m
JOIN cble_asiento_enc a ON a.asiento_id = m.asiento_id
JOIN cble_cuentas     c ON c.id = m.cuenta_id
WHERE a.empresa_id = 1 AND a.anulado = false
  AND a.fecha BETWEEN '2026-01-01' AND '2026-12-31'
GROUP BY c.jerarquia, c.cuenta, c.tipo
HAVING SUM(m.debe) <> 0 OR SUM(m.haber) <> 0
ORDER BY c.jerarquia;
```

### 8.3 Comprobantes sin asiento contable
```sql
SELECT compras_id, fecha, punto, numero, total
FROM facturacion_compra
WHERE empresa_id = 1 AND condic = 1 AND asiento_id IS NULL
ORDER BY fecha;
```

### 8.4 Asiento cuyo monto de cabecera no coincide con los renglones
```sql
SELECT a.asiento_id, a.monto AS monto_cabecera, SUM(m.debe) AS suma_debe
FROM cble_asiento_enc a JOIN cble_asiento_mov m ON m.asiento_id = a.asiento_id
WHERE a.empresa_id = 1 AND a.anulado = false
GROUP BY a.asiento_id, a.monto
HAVING a.monto <> SUM(m.debe);
```

### 8.5 Saltos de numeración en comprobantes (control fiscal)
```sql
SELECT tipo_id, punto, numero,
       numero - LAG(numero) OVER (PARTITION BY tipo_id, punto ORDER BY numero) AS salto
FROM facturacion_venta
WHERE empresa_id = 1 AND estado <> 1
ORDER BY tipo_id, punto, numero;
-- Todo salto <> 1 es un hueco de numeración a investigar
```

### 8.6 Cuenta corriente vs. saldo del maestro
```sql
SELECT cp.codigo_id, cp.razon_social, cp.saldo AS saldo_maestro,
       COALESCE(SUM(c.saldo), 0) AS saldo_calculado,
       cp.saldo - COALESCE(SUM(c.saldo), 0) AS diferencia
FROM facturacion_clienteproveedor cp
LEFT JOIN facturacion_compra c ON c.proveedor_id = cp.codigo_id AND c.empresa_id = cp.empresa_id
WHERE cp.empresa_id = 1 AND cp.tipo_entidad = 2
GROUP BY cp.codigo_id, cp.razon_social, cp.saldo
HAVING cp.saldo <> COALESCE(SUM(c.saldo), 0);
```

---

## 9. AL MODIFICAR POR SQL — RECÁLCULOS QUE DJANGO YA NO HARÁ

Si tocás importes directamente en la base, **la lógica de `recalcular_totales()` no corre**. Cadena a mantener a mano:

| Si modificás… | Debés recalcular… |
|---------------|-------------------|
| `facturacion_ventaitem.total` | `facturacion_venta.neto`, `.iva`, `.total`, `.saldo` |
| `facturacion_compraitem.total` | `facturacion_compra.subtotal`, `.neto`, `.iva`, `.total`, `.saldo` |
| `facturacion_compra.pagado` | `facturacion_compra.saldo` = `total - pagado` |
| Cabeceras de venta/compra | Asiento en `cble_asiento_enc` / `cble_asiento_mov` y `cble_libro_iva_*` |
| `productos_producto.stock` | `productos_stocksucursal.cantidad` (deben cuadrar) |
| Cualquier saldo | `facturacion_clienteproveedor.saldo` |

**Alternativa segura:** en vez de SQL crudo, usar el shell de Django, que sí dispara toda la lógica:
```powershell
python manage.py shell
```
```python
from facturacion.models import Compra
c = Compra.objects.get(compras_id=123)
c.recalcular_totales()      # respeta prorrateos, alícuotas y saldos
```

Después de un `INSERT` manual con `id` explícito, **hay que reposicionar la secuencia** o Django dará error de PK duplicada:
```sql
SELECT setval(pg_get_serial_sequence('facturacion_compra', 'compras_id'),
              (SELECT MAX(compras_id) FROM facturacion_compra));
```

---

## 10. IMPORTAR / EXPORTAR EN pgAdmin 4

**Exportar resultado a CSV/Excel:** ejecutar la consulta → ícono de descarga sobre la grilla de resultados (**Download as CSV**, `F8`).

**Exportar/Importar una tabla:** clic derecho sobre la tabla → **Import/Export Data…** → pestaña *Options* (Format `csv`, Header `Yes`, Delimiter `,`, Encoding `UTF8`) → pestaña *Columns* para elegir columnas.

Por SQL (el archivo queda en el servidor):
```sql
COPY (SELECT * FROM facturacion_venta WHERE empresa_id = 1 AND fecha >= '2026-01-01')
TO 'D:/JM_Soft/scratch/ventas_2026.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

COPY productos_producto (cod_prov, detalle, cto_adq)
FROM 'D:/JM_Soft/scratch/lista_precios.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
```
> Los CSV generados van a `scratch/` (carpeta ignorada por git, según las reglas del proyecto).

---

## 11. BACKUP Y RESTAURACIÓN

**Desde pgAdmin:** clic derecho sobre la base → **Backup…** (formato *Custom* para poder restaurar selectivamente) / **Restore…**.

**Desde consola (PowerShell):**
```powershell
# Backup completo comprimido
& "C:\Program Files\PostgreSQL\16\bin\pg_dump.exe" -U postgres -h localhost -F c -b -v -f "D:\JM_Soft\scratch\erp_20260725.backup" nombre_base

# Sólo una tabla
& "C:\Program Files\PostgreSQL\16\bin\pg_dump.exe" -U postgres -t facturacion_compra -F c -f "D:\JM_Soft\scratch\compras.backup" nombre_base

# Restaurar
& "C:\Program Files\PostgreSQL\16\bin\pg_restore.exe" -U postgres -d nombre_base -c -v "D:\JM_Soft\scratch\erp_20260725.backup"
```
El proyecto ya cuenta con `respaldo_diario.bat` en la raíz.

---

## 12. ATAJOS Y DETALLES DE pgAdmin 4

| Atajo | Acción |
|-------|--------|
| `Alt+Shift+Q` | Abrir Query Tool |
| `F5` | Ejecutar (sólo lo seleccionado, si hay selección) |
| `F7` | Explain |
| `Shift+F7` | Explain Analyze |
| `F8` | Descargar resultado como CSV |
| `Ctrl+Space` | Autocompletado de tablas/columnas |
| `Ctrl+/` | Comentar / descomentar líneas |
| `Ctrl+Shift+K` | Borrar la ventana de consulta |

- **Auto commit / Auto rollback:** *Query Tool → Preferences → Query Tool*. Trabajar con **Auto commit OFF** en producción.
- **Edición en grilla:** si la consulta es `SELECT * FROM tabla` sin joins, se pueden editar celdas directamente y guardar con `F6`. Cómodo para retoques puntuales, pero **igual saltea la lógica de Django** (§9).
- **Historial:** pestaña *Query History* del Query Tool — sirve para reconstruir qué se ejecutó.

---

## 13. PLANTILLA DE INTERVENCIÓN (copiar y pegar)

```sql
-- =========================================================
-- Papel de trabajo:  <descripción>
-- Fecha:             <AAAA-MM-DD>     Responsable: <nombre>
-- Empresa afectada:  <empresa_id = N>
-- Backup previo:     <ruta del .backup>
-- =========================================================

-- (1) FOTO PREVIA
SELECT COUNT(*) AS filas_afectadas, SUM(total) AS importe_afectado
FROM <tabla>
WHERE empresa_id = <N> AND <condición>;

-- (2) MUESTRA
SELECT * FROM <tabla>
WHERE empresa_id = <N> AND <condición>
LIMIT 20;

-- (3) INTERVENCIÓN
BEGIN;
UPDATE <tabla>
SET    <campo> = <valor>
WHERE  empresa_id = <N> AND <condición>
RETURNING *;

-- (4) CONTROL POSTERIOR (dentro de la misma transacción)
SELECT COUNT(*) FROM <tabla>
WHERE empresa_id = <N> AND <condición_esperada_luego_del_cambio>;

-- (5) DECISIÓN
-- COMMIT;    -- confirmar
ROLLBACK;     -- descartar (valor por defecto de este papel)
```

---

## 14. CHECKLIST FINAL

- [ ] ¿Backup hecho y verificado?
- [ ] ¿El `WHERE` incluye `empresa_id`?
- [ ] ¿Corrí el `SELECT` de control con el mismo `WHERE`?
- [ ] ¿La cantidad de filas afectadas coincide con lo esperado?
- [ ] ¿Está todo dentro de `BEGIN;`?
- [ ] ¿Hay agregados o asientos que quedan que recalcular (§9)?
- [ ] ¿Registré la intervención en `docs/walkthrough.txt`?
