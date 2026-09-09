# Plan 088: Mejoras y Correcciones en Panel de Reservas SIGIMAC

## 1. Objetivos
1. **Búsqueda inteligente multi-criterio y en tiempo real (HTMX)**:
   - Autocompletar/filtrar a medida que el usuario escribe (con debounce de 300ms).
   - Buscar por:
     - **Cliente** (completo): Razón Social, CUIT/DNI, Teléfono, Correo, Domicilio, Contacto.
     - **Producto y Subproducto**: Detalle, Código de Proveedor, Código de Fábrica, Números de Serie y CUIM de subproductos asociados.
     - **Recibo**: Número de Recibo y Observaciones.
     - **Identificadores**: ID de Reserva y Número de Preventa.
   - Búsqueda multi-término compuesta (ej. "Juan Glock" o "2033445566 9mm").
2. **Corrección de selector Estado SIGIMAC**:
   - Ajustar altura y espaciado para que el texto de las opciones largas (ej. *"Pendiente Autorización SIGIMAC"*) no quede cortado en su borde inferior.
3. **Rediseño de Botones de Filtrar y Reiniciar**:
   - Eliminar el colapso visual (manchones negros comprimidos).
   - Diseñar botones accesibles, proporcionales y estéticos acordes al estándar de diseño del ERP.

---

## 2. Archivos Afectados
- `verticalidades/armeria/views.py`: Manejo de solicitudes HTMX (`get_template_names`), búsqueda inteligente multi-token y `.distinct()`.
- `verticalidades/armeria/templates/armeria/reservas_list.html`: Rediseño del formulario de filtros, inputs con triggers HTMX reactivos e indicador de carga.
- `verticalidades/armeria/templates/armeria/partials/reservas_tabla_parcial.html`: Nuevo template parcial para refresco dinámico sin recargar la página.

---

## 3. Pruebas y Validación
- Pruebas automatizadas con Django test runner.
- Verificación visual de los controles de formulario y reactividad HTMX.
