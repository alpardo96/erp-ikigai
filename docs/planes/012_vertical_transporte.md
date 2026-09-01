# Plan 012 — Vertical Transporte

## Estado: ❌ Pendiente

## Objetivo
Implementar el módulo de transporte/logística: órdenes de carga, repartos, hojas de ruta, liquidación de choferes y fleteros.

## Modelos a Crear

| Modelo | App | Campos clave | Notas |
|--------|-----|-------------|-------|
| `Chofer` | `transporte` | `nombre`, `documento`, `tipo` (propio/fletero), `activo` | Conductor |
| `Movil` | `transporte` | `patente`, `tipo`, `capacidad`, `activo` | Vehículo |
| `OrdenCarga` | `transporte` | FK empresa, `fecha`, FK cliente, `destino`, `peso`, `estado` | Solicitud de envío |
| `HojaRuta` | `transporte` | FK chofer, FK movil, `fecha`, `estado` | Hoja de ruta diaria |
| `HojaRutaDetalle` | `transporte` | FK hoja_ruta, FK orden_carga, `orden_entrega` | Ordenes asignadas |
| `LiquidacionChofer` | `transporte` | FK chofer, `periodo`, `total_fletes`, `comision`, `neto` | Liquidación periódica |

## Dependencias
- Requiere: `facturacion` ✅, `006_permisos_modulares`

## Referencia VFP
- PRGs: `genera_vista_transporte.prg`, `genera_vista_expresorivadavia.prg`
- SCX: `cons_orden_carga`, `repartos`, ~100 formularios de transporte

## Criterio de Hecho
- [ ] CRUD de choferes, móviles, órdenes de carga
- [ ] Armar hoja de ruta asignando órdenes
- [ ] Liquidación de choferes calcula comisiones
