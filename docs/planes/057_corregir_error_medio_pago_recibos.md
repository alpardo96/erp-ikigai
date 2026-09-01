# Plan de Implementación 057: Inicialización de Medios de Pago por Empresa y Corrección en Guardado de Recibos

## Resumen del Problema Diagnosticado
Al presionar "Guardar recibo" en la **Empresa 2 (ARMERIA ARMAR SAS)** para la cobranza en efectivo (Recibo `RC 0001-00000003`), el sistema emitió un error de medio de pago.

### Causa Raíz Exacta:
1. **Falta de Medios de Pago en Empresa 2 y 3**: La tabla `tesoreria_medio_pago` solo contenía registros cargados para `empresa_id = 1`. Cuando la función `procesar_recibo` buscó `MedioPago.objects.filter(empresa_id=2, categoria='EFE').first()`, obtuvo `None` y lanzó la excepción: `No se encontró MedioPago configurado para la categoría EFE-ARS`.
2. **Falta de Rollback de Transacción al Fallar**: La vista `procesar_recibo` en `tesoreria/views_htmx.py` capturaba la excepción `except Exception as e:` sin llamar a `transaction.set_rollback(True)`. Por este motivo, la transacción no se deshacía del todo y dejó guardados encabezados huérfanos de recibos (Recibos ID 6, 7 y 8) sin movimiento de caja ni asiento contable.
3. **Búsqueda Imprecisa de Medios de Pago**: El backend buscaba por `categoria='EFE'`, lo que hacía que `EFE-ARS` y `EFE-USD` obtuvieran el mismo registro si ambos compartían la categoría `EFE`.

---

## Decisión de Arquitectura Confirmada

- **Aislamiento Estricto por Empresa**: Se mantiene la relación `MedioPago -> Empresa` (`empresa_id`). Cada `MedioPago` está vinculado a la clave primaria única (`cuenta_contable_id`) del plan de cuentas (`cble_cuentas`) de la empresa correspondiente.

---

## Acciones y Cambios Realizados

### 1. Base de Datos (`tesoreria_medio_pago`)
- Reset de la secuencia PostgreSQL `tesoreria_medio_pago_id_seq`.
- Carga de catálogo de Medios de Pago para **Empresa 2 (ARMERIA ARMAR SAS)**:
  - `EFE-ARS`: Efectivo Pesos -> Cta. 215 (`CAJA`)
  - `EFE-USD`: Efectivo Dólares -> Cta. 215 (`CAJA`)
  - `CHQ-TER`: Cheques de Terceros -> Cta. 216 (`VALORES EN CARTERA`)
  - `TRA-BCO`: Transferencia Bancaria -> Cta. 217 (`BANCO MACRO CTA CTE $`)
  - `RET-GCIA`: Retención Ganancias -> Cta. 236 (`AFIP-IMP.GCIAS RET. O PERC.`)
  - `RET-IIBB`: Retención IIBB -> Cta. 253 (`DGR - IIBB SALDO A FAVOR`)
- Carga de catálogo de Medios de Pago para **Empresa 3 (LOPEZ RIOS Y ASOCIADOS SA)**:
  - `EFE-ARS`: Efectivo Pesos -> Cta. 483 (`CAJA`)
  - `EFE-USD`: Efectivo Dólares -> Cta. 483 (`CAJA`)
  - `CHQ-TER`: Cheques de Terceros -> Cta. 484 (`VALORES EN CARTERA`)
  - `TRA-BCO`: Transferencia Bancaria -> Cta. 485 (`BANCO PATAGONIA`)
  - `RET-GCIA`: Retención Ganancias -> Cta. 498 (`AFIP-IMP.GCIAS RET. O PERC.`)
  - `RET-IIBB`: Retención IIBB -> Cta. 512 (`DGR - IIBB SALDO A FAVOR`)
- Eliminación de recibos huérfanos sin movimiento de caja ni asiento (ID 6, 7 y 8) creados en la Empresa 2 durante las pruebas fallidas anteriores.

---

### 2. Capa de Servicios y Lógica de Negocio (`tesoreria`)

#### [MODIFY] `tesoreria/views_htmx.py`
- En `procesar_recibo` y `procesar_orden_pago`:
  1. Búsqueda jerárquica por código específico (`EFE-ARS`, `EFE-USD`, `TRA-BCO`, `CHQ-TER`) con fallback por categoría.
  2. Adición de `transaction.set_rollback(True)` en bloques `except Exception as e:` para evitar comprobantes huérfanos.

---

## Verificación

1. **DB Seed**: Confirmado en la base de datos que Empresa 2 y Empresa 3 disponen de sus 6 medios de pago habilitados.
2. **Cuentas Contables**: Cada medio de pago apunta a la cuenta correspondiente dentro del plan de cuentas de la empresa.
3. **Limpieza de Recibos**: Los recibos de prueba anteriores fueron removidos.
