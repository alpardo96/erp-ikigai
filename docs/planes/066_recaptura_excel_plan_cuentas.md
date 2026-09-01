# Plan de Implementación: Exportación y Recaptura Masiva en Excel del Plan de Cuentas

Se añadirá la funcionalidad para exportar el Plan de Cuentas completo a un archivo Excel (`.xlsx`) y la recaptura/importación masiva desde Excel, siguiendo el estándar de diseño y lógica implementado en el módulo de **Mantenimiento de Productos**.

---

## 1. Objetivos

1. **Exportación a Excel Completo:** Botón que permite descargar el listado total de cuentas contables de la empresa activa en formato `.xlsx` con encabezados formateados y autowidth.
2. **Recaptura / Importación Masiva:** Botón y modal que permite subir un archivo Excel para actualizar o crear cuentas contables de manera atómica (`transaction.atomic()`).
3. **Instrucciones y Reglas de Negocio en Modal:**
   - **Para cuenta nueva:** Dejar la celda `ID` vacía/nula.
   - **Manejo inteligente de ID no encontrado:** Si el usuario ingresó un número en la columna `ID`, el sistema buscará si esa cuenta existe en la empresa activa. Si no la encuentra (porque se trata de un número nuevo), el sistema **NO** forzará el `ID` ingresado por el usuario, sino que la creará como cuenta nueva dejando que PostgreSQL le asigne automáticamente el `ID` autoincremental que corresponda.
   - **Para cuentas existentes:** Si la cuenta existe en la empresa activa, se actualizará cualquier otro campo (`Jerarquía`, `Nombre Cuenta`, `Imputable`, `Tipo`, `Código Legacy`, `RG 830`, `Tipo Disponibilidad`, etc.), manteniendo su `ID` original.
   - **Formato Estándar:** Unificación automática de nombres de cuenta en **MAYÚSCULAS**.

---

## 2. Modificaciones Propuestas

### `contable/services/excel_service.py` [NUEVO]
- Crear `COLUMNAS_CUENTA_MAP` definiendo los nombres y encabezados del Excel.
- `generar_excel_cuentas(queryset)`: Genera el libro `openpyxl` con estilos slate/emerald, bordes finos, fuentes Arial y autoajuste de ancho.
- `procesar_captura_excel_cuentas(empresa, usuario, archivo_excel)`:
  - Lee la primera fila como encabezados mapeados a campos.
  - Para cada fila de datos:
    - Si el `ID` está presente, busca la `Cuenta` existente por `(id=prod_id, empresa=empresa)`.
    - Si existe en la empresa activa -> Actualiza sus campos (salvo el `ID`).
    - Si no existe en la empresa activa o el `ID` estaba vacío -> Crea una nueva `Cuenta` asociada a `empresa=empresa`, dejando que PostgreSQL asigne automáticamente la PK.
    - Resuelve automáticamente la asignación de `sumariza` buscando la jerarquía padre correspondiente.

### `contable/views_htmx.py` [MODIFICAR]
- `exportar_cuentas_excel_completo`: Genera y descarga el archivo `.xlsx`.
- `modal_capturar_cuentas_excel`: Renders modal HTMX de recaptura.
- `capturar_cuentas_excel`: Procesa el formulario `POST` con el archivo `.xlsx`, ejecuta la recaptura en BD y dispara la actualización HTMX de la tabla (`reloadCuentas`).

### `templates/contable/modals/capturar_excel_modal.html` [NUEVO]
- Modal interactivo con Tailwind CSS, drag & drop de archivos Excel.
- Cuadro destacado de instrucciones indicando expresamente que **para cuentas nuevas NO se debe cargar el ID**, y si se pone un ID inexistente, el sistema la creará asignando el ID automático.

### `templates/configuracion/partials/cuentascontables.html` [MODIFICAR]
- Integración de los botones **"Capturar Excel"** y **"Excel Completo"** en la barra superior junto al botón de **"Nueva Cuenta"**.

### `config/urls.py` y `contable/urls.py` [MODIFICAR]
- Registro de las rutas URL para la exportación y el modal de recaptura de cuentas.

### `contable/tests/test_excel_cuentas.py` [NUEVO]
- Pruebas unitarias para validar la exportación completa en Excel y la recaptura masiva (creación con ID nulo/inexistente y actualización por ID existente).

---

## 3. Plan de Verificación

### Pruebas Automatizadas
```bash
python manage.py test contable.tests.test_excel_cuentas
```

### Pruebas Manuales
1. Ingresar a Configuración -> Plan de Cuentas.
2. Hacer clic en **"Excel Completo"** y verificar la descarga del archivo `.xlsx`.
3. Hacer clic en **"Capturar Excel"**, verificar que el modal muestra el mensaje aclaratorio sobre la carga de ID.
4. Modificar nombres o agregar una fila nueva sin ID (o con un ID no existente) en el Excel y subir el archivo.
5. Verificar en la grilla que las cuentas existentes se actualizaron y las nuevas cuentas se crearon con un nuevo ID asignado por el sistema.
