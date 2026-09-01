# Plan de Implementación: Lector de Facturas y Perfiles de Lectura (Proveedor BOWIE)

## Objetivo
Crear un sistema de perfiles de lectura determinista (basado en Regex) para procesar facturas de compra en PDF. Esto complementará o reemplazará la lectura mediante IA genérica, permitiendo extraer con precisión matemática no solo las cabeceras (CUIT, Fecha, Importes), sino también el detalle de los ítems (código, cantidad, descripción, precio unitario y total), asociándolos automáticamente a los productos de la base de datos.
Comenzaremos implementando el primer perfil para el proveedor **BOWIE** (CUIT: 30-61040124-0).

## Análisis
Tras analizar los archivos provistos (`Modelos/facturas/BOWIE.pdf`):
- El CUIT de BOWIE es `30-61040124-0`.
- El PDF contiene texto que puede ser extraído con `pdfplumber`.
- Los ítems de la factura tienen un formato consistente que puede ser analizado con expresiones regulares. He desarrollado una expresión regular (probada con éxito sobre el documento base) que extrae correctamente los productos: código del proveedor, cantidad, descripción, precio unitario y precio total.

> [!WARNING]
> User Review Required: Actualmente la vista con IA (`CargaCompraIAView`) solo devuelve la cabecera (totales, fecha, CUIT). Para procesar los ítems, necesitaremos que el sistema no solo devuelva el JSON, sino que busque los productos en la base de datos (por `cod_prov` o `detalle`) y los cargue en la tabla de ítems de la compra de forma automática.

## Cambios Propuestos

### Módulo de Parsers (`facturacion/services/invoice_parsers/`)
Se creará un nuevo subpaquete dentro de `services` para orquestar la lectura estructurada.

#### [NEW] `facturacion/services/invoice_parsers/__init__.py`
#### [NEW] `facturacion/services/invoice_parsers/base.py`
- Definirá la clase base `BaseInvoiceParser` y un registro (`Registry`) para matchear CUITs con su parser correspondiente.

#### [NEW] `facturacion/services/invoice_parsers/bowie.py`
- Implementará `BowieInvoiceParser`.
- Procesará el texto usando Regex para extraer los números de comprobante, fecha, totales, y un listado detallado de ítems.

#### [NEW] `facturacion/services/invoice_parsers/dispatcher.py`
- Función principal `procesar_factura_perfil(file_bytes, filename)`.
- Leerá el PDF inicial, extraerá el CUIT y, si existe un parser para ese CUIT en el registro (ej. BOWIE), derivará la extracción detallada hacia allí.

### Integración en Vistas y Frontend

#### [MODIFY] `facturacion/views_ia.py` o `facturacion/views_procesamiento.py`
- Modificaremos la vista de procesamiento para que **primero** intente leer la factura usando nuestro `dispatcher`.
- Si el CUIT corresponde a BOWIE, obtendremos el JSON con cabecera + ítems.
- Buscará en la base de datos (modelo `Producto`) coincidencias para el código extraído de la factura (contra `cod_prov`).
- Insertaremos los ítems encontrados en la variable de sesión `compra_items_temp` o los devolveremos en el JSON para que el frontend los reciba y actualice la UI.

#### [MODIFY] `templates/facturacion/carga_compra_ia.html` o `templates/facturacion/compras_carga.html`
- Adaptaremos el JavaScript/HTMX para que, al cargar la factura por perfil y detectarse los productos de forma exitosa, la tabla de ítems de la pantalla de carga se refresque mostrando las cantidades y precios correspondientes.

## Open Questions

> [!IMPORTANT]
> 1. **Manejo de Productos no Encontrados**: Si al leer el detalle de la factura de BOWIE encontramos el código `20832` pero este NO existe en la base de datos de Productos, ¿qué deberíamos hacer? ¿Omitirlo, crear un producto genérico "A revisar", o mostrar un error pidiendo crear el producto primero?
> 2. **Integración con la vista de Carga**: ¿Prefieres que este lector de "perfiles" se integre "invisiblemente" en la actual pantalla de "Carga de Compras IA", de modo que si subes la factura de BOWIE mágicamente lea los ítems con el script, y si es otro proveedor caiga al procesamiento de IA estándar? ¿O armamos una pantalla/botón especial aparte? (Recomiendo la primera opción).

## Plan de Verificación
### Automated Tests
- Ejecutar el script aisladamente contra `Modelos/facturas/BOWIE.pdf` para asegurar el dict final.
### Manual Verification
- Ingresar al ERP en la carga de compras.
- Subir el PDF de BOWIE.
- Validar que se autocomplete el proveedor, la fecha, y que la grilla inferior aparezca ya con las cantidades, descripciones e importes unitarios de los 6 ítems listados en la factura de muestra.
