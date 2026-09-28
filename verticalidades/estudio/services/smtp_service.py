import smtplib
import time
import os
import re
import html
import email.utils
from pathlib import Path
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from typing import Optional, List, Dict, Tuple, Generator

from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone

from facturacion.models import Venta
from facturacion.services.pdf_service import generar_pdf_venta
from verticalidades.estudio.models import EnvioFacturaEstudio
from verticalidades.estudio.services.config_mail_service import get_config_mail, is_config_activa


def safe_format(tpl: str, ctx: dict) -> str:
    """
    Reemplaza de forma segura las variables {nombre} sin arrojar KeyError si hay otras llaves.
    """
    res = str(tpl or '')
    for k, v in ctx.items():
        res = res.replace(f"{{{k}}}", str(v))
    return res


class SMTPService:
    """
    Servicio profesional de envío de facturas por SMTP con:
    - Control de cadencia (rate limiting / throttling) para evitar listas negras (antispam).
    - Reuso de una única sesión autenticada por lote.
    - Cabeceras RFC conformes (Message-ID, Date, X-Mailer, Reply-To).
    - Captura exhaustiva de códigos y respuestas de diagnóstico SMTP.
    """

    def __init__(self, empresa_id: int):
        self.empresa_id = empresa_id
        self.config = get_config_mail(empresa_id)
        self._server = None

    def abrir_conexion(self) -> smtplib.SMTP:
        """
        Abre una sesión SMTP reutilizable según la configuración de la empresa.
        """
        host = self.config.get('servidor_smtp')
        port = int(self.config.get('puerto_smtp', 465))
        usuario = self.config.get('usuario_smtp')
        password = self.config.get('password_smtp')
        usar_ssl = self.config.get('usar_ssl', True)
        usar_tls = self.config.get('usar_tls', False)

        # Si el puerto es 465 o usar_ssl está activo, usamos smtplib.SMTP_SSL (servidor seguro directo)
        if usar_ssl or port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=20)
        else:
            server = smtplib.SMTP(host, port, timeout=20)
            server.ehlo()
            if usar_tls or port == 587:
                server.starttls()
                server.ehlo()

        if usuario and password:
            server.login(usuario, password)

        self._server = server
        return server

    def cerrar_conexion(self):
        """
        Cierra limpiamente la sesión SMTP si está abierta.
        """
        if self._server:
            try:
                self._server.quit()
            except Exception:
                try:
                    self._server.close()
                except Exception:
                    pass
            finally:
                self._server = None

    @staticmethod
    def probar_conexion(config: dict) -> Tuple[bool, str]:
        """
        Verifica conectividad y credenciales SMTP sin enviar correos a clientes.
        """
        host = config.get('servidor_smtp')
        try:
            port = int(config.get('puerto_smtp', 465))
        except (ValueError, TypeError):
            port = 465
        usuario = config.get('usuario_smtp')
        password = config.get('password_smtp')
        usar_ssl = config.get('usar_ssl', True)
        usar_tls = config.get('usar_tls', False)

        if not host:
            return False, "Falta especificar el servidor SMTP."
        if not usuario or not password:
            return False, "Faltan las credenciales de usuario o contraseña SMTP."

        server = None
        try:
            if usar_ssl or port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=15)
            else:
                server = smtplib.SMTP(host, port, timeout=15)
                server.ehlo()
                if usar_tls or port == 587:
                    server.starttls()
                    server.ehlo()

            server.login(usuario, password)
            server.noop()
            return True, "Conexión y autenticación SMTP exitosa."
        except smtplib.SMTPAuthenticationError as e:
            return False, f"Autenticación rechazada por el servidor: {e.smtp_error.decode('utf-8', errors='ignore') if hasattr(e, 'smtp_error') else str(e)}"
        except smtplib.SMTPConnectError as e:
            return False, f"No se pudo conectar al servidor SMTP ({host}:{port}): {str(e)}"
        except Exception as e:
            return False, f"Error en la verificación SMTP: {str(e)}"
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

    def _construir_mensaje(
        self,
        envio: EnvioFacturaEstudio,
        venta: Venta,
        pdf_bytes: bytes,
        lista_destinatarios: List[str],
        usuario=None
    ) -> MIMEMultipart:
        """
        Construye el contenedor MIME con formato multipart/mixed y alternative (plain y html),
        con firma enriquecida, soporte para negritas <b>, variables y logo de firma inline.
        """
        msg = MIMEMultipart('mixed')

        remitente_email = self.config.get('email_remitente') or self.config.get('usuario_smtp')
        remitente_nombre = self.config.get('nombre_remitente') or venta.empresa.nombre

        # Cabeceras
        msg['From'] = email.utils.formataddr((remitente_nombre, remitente_email))
        msg['To'] = ", ".join(lista_destinatarios)
        msg['Reply-To'] = remitente_email
        msg['Date'] = email.utils.formatdate(localtime=True)
        
        # Generar Message-ID profesional para evitar spam filters
        dominio_remitente = remitente_email.split('@')[-1] if '@' in remitente_email else 'erp.local'
        msg['Message-ID'] = email.utils.make_msgid(domain=dominio_remitente)
        msg['X-Mailer'] = 'ERP Ikigai 2.0 - Modulo Estudio'

        # Variables disponibles para sustitución
        u = usuario or getattr(venta, 'usuario', None)
        first_name = (u.first_name if u and getattr(u, 'first_name', None) else (getattr(u, 'username', '') if u else '')).strip()
        last_name = (u.last_name if u and getattr(u, 'last_name', None) else '').strip()
        nombre_usuario = f"{first_name} {last_name}".strip() or (getattr(u, 'username', '') if u else '')

        tipo_cbte = venta.tipo.detalle if venta.tipo else "Comprobante"
        cbte_str = f"{tipo_cbte} {venta.punto:04d}-{venta.numero:08d}"
        cliente_nombre = venta.cliente_razon_social or (venta.cliente.razon_social if venta.cliente else "")
        empresa_nombre = venta.empresa.nombre

        ctx = {
            'cliente': cliente_nombre,
            'comprobante': cbte_str,
            'periodo': venta.periodo_facturado or envio.periodo or "",
            'empresa': empresa_nombre,
            'total': f"${venta.total:,.2f}",
            'first_name': first_name,
            'last_name': last_name,
            'usuario': nombre_usuario,
        }

        # 1. Asunto
        asunto_tpl = self.config.get('asunto') or "Factura {comprobante} - {empresa}"
        asunto_final = safe_format(asunto_tpl, ctx)
        msg['Subject'] = Header(asunto_final, 'utf-8').encode()

        # 2. Textos de Cuerpo y Firma
        cuerpo_tpl = self.config.get('mensaje') or ""
        firma_tpl = self.config.get('firma') or ""

        cuerpo_txt = safe_format(cuerpo_tpl, ctx)
        firma_txt = safe_format(firma_tpl, ctx)

        # 3. Logo de Firma (si existe)
        logo_rel_path = self.config.get('logo_firma')
        logo_path = None
        if logo_rel_path:
            p = Path(settings.MEDIA_ROOT) / logo_rel_path
            if p.exists() and p.is_file():
                logo_path = p

        # 4. Versión Texto Plano (limpia tags <b> y <br>)
        texto_plano_completo = cuerpo_txt
        if firma_txt:
            texto_plano_completo += f"\n\n---\n{firma_txt}"
        texto_plano = re.sub(r'</?(?:b|strong)>', '*', texto_plano_completo)
        texto_plano = re.sub(r'<[^>]+>', '', texto_plano)

        # 5. Versión HTML Enriquecida con soporte para negrita <b>
        def parse_formato_html(texto: str) -> str:
            t = html.escape(texto)
            t = t.replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>')
            t = t.replace('&lt;strong&gt;', '<strong>').replace('&lt;/strong&gt;', '</strong>')
            t = t.replace('&lt;i&gt;', '<i>').replace('&lt;/i&gt;', '</i>')
            t = t.replace('&lt;u&gt;', '<u>').replace('&lt;/u&gt;', '</u>')
            t = t.replace('\n', '<br>')
            return t

        cuerpo_html = parse_formato_html(cuerpo_txt)
        firma_html = parse_formato_html(firma_txt) if firma_txt else ""

        html_logo_tag = ""
        if logo_path:
            html_logo_tag = '<div style="margin-top: 12px;"><img src="cid:firma_logo" style="max-height: 80px; max-width: 240px; display: block;" alt="Firma"></div>'

        firma_bloque = ""
        if firma_html or html_logo_tag:
            firma_bloque = f'''
            <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e2e8f0; color: #475569; font-size: 13px; line-height: 1.5;">
                {firma_html}
                {html_logo_tag}
            </div>
            '''

        html_final = f'''<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"></head>
<body style="margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #1e293b; background-color: #ffffff;">
    <div style="max-width: 600px; margin: 0 auto;">
        <div style="margin-bottom: 20px;">
            {cuerpo_html}
        </div>
        {firma_bloque}
    </div>
</body>
</html>'''

        # Estructurar multipart/alternative y multipart/related para la imagen inline
        alt_part = MIMEMultipart('alternative')
        alt_part.attach(MIMEText(texto_plano, 'plain', 'utf-8'))

        if logo_path:
            related_part = MIMEMultipart('related')
            related_part.attach(MIMEText(html_final, 'html', 'utf-8'))
            try:
                with open(logo_path, 'rb') as f:
                    img_data = f.read()
                ext = logo_path.suffix.lstrip('.').lower()
                mime_sub = 'jpeg' if ext in ['jpg', 'jpeg'] else ext
                img_part = MIMEImage(img_data, _subtype=mime_sub)
                img_part.add_header('Content-ID', '<firma_logo>')
                img_part.add_header('Content-Disposition', 'inline', filename=logo_path.name)
                related_part.attach(img_part)
                alt_part.attach(related_part)
            except Exception:
                alt_part.attach(MIMEText(html_final, 'html', 'utf-8'))
        else:
            alt_part.attach(MIMEText(html_final, 'html', 'utf-8'))

        msg.attach(alt_part)

        # 6. Adjuntar PDF
        nombre_pdf = f"Factura_{venta.tipo.codigo if venta.tipo else 'DOC'}_{venta.punto:04d}-{venta.numero:08d}.pdf"
        adjunto = MIMEApplication(pdf_bytes, _subtype="pdf")
        adjunto.add_header('Content-Disposition', 'attachment', filename=('utf-8', '', nombre_pdf))
        msg.attach(adjunto)

        return msg

    def enviar_factura_individual(self, envio: EnvioFacturaEstudio, usuario=None) -> Tuple[bool, str]:
        """
        Envía una sola factura reutilizando la conexión abierta o abriendo una temporal.
        Actualiza el registro en EnvioFacturaEstudio.
        """
        conexion_propia = False
        if not self._server:
            try:
                self.abrir_conexion()
                conexion_propia = True
            except Exception as e:
                envio.estado = 'ERROR'
                envio.intentos += 1
                envio.respuesta_smtp = f"Fallo al conectar con servidor SMTP: {str(e)}"
                envio.save(update_fields=['estado', 'intentos', 'respuesta_smtp', 'fecha_modificacion'])
                return False, envio.respuesta_smtp

        try:
            # 1. Resolver destinatarios válidos
            raw_destinatarios = envio.destinatarios or (envio.cliente.correo if envio.cliente else "")
            destinatarios = [d.strip() for d in str(raw_destinatarios).split(',') if d.strip()]
            
            validos = []
            for d in destinatarios:
                try:
                    validate_email(d)
                    validos.append(d)
                except ValidationError:
                    pass

            if not validos:
                envio.estado = 'ERROR'
                envio.intentos += 1
                envio.respuesta_smtp = "Error: El cliente no posee ningún correo electrónico válido cargado."
                envio.save(update_fields=['estado', 'intentos', 'respuesta_smtp', 'fecha_modificacion'])
                return False, envio.respuesta_smtp

            # 2. Generar PDF de la factura
            venta = envio.venta
            try:
                pdf_bytes = generar_pdf_venta(venta.ventas_id)
            except Exception as e:
                envio.estado = 'ERROR'
                envio.intentos += 1
                envio.respuesta_smtp = f"Error generando PDF del comprobante: {str(e)}"
                envio.save(update_fields=['estado', 'intentos', 'respuesta_smtp', 'fecha_modificacion'])
                return False, envio.respuesta_smtp

            # 3. Construir mensaje
            msg = self._construir_mensaje(envio, venta, pdf_bytes, validos, usuario=usuario)
            remitente_email = self.config.get('email_remitente') or self.config.get('usuario_smtp')

            # 4. Enviar mediante la sesión SMTP activa
            rechazados = self._server.sendmail(remitente_email, validos, msg.as_string())

            if rechazados:
                envio.estado = 'ERROR'
                envio.intentos += 1
                envio.respuesta_smtp = f"Destinatarios rechazados por el servidor: {rechazados}"
                envio.save(update_fields=['estado', 'intentos', 'respuesta_smtp', 'fecha_modificacion'])
                return False, envio.respuesta_smtp

            # Éxito
            envio.estado = 'ENVIADO'
            envio.intentos += 1
            envio.fecha_envio = timezone.now()
            envio.respuesta_smtp = "250 OK - Entregado exitosamente al servidor SMTP"
            envio.save(update_fields=['estado', 'intentos', 'fecha_envio', 'respuesta_smtp', 'fecha_modificacion'])
            return True, envio.respuesta_smtp

        except smtplib.SMTPRecipientsRefused as e:
            envio.estado = 'ERROR'
            envio.intentos += 1
            envio.respuesta_smtp = f"Error SMTP (Destinatario rechazado): {str(e.recipients)}"
            envio.save(update_fields=['estado', 'intentos', 'respuesta_smtp', 'fecha_modificacion'])
            return False, envio.respuesta_smtp
        except smtplib.SMTPSenderRefused as e:
            envio.estado = 'ERROR'
            envio.intentos += 1
            envio.respuesta_smtp = f"Error SMTP (Remitente no autorizado por el servidor): {e.sender}"
            envio.save(update_fields=['estado', 'intentos', 'respuesta_smtp', 'fecha_modificacion'])
            return False, envio.respuesta_smtp
        except Exception as e:
            envio.estado = 'ERROR'
            envio.intentos += 1
            envio.respuesta_smtp = f"Error en envío: {str(e)}"
            envio.save(update_fields=['estado', 'intentos', 'respuesta_smtp', 'fecha_modificacion'])
            return False, envio.respuesta_smtp
        finally:
            if conexion_propia:
                self.cerrar_conexion()

    def procesar_lote_pendientes_streaming(self, queryset_envios, usuario=None) -> Generator[Dict, None, None]:
        """
        Procesa el lote completo de comprobantes pendientes emitiendo eventos de progreso
        en tiempo real (Generador para StreamingHttpResponse).
        Aplica cadencia (throttling) de 1 segundo entre envíos para no saturar la IP pública.
        """
        total = queryset_envios.count()
        exitosos = 0
        errores = 0
        detalles_errores = []

        yield {
            'tipo': 'inicio',
            'total': total,
            'mensaje': f"Iniciando envío de {total} comprobante(s)..."
        }

        if total == 0:
            yield {
                'tipo': 'fin',
                'total': 0,
                'exitosos': 0,
                'errores': 0,
                'detalles_errores': [],
                'mensaje': "No hay comprobantes pendientes para enviar en este período."
            }
            return

        activa, motivo = is_config_activa(self.empresa_id)
        if not activa:
            yield {
                'tipo': 'fin',
                'total': total,
                'exitosos': 0,
                'errores': total,
                'detalles_errores': [{'cliente': 'General', 'error': motivo}],
                'mensaje': f"Configuración inactiva: {motivo}"
            }
            return

        # Abrir una sola conexión persistente para todo el lote
        try:
            self.abrir_conexion()
        except Exception as e:
            yield {
                'tipo': 'fin',
                'total': total,
                'exitosos': 0,
                'errores': total,
                'detalles_errores': [{'cliente': 'Servidor SMTP', 'error': f"Fallo al conectar: {str(e)}"}],
                'mensaje': f"Error crítico al conectar con el servidor SMTP: {str(e)}"
            }
            return

        delay = float(self.config.get('delay_segundos', 1.0))
        procesados = 0

        try:
            for envio in queryset_envios:
                cliente_nombre = envio.cliente.razon_social if envio.cliente else "Cliente"
                comprobante_str = f"{envio.venta.tipo.detalle if envio.venta.tipo else 'DOC'} {envio.venta.punto:04d}-{envio.venta.numero:08d}"

                ok, respuesta = self.enviar_factura_individual(envio, usuario=usuario)
                procesados += 1

                if ok:
                    exitosos += 1
                    yield {
                        'tipo': 'progreso',
                        'procesados': procesados,
                        'total': total,
                        'porcentaje': round((procesados / total) * 100, 1),
                        'status': 'ok',
                        'cliente': cliente_nombre,
                        'comprobante': comprobante_str,
                        'mensaje': f"✓ {cliente_nombre}: Enviado OK"
                    }
                else:
                    errores += 1
                    detalles_errores.append({
                        'cliente': cliente_nombre,
                        'comprobante': comprobante_str,
                        'error': respuesta
                    })
                    yield {
                        'tipo': 'progreso',
                        'procesados': procesados,
                        'total': total,
                        'porcentaje': round((procesados / total) * 100, 1),
                        'status': 'error',
                        'cliente': cliente_nombre,
                        'comprobante': comprobante_str,
                        'mensaje': f"✗ {cliente_nombre}: {respuesta}"
                    }

                # Respetar cadencia profesional anti-spam entre correos
                if procesados < total and delay > 0:
                    time.sleep(delay)

        finally:
            self.cerrar_conexion()

        yield {
            'tipo': 'fin',
            'total': total,
            'exitosos': exitosos,
            'errores': errores,
            'detalles_errores': detalles_errores,
            'mensaje': f"Lote finalizado: {exitosos} exitoso(s), {errores} con error."
        }
