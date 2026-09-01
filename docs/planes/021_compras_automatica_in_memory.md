# Centralización In-Memory del Motor de Extracción de Facturas

Este plan describe la arquitectura para centralizar el motor de extracción y reconocimiento óptico (OCR) de facturas en compras, operando completamente en memoria. Esto evita generar basura en el disco duro o colapsar el almacenamiento de sesión de Django. Además, incluye la limpieza del formato numérico (tratamiento de decimales y miles) para guardar montos "puros" (como tipos float o Decimal) listos para la base de datos.

## User Review Required

> [!WARNING]
> La arquitectura cambia de **"subir -> guardar -> extraer_IA -> crop_manual_con_coordenadas"** a **"subir -> extraer todo en memoria y devolver Base64 de imagen y datos -> crop_manual_desde_el_frontend_con_Base64"**.
> 
> Para el recorte manual (Mapeo Manual), el frontend extraerá el pedacito de la imagen seleccionada utilizando Canvas y enviará un string Base64 del recorte directamente al backend, quien aplicará Tesseract OCR y devolverá el texto. Esto significa que el backend **no necesita recordar ni guardar en disco/sesión la factura original en ningún momento**.
> ¿Estás de acuerdo con este enfoque puramente in-memory?

## Proposed Changes

---

### `facturacion/services/extractor_facturas.py`
Se centralizará la lógica para que el motor trabaje directamente con bytes (streams), evitando paths de archivos.
- [MODIFY] `extractor_facturas.py`
  - Se añadirá una función `parse_monto(texto)` que tomará valores sucios (ej: `$ 12.345,67` o `12345.67`) y los convertirá a floats limpios (ej: `12345.67`) analizando el último separador (, o .).
  - Se actualizará `extraccion_inteligente_afip` para recibir `file_bytes` y trabajar de forma puramente in-memory utilizando `fitz.open(stream=file_bytes, filetype="pdf")`. Aplicará `parse_monto` a campos `total`, `iva` y `neto`.
  - Se creará una función integradora `procesar_factura_memoria(file_bytes, is_pdf)` que retornará los datos extraídos y la primera página renderizada como un string en **Base64** (`data:image/png;base64,...`).
  - Se creará `procesar_recorte_memoria(image_base64)` que usará PIL y Tesseract para leer directamente el recorte enviado por el usuario.

---

### `facturacion/views_procesamiento.py`
Se adaptarán las vistas para actuar como un intermediario sin estado (stateless).
- [MODIFY] `views_procesamiento.py`
  - `CargaCompraAutomaticaView.post`: Leerá el `.read()` del archivo subido. Llamará a `procesar_factura_memoria`. Retornará un JSON unificado con la imagen (en Base64) y los datos extraídos. No guardará nada en `FileSystemStorage` ni en `request.session`.
  - `ProcesarRecorteOCRView.post`: Ya no buscará el archivo en el disco usando coordenadas. Recibirá un campo `image_crop` (Base64) en el JSON body y lo procesará en el momento.
  - [DELETE] Se eliminará la clase `ExtraccionInteligenteView`, ya que el análisis afip in-memory se realiza íntegramente y en paralelo dentro de `CargaCompraAutomaticaView`.

---

### `config/urls.py`
Se eliminará el ruteo muerto.
- [MODIFY] `urls.py`
  - Se removerá el path de `facturacion/compras/extraccion-inteligente/`.

---

### `templates/facturacion/carga_compra_automatica.html`
Se actualizará la lógica Alpine.js para integrarse con la API de memoria.
- [MODIFY] `carga_compra_automatica.html`
  - `handleFileSelected()` poblará `this.extracciones` y `this.imageUrl` directamente desde la respuesta inicial unificada. Ya no encadenará una segunda llamada al backend.
  - En `procesarRecorte()`, en lugar de mandar coordenadas, se creará un canvas temporal en memoria (`document.createElement('canvas')`), se dibujará el área recortada y se enviará `canvas.toDataURL('image/png')` al backend para obtener el OCR manual de esa zona.

## Verification Plan

### Manual Verification
1. Ingresar a Carga Automática de Compras y subir un PDF de una Factura A o C.
2. Comprobar que la vista cargue instantáneamente los datos, incluyendo el formato numérico (montos limpios como `12345.67`) listos para DB.
3. Trazar en Mapeo Manual un rectángulo y verificar que el recorte OCR devuelva los datos sin fallos, a pesar de que no se guardó el PDF en disco.
4. Revisar la carpeta de `media/` o carpetas temporales para garantizar que **no** se están almacenando archivos residuales en el disco duro.
