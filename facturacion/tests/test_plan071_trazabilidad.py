from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from empresas.models import Empresa, Sucursal, Ejercicio
from facturacion.models import ClienteProveedor, TipoComprobante, Venta, VentaItem
from productos.models import Producto, Subproducto
from facturacion.services.notas_credito import emitir_nota_credito_desde_venta

User = get_user_model()

class TrazabilidadPlan071Test(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.empresa = Empresa.objects.create(nombre="Armeria Test SA", cuit="30711111118", tipo_actividad="armeria")
        self.sucursal = Sucursal.objects.create(empresa=self.empresa, nombre="Central")
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa,
            inicio=timezone.localdate().replace(month=1, day=1),
            cierre=timezone.localdate().replace(month=12, day=31)
        )
        self.cliente = ClienteProveedor.objects.create(
            empresa=self.empresa,
            razon_social="Cliente Trazable",
            tipo_entidad=1
        )
        self.tipo_factura = TipoComprobante.objects.create(codigo='001', detalle='Factura A', signo=1)
        self.tipo_nc = TipoComprobante.objects.create(codigo='003', detalle='Nota de Crédito A', signo=-1)

        # Producto con trazabilidad activa (subprod = True)
        self.producto = Producto.objects.create(
            empresa=self.empresa,
            detalle="PISTOLA 9MM TRAZABLE",
            subprod=True,
            precio_neto=Decimal('1000.00'),
            precio_total=Decimal('1210.00')
        )

        # Subproducto registrado
        self.subproducto = Subproducto.objects.create(
            empresa=self.empresa,
            producto=self.producto,
            sucursal=self.sucursal,
            serie="SERIE-TEST-001",
            cuim="CUIM-TEST-001",
            feccpra=timezone.localdate(),
            cto_adq=Decimal('800.00'),
            situacion='DEPOSITO'
        )

        # Venta realizada
        self.venta = Venta.objects.create(
            empresa=self.empresa,
            sucursal=self.sucursal,
            ejercicio=self.ejercicio,
            cliente=self.cliente,
            tipo=self.tipo_factura,
            punto=1,
            numero=100,
            fecha=timezone.localdate(),
            periodo=timezone.localdate().strftime("%Y%m"),
            usuario=self.user,
            total=Decimal('1210.00')
        )
        self.venta_item = VentaItem.objects.create(
            venta=self.venta,
            producto=self.producto,
            cantidad=Decimal('1.00'),
            precio_unitario=Decimal('1000.00'),
            iva_alicuota=Decimal('21.00'),
            total=Decimal('1210.00')
        )

        # Vincular subproducto a la venta
        self.subproducto.situacion = 'VENDIDA'
        self.subproducto.venta = self.venta
        self.subproducto.fecvta = self.venta.fecha
        self.subproducto.precio_neto = Decimal('1000.00')
        self.subproducto.precio_total = Decimal('1210.00')
        self.subproducto.save()

    def test_reversion_trazabilidad_al_emitir_nota_credito(self):
        """
        Verifica que al emitir la Nota de Crédito por devolución del producto trazable,
        su situación pase a 'DEPOSITO' y la venta quede en None.
        """
        self.assertEqual(self.subproducto.situacion, 'VENDIDA')
        self.assertEqual(self.subproducto.venta, self.venta)

        # Emitir Nota de Crédito
        items_devolucion = {self.venta_item.id: 1}
        nc = emitir_nota_credito_desde_venta(self.venta, items_devolucion, self.user)

        self.assertIsNotNone(nc)
        
        # Refrescar subproducto desde la BD
        self.subproducto.refresh_from_db()
        self.assertEqual(self.subproducto.situacion, 'DEPOSITO')
        self.assertIsNone(self.subproducto.venta)
        self.assertIsNone(self.subproducto.fecvta)
        self.assertEqual(self.subproducto.precio_neto, Decimal('0.00'))
        self.assertEqual(self.subproducto.precio_total, Decimal('0.00'))

    def test_edicion_exclusiva_serie_y_cuim(self):
        """
        Verifica que la vista subproducto_editar_modal actualice únicamente la serie y el cuim.
        """
        client = Client()
        client.force_login(self.user)
        session = client.session
        session['empresa_id'] = self.empresa.id
        session['sucursal_id'] = self.sucursal.id
        session.save()

        # POST para editar SERIE y CUIM
        response = client.post(
            f'/stock/trazabilidad/subproducto/{self.subproducto.subpro}/editar/',
            {'serie': 'SERIE-NUEVA-999', 'cuim': 'CUIM-NUEVO-888'},
            HTTP_HX_REQUEST='true'
        )

        self.assertEqual(response.status_code, 200)
        self.subproducto.refresh_from_db()
        self.assertEqual(self.subproducto.serie, 'SERIE-NUEVA-999')
        self.assertEqual(self.subproducto.cuim, 'CUIM-NUEVO-888')

    def test_subproducto_detalle_modal(self):
        """
        Verifica que la vista subproducto_detalle_modal responda 200 con la plantilla de detalles.
        """
        client = Client()
        client.force_login(self.user)
        session = client.session
        session['empresa_id'] = self.empresa.id
        session.save()

        response = client.get(f'/stock/trazabilidad/subproducto/{self.subproducto.subpro}/detalle/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ficha de Trazabilidad")
        self.assertContains(response, "SERIE-TEST-001")
