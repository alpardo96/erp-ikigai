"""Cobranza y rendición del VENDEDOR, fuera de todo reparto (Plan 076 §C).

Definición del usuario: *"En cuanto a los vendedores, rendirán a esta caja intermedia pero
en su condición de vendedores por los fondos que traen, no como reparto."* Y el motivo por
el que existe: *"Seguramente el pago final lo terminará haciendo el vendedor que le hará la
'guardia' cuando el cliente esté esquivando el pago."*

PARA PODER RENDIR HAY QUE HABER RETENIDO: lo que el vendedor cobra cae en una sesión
recaudadora abierta a su nombre, y esa sesión se cierra recién cuando rinde.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse

from contable.models import Cuenta, Ejercicio, ParametrosContables
from verticalidades.distribucion.models import (CobranzaDistribucion, DomicilioEntrega, Personal,
                                 RendicionReparto, ZonaReparto)
from verticalidades.distribucion.services.caja_reparto import (recibir, rendiciones_por_recibir,
                                                rendir_vendedor, resumen_vendedor,
                                                sesion_abierta_del_vendedor)
from verticalidades.distribucion.services.cobranza_fifo import registrar
from verticalidades.distribucion.services.facturacion import facturar_pedido
from verticalidades.distribucion.services.pedidos import guardar_pedido
from empresas.models import Empresa, PuntoVenta, Sucursal
from facturacion.models import ClienteProveedor,  TipoComprobante
from verticalidades.distribucion.models import ExtensionDistribuidora
from productos.models import Producto, Rubro, StockSucursal
from tesoreria.models import MedioPago, Recibo, RetiroCaja


class BaseVendedorTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Distribuidora Prueba", cuit="30111111118",
            tipo_actividad="DISTRIBUIDORA")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, nombre="Depósito Central", punto=1)
        PuntoVenta.objects.create(empresa=self.empresa, sucursal=self.sucursal, numero=4)
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa, inicio="2026-01-01", cierre="2026-12-31")
        self.usuario = User.objects.create_user(username="admin1", password="x", is_staff=True)

        TipoComprobante.objects.get_or_create(
            codigo='006', defaults={'detalle': "Factura B", 'signo': 1})
        TipoComprobante.objects.get_or_create(
            codigo='PRE', defaults={'detalle': "Comprobante Interno", 'signo': 1})

        cta_caja = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.1", cuenta="CAJA", imputable=1)
        cta_dif = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.9", cuenta="DIFERENCIAS", imputable=1)
        cta_reparto = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.2", cuenta="CAJA DE REPARTO", imputable=1)
        cta_cli = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.3", cuenta="DEUDORES", imputable=1)
        cta_vta = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="4.1.1", cuenta="VENTAS", imputable=1)
        cta_iva = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="2.1.1", cuenta="IVA DEBITO", imputable=1)
        ParametrosContables.objects.create(
            empresa=self.empresa, cta_clientes_default=cta_cli, cta_ventas=cta_vta,
            cta_iva_debito=cta_iva, cta_caja_central=cta_caja,
            cta_caja_mostrador=cta_caja, cta_diferencia_caja=cta_dif,
            cta_caja_reparto=cta_reparto, metodo_contabilizacion_ventas=1)
        MedioPago.objects.create(
            empresa=self.empresa, codigo='EFE-ARS', nombre="Efectivo",
            categoria='EFE', cuenta_contable=cta_caja)
        MedioPago.objects.create(
            empresa=self.empresa, codigo='TRA-BCO', nombre="Transferencia",
            categoria='TRA', cuenta_contable=cta_caja)

        self.zona = ZonaReparto.objects.create(
            empresa=self.empresa, nombre="San Cayetano", orden=1)
        self.romina = Personal.objects.create(
            empresa=self.empresa, nombre="Romina", es_vendedor=True, es_cobrador=True)

        rubro = Rubro.objects.create(empresa=self.empresa, detalle="LACTEOS",
                                     cta_ventas=cta_vta)
        self.producto = Producto.objects.create(
            empresa=self.empresa, detalle="Yogur x 900",
            precio_total=Decimal('1000.00'), rubro=rubro)
        StockSucursal.objects.create(
            producto=self.producto, sucursal=self.sucursal,
            stock_inicial=Decimal('99999.00'), cantidad=Decimal('99999.00'))

    def crear_cliente(self, nombre="Cliente Esquivo"):
        cliente = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social=nombre, tipo_entidad=1,
            domicilio="Belgrano 100", condicion_iva="CONSUMIDOR FINAL",
            limite=Decimal('1000000.00'))
        ExtensionDistribuidora.objects.create(
            cliente=cliente, coeficiente_mayorista=Decimal('1.0000'))
        DomicilioEntrega.objects.create(
            empresa=self.empresa, cliente=cliente, nombre="Casa Central",
            domicilio="Belgrano 100", zona=self.zona, es_principal=True)
        return cliente

    def facturar(self, cliente, cantidad, condic=1, fecha=None):
        pedido = guardar_pedido(
            empresa_id=self.empresa.id, sucursal_id=self.sucursal.id,
            cliente=cliente, usuario=self.usuario, condic_destino=condic,
            items=[{'producto_id': self.producto.id, 'cantidad': cantidad,
                    'precio_unitario': 1000.0, 'total': 1000.0 * cantidad,
                    'descuento': 0}])
        facturar_pedido(pedido, self.usuario)
        pedido.refresh_from_db()
        if fecha:
            type(pedido.venta).objects.filter(pk=pedido.venta_id).update(fecha=fecha)
        return pedido.venta

    def cobrar(self, cliente, valores, vendedor=None):
        return registrar(None, cliente, valores, self.usuario,
                         cobrador=vendedor or self.romina,
                         sucursal_id=self.sucursal.id)


class CobranzaSinRepartoTestCase(BaseVendedorTestCase):
    def test_el_vendedor_cobra_sin_hoja_de_ruta(self):
        cliente = self.crear_cliente()
        factura = self.facturar(cliente, 10, fecha="2026-01-05")

        recibos = self.cobrar(cliente, [{'categoria': 'EFE', 'importe': Decimal('4000.00')}])

        self.assertEqual(len(recibos), 1)
        factura.refresh_from_db()
        self.assertEqual(Decimal(str(factura.saldo)), Decimal('6000.00'))

    def test_la_plata_siempre_tiene_un_responsable(self):
        """Sin reparto y sin cobrador no se sabe a quién reclamarle un faltante."""
        cliente = self.crear_cliente()
        self.facturar(cliente, 5)
        with self.assertRaises(ValueError):
            registrar(None, cliente, [{'categoria': 'EFE', 'importe': Decimal('1000.00')}],
                      self.usuario, sucursal_id=self.sucursal.id)

    def test_hace_falta_saber_en_que_sucursal_deposita(self):
        cliente = self.crear_cliente()
        self.facturar(cliente, 5)
        with self.assertRaises(ValueError):
            registrar(None, cliente, [{'categoria': 'EFE', 'importe': Decimal('1000.00')}],
                      self.usuario, cobrador=self.romina)

    def test_la_cobranza_cae_en_una_sesion_a_nombre_del_vendedor(self):
        """Para poder rendir hay que haber retenido."""
        cliente = self.crear_cliente()
        self.facturar(cliente, 10)
        recibos = self.cobrar(cliente, [{'categoria': 'EFE', 'importe': Decimal('4000.00')}])

        sesion = sesion_abierta_del_vendedor(self.romina, self.sucursal.id)
        self.assertIsNotNone(sesion)
        self.assertEqual(sesion.caja.tipo, 'R')
        self.assertEqual(recibos[0].sesion_caja_id, sesion.id)

    def test_dos_cobranzas_del_mismo_vendedor_caen_en_la_misma_sesion(self):
        primero = self.crear_cliente("Cliente Uno")
        segundo = self.crear_cliente("Cliente Dos")
        self.facturar(primero, 5)
        self.facturar(segundo, 5)

        a = self.cobrar(primero, [{'categoria': 'EFE', 'importe': Decimal('2000.00')}])
        b = self.cobrar(segundo, [{'categoria': 'EFE', 'importe': Decimal('3000.00')}])
        self.assertEqual(a[0].sesion_caja_id, b[0].sesion_caja_id)

    def test_el_satelite_queda_sin_reparto_y_con_cobrador(self):
        cliente = self.crear_cliente()
        self.facturar(cliente, 5)
        recibos = self.cobrar(cliente, [{'categoria': 'EFE', 'importe': Decimal('2000.00')}])

        satelite = CobranzaDistribucion.objects.get(recibo=recibos[0])
        self.assertIsNone(satelite.reparto_id)
        self.assertEqual(satelite.cobrador_id, self.romina.id)

    def test_valen_las_mismas_dos_reglas_de_imputacion(self):
        """No hay caso especial: el FIFO y la segmentación son los del reparto."""
        cliente = self.crear_cliente()
        factura = self.facturar(cliente, 5, condic=1, fecha="2026-01-01")
        pre = self.facturar(cliente, 3, condic=2, fecha="2026-02-01")

        self.cobrar(cliente, [{'categoria': 'EFE', 'importe': Decimal('3000.00')},
                              {'categoria': 'TRA', 'importe': Decimal('2000.00')}])

        pre.refresh_from_db()
        factura.refresh_from_db()
        # El efectivo se comió el PRE entero; la transferencia fue contra la factura.
        self.assertEqual(Decimal(str(pre.saldo)), Decimal('0.00'))
        self.assertEqual(Decimal(str(factura.saldo)), Decimal('3000.00'))


class RestriccionesTestCase(BaseVendedorTestCase):
    def test_una_cobranza_sin_reparto_ni_cobrador_no_puede_existir_en_la_base(self):
        cliente = self.crear_cliente()
        self.facturar(cliente, 5)
        recibo = Recibo.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, ejercicio=self.ejercicio,
            cliente=cliente, fecha="2026-02-10", punto=1, total=Decimal('100.00'))

        with self.assertRaises(IntegrityError):
            CobranzaDistribucion.objects.create(
                recibo=recibo, reparto=None, cobrador=None)

    def test_una_rendicion_necesita_exactamente_un_origen(self):
        retiro = RetiroCaja.objects.create(
            sesion=self._sesion_cualquiera(), tipo='C', usuario=self.usuario,
            sucursal_origen=self.sucursal, sucursal_destino=self.sucursal,
            efectivo_pesos=Decimal('100.00'))

        with self.assertRaises(IntegrityError):
            RendicionReparto.objects.create(reparto=None, vendedor=None, retiro=retiro)

    def _sesion_cualquiera(self):
        from verticalidades.distribucion.services.caja_reparto import caja_recaudadora
        from tesoreria.models import CajaSesion

        return CajaSesion.objects.create(
            caja=caja_recaudadora(self.empresa.id, self.sucursal.id),
            usuario=self.usuario, estado='A')


class RendicionDelVendedorTestCase(BaseVendedorTestCase):
    def _con_cobranza(self, efectivo='5000.00'):
        cliente = self.crear_cliente()
        self.facturar(cliente, 20)
        self.cobrar(cliente, [{'categoria': 'EFE', 'importe': Decimal(efectivo)}])
        return cliente

    def test_el_resumen_muestra_lo_que_todavia_no_rindio(self):
        self._con_cobranza('5000.00')
        datos = resumen_vendedor(self.romina)
        self.assertEqual(datos['efectivo_cobrado'], Decimal('5000.00'))
        self.assertEqual(datos['pendiente_de_rendir'], Decimal('5000.00'))

    def test_lo_trazable_no_se_rinde_en_mano(self):
        """La transferencia ya está en el banco: no la trae en el bolsillo."""
        cliente = self.crear_cliente()
        self.facturar(cliente, 20)
        self.cobrar(cliente, [{'categoria': 'EFE', 'importe': Decimal('4000.00')},
                              {'categoria': 'TRA', 'importe': Decimal('3000.00')}])

        datos = resumen_vendedor(self.romina)
        self.assertEqual(datos['cobrado'], Decimal('7000.00'))
        self.assertEqual(datos['efectivo_cobrado'], Decimal('4000.00'))

    def test_rendir_deja_el_retiro_en_transito_a_nombre_del_vendedor(self):
        self._con_cobranza('5000.00')
        retiro = rendir_vendedor(self.romina, self.usuario,
                                 efectivo_pesos=Decimal('5000.00'),
                                 sucursal_id=self.sucursal.id)

        self.assertEqual(retiro.estado, 'T')
        vinculo = RendicionReparto.objects.get(retiro=retiro)
        self.assertIsNone(vinculo.reparto_id)
        self.assertEqual(vinculo.vendedor_id, self.romina.id)

    def test_rendir_cierra_la_sesion_del_vendedor(self):
        self._con_cobranza('5000.00')
        sesion = sesion_abierta_del_vendedor(self.romina, self.sucursal.id)

        rendir_vendedor(self.romina, self.usuario, efectivo_pesos=Decimal('5000.00'),
                        sucursal_id=self.sucursal.id)

        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'C')
        self.assertIsNone(sesion_abierta_del_vendedor(self.romina, self.sucursal.id))

    def test_no_se_rinde_sin_haber_cobrado(self):
        with self.assertRaises(ValueError):
            rendir_vendedor(self.romina, self.usuario, efectivo_pesos=Decimal('1000.00'),
                            sucursal_id=self.sucursal.id)

    def test_no_se_rinde_un_importe_cero(self):
        self._con_cobranza('5000.00')
        with self.assertRaises(ValueError):
            rendir_vendedor(self.romina, self.usuario, efectivo_pesos=Decimal('0.00'),
                            sucursal_id=self.sucursal.id)

    def test_la_rendicion_del_vendedor_entra_en_la_misma_bandeja(self):
        """Para quien recibe es el mismo acto: contar lo que alguien trajo."""
        self._con_cobranza('5000.00')
        rendir_vendedor(self.romina, self.usuario, efectivo_pesos=Decimal('5000.00'),
                        sucursal_id=self.sucursal.id)

        pendientes = list(rendiciones_por_recibir(self.empresa.id, self.sucursal.id))
        self.assertEqual([p.vendedor_id for p in pendientes], [self.romina.id])

    def test_la_tesoreria_de_reparto_la_recibe_igual_que_la_de_un_reparto(self):
        self._con_cobranza('5000.00')
        retiro = rendir_vendedor(self.romina, self.usuario,
                                 efectivo_pesos=Decimal('5000.00'),
                                 sucursal_id=self.sucursal.id)

        recibir(retiro, self.usuario, contado_pesos=Decimal('4900.00'))

        retiro.refresh_from_db()
        self.assertEqual(retiro.estado, 'R')
        self.assertEqual(retiro.sesion_recepcion.caja.tipo, 'D')
        self.assertEqual(retiro.diferencia_pesos, Decimal('100.00'))

    def test_despues_de_rendir_una_cobranza_nueva_abre_otra_sesion(self):
        cliente = self._con_cobranza('5000.00')
        primera = sesion_abierta_del_vendedor(self.romina, self.sucursal.id)
        rendir_vendedor(self.romina, self.usuario, efectivo_pesos=Decimal('5000.00'),
                        sucursal_id=self.sucursal.id)

        self.cobrar(cliente, [{'categoria': 'EFE', 'importe': Decimal('1000.00')}])
        segunda = sesion_abierta_del_vendedor(self.romina, self.sucursal.id)
        self.assertIsNotNone(segunda)
        self.assertNotEqual(primera.id, segunda.id)


class VistaDelVendedorTestCase(BaseVendedorTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.usuario)
        sesion = self.client.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion['ejercicio_id'] = self.ejercicio.id
        sesion.save()

    def test_la_pantalla_pide_elegir_vendedor(self):
        respuesta = self.client.get(reverse('distribucion_cobranza_vendedor'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.context['vendedor'])

    def test_elegido_el_vendedor_muestra_su_resumen(self):
        cliente = self.crear_cliente()
        self.facturar(cliente, 10)
        self.cobrar(cliente, [{'categoria': 'EFE', 'importe': Decimal('3000.00')}])

        respuesta = self.client.get(
            reverse('distribucion_cobranza_vendedor'), {'vendedor': self.romina.id})
        self.assertEqual(respuesta.context['resumen']['efectivo_cobrado'],
                         Decimal('3000.00'))

    def test_cobrar_desde_la_pantalla(self):
        cliente = self.crear_cliente()
        factura = self.facturar(cliente, 10)

        self.client.post(reverse('distribucion_cobranza_vendedor'), {
            'accion': 'cobrar', 'vendedor': self.romina.id,
            'cliente': cliente.pk, 'valor_efe': '4.000,00'})

        factura.refresh_from_db()
        self.assertEqual(Decimal(str(factura.saldo)), Decimal('6000.00'))

    def test_rendir_desde_la_pantalla(self):
        cliente = self.crear_cliente()
        self.facturar(cliente, 10)
        self.cobrar(cliente, [{'categoria': 'EFE', 'importe': Decimal('3000.00')}])

        self.client.post(reverse('distribucion_cobranza_vendedor'), {
            'accion': 'rendir', 'vendedor': self.romina.id,
            'efectivo_pesos': '3.000,00'})

        vinculo = RendicionReparto.objects.get(vendedor=self.romina)
        self.assertEqual(vinculo.retiro.estado, 'T')
        self.assertEqual(vinculo.retiro.efectivo_pesos, Decimal('3000.00'))

    def test_el_vendedor_de_otra_empresa_no_se_ve(self):
        otra = Empresa.objects.create(nombre="Ajena", cuit="30222222229")
        ajeno = Personal.objects.create(empresa=otra, nombre="Ajeno", es_vendedor=True)

        respuesta = self.client.get(
            reverse('distribucion_cobranza_vendedor'), {'vendedor': ajeno.id})
        self.assertIsNone(respuesta.context['vendedor'])
