# Plan 009 — Reportes Contables y Gerenciales

## Estado: 🔶 Parcial (Libro Diario, Mayor y Balance ya existen como vistas HTMX)

## Objetivo
Completar los reportes contables faltantes y agregar reportes gerenciales exportables. Incluye cierre de ejercicio lógico.

## Reportes a Implementar

| Reporte | Estado | Formato salida |
|---------|--------|---------------|
| Libro Diario | ✅ Vista HTMX | Falta: export Excel/PDF |
| Libro Mayor | ✅ Vista HTMX | Falta: export Excel/PDF |
| Balance Sumas y Saldos | ✅ Vista HTMX | Falta: export Excel/PDF |
| Financiero Mensual | ❌ Pendiente | Excel |
| Cuentas Corrientes (cli/pro) | ❌ Pendiente | HTMX + Excel |
| Ranking Ventas/Compras | ❌ Pendiente | HTMX + Excel |
| Stock valorizado | ❌ Pendiente | Excel |
| Cierre de Ejercicio | ❌ Pendiente | Asiento automático |
| SICORE (retenciones) | ❌ Pendiente | TXT formato AFIP |

## Servicios

| Servicio | Archivo | Qué hace |
|----------|---------|----------|
| Export Excel | `contable/services/reportes.py` | Genera Excel con xlsxwriter |
| Cierre ejercicio | `contable/services/cierre.py` | Asiento cierre resultados + asiento apertura |

## Dependencias
- Requiere: `contable` ✅

## Referencia VFP
- PRGs: `diario_gral.prg`, `genera_vista_contable.prg`
- FRX: `diario_gral.frx`, `mayor_g.frx`, `suma_saldo_*.scx`

## Criterio de Hecho
- [ ] Exportar Libro Diario a Excel
- [ ] Cierre de ejercicio genera asiento de cierre + apertura
- [ ] Cuentas corrientes se consultan por cliente/proveedor
