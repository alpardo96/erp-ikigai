"""Tesorería de Reparto: el nivel intermedio del circuito de fondos (Plan 076 §B).

    cobranzas ─► CAJA RECAUDADORA 'R'      una sesión por reparto
                        │  el repartidor declara, el administrativo cuenta y acepta
                        ▼
                 TESORERÍA DE REPARTO 'D'  UNA POR SUCURSAL
                        │  retiro / cierre de caja (circuito existente)
                        ▼
                 CAJA TESORERÍA 'T'

Incluye la prueba de la regresión de §B.2: el cierre de mostrador no debe poder tomar la
sesión de un reparto.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from contable.models import Cuenta, Ejercicio, ParametrosContables
from verticalidades.distribucion.models import (DomicilioEntrega, Personal, RendicionReparto, Reparto,
                                 Vehiculo, ZonaReparto)
from verticalidades.distribucion.services.caja_reparto import (caja_recaudadora, recibir, rendir,
                                                rendiciones_por_recibir,
                                                sesion_de_tesoreria_reparto,
                                                tesoreria_reparto)
from verticalidades.distribucion.services.cobranza_fifo import registrar
from verticalidades.distribucion.services.facturacion import facturar_pedido
from verticalidades.distribucion.services.pedidos import guardar_pedido
from verticalidades.distribucion.services.reparto import agregar_paradas, cerrar_reparto, crear_reparto
from empresas.models import Empresa, PuntoVenta, Sucursal
from facturacion.models import ClienteProveedor,  TipoComprobante
from verticalidades.distribucion.models import ExtensionDistribuidora
from productos.models import Producto, Rubro, StockSucursal
from tesoreria.models import Caja, CajaSesion, MedioPago, MovimientoCaja, RetiroCaja


class BaseTesoreriaRepartoTestCase(TestCase):
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

        self.cta_caja = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.1", cuenta="CAJA", imputable=1)
        self.cta_dif = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.9", cuenta="DIFERENCIAS DE CAJA", imputable=1)
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
            cta_iva_debito=cta_iva, cta_caja_central=self.cta_caja,
            cta_caja_mostrador=self.cta_caja, cta_diferencia_caja=self.cta_dif,
            cta_caja_reparto=cta_reparto, metodo_contabilizacion_ventas=1)
        MedioPago.objects.create(
            empresa=self.empresa, codigo='EFE-ARS', nombre="Efectivo",
            categoria='EFE', cuenta_contable=self.cta_caja)

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

    def crear_cliente(self, nombre="Cliente Uno"):
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

    def reparto_con_cobranza(self, nombre="Cliente Uno", efectivo='5000.00'):
        cliente = self.crear_cliente(nombre)
        pedido = guardar_pedido(
            empresa_id=self.empresa.id, sucursal_id=self.sucursal.id,
            cliente=cliente, usuario=self.usuario, condic_destino=1,
            items=[{'producto_id': self.producto.id, 'cantidad': 20,
                    'precio_unitario': 1000.0, 'total': 20000.0, 'descuento': 0}])
        facturar_pedido(pedido, self.usuario)
        pedido.refresh_from_db()

        reparto = crear_reparto(
            self.empresa.id, self.sucursal.id, self.usuario,
            vehiculo=self.vehiculo, zona=self.zona, responsables=[self.juan])
        agregar_paradas(reparto, [pedido])
        cerrar_reparto(reparto, self.usuario)
        reparto.refresh_from_db()

        registrar(reparto, cliente,
                  [{'categoria': 'EFE', 'importe': Decimal(efectivo)}],
                  self.usuario, parada=reparto.paradas.get())
        return reparto


class LaCajaIntermediaTestCase(BaseTesoreriaRepartoTestCase):
    def test_la_tesoreria_de_reparto_tiene_tipo_propio(self):
        caja = tesoreria_reparto(self.empresa.id, self.sucursal.id)
        self.assertEqual(caja.tipo, 'D')

    def test_es_una_sola_por_sucursal(self):
        """Acá rinden todos los repartos: lo que los separa es la sesión de origen."""
        primera = tesoreria_reparto(self.empresa.id, self.sucursal.id)
        segunda = tesoreria_reparto(self.empresa.id, self.sucursal.id)
        self.assertEqual(primera.id, segunda.id)
        self.assertEqual(Caja.objects.filter(empresa=self.empresa, tipo='D').count(), 1)

    def test_su_sesion_no_depende_del_cajero_de_turno(self):
        """Siempre hay una activa: quien recibe a un repartidor no queda bloqueado."""
        otro = User.objects.create_user(username="admin2", password="x")
        primera = sesion_de_tesoreria_reparto(self.empresa.id, self.sucursal.id, self.usuario)
        segunda = sesion_de_tesoreria_reparto(self.empresa.id, self.sucursal.id, otro)
        self.assertEqual(primera.id, segunda.id)

    def test_convive_con_la_mostrador_y_con_la_recaudadora(self):
        Caja.objects.create(empresa=self.empresa, sucursal=self.sucursal,
                            nombre="Mostrador", tipo='M')
        caja_recaudadora(self.empresa.id, self.sucursal.id)
        tesoreria_reparto(self.empresa.id, self.sucursal.id)

        tipos = set(Caja.objects.filter(
            empresa=self.empresa, sucursal=self.sucursal).values_list('tipo', flat=True))
        self.assertEqual(tipos, {'M', 'R', 'D'})


class LosDosPasosTestCase(BaseTesoreriaRepartoTestCase):
    def test_rendir_deja_la_plata_en_transito_hacia_la_intermedia(self):
        reparto = self.reparto_con_cobranza()
        retiro = rendir(reparto, self.usuario, efectivo_pesos=Decimal('5000.00'))

        self.assertEqual(retiro.estado, 'T')
        self.assertEqual(retiro.sesion_id, reparto.sesion_caja_id)
        self.assertEqual(retiro.sesion.caja.tipo, 'R')

    def test_el_primer_tramo_no_genera_asiento_de_traslado(self):
        """Las dos cajas comparten cuenta contable: el asiento sería Debe y Haber sobre
        la misma cuenta. Peor sería asentar contra Caja Central plata que sigue en la calle."""
        reparto = self.reparto_con_cobranza()
        retiro = rendir(reparto, self.usuario, efectivo_pesos=Decimal('5000.00'))
        self.assertEqual(retiro.asientos.count(), 0)

    def test_recibir_deposita_lo_contado_en_la_intermedia(self):
        reparto = self.reparto_con_cobranza()
        retiro = rendir(reparto, self.usuario, efectivo_pesos=Decimal('5000.00'))

        recibir(retiro, self.usuario, contado_pesos=Decimal('5000.00'))

        retiro.refresh_from_db()
        self.assertEqual(retiro.estado, 'R')
        self.assertEqual(retiro.sesion_recepcion.caja.tipo, 'D')
        ingreso = MovimientoCaja.objects.get(sesion=retiro.sesion_recepcion, tipo='I')
        self.assertEqual(Decimal(str(ingreso.importe)), Decimal('5000.00'))

    def test_la_caja_refleja_lo_contado_y_no_lo_declarado(self):
        """La caja tiene que decir la plata que efectivamente está adentro."""
        reparto = self.reparto_con_cobranza()
        retiro = rendir(reparto, self.usuario, efectivo_pesos=Decimal('5000.00'))

        recibir(retiro, self.usuario, contado_pesos=Decimal('4800.00'))

        ingreso = MovimientoCaja.objects.get(
            sesion=retiro.sesion_recepcion, tipo='I')
        self.assertEqual(Decimal(str(ingreso.importe)), Decimal('4800.00'))

    def test_el_faltante_queda_registrado_con_su_asiento(self):
        """No se absorbe en silencio: el que declara no es el mismo que cuenta."""
        reparto = self.reparto_con_cobranza()
        retiro = rendir(reparto, self.usuario, efectivo_pesos=Decimal('5000.00'))

        recibir(retiro, self.usuario, contado_pesos=Decimal('4800.00'))

        retiro.refresh_from_db()
        self.assertEqual(retiro.diferencia_pesos, Decimal('200.00'))
        self.assertIsNotNone(retiro.asiento_diferencia_id)

    def test_sin_diferencia_no_se_genera_asiento_de_ajuste(self):
        reparto = self.reparto_con_cobranza()
        retiro = rendir(reparto, self.usuario, efectivo_pesos=Decimal('5000.00'))
        recibir(retiro, self.usuario, contado_pesos=Decimal('5000.00'))

        retiro.refresh_from_db()
        self.assertEqual(retiro.diferencia_pesos, Decimal('0.00'))
        self.assertIsNone(retiro.asiento_diferencia_id)

    def test_no_se_recibe_dos_veces_la_misma_rendicion(self):
        reparto = self.reparto_con_cobranza()
        retiro = rendir(reparto, self.usuario, efectivo_pesos=Decimal('5000.00'))
        recibir(retiro, self.usuario, contado_pesos=Decimal('5000.00'))

        retiro.refresh_from_db()
        with self.assertRaises(ValueError):
            recibir(retiro, self.usuario, contado_pesos=Decimal('5000.00'))

    def test_no_se_recibe_un_importe_negativo(self):
        reparto = self.reparto_con_cobranza()
        retiro = rendir(reparto, self.usuario, efectivo_pesos=Decimal('5000.00'))
        with self.assertRaises(ValueError):
            recibir(retiro, self.usuario, contado_pesos=Decimal('-1.00'))

    def test_la_bandeja_lista_lo_que_esta_en_transito(self):
        reparto = self.reparto_con_cobranza()
        retiro = rendir(reparto, self.usuario, efectivo_pesos=Decimal('5000.00'))

        pendientes = list(rendiciones_por_recibir(self.empresa.id, self.sucursal.id))
        self.assertEqual([p.reparto_id for p in pendientes], [reparto.id])

        recibir(retiro, self.usuario, contado_pesos=Decimal('5000.00'))
        self.assertEqual(list(rendiciones_por_recibir(self.empresa.id, self.sucursal.id)), [])

    def test_dos_repartos_acumulan_en_la_misma_caja_intermedia(self):
        """De acá sale UNA sola rendición consolidada a Tesorería."""
        primero = self.reparto_con_cobranza("Cliente Uno", efectivo='5000.00')
        segundo = self.reparto_con_cobranza("Cliente Dos", efectivo='3000.00')

        for reparto, importe in ((primero, '5000.00'), (segundo, '3000.00')):
            retiro = rendir(reparto, self.usuario, efectivo_pesos=Decimal(importe))
            recibir(retiro, self.usuario, contado_pesos=Decimal(importe))

        sesion = sesion_de_tesoreria_reparto(self.empresa.id, self.sucursal.id, self.usuario)
        total = sum(Decimal(str(m.importe))
                    for m in MovimientoCaja.objects.filter(sesion=sesion, tipo='I'))
        self.assertEqual(total, Decimal('8000.00'))


class RegresionCierreDeMostradorTestCase(BaseTesoreriaRepartoTestCase):
    """Plan 076 §B.2: el cierre de mostrador NO debe tomar la sesión de un reparto.

    `caja_recaudadora()` creó una caja en la misma sucursal donde vive la mostrador, y las
    pantallas de retiro y cierre buscaban «la caja de la sucursal» sin filtrar por tipo. Un
    cajero que además hubiera cerrado un reparto tenía DOS sesiones abiertas a su nombre.
    """

    def setUp(self):
        super().setUp()
        self.mostrador = Caja.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, nombre="Mostrador", tipo='M')
        self.client = Client()
        self.client.force_login(self.usuario)
        sesion = self.client.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion['ejercicio_id'] = self.ejercicio.id
        sesion.save()

    def test_el_cierre_de_mostrador_no_ve_la_sesion_del_reparto(self):
        # El mismo usuario cierra un reparto (abre sesión sobre la recaudadora) y NO tiene
        # sesión de mostrador abierta.
        self.reparto_con_cobranza()
        self.assertTrue(
            CajaSesion.objects.filter(caja__tipo='R', usuario=self.usuario, estado='A').exists())

        respuesta = self.client.get(reverse('caja_cierre_modal'))
        self.assertEqual(respuesta.status_code, 400,
                         "El cierre de mostrador tomó una sesión que no es suya.")

    def test_el_retiro_de_mostrador_tampoco_la_ve(self):
        self.reparto_con_cobranza()
        respuesta = self.client.get(reverse('caja_retiro_modal'))
        self.assertEqual(respuesta.status_code, 400)

    def test_con_su_sesion_de_mostrador_abierta_el_cierre_funciona(self):
        """El filtro no rompe el circuito de siempre."""
        self.reparto_con_cobranza()
        CajaSesion.objects.create(
            caja=self.mostrador, usuario=self.usuario, estado='A',
            creado_por=self.usuario, modificado_por=self.usuario)

        respuesta = self.client.get(reverse('caja_cierre_modal'))
        self.assertEqual(respuesta.status_code, 200)


class VistaDeRecepcionTestCase(BaseTesoreriaRepartoTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.usuario)
        sesion = self.client.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion['ejercicio_id'] = self.ejercicio.id
        sesion.save()

    def test_la_bandeja_muestra_las_rendiciones_en_transito(self):
        reparto = self.reparto_con_cobranza()
        rendir(reparto, self.usuario, efectivo_pesos=Decimal('5000.00'))

        respuesta = self.client.get(reverse('distribucion_recepcion_rendiciones'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, f"Reparto {reparto.numero}")

    def test_recibir_desde_la_pantalla(self):
        reparto = self.reparto_con_cobranza()
        retiro = rendir(reparto, self.usuario, efectivo_pesos=Decimal('5000.00'))
        vinculo = RendicionReparto.objects.get(retiro=retiro)

        self.client.post(reverse('distribucion_recepcion_rendiciones'),
                         {'rendicion': vinculo.id, 'contado_pesos': '4.900,00'})

        retiro.refresh_from_db()
        self.assertEqual(retiro.estado, 'R')
        self.assertEqual(retiro.efectivo_pesos_recibido, Decimal('4900.00'))
        self.assertEqual(retiro.diferencia_pesos, Decimal('100.00'))

    def test_la_rendicion_de_otra_empresa_no_se_recibe(self):
        otra = Empresa.objects.create(nombre="Ajena", cuit="30222222229")
        sucursal = Sucursal.objects.create(empresa=otra, nombre="Única", punto=1)
        reparto = crear_reparto(otra.id, sucursal.id, self.usuario)
        retiro = RetiroCaja.objects.create(
            sesion=CajaSesion.objects.create(
                caja=Caja.objects.create(empresa=otra, sucursal=sucursal,
                                         nombre="R", tipo='R'),
                usuario=self.usuario, estado='A'),
            tipo='C', usuario=self.usuario,
            sucursal_origen=sucursal, sucursal_destino=sucursal,
            efectivo_pesos=Decimal('100.00'))
        vinculo = RendicionReparto.objects.create(reparto=reparto, retiro=retiro)

        respuesta = self.client.post(reverse('distribucion_recepcion_rendiciones'),
                                     {'rendicion': vinculo.id, 'contado_pesos': '100,00'})
        self.assertEqual(respuesta.status_code, 404)
