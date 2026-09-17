# Plan de Implementación: Mejoras Generales, Armería y Migraciones

## Resumen
Se implementarán las optimizaciones solicitadas en el documento "Armeria Propuesta". Además de la desactivación lógica de clientes en la extensión de Armería y la desactivación lógica para Productos a nivel del Core, se agregará un script global de migración para corregir los punteros de ID (secuencias) de PostgreSQL, solucionando el error de "ID ya existe" al intentar crear nuevos registros.

## User Review Required
> [!TIP]
> **Script de Secuencias**: Se creará un script general que lee todos los modelos del sistema (incluso los nuevos que agreguemos a futuro) y le pedirá a la base de datos que ajuste automáticamente sus punteros (secuencias autoincrementales) al máximo ID que tengan en ese momento. Esto es una práctica estándar después de hacer migraciones manuales o inserciones forzadas.

## Proposed Changes

---

### Módulo Migraciones

#### [NEW] migracion/scripts/reset_sequences.py
- Crear un script ejecutable que importe el entorno de Django.
- Utilizar `connection.ops.sequence_reset_sql` junto con `apps.get_models()` para generar dinámicamente las sentencias SQL que reparan los punteros de todas las tablas registradas en el ERP.
- Ejecutar estas sentencias en la base de datos para sincronizar los IDs.

---

### Módulo Productos (Core)

#### [MODIFY] productos/models.py
- Añadir a `Producto` el campo: `activo = models.BooleanField(default=True, verbose_name="Activo")`.

#### [MODIFY] productos/views_htmx.py
- **Borrado Inteligente (`eliminar_producto`)**: Cambiar la instrucción `producto.delete()` por `producto.activo = False; producto.save()`.

#### [MODIFY] productos/services/busqueda_service.py (y vistas de listado)
- Agregar `.filter(activo=True)` a la lógica base de construcción de QuerySets (ej. `construir_filtro_busqueda_producto` o `buscar_productos_inteligente`) para que los productos "eliminados" no aparezcan ni en el ABM ni en los modales de búsqueda rápida.

---

### Módulo Clientes/Proveedores (Extensión Armería)

#### [MODIFY] verticalidades/armeria/models.py
- Añadir a `ExtensionArmeria` el campo: `activo = models.BooleanField(null=True, default=True, verbose_name="Activo en Armería")`.

#### [MODIFY] facturacion/views_htmx.py
- **Borrado Inteligente (`eliminar_cliente`)**: Detectar si la empresa activa tiene `tipo_actividad == 'ARMERIA'`. Si es así, no ejecutar `clipro.delete()`, sino obtener/crear su `ExtensionArmeria` y establecer `activo = False`. (Las demás empresas mantendrán el borrado físico).
- **Buscador y Listados (`buscar_clientes`)**: Si la empresa es Armería, agregar `.exclude(armeria__activo=False)` al QuerySet de `ClienteProveedor` para que los inactivos desaparezcan de todas las grillas y selects.

#### [MODIFY] facturacion/forms.py
- **Validación CUIT duplicado**: Al validar duplicidad de CUIT en `ClienteProveedorForm.clean()`, si es empresa Armería, se ignorarán clientes con `armeria__activo=False`. Mostrará error como burbuja si se detecta un duplicado activo.
- **Validación Email y Teléfono**: 
  - Asegurar que `correo` contenga "@" y ".". 
  - Ajustar el widget de `telefono` (`type="text" pattern="[0-9]*"`) para forzar números sin flechitas del navegador.
- **Autocompletado Localidad**: Agregar `list="datalist-localidades"` al input.
- **Ocultar Contacto**: Si la verticalidad es "Armería", ocultar visualmente el campo `contacto` sin alterar la base de datos.

#### [MODIFY] templates/facturacion/modals/cliente_modal.html
- Insertar `<datalist id="datalist-localidades">` con los valores: San Miguel de Tucumán, Yerba Buena, Banda del Río Salí, Tafí Viejo, Concepción.

---

### Ventas, Preventas y Trazabilidad (Armería)

#### [MODIFY] verticalidades/armeria/views.py
- **Control de Sucursal**: Filtrar transacciones y selectores de subproductos y Preventas según la `sucursal_activa` para no permitir cruce operativo entre sucursales.
- **Validación CLU en Municiones**: En preventa, bloquear la adición de municiones si el `ClienteProveedor` no posee CLU vigente en su `ExtensionArmeria`.
- **Obligatoriedad CUIM**: En compras, el CUIM (6 dígitos) será obligatorio solo si el proveedor no está catalogado también como Cliente.

#### [MODIFY] verticalidades/armeria/templates/armeria/ventas_trazabilidad_carga.html (y preventas)
- Incluir un botón HTMX/Alpine al costado del input de cliente para abrir directamente su modal de edición, permitiendo al vendedor cargar el CLU en el acto.
- **Bug Credencial**: Desvincular el `alert()` del evento `input` constante en JS para el control de la credencial (usando `change` o renderizado visual) para eliminar el bucle infinito al tipear menos de 6 dígitos.

#### [MODIFY] verticalidades/armeria/templates/armeria/partials/trazabilidad_modal_timeline.html
- Tarjeta del historial: al clickear, desplegará los detalles del movimiento.
- Insertar un botón tipo `<a>` con `target="_blank"` y un icono PDF apuntando a `{% url 'facturacion:impresion_venta' id_de_la_venta %}` para reimpresión directa.

## Verification Plan

### Automated Tests
- Ejecutar pruebas en `facturacion/tests` y `verticalidades/armeria/tests.py` para asegurar que las reglas core sigan funcionando.

### Manual Verification
1. Ejecutar el script `reset_sequences.py` y luego intentar crear una empresa o cliente para verificar que no falle por ID duplicado.
2. Eliminar un producto del ABM: verificar que desaparece de las listas pero las facturas pasadas siguen mostrándolo.
3. En empresa Armería: eliminar un cliente y verificar que desaparece, pero sigue existiendo en BDD.
4. Crear un cliente con CUIT duplicado de uno "Activo" (falla) y uno "Inactivo" (pasa).
5. En Preventa Armería: intentar facturar municiones a cliente sin CLU (falla); abrir modal y actualizarlo; facturar (pasa).
6. Timeline de trazabilidad: clickear tarjeta para ver detalles y abrir PDF de factura en nueva pestaña.
