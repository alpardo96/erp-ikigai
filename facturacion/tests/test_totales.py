from django.test import TestCase
from decimal import Decimal
from datetime import date
from django.contrib.auth import get_user_model

from empresas.models import Empresa, Sucursal
from productos.models import Producto
from facturacion.models import ClienteProveedor, TipoComprobante, Venta, VentaItem

User = get_user_model()

class RecalculoTotalesTestCase(TestCase):
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
        self.producto = Producto.objects.create(detalle="Producto 1", empresa=self.empresa)

        self.venta = Venta.objects.create(
            fecha=date.today(),
            tipo=self.tipo_cbte,
            punto=1,
            numero=1001,
            cliente=self.cliente,
            empresa=self.empresa,
            sucursal=self.sucursal,
            usuario=self.user,
            estado=0,
            p_iibb=Decimal("10.00")  # Ejemplo de percepción manual
        )

    def test_recalculo_automatico_de_totales(self):
        # Al inicio, los importes de venta deberían estar en 0 (excepto p_iibb = 10)
        self.assertEqual(self.venta.neto, 0)
        self.assertEqual(self.venta.total, Decimal("10.00")) # Solo tiene la percepcion por ahora
        
        # Agregamos ítem 1: 21% IVA, Total con IVA = 121.00 (Neto = 100, IVA = 21)
        VentaItem.objects.create(
            venta=self.venta,
            producto=self.producto,
            cantidad=Decimal("1.00"),
            precio_unitario=Decimal("121.00"),
            iva_alicuota=Decimal("21.00"),
            total=Decimal("121.00")
        )

        # La venta se auto-recalcula mediante la signal post_save del VentaItem
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.neto, Decimal("100.00"))
        self.assertEqual(self.venta.iva, Decimal("21.00"))
        self.assertEqual(self.venta.total, Decimal("131.00")) # 100 + 21 + 10(iibb)

        # Agregamos ítem 2: 10.5% IVA, Total con IVA = 110.50 (Neto = 100, IVA = 10.50)
        VentaItem.objects.create(
            venta=self.venta,
            producto=self.producto,
            cantidad=Decimal("1.00"),
            precio_unitario=Decimal("110.50"),
            iva_alicuota=Decimal("10.50"),
            total=Decimal("110.50")
        )

        self.venta.refresh_from_db()
        self.assertEqual(self.venta.neto, Decimal("200.00"))
        self.assertEqual(self.venta.iva, Decimal("31.50"))
        self.assertEqual(self.venta.total, Decimal("241.50")) # 200 + 31.50 + 10
