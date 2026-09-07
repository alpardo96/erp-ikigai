# Múltiples Ajustes y Migración Contable (Armería)

El objetivo de este plan es resolver las tareas listadas, abarcando desde correcciones de interfaz (UI) hasta la migración de asientos contables históricos para la vertical de Armería.

> [!IMPORTANT]
> **User Review Required**
> Por favor, revisá la sección de **Open Questions** antes de aprobar, ya que "Reservas SIGIMAC" y "TIPO DOC. Comercio" son requerimientos muy amplios y necesito confirmar el alcance exacto.

## Open Questions

1. **Libro IVA y Contable:** El script de migración para Contabilidad (Asientos, ASTO_ENCABEZADO, ASTO_MOV) fue creado previamente sólo para el módulo "estudio". ¿Deseas que adapte y ejecute ese script para migrar los asientos históricos de **Armería** (`06_migrar_asientos_armeria.py`) con la base de datos de FoxPro?
2. **Reservas de Armas SIGIMAC:** Toda la lógica, modelos, e interfaces de SIGIMAC y Reservas **ya fueron implementadas** en el módulo `verticalidades/armeria`. ¿Te referís a que debo crear un script para migrar datos históricos de Reservas desde FoxPro, o hay alguna funcionalidad específica que falte habilitar/enlazar en la interfaz actual?
3. **TIPO DOC. Comercio para CLIPRO:** Las columnas de `contacto`, `telefono`, `correo`, `IIBB` y `Tipo Doc` ya existen en el listado de Clientes y Proveedores (podes verlas en el botón "Columnas"). Las que sí faltan son `es_policia`, `CLU` y `VTO CLU`. Sobre "TIPO DOC. Comercio", ¿te referís simplemente a mostrar la columna "Tipo Doc", o querés que añada una nueva opción de documento llamada "Comercio" en el formulario de creación?

## Proposed Changes

---

### Facturación (UI)

#### [MODIFY] [facturas_pendientes.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai/templates/facturacion/reportes/facturas_pendientes.html)
- Ajustar las clases de Tailwind del `<select name="estado">`. El recorte de texto en Chrome para Windows suele deberse a alturas fijas (`h-9`) combinadas con paddings internos (`px-2`). Se cambiará a un espaciado más flexible (`py-1.5` o removiendo la altura fija) para que el dropdown renderice bien en todos los navegadores.

#### [MODIFY] [clientes_index.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai/templates/facturacion/clientes_index.html)
- Añadir los checkboxes para controlar la visibilidad de las nuevas columnas: `es_policia`, `CLU`, y `VTO CLU` dentro del menú "Columnas".
- Añadir las etiquetas `<th>` correspondientes a la tabla `tabla-clientes` con soporte para el `hook_ui` de Armería o directamente en la plantilla base (verificando la verticalidad activa).
- Asegurar que `contacto`, `telefono`, `correo`, `IIBB` y `Tipo Doc` (que ya existen) queden visibles u organizadas de la forma que solicitaste.

#### [MODIFY] [cliente_table_rows.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai/templates/facturacion/partials/cliente_table_rows.html)
- Incorporar los tags `<td>` para imprimir los valores de la extensión Armería: `cliente.armeria.es_policia` (mostrando un ícono o "Sí/No"), `cliente.armeria.clu`, y `cliente.armeria.clu_vto`.

---

### Migración y Contabilidad (Armería)

#### [NEW] [06_migrar_asientos_armeria.py](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai/migracion/scripts/armeria/06_migrar_asientos_armeria.py)
- Crear el script que leerá `asto_enc.dbf` y `asto_mov.dbf` desde los directorios de migración de Armería.
- Migrar e insertar los datos en los modelos `Asiento` y `AsientoLinea` (`cble_asiento_enc` y `cble_asiento_mov`), manteniendo la validación estricta de partida doble matemática (`debe = haber`).

## Verification Plan

### Automated Tests
- Validar mediante el comando `python manage.py check` que los templates y plantillas compilen sin errores.

### Manual Verification
- Iniciar el servidor local (`python manage.py runserver`).
- Entrar al listado de Facturas Pendientes desde Chrome y verificar que el select de Estado se renderiza correctamente sin cortar las letras por la mitad.
- Ingresar al listado de Clientes y verificar que las nuevas columnas (Es Policía, CLU, Vto CLU, etc.) aparezcan correctamente.
- En caso de aprobación, ejecutar el nuevo script de migración para trasladar los asientos contables históricos.
