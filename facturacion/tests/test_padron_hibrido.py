from django.test import TestCase
from unittest.mock import MagicMock, patch
from empresas.models import Empresa
from facturacion.services.afip_padron import AFIPPadronService


class AFIPPadronHibridoTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Empresa Test",
            cuit="30708395206",
            tipo_actividad="ESTUDIO"
        )

    @patch('facturacion.services.afip_padron.AFIPPadronService._configurar_credenciales')
    @patch('facturacion.services.afip_padron.aplicar_parche_ssl_afip')
    def test_combinacion_exitosa_a5_y_a13(self, mock_ssl, mock_cred):
        """
        Verifica que cuando ambos servicios responden, se extraiga la condición de IVA real
        y validez de A5 combinados con la identidad de A13.
        """
        service = AFIPPadronService(self.empresa)

        # Simular respuesta de A5 (Constancia)
        service._consultar_constancia = MagicMock(return_value={
            'cuit': '20123456789',
            'razon_social': 'PEREZ JUAN CARLOS',
            'tipo_persona': 'F',
            'condicion_iva': 'RESPONSABLE INSCRIPTO',
            'estado_afip': 'ACTIVO',
            'es_valido_afip': True,
            'domicilio': 'AV CORRIENTES 1234',
            'codigo_postal': '1043',
            'localidad': 'SAN NICOLAS',
            'provincia': 'CIUDAD AUTONOMA DE BUENOS AIRES',
            'actividades': ['SERVICIOS JURIDICOS']
        })

        # Simular respuesta de A13 (Padrón)
        service._consultar_padron_a13 = MagicMock(return_value={
            'cuit': '20123456789',
            'razon_social': 'PEREZ, JUAN CARLOS',
            'tipo_persona': 'F',
            'domicilio': 'AV CORRIENTES 1234 PISO 4',
            'codigo_postal': '1043',
            'provincia': 'CIUDAD AUTONOMA DE BUENOS AIRES',
            'localidad': 'SAN NICOLAS',
            'condicion_iva': 'CONSUMIDOR FINAL',
            'tipo_documento': '80',
            'apellido': 'PEREZ',
            'nombre': 'JUAN CARLOS'
        })

        resultado = service.consultar_cuit('20123456789')

        self.assertEqual(resultado['cuit'], '20123456789')
        self.assertEqual(resultado['razon_social'], 'PEREZ, JUAN CARLOS')
        self.assertEqual(resultado['condicion_iva'], 'RESPONSABLE INSCRIPTO')  # Prevalece el IVA real de A5
        self.assertTrue(resultado['es_valido_afip'])
        self.assertEqual(resultado['fuente'], 'A5+A13')
        self.assertIsNone(resultado['aviso'])

    @patch('facturacion.services.afip_padron.AFIPPadronService._configurar_credenciales')
    @patch('facturacion.services.afip_padron.aplicar_parche_ssl_afip')
    def test_resiliencia_cuando_a5_falla(self, mock_ssl, mock_cred):
        """
        Verifica que si A5 no está autorizado o falla, no se rompe y responde con A13 y aviso claro.
        """
        service = AFIPPadronService(self.empresa)

        # Simular falla de A5 (por ejemplo, falta de delegación en AFIP)
        service._consultar_constancia = MagicMock(side_effect=Exception("Computador no autorizado a acceder al servicio"))

        # A13 sí responde
        service._consultar_padron_a13 = MagicMock(return_value={
            'cuit': '20999999999',
            'razon_social': 'GARCIA, ANA',
            'tipo_persona': 'F',
            'domicilio': 'SAN MARTIN 456',
            'codigo_postal': '4000',
            'provincia': 'TUCUMAN',
            'localidad': 'SAN MIGUEL DE TUCUMAN',
            'condicion_iva': 'RESPONSABLE INSCRIPTO',
            'tipo_documento': '80',
            'apellido': 'GARCIA',
            'nombre': 'ANA'
        })

        resultado = service.consultar_cuit('20999999999')

        self.assertEqual(resultado['cuit'], '20999999999')
        self.assertEqual(resultado['razon_social'], 'GARCIA, ANA')
        self.assertEqual(resultado['fuente'], 'A13')
        self.assertIsNotNone(resultado['aviso'])
        self.assertIn("A13", resultado['aviso'])

    @patch('facturacion.services.afip_padron.AFIPPadronService._configurar_credenciales')
    @patch('facturacion.services.afip_padron.aplicar_parche_ssl_afip')
    def test_resiliencia_cuando_a13_falla(self, mock_ssl, mock_cred):
        """
        Verifica que si A13 falla, no se rompe y responde con A5 y aviso.
        """
        service = AFIPPadronService(self.empresa)

        # A5 responde con Monotributo
        service._consultar_constancia = MagicMock(return_value={
            'cuit': '27333333334',
            'razon_social': 'LOPEZ MARIA',
            'tipo_persona': 'F',
            'condicion_iva': 'MONOTRIBUTO',
            'estado_afip': 'ACTIVO',
            'es_valido_afip': True,
            'domicilio': 'BELGRANO 789',
            'codigo_postal': '4000',
            'localidad': 'SAN MIGUEL DE TUCUMAN',
            'provincia': 'TUCUMAN',
            'actividades': ['VENTA AL POR MENOR']
        })

        # A13 falla
        service._consultar_padron_a13 = MagicMock(side_effect=Exception("Timeout en servicio A13"))

        resultado = service.consultar_cuit('27333333334')

        self.assertEqual(resultado['cuit'], '27333333334')
        self.assertEqual(resultado['condicion_iva'], 'MONOTRIBUTO')
        self.assertEqual(resultado['fuente'], 'A5')
        self.assertIsNotNone(resultado['aviso'])
