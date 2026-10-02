# Plan 103: Configuración de Cadencia de Envío de Mails (Delay Antispam) para Estudio

**Fecha:** 2 de Octubre de 2026  
**Autor:** Cristian - PC CASA  
**Objetivo:** Permitir al usuario configurar la cadencia (intervalo de pausa en segundos entre envíos) desde el modal de ajustes de correo para la verticalidad Estudio, persistiendo el valor en el archivo JSON en `media/config_mails/` para respetar las políticas de servidores SMTP como DonWeb (100 destinatarios/hora) y evitar bloqueos temporales o alarmas de spam.

---

## 1. Contexto y Diagnóstico Técnico
- **Host del Estudio:** `mail.lopezriossa.com` (`67.23.242.202`).
- **Proveedor:** DonWeb / Ferozo.
- **Políticas de DonWeb:** Límite estricto de 100 correos/destinatarios por hora por casilla.
- **Riesgo:** Enviar comprobantes en ráfaga (0 delay) satura el servidor SMTP y puede generar bloqueos temporales de 1 hora.
- **Solución:** Exponer en el modal de configuración SMTP un control amigable de cadencia con presets (`1.0s`, `2.0s`, `3.0s`, `5.0s`), con valor predeterminado seguro en `2.0s` recomendado para DonWeb, y persistirlo en el JSON de la empresa.

---

## 2. Modificaciones Técnicas

### 2.1 Modal de Configuración SMTP
- **Archivo:** `verticalidades/estudio/templates/estudio/modals/config_mails_modal.html`
- **Cambio:** En la sección "2. Servidor SMTP (Saliente)", agregar un selector visual con input numérico (`delay_segundos`) y botones rápidos (`1.0s`, `2.0s`, `3.0s`, `5.0s`), indicando la recomendación para DonWeb.

### 2.2 Endpoint de Guardado de Configuración
- **Archivo:** `verticalidades/estudio/views.py` (`config_mails_guardar`)
- **Cambio:** Capturar `delay_segundos` de `request.POST`, sanitizar entre 0.5s y 60.0s (default 2.0s) y agregarlo a los datos persistidos en el archivo JSON.

### 2.3 Servicios de Configuración y SMTP
- **Archivo:** `verticalidades/estudio/services/config_mail_service.py`
  - Actualizar `DEFAULT_CONFIG['delay_segundos'] = 2.0`.
- **Archivo:** `verticalidades/estudio/services/smtp_service.py`
  - Utilizar `2.0` como fallback si no existe en la configuración.

---

## 3. Plan de Pruebas
1. Ejecución de tests automatizados de `verticalidades.estudio`:
   - `python manage.py test verticalidades.estudio`
2. Test unitario de persistencia y lectura de `delay_segundos` en la configuración de la empresa.
