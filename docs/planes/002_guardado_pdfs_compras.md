# Optimización de Procesamiento OCR y Archivo Físico de Compras

El objetivo de este plan es resolver el congelamiento de la PC/Navegador que ocurre al cargar PDFs pesados en la Carga Automática, y añadir la funcionalidad de almacenar y relacionar el comprobante original en formato PDF con la carga de la Compra final, para poder visualizarlo desde el Listado de Compras.

## Problema Actual
El motor OCR lee el PDF, extrae la primera página y la convierte a un string gigante en formato `Base64`. Este string inmenso (puede pesar megabytes) viaja en el JSON de respuesta y el navegador intenta renderizarlo en el DOM, lo cual satura la RAM del navegador (Chrome/Edge) y congela la pestaña. Además, el PDF original se descarta de la memoria y se pierde una vez que se carga la factura.

## Proposed Changes

### 1. Configuración Global (Media)
Habilitar el manejo de archivos multimedia (`/media/`) en Django para almacenar los PDFs originales de forma segura.

#### [MODIFY] config/settings.py
- Definir `MEDIA_URL = '/media/'` y `MEDIA_ROOT = BASE_DIR / 'media'`.

#### [MODIFY] config/urls.py
- Agregar las rutas para servir los archivos de `/media/` en entorno local.

### 2. Actualización de Base de Datos y Lógica de Negocio
#### [MODIFY] facturacion/models.py
- Agregar el campo `archivo_pdf = models.FileField(upload_to=custom_upload_to, null=True, blank=True)` al modelo `Compra`.
- Crear una función `custom_upload_to` que resuelva la ruta final a `media/<empresa_id>/<proveedor_id>/<filename>`.
- *Nota: Requerirá ejecutar `makemigrations` y `migrate`.*

### 3. Backend de Extracción (OCR)
#### [MODIFY] facturacion/services/extractor_facturas.py
- Refactorizar la función de extracción para que guarde un PNG de vista previa temporal físicamente en lugar de generar un Base64 en memoria.
- Retornar las rutas temporales del archivo.

#### [MODIFY] facturacion/views_procesamiento.py
- En la vista `CargaCompraAutomaticaView`, al recibir el PDF, guardarlo inmediatamente en una carpeta temporal (`media/temp_facturas/`).
- Enviar al frontend la URL del PNG generado y el "Path" temporal del PDF original.

### 4. Interfaz Frontend
#### [MODIFY] templates/facturacion/carga_compra_automatica.html
- Renderizar la imagen usando el atributo normal `src="/media/temp_facturas/preview.png"` en lugar de saturar el DOM con Base64.
- Guardar la ruta temporal del PDF original en el `sessionStorage`.

#### [MODIFY] templates/facturacion/compras_carga.html
- Agregar un campo oculto `<input type="hidden" name="pdf_temp_path" id="id_pdf_temp_path">`.
- Capturar la ruta temporal desde el `sessionStorage` y enviarla por POST al guardar la compra.

### 5. Finalización, Validación y Listado
#### [MODIFY] facturacion/views.py (ComprasCargaView)
- **Bloqueo de Duplicados (NUEVO)**: En el `post`, antes de guardar, verificar si ya existe una `Compra` con exactamente la misma combinación de `empresa`, `proveedor`, `punto` (punto de venta) y `numero` (nro de factura). Si existe, detener el proceso y mostrar un mensaje de error ("Esta factura ya fue cargada en el sistema").
- Al crear y persistir el objeto `Compra`, detectar si viene el `pdf_temp_path`.
- De ser así, trasladar el PDF desde la carpeta temporal hacia su destino final (la ruta definida dinámicamente con `<empresa_id>/<proveedor_id>/`).
- Eliminar los archivos temporales (PDF y PNG).

#### [MODIFY] templates/facturacion/compras_listado.html
- Añadir un ícono o botón en la columna de Acciones para abrir el PDF (en nueva pestaña) **únicamente** de las compras que tengan dicho archivo adjunto.

## User Review Required

> [!IMPORTANT]
> **Migraciones de Base de Datos**: Como vamos a agregar la columna `archivo_pdf` a la tabla de `Compras`, esto alterará la base de datos.
>
> **Rendimiento**: Este cambio evitará categóricamente el cuelgue en el navegador, ya que las imágenes no cargarán la RAM en crudo, sino que serán tratadas como cualquier otra imagen web estándar servida en disco.

¿Estás de acuerdo con avanzar con este plan arquitectónico?
