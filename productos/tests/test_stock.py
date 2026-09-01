from django.test import TestCase
from decimal import Decimal
from datetime import date
from django.contrib.auth import get_user_model

from empresas.models import Empresa, Sucursal
from productos.models import Producto, StockSucursal
from facturacion.models import ClienteProveedor, TipoComprobante, Venta, VentaItem

User = get_user_model()

class StockAutomationTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test_user', password='password')
        self.empresa = Empresa.objects.create(nombre="Test Empresa")
        self.sucursal = Sucursal.objects.create(nombre="Sucursal Test", empresa=self.empresa)
        self.cliente = ClienteProveedor.objects.create(
            razon_social="Test Cliente", 
            tipo_entidad=1,
            empresa=self.empresa
        )
        self.tipo_cbte = TipoComprobante.objects.create(codigo="1", detalle="Factura A")
        self.producto = Producto.objects.create(
            detalle="Producto de Prueba",
            empresa=self.empresa
        )

        self.venta = Venta.objects.create(
            fecha=date.today(),
            tipo=self.tipo_cbte,
            punto=1,
            numero=1001,
            cliente=self.cliente,
            empresa=self.empresa,
            sucursal=self.sucursal,
            usuario=self.user,
            estado=0
        )

    def test_venta_item_resta_stock(self):
        # Aseguramos que inicialmente no hay stock o es 0
        stock, _ = StockSucursal.objects.get_or_create(producto=self.producto, sucursal=self.sucursal, defaults={'cantidad': 0})
        self.assertEqual(stock.cantidad, 0)

        # Agregamos 5 unidades en la venta
        item = VentaItem.objects.create(
            venta=self.venta,
            producto=self.producto,
            cantidad=Decimal("5.00"),
            precio_unitario=Decimal("100.00"),
            iva_alicuota=Decimal("21.00"),
            total=Decimal("500.00")
        )

        # El stock debe bajar 5
        stock.refresh_from_db()
        self.assertEqual(stock.cantidad, Decimal("-5.00"))

        # Si borramos el ítem, el stock debe volver a subir
        item.delete()
        stock.refresh_from_db()
        self.assertEqual(stock.cantidad, Decimal("0.00"))

    def test_edicion_cantidad_venta_item(self):
        # Creamos ítem con 2 unidades (stock debería ser -2)
        item = VentaItem.objects.create(
            venta=self.venta,
            producto=self.producto,
            cantidad=Decimal("2.00"),
            precio_unitario=Decimal("100.00"),
            iva_alicuota=Decimal("21.00"),
            total=Decimal("200.00")
        )
        
        stock = StockSucursal.objects.get(producto=self.producto, sucursal=self.sucursal)
        self.assertEqual(stock.cantidad, Decimal("-2.00"))

        # Simulamos que un usuario edita la cantidad a 5
        item.cantidad = Decimal("5.00")
        item.save()

        # El delta fue -3 adicionales (pasó de 2 a 5). El stock final debe ser -5
        stock.refresh_from_db()
        self.assertEqual(stock.cantidad, Decimal("-5.00"))
