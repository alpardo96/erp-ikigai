from django.test import TestCase
from decimal import Decimal
from datetime import date
from django.contrib.auth import get_user_model

from empresas.models import Empresa, Sucursal
from facturacion.models import ClienteProveedor, TipoComprobante, Venta, VentaAlicuotaIva
from facturacion.services.afip_service import AFIPService

User = get_user_model()


class AFIPServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test_arca_user', password='password123')
        # Usamos la empresa real con CUIT 20399738300 en DB si existe, o creamos una de prueba
        self.empresa_real = Empresa.objects.filter(cuit="20399738300").first()
        if not self.empresa_real:
            self.empresa_real = Empresa.objects.create(
                nombre="Empresa ARCA Test",
                cuit="20399738300",
                entorno_afip="HOM",
                crt_afip="certificados_afip/certificado_cortiz.crt",
                key_afip="certificados_afip/privada.key"
            )
        self.sucursal = Sucursal.objects.filter(empresa=self.empresa_real).first()
        if not self.sucursal:
            self.sucursal = Sucursal.objects.create(nombre="Sucursal 1", empresa=self.empresa_real)

        self.cliente = ClienteProveedor.objects.create(
            razon_social="Cliente Consumidor Final",
            tipo_entidad=1,
            cuit="0",
            tipo_documento="99",
            condicion_iva="CONSUMIDOR FINAL",
            empresa=self.empresa_real
        )
        self.tipo_cbte = TipoComprobante.objects.filter(codigo="6").first()
        if not self.tipo_cbte:
            self.tipo_cbte = TipoComprobante.objects.create(codigo="6", detalle="Factura B")

    def test_emitir_comprobante_homologacion_real(self):
        """
        Prueba de integración real con los servidores WSFEv1 de ARCA en Homologación
        utilizando las credenciales de Ikigai (CUIT 20399738300).
        """
        if not self.empresa_real.crt_afip or not self.empresa_real.key_afip:
            self.skipTest("No se encuentran los certificados en la empresa real para la prueba de integración.")

        afip_service = AFIPService(self.empresa_real)

        datos_factura = {
            'pto_vta': 1,
            'cbte_tipo': 6,  # Factura B
            'concepto': 1,   # Productos
            'doc_tipo': 99,  # Consumidor Final
            'doc_nro': 0,
            'cbte_fch': date.today().strftime('%Y%m%d'),
            'imp_total': 121.0,
            'imp_tot_conc': 0.0,
            'imp_neto': 100.0,
            'imp_op_ex': 0.0,
            'imp_iva': 21.0,
            'condicion_iva_receptor_id': 5  # Consumidor Final
        }
        alicuotas = [
            {
                'id_iva': 5,  # 21%
                'alicuota': Decimal('21.00'),
                'base_imponible': Decimal('100.00'),
                'importe_iva': Decimal('21.00')
            }
        ]

        res = afip_service.emitir_comprobante(datos_factura, alicuotas)
        self.assertTrue(res['exito'], f"Rechazo ARCA: {res.get('error')}")
        self.assertIsNotNone(res.get('cae'))
        self.assertEqual(len(str(res['cae'])), 14, "El CAE devuelto por ARCA debe tener 14 dígitos")
        self.assertGreater(res['numero_comprobante'], 0)
        self.assertIn('cod_qr', res)

    def test_creacion_venta_alicuota_iva(self):
        venta = Venta.objects.create(
            fecha=date.today(),
            tipo=self.tipo_cbte,
            punto=1,
            numero=9999,
            cliente=self.cliente,
            empresa=self.empresa_real,
            sucursal=self.sucursal,
            usuario=self.user,
            estado=2,
            cae="70417000000000",
            vto_cae="2026-08-05"
        )
        
        # Registrar alícuotas discriminadas (21% y 10.5%)
        VentaAlicuotaIva.objects.create(
            venta=venta,
            id_iva=5,  # 21%
            alicuota=Decimal('21.00'),
            base_imponible=Decimal('100.00'),
            importe_iva=Decimal('21.00')
        )
        VentaAlicuotaIva.objects.create(
            venta=venta,
            id_iva=4,  # 10.5%
            alicuota=Decimal('10.50'),
            base_imponible=Decimal('200.00'),
            importe_iva=Decimal('21.00')
        )

        self.assertEqual(venta.alicuotas_iva.count(), 2)
        total_iva = sum(a.importe_iva for a in venta.alicuotas_iva.all())
        self.assertEqual(total_iva, Decimal('42.00'))
