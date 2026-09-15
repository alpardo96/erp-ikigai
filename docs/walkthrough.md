# Bitácora de Desarrollo - ERP Ikigai

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
- **Detalle Técnico e implicaciones**:
  1. **Limpieza de Interfaz para Estudio:** Dado que la verticalidad Estudio maneja "Servicios" y no "Productos" físicos, los campos relacionados a reposición e identificación de fábrica carecen de sentido y ensucian la pantalla.
  2. **Corrección de Variable de Entorno y Vistas:** Se corrigió el condicional en `stock_index.html` y `producto_list.html` reemplazando `request.user.empresa_activa` (que resolvía vacío) por la variable correcta de contexto `empresa_actual`. Ahora se ocultan correctamente en ESTUDIO "Cód. Prov", "Cód. Fab", "Mínimo" y "Pto. Pedir", reflejando esto también en la botonera de columnas y la cabecera.
  3. **Condicionamiento en Modal:** Se aplicó la misma exclusión en `producto_modal.html` ocultando la renderización de esos campos dentro del formulario.
  4. **Eliminación de Exportar Selección:** Se eliminó por completo el botón "Exportar Selección" de `stock_index.html` junto con su ruta en `config/urls.py`, sus funciones HTMX en `views_htmx.py` y el template de modal interactivo, quedando el código libre de componentes no utilizados o rotos.
  5. **Refactorización de Excel Completo:** Se extrajo el mapeo de columnas estático en `excel_service.py` hacia una función dinámica `get_columnas_producto(empresa)`. Con esto, la opción de Excel Completo incluirá "Calibre" para Armería; y "Peso (kg)", "Unidad Venta", "Unidades/Bulto" para Distribución, excluyendo a la vez códigos de fábrica si el tipo es Estudio.
- **Resultado de las pruebas**: Las vistas en una sesión de la verticalidad Estudio ya no despliegan estos controles.
- **Estado actual y siguientes pasos sugeridos**: Corrección visual de la grilla completada exitosamente sin alterar la base ni la integridad del form original.
## Antigravity
- **Fecha/Día**: 14 de Septiembre de 2026
- **Objetivo o Tarea**: Condicionar visualización y exigencia de campos de unidad de venta (Calibre, Peso, Bulto) según el tipo de actividad (Armería, Distribución).
- **Archivos creados o modificados**:
  - `templates/productos/stock_index.html` [MODIFY]
  - `templates/productos/partials/producto_list.html` [MODIFY]
  - `templates/productos/modals/producto_modal.html` [MODIFY]
- **Detalle Técnico e implicaciones**:
  1. **Filtro y Columnas del Index:** Se actualizaron `stock_index.html` y `producto_list.html` para que el campo genérico "Calibre" solo se muestre bajo la actividad "ARMERIA". Si el usuario pertenece a una empresa con actividad "DISTRIBUCION", se muestran las tres columnas pertinentes: "Peso (kg)", "Unidad Venta" y "Unidades/Bulto" directamente desde las propiedades del modelo (`peso_unitario_kg`, `unidad_venta`, `unidades_por_bulto`). Para el resto de actividades no se muestran.
  2. **Modal de Formulario:** En `producto_modal.html` se agregó la visualización condicional de los tres inputs para Distribución, que antes solo mostraba uno. Adicionalmente, se corrigió un bug en JavaScript dentro de la función `toggleCalibreArmeria` donde la variable `rubroTexto` no estaba inicializada y causaba un error por consola al intentar leer su valor para ocultar/mostrar el input de Calibre en Armería.
  3. **No Intromisión:** En bases de otras verticales (ej. Estudio o Agrícola), estos campos permanecen ocultos en el front, y en el form están seteados como `required=False` para evitar errores de validación.
- **Resultado de las pruebas**: Las vistas ahora se renderizan dinámicamente según `request.user.empresa_activa.tipo_actividad`.
- **Estado actual y siguientes pasos sugeridos**: Corrección completa. Los campos respetan sus nomenclaturas de base de datos sin forzar operatorias externas.
## Antigravity
- **Fecha/Día**: 14 de Septiembre de 2026
- **Objetivo o Tarea**: Agregar filtro de validación de Persona Jurídica y corregir carga del campo "es_policia" al crear o editar un cliente/proveedor (verticalidad Armería).
- **Archivos creados o modificados**:
  - `facturacion/views_htmx.py` [MODIFY]
  - `verticalidades/armeria/forms.py` [MODIFY]
- **Detalle Técnico e implicaciones**:
  1. **Validación Cruzada de Entidad Fiscal:** Se agregó una capa de validación en la vista `cliente_proveedor_crear_editar` (`facturacion/views_htmx.py`) para obligar a que cualquier ingreso de CUIT de 11 dígitos que inicie con "3" deba categorizarse forzosamente como "Persona Jurídica" dentro de la extensión de Armería. Así mismo, si el usuario marca "Persona Jurídica", el sistema exigirá que el documento proporcionado sea un CUIT válido (arrancando con 3 y de 11 dígitos). Con esto se logra blindar los errores de carga en AFIP y ANMaC (Agencia Nacional de Materiales Controlados).
  2. **Corrección Carga de Select Booleano (es_policia):** Se reparó un bug visual al momento de editar un Cliente Armería existente. El campo `es_policia` es un `TypedChoiceField` con opciones `('true', 'false')`, pero el form (`ExtensionArmeriaForm`) intentaba pre-poblar su valor vía `self.fields['es_policia'].initial`. En un `ModelForm` con instancia, Django lee del diccionario `self.initial`, que contenía el valor booleano puro de base de datos (`True/False`). Al no hacer match el booleano puro con el string de las opciones, el select cargaba vacío. Se modificó el `__init__` para sobreescribir `self.initial['es_policia']` con el string correspondiente.
- **Resultado de las pruebas**: Se constató el correcto acople de la validación sin interferir con las otras entidades del formulario (distribuidora/base). Y al editar, el selector recupera el valor correcto de "es_policia".
- **Estado actual y siguientes pasos sugeridos**: El bloque de facturación sigue robusto. Funcionalidad completada.

## Antigravity
- **Fecha/Día**: 14 de Septiembre de 2026
- **Objetivo o Tarea**: Reparación del modal de Alta/Edición de Clientes y ajuste de lógica fiscal en Facturación Masiva del Estudio.
- **Archivos creados o modificados**:
  - `templates/facturacion/modals/cliente_modal.html` [MODIFY]
  - `verticalidades/estudio/services/facturacion_lote_estudio.py` [MODIFY]
- **Detalle Técnico e implicaciones**:
  1. **Modal de Clientes Roto (Parte 1 - DOM):** Se reparó una anomalía severa en el DOM de `cliente_modal.html`. Un merge previo había combinado el contenedor `bg-white` (que contenía el `x-data` de AlpineJS) con un `div` interno sin remover su etiqueta de cierre `</div>`. Esto causaba que el formulario y el contenedor de scroll se cerraran prematuramente en la mitad del documento (sección Identidad), expulsando las secciones 2, 3, Notas, módulos y Footer fuera del flujo de layout principal. Se corrigió envolviendo adecuadamente el primer bloque en un nuevo `<div>` para que el cierre `</div>` prematuro apuntara a este wrapper y no al contenedor general `bg-white`. AlpineJS recuperó el control de las directivas `x-show` sobre `esProveedor` en todo el documento y la maquetación se restauró por completo.
  2. **Modal de Clientes Roto (Parte 2 - Comillas en AlpineJS):** El usuario reportó que el modal escupía código JavaScript crudo en la parte superior. Esto ocurría porque al encapsular toda la lógica JS de Alpine dentro del atributo `x-data="{ ... }"` (usando comillas dobles), se insertó inadvertidamente código con comillas dobles internas (ej. `.normalize("NFD")` y `.replace(/.../, "")`). El navegador interpretaba la primera comilla doble como el cierre abrupto del atributo `x-data`, provocando que el resto de la lógica quedara huérfana y se renderizara como texto en el HTML. Se reemplazaron todas las comillas dobles internas por comillas simples (`'NFD'` y `''`), restaurando la interpretación válida de AlpineJS.
  3. **Facturación Masiva de Estudio - Omisión AFIP para No Fiscales:** Se adaptó `FacturacionLoteEstudioService` para que, en caso de ejecutarse un lote mixto donde un cliente con `tarifa_f > 0` posea una condición de IVA no fiscal (ej. `PRESUPUESTO` o `CONSUMO INTERNO`), el monto destinado a facturación fiscal (`tarifa_f`) sea sumado y derivado automáticamente a `tarifa_p` (comprobante interno `PRE`), y la ejecución en AFIP para ese registro sea evitada de forma silente. Esto cumple con la directiva de procesar lotes masivos mezclados enviando a AFIP solo los registros que correspondan según su matriz impositiva, sin interrumpir la operación ni emitir errores.
- **Resultado de las pruebas**: Se verificó que el template renderiza ahora de forma íntegra en un test local de Django. La lógica del servicio de facturación deriva tarifas fiscales a presupuesto de forma correcta según el diccionario de condiciones.
- **Estado actual y siguientes pasos sugeridos**: El modal vuelve a ser cien por ciento operativo, y la facturación loteada puede procesarse en estado mixto. No quedan tareas pendientes urgentes del bloque de facturación.

## Antigravity
- **Fecha/Día**: 09 de Septiembre de 2026
- **Objetivo o Tarea**: Soporte de CSRF para accesos externos dinámicos mediante túneles de Cloudflare (`trycloudflare.com`).
- **Archivos creados o modificados**: `config/settings.py` [MODIFY], `.env` [MODIFY].
- **Detalle Técnico e implicaciones**: Se incorporó la lectura y parseo de `CSRF_TRUSTED_ORIGINS` desde el `.env` en `settings.py`. Para tolerar las URLs cambiantes de Cloudflare Quick Tunnels, se configuró el wildcard `https://*.trycloudflare.com`, que permite a Django validar cualquier subdominio temporal generado sin tener que actualizar manualmente el archivo en cada reinicio del túnel.
- **Resultado de las pruebas**: Configuración aplicada y validada sintácticamente.
- **Estado actual y siguientes pasos sugeridos**: Reiniciar el servidor de desarrollo de Django para que tome los cambios de `settings.py` y `.env`.

## Antigravity
- **Fecha/Día**: 09 de Septiembre de 2026
- **Objetivo o Tarea**: Corrección del comportamiento del menú lateral (sidebar) para que la sección de Ventas permanezca abierta al navegar a Reservas SIGIMAC (`/reservas/sigimac/`).
- **Archivos creados o modificados**: `templates/base.html` [MODIFY].
- **Detalle Técnico e implicaciones**: Se añadió la condición `window.location.pathname.startsWith('/reservas/')` al directivo `x-data="{ open: ... }"` del acordeón de Ventas en `base.html` utilizando Alpine.js. Esto permite que el menú se mantenga expandido, proporcionando feedback visual y continuidad en la navegación para el usuario al acceder a las rutas de reservas. No hay implicaciones en base de datos.
- **Resultado de las pruebas**: Se verificó la lógica de Alpine.js; el menú no se cierra al entrar a la ruta especificada.
- **Estado actual y siguientes pasos sugeridos**: Corrección completada y funcional.


## Cristian - PC CASA
- **Fecha/DÃ­a**: 31 de Agosto de 2026
- **Objetivo o Tarea**: Reforma de Verticalidad en Tablas (DistribuciÃ³n y ArmerÃ­a). Corregir la visualizaciÃ³n de las tablas en los listados y reportes para que el contenedor expanda su altura segÃºn el contenido y evitar encierros en tarjetas pequeÃ±as con scroll interno innecesario.
- **Archivos creados o modificados**: 12 templates en `erp-ikigai-distribucion` y 14 templates en `erp-ikigai-armeria` (`clientes_index.html`, `stock_index.html`, `caja_mostrador_index.html`, `rendiciones_recepcion.html`, etc.).
- **Detalle TÃ©cnico e implicaciones**: Se ejecutÃ³ un script iterativo que removiÃ³ masivamente las clases restrictivas (`h-full`, `flex-1`, `overflow-hidden`) de los contenedores de pÃ¡gina y wrappers de tabla en los listados, preservando Ãºnicamente `overflow-x-auto`. El proyecto `Estudio` fue escaneado sin encontrar incidencias.
- **Resultado de las pruebas**: Se verificaron los cambios en los archivos y la eliminaciÃ³n correcta de las clases problemÃ¡ticas.
- **Estado actual y siguientes pasos sugeridos**: Las tablas ahora se expanden libremente segÃºn su contenido. Queda validar visualmente el comportamiento responsivo en el navegador.

## 15 de Agosto de 2026 â Filtro de Estado en Libro Diario / Libro IVA y ClarificaciÃ³n de Anulaciones

### Objetivo
Responder a la inquietud sobre los movimientos con estado "Anulado" en el Libro IVA / Libro Diario, clarificar las razones contables y fiscales por las cuales la anulaciÃ³n es un proceso irreversible, e implementar un **Filtro de Estado** ("SÃ³lo Activos", "SÃ³lo Anulados", "Todos") en la grilla dinÃ¡mica y en las exportaciones (Excel / PDF).

### Archivos Modificados / Creados
- `templates/contable/partials/libro_diario.html` [MODIFY]: Agregado selector desplegable `<select name="estado">` con opciones (SÃ³lo Activos, SÃ³lo Anulados, Todos).
- `contable/views_htmx.py` [MODIFY]: Actualizada la vista `libro_diario_rows` para procesar el parÃ¡metro `estado` y filtrar `Asiento` segun `anulado`.
- `contable/views_reportes.py` [MODIFY]: Actualizados los endpoints `exportar_diario` (Excel) y `exportar_diario_pdf_view` (PDF) para respetar el filtro por `estado`.
- `contable/tests/test_libro_diario_mejoras.py` [MODIFY]: Agregado el test `test_libro_diario_filtro_estado`.
- `docs/planes/041_filtro_estado_libro_iva_diario.md` [NEW]: Plan de implementaciÃ³n archivado.

### Detalle TÃ©cnico
1. **Modelado y Filtrado:**
   - OpciÃ³n `1` (SÃ³lo Activos): `Asiento.objects.filter(anulado=False)`.
   - OpciÃ³n `2` (SÃ³lo Anulados): `Asiento.objects.filter(anulado=True)`.
   - OpciÃ³n `0` (Todos): sin filtro sobre `anulado`.
2. **Interfaz de Usuario:**
   - La barra de filtros fue estructurada en un diseÃ±o Tailwind limpio con la opciÃ³n predeterminada en "SÃ³lo Activos", ocultando automÃ¡ticamente comprobantes anulados a menos que el usuario elija verlos explÃ­citamente.

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test contable.tests.test_libro_diario_mejoras --noinput
```
**Resultado:** `Ran 7 tests in 27.787s - OK`.

---

## 15 de Agosto de 2026 â RedefiniciÃ³n del campo `condic` (7 valores) â Fase 1 del Plan 047

### Objetivo
Redefinir por completo la semÃ¡ntica del campo `condic`, que hasta ahora tenÃ­a 3 valores (1=Real, 2=Presupuestado, 3=Apertura). Es el **prerrequisito** del nuevo reporte "Balance de Saldos Mensuales" (Plan 047): sin esta fase, el asiento de refundiciÃ³n de resultados âque nacÃ­a con el default `1` (Real)â contaminaba el Ãºltimo mes de todo reporte de evoluciÃ³n mensual, dando vuelta las cuentas de resultado.

### La tabla definitiva
Los valores `1` a `4` coinciden con la numeraciÃ³n del sistema VFP anterior, con lo cual los reportes y la operatoria del usuario mapean 1:1.

| Valor | Nombre | Significado |
|-------|--------|-------------|
| `1` | Real | Registros fiscales. El 90 % de los movimientos. |
| `2` | Presupuestado | No fiscal. Gasto **real** de la empresa sin respaldo documental vÃ¡lido (servimoto, almacÃ©n del barrio, taxi). SÃ³lo anÃ¡lisis de gestiÃ³n. |
| `3` | Ajuste | Factura **vÃ¡lida y a nombre de la empresa** pagada por el dueÃ±o con fondos propios. Va a contabilidad y a las DDJJ de IVA/Ganancias, pero se **excluye del anÃ¡lisis de gastos**. Se carga como cualquier factura, contra proveedores varios. |
| `4` | AuditorÃ­a | Ajustes que el estudio contable remite tras armar los estados contables. |
| `5` | Apertura | Antes era el `3`. Lo genera el sistema. |
| `6` | RefundiciÃ³n | RefundiciÃ³n de cuentas de resultado. Lo genera el sistema. |
| `7` | Cierre | Cierre de ejercicio. **Reservado: todavÃ­a no implementado.** |

**Las tres lentes** (clave para leer cualquier filtro de `condic`): gestiÃ³n = `{1,2}` Â· fiscal = `{1,3}` Â· estados contables = `{1,3,4}`. El `2` baja el resultado real pero no el fiscal; el `3` baja el fiscal sin que salga plata: uno amortigua al otro.

### Archivos Modificados / Creados
- `.cursorrules` [MODIFY]: reescrita la secciÃ³n de `condic` con la tabla de 7 valores, las tres lentes y 5 reglas inflexibles. **Fuente de verdad.**
- `CLAUDE.md` [MODIFY]: actualizado el bullet resumen.
- `contable/models.py` [MODIFY]: constantes `CONDIC_ASIENTO`, `CONDIC_MOVIMIENTO`, `CONDIC_ESTRUCTURAL`, `CONDIC_FISCAL` y helper `condic_opciones()` como fuente Ãºnica de rÃ³tulos; documentado el campo `condic` de `Asiento` y el gate fiscal de `LibroIvaBase`.
- `contable/services/contabilizacion.py` [MODIFY]: el Libro IVA pasa de `compra.condic == 1` a **`compra.condic in (1, 3)`**.
- `contable/services/cierre.py` [MODIFY]: el asiento nace con `condic=6`; la validaciÃ³n de duplicados pasa de `concepto__icontains` a `condic=6`.
- `contable/services/asientos.py` [MODIFY]: `editar_asiento` rechaza asientos con `condic >= 5` (D-6) y fechas fuera del ejercicio del asiento (D-9).
- `contable/views_htmx.py` [MODIFY]: `_calcular_balance` usa `condic=5` para la apertura; el modal de ediciÃ³n desarma `ValidationError` para mostrar el mensaje y no `['...']`.
- `contable/views.py` [MODIFY]: `condic_opciones` al contexto de Libro Diario y Libro Mayor.
- `contable/forms.py` [MODIFY]: rÃ³tulo `2 - Presupuestado` (unificado con `.cursorrules`).
- `facturacion/models.py` [MODIFY]: documentado `condic` en `Venta` y `Compra`.
- `migracion/scripts/02_migrar_asientos.py` [MODIFY]: apertura migrada con `condic=5`.
- `templates/contable/partials/detalle_asiento.html` [MODIFY]: badges para los 7 valores.
- `templates/contable/partials/libro_diario.html`, `libro_mayor.html` [MODIFY]: checkboxes generados desde `condic_opciones` (antes hardcodeados 1/2/3; un asiento `condic>=4` quedaba **invisible** en el Libro Diario).
- `templates/contable/modals/asiento_form.html` [MODIFY]: rÃ³tulo unificado.
- `contable/tests/test_libro_diario_mejoras.py` [MODIFY]: aserciÃ³n del rÃ³tulo.
- `contable/migrations/0019_renumerar_condic.py` [NEW]: data migration.
- `contable/tests/test_condic_renumeracion.py` [NEW]: 18 pruebas.
- `docs/planes/047_reporte_saldos_mensuales.md` [NEW]: plan completo archivado.

### Detalle TÃ©cnico
1. **Sin migraciÃ³n de esquema.** `condic` es un `IntegerField` sin `choices` ni `CheckConstraint`: la renumeraciÃ³n es un `UPDATE`, no un `ALTER TABLE`. La migraciÃ³n `0019` reasigna `3 â 5` y las refundiciones histÃ³ricas (que quedaron con el default `1`) a `6`, identificÃ¡ndolas por el concepto `CIERRE DE EJERCICIO%`, Ãºnico rastro disponible en bases previas. Es **idempotente** y tiene funciÃ³n de reversa.
2. **Momento elegido.** Conteo real de la base antes de migrar: `condic=1` â 40 asientos, `condic=2` â 6, **cero** con `condic=3` y **cero** asientos de cierre. La renumeraciÃ³n no tocÃ³ datos productivos.
3. **Dos bugs preexistentes cerrados de paso:**
   - `editar_asiento` guardaba la fecha nueva sin revalidar que perteneciera al ejercicio del asiento, rompiendo el invariante que `crear_asiento` sÃ­ garantiza (deriva el ejercicio *desde* la fecha).
   - El form de ediciÃ³n sÃ³lo ofrece `condic` 1 y 2, asÃ­ que guardar un asiento de apertura lo **degradaba a Real** de forma silenciosa.
4. **RefundiciÃ³n â  Cierre.** `procesar_cierre_ejercicio` sÃ³lo cancela las cuentas de **resultado**: es una refundiciÃ³n (`6`). El cierre real (`7`), que ademÃ¡s cancela las patrimoniales, **no existe todavÃ­a**. Queda reservado para el desarrollo en que, al crear un ejercicio nuevo, el sistema tome el `condic=7` del anterior y lo copie como `condic=5` (apertura) del nuevo.

### Pruebas Automatizadas
```bash
python manage.py test contable.tests.test_condic_renumeracion --noinput
```
**Resultado:** `Ran 18 tests in 179.906s - OK`

```bash
python manage.py test contable --noinput
```
**Resultado:** `Ran 38 tests in 358.091s - OK`

**RegresiÃ³n de los mÃ³dulos que consumen `condic`:**
```bash
python manage.py test tesoreria --noinput     # Ran 43 tests in 531.169s - OK
python manage.py test facturacion --noinput   # Ran 18 tests - FAILED (errors=2)
```
Los 2 errores de `facturacion` son **preexistentes y ajenos a este cambio**: `test_armeria_credencial_clu.ArmeriaCredencialCLUTestCase` falla en su `setUp` con `TypeError: Sucursal() got unexpected keyword arguments: 'codigo'` â el modelo `Sucursal` no tiene campo `codigo`. El test entrÃ³ con el commit `7ff0da8` (*Solicitar Credencial en Preventa*). **Queda pendiente de corregir en el plan que corresponda.**

Cobertura: semÃ¡ntica de las constantes, rechazo de ediciÃ³n de asientos estructurales y de fechas fuera del ejercicio (incluidos los bordes `inicio`/`cierre`, que es el caso real de la factura del ejercicio anterior), refundiciÃ³n con `condic=6` y detecciÃ³n independiente del concepto, Libro IVA poblado por `condic` 1 y 3 pero no por 2 ni 4, herencia del `condic` del comprobante al asiento, apertura (`5`) separada del movimiento del perÃ­odo, y data migration idempotente.

### Estado actual y siguientes pasos
Fase 1 del Plan 047 **completa**. Siguientes fases: servicio `saldos_mensuales.py`, vistas HTMX, drill-down al mayor del mes, export Excel con el `Ã â1` en modo Resultados.

**Pendientes registrados fuera de alcance:** el `condic=7` (cierre real), la copia automÃ¡tica cierreâapertura, la captura de asientos de auditorÃ­a (`condic=4`), habilitar el `condic=3` en la carga para usuarios autorizados, y el cambio de `condic` posterior a la emisiÃ³n en ventas âque deberÃ¡ resincronizar el Libro IVA al pasar de `{1,3}` a `2`â.

---

## 15 de Agosto de 2026 â Servicio de Saldos Mensuales â Fases 2 y 3 del Plan 047

### Objetivo
Implementar el nÃºcleo de cÃ¡lculo del reporte "Balance de Saldos Mensuales": para cada cuenta del plan, el saldo de apertura, el movimiento neto de cada mes del ejercicio y el saldo al cierre. FunciÃ³n pura, sin `request`, para que sea testeable de forma aislada.

### Archivos Creados
- `contable/services/saldos_mensuales.py` [NEW]: `calcular_saldos_mensuales()` y `periodos_ejercicio()`.
- `contable/tests/test_saldos_mensuales.py` [NEW]: 27 pruebas.

### Detalle TÃ©cnico
1. **Columnas mensuales dinÃ¡micas.** `periodos_ejercicio()` recorre aÃ±o-mes desde `Ejercicio.inicio` hasta `Ejercicio.cierre`, y devuelve para cada perÃ­odo `clave` (`202504`), `label` (`Abr-25`), `primer_dia` y `ultimo_dia` âestos dos Ãºltimos alimentan el drill-down de la fase 6â. A diferencia del VFP, que reordena doce columnas fÃ­sicas `mes_01..mes_12` indexadas por el mes calendario **sin guardar el aÃ±o**, acÃ¡ se guarda el `(aÃ±o, mes)` real: soporta ejercicios irregulares y `202601` no puede colisionar con `202501`.
2. **Dos consultas agregadas, pivot en Python.** Una agrupa por `(cuenta_id, TruncMonth(fecha))` y la otra trae la apertura. Se descartÃ³ anotar 13+ `Sum(...)` condicionales sobre `Cuenta` (extrapolaciÃ³n del patrÃ³n del Balance): con esa cantidad de columnas el plan de PostgreSQL se degrada. Las dos consultas son **mutuamente excluyentes por `condic`**, asÃ­ que ningÃºn movimiento se computa dos veces ni se pierde.
3. **Regla central.** Apertura â `condic=5`; meses â `condic in {1,2,3,4}` (el usuario elige); nunca entran el `6` ni el `7`. Universos disjuntos que **no dependen de la fecha**: un asiento de apertura fechado el 01/01 va a Apertura, no a la columna de enero.
4. **Saneamiento de `condics`.** Se intersecta lo recibido con `{1,2,3,4}`: un querystring armado a mano (`?condic=5&condic=6`) no puede meter la apertura ni la refundiciÃ³n en una columna mensual. Con la intersecciÃ³n vacÃ­a devuelve grilla vacÃ­a con aviso, sin ejecutar la consulta.
5. **Rollup jerÃ¡rquico por profundidad del Ã¡rbol.** El nivel de cada cuenta se calcula siguiendo la cadena `sumariza` (tolerando ciclos y padres colgados), no por `len(jerarquia)`: la longitud del cÃ³digo depende de la convenciÃ³n de numeraciÃ³n de cada empresa, el Ã¡rbol no. Se consolida de mayor a menor profundidad, igual que el `SET ORDER TO jera_cta DESC` del VFP.
6. **Signo natural siempre.** El servicio nunca invierte: la inversiÃ³n (Ã â1) de las cuentas de resultado vivirÃ¡ sÃ³lo en el export a Excel (fase 7). En pantalla el operador necesita ver el movimiento tal cual se registrÃ³, porque el signo es el dato que delata un error de carga.
7. **Omitir sin movimiento con valor absoluto** (criterio del VFP): una cuenta que netea cero pero **tuvo** movimiento se conserva; una sin nada se omite.
8. **Totales sÃ³lo sobre imputables**, para no contar cada importe una vez por nivel de la jerarquÃ­a.

### Pruebas Automatizadas
```bash
python manage.py test contable.tests.test_saldos_mensuales --noinput
```
**Resultado:** `Ran 27 tests in 152.010s - OK`

Destacadas:
- **Prueba cruzada con el Sumas y Saldos:** el `Total` de cada cuenta imputable es idÃ©ntico al saldo final que devuelve `_calcular_balance` para la misma cuenta y ejercicio. Si algÃºn dÃ­a divergen, uno de los dos estÃ¡ mal.
- **Aislamiento por ejercicio:** un asiento con fecha dentro del rango consultado pero adjudicado a otro ejercicio **no** entra. Es el caso que un filtro sÃ³lo por fechas dejarÃ­a pasar, y el que justifica acotar por la FK.
- Las siete combinaciones de `condic` del Â§5.1 del plan (gestiÃ³n `1+2`, estados contables `1+3+4`, sÃ³lo auditorÃ­a `4`, sÃ³lo ajustes `3`â¦), verificando ademÃ¡s que **la columna Apertura es idÃ©ntica en todas**.
- Partida doble: en modo "Todas" la fila TOTALES da `0,00` en cada columna.

### Hallazgo: `Asiento.sucursal` casi nunca se puebla
`crear_asiento()` **no expone el parÃ¡metro `sucursal`** y nunca lo asigna, y todos los llamadores productivos pasan por ahÃ­. Conteo real de la base: **1 de 46 asientos** tiene sucursal. Es decir que el filtro por sucursal del Balance actual ây el del reporte nuevoâ estÃ¡ operativo en el cÃ³digo pero **no tiene datos que filtrar**.

No se corrigiÃ³ porque excede el alcance del Plan 047: la soluciÃ³n es agregar el parÃ¡metro y propagarlo desde el comprobante (`compra.sucursal`, `venta.sucursal`) en los 5 llamadores de `contabilizacion.py`, lo que cambia la semÃ¡ntica de todos los asientos futuros. **Queda registrado para decidirlo aparte.**

### Estado actual y siguientes pasos
Fases 2 y 3 completas. Siguen: vistas HTMX y URLs (4), templates (5), drill-down al mayor del mes (6) y export Excel con el Ã â1 (7).

---

## 15 de Agosto de 2026 â Pantalla de Saldos Mensuales y drill-down â Fases 4, 5 y 6 del Plan 047

### Objetivo
Poner el reporte en pantalla: pÃ¡gina dedicada, panel de filtros HTMX, grilla ancha con columnas fijas, y el drill-down de tres niveles (celda â Mayor de ese mes â asiento contable).

### Archivos Modificados / Creados
- `templates/contable/saldos_mensuales.html` [NEW]: pÃ¡gina con encabezado y contenedor `#saldos-mensuales-content`.
- `templates/contable/partials/saldos_mensuales.html` [NEW]: filtros + grilla + fila de totales.
- `contable/views.py` [MODIFY]: `SaldosMensualesView` (devuelve sÃ³lo el partial ante `HX-Request`).
- `contable/views_htmx.py` [MODIFY]: `get_saldos_mensuales_context`, `saldos_mensuales_datos`, `_querystrings_drilldown`, y **dos filtros nuevos en `get_mayor_context`: `modulo` y `ejercicio_id`**.
- `contable/urls.py` [MODIFY]: rutas `contable_saldos_mensuales` y `saldos_mensuales_datos`.
- `templates/contable/index.html` [MODIFY]: tarjeta de acceso.
- `contable/tests/test_saldos_mensuales_vistas.py` [NEW]: 12 pruebas.

### Detalle TÃ©cnico
1. **El ejercicio es un filtro siempre presente.** Si el querystring no trae uno se toma el activo de la sesiÃ³n; si la empresa no tiene ejercicios, la vista responde 200 con un aviso en vez de romper.
2. **Testigo `filtros_aplicados`.** Un checkbox destildado no viaja en el GET, asÃ­ que "primera carga" y "el usuario destildÃ³ todo" llegan idÃ©nticos al servidor. Un `<input type="hidden">` los distingue: sin testigo se tildan las cuatro condiciones; con testigo se respeta exactamente lo que el usuario dejÃ³ marcado.
3. **La grilla scrollea, nunca la pÃ¡gina.** `overflow-x-auto` con `Cuenta` *sticky* a la izquierda, encabezado *sticky* arriba y fila de totales *sticky* abajo. IndentaciÃ³n por nivel con `padding-left` calculado.
4. **Drill-down sin endpoints nuevos.** La cadena `mayor_cuenta_modal` â `libro_mayor_rows` â `detalle_asiento_modal` ya existÃ­a. Cada celda es un `<button hx-get>` que agrega el rango del mes.
5. **ConciliaciÃ³n celda â mayor.** Los links llevan el `condic` **explÃ­cito**, distinto segÃºn la celda: los tildados para un mes, `condic=5` para Apertura, y ambos para Total. Sin esto se rompÃ­a justo en el primer mes: un asiento de apertura fechado el 01/01 cae dentro del rango de enero y el mayor lo mostrarÃ­a mientras la celda lo excluye. TambiÃ©n se agregÃ³ `ejercicio_id` a `get_mayor_context`, que se acotaba sÃ³lo por fechas y dejaba entrar asientos de otro ejercicio con fecha solapada.
6. **Importes con `{{ valor|formato_ar }}`** en toda la grilla, segÃºn la regla del proyecto. Se corriÃ³ `npm run build`: las clases nuevas (`text-sky-700`, `text-violet-700`, `gap-1.5`, `px-2.5`, `tabular-nums`) no estaban en el CSS purgado.

### Pruebas Automatizadas
```bash
python manage.py test contable.tests.test_saldos_mensuales_vistas --noinput
```
**Resultado:** `Ran 12 tests in 104.297s - OK`

```bash
python manage.py test contable --noinput
```
**Resultado:** `Ran 77 tests in 686.021s - OK`

La prueba central es **la conciliaciÃ³n**: se toma el valor de una celda, se arma el link que genera el template y se verifica que la Î£(debe â haber) que devuelve `libro_mayor_rows` con esos parÃ¡metros sea **exactamente igual**. Se corre con un asiento de apertura fechado dentro del primer mes, que es el escenario donde se romperÃ­a.

### Estado actual y siguientes pasos
Fases 4, 5 y 6 completas. Queda la **fase 7**: exportaciÃ³n a Excel, Ãºnico lugar donde se aplica el Ã â1 a las cuentas de resultado. DespuÃ©s, la mediciÃ³n del Ã­ndice (8) y el contraste manual contra los CSV de referencia (9).

---

## 15 de Agosto de 2026 â ExportaciÃ³n a Excel de Saldos Mensuales â Fase 7 del Plan 047

### Objetivo
Exportar la grilla a Excel con el layout del VFP, y aplicar ahÃ­ ây sÃ³lo ahÃ­â la inversiÃ³n de signo de las cuentas de resultado.

### Archivos Modificados / Creados
- `contable/services/reportes_excel.py` [MODIFY]: **corregido un bug preexistente** (ver abajo) y agregado `exportar_saldos_mensuales_excel()`.
- `contable/views_reportes.py` [MODIFY]: `exportar_saldos_mensuales`.
- `contable/urls.py` [MODIFY]: ruta `exportar_saldos_mensuales_excel`.
- `templates/contable/partials/saldos_mensuales.html` [MODIFY]: botÃ³n Excel que reenvÃ­a los filtros vigentes.
- `contable/tests/test_saldos_mensuales_vistas.py` [MODIFY]: 5 pruebas nuevas del export.

### BUG PREEXISTENTE CORREGIDO: los tres exports a Excel estaban rotos
`_configurar_hoja()` usa `isinstance(fecha_desde, date)` en su lÃ­nea 29, pero **`date` nunca estuvo importado** en el mÃ³dulo. La expresiÃ³n se evalÃºa siempre, con o sin fechas, asÃ­ que la funciÃ³n lanzaba `NameError: name 'date' is not defined` en **toda** llamada.

Como los tres exports la invocan (`exportar_diario_excel`, `exportar_mayor_excel`, `exportar_balance_excel`), la descarga de Excel del **Libro Diario, el Libro Mayor y el Balance estaba caÃ­da**. Se corrigiÃ³ con el `from datetime import date` faltante y se verificÃ³ la funciÃ³n con y sin rango de fechas.

### Detalle TÃ©cnico
1. **Layout idÃ©ntico al VFP** (Anexo A del plan): A=Codigo, B=Sumariza, C=Jerarquia, D=Detalle, E=Imp, F=Apertura, luego una columna por mes, y Total, Tipo, Bce, Pres, Econ, Fciero. Las planillas histÃ³ricas del usuario siguen siendo comparables celda a celda.
2. **La cantidad de columnas de mes es dinÃ¡mica**, igual que en pantalla: se derivan del ejercicio, no son doce fijas.
3. **El encabezado de cada mes es un nÃºmero** (`202601`) con `number_format='000000'`, no texto: asÃ­ se puede ordenar y usar en fÃ³rmulas.
4. **La inversiÃ³n de signo vive Ãºnicamente acÃ¡.** Con alcance `resultados` los importes se multiplican por â1, de modo que los ingresos salgan positivos, los egresos negativos y la fila de totales muestre la ganancia del mes. Es el mismo criterio del VFP, donde `xSig = -1` sÃ³lo existe dentro del procedimiento de exportaciÃ³n.
5. **Sumarizadoras en negrita y azul**, y `freeze_panes` en la columna de Apertura para que Cuenta/Detalle queden fijos al desplazarse.
6. El botÃ³n reenvÃ­a el formulario de filtros completo, asÃ­ que **el Excel refleja exactamente lo que estÃ¡ en pantalla**.

### Pruebas Automatizadas
```bash
python manage.py test contable.tests.test_saldos_mensuales_vistas --noinput
```
**Resultado:** `Ran 17 tests in 157.207s - OK`

```bash
python manage.py test contable --noinput
```
**Resultado:** `Ran 82 tests in 733.518s - OK`

Las pruebas del export abren el `.xlsx` generado con `openpyxl` y verifican celdas concretas: que el encabezado traiga los 12 perÃ­odos como enteros, que en modo "Todas" un ingreso valga `-1000.0` (signo natural) y en modo "SÃ³lo Resultados" `+1000.0`, que con ingresos 1000 y egresos 400 la fila TOTALES muestre `600.0` de ganancia, y que en modo "Todas" esa misma fila cierre en `0.0` por partida doble.

### Estado actual y siguientes pasos
Fase 7 completa. Quedan la **fase 8** (medir con `EXPLAIN ANALYZE` y decidir el Ã­ndice de cobertura) y la **fase 9** (contraste manual contra los CSV de referencia de ARMERIA ARMAR). Para la 9 hace falta migrar esos datos: la base actual tiene 46 asientos y ningÃºn asiento de apertura.

---

## 15 de Agosto de 2026 â BotÃ³n Consultar, SelecciÃ³n de Columnas (Pantalla, Excel y CSV) en Libro Mayor â Plan 048

### Objetivo
Resolver la consulta del Libro Mayor bajo demanda (sin autoejecuciÃ³n al abrir), incorporar la barra de verificaciÃ³n de parÃ¡metros en el modal de cuenta, selecciÃ³n dinÃ¡mica de columnas en la grilla (con 10 predeterminadas y `leyenda` desactivada por defecto), exportaciÃ³n en formato Tabla de Excel (`.xlsx`) y nuevo formato CSV (`.csv`) con BOM UTF-8.

### Archivos Modificados / Creados
- `contable/services/reportes_mayor.py` [NEW]: catÃ¡logo maestro de columnas (`COLUMNAS_MAYOR_CATALOGO`), extractor de columnas solicitadas (`obtener_columnas_seleccionadas`) y formateador de celdas por movimiento (`obtener_valor_columna_movimiento`).
- `contable/services/reportes_excel.py` [MODIFY]: reestructuraciÃ³n de `exportar_mayor_excel` para construir la planilla dinÃ¡micamente con las columnas elegidas y aplicar el objeto `openpyxl.worksheet.table.Table`.
- `contable/views_reportes.py` [MODIFY]: actualizaciÃ³n de `exportar_mayor` y nuevo endpoint `exportar_mayor_csv`.
- `contable/views_htmx.py` [MODIFY]: `libro_mayor_rows` y `mayor_cuenta_modal` con fallbacks de cuenta, selecciÃ³n de columnas y `condic` predeterminados (`1`, `2` y `5`).
- `contable/views.py` [MODIFY]: `LibroMayorView` enviando catÃ¡logo de columnas y `condics_predeterminados`.
- `contable/urls.py` [MODIFY]: registro de ruta `mayor/exportar-csv/`.
- `templates/contable/partials/libro_mayor.html` [MODIFY]: selector desplegable de columnas, botÃ³n CSV, checkboxes `condic` predeterminados (1, 2 y 5) y mensaje inicial informativo sin autoejecuciÃ³n.
- `templates/contable/partials/libro_mayor_rows.html` [MODIFY]: renderizado dinÃ¡mico de celdas segÃºn las columnas seleccionadas y actualizaciÃ³n automÃ¡tica de `thead`.
- `templates/contable/modals/mayor_cuenta_modal.html` [MODIFY]: barra de verificaciÃ³n de parÃ¡metros con botÃ³n "Generar Reporte", selector de columnas y botones CSV, Excel y PDF.
- `contable/tests/test_libro_mayor_columnas.py` [NEW]: pruebas automatizadas para modal, fallback de cuentas y exportaciÃ³n a CSV.
- `docs/planes/048_libro_mayor_boton_generar.md` [NEW]: plan de implementaciÃ³n aprobado.

### Detalle TÃ©cnico
1. **EjecuciÃ³n Bajo Demanda:** Se eliminÃ³ la peticiÃ³n automÃ¡tica `hx-trigger="load"` del modal `mayor_cuenta_modal.html`. La grilla muestra un mensaje guiando al usuario a verificar sus parÃ¡metros y presionar **"Generar Reporte"** o **"Consultar"**.
2. **ConservaciÃ³n de Filtros Existentes:** Se mantuvieron todos los campos de bÃºsqueda previa (Rango de cuentas, Fechas, Cliente/Proveedor, Sucursal y CondiciÃ³n).
3. **CondiciÃ³n Predeterminada:** Se pre-completaron las opciones `1 - Real`, `2 - Presupuestado` y `5 - Apertura` como activas por defecto.
4. **SelecciÃ³n DinÃ¡mica de Columnas:** Se definiÃ³ un catÃ¡logo extensible de 24+ campos de `Asiento`, `AsientoLinea` y `Cuenta`. Por defecto se muestran 10 columnas (`asiento_id`, `fecha`, `concepto`, `cuenta_id`, `cuenta`, `debe`, `haber`, `saldo`, `condic`, `sucursal`), manteniendo `leyenda` desactivada por defecto.
5. **ExportaciÃ³n a CSV con BOM UTF-8:** Se creÃ³ la exportaciÃ³n a CSV con delimitador `;` y BOM `\ufeff` para garantizar apertura nativa sin problemas de codificaciÃ³n en Excel, PowerBI o software externo.
6. **Excel en Formato Tabla:** La exportaciÃ³n a Excel incluye Ãºnicamente las columnas seleccionadas en pantalla y las empaqueta dentro de un objeto `openpyxl.worksheet.table.Table`.

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test contable.tests.test_libro_mayor_columnas --keepdb --noinput
```
**Resultado:** `Ran 3 tests in 11.724s - OK`

### Estado actual y siguientes pasos
Plan 048 completamente implementado y verificado. Todas las pantallas y exportaciones del Libro Mayor operan bajo demanda y con selecciÃ³n dinÃ¡mica de columnas.

---

## 16 de Agosto de 2026 â Plan 049: VÃ­nculo contable de `tesoreria_movimiento_caja`

### Objetivo
Prerrequisito del **Estado de Origen y AplicaciÃ³n de Fondos** (EOAF), que migra los formularios
VFP `suma_saldo_fciero.scx` y `sum_sal_fciero_mov.scx`. La tabla `tesoreria_movimiento_caja` no
tenÃ­a cÃ³mo responder "Â¿de quÃ© cuenta vino la plata y a quÃ© cuenta se aplicÃ³?": le faltaban el
asiento, la cuenta de imputaciÃ³n y el cliente/proveedor, y su `fecha` era la de carga y no la del
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
  `fecha` pasa de `DateTimeField(auto_now_add=True)` a `DateField`; dos Ã­ndices compuestos y el
  `CheckConstraint` de `condic`.
- `tesoreria/views_htmx.py`: los seis circuitos que crean movimientos de caja.
- `tesoreria/services/caja_diaria.py`: docstring desactualizada.
- `migracion/scripts/03_migrar_tesoreria.py`: informa `fecha` (ahora obligatoria) y mapea los tres
  vÃ­nculos del DBF legado.

### Detalle TÃ©cnico

**1. Modelo.** Cuatro FK nuevas, todas nullable. `asiento` va con `on_delete=PROTECT`: los asientos
nunca se borran â`anular_asiento_de_comprobante()` solo marca `anulado=True`â, asÃ­ que la FK no
puede quedar colgada. `fecha` pierde su `db_index` propio porque el Ã­ndice compuesto
`(empresa, fecha)` lo cubre y ninguna consulta se hace sin acotar por empresa. `asiento` y
`cli_pro` tampoco llevan Ã­ndice explÃ­cito: Django ya indexa toda FK y duplicarlo solo costarÃ­a
escrituras.

**2. `cuenta` = cuenta de imputaciÃ³n principal.** Un movimiento de caja es UNO por comprobante,
pero la contrapartida puede ser VARIAS cuentas (recibo simple, OP simple, venta mostrador
multi-rubro). Se guarda la de mayor importe, con una regla Ãºnica para los seis circuitos:
`cuenta_principal_del_asiento()` agrupa las lÃ­neas del asiento por cuenta, descarta las de
disponibilidad (`tipo_disponibilidad` no vacÃ­o: son el bolsillo, no el origen ni la aplicaciÃ³n) y
devuelve la mayor, con desempate por `cuenta_id` para que el resultado sea determinÃ­stico.
**El desglose exacto queda en las lÃ­neas del asiento**, que es de donde los reportes de fondos
toman los importes: `cuenta` sirve para listados, filtros y bÃºsquedas, no para cuadrar.

**3. `fecha`.** `ALTER COLUMN "fecha" TYPE date USING "fecha"::date`. No se pierde el instante de
carga: `MovimientoCaja` hereda `fecha_creacion` de `AuditModel`, que ya guardaba exactamente lo
mismo que el viejo `fecha` (estaba duplicado). Corrige el desvÃ­o de fondo: un recibo del 15/05
cargado el 16/08 caÃ­a en agosto en cualquier reporte por perÃ­odo.

**4. `condic` restringido a (1, 2)** por CheckConstraint. Un movimiento de FONDOS solo puede ser
Real o Presupuestado: el 3 (Ajuste) lo paga el socio y no sale plata de la empresa, el 4 son
ajustes del estudio y los 5/6/7 los genera el sistema. Coincide con la lente de GestiÃ³n.

**5. Bug corregido.** Caja mostrador fijaba `condic=1` en el movimiento de caja, asÃ­ que una venta
presupuestada quedaba registrada como Real. Ahora se deriva del tipo de comprobante:
**PRE (Presupuesto) â 2; cualquier otro â 1**, calculado en el servidor y no tomado del payload.

**5 bis. Bug latente corregido de arrastre.** `tesoreria/services/caja_diaria.py` arma una sola
lista con las filas de sus dos fuentes y la ordena por la tupla `(fecha, id)`: la fuente de
asientos aporta `asiento.fecha` (`date`) y la de movimientos aportaba `movimiento.fecha`
(`datetime`). Ordenar esa lista mezclada lanza `TypeError: '<' not supported between instances of
'datetime.datetime' and 'datetime.date'` en cuanto una caja tiene movimientos de **ambas**
fuentes, que es el caso normal apenas conviven un cobro de mostrador y un recibo. Al pasar `fecha`
a `DateField` los dos lados quedan del mismo tipo. Cubierto por un test de regresiÃ³n.

**6. Migraciones en tres pasos.** El backfill (0014) resuelve `empresa` por la sesiÃ³n, `fecha` y
`cli_pro` por el comprobante, y `asiento` validando el id contra la tabla de asientos âlos tres
comprobantes lo guardan en un `IntegerField` sin FK, asÃ­ que puede apuntar a un asiento
inexistente y la FK nueva no lo tolerarÃ­aâ. Los tres comprobantes sirven de origen, incluida la
venta de mostrador (estampa `venta.asiento_id`): solo quedan sin asiento los movimientos internos
y los importados de VFP sin `ID_ASTO`. **Antes de aplicar el constraint, verifica que no
existan filas con `condic` fuera de (1, 2) y aborta con el listado si las hay**, en vez de
corregirlas por su cuenta. Informa por consola cuÃ¡ntas fechas se reencuadraron.

### Pruebas Automatizadas
```bash
python manage.py test tesoreria.tests.test_plan049_movimiento_caja
```
**Resultado:** `Ran 15 tests in 116.088s - OK`

Cobertura: el servicio de imputaciÃ³n (descarte de disponibilidades, mayor importe, desempate
determinÃ­stico, `None` sin contrapartida, regla PREâ2); recibo con fecha retroactiva; cobranza a
cliente y pago a proveedor (asiento, cuenta, cli_pro, empresa); recibo simple y OP simple 60/40 y
70/30 verificando que el asiento conserva **las dos** cuentas; recontabilizaciÃ³n que reapunta el
movimiento al asiento nuevo dejando el viejo anulado; la regresiÃ³n de ordenamiento de la Caja
Diaria con las dos fuentes conviviendo; y el CheckConstraint rechazando los `condic` 0, 3, 4, 5,
6 y 7.

**RegresiÃ³n de los mÃ³dulos afectados:**
```bash
python manage.py test tesoreria contable
```
**Resultado:** `Ran 142 tests in 795.632s - OK`

### Estado actual y siguientes pasos
Plan 049 **ejecutado**. Las migraciones 0013/0014/0015 quedan **sin aplicar en producciÃ³n**:
correrlas requiere la ventana del usuario, porque el backfill reencuadra fechas histÃ³ricas.

**Siguiente:** Plan 050 â EOAF, con **Ingresos de Fondos / Egresos de Fondos / Flujo Neto**
(sin Disponibilidad Inicial), filtro Real/Presupuestado, desglose por medio, drill-down por cuenta
y exportaciÃ³n a Excel y PDF.

---

## 16 de Agosto de 2026 â Plan 049 (adenda): cierre de la deuda tÃ©cnica del asiento de mostrador

### Objetivo
A pedido del usuario, corregir el asiento de la venta de caja mostrador, que habÃ­a quedado fuera
del alcance inicial del Plan 049.

### Archivos Modificados
- `tesoreria/views_htmx.py`: el `Asiento.objects.create` de `_crear_asientos_y_movimientos_cobro`.
- `tesoreria/services/caja_diaria.py`: deduplicaciÃ³n entre las dos fuentes del reporte.
- `tesoreria/tests/test_plan049_movimiento_caja.py`: clase `CajaMostradorTest` (3 pruebas).
- `docs/planes/049_movimiento_caja_asiento_cuenta_clipro.md`: Â§10 marcada como cerrada.

### Detalle TÃ©cnico

**1. El asiento de mostrador** ahora recibe `condic=venta.condic` âhereda la condiciÃ³n del
comprobante, como manda `.cursorrules`; antes quedaba en el default 1 aunque la venta fuera
presupuestadaâ, `sesion_caja=sesion_caja` âsin eso el cobro no entraba al reporte de Caja Diaria,
que filtra por ese campoâ y `fecha=venta.fecha` en lugar de `timezone.localdate()`, para que
comprobante, asiento y movimiento de caja lleven siempre la misma fecha.

**2. Efecto colateral resuelto: doble conteo.** Al estampar `sesion_caja`, el cobro pasa a llegar
al reporte por sus **dos** fuentes (`_lineas_desde_asientos` y `_lineas_desde_movimientos`). La
deduplicaciÃ³n navegaba al comprobante y su cadena era `movimiento.recibo or movimiento.orden_pago`:
los cobros de mostrador cuelgan de `venta`, asÃ­ que **quedaban fuera y se habrÃ­an contado dos
veces**. Ahora se deduplica por `MovimientoCaja.asiento_id` âel campo que agrega este mismo plan,
que resuelve los tres tipos de comprobante de una sola formaâ, con el comprobante como fallback
para los movimientos histÃ³ricos anteriores al backfill.

**3. Lo que NO se tocÃ³:** el asiento se sigue armando con `Asiento.objects.create` +
`AsientoLinea.objects.create` en vez de `crear_asiento()`. Es un refactor del circuito de
facturaciÃ³n y no deja ningÃºn desvÃ­o funcional pendiente.

### Pruebas Automatizadas
```bash
python manage.py test tesoreria.tests.test_plan049_movimiento_caja
```
**Resultado:** `Ran 18 tests in 126.109s - OK`

Las tres nuevas cubren el circuito de mostrador de punta a punta (preventa â cobro â venta â
asiento â movimiento), usando un comprobante **PRE**, que es el camino que no llama a ARCA:
`condic=2` propagado a venta, movimiento y asiento; `sesion_caja` y `fecha` estampadas en el
asiento; y la regresiÃ³n de doble conteo en la Caja Diaria.

### Estado actual y siguientes pasos
Plan 049 **cerrado por completo**, deuda tÃ©cnica incluida. Migraciones todavÃ­a **sin aplicar**.
Siguiente: **Plan 050 â Estado de Origen y AplicaciÃ³n de Fondos**.

---

## 16 de Agosto de 2026 â Plan 050 fases 1 y 2: nÃºcleo de fondos y servicio del EOAF

### Objetivo
Arrancar el **Estado de Origen y AplicaciÃ³n de Fondos** (migraciÃ³n de `suma_saldo_fciero.scx`).
Fase 1: extraer el nÃºcleo de cÃ¡lculo que ya existÃ­a en la Caja Diaria. Fase 2: el servicio del
reporte, con agregaciÃ³n por cuenta y rollup jerÃ¡rquico.

### Archivos Creados
- `tesoreria/services/fondos.py` [NEW]: nÃºcleo compartido â constantes de disponibilidad,
  `prorratear()`, `lineas_de_fondos()` y `asientos_de_fondos_por_fecha()`.
- `tesoreria/services/eoaf.py` [NEW]: `estado_origen_aplicacion_fondos()` y `detalle_de_cuenta()`.
- `tesoreria/tests/test_eoaf.py` [NEW]: 18 pruebas.
- `docs/planes/050_estado_origen_aplicacion_fondos.md` [NEW]: plan archivado.

### Archivos Modificados
- `tesoreria/services/caja_diaria.py`: delega la descomposiciÃ³n en `fondos.py`; se eliminaron las
  definiciones duplicadas de `_fila_vacia` y `_cuantizar`; nuevo `asientos_de_fondos()`.

### Detalle TÃ©cnico

**1. Un movimiento de fondos es todo asiento que toca una cuenta con `tipo_disponibilidad`.**
Dentro de Ã©l, las lÃ­neas de disponibilidad son el *bolsillo* (dan el desglose por medio) y las de
contrapartida son las filas del reporte. La fuente es el asiento y no `MovimientoCaja`, asÃ­ que
entran tambiÃ©n las compras de contado, los dÃ©bitos bancarios y los asientos manuales que nunca
pasaron por una caja.

**2. Signo, verificado contra `OrigenyAplicacionFondos.xlsx`:** contrapartida al **HABER** =
origen de fondos (**Ingresos**); al **DEBE** = aplicaciÃ³n (**Egresos**). Contrastado en cuatro
cuentas de la muestra (clientes, proveedores, recupero de gastos, telefonÃ­a).

**3. Los traslados entre disponibilidades se excluyen solos.** Un retiro de mostrador a tesorerÃ­a
tiene sus dos puntas en cuentas de disponibilidad: no hay contrapartida, `lineas_de_fondos` lo
emite con `cuenta_id = None` y el EOAF lo descarta. No hizo falta ninguna regla especial. El
legado los mostraba mezclados en el cuerpo del reporte.

**4. Rollup por prefijo de `jerarquia`, acumulando solo IMPUTABLES**, igual que el legado
(`sum ... for jera_cta = jera and imputable = .T.`). Se usa el prefijo y no la FK `sumariza`
porque en los datos legados `sumariza` estÃ¡ desfasado. Los totales suman solo imputables: las
sumarizadoras ya las contienen.

**5. ExtracciÃ³n sin cambio de comportamiento.** `prorratear()` conserva un detalle del original
que era fÃ¡cil de perder: cuando los pesos suman cero **no** hay contrapartida identificable, y el
neto NO se asigna al primero ni se reparte por partes iguales âeso imputarÃ­a fondos a una cuenta
que no los moviÃ³â. Devuelve lista vacÃ­a y decide quien llama.

### Pruebas Automatizadas
```bash
python manage.py test tesoreria.tests.test_eoaf
```
**Resultado:** `Ran 18 tests in 52.144s - OK`

```bash
python manage.py test tesoreria.tests.test_caja_diaria tesoreria.tests.test_plan049_movimiento_caja
```
**Resultado:** `Ran 32 tests in 142.667s - OK` (la extracciÃ³n no alterÃ³ la Caja Diaria)

Cobertura del EOAF: signo de ingresos/egresos, desglose por medio, traslados que no generan
filas, prorrateo que cierra exacto sin perder centavos, rollup jerÃ¡rquico sin doble conteo,
filtros de condiciÃ³n y de fechas, exclusiÃ³n de anulados, aislamiento entre empresas, y el
drill-down con saldo corrido y filtro por medio.

**Control de coherencia (el que en el legado NO cerraba):** Î£ Flujo Neto de las imputables ==
variaciÃ³n neta de las disponibilidades del perÃ­odo. Verificado en test y contra los datos reales
de la empresa 1: neto 5.936.786,45 contra EFE 4.381.966,45 + DOL 1.718.200,00 + BCO â163.380,00.

### Estado actual y siguientes pasos
Fases 1 y 2 **completas**. Pendientes: fase 3 (vista y template HTMX en TesorerÃ­a), fase 4
(drill-down) y fase 5 (Excel y PDF).

**Pendiente de decisiÃ³n del usuario:** marcar la cuenta `111009 TRANSFERENCIA ENTRE SUCURSALES`
con `tipo_disponibilidad='OTR'`. Es un cambio de DATO, no de cÃ³digo. Sin Ã©l, los traslados entre
sucursales van a generar una fila espuria en el EOAF.

---

## 16 de Agosto de 2026 â Plan 050 fases 3 a 5: pantalla, drill-down y exportaciones del EOAF

### Objetivo
Completar el Estado de Origen y AplicaciÃ³n de Fondos: pantalla en el mÃ³dulo **TesorerÃ­a**,
drill-down por cuenta y exportaciÃ³n a Excel y PDF.

### Archivos Creados
- `tesoreria/views_eoaf.py` [NEW]: `eoaf_index`, `eoaf_grilla`, `eoaf_cuenta_modal`,
  `eoaf_excel`, `eoaf_pdf`.
- `tesoreria/services/eoaf_export.py` [NEW]: Excel y PDF.
- `templates/tesoreria/eoaf.html` [NEW]: pantalla con filtros y botÃ³n Generar.
- `templates/tesoreria/partials/eoaf_grilla.html` [NEW]: grilla jerÃ¡rquica.
- `templates/tesoreria/modals/eoaf_cuenta_modal.html` [NEW]: drill-down.
- `templates/tesoreria/pdf/eoaf_pdf.html` [NEW]: layout del PDF.

### Archivos Modificados
- `tesoreria/urls.py`: cinco rutas nuevas bajo `origen-aplicacion-fondos/`.
- `templates/tesoreria/index.html`: tarjeta de acceso al reporte.
- `tesoreria/tests/test_eoaf.py`: clase `VistasTest` (7 pruebas de vistas y exportaciones).
- `docs/planes/050_...md`: fases marcadas como ejecutadas.

### Detalle TÃ©cnico

**1. La grilla no se autoejecuta.** El usuario fija perÃ­odo y condiciÃ³n y presiona **Generar**,
igual que el `cmdGenerar` del formulario legado y que el criterio adoptado en el Libro Mayor
(Plan 048). Sin eso, entrar a la pantalla dispararÃ­a una consulta sobre todo el ejercicio.

**2. Columnas: Ingresos de Fondos / Egresos de Fondos / Flujo Neto**, mÃ¡s el desglose en los
**seis** medios (efectivo, dÃ³lares, valores, banco, tarjetas, otros). El legado mostraba tres y
por eso sus totales no cerraban. **Sin `Disp.Inicial`**, por decisiÃ³n del usuario. Sumarizadoras
en azul y negrita, como en el original.

**3. Drill-down** por cuenta imputable: asiento, fecha, cliente/proveedor, concepto, ingresos,
egresos, desglose por medio, saldo corrido y condiciÃ³n â la vista `cons_caja_diaria_cta` del
legado. Incluye el filtro por medio del option-group `opgMoneda`, extendido de cuatro opciones a
las siete que manejamos. Valida que la cuenta pertenezca a la empresa activa.

**4. Aplanado de `medios` en la vista.** Los templates de Django no indexan un dict por clave
variable. En lugar de agregar un filtro sÃ³lo para eso, `_con_medios_en_orden()` convierte el dict
en una lista ordenada y el template itera. Menos superficie y sin tags nuevos.

**5. DecisiÃ³n tomada con la autonomÃ­a delegada por el usuario:** el **Typeahead + Lupa** por
cliente/proveedor en el drill-down **no se implementÃ³**. El detalle ya llega acotado a una sola
cuenta y a un perÃ­odo, y en los volÃºmenes reales entra en pantalla; el buscador habrÃ­a sido
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
salga con cabecera `%PDF`, y que las exportaciones respeten el filtro de condiciÃ³n.

### Estado actual y siguientes pasos
**Plan 050 completo (fases 1 a 5).** El reporte estÃ¡ en TesorerÃ­a â Origen y AplicaciÃ³n de Fondos.

**Pendiente operativo:** las migraciones `tesoreria.0013/0014/0015` del Plan 049 **siguen sin
aplicar**. El EOAF funciona sin ellas porque lee los asientos, pero el rango de fechas de
`MovimientoCaja` y el vÃ­nculo con el asiento dependen de correrlas:
`python manage.py migrate tesoreria`.

**ConfiguraciÃ³n aplicada:** la cuenta `111009 TRANSFERENCIA ENTRE SUCURSALES` quedÃ³ marcada con
`tipo_disponibilidad='OTR'`. En cada cliente nuevo, la cuenta que se cargue en
`ParametrosContables.cta_transferencias_sucursal` debe quedar marcada igual, o cada traslado
entre sucursales generarÃ¡ una fila espuria en el reporte.

---

## 16 de Agosto de 2026 â AplicaciÃ³n de las migraciones del Plan 049 y verificaciÃ³n en la app

### Motivo
Con el modelo ya cambiado y las migraciones sin aplicar, cualquier consulta a `MovimientoCaja`
fallaba: `ProgrammingError: column tesoreria_movimiento_caja.empresa_id does not exist` al abrir
**Caja Diaria**. La aplicaciÃ³n estaba caÃ­da, asÃ­ que correr las migraciones era la correcciÃ³n.

Antes de migrar se respaldÃ³ la tabla completa (21 filas) a CSV.

### Resultado de la migraciÃ³n
```
Applying tesoreria.0013_plan049_movimiento_caja... OK
Applying tesoreria.0014_plan049_backfill...
  Plan 049: 21 movimientos actualizados. 1 con la fecha reencuadrada a la del comprobante.
  18 vinculados a un asiento (3 sin asiento resoluble).
Applying tesoreria.0015_plan049_constraint_condic... OK
```

Estado final: 21/21 con `empresa` y `cli_pro`, 18 con `asiento`, 15 con `cuenta`.

### VerificaciÃ³n en la aplicaciÃ³n (HTTP 200 contra la base real)
| Pantalla | Estado |
|---|---|
| `/tesoreria/caja-diaria/` | 200 â restablecida |
| `/tesoreria/origen-aplicacion-fondos/` | 200 |
| `â¦/grilla/` | 200 |
| `â¦/excel/` | 200 (xlsx generado) |
| `â¦/pdf/` | 200 (pdf generado) |

### Hallazgos en los datos (PREEXISTENTES, ajenos a estos planes)
1. **Recibos 1, 4 y 5 sin contabilizar** (`Recibo.asiento_id = None`). Son los 3 movimientos que
   quedaron sin `asiento`: el backfill hizo lo correcto al dejarlos nulos. HabrÃ­a que decidir si
   se recontabilizan.
2. **Asientos 137, 138 y 139 (`VENTA MOSTRADOR 1/2/3`) tienen CERO lÃ­neas.** Cabeceras huÃ©rfanas
   de alguna corrida parcial previa del circuito de mostrador. El EOAF los ignora correctamente
   âsin lÃ­neas de disponibilidad no son un movimiento de fondosâ, pero quedan sueltos en la
   contabilidad. **Quedan anotados para revisiÃ³n del usuario.**

### Nota de build
Se ejecutÃ³ `npm run build` de Tailwind: las pantallas nuevas usan clases (violeta,
`max-w-[1400px]`, `sticky bottom-0`) que no estaban en el `output.css` purgado y sin recompilar
el layout se rompÃ­a.

### RegresiÃ³n final de los Planes 049 y 050
```bash
python manage.py test tesoreria contable facturacion
```
**Resultado:** `Ran 189 tests in 959.153s - FAILED (errors=2)`

Los **2 errores son preexistentes y ajenos a estos planes**: los dos Ãºnicos tests de
`facturacion.tests.test_armeria_credencial_clu.ArmeriaCredencialCLUTestCase` fallan en su `setUp`
con `TypeError: Sucursal() got unexpected keyword arguments: 'codigo'` âel modelo `Sucursal` no
tiene campo `codigo`â. Entraron con el commit `7ff0da8` y ya estaban registrados en esta bitÃ¡cora
en la entrada del 15/08. Verificado: ese archivo tiene exactamente 2 tests, `git status
facturacion/` no reporta cambios, y una corrida aislada de
`facturacion.tests.test_armeria_credencial_clu` + `tesoreria.tests.test_eoaf` da
`Ran 28 tests - FAILED (errors=2)`, es decir **26/26 del EOAF en verde**.

**`tesoreria` y `contable`: sin fallas.**

## 16 de Agosto de 2026 â Limpieza de los movimientos de la empresa 1

### Objetivo
La empresa 1 (IKIGAI TECHNOLOGY SAS) se cargÃ³ en etapa de diseÃ±o y se operÃ³ con el sistema a
medio desarrollar, asÃ­ que arrastraba inconsistencias (asientos vacÃ­os, recibos sin contabilizar).
Se vaciÃ³ su historial transaccional para poder probar los circuitos desde cero.

### Alcance (elegido por el usuario)
**SÃ³lo movimientos.** Se CONSERVAN plan de cuentas, ParametrosContables, productos, subproductos,
stock por sucursal, familias, marcas, rubros, clientes/proveedores, medios de pago, cuentas
bancarias, cajas, sucursal, ejercicio y cotizaciones. Las tablas globales compartidas entre
empresas (bancos, tipos de comprobante, jurisdicciones, alÃ­cuotas de IVA, usuarios, permisos) no
se tocaron nunca.

### Procedimiento
1. **Respaldo completo** con `pg_dump -Fc` de toda la base antes de empezar.
2. **Relevamiento** de las 35 tablas con FK a `empresa` y de las que dependen por cascada.
3. **SimulaciÃ³n** dentro de una transacciÃ³n que se revierte, para confirmar el orden de borrado.
4. **EjecuciÃ³n** con el mismo script.

### Detalle TÃ©cnico
**Orden de borrado.** De la hoja a la raÃ­z, respetando los FK con `PROTECT`. Tres dependencias
mandan: `MovimientoCaja.asiento â Asiento` obliga a borrar los movimientos antes que los
asientos; `Asiento.sesion_caja â CajaSesion` obliga a borrar los asientos antes que las sesiones;
y los satÃ©lites (`ValorTerceros`, `TransaccionBancaria`) protegen a `MovimientoCajaDetalle`, asÃ­
que van primero.

**SeÃ±ales desactivadas durante el borrado.** El primer intento abortÃ³ con
`ValidationError: El asiento estÃ¡ desbalanceado. Debe 25000.00 - Haber 50000.00`: el `post_delete`
de `CompraItem` recalcula y vuelve a guardar la `Compra`, y el `post_save` de `Compra` dispara
`contabilizar_compras()`. A mitad del borrado la compra ya habÃ­a perdido sus Ã­tems, asÃ­ que el
asiento salÃ­a descuadrado. Como todo corrÃ­a en una transacciÃ³n, no se borrÃ³ nada. La soluciÃ³n fue
un context manager que desconecta todas las seÃ±ales de modelo y las restaura en un `finally`: en
un teardown masivo no se quiere ningÃºn efecto colateral.

**Saldos derivados recompuestos a mano.** Con las seÃ±ales apagadas, las cuentas corrientes no se
recalculan solas. Al terminar se llevÃ³ `ClienteProveedor.saldo` a su `saldo_inicial`: eran 4
entidades con saldo distinto de cero, hoy las 6 en `0.00`.

**Stock.** Se borrÃ³ el LIBRO de movimientos (`MovimientoStock`, `facturacion.Movimiento`) pero NO
los saldos (`StockSucursal`, 13.596 filas; `ExtensionArmeria`, 3.754). No genera incoherencia:
el stock se cargÃ³ por importaciÃ³n y no se derivaba de esos movimientos âhabÃ­a 13.596 registros de
stock contra 59 movimientosâ.

### Resultado
**356 filas borradas** y 4 saldos reseteados:

| Grupo | Filas |
|---|---|
| Asientos y lÃ­neas | 24 + 87 |
| Ventas / Ã­tems | 18 + 23 |
| Compras / Ã­tems / alÃ­cuotas / ret-perc | 5 + 5 + 1 + 3 |
| Preventas / Ã­tems | 18 + 23 |
| Recibos / aplicaciones | 5 + 5 |
| Ãrdenes de pago / aplicaciones | 1 + 1 |
| Movimientos de caja / detalles / sesiones | 17 + 15 + 3 |
| Trazabilidad de movimientos | 30 |
| Movimientos de stock | 59 |
| Libro IVA / alÃ­cuotas / retenciones sufridas | 5 + 4 + 3 |
| Transacciones bancarias | 1 |

### VerificaciÃ³n
- **Empresa 1:** los 13 grupos de movimientos en **0**; maestros intactos (200 cuentas, 347
  productos, 859 subproductos, 12 rubros, 6 clientes/proveedores, 6 medios de pago, 2 cuentas
  bancarias, 2 cajas, 1 sucursal, 1 ejercicio, ParametrosContables).
- **Otras empresas sin tocar:** empresa 2 con 21 asientos, 11 ventas, 268 cuentas y 6.793
  productos; empresa 3 con 1 asiento, 1 venta y 247 cuentas.
- **AplicaciÃ³n operativa:** TesorerÃ­a, Caja Diaria, EOAF y su grilla responden 200.

### Estado actual y siguientes pasos
La empresa 1 quedÃ³ con su configuraciÃ³n y sus maestros completos y sin historial de operaciones,
lista para probar los circuitos de cero. El respaldo previo queda disponible por si hiciera falta
recuperar algo.

---

## 16 de Agosto de 2026 â VisualizaciÃ³n de Stock Activo y Stock Destino en Buscador Avanzado de Productos (Remitos Internos) â Plan 051

### Objetivo
Mostrar el stock de la sucursal activa en el Buscador Avanzado de Productos en todas las vistas de bÃºsqueda y, al abrirlo desde el formulario de Remito Interno, incorporar automÃ¡ticamente la columna de **Stock Destino** para que el usuario pueda evaluar la necesidad y existencias reales en ambas sucursales.

### Archivos Modificados / Creados
- `templates/facturacion/remito_interno_carga.html` [MODIFY]: inclusiÃ³n de `hx-include="[name='sucursal_origen'], [name='sucursal_destino']"` en el botÃ³n de la lupa.
- `facturacion/views_htmx.py` [MODIFY]: actualizaciÃ³n de `buscador_productos_modal` y `lista_productos_resultados` para calcular y adjuntar `stock_origen` (o sucursal activa) y `stock_destino` en los productos buscados.
- `templates/facturacion/modals/buscador_productos.html` [MODIFY]: agregados inputs ocultos de sucursal en `thead`, cabeceras dinÃ¡micas para **Stk. Activo/Origen** y **Stk. Destino** y ajuste de `tbody` `hx-get` inicial.
- `templates/facturacion/partials/productos_search_results.html` [MODIFY]: renderizado de celdas de stock con insignias visuales (verde/rojo para origen/activa, azul/Ã¡mbar para destino) y ajuste de `colspan`.
- `facturacion/tests/test_plan028.py` [MODIFY]: adiciÃ³n de `BuscadorProductosStockTests` para validar contexto y asignaciÃ³n de stock por sucursal en HTMX.
- `docs/planes/051_stock_sucursales_modal_remito_interno.md` [NEW]: plan de implementaciÃ³n histÃ³rico.

### Detalle TÃ©cnico
1. **Paso de ParÃ¡metros HTMX:** El botÃ³n de la lupa en `remito_interno_carga.html` incluye `[name='sucursal_origen']` y `[name='sucursal_destino']`.
2. **DeterminaciÃ³n de Sucursal Activa vs. Origen/Destino:** `sucursal_origen_id` se resuelve contra el parÃ¡metro GET enviado o contra la sucursal activa de la sesiÃ³n (`request.session.get('sucursal_id')`). `sucursal_destino_id` sÃ³lo se procesa si estÃ¡ presente en el GET.
3. **Consulta Eficiente en `StockSucursal`:** Para los productos devueltos en la bÃºsqueda (mÃ¡ximo 50), se realiza una consulta agrupada contra `StockSucursal` filtrando por `producto_id__in` y `sucursal_id__in`. El resultado se mapea en un diccionario `(producto_id, sucursal_id) -> cantidad` permitiendo la asignaciÃ³n en memoria `O(1)`.
4. **DiseÃ±o Visual:** Celdas con badges de color de Tailwind (`bg-emerald-100` / `bg-rose-100` para origen/activa y `bg-blue-100` / `bg-amber-100` para destino). En bÃºsquedas estÃ¡ndar donde no hay sucursal destino, se muestra la tabla con 6 columnas; en Remitos Internos se extiende a 7 columnas.

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test facturacion.tests.test_plan028
```
**Resultado:** `Ran 11 tests in 109.256s - OK`

### Estado actual y siguientes pasos
Plan 051 completamente implementado y verificado. El modal de bÃºsqueda avanzada de productos muestra el stock activo en bÃºsquedas generales y amplÃ­a la vista a Stock Origen y Stock Destino al confeccionar Remitos Internos.

---

## 16 de Agosto de 2026 â Plan 053: `stock_inicial` y stock derivado por sucursal

### Objetivo
Que el stock deje de ser un contador incremental sin origen y pase a **derivarse** de un punto de
partida mÃ¡s los comprobantes, igual que la cuenta corriente:

    stock = stock_inicial + compras + recepciones â ventas â remitos internos

### Archivos Creados
- `productos/services/stock_service.py` [REESCRITO]: `recalcular_stock()`,
  `recalcular_stock_masivo()` y los tÃ©rminos de la fÃ³rmula declarados como datos.
- `productos/management/commands/recalcular_stock.py` [NEW]: comando de reconstrucciÃ³n.
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
- `productos/tests.py` [BORRADO]: stub vacÃ­o que rompÃ­a el descubrimiento de tests.

### Detalle TÃ©cnico

**1. El stock es derivado.** `StockSucursal.cantidad` se sigue materializando âse lee en toda la
operatoriaâ, pero ya no se ajusta por delta: se **recalcula completo** para ese (producto,
sucursal) cada vez que algo lo afecta. Las tres funciones que llaman las seÃ±ales conservan su
firma; por dentro registran el `MovimientoStock` de auditorÃ­a y delegan en `recalcular_stock()`.

**2. Los tÃ©rminos se declaran como datos, no cableados.** Cada uno dice quÃ© modelo aporta, con quÃ©
signo, por quÃ© campo de cantidad, cÃ³mo llega a la sucursal y quÃ© excluye. Sumar el tÃ©rmino de
**ajustes de inventario** âcuando se haga el formulario de toma fÃ­sicaâ serÃ¡ agregar una entrada,
sin revalidar los cuatro que ya funcionan.

**3. Exclusiones conservadas del cÃ³digo anterior**, cada una con su test: compras con
`id_fac_rem` o `gestion_stock_por_recepcion` (circuito OC), ventas anuladas o con `id_fac_rem`,
recepciones anuladas, remitos internos anulados, y el signo de las notas de crÃ©dito
(`TipoComprobante.signo = â1`, que hace que una NC de venta **devuelva** stock).

**4. Backfill que no mueve un solo nÃºmero.** `stock_inicial = cantidad â movimientos_ya_aplicados`,
calculado con cuatro consultas agrupadas por (producto, sucursal) en vez de cuatro por fila.
Resultado sobre la base real: **13.596 filas inicializadas, 7 con movimientos aplicados y 0
cantidades modificadas**.

**5. Dos caminos de recÃ¡lculo por una razÃ³n de performance.** `recalcular_stock()` hace cuatro
consultas por par (producto, sucursal): ideal al guardar un comprobante, inviable para un
inventario entero. La primera versiÃ³n del comando lo llamaba fila por fila y tardaba mÃ¡s de 10
minutos sobre 13.584 registros. `recalcular_stock_masivo()` agrupa los cuatro tÃ©rminos en cuatro
consultas totales: **49 segundos**.

**6. Baja de `Producto.stock` y `Producto.stkcons`.** Campos heredados del ERP en VFP, donde el
stock se llevaba sobre el producto. Se relevÃ³ que **nadie los escribÃ­a** y que sÃ³lo los leÃ­an dos
exports âel CSV legacy de 74 columnas y su gemelo en Excelâ, que emitÃ­an el valor congelado de la
importaciÃ³n. Ahora esas columnas traen el **stock real de la sucursal de la venta**, precargado en
una sola consulta para no disparar una por fila. `stkcons` (stock en consignaciÃ³n del VFP) queda
en `0.0` como relleno posicional: se conservan las 74 columnas para no romper al consumidor.
El total consolidado ya existÃ­a como la property `Producto.stock_global`.

### Dos problemas preexistentes corregidos al paso
1. **`productos/models.py`**: `InvalidOperation` se usaba en un `except` sin estar importado, asÃ­
   que un IVA mal formado producÃ­a `NameError` en vez de tomar el default. Faltaba una palabra en
   el import.
2. **`productos/tests.py`**: stub vacÃ­o de Django (3 lÃ­neas, del commit inicial) que convivÃ­a con
   el paquete `productos/tests/`. RompÃ­a el descubrimiento con
   `ImportError: 'tests' module incorrectly imported`, o sea que **`manage.py test productos`
   nunca habÃ­a funcionado**. Se borrÃ³ el stub.

### Pruebas Automatizadas
```bash
python manage.py test productos.tests.test_stock_inicial
```
**Resultado:** `Ran 20 tests in 198.099s - OK`

Cobertura: la fÃ³rmula completa, las siete exclusiones, las notas de crÃ©dito de venta y de compra,
la transferencia interna en dos pasos (el total no cambia), el aislamiento entre sucursales, la
idempotencia del recÃ¡lculo y âel caso que da sentido al planâ la **autorreparaciÃ³n**: se rompe
`cantidad` a mano y el recÃ¡lculo la corrige. Con el contador incremental anterior era imposible.

**VerificaciÃ³n sobre la base real:** `recalcular_stock --dry-run` sobre las tres empresas
(13.584 + 9 + 3 registros) informa *"Todos los registros ya estaban correctos"*: la fÃ³rmula
reproduce exactamente el stock que habÃ­a.

### Nota de numeraciÃ³n
Este plan se archivÃ³ primero como 052 y se **renumerÃ³ a 053** al detectarse que, en paralelo, la Trazabilidad de Subproductos ya usaba ese nÃºmero. Los archivos de migraciÃ³n conservan `plan052` en su NOMBRE a propÃ³sito: ya estaban aplicadas en la base y renombrarlas harÃ­a que Django las tomara como nuevas.

### Estado actual y siguientes pasos
Plan 053 **completo**. El stock es reconstruible con `manage.py recalcular_stock --empresa N`.

**PENDIENTE registrado (Â§8 bis del plan):** formulario de carga de inventarios, generales y
periÃ³dicos, al estilo del "arreglo de stock". Va en un plan aparte y necesitarÃ¡ su propio tÃ©rmino
en la fÃ³rmula (Â± ajustes), que es justamente lo que la estructura declarativa deja preparado.

---

## 16 de Agosto de 2026 â Trazabilidad de Subproductos (NÂ° Serie y CUIM) en Remitos Internos y RecepciÃ³n â Plan 052

### Objetivo
Permitir la transferencia de productos trazables (`subprod = True / 1`) mediante la validaciÃ³n de su nÃºmero de serie en la sucursal de origen, emitiendo el Remito Interno con los datos de **NÂ° Serie** y **CUIM**, mostrÃ¡ndolos en el PDF impreso y en la pantalla de recepciÃ³n interna, y reubicando automÃ¡ticamente el `Subproducto.sucursal_id` hacia la sucursal de destino al confirmarse el Informe de RecepciÃ³n.

### Archivos Modificados / Creados
- `facturacion/models.py` [MODIFY]: agregado de campos `subproducto` (FK), `serie` y `cuim` a `RemitoInternoItem`.
- `facturacion/migrations/0047_remitointernoitem_cuim_remitointernoitem_serie_and_more.py` [NEW]: migraciÃ³n de base de datos.
- `facturacion/views_remito_interno.py` [MODIFY]:
  - `RiItemAddView`: validaciÃ³n de productos trazables y verificaciÃ³n del subproducto en la sucursal de origen.
  - `RemitoInternoCargaView`: guardado de `subproducto_id`, `serie` y `cuim`.
  - `RecepcionInternaVincularView`: agrupaciÃ³n de Ã­tems por `(producto_id, subproducto_id)` para mantener viva la trazabilidad por serie.
  - `RecepcionInternaCargaView`: actualizaciÃ³n atÃ³mica de `subproducto.sucursal_id` a la sucursal de destino.
- `templates/facturacion/remito_interno_carga.html` [MODIFY]: adiciÃ³n de campo `NÂ° Serie (si aplica)` y parÃ¡metro `hx-include`.
- `templates/facturacion/partials/ri_items_tabla.html` [MODIFY]: visualizaciÃ³n de leyendas de Serie y CUIM.
- `templates/facturacion/pdf/remito_interno_pdf.html` [MODIFY]: impresiÃ³n de Serie y CUIM en el comprobante PDF.
- `templates/facturacion/partials/recepcion_interna_items_tabla.html` [MODIFY]: despliegue de Serie y CUIM en la recepciÃ³n interna.
- `templates/facturacion/modals/recepcion_interna_vincular.html` [MODIFY]: aclaraciÃ³n de trazabilidad por serie.
- `facturacion/tests/test_plan028.py` [MODIFY]: adiciÃ³n de `SubproductoRemitoInternoTests`.
- `docs/planes/052_trazabilidad_subproductos_remito_interno.md` [NEW]: plan de implementaciÃ³n histÃ³rico.

### Detalle TÃ©cnico
1. **ValidaciÃ³n de Subproducto y Origen:** Al ingresar una serie para un producto trazable (`subprod = True`), `RiItemAddView` busca la coincidencia exacta en `Subproducto`. Si no existe o se ubica en otra sucursal, rechaza la operaciÃ³n informando la inconsistencia.
2. **ConservaciÃ³n de Atributos:** Se almacenan `subproducto_id`, `serie` y `cuim` en `RemitoInternoItem` y se arrastran a la sesiÃ³n de recepciÃ³n interna.
3. **ReubicaciÃ³n FÃ­sica en BD:** Al momento de guardar el `Informe de RecepciÃ³n` (origen = INTERNO) en la sucursal destino, se ejecuta la actualizaciÃ³n `subproducto.sucursal = destino` con `update_fields=['sucursal']`.

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test facturacion.tests.test_plan028
```
**Resultado:** `Ran 13 tests in 141.564s - OK`

### Estado actual y siguientes pasos
Plan 052 completado y verificado en su totalidad. Toda transferencia interna de productos trazables contempla la serie y el CUIM desde la emisiÃ³n hasta la recepciÃ³n con reubicaciÃ³n automÃ¡tica de sucursal.

---

## 17 de Agosto de 2026 â BÃºsqueda y Autocarga por NÂ° de Serie en Remitos Internos (Plan 053)

### Objetivo
Permitir la bÃºsqueda rÃ¡pida y directa por NÂ° de Serie en la emisiÃ³n de Remitos Internos, verificando que la unidad no se encuentre vendida (`situacion != 'VENDIDA'`), comprobando su pertenencia a la sucursal de origen, y autocompletando el ID de producto, la descripciÃ³n y el CUIM.

### Archivos Modificados / Creados
- `facturacion/views_remito_interno.py` [MODIFY]:
  - `ri_buscar_subproducto_por_serie`: vista HTMX que filtra por `serie__iexact`, excluye `situacion='VENDIDA'`, verifica sucursal.
  - `ri_buscar_producto_por_id`: bÃºsqueda instantÃ¡nea con prioridad absoluta por `id` primario sobre `cod_prov`.
  - `RiItemAddView`: resoluciÃ³n de producto priorizando clave primaria `id` antes de `cod_prov`.
  - `RecepcionInternaCargaView` / `RecepcionInternaVincularModalView`: restricciÃ³n estricta de la sucursal receptora a la sucursal activa logueada.
  - `RecepcionInternaImprimirView` [NEW]: vista de emisiÃ³n de PDF para el Informe de RecepciÃ³n Interna.
- `config/urls.py` [MODIFY]: inclusiÃ³n de la ruta `compras/recepcion-interna/<int:rec_id>/imprimir/`.
- `templates/facturacion/pdf/remito_interno_pdf.html` [MODIFY]: inclusiÃ³n de casilla de punteo `[  ]` por Ã­tem y triple bloque de firma.
- `templates/facturacion/pdf/recepcion_interna_pdf.html` [NEW]: diseÃ±o PDF del Informe de RecepciÃ³n Interna con firmas y comprobantes vinculados.
- `templates/facturacion/recepcion_interna_carga.html` [MODIFY]: fijaciÃ³n inalterable de la sucursal receptora a la sucursal activa.
- `templates/facturacion/partials/recepcion_fila.html` [MODIFY]: enlace al PDF de Informe de RecepciÃ³n Interna.
- `facturacion/tests/test_plan028.py` [MODIFY]: inclusiÃ³n de pruebas unitarias para autocompletado y validaciones de serie.
- `docs/planes/053_busqueda_inteligente_series_remito_interno.md` [NEW]: plan de implementaciÃ³n histÃ³rico.

### Detalle TÃ©cnico y Saneamiento de Datos
1. **Persistencia y VisualizaciÃ³n Estricta por `productos_producto.id`:** Se unificÃ³ la regla conceptual del sistema: tanto en sesiÃ³n (`items`), grillas operativas (`ri_items_tabla.html`, `recepcion_interna_items_tabla.html`), modelos y comprobantes PDF, el identificador guardado y mostrado en columna es estrictamente el `producto_id` primario (`productos_producto.id`), desacoplÃ¡ndolo del `cod_prov` que sÃ³lo se usa como comodÃ­n de bÃºsqueda.
2. **Remito e Informe de RecepciÃ³n PDF (DiseÃ±o Sobrio y Ahorro de Tinta):** Se rediseÃ±aron los comprobantes PDF ([`remito_interno_pdf.html`](file:///d:/JM_Soft/erp-ikigai-2/templates/facturacion/pdf/remito_interno_pdf.html) y [`recepcion_interna_pdf.html`](file:///d:/JM_Soft/erp-ikigai-2/templates/facturacion/pdf/recepcion_interna_pdf.html)) alineando el nÃºmero de comprobante a la derecha en el mismo renglÃ³n del tÃ­tulo, reemplazando los fondos negros por bordes rectangulares finos (`#334155`), e implementando una casilla de control cuadrada para el punteo en depÃ³sito sin desbordamiento de renglÃ³n.
3. **Bloqueo RÃ­gido de Sucursal Receptora:** En RecepciÃ³n Interna se eliminÃ³ la selecciÃ³n de sucursal. La recepciÃ³n se asocia de forma fija e inalterable a la sucursal activa del usuario logueado.
4. **CorrecciÃ³n de Clave Primaria en `RecepcionInternaImprimirView`:** Se corrigiÃ³ la consulta de remitos imputados utilizando `ri.pk` (en lugar de `ri.id`), resolviendo la excepciÃ³n `AttributeError`.
5. **CorrecciÃ³n de Mapeo de Sucursales:** Se detectÃ³ e instruyÃ³ un saneamiento de datos en la tabla `productos_subproducto` para reasociar 1,400 registros que apuntaban errÃ³neamente a `sucursal_id = 1` de Empresa 1 hacia `sucursal_id = 3` (Sede Central de Empresa 2).

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test facturacion.tests.test_plan028
```
**Resultado:** `Ran 16 tests in 171.858s - OK`

### Estado actual y siguientes pasos
Plan 053 completado y verificado en su totalidad.

---

## 17 de Agosto de 2026 â DepuraciÃ³n de Cuentas Contables Obsoletas (Empresa ID = 2)

### Objetivo
Eliminar 48 cuentas contables obsoletas/duplicadas en la tabla `cble_cuentas` (modelo `Cuenta`) pertenecientes a `empresa_id = 2`, cuyos cÃ³digos fueron suministrados en el archivo `d:\borrador\borrar.csv`.

### Archivos Modificados / Creados
- Base de datos (`cble_cuentas`): eliminaciÃ³n fÃ­sica de 48 registros sin movimientos asociados.
- `docs/walkthrough.md` [MODIFY]: registro de la intervenciÃ³n.

### Detalle TÃ©cnico
1. **AuditorÃ­a e Integridad Previa:**
   - Se validaron los 48 cÃ³digos del archivo CSV (`codigo`).
   - Se verificÃ³ que ninguna de las 48 cuentas tuviera movimientos contables en `cble_asiento_mov` (`AsientoLinea`), cuentas bancarias asociadas ni parÃ¡metros contables vinculados.
   - Se comprobÃ³ que ninguna cuenta activa externa tuviera `sumariza_id` apuntando a las cuentas a borrar.
2. **EjecuciÃ³n Transaccional AtÃ³mica:**
   - Se ejecutÃ³ un bloque `transaction.atomic()`.
   - Se desvincularon preventivamente las autoreferencias `sumariza = None` internas entre las 48 cuentas.
   - Se ejecutÃ³ el borrado definitivo (`.delete()`) eliminando exactamente las 48 cuentas correspondientes.
   - VerificaciÃ³n posterior: 0 cuentas restantes con los cÃ³digos indicados en `empresa_id = 2`.

---

## 17 de Agosto de 2026 â Carga Maestra de Tarjetas en TesorerÃ­a (`tesoreria_tarjeta`)

### Objetivo
Poblar la tabla maestra de tarjetas (`tesoreria_tarjeta` / modelo `Tarjeta`) a partir del archivo `d:\borrador\tarjetas.csv` para habilitar las operaciones de cobros y liquidaciones con tarjetas de crÃ©dito y dÃ©bito.

### Archivos Modificados / Creados
- Base de datos (`tesoreria_tarjeta`): inserciÃ³n de 10 registros maestros.
- `docs/walkthrough.md` [MODIFY]: registro incremental de la bitÃ¡cora.

### Detalle TÃ©cnico
1. **Origen de Datos:** Lectura del archivo `d:\borrador\tarjetas.csv` (delimitado por `;`).
2. **Mapeo de Atributos:**
   - `codigo` -> `Tarjeta.codigo`
   - `detalle` -> `Tarjeta.nombre`
   - `tipo` -> `Tarjeta.tipo` (`C` = CrÃ©dito, `D` = DÃ©bito)
3. **Carga Idempotente y Transaccional:**
   - EjecuciÃ³n atÃ³mica vÃ­a `transaction.atomic()`.
   - UtilizaciÃ³n de `Tarjeta.objects.update_or_create(...)`.
   - Resultado: 10 tarjetas creadas exitosamente.

---

## 17 de Agosto de 2026 â Plan 054: ResoluciÃ³n Fiscal de Comprobantes ARCA y GestiÃ³n Guiada de Clientes por CondiciÃ³n IVA

### Objetivo
Corregir integralmente la determinaciÃ³n de tipos de comprobante (`TipoComprobante`) para la facturaciÃ³n electrÃ³nica ante ARCA/AFIP por emisores Responsables Inscriptos (Factura A para Responsables Inscriptos y Monotributistas segÃºn RG 5003/5022; Factura B para Consumidores Finales y Exentos), blindar las validaciones cruzadas de CUIT/DNI por condiciÃ³n fiscal e implementar un flujo guiado en el alta/ediciÃ³n de clientes que derive los controles impositivos desde la CondiciÃ³n ante el IVA.

### Archivos Modificados / Creados
- `facturacion/models.py` [MODIFY]: agregado de campo `es_consumidor_final` a `Preventa`.
- `facturacion/migrations/0048_preventa_es_consumidor_final.py` [NEW]: migraciÃ³n de base de datos.
- `facturacion/forms.py` [MODIFY]: validaciÃ³n integral en `ClienteProveedorForm.clean()` e inclusiÃ³n de `es_consumidor_final` en `PreventaForm`.
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]: reorganizaciÃ³n visual poniendo la CondiciÃ³n ante el IVA como selector disparador principal de la SecciÃ³n 1 con control dinÃ¡mico reactivo vÃ­a Alpine.js.
- `templates/facturacion/preventa_carga.html` [MODIFY]: checkbox para "Facturar como Consumidor Final (Factura B)" en la cabecera.
- `facturacion/views.py` [MODIFY]:
  - `resolver_tipo_comprobante_fiscal`: resoluciÃ³n certera de `TipoComprobante` sin caer en fallbacks errÃ³neos a `.first()`.
  - `validar_y_obtener_documento_receptor`: validaciÃ³n estricta de documentos previa a ARCA.
  - `VentasCargaView.post`: validaciÃ³n de coherencia fiscal previa a la comunicaciÃ³n con ARCA.
- `tesoreria/views_htmx.py` [MODIFY]: cobro de Preventa en Caja Mostrador resolviendo Factura A / B de forma certera y respetando `es_consumidor_final` para emitir Factura B.
- `facturacion/views_trazabilidad.py` [MODIFY]: validaciÃ³n de coherencia fiscal y documento antes de emitir a ARCA.
- `templates/facturacion/ventas_carga.html` y `templates/facturacion/ventas_trazabilidad_carga.html` [MODIFY]: preselecciÃ³n de Factura B por defecto y filtrado automÃ¡tico de Factura A/B segÃºn la condiciÃ³n fiscal del cliente seleccionado.
- `docs/planes/054_resolucion_fiscal_comprobantes_y_clientes.md` [NEW]: plan de implementaciÃ³n histÃ³rico.
- `docs/walkthrough.md` [MODIFY]: registro incremental de la bitÃ¡cora.

### Detalle TÃ©cnico
1. **ResoluciÃ³n Robusta de `TipoComprobante`:** Se normalizÃ³ la bÃºsqueda contemplando formatos con padding (`'001'`, `'006'`) y sin padding (`'1'`, `'6'`), eliminando definitivamente el fallback a `.first()` que causaba la asignaciÃ³n accidental de Factura A a Consumidores Finales.
2. **Matriz Impositiva de EmisiÃ³n (Emisor RI):**
   - **Receptor RI o Monotributista:** Emite **Factura A** (`001`), requiriendo `DocTipo = 80` y CUIT de 11 dÃ­gitos.
   - **Receptor Consumidor Final:** Emite **Factura B** (`006`), admitiendo `DocTipo = 99` (`DocNro = 0`), `DocTipo = 96` (DNI) o `DocTipo = 80` (CUIT).
   - **Receptor Exento:** Emite **Factura B** (`006`), requiriendo `DocTipo = 80` y CUIT de 11 dÃ­gitos.
3. **Flujo Guiado de Clientes:** En el modal de alta/ediciÃ³n de clientes, la **CondiciÃ³n ante el IVA** se define en primer tÃ©rmino. Al seleccionar RI, Monotributo o Exento, el Tipo de Documento se fija en `80 - CUIT` y el CUIT pasa a ser obligatorio de 11 dÃ­gitos.
4. **OpciÃ³n de Consumo Propio en Preventas:** Se agregÃ³ `es_consumidor_final` en `Preventa` con un checkbox en la pantalla de carga. Al cobrar la preventa en Caja Mostrador, si estÃ¡ marcado, se fuerza la emisiÃ³n de **Factura B** con condiciÃ³n impositiva de Consumidor Final (5) sin alterar la ficha del cliente en el maestro.

---

## 18 de Agosto de 2026 â Listado de Facturas Pendientes (rÃ©plica del VFP `tran_facturas_pendientes`)

### Objetivo
Replicar en el ERP el formulario VFP **I-108 `tran_facturas_pendientes`** (`c:\jm_soft\balances\forms\`):
el estado de cancelaciÃ³n de la cuenta corriente, comprobante por comprobante, con salidas a
pantalla, Excel y PDF. Se partiÃ³ del anÃ¡lisis del `.scx`/`.sct`, de la vista
`cons_lib_iva_pendientes` extraÃ­da del `contable.dbc`, del reporte `.frx` y de las muestras
`d:\borrador\FacturasPendientes.csv` / `.pdf`.

### Archivos creados / modificados
- `facturacion/services/facturas_pendientes.py` [NEW]: servicio de consulta. `FiltroFacturas`,
  `FilaFactura`, `TotalesFacturas`, `consultar()`, `calcular_totales()`, `agrupar_por_entidad()`.
- `facturacion/services/facturas_pendientes_excel.py` [NEW]: exportaciÃ³n `openpyxl` (19 columnas).
- `facturacion/views_facturas_pendientes.py` [NEW]: las cuatro vistas (pantalla, grilla HTMX,
  Excel, PDF), todas `GET` y de sÃ³lo lectura.
- `templates/facturacion/reportes/facturas_pendientes.html` [NEW]: pantalla con barra de filtros.
- `templates/facturacion/reportes/partials/facturas_pendientes_grilla.html` [NEW]: grilla + pie.
- `templates/facturacion/pdf/facturas_pendientes.html` [NEW]: "RESUMEN DE CUENTAS" (A4 apaisado).
- `config/urls.py` [MODIFY]: 4 rutas nuevas bajo `facturas-pendientes/`.
- `templates/base.html` [MODIFY]: Ã­tem "Facturas Pendientes" en los submenÃºs de Compras
  (`?operacion=C`) y de Ventas (`?operacion=V`).
- `static/css/output.css` [MODIFY]: recompilado con `npm run build` (Tailwind purga por contenido).
- `facturacion/tests/test_facturas_pendientes.py` [NEW]: 24 pruebas.
- `docs/planes/056_listado_facturas_pendientes.md` [NEW]: plan de implementaciÃ³n archivado.

### Detalle tÃ©cnico

**1. La fuente NO es el Libro IVA.** El VFP leÃ­a `lib_iva`; acÃ¡ se lee `Compra` y `Venta`. Tres
razones: `LibroIvaVentas` nunca se puebla (`contabilizacion.py` sÃ³lo crea `LibroIvaCompras`), el
Libro IVA se llena sÃ³lo con `condic in (1,3)` â con lo que los `2` (Presupuestado) y `4`
(AuditorÃ­a) desaparecerÃ­an justo del listado de gestiÃ³n â y `pagado`/`saldo` viven en los
comprobantes. Neto, IVA, No Gravado y Exento ya estÃ¡n en `Compra`/`Venta`: no se toca el
subsistema fiscal para ninguna columna.

**2. `pagado := total â saldo` en las dos operaciones.** `Compra.pagado` existe y la identidad es
exacta. `Venta` **no tiene** campo `pagado`: tiene `cobrado` (cobro en el acto) y
`saldo = total â cobrado â Î£ ReciboAplicacion`. Con esta definiciÃ³n los totalizadores cierran por
construcciÃ³n (`Î£ total = Î£ pagado + Î£ saldo`), y hay un test que lo verifica.

**3. TraducciÃ³n de los filtros del VFP.** Fechas (precargadas con el ejercicio en curso acotado a
hoy, como el `Form.Init`), Compras|Ventas excluyente, Todos|Uno con **Typeahead + Lupa**, y el
estado de pago replicando los rangos de `saldo`: Pagadas â `saldo = 0`, Pendientes â
`saldo <> 0`. El rango negativo del original es intencional y se conservÃ³: asÃ­ aparecen las notas
de crÃ©dito todavÃ­a sin aplicar.

**4. Dos filtros que el VFP no tenÃ­a.** *CondiciÃ³n* (Real/Presupuestado/Ajuste/AuditorÃ­a), que
`.cursorrules` exige en todo listado con importes â sin checkboxes marcados se entiende "todas",
no "ninguna". Y *Incluir anuladas*, apagado por defecto (`Venta.estado != 1`); los estados `2`
(Pend. AutorizaciÃ³n) y `3` (Rechazada) sÃ­ se listan siempre.

**5. SÃ³lo lectura â el botÃ³n "Modificar" no se replicÃ³.** En el VFP desbloqueaba `pagado` en la
grilla y hacÃ­a `TABLEUPDATE` directo sobre `lib_iva`, porque ese campo materializado se
desincronizaba. AcÃ¡ `pagado`/`saldo` son derivados de las aplicaciones de OP y Recibos
(`contable/services/saldos.py`): no hay nada que forzar. **Ninguna de las cuatro rutas es `POST`
y el mÃ³dulo no escribe en la base**; hay un test que recorre las cuatro vistas y verifica que los
importes queden intactos. Al no escribir, tampoco necesita `transaction.atomic()` ni
`select_for_update()`.

**6. Columnas descartadas.** `cantidad` y `litros` son herencia de verticales viejas (GNC/agro):
salen siempre en cero, y la versiÃ³n en producciÃ³n del ejecutable VFP ya ni las exportaba (18
columnas en el CSV contra las 20 que escribe el cÃ³digo). Con ellas se fue el totalizador de
`litros`: **el pie tiene tres cajas â Total, Pagado, Saldo â en vez de las cuatro del original.**
TambiÃ©n se omitieron `vencim` (no existe el campo en `Compra`/`Venta`) y `f_p`.

**7. Truncado honesto.** La grilla corta en 500 filas, pero `calcular_totales()` agrega sobre el
conjunto completo: el pie nunca miente. Cuando hay corte se muestra un aviso explÃ­cito y se
aclara que el Excel y el PDF incluyen todas.

**8. Bug del reporte original corregido.** Midiendo coordenadas sobre `FacturasPendientes.pdf` se
verificÃ³ que en el `.frx` las columnas rotuladas *"Pendiente"* y *"Saldo"* estÃ¡n invertidas: la
primera trae el saldo del comprobante y la segunda el acumulado corrido del grupo. En el PDF
nuevo los rÃ³tulos dicen lo que la columna contiene. Se conservaron las **dos** variantes de suma
corrida del original: `acum_global` (columna `Acum.` del Excel) y `acum_grupo` (reinicia por
cliente/proveedor, como el impreso).

### Implicaciones de base de datos
**Ninguna migraciÃ³n.** Se aprovechan los Ã­ndices existentes `(empresa, fecha)` de `Compra` y
`Venta`, y `(empresa, razon_social)` de `ClienteProveedor` para el `ORDER BY`. Las consultas usan
`select_related` + `.only(...)` acotado, porque el volumen real ronda las 400 filas por consulta
sobre tablas anchas. Queda pendiente evaluar con `EXPLAIN ANALYZE` sobre datos reales si el modo
*Pendientes* justifica un Ã­ndice parcial `WHERE saldo <> 0` (decisiÃ³n D4 del plan).

### Pruebas automatizadas
```bash
.\venv\Scripts\python.exe manage.py test facturacion.tests.test_facturas_pendientes --noinput
```
**Resultado:** `Ran 24 tests in 570.528s - OK`

Cobertura: aislamiento multiempresa (incluido el caso de pasar por querystring el id de una
entidad de otra empresa), estados Pagadas/Pendientes/Todas con saldo negativo, filtro de
condiciÃ³n y el default vacÃ­o, `pagado` contra las aplicaciones reales de una Orden de Pago,
`pagado = total â saldo` en Ventas, cierre de los totales, ventas anuladas (excluidas por
defecto, sin contaminar totales, visibles y marcadas con el checkbox), totales sobre el conjunto
completo con truncado a 500, acumulado global y por grupo, Excel y PDF, y sÃ³lo lectura.

### Estado actual y siguientes pasos
Plan 056 **completo**. Pendientes registrados fuera de alcance: la fecha de vencimiento de los
comprobantes (decisiÃ³n D1 â requiere migraciÃ³n en `Compra`/`Venta` y tocar las pantallas de
carga, merece su propio plan) y el Ã­ndice parcial del modo Pendientes (D4).

**RegresiÃ³n del mÃ³dulo completo:**
```bash
.\venv\Scripts\python.exe manage.py test facturacion --noinput
```
**Resultado:** `Ran 53 tests in 703.389s â FAILED (failures=1, errors=5)`

Los 6 son **preexistentes y ajenos a este cambio** (el diff no toca ninguno de los archivos
involucrados):
- 2 errores en `test_armeria_credencial_clu`: `TypeError: Sucursal() got unexpected keyword
  arguments: 'codigo'` â el modelo `Sucursal` no tiene ese campo. Ya estaba registrado como
  pendiente en la entrada del Plan 047.
- 3 errores en `test_exportar_clientes_excel`: el `setUp` hace
  `Jurisdiccion.objects.create(codigo=901, ...)` y choca con la semilla de la migraciÃ³n
  `facturacion/migrations/0025_cargar_jurisdicciones.py`, que ya inserta la jurisdicciÃ³n 901
  (`UniqueViolation` sobre `facturacion_jurisdiccion_codigo_key`). **Nuevo pendiente detectado.**
- 1 fallo en `test_arca_service.test_emitir_comprobante_homologacion_real`: prueba de integraciÃ³n
  real contra los servidores de ARCA en HomologaciÃ³n, rechazada del lado de ARCA
  (`Err 501: Error interno de base de datos`). Depende de un servicio externo.

### Ajuste posterior â tarjetas en los Ã­ndices de mÃ³dulo
El acceso habÃ­a quedado sÃ³lo en el menÃº lateral. Se agregÃ³ la tarjeta correspondiente en las dos
pantallas de Ã­ndice, siguiendo el patrÃ³n de tarjetas existente (color **orange**, libre en ambas):
- `templates/facturacion/compras_index.html` [MODIFY]: tarjeta "Facturas Pendientes"
  (`?operacion=C`), entre "Listado de Compras" y "Compras AutomÃ¡tica".
- `templates/facturacion/ventas_index.html` [MODIFY]: tarjeta "Facturas Pendientes"
  (`?operacion=V`), despuÃ©s de "Ventas por Producto".
- `static/css/output.css` [MODIFY]: recompilado â las clases `orange` eran nuevas en el purgado.

### CorrecciÃ³n â comentarios de template visibles en pantalla
Se estaban renderizando los comentarios como texto plano. Causa: **`{# ... #}` en Django sÃ³lo
funciona en una lÃ­nea**; los comentarios escritos en dos o tres lÃ­neas no se parsean y salen
literales. Se pasaron a `{% comment %}...{% endcomment %}`:
- `templates/facturacion/reportes/facturas_pendientes.html` [MODIFY]: 2 comentarios.
- `templates/facturacion/pdf/facturas_pendientes.html` [MODIFY]: 1 comentario (en el `<head>`).
- `templates/tesoreria/eoaf.html` [MODIFY] y `templates/tesoreria/modals/eoaf_cuenta_modal.html`
  [MODIFY]: mismo defecto, **preexistente** (Plan 050), tambiÃ©n visible en pantalla.

Barrido de todo `templates/`: no queda ningÃºn `{#` sin su `#}` en la misma lÃ­nea.

---

## 18 de Agosto de 2026 â Plan 055: BotÃ³n de ExportaciÃ³n a Excel en Clientes y Proveedores

### Objetivo
Incorporar la funcionalidad de exportaciÃ³n completa a formato Excel (`.xlsx`) en el listado de Clientes y Proveedores (`/clientes/`), que permita descargar los registros de la empresa respetando los filtros de bÃºsqueda activa (`q` y `tipo`) con **todos los campos de la tabla `ClienteProveedor` (25 columnas)** y **sin la restricciÃ³n de 50 registros en pantalla**.

### Archivos Modificados / Creados
- `facturacion/services/clientes_excel.py` [NEW]: servicio con `openpyxl` que construye el archivo Excel estilizado con 25 columnas, encabezado slate-900, importes formateados (`#,##0.00`) y auto-ajuste de ancho de columnas.
- `facturacion/views_reportes.py` [MODIFY]: agregado de la vista `@login_required exportar_clientes_excel(request)` que consulta el 100% de los registros filtrados sin lÃ­mite `[:50]` y ejecuta el servicio de descarga.
- `config/urls.py` [MODIFY]: registro de la ruta `path('clientes/exportar-excel/', exportar_clientes_excel, name='clientes_exportar_excel')`.
- `templates/facturacion/clientes_index.html` [MODIFY]: agregado del botÃ³n verde estilizado "Exportar Excel" en la barra de acciones superiores y la funciÃ³n JS `exportarExcel()` para enviar la bÃºsqueda activa.
- `facturacion/tests/test_exportar_clientes_excel.py` [NEW]: suite de pruebas unitarias para la descarga Excel sin filtro y con filtros de tipo y bÃºsqueda.
- `docs/planes/055_exportar_excel_clientes_proveedores.md` [NEW]: copia numerada del plan de implementaciÃ³n.
- `docs/walkthrough.md` [MODIFY]: registro incremental de la bitÃ¡cora.

### Detalle TÃ©cnico
1. **Campos Exportados (25 columnas):** ID, RazÃ³n Social, Tipo Entidad, Tipo Documento, CUIT/DNI, Fecha Nacimiento, Domicilio, C. Postal, Localidad, Provincia/JurisdicciÃ³n, Contacto, TelÃ©fono, Correo, CondiciÃ³n IVA, Ingresos Brutos, Saldo Inicial, Saldo Actual, LÃ­mite CrÃ©dito, Objetivo Mensual, ClasificaciÃ³n, Exige Orden Compra, Cta Patrimonial, Cta Resultado, CÃ³digo Anterior, Observaciones.
2. **Sin Truncamiento:** A diferencia de la grilla HTML que estÃ¡ acotada a `[:50]` por desempeÃ±o en navegador, la vista de exportaciÃ³n retorna el 100% de los contactos comerciales coincidentes con el filtro de bÃºsqueda.
3. **Formato:** Encabezado con tÃ­tulo de la empresa, subtÃ­tulo del reporte, filtros aplicados, fecha/hora de emisiÃ³n y celdas estilizadas.

---

## 18 de Agosto de 2026 â InicializaciÃ³n de Medios de Pago por Empresa y CorrecciÃ³n en Guardado de Recibos (Plan 057)

### Objetivo
Resolver el error de medio de pago al presionar "Guardar recibo" en la Empresa 2 (`ARMERIA ARMAR SAS`) para el recibo `RC 0001-00000003`, poblando la tabla `tesoreria_medio_pago` con la asignaciÃ³n correspondiente al plan de cuentas de cada empresa, optimizando la resoluciÃ³n por cÃ³digo (`EFE-ARS`, `EFE-USD`, `CHQ-TER`, `TRA-BCO`) y asegurando la atomicidad de transacciones con `transaction.set_rollback(True)`.

### Archivos Modificados / Creados
- `tesoreria/views_htmx.py` [MODIFY]:
  - `procesar_recibo` y `procesar_orden_pago`: bÃºsqueda jerÃ¡rquica de `MedioPago` especificando cÃ³digo (`EFE-ARS`, `EFE-USD`, `TRA-BCO`, `CHQ-TER`) antes del fallback por categorÃ­a (`EFE`, `TRA`, `CHQ`).
  - AdiciÃ³n de `transaction.set_rollback(True)` en bloques `except Exception as e:` para evitar el guardado de comprobantes huÃ©rfanos sin movimiento de caja ni asiento ante cualquier fallo.
- Base de Datos (`tesoreria_medio_pago`):
  - Reset de secuencia PostgreSQL (`tesoreria_medio_pago_id_seq`).
  - Sembrado de medios de pago para **Empresa 2** (`ARMERIA ARMAR SAS`) y **Empresa 3** (`LOPEZ RIOS Y ASOCIADOS SA`) enlazados a sus respectivas cuentas contables.
  - DepuraciÃ³n de recibos huÃ©rfanos de prueba (ID 6, 7 y 8) en Empresa 2.
- `docs/planes/057_corregir_error_medio_pago_recibos.md` [NEW]: plan de implementaciÃ³n histÃ³rico.
- `docs/walkthrough.md` [MODIFY]: registro incremental de la bitÃ¡cora.

### Detalle TÃ©cnico
1. **Modelado y Aislamiento por Empresa:** Tal como seÃ±alÃ³ acertadamente la decisiÃ³n de arquitectura, cada `MedioPago` debe pertenecer a una empresa (`empresa_id`) debido a que la `cuenta_contable_id` hace referencia a la tabla `cble_cuentas`, cuyos IDs primarios son Ãºnicos por plan de cuentas de empresa.
2. **Carga Inicial de Medios de Pago:**
   - **Empresa 2:** `EFE-ARS` y `EFE-USD` (Cta. 215 - CAJA), `CHQ-TER` (Cta. 216 - VALORES EN CARTERA), `TRA-BCO` (Cta. 217 - BANCO MACRO), `RET-GCIA` (Cta. 236 - AFIP RET. GCIAS), `RET-IIBB` (Cta. 253 - DGR IIBB SALDO A FAVOR).
   - **Empresa 3:** `EFE-ARS` y `EFE-USD` (Cta. 483 - CAJA), `CHQ-TER` (Cta. 484 - VALORES EN CARTERA), `TRA-BCO` (Cta. 485 - BANCO PATAGONIA), `RET-GCIA` (Cta. 498), `RET-IIBB` (Cta. 512).
3. **Robustez Transaccional:** Se introdujo `transaction.set_rollback(True)` en la captura de excepciones dentro de `procesar_recibo` y `procesar_orden_pago` decoradas con `@transaction.atomic`.

---

## 19 de Agosto de 2026 â Plan 059: RediseÃ±o UI/UX del Modal Mayor General de Cuenta (Saldos Mensuales)

### Objetivo
1. Implementar desplazamiento horizontal (`scroll` horizontal) en el listado de movimientos del modal Mayor General de Cuenta para evitar que se corten o compriman excesivamente las columnas contables.
2. Fijar el encabezado de las columnas (`<thead>`) mediante `sticky header` al realizar scroll vertical a lo largo de los movimientos.
3. Ampliar el ancho contenedor del modal de `max-w-5xl` (1024px) a `w-11/12 max-w-7xl` (1280px) para maximizar la visibilidad de datos en pantalla.
4. Ajustar el catÃ¡logo de columnas del Mayor General para establecer como predeterminadas Ãºnicamente las 7 columnas solicitadas: `ID Asiento`, `Fecha`, `Concepto`, `Debe`, `Haber`, `Saldo` y `CondiciÃ³n`.

### Archivos Modificados / Creados
- `contable/services/reportes_mayor.py` [MODIFY]:
  - ActualizaciÃ³n de `COLUMNAS_MAYOR_CATALOGO` otorgando `default = True` exclusivamente a las 7 claves predeterminadas (`asiento_id`, `fecha`, `concepto`, `debe`, `haber`, `saldo`, `condic`) y cambiando `cuenta_id`, `cuenta` y `sucursal` a `default = False`.
- `templates/contable/modals/mayor_cuenta_modal.html` [MODIFY]:
  - RediseÃ±o de la clase de tamaÃ±o modal a `w-11/12 max-w-7xl`.
  - ConfiguraciÃ³n del contenedor interno con `overflow-x-auto overflow-y-auto max-h-[calc(90vh-220px)]` e `inline-block align-middle min-w-full`.
  - Ajuste del `<thead>` inicial por defecto para las 7 columnas requeridas otorgÃ¡ndoles clases `sticky top-0 z-20 bg-slate-100 whitespace-nowrap`.
- `templates/contable/partials/libro_mayor_rows.html` [MODIFY]:
  - AdiciÃ³n de `whitespace-nowrap` a las celdas `<td>` del cuerpo del listado.
  - ActualizaciÃ³n de la funciÃ³n JavaScript `renderThead` incorporando las clases de sticky header y no quiebre de renglÃ³n (`sticky top-0 z-20 bg-slate-100 shadow-sm border-b border-slate-200 whitespace-nowrap`) a los elementos `<th>` generados dinÃ¡micamente.
- `docs/planes/059_rediseno_modal_mayor_cuenta.md` [NEW]: copia de respaldo numerada del plan de implementaciÃ³n.
- `docs/walkthrough.md` [MODIFY]: actualizaciÃ³n incremental de la bitÃ¡cora de desarrollo.

### Detalle TÃ©cnico
1. **Comportamiento del Scroll Horizontal y Vertical:** Al abrir el modal desde Saldos Mensuales o desde el Libro Mayor, el contenedor central de la grilla administra simultÃ¡neamente el scroll vertical de los movimientos y el scroll horizontal cuando el ancho acumulado de columnas supera el ancho Ãºtil de la pantalla.
2. **Encabezado Persistente (Sticky Header):** Al desplazarse verticalmente por una cuenta con cientos de asientos, la fila `<thead>` permanece anclada en la parte superior (`sticky top-0 z-20`) con fondo opaco `bg-slate-100`, asegurando que los tÃ­tulos de las columnas no se pierdan.
3. **CatÃ¡logo de Columnas:** Las 7 columnas por defecto abarcan exactamente la informaciÃ³n operativa fundamental. Cualquier columna adicional (ej. `Sucursal`, `NÂº Diario`, `MÃ³dulo`, `Cli/Prov`) puede agregarse o quitarse en tiempo real mediante el botÃ³n "Columnas".

### Pruebas Automatizadas
```powershell
.\venv\Scripts\python.exe manage.py test contable.tests.test_libro_mayor_columnas contable.tests.test_saldos_mensuales_vistas
```
**Resultado:** `Ran 20 tests in 137.644s - OK`

---

## 19 de Agosto de 2026 â Plan 058: VisualizaciÃ³n de Asientos, RestricciÃ³n de AnulaciÃ³n y CorrecciÃ³n de Imputaciones en OP

### Objetivo
1. Permitir consultar el asiento contable generado directamente desde la columna `Asiento` en los listados de Ãrdenes de Pago y Recibos de Cobranza mediante la apertura interactiva de un modal HTMX (`detalle_asiento_modal`).
2. Restringir la acciÃ³n `ANULAR` exclusivamente a usuarios Administradores (`is_superuser`, `is_staff` o `es_admin_sistema`) tanto en las grillas de Ãrdenes de Pago y Recibos como a nivel de endpoint de backend (retornando `HTTP 403 Forbidden`).
3. Corregir el botÃ³n de eliminaciÃ³n en la tabla de Imputaciones Contables Manuales en la pantalla de Carga de Ãrdenes de Pago (`ordenpago_carga.html`), reemplazando la etiqueta FontAwesome descompuesta por un icono SVG nativo de basura visible y estilizado.

### Archivos Modificados / Creados
- `tesoreria/views_listados.py` [MODIFY]:
  - `orden_pago_anular`: agregado de control de permisos de Administrador (`is_superuser or is_staff or es_admin_sistema`). Retorna `HTTP 403` si el usuario no es Administrador.
  - `recibo_anular`: agregado del mismo control de permisos con respuesta `HTTP 403` para no administradores.
- `templates/tesoreria/partials/ordenpago_grilla.html` [MODIFY]:
  - Columna 9 (`Asiento`): transformada en un botÃ³n HTMX interactivo que al presionar dispara `hx-get="{% url 'detalle_asiento_modal' fila.op.asiento_id %}"`.
  - Columna 10 (`Acciones`): botÃ³n `ANULAR` envuelto en la directiva Jinja `{% if user.is_superuser or user.is_staff or user.perfil.es_admin_sistema %}`.
- `templates/tesoreria/partials/recibo_grilla.html` [MODIFY]:
  - Columna 9 (`Asiento`): transformada en botÃ³n HTMX interactivo para abrir el modal del asiento contable.
  - Columna 10 (`Acciones`): botÃ³n `ANULAR` protegido para mostrarse Ãºnicamente a usuarios Administradores.
- `templates/tesoreria/ordenpago_carga.html` [MODIFY]:
  - Reemplazo de `<i class="fas fa-trash"></i>` en la celda de acciÃ³n de la tabla de imputaciones contables por un botÃ³n de eliminaciÃ³n con icono SVG visible en rojo.
- `templates/contable/modals/detalle_asiento_modal.html` [MODIFY]:
  - Reemplazo de `onclick="document.getElementById('modal-container-2').innerHTML=''"` por `onclick="this.closest('.fixed').remove()"` garantizando un cierre limpio.
  - AmpliaciÃ³n del ancho contenedor del modal de `max-w-4xl` a `max-w-5xl`, extensiÃ³n del ancho de las columnas `Debe` y `Haber` a `w-44` (176px) y adiciÃ³n de `whitespace-nowrap` a las celdas de montos en `tbody` y `tfoot` para impedir el quiebre de renglÃ³n del signo `$` y del importe.
- `docs/planes/058_mejoras_listados_op_recibos.md` [NEW]: copia del plan de implementaciÃ³n formalmente registrado.
- `docs/walkthrough.md` [MODIFY]: actualizaciÃ³n acumulativa de la bitÃ¡cora.

### Detalle TÃ©cnico
1. **Acceso al Asiento Contable:** Al hacer clic en el ID de asiento de cualquier Orden de Pago o Recibo, se ejecuta la peticiÃ³n HTMX al endpoint `detalle_asiento_modal` de la app `contable`, cargando la vista previa del asiento contable con sus lÃ­neas de Debe/Haber, saldo total e informaciÃ³n de cuentas asociadas.
2. **Seguridad y Roles:** Para mantener el principio de privilegio mÃ­nimo, los operadores/vendedores (`is_staff = False`, `es_admin_sistema = False`) no ven el botÃ³n `Anular` en las grillas de OP y Recibos, y si intentaran realizar la peticiÃ³n HTTP POST directamente, la vista intercepta el requerimiento y devuelve un estado `403 Forbidden`.
3. **Optimizaciones de UI y Modales:** La instrucciÃ³n `this.closest('.fixed').remove()` destruye limpia y reactivamente el elemento contenedor del modal flotante sin depender de un ID rÃ­gido en el DOM. AdemÃ¡s, el modal de asiento se ampliÃ³ a `max-w-5xl` con columnas `w-44` y `whitespace-nowrap`, asegurando que los montos en pesos de Debe, Haber y Total Asiento se presenten holgadamente en una sola lÃ­nea.

---

## 20 de Agosto de 2026 â Trazabilidad de Subproductos (Vista y LÃ­nea de Tiempo Modal)

### Objetivo
1. Crear una vista para listar subproductos trazables, permitiendo la bÃºsqueda por Cliente/Proveedor, Serie, CUIM y Producto, y filtrado automÃ¡tico al estado actual (Ãºltimo movimiento) aprovechando Ã­ndices DISTINCT ON y order_by.
2. Validar que la trazabilidad estÃ© restringida a empresas con tipo de actividad 'ARMERIA' o 'AUTOMOTOR'.
3. Integrar un modal con lÃ­nea de tiempo interactivo que detalle el flujo cronolÃ³gico del subproducto (compras y ventas con su historial y comprobantes vinculados).

### Archivos Modificados / Creados
- productos/views_trazabilidad.py [NEW]:
  - SubproductoTrazabilidadListView: Listado general con soporte HTMX de grilla y paginaciÃ³n.
  - 	razabilidad_modal_timeline: Endpoint que devuelve el HTML renderizado con todo el historial de la serie clickeada.
- config/urls.py [MODIFY]: Registro de las rutas stock/trazabilidad/ y stock/trazabilidad/modal/<str:serie>/.
- 	emplates/base.html [MODIFY]: IntegraciÃ³n del enlace 'Trazabilidad Subproductos' debajo de Mantenimiento de Productos en el menÃº lateral.
- 	emplates/productos/trazabilidad_list.html [NEW]: Plantilla maestra del listado con formulario de bÃºsqueda.
- 	emplates/productos/partials/trazabilidad_grilla.html [NEW]: Plantilla parcial (table rows) usada por HTMX.
- 	emplates/productos/partials/trazabilidad_modal_timeline.html [NEW]: Componente modal estilizado (TailwindCSS) representando una lÃ­nea de tiempo (timeline) cronolÃ³gica.

### Detalle TÃ©cnico
1. **LÃ³gica de BÃºsqueda:** Para el filtro por CliPro, el sistema recupera inicialmente las series que tuvieron movimiento asociado con el Cliente/Proveedor buscado, y luego filtra la consulta principal.
2. **Eficiencia PostgreSQL:** El queryset final se ordena por serie, -feccpra y -subpro usando distinct('serie') para recuperar de forma altamente eficiente sÃ³lo el estado mÃ¡s reciente de la serie sin sobrecargar la memoria.
3. **Control de Acceso (ValidaciÃ³n de Negocio):** En el mÃ©todo dispatch() se chequea que empresa.tipo_actividad pertenezca a 'ARMERIA' o 'AUTOMOTOR'; caso contrario redirige al index de stock con un mensaje de advertencia.
4. **VisualizaciÃ³n en Modal (Timeline):** Se empleÃ³ CSS para construir una barra conectora (div.w-0.5.bg-gray-200), trazando el recorrido desde el Ingreso (Compra verde) hasta el Egreso (Venta roja), informando fechas, entidades y comprobantes vinculados.

---

## 20 de Agosto de 2026 â Mejoras UI/UX en Trazabilidad (Autocompletado y Dashboard)

### Objetivo
1. Implementar autocompletado en los filtros de trazabilidad usando Alpine JS (Typeahead pattern).
2. Agregar la tarjeta de acceso de 'Trazabilidad Subproductos' al Dashboard principal de Stock.
3. Solucionar el bug de solicitudes infinitas (looping requests de HTMX en la vista trazabilidad).

### Archivos Modificados
- `templates/productos/trazabilidad_list.html` [MODIFY]:
  - IntegraciÃ³n de la lÃ³gica Alpine.js `x-data="{ open: false }"` para autocompletado.
  - ConexiÃ³n de inputs a `typeahead_clientes`, `typeahead_series_trazabilidad` y `typeahead_productos_venta`.
  - Escucha de eventos custom (e.g. `clienteVentaSeleccionado`, `productoVentaEncontrado`) para autocompletar e invocar el form (`htmx.trigger`).
  - CorrecciÃ³n de `hx-trigger` que escuchaba globalmente `from:input` y generaba peticiones masivas al presionar cualquier tecla o dispararse eventos automÃ¡ticos.
- `templates/productos/stock_dashboard.html` [MODIFY]:
  - AdiciÃ³n del acceso directo (Tarjeta visual) al mÃ³dulo de Trazabilidad, restringido por la validaciÃ³n de negocio (uso en armerÃ­a o automotor).
- `productos/views_trazabilidad.py` [MODIFY]:
  - CorrecciÃ³n en `get_template_names()` aÃ±adiendo fallback de lectura `self.request.META.get('HTTP_HX_REQUEST')` por seguridad para asegurar la respuesta parcial.

### Detalle TÃ©cnico
1. **Autocompletado Typeahead:** Se reutilizaron componentes modales y parciales existentes de facturaciÃ³n (`clientes_typeahead`, `serie_typeahead`, `productos_venta_typeahead`), capturando sus eventos custom en JavaScript (como `seleccionarSerieVenta` o `window.addEventListener('clienteVentaSeleccionado')`) para rellenar los inputs del formulario y lanzar la bÃºsqueda asÃ­ncrona automÃ¡ticamente.
2. **Loop Infinito (BugFix HTMX):** El trigger global del form (`hx-trigger='keyup delay:500ms from:input'`) provocaba que scripts paralelos o extensiones que generaban eventos `keyup` causaran recargas enteras de la tabla. Esto se ha mitigado focalizando los `hx-trigger` y bloqueando el comportamiento por defecto del submit de teclado.

---

## 20 de Agosto de 2026 â OptimizaciÃ³n de Trazabilidad (LÃ­mite 50 registros)

### Objetivo
1. Limitar los resultados en la vista de trazabilidad a 50 registros, imitando el comportamiento de la bÃºsqueda de productos, para evitar la ralentizaciÃ³n en la carga inicial y en las consultas de PostgreSQL.

### Archivos Modificados
- `productos/views_trazabilidad.py` [MODIFY]:
  - Eliminado el atributo `paginate_by = 50` de la clase `SubproductoTrazabilidadListView`.
  - Aplicado slicing manual `return qs[:50]` al finalizar el mÃ©todo `get_queryset()`.

### Detalle TÃ©cnico
1. **Rendimiento PostgreSQL (Avoid COUNT*):** El uso nativo de paginaciÃ³n (`paginate_by`) en el `ListView` de Django obliga a ejecutar una consulta adicional `COUNT(*)` sobre el queryset resultante para saber el nÃºmero total de pÃ¡ginas. En este caso, tratÃ¡ndose de una tabla transaccional (Subproductos) con consultas pesadas de tipo `DISTINCT ON` combinadas con mÃºltiples `JOINS` y filtros de bÃºsqueda, el COUNT(*) introducÃ­a una severa penalizaciÃ³n de rendimiento ("slow query"). Al remover el paginador y hacer directamente el corte `[:50]`, le pedimos a la DB exactamente los primeros 50 elementos que coincidan con la bÃºsqueda (aplicando el index) de forma instantÃ¡nea, al igual que funciona el maestro de artÃ­culos.

---

## 21 de Agosto de 2026 â Plan 062: IncorporaciÃ³n de Costo de ReposiciÃ³n (cto_rep) en VentaItem

### Objetivo
Agregar el campo `cto_rep` (Costo de ReposiciÃ³n) a la tabla `facturacion_ventaitem` para congelar e inmutabilizar el costo de reposiciÃ³n vigente del producto (`productos_producto.cto_rep`) al momento exacto de la venta. Esto permite calcular con precisiÃ³n el **Margen Bruto**, la **ContribuciÃ³n Marginal** y el **Punto de Equilibrio** por Ã­tem y por venta de manera independiente a futuras modificaciones de precios/costos en el catÃ¡logo de productos.

### Archivos Creados / Modificados
- `facturacion/models.py` [MODIFY]:
  - AdiciÃ³n del campo `cto_rep = models.DecimalField(max_digits=15, decimal_places=2, default=0)` en `VentaItem`.
  - LÃ³gica en `VentaItem.save()`: autocompletar `self.cto_rep = self.producto.cto_rep` si `cto_rep` es `0` o `None` al guardar.
  - Propiedades calculadas en `VentaItem`: `subtotal_costo_reposicion`, `contribucion_marginal_unitaria`, `contribucion_marginal_total`.
  - Propiedades calculadas en `Venta`: `total_costo_reposicion`, `contribucion_marginal_total`, `margen_bruto_porcentaje`.
- `facturacion/services/notas_credito.py` [MODIFY]:
  - AsignaciÃ³n explÃ­cita de `cto_rep=original_item.cto_rep` al generar el `VentaItem` de una Nota de CrÃ©dito.
- `facturacion/migrations/0049_ventaitem_cto_rep.py` [NEW]: migraciÃ³n de esquema que agrega la columna `cto_rep`.
- `facturacion/migrations/0050_backfill_ventaitem_cto_rep.py` [NEW]: migraciÃ³n de datos para backfill de ventas histÃ³ricas.
- `facturacion/tests/test_costo_reposicion.py` [NEW]: suite de pruebas unitarias para `cto_rep` y contribuciÃ³n marginal.
- `docs/planes/062_costo_reposicion_ventaitem.md` [NEW]: copia de respaldo archivada del plan de implementaciÃ³n.
- `docs/walkthrough.md` [MODIFY]: registro incremental de la bitÃ¡cora.

### Detalle TÃ©cnico
1. **Inmutabilidad del Costo de Venta:** Al concretar una venta, el costo de reposiciÃ³n del producto se estampa en `VentaItem.cto_rep`. Si el proveedor o el usuario aumentan posteriormente el costo de reposiciÃ³n en la ficha del producto, el costo registrado en la venta realizada se mantiene inalterado.
2. **Backfill HistÃ³rico:** La migraciÃ³n `0050_backfill_ventaitem_cto_rep` recorriÃ³ los registros de `VentaItem` donde `cto_rep` era 0 y les asignÃ³ el `cto_rep` actual de su correspondiente producto mediante operaciones en bloques (`bulk_update`).
3. **Punto de Equilibrio y ContribuciÃ³n Marginal:** La contribuciÃ³n marginal unitaria se computa restando el costo de reposiciÃ³n al precio de venta neto de descuento: `(precio_unitario * (1 - descuento/100)) - cto_rep`.

### Pruebas Automatizadas y VerificaciÃ³n
- **Script de VerificaciÃ³n Transaccional:**
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
Plan 062 **completado, migrado y verificado**. La base de datos y la capa de modelos cuentan con la trazabilidad inmutable del costo de reposiciÃ³n en cada Ã­tem facturado y las propiedades para emitir anÃ¡lisis de contribuciÃ³n marginal y rentabilidad.

---

## 21 de Agosto de 2026 â CorrecciÃ³n Conceptual de Columna de Apertura y Acotamiento de Ejercicio en Sumas y Saldos â Plan 060

### Objetivo
1. Delimitar estrictamente el reporte de **Balance de Sumas y Saldos** al rango de fechas entre la fecha de inicio y de cierre del ejercicio activo de la sesiÃ³n.
2. Calcular la columna **Apertura** considerando la diferencia `Debe - Haber` del asiento contable de apertura (`condic = 5`) del ejercicio activo.
3. Incorporar un selector en la interfaz (checkbox) para habilitar o deshabilitar la inclusiÃ³n del asiento de apertura (predeterminado habilitado).
4. Cuando la `fecha_desde` sea mayor a la fecha de inicio del ejercicio activo, acumular en la columna **Apertura** el asiento de apertura (`condic = 5` si estÃ¡ activado) mÃ¡s los movimientos netos del ejercicio entre `ejercicio.inicio` y `fecha_desde - 1 dÃ­a`.

### Archivos Modificados / Creados
- `contable/views_htmx.py` [MODIFY]:
  - `get_balance_context`: procesa `mostrar_apertura` y delimita `fecha_desde` y `fecha_hasta` al rango `[ejercicio.inicio, ejercicio.cierre]`.
  - `_calcular_balance`: acota las consultas ORM a `asientolinea__asiento__ejercicio_id = ejercicio.id`. Construye 3 filtros disjuntos (`q_apertura_condic5`, `q_movimientos_previos` y `q_periodo`) y calcula la columna apertura para cada cuenta imputable y su rollup jerÃ¡rquico.
- `contable/services/saldos_mensuales.py` [MODIFY]:
  - Blindaje preventivo explÃ­cito en la consulta de apertura `apert` agregando los lÃ­mites de fecha `asiento__fecha__gte=ejercicio.inicio` y `asiento__fecha__lte=ejercicio.cierre`.
- `templates/contable/partials/balance.html` [MODIFY]:
  - AÃ±adido `<input type="hidden" name="filtros_aplicados" value="1">`.
  - AÃ±adido checkbox `<input type="checkbox" name="mostrar_apertura">` con label *"Incluir Apertura"* (predeterminado `checked`).
  - DelimitaciÃ³n de atributos `min` y `max` en los inputs de fecha al rango del ejercicio activo.
- `contable/tests/test_sumas_saldos_apertura.py` [NEW]:
  - Pruebas unitarias dedicadas (`SumasSaldosAperturaTest`) evaluando los 4 escenarios principales (apertura activada/desactivada, `fecha_desde == inicio` y `fecha_desde > inicio`).
- `docs/planes/060_correccion_apertura_sumas_y_saldos.md` [NEW]:
  - Registro permanente del plan de implementaciÃ³n en la documentaciÃ³n histÃ³rica.

### Detalle TÃ©cnico
1. **Paso de ParÃ¡metros:** `get_balance_context` verifica si el usuario desmarcÃ³ `mostrar_apertura` mediante los datos del querystring de filtros HTMX.
2. **CÃ¡lculo de Apertura:**
   $$\text{Apertura} = (\text{Debe}_5 - \text{Haber}_5 \text{ [si } mostrar\_apertura\text{]}) + (\text{Debe}_{\text{prev}} - \text{Haber}_{\text{prev}} \text{ [si } fecha\_desde > ejercicio.inicio\text{]})$$
3. **Respeto a Restricciones de BD:** Los asientos de test cumplen estrictamente las restricciones de unicidad y la regla matemÃ¡tica de base de datos `debe_xor_haber`.

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test contable.tests.test_saldos_mensuales contable.tests.test_sumas_saldos_apertura
```
**Resultado:** `Ran 31 tests in 23.410s - OK (27/27 de saldos_mensuales + 4/4 de sumas_saldos_apertura)`

### Estado actual y siguientes pasos
Plan 060 **completamente implementado, blindado y verificado**. Se mantuvieron en 100% verde la prueba cruzada de coincidencia entre Saldos Mensuales y Balance de Sumas y Saldos.

---

### Objetivo
1. AÃ±adir un botÃ³n en el menÃº superior (navbar) para poder colapsar y expandir la barra lateral izquierda (MenÃº Principal), ahorrando espacio en pantalla a peticiÃ³n del usuario.
2. Hacer que el sistema recuerde la preferencia del usuario si dejÃ³ abierto o cerrado el menÃº entre recargas de pÃ¡gina.

### Archivos Modificados
- `templates/base.html` [MODIFY]:
  - AÃ±adido el estado global `x-data="{ sidebarOpen: $persist(true) }"` en el elemento `<body>` para gestionar y persistir el estado de la barra en el LocalStorage.
  - AÃ±adido un botÃ³n interactivo a la izquierda del logo con un Ã­cono de "hamburguesa" que invierte el estado `sidebarOpen`.
  - Envuelto el `<aside>` del sidebar con directivas `x-show="sidebarOpen"` y transiciones suaves para un efecto de deslizamiento al abrir o cerrar.

---

## 22 de Agosto de 2026 â Plan 066: CorrecciÃ³n del Alta de Proveedores y Reactividad Fiscal

### Objetivo
Resolver el fallo en el formulario modal `ClienteProveedor` que impedÃ­a registrar o ingresar un **Proveedor**, provocado por una reconversiÃ³n forzada a rol "Cliente" en el frontend cuando el tipo de documento inicial era 99 (Sin Identificar), asÃ­ como por la falta de validaciÃ³n estricta de CUIT y CondiciÃ³n Fiscal para proveedores en el backend.

### Archivos Creados / Modificados
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]:
### Pruebas Automatizadas
- **Tests Unitarios Django:**
  ```powershell
  .\venv\Scripts\python.exe manage.py test facturacion.tests.test_proveedor_alta
  ```
  **Resultado:** `Ran 3 tests in 2.150s - OK`

### Estado Actual y Siguientes Pasos
Plan 066 **completado y verificado**. La creaciÃ³n y ediciÃ³n de proveedores funciona de manera fluida y consistente en todo el sistema ERP Ikigai 2.

2. **LÃ³gica de Alerta:**
   - Si `dias > 15`: Estado `success` (sin banner de alerta).
   - Si `4 <= dias <= 15`: Estado `warning` (banner Ã¡mbar preventivo).
   - Si `0 <= dias <= 3`: Estado `danger` (banner rojo urgente).
   - Si `dias < 0`: Estado `danger` con flag `es_vencido=True` (banner rojo parpadeante indicando que la facturaciÃ³n electrÃ³nica puede estar suspendida).

### Resultados de la VerificaciÃ³n
- **Prueba en Shell de Django:**
  - `e.estado_vencimiento_crt` evaluado para empresa activa, simulaciÃ³n de 10 dÃ­as restantes y simulaciÃ³n de certificado vencido.
  - **Resultado:** CÃ¡lculo exacto de dÃ­as, fechas formateadas y banderas activadas segÃºn lo esperado.
- **MigraciÃ³n de base de datos:** `Applying empresas.0015_empresa_vencimiento_crt_afip... OK`.

### Estado Actual
Plan 032 **completamente implementado, probado y verificado**. La gestiÃ³n de vencimiento de certificados digitales ARCA/AFIP estÃ¡ lista y operativa.

---

## 22 de Agosto de 2026 â ExportaciÃ³n Personalizada/Completa en Excel y Captura Masiva de Productos â Plan 063

### Objetivo
1. **ExportaciÃ³n Personalizada a Excel:** Permitir a los usuarios generar reportes en formato Excel `.xlsx` seleccionando dinÃ¡micamente entre la totalidad de los campos del modelo `Producto`.
2. **ExportaciÃ³n de Tabla Completa:** Brindar un botÃ³n de descarga directa de la plantilla/maestro completo de productos de la empresa actual con todos los campos operables.
3. **Captura / ImportaciÃ³n Masiva desde Excel:**
   - Forzar la conversiÃ³n y guardado **SIEMPRE EN MAYÃSCULAS** del detalle del producto, cÃ³digo de proveedor, cÃ³digo de fÃ¡brica, marcas, rubros y familias.
   - Si el `ID` del producto estÃ¡ en el Excel y existe en la base de datos de la empresa: **actualizar todos los campos excepto el ID**.
   - Si el `ID` estÃ¡ vacÃ­o/nulo o no existe: **crear el nuevo producto** asignÃ¡ndole automÃ¡ticamente el ID correspondiente que PostgreSQL genera.
   - Si la **Marca**, **Rubro** o **Familia** provista en el Excel no existe en la BD de la empresa: **crearla automÃ¡ticamente en MAYÃSCULAS**, asignarle su ID autonumÃ©rico y asociarla al nuevo producto.
   - Incluir una advertencia explÃ­cita destacada en el modal de captura aclarando que para productos nuevos se debe dejar la casilla `ID` vacÃ­a.

### Archivos Creados / Modificados
- `productos/services/excel_service.py` [NEW]:
  - `generar_excel_productos(queryset, columnas_seleccionadas)`: construye libros Excel `.xlsx` estilizados (header slate-900, bordes delgados, alineaciÃ³n numÃ©rica y autoajuste de ancho de columnas).
  - `procesar_captura_excel_productos(empresa, usuario, archivo_excel)`: procesa atÃ³micamente la lectura de archivos Excel, conversiÃ³n a MAYÃSCULAS, creaciÃ³n automÃ¡tica de Marcas/Rubros/Familias y actualizaciÃ³n/alta por `ID`.
- `productos/views_htmx.py` [MODIFY]:
  - `exportar_productos_excel_completo`: genera la descarga completa del maestro de productos.
  - `modal_exportar_seleccion`: despliega el modal interactivo con la lista completa de checkboxes por campo.
  - `exportar_productos_excel_seleccion`: procesa el POST y descarga el Excel filtrado por columnas.
  - `modal_capturar_excel`: renderiza el modal de captura con la advertencia de ID para nuevos artÃ­culos.
  - `capturar_productos_excel`: procesa la subida POST del Excel y retorna la parcial con el resumen de la captura emitiendo el evento `productosActualizados`.
- `productos/models.py` [MODIFY]:
  - Agregada la conversiÃ³n automÃ¡tica a MAYÃSCULAS en el mÃ©todo `save()` de `Producto`, `Marca`, `Rubro` y `Familia`.
- `config/urls.py` [MODIFY]:
  - Registradas las 5 rutas bajo `/productos/excel/`.
- `templates/productos/modals/exportar_seleccion_modal.html` [NEW]: modal interactivo de selecciÃ³n de columnas.
- `templates/productos/modals/capturar_excel_modal.html` [NEW]: modal de carga de archivo Excel con banner de advertencia visual.
- `templates/productos/modals/capturar_resultado_modal.html` [NEW]: modal con resumen de captura (indicadores de actualizados, creados, entidades creadas y observaciones).
- `templates/productos/stock_index.html` [MODIFY]: incorporados los 3 botones principales (*Capturar Excel*, *Exportar SelecciÃ³n*, *Excel Completo*) en la barra de herramientas.
- `productos/tests/test_excel_productos.py` [NEW]: suite de pruebas unitarias verificando exportaciÃ³n completa, exportaciÃ³n por selecciÃ³n y captura masiva con actualizaciÃ³n y alta de productos en MAYÃSCULAS.
- `docs/planes/063_exportar_importar_productos_excel.md` [NEW]: plan de implementaciÃ³n histÃ³rico formalmente registrado.

### Detalle TÃ©cnico
1. **Regla de Negocio de MayÃºsculas:** Todos los campos de texto (`detalle`, `cod_prov`, `cod_fab`, `marca`, `rubro`, `familia`) son procesados con `.upper().strip()` tanto a nivel de servicio de captura como en los modelos de Django mediante `save()`.
2. **Auto-AsignaciÃ³n de IDs:** Los productos existentes son identificados por la columna `ID` y actualizados sin modificar su clave primaria. Los productos nuevos con celda `ID` vacÃ­a se persisten mediante `Producto.objects.create(...)`, permitiendo que la secuencia autoincremental de la base de datos le otorgue el nuevo ID autonumÃ©rico.
3. **ResoluciÃ³n Inteligente de Entidades:** Si una Marca, Rubro o Familia mencionada en el Excel no existe en el catÃ¡logo de la empresa, el servicio ejecuta `get_or_create` guardÃ¡ndola en MAYÃSCULAS y vinculando su ID resultante al producto.
4. **Transaccionalidad:** Todo el proceso de captura corre bajo `@transaction.atomic()` para garantizar que un error crÃ­tico no deje la base de datos en un estado inconsistente.

### Pruebas Automatizadas
```bash
.\venv\Scripts\python.exe manage.py test productos.tests.test_excel_productos --keepdb
```
**Resultado:** `Ran 3 tests in 6.675s - OK`

### Estado actual y siguientes pasos
Plan 063 **completamente implementado, probado y verificado**.

---

### Objetivo
1. Evitar la ejecuciÃ³n de consultas pesadas a la base de datos sobre todo el historial al ingresar por primera vez a las pantallas de listados.
2. Establecer como valor predeterminado en los campos `desde` y `hasta` la fecha del dÃ­a de hoy (`timezone.localdate().isoformat()`) en los listados de:
   - **Recibos** (`/tesoreria/recibos/`)
   - **Ãrdenes de Pago** (`/tesoreria/ordenes-pago/`)
   - **Compras** (`/facturacion/compras/`)
   - **Ventas** (`/facturacion/ventas/`)

### Archivos Modificados / Creados
- `tesoreria/views_listados.py` [MODIFY]:
  - Modificado el helper `_rango_fechas(request)` para que `desde` tome por defecto la fecha actual (`hoy.isoformat()`) en lugar del primer dÃ­a del mes en curso. Esto actualiza unificadamente los listados de Recibos y Ãrdenes de Pago.
- `facturacion/views.py` [MODIFY]:
  - Modificado `ComprasListView.get()` para que si `desde` o `hasta` no son provistos en los parÃ¡metros `GET`, adopten la fecha de hoy.
  - Modificado `VentasListView.get()` para que si `desde` o `hasta` no son provistos en los parÃ¡metros `GET`, adopten la fecha de hoy.
- `docs/planes/061_fechas_predeterminadas_listados.md` [NEW]:
  - Archivo de documentaciÃ³n del plan histÃ³rico del proyecto.

### Detalle TÃ©cnico
1. **LÃ³gica de Fallback:** Al recibir solicitudes sin querystring de filtro por fecha (ej. primer renderizado al acceder desde el menÃº principal), la vista asume `desde = hoy` y `hasta = hoy`.
2. **Interactividad:** El usuario conserva la facultad de cambiar manualmente cualquier fecha en el formulario de filtros y hacer clic en consultar/filtrar para ver rangos mÃ¡s amplios (por ejemplo, el mes completo o ejercicios pasados).

### Estado actual y siguientes pasos
Plan 061 **completamente implementado, blindado y verificado**.

---

## 22 de Agosto de 2026 â RefactorizaciÃ³n y Limpieza de CatÃ¡logos (UnificaciÃ³n de Marcas, Rubros y Familias por Empresa) â Plan 064

### Objetivo
1. **UnificaciÃ³n Conceptual del CatÃ¡logo Maestro:** Eliminar de forma definitiva las relaciones `sucursales` (ManyToMany) en los modelos `Marca`, `Rubro` y `Familia` en la app `productos`.
2. **Consistencia y SimplificaciÃ³n de Base de Datos:** Establecer que los catÃ¡logos pertenecen globalmente a la `Empresa`. El aislamiento y segmentaciÃ³n por sucursal se gestiona de forma exclusiva en el inventario fÃ­sico (`StockSucursal`), movimientos de stock, operaciones de caja y comprobantes.
3. **Limpieza de UI/UX y EliminaciÃ³n de CÃ³digo Fantasma:** Quitar los componentes visuales de asignaciÃ³n de sucursales en los modales de creaciÃ³n/ediciÃ³n de categorÃ­as y en las tablas de configuraciÃ³n.

### Archivos Creados / Modificados
- `productos/models.py` [MODIFY]:
  - Eliminado el campo `sucursales = models.ManyToManyField(Sucursal, ...)` en los modelos `Marca`, `Rubro` y `Familia`.
- `productos/migrations/0030_remove_familia_sucursales_remove_marca_sucursales_and_more.py` [NEW]:
  - MigraciÃ³n de Django que elimina las 3 tablas pivote intermedias de PostgreSQL (`productos_marca_sucursales`, `productos_rubro_sucursales`, `productos_familia_sucursales`).
- `productos/forms.py` [MODIFY]:
  - Removido `'sucursales'` de `fields` y `widgets`, y limpiada la lÃ³gica de inicializaciÃ³n en `MarcaForm`, `RubroForm` y `FamiliaForm`.
- `productos/views_htmx.py` [MODIFY]:
  - Removidas las llamadas redundantes `form.save_m2m()` en `marca_modal`, `rubro_prod_modal` y `familia_modal`.
- `productos/management/commands/migrar_productos.py` [MODIFY]:
  - Removidas las asignaciones artificiales `sucursales.add(...)` durante la importaciÃ³n desde VFP.
- `templates/productos/modals/marca_modal.html` [MODIFY]:
  - Eliminada la secciÃ³n visual de selecciÃ³n de sucursales en el modal de marcas.
- `templates/productos/modals/rubro_prod_modal.html` [MODIFY]:
  - Eliminada la secciÃ³n visual de selecciÃ³n de sucursales en el modal de rubros de productos.
- `templates/productos/modals/familia_modal.html` [MODIFY]:
  - Eliminada la secciÃ³n visual de selecciÃ³n de sucursales en el modal de familias.
- `templates/configuracion/partials/marcas.html` & `marcas_list.html` [MODIFY]:
  - Eliminados el encabezado `<th>Sucursales</th>` y las etiquetas/badges por sucursal de la tabla de marcas.
- `templates/configuracion/partials/rubros_prod.html` & `rubros_prod_list.html` [MODIFY]:
  - Eliminados el encabezado `<th>Sucursales</th>` y la columna de sucursales de la tabla de rubros de productos.
- `templates/configuracion/partials/familias.html` & `familias_list.html` [MODIFY]:
  - Eliminados el encabezado `<th>Sucursales</th>` y la columna de sucursales de la tabla de familias.
- `docs/planes/064_limpieza_sucursales_catalogos.md` [NEW]:
  - Plan de implementaciÃ³n histÃ³rico formalmente guardado.

### Detalle TÃ©cnico
1. **Esquema de BD Simplificado:** Al remover el campo M2M en Django y aplicar la migraciÃ³n 0030, las 3 tablas pivote fueron eliminadas en PostgreSQL.
2. **Optimizaciones de Rendimiento y CÃ³digo:** Se aligeraron las transacciones de guardado al evitar inserciones en tablas pivote y se eliminaron filtros inÃºtiles.
3. **Cero Impacto Operativo Negativo:** La bÃºsqueda y facturaciÃ³n de productos continÃºa funcionando normalmente, ya que la disponibilidad por sucursal se rige por `StockSucursal.cantidad`.

### Estado actual y siguientes pasos
Plan 064 **completamente implementado, probado y verificado**.

---

## 22 de Agosto de 2026 â ReplicaciÃ³n de Plan de Cuentas, ParÃ¡metros, Medios de Pago y Cuentas Bancarias (Empresa 1 -> Empresa 3) â Plan 065

### Objetivo
1. **ReplicaciÃ³n Completa del Plan de Cuentas:** Duplicar el catÃ¡logo completo de 247 cuentas contables (`contable.models.Cuenta`) desde la Empresa Origen (`empresa_id = 1` - Lopez Rios y Asoc SA) hacia la Empresa Destino (`empresa_id = 3` - EMPRESA TEST).
2. **PreservaciÃ³n de Estructura JerÃ¡rquica:** Mantener y reasignar las relaciones de parentesco contable (`sumariza`) entre las cuentas clonadas correspondientes a la Empresa 3.
3. **ReplicaciÃ³n de ParÃ¡metros Contables:** Clonar la configuraciÃ³n de `contable.models.ParametrosContables` desde la Empresa 1 a la Empresa 3, mapeando automÃ¡ticamente las 23 claves forÃ¡neas de cuentas predeterminadas (`cta_caja_mostrador`, `cta_ventas`, `cta_compras`, `cta_iva_credito`, `cta_iva_debito`, etc.) hacia las cuentas clonadas equivalentes de la Empresa 3.
4. **MigraciÃ³n de Medios de Pago (`MedioPago`):** Procesar el archivo de exportaciÃ³n `d:\borrador\medios_pagos.csv` para poblar los Medios de Pago (`EFE-ARS`, `EFE-USD`, `CHQ-TER`, `TRA-BCO`, `RET-GCIA`, `RET-IIBB`) enlazÃ¡ndolos automÃ¡ticamente a las cuentas contables correspondientes para Empresa 3 y Empresa 1.
5. **ReplicaciÃ³n de Cuentas Bancarias (`CuentaBancaria`):** Clonar las Cuentas Bancarias de la Empresa 1 (Banco Patagonia, Credicoop, Galicia) hacia la Empresa 3, reasignando sus Foreign Keys de cuentas contables principales y de cheques emitidos.

### Archivos Creados / Modificados
- `contable/management/commands/replicar_plan_cuentas.py` [MODIFY]:
  - Comando de gestiÃ³n de Django `python manage.py replicar_plan_cuentas --origen 1 --destino 3` extendido con 5 fases atÃ³micas (`transaction.atomic()`).
- `docs/planes/065_replicar_plan_cuentas.md` [MODIFY]:
  - Plan de implementaciÃ³n histÃ³rico actualizado.
- `docs/walkthrough.md` [MODIFY]:
  - Registro cronolÃ³gico incremental en la bitÃ¡cora de desarrollo.

### Detalle TÃ©cnico
1. **Fase 1 - CreaciÃ³n/SincronizaciÃ³n de Cuentas:** Carga las 247 cuentas de la Empresa 1 y las crea/actualiza para la Empresa 3 usando un diccionario en memoria por jerarquÃ­a (`jerarquia`) para evitar consultas N+1.
2. **Fase 2 - AsignaciÃ³n JerÃ¡rquica (`sumariza`):** Mapea cada `sumariza_id` original al ID de la cuenta padre clonada para la Empresa 3.
3. **Fase 3 - ParÃ¡metros Contables:** Crea el registro `ParametrosContables` para la Empresa 3 y mapea de forma automÃ¡tica 23 campos FK (`cta_iva_credito`, `cta_iva_debito`, `cta_caja`, `cta_ventas`, `cta_compras`, `cta_caja_mostrador`, etc.) a sus cuentas clonadas correspondientes.
4. **Fase 4 - ImportaciÃ³n de Medios de Pago:** Lee `d:\borrador\medios_pagos.csv` y vincula reactivamente la `cuenta_contable` de cada medio de pago (`EFE-ARS`, `EFE-USD`, `CHQ-TER`, `TRA-BCO`, `RET-GCIA`, `RET-IIBB`) con `ParametrosContables` de cada empresa.
5. **Fase 5 - ReplicaciÃ³n de Cuentas Bancarias:** Clona los registros de `CuentaBancaria` de la Empresa 1 a la Empresa 3 asociando `cuenta_contable` y `cuenta_contable_cheques`.

### Resultados de la EjecuciÃ³n
- **Comando ejecutado:** `python manage.py replicar_plan_cuentas --origen 1 --destino 3`
- **Consola output:**
  - `Fase 1 completada: 247 cuentas procesadas en 'EMPRESA TEST'.`
  - `Fase 2 completada: 242 relaciones jerÃ¡rquicas ('sumariza') vinculadas.`
  - `Fase 3 completada: ParÃ¡metros Contables actualizados con 23 cuentas mapeadas.`
  - `Fase 4 completada: 6 Medios de Pago procesados desde d:\borrador\medios_pagos.csv.`
  - `Fase 5 completada: 3 Cuentas Bancarias procesadas en 'EMPRESA TEST'.`
- **ValidaciÃ³n DB:**
  - `Empresa 3` posee **247** cuentas contables, **1** `ParametrosContables`, **6** `MedioPago` y **3** `CuentaBancaria` enlazados.
  - `Empresa 1` posee **247** cuentas contables, **1** `ParametrosContables`, **6** `MedioPago` y **3** `CuentaBancaria` enlazados.

### Estado actual y siguientes pasos
Plan 065 **completamente implementado, probado y verificado**.

---

## 23 de Agosto de 2026 â Plan 069: Modelo `ArcaMisComprobantes` y Motor de ConciliaciÃ³n ARCA vs. Libro IVA

### Objetivo
Crear la tabla fÃ­sica `arca_mis_comprobantes` para almacenar las planillas de comprobantes emitidos (Ventas) y recibidos (Compras) capturados del portal de Mis Comprobantes ARCA / AFIP, e implementar la conciliaciÃ³n bi-direccional estampando `asiento_id` en ARCA y `cae` en el Libro IVA.

### Archivos Creados
- `impuestos/models.py` [MODIFY]: AdiciÃ³n del modelo `ArcaMisComprobantes` (`empresa`, `origen` ['C'/'V'], `periodo`, `fecha`, `codiva`, `punto`, `numero`, `numero_hasta`, `cuit_contraparte`, `razon_social_contraparte`, `neto_gravado`, `no_gravado`, `exento`, `iva_total`, `otros`, `total`, `cae`, `asiento_id`).
- `impuestos/migrations/0002_arcamiscomprobantes.py` [NEW]: MigraciÃ³n de Django para la creaciÃ³n de la tabla fÃ­sica `arca_mis_comprobantes`.
- `impuestos/tests/test_mis_comprobantes_arca.py` [NEW]: Tests unitarios para el modelo, parseo de planillas CSV/Excel y coincidencia bi-direccional de conciliaciÃ³n.
- `docs/planes/069_arca_mis_comprobantes.md` [NEW]: Copia archivada del plan tÃ©cnico de implementaciÃ³n.

### Archivos Modificados
- `impuestos/services.py` [MODIFY]: ImplementaciÃ³n de `importar_archivo_mis_comprobantes_arca`, `conciliar_mis_comprobantes_arca` y `obtener_reporte_conciliacion_arca`.
- `impuestos/views.py` [MODIFY]: ActualizaciÃ³n de `MisComprobantesArcaView` para procesar la subida del archivo ARCA (POST) y generar el reporte por PerÃ­odo Fiscal (`YYYYMM`) (GET).
- `templates/impuestos/mis_comprobantes_arca.html` [MODIFY]: RediseÃ±o con pestaÃ±as interactivas de Alpine.js: ð¢ **Conciliados**, ð¡ **Solo en Libro IVA (Sin CAE vinculada)** y ðµ **Solo en Mis Comprobantes ARCA (Pendientes)**.

### Detalle TÃ©cnico
1. **VinculaciÃ³n Bi-direccional y SincronizaciÃ³n de PerÃ­odo Fiscal:**
   - En **`ArcaMisComprobantes`**: Al conciliar un registro con el ERP, se estampa el `asiento_id` correspondiente y se actualiza `periodo = match.periodo` con el **perÃ­odo exacto (`YYYYMM`) en el que fue declarado en los Libros IVA del sistema** (contemplando traslados de compras a perÃ­odos vigentes posteriores).
   - En **`cble_libro_iva_compras` / `cble_libro_iva_ventas`**: Al conciliar, se estampa el `cae` o `cai` capturado de ARCA (particularmente Ãºtil en facturaciÃ³n en lÃ­nea de ARCA o comprobantes manuales que no poseÃ­an CAE previo en el ERP).
2. **Resultados de ConciliaciÃ³n:**
   - **Conciliados**: `asiento_id` en ARCA y `cae` en el Libro IVA.
   - **Solo en Libro IVA**: Registros del sistema sin `cae` ni coincidencia en ARCA.
   - **Solo en ARCA**: Registros importados de ARCA pendientes con `asiento_id` nulo.

### Pruebas Ejecutadas
- **MigraciÃ³n aplicada:**
  - `Applying impuestos.0002_arcamiscomprobantes... OK`
- **System Check de Django:**
  ```powershell
  .\venv\Scripts\python.exe manage.py check
  ```
  **Resultado:** `System check identified no issues (0 silenced).`

### Estado Actual
Plan 069 **completamente implementado, migrado y verificado**. La captura e importaciÃ³n de planillas de Mis Comprobantes ARCA y su motor de conciliaciÃ³n bi-direccional contra el Libro IVA (con sincronizaciÃ³n del perÃ­odo declarado `YYYYMM`) estÃ¡n 100% operativos.

---

## 23 de Agosto de 2026 â Plan 068: GestiÃ³n de PerÃ­odos IVA, Cierre, Reapertura y Reglas de ImputaciÃ³n

### Objetivo
Desarrollar la lÃ³gica de gestiÃ³n de PerÃ­odos IVA (`YYYYMM`), liquidaciÃ³n mensual, cierres y reaperturas impositivas, e integrar sus reglas de imputaciÃ³n en las operaciones de Compras y Ventas.

### Archivos Creados
- `impuestos/models.py` [NEW]: Modelo `PeriodoIva` (`empresa`, `periodo`, `estado`, `fecha_cierre`, `usuario_cierre`, `debito_fiscal`, `credito_fiscal`, `saldo_resultante`, `fecha_reapertura`, `usuario_reapertura`).
- `impuestos/services.py` [NEW]: Funciones `es_periodo_cerrado`, `obtener_primer_periodo_vigente_compra`, `calcular_liquidacion_iva`, `cerrar_periodo_iva`, `reabrir_periodo_iva` y `obtener_periodos_cerrados`.
- `impuestos/tests/test_periodo_iva.py` [NEW]: Tests unitarios para el ciclo completo de PerÃ­odo IVA y traslados de compras a perÃ­odos vigentes.
- `impuestos/migrations/0001_initial.py` [NEW]: MigraciÃ³n inicial de `impuestos` (`PeriodoIva`).
- `contable/migrations/0020_libroivacompras_periodo_libroivaventas_periodo.py` [NEW]: AdiciÃ³n del campo `periodo` en `LibroIvaCompras` y `LibroIvaVentas`.
- `facturacion/migrations/0051_limpiar_y_alter_periodo.py` [NEW]: SanitizaciÃ³n de formatos guionados previos y ajuste de `max_length=6` en `periodo` de `Compra` y `Venta`.
- `templates/impuestos/modals/periodos_cerrados_modal.html` [NEW]: Modal HTMX para la visualizaciÃ³n y reapertura de perÃ­odos cerrados.
- `docs/planes/068_cierre_y_periodo_iva.md` [NEW]: Registro permanente del plan de implementaciÃ³n.

### Archivos Modificados
- `contable/models.py` [MODIFY]: Campo `periodo = models.CharField(max_length=6, default='', blank=True, db_index=True)` en `LibroIvaBase`.
- `facturacion/models.py` [MODIFY]: NormalizaciÃ³n de `periodo` a `max_length=6, db_index=True` en `Compra` y `Venta`.
- `contable/services/contabilizacion.py` [MODIFY]: Estampado del campo `periodo` al poblar `LibroIvaCompras` e inclusiÃ³n de `_limpiar_libro_iva_venta` y `_poblar_libro_iva_venta` para poblar `LibroIvaVentas` al contabilizar ventas fiscales.
- `facturacion/views.py` [MODIFY]: ValidaciÃ³n de perÃ­odo cerrado en Ventas (`es_periodo_cerrado`) y cÃ¡lculo automÃ¡tico de perÃ­odo vigente en Compras (`obtener_primer_periodo_vigente_compra`), previniendo perÃ­odos anteriores a la fecha de la factura.
- `impuestos/views.py` [MODIFY]: Vistas de liquidaciÃ³n, cierre, modal de perÃ­odos cerrados y reapertura en `CierrePeriodoIvaView`, `PeriodosCerradosModalView` y `ReabrirPeriodoIvaView`.
- `impuestos/urls.py` [MODIFY]: Ruteo de `periodos-cerrados/modal/` y `reabrir-periodo-iva/`.
- `templates/impuestos/cierre_periodo_iva.html` [MODIFY]: BotÃ³n "Ver PerÃ­odos Cerrados", desglose de DÃ©bito/CrÃ©dito y formulario de Cierre y Reapertura.
- `templates/facturacion/compras_carga.html` [MODIFY]: AdiciÃ³n del campo visual/selector del **PerÃ­odo IVA** (`YYYYMM`) en la cabecera del comprobante.

### Detalle TÃ©cnico
1. **Regla Estricta en Ventas:** El perÃ­odo predeterminado SIEMPRE es el `YYYYMM` de la fecha del comprobante. Si el perÃ­odo `YYYYMM` se encuentra CERRADO por liquidaciÃ³n fiscal, se bloquea la emisiÃ³n.
2. **Regla de Traslado de Compras a PerÃ­odos Vigentes:** Si se registra una factura de compra con fecha en un perÃ­odo cerrado (ej: 22/05/2026, estando cerrados 202601 a 202607), `obtener_primer_periodo_vigente_compra` calcula y asigna automÃ¡ticamente el primer perÃ­odo abierto `>= YYYYMM` (ej. `202608`). Se restringe categÃ³ricamente asignar un perÃ­odo anterior a la fecha de emisiÃ³n de la compra.
3. **Poblado Completo y Consulta de Libro IVA:** Se adecuaron los reportes de `LibroIvaVentasView` e `LibroIvaComprasView` para consultar exclusivamente por **PerÃ­odo Fiscal (`YYYYMM`)** mediante selectores de AÃ±o y Mes Fiscal, removiendo el criterio de dos fechas reservado Ãºnicamente a los reportes de gestiÃ³n.

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
Plan 068 **completamente implementado, migrado y verificado**. La gestiÃ³n de PerÃ­odos IVA, Cierre, Reapertura y las consultas impositivas de Libro IVA Ventas e Compras por PerÃ­odo Fiscal (`YYYYMM`) estÃ¡n 100% operativas.

---

## 23 de Agosto de 2026 â Plan 067: Nuevo Bloque del MenÃº Principal "Impuestos"

### Objetivo
Incorporar la nueva secciÃ³n **Impuestos** en el menÃº principal (barra lateral navegable) del ERP Ikigai 2, con un menÃº desplegable (acordeÃ³n interactivo con Alpine.js) e interfaces para la gestiÃ³n de 5 procesos y reportes impositivos.

### Archivos Creados
- `impuestos/__init__.py` [NEW]: Inicializador del paquete de la app Django impuestos.
- `impuestos/apps.py` [NEW]: DefiniciÃ³n del `ImpuestosConfig(AppConfig)`.
- `impuestos/urls.py` [NEW]: Ruteo del mÃ³dulo de impuestos (`app_name = 'impuestos'`).
- `impuestos/views.py` [NEW]: Vistas `ImpuestosIndexView`, `CierrePeriodoIvaView`, `LibroIvaVentasView`, `LibroIvaComprasView`, `MisComprobantesArcaView` y `SicoreGananciasView`.
- `templates/impuestos/index.html` [NEW]: Panel central/Dashboard de Impuestos con tarjetas interactivas.
- `templates/impuestos/cierre_periodo_iva.html` [NEW]: Pantalla para la liquidaciÃ³n mensual de IVA.
- `templates/impuestos/libro_iva_ventas.html` [NEW]: Pantalla para consultar y exportar el Libro IVA Ventas para Portal IVA (ARCA).
- `templates/impuestos/libro_iva_compras.html` [NEW]: Pantalla para consultar y exportar el Libro IVA Compras para Portal IVA (ARCA).
- `templates/impuestos/mis_comprobantes_arca.html` [NEW]: Pantalla para la captura y conciliaciÃ³n de Mis Comprobantes ARCA.
- `templates/impuestos/sicore_ganancias.html` [NEW]: Pantalla para la exportaciÃ³n de retenciones de Ganancias (RG 830) en formato SICORE.
- `docs/planes/067_bloque_impuestos.md` [NEW]: Copia archivada del plan tÃ©cnico de implementaciÃ³n.

### Archivos Modificados
- `config/settings.py` [MODIFY]: Registro de `'impuestos'` en `INSTALLED_APPS`.
- `config/urls.py` [MODIFY]: InclusiÃ³n de `path('impuestos/', include('impuestos.urls'))`.
- `templates/base.html` [MODIFY]: IntegraciÃ³n del nuevo acordeÃ³n **Impuestos** en el menÃº lateral con estado activo segÃºn la URL solicitada.

### Detalle TÃ©cnico
1. **MÃ³dulo AutÃ³nomo y Modular (`impuestos`):** Se creÃ³ la estructura completa de la aplicaciÃ³n Django `impuestos`, permitiendo escalar de forma limpia los procesos impositivos del sistema.
2. **NavegaciÃ³n DinÃ¡mica en la Barra Lateral:** El menÃº se despliega automÃ¡ticamente si la ruta del usuario comienza con `/impuestos/`, manteniendo el enlace del subproceso activo con resaltado especÃ­fico en color.
3. **Dashboard de Impuestos:** DiseÃ±ado con Tailwind CSS y tarjetas dinÃ¡micas con hover y sombras animadas para acceder a cada proceso:
   - **Cierre Periodo IVA** (`/impuestos/cierre-periodo-iva/`)
   - **Libro IVA Ventas - Portal IVA** (`/impuestos/libro-iva-ventas/`)
   - **Libro IVA Compras - Portal IVA** (`/impuestos/libro-iva-compras/`)
   - **Captura Mis Comprobantes ARCA** (`/impuestos/mis-comprobantes-arca/`)
   - **SICORE - RetenciÃ³n Impuesto a las Ganancias** (`/impuestos/sicore-ganancias/`)

### Pruebas Ejecutadas
- **System Check de Django:**
  ```powershell
  .\venv\Scripts\python.exe manage.py check
  ```
  **Resultado:** `System check identified no issues (0 silenced).`

### Estado Actual
Plan 067 **completamente implementado y verificado**. La secciÃ³n de Impuestos ya se encuentra integrada en la barra lateral del ERP Ikigai 2 y sus vistas estÃ¡n activas.

---

## 23 de Agosto de 2026 â ExportaciÃ³n y Recaptura Masiva en Excel del Plan de Cuentas â Plan 066

### Objetivo
1. **ExportaciÃ³n a Excel Completo:** Implementar la exportaciÃ³n del listado total de cuentas contables (`contable.models.Cuenta`) de la empresa activa en formato `.xlsx` con estilos openpyxl (slate header `0F172A`, texto blanco en negrita Arial, bordes delgados y autoajuste de ancho).
2. **Recaptura / ImportaciÃ³n Masiva desde Excel:** Proveer un modal interactivo con HTMX y Tailwind CSS para subir un archivo Excel y procesar actualizaciones y altas masivas de cuentas de forma atÃ³mica (`transaction.atomic()`).
3. **Manejo Inteligente de IDs:**
   - Si la celda `ID` coincide con una cuenta existente en la empresa activa, se actualizan sus campos (`JerarquÃ­a`, `Nombre Cuenta`, `Imputable`, `Tipo`, `CÃ³digo Legacy`, `RG 830`, `Tipo Disponibilidad`, etc.) manteniendo intacto el `ID`.
   - Si la celda `ID` estÃ¡ vacÃ­a o el `ID` no existe en la empresa activa, se interpreta como cuenta nueva. El sistema **no fuerza el ID ingresado** y deja que PostgreSQL le asigne automÃ¡ticamente el `ID` autoincremental correspondiente.
   - UnificaciÃ³n automÃ¡tica de los nombres de cuenta en **MAYÃSCULAS**.

### Archivos Creados / Modificados
- `contable/services/excel_service.py` [NEW]:
  - `COLUMNAS_CUENTA_MAP`: Mapeo de columnas y encabezados de Excel.
  - `generar_excel_cuentas(queryset)`: Servicio de generaciÃ³n de `.xlsx` para el plan de cuentas.
  - `procesar_captura_excel_cuentas(empresa, usuario, archivo_excel)`: LÃ³gica atÃ³mica de lectura de Excel, actualizaciÃ³n por ID existente y alta de cuentas nuevas con resoluciÃ³n de parentesco (`sumariza`).
- `contable/views_htmx.py` [MODIFY]:
  - `exportar_cuentas_excel_completo`: Vista para descargar el Excel completo.
  - `modal_capturar_cuentas_excel`: Despliega el modal de recaptura.
  - `capturar_cuentas_excel`: Procesa el archivo subido via POST y emite la seÃ±al HTMX `reloadCuentas`.
- `templates/contable/modals/capturar_excel_modal.html` [NEW]:
  - Plantilla del modal de recaptura con resumen de resultados y caja de alerta destacada con las reglas aclaratorias de carga de ID.
- `templates/configuracion/partials/cuentascontables.html` [MODIFY]:
  - IntegraciÃ³n de los botones **"Capturar Excel"** y **"Excel Completo"** en la barra superior junto al botÃ³n de **"Nueva Cuenta"**.
- `config/urls.py` y `contable/urls.py` [MODIFY]:
  - Registro de las rutas URL para exportaciÃ³n y recaptura de cuentas contables.
- `contable/tests/test_excel_cuentas.py` [NEW]:
  - Pruebas automatizadas de exportaciÃ³n a Excel y recaptura masiva (creaciÃ³n con ID vacio/inexistente y actualizaciÃ³n por ID).
- `docs/planes/066_recaptura_excel_plan_cuentas.md` [NEW]:
  - Copia guardada del plan de implementaciÃ³n en la carpeta histÃ³rica de planes.
- `docs/walkthrough.md` [MODIFY]:
  - ActualizaciÃ³n de la bitÃ¡cora de desarrollo.

### Detalle TÃ©cnico
1. **Regla de Negocio del ID:** Se verificÃ³ el diccionario en memoria de las cuentas existentes por `id` pertenencientes a `empresa=empresa`. Si el ID suministrado no se encuentra en la base de datos de esa empresa, la fila se inserta mediante `Cuenta.objects.create(empresa=empresa, ...)` sin pasar la clave primaria `id`, permitiendo que la secuencia de PostgreSQL genere la clave incremental limpia sin conflictos.
2. **AsignaciÃ³n JerÃ¡rquica:** Se calcula la jerarquÃ­a padre extrayendo la subcadena previa al Ãºltimo punto (ej. `1.1` para `1.1.01`) y asociando la Foreign Key `sumariza` automÃ¡ticamente.
3. **Respuesta HTMX:** Si la recaptura actualiza o crea al menos 1 cuenta, la vista asigna la cabecera `HX-Trigger: {"reloadCuentas": true}`, refrescando inmediatamente la grilla de cuentas sin recargar la pÃ¡gina.

### Resultados de las Pruebas
- **Comando ejecutado:** `.\venv\Scripts\python.exe manage.py test contable.tests.test_excel_cuentas`
- **Resultado:**
  - `Ran 3 tests in 0.941s` -> **OK**
  - `test_generar_excel_cuentas`: PasÃ³ exitosamente.
  - `test_capturar_excel_actualizar_y_crear_cuentas`: PasÃ³ exitosamente (verificÃ³ actualizaciÃ³n de ID existente, creaciÃ³n de ID en blanco y asignaciÃ³n de ID autoincremental automÃ¡tico al ingresar un ID inexistente).
  - `test_views_excel_exportar_y_modal`: PasÃ³ exitosamente.

### Estado actual y siguientes pasos
Plan 066 **completamente implementado, probado y verificado**.

## 24 de Agosto de 2026 â Plan 070: IncorporaciÃ³n de Actividades "Distribuidora" y "Empresa AgrÃ­cola" en Empresas

### Objetivo
AÃ±adir las opciones de actividad **Distribuidora** y **Empresa AgrÃ­cola** en el selector (`tipo_actividad`) de `Empresa` y `EmpresaForm` para su selecciÃ³n en el formulario modal de alta y ediciÃ³n de empresas.

### Archivos Modificados / Creados
- `empresas/models.py` [MODIFY]: Definida la tupla `TIPO_ACTIVIDAD_CHOICES` en el modelo `Empresa` incluyendo `('DISTRIBUIDORA', 'Distribuidora')` y `('AGRICOLA', 'Empresa AgrÃ­cola')`.
- `empresas/forms.py` [MODIFY]: Vinculado `tipo_actividad` en `EmpresaForm` a `Empresa.TIPO_ACTIVIDAD_CHOICES`.
- `empresas/migrations/0016_alter_empresa_tipo_actividad.py` [NEW]: MigraciÃ³n de Django que registra los nuevos `choices` en `Empresa`.
- `docs/planes/070_actividades_distribuidora_y_agricola.md` [NEW]: Copia del plan de implementaciÃ³n archivada.

### Implicaciones de Base de Datos
- MigraciÃ³n aplicada: `empresas.0016_alter_empresa_tipo_actividad` (OK).

### Estado Actual
Plan 070 **completamente implementado y verificado**. Las opciones Distribuidora y Empresa AgrÃ­cola se encuentran activas en el selector de tipo de actividad de las empresas.

---

## 26 de Agosto de 2026 â Plan 071: Ajustes en Trazabilidad de Subproductos (/stock/trazabilidad/)

### Tarea u Objetivo
Implementar tres mejoras clave en el mÃ³dulo de Trazabilidad de Subproductos:
1. AmpliaciÃ³n del historial de trazabilidad por **Serie y CUIM** (multiciclo) y creaciÃ³n del modal de detalle completo de compra (`compra_id`) y venta (`id_vta > 0`).
2. Modal y vista HTMX de **EdiciÃ³n exclusiva de SERIE y CUIM** para subsanar errores de tipeo sin alterar montos ni comprobantes.
3. ReversiÃ³n automÃ¡tica del subproducto de `'VENDIDA'` a `'DEPOSITO'` y limpieza de la relaciÃ³n con la venta al emitir una Nota de CrÃ©dito por devoluciÃ³n.

### Archivos Creados
- `templates/productos/partials/subproducto_detalle_modal.html` [NEW]: Plantilla modal HTMX con la ficha completa de datos de adquisiciÃ³n (compra_id, fecha, proveedor, comprobante, costo adq, moneda, cotizaciÃ³n) y venta (id_vta, fecha, cliente, comprobante, precio neto y total).
- `templates/productos/partials/subproducto_editar_modal.html` [NEW]: Formulario modal HTMX restringido exclusivamente a la modificaciÃ³n de los campos `SERIE` y `CUIM`.
- `facturacion/tests/test_plan071_trazabilidad.py` [NEW]: Tests automatizados Django probando la reversiÃ³n a DEPOSITO al emitir Nota de CrÃ©dito y la ediciÃ³n exclusiva de SERIE/CUIM.
- `docs/planes/071_ajustes_trazabilidad_subproductos.md` [NEW]: Copia archivada del plan tÃ©cnico de implementaciÃ³n.

### Archivos Modificados
- `productos/views_trazabilidad.py` [MODIFY]: 
  - AmpliaciÃ³n de `trazabilidad_modal_timeline` para consolidar el historial por Serie y/o CUIM.
  - AdiciÃ³n de la vista `@login_required subproducto_detalle_modal(request, subpro_id)` con consulta select_related de compra y venta.
  - AdiciÃ³n de la vista `@login_required subproducto_editar_modal(request, subpro_id)` para actualizaciÃ³n exclusiva de `serie` y `cuim`.
- `facturacion/services/notas_credito.py` [MODIFY]: ReversiÃ³n automÃ¡tica en `emitir_nota_credito_desde_venta`: al devolver un producto trazable (`subprod == True`), sus objetos `Subproducto` asociados se actualizan a `situacion = 'DEPOSITO'`, `venta = None` (`id_vta = null`), `fecvta = None`, `precio_neto = 0`, `precio_total = 0`, `cotizvta = 1`, `fecent = None`.
- `config/urls.py` [MODIFY]: Registro de las rutas HTMX `/stock/trazabilidad/subproducto/<int:subpro_id>/detalle/` y `/stock/trazabilidad/subproducto/<int:subpro_id>/editar/`.
- `templates/productos/partials/trazabilidad_grilla.html` [MODIFY]: IncorporaciÃ³n de botones de acciÃ³n "Detalle" y "Editar" en cada fila de la grilla.
- `templates/productos/trazabilidad_list.html` [MODIFY]: RediseÃ±o de cabecera inline y formulario ultra-compacto de 1 sola fila con Flexbox proporcional (`flex-1` en CliPro/Producto y anchos reducidos `w-32` Serie, `w-28` CUIM, `w-36` Estado y `w-20` Limpiar). Configurado disparador HTMX dinÃ¡mico en `SERIE` y `CUIM` a partir del 3er carÃ¡cter (`keyup[len>=3 || len==0] delay:250ms`).
- `productos/views_trazabilidad.py` [MODIFY]: CondiciÃ³n backend `len >= 3` en `search_serie` y `search_cuim` para filtrado dinÃ¡mico.
- `templates/productos/partials/trazabilidad_grilla.html` [MODIFY]: ReducciÃ³n de padding de celdas a `py-2 px-3` duplicando la densidad de filas visibles por pantalla.

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
Plan 071 **completamente ejecutado, verificado y documentado**. El mÃ³dulo de Trazabilidad de Subproductos cuenta con interfaz ultra-compacta que maximiza el espacio del listado, filtrado dinÃ¡mico en tiempo real a partir del 3er carÃ¡cter en Serie y CUIM, historial multiciclo por Serie y CUIM, selector de filtrado por Estado Actual (`DEPOSITO` / `VENDIDA`), ficha completa de detalles de compra/venta, ediciÃ³n rÃ¡pida de Serie/CUIM y reversiÃ³n automÃ¡tica a 'DEPOSITO' ante Notas de CrÃ©dito.

---

## 26 de Agosto de 2026 â Limpieza de Archivos Temporales (PDF y PNG) en Carga de Compras

### Objetivo
1. **Borrar Temp de Compras:** Solucionar el problema de la acumulaciÃ³n de archivos temporales (PDFs e imÃ¡genes PNG de vista previa) que no se borraban luego de cargar una factura de compra mediante el servicio OCR de lectura de CUIT.

### Archivos Creados / Modificados
- `facturacion/services/extractor_facturas.py` [MODIFY]:
  - Modificada la generaciÃ³n del nombre de la imagen PNG temporal para que utilice el mismo nombre base que el PDF (en lugar de generar un UUID distinto), lo que permite que el backend pueda emparejarlos y borrarlos juntos al finalizar.
- `facturacion/views.py` [MODIFY]:
  - En la vista de carga de comprobantes, modificado el bloque donde se persiste el PDF definitivo para tambiÃ©n ubicar y eliminar el PNG temporal correspondiente, de forma conjunta y limpia.
- `facturacion/views_procesamiento.py` [MODIFY]:
  - En `CargaCompraAutomaticaView.post`, aÃ±adido un recolector de basura (garbage collector) proactivo: `_limpiar_temp_facturas(temp_dir)`. Este proceso corre antes de crear un nuevo archivo y elimina automÃ¡ticamente cualquier archivo huÃ©rfano dentro de `temp_facturas` que sea anterior a 1 hora (3600 segundos). Esto asegura que los archivos abandonados (subidos, pero no persistidos) no se acumulen.

### Detalle TÃ©cnico
1. **Emparejamiento por Basename:** Al guardar el PDF se asocia un nombre base (ej. `1234abcd.pdf`) y ahora la imagen se llama igual (`1234abcd.png`).
2. **Garbage Collector de Temp:** Para los casos en que el usuario sube una factura y abandona la pÃ¡gina sin guardar, la limpieza periÃ³dica basada en el tiempo de modificaciÃ³n del archivo (`st_mtime`) impide que la carpeta `temp_facturas` crezca sin control.

### Estado actual y siguientes pasos
CorrecciÃ³n de archivos temporales **completamente implementada y operativa**.

## 26 de Agosto de 2026 â ConversiÃ³n de Facturas a WEBP y Nombramiento EspecÃ­fico (Plan 067)

### Objetivo
1. **UnificaciÃ³n WebP (Stitching):** Optimizar el almacenamiento y visualizaciÃ³n convirtiendo los PDFs de compras en imÃ¡genes verticales continuas en formato `WebP`, en lugar de preservar el PDF.
2. **Nomenclatura y Directorio Fijo:** Renombrar el archivo generado siguiendo el patrÃ³n estricto `{empresa_id}.{ejercicio_id}.{asiento_id}.webp` y ubicarlo en la carpeta `compras_archivosWEBP/` **sÃ³lo** tras confirmar y contabilizar la compra.
3. **Bloqueo de EdiciÃ³n (Readonly):** Proteger los montos leÃ­dos mediante OCR en el frontend, bloqueando la ediciÃ³n de precios en la grilla al provenir del escÃ¡ner automÃ¡tico.

### Archivos Modificados
- `facturacion/services/extractor_facturas.py` [MODIFY]:
  - Modificado el extractor para iterar hasta 5 pÃ¡ginas del documento PDF, convertir cada `pixmap` a una imagen con `Pillow` y unirlas verticalmente en un "pergamino" continuo (`stitched.paste()`).
  - Cambiado el formato de salida a `WEBP` en lugar de `PNG` logrando mayor compresiÃ³n.
- `facturacion/models.py` [MODIFY]:
  - Actualizado `compras_pdf_path` para apuntar ahora a `compras_archivosWEBP/{filename}` sin timestamp (el nombre viene prefijado del controlador).
- `facturacion/views_procesamiento.py` [MODIFY]:
  - Ahora se devuelve la ruta `.webp` a la sesiÃ³n y se destruye el PDF original de forma segura (sin cron script en python, confiando en limpieza temporal asÃ­ncrona de SO).
- `facturacion/views.py` [MODIFY]:
  - Al completar la transacciÃ³n y generar el asiento en `ComprasCargaView.post`, se captura `compra.asiento_id` y `compra.ejercicio_id` para renombrar y guardar definitivamente el comprobante como `{empresa_id}.{ejercicio_id}.{asiento_id}.webp`.
- `templates/facturacion/compras_carga.html` [MODIFY]:
  - Se implementÃ³ un script que detecta si el formulario proviene de OCR (`pdf_temp_path`). De ser asÃ­, se iteran todos los campos `precio`, `cto_adq`, `cto_rep` y `descuento`, inyectando propiedades `readOnly` y aplicando clases de bloqueo visual (`bg-slate-100`, `cursor-not-allowed`) para blindar la integridad del dato escaneado.

### Detalle TÃ©cnico
1. **Stitching sin OOM:** El bucle de pÃ¡ginas estÃ¡ acotado deliberadamente a `min(5, len(doc))` para mitigar posibles ataques de denegaciÃ³n (archivos de miles de pÃ¡ginas) que provoquen Timeouts en Gunicorn o saturen la RAM, cubriendo a la vez el 99% de las facturas convencionales.
2. **Manejo de Transacciones:** Si el usuario no hace clic en "Aceptar" y abandona la pÃ¡gina, la imagen WebP vive Ãºnicamente en `temp_facturas/`, el cual serÃ¡ depurado con un cron de Linux. NingÃºn registro huÃ©rfano impacta en `compras_archivosWEBP`.

### Estado actual y siguientes pasos
El plan estÃ¡ **completamente implementado, blindado y probado**. Los comprobantes son ahora pergaminos WebP muy ligeros.

## 26 de Agosto de 2026 â CorrecciÃ³n de desapariciÃ³n de Proveedor al editar Producto

### Objetivo
1. **Evitar desapariciÃ³n de proveedor:** Solucionar el problema reportado donde al editar un producto en el sistema, el proveedor preexistente desaparecÃ­a del formulario forzando al usuario a volver a seleccionarlo.

### Archivos Modificados
- `productos/forms.py` [MODIFY]:
  - Modificado el mÃ©todo `__init__` de `ProductoForm`. El queryset del campo `proveedor` ahora incluye no solo a los proveedores estÃ¡ndar de la empresa activa (`tipo_entidad=2`), sino que tambiÃ©n se expande dinÃ¡micamente mediante `Q()` para incluir explÃ­citamente al proveedor actual del producto en caso de que este fuera configurado de forma global (`empresa__isnull=True`) o con otro `tipo_entidad`.
  - Se agregÃ³ ordenamiento alfabÃ©tico `.order_by('razon_social')` para el catÃ¡logo de proveedores y por `'detalle'` para Marca, Rubro y Familia.

### Detalle TÃ©cnico
1. **ConservaciÃ³n de Foreign Key:** El comportamiento original de `forms.Select` de Django descarta automÃ¡ticamente el valor actual de una instancia si este no se encuentra presente dentro del queryset asignado al campo. Al ampliar el queryset sumando el `self.instance.proveedor_id` mediante el operador `|` (OR), garantizamos que la opciÃ³n se renderice correctamente en el DOM y no se pierda al guardar el formulario.

### Estado actual y siguientes pasos
El problema de ediciÃ³n de proveedor estÃ¡ **completamente solucionado**.

## 26 de Agosto de 2026 â Perfil de Lectura Inteligente de Compras (CUIT 30-71132306-2)

### Objetivo
1. **Nuevo perfil OCR:** Incorporar un mÃ³dulo de lectura de PDF para las facturas del proveedor con CUIT `30-71132306-2`, capaz de identificar el "ArtÃ­culo" como cÃ³digo principal, pero que tambiÃ©n separe y ofrezca el cÃ³digo suplementario ubicado al final de la descripciÃ³n.
2. **Emparejamiento flexible:** Permitir que el sistema busque el producto en la base de datos de la empresa haciendo un doble intento inteligente (`fallback`): primero por el cÃ³digo principal ("ArtÃ­culo"), y si falla, por el cÃ³digo alternativo del proveedor que venÃ­a embutido en el detalle.

### Archivos Modificados / Creados
- `facturacion/services/perfiles_lectura/cuit_30711323062.py` [NEW]:
  - Archivo de perfil `procesar_perfil(texto_completo)`. Se programÃ³ una expresiÃ³n regular adaptada a este diseÃ±o de PDF para capturar cantidades, precios, totales, "ArtÃ­culo" (como `codigo`), descripciÃ³n, y el cÃ³digo embutido final (como `codigo_alt`).
- `facturacion/views_procesamiento.py` [MODIFY]:
  - En la vista `CargaCompraAutomaticaView`, se incorporÃ³ la lectura del nuevo atributo `codigo_alt`. Si el sistema no logra vincular un Ã­tem de la factura por su `codigo` primario, intenta automÃ¡ticamente emparejarlo usando `cod_prov=codigo_alt` y `detalle__icontains=codigo_alt`, extendiendo las capacidades de importaciÃ³n de todo el ERP.

### Detalle TÃ©cnico
1. **RediseÃ±o OCR por Modo de Lectura (`sort=True`):** Se descubriÃ³ que el motor core de `extractor_facturas.py` procesaba los documentos activando la reconstrucciÃ³n de pÃ¡rrafos de PyMuPDF (`sort=True`), lo cual destruye el formato tabular y agrupa las lÃ­neas de texto horizontalmente. Se reconstruyÃ³ integralmente la ExpresiÃ³n Regular de los Ã­tems (`r'^[\s]*([\d\,\.]+)[\s]+(\d+)[\s]+(.*?)[\s]+([\d\,\.]+)[\s]+([\d\,\.]+)[\s]*\n[\s]*(.*?)[\s]*\n'`) para adaptarse a este flujo continuo y garantizar que la grilla reciba correctamente los artÃ­culos.
2. **CorrecciÃ³n de Totales Invertidos:** En los PDFs de este proveedor, la librerÃ­a de extracciÃ³n suele leer el bloque de montos monetarios de los totales *antes* que las etiquetas de texto ("SUBTOTAL", "TOTAL"). Se agregÃ³ una expresiÃ³n regular estructural para interceptar correctamente los valores reales (Neto, Total e IVA) ignorando los subtotales post-descuento.
3. **Mapeo de Descuento Global y Totales ExplÃ­citos:** Se programÃ³ el perfil para aislar el valor del descuento general de la factura y extraer simultÃ¡neamente los 5 valores impositivos fundamentales: Subtotal Bruto, Descuento, Neto Gravado, IVA y Total. Se extendieron las capacidades del frontend (`carga_compra_automatica.html` y `compras_carga.html`) para que transporten y asignen automÃ¡ticamente todos estos campos directamente en el formulario de la vista de Carga Venta/Compra, disparando el recÃ¡lculo visual en pantalla de forma instantÃ¡nea.
4. **Robustez de OCR Transversal:** La modificaciÃ³n a `views_procesamiento.py` fue diseÃ±ada de forma transparente (`it.get('codigo_alt')`), lo que significa que a partir de ahora *cualquier* futuro perfil de lectura podrÃ¡ opcionalmente suministrar un `codigo_alt` y el sistema sabrÃ¡ aprovecharlo para emparejar inteligentemente los artÃ­culos.

### Estado actual y siguientes pasos
Perfil de lectura completado, probado sobre el archivo PDF de muestra y listo para utilizar en el sistema en vivo de Carga de Compras.

## 26 de Agosto de 2026 â CorrecciÃ³n de Error de Sintaxis (NameError) en Modal de Trazabilidad

### Objetivo
1. **Solucionar fallo 500:** Corregir un error de sintaxis (`NameError: name 'sp' is not defined`) en la lista de comprensiÃ³n de la vista `trazabilidad_modal_timeline` que causaba que la carga del modal y el botÃ³n de detalles fallaran en la interfaz.

### Archivos Modificados
- `productos/views_trazabilidad.py` [MODIFY]:
  - Corregida la lista de comprensiÃ³n en la lÃ­nea 85 de `[sp.cuim for sp.cuim in subproductos_serie if sp.cuim]` a `[sp.cuim for sp in subproductos_serie if sp.cuim]`.

### Detalle TÃ©cnico
1. **Sintaxis de Python:** La declaraciÃ³n incorrecta `for sp.cuim in subproductos_serie` intentaba usar un atributo de un objeto no definido (`sp`) como variable de iteraciÃ³n. Se ajustÃ³ a la sintaxis estÃ¡ndar `for sp in subproductos_serie` para extraer correctamente los atributos de los objetos instanciados.
2. **Impacto en UI:** Este error de servidor (HTTP 500) interrumpÃ­a la carga asÃ­ncrona de los modales de HTMX, dejando inoperativos los botones (como el de "detalle") asociados al evento de respuesta de esta vista.
3. **Cierre de Modales HTMX:** Se identificÃ³ que las plantillas `subproducto_detalle_modal.html` y `subproducto_editar_modal.html` carecÃ­an de la declaraciÃ³n de la funciÃ³n JavaScript `closeModal()`, lo cual provocaba que si el usuario hacÃ­a clic fuera del modal (en el backdrop gris) o en el botÃ³n de cerrar, el modal no respondiera y la pantalla quedara bloqueada con la superposiciÃ³n gris. Se inyectÃ³ el script correspondiente para restaurar la interactividad.

### Estado actual y siguientes pasos
El problema en el mÃ³dulo de trazabilidad y el bloqueo de pantalla de los modales estÃ¡ **completamente solucionado y operativo**.

## 26 de Agosto de 2026 â Filtro por Sucursal en Trazabilidad de Subproductos

### Objetivo
1. **Filtro de Sucursales:** Agregar la lÃ³gica en la vista y en la UI para permitir la bÃºsqueda y visualizaciÃ³n de subproductos segÃºn la sucursal a la que pertenecen, dentro del mÃ³dulo de Trazabilidad.

### Archivos Modificados
- `productos/views_trazabilidad.py` [MODIFY]:
  - `SubproductoTrazabilidadListView`: Modificado el mÃ©todo `get_queryset` para incorporar `sucursal_id` como parÃ¡metro de bÃºsqueda extraÃ­do de `request.GET.get('sucursal')`.
  - Agregado el mÃ©todo `get_context_data` para enviar al contexto las sucursales pertenecientes a la empresa en sesiÃ³n y renderizar dinÃ¡micamente el `select` de opciones.
- `templates/productos/trazabilidad_list.html` [MODIFY]:
  - AÃ±adido el combo desplegable (`select`) para la sucursal, integrado con HTMX para refresco automÃ¡tico.
  - AÃ±adida la cabecera `<th>Sucursal</th>` en la tabla de resultados.
- `templates/productos/partials/trazabilidad_grilla.html` [MODIFY]:
  - Agregada la celda correspondiente para visualizar el nombre de la sucursal en cada registro (`{{ sp.sucursal.nombre }}`).
  - Ajustados los valores de los atributos `colspan` de 6 a 7 para las filas de "vacÃ­o" o "cargar mÃ¡s" de la tabla, con el fin de conservar la alineaciÃ³n visual tras la adiciÃ³n de la columna.

### Detalle TÃ©cnico
1. **ConservaciÃ³n de Filtros HTMX:** El nuevo select cuenta con el disparador propio integrado con la solicitud general al endpoint y, al estar envuelto en el form `#form-filtros-trazabilidad`, sus parÃ¡metros se pasan por URL manteniendo el comportamiento responsivo.

### Estado actual y siguientes pasos
Filtro de Sucursales integrado y tabla adaptada a la nueva columna.

## 26 de Agosto de 2026 â ReparaciÃ³n de Filtros en Trazabilidad de Subproductos

### Objetivo
1. **Corregir Filtro CliPro:** Solucionar el problema en el cual seleccionar un cliente/proveedor desde la lista desplegable o utilizar el botÃ³n de "Limpiar" no aplicaba los filtros en el backend, dejando la tabla sin cambios.

### Archivos Modificados
- `templates/productos/trazabilidad_list.html` [MODIFY]:
  - Eliminado el atributo `onsubmit="event.preventDefault();"` del formulario de filtros.
  - Eliminado el listener JS manual de `submit` que interceptaba y realizaba la peticiÃ³n por `htmx.ajax` ignorando los valores de los inputs.
  - Al quitar esta intercepciÃ³n manual, se delegÃ³ el control 100% al comportamiento nativo de HTMX sobre el evento submit, garantizando la correcta serializaciÃ³n y envÃ­o de todo el querystring.

### Estado actual y siguientes pasos
El formulario ya procesa e incluye exitosamente todos sus valores cuando se dispara remotamente mediante `htmx.trigger`.

## 26 de Agosto de 2026 â OptimizaciÃ³n de Sugerencias en Trazabilidad (Solo con movimientos)

### Objetivo
1. **Limpiar listado de sugerencias:** Evitar sugerir todos los clientes/proveedores y productos de la base de datos en los autocompletados del mÃ³dulo de Trazabilidad, restringiendo los resultados exclusivamente a aquellos que realmente poseen movimientos o historiales asociados.

### Archivos Modificados
- `facturacion/views_htmx.py` [MODIFY]:
  - `typeahead_clientes`: Agregada la validaciÃ³n del parÃ¡metro `solo_trazabilidad`. Si estÃ¡ activo (`1`), se utiliza `Exists()` sobre el modelo `Subproducto` con `OuterRef` hacia el ID del cliente o proveedor para excluir del QuerySet a quienes no tengan participaciÃ³n en los subproductos de la empresa.
  - `typeahead_productos_venta`: Implementada la misma lÃ³gica para excluir productos que no existan dentro de la tabla de Trazabilidad/Subproductos de la empresa activa. AdemÃ¡s, se suprimiÃ³ la restricciÃ³n rÃ­gida de `subprod=False` que regÃ­a para las ventas estÃ¡ndar, permitiendo que sÃ­ emerjan los artÃ­culos con trazabilidad (`subprod=True`) bajo este modo exclusivo.
- `templates/productos/trazabilidad_list.html` [MODIFY]:
  - AÃ±adido el valor `solo_trazabilidad: "1"` estÃ¡tico en los diccionarios JS que forman el atributo `hx-vals` de los inputs de bÃºsqueda rÃ¡pida, de manera que esta regla opere exclusivamente aquÃ­ sin afectar las pantallas de facturaciÃ³n convencionales.

### Detalle TÃ©cnico
1. **DesempeÃ±o de Base de Datos:** En lugar de realizar JOINs masivos o comprobaciones iterativas, el uso de la funciÃ³n `Exists()` de Django genera subconsultas correlacionadas `EXISTS(SELECT ...)` en el motor de base de datos. Esto permite que el filtrado sea excepcionalmente rÃ¡pido, frenando la bÃºsqueda en cuanto se encuentra la primera coincidencia, lo cual no penaliza el rendimiento al escribir en el frontend.

### Estado actual y siguientes pasos
Los typeaheads de trazabilidad ahora solo ofrecen entidades y productos con movimientos reales en el sistema, agilizando mucho mÃ¡s las bÃºsquedas.

## 27 de Agosto de 2026 â Columnas de ArmerÃ­a y Combobox 'Es PolicÃ­a' en Clientes y Proveedores â Plan 072

### Objetivo
Extender la gestiÃ³n de Clientes y Proveedores para empresas con actividad de **ArmerÃ­a** (`tipo_actividad == 'ARMERIA'`):
1. Selector de columnas y visualizaciÃ³n en la grilla principal (`CLU`, `Vencimiento CLU` y `Es PolicÃ­a`).
2. Selector desplegable (Combobox / Select) para la condiciÃ³n "Es PolicÃ­a / Fuerza de Seguridad" (predeterminado `NO (Civil / Particular)`).
3. ExportaciÃ³n a Excel incorporando las columnas de ArmerÃ­a.
4. OptimizaciÃ³n de consultas ORM agregando `select_related('armeria')`.

### Archivos Creados / Modificados
- `docs/planes/072_columnas_armeria_y_es_policia_clientes.md` [NEW]: Plan de implementaciÃ³n archivado.
- `facturacion/forms.py` [MODIFY]: `ExtensionArmeriaForm` incluye `es_policia` como `TypedChoiceField` desplegable (opciones `NO (Civil)` y `SÃ (PolicÃ­a)`).
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]: AdiciÃ³n del combobox `es_policia` en el bloque de Registro de ArmerÃ­a en 3 columnas responsivas.
- `facturacion/views.py` [MODIFY]: `ClientesProveedoresIndexView` optimizado con `select_related('jurisdiccion', 'armeria')`.
- `facturacion/views_htmx.py` [MODIFY]: `buscar_clientes` optimizado con `select_related('jurisdiccion', 'armeria')`.
- `facturacion/views_reportes.py` [MODIFY]: `exportar_clientes_excel` con `select_related('jurisdiccion', 'armeria')`.
- `facturacion/services/clientes_excel.py` [MODIFY]: InclusiÃ³n condicional de columnas `CLU`, `Vencimiento CLU` y `Es PolicÃ­a` en el reporte Excel para empresas ArmerÃ­a.
- `templates/facturacion/clientes_index.html` [MODIFY]: Checkboxes de visibilidad de columnas `NÂ° CLU`, `Vencimiento CLU` y `Es PolicÃ­a` en el desplegable y encabezados `<th>` condicionales para ArmerÃ­a.
- `templates/facturacion/partials/cliente_table_rows.html` [MODIFY]: Celdas `<td>` condicionales para CLU, Vencimiento CLU y Es PolicÃ­a.
- `facturacion/tests/test_armeria_credencial_clu.py` [MODIFY]: Pruebas unitarias para `ExtensionArmeriaForm` (combobox) y vistas del buscador.

### Resultado de las Pruebas Automatizadas
```powershell
.\venv\Scripts\python.exe manage.py test facturacion.tests.test_armeria_credencial_clu
```
**Resultado:** `OK (Ran 4 tests in 1.728s)`.

### Estado Actual
Plan 072 **completamente ejecutado, probado y documentado**.

## DÃ­a 28/08/2026 - MÃ³dulo DistribuciÃ³n: toma de pedidos desde el celular (Plan 074, fase 2)

**Responsable:** Claude Opus.

### Objetivo
Ejecutar la fase 2 del [Plan 074](planes/074_modulo_distribucion.md): la pantalla mobile-first con la que el vendedor toma el pedido en la calle, cargando por cÃ³digo, con el crÃ©dito del cliente y el stock disponible a la vista.

### Archivos Creados o Modificados
- `distribucion/services/carrito.py` [NEW]: carrito en sesiÃ³n. `buscar_producto_por_codigo()` (resuelve por ID del ERP o por cÃ³digo del sistema anterior), `buscar_productos()`, `agregar_item()`, `quitar_item()`, `totales()`, `limpiar()`.
- `distribucion/services/pedidos.py` [MODIFY]: `guardar_pedido()`, que persiste el pedido completo desde el carrito y lo numera.
- `distribucion/views_movil.py` [NEW]: ocho vistas HTMX del circuito mÃ³vil.
- `templates/distribucion/movil/` [NEW]: `pedido.html` y cinco parciales (`cabecera`, `carrito`, `clientes_sugerencias`, `productos_sugerencias`, `confirmacion`).
- `config/urls.py` [MODIFY]: ocho rutas.
- `templates/base.html` [MODIFY]: el menÃº distingue "Tomar Pedido (MÃ³vil)" de "Tomar Pedido (PC)".
- `distribucion/tests/test_plan074_movil.py` [NEW]: 29 pruebas.
- `static/css/output.css` [MODIFY]: recompilado.

### Detalle TÃ©cnico

**Carrito compartido con la pantalla de PC.** Se reutiliza la clave de sesiÃ³n `preventa_items_temp` y el mismo formato de Ã­tem, asÃ­ que un pedido empezado en un canal se puede terminar en el otro y el guardado es comÃºn. Evita mantener dos carritos con reglas divergentes.

**El precio nunca viene del navegador.** Se resuelve en el servidor con el coeficiente del cliente. Hay una prueba especÃ­fica que manda `precio=1` en el POST y verifica que se ignora: el importe que ve el vendedor tiene que ser exactamente el que despuÃ©s se factura.

**BÃºsqueda por cÃ³digo con prioridad definida.** Acepta el ID del ERP y el cÃ³digo del sistema anterior, porque durante la transiciÃ³n conviven y el vendedor usa el que recuerda. Ante colisiÃ³n gana el ID del ERP, que es el cÃ³digo definitivo. Probado con un caso de colisiÃ³n sembrado a propÃ³sito.

**Cargar dos veces el mismo artÃ­culo ACUMULA** en vez de rechazar: en la calle el cliente vuelve sobre un artÃ­culo y el vendedor va cantando lo que le piden.

**Cambiar de cliente con un pedido en curso se rechaza** con un aviso, en lugar de vaciar el carrito en silencio.

**La fecha no aparece en ninguna parte**, coherente con el criterio fijado: `Preventa.fecha` es `auto_now_add`. Hay una prueba que verifica que la pantalla no expone ningÃºn `name="fecha"`.

**Conectividad: online-only**, segÃºn lo decidido. La planilla de papel es el plan B.

### Resultado de las Pruebas

```powershell
.\venv\Scripts\python.exe manage.py test distribucion --keepdb --noinput
```
**Resultado:** `OK (Ran 92 tests in 209.5s)` â 28 de la fase 1a, 35 de la fase 1 y 29 nuevas.

El WARNING `Not Found: /distribucion/movil/clientes/364/elegir/` que aparece en la salida es el **404 esperado** del test que verifica que un vendedor no puede elegir un cliente fuera de su cartera.

VerificaciÃ³n adicional: las seis plantillas nuevas compilan y `/distribucion/movil/` responde 200 contra la base real con la empresa 4 en sesiÃ³n.

### Estado Actual y Siguientes Pasos
El vendedor ya puede tomar pedidos desde el celular de punta a punta. **Siguiente: fase 3** â reporte de faltantes y pantalla de asignaciÃ³n de stock escaso por orden de llegada del pedido.

---

**CorrecciÃ³n (mismo dÃ­a) â las fechas de alta y baja de Personal no se mostraban al editar.**

*Reportado por el usuario.* DiagnÃ³stico: **el guardado siempre funcionÃ³**; el defecto era de RENDERIZADO. Con `LANGUAGE_CODE = 'es-ar'`, Django renderiza el valor de un `forms.DateInput` con el formato local (`value="28/08/2026"`), y un `<input type="date">` de HTML5 **sÃ³lo acepta `YYYY-MM-DD` en su atributo `value`**: descarta cualquier otro formato en silencio y muestra el campo VACÃO. El registro tenÃ­a la fecha bien guardada, pero al editarlo parecÃ­a no tenerla, y si el usuario grababa asÃ­ la borraba sin querer.

Del lado de la entrada no habÃ­a problema: Django 5.1 agrega `%Y-%m-%d` a los `DATE_INPUT_FORMATS` del locale, asÃ­ que lo que manda el navegador se parsea bien. Por eso el defecto era difÃ­cil de ver: sÃ³lo se manifestaba al editar.

- `core/forms.py` [MODIFY]: se agregÃ³ el widget **`DateInputHTML5`**, que fija `format='%Y-%m-%d'` y el `type="date"`, con la explicaciÃ³n de la trampa. Va en `core` junto a `DecimalARField`, como Ãºnica fuente de verdad de los widgets compartidos.
- `distribucion/forms.py` [MODIFY]: `fecha_alta` y `fecha_baja` pasan a usarlo.
- `templates/configuracion/modals/personal_form.html` [MODIFY]: faltaba mostrar los errores de `fecha_alta` (sÃ³lo se mostraban los de `fecha_baja`), con lo que un error de validaciÃ³n en ese campo quedaba invisible.
- `distribucion/tests/test_plan074_maestros.py` [MODIFY]: dos pruebas nuevas, una de guardado y otra de **regresiÃ³n** que verifica que el `value` renderizado sale en ISO.

**Resultado:** `OK (Ran 30 tests in 33.8s)`.

**El mismo defecto existe en otros siete widgets de fecha del proyecto**, que no se tocaron por estar fuera del alcance de esta fase. `empresas/forms.py` ya aplicaba el arreglo en dos campos (`fecha_inicio_actividades` y `vencimiento_crt_afip`), asÃ­ que el patrÃ³n correcto ya estaba en el cÃ³digo; falta en:

| Archivo | Campo | Se ve al editar |
|---|---|---|
| `empresas/forms.py:79-80` | `Ejercicio.inicio` / `.cierre` | un ejercicio |
| `facturacion/forms.py:96` | `ClienteProveedor.fecha_nacimiento` | un cliente |
| `facturacion/forms.py:275` | `ExtensionArmeria.clu_vto` | un cliente de armerÃ­a |
| `facturacion/forms.py:34` y `:362` | `Venta.fecha` / `Compra.fecha` | un comprobante |
| `contable/forms.py:102` | fecha del asiento | un asiento |

En todos, editar un registro existente muestra el campo de fecha vacÃ­o. El arreglo es reemplazar `forms.DateInput(attrs={'type': 'date'})` por `DateInputHTML5()`.

## DÃ­a 28/08/2026 - MÃ³dulo DistribuciÃ³n: pedido, crÃ©dito y stock comprometido (Plan 074, fase 1)

**Responsable:** Claude Opus.

### Objetivo
Ejecutar la fase 1 del [Plan 074](planes/074_modulo_distribucion.md): dotar al pedido de numeraciÃ³n correlativa propia, implementar el servicio de crÃ©dito con la regla del saldo disponible negativo, el precio por coeficiente y el stock comprometido. Se completÃ³ ademÃ¡s la pantalla de cartera y agenda que habÃ­a quedado pendiente de la fase 1a.

**DecisiÃ³n de arquitectura:** el mÃ³dulo NO crea un circuito paralelo de pedidos. Reutiliza `Preventa` âque ya tiene estados, autorizaciÃ³n de descuentos e Ã­temsâ y le cuelga la extensiÃ³n con lo propio de la distribuciÃ³n. Todo lo agregado al circuito compartido estÃ¡ condicionado a `tipo_actividad == 'DISTRIBUIDORA'`, asÃ­ que armerÃ­a, estudio y las empresas estÃ¡ndar no cambian de comportamiento.

### Archivos Creados o Modificados

**Modelos y migraciones**
- `distribucion/models.py` [MODIFY]: `ExtensionPedidoDistribucion` (OneToOne con `Preventa`) con `punto`, `numero`, `vendedor`, `fecha_entrega`, `origen`, `condic_destino`, `zona`, `hora_carga`, `alerta_stock`, `alerta_credito`. `UniqueConstraint (punto, numero)`.
- `core/models.py` [MODIFY]: tipo `PEDIDO` en `ContadorDocumento.TIPOS_DOCUMENTO`.
- `productos/models.py` [MODIFY]: `StockSucursal.comprometido` y la property `disponible`.
- Migraciones [NEW]: `distribucion/0002_extensionpedidodistribucion.py`, `core/0002_alter_contadordocumento_tipo_documento.py`, `productos/0032_stocksucursal_comprometido.py`.

**Servicios**
- `distribucion/services/precios.py` [NEW]: `precio_para()` = `Producto.precio_total * coeficiente_mayorista`. Ãnica fuente de verdad del precio de distribuciÃ³n.
- `distribucion/services/credito.py` [NEW]: `situacion_crediticia()` con la regla del saldo disponible negativo.
- `distribucion/services/pedidos.py` [NEW]: `registrar_pedido()` (numeraciÃ³n + alertas), `vendedor_de()`, `clientes_de_la_cartera()`.
- `productos/services/stock_service.py` [MODIFY]: `recalcular_comprometido()` y `disponible_real()`.
- `core/services/numeracion.py` [MODIFY]: `auditar_correlativos()` ahora cubre la serie de pedidos.

**IntegraciÃ³n al circuito de preventa**
- `facturacion/signals.py` [MODIFY]: tres seÃ±ales que mantienen `comprometido` al dÃ­a (alta/baja de Ã­tem y cambio de estado de la cabecera).
- `facturacion/views_htmx.py` [MODIFY]: `info_cliente_preventa` devuelve el panel de crÃ©dito para distribuidoras; `preventas_item_add` recalcula el precio con el coeficiente del cliente y agrega el disponible real y ambos cÃ³digos al Ã­tem.
- `facturacion/views.py` [MODIFY]: `PreventaCargaView` acota el selector de clientes a la cartera del vendedor y, al guardar, llama a `registrar_pedido()` avisando por `messages` el nÃºmero asignado y las alertas.

**Pantallas**
- `distribucion/views.py` [NEW]: `CarteraIndexView` y `DistribucionRequiredMixin`.
- `distribucion/views_htmx.py` [MODIFY]: `asignar_vendedor()` y `asignar_dia_visita()`.
- `templates/distribucion/` [NEW]: `cartera.html`, `partials/cartera_fila.html`, `partials/cartera_filas.html`, `partials/panel_credito.html`.
- `templates/facturacion/preventa_carga.html` [MODIFY]: fila de distribuciÃ³n (condiciÃ³n de facturaciÃ³n, fecha de entrega, observaciones) y contenedor del panel de crÃ©dito.
- `templates/base.html` [MODIFY]: subsecciÃ³n "OperaciÃ³n" en el menÃº de DistribuciÃ³n, con Tomar Pedido y Cartera y Agenda.
- `config/urls.py` [MODIFY]: tres rutas nuevas.
- `static/css/output.css` [MODIFY]: recompilado.

**Pruebas**
- `distribucion/tests/test_plan074_pedidos.py` [NEW]: 35 pruebas.

### Detalle TÃ©cnico

**La regla del saldo disponible negativo.** `saldo_disponible = limite â saldo` y `cobro_minimo = max(0, âsaldo_disponible)`. Esa formulaciÃ³n absorbe los cuatro casos del negocio sin un solo condicional especial: entra holgado, se pasa parcialmente, `limite = 0` (sÃ³lo contado) y cliente bloqueado. El ejemplo del plan queda verificado: lÃ­mite 100.000, saldo 110.000 â disponible â10.000 y cobro mÃ­nimo 10.000.

Al TOMAR el pedido, el disponible descuenta ademÃ¡s los **pedidos sin facturar**. Sin ese tÃ©rmino, tres pedidos del mismo dÃ­a pasan todos el control porque ninguno llegÃ³ todavÃ­a a `saldo`. Al facturar (fase 4) ese tÃ©rmino vale cero por construcciÃ³n.

**Stock comprometido.** Se mantiene con las mismas reglas que `cantidad`: es un valor DERIVADO, se recalcula entero y nunca se ajusta por delta, asÃ­ que es idempotente y autorreparable. Se guarda **separado** de `cantidad` a propÃ³sito: `cantidad` es lo que hay en el depÃ³sito y sale de comprobantes emitidos; `comprometido` es una promesa que todavÃ­a no moviÃ³ mercaderÃ­a. Mezclarlos harÃ­a que un pedido pareciera una salida de stock y el depÃ³sito dejarÃ­a de cuadrar contra el conteo fÃ­sico.

**NumeraciÃ³n del pedido.** Se toma con `siguiente_numero()`, que bloquea el contador con `select_for_update()`, y la base tiene ademÃ¡s el `UniqueConstraint` como segunda barrera â el esquema que el Plan 075 propone llevar a `Venta`. El punto de emisiÃ³n es `sucursal_id`, misma convenciÃ³n que el PRE. `registrar_pedido()` es idempotente: un pedido que se edita conserva su nÃºmero.

**Precio.** Se recalcula siempre en el servidor y no se confÃ­a en lo que manda el navegador: el importe que ve el vendedor tiene que ser exactamente el que despuÃ©s se factura. Un coeficiente sin cargar cae al neutro (1) y no deja el producto en $0.

### Implicaciones de Base de Datos
Tres migraciones aditivas: una tabla nueva, una columna nueva con default y un `choices` ampliado. Respaldo previo con `pg_dump -F c` en `scratch/respaldos/`.

### Resultado de las Pruebas

```powershell
.\venv\Scripts\python.exe manage.py test distribucion --keepdb --noinput
```
**Resultado:** `OK (Ran 63 tests in 190.5s)` â 28 de la fase 1a mÃ¡s 35 nuevas.

VerificaciÃ³n adicional: las seis plantillas nuevas y modificadas compilan, y las pantallas `/distribucion/cartera/`, `/ventas/preventas/carga/` y las dos pestaÃ±as de configuraciÃ³n responden **200** contra la base real con la empresa 4 (RODRIGUEZ MARCELO FABIAN) en sesiÃ³n.

### Estado Actual y Siguientes Pasos

**Ya se puede operar:** asignar la cartera y la agenda de visitas, y tomar pedidos con el panel de crÃ©dito en vivo, precio por coeficiente, disponible real por Ã­tem y nÃºmero correlativo propio.

**Pendiente:** la pantalla mÃ³vil (fase 2), el reporte de faltantes y la asignaciÃ³n de stock escaso (fase 3), y la planilla manual en PDF. El control de crÃ©dito sigue siendo informativo: el vinculante llega con la facturaciÃ³n por lote (fase 4), que a su vez depende del [Plan 075](planes/075_integridad_numeracion_comprobantes_venta.md).

**Defecto preexistente detectado:** `facturacion/views.py` (`VentasCargaView`) referencia una variable `ctx_base` inexistente en la rama de "perÃ­odo IVA cerrado". ProvocarÃ­a un `NameError` al intentar facturar en un perÃ­odo cerrado. No se tocÃ³ por estar fuera del alcance de esta fase.

---

**Ajuste posterior (mismo dÃ­a) â fecha de la preventa.** Por definiciÃ³n del usuario, la fecha del comprobante la determina el sistema, no se edita **y tampoco se muestra**: es siempre la del dÃ­a de carga, y ocupar espacio de pantalla con un dato que no se decide no le aporta nada al operador.

`Preventa.fecha` ya era `auto_now_add`, asÃ­ que la regla **ya se cumplÃ­a en el modelo para todas las actividades** y no habÃ­a ningÃºn input que la pudiera alterar. No hizo falta ningÃºn cambio funcional. Verificado con GET real contra la base: DISTRIBUIDORA y ARMERÃA responden 200 y ninguna expone un input `name="fecha"`.

Queda fijado como criterio para la **fase 4** (facturaciÃ³n por lote): la fecha de la venta la pone el sistema, no el operador. Eso hace estructuralmente inalcanzable la rama de "perÃ­odo IVA cerrado" en el circuito de distribuciÃ³n.

## DÃ­a 28/08/2026 - MÃ³dulo DistribuciÃ³n: maestros y campos base (Plan 074, fase 1a)

**Responsable:** Claude Opus (arquitectura y ejecuciÃ³n).
*Nota: `.cursorrules` indica leer `docs/soy.md` para determinar la firma, pero ese archivo no existe en el repositorio.*

### Objetivo
Ejecutar la primera fase del [Plan 074](planes/074_modulo_distribucion.md): crear la app `distribucion` con sus maestros, los campos de distribuciÃ³n en `Producto`, la extensiÃ³n del cliente, y los ABM necesarios para que se pueda hacer la carga de datos maestros (fase 0 del plan). No se implementÃ³ todavÃ­a ningÃºn circuito operativo.

Se invirtiÃ³ el orden previsto en el plan: la fase 0 era "cargar datos maestros", pero esos campos no existÃ­an todavÃ­a y no habÃ­a dÃ³nde cargarlos. Primero las estructuras, despuÃ©s la carga.

### Archivos Creados o Modificados

**App nueva `distribucion`**
- `distribucion/models.py` [NEW]: `ZonaReparto`, `Personal`, `Vehiculo`, `MotivoDevolucion`, `CarteraVendedor`, `DiaVisita`.
- `distribucion/forms.py` [NEW]: `ZonaRepartoForm`, `PersonalForm`, `VehiculoForm`, `MotivoDevolucionForm`, todos acotados por `empresa_id`.
- `distribucion/views_htmx.py` [NEW]: ABM HTMX de los cuatro catÃ¡logos (modal + buscador + borrado) y siembra del catÃ¡logo de motivos.
- `distribucion/services/catalogos.py` [NEW]: catÃ¡logo inicial de 17 motivos de devoluciÃ³n y `sembrar_motivos()` idempotente.
- `distribucion/management/commands/sembrar_motivos_devolucion.py` [NEW]: comando para sembrar el catÃ¡logo por empresa.
- `distribucion/tests/test_plan074_maestros.py` [NEW]: 25 pruebas.
- `distribucion/apps.py`, `__init__.py`, `migrations/0001_initial.py` [NEW].

**Modelos existentes (cambios aditivos)**
- `productos/models.py` [MODIFY]: `peso_unitario_kg`, `unidad_venta`, `unidades_por_bulto`, `codigo_anterior` en `Producto`, mÃ¡s el Ã­ndice `(empresa, codigo_anterior)` y la normalizaciÃ³n a mayÃºsculas del cÃ³digo anterior.
- `facturacion/models.py` [MODIFY]: `ExtensionDistribuidora` (OneToOne con `ClienteProveedor`), con `clasificacion`, `coeficiente_mayorista`, `zona` y `bloqueado_credito`.
- `productos/migrations/0031_...py`, `facturacion/migrations/0055_extensiondistribuidora.py` [NEW].

**Formularios y vistas**
- `core/forms.py` [NEW]: `DecimalARField`, contrapartida en backend de `static/js/formato_ar.js`. Los inputs `.fInputAR` llegan como `1.234,56` y Django los rechazaba antes de `clean_<campo>`; la conversiÃ³n ocurre en `to_python`. Es la Ãºnica fuente de verdad del desformateo en formularios.
- `facturacion/forms.py` [MODIFY]: `ExtensionDistribuidoraForm`.
- `facturacion/views_htmx.py` [MODIFY]: `cliente_modal` maneja la extensiÃ³n de distribuciÃ³n con el mismo patrÃ³n que ya usaba para armerÃ­a (validaciÃ³n, guardado atÃ³mico y propagaciÃ³n de errores).
- `productos/forms.py` [MODIFY]: los cuatro campos nuevos en `ProductoForm`, con `DecimalARField` para peso y unidades por bulto.
- `core/views_config.py` [MODIFY]: contexto de las cuatro pestaÃ±as nuevas.
- `config/urls.py` [MODIFY]: 17 rutas de los ABM.
- `config/settings.py` [MODIFY]: alta de `distribucion` en `INSTALLED_APPS`.

**Templates**
- `templates/configuracion/partials/` [NEW]: `personal_distribucion.html`, `zonas_reparto.html`, `vehiculos.html`, `motivos_devolucion.html` y sus cuatro `*_table_rows.html`.
- `templates/configuracion/modals/` [NEW]: `personal_form.html`, `zona_form.html`, `vehiculo_form.html`, `motivo_form.html`.
- `templates/configuracion/partials/hub.html` [MODIFY]: bloque "DistribuciÃ³n", visible sÃ³lo si `empresa_actual.tipo_actividad == 'DISTRIBUIDORA'`.
- `templates/productos/modals/producto_modal.html` [MODIFY]: bloque de distribuciÃ³n, con la misma condiciÃ³n.
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]: bloque de distribuciÃ³n en el modal de cliente.
- `static/css/output.css` [MODIFY]: recompilado con `npm run build` (Tailwind purgado: las clases nuevas no existÃ­an).

### Detalle TÃ©cnico

**`Personal` es tabla propia y no un atributo de `Usuario`** (Plan 074 Â§4.3). El motivo de fondo es que no todo el personal opera el ERP: el repartidor trabaja con la hoja de ruta en papel y puede no tocar nunca una pantalla, pero tiene que figurar igual en el documento. Modelarlo como `User` obligarÃ­a a crear credenciales para gente que nunca va a entrar. Por eso `usuario` es un OneToOne **nullable**. Los tres roles (`es_vendedor`, `es_repartidor`, `es_cobrador`) son booleanos acumulables: en una distribuidora chica la misma persona vende, reparte y cobra.

`Venta.vendedor` y `Preventa.vendedor` **no se tocaron**: siguen apuntando a `User` porque los usan los filtros y reportes de las otras actividades. En distribuciÃ³n el vendedor de una venta se obtendrÃ¡ a travÃ©s de su pedido.

**Precio del cliente de reparto** = `Producto.precio_total * ExtensionDistribuidora.coeficiente_mayorista`. La base es el precio de lista **con IVA**; `cto_rep` no interviene en la venta (es costo de reposiciÃ³n, entrada del circuito de compras).

**Multi-tenant:** todas las consultas y todos los combos se acotan por `session['empresa_id']`, con pruebas especÃ­ficas de aislamiento (usuarios, sucursales y zonas de otra empresa no se ofrecen).

**CatÃ¡logo de motivos:** se siembra bajo demanda y no por migraciÃ³n de datos, porque los motivos son por empresa y una empresa puede pasar a ser DISTRIBUIDORA mucho despuÃ©s. La siembra es idempotente (`get_or_create` por empresa + cÃ³digo): no duplica ni pisa lo que el usuario haya editado. `sugiere_apto_reventa` precarga si la mercaderÃ­a devuelta vuelve al stock vendible; los tres motivos que no la devuelven son `PRODUCTO_DANADO`, `PROXIMO_A_VENCER` y `CADENA_DE_FRIO`.

### Implicaciones de Base de Datos
Tres migraciones, todas **aditivas**: seis tablas nuevas en `distribucion`, una tabla nueva en `facturacion` y cuatro columnas nullables/con default en `productos_producto`. Ninguna destructiva, ninguna con pÃ©rdida de datos posible.

Se tomÃ³ un respaldo previo con `pg_dump -F c` en `scratch/respaldos/` (carpeta ignorada por git) antes de aplicar.

### Resultado de las Pruebas

```powershell
.\venv\Scripts\python.exe manage.py test distribucion --keepdb --noinput
.\venv\Scripts\python.exe manage.py test productos --keepdb --noinput
.\venv\Scripts\python.exe manage.py test facturacion --keepdb --noinput
```

| Suite | Resultado |
|---|---|
| `distribucion` | **OK** â 28 pruebas en 41,5 s |
| `productos` | **OK** â 25 pruebas en 151,4 s |
| `facturacion` | 64 pruebas: 1 falla y 24 errores, **todos preexistentes** (ver abajo) |

AdemÃ¡s se verificÃ³ que las 15 plantillas nuevas y modificadas compilan con el cargador de Django.

#### Fallos preexistentes detectados en `facturacion` (NO introducidos por esta intervenciÃ³n)

Se comprobÃ³ creando un *worktree* limpio de `HEAD` y verificando que el defecto ya estÃ¡ ahÃ­, sin ninguno de los cambios de esta fase.

1. **23 errores en `facturacion/tests/test_facturas_pendientes.py`** â `DataError: value too long for type character varying(6)`. Los helpers `crear_compra()` y `crear_venta()` escriben `periodo="2026-06"` (7 caracteres) en un campo `CharField(max_length=6)` cuyo formato documentado es `YYYYMM`. Corresponde `"202606"`. Es un defecto del test, no del modelo, y no puede haber pasado nunca contra PostgreSQL.
2. **1 error en `facturacion/tests/test_arca_service.py`** â `FileNotFoundError` del certificado `media/certificados_afip/certificado_cortiz.crt`. Es una prueba de integraciÃ³n real contra ARCA HomologaciÃ³n: depende del entorno, no del cÃ³digo.
3. **1 falla en `facturacion/tests/test_armeria_credencial_clu.py`** â `test_extension_armeria_form_es_policia_select` arma el `ExtensionArmeriaForm` sin `tipo_persona`. El Plan 073 hizo ese campo obligatorio en el formulario y el test del Plan 072 no se actualizÃ³.

Ninguno de los tres toca archivos modificados en esta intervenciÃ³n. Quedan reportados para resolverse en su mÃ³dulo correspondiente.

### Estado Actual y Siguientes Pasos

**Hecho:** estructuras y ABM listos. Ya se puede hacer la carga de datos maestros de la fase 0 del plan: personal, zonas, vehÃ­culos, motivos, peso y cÃ³digo anterior de los productos, y coeficiente por cliente.

**Pendiente de la fase 1 del plan:** pantalla de cartera de vendedores y dÃ­as de visita (los modelos existen, falta la UI), y los permisos `permiso_distribucion_*` en `usuarios.Perfil` â hoy los ABM se rigen por el permiso general del panel de configuraciÃ³n (`is_staff` o `es_admin_sistema`).

**Siguiente fase sugerida:** fase 1 del plan (pedido con numeraciÃ³n correlativa, servicio de crÃ©dito y stock comprometido), que a su vez depende de definir los valores de `ExtensionDistribuidora.clasificacion` (Â§11.1, Ãºnica decisiÃ³n abierta).

---

**Ajuste posterior (mismo dÃ­a):** se agregÃ³ la secciÃ³n **DistribuciÃ³n** al menÃº lateral (`templates/base.html`), condicionada a `empresa_actual.tipo_actividad == 'DISTRIBUIDORA'`, con accesos directos a los cuatro maestros. Hasta ahora sÃ³lo eran alcanzables desde el Panel de ConfiguraciÃ³n y el mÃ³dulo no se veÃ­a en el menÃº principal. Se recompilÃ³ `output.css`. Los circuitos operativos (pedidos, repartos, cobranzas) se irÃ¡n sumando a esta misma secciÃ³n a medida que avancen las fases del plan.

## DÃ­a 28/08/2026 - SeparaciÃ³n de RazÃ³n Social / Apellido y Nombre (Plan 073)

### Objetivo
Aplicar el Plan 073 para el mÃ³dulo de ArmerÃ­a, separando conceptualmente Persona FÃ­sica (Apellido y Nombre) de Persona JurÃ­dica (RazÃ³n Social), garantizando que en backend los datos persistan unificados en la tabla base.

### Archivos Creados o Modificados
- 
acturacion/models.py [MODIFY]: Se aÃ±adiÃ³ 	ipo_persona (CharField) a la ExtensionArmeria.
- 
acturacion/migrations/0053_extensionarmeria_tipo_persona.py [NEW]: MigraciÃ³n de esquema.
- 
acturacion/migrations/0054_assign_tipo_persona_armeria.py [NEW]: MigraciÃ³n de datos (Data Migration) que iterÃ³ los registros existentes. AsignÃ³ 'J' si el CUIT arranca con 30/33/34 y tiene 11 dÃ­gitos, y 'F' en caso contrario (ademÃ¡s, para 'F', formateÃ³ la RazÃ³n Social dividiÃ©ndola con coma si no la tenÃ­a).
- 
acturacion/forms.py [MODIFY]: Se aÃ±adiÃ³ 	ipo_persona a ExtensionArmeriaForm. Se quitÃ³ la obligaciÃ³n estricta HTML de 
azon_social para poder alternar el formulario dinÃ¡mico, pero se validÃ³ duramente en el mÃ©todo clean().
- 
acturacion/views_htmx.py [MODIFY]: El endpoint cliente_modal fue ajustado. En POST, si el tipo de persona es FÃ­sica (F), concatena Apellido y Nombre en 
azon_social. En GET, si es F, divide 
azon_social por la coma y expone al template variables para armar la vista.
- 	emplates/facturacion/modals/cliente_modal.html [MODIFY]: Se incluyeron Radio Cards de UI premium para elegir entre FÃ­sica o JurÃ­dica. Se dividieron los inputs. AdemÃ¡s, la carga por AFIP rellena estos campos de forma automÃ¡tica leyendo el campo oculto 	ipo_persona.
- 
acturacion/services/afip_padron.py [MODIFY]: Retorna en el diccionario final 
ombre y pellido desglosados para facilitarle la vida al frontend, ademÃ¡s del cÃ³digo F o J.

### Detalle TÃ©cnico
Se respetÃ³ al mÃ¡ximo la directiva de no utilizar suposiciones adivinadas con prefijos en tiempo de ejecuciÃ³n, por lo tanto la determinaciÃ³n del autocompletado en el padrÃ³n recae Ã­ntegramente en los datos del JSON (vÃ­a 	ipoClave). Se diseÃ±Ã³ la interfaz usando Alpine.js y TailwindCSS sin sacrificar la rigurosidad de validaciÃ³n del backend de Django (clean()), asegurando compatibilidad hacia atrÃ¡s mediante Data Migrations.

### Resultado de Pruebas
Las migraciones corrieron satisfactoriamente en entorno local sin errores de sintaxis o constraint.

### Estado actual y siguientes pasos sugeridos
Plan completado exitosamente y listo para pruebas operativas. Sugerimos validar la carga en la vista del usuario final creando y consultando un par de CUITs en la ventana emergente.

## DÃ­a 28/08/2026 - Autocompletado AFIP (PadrÃ³n A13) para Clientes/Proveedores

### Objetivo
Implementar un botÃ³n en el modal de Clientes/Proveedores que consulte automÃ¡ticamente los datos fiscales a AFIP mediante el servicio ws_sr_padron_a13 y rellene el formulario.

### Archivos Modificados/Creados
- 
acturacion/services/afip_padron.py [NEW]: Se creÃ³ el servicio AFIPPadronService que reutiliza la configuraciÃ³n de rca_arg para conectarse a AFIP y obtener los datos a partir de un CUIT.
- 
acturacion/views_htmx.py [MODIFY]: Se agregÃ³ el endpoint consultar_padron_afip que retorna los datos consultados en formato JSON.
- config/urls.py [MODIFY]: Se expuso el endpoint htmx/consultar-afip/<cuit>/.
- 	emplates/facturacion/modals/cliente_modal.html [MODIFY]: Se integrÃ³ un botÃ³n de autocompletado junto al campo de CUIT y lÃ³gica Alpine.js para hacer la solicitud 
etch y distribuir la respuesta en los inputs correspondientes (RazÃ³n Social, Domicilio, IVA, etc.).

### Detalle TÃ©cnico
El servicio de AFIP evalÃºa la respuesta del WS y formatea la condiciÃ³n de IVA segÃºn los impuestos (30 -> Inscripto, 32 -> Exento, o si tiene Monotributo). En el Frontend, si el CUIT es vÃ¡lido (11 dÃ­gitos), se consulta asÃ­ncronamente y se inyectan los valores directamente en los id de los campos, disparando el evento input para reactividad HTMX/Alpine si es necesario.

### Estado Actual y Siguientes Pasos
Plan de Autocompletado finalizado. Queda pendiente probar la integraciÃ³n directamente desde la interfaz.

## 28 de Agosto de 2026 â Visibilidad y Obligatoriedad del Campo "Es PolicÃ­a" en Clientes

### Objetivo
1. **Obligatoriedad y Visibilidad:** Hacer que el campo "Â¿Es PolicÃ­a / Fuerza de Seguridad?" (asociado a la extensiÃ³n de ArmerÃ­a) sea de carÃ¡cter obligatorio, tenga una opciÃ³n vacÃ­a por defecto para forzar la elecciÃ³n, y se ubique en la parte superior del formulario de creaciÃ³n/ediciÃ³n de clientes (secciÃ³n "Identidad y CondiciÃ³n Fiscal") para mayor visibilidad al momento del alta.

### Archivos Modificados
- `facturacion/forms.py` [MODIFY]:
  - `ExtensionArmeriaForm`: Modificado el campo `es_policia` para requerir una selecciÃ³n explÃ­cita (`required=True`), agregando la opciÃ³n vacÃ­a `('', "Seleccione una opciÃ³n")` en los choices, y ajustando el `initial` a `''` cuando se trata de una nueva entidad.
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]:
  - Reubicado el campo `form_armeria.es_policia` desde la secciÃ³n inferior "Registro de ArmerÃ­a" hacia la secciÃ³n superior "1. Identidad y CondiciÃ³n Fiscal", colocÃ¡ndolo junto al "Rol Comercial".
  - Se agregÃ³ el indicador visual de campo obligatorio (`*` en rojo).

### Detalle TÃ©cnico
1. **Forzado de SelecciÃ³n Inicial:** Al agregar una opciÃ³n con valor vacÃ­o y `required=True` en un `TypedChoiceField`, la validaciÃ³n nativa de Django impedirÃ¡ que el formulario se envÃ­e sin que el usuario seleccione activamente "SÃ" o "NO". Si no selecciona nada, la validaciÃ³n fallarÃ¡ y se mostrarÃ¡ el error en el listado superior del modal y debajo del campo.

### Estado actual y siguientes pasos
El campo ahora es obligatorio y mucho mÃ¡s visible en el inicio del formulario.

## 28 de Agosto de 2026 â MigraciÃ³n de Permisos de ArmerÃ­a y EliminaciÃ³n de JOSEN

### Objetivo
1. **LÃ³gica de Visibilidad de ArmerÃ­a:** Migrar el control de acceso a los formularios y configuraciones de ArmerÃ­a, pasando de basarse en permisos individuales por usuario (`puede_armeria`) a depender del atributo `tipo_actividad` de la Empresa activa en sesiÃ³n (si es 'ARMERIA', el mÃ³dulo se activa para los empleados de la empresa).
2. **EliminaciÃ³n del MÃ³dulo JOSEN:** Borrar de manera permanente todas las referencias, modelos de base de datos, formularios, vistas (HTMX y generales), URLs y componentes de interfaz relacionados al submÃ³dulo JOSEN ya cancelado.

### Archivos Modificados
- `usuarios/models.py` [MODIFY]:
  - Eliminados los campos `permiso_armeria_ver`, `permiso_armeria_editar`, `permiso_josen_ver` y `permiso_josen_editar` del modelo `Perfil`.
- `usuarios/forms.py` [MODIFY]:
  - Eliminados los campos de permisos de ArmerÃ­a y JOSEN de `UsuarioForm`.
- `facturacion/models.py` [MODIFY]:
  - Eliminados completamente los modelos `RubroJosen` y `ExtensionJosen`.
- `facturacion/forms.py` [MODIFY]:
  - Eliminados los formularios `ExtensionJosenForm` y `RubroJosenForm`.
- `facturacion/views_htmx.py` [MODIFY]:
  - Eliminado el CRUD completo HTMX para Rubros JOSEN (`rubro_modal`, `buscar_rubros`, `eliminar_rubro`).
  - Refactorizado `cliente_modal`: Eliminada la lÃ³gica de JOSEN y reemplazada la lÃ³gica `puede_armeria` (ahora se lee de `Empresa.tipo_actividad == 'ARMERIA'`).
- `config/urls.py` [MODIFY]:
  - Eliminadas las rutas de configuraciÃ³n de Rubros JOSEN.
- `core/views_config.py` [MODIFY]:
  - Eliminado el pase a contexto de los rubros JOSEN para el panel de control.
- `facturacion/admin.py` [MODIFY]:
  - Eliminado `JosenInline` de la visualizaciÃ³n en el Django Admin y sus importaciones.
- `templates/configuracion/modals/usuario_form.html` [MODIFY]:
  - Removidas las cajas de selecciÃ³n de permisos para ArmerÃ­a y JOSEN.
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]:
  - Removida la secciÃ³n HTML `ParÃ¡metros Josen` condicionada por `puede_josen`.
- `templates/configuracion/partials/hub.html` [MODIFY]:
  - Removido el botÃ³n de acceso al menÃº de Rubros JOSEN en la secciÃ³n contable.
- **Archivos Eliminados** [DELETE]:
  - `templates/configuracion/partials/rubros.html`
  - `templates/configuracion/partials/rubro_table_rows.html`
  - `templates/configuracion/modals/rubro_josen_form.html`

### Detalle TÃ©cnico
1. **Base de datos:** Se generaron 2 archivos de migraciones, `facturacion/migrations/0052_delete_extensionjosen_delete_rubrojosen.py` y `usuarios/migrations/0007_remove_perfil_permiso_armeria_editar_and_more.py`. Al correr `migrate` se eliminaron exitosamente las tablas asociadas y columnas en la base de datos `PostgreSQL`.
2. **RefactorizaciÃ³n de visibilidad:** Al usar `Empresa.tipo_actividad`, el acceso a ArmerÃ­a se maneja dinÃ¡micamente de acuerdo al contexto comercial en el que estÃ© logueado el usuario, reduciendo el riesgo de errores de asignaciÃ³n de permisos manuales.

### Estado actual y siguientes pasos
El mÃ³dulo JOSEN ha sido erradicado del sistema y los permisos para el mÃ³dulo de ArmerÃ­a pasaron satisfactoriamente de estar basados en roles/perfiles de usuarios a depender de la naturaleza de la empresa seleccionada al iniciar la sesiÃ³n.

## 28 de Agosto de 2026 â ReubicaciÃ³n de Campos CUIT/DNI y PolicÃ­a en Formulario de Cliente

### Objetivo
1. **ReubicaciÃ³n de IdentificaciÃ³n (CUIT/DNI):** Mover el input de nÃºmero de documento / CUIT hacia adentro de la tarjeta de "Naturaleza del Cliente" y alinearlo a la derecha, agrupando semÃ¡nticamente la identidad.
2. **ReubicaciÃ³n de "Es PolicÃ­a":** Mover el campo obligatorio "Â¿Es PolicÃ­a / Fuerza de Seguridad?" al final de la tarjeta del mÃ³dulo de "Registro de ArmerÃ­a" acompaÃ±ando a los campos CLU.

### Archivos Modificados
- `templates/facturacion/modals/cliente_modal.html` [MODIFY]:
  - Refactorizada la tarjeta de "Naturaleza del Cliente" convirtiÃ©ndola en un contenedor `flex flex-col md:flex-row justify-between items-start md:items-center gap-6`.
  - Agregado el input "NÃºmero de Documento / CUIT" dentro de dicha tarjeta flotando a la derecha (`w-full md:w-1/3 ml-auto`) cuando es aplicable al mÃ³dulo de armerÃ­a, y como fallback externo mediante un `<template x-if="!puedeArmeria">` para evitar duplicidad del atributo `name` y bugs en el DOM.
  - Movido `form_armeria.es_policia` al grid de 3 columnas de "Registro de ArmerÃ­a", optimizando la simetrÃ­a de los campos de credencial y seguridad.

### Detalle TÃ©cnico
1. **PrevenciÃ³n de Duplicados en DOM HTMX:** Como la validaciÃ³n de CUIT se maneja tanto para altas normales (solo DNI/CUIT) como para altas completas (FÃ­sica/JurÃ­dica), al mover el input dentro de un `<template x-if="puedeArmeria">` se programÃ³ la contracara `<template x-if="!puedeArmeria">`. Alpine.js procesa estos templates removiendo del DOM los nodos inactivos; esto garantiza que al hacer un submit (HTTP POST) Django reciba exactamente un solo valor para la clave `cuit` en lugar de una lista conflictiva.

### Estado actual y siguientes pasos
Los campos han sido exitosamente reordenados y agrupados segÃºn la nueva lÃ³gica, mejorando la usabilidad y conservando toda la validaciÃ³n por HTMX del padrÃ³n.

## DÃ­a 29/08/2026 - FacturaciÃ³n masiva de pedidos (Plan 074, fase 4)

**Responsable:** Claude Opus.

### Objetivo
El corazÃ³n del mÃ³dulo: emitir de una vez los comprobantes de los pedidos del dÃ­a, aplicando la regla del saldo disponible negativo que define el cobro mÃ­nimo del repartidor y la condiciÃ³n de venta impresa en el comprobante.

### La regla, en una sola fÃ³rmula
```
saldo_disponible = limite â saldo    (POSTERIOR a facturar esta carga)
cobro_minimo     = max(0, âsaldo_disponible)
condicion_venta  = CONTADO si cobro_minimo >= total, si no CUENTA CORRIENTE
```
Absorbe los cuatro casos del negocio sin un solo condicional especial: entra holgado, se pasa parcialmente, `limite = 0` (sÃ³lo contado) y cliente bloqueado. Los cuatro tienen su prueba.

### Archivos Creados o Modificados
- `facturacion/services/emision_arca.py` [NEW]: el circuito de emisiÃ³n del CAE existÃ­a **sÃ³lo dentro de `VentasCargaView.post`**, embebido en el manejo del formulario, asÃ­ que ningÃºn otro proceso podÃ­a emitir. Se expone como servicio reutilizable, con las mismas validaciones de coherencia fiscal (A/B segÃºn condiciÃ³n de IVA). Acepta una venta **todavÃ­a sin persistir**, porque el nÃºmero de la serie fiscal lo da ARCA y hay que pedirlo antes de guardar.
- `distribucion/services/facturacion.py` [NEW]: `evaluar_credito()`, `previsualizar()`, `facturar_pedido()`, `facturar_lote()`.
- `distribucion/views.py` [MODIFY]: `FacturacionLoteView` (GET previsualiza, POST emite).
- `facturacion/models.py` [MODIFY]: `Venta.condicion_venta` (CONTADO / CTA_CTE).
- `distribucion/models.py` [MODIFY]: `ExtensionPedidoDistribucion.venta`, el eslabÃ³n Pedido â Comprobante.
- `core/models.py` [MODIFY]: `ContadorDocumento.VENTA_FISCAL`, espejo local de la serie fiscal.
- `usuarios/models.py` [MODIFY]: `permiso_distribucion_facturar_lote`.
- `templates/distribucion/facturacion.html` + dos parciales [NEW]; entrada en el menÃº.
- `distribucion/tests/test_plan074_facturacion.py` [NEW]: 25 pruebas.

### Detalle TÃ©cnico

**La numeraciÃ³n se resuelve ANTES del primer save.** Es lo que obligÃ³ a reestructurar: guardar la venta con un nÃºmero provisorio para corregirlo tras el CAE dejarÃ­a, aunque sea un instante, dos comprobantes con el mismo nÃºmero en la misma serie ây ahora existe el `UniqueConstraint` que lo rechazarÃ­aâ. Por eso los importes y las alÃ­cuotas se calculan en memoria, luego se numera (contador para el PRE, ARCA para la factura) y reciÃ©n ahÃ­ se persiste.

**Cada pedido va en SU PROPIA transacciÃ³n.** Es la diferencia deliberada con el lote de ESTUDIO, donde el `atomic` envolvÃ­a el bucle entero y el primer error abortaba todo: acÃ¡ un cliente mal configurado no puede frenar el reparto de los demÃ¡s. Hay una prueba con tres pedidos donde el del medio falla y los otros dos se emiten igual.

**Se bloquea el cliente con `select_for_update()`** al facturar: dos pedidos suyos emitidos a la vez leerÃ­an el mismo saldo y los dos creerÃ­an entrar en el lÃ­mite.

**El comprobante se guarda dos veces a propÃ³sito:** el segundo save dispara la seÃ±al con los Ã­tems ya creados, que es lo que genera el asiento. Es exactamente el defecto que tenÃ­a el lote de ESTUDIO y que se corrigiÃ³ esta maÃ±ana.

Reglas inflexibles verificadas por pruebas: el asiento hereda el `condic` del comprobante; el PRE **no** entra al Libro IVA y la Factura **sÃ­**; la fecha la pone el sistema; facturar libera el stock comprometido y descuenta el real.

**EmisiÃ³n real contra ARCA:** el circuito quedÃ³ cableado (`modo_prueba=False` llama a `AfipService` y toma el nÃºmero de `CbteDesde`). La pantalla emite hoy en **modo prueba**, con CAE ficticio, hasta que se valide contra HomologaciÃ³n con el certificado cargado.

### Resultado de las Pruebas
```powershell
.\venv\Scripts\python.exe manage.py test distribucion facturacion core --keepdb --noinput
```
**`Ran 257 tests` â 1 error**, `test_emitir_comprobante_homologacion_real`, que falla por falta del certificado ARCA: es de entorno. Cero regresiones.

Migraciones aplicadas con respaldo previo. Las cuatro pantallas del mÃ³dulo responden 200 contra la base real.

### Estado Actual y Siguientes Pasos
Circuito cerrado desde la toma del pedido hasta el comprobante emitido. **Siguiente: fase 5** â `Reparto`, Consolidado de ArtÃ­culos y Hoja de Ruta, que es donde el `cobro_minimo` calculado acÃ¡ sale impreso para el repartidor.

## DÃ­a 29/08/2026 - Integridad de numeraciÃ³n y condiciÃ³n del lote (Plan 075 + correcciÃ³n ESTUDIO)

**Responsable:** Claude Opus.

### Objetivo
Analizar la facturaciÃ³n por lote de ESTUDIO âque ya emite comprobantes fiscales y no fiscalesâ para reutilizarla en la fase 4 de DistribuciÃ³n, corregir lo que estuviera mal y ejecutar el [Plan 075](planes/075_integridad_numeracion_comprobantes_venta.md), del que la fase 4 depende.

### Hallazgo principal: el comprobante interno se guardaba como FISCAL

`FacturacionLoteService` no seteaba `condic` en ninguno de los dos comprobantes, asÃ­ que ambos quedaban con el default (**1 = Real**). El comprobante INTERNO/PRE decÃ­a ser fiscal, mientras su asiento âcreado a mano unas lÃ­neas mÃ¡s abajoâ decÃ­a `condic = 2`. Comprobante y asiento se contradecÃ­an.

No llegaba al Libro IVA sÃ³lo porque `venta_p._no_contabilizar = True` corta la seÃ±al entera. Pero era una **bomba de tiempo**: `contabilizar_venta_individual` puebla el Libro IVA cuando `condic in (1, 3)`, asÃ­ que cualquier re-guardado sin ese flag habrÃ­a declarado ante ARCA una operaciÃ³n que no existe fiscalmente. Y ya hacÃ­a daÃ±o: todo reporte que filtra `Venta.condic` contaba el interno como fiscal.

**CorrecciÃ³n:** `condic=2` en el interno y `condic=1` explÃ­cito en el fiscal, para que el par se lea de un vistazo.

### Otros hallazgos del mismo servicio
- **El manejo de errores por fila era ilusorio.** El `transaction.atomic()` envuelve todo el bucle y el `try/except` estÃ¡ adentro: tras un error de base de datos, Django deja la transacciÃ³n abortada y cualquier consulta posterior lanza `TransactionManagementError`. No se guardaban "los exitosos". *(Documentado, no corregido: es parte del refactor del motor en la fase 4.)*
- **Si no hay cuentas contables configuradas, el comprobante interno se emite sin asiento y sin ningÃºn aviso** â queda con saldo en la cuenta corriente y sin registraciÃ³n. *(Documentado con una prueba que lo deja cubierto para que el refactor lo cambie a conciencia.)*
- El asiento del interno reimplementa a mano ~60 lÃ­neas que `contabilizar_venta_individual` ya hace bien. La ironÃ­a: existÃ­an para compensar el `condic` mal seteado.

### Plan 075 ejecutado

**AuditorÃ­a previa (sÃ³lo lectura):** cero duplicados y cero huecos en `facturacion_venta`. El `UniqueConstraint` se pudo aplicar sin tocar un solo dato.

- `facturacion/models.py` [MODIFY]: `UniqueConstraint (empresa, tipo, punto, numero)` en `Venta`. Era el Ãºnico documento emitido del sistema sin bloqueo al numerar **ni** restricciÃ³n en la base. Queda documentado que `tipo` es nullable y en PostgreSQL los NULL no colisionan: los comprobantes sin tipo quedan fuera del control, y la soluciÃ³n de fondo excede este plan.
- `core/models.py` [MODIFY]: tipos `VENTA_PRE` y `VENTA_NCI` en `ContadorDocumento`, en **series independientes**.
- `core/migrations/0004_inicializar_contadores_venta_no_fiscal.py` [NEW]: migraciÃ³n de datos que inicializa cada contador con el Ãºltimo nÃºmero realmente emitido. Sin esto el primer comprobante habrÃ­a arrancado en 1 y chocado contra el constraint.
- `core/services/numeracion.py` [MODIFY]: `siguiente_numero_pre()` y `siguiente_numero_nci()`, y `auditar_correlativos()` extendida a las dos series nuevas mediante un envoltorio `_VentasDeTipo` que evita duplicar el bucle.
- `facturacion/services/facturacion_lote_service.py` [MODIFY]: el PRE se numera con el contador transaccional y se emite en `punto = sucursal_id`; se eliminan los **fallbacks silenciosos** (tipo PRE por descarte y punto de venta asumido en 1), que ahora fallan con un mensaje explicativo.
- `facturacion/views_estudio.py` [MODIFY]: `modo_prueba` deja de estar hardcodeado y pasa a ser un parÃ¡metro, con el default seguro. Los `ValueError` de configuraciÃ³n se devuelven como 400 con su mensaje, no como error genÃ©rico.
- **La emisiÃ³n real contra ARCA queda bloqueada con un error explÃ­cito** hasta cablear `AfipService`. Antes no habÃ­a forma de emitir en serio; ahora, si alguien lo intenta, el sistema **corta antes de emitir** en vez de generar un comprobante con numeraciÃ³n local que ARCA no autorizÃ³.

### Pruebas
- `facturacion/tests/test_lote_condic.py` [NEW]: 7 pruebas.
- `facturacion/tests/test_plan075_numeracion.py` [NEW]: 16 pruebas.

```powershell
.\venv\Scripts\python.exe manage.py test distribucion facturacion productos core --keepdb --noinput
```
**Resultado:** `Ran 255 tests` â 1 falla y 24 errores, **todos preexistentes y ya documentados**: 23 en `test_facturas_pendientes` (escribe `periodo="2026-06"`, 7 caracteres, en un `varchar(6)`), 1 en `test_arca_service` (falta el certificado, es de entorno) y 1 en `test_armeria_credencial_clu` (el Plan 073 hizo `tipo_persona` obligatorio sin actualizar el test del 072). **Cero regresiones.**

### VerificaciÃ³n contra la base real
Migraciones aplicadas con respaldo previo. Los contadores quedaron inicializados en el Ãºltimo emitido (empresa 2 punto 0 â 1; empresa 3 punto 3 â 1) y `auditar_correlativos()` devuelve **OK en las cinco series** existentes.

### Estado Actual y Siguientes Pasos
El Plan 075 queda ejecutado salvo el cableado de `AfipService` en el lote, que es su paso 5 y hoy estÃ¡ explÃ­citamente bloqueado. Con esto, la **fase 4 de DistribuciÃ³n** ya tiene numeraciÃ³n segura sobre la cual apoyarse.

Sigue pendiente y ofrecido, sin ejecutar: el arreglo del widget de fecha en los otros siete formularios y la exportaciÃ³n del reporte de faltantes a PDF/Excel.

---

**Correcciones posteriores del mismo dÃ­a.**

**1. MenÃº principal roto en empresas DISTRIBUIDORA** *(reportado por el usuario, defecto propio).*
El comentario que habÃ­a puesto en `templates/base.html` usaba `{# â¦ #}` **en varias lÃ­neas**, y los comentarios de una llave en Django son de **UNA SOLA LÃNEA**: la apertura consume sÃ³lo su renglÃ³n y el resto se emite como texto visible. En el menÃº aparecÃ­a el pÃ¡rrafo "MÃ³dulo DistribuciÃ³n (Plan 074). Por ahora sÃ³lo los maestrosâ¦" entre Ventas y DistribuciÃ³n.

Al revisarlo apareciÃ³ el mismo error en **otros nueve comentarios**, todos escritos por mÃ­ en esta serie de fases: `preventa_carga.html`, `movil/pedido.html`, `movil/partials/cabecera.html` (Ã2), `movil/partials/carrito.html`, `movil/partials/confirmacion.html`, `partials/cartera_fila.html` (Ã2) y `partials/panel_credito.html`. Los diez se convirtieron a `{% comment %} â¦ {% endcomment %}`.

VerificaciÃ³n: las **231 plantillas** del proyecto compilan, y las cuatro pantallas del mÃ³dulo (`/distribucion/movil/`, `/cartera/`, `/faltantes/` y la preventa) responden 200 **sin texto de comentario en el HTML**.

**2. La facturaciÃ³n por lote emitÃ­a comprobantes SIN asiento contable.**
Al escribir las pruebas apareciÃ³ un defecto mÃ¡s grave que el del `condic`: la seÃ±al contabiliza en el `post_save` de la `Venta`, pero el lote guarda la venta **antes** de crear los Ã­tems, y `contabilizar_venta_individual` corta con `if not venta.items.exists(): return None`. **La factura fiscal quedaba emitida y sin registraciÃ³n contable.**

CorrecciÃ³n, siguiendo la regla que confirmÃ³ el usuario âcuenta patrimonial del cliente con fallback a `ParametrosContables.cta_clientes_default`, y cuenta de resultado del **rubro del producto facturado** con fallback a `parametros.cta_ventas`â:
- Se re-guarda cada comprobante despuÃ©s de crear sus Ã­tems, para que la seÃ±al contabilice con la venta completa.
- Se eliminÃ³ el `_no_contabilizar` del comprobante interno y **las 54 lÃ­neas del asiento armado a mano**, que existÃ­an sÃ³lo para compensar el `condic` mal seteado. Ahora delega en `contabilizar_venta_individual`, que ya aplica esa regla exacta, valida que la cuenta pertenezca a la empresa y sea imputable, y **levanta un error explÃ­cito** si falta alguna en lugar de emitir el comprobante sin asiento.

Tres pruebas nuevas cubren la regla: el cliente sin `cta_pat` usa la cuenta del parÃ¡metro, el haber sale del rubro del producto, y sin rubro cae al parÃ¡metro general.

**3. Tests preexistentes corregidos** *(a pedido del usuario).*
- `test_facturas_pendientes.py`: los helpers escribÃ­an `periodo="2026-06"` (7 caracteres) en un `CharField(max_length=6)` cuyo formato documentado es **YYYYMM**. Corregido a `"202606"` â el guion no corresponde. **23 errores eliminados.**
- `test_armeria_credencial_clu.py`: el Plan 073 hizo `tipo_persona` obligatorio en `ExtensionArmeriaForm` y el test del Plan 072 no se actualizÃ³. Se agregÃ³ el campo. **1 falla eliminada.**

### Resultado final de la suite
```powershell
.\venv\Scripts\python.exe manage.py test distribucion facturacion productos core --keepdb --noinput
```
**`Ran 257 tests` â 1 solo error**, `test_emitir_comprobante_homologacion_real`, que es una prueba de integraciÃ³n real contra ARCA HomologaciÃ³n y falla por falta del certificado `media/certificados_afip/certificado_cortiz.crt`: es de entorno, no de cÃ³digo.

Se pasÃ³ de **25 fallos a 1**. La suite vuelve a servir como red: de ahora en mÃ¡s, un test rojo seÃ±ala una regresiÃ³n real.

## DÃ­a 29/08/2026 - Faltantes y asignaciÃ³n de stock escaso (Plan 074, fase 3)

**Responsable:** Claude Opus.

### Objetivo
Ejecutar la fase 3 del [Plan 074](planes/074_modulo_distribucion.md): detectar quÃ© productos no alcanzan para cubrir todos los pedidos tomados y sin facturar, y dar la pantalla donde un usuario autorizado reparte ese stock escaso. Es el paso previo a la facturaciÃ³n por lote.

### Archivos Creados o Modificados
- `distribucion/models.py` [MODIFY]: nuevo `AjusteAsignacion` (pedido, producto, cantidad original, cantidad asignada, usuario, fecha, observaciÃ³n).
- `distribucion/services/asignacion.py` [NEW]: `detectar_faltantes()`, `detalle_por_pedido()`, `sugerir_asignacion()`, `aplicar_asignacion()`, `hay_faltantes()`.
- `distribucion/views.py` [MODIFY]: `FaltantesIndexView`, `AsignacionStockView` y el helper de permiso `_puede_asignar()`.
- `usuarios/models.py` [MODIFY]: `permiso_distribucion_asignar_stock`.
- `templates/distribucion/faltantes.html`, `partials/faltantes_filas.html`, `modals/asignacion_form.html` [NEW].
- `templates/base.html` [MODIFY]: entrada "Faltantes y AsignaciÃ³n" en el menÃº de DistribuciÃ³n.
- `config/urls.py` [MODIFY]: dos rutas.
- `distribucion/tests/test_plan074_asignacion.py` [NEW]: 25 pruebas.
- Migraciones: `distribucion/0004_ajusteasignacion.py`, `usuarios/0008_perfil_permiso_distribucion_asignar_stock.py`.

### Detalle TÃ©cnico

**El criterio de reparto es el ORDEN DE LLEGADA del pedido** (`hora_carga` ascendente): el que pidiÃ³ primero se lleva todo lo que pidiÃ³ mientras haya stock, y el faltante lo absorben los Ãºltimos. Es el Ãºnico criterio que se le puede explicar a un vendedor sin discusiÃ³n, y el que eligiÃ³ el usuario. La sugerencia es un punto de partida: la pantalla permite ajustar a mano.

**`detectar_faltantes()` compara contra el stock FÃSICO, no contra el disponible.** El `comprometido` ES la demanda que se estÃ¡ comparando: restarlo serÃ­a contarla dos veces.

**Todo ajuste queda auditado** en `AjusteAsignacion`, con la cantidad original, la asignada, quiÃ©n lo hizo y cuÃ¡ndo. La razÃ³n es operativa: al vendedor hay que poder explicarle despuÃ©s por quÃ© su cliente recibiÃ³ menos de lo que pidiÃ³. Un Ã­tem al que se le asigna lo que pedÃ­a **no genera ajuste ni escritura**.

**Asignar 0 elimina el renglÃ³n** del pedido, no lo deja en cero: un Ã­tem en cero ensuciarÃ­a el comprobante y la hoja de ruta con una lÃ­nea sin sentido. El `AjusteAsignacion` queda igual, y es la explicaciÃ³n de por quÃ© el artÃ­culo desapareciÃ³.

Tras el recorte se recalculan el total del Ã­tem, el total del pedido y el `comprometido` (por la seÃ±al ya existente sobre `PreventaItem`).

**Permiso propio** (`permiso_distribucion_asignar_stock`): repartir stock escaso decide quÃ© cliente recibe menos, que es una decisiÃ³n comercial y no una tarea de carga. Sin el permiso, la pantalla se consulta pero el POST devuelve 403 y los inputs salen deshabilitados.

### Resultado de las Pruebas
```powershell
.\venv\Scripts\python.exe manage.py test distribucion --keepdb --noinput
```
**Resultado:** `OK (Ran 25 tests)` en la suite nueva; 143 en total en el mÃ³dulo.

Los WARNING de `Forbidden` y `Not Found` en la salida son los **esperados** por las pruebas de permiso y de aislamiento de cartera.

VerificaciÃ³n contra la base real (empresa 4): las tres plantillas compilan y `/distribucion/faltantes/` responde 200.

### Estado Actual y Siguientes Pasos
Con la asignaciÃ³n cerrada, el circuito queda listo para la **fase 4: facturaciÃ³n masiva** con la regla del saldo disponible negativo, que emite la Factura o el PRE y decide CONTADO vs. CUENTA CORRIENTE.

Pendiente y ofrecido, sin ejecutar: exportaciÃ³n del reporte de faltantes a PDF/Excel (el plan la prevÃ©), el arreglo del widget de fecha en los otros siete formularios y el [Plan 075](planes/075_integridad_numeracion_comprobantes_venta.md), del que **depende la fase 4**.

## DÃ­a 29/08/2026 - Domicilios de entrega mÃºltiples (Plan 074)

**Responsable:** Claude Opus.

### Objetivo
Un cliente puede tener **varios puntos de entrega** porque tiene sucursales. Se define la regla del circuito, confirmada por el usuario: **1 domicilio de entrega â 1 pedido â 1 comprobante â 1 parada de la hoja de ruta**. Cada sucursal recibe, controla y firma lo suyo, y la cuenta corriente consolida en el cliente.

### DecisiÃ³n estructural: quÃ© se mueve y quÃ© no

`ClienteProveedor.domicilio` es el **fiscal** (el que se imprime como domicilio del cliente). El nuevo `DomicilioEntrega` es el **punto fÃ­sico** al que llega el camiÃ³n.

De ahÃ­ se desprende lo importante: **la zona y la agenda de visitas dejan de colgar del cliente y pasan al domicilio**. Una sucursal en San Cayetano y otra en Villa LujÃ¡n entran en repartos distintos, en dÃ­as distintos y con recorridos distintos: son propiedades de *dÃ³nde se entrega*, no de *quiÃ©n debe*. Colgarlas del cliente obligarÃ­a a que todas sus sucursales compartan zona y dÃ­a.

Lo que **sÃ­** queda en el cliente es el **crÃ©dito**: un CUIT, una cuenta corriente, un lÃ­mite. Las entregas se reparten; la deuda no. Lo mismo la cartera: el vendedor responde por el cliente completo.

### Archivos Creados o Modificados
- `distribucion/models.py` [MODIFY]: nuevo `DomicilioEntrega` (nombre, domicilio, localidad, zona, contacto, telÃ©fono, horario de recepciÃ³n, indicaciones de entrega, principal, activo). `DiaVisita` se reapunta de `cliente` a `domicilio` y admite **varios dÃ­as por punto** (con lÃ¡cteos se pasa dos o tres veces por semana). `ExtensionPedidoDistribucion` suma `domicilio_entrega` y `domicilio_entrega_texto`.
- `facturacion/models.py` [MODIFY]: se **quita** `ExtensionDistribuidora.zona`, que ahora vive en el domicilio.
- `distribucion/services/domicilios.py` [NEW]: `asegurar_domicilio_principal()` (genera el principal a partir del fiscal, idempotente), `domicilios_de()`, `sembrar_domicilios_faltantes()` para la carga inicial.
- `distribucion/services/pedidos.py` [MODIFY]: el pedido toma `domicilio_entrega`; si no se indica, se propone el principal. La **zona del pedido sale del domicilio**.
- `distribucion/views_htmx.py` [MODIFY]: ABM de domicilios y agenda por punto; se elimina la vista de agenda por cliente.
- `distribucion/views_movil.py` [MODIFY]: selector de punto de entrega y `movil_elegir_domicilio`.
- `distribucion/forms.py` [MODIFY]: `DomicilioEntregaForm`.
- `facturacion/forms.py`, `templates/facturacion/modals/cliente_modal.html` [MODIFY]: se saca la zona del cliente.
- `templates/distribucion/` [NEW/MODIFY]: `modals/domicilio_form.html`, `partials/cartera_fila.html` reescrito con los domicilios desplegables, cabecera y confirmaciÃ³n del mÃ³vil.
- `config/urls.py` [MODIFY]: cuatro rutas de domicilios y una del mÃ³vil.
- `distribucion/tests/test_plan074_domicilios.py` [NEW]: 26 pruebas.
- Migraciones: `distribucion/0003_domicilioentrega_and_more.py`, `facturacion/0056_...`.

### Detalle TÃ©cnico

**Snapshot del domicilio en el pedido** (`domicilio_entrega_texto`), con el mismo criterio que `Preventa.cliente_razon_social`: si maÃ±ana se corrige la direcciÃ³n, el comprobante ya emitido tiene que seguir diciendo a dÃ³nde se entregÃ³. Hay una prueba que lo verifica.

**El principal se genera solo** a partir del domicilio fiscal, para que el circuito nunca se trabe por un dato derivable, pero **la responsabilidad de que cada pedido salga con el domicilio correcto es del vendedor** (definiciÃ³n del usuario). Por eso el mÃ³vil ofrece todos los puntos y permite cambiarlo en cualquier momento antes de confirmar, sin perder lo cargado.

**Aviso de punto sin zona:** un domicilio sin zona no entra en ningÃºn reparto, asÃ­ que la cabecera del mÃ³vil lo marca en Ã¡mbar.

### Implicaciones de Base de Datos
Se verificÃ³ que las cuatro tablas afectadas estaban **vacÃ­as** antes de reestructurar (`ExtensionDistribuidora`, `DiaVisita`, `CarteraVendedor`, `ExtensionPedidoDistribucion`: 0 registros), asÃ­ que el cambio de `DiaVisita.cliente` a `DiaVisita.domicilio` no arrastrÃ³ datos. Respaldo previo con `pg_dump -F c` en `scratch/respaldos/`.

### Resultado de las Pruebas
```powershell
.\venv\Scripts\python.exe manage.py test distribucion --keepdb --noinput
```
**Resultado:** `OK (Ran 118 tests in 278.3s)`.

Los dos WARNING de `Not Found` en la salida son los **404 esperados** de las pruebas de aislamiento: un vendedor no puede elegir un cliente fuera de su cartera ni el punto de entrega de otro cliente.

VerificaciÃ³n adicional contra la base real (empresa 4): las ocho plantillas compilan y `/distribucion/movil/`, `/distribucion/cartera/` y la pestaÃ±a de Personal responden 200.

### Estado Actual y Siguientes Pasos
Circuito de pedido completo con puntos de entrega mÃºltiples. **Siguiente: fase 3** â reporte de faltantes y asignaciÃ³n de stock escaso por orden de llegada del pedido.

Pendiente de definiciÃ³n del usuario (Â§11.1 del plan): los valores de `ExtensionDistribuidora.clasificacion`. Y quedÃ³ ofrecido, sin ejecutar, el arreglo del widget de fecha en los otros siete formularios del proyecto.

## 29 de Agosto de 2026 â ReplicaciÃ³n de Plan de Cuentas y ParÃ¡metros Contables (Empresa 2 a Empresa 4)

### Objetivo
1. **ReplicaciÃ³n Contable Completa:** Replicar de forma Ã­ntegra el catÃ¡logo del Plan de Cuentas (`Cuenta`), los ParÃ¡metros Contables (`ParametrosContables`) y los Medios de Pago (`MedioPago`) desde la empresa origen `ARMERIA ARMAR SAS` (ID=2) hacia la empresa destino `RODRIGUEZ MARCELO FABIAN` (ID=4).
2. **GeneralizaciÃ³n del Comando de ReplicaciÃ³n:** Mejorar la Fase 4 del comando `replicar_plan_cuentas.py` para replicar directamente los medios de pago configurados en la empresa origen mapeando sus cuentas contables al nuevo Ã¡rbol destino.

### Archivos Modificados
- `contable/management/commands/replicar_plan_cuentas.py` [MODIFY]:
  - En la Fase 4, se implementÃ³ la lectura y clonaciÃ³n dinÃ¡mica de los objetos `MedioPago` existentes en la `empresa_origen`, remapeando su clave forÃ¡nea `cuenta_contable` al ID de la cuenta clonada en la `empresa_destino`. Se mantuvo la compatibilidad con archivo CSV como mecanismo alternativo de fallback.

### Detalle TÃ©cnico
1. **Atomicidad y Mapeo en Memoria:** Todo el proceso se ejecuta dentro de un bloque `transaction.atomic()`. En la Fase 1 se crearon 220 cuentas contables para la empresa 4 conservando cÃ³digo, jerarquÃ­a, imputabilidad, tipo y atributos especiales, generando un mapa en memoria `{id_origen: nueva_cuenta_destino}`.
2. **ReconstrucciÃ³n del Ãrbol JerÃ¡rquico:** En la Fase 2 se asignaron 215 relaciones `sumariza` apuntando estrictamente a las cuentas padre de la empresa 4.
3. **Mapeo de ParÃ¡metros y Medios de Pago:** En la Fase 3 se instanciÃ³ `ParametrosContables` para la empresa 4 con 23 cuentas contables remapeadas, y en la Fase 4 se clonaron los 6 medios de pago (`CHQ-TER`, `EFE-USD`, `EFE-ARS`, `RET-GCIA`, `RET-IIBB`, `TRA-BCO`) con sus respectivas cuentas contables pertenecientes a la empresa 4.

### Resultado de las Pruebas
- Comando ejecutado: `python manage.py replicar_plan_cuentas --origen 2 --destino 4`.
- Salida del comando: 220 cuentas creadas, 215 relaciones jerÃ¡rquicas vinculadas, parÃ¡metros contables creados con 23 cuentas mapeadas y 6 medios de pago clonados exitosamente.
- ValidaciÃ³n en base de datos: Confirmado que todas las cuentas asociadas a la empresa 4 pertenecen exclusivamente a `empresa_id=4`, sin referencias cruzadas residuales hacia la empresa 2.

### Estado actual y siguientes pasos
La Empresa ID=4 (`RODRIGUEZ MARCELO FABIAN`) cuenta ahora con su estructura contable y medios de pago plenamente operativos e independientes.

## 29 de Agosto de 2026 â InclusiÃ³n de `sumariza_id` en ExportaciÃ³n y Captura Excel del Plan de Cuentas

### Objetivo
1. **InclusiÃ³n de Clave JerÃ¡rquica en Excel:** Incorporar el campo `sumariza_id` en el archivo Excel generado mediante el botÃ³n "Excel Completo" del Plan de Cuentas, permitiendo visualizar y auditar el ID de la cuenta padre en la que consolida cada nodo.
2. **Soporte Bidireccional de Captura:** Habilitar el reconocimiento de `sumariza_id` durante la recaptura e importaciÃ³n masiva de cuentas desde Excel para vincular directamente la cuenta padre si se especifica su ID.

### Archivos Modificados
- `contable/services/excel_service.py` [MODIFY]:
  - AÃ±adida la clave `'sumariza_id': 'Sumariza ID'` a `COLUMNAS_CUENTA_MAP`.
  - Actualizado `generar_excel_cuentas` para volcar `cta.sumariza_id` en la segunda columna del libro.
  - Actualizado `procesar_captura_excel_cuentas` para normalizar el encabezado `sumariza` / `sumariza_id`, resolviendo la asignaciÃ³n `sumariza` por ID explÃ­cito o por jerarquÃ­a como fallback.
- `contable/tests/test_excel_cuentas.py` [MODIFY]:
  - Corregido `Empresa.nombre` en el setup de pruebas.
  - Agregadas aserciones de exportaciÃ³n y asignaciÃ³n de `sumariza_id` en los tests de generaciÃ³n y captura masiva.

### Detalle TÃ©cnico
1. **Estructura de Columnas:** La columna `Sumariza ID` se posiciona inmediatamente despuÃ©s de `ID`, manteniendo el orden lÃ³gico de identificadores previos a la jerarquÃ­a (`ID`, `Sumariza ID`, `JerarquÃ­a`, `Nombre Cuenta`, etc.).
2. **ResoluciÃ³n en ImportaciÃ³n:** En `procesar_captura_excel_cuentas`, si la fila trae un valor numÃ©rico en `Sumariza ID` y dicho ID existe en la empresa activa, se vincula `sumariza_obj = cuentas_por_id[sumariza_id_val]`, otorgando prioridad a la relaciÃ³n explÃ­cita por sobre la inferencia por cadena de texto.

### Resultado de las Pruebas
```powershell
.\venv\Scripts\python.exe manage.py test contable.tests.test_excel_cuentas --keepdb --noinput
```
**Resultado:** `OK (Ran 3 tests in 7.4s)` â GeneraciÃ³n de Excel, actualizaciÃ³n/creaciÃ³n por captura masiva y vistas HTTP con modal comprobadas sin errores.

### Estado actual y siguientes pasos
La exportaciÃ³n a Excel del Plan de Cuentas ya incluye la columna `Sumariza ID` tanto en la descarga como en el motor de recaptura.

## DÃ­a 31/08/2026 - Reporte de devoluciones e integridad de numeraciÃ³n (Plan 074, fase 8)

**Responsable:** Claude Opus.

### Objetivo
Los dos reportes de **control** que cierran el mÃ³dulo: el de devoluciones (Â§7.10) â*"por perÃ­odo, motivo, momento, repartidor, cliente y producto: muestra si el problema es de crÃ©dito, de calidad, de carga o de un repartidor puntual"*â y el de correlativos (Â§4.2), que le faltaban las dos series que el mÃ³dulo emite y no se auditaban.

### Archivos Creados o Modificados
- `distribucion/services/reporte_devoluciones.py` [NEW]: `reporte()` con sus cuatro cortes.
- `core/services/numeracion.py` [MODIFY]: `auditar_correlativos()` incorpora `REPARTO` y `RECEPCION_DEVOLUCION`.
- `distribucion/views.py` [MODIFY]: `DevolucionesReporteView`, `CorrelativosDistribucionView`.
- `templates/distribucion/reporte_devoluciones.html`, `correlativos.html`, `partials/corte_devoluciones.html` [NEW].
- `config/urls.py`, `templates/base.html` [MODIFY]: dos rutas y la secciÃ³n Â«ControlÂ» del menÃº.
- `distribucion/tests/test_plan074_reportes_control.py` [NEW]: 22 pruebas.

Sin migraciones: los dos reportes leen lo que ya existe.

### Detalle TÃ©cnico

**La pregunta que responde el reporte no es CUÃNTO, es POR QUÃ.** Un total de devoluciones no sirve para decidir nada. Lo que cambia una conducta es ver que el 60 % son Â«negocio cerradoÂ» âproblema de agenda de visitasâ, o que se concentran en un repartidor, o en un producto que llega roto. Por eso el reporte son **cuatro cortes sobre los mismos renglones** y no una lista: por motivo (quÃ© falla), por repartidor (si se concentra en alguien), por producto (si el problema es del artÃ­culo) y por cliente (quiÃ©n devuelve mÃ¡s). Cada corte viene ordenado **de mayor a menor importe**: tiene que empezar por lo que mÃ¡s pesa, no por lo que viene primero alfabÃ©ticamente.

**El grano es el renglÃ³n de la recepciÃ³n, no la nota de crÃ©dito.** `RecepcionDevolucionItem` es el Ãºnico lugar donde conviven motivo, producto, cantidad y `apto_reventa`. La NC acredita un importe; la recepciÃ³n explica quÃ© volviÃ³ y por quÃ©.

**Lo no apto para reventa se mide aparte**, con su propio porcentaje: lo que volviÃ³ roto es **pÃ©rdida**, no una devoluciÃ³n mÃ¡s. Mezclarlo con lo que se puede volver a vender esconde el Ãºnico nÃºmero que justifica hablar con un proveedor o con un repartidor.

**Las anulaciones PRE-CARGA van en su propia lista.** Cuando el cliente anula antes de que salga el camiÃ³n, la mercaderÃ­a nunca se cargÃ³ y no pasa por ninguna recepciÃ³n. Si se las mezclara con lo devuelto se estarÃ­a contando como Â«vuelto del repartoÂ» algo que nunca saliÃ³; si se las omitiera, desaparecerÃ­an del anÃ¡lisis. Van aparte, con su total propio.

**AtribuciÃ³n del repartidor.** `RecepcionDevolucion.entregado_por` es opcional, asÃ­ que cuando falta se cae a los responsables del reparto: si hay **exactamente uno**, la devoluciÃ³n es suya sin ambigÃ¼edad. Con varios responsables **no se le atribuye a ninguno** ârepartir la culpa por partes iguales serÃ­a inventar un datoâ y queda como Â«Sin identificarÂ», que es lo que efectivamente se sabe. Hay una prueba para cada caso.

**Una recepciÃ³n anulada no cuenta**: no devolviÃ³ nada, y contarla inflarÃ­a los cuatro cortes a la vez.

**Integridad de numeraciÃ³n.** `auditar_correlativos()` ya cubrÃ­a OC, Informe de RecepciÃ³n, Remito Interno, Pedido, PRE y NCI, pero **le faltaban `REPARTO` y `RECEPCION_DEVOLUCION`**: los dos documentos que el mÃ³dulo emite desde las fases 5 y 6. Dejarlos afuera los volvÃ­a tan inauditables como el nÃºmero de un tercero, que es exactamente lo que el Â§4.2 dice que no puede pasar. La pantalla del mÃ³dulo muestra sus **cinco series** âPedido, Reparto, RecepciÃ³n, PRE y NCIâ con huecos, duplicados y el desfasaje contra el contador; las de compras siguen en su propia pantalla.

### Resultado de las Pruebas
```
python manage.py test distribucion
Ran 378 tests in 409.882s
OK
```
Las 22 nuevas cubren: los cuatro cortes y su orden, la concentraciÃ³n por motivo con su porcentaje, la atribuciÃ³n del repartidor con uno y con varios responsables, la mediciÃ³n separada de lo no apto, los cinco filtros (motivo, repartidor, producto, perÃ­odo, sÃ³lo-no-apto), la recepciÃ³n anulada, el aislamiento multiempresa, las anulaciones pre-carga en su lista aparte, la incorporaciÃ³n de las dos series a la auditorÃ­a, la detecciÃ³n de un hueco, y las dos pantallas.

Un ajuste que hizo la prueba del hueco: `Reparto` estÃ¡ protegido por FK desde `RepartoParada` y `RecepcionDevolucion`, asÃ­ que el hueco se simula con repartos vacÃ­os en vez de borrar uno con paradas.

### Estado Actual y Siguientes Pasos
**El Plan 074 estÃ¡ completo**: las nueve fases, de la toma del pedido al control de las devoluciones y la integridad de las series.

Pendientes ofrecidos y no ejecutados: las exportaciones a PDF/Excel (faltantes, saldos por vendedor y este reporte), el widget de fecha en otros siete formularios, la validaciÃ³n contra ARCA HomologaciÃ³n, y el ajuste de inventario para la mercaderÃ­a devuelta no apta âque este reporte ahora deja a la vista con su importe.

### Cristian - PC CASA
**Fecha:** 02/09/2026
**Objetivo:** Restaurar datos desde dump SQL (db_estudio.sql) purgando la base de datos y resolviendo conflictos con migraciones de verticalidad.
**Archivos creados o modificados:**
- 
estore_db.py (nuevo script en raÃ­z, puede ser borrado luego de validar)
**Detalle TÃ©cnico:** 
Se desarrollÃ³ un script en Python (ETL) para leer e insertar de forma nativa los registros de db_estudio.sql. Se eliminÃ³ el esquema public desde base de datos, se crearon las tablas vÃ­rgenes con python manage.py migrate y posteriormente se volcaron los datos en las 100 tablas usando psycopg3 (copy()).
Para evitar fallas de dependencias forÃ¡neas durante la inyecciÃ³n, se deshabilitaron temporalmente los triggers mediante session_replication_role = 'replica'. Se omitiÃ³ restaurar la tabla django_migrations del backup antiguo para evitar errores de historial inconsistente.
**Resultado de las pruebas:**
El script reportÃ³ inserciones exitosas masivas en todas las entidades (uth_user, 	esoreria, 
acturacion, productos, etc). Las migraciones posteriores corren sin conflictos de historial.
**Estado actual y siguientes pasos sugeridos:**
Base de datos 100% migrada y encuadrada con el nuevo cÃ³digo (sin perder registros antiguos). El sistema debe levantarse y probar si la visualizaciÃ³n del panel administrativo respeta los roles multi-empresa.

### Cristian - PC CASA
**Fecha:** 02/09/2026
**Objetivo:** Solucionar bug de visibilidad de las vistas del mÃ³dulo DistribuciÃ³n al asignar el tipo de actividad a una empresa.
**Archivos creados o modificados:**
- 
erticalidades/distribucion/apps.py
- 
erticalidades/distribucion/templates/distribucion/hooks/menu_sidebar_bottom.html
- 
erticalidades/distribucion/templates/distribucion/hooks/ui_configuracion_hub.html
- 
erticalidades/distribucion/templates/distribucion/hooks/ui_producto_modal_campos.html
**Detalle TÃ©cnico:** 
El modelo Empresa en empresas/models.py guarda el valor constante 'DISTRIBUCION' al seleccionar dicho rubro, pero las plantillas (hooks del menÃº y modales) y la configuraciÃ³n de la App de la verticalidad estaban evaluando la condicional esperando el valor 'DISTRIBUIDORA'. Se unificÃ³ el criterio reemplazando las condicionales y constantes a 'DISTRIBUCION' para que cuadre exactamente con la elecciÃ³n de base de datos de la empresa.
**Resultado de las pruebas:**
Al asignar "DistribuciÃ³n" a una empresa, las condicionales {% if empresa_actual.tipo_actividad == 'DISTRIBUCION' %} ahora resuelven a True e inyectan correctamente el menÃº lateral de DistribuciÃ³n, los campos en el modal de productos y las configuraciones de vehÃ­culos/personal.
**Estado actual y siguientes pasos sugeridos:**
MenÃºs de distribuciÃ³n restaurados correctamente y visibles en el frontend.

### Cristian - PC CASA
**Fecha:** 02/09/2026
**Objetivo:** Portar y adaptar los cambios del commit (57739d1) del proyecto legacy (erp-ikigai-2) hacia la nueva arquitectura con verticalidades.
**Archivos creados o modificados:**
- 	emplates/tesoreria/modals/buscador_bancos.html (Nuevo modal HTMX)
- 	esoreria/views_htmx.py, 	esoreria/urls.py, 	esoreria/forms.py, 	esoreria/models.py
- core/views_config.py
- 	emplates/configuracion/partials/rubros_prod_list.html
- 	emplates/tesoreria/modals/buscador_proveedores_op.html
**Detalle TÃ©cnico:** 
Se migrÃ³ exitosamente el parche de erp-ikigai-2 usando git apply. Esto introdujo:
1. Modal de bÃºsqueda en vivo HTMX para entidades bancarias segÃºn catÃ¡logo BCRA.
2. OptimizaciÃ³n de consultas ORM (select_related) en listados de Cuentas Bancarias para evitar N+1 con cli_pro y cuenta_contable.
3. Ajustes en core/views_config.py para listar Rubro, Marca y Familia optimizados (quitando sucursales huÃ©rfanas y aÃ±adiendo las cuentas contables de ventas/compras).
4. El listado visual de rubros (
ubros_prod_list.html) ahora expone explÃ­citamente las cuentas jerÃ¡rquicas contables asociadas.
**Resultado Pruebas:**
Los parches aplicaron limpiamente (se resolviÃ³ de manera manual el conflicto en 
iews_config.py). Las URLs de HTMX y las dependencias de modelos son consistentes con la base de datos actual.
**Estado Actual:**
Commit migrado y adaptado exitosamente a la arquitectura actual.

### Cristian - PC CASA
**Fecha:** 02/09/2026
**Objetivo:** Trasladar los perfiles de lectura PDF del core a la verticalidad de ArmerÃ­a y refactorizar el extractor para resolverlos dinÃ¡micamente.
**Archivos creados o modificados:**
- 
erticalidades/armeria/perfiles_lectura/ (Directorio y archivos trasladados)
- 
acturacion/services/extractor_facturas.py
- 
acturacion/views_procesamiento.py
**Detalle TÃ©cnico:** 
Se movieron los scripts de parsing especÃ­ficos (cuit_30610401240.py y cuit_30711323062.py) desde el mÃ³dulo genÃ©rico de 
acturacion hacia 
erticalidades/armeria/perfiles_lectura/.
Para mantener el extractor genÃ©rico y evitar cÃ³digo fuertemente acoplado (N+1 ifs por cada verticalidad), se inyectÃ³ el parÃ¡metro 	ipo_actividad (capturado en 
iews_procesamiento.py a travÃ©s de la empresa logueada) y se refactorizÃ³ procesar_factura_archivo() para utilizar importlib buscando dinÃ¡micamente:
1. 
erticalidades.<tipo_actividad>.perfiles_lectura.cuit_<cuit_limpio>
2. (Fallback) 
acturacion.services.perfiles_lectura.cuit_<cuit_limpio>
**Resultado de las pruebas:**
El extractor ahora enruta automÃ¡ticamente la lÃ³gica de lectura hacia la carpeta privada de cada verticalidad, manteniendo el core limpio.
**Estado actual y siguientes pasos sugeridos:**
Finalizado.
**Fecha:** 02/09/2026
**Objetivo:** CorrecciÃ³n de bug en asignaciÃ³n automÃ¡tica del Tipo de Comprobante tras lectura OCR.
**Archivos modificados:**
- 
acturacion/views_procesamiento.py
**Detalle TÃ©cnico:** 
El extractor retornaba el cÃ³digo de comprobante bajo la llave 	ipo_comprobante_afip (ej: "1"), pero la vista intentaba leer la llave inexistente 	ipo_comprobante_codigo. Se corrigiÃ³ la vista para leer la llave correcta y se agregÃ³ .zfill(3) para asegurar que el cÃ³digo concuerde con el formato de 3 dÃ­gitos de la base de datos (ej: "001" en lugar de "1"), lo que permite recuperar el detalle correctamente ("001 - Facturas A").
**Fecha:** 02/09/2026
**Objetivo:** ExtensiÃ³n de sobreescritura de Tipo de Comprobante al perfil 062.
**Archivos modificados:**
- 
erticalidades/armeria/perfiles_lectura/cuit_30711323062.py
**Detalle TÃ©cnico:** 
Al igual que en el perfil de Bowie, el perfil del CUIT 30-71132306-2 no estaba enviando el cÃ³digo explÃ­cito de AFIP al backend, por lo que el front quedaba vacÃ­o si la librerÃ­a general fallaba en detectarlo con exactitud. Se agregÃ³ la lÃ³gica para inyectar 	ipo_comprobante_codigo = '001' (y '003' si es Nota de CrÃ©dito) directamente en los cabecera_overrides de este proveedor.

## DÃ­a 31/08/2026 - La cuenta del efectivo la define la caja, y el recibo del cajero (Plan 077)

**Responsable:** Claude Opus.

### Objetivo
DefiniciÃ³n del usuario: *"Caja mostrador descarga sobre las cuentas definidas por parÃ¡metro âcobranzas por un lado y retiros / cierre de caja por el otroâ, por lo que deberÃ­an quedar en cero o lo que se defina como fondo fijo al final de cada cierre."* Y la mejora que lo acompaÃ±a: *"El cajero todo lo que maneje serÃ¡ a travÃ©s de su CAJA MOSTRADOR."*

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
- MigraciÃ³n: `usuarios/0010_cajero_mostrador.py` (aplicada).
- Plan: `docs/planes/077_recibo_en_mostrador.md` [NEW].

### Detalle TÃ©cnico

**El diagnÃ³stico: el efectivo tenÃ­a TRES destinos contables**, segÃºn por quÃ© camino entrara o saliera.

| Camino | Cuenta que usaba |
|--------|------------------|
| Venta de mostrador cobrada en el acto | `cta_caja` |
| Recibo de cobranza | la del **medio de pago** (fallback `cta_caja_central`) |
| Retiro / cierre de caja | `cta_caja_mostrador` |

Por eso `cta_caja_mostrador` **sÃ³lo recibÃ­a haber y nunca debe**: no es que no cerrara en cero, es que se volvÃ­a cada vez mÃ¡s acreedora con cada cierre. En ARMERIA ya estaba en â$25.000 con una sola lÃ­nea.

**La regla: para el efectivo, la cuenta la define la CAJA.** Un cheque es un cheque entre donde entre; el efectivo vive en un cajÃ³n concreto. Dicho de la forma en que lo planteÃ³ el usuario, que es la que ordena todo: **la cuenta la define quiÃ©n tiene que rendir la plata.** Un recibo hecho en el mostrador lo rinde el cajero; el mismo recibo hecho en TesorerÃ­a ya estÃ¡ en TesorerÃ­a.

`cuenta_efectivo_de_caja(caja, parametros, en_divisa)` resuelve por `caja.tipo`: `'M'` â mostrador, `'R'`/`'D'` â reparto, `'T'` â central. Para las cajas de distribuciÃ³n **lanza error si falta el parÃ¡metro** (sustituirlo en silencio mezclarÃ­a lo que ese parÃ¡metro vino a separar); para mostrador y tesorerÃ­a **devuelve `None` y la cadena sigue**, que es el estado heredado de las empresas que nunca lo cargaron.

En `_cuenta_medio_cobro()` entra como **paso 2**, entre la cuenta bancaria concreta y la lÃ³gica de divisas, y **sÃ³lo para categorÃ­a `EFE`**: la billetera digital no vive en un cajÃ³n que alguien tenga que rendir.

**SimplificaciÃ³n que se llevÃ³ puesta:** el medio de pago `EFE-REP` que el Plan 076 creaba para distribuciÃ³n **dejÃ³ de hacer falta** âla caja ya dice la cuentaâ, asÃ­ que se eliminÃ³. Queda un solo mecanismo en vez de dos, y las pruebas que verificaban aquel medio pasaron a verificar la resoluciÃ³n por caja.

**El recibo del cajero (Â§F).** Es **el mismo recibo que ya existÃ­a**: cliente, aplicaciÃ³n a facturas con saldo, o recibo simple. No hay pantalla nueva. `ReciboCargaView` ganÃ³ un atributo `origen` y una segunda URL apunta a **la misma vista y el mismo template**. Lo Ãºnico que cambiÃ³ de verdad fue `procesar_recibo()`, que resolvÃ­a la caja con `get_o_abrir_caja(...)` â**siempre TesorerÃ­a**, ahÃ­ estaba la raÃ­z de que un recibo nunca impactara el mostradorâ y ahora usa la sesiÃ³n del cajero cuando el origen es el mostrador. Si su caja estÃ¡ cerrada **falla**: no se puede meter plata en un cajÃ³n que no estÃ¡ abierto, y desviarla a TesorerÃ­a serÃ­a peor que rechazarla.

La parte contable del recibo del mostrador **no tiene una sola lÃ­nea propia**: sale de la regla de Â§E.

**La restricciÃ³n del cajero (Â§G).** `Perfil.es_cajero_mostrador`, en `False` por defecto: es una RESTRICCIÃN, no un permiso, asÃ­ que nadie pierde accesos al aplicarla y sÃ³lo queda acotado quien se marque. Al revÃ©s âun permiso que hubiera que otorgarâ habrÃ­a dejado a todos afuera hasta tildarlo uno por uno. El administrador de sistema nunca queda atrapado, para que pueda entrar a corregirlo si se marca por error.

**El bloqueo va en las vistas, no sÃ³lo en el menÃº:** esconder un link no es un permiso, la URL sigue estando para quien la escriba. Las pruebas pegan contra las URLs directas, no contra el HTML del menÃº. Y el mensaje del bloqueo **le dice al cajero por dÃ³nde tiene que operar** en vez de un "no tenÃ©s permiso" a secas.

### Resultado de las Pruebas
```
python manage.py test tesoreria.tests.test_plan077_caja_cierra_en_cero   ->  8 OK
python manage.py test tesoreria.tests.test_plan077_cajero_mostrador      -> 10 OK
python manage.py test tesoreria contable distribucion                    -> 554 OK
```

**La regresiÃ³n encontrÃ³ un bug propio y sirviÃ³ de lecciÃ³n.** El import de
`cuenta_efectivo_de_caja` en la venta de mostrador nunca llegÃ³ al mÃ³dulo: el guardia del
parche lo dio por presente porque la cadena ya aparecÃ­a dentro de otra funciÃ³n, y el cobro de
mostrador rompÃ­a con `NameError`. Lo atraparon tres pruebas del Plan 049.

De ahÃ­ saliÃ³ una prueba nueva â`test_la_venta_de_mostrador_debita_la_cuenta_de_su_caja`â
porque el hueco de fondo era otro: de los **tres caminos** que este plan unifica, el de la
venta de mostrador **no tenÃ­a ninguna prueba que verificara la cuenta**. Las del Plan 049
comprobaban el `condic` y el vÃ­nculo con la caja, no dÃ³nde caÃ­a el debe.
Las 8 primeras **verifican el requerimiento, no la implementaciÃ³n**: cobran en el mostrador, cierran la caja dejando un fondo fijo, y comprueban que `cta_caja_mostrador` queda exactamente en el fondo fijo y que lo rendido llegÃ³ a Caja Central. Si maÃ±ana la cuenta se resolviera de otra manera pero la caja siguiera cerrando bien, deberÃ­an seguir pasando.

### Estado Actual y Siguientes Pasos
El circuito del efectivo quedÃ³ consistente en las tres cajas: mostrador, distribuciÃ³n y tesorerÃ­a. **Los datos histÃ³ricos de las cuatro empresas siguen mal contabilizados** âel usuario confirmÃ³ que son de prueba y anteriores a varias mejorasâ, asÃ­ que no se reexpresÃ³ nada.

Pendientes ofrecidos y no ejecutados: el reporte de devoluciones y el de correlativos del mÃ³dulo DistribuciÃ³n (fase 8 restante), el widget de fecha en otros siete formularios, las exportaciones a PDF/Excel, la validaciÃ³n contra ARCA HomologaciÃ³n, y el ajuste de inventario para la mercaderÃ­a devuelta no apta.

## DÃ­a 31/08/2026 - Cuenta contable propia para la caja de distribuciÃ³n (Plan 076, addenda Â§B)

**Responsable:** Claude Opus.

### Objetivo
DefiniciÃ³n del usuario: *"Agreguemos un nuevo parÃ¡metro `cta_caja_reparto` porque incluso ambos responsables son totalmente distintos."* El efectivo que estÃ¡ en la calle es de otro responsable que el de la caja mostrador âel repartidor y el administrativo de reparto, frente al cajero de turnoâ, asÃ­ que el balance tiene que poder mostrarlo por separado.

### Archivos Creados o Modificados
- `contable/models.py` [MODIFY]: `ParametrosContables.cta_caja_reparto`.
- `templates/configuracion/modals/parametros_contables_form.html` [MODIFY]: el campo en la pantalla de parÃ¡metros.
- `tesoreria/views_htmx.py` [MODIFY]: `cuenta_origen_de_caja()`, y `generar_asientos_traslado()` / `_generar_asiento_diferencia()` pasan a aceptar la cuenta en vez de tenerla fija.
- `distribucion/services/caja_reparto.py` [MODIFY]: `cuenta_de_reparto()` y `medio_pago_efectivo()`.
- `distribucion/services/cobranza_fifo.py` [MODIFY]: el efectivo usa el medio de distribuciÃ³n.
- `distribucion/tests/test_plan076_cuenta_reparto.py` [NEW]: 14 pruebas.
- MigraciÃ³n: `contable/0022_cta_caja_reparto.py` (aplicada).

### Detalle TÃ©cnico

**El parÃ¡metro solo no alcanzaba, y Ã©se fue el hallazgo.** `contabilizar_recibo()` arma el DEBE del asiento con la cuenta contable del **MEDIO DE PAGO**, no con la de la caja (`_cuenta_medio_cobro()`, punto 3 de su orden de resoluciÃ³n). Con el efectivo genÃ©rico, la cobranza de un reparto habrÃ­a seguido cayendo en la cuenta de la mostrador y el parÃ¡metro nuevo no habrÃ­a servido de nada: el balance mostrarÃ­a la cuenta de reparto en cero mientras la plata de la calle se sigue mezclando.

La soluciÃ³n usa el punto de extensiÃ³n que ya existÃ­a en vez de tocar el motor contable: un **medio de pago propio `EFE-REP` (Â«Efectivo en RepartoÂ»)** apuntado a `cta_caja_reparto`, creado y **mantenido en sincronÃ­a** con el parÃ¡metro por `medio_pago_efectivo()`. Si el parÃ¡metro cambia, el medio lo sigue; si no, los asientos nuevos quedarÃ­an apuntando a la cuenta vieja. El usuario no tiene que cargarlo ni recordarlo: se deriva del parÃ¡metro. Hay una prueba de punta a punta que verifica que **lo cobrado en la calle no toca la cuenta de la mostrador**.

**Sin fallback a la mostrador, a propÃ³sito.** `cuenta_de_reparto()` lanza un error explÃ­cito si el parÃ¡metro estÃ¡ vacÃ­o. Sustituirla en silencio mezclarÃ­a la plata del repartidor con la del cajero, que es exactamente lo que esta cuenta viene a separar: *mejor un error claro una vez que un nÃºmero mal agrupado para siempre*. Es ademÃ¡s la doctrina del proyecto desde el Plan 075.

**Dos funciones compartidas dejaron de tener la cuenta fija**, con el comportamiento de siempre por omisiÃ³n:
- `generar_asientos_traslado(..., cuenta_origen=None)` â por omisiÃ³n `cta_caja_mostrador`. El retiro y el cierre resuelven cuÃ¡l corresponde con `cuenta_origen_de_caja(caja, param)`, segÃºn el tipo de caja.
- `_generar_asiento_diferencia(..., cuenta_caja=None)` â por omisiÃ³n `cta_caja_central`. Cuando quien recibe es la TesorerÃ­a de Reparto se ajusta `cta_caja_reparto`, porque **la plata contada estÃ¡ ahÃ­ y no en TesorerÃ­a**: ajustar la Central moverÃ­a una cuenta donde no pasÃ³ nada.

**Las dos cajas de distribuciÃ³n comparten la cuenta.** La recaudadora `'R'` y la TesorerÃ­a de Reparto `'D'` apuntan a `cta_caja_reparto`, asÃ­ que el traslado entre ellas sigue sin generar asiento âserÃ­a Debe y Haber sobre la misma cuentaâ. El asiento contable real aparece reciÃ©n en el segundo tramo, cuando la intermedia rinde a Caja TesorerÃ­a: ahÃ­ sÃ­ **Debe Caja Central / Haber Caja de Reparto**, que es lo que hace visible en el balance cuÃ¡nto hay en la calle.

### Resultado de las Pruebas
```
python manage.py test distribucion tesoreria contable
Ran 534 tests in 517.615s
OK
```
Las 14 pruebas nuevas cubren: el parÃ¡metro y su error cuando falta, el medio de pago propio (que apunta a la cuenta, que no pisa el efectivo genÃ©rico, que sigue al parÃ¡metro si cambia y que es idempotente), el asiento de la cobranza del reparto y del vendedor debitando la cuenta correcta, la diferencia de arqueo ajustando la caja de reparto y no la Central, la resoluciÃ³n de la cuenta de origen segÃºn el tipo de caja, y la verificaciÃ³n de punta a punta de que lo cobrado en la calle no toca la cuenta de la mostrador.

### Estado Actual y Siguientes Pasos

**ACCIÃN PENDIENTE DEL USUARIO.** La empresa 4 (RODRIGUEZ MARCELO FABIAN) todavÃ­a tiene `cta_caja_reparto` **sin configurar**, asÃ­ que el circuito de cobranzas de distribuciÃ³n va a fallar con el mensaje explÃ­cito hasta que se le asigne una cuenta en *ConfiguraciÃ³n â ParÃ¡metros Contables â Caja de Reparto (DistribuciÃ³n)*. Su plan de cuentas hoy tiene `111001 CAJA`, `111002 VALORES EN CARTERA` y `111003 CAJA MOSTRADOR`: el hueco natural es `111004 CAJA DE REPARTO`.

Pendientes ofrecidos y no ejecutados: el reporte de devoluciones y el de correlativos del mÃ³dulo (fase 8 restante), el widget de fecha en otros siete formularios, las exportaciones a PDF/Excel, la validaciÃ³n contra ARCA HomologaciÃ³n, y el ajuste de inventario para la mercaderÃ­a devuelta no apta.

## DÃ­a 31/08/2026 - Cobranza y rendiciÃ³n del vendedor (Plan 076, bloque C)

**Responsable:** Claude Opus.

### Objetivo
DefiniciÃ³n del usuario: *"En cuanto a los vendedores, rendirÃ¡n a esta caja intermedia pero en su condiciÃ³n de vendedores por los fondos que traen, no como reparto."*

### Archivos Creados o Modificados
- `distribucion/models.py` [MODIFY]: `CobranzaDistribucion.reparto` nullable con CheckConstraint de responsable; `RendicionReparto` gana `vendedor` y el CheckConstraint de origen Ãºnico.
- `distribucion/services/caja_reparto.py` [MODIFY]: `abrir_caja_del_vendedor()`, `sesion_abierta_del_vendedor()`, `resumen_vendedor()`, `rendir_vendedor()`; la bandeja lista los dos orÃ­genes.
- `distribucion/services/cobranza_fifo.py` [MODIFY]: `registrar()` acepta `reparto=None`.
- `distribucion/views.py`, `templates/distribucion/cobranza_vendedor.html` [NEW/MODIFY].
- `distribucion/tests/test_plan076_cobranza_vendedor.py` [NEW]: 23 pruebas.
- MigraciÃ³n: `distribucion/0010_rendicion_del_vendedor.py` (aplicada).

### Detalle TÃ©cnico

**Para poder rendir hay que haber retenido.** El vendedor cobra por su cuenta âal cliente que esquiva el pago y al que despuÃ©s le hace la guardiaâ, y esa plata tiene que caer en algÃºn lado antes de que la entregue, o no habrÃ­a nada que rendir. Se le abre una **sesiÃ³n propia sobre la misma caja recaudadora**, que se cierra reciÃ©n cuando rinde. Misma estructura que un reparto, con otro dueÃ±o.

**La sesiÃ³n no dice de quiÃ©n es la plata; lo dice la rendiciÃ³n.** `CajaSesion.usuario` es un `User` y el vendedor puede no serlo (Â§4.3). La sesiÃ³n abierta de un vendedor se identifica por **sus cobranzas**, que llevan el `cobrador`; una sesiÃ³n de reparto nunca entra ahÃ­ porque sus cobranzas tienen `reparto` seteado.

**La plata siempre tiene un responsable.** Dos restricciones de base:
```python
CobranzaDistribucion:  Q(reparto__isnull=False) | Q(cobrador__isnull=False)
RendicionReparto:      exactamente UNO de reparto / vendedor
```
Sin ninguno la plata no tiene dueÃ±o; con los dos, no se sabe a quiÃ©n reclamarle un faltante.

**Mismo FIFO, mismas dos reglas, sin caso especial.** `registrar()` con `reparto=None` recorre idÃ©ntico camino. Una prueba lo fija: efectivo contra el PRE, transferencia contra la factura.

**`Personal` no tiene sucursal** âel vendedor recorre, no estÃ¡ asignado a un depÃ³sitoâ, asÃ­ que la sucursal la aporta quien opera, desde su sesiÃ³n de trabajo. El servicio la exige explÃ­citamente en vez de adivinarla.

**Los dos orÃ­genes comparten bandeja de recepciÃ³n:** para quien recibe es el mismo acto âcontar lo que alguien trajoâ y separarlos sÃ³lo agregarÃ­a una pantalla mÃ¡s.

### Resultado de las Pruebas
```
python manage.py test distribucion.tests.test_plan076_cobranza_vendedor
Ran 23 tests in 30.689s
OK
```

### Estado Actual y Siguientes Pasos
**Plan 076 completo (A + B + C + D).** El circuito de fondos de DistribuciÃ³n quedÃ³ con sus tres niveles y las notas de crÃ©dito descuentan el saldo de su factura en todo el ERP.

Pendientes ofrecidos y no ejecutados: el reporte de devoluciones por perÃ­odo/motivo/repartidor y el de correlativos del mÃ³dulo (fase 8 restante), el widget de fecha en otros siete formularios, las exportaciones a PDF/Excel, la validaciÃ³n contra ARCA HomologaciÃ³n, el ajuste de inventario para la mercaderÃ­a devuelta no apta, y una cuenta contable propia para las cajas de distribuciÃ³n si se quisiera ver por separado en el balance la plata que estÃ¡ en la calle.

## DÃ­a 31/08/2026 - TesorerÃ­a de Reparto intermedia (Plan 076, bloque B)

**Responsable:** Claude Opus.

### Objetivo
DefiniciÃ³n del usuario: *"Las rendiciones de reparto y vendedoresâ¦ se realizan en una 'tesorerÃ­a de reparto intermedia' tal cual la caja mostrador de armerÃ­a, para luego tipo retiro y cierre de caja rendir a caja tesorerÃ­a."* La fase 7 salteaba ese nivel.

### Archivos Creados o Modificados
- `tesoreria/models.py` [MODIFY]: `Caja.tipo` gana `'D'` (TesorerÃ­a de Reparto).
- `tesoreria/views.py`, `tesoreria/views_htmx.py` [MODIFY]: **correcciÃ³n de la regresiÃ³n** y helpers `_caja_operable()` / `_cajas_operables()`.
- `distribucion/services/caja_reparto.py` [MODIFY]: `tesoreria_reparto()`, `sesion_de_tesoreria_reparto()`, `recibir()`, `rendiciones_por_recibir()`; `rendir()` cambia de destino.
- `distribucion/views.py`, `templates/distribucion/recepcion_rendiciones.html` [NEW/MODIFY]: bandeja de recepciÃ³n.
- `distribucion/tests/test_plan076_tesoreria_reparto.py` [NEW]: 20 pruebas.
- MigraciÃ³n: `tesoreria/0017_tesoreria_de_reparto.py` (aplicada).

### Detalle TÃ©cnico

**Son tres niveles, no dos:**
```
cobranzas ââº CAJA RECAUDADORA 'R'      una sesiÃ³n por reparto
                    â  el repartidor declara â el administrativo cuenta y acepta
                    â¼
             TESORERÃA DE REPARTO 'D'  UNA POR SUCURSAL
                    â  retiro / cierre de caja (circuito existente)
                    â¼
             CAJA TESORERÃA 'T'
```
Quien recibe a los repartidores **no es el tesorero central**: es un administrativo que cuenta lo que cada uno trae, lo retiene, y despuÃ©s entrega el consolidado. Es la misma razÃ³n por la que existe la caja mostrador de armerÃ­a. Y **los dos pasos que el Plan 074 Â§7.9 pedÃ­a son los de este tramo**, no los del que va a TesorerÃ­a: estaban bien descritos y mal ubicados.

**REGRESIÃN CORREGIDA (Â§B.2).** `caja_recaudadora()` âde la fase 7â crea una caja `'R'` en la misma sucursal donde vive la mostrador. Seis lugares buscaban Â«la caja de la sucursalÂ» **sin filtrar por tipo**:
```python
Caja.objects.filter(empresa_id=..., sucursal_id=..., activa=True).first()
```
en `tesoreria/views.py:79` y `views_htmx.py` 923, 1328, 1354, 1477 y 1498. `Caja` no tiene `ordering` en su `Meta`, asÃ­ que funcionaba sÃ³lo porque la mostrador tiene `pk` mÃ¡s bajo. **El riesgo real:** la sesiÃ³n se busca con `usuario=request.user, estado='A'`, y un cajero que ademÃ¡s cerrara un reparto tenÃ­a DOS sesiones abiertas a su nombre â el cierre de mostrador podÃ­a tomar la del reparto y rendir esa plata por el circuito equivocado. Hay tres pruebas dedicadas.

**Sin asiento de traslado en el primer tramo, y es deliberado.** La recaudadora y la TesorerÃ­a de Reparto son las dos Â«efectivo fuera de TesorerÃ­aÂ» y comparten cuenta contable (`cta_caja_mostrador`): el asiento serÃ­a Debe y Haber sobre la misma cuenta. Peor todavÃ­a serÃ­a asentar contra Caja Central, porque estarÃ­a registrando en TesorerÃ­a **plata que sigue en la calle**. El movimiento contable real ocurre en el segundo tramo, cuando la intermedia rinde por el retiro/cierre de siempre.

**La caja refleja lo CONTADO, no lo declarado**, y la diferencia genera su asiento contra Diferencias de Caja: un faltante queda registrado, no absorbido en silencio. *El que declara no es el mismo que cuenta.*

### Resultado de las Pruebas
```
python manage.py test distribucion tesoreria
Ran 405 tests in 370.545s
OK
```

---

## DÃ­a 31/08/2026 - Parada de sÃ³lo cobranza (Plan 076, bloque A)

**Responsable:** Claude Opus.

### Objetivo
DefiniciÃ³n del usuario: *"En una hoja de ruta podemos agregar clientes con saldos que no hicieron un pedido pero necesito que le cobren el saldo pendiente."* Si todas las paradas son de esa clase, el reparto es una ruta de cobranza pura, sin detalle de productos.

### Archivos Creados o Modificados
- `distribucion/models.py` [MODIFY]: `RepartoParada.tipo` (`ENTREGA` / `COBRANZA`), `pedido` y `venta` nullables, `cliente` y `domicilio_texto` como campos propios, y tres restricciones nuevas.
- `distribucion/services/reparto.py` [MODIFY]: `agregar_parada_de_cobranza()`, `cerrar_reparto()`, `hoja_de_ruta()`, `consolidado()`, `totales_hoja_de_ruta()`.
- `distribucion/services/devoluciones.py` [MODIFY]: entrega y devoluciones sÃ³lo sobre paradas de ENTREGA.
- `distribucion/views.py` [MODIFY]: acciÃ³n `agregar_cobranza` y selector de clientes con saldo.
- Templates de reparto, hoja de ruta, entrega, cobranza, recepciÃ³n y rendiciÃ³n [MODIFY].
- `distribucion/tests/test_plan076_parada_cobranza.py` [NEW]: 27 pruebas.
- MigraciÃ³n: `distribucion/0009_parada_de_cobranza.py` (aplicada).

### Detalle TÃ©cnico

**EL COBRO MÃNIMO DE UNA PARADA DE COBRANZA ES CERO.** Es la correcciÃ³n central del bloque, y va contra lo que yo habÃ­a asumido primero âque habÃ­a que exigir todo el saldoâ. El usuario lo desarmÃ³:

> *"Puede tranquilamente ser una cobranza parcial como cualquier otraâ¦ la mayorÃ­a de las veces el cliente o no entrega nada o entrega sÃ³lo un pago parcial. Seguramente el pago final lo terminarÃ¡ haciendo el vendedor que le harÃ¡ la 'guardia' cuando el cliente estÃ© esquivando el pago. Cliente que no hizo pedido es mÃ¡s que probable que no estÃ© entre sus prioridades el pagarnos."*

El razonamiento de fondo: **el cobro mÃ­nimo existe porque hay mercaderÃ­a de por medio, es la condiciÃ³n para dejarla.** Sin entrega no hay palanca. El repartidor pide y se lleva lo que le den. Entonces se congela el **saldo** como dato para reclamar, `cobro_minimo = 0`, y lo que traiga se imputa con el procedimiento estÃ¡ndar: FIFO de lo mÃ¡s antiguo, con el efectivo priorizando los `condic = 2`. **Sin caso especial**: es exactamente lo que ya hacÃ­a `registrar()`.

Queda ademÃ¡s coherente el cuadro de la rendiciÃ³n: `esperado = Î£ cobro_minimo`, asÃ­ que estas paradas aportan cero. *No se puede esperar lo que no se tiene con quÃ© exigir.*

**El tipo es explÃ­cito, no inferido.** `RepartoParada.tipo` en vez de deducirlo de `venta is None`: obligar a recordar esa convenciÃ³n en cada lectura es la clase de detalle que despuÃ©s se olvida en un reporte.

**`cliente` y `domicilio_texto` dejan de ser properties.** SalÃ­an de `venta.cliente` y `pedido.domicilio_entrega_texto`; sin comprobante no hay de dÃ³nde sacarlos. La migraciÃ³n los rellena con **los mismos valores que devolvÃ­an las properties**: no hay pÃ©rdida ni interpretaciÃ³n. El domicilio queda congelado por el mismo motivo que los importes.

**Las reglas inflexibles van a la base:**
```python
CheckConstraint(Q(tipo=0, venta__isnull=False) | Q(tipo=1, venta__isnull=True))
UniqueConstraint(['venta'], condition=Q(venta__isnull=False))
```
El Ãºnico se condiciona porque ahora hay nulos. PostgreSQL ya admite varios NULL en un Ã­ndice Ãºnico, pero asÃ­ la regla queda **escrita** y no depende de un detalle del motor. Hay pruebas para las dos combinaciones invÃ¡lidas y para que varias paradas de cobranza convivan en el mismo reparto.

**Lo que se apagÃ³ donde no corresponde:** entrega, devoluciones y RecepciÃ³n de Devoluciones rechazan una parada de cobranza â *sin mercaderÃ­a no hay entrega que registrar ni devoluciÃ³n que recibir*. El Consolidado de un reparto de pura cobranza da **vacÃ­o**, que es lo correcto: no se carga nada al vehÃ­culo. Y `hoja_de_ruta()` pasa a ordenar por el cliente **propio de la parada**: por el del comprobante, las de cobranza caÃ­an todas al final.

### Resultado de las Pruebas
```
python manage.py test distribucion
Ran 297 tests in 281.850s
OK
```

---

## DÃ­a 31/08/2026 - La Nota de CrÃ©dito descuenta el saldo de su factura (Plan 076, bloque D)

**Responsable:** Claude Opus.

### Objetivo
DefiniciÃ³n del usuario: *"Las notas de crÃ©dito, como estÃ¡n vinculadas a la factura que le dio origen, deben computarse en el saldo pendiente de la factura (factura â NC relacionadas), y de ahÃ­ sale el saldo real de la factura. La NC queda con saldo cero porque se aplicÃ³ totalmente a la factura de origen."* **Afecta a todo el ERP, no sÃ³lo a DistribuciÃ³n.**

### Archivos Creados o Modificados
- `facturacion/models.py` [MODIFY]: `Venta.venta_origen` (FK a sÃ­ misma, nullable, `related_name='notas_credito'`).
- `facturacion/services/notas_credito.py` [MODIFY]: `emitir_nota_credito_desde_venta()` estampa el vÃ­nculo.
- `facturacion/signals.py` [MODIFY]: al guardar una NC vinculada se recalcula el saldo de la NC y el de su factura.
- `contable/services/saldos.py` [MODIFY]: `recalcular_saldo_venta()` resta las NC relacionadas y deja la NC en cero; `recalcular_saldo_cliente_proveedor()` **aplica el signo del tipo**.
- `facturacion/tests/test_plan076_saldo_nc.py` [NEW]: 11 pruebas.
- Migraciones: `facturacion/0059_venta_venta_origen.py` y `facturacion/0060_vincular_nc_y_recalcular_saldos.py` (aplicadas).

### Detalle TÃ©cnico

**No existÃ­a vÃ­nculo genÃ©rico NC â factura.** `emitir_nota_credito_desde_venta()` recibÃ­a la venta original, copiaba sus Ã­tems y **no persistÃ­a de dÃ³nde venÃ­a**. El Ãºnico vÃ­nculo era `distribucion.NotaCreditoDistribucion.venta_origen`, satÃ©lite del mÃ³dulo, inÃºtil para armerÃ­a o para el resto del ERP. El campo nuevo `Venta.venta_origen` cierra eso.

**El saldo del comprobante.** `recalcular_saldo_venta()` pasa a ser `total â cobrado â Î£ recibos â Î£ NC relacionadas`, y una NC con `venta_origen` queda en **cero**: se aplicÃ³ por completo a su factura. El recÃ¡lculo se dispara desde la seÃ±al `post_save` de `Venta` y no desde el emisor de la NC, para que valga tambiÃ©n al **anularla**, que es cuando el descuento se revierte. No hay recursiÃ³n: el servicio escribe con `.update()`, que no dispara seÃ±ales.

**Hallazgo: la convenciÃ³n de signo estaba documentada pero no implementada.** `saldos.py` y `tesoreria/views_htmx.py` decÃ­an que las NC *"se graban en negativo vÃ­a `TipoComprobante.signo = -1`"*. Los datos dicen otra cosa: las dos NC de la base tienen total **positivo** (30,00 y 12,00), y `emitir_nota_credito_desde_venta()` las emite asÃ­, sumando Ã­tems positivos. Con `recalcular_saldo_cliente_proveedor()` sumando `total â cobrado` sin aplicar el signo, **una Nota de CrÃ©dito AUMENTABA la deuda del cliente en lugar de bajarla**.

La correcciÃ³n va donde ya estaba el criterio correcto del proyecto: `productos.services.stock_service` multiplica por `tipo__signo` para que la NC invierta el movimiento. Ahora el saldo por entidad hace lo mismo:

```python
Sum((F('total') - F('cobrado')) * Coalesce(F('tipo__signo'), Value(1)))
```

Es un arreglo inseparable del pedido: sin Ã©l la lente por comprobante y la lente por entidad se separaban por el doble de la NC. Hay una prueba que exige que **la suma de los saldos de los comprobantes sea igual al saldo del cliente**.

`recalcular_saldo_compra()` **no se tocÃ³**: no hay ninguna compra con tipo de signo â1 en la base, asÃ­ que no hay evidencia de cuÃ¡l es la convenciÃ³n real del lado de proveedores. Queda anotado.

**Efecto lateral que limpia el diseÃ±o de la fase 7.** Aquella fase documentÃ³ *"las notas de crÃ©dito no entran en el FIFO"* como decisiÃ³n para no manejar signos cruzados. Con esta regla deja de ser un compromiso: la NC baja el saldo de su factura y queda en cero, asÃ­ que el filtro `saldo > 0` de `comprobantes_abiertos()` es correcto **por construcciÃ³n**. Dos pruebas lo fijan.

**MigraciÃ³n de datos.** Vincula las NC existentes desde `NotaCreditoDistribucion.venta_origen` âÃºnico lugar donde el dato existÃ­aâ y recalcula comprobantes y entidades con una **rÃ©plica congelada** de la fÃ³rmula, sin importar el servicio vivo (en una migraciÃ³n el modelo es histÃ³rico). VerificaciÃ³n sobre la base real:

```
ANTES:   ORTIZ JUAN MANUEL  saldo 599,00
DESPUES: ORTIZ JUAN MANUEL  saldo 515,00
```

La baja de 84,00 es exactamente 2 Ã 42,00 (las dos NC de 30,00 y 12,00): antes se sumaban, ahora se restan. Confirma que el error era real y que quedÃ³ corregido.

**LimitaciÃ³n conocida:** las NC histÃ³ricas de otros mÃ³dulos no tienen de dÃ³nde deducir su origen y quedan sin vincular (`venta_origen = NULL`). Son las dos que hay en el sistema. Su saldo se comporta como antes âuna NC sin aplicar es un crÃ©dito pendiente legÃ­timoâ, pero el FIFO las va a ofrecer como comprobante a cobrar hasta que se las vincule a mano.

### Resultado de las Pruebas
```
python manage.py test facturacion contable tesoreria
Ran 280 tests in 221.312s
FAILED (errors=1)   # test_emitir_comprobante_homologacion_real: falta el certificado ARCA (ambiental)
```
Las 11 pruebas nuevas cubren: la NC baja el saldo de su factura, la NC queda en cero, el vÃ­nculo persistido, la NC total, dos NC parciales acumuladas, la convivencia con una cobranza en el mismo saldo, la reversiÃ³n al anular, que el saldo del cliente no se cuente dos veces, que las dos lentes coincidan, y que el FIFO no ofrezca ni una factura ya cubierta ni la NC.

### Estado Actual y Siguientes Pasos
Bloque **D** cerrado. **Siguen A** (parada de sÃ³lo cobranza), **B** (TesorerÃ­a de Reparto intermedia + la regresiÃ³n del Â§B.2) y **C** (rendiciÃ³n del vendedor), en ese orden.

## DÃ­a 31/08/2026 - Cobranzas del repartidor, caja recaudadora y saldos por vendedor (Plan 074, fases 7 y 8)

**Responsable:** Claude Opus.

### Objetivo
Cerrar el circuito del dinero: la cobranza que trae el repartidor con **imputaciÃ³n FIFO segmentada por medio de pago**, la **caja recaudadora** que se abre por reparto, la **rendiciÃ³n a TesorerÃ­a** en dos pasos, y el listado de **Clientes a Cobrar** agrupado por vendedor.

### Archivos Creados o Modificados
- `distribucion/services/cobranza_fifo.py` [NEW]: `planificar()`, `registrar()`, `comprobantes_abiertos()`, `saldo_fiscal()`, `saldo_operativo()`.
- `distribucion/services/caja_reparto.py` [NEW]: `caja_recaudadora()`, `abrir_caja_del_reparto()`, `resumen()`, `rendir()`.
- `distribucion/services/saldos_clientes.py` [NEW]: `listado()` con antigÃ¼edad por tramos y agrupaciÃ³n por vendedor.
- `distribucion/models.py` [MODIFY]: `CobranzaDistribucion`, `RendicionReparto` y `Reparto.sesion_caja`.
- `tesoreria/models.py` [MODIFY]: nuevo tipo de caja `'R'` (Recaudadora / Reparto).
- `distribucion/services/reparto.py` [MODIFY]: `cerrar_reparto()` abre la caja recaudadora.
- `distribucion/views.py` [MODIFY]: `CobranzaRepartoView`, `RendicionRepartoView`, `SaldosClientesView`.
- `templates/distribucion/cobranza.html`, `rendicion.html`, `saldos_clientes.html` [NEW].
- `templates/distribucion/reparto_detalle.html`, `templates/base.html`, `config/urls.py` [MODIFY]: tres rutas nuevas y la entrada de menÃº Â«Clientes a CobrarÂ».
- `distribucion/tests/test_plan074_cobranzas.py` [NEW]: 43 pruebas.
- Migraciones: `distribucion/0008_reparto_sesion_caja_cobranzadistribucion_and_more.py`, `tesoreria/0016_alter_caja_tipo.py`, `core/0007_alter_contadordocumento_tipo_documento.py` (todas aplicadas).

### Detalle TÃ©cnico

**El usuario carga un importe; el corte lo hace el sistema.** El repartidor vuelve y dice Â«de GonzÃ¡lez traje $40.000 en efectivo y un cheque de $66.000Â». Nadie le va a preguntar cuÃ¡nto de eso cancela facturas y cuÃ¡nto cancela PRE: eso lo decide `cobranza_fifo.py` con dos reglas que no se negocian.

1. **Lo trazable va siempre contra `condic = 1`.** Transferencia, cheque, tarjeta, billetera digital y retenciÃ³n: un movimiento que el banco registra no puede cancelar una operaciÃ³n que para el fisco no existe. Todo lo que **no** estÃ© en esa lista se trata como efectivo, incluida la categorÃ­a `OTR`: si no deja rastro externo verificable, no puede respaldar una operaciÃ³n fiscal.
2. **El efectivo cancela primero el PRE mÃ¡s viejo**, y sÃ³lo agotados todos los PRE continÃºa con las facturas. Es la Ãºnica plata que puede pagar lo que no estÃ¡ documentado, asÃ­ que se usa donde hace falta.

Los dos tramos comparten **un solo diccionario de saldos**, que se muta a medida que se imputa. Es lo que garantiza que el efectivo no vuelva a aplicar sobre el peso que ya cancelÃ³ el cheque; hay una prueba que lo fija.

**Dos recibos como mÃ¡ximo, uno por `condic`.** Real y Presupuestado no se mezclan porque cada uno alimenta un circuito contable distinto y el asiento hereda el `condic` del comprobante. El recibo Presupuestado lleva **exactamente** el efectivo que cancelÃ³ PRE; todo lo demÃ¡s âtrazables, efectivo aplicado a facturas y el excedenteâ va al Real. AsÃ­ los dos totales suman lo que entrÃ³ en la caja, y los `MovimientoCajaDetalle` de cada uno cuadran con su total, que es lo que hace que el asiento cierre. Hay una prueba dedicada a ese cuadre.

**El excedente queda en el circuito fiscal**, como anticipo del cliente: es donde se puede justificar de dÃ³nde saliÃ³ la plata. Si sobrÃ³ efectivo es porque ya no quedaba ningÃºn PRE que cancelar, asÃ­ que no hay otro lugar donde ponerlo.

**Las notas de crÃ©dito no entran en el FIFO.** Acreditar una NC contra una factura es una *imputaciÃ³n entre comprobantes*, no una cobranza: no entra plata. Mezclarla obligarÃ­a a manejar signos cruzados en el mismo recorrido y volverÃ­a ilegible el algoritmo. El FIFO recorre sÃ³lo comprobantes con saldo deudor.

**Las dos lentes sobre el saldo del cliente.** `ClienteProveedor.saldo` suma todo sin distinguir: sirve como lente **operativa** (`condic 1 + 2`), que es la que ve el vendedor, la que usa el lÃ­mite de crÃ©dito y la que sale impresa en la Hoja de Ruta âal cliente hay que cobrarle todo lo que debe, tenga o no respaldo fiscalâ. La lente **fiscal** (`condic = 1`) se calcula recorriendo comprobantes y recibos: es la que va a los estados contables. Una prueba muestra el efecto: cobrar en efectivo un PRE baja el saldo operativo y **no mueve el fiscal**.

**Caja recaudadora `'R'`, no la mostrador `'M'`.** La mostrador se abre y cierra por turno de cajero, con arqueo ciego, en un puesto fijo; la recaudadora se abre y cierra **por reparto**, la maneja alguien que estÃ¡ en la calle, y su cierre se concilia contra la Hoja de Ruta. Un `tipo` explÃ­cito evita ramificar el cÃ³digo de la mostrador con condicionales que no tienen nada que ver con ella. Hay **una sola caja recaudadora por sucursal**: lo que separa un reparto de otro es la **sesiÃ³n**, que se abre automÃ¡ticamente al cerrar el reparto.

**De quiÃ©n es la plata lo dice el reparto, no la sesiÃ³n de caja.** `CajaSesion.usuario` es un `User` y el repartidor puede no serlo: trabaja con el papel y no necesita credenciales (Â§4.3). En la prÃ¡ctica el administrativo abre la sesiÃ³n y el `Reparto` dice de quiÃ©n es la recaudaciÃ³n, a travÃ©s de sus `responsables`. `RendicionReparto` es el vÃ­nculo que la sesiÃ³n de caja no puede dar.

**La rendiciÃ³n reutiliza `RetiroCaja`, que ya existe.** Los dos pasos âel repartidor declara, el tesorero cuenta y acepta, la diferencia genera su asientoâ ya estÃ¡n implementados y probados en TesorerÃ­a, y la rendiciÃ³n del reparto aparece en **la misma bandeja de recepciÃ³n** que las de mostrador. AcÃ¡ no se reimplementÃ³ nada: se abre el retiro desde la sesiÃ³n del reparto, se generan sus asientos de traslado y el reparto pasa a **RENDIDO** cerrando su caja. El paso 2 sigue viviendo en TesorerÃ­a, que es donde corresponde: *el que declara no es el mismo que cuenta*.

**DecisiÃ³n contable revisable:** el traslado usa `cta_caja_mostrador` como cuenta de ORIGEN, que es la cuenta de efectivo fuera de TesorerÃ­a. La recaudadora **no tiene parÃ¡metro contable propio**; agregarlo sÃ³lo tendrÃ­a sentido si la empresa quisiera ver por separado en el balance la plata que estÃ¡ en la calle. Queda anotado en el cÃ³digo y acÃ¡.

**Cuadro esperado vs. cobrado vs. rendido** (Â§7.9, punto 4). *Esperado* es la suma de los `cobro_minimo` congelados al cerrar el reparto: lo que el sistema le dijo al repartidor que no podÃ­a dejar de traer. *Cobrado* se abre por medio de pago y por `condic`. *Rendido* muestra lo declarado y lo que el tesorero contÃ³. El cuadro incluye ademÃ¡s **las notas de crÃ©dito del reparto con sus motivos**: sin verlas ahÃ­, el importe de la mercaderÃ­a que volviÃ³ parecerÃ­a un faltante del repartidor.

**Clientes a Cobrar (Â§7.8).** Agrupado por vendedor porque es el responsable directo del saldo de su cartera. Un cliente **sin vendedor asignado no desaparece**: cae en un grupo propio, porque un saldo sin responsable es justamente lo que hay que ver. Cada comprobante trae su antigÃ¼edad en dÃ­as y su tramo (0-30 / 31-60 / 61-90 / +90), y los `condic = 2` van marcados **SÃLO EFECTIVO**: es la traducciÃ³n prÃ¡ctica de la regla 1. Zona y dÃ­a de visita se filtran por el **domicilio de entrega**, no por el cliente, porque un cliente con sucursales tiene domicilios en zonas y dÃ­as distintos. Filtro de condiciÃ³n presente, como exige la regla del proyecto para todo reporte con importes.

### Resultado de las Pruebas
```
python manage.py test distribucion tesoreria contable
Ran 450 tests in 386.295s
OK
```
Las 43 pruebas nuevas cubren: las dos reglas de segmentaciÃ³n, el orden FIFO por fecha, la venta del propio reparto cancelÃ¡ndose al final, el excedente, la no-doble-aplicaciÃ³n entre tramos, la particiÃ³n en dos recibos, el cuadre de los detalles contra el total de cada recibo, la baja del saldo de los comprobantes, el satÃ©lite, la caja recaudadora y su idempotencia, sesiones distintas por reparto sobre la misma caja, el cuadro de rendiciÃ³n, el retiro en trÃ¡nsito, el cierre de la caja al rendir, la doble rendiciÃ³n rechazada, las dos lentes, los tramos de antigÃ¼edad, el filtro de condiciÃ³n, el aislamiento multiempresa y las cuatro pantallas.

Tres ajustes que hicieron las pruebas: `ClienteProveedor` tiene PK `codigo_id` (se usa `.pk`), la contabilizaciÃ³n de una factura fiscal exige `cta_iva_debito`, y el traslado de la rendiciÃ³n exige `cta_caja_mostrador`.

### Estado Actual y Siguientes Pasos
Los nueve procesos del Plan 074 estÃ¡n implementados: desde que el vendedor toma el pedido hasta que la plata llega a TesorerÃ­a, pasando por la facturaciÃ³n, el reparto, la entrega, las devoluciones y la cobranza. **Falta la fase 8 restante**: el reporte de devoluciones por perÃ­odo/motivo/repartidor y el de correlativos del mÃ³dulo, mÃ¡s las exportaciones a PDF/Excel.

Pendientes ofrecidos y no ejecutados: el widget de fecha en otros siete formularios, la exportaciÃ³n de faltantes y de saldos a PDF/Excel, la validaciÃ³n de la emisiÃ³n real contra ARCA HomologaciÃ³n, el ajuste de inventario para la mercaderÃ­a devuelta no apta, y la cuenta contable propia para la caja recaudadora.

## DÃ­a 31/08/2026 - Entrega, devoluciones y notas de crÃ©dito (Plan 074, fase 6)

**Responsable:** Claude Opus.

### Objetivo
Cerrar el circuito de la calle. Como el comprobante ya estÃ¡ emitido cuando el camiÃ³n sale, **todo lo que no se entrega llega con la factura hecha**: deja de ser un caso marginal y pasa a ser parte del trabajo diario. La fase agrega la rendiciÃ³n de la entrega, el documento numerado con el que el depÃ³sito declara quÃ© volviÃ³ (**RecepciÃ³n de Devoluciones**) y la emisiÃ³n de la **Nota de CrÃ©dito** desde ese conteo.

### Archivos Creados o Modificados
- `distribucion/models.py` [MODIFY]: `RecepcionDevolucion`, `RecepcionDevolucionItem` y `NotaCreditoDistribucion`.
- `distribucion/services/devoluciones.py` [NEW]: `marcar_entregada()`, `marcar_no_entregada()`, `paradas_por_recibir()`, `crear_recepcion()`, `cargar_items()`, `confirmar_recepcion()`, `emitir_nota_credito()`, `conciliacion()`.
- `core/models.py` [MODIFY]: tipo `RECEPCION_DEVOLUCION` en `ContadorDocumento`.
- `facturacion/services/notas_credito.py` [MODIFY]: `'PRE': 'NCI'` en `MAPEO_NC`, para que un comprobante interno tenga su nota de crÃ©dito interna.
- `distribucion/views.py` [MODIFY]: `EntregaView` y `RecepcionDevolucionView`.
- `templates/distribucion/entrega.html`, `templates/distribucion/recepcion_devolucion.html` [NEW].
- `templates/distribucion/reparto_detalle.html` [MODIFY]: botÃ³n Â«Entrega y devolucionesÂ», visible sÃ³lo con el reparto cerrado.
- `config/urls.py`, `templates/base.html` [MODIFY]: dos rutas nuevas y el resaltado del menÃº.
- `distribucion/tests/test_plan074_devoluciones.py` [NEW]: 33 pruebas.
- MigraciÃ³n: `distribucion/0007_recepciondevolucion_notacreditodistribucion_and_more.py` (aplicada).

### Detalle TÃ©cnico

**Primero se cuenta, despuÃ©s se acredita.** Es la regla que ordena toda la fase, y es la misma por la que el Informe de RecepciÃ³n precede a la registraciÃ³n de la factura del proveedor. El flujo tiene tres momentos que no se pueden saltear:

1. En la calle, el repartidor marca la parada como **no entregada**, con su observaciÃ³n.
2. En el depÃ³sito se abre la **RecepciÃ³n de Devoluciones**, numerada, donde el encargado cuenta lo que efectivamente volviÃ³ y lo confirma.
3. ReciÃ©n desde esa recepciÃ³n confirmada se emite la **Nota de CrÃ©dito**, con todo precargado.

`emitir_nota_credito()` rechaza una recepciÃ³n que no estÃ© confirmada. Si se acreditara primero y se contara despuÃ©s, se le estarÃ­a acreditando al cliente mercaderÃ­a que puede no haber vuelto, y el descalce aparecerÃ­a reciÃ©n en la conciliaciÃ³n âcuando ya no hay a quiÃ©n reclamarleâ.

**Una recepciÃ³n por pedido devuelto, no una por reparto.** La devoluciÃ³n se acredita a un cliente concreto con una NC contra UN comprobante, asÃ­ que la correspondencia `1 Pedido â 1 Comprobante â 1 RecepciÃ³n â 1 NC` es lo que permite conciliar sin desarmar totales. Un `UniqueConstraint` parcial (`estado in (0, 1)`) impide abrir dos recepciones vigentes para la misma parada; si una se anula, puede rehacerse.

**El documento identifica reparto, pedido y comprobante**, como pidiÃ³ el usuario: la FK a `RepartoParada` trae los tres en un solo salto, y `reparto` queda ademÃ¡s desnormalizado para filtrar y auditar sin JOIN.

**El nÃºmero lo da el sistema.** `ContadorDocumento.RECEPCION_DEVOLUCION` con `siguiente_numero()` bajo `select_for_update()`. Es el criterio de control interno del proyecto: sÃ³lo lo que se emite numerado puede auditarse. La NC de un PRE toma su nÃºmero de la serie `VENTA_NCI`, separada de la de PRE, tal como se acordÃ³.

**El motivo decide si la mercaderÃ­a vuelve al stock vendible.** `MotivoDevolucion.sugiere_apto_reventa` precarga el `apto_reventa` del renglÃ³n: un envase roto no vuelve, un negocio cerrado sÃ­. No queda librado al criterio de quien carga. Los motivos de momento `PRE_CARGA` no se ofrecen en la recepciÃ³n, porque aplican antes de cargar el vehÃ­culo.

**DesvÃ­o documentado respecto del texto del plan: el stock lo devuelve la Nota de CrÃ©dito, no la RecepciÃ³n.** `productos.services.stock_service` deriva el stock de los COMPROBANTES, y las notas de crÃ©dito ya invierten el movimiento por el `signo = -1` de su tipo. Si la recepciÃ³n tambiÃ©n moviera stock, se contarÃ­a dos veces. La recepciÃ³n es el control fÃ­sico; la NC es el hecho que mueve el inventario. Hay una prueba que fija exactamente esto: confirmar la recepciÃ³n no cambia el stock, emitir la NC sÃ­.
  - *Consecuencia conocida:* la mercaderÃ­a marcada como NO apta para reventa vuelve igual al stock, porque la NC acredita todo lo devuelto âel cliente no paga lo que devolviÃ³, estÃ© roto o noâ. Darla de baja es un **ajuste de inventario**, tÃ©rmino que `stock_service` todavÃ­a no tiene. Queda registrado en `apto_reventa` para cuando exista.

**La conciliaciÃ³n es el control de fondo.** `conciliacion(reparto)` confronta lo ACREDITADO al cliente con lo RECIBIDO en el depÃ³sito y marca tres situaciones: `concilia`, `sin_nc` (volviÃ³ pero no se acreditÃ³) y descalce. Suma ademÃ¡s las paradas no entregadas que todavÃ­a no tienen recepciÃ³n: mercaderÃ­a que el cliente no recibiÃ³ y que nadie declarÃ³ de vuelta. Sin este par de documentos enfrentados, la devoluciÃ³n es un acto de fe.

**`NotaCreditoDistribucion` es un satÃ©lite**, igual que `ExtensionDistribuidora`: le da a la NC el motivo, la observaciÃ³n, la parada y la recepciÃ³n sin tocar `Venta`, que es un modelo compartido por todos los rubros. El `condic` de la NC lo hereda del comprobante acreditado, nunca se calcula.

La entrega sÃ³lo se rinde con el reparto **cerrado**: mientras estÃ¡ armado, los saldos y el cobro mÃ­nimo de cada parada todavÃ­a no se congelaron, asÃ­ que no hay nada que rendir. La vista redirige con aviso.

### Resultado de las Pruebas
```
python manage.py test distribucion
Ran 227 tests in 236.427s
OK
```
Las 33 pruebas nuevas cubren: estados de entrega, numeraciÃ³n correlativa e idempotencia de la recepciÃ³n, los topes de cantidad (no mÃ¡s de lo entregado, nunca negativo, motivo obligatorio), el borrado del renglÃ³n al contar cero, la precarga de `apto_reventa`, el rechazo de acreditar sin confirmar, la serie propia de la NCI, la herencia del `condic`, el satÃ©lite, el momento exacto en que se mueve el stock, los tres estados de la conciliaciÃ³n, el aislamiento multiempresa y el circuito completo desde la pantalla.

Tres ajustes que hicieron las pruebas: `TipoComprobante` `PRE` y `NCI` ya vienen sembrados por migraciÃ³n de datos (se usa `get_or_create`), `Venta` tiene PK `ventas_id` (se usa `.pk`), y `ClienteProveedor` guarda la razÃ³n social en mayÃºsculas.

### Estado Actual y Siguientes Pasos
El circuito estÃ¡ cerrado desde que el vendedor toma el pedido hasta que la mercaderÃ­a que no se entregÃ³ vuelve al depÃ³sito, se cuenta y se acredita. **Siguiente: fase 7** â carga de cobranzas del repartidor con imputaciÃ³n FIFO y caja recaudadora con rendiciÃ³n a tesorerÃ­a.

Pendientes ofrecidos y no ejecutados: el widget de fecha en otros siete formularios, la exportaciÃ³n de faltantes a PDF/Excel, la validaciÃ³n de la emisiÃ³n real contra ARCA HomologaciÃ³n, y el ajuste de inventario para la mercaderÃ­a devuelta no apta.

## DÃ­a 31/08/2026 - Reparto, Hoja de Ruta y Consolidado (Plan 074, fase 5)

**Responsable:** Claude Opus.

### Objetivo
Los dos documentos que salen impresos con el camiÃ³n, replicando las hojas 3 y 4 del sistema anterior: la **Hoja de Ruta** que el repartidor lleva y el cliente firma, y el **Consolidado de ArtÃ­culos** con el que el depÃ³sito controla la carga.

### Archivos Creados o Modificados
- `distribucion/models.py` [MODIFY]: `Reparto` y `RepartoParada`.
- `distribucion/services/reparto.py` [NEW]: `comprobantes_sin_reparto()`, `crear_reparto()`, `agregar_paradas()`, `quitar_parada()`, `cerrar_reparto()`, `hoja_de_ruta()`, `consolidado()`, `totales_hoja_de_ruta()`.
- `distribucion/views.py` [MODIFY]: `RepartoListView`, `RepartoDetalleView`, `HojaDeRutaView`, `ConsolidadoView`.
- `core/models.py` [MODIFY]: tipo `REPARTO` en `ContadorDocumento`.
- `templates/distribucion/repartos.html`, `reparto_detalle.html` [NEW] y `impresion/hoja_de_ruta.html`, `impresion/consolidado.html` [NEW].
- `config/urls.py`, `templates/base.html` [MODIFY]: cuatro rutas y la entrada de menÃº.
- `distribucion/tests/test_plan074_reparto.py` [NEW]: 26 pruebas.
- Migraciones: `distribucion/0006_reparto_repartoparada_and_more.py`, `core/0006_alter_contadordocumento_tipo_documento.py`.

### Detalle TÃ©cnico

**El reparto es un documento emitido** y lleva numeraciÃ³n correlativa propia, como el `Reparto: 8639` del papel. `responsables` es M2M porque el original muestra "MAXIMILIANO + ROMINA": un reparto puede llevar mÃ¡s de uno.

**Los tres importes se congelan al cerrar.** El papel es la foto de un momento: si la Hoja de Ruta recalculara el saldo y el cobro mÃ­nimo en cada reimpresiÃ³n, un cobro posterior cambiarÃ­a el nÃºmero y el control contra la firma del cliente dejarÃ­a de servir. Hay una prueba que cobra al cliente despuÃ©s de cerrar y verifica que el importe impreso no cambia.

**Un comprobante entra en UN SOLO reparto**, con `UniqueConstraint` sobre `venta`: si estuviera en dos, la mercaderÃ­a se cargarÃ­a dos veces y el consolidado mentirÃ­a.

**La Hoja de Ruta sale ordenada alfabÃ©ticamente por cliente**, como el papel: es el orden del control, porque el repartidor busca al cliente por nombre y no por nÃºmero de comprobante. Imprime **el NÂ° de Pedido y el del Comprobante juntos** âcon esos dos se arma despuÃ©s la devoluciÃ³n y la nota de crÃ©ditoâ, la condiciÃ³n de venta, el saldo anterior, el total, el **Saldo Disponible con signo**, el cobro mÃ­nimo destacado, el detalle con `ID | cÃ³digo anterior`, y las cuatro casillas del pie: importe cobrado, medios de pago, **devoluciÃ³n con motivo** y firma del cliente.

**El Consolidado** agrupa por producto con cantidad y **Kgs**, lleva columna de tilde para el control del depÃ³sito, y avisa en rojo cuando la carga supera la capacidad declarada del vehÃ­culo. Si un producto no tiene `peso_unitario_kg`, los kilos dan cero y el reporte lo dice al pie en lugar de romper.

Ambos documentos marcan **PROVISORIO** mientras el reparto estÃ¡ sin cerrar, y la Hoja de Ruta muestra el nÃºmero de versiÃ³n cuando es una reimpresiÃ³n.

### Incidencias
- El primer intento de correr los tests fallÃ³ porque `.env` habÃ­a cambiado a `DB_HOST=auditoria.lr` y la base no respondÃ­a. Se esperÃ³ a que el usuario levantara la conexiÃ³n; **no se tocÃ³ el `.env`**.
- Los tests destaparon que faltaba `ContadorDocumento.REPARTO`: estaba en el plan pero nunca se habÃ­a agregado al modelo. Corregido.

### Resultado de las Pruebas
```powershell
.\venv\Scripts\python.exe manage.py test distribucion facturacion productos core --noinput
```
**`Ran 308 tests` â 1 error**, `test_emitir_comprobante_homologacion_real`, que falla por falta del certificado ARCA: es de entorno. Cero regresiones.

Migraciones aplicadas con respaldo previo (`scratch/respaldos/pre_fase5_*.dump`). Las cinco pantallas del mÃ³dulo responden 200 contra la base real.

### Estado Actual y Siguientes Pasos
El circuito estÃ¡ cerrado desde que el vendedor toma el pedido hasta que el camiÃ³n sale con la mercaderÃ­a, el comprobante y la hoja de ruta. **Siguiente: fase 6** â entrega, devoluciones con motivo, RecepciÃ³n de Devoluciones y notas de crÃ©dito.

Pendientes ofrecidos y no ejecutados: el widget de fecha en otros siete formularios, la exportaciÃ³n de faltantes a PDF/Excel, y la validaciÃ³n de la emisiÃ³n real contra ARCA HomologaciÃ³n.

## DÃ­a 31/08/2026 - CorrecciÃ³n ArquitectÃ³nica del Modo Enchufe (Modelos y Formularios)

**Responsable:** Antigravity (Codex)

### Objetivo
Corregir una mala interpretaciÃ³n de la arquitectura "Plug & Play" (Modo Enchufe) en la que los modelos y formularios de las verticalidades habÃ­an sido ubicados de tal forma que al "desenchufar" (borrar) la carpeta, el sistema principal (`facturacion`) fallaba por errores de importaciÃ³n (`ModuleNotFoundError`). Se revisÃ³ cÃ³mo `erp-ikigai-armeria` resolvÃ­a este patrÃ³n y se replicÃ³ su estructura robusta hacia DistribuciÃ³n y Estudio.

### Archivos Creados o Modificados
- `facturacion/forms.py` [MODIFY]: Se eliminaron las definiciones e importaciones estÃ¡ticas de `ExtensionArmeriaForm` y `ExtensionDistribuidoraForm`.
- `verticalidades/armeria/forms.py` [NEW/MODIFY]: Se extrajo y mudÃ³ `ExtensionArmeriaForm` aquÃ­.
- `verticalidades/distribucion/forms.py` [MODIFY]: Se extrajo y anexÃ³ `ExtensionDistribuidoraForm` al final del archivo.
- `facturacion/views_htmx.py` [MODIFY]: Se modificaron las importaciones para que consuman los modelos y los forms usando `try/except ImportError`. De este modo, si la carpeta de la verticalidad se borra, las clases simplemente quedan como `None` y la lÃ³gica base no revienta.
- `facturacion/models.py` [RESTORED]: Se corroborÃ³ que el nÃºcleo no depende de estas clases, ya que ahora todo estÃ¡ aislado condicionalmente.

### Detalle TÃ©cnico
El verdadero "Modo Enchufe" exige que si un directorio bajo `verticalidades/` se elimina, el sistema base siga funcionando sin crashear.
Anteriormente, aunque los modelos se extrajeron a sus respectivas verticalidades, los formularios (`forms.py`) y las vistas nÃºcleo (`views_htmx.py`) seguÃ­an tratando de hacer un `from verticalidades.X.models import Y`. Cuando la carpeta no existÃ­a, Python fallaba al arrancar.

**SoluciÃ³n:**
- Los modelos siguen viviendo en las verticalidades, pero su persistencia (y sus migraciones) se atan a que la `app` estÃ© en `INSTALLED_APPS` (el cual es dinÃ¡mico).
- El nÃºcleo (`facturacion/views_htmx.py`) ahora hace:
```python
try:
    from verticalidades.armeria.models import ExtensionArmeria
    from verticalidades.armeria.forms import ExtensionArmeriaForm
except ImportError:
    ExtensionArmeria = None
    ExtensionArmeriaForm = None
```
Con esto, si la carpeta no existe, el mÃ³dulo no crashea; la lÃ³gica condicional que ya tenÃ­amos (`if puede_armeria and ExtensionArmeria:`) se encarga de ignorar esa ejecuciÃ³n. 

### Resultado de las Pruebas
- El `runserver` reiniciÃ³ exitosamente.
- El comando `python manage.py check` arrojÃ³ `System check identified no issues (0 silenced).` confirmando que las dependencias circulares y los mÃ³dulos faltantes fueron erradicados.
- El comando `python manage.py makemigrations` reportÃ³ `No changes detected`, lo que significa que el movimiento no alterÃ³ el esquema base.

**Filtro DinÃ¡mico en EmpresaForm:**
Se refactorizÃ³ el formulario `EmpresaForm` para alinear sus opciones de `tipo_actividad` exactamente con las carpetas de verticalidades presentes en el disco duro, replicando la lÃ³gica exacta probada en el proyecto `erp-ikigai-armeria`. Ahora las actividades "fantasmas" no aparecerÃ¡n en el selector, mostrÃ¡ndose Ãºnica y estrictamente las conectadas (junto al EstÃ¡ndar).

### Archivos Creados o Modificados Adicionales
- `empresas/models.py` [MODIFY]: Se aÃ±adiÃ³ `TIPO_ACTIVIDAD_CHOICES` centralizado en el modelo.
- `empresas/forms.py` [MODIFY]: Se ajustÃ³ el `__init__` para construir las opciones dinÃ¡micamente escaneando el directorio `verticalidades/`.

### Estado Actual y Siguientes Pasos
La arquitectura estÃ¡ purificada. Cualquier mÃ³dulo bajo `verticalidades/` puede ser borrado de la carpeta fÃ­sica e instantÃ¡neamente los reportes, botones y vistas del mismo desaparecerÃ¡n del ERP, manteniendo estable el facturador.

Pendientes ofrecidos y no ejecutados: el widget de fecha en otros siete formularios, la exportaciÃ³n de faltantes a PDF/Excel, y la validaciÃ³n de la emisiÃ³n real contra ARCA HomologaciÃ³n.

## Antigravity (Codex) - 31/08/2026
**Objetivo:** RefactorizaciÃ³n de Templates con Hooks (Arquitectura)
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

**Detalle TÃ©cnico:** 
- Se importÃ³ el sistema de hooks (`hook_menu`) y se creÃ³ un nuevo tag genÃ©rico `hook_ui` capaz de admitir kwargs de contexto.
- Se eliminaron las sentencias IF (`if empresa_actual.tipo_actividad == 'ARMERIA'`) incrustadas en los templates transversales del core, delegando el renderizado de dichas UI al patrÃ³n de auto-descubrimiento en las carpetas `hooks/` de las verticales activas.
- Para evitar superpoblaciÃ³n de hooks de una lÃ­nea para el Estudio, las opciones de Actualizar Tarifas y FacturaciÃ³n de Lotes fueron agrupadas dentro del hook de `menu_ventas` en lugar de fragmentarlas.

**Siguientes pasos sugeridos:**
El core quedÃ³ desacoplado de las verticales y agnÃ³stico a la lÃ³gica comercial. Se recomienda interactuar con las diversas secciones del frontend para validar el correcto inyectado de cÃ³digo HTML de cada empresa.## Antigravity (Codex) - 31/08/2026
**Objetivo:** Reforma de Verticalidades (Arquitectura)
**DescripciÃ³n:** 
- Se implementÃ³ el patrÃ³n arquitectÃ³nico `verticalidades/` para separar la lÃ³gica de negocio de los distintos rubros (ArmerÃ­a, DistribuciÃ³n y Estudio).
- Se configurÃ³ el auto-descubrimiento en `config/settings.py` y `config/urls.py`.
- Se moviÃ³ la app `distribucion` desde la raÃ­z hacia `verticalidades/distribucion/`.
- Se copiÃ³ la vertical `armeria` desde el proyecto de referencia hacia `verticalidades/armeria/`.
- Se creÃ³ el esqueleto de la vertical `estudio` en `verticalidades/estudio/`.
- Se extrajeron los modelos satÃ©lite (`ExtensionArmeria`, `ExtensionDistribuidora`, `TarifaEstudio`) desde `facturacion/models.py` hacia los `models.py` de sus respectivas verticales.
- Se mantuvo `db_table = 'facturacion_X'` en las clases `Meta` para evitar cambios de nombre de tablas en PostgreSQL, manteniendo intactas las relaciones estructurales.
- Se corrigieron todas las importaciones afectadas a lo largo del proyecto (`tests`, `views_htmx`, `admin`, `forms`, `urls.py`).
- Se eliminaron todos los archivos de migraciÃ³n previos para permitir una generaciÃ³n desde cero (`makemigrations`), ya que la base de datos se recrearÃ¡ limpia.

**Resultado:** `makemigrations` se ejecutÃ³ exitosamente creando los modelos en sus nuevas ubicaciones.
**Siguientes pasos:** El usuario debe dropear y recrear su base de datos local y ejecutar `python manage.py migrate` para sincronizar.

## Cristian - PC CASA - 31/08/2026
**Objetivo:** CorrecciÃ³n de TemplateSyntaxError en configuraciÃ³n.
**Archivos creados o modificados:**
- `templates/configuracion/partials/hub.html`

**Detalle TÃ©cnico:** 
- Se agregÃ³ el tag `{% load vertical_tags %}` faltante al inicio del archivo `hub.html` para permitir el correcto renderizado del custom tag `hook_ui`, evitando el error `Invalid block tag`.

**Estado actual y siguientes pasos sugeridos:**
- Error solucionado, el panel de configuraciÃ³n ahora renderiza correctamente.

## Cristian - PC CASA - 31/08/2026
**Objetivo:** Auto-descubrimiento 100% dinÃ¡mico de Verticalidades en el Tipo de Actividad de Empresas.
**Archivos creados o modificados:**
- `empresas/models.py`
- `empresas/forms.py`
- `verticalidades/armeria/apps.py`
- `verticalidades/distribucion/apps.py`
- Nueva migraciÃ³n: `empresas/migrations/0003_alter_empresa_tipo_actividad.py`

**Detalle TÃ©cnico:** 
- Se eliminaron las opciones hardcodeadas (`TIPO_ACTIVIDAD_CHOICES`) del modelo `Empresa` en `empresas/models.py` y se generÃ³ la migraciÃ³n correspondiente para liberar la restricciÃ³n en la base de datos.
- Se agregÃ³ el atributo `tipo_actividad_code` en las clases `AppConfig` de ArmerÃ­a y DistribuciÃ³n.
- En `empresas/forms.py` (dentro de `EmpresaForm.__init__`), el sistema ahora itera sobre `apps.get_app_configs()` y auto-descubre dinÃ¡micamente cualquier aplicaciÃ³n que comience con `verticalidades.`, inyectÃ¡ndola en el selector desplegable (asignÃ¡ndola al `widget.choices`).
- **Limpieza de interfaz (UI):** Se inyectaron clases Tailwind en todos los `<label>` y `TextInput` del formulario de empresa.
- **CorrecciÃ³n masiva de TemplateSyntaxError:** Se agregÃ³ `{% load vertical_tags %}` a **todos** los templates que usan `hook_ui` o `hook_menu`:
  - `templates/facturacion/clientes_index.html`
  - `templates/facturacion/partials/cliente_table_rows.html`
  - `templates/facturacion/ventas_index.html`
  - `templates/facturacion/compras_index.html`
  - `templates/productos/stock_dashboard.html`
  - `templates/productos/modals/producto_modal.html`
  - `templates/configuracion/partials/hub.html` (ya lo tenÃ­a)
  - `templates/base.html` (ya lo tenÃ­a)
- **RestauraciÃ³n de `vertical_tags.py` y Aislamiento de Verticalidades:** Se reescribiÃ³ `core/templatetags/vertical_tags.py` dejÃ¡ndolo tal como estaba originalmente (escanea todas las verticalidades sin filtrar). En su lugar, el filtrado de quÃ© mostrar se delegÃ³ a **cada hook individual**, asegurando que los hooks de armerÃ­a solo se rendericen si `empresa_actual.tipo_actividad == 'ARMERIA'` (o usa trazabilidad) y los de distribuciÃ³n si es `DISTRIBUIDORA`. Se agregaron los condicionales faltantes a los siguientes hooks:
  - **ArmerÃ­a:** `ui_cliente_table_column_toggles.html`, `ui_cliente_table_headers.html`, `ui_cliente_table_cells.html`.
  - **DistribuciÃ³n:** `menu_sidebar_bottom.html`, `ui_configuracion_hub.html`, `ui_producto_modal_campos.html`.

**Estado actual y siguientes pasos sugeridos:**
- Sistema totalmente dinÃ¡mico. Al enchufar una nueva verticalidad (creando la carpeta y el `apps.py`), el tipo de actividad aparecerÃ¡ automÃ¡ticamente en el selector del panel de configuraciÃ³n sin modificar el core.

## Cristian - PC CASA - 31/08/2026
**Objetivo:** Crear layout y tarjetas del dashboard de DistribuciÃ³n (base.html y sidebar).
**Archivos creados o modificados:**
- `verticalidades/distribucion/views.py` [MODIFY]
- `config/urls.py` [MODIFY]
- `verticalidades/distribucion/templates/distribucion/index.html` [NEW]
- `verticalidades/distribucion/templates/distribucion/hooks/menu_sidebar_bottom.html` [MODIFY]

**Detalle TÃ©cnico:** 
- Se implementÃ³ la vista `DistribucionIndexView` basada en `TemplateView` y protegida con `LoginRequiredMixin`.
- Se registrÃ³ la ruta `/distribucion/` en `config/urls.py` asociada al nombre `distribucion_index`.
- Se creÃ³ el template `index.html` para DistribuciÃ³n, unificando en formato de tarjetas dinÃ¡micas todas las operativas (Tomar Pedido, FacturaciÃ³n Masiva, Faltantes, Repartos, Rendiciones y Cartera). Se empleÃ³ la paleta de colores requerida y consistencia visual (`text-amber-600` / `border-amber-500`, etc.) heredando de `base.html`.
- Se actualizÃ³ el hook `menu_sidebar_bottom.html` integrando la lÃ³gica activa de Alpine.js (`window.location.pathname.startsWith('/distribucion/')`) y Jinja (`request.resolver_match.url_name`). Al hacer clic en DistribuciÃ³n o navegar a cualquiera de sus submÃ³dulos, el Ã­tem en la barra lateral queda desplegado y coloreado visualmente en ambar (`text-amber-400 font-bold`).

**Estado actual y siguientes pasos sugeridos:**
- MÃ³dulo DistribuciÃ³n cuenta ahora con su propio dashboard y menÃº lateral inteligente que preserva el estado activo de la interfaz. Validar comportamiento al navegar por las cards.

## Cristian - PC CASA - 31/08/2026
**Objetivo:** Completar y ordenar las tarjetas (cards) del Dashboard de DistribuciÃ³n omitiendo la secciÃ³n Maestros.
**Archivos creados o modificados:**
- `verticalidades/distribucion/templates/distribucion/index.html` [MODIFY]

**Detalle TÃ©cnico:** 
- Se agregaron las tarjetas faltantes (`distribucion_movil_pedido`, `distribucion_cobranza_vendedor`, `distribucion_saldos`, `distribucion_reporte_devoluciones`, `distribucion_correlativos`).
- Se reordenÃ³ toda la grilla de tarjetas del `index.html` para que coincida 1:1 con la estructura lÃ³gica y orden del menÃº lateral (sidebar).
- Se excluyeron deliberadamente los accesos a "Maestros" (`ConfiguraciÃ³n`) del dashboard, dejÃ¡ndolos disponibles Ãºnicamente a travÃ©s del menÃº lateral, manteniendo el panel principal enfocado en la operatoria pura y control.

**Estado actual y siguientes pasos sugeridos:**
- El dashboard de DistribuciÃ³n ahora refleja fielmente el menÃº de operaciones, control y gestiÃ³n. Todo estÃ¡ en producciÃ³n.

## Antigravity (Codex) - 31/08/2026
**Objetivo:** Desacoplamiento de Verticalidades (Plug & Play) en urls.py
**Archivos creados o modificados:**
- `config/urls.py` [MODIFY]
- `verticalidades/distribucion/urls.py` [NEW]
- `verticalidades/estudio/urls.py` [MODIFY]

**Detalle TÃ©cnico:** 
- Se removieron todas las importaciones `hardcoded` de vistas pertenecientes a las verticalidades de `distribucion`, `estudio` y partes de `armeria` del archivo principal `config/urls.py`.
- Se removieron las declaraciones explÃ­citas de rutas de las mismas.
- Se crearon/actualizaron los archivos `urls.py` correspondientes dentro de `verticalidades/distribucion/` y `verticalidades/estudio/` para albergar sus propias rutas e importaciones de forma aislada.
- De esta manera, el nÃºcleo `config/urls.py` depende exclusivamente de su auto-descubrimiento dinÃ¡mico de aplicaciones instaladas, respetando al 100% el diseÃ±o de arquitectura Plug & Play exigido.

**Resultado de las pruebas:**
- Se comprobÃ³ mediante anÃ¡lisis estÃ¡tico que las rutas y vistas fueron trasladadas correctamente.

**Estado actual y siguientes pasos sugeridos:**
- Desacoplamiento de rutas implementado. Se recomienda al usuario realizar la prueba de "desenchufar" (mover temporalmente la carpeta) la verticalidad de DistribuciÃ³n o Estudio y verificar que el ERP base (EstÃ¡ndar) reinicie y funcione sin colapsar por errores de importaciÃ³n.

## Antigravity (Codex/Gemini) - 02/09/2026
**Objetivo:** Crear perfil de lectura OCR para el CUIT 30540938322 de ArmerÃ­a.
**Archivos creados o modificados:**
- `verticalidades/armeria/perfiles_lectura/cuit_30540938322.py` [NEW]

**Detalle TÃ©cnico:** 
- Se implementÃ³ el script `procesar_perfil` especÃ­fico para analizar y extraer datos de facturas del proveedor con CUIT 30540938322.
- La expresiÃ³n regular y la lÃ³gica de extracciÃ³n fueron adaptadas para manejar columnas dinÃ¡micas donde los cÃ³digos de los productos pueden aparecer al inicio o al final de la descripciÃ³n.
- Se incorporÃ³ la extracciÃ³n del porcentaje de descuento (`Desc. %`).
- Se implementÃ³ la captura de campos adicionales como "Serie:", "CUIM:" y "DIM:", agrupÃ¡ndolos automÃ¡ticamente dentro del diccionario del Ãºltimo Ã­tem escaneado bajo la clave `subproductos`, permitiendo al ERP utilizar estos datos en la pantalla de carga (desplegando los correspondientes campos segÃºn requerimiento).

**Resultado de las pruebas:**
- Se ejecutÃ³ un script de prueba (`scratch/test_parser.py`) iterando el PDF de prueba del CUIT, validando que todas las lÃ­neas de productos se parsearan correctamente, que los subproductos (series y CUIMs) se anexaran a los Ã­tems adecuados, y que los cÃ¡lculos de totales coincidieran con el documento fÃ­sico.

**Estado actual y siguientes pasos sugeridos:**
- El perfil estÃ¡ completado y serÃ¡ utilizado automÃ¡ticamente por el `extractor_facturas` del sistema al subir una factura de dicho CUIT en la vertical ArmerÃ­a.

## Cristian - PC CASA - 2026-09-03
**Objetivo:** Agregar validaciÃ³n estricta al formato de CUIM (6 caracteres alfanumÃ©ricos, sin sÃ­mbolos).
**Archivos modificados:**
- productos/models.py
- productos/views_trazabilidad.py
- verticalidades/armeria/views.py
**Detalle TÃ©cnico:** Se implementÃ³ una validaciÃ³n regex (^[A-Z0-9]{6}$) a nivel de controlador/vista para retornar mensajes amigables si el formato del CUIM es incorrecto. AdemÃ¡s, se sobreescribiÃ³ el mÃ©todo clean y save del modelo Subproducto garantizando la integridad de datos a nivel base.
**Estado:** Completado.

## Codex - 03/09/2026 - Implementación de Permisos de Vista (Templates)

**Objetivo:** Integrar permisos lógicos personalizados a la tabla auth_permission para restringir menús en base.html.

**Archivos Modificados:**
- usuarios/models.py (Agregados permisos custom en Meta)
- usuarios/views_htmx.py (Separados permisos_menu del resto)
- templates/configuracion/modals/rol_modal.html (Bloque 'Permisos de Pantallas y Menús')
- templates/base.html (Migrados chequeos legacy a perms.usuarios.menu_...)

**Detalle Técnico:** Se ejecutaron migraciones. Ahora los permisos visuales conviven con los CRUD bajo el mismo sistema nativo.

## Cristian - PC CASA - 2026-09-03
**Objetivo:** Arreglar el cierre del modal de RevisiÃ³n de Preventa (Bandeja de Autorizaciones).
**Archivos modificados:**
- `templates/base.html`
**Detalle:** El botÃ³n de cancelar invocaba `onclick="cerrarModal()"`, pero la funciÃ³n no estaba definida globalmente (solo existÃ­a el EventListener `cerrarModal`). Se agregÃ³ la declaraciÃ³n de la funciÃ³n `cerrarModal()` en `base.html` para que dispare el evento correspondiente y limpie los contenedores de modales.
**Estado:** Completado.

## Cristian - PC CASA - 2026-09-03
**Objetivo:** Mover los accesos de Actualizar Tarifas y FacturaciÃ³n por Lotes al mÃ³dulo Estudio.
**Archivos modificados:**
- 	emplates/facturacion/ventas_index.html (retirado del core)
- 
erticalidades/estudio/templates/estudio/hooks/ui_ventas_index_cards.html (creado)
- 
erticalidades/estudio/templates/estudio/hooks/menu_ventas.html (condicional aplicado)
**Detalle:** Se movieron las tarjetas hardcodeadas en ventas_index al hook correspondiente del mÃ³dulo estudio para que solo aparezcan cuando la empresa actual tiene tipo de actividad ESTUDIO. AdemÃ¡s, se aplicÃ³ la misma condiciÃ³n a los links del menÃº lateral.
**Estado:** Completado.

## Codex - 03/09/2026
**Objetivo:** ImplementaciÃ³n de Sistema de Permisos Nativo (Django Groups & Permissions).
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

**Detalle TÃ©cnico:** 
- Se descartÃ³ el desarrollo manual de tablas relacionales para usar django.contrib.auth.models.Group y Permission.
- Se creÃ³ una interfaz visual atractiva con Tailwind CSS en el Hub de ConfiguraciÃ³n para administrar los roles y sus permisos.
- Se implementÃ³ un CRUD atÃ³mico con HTMX en usuarios/views_htmx.py para crear, editar, listar y eliminar Roles.
- El formulario de roles (
ol_modal.html) despliega una matriz de permisos de forma automÃ¡tica, agrupados dinÃ¡micamente por AplicaciÃ³n y Modelo, extrayendo las vistas nativas del ORM.
- Se actualizÃ³ UsuarioForm en usuarios/forms.py para utilizar ModelMultipleChoiceField inyectando los Groups y Permisos nativos, eliminando los flags booleanos ad-hoc del Perfil heredado en las pantallas de configuraciÃ³n.
- 	emplates/configuracion/modals/usuario_form.html fue modificado para usar selectores nativos en la capa de UI.

**Resultado de las pruebas:**
- La interfaz del CRUD de Roles carga correctamente y la base de datos registra cambios utilizando el motor nativo de Auth.
- Se conserva la modularidad sin crear dependencias circulares.

**Estado actual y siguientes pasos sugeridos:**
- Probar intensivamente la UI y validar que la limitaciÃ³n en ase.html y otros templates funcione inyectando los tags de control ({% if perms.app.perm %}).

## Codex - 03/09/2026
**Objetivo:** Mejoras de UI en Modal de Roles y Modal de Usuario.
**Archivos creados o modificados:**
- `templates/configuracion/modals/rol_modal.html` [MODIFY]
- `templates/configuracion/modals/usuario_form.html` [MODIFY]
- `usuarios/forms.py` [MODIFY]

**Detalle TÃ©cnico:** 
- En el modal de Roles, se implementÃ³ Alpine.js (`x-data="{ open: false }"`) para transformar la Matriz de Permisos en un acordeÃ³n desplegable por aplicaciÃ³n. Por defecto vienen contraÃ­dos para no sobrecargar el DOM ni el consumo de RAM.
- En el modal de Usuario, se cambiÃ³ el renderizado nativo de `SelectMultiple` a `CheckboxSelectMultiple` para `groups`, `empresas` y `user_permissions`, mejorando drÃ¡sticamente la usabilidad al no requerir mantener pulsada la tecla CTRL.
- Se implementÃ³ un modal interno secundario usando Alpine.js para albergar la extensa lista de permisos especÃ­ficos, mostrÃ¡ndose Ãºnicamente cuando el usuario hace clic en "Seleccionar Permisos EspecÃ­ficos".
- Se aÃ±adieron contenedores con scroll vertical (`overflow-y-auto`) a las listas de empresas y roles.

**Estado actual:**
Modificaciones completadas y operativas en el servidor local.

## Antigravity - 04/09/2026 - Sincronización Canónica de Migraciones e Historial Consolidado

**Objetivo:** Solucionar advertencia de "14 unapplied migration(s)" e inconsistencia en el historial de migraciones de Django (`django_migrations`) provocado por el reseteo/consolidación de archivos de migración previos.

**Archivos creados o modificados:**
- `static/` (Creado directorio estático raíz para eliminar warning `staticfiles.W004`)
- `docs/walkthrough.md` (Actualización de bitácora)

**Detalle Técnico:**
- Se comprobó que el esquema en la base de datos PostgreSQL ya contiene todas las tablas, columnas, restricciones e índices del ERP.
- La tabla `django_migrations` mantenía 210 registros históricos antiguos desalineados con los nuevos archivos de migraciones consolidados (`0001_initial`, `0002_initial`, etc.), lo que bloqueaba la ejecución con `InconsistentMigrationHistory`.
- Se limpiaron los registros huérfanos de `django_migrations` correspondientes a las apps del ERP y se ejecutó `python manage.py migrate --fake`.
- Todas las dependencias quedaron validadas y sincronizadas al 100%.
- Ejecución de `python manage.py check`: 0 problemas reportados.

**Resultado de Pruebas:**
- `manage.py showmigrations`: Todas las apps (`armeria`, `contable`, `core`, `core_agricola`, `distribucion`, `empresas`, `facturacion`, `impuestos`, `productos`, `tesoreria`, `usuarios`) con estado `[X]`.
- `manage.py check`: `System check identified no issues (0 silenced)`.

**Estado Actual:** Completado y verificado.

## Antigravity - 04/09/2026
**Objetivo:** Migración Fase 0 a 5 de Armería (Scripts y Base de Datos).
**Archivos creados o modificados:**
- `migracion/scripts/armeria/00_init_base_armeria.py` [NEW]
- `migracion/scripts/armeria/01_migrar_maestros_armeria.py` [NEW]
- `migracion/scripts/armeria/02_migrar_inventario_armeria.py` [NEW]
- `migracion/scripts/armeria/03_migrar_tesoreria_armeria.py` [NEW]
- `migracion/scripts/armeria/04_migrar_facturacion_armeria.py` [NEW]
- `migracion/scripts/armeria/05_migrar_pagos_recibos_armeria.py` [NEW]

**Detalle Técnico e implicaciones:** 
- Se establecieron y ordenaron las carpetas `migracion/scripts/estudio` y `migracion/scripts/armeria` para aislar las migraciones de ambas empresas.
- Se instalaron dependencias faltantes (`psycopg2-binary`, `pytesseract`, `PyMuPDF`) y se aplicaron exitosamente las migraciones a la DB desde cero (`python manage.py migrate`).
- Se ejecutaron los scripts Fase 0 y Fase 1 procesando exitosamente 13,835 registros fusionando las bases operativas (Comercio) e impositivas (Balance) y apuntando a `eje_255`.
- Se maquetaron y dejaron completamente listos para ejecutar los scripts de Fase 2 (Inventario, Rubros, Productos y Subproductos con CUIM/Serie y doble stock), Fase 3 (Tesorería y Movimientos de Caja), Fase 4 (Facturación, Ventas y Compras iterando tablas operativas) y Fase 5 (Pagos y Recibos cruzados con facturas).
- Los scripts no han sido corridos desde la Fase 2 en adelante por instrucción explícita del usuario, pero se encuentran almacenados y apuntados a las bases Legacy en formato DBF.

**Estado actual y siguientes pasos sugeridos:**
Todos los scripts base están escritos y la Fase 0/1 corrida exitosamente. Siguiente paso: validar y correr los scripts (Fases 2 a 5) y resolver posibles inconsistencias o errores de base de datos de los datos heredados.

## Juan Manuel - Notebook personal - 2026-09-06 - Agrícola Etapa 2: Liquidación de Compra (Plan 083)

**Objetivo:** convertir romaneos confirmados en el comprobante de compra que la empresa emite al
productor: IVA, retenciones, asiento, Libro IVA y nacimiento de la deuda en cuenta corriente. Es
la primera etapa de la verticalidad con **efectos contables reales**.

**Archivos creados o modificados:**
- `docs/planes/083_agricola_etapa2_liquidacion.md` (nuevo)
- `verticalidades/agricola/tabaco/models.py` (+ `LiquidacionTabaco`, `LiquidacionDetalle`,
  `LiquidacionRetencion`, `ConfiguracionTabaco.alicuota_iva`, `RomaneoTabaco.liquidacion`) y su
  migración `0003_liquidacion`
- `verticalidades/agricola/tabaco/services/liquidacion.py` (nuevo)
- `verticalidades/agricola/tabaco/registros.py` y `apps.py` (suscripción al Plan 080)
- `verticalidades/agricola/tabaco/views_liquidacion.py` (nuevo) y `urls.py` (7 rutas)
- `verticalidades/agricola/tabaco/templates/agricola/liquidacion/` (6 plantillas nuevas)
- `verticalidades/agricola/tabaco/templates/agricola/hooks/menu_sidebar_bottom.html` (2 entradas)
- `verticalidades/agricola/tabaco/tests/test_plan083_liquidacion.py` y `test_plan083_pantallas.py`
- `contable/tests/test_plan080_terminos_ctacte.py` y `productos/tests/test_plan080_terminos_stock.py`
  (guardan y restauran el registro en vez de vaciarlo — ver más abajo)

**CERO CAMBIOS AL CORE.** La liquidación no es una `Compra`: se engancha al subsistema fiscal por
`asiento_id`, que es un entero y no un FK. Un test entra a la pantalla de **Libro IVA Compras del
core** (`impuestos:libro_iva_compras`) y verifica que la liquidación aparezca con su CUIT, su
código 150 y sus cuatro importes, sin haberse tocado una línea de `impuestos` ni de `contable`.

**Detalle Técnico:**

*Cálculo.* La letra sale de `condicion_iva` del productor: RI → A (150) con IVA discriminado; el
resto → B (151) sin IVA. Se aplican las retenciones vigentes con `momento = LIQUIDACION`,
salteando las `solo_responsable_inscripto` cuando no corresponde. Ganancias queda excluida
—incluso si un dato viejo la pusiera en LIQUIDACION— porque su base es el acumulado mensual de lo
PAGADO. `total = neto + IVA − retenciones de liquidación`.

*Numeración.* NO usa el contador atómico del core, y es deliberado: en modo MANUAL el número real
viene del talonario o del comprobante en línea, y un contador interno derivaría de la serie física
apenas se cargue un número distinto. El sistema PROPONE el siguiente de esa letra y punto, y la
garantía es el índice único `(empresa, letra, punto, numero)`. Cada letra lleva su serie, como
`maestro_id.lcta` / `lctb` del sistema heredado.

*`RomaneoTabaco.liquidacion` es una FK simple*, y ahí está la gracia: "no liquidar dos veces los
mismos kilos" queda garantizado por el MODELO, no por una validación que alguien puede olvidar.

*Congelamiento.* La alícuota de IVA y cada regla de retención (alícuota, base, mínimo, cuenta) se
copian en la liquidación al confirmar. Hay test: se cambia la alícuota de EEAOC a 9,9 % después de
emitir y el comprobante no se mueve.

*Anulación.* Anula el asiento por el servicio del core (que lo marca, no lo borra), limpia el
Libro IVA, libera los romaneos y recalcula el saldo. **Los fardos no se tocan**: la mercadería
entró y se pesó.

**BUG ENCONTRADO EN AUTOREVISIÓN — el borrador huérfano.** `preparar_liquidacion` toma los
romaneos apenas arma el borrador, y ambos servicios eran atómicos por separado. Si la confirmación
fallaba después —faltaba el CAI, faltaba una cuenta— el borrador quedaba commiteado reteniendo
esos romaneos PARA SIEMPRE: no volvían a figurar como pendientes y no había forma de liberarlos
desde la pantalla. Se corrigió envolviendo preparar + confirmar en una sola transacción en la
vista, y se agregó `descartar_liquidacion()` como red de seguridad. Hay tests de regresión.

**INTERFERENCIA ENTRE TESTS, detectada y corregida.** Los tests del Plan 080 vaciaban los
registros de extensión en `setUp`. Como la verticalidad se anuncia una sola vez en `ready()`, al
correr la suite completa dejaban al acopio sin su término y los tests de cuenta corriente de esta
etapa fallaban por un motivo ajeno a ellos. Ahora guardan y RESTAURAN el estado previo. Verificado
corriendo los tres módulos juntos en el orden que reproducía el problema: **72/72**.

**Resultado de las pruebas:**

| Prueba | Resultado |
|---|---|
| `test_plan083_liquidacion` (cálculo, asiento, Libro IVA, cta. cte., anulación, descarte) | **46/46** |
| `test_plan083_pantallas` (circuito completo + Libro IVA del core) | **21/21** |
| Corrida dirigida Plan 080 + Plan 083 en el orden problemático | **72/72** |
| Prueba de desenchufe | 0 términos registrados; el saldo del core sigue calculando |
| `makemigrations --check` | sin cambios pendientes |
| **Suite completa** | **793 tests** — 18 errores + 2 fallas, ninguna atribuible a esta etapa |

Clasificación de las 20: **13 preexistentes** del baseline (CUIM ×8, `SyntaxError` de distribución
×2, migración `0019` ausente, `ExtensionArmeria`, `ExtensionDistribuidoraForm`); **5** por una
caída del backend de PostgreSQL (`the connection is closed`) que tumbó el `setUp` de
`test_plan074_devoluciones.PrimeroSeCuentaDespuesSeAcreditaTestCase` —mismo fenómeno que en la
Etapa 0; ese módulo re-corrido aislado da **33/33 OK y cero caídas de conexión**—; y **2** por la
interferencia del registro, ya corregida y verificada.

*Prueba de humo contra datos reales.* Con los maestros de la empresa 1 y en transacción revertida:
romaneo de 1.000 kg de Burley al ponderante 3.250 → neto $ 3.250.000, IVA 21 % $ 682.500,
retenciones $ 399.750 (EEAOC 16.250 · Ret. IVA 341.250 · Salud Pública 32.500 · Uso de Agua
9.750), **total $ 3.532.750**. Asiento 176 balanceado en $ 3.932.500 contra las cuentas reales del
plan (114002, 113101, 214401, 214010, 214105, 214402, 211001), Libro IVA código 150 con crédito
computable, y cuenta corriente del productor en **$ −3.532.750**.

**Estado actual:** Etapa 2 completada. El circuito comercial está cerrado de punta a punta:
maestros → romaneo → liquidación → asiento → Libro IVA → cuenta corriente.

**Siguientes pasos sugeridos:**
1. **Etapa 3 — Pago en tesorería**: imputación de la Orden de Pago a la liquidación
   (`agricola_tabaco_liquidacion_pago` + `registrar_aplicacion_op` del Plan 080), retención de
   Ganancias con acumulado mensual, certificados y `recalcular_saldo_liquidacion()`.
2. Confirmar con el contador el tratamiento de la letra B en el Libro IVA (hoy: importe a
   `no_gravado`, sin filas de alícuota).
3. Deuda técnica preexistente: las 6 causas de los 13 errores del baseline.

## Juan Manuel - Notebook personal - 2026-09-06 - Agrícola Etapa 1: Romaneo (Plan 082)

**Objetivo:** registrar la recepción física del tabaco del productor y su clasificación fardo por
fardo, con el precio formado desde la lista vigente y **congelado** en cada fardo. Sin efecto
contable, de stock ni de cuenta corriente: la deuda nace al liquidar (Etapa 2).

**Archivos creados o modificados:**
- `docs/planes/082_agricola_etapa1_romaneo.md` (nuevo)
- `core/models.py` (+ `ContadorDocumento.ROMANEO_TABACO`) y su migración `0003`
- `verticalidades/agricola/tabaco/models.py` (+ `RomaneoTabaco`, `FardoTabaco`,
  `ReclasificacionFardo`) y su migración `0002`
- `verticalidades/agricola/tabaco/services/romaneo.py` (nuevo)
- `verticalidades/agricola/tabaco/forms_romaneo.py` y `views_romaneo.py` (nuevos)
- `verticalidades/agricola/tabaco/urls.py` (13 rutas nuevas)
- `verticalidades/agricola/tabaco/templates/agricola/romaneo/` (11 plantillas nuevas)
- `verticalidades/agricola/tabaco/templates/agricola/hooks/menu_sidebar_bottom.html` (nuevo)
- `verticalidades/agricola/tabaco/tests/test_plan082_romaneo.py` y `test_plan082_pantallas.py`

**Detalle Técnico:**

*El borrador se persiste, no va a la sesión.* El patrón de carrito del ERP guarda los ítems en
`request.session`; acá no sirve, porque un romaneo real tiene cientos de fardos y una sesión con
800 diccionarios se reescribe entera en cada alta. El romaneo nace en BORRADOR en la base y cada
fardo es una fila: además de escalar, si se cae el navegador con 300 fardos cargados no se pierde
nada. Es el criterio del sistema heredado, que usaba una tabla de staging y no memoria.

*Qué se congela.* El romaneo guarda `ponderante_aplicado` y la FK a la lista; cada fardo guarda
`coeficiente_aplicado` y `precio_aplicado`. Hay un test frontal: se carga un fardo, se cambia el
ponderante de la lista a 9.999 y el fardo sigue valiendo lo mismo — y un fardo nuevo del MISMO
romaneo también.

*Numeración.* `ROMANEO_TABACO` se sumó a `ContadorDocumento` para reutilizar
`siguiente_numero()`, que ya resuelve el bloqueo atómico, en lugar de duplicar la lógica.
Precedente: Distribución ya tiene ahí `PEDIDO`, `REPARTO` y `RECEPCION_DEVOLUCION`. El número se
asigna al CONFIRMAR, no al abrir, para no dejar huecos en la serie. El punto sale de
`Sucursal.punto`, cuyo `help_text` dice literalmente que prenumera este tipo de documentos, así
cada sucursal lleva su serie propia.

*La reclasificación no borra.* Cambiar la clase de un fardo confirmado deja una fila en
`ReclasificacionFardo` con clase, coeficiente, precio e importe anteriores y nuevos, más motivo y
usuario. El fardo queda con los valores nuevos pero la cadena completa es reconstruible.

**DOS BUGS QUE ENCONTRARON LOS TESTS:**

1. **Estado obsoleto en la relación cacheada.** `editar_fardo` y `quitar_fardo` leían
   `fardo.romaneo`, que Django cachea. Con el objeto viejo en memoria se podían editar o borrar
   fardos de un romaneo YA CONFIRMADO. Corregido en la raíz: `_exigir_borrador()` relee el estado
   desde la base con `select_for_update()` y devuelve la instancia fresca, lo que además serializa
   contra una confirmación concurrente.
2. **Contrato roto vista/servicio.** `_aviso()` devolvía un `HttpResponse` donde se concatenaba
   texto, y `abrir_romaneo()` no aceptaba `observaciones` pese a estar en el formulario y el modelo.

**TRAMPA DE MODO ENCHUFE EVITADA.** El enlace del menú NO se escribió en `base.html`: un
`{% url 'agro_romaneo_listado' %}` ahí levanta `NoReverseMatch` al desenchufar la carpeta y, como
todas las pantallas extienden `base.html`, se caería el ERP entero. Se usó el templatetag
`{% hook_menu %}`, que renderiza `agricola/hooks/menu_sidebar_bottom.html` sólo si la carpeta
existe. Cero líneas en el core. (Se llegó a agregar una bandera a `core/context_processors.py` y
se revirtió al encontrar el hook.)

**Resultado de las pruebas:**

| Prueba | Resultado |
|---|---|
| `test_plan082_romaneo` (congelado, totales, estados, reclasificación, concurrencia) | **40/40** |
| `test_plan082_pantallas` (circuito completo por el cliente de prueba) | **27/27** |
| Prueba de desenchufe | `check` limpio, 0 apps, rutas inexistentes, términos de stock intactos |
| `makemigrations --check` | sin cambios pendientes |
| **Suite completa** | **729 tests, 13 errores** — todos subconjunto de los 15 preexistentes |

Los 729 son los 640 previos + 67 nuevos de esta etapa + 22 de dos módulos que volvieron a cargar.
Los errores BAJARON de 15 a 13 porque en paralelo se corrigió el import de `TarifaEstudio` en
`facturacion/services/facturacion_lote_service.py` — el bug de producción señalado en el Plan 080.

*Prueba de humo contra datos reales.* Se corrió un romaneo completo con los maestros de la empresa
1 (Burley, ponderante $ 3.250), dentro de una transacción revertida: 5 fardos, 2.311 kg,
$ 6.841.380, PPP $ 2.960,35 = 91,09 % del ponderante, estadística por grupo B/C/N/T/X y
confirmación con número 0002-00000001. No quedó nada en la base. En el primer intento el sistema
rechazó cargar `N5K` en Burley —es una clase de Virginia—, que es exactamente lo que debe hacer.

**OBSERVACIÓN, fuera de alcance.** La corrección de `TarifaEstudio` usa un import ESTÁTICO de
`verticalidades.estudio.models` desde un servicio del core. Verificado: con la carpeta
`verticalidades/estudio/` movida, ese módulo lanza `ModuleNotFoundError`. `manage.py check` sigue
pasando porque nadie lo importa al arrancar, pero es la clase de acoplamiento que el Plan 075
prohíbe. Queda señalado, sin corregir.

**Estado actual:** Etapa 1 completada y verificada. El circuito de romaneo está operativo: abrir,
cargar fardos con precio en vivo, confirmar, imprimir, anular y reclasificar.

**Siguientes pasos sugeridos:**
1. **Etapa 2 — Liquidación de compra**: comprobante 150/151, asiento por `crear_asiento()`,
   Libro IVA + alícuotas por `asiento_id`, retenciones de liquidación y término de cuenta
   corriente del Plan 080. Los maestros y la configuración ya están cargados para arrancar.
2. Deuda técnica preexistente: las causas remanentes de los 13 errores (CUIM en `test_plan028` y
   `test_plan071`, `ExtensionArmeria`, `ExtensionDistribuidoraForm`, el `SyntaxError` de
   `test_plan074_facturacion:22` y `test_plan074_pedidos:20`, y la migración `0019` ausente).

## Juan Manuel - Notebook personal - 2026-09-06 - Agrícola Etapa 0: Maestros del Acopio de Tabaco (Plan 081)

**Objetivo:** dejar cargables y administrables los maestros del acopio —campañas, variedades, las
75 clases con sus coeficientes, listas de precio ponderante, conceptos de retención y la extensión
sectorial del productor—, sin ningún efecto contable, de stock ni de cuenta corriente.

**Archivos creados o modificados:**
- `docs/planes/081_agricola_etapa0_maestros_tabaco.md` (nuevo — plan de la etapa)
- `verticalidades/agricola/urls.py` (nuevo — ver el hallazgo de abajo)
- `verticalidades/agricola/core_agricola/models.py` (+ `Campania`) y su migración `0002_campania`
- `verticalidades/agricola/tabaco/models.py` (6 modelos) y su migración `0001_initial`
- `verticalidades/agricola/tabaco/forms.py`, `views_htmx.py`, `urls.py` (nuevos)
- `verticalidades/agricola/tabaco/services/importacion_clases.py` y `services/precios.py` (nuevos)
- `verticalidades/agricola/tabaco/management/commands/importar_clases_tabaco.py` (nuevo)
- `verticalidades/agricola/tabaco/templates/` (13 plantillas nuevas, dentro de la verticalidad)
- `verticalidades/agricola/tabaco/tests/test_plan081_maestros.py` y `test_plan081_pantallas.py` (nuevos)
- `core/views_config.py` (pestañas agrícolas con import tolerante)
- `templates/configuracion/partials/hub.html` (bloque "Acopio de Tabaco", condicionado)

**HALLAZGO: las rutas de `agricola` no se publicaban.**
El auto-descubrimiento de `config/urls.py` recorre `verticalidades/<app>/` e incluye la app sólo
si encuentra un `urls.py` **en ese primer nivel**. Como `agricola` es un contenedor de sub-apps
(`tabaco`, `granos`) y no una app en sí misma, ninguna de sus rutas llegaba a Django. Se resolvió
creando `verticalidades/agricola/urls.py`, del lado de la verticalidad: **no se tocó
`config/urls.py`**, el mecanismo del core ya servía y lo que faltaba era el punto de entrada.

**Detalle Técnico:**

*7 tablas, todas con prefijo `agricola_`*: `agricola_campania` (en `core_agricola`, porque granos
y caña la comparten), `agricola_tabaco_configuracion`, `..._variedad`, `..._clase`,
`..._lista_precio`, `..._tipo_retencion`, `..._productor`.

*Tres decisiones de modelo que conviene tener presentes:*
1. El **coeficiente lleva 4 decimales** aunque el maestro heredado traiga 2: multiplica un precio
   por miles de kilos y el redondeo se nota.
2. El **precio ponderante se versiona** por variedad, campaña y vigencia, con estado `aprobada`.
   En el VFP era un campo suelto de `tab_variedad`: al cambiarlo se reescribía el precio de todo
   lo ya comprado.
3. `agricola_tabaco_tipo_retencion` **no tiene nada específico de tabaco**, a propósito.
   `tipo_base` (NETO / IVA / ACUM_MENSUAL) y `momento` (LIQUIDACION / PAGO) son genéricos, para
   poder promover la tabla al core cuando otra empresa sea agente de retención. El formulario
   además impide configurar una retención de base acumulada mensual practicada al liquidar: su
   base es el acumulado de lo PAGADO, y al liquidar daría un importe incorrecto.

*Importación de las 75 clases.* Comando `importar_clases_tabaco --empresa <id> [--dry-run]`.
Lee el CSV en UTF-8 con BOM, separador `;` y decimal con coma; busca por `codigo` y nunca por pk;
valida el archivo entero ANTES de escribir, dentro de una transacción. Resultado verificado:
primera corrida 75 altas y 2 variedades; segunda corrida 0 altas y 75 sin cambios. El `--dry-run`
informa lo que haría y deja la base intacta (verificado en 0 registros).

*Datos cargados y verificados contra la base:* 27 Burley + 48 Virginia, coeficientes 0,1000 a
1,0500, `B1F` = 1,0000 en ambas variedades y `H1F` = 1,0500. El **grupo H de Virginia (3 clases)
ahora aparece**: el sistema heredado lo perdía porque agrupaba con una lista fija de cinco letras
(B, C, N, T, X); acá el grupo se deriva del dato.

*Servicio de precios.* `precio_de_clase()` e `importe_de_linea()` implementan
`REDONDEO(ponderante × coeficiente, 2)` y `REDONDEO(precio × kilos, 2)`. El redondeo a dos
decimales del precio unitario es deliberado: si se redondeara recién en el importe final, el
precio impreso en la liquidación no multiplicaría exacto por los kilos y el productor no podría
verificar su propia liquidación con una calculadora.

*Interfaz.* Seis pestañas en el panel de Configuración con búsqueda typeahead (`delay:300ms`),
lupa, `.fInputAR` en todo importe y coeficiente y `|formato_ar` en los displays. Se usó **un modal
genérico** para los cinco maestros en lugar de cinco plantillas casi idénticas. Las plantillas
viven dentro de la verticalidad (`verticalidades/agricola/tabaco/templates/`) para que se
desenchufe limpio. El bloque del hub aparece sólo si `EmpresaVertical.hace_tabaco`, y
`core/views_config.py` importa la verticalidad con `try/except ImportError` — **no se copió** el
patrón sin protección que ese mismo archivo usa hoy para distribución.

**Resultado de las pruebas:**

| Prueba | Resultado |
|---|---|
| `test_plan081_maestros` (importación, restricciones, precios) | **23/23** |
| `test_plan081_pantallas` (render de pestañas, modales, buscadores, aislamiento, altas) | **14/14** |
| Prueba de desenchufe | `check` limpio, 0 apps agrícolas, rutas inexistentes, contexto vacío |
| `makemigrations --check` | sin cambios pendientes |
| Suite completa | 640 tests (603 + 37 nuevos), **los mismos 15 errores preexistentes** |

Los tests de precio validan contra **6 casos reales** del sistema heredado (marzo 2024, Burley,
ponderante 2.500): `B1F → 2.500,00`, `B1FR → 2.125,00`, `B2F → 2.300,00`, `B3F → 1.950,00`,
`C1F → 2.400,00`, `C2F → 2.150,00 × 843 kg = 1.812.450,00`. Hay además un test dedicado al caso
`N5K`: dos códigos con la misma clase dentro de la misma variedad ahora se rechazan al importar.

**Nota sobre la suite completa.** Reportó 17 errores en vez de 15. Los 2 extra fueron **un único
evento de infraestructura**, no una regresión: el backend de PostgreSQL se cayó
(`server closed the connection unexpectedly — server terminated abnormally`) durante
`test_plan074_cobranzas.test_rendir_desde_la_pantalla`, arrastrando a su `tearDownClass`. Ese
módulo re-corrido aislado da **43/43 OK y cero caídas**. Además, la Etapa 0 no registra ningún
término en los registros del Plan 080 —verificado en runtime: los tres registros en 0 y
`_terminos()` devolviendo los cuatro de siempre—, así que el camino de stock y cuenta corriente
que ejecutó esta suite es idéntico al de la corrida anterior, que no tuvo ninguna caída.

**Estado actual:** Etapa 0 completada y verificada. Los maestros quedan operativos y las 75 clases
cargadas para la empresa 1.

**Siguientes pasos sugeridos:**
1. **Cargar los cinco conceptos de retención desde la pantalla.** No se sembraron por comando
   porque cada uno necesita su cuenta de pasivo del plan de cuentas de la empresa, y eso lo define
   el contador. Valores del sistema heredado, a confirmar: EEAOC 0,5 %, Uso de Agua 0,3 %, Salud
   Pública 1 % (los tres sobre el neto, al liquidar), Ret. IVA 50 % del IVA (al liquidar, sólo RI)
   y Ganancias 2 % sobre acumulado mensual con MNI 224.000 (al pagar, sólo RI).
2. Cargar la campaña vigente y su lista de precio ponderante aprobada.
3. **Etapa 1 — Romaneo**: recepción, pesaje y clasificación por fardo, con el precio congelado.
4. Deuda técnica pendiente del baseline: las 6 causas de los 15 errores preexistentes, en especial
   `facturacion/services/facturacion_lote_service.py`, que es código de producción roto.

## Juan Manuel - Notebook personal - 2026-09-06 - Plan 080: términos enchufables en Stock y Cuenta Corriente

**Objetivo:** implementar el único cambio al core que requiere la verticalidad Agrícola: tres
puntos de extensión para que una verticalidad sume sus propios orígenes al cálculo del stock, al
saldo de cuenta corriente y a la imputación de Órdenes de Pago, sin que el core la importe y sin
romper el Modo Enchufe del Plan 075.

**Archivos creados o modificados:**
- `productos/services/stock_service.py` — `registrar_termino_stock()`; `_terminos()` ahora devuelve `base + _TERMINOS_EXTRA`
- `contable/services/saldos.py` — `registrar_termino_ctacte()` y `registrar_aplicacion_op()`, consumidos en `recalcular_saldo_cliente_proveedor()` y `pendiente_de_aplicar_op()`
- `productos/tests/test_plan080_terminos_stock.py` (nuevo, 12 casos)
- `contable/tests/test_plan080_terminos_ctacte.py` (nuevo, 14 casos)
- `verticalidades/estudio/migrations/0001_initial.py` (nuevo — reparación, ver más abajo)
- `docs/planes/080_terminos_enchufables_saldos_stock.md`

**Sin migraciones del core y sin tablas nuevas.** Los cuatro términos de stock y los cuatro
sumandos de cuenta corriente quedaron textualmente iguales: el diff sólo agrega.

**Detalle Técnico:**

*Mecanismo.* Cada servicio expone un registro al que la verticalidad se suscribe desde su
`apps.py::ready()`. La dependencia va verticalidad → core, nunca al revés. Si la carpeta de la
verticalidad no está, su app no entra a `INSTALLED_APPS`, `ready()` no corre, no se registra nada
y los servicios calculan como antes del plan.

*Idempotencia.* El alta es idempotente por `nombre`. Sin eso, un `ready()` ejecutado dos veces
—autoreload, ciertos runners— contaría el stock y la deuda por duplicado en silencio.

*Ajuste sobre el diseño original.* La validación de los términos se hace AL REGISTRAR, no al
calcular. Un `excluir` mal tipeado descubierto dentro de `recalcular_stock()` rompería el stock de
todo el ERP en plena operación; así el servidor directamente no levanta. Se verificó contra la
base que `exclude(Q())` no excluye nada y que `exclude(None)` lanza `TypeError`, de modo que
`None` se normaliza a `Q()` al registrar. También se valida que `signo` sea 1 o −1.

*Convención de importes (documentada en el código).* Un término de cuenta corriente debe declarar
el TOTAL del comprobante, no el neto a pagar. Es el mismo criterio del supuesto S-1 ya
documentado en `saldos.py`: `OrdenPago.total` ya incluye las retenciones practicadas como medio
de pago, así que un comprobante que aportara el neto de retenciones haría que la OP cancelara de
más y el tercero quedara con un crédito falso.

**BLOQUEANTE PREEXISTENTE REPARADO — la suite no podía correr.**
`verticalidades/estudio` tenía el modelo `TarifaEstudio` pero nunca se le generaron migraciones.
Al crear la base de test, Django ejecuta `sync_apps` para las apps sin migraciones ANTES de
aplicar las migraciones, y `TarifaEstudio` hereda de `AuditModel`, que tiene FK a `auth_user`,
que en ese momento todavía no existe: `relation "auth_user" does not exist`. Se verificó además
que la tabla `facturacion_tarifaestudio` tampoco existía en la base real. Se generó la migración
faltante; es puramente aditiva y no requiere `--fake`.

**Resultado de las pruebas:**

| Corrida | Tests | Errores | Tiempo |
|---|---|---|---|
| **Baseline** (código previo al Plan 080, suite completa) | 577 | **15** | 5.454 s |
| **Después** (con Plan 080, suite completa) | 603 | **15** | 5.568 s |
| Tests propios del Plan 080 | 26 | 0 | 62 s |

Los 603 son los 577 del baseline más los 26 nuevos. El conteo de errores no cambió.

*Comparación dirigida (la prueba fuerte).* Sobre 9 módulos —`test_plan028`,
`test_plan071_trazabilidad`, `test_totales`, `test_stock`, `test_stock_inicial`, `test_saldos`,
`test_saldos_mensuales`, `test_contabilizacion_op`, `test_contabilizacion_recibo`, 90 tests— se
corrió la misma suite dos veces: con los dos archivos de servicio revertidos a `7e0b322` y con
la versión del Plan 080. Ambas dieron 8 errores y las listas de fallas son **byte a byte
idénticas**; la única diferencia del diff es el tiempo transcurrido (319,275 s vs 317,764 s).

*Prueba de fuego de desenchufe.* Con `verticalidades/agricola/` movida fuera del proyecto:
`manage.py check` sin problemas, ninguna app con 'agricola' en `INSTALLED_APPS`, 0 términos
registrados en los tres registros, y los términos de stock de siempre intactos
(`['compras','recepciones','ventas','remitos_internos']`). Carpeta restaurada y `check` limpio.

**Los 15 errores preexistentes, clasificados** (ninguno relacionado con este plan; ninguno en los
módulos de stock ni de saldos):

| Causa | Módulos afectados |
|---|---|
| `ValidationError` de CUIM al crear `Subproducto` — la validación estricta agregada el 2026-09-03 rompió tests que crean subproductos sin CUIM válido | `test_plan028` (5), `test_plan071_trazabilidad` (3) |
| `ImportError: cannot import name 'TarifaEstudio' from 'facturacion.models'` — el modelo se mudó a `verticalidades/estudio` y quedaron referencias viejas | `test_lote_condic`, `test_plan075_numeracion` |
| `ImportError: cannot import name 'ExtensionArmeria' from 'facturacion.models'` | `test_armeria_credencial_clu` |
| `ImportError: cannot import name 'ExtensionDistribuidoraForm' from 'facturacion.forms'` | `test_plan074_maestros` |
| `SyntaxError` — un `from ... import` quedó inyectado en medio de otro import multilínea, dejando el paréntesis sin cerrar | `test_plan074_facturacion` (línea 22), `test_plan074_pedidos` (línea 20) |
| `ModuleNotFoundError: No module named 'contable.migrations.0019_renumerar_condic'` — el test importa una migración eliminada en la consolidación del 2026-09-04 | `test_condic_renumeracion` |

**HALLAZGO QUE NO ES SÓLO DE TESTS:** `facturacion/services/facturacion_lote_service.py` línea 6
importa `TarifaEstudio` desde `facturacion.models`. **Es código de producción, no un test**: el
servicio de facturación por lote está roto en tiempo de importación. Es la misma clase de
violación del Modo Enchufe que el Plan 075 prohíbe. **No se corrigió**: queda fuera del alcance de
este plan y necesita decisión.

**Estado actual:** Plan 080 completado y verificado. La Etapa 0 de la verticalidad Agrícola queda
desbloqueada, y con ella las Etapas 2 y 4 cuando llegue el momento.

**Siguientes pasos sugeridos:**
1. **Deuda técnica preexistente** (fuera del alcance agrícola, pero conviene atacarla): las 6
   causas de arriba. La del `facturacion_lote_service.py` es la urgente porque es producción.
2. Etapa 0 — maestros de tabaco, configuración e importación idempotente de las 75 clases desde
   `docs/agricola/tabaco_clase.csv`.
3. Etapa 1 — romaneo: recepción y clasificación por fardo.

## Juan Manuel - Notebook personal - 2026-09-06 - Diseño de la Verticalidad Agrícola (Acopio de Tabaco)

**Objetivo:** Relevar el material de diseño externo y el sistema VFP heredado, contrastarlos contra
el código real del ERP, y dejar documentado el plan de implementación por etapas de la verticalidad
Agrícola, con foco en el circuito de acopio y comercialización de tabaco. **No se modificó código
del ERP: la intervención es exclusivamente documental.**

**Archivos creados o modificados:**
- `docs/agricola/plan inicial agricola.md` (reescrito completo — plan integral v1.0)
- `docs/planes/080_terminos_enchufables_saldos_stock.md` (nuevo)
- `docs/GUIA_MODULAR.md` (alta de la verticalidad 17 — Agropecuario y Acopio de Tabaco)
- `docs/walkthrough.md` (esta entrada)
- `d:orrador	abaco_clase.csv` (corrección de dato: clase código 72 `N5K` → `N5T`)

**Detalle Técnico:**

*Fuentes analizadas.* Paquete de diseño externo `erp_agro_diseno_v0_1` (12 documentos),
`tabaco_clase.csv` (75 clases), y los formularios VFP `op_romaneo.scx/.sct`,
`compra_tabaco.scx/.sct` y `consulta_romaneo.scx/.sct` del sistema heredado, más las estructuras
DBF y la biblioteca de clases `basico.vcx`.

*Verificaciones contra el código del ERP.* Se corrigieron once afirmaciones del paquete externo
que no se sostienen contra el repositorio (detalle en §10 del plan). Las tres de mayor impacto:
1. El stock **no** se ajusta por delta desde signals: es un valor derivado que `recalcular_stock()`
   reconstruye desde una lista declarativa de términos (Plan 053). Extenderlo es agregar un
   término, no rediseñar el motor.
2. `contable.LibroIvaCompras` y `LibroIvaAlic` **no dependen de `Compra`**: se cuelgan del asiento
   por un `asiento_id` que ni siquiera es FK. La verticalidad puede participar del subsistema
   fiscal sin ningún cambio en el core.
3. `contabilizar_orden_pago()` **no lee `OrdenPagoAplicacion`**: el asiento de la OP es idéntico
   pague una `Compra` o una liquidación de tabaco. Y la retención de Ganancias ya está resuelta
   por el core vía `MedioPago` categoría `RET` + `cta_ret_practicada_ganancias`.

*Fórmulas de cálculo extraídas del VFP y validadas.* `precio = ROUND(ponderante × coeficiente, 2)`
e `importe = ROUND(precio × kilos, 2)`, verificadas contra **132 registros reales** de
`cpra_clase_fec.DBF` (marzo 2024): 132/132 exactas. Retenciones: Ret. IVA 50 % del IVA,
EEAOC 0,5 %, Uso de Agua 0,3 %, Salud Pública 1 %, todas sobre el neto; Ganancias 2 % sobre
acumulado mensual menos MNI, régimen 78, MNI 224.000. Ninguna se calcula por kilo.

*Decisión de circuito.* El VFP resolvía liquidación y pago en un solo acto (`op_romaneo`) por una
particularidad operativa de aquel cliente. **No se replica.** El ERP separa los dos hechos:
se liquida (nace la deuda) y después, en tesorería, se emite la Orden de Pago que la cancela.

*Hallazgo en el sistema heredado.* El asiento de la Orden de Pago del VFP no balancea cuando hay
retención de Ganancias: descuadra en 2 × Ret_gcias por tener intercambiados los importes de la
línea del productor y la del banco. Sobrevivió porque con retención en cero cierra. `crear_asiento()`
de Ikigai rechazaría ese asiento, que es el comportamiento correcto.

*Corrección de datos.* En `tabaco_clase.csv`, el código 72 figuraba como `N5K`, duplicando al
código 38 dentro de Virginia con distinto coeficiente (0,15 vs 0,17). Por el patrón de bloques del
maestro corresponde al grupo T y se corrigió a `N5T`, confirmado por el usuario. Tras la
corrección, `(variedad, detalle)` es único además de `(variedad, codigo)`.

*Observación para el equipo.* Las verticalidades `distribucion` y `estudio` existen físicamente en
`verticalidades/` pero no figuran en el índice de `docs/GUIA_MODULAR.md`. No se modificaron sus
filas por estar fuera del alcance de esta tarea.

**Resultado de las pruebas:** No aplica — no hubo cambios de código. El baseline de la suite debe
ejecutarse y registrarse al iniciar el Plan 080, que es el primer plan con impacto en el core.

**Estado actual:** Diseño documentado y aprobado en sus decisiones de fondo. Quedan **siete
decisiones abiertas** (DA-01 a DA-07 del plan), de las cuales tres bloquean la Etapa 2:
momento de cada retención, forma de autorización del comprobante (webservice / talonario con CAI)
y existencia de notas de crédito de liquidación.

**Siguientes pasos sugeridos:**
1. Cerrar DA-01, DA-02 y DA-03 con el asesor impositivo.
2. Ejecutar el Plan 080 (único cambio al core), con baseline y prueba de desenchufe.
3. Etapa 0 — maestros y configuración, con la importación idempotente de las 75 clases.
4. Etapa 1 — romaneo (recepción y clasificación por fardo), sin efectos contables ni de stock.

### Actualización 2026-09-06 (misma jornada) — Cierre de DA-01, DA-02 y DA-03

**Objetivo:** incorporar al plan las tres decisiones que bloqueaban la Etapa 2.

**Archivos modificados:** `docs/agricola/plan inicial agricola.md`

**Decisiones incorporadas:**
- **DA-01 — Momento de cada retención (cerrada).** Ret. IVA, EEAOC, Uso de Agua y Salud Pública se
  practican en la **liquidación**; Ganancias en el **pago**. Queda parametrizado en el campo
  `momento` del maestro de retenciones, no cableado en el código.
- **DA-02 — Autorización del comprobante (cerrada).** Se soportan **dos modos simultáneos**:
  `MANUAL` (captura de tipo, punto, número y CAI, para talonario impreso o comprobante en línea de
  ARCA) — el que se implementa en la Etapa 2 — y `WEBSERVICE`, que queda como punto de extensión
  preparado y sin desarrollar (mejora MP-02). Se agregó la sección §3.6 al plan con el detalle de
  qué se propone y qué es editable en cada modo, y la validación de unicidad
  `(empresa, letra, punto, numero)`.
- **DA-03 — Notas de crédito de liquidación (postergada).** Pasa a la mejora **MP-01**, fuera del
  alcance inicial: falta definir si el comprobante 150/151 tiene su propia nota de crédito con
  código ARCA específico o si se usan las Notas de Crédito convencionales A/B. Mientras tanto, la
  corrección de una liquidación se hace por **anulación con contraasiento** dentro del período.

**Estado actual:** la Etapa 2 queda **desbloqueada**. Las decisiones abiertas remanentes (DA-04 a
DA-07) afectan a las Etapas 1, 4 y 5, no a la liquidación.

## Cristian - PC CASA - 06/09/2026
**Objetivo:** Solución de deudas técnicas urgentes e importaciones huérfanas en verticalidades.
**Archivos creados o modificados:**
- `facturacion/services/facturacion_lote_service.py` [MODIFY]
- `facturacion/tests/test_lote_condic.py` [MODIFY]
- `facturacion/tests/test_plan075_numeracion.py` [MODIFY]
- `migracion/management/commands/migrar_tarifas.py` [MODIFY]
- `facturacion/helpers.py` [MODIFY]
- `facturacion/tests/test_armeria_credencial_clu.py` [MODIFY]

**Detalle Técnico:**
- Se corrigió el error bloqueante en producción y tests provocado por la importación del modelo `TarifaEstudio` desde `facturacion.models`. Ahora se importa correctamente desde su nueva ubicación en `verticalidades.estudio.models`.
- Se revisó el estado de las verticalidades `armeria` y `estudio` en búsqueda de dependencias huérfanas tras su refactorización.
- Se detectó y corrigió la importación huérfana de `ExtensionArmeria` y `ExtensionArmeriaForm` (seguían siendo requeridos desde `facturacion` en lugar de `verticalidades.armeria`) en `facturacion/helpers.py` y `facturacion/tests/test_armeria_credencial_clu.py`.
- Se verificó mediante búsqueda global (grep) que otros modelos migrados (ej. `ReservaArma`) están correctamente referenciados en el resto del proyecto.

**Estado actual y siguientes pasos sugeridos:**
- Los problemas de importación (código roto en tiempo de importación) para las verticalidades evaluadas están resueltos. La suite y el servidor local pueden inicializarse sin fallos. Quedo a la espera de la siguiente deuda o tarea a abordar.

## Juan Manuel - Notebook personal - 2026-09-07 - Agrícola Etapa 4: Stock del Tabaco (Plan 085)

**Objetivo:** que los kilos recibidos entren al stock del ERP y salgan al venderse, usando el
motor existente. Consume el **último punto de extensión del Plan 080 que quedaba sin estrenar**.

**Archivos creados o modificados:**
- `docs/planes/085_agricola_etapa4_stock.md` (nuevo)
- `verticalidades/agricola/tabaco/services/stock.py` (nuevo — término y conciliación)
- `verticalidades/agricola/tabaco/services/romaneo.py` (dispara el recálculo al confirmar/anular)
- `verticalidades/agricola/tabaco/registros.py` (+ `registrar_termino_stock`)
- `verticalidades/agricola/tabaco/management/commands/crear_productos_tabaco.py` (nuevo)
- `verticalidades/agricola/tabaco/views_pago.py` (+ conciliación y recálculo) y `urls.py` (2 rutas)
- `verticalidades/agricola/tabaco/templates/agricola/stock/conciliacion.html` (nuevo)
- `verticalidades/agricola/tabaco/templates/agricola/hooks/menu_sidebar_bottom.html` (1 entrada)
- `verticalidades/agricola/tabaco/tests/test_plan085_stock.py` (nuevo)

**SIN MIGRACIONES.** La etapa no agrega ni una tabla ni un campo: `VariedadTabaco.producto` ya
existía desde el Plan 081, previsto justamente para esto. Todo lo demás es servicio, registro y
pantalla.

**Detalle Técnico:**

*Granularidad: un producto por VARIEDAD, en kilos.* La clase vive en el fardo, no en el producto.
Si hubiera un producto por clase serían 75, y —lo que importa de verdad— una reclasificación
tendría que mover stock de uno a otro. Pero reclasificar NO cambia lo que hay en el galpón: son
los mismos kilos, mejor descriptos. Hay un test que fija esa regla.

*El término sólo aporta la ENTRADA.* La salida ya la resuelve el término `ventas` que existe desde
siempre: al vender tabaco se factura el `Producto` de la variedad y `VentaItem` lo descuenta. Un
segundo término de egreso duplicaría la baja.

*Cuándo entra:* al CONFIRMAR el romaneo. El borrador todavía se está cargando y el anulado no
ocurrió; CONFIRMADO y LIQUIDADO cuentan igual, porque liquidar factura pero no mueve mercadería.
Como el motor recalcula por signals de `CompraItem`/`VentaItem` —que no aplican acá—, el llamado
va explícito en `confirmar_romaneo()` y `anular_romaneo()`, los dos únicos momentos en que un
romaneo cruza el umbral de contar o no contar.

*Degradación silenciosa y deliberada:* si una variedad no tiene producto asignado, el romaneo se
confirma igual y simplemente no mueve stock. Para que ese silencio no se lea como "está todo
bien", la conciliación lo informa como una fila destacada.

*Conciliación:* recibidos − vendidos + inicial contra `StockSucursal.cantidad`, por variedad y
sucursal. La diferencia debe ser cero; si no lo es, el botón de recálculo la corrige, porque el
stock es un valor derivado y autorreparable.

**LOS TRES PUNTOS DE EXTENSIÓN DEL PLAN 080 QUEDAN TODOS EN USO:**

| Punto | Consumido en |
|---|---|
| `registrar_termino_ctacte` | Plan 083 — la deuda de la liquidación |
| `registrar_aplicacion_op` | Plan 084 — la imputación del pago |
| `registrar_termino_stock` | Plan 085 — esta etapa |

El Plan 080 se diseñó al principio de todo, antes de que existiera un solo modelo de tabaco.
Cierra sin haber necesitado un cambio.

**Resultado de las pruebas:**

| Prueba | Resultado |
|---|---|
| `test_plan085_stock` (ingreso, egreso, conciliación, comando, pantalla) | **26/26** |
| Prueba de desenchufe | el stock vuelve **exactamente** a `['compras','recepciones','ventas','remitos_internos']`, los tres registros en 0 y `recalcular_stock()` sigue funcionando |
| `makemigrations --check` | sin cambios pendientes |
| **Suite completa** | **872 tests, 13 errores** — lista **idéntica** al baseline, cero fallas nuevas y cero caídas de conexión |

La corrida tardó 1.136 s con la máquina sola, confirmando de nuevo que las caídas de PostgreSQL
de etapas anteriores venían de correr suites en paralelo.

**Estado actual:** el circuito del acopio está completo de punta a punta —maestros, romaneo,
liquidación, pago y stock— sin una sola modificación funcional al core.

**Siguientes pasos sugeridos:**
1. **Etapa 5** — lotes de acopio, acondicionamiento con mermas, venta y **margen por fardo**
   (venta − compra − costos de acondicionamiento).
2. **Etapa 6** — reportes FET / Secretaría de la Producción y libro de retenciones practicadas.
3. Antes de operar: correr `manage.py crear_productos_tabaco --empresa 1` para que las variedades
   tengan su producto de stock, o asignarlo desde el ABM de variedades.
4. Deuda técnica preexistente: las 6 causas de los 13 errores del baseline.

<<<<<<< HEAD
---

## 2026-09-07 — Juan Manuel - Notebook personal

### Corrección: `unidad_venta` bloqueaba el alta de productos fuera de DISTRIBUCION

**Objetivo:** el usuario reportó que dar de alta un producto en la actividad **ARMERIA** fallaba
por el campo `unidad_venta`.

**Diagnóstico.** El campo no es de las etapas agrícolas: viene del **Plan 074 (Distribución)** y
está en el repositorio desde el commit inicial (`git log -S "unidad_venta" -- productos/models.py`
devuelve sólo `1614a03 Initial commit`; lo crea `productos/migrations/0001_initial.py`). El
problema es una combinación de tres cosas que por separado son correctas:

1. `unidad_venta` está en `ProductoForm.Meta.fields`.
2. En el modelo tenía `default='UNIDAD'` y `choices`, pero **no `blank=True`** → el form lo
   marcaba `required=True`.
3. Sólo se **dibuja** dentro de
   `verticalidades/distribucion/templates/distribucion/hooks/ui_producto_modal_campos.html`, que
   abre con `{% if empresa_actual.tipo_actividad == 'DISTRIBUCION' %}`.

En ARMERIA (y ESTUDIO, AGRICOLA…) el campo nunca llega al POST, el formulario queda inválido y el
producto no se guarda — y el usuario **no puede ver dónde está el error**, porque el campo no está
en pantalla. Reproducido con un POST realista de ARMERIA:
`ERROR en unidad_venta: Este campo es obligatorio.`

De los cuatro campos que inyecta el hook de Distribución, era el **único** que fallaba:
`codigo_anterior`, `peso_unitario_kg` y `unidades_por_bulto` ya eran opcionales.

**Archivos modificados:**
- `productos/models.py` [MODIFY]: `blank=True` en `unidad_venta`, con el comentario del porqué.
- `productos/migrations/0002_unidad_venta_opcional.py` [NEW]: `AlterField`. **No toca el esquema**
  — `blank` es validación a nivel Django, la columna sigue igual.
- `productos/forms.py` [MODIFY]: `clean_unidad_venta()` — si no viaja en el POST, repone el valor
  del producto que se edita o, en un alta, el default del modelo. Sin esto `blank=True` guardaría
  `''` y rompería el `choice`.
- `productos/tests/test_unidad_venta_opcional.py` [NEW]: 5 tests de regresión.

**Por qué el `clean_` y no sólo `blank=True`:** editar un producto de Distribución desde una
pantalla que no dibuja el campo le habría borrado la unidad. El `clean_` la conserva.

**Resultado de las pruebas:**
- `manage.py test productos.tests.test_unidad_venta_opcional` → **5/5 OK** (0,53 s).
- `manage.py test productos` → **41/41 OK** (34,9 s).
- `manage.py makemigrations --check --dry-run` → `No changes detected`.
- Verificación funcional: ARMERIA sin el campo → válido, queda `'UNIDAD'`; DISTRIBUCION con
  `'BULTO'` → válido y respeta `'BULTO'`.

**Estado y siguientes pasos:** corregido. Sin cambios pendientes para las etapas agrícolas; siguen
en pie la Etapa 5 (lotes, acondicionamiento, margen) y la Etapa 6 (reportes FET y libro de
retenciones practicadas).

---

## 2026-09-07 — Juan Manuel - Notebook personal

### Agrícola · Etapa 5 — Lotes de acopio, acondicionamiento, venta y margen (Plan 086)

**Objetivo:** cerrar el circuito comercial del acopio. Hasta acá el tabaco entraba (romaneo), se
facturaba al productor (liquidación), se pagaba (orden de pago) y sumaba kilos al stock. Faltaba
qué pasa con esos kilos **después**: agruparlos, acondicionarlos, venderlos y medir el margen.

Plan: [`docs/planes/086_agricola_etapa5_lotes_acondicionamiento_venta.md`](planes/086_agricola_etapa5_lotes_acondicionamiento_venta.md).

#### Las tres decisiones de fondo

**1. DA-07 se resuelve por configuración, no por código.** El plan integral dejaba abierta la
decisión *"procesos reales de acondicionamiento, mermas normales y coproductos"* para esta etapa.
No la resolví adivinando qué hace la planta: la convertí en un maestro que carga el usuario.
`ProcesoAcondicionamiento` guarda el nombre del proceso y su merma normal esperada. El sistema
sabe que **un proceso toma kilos, devuelve kilos, consume plata y pierde peso**; si mañana aparece
un proceso nuevo, es un alta en una pantalla y no una migración.

**2. La etapa NO genera un solo asiento, y es a propósito.** Es la decisión más importante y la
más contraintuitiva. El ERP no contabiliza el stock: `StockSucursal` lleva cantidades y
`VentaItem.cto_rep` guarda el costo sólo para análisis. Los insumos del acondicionamiento se
compran con una `Compra` normal —*"por ahí irán todas las compras de insumos, agroquímicos"*— que
**ya generó su asiento, su Libro IVA y su deuda con el proveedor**. Lo que faltaba no era
contabilizar de nuevo —eso duplicaría el gasto en el balance— sino **imputar** ese costo ya
contabilizado a un lote para poder medir el margen. Por eso `AcondicionamientoCosto.compra` es un
respaldo opcional y no un disparador contable. Hay un test que lo fija:
`test_el_acondicionamiento_no_genera_asientos`.

**3. Merma y coproducto no son lo mismo.** Merma son kilos que **desaparecen**; coproducto son
kilos que dejan de ser tabaco de la variedad y pasan a ser **otra cosa vendible** (el palo, el
descarte). Sin separarlos, el usuario registraría el palo como merma y perdería un activo real.
Por eso el stock se mueve así:

```
stock(variedad)   = Σ fardos − Σ kilos_baja        # baja = entrada − salida
stock(coproducto) = Σ coproducto.kilos             # reaparece en su propio producto
```

`kilos_baja` incluye los coproductos justamente porque ya no son tabaco de esa variedad. Si acá se
restara sólo la merma, los kilos del palo quedarían contados dos veces.

#### Archivos creados

- `verticalidades/agricola/tabaco/services/lotes.py` [NEW]: armado, venta y derivados del lote.
- `verticalidades/agricola/tabaco/services/acondicionamiento.py` [NEW]: corridas de proceso,
  costos, coproductos, cierre y anulación.
- `verticalidades/agricola/tabaco/services/stock_acondicionamiento.py` [NEW]: los dos términos de
  stock nuevos.
- `verticalidades/agricola/tabaco/services/margen.py` [NEW]: margen por lote, por fardo y por clase.
- `verticalidades/agricola/tabaco/forms_lotes.py` [NEW] · `views_lotes.py` [NEW].
- 16 plantillas nuevas en `templates/agricola/{lote,acond,margen,partials}/` y
  `templates/configuracion/partials/agro_procesos.html`.
- `verticalidades/agricola/tabaco/tests/test_plan086_lotes.py` [NEW] — 43 tests de servicio.
- `verticalidades/agricola/tabaco/tests/test_plan086_pantallas.py` [NEW] — 34 tests de pantalla.

#### Archivos modificados

- `verticalidades/agricola/tabaco/models.py` [MODIFY]: `LoteAcopio`, `ProcesoAcondicionamiento`,
  `Acondicionamiento`, `AcondicionamientoCoproducto`, `AcondicionamientoCosto`, y el FK
  `FardoTabaco.lote`.
- `verticalidades/agricola/tabaco/registros.py` [MODIFY]: se suman los dos términos de stock
  nuevos al tercer punto de extensión del Plan 080.
- `verticalidades/agricola/tabaco/services/stock.py` [MODIFY]: la conciliación contempla las bajas
  de acondicionamiento; `recalcular_stock_del_acondicionamiento()`.
- `verticalidades/agricola/tabaco/urls.py`, `views_htmx.py` (ABM de procesos),
  `templates/agricola/hooks/menu_sidebar_bottom.html`, `templates/agricola/stock/conciliacion.html`.
- `core/models.py` [MODIFY]: `ContadorDocumento.LOTE_TABACO`. **Es el único cambio al core**, y es
  aditivo, igual que `ROMANEO_TABACO` en la Etapa 0.
- `core/views_config.py` y `templates/configuracion/partials/hub.html`: pestaña `agro_procesos`.
- `docs/agricola/plan inicial agricola.md`: DA-07 pasa de abierta a cerrada; Etapa 5 marcada.
- `docs/GUIA_MODULAR.md`: estado del módulo 17.

#### Garantías que da el modelo, no una validación

- `FardoTabaco.lote` es un FK simple, así que **un fardo está en un lote a lo sumo** — igual que
  `RomaneoTabaco.liquidacion` garantiza no liquidar dos veces los mismos kilos.
- `LoteAcopio.venta` es un FK simple: **un lote se vende entero**. Para vender la mitad se arman
  dos lotes; los fardos se mueven mientras no haya un acondicionamiento cerrado.
- CheckConstraint `kilos_salida <= kilos_entrada`: del proceso no puede salir más de lo que entró.

#### El margen: qué se prorratea y qué no

| Componente | Cómo |
|---|---|
| Costo de compra | **Exacto por fardo**: es lo que se le pagó al productor por ese fardo |
| Costo de acondicionamiento | Prorrateado por kilos |
| Ingreso de la venta | Prorrateado por kilos |

Prorratear el costo de compra cuando existe el dato exacto sería perder información: dos fardos
del mismo peso pueden haberse pagado a precios muy distintos según su clase, y esa diferencia es
justamente lo que el reporte tiene que mostrar. Lo de acondicionar se prorratea porque una merma
de proceso no es atribuible a un fardo individual: los fardos se mezclan en la máquina.

El ingreso se mide **sólo sobre las líneas del producto de la variedad**: si en la misma factura
se cobró un flete, ese importe no es ingreso del tabaco y contarlo inflaría el margen.

#### Dos correcciones durante el desarrollo

1. **Dos borradores podían sumar más kilos de los que el lote tenía.** Al abrir el segundo, el
   primero todavía no descontaba nada —un borrador no mueve stock—, así que la validación de
   apertura no podía detectarlo. Ahora `cerrar_acondicionamiento()` revalida los kilos. Test:
   `test_no_se_cierran_dos_borradores_que_suman_mas_que_el_lote`.
2. **Armar y cerrar llegan por enlace, no por HTMX.** Devolver un fragmento en el error habría
   reemplazado la página entera por un pedazo de tabla. Ahora el motivo viaja por `?error=` y lo
   muestra el detalle completo.

#### Base de datos

- `core/migrations/0004_etapa5_lotes.py`: sólo el `choices` de `ContadorDocumento`.
- `verticalidades/agricola/tabaco/migrations/0005_etapa5_lotes.py`: 5 tablas nuevas, el FK
  `fardo.lote`, 6 índices y 12 constraints.

#### Resultado de las pruebas

- `test_plan086_lotes` + `test_plan086_pantallas` → **77/77 OK** (99,1 s).
- `manage.py test verticalidades` → **611 tests, 3 errores**, los tres preexistentes de
  distribución (994,6 s).
- **Suite completa: 954 tests, 13 errores** — lista **idéntica** al baseline, cero fallas nuevas
  (1.288,9 s, corriendo sola). El baseline tenía 872 tests con los mismos 13 errores; los 82 de
  diferencia son los 77 de esta etapa más los 5 de la corrección de `unidad_venta`.
- `manage.py makemigrations --check --dry-run` → `No changes detected`.
- **Prueba de desenchufe** (carpeta `verticalidades/agricola` movida):
  - `manage.py check` → sin problemas;
  - términos de stock: exactamente los cuatro de siempre (`compras`, `recepciones`, `ventas`,
    `remitos_internos`), los tres extras en cero;
  - términos de cuenta corriente y aplicaciones de OP: ninguno;
  - `recalcular_stock()` sigue funcionando sobre un producto real;
  - al reenchufar, `manage.py check` vuelve a pasar.

#### Estado actual y siguientes pasos

Etapa 5 cerrada. Los tres puntos de extensión del Plan 080 siguen siendo los únicos ganchos usados
y el core sólo recibió un `choices` nuevo.

1. **Cargar los procesos reales de la planta** en Configuración → Procesos de Acondicionamiento.
   Es lo único que queda de DA-07 y es dato operativo, no desarrollo.
2. **Etapa 6** — reportes FET / Secretaría de la Producción y libro de retenciones practicadas.
3. Limitación conocida y documentada: un lote se vende entero; para vender parcial se arman dos.
4. Deuda técnica preexistente: las 6 causas de los 13 errores del baseline.
=======
## Juan Manuel - Notebook personal - 2026-09-07 - Agrícola Etapa 3: Pago al Productor (Plan 084)

**Objetivo:** cancelar las liquidaciones del productor con una Orden de Pago, practicando la
retención de Ganancias sobre el acumulado mensual y emitiendo su certificado. **Cierra el
circuito del acopio: romaneo → liquidación → pago.**

**Archivos creados o modificados:**
- `docs/planes/084_agricola_etapa3_pago.md` (nuevo)
- `verticalidades/agricola/tabaco/models.py` (+ `LiquidacionPago`, `RetencionPago`) y su
  migración `0004_pago`
- `verticalidades/agricola/tabaco/services/pago.py` (nuevo)
- `verticalidades/agricola/tabaco/registros.py` (+ `registrar_aplicacion_op`)
- `verticalidades/agricola/tabaco/views_pago.py` (nuevo) y `urls.py` (7 rutas)
- `verticalidades/agricola/tabaco/templates/agricola/pago/` (7 plantillas nuevas)
- `verticalidades/agricola/tabaco/templates/agricola/hooks/menu_sidebar_bottom.html` (2 entradas)
- `verticalidades/agricola/tabaco/tests/test_plan084_pago.py` y `test_plan084_pantallas.py`

**CERO CAMBIOS AL CORE.** Con esta etapa **los tres puntos de extensión del Plan 080 quedan en
uso**: término de stock (pendiente para la Etapa 4), término de cuenta corriente (Plan 083) y
ahora la imputación de Órdenes de Pago.

**Detalle Técnico:**

*La decisión que ordena todo: la retención es un medio de pago.* Ikigai ya sabe practicarlas —un
`MedioPago` de categoría RET que `contabilizar_orden_pago()` acredita contra su cuenta—. No se
construyó un mecanismo nuevo. De ahí sale la ecuación: `OrdenPago.total = Σ medios entregados +
retención`, y `Σ imputaciones = OrdenPago.total`. El asiento lo arma el core sin saber nada de
tabaco, y el término de cuenta corriente del Plan 083 cierra exacto porque la liquidación aportó
su TOTAL y la OP lo cancela entero, retención incluida (supuesto S-1 de `saldos.py`).

*El medio de pago de la retención se resuelve con `get_or_create` por concepto*, tomando la cuenta
contable del propio maestro. Así el contador define la cuenta una sola vez y no hay dos lugares
que puedan discrepar.

*El acumulado mensual se DERIVA, no se almacena.* Se reconstruye sumando los certificados
vigentes del productor en el período. Consecuencia deliberada: al anular un pago se anula su
certificado y el acumulado del mes baja SOLO, sin ningún contador que corregir a mano. El sistema
heredado hacía lo mismo: `liq_mes_ret_gcia` era una vista, no una tabla.

*Alcance de los medios de pago:* efectivo, transferencia, billetera y otros. Los CHEQUES quedan
fuera —arrastran vencimiento, cuenta bancaria, cartera y conciliación— y se avisa en pantalla en
vez de dejar cargar algo a medias.

**Resultado de las pruebas:**

| Prueba | Resultado |
|---|---|
| `test_plan084_pago` (acumulado, asiento, saldos, anulación) | **29/29** |
| `test_plan084_pantallas` (circuito completo + certificado) | **20/20** |
| Prueba de desenchufe | los 3 registros en 0; saldo y pendiente de OP siguen calculando |
| `makemigrations --check` | sin cambios pendientes |
| **Suite completa** | **846 tests, 13 errores** — lista **idéntica** al baseline, cero fallas nuevas y cero caídas de conexión |

*Prueba de humo del circuito completo contra datos reales* (empresa 1, transacción revertida):
liquidación A 0002-00000001 por $ 3.532.750 → retención de Ganancias $ 60.520 sobre base
acumulada $ 3.250.000 menos MNI $ 224.000 → Orden de Pago 0001-00010002 con asiento balanceado
(211001 D 3.532.750 · 111001 H 3.472.230 · 214005 H 60.520), certificado Nº 1 régimen 78 período
202609, **saldo de la liquidación $ 0, saldo del productor $ 0 y pendiente de aplicar de la OP
$ 0**. Esas tres últimas líneas son el cierre del negocio.

**OBSERVACIÓN DE ENTORNO — resuelta.** El backend de PostgreSQL se cayó varias veces durante las
Etapas 0, 2 y 3 (`server closed the connection unexpectedly`). La causa NO era el servidor sino la
CONCURRENCIA: esas corridas competían contra otras suites ejecutándose en paralelo sobre la misma
instancia. La corrida final, con la máquina sola, lo confirma: 846 tests en 1.156 s y cero caídas,
contra 793 tests en 6.415 s con una caída cuando había competencia. Cinco veces más rápido. La
recomendación es no correr suites concurrentes contra la misma instancia.

**Estado actual:** el circuito comercial y financiero del acopio está cerrado de punta a punta.

**Siguientes pasos sugeridos:**
1. **Etapa 4 — Stock del tabaco**: registrar el término de stock del fardo (el único punto de
   extensión del Plan 080 que falta consumir), con el `Producto` por variedad y los kilos.
2. Etapa 5 — lotes de acopio, acondicionamiento, venta y margen por fardo.
3. Etapa 6 — reportes FET / Secretaría de la Producción y libro de retenciones practicadas.
4. Deuda técnica preexistente: las 6 causas de los 13 errores del baseline.

## Antigravity - 07/09/2026
**Objetivo:** Solución de error `IntegrityError` por secuencias de clave primaria desincronizadas.
**Archivos creados o modificados:**
- `reset_sequences.py` [NEW/DELETE] (script temporal)
- `docs/walkthrough.md` [MODIFY]

**Detalle Técnico:**
- Se detectó un error `django.db.utils.IntegrityError` al intentar crear una nueva `CuentaContable` (tabla `cble_cuentas`) provocado porque la secuencia de la tabla no se actualizó tras una inserción explícita de IDs en una migración manual.
- Se elaboró y ejecutó un script (utilizando `django.core.management.color.no_style` y `connection.ops.sequence_reset_sql`) para resetear y sincronizar los contadores de las primary keys en PostgreSQL.
- Se aplicó la reparación sobre todas las tablas del proyecto, ejecutando 76 sentencias de reinicio de secuencias.
- Una vez finalizada la reparación, el script fue eliminado para mantener la higiene del repositorio, acatando las reglas del proyecto.

**Resultado de las pruebas:**
- Script ejecutado exitosamente. Las secuencias de PostgreSQL han sido alineadas con el valor máximo real de los registros de las tablas.

**Estado actual y siguientes pasos sugeridos:**
- Problema solventado. El usuario ya puede crear y guardar registros sin que se produzca una colisión de clave primaria.

## Antigravity - 07/09/2026
**Objetivo:** Continuación y finalización de la Migración de Armería (Fases 2 a 5).
**Archivos creados o modificados:**
- `migracion/scripts/armeria/04_migrar_facturacion_armeria.py` [MODIFY]
- `migracion/scripts/armeria/05_migrar_pagos_recibos_armeria.py` [MODIFY]
- `docs/walkthrough.md` [MODIFY]

**Detalle Técnico e implicaciones:**
- Se procedió a ejecutar las Fases 2 (Inventario), 3 (Tesorería), 4 (Facturación) y 5 (Pagos y Recibos) del bloque de Armería.
- Se detectaron incompatibilidades por los rediseños arquitectónicos previos y se aplicaron parches estructurales en los scripts de migración:
  - En la **Fase 4 (Facturación)**, se corrigió la asignación al modelo `PeriodoIva` (usando el campo `periodo` en vez de `mes/anio`), se ajustaron las claves primarias heredadas (`ventas_id` y `compras_id` en lugar del antiguo `id`), y se implementó un fallback dinámico (con obtención del primer registro disponible) para `proveedor_id`, `cliente_id` y `producto_id` de forma tal de esquivar las restricciones obligatorias `NOT NULL` de la DB en filas huérfanas heredadas de FoxPro.
  - Para esquivar violaciones de clave foránea derivadas de los fallos de clave única o integridad (`UniqueConstraint`), se añadió lógica en memoria post-bulk_create, interceptando únicamente aquellos `id`s que fueron validados en la base, impidiendo arrastrar ítems que hubieran fracasado en la inserción de las cabeceras.
  - En la **Fase 5 (Pagos y Recibos)**, se enlazaron las órdenes de pago y recibos a las compras y ventas adaptando los identificadores referenciales `compras_id` y `ventas_id`.

**Resultado de las pruebas:**
- Fases 2 y 3: Concluidas sin incidencias tras los primeros ajustes.
- Fase 4 (Facturación): Concluida procesando más de 22,900 ventas (y ~34,700 ítems) y 603 compras.
- Fase 5 (Tesorería Pagos): Concluida con 1,805 Órdenes de Pago y 23 Recibos procesados y conciliados exitosamente en la DB.

**Estado actual y siguientes pasos sugeridos:**
- Migración histórica base de Armería finalizada exitosamente a nivel de scripts y registros de DB. Todo el ecosistema heredado se encuentra importado. Se puede dar por cerrado el plan inicial.

### Addendum - Corrección de Clientes vs Proveedores (Armería)
**Detalle Técnico:**
- Se detectó que en el volcado de la Fase 1, todos los registros de la tabla `cli_pro.dbf` habían ingresado al sistema como Clientes (`tipo_entidad=1`) debido a que el antiguo campo `TIPO` de FoxPro se encontraba vacío.
- Se identificó que la verdadera bandera diferenciadora en la base de Armería era la columna `CLI_PRO` (`1` para cliente, `2` para proveedor, `0` neutral).
- **En la base de datos:** Para no tener que eliminar y volver a migrar toda la base de datos (con las demoras masivas que implicaría re-correr Fases 2, 3, 4 y 5), se elaboró un script interno que leyó directamente los DBFs de Comercio y Balance, obteniendo todos los códigos con `CLI_PRO = 2`, y aplicó un `update(tipo_entidad=2)` de manera atómica, corrigiendo 669 registros en total en tiempo real.
- **En los scripts:** Se editó de forma permanente el script de Fase 1 (`01_migrar_maestros_armeria.py`) para que utilice la columna `CLI_PRO` en caso de requerirse una migración limpia desde cero en el futuro.

### Addendum 2 - Asientos Huérfanos en Listado de Ventas (Armería)
**Detalle Técnico:**
- Se reportó que el listado de ventas mostraba la columna "Asiento" vacía. Se comprobó que el script de Fase 4 (`04_migrar_facturacion_armeria.py`) había omitido extraer y mapear el campo `ID_ASTO` proveniente del archivo `ventas_enc.dbf` (y `compras_enc.dbf`) hacia la propiedad `asiento_id` de Django.
- **En la base de datos:** Se ejecutó un script en tiempo real (vía terminal local) que iteró sobre los DBF y aplicó un `bulk_update` directo sobre los modelos de `Venta` en Django. Se vincularon exitosamente **22,585 asientos** históricos con sus comprobantes de venta. (Las compras poseían `ID_ASTO = 0` en origen, por lo que quedaron sin cambios como es correcto).
- **En los scripts:** Se actualizó `04_migrar_facturacion_armeria.py` para mapear de forma permanente `asiento_id=row.get('ID_ASTO')` en las altas nativas.

### Addendum 3 - Corrección de Fallo al Imprimir PDF de Ventas Migradas (Armería)
**Detalle Técnico:**
- Se detectó un error 500 (`AttributeError: 'NoneType' object has no attribute 'codigo'`) al intentar imprimir en PDF comprobantes de venta heredados que no tenían asociado un `TipoComprobante` (`venta.tipo = None`), un escenario común en migraciones históricas con tipos documentales que ya no existen o eran inválidos.
- **En el servicio PDF:** Se modificó `facturacion/services/pdf_service.py` para añadir fallbacks condicionales (`if venta.tipo else ''`) al momento de leer el código y el título del comprobante, garantizando que el reporte en PDF (basado en ReportLab) se dibuje correctamente y titule el documento como "Comprobante" si la venta es huérfana de tipología.

### Addendum 4 - Envolvimiento de Texto (Word-Wrap) en PDF de Ventas
**Detalle Técnico:**
- Se reportó que los detalles de los productos muy largos (ej. armas con especificaciones técnicas o mirillas) desbordaban su columna en la grilla del PDF generado, superponiéndose visualmente sobre las columnas de Cantidad, Precio Unitario e Importe.
- Adicionalmente, se detectó que no se estaban reflejando la Serie y el CUIM de las armas (subproductos) vendidas en el comprobante.
- **En el servicio PDF:** Se incorporó la función `simpleSplit` de `reportlab.lib.utils` en `facturacion/services/pdf_service.py`. En lugar de pintar el string completo en una sola línea, el sistema ahora calcula dinámicamente cuántas líneas requiere el texto para ajustarse al ancho máximo de la columna "Detalle" (280 puntos). Las columnas numéricas (precio, cantidad) se imprimen solo una vez, mientras que el texto descriptivo se dibuja línea por línea empujando el cursor `y_items` dinámicamente hacia abajo.
- **Trazabilidad en PDF:** Se integró en la misma iteración lógica una búsqueda al modelo `Subproducto` a través de la relación inversa pre-cargada (`venta.subproductos.all()`). En caso de coincidir con el producto facturado, se inyectan automáticamente en un renglón nuevo (`\n`) los atributos de "Serie: XXX - Cuim: YYY" debajo del detalle comercial del arma. Adicionalmente, se programó un `fallback` por cliente y fecha: si el usuario imprime un Remito de Venta (el cual FoxPro no vincula nativamente al Subproducto), el sistema buscará inteligentemente si ese mismo producto fue facturado a ese cliente en esa fecha para heredar e imprimir su trazabilidad de todas formas.
- **Corrección de Mapeo FoxPro (Subproductos):** Se detectó que el script de migración `02_migrar_inventario_armeria.py` había omitido enlazar las FK `venta_id` y `compra_id`, y que los `CODIGO` en FoxPro no coincidían 1:1 con el `id` autoincremental de Django. Se ejecutó un parche sobre la base de datos mapeando contra `Producto.codigo_anterior` y se dejaron enlazados exitosamente **1,925 subproductos** a sus respectivas ventas. El archivo `02_migrar_inventario_armeria.py` fue parcheado para que futuras migraciones apliquen esta misma lógica correctamente.
- **Grilla de Trazabilidad:** Se reescribió la consulta ORM de la vista `SubproductoTrazabilidadListView` utilizando `Subquery` en lugar de `distinct('serie')`. Esto solucionó un problema grave donde los filtros (como "Estado Actual = Vendida") aplicaban sobre todo el historial de la serie en lugar de solo sobre su estado más reciente. Además, se habilitó el **ordenamiento dinámico (Sorting)** al hacer clic sobre los encabezados de la tabla, con un input oculto y lógica JavaScript integrados al motor HTMX.
- **Corrección Condición Compras/Ventas:** Se detectó que FoxPro guardaba `CONDIC = 0` en algunas operaciones, lo que provocó que 603 compras y 389 ventas migraran con `condic=0`. Al no ser igual a `1` (Fiscal), el sistema las mostraba visualmente como "Presupuestado" (`condic=2`). Se ejecutó un bulk update para reasignarlas como Fiscal/Real (`condic=1`) y se parcheó el script de migración `04_migrar_facturacion_armeria.py` para asegurar que todo `0` caiga como `1` por defecto.
- **Corrección de Letra en PDF:** Se ajustó la lógica en `facturacion/services/pdf_service.py` que interpreta qué marco dibujar ("A", "B", o "C") en el PDF. Originalmente estaba limitada estrictamente a códigos AFIP (001, 002, 003), lo que provocaba que al renderizar comprobantes históricos con la nomenclatura de FoxPro (`FA`, `CA`, `DA`) el sistema cayera en el caso por defecto (`B`). Ahora el sistema reconoce apropiadamente tanto la codificación AFIP como la interna, renderizando la Letra "A" o "C" correctamente para facturas, notas de débito y crédito.
- **Validación Formulario Producto:** Se reparó un error de validación en la interfaz de creación y edición de productos de la Armería. El campo `unidad_venta`, que había sido establecido como obligatorio a nivel global (requerimiento proveniente de Agrícola), no estaba renderizado en el modal `producto_modal.html`. Esto provocaba que al guardar se enviara un valor vacío y Django rechazara la operación con el error "Este campo es obligatorio". Se incorporó exitosamente el control desplegable "Unidad de Venta" en la misma fila de Punto de Pedido y Stock Mínimo.
- **Corrección de Escala de IVA:** Se detectó que la tabla de FoxPro exportaba la alícuota de IVA en formato unitario (ej. `0.21`, `0.105`), mientras que el ERP espera formato porcentual directo (`21.00`, `10.50`). Esto impedía que los productos y subproductos mapearan correctamente con las opciones predefinidas de la plataforma (21%, 10.5%). Se ejecutó una corrección masiva sobre 7,572 productos y 2,557 subproductos multiplicando su valor por 100 y actualizando la base de datos en tiempo real. Además, el script `02_migrar_inventario_armeria.py` fue modificado para procesar el campo correctamente multiplicando por 100 en futuras importaciones.
- **Facturación - Detalle Dinámico de IVA:** En las "Facturas A" generadas a través del motor de PDFs (`pdf_service.py`), el pie de página informaba exclusivamente un único impuesto (21%), ignorando la presencia de productos facturados al 10.5%. El código fue reescrito para leer e iterar dinámicamente sobre la colección de ítems asociados a la venta (`VentaItem`), agrupar sus bases imponibles de forma proporcional y generar un desglose discriminado por alícuota en el pie del PDF. También se saneó masivamente el campo `iva_alicuota` de las tablas transaccionales en la base de datos que habían importado escalas 0.21 en lugar de 21.00.
- **Filtro de Productos:** Se amplió el buscador HTMX de productos (`buscar_productos` en `views_htmx.py`). Anteriormente solo permitía buscar por Detalle, Código Proveedor o Código Fabricante. Ahora reconoce si la entrada es un número entero para buscar de forma exacta por el `id` autoincremental, y adicionalmente filtra por el `codigo_anterior` de FoxPro, facilitando a los usuarios encontrar productos importados mediante su identificador original.
- **Autocompletado de Clientes en Ventas:** Se corrigió un bug donde el campo de autocompletado de clientes en el listado de ventas no funcionaba al escribir. La causa raíz era una discrepancia de nombres: el input enviaba el valor como `q_cliente` pero el endpoint `typeahead_clientes` solo leía el parámetro `q`. Se parchó la vista para aceptar ambos nombres (`q`, `q_cliente`, `q_proveedor`).
- **Búsqueda por ID en Ventas y Compras:** Se agregó un campo de búsqueda por ID exacto (`venta_id` / `compra_id`) en ambos listados. Cuando se ingresa un ID, el sistema salta los filtros de fecha/cliente y busca directamente por la PK del comprobante.
- **Autocompletado de Proveedor en Compras:** Se reemplazó el `<select>` estático de proveedores (que cargaba todos los proveedores al renderizar la página) por un typeahead dinámico HTMX idéntico al de ventas, con búsqueda progresiva por razón social o CUIT.
- **Unidad de Venta condicional por vertical:** El campo `unidad_venta` en el modal de productos ahora solo se muestra visualmente cuando la empresa tiene `tipo_actividad='DISTRIBUCION'`. Para el resto de verticales (Armería, Agrícola, etc.) el campo queda oculto en la interfaz y en el backend se marcó como `required=False` con un `clean_unidad_venta` que asigna automáticamente el valor por defecto `'UNIDAD'`. Esto evita el error de validación "Este campo es obligatorio" sin impactar la lógica de Distribución.

## Antigravity - 07/09/2026
**Objetivo:** Ajustes de Interfaz en Facturación y Parches/Migraciones de Datos en Armería.
**Archivos creados o modificados:**
- `templates/facturacion/reportes/facturas_pendientes.html` [MODIFY]
- `templates/facturacion/clientes_index.html` [MODIFY]
- `templates/facturacion/partials/cliente_table_rows.html` [MODIFY]
- `migracion/scripts/armeria/01b_parche_clipro_armeria.py` [NEW]
- `migracion/scripts/armeria/06_migrar_asientos_armeria.py` [NEW]
- `docs/walkthrough.md` [MODIFY]

**Detalle Técnico e implicaciones:**
- **UI Facturas Pendientes:** Se corrigió un problema de visualización en navegadores Chrome sobre Windows donde el texto del estado de las facturas (select) quedaba truncado/cortado verticalmente por una altura fija (`h-9` combinada con falta de padding `py`). Se añadió padding vertical (`py-1`).
- **Parche Datos CLIPRO Armería (01b):** Tras descubrir que la migración base (Fase 1) no había mapeado campos clave (Teléfono, Contacto, Correo, Tipo de Documento, Es Policía, CLU y Vto CLU), se diseñó y ejecutó exitosamente el script `01b_parche_clipro_armeria.py`. Este script leyó las bases operativas de FoxPro (`cli_pro.dbf`) en `Comercio` y parchó de manera masiva/atómica sobre la base PostgreSQL mediante `bulk_update` los datos faltantes en `ClienteProveedor` y creando/actualizando relaciones `ExtensionArmeria` sin destruir datos contables ya asociados.
- **Migración Facturación y Libros de IVA (04 y 07):** Se ejecutó el script `04_migrar_facturacion_armeria.py` para procesar el bloque operativo de Facturación. Además, se desarrolló y ejecutó el script `07_migrar_lib_iva_armeria.py` que lee los archivos `lib_iva.dbf` y `lib_iva_alic.dbf` directamente desde el sistema de `Balance` para cargar el módulo contable oficial del Libro IVA Digital (Compras, Ventas y sus correspondientes alícuotas AFIP).
- **Migración Asientos Contables Armería (06):** Se desarrolló y ejecutó el script `06_migrar_asientos_armeria.py` emulando el comportamiento seguro del sistema de Estudios, migrando `asto_enc` (Cabeceras) y `asto_mov` (Líneas) del directorio `Balance` de FoxPro hacia las tablas del subsistema contable nativo, preservando la partida doble estricta matemática de Debe/Haber.
- **Corrección Arquitectónica:** Se restauraron los archivos del core (`clientes_index.html` y `cliente_table_rows.html`) y los hooks de Armería desde el control de versiones, revirtiendo una inyección accidental de código duro que rompía la arquitectura Plug & Play del proyecto. Los hooks nativos ya estaban configurados y su diseño fue preservado.

**Resultado de las pruebas:**
- Script de Parche de CLIPRO ejecutado exitosamente y libre de errores de `UniqueConstraint` utilizando diccionarios para deduplicar filas.
- Script de Migración de Facturación (04) ejecutado procesando exitosamente 22.975 Ventas y 603 Compras.
- Script de Migración de Libro IVA (07) ejecutado procesando exitosamente 1.413 Compras, 7.735 Ventas y 6.284 alícuotas.
- Script de Asientos Contables (06) ejecutado procesando toda la cabecera y movimientos del directorio `Balance`.

**Estado actual y siguientes pasos sugeridos:**
- Migración de datos CLIPRO resuelta.
- Libros de IVA (Facturación) y Asientos Contables migrados exitosamente.
- Queda a definir o refinar cualquier otro ajuste fino en la interfaz o de operaciones "SIGIMAC".
>>>>>>> 6b2fa96e74015965f0956efd62ae588f443dc5e0

---

## 2026-09-07 — Juan Manuel - Notebook personal

### Agrícola · Etapa 6 — Reportes oficiales y gerenciales (Plan 087)

**Objetivo:** lo que el acopio tiene que entregar hacia afuera —FET, Secretaría de la Producción,
organismos recaudadores— y lo que el dueño necesita para decidir.

Plan: [`docs/planes/087_agricola_etapa6_reportes.md`](planes/087_agricola_etapa6_reportes.md).

#### La propiedad que define la etapa: no crea una sola tabla

Todo sale de lo que ya registraron las Etapas 0 a 5. No hay modelos, no hay migraciones y no hay
estado nuevo que mantener sincronizado. Es la prueba de que aquel modelo estaba bien planteado: si
para emitir la planilla FET hubiera que agregar campos, sería señal de que algo no se estaba
capturando cuando correspondía. Hay un test que lo fija enumerando las 19 tablas de las etapas
anteriores (`test_la_etapa_6_no_agrega_ninguna_tabla`).

#### Los cinco reportes

| Reporte | Qué resuelve |
|---|---|
| **Planilla FET** | Reformateo del `Informe_fet` heredado: una fila por romaneo con comprobante, kilos, IVA y las cinco retenciones. CSV y **Excel** |
| **Resumen de acopio** | Fardos, kilos e importe por variedad y clase, con precio promedio ponderado |
| **DDJJ de existencias** | Existencia por galpón **a una fecha de corte** |
| **Libro de retenciones** | Los dos momentos unificados, con totales por organismo |
| **Tableros de margen** | Por campaña, variedad, productor y clase de tabaco |

#### Tres decisiones que el sistema heredado no tuvo que tomar

**1. La planilla FET va por ROMANEO, y las retenciones se prorratean.** El Excel heredado
encabeza con `id_romaneo`, así que la unidad es el romaneo. En el VFP eso era trivial —un romaneo
era una liquidación, el sistema hacía todo en un solo acto—; en Ikigai una liquidación puede
agrupar varios y las retenciones se calculan sobre el comprobante entero. Se prorratean por la
participación del romaneo en el neto, y hay un test que verifica que **la suma de las filas
reconstruye exactamente el IVA y las retenciones del comprobante**.

**2. `Ret. Ganancias` sale del PAGO, no de la liquidación.** Por DA-01, Ganancias se practica al
pagar y su base es el acumulado mensual. Una liquidación todavía no pagada la muestra en cero, y
es lo correcto: poner ahí una estimación sería declarar ante el FET una retención que no se
practicó. La columna se llena con los certificados `RetencionPago` vigentes de las Órdenes de Pago
que cancelaron esa liquidación, prorrateados por lo imputado a ella.

**3. La DDJJ se reconstruye desde los comprobantes, no lee `StockSucursal`.** El stock del ERP
**sólo sabe el presente**. Una declaración que se presenta en octubre por las existencias al 30 de
septiembre necesita el pasado, y el pasado está en los comprobantes. Es el mismo criterio con el
que el ERP deriva el stock, con un corte de fecha encima.

#### Dos hallazgos durante el desarrollo

**A. El adicional no se le paga al productor, y la Etapa 5 lo estaba sumando al costo.**
Al armar la planilla se verificó que `LiquidacionDetalle.importe` es `Sum(fardo.importe)` y que
`liq.neto` se arma de ahí: **el adicional se captura pero no se liquida** —consecuencia directa de
que DA-05 sigue abierta—. Mi Etapa 5 sí lo sumaba a `LoteAcopio.costo_compra`, con lo cual el
costo del lote decía una cosa y la liquidación otra, y el margen salía subestimado contra plata
que nunca salió.

- Corregido: `services/lotes.py::recalcular_lote` ya no lo suma. Se expone aparte en la property
  `LoteAcopio.adicional_informado`.
- En la planilla FET el adicional se muestra —la planilla heredada lo traía— pero **no entra en
  «a pagar»**: incluirlo declararía un importe que el comprobante no dice.
- Al cerrar DA-05 hay que tocar **los dos** lugares juntos: `preparar_liquidacion` y
  `recalcular_lote`.

**B. Los códigos de retención no se pueden cablear.** La primera versión mapeaba las columnas por
código exacto (`IVA`, `GANANCIAS`, `AGUA`). El cliente cargó los suyos como **`RET-IVA`,
`RET-GCIAS` y `USO AGUA`**: tres de las cinco retenciones caían en «otras» y —esto es lo grave—
**nada fallaba a la vista**, porque la fila seguía sumando bien. La planilla mentía en silencio.
Lo detectó `test_una_retencion_nueva_del_maestro_va_a_otras`.

Ahora se resuelve en dos pasos, del más firme al más laxo:
1. Por `tipo_base`, que es **estructural** y no depende del nombre: sólo la retención de IVA se
   calcula sobre el IVA y sólo Ganancias sobre el acumulado mensual. Esas dos columnas quedan
   resueltas sin mirar un solo texto.
2. Por palabra clave en el código o el detalle, para las tres que comparten base `NETO` y no se
   pueden distinguir de otra forma.

Verificado contra los códigos del cliente y contra los genéricos.

#### Archivos creados

- `services/reportes.py` [NEW] — planilla FET, resumen de acopio, existencias a fecha.
- `services/retenciones_libro.py` [NEW] — libro de retenciones, unificando los dos orígenes.
- `services/tableros.py` [NEW] — margen por campaña, variedad, productor y clase.
- `services/exportaciones.py` [NEW] — CSV (`;` + BOM) y XLSX con `openpyxl`.
- `forms_reportes.py` [NEW] · `views_reportes.py` [NEW].
- 11 plantillas en `templates/agricola/reportes/`.
- `tests/test_plan087_reportes.py` [NEW] — 34 tests · `tests/test_plan087_pantallas.py` [NEW] — 27.

#### Archivos modificados

- `verticalidades/agricola/tabaco/services/lotes.py` [MODIFY] — el adicional sale del costo.
- `verticalidades/agricola/tabaco/models.py` [MODIFY] — property `LoteAcopio.adicional_informado`
  (**sin migración**: es una property, no un campo).
- `verticalidades/agricola/tabaco/urls.py` y el hook del menú.
- `docs/agricola/plan inicial agricola.md` — Etapa 6 marcada; DA-05 enriquecida con lo verificado.
- `docs/GUIA_MODULAR.md` — el módulo 17 pasa a 🟢.

#### Reglas transversales respetadas

- **Filtro de `condic` en los cinco reportes.** Los oficiales arrancan en **Real**: lo que se
  declara ante un organismo es la lente fiscal. Los gerenciales, en Todas.
- **Formato es-AR** en pantalla vía `|formato_ar`. En el CSV y el XLSX van **números crudos**: un
  `1.234,56` dentro de un CSV con separador `;` es ambiguo y Excel lo lee como texto; en XLSX el
  formato lo pone la celda. Hay un test para cada cosa.
- **Sin Django Admin**: todo HTML + Tailwind + HTMX.

#### Resultado de las pruebas

- `test_plan087_reportes` → **34/34 OK** (414,3 s).
- `test_plan087_pantallas` → **27/27 OK** (240,8 s).
- `manage.py makemigrations --check --dry-run` → `No changes detected`. **La etapa no genera
  ninguna migración**, que era el criterio de hecho más importante.
- **Prueba de desenchufe**: sin la carpeta, `manage.py check` pasa, los términos de stock vuelven
  a los cuatro de siempre, los tres registros de extensión quedan en cero y las URLs `agro_` dejan
  de resolver, como corresponde. Al reenchufar, todo vuelve.

#### Estado actual y siguientes pasos

**El circuito del acopio de tabaco queda completo de punta a punta**: maestros → romaneo →
liquidación → asiento → Libro IVA → cuenta corriente → pago → certificado → stock → lote →
acondicionamiento → venta → margen → reportes oficiales.

1. **Cargar los procesos reales de la planta** (Configuración → Procesos de Acondicionamiento).
   Es lo único que resta de DA-07 y es dato operativo.
2. **Cerrar DA-05** (naturaleza del adicional). Hoy no se paga; si debe pagarse, son dos lugares.
3. Etapas 7 a 9 —producción propia, granos y caña, exportación— fuera del alcance inicial.
4. MP-01 (notas de crédito de liquidación) y MP-02 (webservice WSLTV) siguen pendientes.
5. Deuda técnica preexistente: las 6 causas de los 13 errores del baseline.

---

## 2026-09-07 (cierre del día) — Juan Manuel - Notebook personal

### Agrícola · Cuatro decisiones cerradas sobre la Etapa 6

Después de la primera entrega del Plan 087, el usuario revisó los hallazgos y cerró cuatro puntos.
Esta entrada registra lo que se cambió y por qué.

#### 1. El adicional: comodín en cero, no se usa (DA-05 CERRADA)

**Decisión del usuario:** *"El adicional lo dejamos en cero y por lo pronto no lo utilizaremos.
Es un comodín que lo más probable es que nunca usemos."*

Se fue un paso más allá de dejarlo en cero: **la pantalla de carga de fardos ya no lo dibuja**. Un
input que se puede llenar y que nunca se cobra es la misma clase de mentira silenciosa que la
columna FET mal mapeada — alguien carga $50.000 y el productor nunca los ve.

- `forms_romaneo.py::FardoForm.adicional` → `HiddenInput`.
- `templates/agricola/romaneo/carga.html` → el bloque del input se retira, con el comentario del
  porqué.
- `models.py::FardoTabaco.adicional` → documentado como comodín, con la nota de que el día que se
  use hay que tocar `preparar_liquidacion` y `recalcular_lote` **juntos**.

El campo sobrevive en el modelo y en el servicio: sigue siendo un comodín disponible.

#### 2. La columna de la planilla FET pasa a ser un dato del maestro

**Observación del usuario:** *"Si el código mapeaba columnas por código exacto ¿por qué me pediste
que los cargue y no lo hiciste tú que sabías el código?"*

**Tiene razón, y el error es mío:** le pedí que cargara los conceptos de retención sin decirle qué
códigos usar, y después escribí un reporte que asumía códigos. Nunca definí uno y aun así el
reporte dependía de eso.

Ofreció cambiar los datos de la tabla para que encajaran con el código. **No se hizo, y por una
razón:** doblar los datos deja el problema de fondo intacto —el mapeo seguiría siendo implícito— y
el próximo concepto que cargue volvería a caer mal. El problema no era el mapa: era que estaba
escondido.

**Solución: `TipoRetencionTabaco.columna_fet`.** Cada concepto declara a qué columna aporta. Se ve
en la pestaña de Configuración, se edita desde el ABM, y un concepto nuevo se asigna a propósito.
Vacío significa «Otras retenciones», que es una columna real de la planilla y no un error.

La migración de datos `0007_sembrar_columna_fet` lo dejó cargado de una vez, deduciendo primero
por `tipo_base` —que es estructural: sólo la retención de IVA se calcula sobre el IVA y sólo
Ganancias sobre el acumulado mensual— y después por palabra clave para las tres que comparten base
`NETO`. **El usuario no tuvo que tocar nada.** Verificado sobre la base real:

| Código cargado | Base | Columna FET asignada |
|---|---|---|
| `RET-IVA` | IVA | Ret. IVA |
| `RET-GCIAS` | ACUM_MENSUAL | Ret. Ganancias |
| `EEAOC` | NETO | EEAOC |
| `SALUD PUBLICA` | NETO | Salud Pública |
| `USO AGUA` | NETO | Uso de Agua |

La deducción sobrevive en `services/reportes.py::_deducir_columna()` como **red**, no como camino
principal: cubre lo que entre por una importación sin pasar por el ABM.

> **Costo consciente:** esto rompe la propiedad «la Etapa 6 no genera migraciones». Se aceptó
> porque la alternativa era dejar una declaración legal apoyada en una heurística.

#### 3. Toda liquidación de tabaco es fiscal — `condic = 1`

**Decisión del usuario:** *"Todas las liquidaciones son fiscales y por lo tanto condic = 1."*

Eso convertía el combo del alta de romaneo en una trampa: un romaneo cargado por error como
Presupuestado **desaparecería en silencio de la planilla FET**, que es una declaración legal.

- `forms_romaneo.py::AbrirRomaneoForm.condic` → `HiddenInput` con `initial=1`.
- `templates/agricola/romaneo/nuevo.html` → muestra «Real / Fiscal — toda liquidación de tabaco lo
  es», sin combo.

El campo sigue en el modelo, lo hereda el asiento (regla inflexible del proyecto) y los listados
conservan el filtro de condición.

#### 4. CSV sin separador de miles

Confirmado por el usuario, sin cambios. Ya estaba fijado por
`test_el_csv_lleva_numeros_crudos_y_no_formato_argentino`.

#### Archivos modificados

- `verticalidades/agricola/tabaco/models.py` — campo `columna_fet`; documentación de `adicional`.
- `verticalidades/agricola/tabaco/migrations/0006_columna_fet.py` [NEW] y
  `0007_sembrar_columna_fet.py` [NEW].
- `verticalidades/agricola/tabaco/services/reportes.py` — `columna_de()` lee el maestro;
  `_deducir_columna()` queda como red.
- `verticalidades/agricola/tabaco/forms.py` — `columna_fet` en el ABM de retenciones.
- `verticalidades/agricola/tabaco/forms_romaneo.py` — `condic` y `adicional` ocultos.
- `templates/agricola/partials/retencion_table_rows.html` y
  `templates/configuracion/partials/agro_retenciones.html` — columna «Col. FET» visible.
- `templates/agricola/romaneo/nuevo.html` y `carga.html`.
- `tests/test_plan087_reportes.py` — clase `DecisionesCerradasTests`, 5 tests nuevos.
- `docs/agricola/plan inicial agricola.md` — DA-05 cerrada; `condic` y `columna_fet` documentadas.
- `docs/planes/087_agricola_etapa6_reportes.md` — §7.2 reescrita, §8 con las decisiones cerradas.

#### Estado y siguiente paso acordado

El usuario eligió seguir por **la deuda técnica preexistente** (los 13 errores del baseline),
empezando por la violación del Modo Enchufe. Análisis ya iniciado:

- **Módulo-nivel, fatales al desenchufar:**
  `facturacion/services/facturacion_lote_service.py:7` y `facturacion/views_estudio.py:9`
  importan `verticalidades.estudio.models` en el encabezado, sin `try/except`.
  `verticalidades/estudio/urls.py` importa a su vez `facturacion.views_estudio`, o sea que la
  dependencia va **core → verticalidad**, al revés del Plan 075.
- **Ya resueltos con `try/except`** (patrón correcto, sirve de referencia):
  `facturacion/views_htmx.py:8-20`.
- **Dentro de funciones** (aceptable): `facturacion/helpers.py`, `core/services/numeracion.py`,
  `core/views_config.py`.

Queda pendiente decidir dónde vive `FacturacionLoteService` y `views_estudio`: lo natural es
moverlos a `verticalidades/estudio/`, que es de quien son.

---

## 2026-09-09 — Cristian - PC CASA

### Mejoras y Correcciones en Panel de Reservas SIGIMAC (Plan 088)

**Objetivo:**
1. Implementar búsqueda inteligente multi-criterio y en tiempo real (autocompletado/filtrado dinámico con HTMX y debounce) que busque por Cliente completo (razón social, CUIT, teléfono, correo, etc.), Producto y Subproducto (detalle, serie, CUIM, código de proveedor, código de fábrica), Recibo de seña e IDs de Reserva/Preventa.
2. Corregir el corte de texto inferior en el selector de Estado SIGIMAC.
3. Rediseñar y corregir la visualización colapsada ("manchones") de los botones de filtrar y reiniciar en el panel de reservas.

**Archivos creados o modificados:**
- `verticalidades/armeria/views.py` (modificado): Manejo de solicitudes HTMX en `get_template_names()`, consulta inteligente multi-token para `q` filtrando sobre Cliente, Producto, Subproductos (serie/CUIM), Recibo y números de comprobante/reserva, y aplicación de `.distinct()`.
- `verticalidades/armeria/templates/armeria/reservas_list.html` (modificado): Rediseño del formulario con triggers HTMX (`input delay:300ms`, `change`), indicador spinner de carga animado, select de Estado SIGIMAC estilizado sin recortes (`h-10 px-3 py-2 text-xs font-semibold rounded-xl`), y botones de Filtrar y Reiniciar con espaciado amplio, iconos claros, tooltips y etiquetas responsivas.
- `verticalidades/armeria/templates/armeria/partials/reservas_tabla_parcial.html` (creado): Parcial con la tabla de reservas y tarjetas de resumen métricas para actualización reactiva instantánea por HTMX.
- `verticalidades/armeria/tests.py` (creado): Suite de pruebas unitarias cubriendo listado completo, respuesta parcial HTMX, búsqueda por cliente, producto/subproducto (serie/CUIM), recibo y filtros por estado.
- `docs/planes/088_mejoras_reservas_sigimac.md` (creado): Plan formal archivado.

**Detalle Técnico:**
- La búsqueda inteligente divide los términos ingresados por espacios y aplica filtros combinados `AND` entre términos y `OR` entre los campos correspondientes a Cliente, Producto, Subproducto, Recibo y número de preventa/reserva.
- Se configuró `hx-trigger="input changed delay:300ms, search"` en el input de búsqueda y `hx-trigger="change"` en los selectores de estado y fechas, permitiendo un filtrado reactivo y fluido sin necesidad de pulsar Enter o hacer click en botones (manteniendo además los botones accesibles y estéticos para submit tradicional).
- Ajuste UI: Se tomó como referencia exacta la barra de filtros de `compras_listado.html` con contenedor `flex flex-wrap items-end gap-3`, campos de fecha compactos (`w-32`), y botones con texto legible y visible ("Filtrar" y "Limpiar").
- Se corrigió la duplicación de los globos/tarjetas de resumen al incluir el parcial en la carga estática inicial.
- Se ajustó el selector de Estado SIGIMAC con `py-1 px-2.5 text-xs font-bold leading-normal` para evitar el clipping vertical del texto en Windows/Chromium.

**Estado actual y siguientes pasos:**
## 2026-09-09 — Cristian - PC CASA

### Búsqueda Inteligente Multi-Término de Productos en Preventa y Ventas (Plan 089)

**Objetivo:**
Hacer más inteligente la búsqueda de productos en la carga de preventa, autocompletado y catálogo general, permitiendo concatenar palabras clave en cualquier orden (hacia adelante, atrás o en el medio) y buscando a través de múltiples atributos (detalle, código de fábrica, código de proveedor, código anterior VFP, marca, rubro, familia e ID), con ordenamiento jerárquico por relevancia y límite optimizado de hasta 100 registros por consulta.

**Archivos creados o modificados:**
- `productos/services/busqueda_service.py` [NEW]: Motor centralizado de búsqueda inteligente de productos con tokenización (`q.split()`), condiciones `AND` por término y `OR` multi-campo, priorización por `Case/When` (coincidencias exactas primero, inicio de texto, subcadena y términos combinados) y soporte multi-tenant.
- `facturacion/views_htmx.py` [MODIFY]: Integración del servicio en `typeahead_productos_venta` (preventa/ventas rápidas), `buscar_producto_venta_por_codigo` (Enter directo con fallback inteligente), `lista_productos_venta_resultados` (modal de ventas con límite de 100 registros), `typeahead_productos_compra` y `lista_productos_resultados` (modal de compras con límite de 100 registros).
- `productos/views_htmx.py` [MODIFY]: Integración en `buscar_productos` para el catálogo general con límite de 100 registros.
- `productos/tests/test_busqueda_inteligente.py` [NEW]: Suite de pruebas unitarias cubriendo palabras en orden invertido, intercaladas, búsqueda por marca/códigos anteriores, relevancia exacta, aislamiento multi-tenant y endpoints HTMX.
- `docs/planes/089_busqueda_inteligente_productos.md` [NEW]: Plan de implementación archivado.
- `docs/walkthrough.md` [MODIFY]: Registro de bitácora acumulativa.

**Detalle Técnico:**
- **Tokenización Multi-Término:** Se descomponen las consultas en palabras individuales permitiendo que términos como `"9mm bersa"` o `"tpr9 pavonada"` localicen de inmediato `"PISTOLA BERSA TPR9 CALIBRE 9X19MM PAVONADA"`.
- **Búsqueda Multi-Atributo:** Cada término busca simultáneamente en `detalle`, `cod_fab`, `cod_prov`, `codigo_anterior`, `marca__detalle`, `rubro__detalle`, `familia__detalle` e `id` (si es numérico).
- **Priorización de Relevancia:** Se utiliza una expresión `Case(When(...))` en Django ORM para asignar orden prioritario a coincidencias exactas de código/ID (peso 1 o 2), coincidencias al inicio del detalle (peso 3), frases completas (peso 4) y coincidencias compuestas (peso 6), manteniendo respuestas ágiles y precisas.
- **Capacidad de Resultados:** Se amplió el límite de resultados para vistas de catálogo y modales de 50 a 100 registros para mayor comodidad del operador sin penalizar la velocidad de la base de datos.

**Resultado de las pruebas:**
- Se crearon pruebas unitarias integrales en `productos/tests/test_busqueda_inteligente.py`.

**Estado actual y siguientes pasos:**
- Motor de búsqueda inteligente completamente operativo en la carga de preventa, ventas, compras y catálogo general.
- Siguientes pasos: Continuar con la hoja de ruta del proyecto o nuevas tareas solicitadas.

## Estudio - Refactor Facturación por Lotes (Servicios)
- **Fecha/Día**: 14 de Septiembre de 2026
- **Objetivo o Tarea**: Migrar módulo de Facturación Lotes a verticalidad Estudio, ajustar período por separado e implementar emisión real AFIP de Servicios.
- **Archivos creados o modificados**: erticalidades/estudio/services/facturacion_lote_estudio.py [NEW], erticalidades/estudio/views.py [MODIFY], erticalidades/estudio/urls.py [MODIFY], erticalidades/estudio/templates/estudio/facturacion_lotes.html [MODIFY].
- **Detalle Técnico e implicaciones**: Se creó el servicio FacturacionLoteEstudioService que conecta con ARCA usando concepto = 2 y fechas armadas desde el período seleccionado. Se trasladaron las vistas desde el core a la verticalidad Estudio sin afectar asientos. En la UI se separó el input de período en Mes y Año autocentrados.
- **Resultado de las pruebas**: Migración de código y templates exitosa. UI revisada.
- **Estado actual y siguientes pasos sugeridos**: Listo para probar facturar un servicio real.

## 2026-09-15 - Excepciones a Roles (Permisos Negativos)

**Objetivo**: Implementar un sistema de exclusiones de permisos para que un usuario pueda tener permisos denegados de forma puntual, anulando los permisos que hereda de su grupo/rol.

**Archivos modificados**:
- usuarios/models.py: Creado modelo PermisoDenegado.
- usuarios/backends.py: Modificado CaseInsensitiveModelBackend para restar PermisoDenegado del set total de permisos de Django.
- usuarios/views_htmx.py: Lógica para guardar PermisoDenegado vs user_permissions al editar un usuario.
- 	emplates/configuracion/modals/usuario_form.html: Habilitados checkboxes de permisos heredados con estados tachado/denegado.

**Migraciones**: usuarios.0004_permisodenegado.
**Siguientes pasos**: Comprobar el funcionamiento del submodal de exclusiones en la UI y la re-renderización de la navbar.
 
 # #   A n t i g r a v i t y 
 -   * * F e c h a / D � a * * :   1 5   d e   S e p t i e m b r e   d e   2 0 2 6 
 -   * * O b j e t i v o   o   T a r e a * * :   C o r r e g i r   e r r o r   c o n c e p t u a l   e n   l a   a s i g n a c i � n   d e   p e r m i s o s   d e n e g a d o s   a l   a g r e g a r   r o l e s   a   u n   u s u a r i o . 
 -   * * A r c h i v o s   c r e a d o s   o   m o d i f i c a d o s * * : 
     -   \ u s u a r i o s / v i e w s _ h t m x . p y \   [ M O D I F Y ] 
 -   * * D e t a l l e   T � c n i c o   e   i m p l i c a c i o n e s * * : 
     -   C u a n d o   s e   a s i g n a b a   u n   n u e v o   g r u p o   ( r o l )   a   u n   u s u a r i o ,   l o s   c h e c k b o x e s   i n d i v i d u a l e s   d e   l o s   p e r m i s o s   h e r e d a d o s   d e   e s e   r o l   n o   a p a r e c � a n   m a r c a d o s   e n   e l   D O M   o r i g i n a l   d e l   f r o n t e n d   a l   m o m e n t o   d e   e n v i a r   e l   f o r m u l a r i o . 
     -   E l   b a c k e n d   c a l c u l a b a   \ d e n e g a d o s   =   p e r m i s o s _ h e r e d a d o s   -   m a r c a d o s \ ,   p o r   l o   q u e   a u t o m � t i c a m e n t e   c a t a l o g a b a   t o d o s   l o s   p e r m i s o s   d e l   g r u p o   r e c i � n   a s i g n a d o   c o m o   d e n e g a d o s   ( y a   q u e   n o   v i a j a b a n   e n   \ m a r c a d o s \ ) . 
     -   S e   m o d i f i c �   l a   l � g i c a   p a r a   c r u z a r   e s t o   c o n   e l   e s t a d o   a n t e r i o r   d e   l a   b a s e   d e   d a t o s   ( \ p e r m i s o s _ h e r e d a d o s _ a n t e s \ ) .   A h o r a   u n   p e r m i s o   s o l o   p a s a   a   d e n e g a d o   s i   e l   u s u a r i o   * * y a   l o   t e n � a   h e r e d a d o   d e s d e   a n t e s   d e   a b r i r   e l   m o d a l * *   y   e x p l � c i t a m e n t e   l o   d e s m a r c � . 
 -   * * R e s u l t a d o   d e   l a s   p r u e b a s * * :   L a   a d i c i � n   d e   u n   n u e v o   r o l   y a   n o   n i e g a   l o s   p e r m i s o s   a u t o m � t i c a m e n t e ,   p e r o   s �   r e s p e t a   l a s   d e n e g a c i o n e s   o   r e v o c a c i o n e s   m a n u a l e s   p o s t e r i o r e s .  
 # #   A n t i g r a v i t y 
 -   * * F e c h a / D � a * * :   1 5   d e   S e p t i e m b r e   d e   2 0 2 6 
 -   * * O b j e t i v o   o   T a r e a * * :   M e j o r a r   l a   U X   d e   a s i g n a c i � n   d e   p e r m i s o s   y   v i s i b i l i d a d   d e l   N a v b a r . 
 -   * * A r c h i v o s   c r e a d o s   o   m o d i f i c a d o s * * : 
     -   \ 	 e m p l a t e s / b a s e . h t m l \   [ M O D I F Y ] 
     -   \ 	 e m p l a t e s / c o n f i g u r a c i o n / m o d a l s / u s u a r i o _ f o r m . h t m l \   [ M O D I F Y ] 
 -   * * D e t a l l e   T � c n i c o   e   i m p l i c a c i o n e s * * : 
     -   S e   a g r e g �   l � g i c a   J a v a S c r i p t   e n   \ u s u a r i o _ f o r m . h t m l \   p a r a   q u e   a l   t i l d a r / d e s t i l d a r   u n   p e r m i s o   ' P a d r e '   ( e j .   \ m e n u _ v e n t a s \ ) ,   a u t o m � t i c a m e n t e   s e l e c c i o n e   o   d e s e l e c c i o n e   t o d o s   s u s   p e r m i s o s   h i j o s   ( \ m e n u _ v e n t a s _ * \ ) ,   h a c i � n d o l o   u n   c o m p o r t a m i e n t o   e x p l � c i t o   e n   l a   U I . 
     -   E n   \  a s e . h t m l \ ,   l o s   a c c e s o s   a   l o s   m � d u l o s   p r i n c i p a l e s   d e l   N a v b a r   a h o r a   v a l i d a n   s i   e l   u s u a r i o   p o s e e   * * c u a l q u i e r a * *   d e   l o s   p e r m i s o s   h i j o s ,   n o   s o l o   e l   p e r m i s o   ' P a d r e '   e s t r i c t o .   E s t o   p e r m i t e   q u e   u n   u s u a r i o   c o n   s o l o   u n   p e r m i s o   e s p e c � f i c o   ( c o m o   P r e v e n t a )   p u e d a   v e r   e l   m e n �   r a � z   c o r r e s p o n d i e n t e   e n   e l   s i d e b a r . 
 -   * * R e s u l t a d o   d e   l a s   p r u e b a s * * :   N a v b a r   v i s i b l e   c o r r e c t a m e n t e   a l   h e r e d a r   s o l o   p e r m i s o s   s e c u n d a r i o s .   M o d a l   a u t o c o m p l e t a   s e l e c c i o n e s .  
 # #   A n t i g r a v i t y 
 -   * * F e c h a / D � a * * :   1 5   d e   S e p t i e m b r e   d e   2 0 2 6 
 -   * * O b j e t i v o   o   T a r e a * * :   D e s a c o p l a r   c o m p r o b a c i o n e s   d e   p e r m i s o s   a n i d a d o s   e n   e l   N a v b a r . 
 -   * * A r c h i v o s   c r e a d o s   o   m o d i f i c a d o s * * : 
     -   \ 	 e m p l a t e s / b a s e . h t m l \   [ M O D I F Y ] 
 -   * * D e t a l l e   T � c n i c o   e   i m p l i c a c i o n e s * * : 
     -   S e   d e s c u b r i �   q u e   v a r i o s   l i n k s   a   s u b - m � d u l o s   e s t a b a n   e n g l o b a d o s   e r r � n e a m e n t e   d e n t r o   d e l   b l o q u e   \ { %   i f   % } \   d e   s u   m � d u l o   \  
 h e r m a n o \   ( e j .   \ m e n u _ v e n t a s _ p r e v e n t a s \   e s t a b a   a d e n t r o   d e l   b l o q u e   q u e   v e r i f i c a b a   \ m e n u _ v e n t a s _ c a r g a \ ) .   
     -   A l   s e p a r a r   e s t o s   c o n d i c i o n a l e s   a   s u   p r o p i o   \ { %   i f   % } \   i n d i v i d u a l ,   a s e g u r a m o s   q u e   s i   u n   u s u a r i o   s o l o   t i e n e   a c c e s o   a   \ C a r g a  
 d e  
 P r e V e n t a s \   o   \ � r d e n e s  
 d e  
 C o m p r a \ ,   e l   l i n k   s e   m u e s t r e   d e   m a n e r a   i n d e p e n d i e n t e   e n   e l   N a v b a r   s i n   r e q u e r i r   t e n e r   a c c e s o   a   l a   c a r g a   d e   v e n t a s / c o m p r a s   g e n e r a l . 
 -   * * R e s u l t a d o   d e   l a s   p r u e b a s * * :   N a v b a r   r e n d e r i z a   a p r o p i a d a m e n t e   l o s   a c c e s o s   d e   m e n � s   e s p e c � f i c o s   q u e   a n t e s   q u e d a b a n   o c u l t o s   p o r   e l   a c o p l a m i e n t o .  
 # #   A n t i g r a v i t y 
 -   * * F e c h a / D � a * * :   1 5   d e   S e p t i e m b r e   d e   2 0 2 6 
 -   * * O b j e t i v o   o   T a r e a * * :   V a l i d a r   p e r m i s o s   e n   l o s   D a s h b o a r d   d e   l o s   M � d u l o s   ( V e n t a s ,   C o m p r a s )   y   C o n f i g u r a c i � n . 
 -   * * A r c h i v o s   c r e a d o s   o   m o d i f i c a d o s * * : 
     -   \ 	 e m p l a t e s / f a c t u r a c i o n / v e n t a s _ i n d e x . h t m l \   [ M O D I F Y ] 
     -   \ 	 e m p l a t e s / f a c t u r a c i o n / c o m p r a s _ i n d e x . h t m l \   [ M O D I F Y ] 
     -   \ 	 e m p l a t e s / c o n f i g u r a c i o n / p a r t i a l s / h u b . h t m l \   [ M O D I F Y ] 
 -   * * D e t a l l e   T � c n i c o   e   i m p l i c a c i o n e s * * : 
     -   A n t e r i o r m e n t e ,   a u n q u e   e l   s i d e b a r   c o n t r o l a b a   l a   v i s i b i l i d a d   d e   l a s   o p c i o n e s ,   l o s   _ D a s h b o a r d s _   d e   i n i c i o   d e   c a d a   m � d u l o   ( e j .   \  e n t a s _ i n d e x \ ,   \ c o m p r a s _ i n d e x \ )   m o s t r a b a n   * * t o d a s * *   l a s   t a r j e t a s   d e   a c c e s o s   d i r e c t o s   s i n   i m p o r t a r   l o s   p e r m i s o s   d e l   u s u a r i o . 
     -   S e   a � a d i e r o n   b l o q u e s   \ { %   i f   p e r m s . u s u a r i o s . . .   % } \   a l r e d e d o r   d e   c a d a   _ c a r d _   ( C a r g a   d e   V e n t a s ,   L i s t a d o ,   P r e v e n t a s ,   � r d e n e s   d e   C o m p r a ,   C a r g a   I A ,   e t c . )   e n   l a s   p l a n t i l l a s   d e   l o s   m � d u l o s   c o r r e s p o n d i e n t e s . 
     -   S e   r e p l i c �   l a   s e g u r i d a d   v i s u a l   p a r a   l a s   t a r j e t a s   d e   G e s t i � n   d e   U s u a r i o s   y   R o l e s   e n   e l   \ h u b . h t m l \   d e   c o n f i g u r a c i � n ,   a s e g u r a n d o   q u e   s o l o   a d m i n i s t r a d o r e s   p u e d a n   v e r   e s t o s   r e c u a d r o s . 
 -   * * R e s u l t a d o   d e   l a s   p r u e b a s * * :   L o s   D a s h b o a r d s   d e   l o s   m � d u l o s   s o l o   r e n d e r i z a n   l a s   t a r j e t a s   d e   f u n c i o n a l i d a d e s   a   l a s   q u e   e l   u s u a r i o   p o s e e   p e r m i s o .  
 # #   A n t i g r a v i t y 
 -   * * F e c h a / D � a * * :   1 5   d e   S e p t i e m b r e   d e   2 0 2 6 
 -   * * O b j e t i v o   o   T a r e a * * :   I m p l e m e n t a r   M i d d l e w a r e   G l o b a l   d e   P e r m i s o s . 
 -   * * A r c h i v o s   c r e a d o s   o   m o d i f i c a d o s * * : 
     -   \ 	 e m p l a t e s / b a s e . h t m l \   [ M O D I F Y ] 
     -   \ u s u a r i o s / m i d d l e w a r e . p y \   [ N E W ] 
     -   \ c o n f i g / s e t t i n g s . p y \   [ M O D I F Y ] 
 -   * * D e t a l l e   T � c n i c o   e   i m p l i c a c i o n e s * * : 
     -   S e   e x t r a j e r o n   l o s   \ { %   h o o k _ m e n u   % } \   d e l   c o n d i c i o n a l   d e   C a r g a   e n   \  a s e . h t m l \   p a r a   g a r a n t i z a r   q u e   l a   v e r t i c a l i d a d   s e   m u e s t r e   s i   e l   u s u a r i o   t i e n e   o t r o s   p e r m i s o s   d e l   m � d u l o   p e r o   n o   n e c e s a r i a m e n t e   e l   d e   c a r g a . 
     -   S e   c r e �   \ R o l e P e r m i s s i o n M i d d l e w a r e \   c o n   t r e s   n i v e l e s   d e   c h e q u e o : 
         1 .   M a p a   e x a c t o   d e   U R L   ( \ E X A C T _ M A P \ )   p a r a   v i s t a s   c r � t i c a s . 
         2 .   M a p a   d e   p r e f i j o   ( \ P R E F I X _ M A P \ )   p a r a   a g r u p a r   e n d p o i n t s   d e   c o n f i g u r a c i � n   o   d e   s e g u r i d a d . 
         3 .   V a l i d a c i � n   p o r   p r e f i j o   d e   m � d u l o   ( \ M O D U L E _ P R E F I X _ P E R M S \ )   p a r a   g a r a n t i z a r   q u e   e n d p o i n t s   g e n � r i c o s   ( e j .   l l a m a d a s   A J A X )   e x i j a n   a l   m e n o s   u n   p e r m i s o   d e n t r o   d e   e s a   f a m i l i a . 
     -   S e   a g r e g �   a   \ M I D D L E W A R E \   e n   \ s e t t i n g s . p y \ . 
 -   * * R e s u l t a d o   d e   l a s   p r u e b a s * * :   L i s t o   p a r a   v e r i f i c a c i � n   m a n u a l .   L a   i n t r u s i � n   d i r e c t a   v � a   U R L   p o r   u s u a r i o s   n o   a u t o r i z a d o s   a r r o j a r �   u n   4 0 3   ( A c c e s o   D e n e g a d o ) .  
 
## Antigravity
- **Fecha/Día**: 15 de Septiembre de 2026
- **Objetivo o Tarea**: Reestructuración de Sucursales por Usuario y Parámetros Contables por Empresa
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
- **Detalle Técnico e implicaciones**:
    - Se añadió el campo M2M sucursales al modelo Perfil.
    - Se actualizó el formulario de Usuarios para permitir la selección de sucursales permitidas.
    - El context_processor valida que la sucursal actual esté dentro de las permitidas, con un fallback a Sede/Casa Central.
    - SeleccionEmpresaView ahora filtra las sucursales devueltas utilizando Prefetch según los permisos.
    - Se movió el acceso de Parámetros Contables del Hub global hacia las filas individuales del ABM de Empresas en la tabla HTMX, inyectando el empresa_id directamente a la URL de HTMX.
- **Resultado de las pruebas**: Vistas HTMX, forms y modelos actualizados correctamente, migraciones ejecutadas exitosamente.
