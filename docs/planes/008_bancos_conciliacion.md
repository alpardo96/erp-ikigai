# Plan 008 — Bancos y Conciliación Bancaria

## Estado: ❌ Pendiente

## Objetivo
Implementar la captura de extractos bancarios (homebanking), conciliación automática sistema vs banco, contabilización de movimientos bancarios y gestión de diferencias. Módulo con alto valor comercial.

## Modelos

| Modelo | App | Campos clave | Notas |
|--------|-----|-------------|-------|
| `ExtractoBancario` | `tesoreria` | FK cuenta_bancaria, `periodo`, `fecha_importacion`, `archivo`, `usuario` | Cabecera de importación |
| `ExtractoItem` | `tesoreria` | FK extracto, `fecha`, `descripcion`, `debito`, `credito`, `saldo`, `conciliado` | Cada línea del extracto |
| `Conciliacion` | `tesoreria` | FK cuenta_bancaria, `fecha_desde`, `fecha_hasta`, `saldo_sistema`, `saldo_banco`, `diferencia` | Cabecera de conciliación |
| `ConciliacionDetalle` | `tesoreria` | FK conciliacion, FK extracto_item, FK asiento_linea (nullable), `estado` | Matching de partidas |

## Servicios

| Servicio | Archivo | Firma | Qué hace |
|----------|---------|-------|----------|
| Importar extracto | `tesoreria/services/bancos.py` | `importar_extracto(cuenta, archivo)` | Parsea Excel/CSV de banco |
| Conciliar | `tesoreria/services/conciliacion.py` | `conciliar_automatico(cuenta, periodo)` | Matching por monto+fecha |
| Contabilizar mvtos | `contable/services/contabilizacion.py` | `contabilizar_movimiento_bancario(item)` | Genera asiento por mvto bancario |

## Archivos a Crear/Modificar
- `tesoreria/models.py` — agregar modelos de extracto y conciliación
- `tesoreria/services/bancos.py` — importación y normalización por banco
- `tesoreria/services/conciliacion.py` — matching automático
- Templates HTMX para vista de conciliación

## Tests Mínimos

| Test | Qué verifica |
|------|-------------|
| `test_importar_extracto_excel` | Parseo correcto de Excel bancario |
| `test_conciliacion_automatica` | Matching por monto+fecha funciona |
| `test_diferencias_pendientes` | Las partidas no conciliadas se listan |

## Dependencias
- Requiere: `contable` ✅, `tesoreria` 🔶 (debe completarse primero)

## Referencia VFP
- PRGs: `contabiliza_res_bcario.prg` (patrón completo de asiento desde resumen bancario)

## Criterio de Hecho
- [ ] Importar extracto Excel y ver los items
- [ ] Conciliación automática encuentra matches
- [ ] Diferencias se listan correctamente
- [ ] Tests pasan
