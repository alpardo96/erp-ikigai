# Plan de Implementación - Armado de Facturas de Venta (A4) con Logo y QR

Este plan detalla los pasos para completar la generación y el armado de las facturas de venta en PDF utilizando las plantillas provistas (`Factura A Estudio.pdf`, `Factura B Estudio.pdf` y `Presupuesto X Estudio.pdf`), en tamaño de hoja A4, incorporando el logo dinámico de la empresa emisora, el código QR de AFIP para comprobantes fiscales y el desglose de alícuotas de IVA correspondientes.

## User Review Required

> [!IMPORTANT]
> **Código Legacy de Coordenadas:** Para evitar la fase de prueba y error en el posicionamiento (eje X, Y en milímetros) de todos los campos en la hoja A4 (Cabecera, Datos del Cliente, Detalle de Ítems, Cuadro de IVA y Totales), solicitamos que nos compartas el código legacy de armado que poseas. Esto garantizará que la información calce exactamente en los casilleros de los diseños base PDF.

> [!NOTE]
> **Librería de Generación de QR:** Usaremos la librería `qrcode` (ya presente en `requirements.txt`) para generar la imagen del QR al vuelo en memoria (`io.BytesIO`) y estamparla usando el canvas de ReportLab, evitando crear archivos temporales en el disco.

## Open Questions

> [!WARNING]
> ¿Tienes a disposición el código legacy con el mapeo de coordenadas X e Y para las plantillas `Factura A Estudio.pdf`, `Factura B Estudio.pdf` y `Presupuesto X Estudio.pdf`? Por favor compártelo en tu respuesta para que podamos integrarlo de forma directa y precisa.

## Proposed Changes

A continuación se detallan los archivos a modificar y crear:

---

### Módulo de Facturación (Servicios e Impresión)

#### [MODIFY] [pdf_service.py](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/facturacion/services/pdf_service.py)
* **Logos Dinámicos de Empresa:**
  * Leer `venta.empresa.logo`. Si está presente y el archivo físico existe, cargarlo y dibujarlo en la cabecera izquierda.
  * Si no está cargado en el modelo, se mantendrá un fallback a un logo predeterminado o se dejará en blanco si no hay imagen de respaldo.
* **Integración del Código QR:**
  * Si la venta cuenta con `cod_qr` (o en su defecto si tiene `cae` y se requiere armar el QR), generaremos la matriz de QR utilizando `qrcode.make_image()` en un buffer de memoria `BytesIO`.
  * Dibujaremos la imagen en las coordenadas correspondientes del pie del comprobante (abajo a la izquierda).
* **Desglose de IVA en Facturas A (Código '001'):**
  * Recuperar las alícuotas asociadas a través de `venta.alicuotas_iva.all()`.
  * Filtrar y mostrar únicamente aquellas alícuotas donde `base_imponible > 0` o `importe_iva > 0` (evitando imprimir tasas en cero).
  * Dibujar este desglose de IVA de forma estructurada en la sección del pie de la Factura A.
* **Detalle de Ítems e Importes:**
  * Dibujar los ítems (`VentaItem`) respetando el límite de renglones por página.
  * Darle formato argentino (`$ XX.XXX,XX`) a los precios unitarios, netos, IVAs y totales.
  * Mostrar las leyendas de CAE y Vencimiento de CAE en los comprobantes fiscales correspondientes.

#### [MODIFY] [venta_previsualizar_modal.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/facturacion/partials/venta_previsualizar_modal.html)
* **Botón de Impresión:**
  * Añadir un botón o enlace para imprimir/descargar el PDF de la factura:
    ```html
    <a href="{% url 'imprimir_factura' venta.ventas_id %}" target="_blank" class="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-black rounded-lg uppercase tracking-widest shadow transition-colors flex items-center gap-1.5 mr-2">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"></path></svg>
        Imprimir
    </a>
    ```

#### [MODIFY] [ventas_listado.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/facturacion/ventas_listado.html)
* **Acción de Impresión Directa:**
  * Agregar una acción adicional de impresión directa en la grilla de ventas (columna de Acciones), representada por un ícono de impresora o un botón compacto "PDF / Imprimir" que redirija a `{% url 'imprimir_factura' v.ventas_id %}` en una pestaña nueva (`target="_blank"`).

---

## Verification Plan

### Automated Tests
* Ejecución de pruebas del módulo de facturación para verificar que no se rompan las consultas de alícuotas ni los flujos existentes:
  ```bash
  python manage.py test facturacion.tests
  ```

### Manual Verification
1. Registrar una Factura A, una Factura B y un Presupuesto X.
2. Ingresar al listado de ventas y presionar el botón de previsualizar y el de impresión directa.
3. Verificar que el PDF generado en hoja A4 tenga:
   * El logo de la empresa cargado en el modelo de Empresa (o en su defecto el fallback).
   * El código QR calzando en el casillero correspondiente (solo para Factura A y B, no para Presupuesto X).
   * El desglose de alícuotas de IVA solo para aquellas que posean importes (en Factura A).
   * Datos del cliente, ítems, totales y CAE/Vencimiento perfectamente posicionados.
