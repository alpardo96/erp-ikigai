# Integración de Motor IA (Google Gemini) para Lectura de Facturas de Compras

## Descripción

Agregar un **tercer motor de extracción** basado en **Google Gemini (gemini-2.5-flash)** al lector de facturas de compras existente. El motor actual (regex AFIP + Tesseract OCR) se mantiene intacto. Gemini actúa como motor complementario que puede leer **cualquier tipo de factura** (PDF con texto, imágenes escaneadas, fotos de celular, formatos no-AFIP) y devolver datos estructurados con alta precisión.

## Arquitectura de Motores (Cascada)

```
Factura subida por el usuario
    │
    ├─ Motor 1: Extracción AFIP (regex sobre texto PDF) → GRATIS, instantáneo
    │   └─ Si extrajo ≥3 campos → se muestran al usuario
    │
    ├─ Motor 2: Gemini AI (API) → Se invoca automáticamente si Motor 1 no alcanzó
    │   └─ Envía imagen/PDF a Gemini → respuesta JSON estructurada
    │
    └─ Motor 3: Tesseract OCR (mapeo manual) → Siempre disponible como fallback
        └─ El usuario dibuja rectángulos para extraer texto zona por zona
```

> [!IMPORTANT]
> La API Key de Gemini ya está configurada en `.env` como `GEMINI_API_KEY`. El tier gratuito permite 15 RPM y 1M tokens/día, más que suficiente para uso ERP.

## Cambios Propuestos

---

### Dependencia Python

#### [MODIFY] [requirements.txt](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/requirements.txt)
- Agregar `google-genai` como nueva dependencia (SDK oficial unificado de Google).
- Agregar `pydantic` (probablemente ya instalada como sub-dependencia, pero la explicitamos).

---

### Nuevo Servicio de Extracción por IA

#### [NEW] [extractor_ia.py](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/facturacion/services/extractor_ia.py)

Nuevo módulo con la función `extraccion_gemini(file_bytes, filename)` que:

1. **Configura el cliente** Gemini usando la key del `.env` (`os.getenv('GEMINI_API_KEY')`).
2. **Define un schema Pydantic** `DatosFactura` con los campos que ya usamos:
   - `cuit: str` (CUIT del proveedor, solo dígitos)
   - `fecha: str` (formato DD/MM/YYYY)
   - `tipo: str` (letra A, B, C, M)
   - `punto: str` (punto de venta)
   - `numero: str` (número de comprobante)
   - `neto: float` (importe neto gravado)
   - `iva: float` (total IVA)
   - `total: float` (total de la factura)
3. **Envía la imagen** (convertida de bytes a PIL Image) junto con un prompt en español diseñado para facturas argentinas:
   ```
   "Sos un extractor de datos de facturas argentinas. Analizá esta imagen de factura
   y devolvé los datos en el formato JSON solicitado. Si un campo no es visible o
   legible, dejalo vacío o en 0. El CUIT debe tener solo dígitos (11 caracteres).
   La fecha debe estar en formato DD/MM/YYYY."
   ```
4. **Usa `response_mime_type='application/json'`** y `response_schema=DatosFactura` para que Gemini devuelva JSON estructurado directamente.
5. **Retorna un diccionario** con el mismo formato que usa `extraccion_inteligente_afip_doc()` para compatibilidad directa.
6. **Maneja errores** (API key faltante, timeout, rate limit) devolviendo `None`.

---

### Modificación del Servicio Existente (Orquestación)

#### [MODIFY] [extractor_facturas.py](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/facturacion/services/extractor_facturas.py)

Cambios mínimos en `procesar_factura_memoria()`:
- Se agrega un parámetro opcional `motor='auto'` que acepta `'auto'`, `'regex'`, `'ia'`.
- Si `motor='auto'`:
  1. Primero ejecuta `extraccion_inteligente_afip_doc()` (regex).
  2. Si extrajo menos de 3 campos con valor, intenta `extraccion_gemini()`.
- Si `motor='regex'`: solo ejecuta el motor regex actual.
- Si `motor='ia'`: solo ejecuta Gemini directamente.
- El resultado incluye un campo `motor_usado: str` para que el frontend muestre qué motor procesó.

> [!NOTE]
> El código actual de `extractor_facturas.py` **no se modifica ni se rompe**. Solo se agrega el import del nuevo módulo y la lógica de fallback en `procesar_factura_memoria()`.

---

### Modificación de la Vista

#### [MODIFY] [views_procesamiento.py](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/facturacion/views_procesamiento.py)

- `CargaCompraAutomaticaView.post`: Lee un parámetro opcional `motor` del FormData (default: `'auto'`). Lo pasa a `procesar_factura_memoria(file_bytes, filename, motor=motor)`.
- La respuesta JSON ahora incluye `motor_usado` para que el frontend lo muestre.

---

### Modificación del Frontend

#### [MODIFY] [carga_compra_automatica.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/facturacion/carga_compra_automatica.html)

Cambios en la toolbar superior y la lógica Alpine.js:

1. **Nuevo botón en la toolbar**: Se agrega un tercer botón "🤖 Gemini IA" en la barra de herramientas superior junto a "Carga Inteligente" y "Mapeo Manual". Permite re-procesar la factura con el motor IA si el regex no fue suficiente.
2. **Variable `motorSeleccionado`**: Nueva variable Alpine (`'auto'`, `'regex'`, `'ia'`).
3. **Función `reprocesarConIA()`**: Botón que re-envía la factura al backend forzando `motor=ia`.
4. **Badge del motor usado**: Un chip/badge pequeño debajo del título "Datos Extraídos" que muestra "Procesado con: Regex AFIP" o "Procesado con: Gemini IA" según la respuesta.
5. **Estado visual de API Key**: Si Gemini falla por falta de key, muestra un toast informativo.

---

### Configuración (Settings)

#### [MODIFY] [settings.py](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/config/settings.py)

- Agregar la lectura de `GEMINI_API_KEY` desde las variables de entorno:
  ```python
  GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
  ```

---

## Plan de Verificación

### Verificación Manual
1. **Sin Gemini (solo regex)**: Subir un PDF AFIP estándar → debe funcionar igual que antes, sin cambios.
2. **Con Gemini**: Subir una imagen/foto de factura que no tiene texto embebido → debe extraer los datos vía IA.
3. **Fallback auto**: Subir un PDF con formato no-AFIP → el regex no encuentra nada → Gemini se activa automáticamente.
4. **Sin API Key**: Borrar la key del `.env` → el sistema sigue funcionando con regex + Tesseract, sin errores.
5. **Botón re-procesar**: Con un PDF ya cargado, presionar "Gemini IA" → re-envía al backend con `motor=ia`.

### Test de Regresión
- Verificar que los tests existentes de facturación (`test_totales.py`) sigan pasando sin cambios.
