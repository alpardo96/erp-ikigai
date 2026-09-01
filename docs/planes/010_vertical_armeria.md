# Plan 010 — Vertical Armería

## Estado: 🔶 Parcial (modelos ExtensionArmeria y Subproducto ya existen)

## Objetivo
Completar la vertical de armería: inventario de armas con trazabilidad individual (serie/CUIM), credenciales CLU, campos DMP en ventas, y reportes específicos del rubro.

## Lo que ya existe
- `facturacion.ExtensionArmeria` — CLU y vencimiento por cliente
- `productos.Subproducto` — bienes individuales con serie, CUIM, estado, propiedad
- `facturacion.VentaItem` — campos `credencial` y `dmp`

## Lo que falta

| Funcionalidad | Detalle |
|--------------|---------|
| Vista de inventario de armas | Listado filtrable de Subproductos con estado (en stock/vendido) |
| Validación de CLU vigente | Al vender un arma, verificar que la CLU del cliente no esté vencida |
| Reportes ANMaC/ARCA | Listados para presentar al organismo regulador |
| ABM de Subproductos | Carga y edición desde la UI (no solo admin) |

## Dependencias
- Requiere: `facturacion` ✅, `productos` ✅, `006_permisos_modulares` (para habilitar la vertical)

## Referencia VFP
- SCX: `inventario_armas.scx`
- DBFs: tablas de inventario con serie, CUIM, estado

## Criterio de Hecho
- [ ] Inventario de armas visible y filtrable en la UI
- [ ] Venta de arma valida CLU vigente (warning si vencida)
- [ ] Subproducto se marca como vendido al facturar
