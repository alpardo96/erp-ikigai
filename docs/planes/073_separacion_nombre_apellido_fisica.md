# Separar Apellido y Nombre vs Razón Social (Módulo Armería)

El objetivo es exigir que el operador defina si está dando de alta una **Persona Física** o **Persona Jurídica** cuando trabaja en el módulo Armería, blindando la carga:
- Al elegir **Física**, se habilitarán los campos **Apellido** y **Nombre**.
- Al elegir **Jurídica**, se habilitará el campo **Razón Social**.
- Los datos se unificarán en el backend para guardarse en el campo `razon_social` de la base de datos (para no romper el esquema unificado).

## > [!WARNING] User Review Required
De acuerdo a tus indicaciones, probaremos este comportamiento **exclusivamente en Armería** antes de inyectarlo en la tabla base de todos los clientes. Por ende, la migración de la base de datos será solo para la tabla `ExtensionArmeria`.

## > [!IMPORTANT] Open Questions: Datos Existentes
Preguntaste: *"¿Conviene setear que si el dni arranca con 20 es física y 30 es jurídica? ¿Poner esta regla que durará poco o acomodar los datos y recién largar?"*

**Mi devolución técnica:**
¡Tu lógica de los prefijos de CUIT (20, 23, 24, 27 = Física; 30, 33, 34 = Jurídica) es matemáticamente perfecta para Argentina!
Pero **NO** debemos dejar esa regla viviendo en el código del sistema para siempre, porque como dices, solo sirve para tapar un hueco temporal. La forma correcta de "acomodar los datos" en Django es usar una **Data Migration (Migración de Datos)**.

¿Qué es esto? Es un script oficial de Django que se ejecuta **UNA SOLA VEZ** al hacer el `migrate`. 
El flujo sería así:
1. Agregamos la columna `tipo_persona` vacía a la base de datos.
2. Nuestro script de migración recorre **todos** los clientes que ya tengan Armería.
3. Lee el CUIT/DNI: si empieza con 3 y tiene 11 dígitos le clava la `"J"` (Jurídica), sino le clava la `"F"` (Física). Además, si es "F", intentará partir la razón social vieja por los espacios y guardarla con la coma (para que no rompa visualmente).
4. Guarda los cambios.

**Conclusión:** Hacemos una migración de datos. Se ejecuta sola, acomoda la basura del pasado en 1 segundo, y nuestro código del ERP queda totalmente limpio sin "parches temporales" asumiendo que de ahora en adelante el dato es 100% confiable.

---

## Proposed Changes

### Módulo: Facturación (Modelos y Migraciones)

#### [NEW] `Migración de Datos (Data Migration)`
- Al hacer `makemigrations`, generaremos un archivo extra de migración en Python que aplique la regla del CUIT:
  - CUIT arranca con 3 (11 dígitos) -> `tipo_persona = 'J'`.
  - DNI o CUIT arranca con 2 (o cualquier otra cosa) -> `tipo_persona = 'F'`.
  - Para los de tipo 'F', se intentará reformatear la `razon_social` para inyectar una coma si es que no la tiene (asumiendo que la última palabra es el nombre y el resto el apellido, o viceversa, solo para tratar de que el `split` no falle).

#### [MODIFY] `facturacion/models.py`
Se agregará el campo `tipo_persona` al modelo `ExtensionArmeria` (como campo de prueba antes de llevarlo a `ClienteProveedor`).
- Será un `CharField` con opciones `('F', 'Persona Física')` y `('J', 'Persona Jurídica')`.
- No tendrá un default en la app final (será obligatorio elegirlo), pero en la migración se nutrirá con la regla del CUIT.

### Módulo: Facturación (Formularios y Lógica)

#### [MODIFY] `facturacion/forms.py`
- Agregar `tipo_persona` a `ExtensionArmeriaForm`.
- Este campo será obligatorio (`required=True`), forzando al usuario a elegir sí o sí uno de los dos Radio Buttons para poder guardar.

#### [MODIFY] `facturacion/views_htmx.py`
En `cliente_modal`:

1. **POST (Guardar nuevo o editado):** 
   - Interceptar `tipo_persona` dentro del bloque de `puede_armeria`. 
   - Si es `F`, tomar `cli_apellido` y `cli_nombre` del request, y concatenarlos como `Apellido, Nombre` para sobreescribir el campo `razon_social` del POST.
   - Si es `J`, validar que el campo original `razon_social` venga con datos.

2. **GET (Edición de un registro existente):** 
   - Si el cliente ya existe y tiene una extensión de Armería vinculada:
     - Revisamos `tipo_persona`.
     - **Si es 'F' (Física):** Tomamos el string guardado en la base de datos en `razon_social` (Ej: "Perez, Juan") y lo dividimos por la coma `split(", ", 1)`. 
       - `context['cli_apellido'] = "Perez"`
       - `context['cli_nombre'] = "Juan"`
       - *(Mecanismo de seguridad por si falla: si no encuentra coma, asigna todo al apellido).*
     - **Si es 'J' (Jurídica):** No hacemos nada extra, el formulario padre cargará la `razon_social` automáticamente en el input.

### Módulo: Facturación (Template Modal)

#### [MODIFY] `templates/facturacion/modals/cliente_modal.html`
- **Alpine.js (`x-data`):** Agregar la variable `tipoPersona` inicializada con el valor guardado en base de datos (o null si es nuevo).
- **Bloqueo Visual Total:**
  - Si `puede_armeria` es True, mostrar 2 enormes botones de selección (Radio cards) al principio: "Persona Física" y "Persona Jurídica".
  - **Mientras `tipoPersona` no esté seleccionado**, ocultamos y deshabilitamos todos los inputs de nombre y razón social, forzando la decisión.
  - **Si se elige "Física":** Mostrar los inputs "Apellido" (poblado con `cli_apellido`) y "Nombre" (poblado con `cli_nombre`).
  - **Si se elige "Jurídica"** o si no tiene permiso de armería: Mostrar el input original "Razón Social".

## Verification Plan

### Automated Tests
- Se generarán las migraciones (`makemigrations`) y se ejecutarán (`migrate`) para asegurar que la base de datos soporta `tipo_persona` en la extensión de Armería.

### Manual Verification
1. Abrir el modal de creación de Cliente/Proveedor con una empresa que sea "ARMERIA".
2. Confirmar que se ven los controles "Persona Física" y "Persona Jurídica".
3. Al seleccionar Física, validar que pide "Apellido" y "Nombre".
4. Guardar y verificar que en la grilla aparece como "Apellido, Nombre".
5. Abrir la edición y verificar que el apellido y nombre se separan correctamente en sus respectivos campos.
6. Probar crear como "Persona Jurídica", llenar la "Razón Social" y verificar que funciona de la forma tradicional.
