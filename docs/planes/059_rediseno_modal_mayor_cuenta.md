# Plan 059: Rediseño del Modal Mayor General de Cuenta

Se propone un rediseño UI/UX y ajuste de configuración en el modal **Mayor General de Cuenta** que se abre desde el informe de **Saldos Mensuales** (y el panel contable). El objetivo es solucionar los inconvenientes de visualización denunciados, agregando scroll horizontal, encabezado fijo (sticky header), mayor ancho para el modal y ajustando las 7 columnas predeterminadas indicadas por el usuario.

## Requerimientos a Resolver

1. **Scroll Horizontal**: Permitir desplazamiento horizontal cuando el ancho acumulado de las columnas exceda la pantalla o contenedor.
2. **Sticky Header**: Mantener visible el encabezado de las columnas (`<thead>`) al realizar scroll vertical por los movimientos.
3. **Modal más Ancho**: Expandir las dimensiones del modal (de `max-w-5xl` a `max-w-7xl w-11/12`) para aprovechar mejor la pantalla en laptops y monitores.
4. **Columnas Predeterminadas**: Establecer como predeterminadas únicamente las 7 columnas solicitadas:
   - `ID Asiento` (`asiento_id`)
   - `Fecha` (`fecha`)
   - `Concepto` (`concepto`)
   - `Debe` (`debe`)
   - `Haber` (`haber`)
   - `Saldo` (`saldo`)
   - `Condición` (`condic`)

---

## User Review Required

> [!NOTE]
> El cambio en las columnas predeterminadas modificará los valores por defecto del catálogo de columnas del Mayor General (`COLUMNAS_MAYOR_CATALOGO`). Las columnas `ID Cuenta`, `Nombre Cuenta` y `Sucursal` se desmarcarán del valor predeterminado por defecto, pero seguirán estando disponibles en el menú desplegable "Columnas" por si se desean incluir en cualquier momento.

---

## Proposed Changes

### Módulo Contable Services

#### [MODIFY] [reportes_mayor.py](file:///d:/JM_Soft/erp-ikigai-2/contable/services/reportes_mayor.py)
- Actualizar `COLUMNAS_MAYOR_CATALOGO`:
  - `asiento_id`: `default = True`
  - `fecha`: `default = True`
  - `concepto`: `default = True`
  - `debe`: `default = True`
  - `haber`: `default = True`
  - `saldo`: `default = True`
  - `condic`: `default = True`
  - `cuenta_id`: cambiar a `default = False`
  - `cuenta`: cambiar a `default = False`
  - `sucursal`: cambiar a `default = False`

---

### Plantillas HTML (Templates)

#### [MODIFY] [mayor_cuenta_modal.html](file:///d:/JM_Soft/erp-ikigai-2/templates/contable/modals/mayor_cuenta_modal.html)
- Cambiar la clase de tamaño contenedor de `max-w-5xl` a `w-11/12 max-w-7xl` para agrandar el modal.
- Modificar el contenedor de la grilla de datos para habilitar desplazamiento horizontal (`overflow-x-auto`) y scroll vertical de altura controlada (`overflow-y-auto max-h-[calc(85vh-220px)]`).
- Agregar las clases `sticky top-0 z-20 bg-slate-100 shadow-sm border-b border-slate-200` a las celdas de encabezado `<th>` en la tabla estática por defecto.
- Ajustar la cabecera por defecto para incluir las 7 columnas solicitadas: ID Asiento, Fecha, Concepto, Debe, Haber, Saldo y Condición.

#### [MODIFY] [libro_mayor_rows.html](file:///d:/JM_Soft/erp-ikigai-2/templates/contable/partials/libro_mayor_rows.html)
- Agregar `whitespace-nowrap` a las celdas `<td>` de la grilla para evitar repliegues verticales de texto y garantizar que se muestre con scroll horizontal fluido.
- Actualizar la función JavaScript `renderThead` para que agregue las clases `sticky top-0 z-20 bg-slate-100 shadow-sm border-b border-slate-200 whitespace-nowrap` en los elementos `<th>` generados dinámicamente según las columnas elegidas por el usuario.

---

## Verification Plan

### Automated Tests
- Ejecutar el conjunto de pruebas del libro mayor y saldos mensuales:
  ```powershell
  python manage.py test contable.tests.test_libro_mayor_columnas contable.tests.test_saldos_mensuales_vistas
  ```

### Manual Verification
- Ingresar al módulo **Saldos Mensuales**.
- Hacer clic en un importe del reporte para abrir el modal **Mayor General de Cuenta**.
- Verificar:
  1. Que el modal abra en tamaño ancho (`max-w-7xl`).
  2. Que las columnas predeterminadas visibles sean exactamente: ID Asiento, Fecha, Concepto, Debe, Haber, Saldo y Condición.
  3. Que al hacer scroll vertical en movimientos extensos, la fila de encabezados se mantenga fija (`sticky`).
  4. Que si se añaden más columnas desde el selector "Columnas", aparezca la barra de desplazamiento horizontal y permita desplazarse cómodamente sin romper el diseño.
