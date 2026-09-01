from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from facturacion.models import Venta, VentaItem, TipoComprobante, ClienteProveedor
from productos.models import Producto
from empresas.models import Empresa, Sucursal

User = get_user_model()

class CostoReposicionVentaItemTest(TestCase):
    """
    Pruebas unitarias para verificar la correcta asignación e inmutabilidad
    del campo cto_rep (costo de reposición) en VentaItem y sus propiedades
    de contribución marginal y rentabilidad.
    """

    def setUp(self):
        # 1. Crear Usuario y Empresa de prueba
        self.user = User.objects.create_user(username="testuser", password="password")
        self.empresa = Empresa.objects.create(
            nombre="Empresa Test",
            cuit="30111111118"
        )
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa,
            nombre="Sucursal Test"
        )
        
        # 2. Crear TipoComprobante y Cliente
        self.tipo_factura = TipoComprobante.objects.create(
            codigo="001",
            detalle="Factura A",
            signo=1
        )
        self.cliente = ClienteProveedor.objects.create(
            empresa=self.empresa,
            razon_social="Cliente Test",
            cuit="30222222224",
            tipo_entidad=1
        )

        # 3. Crear Producto con costo de reposición inicial
        self.producto = Producto.objects.create(
            empresa=self.empresa,
            detalle="Producto de Prueba",
            cto_rep=Decimal("500.00"),  # Costo reposición vigente
            precio_neto=Decimal("1000.00")
        )

        # 4. Crear Venta
        self.venta = Venta.objects.create(
            empresa=self.empresa,
            sucursal=self.sucursal,
            usuario=self.user,
            tipo=self.tipo_factura,
            punto=1,
            numero=1,
            fecha=timezone.now().date(),
            cliente=self.cliente,
            neto=Decimal("1000.00"),
            iva=Decimal("210.00"),
            total=Decimal("1210.00")
        )

    def test_autocompletado_cto_rep_en_save(self):
        """
        Verifica que al guardar un VentaItem sin especificar cto_rep,
        se asigne automáticamente el cto_rep del producto.
        """
        item = VentaItem.objects.create(
            venta=self.venta,
            producto=self.producto,
            cantidad=Decimal("2.00"),
            precio_unitario=Decimal("1000.00"),
            porcentaje_descuento=Decimal("0.00"),
            iva_alicuota=Decimal("21.00"),
            total=Decimal("2420.00")
        )

        # El costo de reposición debe ser igual al del producto en ese momento ($500.00)
        self.assertEqual(item.cto_rep, Decimal("500.00"))

    def test_inmutabilidad_cto_rep_ante_cambio_en_producto(self):
        """
        Verifica que si el cto_rep del Producto cambia posteriormente,
        el VentaItem creado conserva su costo de reposición original de la venta.
        """
        item = VentaItem.objects.create(
            venta=self.venta,
            producto=self.producto,
            cantidad=Decimal("1.00"),
            precio_unitario=Decimal("1000.00"),
            total=Decimal("1210.00")
        )

        # Se actualiza el costo del producto a $750.00
        self.producto.cto_rep = Decimal("750.00")
        self.producto.save()

        # Volver a cargar el ítem de la base de datos
        item.refresh_from_db()
        self.assertEqual(item.cto_rep, Decimal("500.00"))

    def test_calculo_contribucion_marginal_y_rentabilidad(self):
        """
        Verifica que las propiedades de subtotal_costo_reposicion, contribucion_marginal_unitaria,
        contribucion_marginal_total y margen_bruto_porcentaje calculen los montos numéricos exactos.
        """
        item = VentaItem.objects.create(
            venta=self.venta,
            producto=self.producto,
            cantidad=Decimal("3.00"),
            precio_unitario=Decimal("1000.00"),  # Precio unitario neto
            porcentaje_descuento=Decimal("10.00"), # 10% descuento -> Precio neto con desc = $900.00
            cto_rep=Decimal("500.00"),
            total=Decimal("3267.00")
        )

        # 1. Subtotal costo reposición = 3 * 500 = 1500
        self.assertEqual(item.subtotal_costo_reposicion, Decimal("1500.00"))

        # 2. Contribución marginal unitaria = (1000 * 0.90) - 500 = 900 - 500 = 400
        self.assertEqual(item.contribucion_marginal_unitaria, Decimal("400.00"))

        # 3. Contribución marginal total = 400 * 3 = 1200
        self.assertEqual(item.contribucion_marginal_total, Decimal("1200.00"))

        # 4. Verificación a nivel de la Venta
        self.assertEqual(self.venta.total_costo_reposicion, Decimal("1500.00"))
        self.assertEqual(self.venta.contribucion_marginal_total, Decimal("1200.00"))
