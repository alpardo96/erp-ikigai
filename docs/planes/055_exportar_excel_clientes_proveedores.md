# Plan 055: Botón de Exportación a Excel en Clientes y Proveedores

Fecha: 2026-08-18

El objetivo de este plan es incorporar la funcionalidad de descarga en formato Excel (`.xlsx`) en el listado principal de **Clientes y Proveedores** (`/clientes/`). 

Actualmente, el listado en pantalla está paginado/limitado a 50 registros por motivos de rendimiento y la vista solo muestra ciertas columnas según las preferencias del usuario. La nueva exportación generará un archivo Excel completo con **todos los campos/columnas de la entidad** (`ClienteProveedor`), incluyendo los datos de contacto, fiscales, ubicaciones, clasificaciones y cuentas, respetando los filtros activos de búsqueda (`q` para razón social/CUIT y `tipo` para Cliente/Proveedor) pero **sin truncar el resultado a 50 filas**.

---

## User Review Required

> [!IMPORTANT]
> **Campos Incluidos en el Excel (25 columnas):**
> 1. ID (`codigo_id`)
> 2. Razón Social (`razon_social`)
> 3. Tipo de Entidad (Cliente / Proveedor)
> 4. Tipo Documento (`tipo_documento`)
> 5. CUIT / DNI (`cuit`)
> 6. Fecha de Nacimiento (`fecha_nacimiento`)
> 7. Domicilio (`domicilio`)
> 8. C. Postal (`codigo_postal`)
> 9. Localidad (`localidad`)
> 10. Provincia / Jurisdicción (`jurisdiccion`)
> 11. Contacto (`contacto`)
> 12. Teléfono (`telefono`)
> 13. Correo (`correo`)
> 14. Condición IVA (`condicion_iva`)
> 15. Ingresos Brutos (`tipo_iibb`)
> 16. Saldo Inicial (`saldo_inicial`)
> 17. Saldo Actual (`saldo`)
> 18. Límite de Crédito (`limite`)
> 19. Objetivo Mensual (`objetivo_mensual`)
> 20. Clasificación (`clasificacion`)
> 21. Exige Orden Compra (`usa_orden_compra`)
> 22. Cta Patrimonial (`cta_pat`)
> 23. Cta Resultado (`cta_res`)
> 24. Código Anterior (`codigo_anterior`)
> 25. Observaciones (`observaciones`)

> [!NOTE]
> La exportación a Excel respetará los filtros de búsqueda ingresados en la pantalla (`q` y `tipo`), pero **no truncará la lista a 50 registros** como lo hace la grilla HTML, permitiendo obtener el 100% de las entidades que coincidan con la búsqueda.

---

## Open Questions

*No se detectan preguntas abiertas. La especificación cubre el requerimiento funcional exacto planteado.*

---

## Proposed Changes

### Módulo Facturación (Servicio, Vista, Plantilla y URLs)

#### [NEW] [clientes_excel.py](file:///d:/JM_Soft/erp-ikigai-2/facturacion/services/clientes_excel.py)
- Módulo encargado de recibir el queryset de `ClienteProveedor`, construir el libro de trabajo con `openpyxl`, aplicar estilos profesionales (encabezados en azul slate-900, fuentes legibles, bordes, formatos numéricos y de fecha) y devolver la respuesta HTTP de descarga `.xlsx`.

#### [MODIFY] [views_reportes.py](file:///d:/JM_Soft/erp-ikigai-2/facturacion/views_reportes.py) (o `views_htmx.py`)
- Agregar la función vista `@login_required exportar_clientes_excel(request)`:
  - Recupera `empresa_id` de la sesión.
  - Lee parámetros GET `q` y `tipo`.
  - Construye el filtro de base de datos (`Q(razon_social__icontains=q) | Q(cuit__icontains=q)` y `tipo_entidad=tipo`).
  - Consulta los clientes/proveedores ordenados por `razon_social` (con `select_related('jurisdiccion')`), sin limitar a 50.
  - Llama a `exportar_clientes_excel(clientes, empresa, filtros)`.

#### [MODIFY] [urls.py](file:///d:/JM_Soft/erp-ikigai-2/config/urls.py)
- Registrar la ruta `path('clientes/exportar-excel/', exportar_clientes_excel, name='clientes_exportar_excel')`.

#### [MODIFY] [clientes_index.html](file:///d:/JM_Soft/erp-ikigai-2/templates/facturacion/clientes_index.html)
- Agregar un botón **"Exportar Excel"** verde estilizado en el encabezado principal de la página.
- Agregar la función JavaScript `exportarExcel()` que lee los valores actuales de `name="q"` y `name="tipo"` y redirige a la URL de exportación para iniciar la descarga.

---

## Verification Plan

### Pruebas Automatizadas
- Crear un test unitario en `facturacion/tests/test_exportar_clientes_excel.py` para verificar que la vista responda con `status_code == 200`, el `Content-Type` de spreadsheet de openpyxl y contenga los datos esperados de los clientes.
- Ejecutar los tests con `py manage.py test facturacion.tests.test_exportar_clientes_excel`.

### Verificación Manual
1. Ingresar al panel de **Clientes y Proveedores** (`http://127.0.0.1:8000/clientes/`).
2. Probar presionar el botón **"Exportar Excel"** directamente sin filtros. Verificar que descargue un archivo `.xlsx` con todas las columnas y todos los registros de la empresa.
3. Probar filtrar por tipo (ej. sólo "Proveedores") o por texto (ej. razón social parcial) y presionar **"Exportar Excel"**. Verificar que el archivo generado respete el filtro pero incluya todos los resultados coincidentes y con todas las 25 columnas solicitadas.
