# Plan 013 — Migración de Datos VFP

## Estado: ❌ Pendiente (antes de go-live)

## Objetivo
Importar datos históricos del sistema VFP (DBFs) a PostgreSQL mediante scripts repetibles, controlados por empresa/ejercicio, con auditoría de lotes e idempotencia.

## Estrategia

| Bloque | Fuente VFP | Destino Django | Prioridad |
|--------|-----------|---------------|-----------|
| Empresas / ejercicios | `parametros.dbf` | `empresas.Empresa`, `empresas.Ejercicio` | 1 |
| Plan de cuentas | `cuentas` en carpeta ejercicio | `contable.Cuenta` | 1 |
| Clientes/proveedores | `cli_pro.dbf` | `facturacion.ClienteProveedor` | 1 |
| Comprobantes | `lib_iva.dbf`, compras/ventas | `facturacion.Compra`, `facturacion.Venta` | 2 |
| Asientos | `asto_enc` / `asto_mov` | `contable.Asiento`, `contable.AsientoLinea` | 2 |
| Productos y stock | Tablas de productos | `productos.Producto`, `StockSucursal` | 2 |
| Auxiliares/reportes | `aux_*`, `tot_*` | NO migrar — regenerar | — |

## Implementación
- Management command: `python manage.py importar_legacy_dbf --carpeta=Eje_NNN --empresa=X`
- Librería: `dbfread` con `encoding='latin-1'`, `char_decode_errors='replace'`
- Lotes de `bulk_create(batch_size=1000)`
- Tabla auxiliar `_legacy_id_map(modelo, id_vfp, id_django)` para resolver FKs
- Idempotencia: si se corre 2 veces, no duplica
- Log detallado de filas saltadas/errores

## Dependencias
- Requiere: todos los módulos core implementados

## Criterio de Hecho
- [ ] Importar empresa de prueba completa
- [ ] Saldos importados coinciden con los del VFP
- [ ] Correr 2 veces no duplica datos
- [ ] Log muestra errores claros
