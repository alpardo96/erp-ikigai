# Configuración de Datos de Empresa y Encabezado Dinámico en PDF de Facturas

Este plan describe las modificaciones necesarias para permitir registrar la **Fecha de Inicio de Actividades** y la **Condición de IVA** en la entidad Empresa, exponerlos en su respectivo formulario de edición, y adaptar el servicio de generación de PDFs de facturas para que oculte el logo y los datos del emisor cuando el comprobante sea No Fiscal (`condic=2`).

## User Review Required

> [!IMPORTANT]
> - **Migración de base de datos**: Se añadirá `fecha_inicio_actividades` y `condicion_iva` al modelo `Empresa`. Se generará y ejecutará la migración correspondiente.
> - **Campos dinámicos en facturas**: La lógica de `pdf_service.py` que usaba datos hardcodeados ("RESPONSABLE INSCRIPTO", "01/01/2000") ahora leerá directamente de los nuevos campos de la Empresa activa en la base de datos.
> - **Comportamiento No Fiscal (`condic=2`)**: Si la condición del comprobante es 2 (no fiscal/presupuesto), se enmascarará con color blanco toda la cabecera correspondiente al emisor (logo, nombre, dirección, CUIT, IIBB, Inicio de actividades) en el PDF final para que no se muestren los datos de la empresa emisora.

---

## Proposed Changes

### 1. Módulo Empresas (Modelos y Formularios)

#### [MODIFY] [models.py](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/empresas/models.py)
* Definir `CONDICION_IVA_CHOICES` en el módulo.
* Agregar los campos al modelo `Empresa`:
  - `fecha_inicio_actividades = models.DateField(null=True, blank=True, verbose_name="Fecha de Inicio de Actividades")`
  - `condicion_iva = models.CharField(max_length=50, choices=CONDICION_IVA_CHOICES, default='RESPONSABLE INSCRIPTO', verbose_name="Condición IVA")`

#### [MODIFY] [forms.py](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/empresas/forms.py)
* Incluir `fecha_inicio_actividades` y `condicion_iva` en el formulario `EmpresaForm`.
* Agregar los widgets adecuados (`forms.DateInput(attrs={'type': 'date'})` y `forms.Select`).

#### [MODIFY] [empresa_form.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/configuracion/modals/empresa_form.html)
* Agregar los inputs visuales dentro del grid en el modal de edición de empresa.

---

### 2. Módulo Facturación (Impresión PDF)

#### [MODIFY] [pdf_service.py](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/facturacion/services/pdf_service.py)
* En `generar_pdf_venta(venta_id)`:
  - Validar la condición de la venta (`venta.condic`).
  - **Si `venta.condic == 2` (No Fiscal / Presupuesto / Proyectado)**:
    - Aplicar máscaras blancas (`mask_area`) sobre:
      - El área del logo y cabecera del emisor (`mask_area(55.0, 20.0, 280.0, 133.0)`).
      - El área de CUIT, IIBB e Inicio de actividades a la derecha.
    - **No** dibujar ningún dato del emisor (ni logo, ni textos, ni números fiscales).
  - **Si `venta.condic == 1` (Fiscal)**:
    - Dibujar los datos del emisor como de costumbre, pero reemplazando los valores hardcodeados por los nuevos campos dinámicos:
      - `iva_emisor = empresa.condicion_iva`
      - `inicio_emisor = empresa.fecha_inicio_actividades.strftime('%d/%m/%Y') if empresa.fecha_inicio_actividades else '01/01/2000'`

---

## Verification Plan

### Automated Tests
* Ejecutar un script/test para verificar la migración de base de datos de empresas.
* Validar que la generación de PDF de venta siga funcionando y no lance excepciones tras los cambios de modelos.

### Manual Verification
1. Ir a la edición de la empresa en el ERP.
2. Cargar la **Fecha de Inicio de Actividades** y seleccionar la **Condición IVA**. Guardar los cambios.
3. Generar/visualizar un PDF de un comprobante **Fiscal (`condic=1`)**: verificar que la cabecera muestra el logo y los nuevos datos de IVA e inicio de actividades correctos.
4. Generar/visualizar un PDF de un comprobante **No Fiscal (`condic=2`) / Presupuesto**: verificar que la cabecera está completamente en blanco en cuanto a datos de la empresa emisora y su logo.
