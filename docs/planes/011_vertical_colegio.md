# Plan 011 — Vertical Colegio

## Estado: ❌ Pendiente

## Objetivo
Implementar el módulo de gestión escolar: alumnos, matrículas, cuotas con coeficientes, devengamiento, cobranzas y caja colegio. Cliente principal: IPJA (CUIT 30638118382, exento de IVA).

## Modelos a Crear

| Modelo | App | Campos clave | Notas |
|--------|-----|-------------|-------|
| `Alumno` | `colegio` | FK cliente_proveedor, `nivel`, `grado`, `division`, `activo` | Extensión del tercero como alumno |
| `Matricula` | `colegio` | FK alumno, `anio`, `monto_base`, `coeficiente`, `monto_final` | Inscripción anual |
| `CuotaColegio` | `colegio` | FK matricula, `mes`, `monto`, `pagado`, `fecha_pago` | Cuota mensual devengada |
| `CajaColegio` | `colegio` | `fecha`, `concepto`, `ingreso`, `egreso`, `saldo` | Caja específica del colegio |

## Servicios

| Servicio | Qué hace |
|----------|----------|
| `devengar_cuotas(anio, mes)` | Genera cuotas para todos los alumnos activos con sus coeficientes |
| `facturar_cuotas_masivo(mes)` | Genera facturas C masivas para las cuotas pendientes |

## Dependencias
- Requiere: `facturacion` ✅, `006_permisos_modulares`

## Referencia VFP
- PRGs: `col_actualiza_devenga_cobros.prg`, `genera_vista_colegio.prg`
- Modelo existente: `ExtensionJosen` con `coeficiente` y `RubroJosen`

## Criterio de Hecho
- [ ] Alta de alumnos y matrículas
- [ ] Devengamiento mensual genera cuotas
- [ ] Facturación masiva emite FC para cuotas pendientes
