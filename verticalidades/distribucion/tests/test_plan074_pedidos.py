"""Tests del pedido de distribución: numeración, precio, crédito y stock comprometido.

Plan 074, fase 1.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from core.models import ContadorDocumento
from core.services.numeracion import auditar_correlativos
from verticalidades.distribucion.models import (CarteraVendedor, DomicilioEntrega,
                                 ExtensionPedidoDistribucion, Personal, ZonaReparto)
from verticalidades.distribucion.services import credito, precios
from verticalidades.distribucion.services.pedidos import (clientes_de_la_cartera, registrar_pedido,
                                           vendedor_de)
from empresas.models import Empresa, Sucursal
from facturacion.models import (ClienteProveedor,  Preventa
from verticalidades.distribucion.models import ExtensionDistribuidora
                                PreventaItem)
from productos.models import Producto, StockSucursal
from productos.services.stock_service import disponible_real, recalcular_comprometido
from usuarios.models import Perfil


class BasePedidoTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Distribuidora Prueba", cuit="30111111118",
            tipo_actividad="DISTRIBUIDORA")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, nombre="Depósito Central", punto=1)
        self.otra_sucursal = Sucursal.objects.create(
            empresa=self.empresa, nombre="Sucursal Norte", punto=2)
        self.usuario = User.objects.create_user(username="operador", password="x")
        self.zona = ZonaReparto.objects.create(
            empresa=self.empresa, nombre="San Cayetano", orden=1)

        self.cliente = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="Almacén Don José", tipo_entidad=1,
            limite=Decimal('100000.00'))
        self.extension = ExtensionDistribuidora.objects.create(
            cliente=self.cliente, coeficiente_mayorista=Decimal('0.9000'))
        # La zona vive en el DOMICILIO DE ENTREGA, no en el cliente: una sucursal en
        # San Cayetano y otra en Villa Luján entran en repartos distintos.
        self.domicilio = DomicilioEntrega.objects.create(
            empresa=self.empresa, cliente=self.cliente, nombre="Casa Central",
            domicilio="Belgrano 100", zona=self.zona, es_principal=True)

        self.producto = Producto.objects.create(
            empresa=self.empresa, detalle="Yogur x 900 vainilla",
            precio_total=Decimal('1690.00'), cto_rep=Decimal('900.00'))
        StockSucursal.objects.create(
            producto=self.producto, sucursal=self.sucursal,
            stock_inicial=Decimal('100.00'), cantidad=Decimal('100.00'))

    def crear_pedido(self, cantidad=10, cliente=None, sucursal=None, estado=2):
        preventa = Preventa.objects.create(
            cliente=cliente or self.cliente, vendedor=self.usuario,
            empresa=self.empresa, sucursal=sucursal or self.sucursal, estado=estado)
        PreventaItem.objects.create(
            preventa=preventa, producto=self.producto, cantidad=Decimal(str(cantidad)),
            precio_unitario=Decimal('1521.00'))
        preventa.recalcular_totales()
        return preventa


class PrecioPorCoeficienteTestCase(BasePedidoTestCase):
    def test_precio_es_precio_total_por_coeficiente(self):
        """La base es el precio de lista CON IVA; `cto_rep` no interviene."""
        self.assertEqual(precios.precio_para(self.producto, self.cliente),
                         Decimal('1521.00'))

    def test_cliente_sin_extension_paga_precio_de_lista(self):
        otro = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="Sin Extensión", tipo_entidad=1)
        self.assertEqual(precios.precio_para(self.producto, otro), Decimal('1690.00'))

    def test_coeficiente_cero_no_se_toma_como_gratis(self):
        """Un coeficiente sin cargar cae al neutro, no deja el producto en $0."""
        self.extension.coeficiente_mayorista = Decimal('0')
        self.extension.save()
        self.assertEqual(precios.precio_para(self.producto, self.cliente),
                         Decimal('1690.00'))

    def test_precio_se_redondea_a_dos_decimales(self):
        self.extension.coeficiente_mayorista = Decimal('0.8333')
        self.extension.save()
        # 1690 * 0.8333 = 1408,277 -> 1408,28
        self.assertEqual(precios.precio_para(self.producto, self.cliente),
                         Decimal('1408.28'))


class CreditoTestCase(BasePedidoTestCase):
    def test_disponible_es_limite_menos_saldo(self):
        self.cliente.saldo = Decimal('60000.00')
        self.cliente.save()
        situacion = credito.situacion_crediticia(self.cliente)
        self.assertEqual(situacion['disponible'], Decimal('40000.00'))
        self.assertEqual(situacion['cobro_minimo'], Decimal('0.00'))
        self.assertFalse(situacion['excedido'])

    def test_disponible_negativo_define_el_cobro_minimo(self):
        """Límite 100.000, saldo 110.000 -> disponible −10.000, cobro mínimo 10.000."""
        self.cliente.saldo = Decimal('110000.00')
        self.cliente.save()
        situacion = credito.situacion_crediticia(self.cliente)
        self.assertEqual(situacion['disponible'], Decimal('-10000.00'))
        self.assertEqual(situacion['cobro_minimo'], Decimal('10000.00'))
        self.assertTrue(situacion['excedido'])

    def test_limite_cero_es_solo_contado(self):
        self.cliente.limite = Decimal('0')
        self.cliente.save()
        situacion = credito.situacion_crediticia(self.cliente)
        self.assertTrue(situacion['solo_contado'])
        self.assertEqual(situacion['disponible'], Decimal('0.00'))

    def test_cliente_bloqueado_no_tiene_credito_aunque_tenga_limite(self):
        self.extension.bloqueado_credito = True
        self.extension.save()
        self.cliente.refresh_from_db()
        situacion = credito.situacion_crediticia(self.cliente)
        self.assertTrue(situacion['bloqueado'])
        self.assertTrue(situacion['solo_contado'])
        self.assertLessEqual(situacion['disponible'], Decimal('0'))

    def test_pedidos_sin_facturar_descuentan_del_disponible(self):
        """Sin este término, tres pedidos del mismo día pasan todos el control."""
        antes = credito.disponible_al_tomar(self.cliente)
        self.crear_pedido(cantidad=10)   # 10 * 1521 = 15.210
        despues = credito.disponible_al_tomar(self.cliente)
        self.assertEqual(antes - despues, Decimal('15210.00'))

    def test_pedido_facturado_deja_de_descontar(self):
        preventa = self.crear_pedido(cantidad=10)
        con_pedido = credito.disponible_al_tomar(self.cliente)
        preventa.estado = 3   # Facturada
        preventa.save()
        self.assertGreater(credito.disponible_al_tomar(self.cliente), con_pedido)


class StockComprometidoTestCase(BasePedidoTestCase):
    def test_pedido_compromete_stock_sin_moverlo(self):
        """El pedido no toca el stock físico: promete, no despacha."""
        self.crear_pedido(cantidad=30)
        fila = StockSucursal.objects.get(producto=self.producto, sucursal=self.sucursal)
        self.assertEqual(fila.cantidad, Decimal('100.00'))       # el físico no cambió
        self.assertEqual(fila.comprometido, Decimal('30.00'))
        self.assertEqual(fila.disponible, Decimal('70.00'))

    def test_disponible_real_descuenta_lo_comprometido(self):
        self.crear_pedido(cantidad=30)
        self.assertEqual(disponible_real(self.producto.id, self.sucursal.id),
                         Decimal('70.00'))

    def test_facturar_libera_el_comprometido(self):
        preventa = self.crear_pedido(cantidad=30)
        preventa.estado = 3   # Facturada
        preventa.save()
        fila = StockSucursal.objects.get(producto=self.producto, sucursal=self.sucursal)
        self.assertEqual(fila.comprometido, Decimal('0.00'))

    def test_anular_libera_el_comprometido(self):
        preventa = self.crear_pedido(cantidad=30)
        preventa.estado = 4   # Anulada
        preventa.save()
        fila = StockSucursal.objects.get(producto=self.producto, sucursal=self.sucursal)
        self.assertEqual(fila.comprometido, Decimal('0.00'))

    def test_borrar_el_item_libera_el_comprometido(self):
        preventa = self.crear_pedido(cantidad=30)
        preventa.items.all().delete()
        fila = StockSucursal.objects.get(producto=self.producto, sucursal=self.sucursal)
        self.assertEqual(fila.comprometido, Decimal('0.00'))

    def test_dos_pedidos_acumulan_el_comprometido(self):
        """Es el caso que motiva el campo: dos vendedores, el mismo stock."""
        self.crear_pedido(cantidad=30)
        self.crear_pedido(cantidad=50)
        self.assertEqual(disponible_real(self.producto.id, self.sucursal.id),
                         Decimal('20.00'))

    def test_el_comprometido_es_por_sucursal(self):
        self.crear_pedido(cantidad=30, sucursal=self.otra_sucursal)
        fila = StockSucursal.objects.get(producto=self.producto, sucursal=self.sucursal)
        self.assertEqual(fila.comprometido, Decimal('0.00'))

    def test_recalculo_es_idempotente_y_autorreparable(self):
        self.crear_pedido(cantidad=30)
        fila = StockSucursal.objects.get(producto=self.producto, sucursal=self.sucursal)
        fila.comprometido = Decimal('999.00')      # se ensucia a propósito
        fila.save(update_fields=['comprometido'])

        recalcular_comprometido(self.producto.id, self.sucursal.id)
        fila.refresh_from_db()
        self.assertEqual(fila.comprometido, Decimal('30.00'))


class NumeracionPedidoTestCase(BasePedidoTestCase):
    def test_el_pedido_recibe_numero_correlativo(self):
        p1 = registrar_pedido(self.crear_pedido())
        p2 = registrar_pedido(self.crear_pedido())
        self.assertEqual(p1.numero, 1)
        self.assertEqual(p2.numero, 2)

    def test_el_punto_es_la_sucursal_emisora(self):
        pedido = registrar_pedido(self.crear_pedido())
        self.assertEqual(pedido.punto, self.sucursal.id)

    def test_cada_sucursal_lleva_su_propia_serie(self):
        p1 = registrar_pedido(self.crear_pedido(sucursal=self.sucursal))
        p2 = registrar_pedido(self.crear_pedido(sucursal=self.otra_sucursal))
        self.assertEqual(p1.numero, 1)
        self.assertEqual(p2.numero, 1)
        self.assertNotEqual(p1.punto, p2.punto)

    def test_registrar_dos_veces_no_renumera(self):
        """Un pedido que se edita conserva su número, como cualquier documento emitido."""
        preventa = self.crear_pedido()
        primero = registrar_pedido(preventa)
        segundo = registrar_pedido(preventa)
        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(primero.numero, segundo.numero)

    def test_la_base_rechaza_un_numero_duplicado(self):
        """Segunda barrera: aunque falle el contador, la base no acepta el duplicado."""
        registrar_pedido(self.crear_pedido())
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ExtensionPedidoDistribucion.objects.create(
                    preventa=self.crear_pedido(), punto=self.sucursal.id, numero=1)

    def test_la_auditoria_de_correlativos_cubre_el_pedido(self):
        for _ in range(3):
            registrar_pedido(self.crear_pedido())

        filas = [f for f in auditar_correlativos(self.empresa.id)
                 if f['tipo'] == ContadorDocumento.PEDIDO]
        self.assertEqual(len(filas), 1)
        self.assertTrue(filas[0]['ok'])
        self.assertEqual(filas[0]['maximo'], 3)
        self.assertEqual(filas[0]['faltantes'], [])
        self.assertEqual(filas[0]['duplicados'], [])

    def test_la_auditoria_detecta_un_hueco_en_la_serie(self):
        registrar_pedido(self.crear_pedido())
        ExtensionPedidoDistribucion.objects.create(
            preventa=self.crear_pedido(), punto=self.sucursal.id, numero=3)

        filas = [f for f in auditar_correlativos(self.empresa.id)
                 if f['tipo'] == ContadorDocumento.PEDIDO]
        self.assertFalse(filas[0]['ok'])
        self.assertEqual(filas[0]['faltantes'], [2])


class RegistroDelPedidoTestCase(BasePedidoTestCase):
    def test_toma_el_vendedor_de_la_cartera(self):
        vendedor = Personal.objects.create(
            empresa=self.empresa, nombre="Juan", es_vendedor=True)
        CarteraVendedor.objects.create(
            empresa=self.empresa, vendedor=vendedor, cliente=self.cliente)

        pedido = registrar_pedido(self.crear_pedido())
        self.assertEqual(pedido.vendedor, vendedor)

    def test_hereda_la_zona_del_domicilio_de_entrega(self):
        pedido = registrar_pedido(self.crear_pedido())
        self.assertEqual(pedido.domicilio_entrega, self.domicilio)
        self.assertEqual(pedido.zona, self.zona)

    def test_marca_alerta_de_credito_cuando_el_pedido_excede_el_limite(self):
        self.cliente.limite = Decimal('1000.00')
        self.cliente.save()
        pedido = registrar_pedido(self.crear_pedido(cantidad=10))   # 15.210
        self.assertTrue(pedido.alerta_credito)

    def test_no_marca_alerta_de_credito_cuando_entra_holgado(self):
        pedido = registrar_pedido(self.crear_pedido(cantidad=1))
        self.assertFalse(pedido.alerta_credito)

    def test_marca_alerta_de_stock_cuando_no_alcanza(self):
        pedido = registrar_pedido(self.crear_pedido(cantidad=150))  # hay 100
        self.assertTrue(pedido.alerta_stock)

    def test_no_marca_alerta_de_stock_cuando_alcanza_justo(self):
        pedido = registrar_pedido(self.crear_pedido(cantidad=100))
        self.assertFalse(pedido.alerta_stock)

    def test_condic_destino_distingue_factura_de_pre(self):
        pedido = registrar_pedido(self.crear_pedido(), condic_destino=2)
        self.assertEqual(pedido.condic_destino, 2)


class CarteraDelVendedorTestCase(BasePedidoTestCase):
    def setUp(self):
        super().setUp()
        self.usuario_vendedor = User.objects.create_user(username="juanv", password="x")
        Perfil.objects.create(usuario=self.usuario_vendedor).empresas.add(self.empresa)
        self.vendedor = Personal.objects.create(
            empresa=self.empresa, nombre="Juan", es_vendedor=True,
            usuario=self.usuario_vendedor)
        self.otro_cliente = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="Kiosco La Esquina", tipo_entidad=1)

    def test_el_vendedor_solo_ve_su_cartera(self):
        CarteraVendedor.objects.create(
            empresa=self.empresa, vendedor=self.vendedor, cliente=self.cliente)
        cartera = clientes_de_la_cartera(self.usuario_vendedor, self.empresa.id)
        self.assertEqual(cartera, {self.cliente.codigo_id})
        self.assertNotIn(self.otro_cliente.codigo_id, cartera)

    def test_un_administrativo_sin_personal_ve_todos_los_clientes(self):
        """Es quien toma los pedidos telefónicos de cualquier cliente."""
        self.assertIsNone(clientes_de_la_cartera(self.usuario, self.empresa.id))

    def test_vendedor_de_devuelve_none_si_el_cliente_no_esta_asignado(self):
        self.assertIsNone(vendedor_de(self.otro_cliente, self.empresa.id))
