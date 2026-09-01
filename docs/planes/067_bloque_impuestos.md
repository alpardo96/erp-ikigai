# Plan de Implementación: Nuevo Bloque del Menú Principal "Impuestos"

Este plan detalla los cambios necesarios para integrar la nueva sección de **Impuestos** en el menú principal (barra lateral navegable) del ERP Ikigai 2, ofreciendo acceso directo a sus 5 procesos y reportes impositivos fundamentales.

---

## 📌 Objetivos y Alcance

1. **Nueva App / Módulo `impuestos`**: Crear y registrar el paquete de Django `impuestos` para agrupar de forma limpia la lógica de ruteo, vistas y plantillas de la gestión fiscal del ERP.
2. **Nuevo Bloque en el Menú Principal (Sidebar)**: Agregar la sección **Impuestos** en `templates/base.html`, con un diseño de menú desplegable (acordeón interactivo mediante Alpine.js) con icono distintivo (`fa-receipt` / `fa-file-invoice-dollar` o SVG dedicado), activo si la ruta coincide con `/impuestos/`.
3. **Dashboard Principal de Impuestos (`/impuestos/`)**: Desarrollar la vista e interfaz de aterrizaje con tarjetas dinámicas con estilo premium en Tailwind CSS para navegar rápidamente a cada subproceso.
4. **Subpáginas y Vistas para los 5 Procesos / Reportes**:
   - 1. **Cierre Periodo IVA** (`/impuestos/cierre-periodo-iva/`) -> `impuestos:cierre_periodo_iva`
   - 2. **Libro IVA Ventas - Portal IVA** (`/impuestos/libro-iva-ventas/`) -> `impuestos:libro_iva_ventas`
   - 3. **Libro IVA Compras - Portal IVA** (`/impuestos/libro-iva-compras/`) -> `impuestos:libro_iva_compras`
   - 4. **Captura Mis Comprobantes ARCA** (`/impuestos/mis-comprobantes-arca/`) -> `impuestos:mis_comprobantes_arca`
   - 5. **SICORE - Retención Impuesto a las Ganancias** (`/impuestos/sicore-ganancias/`) -> `impuestos:sicore_ganancias`

---

## 🛠️ Arquitectura y Modificaciones Propuestas

### 1. Módulo Django `impuestos`
- **[NEW] `impuestos/__init__.py`**
- **[NEW] `impuestos/apps.py`**: Configuración de `ImpuestosConfig(AppConfig)`.
- **[NEW] `impuestos/urls.py`**: Definición del ruteo con `app_name = 'impuestos'`.
- **[NEW] `impuestos/views.py`**: Vistas de clase (`LoginRequiredMixin`, `TemplateView`) para:
  - `ImpuestosIndexView` (`index.html`)
  - `CierrePeriodoIvaView` (`cierre_periodo_iva.html`)
  - `LibroIvaVentasView` (`libro_iva_ventas.html`)
  - `LibroIvaComprasView` (`libro_iva_compras.html`)
  - `MisComprobantesArcaView` (`mis_comprobantes_arca.html`)
  - `SicoreGananciasView` (`sicore_ganancias.html`)

### 2. Registro Global de la App y URLs
- **[MODIFY] `config/settings.py`**: Agregar `'impuestos'` a `INSTALLED_APPS`.
- **[MODIFY] `config/urls.py`**: Incluir las rutas del módulo en `path('impuestos/', include('impuestos.urls'))`.

### 3. Menú Lateral de Navegación
- **[MODIFY] `templates/base.html`**:
  - Insertar el nuevo acordeón desplegable **Impuestos** en la barra lateral debajo del módulo Contable / Tesorería.
  - Configurar las directivas de Alpine.js: `x-data="{ open: window.location.pathname.startsWith('/impuestos/') }"` para mantener el menú desplegado cuando se navega dentro del módulo.
  - Agregar los 5 enlaces con resaltado activo según el `request.resolver_match`.

### 4. Interfaces Visuales (Templates HTML)
- **[NEW] `templates/impuestos/index.html`**: Panel central de control de Impuestos con 5 tarjetas principales estilizadas con degradados y micro-interacciones hover.
- **[NEW] `templates/impuestos/cierre_periodo_iva.html`**: Pantalla para la liquidación mensual y cierre del periodo de IVA.
- **[NEW] `templates/impuestos/libro_iva_ventas.html`**: Pantalla para exportación y emisión del Libro IVA Ventas para Digital Portal IVA (ARCA).
- **[NEW] `templates/impuestos/libro_iva_compras.html`**: Pantalla para exportación y emisión del Libro IVA Compras para Digital Portal IVA (ARCA).
- **[NEW] `templates/impuestos/mis-comprobantes-arca.html`**: Interfaz para importación y conciliación masiva desde Mis Comprobantes ARCA.
- **[NEW] `templates/impuestos/sicore_ganancias.html`**: Pantalla de generación de archivos de retenciones practicadas SICORE - Impuesto a las Ganancias (RG 830).

---

## 📋 Plan de Verificación

### Pruebas Automatizadas y Sintácticas
- Ejecutar `python manage.py check` para verificar que la app `impuestos` e `urls.py` estén correctamente importados sin conflictos ni errores de sintaxis.

### Verificación Manual en Navegador
1. Iniciar/verificar el servidor de desarrollo `python manage.py runserver`.
2. Ingresar al sistema y constatar que en la barra lateral izquierda aparece la nueva opción **Impuestos** con su correspondiente icono.
3. Desplegar el menú y verificar que se visualicen adecuadamente las 5 opciones:
   - Cierre Periodo IVA
   - Libro IVA Ventas - Portal IVA
   - Libro IVA Compras - Portal IVA
   - Captura Mis Comprobantes ARCA
   - SICORE - Retencion Impuesto a las Ganancias
4. Navegar a cada uno de los enlaces comprobando la correcta renderización de cada vista y el mantenimiento del estado desplegado del menú lateral.
