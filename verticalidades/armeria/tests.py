from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from empresas.models import Empresa, Sucursal, Ejercicio
from facturacion.models import ClienteProveedor, Preventa
from productos.models import Producto, Subproducto
from tesoreria.models import Recibo
from verticalidades.armeria.models import ReservaArma

User = get_user_model()

class ReservaArmaListViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='operador_armeria', password='password123')
        self.client = Client()
        self.client.login(username='operador_armeria', password='password123')

        self.empresa = Empresa.objects.create(nombre="Armeria Sigimac SA", cuit="30799999991", tipo_actividad="armeria")
        self.sucursal = Sucursal.objects.create(empresa=self.empresa, nombre="Casa Central")
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa,
            inicio=timezone.localdate().replace(month=1, day=1),
            cierre=timezone.localdate().replace(month=12, day=31)
        )

        session = self.client.session
        session['empresa_id'] = self.empresa.id
        session['sucursal_id'] = self.sucursal.id
        session.save()

        # Clientes
        self.cliente_1 = ClienteProveedor.objects.create(
            empresa=self.empresa,
            razon_social="Carlos Perez",
            cuit="20301112229",
            telefono="1144556677",
            tipo_entidad=1
        )
        self.cliente_2 = ClienteProveedor.objects.create(
            empresa=self.empresa,
            razon_social="Mariana Gonzalez",
            cuit="27402223334",
            telefono="1199887766",
            tipo_entidad=1
        )

        # Productos
        self.producto_1 = Producto.objects.create(
            empresa=self.empresa,
            detalle="PISTOLA GLOCK 17 GEN 5",
            cod_prov="GLK-17",
            cod_fab="FAB-991",
            subprod=True
        )
        self.producto_2 = Producto.objects.create(
            empresa=self.empresa,
            detalle="CARABINA RUGER 10/22",
            cod_prov="RUG-22",
            cod_fab="FAB-882",
            subprod=True
        )

        # Subproductos (números de serie)
        self.subproducto_1 = Subproducto.objects.create(
            empresa=self.empresa,
            producto=self.producto_1,
            sucursal=self.sucursal,
            serie="SERIE-GLK-99001",
            cuim="CUIM-99001",
            feccpra=timezone.localdate(),
            cto_adq=Decimal('500.00'),
            situacion='DEPOSITO'
        )

        # Preventas
        self.preventa_1 = Preventa.objects.create(
            empresa=self.empresa,
            sucursal=self.sucursal,
            cliente=self.cliente_1,
            total=Decimal('1000.00')
        )
        self.preventa_2 = Preventa.objects.create(
            empresa=self.empresa,
            sucursal=self.sucursal,
            cliente=self.cliente_2,
            total=Decimal('1500.00')
        )

        # Recibos
        self.recibo_1 = Recibo.objects.create(
            empresa=self.empresa,
            sucursal=self.sucursal,
            ejercicio=self.ejercicio,
            cliente=self.cliente_1,
            fecha=timezone.localdate(),
            numero=1055,
            total=Decimal('300.00'),
            observaciones="Seña 30% reserva Glock"
        )
        self.recibo_2 = Recibo.objects.create(
            empresa=self.empresa,
            sucursal=self.sucursal,
            ejercicio=self.ejercicio,
            cliente=self.cliente_2,
            fecha=timezone.localdate(),
            numero=1056,
            total=Decimal('450.00'),
            observaciones="Seña Ruger"
        )

        # Reservas de Armas
        self.reserva_1 = ReservaArma.objects.create(
            empresa=self.empresa,
            sucursal=self.sucursal,
            preventa=self.preventa_1,
            cliente=self.cliente_1,
            producto=self.producto_1,
            recibo_reserva=self.recibo_1,
            monto_reservado=Decimal('300.00'),
            monto_total=Decimal('1000.00'),
            estado='PENDIENTE'
        )
        self.reserva_2 = ReservaArma.objects.create(
            empresa=self.empresa,
            sucursal=self.sucursal,
            preventa=self.preventa_2,
            cliente=self.cliente_2,
            producto=self.producto_2,
            recibo_reserva=self.recibo_2,
            monto_reservado=Decimal('450.00'),
            monto_total=Decimal('1500.00'),
            estado='APLICADA'
        )

    def test_listado_completo_no_htmx(self):
        url = reverse('armeria_reservas_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'armeria/reservas_list.html')
        self.assertTemplateUsed(response, 'armeria/partials/reservas_tabla_parcial.html')
        self.assertIn(self.reserva_1, response.context['reservas'])

    def test_respuesta_parcial_htmx(self):
        url = reverse('armeria_reservas_list')
        response = self.client.get(url, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'armeria/partials/reservas_tabla_parcial.html')
        self.assertTemplateNotUsed(response, 'base.html')

    def test_busqueda_inteligente_por_cliente(self):
        url = reverse('armeria_reservas_list')
        # Por razón social
        res_nombre = self.client.get(url, {'q': 'Perez'})
        self.assertIn(self.reserva_1, res_nombre.context['reservas'])
        self.assertNotIn(self.reserva_2, res_nombre.context['reservas'])

        # Por CUIT
        res_cuit = self.client.get(url, {'q': '27402223334'})
        self.assertIn(self.reserva_2, res_cuit.context['reservas'])
        self.assertNotIn(self.reserva_1, res_cuit.context['reservas'])

    def test_busqueda_inteligente_por_producto_y_subproducto(self):
        url = reverse('armeria_reservas_list')
        # Por detalle de producto
        res_prod = self.client.get(url, {'q': 'Glock 17'})
        self.assertIn(self.reserva_1, res_prod.context['reservas'])
        self.assertNotIn(self.reserva_2, res_prod.context['reservas'])

        # Por número de serie del subproducto
        res_serie = self.client.get(url, {'q': 'SERIE-GLK-99001'})
        self.assertIn(self.reserva_1, res_serie.context['reservas'])
        self.assertNotIn(self.reserva_2, res_serie.context['reservas'])

        # Por CUIM
        res_cuim = self.client.get(url, {'q': 'CUIM-99001'})
        self.assertIn(self.reserva_1, res_cuim.context['reservas'])

    def test_busqueda_inteligente_por_recibo(self):
        url = reverse('armeria_reservas_list')
        # Por número de recibo
        res_recibo = self.client.get(url, {'q': '1055'})
        self.assertIn(self.reserva_1, res_recibo.context['reservas'])
        self.assertNotIn(self.reserva_2, res_recibo.context['reservas'])

    def test_filtrado_por_estado_sigimac(self):
        url = reverse('armeria_reservas_list')
        res_pend = self.client.get(url, {'estado': 'PENDIENTE'})
        self.assertIn(self.reserva_1, res_pend.context['reservas'])
        self.assertNotIn(self.reserva_2, res_pend.context['reservas'])

        res_aplicadas = self.client.get(url, {'estado': 'APLICADA'})
        self.assertIn(self.reserva_2, res_aplicadas.context['reservas'])
        self.assertNotIn(self.reserva_1, res_aplicadas.context['reservas'])
