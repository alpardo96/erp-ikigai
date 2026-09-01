# Plan 063: Exportación e Importación / Captura Masiva de Productos en Excel (Con Mayúsculas y Creación Automática de Entidades)

## Visión General
Este documento especifica el diseño técnico para el Mantenimiento de Productos en el ERP Ikigai 2, cubriendo:
1. **Exportación a Excel Personalizada con Selección de Columnas**: Permite al usuario seleccionar qué campos de la tabla de productos exportar (con la lista completa de todos los campos disponibles).
2. **Exportación a Excel de la Tabla Completa (Plantilla)**: Botón para descargar el maestro completo de productos de la empresa con todos sus campos operables.
3. **Captura / Importación Masiva desde Excel**:
   - Convertir y guardar **SIEMPRE EN MAYÚSCULAS** el detalle del producto, código proveedor, código fábrica, marca, rubro y familia.
   - Si el `ID` ya existe en la base de datos de la empresa, **actualiza todos los campos del producto excepto el ID**.
   - Si el `ID` no está especificado o está vacío, **crea el nuevo producto** asignándole el ID correspondiente de forma automática.
   - Si se especifica una **Marca**, **Rubro** o **Familia** inexistente en la base de datos de la empresa, el sistema los **creará automáticamente en MAYÚSCULAS**, les asignará su ID único correspondiente en su tabla respectiva y vinculará dicho ID al nuevo producto.
   - Presenta un aviso explícito en el modal alertando que **para productos nuevos no deben colocar el ID** porque el sistema lo asignará automáticamente.

---

## 1. Reglas de Negocio y Conversión a Mayúsculas

### Unificación de Mayúsculas:
- Todo texto ingresado (Detalle del producto, Cód. Prov, Cód. Fab, Marca, Rubro, Familia) es convertido a **MAYÚSCULAS** (`.upper().strip()`) antes de guardarse en la BD.

### Creación Automática de Marcas, Rubros y Familias:
- Si el Excel contiene los nombres/detalles de Marca, Rubro o Familia:
  - Busca si existe la entidad para la `Empresa` en la BD (insensible a mayúsculas).
  - Si no existe: la crea automáticamente (`Marca.objects.create(empresa=empresa, detalle=nombre.upper())`), toma el nuevo ID autonumérico asignado por PostgreSQL y lo asocia al `Producto`.

---

## 2. Arquitectura de Componentes

### 1. `productos/services/excel_service.py`
Servicio para procesamiento de Excel con `openpyxl`:
- `generar_excel_productos(queryset, columnas_seleccionadas)`
- `procesar_captura_excel_productos(empresa, usuario, archivo_excel)`

### 2. `productos/views_htmx.py`
Vistas HTMX y descargas:
- `exportar_productos_excel_completo`
- `modal_exportar_seleccion`
- `exportar_productos_excel_seleccion`
- `modal_capturar_excel`
- `capturar_productos_excel`

### 3. Modales HTML y Vistas
- `templates/productos/modals/exportar_seleccion_modal.html`
- `templates/productos/modals/capturar_excel_modal.html`
- Botones integrados en `templates/productos/stock_index.html`

---

## 3. Plan de Pruebas
1. Tests unitarios en `productos/tests/test_excel_productos.py`.
2. Prueba de exportación de selección y completa.
3. Prueba de captura actualizando producto por ID existente y conversión a MAYÚSCULAS.
4. Prueba de captura creando producto nuevo con ID omitido y alta automática de Marca/Rubro/Familia en MAYÚSCULAS.
