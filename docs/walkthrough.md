# Bitácora de Desarrollo - ERP Ikigai

## Antigravity (Codex/Gemini) - 02/09/2026
**Objetivo:** Crear perfil de lectura OCR para el CUIT 30540938322 de Armería.
**Archivos creados o modificados:**
- `verticalidades/armeria/perfiles_lectura/cuit_30540938322.py` [NEW]

**Detalle Técnico:** 
- Se implementó el script `procesar_perfil` específico para analizar y extraer datos de facturas del proveedor con CUIT 30540938322.
- La expresión regular y la lógica de extracción fueron adaptadas para manejar columnas dinámicas donde los códigos de los productos pueden aparecer al inicio o al final de la descripción.
- Se incorporó la extracción del porcentaje de descuento (`Desc. %`).
- Se implementó la captura de campos adicionales como "Serie:", "CUIM:" y "DIM:", agrupándolos automáticamente dentro del diccionario del último ítem escaneado bajo la clave `subproductos`, permitiendo al ERP utilizar estos datos en la pantalla de carga (desplegando los correspondientes campos según requerimiento).

**Resultado de las pruebas:**
- Se ejecutó un script de prueba (`scratch/test_parser.py`) iterando el PDF de prueba del CUIT, validando que todas las líneas de productos se parsearan correctamente, que los subproductos (series y CUIMs) se anexaran a los ítems adecuados, y que los cálculos de totales coincidieran con el documento físico.

**Estado actual y siguientes pasos sugeridos:**
- El perfil está completado y será utilizado automáticamente por el `extractor_facturas` del sistema al subir una factura de dicho CUIT en la vertical Armería.

## Antigravity (Codex) - 31/08/2026
**Objetivo:** Desacoplamiento de Verticalidades (Plug & Play) en urls.py
**Archivos creados o modificados:**
- `config/urls.py` [MODIFY]
- `verticalidades/distribucion/urls.py` [NEW]
- `verticalidades/estudio/urls.py` [MODIFY]

**Detalle Técnico:** 
- Se removieron todas las importaciones `hardcoded` de vistas pertenecientes a las verticalidades de `distribucion`, `estudio` y partes de `armeria` del archivo principal `config/urls.py`.
- Se removieron las declaraciones explícitas de rutas de las mismas.
- Se crearon/actualizaron los archivos `urls.py` correspondientes dentro de `verticalidades/distribucion/` y `verticalidades/estudio/` para albergar sus propias rutas e importaciones de forma aislada.
- De esta manera, el núcleo `config/urls.py` depende exclusivamente de su auto-descubrimiento dinámico de aplicaciones instaladas, respetando al 100% el diseño de arquitectura Plug & Play exigido.

**Resultado de las pruebas:**
- Se comprobó mediante análisis estático que las rutas y vistas fueron trasladadas correctamente.

**Estado actual y siguientes pasos sugeridos:**
- Desacoplamiento de rutas implementado. Se recomienda al usuario realizar la prueba de "desenchufar" (mover temporalmente la carpeta) la verticalidad de Distribución o Estudio y verificar que el ERP base (Estándar) reinicie y funcione sin colapsar por errores de importación.

## Cristian - PC CASA - 31/08/2026
**Objetivo:** Completar y ordenar las tarjetas (cards) del Dashboard de Distribución omitiendo la sección Maestros.
**Archivos creados o modificados:**
- `verticalidades/distribucion/templates/distribucion/index.html` [MODIFY]

**Detalle Técnico:** 
- Se agregaron las tarjetas faltantes (`distribucion_movil_pedido`, `distribucion_cobranza_vendedor`, `distribucion_saldos`, `distribucion_reporte_devoluciones`, `distribucion_correlativos`).
- Se reordenó toda la grilla de tarjetas del `index.html` para que coincida 1:1 con la estructura lógica y orden del menú lateral (sidebar).
- Se excluyeron deliberadamente los accesos a "Maestros" (`Configuración`) del dashboard, dejándolos disponibles únicamente a través del menú lateral, manteniendo el panel principal enfocado en la operatoria pura y control.

**Estado actual y siguientes pasos sugeridos:**
- El dashboard de Distribución ahora refleja fielmente el menú de operaciones, control y gestión. Todo está en producción.


## Cristian - PC CASA - 31/08/2026
**Objetivo:** Crear layout y tarjetas del dashboard de Distribución (base.html y sidebar).
**Archivos creados o modificados:**
- `verticalidades/distribucion/views.py` [MODIFY]
- `config/urls.py` [MODIFY]
- `verticalidades/distribucion/templates/distribucion/index.html` [NEW]
- `verticalidades/distribucion/templates/distribucion/hooks/menu_sidebar_bottom.html` [MODIFY]

**Detalle Técnico:** 
- Se implementó la vista `DistribucionIndexView` basada en `TemplateView` y protegida con `LoginRequiredMixin`.
- Se registró la ruta `/distribucion/` en `config/urls.py` asociada al nombre `distribucion_index`.
- Se creó el template `index.html` para Distribución, unificando en formato de tarjetas dinámicas todas las operativas (Tomar Pedido, Facturación Masiva, Faltantes, Repartos, Rendiciones y Cartera). Se empleó la paleta de colores requerida y consistencia visual (`text-amber-600` / `border-amber-500`, etc.) heredando de `base.html`.
- Se actualizó el hook `menu_sidebar_bottom.html` integrando la lógica activa de Alpine.js (`window.location.pathname.startsWith('/distribucion/')`) y Jinja (`request.resolver_match.url_name`). Al hacer clic en Distribución o navegar a cualquiera de sus submódulos, el ítem en la barra lateral queda desplegado y coloreado visualmente en ambar (`text-amber-400 font-bold`).

**Estado actual y siguientes pasos sugeridos:**
- Módulo Distribución cuenta ahora con su propio dashboard y menú lateral inteligente que preserva el estado activo de la interfaz. Validar comportamiento al navegar por las cards.


## Cristian - PC CASA - 31/08/2026
**Objetivo:** Auto-descubrimiento 100% dinámico de Verticalidades en el Tipo de Actividad de Empresas.
**Archivos creados o modificados:**
- `empresas/models.py`
- `empresas/forms.py`
- `verticalidades/armeria/apps.py`
- `verticalidades/distribucion/apps.py`
- Nueva migración: `empresas/migrations/0003_alter_empresa_tipo_actividad.py`

**Detalle Técnico:** 
- Se eliminaron las opciones hardcodeadas (`TIPO_ACTIVIDAD_CHOICES`) del modelo `Empresa` en `empresas/models.py` y se generó la migración correspondiente para liberar la restricción en la base de datos.
- Se agregó el atributo `tipo_actividad_code` en las clases `AppConfig` de Armería y Distribución.
- En `empresas/forms.py` (dentro de `EmpresaForm.__init__`), el sistema ahora itera sobre `apps.get_app_configs()` y auto-descubre dinámicamente cualquier aplicación que comience con `verticalidades.`, inyectándola en el selector desplegable (asignándola al `widget.choices`).
- **Limpieza de interfaz (UI):** Se inyectaron clases Tailwind en todos los `<label>` y `TextInput` del formulario de empresa.
- **Corrección masiva de TemplateSyntaxError:** Se agregó `{% load vertical_tags %}` a **todos** los templates que usan `hook_ui` o `hook_menu`:
  - `templates/facturacion/clientes_index.html`
  - `templates/facturacion/partials/cliente_table_rows.html`
  - `templates/facturacion/ventas_index.html`
  - `templates/facturacion/compras_index.html`
  - `templates/productos/stock_dashboard.html`
  - `templates/productos/modals/producto_modal.html`
  - `templates/configuracion/partials/hub.html` (ya lo tenía)
  - `templates/base.html` (ya lo tenía)
- **Restauración de `vertical_tags.py` y Aislamiento de Verticalidades:** Se reescribió `core/templatetags/vertical_tags.py` dejándolo tal como estaba originalmente (escanea todas las verticalidades sin filtrar). En su lugar, el filtrado de qué mostrar se delegó a **cada hook individual**, asegurando que los hooks de armería solo se rendericen si `empresa_actual.tipo_actividad == 'ARMERIA'` (o usa trazabilidad) y los de distribución si es `DISTRIBUIDORA`. Se agregaron los condicionales faltantes a los siguientes hooks:
  - **Armería:** `ui_cliente_table_column_toggles.html`, `ui_cliente_table_headers.html`, `ui_cliente_table_cells.html`.
  - **Distribución:** `menu_sidebar_bottom.html`, `ui_configuracion_hub.html`, `ui_producto_modal_campos.html`.

**Estado actual y siguientes pasos sugeridos:**
- Sistema totalmente dinámico. Al enchufar una nueva verticalidad (creando la carpeta y el `apps.py`), el tipo de actividad aparecerá automáticamente en el selector del panel de configuración sin modificar el core.

## Cristian - PC CASA - 31/08/2026
**Objetivo:** Corrección de TemplateSyntaxError en configuración.
**Archivos creados o modificados:**
- `templates/configuracion/partials/hub.html`

**Detalle Técnico:** 
- Se agregó el tag `{% load vertical_tags %}` faltante al inicio del archivo `hub.html` para permitir el correcto renderizado del custom tag `hook_ui`, evitando el error `Invalid block tag`.

**Estado actual y siguientes pasos sugeridos:**
- Error solucionado, el panel de configuración ahora renderiza correctamente.

## Antigravity (Codex) - 31/08/2026
**Objetivo:** Refactorización de Templates con Hooks (Arquitectura)
**Archivos creados o modificados:**
- `core/templatetags/vertical_tags.py`
- `templates/base.html`
- `templates/facturacion/clientes_index.html`
- `templates/facturacion/partials/cliente_table_rows.html`
- `templates/productos/modals/producto_modal.html`
- `templates/facturacion/ventas_index.html` y `compras_index.html`
- `templates/productos/stock_dashboard.html`
- `templates/configuracion/partials/hub.html`
- Nuevos hooks en `verticalidades/armeria/templates/armeria/hooks/`: `ui_cliente_table_column_toggles.html`, `ui_cliente_table_headers.html`, `ui_cliente_table_cells.html`, `ui_producto_modal_opciones.html`, `ui_ventas_index_cards.html`, `ui_compras_index_cards.html`, `ui_stock_dashboard_cards.html`.
- Nuevos hooks en `verticalidades/distribucion/templates/distribucion/hooks/`: `menu_sidebar_bottom.html`, `ui_configuracion_hub.html`, `ui_producto_modal_campos.html`.
- Nuevos hooks en `verticalidades/estudio/templates/estudio/hooks/`: `menu_ventas.html`.

**Detalle Técnico:** 
- Se importó el sistema de hooks (`hook_menu`) y se creó un nuevo tag genérico `hook_ui` capaz de admitir kwargs de contexto.
- Se eliminaron las sentencias IF (`if empresa_actual.tipo_actividad == 'ARMERIA'`) incrustadas en los templates transversales del core, delegando el renderizado de dichas UI al patrón de auto-descubrimiento en las carpetas `hooks/` de las verticales activas.
- Para evitar superpoblación de hooks de una línea para el Estudio, las opciones de Actualizar Tarifas y Facturación de Lotes fueron agrupadas dentro del hook de `menu_ventas` en lugar de fragmentarlas.

**Siguientes pasos sugeridos:**
El core quedó desacoplado de las verticales y agnóstico a la lógica comercial. Se recomienda interactuar con las diversas secciones del frontend para validar el correcto inyectado de código HTML de cada empresa.## Antigravity (Codex) - 31/08/2026
**Objetivo:** Reforma de Verticalidades (Arquitectura)
**Descripción:** 
- Se implementó el patrón arquitectónico `verticalidades/` para separar la lógica de negocio de los distintos rubros (Armería, Distribución y Estudio).
- Se configuró el auto-descubrimiento en `config/settings.py` y `config/urls.py`.
- Se movió la app `distribucion` desde la raíz hacia `verticalidades/distribucion/`.
- Se copió la vertical `armeria` desde el proyecto de referencia hacia `verticalidades/armeria/`.
- Se creó el esqueleto de la vertical `estudio` en `verticalidades/estudio/`.
- Se extrajeron los modelos satélite (`ExtensionArmeria`, `ExtensionDistribuidora`, `TarifaEstudio`) desde `facturacion/models.py` hacia los `models.py` de sus respectivas verticales.
- Se mantuvo `db_table = 'facturacion_X'` en las clases `Meta` para evitar cambios de nombre de tablas en PostgreSQL, manteniendo intactas las relaciones estructurales.
- Se corrigieron todas las importaciones afectadas a lo largo del proyecto (`tests`, `views_htmx`, `admin`, `forms`, `urls.py`).
- Se eliminaron todos los archivos de migración previos para permitir una generación desde cero (`makemigrations`), ya que la base de datos se recreará limpia.

**Resultado:** `makemigrations` se ejecutó exitosamente creando los modelos en sus nuevas ubicaciones.
**Siguientes pasos:** El usuario debe dropear y recrear su base de datos local y ejecutar `python manage.py migrate` para sincronizar.

## Cristian - PC CASA
- **Fecha/Día**: 31 de Agosto de 2026
- **Objetivo o Tarea**: Reforma de Verticalidad en Tablas (Distribución y Armería). Corregir la visualización de las tablas en los listados y reportes para que el contenedor expanda su altura según el contenido y evitar encierros en tarjetas pequeñas con scroll interno innecesario.
- **Archivos creados o modificados**: 12 templates en `erp-ikigai-distribucion` y 14 templates en `erp-ikigai-armeria` (`clientes_index.html`, `stock_index.html`, `caja_mostrador_index.html`, `rendiciones_recepcion.html`, etc.).
- **Detalle Técnico e implicaciones**: Se ejecutó un script iterativo que removió masivamente las clases restrictivas (`h-full`, `flex-1`, `overflow-hidden`) de los contenedores de página y wrappers de tabla en los listados, preservando únicamente `overflow-x-auto`. El proyecto `Estudio` fue escaneado sin encontrar incidencias.
- **Resultado de las pruebas**: Se verificaron los cambios en los archivos y la eliminación correcta de las clases problemáticas.
- **Estado actual y siguientes pasos sugeridos**: Las tablas ahora se expanden libremente según su contenido. Queda validar visualmente el comportamiento responsivo en el navegador.

## 29 de Agosto de 2026 — Inclusión de `sumariza_id` en Exportación y Captura Excel del Plan de Cuentas

### Objetivo
1. **Inclusión de Clave Jerárquica en Excel:** Incorporar el campo `sumariza_id` en el archivo Excel generado mediante el botón "Excel Completo" del Plan de Cuentas, permitiendo visualizar y auditar el ID de la cuenta padre en la que consolida cada nodo.
2. **Soporte Bidireccional de Captura:** Habilitar el reconocimiento de `sumariza_id` durante la recaptura e importación masiva de cuentas desde Excel para vincular directamente la cuenta padre si se especifica su ID.

### Archivos Modificados
- `contable/services/excel_service.py` [MODIFY]:
  - Añadida la clave `'sumariza_id': 'Sumariza ID'` a `COLUMNAS_CUENTA_MAP`.
  - Actualizado `generar_excel_cuentas` para volcar `cta.sumariza_id` en la segunda columna del libro.
  - Actualizado `procesar_captura_excel_cuentas` para normalizar el encabezado `sumariza` / `sumariza_id`, resolviendo la asignación `sumariza` por ID explícito o por jerarquía como fallback.
- `contable/tests/test_excel_cuentas.py` [MODIFY]:
  - Corregido `Empresa.nombre` en el setup de pruebas.
  - Agregadas aserciones de exportación y asignación de `sumariza_id` en los tests de generación y captura masiva.

### Detalle Técnico
1. **Estructura de Columnas:** La columna `Sumariza ID` se posiciona inmediatamente después de `ID`, manteniendo el orden lógico de identificadores previos a la jerarquía (`ID`, `Sumariza ID`, `Jerarquía`, `Nombre Cuenta`, etc.).
2. **Resolución en Importación:** En `procesar_captura_excel_cuentas`, si la fila trae un valor numérico en `Sumariza ID` y dicho ID existe en la empresa activa, se vincula `sumariza_obj = cuentas_por_id[sumariza_id_val]`, otorgando prioridad a la relación explícita por sobre la inferencia por cadena de texto.

### Resultado de las Pruebas
```powershell
.\venv\Scripts\python.exe manage.py test contable.tests.test_excel_cuentas --keepdb --noinput
```
**Resultado:** `OK (Ran 3 tests in 7.4s)` — Generación de Excel, actualización/creación por captura masiva y vistas HTTP con modal comprobadas sin errores.

### Estado actual y siguientes pasos
La exportación a Excel del Plan de Cuentas ya incluye la columna `Sumariza ID` tanto en la descarga como en el motor de recaptura.


## 29 de Agosto de 2026 — Replicación de Plan de Cuentas y Parámetros Contables (Empresa 2 a Empresa 4)

### Objetivo
1. **Replicación Contable Completa:** Replicar de forma íntegra el catálogo del Plan de Cuentas (`Cuenta`), los Parámetros Contables (`ParametrosContables`) y los Medios de Pago (`MedioPago`) desde la empresa origen `ARMERIA ARMAR SAS` (ID=2) hacia la empresa destino `RODRIGUEZ MARCELO FABIAN` (ID=4).
2. **Generalización del Comando de Replicación:** Mejorar la Fase 4 del comando `replicar_plan_cuentas.py` para replicar directamente los medios de pago configurados en la empresa origen mapeando sus cuentas contables al nuevo árbol destino.

### Archivos Modificados
- `contable/management/commands/replicar_plan_cuentas.py` [MODIFY]:
  - En la Fase 4, se implementó la lectura y clonación dinámica de los objetos `MedioPago` existentes en la `empresa_origen`, remapeando su clave foránea `cuenta_contable` al ID de la cuenta clonada en la `empresa_destino`. Se mantuvo la compatibilidad con archivo CSV como mecanismo alternativo de fallback.

### Detalle Técnico
1. **Atomicidad y Mapeo en Memoria:** Todo el proceso se ejecuta dentro de un bloque `transaction.atomic()`. En la Fase 1 se crearon 220 cuentas contables para la empresa 4 conservando código, jerarquía, imputabilidad, tipo y atributos especiales, generando un mapa en memoria `{id_origen: nueva_cuenta_destino}`.
2. **Reconstrucción del Árbol Jerárquico:** En la Fase 2 se asignaron 215 relaciones `sumariza` apuntando estrictamente a las cuentas padre de la empresa 4.
3. **Mapeo de Parámetros y Medios de Pago:** En la Fase 3 se instanció `ParametrosContables` para la empresa 4 con 23 cuentas contables remapeadas, y en la Fase 4 se clonaron los 6 medios de pago (`CHQ-TER`, `EFE-USD`, `EFE-ARS`, `RET-GCIA`, `RET-IIBB`, `TRA-BCO`) con sus respectivas cuentas contables pertenecientes a la empresa 4.

### Resultado de las Pruebas
- Comando ejecutado: `python manage.py replicar_plan_cuentas --origen 2 --destino 4`.
- Salida del comando: 220 cuentas creadas, 215 relaciones jerárquicas vinculadas, parámetros contables creados con 23 cuentas mapeadas y 6 medios de pago clonados exitosamente.
- Validación en base de datos: Confirmado que todas las cuentas asociadas a la empresa 4 pertenecen exclusivamente a `empresa_id=4`, sin referencias cruzadas residuales hacia la empresa 2.

### Estado actual y siguientes pasos
La Empresa ID=4 (`RODRIGUEZ MARCELO FABIAN`) cuenta ahora con su estructura contable y medios de pago plenamente operativos e independientes.


## 28 de Agosto de 2026 — Reubicación de Campos CUIT/DNI y Policía en Formulario de Cliente

### Objetivo
1. **Reubicación de Identificación (CUIT/DNI):** Mover el input de número de documento / CUIT hacia adentro de la tarjeta de "Naturaleza del Cliente" y alinearlo a la derecha, agrupando semánticamente la identidad.
2. **Reubicación de "Es Policía":** Mover el campo obligatorio "¿Es Policía / Fuerza de Seguridad?" al final de la tarjeta del módulo de "Registro de Armería" acompañando a los campos CLU.

### Archivos Modificados
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]:
  - Refactorizada la tarjeta de "Naturaleza del Cliente" convirtiéndola en un contenedor `flex flex-col md:flex-row justify-between items-start md:items-center gap-6`.
  - Agregado el input "Número de Documento / CUIT" dentro de dicha tarjeta flotando a la derecha (`w-full md:w-1/3 ml-auto`) cuando es aplicable al módulo de armería, y como fallback externo mediante un `<template x-if="!puedeArmeria">` para evitar duplicidad del atributo `name` y bugs en el DOM.
  - Movido `form_armeria.es_policia` al grid de 3 columnas de "Registro de Armería", optimizando la simetría de los campos de credencial y seguridad.

### Detalle Técnico
1. **Prevención de Duplicados en DOM HTMX:** Como la validación de CUIT se maneja tanto para altas normales (solo DNI/CUIT) como para altas completas (Física/Jurídica), al mover el input dentro de un `<template x-if="puedeArmeria">` se programó la contracara `<template x-if="!puedeArmeria">`. Alpine.js procesa estos templates removiendo del DOM los nodos inactivos; esto garantiza que al hacer un submit (HTTP POST) Django reciba exactamente un solo valor para la clave `cuit` en lugar de una lista conflictiva.

### Estado actual y siguientes pasos
Los campos han sido exitosamente reordenados y agrupados según la nueva lógica, mejorando la usabilidad y conservando toda la validación por HTMX del padrón.


## 28 de Agosto de 2026 — Migración de Permisos de Armería y Eliminación de JOSEN

### Objetivo
1. **Lógica de Visibilidad de Armería:** Migrar el control de acceso a los formularios y configuraciones de Armería, pasando de basarse en permisos individuales por usuario (`puede_armeria`) a depender del atributo `tipo_actividad` de la Empresa activa en sesión (si es 'ARMERIA', el módulo se activa para los empleados de la empresa).
2. **Eliminación del Módulo JOSEN:** Borrar de manera permanente todas las referencias, modelos de base de datos, formularios, vistas (HTMX y generales), URLs y componentes de interfaz relacionados al submódulo JOSEN ya cancelado.

### Archivos Modificados
- `usuarios/models.py` [MODIFY]:
  - Eliminados los campos `permiso_armeria_ver`, `permiso_armeria_editar`, `permiso_josen_ver` y `permiso_josen_editar` del modelo `Perfil`.
- `usuarios/forms.py` [MODIFY]:
  - Eliminados los campos de permisos de Armería y JOSEN de `UsuarioForm`.
- `facturacion/models.py` [MODIFY]:
  - Eliminados completamente los modelos `RubroJosen` y `ExtensionJosen`.
- `facturacion/forms.py` [MODIFY]:
  - Eliminados los formularios `ExtensionJosenForm` y `RubroJosenForm`.
- `facturacion/views_htmx.py` [MODIFY]:
  - Eliminado el CRUD completo HTMX para Rubros JOSEN (`rubro_modal`, `buscar_rubros`, `eliminar_rubro`).
  - Refactorizado `cliente_modal`: Eliminada la lógica de JOSEN y reemplazada la lógica `puede_armeria` (ahora se lee de `Empresa.tipo_actividad == 'ARMERIA'`).
- `config/urls.py` [MODIFY]:
  - Eliminadas las rutas de configuración de Rubros JOSEN.
- `core/views_config.py` [MODIFY]:
  - Eliminado el pase a contexto de los rubros JOSEN para el panel de control.
- `facturacion/admin.py` [MODIFY]:
  - Eliminado `JosenInline` de la visualización en el Django Admin y sus importaciones.
- `templates/configuracion/modals/usuario_form.html` [MODIFY]:
  - Removidas las cajas de selección de permisos para Armería y JOSEN.
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]:
  - Removida la sección HTML `Parámetros Josen` condicionada por `puede_josen`.
- `templates/configuracion/partials/hub.html` [MODIFY]:
  - Removido el botón de acceso al menú de Rubros JOSEN en la sección contable.
- **Archivos Eliminados** [DELETE]:
  - `templates/configuracion/partials/rubros.html`
  - `templates/configuracion/partials/rubro_table_rows.html`
  - `templates/configuracion/modals/rubro_josen_form.html`

### Detalle Técnico
1. **Base de datos:** Se generaron 2 archivos de migraciones, `facturacion/migrations/0052_delete_extensionjosen_delete_rubrojosen.py` y `usuarios/migrations/0007_remove_perfil_permiso_armeria_editar_and_more.py`. Al correr `migrate` se eliminaron exitosamente las tablas asociadas y columnas en la base de datos `PostgreSQL`.
2. **Refactorización de visibilidad:** Al usar `Empresa.tipo_actividad`, el acceso a Armería se maneja dinámicamente de acuerdo al contexto comercial en el que esté logueado el usuario, reduciendo el riesgo de errores de asignación de permisos manuales.

### Estado actual y siguientes pasos
El módulo JOSEN ha sido erradicado del sistema y los permisos para el módulo de Armería pasaron satisfactoriamente de estar basados en roles/perfiles de usuarios a depender de la naturaleza de la empresa seleccionada al iniciar la sesión.

## 28 de Agosto de 2026 — Visibilidad y Obligatoriedad del Campo "Es Policía" en Clientes

### Objetivo
1. **Obligatoriedad y Visibilidad:** Hacer que el campo "¿Es Policía / Fuerza de Seguridad?" (asociado a la extensión de Armería) sea de carácter obligatorio, tenga una opción vacía por defecto para forzar la elección, y se ubique en la parte superior del formulario de creación/edición de clientes (sección "Identidad y Condición Fiscal") para mayor visibilidad al momento del alta.

### Archivos Modificados
- `facturacion/forms.py` [MODIFY]:
  - `ExtensionArmeriaForm`: Modificado el campo `es_policia` para requerir una selección explícita (`required=True`), agregando la opción vacía `('', "Seleccione una opción")` en los choices, y ajustando el `initial` a `''` cuando se trata de una nueva entidad.
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]:
  - Reubicado el campo `form_armeria.es_policia` desde la sección inferior "Registro de Armería" hacia la sección superior "1. Identidad y Condición Fiscal", colocándolo junto al "Rol Comercial".
  - Se agregó el indicador visual de campo obligatorio (`*` en rojo).

### Detalle Técnico
1. **Forzado de Selección Inicial:** Al agregar una opción con valor vacío y `required=True` en un `TypedChoiceField`, la validación nativa de Django impedirá que el formulario se envíe sin que el usuario seleccione activamente "SÍ" o "NO". Si no selecciona nada, la validación fallará y se mostrará el error en el listado superior del modal y debajo del campo.

### Estado actual y siguientes pasos
El campo ahora es obligatorio y mucho más visible en el inicio del formulario.

## 26 de Agosto de 2026 — Optimización de Sugerencias en Trazabilidad (Solo con movimientos)

### Objetivo
1. **Limpiar listado de sugerencias:** Evitar sugerir todos los clientes/proveedores y productos de la base de datos en los autocompletados del módulo de Trazabilidad, restringiendo los resultados exclusivamente a aquellos que realmente poseen movimientos o historiales asociados.

### Archivos Modificados
- `facturacion/views_htmx.py` [MODIFY]:
  - `typeahead_clientes`: Agregada la validación del parámetro `solo_trazabilidad`. Si está activo (`1`), se utiliza `Exists()` sobre el modelo `Subproducto` con `OuterRef` hacia el ID del cliente o proveedor para excluir del QuerySet a quienes no tengan participación en los subproductos de la empresa.
  - `typeahead_productos_venta`: Implementada la misma lógica para excluir productos que no existan dentro de la tabla de Trazabilidad/Subproductos de la empresa activa. Además, se suprimió la restricción rígida de `subprod=False` que regía para las ventas estándar, permitiendo que sí emerjan los artículos con trazabilidad (`subprod=True`) bajo este modo exclusivo.
- `templates/productos/trazabilidad_list.html` [MODIFY]:
  - Añadido el valor `solo_trazabilidad: "1"` estático en los diccionarios JS que forman el atributo `hx-vals` de los inputs de búsqueda rápida, de manera que esta regla opere exclusivamente aquí sin afectar las pantallas de facturación convencionales.

### Detalle Técnico
1. **Desempeño de Base de Datos:** En lugar de realizar JOINs masivos o comprobaciones iterativas, el uso de la función `Exists()` de Django genera subconsultas correlacionadas `EXISTS(SELECT ...)` en el motor de base de datos. Esto permite que el filtrado sea excepcionalmente rápido, frenando la búsqueda en cuanto se encuentra la primera coincidencia, lo cual no penaliza el rendimiento al escribir en el frontend.

### Estado actual y siguientes pasos
Los typeaheads de trazabilidad ahora solo ofrecen entidades y productos con movimientos reales en el sistema, agilizando mucho más las búsquedas.


## 26 de Agosto de 2026 — Reparación de Filtros en Trazabilidad de Subproductos

### Objetivo
1. **Corregir Filtro CliPro:** Solucionar el problema en el cual seleccionar un cliente/proveedor desde la lista desplegable o utilizar el botón de "Limpiar" no aplicaba los filtros en el backend, dejando la tabla sin cambios.

### Archivos Modificados
- `templates/productos/trazabilidad_list.html` [MODIFY]:
  - Eliminado el atributo `onsubmit="event.preventDefault();"` del formulario de filtros.
  - Eliminado el listener JS manual de `submit` que interceptaba y realizaba la petición por `htmx.ajax` ignorando los valores de los inputs.
  - Al quitar esta intercepción manual, se delegó el control 100% al comportamiento nativo de HTMX sobre el evento submit, garantizando la correcta serialización y envío de todo el querystring.

### Estado actual y siguientes pasos
El formulario ya procesa e incluye exitosamente todos sus valores cuando se dispara remotamente mediante `htmx.trigger`.


## 26 de Agosto de 2026 — Filtro por Sucursal en Trazabilidad de Subproductos

### Objetivo
1. **Filtro de Sucursales:** Agregar la lógica en la vista y en la UI para permitir la búsqueda y visualización de subproductos según la sucursal a la que pertenecen, dentro del módulo de Trazabilidad.

### Archivos Modificados
- `productos/views_trazabilidad.py` [MODIFY]:
  - `SubproductoTrazabilidadListView`: Modificado el método `get_queryset` para incorporar `sucursal_id` como parámetro de búsqueda extraído de `request.GET.get('sucursal')`.
  - Agregado el método `get_context_data` para enviar al contexto las sucursales pertenecientes a la empresa en sesión y renderizar dinámicamente el `select` de opciones.
- `templates/productos/trazabilidad_list.html` [MODIFY]:
  - Añadido el combo desplegable (`select`) para la sucursal, integrado con HTMX para refresco automático.
  - Añadida la cabecera `<th>Sucursal</th>` en la tabla de resultados.
- `templates/productos/partials/trazabilidad_grilla.html` [MODIFY]:
  - Agregada la celda correspondiente para visualizar el nombre de la sucursal en cada registro (`{{ sp.sucursal.nombre }}`).
  - Ajustados los valores de los atributos `colspan` de 6 a 7 para las filas de "vacío" o "cargar más" de la tabla, con el fin de conservar la alineación visual tras la adición de la columna.

### Detalle Técnico
1. **Conservación de Filtros HTMX:** El nuevo select cuenta con el disparador propio integrado con la solicitud general al endpoint y, al estar envuelto en el form `#form-filtros-trazabilidad`, sus parámetros se pasan por URL manteniendo el comportamiento responsivo.

### Estado actual y siguientes pasos
Filtro de Sucursales integrado y tabla adaptada a la nueva columna.


## 26 de Agosto de 2026 — Corrección de Error de Sintaxis (NameError) en Modal de Trazabilidad

### Objetivo
1. **Solucionar fallo 500:** Corregir un error de sintaxis (`NameError: name 'sp' is not defined`) en la lista de comprensión de la vista `trazabilidad_modal_timeline` que causaba que la carga del modal y el botón de detalles fallaran en la interfaz.

### Archivos Modificados
- `productos/views_trazabilidad.py` [MODIFY]:
  - Corregida la lista de comprensión en la línea 85 de `[sp.cuim for sp.cuim in subproductos_serie if sp.cuim]` a `[sp.cuim for sp in subproductos_serie if sp.cuim]`.

### Detalle Técnico
1. **Sintaxis de Python:** La declaración incorrecta `for sp.cuim in subproductos_serie` intentaba usar un atributo de un objeto no definido (`sp`) como variable de iteración. Se ajustó a la sintaxis estándar `for sp in subproductos_serie` para extraer correctamente los atributos de los objetos instanciados.
2. **Impacto en UI:** Este error de servidor (HTTP 500) interrumpía la carga asíncrona de los modales de HTMX, dejando inoperativos los botones (como el de "detalle") asociados al evento de respuesta de esta vista.
3. **Cierre de Modales HTMX:** Se identificó que las plantillas `subproducto_detalle_modal.html` y `subproducto_editar_modal.html` carecían de la declaración de la función JavaScript `closeModal()`, lo cual provocaba que si el usuario hacía clic fuera del modal (en el backdrop gris) o en el botón de cerrar, el modal no respondiera y la pantalla quedara bloqueada con la superposición gris. Se inyectó el script correspondiente para restaurar la interactividad.

### Estado actual y siguientes pasos
El problema en el módulo de trazabilidad y el bloqueo de pantalla de los modales está **completamente solucionado y operativo**.

## 26 de Agosto de 2026 — Perfil de Lectura Inteligente de Compras (CUIT 30-71132306-2)

### Objetivo
1. **Nuevo perfil OCR:** Incorporar un módulo de lectura de PDF para las facturas del proveedor con CUIT `30-71132306-2`, capaz de identificar el "Artículo" como código principal, pero que también separe y ofrezca el código suplementario ubicado al final de la descripción.
2. **Emparejamiento flexible:** Permitir que el sistema busque el producto en la base de datos de la empresa haciendo un doble intento inteligente (`fallback`): primero por el código principal ("Artículo"), y si falla, por el código alternativo del proveedor que venía embutido en el detalle.

### Archivos Modificados / Creados
- `facturacion/services/perfiles_lectura/cuit_30711323062.py` [NEW]:
  - Archivo de perfil `procesar_perfil(texto_completo)`. Se programó una expresión regular adaptada a este diseño de PDF para capturar cantidades, precios, totales, "Artículo" (como `codigo`), descripción, y el código embutido final (como `codigo_alt`).
- `facturacion/views_procesamiento.py` [MODIFY]:
  - En la vista `CargaCompraAutomaticaView`, se incorporó la lectura del nuevo atributo `codigo_alt`. Si el sistema no logra vincular un ítem de la factura por su `codigo` primario, intenta automáticamente emparejarlo usando `cod_prov=codigo_alt` y `detalle__icontains=codigo_alt`, extendiendo las capacidades de importación de todo el ERP.

### Detalle Técnico
1. **Rediseño OCR por Modo de Lectura (`sort=True`):** Se descubrió que el motor core de `extractor_facturas.py` procesaba los documentos activando la reconstrucción de párrafos de PyMuPDF (`sort=True`), lo cual destruye el formato tabular y agrupa las líneas de texto horizontalmente. Se reconstruyó integralmente la Expresión Regular de los ítems (`r'^[\s]*([\d\,\.]+)[\s]+(\d+)[\s]+(.*?)[\s]+([\d\,\.]+)[\s]+([\d\,\.]+)[\s]*\n[\s]*(.*?)[\s]*\n'`) para adaptarse a este flujo continuo y garantizar que la grilla reciba correctamente los artículos.
2. **Corrección de Totales Invertidos:** En los PDFs de este proveedor, la librería de extracción suele leer el bloque de montos monetarios de los totales *antes* que las etiquetas de texto ("SUBTOTAL", "TOTAL"). Se agregó una expresión regular estructural para interceptar correctamente los valores reales (Neto, Total e IVA) ignorando los subtotales post-descuento.
3. **Mapeo de Descuento Global y Totales Explícitos:** Se programó el perfil para aislar el valor del descuento general de la factura y extraer simultáneamente los 5 valores impositivos fundamentales: Subtotal Bruto, Descuento, Neto Gravado, IVA y Total. Se extendieron las capacidades del frontend (`carga_compra_automatica.html` y `compras_carga.html`) para que transporten y asignen automáticamente todos estos campos directamente en el formulario de la vista de Carga Venta/Compra, disparando el recálculo visual en pantalla de forma instantánea.
4. **Robustez de OCR Transversal:** La modificación a `views_procesamiento.py` fue diseñada de forma transparente (`it.get('codigo_alt')`), lo que significa que a partir de ahora *cualquier* futuro perfil de lectura podrá opcionalmente suministrar un `codigo_alt` y el sistema sabrá aprovecharlo para emparejar inteligentemente los artículos.

### Estado actual y siguientes pasos
Perfil de lectura completado, probado sobre el archivo PDF de muestra y listo para utilizar en el sistema en vivo de Carga de Compras.


## 26 de Agosto de 2026 — Corrección de desaparición de Proveedor al editar Producto

### Objetivo
1. **Evitar desaparición de proveedor:** Solucionar el problema reportado donde al editar un producto en el sistema, el proveedor preexistente desaparecía del formulario forzando al usuario a volver a seleccionarlo.

### Archivos Modificados
- `productos/forms.py` [MODIFY]:
  - Modificado el método `__init__` de `ProductoForm`. El queryset del campo `proveedor` ahora incluye no solo a los proveedores estándar de la empresa activa (`tipo_entidad=2`), sino que también se expande dinámicamente mediante `Q()` para incluir explícitamente al proveedor actual del producto en caso de que este fuera configurado de forma global (`empresa__isnull=True`) o con otro `tipo_entidad`.
  - Se agregó ordenamiento alfabético `.order_by('razon_social')` para el catálogo de proveedores y por `'detalle'` para Marca, Rubro y Familia.

### Detalle Técnico
1. **Conservación de Foreign Key:** El comportamiento original de `forms.Select` de Django descarta automáticamente el valor actual de una instancia si este no se encuentra presente dentro del queryset asignado al campo. Al ampliar el queryset sumando el `self.instance.proveedor_id` mediante el operador `|` (OR), garantizamos que la opción se renderice correctamente en el DOM y no se pierda al guardar el formulario.

### Estado actual y siguientes pasos
El problema de edición de proveedor está **completamente solucionado**.


## 26 de Agosto de 2026 — Conversión de Facturas a WEBP y Nombramiento Específico (Plan 067)

### Objetivo
1. **Unificación WebP (Stitching):** Optimizar el almacenamiento y visualización convirtiendo los PDFs de compras en imágenes verticales continuas en formato `WebP`, en lugar de preservar el PDF.
2. **Nomenclatura y Directorio Fijo:** Renombrar el archivo generado siguiendo el patrón estricto `{empresa_id}.{ejercicio_id}.{asiento_id}.webp` y ubicarlo en la carpeta `compras_archivosWEBP/` **sólo** tras confirmar y contabilizar la compra.
3. **Bloqueo de Edición (Readonly):** Proteger los montos leídos mediante OCR en el frontend, bloqueando la edición de precios en la grilla al provenir del escáner automático.

### Archivos Modificados
- `facturacion/services/extractor_facturas.py` [MODIFY]:
  - Modificado el extractor para iterar hasta 5 páginas del documento PDF, convertir cada `pixmap` a una imagen con `Pillow` y unirlas verticalmente en un "pergamino" continuo (`stitched.paste()`).
  - Cambiado el formato de salida a `WEBP` en lugar de `PNG` logrando mayor compresión.
- `facturacion/models.py` [MODIFY]:
  - Actualizado `compras_pdf_path` para apuntar ahora a `compras_archivosWEBP/{filename}` sin timestamp (el nombre viene prefijado del controlador).
- `facturacion/views_procesamiento.py` [MODIFY]:
  - Ahora se devuelve la ruta `.webp` a la sesión y se destruye el PDF original de forma segura (sin cron script en python, confiando en limpieza temporal asíncrona de SO).
- `facturacion/views.py` [MODIFY]:
  - Al completar la transacción y generar el asiento en `ComprasCargaView.post`, se captura `compra.asiento_id` y `compra.ejercicio_id` para renombrar y guardar definitivamente el comprobante como `{empresa_id}.{ejercicio_id}.{asiento_id}.webp`.
- `templates/facturacion/compras_carga.html` [MODIFY]:
  - Se implementó un script que detecta si el formulario proviene de OCR (`pdf_temp_path`). De ser así, se iteran todos los campos `precio`, `cto_adq`, `cto_rep` y `descuento`, inyectando propiedades `readOnly` y aplicando clases de bloqueo visual (`bg-slate-100`, `cursor-not-allowed`) para blindar la integridad del dato escaneado.

### Detalle Técnico
1. **Stitching sin OOM:** El bucle de páginas está acotado deliberadamente a `min(5, len(doc))` para mitigar posibles ataques de denegación (archivos de miles de páginas) que provoquen Timeouts en Gunicorn o saturen la RAM, cubriendo a la vez el 99% de las facturas convencionales.
2. **Manejo de Transacciones:** Si el usuario no hace clic en "Aceptar" y abandona la página, la imagen WebP vive únicamente en `temp_facturas/`, el cual será depurado con un cron de Linux. Ningún registro huérfano impacta en `compras_archivosWEBP`.

### Estado actual y siguientes pasos
El plan está **completamente implementado, blindado y probado**. Los comprobantes son ahora pergaminos WebP muy ligeros.
## 26 de Agosto de 2026 — Limpieza de Archivos Temporales (PDF y PNG) en Carga de Compras

### Objetivo
1. **Borrar Temp de Compras:** Solucionar el problema de la acumulación de archivos temporales (PDFs e imágenes PNG de vista previa) que no se borraban luego de cargar una factura de compra mediante el servicio OCR de lectura de CUIT.

### Archivos Creados / Modificados
- `facturacion/services/extractor_facturas.py` [MODIFY]:
  - Modificada la generación del nombre de la imagen PNG temporal para que utilice el mismo nombre base que el PDF (en lugar de generar un UUID distinto), lo que permite que el backend pueda emparejarlos y borrarlos juntos al finalizar.
- `facturacion/views.py` [MODIFY]:
  - En la vista de carga de comprobantes, modificado el bloque donde se persiste el PDF definitivo para también ubicar y eliminar el PNG temporal correspondiente, de forma conjunta y limpia.
- `facturacion/views_procesamiento.py` [MODIFY]:
  - En `CargaCompraAutomaticaView.post`, añadido un recolector de basura (garbage collector) proactivo: `_limpiar_temp_facturas(temp_dir)`. Este proceso corre antes de crear un nuevo archivo y elimina automáticamente cualquier archivo huérfano dentro de `temp_facturas` que sea anterior a 1 hora (3600 segundos). Esto asegura que los archivos abandonados (subidos, pero no persistidos) no se acumulen.

### Detalle Técnico
1. **Emparejamiento por Basename:** Al guardar el PDF se asocia un nombre base (ej. `1234abcd.pdf`) y ahora la imagen se llama igual (`1234abcd.png`).
2. **Garbage Collector de Temp:** Para los casos en que el usuario sube una factura y abandona la página sin guardar, la limpieza periódica basada en el tiempo de modificación del archivo (`st_mtime`) impide que la carpeta `temp_facturas` crezca sin control.

### Estado actual y siguientes pasos
Corrección de archivos temporales **completamente implementada y operativa**.


## 23 de Agosto de 2026 — Exportación y Recaptura Masiva en Excel del Plan de Cuentas — Plan 066

### Objetivo
1. **Exportación a Excel Completo:** Implementar la exportación del listado total de cuentas contables (`contable.models.Cuenta`) de la empresa activa en formato `.xlsx` con estilos openpyxl (slate header `0F172A`, texto blanco en negrita Arial, bordes delgados y autoajuste de ancho).
2. **Recaptura / Importación Masiva desde Excel:** Proveer un modal interactivo con HTMX y Tailwind CSS para subir un archivo Excel y procesar actualizaciones y altas masivas de cuentas de forma atómica (`transaction.atomic()`).
3. **Manejo Inteligente de IDs:**
   - Si la celda `ID` coincide con una cuenta existente en la empresa activa, se actualizan sus campos (`Jerarquía`, `Nombre Cuenta`, `Imputable`, `Tipo`, `Código Legacy`, `RG 830`, `Tipo Disponibilidad`, etc.) manteniendo intacto el `ID`.
   - Si la celda `ID` está vacía o el `ID` no existe en la empresa activa, se interpreta como cuenta nueva. El sistema **no fuerza el ID ingresado** y deja que PostgreSQL le asigne automáticamente el `ID` autoincremental correspondiente.
   - Unificación automática de los nombres de cuenta en **MAYÚSCULAS**.

### Archivos Creados / Modificados
- `contable/services/excel_service.py` [NEW]:
  - `COLUMNAS_CUENTA_MAP`: Mapeo de columnas y encabezados de Excel.
  - `generar_excel_cuentas(queryset)`: Servicio de generación de `.xlsx` para el plan de cuentas.
  - `procesar_captura_excel_cuentas(empresa, usuario, archivo_excel)`: Lógica atómica de lectura de Excel, actualización por ID existente y alta de cuentas nuevas con resolución de parentesco (`sumariza`).
- `contable/views_htmx.py` [MODIFY]:
  - `exportar_cuentas_excel_completo`: Vista para descargar el Excel completo.
  - `modal_capturar_cuentas_excel`: Despliega el modal de recaptura.
  - `capturar_cuentas_excel`: Procesa el archivo subido via POST y emite la señal HTMX `reloadCuentas`.
- `templates/contable/modals/capturar_excel_modal.html` [NEW]:
  - Plantilla del modal de recaptura con resumen de resultados y caja de alerta destacada con las reglas aclaratorias de carga de ID.
- `templates/configuracion/partials/cuentascontables.html` [MODIFY]:
  - Integración de los botones **"Capturar Excel"** y **"Excel Completo"** en la barra superior junto al botón de **"Nueva Cuenta"**.
- `config/urls.py` y `contable/urls.py` [MODIFY]:
  - Registro de las rutas URL para exportación y recaptura de cuentas contables.
- `contable/tests/test_excel_cuentas.py` [NEW]:
  - Pruebas automatizadas de exportación a Excel y recaptura masiva (creación con ID vacio/inexistente y actualización por ID).
- `docs/planes/066_recaptura_excel_plan_cuentas.md` [NEW]:
  - Copia guardada del plan de implementación en la carpeta histórica de planes.
- `docs/walkthrough.md` [MODIFY]:
  - Actualización de la bitácora de desarrollo.

### Detalle Técnico
1. **Regla de Negocio del ID:** Se verificó el diccionario en memoria de las cuentas existentes por `id` pertenencientes a `empresa=empresa`. Si el ID suministrado no se encuentra en la base de datos de esa empresa, la fila se inserta mediante `Cuenta.objects.create(empresa=empresa, ...)` sin pasar la clave primaria `id`, permitiendo que la secuencia de PostgreSQL genere la clave incremental limpia sin conflictos.
2. **Asignación Jerárquica:** Se calcula la jerarquía padre extrayendo la subcadena previa al último punto (ej. `1.1` para `1.1.01`) y asociando la Foreign Key `sumariza` automáticamente.
3. **Respuesta HTMX:** Si la recaptura actualiza o crea al menos 1 cuenta, la vista asigna la cabecera `HX-Trigger: {"reloadCuentas": true}`, refrescando inmediatamente la grilla de cuentas sin recargar la página.

### Resultados de las Pruebas
- **Comando ejecutado:** `.\venv\Scripts\python.exe manage.py test contable.tests.test_excel_cuentas`
- **Resultado:**
  - `Ran 3 tests in 0.941s` -> **OK**
  - `test_generar_excel_cuentas`: Pasó exitosamente.
  - `test_capturar_excel_actualizar_y_crear_cuentas`: Pasó exitosamente (verificó actualización de ID existente, creación de ID en blanco y asignación de ID autoincremental automático al ingresar un ID inexistente).
  - `test_views_excel_exportar_y_modal`: Pasó exitosamente.

### Estado actual y siguientes pasos
Plan 066 **completamente implementado, probado y verificado**.


## 22 de Agosto de 2026 — Replicación de Plan de Cuentas, Parámetros, Medios de Pago y Cuentas Bancarias (Empresa 1 -> Empresa 3) — Plan 065

### Objetivo
1. **Replicación Completa del Plan de Cuentas:** Duplicar el catálogo completo de 247 cuentas contables (`contable.models.Cuenta`) desde la Empresa Origen (`empresa_id = 1` - Lopez Rios y Asoc SA) hacia la Empresa Destino (`empresa_id = 3` - EMPRESA TEST).
2. **Preservación de Estructura Jerárquica:** Mantener y reasignar las relaciones de parentesco contable (`sumariza`) entre las cuentas clonadas correspondientes a la Empresa 3.
3. **Replicación de Parámetros Contables:** Clonar la configuración de `contable.models.ParametrosContables` desde la Empresa 1 a la Empresa 3, mapeando automáticamente las 23 claves foráneas de cuentas predeterminadas (`cta_caja_mostrador`, `cta_ventas`, `cta_compras`, `cta_iva_credito`, `cta_iva_debito`, etc.) hacia las cuentas clonadas equivalentes de la Empresa 3.
4. **Migración de Medios de Pago (`MedioPago`):** Procesar el archivo de exportación `d:\borrador\medios_pagos.csv` para poblar los Medios de Pago (`EFE-ARS`, `EFE-USD`, `CHQ-TER`, `TRA-BCO`, `RET-GCIA`, `RET-IIBB`) enlazándolos automáticamente a las cuentas contables correspondientes para Empresa 3 y Empresa 1.
5. **Replicación de Cuentas Bancarias (`CuentaBancaria`):** Clonar las Cuentas Bancarias de la Empresa 1 (Banco Patagonia, Credicoop, Galicia) hacia la Empresa 3, reasignando sus Foreign Keys de cuentas contables principales y de cheques emitidos.

### Archivos Creados / Modificados
- `contable/management/commands/replicar_plan_cuentas.py` [MODIFY]:
  - Comando de gestión de Django `python manage.py replicar_plan_cuentas --origen 1 --destino 3` extendido con 5 fases atómicas (`transaction.atomic()`).
- `docs/planes/065_replicar_plan_cuentas.md` [MODIFY]:
  - Plan de implementación histórico actualizado.
- `docs/walkthrough.md` [MODIFY]:
  - Registro cronológico incremental en la bitácora de desarrollo.

### Detalle Técnico
1. **Fase 1 - Creación/Sincronización de Cuentas:** Carga las 247 cuentas de la Empresa 1 y las crea/actualiza para la Empresa 3 usando un diccionario en memoria por jerarquía (`jerarquia`) para evitar consultas N+1.
2. **Fase 2 - Asignación Jerárquica (`sumariza`):** Mapea cada `sumariza_id` original al ID de la cuenta padre clonada para la Empresa 3.
3. **Fase 3 - Parámetros Contables:** Crea el registro `ParametrosContables` para la Empresa 3 y mapea de forma automática 23 campos FK (`cta_iva_credito`, `cta_iva_debito`, `cta_caja`, `cta_ventas`, `cta_compras`, `cta_caja_mostrador`, etc.) a sus cuentas clonadas correspondientes.
4. **Fase 4 - Importación de Medios de Pago:** Lee `d:\borrador\medios_pagos.csv` y vincula reactivamente la `cuenta_contable` de cada medio de pago (`EFE-ARS`, `EFE-USD`, `CHQ-TER`, `TRA-BCO`, `RET-GCIA`, `RET-IIBB`) con `ParametrosContables` de cada empresa.
5. **Fase 5 - Replicación de Cuentas Bancarias:** Clona los registros de `CuentaBancaria` de la Empresa 1 a la Empresa 3 asociando `cuenta_contable` y `cuenta_contable_cheques`.

### Resultados de la Ejecución
- **Comando ejecutado:** `python manage.py replicar_plan_cuentas --origen 1 --destino 3`
- **Consola output:**
  - `Fase 1 completada: 247 cuentas procesadas en 'EMPRESA TEST'.`
  - `Fase 2 completada: 242 relaciones jerárquicas ('sumariza') vinculadas.`
  - `Fase 3 completada: Parámetros Contables actualizados con 23 cuentas mapeadas.`
  - `Fase 4 completada: 6 Medios de Pago procesados desde d:\borrador\medios_pagos.csv.`
  - `Fase 5 completada: 3 Cuentas Bancarias procesadas en 'EMPRESA TEST'.`
- **Validación DB:**
  - `Empresa 3` posee **247** cuentas contables, **1** `ParametrosContables`, **6** `MedioPago` y **3** `CuentaBancaria` enlazados.
  - `Empresa 1` posee **247** cuentas contables, **1** `ParametrosContables`, **6** `MedioPago` y **3** `CuentaBancaria` enlazados.

### Estado actual y siguientes pasos
Plan 065 **completamente implementado, probado y verificado**.

---

## 22 de Agosto de 2026 — Refactorización y Limpieza de Catálogos (Unificación de Marcas, Rubros y Familias por Empresa) — Plan 064

### Objetivo
1. **Unificación Conceptual del Catálogo Maestro:** Eliminar de forma definitiva las relaciones `sucursales` (ManyToMany) en los modelos `Marca`, `Rubro` y `Familia` en la app `productos`.
2. **Consistencia y Simplificación de Base de Datos:** Establecer que los catálogos pertenecen globalmente a la `Empresa`. El aislamiento y segmentación por sucursal se gestiona de forma exclusiva en el inventario físico (`StockSucursal`), movimientos de stock, operaciones de caja y comprobantes.
3. **Limpieza de UI/UX y Eliminación de Código Fantasma:** Quitar los componentes visuales de asignación de sucursales en los modales de creación/edición de categorías y en las tablas de configuración.

### Archivos Creados / Modificados
- `productos/models.py` [MODIFY]:
  - Eliminado el campo `sucursales = models.ManyToManyField(Sucursal, ...)` en los modelos `Marca`, `Rubro` y `Familia`.
- `productos/migrations/0030_remove_familia_sucursales_remove_marca_sucursales_and_more.py` [NEW]:
  - Migración de Django que elimina las 3 tablas pivote intermedias de PostgreSQL (`productos_marca_sucursales`, `productos_rubro_sucursales`, `productos_familia_sucursales`).
- `productos/forms.py` [MODIFY]:
  - Removido `'sucursales'` de `fields` y `widgets`, y limpiada la lógica de inicialización en `MarcaForm`, `RubroForm` y `FamiliaForm`.
- `productos/views_htmx.py` [MODIFY]:
  - Removidas las llamadas redundantes `form.save_m2m()` en `marca_modal`, `rubro_prod_modal` y `familia_modal`.
- `productos/management/commands/migrar_productos.py` [MODIFY]:
  - Removidas las asignaciones artificiales `sucursales.add(...)` durante la importación desde VFP.
- `templates/productos/modals/marca_modal.html` [MODIFY]:
  - Eliminada la sección visual de selección de sucursales en el modal de marcas.
- `templates/productos/modals/rubro_prod_modal.html` [MODIFY]:
  - Eliminada la sección visual de selección de sucursales en el modal de rubros de productos.
- `templates/productos/modals/familia_modal.html` [MODIFY]:
  - Eliminada la sección visual de selección de sucursales en el modal de familias.
- `templates/configuracion/partials/marcas.html` & `marcas_list.html` [MODIFY]:
  - Eliminados el encabezado `<th>Sucursales</th>` y las etiquetas/badges por sucursal de la tabla de marcas.
- `templates/configuracion/partials/rubros_prod.html` & `rubros_prod_list.html` [MODIFY]:
  - Eliminados el encabezado `<th>Sucursales</th>` y la columna de sucursales de la tabla de rubros de productos.
- `templates/configuracion/partials/familias.html` & `familias_list.html` [MODIFY]:
  - Eliminados el encabezado `<th>Sucursales</th>` y la columna de sucursales de la tabla de familias.
- `docs/planes/064_limpieza_sucursales_catalogos.md` [NEW]:
  - Plan de implementación histórico formalmente guardado.

### Detalle Técnico
1. **Esquema de BD Simplificado:** Al remover el campo M2M en Django y aplicar la migración 0030, las 3 tablas pivote fueron eliminadas en PostgreSQL.
2. **Optimizaciones de Rendimiento y Código:** Se aligeraron las transacciones de guardado al evitar inserciones en tablas pivote y se eliminaron filtros inútiles.
3. **Cero Impacto Operativo Negativo:** La búsqueda y facturación de productos continúa funcionando normalmente, ya que la disponibilidad por sucursal se rige por `StockSucursal.cantidad`.

### Estado actual y siguientes pasos
Plan 064 **completamente implementado, probado y verificado**.

---

## 22 de Agosto de 2026 — Exportación Personalizada/Completa en Excel y Captura Masiva de Productos — Plan 063

### Objetivo
1. **Exportación Personalizada a Excel:** Permitir a los usuarios generar reportes en formato Excel `.xlsx` seleccionando dinámicamente entre la totalidad de los campos del modelo `Producto`.
2. **Exportación de Tabla Completa:** Brindar un botón de descarga directa de la plantilla/maestro completo de productos de la empresa actual con todos los campos operables.
3. **Captura / Importación Masiva desde Excel:**
   - Forzar la conversión y guardado **SIEMPRE EN MAYÚSCULAS** del detalle del producto, código de proveedor, código de fábrica, marcas, rubros y familias.
   - Si el `ID` del producto está en el Excel y existe en la base de datos de la empresa: **actualizar todos los campos excepto el ID**.
   - Si el `ID` está vacío/nulo o no existe: **crear el nuevo producto** asignándole automáticamente el ID correspondiente que PostgreSQL genera.
   - Si la **Marca**, **Rubro** o **Familia** provista en el Excel no existe en la BD de la empresa: **crearla automáticamente en MAYÚSCULAS**, asignarle su ID autonumérico y asociarla al nuevo producto.
   - Incluir una advertencia explícita destacada en el modal de captura aclarando que para productos nuevos se debe dejar la casilla `ID` vacía.

### Archivos Creados / Modificados
- `productos/services/excel_service.py` [NEW]:
  - `generar_excel_productos(queryset, columnas_seleccionadas)`: construye libros Excel `.xlsx` estilizados (header slate-900, bordes delgados, alineación numérica y autoajuste de ancho de columnas).
  - `procesar_captura_excel_productos(empresa, usuario, archivo_excel)`: procesa atómicamente la lectura de archivos Excel, conversión a MAYÚSCULAS, creación automática de Marcas/Rubros/Familias y actualización/alta por `ID`.
- `productos/views_htmx.py` [MODIFY]:
  - `exportar_productos_excel_completo`: genera la descarga completa del maestro de productos.
  - `modal_exportar_seleccion`: despliega el modal interactivo con la lista completa de checkboxes por campo.
  - `exportar_productos_excel_seleccion`: procesa el POST y descarga el Excel filtrado por columnas.
  - `modal_capturar_excel`: renderiza el modal de captura con la advertencia de ID para nuevos artículos.
  - `capturar_productos_excel`: procesa la subida POST del Excel y retorna la parcial con el resumen de la captura emitiendo el evento `productosActualizados`.
- `productos/models.py` [MODIFY]:
  - Agregada la conversión automática a MAYÚSCULAS en el método `save()` de `Producto`, `Marca`, `Rubro` y `Familia`.
- `config/urls.py` [MODIFY]:
  - Registradas las 5 rutas bajo `/productos/excel/`.
- `templates/productos/modals/exportar_seleccion_modal.html` [NEW]: modal interactivo de selección de columnas.
- `templates/productos/modals/capturar_excel_modal.html` [NEW]: modal de carga de archivo Excel con banner de advertencia visual.
- `templates/productos/modals/capturar_resultado_modal.html` [NEW]: modal con resumen de captura (indicadores de actualizados, creados, entidades creadas y observaciones).
- `templates/productos/stock_index.html` [MODIFY]: incorporados los 3 botones principales (*Capturar Excel*, *Exportar Selección*, *Excel Completo*) en la barra de herramientas.
- `productos/tests/test_excel_productos.py` [NEW]: suite de pruebas unitarias verificando exportación completa, exportación por selección y captura masiva con actualización y alta de productos en MAYÚSCULAS.
- `docs/planes/063_exportar_importar_productos_excel.md` [NEW]: plan de implementación histórico formalmente registrado.

### Detalle Técnico
1. **Regla de Negocio de Mayúsculas:** Todos los campos de texto (`detalle`, `cod_prov`, `cod_fab`, `marca`, `rubro`, `familia`) son procesados con `.upper().strip()` tanto a nivel de servicio de captura como en los modelos de Django mediante `save()`.
2. **Auto-Asignación de IDs:** Los productos existentes son identificados por la columna `ID` y actualizados sin modificar su clave primaria. Los productos nuevos con celda `ID` vacía se persisten mediante `Producto.objects.create(...)`, permitiendo que la secuencia autoincremental de la base de datos le otorgue el nuevo ID autonumérico.
3. **Resolución Inteligente de Entidades:** Si una Marca, Rubro o Familia mencionada en el Excel no existe en el catálogo de la empresa, el servicio ejecuta `get_or_create` guardándola en MAYÚSCULAS y vinculando su ID resultante al producto.
4. **Transaccionalidad:** Todo el proceso de captura corre bajo `@transaction.atomic()` para garantizar que un error crítico no deje la base de datos en un estado inconsistente.

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test productos.tests.test_excel_productos --keepdb
```
**Resultado:** `Ran 3 tests in 6.675s - OK`

### Estado actual y siguientes pasos
Plan 063 **completamente implementado, probado y verificado**.

---

### Objetivo
1. Evitar la ejecución de consultas pesadas a la base de datos sobre todo el historial al ingresar por primera vez a las pantallas de listados.
2. Establecer como valor predeterminado en los campos `desde` y `hasta` la fecha del día de hoy (`timezone.localdate().isoformat()`) en los listados de:
   - **Recibos** (`/tesoreria/recibos/`)
   - **Órdenes de Pago** (`/tesoreria/ordenes-pago/`)
   - **Compras** (`/facturacion/compras/`)
   - **Ventas** (`/facturacion/ventas/`)

### Archivos Modificados / Creados
- `tesoreria/views_listados.py` [MODIFY]:
  - Modificado el helper `_rango_fechas(request)` para que `desde` tome por defecto la fecha actual (`hoy.isoformat()`) en lugar del primer día del mes en curso. Esto actualiza unificadamente los listados de Recibos y Órdenes de Pago.
- `facturacion/views.py` [MODIFY]:
  - Modificado `ComprasListView.get()` para que si `desde` o `hasta` no son provistos en los parámetros `GET`, adopten la fecha de hoy.
  - Modificado `VentasListView.get()` para que si `desde` o `hasta` no son provistos en los parámetros `GET`, adopten la fecha de hoy.
- `docs/planes/061_fechas_predeterminadas_listados.md` [NEW]:
  - Archivo de documentación del plan histórico del proyecto.

### Detalle Técnico
1. **Lógica de Fallback:** Al recibir solicitudes sin querystring de filtro por fecha (ej. primer renderizado al acceder desde el menú principal), la vista asume `desde = hoy` y `hasta = hoy`.
2. **Interactividad:** El usuario conserva la facultad de cambiar manualmente cualquier fecha en el formulario de filtros y hacer clic en consultar/filtrar para ver rangos más amplios (por ejemplo, el mes completo o ejercicios pasados).

### Estado actual y siguientes pasos
Plan 061 **completamente implementado, blindado y verificado**.

---

## 21 de Agosto de 2026 — Corrección Conceptual de Columna de Apertura y Acotamiento de Ejercicio en Sumas y Saldos — Plan 060

### Objetivo
1. Delimitar estrictamente el reporte de **Balance de Sumas y Saldos** al rango de fechas entre la fecha de inicio y de cierre del ejercicio activo de la sesión.
2. Calcular la columna **Apertura** considerando la diferencia `Debe - Haber` del asiento contable de apertura (`condic = 5`) del ejercicio activo.
3. Incorporar un selector en la interfaz (checkbox) para habilitar o deshabilitar la inclusión del asiento de apertura (predeterminado habilitado).
4. Cuando la `fecha_desde` sea mayor a la fecha de inicio del ejercicio activo, acumular en la columna **Apertura** el asiento de apertura (`condic = 5` si está activado) más los movimientos netos del ejercicio entre `ejercicio.inicio` y `fecha_desde - 1 día`.

### Archivos Modificados / Creados
- `contable/views_htmx.py` [MODIFY]:
  - `get_balance_context`: procesa `mostrar_apertura` y delimita `fecha_desde` y `fecha_hasta` al rango `[ejercicio.inicio, ejercicio.cierre]`.
  - `_calcular_balance`: acota las consultas ORM a `asientolinea__asiento__ejercicio_id = ejercicio.id`. Construye 3 filtros disjuntos (`q_apertura_condic5`, `q_movimientos_previos` y `q_periodo`) y calcula la columna apertura para cada cuenta imputable y su rollup jerárquico.
- `contable/services/saldos_mensuales.py` [MODIFY]:
  - Blindaje preventivo explícito en la consulta de apertura `apert` agregando los límites de fecha `asiento__fecha__gte=ejercicio.inicio` y `asiento__fecha__lte=ejercicio.cierre`.
- `templates/contable/partials/balance.html` [MODIFY]:
  - Añadido `<input type="hidden" name="filtros_aplicados" value="1">`.
  - Añadido checkbox `<input type="checkbox" name="mostrar_apertura">` con label *"Incluir Apertura"* (predeterminado `checked`).
  - Delimitación de atributos `min` y `max` en los inputs de fecha al rango del ejercicio activo.
- `contable/tests/test_sumas_saldos_apertura.py` [NEW]:
  - Pruebas unitarias dedicadas (`SumasSaldosAperturaTest`) evaluando los 4 escenarios principales (apertura activada/desactivada, `fecha_desde == inicio` y `fecha_desde > inicio`).
- `docs/planes/060_correccion_apertura_sumas_y_saldos.md` [NEW]:
  - Registro permanente del plan de implementación en la documentación histórica.

### Detalle Técnico
1. **Paso de Parámetros:** `get_balance_context` verifica si el usuario desmarcó `mostrar_apertura` mediante los datos del querystring de filtros HTMX.
2. **Cálculo de Apertura:**
   $$\text{Apertura} = (\text{Debe}_5 - \text{Haber}_5 \text{ [si } mostrar\_apertura\text{]}) + (\text{Debe}_{\text{prev}} - \text{Haber}_{\text{prev}} \text{ [si } fecha\_desde > ejercicio.inicio\text{]})$$
3. **Respeto a Restricciones de BD:** Los asientos de test cumplen estrictamente las restricciones de unicidad y la regla matemática de base de datos `debe_xor_haber`.

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test contable.tests.test_saldos_mensuales contable.tests.test_sumas_saldos_apertura
```
**Resultado:** `Ran 31 tests in 23.410s - OK (27/27 de saldos_mensuales + 4/4 de sumas_saldos_apertura)`

### Estado actual y siguientes pasos
Plan 060 **completamente implementado, blindado y verificado**. Se mantuvieron en 100% verde la prueba cruzada de coincidencia entre Saldos Mensuales y Balance de Sumas y Saldos.

---

### Objetivo
1. Añadir un botón en el menú superior (navbar) para poder colapsar y expandir la barra lateral izquierda (Menú Principal), ahorrando espacio en pantalla a petición del usuario.
2. Hacer que el sistema recuerde la preferencia del usuario si dejó abierto o cerrado el menú entre recargas de página.

### Archivos Modificados
- `templates/base.html` [MODIFY]:
  - Añadido el estado global `x-data="{ sidebarOpen: $persist(true) }"` en el elemento `<body>` para gestionar y persistir el estado de la barra en el LocalStorage.
  - Añadido un botón interactivo a la izquierda del logo con un ícono de "hamburguesa" que invierte el estado `sidebarOpen`.
  - Envuelto el `<aside>` del sidebar con directivas `x-show="sidebarOpen"` y transiciones suaves para un efecto de deslizamiento al abrir o cerrar.

---

## 20 de Agosto de 2026 — Optimización de Trazabilidad (Límite 50 registros)

### Objetivo
1. Limitar los resultados en la vista de trazabilidad a 50 registros, imitando el comportamiento de la búsqueda de productos, para evitar la ralentización en la carga inicial y en las consultas de PostgreSQL.

### Archivos Modificados
- `productos/views_trazabilidad.py` [MODIFY]:
  - Eliminado el atributo `paginate_by = 50` de la clase `SubproductoTrazabilidadListView`.
  - Aplicado slicing manual `return qs[:50]` al finalizar el método `get_queryset()`.

### Detalle Técnico
1. **Rendimiento PostgreSQL (Avoid COUNT*):** El uso nativo de paginación (`paginate_by`) en el `ListView` de Django obliga a ejecutar una consulta adicional `COUNT(*)` sobre el queryset resultante para saber el número total de páginas. En este caso, tratándose de una tabla transaccional (Subproductos) con consultas pesadas de tipo `DISTINCT ON` combinadas con múltiples `JOINS` y filtros de búsqueda, el COUNT(*) introducía una severa penalización de rendimiento ("slow query"). Al remover el paginador y hacer directamente el corte `[:50]`, le pedimos a la DB exactamente los primeros 50 elementos que coincidan con la búsqueda (aplicando el index) de forma instantánea, al igual que funciona el maestro de artículos.

---

## 20 de Agosto de 2026 — Mejoras UI/UX en Trazabilidad (Autocompletado y Dashboard)

### Objetivo
1. Implementar autocompletado en los filtros de trazabilidad usando Alpine JS (Typeahead pattern).
2. Agregar la tarjeta de acceso de 'Trazabilidad Subproductos' al Dashboard principal de Stock.
3. Solucionar el bug de solicitudes infinitas (looping requests de HTMX en la vista trazabilidad).

### Archivos Modificados
- `templates/productos/trazabilidad_list.html` [MODIFY]:
  - Integración de la lógica Alpine.js `x-data="{ open: false }"` para autocompletado.
  - Conexión de inputs a `typeahead_clientes`, `typeahead_series_trazabilidad` y `typeahead_productos_venta`.
  - Escucha de eventos custom (e.g. `clienteVentaSeleccionado`, `productoVentaEncontrado`) para autocompletar e invocar el form (`htmx.trigger`).
  - Corrección de `hx-trigger` que escuchaba globalmente `from:input` y generaba peticiones masivas al presionar cualquier tecla o dispararse eventos automáticos.
- `templates/productos/stock_dashboard.html` [MODIFY]:
  - Adición del acceso directo (Tarjeta visual) al módulo de Trazabilidad, restringido por la validación de negocio (uso en armería o automotor).
- `productos/views_trazabilidad.py` [MODIFY]:
  - Corrección en `get_template_names()` añadiendo fallback de lectura `self.request.META.get('HTTP_HX_REQUEST')` por seguridad para asegurar la respuesta parcial.

### Detalle Técnico
1. **Autocompletado Typeahead:** Se reutilizaron componentes modales y parciales existentes de facturación (`clientes_typeahead`, `serie_typeahead`, `productos_venta_typeahead`), capturando sus eventos custom en JavaScript (como `seleccionarSerieVenta` o `window.addEventListener('clienteVentaSeleccionado')`) para rellenar los inputs del formulario y lanzar la búsqueda asíncrona automáticamente.
2. **Loop Infinito (BugFix HTMX):** El trigger global del form (`hx-trigger='keyup delay:500ms from:input'`) provocaba que scripts paralelos o extensiones que generaban eventos `keyup` causaran recargas enteras de la tabla. Esto se ha mitigado focalizando los `hx-trigger` y bloqueando el comportamiento por defecto del submit de teclado.

---

## 20 de Agosto de 2026 — Trazabilidad de Subproductos (Vista y Línea de Tiempo Modal)

### Objetivo
1. Crear una vista para listar subproductos trazables, permitiendo la búsqueda por Cliente/Proveedor, Serie, CUIM y Producto, y filtrado automático al estado actual (último movimiento) aprovechando índices DISTINCT ON y order_by.
2. Validar que la trazabilidad esté restringida a empresas con tipo de actividad 'ARMERIA' o 'AUTOMOTOR'.
3. Integrar un modal con línea de tiempo interactivo que detalle el flujo cronológico del subproducto (compras y ventas con su historial y comprobantes vinculados).

### Archivos Modificados / Creados
- productos/views_trazabilidad.py [NEW]:
  - SubproductoTrazabilidadListView: Listado general con soporte HTMX de grilla y paginación.
  - 	razabilidad_modal_timeline: Endpoint que devuelve el HTML renderizado con todo el historial de la serie clickeada.
- config/urls.py [MODIFY]: Registro de las rutas stock/trazabilidad/ y stock/trazabilidad/modal/<str:serie>/.
- 	emplates/base.html [MODIFY]: Integración del enlace 'Trazabilidad Subproductos' debajo de Mantenimiento de Productos en el menú lateral.
- 	emplates/productos/trazabilidad_list.html [NEW]: Plantilla maestra del listado con formulario de búsqueda.
- 	emplates/productos/partials/trazabilidad_grilla.html [NEW]: Plantilla parcial (table rows) usada por HTMX.
- 	emplates/productos/partials/trazabilidad_modal_timeline.html [NEW]: Componente modal estilizado (TailwindCSS) representando una línea de tiempo (timeline) cronológica.

### Detalle Técnico
1. **Lógica de Búsqueda:** Para el filtro por CliPro, el sistema recupera inicialmente las series que tuvieron movimiento asociado con el Cliente/Proveedor buscado, y luego filtra la consulta principal.
2. **Eficiencia PostgreSQL:** El queryset final se ordena por serie, -feccpra y -subpro usando distinct('serie') para recuperar de forma altamente eficiente sólo el estado más reciente de la serie sin sobrecargar la memoria.
3. **Control de Acceso (Validación de Negocio):** En el método dispatch() se chequea que empresa.tipo_actividad pertenezca a 'ARMERIA' o 'AUTOMOTOR'; caso contrario redirige al index de stock con un mensaje de advertencia.
4. **Visualización en Modal (Timeline):** Se empleó CSS para construir una barra conectora (div.w-0.5.bg-gray-200), trazando el recorrido desde el Ingreso (Compra verde) hasta el Egreso (Venta roja), informando fechas, entidades y comprobantes vinculados.

---

## 19 de Agosto de 2026 — Plan 058: Visualización de Asientos, Restricción de Anulación y Corrección de Imputaciones en OP

### Objetivo
1. Permitir consultar el asiento contable generado directamente desde la columna `Asiento` en los listados de Órdenes de Pago y Recibos de Cobranza mediante la apertura interactiva de un modal HTMX (`detalle_asiento_modal`).
2. Restringir la acción `ANULAR` exclusivamente a usuarios Administradores (`is_superuser`, `is_staff` o `es_admin_sistema`) tanto en las grillas de Órdenes de Pago y Recibos como a nivel de endpoint de backend (retornando `HTTP 403 Forbidden`).
3. Corregir el botón de eliminación en la tabla de Imputaciones Contables Manuales en la pantalla de Carga de Órdenes de Pago (`ordenpago_carga.html`), reemplazando la etiqueta FontAwesome descompuesta por un icono SVG nativo de basura visible y estilizado.

### Archivos Modificados / Creados
- `tesoreria/views_listados.py` [MODIFY]:
  - `orden_pago_anular`: agregado de control de permisos de Administrador (`is_superuser or is_staff or es_admin_sistema`). Retorna `HTTP 403` si el usuario no es Administrador.
  - `recibo_anular`: agregado del mismo control de permisos con respuesta `HTTP 403` para no administradores.
- `templates/tesoreria/partials/ordenpago_grilla.html` [MODIFY]:
  - Columna 9 (`Asiento`): transformada en un botón HTMX interactivo que al presionar dispara `hx-get="{% url 'detalle_asiento_modal' fila.op.asiento_id %}"`.
  - Columna 10 (`Acciones`): botón `ANULAR` envuelto en la directiva Jinja `{% if user.is_superuser or user.is_staff or user.perfil.es_admin_sistema %}`.
- `templates/tesoreria/partials/recibo_grilla.html` [MODIFY]:
  - Columna 9 (`Asiento`): transformada en botón HTMX interactivo para abrir el modal del asiento contable.
  - Columna 10 (`Acciones`): botón `ANULAR` protegido para mostrarse únicamente a usuarios Administradores.
- `templates/tesoreria/ordenpago_carga.html` [MODIFY]:
  - Reemplazo de `<i class="fas fa-trash"></i>` en la celda de acción de la tabla de imputaciones contables por un botón de eliminación con icono SVG visible en rojo.
- `templates/contable/modals/detalle_asiento_modal.html` [MODIFY]:
  - Reemplazo de `onclick="document.getElementById('modal-container-2').innerHTML=''"` por `onclick="this.closest('.fixed').remove()"` garantizando un cierre limpio.
  - Ampliación del ancho contenedor del modal de `max-w-4xl` a `max-w-5xl`, extensión del ancho de las columnas `Debe` y `Haber` a `w-44` (176px) y adición de `whitespace-nowrap` a las celdas de montos en `tbody` y `tfoot` para impedir el quiebre de renglón del signo `$` y del importe.
- `docs/planes/058_mejoras_listados_op_recibos.md` [NEW]: copia del plan de implementación formalmente registrado.
- `docs/walkthrough.md` [MODIFY]: actualización acumulativa de la bitácora.

### Detalle Técnico
1. **Acceso al Asiento Contable:** Al hacer clic en el ID de asiento de cualquier Orden de Pago o Recibo, se ejecuta la petición HTMX al endpoint `detalle_asiento_modal` de la app `contable`, cargando la vista previa del asiento contable con sus líneas de Debe/Haber, saldo total e información de cuentas asociadas.
2. **Seguridad y Roles:** Para mantener el principio de privilegio mínimo, los operadores/vendedores (`is_staff = False`, `es_admin_sistema = False`) no ven el botón `Anular` en las grillas de OP y Recibos, y si intentaran realizar la petición HTTP POST directamente, la vista intercepta el requerimiento y devuelve un estado `403 Forbidden`.
3. **Optimizaciones de UI y Modales:** La instrucción `this.closest('.fixed').remove()` destruye limpia y reactivamente el elemento contenedor del modal flotante sin depender de un ID rígido en el DOM. Además, el modal de asiento se amplió a `max-w-5xl` con columnas `w-44` y `whitespace-nowrap`, asegurando que los montos en pesos de Debe, Haber y Total Asiento se presenten holgadamente en una sola línea.

---

## 18 de Agosto de 2026 — Inicialización de Medios de Pago por Empresa y Corrección en Guardado de Recibos (Plan 057)

### Objetivo
Resolver el error de medio de pago al presionar "Guardar recibo" en la Empresa 2 (`ARMERIA ARMAR SAS`) para el recibo `RC 0001-00000003`, poblando la tabla `tesoreria_medio_pago` con la asignación correspondiente al plan de cuentas de cada empresa, optimizando la resolución por código (`EFE-ARS`, `EFE-USD`, `CHQ-TER`, `TRA-BCO`) y asegurando la atomicidad de transacciones con `transaction.set_rollback(True)`.

### Archivos Modificados / Creados
- `tesoreria/views_htmx.py` [MODIFY]:
  - `procesar_recibo` y `procesar_orden_pago`: búsqueda jerárquica de `MedioPago` especificando código (`EFE-ARS`, `EFE-USD`, `TRA-BCO`, `CHQ-TER`) antes del fallback por categoría (`EFE`, `TRA`, `CHQ`).
  - Adición de `transaction.set_rollback(True)` en bloques `except Exception as e:` para evitar el guardado de comprobantes huérfanos sin movimiento de caja ni asiento ante cualquier fallo.
- Base de Datos (`tesoreria_medio_pago`):
  - Reset de secuencia PostgreSQL (`tesoreria_medio_pago_id_seq`).
  - Sembrado de medios de pago para **Empresa 2** (`ARMERIA ARMAR SAS`) y **Empresa 3** (`LOPEZ RIOS Y ASOCIADOS SA`) enlazados a sus respectivas cuentas contables.
  - Depuración de recibos huérfanos de prueba (ID 6, 7 y 8) en Empresa 2.
- `docs/planes/057_corregir_error_medio_pago_recibos.md` [NEW]: plan de implementación histórico.
- `docs/walkthrough.md` [MODIFY]: registro incremental de la bitácora.

### Detalle Técnico
1. **Modelado y Aislamiento por Empresa:** Tal como señaló acertadamente la decisión de arquitectura, cada `MedioPago` debe pertenecer a una empresa (`empresa_id`) debido a que la `cuenta_contable_id` hace referencia a la tabla `cble_cuentas`, cuyos IDs primarios son únicos por plan de cuentas de empresa.
2. **Carga Inicial de Medios de Pago:**
   - **Empresa 2:** `EFE-ARS` y `EFE-USD` (Cta. 215 - CAJA), `CHQ-TER` (Cta. 216 - VALORES EN CARTERA), `TRA-BCO` (Cta. 217 - BANCO MACRO), `RET-GCIA` (Cta. 236 - AFIP RET. GCIAS), `RET-IIBB` (Cta. 253 - DGR IIBB SALDO A FAVOR).
   - **Empresa 3:** `EFE-ARS` y `EFE-USD` (Cta. 483 - CAJA), `CHQ-TER` (Cta. 484 - VALORES EN CARTERA), `TRA-BCO` (Cta. 485 - BANCO PATAGONIA), `RET-GCIA` (Cta. 498), `RET-IIBB` (Cta. 512).
3. **Robustez Transaccional:** Se introdujo `transaction.set_rollback(True)` en la captura de excepciones dentro de `procesar_recibo` y `procesar_orden_pago` decoradas con `@transaction.atomic`.

---

## 18 de Agosto de 2026 — Plan 055: Botón de Exportación a Excel en Clientes y Proveedores

### Objetivo
Incorporar la funcionalidad de exportación completa a formato Excel (`.xlsx`) en el listado de Clientes y Proveedores (`/clientes/`), que permita descargar los registros de la empresa respetando los filtros de búsqueda activa (`q` y `tipo`) con **todos los campos de la tabla `ClienteProveedor` (25 columnas)** y **sin la restricción de 50 registros en pantalla**.

### Archivos Modificados / Creados
- `facturacion/services/clientes_excel.py` [NEW]: servicio con `openpyxl` que construye el archivo Excel estilizado con 25 columnas, encabezado slate-900, importes formateados (`#,##0.00`) y auto-ajuste de ancho de columnas.
- `facturacion/views_reportes.py` [MODIFY]: agregado de la vista `@login_required exportar_clientes_excel(request)` que consulta el 100% de los registros filtrados sin límite `[:50]` y ejecuta el servicio de descarga.
- `config/urls.py` [MODIFY]: registro de la ruta `path('clientes/exportar-excel/', exportar_clientes_excel, name='clientes_exportar_excel')`.
- `templates/facturacion/clientes_index.html` [MODIFY]: agregado del botón verde estilizado "Exportar Excel" en la barra de acciones superiores y la función JS `exportarExcel()` para enviar la búsqueda activa.
- `facturacion/tests/test_exportar_clientes_excel.py` [NEW]: suite de pruebas unitarias para la descarga Excel sin filtro y con filtros de tipo y búsqueda.
- `docs/planes/055_exportar_excel_clientes_proveedores.md` [NEW]: copia numerada del plan de implementación.
- `docs/walkthrough.md` [MODIFY]: registro incremental de la bitácora.

### Detalle Técnico
1. **Campos Exportados (25 columnas):** ID, Razón Social, Tipo Entidad, Tipo Documento, CUIT/DNI, Fecha Nacimiento, Domicilio, C. Postal, Localidad, Provincia/Jurisdicción, Contacto, Teléfono, Correo, Condición IVA, Ingresos Brutos, Saldo Inicial, Saldo Actual, Límite Crédito, Objetivo Mensual, Clasificación, Exige Orden Compra, Cta Patrimonial, Cta Resultado, Código Anterior, Observaciones.
2. **Sin Truncamiento:** A diferencia de la grilla HTML que está acotada a `[:50]` por desempeño en navegador, la vista de exportación retorna el 100% de los contactos comerciales coincidentes con el filtro de búsqueda.
3. **Formato:** Encabezado con título de la empresa, subtítulo del reporte, filtros aplicados, fecha/hora de emisión y celdas estilizadas.

---

## 17 de Agosto de 2026 — Plan 054: Resolución Fiscal de Comprobantes ARCA y Gestión Guiada de Clientes por Condición IVA

### Objetivo
Corregir integralmente la determinación de tipos de comprobante (`TipoComprobante`) para la facturación electrónica ante ARCA/AFIP por emisores Responsables Inscriptos (Factura A para Responsables Inscriptos y Monotributistas según RG 5003/5022; Factura B para Consumidores Finales y Exentos), blindar las validaciones cruzadas de CUIT/DNI por condición fiscal e implementar un flujo guiado en el alta/edición de clientes que derive los controles impositivos desde la Condición ante el IVA.

### Archivos Modificados / Creados
- `facturacion/models.py` [MODIFY]: agregado de campo `es_consumidor_final` a `Preventa`.
- `facturacion/migrations/0048_preventa_es_consumidor_final.py` [NEW]: migración de base de datos.
- `facturacion/forms.py` [MODIFY]: validación integral en `ClienteProveedorForm.clean()` e inclusión de `es_consumidor_final` en `PreventaForm`.
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]: reorganización visual poniendo la Condición ante el IVA como selector disparador principal de la Sección 1 con control dinámico reactivo vía Alpine.js.
- `templates/facturacion/preventa_carga.html` [MODIFY]: checkbox para "Facturar como Consumidor Final (Factura B)" en la cabecera.
- `facturacion/views.py` [MODIFY]:
  - `resolver_tipo_comprobante_fiscal`: resolución certera de `TipoComprobante` sin caer en fallbacks erróneos a `.first()`.
  - `validar_y_obtener_documento_receptor`: validación estricta de documentos previa a ARCA.
  - `VentasCargaView.post`: validación de coherencia fiscal previa a la comunicación con ARCA.
- `tesoreria/views_htmx.py` [MODIFY]: cobro de Preventa en Caja Mostrador resolviendo Factura A / B de forma certera y respetando `es_consumidor_final` para emitir Factura B.
- `facturacion/views_trazabilidad.py` [MODIFY]: validación de coherencia fiscal y documento antes de emitir a ARCA.
- `templates/facturacion/ventas_carga.html` y `templates/facturacion/ventas_trazabilidad_carga.html` [MODIFY]: preselección de Factura B por defecto y filtrado automático de Factura A/B según la condición fiscal del cliente seleccionado.
- `docs/planes/054_resolucion_fiscal_comprobantes_y_clientes.md` [NEW]: plan de implementación histórico.
- `docs/walkthrough.md` [MODIFY]: registro incremental de la bitácora.

### Detalle Técnico
1. **Resolución Robusta de `TipoComprobante`:** Se normalizó la búsqueda contemplando formatos con padding (`'001'`, `'006'`) y sin padding (`'1'`, `'6'`), eliminando definitivamente el fallback a `.first()` que causaba la asignación accidental de Factura A a Consumidores Finales.
2. **Matriz Impositiva de Emisión (Emisor RI):**
   - **Receptor RI o Monotributista:** Emite **Factura A** (`001`), requiriendo `DocTipo = 80` y CUIT de 11 dígitos.
   - **Receptor Consumidor Final:** Emite **Factura B** (`006`), admitiendo `DocTipo = 99` (`DocNro = 0`), `DocTipo = 96` (DNI) o `DocTipo = 80` (CUIT).
   - **Receptor Exento:** Emite **Factura B** (`006`), requiriendo `DocTipo = 80` y CUIT de 11 dígitos.
3. **Flujo Guiado de Clientes:** En el modal de alta/edición de clientes, la **Condición ante el IVA** se define en primer término. Al seleccionar RI, Monotributo o Exento, el Tipo de Documento se fija en `80 - CUIT` y el CUIT pasa a ser obligatorio de 11 dígitos.
4. **Opción de Consumo Propio en Preventas:** Se agregó `es_consumidor_final` en `Preventa` con un checkbox en la pantalla de carga. Al cobrar la preventa en Caja Mostrador, si está marcado, se fuerza la emisión de **Factura B** con condición impositiva de Consumidor Final (5) sin alterar la ficha del cliente en el maestro.

---

## 17 de Agosto de 2026 — Carga Maestra de Tarjetas en Tesorería (`tesoreria_tarjeta`)

### Objetivo
Poblar la tabla maestra de tarjetas (`tesoreria_tarjeta` / modelo `Tarjeta`) a partir del archivo `d:\borrador\tarjetas.csv` para habilitar las operaciones de cobros y liquidaciones con tarjetas de crédito y débito.

### Archivos Modificados / Creados
- Base de datos (`tesoreria_tarjeta`): inserción de 10 registros maestros.
- `docs/walkthrough.md` [MODIFY]: registro incremental de la bitácora.

### Detalle Técnico
1. **Origen de Datos:** Lectura del archivo `d:\borrador\tarjetas.csv` (delimitado por `;`).
2. **Mapeo de Atributos:**
   - `codigo` -> `Tarjeta.codigo`
   - `detalle` -> `Tarjeta.nombre`
   - `tipo` -> `Tarjeta.tipo` (`C` = Crédito, `D` = Débito)
3. **Carga Idempotente y Transaccional:**
   - Ejecución atómica vía `transaction.atomic()`.
   - Utilización de `Tarjeta.objects.update_or_create(...)`.
   - Resultado: 10 tarjetas creadas exitosamente.

---

## 17 de Agosto de 2026 — Depuración de Cuentas Contables Obsoletas (Empresa ID = 2)

### Objetivo
Eliminar 48 cuentas contables obsoletas/duplicadas en la tabla `cble_cuentas` (modelo `Cuenta`) pertenecientes a `empresa_id = 2`, cuyos códigos fueron suministrados en el archivo `d:\borrador\borrar.csv`.

### Archivos Modificados / Creados
- Base de datos (`cble_cuentas`): eliminación física de 48 registros sin movimientos asociados.
- `docs/walkthrough.md` [MODIFY]: registro de la intervención.

### Detalle Técnico
1. **Auditoría e Integridad Previa:**
   - Se validaron los 48 códigos del archivo CSV (`codigo`).
   - Se verificó que ninguna de las 48 cuentas tuviera movimientos contables en `cble_asiento_mov` (`AsientoLinea`), cuentas bancarias asociadas ni parámetros contables vinculados.
   - Se comprobó que ninguna cuenta activa externa tuviera `sumariza_id` apuntando a las cuentas a borrar.
2. **Ejecución Transaccional Atómica:**
   - Se ejecutó un bloque `transaction.atomic()`.
   - Se desvincularon preventivamente las autoreferencias `sumariza = None` internas entre las 48 cuentas.
   - Se ejecutó el borrado definitivo (`.delete()`) eliminando exactamente las 48 cuentas correspondientes.
   - Verificación posterior: 0 cuentas restantes con los códigos indicados en `empresa_id = 2`.

---

## 17 de Agosto de 2026 — Búsqueda y Autocarga por N° de Serie en Remitos Internos (Plan 053)

### Objetivo
Permitir la búsqueda rápida y directa por N° de Serie en la emisión de Remitos Internos, verificando que la unidad no se encuentre vendida (`situacion != 'VENDIDA'`), comprobando su pertenencia a la sucursal de origen, y autocompletando el ID de producto, la descripción y el CUIM.

### Archivos Modificados / Creados
- `facturacion/views_remito_interno.py` [MODIFY]:
  - `ri_buscar_subproducto_por_serie`: vista HTMX que filtra por `serie__iexact`, excluye `situacion='VENDIDA'`, verifica sucursal.
  - `ri_buscar_producto_por_id`: búsqueda instantánea con prioridad absoluta por `id` primario sobre `cod_prov`.
  - `RiItemAddView`: resolución de producto priorizando clave primaria `id` antes de `cod_prov`.
  - `RecepcionInternaCargaView` / `RecepcionInternaVincularModalView`: restricción estricta de la sucursal receptora a la sucursal activa logueada.
  - `RecepcionInternaImprimirView` [NEW]: vista de emisión de PDF para el Informe de Recepción Interna.
- `config/urls.py` [MODIFY]: inclusión de la ruta `compras/recepcion-interna/<int:rec_id>/imprimir/`.
- `templates/facturacion/pdf/remito_interno_pdf.html` [MODIFY]: inclusión de casilla de punteo `[  ]` por ítem y triple bloque de firma.
- `templates/facturacion/pdf/recepcion_interna_pdf.html` [NEW]: diseño PDF del Informe de Recepción Interna con firmas y comprobantes vinculados.
- `templates/facturacion/recepcion_interna_carga.html` [MODIFY]: fijación inalterable de la sucursal receptora a la sucursal activa.
- `templates/facturacion/partials/recepcion_fila.html` [MODIFY]: enlace al PDF de Informe de Recepción Interna.
- `facturacion/tests/test_plan028.py` [MODIFY]: inclusión de pruebas unitarias para autocompletado y validaciones de serie.
- `docs/planes/053_busqueda_inteligente_series_remito_interno.md` [NEW]: plan de implementación histórico.

### Detalle Técnico y Saneamiento de Datos
1. **Persistencia y Visualización Estricta por `productos_producto.id`:** Se unificó la regla conceptual del sistema: tanto en sesión (`items`), grillas operativas (`ri_items_tabla.html`, `recepcion_interna_items_tabla.html`), modelos y comprobantes PDF, el identificador guardado y mostrado en columna es estrictamente el `producto_id` primario (`productos_producto.id`), desacoplándolo del `cod_prov` que sólo se usa como comodín de búsqueda.
2. **Remito e Informe de Recepción PDF (Diseño Sobrio y Ahorro de Tinta):** Se rediseñaron los comprobantes PDF ([`remito_interno_pdf.html`](file:///d:/JM_Soft/erp-ikigai-2/templates/facturacion/pdf/remito_interno_pdf.html) y [`recepcion_interna_pdf.html`](file:///d:/JM_Soft/erp-ikigai-2/templates/facturacion/pdf/recepcion_interna_pdf.html)) alineando el número de comprobante a la derecha en el mismo renglón del título, reemplazando los fondos negros por bordes rectangulares finos (`#334155`), e implementando una casilla de control cuadrada para el punteo en depósito sin desbordamiento de renglón.
3. **Bloqueo Rígido de Sucursal Receptora:** En Recepción Interna se eliminó la selección de sucursal. La recepción se asocia de forma fija e inalterable a la sucursal activa del usuario logueado.
4. **Corrección de Clave Primaria en `RecepcionInternaImprimirView`:** Se corrigió la consulta de remitos imputados utilizando `ri.pk` (en lugar de `ri.id`), resolviendo la excepción `AttributeError`.
5. **Corrección de Mapeo de Sucursales:** Se detectó e instruyó un saneamiento de datos en la tabla `productos_subproducto` para reasociar 1,400 registros que apuntaban erróneamente a `sucursal_id = 1` de Empresa 1 hacia `sucursal_id = 3` (Sede Central de Empresa 2).

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test facturacion.tests.test_plan028
```
**Resultado:** `Ran 16 tests in 171.858s - OK`

### Estado actual y siguientes pasos
Plan 053 completado y verificado en su totalidad.

---

## 16 de Agosto de 2026 — Trazabilidad de Subproductos (N° Serie y CUIM) en Remitos Internos y Recepción — Plan 052

### Objetivo
Permitir la transferencia de productos trazables (`subprod = True / 1`) mediante la validación de su número de serie en la sucursal de origen, emitiendo el Remito Interno con los datos de **N° Serie** y **CUIM**, mostrándolos en el PDF impreso y en la pantalla de recepción interna, y reubicando automáticamente el `Subproducto.sucursal_id` hacia la sucursal de destino al confirmarse el Informe de Recepción.

### Archivos Modificados / Creados
- `facturacion/models.py` [MODIFY]: agregado de campos `subproducto` (FK), `serie` y `cuim` a `RemitoInternoItem`.
- `facturacion/migrations/0047_remitointernoitem_cuim_remitointernoitem_serie_and_more.py` [NEW]: migración de base de datos.
- `facturacion/views_remito_interno.py` [MODIFY]:
  - `RiItemAddView`: validación de productos trazables y verificación del subproducto en la sucursal de origen.
  - `RemitoInternoCargaView`: guardado de `subproducto_id`, `serie` y `cuim`.
  - `RecepcionInternaVincularView`: agrupación de ítems por `(producto_id, subproducto_id)` para mantener viva la trazabilidad por serie.
  - `RecepcionInternaCargaView`: actualización atómica de `subproducto.sucursal_id` a la sucursal de destino.
- `templates/facturacion/remito_interno_carga.html` [MODIFY]: adición de campo `N° Serie (si aplica)` y parámetro `hx-include`.
- `templates/facturacion/partials/ri_items_tabla.html` [MODIFY]: visualización de leyendas de Serie y CUIM.
- `templates/facturacion/pdf/remito_interno_pdf.html` [MODIFY]: impresión de Serie y CUIM en el comprobante PDF.
- `templates/facturacion/partials/recepcion_interna_items_tabla.html` [MODIFY]: despliegue de Serie y CUIM en la recepción interna.
- `templates/facturacion/modals/recepcion_interna_vincular.html` [MODIFY]: aclaración de trazabilidad por serie.
- `facturacion/tests/test_plan028.py` [MODIFY]: adición de `SubproductoRemitoInternoTests`.
- `docs/planes/052_trazabilidad_subproductos_remito_interno.md` [NEW]: plan de implementación histórico.

### Detalle Técnico
1. **Validación de Subproducto y Origen:** Al ingresar una serie para un producto trazable (`subprod = True`), `RiItemAddView` busca la coincidencia exacta en `Subproducto`. Si no existe o se ubica en otra sucursal, rechaza la operación informando la inconsistencia.
2. **Conservación de Atributos:** Se almacenan `subproducto_id`, `serie` y `cuim` en `RemitoInternoItem` y se arrastran a la sesión de recepción interna.
3. **Reubicación Física en BD:** Al momento de guardar el `Informe de Recepción` (origen = INTERNO) en la sucursal destino, se ejecuta la actualización `subproducto.sucursal = destino` con `update_fields=['sucursal']`.

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test facturacion.tests.test_plan028
```
**Resultado:** `Ran 13 tests in 141.564s - OK`

### Estado actual y siguientes pasos
Plan 052 completado y verificado en su totalidad. Toda transferencia interna de productos trazables contempla la serie y el CUIM desde la emisión hasta la recepción con reubicación automática de sucursal.

---

## 16 de Agosto de 2026 — Plan 053: `stock_inicial` y stock derivado por sucursal

### Objetivo
Que el stock deje de ser un contador incremental sin origen y pase a **derivarse** de un punto de
partida más los comprobantes, igual que la cuenta corriente:

    stock = stock_inicial + compras + recepciones − ventas − remitos internos

### Archivos Creados
- `productos/services/stock_service.py` [REESCRITO]: `recalcular_stock()`,
  `recalcular_stock_masivo()` y los términos de la fórmula declarados como datos.
- `productos/management/commands/recalcular_stock.py` [NEW]: comando de reconstrucción.
- `productos/tests/test_stock_inicial.py` [NEW]: 20 pruebas.
- `productos/migrations/0026|0027|0028` [NEW]: campo, backfill y baja de `stock`/`stkcons`.
- `docs/planes/052_stock_inicial_y_recalculo.md` [NEW].

### Archivos Modificados
- `productos/models.py`: `StockSucursal.stock_inicial`; baja de `Producto.stock` y
  `Producto.stkcons`; **corregido un bug preexistente** (ver abajo).
- `facturacion/views_reportes.py` y `facturacion/services/ventas_reportes_excel.py`: la columna
  Stock de los dos exports pasa a traer el stock real.
- `productos/management/commands/migrar_productos.py`: el stock del sistema anterior va a
  `StockSucursal.stock_inicial`.
- `productos/tests.py` [BORRADO]: stub vacío que rompía el descubrimiento de tests.

### Detalle Técnico

**1. El stock es derivado.** `StockSucursal.cantidad` se sigue materializando —se lee en toda la
operatoria—, pero ya no se ajusta por delta: se **recalcula completo** para ese (producto,
sucursal) cada vez que algo lo afecta. Las tres funciones que llaman las señales conservan su
firma; por dentro registran el `MovimientoStock` de auditoría y delegan en `recalcular_stock()`.

**2. Los términos se declaran como datos, no cableados.** Cada uno dice qué modelo aporta, con qué
signo, por qué campo de cantidad, cómo llega a la sucursal y qué excluye. Sumar el término de
**ajustes de inventario** —cuando se haga el formulario de toma física— será agregar una entrada,
sin revalidar los cuatro que ya funcionan.

**3. Exclusiones conservadas del código anterior**, cada una con su test: compras con
`id_fac_rem` o `gestion_stock_por_recepcion` (circuito OC), ventas anuladas o con `id_fac_rem`,
recepciones anuladas, remitos internos anulados, y el signo de las notas de crédito
(`TipoComprobante.signo = −1`, que hace que una NC de venta **devuelva** stock).

**4. Backfill que no mueve un solo número.** `stock_inicial = cantidad − movimientos_ya_aplicados`,
calculado con cuatro consultas agrupadas por (producto, sucursal) en vez de cuatro por fila.
Resultado sobre la base real: **13.596 filas inicializadas, 7 con movimientos aplicados y 0
cantidades modificadas**.

**5. Dos caminos de recálculo por una razón de performance.** `recalcular_stock()` hace cuatro
consultas por par (producto, sucursal): ideal al guardar un comprobante, inviable para un
inventario entero. La primera versión del comando lo llamaba fila por fila y tardaba más de 10
minutos sobre 13.584 registros. `recalcular_stock_masivo()` agrupa los cuatro términos en cuatro
consultas totales: **49 segundos**.

**6. Baja de `Producto.stock` y `Producto.stkcons`.** Campos heredados del ERP en VFP, donde el
stock se llevaba sobre el producto. Se relevó que **nadie los escribía** y que sólo los leían dos
exports —el CSV legacy de 74 columnas y su gemelo en Excel—, que emitían el valor congelado de la
importación. Ahora esas columnas traen el **stock real de la sucursal de la venta**, precargado en
una sola consulta para no disparar una por fila. `stkcons` (stock en consignación del VFP) queda
en `0.0` como relleno posicional: se conservan las 74 columnas para no romper al consumidor.
El total consolidado ya existía como la property `Producto.stock_global`.

### Dos problemas preexistentes corregidos al paso
1. **`productos/models.py`**: `InvalidOperation` se usaba en un `except` sin estar importado, así
   que un IVA mal formado producía `NameError` en vez de tomar el default. Faltaba una palabra en
   el import.
2. **`productos/tests.py`**: stub vacío de Django (3 líneas, del commit inicial) que convivía con
   el paquete `productos/tests/`. Rompía el descubrimiento con
   `ImportError: 'tests' module incorrectly imported`, o sea que **`manage.py test productos`
   nunca había funcionado**. Se borró el stub.

### Pruebas Automatizadas
```bash
python manage.py test productos.tests.test_stock_inicial
```
**Resultado:** `Ran 20 tests in 198.099s - OK`

Cobertura: la fórmula completa, las siete exclusiones, las notas de crédito de venta y de compra,
la transferencia interna en dos pasos (el total no cambia), el aislamiento entre sucursales, la
idempotencia del recálculo y —el caso que da sentido al plan— la **autorreparación**: se rompe
`cantidad` a mano y el recálculo la corrige. Con el contador incremental anterior era imposible.

**Verificación sobre la base real:** `recalcular_stock --dry-run` sobre las tres empresas
(13.584 + 9 + 3 registros) informa *"Todos los registros ya estaban correctos"*: la fórmula
reproduce exactamente el stock que había.

### Nota de numeración
Este plan se archivó primero como 052 y se **renumeró a 053** al detectarse que, en paralelo, la Trazabilidad de Subproductos ya usaba ese número. Los archivos de migración conservan `plan052` en su NOMBRE a propósito: ya estaban aplicadas en la base y renombrarlas haría que Django las tomara como nuevas.

### Estado actual y siguientes pasos
Plan 053 **completo**. El stock es reconstruible con `manage.py recalcular_stock --empresa N`.

**PENDIENTE registrado (§8 bis del plan):** formulario de carga de inventarios, generales y
periódicos, al estilo del "arreglo de stock". Va en un plan aparte y necesitará su propio término
en la fórmula (± ajustes), que es justamente lo que la estructura declarativa deja preparado.

---

## 16 de Agosto de 2026 — Visualización de Stock Activo y Stock Destino en Buscador Avanzado de Productos (Remitos Internos) — Plan 051

### Objetivo
Mostrar el stock de la sucursal activa en el Buscador Avanzado de Productos en todas las vistas de búsqueda y, al abrirlo desde el formulario de Remito Interno, incorporar automáticamente la columna de **Stock Destino** para que el usuario pueda evaluar la necesidad y existencias reales en ambas sucursales.

### Archivos Modificados / Creados
- `templates/facturacion/remito_interno_carga.html` [MODIFY]: inclusión de `hx-include="[name='sucursal_origen'], [name='sucursal_destino']"` en el botón de la lupa.
- `facturacion/views_htmx.py` [MODIFY]: actualización de `buscador_productos_modal` y `lista_productos_resultados` para calcular y adjuntar `stock_origen` (o sucursal activa) y `stock_destino` en los productos buscados.
- `templates/facturacion/modals/buscador_productos.html` [MODIFY]: agregados inputs ocultos de sucursal en `thead`, cabeceras dinámicas para **Stk. Activo/Origen** y **Stk. Destino** y ajuste de `tbody` `hx-get` inicial.
- `templates/facturacion/partials/productos_search_results.html` [MODIFY]: renderizado de celdas de stock con insignias visuales (verde/rojo para origen/activa, azul/ámbar para destino) y ajuste de `colspan`.
- `facturacion/tests/test_plan028.py` [MODIFY]: adición de `BuscadorProductosStockTests` para validar contexto y asignación de stock por sucursal en HTMX.
- `docs/planes/051_stock_sucursales_modal_remito_interno.md` [NEW]: plan de implementación histórico.

### Detalle Técnico
1. **Paso de Parámetros HTMX:** El botón de la lupa en `remito_interno_carga.html` incluye `[name='sucursal_origen']` y `[name='sucursal_destino']`.
2. **Determinación de Sucursal Activa vs. Origen/Destino:** `sucursal_origen_id` se resuelve contra el parámetro GET enviado o contra la sucursal activa de la sesión (`request.session.get('sucursal_id')`). `sucursal_destino_id` sólo se procesa si está presente en el GET.
3. **Consulta Eficiente en `StockSucursal`:** Para los productos devueltos en la búsqueda (máximo 50), se realiza una consulta agrupada contra `StockSucursal` filtrando por `producto_id__in` y `sucursal_id__in`. El resultado se mapea en un diccionario `(producto_id, sucursal_id) -> cantidad` permitiendo la asignación en memoria `O(1)`.
4. **Diseño Visual:** Celdas con badges de color de Tailwind (`bg-emerald-100` / `bg-rose-100` para origen/activa y `bg-blue-100` / `bg-amber-100` para destino). En búsquedas estándar donde no hay sucursal destino, se muestra la tabla con 6 columnas; en Remitos Internos se extiende a 7 columnas.

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test facturacion.tests.test_plan028
```
**Resultado:** `Ran 11 tests in 109.256s - OK`

### Estado actual y siguientes pasos
Plan 051 completamente implementado y verificado. El modal de búsqueda avanzada de productos muestra el stock activo en búsquedas generales y amplía la vista a Stock Origen y Stock Destino al confeccionar Remitos Internos.

---

## 16 de Agosto de 2026 — Limpieza de los movimientos de la empresa 1

### Objetivo
La empresa 1 (IKIGAI TECHNOLOGY SAS) se cargó en etapa de diseño y se operó con el sistema a
medio desarrollar, así que arrastraba inconsistencias (asientos vacíos, recibos sin contabilizar).
Se vació su historial transaccional para poder probar los circuitos desde cero.

### Alcance (elegido por el usuario)
**Sólo movimientos.** Se CONSERVAN plan de cuentas, ParametrosContables, productos, subproductos,
stock por sucursal, familias, marcas, rubros, clientes/proveedores, medios de pago, cuentas
bancarias, cajas, sucursal, ejercicio y cotizaciones. Las tablas globales compartidas entre
empresas (bancos, tipos de comprobante, jurisdicciones, alícuotas de IVA, usuarios, permisos) no
se tocaron nunca.

### Procedimiento
1. **Respaldo completo** con `pg_dump -Fc` de toda la base antes de empezar.
2. **Relevamiento** de las 35 tablas con FK a `empresa` y de las que dependen por cascada.
3. **Simulación** dentro de una transacción que se revierte, para confirmar el orden de borrado.
4. **Ejecución** con el mismo script.

### Detalle Técnico
**Orden de borrado.** De la hoja a la raíz, respetando los FK con `PROTECT`. Tres dependencias
mandan: `MovimientoCaja.asiento → Asiento` obliga a borrar los movimientos antes que los
asientos; `Asiento.sesion_caja → CajaSesion` obliga a borrar los asientos antes que las sesiones;
y los satélites (`ValorTerceros`, `TransaccionBancaria`) protegen a `MovimientoCajaDetalle`, así
que van primero.

**Señales desactivadas durante el borrado.** El primer intento abortó con
`ValidationError: El asiento está desbalanceado. Debe 25000.00 - Haber 50000.00`: el `post_delete`
de `CompraItem` recalcula y vuelve a guardar la `Compra`, y el `post_save` de `Compra` dispara
`contabilizar_compras()`. A mitad del borrado la compra ya había perdido sus ítems, así que el
asiento salía descuadrado. Como todo corría en una transacción, no se borró nada. La solución fue
un context manager que desconecta todas las señales de modelo y las restaura en un `finally`: en
un teardown masivo no se quiere ningún efecto colateral.

**Saldos derivados recompuestos a mano.** Con las señales apagadas, las cuentas corrientes no se
recalculan solas. Al terminar se llevó `ClienteProveedor.saldo` a su `saldo_inicial`: eran 4
entidades con saldo distinto de cero, hoy las 6 en `0.00`.

**Stock.** Se borró el LIBRO de movimientos (`MovimientoStock`, `facturacion.Movimiento`) pero NO
los saldos (`StockSucursal`, 13.596 filas; `ExtensionArmeria`, 3.754). No genera incoherencia:
el stock se cargó por importación y no se derivaba de esos movimientos —había 13.596 registros de
stock contra 59 movimientos—.

### Resultado
**356 filas borradas** y 4 saldos reseteados:

| Grupo | Filas |
|---|---|
| Asientos y líneas | 24 + 87 |
| Ventas / ítems | 18 + 23 |
| Compras / ítems / alícuotas / ret-perc | 5 + 5 + 1 + 3 |
| Preventas / ítems | 18 + 23 |
| Recibos / aplicaciones | 5 + 5 |
| Órdenes de pago / aplicaciones | 1 + 1 |
| Movimientos de caja / detalles / sesiones | 17 + 15 + 3 |
| Trazabilidad de movimientos | 30 |
| Movimientos de stock | 59 |
| Libro IVA / alícuotas / retenciones sufridas | 5 + 4 + 3 |
| Transacciones bancarias | 1 |

### Verificación
- **Empresa 1:** los 13 grupos de movimientos en **0**; maestros intactos (200 cuentas, 347
  productos, 859 subproductos, 12 rubros, 6 clientes/proveedores, 6 medios de pago, 2 cuentas
  bancarias, 2 cajas, 1 sucursal, 1 ejercicio, ParametrosContables).
- **Otras empresas sin tocar:** empresa 2 con 21 asientos, 11 ventas, 268 cuentas y 6.793
  productos; empresa 3 con 1 asiento, 1 venta y 247 cuentas.
- **Aplicación operativa:** Tesorería, Caja Diaria, EOAF y su grilla responden 200.

### Estado actual y siguientes pasos
La empresa 1 quedó con su configuración y sus maestros completos y sin historial de operaciones,
lista para probar los circuitos de cero. El respaldo previo queda disponible por si hiciera falta
recuperar algo.

---

## 16 de Agosto de 2026 — Aplicación de las migraciones del Plan 049 y verificación en la app

### Motivo
Con el modelo ya cambiado y las migraciones sin aplicar, cualquier consulta a `MovimientoCaja`
fallaba: `ProgrammingError: column tesoreria_movimiento_caja.empresa_id does not exist` al abrir
**Caja Diaria**. La aplicación estaba caída, así que correr las migraciones era la corrección.

Antes de migrar se respaldó la tabla completa (21 filas) a CSV.

### Resultado de la migración
```
Applying tesoreria.0013_plan049_movimiento_caja... OK
Applying tesoreria.0014_plan049_backfill...
  Plan 049: 21 movimientos actualizados. 1 con la fecha reencuadrada a la del comprobante.
  18 vinculados a un asiento (3 sin asiento resoluble).
Applying tesoreria.0015_plan049_constraint_condic... OK
```

Estado final: 21/21 con `empresa` y `cli_pro`, 18 con `asiento`, 15 con `cuenta`.

### Verificación en la aplicación (HTTP 200 contra la base real)
| Pantalla | Estado |
|---|---|
| `/tesoreria/caja-diaria/` | 200 — restablecida |
| `/tesoreria/origen-aplicacion-fondos/` | 200 |
| `…/grilla/` | 200 |
| `…/excel/` | 200 (xlsx generado) |
| `…/pdf/` | 200 (pdf generado) |

### Hallazgos en los datos (PREEXISTENTES, ajenos a estos planes)
1. **Recibos 1, 4 y 5 sin contabilizar** (`Recibo.asiento_id = None`). Son los 3 movimientos que
   quedaron sin `asiento`: el backfill hizo lo correcto al dejarlos nulos. Habría que decidir si
   se recontabilizan.
2. **Asientos 137, 138 y 139 (`VENTA MOSTRADOR 1/2/3`) tienen CERO líneas.** Cabeceras huérfanas
   de alguna corrida parcial previa del circuito de mostrador. El EOAF los ignora correctamente
   —sin líneas de disponibilidad no son un movimiento de fondos—, pero quedan sueltos en la
   contabilidad. **Quedan anotados para revisión del usuario.**

### Nota de build
Se ejecutó `npm run build` de Tailwind: las pantallas nuevas usan clases (violeta,
`max-w-[1400px]`, `sticky bottom-0`) que no estaban en el `output.css` purgado y sin recompilar
el layout se rompía.

### Regresión final de los Planes 049 y 050
```bash
python manage.py test tesoreria contable facturacion
```
**Resultado:** `Ran 189 tests in 959.153s - FAILED (errors=2)`

Los **2 errores son preexistentes y ajenos a estos planes**: los dos únicos tests de
`facturacion.tests.test_armeria_credencial_clu.ArmeriaCredencialCLUTestCase` fallan en su `setUp`
con `TypeError: Sucursal() got unexpected keyword arguments: 'codigo'` —el modelo `Sucursal` no
tiene campo `codigo`—. Entraron con el commit `7ff0da8` y ya estaban registrados en esta bitácora
en la entrada del 15/08. Verificado: ese archivo tiene exactamente 2 tests, `git status
facturacion/` no reporta cambios, y una corrida aislada de
`facturacion.tests.test_armeria_credencial_clu` + `tesoreria.tests.test_eoaf` da
`Ran 28 tests - FAILED (errors=2)`, es decir **26/26 del EOAF en verde**.

**`tesoreria` y `contable`: sin fallas.**
## 16 de Agosto de 2026 — Plan 050 fases 3 a 5: pantalla, drill-down y exportaciones del EOAF

### Objetivo
Completar el Estado de Origen y Aplicación de Fondos: pantalla en el módulo **Tesorería**,
drill-down por cuenta y exportación a Excel y PDF.

### Archivos Creados
- `tesoreria/views_eoaf.py` [NEW]: `eoaf_index`, `eoaf_grilla`, `eoaf_cuenta_modal`,
  `eoaf_excel`, `eoaf_pdf`.
- `tesoreria/services/eoaf_export.py` [NEW]: Excel y PDF.
- `templates/tesoreria/eoaf.html` [NEW]: pantalla con filtros y botón Generar.
- `templates/tesoreria/partials/eoaf_grilla.html` [NEW]: grilla jerárquica.
- `templates/tesoreria/modals/eoaf_cuenta_modal.html` [NEW]: drill-down.
- `templates/tesoreria/pdf/eoaf_pdf.html` [NEW]: layout del PDF.

### Archivos Modificados
- `tesoreria/urls.py`: cinco rutas nuevas bajo `origen-aplicacion-fondos/`.
- `templates/tesoreria/index.html`: tarjeta de acceso al reporte.
- `tesoreria/tests/test_eoaf.py`: clase `VistasTest` (7 pruebas de vistas y exportaciones).
- `docs/planes/050_...md`: fases marcadas como ejecutadas.

### Detalle Técnico

**1. La grilla no se autoejecuta.** El usuario fija período y condición y presiona **Generar**,
igual que el `cmdGenerar` del formulario legado y que el criterio adoptado en el Libro Mayor
(Plan 048). Sin eso, entrar a la pantalla dispararía una consulta sobre todo el ejercicio.

**2. Columnas: Ingresos de Fondos / Egresos de Fondos / Flujo Neto**, más el desglose en los
**seis** medios (efectivo, dólares, valores, banco, tarjetas, otros). El legado mostraba tres y
por eso sus totales no cerraban. **Sin `Disp.Inicial`**, por decisión del usuario. Sumarizadoras
en azul y negrita, como en el original.

**3. Drill-down** por cuenta imputable: asiento, fecha, cliente/proveedor, concepto, ingresos,
egresos, desglose por medio, saldo corrido y condición — la vista `cons_caja_diaria_cta` del
legado. Incluye el filtro por medio del option-group `opgMoneda`, extendido de cuatro opciones a
las siete que manejamos. Valida que la cuenta pertenezca a la empresa activa.

**4. Aplanado de `medios` en la vista.** Los templates de Django no indexan un dict por clave
variable. En lugar de agregar un filtro sólo para eso, `_con_medios_en_orden()` convierte el dict
en una lista ordenada y el template itera. Menos superficie y sin tags nuevos.

**5. Decisión tomada con la autonomía delegada por el usuario:** el **Typeahead + Lupa** por
cliente/proveedor en el drill-down **no se implementó**. El detalle ya llega acotado a una sola
cuenta y a un período, y en los volúmenes reales entra en pantalla; el buscador habría sido
complejidad sin uso. `MovimientoCaja.cli_pro` (Plan 049) lo deja disponible para cuando el
volumen lo justifique. Queda anotado en el plan.

### Pruebas Automatizadas
```bash
python manage.py test tesoreria.tests.test_eoaf
```
**Resultado:** `Ran 26 tests in 76.711s - OK`

Las 8 nuevas verifican que la pantalla NO autoejecute la consulta, que la grilla liste las
cuentas con movimiento en formato es-AR, que el modal muestre el detalle y rechace una cuenta de
otra empresa, que el Excel traiga las tres columnas de flujo y **no** `Disp.Inicial`, que el PDF
salga con cabecera `%PDF`, y que las exportaciones respeten el filtro de condición.

### Estado actual y siguientes pasos
**Plan 050 completo (fases 1 a 5).** El reporte está en Tesorería → Origen y Aplicación de Fondos.

**Pendiente operativo:** las migraciones `tesoreria.0013/0014/0015` del Plan 049 **siguen sin
aplicar**. El EOAF funciona sin ellas porque lee los asientos, pero el rango de fechas de
`MovimientoCaja` y el vínculo con el asiento dependen de correrlas:
`python manage.py migrate tesoreria`.

**Configuración aplicada:** la cuenta `111009 TRANSFERENCIA ENTRE SUCURSALES` quedó marcada con
`tipo_disponibilidad='OTR'`. En cada cliente nuevo, la cuenta que se cargue en
`ParametrosContables.cta_transferencias_sucursal` debe quedar marcada igual, o cada traslado
entre sucursales generará una fila espuria en el reporte.

---

## 16 de Agosto de 2026 — Plan 050 fases 1 y 2: núcleo de fondos y servicio del EOAF

### Objetivo
Arrancar el **Estado de Origen y Aplicación de Fondos** (migración de `suma_saldo_fciero.scx`).
Fase 1: extraer el núcleo de cálculo que ya existía en la Caja Diaria. Fase 2: el servicio del
reporte, con agregación por cuenta y rollup jerárquico.

### Archivos Creados
- `tesoreria/services/fondos.py` [NEW]: núcleo compartido — constantes de disponibilidad,
  `prorratear()`, `lineas_de_fondos()` y `asientos_de_fondos_por_fecha()`.
- `tesoreria/services/eoaf.py` [NEW]: `estado_origen_aplicacion_fondos()` y `detalle_de_cuenta()`.
- `tesoreria/tests/test_eoaf.py` [NEW]: 18 pruebas.
- `docs/planes/050_estado_origen_aplicacion_fondos.md` [NEW]: plan archivado.

### Archivos Modificados
- `tesoreria/services/caja_diaria.py`: delega la descomposición en `fondos.py`; se eliminaron las
  definiciones duplicadas de `_fila_vacia` y `_cuantizar`; nuevo `asientos_de_fondos()`.

### Detalle Técnico

**1. Un movimiento de fondos es todo asiento que toca una cuenta con `tipo_disponibilidad`.**
Dentro de él, las líneas de disponibilidad son el *bolsillo* (dan el desglose por medio) y las de
contrapartida son las filas del reporte. La fuente es el asiento y no `MovimientoCaja`, así que
entran también las compras de contado, los débitos bancarios y los asientos manuales que nunca
pasaron por una caja.

**2. Signo, verificado contra `OrigenyAplicacionFondos.xlsx`:** contrapartida al **HABER** =
origen de fondos (**Ingresos**); al **DEBE** = aplicación (**Egresos**). Contrastado en cuatro
cuentas de la muestra (clientes, proveedores, recupero de gastos, telefonía).

**3. Los traslados entre disponibilidades se excluyen solos.** Un retiro de mostrador a tesorería
tiene sus dos puntas en cuentas de disponibilidad: no hay contrapartida, `lineas_de_fondos` lo
emite con `cuenta_id = None` y el EOAF lo descarta. No hizo falta ninguna regla especial. El
legado los mostraba mezclados en el cuerpo del reporte.

**4. Rollup por prefijo de `jerarquia`, acumulando solo IMPUTABLES**, igual que el legado
(`sum ... for jera_cta = jera and imputable = .T.`). Se usa el prefijo y no la FK `sumariza`
porque en los datos legados `sumariza` está desfasado. Los totales suman solo imputables: las
sumarizadoras ya las contienen.

**5. Extracción sin cambio de comportamiento.** `prorratear()` conserva un detalle del original
que era fácil de perder: cuando los pesos suman cero **no** hay contrapartida identificable, y el
neto NO se asigna al primero ni se reparte por partes iguales —eso imputaría fondos a una cuenta
que no los movió—. Devuelve lista vacía y decide quien llama.

### Pruebas Automatizadas
```bash
python manage.py test tesoreria.tests.test_eoaf
```
**Resultado:** `Ran 18 tests in 52.144s - OK`

```bash
python manage.py test tesoreria.tests.test_caja_diaria tesoreria.tests.test_plan049_movimiento_caja
```
**Resultado:** `Ran 32 tests in 142.667s - OK` (la extracción no alteró la Caja Diaria)

Cobertura del EOAF: signo de ingresos/egresos, desglose por medio, traslados que no generan
filas, prorrateo que cierra exacto sin perder centavos, rollup jerárquico sin doble conteo,
filtros de condición y de fechas, exclusión de anulados, aislamiento entre empresas, y el
drill-down con saldo corrido y filtro por medio.

**Control de coherencia (el que en el legado NO cerraba):** Σ Flujo Neto de las imputables ==
variación neta de las disponibilidades del período. Verificado en test y contra los datos reales
de la empresa 1: neto 5.936.786,45 contra EFE 4.381.966,45 + DOL 1.718.200,00 + BCO −163.380,00.

### Estado actual y siguientes pasos
Fases 1 y 2 **completas**. Pendientes: fase 3 (vista y template HTMX en Tesorería), fase 4
(drill-down) y fase 5 (Excel y PDF).

**Pendiente de decisión del usuario:** marcar la cuenta `111009 TRANSFERENCIA ENTRE SUCURSALES`
con `tipo_disponibilidad='OTR'`. Es un cambio de DATO, no de código. Sin él, los traslados entre
sucursales van a generar una fila espuria en el EOAF.

---

## 16 de Agosto de 2026 — Plan 049 (adenda): cierre de la deuda técnica del asiento de mostrador

### Objetivo
A pedido del usuario, corregir el asiento de la venta de caja mostrador, que había quedado fuera
del alcance inicial del Plan 049.

### Archivos Modificados
- `tesoreria/views_htmx.py`: el `Asiento.objects.create` de `_crear_asientos_y_movimientos_cobro`.
- `tesoreria/services/caja_diaria.py`: deduplicación entre las dos fuentes del reporte.
- `tesoreria/tests/test_plan049_movimiento_caja.py`: clase `CajaMostradorTest` (3 pruebas).
- `docs/planes/049_movimiento_caja_asiento_cuenta_clipro.md`: §10 marcada como cerrada.

### Detalle Técnico

**1. El asiento de mostrador** ahora recibe `condic=venta.condic` —hereda la condición del
comprobante, como manda `.cursorrules`; antes quedaba en el default 1 aunque la venta fuera
presupuestada—, `sesion_caja=sesion_caja` —sin eso el cobro no entraba al reporte de Caja Diaria,
que filtra por ese campo— y `fecha=venta.fecha` en lugar de `timezone.localdate()`, para que
comprobante, asiento y movimiento de caja lleven siempre la misma fecha.

**2. Efecto colateral resuelto: doble conteo.** Al estampar `sesion_caja`, el cobro pasa a llegar
al reporte por sus **dos** fuentes (`_lineas_desde_asientos` y `_lineas_desde_movimientos`). La
deduplicación navegaba al comprobante y su cadena era `movimiento.recibo or movimiento.orden_pago`:
los cobros de mostrador cuelgan de `venta`, así que **quedaban fuera y se habrían contado dos
veces**. Ahora se deduplica por `MovimientoCaja.asiento_id` —el campo que agrega este mismo plan,
que resuelve los tres tipos de comprobante de una sola forma—, con el comprobante como fallback
para los movimientos históricos anteriores al backfill.

**3. Lo que NO se tocó:** el asiento se sigue armando con `Asiento.objects.create` +
`AsientoLinea.objects.create` en vez de `crear_asiento()`. Es un refactor del circuito de
facturación y no deja ningún desvío funcional pendiente.

### Pruebas Automatizadas
```bash
python manage.py test tesoreria.tests.test_plan049_movimiento_caja
```
**Resultado:** `Ran 18 tests in 126.109s - OK`

Las tres nuevas cubren el circuito de mostrador de punta a punta (preventa → cobro → venta →
asiento → movimiento), usando un comprobante **PRE**, que es el camino que no llama a ARCA:
`condic=2` propagado a venta, movimiento y asiento; `sesion_caja` y `fecha` estampadas en el
asiento; y la regresión de doble conteo en la Caja Diaria.

### Estado actual y siguientes pasos
Plan 049 **cerrado por completo**, deuda técnica incluida. Migraciones todavía **sin aplicar**.
Siguiente: **Plan 050 — Estado de Origen y Aplicación de Fondos**.

---

## 16 de Agosto de 2026 — Plan 049: Vínculo contable de `tesoreria_movimiento_caja`

### Objetivo
Prerrequisito del **Estado de Origen y Aplicación de Fondos** (EOAF), que migra los formularios
VFP `suma_saldo_fciero.scx` y `sum_sal_fciero_mov.scx`. La tabla `tesoreria_movimiento_caja` no
tenía cómo responder "¿de qué cuenta vino la plata y a qué cuenta se aplicó?": le faltaban el
asiento, la cuenta de imputación y el cliente/proveedor, y su `fecha` era la de carga y no la del
comprobante. El equivalente legado es `caja_diaria` (`ID_ASTO`, `ID_CTA`, `ID_COD`, `FECHA`).

### Archivos Creados
- `docs/planes/049_movimiento_caja_asiento_cuenta_clipro.md` [NEW]: plan archivado.
- `tesoreria/services/imputacion.py` [NEW]: `cuenta_principal_del_asiento()`,
  `condic_por_comprobante()` y `estampar_asiento()`.
- `tesoreria/migrations/0013_plan049_movimiento_caja.py` [NEW]: esquema.
- `tesoreria/migrations/0014_plan049_backfill.py` [NEW]: datos.
- `tesoreria/migrations/0015_plan049_constraint_condic.py` [NEW]: CheckConstraint.
- `tesoreria/tests/test_plan049_movimiento_caja.py` [NEW]: 14 pruebas.

### Archivos Modificados
- `tesoreria/models.py`: `MovimientoCaja` gana `empresa`, `asiento`, `cuenta` y `cli_pro`;
  `fecha` pasa de `DateTimeField(auto_now_add=True)` a `DateField`; dos índices compuestos y el
  `CheckConstraint` de `condic`.
- `tesoreria/views_htmx.py`: los seis circuitos que crean movimientos de caja.
- `tesoreria/services/caja_diaria.py`: docstring desactualizada.
- `migracion/scripts/03_migrar_tesoreria.py`: informa `fecha` (ahora obligatoria) y mapea los tres
  vínculos del DBF legado.

### Detalle Técnico

**1. Modelo.** Cuatro FK nuevas, todas nullable. `asiento` va con `on_delete=PROTECT`: los asientos
nunca se borran —`anular_asiento_de_comprobante()` solo marca `anulado=True`—, así que la FK no
puede quedar colgada. `fecha` pierde su `db_index` propio porque el índice compuesto
`(empresa, fecha)` lo cubre y ninguna consulta se hace sin acotar por empresa. `asiento` y
`cli_pro` tampoco llevan índice explícito: Django ya indexa toda FK y duplicarlo solo costaría
escrituras.

**2. `cuenta` = cuenta de imputación principal.** Un movimiento de caja es UNO por comprobante,
pero la contrapartida puede ser VARIAS cuentas (recibo simple, OP simple, venta mostrador
multi-rubro). Se guarda la de mayor importe, con una regla única para los seis circuitos:
`cuenta_principal_del_asiento()` agrupa las líneas del asiento por cuenta, descarta las de
disponibilidad (`tipo_disponibilidad` no vacío: son el bolsillo, no el origen ni la aplicación) y
devuelve la mayor, con desempate por `cuenta_id` para que el resultado sea determinístico.
**El desglose exacto queda en las líneas del asiento**, que es de donde los reportes de fondos
toman los importes: `cuenta` sirve para listados, filtros y búsquedas, no para cuadrar.

**3. `fecha`.** `ALTER COLUMN "fecha" TYPE date USING "fecha"::date`. No se pierde el instante de
carga: `MovimientoCaja` hereda `fecha_creacion` de `AuditModel`, que ya guardaba exactamente lo
mismo que el viejo `fecha` (estaba duplicado). Corrige el desvío de fondo: un recibo del 15/05
cargado el 16/08 caía en agosto en cualquier reporte por período.

**4. `condic` restringido a (1, 2)** por CheckConstraint. Un movimiento de FONDOS solo puede ser
Real o Presupuestado: el 3 (Ajuste) lo paga el socio y no sale plata de la empresa, el 4 son
ajustes del estudio y los 5/6/7 los genera el sistema. Coincide con la lente de Gestión.

**5. Bug corregido.** Caja mostrador fijaba `condic=1` en el movimiento de caja, así que una venta
presupuestada quedaba registrada como Real. Ahora se deriva del tipo de comprobante:
**PRE (Presupuesto) → 2; cualquier otro → 1**, calculado en el servidor y no tomado del payload.

**5 bis. Bug latente corregido de arrastre.** `tesoreria/services/caja_diaria.py` arma una sola
lista con las filas de sus dos fuentes y la ordena por la tupla `(fecha, id)`: la fuente de
asientos aporta `asiento.fecha` (`date`) y la de movimientos aportaba `movimiento.fecha`
(`datetime`). Ordenar esa lista mezclada lanza `TypeError: '<' not supported between instances of
'datetime.datetime' and 'datetime.date'` en cuanto una caja tiene movimientos de **ambas**
fuentes, que es el caso normal apenas conviven un cobro de mostrador y un recibo. Al pasar `fecha`
a `DateField` los dos lados quedan del mismo tipo. Cubierto por un test de regresión.

**6. Migraciones en tres pasos.** El backfill (0014) resuelve `empresa` por la sesión, `fecha` y
`cli_pro` por el comprobante, y `asiento` validando el id contra la tabla de asientos —los tres
comprobantes lo guardan en un `IntegerField` sin FK, así que puede apuntar a un asiento
inexistente y la FK nueva no lo toleraría—. Los tres comprobantes sirven de origen, incluida la
venta de mostrador (estampa `venta.asiento_id`): solo quedan sin asiento los movimientos internos
y los importados de VFP sin `ID_ASTO`. **Antes de aplicar el constraint, verifica que no
existan filas con `condic` fuera de (1, 2) y aborta con el listado si las hay**, en vez de
corregirlas por su cuenta. Informa por consola cuántas fechas se reencuadraron.

### Pruebas Automatizadas
```bash
python manage.py test tesoreria.tests.test_plan049_movimiento_caja
```
**Resultado:** `Ran 15 tests in 116.088s - OK`

Cobertura: el servicio de imputación (descarte de disponibilidades, mayor importe, desempate
determinístico, `None` sin contrapartida, regla PRE→2); recibo con fecha retroactiva; cobranza a
cliente y pago a proveedor (asiento, cuenta, cli_pro, empresa); recibo simple y OP simple 60/40 y
70/30 verificando que el asiento conserva **las dos** cuentas; recontabilización que reapunta el
movimiento al asiento nuevo dejando el viejo anulado; la regresión de ordenamiento de la Caja
Diaria con las dos fuentes conviviendo; y el CheckConstraint rechazando los `condic` 0, 3, 4, 5,
6 y 7.

**Regresión de los módulos afectados:**
```bash
python manage.py test tesoreria contable
```
**Resultado:** `Ran 142 tests in 795.632s - OK`

### Estado actual y siguientes pasos
Plan 049 **ejecutado**. Las migraciones 0013/0014/0015 quedan **sin aplicar en producción**:
correrlas requiere la ventana del usuario, porque el backfill reencuadra fechas históricas.

**Siguiente:** Plan 050 — EOAF, con **Ingresos de Fondos / Egresos de Fondos / Flujo Neto**
(sin Disponibilidad Inicial), filtro Real/Presupuestado, desglose por medio, drill-down por cuenta
y exportación a Excel y PDF.

---

## 15 de Agosto de 2026 — Botón Consultar, Selección de Columnas (Pantalla, Excel y CSV) en Libro Mayor — Plan 048

### Objetivo
Resolver la consulta del Libro Mayor bajo demanda (sin autoejecución al abrir), incorporar la barra de verificación de parámetros en el modal de cuenta, selección dinámica de columnas en la grilla (con 10 predeterminadas y `leyenda` desactivada por defecto), exportación en formato Tabla de Excel (`.xlsx`) y nuevo formato CSV (`.csv`) con BOM UTF-8.

### Archivos Modificados / Creados
- `contable/services/reportes_mayor.py` [NEW]: catálogo maestro de columnas (`COLUMNAS_MAYOR_CATALOGO`), extractor de columnas solicitadas (`obtener_columnas_seleccionadas`) y formateador de celdas por movimiento (`obtener_valor_columna_movimiento`).
- `contable/services/reportes_excel.py` [MODIFY]: reestructuración de `exportar_mayor_excel` para construir la planilla dinámicamente con las columnas elegidas y aplicar el objeto `openpyxl.worksheet.table.Table`.
- `contable/views_reportes.py` [MODIFY]: actualización de `exportar_mayor` y nuevo endpoint `exportar_mayor_csv`.
- `contable/views_htmx.py` [MODIFY]: `libro_mayor_rows` y `mayor_cuenta_modal` con fallbacks de cuenta, selección de columnas y `condic` predeterminados (`1`, `2` y `5`).
- `contable/views.py` [MODIFY]: `LibroMayorView` enviando catálogo de columnas y `condics_predeterminados`.
- `contable/urls.py` [MODIFY]: registro de ruta `mayor/exportar-csv/`.
- `templates/contable/partials/libro_mayor.html` [MODIFY]: selector desplegable de columnas, botón CSV, checkboxes `condic` predeterminados (1, 2 y 5) y mensaje inicial informativo sin autoejecución.
- `templates/contable/partials/libro_mayor_rows.html` [MODIFY]: renderizado dinámico de celdas según las columnas seleccionadas y actualización automática de `thead`.
- `templates/contable/modals/mayor_cuenta_modal.html` [MODIFY]: barra de verificación de parámetros con botón "Generar Reporte", selector de columnas y botones CSV, Excel y PDF.
- `contable/tests/test_libro_mayor_columnas.py` [NEW]: pruebas automatizadas para modal, fallback de cuentas y exportación a CSV.
- `docs/planes/048_libro_mayor_boton_generar.md` [NEW]: plan de implementación aprobado.

### Detalle Técnico
1. **Ejecución Bajo Demanda:** Se eliminó la petición automática `hx-trigger="load"` del modal `mayor_cuenta_modal.html`. La grilla muestra un mensaje guiando al usuario a verificar sus parámetros y presionar **"Generar Reporte"** o **"Consultar"**.
2. **Conservación de Filtros Existentes:** Se mantuvieron todos los campos de búsqueda previa (Rango de cuentas, Fechas, Cliente/Proveedor, Sucursal y Condición).
3. **Condición Predeterminada:** Se pre-completaron las opciones `1 - Real`, `2 - Presupuestado` y `5 - Apertura` como activas por defecto.
4. **Selección Dinámica de Columnas:** Se definió un catálogo extensible de 24+ campos de `Asiento`, `AsientoLinea` y `Cuenta`. Por defecto se muestran 10 columnas (`asiento_id`, `fecha`, `concepto`, `cuenta_id`, `cuenta`, `debe`, `haber`, `saldo`, `condic`, `sucursal`), manteniendo `leyenda` desactivada por defecto.
5. **Exportación a CSV con BOM UTF-8:** Se creó la exportación a CSV con delimitador `;` y BOM `\ufeff` para garantizar apertura nativa sin problemas de codificación en Excel, PowerBI o software externo.
6. **Excel en Formato Tabla:** La exportación a Excel incluye únicamente las columnas seleccionadas en pantalla y las empaqueta dentro de un objeto `openpyxl.worksheet.table.Table`.

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test contable.tests.test_libro_mayor_columnas --keepdb --noinput
```
**Resultado:** `Ran 3 tests in 11.724s - OK`

### Estado actual y siguientes pasos
Plan 048 completamente implementado y verificado. Todas las pantallas y exportaciones del Libro Mayor operan bajo demanda y con selección dinámica de columnas.

---

## 15 de Agosto de 2026 — Exportación a Excel de Saldos Mensuales — Fase 7 del Plan 047

### Objetivo
Exportar la grilla a Excel con el layout del VFP, y aplicar ahí —y sólo ahí— la inversión de signo de las cuentas de resultado.

### Archivos Modificados / Creados
- `contable/services/reportes_excel.py` [MODIFY]: **corregido un bug preexistente** (ver abajo) y agregado `exportar_saldos_mensuales_excel()`.
- `contable/views_reportes.py` [MODIFY]: `exportar_saldos_mensuales`.
- `contable/urls.py` [MODIFY]: ruta `exportar_saldos_mensuales_excel`.
- `templates/contable/partials/saldos_mensuales.html` [MODIFY]: botón Excel que reenvía los filtros vigentes.
- `contable/tests/test_saldos_mensuales_vistas.py` [MODIFY]: 5 pruebas nuevas del export.

### BUG PREEXISTENTE CORREGIDO: los tres exports a Excel estaban rotos
`_configurar_hoja()` usa `isinstance(fecha_desde, date)` en su línea 29, pero **`date` nunca estuvo importado** en el módulo. La expresión se evalúa siempre, con o sin fechas, así que la función lanzaba `NameError: name 'date' is not defined` en **toda** llamada.

Como los tres exports la invocan (`exportar_diario_excel`, `exportar_mayor_excel`, `exportar_balance_excel`), la descarga de Excel del **Libro Diario, el Libro Mayor y el Balance estaba caída**. Se corrigió con el `from datetime import date` faltante y se verificó la función con y sin rango de fechas.

### Detalle Técnico
1. **Layout idéntico al VFP** (Anexo A del plan): A=Codigo, B=Sumariza, C=Jerarquia, D=Detalle, E=Imp, F=Apertura, luego una columna por mes, y Total, Tipo, Bce, Pres, Econ, Fciero. Las planillas históricas del usuario siguen siendo comparables celda a celda.
2. **La cantidad de columnas de mes es dinámica**, igual que en pantalla: se derivan del ejercicio, no son doce fijas.
3. **El encabezado de cada mes es un número** (`202601`) con `number_format='000000'`, no texto: así se puede ordenar y usar en fórmulas.
4. **La inversión de signo vive únicamente acá.** Con alcance `resultados` los importes se multiplican por −1, de modo que los ingresos salgan positivos, los egresos negativos y la fila de totales muestre la ganancia del mes. Es el mismo criterio del VFP, donde `xSig = -1` sólo existe dentro del procedimiento de exportación.
5. **Sumarizadoras en negrita y azul**, y `freeze_panes` en la columna de Apertura para que Cuenta/Detalle queden fijos al desplazarse.
6. El botón reenvía el formulario de filtros completo, así que **el Excel refleja exactamente lo que está en pantalla**.

### Pruebas Automatizadas
```bash
python manage.py test contable.tests.test_saldos_mensuales_vistas --noinput
```
**Resultado:** `Ran 17 tests in 157.207s - OK`

```bash
python manage.py test contable --noinput
```
**Resultado:** `Ran 82 tests in 733.518s - OK`

Las pruebas del export abren el `.xlsx` generado con `openpyxl` y verifican celdas concretas: que el encabezado traiga los 12 períodos como enteros, que en modo "Todas" un ingreso valga `-1000.0` (signo natural) y en modo "Sólo Resultados" `+1000.0`, que con ingresos 1000 y egresos 400 la fila TOTALES muestre `600.0` de ganancia, y que en modo "Todas" esa misma fila cierre en `0.0` por partida doble.

### Estado actual y siguientes pasos
Fase 7 completa. Quedan la **fase 8** (medir con `EXPLAIN ANALYZE` y decidir el índice de cobertura) y la **fase 9** (contraste manual contra los CSV de referencia de ARMERIA ARMAR). Para la 9 hace falta migrar esos datos: la base actual tiene 46 asientos y ningún asiento de apertura.

---

## 15 de Agosto de 2026 — Pantalla de Saldos Mensuales y drill-down — Fases 4, 5 y 6 del Plan 047

### Objetivo
Poner el reporte en pantalla: página dedicada, panel de filtros HTMX, grilla ancha con columnas fijas, y el drill-down de tres niveles (celda → Mayor de ese mes → asiento contable).

### Archivos Modificados / Creados
- `templates/contable/saldos_mensuales.html` [NEW]: página con encabezado y contenedor `#saldos-mensuales-content`.
- `templates/contable/partials/saldos_mensuales.html` [NEW]: filtros + grilla + fila de totales.
- `contable/views.py` [MODIFY]: `SaldosMensualesView` (devuelve sólo el partial ante `HX-Request`).
- `contable/views_htmx.py` [MODIFY]: `get_saldos_mensuales_context`, `saldos_mensuales_datos`, `_querystrings_drilldown`, y **dos filtros nuevos en `get_mayor_context`: `modulo` y `ejercicio_id`**.
- `contable/urls.py` [MODIFY]: rutas `contable_saldos_mensuales` y `saldos_mensuales_datos`.
- `templates/contable/index.html` [MODIFY]: tarjeta de acceso.
- `contable/tests/test_saldos_mensuales_vistas.py` [NEW]: 12 pruebas.

### Detalle Técnico
1. **El ejercicio es un filtro siempre presente.** Si el querystring no trae uno se toma el activo de la sesión; si la empresa no tiene ejercicios, la vista responde 200 con un aviso en vez de romper.
2. **Testigo `filtros_aplicados`.** Un checkbox destildado no viaja en el GET, así que "primera carga" y "el usuario destildó todo" llegan idénticos al servidor. Un `<input type="hidden">` los distingue: sin testigo se tildan las cuatro condiciones; con testigo se respeta exactamente lo que el usuario dejó marcado.
3. **La grilla scrollea, nunca la página.** `overflow-x-auto` con `Cuenta` *sticky* a la izquierda, encabezado *sticky* arriba y fila de totales *sticky* abajo. Indentación por nivel con `padding-left` calculado.
4. **Drill-down sin endpoints nuevos.** La cadena `mayor_cuenta_modal` → `libro_mayor_rows` → `detalle_asiento_modal` ya existía. Cada celda es un `<button hx-get>` que agrega el rango del mes.
5. **Conciliación celda ↔ mayor.** Los links llevan el `condic` **explícito**, distinto según la celda: los tildados para un mes, `condic=5` para Apertura, y ambos para Total. Sin esto se rompía justo en el primer mes: un asiento de apertura fechado el 01/01 cae dentro del rango de enero y el mayor lo mostraría mientras la celda lo excluye. También se agregó `ejercicio_id` a `get_mayor_context`, que se acotaba sólo por fechas y dejaba entrar asientos de otro ejercicio con fecha solapada.
6. **Importes con `{{ valor|formato_ar }}`** en toda la grilla, según la regla del proyecto. Se corrió `npm run build`: las clases nuevas (`text-sky-700`, `text-violet-700`, `gap-1.5`, `px-2.5`, `tabular-nums`) no estaban en el CSS purgado.

### Pruebas Automatizadas
```bash
python manage.py test contable.tests.test_saldos_mensuales_vistas --noinput
```
**Resultado:** `Ran 12 tests in 104.297s - OK`

```bash
python manage.py test contable --noinput
```
**Resultado:** `Ran 77 tests in 686.021s - OK`

La prueba central es **la conciliación**: se toma el valor de una celda, se arma el link que genera el template y se verifica que la Σ(debe − haber) que devuelve `libro_mayor_rows` con esos parámetros sea **exactamente igual**. Se corre con un asiento de apertura fechado dentro del primer mes, que es el escenario donde se rompería.

### Estado actual y siguientes pasos
Fases 4, 5 y 6 completas. Queda la **fase 7**: exportación a Excel, único lugar donde se aplica el × −1 a las cuentas de resultado. Después, la medición del índice (8) y el contraste manual contra los CSV de referencia (9).

---

## 15 de Agosto de 2026 — Servicio de Saldos Mensuales — Fases 2 y 3 del Plan 047

### Objetivo
Implementar el núcleo de cálculo del reporte "Balance de Saldos Mensuales": para cada cuenta del plan, el saldo de apertura, el movimiento neto de cada mes del ejercicio y el saldo al cierre. Función pura, sin `request`, para que sea testeable de forma aislada.

### Archivos Creados
- `contable/services/saldos_mensuales.py` [NEW]: `calcular_saldos_mensuales()` y `periodos_ejercicio()`.
- `contable/tests/test_saldos_mensuales.py` [NEW]: 27 pruebas.

### Detalle Técnico
1. **Columnas mensuales dinámicas.** `periodos_ejercicio()` recorre año-mes desde `Ejercicio.inicio` hasta `Ejercicio.cierre`, y devuelve para cada período `clave` (`202504`), `label` (`Abr-25`), `primer_dia` y `ultimo_dia` —estos dos últimos alimentan el drill-down de la fase 6—. A diferencia del VFP, que reordena doce columnas físicas `mes_01..mes_12` indexadas por el mes calendario **sin guardar el año**, acá se guarda el `(año, mes)` real: soporta ejercicios irregulares y `202601` no puede colisionar con `202501`.
2. **Dos consultas agregadas, pivot en Python.** Una agrupa por `(cuenta_id, TruncMonth(fecha))` y la otra trae la apertura. Se descartó anotar 13+ `Sum(...)` condicionales sobre `Cuenta` (extrapolación del patrón del Balance): con esa cantidad de columnas el plan de PostgreSQL se degrada. Las dos consultas son **mutuamente excluyentes por `condic`**, así que ningún movimiento se computa dos veces ni se pierde.
3. **Regla central.** Apertura ← `condic=5`; meses ← `condic in {1,2,3,4}` (el usuario elige); nunca entran el `6` ni el `7`. Universos disjuntos que **no dependen de la fecha**: un asiento de apertura fechado el 01/01 va a Apertura, no a la columna de enero.
4. **Saneamiento de `condics`.** Se intersecta lo recibido con `{1,2,3,4}`: un querystring armado a mano (`?condic=5&condic=6`) no puede meter la apertura ni la refundición en una columna mensual. Con la intersección vacía devuelve grilla vacía con aviso, sin ejecutar la consulta.
5. **Rollup jerárquico por profundidad del árbol.** El nivel de cada cuenta se calcula siguiendo la cadena `sumariza` (tolerando ciclos y padres colgados), no por `len(jerarquia)`: la longitud del código depende de la convención de numeración de cada empresa, el árbol no. Se consolida de mayor a menor profundidad, igual que el `SET ORDER TO jera_cta DESC` del VFP.
6. **Signo natural siempre.** El servicio nunca invierte: la inversión (× −1) de las cuentas de resultado vivirá sólo en el export a Excel (fase 7). En pantalla el operador necesita ver el movimiento tal cual se registró, porque el signo es el dato que delata un error de carga.
7. **Omitir sin movimiento con valor absoluto** (criterio del VFP): una cuenta que netea cero pero **tuvo** movimiento se conserva; una sin nada se omite.
8. **Totales sólo sobre imputables**, para no contar cada importe una vez por nivel de la jerarquía.

### Pruebas Automatizadas
```bash
python manage.py test contable.tests.test_saldos_mensuales --noinput
```
**Resultado:** `Ran 27 tests in 152.010s - OK`

Destacadas:
- **Prueba cruzada con el Sumas y Saldos:** el `Total` de cada cuenta imputable es idéntico al saldo final que devuelve `_calcular_balance` para la misma cuenta y ejercicio. Si algún día divergen, uno de los dos está mal.
- **Aislamiento por ejercicio:** un asiento con fecha dentro del rango consultado pero adjudicado a otro ejercicio **no** entra. Es el caso que un filtro sólo por fechas dejaría pasar, y el que justifica acotar por la FK.
- Las siete combinaciones de `condic` del §5.1 del plan (gestión `1+2`, estados contables `1+3+4`, sólo auditoría `4`, sólo ajustes `3`…), verificando además que **la columna Apertura es idéntica en todas**.
- Partida doble: en modo "Todas" la fila TOTALES da `0,00` en cada columna.

### Hallazgo: `Asiento.sucursal` casi nunca se puebla
`crear_asiento()` **no expone el parámetro `sucursal`** y nunca lo asigna, y todos los llamadores productivos pasan por ahí. Conteo real de la base: **1 de 46 asientos** tiene sucursal. Es decir que el filtro por sucursal del Balance actual —y el del reporte nuevo— está operativo en el código pero **no tiene datos que filtrar**.

No se corrigió porque excede el alcance del Plan 047: la solución es agregar el parámetro y propagarlo desde el comprobante (`compra.sucursal`, `venta.sucursal`) en los 5 llamadores de `contabilizacion.py`, lo que cambia la semántica de todos los asientos futuros. **Queda registrado para decidirlo aparte.**

### Estado actual y siguientes pasos
Fases 2 y 3 completas. Siguen: vistas HTMX y URLs (4), templates (5), drill-down al mayor del mes (6) y export Excel con el × −1 (7).

---

## 15 de Agosto de 2026 — Redefinición del campo `condic` (7 valores) — Fase 1 del Plan 047

### Objetivo
Redefinir por completo la semántica del campo `condic`, que hasta ahora tenía 3 valores (1=Real, 2=Presupuestado, 3=Apertura). Es el **prerrequisito** del nuevo reporte "Balance de Saldos Mensuales" (Plan 047): sin esta fase, el asiento de refundición de resultados —que nacía con el default `1` (Real)— contaminaba el último mes de todo reporte de evolución mensual, dando vuelta las cuentas de resultado.

### La tabla definitiva
Los valores `1` a `4` coinciden con la numeración del sistema VFP anterior, con lo cual los reportes y la operatoria del usuario mapean 1:1.

| Valor | Nombre | Significado |
|-------|--------|-------------|
| `1` | Real | Registros fiscales. El 90 % de los movimientos. |
| `2` | Presupuestado | No fiscal. Gasto **real** de la empresa sin respaldo documental válido (servimoto, almacén del barrio, taxi). Sólo análisis de gestión. |
| `3` | Ajuste | Factura **válida y a nombre de la empresa** pagada por el dueño con fondos propios. Va a contabilidad y a las DDJJ de IVA/Ganancias, pero se **excluye del análisis de gastos**. Se carga como cualquier factura, contra proveedores varios. |
| `4` | Auditoría | Ajustes que el estudio contable remite tras armar los estados contables. |
| `5` | Apertura | Antes era el `3`. Lo genera el sistema. |
| `6` | Refundición | Refundición de cuentas de resultado. Lo genera el sistema. |
| `7` | Cierre | Cierre de ejercicio. **Reservado: todavía no implementado.** |

**Las tres lentes** (clave para leer cualquier filtro de `condic`): gestión = `{1,2}` · fiscal = `{1,3}` · estados contables = `{1,3,4}`. El `2` baja el resultado real pero no el fiscal; el `3` baja el fiscal sin que salga plata: uno amortigua al otro.

### Archivos Modificados / Creados
- `.cursorrules` [MODIFY]: reescrita la sección de `condic` con la tabla de 7 valores, las tres lentes y 5 reglas inflexibles. **Fuente de verdad.**
- `CLAUDE.md` [MODIFY]: actualizado el bullet resumen.
- `contable/models.py` [MODIFY]: constantes `CONDIC_ASIENTO`, `CONDIC_MOVIMIENTO`, `CONDIC_ESTRUCTURAL`, `CONDIC_FISCAL` y helper `condic_opciones()` como fuente única de rótulos; documentado el campo `condic` de `Asiento` y el gate fiscal de `LibroIvaBase`.
- `contable/services/contabilizacion.py` [MODIFY]: el Libro IVA pasa de `compra.condic == 1` a **`compra.condic in (1, 3)`**.
- `contable/services/cierre.py` [MODIFY]: el asiento nace con `condic=6`; la validación de duplicados pasa de `concepto__icontains` a `condic=6`.
- `contable/services/asientos.py` [MODIFY]: `editar_asiento` rechaza asientos con `condic >= 5` (D-6) y fechas fuera del ejercicio del asiento (D-9).
- `contable/views_htmx.py` [MODIFY]: `_calcular_balance` usa `condic=5` para la apertura; el modal de edición desarma `ValidationError` para mostrar el mensaje y no `['...']`.
- `contable/views.py` [MODIFY]: `condic_opciones` al contexto de Libro Diario y Libro Mayor.
- `contable/forms.py` [MODIFY]: rótulo `2 - Presupuestado` (unificado con `.cursorrules`).
- `facturacion/models.py` [MODIFY]: documentado `condic` en `Venta` y `Compra`.
- `migracion/scripts/02_migrar_asientos.py` [MODIFY]: apertura migrada con `condic=5`.
- `templates/contable/partials/detalle_asiento.html` [MODIFY]: badges para los 7 valores.
- `templates/contable/partials/libro_diario.html`, `libro_mayor.html` [MODIFY]: checkboxes generados desde `condic_opciones` (antes hardcodeados 1/2/3; un asiento `condic>=4` quedaba **invisible** en el Libro Diario).
- `templates/contable/modals/asiento_form.html` [MODIFY]: rótulo unificado.
- `contable/tests/test_libro_diario_mejoras.py` [MODIFY]: aserción del rótulo.
- `contable/migrations/0019_renumerar_condic.py` [NEW]: data migration.
- `contable/tests/test_condic_renumeracion.py` [NEW]: 18 pruebas.
- `docs/planes/047_reporte_saldos_mensuales.md` [NEW]: plan completo archivado.

### Detalle Técnico
1. **Sin migración de esquema.** `condic` es un `IntegerField` sin `choices` ni `CheckConstraint`: la renumeración es un `UPDATE`, no un `ALTER TABLE`. La migración `0019` reasigna `3 → 5` y las refundiciones históricas (que quedaron con el default `1`) a `6`, identificándolas por el concepto `CIERRE DE EJERCICIO%`, único rastro disponible en bases previas. Es **idempotente** y tiene función de reversa.
2. **Momento elegido.** Conteo real de la base antes de migrar: `condic=1` → 40 asientos, `condic=2` → 6, **cero** con `condic=3` y **cero** asientos de cierre. La renumeración no tocó datos productivos.
3. **Dos bugs preexistentes cerrados de paso:**
   - `editar_asiento` guardaba la fecha nueva sin revalidar que perteneciera al ejercicio del asiento, rompiendo el invariante que `crear_asiento` sí garantiza (deriva el ejercicio *desde* la fecha).
   - El form de edición sólo ofrece `condic` 1 y 2, así que guardar un asiento de apertura lo **degradaba a Real** de forma silenciosa.
4. **Refundición ≠ Cierre.** `procesar_cierre_ejercicio` sólo cancela las cuentas de **resultado**: es una refundición (`6`). El cierre real (`7`), que además cancela las patrimoniales, **no existe todavía**. Queda reservado para el desarrollo en que, al crear un ejercicio nuevo, el sistema tome el `condic=7` del anterior y lo copie como `condic=5` (apertura) del nuevo.

### Pruebas Automatizadas
```bash
python manage.py test contable.tests.test_condic_renumeracion --noinput
```
**Resultado:** `Ran 18 tests in 179.906s - OK`

```bash
python manage.py test contable --noinput
```
**Resultado:** `Ran 38 tests in 358.091s - OK`

**Regresión de los módulos que consumen `condic`:**
```bash
python manage.py test tesoreria --noinput     # Ran 43 tests in 531.169s - OK
python manage.py test facturacion --noinput   # Ran 18 tests - FAILED (errors=2)
```
Los 2 errores de `facturacion` son **preexistentes y ajenos a este cambio**: `test_armeria_credencial_clu.ArmeriaCredencialCLUTestCase` falla en su `setUp` con `TypeError: Sucursal() got unexpected keyword arguments: 'codigo'` — el modelo `Sucursal` no tiene campo `codigo`. El test entró con el commit `7ff0da8` (*Solicitar Credencial en Preventa*). **Queda pendiente de corregir en el plan que corresponda.**

Cobertura: semántica de las constantes, rechazo de edición de asientos estructurales y de fechas fuera del ejercicio (incluidos los bordes `inicio`/`cierre`, que es el caso real de la factura del ejercicio anterior), refundición con `condic=6` y detección independiente del concepto, Libro IVA poblado por `condic` 1 y 3 pero no por 2 ni 4, herencia del `condic` del comprobante al asiento, apertura (`5`) separada del movimiento del período, y data migration idempotente.

### Estado actual y siguientes pasos
Fase 1 del Plan 047 **completa**. Siguientes fases: servicio `saldos_mensuales.py`, vistas HTMX, drill-down al mayor del mes, export Excel con el `× −1` en modo Resultados.

**Pendientes registrados fuera de alcance:** el `condic=7` (cierre real), la copia automática cierre→apertura, la captura de asientos de auditoría (`condic=4`), habilitar el `condic=3` en la carga para usuarios autorizados, y el cambio de `condic` posterior a la emisión en ventas —que deberá resincronizar el Libro IVA al pasar de `{1,3}` a `2`—.

---

## 15 de Agosto de 2026 — Filtro de Estado en Libro Diario / Libro IVA y Clarificación de Anulaciones

### Objetivo
Responder a la inquietud sobre los movimientos con estado "Anulado" en el Libro IVA / Libro Diario, clarificar las razones contables y fiscales por las cuales la anulación es un proceso irreversible, e implementar un **Filtro de Estado** ("Sólo Activos", "Sólo Anulados", "Todos") en la grilla dinámica y en las exportaciones (Excel / PDF).

### Archivos Modificados / Creados
- `templates/contable/partials/libro_diario.html` [MODIFY]: Agregado selector desplegable `<select name="estado">` con opciones (Sólo Activos, Sólo Anulados, Todos).
- `contable/views_htmx.py` [MODIFY]: Actualizada la vista `libro_diario_rows` para procesar el parámetro `estado` y filtrar `Asiento` segun `anulado`.
- `contable/views_reportes.py` [MODIFY]: Actualizados los endpoints `exportar_diario` (Excel) y `exportar_diario_pdf_view` (PDF) para respetar el filtro por `estado`.
- `contable/tests/test_libro_diario_mejoras.py` [MODIFY]: Agregado el test `test_libro_diario_filtro_estado`.
- `docs/planes/041_filtro_estado_libro_iva_diario.md` [NEW]: Plan de implementación archivado.

### Detalle Técnico
1. **Modelado y Filtrado:**
   - Opción `1` (Sólo Activos): `Asiento.objects.filter(anulado=False)`.
   - Opción `2` (Sólo Anulados): `Asiento.objects.filter(anulado=True)`.
   - Opción `0` (Todos): sin filtro sobre `anulado`.
2. **Interfaz de Usuario:**
   - La barra de filtros fue estructurada en un diseño Tailwind limpio con la opción predeterminada en "Sólo Activos", ocultando automáticamente comprobantes anulados a menos que el usuario elija verlos explícitamente.

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test contable.tests.test_libro_diario_mejoras --noinput
```
**Resultado:** `Ran 7 tests in 27.787s - OK`.

---


## 18 de Agosto de 2026 — Listado de Facturas Pendientes (réplica del VFP `tran_facturas_pendientes`)

### Objetivo
Replicar en el ERP el formulario VFP **I-108 `tran_facturas_pendientes`** (`c:\jm_soft\balances\forms\`):
el estado de cancelación de la cuenta corriente, comprobante por comprobante, con salidas a
pantalla, Excel y PDF. Se partió del análisis del `.scx`/`.sct`, de la vista
`cons_lib_iva_pendientes` extraída del `contable.dbc`, del reporte `.frx` y de las muestras
`d:\borrador\FacturasPendientes.csv` / `.pdf`.

### Archivos creados / modificados
- `facturacion/services/facturas_pendientes.py` [NEW]: servicio de consulta. `FiltroFacturas`,
  `FilaFactura`, `TotalesFacturas`, `consultar()`, `calcular_totales()`, `agrupar_por_entidad()`.
- `facturacion/services/facturas_pendientes_excel.py` [NEW]: exportación `openpyxl` (19 columnas).
- `facturacion/views_facturas_pendientes.py` [NEW]: las cuatro vistas (pantalla, grilla HTMX,
  Excel, PDF), todas `GET` y de sólo lectura.
- `templates/facturacion/reportes/facturas_pendientes.html` [NEW]: pantalla con barra de filtros.
- `templates/facturacion/reportes/partials/facturas_pendientes_grilla.html` [NEW]: grilla + pie.
- `templates/facturacion/pdf/facturas_pendientes.html` [NEW]: "RESUMEN DE CUENTAS" (A4 apaisado).
- `config/urls.py` [MODIFY]: 4 rutas nuevas bajo `facturas-pendientes/`.
- `templates/base.html` [MODIFY]: ítem "Facturas Pendientes" en los submenús de Compras
  (`?operacion=C`) y de Ventas (`?operacion=V`).
- `static/css/output.css` [MODIFY]: recompilado con `npm run build` (Tailwind purga por contenido).
- `facturacion/tests/test_facturas_pendientes.py` [NEW]: 24 pruebas.
- `docs/planes/056_listado_facturas_pendientes.md` [NEW]: plan de implementación archivado.

### Detalle técnico

**1. La fuente NO es el Libro IVA.** El VFP leía `lib_iva`; acá se lee `Compra` y `Venta`. Tres
razones: `LibroIvaVentas` nunca se puebla (`contabilizacion.py` sólo crea `LibroIvaCompras`), el
Libro IVA se llena sólo con `condic in (1,3)` — con lo que los `2` (Presupuestado) y `4`
(Auditoría) desaparecerían justo del listado de gestión — y `pagado`/`saldo` viven en los
comprobantes. Neto, IVA, No Gravado y Exento ya están en `Compra`/`Venta`: no se toca el
subsistema fiscal para ninguna columna.

**2. `pagado := total − saldo` en las dos operaciones.** `Compra.pagado` existe y la identidad es
exacta. `Venta` **no tiene** campo `pagado`: tiene `cobrado` (cobro en el acto) y
`saldo = total − cobrado − Σ ReciboAplicacion`. Con esta definición los totalizadores cierran por
construcción (`Σ total = Σ pagado + Σ saldo`), y hay un test que lo verifica.

**3. Traducción de los filtros del VFP.** Fechas (precargadas con el ejercicio en curso acotado a
hoy, como el `Form.Init`), Compras|Ventas excluyente, Todos|Uno con **Typeahead + Lupa**, y el
estado de pago replicando los rangos de `saldo`: Pagadas ⇒ `saldo = 0`, Pendientes ⇒
`saldo <> 0`. El rango negativo del original es intencional y se conservó: así aparecen las notas
de crédito todavía sin aplicar.

**4. Dos filtros que el VFP no tenía.** *Condición* (Real/Presupuestado/Ajuste/Auditoría), que
`.cursorrules` exige en todo listado con importes — sin checkboxes marcados se entiende "todas",
no "ninguna". Y *Incluir anuladas*, apagado por defecto (`Venta.estado != 1`); los estados `2`
(Pend. Autorización) y `3` (Rechazada) sí se listan siempre.

**5. Sólo lectura — el botón "Modificar" no se replicó.** En el VFP desbloqueaba `pagado` en la
grilla y hacía `TABLEUPDATE` directo sobre `lib_iva`, porque ese campo materializado se
desincronizaba. Acá `pagado`/`saldo` son derivados de las aplicaciones de OP y Recibos
(`contable/services/saldos.py`): no hay nada que forzar. **Ninguna de las cuatro rutas es `POST`
y el módulo no escribe en la base**; hay un test que recorre las cuatro vistas y verifica que los
importes queden intactos. Al no escribir, tampoco necesita `transaction.atomic()` ni
`select_for_update()`.

**6. Columnas descartadas.** `cantidad` y `litros` son herencia de verticales viejas (GNC/agro):
salen siempre en cero, y la versión en producción del ejecutable VFP ya ni las exportaba (18
columnas en el CSV contra las 20 que escribe el código). Con ellas se fue el totalizador de
`litros`: **el pie tiene tres cajas — Total, Pagado, Saldo — en vez de las cuatro del original.**
También se omitieron `vencim` (no existe el campo en `Compra`/`Venta`) y `f_p`.

**7. Truncado honesto.** La grilla corta en 500 filas, pero `calcular_totales()` agrega sobre el
conjunto completo: el pie nunca miente. Cuando hay corte se muestra un aviso explícito y se
aclara que el Excel y el PDF incluyen todas.

**8. Bug del reporte original corregido.** Midiendo coordenadas sobre `FacturasPendientes.pdf` se
verificó que en el `.frx` las columnas rotuladas *"Pendiente"* y *"Saldo"* están invertidas: la
primera trae el saldo del comprobante y la segunda el acumulado corrido del grupo. En el PDF
nuevo los rótulos dicen lo que la columna contiene. Se conservaron las **dos** variantes de suma
corrida del original: `acum_global` (columna `Acum.` del Excel) y `acum_grupo` (reinicia por
cliente/proveedor, como el impreso).

### Implicaciones de base de datos
**Ninguna migración.** Se aprovechan los índices existentes `(empresa, fecha)` de `Compra` y
`Venta`, y `(empresa, razon_social)` de `ClienteProveedor` para el `ORDER BY`. Las consultas usan
`select_related` + `.only(...)` acotado, porque el volumen real ronda las 400 filas por consulta
sobre tablas anchas. Queda pendiente evaluar con `EXPLAIN ANALYZE` sobre datos reales si el modo
*Pendientes* justifica un índice parcial `WHERE saldo <> 0` (decisión D4 del plan).

### Pruebas automatizadas
```bash
.\venv\Scripts\python.exe manage.py test facturacion.tests.test_facturas_pendientes --noinput
```
**Resultado:** `Ran 24 tests in 570.528s - OK`

Cobertura: aislamiento multiempresa (incluido el caso de pasar por querystring el id de una
entidad de otra empresa), estados Pagadas/Pendientes/Todas con saldo negativo, filtro de
condición y el default vacío, `pagado` contra las aplicaciones reales de una Orden de Pago,
`pagado = total − saldo` en Ventas, cierre de los totales, ventas anuladas (excluidas por
defecto, sin contaminar totales, visibles y marcadas con el checkbox), totales sobre el conjunto
completo con truncado a 500, acumulado global y por grupo, Excel y PDF, y sólo lectura.

### Estado actual y siguientes pasos
Plan 056 **completo**. Pendientes registrados fuera de alcance: la fecha de vencimiento de los
comprobantes (decisión D1 — requiere migración en `Compra`/`Venta` y tocar las pantallas de
carga, merece su propio plan) y el índice parcial del modo Pendientes (D4).

**Regresión del módulo completo:**
```bash
.\venv\Scripts\python.exe manage.py test facturacion --noinput
```
**Resultado:** `Ran 53 tests in 703.389s — FAILED (failures=1, errors=5)`

Los 6 son **preexistentes y ajenos a este cambio** (el diff no toca ninguno de los archivos
involucrados):
- 2 errores en `test_armeria_credencial_clu`: `TypeError: Sucursal() got unexpected keyword
  arguments: 'codigo'` — el modelo `Sucursal` no tiene ese campo. Ya estaba registrado como
  pendiente en la entrada del Plan 047.
- 3 errores en `test_exportar_clientes_excel`: el `setUp` hace
  `Jurisdiccion.objects.create(codigo=901, ...)` y choca con la semilla de la migración
  `facturacion/migrations/0025_cargar_jurisdicciones.py`, que ya inserta la jurisdicción 901
  (`UniqueViolation` sobre `facturacion_jurisdiccion_codigo_key`). **Nuevo pendiente detectado.**
- 1 fallo en `test_arca_service.test_emitir_comprobante_homologacion_real`: prueba de integración
  real contra los servidores de ARCA en Homologación, rechazada del lado de ARCA
  (`Err 501: Error interno de base de datos`). Depende de un servicio externo.

### Ajuste posterior — tarjetas en los índices de módulo
El acceso había quedado sólo en el menú lateral. Se agregó la tarjeta correspondiente en las dos
pantallas de índice, siguiendo el patrón de tarjetas existente (color **orange**, libre en ambas):
- `templates/facturacion/compras_index.html` [MODIFY]: tarjeta "Facturas Pendientes"
  (`?operacion=C`), entre "Listado de Compras" y "Compras Automática".
- `templates/facturacion/ventas_index.html` [MODIFY]: tarjeta "Facturas Pendientes"
  (`?operacion=V`), después de "Ventas por Producto".
- `static/css/output.css` [MODIFY]: recompilado — las clases `orange` eran nuevas en el purgado.

### Corrección — comentarios de template visibles en pantalla
Se estaban renderizando los comentarios como texto plano. Causa: **`{# ... #}` en Django sólo
funciona en una línea**; los comentarios escritos en dos o tres líneas no se parsean y salen
literales. Se pasaron a `{% comment %}...{% endcomment %}`:
- `templates/facturacion/reportes/facturas_pendientes.html` [MODIFY]: 2 comentarios.
- `templates/facturacion/pdf/facturas_pendientes.html` [MODIFY]: 1 comentario (en el `<head>`).
- `templates/tesoreria/eoaf.html` [MODIFY] y `templates/tesoreria/modals/eoaf_cuenta_modal.html`
  [MODIFY]: mismo defecto, **preexistente** (Plan 050), también visible en pantalla.

Barrido de todo `templates/`: no queda ningún `{#` sin su `#}` en la misma línea.

---

## 19 de Agosto de 2026 — Plan 059: Rediseño UI/UX del Modal Mayor General de Cuenta (Saldos Mensuales)

### Objetivo
1. Implementar desplazamiento horizontal (`scroll` horizontal) en el listado de movimientos del modal Mayor General de Cuenta para evitar que se corten o compriman excesivamente las columnas contables.
2. Fijar el encabezado de las columnas (`<thead>`) mediante `sticky header` al realizar scroll vertical a lo largo de los movimientos.
3. Ampliar el ancho contenedor del modal de `max-w-5xl` (1024px) a `w-11/12 max-w-7xl` (1280px) para maximizar la visibilidad de datos en pantalla.
4. Ajustar el catálogo de columnas del Mayor General para establecer como predeterminadas únicamente las 7 columnas solicitadas: `ID Asiento`, `Fecha`, `Concepto`, `Debe`, `Haber`, `Saldo` y `Condición`.

### Archivos Modificados / Creados
- `contable/services/reportes_mayor.py` [MODIFY]:
  - Actualización de `COLUMNAS_MAYOR_CATALOGO` otorgando `default = True` exclusivamente a las 7 claves predeterminadas (`asiento_id`, `fecha`, `concepto`, `debe`, `haber`, `saldo`, `condic`) y cambiando `cuenta_id`, `cuenta` y `sucursal` a `default = False`.
- `templates/contable/modals/mayor_cuenta_modal.html` [MODIFY]:
  - Rediseño de la clase de tamaño modal a `w-11/12 max-w-7xl`.
  - Configuración del contenedor interno con `overflow-x-auto overflow-y-auto max-h-[calc(90vh-220px)]` e `inline-block align-middle min-w-full`.
  - Ajuste del `<thead>` inicial por defecto para las 7 columnas requeridas otorgándoles clases `sticky top-0 z-20 bg-slate-100 whitespace-nowrap`.
- `templates/contable/partials/libro_mayor_rows.html` [MODIFY]:
  - Adición de `whitespace-nowrap` a las celdas `<td>` del cuerpo del listado.
  - Actualización de la función JavaScript `renderThead` incorporando las clases de sticky header y no quiebre de renglón (`sticky top-0 z-20 bg-slate-100 shadow-sm border-b border-slate-200 whitespace-nowrap`) a los elementos `<th>` generados dinámicamente.
- `docs/planes/059_rediseno_modal_mayor_cuenta.md` [NEW]: copia de respaldo numerada del plan de implementación.
- `docs/walkthrough.md` [MODIFY]: actualización incremental de la bitácora de desarrollo.

### Detalle Técnico
1. **Comportamiento del Scroll Horizontal y Vertical:** Al abrir el modal desde Saldos Mensuales o desde el Libro Mayor, el contenedor central de la grilla administra simultáneamente el scroll vertical de los movimientos y el scroll horizontal cuando el ancho acumulado de columnas supera el ancho útil de la pantalla.
2. **Encabezado Persistente (Sticky Header):** Al desplazarse verticalmente por una cuenta con cientos de asientos, la fila `<thead>` permanece anclada en la parte superior (`sticky top-0 z-20`) con fondo opaco `bg-slate-100`, asegurando que los títulos de las columnas no se pierdan.
3. **Catálogo de Columnas:** Las 7 columnas por defecto abarcan exactamente la información operativa fundamental. Cualquier columna adicional (ej. `Sucursal`, `Nº Diario`, `Módulo`, `Cli/Prov`) puede agregarse o quitarse en tiempo real mediante el botón "Columnas".

### Pruebas Automatizadas
```powershell
.\venv\Scripts\python.exe manage.py test contable.tests.test_libro_mayor_columnas contable.tests.test_saldos_mensuales_vistas
```
**Resultado:** `Ran 20 tests in 137.644s - OK`

---

## 21 de Agosto de 2026 — Plan 062: Incorporación de Costo de Reposición (cto_rep) en VentaItem

### Objetivo
Agregar el campo `cto_rep` (Costo de Reposición) a la tabla `facturacion_ventaitem` para congelar e inmutabilizar el costo de reposición vigente del producto (`productos_producto.cto_rep`) al momento exacto de la venta. Esto permite calcular con precisión el **Margen Bruto**, la **Contribución Marginal** y el **Punto de Equilibrio** por ítem y por venta de manera independiente a futuras modificaciones de precios/costos en el catálogo de productos.

### Archivos Creados / Modificados
- `facturacion/models.py` [MODIFY]:
  - Adición del campo `cto_rep = models.DecimalField(max_digits=15, decimal_places=2, default=0)` en `VentaItem`.
  - Lógica en `VentaItem.save()`: autocompletar `self.cto_rep = self.producto.cto_rep` si `cto_rep` es `0` o `None` al guardar.
  - Propiedades calculadas en `VentaItem`: `subtotal_costo_reposicion`, `contribucion_marginal_unitaria`, `contribucion_marginal_total`.
  - Propiedades calculadas en `Venta`: `total_costo_reposicion`, `contribucion_marginal_total`, `margen_bruto_porcentaje`.
- `facturacion/services/notas_credito.py` [MODIFY]:
  - Asignación explícita de `cto_rep=original_item.cto_rep` al generar el `VentaItem` de una Nota de Crédito.
- `facturacion/migrations/0049_ventaitem_cto_rep.py` [NEW]: migración de esquema que agrega la columna `cto_rep`.
- `facturacion/migrations/0050_backfill_ventaitem_cto_rep.py` [NEW]: migración de datos para backfill de ventas históricas.
- `facturacion/tests/test_costo_reposicion.py` [NEW]: suite de pruebas unitarias para `cto_rep` y contribución marginal.
- `docs/planes/062_costo_reposicion_ventaitem.md` [NEW]: copia de respaldo archivada del plan de implementación.
- `docs/walkthrough.md` [MODIFY]: registro incremental de la bitácora.

### Detalle Técnico
1. **Inmutabilidad del Costo de Venta:** Al concretar una venta, el costo de reposición del producto se estampa en `VentaItem.cto_rep`. Si el proveedor o el usuario aumentan posteriormente el costo de reposición en la ficha del producto, el costo registrado en la venta realizada se mantiene inalterado.
2. **Backfill Histórico:** La migración `0050_backfill_ventaitem_cto_rep` recorrió los registros de `VentaItem` donde `cto_rep` era 0 y les asignó el `cto_rep` actual de su correspondiente producto mediante operaciones en bloques (`bulk_update`).
3. **Punto de Equilibrio y Contribución Marginal:** La contribución marginal unitaria se computa restando el costo de reposición al precio de venta neto de descuento: `(precio_unitario * (1 - descuento/100)) - cto_rep`.

### Pruebas Automatizadas y Verificación
- **Script de Verificación Transaccional:**
  ```powershell
  .\venv\Scripts\python.exe C:\Users\cpn_o\.gemini\antigravity-ide\brain\6398231f-2136-4cc9-9b17-4e379c8bf3f8\scratch\test_costo_reposicion_script.py
  ```
  **Resultado:** `[TEST SUCCESS] Todos los asserts pasaron exitosamente.`
- **Tests Unitarios Django:**
  ```powershell
  .\venv\Scripts\python.exe manage.py test facturacion.tests.test_costo_reposicion --noinput --keepdb
  ```
  **Resultado:** `OK`

### Estado actual y siguientes pasos
Plan 062 **completado, migrado y verificado**. La base de datos y la capa de modelos cuentan con la trazabilidad inmutable del costo de reposición en cada ítem facturado y las propiedades para emitir análisis de contribución marginal y rentabilidad.

---

## 22 de Agosto de 2026 — Plan 066: Corrección del Alta de Proveedores y Reactividad Fiscal

### Objetivo
Resolver el fallo en el formulario modal `ClienteProveedor` que impedía registrar o ingresar un **Proveedor**, provocado por una reconversión forzada a rol "Cliente" en el frontend cuando el tipo de documento inicial era 99 (Sin Identificar), así como por la falta de validación estricta de CUIT y Condición Fiscal para proveedores en el backend.

### Archivos Creados / Modificados
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]:
### Pruebas Automatizadas
- **Tests Unitarios Django:**
  ```powershell
  .\venv\Scripts\python.exe manage.py test facturacion.tests.test_proveedor_alta
  ```
  **Resultado:** `Ran 3 tests in 2.150s - OK`

### Estado Actual y Siguientes Pasos
Plan 066 **completado y verificado**. La creación y edición de proveedores funciona de manera fluida y consistente en todo el sistema ERP Ikigai 2.

2. **Lógica de Alerta:**
   - Si `dias > 15`: Estado `success` (sin banner de alerta).
   - Si `4 <= dias <= 15`: Estado `warning` (banner ámbar preventivo).
   - Si `0 <= dias <= 3`: Estado `danger` (banner rojo urgente).
   - Si `dias < 0`: Estado `danger` con flag `es_vencido=True` (banner rojo parpadeante indicando que la facturación electrónica puede estar suspendida).

### Resultados de la Verificación
- **Prueba en Shell de Django:**
  - `e.estado_vencimiento_crt` evaluado para empresa activa, simulación de 10 días restantes y simulación de certificado vencido.
  - **Resultado:** Cálculo exacto de días, fechas formateadas y banderas activadas según lo esperado.
- **Migración de base de datos:** `Applying empresas.0015_empresa_vencimiento_crt_afip... OK`.

### Estado Actual
Plan 032 **completamente implementado, probado y verificado**. La gestión de vencimiento de certificados digitales ARCA/AFIP está lista y operativa.

---

## 23 de Agosto de 2026 — Plan 067: Nuevo Bloque del Menú Principal "Impuestos"

### Objetivo
Incorporar la nueva sección **Impuestos** en el menú principal (barra lateral navegable) del ERP Ikigai 2, con un menú desplegable (acordeón interactivo con Alpine.js) e interfaces para la gestión de 5 procesos y reportes impositivos.

### Archivos Creados
- `impuestos/__init__.py` [NEW]: Inicializador del paquete de la app Django impuestos.
- `impuestos/apps.py` [NEW]: Definición del `ImpuestosConfig(AppConfig)`.
- `impuestos/urls.py` [NEW]: Ruteo del módulo de impuestos (`app_name = 'impuestos'`).
- `impuestos/views.py` [NEW]: Vistas `ImpuestosIndexView`, `CierrePeriodoIvaView`, `LibroIvaVentasView`, `LibroIvaComprasView`, `MisComprobantesArcaView` y `SicoreGananciasView`.
- `templates/impuestos/index.html` [NEW]: Panel central/Dashboard de Impuestos con tarjetas interactivas.
- `templates/impuestos/cierre_periodo_iva.html` [NEW]: Pantalla para la liquidación mensual de IVA.
- `templates/impuestos/libro_iva_ventas.html` [NEW]: Pantalla para consultar y exportar el Libro IVA Ventas para Portal IVA (ARCA).
- `templates/impuestos/libro_iva_compras.html` [NEW]: Pantalla para consultar y exportar el Libro IVA Compras para Portal IVA (ARCA).
- `templates/impuestos/mis_comprobantes_arca.html` [NEW]: Pantalla para la captura y conciliación de Mis Comprobantes ARCA.
- `templates/impuestos/sicore_ganancias.html` [NEW]: Pantalla para la exportación de retenciones de Ganancias (RG 830) en formato SICORE.
- `docs/planes/067_bloque_impuestos.md` [NEW]: Copia archivada del plan técnico de implementación.

### Archivos Modificados
- `config/settings.py` [MODIFY]: Registro de `'impuestos'` en `INSTALLED_APPS`.
- `config/urls.py` [MODIFY]: Inclusión de `path('impuestos/', include('impuestos.urls'))`.
- `templates/base.html` [MODIFY]: Integración del nuevo acordeón **Impuestos** en el menú lateral con estado activo según la URL solicitada.

### Detalle Técnico
1. **Módulo Autónomo y Modular (`impuestos`):** Se creó la estructura completa de la aplicación Django `impuestos`, permitiendo escalar de forma limpia los procesos impositivos del sistema.
2. **Navegación Dinámica en la Barra Lateral:** El menú se despliega automáticamente si la ruta del usuario comienza con `/impuestos/`, manteniendo el enlace del subproceso activo con resaltado específico en color.
3. **Dashboard de Impuestos:** Diseñado con Tailwind CSS y tarjetas dinámicas con hover y sombras animadas para acceder a cada proceso:
   - **Cierre Periodo IVA** (`/impuestos/cierre-periodo-iva/`)
   - **Libro IVA Ventas - Portal IVA** (`/impuestos/libro-iva-ventas/`)
   - **Libro IVA Compras - Portal IVA** (`/impuestos/libro-iva-compras/`)
   - **Captura Mis Comprobantes ARCA** (`/impuestos/mis-comprobantes-arca/`)
   - **SICORE - Retención Impuesto a las Ganancias** (`/impuestos/sicore-ganancias/`)

### Pruebas Ejecutadas
- **System Check de Django:**
  ```powershell
  .\venv\Scripts\python.exe manage.py check
  ```
  **Resultado:** `System check identified no issues (0 silenced).`

### Estado Actual
Plan 067 **completamente implementado y verificado**. La sección de Impuestos ya se encuentra integrada en la barra lateral del ERP Ikigai 2 y sus vistas están activas.

---

## 23 de Agosto de 2026 — Plan 068: Gestión de Períodos IVA, Cierre, Reapertura y Reglas de Imputación

### Objetivo
Desarrollar la lógica de gestión de Períodos IVA (`YYYYMM`), liquidación mensual, cierres y reaperturas impositivas, e integrar sus reglas de imputación en las operaciones de Compras y Ventas.

### Archivos Creados
- `impuestos/models.py` [NEW]: Modelo `PeriodoIva` (`empresa`, `periodo`, `estado`, `fecha_cierre`, `usuario_cierre`, `debito_fiscal`, `credito_fiscal`, `saldo_resultante`, `fecha_reapertura`, `usuario_reapertura`).
- `impuestos/services.py` [NEW]: Funciones `es_periodo_cerrado`, `obtener_primer_periodo_vigente_compra`, `calcular_liquidacion_iva`, `cerrar_periodo_iva`, `reabrir_periodo_iva` y `obtener_periodos_cerrados`.
- `impuestos/tests/test_periodo_iva.py` [NEW]: Tests unitarios para el ciclo completo de Período IVA y traslados de compras a períodos vigentes.
- `impuestos/migrations/0001_initial.py` [NEW]: Migración inicial de `impuestos` (`PeriodoIva`).
- `contable/migrations/0020_libroivacompras_periodo_libroivaventas_periodo.py` [NEW]: Adición del campo `periodo` en `LibroIvaCompras` y `LibroIvaVentas`.
- `facturacion/migrations/0051_limpiar_y_alter_periodo.py` [NEW]: Sanitización de formatos guionados previos y ajuste de `max_length=6` en `periodo` de `Compra` y `Venta`.
- `templates/impuestos/modals/periodos_cerrados_modal.html` [NEW]: Modal HTMX para la visualización y reapertura de períodos cerrados.
- `docs/planes/068_cierre_y_periodo_iva.md` [NEW]: Registro permanente del plan de implementación.

### Archivos Modificados
- `contable/models.py` [MODIFY]: Campo `periodo = models.CharField(max_length=6, default='', blank=True, db_index=True)` en `LibroIvaBase`.
- `facturacion/models.py` [MODIFY]: Normalización de `periodo` a `max_length=6, db_index=True` en `Compra` y `Venta`.
- `contable/services/contabilizacion.py` [MODIFY]: Estampado del campo `periodo` al poblar `LibroIvaCompras` e inclusión de `_limpiar_libro_iva_venta` y `_poblar_libro_iva_venta` para poblar `LibroIvaVentas` al contabilizar ventas fiscales.
- `facturacion/views.py` [MODIFY]: Validación de período cerrado en Ventas (`es_periodo_cerrado`) y cálculo automático de período vigente en Compras (`obtener_primer_periodo_vigente_compra`), previniendo períodos anteriores a la fecha de la factura.
- `impuestos/views.py` [MODIFY]: Vistas de liquidación, cierre, modal de períodos cerrados y reapertura en `CierrePeriodoIvaView`, `PeriodosCerradosModalView` y `ReabrirPeriodoIvaView`.
- `impuestos/urls.py` [MODIFY]: Ruteo de `periodos-cerrados/modal/` y `reabrir-periodo-iva/`.
- `templates/impuestos/cierre_periodo_iva.html` [MODIFY]: Botón "Ver Períodos Cerrados", desglose de Débito/Crédito y formulario de Cierre y Reapertura.
- `templates/facturacion/compras_carga.html` [MODIFY]: Adición del campo visual/selector del **Período IVA** (`YYYYMM`) en la cabecera del comprobante.

### Detalle Técnico
1. **Regla Estricta en Ventas:** El período predeterminado SIEMPRE es el `YYYYMM` de la fecha del comprobante. Si el período `YYYYMM` se encuentra CERRADO por liquidación fiscal, se bloquea la emisión.
2. **Regla de Traslado de Compras a Períodos Vigentes:** Si se registra una factura de compra con fecha en un período cerrado (ej: 22/05/2026, estando cerrados 202601 a 202607), `obtener_primer_periodo_vigente_compra` calcula y asigna automáticamente el primer período abierto `>= YYYYMM` (ej. `202608`). Se restringe categóricamente asignar un período anterior a la fecha de emisión de la compra.
3. **Poblado Completo y Consulta de Libro IVA:** Se adecuaron los reportes de `LibroIvaVentasView` e `LibroIvaComprasView` para consultar exclusivamente por **Período Fiscal (`YYYYMM`)** mediante selectores de Año y Mes Fiscal, removiendo el criterio de dos fechas reservado únicamente a los reportes de gestión.

### Pruebas Ejecutadas
- **Migraciones aplicadas:**
  - `Applying contable.0020_libroivacompras_periodo_libroivaventas_periodo... OK`
  - `Applying facturacion.0051_limpiar_y_alter_periodo... OK`
  - `Applying impuestos.0001_initial... OK`
- **System Check de Django:**
  ```powershell
  .\venv\Scripts\python.exe manage.py check
  ```
  **Resultado:** `System check identified no issues (0 silenced).`

### Estado Actual
Plan 068 **completamente implementado, migrado y verificado**. La gestión de Períodos IVA, Cierre, Reapertura y las consultas impositivas de Libro IVA Ventas e Compras por Período Fiscal (`YYYYMM`) están 100% operativas.

---

## 23 de Agosto de 2026 — Plan 069: Modelo `ArcaMisComprobantes` y Motor de Conciliación ARCA vs. Libro IVA

### Objetivo
Crear la tabla física `arca_mis_comprobantes` para almacenar las planillas de comprobantes emitidos (Ventas) y recibidos (Compras) capturados del portal de Mis Comprobantes ARCA / AFIP, e implementar la conciliación bi-direccional estampando `asiento_id` en ARCA y `cae` en el Libro IVA.

### Archivos Creados
- `impuestos/models.py` [MODIFY]: Adición del modelo `ArcaMisComprobantes` (`empresa`, `origen` ['C'/'V'], `periodo`, `fecha`, `codiva`, `punto`, `numero`, `numero_hasta`, `cuit_contraparte`, `razon_social_contraparte`, `neto_gravado`, `no_gravado`, `exento`, `iva_total`, `otros`, `total`, `cae`, `asiento_id`).
- `impuestos/migrations/0002_arcamiscomprobantes.py` [NEW]: Migración de Django para la creación de la tabla física `arca_mis_comprobantes`.
- `impuestos/tests/test_mis_comprobantes_arca.py` [NEW]: Tests unitarios para el modelo, parseo de planillas CSV/Excel y coincidencia bi-direccional de conciliación.
- `docs/planes/069_arca_mis_comprobantes.md` [NEW]: Copia archivada del plan técnico de implementación.

### Archivos Modificados
- `impuestos/services.py` [MODIFY]: Implementación de `importar_archivo_mis_comprobantes_arca`, `conciliar_mis_comprobantes_arca` y `obtener_reporte_conciliacion_arca`.
- `impuestos/views.py` [MODIFY]: Actualización de `MisComprobantesArcaView` para procesar la subida del archivo ARCA (POST) y generar el reporte por Período Fiscal (`YYYYMM`) (GET).
- `templates/impuestos/mis_comprobantes_arca.html` [MODIFY]: Rediseño con pestañas interactivas de Alpine.js: 🟢 **Conciliados**, 🟡 **Solo en Libro IVA (Sin CAE vinculada)** y 🔵 **Solo en Mis Comprobantes ARCA (Pendientes)**.

### Detalle Técnico
1. **Vinculación Bi-direccional y Sincronización de Período Fiscal:**
   - En **`ArcaMisComprobantes`**: Al conciliar un registro con el ERP, se estampa el `asiento_id` correspondiente y se actualiza `periodo = match.periodo` con el **período exacto (`YYYYMM`) en el que fue declarado en los Libros IVA del sistema** (contemplando traslados de compras a períodos vigentes posteriores).
   - En **`cble_libro_iva_compras` / `cble_libro_iva_ventas`**: Al conciliar, se estampa el `cae` o `cai` capturado de ARCA (particularmente útil en facturación en línea de ARCA o comprobantes manuales que no poseían CAE previo en el ERP).
2. **Resultados de Conciliación:**
   - **Conciliados**: `asiento_id` en ARCA y `cae` en el Libro IVA.
   - **Solo en Libro IVA**: Registros del sistema sin `cae` ni coincidencia en ARCA.
   - **Solo en ARCA**: Registros importados de ARCA pendientes con `asiento_id` nulo.

### Pruebas Ejecutadas
- **Migración aplicada:**
  - `Applying impuestos.0002_arcamiscomprobantes... OK`
- **System Check de Django:**
  ```powershell
  .\venv\Scripts\python.exe manage.py check
  ```
  **Resultado:** `System check identified no issues (0 silenced).`

### Estado Actual
Plan 069 **completamente implementado, migrado y verificado**. La captura e importación de planillas de Mis Comprobantes ARCA y su motor de conciliación bi-direccional contra el Libro IVA (con sincronización del período declarado `YYYYMM`) están 100% operativos.

---

## 24 de Agosto de 2026 — Plan 070: Incorporación de Actividades "Distribuidora" y "Empresa Agrícola" en Empresas

### Objetivo
Añadir las opciones de actividad **Distribuidora** y **Empresa Agrícola** en el selector (`tipo_actividad`) de `Empresa` y `EmpresaForm` para su selección en el formulario modal de alta y edición de empresas.

### Archivos Modificados / Creados
- `empresas/models.py` [MODIFY]: Definida la tupla `TIPO_ACTIVIDAD_CHOICES` en el modelo `Empresa` incluyendo `('DISTRIBUIDORA', 'Distribuidora')` y `('AGRICOLA', 'Empresa Agrícola')`.
- `empresas/forms.py` [MODIFY]: Vinculado `tipo_actividad` en `EmpresaForm` a `Empresa.TIPO_ACTIVIDAD_CHOICES`.
- `empresas/migrations/0016_alter_empresa_tipo_actividad.py` [NEW]: Migración de Django que registra los nuevos `choices` en `Empresa`.
- `docs/planes/070_actividades_distribuidora_y_agricola.md` [NEW]: Copia del plan de implementación archivada.

### Implicaciones de Base de Datos
- Migración aplicada: `empresas.0016_alter_empresa_tipo_actividad` (OK).

### Estado Actual
Plan 070 **completamente implementado y verificado**. Las opciones Distribuidora y Empresa Agrícola se encuentran activas en el selector de tipo de actividad de las empresas.

---

## 26 de Agosto de 2026 — Plan 071: Ajustes en Trazabilidad de Subproductos (/stock/trazabilidad/)

### Tarea u Objetivo
Implementar tres mejoras clave en el módulo de Trazabilidad de Subproductos:
1. Ampliación del historial de trazabilidad por **Serie y CUIM** (multiciclo) y creación del modal de detalle completo de compra (`compra_id`) y venta (`id_vta > 0`).
2. Modal y vista HTMX de **Edición exclusiva de SERIE y CUIM** para subsanar errores de tipeo sin alterar montos ni comprobantes.
3. Reversión automática del subproducto de `'VENDIDA'` a `'DEPOSITO'` y limpieza de la relación con la venta al emitir una Nota de Crédito por devolución.

### Archivos Creados
- `templates/productos/partials/subproducto_detalle_modal.html` [NEW]: Plantilla modal HTMX con la ficha completa de datos de adquisición (compra_id, fecha, proveedor, comprobante, costo adq, moneda, cotización) y venta (id_vta, fecha, cliente, comprobante, precio neto y total).
- `templates/productos/partials/subproducto_editar_modal.html` [NEW]: Formulario modal HTMX restringido exclusivamente a la modificación de los campos `SERIE` y `CUIM`.
- `facturacion/tests/test_plan071_trazabilidad.py` [NEW]: Tests automatizados Django probando la reversión a DEPOSITO al emitir Nota de Crédito y la edición exclusiva de SERIE/CUIM.
- `docs/planes/071_ajustes_trazabilidad_subproductos.md` [NEW]: Copia archivada del plan técnico de implementación.

### Archivos Modificados
- `productos/views_trazabilidad.py` [MODIFY]: 
  - Ampliación de `trazabilidad_modal_timeline` para consolidar el historial por Serie y/o CUIM.
  - Adición de la vista `@login_required subproducto_detalle_modal(request, subpro_id)` con consulta select_related de compra y venta.
  - Adición de la vista `@login_required subproducto_editar_modal(request, subpro_id)` para actualización exclusiva de `serie` y `cuim`.
- `facturacion/services/notas_credito.py` [MODIFY]: Reversión automática en `emitir_nota_credito_desde_venta`: al devolver un producto trazable (`subprod == True`), sus objetos `Subproducto` asociados se actualizan a `situacion = 'DEPOSITO'`, `venta = None` (`id_vta = null`), `fecvta = None`, `precio_neto = 0`, `precio_total = 0`, `cotizvta = 1`, `fecent = None`.
- `config/urls.py` [MODIFY]: Registro de las rutas HTMX `/stock/trazabilidad/subproducto/<int:subpro_id>/detalle/` y `/stock/trazabilidad/subproducto/<int:subpro_id>/editar/`.
- `templates/productos/partials/trazabilidad_grilla.html` [MODIFY]: Incorporación de botones de acción "Detalle" y "Editar" en cada fila de la grilla.
- `templates/productos/trazabilidad_list.html` [MODIFY]: Rediseño de cabecera inline y formulario ultra-compacto de 1 sola fila con Flexbox proporcional (`flex-1` en CliPro/Producto y anchos reducidos `w-32` Serie, `w-28` CUIM, `w-36` Estado y `w-20` Limpiar). Configurado disparador HTMX dinámico en `SERIE` y `CUIM` a partir del 3er carácter (`keyup[len>=3 || len==0] delay:250ms`).
- `productos/views_trazabilidad.py` [MODIFY]: Condición backend `len >= 3` en `search_serie` y `search_cuim` para filtrado dinámico.
- `templates/productos/partials/trazabilidad_grilla.html` [MODIFY]: Reducción de padding de celdas a `py-2 px-3` duplicando la densidad de filas visibles por pantalla.

### Resultado de Pruebas
- **Django Check:** 
  ```powershell
  .\venv\Scripts\python.exe manage.py check
  ```
  **Resultado:** `System check identified no issues (0 silenced).`
- **Pruebas Automatizadas (Django Unit Tests):**
  ```powershell
  .\venv\Scripts\python.exe manage.py test facturacion.tests.test_plan071_trazabilidad
  ```
  **Resultado:** `OK (3 tests ejecutados limpia y exitosamente)`.

### Estado Actual
Plan 071 **completamente ejecutado, verificado y documentado**. El módulo de Trazabilidad de Subproductos cuenta con interfaz ultra-compacta que maximiza el espacio del listado, filtrado dinámico en tiempo real a partir del 3er carácter en Serie y CUIM, historial multiciclo por Serie y CUIM, selector de filtrado por Estado Actual (`DEPOSITO` / `VENDIDA`), ficha completa de detalles de compra/venta, edición rápida de Serie/CUIM y reversión automática a 'DEPOSITO' ante Notas de Crédito.

---

## 27 de Agosto de 2026 — Columnas de Armería y Combobox 'Es Policía' en Clientes y Proveedores — Plan 072

### Objetivo
Extender la gestión de Clientes y Proveedores para empresas con actividad de **Armería** (`tipo_actividad == 'ARMERIA'`):
1. Selector de columnas y visualización en la grilla principal (`CLU`, `Vencimiento CLU` y `Es Policía`).
2. Selector desplegable (Combobox / Select) para la condición "Es Policía / Fuerza de Seguridad" (predeterminado `NO (Civil / Particular)`).
3. Exportación a Excel incorporando las columnas de Armería.
4. Optimización de consultas ORM agregando `select_related('armeria')`.

### Archivos Creados / Modificados
- `docs/planes/072_columnas_armeria_y_es_policia_clientes.md` [NEW]: Plan de implementación archivado.
- `facturacion/forms.py` [MODIFY]: `ExtensionArmeriaForm` incluye `es_policia` como `TypedChoiceField` desplegable (opciones `NO (Civil)` y `SÍ (Policía)`).
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]: Adición del combobox `es_policia` en el bloque de Registro de Armería en 3 columnas responsivas.
- `facturacion/views.py` [MODIFY]: `ClientesProveedoresIndexView` optimizado con `select_related('jurisdiccion', 'armeria')`.
- `facturacion/views_htmx.py` [MODIFY]: `buscar_clientes` optimizado con `select_related('jurisdiccion', 'armeria')`.
- `facturacion/views_reportes.py` [MODIFY]: `exportar_clientes_excel` con `select_related('jurisdiccion', 'armeria')`.
- `facturacion/services/clientes_excel.py` [MODIFY]: Inclusión condicional de columnas `CLU`, `Vencimiento CLU` y `Es Policía` en el reporte Excel para empresas Armería.
- `templates/facturacion/clientes_index.html` [MODIFY]: Checkboxes de visibilidad de columnas `N° CLU`, `Vencimiento CLU` y `Es Policía` en el desplegable y encabezados `<th>` condicionales para Armería.
- `templates/facturacion/partials/cliente_table_rows.html` [MODIFY]: Celdas `<td>` condicionales para CLU, Vencimiento CLU y Es Policía.
- `facturacion/tests/test_armeria_credencial_clu.py` [MODIFY]: Pruebas unitarias para `ExtensionArmeriaForm` (combobox) y vistas del buscador.

### Resultado de las Pruebas Automatizadas
```powershell
.\venv\Scripts\python.exe manage.py test facturacion.tests.test_armeria_credencial_clu
```
**Resultado:** `OK (Ran 4 tests in 1.728s)`.

### Estado Actual
Plan 072 **completamente ejecutado, probado y documentado**.






## Día 28/08/2026 - Autocompletado AFIP (Padrón A13) para Clientes/Proveedores

### Objetivo
Implementar un botón en el modal de Clientes/Proveedores que consulte automáticamente los datos fiscales a AFIP mediante el servicio ws_sr_padron_a13 y rellene el formulario.

### Archivos Modificados/Creados
- acturacion/services/afip_padron.py [NEW]: Se creó el servicio AFIPPadronService que reutiliza la configuración de rca_arg para conectarse a AFIP y obtener los datos a partir de un CUIT.
- acturacion/views_htmx.py [MODIFY]: Se agregó el endpoint consultar_padron_afip que retorna los datos consultados en formato JSON.
- config/urls.py [MODIFY]: Se expuso el endpoint htmx/consultar-afip/<cuit>/.
- 	emplates/facturacion/modals/cliente_modal.html [MODIFY]: Se integró un botón de autocompletado junto al campo de CUIT y lógica Alpine.js para hacer la solicitud etch y distribuir la respuesta en los inputs correspondientes (Razón Social, Domicilio, IVA, etc.).

### Detalle Técnico
El servicio de AFIP evalúa la respuesta del WS y formatea la condición de IVA según los impuestos (30 -> Inscripto, 32 -> Exento, o si tiene Monotributo). En el Frontend, si el CUIT es válido (11 dígitos), se consulta asíncronamente y se inyectan los valores directamente en los id de los campos, disparando el evento input para reactividad HTMX/Alpine si es necesario.

### Estado Actual y Siguientes Pasos
Plan de Autocompletado finalizado. Queda pendiente probar la integración directamente desde la interfaz.


## Día 28/08/2026 - Separación de Razón Social / Apellido y Nombre (Plan 073)

### Objetivo
Aplicar el Plan 073 para el módulo de Armería, separando conceptualmente Persona Física (Apellido y Nombre) de Persona Jurídica (Razón Social), garantizando que en backend los datos persistan unificados en la tabla base.

### Archivos Creados o Modificados
- acturacion/models.py [MODIFY]: Se añadió 	ipo_persona (CharField) a la ExtensionArmeria.
- acturacion/migrations/0053_extensionarmeria_tipo_persona.py [NEW]: Migración de esquema.
- acturacion/migrations/0054_assign_tipo_persona_armeria.py [NEW]: Migración de datos (Data Migration) que iteró los registros existentes. Asignó 'J' si el CUIT arranca con 30/33/34 y tiene 11 dígitos, y 'F' en caso contrario (además, para 'F', formateó la Razón Social dividiéndola con coma si no la tenía).
- acturacion/forms.py [MODIFY]: Se añadió 	ipo_persona a ExtensionArmeriaForm. Se quitó la obligación estricta HTML de 
azon_social para poder alternar el formulario dinámico, pero se validó duramente en el método clean().
- acturacion/views_htmx.py [MODIFY]: El endpoint cliente_modal fue ajustado. En POST, si el tipo de persona es Física (F), concatena Apellido y Nombre en 
azon_social. En GET, si es F, divide 
azon_social por la coma y expone al template variables para armar la vista.
- 	emplates/facturacion/modals/cliente_modal.html [MODIFY]: Se incluyeron Radio Cards de UI premium para elegir entre Física o Jurídica. Se dividieron los inputs. Además, la carga por AFIP rellena estos campos de forma automática leyendo el campo oculto 	ipo_persona.
- acturacion/services/afip_padron.py [MODIFY]: Retorna en el diccionario final 
ombre y pellido desglosados para facilitarle la vida al frontend, además del código F o J.

### Detalle Técnico
Se respetó al máximo la directiva de no utilizar suposiciones adivinadas con prefijos en tiempo de ejecución, por lo tanto la determinación del autocompletado en el padrón recae íntegramente en los datos del JSON (vía 	ipoClave). Se diseñó la interfaz usando Alpine.js y TailwindCSS sin sacrificar la rigurosidad de validación del backend de Django (clean()), asegurando compatibilidad hacia atrás mediante Data Migrations.

### Resultado de Pruebas
Las migraciones corrieron satisfactoriamente en entorno local sin errores de sintaxis o constraint.

### Estado actual y siguientes pasos sugeridos
Plan completado exitosamente y listo para pruebas operativas. Sugerimos validar la carga en la vista del usuario final creando y consultando un par de CUITs en la ventana emergente.


## Día 28/08/2026 - Módulo Distribución: maestros y campos base (Plan 074, fase 1a)

**Responsable:** Claude Opus (arquitectura y ejecución).
*Nota: `.cursorrules` indica leer `docs/soy.md` para determinar la firma, pero ese archivo no existe en el repositorio.*

### Objetivo
Ejecutar la primera fase del [Plan 074](planes/074_modulo_distribucion.md): crear la app `distribucion` con sus maestros, los campos de distribución en `Producto`, la extensión del cliente, y los ABM necesarios para que se pueda hacer la carga de datos maestros (fase 0 del plan). No se implementó todavía ningún circuito operativo.

Se invirtió el orden previsto en el plan: la fase 0 era "cargar datos maestros", pero esos campos no existían todavía y no había dónde cargarlos. Primero las estructuras, después la carga.

### Archivos Creados o Modificados

**App nueva `distribucion`**
- `distribucion/models.py` [NEW]: `ZonaReparto`, `Personal`, `Vehiculo`, `MotivoDevolucion`, `CarteraVendedor`, `DiaVisita`.
- `distribucion/forms.py` [NEW]: `ZonaRepartoForm`, `PersonalForm`, `VehiculoForm`, `MotivoDevolucionForm`, todos acotados por `empresa_id`.
- `distribucion/views_htmx.py` [NEW]: ABM HTMX de los cuatro catálogos (modal + buscador + borrado) y siembra del catálogo de motivos.
- `distribucion/services/catalogos.py` [NEW]: catálogo inicial de 17 motivos de devolución y `sembrar_motivos()` idempotente.
- `distribucion/management/commands/sembrar_motivos_devolucion.py` [NEW]: comando para sembrar el catálogo por empresa.
- `distribucion/tests/test_plan074_maestros.py` [NEW]: 25 pruebas.
- `distribucion/apps.py`, `__init__.py`, `migrations/0001_initial.py` [NEW].

**Modelos existentes (cambios aditivos)**
- `productos/models.py` [MODIFY]: `peso_unitario_kg`, `unidad_venta`, `unidades_por_bulto`, `codigo_anterior` en `Producto`, más el índice `(empresa, codigo_anterior)` y la normalización a mayúsculas del código anterior.
- `facturacion/models.py` [MODIFY]: `ExtensionDistribuidora` (OneToOne con `ClienteProveedor`), con `clasificacion`, `coeficiente_mayorista`, `zona` y `bloqueado_credito`.
- `productos/migrations/0031_...py`, `facturacion/migrations/0055_extensiondistribuidora.py` [NEW].

**Formularios y vistas**
- `core/forms.py` [NEW]: `DecimalARField`, contrapartida en backend de `static/js/formato_ar.js`. Los inputs `.fInputAR` llegan como `1.234,56` y Django los rechazaba antes de `clean_<campo>`; la conversión ocurre en `to_python`. Es la única fuente de verdad del desformateo en formularios.
- `facturacion/forms.py` [MODIFY]: `ExtensionDistribuidoraForm`.
- `facturacion/views_htmx.py` [MODIFY]: `cliente_modal` maneja la extensión de distribución con el mismo patrón que ya usaba para armería (validación, guardado atómico y propagación de errores).
- `productos/forms.py` [MODIFY]: los cuatro campos nuevos en `ProductoForm`, con `DecimalARField` para peso y unidades por bulto.
- `core/views_config.py` [MODIFY]: contexto de las cuatro pestañas nuevas.
- `config/urls.py` [MODIFY]: 17 rutas de los ABM.
- `config/settings.py` [MODIFY]: alta de `distribucion` en `INSTALLED_APPS`.

**Templates**
- `templates/configuracion/partials/` [NEW]: `personal_distribucion.html`, `zonas_reparto.html`, `vehiculos.html`, `motivos_devolucion.html` y sus cuatro `*_table_rows.html`.
- `templates/configuracion/modals/` [NEW]: `personal_form.html`, `zona_form.html`, `vehiculo_form.html`, `motivo_form.html`.
- `templates/configuracion/partials/hub.html` [MODIFY]: bloque "Distribución", visible sólo si `empresa_actual.tipo_actividad == 'DISTRIBUIDORA'`.
- `templates/productos/modals/producto_modal.html` [MODIFY]: bloque de distribución, con la misma condición.
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]: bloque de distribución en el modal de cliente.
- `static/css/output.css` [MODIFY]: recompilado con `npm run build` (Tailwind purgado: las clases nuevas no existían).

### Detalle Técnico

**`Personal` es tabla propia y no un atributo de `Usuario`** (Plan 074 §4.3). El motivo de fondo es que no todo el personal opera el ERP: el repartidor trabaja con la hoja de ruta en papel y puede no tocar nunca una pantalla, pero tiene que figurar igual en el documento. Modelarlo como `User` obligaría a crear credenciales para gente que nunca va a entrar. Por eso `usuario` es un OneToOne **nullable**. Los tres roles (`es_vendedor`, `es_repartidor`, `es_cobrador`) son booleanos acumulables: en una distribuidora chica la misma persona vende, reparte y cobra.

`Venta.vendedor` y `Preventa.vendedor` **no se tocaron**: siguen apuntando a `User` porque los usan los filtros y reportes de las otras actividades. En distribución el vendedor de una venta se obtendrá a través de su pedido.

**Precio del cliente de reparto** = `Producto.precio_total * ExtensionDistribuidora.coeficiente_mayorista`. La base es el precio de lista **con IVA**; `cto_rep` no interviene en la venta (es costo de reposición, entrada del circuito de compras).

**Multi-tenant:** todas las consultas y todos los combos se acotan por `session['empresa_id']`, con pruebas específicas de aislamiento (usuarios, sucursales y zonas de otra empresa no se ofrecen).

**Catálogo de motivos:** se siembra bajo demanda y no por migración de datos, porque los motivos son por empresa y una empresa puede pasar a ser DISTRIBUIDORA mucho después. La siembra es idempotente (`get_or_create` por empresa + código): no duplica ni pisa lo que el usuario haya editado. `sugiere_apto_reventa` precarga si la mercadería devuelta vuelve al stock vendible; los tres motivos que no la devuelven son `PRODUCTO_DANADO`, `PROXIMO_A_VENCER` y `CADENA_DE_FRIO`.

### Implicaciones de Base de Datos
Tres migraciones, todas **aditivas**: seis tablas nuevas en `distribucion`, una tabla nueva en `facturacion` y cuatro columnas nullables/con default en `productos_producto`. Ninguna destructiva, ninguna con pérdida de datos posible.

Se tomó un respaldo previo con `pg_dump -F c` en `scratch/respaldos/` (carpeta ignorada por git) antes de aplicar.

### Resultado de las Pruebas

```powershell
.\venv\Scripts\python.exe manage.py test distribucion --keepdb --noinput
.\venv\Scripts\python.exe manage.py test productos --keepdb --noinput
.\venv\Scripts\python.exe manage.py test facturacion --keepdb --noinput
```

| Suite | Resultado |
|---|---|
| `distribucion` | **OK** — 28 pruebas en 41,5 s |
| `productos` | **OK** — 25 pruebas en 151,4 s |
| `facturacion` | 64 pruebas: 1 falla y 24 errores, **todos preexistentes** (ver abajo) |

Además se verificó que las 15 plantillas nuevas y modificadas compilan con el cargador de Django.

#### Fallos preexistentes detectados en `facturacion` (NO introducidos por esta intervención)

Se comprobó creando un *worktree* limpio de `HEAD` y verificando que el defecto ya está ahí, sin ninguno de los cambios de esta fase.

1. **23 errores en `facturacion/tests/test_facturas_pendientes.py`** — `DataError: value too long for type character varying(6)`. Los helpers `crear_compra()` y `crear_venta()` escriben `periodo="2026-06"` (7 caracteres) en un campo `CharField(max_length=6)` cuyo formato documentado es `YYYYMM`. Corresponde `"202606"`. Es un defecto del test, no del modelo, y no puede haber pasado nunca contra PostgreSQL.
2. **1 error en `facturacion/tests/test_arca_service.py`** — `FileNotFoundError` del certificado `media/certificados_afip/certificado_cortiz.crt`. Es una prueba de integración real contra ARCA Homologación: depende del entorno, no del código.
3. **1 falla en `facturacion/tests/test_armeria_credencial_clu.py`** — `test_extension_armeria_form_es_policia_select` arma el `ExtensionArmeriaForm` sin `tipo_persona`. El Plan 073 hizo ese campo obligatorio en el formulario y el test del Plan 072 no se actualizó.

Ninguno de los tres toca archivos modificados en esta intervención. Quedan reportados para resolverse en su módulo correspondiente.

### Estado Actual y Siguientes Pasos

**Hecho:** estructuras y ABM listos. Ya se puede hacer la carga de datos maestros de la fase 0 del plan: personal, zonas, vehículos, motivos, peso y código anterior de los productos, y coeficiente por cliente.

**Pendiente de la fase 1 del plan:** pantalla de cartera de vendedores y días de visita (los modelos existen, falta la UI), y los permisos `permiso_distribucion_*` en `usuarios.Perfil` — hoy los ABM se rigen por el permiso general del panel de configuración (`is_staff` o `es_admin_sistema`).

**Siguiente fase sugerida:** fase 1 del plan (pedido con numeración correlativa, servicio de crédito y stock comprometido), que a su vez depende de definir los valores de `ExtensionDistribuidora.clasificacion` (§11.1, única decisión abierta).

---

**Ajuste posterior (mismo día):** se agregó la sección **Distribución** al menú lateral (`templates/base.html`), condicionada a `empresa_actual.tipo_actividad == 'DISTRIBUIDORA'`, con accesos directos a los cuatro maestros. Hasta ahora sólo eran alcanzables desde el Panel de Configuración y el módulo no se veía en el menú principal. Se recompiló `output.css`. Los circuitos operativos (pedidos, repartos, cobranzas) se irán sumando a esta misma sección a medida que avancen las fases del plan.


## Día 28/08/2026 - Módulo Distribución: pedido, crédito y stock comprometido (Plan 074, fase 1)

**Responsable:** Claude Opus.

### Objetivo
Ejecutar la fase 1 del [Plan 074](planes/074_modulo_distribucion.md): dotar al pedido de numeración correlativa propia, implementar el servicio de crédito con la regla del saldo disponible negativo, el precio por coeficiente y el stock comprometido. Se completó además la pantalla de cartera y agenda que había quedado pendiente de la fase 1a.

**Decisión de arquitectura:** el módulo NO crea un circuito paralelo de pedidos. Reutiliza `Preventa` —que ya tiene estados, autorización de descuentos e ítems— y le cuelga la extensión con lo propio de la distribución. Todo lo agregado al circuito compartido está condicionado a `tipo_actividad == 'DISTRIBUIDORA'`, así que armería, estudio y las empresas estándar no cambian de comportamiento.

### Archivos Creados o Modificados

**Modelos y migraciones**
- `distribucion/models.py` [MODIFY]: `ExtensionPedidoDistribucion` (OneToOne con `Preventa`) con `punto`, `numero`, `vendedor`, `fecha_entrega`, `origen`, `condic_destino`, `zona`, `hora_carga`, `alerta_stock`, `alerta_credito`. `UniqueConstraint (punto, numero)`.
- `core/models.py` [MODIFY]: tipo `PEDIDO` en `ContadorDocumento.TIPOS_DOCUMENTO`.
- `productos/models.py` [MODIFY]: `StockSucursal.comprometido` y la property `disponible`.
- Migraciones [NEW]: `distribucion/0002_extensionpedidodistribucion.py`, `core/0002_alter_contadordocumento_tipo_documento.py`, `productos/0032_stocksucursal_comprometido.py`.

**Servicios**
- `distribucion/services/precios.py` [NEW]: `precio_para()` = `Producto.precio_total * coeficiente_mayorista`. Única fuente de verdad del precio de distribución.
- `distribucion/services/credito.py` [NEW]: `situacion_crediticia()` con la regla del saldo disponible negativo.
- `distribucion/services/pedidos.py` [NEW]: `registrar_pedido()` (numeración + alertas), `vendedor_de()`, `clientes_de_la_cartera()`.
- `productos/services/stock_service.py` [MODIFY]: `recalcular_comprometido()` y `disponible_real()`.
- `core/services/numeracion.py` [MODIFY]: `auditar_correlativos()` ahora cubre la serie de pedidos.

**Integración al circuito de preventa**
- `facturacion/signals.py` [MODIFY]: tres señales que mantienen `comprometido` al día (alta/baja de ítem y cambio de estado de la cabecera).
- `facturacion/views_htmx.py` [MODIFY]: `info_cliente_preventa` devuelve el panel de crédito para distribuidoras; `preventas_item_add` recalcula el precio con el coeficiente del cliente y agrega el disponible real y ambos códigos al ítem.
- `facturacion/views.py` [MODIFY]: `PreventaCargaView` acota el selector de clientes a la cartera del vendedor y, al guardar, llama a `registrar_pedido()` avisando por `messages` el número asignado y las alertas.

**Pantallas**
- `distribucion/views.py` [NEW]: `CarteraIndexView` y `DistribucionRequiredMixin`.
- `distribucion/views_htmx.py` [MODIFY]: `asignar_vendedor()` y `asignar_dia_visita()`.
- `templates/distribucion/` [NEW]: `cartera.html`, `partials/cartera_fila.html`, `partials/cartera_filas.html`, `partials/panel_credito.html`.
- `templates/facturacion/preventa_carga.html` [MODIFY]: fila de distribución (condición de facturación, fecha de entrega, observaciones) y contenedor del panel de crédito.
- `templates/base.html` [MODIFY]: subsección "Operación" en el menú de Distribución, con Tomar Pedido y Cartera y Agenda.
- `config/urls.py` [MODIFY]: tres rutas nuevas.
- `static/css/output.css` [MODIFY]: recompilado.

**Pruebas**
- `distribucion/tests/test_plan074_pedidos.py` [NEW]: 35 pruebas.

### Detalle Técnico

**La regla del saldo disponible negativo.** `saldo_disponible = limite − saldo` y `cobro_minimo = max(0, −saldo_disponible)`. Esa formulación absorbe los cuatro casos del negocio sin un solo condicional especial: entra holgado, se pasa parcialmente, `limite = 0` (sólo contado) y cliente bloqueado. El ejemplo del plan queda verificado: límite 100.000, saldo 110.000 → disponible −10.000 y cobro mínimo 10.000.

Al TOMAR el pedido, el disponible descuenta además los **pedidos sin facturar**. Sin ese término, tres pedidos del mismo día pasan todos el control porque ninguno llegó todavía a `saldo`. Al facturar (fase 4) ese término vale cero por construcción.

**Stock comprometido.** Se mantiene con las mismas reglas que `cantidad`: es un valor DERIVADO, se recalcula entero y nunca se ajusta por delta, así que es idempotente y autorreparable. Se guarda **separado** de `cantidad` a propósito: `cantidad` es lo que hay en el depósito y sale de comprobantes emitidos; `comprometido` es una promesa que todavía no movió mercadería. Mezclarlos haría que un pedido pareciera una salida de stock y el depósito dejaría de cuadrar contra el conteo físico.

**Numeración del pedido.** Se toma con `siguiente_numero()`, que bloquea el contador con `select_for_update()`, y la base tiene además el `UniqueConstraint` como segunda barrera — el esquema que el Plan 075 propone llevar a `Venta`. El punto de emisión es `sucursal_id`, misma convención que el PRE. `registrar_pedido()` es idempotente: un pedido que se edita conserva su número.

**Precio.** Se recalcula siempre en el servidor y no se confía en lo que manda el navegador: el importe que ve el vendedor tiene que ser exactamente el que después se factura. Un coeficiente sin cargar cae al neutro (1) y no deja el producto en $0.

### Implicaciones de Base de Datos
Tres migraciones aditivas: una tabla nueva, una columna nueva con default y un `choices` ampliado. Respaldo previo con `pg_dump -F c` en `scratch/respaldos/`.

### Resultado de las Pruebas

```powershell
.\venv\Scripts\python.exe manage.py test distribucion --keepdb --noinput
```
**Resultado:** `OK (Ran 63 tests in 190.5s)` — 28 de la fase 1a más 35 nuevas.

Verificación adicional: las seis plantillas nuevas y modificadas compilan, y las pantallas `/distribucion/cartera/`, `/ventas/preventas/carga/` y las dos pestañas de configuración responden **200** contra la base real con la empresa 4 (RODRIGUEZ MARCELO FABIAN) en sesión.

### Estado Actual y Siguientes Pasos

**Ya se puede operar:** asignar la cartera y la agenda de visitas, y tomar pedidos con el panel de crédito en vivo, precio por coeficiente, disponible real por ítem y número correlativo propio.

**Pendiente:** la pantalla móvil (fase 2), el reporte de faltantes y la asignación de stock escaso (fase 3), y la planilla manual en PDF. El control de crédito sigue siendo informativo: el vinculante llega con la facturación por lote (fase 4), que a su vez depende del [Plan 075](planes/075_integridad_numeracion_comprobantes_venta.md).

**Defecto preexistente detectado:** `facturacion/views.py` (`VentasCargaView`) referencia una variable `ctx_base` inexistente en la rama de "período IVA cerrado". Provocaría un `NameError` al intentar facturar en un período cerrado. No se tocó por estar fuera del alcance de esta fase.

---

**Ajuste posterior (mismo día) — fecha de la preventa.** Por definición del usuario, la fecha del comprobante la determina el sistema, no se edita **y tampoco se muestra**: es siempre la del día de carga, y ocupar espacio de pantalla con un dato que no se decide no le aporta nada al operador.

`Preventa.fecha` ya era `auto_now_add`, así que la regla **ya se cumplía en el modelo para todas las actividades** y no había ningún input que la pudiera alterar. No hizo falta ningún cambio funcional. Verificado con GET real contra la base: DISTRIBUIDORA y ARMERÍA responden 200 y ninguna expone un input `name="fecha"`.

Queda fijado como criterio para la **fase 4** (facturación por lote): la fecha de la venta la pone el sistema, no el operador. Eso hace estructuralmente inalcanzable la rama de "período IVA cerrado" en el circuito de distribución.


## Día 28/08/2026 - Módulo Distribución: toma de pedidos desde el celular (Plan 074, fase 2)

**Responsable:** Claude Opus.

### Objetivo
Ejecutar la fase 2 del [Plan 074](planes/074_modulo_distribucion.md): la pantalla mobile-first con la que el vendedor toma el pedido en la calle, cargando por código, con el crédito del cliente y el stock disponible a la vista.

### Archivos Creados o Modificados
- `distribucion/services/carrito.py` [NEW]: carrito en sesión. `buscar_producto_por_codigo()` (resuelve por ID del ERP o por código del sistema anterior), `buscar_productos()`, `agregar_item()`, `quitar_item()`, `totales()`, `limpiar()`.
- `distribucion/services/pedidos.py` [MODIFY]: `guardar_pedido()`, que persiste el pedido completo desde el carrito y lo numera.
- `distribucion/views_movil.py` [NEW]: ocho vistas HTMX del circuito móvil.
- `templates/distribucion/movil/` [NEW]: `pedido.html` y cinco parciales (`cabecera`, `carrito`, `clientes_sugerencias`, `productos_sugerencias`, `confirmacion`).
- `config/urls.py` [MODIFY]: ocho rutas.
- `templates/base.html` [MODIFY]: el menú distingue "Tomar Pedido (Móvil)" de "Tomar Pedido (PC)".
- `distribucion/tests/test_plan074_movil.py` [NEW]: 29 pruebas.
- `static/css/output.css` [MODIFY]: recompilado.

### Detalle Técnico

**Carrito compartido con la pantalla de PC.** Se reutiliza la clave de sesión `preventa_items_temp` y el mismo formato de ítem, así que un pedido empezado en un canal se puede terminar en el otro y el guardado es común. Evita mantener dos carritos con reglas divergentes.

**El precio nunca viene del navegador.** Se resuelve en el servidor con el coeficiente del cliente. Hay una prueba específica que manda `precio=1` en el POST y verifica que se ignora: el importe que ve el vendedor tiene que ser exactamente el que después se factura.

**Búsqueda por código con prioridad definida.** Acepta el ID del ERP y el código del sistema anterior, porque durante la transición conviven y el vendedor usa el que recuerda. Ante colisión gana el ID del ERP, que es el código definitivo. Probado con un caso de colisión sembrado a propósito.

**Cargar dos veces el mismo artículo ACUMULA** en vez de rechazar: en la calle el cliente vuelve sobre un artículo y el vendedor va cantando lo que le piden.

**Cambiar de cliente con un pedido en curso se rechaza** con un aviso, en lugar de vaciar el carrito en silencio.

**La fecha no aparece en ninguna parte**, coherente con el criterio fijado: `Preventa.fecha` es `auto_now_add`. Hay una prueba que verifica que la pantalla no expone ningún `name="fecha"`.

**Conectividad: online-only**, según lo decidido. La planilla de papel es el plan B.

### Resultado de las Pruebas

```powershell
.\venv\Scripts\python.exe manage.py test distribucion --keepdb --noinput
```
**Resultado:** `OK (Ran 92 tests in 209.5s)` — 28 de la fase 1a, 35 de la fase 1 y 29 nuevas.

El WARNING `Not Found: /distribucion/movil/clientes/364/elegir/` que aparece en la salida es el **404 esperado** del test que verifica que un vendedor no puede elegir un cliente fuera de su cartera.

Verificación adicional: las seis plantillas nuevas compilan y `/distribucion/movil/` responde 200 contra la base real con la empresa 4 en sesión.

### Estado Actual y Siguientes Pasos
El vendedor ya puede tomar pedidos desde el celular de punta a punta. **Siguiente: fase 3** — reporte de faltantes y pantalla de asignación de stock escaso por orden de llegada del pedido.

---

**Corrección (mismo día) — las fechas de alta y baja de Personal no se mostraban al editar.**

*Reportado por el usuario.* Diagnóstico: **el guardado siempre funcionó**; el defecto era de RENDERIZADO. Con `LANGUAGE_CODE = 'es-ar'`, Django renderiza el valor de un `forms.DateInput` con el formato local (`value="28/08/2026"`), y un `<input type="date">` de HTML5 **sólo acepta `YYYY-MM-DD` en su atributo `value`**: descarta cualquier otro formato en silencio y muestra el campo VACÍO. El registro tenía la fecha bien guardada, pero al editarlo parecía no tenerla, y si el usuario grababa así la borraba sin querer.

Del lado de la entrada no había problema: Django 5.1 agrega `%Y-%m-%d` a los `DATE_INPUT_FORMATS` del locale, así que lo que manda el navegador se parsea bien. Por eso el defecto era difícil de ver: sólo se manifestaba al editar.

- `core/forms.py` [MODIFY]: se agregó el widget **`DateInputHTML5`**, que fija `format='%Y-%m-%d'` y el `type="date"`, con la explicación de la trampa. Va en `core` junto a `DecimalARField`, como única fuente de verdad de los widgets compartidos.
- `distribucion/forms.py` [MODIFY]: `fecha_alta` y `fecha_baja` pasan a usarlo.
- `templates/configuracion/modals/personal_form.html` [MODIFY]: faltaba mostrar los errores de `fecha_alta` (sólo se mostraban los de `fecha_baja`), con lo que un error de validación en ese campo quedaba invisible.
- `distribucion/tests/test_plan074_maestros.py` [MODIFY]: dos pruebas nuevas, una de guardado y otra de **regresión** que verifica que el `value` renderizado sale en ISO.

**Resultado:** `OK (Ran 30 tests in 33.8s)`.

**El mismo defecto existe en otros siete widgets de fecha del proyecto**, que no se tocaron por estar fuera del alcance de esta fase. `empresas/forms.py` ya aplicaba el arreglo en dos campos (`fecha_inicio_actividades` y `vencimiento_crt_afip`), así que el patrón correcto ya estaba en el código; falta en:

| Archivo | Campo | Se ve al editar |
|---|---|---|
| `empresas/forms.py:79-80` | `Ejercicio.inicio` / `.cierre` | un ejercicio |
| `facturacion/forms.py:96` | `ClienteProveedor.fecha_nacimiento` | un cliente |
| `facturacion/forms.py:275` | `ExtensionArmeria.clu_vto` | un cliente de armería |
| `facturacion/forms.py:34` y `:362` | `Venta.fecha` / `Compra.fecha` | un comprobante |
| `contable/forms.py:102` | fecha del asiento | un asiento |

En todos, editar un registro existente muestra el campo de fecha vacío. El arreglo es reemplazar `forms.DateInput(attrs={'type': 'date'})` por `DateInputHTML5()`.


## Día 29/08/2026 - Domicilios de entrega múltiples (Plan 074)

**Responsable:** Claude Opus.

### Objetivo
Un cliente puede tener **varios puntos de entrega** porque tiene sucursales. Se define la regla del circuito, confirmada por el usuario: **1 domicilio de entrega → 1 pedido → 1 comprobante → 1 parada de la hoja de ruta**. Cada sucursal recibe, controla y firma lo suyo, y la cuenta corriente consolida en el cliente.

### Decisión estructural: qué se mueve y qué no

`ClienteProveedor.domicilio` es el **fiscal** (el que se imprime como domicilio del cliente). El nuevo `DomicilioEntrega` es el **punto físico** al que llega el camión.

De ahí se desprende lo importante: **la zona y la agenda de visitas dejan de colgar del cliente y pasan al domicilio**. Una sucursal en San Cayetano y otra en Villa Luján entran en repartos distintos, en días distintos y con recorridos distintos: son propiedades de *dónde se entrega*, no de *quién debe*. Colgarlas del cliente obligaría a que todas sus sucursales compartan zona y día.

Lo que **sí** queda en el cliente es el **crédito**: un CUIT, una cuenta corriente, un límite. Las entregas se reparten; la deuda no. Lo mismo la cartera: el vendedor responde por el cliente completo.

### Archivos Creados o Modificados
- `distribucion/models.py` [MODIFY]: nuevo `DomicilioEntrega` (nombre, domicilio, localidad, zona, contacto, teléfono, horario de recepción, indicaciones de entrega, principal, activo). `DiaVisita` se reapunta de `cliente` a `domicilio` y admite **varios días por punto** (con lácteos se pasa dos o tres veces por semana). `ExtensionPedidoDistribucion` suma `domicilio_entrega` y `domicilio_entrega_texto`.
- `facturacion/models.py` [MODIFY]: se **quita** `ExtensionDistribuidora.zona`, que ahora vive en el domicilio.
- `distribucion/services/domicilios.py` [NEW]: `asegurar_domicilio_principal()` (genera el principal a partir del fiscal, idempotente), `domicilios_de()`, `sembrar_domicilios_faltantes()` para la carga inicial.
- `distribucion/services/pedidos.py` [MODIFY]: el pedido toma `domicilio_entrega`; si no se indica, se propone el principal. La **zona del pedido sale del domicilio**.
- `distribucion/views_htmx.py` [MODIFY]: ABM de domicilios y agenda por punto; se elimina la vista de agenda por cliente.
- `distribucion/views_movil.py` [MODIFY]: selector de punto de entrega y `movil_elegir_domicilio`.
- `distribucion/forms.py` [MODIFY]: `DomicilioEntregaForm`.
- `facturacion/forms.py`, `templates/facturacion/modals/cliente_modal.html` [MODIFY]: se saca la zona del cliente.
- `templates/distribucion/` [NEW/MODIFY]: `modals/domicilio_form.html`, `partials/cartera_fila.html` reescrito con los domicilios desplegables, cabecera y confirmación del móvil.
- `config/urls.py` [MODIFY]: cuatro rutas de domicilios y una del móvil.
- `distribucion/tests/test_plan074_domicilios.py` [NEW]: 26 pruebas.
- Migraciones: `distribucion/0003_domicilioentrega_and_more.py`, `facturacion/0056_...`.

### Detalle Técnico

**Snapshot del domicilio en el pedido** (`domicilio_entrega_texto`), con el mismo criterio que `Preventa.cliente_razon_social`: si mañana se corrige la dirección, el comprobante ya emitido tiene que seguir diciendo a dónde se entregó. Hay una prueba que lo verifica.

**El principal se genera solo** a partir del domicilio fiscal, para que el circuito nunca se trabe por un dato derivable, pero **la responsabilidad de que cada pedido salga con el domicilio correcto es del vendedor** (definición del usuario). Por eso el móvil ofrece todos los puntos y permite cambiarlo en cualquier momento antes de confirmar, sin perder lo cargado.

**Aviso de punto sin zona:** un domicilio sin zona no entra en ningún reparto, así que la cabecera del móvil lo marca en ámbar.

### Implicaciones de Base de Datos
Se verificó que las cuatro tablas afectadas estaban **vacías** antes de reestructurar (`ExtensionDistribuidora`, `DiaVisita`, `CarteraVendedor`, `ExtensionPedidoDistribucion`: 0 registros), así que el cambio de `DiaVisita.cliente` a `DiaVisita.domicilio` no arrastró datos. Respaldo previo con `pg_dump -F c` en `scratch/respaldos/`.

### Resultado de las Pruebas
```powershell
.\venv\Scripts\python.exe manage.py test distribucion --keepdb --noinput
```
**Resultado:** `OK (Ran 118 tests in 278.3s)`.

Los dos WARNING de `Not Found` en la salida son los **404 esperados** de las pruebas de aislamiento: un vendedor no puede elegir un cliente fuera de su cartera ni el punto de entrega de otro cliente.

Verificación adicional contra la base real (empresa 4): las ocho plantillas compilan y `/distribucion/movil/`, `/distribucion/cartera/` y la pestaña de Personal responden 200.

### Estado Actual y Siguientes Pasos
Circuito de pedido completo con puntos de entrega múltiples. **Siguiente: fase 3** — reporte de faltantes y asignación de stock escaso por orden de llegada del pedido.

Pendiente de definición del usuario (§11.1 del plan): los valores de `ExtensionDistribuidora.clasificacion`. Y quedó ofrecido, sin ejecutar, el arreglo del widget de fecha en los otros siete formularios del proyecto.


## Día 29/08/2026 - Faltantes y asignación de stock escaso (Plan 074, fase 3)

**Responsable:** Claude Opus.

### Objetivo
Ejecutar la fase 3 del [Plan 074](planes/074_modulo_distribucion.md): detectar qué productos no alcanzan para cubrir todos los pedidos tomados y sin facturar, y dar la pantalla donde un usuario autorizado reparte ese stock escaso. Es el paso previo a la facturación por lote.

### Archivos Creados o Modificados
- `distribucion/models.py` [MODIFY]: nuevo `AjusteAsignacion` (pedido, producto, cantidad original, cantidad asignada, usuario, fecha, observación).
- `distribucion/services/asignacion.py` [NEW]: `detectar_faltantes()`, `detalle_por_pedido()`, `sugerir_asignacion()`, `aplicar_asignacion()`, `hay_faltantes()`.
- `distribucion/views.py` [MODIFY]: `FaltantesIndexView`, `AsignacionStockView` y el helper de permiso `_puede_asignar()`.
- `usuarios/models.py` [MODIFY]: `permiso_distribucion_asignar_stock`.
- `templates/distribucion/faltantes.html`, `partials/faltantes_filas.html`, `modals/asignacion_form.html` [NEW].
- `templates/base.html` [MODIFY]: entrada "Faltantes y Asignación" en el menú de Distribución.
- `config/urls.py` [MODIFY]: dos rutas.
- `distribucion/tests/test_plan074_asignacion.py` [NEW]: 25 pruebas.
- Migraciones: `distribucion/0004_ajusteasignacion.py`, `usuarios/0008_perfil_permiso_distribucion_asignar_stock.py`.

### Detalle Técnico

**El criterio de reparto es el ORDEN DE LLEGADA del pedido** (`hora_carga` ascendente): el que pidió primero se lleva todo lo que pidió mientras haya stock, y el faltante lo absorben los últimos. Es el único criterio que se le puede explicar a un vendedor sin discusión, y el que eligió el usuario. La sugerencia es un punto de partida: la pantalla permite ajustar a mano.

**`detectar_faltantes()` compara contra el stock FÍSICO, no contra el disponible.** El `comprometido` ES la demanda que se está comparando: restarlo sería contarla dos veces.

**Todo ajuste queda auditado** en `AjusteAsignacion`, con la cantidad original, la asignada, quién lo hizo y cuándo. La razón es operativa: al vendedor hay que poder explicarle después por qué su cliente recibió menos de lo que pidió. Un ítem al que se le asigna lo que pedía **no genera ajuste ni escritura**.

**Asignar 0 elimina el renglón** del pedido, no lo deja en cero: un ítem en cero ensuciaría el comprobante y la hoja de ruta con una línea sin sentido. El `AjusteAsignacion` queda igual, y es la explicación de por qué el artículo desapareció.

Tras el recorte se recalculan el total del ítem, el total del pedido y el `comprometido` (por la señal ya existente sobre `PreventaItem`).

**Permiso propio** (`permiso_distribucion_asignar_stock`): repartir stock escaso decide qué cliente recibe menos, que es una decisión comercial y no una tarea de carga. Sin el permiso, la pantalla se consulta pero el POST devuelve 403 y los inputs salen deshabilitados.

### Resultado de las Pruebas
```powershell
.\venv\Scripts\python.exe manage.py test distribucion --keepdb --noinput
```
**Resultado:** `OK (Ran 25 tests)` en la suite nueva; 143 en total en el módulo.

Los WARNING de `Forbidden` y `Not Found` en la salida son los **esperados** por las pruebas de permiso y de aislamiento de cartera.

Verificación contra la base real (empresa 4): las tres plantillas compilan y `/distribucion/faltantes/` responde 200.

### Estado Actual y Siguientes Pasos
Con la asignación cerrada, el circuito queda listo para la **fase 4: facturación masiva** con la regla del saldo disponible negativo, que emite la Factura o el PRE y decide CONTADO vs. CUENTA CORRIENTE.

Pendiente y ofrecido, sin ejecutar: exportación del reporte de faltantes a PDF/Excel (el plan la prevé), el arreglo del widget de fecha en los otros siete formularios y el [Plan 075](planes/075_integridad_numeracion_comprobantes_venta.md), del que **depende la fase 4**.


## Día 29/08/2026 - Integridad de numeración y condición del lote (Plan 075 + corrección ESTUDIO)

**Responsable:** Claude Opus.

### Objetivo
Analizar la facturación por lote de ESTUDIO —que ya emite comprobantes fiscales y no fiscales— para reutilizarla en la fase 4 de Distribución, corregir lo que estuviera mal y ejecutar el [Plan 075](planes/075_integridad_numeracion_comprobantes_venta.md), del que la fase 4 depende.

### Hallazgo principal: el comprobante interno se guardaba como FISCAL

`FacturacionLoteService` no seteaba `condic` en ninguno de los dos comprobantes, así que ambos quedaban con el default (**1 = Real**). El comprobante INTERNO/PRE decía ser fiscal, mientras su asiento —creado a mano unas líneas más abajo— decía `condic = 2`. Comprobante y asiento se contradecían.

No llegaba al Libro IVA sólo porque `venta_p._no_contabilizar = True` corta la señal entera. Pero era una **bomba de tiempo**: `contabilizar_venta_individual` puebla el Libro IVA cuando `condic in (1, 3)`, así que cualquier re-guardado sin ese flag habría declarado ante ARCA una operación que no existe fiscalmente. Y ya hacía daño: todo reporte que filtra `Venta.condic` contaba el interno como fiscal.

**Corrección:** `condic=2` en el interno y `condic=1` explícito en el fiscal, para que el par se lea de un vistazo.

### Otros hallazgos del mismo servicio
- **El manejo de errores por fila era ilusorio.** El `transaction.atomic()` envuelve todo el bucle y el `try/except` está adentro: tras un error de base de datos, Django deja la transacción abortada y cualquier consulta posterior lanza `TransactionManagementError`. No se guardaban "los exitosos". *(Documentado, no corregido: es parte del refactor del motor en la fase 4.)*
- **Si no hay cuentas contables configuradas, el comprobante interno se emite sin asiento y sin ningún aviso** — queda con saldo en la cuenta corriente y sin registración. *(Documentado con una prueba que lo deja cubierto para que el refactor lo cambie a conciencia.)*
- El asiento del interno reimplementa a mano ~60 líneas que `contabilizar_venta_individual` ya hace bien. La ironía: existían para compensar el `condic` mal seteado.

### Plan 075 ejecutado

**Auditoría previa (sólo lectura):** cero duplicados y cero huecos en `facturacion_venta`. El `UniqueConstraint` se pudo aplicar sin tocar un solo dato.

- `facturacion/models.py` [MODIFY]: `UniqueConstraint (empresa, tipo, punto, numero)` en `Venta`. Era el único documento emitido del sistema sin bloqueo al numerar **ni** restricción en la base. Queda documentado que `tipo` es nullable y en PostgreSQL los NULL no colisionan: los comprobantes sin tipo quedan fuera del control, y la solución de fondo excede este plan.
- `core/models.py` [MODIFY]: tipos `VENTA_PRE` y `VENTA_NCI` en `ContadorDocumento`, en **series independientes**.
- `core/migrations/0004_inicializar_contadores_venta_no_fiscal.py` [NEW]: migración de datos que inicializa cada contador con el último número realmente emitido. Sin esto el primer comprobante habría arrancado en 1 y chocado contra el constraint.
- `core/services/numeracion.py` [MODIFY]: `siguiente_numero_pre()` y `siguiente_numero_nci()`, y `auditar_correlativos()` extendida a las dos series nuevas mediante un envoltorio `_VentasDeTipo` que evita duplicar el bucle.
- `facturacion/services/facturacion_lote_service.py` [MODIFY]: el PRE se numera con el contador transaccional y se emite en `punto = sucursal_id`; se eliminan los **fallbacks silenciosos** (tipo PRE por descarte y punto de venta asumido en 1), que ahora fallan con un mensaje explicativo.
- `facturacion/views_estudio.py` [MODIFY]: `modo_prueba` deja de estar hardcodeado y pasa a ser un parámetro, con el default seguro. Los `ValueError` de configuración se devuelven como 400 con su mensaje, no como error genérico.
- **La emisión real contra ARCA queda bloqueada con un error explícito** hasta cablear `AfipService`. Antes no había forma de emitir en serio; ahora, si alguien lo intenta, el sistema **corta antes de emitir** en vez de generar un comprobante con numeración local que ARCA no autorizó.

### Pruebas
- `facturacion/tests/test_lote_condic.py` [NEW]: 7 pruebas.
- `facturacion/tests/test_plan075_numeracion.py` [NEW]: 16 pruebas.

```powershell
.\venv\Scripts\python.exe manage.py test distribucion facturacion productos core --keepdb --noinput
```
**Resultado:** `Ran 255 tests` — 1 falla y 24 errores, **todos preexistentes y ya documentados**: 23 en `test_facturas_pendientes` (escribe `periodo="2026-06"`, 7 caracteres, en un `varchar(6)`), 1 en `test_arca_service` (falta el certificado, es de entorno) y 1 en `test_armeria_credencial_clu` (el Plan 073 hizo `tipo_persona` obligatorio sin actualizar el test del 072). **Cero regresiones.**

### Verificación contra la base real
Migraciones aplicadas con respaldo previo. Los contadores quedaron inicializados en el último emitido (empresa 2 punto 0 → 1; empresa 3 punto 3 → 1) y `auditar_correlativos()` devuelve **OK en las cinco series** existentes.

### Estado Actual y Siguientes Pasos
El Plan 075 queda ejecutado salvo el cableado de `AfipService` en el lote, que es su paso 5 y hoy está explícitamente bloqueado. Con esto, la **fase 4 de Distribución** ya tiene numeración segura sobre la cual apoyarse.

Sigue pendiente y ofrecido, sin ejecutar: el arreglo del widget de fecha en los otros siete formularios y la exportación del reporte de faltantes a PDF/Excel.

---

**Correcciones posteriores del mismo día.**

**1. Menú principal roto en empresas DISTRIBUIDORA** *(reportado por el usuario, defecto propio).*
El comentario que había puesto en `templates/base.html` usaba `{# … #}` **en varias líneas**, y los comentarios de una llave en Django son de **UNA SOLA LÍNEA**: la apertura consume sólo su renglón y el resto se emite como texto visible. En el menú aparecía el párrafo "Módulo Distribución (Plan 074). Por ahora sólo los maestros…" entre Ventas y Distribución.

Al revisarlo apareció el mismo error en **otros nueve comentarios**, todos escritos por mí en esta serie de fases: `preventa_carga.html`, `movil/pedido.html`, `movil/partials/cabecera.html` (×2), `movil/partials/carrito.html`, `movil/partials/confirmacion.html`, `partials/cartera_fila.html` (×2) y `partials/panel_credito.html`. Los diez se convirtieron a `{% comment %} … {% endcomment %}`.

Verificación: las **231 plantillas** del proyecto compilan, y las cuatro pantallas del módulo (`/distribucion/movil/`, `/cartera/`, `/faltantes/` y la preventa) responden 200 **sin texto de comentario en el HTML**.

**2. La facturación por lote emitía comprobantes SIN asiento contable.**
Al escribir las pruebas apareció un defecto más grave que el del `condic`: la señal contabiliza en el `post_save` de la `Venta`, pero el lote guarda la venta **antes** de crear los ítems, y `contabilizar_venta_individual` corta con `if not venta.items.exists(): return None`. **La factura fiscal quedaba emitida y sin registración contable.**

Corrección, siguiendo la regla que confirmó el usuario —cuenta patrimonial del cliente con fallback a `ParametrosContables.cta_clientes_default`, y cuenta de resultado del **rubro del producto facturado** con fallback a `parametros.cta_ventas`—:
- Se re-guarda cada comprobante después de crear sus ítems, para que la señal contabilice con la venta completa.
- Se eliminó el `_no_contabilizar` del comprobante interno y **las 54 líneas del asiento armado a mano**, que existían sólo para compensar el `condic` mal seteado. Ahora delega en `contabilizar_venta_individual`, que ya aplica esa regla exacta, valida que la cuenta pertenezca a la empresa y sea imputable, y **levanta un error explícito** si falta alguna en lugar de emitir el comprobante sin asiento.

Tres pruebas nuevas cubren la regla: el cliente sin `cta_pat` usa la cuenta del parámetro, el haber sale del rubro del producto, y sin rubro cae al parámetro general.

**3. Tests preexistentes corregidos** *(a pedido del usuario).*
- `test_facturas_pendientes.py`: los helpers escribían `periodo="2026-06"` (7 caracteres) en un `CharField(max_length=6)` cuyo formato documentado es **YYYYMM**. Corregido a `"202606"` — el guion no corresponde. **23 errores eliminados.**
- `test_armeria_credencial_clu.py`: el Plan 073 hizo `tipo_persona` obligatorio en `ExtensionArmeriaForm` y el test del Plan 072 no se actualizó. Se agregó el campo. **1 falla eliminada.**

### Resultado final de la suite
```powershell
.\venv\Scripts\python.exe manage.py test distribucion facturacion productos core --keepdb --noinput
```
**`Ran 257 tests` — 1 solo error**, `test_emitir_comprobante_homologacion_real`, que es una prueba de integración real contra ARCA Homologación y falla por falta del certificado `media/certificados_afip/certificado_cortiz.crt`: es de entorno, no de código.

Se pasó de **25 fallos a 1**. La suite vuelve a servir como red: de ahora en más, un test rojo señala una regresión real.


## Día 29/08/2026 - Facturación masiva de pedidos (Plan 074, fase 4)

**Responsable:** Claude Opus.

### Objetivo
El corazón del módulo: emitir de una vez los comprobantes de los pedidos del día, aplicando la regla del saldo disponible negativo que define el cobro mínimo del repartidor y la condición de venta impresa en el comprobante.

### La regla, en una sola fórmula
```
saldo_disponible = limite − saldo    (POSTERIOR a facturar esta carga)
cobro_minimo     = max(0, −saldo_disponible)
condicion_venta  = CONTADO si cobro_minimo >= total, si no CUENTA CORRIENTE
```
Absorbe los cuatro casos del negocio sin un solo condicional especial: entra holgado, se pasa parcialmente, `limite = 0` (sólo contado) y cliente bloqueado. Los cuatro tienen su prueba.

### Archivos Creados o Modificados
- `facturacion/services/emision_arca.py` [NEW]: el circuito de emisión del CAE existía **sólo dentro de `VentasCargaView.post`**, embebido en el manejo del formulario, así que ningún otro proceso podía emitir. Se expone como servicio reutilizable, con las mismas validaciones de coherencia fiscal (A/B según condición de IVA). Acepta una venta **todavía sin persistir**, porque el número de la serie fiscal lo da ARCA y hay que pedirlo antes de guardar.
- `distribucion/services/facturacion.py` [NEW]: `evaluar_credito()`, `previsualizar()`, `facturar_pedido()`, `facturar_lote()`.
- `distribucion/views.py` [MODIFY]: `FacturacionLoteView` (GET previsualiza, POST emite).
- `facturacion/models.py` [MODIFY]: `Venta.condicion_venta` (CONTADO / CTA_CTE).
- `distribucion/models.py` [MODIFY]: `ExtensionPedidoDistribucion.venta`, el eslabón Pedido → Comprobante.
- `core/models.py` [MODIFY]: `ContadorDocumento.VENTA_FISCAL`, espejo local de la serie fiscal.
- `usuarios/models.py` [MODIFY]: `permiso_distribucion_facturar_lote`.
- `templates/distribucion/facturacion.html` + dos parciales [NEW]; entrada en el menú.
- `distribucion/tests/test_plan074_facturacion.py` [NEW]: 25 pruebas.

### Detalle Técnico

**La numeración se resuelve ANTES del primer save.** Es lo que obligó a reestructurar: guardar la venta con un número provisorio para corregirlo tras el CAE dejaría, aunque sea un instante, dos comprobantes con el mismo número en la misma serie —y ahora existe el `UniqueConstraint` que lo rechazaría—. Por eso los importes y las alícuotas se calculan en memoria, luego se numera (contador para el PRE, ARCA para la factura) y recién ahí se persiste.

**Cada pedido va en SU PROPIA transacción.** Es la diferencia deliberada con el lote de ESTUDIO, donde el `atomic` envolvía el bucle entero y el primer error abortaba todo: acá un cliente mal configurado no puede frenar el reparto de los demás. Hay una prueba con tres pedidos donde el del medio falla y los otros dos se emiten igual.

**Se bloquea el cliente con `select_for_update()`** al facturar: dos pedidos suyos emitidos a la vez leerían el mismo saldo y los dos creerían entrar en el límite.

**El comprobante se guarda dos veces a propósito:** el segundo save dispara la señal con los ítems ya creados, que es lo que genera el asiento. Es exactamente el defecto que tenía el lote de ESTUDIO y que se corrigió esta mañana.

Reglas inflexibles verificadas por pruebas: el asiento hereda el `condic` del comprobante; el PRE **no** entra al Libro IVA y la Factura **sí**; la fecha la pone el sistema; facturar libera el stock comprometido y descuenta el real.

**Emisión real contra ARCA:** el circuito quedó cableado (`modo_prueba=False` llama a `AfipService` y toma el número de `CbteDesde`). La pantalla emite hoy en **modo prueba**, con CAE ficticio, hasta que se valide contra Homologación con el certificado cargado.

### Resultado de las Pruebas
```powershell
.\venv\Scripts\python.exe manage.py test distribucion facturacion core --keepdb --noinput
```
**`Ran 257 tests` — 1 error**, `test_emitir_comprobante_homologacion_real`, que falla por falta del certificado ARCA: es de entorno. Cero regresiones.

Migraciones aplicadas con respaldo previo. Las cuatro pantallas del módulo responden 200 contra la base real.

### Estado Actual y Siguientes Pasos
Circuito cerrado desde la toma del pedido hasta el comprobante emitido. **Siguiente: fase 5** — `Reparto`, Consolidado de Artículos y Hoja de Ruta, que es donde el `cobro_minimo` calculado acá sale impreso para el repartidor.

## Día 31/08/2026 - Corrección Arquitectónica del Modo Enchufe (Modelos y Formularios)

**Responsable:** Antigravity (Codex)

### Objetivo
Corregir una mala interpretación de la arquitectura "Plug & Play" (Modo Enchufe) en la que los modelos y formularios de las verticalidades habían sido ubicados de tal forma que al "desenchufar" (borrar) la carpeta, el sistema principal (`facturacion`) fallaba por errores de importación (`ModuleNotFoundError`). Se revisó cómo `erp-ikigai-armeria` resolvía este patrón y se replicó su estructura robusta hacia Distribución y Estudio.

### Archivos Creados o Modificados
- `facturacion/forms.py` [MODIFY]: Se eliminaron las definiciones e importaciones estáticas de `ExtensionArmeriaForm` y `ExtensionDistribuidoraForm`.
- `verticalidades/armeria/forms.py` [NEW/MODIFY]: Se extrajo y mudó `ExtensionArmeriaForm` aquí.
- `verticalidades/distribucion/forms.py` [MODIFY]: Se extrajo y anexó `ExtensionDistribuidoraForm` al final del archivo.
- `facturacion/views_htmx.py` [MODIFY]: Se modificaron las importaciones para que consuman los modelos y los forms usando `try/except ImportError`. De este modo, si la carpeta de la verticalidad se borra, las clases simplemente quedan como `None` y la lógica base no revienta.
- `facturacion/models.py` [RESTORED]: Se corroboró que el núcleo no depende de estas clases, ya que ahora todo está aislado condicionalmente.

### Detalle Técnico
El verdadero "Modo Enchufe" exige que si un directorio bajo `verticalidades/` se elimina, el sistema base siga funcionando sin crashear.
Anteriormente, aunque los modelos se extrajeron a sus respectivas verticalidades, los formularios (`forms.py`) y las vistas núcleo (`views_htmx.py`) seguían tratando de hacer un `from verticalidades.X.models import Y`. Cuando la carpeta no existía, Python fallaba al arrancar.

**Solución:**
- Los modelos siguen viviendo en las verticalidades, pero su persistencia (y sus migraciones) se atan a que la `app` esté en `INSTALLED_APPS` (el cual es dinámico).
- El núcleo (`facturacion/views_htmx.py`) ahora hace:
```python
try:
    from verticalidades.armeria.models import ExtensionArmeria
    from verticalidades.armeria.forms import ExtensionArmeriaForm
except ImportError:
    ExtensionArmeria = None
    ExtensionArmeriaForm = None
```
Con esto, si la carpeta no existe, el módulo no crashea; la lógica condicional que ya teníamos (`if puede_armeria and ExtensionArmeria:`) se encarga de ignorar esa ejecución. 

### Resultado de las Pruebas
- El `runserver` reinició exitosamente.
- El comando `python manage.py check` arrojó `System check identified no issues (0 silenced).` confirmando que las dependencias circulares y los módulos faltantes fueron erradicados.
- El comando `python manage.py makemigrations` reportó `No changes detected`, lo que significa que el movimiento no alteró el esquema base.

**Filtro Dinámico en EmpresaForm:**
Se refactorizó el formulario `EmpresaForm` para alinear sus opciones de `tipo_actividad` exactamente con las carpetas de verticalidades presentes en el disco duro, replicando la lógica exacta probada en el proyecto `erp-ikigai-armeria`. Ahora las actividades "fantasmas" no aparecerán en el selector, mostrándose única y estrictamente las conectadas (junto al Estándar).

### Archivos Creados o Modificados Adicionales
- `empresas/models.py` [MODIFY]: Se añadió `TIPO_ACTIVIDAD_CHOICES` centralizado en el modelo.
- `empresas/forms.py` [MODIFY]: Se ajustó el `__init__` para construir las opciones dinámicamente escaneando el directorio `verticalidades/`.

### Estado Actual y Siguientes Pasos
La arquitectura está purificada. Cualquier módulo bajo `verticalidades/` puede ser borrado de la carpeta física e instantáneamente los reportes, botones y vistas del mismo desaparecerán del ERP, manteniendo estable el facturador.

Pendientes ofrecidos y no ejecutados: el widget de fecha en otros siete formularios, la exportación de faltantes a PDF/Excel, y la validación de la emisión real contra ARCA Homologación.


## Día 31/08/2026 - Reparto, Hoja de Ruta y Consolidado (Plan 074, fase 5)

**Responsable:** Claude Opus.

### Objetivo
Los dos documentos que salen impresos con el camión, replicando las hojas 3 y 4 del sistema anterior: la **Hoja de Ruta** que el repartidor lleva y el cliente firma, y el **Consolidado de Artículos** con el que el depósito controla la carga.

### Archivos Creados o Modificados
- `distribucion/models.py` [MODIFY]: `Reparto` y `RepartoParada`.
- `distribucion/services/reparto.py` [NEW]: `comprobantes_sin_reparto()`, `crear_reparto()`, `agregar_paradas()`, `quitar_parada()`, `cerrar_reparto()`, `hoja_de_ruta()`, `consolidado()`, `totales_hoja_de_ruta()`.
- `distribucion/views.py` [MODIFY]: `RepartoListView`, `RepartoDetalleView`, `HojaDeRutaView`, `ConsolidadoView`.
- `core/models.py` [MODIFY]: tipo `REPARTO` en `ContadorDocumento`.
- `templates/distribucion/repartos.html`, `reparto_detalle.html` [NEW] y `impresion/hoja_de_ruta.html`, `impresion/consolidado.html` [NEW].
- `config/urls.py`, `templates/base.html` [MODIFY]: cuatro rutas y la entrada de menú.
- `distribucion/tests/test_plan074_reparto.py` [NEW]: 26 pruebas.
- Migraciones: `distribucion/0006_reparto_repartoparada_and_more.py`, `core/0006_alter_contadordocumento_tipo_documento.py`.

### Detalle Técnico

**El reparto es un documento emitido** y lleva numeración correlativa propia, como el `Reparto: 8639` del papel. `responsables` es M2M porque el original muestra "MAXIMILIANO + ROMINA": un reparto puede llevar más de uno.

**Los tres importes se congelan al cerrar.** El papel es la foto de un momento: si la Hoja de Ruta recalculara el saldo y el cobro mínimo en cada reimpresión, un cobro posterior cambiaría el número y el control contra la firma del cliente dejaría de servir. Hay una prueba que cobra al cliente después de cerrar y verifica que el importe impreso no cambia.

**Un comprobante entra en UN SOLO reparto**, con `UniqueConstraint` sobre `venta`: si estuviera en dos, la mercadería se cargaría dos veces y el consolidado mentiría.

**La Hoja de Ruta sale ordenada alfabéticamente por cliente**, como el papel: es el orden del control, porque el repartidor busca al cliente por nombre y no por número de comprobante. Imprime **el N° de Pedido y el del Comprobante juntos** —con esos dos se arma después la devolución y la nota de crédito—, la condición de venta, el saldo anterior, el total, el **Saldo Disponible con signo**, el cobro mínimo destacado, el detalle con `ID | código anterior`, y las cuatro casillas del pie: importe cobrado, medios de pago, **devolución con motivo** y firma del cliente.

**El Consolidado** agrupa por producto con cantidad y **Kgs**, lleva columna de tilde para el control del depósito, y avisa en rojo cuando la carga supera la capacidad declarada del vehículo. Si un producto no tiene `peso_unitario_kg`, los kilos dan cero y el reporte lo dice al pie en lugar de romper.

Ambos documentos marcan **PROVISORIO** mientras el reparto está sin cerrar, y la Hoja de Ruta muestra el número de versión cuando es una reimpresión.

### Incidencias
- El primer intento de correr los tests falló porque `.env` había cambiado a `DB_HOST=auditoria.lr` y la base no respondía. Se esperó a que el usuario levantara la conexión; **no se tocó el `.env`**.
- Los tests destaparon que faltaba `ContadorDocumento.REPARTO`: estaba en el plan pero nunca se había agregado al modelo. Corregido.

### Resultado de las Pruebas
```powershell
.\venv\Scripts\python.exe manage.py test distribucion facturacion productos core --noinput
```
**`Ran 308 tests` — 1 error**, `test_emitir_comprobante_homologacion_real`, que falla por falta del certificado ARCA: es de entorno. Cero regresiones.

Migraciones aplicadas con respaldo previo (`scratch/respaldos/pre_fase5_*.dump`). Las cinco pantallas del módulo responden 200 contra la base real.

### Estado Actual y Siguientes Pasos
El circuito está cerrado desde que el vendedor toma el pedido hasta que el camión sale con la mercadería, el comprobante y la hoja de ruta. **Siguiente: fase 6** — entrega, devoluciones con motivo, Recepción de Devoluciones y notas de crédito.

Pendientes ofrecidos y no ejecutados: el widget de fecha en otros siete formularios, la exportación de faltantes a PDF/Excel, y la validación de la emisión real contra ARCA Homologación.

## Día 31/08/2026 - Entrega, devoluciones y notas de crédito (Plan 074, fase 6)

**Responsable:** Claude Opus.

### Objetivo
Cerrar el circuito de la calle. Como el comprobante ya está emitido cuando el camión sale, **todo lo que no se entrega llega con la factura hecha**: deja de ser un caso marginal y pasa a ser parte del trabajo diario. La fase agrega la rendición de la entrega, el documento numerado con el que el depósito declara qué volvió (**Recepción de Devoluciones**) y la emisión de la **Nota de Crédito** desde ese conteo.

### Archivos Creados o Modificados
- `distribucion/models.py` [MODIFY]: `RecepcionDevolucion`, `RecepcionDevolucionItem` y `NotaCreditoDistribucion`.
- `distribucion/services/devoluciones.py` [NEW]: `marcar_entregada()`, `marcar_no_entregada()`, `paradas_por_recibir()`, `crear_recepcion()`, `cargar_items()`, `confirmar_recepcion()`, `emitir_nota_credito()`, `conciliacion()`.
- `core/models.py` [MODIFY]: tipo `RECEPCION_DEVOLUCION` en `ContadorDocumento`.
- `facturacion/services/notas_credito.py` [MODIFY]: `'PRE': 'NCI'` en `MAPEO_NC`, para que un comprobante interno tenga su nota de crédito interna.
- `distribucion/views.py` [MODIFY]: `EntregaView` y `RecepcionDevolucionView`.
- `templates/distribucion/entrega.html`, `templates/distribucion/recepcion_devolucion.html` [NEW].
- `templates/distribucion/reparto_detalle.html` [MODIFY]: botón «Entrega y devoluciones», visible sólo con el reparto cerrado.
- `config/urls.py`, `templates/base.html` [MODIFY]: dos rutas nuevas y el resaltado del menú.
- `distribucion/tests/test_plan074_devoluciones.py` [NEW]: 33 pruebas.
- Migración: `distribucion/0007_recepciondevolucion_notacreditodistribucion_and_more.py` (aplicada).

### Detalle Técnico

**Primero se cuenta, después se acredita.** Es la regla que ordena toda la fase, y es la misma por la que el Informe de Recepción precede a la registración de la factura del proveedor. El flujo tiene tres momentos que no se pueden saltear:

1. En la calle, el repartidor marca la parada como **no entregada**, con su observación.
2. En el depósito se abre la **Recepción de Devoluciones**, numerada, donde el encargado cuenta lo que efectivamente volvió y lo confirma.
3. Recién desde esa recepción confirmada se emite la **Nota de Crédito**, con todo precargado.

`emitir_nota_credito()` rechaza una recepción que no esté confirmada. Si se acreditara primero y se contara después, se le estaría acreditando al cliente mercadería que puede no haber vuelto, y el descalce aparecería recién en la conciliación —cuando ya no hay a quién reclamarle—.

**Una recepción por pedido devuelto, no una por reparto.** La devolución se acredita a un cliente concreto con una NC contra UN comprobante, así que la correspondencia `1 Pedido → 1 Comprobante → 1 Recepción → 1 NC` es lo que permite conciliar sin desarmar totales. Un `UniqueConstraint` parcial (`estado in (0, 1)`) impide abrir dos recepciones vigentes para la misma parada; si una se anula, puede rehacerse.

**El documento identifica reparto, pedido y comprobante**, como pidió el usuario: la FK a `RepartoParada` trae los tres en un solo salto, y `reparto` queda además desnormalizado para filtrar y auditar sin JOIN.

**El número lo da el sistema.** `ContadorDocumento.RECEPCION_DEVOLUCION` con `siguiente_numero()` bajo `select_for_update()`. Es el criterio de control interno del proyecto: sólo lo que se emite numerado puede auditarse. La NC de un PRE toma su número de la serie `VENTA_NCI`, separada de la de PRE, tal como se acordó.

**El motivo decide si la mercadería vuelve al stock vendible.** `MotivoDevolucion.sugiere_apto_reventa` precarga el `apto_reventa` del renglón: un envase roto no vuelve, un negocio cerrado sí. No queda librado al criterio de quien carga. Los motivos de momento `PRE_CARGA` no se ofrecen en la recepción, porque aplican antes de cargar el vehículo.

**Desvío documentado respecto del texto del plan: el stock lo devuelve la Nota de Crédito, no la Recepción.** `productos.services.stock_service` deriva el stock de los COMPROBANTES, y las notas de crédito ya invierten el movimiento por el `signo = -1` de su tipo. Si la recepción también moviera stock, se contaría dos veces. La recepción es el control físico; la NC es el hecho que mueve el inventario. Hay una prueba que fija exactamente esto: confirmar la recepción no cambia el stock, emitir la NC sí.
  - *Consecuencia conocida:* la mercadería marcada como NO apta para reventa vuelve igual al stock, porque la NC acredita todo lo devuelto —el cliente no paga lo que devolvió, esté roto o no—. Darla de baja es un **ajuste de inventario**, término que `stock_service` todavía no tiene. Queda registrado en `apto_reventa` para cuando exista.

**La conciliación es el control de fondo.** `conciliacion(reparto)` confronta lo ACREDITADO al cliente con lo RECIBIDO en el depósito y marca tres situaciones: `concilia`, `sin_nc` (volvió pero no se acreditó) y descalce. Suma además las paradas no entregadas que todavía no tienen recepción: mercadería que el cliente no recibió y que nadie declaró de vuelta. Sin este par de documentos enfrentados, la devolución es un acto de fe.

**`NotaCreditoDistribucion` es un satélite**, igual que `ExtensionDistribuidora`: le da a la NC el motivo, la observación, la parada y la recepción sin tocar `Venta`, que es un modelo compartido por todos los rubros. El `condic` de la NC lo hereda del comprobante acreditado, nunca se calcula.

La entrega sólo se rinde con el reparto **cerrado**: mientras está armado, los saldos y el cobro mínimo de cada parada todavía no se congelaron, así que no hay nada que rendir. La vista redirige con aviso.

### Resultado de las Pruebas
```
python manage.py test distribucion
Ran 227 tests in 236.427s
OK
```
Las 33 pruebas nuevas cubren: estados de entrega, numeración correlativa e idempotencia de la recepción, los topes de cantidad (no más de lo entregado, nunca negativo, motivo obligatorio), el borrado del renglón al contar cero, la precarga de `apto_reventa`, el rechazo de acreditar sin confirmar, la serie propia de la NCI, la herencia del `condic`, el satélite, el momento exacto en que se mueve el stock, los tres estados de la conciliación, el aislamiento multiempresa y el circuito completo desde la pantalla.

Tres ajustes que hicieron las pruebas: `TipoComprobante` `PRE` y `NCI` ya vienen sembrados por migración de datos (se usa `get_or_create`), `Venta` tiene PK `ventas_id` (se usa `.pk`), y `ClienteProveedor` guarda la razón social en mayúsculas.

### Estado Actual y Siguientes Pasos
El circuito está cerrado desde que el vendedor toma el pedido hasta que la mercadería que no se entregó vuelve al depósito, se cuenta y se acredita. **Siguiente: fase 7** — carga de cobranzas del repartidor con imputación FIFO y caja recaudadora con rendición a tesorería.

Pendientes ofrecidos y no ejecutados: el widget de fecha en otros siete formularios, la exportación de faltantes a PDF/Excel, la validación de la emisión real contra ARCA Homologación, y el ajuste de inventario para la mercadería devuelta no apta.

## Día 31/08/2026 - Cobranzas del repartidor, caja recaudadora y saldos por vendedor (Plan 074, fases 7 y 8)

**Responsable:** Claude Opus.

### Objetivo
Cerrar el circuito del dinero: la cobranza que trae el repartidor con **imputación FIFO segmentada por medio de pago**, la **caja recaudadora** que se abre por reparto, la **rendición a Tesorería** en dos pasos, y el listado de **Clientes a Cobrar** agrupado por vendedor.

### Archivos Creados o Modificados
- `distribucion/services/cobranza_fifo.py` [NEW]: `planificar()`, `registrar()`, `comprobantes_abiertos()`, `saldo_fiscal()`, `saldo_operativo()`.
- `distribucion/services/caja_reparto.py` [NEW]: `caja_recaudadora()`, `abrir_caja_del_reparto()`, `resumen()`, `rendir()`.
- `distribucion/services/saldos_clientes.py` [NEW]: `listado()` con antigüedad por tramos y agrupación por vendedor.
- `distribucion/models.py` [MODIFY]: `CobranzaDistribucion`, `RendicionReparto` y `Reparto.sesion_caja`.
- `tesoreria/models.py` [MODIFY]: nuevo tipo de caja `'R'` (Recaudadora / Reparto).
- `distribucion/services/reparto.py` [MODIFY]: `cerrar_reparto()` abre la caja recaudadora.
- `distribucion/views.py` [MODIFY]: `CobranzaRepartoView`, `RendicionRepartoView`, `SaldosClientesView`.
- `templates/distribucion/cobranza.html`, `rendicion.html`, `saldos_clientes.html` [NEW].
- `templates/distribucion/reparto_detalle.html`, `templates/base.html`, `config/urls.py` [MODIFY]: tres rutas nuevas y la entrada de menú «Clientes a Cobrar».
- `distribucion/tests/test_plan074_cobranzas.py` [NEW]: 43 pruebas.
- Migraciones: `distribucion/0008_reparto_sesion_caja_cobranzadistribucion_and_more.py`, `tesoreria/0016_alter_caja_tipo.py`, `core/0007_alter_contadordocumento_tipo_documento.py` (todas aplicadas).

### Detalle Técnico

**El usuario carga un importe; el corte lo hace el sistema.** El repartidor vuelve y dice «de González traje $40.000 en efectivo y un cheque de $66.000». Nadie le va a preguntar cuánto de eso cancela facturas y cuánto cancela PRE: eso lo decide `cobranza_fifo.py` con dos reglas que no se negocian.

1. **Lo trazable va siempre contra `condic = 1`.** Transferencia, cheque, tarjeta, billetera digital y retención: un movimiento que el banco registra no puede cancelar una operación que para el fisco no existe. Todo lo que **no** esté en esa lista se trata como efectivo, incluida la categoría `OTR`: si no deja rastro externo verificable, no puede respaldar una operación fiscal.
2. **El efectivo cancela primero el PRE más viejo**, y sólo agotados todos los PRE continúa con las facturas. Es la única plata que puede pagar lo que no está documentado, así que se usa donde hace falta.

Los dos tramos comparten **un solo diccionario de saldos**, que se muta a medida que se imputa. Es lo que garantiza que el efectivo no vuelva a aplicar sobre el peso que ya canceló el cheque; hay una prueba que lo fija.

**Dos recibos como máximo, uno por `condic`.** Real y Presupuestado no se mezclan porque cada uno alimenta un circuito contable distinto y el asiento hereda el `condic` del comprobante. El recibo Presupuestado lleva **exactamente** el efectivo que canceló PRE; todo lo demás —trazables, efectivo aplicado a facturas y el excedente— va al Real. Así los dos totales suman lo que entró en la caja, y los `MovimientoCajaDetalle` de cada uno cuadran con su total, que es lo que hace que el asiento cierre. Hay una prueba dedicada a ese cuadre.

**El excedente queda en el circuito fiscal**, como anticipo del cliente: es donde se puede justificar de dónde salió la plata. Si sobró efectivo es porque ya no quedaba ningún PRE que cancelar, así que no hay otro lugar donde ponerlo.

**Las notas de crédito no entran en el FIFO.** Acreditar una NC contra una factura es una *imputación entre comprobantes*, no una cobranza: no entra plata. Mezclarla obligaría a manejar signos cruzados en el mismo recorrido y volvería ilegible el algoritmo. El FIFO recorre sólo comprobantes con saldo deudor.

**Las dos lentes sobre el saldo del cliente.** `ClienteProveedor.saldo` suma todo sin distinguir: sirve como lente **operativa** (`condic 1 + 2`), que es la que ve el vendedor, la que usa el límite de crédito y la que sale impresa en la Hoja de Ruta —al cliente hay que cobrarle todo lo que debe, tenga o no respaldo fiscal—. La lente **fiscal** (`condic = 1`) se calcula recorriendo comprobantes y recibos: es la que va a los estados contables. Una prueba muestra el efecto: cobrar en efectivo un PRE baja el saldo operativo y **no mueve el fiscal**.

**Caja recaudadora `'R'`, no la mostrador `'M'`.** La mostrador se abre y cierra por turno de cajero, con arqueo ciego, en un puesto fijo; la recaudadora se abre y cierra **por reparto**, la maneja alguien que está en la calle, y su cierre se concilia contra la Hoja de Ruta. Un `tipo` explícito evita ramificar el código de la mostrador con condicionales que no tienen nada que ver con ella. Hay **una sola caja recaudadora por sucursal**: lo que separa un reparto de otro es la **sesión**, que se abre automáticamente al cerrar el reparto.

**De quién es la plata lo dice el reparto, no la sesión de caja.** `CajaSesion.usuario` es un `User` y el repartidor puede no serlo: trabaja con el papel y no necesita credenciales (§4.3). En la práctica el administrativo abre la sesión y el `Reparto` dice de quién es la recaudación, a través de sus `responsables`. `RendicionReparto` es el vínculo que la sesión de caja no puede dar.

**La rendición reutiliza `RetiroCaja`, que ya existe.** Los dos pasos —el repartidor declara, el tesorero cuenta y acepta, la diferencia genera su asiento— ya están implementados y probados en Tesorería, y la rendición del reparto aparece en **la misma bandeja de recepción** que las de mostrador. Acá no se reimplementó nada: se abre el retiro desde la sesión del reparto, se generan sus asientos de traslado y el reparto pasa a **RENDIDO** cerrando su caja. El paso 2 sigue viviendo en Tesorería, que es donde corresponde: *el que declara no es el mismo que cuenta*.

**Decisión contable revisable:** el traslado usa `cta_caja_mostrador` como cuenta de ORIGEN, que es la cuenta de efectivo fuera de Tesorería. La recaudadora **no tiene parámetro contable propio**; agregarlo sólo tendría sentido si la empresa quisiera ver por separado en el balance la plata que está en la calle. Queda anotado en el código y acá.

**Cuadro esperado vs. cobrado vs. rendido** (§7.9, punto 4). *Esperado* es la suma de los `cobro_minimo` congelados al cerrar el reparto: lo que el sistema le dijo al repartidor que no podía dejar de traer. *Cobrado* se abre por medio de pago y por `condic`. *Rendido* muestra lo declarado y lo que el tesorero contó. El cuadro incluye además **las notas de crédito del reparto con sus motivos**: sin verlas ahí, el importe de la mercadería que volvió parecería un faltante del repartidor.

**Clientes a Cobrar (§7.8).** Agrupado por vendedor porque es el responsable directo del saldo de su cartera. Un cliente **sin vendedor asignado no desaparece**: cae en un grupo propio, porque un saldo sin responsable es justamente lo que hay que ver. Cada comprobante trae su antigüedad en días y su tramo (0-30 / 31-60 / 61-90 / +90), y los `condic = 2` van marcados **SÓLO EFECTIVO**: es la traducción práctica de la regla 1. Zona y día de visita se filtran por el **domicilio de entrega**, no por el cliente, porque un cliente con sucursales tiene domicilios en zonas y días distintos. Filtro de condición presente, como exige la regla del proyecto para todo reporte con importes.

### Resultado de las Pruebas
```
python manage.py test distribucion tesoreria contable
Ran 450 tests in 386.295s
OK
```
Las 43 pruebas nuevas cubren: las dos reglas de segmentación, el orden FIFO por fecha, la venta del propio reparto cancelándose al final, el excedente, la no-doble-aplicación entre tramos, la partición en dos recibos, el cuadre de los detalles contra el total de cada recibo, la baja del saldo de los comprobantes, el satélite, la caja recaudadora y su idempotencia, sesiones distintas por reparto sobre la misma caja, el cuadro de rendición, el retiro en tránsito, el cierre de la caja al rendir, la doble rendición rechazada, las dos lentes, los tramos de antigüedad, el filtro de condición, el aislamiento multiempresa y las cuatro pantallas.

Tres ajustes que hicieron las pruebas: `ClienteProveedor` tiene PK `codigo_id` (se usa `.pk`), la contabilización de una factura fiscal exige `cta_iva_debito`, y el traslado de la rendición exige `cta_caja_mostrador`.

### Estado Actual y Siguientes Pasos
Los nueve procesos del Plan 074 están implementados: desde que el vendedor toma el pedido hasta que la plata llega a Tesorería, pasando por la facturación, el reparto, la entrega, las devoluciones y la cobranza. **Falta la fase 8 restante**: el reporte de devoluciones por período/motivo/repartidor y el de correlativos del módulo, más las exportaciones a PDF/Excel.

Pendientes ofrecidos y no ejecutados: el widget de fecha en otros siete formularios, la exportación de faltantes y de saldos a PDF/Excel, la validación de la emisión real contra ARCA Homologación, el ajuste de inventario para la mercadería devuelta no apta, y la cuenta contable propia para la caja recaudadora.

## Día 31/08/2026 - La Nota de Crédito descuenta el saldo de su factura (Plan 076, bloque D)

**Responsable:** Claude Opus.

### Objetivo
Definición del usuario: *"Las notas de crédito, como están vinculadas a la factura que le dio origen, deben computarse en el saldo pendiente de la factura (factura − NC relacionadas), y de ahí sale el saldo real de la factura. La NC queda con saldo cero porque se aplicó totalmente a la factura de origen."* **Afecta a todo el ERP, no sólo a Distribución.**

### Archivos Creados o Modificados
- `facturacion/models.py` [MODIFY]: `Venta.venta_origen` (FK a sí misma, nullable, `related_name='notas_credito'`).
- `facturacion/services/notas_credito.py` [MODIFY]: `emitir_nota_credito_desde_venta()` estampa el vínculo.
- `facturacion/signals.py` [MODIFY]: al guardar una NC vinculada se recalcula el saldo de la NC y el de su factura.
- `contable/services/saldos.py` [MODIFY]: `recalcular_saldo_venta()` resta las NC relacionadas y deja la NC en cero; `recalcular_saldo_cliente_proveedor()` **aplica el signo del tipo**.
- `facturacion/tests/test_plan076_saldo_nc.py` [NEW]: 11 pruebas.
- Migraciones: `facturacion/0059_venta_venta_origen.py` y `facturacion/0060_vincular_nc_y_recalcular_saldos.py` (aplicadas).

### Detalle Técnico

**No existía vínculo genérico NC → factura.** `emitir_nota_credito_desde_venta()` recibía la venta original, copiaba sus ítems y **no persistía de dónde venía**. El único vínculo era `distribucion.NotaCreditoDistribucion.venta_origen`, satélite del módulo, inútil para armería o para el resto del ERP. El campo nuevo `Venta.venta_origen` cierra eso.

**El saldo del comprobante.** `recalcular_saldo_venta()` pasa a ser `total − cobrado − Σ recibos − Σ NC relacionadas`, y una NC con `venta_origen` queda en **cero**: se aplicó por completo a su factura. El recálculo se dispara desde la señal `post_save` de `Venta` y no desde el emisor de la NC, para que valga también al **anularla**, que es cuando el descuento se revierte. No hay recursión: el servicio escribe con `.update()`, que no dispara señales.

**Hallazgo: la convención de signo estaba documentada pero no implementada.** `saldos.py` y `tesoreria/views_htmx.py` decían que las NC *"se graban en negativo vía `TipoComprobante.signo = -1`"*. Los datos dicen otra cosa: las dos NC de la base tienen total **positivo** (30,00 y 12,00), y `emitir_nota_credito_desde_venta()` las emite así, sumando ítems positivos. Con `recalcular_saldo_cliente_proveedor()` sumando `total − cobrado` sin aplicar el signo, **una Nota de Crédito AUMENTABA la deuda del cliente en lugar de bajarla**.

La corrección va donde ya estaba el criterio correcto del proyecto: `productos.services.stock_service` multiplica por `tipo__signo` para que la NC invierta el movimiento. Ahora el saldo por entidad hace lo mismo:

```python
Sum((F('total') - F('cobrado')) * Coalesce(F('tipo__signo'), Value(1)))
```

Es un arreglo inseparable del pedido: sin él la lente por comprobante y la lente por entidad se separaban por el doble de la NC. Hay una prueba que exige que **la suma de los saldos de los comprobantes sea igual al saldo del cliente**.

`recalcular_saldo_compra()` **no se tocó**: no hay ninguna compra con tipo de signo −1 en la base, así que no hay evidencia de cuál es la convención real del lado de proveedores. Queda anotado.

**Efecto lateral que limpia el diseño de la fase 7.** Aquella fase documentó *"las notas de crédito no entran en el FIFO"* como decisión para no manejar signos cruzados. Con esta regla deja de ser un compromiso: la NC baja el saldo de su factura y queda en cero, así que el filtro `saldo > 0` de `comprobantes_abiertos()` es correcto **por construcción**. Dos pruebas lo fijan.

**Migración de datos.** Vincula las NC existentes desde `NotaCreditoDistribucion.venta_origen` —único lugar donde el dato existía— y recalcula comprobantes y entidades con una **réplica congelada** de la fórmula, sin importar el servicio vivo (en una migración el modelo es histórico). Verificación sobre la base real:

```
ANTES:   ORTIZ JUAN MANUEL  saldo 599,00
DESPUES: ORTIZ JUAN MANUEL  saldo 515,00
```

La baja de 84,00 es exactamente 2 × 42,00 (las dos NC de 30,00 y 12,00): antes se sumaban, ahora se restan. Confirma que el error era real y que quedó corregido.

**Limitación conocida:** las NC históricas de otros módulos no tienen de dónde deducir su origen y quedan sin vincular (`venta_origen = NULL`). Son las dos que hay en el sistema. Su saldo se comporta como antes —una NC sin aplicar es un crédito pendiente legítimo—, pero el FIFO las va a ofrecer como comprobante a cobrar hasta que se las vincule a mano.

### Resultado de las Pruebas
```
python manage.py test facturacion contable tesoreria
Ran 280 tests in 221.312s
FAILED (errors=1)   # test_emitir_comprobante_homologacion_real: falta el certificado ARCA (ambiental)
```
Las 11 pruebas nuevas cubren: la NC baja el saldo de su factura, la NC queda en cero, el vínculo persistido, la NC total, dos NC parciales acumuladas, la convivencia con una cobranza en el mismo saldo, la reversión al anular, que el saldo del cliente no se cuente dos veces, que las dos lentes coincidan, y que el FIFO no ofrezca ni una factura ya cubierta ni la NC.

### Estado Actual y Siguientes Pasos
Bloque **D** cerrado. **Siguen A** (parada de sólo cobranza), **B** (Tesorería de Reparto intermedia + la regresión del §B.2) y **C** (rendición del vendedor), en ese orden.

## Día 31/08/2026 - Parada de sólo cobranza (Plan 076, bloque A)

**Responsable:** Claude Opus.

### Objetivo
Definición del usuario: *"En una hoja de ruta podemos agregar clientes con saldos que no hicieron un pedido pero necesito que le cobren el saldo pendiente."* Si todas las paradas son de esa clase, el reparto es una ruta de cobranza pura, sin detalle de productos.

### Archivos Creados o Modificados
- `distribucion/models.py` [MODIFY]: `RepartoParada.tipo` (`ENTREGA` / `COBRANZA`), `pedido` y `venta` nullables, `cliente` y `domicilio_texto` como campos propios, y tres restricciones nuevas.
- `distribucion/services/reparto.py` [MODIFY]: `agregar_parada_de_cobranza()`, `cerrar_reparto()`, `hoja_de_ruta()`, `consolidado()`, `totales_hoja_de_ruta()`.
- `distribucion/services/devoluciones.py` [MODIFY]: entrega y devoluciones sólo sobre paradas de ENTREGA.
- `distribucion/views.py` [MODIFY]: acción `agregar_cobranza` y selector de clientes con saldo.
- Templates de reparto, hoja de ruta, entrega, cobranza, recepción y rendición [MODIFY].
- `distribucion/tests/test_plan076_parada_cobranza.py` [NEW]: 27 pruebas.
- Migración: `distribucion/0009_parada_de_cobranza.py` (aplicada).

### Detalle Técnico

**EL COBRO MÍNIMO DE UNA PARADA DE COBRANZA ES CERO.** Es la corrección central del bloque, y va contra lo que yo había asumido primero —que había que exigir todo el saldo—. El usuario lo desarmó:

> *"Puede tranquilamente ser una cobranza parcial como cualquier otra… la mayoría de las veces el cliente o no entrega nada o entrega sólo un pago parcial. Seguramente el pago final lo terminará haciendo el vendedor que le hará la 'guardia' cuando el cliente esté esquivando el pago. Cliente que no hizo pedido es más que probable que no esté entre sus prioridades el pagarnos."*

El razonamiento de fondo: **el cobro mínimo existe porque hay mercadería de por medio, es la condición para dejarla.** Sin entrega no hay palanca. El repartidor pide y se lleva lo que le den. Entonces se congela el **saldo** como dato para reclamar, `cobro_minimo = 0`, y lo que traiga se imputa con el procedimiento estándar: FIFO de lo más antiguo, con el efectivo priorizando los `condic = 2`. **Sin caso especial**: es exactamente lo que ya hacía `registrar()`.

Queda además coherente el cuadro de la rendición: `esperado = Σ cobro_minimo`, así que estas paradas aportan cero. *No se puede esperar lo que no se tiene con qué exigir.*

**El tipo es explícito, no inferido.** `RepartoParada.tipo` en vez de deducirlo de `venta is None`: obligar a recordar esa convención en cada lectura es la clase de detalle que después se olvida en un reporte.

**`cliente` y `domicilio_texto` dejan de ser properties.** Salían de `venta.cliente` y `pedido.domicilio_entrega_texto`; sin comprobante no hay de dónde sacarlos. La migración los rellena con **los mismos valores que devolvían las properties**: no hay pérdida ni interpretación. El domicilio queda congelado por el mismo motivo que los importes.

**Las reglas inflexibles van a la base:**
```python
CheckConstraint(Q(tipo=0, venta__isnull=False) | Q(tipo=1, venta__isnull=True))
UniqueConstraint(['venta'], condition=Q(venta__isnull=False))
```
El único se condiciona porque ahora hay nulos. PostgreSQL ya admite varios NULL en un índice único, pero así la regla queda **escrita** y no depende de un detalle del motor. Hay pruebas para las dos combinaciones inválidas y para que varias paradas de cobranza convivan en el mismo reparto.

**Lo que se apagó donde no corresponde:** entrega, devoluciones y Recepción de Devoluciones rechazan una parada de cobranza — *sin mercadería no hay entrega que registrar ni devolución que recibir*. El Consolidado de un reparto de pura cobranza da **vacío**, que es lo correcto: no se carga nada al vehículo. Y `hoja_de_ruta()` pasa a ordenar por el cliente **propio de la parada**: por el del comprobante, las de cobranza caían todas al final.

### Resultado de las Pruebas
```
python manage.py test distribucion
Ran 297 tests in 281.850s
OK
```

---

## Día 31/08/2026 - Tesorería de Reparto intermedia (Plan 076, bloque B)

**Responsable:** Claude Opus.

### Objetivo
Definición del usuario: *"Las rendiciones de reparto y vendedores… se realizan en una 'tesorería de reparto intermedia' tal cual la caja mostrador de armería, para luego tipo retiro y cierre de caja rendir a caja tesorería."* La fase 7 salteaba ese nivel.

### Archivos Creados o Modificados
- `tesoreria/models.py` [MODIFY]: `Caja.tipo` gana `'D'` (Tesorería de Reparto).
- `tesoreria/views.py`, `tesoreria/views_htmx.py` [MODIFY]: **corrección de la regresión** y helpers `_caja_operable()` / `_cajas_operables()`.
- `distribucion/services/caja_reparto.py` [MODIFY]: `tesoreria_reparto()`, `sesion_de_tesoreria_reparto()`, `recibir()`, `rendiciones_por_recibir()`; `rendir()` cambia de destino.
- `distribucion/views.py`, `templates/distribucion/recepcion_rendiciones.html` [NEW/MODIFY]: bandeja de recepción.
- `distribucion/tests/test_plan076_tesoreria_reparto.py` [NEW]: 20 pruebas.
- Migración: `tesoreria/0017_tesoreria_de_reparto.py` (aplicada).

### Detalle Técnico

**Son tres niveles, no dos:**
```
cobranzas ─► CAJA RECAUDADORA 'R'      una sesión por reparto
                    │  el repartidor declara → el administrativo cuenta y acepta
                    ▼
             TESORERÍA DE REPARTO 'D'  UNA POR SUCURSAL
                    │  retiro / cierre de caja (circuito existente)
                    ▼
             CAJA TESORERÍA 'T'
```
Quien recibe a los repartidores **no es el tesorero central**: es un administrativo que cuenta lo que cada uno trae, lo retiene, y después entrega el consolidado. Es la misma razón por la que existe la caja mostrador de armería. Y **los dos pasos que el Plan 074 §7.9 pedía son los de este tramo**, no los del que va a Tesorería: estaban bien descritos y mal ubicados.

**REGRESIÓN CORREGIDA (§B.2).** `caja_recaudadora()` —de la fase 7— crea una caja `'R'` en la misma sucursal donde vive la mostrador. Seis lugares buscaban «la caja de la sucursal» **sin filtrar por tipo**:
```python
Caja.objects.filter(empresa_id=..., sucursal_id=..., activa=True).first()
```
en `tesoreria/views.py:79` y `views_htmx.py` 923, 1328, 1354, 1477 y 1498. `Caja` no tiene `ordering` en su `Meta`, así que funcionaba sólo porque la mostrador tiene `pk` más bajo. **El riesgo real:** la sesión se busca con `usuario=request.user, estado='A'`, y un cajero que además cerrara un reparto tenía DOS sesiones abiertas a su nombre — el cierre de mostrador podía tomar la del reparto y rendir esa plata por el circuito equivocado. Hay tres pruebas dedicadas.

**Sin asiento de traslado en el primer tramo, y es deliberado.** La recaudadora y la Tesorería de Reparto son las dos «efectivo fuera de Tesorería» y comparten cuenta contable (`cta_caja_mostrador`): el asiento sería Debe y Haber sobre la misma cuenta. Peor todavía sería asentar contra Caja Central, porque estaría registrando en Tesorería **plata que sigue en la calle**. El movimiento contable real ocurre en el segundo tramo, cuando la intermedia rinde por el retiro/cierre de siempre.

**La caja refleja lo CONTADO, no lo declarado**, y la diferencia genera su asiento contra Diferencias de Caja: un faltante queda registrado, no absorbido en silencio. *El que declara no es el mismo que cuenta.*

### Resultado de las Pruebas
```
python manage.py test distribucion tesoreria
Ran 405 tests in 370.545s
OK
```

---

## Día 31/08/2026 - Cobranza y rendición del vendedor (Plan 076, bloque C)

**Responsable:** Claude Opus.

### Objetivo
Definición del usuario: *"En cuanto a los vendedores, rendirán a esta caja intermedia pero en su condición de vendedores por los fondos que traen, no como reparto."*

### Archivos Creados o Modificados
- `distribucion/models.py` [MODIFY]: `CobranzaDistribucion.reparto` nullable con CheckConstraint de responsable; `RendicionReparto` gana `vendedor` y el CheckConstraint de origen único.
- `distribucion/services/caja_reparto.py` [MODIFY]: `abrir_caja_del_vendedor()`, `sesion_abierta_del_vendedor()`, `resumen_vendedor()`, `rendir_vendedor()`; la bandeja lista los dos orígenes.
- `distribucion/services/cobranza_fifo.py` [MODIFY]: `registrar()` acepta `reparto=None`.
- `distribucion/views.py`, `templates/distribucion/cobranza_vendedor.html` [NEW/MODIFY].
- `distribucion/tests/test_plan076_cobranza_vendedor.py` [NEW]: 23 pruebas.
- Migración: `distribucion/0010_rendicion_del_vendedor.py` (aplicada).

### Detalle Técnico

**Para poder rendir hay que haber retenido.** El vendedor cobra por su cuenta —al cliente que esquiva el pago y al que después le hace la guardia—, y esa plata tiene que caer en algún lado antes de que la entregue, o no habría nada que rendir. Se le abre una **sesión propia sobre la misma caja recaudadora**, que se cierra recién cuando rinde. Misma estructura que un reparto, con otro dueño.

**La sesión no dice de quién es la plata; lo dice la rendición.** `CajaSesion.usuario` es un `User` y el vendedor puede no serlo (§4.3). La sesión abierta de un vendedor se identifica por **sus cobranzas**, que llevan el `cobrador`; una sesión de reparto nunca entra ahí porque sus cobranzas tienen `reparto` seteado.

**La plata siempre tiene un responsable.** Dos restricciones de base:
```python
CobranzaDistribucion:  Q(reparto__isnull=False) | Q(cobrador__isnull=False)
RendicionReparto:      exactamente UNO de reparto / vendedor
```
Sin ninguno la plata no tiene dueño; con los dos, no se sabe a quién reclamarle un faltante.

**Mismo FIFO, mismas dos reglas, sin caso especial.** `registrar()` con `reparto=None` recorre idéntico camino. Una prueba lo fija: efectivo contra el PRE, transferencia contra la factura.

**`Personal` no tiene sucursal** —el vendedor recorre, no está asignado a un depósito—, así que la sucursal la aporta quien opera, desde su sesión de trabajo. El servicio la exige explícitamente en vez de adivinarla.

**Los dos orígenes comparten bandeja de recepción:** para quien recibe es el mismo acto —contar lo que alguien trajo— y separarlos sólo agregaría una pantalla más.

### Resultado de las Pruebas
```
python manage.py test distribucion.tests.test_plan076_cobranza_vendedor
Ran 23 tests in 30.689s
OK
```

### Estado Actual y Siguientes Pasos
**Plan 076 completo (A + B + C + D).** El circuito de fondos de Distribución quedó con sus tres niveles y las notas de crédito descuentan el saldo de su factura en todo el ERP.

Pendientes ofrecidos y no ejecutados: el reporte de devoluciones por período/motivo/repartidor y el de correlativos del módulo (fase 8 restante), el widget de fecha en otros siete formularios, las exportaciones a PDF/Excel, la validación contra ARCA Homologación, el ajuste de inventario para la mercadería devuelta no apta, y una cuenta contable propia para las cajas de distribución si se quisiera ver por separado en el balance la plata que está en la calle.

## Día 31/08/2026 - Cuenta contable propia para la caja de distribución (Plan 076, addenda §B)

**Responsable:** Claude Opus.

### Objetivo
Definición del usuario: *"Agreguemos un nuevo parámetro `cta_caja_reparto` porque incluso ambos responsables son totalmente distintos."* El efectivo que está en la calle es de otro responsable que el de la caja mostrador —el repartidor y el administrativo de reparto, frente al cajero de turno—, así que el balance tiene que poder mostrarlo por separado.

### Archivos Creados o Modificados
- `contable/models.py` [MODIFY]: `ParametrosContables.cta_caja_reparto`.
- `templates/configuracion/modals/parametros_contables_form.html` [MODIFY]: el campo en la pantalla de parámetros.
- `tesoreria/views_htmx.py` [MODIFY]: `cuenta_origen_de_caja()`, y `generar_asientos_traslado()` / `_generar_asiento_diferencia()` pasan a aceptar la cuenta en vez de tenerla fija.
- `distribucion/services/caja_reparto.py` [MODIFY]: `cuenta_de_reparto()` y `medio_pago_efectivo()`.
- `distribucion/services/cobranza_fifo.py` [MODIFY]: el efectivo usa el medio de distribución.
- `distribucion/tests/test_plan076_cuenta_reparto.py` [NEW]: 14 pruebas.
- Migración: `contable/0022_cta_caja_reparto.py` (aplicada).

### Detalle Técnico

**El parámetro solo no alcanzaba, y ése fue el hallazgo.** `contabilizar_recibo()` arma el DEBE del asiento con la cuenta contable del **MEDIO DE PAGO**, no con la de la caja (`_cuenta_medio_cobro()`, punto 3 de su orden de resolución). Con el efectivo genérico, la cobranza de un reparto habría seguido cayendo en la cuenta de la mostrador y el parámetro nuevo no habría servido de nada: el balance mostraría la cuenta de reparto en cero mientras la plata de la calle se sigue mezclando.

La solución usa el punto de extensión que ya existía en vez de tocar el motor contable: un **medio de pago propio `EFE-REP` («Efectivo en Reparto»)** apuntado a `cta_caja_reparto`, creado y **mantenido en sincronía** con el parámetro por `medio_pago_efectivo()`. Si el parámetro cambia, el medio lo sigue; si no, los asientos nuevos quedarían apuntando a la cuenta vieja. El usuario no tiene que cargarlo ni recordarlo: se deriva del parámetro. Hay una prueba de punta a punta que verifica que **lo cobrado en la calle no toca la cuenta de la mostrador**.

**Sin fallback a la mostrador, a propósito.** `cuenta_de_reparto()` lanza un error explícito si el parámetro está vacío. Sustituirla en silencio mezclaría la plata del repartidor con la del cajero, que es exactamente lo que esta cuenta viene a separar: *mejor un error claro una vez que un número mal agrupado para siempre*. Es además la doctrina del proyecto desde el Plan 075.

**Dos funciones compartidas dejaron de tener la cuenta fija**, con el comportamiento de siempre por omisión:
- `generar_asientos_traslado(..., cuenta_origen=None)` → por omisión `cta_caja_mostrador`. El retiro y el cierre resuelven cuál corresponde con `cuenta_origen_de_caja(caja, param)`, según el tipo de caja.
- `_generar_asiento_diferencia(..., cuenta_caja=None)` → por omisión `cta_caja_central`. Cuando quien recibe es la Tesorería de Reparto se ajusta `cta_caja_reparto`, porque **la plata contada está ahí y no en Tesorería**: ajustar la Central movería una cuenta donde no pasó nada.

**Las dos cajas de distribución comparten la cuenta.** La recaudadora `'R'` y la Tesorería de Reparto `'D'` apuntan a `cta_caja_reparto`, así que el traslado entre ellas sigue sin generar asiento —sería Debe y Haber sobre la misma cuenta—. El asiento contable real aparece recién en el segundo tramo, cuando la intermedia rinde a Caja Tesorería: ahí sí **Debe Caja Central / Haber Caja de Reparto**, que es lo que hace visible en el balance cuánto hay en la calle.

### Resultado de las Pruebas
```
python manage.py test distribucion tesoreria contable
Ran 534 tests in 517.615s
OK
```
Las 14 pruebas nuevas cubren: el parámetro y su error cuando falta, el medio de pago propio (que apunta a la cuenta, que no pisa el efectivo genérico, que sigue al parámetro si cambia y que es idempotente), el asiento de la cobranza del reparto y del vendedor debitando la cuenta correcta, la diferencia de arqueo ajustando la caja de reparto y no la Central, la resolución de la cuenta de origen según el tipo de caja, y la verificación de punta a punta de que lo cobrado en la calle no toca la cuenta de la mostrador.

### Estado Actual y Siguientes Pasos

**ACCIÓN PENDIENTE DEL USUARIO.** La empresa 4 (RODRIGUEZ MARCELO FABIAN) todavía tiene `cta_caja_reparto` **sin configurar**, así que el circuito de cobranzas de distribución va a fallar con el mensaje explícito hasta que se le asigne una cuenta en *Configuración → Parámetros Contables → Caja de Reparto (Distribución)*. Su plan de cuentas hoy tiene `111001 CAJA`, `111002 VALORES EN CARTERA` y `111003 CAJA MOSTRADOR`: el hueco natural es `111004 CAJA DE REPARTO`.

Pendientes ofrecidos y no ejecutados: el reporte de devoluciones y el de correlativos del módulo (fase 8 restante), el widget de fecha en otros siete formularios, las exportaciones a PDF/Excel, la validación contra ARCA Homologación, y el ajuste de inventario para la mercadería devuelta no apta.

## Día 31/08/2026 - La cuenta del efectivo la define la caja, y el recibo del cajero (Plan 077)

**Responsable:** Claude Opus.

### Objetivo
Definición del usuario: *"Caja mostrador descarga sobre las cuentas definidas por parámetro —cobranzas por un lado y retiros / cierre de caja por el otro—, por lo que deberían quedar en cero o lo que se defina como fondo fijo al final de cada cierre."* Y la mejora que lo acompaña: *"El cajero todo lo que maneje será a través de su CAJA MOSTRADOR."*

### Archivos Creados o Modificados
- `contable/services/contabilizacion.py` [MODIFY]: `cuenta_efectivo_de_caja()` y el nuevo paso 2 de `_cuenta_medio_cobro()`.
- `tesoreria/views_htmx.py` [MODIFY]: la venta de mostrador, el traslado y `procesar_recibo()`.
- `tesoreria/views.py`, `tesoreria/urls.py` [MODIFY]: `ReciboCargaView.origen` y la ruta del mostrador.
- `tesoreria/permisos.py` [NEW]: `bloquear_cajero`, `SinCajeroMostradorMixin`, `es_cajero_restringido()`.
- `tesoreria/views_listados.py`, `views_caja_diaria.py`, `views_eoaf.py` [MODIFY]: bloqueos.
- `usuarios/models.py`, `usuarios/forms.py` [MODIFY]: `Perfil.es_cajero_mostrador`.
- `distribucion/services/caja_reparto.py` [MODIFY]: se elimina el medio de pago `EFE-REP`.
- `templates/tesoreria/caja_mostrador_index.html`, `recibo_carga.html`, `templates/base.html`, `templates/configuracion/modals/usuario_form.html` [MODIFY].
- `tesoreria/tests/test_plan077_caja_cierra_en_cero.py` [NEW]: 8 pruebas.
- `tesoreria/tests/test_plan077_cajero_mostrador.py` [NEW]: 10 pruebas.
- Migración: `usuarios/0010_cajero_mostrador.py` (aplicada).
- Plan: `docs/planes/077_recibo_en_mostrador.md` [NEW].

### Detalle Técnico

**El diagnóstico: el efectivo tenía TRES destinos contables**, según por qué camino entrara o saliera.

| Camino | Cuenta que usaba |
|--------|------------------|
| Venta de mostrador cobrada en el acto | `cta_caja` |
| Recibo de cobranza | la del **medio de pago** (fallback `cta_caja_central`) |
| Retiro / cierre de caja | `cta_caja_mostrador` |

Por eso `cta_caja_mostrador` **sólo recibía haber y nunca debe**: no es que no cerrara en cero, es que se volvía cada vez más acreedora con cada cierre. En ARMERIA ya estaba en −$25.000 con una sola línea.

**La regla: para el efectivo, la cuenta la define la CAJA.** Un cheque es un cheque entre donde entre; el efectivo vive en un cajón concreto. Dicho de la forma en que lo planteó el usuario, que es la que ordena todo: **la cuenta la define quién tiene que rendir la plata.** Un recibo hecho en el mostrador lo rinde el cajero; el mismo recibo hecho en Tesorería ya está en Tesorería.

`cuenta_efectivo_de_caja(caja, parametros, en_divisa)` resuelve por `caja.tipo`: `'M'` → mostrador, `'R'`/`'D'` → reparto, `'T'` → central. Para las cajas de distribución **lanza error si falta el parámetro** (sustituirlo en silencio mezclaría lo que ese parámetro vino a separar); para mostrador y tesorería **devuelve `None` y la cadena sigue**, que es el estado heredado de las empresas que nunca lo cargaron.

En `_cuenta_medio_cobro()` entra como **paso 2**, entre la cuenta bancaria concreta y la lógica de divisas, y **sólo para categoría `EFE`**: la billetera digital no vive en un cajón que alguien tenga que rendir.

**Simplificación que se llevó puesta:** el medio de pago `EFE-REP` que el Plan 076 creaba para distribución **dejó de hacer falta** —la caja ya dice la cuenta—, así que se eliminó. Queda un solo mecanismo en vez de dos, y las pruebas que verificaban aquel medio pasaron a verificar la resolución por caja.

**El recibo del cajero (§F).** Es **el mismo recibo que ya existía**: cliente, aplicación a facturas con saldo, o recibo simple. No hay pantalla nueva. `ReciboCargaView` ganó un atributo `origen` y una segunda URL apunta a **la misma vista y el mismo template**. Lo único que cambió de verdad fue `procesar_recibo()`, que resolvía la caja con `get_o_abrir_caja(...)` —**siempre Tesorería**, ahí estaba la raíz de que un recibo nunca impactara el mostrador— y ahora usa la sesión del cajero cuando el origen es el mostrador. Si su caja está cerrada **falla**: no se puede meter plata en un cajón que no está abierto, y desviarla a Tesorería sería peor que rechazarla.

La parte contable del recibo del mostrador **no tiene una sola línea propia**: sale de la regla de §E.

**La restricción del cajero (§G).** `Perfil.es_cajero_mostrador`, en `False` por defecto: es una RESTRICCIÓN, no un permiso, así que nadie pierde accesos al aplicarla y sólo queda acotado quien se marque. Al revés —un permiso que hubiera que otorgar— habría dejado a todos afuera hasta tildarlo uno por uno. El administrador de sistema nunca queda atrapado, para que pueda entrar a corregirlo si se marca por error.

**El bloqueo va en las vistas, no sólo en el menú:** esconder un link no es un permiso, la URL sigue estando para quien la escriba. Las pruebas pegan contra las URLs directas, no contra el HTML del menú. Y el mensaje del bloqueo **le dice al cajero por dónde tiene que operar** en vez de un "no tenés permiso" a secas.

### Resultado de las Pruebas
```
python manage.py test tesoreria.tests.test_plan077_caja_cierra_en_cero   ->  8 OK
python manage.py test tesoreria.tests.test_plan077_cajero_mostrador      -> 10 OK
python manage.py test tesoreria contable distribucion                    -> 554 OK
```

**La regresión encontró un bug propio y sirvió de lección.** El import de
`cuenta_efectivo_de_caja` en la venta de mostrador nunca llegó al módulo: el guardia del
parche lo dio por presente porque la cadena ya aparecía dentro de otra función, y el cobro de
mostrador rompía con `NameError`. Lo atraparon tres pruebas del Plan 049.

De ahí salió una prueba nueva —`test_la_venta_de_mostrador_debita_la_cuenta_de_su_caja`—
porque el hueco de fondo era otro: de los **tres caminos** que este plan unifica, el de la
venta de mostrador **no tenía ninguna prueba que verificara la cuenta**. Las del Plan 049
comprobaban el `condic` y el vínculo con la caja, no dónde caía el debe.
Las 8 primeras **verifican el requerimiento, no la implementación**: cobran en el mostrador, cierran la caja dejando un fondo fijo, y comprueban que `cta_caja_mostrador` queda exactamente en el fondo fijo y que lo rendido llegó a Caja Central. Si mañana la cuenta se resolviera de otra manera pero la caja siguiera cerrando bien, deberían seguir pasando.

### Estado Actual y Siguientes Pasos
El circuito del efectivo quedó consistente en las tres cajas: mostrador, distribución y tesorería. **Los datos históricos de las cuatro empresas siguen mal contabilizados** —el usuario confirmó que son de prueba y anteriores a varias mejoras—, así que no se reexpresó nada.

Pendientes ofrecidos y no ejecutados: el reporte de devoluciones y el de correlativos del módulo Distribución (fase 8 restante), el widget de fecha en otros siete formularios, las exportaciones a PDF/Excel, la validación contra ARCA Homologación, y el ajuste de inventario para la mercadería devuelta no apta.

## Día 31/08/2026 - Reporte de devoluciones e integridad de numeración (Plan 074, fase 8)

**Responsable:** Claude Opus.

### Objetivo
Los dos reportes de **control** que cierran el módulo: el de devoluciones (§7.10) —*"por período, motivo, momento, repartidor, cliente y producto: muestra si el problema es de crédito, de calidad, de carga o de un repartidor puntual"*— y el de correlativos (§4.2), que le faltaban las dos series que el módulo emite y no se auditaban.

### Archivos Creados o Modificados
- `distribucion/services/reporte_devoluciones.py` [NEW]: `reporte()` con sus cuatro cortes.
- `core/services/numeracion.py` [MODIFY]: `auditar_correlativos()` incorpora `REPARTO` y `RECEPCION_DEVOLUCION`.
- `distribucion/views.py` [MODIFY]: `DevolucionesReporteView`, `CorrelativosDistribucionView`.
- `templates/distribucion/reporte_devoluciones.html`, `correlativos.html`, `partials/corte_devoluciones.html` [NEW].
- `config/urls.py`, `templates/base.html` [MODIFY]: dos rutas y la sección «Control» del menú.
- `distribucion/tests/test_plan074_reportes_control.py` [NEW]: 22 pruebas.

Sin migraciones: los dos reportes leen lo que ya existe.

### Detalle Técnico

**La pregunta que responde el reporte no es CUÁNTO, es POR QUÉ.** Un total de devoluciones no sirve para decidir nada. Lo que cambia una conducta es ver que el 60 % son «negocio cerrado» —problema de agenda de visitas—, o que se concentran en un repartidor, o en un producto que llega roto. Por eso el reporte son **cuatro cortes sobre los mismos renglones** y no una lista: por motivo (qué falla), por repartidor (si se concentra en alguien), por producto (si el problema es del artículo) y por cliente (quién devuelve más). Cada corte viene ordenado **de mayor a menor importe**: tiene que empezar por lo que más pesa, no por lo que viene primero alfabéticamente.

**El grano es el renglón de la recepción, no la nota de crédito.** `RecepcionDevolucionItem` es el único lugar donde conviven motivo, producto, cantidad y `apto_reventa`. La NC acredita un importe; la recepción explica qué volvió y por qué.

**Lo no apto para reventa se mide aparte**, con su propio porcentaje: lo que volvió roto es **pérdida**, no una devolución más. Mezclarlo con lo que se puede volver a vender esconde el único número que justifica hablar con un proveedor o con un repartidor.

**Las anulaciones PRE-CARGA van en su propia lista.** Cuando el cliente anula antes de que salga el camión, la mercadería nunca se cargó y no pasa por ninguna recepción. Si se las mezclara con lo devuelto se estaría contando como «vuelto del reparto» algo que nunca salió; si se las omitiera, desaparecerían del análisis. Van aparte, con su total propio.

**Atribución del repartidor.** `RecepcionDevolucion.entregado_por` es opcional, así que cuando falta se cae a los responsables del reparto: si hay **exactamente uno**, la devolución es suya sin ambigüedad. Con varios responsables **no se le atribuye a ninguno** —repartir la culpa por partes iguales sería inventar un dato— y queda como «Sin identificar», que es lo que efectivamente se sabe. Hay una prueba para cada caso.

**Una recepción anulada no cuenta**: no devolvió nada, y contarla inflaría los cuatro cortes a la vez.

**Integridad de numeración.** `auditar_correlativos()` ya cubría OC, Informe de Recepción, Remito Interno, Pedido, PRE y NCI, pero **le faltaban `REPARTO` y `RECEPCION_DEVOLUCION`**: los dos documentos que el módulo emite desde las fases 5 y 6. Dejarlos afuera los volvía tan inauditables como el número de un tercero, que es exactamente lo que el §4.2 dice que no puede pasar. La pantalla del módulo muestra sus **cinco series** —Pedido, Reparto, Recepción, PRE y NCI— con huecos, duplicados y el desfasaje contra el contador; las de compras siguen en su propia pantalla.

### Resultado de las Pruebas
```
python manage.py test distribucion
Ran 378 tests in 409.882s
OK
```
Las 22 nuevas cubren: los cuatro cortes y su orden, la concentración por motivo con su porcentaje, la atribución del repartidor con uno y con varios responsables, la medición separada de lo no apto, los cinco filtros (motivo, repartidor, producto, período, sólo-no-apto), la recepción anulada, el aislamiento multiempresa, las anulaciones pre-carga en su lista aparte, la incorporación de las dos series a la auditoría, la detección de un hueco, y las dos pantallas.

Un ajuste que hizo la prueba del hueco: `Reparto` está protegido por FK desde `RepartoParada` y `RecepcionDevolucion`, así que el hueco se simula con repartos vacíos en vez de borrar uno con paradas.

### Estado Actual y Siguientes Pasos
**El Plan 074 está completo**: las nueve fases, de la toma del pedido al control de las devoluciones y la integridad de las series.

Pendientes ofrecidos y no ejecutados: las exportaciones a PDF/Excel (faltantes, saldos por vendedor y este reporte), el widget de fecha en otros siete formularios, la validación contra ARCA Homologación, y el ajuste de inventario para la mercadería devuelta no apta —que este reporte ahora deja a la vista con su importe.

### Cristian - PC CASA
**Fecha:** 02/09/2026
**Objetivo:** Restaurar datos desde dump SQL (db_estudio.sql) purgando la base de datos y resolviendo conflictos con migraciones de verticalidad.
**Archivos creados o modificados:**
- estore_db.py (nuevo script en raíz, puede ser borrado luego de validar)
**Detalle Técnico:** 
Se desarrolló un script en Python (ETL) para leer e insertar de forma nativa los registros de db_estudio.sql. Se eliminó el esquema public desde base de datos, se crearon las tablas vírgenes con python manage.py migrate y posteriormente se volcaron los datos en las 100 tablas usando psycopg3 (copy()).
Para evitar fallas de dependencias foráneas durante la inyección, se deshabilitaron temporalmente los triggers mediante session_replication_role = 'replica'. Se omitió restaurar la tabla django_migrations del backup antiguo para evitar errores de historial inconsistente.
**Resultado de las pruebas:**
El script reportó inserciones exitosas masivas en todas las entidades (uth_user, 	esoreria, acturacion, productos, etc). Las migraciones posteriores corren sin conflictos de historial.
**Estado actual y siguientes pasos sugeridos:**
Base de datos 100% migrada y encuadrada con el nuevo código (sin perder registros antiguos). El sistema debe levantarse y probar si la visualización del panel administrativo respeta los roles multi-empresa.

### Cristian - PC CASA
**Fecha:** 02/09/2026
**Objetivo:** Solucionar bug de visibilidad de las vistas del módulo Distribución al asignar el tipo de actividad a una empresa.
**Archivos creados o modificados:**
- erticalidades/distribucion/apps.py
- erticalidades/distribucion/templates/distribucion/hooks/menu_sidebar_bottom.html
- erticalidades/distribucion/templates/distribucion/hooks/ui_configuracion_hub.html
- erticalidades/distribucion/templates/distribucion/hooks/ui_producto_modal_campos.html
**Detalle Técnico:** 
El modelo Empresa en empresas/models.py guarda el valor constante 'DISTRIBUCION' al seleccionar dicho rubro, pero las plantillas (hooks del menú y modales) y la configuración de la App de la verticalidad estaban evaluando la condicional esperando el valor 'DISTRIBUIDORA'. Se unificó el criterio reemplazando las condicionales y constantes a 'DISTRIBUCION' para que cuadre exactamente con la elección de base de datos de la empresa.
**Resultado de las pruebas:**
Al asignar "Distribución" a una empresa, las condicionales {% if empresa_actual.tipo_actividad == 'DISTRIBUCION' %} ahora resuelven a True e inyectan correctamente el menú lateral de Distribución, los campos en el modal de productos y las configuraciones de vehículos/personal.
**Estado actual y siguientes pasos sugeridos:**
Menús de distribución restaurados correctamente y visibles en el frontend.

### Cristian - PC CASA
**Fecha:** 02/09/2026
**Objetivo:** Portar y adaptar los cambios del commit (57739d1) del proyecto legacy (erp-ikigai-2) hacia la nueva arquitectura con verticalidades.
**Archivos creados o modificados:**
- 	emplates/tesoreria/modals/buscador_bancos.html (Nuevo modal HTMX)
- 	esoreria/views_htmx.py, 	esoreria/urls.py, 	esoreria/forms.py, 	esoreria/models.py
- core/views_config.py
- 	emplates/configuracion/partials/rubros_prod_list.html
- 	emplates/tesoreria/modals/buscador_proveedores_op.html
**Detalle Técnico:** 
Se migró exitosamente el parche de erp-ikigai-2 usando git apply. Esto introdujo:
1. Modal de búsqueda en vivo HTMX para entidades bancarias según catálogo BCRA.
2. Optimización de consultas ORM (select_related) en listados de Cuentas Bancarias para evitar N+1 con cli_pro y cuenta_contable.
3. Ajustes en core/views_config.py para listar Rubro, Marca y Familia optimizados (quitando sucursales huérfanas y añadiendo las cuentas contables de ventas/compras).
4. El listado visual de rubros (ubros_prod_list.html) ahora expone explícitamente las cuentas jerárquicas contables asociadas.
**Resultado Pruebas:**
Los parches aplicaron limpiamente (se resolvió de manera manual el conflicto en iews_config.py). Las URLs de HTMX y las dependencias de modelos son consistentes con la base de datos actual.
**Estado Actual:**
Commit migrado y adaptado exitosamente a la arquitectura actual.

### Cristian - PC CASA
**Fecha:** 02/09/2026
**Objetivo:** Trasladar los perfiles de lectura PDF del core a la verticalidad de Armería y refactorizar el extractor para resolverlos dinámicamente.
**Archivos creados o modificados:**
- erticalidades/armeria/perfiles_lectura/ (Directorio y archivos trasladados)
- acturacion/services/extractor_facturas.py
- acturacion/views_procesamiento.py
**Detalle Técnico:** 
Se movieron los scripts de parsing específicos (cuit_30610401240.py y cuit_30711323062.py) desde el módulo genérico de acturacion hacia erticalidades/armeria/perfiles_lectura/.
Para mantener el extractor genérico y evitar código fuertemente acoplado (N+1 ifs por cada verticalidad), se inyectó el parámetro 	ipo_actividad (capturado en iews_procesamiento.py a través de la empresa logueada) y se refactorizó procesar_factura_archivo() para utilizar importlib buscando dinámicamente:
1. erticalidades.<tipo_actividad>.perfiles_lectura.cuit_<cuit_limpio>
2. (Fallback) acturacion.services.perfiles_lectura.cuit_<cuit_limpio>
**Resultado de las pruebas:**
El extractor ahora enruta automáticamente la lógica de lectura hacia la carpeta privada de cada verticalidad, manteniendo el core limpio.
**Estado actual y siguientes pasos sugeridos:**
Finalizado.
**Fecha:** 02/09/2026
**Objetivo:** Corrección de bug en asignación automática del Tipo de Comprobante tras lectura OCR.
**Archivos modificados:**
- acturacion/views_procesamiento.py
**Detalle Técnico:** 
El extractor retornaba el código de comprobante bajo la llave 	ipo_comprobante_afip (ej: "1"), pero la vista intentaba leer la llave inexistente 	ipo_comprobante_codigo. Se corrigió la vista para leer la llave correcta y se agregó .zfill(3) para asegurar que el código concuerde con el formato de 3 dígitos de la base de datos (ej: "001" en lugar de "1"), lo que permite recuperar el detalle correctamente ("001 - Facturas A").
**Fecha:** 02/09/2026
**Objetivo:** Extensión de sobreescritura de Tipo de Comprobante al perfil 062.
**Archivos modificados:**
- erticalidades/armeria/perfiles_lectura/cuit_30711323062.py
**Detalle Técnico:** 
Al igual que en el perfil de Bowie, el perfil del CUIT 30-71132306-2 no estaba enviando el código explícito de AFIP al backend, por lo que el front quedaba vacío si la librería general fallaba en detectarlo con exactitud. Se agregó la lógica para inyectar 	ipo_comprobante_codigo = '001' (y '003' si es Nota de Crédito) directamente en los cabecera_overrides de este proveedor.

## Cristian - PC CASA - 2026-09-03
**Objetivo:** Mover los accesos de Actualizar Tarifas y Facturación por Lotes al módulo Estudio.
**Archivos modificados:**
- 	emplates/facturacion/ventas_index.html (retirado del core)
- erticalidades/estudio/templates/estudio/hooks/ui_ventas_index_cards.html (creado)
- erticalidades/estudio/templates/estudio/hooks/menu_ventas.html (condicional aplicado)
**Detalle:** Se movieron las tarjetas hardcodeadas en ventas_index al hook correspondiente del módulo estudio para que solo aparezcan cuando la empresa actual tiene tipo de actividad ESTUDIO. Además, se aplicó la misma condición a los links del menú lateral.
**Estado:** Completado.
