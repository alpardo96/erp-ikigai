from django.test import TestCase, Client
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from empresas.models import Empresa, Sucursal
from productos.models import Producto, Rubro
from facturacion.models import ClienteProveedor, Preventa, PreventaItem
from verticalidades.armeria.models import ExtensionArmeria
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
        from verticalidades.armeria.forms import ExtensionArmeriaForm
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

    def test_preventas_item_add_formato_precio_ar(self):
        """Verifica que montos con formato argentino (ej. '444.808,00') o desformateados no se multipliquen por 100."""
        self.empresa.modo_edicion_facturacion = 'PRECIO'
        self.empresa.save()

        client = Client()
        client.force_login(self.user)
        session = client.session
        session['empresa_id'] = self.empresa.id
        session['sucursal_id'] = self.sucursal.id
        session['preventa_items_temp'] = []
        session.save()

        # Enviar precio en formato con puntos de miles y coma decimal
        response = client.post('/ventas/preventas/item/agregar/', {
            'producto_id': self.producto_creden.id,
            'credencial': '1234567',
            'cantidad': '1',
            'precio': '444.808,00',
            'descuento': '0'
        })
        self.assertEqual(response.status_code, 200)
        items = client.session['preventa_items_temp']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['precio_unitario'], 444808.0)
        self.assertEqual(items[0]['total'], 444808.0)

    def test_preventa_credencial_condicion_subprod(self):
        """Verifica que para armas (subprod=True) no se exija credencial en preventa, y para creden=True sin subprod sí se exija."""
        client = Client()
        client.force_login(self.user)
        session = client.session
        session['empresa_id'] = self.empresa.id
        session['sucursal_id'] = self.sucursal.id
        session['preventa_items_temp'] = []
        session.save()

        # 1. Producto arma (creden=True, subprod=True) -> NO debe exigir credencial en preventa (es anticipo)
        resp_arma = client.post('/ventas/preventas/item/agregar/', {
            'producto_id': self.producto_creden.id,
            'credencial': '',
            'cantidad': '1',
            'precio': '1000.00',
            'descuento': '0'
        })
        self.assertEqual(resp_arma.status_code, 200)
        self.assertNotIn("requiere CREDENCIAL", resp_arma.content.decode())
        self.assertEqual(len(client.session['preventa_items_temp']), 1)

        # 2. Producto munición/artículo controlado (creden=True, subprod=False) -> SÍ debe exigir credencial
        session['preventa_items_temp'] = []
        session.save()

        prod_municion = Producto.objects.create(
            id=102,
            empresa=self.empresa,
            detalle="Caja Municiones 9mm",
            precio_total=Decimal("50.00"),
            creden=True,
            subprod=False,
            rubro=self.rubro
        )
        resp_municion_sin_cred = client.post('/ventas/preventas/item/agregar/', {
            'producto_id': prod_municion.id,
            'credencial': '',
            'cantidad': '1',
            'precio': '50.00',
            'descuento': '0'
        })
        self.assertEqual(resp_municion_sin_cred.status_code, 200)
        self.assertIn("requiere CREDENCIAL", resp_municion_sin_cred.content.decode())



