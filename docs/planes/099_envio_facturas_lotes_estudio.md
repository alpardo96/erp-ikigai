# Plan 099: Modalidad Estudio - Multi-contacto Clipro, Servicio SMTP Antispam y Envío Masivo de Facturas

**Fecha:** 28 de Septiembre de 2026  
**Objetivo:** Implementar la modalidad específica de verticalidad Estudio para:
1. Permitir múltiples correos y teléfonos concatenados por coma en Clipro (exclusivo para Estudio).
2. Desarrollar un servicio profesional de SMTP con control de cadencia (rate limiting / throttling), reuso de conexión segura y cabeceras anti-spam para proteger la IP pública y evitar listas negras.
3. Configuración por empresa en archivo `.json` en `media/` con activación/desactivación, servidor SMTP y plantilla de mensaje.
4. Registro automático de facturas emitidas por lotes en tabla satélite de Estudio (`estudio_envio_factura`).
5. Vista operativa de ventas para envíos de facturas por mail, con reenvío individual y botón masivo "Enviar Pendientes" con modal emergente bloqueante y reporte en tiempo real.

---

## 1. Múltiples Correos y Teléfonos en Clipro (Solo Estudio)

### 1.1 Modelo `ClienteProveedor`
- Archivo: `facturacion/models.py`
- Modificar `correo` de `models.EmailField` a `models.CharField(max_length=255, null=True, blank=True)`.
- Modificar `telefono` a `models.CharField(max_length=255, null=True, blank=True)`.
- Generar y aplicar migración en `facturacion`.

### 1.2 Formulario `ClienteProveedorForm`
- Archivo: `facturacion/forms.py`
- En `__init__`: si `empresa.tipo_actividad == 'ESTUDIO'`, definir `correo` y `telefono` como `forms.CharField(required=False)`.
- En `clean()`:
  - Para Estudio: dividir `correo` por `,`, validar cada dirección con `validate_email` de Django, normalizar con `", "`. En `telefono`, sanitizar y unir con `", "`.
  - Para otras actividades: mantener la validación estándar original.

### 1.3 Modal de Clipro
- Archivos: `facturacion/views_htmx.py` y `templates/facturacion/modals/cliente_modal.html`
- Inyectar en el contexto `es_estudio: true/false`.
- En el template, si `es_estudio` es verdadero:
  - Componente Alpine.js interactivo para gestionar chips/etiquetas de teléfonos y correos.
  - Botones de `+ Agregar` y eliminación `[×]`.
  - Input oculto sincronizado que guarda el valor concatenado por coma `, `.
  - Si es falso (otras empresas), mantiene los inputs clásicos unitarios.

---

## 2. Configuración de Correo por Empresa en Media

### 2.1 Servicio `config_mail_service.py`
- Archivo: `verticalidades/estudio/services/config_mail_service.py`
- Gestiona lectura y escritura en `media/config_mails/empresa_{empresa_id}_mails.json`.
- Esquema:
  - `activo`: boolean
  - `email_remitente`: str
  - `nombre_remitente`: str
  - `servidor_smtp`: str (default: smtp.gmail.com)
  - `puerto_smtp`: int (default: 587)
  - `usuario_smtp`: str
  - `password_smtp`: str
  - `usar_tls`: bool (default: true)
  - `usar_ssl`: bool (default: false)
  - `asunto`: str (ej. "Factura {comprobante} - {empresa}")
  - `mensaje`: str (plantilla con variables `{cliente}`, `{comprobante}`, `{periodo}`, `{empresa}`)
  - `delay_segundos`: float (cadencia entre envíos anti-spam, default: 1.0 seg)

### 2.2 Modal y Card de Configuración
- Archivo modal: `verticalidades/estudio/templates/estudio/modals/config_mails_modal.html`
- Archivo tarjeta: en `templates/configuracion/partials/hub.html` (sector Organización / Empresas)
- Vistas asociadas en `verticalidades/estudio/views.py`:
  - `config_mails_modal`: renderiza el modal con los datos actuales.
  - `config_mails_guardar`: valida y escribe el JSON en `media/`.
  - `config_mails_probar`: prueba la conexión y handshake SMTP sin enviar correos masivos.

---

## 3. Servicio SMTP Profesional Anti-Spam (`smtp_service.py`)

### 3.1 Diseño Técnico
- Archivo: `verticalidades/estudio/services/smtp_service.py`
- **Reuso de Conexión:** Abre una única sesión SMTP autenticada para procesar el lote, evitando abrir y cerrar múltiples conexiones consecutivas que los proveedores (Gmail, Outlook, servidores corporativos) interpretan como ataque o flood.
- **Throttling / Cadencia Controlada:** Inserta una pausa prudencial configurable (1 segundo por comprobante) entre cada mensaje para no saturar la IP pública ni activar filtros de rate limiting.
- **Cabeceras Profesionales:**
  - `From`: `"Nombre Empresa" <remitente@dominio.com>`
  - `Reply-To`: correo del remitente o estudio.
  - `Message-ID`: generado con UUID y dominio del remitente.
  - `X-Mailer`: `ERP Ikigai 2.0 - Modulo Estudio`
  - `Date`: RFC 2822
- **Adjunto PDF en Memoria:** Utiliza `generar_pdf_venta(venta_id)` de `facturacion.services.pdf_service` y adjunta el binario como `application/pdf` con nombre legible (`Factura_A_0001-00001234.pdf`).
- **Captura de Respuestas SMTP:**
  - Si el servidor responde `250 OK`, se almacena `"250 OK - Entregado a servidor SMTP"`.
  - Si hay rechazo (550, 421, timeout, auth error), se captura la respuesta exacta para diagnóstico.

---

## 4. Tabla Satélite de Estudio y Automatización en Facturación por Lotes

### 4.1 Modelo `EnvioFacturaEstudio`
- Archivo: `verticalidades/estudio/models.py`
- Campos:
  - `empresa`: ForeignKey a `Empresa`
  - `venta`: OneToOneField a `facturacion.Venta`
  - `cliente`: ForeignKey a `facturacion.ClienteProveedor`
  - `periodo`: CharField(6) (YYYYMM)
  - `destinatarios`: CharField(500)
  - `estado`: Choices (`PENDIENTE`, `ENVIADO`, `ERROR`)
  - `respuesta_smtp`: TextField
  - `fecha_envio`: DateTimeField
  - `intentos`: PositiveIntegerField
  - Índices en `(empresa, estado)` y `(empresa, periodo)`
- Migración en `verticalidades/estudio/migrations/0002_...py`.

### 4.2 Automatización en Lote
- Archivo: `verticalidades/estudio/services/facturacion_lote_estudio.py`
- Al generar cada factura (`venta_f` o `venta_p`), se inserta el registro `EnvioFacturaEstudio` en estado `PENDIENTE` vinculado a la venta y con los correos del Clipro.

---

## 5. Vista Operativa de Ventas: Envío de Facturas

### 5.1 Vistas y Rutas
- Archivos: `verticalidades/estudio/views.py` y `verticalidades/estudio/urls.py`
- Rutas:
  - `estudio/envios-facturas/`: vista principal con selector de período (Mes y Año), métricas superiores (Total, Enviados, Pendientes, Errores) y tabla filtrable.
  - `estudio/envios-facturas/api/`: devuelve JSON con el estado de las facturas del período (descubriendo automáticamente facturas previas no registradas si existieran).
  - `estudio/envios-facturas/enviar-pendientes/`: endpoint de streaming HTTP para procesar todos los pendientes del período en cola, emitiendo progreso línea a línea.
  - `estudio/envios-facturas/reenviar/<int:envio_id>/`: reintento individual para facturas con error o pendientes.

### 5.2 Modal Bloqueante de Progreso en Vivo
- El usuario hace clic en "Enviar Pendientes".
- Se despliega el modal que bloquea la pantalla con backdrop oscuro y `pointer-events-none` en el fondo.
- Consume el streaming del servidor y actualiza una barra de progreso porcentual y un listado en vivo con el estado de cada cliente.
- Al finalizar:
  - Muestra tarjetas de resumen (Total exitosos vs Total con error).
  - Si hay errores, muestra la lista con los motivos devueltos por SMTP.
  - Habilita el botón "Cerrar y Actualizar", refrescando la tabla automáticamente.
- En la tabla, las facturas con estado `ENVIADO` (OK de SMTP) ocultan el botón de reenvío y muestran un badge verde permanente.

### 5.3 Hooks de Menú y Tarjetas
- `verticalidades/estudio/templates/estudio/hooks/ui_ventas_index_cards.html`: nueva tarjeta "Envío de Facturas por Mail".
- `verticalidades/estudio/templates/estudio/hooks/menu_ventas.html`: enlace directo a la vista.
