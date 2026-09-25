# Plan de Implementación: Deshabilitación y Filtrado Condicional (Solo Administrador) en Clientes/Proveedores y Productos

## 1. Contexto y Objetivos
El usuario ha solicitado estandarizar y blindar la lógica de **deshabilitar** (soft-delete / inactivación) para **Clientes y Proveedores (clipro)** y **Productos**, asegurando:
1. **Acción Restringida:** Únicamente los usuarios con rol de **Administrador** (`is_superuser`, `is_staff` o `perfil.es_admin_sistema`) pueden deshabilitar o rehabilitar un cliente, proveedor o producto.
2. **Filtro de Estado Exclusivo para Administrador:** En las pantallas principales de listado, solo el Administrador tendrá acceso al selector de estados:
   - `Habilitados` (opción predeterminada).
   - `Deshabilitados`.
   - `Todos`.
3. **Comportamiento para el Resto de los Roles:** Vendedores, cajeros y demás usuarios estándar nunca verán el selector de estados ni los registros deshabilitados; el backend forzará siempre y de forma estricta que solo se listen y autocompleten registros activos (`activo=True`). Tampoco visualizarán los botones de acción para deshabilitar o habilitar.

---

## 2. Análisis del Estado Actual

### A. Clientes y Proveedores (`ClienteProveedor`):
- **Modelo:** Actualmente `ClienteProveedor` en `facturacion/models.py` **no** tiene un campo `activo` a nivel de modelo base. Solo existía un campo `activo` dentro del modelo satélite `ExtensionArmeria`, lo cual dejaba al resto de las empresas con borrado físico `cliente.delete()` que ponía en riesgo la integridad referencial.
- **Acción actual:** En `facturacion/views_htmx.py` (`eliminar_cliente`), cualquier usuario autenticado podía disparar el borrado. Para Armería se seteaba `armeria.activo = False`, pero para las demás se ejecutaba `cliente.delete()`.
- **Buscador:** `buscar_clientes` no disponía de filtro por estado de activación y en la plantilla `cliente_table_rows.html` el botón de eliminar era visible para todos los usuarios.

### B. Productos (`Producto`):
- **Modelo:** `Producto` en `productos/models.py` ya posee el campo `activo = models.BooleanField(default=True, db_index=True)`.
- **Acción actual:** En `productos/views_htmx.py` (`eliminar_producto`), la acción hacía `producto.activo = False`, pero no validaba rol de Administrador ni permitía la acción inversa de **rehabilitar** (`producto.activo = True`).
- **Buscador:** `buscar_productos_inteligente` tenía `activo=True` hardcodeado en `empresa_filtros`. No existía selector de estado en `stock_index.html` y el botón de eliminar en `producto_list.html` estaba visible para cualquier rol.

---

## 3. Plan Detallado de Modificaciones

### Paso 1: Modelo `ClienteProveedor` y Migración de Base de Datos
- **Archivo:** `facturacion/models.py`
  - Añadir campo:
    ```python
    activo = models.BooleanField(default=True, db_index=True, verbose_name="Activo")
    ```
- **Migración:**
  - Ejecutar `python manage.py makemigrations facturacion` y `python manage.py migrate`.

### Paso 2: Backend de Clientes y Proveedores (`facturacion/views_htmx.py`)
- **Endpoint de alternancia de estado (`eliminar_cliente` / toggle):**
  - Validar rol de Administrador:
    ```python
    es_admin = request.user.is_superuser or request.user.is_staff or getattr(getattr(request.user, 'perfil', None), 'es_admin_sistema', False)
    if not es_admin:
        return HttpResponseForbidden("Solo un Administrador puede deshabilitar o habilitar clientes/proveedores.")
    ```
  - Alternar: `cliente.activo = not cliente.activo`.
  - Si la empresa es Armería, sincronizar `ExtensionArmeria.activo = cliente.activo`.
  - Disparar `reloadClientes` vía `HX-Trigger`.
- **Buscador `buscar_clientes`:**
  - Si `es_admin`: leer `estado_activo = request.GET.get('estado_activo', 'habilitados')`.
  - Si `not es_admin`: forzar `estado_activo = 'habilitados'`.
  - Aplicar filtro sobre el QuerySet:
    - `'habilitados'`: `.filter(activo=True)`.
    - `'deshabilitados'`: `.filter(activo=False)`.
    - `'todos'`: sin filtro de `activo`.
- **Buscadores de ventas/preventas (`lista_clientes_venta_resultados`, etc.):**
  - Asegurar que siempre filtren con `activo=True` para que no se puedan emitir comprobantes a entidades dadas de baja.

### Paso 3: Frontend de Clientes y Proveedores
- **Archivo:** `templates/facturacion/clientes_index.html`
  - Incluir el combobox de estado condicionado al Administrador:
    ```html
    {% if user.is_superuser or user.is_staff or user.perfil.es_admin_sistema %}
    <select name="estado_activo" hx-get="{% url 'cliente_search' %}" hx-trigger="change" hx-target="#cliente-rows" hx-include="[name='q'], [name='tipo']"
        class="bg-gray-50 border border-gray-200 text-gray-700 text-sm rounded-2xl focus:ring-indigo-500 focus:border-indigo-500 block p-3 px-4 font-medium shadow-sm cursor-pointer">
        <option value="habilitados" selected>Estado: Habilitados</option>
        <option value="deshabilitados">Estado: Deshabilitados</option>
        <option value="todos">Estado: Todos</option>
    </select>
    {% endif %}
    ```
  - En los inputs existentes `[name='q']` y `[name='tipo']`, incluir `[name='estado_activo']` en sus `hx-include`.
- **Archivo:** `templates/facturacion/partials/cliente_table_rows.html`
  - Si `not cliente.activo`: aplicar estilo visual atenuado a la fila (`opacity-60 bg-gray-50`) y añadir badge `DESHABILITADO`.
  - En la botonera de acciones:
    - Si el usuario es Administrador:
      - Si `cliente.activo`: botón rojo para deshabilitar con confirmación.
      - Si `not cliente.activo`: botón verde para rehabilitar con confirmación.
    - Si el usuario NO es Administrador: no mostrar ningún botón de deshabilitar/habilitar.

### Paso 4: Backend de Productos (`productos/services/busqueda_service.py` y `productos/views_htmx.py`)
- **Archivo:** `productos/services/busqueda_service.py`
  - Actualizar `construir_filtro_busqueda_producto` y `buscar_productos_inteligente` para recibir el parámetro `estado_activo='habilitados'`.
  - Configurar `empresa_filtros`:
    - Si `estado_activo == 'habilitados'`: `Q(empresa_id=empresa_id, activo=True)`
    - Si `estado_activo == 'deshabilitados'`: `Q(empresa_id=empresa_id, activo=False)`
    - Si `estado_activo == 'todos'`: `Q(empresa_id=empresa_id)`
- **Archivo:** `productos/views_htmx.py`
  - En `buscar_productos`:
    - Evaluar si `request.user` es Administrador.
    - Si es Admin: tomar `request.GET.get('estado_activo', 'habilitados')`.
    - Si no es Admin: forzar `estado_activo = 'habilitados'`.
    - Pasar `estado_activo` a `buscar_productos_inteligente`.
  - En `eliminar_producto` (toggle):
    - Validar rol de Administrador. Si no lo es, retornar `HttpResponseForbidden`.
    - Alternar `producto.activo = not producto.activo`.
    - Guardar y disparar `'productosActualizados'` vía `HX-Trigger`.

### Paso 5: Frontend de Productos
- **Archivo:** `templates/productos/stock_index.html`
  - Añadir el selector de estado solo para Administradores:
    ```html
    {% if user.is_superuser or user.is_staff or user.perfil.es_admin_sistema %}
    <select name="estado_activo" id="id_estado_activo_prod"
        hx-get="{% url 'producto_search' %}"
        hx-trigger="change"
        hx-include="[name='q'], [name='campo']"
        hx-target="#producto-rows"
        class="bg-gray-50 border border-gray-200 text-gray-700 text-sm rounded-2xl focus:ring-indigo-500 focus:border-indigo-500 block p-3 px-4 font-medium shadow-sm cursor-pointer whitespace-nowrap">
        <option value="habilitados" selected>Estado: Habilitados</option>
        <option value="deshabilitados">Estado: Deshabilitados</option>
        <option value="todos">Estado: Todos</option>
    </select>
    {% endif %}
    ```
  - Incluir `[name='estado_activo']` en el `hx-include` del buscador `[name='q']` y del selector de campo `[name='campo']`.
- **Archivo:** `templates/productos/partials/producto_list.html`
  - Si `not producto.activo`: aplicar opacidad reducida (`opacity-60 bg-gray-50`) y etiqueta distintiva `DESHABILITADO`.
  - En la botonera de acciones:
    - Si es Administrador:
      - Si `producto.activo`: botón rojo para deshabilitar con confirmación.
      - Si `not producto.activo`: botón verde para habilitar con confirmación.
    - Si no es Administrador: ocultar el botón.

---

## 4. Plan de Pruebas
1. **Pruebas de Permisos de Backend:**
   - Intentar invocar el endpoint de deshabilitar cliente y producto con un usuario estándar -> Debe recibir HTTP 403 Forbidden.
   - Invocar el endpoint con un usuario Administrador -> Debe alternar el campo `activo` exitosamente y responder con el header de recarga HTMX.
2. **Pruebas de Filtrado en Interfaz:**
   - Iniciar sesión como Administrador: verificar que se visualiza el combobox con opciones `Habilitados`, `Deshabilitados`, `Todos`.
   - Probar cambiar el filtro a `Deshabilitados`: deben listarse solo los dados de baja y mostrar el botón verde para reactivar.
   - Iniciar sesión como Vendedor / Cajero: verificar que el combobox de estado **no existe** en pantalla, solo se listan los habilitados y no hay botones de deshabilitar/habilitar en la grilla.
3. **Pruebas Unitarias de Regresión:**
   - Ejecutar la suite completa:
     `python manage.py test verticalidades.armeria facturacion.tests.test_armeria_credencial_clu`
