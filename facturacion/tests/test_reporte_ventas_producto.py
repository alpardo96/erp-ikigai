from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

from empresas.models import Empresa, Sucursal, Ejercicio
from facturacion.models import ClienteProveedor, TipoComprobante, Venta, VentaItem
from productos.models import Producto, Rubro, Familia, Marca

User = get_user_model()


class ReporteVentasProductoTestCase(TestCase):
    def setUp(self):
        # Configuración de Entidades de Prueba
        self.empresa = Empresa.objects.create(nombre="EMPRESA PRUEBA SRL", cuit="30111111118")
        self.sucursal = Sucursal.objects.create(empresa=self.empresa, nombre="CASA CENTRAL")
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa,
            ejercicio="2026",
            inicio="2026-01-01",
            cierre="2026-12-31"
        )
        self.user = User.objects.create_user(username="testuser", password="password123")

        self.tipo_factura = TipoComprobante.objects.create(codigo="FB", detalle="FACTURA B", signo=1)

        self.cliente = ClienteProveedor.objects.create(
            empresa=self.empresa,
            razon_social="CLIENTE PRUEBA SA",
            tipo_entidad=1,
            cuit="20222222223"
        )

        self.rubro = Rubro.objects.create(empresa=self.empresa, detalle="RUBRO TEST")
        self.familia = Familia.objects.create(empresa=self.empresa, detalle="FAMILIA TEST", rubro=self.rubro)
        self.marca = Marca.objects.create(empresa=self.empresa, detalle="MARCA TEST")

        self.producto1 = Producto.objects.create(
            empresa=self.empresa,
            detalle="PRODUCTO 1 TEST",
            rubro=self.rubro,
            familia=self.familia,
            marca=self.marca,
            precio_neto=Decimal("1000.00"),
            precio_total=Decimal("1210.00")
        )

        self.producto2 = Producto.objects.create(
            empresa=self.empresa,
            detalle="PRODUCTO 2 TEST",
            rubro=self.rubro,
            familia=self.familia,
            precio_neto=Decimal("2000.00"),
            precio_total=Decimal("2420.00")
        )

        # Venta 1 (Fiscal - condic=1)
        self.venta1 = Venta.objects.create(
            empresa=self.empresa,
            sucursal=self.sucursal,
            ejercicio=self.ejercicio,
            usuario=self.user,
            vendedor=self.user,
            cliente=self.cliente,
            tipo=self.tipo_factura,
            punto=1,
            numero=100,
            fecha=timezone.localdate(),
            condic=1, # Fiscal
            neto=Decimal("1000.00"),
            iva=Decimal("210.00"),
            total=Decimal("1210.00"),
            estado=0
        )
        self.item1 = VentaItem.objects.create(
            venta=self.venta1,
            producto=self.producto1,
            cantidad=Decimal("2.00"),
            precio_unitario=Decimal("605.00"),
            iva_alicuota=Decimal("21.00"),
            total=Decimal("1210.00")
        )

        # Venta 2 (No Fiscal - condic=2)
        self.venta2 = Venta.objects.create(
            empresa=self.empresa,
            sucursal=self.sucursal,
            ejercicio=self.ejercicio,
            usuario=self.user,
            vendedor=self.user,
            cliente=self.cliente,
            tipo=self.tipo_factura,
            punto=1,
            numero=101,
            fecha=timezone.localdate(),
            condic=2, # No Fiscal
            neto=Decimal("2000.00"),
            iva=Decimal("420.00"),
            total=Decimal("2420.00"),
            estado=0
        )
        self.item2 = VentaItem.objects.create(
            venta=self.venta2,
            producto=self.producto2,
            cantidad=Decimal("1.00"),
            precio_unitario=Decimal("2420.00"),
            iva_alicuota=Decimal("21.00"),
            total=Decimal("2420.00")
        )

        self.client = Client()
        self.client.login(username="testuser", password="password123")

        # Configurar la empresa en la sesión
        session = self.client.session
        session['empresa_id'] = self.empresa.pk
        session['ejercicio_id'] = self.ejercicio.pk
        session.save()

    def test_reporte_ventas_producto_vista_principal(self):
        """Verifica la carga inicial del reporte de ventas por producto (200 OK y pantalla limpia de consulta inicial)."""
        url = reverse('reporte_ventas_producto')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reporte de Ventas por Producto")
        self.assertContains(response, "Seleccione los parámetros de consulta y presione \"Filtrar\"")

    def test_reporte_ventas_producto_filtrado_htmx(self):
        """Verifica la búsqueda asíncrona por HTMX filtrando por producto al enviar filtering=1."""
        url = reverse('reporte_ventas_producto_search')
        response = self.client.get(url, {
            'filtering': '1',
            'producto': self.producto1.pk,
            'desde': timezone.localdate().strftime('%Y-%m-%d'),
            'hasta': timezone.localdate().strftime('%Y-%m-%d'),
            'fiscal': 'on',
            'no_fiscal': 'on'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PRODUCTO 1 TEST")
        self.assertNotContains(response, "PRODUCTO 2 TEST")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PRODUCTO 1 TEST")
        self.assertNotContains(response, "PRODUCTO 2 TEST")

    def test_reporte_ventas_producto_filtrado_condicion_fiscal(self):
        """Verifica el filtrado por comprobantes fiscales (condic=1)."""
        url = reverse('reporte_ventas_producto_search')
        response = self.client.get(url, {
            'filtering': '1',
            'desde': timezone.localdate().strftime('%Y-%m-%d'),
            'hasta': timezone.localdate().strftime('%Y-%m-%d'),
            'fiscal': 'on', # Solo Fiscal
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PRODUCTO 1 TEST")
        self.assertNotContains(response, "PRODUCTO 2 TEST")

    def test_exportar_csv_74_columnas(self):
        """Verifica la exportación CSV y la presencia de la cabecera completa de 74 campos."""
        url = reverse('reporte_ventas_producto_csv')
        response = self.client.get(url, {
            'filtering': '1',
            'desde': timezone.localdate().strftime('%Y-%m-%d'),
            'hasta': timezone.localdate().strftime('%Y-%m-%d'),
            'fiscal': 'on',
            'no_fiscal': 'on'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/csv'))
        
        content = response.content.decode('utf-8-sig')
        lines = content.strip().split('\r\n')
        header_cols = lines[0].split(',')
        self.assertEqual(len(header_cols), 74)
        self.assertEqual(header_cols[0], 'id_vta')
        self.assertEqual(header_cols[-1], 'observa')

    def test_exportar_excel_formato(self):
        """Verifica que el reporte descargable en Excel devuelva status 200 y el mimetype correcto."""
        url = reverse('reporte_ventas_producto_excel')
        response = self.client.get(url, {
            'filtering': '1',
            'desde': timezone.localdate().strftime('%Y-%m-%d'),
            'hasta': timezone.localdate().strftime('%Y-%m-%d'),
            'fiscal': 'on',
            'no_fiscal': 'on'
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def test_domicilio_completo_propiedad(self):
        """Verifica la concatenación de domicilio, código postal, localidad y jurisdicción."""
        from facturacion.models import Jurisdiccion
        jur = Jurisdiccion.objects.create(codigo="01", nombre="BUENOS AIRES")
        cli = ClienteProveedor.objects.create(
            empresa=self.empresa,
            razon_social="JUAN PEREZ",
            tipo_entidad=1,
            cuit="20333333334",
            domicilio="AV CORRIENTES 1234",
            codigo_postal="1043",
            localidad="SAN NICOLAS",
            jurisdiccion=jur
        )
        self.assertEqual(cli.domicilio_completo, "AV CORRIENTES 1234 - CP: 1043 - SAN NICOLAS, BUENOS AIRES")

    def test_sincronizar_datos_cliente_venta(self):
        """Verifica que el endpoint venta_sincronizar_cliente actualice los campos snapshot de la venta."""
        self.cliente.razon_social = "CLIENTE ACTUALIZADO SA"
        self.cliente.cuit = "30777777779"
        self.cliente.domicilio = "NUEVA DIRECCION 456"
        self.cliente.codigo_postal = "1405"
        self.cliente.localidad = "CABALLITO"
        self.cliente.save()

        url = reverse('venta_sincronizar_cliente', args=[self.venta1.ventas_id])
        response = self.client.post(url, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)

        self.venta1.refresh_from_db()
        self.assertEqual(self.venta1.cliente_razon_social, "CLIENTE ACTUALIZADO SA")
        self.assertEqual(self.venta1.cliente_cuit, "30777777779")
        self.assertIn("NUEVA DIRECCION 456", self.venta1.cliente_domicilio)
        self.assertIn("1405", self.venta1.cliente_domicilio)

