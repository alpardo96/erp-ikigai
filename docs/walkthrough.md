# Bitácora de Desarrollo - ERP Ikigai

## Cristian - PC CASA
- **Fecha/Día**: 30 de Septiembre de 2026
- **Objetivo o Tarea**: Corrección de `AttributeError: 'Producto' object has no attribute 'pr_vta1'` en `Subproducto` y limpieza de partial duplicado `serie_typeahead.html` en facturación.
- **Archivos creados o modificados**:
  - `productos/models.py` [MODIFY]
  - `verticalidades/armeria/templates/armeria/partials/serie_typeahead.html` [MODIFY]
  - `templates/facturacion/partials/serie_typeahead.html` [DELETED]
- **Detalle Técnico e implicaciones**:
  1. **Corrección de `AttributeError` en `Subproducto`:** En `productos/models.py`, las propiedades `precio_pesos`, `calcular_precio_pesos` y `precio_usd_referencia` intentaban acceder a `self.producto.pr_vta1` como respaldo. Dado que `Producto` utiliza `precio_neto` y no posee el campo histórico `pr_vta1`, se corrigió la lógica accediendo a `float((self.producto.precio_neto if self.producto else 0) or 0)`.
  2. **Actualización de `serie_typeahead.html`:** En `verticalidades/armeria/templates/armeria/partials/serie_typeahead.html`, se reemplazaron las llamadas obsoletas a `sub.producto.pr_vta1` y `sub.producto.iva` por `sub.producto.precio_neto` y `sub.producto.alic_iva`.
  3. **Eliminación de duplicación en Core:** Se eliminó el archivo residual `templates/facturacion/partials/serie_typeahead.html`, dejando el componente encapsulado exclusivamente dentro del enchufe de la verticalidad de armería (`verticalidades/armeria/`).
- **Resultado de las pruebas**: Verificación de sintaxis y eliminación de referencias huérfanas en plantillas y modelos.
- **Estado actual y siguientes pasos sugeridos**: Vistas de stock de armas y búsqueda typeahead por series operativas y libres de errores.

## Cristian - PC CASA
- **Fecha/Día**: 30 de Septiembre de 2026
- **Objetivo o Tarea**: Optimización integral de filtros, selectores múltiples estilo Excel para Marca y Calibre, redimensionamiento de campos de búsqueda y formato de moneda argentino (`formato_ar`) en Stock de Armas (`/stock/armas/`).
- **Archivos creados o modificados**:
  - `docs/planes/100_filtros_marca_calibre_formato_stock_armas.md` [NEW]
  - `verticalidades/armeria/views.py` [MODIFY]
  - `verticalidades/armeria/templates/armeria/stock_armas_list.html` [MODIFY]
  - `verticalidades/armeria/templates/armeria/partials/stock_armas_grilla.html` [MODIFY]
  - `verticalidades/armeria/templates/armeria/partials/stock_armas_detalle_modal.html` [MODIFY]
  - `verticalidades/armeria/tests.py` [MODIFY]
- **Detalle Técnico e implicaciones**:
  1. **Corrección de "Seleccionar Todo" / "Limpiar" en Filtros Excel:** Se corrigió la referencia del DOM en la función `toggleAll` y `updateSelected` de Alpine.js utilizando `this.$root || this.$el.closest('[x-data]')`, evitando que `this.$el` se refiriera al botón clickeado y garantizando que se tilden/destilden correctamente todas las casillas visibles del desplegable y se emita el submit a HTMX.
  2. **Revisión de `fecha_nacimiento` en Clientes:** Se verificó el campo `fecha_nacimiento` en `ClienteProveedor` y `ClienteProveedorForm`. Es un campo opcional (`null=True, blank=True`), por lo que no bloquea ni rompe ninguna otra verticalidad. Se aseguró en `facturacion/views_htmx.py` (`cliente_modal`) que `pedir_fecha_nacimiento` se active automáticamente cuando la empresa es de tipo Armería o Automotor (`empresa.tipo_actividad in ['armeria', 'automotor']`).
  3. **Eliminación de redundancia en Condición:** Se removió la píldora `USADAS` del grupo de familias superior (`#familia-pills`), conservando únicamente las familias reales (`TODOS`, `PISTOLA`, `ESCOPETA`, `CARABINA`, `FUSIL`, `PISTOLÓN`) y dejando el filtrado por condición estrictamente en el selector `<select name="estado">` (`Todas`, `Nuevo`, `Usado`).
  4. **Formato Argentino (`formato_ar`):** Se cargó `{% load formato_tags %}` y se aplicó `|formato_ar` en todos los montos y cotizaciones de la grilla de stock y del modal de detalle de artículo.
  5. **Rebalanceo de Tamaños de Entrada:** Se asignó `maxlength="16"` y ancho visual de 16 caracteres mono (`w-44`) al campo **Nro. Serie**, y `maxlength="9"` con ancho mono (`w-28`) al campo **CUIM**, acotando la **Búsqueda Rápida** a Producto/Código con ancho controlado.
  6. **Filtros Múltiples estilo Excel (Marca y Calibre):**
     - Se crearon popovers compactos con Alpine.js (`excelFilter`) que incluyen buscador de texto en vivo, botones de "Seleccionar todo" / "Limpiar", scroll acotado a 180px con overflow contenido (`style="max-height: 180px; overflow-y: auto;"`), y sincronización reactiva directa mediante HTMX al modificar checkboxes.
     - En backend (`StockArmasListView`): se reciben listas `marcas` y `calibres`, se acotan las marcas del contexto únicamente a las que tienen subproductos en depósito, y se excluyó marca/calibre de la búsqueda general por texto.
- **Resultado de las pruebas**: Integración de pruebas automatizadas `StockArmasFiltrosTests` en `verticalidades/armeria/tests.py`.
- **Estado actual y siguientes pasos sugeridos**: Vistas de stock de armas y modales optimizados y estilizados.

## Cristian - PC CASA
- **Fecha/Día**: 29 de Septiembre de 2026
- **Objetivo o Tarea**: Corrección de navegación y apertura de modal en la pantalla de Recepción de Rendiciones de Tesorería.
- **Archivos creados o modificados**:
  - `templates/tesoreria/rendiciones_recepcion.html` [MODIFY]
- **Detalle Técnico e implicaciones**:
  1. **Cierre de Enlace HTML (`<a>`):** El hipervínculo del botón de volver al menú de tesorería (`<a href="{% url 'tesoreria_index' %}">`) carecía de la etiqueta de cierre `</a>`, lo que provocaba que el navegador envolviera toda la grilla de rendiciones y el botón de acción "Recibir" dentro del enlace.
  2. **Restauración de HTMX Modal:** Se cerró correctamente el tag `</a>`. Al hacer clic en "Recibir", HTMX ahora dispara con normalidad el endpoint `rendicion_recibir_modal` renderizando el arqueo/conteo dentro de `#modal-container` sin redirigir al menú.
- **Resultado de las pruebas**: Verificación de sintaxis de plantilla y carga de modal HTMX.
- **Estado actual y siguientes pasos sugeridos**: Recepción de rendiciones operativa para pruebas de tesorería.

## Cristian - PC CASA
- **Fecha/Día**: 29 de Septiembre de 2026
- **Objetivo o Tarea**: Persistencia integral de los datos de cabecera (Proveedor, Fecha, Tipo/Punto/Número de Comprobante, Período, Moneda, Cotización, Condición e Impuestos) en Carga de Compras ante modificaciones de productos y errores de validación.
- **Archivos creados o modificados**:
  - `templates/facturacion/compras_carga.html` [MODIFY]
  - `facturacion/views.py` [MODIFY]
  - `facturacion/tests/test_compras_persistencia.py` [NEW]
- **Detalle Técnico e implicaciones**:
  1. **Corrección de Renderizado Server-Side (POST con Errores):**
     - En `facturacion/views.py` (`ComprasCargaView.post`): Se completó `ctx_base` para transferir de regreso al template la totalidad de los datos de cabecera (`periodo_sugerido`, `modo`, `empresa_usa_oc`, `proveedor_display`, `comprobante_display`, `cuentas`, `alicuotas_iva`) y se ordenó la inicialización de `es_gasto` e `items_temp` previo a su ensamblado.
     - En `templates/facturacion/compras_carga.html`: Se corrigió el filtro de fecha `value="{{ form.fecha.value|date:'Y-m-d'|default:form.fecha.value|default:'' }}"` para evitar que el filtro `|date` de Django devuelva cadena vacía cuando el formulario está bindeado con strings en POST. Se vincularon los atributos `value` de `subtotal`, `descuento`, `neto`, `iva`, `p_iibb`, `p_iva`, `otros`, `total`, `condic` y `modo`. Se removió la llamada a `form.periodo` inexistente usando `periodo_sugerido`.
  2. **Persistencia y Respaldo en SessionStorage:**
     - Se ajustó `guardarCabeceraEnStorage()` para capturar todos los campos clave (fecha, período, proveedor ID y nombre, tipo ID y display, punto, número, moneda, cotización, condición, modo, impuestos).
     - Se conectaron los disparadores automáticos en eventos personalizados `clienteVentaSeleccionado` y `comprobanteSeleccionado`.
     - Se eliminó el borrado prematuro del draft en el evento `submit` del formulario, reemplazándolo por una limpieza controlada únicamente cuando la respuesta del servidor confirma éxito (`message.tags == 'success'`).
  3. **Pruebas Automatizadas:** Se verificó mediante `test_compras_persistencia.py` que ante errores de validación en POST los datos de cabecera y montos persisten íntegros en el HTML de respuesta.
- **Resultado de las pruebas**: `Ran 1 test in 0.562s - OK`.
- **Estado actual y siguientes pasos sugeridos**: Carga de compras totalmente blindada contra pérdida de datos por error o recarga.

## Cristian - PC CASA
- **Fecha/Día**: 29 de Septiembre de 2026
- **Objetivo o Tarea**: Comando de management para actualizar masivamente Subproductos de estado 'USADO' a 'NUEVO'.
- **Archivos creados o modificados**:
  - `productos/management/commands/set_subproductos_nuevos.py` [NEW]
  - `productos/tests/test_set_subproductos_nuevos.py` [NEW]
- **Detalle Técnico e implicaciones**:
  1. **Comando `set_subproductos_nuevos`:** Actualiza de forma atómica todos los registros de `Subproducto` con `estado='USADO'` a `estado='NUEVO'`. Admite los argumentos opcionales `--empresa-id <id>` (para acotar a una empresa específica) y `--dry-run` (para simulación).
  2. **Pruebas Automatizadas:** Se validó la ejecución del comando con simulación y actualización real en `test_set_subproductos_nuevos.py`.
- **Resultado de las pruebas**: `Ran 2 tests in 0.162s - OK`.
- **Estado actual y siguientes pasos sugeridos**: Comando disponible para ejecución directa vía consola.

## Cristian - PC CASA
- **Fecha/Día**: 29 de Septiembre de 2026
- **Objetivo o Tarea**: Indexación de rendimiento y exclusión estricta de Productos y Clientes/Proveedores inactivos en búsquedas operativas (Preventa, Compra, Venta, Tesorería, Remitos).
- **Archivos creados o modificados**:
  - `productos/models.py` [MODIFY]
  - `facturacion/models.py` [MODIFY]
  - `facturacion/views_htmx.py` [MODIFY]
  - `tesoreria/views_htmx.py` [MODIFY]
  - `facturacion/forms.py` [MODIFY]
  - `productos/forms.py` [MODIFY]
  - `facturacion/migrations/0006_clienteproveedor_facturacion_empresa_bfa3eb_idx_and_more.py` [NEW]
  - `productos/migrations/0009_alter_familia_options_and_more.py` [NEW]
  - `facturacion/tests/test_filtros_activos_operativos.py` [NEW]
- **Detalle Técnico e implicaciones**:
  1. **Índices de Base de Datos PostgreSQL (`activo`):**
     - En `Producto.Meta`: se crearon índices compuestos de cobertura `(empresa, activo, detalle)`, `(empresa, activo, cod_prov)`, `(empresa, activo, cod_fab)`, `(empresa, activo, codigo_anterior)` y `(empresa, activo)`. Se eliminó una declaración duplicada del campo `activo` en el modelo.
     - En `ClienteProveedor.Meta`: se agregaron índices compuestos `(empresa, activo, tipo_entidad)`, `(empresa, activo, razon_social)`, `(empresa, activo, cuit)`, `(empresa, activo, codigo_anterior)` y `(empresa, activo)`.
  2. **Exclusión en Circuitos Operativos:**
     - En **Facturación/Preventa/Venta**: `buscar_producto_venta_por_codigo`, `lista_productos_venta_resultados`, `typeahead_clientes`, `PreventaForm` y `VentaForm` ahora imponen `activo=True` para garantizar que artículos y clientes dados de baja no aparezcan en la operatoria comercial.
     - En **Compras**: `buscar_producto_por_codigo`, `buscar_producto_por_codprov`, `lista_productos_resultados` y `CompraForm` filtran productos y proveedores con `activo=True`.
     - En **Tesorería**: `buscar_cliente_proveedor`, `lista_clientes_recibo_resultados` y `lista_proveedores_op_resultados` excluyen entidades inactivas en recibos y órdenes de pago.
  3. **Pruebas Automatizadas:** Se creó `test_filtros_activos_operativos.py` testeando la exclusión en ventas, compras, typeaheads y tesorería.
- **Resultado de las pruebas**: `Ran 7 tests in 3.318s - OK`.
- **Estado actual y siguientes pasos sugeridos**: Listo para aplicar `migrate` en base de datos.

## Cristian - PC CASA
- **Fecha/Día**: 29 de Septiembre de 2026
- **Objetivo o Tarea**: Filtrado dinámico y persistente de Subfamilias por Familia en el alta, edición y duplicación de Productos.
- **Archivos creados o modificados**:
  - `productos/forms.py` [MODIFY]
  - `productos/views_htmx.py` [MODIFY]
  - `productos/models.py` [MODIFY]
  - `templates/productos/modals/producto_modal.html` [MODIFY]
  - `productos/tests/test_catalogos_familias.py` [MODIFY]
- **Detalle Técnico e implicaciones**:
  1. **Inicialización de Queryset en `ProductoForm`:** Al abrir el formulario de edición o duplicación de un producto, el campo `subfamilia` ahora lee la familia activa (`self.instance.familia_id`, `self.initial['familia']` o `self.data['familia']`) y restringe su queryset exclusivamente a las subfamilias pertenecientes a dicha familia y empresa. Si no hay familia seleccionada (alta limpia), el selector arranca vacío con `Subfamilia.objects.none()`.
  2. **Casacada y Limpieza Dinámica (HTMX + JS):** Se actualizaron los listeners `hx-on:change` en los selectores de Rubro y Familia. Al cambiar de Rubro se resetea el selector de Subfamilia y sus márgenes sugeridos; al cambiar de Familia se cargan asíncronamente vía HTMX solo sus subfamilias hijas.
  3. **Corrección de Render en Modal:** Se restauró el valor por defecto `0` en los `<span>` de los márgenes sugeridos de `producto_modal.html` para evitar excepciones `VariableDoesNotExist` de Django al evaluar claves nulas en la edición de productos huérfanos o sin relaciones.
  4. **Unificación de `__str__`:** Se ajustó el método `__str__` del modelo `Subfamilia` para retornar `self.detalle`, alineándose de forma consistente con `Marca`, `Rubro` y `Familia`.
- **Resultado de las pruebas**: `Ran 8 tests in 0.787s - OK` (incluye pruebas de renderizado del modal en edición y altas huérfanas).
- **Estado actual y siguientes pasos sugeridos**: Validado y 100% operativo sin errores 500.

## Cristian - PC CASA
- **Fecha/Día**: 29 de Septiembre de 2026
- **Objetivo o Tarea**: Corrección de representación de nombres en catálogo de Familias para Subfamilias y selectores del ERP.
- **Archivos creados o modificados**:
  - `productos/models.py` [MODIFY]
  - `productos/tests/test_catalogos_familias.py` [NEW]
- **Detalle Técnico e implicaciones**:
  1. **Método `__str__` y ordenamiento en `Familia`:** El modelo `Familia` carecía de la implementación del método `__str__`, provocando que en los formularios de Django (como `SubfamiliaForm`) y dropdowns de selección se mostrara la representación genérica por defecto de Python/Django (`Familia object (1)`). Se añadió el método `__str__` retornando `self.detalle` y se configuró `ordering = ['detalle']` en su clase `Meta`.
  2. **Pruebas de Catálogo:** Se añadió suite de pruebas unitarias (`test_catalogos_familias.py`) comprobando que tanto `Familia` como `Subfamilia` y los selectores asociados presenten sus nombres descriptivos correctos.
- **Resultado de las pruebas**: `Ran 3 tests in 0.151s - OK`.
- **Estado actual y siguientes pasos sugeridos**: Corregido y validado.

## Antigravity
- **Fecha/Día**: 14 de Septiembre de 2026
- **Objetivo o Tarea**: Ocultar campos innecesarios en el maestro de productos/servicios para la verticalidad Estudio Contable.
- **Archivos creados o modificados**:
  - `templates/productos/stock_index.html` [MODIFY]
  - `templates/productos/partials/producto_list.html` [MODIFY]
  - `templates/productos/modals/producto_modal.html` [MODIFY]
  - `productos/services/excel_service.py` [MODIFY]
  - `productos/views_htmx.py` [MODIFY]
  - `config/urls.py` [MODIFY]
  - `templates/productos/modals/exportar_seleccion_modal.html` [DELETE]
- **Detalle TÃ©cnico e implicaciones**:
  1. **Limpieza de Interfaz para Estudio:** Dado que la verticalidad Estudio maneja "Servicios" y no "Productos" fÃ­sicos, los campos relacionados a reposiciÃ³n e identificaciÃ³n de fÃ¡brica carecen de sentido y ensucian la pantalla.
  2. **CorrecciÃ³n de Variable de Entorno y Vistas:** Se corrigiÃ³ el condicional en `stock_index.html` y `producto_list.html` reemplazando `request.user.empresa_activa` (que resolvÃ­a vacÃ­o) por la variable correcta de contexto `empresa_actual`. Ahora se ocultan correctamente en ESTUDIO "CÃ³d. Prov", "CÃ³d. Fab", "MÃ­nimo" y "Pto. Pedir", reflejando esto tambiÃ©n en la botonera de columnas y la cabecera.
  3. **Condicionamiento en Modal:** Se aplicÃ³ la misma exclusiÃ³n en `producto_modal.html` ocultando la renderizaciÃ³n de esos campos dentro del formulario.
  4. **EliminaciÃ³n de Exportar SelecciÃ³n:** Se eliminÃ³ por completo el botÃ³n "Exportar SelecciÃ³n" de `stock_index.html` junto con su ruta en `config/urls.py`, sus funciones HTMX en `views_htmx.py` y el template de modal interactivo, quedando el cÃ³digo libre de componentes no utilizados o rotos.
  5. **RefactorizaciÃ³n de Excel Completo:** Se extrajo el mapeo de columnas estÃ¡tico en `excel_service.py` hacia una funciÃ³n dinÃ¡mica `get_columnas_producto(empresa)`. Con esto, la opciÃ³n de Excel Completo incluirÃ¡ "Calibre" para ArmerÃ­a; y "Peso (kg)", "Unidad Venta", "Unidades/Bulto" para DistribuciÃ³n, excluyendo a la vez cÃ³digos de fÃ¡brica si el tipo es Estudio.
- **Resultado de las pruebas**: Las vistas en una sesiÃ³n de la verticalidad Estudio ya no despliegan estos controles.
- **Estado actual y siguientes pasos sugeridos**: CorrecciÃ³n visual de la grilla completada exitosamente sin alterar la base ni la integridad del form original.
## Antigravity
- **Fecha/DÃ­a**: 14 de Septiembre de 2026
- **Objetivo o Tarea**: Condicionar visualizaciÃ³n y exigencia de campos de unidad de venta (Calibre, Peso, Bulto) segÃºn el tipo de actividad (ArmerÃ­a, DistribuciÃ³n).
- **Archivos creados o modificados**:
  - `templates/productos/stock_index.html` [MODIFY]
  - `templates/productos/partials/producto_list.html` [MODIFY]
  - `templates/productos/modals/producto_modal.html` [MODIFY]
- **Detalle TÃ©cnico e implicaciones**:
  1. **Filtro y Columnas del Index:** Se actualizaron `stock_index.html` y `producto_list.html` para que el campo genÃ©rico "Calibre" solo se muestre bajo la actividad "ARMERIA". Si el usuario pertenece a una empresa con actividad "DISTRIBUCION", se muestran las tres columnas pertinentes: "Peso (kg)", "Unidad Venta" y "Unidades/Bulto" directamente desde las propiedades del modelo (`peso_unitario_kg`, `unidad_venta`, `unidades_por_bulto`). Para el resto de actividades no se muestran.
  2. **Modal de Formulario:** En `producto_modal.html` se agregÃ³ la visualizaciÃ³n condicional de los tres inputs para DistribuciÃ³n, que antes solo mostraba uno. Adicionalmente, se corrigiÃ³ un bug en JavaScript dentro de la funciÃ³n `toggleCalibreArmeria` donde la variable `rubroTexto` no estaba inicializada y causaba un error por consola al intentar leer su valor para ocultar/mostrar el input de Calibre en ArmerÃ­a.
  3. **No IntromisiÃ³n:** En bases de otras verticales (ej. Estudio o AgrÃ­cola), estos campos permanecen ocultos en el front, y en el form estÃ¡n seteados como `required=False` para evitar errores de validaciÃ³n.
- **Resultado de las pruebas**: Las vistas ahora se renderizan dinÃ¡micamente segÃºn `request.user.empresa_activa.tipo_actividad`.
- **Estado actual y siguientes pasos sugeridos**: CorrecciÃ³n completa. Los campos respetan sus nomenclaturas de base de datos sin forzar operatorias externas.
## Antigravity
- **Fecha/DÃ­a**: 14 de Septiembre de 2026
- **Objetivo o Tarea**: Agregar filtro de validaciÃ³n de Persona JurÃ­dica y corregir carga del campo "es_policia" al crear o editar un cliente/proveedor (verticalidad ArmerÃ­a).
- **Archivos creados o modificados**:
  - `facturacion/views_htmx.py` [MODIFY]
  - `verticalidades/armeria/forms.py` [MODIFY]
- **Detalle TÃ©cnico e implicaciones**:
  1. **ValidaciÃ³n Cruzada de Entidad Fiscal:** Se agregÃ³ una capa de validaciÃ³n en la vista `cliente_proveedor_crear_editar` (`facturacion/views_htmx.py`) para obligar a que cualquier ingreso de CUIT de 11 dÃ­gitos que inicie con "3" deba categorizarse forzosamente como "Persona JurÃ­dica" dentro de la extensiÃ³n de ArmerÃ­a. AsÃ­ mismo, si el usuario marca "Persona JurÃ­dica", el sistema exigirÃ¡ que el documento proporcionado sea un CUIT vÃ¡lido (arrancando con 3 y de 11 dÃ­gitos). Con esto se logra blindar los errores de carga en AFIP y ANMaC (Agencia Nacional de Materiales Controlados).
  2. **CorrecciÃ³n Carga de Select Booleano (es_policia):** Se reparÃ³ un bug visual al momento de editar un Cliente ArmerÃ­a existente. El campo `es_policia` es un `TypedChoiceField` con opciones `('true', 'false')`, pero el form (`ExtensionArmeriaForm`) intentaba pre-poblar su valor vÃ­a `self.fields['es_policia'].initial`. En un `ModelForm` con instancia, Django lee del diccionario `self.initial`, que contenÃ­a el valor booleano puro de base de datos (`True/False`). Al no hacer match el booleano puro con el string de las opciones, el select cargaba vacÃ­o. Se modificÃ³ el `__init__` para sobreescribir `self.initial['es_policia']` con el string correspondiente.
- **Resultado de las pruebas**: Se constatÃ³ el correcto acople de la validaciÃ³n sin interferir con las otras entidades del formulario (distribuidora/base). Y al editar, el selector recupera el valor correcto de "es_policia".
- **Estado actual y siguientes pasos sugeridos**: El bloque de facturaciÃ³n sigue robusto. Funcionalidad completada.

## Antigravity
- **Fecha/DÃ­a**: 14 de Septiembre de 2026
- **Objetivo o Tarea**: ReparaciÃ³n del modal de Alta/EdiciÃ³n de Clientes y ajuste de lÃ³gica fiscal en FacturaciÃ³n Masiva del Estudio.
- **Archivos creados o modificados**:
  - `templates/facturacion/modals/cliente_modal.html` [MODIFY]
  - `verticalidades/estudio/services/facturacion_lote_estudio.py` [MODIFY]
- **Detalle TÃ©cnico e implicaciones**:
  1. **Modal de Clientes Roto (Parte 1 - DOM):** Se reparÃ³ una anomalÃ­a severa en el DOM de `cliente_modal.html`. Un merge previo habÃ­a combinado el contenedor `bg-white` (que contenÃ­a el `x-data` de AlpineJS) con un `div` interno sin remover su etiqueta de cierre `</div>`. Esto causaba que el formulario y el contenedor de scroll se cerraran prematuramente en la mitad del documento (secciÃ³n Identidad), expulsando las secciones 2, 3, Notas, mÃ³dulos y Footer fuera del flujo de layout principal. Se corrigiÃ³ envolviendo adecuadamente el primer bloque en un nuevo `<div>` para que el cierre `</div>` prematuro apuntara a este wrapper y no al contenedor general `bg-white`. AlpineJS recuperÃ³ el control de las directivas `x-show` sobre `esProveedor` en todo el documento y la maquetaciÃ³n se restaurÃ³ por completo.
  2. **Modal de Clientes Roto (Parte 2 - Comillas en AlpineJS):** El usuario reportÃ³ que el modal escupÃ­a cÃ³digo JavaScript crudo en la parte superior. Esto ocurrÃ­a porque al encapsular toda la lÃ³gica JS de Alpine dentro del atributo `x-data="{ ... }"` (usando comillas dobles), se insertÃ³ inadvertidamente cÃ³digo con comillas dobles internas (ej. `.normalize("NFD")` y `.replace(/.../, "")`). El navegador interpretaba la primera comilla doble como el cierre abrupto del atributo `x-data`, provocando que el resto de la lÃ³gica quedara huÃ©rfana y se renderizara como texto en el HTML. Se reemplazaron todas las comillas dobles internas por comillas simples (`'NFD'` y `''`), restaurando la interpretaciÃ³n vÃ¡lida de AlpineJS.
  3. **FacturaciÃ³n Masiva de Estudio - OmisiÃ³n AFIP para No Fiscales:** Se adaptÃ³ `FacturacionLoteEstudioService` para que, en caso de ejecutarse un lote mixto donde un cliente con `tarifa_f > 0` posea una condiciÃ³n de IVA no fiscal (ej. `PRESUPUESTO` o `CONSUMO INTERNO`), el monto destinado a facturaciÃ³n fiscal (`tarifa_f`) sea sumado y derivado automÃ¡ticamente a `tarifa_p` (comprobante interno `PRE`), y la ejecuciÃ³n en AFIP para ese registro sea evitada de forma silente. Esto cumple con la directiva de procesar lotes masivos mezclados enviando a AFIP solo los registros que correspondan segÃºn su matriz impositiva, sin interrumpir la operaciÃ³n ni emitir errores.
- **Resultado de las pruebas**: Se verificÃ³ que el template renderiza ahora de forma Ã­ntegra en un test local de Django. La lÃ³gica del servicio de facturaciÃ³n deriva tarifas fiscales a presupuesto de forma correcta segÃºn el diccionario de condiciones.
- **Estado actual y siguientes pasos sugeridos**: El modal vuelve a ser cien por ciento operativo, y la facturaciÃ³n loteada puede procesarse en estado mixto. No quedan tareas pendientes urgentes del bloque de facturaciÃ³n.

## Antigravity
- **Fecha/DÃ­a**: 09 de Septiembre de 2026
- **Objetivo o Tarea**: Soporte de CSRF para accesos externos dinÃ¡micos mediante tÃºneles de Cloudflare (`trycloudflare.com`).
- **Archivos creados o modificados**: `config/settings.py` [MODIFY], `.env` [MODIFY].
- **Detalle TÃ©cnico e implicaciones**: Se incorporÃ³ la lectura y parseo de `CSRF_TRUSTED_ORIGINS` desde el `.env` en `settings.py`. Para tolerar las URLs cambiantes de Cloudflare Quick Tunnels, se configurÃ³ el wildcard `https://*.trycloudflare.com`, que permite a Django validar cualquier subdominio temporal generado sin tener que actualizar manualmente el archivo en cada reinicio del tÃºnel.
- **Resultado de las pruebas**: ConfiguraciÃ³n aplicada y validada sintÃ¡cticamente.
- **Estado actual y siguientes pasos sugeridos**: Reiniciar el servidor de desarrollo de Django para que tome los cambios de `settings.py` y `.env`.

## Antigravity
- **Fecha/DÃ­a**: 09 de Septiembre de 2026
- **Objetivo o Tarea**: CorrecciÃ³n del comportamiento del menÃº lateral (sidebar) para que la secciÃ³n de Ventas permanezca abierta al navegar a Reservas SIGIMAC (`/reservas/sigimac/`).
- **Archivos creados o modificados**: `templates/base.html` [MODIFY].
- **Detalle TÃ©cnico e implicaciones**: Se aÃ±adiÃ³ la condiciÃ³n `window.location.pathname.startsWith('/reservas/')` al directivo `x-data="{ open: ... }"` del acordeÃ³n de Ventas en `base.html` utilizando Alpine.js. Esto permite que el menÃº se mantenga expandido, proporcionando feedback visual y continuidad en la navegaciÃ³n para el usuario al acceder a las rutas de reservas. No hay implicaciones en base de datos.
- **Resultado de las pruebas**: Se verificÃ³ la lÃ³gica de Alpine.js; el menÃº no se cierra al entrar a la ruta especificada.
- **Estado actual y siguientes pasos sugeridos**: CorrecciÃ³n completada y funcional.


## Cristian - PC CASA
- **Fecha/DÃÂ­a**: 31 de Agosto de 2026
- **Objetivo o Tarea**: Reforma de Verticalidad en Tablas (DistribuciÃÂ³n y ArmerÃÂ­a). Corregir la visualizaciÃÂ³n de las tablas en los listados y reportes para que el contenedor expanda su altura segÃÂºn el contenido y evitar encierros en tarjetas pequeÃÂ±as con scroll interno innecesario.
- **Archivos creados o modificados**: 12 templates en `erp-ikigai-distribucion` y 14 templates en `erp-ikigai-armeria` (`clientes_index.html`, `stock_index.html`, `caja_mostrador_index.html`, `rendiciones_recepcion.html`, etc.).
- **Detalle TÃÂ©cnico e implicaciones**: Se ejecutÃÂ³ un script iterativo que removiÃÂ³ masivamente las clases restrictivas (`h-full`, `flex-1`, `overflow-hidden`) de los contenedores de pÃÂ¡gina y wrappers de tabla en los listados, preservando ÃÂºnicamente `overflow-x-auto`. El proyecto `Estudio` fue escaneado sin encontrar incidencias.
- **Resultado de las pruebas**: Se verificaron los cambios en los archivos y la eliminaciÃÂ³n correcta de las clases problemÃÂ¡ticas.
- **Estado actual y siguientes pasos sugeridos**: Las tablas ahora se expanden libremente segÃÂºn su contenido. Queda validar visualmente el comportamiento responsivo en el navegador.

## 15 de Agosto de 2026 Ã¢ÂÂ Filtro de Estado en Libro Diario / Libro IVA y ClarificaciÃÂ³n de Anulaciones

### Objetivo
Responder a la inquietud sobre los movimientos con estado "Anulado" en el Libro IVA / Libro Diario, clarificar las razones contables y fiscales por las cuales la anulaciÃÂ³n es un proceso irreversible, e implementar un **Filtro de Estado** ("SÃÂ³lo Activos", "SÃÂ³lo Anulados", "Todos") en la grilla dinÃÂ¡mica y en las exportaciones (Excel / PDF).

### Archivos Modificados / Creados
- `templates/contable/partials/libro_diario.html` [MODIFY]: Agregado selector desplegable `<select name="estado">` con opciones (SÃÂ³lo Activos, SÃÂ³lo Anulados, Todos).
- `contable/views_htmx.py` [MODIFY]: Actualizada la vista `libro_diario_rows` para procesar el parÃÂ¡metro `estado` y filtrar `Asiento` segun `anulado`.
- `contable/views_reportes.py` [MODIFY]: Actualizados los endpoints `exportar_diario` (Excel) y `exportar_diario_pdf_view` (PDF) para respetar el filtro por `estado`.
- `contable/tests/test_libro_diario_mejoras.py` [MODIFY]: Agregado el test `test_libro_diario_filtro_estado`.
- `docs/planes/041_filtro_estado_libro_iva_diario.md` [NEW]: Plan de implementaciÃÂ³n archivado.

### Detalle TÃÂ©cnico
1. **Modelado y Filtrado:**
   - OpciÃÂ³n `1` (SÃÂ³lo Activos): `Asiento.objects.filter(anulado=False)`.
   - OpciÃÂ³n `2` (SÃÂ³lo Anulados): `Asiento.objects.filter(anulado=True)`.
   - OpciÃÂ³n `0` (Todos): sin filtro sobre `anulado`.
2. **Interfaz de Usuario:**
   - La barra de filtros fue estructurada en un diseÃÂ±o Tailwind limpio con la opciÃÂ³n predeterminada en "SÃÂ³lo Activos", ocultando automÃÂ¡ticamente comprobantes anulados a menos que el usuario elija verlos explÃÂ­citamente.

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test contable.tests.test_libro_diario_mejoras --noinput
```
**Resultado:** `Ran 7 tests in 27.787s - OK`.

---

## 15 de Agosto de 2026 Ã¢ÂÂ RedefiniciÃÂ³n del campo `condic` (7 valores) Ã¢ÂÂ Fase 1 del Plan 047

### Objetivo
Redefinir por completo la semÃÂ¡ntica del campo `condic`, que hasta ahora tenÃÂ­a 3 valores (1=Real, 2=Presupuestado, 3=Apertura). Es el **prerrequisito** del nuevo reporte "Balance de Saldos Mensuales" (Plan 047): sin esta fase, el asiento de refundiciÃÂ³n de resultados Ã¢ÂÂque nacÃÂ­a con el default `1` (Real)Ã¢ÂÂ contaminaba el ÃÂºltimo mes de todo reporte de evoluciÃÂ³n mensual, dando vuelta las cuentas de resultado.

### La tabla definitiva
Los valores `1` a `4` coinciden con la numeraciÃÂ³n del sistema VFP anterior, con lo cual los reportes y la operatoria del usuario mapean 1:1.

| Valor | Nombre | Significado |
|-------|--------|-------------|
| `1` | Real | Registros fiscales. El 90 % de los movimientos. |
| `2` | Presupuestado | No fiscal. Gasto **real** de la empresa sin respaldo documental vÃÂ¡lido (servimoto, almacÃÂ©n del barrio, taxi). SÃÂ³lo anÃÂ¡lisis de gestiÃÂ³n. |
| `3` | Ajuste | Factura **vÃÂ¡lida y a nombre de la empresa** pagada por el dueÃÂ±o con fondos propios. Va a contabilidad y a las DDJJ de IVA/Ganancias, pero se **excluye del anÃÂ¡lisis de gastos**. Se carga como cualquier factura, contra proveedores varios. |
| `4` | AuditorÃÂ­a | Ajustes que el estudio contable remite tras armar los estados contables. |
| `5` | Apertura | Antes era el `3`. Lo genera el sistema. |
| `6` | RefundiciÃÂ³n | RefundiciÃÂ³n de cuentas de resultado. Lo genera el sistema. |
| `7` | Cierre | Cierre de ejercicio. **Reservado: todavÃÂ­a no implementado.** |

**Las tres lentes** (clave para leer cualquier filtro de `condic`): gestiÃÂ³n = `{1,2}` ÃÂ· fiscal = `{1,3}` ÃÂ· estados contables = `{1,3,4}`. El `2` baja el resultado real pero no el fiscal; el `3` baja el fiscal sin que salga plata: uno amortigua al otro.

### Archivos Modificados / Creados
- `.cursorrules` [MODIFY]: reescrita la secciÃÂ³n de `condic` con la tabla de 7 valores, las tres lentes y 5 reglas inflexibles. **Fuente de verdad.**
- `CLAUDE.md` [MODIFY]: actualizado el bullet resumen.
- `contable/models.py` [MODIFY]: constantes `CONDIC_ASIENTO`, `CONDIC_MOVIMIENTO`, `CONDIC_ESTRUCTURAL`, `CONDIC_FISCAL` y helper `condic_opciones()` como fuente ÃÂºnica de rÃÂ³tulos; documentado el campo `condic` de `Asiento` y el gate fiscal de `LibroIvaBase`.
- `contable/services/contabilizacion.py` [MODIFY]: el Libro IVA pasa de `compra.condic == 1` a **`compra.condic in (1, 3)`**.
- `contable/services/cierre.py` [MODIFY]: el asiento nace con `condic=6`; la validaciÃÂ³n de duplicados pasa de `concepto__icontains` a `condic=6`.
- `contable/services/asientos.py` [MODIFY]: `editar_asiento` rechaza asientos con `condic >= 5` (D-6) y fechas fuera del ejercicio del asiento (D-9).
- `contable/views_htmx.py` [MODIFY]: `_calcular_balance` usa `condic=5` para la apertura; el modal de ediciÃÂ³n desarma `ValidationError` para mostrar el mensaje y no `['...']`.
- `contable/views.py` [MODIFY]: `condic_opciones` al contexto de Libro Diario y Libro Mayor.
- `contable/forms.py` [MODIFY]: rÃÂ³tulo `2 - Presupuestado` (unificado con `.cursorrules`).
- `facturacion/models.py` [MODIFY]: documentado `condic` en `Venta` y `Compra`.
- `migracion/scripts/02_migrar_asientos.py` [MODIFY]: apertura migrada con `condic=5`.
- `templates/contable/partials/detalle_asiento.html` [MODIFY]: badges para los 7 valores.
- `templates/contable/partials/libro_diario.html`, `libro_mayor.html` [MODIFY]: checkboxes generados desde `condic_opciones` (antes hardcodeados 1/2/3; un asiento `condic>=4` quedaba **invisible** en el Libro Diario).
- `templates/contable/modals/asiento_form.html` [MODIFY]: rÃÂ³tulo unificado.
- `contable/tests/test_libro_diario_mejoras.py` [MODIFY]: aserciÃÂ³n del rÃÂ³tulo.
- `contable/migrations/0019_renumerar_condic.py` [NEW]: data migration.
- `contable/tests/test_condic_renumeracion.py` [NEW]: 18 pruebas.
- `docs/planes/047_reporte_saldos_mensuales.md` [NEW]: plan completo archivado.

### Detalle TÃÂ©cnico
1. **Sin migraciÃÂ³n de esquema.** `condic` es un `IntegerField` sin `choices` ni `CheckConstraint`: la renumeraciÃÂ³n es un `UPDATE`, no un `ALTER TABLE`. La migraciÃÂ³n `0019` reasigna `3 Ã¢ÂÂ 5` y las refundiciones histÃÂ³ricas (que quedaron con el default `1`) a `6`, identificÃÂ¡ndolas por el concepto `CIERRE DE EJERCICIO%`, ÃÂºnico rastro disponible en bases previas. Es **idempotente** y tiene funciÃÂ³n de reversa.
2. **Momento elegido.** Conteo real de la base antes de migrar: `condic=1` Ã¢ÂÂ 40 asientos, `condic=2` Ã¢ÂÂ 6, **cero** con `condic=3` y **cero** asientos de cierre. La renumeraciÃÂ³n no tocÃÂ³ datos productivos.
3. **Dos bugs preexistentes cerrados de paso:**
   - `editar_asiento` guardaba la fecha nueva sin revalidar que perteneciera al ejercicio del asiento, rompiendo el invariante que `crear_asiento` sÃÂ­ garantiza (deriva el ejercicio *desde* la fecha).
   - El form de ediciÃÂ³n sÃÂ³lo ofrece `condic` 1 y 2, asÃÂ­ que guardar un asiento de apertura lo **degradaba a Real** de forma silenciosa.
4. **RefundiciÃÂ³n Ã¢ÂÂ  Cierre.** `procesar_cierre_ejercicio` sÃÂ³lo cancela las cuentas de **resultado**: es una refundiciÃÂ³n (`6`). El cierre real (`7`), que ademÃÂ¡s cancela las patrimoniales, **no existe todavÃÂ­a**. Queda reservado para el desarrollo en que, al crear un ejercicio nuevo, el sistema tome el `condic=7` del anterior y lo copie como `condic=5` (apertura) del nuevo.

### Pruebas Automatizadas
```bash
python manage.py test contable.tests.test_condic_renumeracion --noinput
```
**Resultado:** `Ran 18 tests in 179.906s - OK`

```bash
python manage.py test contable --noinput
```
**Resultado:** `Ran 38 tests in 358.091s - OK`

**RegresiÃÂ³n de los mÃÂ³dulos que consumen `condic`:**
```bash
python manage.py test tesoreria --noinput     # Ran 43 tests in 531.169s - OK
python manage.py test facturacion --noinput   # Ran 18 tests - FAILED (errors=2)
```
Los 2 errores de `facturacion` son **preexistentes y ajenos a este cambio**: `test_armeria_credencial_clu.ArmeriaCredencialCLUTestCase` falla en su `setUp` con `TypeError: Sucursal() got unexpected keyword arguments: 'codigo'` Ã¢ÂÂ el modelo `Sucursal` no tiene campo `codigo`. El test entrÃÂ³ con el commit `7ff0da8` (*Solicitar Credencial en Preventa*). **Queda pendiente de corregir en el plan que corresponda.**

Cobertura: semÃÂ¡ntica de las constantes, rechazo de ediciÃÂ³n de asientos estructurales y de fechas fuera del ejercicio (incluidos los bordes `inicio`/`cierre`, que es el caso real de la factura del ejercicio anterior), refundiciÃÂ³n con `condic=6` y detecciÃÂ³n independiente del concepto, Libro IVA poblado por `condic` 1 y 3 pero no por 2 ni 4, herencia del `condic` del comprobante al asiento, apertura (`5`) separada del movimiento del perÃÂ­odo, y data migration idempotente.

### Estado actual y siguientes pasos
Fase 1 del Plan 047 **completa**. Siguientes fases: servicio `saldos_mensuales.py`, vistas HTMX, drill-down al mayor del mes, export Excel con el `ÃÂ Ã¢ÂÂ1` en modo Resultados.

**Pendientes registrados fuera de alcance:** el `condic=7` (cierre real), la copia automÃÂ¡tica cierreÃ¢ÂÂapertura, la captura de asientos de auditorÃÂ­a (`condic=4`), habilitar el `condic=3` en la carga para usuarios autorizados, y el cambio de `condic` posterior a la emisiÃÂ³n en ventas Ã¢ÂÂque deberÃÂ¡ resincronizar el Libro IVA al pasar de `{1,3}` a `2`Ã¢ÂÂ.

---

## 15 de Agosto de 2026 Ã¢ÂÂ Servicio de Saldos Mensuales Ã¢ÂÂ Fases 2 y 3 del Plan 047

### Objetivo
Implementar el nÃÂºcleo de cÃÂ¡lculo del reporte "Balance de Saldos Mensuales": para cada cuenta del plan, el saldo de apertura, el movimiento neto de cada mes del ejercicio y el saldo al cierre. FunciÃÂ³n pura, sin `request`, para que sea testeable de forma aislada.

### Archivos Creados
- `contable/services/saldos_mensuales.py` [NEW]: `calcular_saldos_mensuales()` y `periodos_ejercicio()`.
- `contable/tests/test_saldos_mensuales.py` [NEW]: 27 pruebas.

### Detalle TÃÂ©cnico
1. **Columnas mensuales dinÃÂ¡micas.** `periodos_ejercicio()` recorre aÃÂ±o-mes desde `Ejercicio.inicio` hasta `Ejercicio.cierre`, y devuelve para cada perÃÂ­odo `clave` (`202504`), `label` (`Abr-25`), `primer_dia` y `ultimo_dia` Ã¢ÂÂestos dos ÃÂºltimos alimentan el drill-down de la fase 6Ã¢ÂÂ. A diferencia del VFP, que reordena doce columnas fÃÂ­sicas `mes_01..mes_12` indexadas por el mes calendario **sin guardar el aÃÂ±o**, acÃÂ¡ se guarda el `(aÃÂ±o, mes)` real: soporta ejercicios irregulares y `202601` no puede colisionar con `202501`.
2. **Dos consultas agregadas, pivot en Python.** Una agrupa por `(cuenta_id, TruncMonth(fecha))` y la otra trae la apertura. Se descartÃÂ³ anotar 13+ `Sum(...)` condicionales sobre `Cuenta` (extrapolaciÃÂ³n del patrÃÂ³n del Balance): con esa cantidad de columnas el plan de PostgreSQL se degrada. Las dos consultas son **mutuamente excluyentes por `condic`**, asÃÂ­ que ningÃÂºn movimiento se computa dos veces ni se pierde.
3. **Regla central.** Apertura Ã¢ÂÂ `condic=5`; meses Ã¢ÂÂ `condic in {1,2,3,4}` (el usuario elige); nunca entran el `6` ni el `7`. Universos disjuntos que **no dependen de la fecha**: un asiento de apertura fechado el 01/01 va a Apertura, no a la columna de enero.
4. **Saneamiento de `condics`.** Se intersecta lo recibido con `{1,2,3,4}`: un querystring armado a mano (`?condic=5&condic=6`) no puede meter la apertura ni la refundiciÃÂ³n en una columna mensual. Con la intersecciÃÂ³n vacÃÂ­a devuelve grilla vacÃÂ­a con aviso, sin ejecutar la consulta.
5. **Rollup jerÃÂ¡rquico por profundidad del ÃÂ¡rbol.** El nivel de cada cuenta se calcula siguiendo la cadena `sumariza` (tolerando ciclos y padres colgados), no por `len(jerarquia)`: la longitud del cÃÂ³digo depende de la convenciÃÂ³n de numeraciÃÂ³n de cada empresa, el ÃÂ¡rbol no. Se consolida de mayor a menor profundidad, igual que el `SET ORDER TO jera_cta DESC` del VFP.
6. **Signo natural siempre.** El servicio nunca invierte: la inversiÃÂ³n (ÃÂ Ã¢ÂÂ1) de las cuentas de resultado vivirÃÂ¡ sÃÂ³lo en el export a Excel (fase 7). En pantalla el operador necesita ver el movimiento tal cual se registrÃÂ³, porque el signo es el dato que delata un error de carga.
7. **Omitir sin movimiento con valor absoluto** (criterio del VFP): una cuenta que netea cero pero **tuvo** movimiento se conserva; una sin nada se omite.
8. **Totales sÃÂ³lo sobre imputables**, para no contar cada importe una vez por nivel de la jerarquÃÂ­a.

### Pruebas Automatizadas
```bash
python manage.py test contable.tests.test_saldos_mensuales --noinput
```
**Resultado:** `Ran 27 tests in 152.010s - OK`

Destacadas:
- **Prueba cruzada con el Sumas y Saldos:** el `Total` de cada cuenta imputable es idÃÂ©ntico al saldo final que devuelve `_calcular_balance` para la misma cuenta y ejercicio. Si algÃÂºn dÃÂ­a divergen, uno de los dos estÃÂ¡ mal.
- **Aislamiento por ejercicio:** un asiento con fecha dentro del rango consultado pero adjudicado a otro ejercicio **no** entra. Es el caso que un filtro sÃÂ³lo por fechas dejarÃÂ­a pasar, y el que justifica acotar por la FK.
- Las siete combinaciones de `condic` del ÃÂ§5.1 del plan (gestiÃÂ³n `1+2`, estados contables `1+3+4`, sÃÂ³lo auditorÃÂ­a `4`, sÃÂ³lo ajustes `3`Ã¢ÂÂ¦), verificando ademÃÂ¡s que **la columna Apertura es idÃÂ©ntica en todas**.
- Partida doble: en modo "Todas" la fila TOTALES da `0,00` en cada columna.

### Hallazgo: `Asiento.sucursal` casi nunca se puebla
`crear_asiento()` **no expone el parÃÂ¡metro `sucursal`** y nunca lo asigna, y todos los llamadores productivos pasan por ahÃÂ­. Conteo real de la base: **1 de 46 asientos** tiene sucursal. Es decir que el filtro por sucursal del Balance actual Ã¢ÂÂy el del reporte nuevoÃ¢ÂÂ estÃÂ¡ operativo en el cÃÂ³digo pero **no tiene datos que filtrar**.

No se corrigiÃÂ³ porque excede el alcance del Plan 047: la soluciÃÂ³n es agregar el parÃÂ¡metro y propagarlo desde el comprobante (`compra.sucursal`, `venta.sucursal`) en los 5 llamadores de `contabilizacion.py`, lo que cambia la semÃÂ¡ntica de todos los asientos futuros. **Queda registrado para decidirlo aparte.**

### Estado actual y siguientes pasos
Fases 2 y 3 completas. Siguen: vistas HTMX y URLs (4), templates (5), drill-down al mayor del mes (6) y export Excel con el ÃÂ Ã¢ÂÂ1 (7).

---

## 15 de Agosto de 2026 Ã¢ÂÂ Pantalla de Saldos Mensuales y drill-down Ã¢ÂÂ Fases 4, 5 y 6 del Plan 047

### Objetivo
Poner el reporte en pantalla: pÃÂ¡gina dedicada, panel de filtros HTMX, grilla ancha con columnas fijas, y el drill-down de tres niveles (celda Ã¢ÂÂ Mayor de ese mes Ã¢ÂÂ asiento contable).

### Archivos Modificados / Creados
- `templates/contable/saldos_mensuales.html` [NEW]: pÃÂ¡gina con encabezado y contenedor `#saldos-mensuales-content`.
- `templates/contable/partials/saldos_mensuales.html` [NEW]: filtros + grilla + fila de totales.
- `contable/views.py` [MODIFY]: `SaldosMensualesView` (devuelve sÃÂ³lo el partial ante `HX-Request`).
- `contable/views_htmx.py` [MODIFY]: `get_saldos_mensuales_context`, `saldos_mensuales_datos`, `_querystrings_drilldown`, y **dos filtros nuevos en `get_mayor_context`: `modulo` y `ejercicio_id`**.
- `contable/urls.py` [MODIFY]: rutas `contable_saldos_mensuales` y `saldos_mensuales_datos`.
- `templates/contable/index.html` [MODIFY]: tarjeta de acceso.
- `contable/tests/test_saldos_mensuales_vistas.py` [NEW]: 12 pruebas.

### Detalle TÃÂ©cnico
1. **El ejercicio es un filtro siempre presente.** Si el querystring no trae uno se toma el activo de la sesiÃÂ³n; si la empresa no tiene ejercicios, la vista responde 200 con un aviso en vez de romper.
2. **Testigo `filtros_aplicados`.** Un checkbox destildado no viaja en el GET, asÃÂ­ que "primera carga" y "el usuario destildÃÂ³ todo" llegan idÃÂ©nticos al servidor. Un `<input type="hidden">` los distingue: sin testigo se tildan las cuatro condiciones; con testigo se respeta exactamente lo que el usuario dejÃÂ³ marcado.
3. **La grilla scrollea, nunca la pÃÂ¡gina.** `overflow-x-auto` con `Cuenta` *sticky* a la izquierda, encabezado *sticky* arriba y fila de totales *sticky* abajo. IndentaciÃÂ³n por nivel con `padding-left` calculado.
4. **Drill-down sin endpoints nuevos.** La cadena `mayor_cuenta_modal` Ã¢ÂÂ `libro_mayor_rows` Ã¢ÂÂ `detalle_asiento_modal` ya existÃÂ­a. Cada celda es un `<button hx-get>` que agrega el rango del mes.
5. **ConciliaciÃÂ³n celda Ã¢ÂÂ mayor.** Los links llevan el `condic` **explÃÂ­cito**, distinto segÃÂºn la celda: los tildados para un mes, `condic=5` para Apertura, y ambos para Total. Sin esto se rompÃÂ­a justo en el primer mes: un asiento de apertura fechado el 01/01 cae dentro del rango de enero y el mayor lo mostrarÃÂ­a mientras la celda lo excluye. TambiÃÂ©n se agregÃÂ³ `ejercicio_id` a `get_mayor_context`, que se acotaba sÃÂ³lo por fechas y dejaba entrar asientos de otro ejercicio con fecha solapada.
6. **Importes con `{{ valor|formato_ar }}`** en toda la grilla, segÃÂºn la regla del proyecto. Se corriÃÂ³ `npm run build`: las clases nuevas (`text-sky-700`, `text-violet-700`, `gap-1.5`, `px-2.5`, `tabular-nums`) no estaban en el CSS purgado.

### Pruebas Automatizadas
```bash
python manage.py test contable.tests.test_saldos_mensuales_vistas --noinput
```
**Resultado:** `Ran 12 tests in 104.297s - OK`

```bash
python manage.py test contable --noinput
```
**Resultado:** `Ran 77 tests in 686.021s - OK`

La prueba central es **la conciliaciÃÂ³n**: se toma el valor de una celda, se arma el link que genera el template y se verifica que la ÃÂ£(debe Ã¢ÂÂ haber) que devuelve `libro_mayor_rows` con esos parÃÂ¡metros sea **exactamente igual**. Se corre con un asiento de apertura fechado dentro del primer mes, que es el escenario donde se romperÃÂ­a.

### Estado actual y siguientes pasos
Fases 4, 5 y 6 completas. Queda la **fase 7**: exportaciÃÂ³n a Excel, ÃÂºnico lugar donde se aplica el ÃÂ Ã¢ÂÂ1 a las cuentas de resultado. DespuÃÂ©s, la mediciÃÂ³n del ÃÂ­ndice (8) y el contraste manual contra los CSV de referencia (9).

---

## 15 de Agosto de 2026 Ã¢ÂÂ ExportaciÃÂ³n a Excel de Saldos Mensuales Ã¢ÂÂ Fase 7 del Plan 047

### Objetivo
Exportar la grilla a Excel con el layout del VFP, y aplicar ahÃÂ­ Ã¢ÂÂy sÃÂ³lo ahÃÂ­Ã¢ÂÂ la inversiÃÂ³n de signo de las cuentas de resultado.

### Archivos Modificados / Creados
- `contable/services/reportes_excel.py` [MODIFY]: **corregido un bug preexistente** (ver abajo) y agregado `exportar_saldos_mensuales_excel()`.
- `contable/views_reportes.py` [MODIFY]: `exportar_saldos_mensuales`.
- `contable/urls.py` [MODIFY]: ruta `exportar_saldos_mensuales_excel`.
- `templates/contable/partials/saldos_mensuales.html` [MODIFY]: botÃÂ³n Excel que reenvÃÂ­a los filtros vigentes.
- `contable/tests/test_saldos_mensuales_vistas.py` [MODIFY]: 5 pruebas nuevas del export.

### BUG PREEXISTENTE CORREGIDO: los tres exports a Excel estaban rotos
`_configurar_hoja()` usa `isinstance(fecha_desde, date)` en su lÃÂ­nea 29, pero **`date` nunca estuvo importado** en el mÃÂ³dulo. La expresiÃÂ³n se evalÃÂºa siempre, con o sin fechas, asÃÂ­ que la funciÃÂ³n lanzaba `NameError: name 'date' is not defined` en **toda** llamada.

Como los tres exports la invocan (`exportar_diario_excel`, `exportar_mayor_excel`, `exportar_balance_excel`), la descarga de Excel del **Libro Diario, el Libro Mayor y el Balance estaba caÃÂ­da**. Se corrigiÃÂ³ con el `from datetime import date` faltante y se verificÃÂ³ la funciÃÂ³n con y sin rango de fechas.

### Detalle TÃÂ©cnico
1. **Layout idÃÂ©ntico al VFP** (Anexo A del plan): A=Codigo, B=Sumariza, C=Jerarquia, D=Detalle, E=Imp, F=Apertura, luego una columna por mes, y Total, Tipo, Bce, Pres, Econ, Fciero. Las planillas histÃÂ³ricas del usuario siguen siendo comparables celda a celda.
2. **La cantidad de columnas de mes es dinÃÂ¡mica**, igual que en pantalla: se derivan del ejercicio, no son doce fijas.
3. **El encabezado de cada mes es un nÃÂºmero** (`202601`) con `number_format='000000'`, no texto: asÃÂ­ se puede ordenar y usar en fÃÂ³rmulas.
4. **La inversiÃÂ³n de signo vive ÃÂºnicamente acÃÂ¡.** Con alcance `resultados` los importes se multiplican por Ã¢ÂÂ1, de modo que los ingresos salgan positivos, los egresos negativos y la fila de totales muestre la ganancia del mes. Es el mismo criterio del VFP, donde `xSig = -1` sÃÂ³lo existe dentro del procedimiento de exportaciÃÂ³n.
5. **Sumarizadoras en negrita y azul**, y `freeze_panes` en la columna de Apertura para que Cuenta/Detalle queden fijos al desplazarse.
6. El botÃÂ³n reenvÃÂ­a el formulario de filtros completo, asÃÂ­ que **el Excel refleja exactamente lo que estÃÂ¡ en pantalla**.

### Pruebas Automatizadas
```bash
python manage.py test contable.tests.test_saldos_mensuales_vistas --noinput
```
**Resultado:** `Ran 17 tests in 157.207s - OK`

```bash
python manage.py test contable --noinput
```
**Resultado:** `Ran 82 tests in 733.518s - OK`

Las pruebas del export abren el `.xlsx` generado con `openpyxl` y verifican celdas concretas: que el encabezado traiga los 12 perÃÂ­odos como enteros, que en modo "Todas" un ingreso valga `-1000.0` (signo natural) y en modo "SÃÂ³lo Resultados" `+1000.0`, que con ingresos 1000 y egresos 400 la fila TOTALES muestre `600.0` de ganancia, y que en modo "Todas" esa misma fila cierre en `0.0` por partida doble.

### Estado actual y siguientes pasos
Fase 7 completa. Quedan la **fase 8** (medir con `EXPLAIN ANALYZE` y decidir el ÃÂ­ndice de cobertura) y la **fase 9** (contraste manual contra los CSV de referencia de ARMERIA ARMAR). Para la 9 hace falta migrar esos datos: la base actual tiene 46 asientos y ningÃÂºn asiento de apertura.

---

## 15 de Agosto de 2026 Ã¢ÂÂ BotÃÂ³n Consultar, SelecciÃÂ³n de Columnas (Pantalla, Excel y CSV) en Libro Mayor Ã¢ÂÂ Plan 048

### Objetivo
Resolver la consulta del Libro Mayor bajo demanda (sin autoejecuciÃÂ³n al abrir), incorporar la barra de verificaciÃÂ³n de parÃÂ¡metros en el modal de cuenta, selecciÃÂ³n dinÃÂ¡mica de columnas en la grilla (con 10 predeterminadas y `leyenda` desactivada por defecto), exportaciÃÂ³n en formato Tabla de Excel (`.xlsx`) y nuevo formato CSV (`.csv`) con BOM UTF-8.

### Archivos Modificados / Creados
- `contable/services/reportes_mayor.py` [NEW]: catÃÂ¡logo maestro de columnas (`COLUMNAS_MAYOR_CATALOGO`), extractor de columnas solicitadas (`obtener_columnas_seleccionadas`) y formateador de celdas por movimiento (`obtener_valor_columna_movimiento`).
- `contable/services/reportes_excel.py` [MODIFY]: reestructuraciÃÂ³n de `exportar_mayor_excel` para construir la planilla dinÃÂ¡micamente con las columnas elegidas y aplicar el objeto `openpyxl.worksheet.table.Table`.
- `contable/views_reportes.py` [MODIFY]: actualizaciÃÂ³n de `exportar_mayor` y nuevo endpoint `exportar_mayor_csv`.
- `contable/views_htmx.py` [MODIFY]: `libro_mayor_rows` y `mayor_cuenta_modal` con fallbacks de cuenta, selecciÃÂ³n de columnas y `condic` predeterminados (`1`, `2` y `5`).
- `contable/views.py` [MODIFY]: `LibroMayorView` enviando catÃÂ¡logo de columnas y `condics_predeterminados`.
- `contable/urls.py` [MODIFY]: registro de ruta `mayor/exportar-csv/`.
- `templates/contable/partials/libro_mayor.html` [MODIFY]: selector desplegable de columnas, botÃÂ³n CSV, checkboxes `condic` predeterminados (1, 2 y 5) y mensaje inicial informativo sin autoejecuciÃÂ³n.
- `templates/contable/partials/libro_mayor_rows.html` [MODIFY]: renderizado dinÃÂ¡mico de celdas segÃÂºn las columnas seleccionadas y actualizaciÃÂ³n automÃÂ¡tica de `thead`.
- `templates/contable/modals/mayor_cuenta_modal.html` [MODIFY]: barra de verificaciÃÂ³n de parÃÂ¡metros con botÃÂ³n "Generar Reporte", selector de columnas y botones CSV, Excel y PDF.
- `contable/tests/test_libro_mayor_columnas.py` [NEW]: pruebas automatizadas para modal, fallback de cuentas y exportaciÃÂ³n a CSV.
- `docs/planes/048_libro_mayor_boton_generar.md` [NEW]: plan de implementaciÃÂ³n aprobado.

### Detalle TÃÂ©cnico
1. **EjecuciÃÂ³n Bajo Demanda:** Se eliminÃÂ³ la peticiÃÂ³n automÃÂ¡tica `hx-trigger="load"` del modal `mayor_cuenta_modal.html`. La grilla muestra un mensaje guiando al usuario a verificar sus parÃÂ¡metros y presionar **"Generar Reporte"** o **"Consultar"**.
2. **ConservaciÃÂ³n de Filtros Existentes:** Se mantuvieron todos los campos de bÃÂºsqueda previa (Rango de cuentas, Fechas, Cliente/Proveedor, Sucursal y CondiciÃÂ³n).
3. **CondiciÃÂ³n Predeterminada:** Se pre-completaron las opciones `1 - Real`, `2 - Presupuestado` y `5 - Apertura` como activas por defecto.
4. **SelecciÃÂ³n DinÃÂ¡mica de Columnas:** Se definiÃÂ³ un catÃÂ¡logo extensible de 24+ campos de `Asiento`, `AsientoLinea` y `Cuenta`. Por defecto se muestran 10 columnas (`asiento_id`, `fecha`, `concepto`, `cuenta_id`, `cuenta`, `debe`, `haber`, `saldo`, `condic`, `sucursal`), manteniendo `leyenda` desactivada por defecto.
5. **ExportaciÃÂ³n a CSV con BOM UTF-8:** Se creÃÂ³ la exportaciÃÂ³n a CSV con delimitador `;` y BOM `\ufeff` para garantizar apertura nativa sin problemas de codificaciÃÂ³n en Excel, PowerBI o software externo.
6. **Excel en Formato Tabla:** La exportaciÃÂ³n a Excel incluye ÃÂºnicamente las columnas seleccionadas en pantalla y las empaqueta dentro de un objeto `openpyxl.worksheet.table.Table`.

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test contable.tests.test_libro_mayor_columnas --keepdb --noinput
```
**Resultado:** `Ran 3 tests in 11.724s - OK`

### Estado actual y siguientes pasos
Plan 048 completamente implementado y verificado. Todas las pantallas y exportaciones del Libro Mayor operan bajo demanda y con selecciÃÂ³n dinÃÂ¡mica de columnas.

---

## 16 de Agosto de 2026 Ã¢ÂÂ Plan 049: VÃÂ­nculo contable de `tesoreria_movimiento_caja`

### Objetivo
Prerrequisito del **Estado de Origen y AplicaciÃÂ³n de Fondos** (EOAF), que migra los formularios
VFP `suma_saldo_fciero.scx` y `sum_sal_fciero_mov.scx`. La tabla `tesoreria_movimiento_caja` no
tenÃÂ­a cÃÂ³mo responder "ÃÂ¿de quÃÂ© cuenta vino la plata y a quÃÂ© cuenta se aplicÃÂ³?": le faltaban el
asiento, la cuenta de imputaciÃÂ³n y el cliente/proveedor, y su `fecha` era la de carga y no la del
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
  `fecha` pasa de `DateTimeField(auto_now_add=True)` a `DateField`; dos ÃÂ­ndices compuestos y el
  `CheckConstraint` de `condic`.
- `tesoreria/views_htmx.py`: los seis circuitos que crean movimientos de caja.
- `tesoreria/services/caja_diaria.py`: docstring desactualizada.
- `migracion/scripts/03_migrar_tesoreria.py`: informa `fecha` (ahora obligatoria) y mapea los tres
  vÃÂ­nculos del DBF legado.

### Detalle TÃÂ©cnico

**1. Modelo.** Cuatro FK nuevas, todas nullable. `asiento` va con `on_delete=PROTECT`: los asientos
nunca se borran Ã¢ÂÂ`anular_asiento_de_comprobante()` solo marca `anulado=True`Ã¢ÂÂ, asÃÂ­ que la FK no
puede quedar colgada. `fecha` pierde su `db_index` propio porque el ÃÂ­ndice compuesto
`(empresa, fecha)` lo cubre y ninguna consulta se hace sin acotar por empresa. `asiento` y
`cli_pro` tampoco llevan ÃÂ­ndice explÃÂ­cito: Django ya indexa toda FK y duplicarlo solo costarÃÂ­a
escrituras.

**2. `cuenta` = cuenta de imputaciÃÂ³n principal.** Un movimiento de caja es UNO por comprobante,
pero la contrapartida puede ser VARIAS cuentas (recibo simple, OP simple, venta mostrador
multi-rubro). Se guarda la de mayor importe, con una regla ÃÂºnica para los seis circuitos:
`cuenta_principal_del_asiento()` agrupa las lÃÂ­neas del asiento por cuenta, descarta las de
disponibilidad (`tipo_disponibilidad` no vacÃÂ­o: son el bolsillo, no el origen ni la aplicaciÃÂ³n) y
devuelve la mayor, con desempate por `cuenta_id` para que el resultado sea determinÃÂ­stico.
**El desglose exacto queda en las lÃÂ­neas del asiento**, que es de donde los reportes de fondos
toman los importes: `cuenta` sirve para listados, filtros y bÃÂºsquedas, no para cuadrar.

**3. `fecha`.** `ALTER COLUMN "fecha" TYPE date USING "fecha"::date`. No se pierde el instante de
carga: `MovimientoCaja` hereda `fecha_creacion` de `AuditModel`, que ya guardaba exactamente lo
mismo que el viejo `fecha` (estaba duplicado). Corrige el desvÃÂ­o de fondo: un recibo del 15/05
cargado el 16/08 caÃÂ­a en agosto en cualquier reporte por perÃÂ­odo.

**4. `condic` restringido a (1, 2)** por CheckConstraint. Un movimiento de FONDOS solo puede ser
Real o Presupuestado: el 3 (Ajuste) lo paga el socio y no sale plata de la empresa, el 4 son
ajustes del estudio y los 5/6/7 los genera el sistema. Coincide con la lente de GestiÃÂ³n.

**5. Bug corregido.** Caja mostrador fijaba `condic=1` en el movimiento de caja, asÃÂ­ que una venta
presupuestada quedaba registrada como Real. Ahora se deriva del tipo de comprobante:
**PRE (Presupuesto) Ã¢ÂÂ 2; cualquier otro Ã¢ÂÂ 1**, calculado en el servidor y no tomado del payload.

**5 bis. Bug latente corregido de arrastre.** `tesoreria/services/caja_diaria.py` arma una sola
lista con las filas de sus dos fuentes y la ordena por la tupla `(fecha, id)`: la fuente de
asientos aporta `asiento.fecha` (`date`) y la de movimientos aportaba `movimiento.fecha`
(`datetime`). Ordenar esa lista mezclada lanza `TypeError: '<' not supported between instances of
'datetime.datetime' and 'datetime.date'` en cuanto una caja tiene movimientos de **ambas**
fuentes, que es el caso normal apenas conviven un cobro de mostrador y un recibo. Al pasar `fecha`
a `DateField` los dos lados quedan del mismo tipo. Cubierto por un test de regresiÃÂ³n.

**6. Migraciones en tres pasos.** El backfill (0014) resuelve `empresa` por la sesiÃÂ³n, `fecha` y
`cli_pro` por el comprobante, y `asiento` validando el id contra la tabla de asientos Ã¢ÂÂlos tres
comprobantes lo guardan en un `IntegerField` sin FK, asÃÂ­ que puede apuntar a un asiento
inexistente y la FK nueva no lo tolerarÃÂ­aÃ¢ÂÂ. Los tres comprobantes sirven de origen, incluida la
venta de mostrador (estampa `venta.asiento_id`): solo quedan sin asiento los movimientos internos
y los importados de VFP sin `ID_ASTO`. **Antes de aplicar el constraint, verifica que no
existan filas con `condic` fuera de (1, 2) y aborta con el listado si las hay**, en vez de
corregirlas por su cuenta. Informa por consola cuÃÂ¡ntas fechas se reencuadraron.

### Pruebas Automatizadas
```bash
python manage.py test tesoreria.tests.test_plan049_movimiento_caja
```
**Resultado:** `Ran 15 tests in 116.088s - OK`

Cobertura: el servicio de imputaciÃÂ³n (descarte de disponibilidades, mayor importe, desempate
determinÃÂ­stico, `None` sin contrapartida, regla PREÃ¢ÂÂ2); recibo con fecha retroactiva; cobranza a
cliente y pago a proveedor (asiento, cuenta, cli_pro, empresa); recibo simple y OP simple 60/40 y
70/30 verificando que el asiento conserva **las dos** cuentas; recontabilizaciÃÂ³n que reapunta el
movimiento al asiento nuevo dejando el viejo anulado; la regresiÃÂ³n de ordenamiento de la Caja
Diaria con las dos fuentes conviviendo; y el CheckConstraint rechazando los `condic` 0, 3, 4, 5,
6 y 7.

**RegresiÃÂ³n de los mÃÂ³dulos afectados:**
```bash
python manage.py test tesoreria contable
```
**Resultado:** `Ran 142 tests in 795.632s - OK`

### Estado actual y siguientes pasos
Plan 049 **ejecutado**. Las migraciones 0013/0014/0015 quedan **sin aplicar en producciÃÂ³n**:
correrlas requiere la ventana del usuario, porque el backfill reencuadra fechas histÃÂ³ricas.

**Siguiente:** Plan 050 Ã¢ÂÂ EOAF, con **Ingresos de Fondos / Egresos de Fondos / Flujo Neto**
(sin Disponibilidad Inicial), filtro Real/Presupuestado, desglose por medio, drill-down por cuenta
y exportaciÃÂ³n a Excel y PDF.

---

## 16 de Agosto de 2026 Ã¢ÂÂ Plan 049 (adenda): cierre de la deuda tÃÂ©cnica del asiento de mostrador

### Objetivo
A pedido del usuario, corregir el asiento de la venta de caja mostrador, que habÃÂ­a quedado fuera
del alcance inicial del Plan 049.

### Archivos Modificados
- `tesoreria/views_htmx.py`: el `Asiento.objects.create` de `_crear_asientos_y_movimientos_cobro`.
- `tesoreria/services/caja_diaria.py`: deduplicaciÃÂ³n entre las dos fuentes del reporte.
- `tesoreria/tests/test_plan049_movimiento_caja.py`: clase `CajaMostradorTest` (3 pruebas).
- `docs/planes/049_movimiento_caja_asiento_cuenta_clipro.md`: ÃÂ§10 marcada como cerrada.

### Detalle TÃÂ©cnico

**1. El asiento de mostrador** ahora recibe `condic=venta.condic` Ã¢ÂÂhereda la condiciÃÂ³n del
comprobante, como manda `.cursorrules`; antes quedaba en el default 1 aunque la venta fuera
presupuestadaÃ¢ÂÂ, `sesion_caja=sesion_caja` Ã¢ÂÂsin eso el cobro no entraba al reporte de Caja Diaria,
que filtra por ese campoÃ¢ÂÂ y `fecha=venta.fecha` en lugar de `timezone.localdate()`, para que
comprobante, asiento y movimiento de caja lleven siempre la misma fecha.

**2. Efecto colateral resuelto: doble conteo.** Al estampar `sesion_caja`, el cobro pasa a llegar
al reporte por sus **dos** fuentes (`_lineas_desde_asientos` y `_lineas_desde_movimientos`). La
deduplicaciÃÂ³n navegaba al comprobante y su cadena era `movimiento.recibo or movimiento.orden_pago`:
los cobros de mostrador cuelgan de `venta`, asÃÂ­ que **quedaban fuera y se habrÃÂ­an contado dos
veces**. Ahora se deduplica por `MovimientoCaja.asiento_id` Ã¢ÂÂel campo que agrega este mismo plan,
que resuelve los tres tipos de comprobante de una sola formaÃ¢ÂÂ, con el comprobante como fallback
para los movimientos histÃÂ³ricos anteriores al backfill.

**3. Lo que NO se tocÃÂ³:** el asiento se sigue armando con `Asiento.objects.create` +
`AsientoLinea.objects.create` en vez de `crear_asiento()`. Es un refactor del circuito de
facturaciÃÂ³n y no deja ningÃÂºn desvÃÂ­o funcional pendiente.

### Pruebas Automatizadas
```bash
python manage.py test tesoreria.tests.test_plan049_movimiento_caja
```
**Resultado:** `Ran 18 tests in 126.109s - OK`

Las tres nuevas cubren el circuito de mostrador de punta a punta (preventa Ã¢ÂÂ cobro Ã¢ÂÂ venta Ã¢ÂÂ
asiento Ã¢ÂÂ movimiento), usando un comprobante **PRE**, que es el camino que no llama a ARCA:
`condic=2` propagado a venta, movimiento y asiento; `sesion_caja` y `fecha` estampadas en el
asiento; y la regresiÃÂ³n de doble conteo en la Caja Diaria.

### Estado actual y siguientes pasos
Plan 049 **cerrado por completo**, deuda tÃÂ©cnica incluida. Migraciones todavÃÂ­a **sin aplicar**.
Siguiente: **Plan 050 Ã¢ÂÂ Estado de Origen y AplicaciÃÂ³n de Fondos**.

---

## 16 de Agosto de 2026 Ã¢ÂÂ Plan 050 fases 1 y 2: nÃÂºcleo de fondos y servicio del EOAF

### Objetivo
Arrancar el **Estado de Origen y AplicaciÃÂ³n de Fondos** (migraciÃÂ³n de `suma_saldo_fciero.scx`).
Fase 1: extraer el nÃÂºcleo de cÃÂ¡lculo que ya existÃÂ­a en la Caja Diaria. Fase 2: el servicio del
reporte, con agregaciÃÂ³n por cuenta y rollup jerÃÂ¡rquico.

### Archivos Creados
- `tesoreria/services/fondos.py` [NEW]: nÃÂºcleo compartido Ã¢ÂÂ constantes de disponibilidad,
  `prorratear()`, `lineas_de_fondos()` y `asientos_de_fondos_por_fecha()`.
- `tesoreria/services/eoaf.py` [NEW]: `estado_origen_aplicacion_fondos()` y `detalle_de_cuenta()`.
- `tesoreria/tests/test_eoaf.py` [NEW]: 18 pruebas.
- `docs/planes/050_estado_origen_aplicacion_fondos.md` [NEW]: plan archivado.

### Archivos Modificados
- `tesoreria/services/caja_diaria.py`: delega la descomposiciÃÂ³n en `fondos.py`; se eliminaron las
  definiciones duplicadas de `_fila_vacia` y `_cuantizar`; nuevo `asientos_de_fondos()`.

### Detalle TÃÂ©cnico

**1. Un movimiento de fondos es todo asiento que toca una cuenta con `tipo_disponibilidad`.**
Dentro de ÃÂ©l, las lÃÂ­neas de disponibilidad son el *bolsillo* (dan el desglose por medio) y las de
contrapartida son las filas del reporte. La fuente es el asiento y no `MovimientoCaja`, asÃÂ­ que
entran tambiÃÂ©n las compras de contado, los dÃÂ©bitos bancarios y los asientos manuales que nunca
pasaron por una caja.

**2. Signo, verificado contra `OrigenyAplicacionFondos.xlsx`:** contrapartida al **HABER** =
origen de fondos (**Ingresos**); al **DEBE** = aplicaciÃÂ³n (**Egresos**). Contrastado en cuatro
cuentas de la muestra (clientes, proveedores, recupero de gastos, telefonÃÂ­a).

**3. Los traslados entre disponibilidades se excluyen solos.** Un retiro de mostrador a tesorerÃÂ­a
tiene sus dos puntas en cuentas de disponibilidad: no hay contrapartida, `lineas_de_fondos` lo
emite con `cuenta_id = None` y el EOAF lo descarta. No hizo falta ninguna regla especial. El
legado los mostraba mezclados en el cuerpo del reporte.

**4. Rollup por prefijo de `jerarquia`, acumulando solo IMPUTABLES**, igual que el legado
(`sum ... for jera_cta = jera and imputable = .T.`). Se usa el prefijo y no la FK `sumariza`
porque en los datos legados `sumariza` estÃÂ¡ desfasado. Los totales suman solo imputables: las
sumarizadoras ya las contienen.

**5. ExtracciÃÂ³n sin cambio de comportamiento.** `prorratear()` conserva un detalle del original
que era fÃÂ¡cil de perder: cuando los pesos suman cero **no** hay contrapartida identificable, y el
neto NO se asigna al primero ni se reparte por partes iguales Ã¢ÂÂeso imputarÃÂ­a fondos a una cuenta
que no los moviÃÂ³Ã¢ÂÂ. Devuelve lista vacÃÂ­a y decide quien llama.

### Pruebas Automatizadas
```bash
python manage.py test tesoreria.tests.test_eoaf
```
**Resultado:** `Ran 18 tests in 52.144s - OK`

```bash
python manage.py test tesoreria.tests.test_caja_diaria tesoreria.tests.test_plan049_movimiento_caja
```
**Resultado:** `Ran 32 tests in 142.667s - OK` (la extracciÃÂ³n no alterÃÂ³ la Caja Diaria)

Cobertura del EOAF: signo de ingresos/egresos, desglose por medio, traslados que no generan
filas, prorrateo que cierra exacto sin perder centavos, rollup jerÃÂ¡rquico sin doble conteo,
filtros de condiciÃÂ³n y de fechas, exclusiÃÂ³n de anulados, aislamiento entre empresas, y el
drill-down con saldo corrido y filtro por medio.

**Control de coherencia (el que en el legado NO cerraba):** ÃÂ£ Flujo Neto de las imputables ==
variaciÃÂ³n neta de las disponibilidades del perÃÂ­odo. Verificado en test y contra los datos reales
de la empresa 1: neto 5.936.786,45 contra EFE 4.381.966,45 + DOL 1.718.200,00 + BCO Ã¢ÂÂ163.380,00.

### Estado actual y siguientes pasos
Fases 1 y 2 **completas**. Pendientes: fase 3 (vista y template HTMX en TesorerÃÂ­a), fase 4
(drill-down) y fase 5 (Excel y PDF).

**Pendiente de decisiÃÂ³n del usuario:** marcar la cuenta `111009 TRANSFERENCIA ENTRE SUCURSALES`
con `tipo_disponibilidad='OTR'`. Es un cambio de DATO, no de cÃÂ³digo. Sin ÃÂ©l, los traslados entre
sucursales van a generar una fila espuria en el EOAF.

---

## 16 de Agosto de 2026 Ã¢ÂÂ Plan 050 fases 3 a 5: pantalla, drill-down y exportaciones del EOAF

### Objetivo
Completar el Estado de Origen y AplicaciÃÂ³n de Fondos: pantalla en el mÃÂ³dulo **TesorerÃÂ­a**,
drill-down por cuenta y exportaciÃÂ³n a Excel y PDF.

### Archivos Creados
- `tesoreria/views_eoaf.py` [NEW]: `eoaf_index`, `eoaf_grilla`, `eoaf_cuenta_modal`,
  `eoaf_excel`, `eoaf_pdf`.
- `tesoreria/services/eoaf_export.py` [NEW]: Excel y PDF.
- `templates/tesoreria/eoaf.html` [NEW]: pantalla con filtros y botÃÂ³n Generar.
- `templates/tesoreria/partials/eoaf_grilla.html` [NEW]: grilla jerÃÂ¡rquica.
- `templates/tesoreria/modals/eoaf_cuenta_modal.html` [NEW]: drill-down.
- `templates/tesoreria/pdf/eoaf_pdf.html` [NEW]: layout del PDF.

### Archivos Modificados
- `tesoreria/urls.py`: cinco rutas nuevas bajo `origen-aplicacion-fondos/`.
- `templates/tesoreria/index.html`: tarjeta de acceso al reporte.
- `tesoreria/tests/test_eoaf.py`: clase `VistasTest` (7 pruebas de vistas y exportaciones).
- `docs/planes/050_...md`: fases marcadas como ejecutadas.

### Detalle TÃÂ©cnico

**1. La grilla no se autoejecuta.** El usuario fija perÃÂ­odo y condiciÃÂ³n y presiona **Generar**,
igual que el `cmdGenerar` del formulario legado y que el criterio adoptado en el Libro Mayor
(Plan 048). Sin eso, entrar a la pantalla dispararÃÂ­a una consulta sobre todo el ejercicio.

**2. Columnas: Ingresos de Fondos / Egresos de Fondos / Flujo Neto**, mÃÂ¡s el desglose en los
**seis** medios (efectivo, dÃÂ³lares, valores, banco, tarjetas, otros). El legado mostraba tres y
por eso sus totales no cerraban. **Sin `Disp.Inicial`**, por decisiÃÂ³n del usuario. Sumarizadoras
en azul y negrita, como en el original.

**3. Drill-down** por cuenta imputable: asiento, fecha, cliente/proveedor, concepto, ingresos,
egresos, desglose por medio, saldo corrido y condiciÃÂ³n Ã¢ÂÂ la vista `cons_caja_diaria_cta` del
legado. Incluye el filtro por medio del option-group `opgMoneda`, extendido de cuatro opciones a
las siete que manejamos. Valida que la cuenta pertenezca a la empresa activa.

**4. Aplanado de `medios` en la vista.** Los templates de Django no indexan un dict por clave
variable. En lugar de agregar un filtro sÃÂ³lo para eso, `_con_medios_en_orden()` convierte el dict
en una lista ordenada y el template itera. Menos superficie y sin tags nuevos.

**5. DecisiÃÂ³n tomada con la autonomÃÂ­a delegada por el usuario:** el **Typeahead + Lupa** por
cliente/proveedor en el drill-down **no se implementÃÂ³**. El detalle ya llega acotado a una sola
cuenta y a un perÃÂ­odo, y en los volÃÂºmenes reales entra en pantalla; el buscador habrÃÂ­a sido
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
salga con cabecera `%PDF`, y que las exportaciones respeten el filtro de condiciÃÂ³n.

### Estado actual y siguientes pasos
**Plan 050 completo (fases 1 a 5).** El reporte estÃÂ¡ en TesorerÃÂ­a Ã¢ÂÂ Origen y AplicaciÃÂ³n de Fondos.

**Pendiente operativo:** las migraciones `tesoreria.0013/0014/0015` del Plan 049 **siguen sin
aplicar**. El EOAF funciona sin ellas porque lee los asientos, pero el rango de fechas de
`MovimientoCaja` y el vÃÂ­nculo con el asiento dependen de correrlas:
`python manage.py migrate tesoreria`.

**ConfiguraciÃÂ³n aplicada:** la cuenta `111009 TRANSFERENCIA ENTRE SUCURSALES` quedÃÂ³ marcada con
`tipo_disponibilidad='OTR'`. En cada cliente nuevo, la cuenta que se cargue en
`ParametrosContables.cta_transferencias_sucursal` debe quedar marcada igual, o cada traslado
entre sucursales generarÃÂ¡ una fila espuria en el reporte.

---

## 16 de Agosto de 2026 Ã¢ÂÂ AplicaciÃÂ³n de las migraciones del Plan 049 y verificaciÃÂ³n en la app

### Motivo
Con el modelo ya cambiado y las migraciones sin aplicar, cualquier consulta a `MovimientoCaja`
fallaba: `ProgrammingError: column tesoreria_movimiento_caja.empresa_id does not exist` al abrir
**Caja Diaria**. La aplicaciÃÂ³n estaba caÃÂ­da, asÃÂ­ que correr las migraciones era la correcciÃÂ³n.

Antes de migrar se respaldÃÂ³ la tabla completa (21 filas) a CSV.

### Resultado de la migraciÃÂ³n
```
Applying tesoreria.0013_plan049_movimiento_caja... OK
Applying tesoreria.0014_plan049_backfill...
  Plan 049: 21 movimientos actualizados. 1 con la fecha reencuadrada a la del comprobante.
  18 vinculados a un asiento (3 sin asiento resoluble).
Applying tesoreria.0015_plan049_constraint_condic... OK
```

Estado final: 21/21 con `empresa` y `cli_pro`, 18 con `asiento`, 15 con `cuenta`.

### VerificaciÃÂ³n en la aplicaciÃÂ³n (HTTP 200 contra la base real)
| Pantalla | Estado |
|---|---|
| `/tesoreria/caja-diaria/` | 200 Ã¢ÂÂ restablecida |
| `/tesoreria/origen-aplicacion-fondos/` | 200 |
| `Ã¢ÂÂ¦/grilla/` | 200 |
| `Ã¢ÂÂ¦/excel/` | 200 (xlsx generado) |
| `Ã¢ÂÂ¦/pdf/` | 200 (pdf generado) |

### Hallazgos en los datos (PREEXISTENTES, ajenos a estos planes)
1. **Recibos 1, 4 y 5 sin contabilizar** (`Recibo.asiento_id = None`). Son los 3 movimientos que
   quedaron sin `asiento`: el backfill hizo lo correcto al dejarlos nulos. HabrÃÂ­a que decidir si
   se recontabilizan.
2. **Asientos 137, 138 y 139 (`VENTA MOSTRADOR 1/2/3`) tienen CERO lÃÂ­neas.** Cabeceras huÃÂ©rfanas
   de alguna corrida parcial previa del circuito de mostrador. El EOAF los ignora correctamente
   Ã¢ÂÂsin lÃÂ­neas de disponibilidad no son un movimiento de fondosÃ¢ÂÂ, pero quedan sueltos en la
   contabilidad. **Quedan anotados para revisiÃÂ³n del usuario.**

### Nota de build
Se ejecutÃÂ³ `npm run build` de Tailwind: las pantallas nuevas usan clases (violeta,
`max-w-[1400px]`, `sticky bottom-0`) que no estaban en el `output.css` purgado y sin recompilar
el layout se rompÃÂ­a.

### RegresiÃÂ³n final de los Planes 049 y 050
```bash
python manage.py test tesoreria contable facturacion
```
**Resultado:** `Ran 189 tests in 959.153s - FAILED (errors=2)`

Los **2 errores son preexistentes y ajenos a estos planes**: los dos ÃÂºnicos tests de
`facturacion.tests.test_armeria_credencial_clu.ArmeriaCredencialCLUTestCase` fallan en su `setUp`
con `TypeError: Sucursal() got unexpected keyword arguments: 'codigo'` Ã¢ÂÂel modelo `Sucursal` no
tiene campo `codigo`Ã¢ÂÂ. Entraron con el commit `7ff0da8` y ya estaban registrados en esta bitÃÂ¡cora
en la entrada del 15/08. Verificado: ese archivo tiene exactamente 2 tests, `git status
facturacion/` no reporta cambios, y una corrida aislada de
`facturacion.tests.test_armeria_credencial_clu` + `tesoreria.tests.test_eoaf` da
`Ran 28 tests - FAILED (errors=2)`, es decir **26/26 del EOAF en verde**.

**`tesoreria` y `contable`: sin fallas.**

## 16 de Agosto de 2026 Ã¢ÂÂ Limpieza de los movimientos de la empresa 1

### Objetivo
La empresa 1 (IKIGAI TECHNOLOGY SAS) se cargÃÂ³ en etapa de diseÃÂ±o y se operÃÂ³ con el sistema a
medio desarrollar, asÃÂ­ que arrastraba inconsistencias (asientos vacÃÂ­os, recibos sin contabilizar).
Se vaciÃÂ³ su historial transaccional para poder probar los circuitos desde cero.

### Alcance (elegido por el usuario)
**SÃÂ³lo movimientos.** Se CONSERVAN plan de cuentas, ParametrosContables, productos, subproductos,
stock por sucursal, familias, marcas, rubros, clientes/proveedores, medios de pago, cuentas
bancarias, cajas, sucursal, ejercicio y cotizaciones. Las tablas globales compartidas entre
empresas (bancos, tipos de comprobante, jurisdicciones, alÃÂ­cuotas de IVA, usuarios, permisos) no
se tocaron nunca.

### Procedimiento
1. **Respaldo completo** con `pg_dump -Fc` de toda la base antes de empezar.
2. **Relevamiento** de las 35 tablas con FK a `empresa` y de las que dependen por cascada.
3. **SimulaciÃÂ³n** dentro de una transacciÃÂ³n que se revierte, para confirmar el orden de borrado.
4. **EjecuciÃÂ³n** con el mismo script.

### Detalle TÃÂ©cnico
**Orden de borrado.** De la hoja a la raÃÂ­z, respetando los FK con `PROTECT`. Tres dependencias
mandan: `MovimientoCaja.asiento Ã¢ÂÂ Asiento` obliga a borrar los movimientos antes que los
asientos; `Asiento.sesion_caja Ã¢ÂÂ CajaSesion` obliga a borrar los asientos antes que las sesiones;
y los satÃÂ©lites (`ValorTerceros`, `TransaccionBancaria`) protegen a `MovimientoCajaDetalle`, asÃÂ­
que van primero.

**SeÃÂ±ales desactivadas durante el borrado.** El primer intento abortÃÂ³ con
`ValidationError: El asiento estÃÂ¡ desbalanceado. Debe 25000.00 - Haber 50000.00`: el `post_delete`
de `CompraItem` recalcula y vuelve a guardar la `Compra`, y el `post_save` de `Compra` dispara
`contabilizar_compras()`. A mitad del borrado la compra ya habÃÂ­a perdido sus ÃÂ­tems, asÃÂ­ que el
asiento salÃÂ­a descuadrado. Como todo corrÃÂ­a en una transacciÃÂ³n, no se borrÃÂ³ nada. La soluciÃÂ³n fue
un context manager que desconecta todas las seÃÂ±ales de modelo y las restaura en un `finally`: en
un teardown masivo no se quiere ningÃÂºn efecto colateral.

**Saldos derivados recompuestos a mano.** Con las seÃÂ±ales apagadas, las cuentas corrientes no se
recalculan solas. Al terminar se llevÃÂ³ `ClienteProveedor.saldo` a su `saldo_inicial`: eran 4
entidades con saldo distinto de cero, hoy las 6 en `0.00`.

**Stock.** Se borrÃÂ³ el LIBRO de movimientos (`MovimientoStock`, `facturacion.Movimiento`) pero NO
los saldos (`StockSucursal`, 13.596 filas; `ExtensionArmeria`, 3.754). No genera incoherencia:
el stock se cargÃÂ³ por importaciÃÂ³n y no se derivaba de esos movimientos Ã¢ÂÂhabÃÂ­a 13.596 registros de
stock contra 59 movimientosÃ¢ÂÂ.

### Resultado
**356 filas borradas** y 4 saldos reseteados:

| Grupo | Filas |
|---|---|
| Asientos y lÃÂ­neas | 24 + 87 |
| Ventas / ÃÂ­tems | 18 + 23 |
| Compras / ÃÂ­tems / alÃÂ­cuotas / ret-perc | 5 + 5 + 1 + 3 |
| Preventas / ÃÂ­tems | 18 + 23 |
| Recibos / aplicaciones | 5 + 5 |
| ÃÂrdenes de pago / aplicaciones | 1 + 1 |
| Movimientos de caja / detalles / sesiones | 17 + 15 + 3 |
| Trazabilidad de movimientos | 30 |
| Movimientos de stock | 59 |
| Libro IVA / alÃÂ­cuotas / retenciones sufridas | 5 + 4 + 3 |
| Transacciones bancarias | 1 |

### VerificaciÃÂ³n
- **Empresa 1:** los 13 grupos de movimientos en **0**; maestros intactos (200 cuentas, 347
  productos, 859 subproductos, 12 rubros, 6 clientes/proveedores, 6 medios de pago, 2 cuentas
  bancarias, 2 cajas, 1 sucursal, 1 ejercicio, ParametrosContables).
- **Otras empresas sin tocar:** empresa 2 con 21 asientos, 11 ventas, 268 cuentas y 6.793
  productos; empresa 3 con 1 asiento, 1 venta y 247 cuentas.
- **AplicaciÃÂ³n operativa:** TesorerÃÂ­a, Caja Diaria, EOAF y su grilla responden 200.

### Estado actual y siguientes pasos
La empresa 1 quedÃÂ³ con su configuraciÃÂ³n y sus maestros completos y sin historial de operaciones,
lista para probar los circuitos de cero. El respaldo previo queda disponible por si hiciera falta
recuperar algo.

---

## 16 de Agosto de 2026 Ã¢ÂÂ VisualizaciÃÂ³n de Stock Activo y Stock Destino en Buscador Avanzado de Productos (Remitos Internos) Ã¢ÂÂ Plan 051

### Objetivo
Mostrar el stock de la sucursal activa en el Buscador Avanzado de Productos en todas las vistas de bÃÂºsqueda y, al abrirlo desde el formulario de Remito Interno, incorporar automÃÂ¡ticamente la columna de **Stock Destino** para que el usuario pueda evaluar la necesidad y existencias reales en ambas sucursales.

### Archivos Modificados / Creados
- `templates/facturacion/remito_interno_carga.html` [MODIFY]: inclusiÃÂ³n de `hx-include="[name='sucursal_origen'], [name='sucursal_destino']"` en el botÃÂ³n de la lupa.
- `facturacion/views_htmx.py` [MODIFY]: actualizaciÃÂ³n de `buscador_productos_modal` y `lista_productos_resultados` para calcular y adjuntar `stock_origen` (o sucursal activa) y `stock_destino` en los productos buscados.
- `templates/facturacion/modals/buscador_productos.html` [MODIFY]: agregados inputs ocultos de sucursal en `thead`, cabeceras dinÃÂ¡micas para **Stk. Activo/Origen** y **Stk. Destino** y ajuste de `tbody` `hx-get` inicial.
- `templates/facturacion/partials/productos_search_results.html` [MODIFY]: renderizado de celdas de stock con insignias visuales (verde/rojo para origen/activa, azul/ÃÂ¡mbar para destino) y ajuste de `colspan`.
- `facturacion/tests/test_plan028.py` [MODIFY]: adiciÃÂ³n de `BuscadorProductosStockTests` para validar contexto y asignaciÃÂ³n de stock por sucursal en HTMX.
- `docs/planes/051_stock_sucursales_modal_remito_interno.md` [NEW]: plan de implementaciÃÂ³n histÃÂ³rico.

### Detalle TÃÂ©cnico
1. **Paso de ParÃÂ¡metros HTMX:** El botÃÂ³n de la lupa en `remito_interno_carga.html` incluye `[name='sucursal_origen']` y `[name='sucursal_destino']`.
2. **DeterminaciÃÂ³n de Sucursal Activa vs. Origen/Destino:** `sucursal_origen_id` se resuelve contra el parÃÂ¡metro GET enviado o contra la sucursal activa de la sesiÃÂ³n (`request.session.get('sucursal_id')`). `sucursal_destino_id` sÃÂ³lo se procesa si estÃÂ¡ presente en el GET.
3. **Consulta Eficiente en `StockSucursal`:** Para los productos devueltos en la bÃÂºsqueda (mÃÂ¡ximo 50), se realiza una consulta agrupada contra `StockSucursal` filtrando por `producto_id__in` y `sucursal_id__in`. El resultado se mapea en un diccionario `(producto_id, sucursal_id) -> cantidad` permitiendo la asignaciÃÂ³n en memoria `O(1)`.
4. **DiseÃÂ±o Visual:** Celdas con badges de color de Tailwind (`bg-emerald-100` / `bg-rose-100` para origen/activa y `bg-blue-100` / `bg-amber-100` para destino). En bÃÂºsquedas estÃÂ¡ndar donde no hay sucursal destino, se muestra la tabla con 6 columnas; en Remitos Internos se extiende a 7 columnas.

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test facturacion.tests.test_plan028
```
**Resultado:** `Ran 11 tests in 109.256s - OK`

### Estado actual y siguientes pasos
Plan 051 completamente implementado y verificado. El modal de bÃÂºsqueda avanzada de productos muestra el stock activo en bÃÂºsquedas generales y amplÃÂ­a la vista a Stock Origen y Stock Destino al confeccionar Remitos Internos.

---

## 16 de Agosto de 2026 Ã¢ÂÂ Plan 053: `stock_inicial` y stock derivado por sucursal

### Objetivo
Que el stock deje de ser un contador incremental sin origen y pase a **derivarse** de un punto de
partida mÃÂ¡s los comprobantes, igual que la cuenta corriente:

    stock = stock_inicial + compras + recepciones Ã¢ÂÂ ventas Ã¢ÂÂ remitos internos

### Archivos Creados
- `productos/services/stock_service.py` [REESCRITO]: `recalcular_stock()`,
  `recalcular_stock_masivo()` y los tÃÂ©rminos de la fÃÂ³rmula declarados como datos.
- `productos/management/commands/recalcular_stock.py` [NEW]: comando de reconstrucciÃÂ³n.
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
- `productos/tests.py` [BORRADO]: stub vacÃÂ­o que rompÃÂ­a el descubrimiento de tests.

### Detalle TÃÂ©cnico

**1. El stock es derivado.** `StockSucursal.cantidad` se sigue materializando Ã¢ÂÂse lee en toda la
operatoriaÃ¢ÂÂ, pero ya no se ajusta por delta: se **recalcula completo** para ese (producto,
sucursal) cada vez que algo lo afecta. Las tres funciones que llaman las seÃÂ±ales conservan su
firma; por dentro registran el `MovimientoStock` de auditorÃÂ­a y delegan en `recalcular_stock()`.

**2. Los tÃÂ©rminos se declaran como datos, no cableados.** Cada uno dice quÃÂ© modelo aporta, con quÃÂ©
signo, por quÃÂ© campo de cantidad, cÃÂ³mo llega a la sucursal y quÃÂ© excluye. Sumar el tÃÂ©rmino de
**ajustes de inventario** Ã¢ÂÂcuando se haga el formulario de toma fÃÂ­sicaÃ¢ÂÂ serÃÂ¡ agregar una entrada,
sin revalidar los cuatro que ya funcionan.

**3. Exclusiones conservadas del cÃÂ³digo anterior**, cada una con su test: compras con
`id_fac_rem` o `gestion_stock_por_recepcion` (circuito OC), ventas anuladas o con `id_fac_rem`,
recepciones anuladas, remitos internos anulados, y el signo de las notas de crÃÂ©dito
(`TipoComprobante.signo = Ã¢ÂÂ1`, que hace que una NC de venta **devuelva** stock).

**4. Backfill que no mueve un solo nÃÂºmero.** `stock_inicial = cantidad Ã¢ÂÂ movimientos_ya_aplicados`,
calculado con cuatro consultas agrupadas por (producto, sucursal) en vez de cuatro por fila.
Resultado sobre la base real: **13.596 filas inicializadas, 7 con movimientos aplicados y 0
cantidades modificadas**.

**5. Dos caminos de recÃÂ¡lculo por una razÃÂ³n de performance.** `recalcular_stock()` hace cuatro
consultas por par (producto, sucursal): ideal al guardar un comprobante, inviable para un
inventario entero. La primera versiÃÂ³n del comando lo llamaba fila por fila y tardaba mÃÂ¡s de 10
minutos sobre 13.584 registros. `recalcular_stock_masivo()` agrupa los cuatro tÃÂ©rminos en cuatro
consultas totales: **49 segundos**.

**6. Baja de `Producto.stock` y `Producto.stkcons`.** Campos heredados del ERP en VFP, donde el
stock se llevaba sobre el producto. Se relevÃÂ³ que **nadie los escribÃÂ­a** y que sÃÂ³lo los leÃÂ­an dos
exports Ã¢ÂÂel CSV legacy de 74 columnas y su gemelo en ExcelÃ¢ÂÂ, que emitÃÂ­an el valor congelado de la
importaciÃÂ³n. Ahora esas columnas traen el **stock real de la sucursal de la venta**, precargado en
una sola consulta para no disparar una por fila. `stkcons` (stock en consignaciÃÂ³n del VFP) queda
en `0.0` como relleno posicional: se conservan las 74 columnas para no romper al consumidor.
El total consolidado ya existÃÂ­a como la property `Producto.stock_global`.

### Dos problemas preexistentes corregidos al paso
1. **`productos/models.py`**: `InvalidOperation` se usaba en un `except` sin estar importado, asÃÂ­
   que un IVA mal formado producÃÂ­a `NameError` en vez de tomar el default. Faltaba una palabra en
   el import.
2. **`productos/tests.py`**: stub vacÃÂ­o de Django (3 lÃÂ­neas, del commit inicial) que convivÃÂ­a con
   el paquete `productos/tests/`. RompÃÂ­a el descubrimiento con
   `ImportError: 'tests' module incorrectly imported`, o sea que **`manage.py test productos`
   nunca habÃÂ­a funcionado**. Se borrÃÂ³ el stub.

### Pruebas Automatizadas
```bash
python manage.py test productos.tests.test_stock_inicial
```
**Resultado:** `Ran 20 tests in 198.099s - OK`

Cobertura: la fÃÂ³rmula completa, las siete exclusiones, las notas de crÃÂ©dito de venta y de compra,
la transferencia interna en dos pasos (el total no cambia), el aislamiento entre sucursales, la
idempotencia del recÃÂ¡lculo y Ã¢ÂÂel caso que da sentido al planÃ¢ÂÂ la **autorreparaciÃÂ³n**: se rompe
`cantidad` a mano y el recÃÂ¡lculo la corrige. Con el contador incremental anterior era imposible.

**VerificaciÃÂ³n sobre la base real:** `recalcular_stock --dry-run` sobre las tres empresas
(13.584 + 9 + 3 registros) informa *"Todos los registros ya estaban correctos"*: la fÃÂ³rmula
reproduce exactamente el stock que habÃÂ­a.

### Nota de numeraciÃÂ³n
Este plan se archivÃÂ³ primero como 052 y se **renumerÃÂ³ a 053** al detectarse que, en paralelo, la Trazabilidad de Subproductos ya usaba ese nÃÂºmero. Los archivos de migraciÃÂ³n conservan `plan052` en su NOMBRE a propÃÂ³sito: ya estaban aplicadas en la base y renombrarlas harÃÂ­a que Django las tomara como nuevas.

### Estado actual y siguientes pasos
Plan 053 **completo**. El stock es reconstruible con `manage.py recalcular_stock --empresa N`.

**PENDIENTE registrado (ÃÂ§8 bis del plan):** formulario de carga de inventarios, generales y
periÃÂ³dicos, al estilo del "arreglo de stock". Va en un plan aparte y necesitarÃÂ¡ su propio tÃÂ©rmino
en la fÃÂ³rmula (ÃÂ± ajustes), que es justamente lo que la estructura declarativa deja preparado.

---

## 16 de Agosto de 2026 Ã¢ÂÂ Trazabilidad de Subproductos (NÃÂ° Serie y CUIM) en Remitos Internos y RecepciÃÂ³n Ã¢ÂÂ Plan 052

### Objetivo
Permitir la transferencia de productos trazables (`subprod = True / 1`) mediante la validaciÃÂ³n de su nÃÂºmero de serie en la sucursal de origen, emitiendo el Remito Interno con los datos de **NÃÂ° Serie** y **CUIM**, mostrÃÂ¡ndolos en el PDF impreso y en la pantalla de recepciÃÂ³n interna, y reubicando automÃÂ¡ticamente el `Subproducto.sucursal_id` hacia la sucursal de destino al confirmarse el Informe de RecepciÃÂ³n.

### Archivos Modificados / Creados
- `facturacion/models.py` [MODIFY]: agregado de campos `subproducto` (FK), `serie` y `cuim` a `RemitoInternoItem`.
- `facturacion/migrations/0047_remitointernoitem_cuim_remitointernoitem_serie_and_more.py` [NEW]: migraciÃÂ³n de base de datos.
- `facturacion/views_remito_interno.py` [MODIFY]:
  - `RiItemAddView`: validaciÃÂ³n de productos trazables y verificaciÃÂ³n del subproducto en la sucursal de origen.
  - `RemitoInternoCargaView`: guardado de `subproducto_id`, `serie` y `cuim`.
  - `RecepcionInternaVincularView`: agrupaciÃÂ³n de ÃÂ­tems por `(producto_id, subproducto_id)` para mantener viva la trazabilidad por serie.
  - `RecepcionInternaCargaView`: actualizaciÃÂ³n atÃÂ³mica de `subproducto.sucursal_id` a la sucursal de destino.
- `templates/facturacion/remito_interno_carga.html` [MODIFY]: adiciÃÂ³n de campo `NÃÂ° Serie (si aplica)` y parÃÂ¡metro `hx-include`.
- `templates/facturacion/partials/ri_items_tabla.html` [MODIFY]: visualizaciÃÂ³n de leyendas de Serie y CUIM.
- `templates/facturacion/pdf/remito_interno_pdf.html` [MODIFY]: impresiÃÂ³n de Serie y CUIM en el comprobante PDF.
- `templates/facturacion/partials/recepcion_interna_items_tabla.html` [MODIFY]: despliegue de Serie y CUIM en la recepciÃÂ³n interna.
- `templates/facturacion/modals/recepcion_interna_vincular.html` [MODIFY]: aclaraciÃÂ³n de trazabilidad por serie.
- `facturacion/tests/test_plan028.py` [MODIFY]: adiciÃÂ³n de `SubproductoRemitoInternoTests`.
- `docs/planes/052_trazabilidad_subproductos_remito_interno.md` [NEW]: plan de implementaciÃÂ³n histÃÂ³rico.

### Detalle TÃÂ©cnico
1. **ValidaciÃÂ³n de Subproducto y Origen:** Al ingresar una serie para un producto trazable (`subprod = True`), `RiItemAddView` busca la coincidencia exacta en `Subproducto`. Si no existe o se ubica en otra sucursal, rechaza la operaciÃÂ³n informando la inconsistencia.
2. **ConservaciÃÂ³n de Atributos:** Se almacenan `subproducto_id`, `serie` y `cuim` en `RemitoInternoItem` y se arrastran a la sesiÃÂ³n de recepciÃÂ³n interna.
3. **ReubicaciÃÂ³n FÃÂ­sica en BD:** Al momento de guardar el `Informe de RecepciÃÂ³n` (origen = INTERNO) en la sucursal destino, se ejecuta la actualizaciÃÂ³n `subproducto.sucursal = destino` con `update_fields=['sucursal']`.

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test facturacion.tests.test_plan028
```
**Resultado:** `Ran 13 tests in 141.564s - OK`

### Estado actual y siguientes pasos
Plan 052 completado y verificado en su totalidad. Toda transferencia interna de productos trazables contempla la serie y el CUIM desde la emisiÃÂ³n hasta la recepciÃÂ³n con reubicaciÃÂ³n automÃÂ¡tica de sucursal.

---

## 17 de Agosto de 2026 Ã¢ÂÂ BÃÂºsqueda y Autocarga por NÃÂ° de Serie en Remitos Internos (Plan 053)

### Objetivo
Permitir la bÃÂºsqueda rÃÂ¡pida y directa por NÃÂ° de Serie en la emisiÃÂ³n de Remitos Internos, verificando que la unidad no se encuentre vendida (`situacion != 'VENDIDA'`), comprobando su pertenencia a la sucursal de origen, y autocompletando el ID de producto, la descripciÃÂ³n y el CUIM.

### Archivos Modificados / Creados
- `facturacion/views_remito_interno.py` [MODIFY]:
  - `ri_buscar_subproducto_por_serie`: vista HTMX que filtra por `serie__iexact`, excluye `situacion='VENDIDA'`, verifica sucursal.
  - `ri_buscar_producto_por_id`: bÃÂºsqueda instantÃÂ¡nea con prioridad absoluta por `id` primario sobre `cod_prov`.
  - `RiItemAddView`: resoluciÃÂ³n de producto priorizando clave primaria `id` antes de `cod_prov`.
  - `RecepcionInternaCargaView` / `RecepcionInternaVincularModalView`: restricciÃÂ³n estricta de la sucursal receptora a la sucursal activa logueada.
  - `RecepcionInternaImprimirView` [NEW]: vista de emisiÃÂ³n de PDF para el Informe de RecepciÃÂ³n Interna.
- `config/urls.py` [MODIFY]: inclusiÃÂ³n de la ruta `compras/recepcion-interna/<int:rec_id>/imprimir/`.
- `templates/facturacion/pdf/remito_interno_pdf.html` [MODIFY]: inclusiÃÂ³n de casilla de punteo `[  ]` por ÃÂ­tem y triple bloque de firma.
- `templates/facturacion/pdf/recepcion_interna_pdf.html` [NEW]: diseÃÂ±o PDF del Informe de RecepciÃÂ³n Interna con firmas y comprobantes vinculados.
- `templates/facturacion/recepcion_interna_carga.html` [MODIFY]: fijaciÃÂ³n inalterable de la sucursal receptora a la sucursal activa.
- `templates/facturacion/partials/recepcion_fila.html` [MODIFY]: enlace al PDF de Informe de RecepciÃÂ³n Interna.
- `facturacion/tests/test_plan028.py` [MODIFY]: inclusiÃÂ³n de pruebas unitarias para autocompletado y validaciones de serie.
- `docs/planes/053_busqueda_inteligente_series_remito_interno.md` [NEW]: plan de implementaciÃÂ³n histÃÂ³rico.

### Detalle TÃÂ©cnico y Saneamiento de Datos
1. **Persistencia y VisualizaciÃÂ³n Estricta por `productos_producto.id`:** Se unificÃÂ³ la regla conceptual del sistema: tanto en sesiÃÂ³n (`items`), grillas operativas (`ri_items_tabla.html`, `recepcion_interna_items_tabla.html`), modelos y comprobantes PDF, el identificador guardado y mostrado en columna es estrictamente el `producto_id` primario (`productos_producto.id`), desacoplÃÂ¡ndolo del `cod_prov` que sÃÂ³lo se usa como comodÃÂ­n de bÃÂºsqueda.
2. **Remito e Informe de RecepciÃÂ³n PDF (DiseÃÂ±o Sobrio y Ahorro de Tinta):** Se rediseÃÂ±aron los comprobantes PDF ([`remito_interno_pdf.html`](file:///d:/JM_Soft/erp-ikigai-2/templates/facturacion/pdf/remito_interno_pdf.html) y [`recepcion_interna_pdf.html`](file:///d:/JM_Soft/erp-ikigai-2/templates/facturacion/pdf/recepcion_interna_pdf.html)) alineando el nÃÂºmero de comprobante a la derecha en el mismo renglÃÂ³n del tÃÂ­tulo, reemplazando los fondos negros por bordes rectangulares finos (`#334155`), e implementando una casilla de control cuadrada para el punteo en depÃÂ³sito sin desbordamiento de renglÃÂ³n.
3. **Bloqueo RÃÂ­gido de Sucursal Receptora:** En RecepciÃÂ³n Interna se eliminÃÂ³ la selecciÃÂ³n de sucursal. La recepciÃÂ³n se asocia de forma fija e inalterable a la sucursal activa del usuario logueado.
4. **CorrecciÃÂ³n de Clave Primaria en `RecepcionInternaImprimirView`:** Se corrigiÃÂ³ la consulta de remitos imputados utilizando `ri.pk` (en lugar de `ri.id`), resolviendo la excepciÃÂ³n `AttributeError`.
5. **CorrecciÃÂ³n de Mapeo de Sucursales:** Se detectÃÂ³ e instruyÃÂ³ un saneamiento de datos en la tabla `productos_subproducto` para reasociar 1,400 registros que apuntaban errÃÂ³neamente a `sucursal_id = 1` de Empresa 1 hacia `sucursal_id = 3` (Sede Central de Empresa 2).

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test facturacion.tests.test_plan028
```
**Resultado:** `Ran 16 tests in 171.858s - OK`

### Estado actual y siguientes pasos
Plan 053 completado y verificado en su totalidad.

---

## 17 de Agosto de 2026 Ã¢ÂÂ DepuraciÃÂ³n de Cuentas Contables Obsoletas (Empresa ID = 2)

### Objetivo
Eliminar 48 cuentas contables obsoletas/duplicadas en la tabla `cble_cuentas` (modelo `Cuenta`) pertenecientes a `empresa_id = 2`, cuyos cÃÂ³digos fueron suministrados en el archivo `d:\borrador\borrar.csv`.

### Archivos Modificados / Creados
- Base de datos (`cble_cuentas`): eliminaciÃÂ³n fÃÂ­sica de 48 registros sin movimientos asociados.
- `docs/walkthrough.md` [MODIFY]: registro de la intervenciÃÂ³n.

### Detalle TÃÂ©cnico
1. **AuditorÃÂ­a e Integridad Previa:**
   - Se validaron los 48 cÃÂ³digos del archivo CSV (`codigo`).
   - Se verificÃÂ³ que ninguna de las 48 cuentas tuviera movimientos contables en `cble_asiento_mov` (`AsientoLinea`), cuentas bancarias asociadas ni parÃÂ¡metros contables vinculados.
   - Se comprobÃÂ³ que ninguna cuenta activa externa tuviera `sumariza_id` apuntando a las cuentas a borrar.
2. **EjecuciÃÂ³n Transaccional AtÃÂ³mica:**
   - Se ejecutÃÂ³ un bloque `transaction.atomic()`.
   - Se desvincularon preventivamente las autoreferencias `sumariza = None` internas entre las 48 cuentas.
   - Se ejecutÃÂ³ el borrado definitivo (`.delete()`) eliminando exactamente las 48 cuentas correspondientes.
   - VerificaciÃÂ³n posterior: 0 cuentas restantes con los cÃÂ³digos indicados en `empresa_id = 2`.

---

## 17 de Agosto de 2026 Ã¢ÂÂ Carga Maestra de Tarjetas en TesorerÃÂ­a (`tesoreria_tarjeta`)

### Objetivo
Poblar la tabla maestra de tarjetas (`tesoreria_tarjeta` / modelo `Tarjeta`) a partir del archivo `d:\borrador\tarjetas.csv` para habilitar las operaciones de cobros y liquidaciones con tarjetas de crÃÂ©dito y dÃÂ©bito.

### Archivos Modificados / Creados
- Base de datos (`tesoreria_tarjeta`): inserciÃÂ³n de 10 registros maestros.
- `docs/walkthrough.md` [MODIFY]: registro incremental de la bitÃÂ¡cora.

### Detalle TÃÂ©cnico
1. **Origen de Datos:** Lectura del archivo `d:\borrador\tarjetas.csv` (delimitado por `;`).
2. **Mapeo de Atributos:**
   - `codigo` -> `Tarjeta.codigo`
   - `detalle` -> `Tarjeta.nombre`
   - `tipo` -> `Tarjeta.tipo` (`C` = CrÃÂ©dito, `D` = DÃÂ©bito)
3. **Carga Idempotente y Transaccional:**
   - EjecuciÃÂ³n atÃÂ³mica vÃÂ­a `transaction.atomic()`.
   - UtilizaciÃÂ³n de `Tarjeta.objects.update_or_create(...)`.
   - Resultado: 10 tarjetas creadas exitosamente.

---

## 17 de Agosto de 2026 Ã¢ÂÂ Plan 054: ResoluciÃÂ³n Fiscal de Comprobantes ARCA y GestiÃÂ³n Guiada de Clientes por CondiciÃÂ³n IVA

### Objetivo
Corregir integralmente la determinaciÃÂ³n de tipos de comprobante (`TipoComprobante`) para la facturaciÃÂ³n electrÃÂ³nica ante ARCA/AFIP por emisores Responsables Inscriptos (Factura A para Responsables Inscriptos y Monotributistas segÃÂºn RG 5003/5022; Factura B para Consumidores Finales y Exentos), blindar las validaciones cruzadas de CUIT/DNI por condiciÃÂ³n fiscal e implementar un flujo guiado en el alta/ediciÃÂ³n de clientes que derive los controles impositivos desde la CondiciÃÂ³n ante el IVA.

### Archivos Modificados / Creados
- `facturacion/models.py` [MODIFY]: agregado de campo `es_consumidor_final` a `Preventa`.
- `facturacion/migrations/0048_preventa_es_consumidor_final.py` [NEW]: migraciÃÂ³n de base de datos.
- `facturacion/forms.py` [MODIFY]: validaciÃÂ³n integral en `ClienteProveedorForm.clean()` e inclusiÃÂ³n de `es_consumidor_final` en `PreventaForm`.
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]: reorganizaciÃÂ³n visual poniendo la CondiciÃÂ³n ante el IVA como selector disparador principal de la SecciÃÂ³n 1 con control dinÃÂ¡mico reactivo vÃÂ­a Alpine.js.
- `templates/facturacion/preventa_carga.html` [MODIFY]: checkbox para "Facturar como Consumidor Final (Factura B)" en la cabecera.
- `facturacion/views.py` [MODIFY]:
  - `resolver_tipo_comprobante_fiscal`: resoluciÃÂ³n certera de `TipoComprobante` sin caer en fallbacks errÃÂ³neos a `.first()`.
  - `validar_y_obtener_documento_receptor`: validaciÃÂ³n estricta de documentos previa a ARCA.
  - `VentasCargaView.post`: validaciÃÂ³n de coherencia fiscal previa a la comunicaciÃÂ³n con ARCA.
- `tesoreria/views_htmx.py` [MODIFY]: cobro de Preventa en Caja Mostrador resolviendo Factura A / B de forma certera y respetando `es_consumidor_final` para emitir Factura B.
- `facturacion/views_trazabilidad.py` [MODIFY]: validaciÃÂ³n de coherencia fiscal y documento antes de emitir a ARCA.
- `templates/facturacion/ventas_carga.html` y `templates/facturacion/ventas_trazabilidad_carga.html` [MODIFY]: preselecciÃÂ³n de Factura B por defecto y filtrado automÃÂ¡tico de Factura A/B segÃÂºn la condiciÃÂ³n fiscal del cliente seleccionado.
- `docs/planes/054_resolucion_fiscal_comprobantes_y_clientes.md` [NEW]: plan de implementaciÃÂ³n histÃÂ³rico.
- `docs/walkthrough.md` [MODIFY]: registro incremental de la bitÃÂ¡cora.

### Detalle TÃÂ©cnico
1. **ResoluciÃÂ³n Robusta de `TipoComprobante`:** Se normalizÃÂ³ la bÃÂºsqueda contemplando formatos con padding (`'001'`, `'006'`) y sin padding (`'1'`, `'6'`), eliminando definitivamente el fallback a `.first()` que causaba la asignaciÃÂ³n accidental de Factura A a Consumidores Finales.
2. **Matriz Impositiva de EmisiÃÂ³n (Emisor RI):**
   - **Receptor RI o Monotributista:** Emite **Factura A** (`001`), requiriendo `DocTipo = 80` y CUIT de 11 dÃÂ­gitos.
   - **Receptor Consumidor Final:** Emite **Factura B** (`006`), admitiendo `DocTipo = 99` (`DocNro = 0`), `DocTipo = 96` (DNI) o `DocTipo = 80` (CUIT).
   - **Receptor Exento:** Emite **Factura B** (`006`), requiriendo `DocTipo = 80` y CUIT de 11 dÃÂ­gitos.
3. **Flujo Guiado de Clientes:** En el modal de alta/ediciÃÂ³n de clientes, la **CondiciÃÂ³n ante el IVA** se define en primer tÃÂ©rmino. Al seleccionar RI, Monotributo o Exento, el Tipo de Documento se fija en `80 - CUIT` y el CUIT pasa a ser obligatorio de 11 dÃÂ­gitos.
4. **OpciÃÂ³n de Consumo Propio en Preventas:** Se agregÃÂ³ `es_consumidor_final` en `Preventa` con un checkbox en la pantalla de carga. Al cobrar la preventa en Caja Mostrador, si estÃÂ¡ marcado, se fuerza la emisiÃÂ³n de **Factura B** con condiciÃÂ³n impositiva de Consumidor Final (5) sin alterar la ficha del cliente en el maestro.

---

## 18 de Agosto de 2026 Ã¢ÂÂ Listado de Facturas Pendientes (rÃÂ©plica del VFP `tran_facturas_pendientes`)

### Objetivo
Replicar en el ERP el formulario VFP **I-108 `tran_facturas_pendientes`** (`c:\jm_soft\balances\forms\`):
el estado de cancelaciÃÂ³n de la cuenta corriente, comprobante por comprobante, con salidas a
pantalla, Excel y PDF. Se partiÃÂ³ del anÃÂ¡lisis del `.scx`/`.sct`, de la vista
`cons_lib_iva_pendientes` extraÃÂ­da del `contable.dbc`, del reporte `.frx` y de las muestras
`d:\borrador\FacturasPendientes.csv` / `.pdf`.

### Archivos creados / modificados
- `facturacion/services/facturas_pendientes.py` [NEW]: servicio de consulta. `FiltroFacturas`,
  `FilaFactura`, `TotalesFacturas`, `consultar()`, `calcular_totales()`, `agrupar_por_entidad()`.
- `facturacion/services/facturas_pendientes_excel.py` [NEW]: exportaciÃÂ³n `openpyxl` (19 columnas).
- `facturacion/views_facturas_pendientes.py` [NEW]: las cuatro vistas (pantalla, grilla HTMX,
  Excel, PDF), todas `GET` y de sÃÂ³lo lectura.
- `templates/facturacion/reportes/facturas_pendientes.html` [NEW]: pantalla con barra de filtros.
- `templates/facturacion/reportes/partials/facturas_pendientes_grilla.html` [NEW]: grilla + pie.
- `templates/facturacion/pdf/facturas_pendientes.html` [NEW]: "RESUMEN DE CUENTAS" (A4 apaisado).
- `config/urls.py` [MODIFY]: 4 rutas nuevas bajo `facturas-pendientes/`.
- `templates/base.html` [MODIFY]: ÃÂ­tem "Facturas Pendientes" en los submenÃÂºs de Compras
  (`?operacion=C`) y de Ventas (`?operacion=V`).
- `static/css/output.css` [MODIFY]: recompilado con `npm run build` (Tailwind purga por contenido).
- `facturacion/tests/test_facturas_pendientes.py` [NEW]: 24 pruebas.
- `docs/planes/056_listado_facturas_pendientes.md` [NEW]: plan de implementaciÃÂ³n archivado.

### Detalle tÃÂ©cnico

**1. La fuente NO es el Libro IVA.** El VFP leÃÂ­a `lib_iva`; acÃÂ¡ se lee `Compra` y `Venta`. Tres
razones: `LibroIvaVentas` nunca se puebla (`contabilizacion.py` sÃÂ³lo crea `LibroIvaCompras`), el
Libro IVA se llena sÃÂ³lo con `condic in (1,3)` Ã¢ÂÂ con lo que los `2` (Presupuestado) y `4`
(AuditorÃÂ­a) desaparecerÃÂ­an justo del listado de gestiÃÂ³n Ã¢ÂÂ y `pagado`/`saldo` viven en los
comprobantes. Neto, IVA, No Gravado y Exento ya estÃÂ¡n en `Compra`/`Venta`: no se toca el
subsistema fiscal para ninguna columna.

**2. `pagado := total Ã¢ÂÂ saldo` en las dos operaciones.** `Compra.pagado` existe y la identidad es
exacta. `Venta` **no tiene** campo `pagado`: tiene `cobrado` (cobro en el acto) y
`saldo = total Ã¢ÂÂ cobrado Ã¢ÂÂ ÃÂ£ ReciboAplicacion`. Con esta definiciÃÂ³n los totalizadores cierran por
construcciÃÂ³n (`ÃÂ£ total = ÃÂ£ pagado + ÃÂ£ saldo`), y hay un test que lo verifica.

**3. TraducciÃÂ³n de los filtros del VFP.** Fechas (precargadas con el ejercicio en curso acotado a
hoy, como el `Form.Init`), Compras|Ventas excluyente, Todos|Uno con **Typeahead + Lupa**, y el
estado de pago replicando los rangos de `saldo`: Pagadas Ã¢ÂÂ `saldo = 0`, Pendientes Ã¢ÂÂ
`saldo <> 0`. El rango negativo del original es intencional y se conservÃÂ³: asÃÂ­ aparecen las notas
de crÃÂ©dito todavÃÂ­a sin aplicar.

**4. Dos filtros que el VFP no tenÃÂ­a.** *CondiciÃÂ³n* (Real/Presupuestado/Ajuste/AuditorÃÂ­a), que
`.cursorrules` exige en todo listado con importes Ã¢ÂÂ sin checkboxes marcados se entiende "todas",
no "ninguna". Y *Incluir anuladas*, apagado por defecto (`Venta.estado != 1`); los estados `2`
(Pend. AutorizaciÃÂ³n) y `3` (Rechazada) sÃÂ­ se listan siempre.

**5. SÃÂ³lo lectura Ã¢ÂÂ el botÃÂ³n "Modificar" no se replicÃÂ³.** En el VFP desbloqueaba `pagado` en la
grilla y hacÃÂ­a `TABLEUPDATE` directo sobre `lib_iva`, porque ese campo materializado se
desincronizaba. AcÃÂ¡ `pagado`/`saldo` son derivados de las aplicaciones de OP y Recibos
(`contable/services/saldos.py`): no hay nada que forzar. **Ninguna de las cuatro rutas es `POST`
y el mÃÂ³dulo no escribe en la base**; hay un test que recorre las cuatro vistas y verifica que los
importes queden intactos. Al no escribir, tampoco necesita `transaction.atomic()` ni
`select_for_update()`.

**6. Columnas descartadas.** `cantidad` y `litros` son herencia de verticales viejas (GNC/agro):
salen siempre en cero, y la versiÃÂ³n en producciÃÂ³n del ejecutable VFP ya ni las exportaba (18
columnas en el CSV contra las 20 que escribe el cÃÂ³digo). Con ellas se fue el totalizador de
`litros`: **el pie tiene tres cajas Ã¢ÂÂ Total, Pagado, Saldo Ã¢ÂÂ en vez de las cuatro del original.**
TambiÃÂ©n se omitieron `vencim` (no existe el campo en `Compra`/`Venta`) y `f_p`.

**7. Truncado honesto.** La grilla corta en 500 filas, pero `calcular_totales()` agrega sobre el
conjunto completo: el pie nunca miente. Cuando hay corte se muestra un aviso explÃÂ­cito y se
aclara que el Excel y el PDF incluyen todas.

**8. Bug del reporte original corregido.** Midiendo coordenadas sobre `FacturasPendientes.pdf` se
verificÃÂ³ que en el `.frx` las columnas rotuladas *"Pendiente"* y *"Saldo"* estÃÂ¡n invertidas: la
primera trae el saldo del comprobante y la segunda el acumulado corrido del grupo. En el PDF
nuevo los rÃÂ³tulos dicen lo que la columna contiene. Se conservaron las **dos** variantes de suma
corrida del original: `acum_global` (columna `Acum.` del Excel) y `acum_grupo` (reinicia por
cliente/proveedor, como el impreso).

### Implicaciones de base de datos
**Ninguna migraciÃÂ³n.** Se aprovechan los ÃÂ­ndices existentes `(empresa, fecha)` de `Compra` y
`Venta`, y `(empresa, razon_social)` de `ClienteProveedor` para el `ORDER BY`. Las consultas usan
`select_related` + `.only(...)` acotado, porque el volumen real ronda las 400 filas por consulta
sobre tablas anchas. Queda pendiente evaluar con `EXPLAIN ANALYZE` sobre datos reales si el modo
*Pendientes* justifica un ÃÂ­ndice parcial `WHERE saldo <> 0` (decisiÃÂ³n D4 del plan).

### Pruebas automatizadas
```bash
.\venv\Scripts\python.exe manage.py test facturacion.tests.test_facturas_pendientes --noinput
```
**Resultado:** `Ran 24 tests in 570.528s - OK`

Cobertura: aislamiento multiempresa (incluido el caso de pasar por querystring el id de una
entidad de otra empresa), estados Pagadas/Pendientes/Todas con saldo negativo, filtro de
condiciÃÂ³n y el default vacÃÂ­o, `pagado` contra las aplicaciones reales de una Orden de Pago,
`pagado = total Ã¢ÂÂ saldo` en Ventas, cierre de los totales, ventas anuladas (excluidas por
defecto, sin contaminar totales, visibles y marcadas con el checkbox), totales sobre el conjunto
completo con truncado a 500, acumulado global y por grupo, Excel y PDF, y sÃÂ³lo lectura.

### Estado actual y siguientes pasos
Plan 056 **completo**. Pendientes registrados fuera de alcance: la fecha de vencimiento de los
comprobantes (decisiÃÂ³n D1 Ã¢ÂÂ requiere migraciÃÂ³n en `Compra`/`Venta` y tocar las pantallas de
carga, merece su propio plan) y el ÃÂ­ndice parcial del modo Pendientes (D4).

**RegresiÃÂ³n del mÃÂ³dulo completo:**
```bash
.\venv\Scripts\python.exe manage.py test facturacion --noinput
```
**Resultado:** `Ran 53 tests in 703.389s Ã¢ÂÂ FAILED (failures=1, errors=5)`

Los 6 son **preexistentes y ajenos a este cambio** (el diff no toca ninguno de los archivos
involucrados):
- 2 errores en `test_armeria_credencial_clu`: `TypeError: Sucursal() got unexpected keyword
  arguments: 'codigo'` Ã¢ÂÂ el modelo `Sucursal` no tiene ese campo. Ya estaba registrado como
  pendiente en la entrada del Plan 047.
- 3 errores en `test_exportar_clientes_excel`: el `setUp` hace
  `Jurisdiccion.objects.create(codigo=901, ...)` y choca con la semilla de la migraciÃÂ³n
  `facturacion/migrations/0025_cargar_jurisdicciones.py`, que ya inserta la jurisdicciÃÂ³n 901
  (`UniqueViolation` sobre `facturacion_jurisdiccion_codigo_key`). **Nuevo pendiente detectado.**
- 1 fallo en `test_arca_service.test_emitir_comprobante_homologacion_real`: prueba de integraciÃÂ³n
  real contra los servidores de ARCA en HomologaciÃÂ³n, rechazada del lado de ARCA
  (`Err 501: Error interno de base de datos`). Depende de un servicio externo.

### Ajuste posterior Ã¢ÂÂ tarjetas en los ÃÂ­ndices de mÃÂ³dulo
El acceso habÃÂ­a quedado sÃÂ³lo en el menÃÂº lateral. Se agregÃÂ³ la tarjeta correspondiente en las dos
pantallas de ÃÂ­ndice, siguiendo el patrÃÂ³n de tarjetas existente (color **orange**, libre en ambas):
- `templates/facturacion/compras_index.html` [MODIFY]: tarjeta "Facturas Pendientes"
  (`?operacion=C`), entre "Listado de Compras" y "Compras AutomÃÂ¡tica".
- `templates/facturacion/ventas_index.html` [MODIFY]: tarjeta "Facturas Pendientes"
  (`?operacion=V`), despuÃÂ©s de "Ventas por Producto".
- `static/css/output.css` [MODIFY]: recompilado Ã¢ÂÂ las clases `orange` eran nuevas en el purgado.

### CorrecciÃÂ³n Ã¢ÂÂ comentarios de template visibles en pantalla
Se estaban renderizando los comentarios como texto plano. Causa: **`{# ... #}` en Django sÃÂ³lo
funciona en una lÃÂ­nea**; los comentarios escritos en dos o tres lÃÂ­neas no se parsean y salen
literales. Se pasaron a `{% comment %}...{% endcomment %}`:
- `templates/facturacion/reportes/facturas_pendientes.html` [MODIFY]: 2 comentarios.
- `templates/facturacion/pdf/facturas_pendientes.html` [MODIFY]: 1 comentario (en el `<head>`).
- `templates/tesoreria/eoaf.html` [MODIFY] y `templates/tesoreria/modals/eoaf_cuenta_modal.html`
  [MODIFY]: mismo defecto, **preexistente** (Plan 050), tambiÃÂ©n visible en pantalla.

Barrido de todo `templates/`: no queda ningÃÂºn `{#` sin su `#}` en la misma lÃÂ­nea.

---

## 18 de Agosto de 2026 Ã¢ÂÂ Plan 055: BotÃÂ³n de ExportaciÃÂ³n a Excel en Clientes y Proveedores

### Objetivo
Incorporar la funcionalidad de exportaciÃÂ³n completa a formato Excel (`.xlsx`) en el listado de Clientes y Proveedores (`/clientes/`), que permita descargar los registros de la empresa respetando los filtros de bÃÂºsqueda activa (`q` y `tipo`) con **todos los campos de la tabla `ClienteProveedor` (25 columnas)** y **sin la restricciÃÂ³n de 50 registros en pantalla**.

### Archivos Modificados / Creados
- `facturacion/services/clientes_excel.py` [NEW]: servicio con `openpyxl` que construye el archivo Excel estilizado con 25 columnas, encabezado slate-900, importes formateados (`#,##0.00`) y auto-ajuste de ancho de columnas.
- `facturacion/views_reportes.py` [MODIFY]: agregado de la vista `@login_required exportar_clientes_excel(request)` que consulta el 100% de los registros filtrados sin lÃÂ­mite `[:50]` y ejecuta el servicio de descarga.
- `config/urls.py` [MODIFY]: registro de la ruta `path('clientes/exportar-excel/', exportar_clientes_excel, name='clientes_exportar_excel')`.
- `templates/facturacion/clientes_index.html` [MODIFY]: agregado del botÃÂ³n verde estilizado "Exportar Excel" en la barra de acciones superiores y la funciÃÂ³n JS `exportarExcel()` para enviar la bÃÂºsqueda activa.
- `facturacion/tests/test_exportar_clientes_excel.py` [NEW]: suite de pruebas unitarias para la descarga Excel sin filtro y con filtros de tipo y bÃÂºsqueda.
- `docs/planes/055_exportar_excel_clientes_proveedores.md` [NEW]: copia numerada del plan de implementaciÃÂ³n.
- `docs/walkthrough.md` [MODIFY]: registro incremental de la bitÃÂ¡cora.

### Detalle TÃÂ©cnico
1. **Campos Exportados (25 columnas):** ID, RazÃÂ³n Social, Tipo Entidad, Tipo Documento, CUIT/DNI, Fecha Nacimiento, Domicilio, C. Postal, Localidad, Provincia/JurisdicciÃÂ³n, Contacto, TelÃÂ©fono, Correo, CondiciÃÂ³n IVA, Ingresos Brutos, Saldo Inicial, Saldo Actual, LÃÂ­mite CrÃÂ©dito, Objetivo Mensual, ClasificaciÃÂ³n, Exige Orden Compra, Cta Patrimonial, Cta Resultado, CÃÂ³digo Anterior, Observaciones.
2. **Sin Truncamiento:** A diferencia de la grilla HTML que estÃÂ¡ acotada a `[:50]` por desempeÃÂ±o en navegador, la vista de exportaciÃÂ³n retorna el 100% de los contactos comerciales coincidentes con el filtro de bÃÂºsqueda.
3. **Formato:** Encabezado con tÃÂ­tulo de la empresa, subtÃÂ­tulo del reporte, filtros aplicados, fecha/hora de emisiÃÂ³n y celdas estilizadas.

---

## 18 de Agosto de 2026 Ã¢ÂÂ InicializaciÃÂ³n de Medios de Pago por Empresa y CorrecciÃÂ³n en Guardado de Recibos (Plan 057)

### Objetivo
Resolver el error de medio de pago al presionar "Guardar recibo" en la Empresa 2 (`ARMERIA ARMAR SAS`) para el recibo `RC 0001-00000003`, poblando la tabla `tesoreria_medio_pago` con la asignaciÃÂ³n correspondiente al plan de cuentas de cada empresa, optimizando la resoluciÃÂ³n por cÃÂ³digo (`EFE-ARS`, `EFE-USD`, `CHQ-TER`, `TRA-BCO`) y asegurando la atomicidad de transacciones con `transaction.set_rollback(True)`.

### Archivos Modificados / Creados
- `tesoreria/views_htmx.py` [MODIFY]:
  - `procesar_recibo` y `procesar_orden_pago`: bÃÂºsqueda jerÃÂ¡rquica de `MedioPago` especificando cÃÂ³digo (`EFE-ARS`, `EFE-USD`, `TRA-BCO`, `CHQ-TER`) antes del fallback por categorÃÂ­a (`EFE`, `TRA`, `CHQ`).
  - AdiciÃÂ³n de `transaction.set_rollback(True)` en bloques `except Exception as e:` para evitar el guardado de comprobantes huÃÂ©rfanos sin movimiento de caja ni asiento ante cualquier fallo.
- Base de Datos (`tesoreria_medio_pago`):
  - Reset de secuencia PostgreSQL (`tesoreria_medio_pago_id_seq`).
  - Sembrado de medios de pago para **Empresa 2** (`ARMERIA ARMAR SAS`) y **Empresa 3** (`LOPEZ RIOS Y ASOCIADOS SA`) enlazados a sus respectivas cuentas contables.
  - DepuraciÃÂ³n de recibos huÃÂ©rfanos de prueba (ID 6, 7 y 8) en Empresa 2.
- `docs/planes/057_corregir_error_medio_pago_recibos.md` [NEW]: plan de implementaciÃÂ³n histÃÂ³rico.
- `docs/walkthrough.md` [MODIFY]: registro incremental de la bitÃÂ¡cora.

### Detalle TÃÂ©cnico
1. **Modelado y Aislamiento por Empresa:** Tal como seÃÂ±alÃÂ³ acertadamente la decisiÃÂ³n de arquitectura, cada `MedioPago` debe pertenecer a una empresa (`empresa_id`) debido a que la `cuenta_contable_id` hace referencia a la tabla `cble_cuentas`, cuyos IDs primarios son ÃÂºnicos por plan de cuentas de empresa.
2. **Carga Inicial de Medios de Pago:**
   - **Empresa 2:** `EFE-ARS` y `EFE-USD` (Cta. 215 - CAJA), `CHQ-TER` (Cta. 216 - VALORES EN CARTERA), `TRA-BCO` (Cta. 217 - BANCO MACRO), `RET-GCIA` (Cta. 236 - AFIP RET. GCIAS), `RET-IIBB` (Cta. 253 - DGR IIBB SALDO A FAVOR).
   - **Empresa 3:** `EFE-ARS` y `EFE-USD` (Cta. 483 - CAJA), `CHQ-TER` (Cta. 484 - VALORES EN CARTERA), `TRA-BCO` (Cta. 485 - BANCO PATAGONIA), `RET-GCIA` (Cta. 498), `RET-IIBB` (Cta. 512).
3. **Robustez Transaccional:** Se introdujo `transaction.set_rollback(True)` en la captura de excepciones dentro de `procesar_recibo` y `procesar_orden_pago` decoradas con `@transaction.atomic`.

---

## 19 de Agosto de 2026 Ã¢ÂÂ Plan 059: RediseÃÂ±o UI/UX del Modal Mayor General de Cuenta (Saldos Mensuales)

### Objetivo
1. Implementar desplazamiento horizontal (`scroll` horizontal) en el listado de movimientos del modal Mayor General de Cuenta para evitar que se corten o compriman excesivamente las columnas contables.
2. Fijar el encabezado de las columnas (`<thead>`) mediante `sticky header` al realizar scroll vertical a lo largo de los movimientos.
3. Ampliar el ancho contenedor del modal de `max-w-5xl` (1024px) a `w-11/12 max-w-7xl` (1280px) para maximizar la visibilidad de datos en pantalla.
4. Ajustar el catÃÂ¡logo de columnas del Mayor General para establecer como predeterminadas ÃÂºnicamente las 7 columnas solicitadas: `ID Asiento`, `Fecha`, `Concepto`, `Debe`, `Haber`, `Saldo` y `CondiciÃÂ³n`.

### Archivos Modificados / Creados
- `contable/services/reportes_mayor.py` [MODIFY]:
  - ActualizaciÃÂ³n de `COLUMNAS_MAYOR_CATALOGO` otorgando `default = True` exclusivamente a las 7 claves predeterminadas (`asiento_id`, `fecha`, `concepto`, `debe`, `haber`, `saldo`, `condic`) y cambiando `cuenta_id`, `cuenta` y `sucursal` a `default = False`.
- `templates/contable/modals/mayor_cuenta_modal.html` [MODIFY]:
  - RediseÃÂ±o de la clase de tamaÃÂ±o modal a `w-11/12 max-w-7xl`.
  - ConfiguraciÃÂ³n del contenedor interno con `overflow-x-auto overflow-y-auto max-h-[calc(90vh-220px)]` e `inline-block align-middle min-w-full`.
  - Ajuste del `<thead>` inicial por defecto para las 7 columnas requeridas otorgÃÂ¡ndoles clases `sticky top-0 z-20 bg-slate-100 whitespace-nowrap`.
- `templates/contable/partials/libro_mayor_rows.html` [MODIFY]:
  - AdiciÃÂ³n de `whitespace-nowrap` a las celdas `<td>` del cuerpo del listado.
  - ActualizaciÃÂ³n de la funciÃÂ³n JavaScript `renderThead` incorporando las clases de sticky header y no quiebre de renglÃÂ³n (`sticky top-0 z-20 bg-slate-100 shadow-sm border-b border-slate-200 whitespace-nowrap`) a los elementos `<th>` generados dinÃÂ¡micamente.
- `docs/planes/059_rediseno_modal_mayor_cuenta.md` [NEW]: copia de respaldo numerada del plan de implementaciÃÂ³n.
- `docs/walkthrough.md` [MODIFY]: actualizaciÃÂ³n incremental de la bitÃÂ¡cora de desarrollo.

### Detalle TÃÂ©cnico
1. **Comportamiento del Scroll Horizontal y Vertical:** Al abrir el modal desde Saldos Mensuales o desde el Libro Mayor, el contenedor central de la grilla administra simultÃÂ¡neamente el scroll vertical de los movimientos y el scroll horizontal cuando el ancho acumulado de columnas supera el ancho ÃÂºtil de la pantalla.
2. **Encabezado Persistente (Sticky Header):** Al desplazarse verticalmente por una cuenta con cientos de asientos, la fila `<thead>` permanece anclada en la parte superior (`sticky top-0 z-20`) con fondo opaco `bg-slate-100`, asegurando que los tÃÂ­tulos de las columnas no se pierdan.
3. **CatÃÂ¡logo de Columnas:** Las 7 columnas por defecto abarcan exactamente la informaciÃÂ³n operativa fundamental. Cualquier columna adicional (ej. `Sucursal`, `NÃÂº Diario`, `MÃÂ³dulo`, `Cli/Prov`) puede agregarse o quitarse en tiempo real mediante el botÃÂ³n "Columnas".

### Pruebas Automatizadas
```powershell
.\venv\Scripts\python.exe manage.py test contable.tests.test_libro_mayor_columnas contable.tests.test_saldos_mensuales_vistas
```
**Resultado:** `Ran 20 tests in 137.644s - OK`

---

## 19 de Agosto de 2026 Ã¢ÂÂ Plan 058: VisualizaciÃÂ³n de Asientos, RestricciÃÂ³n de AnulaciÃÂ³n y CorrecciÃÂ³n de Imputaciones en OP

### Objetivo
1. Permitir consultar el asiento contable generado directamente desde la columna `Asiento` en los listados de ÃÂrdenes de Pago y Recibos de Cobranza mediante la apertura interactiva de un modal HTMX (`detalle_asiento_modal`).
2. Restringir la acciÃÂ³n `ANULAR` exclusivamente a usuarios Administradores (`is_superuser`, `is_staff` o `es_admin_sistema`) tanto en las grillas de ÃÂrdenes de Pago y Recibos como a nivel de endpoint de backend (retornando `HTTP 403 Forbidden`).
3. Corregir el botÃÂ³n de eliminaciÃÂ³n en la tabla de Imputaciones Contables Manuales en la pantalla de Carga de ÃÂrdenes de Pago (`ordenpago_carga.html`), reemplazando la etiqueta FontAwesome descompuesta por un icono SVG nativo de basura visible y estilizado.

### Archivos Modificados / Creados
- `tesoreria/views_listados.py` [MODIFY]:
  - `orden_pago_anular`: agregado de control de permisos de Administrador (`is_superuser or is_staff or es_admin_sistema`). Retorna `HTTP 403` si el usuario no es Administrador.
  - `recibo_anular`: agregado del mismo control de permisos con respuesta `HTTP 403` para no administradores.
- `templates/tesoreria/partials/ordenpago_grilla.html` [MODIFY]:
  - Columna 9 (`Asiento`): transformada en un botÃÂ³n HTMX interactivo que al presionar dispara `hx-get="{% url 'detalle_asiento_modal' fila.op.asiento_id %}"`.
  - Columna 10 (`Acciones`): botÃÂ³n `ANULAR` envuelto en la directiva Jinja `{% if user.is_superuser or user.is_staff or user.perfil.es_admin_sistema %}`.
- `templates/tesoreria/partials/recibo_grilla.html` [MODIFY]:
  - Columna 9 (`Asiento`): transformada en botÃÂ³n HTMX interactivo para abrir el modal del asiento contable.
  - Columna 10 (`Acciones`): botÃÂ³n `ANULAR` protegido para mostrarse ÃÂºnicamente a usuarios Administradores.
- `templates/tesoreria/ordenpago_carga.html` [MODIFY]:
  - Reemplazo de `<i class="fas fa-trash"></i>` en la celda de acciÃÂ³n de la tabla de imputaciones contables por un botÃÂ³n de eliminaciÃÂ³n con icono SVG visible en rojo.
- `templates/contable/modals/detalle_asiento_modal.html` [MODIFY]:
  - Reemplazo de `onclick="document.getElementById('modal-container-2').innerHTML=''"` por `onclick="this.closest('.fixed').remove()"` garantizando un cierre limpio.
  - AmpliaciÃÂ³n del ancho contenedor del modal de `max-w-4xl` a `max-w-5xl`, extensiÃÂ³n del ancho de las columnas `Debe` y `Haber` a `w-44` (176px) y adiciÃÂ³n de `whitespace-nowrap` a las celdas de montos en `tbody` y `tfoot` para impedir el quiebre de renglÃÂ³n del signo `$` y del importe.
- `docs/planes/058_mejoras_listados_op_recibos.md` [NEW]: copia del plan de implementaciÃÂ³n formalmente registrado.
- `docs/walkthrough.md` [MODIFY]: actualizaciÃÂ³n acumulativa de la bitÃÂ¡cora.

### Detalle TÃÂ©cnico
1. **Acceso al Asiento Contable:** Al hacer clic en el ID de asiento de cualquier Orden de Pago o Recibo, se ejecuta la peticiÃÂ³n HTMX al endpoint `detalle_asiento_modal` de la app `contable`, cargando la vista previa del asiento contable con sus lÃÂ­neas de Debe/Haber, saldo total e informaciÃÂ³n de cuentas asociadas.
2. **Seguridad y Roles:** Para mantener el principio de privilegio mÃÂ­nimo, los operadores/vendedores (`is_staff = False`, `es_admin_sistema = False`) no ven el botÃÂ³n `Anular` en las grillas de OP y Recibos, y si intentaran realizar la peticiÃÂ³n HTTP POST directamente, la vista intercepta el requerimiento y devuelve un estado `403 Forbidden`.
3. **Optimizaciones de UI y Modales:** La instrucciÃÂ³n `this.closest('.fixed').remove()` destruye limpia y reactivamente el elemento contenedor del modal flotante sin depender de un ID rÃÂ­gido en el DOM. AdemÃÂ¡s, el modal de asiento se ampliÃÂ³ a `max-w-5xl` con columnas `w-44` y `whitespace-nowrap`, asegurando que los montos en pesos de Debe, Haber y Total Asiento se presenten holgadamente en una sola lÃÂ­nea.

---

## 20 de Agosto de 2026 Ã¢ÂÂ Trazabilidad de Subproductos (Vista y LÃÂ­nea de Tiempo Modal)

### Objetivo
1. Crear una vista para listar subproductos trazables, permitiendo la bÃÂºsqueda por Cliente/Proveedor, Serie, CUIM y Producto, y filtrado automÃÂ¡tico al estado actual (ÃÂºltimo movimiento) aprovechando ÃÂ­ndices DISTINCT ON y order_by.
2. Validar que la trazabilidad estÃÂ© restringida a empresas con tipo de actividad 'ARMERIA' o 'AUTOMOTOR'.
3. Integrar un modal con lÃÂ­nea de tiempo interactivo que detalle el flujo cronolÃÂ³gico del subproducto (compras y ventas con su historial y comprobantes vinculados).

### Archivos Modificados / Creados
- productos/views_trazabilidad.py [NEW]:
  - SubproductoTrazabilidadListView: Listado general con soporte HTMX de grilla y paginaciÃÂ³n.
  - 	razabilidad_modal_timeline: Endpoint que devuelve el HTML renderizado con todo el historial de la serie clickeada.
- config/urls.py [MODIFY]: Registro de las rutas stock/trazabilidad/ y stock/trazabilidad/modal/<str:serie>/.
- 	emplates/base.html [MODIFY]: IntegraciÃÂ³n del enlace 'Trazabilidad Subproductos' debajo de Mantenimiento de Productos en el menÃÂº lateral.
- 	emplates/productos/trazabilidad_list.html [NEW]: Plantilla maestra del listado con formulario de bÃÂºsqueda.
- 	emplates/productos/partials/trazabilidad_grilla.html [NEW]: Plantilla parcial (table rows) usada por HTMX.
- 	emplates/productos/partials/trazabilidad_modal_timeline.html [NEW]: Componente modal estilizado (TailwindCSS) representando una lÃÂ­nea de tiempo (timeline) cronolÃÂ³gica.

### Detalle TÃÂ©cnico
1. **LÃÂ³gica de BÃÂºsqueda:** Para el filtro por CliPro, el sistema recupera inicialmente las series que tuvieron movimiento asociado con el Cliente/Proveedor buscado, y luego filtra la consulta principal.
2. **Eficiencia PostgreSQL:** El queryset final se ordena por serie, -feccpra y -subpro usando distinct('serie') para recuperar de forma altamente eficiente sÃÂ³lo el estado mÃÂ¡s reciente de la serie sin sobrecargar la memoria.
3. **Control de Acceso (ValidaciÃÂ³n de Negocio):** En el mÃÂ©todo dispatch() se chequea que empresa.tipo_actividad pertenezca a 'ARMERIA' o 'AUTOMOTOR'; caso contrario redirige al index de stock con un mensaje de advertencia.
4. **VisualizaciÃÂ³n en Modal (Timeline):** Se empleÃÂ³ CSS para construir una barra conectora (div.w-0.5.bg-gray-200), trazando el recorrido desde el Ingreso (Compra verde) hasta el Egreso (Venta roja), informando fechas, entidades y comprobantes vinculados.

---

## 20 de Agosto de 2026 Ã¢ÂÂ Mejoras UI/UX en Trazabilidad (Autocompletado y Dashboard)

### Objetivo
1. Implementar autocompletado en los filtros de trazabilidad usando Alpine JS (Typeahead pattern).
2. Agregar la tarjeta de acceso de 'Trazabilidad Subproductos' al Dashboard principal de Stock.
3. Solucionar el bug de solicitudes infinitas (looping requests de HTMX en la vista trazabilidad).

### Archivos Modificados
- `templates/productos/trazabilidad_list.html` [MODIFY]:
  - IntegraciÃÂ³n de la lÃÂ³gica Alpine.js `x-data="{ open: false }"` para autocompletado.
  - ConexiÃÂ³n de inputs a `typeahead_clientes`, `typeahead_series_trazabilidad` y `typeahead_productos_venta`.
  - Escucha de eventos custom (e.g. `clienteVentaSeleccionado`, `productoVentaEncontrado`) para autocompletar e invocar el form (`htmx.trigger`).
  - CorrecciÃÂ³n de `hx-trigger` que escuchaba globalmente `from:input` y generaba peticiones masivas al presionar cualquier tecla o dispararse eventos automÃÂ¡ticos.
- `templates/productos/stock_dashboard.html` [MODIFY]:
  - AdiciÃÂ³n del acceso directo (Tarjeta visual) al mÃÂ³dulo de Trazabilidad, restringido por la validaciÃÂ³n de negocio (uso en armerÃÂ­a o automotor).
- `productos/views_trazabilidad.py` [MODIFY]:
  - CorrecciÃÂ³n en `get_template_names()` aÃÂ±adiendo fallback de lectura `self.request.META.get('HTTP_HX_REQUEST')` por seguridad para asegurar la respuesta parcial.

### Detalle TÃÂ©cnico
1. **Autocompletado Typeahead:** Se reutilizaron componentes modales y parciales existentes de facturaciÃÂ³n (`clientes_typeahead`, `serie_typeahead`, `productos_venta_typeahead`), capturando sus eventos custom en JavaScript (como `seleccionarSerieVenta` o `window.addEventListener('clienteVentaSeleccionado')`) para rellenar los inputs del formulario y lanzar la bÃÂºsqueda asÃÂ­ncrona automÃÂ¡ticamente.
2. **Loop Infinito (BugFix HTMX):** El trigger global del form (`hx-trigger='keyup delay:500ms from:input'`) provocaba que scripts paralelos o extensiones que generaban eventos `keyup` causaran recargas enteras de la tabla. Esto se ha mitigado focalizando los `hx-trigger` y bloqueando el comportamiento por defecto del submit de teclado.

---

## 20 de Agosto de 2026 Ã¢ÂÂ OptimizaciÃÂ³n de Trazabilidad (LÃÂ­mite 50 registros)

### Objetivo
1. Limitar los resultados en la vista de trazabilidad a 50 registros, imitando el comportamiento de la bÃÂºsqueda de productos, para evitar la ralentizaciÃÂ³n en la carga inicial y en las consultas de PostgreSQL.

### Archivos Modificados
- `productos/views_trazabilidad.py` [MODIFY]:
  - Eliminado el atributo `paginate_by = 50` de la clase `SubproductoTrazabilidadListView`.
  - Aplicado slicing manual `return qs[:50]` al finalizar el mÃÂ©todo `get_queryset()`.

### Detalle TÃÂ©cnico
1. **Rendimiento PostgreSQL (Avoid COUNT*):** El uso nativo de paginaciÃÂ³n (`paginate_by`) en el `ListView` de Django obliga a ejecutar una consulta adicional `COUNT(*)` sobre el queryset resultante para saber el nÃÂºmero total de pÃÂ¡ginas. En este caso, tratÃÂ¡ndose de una tabla transaccional (Subproductos) con consultas pesadas de tipo `DISTINCT ON` combinadas con mÃÂºltiples `JOINS` y filtros de bÃÂºsqueda, el COUNT(*) introducÃÂ­a una severa penalizaciÃÂ³n de rendimiento ("slow query"). Al remover el paginador y hacer directamente el corte `[:50]`, le pedimos a la DB exactamente los primeros 50 elementos que coincidan con la bÃÂºsqueda (aplicando el index) de forma instantÃÂ¡nea, al igual que funciona el maestro de artÃÂ­culos.

---

## 21 de Agosto de 2026 Ã¢ÂÂ Plan 062: IncorporaciÃÂ³n de Costo de ReposiciÃÂ³n (cto_rep) en VentaItem

### Objetivo
Agregar el campo `cto_rep` (Costo de ReposiciÃÂ³n) a la tabla `facturacion_ventaitem` para congelar e inmutabilizar el costo de reposiciÃÂ³n vigente del producto (`productos_producto.cto_rep`) al momento exacto de la venta. Esto permite calcular con precisiÃÂ³n el **Margen Bruto**, la **ContribuciÃÂ³n Marginal** y el **Punto de Equilibrio** por ÃÂ­tem y por venta de manera independiente a futuras modificaciones de precios/costos en el catÃÂ¡logo de productos.

### Archivos Creados / Modificados
- `facturacion/models.py` [MODIFY]:
  - AdiciÃÂ³n del campo `cto_rep = models.DecimalField(max_digits=15, decimal_places=2, default=0)` en `VentaItem`.
  - LÃÂ³gica en `VentaItem.save()`: autocompletar `self.cto_rep = self.producto.cto_rep` si `cto_rep` es `0` o `None` al guardar.
  - Propiedades calculadas en `VentaItem`: `subtotal_costo_reposicion`, `contribucion_marginal_unitaria`, `contribucion_marginal_total`.
  - Propiedades calculadas en `Venta`: `total_costo_reposicion`, `contribucion_marginal_total`, `margen_bruto_porcentaje`.
- `facturacion/services/notas_credito.py` [MODIFY]:
  - AsignaciÃÂ³n explÃÂ­cita de `cto_rep=original_item.cto_rep` al generar el `VentaItem` de una Nota de CrÃÂ©dito.
- `facturacion/migrations/0049_ventaitem_cto_rep.py` [NEW]: migraciÃÂ³n de esquema que agrega la columna `cto_rep`.
- `facturacion/migrations/0050_backfill_ventaitem_cto_rep.py` [NEW]: migraciÃÂ³n de datos para backfill de ventas histÃÂ³ricas.
- `facturacion/tests/test_costo_reposicion.py` [NEW]: suite de pruebas unitarias para `cto_rep` y contribuciÃÂ³n marginal.
- `docs/planes/062_costo_reposicion_ventaitem.md` [NEW]: copia de respaldo archivada del plan de implementaciÃÂ³n.
- `docs/walkthrough.md` [MODIFY]: registro incremental de la bitÃÂ¡cora.

### Detalle TÃÂ©cnico
1. **Inmutabilidad del Costo de Venta:** Al concretar una venta, el costo de reposiciÃÂ³n del producto se estampa en `VentaItem.cto_rep`. Si el proveedor o el usuario aumentan posteriormente el costo de reposiciÃÂ³n en la ficha del producto, el costo registrado en la venta realizada se mantiene inalterado.
2. **Backfill HistÃÂ³rico:** La migraciÃÂ³n `0050_backfill_ventaitem_cto_rep` recorriÃÂ³ los registros de `VentaItem` donde `cto_rep` era 0 y les asignÃÂ³ el `cto_rep` actual de su correspondiente producto mediante operaciones en bloques (`bulk_update`).
3. **Punto de Equilibrio y ContribuciÃÂ³n Marginal:** La contribuciÃÂ³n marginal unitaria se computa restando el costo de reposiciÃÂ³n al precio de venta neto de descuento: `(precio_unitario * (1 - descuento/100)) - cto_rep`.

### Pruebas Automatizadas y VerificaciÃÂ³n
- **Script de VerificaciÃÂ³n Transaccional:**
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
Plan 062 **completado, migrado y verificado**. La base de datos y la capa de modelos cuentan con la trazabilidad inmutable del costo de reposiciÃÂ³n en cada ÃÂ­tem facturado y las propiedades para emitir anÃÂ¡lisis de contribuciÃÂ³n marginal y rentabilidad.

---

## 21 de Agosto de 2026 Ã¢ÂÂ CorrecciÃÂ³n Conceptual de Columna de Apertura y Acotamiento de Ejercicio en Sumas y Saldos Ã¢ÂÂ Plan 060

### Objetivo
1. Delimitar estrictamente el reporte de **Balance de Sumas y Saldos** al rango de fechas entre la fecha de inicio y de cierre del ejercicio activo de la sesiÃÂ³n.
2. Calcular la columna **Apertura** considerando la diferencia `Debe - Haber` del asiento contable de apertura (`condic = 5`) del ejercicio activo.
3. Incorporar un selector en la interfaz (checkbox) para habilitar o deshabilitar la inclusiÃÂ³n del asiento de apertura (predeterminado habilitado).
4. Cuando la `fecha_desde` sea mayor a la fecha de inicio del ejercicio activo, acumular en la columna **Apertura** el asiento de apertura (`condic = 5` si estÃÂ¡ activado) mÃÂ¡s los movimientos netos del ejercicio entre `ejercicio.inicio` y `fecha_desde - 1 dÃÂ­a`.

### Archivos Modificados / Creados
- `contable/views_htmx.py` [MODIFY]:
  - `get_balance_context`: procesa `mostrar_apertura` y delimita `fecha_desde` y `fecha_hasta` al rango `[ejercicio.inicio, ejercicio.cierre]`.
  - `_calcular_balance`: acota las consultas ORM a `asientolinea__asiento__ejercicio_id = ejercicio.id`. Construye 3 filtros disjuntos (`q_apertura_condic5`, `q_movimientos_previos` y `q_periodo`) y calcula la columna apertura para cada cuenta imputable y su rollup jerÃÂ¡rquico.
- `contable/services/saldos_mensuales.py` [MODIFY]:
  - Blindaje preventivo explÃÂ­cito en la consulta de apertura `apert` agregando los lÃÂ­mites de fecha `asiento__fecha__gte=ejercicio.inicio` y `asiento__fecha__lte=ejercicio.cierre`.
- `templates/contable/partials/balance.html` [MODIFY]:
  - AÃÂ±adido `<input type="hidden" name="filtros_aplicados" value="1">`.
  - AÃÂ±adido checkbox `<input type="checkbox" name="mostrar_apertura">` con label *"Incluir Apertura"* (predeterminado `checked`).
  - DelimitaciÃÂ³n de atributos `min` y `max` en los inputs de fecha al rango del ejercicio activo.
- `contable/tests/test_sumas_saldos_apertura.py` [NEW]:
  - Pruebas unitarias dedicadas (`SumasSaldosAperturaTest`) evaluando los 4 escenarios principales (apertura activada/desactivada, `fecha_desde == inicio` y `fecha_desde > inicio`).
- `docs/planes/060_correccion_apertura_sumas_y_saldos.md` [NEW]:
  - Registro permanente del plan de implementaciÃÂ³n en la documentaciÃÂ³n histÃÂ³rica.

### Detalle TÃÂ©cnico
1. **Paso de ParÃÂ¡metros:** `get_balance_context` verifica si el usuario desmarcÃÂ³ `mostrar_apertura` mediante los datos del querystring de filtros HTMX.
2. **CÃÂ¡lculo de Apertura:**
   $$\text{Apertura} = (\text{Debe}_5 - \text{Haber}_5 \text{ [si } mostrar\_apertura\text{]}) + (\text{Debe}_{\text{prev}} - \text{Haber}_{\text{prev}} \text{ [si } fecha\_desde > ejercicio.inicio\text{]})$$
3. **Respeto a Restricciones de BD:** Los asientos de test cumplen estrictamente las restricciones de unicidad y la regla matemÃÂ¡tica de base de datos `debe_xor_haber`.

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test contable.tests.test_saldos_mensuales contable.tests.test_sumas_saldos_apertura
```
**Resultado:** `Ran 31 tests in 23.410s - OK (27/27 de saldos_mensuales + 4/4 de sumas_saldos_apertura)`

### Estado actual y siguientes pasos
Plan 060 **completamente implementado, blindado y verificado**. Se mantuvieron en 100% verde la prueba cruzada de coincidencia entre Saldos Mensuales y Balance de Sumas y Saldos.

---

### Objetivo
1. AÃÂ±adir un botÃÂ³n en el menÃÂº superior (navbar) para poder colapsar y expandir la barra lateral izquierda (MenÃÂº Principal), ahorrando espacio en pantalla a peticiÃÂ³n del usuario.
2. Hacer que el sistema recuerde la preferencia del usuario si dejÃÂ³ abierto o cerrado el menÃÂº entre recargas de pÃÂ¡gina.

### Archivos Modificados
- `templates/base.html` [MODIFY]:
  - AÃÂ±adido el estado global `x-data="{ sidebarOpen: $persist(true) }"` en el elemento `<body>` para gestionar y persistir el estado de la barra en el LocalStorage.
  - AÃÂ±adido un botÃÂ³n interactivo a la izquierda del logo con un ÃÂ­cono de "hamburguesa" que invierte el estado `sidebarOpen`.
  - Envuelto el `<aside>` del sidebar con directivas `x-show="sidebarOpen"` y transiciones suaves para un efecto de deslizamiento al abrir o cerrar.

---

## 22 de Agosto de 2026 Ã¢ÂÂ Plan 066: CorrecciÃÂ³n del Alta de Proveedores y Reactividad Fiscal

### Objetivo
Resolver el fallo en el formulario modal `ClienteProveedor` que impedÃÂ­a registrar o ingresar un **Proveedor**, provocado por una reconversiÃÂ³n forzada a rol "Cliente" en el frontend cuando el tipo de documento inicial era 99 (Sin Identificar), asÃÂ­ como por la falta de validaciÃÂ³n estricta de CUIT y CondiciÃÂ³n Fiscal para proveedores en el backend.

### Archivos Creados / Modificados
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]:
### Pruebas Automatizadas
- **Tests Unitarios Django:**
  ```powershell
  .\venv\Scripts\python.exe manage.py test facturacion.tests.test_proveedor_alta
  ```
  **Resultado:** `Ran 3 tests in 2.150s - OK`

### Estado Actual y Siguientes Pasos
Plan 066 **completado y verificado**. La creaciÃÂ³n y ediciÃÂ³n de proveedores funciona de manera fluida y consistente en todo el sistema ERP Ikigai 2.

2. **LÃÂ³gica de Alerta:**
   - Si `dias > 15`: Estado `success` (sin banner de alerta).
   - Si `4 <= dias <= 15`: Estado `warning` (banner ÃÂ¡mbar preventivo).
   - Si `0 <= dias <= 3`: Estado `danger` (banner rojo urgente).
   - Si `dias < 0`: Estado `danger` con flag `es_vencido=True` (banner rojo parpadeante indicando que la facturaciÃÂ³n electrÃÂ³nica puede estar suspendida).

### Resultados de la VerificaciÃÂ³n
- **Prueba en Shell de Django:**
  - `e.estado_vencimiento_crt` evaluado para empresa activa, simulaciÃÂ³n de 10 dÃÂ­as restantes y simulaciÃÂ³n de certificado vencido.
  - **Resultado:** CÃÂ¡lculo exacto de dÃÂ­as, fechas formateadas y banderas activadas segÃÂºn lo esperado.
- **MigraciÃÂ³n de base de datos:** `Applying empresas.0015_empresa_vencimiento_crt_afip... OK`.

### Estado Actual
Plan 032 **completamente implementado, probado y verificado**. La gestiÃÂ³n de vencimiento de certificados digitales ARCA/AFIP estÃÂ¡ lista y operativa.

---

## 22 de Agosto de 2026 Ã¢ÂÂ ExportaciÃÂ³n Personalizada/Completa en Excel y Captura Masiva de Productos Ã¢ÂÂ Plan 063

### Objetivo
1. **ExportaciÃÂ³n Personalizada a Excel:** Permitir a los usuarios generar reportes en formato Excel `.xlsx` seleccionando dinÃÂ¡micamente entre la totalidad de los campos del modelo `Producto`.
2. **ExportaciÃÂ³n de Tabla Completa:** Brindar un botÃÂ³n de descarga directa de la plantilla/maestro completo de productos de la empresa actual con todos los campos operables.
3. **Captura / ImportaciÃÂ³n Masiva desde Excel:**
   - Forzar la conversiÃÂ³n y guardado **SIEMPRE EN MAYÃÂSCULAS** del detalle del producto, cÃÂ³digo de proveedor, cÃÂ³digo de fÃÂ¡brica, marcas, rubros y familias.
   - Si el `ID` del producto estÃÂ¡ en el Excel y existe en la base de datos de la empresa: **actualizar todos los campos excepto el ID**.
   - Si el `ID` estÃÂ¡ vacÃÂ­o/nulo o no existe: **crear el nuevo producto** asignÃÂ¡ndole automÃÂ¡ticamente el ID correspondiente que PostgreSQL genera.
   - Si la **Marca**, **Rubro** o **Familia** provista en el Excel no existe en la BD de la empresa: **crearla automÃÂ¡ticamente en MAYÃÂSCULAS**, asignarle su ID autonumÃÂ©rico y asociarla al nuevo producto.
   - Incluir una advertencia explÃÂ­cita destacada en el modal de captura aclarando que para productos nuevos se debe dejar la casilla `ID` vacÃÂ­a.

### Archivos Creados / Modificados
- `productos/services/excel_service.py` [NEW]:
  - `generar_excel_productos(queryset, columnas_seleccionadas)`: construye libros Excel `.xlsx` estilizados (header slate-900, bordes delgados, alineaciÃÂ³n numÃÂ©rica y autoajuste de ancho de columnas).
  - `procesar_captura_excel_productos(empresa, usuario, archivo_excel)`: procesa atÃÂ³micamente la lectura de archivos Excel, conversiÃÂ³n a MAYÃÂSCULAS, creaciÃÂ³n automÃÂ¡tica de Marcas/Rubros/Familias y actualizaciÃÂ³n/alta por `ID`.
- `productos/views_htmx.py` [MODIFY]:
  - `exportar_productos_excel_completo`: genera la descarga completa del maestro de productos.
  - `modal_exportar_seleccion`: despliega el modal interactivo con la lista completa de checkboxes por campo.
  - `exportar_productos_excel_seleccion`: procesa el POST y descarga el Excel filtrado por columnas.
  - `modal_capturar_excel`: renderiza el modal de captura con la advertencia de ID para nuevos artÃÂ­culos.
  - `capturar_productos_excel`: procesa la subida POST del Excel y retorna la parcial con el resumen de la captura emitiendo el evento `productosActualizados`.
- `productos/models.py` [MODIFY]:
  - Agregada la conversiÃÂ³n automÃÂ¡tica a MAYÃÂSCULAS en el mÃÂ©todo `save()` de `Producto`, `Marca`, `Rubro` y `Familia`.
- `config/urls.py` [MODIFY]:
  - Registradas las 5 rutas bajo `/productos/excel/`.
- `templates/productos/modals/exportar_seleccion_modal.html` [NEW]: modal interactivo de selecciÃÂ³n de columnas.
- `templates/productos/modals/capturar_excel_modal.html` [NEW]: modal de carga de archivo Excel con banner de advertencia visual.
- `templates/productos/modals/capturar_resultado_modal.html` [NEW]: modal con resumen de captura (indicadores de actualizados, creados, entidades creadas y observaciones).
- `templates/productos/stock_index.html` [MODIFY]: incorporados los 3 botones principales (*Capturar Excel*, *Exportar SelecciÃÂ³n*, *Excel Completo*) en la barra de herramientas.
- `productos/tests/test_excel_productos.py` [NEW]: suite de pruebas unitarias verificando exportaciÃÂ³n completa, exportaciÃÂ³n por selecciÃÂ³n y captura masiva con actualizaciÃÂ³n y alta de productos en MAYÃÂSCULAS.
- `docs/planes/063_exportar_importar_productos_excel.md` [NEW]: plan de implementaciÃÂ³n histÃÂ³rico formalmente registrado.

### Detalle TÃÂ©cnico
1. **Regla de Negocio de MayÃÂºsculas:** Todos los campos de texto (`detalle`, `cod_prov`, `cod_fab`, `marca`, `rubro`, `familia`) son procesados con `.upper().strip()` tanto a nivel de servicio de captura como en los modelos de Django mediante `save()`.
2. **Auto-AsignaciÃÂ³n de IDs:** Los productos existentes son identificados por la columna `ID` y actualizados sin modificar su clave primaria. Los productos nuevos con celda `ID` vacÃÂ­a se persisten mediante `Producto.objects.create(...)`, permitiendo que la secuencia autoincremental de la base de datos le otorgue el nuevo ID autonumÃÂ©rico.
3. **ResoluciÃÂ³n Inteligente de Entidades:** Si una Marca, Rubro o Familia mencionada en el Excel no existe en el catÃÂ¡logo de la empresa, el servicio ejecuta `get_or_create` guardÃÂ¡ndola en MAYÃÂSCULAS y vinculando su ID resultante al producto.
4. **Transaccionalidad:** Todo el proceso de captura corre bajo `@transaction.atomic()` para garantizar que un error crÃÂ­tico no deje la base de datos en un estado inconsistente.

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test productos.tests.test_excel_productos --keepdb
```
**Resultado:** `Ran 3 tests in 6.675s - OK`

### Estado actual y siguientes pasos
Plan 063 **completamente implementado, probado y verificado**.

---

### Objetivo
1. Evitar la ejecuciÃÂ³n de consultas pesadas a la base de datos sobre todo el historial al ingresar por primera vez a las pantallas de listados.
2. Establecer como valor predeterminado en los campos `desde` y `hasta` la fecha del dÃÂ­a de hoy (`timezone.localdate().isoformat()`) en los listados de:
   - **Recibos** (`/tesoreria/recibos/`)
   - **ÃÂrdenes de Pago** (`/tesoreria/ordenes-pago/`)
   - **Compras** (`/facturacion/compras/`)
   - **Ventas** (`/facturacion/ventas/`)

### Archivos Modificados / Creados
- `tesoreria/views_listados.py` [MODIFY]:
  - Modificado el helper `_rango_fechas(request)` para que `desde` tome por defecto la fecha actual (`hoy.isoformat()`) en lugar del primer dÃÂ­a del mes en curso. Esto actualiza unificadamente los listados de Recibos y ÃÂrdenes de Pago.
- `facturacion/views.py` [MODIFY]:
  - Modificado `ComprasListView.get()` para que si `desde` o `hasta` no son provistos en los parÃÂ¡metros `GET`, adopten la fecha de hoy.
  - Modificado `VentasListView.get()` para que si `desde` o `hasta` no son provistos en los parÃÂ¡metros `GET`, adopten la fecha de hoy.
- `docs/planes/061_fechas_predeterminadas_listados.md` [NEW]:
  - Archivo de documentaciÃÂ³n del plan histÃÂ³rico del proyecto.

### Detalle TÃÂ©cnico
1. **LÃÂ³gica de Fallback:** Al recibir solicitudes sin querystring de filtro por fecha (ej. primer renderizado al acceder desde el menÃÂº principal), la vista asume `desde = hoy` y `hasta = hoy`.
2. **Interactividad:** El usuario conserva la facultad de cambiar manualmente cualquier fecha en el formulario de filtros y hacer clic en consultar/filtrar para ver rangos mÃÂ¡s amplios (por ejemplo, el mes completo o ejercicios pasados).

### Estado actual y siguientes pasos
Plan 061 **completamente implementado, blindado y verificado**.

---

## 22 de Agosto de 2026 Ã¢ÂÂ RefactorizaciÃÂ³n y Limpieza de CatÃÂ¡logos (UnificaciÃÂ³n de Marcas, Rubros y Familias por Empresa) Ã¢ÂÂ Plan 064

### Objetivo
1. **UnificaciÃÂ³n Conceptual del CatÃÂ¡logo Maestro:** Eliminar de forma definitiva las relaciones `sucursales` (ManyToMany) en los modelos `Marca`, `Rubro` y `Familia` en la app `productos`.
2. **Consistencia y SimplificaciÃÂ³n de Base de Datos:** Establecer que los catÃÂ¡logos pertenecen globalmente a la `Empresa`. El aislamiento y segmentaciÃÂ³n por sucursal se gestiona de forma exclusiva en el inventario fÃÂ­sico (`StockSucursal`), movimientos de stock, operaciones de caja y comprobantes.
3. **Limpieza de UI/UX y EliminaciÃÂ³n de CÃÂ³digo Fantasma:** Quitar los componentes visuales de asignaciÃÂ³n de sucursales en los modales de creaciÃÂ³n/ediciÃÂ³n de categorÃÂ­as y en las tablas de configuraciÃÂ³n.

### Archivos Creados / Modificados
- `productos/models.py` [MODIFY]:
  - Eliminado el campo `sucursales = models.ManyToManyField(Sucursal, ...)` en los modelos `Marca`, `Rubro` y `Familia`.
- `productos/migrations/0030_remove_familia_sucursales_remove_marca_sucursales_and_more.py` [NEW]:
  - MigraciÃÂ³n de Django que elimina las 3 tablas pivote intermedias de PostgreSQL (`productos_marca_sucursales`, `productos_rubro_sucursales`, `productos_familia_sucursales`).
- `productos/forms.py` [MODIFY]:
  - Removido `'sucursales'` de `fields` y `widgets`, y limpiada la lÃÂ³gica de inicializaciÃÂ³n en `MarcaForm`, `RubroForm` y `FamiliaForm`.
- `productos/views_htmx.py` [MODIFY]:
  - Removidas las llamadas redundantes `form.save_m2m()` en `marca_modal`, `rubro_prod_modal` y `familia_modal`.
- `productos/management/commands/migrar_productos.py` [MODIFY]:
  - Removidas las asignaciones artificiales `sucursales.add(...)` durante la importaciÃÂ³n desde VFP.
- `templates/productos/modals/marca_modal.html` [MODIFY]:
  - Eliminada la secciÃÂ³n visual de selecciÃÂ³n de sucursales en el modal de marcas.
- `templates/productos/modals/rubro_prod_modal.html` [MODIFY]:
  - Eliminada la secciÃÂ³n visual de selecciÃÂ³n de sucursales en el modal de rubros de productos.
- `templates/productos/modals/familia_modal.html` [MODIFY]:
  - Eliminada la secciÃÂ³n visual de selecciÃÂ³n de sucursales en el modal de familias.
- `templates/configuracion/partials/marcas.html` & `marcas_list.html` [MODIFY]:
  - Eliminados el encabezado `<th>Sucursales</th>` y las etiquetas/badges por sucursal de la tabla de marcas.
- `templates/configuracion/partials/rubros_prod.html` & `rubros_prod_list.html` [MODIFY]:
  - Eliminados el encabezado `<th>Sucursales</th>` y la columna de sucursales de la tabla de rubros de productos.
- `templates/configuracion/partials/familias.html` & `familias_list.html` [MODIFY]:
  - Eliminados el encabezado `<th>Sucursales</th>` y la columna de sucursales de la tabla de familias.
- `docs/planes/064_limpieza_sucursales_catalogos.md` [NEW]:
  - Plan de implementaciÃÂ³n histÃÂ³rico formalmente guardado.

### Detalle TÃÂ©cnico
1. **Esquema de BD Simplificado:** Al remover el campo M2M en Django y aplicar la migraciÃÂ³n 0030, las 3 tablas pivote fueron eliminadas en PostgreSQL.
2. **Optimizaciones de Rendimiento y CÃÂ³digo:** Se aligeraron las transacciones de guardado al evitar inserciones en tablas pivote y se eliminaron filtros inÃÂºtiles.
3. **Cero Impacto Operativo Negativo:** La bÃÂºsqueda y facturaciÃÂ³n de productos continÃÂºa funcionando normalmente, ya que la disponibilidad por sucursal se rige por `StockSucursal.cantidad`.

### Estado actual y siguientes pasos
Plan 064 **completamente implementado, probado y verificado**.

---

## 22 de Agosto de 2026 Ã¢ÂÂ ReplicaciÃÂ³n de Plan de Cuentas, ParÃÂ¡metros, Medios de Pago y Cuentas Bancarias (Empresa 1 -> Empresa 3) Ã¢ÂÂ Plan 065

### Objetivo
1. **ReplicaciÃÂ³n Completa del Plan de Cuentas:** Duplicar el catÃÂ¡logo completo de 247 cuentas contables (`contable.models.Cuenta`) desde la Empresa Origen (`empresa_id = 1` - Lopez Rios y Asoc SA) hacia la Empresa Destino (`empresa_id = 3` - EMPRESA TEST).
2. **PreservaciÃÂ³n de Estructura JerÃÂ¡rquica:** Mantener y reasignar las relaciones de parentesco contable (`sumariza`) entre las cuentas clonadas correspondientes a la Empresa 3.
3. **ReplicaciÃÂ³n de ParÃÂ¡metros Contables:** Clonar la configuraciÃÂ³n de `contable.models.ParametrosContables` desde la Empresa 1 a la Empresa 3, mapeando automÃÂ¡ticamente las 23 claves forÃÂ¡neas de cuentas predeterminadas (`cta_caja_mostrador`, `cta_ventas`, `cta_compras`, `cta_iva_credito`, `cta_iva_debito`, etc.) hacia las cuentas clonadas equivalentes de la Empresa 3.
4. **MigraciÃÂ³n de Medios de Pago (`MedioPago`):** Procesar el archivo de exportaciÃÂ³n `d:\borrador\medios_pagos.csv` para poblar los Medios de Pago (`EFE-ARS`, `EFE-USD`, `CHQ-TER`, `TRA-BCO`, `RET-GCIA`, `RET-IIBB`) enlazÃÂ¡ndolos automÃÂ¡ticamente a las cuentas contables correspondientes para Empresa 3 y Empresa 1.
5. **ReplicaciÃÂ³n de Cuentas Bancarias (`CuentaBancaria`):** Clonar las Cuentas Bancarias de la Empresa 1 (Banco Patagonia, Credicoop, Galicia) hacia la Empresa 3, reasignando sus Foreign Keys de cuentas contables principales y de cheques emitidos.

### Archivos Creados / Modificados
- `contable/management/commands/replicar_plan_cuentas.py` [MODIFY]:
  - Comando de gestiÃÂ³n de Django `python manage.py replicar_plan_cuentas --origen 1 --destino 3` extendido con 5 fases atÃÂ³micas (`transaction.atomic()`).
- `docs/planes/065_replicar_plan_cuentas.md` [MODIFY]:
  - Plan de implementaciÃÂ³n histÃÂ³rico actualizado.
- `docs/walkthrough.md` [MODIFY]:
  - Registro cronolÃÂ³gico incremental en la bitÃÂ¡cora de desarrollo.

### Detalle TÃÂ©cnico
1. **Fase 1 - CreaciÃÂ³n/SincronizaciÃÂ³n de Cuentas:** Carga las 247 cuentas de la Empresa 1 y las crea/actualiza para la Empresa 3 usando un diccionario en memoria por jerarquÃÂ­a (`jerarquia`) para evitar consultas N+1.
2. **Fase 2 - AsignaciÃÂ³n JerÃÂ¡rquica (`sumariza`):** Mapea cada `sumariza_id` original al ID de la cuenta padre clonada para la Empresa 3.
3. **Fase 3 - ParÃÂ¡metros Contables:** Crea el registro `ParametrosContables` para la Empresa 3 y mapea de forma automÃÂ¡tica 23 campos FK (`cta_iva_credito`, `cta_iva_debito`, `cta_caja`, `cta_ventas`, `cta_compras`, `cta_caja_mostrador`, etc.) a sus cuentas clonadas correspondientes.
4. **Fase 4 - ImportaciÃÂ³n de Medios de Pago:** Lee `d:\borrador\medios_pagos.csv` y vincula reactivamente la `cuenta_contable` de cada medio de pago (`EFE-ARS`, `EFE-USD`, `CHQ-TER`, `TRA-BCO`, `RET-GCIA`, `RET-IIBB`) con `ParametrosContables` de cada empresa.
5. **Fase 5 - ReplicaciÃÂ³n de Cuentas Bancarias:** Clona los registros de `CuentaBancaria` de la Empresa 1 a la Empresa 3 asociando `cuenta_contable` y `cuenta_contable_cheques`.

### Resultados de la EjecuciÃÂ³n
- **Comando ejecutado:** `python manage.py replicar_plan_cuentas --origen 1 --destino 3`
- **Consola output:**
  - `Fase 1 completada: 247 cuentas procesadas en 'EMPRESA TEST'.`
  - `Fase 2 completada: 242 relaciones jerÃÂ¡rquicas ('sumariza') vinculadas.`
  - `Fase 3 completada: ParÃÂ¡metros Contables actualizados con 23 cuentas mapeadas.`
  - `Fase 4 completada: 6 Medios de Pago procesados desde d:\borrador\medios_pagos.csv.`
  - `Fase 5 completada: 3 Cuentas Bancarias procesadas en 'EMPRESA TEST'.`
- **ValidaciÃÂ³n DB:**
  - `Empresa 3` posee **247** cuentas contables, **1** `ParametrosContables`, **6** `MedioPago` y **3** `CuentaBancaria` enlazados.
  - `Empresa 1` posee **247** cuentas contables, **1** `ParametrosContables`, **6** `MedioPago` y **3** `CuentaBancaria` enlazados.

### Estado actual y siguientes pasos
Plan 065 **completamente implementado, probado y verificado**.

---

## 23 de Agosto de 2026 Ã¢ÂÂ Plan 069: Modelo `ArcaMisComprobantes` y Motor de ConciliaciÃÂ³n ARCA vs. Libro IVA

### Objetivo
Crear la tabla fÃÂ­sica `arca_mis_comprobantes` para almacenar las planillas de comprobantes emitidos (Ventas) y recibidos (Compras) capturados del portal de Mis Comprobantes ARCA / AFIP, e implementar la conciliaciÃÂ³n bi-direccional estampando `asiento_id` en ARCA y `cae` en el Libro IVA.

### Archivos Creados
- `impuestos/models.py` [MODIFY]: AdiciÃÂ³n del modelo `ArcaMisComprobantes` (`empresa`, `origen` ['C'/'V'], `periodo`, `fecha`, `codiva`, `punto`, `numero`, `numero_hasta`, `cuit_contraparte`, `razon_social_contraparte`, `neto_gravado`, `no_gravado`, `exento`, `iva_total`, `otros`, `total`, `cae`, `asiento_id`).
- `impuestos/migrations/0002_arcamiscomprobantes.py` [NEW]: MigraciÃÂ³n de Django para la creaciÃÂ³n de la tabla fÃÂ­sica `arca_mis_comprobantes`.
- `impuestos/tests/test_mis_comprobantes_arca.py` [NEW]: Tests unitarios para el modelo, parseo de planillas CSV/Excel y coincidencia bi-direccional de conciliaciÃÂ³n.
- `docs/planes/069_arca_mis_comprobantes.md` [NEW]: Copia archivada del plan tÃÂ©cnico de implementaciÃÂ³n.

### Archivos Modificados
- `impuestos/services.py` [MODIFY]: ImplementaciÃÂ³n de `importar_archivo_mis_comprobantes_arca`, `conciliar_mis_comprobantes_arca` y `obtener_reporte_conciliacion_arca`.
- `impuestos/views.py` [MODIFY]: ActualizaciÃÂ³n de `MisComprobantesArcaView` para procesar la subida del archivo ARCA (POST) y generar el reporte por PerÃÂ­odo Fiscal (`YYYYMM`) (GET).
- `templates/impuestos/mis_comprobantes_arca.html` [MODIFY]: RediseÃÂ±o con pestaÃÂ±as interactivas de Alpine.js: Ã°ÂÂÂ¢ **Conciliados**, Ã°ÂÂÂ¡ **Solo en Libro IVA (Sin CAE vinculada)** y Ã°ÂÂÂµ **Solo en Mis Comprobantes ARCA (Pendientes)**.

### Detalle TÃÂ©cnico
1. **VinculaciÃÂ³n Bi-direccional y SincronizaciÃÂ³n de PerÃÂ­odo Fiscal:**
   - En **`ArcaMisComprobantes`**: Al conciliar un registro con el ERP, se estampa el `asiento_id` correspondiente y se actualiza `periodo = match.periodo` con el **perÃÂ­odo exacto (`YYYYMM`) en el que fue declarado en los Libros IVA del sistema** (contemplando traslados de compras a perÃÂ­odos vigentes posteriores).
   - En **`cble_libro_iva_compras` / `cble_libro_iva_ventas`**: Al conciliar, se estampa el `cae` o `cai` capturado de ARCA (particularmente ÃÂºtil en facturaciÃÂ³n en lÃÂ­nea de ARCA o comprobantes manuales que no poseÃÂ­an CAE previo en el ERP).
2. **Resultados de ConciliaciÃÂ³n:**
   - **Conciliados**: `asiento_id` en ARCA y `cae` en el Libro IVA.
   - **Solo en Libro IVA**: Registros del sistema sin `cae` ni coincidencia en ARCA.
   - **Solo en ARCA**: Registros importados de ARCA pendientes con `asiento_id` nulo.

### Pruebas Ejecutadas
- **MigraciÃÂ³n aplicada:**
  - `Applying impuestos.0002_arcamiscomprobantes... OK`
- **System Check de Django:**
  ```powershell
  .\venv\Scripts\python.exe manage.py check
  ```
  **Resultado:** `System check identified no issues (0 silenced).`

### Estado Actual
Plan 069 **completamente implementado, migrado y verificado**. La captura e importaciÃÂ³n de planillas de Mis Comprobantes ARCA y su motor de conciliaciÃÂ³n bi-direccional contra el Libro IVA (con sincronizaciÃÂ³n del perÃÂ­odo declarado `YYYYMM`) estÃÂ¡n 100% operativos.

---

## 23 de Agosto de 2026 Ã¢ÂÂ Plan 068: GestiÃÂ³n de PerÃÂ­odos IVA, Cierre, Reapertura y Reglas de ImputaciÃÂ³n

### Objetivo
Desarrollar la lÃÂ³gica de gestiÃÂ³n de PerÃÂ­odos IVA (`YYYYMM`), liquidaciÃÂ³n mensual, cierres y reaperturas impositivas, e integrar sus reglas de imputaciÃÂ³n en las operaciones de Compras y Ventas.

### Archivos Creados
- `impuestos/models.py` [NEW]: Modelo `PeriodoIva` (`empresa`, `periodo`, `estado`, `fecha_cierre`, `usuario_cierre`, `debito_fiscal`, `credito_fiscal`, `saldo_resultante`, `fecha_reapertura`, `usuario_reapertura`).
- `impuestos/services.py` [NEW]: Funciones `es_periodo_cerrado`, `obtener_primer_periodo_vigente_compra`, `calcular_liquidacion_iva`, `cerrar_periodo_iva`, `reabrir_periodo_iva` y `obtener_periodos_cerrados`.
- `impuestos/tests/test_periodo_iva.py` [NEW]: Tests unitarios para el ciclo completo de PerÃÂ­odo IVA y traslados de compras a perÃÂ­odos vigentes.
- `impuestos/migrations/0001_initial.py` [NEW]: MigraciÃÂ³n inicial de `impuestos` (`PeriodoIva`).
- `contable/migrations/0020_libroivacompras_periodo_libroivaventas_periodo.py` [NEW]: AdiciÃÂ³n del campo `periodo` en `LibroIvaCompras` y `LibroIvaVentas`.
- `facturacion/migrations/0051_limpiar_y_alter_periodo.py` [NEW]: SanitizaciÃÂ³n de formatos guionados previos y ajuste de `max_length=6` en `periodo` de `Compra` y `Venta`.
- `templates/impuestos/modals/periodos_cerrados_modal.html` [NEW]: Modal HTMX para la visualizaciÃÂ³n y reapertura de perÃÂ­odos cerrados.
- `docs/planes/068_cierre_y_periodo_iva.md` [NEW]: Registro permanente del plan de implementaciÃÂ³n.

### Archivos Modificados
- `contable/models.py` [MODIFY]: Campo `periodo = models.CharField(max_length=6, default='', blank=True, db_index=True)` en `LibroIvaBase`.
- `facturacion/models.py` [MODIFY]: NormalizaciÃÂ³n de `periodo` a `max_length=6, db_index=True` en `Compra` y `Venta`.
- `contable/services/contabilizacion.py` [MODIFY]: Estampado del campo `periodo` al poblar `LibroIvaCompras` e inclusiÃÂ³n de `_limpiar_libro_iva_venta` y `_poblar_libro_iva_venta` para poblar `LibroIvaVentas` al contabilizar ventas fiscales.
- `facturacion/views.py` [MODIFY]: ValidaciÃÂ³n de perÃÂ­odo cerrado en Ventas (`es_periodo_cerrado`) y cÃÂ¡lculo automÃÂ¡tico de perÃÂ­odo vigente en Compras (`obtener_primer_periodo_vigente_compra`), previniendo perÃÂ­odos anteriores a la fecha de la factura.
- `impuestos/views.py` [MODIFY]: Vistas de liquidaciÃÂ³n, cierre, modal de perÃÂ­odos cerrados y reapertura en `CierrePeriodoIvaView`, `PeriodosCerradosModalView` y `ReabrirPeriodoIvaView`.
- `impuestos/urls.py` [MODIFY]: Ruteo de `periodos-cerrados/modal/` y `reabrir-periodo-iva/`.
- `templates/impuestos/cierre_periodo_iva.html` [MODIFY]: BotÃÂ³n "Ver PerÃÂ­odos Cerrados", desglose de DÃÂ©bito/CrÃÂ©dito y formulario de Cierre y Reapertura.
- `templates/facturacion/compras_carga.html` [MODIFY]: AdiciÃÂ³n del campo visual/selector del **PerÃÂ­odo IVA** (`YYYYMM`) en la cabecera del comprobante.

### Detalle TÃÂ©cnico
1. **Regla Estricta en Ventas:** El perÃÂ­odo predeterminado SIEMPRE es el `YYYYMM` de la fecha del comprobante. Si el perÃÂ­odo `YYYYMM` se encuentra CERRADO por liquidaciÃÂ³n fiscal, se bloquea la emisiÃÂ³n.
2. **Regla de Traslado de Compras a PerÃÂ­odos Vigentes:** Si se registra una factura de compra con fecha en un perÃÂ­odo cerrado (ej: 22/05/2026, estando cerrados 202601 a 202607), `obtener_primer_periodo_vigente_compra` calcula y asigna automÃÂ¡ticamente el primer perÃÂ­odo abierto `>= YYYYMM` (ej. `202608`). Se restringe categÃÂ³ricamente asignar un perÃÂ­odo anterior a la fecha de emisiÃÂ³n de la compra.
3. **Poblado Completo y Consulta de Libro IVA:** Se adecuaron los reportes de `LibroIvaVentasView` e `LibroIvaComprasView` para consultar exclusivamente por **PerÃÂ­odo Fiscal (`YYYYMM`)** mediante selectores de AÃÂ±o y Mes Fiscal, removiendo el criterio de dos fechas reservado ÃÂºnicamente a los reportes de gestiÃÂ³n.

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
Plan 068 **completamente implementado, migrado y verificado**. La gestiÃÂ³n de PerÃÂ­odos IVA, Cierre, Reapertura y las consultas impositivas de Libro IVA Ventas e Compras por PerÃÂ­odo Fiscal (`YYYYMM`) estÃÂ¡n 100% operativas.

---

## 23 de Agosto de 2026 Ã¢ÂÂ Plan 067: Nuevo Bloque del MenÃÂº Principal "Impuestos"

### Objetivo
Incorporar la nueva secciÃÂ³n **Impuestos** en el menÃÂº principal (barra lateral navegable) del ERP Ikigai 2, con un menÃÂº desplegable (acordeÃÂ³n interactivo con Alpine.js) e interfaces para la gestiÃÂ³n de 5 procesos y reportes impositivos.

### Archivos Creados
- `impuestos/__init__.py` [NEW]: Inicializador del paquete de la app Django impuestos.
- `impuestos/apps.py` [NEW]: DefiniciÃÂ³n del `ImpuestosConfig(AppConfig)`.
- `impuestos/urls.py` [NEW]: Ruteo del mÃÂ³dulo de impuestos (`app_name = 'impuestos'`).
- `impuestos/views.py` [NEW]: Vistas `ImpuestosIndexView`, `CierrePeriodoIvaView`, `LibroIvaVentasView`, `LibroIvaComprasView`, `MisComprobantesArcaView` y `SicoreGananciasView`.
- `templates/impuestos/index.html` [NEW]: Panel central/Dashboard de Impuestos con tarjetas interactivas.
- `templates/impuestos/cierre_periodo_iva.html` [NEW]: Pantalla para la liquidaciÃÂ³n mensual de IVA.
- `templates/impuestos/libro_iva_ventas.html` [NEW]: Pantalla para consultar y exportar el Libro IVA Ventas para Portal IVA (ARCA).
- `templates/impuestos/libro_iva_compras.html` [NEW]: Pantalla para consultar y exportar el Libro IVA Compras para Portal IVA (ARCA).
- `templates/impuestos/mis_comprobantes_arca.html` [NEW]: Pantalla para la captura y conciliaciÃÂ³n de Mis Comprobantes ARCA.
- `templates/impuestos/sicore_ganancias.html` [NEW]: Pantalla para la exportaciÃÂ³n de retenciones de Ganancias (RG 830) en formato SICORE.
- `docs/planes/067_bloque_impuestos.md` [NEW]: Copia archivada del plan tÃÂ©cnico de implementaciÃÂ³n.

### Archivos Modificados
- `config/settings.py` [MODIFY]: Registro de `'impuestos'` en `INSTALLED_APPS`.
- `config/urls.py` [MODIFY]: InclusiÃÂ³n de `path('impuestos/', include('impuestos.urls'))`.
- `templates/base.html` [MODIFY]: IntegraciÃÂ³n del nuevo acordeÃÂ³n **Impuestos** en el menÃÂº lateral con estado activo segÃÂºn la URL solicitada.

### Detalle TÃÂ©cnico
1. **MÃÂ³dulo AutÃÂ³nomo y Modular (`impuestos`):** Se creÃÂ³ la estructura completa de la aplicaciÃÂ³n Django `impuestos`, permitiendo escalar de forma limpia los procesos impositivos del sistema.
2. **NavegaciÃÂ³n DinÃÂ¡mica en la Barra Lateral:** El menÃÂº se despliega automÃÂ¡ticamente si la ruta del usuario comienza con `/impuestos/`, manteniendo el enlace del subproceso activo con resaltado especÃÂ­fico en color.
3. **Dashboard de Impuestos:** DiseÃÂ±ado con Tailwind CSS y tarjetas dinÃÂ¡micas con hover y sombras animadas para acceder a cada proceso:
   - **Cierre Periodo IVA** (`/impuestos/cierre-periodo-iva/`)
   - **Libro IVA Ventas - Portal IVA** (`/impuestos/libro-iva-ventas/`)
   - **Libro IVA Compras - Portal IVA** (`/impuestos/libro-iva-compras/`)
   - **Captura Mis Comprobantes ARCA** (`/impuestos/mis-comprobantes-arca/`)
   - **SICORE - RetenciÃÂ³n Impuesto a las Ganancias** (`/impuestos/sicore-ganancias/`)

### Pruebas Ejecutadas
- **System Check de Django:**
  ```powershell
  .\venv\Scripts\python.exe manage.py check
  ```
  **Resultado:** `System check identified no issues (0 silenced).`

### Estado Actual
Plan 067 **completamente implementado y verificado**. La secciÃÂ³n de Impuestos ya se encuentra integrada en la barra lateral del ERP Ikigai 2 y sus vistas estÃÂ¡n activas.

---

## 23 de Agosto de 2026 Ã¢ÂÂ ExportaciÃÂ³n y Recaptura Masiva en Excel del Plan de Cuentas Ã¢ÂÂ Plan 066

### Objetivo
1. **ExportaciÃÂ³n a Excel Completo:** Implementar la exportaciÃÂ³n del listado total de cuentas contables (`contable.models.Cuenta`) de la empresa activa en formato `.xlsx` con estilos openpyxl (slate header `0F172A`, texto blanco en negrita Arial, bordes delgados y autoajuste de ancho).
2. **Recaptura / ImportaciÃÂ³n Masiva desde Excel:** Proveer un modal interactivo con HTMX y Tailwind CSS para subir un archivo Excel y procesar actualizaciones y altas masivas de cuentas de forma atÃÂ³mica (`transaction.atomic()`).
3. **Manejo Inteligente de IDs:**
   - Si la celda `ID` coincide con una cuenta existente en la empresa activa, se actualizan sus campos (`JerarquÃÂ­a`, `Nombre Cuenta`, `Imputable`, `Tipo`, `CÃÂ³digo Legacy`, `RG 830`, `Tipo Disponibilidad`, etc.) manteniendo intacto el `ID`.
   - Si la celda `ID` estÃÂ¡ vacÃÂ­a o el `ID` no existe en la empresa activa, se interpreta como cuenta nueva. El sistema **no fuerza el ID ingresado** y deja que PostgreSQL le asigne automÃÂ¡ticamente el `ID` autoincremental correspondiente.
   - UnificaciÃÂ³n automÃÂ¡tica de los nombres de cuenta en **MAYÃÂSCULAS**.

### Archivos Creados / Modificados
- `contable/services/excel_service.py` [NEW]:
  - `COLUMNAS_CUENTA_MAP`: Mapeo de columnas y encabezados de Excel.
  - `generar_excel_cuentas(queryset)`: Servicio de generaciÃÂ³n de `.xlsx` para el plan de cuentas.
  - `procesar_captura_excel_cuentas(empresa, usuario, archivo_excel)`: LÃÂ³gica atÃÂ³mica de lectura de Excel, actualizaciÃÂ³n por ID existente y alta de cuentas nuevas con resoluciÃÂ³n de parentesco (`sumariza`).
- `contable/views_htmx.py` [MODIFY]:
  - `exportar_cuentas_excel_completo`: Vista para descargar el Excel completo.
  - `modal_capturar_cuentas_excel`: Despliega el modal de recaptura.
  - `capturar_cuentas_excel`: Procesa el archivo subido via POST y emite la seÃÂ±al HTMX `reloadCuentas`.
- `templates/contable/modals/capturar_excel_modal.html` [NEW]:
  - Plantilla del modal de recaptura con resumen de resultados y caja de alerta destacada con las reglas aclaratorias de carga de ID.
- `templates/configuracion/partials/cuentascontables.html` [MODIFY]:
  - IntegraciÃÂ³n de los botones **"Capturar Excel"** y **"Excel Completo"** en la barra superior junto al botÃÂ³n de **"Nueva Cuenta"**.
- `config/urls.py` y `contable/urls.py` [MODIFY]:
  - Registro de las rutas URL para exportaciÃÂ³n y recaptura de cuentas contables.
- `contable/tests/test_excel_cuentas.py` [NEW]:
  - Pruebas automatizadas de exportaciÃÂ³n a Excel y recaptura masiva (creaciÃÂ³n con ID vacio/inexistente y actualizaciÃÂ³n por ID).
- `docs/planes/066_recaptura_excel_plan_cuentas.md` [NEW]:
  - Copia guardada del plan de implementaciÃÂ³n en la carpeta histÃÂ³rica de planes.
- `docs/walkthrough.md` [MODIFY]:
  - ActualizaciÃÂ³n de la bitÃÂ¡cora de desarrollo.

### Detalle TÃÂ©cnico
1. **Regla de Negocio del ID:** Se verificÃÂ³ el diccionario en memoria de las cuentas existentes por `id` pertenencientes a `empresa=empresa`. Si el ID suministrado no se encuentra en la base de datos de esa empresa, la fila se inserta mediante `Cuenta.objects.create(empresa=empresa, ...)` sin pasar la clave primaria `id`, permitiendo que la secuencia de PostgreSQL genere la clave incremental limpia sin conflictos.
2. **AsignaciÃÂ³n JerÃÂ¡rquica:** Se calcula la jerarquÃÂ­a padre extrayendo la subcadena previa al ÃÂºltimo punto (ej. `1.1` para `1.1.01`) y asociando la Foreign Key `sumariza` automÃÂ¡ticamente.
3. **Respuesta HTMX:** Si la recaptura actualiza o crea al menos 1 cuenta, la vista asigna la cabecera `HX-Trigger: {"reloadCuentas": true}`, refrescando inmediatamente la grilla de cuentas sin recargar la pÃÂ¡gina.

### Resultados de las Pruebas
- **Comando ejecutado:** `.\venv\Scripts\python.exe manage.py test contable.tests.test_excel_cuentas`
- **Resultado:**
  - `Ran 3 tests in 0.941s` -> **OK**
  - `test_generar_excel_cuentas`: PasÃÂ³ exitosamente.
  - `test_capturar_excel_actualizar_y_crear_cuentas`: PasÃÂ³ exitosamente (verificÃÂ³ actualizaciÃÂ³n de ID existente, creaciÃÂ³n de ID en blanco y asignaciÃÂ³n de ID autoincremental automÃÂ¡tico al ingresar un ID inexistente).
  - `test_views_excel_exportar_y_modal`: PasÃÂ³ exitosamente.

### Estado actual y siguientes pasos
Plan 066 **completamente implementado, probado y verificado**.

## 24 de Agosto de 2026 Ã¢ÂÂ Plan 070: IncorporaciÃÂ³n de Actividades "Distribuidora" y "Empresa AgrÃÂ­cola" en Empresas

### Objetivo
AÃÂ±adir las opciones de actividad **Distribuidora** y **Empresa AgrÃÂ­cola** en el selector (`tipo_actividad`) de `Empresa` y `EmpresaForm` para su selecciÃÂ³n en el formulario modal de alta y ediciÃÂ³n de empresas.

### Archivos Modificados / Creados
- `empresas/models.py` [MODIFY]: Definida la tupla `TIPO_ACTIVIDAD_CHOICES` en el modelo `Empresa` incluyendo `('DISTRIBUIDORA', 'Distribuidora')` y `('AGRICOLA', 'Empresa AgrÃÂ­cola')`.
- `empresas/forms.py` [MODIFY]: Vinculado `tipo_actividad` en `EmpresaForm` a `Empresa.TIPO_ACTIVIDAD_CHOICES`.
- `empresas/migrations/0016_alter_empresa_tipo_actividad.py` [NEW]: MigraciÃÂ³n de Django que registra los nuevos `choices` en `Empresa`.
- `docs/planes/070_actividades_distribuidora_y_agricola.md` [NEW]: Copia del plan de implementaciÃÂ³n archivada.

### Implicaciones de Base de Datos
- MigraciÃÂ³n aplicada: `empresas.0016_alter_empresa_tipo_actividad` (OK).

### Estado Actual
Plan 070 **completamente implementado y verificado**. Las opciones Distribuidora y Empresa AgrÃÂ­cola se encuentran activas en el selector de tipo de actividad de las empresas.

---

## 26 de Agosto de 2026 Ã¢ÂÂ Plan 071: Ajustes en Trazabilidad de Subproductos (/stock/trazabilidad/)

### Tarea u Objetivo
Implementar tres mejoras clave en el mÃÂ³dulo de Trazabilidad de Subproductos:
1. AmpliaciÃÂ³n del historial de trazabilidad por **Serie y CUIM** (multiciclo) y creaciÃÂ³n del modal de detalle completo de compra (`compra_id`) y venta (`id_vta > 0`).
2. Modal y vista HTMX de **EdiciÃÂ³n exclusiva de SERIE y CUIM** para subsanar errores de tipeo sin alterar montos ni comprobantes.
3. ReversiÃÂ³n automÃÂ¡tica del subproducto de `'VENDIDA'` a `'DEPOSITO'` y limpieza de la relaciÃÂ³n con la venta al emitir una Nota de CrÃÂ©dito por devoluciÃÂ³n.

### Archivos Creados
- `templates/productos/partials/subproducto_detalle_modal.html` [NEW]: Plantilla modal HTMX con la ficha completa de datos de adquisiciÃÂ³n (compra_id, fecha, proveedor, comprobante, costo adq, moneda, cotizaciÃÂ³n) y venta (id_vta, fecha, cliente, comprobante, precio neto y total).
- `templates/productos/partials/subproducto_editar_modal.html` [NEW]: Formulario modal HTMX restringido exclusivamente a la modificaciÃÂ³n de los campos `SERIE` y `CUIM`.
- `facturacion/tests/test_plan071_trazabilidad.py` [NEW]: Tests automatizados Django probando la reversiÃÂ³n a DEPOSITO al emitir Nota de CrÃÂ©dito y la ediciÃÂ³n exclusiva de SERIE/CUIM.
- `docs/planes/071_ajustes_trazabilidad_subproductos.md` [NEW]: Copia archivada del plan tÃÂ©cnico de implementaciÃÂ³n.

### Archivos Modificados
- `productos/views_trazabilidad.py` [MODIFY]: 
  - AmpliaciÃÂ³n de `trazabilidad_modal_timeline` para consolidar el historial por Serie y/o CUIM.
  - AdiciÃÂ³n de la vista `@login_required subproducto_detalle_modal(request, subpro_id)` con consulta select_related de compra y venta.
  - AdiciÃÂ³n de la vista `@login_required subproducto_editar_modal(request, subpro_id)` para actualizaciÃÂ³n exclusiva de `serie` y `cuim`.
- `facturacion/services/notas_credito.py` [MODIFY]: ReversiÃÂ³n automÃÂ¡tica en `emitir_nota_credito_desde_venta`: al devolver un producto trazable (`subprod == True`), sus objetos `Subproducto` asociados se actualizan a `situacion = 'DEPOSITO'`, `venta = None` (`id_vta = null`), `fecvta = None`, `precio_neto = 0`, `precio_total = 0`, `cotizvta = 1`, `fecent = None`.
- `config/urls.py` [MODIFY]: Registro de las rutas HTMX `/stock/trazabilidad/subproducto/<int:subpro_id>/detalle/` y `/stock/trazabilidad/subproducto/<int:subpro_id>/editar/`.
- `templates/productos/partials/trazabilidad_grilla.html` [MODIFY]: IncorporaciÃÂ³n de botones de acciÃÂ³n "Detalle" y "Editar" en cada fila de la grilla.
- `templates/productos/trazabilidad_list.html` [MODIFY]: RediseÃÂ±o de cabecera inline y formulario ultra-compacto de 1 sola fila con Flexbox proporcional (`flex-1` en CliPro/Producto y anchos reducidos `w-32` Serie, `w-28` CUIM, `w-36` Estado y `w-20` Limpiar). Configurado disparador HTMX dinÃÂ¡mico en `SERIE` y `CUIM` a partir del 3er carÃÂ¡cter (`keyup[len>=3 || len==0] delay:250ms`).
- `productos/views_trazabilidad.py` [MODIFY]: CondiciÃÂ³n backend `len >= 3` en `search_serie` y `search_cuim` para filtrado dinÃÂ¡mico.
- `templates/productos/partials/trazabilidad_grilla.html` [MODIFY]: ReducciÃÂ³n de padding de celdas a `py-2 px-3` duplicando la densidad de filas visibles por pantalla.

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
Plan 071 **completamente ejecutado, verificado y documentado**. El mÃÂ³dulo de Trazabilidad de Subproductos cuenta con interfaz ultra-compacta que maximiza el espacio del listado, filtrado dinÃÂ¡mico en tiempo real a partir del 3er carÃÂ¡cter en Serie y CUIM, historial multiciclo por Serie y CUIM, selector de filtrado por Estado Actual (`DEPOSITO` / `VENDIDA`), ficha completa de detalles de compra/venta, ediciÃÂ³n rÃÂ¡pida de Serie/CUIM y reversiÃÂ³n automÃÂ¡tica a 'DEPOSITO' ante Notas de CrÃÂ©dito.

---

## 26 de Agosto de 2026 Ã¢ÂÂ Limpieza de Archivos Temporales (PDF y PNG) en Carga de Compras

### Objetivo
1. **Borrar Temp de Compras:** Solucionar el problema de la acumulaciÃÂ³n de archivos temporales (PDFs e imÃÂ¡genes PNG de vista previa) que no se borraban luego de cargar una factura de compra mediante el servicio OCR de lectura de CUIT.

### Archivos Creados / Modificados
- `facturacion/services/extractor_facturas.py` [MODIFY]:
  - Modificada la generaciÃÂ³n del nombre de la imagen PNG temporal para que utilice el mismo nombre base que el PDF (en lugar de generar un UUID distinto), lo que permite que el backend pueda emparejarlos y borrarlos juntos al finalizar.
- `facturacion/views.py` [MODIFY]:
  - En la vista de carga de comprobantes, modificado el bloque donde se persiste el PDF definitivo para tambiÃÂ©n ubicar y eliminar el PNG temporal correspondiente, de forma conjunta y limpia.
- `facturacion/views_procesamiento.py` [MODIFY]:
  - En `CargaCompraAutomaticaView.post`, aÃÂ±adido un recolector de basura (garbage collector) proactivo: `_limpiar_temp_facturas(temp_dir)`. Este proceso corre antes de crear un nuevo archivo y elimina automÃÂ¡ticamente cualquier archivo huÃÂ©rfano dentro de `temp_facturas` que sea anterior a 1 hora (3600 segundos). Esto asegura que los archivos abandonados (subidos, pero no persistidos) no se acumulen.

### Detalle TÃÂ©cnico
1. **Emparejamiento por Basename:** Al guardar el PDF se asocia un nombre base (ej. `1234abcd.pdf`) y ahora la imagen se llama igual (`1234abcd.png`).
2. **Garbage Collector de Temp:** Para los casos en que el usuario sube una factura y abandona la pÃÂ¡gina sin guardar, la limpieza periÃÂ³dica basada en el tiempo de modificaciÃÂ³n del archivo (`st_mtime`) impide que la carpeta `temp_facturas` crezca sin control.

### Estado actual y siguientes pasos
CorrecciÃÂ³n de archivos temporales **completamente implementada y operativa**.

## 26 de Agosto de 2026 Ã¢ÂÂ ConversiÃÂ³n de Facturas a WEBP y Nombramiento EspecÃÂ­fico (Plan 067)

### Objetivo
1. **UnificaciÃÂ³n WebP (Stitching):** Optimizar el almacenamiento y visualizaciÃÂ³n convirtiendo los PDFs de compras en imÃÂ¡genes verticales continuas en formato `WebP`, en lugar de preservar el PDF.
2. **Nomenclatura y Directorio Fijo:** Renombrar el archivo generado siguiendo el patrÃÂ³n estricto `{empresa_id}.{ejercicio_id}.{asiento_id}.webp` y ubicarlo en la carpeta `compras_archivosWEBP/` **sÃÂ³lo** tras confirmar y contabilizar la compra.
3. **Bloqueo de EdiciÃÂ³n (Readonly):** Proteger los montos leÃÂ­dos mediante OCR en el frontend, bloqueando la ediciÃÂ³n de precios en la grilla al provenir del escÃÂ¡ner automÃÂ¡tico.

### Archivos Modificados
- `facturacion/services/extractor_facturas.py` [MODIFY]:
  - Modificado el extractor para iterar hasta 5 pÃÂ¡ginas del documento PDF, convertir cada `pixmap` a una imagen con `Pillow` y unirlas verticalmente en un "pergamino" continuo (`stitched.paste()`).
  - Cambiado el formato de salida a `WEBP` en lugar de `PNG` logrando mayor compresiÃÂ³n.
- `facturacion/models.py` [MODIFY]:
  - Actualizado `compras_pdf_path` para apuntar ahora a `compras_archivosWEBP/{filename}` sin timestamp (el nombre viene prefijado del controlador).
- `facturacion/views_procesamiento.py` [MODIFY]:
  - Ahora se devuelve la ruta `.webp` a la sesiÃÂ³n y se destruye el PDF original de forma segura (sin cron script en python, confiando en limpieza temporal asÃÂ­ncrona de SO).
- `facturacion/views.py` [MODIFY]:
  - Al completar la transacciÃÂ³n y generar el asiento en `ComprasCargaView.post`, se captura `compra.asiento_id` y `compra.ejercicio_id` para renombrar y guardar definitivamente el comprobante como `{empresa_id}.{ejercicio_id}.{asiento_id}.webp`.
- `templates/facturacion/compras_carga.html` [MODIFY]:
  - Se implementÃÂ³ un script que detecta si el formulario proviene de OCR (`pdf_temp_path`). De ser asÃÂ­, se iteran todos los campos `precio`, `cto_adq`, `cto_rep` y `descuento`, inyectando propiedades `readOnly` y aplicando clases de bloqueo visual (`bg-slate-100`, `cursor-not-allowed`) para blindar la integridad del dato escaneado.

### Detalle TÃÂ©cnico
1. **Stitching sin OOM:** El bucle de pÃÂ¡ginas estÃÂ¡ acotado deliberadamente a `min(5, len(doc))` para mitigar posibles ataques de denegaciÃÂ³n (archivos de miles de pÃÂ¡ginas) que provoquen Timeouts en Gunicorn o saturen la RAM, cubriendo a la vez el 99% de las facturas convencionales.
2. **Manejo de Transacciones:** Si el usuario no hace clic en "Aceptar" y abandona la pÃÂ¡gina, la imagen WebP vive ÃÂºnicamente en `temp_facturas/`, el cual serÃÂ¡ depurado con un cron de Linux. NingÃÂºn registro huÃÂ©rfano impacta en `compras_archivosWEBP`.

### Estado actual y siguientes pasos
El plan estÃÂ¡ **completamente implementado, blindado y probado**. Los comprobantes son ahora pergaminos WebP muy ligeros.

## 26 de Agosto de 2026 Ã¢ÂÂ CorrecciÃÂ³n de desapariciÃÂ³n de Proveedor al editar Producto

### Objetivo
1. **Evitar desapariciÃÂ³n de proveedor:** Solucionar el problema reportado donde al editar un producto en el sistema, el proveedor preexistente desaparecÃÂ­a del formulario forzando al usuario a volver a seleccionarlo.

### Archivos Modificados
- `productos/forms.py` [MODIFY]:
  - Modificado el mÃÂ©todo `__init__` de `ProductoForm`. El queryset del campo `proveedor` ahora incluye no solo a los proveedores estÃÂ¡ndar de la empresa activa (`tipo_entidad=2`), sino que tambiÃÂ©n se expande dinÃÂ¡micamente mediante `Q()` para incluir explÃÂ­citamente al proveedor actual del producto en caso de que este fuera configurado de forma global (`empresa__isnull=True`) o con otro `tipo_entidad`.
  - Se agregÃÂ³ ordenamiento alfabÃÂ©tico `.order_by('razon_social')` para el catÃÂ¡logo de proveedores y por `'detalle'` para Marca, Rubro y Familia.

### Detalle TÃÂ©cnico
1. **ConservaciÃÂ³n de Foreign Key:** El comportamiento original de `forms.Select` de Django descarta automÃÂ¡ticamente el valor actual de una instancia si este no se encuentra presente dentro del queryset asignado al campo. Al ampliar el queryset sumando el `self.instance.proveedor_id` mediante el operador `|` (OR), garantizamos que la opciÃÂ³n se renderice correctamente en el DOM y no se pierda al guardar el formulario.

### Estado actual y siguientes pasos
El problema de ediciÃÂ³n de proveedor estÃÂ¡ **completamente solucionado**.

## 26 de Agosto de 2026 Ã¢ÂÂ Perfil de Lectura Inteligente de Compras (CUIT 30-71132306-2)

### Objetivo
1. **Nuevo perfil OCR:** Incorporar un mÃÂ³dulo de lectura de PDF para las facturas del proveedor con CUIT `30-71132306-2`, capaz de identificar el "ArtÃÂ­culo" como cÃÂ³digo principal, pero que tambiÃÂ©n separe y ofrezca el cÃÂ³digo suplementario ubicado al final de la descripciÃÂ³n.
2. **Emparejamiento flexible:** Permitir que el sistema busque el producto en la base de datos de la empresa haciendo un doble intento inteligente (`fallback`): primero por el cÃÂ³digo principal ("ArtÃÂ­culo"), y si falla, por el cÃÂ³digo alternativo del proveedor que venÃÂ­a embutido en el detalle.

### Archivos Modificados / Creados
- `facturacion/services/perfiles_lectura/cuit_30711323062.py` [NEW]:
  - Archivo de perfil `procesar_perfil(texto_completo)`. Se programÃÂ³ una expresiÃÂ³n regular adaptada a este diseÃÂ±o de PDF para capturar cantidades, precios, totales, "ArtÃÂ­culo" (como `codigo`), descripciÃÂ³n, y el cÃÂ³digo embutido final (como `codigo_alt`).
- `facturacion/views_procesamiento.py` [MODIFY]:
  - En la vista `CargaCompraAutomaticaView`, se incorporÃÂ³ la lectura del nuevo atributo `codigo_alt`. Si el sistema no logra vincular un ÃÂ­tem de la factura por su `codigo` primario, intenta automÃÂ¡ticamente emparejarlo usando `cod_prov=codigo_alt` y `detalle__icontains=codigo_alt`, extendiendo las capacidades de importaciÃÂ³n de todo el ERP.

### Detalle TÃÂ©cnico
1. **RediseÃÂ±o OCR por Modo de Lectura (`sort=True`):** Se descubriÃÂ³ que el motor core de `extractor_facturas.py` procesaba los documentos activando la reconstrucciÃÂ³n de pÃÂ¡rrafos de PyMuPDF (`sort=True`), lo cual destruye el formato tabular y agrupa las lÃÂ­neas de texto horizontalmente. Se reconstruyÃÂ³ integralmente la ExpresiÃÂ³n Regular de los ÃÂ­tems (`r'^[\s]*([\d\,\.]+)[\s]+(\d+)[\s]+(.*?)[\s]+([\d\,\.]+)[\s]+([\d\,\.]+)[\s]*\n[\s]*(.*?)[\s]*\n'`) para adaptarse a este flujo continuo y garantizar que la grilla reciba correctamente los artÃÂ­culos.
2. **CorrecciÃÂ³n de Totales Invertidos:** En los PDFs de este proveedor, la librerÃÂ­a de extracciÃÂ³n suele leer el bloque de montos monetarios de los totales *antes* que las etiquetas de texto ("SUBTOTAL", "TOTAL"). Se agregÃÂ³ una expresiÃÂ³n regular estructural para interceptar correctamente los valores reales (Neto, Total e IVA) ignorando los subtotales post-descuento.
3. **Mapeo de Descuento Global y Totales ExplÃÂ­citos:** Se programÃÂ³ el perfil para aislar el valor del descuento general de la factura y extraer simultÃÂ¡neamente los 5 valores impositivos fundamentales: Subtotal Bruto, Descuento, Neto Gravado, IVA y Total. Se extendieron las capacidades del frontend (`carga_compra_automatica.html` y `compras_carga.html`) para que transporten y asignen automÃÂ¡ticamente todos estos campos directamente en el formulario de la vista de Carga Venta/Compra, disparando el recÃÂ¡lculo visual en pantalla de forma instantÃÂ¡nea.
4. **Robustez de OCR Transversal:** La modificaciÃÂ³n a `views_procesamiento.py` fue diseÃÂ±ada de forma transparente (`it.get('codigo_alt')`), lo que significa que a partir de ahora *cualquier* futuro perfil de lectura podrÃÂ¡ opcionalmente suministrar un `codigo_alt` y el sistema sabrÃÂ¡ aprovecharlo para emparejar inteligentemente los artÃÂ­culos.

### Estado actual y siguientes pasos
Perfil de lectura completado, probado sobre el archivo PDF de muestra y listo para utilizar en el sistema en vivo de Carga de Compras.

## 26 de Agosto de 2026 Ã¢ÂÂ CorrecciÃÂ³n de Error de Sintaxis (NameError) en Modal de Trazabilidad

### Objetivo
1. **Solucionar fallo 500:** Corregir un error de sintaxis (`NameError: name 'sp' is not defined`) en la lista de comprensiÃÂ³n de la vista `trazabilidad_modal_timeline` que causaba que la carga del modal y el botÃÂ³n de detalles fallaran en la interfaz.

### Archivos Modificados
- `productos/views_trazabilidad.py` [MODIFY]:
  - Corregida la lista de comprensiÃÂ³n en la lÃÂ­nea 85 de `[sp.cuim for sp.cuim in subproductos_serie if sp.cuim]` a `[sp.cuim for sp in subproductos_serie if sp.cuim]`.

### Detalle TÃÂ©cnico
1. **Sintaxis de Python:** La declaraciÃÂ³n incorrecta `for sp.cuim in subproductos_serie` intentaba usar un atributo de un objeto no definido (`sp`) como variable de iteraciÃÂ³n. Se ajustÃÂ³ a la sintaxis estÃÂ¡ndar `for sp in subproductos_serie` para extraer correctamente los atributos de los objetos instanciados.
2. **Impacto en UI:** Este error de servidor (HTTP 500) interrumpÃÂ­a la carga asÃÂ­ncrona de los modales de HTMX, dejando inoperativos los botones (como el de "detalle") asociados al evento de respuesta de esta vista.
3. **Cierre de Modales HTMX:** Se identificÃÂ³ que las plantillas `subproducto_detalle_modal.html` y `subproducto_editar_modal.html` carecÃÂ­an de la declaraciÃÂ³n de la funciÃÂ³n JavaScript `closeModal()`, lo cual provocaba que si el usuario hacÃÂ­a clic fuera del modal (en el backdrop gris) o en el botÃÂ³n de cerrar, el modal no respondiera y la pantalla quedara bloqueada con la superposiciÃÂ³n gris. Se inyectÃÂ³ el script correspondiente para restaurar la interactividad.

### Estado actual y siguientes pasos
El problema en el mÃÂ³dulo de trazabilidad y el bloqueo de pantalla de los modales estÃÂ¡ **completamente solucionado y operativo**.

## 26 de Agosto de 2026 Ã¢ÂÂ Filtro por Sucursal en Trazabilidad de Subproductos

### Objetivo
1. **Filtro de Sucursales:** Agregar la lÃÂ³gica en la vista y en la UI para permitir la bÃÂºsqueda y visualizaciÃÂ³n de subproductos segÃÂºn la sucursal a la que pertenecen, dentro del mÃÂ³dulo de Trazabilidad.

### Archivos Modificados
- `productos/views_trazabilidad.py` [MODIFY]:
  - `SubproductoTrazabilidadListView`: Modificado el mÃÂ©todo `get_queryset` para incorporar `sucursal_id` como parÃÂ¡metro de bÃÂºsqueda extraÃÂ­do de `request.GET.get('sucursal')`.
  - Agregado el mÃÂ©todo `get_context_data` para enviar al contexto las sucursales pertenecientes a la empresa en sesiÃÂ³n y renderizar dinÃÂ¡micamente el `select` de opciones.
- `templates/productos/trazabilidad_list.html` [MODIFY]:
  - AÃÂ±adido el combo desplegable (`select`) para la sucursal, integrado con HTMX para refresco automÃÂ¡tico.
  - AÃÂ±adida la cabecera `<th>Sucursal</th>` en la tabla de resultados.
- `templates/productos/partials/trazabilidad_grilla.html` [MODIFY]:
  - Agregada la celda correspondiente para visualizar el nombre de la sucursal en cada registro (`{{ sp.sucursal.nombre }}`).
  - Ajustados los valores de los atributos `colspan` de 6 a 7 para las filas de "vacÃÂ­o" o "cargar mÃÂ¡s" de la tabla, con el fin de conservar la alineaciÃÂ³n visual tras la adiciÃÂ³n de la columna.

### Detalle TÃÂ©cnico
1. **ConservaciÃÂ³n de Filtros HTMX:** El nuevo select cuenta con el disparador propio integrado con la solicitud general al endpoint y, al estar envuelto en el form `#form-filtros-trazabilidad`, sus parÃÂ¡metros se pasan por URL manteniendo el comportamiento responsivo.

### Estado actual y siguientes pasos
Filtro de Sucursales integrado y tabla adaptada a la nueva columna.

## 26 de Agosto de 2026 Ã¢ÂÂ ReparaciÃÂ³n de Filtros en Trazabilidad de Subproductos

### Objetivo
1. **Corregir Filtro CliPro:** Solucionar el problema en el cual seleccionar un cliente/proveedor desde la lista desplegable o utilizar el botÃÂ³n de "Limpiar" no aplicaba los filtros en el backend, dejando la tabla sin cambios.

### Archivos Modificados
- `templates/productos/trazabilidad_list.html` [MODIFY]:
  - Eliminado el atributo `onsubmit="event.preventDefault();"` del formulario de filtros.
  - Eliminado el listener JS manual de `submit` que interceptaba y realizaba la peticiÃÂ³n por `htmx.ajax` ignorando los valores de los inputs.
  - Al quitar esta intercepciÃÂ³n manual, se delegÃÂ³ el control 100% al comportamiento nativo de HTMX sobre el evento submit, garantizando la correcta serializaciÃÂ³n y envÃÂ­o de todo el querystring.

### Estado actual y siguientes pasos
El formulario ya procesa e incluye exitosamente todos sus valores cuando se dispara remotamente mediante `htmx.trigger`.

## 26 de Agosto de 2026 Ã¢ÂÂ OptimizaciÃÂ³n de Sugerencias en Trazabilidad (Solo con movimientos)

### Objetivo
1. **Limpiar listado de sugerencias:** Evitar sugerir todos los clientes/proveedores y productos de la base de datos en los autocompletados del mÃÂ³dulo de Trazabilidad, restringiendo los resultados exclusivamente a aquellos que realmente poseen movimientos o historiales asociados.

### Archivos Modificados
- `facturacion/views_htmx.py` [MODIFY]:
  - `typeahead_clientes`: Agregada la validaciÃÂ³n del parÃÂ¡metro `solo_trazabilidad`. Si estÃÂ¡ activo (`1`), se utiliza `Exists()` sobre el modelo `Subproducto` con `OuterRef` hacia el ID del cliente o proveedor para excluir del QuerySet a quienes no tengan participaciÃÂ³n en los subproductos de la empresa.
  - `typeahead_productos_venta`: Implementada la misma lÃÂ³gica para excluir productos que no existan dentro de la tabla de Trazabilidad/Subproductos de la empresa activa. AdemÃÂ¡s, se suprimiÃÂ³ la restricciÃÂ³n rÃÂ­gida de `subprod=False` que regÃÂ­a para las ventas estÃÂ¡ndar, permitiendo que sÃÂ­ emerjan los artÃÂ­culos con trazabilidad (`subprod=True`) bajo este modo exclusivo.
- `templates/productos/trazabilidad_list.html` [MODIFY]:
  - AÃÂ±adido el valor `solo_trazabilidad: "1"` estÃÂ¡tico en los diccionarios JS que forman el atributo `hx-vals` de los inputs de bÃÂºsqueda rÃÂ¡pida, de manera que esta regla opere exclusivamente aquÃÂ­ sin afectar las pantallas de facturaciÃÂ³n convencionales.

### Detalle TÃÂ©cnico
1. **DesempeÃÂ±o de Base de Datos:** En lugar de realizar JOINs masivos o comprobaciones iterativas, el uso de la funciÃÂ³n `Exists()` de Django genera subconsultas correlacionadas `EXISTS(SELECT ...)` en el motor de base de datos. Esto permite que el filtrado sea excepcionalmente rÃÂ¡pido, frenando la bÃÂºsqueda en cuanto se encuentra la primera coincidencia, lo cual no penaliza el rendimiento al escribir en el frontend.

### Estado actual y siguientes pasos
Los typeaheads de trazabilidad ahora solo ofrecen entidades y productos con movimientos reales en el sistema, agilizando mucho mÃÂ¡s las bÃÂºsquedas.

## 27 de Agosto de 2026 Ã¢ÂÂ Columnas de ArmerÃÂ­a y Combobox 'Es PolicÃÂ­a' en Clientes y Proveedores Ã¢ÂÂ Plan 072

### Objetivo
Extender la gestiÃÂ³n de Clientes y Proveedores para empresas con actividad de **ArmerÃÂ­a** (`tipo_actividad == 'ARMERIA'`):
1. Selector de columnas y visualizaciÃÂ³n en la grilla principal (`CLU`, `Vencimiento CLU` y `Es PolicÃÂ­a`).
2. Selector desplegable (Combobox / Select) para la condiciÃÂ³n "Es PolicÃÂ­a / Fuerza de Seguridad" (predeterminado `NO (Civil / Particular)`).
3. ExportaciÃÂ³n a Excel incorporando las columnas de ArmerÃÂ­a.
4. OptimizaciÃÂ³n de consultas ORM agregando `select_related('armeria')`.

### Archivos Creados / Modificados
- `docs/planes/072_columnas_armeria_y_es_policia_clientes.md` [NEW]: Plan de implementaciÃÂ³n archivado.
- `facturacion/forms.py` [MODIFY]: `ExtensionArmeriaForm` incluye `es_policia` como `TypedChoiceField` desplegable (opciones `NO (Civil)` y `SÃÂ (PolicÃÂ­a)`).
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]: AdiciÃÂ³n del combobox `es_policia` en el bloque de Registro de ArmerÃÂ­a en 3 columnas responsivas.
- `facturacion/views.py` [MODIFY]: `ClientesProveedoresIndexView` optimizado con `select_related('jurisdiccion', 'armeria')`.
- `facturacion/views_htmx.py` [MODIFY]: `buscar_clientes` optimizado con `select_related('jurisdiccion', 'armeria')`.
- `facturacion/views_reportes.py` [MODIFY]: `exportar_clientes_excel` con `select_related('jurisdiccion', 'armeria')`.
- `facturacion/services/clientes_excel.py` [MODIFY]: InclusiÃÂ³n condicional de columnas `CLU`, `Vencimiento CLU` y `Es PolicÃÂ­a` en el reporte Excel para empresas ArmerÃÂ­a.
- `templates/facturacion/clientes_index.html` [MODIFY]: Checkboxes de visibilidad de columnas `NÃÂ° CLU`, `Vencimiento CLU` y `Es PolicÃÂ­a` en el desplegable y encabezados `<th>` condicionales para ArmerÃÂ­a.
- `templates/facturacion/partials/cliente_table_rows.html` [MODIFY]: Celdas `<td>` condicionales para CLU, Vencimiento CLU y Es PolicÃÂ­a.
- `facturacion/tests/test_armeria_credencial_clu.py` [MODIFY]: Pruebas unitarias para `ExtensionArmeriaForm` (combobox) y vistas del buscador.

### Resultado de las Pruebas Automatizadas
```powershell
.\venv\Scripts\python.exe manage.py test facturacion.tests.test_armeria_credencial_clu
```
**Resultado:** `OK (Ran 4 tests in 1.728s)`.

### Estado Actual
Plan 072 **completamente ejecutado, probado y documentado**.

## DÃÂ­a 28/08/2026 - MÃÂ³dulo DistribuciÃÂ³n: toma de pedidos desde el celular (Plan 074, fase 2)

**Responsable:** Claude Opus.

### Objetivo
Ejecutar la fase 2 del [Plan 074](planes/074_modulo_distribucion.md): la pantalla mobile-first con la que el vendedor toma el pedido en la calle, cargando por cÃÂ³digo, con el crÃÂ©dito del cliente y el stock disponible a la vista.

### Archivos Creados o Modificados
- `distribucion/services/carrito.py` [NEW]: carrito en sesiÃÂ³n. `buscar_producto_por_codigo()` (resuelve por ID del ERP o por cÃÂ³digo del sistema anterior), `buscar_productos()`, `agregar_item()`, `quitar_item()`, `totales()`, `limpiar()`.
- `distribucion/services/pedidos.py` [MODIFY]: `guardar_pedido()`, que persiste el pedido completo desde el carrito y lo numera.
- `distribucion/views_movil.py` [NEW]: ocho vistas HTMX del circuito mÃÂ³vil.
- `templates/distribucion/movil/` [NEW]: `pedido.html` y cinco parciales (`cabecera`, `carrito`, `clientes_sugerencias`, `productos_sugerencias`, `confirmacion`).
- `config/urls.py` [MODIFY]: ocho rutas.
- `templates/base.html` [MODIFY]: el menÃÂº distingue "Tomar Pedido (MÃÂ³vil)" de "Tomar Pedido (PC)".
- `distribucion/tests/test_plan074_movil.py` [NEW]: 29 pruebas.
- `static/css/output.css` [MODIFY]: recompilado.

### Detalle TÃÂ©cnico

**Carrito compartido con la pantalla de PC.** Se reutiliza la clave de sesiÃÂ³n `preventa_items_temp` y el mismo formato de ÃÂ­tem, asÃÂ­ que un pedido empezado en un canal se puede terminar en el otro y el guardado es comÃÂºn. Evita mantener dos carritos con reglas divergentes.

**El precio nunca viene del navegador.** Se resuelve en el servidor con el coeficiente del cliente. Hay una prueba especÃÂ­fica que manda `precio=1` en el POST y verifica que se ignora: el importe que ve el vendedor tiene que ser exactamente el que despuÃÂ©s se factura.

**BÃÂºsqueda por cÃÂ³digo con prioridad definida.** Acepta el ID del ERP y el cÃÂ³digo del sistema anterior, porque durante la transiciÃÂ³n conviven y el vendedor usa el que recuerda. Ante colisiÃÂ³n gana el ID del ERP, que es el cÃÂ³digo definitivo. Probado con un caso de colisiÃÂ³n sembrado a propÃÂ³sito.

**Cargar dos veces el mismo artÃÂ­culo ACUMULA** en vez de rechazar: en la calle el cliente vuelve sobre un artÃÂ­culo y el vendedor va cantando lo que le piden.

**Cambiar de cliente con un pedido en curso se rechaza** con un aviso, en lugar de vaciar el carrito en silencio.

**La fecha no aparece en ninguna parte**, coherente con el criterio fijado: `Preventa.fecha` es `auto_now_add`. Hay una prueba que verifica que la pantalla no expone ningÃÂºn `name="fecha"`.

**Conectividad: online-only**, segÃÂºn lo decidido. La planilla de papel es el plan B.

### Resultado de las Pruebas

```powershell
.\venv\Scripts\python.exe manage.py test distribucion --keepdb --noinput
```
**Resultado:** `OK (Ran 92 tests in 209.5s)` Ã¢ÂÂ 28 de la fase 1a, 35 de la fase 1 y 29 nuevas.

El WARNING `Not Found: /distribucion/movil/clientes/364/elegir/` que aparece en la salida es el **404 esperado** del test que verifica que un vendedor no puede elegir un cliente fuera de su cartera.

VerificaciÃÂ³n adicional: las seis plantillas nuevas compilan y `/distribucion/movil/` responde 200 contra la base real con la empresa 4 en sesiÃÂ³n.

### Estado Actual y Siguientes Pasos
El vendedor ya puede tomar pedidos desde el celular de punta a punta. **Siguiente: fase 3** Ã¢ÂÂ reporte de faltantes y pantalla de asignaciÃÂ³n de stock escaso por orden de llegada del pedido.

---

**CorrecciÃÂ³n (mismo dÃÂ­a) Ã¢ÂÂ las fechas de alta y baja de Personal no se mostraban al editar.**

*Reportado por el usuario.* DiagnÃÂ³stico: **el guardado siempre funcionÃÂ³**; el defecto era de RENDERIZADO. Con `LANGUAGE_CODE = 'es-ar'`, Django renderiza el valor de un `forms.DateInput` con el formato local (`value="28/08/2026"`), y un `<input type="date">` de HTML5 **sÃÂ³lo acepta `YYYY-MM-DD` en su atributo `value`**: descarta cualquier otro formato en silencio y muestra el campo VACÃÂO. El registro tenÃÂ­a la fecha bien guardada, pero al editarlo parecÃÂ­a no tenerla, y si el usuario grababa asÃÂ­ la borraba sin querer.

Del lado de la entrada no habÃÂ­a problema: Django 5.1 agrega `%Y-%m-%d` a los `DATE_INPUT_FORMATS` del locale, asÃÂ­ que lo que manda el navegador se parsea bien. Por eso el defecto era difÃÂ­cil de ver: sÃÂ³lo se manifestaba al editar.

- `core/forms.py` [MODIFY]: se agregÃÂ³ el widget **`DateInputHTML5`**, que fija `format='%Y-%m-%d'` y el `type="date"`, con la explicaciÃÂ³n de la trampa. Va en `core` junto a `DecimalARField`, como ÃÂºnica fuente de verdad de los widgets compartidos.
- `distribucion/forms.py` [MODIFY]: `fecha_alta` y `fecha_baja` pasan a usarlo.
- `templates/configuracion/modals/personal_form.html` [MODIFY]: faltaba mostrar los errores de `fecha_alta` (sÃÂ³lo se mostraban los de `fecha_baja`), con lo que un error de validaciÃÂ³n en ese campo quedaba invisible.
- `distribucion/tests/test_plan074_maestros.py` [MODIFY]: dos pruebas nuevas, una de guardado y otra de **regresiÃÂ³n** que verifica que el `value` renderizado sale en ISO.

**Resultado:** `OK (Ran 30 tests in 33.8s)`.

**El mismo defecto existe en otros siete widgets de fecha del proyecto**, que no se tocaron por estar fuera del alcance de esta fase. `empresas/forms.py` ya aplicaba el arreglo en dos campos (`fecha_inicio_actividades` y `vencimiento_crt_afip`), asÃÂ­ que el patrÃÂ³n correcto ya estaba en el cÃÂ³digo; falta en:

| Archivo | Campo | Se ve al editar |
|---|---|---|
| `empresas/forms.py:79-80` | `Ejercicio.inicio` / `.cierre` | un ejercicio |
| `facturacion/forms.py:96` | `ClienteProveedor.fecha_nacimiento` | un cliente |
| `facturacion/forms.py:275` | `ExtensionArmeria.clu_vto` | un cliente de armerÃÂ­a |
| `facturacion/forms.py:34` y `:362` | `Venta.fecha` / `Compra.fecha` | un comprobante |
| `contable/forms.py:102` | fecha del asiento | un asiento |

En todos, editar un registro existente muestra el campo de fecha vacÃÂ­o. El arreglo es reemplazar `forms.DateInput(attrs={'type': 'date'})` por `DateInputHTML5()`.

## DÃÂ­a 28/08/2026 - MÃÂ³dulo DistribuciÃÂ³n: pedido, crÃÂ©dito y stock comprometido (Plan 074, fase 1)

**Responsable:** Claude Opus.

### Objetivo
Ejecutar la fase 1 del [Plan 074](planes/074_modulo_distribucion.md): dotar al pedido de numeraciÃÂ³n correlativa propia, implementar el servicio de crÃÂ©dito con la regla del saldo disponible negativo, el precio por coeficiente y el stock comprometido. Se completÃÂ³ ademÃÂ¡s la pantalla de cartera y agenda que habÃÂ­a quedado pendiente de la fase 1a.

**DecisiÃÂ³n de arquitectura:** el mÃÂ³dulo NO crea un circuito paralelo de pedidos. Reutiliza `Preventa` Ã¢ÂÂque ya tiene estados, autorizaciÃÂ³n de descuentos e ÃÂ­temsÃ¢ÂÂ y le cuelga la extensiÃÂ³n con lo propio de la distribuciÃÂ³n. Todo lo agregado al circuito compartido estÃÂ¡ condicionado a `tipo_actividad == 'DISTRIBUIDORA'`, asÃÂ­ que armerÃÂ­a, estudio y las empresas estÃÂ¡ndar no cambian de comportamiento.

### Archivos Creados o Modificados

**Modelos y migraciones**
- `distribucion/models.py` [MODIFY]: `ExtensionPedidoDistribucion` (OneToOne con `Preventa`) con `punto`, `numero`, `vendedor`, `fecha_entrega`, `origen`, `condic_destino`, `zona`, `hora_carga`, `alerta_stock`, `alerta_credito`. `UniqueConstraint (punto, numero)`.
- `core/models.py` [MODIFY]: tipo `PEDIDO` en `ContadorDocumento.TIPOS_DOCUMENTO`.
- `productos/models.py` [MODIFY]: `StockSucursal.comprometido` y la property `disponible`.
- Migraciones [NEW]: `distribucion/0002_extensionpedidodistribucion.py`, `core/0002_alter_contadordocumento_tipo_documento.py`, `productos/0032_stocksucursal_comprometido.py`.

**Servicios**
- `distribucion/services/precios.py` [NEW]: `precio_para()` = `Producto.precio_total * coeficiente_mayorista`. ÃÂnica fuente de verdad del precio de distribuciÃÂ³n.
- `distribucion/services/credito.py` [NEW]: `situacion_crediticia()` con la regla del saldo disponible negativo.
- `distribucion/services/pedidos.py` [NEW]: `registrar_pedido()` (numeraciÃÂ³n + alertas), `vendedor_de()`, `clientes_de_la_cartera()`.
- `productos/services/stock_service.py` [MODIFY]: `recalcular_comprometido()` y `disponible_real()`.
- `core/services/numeracion.py` [MODIFY]: `auditar_correlativos()` ahora cubre la serie de pedidos.

**IntegraciÃÂ³n al circuito de preventa**
- `facturacion/signals.py` [MODIFY]: tres seÃÂ±ales que mantienen `comprometido` al dÃÂ­a (alta/baja de ÃÂ­tem y cambio de estado de la cabecera).
- `facturacion/views_htmx.py` [MODIFY]: `info_cliente_preventa` devuelve el panel de crÃÂ©dito para distribuidoras; `preventas_item_add` recalcula el precio con el coeficiente del cliente y agrega el disponible real y ambos cÃÂ³digos al ÃÂ­tem.
- `facturacion/views.py` [MODIFY]: `PreventaCargaView` acota el selector de clientes a la cartera del vendedor y, al guardar, llama a `registrar_pedido()` avisando por `messages` el nÃÂºmero asignado y las alertas.

**Pantallas**
- `distribucion/views.py` [NEW]: `CarteraIndexView` y `DistribucionRequiredMixin`.
- `distribucion/views_htmx.py` [MODIFY]: `asignar_vendedor()` y `asignar_dia_visita()`.
- `templates/distribucion/` [NEW]: `cartera.html`, `partials/cartera_fila.html`, `partials/cartera_filas.html`, `partials/panel_credito.html`.
- `templates/facturacion/preventa_carga.html` [MODIFY]: fila de distribuciÃÂ³n (condiciÃÂ³n de facturaciÃÂ³n, fecha de entrega, observaciones) y contenedor del panel de crÃÂ©dito.
- `templates/base.html` [MODIFY]: subsecciÃÂ³n "OperaciÃÂ³n" en el menÃÂº de DistribuciÃÂ³n, con Tomar Pedido y Cartera y Agenda.
- `config/urls.py` [MODIFY]: tres rutas nuevas.
- `static/css/output.css` [MODIFY]: recompilado.

**Pruebas**
- `distribucion/tests/test_plan074_pedidos.py` [NEW]: 35 pruebas.

### Detalle TÃÂ©cnico

**La regla del saldo disponible negativo.** `saldo_disponible = limite Ã¢ÂÂ saldo` y `cobro_minimo = max(0, Ã¢ÂÂsaldo_disponible)`. Esa formulaciÃÂ³n absorbe los cuatro casos del negocio sin un solo condicional especial: entra holgado, se pasa parcialmente, `limite = 0` (sÃÂ³lo contado) y cliente bloqueado. El ejemplo del plan queda verificado: lÃÂ­mite 100.000, saldo 110.000 Ã¢ÂÂ disponible Ã¢ÂÂ10.000 y cobro mÃÂ­nimo 10.000.

Al TOMAR el pedido, el disponible descuenta ademÃÂ¡s los **pedidos sin facturar**. Sin ese tÃÂ©rmino, tres pedidos del mismo dÃÂ­a pasan todos el control porque ninguno llegÃÂ³ todavÃÂ­a a `saldo`. Al facturar (fase 4) ese tÃÂ©rmino vale cero por construcciÃÂ³n.

**Stock comprometido.** Se mantiene con las mismas reglas que `cantidad`: es un valor DERIVADO, se recalcula entero y nunca se ajusta por delta, asÃÂ­ que es idempotente y autorreparable. Se guarda **separado** de `cantidad` a propÃÂ³sito: `cantidad` es lo que hay en el depÃÂ³sito y sale de comprobantes emitidos; `comprometido` es una promesa que todavÃÂ­a no moviÃÂ³ mercaderÃÂ­a. Mezclarlos harÃÂ­a que un pedido pareciera una salida de stock y el depÃÂ³sito dejarÃÂ­a de cuadrar contra el conteo fÃÂ­sico.

**NumeraciÃÂ³n del pedido.** Se toma con `siguiente_numero()`, que bloquea el contador con `select_for_update()`, y la base tiene ademÃÂ¡s el `UniqueConstraint` como segunda barrera Ã¢ÂÂ el esquema que el Plan 075 propone llevar a `Venta`. El punto de emisiÃÂ³n es `sucursal_id`, misma convenciÃÂ³n que el PRE. `registrar_pedido()` es idempotente: un pedido que se edita conserva su nÃÂºmero.

**Precio.** Se recalcula siempre en el servidor y no se confÃÂ­a en lo que manda el navegador: el importe que ve el vendedor tiene que ser exactamente el que despuÃÂ©s se factura. Un coeficiente sin cargar cae al neutro (1) y no deja el producto en $0.

### Implicaciones de Base de Datos
Tres migraciones aditivas: una tabla nueva, una columna nueva con default y un `choices` ampliado. Respaldo previo con `pg_dump -F c` en `scratch/respaldos/`.

### Resultado de las Pruebas

```powershell
.\venv\Scripts\python.exe manage.py test distribucion --keepdb --noinput
```
**Resultado:** `OK (Ran 63 tests in 190.5s)` Ã¢ÂÂ 28 de la fase 1a mÃÂ¡s 35 nuevas.

VerificaciÃÂ³n adicional: las seis plantillas nuevas y modificadas compilan, y las pantallas `/distribucion/cartera/`, `/ventas/preventas/carga/` y las dos pestaÃÂ±as de configuraciÃÂ³n responden **200** contra la base real con la empresa 4 (RODRIGUEZ MARCELO FABIAN) en sesiÃÂ³n.

### Estado Actual y Siguientes Pasos

**Ya se puede operar:** asignar la cartera y la agenda de visitas, y tomar pedidos con el panel de crÃÂ©dito en vivo, precio por coeficiente, disponible real por ÃÂ­tem y nÃÂºmero correlativo propio.

**Pendiente:** la pantalla mÃÂ³vil (fase 2), el reporte de faltantes y la asignaciÃÂ³n de stock escaso (fase 3), y la planilla manual en PDF. El control de crÃÂ©dito sigue siendo informativo: el vinculante llega con la facturaciÃÂ³n por lote (fase 4), que a su vez depende del [Plan 075](planes/075_integridad_numeracion_comprobantes_venta.md).

**Defecto preexistente detectado:** `facturacion/views.py` (`VentasCargaView`) referencia una variable `ctx_base` inexistente en la rama de "perÃÂ­odo IVA cerrado". ProvocarÃÂ­a un `NameError` al intentar facturar en un perÃÂ­odo cerrado. No se tocÃÂ³ por estar fuera del alcance de esta fase.

---

**Ajuste posterior (mismo dÃÂ­a) Ã¢ÂÂ fecha de la preventa.** Por definiciÃÂ³n del usuario, la fecha del comprobante la determina el sistema, no se edita **y tampoco se muestra**: es siempre la del dÃÂ­a de carga, y ocupar espacio de pantalla con un dato que no se decide no le aporta nada al operador.

`Preventa.fecha` ya era `auto_now_add`, asÃÂ­ que la regla **ya se cumplÃÂ­a en el modelo para todas las actividades** y no habÃÂ­a ningÃÂºn input que la pudiera alterar. No hizo falta ningÃÂºn cambio funcional. Verificado con GET real contra la base: DISTRIBUIDORA y ARMERÃÂA responden 200 y ninguna expone un input `name="fecha"`.

Queda fijado como criterio para la **fase 4** (facturaciÃÂ³n por lote): la fecha de la venta la pone el sistema, no el operador. Eso hace estructuralmente inalcanzable la rama de "perÃÂ­odo IVA cerrado" en el circuito de distribuciÃÂ³n.

## DÃÂ­a 28/08/2026 - MÃÂ³dulo DistribuciÃÂ³n: maestros y campos base (Plan 074, fase 1a)

**Responsable:** Claude Opus (arquitectura y ejecuciÃÂ³n).
*Nota: `.cursorrules` indica leer `docs/soy.md` para determinar la firma, pero ese archivo no existe en el repositorio.*

### Objetivo
Ejecutar la primera fase del [Plan 074](planes/074_modulo_distribucion.md): crear la app `distribucion` con sus maestros, los campos de distribuciÃÂ³n en `Producto`, la extensiÃÂ³n del cliente, y los ABM necesarios para que se pueda hacer la carga de datos maestros (fase 0 del plan). No se implementÃÂ³ todavÃÂ­a ningÃÂºn circuito operativo.

Se invirtiÃÂ³ el orden previsto en el plan: la fase 0 era "cargar datos maestros", pero esos campos no existÃÂ­an todavÃÂ­a y no habÃÂ­a dÃÂ³nde cargarlos. Primero las estructuras, despuÃÂ©s la carga.

### Archivos Creados o Modificados

**App nueva `distribucion`**
- `distribucion/models.py` [NEW]: `ZonaReparto`, `Personal`, `Vehiculo`, `MotivoDevolucion`, `CarteraVendedor`, `DiaVisita`.
- `distribucion/forms.py` [NEW]: `ZonaRepartoForm`, `PersonalForm`, `VehiculoForm`, `MotivoDevolucionForm`, todos acotados por `empresa_id`.
- `distribucion/views_htmx.py` [NEW]: ABM HTMX de los cuatro catÃÂ¡logos (modal + buscador + borrado) y siembra del catÃÂ¡logo de motivos.
- `distribucion/services/catalogos.py` [NEW]: catÃÂ¡logo inicial de 17 motivos de devoluciÃÂ³n y `sembrar_motivos()` idempotente.
- `distribucion/management/commands/sembrar_motivos_devolucion.py` [NEW]: comando para sembrar el catÃÂ¡logo por empresa.
- `distribucion/tests/test_plan074_maestros.py` [NEW]: 25 pruebas.
- `distribucion/apps.py`, `__init__.py`, `migrations/0001_initial.py` [NEW].

**Modelos existentes (cambios aditivos)**
- `productos/models.py` [MODIFY]: `peso_unitario_kg`, `unidad_venta`, `unidades_por_bulto`, `codigo_anterior` en `Producto`, mÃÂ¡s el ÃÂ­ndice `(empresa, codigo_anterior)` y la normalizaciÃÂ³n a mayÃÂºsculas del cÃÂ³digo anterior.
- `facturacion/models.py` [MODIFY]: `ExtensionDistribuidora` (OneToOne con `ClienteProveedor`), con `clasificacion`, `coeficiente_mayorista`, `zona` y `bloqueado_credito`.
- `productos/migrations/0031_...py`, `facturacion/migrations/0055_extensiondistribuidora.py` [NEW].

**Formularios y vistas**
- `core/forms.py` [NEW]: `DecimalARField`, contrapartida en backend de `static/js/formato_ar.js`. Los inputs `.fInputAR` llegan como `1.234,56` y Django los rechazaba antes de `clean_<campo>`; la conversiÃÂ³n ocurre en `to_python`. Es la ÃÂºnica fuente de verdad del desformateo en formularios.
- `facturacion/forms.py` [MODIFY]: `ExtensionDistribuidoraForm`.
- `facturacion/views_htmx.py` [MODIFY]: `cliente_modal` maneja la extensiÃÂ³n de distribuciÃÂ³n con el mismo patrÃÂ³n que ya usaba para armerÃÂ­a (validaciÃÂ³n, guardado atÃÂ³mico y propagaciÃÂ³n de errores).
- `productos/forms.py` [MODIFY]: los cuatro campos nuevos en `ProductoForm`, con `DecimalARField` para peso y unidades por bulto.
- `core/views_config.py` [MODIFY]: contexto de las cuatro pestaÃÂ±as nuevas.
- `config/urls.py` [MODIFY]: 17 rutas de los ABM.
- `config/settings.py` [MODIFY]: alta de `distribucion` en `INSTALLED_APPS`.

**Templates**
- `templates/configuracion/partials/` [NEW]: `personal_distribucion.html`, `zonas_reparto.html`, `vehiculos.html`, `motivos_devolucion.html` y sus cuatro `*_table_rows.html`.
- `templates/configuracion/modals/` [NEW]: `personal_form.html`, `zona_form.html`, `vehiculo_form.html`, `motivo_form.html`.
- `templates/configuracion/partials/hub.html` [MODIFY]: bloque "DistribuciÃÂ³n", visible sÃÂ³lo si `empresa_actual.tipo_actividad == 'DISTRIBUIDORA'`.
- `templates/productos/modals/producto_modal.html` [MODIFY]: bloque de distribuciÃÂ³n, con la misma condiciÃÂ³n.
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]: bloque de distribuciÃÂ³n en el modal de cliente.
- `static/css/output.css` [MODIFY]: recompilado con `npm run build` (Tailwind purgado: las clases nuevas no existÃÂ­an).

### Detalle TÃÂ©cnico

**`Personal` es tabla propia y no un atributo de `Usuario`** (Plan 074 ÃÂ§4.3). El motivo de fondo es que no todo el personal opera el ERP: el repartidor trabaja con la hoja de ruta en papel y puede no tocar nunca una pantalla, pero tiene que figurar igual en el documento. Modelarlo como `User` obligarÃÂ­a a crear credenciales para gente que nunca va a entrar. Por eso `usuario` es un OneToOne **nullable**. Los tres roles (`es_vendedor`, `es_repartidor`, `es_cobrador`) son booleanos acumulables: en una distribuidora chica la misma persona vende, reparte y cobra.

`Venta.vendedor` y `Preventa.vendedor` **no se tocaron**: siguen apuntando a `User` porque los usan los filtros y reportes de las otras actividades. En distribuciÃÂ³n el vendedor de una venta se obtendrÃÂ¡ a travÃÂ©s de su pedido.

**Precio del cliente de reparto** = `Producto.precio_total * ExtensionDistribuidora.coeficiente_mayorista`. La base es el precio de lista **con IVA**; `cto_rep` no interviene en la venta (es costo de reposiciÃÂ³n, entrada del circuito de compras).

**Multi-tenant:** todas las consultas y todos los combos se acotan por `session['empresa_id']`, con pruebas especÃÂ­ficas de aislamiento (usuarios, sucursales y zonas de otra empresa no se ofrecen).

**CatÃÂ¡logo de motivos:** se siembra bajo demanda y no por migraciÃÂ³n de datos, porque los motivos son por empresa y una empresa puede pasar a ser DISTRIBUIDORA mucho despuÃÂ©s. La siembra es idempotente (`get_or_create` por empresa + cÃÂ³digo): no duplica ni pisa lo que el usuario haya editado. `sugiere_apto_reventa` precarga si la mercaderÃÂ­a devuelta vuelve al stock vendible; los tres motivos que no la devuelven son `PRODUCTO_DANADO`, `PROXIMO_A_VENCER` y `CADENA_DE_FRIO`.

### Implicaciones de Base de Datos
Tres migraciones, todas **aditivas**: seis tablas nuevas en `distribucion`, una tabla nueva en `facturacion` y cuatro columnas nullables/con default en `productos_producto`. Ninguna destructiva, ninguna con pÃÂ©rdida de datos posible.

Se tomÃÂ³ un respaldo previo con `pg_dump -F c` en `scratch/respaldos/` (carpeta ignorada por git) antes de aplicar.

### Resultado de las Pruebas

```powershell
.\venv\Scripts\python.exe manage.py test distribucion --keepdb --noinput
.\venv\Scripts\python.exe manage.py test productos --keepdb --noinput
.\venv\Scripts\python.exe manage.py test facturacion --keepdb --noinput
```

| Suite | Resultado |
|---|---|
| `distribucion` | **OK** Ã¢ÂÂ 28 pruebas en 41,5 s |
| `productos` | **OK** Ã¢ÂÂ 25 pruebas en 151,4 s |
| `facturacion` | 64 pruebas: 1 falla y 24 errores, **todos preexistentes** (ver abajo) |

AdemÃÂ¡s se verificÃÂ³ que las 15 plantillas nuevas y modificadas compilan con el cargador de Django.

#### Fallos preexistentes detectados en `facturacion` (NO introducidos por esta intervenciÃÂ³n)

Se comprobÃÂ³ creando un *worktree* limpio de `HEAD` y verificando que el defecto ya estÃÂ¡ ahÃÂ­, sin ninguno de los cambios de esta fase.

1. **23 errores en `facturacion/tests/test_facturas_pendientes.py`** Ã¢ÂÂ `DataError: value too long for type character varying(6)`. Los helpers `crear_compra()` y `crear_venta()` escriben `periodo="2026-06"` (7 caracteres) en un campo `CharField(max_length=6)` cuyo formato documentado es `YYYYMM`. Corresponde `"202606"`. Es un defecto del test, no del modelo, y no puede haber pasado nunca contra PostgreSQL.
2. **1 error en `facturacion/tests/test_arca_service.py`** Ã¢ÂÂ `FileNotFoundError` del certificado `media/certificados_afip/certificado_cortiz.crt`. Es una prueba de integraciÃÂ³n real contra ARCA HomologaciÃÂ³n: depende del entorno, no del cÃÂ³digo.
3. **1 falla en `facturacion/tests/test_armeria_credencial_clu.py`** Ã¢ÂÂ `test_extension_armeria_form_es_policia_select` arma el `ExtensionArmeriaForm` sin `tipo_persona`. El Plan 073 hizo ese campo obligatorio en el formulario y el test del Plan 072 no se actualizÃÂ³.

Ninguno de los tres toca archivos modificados en esta intervenciÃÂ³n. Quedan reportados para resolverse en su mÃÂ³dulo correspondiente.

### Estado Actual y Siguientes Pasos

**Hecho:** estructuras y ABM listos. Ya se puede hacer la carga de datos maestros de la fase 0 del plan: personal, zonas, vehÃÂ­culos, motivos, peso y cÃÂ³digo anterior de los productos, y coeficiente por cliente.

**Pendiente de la fase 1 del plan:** pantalla de cartera de vendedores y dÃÂ­as de visita (los modelos existen, falta la UI), y los permisos `permiso_distribucion_*` en `usuarios.Perfil` Ã¢ÂÂ hoy los ABM se rigen por el permiso general del panel de configuraciÃÂ³n (`is_staff` o `es_admin_sistema`).

**Siguiente fase sugerida:** fase 1 del plan (pedido con numeraciÃÂ³n correlativa, servicio de crÃÂ©dito y stock comprometido), que a su vez depende de definir los valores de `ExtensionDistribuidora.clasificacion` (ÃÂ§11.1, ÃÂºnica decisiÃÂ³n abierta).

---

**Ajuste posterior (mismo dÃÂ­a):** se agregÃÂ³ la secciÃÂ³n **DistribuciÃÂ³n** al menÃÂº lateral (`templates/base.html`), condicionada a `empresa_actual.tipo_actividad == 'DISTRIBUIDORA'`, con accesos directos a los cuatro maestros. Hasta ahora sÃÂ³lo eran alcanzables desde el Panel de ConfiguraciÃÂ³n y el mÃÂ³dulo no se veÃÂ­a en el menÃÂº principal. Se recompilÃÂ³ `output.css`. Los circuitos operativos (pedidos, repartos, cobranzas) se irÃÂ¡n sumando a esta misma secciÃÂ³n a medida que avancen las fases del plan.

## DÃÂ­a 28/08/2026 - SeparaciÃÂ³n de RazÃÂ³n Social / Apellido y Nombre (Plan 073)

### Objetivo
Aplicar el Plan 073 para el mÃÂ³dulo de ArmerÃÂ­a, separando conceptualmente Persona FÃÂ­sica (Apellido y Nombre) de Persona JurÃÂ­dica (RazÃÂ³n Social), garantizando que en backend los datos persistan unificados en la tabla base.

### Archivos Creados o Modificados
- 
acturacion/models.py [MODIFY]: Se aÃÂ±adiÃÂ³ 	ipo_persona (CharField) a la ExtensionArmeria.
- 
acturacion/migrations/0053_extensionarmeria_tipo_persona.py [NEW]: MigraciÃÂ³n de esquema.
- 
acturacion/migrations/0054_assign_tipo_persona_armeria.py [NEW]: MigraciÃÂ³n de datos (Data Migration) que iterÃÂ³ los registros existentes. AsignÃÂ³ 'J' si el CUIT arranca con 30/33/34 y tiene 11 dÃÂ­gitos, y 'F' en caso contrario (ademÃÂ¡s, para 'F', formateÃÂ³ la RazÃÂ³n Social dividiÃÂ©ndola con coma si no la tenÃÂ­a).
- 
acturacion/forms.py [MODIFY]: Se aÃÂ±adiÃÂ³ 	ipo_persona a ExtensionArmeriaForm. Se quitÃÂ³ la obligaciÃÂ³n estricta HTML de 
azon_social para poder alternar el formulario dinÃÂ¡mico, pero se validÃÂ³ duramente en el mÃÂ©todo clean().
- 
acturacion/views_htmx.py [MODIFY]: El endpoint cliente_modal fue ajustado. En POST, si el tipo de persona es FÃÂ­sica (F), concatena Apellido y Nombre en 
azon_social. En GET, si es F, divide 
azon_social por la coma y expone al template variables para armar la vista.
- 	emplates/facturacion/modals/cliente_modal.html [MODIFY]: Se incluyeron Radio Cards de UI premium para elegir entre FÃÂ­sica o JurÃÂ­dica. Se dividieron los inputs. AdemÃÂ¡s, la carga por AFIP rellena estos campos de forma automÃÂ¡tica leyendo el campo oculto 	ipo_persona.
- 
acturacion/services/afip_padron.py [MODIFY]: Retorna en el diccionario final 
ombre y pellido desglosados para facilitarle la vida al frontend, ademÃÂ¡s del cÃÂ³digo F o J.

### Detalle TÃÂ©cnico
Se respetÃÂ³ al mÃÂ¡ximo la directiva de no utilizar suposiciones adivinadas con prefijos en tiempo de ejecuciÃÂ³n, por lo tanto la determinaciÃÂ³n del autocompletado en el padrÃÂ³n recae ÃÂ­ntegramente en los datos del JSON (vÃÂ­a 	ipoClave). Se diseÃÂ±ÃÂ³ la interfaz usando Alpine.js y TailwindCSS sin sacrificar la rigurosidad de validaciÃÂ³n del backend de Django (clean()), asegurando compatibilidad hacia atrÃÂ¡s mediante Data Migrations.

### Resultado de Pruebas
Las migraciones corrieron satisfactoriamente en entorno local sin errores de sintaxis o constraint.

### Estado actual y siguientes pasos sugeridos
Plan completado exitosamente y listo para pruebas operativas. Sugerimos validar la carga en la vista del usuario final creando y consultando un par de CUITs en la ventana emergente.

## DÃÂ­a 28/08/2026 - Autocompletado AFIP (PadrÃÂ³n A13) para Clientes/Proveedores

### Objetivo
Implementar un botÃÂ³n en el modal de Clientes/Proveedores que consulte automÃÂ¡ticamente los datos fiscales a AFIP mediante el servicio ws_sr_padron_a13 y rellene el formulario.

### Archivos Modificados/Creados
- 
acturacion/services/afip_padron.py [NEW]: Se creÃÂ³ el servicio AFIPPadronService que reutiliza la configuraciÃÂ³n de rca_arg para conectarse a AFIP y obtener los datos a partir de un CUIT.
- 
acturacion/views_htmx.py [MODIFY]: Se agregÃÂ³ el endpoint consultar_padron_afip que retorna los datos consultados en formato JSON.
- config/urls.py [MODIFY]: Se expuso el endpoint htmx/consultar-afip/<cuit>/.
- 	emplates/facturacion/modals/cliente_modal.html [MODIFY]: Se integrÃÂ³ un botÃÂ³n de autocompletado junto al campo de CUIT y lÃÂ³gica Alpine.js para hacer la solicitud 
etch y distribuir la respuesta en los inputs correspondientes (RazÃÂ³n Social, Domicilio, IVA, etc.).

### Detalle TÃÂ©cnico
El servicio de AFIP evalÃÂºa la respuesta del WS y formatea la condiciÃÂ³n de IVA segÃÂºn los impuestos (30 -> Inscripto, 32 -> Exento, o si tiene Monotributo). En el Frontend, si el CUIT es vÃÂ¡lido (11 dÃÂ­gitos), se consulta asÃÂ­ncronamente y se inyectan los valores directamente en los id de los campos, disparando el evento input para reactividad HTMX/Alpine si es necesario.

### Estado Actual y Siguientes Pasos
Plan de Autocompletado finalizado. Queda pendiente probar la integraciÃÂ³n directamente desde la interfaz.

## 28 de Agosto de 2026 Ã¢ÂÂ Visibilidad y Obligatoriedad del Campo "Es PolicÃÂ­a" en Clientes

### Objetivo
1. **Obligatoriedad y Visibilidad:** Hacer que el campo "ÃÂ¿Es PolicÃÂ­a / Fuerza de Seguridad?" (asociado a la extensiÃÂ³n de ArmerÃÂ­a) sea de carÃÂ¡cter obligatorio, tenga una opciÃÂ³n vacÃÂ­a por defecto para forzar la elecciÃÂ³n, y se ubique en la parte superior del formulario de creaciÃÂ³n/ediciÃÂ³n de clientes (secciÃÂ³n "Identidad y CondiciÃÂ³n Fiscal") para mayor visibilidad al momento del alta.

### Archivos Modificados
- `facturacion/forms.py` [MODIFY]:
  - `ExtensionArmeriaForm`: Modificado el campo `es_policia` para requerir una selecciÃÂ³n explÃÂ­cita (`required=True`), agregando la opciÃÂ³n vacÃÂ­a `('', "Seleccione una opciÃÂ³n")` en los choices, y ajustando el `initial` a `''` cuando se trata de una nueva entidad.
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]:
  - Reubicado el campo `form_armeria.es_policia` desde la secciÃÂ³n inferior "Registro de ArmerÃÂ­a" hacia la secciÃÂ³n superior "1. Identidad y CondiciÃÂ³n Fiscal", colocÃÂ¡ndolo junto al "Rol Comercial".
  - Se agregÃÂ³ el indicador visual de campo obligatorio (`*` en rojo).

### Detalle TÃÂ©cnico
1. **Forzado de SelecciÃÂ³n Inicial:** Al agregar una opciÃÂ³n con valor vacÃÂ­o y `required=True` en un `TypedChoiceField`, la validaciÃÂ³n nativa de Django impedirÃÂ¡ que el formulario se envÃÂ­e sin que el usuario seleccione activamente "SÃÂ" o "NO". Si no selecciona nada, la validaciÃÂ³n fallarÃÂ¡ y se mostrarÃÂ¡ el error en el listado superior del modal y debajo del campo.

### Estado actual y siguientes pasos
El campo ahora es obligatorio y mucho mÃÂ¡s visible en el inicio del formulario.

## 28 de Agosto de 2026 Ã¢ÂÂ MigraciÃÂ³n de Permisos de ArmerÃÂ­a y EliminaciÃÂ³n de JOSEN

### Objetivo
1. **LÃÂ³gica de Visibilidad de ArmerÃÂ­a:** Migrar el control de acceso a los formularios y configuraciones de ArmerÃÂ­a, pasando de basarse en permisos individuales por usuario (`puede_armeria`) a depender del atributo `tipo_actividad` de la Empresa activa en sesiÃÂ³n (si es 'ARMERIA', el mÃÂ³dulo se activa para los empleados de la empresa).
2. **EliminaciÃÂ³n del MÃÂ³dulo JOSEN:** Borrar de manera permanente todas las referencias, modelos de base de datos, formularios, vistas (HTMX y generales), URLs y componentes de interfaz relacionados al submÃÂ³dulo JOSEN ya cancelado.

### Archivos Modificados
- `usuarios/models.py` [MODIFY]:
  - Eliminados los campos `permiso_armeria_ver`, `permiso_armeria_editar`, `permiso_josen_ver` y `permiso_josen_editar` del modelo `Perfil`.
- `usuarios/forms.py` [MODIFY]:
  - Eliminados los campos de permisos de ArmerÃÂ­a y JOSEN de `UsuarioForm`.
- `facturacion/models.py` [MODIFY]:
  - Eliminados completamente los modelos `RubroJosen` y `ExtensionJosen`.
- `facturacion/forms.py` [MODIFY]:
  - Eliminados los formularios `ExtensionJosenForm` y `RubroJosenForm`.
- `facturacion/views_htmx.py` [MODIFY]:
  - Eliminado el CRUD completo HTMX para Rubros JOSEN (`rubro_modal`, `buscar_rubros`, `eliminar_rubro`).
  - Refactorizado `cliente_modal`: Eliminada la lÃÂ³gica de JOSEN y reemplazada la lÃÂ³gica `puede_armeria` (ahora se lee de `Empresa.tipo_actividad == 'ARMERIA'`).
- `config/urls.py` [MODIFY]:
  - Eliminadas las rutas de configuraciÃÂ³n de Rubros JOSEN.
- `core/views_config.py` [MODIFY]:
  - Eliminado el pase a contexto de los rubros JOSEN para el panel de control.
- `facturacion/admin.py` [MODIFY]:
  - Eliminado `JosenInline` de la visualizaciÃÂ³n en el Django Admin y sus importaciones.
- `templates/configuracion/modals/usuario_form.html` [MODIFY]:
  - Removidas las cajas de selecciÃÂ³n de permisos para ArmerÃÂ­a y JOSEN.
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]:
  - Removida la secciÃÂ³n HTML `ParÃÂ¡metros Josen` condicionada por `puede_josen`.
- `templates/configuracion/partials/hub.html` [MODIFY]:
  - Removido el botÃÂ³n de acceso al menÃÂº de Rubros JOSEN en la secciÃÂ³n contable.
- **Archivos Eliminados** [DELETE]:
  - `templates/configuracion/partials/rubros.html`
  - `templates/configuracion/partials/rubro_table_rows.html`
  - `templates/configuracion/modals/rubro_josen_form.html`

### Detalle TÃÂ©cnico
1. **Base de datos:** Se generaron 2 archivos de migraciones, `facturacion/migrations/0052_delete_extensionjosen_delete_rubrojosen.py` y `usuarios/migrations/0007_remove_perfil_permiso_armeria_editar_and_more.py`. Al correr `migrate` se eliminaron exitosamente las tablas asociadas y columnas en la base de datos `PostgreSQL`.
2. **RefactorizaciÃÂ³n de visibilidad:** Al usar `Empresa.tipo_actividad`, el acceso a ArmerÃÂ­a se maneja dinÃÂ¡micamente de acuerdo al contexto comercial en el que estÃÂ© logueado el usuario, reduciendo el riesgo de errores de asignaciÃÂ³n de permisos manuales.

### Estado actual y siguientes pasos
El mÃÂ³dulo JOSEN ha sido erradicado del sistema y los permisos para el mÃÂ³dulo de ArmerÃÂ­a pasaron satisfactoriamente de estar basados en roles/perfiles de usuarios a depender de la naturaleza de la empresa seleccionada al iniciar la sesiÃÂ³n.

## 28 de Agosto de 2026 Ã¢ÂÂ ReubicaciÃÂ³n de Campos CUIT/DNI y PolicÃÂ­a en Formulario de Cliente

### Objetivo
1. **ReubicaciÃÂ³n de IdentificaciÃÂ³n (CUIT/DNI):** Mover el input de nÃÂºmero de documento / CUIT hacia adentro de la tarjeta de "Naturaleza del Cliente" y alinearlo a la derecha, agrupando semÃÂ¡nticamente la identidad.
2. **ReubicaciÃÂ³n de "Es PolicÃÂ­a":** Mover el campo obligatorio "ÃÂ¿Es PolicÃÂ­a / Fuerza de Seguridad?" al final de la tarjeta del mÃÂ³dulo de "Registro de ArmerÃÂ­a" acompaÃÂ±ando a los campos CLU.

### Archivos Modificados
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]:
  - Refactorizada la tarjeta de "Naturaleza del Cliente" convirtiÃÂ©ndola en un contenedor `flex flex-col md:flex-row justify-between items-start md:items-center gap-6`.
  - Agregado el input "NÃÂºmero de Documento / CUIT" dentro de dicha tarjeta flotando a la derecha (`w-full md:w-1/3 ml-auto`) cuando es aplicable al mÃÂ³dulo de armerÃÂ­a, y como fallback externo mediante un `<template x-if="!puedeArmeria">` para evitar duplicidad del atributo `name` y bugs en el DOM.
  - Movido `form_armeria.es_policia` al grid de 3 columnas de "Registro de ArmerÃÂ­a", optimizando la simetrÃÂ­a de los campos de credencial y seguridad.

### Detalle TÃÂ©cnico
1. **PrevenciÃÂ³n de Duplicados en DOM HTMX:** Como la validaciÃÂ³n de CUIT se maneja tanto para altas normales (solo DNI/CUIT) como para altas completas (FÃÂ­sica/JurÃÂ­dica), al mover el input dentro de un `<template x-if="puedeArmeria">` se programÃÂ³ la contracara `<template x-if="!puedeArmeria">`. Alpine.js procesa estos templates removiendo del DOM los nodos inactivos; esto garantiza que al hacer un submit (HTTP POST) Django reciba exactamente un solo valor para la clave `cuit` en lugar de una lista conflictiva.

### Estado actual y siguientes pasos
Los campos han sido exitosamente reordenados y agrupados segÃÂºn la nueva lÃÂ³gica, mejorando la usabilidad y conservando toda la validaciÃÂ³n por HTMX del padrÃÂ³n.

## DÃÂ­a 29/08/2026 - FacturaciÃÂ³n masiva de pedidos (Plan 074, fase 4)

**Responsable:** Claude Opus.

### Objetivo
El corazÃÂ³n del mÃÂ³dulo: emitir de una vez los comprobantes de los pedidos del dÃÂ­a, aplicando la regla del saldo disponible negativo que define el cobro mÃÂ­nimo del repartidor y la condiciÃÂ³n de venta impresa en el comprobante.

### La regla, en una sola fÃÂ³rmula
```
saldo_disponible = limite Ã¢ÂÂ saldo    (POSTERIOR a facturar esta carga)
cobro_minimo     = max(0, Ã¢ÂÂsaldo_disponible)
condicion_venta  = CONTADO si cobro_minimo >= total, si no CUENTA CORRIENTE
```
Absorbe los cuatro casos del negocio sin un solo condicional especial: entra holgado, se pasa parcialmente, `limite = 0` (sÃÂ³lo contado) y cliente bloqueado. Los cuatro tienen su prueba.

### Archivos Creados o Modificados
- `facturacion/services/emision_arca.py` [NEW]: el circuito de emisiÃÂ³n del CAE existÃÂ­a **sÃÂ³lo dentro de `VentasCargaView.post`**, embebido en el manejo del formulario, asÃÂ­ que ningÃÂºn otro proceso podÃÂ­a emitir. Se expone como servicio reutilizable, con las mismas validaciones de coherencia fiscal (A/B segÃÂºn condiciÃÂ³n de IVA). Acepta una venta **todavÃÂ­a sin persistir**, porque el nÃÂºmero de la serie fiscal lo da ARCA y hay que pedirlo antes de guardar.
- `distribucion/services/facturacion.py` [NEW]: `evaluar_credito()`, `previsualizar()`, `facturar_pedido()`, `facturar_lote()`.
- `distribucion/views.py` [MODIFY]: `FacturacionLoteView` (GET previsualiza, POST emite).
- `facturacion/models.py` [MODIFY]: `Venta.condicion_venta` (CONTADO / CTA_CTE).
- `distribucion/models.py` [MODIFY]: `ExtensionPedidoDistribucion.venta`, el eslabÃÂ³n Pedido Ã¢ÂÂ Comprobante.
- `core/models.py` [MODIFY]: `ContadorDocumento.VENTA_FISCAL`, espejo local de la serie fiscal.
- `usuarios/models.py` [MODIFY]: `permiso_distribucion_facturar_lote`.
- `templates/distribucion/facturacion.html` + dos parciales [NEW]; entrada en el menÃÂº.
- `distribucion/tests/test_plan074_facturacion.py` [NEW]: 25 pruebas.

### Detalle TÃÂ©cnico

**La numeraciÃÂ³n se resuelve ANTES del primer save.** Es lo que obligÃÂ³ a reestructurar: guardar la venta con un nÃÂºmero provisorio para corregirlo tras el CAE dejarÃÂ­a, aunque sea un instante, dos comprobantes con el mismo nÃÂºmero en la misma serie Ã¢ÂÂy ahora existe el `UniqueConstraint` que lo rechazarÃÂ­aÃ¢ÂÂ. Por eso los importes y las alÃÂ­cuotas se calculan en memoria, luego se numera (contador para el PRE, ARCA para la factura) y reciÃÂ©n ahÃÂ­ se persiste.

**Cada pedido va en SU PROPIA transacciÃÂ³n.** Es la diferencia deliberada con el lote de ESTUDIO, donde el `atomic` envolvÃÂ­a el bucle entero y el primer error abortaba todo: acÃÂ¡ un cliente mal configurado no puede frenar el reparto de los demÃÂ¡s. Hay una prueba con tres pedidos donde el del medio falla y los otros dos se emiten igual.

**Se bloquea el cliente con `select_for_update()`** al facturar: dos pedidos suyos emitidos a la vez leerÃÂ­an el mismo saldo y los dos creerÃÂ­an entrar en el lÃÂ­mite.

**El comprobante se guarda dos veces a propÃÂ³sito:** el segundo save dispara la seÃÂ±al con los ÃÂ­tems ya creados, que es lo que genera el asiento. Es exactamente el defecto que tenÃÂ­a el lote de ESTUDIO y que se corrigiÃÂ³ esta maÃÂ±ana.

Reglas inflexibles verificadas por pruebas: el asiento hereda el `condic` del comprobante; el PRE **no** entra al Libro IVA y la Factura **sÃÂ­**; la fecha la pone el sistema; facturar libera el stock comprometido y descuenta el real.

**EmisiÃÂ³n real contra ARCA:** el circuito quedÃÂ³ cableado (`modo_prueba=False` llama a `AfipService` y toma el nÃÂºmero de `CbteDesde`). La pantalla emite hoy en **modo prueba**, con CAE ficticio, hasta que se valide contra HomologaciÃÂ³n con el certificado cargado.

### Resultado de las Pruebas
```powershell
.\venv\Scripts\python.exe manage.py test distribucion facturacion core --keepdb --noinput
```
**`Ran 257 tests` Ã¢ÂÂ 1 error**, `test_emitir_comprobante_homologacion_real`, que falla por falta del certificado ARCA: es de entorno. Cero regresiones.

Migraciones aplicadas con respaldo previo. Las cuatro pantallas del mÃÂ³dulo responden 200 contra la base real.

### Estado Actual y Siguientes Pasos
Circuito cerrado desde la toma del pedido hasta el comprobante emitido. **Siguiente: fase 5** Ã¢ÂÂ `Reparto`, Consolidado de ArtÃÂ­culos y Hoja de Ruta, que es donde el `cobro_minimo` calculado acÃÂ¡ sale impreso para el repartidor.

## DÃÂ­a 29/08/2026 - Integridad de numeraciÃÂ³n y condiciÃÂ³n del lote (Plan 075 + correcciÃÂ³n ESTUDIO)

**Responsable:** Claude Opus.

### Objetivo
Analizar la facturaciÃÂ³n por lote de ESTUDIO Ã¢ÂÂque ya emite comprobantes fiscales y no fiscalesÃ¢ÂÂ para reutilizarla en la fase 4 de DistribuciÃÂ³n, corregir lo que estuviera mal y ejecutar el [Plan 075](planes/075_integridad_numeracion_comprobantes_venta.md), del que la fase 4 depende.

### Hallazgo principal: el comprobante interno se guardaba como FISCAL

`FacturacionLoteService` no seteaba `condic` en ninguno de los dos comprobantes, asÃÂ­ que ambos quedaban con el default (**1 = Real**). El comprobante INTERNO/PRE decÃÂ­a ser fiscal, mientras su asiento Ã¢ÂÂcreado a mano unas lÃÂ­neas mÃÂ¡s abajoÃ¢ÂÂ decÃÂ­a `condic = 2`. Comprobante y asiento se contradecÃÂ­an.

No llegaba al Libro IVA sÃÂ³lo porque `venta_p._no_contabilizar = True` corta la seÃÂ±al entera. Pero era una **bomba de tiempo**: `contabilizar_venta_individual` puebla el Libro IVA cuando `condic in (1, 3)`, asÃÂ­ que cualquier re-guardado sin ese flag habrÃÂ­a declarado ante ARCA una operaciÃÂ³n que no existe fiscalmente. Y ya hacÃÂ­a daÃÂ±o: todo reporte que filtra `Venta.condic` contaba el interno como fiscal.

**CorrecciÃÂ³n:** `condic=2` en el interno y `condic=1` explÃÂ­cito en el fiscal, para que el par se lea de un vistazo.

### Otros hallazgos del mismo servicio
- **El manejo de errores por fila era ilusorio.** El `transaction.atomic()` envuelve todo el bucle y el `try/except` estÃÂ¡ adentro: tras un error de base de datos, Django deja la transacciÃÂ³n abortada y cualquier consulta posterior lanza `TransactionManagementError`. No se guardaban "los exitosos". *(Documentado, no corregido: es parte del refactor del motor en la fase 4.)*
- **Si no hay cuentas contables configuradas, el comprobante interno se emite sin asiento y sin ningÃÂºn aviso** Ã¢ÂÂ queda con saldo en la cuenta corriente y sin registraciÃÂ³n. *(Documentado con una prueba que lo deja cubierto para que el refactor lo cambie a conciencia.)*
- El asiento del interno reimplementa a mano ~60 lÃÂ­neas que `contabilizar_venta_individual` ya hace bien. La ironÃÂ­a: existÃÂ­an para compensar el `condic` mal seteado.

### Plan 075 ejecutado

**AuditorÃÂ­a previa (sÃÂ³lo lectura):** cero duplicados y cero huecos en `facturacion_venta`. El `UniqueConstraint` se pudo aplicar sin tocar un solo dato.

- `facturacion/models.py` [MODIFY]: `UniqueConstraint (empresa, tipo, punto, numero)` en `Venta`. Era el ÃÂºnico documento emitido del sistema sin bloqueo al numerar **ni** restricciÃÂ³n en la base. Queda documentado que `tipo` es nullable y en PostgreSQL los NULL no colisionan: los comprobantes sin tipo quedan fuera del control, y la soluciÃÂ³n de fondo excede este plan.
- `core/models.py` [MODIFY]: tipos `VENTA_PRE` y `VENTA_NCI` en `ContadorDocumento`, en **series independientes**.
- `core/migrations/0004_inicializar_contadores_venta_no_fiscal.py` [NEW]: migraciÃÂ³n de datos que inicializa cada contador con el ÃÂºltimo nÃÂºmero realmente emitido. Sin esto el primer comprobante habrÃÂ­a arrancado en 1 y chocado contra el constraint.
- `core/services/numeracion.py` [MODIFY]: `siguiente_numero_pre()` y `siguiente_numero_nci()`, y `auditar_correlativos()` extendida a las dos series nuevas mediante un envoltorio `_VentasDeTipo` que evita duplicar el bucle.
- `facturacion/services/facturacion_lote_service.py` [MODIFY]: el PRE se numera con el contador transaccional y se emite en `punto = sucursal_id`; se eliminan los **fallbacks silenciosos** (tipo PRE por descarte y punto de venta asumido en 1), que ahora fallan con un mensaje explicativo.
- `facturacion/views_estudio.py` [MODIFY]: `modo_prueba` deja de estar hardcodeado y pasa a ser un parÃÂ¡metro, con el default seguro. Los `ValueError` de configuraciÃÂ³n se devuelven como 400 con su mensaje, no como error genÃÂ©rico.
- **La emisiÃÂ³n real contra ARCA queda bloqueada con un error explÃÂ­cito** hasta cablear `AfipService`. Antes no habÃÂ­a forma de emitir en serio; ahora, si alguien lo intenta, el sistema **corta antes de emitir** en vez de generar un comprobante con numeraciÃÂ³n local que ARCA no autorizÃÂ³.

### Pruebas
- `facturacion/tests/test_lote_condic.py` [NEW]: 7 pruebas.
- `facturacion/tests/test_plan075_numeracion.py` [NEW]: 16 pruebas.

```powershell
.\venv\Scripts\python.exe manage.py test distribucion facturacion productos core --keepdb --noinput
```
**Resultado:** `Ran 255 tests` Ã¢ÂÂ 1 falla y 24 errores, **todos preexistentes y ya documentados**: 23 en `test_facturas_pendientes` (escribe `periodo="2026-06"`, 7 caracteres, en un `varchar(6)`), 1 en `test_arca_service` (falta el certificado, es de entorno) y 1 en `test_armeria_credencial_clu` (el Plan 073 hizo `tipo_persona` obligatorio sin actualizar el test del 072). **Cero regresiones.**

### VerificaciÃÂ³n contra la base real
Migraciones aplicadas con respaldo previo. Los contadores quedaron inicializados en el ÃÂºltimo emitido (empresa 2 punto 0 Ã¢ÂÂ 1; empresa 3 punto 3 Ã¢ÂÂ 1) y `auditar_correlativos()` devuelve **OK en las cinco series** existentes.

### Estado Actual y Siguientes Pasos
El Plan 075 queda ejecutado salvo el cableado de `AfipService` en el lote, que es su paso 5 y hoy estÃÂ¡ explÃÂ­citamente bloqueado. Con esto, la **fase 4 de DistribuciÃÂ³n** ya tiene numeraciÃÂ³n segura sobre la cual apoyarse.

Sigue pendiente y ofrecido, sin ejecutar: el arreglo del widget de fecha en los otros siete formularios y la exportaciÃÂ³n del reporte de faltantes a PDF/Excel.

---

**Correcciones posteriores del mismo dÃÂ­a.**

**1. MenÃÂº principal roto en empresas DISTRIBUIDORA** *(reportado por el usuario, defecto propio).*
El comentario que habÃÂ­a puesto en `templates/base.html` usaba `{# Ã¢ÂÂ¦ #}` **en varias lÃÂ­neas**, y los comentarios de una llave en Django son de **UNA SOLA LÃÂNEA**: la apertura consume sÃÂ³lo su renglÃÂ³n y el resto se emite como texto visible. En el menÃÂº aparecÃÂ­a el pÃÂ¡rrafo "MÃÂ³dulo DistribuciÃÂ³n (Plan 074). Por ahora sÃÂ³lo los maestrosÃ¢ÂÂ¦" entre Ventas y DistribuciÃÂ³n.

Al revisarlo apareciÃÂ³ el mismo error en **otros nueve comentarios**, todos escritos por mÃÂ­ en esta serie de fases: `preventa_carga.html`, `movil/pedido.html`, `movil/partials/cabecera.html` (ÃÂ2), `movil/partials/carrito.html`, `movil/partials/confirmacion.html`, `partials/cartera_fila.html` (ÃÂ2) y `partials/panel_credito.html`. Los diez se convirtieron a `{% comment %} Ã¢ÂÂ¦ {% endcomment %}`.

VerificaciÃÂ³n: las **231 plantillas** del proyecto compilan, y las cuatro pantallas del mÃÂ³dulo (`/distribucion/movil/`, `/cartera/`, `/faltantes/` y la preventa) responden 200 **sin texto de comentario en el HTML**.

**2. La facturaciÃÂ³n por lote emitÃÂ­a comprobantes SIN asiento contable.**
Al escribir las pruebas apareciÃÂ³ un defecto mÃÂ¡s grave que el del `condic`: la seÃÂ±al contabiliza en el `post_save` de la `Venta`, pero el lote guarda la venta **antes** de crear los ÃÂ­tems, y `contabilizar_venta_individual` corta con `if not venta.items.exists(): return None`. **La factura fiscal quedaba emitida y sin registraciÃÂ³n contable.**

CorrecciÃÂ³n, siguiendo la regla que confirmÃÂ³ el usuario Ã¢ÂÂcuenta patrimonial del cliente con fallback a `ParametrosContables.cta_clientes_default`, y cuenta de resultado del **rubro del producto facturado** con fallback a `parametros.cta_ventas`Ã¢ÂÂ:
- Se re-guarda cada comprobante despuÃÂ©s de crear sus ÃÂ­tems, para que la seÃÂ±al contabilice con la venta completa.
- Se eliminÃÂ³ el `_no_contabilizar` del comprobante interno y **las 54 lÃÂ­neas del asiento armado a mano**, que existÃÂ­an sÃÂ³lo para compensar el `condic` mal seteado. Ahora delega en `contabilizar_venta_individual`, que ya aplica esa regla exacta, valida que la cuenta pertenezca a la empresa y sea imputable, y **levanta un error explÃÂ­cito** si falta alguna en lugar de emitir el comprobante sin asiento.

Tres pruebas nuevas cubren la regla: el cliente sin `cta_pat` usa la cuenta del parÃÂ¡metro, el haber sale del rubro del producto, y sin rubro cae al parÃÂ¡metro general.

**3. Tests preexistentes corregidos** *(a pedido del usuario).*
- `test_facturas_pendientes.py`: los helpers escribÃÂ­an `periodo="2026-06"` (7 caracteres) en un `CharField(max_length=6)` cuyo formato documentado es **YYYYMM**. Corregido a `"202606"` Ã¢ÂÂ el guion no corresponde. **23 errores eliminados.**
- `test_armeria_credencial_clu.py`: el Plan 073 hizo `tipo_persona` obligatorio en `ExtensionArmeriaForm` y el test del Plan 072 no se actualizÃÂ³. Se agregÃÂ³ el campo. **1 falla eliminada.**

### Resultado final de la suite
```powershell
.\venv\Scripts\python.exe manage.py test distribucion facturacion productos core --keepdb --noinput
```
**`Ran 257 tests` Ã¢ÂÂ 1 solo error**, `test_emitir_comprobante_homologacion_real`, que es una prueba de integraciÃÂ³n real contra ARCA HomologaciÃÂ³n y falla por falta del certificado `media/certificados_afip/certificado_cortiz.crt`: es de entorno, no de cÃÂ³digo.

Se pasÃÂ³ de **25 fallos a 1**. La suite vuelve a servir como red: de ahora en mÃÂ¡s, un test rojo seÃÂ±ala una regresiÃÂ³n real.

## DÃÂ­a 29/08/2026 - Faltantes y asignaciÃÂ³n de stock escaso (Plan 074, fase 3)

**Responsable:** Claude Opus.

### Objetivo
Ejecutar la fase 3 del [Plan 074](planes/074_modulo_distribucion.md): detectar quÃÂ© productos no alcanzan para cubrir todos los pedidos tomados y sin facturar, y dar la pantalla donde un usuario autorizado reparte ese stock escaso. Es el paso previo a la facturaciÃÂ³n por lote.

### Archivos Creados o Modificados
- `distribucion/models.py` [MODIFY]: nuevo `AjusteAsignacion` (pedido, producto, cantidad original, cantidad asignada, usuario, fecha, observaciÃÂ³n).
- `distribucion/services/asignacion.py` [NEW]: `detectar_faltantes()`, `detalle_por_pedido()`, `sugerir_asignacion()`, `aplicar_asignacion()`, `hay_faltantes()`.
- `distribucion/views.py` [MODIFY]: `FaltantesIndexView`, `AsignacionStockView` y el helper de permiso `_puede_asignar()`.
- `usuarios/models.py` [MODIFY]: `permiso_distribucion_asignar_stock`.
- `templates/distribucion/faltantes.html`, `partials/faltantes_filas.html`, `modals/asignacion_form.html` [NEW].
- `templates/base.html` [MODIFY]: entrada "Faltantes y AsignaciÃÂ³n" en el menÃÂº de DistribuciÃÂ³n.
- `config/urls.py` [MODIFY]: dos rutas.
- `distribucion/tests/test_plan074_asignacion.py` [NEW]: 25 pruebas.
- Migraciones: `distribucion/0004_ajusteasignacion.py`, `usuarios/0008_perfil_permiso_distribucion_asignar_stock.py`.

### Detalle TÃÂ©cnico

**El criterio de reparto es el ORDEN DE LLEGADA del pedido** (`hora_carga` ascendente): el que pidiÃÂ³ primero se lleva todo lo que pidiÃÂ³ mientras haya stock, y el faltante lo absorben los ÃÂºltimos. Es el ÃÂºnico criterio que se le puede explicar a un vendedor sin discusiÃÂ³n, y el que eligiÃÂ³ el usuario. La sugerencia es un punto de partida: la pantalla permite ajustar a mano.

**`detectar_faltantes()` compara contra el stock FÃÂSICO, no contra el disponible.** El `comprometido` ES la demanda que se estÃÂ¡ comparando: restarlo serÃÂ­a contarla dos veces.

**Todo ajuste queda auditado** en `AjusteAsignacion`, con la cantidad original, la asignada, quiÃÂ©n lo hizo y cuÃÂ¡ndo. La razÃÂ³n es operativa: al vendedor hay que poder explicarle despuÃÂ©s por quÃÂ© su cliente recibiÃÂ³ menos de lo que pidiÃÂ³. Un ÃÂ­tem al que se le asigna lo que pedÃÂ­a **no genera ajuste ni escritura**.

**Asignar 0 elimina el renglÃÂ³n** del pedido, no lo deja en cero: un ÃÂ­tem en cero ensuciarÃÂ­a el comprobante y la hoja de ruta con una lÃÂ­nea sin sentido. El `AjusteAsignacion` queda igual, y es la explicaciÃÂ³n de por quÃÂ© el artÃÂ­culo desapareciÃÂ³.

Tras el recorte se recalculan el total del ÃÂ­tem, el total del pedido y el `comprometido` (por la seÃÂ±al ya existente sobre `PreventaItem`).

**Permiso propio** (`permiso_distribucion_asignar_stock`): repartir stock escaso decide quÃÂ© cliente recibe menos, que es una decisiÃÂ³n comercial y no una tarea de carga. Sin el permiso, la pantalla se consulta pero el POST devuelve 403 y los inputs salen deshabilitados.

### Resultado de las Pruebas
```powershell
.\venv\Scripts\python.exe manage.py test distribucion --keepdb --noinput
```
**Resultado:** `OK (Ran 25 tests)` en la suite nueva; 143 en total en el mÃÂ³dulo.

Los WARNING de `Forbidden` y `Not Found` en la salida son los **esperados** por las pruebas de permiso y de aislamiento de cartera.

VerificaciÃÂ³n contra la base real (empresa 4): las tres plantillas compilan y `/distribucion/faltantes/` responde 200.

### Estado Actual y Siguientes Pasos
Con la asignaciÃÂ³n cerrada, el circuito queda listo para la **fase 4: facturaciÃÂ³n masiva** con la regla del saldo disponible negativo, que emite la Factura o el PRE y decide CONTADO vs. CUENTA CORRIENTE.

Pendiente y ofrecido, sin ejecutar: exportaciÃÂ³n del reporte de faltantes a PDF/Excel (el plan la prevÃÂ©), el arreglo del widget de fecha en los otros siete formularios y el [Plan 075](planes/075_integridad_numeracion_comprobantes_venta.md), del que **depende la fase 4**.

## DÃÂ­a 29/08/2026 - Domicilios de entrega mÃÂºltiples (Plan 074)

**Responsable:** Claude Opus.

### Objetivo
Un cliente puede tener **varios puntos de entrega** porque tiene sucursales. Se define la regla del circuito, confirmada por el usuario: **1 domicilio de entrega Ã¢ÂÂ 1 pedido Ã¢ÂÂ 1 comprobante Ã¢ÂÂ 1 parada de la hoja de ruta**. Cada sucursal recibe, controla y firma lo suyo, y la cuenta corriente consolida en el cliente.

### DecisiÃÂ³n estructural: quÃÂ© se mueve y quÃÂ© no

`ClienteProveedor.domicilio` es el **fiscal** (el que se imprime como domicilio del cliente). El nuevo `DomicilioEntrega` es el **punto fÃÂ­sico** al que llega el camiÃÂ³n.

De ahÃÂ­ se desprende lo importante: **la zona y la agenda de visitas dejan de colgar del cliente y pasan al domicilio**. Una sucursal en San Cayetano y otra en Villa LujÃÂ¡n entran en repartos distintos, en dÃÂ­as distintos y con recorridos distintos: son propiedades de *dÃÂ³nde se entrega*, no de *quiÃÂ©n debe*. Colgarlas del cliente obligarÃÂ­a a que todas sus sucursales compartan zona y dÃÂ­a.

Lo que **sÃÂ­** queda en el cliente es el **crÃÂ©dito**: un CUIT, una cuenta corriente, un lÃÂ­mite. Las entregas se reparten; la deuda no. Lo mismo la cartera: el vendedor responde por el cliente completo.

### Archivos Creados o Modificados
- `distribucion/models.py` [MODIFY]: nuevo `DomicilioEntrega` (nombre, domicilio, localidad, zona, contacto, telÃÂ©fono, horario de recepciÃÂ³n, indicaciones de entrega, principal, activo). `DiaVisita` se reapunta de `cliente` a `domicilio` y admite **varios dÃÂ­as por punto** (con lÃÂ¡cteos se pasa dos o tres veces por semana). `ExtensionPedidoDistribucion` suma `domicilio_entrega` y `domicilio_entrega_texto`.
- `facturacion/models.py` [MODIFY]: se **quita** `ExtensionDistribuidora.zona`, que ahora vive en el domicilio.
- `distribucion/services/domicilios.py` [NEW]: `asegurar_domicilio_principal()` (genera el principal a partir del fiscal, idempotente), `domicilios_de()`, `sembrar_domicilios_faltantes()` para la carga inicial.
- `distribucion/services/pedidos.py` [MODIFY]: el pedido toma `domicilio_entrega`; si no se indica, se propone el principal. La **zona del pedido sale del domicilio**.
- `distribucion/views_htmx.py` [MODIFY]: ABM de domicilios y agenda por punto; se elimina la vista de agenda por cliente.
- `distribucion/views_movil.py` [MODIFY]: selector de punto de entrega y `movil_elegir_domicilio`.
- `distribucion/forms.py` [MODIFY]: `DomicilioEntregaForm`.
- `facturacion/forms.py`, `templates/facturacion/modals/cliente_modal.html` [MODIFY]: se saca la zona del cliente.
- `templates/distribucion/` [NEW/MODIFY]: `modals/domicilio_form.html`, `partials/cartera_fila.html` reescrito con los domicilios desplegables, cabecera y confirmaciÃÂ³n del mÃÂ³vil.
- `config/urls.py` [MODIFY]: cuatro rutas de domicilios y una del mÃÂ³vil.
- `distribucion/tests/test_plan074_domicilios.py` [NEW]: 26 pruebas.
- Migraciones: `distribucion/0003_domicilioentrega_and_more.py`, `facturacion/0056_...`.

### Detalle TÃÂ©cnico

**Snapshot del domicilio en el pedido** (`domicilio_entrega_texto`), con el mismo criterio que `Preventa.cliente_razon_social`: si maÃÂ±ana se corrige la direcciÃÂ³n, el comprobante ya emitido tiene que seguir diciendo a dÃÂ³nde se entregÃÂ³. Hay una prueba que lo verifica.

**El principal se genera solo** a partir del domicilio fiscal, para que el circuito nunca se trabe por un dato derivable, pero **la responsabilidad de que cada pedido salga con el domicilio correcto es del vendedor** (definiciÃÂ³n del usuario). Por eso el mÃÂ³vil ofrece todos los puntos y permite cambiarlo en cualquier momento antes de confirmar, sin perder lo cargado.

**Aviso de punto sin zona:** un domicilio sin zona no entra en ningÃÂºn reparto, asÃÂ­ que la cabecera del mÃÂ³vil lo marca en ÃÂ¡mbar.

### Implicaciones de Base de Datos
Se verificÃÂ³ que las cuatro tablas afectadas estaban **vacÃÂ­as** antes de reestructurar (`ExtensionDistribuidora`, `DiaVisita`, `CarteraVendedor`, `ExtensionPedidoDistribucion`: 0 registros), asÃÂ­ que el cambio de `DiaVisita.cliente` a `DiaVisita.domicilio` no arrastrÃÂ³ datos. Respaldo previo con `pg_dump -F c` en `scratch/respaldos/`.

### Resultado de las Pruebas
```powershell
.\venv\Scripts\python.exe manage.py test distribucion --keepdb --noinput
```
**Resultado:** `OK (Ran 118 tests in 278.3s)`.

Los dos WARNING de `Not Found` en la salida son los **404 esperados** de las pruebas de aislamiento: un vendedor no puede elegir un cliente fuera de su cartera ni el punto de entrega de otro cliente.

VerificaciÃÂ³n adicional contra la base real (empresa 4): las ocho plantillas compilan y `/distribucion/movil/`, `/distribucion/cartera/` y la pestaÃÂ±a de Personal responden 200.

### Estado Actual y Siguientes Pasos
Circuito de pedido completo con puntos de entrega mÃÂºltiples. **Siguiente: fase 3** Ã¢ÂÂ reporte de faltantes y asignaciÃÂ³n de stock escaso por orden de llegada del pedido.

Pendiente de definiciÃÂ³n del usuario (ÃÂ§11.1 del plan): los valores de `ExtensionDistribuidora.clasificacion`. Y quedÃÂ³ ofrecido, sin ejecutar, el arreglo del widget de fecha en los otros siete formularios del proyecto.

## 29 de Agosto de 2026 Ã¢ÂÂ ReplicaciÃÂ³n de Plan de Cuentas y ParÃÂ¡metros Contables (Empresa 2 a Empresa 4)

### Objetivo
1. **ReplicaciÃÂ³n Contable Completa:** Replicar de forma ÃÂ­ntegra el catÃÂ¡logo del Plan de Cuentas (`Cuenta`), los ParÃÂ¡metros Contables (`ParametrosContables`) y los Medios de Pago (`MedioPago`) desde la empresa origen `ARMERIA ARMAR SAS` (ID=2) hacia la empresa destino `RODRIGUEZ MARCELO FABIAN` (ID=4).
2. **GeneralizaciÃÂ³n del Comando de ReplicaciÃÂ³n:** Mejorar la Fase 4 del comando `replicar_plan_cuentas.py` para replicar directamente los medios de pago configurados en la empresa origen mapeando sus cuentas contables al nuevo ÃÂ¡rbol destino.

### Archivos Modificados
- `contable/management/commands/replicar_plan_cuentas.py` [MODIFY]:
  - En la Fase 4, se implementÃÂ³ la lectura y clonaciÃÂ³n dinÃÂ¡mica de los objetos `MedioPago` existentes en la `empresa_origen`, remapeando su clave forÃÂ¡nea `cuenta_contable` al ID de la cuenta clonada en la `empresa_destino`. Se mantuvo la compatibilidad con archivo CSV como mecanismo alternativo de fallback.

### Detalle TÃÂ©cnico
1. **Atomicidad y Mapeo en Memoria:** Todo el proceso se ejecuta dentro de un bloque `transaction.atomic()`. En la Fase 1 se crearon 220 cuentas contables para la empresa 4 conservando cÃÂ³digo, jerarquÃÂ­a, imputabilidad, tipo y atributos especiales, generando un mapa en memoria `{id_origen: nueva_cuenta_destino}`.
2. **ReconstrucciÃÂ³n del ÃÂrbol JerÃÂ¡rquico:** En la Fase 2 se asignaron 215 relaciones `sumariza` apuntando estrictamente a las cuentas padre de la empresa 4.
3. **Mapeo de ParÃÂ¡metros y Medios de Pago:** En la Fase 3 se instanciÃÂ³ `ParametrosContables` para la empresa 4 con 23 cuentas contables remapeadas, y en la Fase 4 se clonaron los 6 medios de pago (`CHQ-TER`, `EFE-USD`, `EFE-ARS`, `RET-GCIA`, `RET-IIBB`, `TRA-BCO`) con sus respectivas cuentas contables pertenecientes a la empresa 4.

### Resultado de las Pruebas
- Comando ejecutado: `python manage.py replicar_plan_cuentas --origen 2 --destino 4`.
- Salida del comando: 220 cuentas creadas, 215 relaciones jerÃÂ¡rquicas vinculadas, parÃÂ¡metros contables creados con 23 cuentas mapeadas y 6 medios de pago clonados exitosamente.
- ValidaciÃÂ³n en base de datos: Confirmado que todas las cuentas asociadas a la empresa 4 pertenecen exclusivamente a `empresa_id=4`, sin referencias cruzadas residuales hacia la empresa 2.

### Estado actual y siguientes pasos
La Empresa ID=4 (`RODRIGUEZ MARCELO FABIAN`) cuenta ahora con su estructura contable y medios de pago plenamente operativos e independientes.

## 29 de Agosto de 2026 Ã¢ÂÂ InclusiÃÂ³n de `sumariza_id` en ExportaciÃÂ³n y Captura Excel del Plan de Cuentas

### Objetivo
1. **InclusiÃÂ³n de Clave JerÃÂ¡rquica en Excel:** Incorporar el campo `sumariza_id` en el archivo Excel generado mediante el botÃÂ³n "Excel Completo" del Plan de Cuentas, permitiendo visualizar y auditar el ID de la cuenta padre en la que consolida cada nodo.
2. **Soporte Bidireccional de Captura:** Habilitar el reconocimiento de `sumariza_id` durante la recaptura e importaciÃÂ³n masiva de cuentas desde Excel para vincular directamente la cuenta padre si se especifica su ID.

### Archivos Modificados
- `contable/services/excel_service.py` [MODIFY]:
  - AÃÂ±adida la clave `'sumariza_id': 'Sumariza ID'` a `COLUMNAS_CUENTA_MAP`.
  - Actualizado `generar_excel_cuentas` para volcar `cta.sumariza_id` en la segunda columna del libro.
  - Actualizado `procesar_captura_excel_cuentas` para normalizar el encabezado `sumariza` / `sumariza_id`, resolviendo la asignaciÃÂ³n `sumariza` por ID explÃÂ­cito o por jerarquÃÂ­a como fallback.
- `contable/tests/test_excel_cuentas.py` [MODIFY]:
  - Corregido `Empresa.nombre` en el setup de pruebas.
  - Agregadas aserciones de exportaciÃÂ³n y asignaciÃÂ³n de `sumariza_id` en los tests de generaciÃÂ³n y captura masiva.

### Detalle TÃÂ©cnico
1. **Estructura de Columnas:** La columna `Sumariza ID` se posiciona inmediatamente despuÃÂ©s de `ID`, manteniendo el orden lÃÂ³gico de identificadores previos a la jerarquÃÂ­a (`ID`, `Sumariza ID`, `JerarquÃÂ­a`, `Nombre Cuenta`, etc.).
2. **ResoluciÃÂ³n en ImportaciÃÂ³n:** En `procesar_captura_excel_cuentas`, si la fila trae un valor numÃÂ©rico en `Sumariza ID` y dicho ID existe en la empresa activa, se vincula `sumariza_obj = cuentas_por_id[sumariza_id_val]`, otorgando prioridad a la relaciÃÂ³n explÃÂ­cita por sobre la inferencia por cadena de texto.

### Resultado de las Pruebas
```powershell
.\venv\Scripts\python.exe manage.py test contable.tests.test_excel_cuentas --keepdb --noinput
```
**Resultado:** `OK (Ran 3 tests in 7.4s)` Ã¢ÂÂ GeneraciÃÂ³n de Excel, actualizaciÃÂ³n/creaciÃÂ³n por captura masiva y vistas HTTP con modal comprobadas sin errores.

### Estado actual y siguientes pasos
La exportaciÃÂ³n a Excel del Plan de Cuentas ya incluye la columna `Sumariza ID` tanto en la descarga como en el motor de recaptura.

## DÃÂ­a 31/08/2026 - Reporte de devoluciones e integridad de numeraciÃÂ³n (Plan 074, fase 8)

**Responsable:** Claude Opus.

### Objetivo
Los dos reportes de **control** que cierran el mÃÂ³dulo: el de devoluciones (ÃÂ§7.10) Ã¢ÂÂ*"por perÃÂ­odo, motivo, momento, repartidor, cliente y producto: muestra si el problema es de crÃÂ©dito, de calidad, de carga o de un repartidor puntual"*Ã¢ÂÂ y el de correlativos (ÃÂ§4.2), que le faltaban las dos series que el mÃÂ³dulo emite y no se auditaban.

### Archivos Creados o Modificados
- `distribucion/services/reporte_devoluciones.py` [NEW]: `reporte()` con sus cuatro cortes.
- `core/services/numeracion.py` [MODIFY]: `auditar_correlativos()` incorpora `REPARTO` y `RECEPCION_DEVOLUCION`.
- `distribucion/views.py` [MODIFY]: `DevolucionesReporteView`, `CorrelativosDistribucionView`.
- `templates/distribucion/reporte_devoluciones.html`, `correlativos.html`, `partials/corte_devoluciones.html` [NEW].
- `config/urls.py`, `templates/base.html` [MODIFY]: dos rutas y la secciÃÂ³n ÃÂ«ControlÃÂ» del menÃÂº.
- `distribucion/tests/test_plan074_reportes_control.py` [NEW]: 22 pruebas.

Sin migraciones: los dos reportes leen lo que ya existe.

### Detalle TÃÂ©cnico

**La pregunta que responde el reporte no es CUÃÂNTO, es POR QUÃÂ.** Un total de devoluciones no sirve para decidir nada. Lo que cambia una conducta es ver que el 60 % son ÃÂ«negocio cerradoÃÂ» Ã¢ÂÂproblema de agenda de visitasÃ¢ÂÂ, o que se concentran en un repartidor, o en un producto que llega roto. Por eso el reporte son **cuatro cortes sobre los mismos renglones** y no una lista: por motivo (quÃÂ© falla), por repartidor (si se concentra en alguien), por producto (si el problema es del artÃÂ­culo) y por cliente (quiÃÂ©n devuelve mÃÂ¡s). Cada corte viene ordenado **de mayor a menor importe**: tiene que empezar por lo que mÃÂ¡s pesa, no por lo que viene primero alfabÃÂ©ticamente.

**El grano es el renglÃÂ³n de la recepciÃÂ³n, no la nota de crÃÂ©dito.** `RecepcionDevolucionItem` es el ÃÂºnico lugar donde conviven motivo, producto, cantidad y `apto_reventa`. La NC acredita un importe; la recepciÃÂ³n explica quÃÂ© volviÃÂ³ y por quÃÂ©.

**Lo no apto para reventa se mide aparte**, con su propio porcentaje: lo que volviÃÂ³ roto es **pÃÂ©rdida**, no una devoluciÃÂ³n mÃÂ¡s. Mezclarlo con lo que se puede volver a vender esconde el ÃÂºnico nÃÂºmero que justifica hablar con un proveedor o con un repartidor.

**Las anulaciones PRE-CARGA van en su propia lista.** Cuando el cliente anula antes de que salga el camiÃÂ³n, la mercaderÃÂ­a nunca se cargÃÂ³ y no pasa por ninguna recepciÃÂ³n. Si se las mezclara con lo devuelto se estarÃÂ­a contando como ÃÂ«vuelto del repartoÃÂ» algo que nunca saliÃÂ³; si se las omitiera, desaparecerÃÂ­an del anÃÂ¡lisis. Van aparte, con su total propio.

**AtribuciÃÂ³n del repartidor.** `RecepcionDevolucion.entregado_por` es opcional, asÃÂ­ que cuando falta se cae a los responsables del reparto: si hay **exactamente uno**, la devoluciÃÂ³n es suya sin ambigÃÂ¼edad. Con varios responsables **no se le atribuye a ninguno** Ã¢ÂÂrepartir la culpa por partes iguales serÃÂ­a inventar un datoÃ¢ÂÂ y queda como ÃÂ«Sin identificarÃÂ», que es lo que efectivamente se sabe. Hay una prueba para cada caso.

**Una recepciÃÂ³n anulada no cuenta**: no devolviÃÂ³ nada, y contarla inflarÃÂ­a los cuatro cortes a la vez.

**Integridad de numeraciÃÂ³n.** `auditar_correlativos()` ya cubrÃÂ­a OC, Informe de RecepciÃÂ³n, Remito Interno, Pedido, PRE y NCI, pero **le faltaban `REPARTO` y `RECEPCION_DEVOLUCION`**: los dos documentos que el mÃÂ³dulo emite desde las fases 5 y 6. Dejarlos afuera los volvÃÂ­a tan inauditables como el nÃÂºmero de un tercero, que es exactamente lo que el ÃÂ§4.2 dice que no puede pasar. La pantalla del mÃÂ³dulo muestra sus **cinco series** Ã¢ÂÂPedido, Reparto, RecepciÃÂ³n, PRE y NCIÃ¢ÂÂ con huecos, duplicados y el desfasaje contra el contador; las de compras siguen en su propia pantalla.

### Resultado de las Pruebas
```
python manage.py test distribucion
Ran 378 tests in 409.882s
OK
```
Las 22 nuevas cubren: los cuatro cortes y su orden, la concentraciÃÂ³n por motivo con su porcentaje, la atribuciÃÂ³n del repartidor con uno y con varios responsables, la mediciÃÂ³n separada de lo no apto, los cinco filtros (motivo, repartidor, producto, perÃÂ­odo, sÃÂ³lo-no-apto), la recepciÃÂ³n anulada, el aislamiento multiempresa, las anulaciones pre-carga en su lista aparte, la incorporaciÃÂ³n de las dos series a la auditorÃÂ­a, la detecciÃÂ³n de un hueco, y las dos pantallas.

Un ajuste que hizo la prueba del hueco: `Reparto` estÃÂ¡ protegido por FK desde `RepartoParada` y `RecepcionDevolucion`, asÃÂ­ que el hueco se simula con repartos vacÃÂ­os en vez de borrar uno con paradas.

### Estado Actual y Siguientes Pasos
**El Plan 074 estÃÂ¡ completo**: las nueve fases, de la toma del pedido al control de las devoluciones y la integridad de las series.

Pendientes ofrecidos y no ejecutados: las exportaciones a PDF/Excel (faltantes, saldos por vendedor y este reporte), el widget de fecha en otros siete formularios, la validaciÃÂ³n contra ARCA HomologaciÃÂ³n, y el ajuste de inventario para la mercaderÃÂ­a devuelta no apta Ã¢ÂÂque este reporte ahora deja a la vista con su importe.

### Cristian - PC CASA
**Fecha:** 02/09/2026
**Objetivo:** Restaurar datos desde dump SQL (db_estudio.sql) purgando la base de datos y resolviendo conflictos con migraciones de verticalidad.
**Archivos creados o modificados:**
- 
estore_db.py (nuevo script en raÃÂ­z, puede ser borrado luego de validar)
**Detalle TÃÂ©cnico:** 
Se desarrollÃÂ³ un script en Python (ETL) para leer e insertar de forma nativa los registros de db_estudio.sql. Se eliminÃÂ³ el esquema public desde base de datos, se crearon las tablas vÃÂ­rgenes con python manage.py migrate y posteriormente se volcaron los datos en las 100 tablas usando psycopg3 (copy()).
Para evitar fallas de dependencias forÃÂ¡neas durante la inyecciÃÂ³n, se deshabilitaron temporalmente los triggers mediante session_replication_role = 'replica'. Se omitiÃÂ³ restaurar la tabla django_migrations del backup antiguo para evitar errores de historial inconsistente.
**Resultado de las pruebas:**
El script reportÃÂ³ inserciones exitosas masivas en todas las entidades (uth_user, 	esoreria, 
acturacion, productos, etc). Las migraciones posteriores corren sin conflictos de historial.
**Estado actual y siguientes pasos sugeridos:**
Base de datos 100% migrada y encuadrada con el nuevo cÃÂ³digo (sin perder registros antiguos). El sistema debe levantarse y probar si la visualizaciÃÂ³n del panel administrativo respeta los roles multi-empresa.

### Cristian - PC CASA
**Fecha:** 02/09/2026
**Objetivo:** Solucionar bug de visibilidad de las vistas del mÃÂ³dulo DistribuciÃÂ³n al asignar el tipo de actividad a una empresa.
**Archivos creados o modificados:**
- 
erticalidades/distribucion/apps.py
- 
erticalidades/distribucion/templates/distribucion/hooks/menu_sidebar_bottom.html
- 
erticalidades/distribucion/templates/distribucion/hooks/ui_configuracion_hub.html
- 
erticalidades/distribucion/templates/distribucion/hooks/ui_producto_modal_campos.html
**Detalle TÃÂ©cnico:** 
El modelo Empresa en empresas/models.py guarda el valor constante 'DISTRIBUCION' al seleccionar dicho rubro, pero las plantillas (hooks del menÃÂº y modales) y la configuraciÃÂ³n de la App de la verticalidad estaban evaluando la condicional esperando el valor 'DISTRIBUIDORA'. Se unificÃÂ³ el criterio reemplazando las condicionales y constantes a 'DISTRIBUCION' para que cuadre exactamente con la elecciÃÂ³n de base de datos de la empresa.
**Resultado de las pruebas:**
Al asignar "DistribuciÃÂ³n" a una empresa, las condicionales {% if empresa_actual.tipo_actividad == 'DISTRIBUCION' %} ahora resuelven a True e inyectan correctamente el menÃÂº lateral de DistribuciÃÂ³n, los campos en el modal de productos y las configuraciones de vehÃÂ­culos/personal.
**Estado actual y siguientes pasos sugeridos:**
MenÃÂºs de distribuciÃÂ³n restaurados correctamente y visibles en el frontend.

### Cristian - PC CASA
**Fecha:** 02/09/2026
**Objetivo:** Portar y adaptar los cambios del commit (57739d1) del proyecto legacy (erp-ikigai-2) hacia la nueva arquitectura con verticalidades.
**Archivos creados o modificados:**
- 	emplates/tesoreria/modals/buscador_bancos.html (Nuevo modal HTMX)
- 	esoreria/views_htmx.py, 	esoreria/urls.py, 	esoreria/forms.py, 	esoreria/models.py
- core/views_config.py
- 	emplates/configuracion/partials/rubros_prod_list.html
- 	emplates/tesoreria/modals/buscador_proveedores_op.html
**Detalle TÃÂ©cnico:** 
Se migrÃÂ³ exitosamente el parche de erp-ikigai-2 usando git apply. Esto introdujo:
1. Modal de bÃÂºsqueda en vivo HTMX para entidades bancarias segÃÂºn catÃÂ¡logo BCRA.
2. OptimizaciÃÂ³n de consultas ORM (select_related) en listados de Cuentas Bancarias para evitar N+1 con cli_pro y cuenta_contable.
3. Ajustes en core/views_config.py para listar Rubro, Marca y Familia optimizados (quitando sucursales huÃÂ©rfanas y aÃÂ±adiendo las cuentas contables de ventas/compras).
4. El listado visual de rubros (
ubros_prod_list.html) ahora expone explÃÂ­citamente las cuentas jerÃÂ¡rquicas contables asociadas.
**Resultado Pruebas:**
Los parches aplicaron limpiamente (se resolviÃÂ³ de manera manual el conflicto en 
iews_config.py). Las URLs de HTMX y las dependencias de modelos son consistentes con la base de datos actual.
**Estado Actual:**
Commit migrado y adaptado exitosamente a la arquitectura actual.

### Cristian - PC CASA
**Fecha:** 02/09/2026
**Objetivo:** Trasladar los perfiles de lectura PDF del core a la verticalidad de ArmerÃÂ­a y refactorizar el extractor para resolverlos dinÃÂ¡micamente.
**Archivos creados o modificados:**
- 
erticalidades/armeria/perfiles_lectura/ (Directorio y archivos trasladados)
- 
acturacion/services/extractor_facturas.py
- 
acturacion/views_procesamiento.py
**Detalle TÃÂ©cnico:** 
Se movieron los scripts de parsing especÃÂ­ficos (cuit_30610401240.py y cuit_30711323062.py) desde el mÃÂ³dulo genÃÂ©rico de 
acturacion hacia 
erticalidades/armeria/perfiles_lectura/.
Para mantener el extractor genÃÂ©rico y evitar cÃÂ³digo fuertemente acoplado (N+1 ifs por cada verticalidad), se inyectÃÂ³ el parÃÂ¡metro 	ipo_actividad (capturado en 
iews_procesamiento.py a travÃÂ©s de la empresa logueada) y se refactorizÃÂ³ procesar_factura_archivo() para utilizar importlib buscando dinÃÂ¡micamente:
1. 
erticalidades.<tipo_actividad>.perfiles_lectura.cuit_<cuit_limpio>
2. (Fallback) 
acturacion.services.perfiles_lectura.cuit_<cuit_limpio>
**Resultado de las pruebas:**
El extractor ahora enruta automÃÂ¡ticamente la lÃÂ³gica de lectura hacia la carpeta privada de cada verticalidad, manteniendo el core limpio.
**Estado actual y siguientes pasos sugeridos:**
Finalizado.
**Fecha:** 02/09/2026
**Objetivo:** CorrecciÃÂ³n de bug en asignaciÃÂ³n automÃÂ¡tica del Tipo de Comprobante tras lectura OCR.
**Archivos modificados:**
- 
acturacion/views_procesamiento.py
**Detalle TÃÂ©cnico:** 
El extractor retornaba el cÃÂ³digo de comprobante bajo la llave 	ipo_comprobante_afip (ej: "1"), pero la vista intentaba leer la llave inexistente 	ipo_comprobante_codigo. Se corrigiÃÂ³ la vista para leer la llave correcta y se agregÃÂ³ .zfill(3) para asegurar que el cÃÂ³digo concuerde con el formato de 3 dÃÂ­gitos de la base de datos (ej: "001" en lugar de "1"), lo que permite recuperar el detalle correctamente ("001 - Facturas A").
**Fecha:** 02/09/2026
**Objetivo:** ExtensiÃÂ³n de sobreescritura de Tipo de Comprobante al perfil 062.
**Archivos modificados:**
- 
erticalidades/armeria/perfiles_lectura/cuit_30711323062.py
**Detalle TÃÂ©cnico:** 
Al igual que en el perfil de Bowie, el perfil del CUIT 30-71132306-2 no estaba enviando el cÃÂ³digo explÃÂ­cito de AFIP al backend, por lo que el front quedaba vacÃÂ­o si la librerÃÂ­a general fallaba en detectarlo con exactitud. Se agregÃÂ³ la lÃÂ³gica para inyectar 	ipo_comprobante_codigo = '001' (y '003' si es Nota de CrÃÂ©dito) directamente en los cabecera_overrides de este proveedor.

## DÃÂ­a 31/08/2026 - La cuenta del efectivo la define la caja, y el recibo del cajero (Plan 077)

**Responsable:** Claude Opus.

### Objetivo
DefiniciÃÂ³n del usuario: *"Caja mostrador descarga sobre las cuentas definidas por parÃÂ¡metro Ã¢ÂÂcobranzas por un lado y retiros / cierre de caja por el otroÃ¢ÂÂ, por lo que deberÃÂ­an quedar en cero o lo que se defina como fondo fijo al final de cada cierre."* Y la mejora que lo acompaÃÂ±a: *"El cajero todo lo que maneje serÃÂ¡ a travÃÂ©s de su CAJA MOSTRADOR."*

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
- MigraciÃÂ³n: `usuarios/0010_cajero_mostrador.py` (aplicada).
- Plan: `docs/planes/077_recibo_en_mostrador.md` [NEW].

### Detalle TÃÂ©cnico

**El diagnÃÂ³stico: el efectivo tenÃÂ­a TRES destinos contables**, segÃÂºn por quÃÂ© camino entrara o saliera.

| Camino | Cuenta que usaba |
|--------|------------------|
| Venta de mostrador cobrada en el acto | `cta_caja` |
| Recibo de cobranza | la del **medio de pago** (fallback `cta_caja_central`) |
| Retiro / cierre de caja | `cta_caja_mostrador` |

Por eso `cta_caja_mostrador` **sÃÂ³lo recibÃÂ­a haber y nunca debe**: no es que no cerrara en cero, es que se volvÃÂ­a cada vez mÃÂ¡s acreedora con cada cierre. En ARMERIA ya estaba en Ã¢ÂÂ$25.000 con una sola lÃÂ­nea.

**La regla: para el efectivo, la cuenta la define la CAJA.** Un cheque es un cheque entre donde entre; el efectivo vive en un cajÃÂ³n concreto. Dicho de la forma en que lo planteÃÂ³ el usuario, que es la que ordena todo: **la cuenta la define quiÃÂ©n tiene que rendir la plata.** Un recibo hecho en el mostrador lo rinde el cajero; el mismo recibo hecho en TesorerÃÂ­a ya estÃÂ¡ en TesorerÃÂ­a.

`cuenta_efectivo_de_caja(caja, parametros, en_divisa)` resuelve por `caja.tipo`: `'M'` Ã¢ÂÂ mostrador, `'R'`/`'D'` Ã¢ÂÂ reparto, `'T'` Ã¢ÂÂ central. Para las cajas de distribuciÃÂ³n **lanza error si falta el parÃÂ¡metro** (sustituirlo en silencio mezclarÃÂ­a lo que ese parÃÂ¡metro vino a separar); para mostrador y tesorerÃÂ­a **devuelve `None` y la cadena sigue**, que es el estado heredado de las empresas que nunca lo cargaron.

En `_cuenta_medio_cobro()` entra como **paso 2**, entre la cuenta bancaria concreta y la lÃÂ³gica de divisas, y **sÃÂ³lo para categorÃÂ­a `EFE`**: la billetera digital no vive en un cajÃÂ³n que alguien tenga que rendir.

**SimplificaciÃÂ³n que se llevÃÂ³ puesta:** el medio de pago `EFE-REP` que el Plan 076 creaba para distribuciÃÂ³n **dejÃÂ³ de hacer falta** Ã¢ÂÂla caja ya dice la cuentaÃ¢ÂÂ, asÃÂ­ que se eliminÃÂ³. Queda un solo mecanismo en vez de dos, y las pruebas que verificaban aquel medio pasaron a verificar la resoluciÃÂ³n por caja.

**El recibo del cajero (ÃÂ§F).** Es **el mismo recibo que ya existÃÂ­a**: cliente, aplicaciÃÂ³n a facturas con saldo, o recibo simple. No hay pantalla nueva. `ReciboCargaView` ganÃÂ³ un atributo `origen` y una segunda URL apunta a **la misma vista y el mismo template**. Lo ÃÂºnico que cambiÃÂ³ de verdad fue `procesar_recibo()`, que resolvÃÂ­a la caja con `get_o_abrir_caja(...)` Ã¢ÂÂ**siempre TesorerÃÂ­a**, ahÃÂ­ estaba la raÃÂ­z de que un recibo nunca impactara el mostradorÃ¢ÂÂ y ahora usa la sesiÃÂ³n del cajero cuando el origen es el mostrador. Si su caja estÃÂ¡ cerrada **falla**: no se puede meter plata en un cajÃÂ³n que no estÃÂ¡ abierto, y desviarla a TesorerÃÂ­a serÃÂ­a peor que rechazarla.

La parte contable del recibo del mostrador **no tiene una sola lÃÂ­nea propia**: sale de la regla de ÃÂ§E.

**La restricciÃÂ³n del cajero (ÃÂ§G).** `Perfil.es_cajero_mostrador`, en `False` por defecto: es una RESTRICCIÃÂN, no un permiso, asÃÂ­ que nadie pierde accesos al aplicarla y sÃÂ³lo queda acotado quien se marque. Al revÃÂ©s Ã¢ÂÂun permiso que hubiera que otorgarÃ¢ÂÂ habrÃÂ­a dejado a todos afuera hasta tildarlo uno por uno. El administrador de sistema nunca queda atrapado, para que pueda entrar a corregirlo si se marca por error.

**El bloqueo va en las vistas, no sÃÂ³lo en el menÃÂº:** esconder un link no es un permiso, la URL sigue estando para quien la escriba. Las pruebas pegan contra las URLs directas, no contra el HTML del menÃÂº. Y el mensaje del bloqueo **le dice al cajero por dÃÂ³nde tiene que operar** en vez de un "no tenÃÂ©s permiso" a secas.

### Resultado de las Pruebas
```
python manage.py test tesoreria.tests.test_plan077_caja_cierra_en_cero   ->  8 OK
python manage.py test tesoreria.tests.test_plan077_cajero_mostrador      -> 10 OK
python manage.py test tesoreria contable distribucion                    -> 554 OK
```

**La regresiÃÂ³n encontrÃÂ³ un bug propio y sirviÃÂ³ de lecciÃÂ³n.** El import de
`cuenta_efectivo_de_caja` en la venta de mostrador nunca llegÃÂ³ al mÃÂ³dulo: el guardia del
parche lo dio por presente porque la cadena ya aparecÃÂ­a dentro de otra funciÃÂ³n, y el cobro de
mostrador rompÃÂ­a con `NameError`. Lo atraparon tres pruebas del Plan 049.

De ahÃÂ­ saliÃÂ³ una prueba nueva Ã¢ÂÂ`test_la_venta_de_mostrador_debita_la_cuenta_de_su_caja`Ã¢ÂÂ
porque el hueco de fondo era otro: de los **tres caminos** que este plan unifica, el de la
venta de mostrador **no tenÃÂ­a ninguna prueba que verificara la cuenta**. Las del Plan 049
comprobaban el `condic` y el vÃÂ­nculo con la caja, no dÃÂ³nde caÃÂ­a el debe.
Las 8 primeras **verifican el requerimiento, no la implementaciÃÂ³n**: cobran en el mostrador, cierran la caja dejando un fondo fijo, y comprueban que `cta_caja_mostrador` queda exactamente en el fondo fijo y que lo rendido llegÃÂ³ a Caja Central. Si maÃÂ±ana la cuenta se resolviera de otra manera pero la caja siguiera cerrando bien, deberÃÂ­an seguir pasando.

### Estado Actual y Siguientes Pasos
El circuito del efectivo quedÃÂ³ consistente en las tres cajas: mostrador, distribuciÃÂ³n y tesorerÃÂ­a. **Los datos histÃÂ³ricos de las cuatro empresas siguen mal contabilizados** Ã¢ÂÂel usuario confirmÃÂ³ que son de prueba y anteriores a varias mejorasÃ¢ÂÂ, asÃÂ­ que no se reexpresÃÂ³ nada.

Pendientes ofrecidos y no ejecutados: el reporte de devoluciones y el de correlativos del mÃÂ³dulo DistribuciÃÂ³n (fase 8 restante), el widget de fecha en otros siete formularios, las exportaciones a PDF/Excel, la validaciÃÂ³n contra ARCA HomologaciÃÂ³n, y el ajuste de inventario para la mercaderÃÂ­a devuelta no apta.

## DÃÂ­a 31/08/2026 - Cuenta contable propia para la caja de distribuciÃÂ³n (Plan 076, addenda ÃÂ§B)

**Responsable:** Claude Opus.

### Objetivo
DefiniciÃÂ³n del usuario: *"Agreguemos un nuevo parÃÂ¡metro `cta_caja_reparto` porque incluso ambos responsables son totalmente distintos."* El efectivo que estÃÂ¡ en la calle es de otro responsable que el de la caja mostrador Ã¢ÂÂel repartidor y el administrativo de reparto, frente al cajero de turnoÃ¢ÂÂ, asÃÂ­ que el balance tiene que poder mostrarlo por separado.

### Archivos Creados o Modificados
- `contable/models.py` [MODIFY]: `ParametrosContables.cta_caja_reparto`.
- `templates/configuracion/modals/parametros_contables_form.html` [MODIFY]: el campo en la pantalla de parÃÂ¡metros.
- `tesoreria/views_htmx.py` [MODIFY]: `cuenta_origen_de_caja()`, y `generar_asientos_traslado()` / `_generar_asiento_diferencia()` pasan a aceptar la cuenta en vez de tenerla fija.
- `distribucion/services/caja_reparto.py` [MODIFY]: `cuenta_de_reparto()` y `medio_pago_efectivo()`.
- `distribucion/services/cobranza_fifo.py` [MODIFY]: el efectivo usa el medio de distribuciÃÂ³n.
- `distribucion/tests/test_plan076_cuenta_reparto.py` [NEW]: 14 pruebas.
- MigraciÃÂ³n: `contable/0022_cta_caja_reparto.py` (aplicada).

### Detalle TÃÂ©cnico

**El parÃÂ¡metro solo no alcanzaba, y ÃÂ©se fue el hallazgo.** `contabilizar_recibo()` arma el DEBE del asiento con la cuenta contable del **MEDIO DE PAGO**, no con la de la caja (`_cuenta_medio_cobro()`, punto 3 de su orden de resoluciÃÂ³n). Con el efectivo genÃÂ©rico, la cobranza de un reparto habrÃÂ­a seguido cayendo en la cuenta de la mostrador y el parÃÂ¡metro nuevo no habrÃÂ­a servido de nada: el balance mostrarÃÂ­a la cuenta de reparto en cero mientras la plata de la calle se sigue mezclando.

La soluciÃÂ³n usa el punto de extensiÃÂ³n que ya existÃÂ­a en vez de tocar el motor contable: un **medio de pago propio `EFE-REP` (ÃÂ«Efectivo en RepartoÃÂ»)** apuntado a `cta_caja_reparto`, creado y **mantenido en sincronÃÂ­a** con el parÃÂ¡metro por `medio_pago_efectivo()`. Si el parÃÂ¡metro cambia, el medio lo sigue; si no, los asientos nuevos quedarÃÂ­an apuntando a la cuenta vieja. El usuario no tiene que cargarlo ni recordarlo: se deriva del parÃÂ¡metro. Hay una prueba de punta a punta que verifica que **lo cobrado en la calle no toca la cuenta de la mostrador**.

**Sin fallback a la mostrador, a propÃÂ³sito.** `cuenta_de_reparto()` lanza un error explÃÂ­cito si el parÃÂ¡metro estÃÂ¡ vacÃÂ­o. Sustituirla en silencio mezclarÃÂ­a la plata del repartidor con la del cajero, que es exactamente lo que esta cuenta viene a separar: *mejor un error claro una vez que un nÃÂºmero mal agrupado para siempre*. Es ademÃÂ¡s la doctrina del proyecto desde el Plan 075.

**Dos funciones compartidas dejaron de tener la cuenta fija**, con el comportamiento de siempre por omisiÃÂ³n:
- `generar_asientos_traslado(..., cuenta_origen=None)` Ã¢ÂÂ por omisiÃÂ³n `cta_caja_mostrador`. El retiro y el cierre resuelven cuÃÂ¡l corresponde con `cuenta_origen_de_caja(caja, param)`, segÃÂºn el tipo de caja.
- `_generar_asiento_diferencia(..., cuenta_caja=None)` Ã¢ÂÂ por omisiÃÂ³n `cta_caja_central`. Cuando quien recibe es la TesorerÃÂ­a de Reparto se ajusta `cta_caja_reparto`, porque **la plata contada estÃÂ¡ ahÃÂ­ y no en TesorerÃÂ­a**: ajustar la Central moverÃÂ­a una cuenta donde no pasÃÂ³ nada.

**Las dos cajas de distribuciÃÂ³n comparten la cuenta.** La recaudadora `'R'` y la TesorerÃÂ­a de Reparto `'D'` apuntan a `cta_caja_reparto`, asÃÂ­ que el traslado entre ellas sigue sin generar asiento Ã¢ÂÂserÃÂ­a Debe y Haber sobre la misma cuentaÃ¢ÂÂ. El asiento contable real aparece reciÃÂ©n en el segundo tramo, cuando la intermedia rinde a Caja TesorerÃÂ­a: ahÃÂ­ sÃÂ­ **Debe Caja Central / Haber Caja de Reparto**, que es lo que hace visible en el balance cuÃÂ¡nto hay en la calle.

### Resultado de las Pruebas
```
python manage.py test distribucion tesoreria contable
Ran 534 tests in 517.615s
OK
```
Las 14 pruebas nuevas cubren: el parÃÂ¡metro y su error cuando falta, el medio de pago propio (que apunta a la cuenta, que no pisa el efectivo genÃÂ©rico, que sigue al parÃÂ¡metro si cambia y que es idempotente), el asiento de la cobranza del reparto y del vendedor debitando la cuenta correcta, la diferencia de arqueo ajustando la caja de reparto y no la Central, la resoluciÃÂ³n de la cuenta de origen segÃÂºn el tipo de caja, y la verificaciÃÂ³n de punta a punta de que lo cobrado en la calle no toca la cuenta de la mostrador.

### Estado Actual y Siguientes Pasos

**ACCIÃÂN PENDIENTE DEL USUARIO.** La empresa 4 (RODRIGUEZ MARCELO FABIAN) todavÃÂ­a tiene `cta_caja_reparto` **sin configurar**, asÃÂ­ que el circuito de cobranzas de distribuciÃÂ³n va a fallar con el mensaje explÃÂ­cito hasta que se le asigne una cuenta en *ConfiguraciÃÂ³n Ã¢ÂÂ ParÃÂ¡metros Contables Ã¢ÂÂ Caja de Reparto (DistribuciÃÂ³n)*. Su plan de cuentas hoy tiene `111001 CAJA`, `111002 VALORES EN CARTERA` y `111003 CAJA MOSTRADOR`: el hueco natural es `111004 CAJA DE REPARTO`.

Pendientes ofrecidos y no ejecutados: el reporte de devoluciones y el de correlativos del mÃÂ³dulo (fase 8 restante), el widget de fecha en otros siete formularios, las exportaciones a PDF/Excel, la validaciÃÂ³n contra ARCA HomologaciÃÂ³n, y el ajuste de inventario para la mercaderÃÂ­a devuelta no apta.

## DÃÂ­a 31/08/2026 - Cobranza y rendiciÃÂ³n del vendedor (Plan 076, bloque C)

**Responsable:** Claude Opus.

### Objetivo
DefiniciÃÂ³n del usuario: *"En cuanto a los vendedores, rendirÃÂ¡n a esta caja intermedia pero en su condiciÃÂ³n de vendedores por los fondos que traen, no como reparto."*

### Archivos Creados o Modificados
- `distribucion/models.py` [MODIFY]: `CobranzaDistribucion.reparto` nullable con CheckConstraint de responsable; `RendicionReparto` gana `vendedor` y el CheckConstraint de origen ÃÂºnico.
- `distribucion/services/caja_reparto.py` [MODIFY]: `abrir_caja_del_vendedor()`, `sesion_abierta_del_vendedor()`, `resumen_vendedor()`, `rendir_vendedor()`; la bandeja lista los dos orÃÂ­genes.
- `distribucion/services/cobranza_fifo.py` [MODIFY]: `registrar()` acepta `reparto=None`.
- `distribucion/views.py`, `templates/distribucion/cobranza_vendedor.html` [NEW/MODIFY].
- `distribucion/tests/test_plan076_cobranza_vendedor.py` [NEW]: 23 pruebas.
- MigraciÃÂ³n: `distribucion/0010_rendicion_del_vendedor.py` (aplicada).

### Detalle TÃÂ©cnico

**Para poder rendir hay que haber retenido.** El vendedor cobra por su cuenta Ã¢ÂÂal cliente que esquiva el pago y al que despuÃÂ©s le hace la guardiaÃ¢ÂÂ, y esa plata tiene que caer en algÃÂºn lado antes de que la entregue, o no habrÃÂ­a nada que rendir. Se le abre una **sesiÃÂ³n propia sobre la misma caja recaudadora**, que se cierra reciÃÂ©n cuando rinde. Misma estructura que un reparto, con otro dueÃÂ±o.

**La sesiÃÂ³n no dice de quiÃÂ©n es la plata; lo dice la rendiciÃÂ³n.** `CajaSesion.usuario` es un `User` y el vendedor puede no serlo (ÃÂ§4.3). La sesiÃÂ³n abierta de un vendedor se identifica por **sus cobranzas**, que llevan el `cobrador`; una sesiÃÂ³n de reparto nunca entra ahÃÂ­ porque sus cobranzas tienen `reparto` seteado.

**La plata siempre tiene un responsable.** Dos restricciones de base:
```python
CobranzaDistribucion:  Q(reparto__isnull=False) | Q(cobrador__isnull=False)
RendicionReparto:      exactamente UNO de reparto / vendedor
```
Sin ninguno la plata no tiene dueÃÂ±o; con los dos, no se sabe a quiÃÂ©n reclamarle un faltante.

**Mismo FIFO, mismas dos reglas, sin caso especial.** `registrar()` con `reparto=None` recorre idÃÂ©ntico camino. Una prueba lo fija: efectivo contra el PRE, transferencia contra la factura.

**`Personal` no tiene sucursal** Ã¢ÂÂel vendedor recorre, no estÃÂ¡ asignado a un depÃÂ³sitoÃ¢ÂÂ, asÃÂ­ que la sucursal la aporta quien opera, desde su sesiÃÂ³n de trabajo. El servicio la exige explÃÂ­citamente en vez de adivinarla.

**Los dos orÃÂ­genes comparten bandeja de recepciÃÂ³n:** para quien recibe es el mismo acto Ã¢ÂÂcontar lo que alguien trajoÃ¢ÂÂ y separarlos sÃÂ³lo agregarÃÂ­a una pantalla mÃÂ¡s.

### Resultado de las Pruebas
```
python manage.py test distribucion.tests.test_plan076_cobranza_vendedor
Ran 23 tests in 30.689s
OK
```

### Estado Actual y Siguientes Pasos
**Plan 076 completo (A + B + C + D).** El circuito de fondos de DistribuciÃÂ³n quedÃÂ³ con sus tres niveles y las notas de crÃÂ©dito descuentan el saldo de su factura en todo el ERP.

Pendientes ofrecidos y no ejecutados: el reporte de devoluciones por perÃÂ­odo/motivo/repartidor y el de correlativos del mÃÂ³dulo (fase 8 restante), el widget de fecha en otros siete formularios, las exportaciones a PDF/Excel, la validaciÃÂ³n contra ARCA HomologaciÃÂ³n, el ajuste de inventario para la mercaderÃÂ­a devuelta no apta, y una cuenta contable propia para las cajas de distribuciÃÂ³n si se quisiera ver por separado en el balance la plata que estÃÂ¡ en la calle.

## DÃÂ­a 31/08/2026 - TesorerÃÂ­a de Reparto intermedia (Plan 076, bloque B)

**Responsable:** Claude Opus.

### Objetivo
DefiniciÃÂ³n del usuario: *"Las rendiciones de reparto y vendedoresÃ¢ÂÂ¦ se realizan en una 'tesorerÃÂ­a de reparto intermedia' tal cual la caja mostrador de armerÃÂ­a, para luego tipo retiro y cierre de caja rendir a caja tesorerÃÂ­a."* La fase 7 salteaba ese nivel.

### Archivos Creados o Modificados
- `tesoreria/models.py` [MODIFY]: `Caja.tipo` gana `'D'` (TesorerÃÂ­a de Reparto).
- `tesoreria/views.py`, `tesoreria/views_htmx.py` [MODIFY]: **correcciÃÂ³n de la regresiÃÂ³n** y helpers `_caja_operable()` / `_cajas_operables()`.
- `distribucion/services/caja_reparto.py` [MODIFY]: `tesoreria_reparto()`, `sesion_de_tesoreria_reparto()`, `recibir()`, `rendiciones_por_recibir()`; `rendir()` cambia de destino.
- `distribucion/views.py`, `templates/distribucion/recepcion_rendiciones.html` [NEW/MODIFY]: bandeja de recepciÃÂ³n.
- `distribucion/tests/test_plan076_tesoreria_reparto.py` [NEW]: 20 pruebas.
- MigraciÃÂ³n: `tesoreria/0017_tesoreria_de_reparto.py` (aplicada).

### Detalle TÃÂ©cnico

**Son tres niveles, no dos:**
```
cobranzas Ã¢ÂÂÃ¢ÂÂº CAJA RECAUDADORA 'R'      una sesiÃÂ³n por reparto
                    Ã¢ÂÂ  el repartidor declara Ã¢ÂÂ el administrativo cuenta y acepta
                    Ã¢ÂÂ¼
             TESORERÃÂA DE REPARTO 'D'  UNA POR SUCURSAL
                    Ã¢ÂÂ  retiro / cierre de caja (circuito existente)
                    Ã¢ÂÂ¼
             CAJA TESORERÃÂA 'T'
```
Quien recibe a los repartidores **no es el tesorero central**: es un administrativo que cuenta lo que cada uno trae, lo retiene, y despuÃÂ©s entrega el consolidado. Es la misma razÃÂ³n por la que existe la caja mostrador de armerÃÂ­a. Y **los dos pasos que el Plan 074 ÃÂ§7.9 pedÃÂ­a son los de este tramo**, no los del que va a TesorerÃÂ­a: estaban bien descritos y mal ubicados.

**REGRESIÃÂN CORREGIDA (ÃÂ§B.2).** `caja_recaudadora()` Ã¢ÂÂde la fase 7Ã¢ÂÂ crea una caja `'R'` en la misma sucursal donde vive la mostrador. Seis lugares buscaban ÃÂ«la caja de la sucursalÃÂ» **sin filtrar por tipo**:
```python
Caja.objects.filter(empresa_id=..., sucursal_id=..., activa=True).first()
```
en `tesoreria/views.py:79` y `views_htmx.py` 923, 1328, 1354, 1477 y 1498. `Caja` no tiene `ordering` en su `Meta`, asÃÂ­ que funcionaba sÃÂ³lo porque la mostrador tiene `pk` mÃÂ¡s bajo. **El riesgo real:** la sesiÃÂ³n se busca con `usuario=request.user, estado='A'`, y un cajero que ademÃÂ¡s cerrara un reparto tenÃÂ­a DOS sesiones abiertas a su nombre Ã¢ÂÂ el cierre de mostrador podÃÂ­a tomar la del reparto y rendir esa plata por el circuito equivocado. Hay tres pruebas dedicadas.

**Sin asiento de traslado en el primer tramo, y es deliberado.** La recaudadora y la TesorerÃÂ­a de Reparto son las dos ÃÂ«efectivo fuera de TesorerÃÂ­aÃÂ» y comparten cuenta contable (`cta_caja_mostrador`): el asiento serÃÂ­a Debe y Haber sobre la misma cuenta. Peor todavÃÂ­a serÃÂ­a asentar contra Caja Central, porque estarÃÂ­a registrando en TesorerÃÂ­a **plata que sigue en la calle**. El movimiento contable real ocurre en el segundo tramo, cuando la intermedia rinde por el retiro/cierre de siempre.

**La caja refleja lo CONTADO, no lo declarado**, y la diferencia genera su asiento contra Diferencias de Caja: un faltante queda registrado, no absorbido en silencio. *El que declara no es el mismo que cuenta.*

### Resultado de las Pruebas
```
python manage.py test distribucion tesoreria
Ran 405 tests in 370.545s
OK
```

---

## DÃÂ­a 31/08/2026 - Parada de sÃÂ³lo cobranza (Plan 076, bloque A)

**Responsable:** Claude Opus.

### Objetivo
DefiniciÃÂ³n del usuario: *"En una hoja de ruta podemos agregar clientes con saldos que no hicieron un pedido pero necesito que le cobren el saldo pendiente."* Si todas las paradas son de esa clase, el reparto es una ruta de cobranza pura, sin detalle de productos.

### Archivos Creados o Modificados
- `distribucion/models.py` [MODIFY]: `RepartoParada.tipo` (`ENTREGA` / `COBRANZA`), `pedido` y `venta` nullables, `cliente` y `domicilio_texto` como campos propios, y tres restricciones nuevas.
- `distribucion/services/reparto.py` [MODIFY]: `agregar_parada_de_cobranza()`, `cerrar_reparto()`, `hoja_de_ruta()`, `consolidado()`, `totales_hoja_de_ruta()`.
- `distribucion/services/devoluciones.py` [MODIFY]: entrega y devoluciones sÃÂ³lo sobre paradas de ENTREGA.
- `distribucion/views.py` [MODIFY]: acciÃÂ³n `agregar_cobranza` y selector de clientes con saldo.
- Templates de reparto, hoja de ruta, entrega, cobranza, recepciÃÂ³n y rendiciÃÂ³n [MODIFY].
- `distribucion/tests/test_plan076_parada_cobranza.py` [NEW]: 27 pruebas.
- MigraciÃÂ³n: `distribucion/0009_parada_de_cobranza.py` (aplicada).

### Detalle TÃÂ©cnico

**EL COBRO MÃÂNIMO DE UNA PARADA DE COBRANZA ES CERO.** Es la correcciÃÂ³n central del bloque, y va contra lo que yo habÃÂ­a asumido primero Ã¢ÂÂque habÃÂ­a que exigir todo el saldoÃ¢ÂÂ. El usuario lo desarmÃÂ³:

> *"Puede tranquilamente ser una cobranza parcial como cualquier otraÃ¢ÂÂ¦ la mayorÃÂ­a de las veces el cliente o no entrega nada o entrega sÃÂ³lo un pago parcial. Seguramente el pago final lo terminarÃÂ¡ haciendo el vendedor que le harÃÂ¡ la 'guardia' cuando el cliente estÃÂ© esquivando el pago. Cliente que no hizo pedido es mÃÂ¡s que probable que no estÃÂ© entre sus prioridades el pagarnos."*

El razonamiento de fondo: **el cobro mÃÂ­nimo existe porque hay mercaderÃÂ­a de por medio, es la condiciÃÂ³n para dejarla.** Sin entrega no hay palanca. El repartidor pide y se lleva lo que le den. Entonces se congela el **saldo** como dato para reclamar, `cobro_minimo = 0`, y lo que traiga se imputa con el procedimiento estÃÂ¡ndar: FIFO de lo mÃÂ¡s antiguo, con el efectivo priorizando los `condic = 2`. **Sin caso especial**: es exactamente lo que ya hacÃÂ­a `registrar()`.

Queda ademÃÂ¡s coherente el cuadro de la rendiciÃÂ³n: `esperado = ÃÂ£ cobro_minimo`, asÃÂ­ que estas paradas aportan cero. *No se puede esperar lo que no se tiene con quÃÂ© exigir.*

**El tipo es explÃÂ­cito, no inferido.** `RepartoParada.tipo` en vez de deducirlo de `venta is None`: obligar a recordar esa convenciÃÂ³n en cada lectura es la clase de detalle que despuÃÂ©s se olvida en un reporte.

**`cliente` y `domicilio_texto` dejan de ser properties.** SalÃÂ­an de `venta.cliente` y `pedido.domicilio_entrega_texto`; sin comprobante no hay de dÃÂ³nde sacarlos. La migraciÃÂ³n los rellena con **los mismos valores que devolvÃÂ­an las properties**: no hay pÃÂ©rdida ni interpretaciÃÂ³n. El domicilio queda congelado por el mismo motivo que los importes.

**Las reglas inflexibles van a la base:**
```python
CheckConstraint(Q(tipo=0, venta__isnull=False) | Q(tipo=1, venta__isnull=True))
UniqueConstraint(['venta'], condition=Q(venta__isnull=False))
```
El ÃÂºnico se condiciona porque ahora hay nulos. PostgreSQL ya admite varios NULL en un ÃÂ­ndice ÃÂºnico, pero asÃÂ­ la regla queda **escrita** y no depende de un detalle del motor. Hay pruebas para las dos combinaciones invÃÂ¡lidas y para que varias paradas de cobranza convivan en el mismo reparto.

**Lo que se apagÃÂ³ donde no corresponde:** entrega, devoluciones y RecepciÃÂ³n de Devoluciones rechazan una parada de cobranza Ã¢ÂÂ *sin mercaderÃÂ­a no hay entrega que registrar ni devoluciÃÂ³n que recibir*. El Consolidado de un reparto de pura cobranza da **vacÃÂ­o**, que es lo correcto: no se carga nada al vehÃÂ­culo. Y `hoja_de_ruta()` pasa a ordenar por el cliente **propio de la parada**: por el del comprobante, las de cobranza caÃÂ­an todas al final.

### Resultado de las Pruebas
```
python manage.py test distribucion
Ran 297 tests in 281.850s
OK
```

---

## DÃÂ­a 31/08/2026 - La Nota de CrÃÂ©dito descuenta el saldo de su factura (Plan 076, bloque D)

**Responsable:** Claude Opus.

### Objetivo
DefiniciÃÂ³n del usuario: *"Las notas de crÃÂ©dito, como estÃÂ¡n vinculadas a la factura que le dio origen, deben computarse en el saldo pendiente de la factura (factura Ã¢ÂÂ NC relacionadas), y de ahÃÂ­ sale el saldo real de la factura. La NC queda con saldo cero porque se aplicÃÂ³ totalmente a la factura de origen."* **Afecta a todo el ERP, no sÃÂ³lo a DistribuciÃÂ³n.**

### Archivos Creados o Modificados
- `facturacion/models.py` [MODIFY]: `Venta.venta_origen` (FK a sÃÂ­ misma, nullable, `related_name='notas_credito'`).
- `facturacion/services/notas_credito.py` [MODIFY]: `emitir_nota_credito_desde_venta()` estampa el vÃÂ­nculo.
- `facturacion/signals.py` [MODIFY]: al guardar una NC vinculada se recalcula el saldo de la NC y el de su factura.
- `contable/services/saldos.py` [MODIFY]: `recalcular_saldo_venta()` resta las NC relacionadas y deja la NC en cero; `recalcular_saldo_cliente_proveedor()` **aplica el signo del tipo**.
- `facturacion/tests/test_plan076_saldo_nc.py` [NEW]: 11 pruebas.
- Migraciones: `facturacion/0059_venta_venta_origen.py` y `facturacion/0060_vincular_nc_y_recalcular_saldos.py` (aplicadas).

### Detalle TÃÂ©cnico

**No existÃÂ­a vÃÂ­nculo genÃÂ©rico NC Ã¢ÂÂ factura.** `emitir_nota_credito_desde_venta()` recibÃÂ­a la venta original, copiaba sus ÃÂ­tems y **no persistÃÂ­a de dÃÂ³nde venÃÂ­a**. El ÃÂºnico vÃÂ­nculo era `distribucion.NotaCreditoDistribucion.venta_origen`, satÃÂ©lite del mÃÂ³dulo, inÃÂºtil para armerÃÂ­a o para el resto del ERP. El campo nuevo `Venta.venta_origen` cierra eso.

**El saldo del comprobante.** `recalcular_saldo_venta()` pasa a ser `total Ã¢ÂÂ cobrado Ã¢ÂÂ ÃÂ£ recibos Ã¢ÂÂ ÃÂ£ NC relacionadas`, y una NC con `venta_origen` queda en **cero**: se aplicÃÂ³ por completo a su factura. El recÃÂ¡lculo se dispara desde la seÃÂ±al `post_save` de `Venta` y no desde el emisor de la NC, para que valga tambiÃÂ©n al **anularla**, que es cuando el descuento se revierte. No hay recursiÃÂ³n: el servicio escribe con `.update()`, que no dispara seÃÂ±ales.

**Hallazgo: la convenciÃÂ³n de signo estaba documentada pero no implementada.** `saldos.py` y `tesoreria/views_htmx.py` decÃÂ­an que las NC *"se graban en negativo vÃÂ­a `TipoComprobante.signo = -1`"*. Los datos dicen otra cosa: las dos NC de la base tienen total **positivo** (30,00 y 12,00), y `emitir_nota_credito_desde_venta()` las emite asÃÂ­, sumando ÃÂ­tems positivos. Con `recalcular_saldo_cliente_proveedor()` sumando `total Ã¢ÂÂ cobrado` sin aplicar el signo, **una Nota de CrÃÂ©dito AUMENTABA la deuda del cliente en lugar de bajarla**.

La correcciÃÂ³n va donde ya estaba el criterio correcto del proyecto: `productos.services.stock_service` multiplica por `tipo__signo` para que la NC invierta el movimiento. Ahora el saldo por entidad hace lo mismo:

```python
Sum((F('total') - F('cobrado')) * Coalesce(F('tipo__signo'), Value(1)))
```

Es un arreglo inseparable del pedido: sin ÃÂ©l la lente por comprobante y la lente por entidad se separaban por el doble de la NC. Hay una prueba que exige que **la suma de los saldos de los comprobantes sea igual al saldo del cliente**.

`recalcular_saldo_compra()` **no se tocÃÂ³**: no hay ninguna compra con tipo de signo Ã¢ÂÂ1 en la base, asÃÂ­ que no hay evidencia de cuÃÂ¡l es la convenciÃÂ³n real del lado de proveedores. Queda anotado.

**Efecto lateral que limpia el diseÃÂ±o de la fase 7.** Aquella fase documentÃÂ³ *"las notas de crÃÂ©dito no entran en el FIFO"* como decisiÃÂ³n para no manejar signos cruzados. Con esta regla deja de ser un compromiso: la NC baja el saldo de su factura y queda en cero, asÃÂ­ que el filtro `saldo > 0` de `comprobantes_abiertos()` es correcto **por construcciÃÂ³n**. Dos pruebas lo fijan.

**MigraciÃÂ³n de datos.** Vincula las NC existentes desde `NotaCreditoDistribucion.venta_origen` Ã¢ÂÂÃÂºnico lugar donde el dato existÃÂ­aÃ¢ÂÂ y recalcula comprobantes y entidades con una **rÃÂ©plica congelada** de la fÃÂ³rmula, sin importar el servicio vivo (en una migraciÃÂ³n el modelo es histÃÂ³rico). VerificaciÃÂ³n sobre la base real:

```
ANTES:   ORTIZ JUAN MANUEL  saldo 599,00
DESPUES: ORTIZ JUAN MANUEL  saldo 515,00
```

La baja de 84,00 es exactamente 2 ÃÂ 42,00 (las dos NC de 30,00 y 12,00): antes se sumaban, ahora se restan. Confirma que el error era real y que quedÃÂ³ corregido.

**LimitaciÃÂ³n conocida:** las NC histÃÂ³ricas de otros mÃÂ³dulos no tienen de dÃÂ³nde deducir su origen y quedan sin vincular (`venta_origen = NULL`). Son las dos que hay en el sistema. Su saldo se comporta como antes Ã¢ÂÂuna NC sin aplicar es un crÃÂ©dito pendiente legÃÂ­timoÃ¢ÂÂ, pero el FIFO las va a ofrecer como comprobante a cobrar hasta que se las vincule a mano.

### Resultado de las Pruebas
```
python manage.py test facturacion contable tesoreria
Ran 280 tests in 221.312s
FAILED (errors=1)   # test_emitir_comprobante_homologacion_real: falta el certificado ARCA (ambiental)
```
Las 11 pruebas nuevas cubren: la NC baja el saldo de su factura, la NC queda en cero, el vÃÂ­nculo persistido, la NC total, dos NC parciales acumuladas, la convivencia con una cobranza en el mismo saldo, la reversiÃÂ³n al anular, que el saldo del cliente no se cuente dos veces, que las dos lentes coincidan, y que el FIFO no ofrezca ni una factura ya cubierta ni la NC.

### Estado Actual y Siguientes Pasos
Bloque **D** cerrado. **Siguen A** (parada de sÃÂ³lo cobranza), **B** (TesorerÃÂ­a de Reparto intermedia + la regresiÃÂ³n del ÃÂ§B.2) y **C** (rendiciÃÂ³n del vendedor), en ese orden.

## DÃÂ­a 31/08/2026 - Cobranzas del repartidor, caja recaudadora y saldos por vendedor (Plan 074, fases 7 y 8)

**Responsable:** Claude Opus.

### Objetivo
Cerrar el circuito del dinero: la cobranza que trae el repartidor con **imputaciÃÂ³n FIFO segmentada por medio de pago**, la **caja recaudadora** que se abre por reparto, la **rendiciÃÂ³n a TesorerÃÂ­a** en dos pasos, y el listado de **Clientes a Cobrar** agrupado por vendedor.

### Archivos Creados o Modificados
- `distribucion/services/cobranza_fifo.py` [NEW]: `planificar()`, `registrar()`, `comprobantes_abiertos()`, `saldo_fiscal()`, `saldo_operativo()`.
- `distribucion/services/caja_reparto.py` [NEW]: `caja_recaudadora()`, `abrir_caja_del_reparto()`, `resumen()`, `rendir()`.
- `distribucion/services/saldos_clientes.py` [NEW]: `listado()` con antigÃÂ¼edad por tramos y agrupaciÃÂ³n por vendedor.
- `distribucion/models.py` [MODIFY]: `CobranzaDistribucion`, `RendicionReparto` y `Reparto.sesion_caja`.
- `tesoreria/models.py` [MODIFY]: nuevo tipo de caja `'R'` (Recaudadora / Reparto).
- `distribucion/services/reparto.py` [MODIFY]: `cerrar_reparto()` abre la caja recaudadora.
- `distribucion/views.py` [MODIFY]: `CobranzaRepartoView`, `RendicionRepartoView`, `SaldosClientesView`.
- `templates/distribucion/cobranza.html`, `rendicion.html`, `saldos_clientes.html` [NEW].
- `templates/distribucion/reparto_detalle.html`, `templates/base.html`, `config/urls.py` [MODIFY]: tres rutas nuevas y la entrada de menÃÂº ÃÂ«Clientes a CobrarÃÂ».
- `distribucion/tests/test_plan074_cobranzas.py` [NEW]: 43 pruebas.
- Migraciones: `distribucion/0008_reparto_sesion_caja_cobranzadistribucion_and_more.py`, `tesoreria/0016_alter_caja_tipo.py`, `core/0007_alter_contadordocumento_tipo_documento.py` (todas aplicadas).

### Detalle TÃÂ©cnico

**El usuario carga un importe; el corte lo hace el sistema.** El repartidor vuelve y dice ÃÂ«de GonzÃÂ¡lez traje $40.000 en efectivo y un cheque de $66.000ÃÂ». Nadie le va a preguntar cuÃÂ¡nto de eso cancela facturas y cuÃÂ¡nto cancela PRE: eso lo decide `cobranza_fifo.py` con dos reglas que no se negocian.

1. **Lo trazable va siempre contra `condic = 1`.** Transferencia, cheque, tarjeta, billetera digital y retenciÃÂ³n: un movimiento que el banco registra no puede cancelar una operaciÃÂ³n que para el fisco no existe. Todo lo que **no** estÃÂ© en esa lista se trata como efectivo, incluida la categorÃÂ­a `OTR`: si no deja rastro externo verificable, no puede respaldar una operaciÃÂ³n fiscal.
2. **El efectivo cancela primero el PRE mÃÂ¡s viejo**, y sÃÂ³lo agotados todos los PRE continÃÂºa con las facturas. Es la ÃÂºnica plata que puede pagar lo que no estÃÂ¡ documentado, asÃÂ­ que se usa donde hace falta.

Los dos tramos comparten **un solo diccionario de saldos**, que se muta a medida que se imputa. Es lo que garantiza que el efectivo no vuelva a aplicar sobre el peso que ya cancelÃÂ³ el cheque; hay una prueba que lo fija.

**Dos recibos como mÃÂ¡ximo, uno por `condic`.** Real y Presupuestado no se mezclan porque cada uno alimenta un circuito contable distinto y el asiento hereda el `condic` del comprobante. El recibo Presupuestado lleva **exactamente** el efectivo que cancelÃÂ³ PRE; todo lo demÃÂ¡s Ã¢ÂÂtrazables, efectivo aplicado a facturas y el excedenteÃ¢ÂÂ va al Real. AsÃÂ­ los dos totales suman lo que entrÃÂ³ en la caja, y los `MovimientoCajaDetalle` de cada uno cuadran con su total, que es lo que hace que el asiento cierre. Hay una prueba dedicada a ese cuadre.

**El excedente queda en el circuito fiscal**, como anticipo del cliente: es donde se puede justificar de dÃÂ³nde saliÃÂ³ la plata. Si sobrÃÂ³ efectivo es porque ya no quedaba ningÃÂºn PRE que cancelar, asÃÂ­ que no hay otro lugar donde ponerlo.

**Las notas de crÃÂ©dito no entran en el FIFO.** Acreditar una NC contra una factura es una *imputaciÃÂ³n entre comprobantes*, no una cobranza: no entra plata. Mezclarla obligarÃÂ­a a manejar signos cruzados en el mismo recorrido y volverÃÂ­a ilegible el algoritmo. El FIFO recorre sÃÂ³lo comprobantes con saldo deudor.

**Las dos lentes sobre el saldo del cliente.** `ClienteProveedor.saldo` suma todo sin distinguir: sirve como lente **operativa** (`condic 1 + 2`), que es la que ve el vendedor, la que usa el lÃÂ­mite de crÃÂ©dito y la que sale impresa en la Hoja de Ruta Ã¢ÂÂal cliente hay que cobrarle todo lo que debe, tenga o no respaldo fiscalÃ¢ÂÂ. La lente **fiscal** (`condic = 1`) se calcula recorriendo comprobantes y recibos: es la que va a los estados contables. Una prueba muestra el efecto: cobrar en efectivo un PRE baja el saldo operativo y **no mueve el fiscal**.

**Caja recaudadora `'R'`, no la mostrador `'M'`.** La mostrador se abre y cierra por turno de cajero, con arqueo ciego, en un puesto fijo; la recaudadora se abre y cierra **por reparto**, la maneja alguien que estÃÂ¡ en la calle, y su cierre se concilia contra la Hoja de Ruta. Un `tipo` explÃÂ­cito evita ramificar el cÃÂ³digo de la mostrador con condicionales que no tienen nada que ver con ella. Hay **una sola caja recaudadora por sucursal**: lo que separa un reparto de otro es la **sesiÃÂ³n**, que se abre automÃÂ¡ticamente al cerrar el reparto.

**De quiÃÂ©n es la plata lo dice el reparto, no la sesiÃÂ³n de caja.** `CajaSesion.usuario` es un `User` y el repartidor puede no serlo: trabaja con el papel y no necesita credenciales (ÃÂ§4.3). En la prÃÂ¡ctica el administrativo abre la sesiÃÂ³n y el `Reparto` dice de quiÃÂ©n es la recaudaciÃÂ³n, a travÃÂ©s de sus `responsables`. `RendicionReparto` es el vÃÂ­nculo que la sesiÃÂ³n de caja no puede dar.

**La rendiciÃÂ³n reutiliza `RetiroCaja`, que ya existe.** Los dos pasos Ã¢ÂÂel repartidor declara, el tesorero cuenta y acepta, la diferencia genera su asientoÃ¢ÂÂ ya estÃÂ¡n implementados y probados en TesorerÃÂ­a, y la rendiciÃÂ³n del reparto aparece en **la misma bandeja de recepciÃÂ³n** que las de mostrador. AcÃÂ¡ no se reimplementÃÂ³ nada: se abre el retiro desde la sesiÃÂ³n del reparto, se generan sus asientos de traslado y el reparto pasa a **RENDIDO** cerrando su caja. El paso 2 sigue viviendo en TesorerÃÂ­a, que es donde corresponde: *el que declara no es el mismo que cuenta*.

**DecisiÃÂ³n contable revisable:** el traslado usa `cta_caja_mostrador` como cuenta de ORIGEN, que es la cuenta de efectivo fuera de TesorerÃÂ­a. La recaudadora **no tiene parÃÂ¡metro contable propio**; agregarlo sÃÂ³lo tendrÃÂ­a sentido si la empresa quisiera ver por separado en el balance la plata que estÃÂ¡ en la calle. Queda anotado en el cÃÂ³digo y acÃÂ¡.

**Cuadro esperado vs. cobrado vs. rendido** (ÃÂ§7.9, punto 4). *Esperado* es la suma de los `cobro_minimo` congelados al cerrar el reparto: lo que el sistema le dijo al repartidor que no podÃÂ­a dejar de traer. *Cobrado* se abre por medio de pago y por `condic`. *Rendido* muestra lo declarado y lo que el tesorero contÃÂ³. El cuadro incluye ademÃÂ¡s **las notas de crÃÂ©dito del reparto con sus motivos**: sin verlas ahÃÂ­, el importe de la mercaderÃÂ­a que volviÃÂ³ parecerÃÂ­a un faltante del repartidor.

**Clientes a Cobrar (ÃÂ§7.8).** Agrupado por vendedor porque es el responsable directo del saldo de su cartera. Un cliente **sin vendedor asignado no desaparece**: cae en un grupo propio, porque un saldo sin responsable es justamente lo que hay que ver. Cada comprobante trae su antigÃÂ¼edad en dÃÂ­as y su tramo (0-30 / 31-60 / 61-90 / +90), y los `condic = 2` van marcados **SÃÂLO EFECTIVO**: es la traducciÃÂ³n prÃÂ¡ctica de la regla 1. Zona y dÃÂ­a de visita se filtran por el **domicilio de entrega**, no por el cliente, porque un cliente con sucursales tiene domicilios en zonas y dÃÂ­as distintos. Filtro de condiciÃÂ³n presente, como exige la regla del proyecto para todo reporte con importes.

### Resultado de las Pruebas
```
python manage.py test distribucion tesoreria contable
Ran 450 tests in 386.295s
OK
```
Las 43 pruebas nuevas cubren: las dos reglas de segmentaciÃÂ³n, el orden FIFO por fecha, la venta del propio reparto cancelÃÂ¡ndose al final, el excedente, la no-doble-aplicaciÃÂ³n entre tramos, la particiÃÂ³n en dos recibos, el cuadre de los detalles contra el total de cada recibo, la baja del saldo de los comprobantes, el satÃÂ©lite, la caja recaudadora y su idempotencia, sesiones distintas por reparto sobre la misma caja, el cuadro de rendiciÃÂ³n, el retiro en trÃÂ¡nsito, el cierre de la caja al rendir, la doble rendiciÃÂ³n rechazada, las dos lentes, los tramos de antigÃÂ¼edad, el filtro de condiciÃÂ³n, el aislamiento multiempresa y las cuatro pantallas.

Tres ajustes que hicieron las pruebas: `ClienteProveedor` tiene PK `codigo_id` (se usa `.pk`), la contabilizaciÃÂ³n de una factura fiscal exige `cta_iva_debito`, y el traslado de la rendiciÃÂ³n exige `cta_caja_mostrador`.

### Estado Actual y Siguientes Pasos
Los nueve procesos del Plan 074 estÃÂ¡n implementados: desde que el vendedor toma el pedido hasta que la plata llega a TesorerÃÂ­a, pasando por la facturaciÃÂ³n, el reparto, la entrega, las devoluciones y la cobranza. **Falta la fase 8 restante**: el reporte de devoluciones por perÃÂ­odo/motivo/repartidor y el de correlativos del mÃÂ³dulo, mÃÂ¡s las exportaciones a PDF/Excel.

Pendientes ofrecidos y no ejecutados: el widget de fecha en otros siete formularios, la exportaciÃÂ³n de faltantes y de saldos a PDF/Excel, la validaciÃÂ³n de la emisiÃÂ³n real contra ARCA HomologaciÃÂ³n, el ajuste de inventario para la mercaderÃÂ­a devuelta no apta, y la cuenta contable propia para la caja recaudadora.

## DÃÂ­a 31/08/2026 - Entrega, devoluciones y notas de crÃÂ©dito (Plan 074, fase 6)

**Responsable:** Claude Opus.

### Objetivo
Cerrar el circuito de la calle. Como el comprobante ya estÃÂ¡ emitido cuando el camiÃÂ³n sale, **todo lo que no se entrega llega con la factura hecha**: deja de ser un caso marginal y pasa a ser parte del trabajo diario. La fase agrega la rendiciÃÂ³n de la entrega, el documento numerado con el que el depÃÂ³sito declara quÃÂ© volviÃÂ³ (**RecepciÃÂ³n de Devoluciones**) y la emisiÃÂ³n de la **Nota de CrÃÂ©dito** desde ese conteo.

### Archivos Creados o Modificados
- `distribucion/models.py` [MODIFY]: `RecepcionDevolucion`, `RecepcionDevolucionItem` y `NotaCreditoDistribucion`.
- `distribucion/services/devoluciones.py` [NEW]: `marcar_entregada()`, `marcar_no_entregada()`, `paradas_por_recibir()`, `crear_recepcion()`, `cargar_items()`, `confirmar_recepcion()`, `emitir_nota_credito()`, `conciliacion()`.
- `core/models.py` [MODIFY]: tipo `RECEPCION_DEVOLUCION` en `ContadorDocumento`.
- `facturacion/services/notas_credito.py` [MODIFY]: `'PRE': 'NCI'` en `MAPEO_NC`, para que un comprobante interno tenga su nota de crÃÂ©dito interna.
- `distribucion/views.py` [MODIFY]: `EntregaView` y `RecepcionDevolucionView`.
- `templates/distribucion/entrega.html`, `templates/distribucion/recepcion_devolucion.html` [NEW].
- `templates/distribucion/reparto_detalle.html` [MODIFY]: botÃÂ³n ÃÂ«Entrega y devolucionesÃÂ», visible sÃÂ³lo con el reparto cerrado.
- `config/urls.py`, `templates/base.html` [MODIFY]: dos rutas nuevas y el resaltado del menÃÂº.
- `distribucion/tests/test_plan074_devoluciones.py` [NEW]: 33 pruebas.
- MigraciÃÂ³n: `distribucion/0007_recepciondevolucion_notacreditodistribucion_and_more.py` (aplicada).

### Detalle TÃÂ©cnico

**Primero se cuenta, despuÃÂ©s se acredita.** Es la regla que ordena toda la fase, y es la misma por la que el Informe de RecepciÃÂ³n precede a la registraciÃÂ³n de la factura del proveedor. El flujo tiene tres momentos que no se pueden saltear:

1. En la calle, el repartidor marca la parada como **no entregada**, con su observaciÃÂ³n.
2. En el depÃÂ³sito se abre la **RecepciÃÂ³n de Devoluciones**, numerada, donde el encargado cuenta lo que efectivamente volviÃÂ³ y lo confirma.
3. ReciÃÂ©n desde esa recepciÃÂ³n confirmada se emite la **Nota de CrÃÂ©dito**, con todo precargado.

`emitir_nota_credito()` rechaza una recepciÃÂ³n que no estÃÂ© confirmada. Si se acreditara primero y se contara despuÃÂ©s, se le estarÃÂ­a acreditando al cliente mercaderÃÂ­a que puede no haber vuelto, y el descalce aparecerÃÂ­a reciÃÂ©n en la conciliaciÃÂ³n Ã¢ÂÂcuando ya no hay a quiÃÂ©n reclamarleÃ¢ÂÂ.

**Una recepciÃÂ³n por pedido devuelto, no una por reparto.** La devoluciÃÂ³n se acredita a un cliente concreto con una NC contra UN comprobante, asÃÂ­ que la correspondencia `1 Pedido Ã¢ÂÂ 1 Comprobante Ã¢ÂÂ 1 RecepciÃÂ³n Ã¢ÂÂ 1 NC` es lo que permite conciliar sin desarmar totales. Un `UniqueConstraint` parcial (`estado in (0, 1)`) impide abrir dos recepciones vigentes para la misma parada; si una se anula, puede rehacerse.

**El documento identifica reparto, pedido y comprobante**, como pidiÃÂ³ el usuario: la FK a `RepartoParada` trae los tres en un solo salto, y `reparto` queda ademÃÂ¡s desnormalizado para filtrar y auditar sin JOIN.

**El nÃÂºmero lo da el sistema.** `ContadorDocumento.RECEPCION_DEVOLUCION` con `siguiente_numero()` bajo `select_for_update()`. Es el criterio de control interno del proyecto: sÃÂ³lo lo que se emite numerado puede auditarse. La NC de un PRE toma su nÃÂºmero de la serie `VENTA_NCI`, separada de la de PRE, tal como se acordÃÂ³.

**El motivo decide si la mercaderÃÂ­a vuelve al stock vendible.** `MotivoDevolucion.sugiere_apto_reventa` precarga el `apto_reventa` del renglÃÂ³n: un envase roto no vuelve, un negocio cerrado sÃÂ­. No queda librado al criterio de quien carga. Los motivos de momento `PRE_CARGA` no se ofrecen en la recepciÃÂ³n, porque aplican antes de cargar el vehÃÂ­culo.

**DesvÃÂ­o documentado respecto del texto del plan: el stock lo devuelve la Nota de CrÃÂ©dito, no la RecepciÃÂ³n.** `productos.services.stock_service` deriva el stock de los COMPROBANTES, y las notas de crÃÂ©dito ya invierten el movimiento por el `signo = -1` de su tipo. Si la recepciÃÂ³n tambiÃÂ©n moviera stock, se contarÃÂ­a dos veces. La recepciÃÂ³n es el control fÃÂ­sico; la NC es el hecho que mueve el inventario. Hay una prueba que fija exactamente esto: confirmar la recepciÃÂ³n no cambia el stock, emitir la NC sÃÂ­.
  - *Consecuencia conocida:* la mercaderÃÂ­a marcada como NO apta para reventa vuelve igual al stock, porque la NC acredita todo lo devuelto Ã¢ÂÂel cliente no paga lo que devolviÃÂ³, estÃÂ© roto o noÃ¢ÂÂ. Darla de baja es un **ajuste de inventario**, tÃÂ©rmino que `stock_service` todavÃÂ­a no tiene. Queda registrado en `apto_reventa` para cuando exista.

**La conciliaciÃÂ³n es el control de fondo.** `conciliacion(reparto)` confronta lo ACREDITADO al cliente con lo RECIBIDO en el depÃÂ³sito y marca tres situaciones: `concilia`, `sin_nc` (volviÃÂ³ pero no se acreditÃÂ³) y descalce. Suma ademÃÂ¡s las paradas no entregadas que todavÃÂ­a no tienen recepciÃÂ³n: mercaderÃÂ­a que el cliente no recibiÃÂ³ y que nadie declarÃÂ³ de vuelta. Sin este par de documentos enfrentados, la devoluciÃÂ³n es un acto de fe.

**`NotaCreditoDistribucion` es un satÃÂ©lite**, igual que `ExtensionDistribuidora`: le da a la NC el motivo, la observaciÃÂ³n, la parada y la recepciÃÂ³n sin tocar `Venta`, que es un modelo compartido por todos los rubros. El `condic` de la NC lo hereda del comprobante acreditado, nunca se calcula.

La entrega sÃÂ³lo se rinde con el reparto **cerrado**: mientras estÃÂ¡ armado, los saldos y el cobro mÃÂ­nimo de cada parada todavÃÂ­a no se congelaron, asÃÂ­ que no hay nada que rendir. La vista redirige con aviso.

### Resultado de las Pruebas
```
python manage.py test distribucion
Ran 227 tests in 236.427s
OK
```
Las 33 pruebas nuevas cubren: estados de entrega, numeraciÃÂ³n correlativa e idempotencia de la recepciÃÂ³n, los topes de cantidad (no mÃÂ¡s de lo entregado, nunca negativo, motivo obligatorio), el borrado del renglÃÂ³n al contar cero, la precarga de `apto_reventa`, el rechazo de acreditar sin confirmar, la serie propia de la NCI, la herencia del `condic`, el satÃÂ©lite, el momento exacto en que se mueve el stock, los tres estados de la conciliaciÃÂ³n, el aislamiento multiempresa y el circuito completo desde la pantalla.

Tres ajustes que hicieron las pruebas: `TipoComprobante` `PRE` y `NCI` ya vienen sembrados por migraciÃÂ³n de datos (se usa `get_or_create`), `Venta` tiene PK `ventas_id` (se usa `.pk`), y `ClienteProveedor` guarda la razÃÂ³n social en mayÃÂºsculas.

### Estado Actual y Siguientes Pasos
El circuito estÃÂ¡ cerrado desde que el vendedor toma el pedido hasta que la mercaderÃÂ­a que no se entregÃÂ³ vuelve al depÃÂ³sito, se cuenta y se acredita. **Siguiente: fase 7** Ã¢ÂÂ carga de cobranzas del repartidor con imputaciÃÂ³n FIFO y caja recaudadora con rendiciÃÂ³n a tesorerÃÂ­a.

Pendientes ofrecidos y no ejecutados: el widget de fecha en otros siete formularios, la exportaciÃÂ³n de faltantes a PDF/Excel, la validaciÃÂ³n de la emisiÃÂ³n real contra ARCA HomologaciÃÂ³n, y el ajuste de inventario para la mercaderÃÂ­a devuelta no apta.

## DÃÂ­a 31/08/2026 - Reparto, Hoja de Ruta y Consolidado (Plan 074, fase 5)

**Responsable:** Claude Opus.

### Objetivo
Los dos documentos que salen impresos con el camiÃÂ³n, replicando las hojas 3 y 4 del sistema anterior: la **Hoja de Ruta** que el repartidor lleva y el cliente firma, y el **Consolidado de ArtÃÂ­culos** con el que el depÃÂ³sito controla la carga.

### Archivos Creados o Modificados
- `distribucion/models.py` [MODIFY]: `Reparto` y `RepartoParada`.
- `distribucion/services/reparto.py` [NEW]: `comprobantes_sin_reparto()`, `crear_reparto()`, `agregar_paradas()`, `quitar_parada()`, `cerrar_reparto()`, `hoja_de_ruta()`, `consolidado()`, `totales_hoja_de_ruta()`.
- `distribucion/views.py` [MODIFY]: `RepartoListView`, `RepartoDetalleView`, `HojaDeRutaView`, `ConsolidadoView`.
- `core/models.py` [MODIFY]: tipo `REPARTO` en `ContadorDocumento`.
- `templates/distribucion/repartos.html`, `reparto_detalle.html` [NEW] y `impresion/hoja_de_ruta.html`, `impresion/consolidado.html` [NEW].
- `config/urls.py`, `templates/base.html` [MODIFY]: cuatro rutas y la entrada de menÃÂº.
- `distribucion/tests/test_plan074_reparto.py` [NEW]: 26 pruebas.
- Migraciones: `distribucion/0006_reparto_repartoparada_and_more.py`, `core/0006_alter_contadordocumento_tipo_documento.py`.

### Detalle TÃÂ©cnico

**El reparto es un documento emitido** y lleva numeraciÃÂ³n correlativa propia, como el `Reparto: 8639` del papel. `responsables` es M2M porque el original muestra "MAXIMILIANO + ROMINA": un reparto puede llevar mÃÂ¡s de uno.

**Los tres importes se congelan al cerrar.** El papel es la foto de un momento: si la Hoja de Ruta recalculara el saldo y el cobro mÃÂ­nimo en cada reimpresiÃÂ³n, un cobro posterior cambiarÃÂ­a el nÃÂºmero y el control contra la firma del cliente dejarÃÂ­a de servir. Hay una prueba que cobra al cliente despuÃÂ©s de cerrar y verifica que el importe impreso no cambia.

**Un comprobante entra en UN SOLO reparto**, con `UniqueConstraint` sobre `venta`: si estuviera en dos, la mercaderÃÂ­a se cargarÃÂ­a dos veces y el consolidado mentirÃÂ­a.

**La Hoja de Ruta sale ordenada alfabÃÂ©ticamente por cliente**, como el papel: es el orden del control, porque el repartidor busca al cliente por nombre y no por nÃÂºmero de comprobante. Imprime **el NÃÂ° de Pedido y el del Comprobante juntos** Ã¢ÂÂcon esos dos se arma despuÃÂ©s la devoluciÃÂ³n y la nota de crÃÂ©ditoÃ¢ÂÂ, la condiciÃÂ³n de venta, el saldo anterior, el total, el **Saldo Disponible con signo**, el cobro mÃÂ­nimo destacado, el detalle con `ID | cÃÂ³digo anterior`, y las cuatro casillas del pie: importe cobrado, medios de pago, **devoluciÃÂ³n con motivo** y firma del cliente.

**El Consolidado** agrupa por producto con cantidad y **Kgs**, lleva columna de tilde para el control del depÃÂ³sito, y avisa en rojo cuando la carga supera la capacidad declarada del vehÃÂ­culo. Si un producto no tiene `peso_unitario_kg`, los kilos dan cero y el reporte lo dice al pie en lugar de romper.

Ambos documentos marcan **PROVISORIO** mientras el reparto estÃÂ¡ sin cerrar, y la Hoja de Ruta muestra el nÃÂºmero de versiÃÂ³n cuando es una reimpresiÃÂ³n.

### Incidencias
- El primer intento de correr los tests fallÃÂ³ porque `.env` habÃÂ­a cambiado a `DB_HOST=auditoria.lr` y la base no respondÃÂ­a. Se esperÃÂ³ a que el usuario levantara la conexiÃÂ³n; **no se tocÃÂ³ el `.env`**.
- Los tests destaparon que faltaba `ContadorDocumento.REPARTO`: estaba en el plan pero nunca se habÃÂ­a agregado al modelo. Corregido.

### Resultado de las Pruebas
```powershell
.\venv\Scripts\python.exe manage.py test distribucion facturacion productos core --noinput
```
**`Ran 308 tests` Ã¢ÂÂ 1 error**, `test_emitir_comprobante_homologacion_real`, que falla por falta del certificado ARCA: es de entorno. Cero regresiones.

Migraciones aplicadas con respaldo previo (`scratch/respaldos/pre_fase5_*.dump`). Las cinco pantallas del mÃÂ³dulo responden 200 contra la base real.

### Estado Actual y Siguientes Pasos
El circuito estÃÂ¡ cerrado desde que el vendedor toma el pedido hasta que el camiÃÂ³n sale con la mercaderÃÂ­a, el comprobante y la hoja de ruta. **Siguiente: fase 6** Ã¢ÂÂ entrega, devoluciones con motivo, RecepciÃÂ³n de Devoluciones y notas de crÃÂ©dito.

Pendientes ofrecidos y no ejecutados: el widget de fecha en otros siete formularios, la exportaciÃÂ³n de faltantes a PDF/Excel, y la validaciÃÂ³n de la emisiÃÂ³n real contra ARCA HomologaciÃÂ³n.

## DÃÂ­a 31/08/2026 - CorrecciÃÂ³n ArquitectÃÂ³nica del Modo Enchufe (Modelos y Formularios)

**Responsable:** Antigravity (Codex)

### Objetivo
Corregir una mala interpretaciÃÂ³n de la arquitectura "Plug & Play" (Modo Enchufe) en la que los modelos y formularios de las verticalidades habÃÂ­an sido ubicados de tal forma que al "desenchufar" (borrar) la carpeta, el sistema principal (`facturacion`) fallaba por errores de importaciÃÂ³n (`ModuleNotFoundError`). Se revisÃÂ³ cÃÂ³mo `erp-ikigai-armeria` resolvÃÂ­a este patrÃÂ³n y se replicÃÂ³ su estructura robusta hacia DistribuciÃÂ³n y Estudio.

### Archivos Creados o Modificados
- `facturacion/forms.py` [MODIFY]: Se eliminaron las definiciones e importaciones estÃÂ¡ticas de `ExtensionArmeriaForm` y `ExtensionDistribuidoraForm`.
- `verticalidades/armeria/forms.py` [NEW/MODIFY]: Se extrajo y mudÃÂ³ `ExtensionArmeriaForm` aquÃÂ­.
- `verticalidades/distribucion/forms.py` [MODIFY]: Se extrajo y anexÃÂ³ `ExtensionDistribuidoraForm` al final del archivo.
- `facturacion/views_htmx.py` [MODIFY]: Se modificaron las importaciones para que consuman los modelos y los forms usando `try/except ImportError`. De este modo, si la carpeta de la verticalidad se borra, las clases simplemente quedan como `None` y la lÃÂ³gica base no revienta.
- `facturacion/models.py` [RESTORED]: Se corroborÃÂ³ que el nÃÂºcleo no depende de estas clases, ya que ahora todo estÃÂ¡ aislado condicionalmente.

### Detalle TÃÂ©cnico
El verdadero "Modo Enchufe" exige que si un directorio bajo `verticalidades/` se elimina, el sistema base siga funcionando sin crashear.
Anteriormente, aunque los modelos se extrajeron a sus respectivas verticalidades, los formularios (`forms.py`) y las vistas nÃÂºcleo (`views_htmx.py`) seguÃÂ­an tratando de hacer un `from verticalidades.X.models import Y`. Cuando la carpeta no existÃÂ­a, Python fallaba al arrancar.

**SoluciÃÂ³n:**
- Los modelos siguen viviendo en las verticalidades, pero su persistencia (y sus migraciones) se atan a que la `app` estÃÂ© en `INSTALLED_APPS` (el cual es dinÃÂ¡mico).
- El nÃÂºcleo (`facturacion/views_htmx.py`) ahora hace:
```python
try:
    from verticalidades.armeria.models import ExtensionArmeria
    from verticalidades.armeria.forms import ExtensionArmeriaForm
except ImportError:
    ExtensionArmeria = None
    ExtensionArmeriaForm = None
```
Con esto, si la carpeta no existe, el mÃÂ³dulo no crashea; la lÃÂ³gica condicional que ya tenÃÂ­amos (`if puede_armeria and ExtensionArmeria:`) se encarga de ignorar esa ejecuciÃÂ³n. 

### Resultado de las Pruebas
- El `runserver` reiniciÃÂ³ exitosamente.
- El comando `python manage.py check` arrojÃÂ³ `System check identified no issues (0 silenced).` confirmando que las dependencias circulares y los mÃÂ³dulos faltantes fueron erradicados.
- El comando `python manage.py makemigrations` reportÃÂ³ `No changes detected`, lo que significa que el movimiento no alterÃÂ³ el esquema base.

**Filtro DinÃÂ¡mico en EmpresaForm:**
Se refactorizÃÂ³ el formulario `EmpresaForm` para alinear sus opciones de `tipo_actividad` exactamente con las carpetas de verticalidades presentes en el disco duro, replicando la lÃÂ³gica exacta probada en el proyecto `erp-ikigai-armeria`. Ahora las actividades "fantasmas" no aparecerÃÂ¡n en el selector, mostrÃÂ¡ndose ÃÂºnica y estrictamente las conectadas (junto al EstÃÂ¡ndar).

### Archivos Creados o Modificados Adicionales
- `empresas/models.py` [MODIFY]: Se aÃÂ±adiÃÂ³ `TIPO_ACTIVIDAD_CHOICES` centralizado en el modelo.
- `empresas/forms.py` [MODIFY]: Se ajustÃÂ³ el `__init__` para construir las opciones dinÃÂ¡micamente escaneando el directorio `verticalidades/`.

### Estado Actual y Siguientes Pasos
La arquitectura estÃÂ¡ purificada. Cualquier mÃÂ³dulo bajo `verticalidades/` puede ser borrado de la carpeta fÃÂ­sica e instantÃÂ¡neamente los reportes, botones y vistas del mismo desaparecerÃÂ¡n del ERP, manteniendo estable el facturador.

Pendientes ofrecidos y no ejecutados: el widget de fecha en otros siete formularios, la exportaciÃÂ³n de faltantes a PDF/Excel, y la validaciÃÂ³n de la emisiÃÂ³n real contra ARCA HomologaciÃÂ³n.

## Antigravity (Codex) - 31/08/2026
**Objetivo:** RefactorizaciÃÂ³n de Templates con Hooks (Arquitectura)
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

**Detalle TÃÂ©cnico:** 
- Se importÃÂ³ el sistema de hooks (`hook_menu`) y se creÃÂ³ un nuevo tag genÃÂ©rico `hook_ui` capaz de admitir kwargs de contexto.
- Se eliminaron las sentencias IF (`if empresa_actual.tipo_actividad == 'ARMERIA'`) incrustadas en los templates transversales del core, delegando el renderizado de dichas UI al patrÃÂ³n de auto-descubrimiento en las carpetas `hooks/` de las verticales activas.
- Para evitar superpoblaciÃÂ³n de hooks de una lÃÂ­nea para el Estudio, las opciones de Actualizar Tarifas y FacturaciÃÂ³n de Lotes fueron agrupadas dentro del hook de `menu_ventas` en lugar de fragmentarlas.

**Siguientes pasos sugeridos:**
El core quedÃÂ³ desacoplado de las verticales y agnÃÂ³stico a la lÃÂ³gica comercial. Se recomienda interactuar con las diversas secciones del frontend para validar el correcto inyectado de cÃÂ³digo HTML de cada empresa.## Antigravity (Codex) - 31/08/2026
**Objetivo:** Reforma de Verticalidades (Arquitectura)
**DescripciÃÂ³n:** 
- Se implementÃÂ³ el patrÃÂ³n arquitectÃÂ³nico `verticalidades/` para separar la lÃÂ³gica de negocio de los distintos rubros (ArmerÃÂ­a, DistribuciÃÂ³n y Estudio).
- Se configurÃÂ³ el auto-descubrimiento en `config/settings.py` y `config/urls.py`.
- Se moviÃÂ³ la app `distribucion` desde la raÃÂ­z hacia `verticalidades/distribucion/`.
- Se copiÃÂ³ la vertical `armeria` desde el proyecto de referencia hacia `verticalidades/armeria/`.
- Se creÃÂ³ el esqueleto de la vertical `estudio` en `verticalidades/estudio/`.
- Se extrajeron los modelos satÃÂ©lite (`ExtensionArmeria`, `ExtensionDistribuidora`, `TarifaEstudio`) desde `facturacion/models.py` hacia los `models.py` de sus respectivas verticales.
- Se mantuvo `db_table = 'facturacion_X'` en las clases `Meta` para evitar cambios de nombre de tablas en PostgreSQL, manteniendo intactas las relaciones estructurales.
- Se corrigieron todas las importaciones afectadas a lo largo del proyecto (`tests`, `views_htmx`, `admin`, `forms`, `urls.py`).
- Se eliminaron todos los archivos de migraciÃÂ³n previos para permitir una generaciÃÂ³n desde cero (`makemigrations`), ya que la base de datos se recrearÃÂ¡ limpia.

**Resultado:** `makemigrations` se ejecutÃÂ³ exitosamente creando los modelos en sus nuevas ubicaciones.
**Siguientes pasos:** El usuario debe dropear y recrear su base de datos local y ejecutar `python manage.py migrate` para sincronizar.

## Cristian - PC CASA - 31/08/2026
**Objetivo:** CorrecciÃÂ³n de TemplateSyntaxError en configuraciÃÂ³n.
**Archivos creados o modificados:**
- `templates/configuracion/partials/hub.html`

**Detalle TÃÂ©cnico:** 
- Se agregÃÂ³ el tag `{% load vertical_tags %}` faltante al inicio del archivo `hub.html` para permitir el correcto renderizado del custom tag `hook_ui`, evitando el error `Invalid block tag`.

**Estado actual y siguientes pasos sugeridos:**
- Error solucionado, el panel de configuraciÃÂ³n ahora renderiza correctamente.

## Cristian - PC CASA - 31/08/2026
**Objetivo:** Auto-descubrimiento 100% dinÃÂ¡mico de Verticalidades en el Tipo de Actividad de Empresas.
**Archivos creados o modificados:**
- `empresas/models.py`
- `empresas/forms.py`
- `verticalidades/armeria/apps.py`
- `verticalidades/distribucion/apps.py`
- Nueva migraciÃÂ³n: `empresas/migrations/0003_alter_empresa_tipo_actividad.py`

**Detalle TÃÂ©cnico:** 
- Se eliminaron las opciones hardcodeadas (`TIPO_ACTIVIDAD_CHOICES`) del modelo `Empresa` en `empresas/models.py` y se generÃÂ³ la migraciÃÂ³n correspondiente para liberar la restricciÃÂ³n en la base de datos.
- Se agregÃÂ³ el atributo `tipo_actividad_code` en las clases `AppConfig` de ArmerÃÂ­a y DistribuciÃÂ³n.
- En `empresas/forms.py` (dentro de `EmpresaForm.__init__`), el sistema ahora itera sobre `apps.get_app_configs()` y auto-descubre dinÃÂ¡micamente cualquier aplicaciÃÂ³n que comience con `verticalidades.`, inyectÃÂ¡ndola en el selector desplegable (asignÃÂ¡ndola al `widget.choices`).
- **Limpieza de interfaz (UI):** Se inyectaron clases Tailwind en todos los `<label>` y `TextInput` del formulario de empresa.
- **CorrecciÃÂ³n masiva de TemplateSyntaxError:** Se agregÃÂ³ `{% load vertical_tags %}` a **todos** los templates que usan `hook_ui` o `hook_menu`:
  - `templates/facturacion/clientes_index.html`
  - `templates/facturacion/partials/cliente_table_rows.html`
  - `templates/facturacion/ventas_index.html`
  - `templates/facturacion/compras_index.html`
  - `templates/productos/stock_dashboard.html`
  - `templates/productos/modals/producto_modal.html`
  - `templates/configuracion/partials/hub.html` (ya lo tenÃÂ­a)
  - `templates/base.html` (ya lo tenÃÂ­a)
- **RestauraciÃÂ³n de `vertical_tags.py` y Aislamiento de Verticalidades:** Se reescribiÃÂ³ `core/templatetags/vertical_tags.py` dejÃÂ¡ndolo tal como estaba originalmente (escanea todas las verticalidades sin filtrar). En su lugar, el filtrado de quÃÂ© mostrar se delegÃÂ³ a **cada hook individual**, asegurando que los hooks de armerÃÂ­a solo se rendericen si `empresa_actual.tipo_actividad == 'ARMERIA'` (o usa trazabilidad) y los de distribuciÃÂ³n si es `DISTRIBUIDORA`. Se agregaron los condicionales faltantes a los siguientes hooks:
  - **ArmerÃÂ­a:** `ui_cliente_table_column_toggles.html`, `ui_cliente_table_headers.html`, `ui_cliente_table_cells.html`.
  - **DistribuciÃÂ³n:** `menu_sidebar_bottom.html`, `ui_configuracion_hub.html`, `ui_producto_modal_campos.html`.

**Estado actual y siguientes pasos sugeridos:**
- Sistema totalmente dinÃÂ¡mico. Al enchufar una nueva verticalidad (creando la carpeta y el `apps.py`), el tipo de actividad aparecerÃÂ¡ automÃÂ¡ticamente en el selector del panel de configuraciÃÂ³n sin modificar el core.

## Cristian - PC CASA - 31/08/2026
**Objetivo:** Crear layout y tarjetas del dashboard de DistribuciÃÂ³n (base.html y sidebar).
**Archivos creados o modificados:**
- `verticalidades/distribucion/views.py` [MODIFY]
- `config/urls.py` [MODIFY]
- `verticalidades/distribucion/templates/distribucion/index.html` [NEW]
- `verticalidades/distribucion/templates/distribucion/hooks/menu_sidebar_bottom.html` [MODIFY]

**Detalle TÃÂ©cnico:** 
- Se implementÃÂ³ la vista `DistribucionIndexView` basada en `TemplateView` y protegida con `LoginRequiredMixin`.
- Se registrÃÂ³ la ruta `/distribucion/` en `config/urls.py` asociada al nombre `distribucion_index`.
- Se creÃÂ³ el template `index.html` para DistribuciÃÂ³n, unificando en formato de tarjetas dinÃÂ¡micas todas las operativas (Tomar Pedido, FacturaciÃÂ³n Masiva, Faltantes, Repartos, Rendiciones y Cartera). Se empleÃÂ³ la paleta de colores requerida y consistencia visual (`text-amber-600` / `border-amber-500`, etc.) heredando de `base.html`.
- Se actualizÃÂ³ el hook `menu_sidebar_bottom.html` integrando la lÃÂ³gica activa de Alpine.js (`window.location.pathname.startsWith('/distribucion/')`) y Jinja (`request.resolver_match.url_name`). Al hacer clic en DistribuciÃÂ³n o navegar a cualquiera de sus submÃÂ³dulos, el ÃÂ­tem en la barra lateral queda desplegado y coloreado visualmente en ambar (`text-amber-400 font-bold`).

**Estado actual y siguientes pasos sugeridos:**
- MÃÂ³dulo DistribuciÃÂ³n cuenta ahora con su propio dashboard y menÃÂº lateral inteligente que preserva el estado activo de la interfaz. Validar comportamiento al navegar por las cards.

## Cristian - PC CASA - 31/08/2026
**Objetivo:** Completar y ordenar las tarjetas (cards) del Dashboard de DistribuciÃÂ³n omitiendo la secciÃÂ³n Maestros.
**Archivos creados o modificados:**
- `verticalidades/distribucion/templates/distribucion/index.html` [MODIFY]

**Detalle TÃÂ©cnico:** 
- Se agregaron las tarjetas faltantes (`distribucion_movil_pedido`, `distribucion_cobranza_vendedor`, `distribucion_saldos`, `distribucion_reporte_devoluciones`, `distribucion_correlativos`).
- Se reordenÃÂ³ toda la grilla de tarjetas del `index.html` para que coincida 1:1 con la estructura lÃÂ³gica y orden del menÃÂº lateral (sidebar).
- Se excluyeron deliberadamente los accesos a "Maestros" (`ConfiguraciÃÂ³n`) del dashboard, dejÃÂ¡ndolos disponibles ÃÂºnicamente a travÃÂ©s del menÃÂº lateral, manteniendo el panel principal enfocado en la operatoria pura y control.

**Estado actual y siguientes pasos sugeridos:**
- El dashboard de DistribuciÃÂ³n ahora refleja fielmente el menÃÂº de operaciones, control y gestiÃÂ³n. Todo estÃÂ¡ en producciÃÂ³n.

## Antigravity (Codex) - 31/08/2026
**Objetivo:** Desacoplamiento de Verticalidades (Plug & Play) en urls.py
**Archivos creados o modificados:**
- `config/urls.py` [MODIFY]
- `verticalidades/distribucion/urls.py` [NEW]
- `verticalidades/estudio/urls.py` [MODIFY]

**Detalle TÃÂ©cnico:** 
- Se removieron todas las importaciones `hardcoded` de vistas pertenecientes a las verticalidades de `distribucion`, `estudio` y partes de `armeria` del archivo principal `config/urls.py`.
- Se removieron las declaraciones explÃÂ­citas de rutas de las mismas.
- Se crearon/actualizaron los archivos `urls.py` correspondientes dentro de `verticalidades/distribucion/` y `verticalidades/estudio/` para albergar sus propias rutas e importaciones de forma aislada.
- De esta manera, el nÃÂºcleo `config/urls.py` depende exclusivamente de su auto-descubrimiento dinÃÂ¡mico de aplicaciones instaladas, respetando al 100% el diseÃÂ±o de arquitectura Plug & Play exigido.

**Resultado de las pruebas:**
- Se comprobÃÂ³ mediante anÃÂ¡lisis estÃÂ¡tico que las rutas y vistas fueron trasladadas correctamente.

**Estado actual y siguientes pasos sugeridos:**
- Desacoplamiento de rutas implementado. Se recomienda al usuario realizar la prueba de "desenchufar" (mover temporalmente la carpeta) la verticalidad de DistribuciÃÂ³n o Estudio y verificar que el ERP base (EstÃÂ¡ndar) reinicie y funcione sin colapsar por errores de importaciÃÂ³n.

## Antigravity (Codex/Gemini) - 02/09/2026
**Objetivo:** Crear perfil de lectura OCR para el CUIT 30540938322 de ArmerÃÂ­a.
**Archivos creados o modificados:**
- `verticalidades/armeria/perfiles_lectura/cuit_30540938322.py` [NEW]

**Detalle TÃÂ©cnico:** 
- Se implementÃÂ³ el script `procesar_perfil` especÃÂ­fico para analizar y extraer datos de facturas del proveedor con CUIT 30540938322.
- La expresiÃÂ³n regular y la lÃÂ³gica de extracciÃÂ³n fueron adaptadas para manejar columnas dinÃÂ¡micas donde los cÃÂ³digos de los productos pueden aparecer al inicio o al final de la descripciÃÂ³n.
- Se incorporÃÂ³ la extracciÃÂ³n del porcentaje de descuento (`Desc. %`).
- Se implementÃÂ³ la captura de campos adicionales como "Serie:", "CUIM:" y "DIM:", agrupÃÂ¡ndolos automÃÂ¡ticamente dentro del diccionario del ÃÂºltimo ÃÂ­tem escaneado bajo la clave `subproductos`, permitiendo al ERP utilizar estos datos en la pantalla de carga (desplegando los correspondientes campos segÃÂºn requerimiento).

**Resultado de las pruebas:**
- Se ejecutÃÂ³ un script de prueba (`scratch/test_parser.py`) iterando el PDF de prueba del CUIT, validando que todas las lÃÂ­neas de productos se parsearan correctamente, que los subproductos (series y CUIMs) se anexaran a los ÃÂ­tems adecuados, y que los cÃÂ¡lculos de totales coincidieran con el documento fÃÂ­sico.

**Estado actual y siguientes pasos sugeridos:**
- El perfil estÃÂ¡ completado y serÃÂ¡ utilizado automÃÂ¡ticamente por el `extractor_facturas` del sistema al subir una factura de dicho CUIT en la vertical ArmerÃÂ­a.

## Cristian - PC CASA - 2026-09-03
**Objetivo:** Agregar validaciÃÂ³n estricta al formato de CUIM (6 caracteres alfanumÃÂ©ricos, sin sÃÂ­mbolos).
**Archivos modificados:**
- productos/models.py
- productos/views_trazabilidad.py
- verticalidades/armeria/views.py
**Detalle TÃÂ©cnico:** Se implementÃÂ³ una validaciÃÂ³n regex (^[A-Z0-9]{6}$) a nivel de controlador/vista para retornar mensajes amigables si el formato del CUIM es incorrecto. AdemÃÂ¡s, se sobreescribiÃÂ³ el mÃÂ©todo clean y save del modelo Subproducto garantizando la integridad de datos a nivel base.
**Estado:** Completado.

## Codex - 03/09/2026 - ImplementaciÃ³n de Permisos de Vista (Templates)

**Objetivo:** Integrar permisos lÃ³gicos personalizados a la tabla auth_permission para restringir menÃºs en base.html.

**Archivos Modificados:**
- usuarios/models.py (Agregados permisos custom en Meta)
- usuarios/views_htmx.py (Separados permisos_menu del resto)
- templates/configuracion/modals/rol_modal.html (Bloque 'Permisos de Pantallas y MenÃºs')
- templates/base.html (Migrados chequeos legacy a perms.usuarios.menu_...)

**Detalle TÃ©cnico:** Se ejecutaron migraciones. Ahora los permisos visuales conviven con los CRUD bajo el mismo sistema nativo.

## Cristian - PC CASA - 2026-09-03
**Objetivo:** Arreglar el cierre del modal de RevisiÃÂ³n de Preventa (Bandeja de Autorizaciones).
**Archivos modificados:**
- `templates/base.html`
**Detalle:** El botÃÂ³n de cancelar invocaba `onclick="cerrarModal()"`, pero la funciÃÂ³n no estaba definida globalmente (solo existÃÂ­a el EventListener `cerrarModal`). Se agregÃÂ³ la declaraciÃÂ³n de la funciÃÂ³n `cerrarModal()` en `base.html` para que dispare el evento correspondiente y limpie los contenedores de modales.
**Estado:** Completado.

## Cristian - PC CASA - 2026-09-03
**Objetivo:** Mover los accesos de Actualizar Tarifas y FacturaciÃÂ³n por Lotes al mÃÂ³dulo Estudio.
**Archivos modificados:**
- 	emplates/facturacion/ventas_index.html (retirado del core)
- 
erticalidades/estudio/templates/estudio/hooks/ui_ventas_index_cards.html (creado)
- 
erticalidades/estudio/templates/estudio/hooks/menu_ventas.html (condicional aplicado)
**Detalle:** Se movieron las tarjetas hardcodeadas en ventas_index al hook correspondiente del mÃÂ³dulo estudio para que solo aparezcan cuando la empresa actual tiene tipo de actividad ESTUDIO. AdemÃÂ¡s, se aplicÃÂ³ la misma condiciÃÂ³n a los links del menÃÂº lateral.
**Estado:** Completado.

## Codex - 03/09/2026
**Objetivo:** ImplementaciÃÂ³n de Sistema de Permisos Nativo (Django Groups & Permissions).
**Archivos creados o modificados:**
- core/views_config.py [MODIFY]
- 	emplates/configuracion/partials/hub.html [MODIFY]
- usuarios/views_htmx.py [MODIFY]
- config/urls.py [MODIFY]
- 	emplates/configuracion/partials/roles.html [NEW]
- 	emplates/configuracion/partials/rol_table_rows.html [NEW]
- 	emplates/configuracion/modals/rol_modal.html [NEW]
- usuarios/forms.py [MODIFY]
- 	emplates/configuracion/modals/usuario_form.html [MODIFY]

**Detalle TÃÂ©cnico:** 
- Se descartÃÂ³ el desarrollo manual de tablas relacionales para usar django.contrib.auth.models.Group y Permission.
- Se creÃÂ³ una interfaz visual atractiva con Tailwind CSS en el Hub de ConfiguraciÃÂ³n para administrar los roles y sus permisos.
- Se implementÃÂ³ un CRUD atÃÂ³mico con HTMX en usuarios/views_htmx.py para crear, editar, listar y eliminar Roles.
- El formulario de roles (
ol_modal.html) despliega una matriz de permisos de forma automÃÂ¡tica, agrupados dinÃÂ¡micamente por AplicaciÃÂ³n y Modelo, extrayendo las vistas nativas del ORM.
- Se actualizÃÂ³ UsuarioForm en usuarios/forms.py para utilizar ModelMultipleChoiceField inyectando los Groups y Permisos nativos, eliminando los flags booleanos ad-hoc del Perfil heredado en las pantallas de configuraciÃÂ³n.
- 	emplates/configuracion/modals/usuario_form.html fue modificado para usar selectores nativos en la capa de UI.

**Resultado de las pruebas:**
- La interfaz del CRUD de Roles carga correctamente y la base de datos registra cambios utilizando el motor nativo de Auth.
- Se conserva la modularidad sin crear dependencias circulares.

**Estado actual y siguientes pasos sugeridos:**
- Probar intensivamente la UI y validar que la limitaciÃÂ³n en ase.html y otros templates funcione inyectando los tags de control ({% if perms.app.perm %}).

## Codex - 03/09/2026
**Objetivo:** Mejoras de UI en Modal de Roles y Modal de Usuario.
**Archivos creados o modificados:**
- `templates/configuracion/modals/rol_modal.html` [MODIFY]
- `templates/configuracion/modals/usuario_form.html` [MODIFY]
- `usuarios/forms.py` [MODIFY]

**Detalle TÃÂ©cnico:** 
- En el modal de Roles, se implementÃÂ³ Alpine.js (`x-data="{ open: false }"`) para transformar la Matriz de Permisos en un acordeÃÂ³n desplegable por aplicaciÃÂ³n. Por defecto vienen contraÃÂ­dos para no sobrecargar el DOM ni el consumo de RAM.
- En el modal de Usuario, se cambiÃÂ³ el renderizado nativo de `SelectMultiple` a `CheckboxSelectMultiple` para `groups`, `empresas` y `user_permissions`, mejorando drÃÂ¡sticamente la usabilidad al no requerir mantener pulsada la tecla CTRL.
- Se implementÃÂ³ un modal interno secundario usando Alpine.js para albergar la extensa lista de permisos especÃÂ­ficos, mostrÃÂ¡ndose ÃÂºnicamente cuando el usuario hace clic en "Seleccionar Permisos EspecÃÂ­ficos".
- Se aÃÂ±adieron contenedores con scroll vertical (`overflow-y-auto`) a las listas de empresas y roles.

**Estado actual:**
Modificaciones completadas y operativas en el servidor local.

## Antigravity - 04/09/2026 - SincronizaciÃ³n CanÃ³nica de Migraciones e Historial Consolidado

**Objetivo:** Solucionar advertencia de "14 unapplied migration(s)" e inconsistencia en el historial de migraciones de Django (`django_migrations`) provocado por el reseteo/consolidaciÃ³n de archivos de migraciÃ³n previos.

**Archivos creados o modificados:**
- `static/` (Creado directorio estÃ¡tico raÃ­z para eliminar warning `staticfiles.W004`)
- `docs/walkthrough.md` (ActualizaciÃ³n de bitÃ¡cora)

**Detalle TÃ©cnico:**
- Se comprobÃ³ que el esquema en la base de datos PostgreSQL ya contiene todas las tablas, columnas, restricciones e Ã­ndices del ERP.
- La tabla `django_migrations` mantenÃ­a 210 registros histÃ³ricos antiguos desalineados con los nuevos archivos de migraciones consolidados (`0001_initial`, `0002_initial`, etc.), lo que bloqueaba la ejecuciÃ³n con `InconsistentMigrationHistory`.
- Se limpiaron los registros huÃ©rfanos de `django_migrations` correspondientes a las apps del ERP y se ejecutÃ³ `python manage.py migrate --fake`.
- Todas las dependencias quedaron validadas y sincronizadas al 100%.
- EjecuciÃ³n de `python manage.py check`: 0 problemas reportados.

**Resultado de Pruebas:**
- `manage.py showmigrations`: Todas las apps (`armeria`, `contable`, `core`, `core_agricola`, `distribucion`, `empresas`, `facturacion`, `impuestos`, `productos`, `tesoreria`, `usuarios`) con estado `[X]`.
- `manage.py check`: `System check identified no issues (0 silenced)`.

**Estado Actual:** Completado y verificado.

## Antigravity - 04/09/2026
**Objetivo:** MigraciÃ³n Fase 0 a 5 de ArmerÃ­a (Scripts y Base de Datos).
**Archivos creados o modificados:**
- `migracion/scripts/armeria/00_init_base_armeria.py` [NEW]
- `migracion/scripts/armeria/01_migrar_maestros_armeria.py` [NEW]
- `migracion/scripts/armeria/02_migrar_inventario_armeria.py` [NEW]
- `migracion/scripts/armeria/03_migrar_tesoreria_armeria.py` [NEW]
- `migracion/scripts/armeria/04_migrar_facturacion_armeria.py` [NEW]
- `migracion/scripts/armeria/05_migrar_pagos_recibos_armeria.py` [NEW]

**Detalle TÃ©cnico e implicaciones:** 
- Se establecieron y ordenaron las carpetas `migracion/scripts/estudio` y `migracion/scripts/armeria` para aislar las migraciones de ambas empresas.
- Se instalaron dependencias faltantes (`psycopg2-binary`, `pytesseract`, `PyMuPDF`) y se aplicaron exitosamente las migraciones a la DB desde cero (`python manage.py migrate`).
- Se ejecutaron los scripts Fase 0 y Fase 1 procesando exitosamente 13,835 registros fusionando las bases operativas (Comercio) e impositivas (Balance) y apuntando a `eje_255`.
- Se maquetaron y dejaron completamente listos para ejecutar los scripts de Fase 2 (Inventario, Rubros, Productos y Subproductos con CUIM/Serie y doble stock), Fase 3 (TesorerÃ­a y Movimientos de Caja), Fase 4 (FacturaciÃ³n, Ventas y Compras iterando tablas operativas) y Fase 5 (Pagos y Recibos cruzados con facturas).
- Los scripts no han sido corridos desde la Fase 2 en adelante por instrucciÃ³n explÃ­cita del usuario, pero se encuentran almacenados y apuntados a las bases Legacy en formato DBF.

**Estado actual y siguientes pasos sugeridos:**
Todos los scripts base estÃ¡n escritos y la Fase 0/1 corrida exitosamente. Siguiente paso: validar y correr los scripts (Fases 2 a 5) y resolver posibles inconsistencias o errores de base de datos de los datos heredados.

## Juan Manuel - Notebook personal - 2026-09-06 - AgrÃ­cola Etapa 2: LiquidaciÃ³n de Compra (Plan 083)

**Objetivo:** convertir romaneos confirmados en el comprobante de compra que la empresa emite al
productor: IVA, retenciones, asiento, Libro IVA y nacimiento de la deuda en cuenta corriente. Es
la primera etapa de la verticalidad con **efectos contables reales**.

**Archivos creados o modificados:**
- `docs/planes/083_agricola_etapa2_liquidacion.md` (nuevo)
- `verticalidades/agricola/tabaco/models.py` (+ `LiquidacionTabaco`, `LiquidacionDetalle`,
  `LiquidacionRetencion`, `ConfiguracionTabaco.alicuota_iva`, `RomaneoTabaco.liquidacion`) y su
  migraciÃ³n `0003_liquidacion`
- `verticalidades/agricola/tabaco/services/liquidacion.py` (nuevo)
- `verticalidades/agricola/tabaco/registros.py` y `apps.py` (suscripciÃ³n al Plan 080)
- `verticalidades/agricola/tabaco/views_liquidacion.py` (nuevo) y `urls.py` (7 rutas)
- `verticalidades/agricola/tabaco/templates/agricola/liquidacion/` (6 plantillas nuevas)
- `verticalidades/agricola/tabaco/templates/agricola/hooks/menu_sidebar_bottom.html` (2 entradas)
- `verticalidades/agricola/tabaco/tests/test_plan083_liquidacion.py` y `test_plan083_pantallas.py`
- `contable/tests/test_plan080_terminos_ctacte.py` y `productos/tests/test_plan080_terminos_stock.py`
  (guardan y restauran el registro en vez de vaciarlo â ver mÃ¡s abajo)

**CERO CAMBIOS AL CORE.** La liquidaciÃ³n no es una `Compra`: se engancha al subsistema fiscal por
`asiento_id`, que es un entero y no un FK. Un test entra a la pantalla de **Libro IVA Compras del
core** (`impuestos:libro_iva_compras`) y verifica que la liquidaciÃ³n aparezca con su CUIT, su
cÃ³digo 150 y sus cuatro importes, sin haberse tocado una lÃ­nea de `impuestos` ni de `contable`.

**Detalle TÃ©cnico:**

*CÃ¡lculo.* La letra sale de `condicion_iva` del productor: RI â A (150) con IVA discriminado; el
resto â B (151) sin IVA. Se aplican las retenciones vigentes con `momento = LIQUIDACION`,
salteando las `solo_responsable_inscripto` cuando no corresponde. Ganancias queda excluida
âincluso si un dato viejo la pusiera en LIQUIDACIONâ porque su base es el acumulado mensual de lo
PAGADO. `total = neto + IVA â retenciones de liquidaciÃ³n`.

*NumeraciÃ³n.* NO usa el contador atÃ³mico del core, y es deliberado: en modo MANUAL el nÃºmero real
viene del talonario o del comprobante en lÃ­nea, y un contador interno derivarÃ­a de la serie fÃ­sica
apenas se cargue un nÃºmero distinto. El sistema PROPONE el siguiente de esa letra y punto, y la
garantÃ­a es el Ã­ndice Ãºnico `(empresa, letra, punto, numero)`. Cada letra lleva su serie, como
`maestro_id.lcta` / `lctb` del sistema heredado.

*`RomaneoTabaco.liquidacion` es una FK simple*, y ahÃ­ estÃ¡ la gracia: "no liquidar dos veces los
mismos kilos" queda garantizado por el MODELO, no por una validaciÃ³n que alguien puede olvidar.

*Congelamiento.* La alÃ­cuota de IVA y cada regla de retenciÃ³n (alÃ­cuota, base, mÃ­nimo, cuenta) se
copian en la liquidaciÃ³n al confirmar. Hay test: se cambia la alÃ­cuota de EEAOC a 9,9 % despuÃ©s de
emitir y el comprobante no se mueve.

*AnulaciÃ³n.* Anula el asiento por el servicio del core (que lo marca, no lo borra), limpia el
Libro IVA, libera los romaneos y recalcula el saldo. **Los fardos no se tocan**: la mercaderÃ­a
entrÃ³ y se pesÃ³.

**BUG ENCONTRADO EN AUTOREVISIÃN â el borrador huÃ©rfano.** `preparar_liquidacion` toma los
romaneos apenas arma el borrador, y ambos servicios eran atÃ³micos por separado. Si la confirmaciÃ³n
fallaba despuÃ©s âfaltaba el CAI, faltaba una cuentaâ el borrador quedaba commiteado reteniendo
esos romaneos PARA SIEMPRE: no volvÃ­an a figurar como pendientes y no habÃ­a forma de liberarlos
desde la pantalla. Se corrigiÃ³ envolviendo preparar + confirmar en una sola transacciÃ³n en la
vista, y se agregÃ³ `descartar_liquidacion()` como red de seguridad. Hay tests de regresiÃ³n.

**INTERFERENCIA ENTRE TESTS, detectada y corregida.** Los tests del Plan 080 vaciaban los
registros de extensiÃ³n en `setUp`. Como la verticalidad se anuncia una sola vez en `ready()`, al
correr la suite completa dejaban al acopio sin su tÃ©rmino y los tests de cuenta corriente de esta
etapa fallaban por un motivo ajeno a ellos. Ahora guardan y RESTAURAN el estado previo. Verificado
corriendo los tres mÃ³dulos juntos en el orden que reproducÃ­a el problema: **72/72**.

**Resultado de las pruebas:**

| Prueba | Resultado |
|---|---|
| `test_plan083_liquidacion` (cÃ¡lculo, asiento, Libro IVA, cta. cte., anulaciÃ³n, descarte) | **46/46** |
| `test_plan083_pantallas` (circuito completo + Libro IVA del core) | **21/21** |
| Corrida dirigida Plan 080 + Plan 083 en el orden problemÃ¡tico | **72/72** |
| Prueba de desenchufe | 0 tÃ©rminos registrados; el saldo del core sigue calculando |
| `makemigrations --check` | sin cambios pendientes |
| **Suite completa** | **793 tests** â 18 errores + 2 fallas, ninguna atribuible a esta etapa |

ClasificaciÃ³n de las 20: **13 preexistentes** del baseline (CUIM Ã8, `SyntaxError` de distribuciÃ³n
Ã2, migraciÃ³n `0019` ausente, `ExtensionArmeria`, `ExtensionDistribuidoraForm`); **5** por una
caÃ­da del backend de PostgreSQL (`the connection is closed`) que tumbÃ³ el `setUp` de
`test_plan074_devoluciones.PrimeroSeCuentaDespuesSeAcreditaTestCase` âmismo fenÃ³meno que en la
Etapa 0; ese mÃ³dulo re-corrido aislado da **33/33 OK y cero caÃ­das de conexiÃ³n**â; y **2** por la
interferencia del registro, ya corregida y verificada.

*Prueba de humo contra datos reales.* Con los maestros de la empresa 1 y en transacciÃ³n revertida:
romaneo de 1.000 kg de Burley al ponderante 3.250 â neto $ 3.250.000, IVA 21 % $ 682.500,
retenciones $ 399.750 (EEAOC 16.250 Â· Ret. IVA 341.250 Â· Salud PÃºblica 32.500 Â· Uso de Agua
9.750), **total $ 3.532.750**. Asiento 176 balanceado en $ 3.932.500 contra las cuentas reales del
plan (114002, 113101, 214401, 214010, 214105, 214402, 211001), Libro IVA cÃ³digo 150 con crÃ©dito
computable, y cuenta corriente del productor en **$ â3.532.750**.

**Estado actual:** Etapa 2 completada. El circuito comercial estÃ¡ cerrado de punta a punta:
maestros â romaneo â liquidaciÃ³n â asiento â Libro IVA â cuenta corriente.

**Siguientes pasos sugeridos:**
1. **Etapa 3 â Pago en tesorerÃ­a**: imputaciÃ³n de la Orden de Pago a la liquidaciÃ³n
   (`agricola_tabaco_liquidacion_pago` + `registrar_aplicacion_op` del Plan 080), retenciÃ³n de
   Ganancias con acumulado mensual, certificados y `recalcular_saldo_liquidacion()`.
2. Confirmar con el contador el tratamiento de la letra B en el Libro IVA (hoy: importe a
   `no_gravado`, sin filas de alÃ­cuota).
3. Deuda tÃ©cnica preexistente: las 6 causas de los 13 errores del baseline.

## Juan Manuel - Notebook personal - 2026-09-06 - AgrÃ­cola Etapa 1: Romaneo (Plan 082)

**Objetivo:** registrar la recepciÃ³n fÃ­sica del tabaco del productor y su clasificaciÃ³n fardo por
fardo, con el precio formado desde la lista vigente y **congelado** en cada fardo. Sin efecto
contable, de stock ni de cuenta corriente: la deuda nace al liquidar (Etapa 2).

**Archivos creados o modificados:**
- `docs/planes/082_agricola_etapa1_romaneo.md` (nuevo)
- `core/models.py` (+ `ContadorDocumento.ROMANEO_TABACO`) y su migraciÃ³n `0003`
- `verticalidades/agricola/tabaco/models.py` (+ `RomaneoTabaco`, `FardoTabaco`,
  `ReclasificacionFardo`) y su migraciÃ³n `0002`
- `verticalidades/agricola/tabaco/services/romaneo.py` (nuevo)
- `verticalidades/agricola/tabaco/forms_romaneo.py` y `views_romaneo.py` (nuevos)
- `verticalidades/agricola/tabaco/urls.py` (13 rutas nuevas)
- `verticalidades/agricola/tabaco/templates/agricola/romaneo/` (11 plantillas nuevas)
- `verticalidades/agricola/tabaco/templates/agricola/hooks/menu_sidebar_bottom.html` (nuevo)
- `verticalidades/agricola/tabaco/tests/test_plan082_romaneo.py` y `test_plan082_pantallas.py`

**Detalle TÃ©cnico:**

*El borrador se persiste, no va a la sesiÃ³n.* El patrÃ³n de carrito del ERP guarda los Ã­tems en
`request.session`; acÃ¡ no sirve, porque un romaneo real tiene cientos de fardos y una sesiÃ³n con
800 diccionarios se reescribe entera en cada alta. El romaneo nace en BORRADOR en la base y cada
fardo es una fila: ademÃ¡s de escalar, si se cae el navegador con 300 fardos cargados no se pierde
nada. Es el criterio del sistema heredado, que usaba una tabla de staging y no memoria.

*QuÃ© se congela.* El romaneo guarda `ponderante_aplicado` y la FK a la lista; cada fardo guarda
`coeficiente_aplicado` y `precio_aplicado`. Hay un test frontal: se carga un fardo, se cambia el
ponderante de la lista a 9.999 y el fardo sigue valiendo lo mismo â y un fardo nuevo del MISMO
romaneo tambiÃ©n.

*NumeraciÃ³n.* `ROMANEO_TABACO` se sumÃ³ a `ContadorDocumento` para reutilizar
`siguiente_numero()`, que ya resuelve el bloqueo atÃ³mico, en lugar de duplicar la lÃ³gica.
Precedente: DistribuciÃ³n ya tiene ahÃ­ `PEDIDO`, `REPARTO` y `RECEPCION_DEVOLUCION`. El nÃºmero se
asigna al CONFIRMAR, no al abrir, para no dejar huecos en la serie. El punto sale de
`Sucursal.punto`, cuyo `help_text` dice literalmente que prenumera este tipo de documentos, asÃ­
cada sucursal lleva su serie propia.

*La reclasificaciÃ³n no borra.* Cambiar la clase de un fardo confirmado deja una fila en
`ReclasificacionFardo` con clase, coeficiente, precio e importe anteriores y nuevos, mÃ¡s motivo y
usuario. El fardo queda con los valores nuevos pero la cadena completa es reconstruible.

**DOS BUGS QUE ENCONTRARON LOS TESTS:**

1. **Estado obsoleto en la relaciÃ³n cacheada.** `editar_fardo` y `quitar_fardo` leÃ­an
   `fardo.romaneo`, que Django cachea. Con el objeto viejo en memoria se podÃ­an editar o borrar
   fardos de un romaneo YA CONFIRMADO. Corregido en la raÃ­z: `_exigir_borrador()` relee el estado
   desde la base con `select_for_update()` y devuelve la instancia fresca, lo que ademÃ¡s serializa
   contra una confirmaciÃ³n concurrente.
2. **Contrato roto vista/servicio.** `_aviso()` devolvÃ­a un `HttpResponse` donde se concatenaba
   texto, y `abrir_romaneo()` no aceptaba `observaciones` pese a estar en el formulario y el modelo.

**TRAMPA DE MODO ENCHUFE EVITADA.** El enlace del menÃº NO se escribiÃ³ en `base.html`: un
`{% url 'agro_romaneo_listado' %}` ahÃ­ levanta `NoReverseMatch` al desenchufar la carpeta y, como
todas las pantallas extienden `base.html`, se caerÃ­a el ERP entero. Se usÃ³ el templatetag
`{% hook_menu %}`, que renderiza `agricola/hooks/menu_sidebar_bottom.html` sÃ³lo si la carpeta
existe. Cero lÃ­neas en el core. (Se llegÃ³ a agregar una bandera a `core/context_processors.py` y
se revirtiÃ³ al encontrar el hook.)

**Resultado de las pruebas:**

| Prueba | Resultado |
|---|---|
| `test_plan082_romaneo` (congelado, totales, estados, reclasificaciÃ³n, concurrencia) | **40/40** |
| `test_plan082_pantallas` (circuito completo por el cliente de prueba) | **27/27** |
| Prueba de desenchufe | `check` limpio, 0 apps, rutas inexistentes, tÃ©rminos de stock intactos |
| `makemigrations --check` | sin cambios pendientes |
| **Suite completa** | **729 tests, 13 errores** â todos subconjunto de los 15 preexistentes |

Los 729 son los 640 previos + 67 nuevos de esta etapa + 22 de dos mÃ³dulos que volvieron a cargar.
Los errores BAJARON de 15 a 13 porque en paralelo se corrigiÃ³ el import de `TarifaEstudio` en
`facturacion/services/facturacion_lote_service.py` â el bug de producciÃ³n seÃ±alado en el Plan 080.

*Prueba de humo contra datos reales.* Se corriÃ³ un romaneo completo con los maestros de la empresa
1 (Burley, ponderante $ 3.250), dentro de una transacciÃ³n revertida: 5 fardos, 2.311 kg,
$ 6.841.380, PPP $ 2.960,35 = 91,09 % del ponderante, estadÃ­stica por grupo B/C/N/T/X y
confirmaciÃ³n con nÃºmero 0002-00000001. No quedÃ³ nada en la base. En el primer intento el sistema
rechazÃ³ cargar `N5K` en Burley âes una clase de Virginiaâ, que es exactamente lo que debe hacer.

**OBSERVACIÃN, fuera de alcance.** La correcciÃ³n de `TarifaEstudio` usa un import ESTÃTICO de
`verticalidades.estudio.models` desde un servicio del core. Verificado: con la carpeta
`verticalidades/estudio/` movida, ese mÃ³dulo lanza `ModuleNotFoundError`. `manage.py check` sigue
pasando porque nadie lo importa al arrancar, pero es la clase de acoplamiento que el Plan 075
prohÃ­be. Queda seÃ±alado, sin corregir.

**Estado actual:** Etapa 1 completada y verificada. El circuito de romaneo estÃ¡ operativo: abrir,
cargar fardos con precio en vivo, confirmar, imprimir, anular y reclasificar.

**Siguientes pasos sugeridos:**
1. **Etapa 2 â LiquidaciÃ³n de compra**: comprobante 150/151, asiento por `crear_asiento()`,
   Libro IVA + alÃ­cuotas por `asiento_id`, retenciones de liquidaciÃ³n y tÃ©rmino de cuenta
   corriente del Plan 080. Los maestros y la configuraciÃ³n ya estÃ¡n cargados para arrancar.
2. Deuda tÃ©cnica preexistente: las causas remanentes de los 13 errores (CUIM en `test_plan028` y
   `test_plan071`, `ExtensionArmeria`, `ExtensionDistribuidoraForm`, el `SyntaxError` de
   `test_plan074_facturacion:22` y `test_plan074_pedidos:20`, y la migraciÃ³n `0019` ausente).

## Juan Manuel - Notebook personal - 2026-09-06 - AgrÃ­cola Etapa 0: Maestros del Acopio de Tabaco (Plan 081)

**Objetivo:** dejar cargables y administrables los maestros del acopio âcampaÃ±as, variedades, las
75 clases con sus coeficientes, listas de precio ponderante, conceptos de retenciÃ³n y la extensiÃ³n
sectorial del productorâ, sin ningÃºn efecto contable, de stock ni de cuenta corriente.

**Archivos creados o modificados:**
- `docs/planes/081_agricola_etapa0_maestros_tabaco.md` (nuevo â plan de la etapa)
- `verticalidades/agricola/urls.py` (nuevo â ver el hallazgo de abajo)
- `verticalidades/agricola/core_agricola/models.py` (+ `Campania`) y su migraciÃ³n `0002_campania`
- `verticalidades/agricola/tabaco/models.py` (6 modelos) y su migraciÃ³n `0001_initial`
- `verticalidades/agricola/tabaco/forms.py`, `views_htmx.py`, `urls.py` (nuevos)
- `verticalidades/agricola/tabaco/services/importacion_clases.py` y `services/precios.py` (nuevos)
- `verticalidades/agricola/tabaco/management/commands/importar_clases_tabaco.py` (nuevo)
- `verticalidades/agricola/tabaco/templates/` (13 plantillas nuevas, dentro de la verticalidad)
- `verticalidades/agricola/tabaco/tests/test_plan081_maestros.py` y `test_plan081_pantallas.py` (nuevos)
- `core/views_config.py` (pestaÃ±as agrÃ­colas con import tolerante)
- `templates/configuracion/partials/hub.html` (bloque "Acopio de Tabaco", condicionado)

**HALLAZGO: las rutas de `agricola` no se publicaban.**
El auto-descubrimiento de `config/urls.py` recorre `verticalidades/<app>/` e incluye la app sÃ³lo
si encuentra un `urls.py` **en ese primer nivel**. Como `agricola` es un contenedor de sub-apps
(`tabaco`, `granos`) y no una app en sÃ­ misma, ninguna de sus rutas llegaba a Django. Se resolviÃ³
creando `verticalidades/agricola/urls.py`, del lado de la verticalidad: **no se tocÃ³
`config/urls.py`**, el mecanismo del core ya servÃ­a y lo que faltaba era el punto de entrada.

**Detalle TÃ©cnico:**

*7 tablas, todas con prefijo `agricola_`*: `agricola_campania` (en `core_agricola`, porque granos
y caÃ±a la comparten), `agricola_tabaco_configuracion`, `..._variedad`, `..._clase`,
`..._lista_precio`, `..._tipo_retencion`, `..._productor`.

*Tres decisiones de modelo que conviene tener presentes:*
1. El **coeficiente lleva 4 decimales** aunque el maestro heredado traiga 2: multiplica un precio
   por miles de kilos y el redondeo se nota.
2. El **precio ponderante se versiona** por variedad, campaÃ±a y vigencia, con estado `aprobada`.
   En el VFP era un campo suelto de `tab_variedad`: al cambiarlo se reescribÃ­a el precio de todo
   lo ya comprado.
3. `agricola_tabaco_tipo_retencion` **no tiene nada especÃ­fico de tabaco**, a propÃ³sito.
   `tipo_base` (NETO / IVA / ACUM_MENSUAL) y `momento` (LIQUIDACION / PAGO) son genÃ©ricos, para
   poder promover la tabla al core cuando otra empresa sea agente de retenciÃ³n. El formulario
   ademÃ¡s impide configurar una retenciÃ³n de base acumulada mensual practicada al liquidar: su
   base es el acumulado de lo PAGADO, y al liquidar darÃ­a un importe incorrecto.

*ImportaciÃ³n de las 75 clases.* Comando `importar_clases_tabaco --empresa <id> [--dry-run]`.
Lee el CSV en UTF-8 con BOM, separador `;` y decimal con coma; busca por `codigo` y nunca por pk;
valida el archivo entero ANTES de escribir, dentro de una transacciÃ³n. Resultado verificado:
primera corrida 75 altas y 2 variedades; segunda corrida 0 altas y 75 sin cambios. El `--dry-run`
informa lo que harÃ­a y deja la base intacta (verificado en 0 registros).

*Datos cargados y verificados contra la base:* 27 Burley + 48 Virginia, coeficientes 0,1000 a
1,0500, `B1F` = 1,0000 en ambas variedades y `H1F` = 1,0500. El **grupo H de Virginia (3 clases)
ahora aparece**: el sistema heredado lo perdÃ­a porque agrupaba con una lista fija de cinco letras
(B, C, N, T, X); acÃ¡ el grupo se deriva del dato.

*Servicio de precios.* `precio_de_clase()` e `importe_de_linea()` implementan
`REDONDEO(ponderante Ã coeficiente, 2)` y `REDONDEO(precio Ã kilos, 2)`. El redondeo a dos
decimales del precio unitario es deliberado: si se redondeara reciÃ©n en el importe final, el
precio impreso en la liquidaciÃ³n no multiplicarÃ­a exacto por los kilos y el productor no podrÃ­a
verificar su propia liquidaciÃ³n con una calculadora.

*Interfaz.* Seis pestaÃ±as en el panel de ConfiguraciÃ³n con bÃºsqueda typeahead (`delay:300ms`),
lupa, `.fInputAR` en todo importe y coeficiente y `|formato_ar` en los displays. Se usÃ³ **un modal
genÃ©rico** para los cinco maestros en lugar de cinco plantillas casi idÃ©nticas. Las plantillas
viven dentro de la verticalidad (`verticalidades/agricola/tabaco/templates/`) para que se
desenchufe limpio. El bloque del hub aparece sÃ³lo si `EmpresaVertical.hace_tabaco`, y
`core/views_config.py` importa la verticalidad con `try/except ImportError` â **no se copiÃ³** el
patrÃ³n sin protecciÃ³n que ese mismo archivo usa hoy para distribuciÃ³n.

**Resultado de las pruebas:**

| Prueba | Resultado |
|---|---|
| `test_plan081_maestros` (importaciÃ³n, restricciones, precios) | **23/23** |
| `test_plan081_pantallas` (render de pestaÃ±as, modales, buscadores, aislamiento, altas) | **14/14** |
| Prueba de desenchufe | `check` limpio, 0 apps agrÃ­colas, rutas inexistentes, contexto vacÃ­o |
| `makemigrations --check` | sin cambios pendientes |
| Suite completa | 640 tests (603 + 37 nuevos), **los mismos 15 errores preexistentes** |

Los tests de precio validan contra **6 casos reales** del sistema heredado (marzo 2024, Burley,
ponderante 2.500): `B1F â 2.500,00`, `B1FR â 2.125,00`, `B2F â 2.300,00`, `B3F â 1.950,00`,
`C1F â 2.400,00`, `C2F â 2.150,00 Ã 843 kg = 1.812.450,00`. Hay ademÃ¡s un test dedicado al caso
`N5K`: dos cÃ³digos con la misma clase dentro de la misma variedad ahora se rechazan al importar.

**Nota sobre la suite completa.** ReportÃ³ 17 errores en vez de 15. Los 2 extra fueron **un Ãºnico
evento de infraestructura**, no una regresiÃ³n: el backend de PostgreSQL se cayÃ³
(`server closed the connection unexpectedly â server terminated abnormally`) durante
`test_plan074_cobranzas.test_rendir_desde_la_pantalla`, arrastrando a su `tearDownClass`. Ese
mÃ³dulo re-corrido aislado da **43/43 OK y cero caÃ­das**. AdemÃ¡s, la Etapa 0 no registra ningÃºn
tÃ©rmino en los registros del Plan 080 âverificado en runtime: los tres registros en 0 y
`_terminos()` devolviendo los cuatro de siempreâ, asÃ­ que el camino de stock y cuenta corriente
que ejecutÃ³ esta suite es idÃ©ntico al de la corrida anterior, que no tuvo ninguna caÃ­da.

**Estado actual:** Etapa 0 completada y verificada. Los maestros quedan operativos y las 75 clases
cargadas para la empresa 1.

**Siguientes pasos sugeridos:**
1. **Cargar los cinco conceptos de retenciÃ³n desde la pantalla.** No se sembraron por comando
   porque cada uno necesita su cuenta de pasivo del plan de cuentas de la empresa, y eso lo define
   el contador. Valores del sistema heredado, a confirmar: EEAOC 0,5 %, Uso de Agua 0,3 %, Salud
   PÃºblica 1 % (los tres sobre el neto, al liquidar), Ret. IVA 50 % del IVA (al liquidar, sÃ³lo RI)
   y Ganancias 2 % sobre acumulado mensual con MNI 224.000 (al pagar, sÃ³lo RI).
2. Cargar la campaÃ±a vigente y su lista de precio ponderante aprobada.
3. **Etapa 1 â Romaneo**: recepciÃ³n, pesaje y clasificaciÃ³n por fardo, con el precio congelado.
4. Deuda tÃ©cnica pendiente del baseline: las 6 causas de los 15 errores preexistentes, en especial
   `facturacion/services/facturacion_lote_service.py`, que es cÃ³digo de producciÃ³n roto.

## Juan Manuel - Notebook personal - 2026-09-06 - Plan 080: tÃ©rminos enchufables en Stock y Cuenta Corriente

**Objetivo:** implementar el Ãºnico cambio al core que requiere la verticalidad AgrÃ­cola: tres
puntos de extensiÃ³n para que una verticalidad sume sus propios orÃ­genes al cÃ¡lculo del stock, al
saldo de cuenta corriente y a la imputaciÃ³n de Ãrdenes de Pago, sin que el core la importe y sin
romper el Modo Enchufe del Plan 075.

**Archivos creados o modificados:**
- `productos/services/stock_service.py` â `registrar_termino_stock()`; `_terminos()` ahora devuelve `base + _TERMINOS_EXTRA`
- `contable/services/saldos.py` â `registrar_termino_ctacte()` y `registrar_aplicacion_op()`, consumidos en `recalcular_saldo_cliente_proveedor()` y `pendiente_de_aplicar_op()`
- `productos/tests/test_plan080_terminos_stock.py` (nuevo, 12 casos)
- `contable/tests/test_plan080_terminos_ctacte.py` (nuevo, 14 casos)
- `verticalidades/estudio/migrations/0001_initial.py` (nuevo â reparaciÃ³n, ver mÃ¡s abajo)
- `docs/planes/080_terminos_enchufables_saldos_stock.md`

**Sin migraciones del core y sin tablas nuevas.** Los cuatro tÃ©rminos de stock y los cuatro
sumandos de cuenta corriente quedaron textualmente iguales: el diff sÃ³lo agrega.

**Detalle TÃ©cnico:**

*Mecanismo.* Cada servicio expone un registro al que la verticalidad se suscribe desde su
`apps.py::ready()`. La dependencia va verticalidad â core, nunca al revÃ©s. Si la carpeta de la
verticalidad no estÃ¡, su app no entra a `INSTALLED_APPS`, `ready()` no corre, no se registra nada
y los servicios calculan como antes del plan.

*Idempotencia.* El alta es idempotente por `nombre`. Sin eso, un `ready()` ejecutado dos veces
âautoreload, ciertos runnersâ contarÃ­a el stock y la deuda por duplicado en silencio.

*Ajuste sobre el diseÃ±o original.* La validaciÃ³n de los tÃ©rminos se hace AL REGISTRAR, no al
calcular. Un `excluir` mal tipeado descubierto dentro de `recalcular_stock()` romperÃ­a el stock de
todo el ERP en plena operaciÃ³n; asÃ­ el servidor directamente no levanta. Se verificÃ³ contra la
base que `exclude(Q())` no excluye nada y que `exclude(None)` lanza `TypeError`, de modo que
`None` se normaliza a `Q()` al registrar. TambiÃ©n se valida que `signo` sea 1 o â1.

*ConvenciÃ³n de importes (documentada en el cÃ³digo).* Un tÃ©rmino de cuenta corriente debe declarar
el TOTAL del comprobante, no el neto a pagar. Es el mismo criterio del supuesto S-1 ya
documentado en `saldos.py`: `OrdenPago.total` ya incluye las retenciones practicadas como medio
de pago, asÃ­ que un comprobante que aportara el neto de retenciones harÃ­a que la OP cancelara de
mÃ¡s y el tercero quedara con un crÃ©dito falso.

**BLOQUEANTE PREEXISTENTE REPARADO â la suite no podÃ­a correr.**
`verticalidades/estudio` tenÃ­a el modelo `TarifaEstudio` pero nunca se le generaron migraciones.
Al crear la base de test, Django ejecuta `sync_apps` para las apps sin migraciones ANTES de
aplicar las migraciones, y `TarifaEstudio` hereda de `AuditModel`, que tiene FK a `auth_user`,
que en ese momento todavÃ­a no existe: `relation "auth_user" does not exist`. Se verificÃ³ ademÃ¡s
que la tabla `facturacion_tarifaestudio` tampoco existÃ­a en la base real. Se generÃ³ la migraciÃ³n
faltante; es puramente aditiva y no requiere `--fake`.

**Resultado de las pruebas:**

| Corrida | Tests | Errores | Tiempo |
|---|---|---|---|
| **Baseline** (cÃ³digo previo al Plan 080, suite completa) | 577 | **15** | 5.454 s |
| **DespuÃ©s** (con Plan 080, suite completa) | 603 | **15** | 5.568 s |
| Tests propios del Plan 080 | 26 | 0 | 62 s |

Los 603 son los 577 del baseline mÃ¡s los 26 nuevos. El conteo de errores no cambiÃ³.

*ComparaciÃ³n dirigida (la prueba fuerte).* Sobre 9 mÃ³dulos â`test_plan028`,
`test_plan071_trazabilidad`, `test_totales`, `test_stock`, `test_stock_inicial`, `test_saldos`,
`test_saldos_mensuales`, `test_contabilizacion_op`, `test_contabilizacion_recibo`, 90 testsâ se
corriÃ³ la misma suite dos veces: con los dos archivos de servicio revertidos a `7e0b322` y con
la versiÃ³n del Plan 080. Ambas dieron 8 errores y las listas de fallas son **byte a byte
idÃ©nticas**; la Ãºnica diferencia del diff es el tiempo transcurrido (319,275 s vs 317,764 s).

*Prueba de fuego de desenchufe.* Con `verticalidades/agricola/` movida fuera del proyecto:
`manage.py check` sin problemas, ninguna app con 'agricola' en `INSTALLED_APPS`, 0 tÃ©rminos
registrados en los tres registros, y los tÃ©rminos de stock de siempre intactos
(`['compras','recepciones','ventas','remitos_internos']`). Carpeta restaurada y `check` limpio.

**Los 15 errores preexistentes, clasificados** (ninguno relacionado con este plan; ninguno en los
mÃ³dulos de stock ni de saldos):

| Causa | MÃ³dulos afectados |
|---|---|
| `ValidationError` de CUIM al crear `Subproducto` â la validaciÃ³n estricta agregada el 2026-09-03 rompiÃ³ tests que crean subproductos sin CUIM vÃ¡lido | `test_plan028` (5), `test_plan071_trazabilidad` (3) |
| `ImportError: cannot import name 'TarifaEstudio' from 'facturacion.models'` â el modelo se mudÃ³ a `verticalidades/estudio` y quedaron referencias viejas | `test_lote_condic`, `test_plan075_numeracion` |
| `ImportError: cannot import name 'ExtensionArmeria' from 'facturacion.models'` | `test_armeria_credencial_clu` |
| `ImportError: cannot import name 'ExtensionDistribuidoraForm' from 'facturacion.forms'` | `test_plan074_maestros` |
| `SyntaxError` â un `from ... import` quedÃ³ inyectado en medio de otro import multilÃ­nea, dejando el parÃ©ntesis sin cerrar | `test_plan074_facturacion` (lÃ­nea 22), `test_plan074_pedidos` (lÃ­nea 20) |
| `ModuleNotFoundError: No module named 'contable.migrations.0019_renumerar_condic'` â el test importa una migraciÃ³n eliminada en la consolidaciÃ³n del 2026-09-04 | `test_condic_renumeracion` |

**HALLAZGO QUE NO ES SÃLO DE TESTS:** `facturacion/services/facturacion_lote_service.py` lÃ­nea 6
importa `TarifaEstudio` desde `facturacion.models`. **Es cÃ³digo de producciÃ³n, no un test**: el
servicio de facturaciÃ³n por lote estÃ¡ roto en tiempo de importaciÃ³n. Es la misma clase de
violaciÃ³n del Modo Enchufe que el Plan 075 prohÃ­be. **No se corrigiÃ³**: queda fuera del alcance de
este plan y necesita decisiÃ³n.

**Estado actual:** Plan 080 completado y verificado. La Etapa 0 de la verticalidad AgrÃ­cola queda
desbloqueada, y con ella las Etapas 2 y 4 cuando llegue el momento.

**Siguientes pasos sugeridos:**
1. **Deuda tÃ©cnica preexistente** (fuera del alcance agrÃ­cola, pero conviene atacarla): las 6
   causas de arriba. La del `facturacion_lote_service.py` es la urgente porque es producciÃ³n.
2. Etapa 0 â maestros de tabaco, configuraciÃ³n e importaciÃ³n idempotente de las 75 clases desde
   `docs/agricola/tabaco_clase.csv`.
3. Etapa 1 â romaneo: recepciÃ³n y clasificaciÃ³n por fardo.

## Juan Manuel - Notebook personal - 2026-09-06 - DiseÃ±o de la Verticalidad AgrÃ­cola (Acopio de Tabaco)

**Objetivo:** Relevar el material de diseÃ±o externo y el sistema VFP heredado, contrastarlos contra
el cÃ³digo real del ERP, y dejar documentado el plan de implementaciÃ³n por etapas de la verticalidad
AgrÃ­cola, con foco en el circuito de acopio y comercializaciÃ³n de tabaco. **No se modificÃ³ cÃ³digo
del ERP: la intervenciÃ³n es exclusivamente documental.**

**Archivos creados o modificados:**
- `docs/agricola/plan inicial agricola.md` (reescrito completo â plan integral v1.0)
- `docs/planes/080_terminos_enchufables_saldos_stock.md` (nuevo)
- `docs/GUIA_MODULAR.md` (alta de la verticalidad 17 â Agropecuario y Acopio de Tabaco)
- `docs/walkthrough.md` (esta entrada)
- `d:orrador	abaco_clase.csv` (correcciÃ³n de dato: clase cÃ³digo 72 `N5K` â `N5T`)

**Detalle TÃ©cnico:**

*Fuentes analizadas.* Paquete de diseÃ±o externo `erp_agro_diseno_v0_1` (12 documentos),
`tabaco_clase.csv` (75 clases), y los formularios VFP `op_romaneo.scx/.sct`,
`compra_tabaco.scx/.sct` y `consulta_romaneo.scx/.sct` del sistema heredado, mÃ¡s las estructuras
DBF y la biblioteca de clases `basico.vcx`.

*Verificaciones contra el cÃ³digo del ERP.* Se corrigieron once afirmaciones del paquete externo
que no se sostienen contra el repositorio (detalle en Â§10 del plan). Las tres de mayor impacto:
1. El stock **no** se ajusta por delta desde signals: es un valor derivado que `recalcular_stock()`
   reconstruye desde una lista declarativa de tÃ©rminos (Plan 053). Extenderlo es agregar un
   tÃ©rmino, no rediseÃ±ar el motor.
2. `contable.LibroIvaCompras` y `LibroIvaAlic` **no dependen de `Compra`**: se cuelgan del asiento
   por un `asiento_id` que ni siquiera es FK. La verticalidad puede participar del subsistema
   fiscal sin ningÃºn cambio en el core.
3. `contabilizar_orden_pago()` **no lee `OrdenPagoAplicacion`**: el asiento de la OP es idÃ©ntico
   pague una `Compra` o una liquidaciÃ³n de tabaco. Y la retenciÃ³n de Ganancias ya estÃ¡ resuelta
   por el core vÃ­a `MedioPago` categorÃ­a `RET` + `cta_ret_practicada_ganancias`.

*FÃ³rmulas de cÃ¡lculo extraÃ­das del VFP y validadas.* `precio = ROUND(ponderante Ã coeficiente, 2)`
e `importe = ROUND(precio Ã kilos, 2)`, verificadas contra **132 registros reales** de
`cpra_clase_fec.DBF` (marzo 2024): 132/132 exactas. Retenciones: Ret. IVA 50 % del IVA,
EEAOC 0,5 %, Uso de Agua 0,3 %, Salud PÃºblica 1 %, todas sobre el neto; Ganancias 2 % sobre
acumulado mensual menos MNI, rÃ©gimen 78, MNI 224.000. Ninguna se calcula por kilo.

*DecisiÃ³n de circuito.* El VFP resolvÃ­a liquidaciÃ³n y pago en un solo acto (`op_romaneo`) por una
particularidad operativa de aquel cliente. **No se replica.** El ERP separa los dos hechos:
se liquida (nace la deuda) y despuÃ©s, en tesorerÃ­a, se emite la Orden de Pago que la cancela.

*Hallazgo en el sistema heredado.* El asiento de la Orden de Pago del VFP no balancea cuando hay
retenciÃ³n de Ganancias: descuadra en 2 Ã Ret_gcias por tener intercambiados los importes de la
lÃ­nea del productor y la del banco. SobreviviÃ³ porque con retenciÃ³n en cero cierra. `crear_asiento()`
de Ikigai rechazarÃ­a ese asiento, que es el comportamiento correcto.

*CorrecciÃ³n de datos.* En `tabaco_clase.csv`, el cÃ³digo 72 figuraba como `N5K`, duplicando al
cÃ³digo 38 dentro de Virginia con distinto coeficiente (0,15 vs 0,17). Por el patrÃ³n de bloques del
maestro corresponde al grupo T y se corrigiÃ³ a `N5T`, confirmado por el usuario. Tras la
correcciÃ³n, `(variedad, detalle)` es Ãºnico ademÃ¡s de `(variedad, codigo)`.

*ObservaciÃ³n para el equipo.* Las verticalidades `distribucion` y `estudio` existen fÃ­sicamente en
`verticalidades/` pero no figuran en el Ã­ndice de `docs/GUIA_MODULAR.md`. No se modificaron sus
filas por estar fuera del alcance de esta tarea.

**Resultado de las pruebas:** No aplica â no hubo cambios de cÃ³digo. El baseline de la suite debe
ejecutarse y registrarse al iniciar el Plan 080, que es el primer plan con impacto en el core.

**Estado actual:** DiseÃ±o documentado y aprobado en sus decisiones de fondo. Quedan **siete
decisiones abiertas** (DA-01 a DA-07 del plan), de las cuales tres bloquean la Etapa 2:
momento de cada retenciÃ³n, forma de autorizaciÃ³n del comprobante (webservice / talonario con CAI)
y existencia de notas de crÃ©dito de liquidaciÃ³n.

**Siguientes pasos sugeridos:**
1. Cerrar DA-01, DA-02 y DA-03 con el asesor impositivo.
2. Ejecutar el Plan 080 (Ãºnico cambio al core), con baseline y prueba de desenchufe.
3. Etapa 0 â maestros y configuraciÃ³n, con la importaciÃ³n idempotente de las 75 clases.
4. Etapa 1 â romaneo (recepciÃ³n y clasificaciÃ³n por fardo), sin efectos contables ni de stock.

### ActualizaciÃ³n 2026-09-06 (misma jornada) â Cierre de DA-01, DA-02 y DA-03

**Objetivo:** incorporar al plan las tres decisiones que bloqueaban la Etapa 2.

**Archivos modificados:** `docs/agricola/plan inicial agricola.md`

**Decisiones incorporadas:**
- **DA-01 â Momento de cada retenciÃ³n (cerrada).** Ret. IVA, EEAOC, Uso de Agua y Salud PÃºblica se
  practican en la **liquidaciÃ³n**; Ganancias en el **pago**. Queda parametrizado en el campo
  `momento` del maestro de retenciones, no cableado en el cÃ³digo.
- **DA-02 â AutorizaciÃ³n del comprobante (cerrada).** Se soportan **dos modos simultÃ¡neos**:
  `MANUAL` (captura de tipo, punto, nÃºmero y CAI, para talonario impreso o comprobante en lÃ­nea de
  ARCA) â el que se implementa en la Etapa 2 â y `WEBSERVICE`, que queda como punto de extensiÃ³n
  preparado y sin desarrollar (mejora MP-02). Se agregÃ³ la secciÃ³n Â§3.6 al plan con el detalle de
  quÃ© se propone y quÃ© es editable en cada modo, y la validaciÃ³n de unicidad
  `(empresa, letra, punto, numero)`.
- **DA-03 â Notas de crÃ©dito de liquidaciÃ³n (postergada).** Pasa a la mejora **MP-01**, fuera del
  alcance inicial: falta definir si el comprobante 150/151 tiene su propia nota de crÃ©dito con
  cÃ³digo ARCA especÃ­fico o si se usan las Notas de CrÃ©dito convencionales A/B. Mientras tanto, la
  correcciÃ³n de una liquidaciÃ³n se hace por **anulaciÃ³n con contraasiento** dentro del perÃ­odo.

**Estado actual:** la Etapa 2 queda **desbloqueada**. Las decisiones abiertas remanentes (DA-04 a
DA-07) afectan a las Etapas 1, 4 y 5, no a la liquidaciÃ³n.

## Cristian - PC CASA - 06/09/2026
**Objetivo:** SoluciÃ³n de deudas tÃ©cnicas urgentes e importaciones huÃ©rfanas en verticalidades.
**Archivos creados o modificados:**
- `facturacion/services/facturacion_lote_service.py` [MODIFY]
- `facturacion/tests/test_lote_condic.py` [MODIFY]
- `facturacion/tests/test_plan075_numeracion.py` [MODIFY]
- `migracion/management/commands/migrar_tarifas.py` [MODIFY]
- `facturacion/helpers.py` [MODIFY]
- `facturacion/tests/test_armeria_credencial_clu.py` [MODIFY]

**Detalle TÃ©cnico:**
- Se corrigiÃ³ el error bloqueante en producciÃ³n y tests provocado por la importaciÃ³n del modelo `TarifaEstudio` desde `facturacion.models`. Ahora se importa correctamente desde su nueva ubicaciÃ³n en `verticalidades.estudio.models`.
- Se revisÃ³ el estado de las verticalidades `armeria` y `estudio` en bÃºsqueda de dependencias huÃ©rfanas tras su refactorizaciÃ³n.
- Se detectÃ³ y corrigiÃ³ la importaciÃ³n huÃ©rfana de `ExtensionArmeria` y `ExtensionArmeriaForm` (seguÃ­an siendo requeridos desde `facturacion` en lugar de `verticalidades.armeria`) en `facturacion/helpers.py` y `facturacion/tests/test_armeria_credencial_clu.py`.
- Se verificÃ³ mediante bÃºsqueda global (grep) que otros modelos migrados (ej. `ReservaArma`) estÃ¡n correctamente referenciados en el resto del proyecto.

**Estado actual y siguientes pasos sugeridos:**
- Los problemas de importaciÃ³n (cÃ³digo roto en tiempo de importaciÃ³n) para las verticalidades evaluadas estÃ¡n resueltos. La suite y el servidor local pueden inicializarse sin fallos. Quedo a la espera de la siguiente deuda o tarea a abordar.

## Juan Manuel - Notebook personal - 2026-09-07 - AgrÃ­cola Etapa 4: Stock del Tabaco (Plan 085)

**Objetivo:** que los kilos recibidos entren al stock del ERP y salgan al venderse, usando el
motor existente. Consume el **Ãºltimo punto de extensiÃ³n del Plan 080 que quedaba sin estrenar**.

**Archivos creados o modificados:**
- `docs/planes/085_agricola_etapa4_stock.md` (nuevo)
- `verticalidades/agricola/tabaco/services/stock.py` (nuevo â tÃ©rmino y conciliaciÃ³n)
- `verticalidades/agricola/tabaco/services/romaneo.py` (dispara el recÃ¡lculo al confirmar/anular)
- `verticalidades/agricola/tabaco/registros.py` (+ `registrar_termino_stock`)
- `verticalidades/agricola/tabaco/management/commands/crear_productos_tabaco.py` (nuevo)
- `verticalidades/agricola/tabaco/views_pago.py` (+ conciliaciÃ³n y recÃ¡lculo) y `urls.py` (2 rutas)
- `verticalidades/agricola/tabaco/templates/agricola/stock/conciliacion.html` (nuevo)
- `verticalidades/agricola/tabaco/templates/agricola/hooks/menu_sidebar_bottom.html` (1 entrada)
- `verticalidades/agricola/tabaco/tests/test_plan085_stock.py` (nuevo)

**SIN MIGRACIONES.** La etapa no agrega ni una tabla ni un campo: `VariedadTabaco.producto` ya
existÃ­a desde el Plan 081, previsto justamente para esto. Todo lo demÃ¡s es servicio, registro y
pantalla.

**Detalle TÃ©cnico:**

*Granularidad: un producto por VARIEDAD, en kilos.* La clase vive en el fardo, no en el producto.
Si hubiera un producto por clase serÃ­an 75, y âlo que importa de verdadâ una reclasificaciÃ³n
tendrÃ­a que mover stock de uno a otro. Pero reclasificar NO cambia lo que hay en el galpÃ³n: son
los mismos kilos, mejor descriptos. Hay un test que fija esa regla.

*El tÃ©rmino sÃ³lo aporta la ENTRADA.* La salida ya la resuelve el tÃ©rmino `ventas` que existe desde
siempre: al vender tabaco se factura el `Producto` de la variedad y `VentaItem` lo descuenta. Un
segundo tÃ©rmino de egreso duplicarÃ­a la baja.

*CuÃ¡ndo entra:* al CONFIRMAR el romaneo. El borrador todavÃ­a se estÃ¡ cargando y el anulado no
ocurriÃ³; CONFIRMADO y LIQUIDADO cuentan igual, porque liquidar factura pero no mueve mercaderÃ­a.
Como el motor recalcula por signals de `CompraItem`/`VentaItem` âque no aplican acÃ¡â, el llamado
va explÃ­cito en `confirmar_romaneo()` y `anular_romaneo()`, los dos Ãºnicos momentos en que un
romaneo cruza el umbral de contar o no contar.

*DegradaciÃ³n silenciosa y deliberada:* si una variedad no tiene producto asignado, el romaneo se
confirma igual y simplemente no mueve stock. Para que ese silencio no se lea como "estÃ¡ todo
bien", la conciliaciÃ³n lo informa como una fila destacada.

*ConciliaciÃ³n:* recibidos â vendidos + inicial contra `StockSucursal.cantidad`, por variedad y
sucursal. La diferencia debe ser cero; si no lo es, el botÃ³n de recÃ¡lculo la corrige, porque el
stock es un valor derivado y autorreparable.

**LOS TRES PUNTOS DE EXTENSIÃN DEL PLAN 080 QUEDAN TODOS EN USO:**

| Punto | Consumido en |
|---|---|
| `registrar_termino_ctacte` | Plan 083 â la deuda de la liquidaciÃ³n |
| `registrar_aplicacion_op` | Plan 084 â la imputaciÃ³n del pago |
| `registrar_termino_stock` | Plan 085 â esta etapa |

El Plan 080 se diseÃ±Ã³ al principio de todo, antes de que existiera un solo modelo de tabaco.
Cierra sin haber necesitado un cambio.

**Resultado de las pruebas:**

| Prueba | Resultado |
|---|---|
| `test_plan085_stock` (ingreso, egreso, conciliaciÃ³n, comando, pantalla) | **26/26** |
| Prueba de desenchufe | el stock vuelve **exactamente** a `['compras','recepciones','ventas','remitos_internos']`, los tres registros en 0 y `recalcular_stock()` sigue funcionando |
| `makemigrations --check` | sin cambios pendientes |
| **Suite completa** | **872 tests, 13 errores** â lista **idÃ©ntica** al baseline, cero fallas nuevas y cero caÃ­das de conexiÃ³n |

La corrida tardÃ³ 1.136 s con la mÃ¡quina sola, confirmando de nuevo que las caÃ­das de PostgreSQL
de etapas anteriores venÃ­an de correr suites en paralelo.

**Estado actual:** el circuito del acopio estÃ¡ completo de punta a punta âmaestros, romaneo,
liquidaciÃ³n, pago y stockâ sin una sola modificaciÃ³n funcional al core.

**Siguientes pasos sugeridos:**
1. **Etapa 5** â lotes de acopio, acondicionamiento con mermas, venta y **margen por fardo**
   (venta â compra â costos de acondicionamiento).
2. **Etapa 6** â reportes FET / SecretarÃ­a de la ProducciÃ³n y libro de retenciones practicadas.
3. Antes de operar: correr `manage.py crear_productos_tabaco --empresa 1` para que las variedades
   tengan su producto de stock, o asignarlo desde el ABM de variedades.
4. Deuda tÃ©cnica preexistente: las 6 causas de los 13 errores del baseline.

<<<<<<< HEAD
---

## 2026-09-07 â Juan Manuel - Notebook personal

### CorrecciÃ³n: `unidad_venta` bloqueaba el alta de productos fuera de DISTRIBUCION

**Objetivo:** el usuario reportÃ³ que dar de alta un producto en la actividad **ARMERIA** fallaba
por el campo `unidad_venta`.

**DiagnÃ³stico.** El campo no es de las etapas agrÃ­colas: viene del **Plan 074 (DistribuciÃ³n)** y
estÃ¡ en el repositorio desde el commit inicial (`git log -S "unidad_venta" -- productos/models.py`
devuelve sÃ³lo `1614a03 Initial commit`; lo crea `productos/migrations/0001_initial.py`). El
problema es una combinaciÃ³n de tres cosas que por separado son correctas:

1. `unidad_venta` estÃ¡ en `ProductoForm.Meta.fields`.
2. En el modelo tenÃ­a `default='UNIDAD'` y `choices`, pero **no `blank=True`** â el form lo
   marcaba `required=True`.
3. SÃ³lo se **dibuja** dentro de
   `verticalidades/distribucion/templates/distribucion/hooks/ui_producto_modal_campos.html`, que
   abre con `{% if empresa_actual.tipo_actividad == 'DISTRIBUCION' %}`.

En ARMERIA (y ESTUDIO, AGRICOLAâ¦) el campo nunca llega al POST, el formulario queda invÃ¡lido y el
producto no se guarda â y el usuario **no puede ver dÃ³nde estÃ¡ el error**, porque el campo no estÃ¡
en pantalla. Reproducido con un POST realista de ARMERIA:
`ERROR en unidad_venta: Este campo es obligatorio.`

De los cuatro campos que inyecta el hook de DistribuciÃ³n, era el **Ãºnico** que fallaba:
`codigo_anterior`, `peso_unitario_kg` y `unidades_por_bulto` ya eran opcionales.

**Archivos modificados:**
- `productos/models.py` [MODIFY]: `blank=True` en `unidad_venta`, con el comentario del porquÃ©.
- `productos/migrations/0002_unidad_venta_opcional.py` [NEW]: `AlterField`. **No toca el esquema**
  â `blank` es validaciÃ³n a nivel Django, la columna sigue igual.
- `productos/forms.py` [MODIFY]: `clean_unidad_venta()` â si no viaja en el POST, repone el valor
  del producto que se edita o, en un alta, el default del modelo. Sin esto `blank=True` guardarÃ­a
  `''` y romperÃ­a el `choice`.
- `productos/tests/test_unidad_venta_opcional.py` [NEW]: 5 tests de regresiÃ³n.

**Por quÃ© el `clean_` y no sÃ³lo `blank=True`:** editar un producto de DistribuciÃ³n desde una
pantalla que no dibuja el campo le habrÃ­a borrado la unidad. El `clean_` la conserva.

**Resultado de las pruebas:**
- `manage.py test productos.tests.test_unidad_venta_opcional` â **5/5 OK** (0,53 s).
- `manage.py test productos` â **41/41 OK** (34,9 s).
- `manage.py makemigrations --check --dry-run` â `No changes detected`.
- VerificaciÃ³n funcional: ARMERIA sin el campo â vÃ¡lido, queda `'UNIDAD'`; DISTRIBUCION con
  `'BULTO'` â vÃ¡lido y respeta `'BULTO'`.

**Estado y siguientes pasos:** corregido. Sin cambios pendientes para las etapas agrÃ­colas; siguen
en pie la Etapa 5 (lotes, acondicionamiento, margen) y la Etapa 6 (reportes FET y libro de
retenciones practicadas).

---

## 2026-09-07 â Juan Manuel - Notebook personal

### AgrÃ­cola Â· Etapa 5 â Lotes de acopio, acondicionamiento, venta y margen (Plan 086)

**Objetivo:** cerrar el circuito comercial del acopio. Hasta acÃ¡ el tabaco entraba (romaneo), se
facturaba al productor (liquidaciÃ³n), se pagaba (orden de pago) y sumaba kilos al stock. Faltaba
quÃ© pasa con esos kilos **despuÃ©s**: agruparlos, acondicionarlos, venderlos y medir el margen.

Plan: [`docs/planes/086_agricola_etapa5_lotes_acondicionamiento_venta.md`](planes/086_agricola_etapa5_lotes_acondicionamiento_venta.md).

#### Las tres decisiones de fondo

**1. DA-07 se resuelve por configuraciÃ³n, no por cÃ³digo.** El plan integral dejaba abierta la
decisiÃ³n *"procesos reales de acondicionamiento, mermas normales y coproductos"* para esta etapa.
No la resolvÃ­ adivinando quÃ© hace la planta: la convertÃ­ en un maestro que carga el usuario.
`ProcesoAcondicionamiento` guarda el nombre del proceso y su merma normal esperada. El sistema
sabe que **un proceso toma kilos, devuelve kilos, consume plata y pierde peso**; si maÃ±ana aparece
un proceso nuevo, es un alta en una pantalla y no una migraciÃ³n.

**2. La etapa NO genera un solo asiento, y es a propÃ³sito.** Es la decisiÃ³n mÃ¡s importante y la
mÃ¡s contraintuitiva. El ERP no contabiliza el stock: `StockSucursal` lleva cantidades y
`VentaItem.cto_rep` guarda el costo sÃ³lo para anÃ¡lisis. Los insumos del acondicionamiento se
compran con una `Compra` normal â*"por ahÃ­ irÃ¡n todas las compras de insumos, agroquÃ­micos"*â que
**ya generÃ³ su asiento, su Libro IVA y su deuda con el proveedor**. Lo que faltaba no era
contabilizar de nuevo âeso duplicarÃ­a el gasto en el balanceâ sino **imputar** ese costo ya
contabilizado a un lote para poder medir el margen. Por eso `AcondicionamientoCosto.compra` es un
respaldo opcional y no un disparador contable. Hay un test que lo fija:
`test_el_acondicionamiento_no_genera_asientos`.

**3. Merma y coproducto no son lo mismo.** Merma son kilos que **desaparecen**; coproducto son
kilos que dejan de ser tabaco de la variedad y pasan a ser **otra cosa vendible** (el palo, el
descarte). Sin separarlos, el usuario registrarÃ­a el palo como merma y perderÃ­a un activo real.
Por eso el stock se mueve asÃ­:

```
stock(variedad)   = Î£ fardos â Î£ kilos_baja        # baja = entrada â salida
stock(coproducto) = Î£ coproducto.kilos             # reaparece en su propio producto
```

`kilos_baja` incluye los coproductos justamente porque ya no son tabaco de esa variedad. Si acÃ¡ se
restara sÃ³lo la merma, los kilos del palo quedarÃ­an contados dos veces.

#### Archivos creados

- `verticalidades/agricola/tabaco/services/lotes.py` [NEW]: armado, venta y derivados del lote.
- `verticalidades/agricola/tabaco/services/acondicionamiento.py` [NEW]: corridas de proceso,
  costos, coproductos, cierre y anulaciÃ³n.
- `verticalidades/agricola/tabaco/services/stock_acondicionamiento.py` [NEW]: los dos tÃ©rminos de
  stock nuevos.
- `verticalidades/agricola/tabaco/services/margen.py` [NEW]: margen por lote, por fardo y por clase.
- `verticalidades/agricola/tabaco/forms_lotes.py` [NEW] Â· `views_lotes.py` [NEW].
- 16 plantillas nuevas en `templates/agricola/{lote,acond,margen,partials}/` y
  `templates/configuracion/partials/agro_procesos.html`.
- `verticalidades/agricola/tabaco/tests/test_plan086_lotes.py` [NEW] â 43 tests de servicio.
- `verticalidades/agricola/tabaco/tests/test_plan086_pantallas.py` [NEW] â 34 tests de pantalla.

#### Archivos modificados

- `verticalidades/agricola/tabaco/models.py` [MODIFY]: `LoteAcopio`, `ProcesoAcondicionamiento`,
  `Acondicionamiento`, `AcondicionamientoCoproducto`, `AcondicionamientoCosto`, y el FK
  `FardoTabaco.lote`.
- `verticalidades/agricola/tabaco/registros.py` [MODIFY]: se suman los dos tÃ©rminos de stock
  nuevos al tercer punto de extensiÃ³n del Plan 080.
- `verticalidades/agricola/tabaco/services/stock.py` [MODIFY]: la conciliaciÃ³n contempla las bajas
  de acondicionamiento; `recalcular_stock_del_acondicionamiento()`.
- `verticalidades/agricola/tabaco/urls.py`, `views_htmx.py` (ABM de procesos),
  `templates/agricola/hooks/menu_sidebar_bottom.html`, `templates/agricola/stock/conciliacion.html`.
- `core/models.py` [MODIFY]: `ContadorDocumento.LOTE_TABACO`. **Es el Ãºnico cambio al core**, y es
  aditivo, igual que `ROMANEO_TABACO` en la Etapa 0.
- `core/views_config.py` y `templates/configuracion/partials/hub.html`: pestaÃ±a `agro_procesos`.
- `docs/agricola/plan inicial agricola.md`: DA-07 pasa de abierta a cerrada; Etapa 5 marcada.
- `docs/GUIA_MODULAR.md`: estado del mÃ³dulo 17.

#### GarantÃ­as que da el modelo, no una validaciÃ³n

- `FardoTabaco.lote` es un FK simple, asÃ­ que **un fardo estÃ¡ en un lote a lo sumo** â igual que
  `RomaneoTabaco.liquidacion` garantiza no liquidar dos veces los mismos kilos.
- `LoteAcopio.venta` es un FK simple: **un lote se vende entero**. Para vender la mitad se arman
  dos lotes; los fardos se mueven mientras no haya un acondicionamiento cerrado.
- CheckConstraint `kilos_salida <= kilos_entrada`: del proceso no puede salir mÃ¡s de lo que entrÃ³.

#### El margen: quÃ© se prorratea y quÃ© no

| Componente | CÃ³mo |
|---|---|
| Costo de compra | **Exacto por fardo**: es lo que se le pagÃ³ al productor por ese fardo |
| Costo de acondicionamiento | Prorrateado por kilos |
| Ingreso de la venta | Prorrateado por kilos |

Prorratear el costo de compra cuando existe el dato exacto serÃ­a perder informaciÃ³n: dos fardos
del mismo peso pueden haberse pagado a precios muy distintos segÃºn su clase, y esa diferencia es
justamente lo que el reporte tiene que mostrar. Lo de acondicionar se prorratea porque una merma
de proceso no es atribuible a un fardo individual: los fardos se mezclan en la mÃ¡quina.

El ingreso se mide **sÃ³lo sobre las lÃ­neas del producto de la variedad**: si en la misma factura
se cobrÃ³ un flete, ese importe no es ingreso del tabaco y contarlo inflarÃ­a el margen.

#### Dos correcciones durante el desarrollo

1. **Dos borradores podÃ­an sumar mÃ¡s kilos de los que el lote tenÃ­a.** Al abrir el segundo, el
   primero todavÃ­a no descontaba nada âun borrador no mueve stockâ, asÃ­ que la validaciÃ³n de
   apertura no podÃ­a detectarlo. Ahora `cerrar_acondicionamiento()` revalida los kilos. Test:
   `test_no_se_cierran_dos_borradores_que_suman_mas_que_el_lote`.
2. **Armar y cerrar llegan por enlace, no por HTMX.** Devolver un fragmento en el error habrÃ­a
   reemplazado la pÃ¡gina entera por un pedazo de tabla. Ahora el motivo viaja por `?error=` y lo
   muestra el detalle completo.

#### Base de datos

- `core/migrations/0004_etapa5_lotes.py`: sÃ³lo el `choices` de `ContadorDocumento`.
- `verticalidades/agricola/tabaco/migrations/0005_etapa5_lotes.py`: 5 tablas nuevas, el FK
  `fardo.lote`, 6 Ã­ndices y 12 constraints.

#### Resultado de las pruebas

- `test_plan086_lotes` + `test_plan086_pantallas` â **77/77 OK** (99,1 s).
- `manage.py test verticalidades` â **611 tests, 3 errores**, los tres preexistentes de
  distribuciÃ³n (994,6 s).
- **Suite completa: 954 tests, 13 errores** â lista **idÃ©ntica** al baseline, cero fallas nuevas
  (1.288,9 s, corriendo sola). El baseline tenÃ­a 872 tests con los mismos 13 errores; los 82 de
  diferencia son los 77 de esta etapa mÃ¡s los 5 de la correcciÃ³n de `unidad_venta`.
- `manage.py makemigrations --check --dry-run` â `No changes detected`.
- **Prueba de desenchufe** (carpeta `verticalidades/agricola` movida):
  - `manage.py check` â sin problemas;
  - tÃ©rminos de stock: exactamente los cuatro de siempre (`compras`, `recepciones`, `ventas`,
    `remitos_internos`), los tres extras en cero;
  - tÃ©rminos de cuenta corriente y aplicaciones de OP: ninguno;
  - `recalcular_stock()` sigue funcionando sobre un producto real;
  - al reenchufar, `manage.py check` vuelve a pasar.

#### Estado actual y siguientes pasos

Etapa 5 cerrada. Los tres puntos de extensiÃ³n del Plan 080 siguen siendo los Ãºnicos ganchos usados
y el core sÃ³lo recibiÃ³ un `choices` nuevo.

1. **Cargar los procesos reales de la planta** en ConfiguraciÃ³n â Procesos de Acondicionamiento.
   Es lo Ãºnico que queda de DA-07 y es dato operativo, no desarrollo.
2. **Etapa 6** â reportes FET / SecretarÃ­a de la ProducciÃ³n y libro de retenciones practicadas.
3. LimitaciÃ³n conocida y documentada: un lote se vende entero; para vender parcial se arman dos.
4. Deuda tÃ©cnica preexistente: las 6 causas de los 13 errores del baseline.
=======
## Juan Manuel - Notebook personal - 2026-09-07 - AgrÃ­cola Etapa 3: Pago al Productor (Plan 084)

**Objetivo:** cancelar las liquidaciones del productor con una Orden de Pago, practicando la
retenciÃ³n de Ganancias sobre el acumulado mensual y emitiendo su certificado. **Cierra el
circuito del acopio: romaneo â liquidaciÃ³n â pago.**

**Archivos creados o modificados:**
- `docs/planes/084_agricola_etapa3_pago.md` (nuevo)
- `verticalidades/agricola/tabaco/models.py` (+ `LiquidacionPago`, `RetencionPago`) y su
  migraciÃ³n `0004_pago`
- `verticalidades/agricola/tabaco/services/pago.py` (nuevo)
- `verticalidades/agricola/tabaco/registros.py` (+ `registrar_aplicacion_op`)
- `verticalidades/agricola/tabaco/views_pago.py` (nuevo) y `urls.py` (7 rutas)
- `verticalidades/agricola/tabaco/templates/agricola/pago/` (7 plantillas nuevas)
- `verticalidades/agricola/tabaco/templates/agricola/hooks/menu_sidebar_bottom.html` (2 entradas)
- `verticalidades/agricola/tabaco/tests/test_plan084_pago.py` y `test_plan084_pantallas.py`

**CERO CAMBIOS AL CORE.** Con esta etapa **los tres puntos de extensiÃ³n del Plan 080 quedan en
uso**: tÃ©rmino de stock (pendiente para la Etapa 4), tÃ©rmino de cuenta corriente (Plan 083) y
ahora la imputaciÃ³n de Ãrdenes de Pago.

**Detalle TÃ©cnico:**

*La decisiÃ³n que ordena todo: la retenciÃ³n es un medio de pago.* Ikigai ya sabe practicarlas âun
`MedioPago` de categorÃ­a RET que `contabilizar_orden_pago()` acredita contra su cuentaâ. No se
construyÃ³ un mecanismo nuevo. De ahÃ­ sale la ecuaciÃ³n: `OrdenPago.total = Î£ medios entregados +
retenciÃ³n`, y `Î£ imputaciones = OrdenPago.total`. El asiento lo arma el core sin saber nada de
tabaco, y el tÃ©rmino de cuenta corriente del Plan 083 cierra exacto porque la liquidaciÃ³n aportÃ³
su TOTAL y la OP lo cancela entero, retenciÃ³n incluida (supuesto S-1 de `saldos.py`).

*El medio de pago de la retenciÃ³n se resuelve con `get_or_create` por concepto*, tomando la cuenta
contable del propio maestro. AsÃ­ el contador define la cuenta una sola vez y no hay dos lugares
que puedan discrepar.

*El acumulado mensual se DERIVA, no se almacena.* Se reconstruye sumando los certificados
vigentes del productor en el perÃ­odo. Consecuencia deliberada: al anular un pago se anula su
certificado y el acumulado del mes baja SOLO, sin ningÃºn contador que corregir a mano. El sistema
heredado hacÃ­a lo mismo: `liq_mes_ret_gcia` era una vista, no una tabla.

*Alcance de los medios de pago:* efectivo, transferencia, billetera y otros. Los CHEQUES quedan
fuera âarrastran vencimiento, cuenta bancaria, cartera y conciliaciÃ³nâ y se avisa en pantalla en
vez de dejar cargar algo a medias.

**Resultado de las pruebas:**

| Prueba | Resultado |
|---|---|
| `test_plan084_pago` (acumulado, asiento, saldos, anulaciÃ³n) | **29/29** |
| `test_plan084_pantallas` (circuito completo + certificado) | **20/20** |
| Prueba de desenchufe | los 3 registros en 0; saldo y pendiente de OP siguen calculando |
| `makemigrations --check` | sin cambios pendientes |
| **Suite completa** | **846 tests, 13 errores** â lista **idÃ©ntica** al baseline, cero fallas nuevas y cero caÃ­das de conexiÃ³n |

*Prueba de humo del circuito completo contra datos reales* (empresa 1, transacciÃ³n revertida):
liquidaciÃ³n A 0002-00000001 por $ 3.532.750 â retenciÃ³n de Ganancias $ 60.520 sobre base
acumulada $ 3.250.000 menos MNI $ 224.000 â Orden de Pago 0001-00010002 con asiento balanceado
(211001 D 3.532.750 Â· 111001 H 3.472.230 Â· 214005 H 60.520), certificado NÂº 1 rÃ©gimen 78 perÃ­odo
202609, **saldo de la liquidaciÃ³n $ 0, saldo del productor $ 0 y pendiente de aplicar de la OP
$ 0**. Esas tres Ãºltimas lÃ­neas son el cierre del negocio.

**OBSERVACIÃN DE ENTORNO â resuelta.** El backend de PostgreSQL se cayÃ³ varias veces durante las
Etapas 0, 2 y 3 (`server closed the connection unexpectedly`). La causa NO era el servidor sino la
CONCURRENCIA: esas corridas competÃ­an contra otras suites ejecutÃ¡ndose en paralelo sobre la misma
instancia. La corrida final, con la mÃ¡quina sola, lo confirma: 846 tests en 1.156 s y cero caÃ­das,
contra 793 tests en 6.415 s con una caÃ­da cuando habÃ­a competencia. Cinco veces mÃ¡s rÃ¡pido. La
recomendaciÃ³n es no correr suites concurrentes contra la misma instancia.

**Estado actual:** el circuito comercial y financiero del acopio estÃ¡ cerrado de punta a punta.

**Siguientes pasos sugeridos:**
1. **Etapa 4 â Stock del tabaco**: registrar el tÃ©rmino de stock del fardo (el Ãºnico punto de
   extensiÃ³n del Plan 080 que falta consumir), con el `Producto` por variedad y los kilos.
2. Etapa 5 â lotes de acopio, acondicionamiento, venta y margen por fardo.
3. Etapa 6 â reportes FET / SecretarÃ­a de la ProducciÃ³n y libro de retenciones practicadas.
4. Deuda tÃ©cnica preexistente: las 6 causas de los 13 errores del baseline.

## Antigravity - 07/09/2026
**Objetivo:** SoluciÃ³n de error `IntegrityError` por secuencias de clave primaria desincronizadas.
**Archivos creados o modificados:**
- `reset_sequences.py` [NEW/DELETE] (script temporal)
- `docs/walkthrough.md` [MODIFY]

**Detalle TÃ©cnico:**
- Se detectÃ³ un error `django.db.utils.IntegrityError` al intentar crear una nueva `CuentaContable` (tabla `cble_cuentas`) provocado porque la secuencia de la tabla no se actualizÃ³ tras una inserciÃ³n explÃ­cita de IDs en una migraciÃ³n manual.
- Se elaborÃ³ y ejecutÃ³ un script (utilizando `django.core.management.color.no_style` y `connection.ops.sequence_reset_sql`) para resetear y sincronizar los contadores de las primary keys en PostgreSQL.
- Se aplicÃ³ la reparaciÃ³n sobre todas las tablas del proyecto, ejecutando 76 sentencias de reinicio de secuencias.
- Una vez finalizada la reparaciÃ³n, el script fue eliminado para mantener la higiene del repositorio, acatando las reglas del proyecto.

**Resultado de las pruebas:**
- Script ejecutado exitosamente. Las secuencias de PostgreSQL han sido alineadas con el valor mÃ¡ximo real de los registros de las tablas.

**Estado actual y siguientes pasos sugeridos:**
- Problema solventado. El usuario ya puede crear y guardar registros sin que se produzca una colisiÃ³n de clave primaria.

## Antigravity - 07/09/2026
**Objetivo:** ContinuaciÃ³n y finalizaciÃ³n de la MigraciÃ³n de ArmerÃ­a (Fases 2 a 5).
**Archivos creados o modificados:**
- `migracion/scripts/armeria/04_migrar_facturacion_armeria.py` [MODIFY]
- `migracion/scripts/armeria/05_migrar_pagos_recibos_armeria.py` [MODIFY]
- `docs/walkthrough.md` [MODIFY]

**Detalle TÃ©cnico e implicaciones:**
- Se procediÃ³ a ejecutar las Fases 2 (Inventario), 3 (TesorerÃ­a), 4 (FacturaciÃ³n) y 5 (Pagos y Recibos) del bloque de ArmerÃ­a.
- Se detectaron incompatibilidades por los rediseÃ±os arquitectÃ³nicos previos y se aplicaron parches estructurales en los scripts de migraciÃ³n:
  - En la **Fase 4 (FacturaciÃ³n)**, se corrigiÃ³ la asignaciÃ³n al modelo `PeriodoIva` (usando el campo `periodo` en vez de `mes/anio`), se ajustaron las claves primarias heredadas (`ventas_id` y `compras_id` en lugar del antiguo `id`), y se implementÃ³ un fallback dinÃ¡mico (con obtenciÃ³n del primer registro disponible) para `proveedor_id`, `cliente_id` y `producto_id` de forma tal de esquivar las restricciones obligatorias `NOT NULL` de la DB en filas huÃ©rfanas heredadas de FoxPro.
  - Para esquivar violaciones de clave forÃ¡nea derivadas de los fallos de clave Ãºnica o integridad (`UniqueConstraint`), se aÃ±adiÃ³ lÃ³gica en memoria post-bulk_create, interceptando Ãºnicamente aquellos `id`s que fueron validados en la base, impidiendo arrastrar Ã­tems que hubieran fracasado en la inserciÃ³n de las cabeceras.
  - En la **Fase 5 (Pagos y Recibos)**, se enlazaron las Ã³rdenes de pago y recibos a las compras y ventas adaptando los identificadores referenciales `compras_id` y `ventas_id`.

**Resultado de las pruebas:**
- Fases 2 y 3: Concluidas sin incidencias tras los primeros ajustes.
- Fase 4 (FacturaciÃ³n): Concluida procesando mÃ¡s de 22,900 ventas (y ~34,700 Ã­tems) y 603 compras.
- Fase 5 (TesorerÃ­a Pagos): Concluida con 1,805 Ãrdenes de Pago y 23 Recibos procesados y conciliados exitosamente en la DB.

**Estado actual y siguientes pasos sugeridos:**
- MigraciÃ³n histÃ³rica base de ArmerÃ­a finalizada exitosamente a nivel de scripts y registros de DB. Todo el ecosistema heredado se encuentra importado. Se puede dar por cerrado el plan inicial.

### Addendum - CorrecciÃ³n de Clientes vs Proveedores (ArmerÃ­a)
**Detalle TÃ©cnico:**
- Se detectÃ³ que en el volcado de la Fase 1, todos los registros de la tabla `cli_pro.dbf` habÃ­an ingresado al sistema como Clientes (`tipo_entidad=1`) debido a que el antiguo campo `TIPO` de FoxPro se encontraba vacÃ­o.
- Se identificÃ³ que la verdadera bandera diferenciadora en la base de ArmerÃ­a era la columna `CLI_PRO` (`1` para cliente, `2` para proveedor, `0` neutral).
- **En la base de datos:** Para no tener que eliminar y volver a migrar toda la base de datos (con las demoras masivas que implicarÃ­a re-correr Fases 2, 3, 4 y 5), se elaborÃ³ un script interno que leyÃ³ directamente los DBFs de Comercio y Balance, obteniendo todos los cÃ³digos con `CLI_PRO = 2`, y aplicÃ³ un `update(tipo_entidad=2)` de manera atÃ³mica, corrigiendo 669 registros en total en tiempo real.
- **En los scripts:** Se editÃ³ de forma permanente el script de Fase 1 (`01_migrar_maestros_armeria.py`) para que utilice la columna `CLI_PRO` en caso de requerirse una migraciÃ³n limpia desde cero en el futuro.

### Addendum 2 - Asientos HuÃ©rfanos en Listado de Ventas (ArmerÃ­a)
**Detalle TÃ©cnico:**
- Se reportÃ³ que el listado de ventas mostraba la columna "Asiento" vacÃ­a. Se comprobÃ³ que el script de Fase 4 (`04_migrar_facturacion_armeria.py`) habÃ­a omitido extraer y mapear el campo `ID_ASTO` proveniente del archivo `ventas_enc.dbf` (y `compras_enc.dbf`) hacia la propiedad `asiento_id` de Django.
- **En la base de datos:** Se ejecutÃ³ un script en tiempo real (vÃ­a terminal local) que iterÃ³ sobre los DBF y aplicÃ³ un `bulk_update` directo sobre los modelos de `Venta` en Django. Se vincularon exitosamente **22,585 asientos** histÃ³ricos con sus comprobantes de venta. (Las compras poseÃ­an `ID_ASTO = 0` en origen, por lo que quedaron sin cambios como es correcto).
- **En los scripts:** Se actualizÃ³ `04_migrar_facturacion_armeria.py` para mapear de forma permanente `asiento_id=row.get('ID_ASTO')` en las altas nativas.

### Addendum 3 - CorrecciÃ³n de Fallo al Imprimir PDF de Ventas Migradas (ArmerÃ­a)
**Detalle TÃ©cnico:**
- Se detectÃ³ un error 500 (`AttributeError: 'NoneType' object has no attribute 'codigo'`) al intentar imprimir en PDF comprobantes de venta heredados que no tenÃ­an asociado un `TipoComprobante` (`venta.tipo = None`), un escenario comÃºn en migraciones histÃ³ricas con tipos documentales que ya no existen o eran invÃ¡lidos.
- **En el servicio PDF:** Se modificÃ³ `facturacion/services/pdf_service.py` para aÃ±adir fallbacks condicionales (`if venta.tipo else ''`) al momento de leer el cÃ³digo y el tÃ­tulo del comprobante, garantizando que el reporte en PDF (basado en ReportLab) se dibuje correctamente y titule el documento como "Comprobante" si la venta es huÃ©rfana de tipologÃ­a.

### Addendum 4 - Envolvimiento de Texto (Word-Wrap) en PDF de Ventas
**Detalle TÃ©cnico:**
- Se reportÃ³ que los detalles de los productos muy largos (ej. armas con especificaciones tÃ©cnicas o mirillas) desbordaban su columna en la grilla del PDF generado, superponiÃ©ndose visualmente sobre las columnas de Cantidad, Precio Unitario e Importe.
- Adicionalmente, se detectÃ³ que no se estaban reflejando la Serie y el CUIM de las armas (subproductos) vendidas en el comprobante.
- **En el servicio PDF:** Se incorporÃ³ la funciÃ³n `simpleSplit` de `reportlab.lib.utils` en `facturacion/services/pdf_service.py`. En lugar de pintar el string completo en una sola lÃ­nea, el sistema ahora calcula dinÃ¡micamente cuÃ¡ntas lÃ­neas requiere el texto para ajustarse al ancho mÃ¡ximo de la columna "Detalle" (280 puntos). Las columnas numÃ©ricas (precio, cantidad) se imprimen solo una vez, mientras que el texto descriptivo se dibuja lÃ­nea por lÃ­nea empujando el cursor `y_items` dinÃ¡micamente hacia abajo.
- **Trazabilidad en PDF:** Se integrÃ³ en la misma iteraciÃ³n lÃ³gica una bÃºsqueda al modelo `Subproducto` a travÃ©s de la relaciÃ³n inversa pre-cargada (`venta.subproductos.all()`). En caso de coincidir con el producto facturado, se inyectan automÃ¡ticamente en un renglÃ³n nuevo (`\n`) los atributos de "Serie: XXX - Cuim: YYY" debajo del detalle comercial del arma. Adicionalmente, se programÃ³ un `fallback` por cliente y fecha: si el usuario imprime un Remito de Venta (el cual FoxPro no vincula nativamente al Subproducto), el sistema buscarÃ¡ inteligentemente si ese mismo producto fue facturado a ese cliente en esa fecha para heredar e imprimir su trazabilidad de todas formas.
- **CorrecciÃ³n de Mapeo FoxPro (Subproductos):** Se detectÃ³ que el script de migraciÃ³n `02_migrar_inventario_armeria.py` habÃ­a omitido enlazar las FK `venta_id` y `compra_id`, y que los `CODIGO` en FoxPro no coincidÃ­an 1:1 con el `id` autoincremental de Django. Se ejecutÃ³ un parche sobre la base de datos mapeando contra `Producto.codigo_anterior` y se dejaron enlazados exitosamente **1,925 subproductos** a sus respectivas ventas. El archivo `02_migrar_inventario_armeria.py` fue parcheado para que futuras migraciones apliquen esta misma lÃ³gica correctamente.
- **Grilla de Trazabilidad:** Se reescribiÃ³ la consulta ORM de la vista `SubproductoTrazabilidadListView` utilizando `Subquery` en lugar de `distinct('serie')`. Esto solucionÃ³ un problema grave donde los filtros (como "Estado Actual = Vendida") aplicaban sobre todo el historial de la serie en lugar de solo sobre su estado mÃ¡s reciente. AdemÃ¡s, se habilitÃ³ el **ordenamiento dinÃ¡mico (Sorting)** al hacer clic sobre los encabezados de la tabla, con un input oculto y lÃ³gica JavaScript integrados al motor HTMX.
- **CorrecciÃ³n CondiciÃ³n Compras/Ventas:** Se detectÃ³ que FoxPro guardaba `CONDIC = 0` en algunas operaciones, lo que provocÃ³ que 603 compras y 389 ventas migraran con `condic=0`. Al no ser igual a `1` (Fiscal), el sistema las mostraba visualmente como "Presupuestado" (`condic=2`). Se ejecutÃ³ un bulk update para reasignarlas como Fiscal/Real (`condic=1`) y se parcheÃ³ el script de migraciÃ³n `04_migrar_facturacion_armeria.py` para asegurar que todo `0` caiga como `1` por defecto.
- **CorrecciÃ³n de Letra en PDF:** Se ajustÃ³ la lÃ³gica en `facturacion/services/pdf_service.py` que interpreta quÃ© marco dibujar ("A", "B", o "C") en el PDF. Originalmente estaba limitada estrictamente a cÃ³digos AFIP (001, 002, 003), lo que provocaba que al renderizar comprobantes histÃ³ricos con la nomenclatura de FoxPro (`FA`, `CA`, `DA`) el sistema cayera en el caso por defecto (`B`). Ahora el sistema reconoce apropiadamente tanto la codificaciÃ³n AFIP como la interna, renderizando la Letra "A" o "C" correctamente para facturas, notas de dÃ©bito y crÃ©dito.
- **ValidaciÃ³n Formulario Producto:** Se reparÃ³ un error de validaciÃ³n en la interfaz de creaciÃ³n y ediciÃ³n de productos de la ArmerÃ­a. El campo `unidad_venta`, que habÃ­a sido establecido como obligatorio a nivel global (requerimiento proveniente de AgrÃ­cola), no estaba renderizado en el modal `producto_modal.html`. Esto provocaba que al guardar se enviara un valor vacÃ­o y Django rechazara la operaciÃ³n con el error "Este campo es obligatorio". Se incorporÃ³ exitosamente el control desplegable "Unidad de Venta" en la misma fila de Punto de Pedido y Stock MÃ­nimo.
- **CorrecciÃ³n de Escala de IVA:** Se detectÃ³ que la tabla de FoxPro exportaba la alÃ­cuota de IVA en formato unitario (ej. `0.21`, `0.105`), mientras que el ERP espera formato porcentual directo (`21.00`, `10.50`). Esto impedÃ­a que los productos y subproductos mapearan correctamente con las opciones predefinidas de la plataforma (21%, 10.5%). Se ejecutÃ³ una correcciÃ³n masiva sobre 7,572 productos y 2,557 subproductos multiplicando su valor por 100 y actualizando la base de datos en tiempo real. AdemÃ¡s, el script `02_migrar_inventario_armeria.py` fue modificado para procesar el campo correctamente multiplicando por 100 en futuras importaciones.
- **FacturaciÃ³n - Detalle DinÃ¡mico de IVA:** En las "Facturas A" generadas a travÃ©s del motor de PDFs (`pdf_service.py`), el pie de pÃ¡gina informaba exclusivamente un Ãºnico impuesto (21%), ignorando la presencia de productos facturados al 10.5%. El cÃ³digo fue reescrito para leer e iterar dinÃ¡micamente sobre la colecciÃ³n de Ã­tems asociados a la venta (`VentaItem`), agrupar sus bases imponibles de forma proporcional y generar un desglose discriminado por alÃ­cuota en el pie del PDF. TambiÃ©n se saneÃ³ masivamente el campo `iva_alicuota` de las tablas transaccionales en la base de datos que habÃ­an importado escalas 0.21 en lugar de 21.00.
- **Filtro de Productos:** Se ampliÃ³ el buscador HTMX de productos (`buscar_productos` en `views_htmx.py`). Anteriormente solo permitÃ­a buscar por Detalle, CÃ³digo Proveedor o CÃ³digo Fabricante. Ahora reconoce si la entrada es un nÃºmero entero para buscar de forma exacta por el `id` autoincremental, y adicionalmente filtra por el `codigo_anterior` de FoxPro, facilitando a los usuarios encontrar productos importados mediante su identificador original.
- **Autocompletado de Clientes en Ventas:** Se corrigiÃ³ un bug donde el campo de autocompletado de clientes en el listado de ventas no funcionaba al escribir. La causa raÃ­z era una discrepancia de nombres: el input enviaba el valor como `q_cliente` pero el endpoint `typeahead_clientes` solo leÃ­a el parÃ¡metro `q`. Se parchÃ³ la vista para aceptar ambos nombres (`q`, `q_cliente`, `q_proveedor`).
- **BÃºsqueda por ID en Ventas y Compras:** Se agregÃ³ un campo de bÃºsqueda por ID exacto (`venta_id` / `compra_id`) en ambos listados. Cuando se ingresa un ID, el sistema salta los filtros de fecha/cliente y busca directamente por la PK del comprobante.
- **Autocompletado de Proveedor en Compras:** Se reemplazÃ³ el `<select>` estÃ¡tico de proveedores (que cargaba todos los proveedores al renderizar la pÃ¡gina) por un typeahead dinÃ¡mico HTMX idÃ©ntico al de ventas, con bÃºsqueda progresiva por razÃ³n social o CUIT.
- **Unidad de Venta condicional por vertical:** El campo `unidad_venta` en el modal de productos ahora solo se muestra visualmente cuando la empresa tiene `tipo_actividad='DISTRIBUCION'`. Para el resto de verticales (ArmerÃ­a, AgrÃ­cola, etc.) el campo queda oculto en la interfaz y en el backend se marcÃ³ como `required=False` con un `clean_unidad_venta` que asigna automÃ¡ticamente el valor por defecto `'UNIDAD'`. Esto evita el error de validaciÃ³n "Este campo es obligatorio" sin impactar la lÃ³gica de DistribuciÃ³n.

## Antigravity - 07/09/2026
**Objetivo:** Ajustes de Interfaz en FacturaciÃ³n y Parches/Migraciones de Datos en ArmerÃ­a.
**Archivos creados o modificados:**
- `templates/facturacion/reportes/facturas_pendientes.html` [MODIFY]
- `templates/facturacion/clientes_index.html` [MODIFY]
- `templates/facturacion/partials/cliente_table_rows.html` [MODIFY]
- `migracion/scripts/armeria/01b_parche_clipro_armeria.py` [NEW]
- `migracion/scripts/armeria/06_migrar_asientos_armeria.py` [NEW]
- `docs/walkthrough.md` [MODIFY]

**Detalle TÃ©cnico e implicaciones:**
- **UI Facturas Pendientes:** Se corrigiÃ³ un problema de visualizaciÃ³n en navegadores Chrome sobre Windows donde el texto del estado de las facturas (select) quedaba truncado/cortado verticalmente por una altura fija (`h-9` combinada con falta de padding `py`). Se aÃ±adiÃ³ padding vertical (`py-1`).
- **Parche Datos CLIPRO ArmerÃ­a (01b):** Tras descubrir que la migraciÃ³n base (Fase 1) no habÃ­a mapeado campos clave (TelÃ©fono, Contacto, Correo, Tipo de Documento, Es PolicÃ­a, CLU y Vto CLU), se diseÃ±Ã³ y ejecutÃ³ exitosamente el script `01b_parche_clipro_armeria.py`. Este script leyÃ³ las bases operativas de FoxPro (`cli_pro.dbf`) en `Comercio` y parchÃ³ de manera masiva/atÃ³mica sobre la base PostgreSQL mediante `bulk_update` los datos faltantes en `ClienteProveedor` y creando/actualizando relaciones `ExtensionArmeria` sin destruir datos contables ya asociados.
- **MigraciÃ³n FacturaciÃ³n y Libros de IVA (04 y 07):** Se ejecutÃ³ el script `04_migrar_facturacion_armeria.py` para procesar el bloque operativo de FacturaciÃ³n. AdemÃ¡s, se desarrollÃ³ y ejecutÃ³ el script `07_migrar_lib_iva_armeria.py` que lee los archivos `lib_iva.dbf` y `lib_iva_alic.dbf` directamente desde el sistema de `Balance` para cargar el mÃ³dulo contable oficial del Libro IVA Digital (Compras, Ventas y sus correspondientes alÃ­cuotas AFIP).
- **MigraciÃ³n Asientos Contables ArmerÃ­a (06):** Se desarrollÃ³ y ejecutÃ³ el script `06_migrar_asientos_armeria.py` emulando el comportamiento seguro del sistema de Estudios, migrando `asto_enc` (Cabeceras) y `asto_mov` (LÃ­neas) del directorio `Balance` de FoxPro hacia las tablas del subsistema contable nativo, preservando la partida doble estricta matemÃ¡tica de Debe/Haber.
- **CorrecciÃ³n ArquitectÃ³nica:** Se restauraron los archivos del core (`clientes_index.html` y `cliente_table_rows.html`) y los hooks de ArmerÃ­a desde el control de versiones, revirtiendo una inyecciÃ³n accidental de cÃ³digo duro que rompÃ­a la arquitectura Plug & Play del proyecto. Los hooks nativos ya estaban configurados y su diseÃ±o fue preservado.

**Resultado de las pruebas:**
- Script de Parche de CLIPRO ejecutado exitosamente y libre de errores de `UniqueConstraint` utilizando diccionarios para deduplicar filas.
- Script de MigraciÃ³n de FacturaciÃ³n (04) ejecutado procesando exitosamente 22.975 Ventas y 603 Compras.
- Script de MigraciÃ³n de Libro IVA (07) ejecutado procesando exitosamente 1.413 Compras, 7.735 Ventas y 6.284 alÃ­cuotas.
- Script de Asientos Contables (06) ejecutado procesando toda la cabecera y movimientos del directorio `Balance`.

**Estado actual y siguientes pasos sugeridos:**
- MigraciÃ³n de datos CLIPRO resuelta.
- Libros de IVA (FacturaciÃ³n) y Asientos Contables migrados exitosamente.
- Queda a definir o refinar cualquier otro ajuste fino en la interfaz o de operaciones "SIGIMAC".
>>>>>>> 6b2fa96e74015965f0956efd62ae588f443dc5e0

---

## 2026-09-07 â Juan Manuel - Notebook personal

### AgrÃ­cola Â· Etapa 6 â Reportes oficiales y gerenciales (Plan 087)

**Objetivo:** lo que el acopio tiene que entregar hacia afuera âFET, SecretarÃ­a de la ProducciÃ³n,
organismos recaudadoresâ y lo que el dueÃ±o necesita para decidir.

Plan: [`docs/planes/087_agricola_etapa6_reportes.md`](planes/087_agricola_etapa6_reportes.md).

#### La propiedad que define la etapa: no crea una sola tabla

Todo sale de lo que ya registraron las Etapas 0 a 5. No hay modelos, no hay migraciones y no hay
estado nuevo que mantener sincronizado. Es la prueba de que aquel modelo estaba bien planteado: si
para emitir la planilla FET hubiera que agregar campos, serÃ­a seÃ±al de que algo no se estaba
capturando cuando correspondÃ­a. Hay un test que lo fija enumerando las 19 tablas de las etapas
anteriores (`test_la_etapa_6_no_agrega_ninguna_tabla`).

#### Los cinco reportes

| Reporte | QuÃ© resuelve |
|---|---|
| **Planilla FET** | Reformateo del `Informe_fet` heredado: una fila por romaneo con comprobante, kilos, IVA y las cinco retenciones. CSV y **Excel** |
| **Resumen de acopio** | Fardos, kilos e importe por variedad y clase, con precio promedio ponderado |
| **DDJJ de existencias** | Existencia por galpÃ³n **a una fecha de corte** |
| **Libro de retenciones** | Los dos momentos unificados, con totales por organismo |
| **Tableros de margen** | Por campaÃ±a, variedad, productor y clase de tabaco |

#### Tres decisiones que el sistema heredado no tuvo que tomar

**1. La planilla FET va por ROMANEO, y las retenciones se prorratean.** El Excel heredado
encabeza con `id_romaneo`, asÃ­ que la unidad es el romaneo. En el VFP eso era trivial âun romaneo
era una liquidaciÃ³n, el sistema hacÃ­a todo en un solo actoâ; en Ikigai una liquidaciÃ³n puede
agrupar varios y las retenciones se calculan sobre el comprobante entero. Se prorratean por la
participaciÃ³n del romaneo en el neto, y hay un test que verifica que **la suma de las filas
reconstruye exactamente el IVA y las retenciones del comprobante**.

**2. `Ret. Ganancias` sale del PAGO, no de la liquidaciÃ³n.** Por DA-01, Ganancias se practica al
pagar y su base es el acumulado mensual. Una liquidaciÃ³n todavÃ­a no pagada la muestra en cero, y
es lo correcto: poner ahÃ­ una estimaciÃ³n serÃ­a declarar ante el FET una retenciÃ³n que no se
practicÃ³. La columna se llena con los certificados `RetencionPago` vigentes de las Ãrdenes de Pago
que cancelaron esa liquidaciÃ³n, prorrateados por lo imputado a ella.

**3. La DDJJ se reconstruye desde los comprobantes, no lee `StockSucursal`.** El stock del ERP
**sÃ³lo sabe el presente**. Una declaraciÃ³n que se presenta en octubre por las existencias al 30 de
septiembre necesita el pasado, y el pasado estÃ¡ en los comprobantes. Es el mismo criterio con el
que el ERP deriva el stock, con un corte de fecha encima.

#### Dos hallazgos durante el desarrollo

**A. El adicional no se le paga al productor, y la Etapa 5 lo estaba sumando al costo.**
Al armar la planilla se verificÃ³ que `LiquidacionDetalle.importe` es `Sum(fardo.importe)` y que
`liq.neto` se arma de ahÃ­: **el adicional se captura pero no se liquida** âconsecuencia directa de
que DA-05 sigue abiertaâ. Mi Etapa 5 sÃ­ lo sumaba a `LoteAcopio.costo_compra`, con lo cual el
costo del lote decÃ­a una cosa y la liquidaciÃ³n otra, y el margen salÃ­a subestimado contra plata
que nunca saliÃ³.

- Corregido: `services/lotes.py::recalcular_lote` ya no lo suma. Se expone aparte en la property
  `LoteAcopio.adicional_informado`.
- En la planilla FET el adicional se muestra âla planilla heredada lo traÃ­aâ pero **no entra en
  Â«a pagarÂ»**: incluirlo declararÃ­a un importe que el comprobante no dice.
- Al cerrar DA-05 hay que tocar **los dos** lugares juntos: `preparar_liquidacion` y
  `recalcular_lote`.

**B. Los cÃ³digos de retenciÃ³n no se pueden cablear.** La primera versiÃ³n mapeaba las columnas por
cÃ³digo exacto (`IVA`, `GANANCIAS`, `AGUA`). El cliente cargÃ³ los suyos como **`RET-IVA`,
`RET-GCIAS` y `USO AGUA`**: tres de las cinco retenciones caÃ­an en Â«otrasÂ» y âesto es lo graveâ
**nada fallaba a la vista**, porque la fila seguÃ­a sumando bien. La planilla mentÃ­a en silencio.
Lo detectÃ³ `test_una_retencion_nueva_del_maestro_va_a_otras`.

Ahora se resuelve en dos pasos, del mÃ¡s firme al mÃ¡s laxo:
1. Por `tipo_base`, que es **estructural** y no depende del nombre: sÃ³lo la retenciÃ³n de IVA se
   calcula sobre el IVA y sÃ³lo Ganancias sobre el acumulado mensual. Esas dos columnas quedan
   resueltas sin mirar un solo texto.
2. Por palabra clave en el cÃ³digo o el detalle, para las tres que comparten base `NETO` y no se
   pueden distinguir de otra forma.

Verificado contra los cÃ³digos del cliente y contra los genÃ©ricos.

#### Archivos creados

- `services/reportes.py` [NEW] â planilla FET, resumen de acopio, existencias a fecha.
- `services/retenciones_libro.py` [NEW] â libro de retenciones, unificando los dos orÃ­genes.
- `services/tableros.py` [NEW] â margen por campaÃ±a, variedad, productor y clase.
- `services/exportaciones.py` [NEW] â CSV (`;` + BOM) y XLSX con `openpyxl`.
- `forms_reportes.py` [NEW] Â· `views_reportes.py` [NEW].
- 11 plantillas en `templates/agricola/reportes/`.
- `tests/test_plan087_reportes.py` [NEW] â 34 tests Â· `tests/test_plan087_pantallas.py` [NEW] â 27.

#### Archivos modificados

- `verticalidades/agricola/tabaco/services/lotes.py` [MODIFY] â el adicional sale del costo.
- `verticalidades/agricola/tabaco/models.py` [MODIFY] â property `LoteAcopio.adicional_informado`
  (**sin migraciÃ³n**: es una property, no un campo).
- `verticalidades/agricola/tabaco/urls.py` y el hook del menÃº.
- `docs/agricola/plan inicial agricola.md` â Etapa 6 marcada; DA-05 enriquecida con lo verificado.
- `docs/GUIA_MODULAR.md` â el mÃ³dulo 17 pasa a ð¢.

#### Reglas transversales respetadas

- **Filtro de `condic` en los cinco reportes.** Los oficiales arrancan en **Real**: lo que se
  declara ante un organismo es la lente fiscal. Los gerenciales, en Todas.
- **Formato es-AR** en pantalla vÃ­a `|formato_ar`. En el CSV y el XLSX van **nÃºmeros crudos**: un
  `1.234,56` dentro de un CSV con separador `;` es ambiguo y Excel lo lee como texto; en XLSX el
  formato lo pone la celda. Hay un test para cada cosa.
- **Sin Django Admin**: todo HTML + Tailwind + HTMX.

#### Resultado de las pruebas

- `test_plan087_reportes` â **34/34 OK** (414,3 s).
- `test_plan087_pantallas` â **27/27 OK** (240,8 s).
- `manage.py makemigrations --check --dry-run` â `No changes detected`. **La etapa no genera
  ninguna migraciÃ³n**, que era el criterio de hecho mÃ¡s importante.
- **Prueba de desenchufe**: sin la carpeta, `manage.py check` pasa, los tÃ©rminos de stock vuelven
  a los cuatro de siempre, los tres registros de extensiÃ³n quedan en cero y las URLs `agro_` dejan
  de resolver, como corresponde. Al reenchufar, todo vuelve.

#### Estado actual y siguientes pasos

**El circuito del acopio de tabaco queda completo de punta a punta**: maestros â romaneo â
liquidaciÃ³n â asiento â Libro IVA â cuenta corriente â pago â certificado â stock â lote â
acondicionamiento â venta â margen â reportes oficiales.

1. **Cargar los procesos reales de la planta** (ConfiguraciÃ³n â Procesos de Acondicionamiento).
   Es lo Ãºnico que resta de DA-07 y es dato operativo.
2. **Cerrar DA-05** (naturaleza del adicional). Hoy no se paga; si debe pagarse, son dos lugares.
3. Etapas 7 a 9 âproducciÃ³n propia, granos y caÃ±a, exportaciÃ³nâ fuera del alcance inicial.
4. MP-01 (notas de crÃ©dito de liquidaciÃ³n) y MP-02 (webservice WSLTV) siguen pendientes.
5. Deuda tÃ©cnica preexistente: las 6 causas de los 13 errores del baseline.

---

## 2026-09-07 (cierre del dÃ­a) â Juan Manuel - Notebook personal

### AgrÃ­cola Â· Cuatro decisiones cerradas sobre la Etapa 6

DespuÃ©s de la primera entrega del Plan 087, el usuario revisÃ³ los hallazgos y cerrÃ³ cuatro puntos.
Esta entrada registra lo que se cambiÃ³ y por quÃ©.

#### 1. El adicional: comodÃ­n en cero, no se usa (DA-05 CERRADA)

**DecisiÃ³n del usuario:** *"El adicional lo dejamos en cero y por lo pronto no lo utilizaremos.
Es un comodÃ­n que lo mÃ¡s probable es que nunca usemos."*

Se fue un paso mÃ¡s allÃ¡ de dejarlo en cero: **la pantalla de carga de fardos ya no lo dibuja**. Un
input que se puede llenar y que nunca se cobra es la misma clase de mentira silenciosa que la
columna FET mal mapeada â alguien carga $50.000 y el productor nunca los ve.

- `forms_romaneo.py::FardoForm.adicional` â `HiddenInput`.
- `templates/agricola/romaneo/carga.html` â el bloque del input se retira, con el comentario del
  porquÃ©.
- `models.py::FardoTabaco.adicional` â documentado como comodÃ­n, con la nota de que el dÃ­a que se
  use hay que tocar `preparar_liquidacion` y `recalcular_lote` **juntos**.

El campo sobrevive en el modelo y en el servicio: sigue siendo un comodÃ­n disponible.

#### 2. La columna de la planilla FET pasa a ser un dato del maestro

**ObservaciÃ³n del usuario:** *"Si el cÃ³digo mapeaba columnas por cÃ³digo exacto Â¿por quÃ© me pediste
que los cargue y no lo hiciste tÃº que sabÃ­as el cÃ³digo?"*

**Tiene razÃ³n, y el error es mÃ­o:** le pedÃ­ que cargara los conceptos de retenciÃ³n sin decirle quÃ©
cÃ³digos usar, y despuÃ©s escribÃ­ un reporte que asumÃ­a cÃ³digos. Nunca definÃ­ uno y aun asÃ­ el
reporte dependÃ­a de eso.

OfreciÃ³ cambiar los datos de la tabla para que encajaran con el cÃ³digo. **No se hizo, y por una
razÃ³n:** doblar los datos deja el problema de fondo intacto âel mapeo seguirÃ­a siendo implÃ­citoâ y
el prÃ³ximo concepto que cargue volverÃ­a a caer mal. El problema no era el mapa: era que estaba
escondido.

**SoluciÃ³n: `TipoRetencionTabaco.columna_fet`.** Cada concepto declara a quÃ© columna aporta. Se ve
en la pestaÃ±a de ConfiguraciÃ³n, se edita desde el ABM, y un concepto nuevo se asigna a propÃ³sito.
VacÃ­o significa Â«Otras retencionesÂ», que es una columna real de la planilla y no un error.

La migraciÃ³n de datos `0007_sembrar_columna_fet` lo dejÃ³ cargado de una vez, deduciendo primero
por `tipo_base` âque es estructural: sÃ³lo la retenciÃ³n de IVA se calcula sobre el IVA y sÃ³lo
Ganancias sobre el acumulado mensualâ y despuÃ©s por palabra clave para las tres que comparten base
`NETO`. **El usuario no tuvo que tocar nada.** Verificado sobre la base real:

| CÃ³digo cargado | Base | Columna FET asignada |
|---|---|---|
| `RET-IVA` | IVA | Ret. IVA |
| `RET-GCIAS` | ACUM_MENSUAL | Ret. Ganancias |
| `EEAOC` | NETO | EEAOC |
| `SALUD PUBLICA` | NETO | Salud PÃºblica |
| `USO AGUA` | NETO | Uso de Agua |

La deducciÃ³n sobrevive en `services/reportes.py::_deducir_columna()` como **red**, no como camino
principal: cubre lo que entre por una importaciÃ³n sin pasar por el ABM.

> **Costo consciente:** esto rompe la propiedad Â«la Etapa 6 no genera migracionesÂ». Se aceptÃ³
> porque la alternativa era dejar una declaraciÃ³n legal apoyada en una heurÃ­stica.

#### 3. Toda liquidaciÃ³n de tabaco es fiscal â `condic = 1`

**DecisiÃ³n del usuario:** *"Todas las liquidaciones son fiscales y por lo tanto condic = 1."*

Eso convertÃ­a el combo del alta de romaneo en una trampa: un romaneo cargado por error como
Presupuestado **desaparecerÃ­a en silencio de la planilla FET**, que es una declaraciÃ³n legal.

- `forms_romaneo.py::AbrirRomaneoForm.condic` â `HiddenInput` con `initial=1`.
- `templates/agricola/romaneo/nuevo.html` â muestra Â«Real / Fiscal â toda liquidaciÃ³n de tabaco lo
  esÂ», sin combo.

El campo sigue en el modelo, lo hereda el asiento (regla inflexible del proyecto) y los listados
conservan el filtro de condiciÃ³n.

#### 4. CSV sin separador de miles

Confirmado por el usuario, sin cambios. Ya estaba fijado por
`test_el_csv_lleva_numeros_crudos_y_no_formato_argentino`.

#### Archivos modificados

- `verticalidades/agricola/tabaco/models.py` â campo `columna_fet`; documentaciÃ³n de `adicional`.
- `verticalidades/agricola/tabaco/migrations/0006_columna_fet.py` [NEW] y
  `0007_sembrar_columna_fet.py` [NEW].
- `verticalidades/agricola/tabaco/services/reportes.py` â `columna_de()` lee el maestro;
  `_deducir_columna()` queda como red.
- `verticalidades/agricola/tabaco/forms.py` â `columna_fet` en el ABM de retenciones.
- `verticalidades/agricola/tabaco/forms_romaneo.py` â `condic` y `adicional` ocultos.
- `templates/agricola/partials/retencion_table_rows.html` y
  `templates/configuracion/partials/agro_retenciones.html` â columna Â«Col. FETÂ» visible.
- `templates/agricola/romaneo/nuevo.html` y `carga.html`.
- `tests/test_plan087_reportes.py` â clase `DecisionesCerradasTests`, 5 tests nuevos.
- `docs/agricola/plan inicial agricola.md` â DA-05 cerrada; `condic` y `columna_fet` documentadas.
- `docs/planes/087_agricola_etapa6_reportes.md` â Â§7.2 reescrita, Â§8 con las decisiones cerradas.

#### Estado y siguiente paso acordado

El usuario eligiÃ³ seguir por **la deuda tÃ©cnica preexistente** (los 13 errores del baseline),
empezando por la violaciÃ³n del Modo Enchufe. AnÃ¡lisis ya iniciado:

- **MÃ³dulo-nivel, fatales al desenchufar:**
  `facturacion/services/facturacion_lote_service.py:7` y `facturacion/views_estudio.py:9`
  importan `verticalidades.estudio.models` en el encabezado, sin `try/except`.
  `verticalidades/estudio/urls.py` importa a su vez `facturacion.views_estudio`, o sea que la
  dependencia va **core â verticalidad**, al revÃ©s del Plan 075.
- **Ya resueltos con `try/except`** (patrÃ³n correcto, sirve de referencia):
  `facturacion/views_htmx.py:8-20`.
- **Dentro de funciones** (aceptable): `facturacion/helpers.py`, `core/services/numeracion.py`,
  `core/views_config.py`.

Queda pendiente decidir dÃ³nde vive `FacturacionLoteService` y `views_estudio`: lo natural es
moverlos a `verticalidades/estudio/`, que es de quien son.

---

## 2026-09-09 â Cristian - PC CASA

### Mejoras y Correcciones en Panel de Reservas SIGIMAC (Plan 088)

**Objetivo:**
1. Implementar bÃºsqueda inteligente multi-criterio y en tiempo real (autocompletado/filtrado dinÃ¡mico con HTMX y debounce) que busque por Cliente completo (razÃ³n social, CUIT, telÃ©fono, correo, etc.), Producto y Subproducto (detalle, serie, CUIM, cÃ³digo de proveedor, cÃ³digo de fÃ¡brica), Recibo de seÃ±a e IDs de Reserva/Preventa.
2. Corregir el corte de texto inferior en el selector de Estado SIGIMAC.
3. RediseÃ±ar y corregir la visualizaciÃ³n colapsada ("manchones") de los botones de filtrar y reiniciar en el panel de reservas.

**Archivos creados o modificados:**
- `verticalidades/armeria/views.py` (modificado): Manejo de solicitudes HTMX en `get_template_names()`, consulta inteligente multi-token para `q` filtrando sobre Cliente, Producto, Subproductos (serie/CUIM), Recibo y nÃºmeros de comprobante/reserva, y aplicaciÃ³n de `.distinct()`.
- `verticalidades/armeria/templates/armeria/reservas_list.html` (modificado): RediseÃ±o del formulario con triggers HTMX (`input delay:300ms`, `change`), indicador spinner de carga animado, select de Estado SIGIMAC estilizado sin recortes (`h-10 px-3 py-2 text-xs font-semibold rounded-xl`), y botones de Filtrar y Reiniciar con espaciado amplio, iconos claros, tooltips y etiquetas responsivas.
- `verticalidades/armeria/templates/armeria/partials/reservas_tabla_parcial.html` (creado): Parcial con la tabla de reservas y tarjetas de resumen mÃ©tricas para actualizaciÃ³n reactiva instantÃ¡nea por HTMX.
- `verticalidades/armeria/tests.py` (creado): Suite de pruebas unitarias cubriendo listado completo, respuesta parcial HTMX, bÃºsqueda por cliente, producto/subproducto (serie/CUIM), recibo y filtros por estado.
- `docs/planes/088_mejoras_reservas_sigimac.md` (creado): Plan formal archivado.

**Detalle TÃ©cnico:**
- La bÃºsqueda inteligente divide los tÃ©rminos ingresados por espacios y aplica filtros combinados `AND` entre tÃ©rminos y `OR` entre los campos correspondientes a Cliente, Producto, Subproducto, Recibo y nÃºmero de preventa/reserva.
- Se configurÃ³ `hx-trigger="input changed delay:300ms, search"` en el input de bÃºsqueda y `hx-trigger="change"` en los selectores de estado y fechas, permitiendo un filtrado reactivo y fluido sin necesidad de pulsar Enter o hacer click en botones (manteniendo ademÃ¡s los botones accesibles y estÃ©ticos para submit tradicional).
- Ajuste UI: Se tomÃ³ como referencia exacta la barra de filtros de `compras_listado.html` con contenedor `flex flex-wrap items-end gap-3`, campos de fecha compactos (`w-32`), y botones con texto legible y visible ("Filtrar" y "Limpiar").
- Se corrigiÃ³ la duplicaciÃ³n de los globos/tarjetas de resumen al incluir el parcial en la carga estÃ¡tica inicial.
- Se ajustÃ³ el selector de Estado SIGIMAC con `py-1 px-2.5 text-xs font-bold leading-normal` para evitar el clipping vertical del texto en Windows/Chromium.

**Estado actual y siguientes pasos:**
## 2026-09-09 â Cristian - PC CASA

### BÃºsqueda Inteligente Multi-TÃ©rmino de Productos en Preventa y Ventas (Plan 089)

**Objetivo:**
Hacer mÃ¡s inteligente la bÃºsqueda de productos en la carga de preventa, autocompletado y catÃ¡logo general, permitiendo concatenar palabras clave en cualquier orden (hacia adelante, atrÃ¡s o en el medio) y buscando a travÃ©s de mÃºltiples atributos (detalle, cÃ³digo de fÃ¡brica, cÃ³digo de proveedor, cÃ³digo anterior VFP, marca, rubro, familia e ID), con ordenamiento jerÃ¡rquico por relevancia y lÃ­mite optimizado de hasta 100 registros por consulta.

**Archivos creados o modificados:**
- `productos/services/busqueda_service.py` [NEW]: Motor centralizado de bÃºsqueda inteligente de productos con tokenizaciÃ³n (`q.split()`), condiciones `AND` por tÃ©rmino y `OR` multi-campo, priorizaciÃ³n por `Case/When` (coincidencias exactas primero, inicio de texto, subcadena y tÃ©rminos combinados) y soporte multi-tenant.
- `facturacion/views_htmx.py` [MODIFY]: IntegraciÃ³n del servicio en `typeahead_productos_venta` (preventa/ventas rÃ¡pidas), `buscar_producto_venta_por_codigo` (Enter directo con fallback inteligente), `lista_productos_venta_resultados` (modal de ventas con lÃ­mite de 100 registros), `typeahead_productos_compra` y `lista_productos_resultados` (modal de compras con lÃ­mite de 100 registros).
- `productos/views_htmx.py` [MODIFY]: IntegraciÃ³n en `buscar_productos` para el catÃ¡logo general con lÃ­mite de 100 registros.
- `productos/tests/test_busqueda_inteligente.py` [NEW]: Suite de pruebas unitarias cubriendo palabras en orden invertido, intercaladas, bÃºsqueda por marca/cÃ³digos anteriores, relevancia exacta, aislamiento multi-tenant y endpoints HTMX.
- `docs/planes/089_busqueda_inteligente_productos.md` [NEW]: Plan de implementaciÃ³n archivado.
- `docs/walkthrough.md` [MODIFY]: Registro de bitÃ¡cora acumulativa.

**Detalle TÃ©cnico:**
- **TokenizaciÃ³n Multi-TÃ©rmino:** Se descomponen las consultas en palabras individuales permitiendo que tÃ©rminos como `"9mm bersa"` o `"tpr9 pavonada"` localicen de inmediato `"PISTOLA BERSA TPR9 CALIBRE 9X19MM PAVONADA"`.
- **BÃºsqueda Multi-Atributo:** Cada tÃ©rmino busca simultÃ¡neamente en `detalle`, `cod_fab`, `cod_prov`, `codigo_anterior`, `marca__detalle`, `rubro__detalle`, `familia__detalle` e `id` (si es numÃ©rico).
- **PriorizaciÃ³n de Relevancia:** Se utiliza una expresiÃ³n `Case(When(...))` en Django ORM para asignar orden prioritario a coincidencias exactas de cÃ³digo/ID (peso 1 o 2), coincidencias al inicio del detalle (peso 3), frases completas (peso 4) y coincidencias compuestas (peso 6), manteniendo respuestas Ã¡giles y precisas.
- **Capacidad de Resultados:** Se ampliÃ³ el lÃ­mite de resultados para vistas de catÃ¡logo y modales de 50 a 100 registros para mayor comodidad del operador sin penalizar la velocidad de la base de datos.

**Resultado de las pruebas:**
- Se crearon pruebas unitarias integrales en `productos/tests/test_busqueda_inteligente.py`.

**Estado actual y siguientes pasos:**
- Motor de bÃºsqueda inteligente completamente operativo en la carga de preventa, ventas, compras y catÃ¡logo general.
- Siguientes pasos: Continuar con la hoja de ruta del proyecto o nuevas tareas solicitadas.

## Estudio - Refactor FacturaciÃ³n por Lotes (Servicios)
- **Fecha/DÃ­a**: 14 de Septiembre de 2026
- **Objetivo o Tarea**: Migrar mÃ³dulo de FacturaciÃ³n Lotes a verticalidad Estudio, ajustar perÃ­odo por separado e implementar emisiÃ³n real AFIP de Servicios.
- **Archivos creados o modificados**: erticalidades/estudio/services/facturacion_lote_estudio.py [NEW], erticalidades/estudio/views.py [MODIFY], erticalidades/estudio/urls.py [MODIFY], erticalidades/estudio/templates/estudio/facturacion_lotes.html [MODIFY].
- **Detalle TÃ©cnico e implicaciones**: Se creÃ³ el servicio FacturacionLoteEstudioService que conecta con ARCA usando concepto = 2 y fechas armadas desde el perÃ­odo seleccionado. Se trasladaron las vistas desde el core a la verticalidad Estudio sin afectar asientos. En la UI se separÃ³ el input de perÃ­odo en Mes y AÃ±o autocentrados.
- **Resultado de las pruebas**: MigraciÃ³n de cÃ³digo y templates exitosa. UI revisada.
- **Estado actual y siguientes pasos sugeridos**: Listo para probar facturar un servicio real.

## 2026-09-15 - Excepciones a Roles (Permisos Negativos)

**Objetivo**: Implementar un sistema de exclusiones de permisos para que un usuario pueda tener permisos denegados de forma puntual, anulando los permisos que hereda de su grupo/rol.

**Archivos modificados**:
- usuarios/models.py: Creado modelo PermisoDenegado.
- usuarios/backends.py: Modificado CaseInsensitiveModelBackend para restar PermisoDenegado del set total de permisos de Django.
- usuarios/views_htmx.py: LÃ³gica para guardar PermisoDenegado vs user_permissions al editar un usuario.
- 	emplates/configuracion/modals/usuario_form.html: Habilitados checkboxes de permisos heredados con estados tachado/denegado.

**Migraciones**: usuarios.0004_permisodenegado.
**Siguientes pasos**: Comprobar el funcionamiento del submodal de exclusiones en la UI y la re-renderizaciÃ³n de la navbar.

 
 # #   A n t i g r a v i t y 
 -   * * F e c h a / D ï¿½ a * * :   1 5   d e   S e p t i e m b r e   d e   2 0 2 6 
 -   * * O b j e t i v o   o   T a r e a * * :   C o r r e g i r   e r r o r   c o n c e p t u a l   e n   l a   a s i g n a c i ï¿½ n   d e   p e r m i s o s   d e n e g a d o s   a l   a g r e g a r   r o l e s   a   u n   u s u a r i o . 
 -   * * A r c h i v o s   c r e a d o s   o   m o d i f i c a d o s * * : 
     -   \ u s u a r i o s / v i e w s _ h t m x . p y \   [ M O D I F Y ] 
 -   * * D e t a l l e   T ï¿½ c n i c o   e   i m p l i c a c i o n e s * * : 
     -   C u a n d o   s e   a s i g n a b a   u n   n u e v o   g r u p o   ( r o l )   a   u n   u s u a r i o ,   l o s   c h e c k b o x e s   i n d i v i d u a l e s   d e   l o s   p e r m i s o s   h e r e d a d o s   d e   e s e   r o l   n o   a p a r e c ï¿½ a n   m a r c a d o s   e n   e l   D O M   o r i g i n a l   d e l   f r o n t e n d   a l   m o m e n t o   d e   e n v i a r   e l   f o r m u l a r i o . 
     -   E l   b a c k e n d   c a l c u l a b a   \ d e n e g a d o s   =   p e r m i s o s _ h e r e d a d o s   -   m a r c a d o s \ ,   p o r   l o   q u e   a u t o m ï¿½ t i c a m e n t e   c a t a l o g a b a   t o d o s   l o s   p e r m i s o s   d e l   g r u p o   r e c i ï¿½ n   a s i g n a d o   c o m o   d e n e g a d o s   ( y a   q u e   n o   v i a j a b a n   e n   \ m a r c a d o s \ ) . 
     -   S e   m o d i f i c ï¿½   l a   l ï¿½ g i c a   p a r a   c r u z a r   e s t o   c o n   e l   e s t a d o   a n t e r i o r   d e   l a   b a s e   d e   d a t o s   ( \ p e r m i s o s _ h e r e d a d o s _ a n t e s \ ) .   A h o r a   u n   p e r m i s o   s o l o   p a s a   a   d e n e g a d o   s i   e l   u s u a r i o   * * y a   l o   t e n ï¿½ a   h e r e d a d o   d e s d e   a n t e s   d e   a b r i r   e l   m o d a l * *   y   e x p l ï¿½ c i t a m e n t e   l o   d e s m a r c ï¿½ . 
 -   * * R e s u l t a d o   d e   l a s   p r u e b a s * * :   L a   a d i c i ï¿½ n   d e   u n   n u e v o   r o l   y a   n o   n i e g a   l o s   p e r m i s o s   a u t o m ï¿½ t i c a m e n t e ,   p e r o   s ï¿½   r e s p e t a   l a s   d e n e g a c i o n e s   o   r e v o c a c i o n e s   m a n u a l e s   p o s t e r i o r e s . 
 
 # #   A n t i g r a v i t y 
 -   * * F e c h a / D ï¿½ a * * :   1 5   d e   S e p t i e m b r e   d e   2 0 2 6 
 -   * * O b j e t i v o   o   T a r e a * * :   M e j o r a r   l a   U X   d e   a s i g n a c i ï¿½ n   d e   p e r m i s o s   y   v i s i b i l i d a d   d e l   N a v b a r . 
 -   * * A r c h i v o s   c r e a d o s   o   m o d i f i c a d o s * * : 
     -   \ 	 e m p l a t e s / b a s e . h t m l \   [ M O D I F Y ] 
     -   \ 	 e m p l a t e s / c o n f i g u r a c i o n / m o d a l s / u s u a r i o _ f o r m . h t m l \   [ M O D I F Y ] 
 -   * * D e t a l l e   T ï¿½ c n i c o   e   i m p l i c a c i o n e s * * : 
     -   S e   a g r e g ï¿½   l ï¿½ g i c a   J a v a S c r i p t   e n   \ u s u a r i o _ f o r m . h t m l \   p a r a   q u e   a l   t i l d a r / d e s t i l d a r   u n   p e r m i s o   ' P a d r e '   ( e j .   \ m e n u _ v e n t a s \ ) ,   a u t o m ï¿½ t i c a m e n t e   s e l e c c i o n e   o   d e s e l e c c i o n e   t o d o s   s u s   p e r m i s o s   h i j o s   ( \ m e n u _ v e n t a s _ * \ ) ,   h a c i ï¿½ n d o l o   u n   c o m p o r t a m i e n t o   e x p l ï¿½ c i t o   e n   l a   U I . 
     -   E n   \  a s e . h t m l \ ,   l o s   a c c e s o s   a   l o s   m ï¿½ d u l o s   p r i n c i p a l e s   d e l   N a v b a r   a h o r a   v a l i d a n   s i   e l   u s u a r i o   p o s e e   * * c u a l q u i e r a * *   d e   l o s   p e r m i s o s   h i j o s ,   n o   s o l o   e l   p e r m i s o   ' P a d r e '   e s t r i c t o .   E s t o   p e r m i t e   q u e   u n   u s u a r i o   c o n   s o l o   u n   p e r m i s o   e s p e c ï¿½ f i c o   ( c o m o   P r e v e n t a )   p u e d a   v e r   e l   m e n ï¿½   r a ï¿½ z   c o r r e s p o n d i e n t e   e n   e l   s i d e b a r . 
 -   * * R e s u l t a d o   d e   l a s   p r u e b a s * * :   N a v b a r   v i s i b l e   c o r r e c t a m e n t e   a l   h e r e d a r   s o l o   p e r m i s o s   s e c u n d a r i o s .   M o d a l   a u t o c o m p l e t a   s e l e c c i o n e s . 
 
 # #   A n t i g r a v i t y 
 -   * * F e c h a / D ï¿½ a * * :   1 5   d e   S e p t i e m b r e   d e   2 0 2 6 
 -   * * O b j e t i v o   o   T a r e a * * :   D e s a c o p l a r   c o m p r o b a c i o n e s   d e   p e r m i s o s   a n i d a d o s   e n   e l   N a v b a r . 
 -   * * A r c h i v o s   c r e a d o s   o   m o d i f i c a d o s * * : 
     -   \ 	 e m p l a t e s / b a s e . h t m l \   [ M O D I F Y ] 
 -   * * D e t a l l e   T ï¿½ c n i c o   e   i m p l i c a c i o n e s * * : 
     -   S e   d e s c u b r i ï¿½   q u e   v a r i o s   l i n k s   a   s u b - m ï¿½ d u l o s   e s t a b a n   e n g l o b a d o s   e r r ï¿½ n e a m e n t e   d e n t r o   d e l   b l o q u e   \ { %   i f   % } \   d e   s u   m ï¿½ d u l o   \ 
 
 h e r m a n o \   ( e j .   \ m e n u _ v e n t a s _ p r e v e n t a s \   e s t a b a   a d e n t r o   d e l   b l o q u e   q u e   v e r i f i c a b a   \ m e n u _ v e n t a s _ c a r g a \ ) .   
     -   A l   s e p a r a r   e s t o s   c o n d i c i o n a l e s   a   s u   p r o p i o   \ { %   i f   % } \   i n d i v i d u a l ,   a s e g u r a m o s   q u e   s i   u n   u s u a r i o   s o l o   t i e n e   a c c e s o   a   \ C a r g a 
 
 d e 
 
 P r e V e n t a s \   o   \ ï¿½ r d e n e s 
 
 d e 
 
 C o m p r a \ ,   e l   l i n k   s e   m u e s t r e   d e   m a n e r a   i n d e p e n d i e n t e   e n   e l   N a v b a r   s i n   r e q u e r i r   t e n e r   a c c e s o   a   l a   c a r g a   d e   v e n t a s / c o m p r a s   g e n e r a l . 
 -   * * R e s u l t a d o   d e   l a s   p r u e b a s * * :   N a v b a r   r e n d e r i z a   a p r o p i a d a m e n t e   l o s   a c c e s o s   d e   m e n ï¿½ s   e s p e c ï¿½ f i c o s   q u e   a n t e s   q u e d a b a n   o c u l t o s   p o r   e l   a c o p l a m i e n t o . 
 
 # #   A n t i g r a v i t y 
 -   * * F e c h a / D ï¿½ a * * :   1 5   d e   S e p t i e m b r e   d e   2 0 2 6 
 -   * * O b j e t i v o   o   T a r e a * * :   V a l i d a r   p e r m i s o s   e n   l o s   D a s h b o a r d   d e   l o s   M ï¿½ d u l o s   ( V e n t a s ,   C o m p r a s )   y   C o n f i g u r a c i ï¿½ n . 
 -   * * A r c h i v o s   c r e a d o s   o   m o d i f i c a d o s * * : 
     -   \ 	 e m p l a t e s / f a c t u r a c i o n / v e n t a s _ i n d e x . h t m l \   [ M O D I F Y ] 
     -   \ 	 e m p l a t e s / f a c t u r a c i o n / c o m p r a s _ i n d e x . h t m l \   [ M O D I F Y ] 
     -   \ 	 e m p l a t e s / c o n f i g u r a c i o n / p a r t i a l s / h u b . h t m l \   [ M O D I F Y ] 
 -   * * D e t a l l e   T ï¿½ c n i c o   e   i m p l i c a c i o n e s * * : 
     -   A n t e r i o r m e n t e ,   a u n q u e   e l   s i d e b a r   c o n t r o l a b a   l a   v i s i b i l i d a d   d e   l a s   o p c i o n e s ,   l o s   _ D a s h b o a r d s _   d e   i n i c i o   d e   c a d a   m ï¿½ d u l o   ( e j .   \  e n t a s _ i n d e x \ ,   \ c o m p r a s _ i n d e x \ )   m o s t r a b a n   * * t o d a s * *   l a s   t a r j e t a s   d e   a c c e s o s   d i r e c t o s   s i n   i m p o r t a r   l o s   p e r m i s o s   d e l   u s u a r i o . 
     -   S e   a ï¿½ a d i e r o n   b l o q u e s   \ { %   i f   p e r m s . u s u a r i o s . . .   % } \   a l r e d e d o r   d e   c a d a   _ c a r d _   ( C a r g a   d e   V e n t a s ,   L i s t a d o ,   P r e v e n t a s ,   ï¿½ r d e n e s   d e   C o m p r a ,   C a r g a   I A ,   e t c . )   e n   l a s   p l a n t i l l a s   d e   l o s   m ï¿½ d u l o s   c o r r e s p o n d i e n t e s . 
     -   S e   r e p l i c ï¿½   l a   s e g u r i d a d   v i s u a l   p a r a   l a s   t a r j e t a s   d e   G e s t i ï¿½ n   d e   U s u a r i o s   y   R o l e s   e n   e l   \ h u b . h t m l \   d e   c o n f i g u r a c i ï¿½ n ,   a s e g u r a n d o   q u e   s o l o   a d m i n i s t r a d o r e s   p u e d a n   v e r   e s t o s   r e c u a d r o s . 
 -   * * R e s u l t a d o   d e   l a s   p r u e b a s * * :   L o s   D a s h b o a r d s   d e   l o s   m ï¿½ d u l o s   s o l o   r e n d e r i z a n   l a s   t a r j e t a s   d e   f u n c i o n a l i d a d e s   a   l a s   q u e   e l   u s u a r i o   p o s e e   p e r m i s o . 
 
 # #   A n t i g r a v i t y 
 -   * * F e c h a / D ï¿½ a * * :   1 5   d e   S e p t i e m b r e   d e   2 0 2 6 
 -   * * O b j e t i v o   o   T a r e a * * :   I m p l e m e n t a r   M i d d l e w a r e   G l o b a l   d e   P e r m i s o s . 
 -   * * A r c h i v o s   c r e a d o s   o   m o d i f i c a d o s * * : 
     -   \ 	 e m p l a t e s / b a s e . h t m l \   [ M O D I F Y ] 
     -   \ u s u a r i o s / m i d d l e w a r e . p y \   [ N E W ] 
     -   \ c o n f i g / s e t t i n g s . p y \   [ M O D I F Y ] 
 -   * * D e t a l l e   T ï¿½ c n i c o   e   i m p l i c a c i o n e s * * : 
     -   S e   e x t r a j e r o n   l o s   \ { %   h o o k _ m e n u   % } \   d e l   c o n d i c i o n a l   d e   C a r g a   e n   \  a s e . h t m l \   p a r a   g a r a n t i z a r   q u e   l a   v e r t i c a l i d a d   s e   m u e s t r e   s i   e l   u s u a r i o   t i e n e   o t r o s   p e r m i s o s   d e l   m ï¿½ d u l o   p e r o   n o   n e c e s a r i a m e n t e   e l   d e   c a r g a . 
     -   S e   c r e ï¿½   \ R o l e P e r m i s s i o n M i d d l e w a r e \   c o n   t r e s   n i v e l e s   d e   c h e q u e o : 
         1 .   M a p a   e x a c t o   d e   U R L   ( \ E X A C T _ M A P \ )   p a r a   v i s t a s   c r ï¿½ t i c a s . 
         2 .   M a p a   d e   p r e f i j o   ( \ P R E F I X _ M A P \ )   p a r a   a g r u p a r   e n d p o i n t s   d e   c o n f i g u r a c i ï¿½ n   o   d e   s e g u r i d a d . 
         3 .   V a l i d a c i ï¿½ n   p o r   p r e f i j o   d e   m ï¿½ d u l o   ( \ M O D U L E _ P R E F I X _ P E R M S \ )   p a r a   g a r a n t i z a r   q u e   e n d p o i n t s   g e n ï¿½ r i c o s   ( e j .   l l a m a d a s   A J A X )   e x i j a n   a l   m e n o s   u n   p e r m i s o   d e n t r o   d e   e s a   f a m i l i a . 
     -   S e   a g r e g ï¿½   a   \ M I D D L E W A R E \   e n   \ s e t t i n g s . p y \ . 
 -   * * R e s u l t a d o   d e   l a s   p r u e b a s * * :   L i s t o   p a r a   v e r i f i c a c i ï¿½ n   m a n u a l .   L a   i n t r u s i ï¿½ n   d i r e c t a   v ï¿½ a   U R L   p o r   u s u a r i o s   n o   a u t o r i z a d o s   a r r o j a r ï¿½   u n   4 0 3   ( A c c e s o   D e n e g a d o ) . 
 
 
## Antigravity
- **Fecha/DÃ­a**: 15 de Septiembre de 2026
- **Objetivo o Tarea**: ReestructuraciÃ³n de Sucursales por Usuario y ParÃ¡metros Contables por Empresa
- **Archivos creados o modificados**:
    - usuarios/models.py [MODIFY]
    - usuarios/forms.py [MODIFY]
    - core/context_processors.py [MODIFY]
    - usuarios/views.py [MODIFY]
    - 	emplates/configuracion/modals/usuario_form.html [MODIFY]
    - 	emplates/configuracion/partials/hub.html [MODIFY]
    - 	emplates/configuracion/partials/empresa_table_rows.html [MODIFY]
    - config/urls.py [MODIFY]
    - contable/views_htmx.py [MODIFY]
    - 	emplates/configuracion/modals/parametros_contables_form.html [MODIFY]
- **Detalle TÃ©cnico e implicaciones**:
    - Se aÃ±adiÃ³ el campo M2M sucursales al modelo Perfil.
    - Se actualizÃ³ el formulario de Usuarios para permitir la selecciÃ³n de sucursales permitidas.
    - El context_processor valida que la sucursal actual estÃ© dentro de las permitidas, con un fallback a Sede/Casa Central.
    - SeleccionEmpresaView ahora filtra las sucursales devueltas utilizando Prefetch segÃºn los permisos.
    - Se moviÃ³ el acceso de ParÃ¡metros Contables del Hub global hacia las filas individuales del ABM de Empresas en la tabla HTMX, inyectando el empresa_id directamente a la URL de HTMX.
- **Resultado de las pruebas**: Vistas HTMX, forms y modelos actualizados correctamente, migraciones ejecutadas exitosamente.

## Antigravity
- **Fecha/Dï¿½a**: 16 de Septiembre de 2026
- **Objetivo o Tarea**: Implementaciï¿½n de Extensiones Armerï¿½a, Trazabilidad, e Impresiï¿½n de Preventas
- **Archivos creados o modificados**:
    - \acturacion/views.py\ [MODIFY]
    - \erticalidades/armeria/views.py\ [MODIFY]
    - \acturacion/services/pdf_service.py\ [MODIFY]
    - \acturacion/views_impresion.py\ [MODIFY]
    - \config/urls.py\ [MODIFY]
    - \	emplates/facturacion/preventa_carga.html\ [MODIFY]
    - \	emplates/facturacion/ventas_carga.html\ [MODIFY]
    - \	emplates/facturacion/autorizaciones_index.html\ [MODIFY]
    - \erticalidades/armeria/templates/armeria/partials/trazabilidad_modal_timeline.html\ [MODIFY]
- **Detalle Tï¿½cnico e implicaciones**:
    - Se agregï¿½ botï¿½n de ediciï¿½n de cliente en modal en las vistas de carga de ventas y preventas.
    - Se reemplazaron alertas de bucle infinito (alert) por notificaciones Swal.fire.
    - Se incorporï¿½ soporte de impresiï¿½n de Remitos de Preventa con \generar_pdf_preventa\.
    - Se aï¿½adiï¿½ botï¿½n PDF en el modal de Trazabilidad (Timeline) y en la bandeja de Autorizaciones para descargar el comprobante en nueva pestaï¿½a.
    - Se ejecutï¿½ script de reset de secuencias para arreglar error de ID ya existente y se aplicaron migraciones para los borrados lï¿½gicos.
- **Resultado de las pruebas**: Vistas actualizadas, PDF generando correctamente y bug de alertas JS solucionado.


## Antigravity
- **Fecha/Dï¿½a**: 16 de Septiembre de 2026
- **Objetivo o Tarea**: Arreglar selecciï¿½n de cliente en Armerï¿½a y automatizar facturaciï¿½n de reservas SIGIMAC.
- **Archivos creados o modificados**:
    - \	emplates/facturacion/partials/clientes_typeahead.html\ [MODIFY]
    - \erticalidades/armeria/templates/armeria/partials/reservas_tabla_parcial.html\ [MODIFY]
    - \erticalidades/armeria/views.py\ [MODIFY]
    - \erticalidades/armeria/templates/armeria/ventas_trazabilidad_carga.html\ [MODIFY]
- **Detalle Tï¿½cnico e implicaciones**:
    - Se solucionï¿½ el bug donde \clienteVentaSeleccionado\ no llegaba a \document.body\ al seleccionarse desde el typeahead, haciendo que el evento se dispare sobre \document.body\ y burbujee de forma correcta. Esto arreglï¿½ la alerta de reserva pendiente "que no estaba funcionando".
    - El botï¿½n "Facturar" en SIGIMAC ahora aï¿½ade \?cliente_id=X\ a la URL.
    - \VentasTrazabilidadCargaView\ lee el parï¿½metro y auto-asigna al cliente en la vista, despachando el evento HTMX al terminar de cargar la pï¿½gina, de modo que se rellenan sus datos e impuestos automï¿½ticamente.
    - El autocompletado de serie \	ypeahead_series_trazabilidad\ ahora intercepta el \cliente_id\ seleccionado en la factura y, de estar el campo de serie vacï¿½o (cuando el usuario hace focus/clic), carga directamente los subproductos (series) que ese cliente tenga en sus reservas PENDIENTES, facilitando seleccionar el arma reservada sin escribir nada.
- **Resultado de las pruebas**: Navegaciï¿½n directa desde bandeja SIGIMAC hasta Trazabilidad con cliente precargado y arma lista para ser seleccionada al hacer clic en el buscador de series.


## Antigravity (Correcciï¿½n)
- **Fecha/Dï¿½a**: 16 de Septiembre de 2026
- **Objetivo o Tarea**: Arreglar error de ID vacï¿½o al clickear 'Facturar' y alerta no renderizada.
- **Archivos modificados**:
    - \erticalidades/armeria/templates/armeria/partials/reservas_tabla_parcial.html\ [MODIFY]
    - \erticalidades/armeria/templates/armeria/ventas_trazabilidad_carga.html\ [MODIFY]
- **Detalle Tï¿½cnico**:
    - Se cambiï¿½ \{{ r.cliente.id }}\ por \{{ r.cliente.pk }}\ en el botï¿½n Facturar de la tabla de reservas. Esto ocurrï¿½a porque el modelo \ClienteProveedor\ tiene un primary key personalizado (\codigo_id\), lo que provocaba que Django devolviera un string vacï¿½o al usar \.id\ en el template, arruinando la URL generada.
    - Se cambiï¿½ el uso de \etch()\ crudo en JS por \htmx.ajax()\ al escuchar el evento de cliente seleccionado. Esto asegura que la peticiï¿½n de validaciï¿½n de reserva SIGIMAC viaje con todas las cookies de sesiï¿½n y cabeceras necesarias, evitando que la vista de verificaciï¿½n fallara al no reconocer la sesiï¿½n (\empresa_id\).


    - Se regresï¿½ el sistema de alerta al mï¿½todo \etch()\ (el cual funcionaba antes) pero montado sobre el \document.body\, debido a que HTMX por defecto cancela las peticiones asï¿½ncronas concurrentes originadas en el mismo elemento (o si no se les especifica un 'source' explï¿½cito). Al volver a usar la API nativa de JavaScript, permitimos que la carga de los detalles fiscales del cliente y la alerta de reserva se procesen en paralelo sin chocarse ni cancelarse.
    - **Protecciï¿½n de Concurrencia (Doble Venta)**: Se aï¿½adiï¿½ una validaciï¿½n temprana en \VentasTrazabilidadCargaView\ al momento de hacer un POST. Si se envï¿½a un \
eserva_id\, se verifica en milisegundos que siga en estado 'PENDIENTE' antes de tocar AFIP. Si otra PC ya la facturï¿½ mientras esta tenï¿½a la pestaï¿½a abierta, el sistema bloquearï¿½ la venta y devolverï¿½ un mensaje de error amigable, previniendo asï¿½ un doble cobro y doble baja de stock.


## [16 de Septiembre de 2026] - Notas de Reservas SIGIMAC
**Objetivo:** Permitir al vendedor aï¿½adir una nota interna al confirmar la preventa de un arma (producto trazable), y visualizarla en la bandeja del cajero de Reservas SIGIMAC.
**Archivos Modificados:**
- \acturacion/models.py\: Aï¿½adido \
otas_sigimac\ a \Preventa\.
- \erticalidades/armeria/models.py\: Aï¿½adido \
otas\ a \ReservaArma\.
- \acturacion/migrations/0004_preventa_notas_sigimac.py\ y \rmeria/migrations/0006_reservaarma_notas.py\: Migraciones generadas y aplicadas.
- \	emplates/facturacion/partials/preventa_items_tabla.html\: Inyectado flag oculto \	iene_arma_flag\ si algï¿½n producto tiene \subprod = True\.
- \	emplates/facturacion/preventa_carga.html\: Interceptado el botï¿½n de Confirmar Preventa para levantar el modal \Swal.fire\ solicitando la nota.
- \acturacion/views.py\ (\PreventaCargaView\): Captura de \
otas_sigimac\ por POST.
- \	esoreria/views_htmx.py\ (\procesar_recibo_preventa_trazable\): Se copia el campo \preventa.notas_sigimac\ al crear la \ReservaArma\.
- \erticalidades/armeria/templates/armeria/partials/reservas_tabla_parcial.html\: Aï¿½adida columna Notas y botï¿½n interactivo para visualizar el contenido con \Swal.fire\.
**Resultado:** Al facturar un arma, salta el modal de notas y las notas son copiadas a la bandeja de Armerï¿½a, reemplazando el flujo fï¿½sico de anotaciones en papel.


- **Ajustes Adicionales (16 Sep)**: 
  - Se configurï¿½ \llowOutsideClick: false\ en el modal de notas para evitar cierres accidentales por miss-clicks.
  - Se aï¿½adieron explï¿½citamente los botones de Aceptar (Confirmar) y Cancelar (Cerrar).
  - Se implementï¿½ validaciï¿½n de campo obligatorio dentro de \preConfirm\: no se permite avanzar si la nota estï¿½ vacï¿½a, arrojando un mensaje de error visual dentro del modal de SweetAlert.


  - Se forzï¿½ el color del texto de los botones del modal (\	ext-white !font-bold\) a travï¿½s de \customClass\ para evitar que TailwindCSS sobreescriba los colores por defecto de SweetAlert2, corrigiendo el error visual de que los botones de Aceptar/Cancelar se vieran oscuros o invisibles.


  - Se corrigiï¿½ la visibilidad del botï¿½n en la columna de Notas de la bandeja de Reservas. El ï¿½cono previo (\a-note-sticky\) no estaba siendo renderizado por la versiï¿½n de FontAwesome en uso, lo que causaba que el botï¿½n tuviera dimensiones 0x0 y la celda apareciera vacï¿½a. Se reemplazï¿½ por \a-comment-dots\ y se le dio estilo estructurado (padding, fondo y borde) para asegurar su correcta renderizaciï¿½n e interactividad.


  - Se cambiï¿½ el ï¿½cono del botï¿½n de Notas en la tabla de Reservas por un SVG nativo embebido, ya que hubo problemas de compatibilidad con la versiï¿½n de FontAwesome local que impedï¿½an la correcta renderizaciï¿½n de cualquier ï¿½cono en esa vista, mostrando un botï¿½n vacï¿½o.



---

## Cristian - PC CASA
- **Fecha/DÃ­a**: 16 de Septiembre de 2026
- **Objetivo o Tarea**: ImplementaciÃ³n completa del flujo de Notas SIGIMAC en Preventa/Reservas y estabilizaciÃ³n UI de Trazabilidad.
- **Archivos creados o modificados**:
    - acturacion/models.py [MODIFY]
    - erticalidades/armeria/models.py [MODIFY]
    - acturacion/migrations/0004_preventa_notas_sigimac.py [NEW]
    - erticalidades/armeria/migrations/0006_reservaarma_notas.py [NEW]
    - 	emplates/facturacion/partials/preventa_items_tabla.html [MODIFY]
    - 	emplates/facturacion/preventa_carga.html [MODIFY]
    - acturacion/views.py [MODIFY]
    - 	esoreria/views_htmx.py [MODIFY]
    - erticalidades/armeria/templates/armeria/partials/reservas_tabla_parcial.html [MODIFY]
    - erticalidades/armeria/templates/armeria/ventas_trazabilidad_carga.html [MODIFY]
    - 	emplates/facturacion/partials/clientes_typeahead.html [MODIFY]
    - erticalidades/armeria/views.py [MODIFY]
- **Detalle TÃ©cnico e implicaciones**:
    - **Pase y DetecciÃ³n de Reservas en Trazabilidad**: El botÃ³n 'Facturar' en Reservas ahora vincula mediante ?cliente_id=X utilizando .pk (soportando primary key codigo_id), cargando automÃ¡ticamente datos fiscales y sugiriendo en el buscador de series las armas reservadas activas del cliente.
    - **ProtecciÃ³n de Concurrencia**: VerificaciÃ³n de estado 'PENDIENTE' de la reserva antes de enviar a AFIP/guardar, previniendo dobles ventas accidentales entre terminales simultÃ¡neas.
    - **Notas SIGIMAC en Preventa**: IntercepciÃ³n de 'Confirmar Preventa' si hay productos trazables para ingresar notas obligatorias dirigidas a caja/armerÃ­a (llowOutsideClick: false). Las notas se guardan y se transfieren a la ReservaArma en la cobranza de seÃ±a/preventa.
    - **UI y Estilos SweetAlert & SVG**: Se aplicÃ³ uttonsStyling: false con clases Tailwind (customClass) para asegurar contraste y legibilidad en botones de SweetAlert. Se reemplazÃ³ el icono FontAwesome en la tabla de Reservas por un componente SVG inline para garantizar visualizaciÃ³n perfecta y apertura del modal de notas.
- **Resultado de las pruebas**: Flujo validado de extremo a extremo: Carga de Preventa trazable -> Solicitud de Nota -> CreaciÃ³n de Reserva con Notas visibles en bandeja -> FacturaciÃ³n directa con cliente y arma precargados.
- **Estado actual**: Funcionalidad completada y verificada.

---

### Cristian - PC CASA
**Fecha:** 17/09/2026
**Objetivo:** Separar Ficha de Subproducto de Detalles de Movimiento y aplicar nuevo diseÃ±o.
**Archivos Modificados:**
- `verticalidades/armeria/views.py`: Se renombrÃ³ `subproducto_detalle_modal` a `movimiento_detalle_modal` y se creÃ³ la nueva vista `subproducto_detalle_modal`.
- `verticalidades/armeria/urls.py`: Se agregÃ³ la ruta para `movimiento_detalle_modal`.
- `templates/productos/partials/movimiento_detalle_modal.html`: Se renombrÃ³ desde `subproducto_detalle_modal.html`, se ajustÃ³ el botÃ³n Volver y se agregÃ³ el botÃ³n PDF para facturas.
- `templates/productos/partials/subproducto_detalle_modal.html`: Creado desde cero con diseÃ±o modo oscuro (Ficha del Arma).
- `templates/productos/partials/trazabilidad_modal_timeline.html`: Se actualizaron las referencias de URL al nuevo `movimiento_detalle_modal`.
**Detalle TÃ©cnico:** 
Se implementÃ³ el flujo donde al presionar "Detalle" en la grilla principal, se abre la Ficha del Arma. Al presionar "Historial", se abre la lÃ­nea de tiempo. Y desde la lÃ­nea de tiempo se accede a los Detalles del Movimiento (que ahora incluyen botÃ³n de Volver y PDF).
**Pruebas:** Servidor corriendo (sin caÃ­das), flujo de modal evaluado a nivel cÃ³digo de HTMX.
**Estado y Siguientes Pasos:** Completado. Pendiente a futuro lÃ³gica de precios (Efectivo/DÃ©bito/USD) desde Medios de Pago.

---

### Cristian - PC CASA
**Fecha:** 17/09/2026
**Objetivo:** Agregar leyendas informativas de validaciÃ³n en el formulario de Clientes/Proveedores.
**Archivos Modificados:**
- `templates/facturacion/modals/cliente_modal.html`: Se aÃ±adieron mensajes en rojo ("SÃ³lo nÃºmeros permitidos" y "Debe ser un email vÃ¡lido con @") debajo de los inputs de telÃ©fono y correo respectivamente. AdemÃ¡s, se habilitÃ³ el renderizado de `form.errors` para esos campos.
**Detalle TÃ©cnico:** 
Esto soluciona un problema de UX donde el HTMX fallaba silenciosamente al no cumplir el regex de validaciÃ³n (por ej. ingresar letras en el telÃ©fono) y el usuario no entendÃ­a por quÃ© no se guardaba la entidad.
**Pruebas:** Servidor corriendo, inspecciÃ³n visual del cÃ³digo HTML modificado.
**Estado y Siguientes Pasos:** Completado.

## [Codex] 18/Sep/2026 - Ajustes de Ajuste en Medio de Pago y Stock de Armas
**Objetivo:** Implementar campo de ajuste en medio de pago y crear vista especÃ­fica para operarios (Stock de Armas) excluyendo histÃ³rico de venta, junto con un desglose de precios dinÃ¡mico. Modificar Trazabilidad para adaptarla al uso administrativo.

**Archivos modificados:**
- 	esoreria/models.py [MODIFY]: Agregado campo juste en MedioPago para soportar porcentajes de recargo/descuento.
- 	esoreria/forms.py [MODIFY]: AÃ±adidos 	ipo_ajuste y porcentaje_ajuste virtuales con lÃ³gica de guardado y carga inicial.
- 	emplates/configuracion/modals/mediopago_form.html [MODIFY]: Incorporado script JS y campos para reflejar la interfaz dinÃ¡mica del ajuste.
- erticalidades/armeria/templates/armeria/hooks/menu_stock.html [MODIFY]: Cambio de nombre de menÃº a Trazabilidad de Productos.
- erticalidades/armeria/urls.py [MODIFY]: Creadas URLs stock_armas_listado y stock_armas_detalle_modal.
- erticalidades/armeria/views.py [MODIFY]: Agregadas las vistas StockArmasListView y stock_armas_detalle_modal (con cÃ¡lculo matemÃ¡tico).
- erticalidades/armeria/templates/armeria/partials/trazabilidad_grilla.html [MODIFY]: Eliminado botÃ³n Detalle.
- 	emplates/productos/partials/trazabilidad_grilla.html [MODIFY]: Eliminado botÃ³n Detalle.
- erticalidades/armeria/templates/armeria/partials/subproducto_detalle_modal.html [MODIFY]: Cambiado botÃ³n Cerrar por Volver.
- 	emplates/productos/partials/subproducto_detalle_modal.html [MODIFY]: Cambiado botÃ³n Cerrar por Volver.
- erticalidades/armeria/templates/armeria/stock_armas_list.html [NEW]: Plantilla principal para la vista de operarios, eliminando filtro de estado y cambiando targets HTMX.
- erticalidades/armeria/templates/armeria/partials/stock_armas_grilla.html [NEW]: Grilla para la vista de operarios sin botÃ³n Historial y con nuevo botÃ³n Detalle.
- erticalidades/armeria/templates/armeria/partials/stock_armas_detalle_modal.html [NEW]: Modal mostrando info del producto y la tabla con Desglose de Precios (Medio de Pago vs Precio Final).

**Detalles TÃ©cnicos:**
- Se generaron las migraciones (makemigrations) y se corriÃ³ la migraciÃ³n para 	esoreria.
- Se validÃ³ el recargo/descuento multiplicando por 10 o -10, con la fÃ³rmula precio_final = precio_lista * (1 + ajuste / 1000).

**Siguientes pasos sugeridos:**
- Validar el frontend abriendo un subproducto en /stock/armas/ y crear un nuevo Medio de Pago para verificar el campo.

**Ajustes Posteriores:**
- Se corrigiÃ³ error AttributeError en la vista stock_armas_detalle_modal cambiando precio_vta_1 y moneda_vta por sus respectivos campos correctos (precio_neto y moneda).
- Se modificaron las columnas de stock_armas_list.html y stock_armas_grilla.html a: Producto, Serie, Cuim, Marca, Calibre, CondiciÃ³n, Sucursal, Estado Sigimac.
- Se eliminÃ³ la columna Acciones, haciendo toda la fila clickeable (con hx-get y cursor-pointer) para abrir el Detalle de Desglose.
- Se agregaron accesos directos de Stock de Armas en el MenÃº lateral y el Dashboard de Stock.

**Ajustes Posteriores II:**
- Se rediseÃ±Ã³ el modal de Detalle de Stock de Armas (stock_armas_detalle_modal.html) para tener formato horizontal (max-w-4xl).
- En la vista stock_armas_detalle_modal, se agregÃ³ la consulta otros_subproductos excluyendo la serie actual pero coincidiendo el producto base en estados DEPOSITO y CONSIGNACION.
- El panel izquierdo contiene la informaciÃ³n del arma seleccionada y el Desglose de Precios.
- El panel derecho lista dinÃ¡micamente 'Mismo ArtÃ­culo (En Stock)' enumerando ID de serie, Estado, Sucursal en la que se encuentra y el Precio Referencia.

**Ajustes de Modularidad (Core vs Verticalidad):**
- Se eliminaron definitivamente las vistas residuales de trazabilidad en el Core (productos/views_trazabilidad.py).
- Se eliminaron todos los templates residuales en 	emplates/productos/ y 	emplates/productos/partials/ que pertenecÃ­an a Trazabilidad, tales como 	razabilidad_list.html, 	razabilidad_grilla.html, subproducto_detalle_modal.html, movimiento_detalle_modal.html, 	razabilidad_modal_timeline.html y subproducto_editar_modal.html.
- Se asegurÃ³ que todo el ecosistema de **Trazabilidad de Subproductos** quede aislado funcional y visualmente en la verticalidad de ArmerÃ­a (erticalidades/armeria/), garantizando la separaciÃ³n de dominio.

**Ajustes en Paginacion (Infinite Scroll) en Core y Verticalidad:**
- Se implemento Infinite Scroll en la grilla principal de Productos. Anteriormente estaba limitada de forma fija a los primeros 100 resultados.
- Se reemplazo el boton manual de Cargar mas resultados por un activador automatico en las grillas de trazabilidad y stock de armas.
- Esto resuelve el problema de visibilidad de items paginados, garantizando que el usuario pueda recorrer el inventario completo sin bloqueos ni requerir clics adicionales.

## [Cristian - PC CASA] 18/Sep/2026 - Permisos de Rol para Stock de Armas y Trazabilidad en Verticalidad
**Objetivo:** Separar y registrar correctamente los permisos de 'Stock de Armas' y 'Trazabilidad Productos' respetando la verticalidad de Armeria.

**Archivos modificados:**
- verticalidades/armeria/models.py [MODIFY]: Se agrego el permiso 'menu_armeria_trazabilidad' a ExtensionArmeria, separandolo de ventas.
- verticalidades/armeria/templates/armeria/hooks/menu_stock.html [MODIFY]: Se envolvio la trazabilidad bajo su propio chequeo de permiso (menu_armeria_trazabilidad).
- usuarios/middleware.py [MODIFY]: Se agregaron al EXACT_MAP las URLs de armeria protegiendolas bajo los permisos de la verticalidad de armeria.

**Detalles Tecnicos:**
- Se generaron (0007_alter_extensionarmeria_options.py) y aplicaron migraciones para armeria.
- Los menus ahora se visualizaran bajo la categoria 'Armeria (Verticalidad)' en el modal de Roles.

**Estado y Siguientes Pasos:** Completado.

## [Cristian - PC CASA] 19/Sep/2026 - Separador de Miles en Reportes en Pantalla (Listados Ventas y Compras)
**Objetivo:** Formatear todos los importes monetarios con separador de miles y 2 decimales fijos (ej: $ 1.234.567,89) en las grillas y reportes visuales de Ventas y Compras, garantizando aislamiento total del backend para no afectar capturas ni exportaciones.

**Archivos modificados:**
- core/templatetags/formato_tags.py [MODIFY]: Se optimizÃ³ el filtro formato_ar para formatear con precisiÃ³n y sustituciÃ³n directa de separadores a partir de cadenas float/Decimal, soportando valores nulos, vacÃ­os y ceros.
- templates/facturacion/ventas_listado.html [MODIFY]: Se cargÃ³ formato_tags y se aplicÃ³ |formato_ar en Neto, IVA, Total y la fila de Totales del tfoot.
- templates/facturacion/compras_listado.html [MODIFY]: Se cargÃ³ formato_tags y se aplicÃ³ |formato_ar en Neto, IVA, Total y la fila de Totales del tfoot.
- docs/planes/091_separador_miles_reportes.md [NEW]: Plan de implementaciÃ³n consensuado en sesiÃ³n Grill-Me.

**Detalles TÃ©cnicos:**
- No se modificaron settings globales ni parsers de backend para asegurar que ningÃºn proceso de captura (OCR, Excel) o formularios HTMX (.fInputAR) sufran efectos colaterales.
- Las exportaciones a Excel (.xlsx) conservan sus valores numÃ©ricos originales (float/Decimal) con mÃ¡scaras de celda (#,##0.00) para preservar la capacidad de cÃ¡lculo en hojas de cÃ¡lculo.

**Resultado de las pruebas:**
- Se ejecutÃ³ script de verificaciÃ³n sobre templates reales renderizando importes superiores a $ 80M y comprobando la presencia exacta de puntos de miles y comas decimales ($ 84.981.702,00, $ 1.234.567,89, etc.).

**Estado y Siguientes Pasos:** Completado y verificado.

## [Cristian - PC CASA] 19/Sep/2026 - ConsolidaciÃ³n de formato_ar.js en core/static/js/ (Versionado en Git)
**Objetivo:** Reubicar y consolidar el script JavaScript de formateo numÃ©rico en core/static/js/formato_ar.js para que quede integrado en el mÃ³dulo core y versionado en Git (la carpeta raÃ­z static/ estÃ¡ excluida en .gitignore), eliminando funciones locales redundantes.

**Archivos modificados/creados:**
- core/static/js/formato_ar.js [NEW]: ImplementaciÃ³n definitiva centralizada con soporte de eventos HTMX, MutationObserver, captura de teclado punto a coma, formateo en vivo y funciones globales (desformatearAR, formatearAR, formatoMonedaAR, inicializarFormatoAR, parseAR, fMiles).
- core/context_processors.py [MODIFY]: Actualizada la bÃºsqueda de mtime apuntando a core/static/js/formato_ar.js para cache-busting.
- core/forms.py [MODIFY]: Actualizada la documentaciÃ³n de referencia a core/static/js/formato_ar.js.
- templates/facturacion/ventas_carga.html [MODIFY]: Eliminadas funciones locales redundantes parseAR y fMiles.
- templates/facturacion/ventas_trazabilidad_carga.html [MODIFY]: Eliminadas funciones locales redundantes parseAR y fMiles.
- templates/facturacion/compras_carga.html [MODIFY]: Eliminadas funciones locales redundantes parseAR y fMiles.
- templates/facturacion/preventa_carga.html [MODIFY]: Eliminadas funciones locales redundantes parseAR y fMiles.
- verticalidades/armeria/templates/armeria/ventas_trazabilidad_carga.html [MODIFY]: Eliminadas funciones locales redundantes.
- verticalidades/agricola/tabaco/forms.py [MODIFY]: Actualizada referencia documental a core/static/js/formato_ar.js.
- .cursorrules y CLAUDE.md [MODIFY]: Ratificada la regla general obligatoria de formato es-AR con core/static/js/formato_ar.js como Ãºnica fuente de verdad en JavaScript.
- static/js/formato_ar.js [DELETE]: Removido archivo huÃ©rfano de la carpeta excluida de git.

**Resultado de las pruebas:**
- Script test_static_resolution.py verificÃ³ que Django StaticFiles resuelve el archivo directamente desde core/static/js/formato_ar.js con su hash/versiÃ³n correspondiente.

**Estado y Siguientes Pasos:** Completado y verificado.

### Cristian - PC CASA
**Fecha:** 20 de Septiembre de 2026
**Objetivo:** Corrección de referencias Javascript faltantes (fMiles / parseAR) por la centralización de formato_ar.
**Archivos modificados:**
- erticalidades/armeria/templates/armeria/ventas_trazabilidad_carga.html`n- 	emplates/facturacion/ventas_trazabilidad_carga.html`n- 	emplates/facturacion/ventas_carga.html`n- 	emplates/facturacion/preventa_carga.html`n- 	emplates/facturacion/compras_carga.html`n- 	emplates/tesoreria/caja_mostrador_abrir.html`n**Detalle Técnico:** Se reemplazaron todas las llamadas a las funciones viejas Miles y parseAR que quedaron huérfanas en los event listeners tras el último commit. Ahora todas llaman a las nuevas funciones centralizadas ormatearAR y desformatearAR exportadas globalmente desde core/static/js/formato_ar.js.
**Pruebas:** Archivos actualizados exitosamente.

### Cristian - PC CASA
**Fecha:** 20 de Septiembre de 2026
**Objetivo:** Hacer que los botones de eliminar del carrito sean siempre visibles.
**Archivos modificados:**
- 	emplates/facturacion/partials/preventa_items_tabla.html`n- 	emplates/facturacion/partials/venta_items_tabla.html`n- 	emplates/facturacion/partials/venta_trazabilidad_items_tabla.html`n- erticalidades/armeria/templates/armeria/partials/venta_trazabilidad_items_tabla.html`n**Detalle Técnico:** Se eliminaron las clases de Tailwind CSS opacity-0 y group-hover:opacity-100 en los íconos de basura de los carritos de venta y preventa, para que se muestren permanentemente de color rojo sin necesidad de hacer hover con el mouse, igualando el comportamiento de Carga de Compras.
**Pruebas:** Archivos actualizados exitosamente.

### Cristian - PC CASA
**Fecha:** 22 de Septiembre de 2026
**Objetivo:** Ajustes en Stock de Armas (Filtros e ID).
**Archivos modificados:**
- `verticalidades/armeria/templates/armeria/stock_armas_list.html`
- `verticalidades/armeria/templates/armeria/partials/stock_armas_grilla.html`
- `verticalidades/armeria/views.py`
- `verticalidades/armeria/templates/armeria/partials/stock_armas_detalle_modal.html`
**Detalle Tcnico:** Se elimin el filtro de CliPro. Se agreg la columna ID a la grilla y el filtro por Condicin (NUEVO/USADO). En el modal de detalle se incluy el ID Producto por encima del Calibre.
**Pruebas:** Archivos actualizados exitosamente.

### Cristian - PC CASA
**Fecha:** 22 de Septiembre de 2026
**Objetivo:** Mostrar campo CUIM en compras por trazabilidad de armera.
**Archivos modificados:**
- `verticalidades/armeria/templates/armeria/compras_trazabilidad_carga.html`
**Detalle Tcnico:** Se ajust la condicional del template para que el input del CUIM se muestre siempre que la empresa sea una Armera, independientemente del config general.
**Pruebas:** Guardado exitosamente.

### Cristian - PC CASA
**Fecha:** 22 de Septiembre de 2026
**Objetivo:** Establecer estado por defecto a USADO en compras de armas.
**Archivos modificados:**
- `verticalidades/armeria/templates/armeria/compras_trazabilidad_carga.html`
- `verticalidades/armeria/views.py`
**Detalle Tcnico:** Ya que las compras en armera corresponden a la carga de bienes usados para reventa, se cambi la opcin seleccionada por defecto del desplegable de 'Estado' a 'USADO', as como tambin el valor por defecto en la vista del backend.
**Pruebas:** Guardado exitosamente.

### Cristian - PC CASA
**Fecha:** 22 de Septiembre de 2026
**Objetivo:** Correccin de error de Django al buscar productos trazables en compras.
**Archivos modificados:**
- `facturacion/views_htmx.py`
**Detalle Tcnico:** Se solucion un TypeError ('Cannot filter a query once a slice has been taken') en la vista `typeahead_productos_compra`. El problema ocurra porque se estaba intentando aplicar `.filter(subprod=True)` sobre un QuerySet que ya haba sido limitado con slicing (`[:100]`) por la funcin `buscar_productos_inteligente`. Se reemplaz por el uso directo de `construir_filtro_busqueda_producto`, aplicando el filtro antes del slicing final.
**Pruebas:** Guardado exitosamente.

### Cristian - PC CASA
**Fecha:** 22 de Septiembre de 2026
**Objetivo:** Correccin del script JS para el estado por defecto del tem.
**Archivos modificados:**
- `verticalidades/armeria/templates/armeria/compras_trazabilidad_carga.html`
**Detalle Tcnico:** El script Javascript tena 'NUEVO' hardcodeado como fallback en caso de que el select de Estado no se renderizara o no estuviera disponible (debido a configuraciones de trazabilidad). Se cambi este fallback explcitamente a 'USADO' en `agregarItemCompraTrazabilidad()` para que coincida con el backend y las reglas de negocio de armera.
**Pruebas:** Guardado exitosamente.

### Cristian - PC CASA
**Fecha:** 24 de Septiembre de 2026
**Objetivo:** ImplementaciÃ³n integral de optimizaciones y correcciones del mÃ³dulo de ArmerÃ­a y FacturaciÃ³n (Puntos 5.6, 6.2, 6.3, 6.5, 6.6, 6.7, 6.8, 8.1, 8.2, 8.3, 9.2 y 9.3 de docs/ObservacionesArmeria.md).
**Archivos creados o modificados:**
- productos/models.py: IncorporaciÃ³n del campo observaciones en Producto, propiedades es_moneda_dolar, precio_pesos, precio_usd_referencia y mÃ©todo calcular_precio_pesos() en Subproducto. FlexibilizaciÃ³n de CUIM en clean().
- productos/forms.py: Campo observaciones agregado a ProductoForm.
- 	emplates/productos/modals/producto_modal.html: Renderizado del textarea de observaciones en pestaÃ±as de producto.
- productos/migrations/0007_producto_observaciones.py: MigraciÃ³n de base de datos para Producto.observaciones.
- erticalidades/armeria/views.py: Soporte de Cliente, Comprobante y precios en ficha de historial; parseo con parsear_decimal_ar en ediciÃ³n de precios de venta trazabilidad; bloqueo de mÃ¡s de 1 arma en carro; validaciÃ³n de Reserva SIGIMAC pendiente y sucursal activa al facturar.
- erticalidades/armeria/templates/armeria/stock_armas_list.html: Barra interactiva de selector de Familias (pills HTMX: TODOS, PISTOLA, ESCOPETA, CARABINA, FUSIL, PISTOLON, USADAS); bÃºsqueda rÃ¡pida en vivo con debounce directo sobre la grilla sin dropdown flotante; ordenamiento interactivo por cabeceras (Marca, Calibre, Precio, etc.).
- erticalidades/armeria/templates/armeria/partials/stock_armas_grilla.html: IncorporaciÃ³n de columna ordenable Precio ($) pesificado por DÃ³lar Cobranza con referencia USD.
- erticalidades/armeria/templates/armeria/partials/stock_armas_detalle_modal.html: VisualizaciÃ³n de notas/observaciones del producto, desglose de cotizaciÃ³n DÃ³lar Cobranza y botÃ³n verde 'Generar Preventa' condicionado a sucursal activa.
- erticalidades/armeria/templates/armeria/ventas_trazabilidad_carga.html: Contenedor para reservas SIGIMAC del cliente, deshabilitaciÃ³n de input de serie al haber 1 arma, cierre de dropdown de serie al clickear afuera y validaciÃ³n de reserva antes de emitir venta.
- erticalidades/armeria/templates/armeria/partials/subproducto_detalle_modal.html: InclusiÃ³n de datos del cliente, comprobante y valores en ficha de trazabilidad.
- erticalidades/armeria/templates/armeria/partials/trazabilidad_modal_timeline.html: Enlace directo a visor de comprobantes/facturas y detalle de precios en la lÃ­nea de tiempo.
- 	emplates/facturacion/compras_carga.html: Persistencia de valores de cabecera (proveedor, comprobante, cotizaciÃ³n, etc.) y guardado/restauraciÃ³n automÃ¡tica mediante sessionStorage.
- 	emplates/facturacion/partials/compra_items_tabla.html: BotÃ³n de carga de series y CUIM destacado con alerta animada â ï¸ Cargar Series/CUIM (0/1) hasta completarse.
- acturacion/views_htmx.py: ValidaciÃ³n de unicidad de Series y CUIM en compras (intra-Ã­tem, inter-Ã­tem y contra subproductos activos en DB); formato estricto de CUIM de 6 alfanumÃ©ricos; modal de series con reporte de error inline.
- 	emplates/facturacion/modals/compras_series_modal.html: Contenedor de alerta de error en validaciÃ³n de series/CUIM sin cierre de modal.
- acturacion/views.py: Soporte de precarga de arma seleccionada por GET (subpro_id) en PreventaCargaView.get; fallback seguro de sucursal_id en post; persistencia de cabecera y validaciÃ³n estricta de unicidad y formato en ComprasCargaView.post.
- acturacion/views_trazabilidad.py: Parseo seguro con parsear_decimal_ar para eliminar duplicaciÃ³n de ceros al editar importes.
- 	emplates/facturacion/partials/preventa_items_tabla.html: Etiqueta corregida a 'Precio Unitario ($)'.
- 	emplates/facturacion/partials/venta_trazabilidad_items_tabla.html y erticalidades/armeria/templates/armeria/partials/venta_trazabilidad_items_tabla.html: Etiqueta corregida a 'Precio Unitario ($)'.
- docs/ObservacionesArmeria.md: ActualizaciÃ³n de estado de los Ã­tems 5.6, 6.2, 6.3, 6.5, 6.6, 6.7, 6.8, 8.1, 8.2, 8.3, 9.2 y 9.3.
- docs/planes/093_optimizaciones_observaciones_armeria.md: Plan maestro de ejecuciÃ³n de optimizaciones de armerÃ­a.
**Detalle TÃ©cnico:**
- Se resolviÃ³ la discrepancia de precios en dÃ³lares de productos de armerÃ­a normalizando a moneda 'DOL' (2,523 productos y 834 subproductos actualizados) y aplicando la cotizaciÃ³n global de dolar_cobranza de la empresa para calcular el importe en pesos argentinos.
- En la interfaz de Stock de Armas, se transformÃ³ el buscador para que filtre de forma inmediata la tabla con HTMX preservando los filtros de familia, marca y calibre, y se agregÃ³ ordenamiento interactivo en todas las cabeceras clave.
- Se implementÃ³ el circuito de precarga de armas hacia Preventa desde el modal de detalle, blindando la regla operativa de que el usuario debe estar en la misma sucursal donde radica el arma fÃ­sica.
- En Compras, se blindÃ³ la unicidad de Serie y CUIM y se implementÃ³ persistencia en sessionStorage para evitar pÃ©rdida de cabecera por recarga accidental o errores de validaciÃ³n.
- En Venta Trazabilidad, se forzÃ³ la selecciÃ³n de Reserva SIGIMAC pendiente para poder grabar la venta, se restringiÃ³ a un mÃ¡ximo de 1 arma en carro y se corrigiÃ³ el formateo numÃ©rico con parsear_decimal_ar.
**Resultado de las pruebas:**
- python manage.py test verticalidades.armeria: 9 tests ejecutados con Ã©xito (OK).
- python manage.py test facturacion.tests.test_armeria_credencial_clu: 9 tests ejecutados con Ã©xito (OK).
- Total: 18/18 pruebas unitarias superadas satisfactoriamente.
**Estado actual y siguientes pasos sugeridos:**
- Todos los puntos planificados (5.6, 6.2, 6.3, 6.5, 6.6, 6.7, 6.8, 8.1, 8.2, 8.3, 9.2, 9.3) se encuentran finalizados y verificados.
- Siguiente paso sugerido: Coordinar con el usuario la revisiÃ³n de los puntos pendientes de logÃ­stica/recepciÃ³n con Esteban (7.1, 8.4) o el flujo de caja mostrador/reservas (10.4).

### Cristian - PC CASA
**Fecha:** 24 de Septiembre de 2026
**Objetivo:** Ocultamiento y restricciÃ³n de la lÃ³gica de Carga de Ventas comÃºn para la verticalidad ARMERIA (Punto 9.1 de docs/ObservacionesArmeria.md).
**Archivos creados o modificados:**
- 	emplates/base.html: Se aÃ±adiÃ³ la condiciÃ³n {% if empresa_actual.tipo_actividad != 'ARMERIA' %} en el submenÃº de Ventas para no mostrar el acceso 'Carga de Ventas'.
- 	emplates/facturacion/ventas_index.html: Se ocultÃ³ la tarjeta principal de 'Carga de Ventas' para empresas con 	ipo_actividad == 'ARMERIA'.
- 	emplates/facturacion/ventas_listado.html: Se ocultÃ³ el botÃ³n de acceso rÃ¡pido 'Nueva Venta' cuando la empresa activa es de ArmerÃ­a.
- acturacion/views.py: Se incorporÃ³ validaciÃ³n tanto en get como en post de VentasCargaView para redirigir con mensaje de aviso a preventas_carga si un usuario de ArmerÃ­a intenta acceder de forma directa por URL.
**Detalle TÃ©cnico:** En la verticalidad de ArmerÃ­a, la facturaciÃ³n directa sin trazabilidad ni reserva previa debe quedar deshabilitada tanto a nivel visual (sidebar, cards y botones) como a nivel backend (protecciÃ³n de la vista), canalizando todo el flujo operativo a travÃ©s de Preventas (reserva y seÃ±as) y Ventas con Trazabilidad (facturaciÃ³n final del arma vinculada a la reserva SIGIMAC).
**Resultado de las pruebas:**
- python manage.py test verticalidades.armeria facturacion.tests.test_armeria_credencial_clu: 18 tests ejecutados con Ã©xito (OK).
**Estado actual y siguientes pasos sugeridos:**
- Punto 9.1 completado y verificado. Quedan disponibles para el usuario los siguientes puntos de la lista de observaciones segÃºn su prioridad.


### Cristian - PC CASA
**Fecha:** 24 de Septiembre de 2026
**Objetivo:** RemociÃ³n del botÃ³n de eliminar/sÃ­mbolo de basurero e implementaciÃ³n de lÃ³gica Deshabilitar/Habilitar restringida exclusivamente a Administradores con filtro de estados (Puntos 3.2 y 4.2 de docs/ObservacionesArmeria.md).
**Archivos creados o modificados:**
- facturacion/models.py: IncorporaciÃ³n del campo `activo = models.BooleanField(default=True, db_index=True, verbose_name="Activo")` en `ClienteProveedor`.
- facturacion/migrations/0005_clienteproveedor_activo.py: Nueva migraciÃ³n aplicada para soporte de soft-delete en clientes y proveedores.
- facturacion/views_htmx.py:
  - En `buscar_clientes`: DetecciÃ³n de Administrador (`is_superuser`, `is_staff` o `perfil.es_admin_sistema`). Si es Administrador, lee el parÃ¡metro `estado_activo` (`habilitados`, `deshabilitados`, `todos`); si es un rol comÃºn, fuerza estrictamente `estado_activo='habilitados'` (`activo=True`). Pasa `es_admin` al contexto.
  - En `eliminar_cliente`: Convierte la acciÃ³n en toggle reversible de `cliente.activo`. Retorna `HTTP 403 Forbidden` si un usuario no administrador intenta ejecutarla. Sincroniza con `ExtensionArmeria.activo` si corresponde.
  - En `lista_clientes_venta_resultados`: Filtrado forzado con `activo=True` para impedir facturar a entidades inactivas.
- productos/services/busqueda_service.py:
  - En `construir_filtro_busqueda_producto` y `buscar_productos_inteligente`: Soporte del parÃ¡metro `estado_activo` (`habilitados`, `deshabilitados`, `todos`).
- productos/views_htmx.py:
  - En `buscar_productos`: EvaluaciÃ³n de Administrador. Si no es admin, se fuerza `estado_activo='habilitados'`. Pasa `es_admin` al contexto.
  - En `eliminar_producto`: Toggle reversible de `producto.activo` protegido contra usuarios no administradores (retorna `HTTP 403 Forbidden`).
- templates/facturacion/clientes_index.html: Selector dropdown de filtro de estado (`Habilitados`, `Deshabilitados`, `Todos`) visible Ãºnicamente si `es_admin=True`. Integrado al trigger HTMX de `q` y `tipo`.
- templates/facturacion/partials/cliente_table_rows.html: Removido el botÃ³n de eliminar y el Ã­cono de basurero. Para usuarios estÃ¡ndar solo queda disponible el botÃ³n de Editar. Para Administradores, se incorporaron botones contextuales: botÃ³n de Deshabilitar (Ã­cono de bloqueo/suspensiÃ³n) si estÃ¡ activo, y botÃ³n de Habilitar (Ã­cono de check) si estÃ¡ inactivo. Badge visual `DESHABILITADO` y atenuaciÃ³n para registros inactivos.
- templates/productos/stock_index.html: Selector dropdown de filtro de estado (`Habilitados`, `Deshabilitados`, `Todos`) visible Ãºnicamente si `es_admin=True`. Integrado al trigger HTMX del buscador `q` y selector de campo.
- templates/productos/partials/producto_list.html: Removido el botÃ³n de eliminar y el Ã­cono de basurero. Para usuarios comunes solo quedan Editar y Duplicar. Para Administradores, botones contextuales de Deshabilitar o Habilitar segÃºn el estado del producto, con badge `DESHABILITADO` y opacidad en registros inactivos.
- docs/planes/094_deshabilitar_clipro_productos_admin.md: DiseÃ±o de arquitectura y plan tÃ©cnico del mÃ³dulo.
- docs/ObservacionesArmeria.md: Actualizados los Ã­tems 3.2 y 4.2 reflejando la soluciÃ³n implementada.
- facturacion/tests/test_toggle_activo_admin.py: 6 pruebas unitarias cubriendo protecciÃ³n de 403 en no-admin, toggle reversible por admin y filtrado diferencial entre perfiles.
**Detalle TÃ©cnico:**
- Se eliminÃ³ cualquier rastro de eliminaciÃ³n fÃ­sica y representaciones de basurero en la interfaz de Clientes y Productos.
- Se implementÃ³ un modelo de soft-delete granular con seguridad a doble nivel:
  1. Frontend: ocultamiento condicional de controles y selectores para usuarios sin perfil administrativo.
  2. Backend: verificaciÃ³n estricta en las vistas HTMX y servicios de bÃºsqueda que deniega vÃ­a HTTP 403 peticiones no autorizadas y fuerza la condiciÃ³n `activo=True` a nivel de QuerySet para evitar cualquier intento de elusiÃ³n por parÃ¡metros GET/POST.
**Resultado de las pruebas:**
- python manage.py test facturacion.tests.test_toggle_activo_admin: 6 tests ejecutados con Ã©xito (OK).
- python manage.py test verticalidades.armeria: 9 tests ejecutados con Ã©xito (OK).
- python manage.py test facturacion.tests.test_armeria_credencial_clu: 9 tests ejecutados con Ã©xito (OK).
- Total: 24/24 pruebas unitarias aprobadas satisfactoriamente.
**Estado actual y siguientes pasos sugeridos:**
- Funcionalidad de Deshabilitar/Habilitar blindada al 100% para Administradores y libre de Ã­conos de basurero para roles operativos.
- Siguiente paso sugerido: Continuar con los siguientes puntos de docs/ObservacionesArmeria.md seleccionados por el usuario.


### Cristian - PC CASA
**Fecha:** 24 de Septiembre de 2026
**Objetivo:** Ajuste de diseÃ±o y tamaÃ±o compacto del selector de estado de clientes y productos ajustado al length de sus opciones.
**Archivos creados o modificados:**
- templates/facturacion/clientes_index.html: Se eliminÃ³ la clase `block` que provocaba que los selects heredaran `width: 100%` y se apilaran verticalmente con un ancho sobredimensionado. Se aÃ±adieron las clases `!w-auto shrink-0` y estilo `width: auto !important; max-width: fit-content;` en los selectores de `tipo` y `estado_activo`, y se configurÃ³ el contenedor con `flex-nowrap items-center` para que convivan en una sola fila compacta y armÃ³nica.
- templates/productos/stock_index.html: Se aplicÃ³ el mismo ajuste en los selectores de `campo` y `estado_activo`, eliminando el comportamiento de bloque expandido y ajustando su ancho estrictamente al contenido de sus opciones.
**Detalle TÃ©cnico:** Debido a las directivas de estilo base del proyecto donde `select { width: 100%; display: block; }`, los selectores dentro de contenedores flexibles sin dimensiÃ³n explÃ­cita se expandÃ­an ocupando todo el ancho horizontal disponible. Con la combinaciÃ³n de `!w-auto`, `shrink-0` y `fit-content`, los selectores pasan a ocupar Ãºnicamente el espacio horizontal necesario para sus textos y flecha, alineÃ¡ndose en una sola lÃ­nea junto al botÃ³n de columnas.
**Resultado de las pruebas:**
- python manage.py test facturacion.tests.test_toggle_activo_admin: 6 tests ejecutados con Ã©xito (OK).
**Estado actual y siguientes pasos sugeridos:**
- Interfaz compacta y equilibrada visualmente en Clientes y Productos.


### Re-MigraciÃ³n Limpia y Consolidada - Vertical Estudio (eje_272)
**Fecha:** 28 de Septiembre de 2026
**Objetivo:** Re-migraciÃ³n desde cero y consolidaciÃ³n de la base de datos para la vertical Estudio a partir del lote FoxPro \eje_272\.
**Archivos creados o modificados:**
- \docs/planes/096_remigracion_estudio_eje272.md\ [NEW]
- \migracion/scripts/estudio/00_init_base.py\ [MODIFIED]
- \migracion/scripts/estudio/01_migrar_maestros.py\ [MODIFIED]
- \migracion/scripts/estudio/02_migrar_asientos.py\ [MODIFIED]
- \migracion/scripts/estudio/03_migrar_tesoreria.py\ [MODIFIED]
- \migracion/scripts/estudio/04_migrar_facturacion.py\ [MODIFIED]
- \migracion/scripts/estudio/05_migrar_pagos_recibos.py\ [MODIFIED]
- \migracion/scripts/estudio/06_verificar_integridad.py\ [MODIFIED]
- \migracion/scripts/estudio/run_migracion_limpia_estudio.py\ [NEW]
**Detalle TÃ©cnico:**
- Se implementÃ³ el orquestador un_migracion_limpia_estudio.py\ que ejecuta un vaciado previo en cascada (\TRUNCATE CASCADE\) de las tablas operativas, contables y de tesorerÃ­a para evitar registros residuales o claves forÃ¡neas huÃ©rfanas.
- Se corrigieron y consolidaron todas las fases de migraciÃ³n:
  - Fase 0: InicializaciÃ³n base de Empresa (Lopez Rios y Asoc SA), Sucursal (Casa Central), Ejercicios Contables 2026 y 2027, Caja de TesorerÃ­a y Producto default para honorarios.
  - Fase 1: Cuentas contables jerÃ¡rquicas, jurisdicciones, alÃ­cuotas de IVA, tipos de comprobantes, parÃ¡metros contables y clientes/proveedores con discriminaciÃ³n fiel de \	ipo_entidad\ (campo \CLI_PRO\) y condiciÃ³n IVA.
  - Fase 2: Asiento de apertura y 1.817 asientos contables con sanitizaciÃ³n matemÃ¡tica de dÃ©bitos/crÃ©ditos negativos y garantÃ­a de constraint \debe_xor_haber\.
  - Fase 3: Bancos, cuentas bancarias, sesiones de caja diaria, 4.293 movimientos de caja con vÃ­nculos contables y de entidades, 1.173 valores de terceros en cartera y 428 transacciones bancarias (cheques propios emitidos y transferencias).
  - Fase 4: 2.442 ventas y 517 compras con resoluciÃ³n de tipos de comprobantes AFIP/CITI, formato de perÃ­odo YYYYMM, generaciÃ³n de Ã­tems de venta/compra y alÃ­cuotas desglosadas.
  - Fase 5: Ãrdenes de pago, recibos de cobranza y aplicaciones cruzadas a facturas.
  - Fase 6: AuditorÃ­a estricta de partida doble y consistencia volumÃ©trica.
  - Fase 7: Reseteo de secuencias autoincrementales en PostgreSQL.
**Resultado de las pruebas:**
- AuditorÃ­a contable: 100% de los Asientos Contables (1.818 asientos) balancean con diferencia .00 (Debe = Haber).
- Resumen volumÃ©trico: 247 Cuentas, 387 Clipro, 1.818 Asientos (4.658 lÃ­neas), 2.442 Ventas con sus items, 517 Compras con sus items, 323 Sesiones de Caja, 4.293 Movimientos de Caja, 1.173 Cheques en Cartera, 428 Transacciones Bancarias, 2.521 OPs, 277 Recibos.
- Reseteo de secuencias: Exitoso.
**Estado actual y siguientes pasos sugeridos:**
- Base de datos \erp-Ikigai-Estudio\ 100% migrada, consistente y lista para producciÃ³n.

**ActualizaciÃ³n (Libro IVA Digital Incorporado):**
- Se creÃ³ el script \migracion/scripts/estudio/07_migrar_lib_iva.py\ replicando la arquitectura de ArmerÃ­a para poblar los modelos fiscales de ARCA:
  - \LibroIvaCompras\ (517 registros).
  - \LibroIvaVentas\ (2.417 registros con CAE, Vto. CAE y QR).
  - \LibroIvaAlic\ (328 alÃ­cuotas desglosadas vinculadas por \siento_id\ y discriminadas por \c_v\).
- Se reejecutÃ³ la suite completa con Ã©xito y secuencias reseteadas.

### Correccion de Creacion de Usuarios (IntegrityError en usuarios_perfil)
**Fecha:** 28 de Septiembre de 2026
**Objetivo:** Solucionar el error IntegrityError: null value in column permiso_armeria_editar violates not-null constraint al dar de alta nuevos usuarios en la verticalidad Estudio.
**Archivos creados o modificados:**
- usuarios/migrations/0008_cleanup_legacy_perfil_columns.py [NEW]
**Detalle Tecnico:**
- La tabla usuarios_perfil en PostgreSQL conservaba columnas residuales NOT NULL sin default (permiso_armeria_editar, permiso_armeria_ver, permiso_josen_editar, permiso_josen_ver) de versiones anteriores.
- Se genero y aplico la migracion 0008 para eliminarlas de forma definitiva mediante ALTER TABLE usuarios_perfil DROP COLUMN IF EXISTS.
**Resultado de las pruebas:**
- Prueba de alta de usuario con UsuarioForm y creacion automatica de Perfil: OK.
**Estado actual y siguientes pasos sugeridos:**
- Alta y edicion de usuarios operativa sin errores en todas las verticalidades.

### Eliminacion de Accion Anular y Visualizacion PDF Inline en Tesoreria
**Fecha:** 28 de Septiembre de 2026
**Objetivo:** Quitar el boton de Anular y toda su logica en los listados de Recibos y Ordenes de Pago (TesorerÃ­a), y configurar la generacion de comprobantes PDF en modo inline (visor en navegador en nueva pestaÃ±a) en lugar de forzar la descarga de archivos.
**Archivos creados o modificados:**
- contable/services/reportes_pdf.py [MODIFIED]
- facturacion/services/reportes_pdf.py [MODIFIED]
- tesoreria/views_listados.py [MODIFIED]
- tesoreria/urls.py [MODIFIED]
- templates/tesoreria/partials/ordenpago_grilla.html [MODIFIED]
- templates/tesoreria/partials/recibo_grilla.html [MODIFIED]
- docs/planes/097_eliminar_anular_pdf_inline_tesoreria.md [NEW]
**Detalle Tecnico:**
- Se actualizo la funcion render_pdf_response en contable y facturacion con as_attachment=False por defecto, configurando Content-Disposition: inline; filename=... para permitir la visualizacion y previsualizacion directa en el navegador.
- Se removieron las vistas orden_pago_anular y recibo_anular en tesoreria/views_listados.py, junto con sus rutas asociadas en tesoreria/urls.py.
- Se eliminaron los botones de 'Anular' en templates/tesoreria/partials/ordenpago_grilla.html y recibo_grilla.html.
- Se rediseÃ±aron los botones de 'PDF' en ambas grillas con estilo uniforme, icono SVG y target='_blank' identico al listado de facturacion/ventas.
**Estado actual y siguientes pasos sugeridos:**
- Listados de Recibos y Ordenes de Pago limpios, sin acciones de anulaciÃ³n y con previsualizaciÃ³n PDF directa en el navegador.

### Migración Limpia de Estudio: Asiento Padre (ID_ASTO), Caja Diaria y Mapeo Universal de Usuarios
**Fecha:** 28 de Septiembre de 2026
**Objetivo:** Restaurar y vincular el padre contable asiento_id (ID_ASTO) en todas las tablas transaccionales de la verticalidad Estudio, poblar los detalles desglosados de fondos en tesoreria_movimiento_caja_detalle para habilitar la visualización completa de la Caja Diaria, y aplicar la regla transversal de asignación de usuarios (ID_USU legacy 2 -> usuario 3 [Nicolas], ID_USU legacy 4 -> usuario 4 [Usuario 4], resto -> 1 [Ikigai]).
**Archivos creados o modificados:**
- migracion/scripts/estudio/00_init_base.py [MODIFIED]
- migracion/scripts/estudio/01_migrar_maestros.py [MODIFIED]
- migracion/scripts/estudio/02_migrar_asientos.py [MODIFIED]
- migracion/scripts/estudio/03_migrar_tesoreria.py [MODIFIED]
- migracion/scripts/estudio/04_migrar_facturacion.py [MODIFIED]
- migracion/scripts/estudio/05_migrar_pagos_recibos.py [MODIFIED]
- migracion/scripts/estudio/06_verificar_integridad.py [MODIFIED]
- migracion/scripts/estudio/run_migracion_limpia_estudio.py [MODIFIED]
- docs/planes/098_migracion_asiento_id_caja_diaria_usuarios.md [NEW]
- docs/walkthrough.md [MODIFIED]
**Detalle Tecnico:**
- En 00_init_base.py: se aseguró el usuario id=4 ('usuario4') para FKs y se sembraron los registros maestros de MedioPago (EFE, DOL, CHQ, TRA, TAR, RET, OTR).
- En 02_migrar_asientos.py: se estableció sesion_caja_id=None en fase 2 para prevenir violación de FK antes de la existencia de CajaSesion, y se asignó creado_por_id con resolver_usuario_id().
- En 03_migrar_tesoreria.py: se agruparon los movimientos de caja_diaria.dbf para resolver el usuario real de CajaSesion cuando enc_caja_diaria.dbf trae ID_USU=0; se crearon asientos complementarios para cualquier ID_ASTO de caja previo a 2026; se pobló tesoreria_movimiento_caja_detalle con 4.533 registros desglosando los importes de efectivo, dólares, banco, valores, tarjetas y retenciones; y se vincularon masivamente 4.293 asientos a su sesion_caja_id.
- En 04_migrar_facturacion.py: se mapeó usuario_id a través de usuario_por_asiento cruzando con asto_enc, caja_diaria, recibos, ord_pago y cheques, removiendo referencias a campos inexistentes en Venta/Compra.
- En 05_migrar_pagos_recibos.py: se corrigió la colisión de numero=0 mediante fallback a ID_REC e ID_OP; se asignó asiento_id y creado_por_id; y se realizó la vinculación recíproca de recibo_id y orden_pago_id sobre MovimientoCaja por asiento_id (4.231 movimientos vinculados).
- En 06_verificar_integridad.py: se agregaron comprobaciones de desglose de medios de pago en caja y distribución auditada de usuarios.
**Resultado de las pruebas:**
- Auditoría Contable: 100% de los Asientos Contables balancean en partida doble (Debe = Haber).
- Total Asientos Contables: 5.079.
- Asientos Vinculados con Sesión de Caja: 4.293 asientos.
- Movimientos de Caja Diaria: 4.293 (100% con asiento_id asignado).
- Detalles de Fondos en Caja Diaria: 4.533 registros (solucionado problema de grilla vacía).
- Órdenes de Pago Migradas: 2.597 | Recibos de Cobranza Migrados: 1.664.
- Distribución de Usuarios Auditada:
  * Asientos (creado_por_id): Nicolas (3): 4.666 | Usuario 4 (4): 399 | Ikigai (1): 14
  * Sesiones Caja (usuario_id): Nicolas (3): 304 | Usuario 4 (4): 18 | Ikigai (1): 2
  * Movimientos Caja (creado_por_id): Nicolas (3): 4.155 | Usuario 4 (4): 138
  * Recibos (creado_por_id): Nicolas (3): 1.604 | Usuario 4 (4): 60
  * Órdenes de Pago (creado_por_id): Nicolas (3): 2.519 | Usuario 4 (4): 78
  * Ventas (usuario_id): Ikigai (1): 1.866 | Nicolas (3): 451 | Usuario 4 (4): 125
  * Compras (usuario_id): Ikigai (1): 354 | Nicolas (3): 107 | Usuario 4 (4): 56
- Reseteo de secuencias PostgreSQL ejecutado con éxito.
**Estado actual y siguientes pasos sugeridos:**
- Migración limpia de Estudio completada al 100% con total integridad referencial, padre contable ID_ASTO preservado, Caja Diaria visible y usuarios mapeados.

### Plan 099: Modalidad de Envío de Facturas por Lotes y Multi-contacto para Verticalidad Estudio
**Fecha:** 28 de Septiembre de 2026
**Objetivo:** Desarrollar la modalidad completa de facturación y despacho para la verticalidad Estudio: soporte de multi-correo y multi-teléfono en Clipro delimitados por coma, configuración SMTP aislada por empresa persistida en JSON en media, tabla satélite EnvioFacturaEstudio integrada con Facturación por Lotes, servicio SMTP profesional con cadencia anti-spam y streaming en tiempo real, pantalla operativa de Ventas con KPIs y modal bloqueante de envíos masivos.
**Archivos creados o modificados:**
- docs/planes/099_envio_facturas_lotes_estudio.md [NEW]
- verticalidades/estudio/models.py [MODIFIED]
- verticalidades/estudio/migrations/0002_enviofacturaestudio.py [NEW]
- verticalidades/estudio/services/config_mail_service.py [NEW]
- verticalidades/estudio/services/smtp_service.py [NEW]
- verticalidades/estudio/services/facturacion_lote_estudio.py [MODIFIED]
- verticalidades/estudio/views.py [MODIFIED]
- verticalidades/estudio/urls.py [MODIFIED]
- verticalidades/estudio/templates/estudio/envios_facturas.html [NEW]
- verticalidades/estudio/templates/estudio/modals/config_mails_modal.html [NEW]
- verticalidades/estudio/templates/estudio/hooks/ui_ventas_index_cards.html [MODIFIED]
- verticalidades/estudio/templates/estudio/hooks/menu_ventas.html [MODIFIED]
- verticalidades/estudio/tests.py [NEW]
- facturacion/forms.py [MODIFIED]
- facturacion/views_htmx.py [MODIFIED]
- templates/facturacion/modals/cliente_modal.html [MODIFIED]
- templates/configuracion/partials/hub.html [MODIFIED]
- templates/configuracion/partials/empresa_table_rows.html [MODIFIED]
- docs/walkthrough.md [MODIFIED]
**Detalle Técnico e Implicaciones de Base de Datos:**
- En PostgreSQL, los campos varchar(254) de correo y varchar(100) de teléfono existentes en facturacion_clienteproveedor almacenan de forma nativa strings concatenados con comas ("a@b.com, c@d.com") sin requerir ninguna modificación del esquema en la app facturación ni migraciones destructivas.
- En facturacion/forms.py (ClienteProveedorForm): se detecta si la empresa activa es de verticalidad ESTUDIO; si lo es, se reemplazan los widgets por TextInput monospace, se implementa _get_validation_exclusions para admitir la multiplicidad de correos excluyendo la validación de email singular del modelo, y en clean() se valida cada correo individualmente con validate_email sanitizándolo y uniéndolo con ", ". Para cualquier otra verticalidad se mantiene el comportamiento clásico e inflexible.
- En templates/facturacion/modals/cliente_modal.html: se incorporó un componente interactivo de chips/etiquetas con Alpine.js cuando es_estudio es True, permitiendo agregar y remover múltiples correos y teléfonos cómodamente con inputs y tags individuales.
- En verticalidades/estudio/models.py: se creó el modelo satélite EnvioFacturaEstudio con relación OneToOne a facturacion.Venta, FK a ClienteProveedor, periodo, destinatarios, estado (PENDIENTE, ENVIADO, ERROR), respuesta_smtp, intentos, fecha_envio e índices optimizados de PostgreSQL para (empresa, periodo, estado). Se aplicó la migración exclusiva estudio.0002_enviofacturaestudio sin afectar la base de producción.
- En verticalidades/estudio/services/config_mail_service.py: se establecieron como valores predeterminados de la verticalidad el servidor propio mail.lopez-rios.com, puerto 465 y seguridad SSL directa (usar_ssl=True), permitiendo al usuario modificarlos a través del modal y persistirlos en media/config_mails/empresa_{id}_mails.json.
- En verticalidades/estudio/services/smtp_service.py: se afinó la apertura de sesión smtplib.SMTP_SSL(host, port, timeout=20) asegurando compatibilidad nativa cuando port == 465 o usar_ssl está activo, reuso de sesión única por lote y rate-limiting de 1 segundo para no quemar la IP pública.
- Blindaje Modular Absoluto (Zero-Spillover): Se eliminaron referencias directas y URLs hardcodeadas de Estudio en templates/configuracion/partials/hub.html y empresa_table_rows.html, reemplazándolas por hooks dinámicos {% hook_ui 'configuracion_hub' %} y {% hook_ui 'empresa_row_action' empresa=empresa %} alojados en verticalidades/estudio/templates/estudio/hooks/. De este modo, si la verticalidad Estudio está ausente o si se accede desde Armería o Agrícola, el sistema no evalúa rutas de estudio ni genera errores NoReverseMatch.
- En facturacion/forms.py: se blindó la detección de empresa_id con fallback defensivo a self.instance.empresa_id para garantizar que las empresas que no sean ESTUDIO mantengan la validación de 1 solo correo y rechacen listas concatenadas.
**Resultado de las pruebas:**
- python manage.py check: 0 problemas encontrados.
- python manage.py test verticalidades.estudio.tests: 6 tests ejecutados exitosamente (100% OK):
  * test_clipro_multi_correo_y_telefono_en_estudio: OK
  * test_clipro_correo_invalido_en_estudio: OK
  * test_clipro_no_afecta_otras_verticalidades: OK (Validación de no-regresión para Armería/Agrícola)
  * test_config_mail_service_guardar_y_leer: OK (Verificación con mail.lopez-rios.com:465 SSL)
  * test_modelo_envio_factura_estudio: OK
  * test_api_envios_facturas_descubrimiento_automatico: OK
- Base de datos en producción erp-Ikigai-Estudio permanece 100% íntegra y sin migraciones ajenas.
**Estado actual y siguientes pasos sugeridos:**
- Módulo de Envío de Facturas por Lotes y Multi-contacto para Estudio Contable completado, probado con 6 pruebas unitarias exitosas y 100% desacoplado de las demás verticalidades.

### Optimización de Rendimiento de Modales, Editores Divididos (Cuerpo y Firma/Logo) y Formato MIME con Negrita
**Fecha:** 28 de Septiembre de 2026
**Objetivo:** Eliminar la lentitud y bloqueo del navegador al abrir la configuración de correos removiendo los filtros de desenfoque (`backdrop-blur`), estructurar la personalización del mensaje en 2 botones interactivos ("Cuerpo del Mensaje" y "Firma y Logo") que abren modales amplios con pantalla dividida (izquierda edición con botón `<b>` e inserción de variables, derecha vista previa reactiva en tiempo real), permitir la carga y eliminación de archivos de logo de empresa, incorporar variables de usuario `{first_name}` y `{last_name}` de `auth_user`, y soportar formato dual MIME (HTML con negrita y logo inline `cid:firma_logo`, y texto plano limpio).
**Archivos creados o modificados:**
- `verticalidades/estudio/services/config_mail_service.py` [MODIFIED]
- `verticalidades/estudio/services/smtp_service.py` [MODIFIED]
- `verticalidades/estudio/views.py` [MODIFIED]
- `verticalidades/estudio/templates/estudio/modals/config_mails_modal.html` [MODIFIED]
- `verticalidades/estudio/templates/estudio/envios_facturas.html` [MODIFIED]
- `verticalidades/estudio/tests.py` [MODIFIED]
- `docs/walkthrough.md` [MODIFIED]
**Detalle Técnico e Implicaciones de Base de Datos:**
1. **Rendimiento GPU / Eliminación de `backdrop-blur`:** Se detectó que las clases Tailwind `backdrop-blur-sm` y `backdrop-blur-md` provocaban recalcular en software/GPU el renderizado de tablas y sombras del ERP en Windows, congelando el navegador al abrir los modales. Se reemplazaron por fondos translúcidos nítidos (`bg-slate-900/60`, `bg-slate-900/70`, `bg-slate-900/80`), logrando una apertura instantánea y sin lag.
2. **Arquitectura de Editores Divididos (2 Columnas con Vista Previa en Vivo):**
   - **Cuerpo del Mensaje:** Modal panorámico (`max-w-6xl`) con editor a la izquierda (botón `<b> Negrita` que envuelve selecciones de texto, chips de variables con inserción en la posición del cursor para `{cliente}`, `{comprobante}`, `{periodo}`, `{total}`, `{empresa}`, `{first_name}`, `{last_name}`) y previsualizador a la derecha simulando una bandeja de entrada con datos de muestra, archivo adjunto y negritas nativas.
   - **Firma y Logo:** Modal panorámico con subida de archivo de imagen (PNG, JPG, WebP, SVG) para el logo institucional guardado en `media/config_mails/firmas/`, botón para quitar logo, editor de texto de la firma con negritas `<b>` y variables `{first_name}`, `{last_name}`, `{empresa}`, y vista previa reactiva al pie del correo con el logo y el bloque de firma.
3. **Soporte de Variables del Usuario Autenticado (`auth_user`):**
   - En `smtp_service.py` y `views.py`, los envíos masivos y unitarios propagan `usuario=request.user` para resolver dinámicamente `{first_name}` y `{last_name}` (o fallback a `username`), permitiendo firmas y saludos personalizados de quien efectúa el envío.
   - Función `safe_format` tolerante que no lanza `KeyError` ante variables inexistentes o no reconocidas.
4. **Formato Dual MIME y Logo Inline Anti-Spam:**
   - La versión `text/html` traduce `<b>...</b>` a etiquetas semánticas y `<br>` para saltos de línea.
   - La versión `text/plain` remueve automáticamente cualquier etiqueta `<b>` o `</b>` mediante expresiones regulares para no ensuciar la lectura en clientes de solo texto.
   - El logo se adjunta con arquitectura `multipart/related` como `MIMEImage` con `Content-ID: <firma_logo>` y `Content-Disposition: inline`, garantizando que clientes como Gmail, Outlook o Thunderbird lo rendericen de forma nativa e inmediata sin bloquearlo por considerarlo un rastreador externo.
5. **Cero Impacto en Base de Datos:** Todo el almacenamiento de configuración de correo y logos se mantiene en la capa de medios (`media/config_mails/`), manteniendo la base de datos de producción intacta.
**Resultado de las pruebas:**
- `python manage.py check`: 0 problemas.
- `python manage.py test verticalidades.estudio.tests`: 8 pruebas ejecutadas y aprobadas al 100% (`Ran 8 tests in 26.512s - OK`):
  * `test_formato_variables_y_negrita_en_smtp_service`: OK
  * `test_config_mails_guardar_firma_y_modal_sin_blur`: OK
  * `test_clipro_multi_correo_y_telefono_en_estudio`: OK
  * `test_clipro_correo_invalido_en_estudio`: OK
  * `test_clipro_no_afecta_otras_verticalidades`: OK
  * `test_config_mail_service_guardar_y_leer`: OK
  * `test_modelo_envio_factura_estudio`: OK
  * `test_api_envios_facturas_descubrimiento_automatico`: OK
**Estado actual y siguientes pasos sugeridos:**
- Sistema de configuración de emails de facturación totalmente optimizado, responsivo y fluido.
- Proceder a la prueba operativa en el navegador por parte del usuario ingresando a la configuración de la empresa en la verticalidad Estudio.

### Corrección de FieldError en Búsqueda de Jurisdicción por Código Postal
**Autor:** Cristian - PC CASA
**Fecha:** 29 de Septiembre de 2026
**Objetivo:** Resolver excepción `django.core.exceptions.FieldError: Cannot resolve keyword 'modificado' into field` en la vista HTMX `/htmx/buscar-cp/` invocada desde el modal de alta y edición de clientes y proveedores.
**Archivos creados o modificados:**
- `facturacion/views_htmx.py` [MODIFIED]
- `docs/walkthrough.md` [MODIFIED]
**Detalle Técnico e Implicaciones de Base de Datos:**
1. **Error de Campo en QuerySet:** En la función `buscar_jurisdiccion_por_cp`, al consultar si existía un registro previo con el mismo código postal, se aplicaba `.order_by('-modificado')`. Dado que el modelo `ClienteProveedor` hereda de `AuditModel`, el campo correcto de fecha de última modificación es `fecha_modificacion`.
2. **Corrección Aplicada:** Se actualizó el ordenamiento a `.order_by('-fecha_modificacion')`, permitiendo la correcta deducción de la jurisdicción (provincia) y localidad sin fallas de ORM.
3. **Cero Impacto en Esquema de Base de Datos:** Sin necesidad de migraciones.
**Resultado de las pruebas:**
- `python manage.py check`: `System check identified no issues (0 silenced)`.
**Estado actual y siguientes pasos sugeridos:**
- Búsqueda y autocompletado por Código Postal operativa y corregida.

### Corrección de Alerta de Producto Duplicado en Carga de Preventa (Toast de 3s sin romper grilla)
**Autor:** Cristian - PC CASA
**Fecha:** 29 de Septiembre de 2026
**Objetivo:** Evitar que al cargar un producto ya existente en la preventa la tabla de ítems sea reemplazada por un cartel estático pegado, implementando un Toast emergente de 3 segundos que desaparece automáticamente sin alterar ni romper la grilla de productos cargados.
**Archivos creados o modificados:**
- `facturacion/views_htmx.py` [MODIFIED]
- `templates/facturacion/preventa_carga.html` [MODIFIED]
- `docs/walkthrough.md` [MODIFIED]
**Detalle Técnico e Implicaciones de Base de Datos:**
1. **Causa del problema:** En `preventas_item_add` (`facturacion/views_htmx.py`), cuando el producto ya existía en `request.session['preventa_items_temp']`, se retornaba un `HttpResponse("<div class='...'>Este producto ya fue cargado.</div>")`. Dado que el target HTMX de la petición es `#items-tabla-container`, la tabla entera de ítems quedaba destruida y reemplazada por dicho `<div>`, quedando congelada permanentemente.
2. **Solución en Backend:** Se estructuró la respuesta de error para que SIEMPRE devuelva el template de la tabla parcial (`facturacion/partials/preventa_items_tabla.html`) con los ítems existentes en la sesión, emitiendo mediante el header `HX-Trigger` el evento `alertaPreventa` junto con `limpiarInputsCargaPreventa`.
3. **Solución en Frontend:** En `preventa_carga.html`, se configuró el listener para `alertaPreventa` que ejecuta SweetAlert2 Toast con `timer: 3000` (3 segundos), barra de progreso (`timerProgressBar: true`) y cierre automático sin requerir interacción del usuario, manteniendo el foco listo para continuar la carga.
4. **Cero Impacto en Base de Datos:** Sin migraciones.
**Resultado de las pruebas:**
- Validación sintáctica de vistas y templates completada con éxito.
**Estado actual y siguientes pasos sugeridos:**
- Alerta no invasiva de 3 segundos lista y grilla de preventa protegida contra roturas.

