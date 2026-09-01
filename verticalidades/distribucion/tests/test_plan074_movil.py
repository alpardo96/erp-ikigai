"""Tests de la toma de pedidos desde el celular (Plan 074, fase 2)."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from verticalidades.distribucion.models import CarteraVendedor, ExtensionPedidoDistribucion, Personal
from verticalidades.distribucion.services import carrito
from empresas.models import Empresa, Sucursal
from facturacion.models import ClienteProveedor,  Preventa
from verticalidades.distribucion.models import ExtensionDistribuidora
from productos.models import Producto, StockSucursal
from usuarios.models import Perfil


class BaseMovilTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Distribuidora Prueba", cuit="30111111118",
            tipo_actividad="DISTRIBUIDORA")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, nombre="Depósito Central", punto=1)

        self.usuario = User.objects.create_user(username="juanv", password="clave123")
        Perfil.objects.create(usuario=self.usuario).empresas.add(self.empresa)
        self.vendedor = Personal.objects.create(
            empresa=self.empresa, nombre="Juan", es_vendedor=True, usuario=self.usuario)

        self.cliente = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="Almacén Don José", tipo_entidad=1,
            limite=Decimal('100000.00'))
        ExtensionDistribuidora.objects.create(
            cliente=self.cliente, coeficiente_mayorista=Decimal('0.9000'))
        CarteraVendedor.objects.create(
            empresa=self.empresa, vendedor=self.vendedor, cliente=self.cliente)

        # Cliente de otro vendedor: no debe aparecer en la cartera de Juan.
        self.cliente_ajeno = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="Kiosco La Esquina", tipo_entidad=1)

        self.producto = Producto.objects.create(
            empresa=self.empresa, detalle="Yogur x 900 vainilla",
            precio_total=Decimal('1690.00'), codigo_anterior="3002")
        StockSucursal.objects.create(
            producto=self.producto, sucursal=self.sucursal,
            stock_inicial=Decimal('50.00'), cantidad=Decimal('50.00'))

        self.client = Client()
        self.client.force_login(self.usuario)
        sesion = self.client.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion.save()

    def elegir_cliente(self, cliente=None):
        cliente = cliente or self.cliente
        return self.client.post(reverse('distribucion_movil_elegir_cliente',
                                        args=[cliente.codigo_id]))


class BusquedaPorCodigoTestCase(BaseMovilTestCase):
    def test_encuentra_por_id_del_erp(self):
        encontrado = carrito.buscar_producto_por_codigo(str(self.producto.id), self.empresa.id)
        self.assertEqual(encontrado, self.producto)

    def test_encuentra_por_codigo_del_sistema_anterior(self):
        """Durante la transición conviven los dos códigos y el vendedor usa el que recuerda."""
        otro = Producto.objects.create(
            empresa=self.empresa, detalle="Leche sachet", codigo_anterior="1001")
        self.assertEqual(carrito.buscar_producto_por_codigo("1001", self.empresa.id), otro)

    def test_el_id_del_erp_tiene_prioridad_sobre_el_anterior(self):
        """Si un código existe como ID y como código anterior de otro, gana el ID."""
        colision = Producto.objects.create(
            empresa=self.empresa, detalle="Colisión",
            codigo_anterior=str(self.producto.id))
        encontrado = carrito.buscar_producto_por_codigo(str(self.producto.id), self.empresa.id)
        self.assertEqual(encontrado, self.producto)
        self.assertNotEqual(encontrado, colision)

    def test_no_cruza_empresas(self):
        otra = Empresa.objects.create(nombre="Otra", cuit="30222222229",
                                      tipo_actividad="DISTRIBUIDORA")
        ajeno = Producto.objects.create(empresa=otra, detalle="Ajeno", codigo_anterior="9999")
        self.assertIsNone(carrito.buscar_producto_por_codigo("9999", self.empresa.id))
        self.assertEqual(carrito.buscar_producto_por_codigo("9999", otra.id), ajeno)

    def test_codigo_inexistente_devuelve_none(self):
        self.assertIsNone(carrito.buscar_producto_por_codigo("777777", self.empresa.id))


class CarteraEnElMovilTestCase(BaseMovilTestCase):
    def test_el_typeahead_solo_muestra_la_cartera_del_vendedor(self):
        respuesta = self.client.get(reverse('distribucion_movil_clientes'), {'q': ''})
        contenido = respuesta.content.decode('utf-8')
        self.assertIn("ALMACÉN DON JOSÉ", contenido.upper())
        self.assertNotIn("KIOSCO LA ESQUINA", contenido.upper())

    def test_no_se_puede_elegir_un_cliente_fuera_de_la_cartera(self):
        respuesta = self.elegir_cliente(self.cliente_ajeno)
        self.assertEqual(respuesta.status_code, 404)


class CargaDeItemsTestCase(BaseMovilTestCase):
    def test_agrega_por_codigo_con_el_precio_del_coeficiente(self):
        self.elegir_cliente()
        self.client.post(reverse('distribucion_movil_item_add'),
                         {'codigo': str(self.producto.id), 'cantidad': '10'})
        items = self.client.session[carrito.CLAVE_ITEMS]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['precio_unitario'], 1521.0)   # 1690 * 0,90
        self.assertEqual(items[0]['total'], 15210.0)

    def test_ignora_el_precio_que_manda_el_navegador(self):
        """El precio se resuelve en el servidor: no se confía en el cliente."""
        self.elegir_cliente()
        self.client.post(reverse('distribucion_movil_item_add'),
                         {'codigo': str(self.producto.id), 'cantidad': '1', 'precio': '1'})
        items = self.client.session[carrito.CLAVE_ITEMS]
        self.assertEqual(items[0]['precio_unitario'], 1521.0)

    def test_cargar_dos_veces_el_mismo_articulo_acumula(self):
        """En la calle el cliente vuelve sobre un artículo: se suma, no se rechaza."""
        self.elegir_cliente()
        for _ in range(2):
            self.client.post(reverse('distribucion_movil_item_add'),
                             {'codigo': str(self.producto.id), 'cantidad': '5'})
        items = self.client.session[carrito.CLAVE_ITEMS]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['cantidad'], 10.0)

    def test_cantidad_en_formato_es_ar(self):
        self.elegir_cliente()
        self.client.post(reverse('distribucion_movil_item_add'),
                         {'codigo': str(self.producto.id), 'cantidad': '1.234,50'})
        items = self.client.session[carrito.CLAVE_ITEMS]
        self.assertEqual(items[0]['cantidad'], 1234.5)

    def test_codigo_inexistente_avisa_y_no_agrega(self):
        self.elegir_cliente()
        respuesta = self.client.post(reverse('distribucion_movil_item_add'),
                                     {'codigo': '777777', 'cantidad': '1'})
        self.assertIn("No existe el artículo", respuesta.content.decode('utf-8'))
        self.assertEqual(self.client.session.get(carrito.CLAVE_ITEMS, []), [])

    def test_no_deja_cargar_sin_cliente(self):
        respuesta = self.client.post(reverse('distribucion_movil_item_add'),
                                     {'codigo': str(self.producto.id), 'cantidad': '1'})
        self.assertIn("Elegí primero el cliente", respuesta.content.decode('utf-8'))

    def test_cantidad_cero_o_negativa_se_rechaza(self):
        self.elegir_cliente()
        respuesta = self.client.post(reverse('distribucion_movil_item_add'),
                                     {'codigo': str(self.producto.id), 'cantidad': '0'})
        self.assertIn("mayor a cero", respuesta.content.decode('utf-8'))

    def test_quitar_item(self):
        self.elegir_cliente()
        self.client.post(reverse('distribucion_movil_item_add'),
                         {'codigo': str(self.producto.id), 'cantidad': '3'})
        self.client.post(reverse('distribucion_movil_item_remove', args=[0]))
        self.assertEqual(self.client.session[carrito.CLAVE_ITEMS], [])

    def test_descartar_vacia_el_pedido_completo(self):
        self.elegir_cliente()
        self.client.post(reverse('distribucion_movil_item_add'),
                         {'codigo': str(self.producto.id), 'cantidad': '3'})
        self.client.post(reverse('distribucion_movil_descartar'))
        self.assertEqual(self.client.session[carrito.CLAVE_ITEMS], [])
        self.assertIsNone(self.client.session.get(carrito.CLAVE_CLIENTE))

    def test_cambiar_de_cliente_con_pedido_en_curso_se_rechaza(self):
        """Cambiar de cliente vaciaría el carrito sin aviso: primero se cierra el pedido."""
        otro = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="Otro Cliente", tipo_entidad=1)
        CarteraVendedor.objects.create(
            empresa=self.empresa, vendedor=self.vendedor, cliente=otro)

        self.elegir_cliente()
        self.client.post(reverse('distribucion_movil_item_add'),
                         {'codigo': str(self.producto.id), 'cantidad': '3'})
        respuesta = self.elegir_cliente(otro)

        self.assertIn("pedido en curso", respuesta.content.decode('utf-8'))
        self.assertEqual(self.client.session[carrito.CLAVE_CLIENTE], self.cliente.codigo_id)


class ConfirmacionDelPedidoTestCase(BaseMovilTestCase):
    def _cargar(self, cantidad='10'):
        self.elegir_cliente()
        self.client.post(reverse('distribucion_movil_item_add'),
                         {'codigo': str(self.producto.id), 'cantidad': cantidad})

    def test_confirmar_crea_el_pedido_numerado(self):
        self._cargar()
        respuesta = self.client.post(reverse('distribucion_movil_confirmar'),
                                     {'condic_destino': '1'})

        pedido = ExtensionPedidoDistribucion.objects.get()
        self.assertEqual(pedido.numero, 1)
        self.assertEqual(pedido.punto, self.sucursal.id)
        self.assertEqual(pedido.origen, ExtensionPedidoDistribucion.ORIGEN_MOVIL)
        self.assertIn(pedido.numero_formateado, respuesta.content.decode('utf-8'))

    def test_el_pedido_queda_con_el_vendedor_de_la_cartera(self):
        self._cargar()
        self.client.post(reverse('distribucion_movil_confirmar'))
        self.assertEqual(ExtensionPedidoDistribucion.objects.get().vendedor, self.vendedor)

    def test_la_fecha_la_pone_el_sistema(self):
        """`Preventa.fecha` es `auto_now_add`: el vendedor no la elige ni la ve."""
        from django.utils import timezone
        self._cargar()
        self.client.post(reverse('distribucion_movil_confirmar'))
        self.assertEqual(Preventa.objects.get().fecha, timezone.localdate())

    def test_confirmar_limpia_el_carrito(self):
        self._cargar()
        self.client.post(reverse('distribucion_movil_confirmar'))
        self.assertEqual(self.client.session.get(carrito.CLAVE_ITEMS), [])
        self.assertIsNone(self.client.session.get(carrito.CLAVE_CLIENTE))

    def test_el_pedido_compromete_stock(self):
        self._cargar(cantidad='30')
        self.client.post(reverse('distribucion_movil_confirmar'))
        fila = StockSucursal.objects.get(producto=self.producto, sucursal=self.sucursal)
        self.assertEqual(fila.cantidad, Decimal('50.00'))       # el físico no cambió
        self.assertEqual(fila.comprometido, Decimal('30.00'))

    def test_condic_destino_pre_se_respeta(self):
        self._cargar()
        self.client.post(reverse('distribucion_movil_confirmar'), {'condic_destino': '2'})
        self.assertEqual(ExtensionPedidoDistribucion.objects.get().condic_destino, 2)

    def test_avisa_cuando_el_pedido_excede_el_stock(self):
        self._cargar(cantidad='80')   # hay 50
        respuesta = self.client.post(reverse('distribucion_movil_confirmar'))
        self.assertTrue(ExtensionPedidoDistribucion.objects.get().alerta_stock)
        self.assertIn("sujeto a disponibilidad", respuesta.content.decode('utf-8'))

    def test_confirmar_sin_items_no_crea_nada(self):
        self.elegir_cliente()
        respuesta = self.client.post(reverse('distribucion_movil_confirmar'))
        self.assertIn("Falta el cliente o los artículos", respuesta.content.decode('utf-8'))
        self.assertEqual(ExtensionPedidoDistribucion.objects.count(), 0)

    def test_dos_pedidos_seguidos_reciben_numeros_correlativos(self):
        for _ in range(2):
            self._cargar()
            self.client.post(reverse('distribucion_movil_confirmar'))
        numeros = list(ExtensionPedidoDistribucion.objects.order_by('numero')
                       .values_list('numero', flat=True))
        self.assertEqual(numeros, [1, 2])


class PantallaMovilTestCase(BaseMovilTestCase):
    def test_la_pantalla_responde(self):
        respuesta = self.client.get(reverse('distribucion_movil_pedido'))
        self.assertEqual(respuesta.status_code, 200)

    def test_retoma_un_pedido_a_medias(self):
        """Si el vendedor sale y vuelve, el pedido sigue donde estaba."""
        self.elegir_cliente()
        self.client.post(reverse('distribucion_movil_item_add'),
                         {'codigo': str(self.producto.id), 'cantidad': '7'})
        respuesta = self.client.get(reverse('distribucion_movil_pedido'))
        contenido = respuesta.content.decode('utf-8')
        self.assertIn("ALMACÉN DON JOSÉ", contenido.upper())
        self.assertIn("YOGUR X 900 VAINILLA", contenido.upper())

    def test_no_muestra_ningun_campo_de_fecha_del_comprobante(self):
        respuesta = self.client.get(reverse('distribucion_movil_pedido'))
        self.assertNotIn('name="fecha"', respuesta.content.decode('utf-8'))
