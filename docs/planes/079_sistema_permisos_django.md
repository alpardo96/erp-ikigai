# Plan 079 — Sistema de Permisos Nativo (Django Groups & Permissions)

## Objetivo
Implementar un sistema de roles y permisos aprovechando los modelos nativos de Django (`django.contrib.auth.models.Group` y `Permission`), beneficiándonos de su robustez y rendimiento nativo (`user.has_perm()`). Para evitar la interfaz tosca del Django Admin, construiremos una UI profesional propia con Tailwind CSS y HTMX en el módulo de Configuración.
Como enfoque iterativo, comenzaremos aplicando la restricción visual directamente en el menú de navegación (`base.html` y hooks) y posteriormente se aplicarán reglas de edición granulares en el código (`puede_editar`).

> [!TIP]
> **Punto de vista:** Tienes toda la razón. Aprovechar los modelos nativos de Django es la decisión más inteligente arquitectónicamente. Django genera automáticamente 4 permisos por cada modelo de la base de datos (Ver, Añadir, Cambiar, Eliminar). Al usar esto, nos ahorramos crear tablas personalizadas, ganamos los decoradores nativos de Django (`@permission_required`) y el rendimiento está ultra-optimizado. El único problema histórico de Django es su panel de administración, el cual vamos a ignorar por completo construyendo nuestra propia vista.

## Open Questions
- **Agrupación Visual de Permisos**: Django crea permisos automáticos para *todos* los modelos (ej: `view_cliente`, `add_cliente`, `delete_asiento`). En la pantalla de creación de Roles, ¿prefieres que agrupe los permisos automáticamente por la "App" a la que pertenecen (ej. bloque de Facturación, bloque de Contabilidad, bloque de Productos), o prefieres que armemos un script que traduzca estos permisos a nombres más amigables (ej. en lugar de "Puede añadir cliente", diga "Crear Cliente")?

## Proposed Changes

### 1. Panel de Configuración UI (CRUD de Roles)
#### [MODIFY] `core/views_config.py`
- Añadir la pestaña `roles` (Grupos) al Hub de Configuración.
- Pasar el QuerySet de `Group.objects.all()` y `Permission.objects.select_related('content_type')` agrupado por aplicación (app_label) al contexto.
#### [MODIFY] `templates/configuracion/hub.html`
- Inyectar el botón de acceso rápido a "Roles y Permisos".
#### [NEW] `templates/configuracion/partials/roles.html`
- Interfaz del listado de Roles (Grupos).
#### [NEW] `templates/configuracion/modals/rol_modal.html`
- Modal para Crear/Editar un Rol. Incluirá un grid agrupado por Módulos/Apps. Por cada modelo, se mostrarán checkboxes sutiles para (Ver | Añadir | Editar | Eliminar) mapeados directamente a los IDs de los `Permission` de Django.

### 2. Formulario de Usuario
#### [MODIFY] `usuarios/forms.py` y `templates/configuracion/modals/usuario_form.html`
- Reemplazar la lista de checkboxes estáticos (`permiso_clientes_ver`, etc.) por un selector de Roles (Groups).
- Añadir un selector múltiple avanzado para los Permisos Individuales Adicionales (directamente al campo `user_permissions` nativo del usuario).
- **Mantenimiento**: Eliminar los booleanos obsoletos del código del formulario (aunque las columnas sigan en la DB por ahora, luego se hará la migración para borrarlas).

### 3. Restricciones en Vistas y Menús (Primera Fase)
#### [MODIFY] *Templates Transversales* (`base.html`, `menu_sidebar.html`, `hooks`)
- Aplicar bloqueos de visibilidad en el menú principal utilizando los tags nativos de Django: `{% if perms.facturacion.view_cliente %}`.
- Con esto, ocultaremos las puertas de acceso a los distintos módulos para los usuarios que no tengan el permiso de "Ver".

## Verification Plan
### Automated Tests
- Validar mediante scripts que al asignar un grupo a un usuario, `user.has_perm()` responda correctamente.
### Manual Verification
- Ingresar como administrador.
- Crear un rol "Solo Lectura Clientes" y asignarle únicamente el permiso `view_cliente`.
- Asignar el rol a un usuario de prueba.
- Iniciar sesión con el usuario de prueba y validar que en el menú lateral solo aparezca el acceso a Clientes, y que no pueda guardar ni eliminar (sujetando los botones de la UI al permiso).
