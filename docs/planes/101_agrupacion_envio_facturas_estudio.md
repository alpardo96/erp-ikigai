# Plan 101: Agrupación Permanente y Dinámica de Envíos de Facturas (Verticalidad Estudio)

**Fecha:** 01 de Octubre de 2026  
**Autor:** Cristian - PC CASA  
**Verticalidad:** Exclusiva para empresas tipo `ESTUDIO` (`verticalidades.estudio`)  
**Objetivo:** Permitir la agrupación de comprobantes para su envío por correo electrónico consolidado (múltiples facturas en 1 solo mail con múltiples PDFs adjuntos) tanto para:
1. **Un mismo cliente** con múltiples facturas emitidas por diferentes servicios/conceptos en el período (con opción de salir agrupadas en 1 solo mail o individuales en correos separados).
2. **Múltiples clientes (Clipros)** distintos que pertenecen al mismo grupo económico, holding o familia y comparten el mismo destinatario de correo.
3. **Gestión integral desde la UI**: Modal de administración de grupos permanentes y asignación/desasignación ágil de comprobantes en la pantalla de Envíos sin salir de la vista operativa.

---

## 1. Análisis del Modelo de Datos (Exclusivo Verticalidad Estudio)

### 1.1 Nuevo Modelo: `GrupoEnvioEstudio`
Ubicación: `verticalidades/estudio/models.py`
Hereda de `AuditModel` (`core.models.AuditModel`).
* **`empresa`**: ForeignKey a `empresas.Empresa` (on_delete=CASCADE).
* **`nombre`**: CharField(150), ej. "Grupo Pérez", "Holding XYZ", "Honorarios + Liquidación Juan Gómez".
* **`destinatarios`**: CharField(500), correos electrónicos separados por coma (normalizados).
* **`clientes`**: ManyToManyField a `facturacion.ClienteProveedor` (related_name='grupos_envio_estudio', blank=True). Permite definir qué clientes integran este grupo de forma permanente.
* **`activo`**: BooleanField(default=True).
* **`observaciones`**: TextField(blank=True, null=True).
* **Meta**:
  * `db_table = 'estudio_grupo_envio'`
  * `verbose_name = 'Grupo de Envío Estudio'`
  * `verbose_name_plural = 'Grupos de Envío Estudio'`
  * Índices en `['empresa', 'activo']`.

### 1.2 Extensión de `EnvioFacturaEstudio`
Ubicación: `verticalidades/estudio/models.py`
* **`grupo`**: ForeignKey a `GrupoEnvioEstudio` (null=True, blank=True, on_delete=models.SET_NULL, related_name='envios_facturas', verbose_name="Grupo de Envío").
* Índice en `['empresa', 'grupo']`.

---

## 2. Lógica de Descubrimiento y Asignación Automática

En `verticalidades/estudio/views.py` (`api_envios_facturas` y `facturacion_lote_estudio.py`):
1. Al descubrir o generar comprobantes de venta del período para la empresa activa:
   - Se consulta si el cliente (`v.cliente_id`) forma parte de un `GrupoEnvioEstudio` activo de esa empresa.
   - Si pertenece a un grupo activo:
     - El registro `EnvioFacturaEstudio` se crea vinculado automáticamente a ese `grupo`.
     - Si el grupo tiene destinatarios definidos, se preasignan como destinatarios del envío.
   - Si no pertenece a ningún grupo (o el cliente no tiene grupo):
     - El registro queda con `grupo = None` (envío individual estándar).
2. En la respuesta JSON de `api_envios_facturas`, cada item incluirá:
   - `grupo_id`: ID del grupo o `null`.
   - `grupo_nombre`: Nombre del grupo o `""`.
   - `grupo_destinatarios`: Destinatarios del grupo.
   - Lista general de `grupos_disponibles` para que el frontend pueda desplegarlos en selectores.

---

## 3. Servicio SMTP: Envío Consolidado Multi-Factura (`smtp_service.py`)

Ubicación: `verticalidades/estudio/services/smtp_service.py`

### 3.1 Procesamiento por Lote Streaming
Al invocar `procesar_lote_pendientes_streaming(envios_pendientes, usuario)`:
1. Los registros seleccionados se dividen en dos categorías:
   * **Individuales (`grupo is None`):** Se procesan de forma unitaria tal como hasta ahora (1 correo por factura).
   * **Agrupados (`grupo is not None`):** Se agrupan por `grupo_id`.
2. Para cada paquete o grupo:
   * Se recuperan todos los `EnvioFacturaEstudio` del grupo seleccionados en el lote.
   * Se compila el correo consolidado:
     * **Asunto:** Configurable, ej. *"Comprobantes Período {periodo} - {grupo_nombre}"*.
     * **Cuerpo HTML:**
       * Saludo al grupo/destinatario.
       * Tabla profesional estilizada con las columnas: Cliente / Razón Social, Tipo y Número de Comprobante, Concepto y Total.
       * Fila destacada con el **Importe Total Consolidado**.
       * Firma corporativa del estudio.
     * **Adjuntos:**
       * Se genera en memoria el PDF oficial de cada venta: `Factura_A_0001-00000001.pdf`, `Factura_A_0001-00000002.pdf`, etc.
       * Si algún comprobante tiene adjunto externo (`archivo_adjunto`) y su `modo_adjunto` es `REEMPLAZAR` o `AMBOS`, se adjuntan los archivos respectivos.
   * Se envía a través de la conexión SMTP persistente con el control de cadencia (anti-spam).
   * En caso de éxito (`250 OK`):
     * Mediante `transaction.atomic()`, se actualizan **todos** los `EnvioFacturaEstudio` del paquete a estado `'ENVIADO'`, registrando fecha y respuesta SMTP.
     * Se emite evento SSE de progreso al frontend indicando: *"Grupo {nombre} ({N} comprobantes) enviado con éxito"*.
   * En caso de error:
     * Todos los registros del paquete pasan a estado `'ERROR'` con el detalle exacto para reintento.

---

## 4. Interfaz de Usuario y Experiencia Operativa (Alpine.js + Tailwind)

Ubicación: `verticalidades/estudio/templates/estudio/envios_facturas.html` y nuevo modal.

### 4.1 Barra de Acciones Superior
* Junto al botón "Enviar Seleccionadas", se añade el botón:
  * **"📦 Grupos de Envío"** (con badge indicando cuántos grupos activos existen).

### 4.2 Modal: Gestión de Grupos de Envío (`modals/grupos_envio_modal.html`)
Permite:
1. **Crear / Editar Grupos Permanentes:**
   * Nombre del grupo (ej. "Familia Rossi", "Grupo Constructora").
   * Destinatarios de correo (chips interactivos de emails).
   * Asignación de clientes (buscador multiselect de Clipro del estudio).
2. **Acciones Rápidas sobre el Período Actual:**
   * Botón para **"Agrupar comprobantes seleccionados"** en un grupo nuevo o existente.
   * Botón para **"Desagrupar"** (dejar como envíos individuales).

### 4.3 Visualización en la Grilla Principal
* Cada fila perteneciente a un grupo muestra una insignia visual distintiva (ej. badge índigo con icono `📦 [Nombre del Grupo]`).
* Tooltip y filtro rápido para listar: "Todos", "Individuales", o filtrar por un grupo específico.
* Si se selecciona una fila de un grupo, el sistema puede seleccionar automáticamente a sus compañeras de grupo para mantener la integridad del paquete.

---

## 5. Endpoints y Vistas en `views.py`

* `api_grupos_envio(request)`: GET para listar los grupos de la empresa; POST para crear o editar un grupo.
* `api_eliminar_grupo_envio(request, grupo_id)`: POST/DELETE para desactivar o eliminar un grupo.
* `api_asignar_grupo_comprobantes(request)`: POST con lista de `envio_ids` y `grupo_id` (o `null` para desagrupar) para modificar la agrupación directamente en la pantalla de envíos.

---

## 6. Plan de Pruebas Automatizadas

En `verticalidades/estudio/tests.py`:
1. **Test de Modelos:** Creación de `GrupoEnvioEstudio` con múltiples clientes y verificación de relaciones.
2. **Test de Auto-descubrimiento:** Generación de comprobantes y verificación de que se asigne automáticamente el grupo si el cliente pertenece a uno.
3. **Test de Envío Agrupado SMTP:**
   * Mock de SMTP server.
   * Verificación de que para 3 facturas de un grupo se despache **un único correo MIME**.
   * Verificación de que el correo contenga los 3 PDFs adjuntos.
   * Verificación de que los 3 registros de `EnvioFacturaEstudio` queden en estado `ENVIADO`.
4. **Test de Desagrupación y Envío Individual:** Verificar que facturas sin grupo sigan saliendo de forma unitaria sin alteración.
