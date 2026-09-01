# Plan 006 — Permisos Modulares Flexibles

## Estado: ❌ Pendiente

## Objetivo
Reemplazar los permisos hardcoded por vertical (`permiso_armeria_*`, `permiso_josen_*`) en el modelo `Perfil` por un sistema flexible basado en tablas: `ModuloNegocio` + `PermisoUsuarioModulo`. Sumar módulos nuevos será un insert, no una migración.

## Modelos

| Modelo | App | Campos clave | Notas |
|--------|-----|-------------|-------|
| `ModuloNegocio` | `usuarios` | `codigo` (unique), `nombre`, `activo` | Ej: 'armeria', 'colegio', 'transporte' |
| `PermisoUsuarioModulo` | `usuarios` | FK `perfil`, FK `modulo`, `puede_ver`, `puede_editar` | `unique_together = ('perfil', 'modulo')` |

## Servicios

| Servicio | Archivo | Firma | Qué hace |
|----------|---------|-------|----------|
| Helper de permisos | `usuarios/models.py` | `Perfil.tiene_permiso(modulo_codigo, accion)` | Consulta rápida si el usuario tiene acceso |

## Archivos a Crear/Modificar
- `usuarios/models.py` — agregar `ModuloNegocio`, `PermisoUsuarioModulo`, helper `tiene_permiso()`
- `usuarios/admin.py` — registrar inline si se necesita para debug
- Migración de datos: convertir permisos hardcoded existentes a registros en las nuevas tablas
- Migración: eliminar campos `permiso_armeria_*`, `permiso_josen_*` de `Perfil`
- Hub de Configuración: ABM de módulos y asignación de permisos

## Tests Mínimos

| Test | Qué verifica |
|------|-------------|
| `test_crear_modulo_sin_migracion` | Crear módulo "inmobiliaria" solo con insert |
| `test_permiso_ver_modulo` | Asignar permiso de ver, verificar acceso |
| `test_sin_permiso_denegado` | Sin permiso, `tiene_permiso()` retorna False |
| `test_migracion_permisos_legacy` | Los permisos hardcoded se migran correctamente |

## Dependencias
- Requiere: `core`, `empresas` (ya listos)

## Referencia VFP
- DBFs: `aux_acceso.dbf` (91 entradas con IDs jerárquicos `A-`, `B-`, `C-`, etc.)
- PRGs: Control en `balances.prg` → `oApp.selec_menu`

## Criterio de Hecho
- [ ] Crear módulo "inmobiliaria" y asignar permisos sin tocar código
- [ ] Los campos hardcoded `permiso_armeria_*` / `permiso_josen_*` ya no existen en `Perfil`
- [ ] Tests pasan
