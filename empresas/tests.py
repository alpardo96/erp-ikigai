from datetime import date, timedelta
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from empresas.models import Empresa

class VencimientoCertificadoTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Empresa Test Certificados",
            cuit="30712345678",
            condicion_iva="RESPONSABLE INSCRIPTO"
        )

    def test_empresa_sin_certificado(self):
        """Verifica que si no hay certificado ni vencimiento, la alerta esté inactiva."""
        estado = self.empresa.estado_vencimiento_crt
        self.assertFalse(estado['tiene_certificado'])
        self.assertFalse(estado['es_advertencia'])
        self.assertFalse(estado['es_vencido'])
        self.assertIsNone(self.empresa.dias_hasta_vencimiento_crt)

    def test_certificado_vigente_mas_de_15_dias(self):
        """Verifica que un certificado con más de 15 días de vigencia no dispare advertencia."""
        self.empresa.crt_afip = SimpleUploadedFile("cert_test.crt", b"dummy cert data")
        self.empresa.vencimiento_crt_afip = date.today() + timedelta(days=30)
        self.empresa.save()

        estado = self.empresa.estado_vencimiento_crt
        self.assertTrue(estado['tiene_certificado'])
        self.assertFalse(estado['es_advertencia'])
        self.assertFalse(estado['es_vencido'])
        self.assertEqual(estado['nivel'], 'success')
        self.assertEqual(self.empresa.dias_hasta_vencimiento_crt, 30)

    def test_certificado_proximo_a_vencer_15_dias(self):
        """Verifica que un certificado que vence en 15 días active la advertencia (es_advertencia=True)."""
        self.empresa.crt_afip = SimpleUploadedFile("cert_test.crt", b"dummy cert data")
        self.empresa.vencimiento_crt_afip = date.today() + timedelta(days=15)
        self.empresa.save()

        estado = self.empresa.estado_vencimiento_crt
        self.assertTrue(estado['tiene_certificado'])
        self.assertTrue(estado['es_advertencia'])
        self.assertFalse(estado['es_vencido'])
        self.assertEqual(estado['nivel'], 'warning')
        self.assertEqual(self.empresa.dias_hasta_vencimiento_crt, 15)

    def test_certificado_proximo_a_vencer_urgente_3_dias(self):
        """Verifica que un certificado que vence en 3 días tenga nivel de peligro (danger)."""
        self.empresa.crt_afip = SimpleUploadedFile("cert_test.crt", b"dummy cert data")
        self.empresa.vencimiento_crt_afip = date.today() + timedelta(days=3)
        self.empresa.save()

        estado = self.empresa.estado_vencimiento_crt
        self.assertTrue(estado['es_advertencia'])
        self.assertFalse(estado['es_vencido'])
        self.assertEqual(estado['nivel'], 'danger')
        self.assertEqual(self.empresa.dias_hasta_vencimiento_crt, 3)

    def test_certificado_vencido(self):
        """Verifica que un certificado cuyo vencimiento ya pasó active la alerta crítica (es_vencido=True)."""
        self.empresa.crt_afip = SimpleUploadedFile("cert_test.crt", b"dummy cert data")
        self.empresa.vencimiento_crt_afip = date.today() - timedelta(days=5)
        self.empresa.save()

        estado = self.empresa.estado_vencimiento_crt
        self.assertTrue(estado['tiene_certificado'])
        self.assertTrue(estado['es_advertencia'])
        self.assertTrue(estado['es_vencido'])
        self.assertEqual(estado['nivel'], 'danger')
        self.assertEqual(self.empresa.dias_hasta_vencimiento_crt, -5)
        self.assertIn("VENCIÓ hace 5 día(s)", estado['mensaje'])

    def test_context_processor_alerta_activada(self):
        """Verifica que el context processor global inyecte alerta_certificado_afip cuando corresponda."""
        from core.context_processors import context_context
        from django.test import RequestFactory

        self.empresa.crt_afip = SimpleUploadedFile("cert_test.crt", b"dummy cert data")
        self.empresa.vencimiento_crt_afip = date.today() + timedelta(days=10)
        self.empresa.save()

        factory = RequestFactory()
        request = factory.get('/')
        request.session = {'empresa_id': self.empresa.id}

        context = context_context(request)
        self.assertIsNotNone(context['alerta_certificado_afip'])
        self.assertEqual(context['alerta_certificado_afip']['dias'], 10)
