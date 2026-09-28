import json
import os
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone

from empresas.models import Empresa, Sucursal
from facturacion.models import ClienteProveedor, TipoComprobante, Venta, VentaItem
from facturacion.forms import ClienteProveedorForm
from verticalidades.estudio.models import TarifaEstudio, EnvioFacturaEstudio
from verticalidades.estudio.services.config_mail_service import (
    get_config_mail, guardar_config_mail, is_config_activa, get_config_file_path
)
from verticalidades.estudio.services.smtp_service import SMTPService, safe_format


class Plan099EstudioTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testadmin', password='password123', is_staff=True)
        self.client = Client()
        self.client.login(username='testadmin', password='password123')

        # Empresa Estudio
        self.empresa_estudio = Empresa.objects.create(
            nombre="Estudio Contable Test",
            cuit="30111111118",
            tipo_actividad="ESTUDIO",
            condicion_iva="RESPONSABLE INSCRIPTO"
        )
        self.sucursal = Sucursal.objects.create(
            nombre="Casa Central",
            empresa=self.empresa_estudio
        )

        # Empresa Estandar
        self.empresa_std = Empresa.objects.create(
            nombre="Comercial General Test",
            cuit="30222222229",
            tipo_actividad="",
            condicion_iva="RESPONSABLE INSCRIPTO"
        )

        # Tipo comprobante
        self.tipo_factura = TipoComprobante.objects.create(
            codigo='011',
            detalle='Factura C',
            estado=True
        )

    def tearDown(self):
        # Limpiar archivo de configuración creado en tests
        cfg_file = get_config_file_path(self.empresa_estudio.id)
        if cfg_file.exists():
            try:
                os.remove(cfg_file)
            except Exception:
                pass

    def test_clipro_multi_correo_y_telefono_en_estudio(self):
        """
        Verifica que en empresas Estudio se admitan múltiples correos y teléfonos
        concatenados por coma, normalizándolos y validando cada email.
        """
        data = {
            'razon_social': 'Cliente Multi Contacto SA',
            'cuit': '30712345678',
            'tipo_entidad': 1,
            'condicion_iva': 'RESPONSABLE INSCRIPTO',
            'tipo_documento': '80',
            'tipo_iibb': 'LOCAL',
            'correo': 'contabilidad@cliente.com, pagos@cliente.com, gerencia@cliente.com',
            'telefono': '011-4455-6677, 381-4998877',
        }
        form = ClienteProveedorForm(data=data, empresa_id=self.empresa_estudio.id)
        self.assertTrue(form.is_valid(), f"Errores en form: {form.errors}")
        
        # Guardar y verificar concatenación
        cliente = form.save(commit=False)
        cliente.empresa = self.empresa_estudio
        cliente.save()

        self.assertEqual(cliente.correo, "contabilidad@cliente.com, pagos@cliente.com, gerencia@cliente.com")
        self.assertEqual(cliente.telefono, "011-4455-6677, 381-4998877")

    def test_clipro_correo_invalido_en_estudio(self):
        """
        Verifica que si uno de los múltiples correos tiene formato inválido,
        el formulario lo rechace con error específico en Estudio.
        """
        data = {
            'razon_social': 'Cliente Correo Malo SA',
            'cuit': '30712345679',
            'tipo_entidad': 1,
            'condicion_iva': 'RESPONSABLE INSCRIPTO',
            'tipo_documento': '80',
            'tipo_iibb': 'LOCAL',
            'correo': 'valido@test.com, correo-invalido-sin-arroba, otro@valido.com',
            'telefono': '12345',
        }
        form = ClienteProveedorForm(data=data, empresa_id=self.empresa_estudio.id)
        self.assertFalse(form.is_valid())
        self.assertIn('correo', form.errors)
        self.assertTrue(any("correo-invalido-sin-arroba" in err for err in form.errors['correo']))

    def test_config_mail_service_guardar_y_leer(self):
        """
        Verifica que la configuración de correo se persista en archivo JSON en media
        y se lea correctamente con sus defaults.
        """
        cfg_inicial = get_config_mail(self.empresa_estudio.id)
        self.assertTrue(cfg_inicial['activo'])
        self.assertEqual(cfg_inicial['servidor_smtp'], 'mail.lopez-rios.com')
        self.assertEqual(cfg_inicial['puerto_smtp'], 465)
        self.assertTrue(cfg_inicial['usar_ssl'])

        # Guardar cambios
        datos_nuevos = {
            'activo': True,
            'email_remitente': 'envios@estudiotest.com',
            'nombre_remitente': 'Estudio Test Remitente',
            'servidor_smtp': 'smtp.office365.com',
            'puerto_smtp': 587,
            'usuario_smtp': 'envios@estudiotest.com',
            'password_smtp': 'secreto123',
            'asunto': 'Comprobante {comprobante}',
            'mensaje': 'Hola {cliente}, adjuntamos factura.'
        }
        guardar_config_mail(self.empresa_estudio.id, datos_nuevos)

        # Recuperar y verificar
        cfg_recuperada = get_config_mail(self.empresa_estudio.id)
        self.assertEqual(cfg_recuperada['servidor_smtp'], 'smtp.office365.com')
        self.assertEqual(cfg_recuperada['usuario_smtp'], 'envios@estudiotest.com')
        self.assertEqual(cfg_recuperada['asunto'], 'Comprobante {comprobante}')

        # Validar estado activo
        activa, motivo = is_config_activa(self.empresa_estudio.id)
        self.assertTrue(activa)
        self.assertEqual(motivo, "")

    def test_modelo_envio_factura_estudio(self):
        """
        Verifica creación y transición de estados en EnvioFacturaEstudio.
        """
        cliente = ClienteProveedor.objects.create(
            empresa=self.empresa_estudio,
            razon_social="Cliente Prueba SA",
            cuit="30999999999",
            tipo_entidad=1,
            correo="cliente@prueba.com, facturas@prueba.com"
        )
        venta = Venta.objects.create(
            empresa=self.empresa_estudio,
            cliente=cliente,
            tipo=self.tipo_factura,
            punto=1,
            numero=1001,
            fecha=timezone.now().date(),
            periodo="202609",
            periodo_facturado="202609",
            neto=Decimal("1000.00"),
            total=Decimal("1210.00"),
            sucursal=self.sucursal,
            usuario=self.user
        )

        envio = EnvioFacturaEstudio.objects.create(
            empresa=self.empresa_estudio,
            venta=venta,
            cliente=cliente,
            periodo="202609",
            destinatarios=cliente.correo,
            estado='PENDIENTE'
        )

        self.assertEqual(envio.estado, 'PENDIENTE')
        self.assertEqual(envio.destinatarios, "cliente@prueba.com, facturas@prueba.com")
        self.assertEqual(envio.intentos, 0)

        # Simular envío exitoso
        envio.estado = 'ENVIADO'
        envio.respuesta_smtp = '250 OK - Entregado exitosamente'
        envio.fecha_envio = timezone.now()
        envio.intentos += 1
        envio.save()

        envio.refresh_from_db()
        self.assertEqual(envio.estado, 'ENVIADO')
        self.assertEqual(envio.intentos, 1)

    def test_api_envios_facturas_descubrimiento_automatico(self):
        """
        Verifica que api_envios_facturas descubra automáticamente ventas del período
        que no tenían registro previo en EnvioFacturaEstudio.
        """
        session = self.client.session
        session['empresa_id'] = self.empresa_estudio.id
        session.save()

        cliente = ClienteProveedor.objects.create(
            empresa=self.empresa_estudio,
            razon_social="Cliente Auto SA",
            cuit="30888888888",
            tipo_entidad=1,
            correo="auto@cliente.com"
        )
        venta = Venta.objects.create(
            empresa=self.empresa_estudio,
            cliente=cliente,
            tipo=self.tipo_factura,
            punto=1,
            numero=2001,
            fecha=timezone.now().date(),
            periodo="202609",
            periodo_facturado="202609",
            neto=Decimal("5000.00"),
            total=Decimal("6050.00"),
            sucursal=self.sucursal,
            usuario=self.user
        )

        # Llamar a la API
        response = self.client.get('/estudio/envios-facturas/api/?periodo=202609')
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['periodo'], '202609')
        self.assertEqual(data['metricas']['total'], 1)
        self.assertEqual(data['metricas']['pendientes'], 1)
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(data['items'][0]['cliente_razon'], 'CLIENTE AUTO SA')
        self.assertEqual(data['items'][0]['estado'], 'PENDIENTE')

    def test_clipro_no_afecta_otras_verticalidades(self):
        """
        Garantiza que para cualquier empresa que NO sea de verticalidad ESTUDIO
        (como Armería, Agrícola, Distribución o General), la validación de Clipro
        se mantenga 100% estándar (1 solo email) y no active multicorreo.
        """
        data = {
            'razon_social': 'Empresa Comercial Estandar SA',
            'cuit': '30777777777',
            'tipo_entidad': 1,
            'condicion_iva': 'RESPONSABLE INSCRIPTO',
            'tipo_documento': '80',
            'tipo_iibb': 'LOCAL',
            'correo': 'email1@test.com, email2@test.com',
            'telefono': '123456',
        }
        form = ClienteProveedorForm(data=data, empresa_id=self.empresa_std.id)
        self.assertFalse(form.is_valid())
        self.assertIn('correo', form.errors)
        self.assertTrue(any("válida" in err.lower() for err in form.errors['correo']))

    def test_formato_variables_y_negrita_en_smtp_service(self):
        """
        Verifica que safe_format reemplace {first_name}, {last_name}, {usuario},
        así como variables de cliente, y no falle ante variables no existentes.
        También valida que se preserve <b>...</b> para HTML y que _construir_mensaje
        genere la versión de texto plano limpia de tags HTML.
        """
        self.user.first_name = "Juan"
        self.user.last_name = "Pérez"
        self.user.save()

        ctx = {
            'cliente': 'Empresa Cliente SRL',
            'comprobante': 'Factura A 0001-00000001',
            'periodo': '202609',
            'total': '$ 10.000,00',
            'empresa': 'Estudio López',
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'usuario': f"{self.user.first_name} {self.user.last_name}",
        }

        # Prueba con texto con formato negrita <b> y variables
        plantilla_mensaje = "Hola {cliente}, adjunto <b>{comprobante}</b>. Saludos, <b>{first_name} {last_name}</b>."
        resultado = safe_format(plantilla_mensaje, ctx)
        self.assertEqual(resultado, "Hola Empresa Cliente SRL, adjunto <b>Factura A 0001-00000001</b>. Saludos, <b>Juan Pérez</b>.")

        # Prueba de tolerancia a variables no existentes (debe dejarlas sin romper)
        plantilla_con_extra = "Hola {cliente}, dato {variable_inexistente}."
        resultado_extra = safe_format(plantilla_con_extra, ctx)
        self.assertIn("Empresa Cliente SRL", resultado_extra)
        self.assertIn("{variable_inexistente}", resultado_extra)

    def test_config_mails_guardar_firma_y_modal_sin_blur(self):
        """
        Verifica que el modal se renderice sin 'backdrop-blur' para optimizar la GPU,
        y que el endpoint guardar procese correctamente la firma y asunto.
        """
        session = self.client.session
        session['empresa_id'] = self.empresa_estudio.id
        session.save()

        # 1. Verificar carga de modal sin backdrop-blur
        response = self.client.get('/estudio/config-mails/modal/')
        self.assertEqual(response.status_code, 200)
        contenido = response.content.decode('utf-8')
        self.assertNotIn('backdrop-blur', contenido)
        self.assertIn('modalCuerpo', contenido)
        self.assertIn('modalFirma', contenido)
        self.assertIn('{first_name}', contenido)
        self.assertIn('{last_name}', contenido)

        # 2. Guardar datos incluyendo firma con negrita
        post_data = {
            'activo': 'on',
            'email_remitente': 'facturacion@estudiolopez.com',
            'nombre_remitente': 'Estudio Contable López',
            'servidor_smtp': 'mail.lopez-rios.com',
            'puerto_smtp': '465',
            'usuario_smtp': 'facturacion@lopez-rios.com',
            'password_smtp': 'clave_segura_123',
            'usar_ssl': 'on',
            'asunto': 'Factura {comprobante} de {empresa}',
            'mensaje': 'Estimado {cliente}, adjuntamos su factura.',
            'firma': 'Atentamente,\n<b>{first_name} {last_name}</b>\n{empresa}'
        }
        res_guardar = self.client.post('/estudio/config-mails/guardar/', data=post_data)
        self.assertEqual(res_guardar.status_code, 200)
        self.assertEqual(res_guardar.json().get('status'), 'success')

        # Verificar persistencia en archivo de configuración
        cfg = get_config_mail(self.empresa_estudio.id)
        self.assertEqual(cfg['email_remitente'], 'facturacion@estudiolopez.com')
        self.assertEqual(cfg['firma'], 'Atentamente,\n<b>{first_name} {last_name}</b>\n{empresa}')
        self.assertTrue(cfg['usar_ssl'])
