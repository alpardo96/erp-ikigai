# Plan 014 — Seguridad y Deploy

## Estado: ❌ Pendiente (antes de go-live)

## Objetivo
Preparar el proyecto para uso productivo con datos reales: variables de entorno, rotación de credenciales, backups, hardening y auditoría de accesos.

## Checklist de Seguridad

| Tarea | Detalle | Prioridad |
|-------|---------|-----------|
| Variables de entorno | `django-environ` + `.env` no versionado. Mover `SECRET_KEY`, credenciales DB | Alta |
| Rotar password Postgres | El actual está en el repo (`JM_Soft`) — cambiarlo | Alta |
| `DEBUG = False` | + `ALLOWED_HOSTS` explícito | Alta |
| CSRF/Session seguras | `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` (con HTTPS) | Media |
| Backup automático | `pg_dump` + cifrado GPG + destino fuera del servidor | Alta |
| Permisos DB | Usuario app ≠ superuser Postgres | Media |
| Auditoría de accesos | Loguear logins (éxito/fallo) + operaciones sensibles | Media |
| `python manage.py check --deploy` | Debe pasar sin warnings críticos | Alta |
| Logging estructurado | Logger por app → archivo rotativo `logs/erp-ikigai.log` | Media |

## Deploy

| Opción | Detalle |
|--------|---------|
| PyInstaller (.exe) | Objetivo principal: distribución standalone como el VFP |
| Servidor local | Django + Postgres en red local del estudio contable |

## Dependencias
- Requiere: todos los módulos operativos funcionales

## Criterio de Hecho
- [ ] Clonar repo en máquina limpia no expone credenciales
- [ ] `check --deploy` pasa sin warnings críticos
- [ ] Backup automático funciona
- [ ] Logging registra operaciones sensibles
