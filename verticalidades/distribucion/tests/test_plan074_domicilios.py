"""Tests de los domicilios de entrega (Plan 074).

Un cliente puede tener varios puntos de entrega porque tiene sucursales. La regla del
circuito es **1 domicilio → 1 pedido → 1 comprobante → 1 parada**: cada sucursal recibe,
controla y firma lo suyo.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from verticalidades.distribucion.models import (CarteraVendedor, DiaVisita, DomicilioEntrega,
                                 ExtensionPedidoDistribucion, Personal, ZonaReparto)
from verticalidades.distribucion.services.domicilios import (asegurar_domicilio_principal,
                                              sembrar_domicilios_faltantes)
from verticalidades.distribucion.services.pedidos import guardar_pedido
from empresas.models import Empresa, Sucursal
from facturacion.models import ClienteProveedor
from verticalidades.distribucion.models import ExtensionDistribuidora
from productos.models import Producto, StockSucursal
from usuarios.models import Perfil


class BaseDomicilioTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Distribuidora Prueba", cuit="30111111118",
            tipo_actividad="DISTRIBUIDORA")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, nombre="Depósito Central", punto=1)
        self.centro = ZonaReparto.objects.create(
            empresa=self.empresa, nombre="San Cayetano", orden=1)
        self.norte = ZonaReparto.objects.create(
            empresa=self.empresa, nombre="Villa Luján", orden=2)

        self.usuario = User.objects.create_user(username="operador", password="x")
        self.cliente = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="Supermercado Don José", tipo_entidad=1,
            domicilio="Belgrano 100", localidad="San Miguel de Tucumán",
            limite=Decimal('500000.00'))
        ExtensionDistribuidora.objects.create(
            cliente=self.cliente, coeficiente_mayorista=Decimal('0.9000'))

        self.producto = Producto.objects.create(
            empresa=self.empresa, detalle="Yogur x 900", precio_total=Decimal('1000.00'))
        StockSucursal.objects.create(
            producto=self.producto, sucursal=self.sucursal,
            stock_inicial=Decimal('500.00'), cantidad=Decimal('500.00'))

    def item(self, cantidad=5):
        return [{
            'producto_id': self.producto.id, 'cantidad': cantidad,
            'precio_unitario': 900.0, 'total': 900.0 * cantidad, 'descuento': 0,
        }]


class DomicilioPrincipalTestCase(BaseDomicilioTestCase):
    def test_se_genera_del_domicilio_fiscal_si_no_hay_ninguno(self):
        """El predeterminado es el fiscal: el circuito nunca se traba por este dato."""
        principal = asegurar_domicilio_principal(self.cliente, self.empresa.id)
        self.assertEqual(principal.domicilio, "BELGRANO 100")
        self.assertEqual(principal.localidad, "SAN MIGUEL DE TUCUMÁN")
        self.assertTrue(principal.es_principal)

    def test_es_idempotente(self):
        primero = asegurar_domicilio_principal(self.cliente, self.empresa.id)
        segundo = asegurar_domicilio_principal(self.cliente, self.empresa.id)
        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(DomicilioEntrega.objects.filter(cliente=self.cliente).count(), 1)

    def test_no_pisa_los_domicilios_ya_cargados(self):
        propio = DomicilioEntrega.objects.create(
            empresa=self.empresa, cliente=self.cliente, nombre="Sucursal Centro",
            domicilio="25 de Mayo 500", es_principal=True)
        self.assertEqual(asegurar_domicilio_principal(self.cliente, self.empresa.id), propio)
        self.assertEqual(DomicilioEntrega.objects.filter(cliente=self.cliente).count(), 1)

    def test_si_hay_domicilios_pero_ninguno_principal_promueve_el_primero(self):
        DomicilioEntrega.objects.create(
            empresa=self.empresa, cliente=self.cliente, nombre="Sucursal Centro",
            domicilio="25 de Mayo 500", es_principal=False)
        principal = asegurar_domicilio_principal(self.cliente, self.empresa.id)
        self.assertTrue(principal.es_principal)

    def test_cliente_sin_domicilio_fiscal_no_rompe(self):
        sin_domicilio = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="Sin Domicilio", tipo_entidad=1)
        principal = asegurar_domicilio_principal(sin_domicilio, self.empresa.id)
        self.assertEqual(principal.domicilio, "SIN DOMICILIO CARGADO")

    def test_marcar_principal_desmarca_al_anterior(self):
        primero = asegurar_domicilio_principal(self.cliente, self.empresa.id)
        segundo = DomicilioEntrega.objects.create(
            empresa=self.empresa, cliente=self.cliente, nombre="Sucursal Norte",
            domicilio="Av. Roca 2000", es_principal=True)
        primero.refresh_from_db()
        self.assertFalse(primero.es_principal)
        self.assertTrue(segundo.es_principal)

    def test_siembra_masiva_para_la_carga_inicial(self):
        otro = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="Otro Cliente", tipo_entidad=1,
            domicilio="Muñecas 300")
        creados = sembrar_domicilios_faltantes(self.empresa.id)
        self.assertEqual(creados, 2)
        self.assertTrue(DomicilioEntrega.objects.filter(cliente=otro).exists())
        # Idempotente: correrla de nuevo no duplica.
        self.assertEqual(sembrar_domicilios_faltantes(self.empresa.id), 0)


class VariasSucursalesTestCase(BaseDomicilioTestCase):
    def setUp(self):
        super().setUp()
        self.centro_dom = DomicilioEntrega.objects.create(
            empresa=self.empresa, cliente=self.cliente, nombre="Sucursal Centro",
            domicilio="25 de Mayo 500", zona=self.centro, es_principal=True)
        self.norte_dom = DomicilioEntrega.objects.create(
            empresa=self.empresa, cliente=self.cliente, nombre="Sucursal Norte",
            domicilio="Av. Roca 2000", zona=self.norte)

    def test_las_sucursales_pueden_estar_en_zonas_distintas(self):
        """Es la razón de fondo por la que la zona vive acá y no en el cliente."""
        self.assertNotEqual(self.centro_dom.zona, self.norte_dom.zona)

    def test_no_se_repite_el_nombre_en_el_mismo_cliente(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DomicilioEntrega.objects.create(
                    empresa=self.empresa, cliente=self.cliente,
                    nombre="SUCURSAL CENTRO", domicilio="Otra dirección")

    def test_dos_clientes_pueden_usar_el_mismo_nombre(self):
        otro = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="Otro", tipo_entidad=1)
        DomicilioEntrega.objects.create(
            empresa=self.empresa, cliente=otro, nombre="Sucursal Centro",
            domicilio="Otra calle 100")
        self.assertEqual(DomicilioEntrega.objects.filter(nombre="SUCURSAL CENTRO").count(), 2)

    def test_cada_punto_lleva_su_propia_agenda(self):
        DiaVisita.objects.create(empresa=self.empresa, domicilio=self.centro_dom, dia_semana=1)
        DiaVisita.objects.create(empresa=self.empresa, domicilio=self.centro_dom, dia_semana=4)
        DiaVisita.objects.create(empresa=self.empresa, domicilio=self.norte_dom, dia_semana=2)

        self.assertEqual(self.centro_dom.dias_visita.count(), 2)   # lunes y jueves
        self.assertEqual(self.norte_dom.dias_visita.count(), 1)

    def test_el_texto_completo_arma_la_direccion(self):
        self.centro_dom.localidad = "Yerba Buena"
        self.centro_dom.save()
        self.assertEqual(self.centro_dom.texto_completo, "25 DE MAYO 500 - YERBA BUENA")


class PedidoPorPuntoDeEntregaTestCase(BaseDomicilioTestCase):
    """La regla del circuito: 1 domicilio → 1 pedido → 1 comprobante → 1 parada."""

    def setUp(self):
        super().setUp()
        self.centro_dom = DomicilioEntrega.objects.create(
            empresa=self.empresa, cliente=self.cliente, nombre="Sucursal Centro",
            domicilio="25 de Mayo 500", zona=self.centro, es_principal=True)
        self.norte_dom = DomicilioEntrega.objects.create(
            empresa=self.empresa, cliente=self.cliente, nombre="Sucursal Norte",
            domicilio="Av. Roca 2000", zona=self.norte)

    def _pedido(self, domicilio=None):
        return guardar_pedido(
            empresa_id=self.empresa.id, sucursal_id=self.sucursal.id,
            cliente=self.cliente, usuario=self.usuario, items=self.item(),
            domicilio_entrega=domicilio)

    def test_el_pedido_guarda_su_punto_de_entrega(self):
        pedido = self._pedido(self.norte_dom)
        self.assertEqual(pedido.domicilio_entrega, self.norte_dom)

    def test_la_zona_del_pedido_sale_del_domicilio_y_no_del_cliente(self):
        pedido = self._pedido(self.norte_dom)
        self.assertEqual(pedido.zona, self.norte)

    def test_sin_domicilio_indicado_se_usa_el_principal(self):
        pedido = self._pedido()
        self.assertEqual(pedido.domicilio_entrega, self.centro_dom)

    def test_guarda_el_texto_del_domicilio_como_snapshot(self):
        """Si mañana se corrige la dirección, el comprobante ya emitido no cambia."""
        pedido = self._pedido(self.norte_dom)
        texto_original = pedido.domicilio_entrega_texto

        self.norte_dom.domicilio = "Av. Roca 3000"
        self.norte_dom.save()
        pedido.refresh_from_db()

        self.assertEqual(pedido.domicilio_entrega_texto, texto_original)
        self.assertNotEqual(pedido.domicilio_entrega.texto_completo, texto_original)

    def test_tres_sucursales_generan_tres_pedidos_independientes(self):
        p1 = self._pedido(self.centro_dom)
        p2 = self._pedido(self.norte_dom)
        self.assertNotEqual(p1.pk, p2.pk)
        self.assertEqual([p1.numero, p2.numero], [1, 2])
        self.assertNotEqual(p1.zona, p2.zona)

    def test_el_credito_es_del_cliente_y_no_del_punto(self):
        """Las entregas se reparten; la deuda no."""
        self._pedido(self.centro_dom)
        self._pedido(self.norte_dom)
        from verticalidades.distribucion.services.credito import situacion_crediticia
        situacion = situacion_crediticia(self.cliente)
        # Los dos pedidos descuentan del MISMO límite del cliente.
        self.assertEqual(situacion['pedidos_pendientes'], Decimal('9000.00'))

    def test_no_se_puede_borrar_un_domicilio_con_pedidos(self):
        self._pedido(self.norte_dom)
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.norte_dom.delete()


class MovilConVariasSucursalesTestCase(BaseDomicilioTestCase):
    def setUp(self):
        super().setUp()
        Perfil.objects.create(usuario=self.usuario).empresas.add(self.empresa)
        vendedor = Personal.objects.create(
            empresa=self.empresa, nombre="Juan", es_vendedor=True, usuario=self.usuario)
        CarteraVendedor.objects.create(
            empresa=self.empresa, vendedor=vendedor, cliente=self.cliente)

        self.centro_dom = DomicilioEntrega.objects.create(
            empresa=self.empresa, cliente=self.cliente, nombre="Sucursal Centro",
            domicilio="25 de Mayo 500", zona=self.centro, es_principal=True)
        self.norte_dom = DomicilioEntrega.objects.create(
            empresa=self.empresa, cliente=self.cliente, nombre="Sucursal Norte",
            domicilio="Av. Roca 2000", zona=self.norte)

        self.client = Client()
        self.client.force_login(self.usuario)
        sesion = self.client.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion.save()

    def test_al_elegir_el_cliente_se_propone_el_principal(self):
        respuesta = self.client.post(
            reverse('distribucion_movil_elegir_cliente', args=[self.cliente.codigo_id]))
        contenido = respuesta.content.decode('utf-8')
        self.assertIn("SUCURSAL CENTRO", contenido.upper())
        self.assertIn("SUCURSAL NORTE", contenido.upper())   # se ofrecen las dos

    def test_el_vendedor_puede_cambiar_el_punto_de_entrega(self):
        self.client.post(reverse('distribucion_movil_elegir_cliente',
                                 args=[self.cliente.codigo_id]))
        self.client.post(reverse('distribucion_movil_item_add'),
                         {'codigo': str(self.producto.id), 'cantidad': '5'})
        self.client.post(reverse('distribucion_movil_elegir_domicilio',
                                 args=[self.norte_dom.id]))
        self.client.post(reverse('distribucion_movil_confirmar'))

        pedido = ExtensionPedidoDistribucion.objects.get()
        self.assertEqual(pedido.domicilio_entrega, self.norte_dom)
        self.assertEqual(pedido.zona, self.norte)

    def test_cambiar_de_punto_no_borra_lo_cargado(self):
        self.client.post(reverse('distribucion_movil_elegir_cliente',
                                 args=[self.cliente.codigo_id]))
        self.client.post(reverse('distribucion_movil_item_add'),
                         {'codigo': str(self.producto.id), 'cantidad': '5'})
        self.client.post(reverse('distribucion_movil_elegir_domicilio',
                                 args=[self.norte_dom.id]))
        from verticalidades.distribucion.services import carrito
        self.assertEqual(len(self.client.session[carrito.CLAVE_ITEMS]), 1)

    def test_no_se_puede_elegir_el_punto_de_otro_cliente(self):
        ajeno_cliente = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="Ajeno", tipo_entidad=1)
        ajeno = DomicilioEntrega.objects.create(
            empresa=self.empresa, cliente=ajeno_cliente, nombre="Depósito",
            domicilio="Otra calle")
        self.client.post(reverse('distribucion_movil_elegir_cliente',
                                 args=[self.cliente.codigo_id]))
        respuesta = self.client.post(
            reverse('distribucion_movil_elegir_domicilio', args=[ajeno.id]))
        self.assertEqual(respuesta.status_code, 404)
