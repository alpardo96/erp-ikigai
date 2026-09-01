from django.test import TestCase, Client
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from empresas.models import Empresa, Sucursal
from productos.models import Producto, Rubro
from facturacion.models import ClienteProveedor, ExtensionArmeria, Preventa, PreventaItem
from django.contrib.auth.models import User
from facturacion.helpers import validar_clu_cliente_armeria


class ArmeriaCredencialCLUTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Armería Prueba",
            cuit="30111111118",
            tipo_actividad="ARMERIA"
        )
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa,
            nombre="Sucursal Central",
            punto=1
        )
        self.user = User.objects.create_user(
            username="testuser",
            password="password123"
        )
        self.rubro = Rubro.objects.create(
            empresa=self.empresa,
            detalle="Armas",
            descuento_maximo=10.0
        )
        self.producto_creden = Producto.objects.create(
            id=101,
            empresa=self.empresa,
            detalle="Pistola 9mm",
            precio_total=Decimal("1000.00"),
            creden=True,
            subprod=True,
            rubro=self.rubro
        )
        self.cliente_valido = ClienteProveedor.objects.create(
            empresa=self.empresa,
            razon_social="Juan Perez",
            cuit="20123456789",
            tipo_entidad=1
        )
        ExtensionArmeria.objects.create(
            cliente=self.cliente_valido,
            clu="CLU-12345",
            clu_vto=timezone.localdate() + timedelta(days=30)
        )
        self.cliente_vencido = ClienteProveedor.objects.create(
            empresa=self.empresa,
            razon_social="Pedro Gomez",
            cuit="20987654321",
            tipo_entidad=1
        )
        ExtensionArmeria.objects.create(
            cliente=self.cliente_vencido,
            clu="CLU-99999",
            clu_vto=timezone.localdate() - timedelta(days=1)
        )

    def test_validar_clu_helper(self):
        # Valido
        valido, err = validar_clu_cliente_armeria(self.cliente_valido, self.empresa.id)
        self.assertTrue(valido)
        self.assertEqual(err, "")

        # Vencido
        valido, err = validar_clu_cliente_armeria(self.cliente_vencido, self.empresa.id)
        self.assertFalse(valido)
        self.assertIn("VENCIDO", err)

    def test_preventa_item_credencial_persistence(self):
        preventa = Preventa.objects.create(
            cliente=self.cliente_valido,
            vendedor=self.user,
            empresa=self.empresa,
            sucursal=self.sucursal,
            cliente_razon_social=self.cliente_valido.razon_social
        )
        item = PreventaItem.objects.create(
            preventa=preventa,
            producto=self.producto_creden,
            cantidad=1,
            precio_unitario=Decimal("1000.00"),
            credencial="CRED-998877",
            dmp=Decimal("1.00")
        )
        self.assertEqual(item.credencial, "CRED-998877")
        self.assertEqual(item.dmp, Decimal("1.00"))

    def test_extension_armeria_form_es_policia_select(self):
        from facturacion.forms import ExtensionArmeriaForm
        # Test con es_policia = True
        form_true = ExtensionArmeriaForm(data={'tipo_persona': 'F', 'clu': 'CLU-POLICIA', 'clu_vto': '2028-12-31', 'es_policia': 'true'})
        self.assertTrue(form_true.is_valid())
        self.assertTrue(form_true.cleaned_data['es_policia'])

        # Test con es_policia = False (Predeterminado / Civil)
        form_false = ExtensionArmeriaForm(data={'tipo_persona': 'F', 'clu': 'CLU-CIVIL', 'clu_vto': '2028-12-31', 'es_policia': 'false'})
        self.assertTrue(form_false.is_valid())
        self.assertFalse(form_false.cleaned_data['es_policia'])

    def test_buscar_clientes_armeria_columns(self):
        client = Client()
        session = client.session
        session['empresa_id'] = self.empresa.id
        session.save()

        response = client.get('/clientes/buscar/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'col-clu', response.content)
        self.assertIn(b'col-policia', response.content)

