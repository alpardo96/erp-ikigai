# Plan de Implementación: Control y Advertencia de Vencimiento de Certificados Digitales ARCA/AFIP

Los certificados digitales (.crt) de ARCA/AFIP tienen una fecha de caducidad fijada por el organismo emisor (normalmente 1 a 2 años). Para evitar que una empresa quede inhabilitada para facturar electrónicamente sin previo aviso, este plan detalla la incorporación del campo de fecha de vencimiento en la tabla `empresas_empresa`, la autodetección automática del vencimiento al subir o guardar el certificado (.crt), y un sistema de alertas muy visible y legible en la interfaz del sistema a partir de 15 días antes del vencimiento (o si ya se encuentra vencido).

---

## 🛑 Revisión del Usuario Requerida

> [!IMPORTANT]
> **Puntos clave a revisar:**
> 1. **Autodetección:** Al subir un certificado `.crt`, el sistema extraerá automáticamente la fecha de vencimiento utilizando la librería nativa `cryptography.x509`. No obstante, el campo `vencimiento_crt_afip` también se expondrá en el formulario de la empresa para permitir consulta o edición manual si fuera necesario.
> 2. **Criterio de Advertencia:** La advertencia se activará automáticamente cuando falten **15 días o menos** para el vencimiento (o si el certificado ya expiró).
> 3. **Visibilidad:** La advertencia se mostrará de dos formas:
>    - **Banner global destacado** en la parte superior del layout (`base.html`), visible al navegar por el sistema con esa empresa seleccionada.
>    - **Indicador de estado (Badge)** en la pantalla/modal de configuración de la empresa.

---

## ❓ Preguntas Abiertas

Ninguna por el momento. Los requerimientos fueron definidos claramente.

---

## 🛠️ Cambios Propuestos

### 1. App `empresas` (Modelos y Formularios)

#### [MODIFY] `empresas/models.py`
- Agregar el campo `vencimiento_crt_afip = models.DateField(null=True, blank=True, verbose_name="Fecha de Vencimiento Certificado ARCA")`.
- Implementar el método helper `extraer_vencimiento_crt()` para leer los bytes del certificado `.crt` subido y obtener su fecha de vencimiento (`not_valid_after_utc.date()`).
- Sobrescribir `save(*args, **kwargs)` para autocompletar `vencimiento_crt_afip` si existe el archivo `.crt` y la fecha está vacía o el certificado fue modificado.
- Agregar propiedades helper en `Empresa`:
  - `dias_hasta_vencimiento_crt`: Número entero de días restantes.
  - `estado_vencimiento_crt`: Estructura con `es_vencido`, `es_advertencia`, `dias`, `nivel` ('danger', 'warning', 'success', 'none') y `mensaje`.

#### [MODIFY] `empresas/forms.py`
- Añadir `vencimiento_crt_afip` a `fields` de `EmpresaForm`.
- Configurar widget de fecha `forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'w-full rounded-xl border-gray-200 text-sm'})`.

#### [NEW] `empresas/migrations/0015_empresa_vencimiento_crt_afip.py`
- Migración de esquema para agregar la columna `vencimiento_crt_afip` a `empresas_empresa`.
- Migración de datos opcional para recalcular el vencimiento de las empresas que ya tengan `.crt` guardado en el servidor.

---

### 2. Context Processor Global y Layout Base

#### [MODIFY] `core/context_processors.py`
- En `context_context(request)`:
  - Evaluar la `empresa_actual`.
  - Si la empresa posee certificado `.crt`, consultar `estado_vencimiento_crt`.
  - Si la empresa está en período de advertencia (`dias <= 15`) o vencida, inyectar el diccionario `alerta_certificado_afip` en el contexto global de las plantillas.

#### [MODIFY] `templates/base.html`
- Insertar un banner de alerta destacado e imposible de obviar en la parte superior de la vista principal.
- **Banner Rojo (Vencido / <= 3 días):** Estilo de urgencia con ícono de aviso crítico y enlace directo a configuración.
- **Banner Amarillo (4 a 15 días):** Estilo de advertencia preventiva con contador de días restantes.

---

### 3. Vistas y Modales de Empresa

#### [MODIFY] `templates/configuracion/modals/empresa_form.html`
- Incluir la fecha de vencimiento `vencimiento_crt_afip` dentro de la sección "Facturación Electrónica ARCA (WSFEv1)".
- Agregar insignias visuales (badges de colores) que indiquen claramente el estado actual del certificado (Vigente / Vence en X días / Vencido).

---

### 4. Pruebas Unitarias

#### [NEW] `empresas/tests/test_vencimiento_certificado.py`
- Pruebas unitarias para validar:
  1. Extracción correcta de la fecha de vencimiento a partir de un certificado PEM X509.
  2. Cálculo de días restantes y respuestas de `estado_vencimiento_crt`.
  3. Comportamiento del contexto global cuando la empresa tiene un certificado próximo a vencer.

---

## 🧪 Plan de Verificación

### Pruebas Automatizadas
- Ejecutar la suite de tests de la app `empresas`:
  ```bash
  venv\Scripts\python.exe manage.py test empresas
  ```

### Pruebas Manuales
1. Ingresar como Administrador al ERP.
2. Abrir la configuración de la empresa en `Configuración > Editar Empresa`.
3. Cargar un certificado `.crt` válido y verificar que la fecha de vencimiento se auto-complete correctamente.
4. Modificar manualmente la fecha de vencimiento a una fecha dentro de los próximos 10 días para simular la advertencia previa de 15 días.
5. Guardar los cambios y verificar la aparición del banner de advertencia amarillo en la parte superior de la pantalla al navegar.
6. Cambiar la fecha a una fecha pasada (simular certificado vencido) y verificar la transición a la alerta roja crítica.
