# Plan 095 — Módulo de Inventario de Mercaderías (General y Parcial)

## 1. OBJETIVO Y VISIÓN
Implementar el módulo integral de **Toma de Inventarios Físicos de Mercaderías** en el ERP Ikigai, disponible de forma **transversal para todas las actividades y verticalidades** (Armería, Distribución, Agrícola, etc.).

El módulo permite:
1. Realizar **Inventarios Generales** (todo el catálogo de la sucursal) o **Inventarios Parciales** (filtrados por Código, Detalle, Proveedor, Marca, Rubro, Familia o Subfamilia, o un ajuste puntual de un único artículo).
2. Generar e imprimir la **Planilla de Conteo Físico en PDF**, ordenada jerárquicamente por:
   $$\text{Rubro} \rightarrow \text{Familia} \rightarrow \text{Subfamilia} \rightarrow \text{Detalle}$$
   con casilleros en blanco para anotación manual.
3. Cargar el recuento físico en una grilla interactiva con cálculo de diferencias en tiempo real:
   $$\text{Diferencia} = \text{Cantidad Contada} - \text{Stock Teórico}$$
4. Gestionar el circuito de **Autorización y Auditoría (Opción A)**:
   - El operador cuenta, edita y borra libremente en `BORRADOR`.
   - Al cerrar, pasa a `PENDIENTE_AUTORIZACION` (bloqueando cambios al operador).
   - El autorizador/supervisor puede **ajustar cantidades contadas** directamente (dejando auditoría), **aprobar/aplicar** al stock o **rechazar/devolver a borrador**.
5. Impactar en el cálculo del stock disponible a través de `productos.services.stock_service.recalcular_stock()` solo para inventarios en estado `APLICADO`.

---

## 2. MODELOS Y BASE DE DATOS

### 2.1 Modelo `TomaInventario` (Cabecera)
Actualización de choices de estado y campos de auditoría en `productos/models.py`:

```python
ESTADOS_INVENTARIO = [
    ('BORRADOR', 'Borrador / En Conteo'),
    ('PENDIENTE', 'Pendiente de Autorización'),
    ('APLICADO', 'Aplicado al Stock'),
    ('RECHAZADO', 'Rechazado'),
    ('ANULADO', 'Anulado'),
]
```

Campos a complementar en `TomaInventario`:
- `empresa`: `ForeignKey(Empresa)`
- `sucursal`: `ForeignKey(Sucursal)`
- `numero`: `IntegerField` (correlativo por empresa/sucursal)
- `fecha_toma`: `DateTimeField`
- `tipo_alcance`: `CharField` (`'GENERAL'`, `'PARCIAL'`)
- `filtros_aplicados`: `TextField` (guarda resumen de filtros con los que se generó la planilla)
- `estado`: `CharField(choices=ESTADOS_INVENTARIO, default='BORRADOR')`
- `observaciones`: `TextField`
- `usuario_conteo`: `ForeignKey(User, related_name="inventarios_contados")`
- `usuario_autorizo`: `ForeignKey(User, related_name="inventarios_autorizados", null=True, blank=True)`
- `fecha_autorizo`: `DateTimeField(null=True, blank=True)`
- `motivo_rechazo`: `TextField(null=True, blank=True)`

### 2.2 Modelo `TomaInventarioItem` (Detalle de Ítems)
Campos de detalle en `productos/models.py`:
- `inventario`: `ForeignKey(TomaInventario, related_name='items')`
- `producto`: `ForeignKey(Producto, related_name='conteos_inventario')`
- `stock_teorico`: `DecimalField(max_digits=15, decimal_places=2, default=0)` (foto del stock al momento de iniciar)
- `cantidad_contada`: `DecimalField(max_digits=15, decimal_places=2, default=0)`
- `diferencia`: `DecimalField(max_digits=15, decimal_places=2, default=0)` (calculada: contada - teorico)
- `modificado_por_autorizador`: `BooleanField(default=False)`
- `cantidad_original_operador`: `DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)`
- `observaciones`: `CharField(max_length=255, null=True, blank=True)`

---

## 3. INTEGRACIÓN EN EL CÁLCULO DE STOCK (`stock_service.py`)

Se añade el término en `_terminos()` de `productos/services/stock_service.py`:

```python
{
    'nombre': 'ajustes_inventario',
    'modelo': TomaInventarioItem,
    'signo': 1,
    'cantidad': 'diferencia',
    'producto': 'producto_id',
    'sucursal': 'inventario__sucursal_id',
    'signo_cbte': None,
    'excluir': ~Q(inventario__estado='APLICADO'),  # Solo impacta si está APLICADO
}
```

De esta forma, cuando un inventario se autoriza y pasa a `APLICADO`:
$$\text{Stock} = \text{Stock Inicial} + \text{Compras} + \text{Recepciones} - \text{Ventas} - \text{Remitos Internos} + \sum \text{Diferencias Inventarios Aplicados}$$

---

## 4. PANTALLAS Y COMPONENTES UI

### 4.1 Menú y Accesos
- Ubicación: Menú Lateral $\rightarrow$ **Stock** $\rightarrow$ **Toma de Inventarios** (`/stock/inventarios/`).
- Botón de acción rápida en el Dashboard de Stock: *"Nuevo Inventario Físico"*.

### 4.2 Listado de Inventarios (`inventario_listado.html`)
- Tabla con historial de tomas: Nro, Fecha, Sucursal, Alcance (General/Parcial), Ítems Contados, Estado (Badge de color), Usuario, Acciones.
- Acciones según estado:
  - `BORRADOR`: Continuar Conteo / Imprimir Planilla / Enviar a Autorización / Anular.
  - `PENDIENTE`: Ver Detalle / Revisar y Autorizar (para Administradores/Supervisores).
  - `APLICADO`: Ver Detalle / Imprimir Reporte Final de Ajustes.
  - `RECHAZADO` / `ANULADO`: Ver Detalle.

### 4.3 Pantalla de Carga y Conteo (`inventario_carga.html`)
- **Cabecera de Filtros y Generación:**
  - Selectores desplegables encadenados: Marca, Rubro, Familia, Subfamilia, Proveedor.
  - Buscador rápido por Código / Detalle.
  - Botón **"Generar / Cargar Grilla"** e **"Imprimir Planilla de Conteo (PDF)"**.
- **Grilla Interactiva de Conteo:**
  - Columnas: Cód. Prov / ID, Detalle del Producto, Rubro / Familia, Stock Teórico, **Cantidad Contada (Input)**, Diferencia (+/- con color), Acciones (Borrar ítem).
  - Alta rápida unitaria: Buscador tipo typeahead para agregar artículos individuales al vuelo (caso de ajuste de 1 solo producto).
  - Guardado dinámico con HTMX (actualización automática de la fila y de los totales).
- **Botones de Cierre:**
  - *Guardar Borrador* (para pausar y continuar luego).
  - *Enviar a Autorización* (pasa a `PENDIENTE` y bloquea la edición al operador).

### 4.4 Pantalla / Modal de Autorización (`inventario_autorizar_modal.html`)
- Exclusiva para usuarios con rol o permiso de Autorizador/Administrador.
- Muestra el resumen del inventario: total de ítems, ítems con sobrante, ítems con faltante, total neto de unidades a ajustar.
- Grilla con las diferencias detectadas.
- **Capacidad de edición (Opción A):** El autorizador puede modificar el valor en el casillero de cantidad si detecta un error de carga del operador (el sistema guarda el valor original y marca auditoría).
- Botones:
  - **Aprobar y Aplicar Stock** $\rightarrow$ Pasa a `APLICADO`, ejecuta `recalcular_stock()` para cada producto involucrado y emite `MovimientoStock` de auditoría tipo `ENTRADA` o `SALIDA`.
  - **Rechazar / Devolver a Conteo** $\rightarrow$ Solicita motivo y regresa el inventario a `BORRADOR`.
  - **Anular**.

### 4.5 Planilla de Conteo Físico en PDF (`inventario_planilla_pdf.html`)
- Formato A4 limpio y optimizado para impresión.
- Encabezado con Empresa, Sucursal, Fecha, Nro. de Inventario y Filtros aplicados.
- Ordenamiento jerárquico estricto: `Rubro` $\rightarrow$ `Familia` $\rightarrow$ `Subfamilia` $\rightarrow$ `Detalle`.
- Columnas:
  1. Cód. Prov / ID
  2. Descripción del Producto
  3. Unidad / Calibre
  4. Marca
  5. Casillero amplio en blanco: **[ Conteo Físico: _______ ]**
  6. Observaciones: **[ ___________________ ]**

---

## 5. PASOS DE IMPLEMENTACIÓN

1. **Modelos y Migración:**
   - Actualizar choices y campos de auditoría en `TomaInventario` y `TomaInventarioItem`.
   - Ejecutar `makemigrations` y `migrate`.
2. **Servicio de Stock:**
   - Registrar el término de ajustes de inventario en `productos/services/stock_service.py`.
   - Implementar función de servicio `aplicar_inventario_al_stock(inventario, usuario)`.
3. **Formularios y Vistas Backend:**
   - Crear formularios en `productos/forms.py` (`TomaInventarioForm`, `TomaInventarioItemForm`, `InventarioFiltroForm`).
   - Crear vistas en `productos/views_inventario.py` (Listado, Carga, HTMX para agregar/editar/quitar ítems, Modal de Autorización, Generación de PDF).
4. **Templates y UI:**
   - Diseñar templates en `templates/productos/inventario/`:
     - `inventario_listado.html`
     - `inventario_carga.html`
     - `partials/grilla_items.html`
     - `modals/autorizar_modal.html`
     - `pdf/planilla_conteo_pdf.html`
5. **Rutas y Menú:**
   - Registrar URLs en `productos/urls.py` o `config/urls.py`.
   - Agregar enlaces en sidebar y dashboard de stock.
6. **Validaciones y Pruebas:**
   - Pruebas unitarias de recálculo de stock con inventarios aplicados, rechazados y borradores.
   - Verificación de consistencia en todas las actividades.
