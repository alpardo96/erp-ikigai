"""Parada de sólo cobranza en la hoja de ruta (Plan 076 §A).

Un cliente con saldo que NO hizo pedido. El repartidor pasa únicamente a cobrarle.

    EL COBRO MÍNIMO EXISTE PORQUE HAY MERCADERÍA DE POR MEDIO: es la condición para
    dejarla. Acá no se entrega nada, así que NO HAY PALANCA.

Definición del usuario: *"Puede tranquilamente ser una cobranza parcial como cualquier
otra… la mayoría de las veces el cliente o no entrega nada o entrega sólo un pago parcial.
Cliente que no hizo pedido es más que probable que no esté entre sus prioridades el
pagarnos."*
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse

from contable.models import Cuenta, Ejercicio, ParametrosContables
from verticalidades.distribucion.models import (DomicilioEntrega, Personal, Reparto, RepartoParada,
                                 Vehiculo, ZonaReparto)
from verticalidades.distribucion.services.cobranza_fifo import registrar
from verticalidades.distribucion.services.devoluciones import (crear_recepcion, marcar_entregada,
                                                marcar_no_entregada, paradas_por_recibir)
from verticalidades.distribucion.services.facturacion import facturar_pedido
from verticalidades.distribucion.services.pedidos import guardar_pedido
from verticalidades.distribucion.services.reparto import (agregar_parada_de_cobranza, agregar_paradas,
                                           cerrar_reparto, consolidado, crear_reparto,
                                           hoja_de_ruta, totales_hoja_de_ruta)
from empresas.models import Empresa, PuntoVenta, Sucursal
from facturacion.models import ClienteProveedor,  TipoComprobante
from verticalidades.distribucion.models import ExtensionDistribuidora
from productos.models import Producto, Rubro, StockSucursal


class BaseParadaCobranzaTestCase(TestCase):
    def setUp(self):
        from tesoreria.models import MedioPago

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
            cta_caja_mostrador=cta_caja, cta_caja_reparto=cta_reparto,
            metodo_contabilizacion_ventas=1)
        MedioPago.objects.create(
            empresa=self.empresa, codigo='EFE-ARS', nombre="Efectivo",
            categoria='EFE', cuenta_contable=cta_caja)

        self.zona = ZonaReparto.objects.create(
            empresa=self.empresa, nombre="San Cayetano", orden=1)
        self.vehiculo = Vehiculo.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, patente="AB123CD",
            descripcion="Furgón", capacidad_kg=Decimal('5000.00'))
        self.juan = Personal.objects.create(
            empresa=self.empresa, nombre="Juan", es_repartidor=True)

        rubro = Rubro.objects.create(empresa=self.empresa, detalle="LACTEOS",
                                     cta_ventas=cta_vta)
        self.producto = Producto.objects.create(
            empresa=self.empresa, detalle="Yogur x 900",
            precio_total=Decimal('1000.00'), peso_unitario_kg=Decimal('2.000'),
            rubro=rubro)
        StockSucursal.objects.create(
            producto=self.producto, sucursal=self.sucursal,
            stock_inicial=Decimal('99999.00'), cantidad=Decimal('99999.00'))

    # ------------------------------------------------------------------ helpers
    def crear_cliente(self, nombre="Cliente Uno", limite='1000000.00'):
        cliente = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social=nombre, tipo_entidad=1,
            domicilio="Belgrano 100", condicion_iva="CONSUMIDOR FINAL",
            limite=Decimal(limite))
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
        return pedido, pedido.venta

    def reparto(self):
        return crear_reparto(
            self.empresa.id, self.sucursal.id, self.usuario,
            vehiculo=self.vehiculo, zona=self.zona, responsables=[self.juan])


class ArmadoTestCase(BaseParadaCobranzaTestCase):
    def test_se_agrega_un_cliente_con_saldo_sin_comprobante(self):
        deudor = self.crear_cliente("Deudor Viejo")
        self.facturar(deudor, 8, fecha="2026-01-05")
        reparto = self.reparto()

        parada = agregar_parada_de_cobranza(reparto, deudor, self.usuario)

        self.assertEqual(parada.tipo, RepartoParada.COBRANZA)
        self.assertTrue(parada.es_cobranza)
        self.assertIsNone(parada.venta_id)
        self.assertIsNone(parada.pedido_id)
        self.assertEqual(parada.cliente_id, deudor.pk)

    def test_el_domicilio_queda_congelado_en_la_parada(self):
        deudor = self.crear_cliente("Deudor Viejo")
        reparto = self.reparto()
        parada = agregar_parada_de_cobranza(reparto, deudor, self.usuario)

        self.assertIn("BELGRANO 100", parada.domicilio_entrega.upper())

    def test_no_se_agrega_dos_veces_al_mismo_cliente(self):
        deudor = self.crear_cliente("Deudor Viejo")
        reparto = self.reparto()
        agregar_parada_de_cobranza(reparto, deudor, self.usuario)

        with self.assertRaises(ValueError):
            agregar_parada_de_cobranza(reparto, deudor, self.usuario)

    def test_no_se_agregan_paradas_a_un_reparto_cerrado(self):
        cliente = self.crear_cliente("Con Pedido")
        pedido, _ = self.facturar(cliente, 5)
        reparto = self.reparto()
        agregar_paradas(reparto, [pedido])
        cerrar_reparto(reparto, self.usuario)

        with self.assertRaises(ValueError):
            agregar_parada_de_cobranza(reparto, self.crear_cliente("Tarde"), self.usuario)

    def test_la_parada_de_entrega_guarda_su_cliente_y_domicilio(self):
        """Dejaron de ser properties derivadas: ahora son campos propios."""
        cliente = self.crear_cliente("Con Pedido")
        pedido, venta = self.facturar(cliente, 5)
        reparto = self.reparto()
        agregar_paradas(reparto, [pedido])

        parada = reparto.paradas.get()
        self.assertEqual(parada.tipo, RepartoParada.ENTREGA)
        self.assertEqual(parada.cliente_id, cliente.pk)
        self.assertTrue(parada.domicilio_entrega)


class RestriccionesDeBaseTestCase(BaseParadaCobranzaTestCase):
    """Las reglas inflexibles viven en la base, no en el código."""

    def test_una_entrega_sin_comprobante_es_imposible(self):
        cliente = self.crear_cliente()
        reparto = self.reparto()
        with self.assertRaises(IntegrityError):
            RepartoParada.objects.create(
                reparto=reparto, tipo=RepartoParada.ENTREGA,
                cliente=cliente, venta=None, pedido=None, orden=1)

    def test_una_cobranza_con_comprobante_es_imposible(self):
        cliente = self.crear_cliente()
        pedido, venta = self.facturar(cliente, 5)
        reparto = self.reparto()
        with self.assertRaises(IntegrityError):
            RepartoParada.objects.create(
                reparto=reparto, tipo=RepartoParada.COBRANZA,
                cliente=cliente, venta=venta, pedido=pedido, orden=1)

    def test_un_comprobante_sigue_entrando_en_un_solo_reparto(self):
        """El UniqueConstraint sobre `venta` sigue vigente pese a los nulos."""
        cliente = self.crear_cliente()
        pedido, _ = self.facturar(cliente, 5)
        primero = self.reparto()
        agregar_paradas(primero, [pedido])

        segundo = self.reparto()
        self.assertEqual(agregar_paradas(segundo, [pedido]), 0)

    def test_varias_paradas_de_cobranza_conviven_en_el_mismo_reparto(self):
        """Todas tienen `venta = NULL`: el índice único no debe estorbarlas."""
        reparto = self.reparto()
        for nombre in ("Deudor Uno", "Deudor Dos", "Deudor Tres"):
            agregar_parada_de_cobranza(reparto, self.crear_cliente(nombre), self.usuario)

        self.assertEqual(reparto.paradas.count(), 3)


class CobroMinimoTestCase(BaseParadaCobranzaTestCase):
    """La corrección central del plan: sin mercadería no hay palanca."""

    def test_el_cobro_minimo_de_una_parada_de_cobranza_es_cero(self):
        deudor = self.crear_cliente("Deudor Viejo", limite='1000.00')
        self.facturar(deudor, 8, fecha="2026-01-05")   # queda muy pasado de límite
        reparto = self.reparto()
        agregar_parada_de_cobranza(reparto, deudor, self.usuario)
        cerrar_reparto(reparto, self.usuario)

        parada = reparto.paradas.get()
        self.assertEqual(parada.cobro_minimo, Decimal('0.00'))

    def test_se_congela_el_saldo_como_dato_para_reclamar(self):
        deudor = self.crear_cliente("Deudor Viejo")
        self.facturar(deudor, 8, fecha="2026-01-05")
        reparto = self.reparto()
        agregar_parada_de_cobranza(reparto, deudor, self.usuario)
        cerrar_reparto(reparto, self.usuario)

        parada = reparto.paradas.get()
        self.assertEqual(parada.saldo_anterior, Decimal('8000.00'))

    def test_la_parada_de_entrega_conserva_su_cobro_minimo(self):
        """La regla vieja no cambió donde sí hay mercadería."""
        cliente = self.crear_cliente("Pasado De Limite", limite='1000.00')
        pedido, _ = self.facturar(cliente, 5)
        reparto = self.reparto()
        agregar_paradas(reparto, [pedido])
        cerrar_reparto(reparto, self.usuario)

        parada = reparto.paradas.get()
        self.assertEqual(parada.cobro_minimo, Decimal('4000.00'))

    def test_el_esperado_del_reparto_no_cuenta_las_paradas_de_cobranza(self):
        """No se puede esperar lo que no se tiene con qué exigir."""
        from verticalidades.distribucion.services.caja_reparto import resumen

        cliente = self.crear_cliente("Pasado De Limite", limite='1000.00')
        pedido, _ = self.facturar(cliente, 5)
        deudor = self.crear_cliente("Deudor Viejo", limite='0.00')
        self.facturar(deudor, 8, fecha="2026-01-05")

        reparto = self.reparto()
        agregar_paradas(reparto, [pedido])
        agregar_parada_de_cobranza(reparto, deudor, self.usuario)
        cerrar_reparto(reparto, self.usuario)

        self.assertEqual(resumen(reparto)['esperado'], Decimal('4000.00'))


class HojaDeRutaYConsolidadoTestCase(BaseParadaCobranzaTestCase):
    def test_la_parada_de_cobranza_entra_en_el_orden_alfabetico(self):
        """Se ordena por el cliente PROPIO de la parada, no por el del comprobante."""
        zeta = self.crear_cliente("ZETA CON PEDIDO")
        pedido, _ = self.facturar(zeta, 5)
        alfa = self.crear_cliente("ALFA SOLO COBRANZA")
        self.facturar(alfa, 3, fecha="2026-01-05")

        reparto = self.reparto()
        agregar_paradas(reparto, [pedido])
        agregar_parada_de_cobranza(reparto, alfa, self.usuario)
        cerrar_reparto(reparto, self.usuario)

        nombres = [p.cliente.razon_social for p in hoja_de_ruta(reparto)]
        self.assertEqual(nombres, ["ALFA SOLO COBRANZA", "ZETA CON PEDIDO"])

    def test_un_reparto_de_pura_cobranza_da_consolidado_vacio(self):
        """No se carga nada al vehículo: es exactamente lo correcto."""
        reparto = self.reparto()
        for nombre in ("Deudor Uno", "Deudor Dos"):
            deudor = self.crear_cliente(nombre)
            self.facturar(deudor, 4, fecha="2026-01-05")
            agregar_parada_de_cobranza(reparto, deudor, self.usuario)
        cerrar_reparto(reparto, self.usuario)

        filas, totales = consolidado(reparto)
        self.assertEqual(filas, [])
        self.assertEqual(totales['kilos'], Decimal('0.00'))

    def test_los_totales_separan_lo_que_se_entrega_de_lo_que_se_reclama(self):
        cliente = self.crear_cliente("Con Pedido")
        pedido, _ = self.facturar(cliente, 5)
        deudor = self.crear_cliente("Deudor Viejo")
        self.facturar(deudor, 3, fecha="2026-01-05")

        reparto = self.reparto()
        agregar_paradas(reparto, [pedido])
        agregar_parada_de_cobranza(reparto, deudor, self.usuario)
        cerrar_reparto(reparto, self.usuario)

        totales = totales_hoja_de_ruta(reparto)
        self.assertEqual(totales['paradas'], 2)
        self.assertEqual(totales['paradas_de_cobranza'], 1)
        self.assertEqual(totales['total'], Decimal('5000.00'))
        self.assertEqual(totales['saldo_a_reclamar'], Decimal('3000.00'))


class EntregaYDevolucionesTestCase(BaseParadaCobranzaTestCase):
    """Sin mercadería no hay entrega que registrar ni devolución que recibir."""

    def _parada_de_cobranza(self):
        deudor = self.crear_cliente("Deudor Viejo")
        self.facturar(deudor, 4, fecha="2026-01-05")
        reparto = self.reparto()
        parada = agregar_parada_de_cobranza(reparto, deudor, self.usuario)
        cerrar_reparto(reparto, self.usuario)
        reparto.refresh_from_db()
        return reparto, parada, deudor

    def test_no_se_marca_como_entregada(self):
        _, parada, _ = self._parada_de_cobranza()
        with self.assertRaises(ValueError):
            marcar_entregada(parada, self.usuario)

    def test_no_se_marca_como_no_entregada(self):
        _, parada, _ = self._parada_de_cobranza()
        with self.assertRaises(ValueError):
            marcar_no_entregada(parada, "no estaba")

    def test_no_se_le_abre_una_recepcion_de_devoluciones(self):
        _, parada, _ = self._parada_de_cobranza()
        with self.assertRaises(ValueError):
            crear_recepcion(parada, self.usuario)

    def test_no_figura_entre_las_paradas_por_recibir(self):
        reparto, _, _ = self._parada_de_cobranza()
        self.assertEqual(list(paradas_por_recibir(reparto)), [])


class CobranzaSobreLaParadaTestCase(BaseParadaCobranzaTestCase):
    """Lo que traiga se imputa con el procedimiento estándar, sin caso especial."""

    def test_el_pago_parcial_se_imputa_a_lo_mas_antiguo(self):
        deudor = self.crear_cliente("Deudor Viejo")
        _, vieja = self.facturar(deudor, 3, fecha="2026-01-05")
        _, nueva = self.facturar(deudor, 5, fecha="2026-02-05")

        reparto = self.reparto()
        parada = agregar_parada_de_cobranza(reparto, deudor, self.usuario)
        cerrar_reparto(reparto, self.usuario)
        reparto.refresh_from_db()

        registrar(reparto, deudor, [{'categoria': 'EFE', 'importe': Decimal('2000.00')}],
                  self.usuario, parada=reparto.paradas.get())

        vieja.refresh_from_db()
        nueva.refresh_from_db()
        self.assertEqual(Decimal(str(vieja.saldo)), Decimal('1000.00'))
        self.assertEqual(Decimal(str(nueva.saldo)), Decimal('5000.00'))

    def test_el_efectivo_prioriza_los_comprobantes_no_fiscales(self):
        deudor = self.crear_cliente("Deudor Viejo")
        _, factura = self.facturar(deudor, 5, condic=1, fecha="2026-01-01")
        _, pre = self.facturar(deudor, 3, condic=2, fecha="2026-02-01")

        reparto = self.reparto()
        agregar_parada_de_cobranza(reparto, deudor, self.usuario)
        cerrar_reparto(reparto, self.usuario)
        reparto.refresh_from_db()

        registrar(reparto, deudor, [{'categoria': 'EFE', 'importe': Decimal('3000.00')}],
                  self.usuario, parada=reparto.paradas.get())

        pre.refresh_from_db()
        factura.refresh_from_db()
        self.assertEqual(Decimal(str(pre.saldo)), Decimal('0.00'))
        self.assertEqual(Decimal(str(factura.saldo)), Decimal('5000.00'))

    def test_el_cliente_puede_no_entregar_nada(self):
        """El caso más frecuente: la parada queda sin cobranza y no rompe nada."""
        from verticalidades.distribucion.services.caja_reparto import resumen

        deudor = self.crear_cliente("Deudor Viejo")
        self.facturar(deudor, 4, fecha="2026-01-05")
        reparto = self.reparto()
        agregar_parada_de_cobranza(reparto, deudor, self.usuario)
        cerrar_reparto(reparto, self.usuario)
        reparto.refresh_from_db()

        datos = resumen(reparto)
        self.assertEqual(datos['cobrado'], Decimal('0.00'))
        self.assertEqual(datos['esperado'], Decimal('0.00'))


class VistaDeArmadoTestCase(BaseParadaCobranzaTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.usuario)
        sesion = self.client.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion['ejercicio_id'] = self.ejercicio.id
        sesion.save()

    def test_se_agrega_la_parada_desde_la_pantalla(self):
        deudor = self.crear_cliente("Deudor Viejo")
        self.facturar(deudor, 4, fecha="2026-01-05")
        reparto = self.reparto()

        self.client.post(reverse('distribucion_reparto_detalle', args=[reparto.id]),
                         {'accion': 'agregar_cobranza', 'cliente': deudor.pk})

        parada = reparto.paradas.get()
        self.assertEqual(parada.tipo, RepartoParada.COBRANZA)
        self.assertEqual(parada.cliente_id, deudor.pk)

    def test_la_pantalla_ofrece_solo_clientes_con_saldo(self):
        deudor = self.crear_cliente("Deudor Viejo")
        self.facturar(deudor, 4, fecha="2026-01-05")
        self.crear_cliente("Al Dia")   # sin comprobantes: saldo cero
        reparto = self.reparto()

        respuesta = self.client.get(
            reverse('distribucion_reparto_detalle', args=[reparto.id]))
        nombres = [c.razon_social for c in respuesta.context['clientes_con_saldo']]
        self.assertIn("DEUDOR VIEJO", nombres)
        self.assertNotIn("AL DIA", nombres)

    def test_el_cliente_ya_agregado_deja_de_ofrecerse(self):
        deudor = self.crear_cliente("Deudor Viejo")
        self.facturar(deudor, 4, fecha="2026-01-05")
        reparto = self.reparto()
        agregar_parada_de_cobranza(reparto, deudor, self.usuario)

        respuesta = self.client.get(
            reverse('distribucion_reparto_detalle', args=[reparto.id]))
        nombres = [c.razon_social for c in respuesta.context['clientes_con_saldo']]
        self.assertNotIn("DEUDOR VIEJO", nombres)

    def test_la_hoja_de_ruta_imprime_la_parada_de_cobranza(self):
        deudor = self.crear_cliente("Deudor Viejo")
        self.facturar(deudor, 4, fecha="2026-01-05")
        reparto = self.reparto()
        agregar_parada_de_cobranza(reparto, deudor, self.usuario)
        cerrar_reparto(reparto, self.usuario)

        respuesta = self.client.get(
            reverse('distribucion_hoja_de_ruta', args=[reparto.id]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "DEUDOR VIEJO")
        self.assertContains(respuesta, "SÓLO COBRANZA")
