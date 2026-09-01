"""Facturación masiva de pedidos de distribución (Plan 074, fase 4).

El corazón del módulo: la regla del saldo disponible negativo decide, con un solo
cálculo, el cobro mínimo que el repartidor tiene que traer y la condición de venta que se
imprime en el comprobante.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from contable.models import Asiento, Cuenta, Ejercicio, LibroIvaVentas, ParametrosContables
from verticalidades.distribucion.models import DomicilioEntrega, ExtensionPedidoDistribucion
from verticalidades.distribucion.services.facturacion import (CONTADO, CTA_CTE, evaluar_credito,
                                               facturar_lote, facturar_pedido,
                                               pedidos_pendientes, previsualizar)
from verticalidades.distribucion.services.pedidos import guardar_pedido
from empresas.models import Empresa, PuntoVenta, Sucursal
from facturacion.models import (ClienteProveedor,  TipoComprobante
from verticalidades.distribucion.models import ExtensionDistribuidora
                                Venta)
from productos.models import Producto, Rubro, StockSucursal
from usuarios.models import Perfil


class BaseFacturacionTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Distribuidora Prueba", cuit="30111111118",
            tipo_actividad="DISTRIBUIDORA")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, nombre="Depósito Central", punto=1)
        self.punto_venta = PuntoVenta.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, numero=4)
        Ejercicio.objects.create(
            empresa=self.empresa, inicio="2026-01-01", cierre="2026-12-31")

        self.usuario = User.objects.create_user(username="admin1", password="x", is_staff=True)

        TipoComprobante.objects.create(codigo='006', detalle="Factura B", signo=1)
        TipoComprobante.objects.create(codigo='PRE', detalle="Comprobante Interno", signo=1)

        self.cta_clientes = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.3", cuenta="DEUDORES", imputable=1)
        self.cta_ventas = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="4.1.1", cuenta="VENTAS", imputable=1)
        self.cta_iva = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="2.1.4", cuenta="IVA DEBITO", imputable=1)
        ParametrosContables.objects.create(
            empresa=self.empresa, cta_clientes_default=self.cta_clientes,
            cta_ventas=self.cta_ventas, cta_iva_debito=self.cta_iva,
            metodo_contabilizacion_ventas=1)

        self.rubro = Rubro.objects.create(
            empresa=self.empresa, detalle="LACTEOS", cta_ventas=self.cta_ventas)
        self.producto = Producto.objects.create(
            empresa=self.empresa, detalle="Yogur x 900", precio_total=Decimal('1000.00'),
            alic_iva=Decimal('21.00'), rubro=self.rubro)
        StockSucursal.objects.create(
            producto=self.producto, sucursal=self.sucursal,
            stock_inicial=Decimal('1000.00'), cantidad=Decimal('1000.00'))

    def crear_cliente(self, nombre, limite='100000.00', saldo='0.00', bloqueado=False):
        cliente = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social=nombre, tipo_entidad=1,
            domicilio="Belgrano 100", condicion_iva="CONSUMIDOR FINAL",
            cuit="20123456783", tipo_documento="96",
            limite=Decimal(limite), saldo=Decimal(saldo))
        ExtensionDistribuidora.objects.create(
            cliente=cliente, coeficiente_mayorista=Decimal('1.0000'),
            bloqueado_credito=bloqueado)
        DomicilioEntrega.objects.create(
            empresa=self.empresa, cliente=cliente, nombre="Casa Central",
            domicilio="Belgrano 100", es_principal=True)
        return cliente

    def crear_pedido(self, cliente, cantidad=10, condic_destino=2):
        return guardar_pedido(
            empresa_id=self.empresa.id, sucursal_id=self.sucursal.id,
            cliente=cliente, usuario=self.usuario, condic_destino=condic_destino,
            items=[{'producto_id': self.producto.id, 'cantidad': cantidad,
                    'precio_unitario': 1000.0, 'total': 1000.0 * cantidad,
                    'descuento': 0}])


class ReglaDelSaldoDisponibleTestCase(BaseFacturacionTestCase):
    """Los cuatro casos de la tabla, resueltos por una sola fórmula."""

    def test_entra_holgado_en_el_limite(self):
        cliente = self.crear_cliente("Holgado", limite='100000', saldo='0')
        credito = evaluar_credito(cliente, Decimal('10000'))
        self.assertEqual(credito['saldo_disponible'], Decimal('90000'))
        self.assertEqual(credito['cobro_minimo'], Decimal('0.00'))
        self.assertEqual(credito['condicion_venta'], CTA_CTE)

    def test_se_pasa_parcialmente(self):
        """Límite 100.000, saldo 60.000, carga 50.000 → disponible −10.000."""
        cliente = self.crear_cliente("Ajustado", limite='100000', saldo='60000')
        credito = evaluar_credito(cliente, Decimal('50000'))
        self.assertEqual(credito['saldo_disponible'], Decimal('-10000'))
        self.assertEqual(credito['cobro_minimo'], Decimal('10000'))
        # Sigue siendo cuenta corriente: sólo hay que cobrar el excedente.
        self.assertEqual(credito['condicion_venta'], CTA_CTE)

    def test_limite_cero_es_solo_contado(self):
        cliente = self.crear_cliente("Sin Crédito", limite='0', saldo='0')
        credito = evaluar_credito(cliente, Decimal('50000'))
        self.assertEqual(credito['cobro_minimo'], Decimal('50000'))
        self.assertEqual(credito['condicion_venta'], CONTADO)

    def test_cliente_bloqueado_es_contado_aunque_tenga_limite(self):
        cliente = self.crear_cliente("Bloqueado", limite='500000', saldo='0', bloqueado=True)
        credito = evaluar_credito(cliente, Decimal('50000'))
        self.assertTrue(credito['bloqueado'])
        self.assertEqual(credito['cobro_minimo'], Decimal('50000'))
        self.assertEqual(credito['condicion_venta'], CONTADO)

    def test_el_disponible_mira_la_foto_POSTERIOR_a_facturar(self):
        """Es lo que hace útil el número: dice cómo queda el cliente con esta carga."""
        cliente = self.crear_cliente("Justo", limite='100000', saldo='0')
        self.assertEqual(evaluar_credito(cliente, Decimal('100000'))['saldo_disponible'],
                         Decimal('0.00'))
        self.assertEqual(evaluar_credito(cliente, Decimal('100001'))['cobro_minimo'],
                         Decimal('1.00'))


class EmisionDelComprobanteTestCase(BaseFacturacionTestCase):
    def test_el_pre_se_numera_por_sucursal_y_no_es_fiscal(self):
        pedido = self.crear_pedido(self.crear_cliente("Cliente PRE"), condic_destino=2)
        venta = facturar_pedido(pedido, self.usuario)

        self.assertEqual(venta.condic, 2)
        self.assertEqual(venta.punto, self.sucursal.id)
        self.assertEqual(venta.numero, 1)
        self.assertEqual(venta.tipo.codigo, 'PRE')
        self.assertFalse(venta.cae)

    def test_el_pre_no_entra_al_libro_iva(self):
        pedido = self.crear_pedido(self.crear_cliente("Cliente PRE"), condic_destino=2)
        venta = facturar_pedido(pedido, self.usuario)
        self.assertFalse(LibroIvaVentas.objects.filter(asiento_id=venta.asiento_id).exists())

    def test_la_factura_usa_el_punto_de_venta_de_arca(self):
        pedido = self.crear_pedido(self.crear_cliente("Cliente Fiscal"), condic_destino=1)
        venta = facturar_pedido(pedido, self.usuario, modo_prueba=True)

        self.assertEqual(venta.condic, 1)
        self.assertEqual(venta.punto, self.punto_venta.numero)
        self.assertEqual(venta.tipo.codigo, '006')   # Consumidor Final → Factura B

    def test_la_factura_si_entra_al_libro_iva(self):
        pedido = self.crear_pedido(self.crear_cliente("Cliente Fiscal"), condic_destino=1)
        venta = facturar_pedido(pedido, self.usuario, modo_prueba=True)
        self.assertTrue(LibroIvaVentas.objects.filter(asiento_id=venta.asiento_id).exists())

    def test_el_comprobante_genera_asiento_con_el_condic_correcto(self):
        """Regla inflexible: el asiento hereda el `condic` del comprobante."""
        pedido = self.crear_pedido(self.crear_cliente("Cliente PRE"), condic_destino=2)
        venta = facturar_pedido(pedido, self.usuario)

        self.assertIsNotNone(venta.asiento_id)
        asiento = Asiento.objects.get(asiento_id=venta.asiento_id)
        self.assertEqual(asiento.condic, 2)

    def test_la_fecha_la_pone_el_sistema(self):
        pedido = self.crear_pedido(self.crear_cliente("Cliente"), condic_destino=2)
        venta = facturar_pedido(pedido, self.usuario)
        self.assertEqual(venta.fecha, timezone.localdate())

    def test_la_condicion_de_venta_queda_congelada_en_el_comprobante(self):
        cliente = self.crear_cliente("Sin Crédito", limite='0')
        venta = facturar_pedido(self.crear_pedido(cliente), self.usuario)
        self.assertEqual(venta.condicion_venta, CONTADO)

    def test_el_pedido_queda_vinculado_y_facturado(self):
        pedido = self.crear_pedido(self.crear_cliente("Cliente"))
        venta = facturar_pedido(pedido, self.usuario)

        pedido.refresh_from_db()
        self.assertEqual(pedido.venta, venta)
        self.assertEqual(pedido.preventa.estado, 3)   # Facturada

    def test_facturar_libera_el_stock_comprometido_y_descuenta_el_real(self):
        pedido = self.crear_pedido(self.crear_cliente("Cliente"), cantidad=30)
        fila = StockSucursal.objects.get(producto=self.producto, sucursal=self.sucursal)
        self.assertEqual(fila.comprometido, Decimal('30.00'))

        facturar_pedido(pedido, self.usuario)

        fila.refresh_from_db()
        self.assertEqual(fila.comprometido, Decimal('0.00'))   # ya no es una promesa
        self.assertEqual(fila.cantidad, Decimal('970.00'))     # salió del depósito

    def test_facturar_dos_veces_el_mismo_pedido_no_duplica(self):
        pedido = self.crear_pedido(self.crear_cliente("Cliente"))
        primera = facturar_pedido(pedido, self.usuario)
        segunda = facturar_pedido(pedido, self.usuario)
        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(Venta.objects.count(), 1)

    def test_los_pre_avanzan_correlativos(self):
        for nombre in ("Uno", "Dos", "Tres"):
            facturar_pedido(self.crear_pedido(self.crear_cliente(nombre)), self.usuario)
        numeros = sorted(Venta.objects.values_list('numero', flat=True))
        self.assertEqual(numeros, [1, 2, 3])

    def test_pedido_sin_articulos_falla_explicito(self):
        cliente = self.crear_cliente("Vacío")
        pedido = self.crear_pedido(cliente)
        pedido.preventa.items.all().delete()
        with self.assertRaises(ValueError):
            facturar_pedido(pedido, self.usuario)


class LoteTestCase(BaseFacturacionTestCase):
    def test_un_error_no_frena_a_los_demas(self):
        """Diferencia con el lote de ESTUDIO: cada pedido va en su propia transacción."""
        bueno = self.crear_pedido(self.crear_cliente("Bueno"))
        malo = self.crear_pedido(self.crear_cliente("Malo"))
        malo.preventa.items.all().delete()
        otro = self.crear_pedido(self.crear_cliente("Otro"))

        resultados = facturar_lote([bueno, malo, otro], self.usuario)

        self.assertEqual([r['ok'] for r in resultados], [True, False, True])
        self.assertEqual(Venta.objects.count(), 2)

    def test_sin_tipo_pre_configurado_el_error_es_explicito(self):
        TipoComprobante.objects.filter(codigo='PRE').delete()
        pedido = self.crear_pedido(self.crear_cliente("Cliente"))
        resultados = facturar_lote([pedido], self.usuario)
        self.assertFalse(resultados[0]['ok'])
        self.assertIn("PRE", resultados[0]['mensaje'])

    def test_los_pedidos_pendientes_excluyen_los_ya_facturados(self):
        pedido = self.crear_pedido(self.crear_cliente("Cliente"))
        self.assertEqual(pedidos_pendientes(self.empresa.id, self.sucursal.id).count(), 1)
        facturar_pedido(pedido, self.usuario)
        self.assertEqual(pedidos_pendientes(self.empresa.id, self.sucursal.id).count(), 0)

    def test_la_previsualizacion_trae_el_credito_de_cada_pedido(self):
        self.crear_pedido(self.crear_cliente("Sin Crédito", limite='0'))
        filas = previsualizar(self.empresa.id, self.sucursal.id)
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]['credito']['condicion_venta'], CONTADO)


class PantallaFacturacionTestCase(BaseFacturacionTestCase):
    def setUp(self):
        super().setUp()
        self.pedido = self.crear_pedido(self.crear_cliente("Cliente Uno"))
        self.client = Client()
        self.client.force_login(self.usuario)
        sesion = self.client.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion.save()

    def test_la_pantalla_responde_con_la_previsualizacion(self):
        respuesta = self.client.get(reverse('distribucion_facturacion'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("CLIENTE UNO", respuesta.content.decode('utf-8').upper())

    def test_emitir_desde_la_pantalla(self):
        respuesta = self.client.post(reverse('distribucion_facturacion'),
                                     {'pedidos': [str(self.pedido.id)]})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Venta.objects.count(), 1)

    def test_sin_seleccionar_nada_avisa(self):
        respuesta = self.client.post(reverse('distribucion_facturacion'), {})
        self.assertIn("No seleccionaste", respuesta.content.decode('utf-8'))
        self.assertEqual(Venta.objects.count(), 0)

    def test_sin_permiso_no_se_puede_emitir(self):
        raso = User.objects.create_user(username="raso", password="x")
        Perfil.objects.create(usuario=raso).empresas.add(self.empresa)
        cliente = Client()
        cliente.force_login(raso)
        sesion = cliente.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion.save()

        respuesta = cliente.post(reverse('distribucion_facturacion'),
                                 {'pedidos': [str(self.pedido.id)]})
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(Venta.objects.count(), 0)
