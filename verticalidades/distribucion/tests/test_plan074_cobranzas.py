"""Cobranzas del repartidor, caja recaudadora y rendición (Plan 074, fases 7 y 8).

Las dos reglas que ordenan la imputación no se negocian y están fijadas acá:

    1. Lo TRAZABLE va siempre contra `condic = 1`.
    2. El EFECTIVO cancela primero los PRE más viejos.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from contable.models import Cuenta, Ejercicio, ParametrosContables
from verticalidades.distribucion.models import (CarteraVendedor, CobranzaDistribucion, DiaVisita,
                                 DomicilioEntrega, Personal, RendicionReparto, Reparto,
                                 Vehiculo, ZonaReparto)
from verticalidades.distribucion.services.caja_reparto import (abrir_caja_del_reparto, caja_recaudadora,
                                                rendir, resumen)
from verticalidades.distribucion.services.cobranza_fifo import (comprobantes_abiertos, planificar,
                                                 registrar, saldo_fiscal, saldo_operativo)
from verticalidades.distribucion.services.facturacion import facturar_pedido
from verticalidades.distribucion.services.pedidos import guardar_pedido
from verticalidades.distribucion.services.reparto import agregar_paradas, cerrar_reparto, crear_reparto
from verticalidades.distribucion.services.saldos_clientes import listado
from empresas.models import Empresa, PuntoVenta, Sucursal
from facturacion.models import ClienteProveedor,  TipoComprobante
from verticalidades.distribucion.models import ExtensionDistribuidora
from productos.models import Producto, Rubro, StockSucursal
from tesoreria.models import Caja, MedioPago, Recibo, ReciboAplicacion, RetiroCaja


class BaseCobranzaTestCase(TestCase):
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
        TipoComprobante.objects.get_or_create(
            codigo='NCI', defaults={'detalle': "Nota de Crédito Interna", 'signo': -1})

        self.cta_caja = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.1", cuenta="CAJA", imputable=1)
        self.cta_banco = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.2", cuenta="BANCO", imputable=1)
        cta_reparto = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.2", cuenta="CAJA DE REPARTO", imputable=1)
        cta_cli = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.3", cuenta="DEUDORES", imputable=1)
        cta_vta = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="4.1.1", cuenta="VENTAS", imputable=1)
        cta_iva = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="2.1.1", cuenta="IVA DEBITO", imputable=1)
        # `cta_caja_mostrador` es la cuenta de efectivo fuera de Tesoreria: es la que usa
        # el traslado como ORIGEN cuando el repartidor rinde.
        ParametrosContables.objects.create(
            empresa=self.empresa, cta_clientes_default=cta_cli, cta_ventas=cta_vta,
            cta_iva_debito=cta_iva, cta_caja_central=self.cta_caja,
            cta_caja_mostrador=self.cta_caja, cta_caja_reparto=cta_reparto,
            metodo_contabilizacion_ventas=1)

        self.efectivo = MedioPago.objects.create(
            empresa=self.empresa, codigo='EFE-ARS', nombre="Efectivo",
            categoria='EFE', cuenta_contable=self.cta_caja)
        self.transferencia = MedioPago.objects.create(
            empresa=self.empresa, codigo='TRA-BCO', nombre="Transferencia",
            categoria='TRA', cuenta_contable=self.cta_banco)
        self.cheque = MedioPago.objects.create(
            empresa=self.empresa, codigo='CHQ-TER', nombre="Cheque de terceros",
            categoria='CHQ', cuenta_contable=self.cta_banco)

        self.zona = ZonaReparto.objects.create(
            empresa=self.empresa, nombre="San Cayetano", orden=1)
        self.vehiculo = Vehiculo.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, patente="AB123CD",
            descripcion="Furgón", capacidad_kg=Decimal('5000.00'))
        self.juan = Personal.objects.create(
            empresa=self.empresa, nombre="Juan", es_repartidor=True, es_cobrador=True)
        self.vendedor = Personal.objects.create(
            empresa=self.empresa, nombre="Romina", es_vendedor=True)

        rubro = Rubro.objects.create(empresa=self.empresa, detalle="LACTEOS",
                                     cta_ventas=cta_vta)
        self.producto = Producto.objects.create(
            empresa=self.empresa, detalle="Yogur x 900", precio_total=Decimal('1000.00'),
            peso_unitario_kg=Decimal('2.000'), rubro=rubro)
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

    def facturar(self, cliente, cantidad, condic, fecha=None):
        """Emite un comprobante del `condic` pedido y devuelve la Venta."""
        pedido = guardar_pedido(
            empresa_id=self.empresa.id, sucursal_id=self.sucursal.id,
            cliente=cliente, usuario=self.usuario, condic_destino=condic,
            items=[{'producto_id': self.producto.id, 'cantidad': cantidad,
                    'precio_unitario': 1000.0, 'total': 1000.0 * cantidad,
                    'descuento': 0}])
        facturar_pedido(pedido, self.usuario)
        pedido.refresh_from_db()
        venta = pedido.venta
        if fecha:
            # Envejecer el comprobante sin volver a contabilizarlo: es sólo el orden FIFO.
            type(venta).objects.filter(pk=venta.pk).update(fecha=fecha)
            venta.refresh_from_db()
        return pedido, venta

    def reparto_cerrado(self, *pedidos):
        reparto = crear_reparto(
            self.empresa.id, self.sucursal.id, self.usuario,
            vehiculo=self.vehiculo, zona=self.zona, responsables=[self.juan])
        if pedidos:
            agregar_paradas(reparto, list(pedidos))
        cerrar_reparto(reparto, self.usuario)
        reparto.refresh_from_db()
        return reparto


class SegmentacionPorMedioDePagoTestCase(BaseCobranzaTestCase):
    """Regla 1: lo trazable va contra `condic = 1`. Regla 2: el efectivo ataca los PRE."""

    def test_lo_trazable_solo_cancela_comprobantes_fiscales(self):
        """Un movimiento que el banco registra no puede cancelar lo que no existe para el fisco."""
        cliente = self.crear_cliente()
        _, pre = self.facturar(cliente, 10, condic=2, fecha="2026-01-10")
        _, factura = self.facturar(cliente, 10, condic=1, fecha="2026-02-10")

        plan = planificar(cliente, self.empresa.id,
                          [{'categoria': 'TRA', 'importe': Decimal('6000.00')}])

        self.assertEqual(plan['aplicado_presupuestado'], Decimal('0.00'))
        self.assertEqual(plan['aplicado_real'], Decimal('6000.00'))
        self.assertEqual([a['venta'].pk for a in plan['aplicaciones'][1]], [factura.pk])

    def test_el_efectivo_cancela_primero_el_pre_mas_viejo(self):
        """Es la única plata que puede pagar lo que no está documentado."""
        cliente = self.crear_cliente()
        _, pre_viejo = self.facturar(cliente, 3, condic=2, fecha="2026-01-05")
        _, pre_nuevo = self.facturar(cliente, 3, condic=2, fecha="2026-02-05")
        _, factura = self.facturar(cliente, 10, condic=1, fecha="2026-01-01")

        plan = planificar(cliente, self.empresa.id,
                          [{'categoria': 'EFE', 'importe': Decimal('4000.00')}])

        aplicados = [(a['venta'].pk, a['importe']) for a in plan['aplicaciones'][2]]
        self.assertEqual(aplicados, [(pre_viejo.pk, Decimal('3000.00')),
                                     (pre_nuevo.pk, Decimal('1000.00'))])
        # Ni un peso fue a la factura, que es más vieja que los dos PRE.
        self.assertEqual(plan['aplicaciones'][1], [])

    def test_agotados_los_pre_el_efectivo_sigue_con_las_facturas(self):
        cliente = self.crear_cliente()
        _, pre = self.facturar(cliente, 2, condic=2, fecha="2026-01-05")
        _, factura = self.facturar(cliente, 10, condic=1, fecha="2026-01-10")

        plan = planificar(cliente, self.empresa.id,
                          [{'categoria': 'EFE', 'importe': Decimal('5000.00')}])

        self.assertEqual(plan['aplicado_presupuestado'], Decimal('2000.00'))
        self.assertEqual(plan['aplicado_real'], Decimal('3000.00'))

    def test_lo_que_no_es_trazable_se_trata_como_efectivo(self):
        """Si no deja rastro externo verificable, no puede respaldar una operación fiscal."""
        cliente = self.crear_cliente()
        _, pre = self.facturar(cliente, 5, condic=2, fecha="2026-01-05")

        plan = planificar(cliente, self.empresa.id,
                          [{'categoria': 'OTR', 'importe': Decimal('5000.00')}])
        self.assertEqual(plan['efectivo'], Decimal('5000.00'))
        self.assertEqual(plan['aplicado_presupuestado'], Decimal('5000.00'))

    def test_el_fifo_ordena_por_fecha_y_la_venta_del_reparto_se_cancela_al_final(self):
        cliente = self.crear_cliente()
        _, vieja = self.facturar(cliente, 5, condic=1, fecha="2026-01-01")
        _, del_reparto = self.facturar(cliente, 5, condic=1, fecha="2026-06-01")

        plan = planificar(cliente, self.empresa.id,
                          [{'categoria': 'TRA', 'importe': Decimal('6000.00')}])
        aplicados = [(a['venta'].pk, a['importe']) for a in plan['aplicaciones'][1]]
        self.assertEqual(aplicados, [(vieja.pk, Decimal('5000.00')),
                                     (del_reparto.pk, Decimal('1000.00'))])

    def test_el_excedente_queda_en_el_circuito_fiscal(self):
        """Es donde se puede justificar de dónde salió la plata."""
        cliente = self.crear_cliente()
        self.facturar(cliente, 2, condic=1, fecha="2026-01-01")

        plan = planificar(cliente, self.empresa.id,
                          [{'categoria': 'TRA', 'importe': Decimal('5000.00')}])
        self.assertEqual(plan['aplicado_real'], Decimal('2000.00'))
        self.assertEqual(plan['excedente'], Decimal('3000.00'))

    def test_los_dos_tramos_no_aplican_dos_veces_sobre_el_mismo_comprobante(self):
        cliente = self.crear_cliente()
        _, factura = self.facturar(cliente, 10, condic=1, fecha="2026-01-01")

        plan = planificar(cliente, self.empresa.id, [
            {'categoria': 'CHQ', 'importe': Decimal('6000.00')},
            {'categoria': 'EFE', 'importe': Decimal('6000.00')},
        ])
        total_aplicado = sum(a['importe'] for a in plan['aplicaciones'][1])
        self.assertEqual(total_aplicado, Decimal('10000.00'))
        self.assertEqual(plan['excedente'], Decimal('2000.00'))


class RegistroDeLaCobranzaTestCase(BaseCobranzaTestCase):
    def test_una_cobranza_mixta_genera_dos_recibos_uno_por_condic(self):
        """Real y Presupuestado no se mezclan: cada uno alimenta un circuito distinto."""
        cliente = self.crear_cliente()
        _, pre = self.facturar(cliente, 4, condic=2, fecha="2026-01-05")
        pedido, factura = self.facturar(cliente, 10, condic=1, fecha="2026-02-05")
        reparto = self.reparto_cerrado(pedido)

        recibos = registrar(reparto, cliente, [
            {'categoria': 'EFE', 'importe': Decimal('6000.00')},
            {'categoria': 'CHQ', 'importe': Decimal('4000.00')},
        ], self.usuario, parada=reparto.paradas.get(), cobrador=self.juan)

        self.assertEqual(len(recibos), 2)
        self.assertEqual({r.condic for r in recibos}, {1, 2})
        # El recibo Presupuestado lleva EXACTAMENTE el efectivo que canceló el PRE.
        pre_recibo = next(r for r in recibos if r.condic == 2)
        self.assertEqual(Decimal(str(pre_recibo.total)), Decimal('4000.00'))
        # Todo lo demás va al Real: el cheque, más el efectivo que no fue al PRE.
        real = next(r for r in recibos if r.condic == 1)
        self.assertEqual(Decimal(str(real.total)), Decimal('6000.00'))

    def test_los_recibos_suman_exactamente_lo_que_entro(self):
        """Si no, la caja no cuadra."""
        cliente = self.crear_cliente()
        _, pre = self.facturar(cliente, 3, condic=2, fecha="2026-01-05")
        pedido, factura = self.facturar(cliente, 10, condic=1, fecha="2026-02-05")
        reparto = self.reparto_cerrado(pedido)

        recibos = registrar(reparto, cliente, [
            {'categoria': 'EFE', 'importe': Decimal('7000.00')},
            {'categoria': 'TRA', 'importe': Decimal('2500.00')},
        ], self.usuario, parada=reparto.paradas.get())

        self.assertEqual(sum(Decimal(str(r.total)) for r in recibos),
                         Decimal('9500.00'))

    def test_los_detalles_del_movimiento_cuadran_con_el_total_del_recibo(self):
        """El asiento se arma leyendo los detalles: si no cuadran, no cierra."""
        cliente = self.crear_cliente()
        _, pre = self.facturar(cliente, 3, condic=2, fecha="2026-01-05")
        pedido, factura = self.facturar(cliente, 10, condic=1, fecha="2026-02-05")
        reparto = self.reparto_cerrado(pedido)

        recibos = registrar(reparto, cliente, [
            {'categoria': 'EFE', 'importe': Decimal('7000.00')},
            {'categoria': 'TRA', 'importe': Decimal('2500.00')},
        ], self.usuario, parada=reparto.paradas.get())

        for recibo in recibos:
            movimiento = recibo.movimientocaja_set.get()
            suma = sum(Decimal(str(d.importe)) for d in movimiento.detalles.all())
            self.assertEqual(suma, Decimal(str(recibo.total)),
                             f"El recibo condic {recibo.condic} no cuadra con sus detalles.")

    def test_la_cobranza_baja_el_saldo_de_los_comprobantes(self):
        cliente = self.crear_cliente()
        pedido, factura = self.facturar(cliente, 10, condic=1, fecha="2026-02-05")
        reparto = self.reparto_cerrado(pedido)

        registrar(reparto, cliente, [{'categoria': 'TRA', 'importe': Decimal('4000.00')}],
                  self.usuario, parada=reparto.paradas.get())

        factura.refresh_from_db()
        self.assertEqual(Decimal(str(factura.saldo)), Decimal('6000.00'))

    def test_cada_recibo_deja_su_satelite_con_reparto_parada_y_cobrador(self):
        cliente = self.crear_cliente()
        pedido, factura = self.facturar(cliente, 5, condic=1, fecha="2026-02-05")
        reparto = self.reparto_cerrado(pedido)
        parada = reparto.paradas.get()

        recibos = registrar(reparto, cliente,
                            [{'categoria': 'EFE', 'importe': Decimal('5000.00')}],
                            self.usuario, parada=parada, cobrador=self.juan)

        satelite = CobranzaDistribucion.objects.get(recibo=recibos[0])
        self.assertEqual(satelite.reparto_id, reparto.id)
        self.assertEqual(satelite.parada_id, parada.id)
        self.assertEqual(satelite.cobrador_id, self.juan.id)

    def test_el_recibo_entra_en_la_caja_recaudadora_del_reparto(self):
        cliente = self.crear_cliente()
        pedido, factura = self.facturar(cliente, 5, condic=1, fecha="2026-02-05")
        reparto = self.reparto_cerrado(pedido)

        recibos = registrar(reparto, cliente,
                            [{'categoria': 'EFE', 'importe': Decimal('5000.00')}],
                            self.usuario, parada=reparto.paradas.get())

        self.assertEqual(recibos[0].sesion_caja_id, reparto.sesion_caja_id)
        self.assertEqual(reparto.sesion_caja.caja.tipo, 'R')

    def test_no_se_cobra_sobre_un_reparto_que_todavia_no_salio(self):
        cliente = self.crear_cliente()
        pedido, factura = self.facturar(cliente, 5, condic=1, fecha="2026-02-05")
        reparto = crear_reparto(self.empresa.id, self.sucursal.id, self.usuario)
        agregar_paradas(reparto, [pedido])

        with self.assertRaises(ValueError):
            registrar(reparto, cliente,
                      [{'categoria': 'EFE', 'importe': Decimal('5000.00')}], self.usuario)

    def test_una_cobranza_sin_importe_se_rechaza(self):
        cliente = self.crear_cliente()
        pedido, factura = self.facturar(cliente, 5, condic=1, fecha="2026-02-05")
        reparto = self.reparto_cerrado(pedido)

        with self.assertRaises(ValueError):
            registrar(reparto, cliente, [], self.usuario)


class LasDosLentesTestCase(BaseCobranzaTestCase):
    def test_el_saldo_fiscal_ignora_los_pre(self):
        cliente = self.crear_cliente()
        self.facturar(cliente, 4, condic=2, fecha="2026-01-05")
        self.facturar(cliente, 10, condic=1, fecha="2026-02-05")

        self.assertEqual(saldo_fiscal(cliente, self.empresa.id), Decimal('10000.00'))

    def test_el_saldo_operativo_suma_los_dos_circuitos(self):
        """Al cliente hay que cobrarle todo lo que debe, tenga o no respaldo fiscal."""
        cliente = self.crear_cliente()
        self.facturar(cliente, 4, condic=2, fecha="2026-01-05")
        self.facturar(cliente, 10, condic=1, fecha="2026-02-05")

        self.assertEqual(saldo_operativo(cliente, self.empresa.id), Decimal('14000.00'))

    def test_la_cobranza_baja_cada_lente_por_su_lado(self):
        cliente = self.crear_cliente()
        _, pre = self.facturar(cliente, 4, condic=2, fecha="2026-01-05")
        pedido, factura = self.facturar(cliente, 10, condic=1, fecha="2026-02-05")
        reparto = self.reparto_cerrado(pedido)

        registrar(reparto, cliente, [{'categoria': 'EFE', 'importe': Decimal('4000.00')}],
                  self.usuario, parada=reparto.paradas.get())

        # El efectivo se comió el PRE entero: el fiscal no se movió.
        self.assertEqual(saldo_fiscal(cliente, self.empresa.id), Decimal('10000.00'))
        self.assertEqual(saldo_operativo(cliente, self.empresa.id), Decimal('10000.00'))


class CajaRecaudadoraTestCase(BaseCobranzaTestCase):
    def test_la_caja_recaudadora_es_de_tipo_propio(self):
        """Se abre por reparto, no por turno de cajero: es otra regla de negocio."""
        caja = caja_recaudadora(self.empresa.id, self.sucursal.id)
        self.assertEqual(caja.tipo, 'R')
        # Una sola por sucursal: lo que separa un reparto de otro es la SESIÓN.
        otra = caja_recaudadora(self.empresa.id, self.sucursal.id)
        self.assertEqual(caja.id, otra.id)
        self.assertEqual(Caja.objects.filter(empresa=self.empresa, tipo='R').count(), 1)

    def test_cerrar_el_reparto_abre_su_caja(self):
        cliente = self.crear_cliente()
        pedido, factura = self.facturar(cliente, 5, condic=1, fecha="2026-02-05")
        reparto = self.reparto_cerrado(pedido)

        self.assertIsNotNone(reparto.sesion_caja_id)
        self.assertEqual(reparto.sesion_caja.estado, 'A')
        self.assertEqual(reparto.sesion_caja.saldo_inicial, Decimal('0.00'))

    def test_abrir_la_caja_es_idempotente(self):
        cliente = self.crear_cliente()
        pedido, factura = self.facturar(cliente, 5, condic=1, fecha="2026-02-05")
        reparto = self.reparto_cerrado(pedido)

        sesion = abrir_caja_del_reparto(reparto, self.usuario)
        self.assertEqual(sesion.id, reparto.sesion_caja_id)

    def test_dos_repartos_tienen_sesiones_distintas_sobre_la_misma_caja(self):
        cliente_a = self.crear_cliente("Cliente A")
        cliente_b = self.crear_cliente("Cliente B")
        pedido_a, _ = self.facturar(cliente_a, 5, condic=1, fecha="2026-02-05")
        pedido_b, _ = self.facturar(cliente_b, 5, condic=1, fecha="2026-02-05")

        primero = self.reparto_cerrado(pedido_a)
        segundo = self.reparto_cerrado(pedido_b)
        self.assertNotEqual(primero.sesion_caja_id, segundo.sesion_caja_id)
        self.assertEqual(primero.sesion_caja.caja_id, segundo.sesion_caja.caja_id)


class RendicionTestCase(BaseCobranzaTestCase):
    def _reparto_con_cobranza(self, efectivo='5000.00', trazable=None):
        cliente = self.crear_cliente()
        pedido, factura = self.facturar(cliente, 20, condic=1, fecha="2026-02-05")
        reparto = self.reparto_cerrado(pedido)
        valores = [{'categoria': 'EFE', 'importe': Decimal(efectivo)}]
        if trazable:
            valores.append({'categoria': 'TRA', 'importe': Decimal(trazable)})
        registrar(reparto, cliente, valores, self.usuario,
                  parada=reparto.paradas.get(), cobrador=self.juan)
        return reparto

    def test_el_resumen_confronta_esperado_cobrado_y_rendido(self):
        reparto = self._reparto_con_cobranza(efectivo='5000.00', trazable='3000.00')
        datos = resumen(reparto)

        self.assertEqual(datos['cobrado'], Decimal('8000.00'))
        self.assertEqual(datos['efectivo_cobrado'], Decimal('5000.00'))
        self.assertEqual(datos['declarado'], Decimal('0.00'))
        self.assertEqual(datos['pendiente_de_rendir'], Decimal('5000.00'))

    def test_solo_el_efectivo_se_rinde_en_mano(self):
        """La transferencia ya está en el banco: no la trae el repartidor en el bolsillo."""
        reparto = self._reparto_con_cobranza(efectivo='5000.00', trazable='3000.00')
        datos = resumen(reparto)
        self.assertEqual(datos['cobrado'] - datos['efectivo_cobrado'], Decimal('3000.00'))

    def test_rendir_deja_el_retiro_en_transito(self):
        """El que declara no es el mismo que cuenta: el paso 2 lo hace el tesorero."""
        reparto = self._reparto_con_cobranza()
        retiro = rendir(reparto, self.usuario, efectivo_pesos=Decimal('5000.00'))

        self.assertEqual(retiro.estado, 'T')
        self.assertEqual(retiro.efectivo_pesos, Decimal('5000.00'))
        self.assertEqual(retiro.sesion_id, reparto.sesion_caja_id)

    def test_rendir_marca_el_reparto_y_cierra_la_caja(self):
        reparto = self._reparto_con_cobranza()
        rendir(reparto, self.usuario, efectivo_pesos=Decimal('5000.00'))

        reparto.refresh_from_db()
        self.assertEqual(reparto.estado, Reparto.RENDIDO)
        self.assertEqual(reparto.sesion_caja.estado, 'C')

    def test_la_rendicion_dice_de_que_reparto_es_la_plata(self):
        """La sesión de caja no puede decirlo: su usuario es un `User` y el repartidor puede no serlo."""
        reparto = self._reparto_con_cobranza()
        retiro = rendir(reparto, self.usuario, efectivo_pesos=Decimal('5000.00'))

        vinculo = RendicionReparto.objects.get(retiro=retiro)
        self.assertEqual(vinculo.reparto_id, reparto.id)
        self.assertEqual(vinculo.esperado, Decimal('5000.00'))

    def test_no_se_rinde_dos_veces_el_mismo_reparto(self):
        reparto = self._reparto_con_cobranza()
        rendir(reparto, self.usuario, efectivo_pesos=Decimal('5000.00'))
        reparto.refresh_from_db()

        with self.assertRaises(ValueError):
            rendir(reparto, self.usuario, efectivo_pesos=Decimal('1000.00'))

    def test_no_se_rinde_un_importe_negativo(self):
        reparto = self._reparto_con_cobranza()
        with self.assertRaises(ValueError):
            rendir(reparto, self.usuario, efectivo_pesos=Decimal('-100.00'))

    def test_rendida_la_caja_ya_no_acepta_cobranzas(self):
        reparto = self._reparto_con_cobranza()
        rendir(reparto, self.usuario, efectivo_pesos=Decimal('5000.00'))
        reparto.refresh_from_db()

        otro = self.crear_cliente("Cliente Tarde")
        self.facturar(otro, 3, condic=1, fecha="2026-02-06")
        with self.assertRaises(ValueError):
            registrar(reparto, otro,
                      [{'categoria': 'EFE', 'importe': Decimal('1000.00')}], self.usuario)


class SaldosPorVendedorTestCase(BaseCobranzaTestCase):
    def test_el_listado_agrupa_por_vendedor(self):
        """El vendedor es el responsable directo del saldo de su cartera."""
        cliente = self.crear_cliente("Cliente Uno")
        CarteraVendedor.objects.create(
            empresa=self.empresa, vendedor=self.vendedor, cliente=cliente)
        self.facturar(cliente, 10, condic=1, fecha="2026-02-05")

        datos = listado(self.empresa.id, hoy=__import__('datetime').date(2026, 3, 5))
        self.assertEqual(len(datos['grupos']), 1)
        self.assertEqual(datos['grupos'][0]['vendedor'].id, self.vendedor.id)
        self.assertEqual(datos['total'], Decimal('10000.00'))

    def test_un_cliente_sin_vendedor_no_desaparece(self):
        """Un saldo sin responsable es justamente lo que hay que ver."""
        cliente = self.crear_cliente("Huerfano")
        self.facturar(cliente, 5, condic=1, fecha="2026-02-05")

        datos = listado(self.empresa.id, hoy=__import__('datetime').date(2026, 3, 5))
        self.assertEqual(len(datos['grupos']), 1)
        self.assertIsNone(datos['grupos'][0]['vendedor'])

    def test_marca_los_comprobantes_que_solo_se_cobran_en_efectivo(self):
        cliente = self.crear_cliente()
        self.facturar(cliente, 4, condic=2, fecha="2026-01-05")
        self.facturar(cliente, 10, condic=1, fecha="2026-02-05")

        datos = listado(self.empresa.id, hoy=__import__('datetime').date(2026, 3, 5))
        ficha = datos['grupos'][0]['clientes'][0]
        marcas = {c['venta'].condic: c['solo_efectivo'] for c in ficha['comprobantes']}
        self.assertTrue(marcas[2])
        self.assertFalse(marcas[1])

    def test_la_antiguedad_cae_en_su_tramo(self):
        cliente = self.crear_cliente()
        self.facturar(cliente, 1, condic=1, fecha="2026-03-01")   # 4 días
        self.facturar(cliente, 2, condic=1, fecha="2025-11-01")   # +90 días

        datos = listado(self.empresa.id, hoy=__import__('datetime').date(2026, 3, 5))
        tramos = dict(datos['tramos'])
        self.assertEqual(tramos['0-30'], Decimal('1000.00'))
        self.assertEqual(tramos['+90'], Decimal('2000.00'))

    def test_el_filtro_de_condicion_acota_el_reporte(self):
        """Todo reporte con importes ofrece el filtro de condición (regla del proyecto)."""
        cliente = self.crear_cliente()
        self.facturar(cliente, 4, condic=2, fecha="2026-01-05")
        self.facturar(cliente, 10, condic=1, fecha="2026-02-05")

        solo_fiscal = listado(self.empresa.id, condics=(1,),
                              hoy=__import__('datetime').date(2026, 3, 5))
        self.assertEqual(solo_fiscal['total'], Decimal('10000.00'))

    def test_el_disponible_sale_del_limite_menos_el_saldo_operativo(self):
        cliente = self.crear_cliente(limite='12000.00')
        self.facturar(cliente, 4, condic=2, fecha="2026-01-05")
        self.facturar(cliente, 10, condic=1, fecha="2026-02-05")

        datos = listado(self.empresa.id, hoy=__import__('datetime').date(2026, 3, 5))
        ficha = datos['grupos'][0]['clientes'][0]
        self.assertEqual(ficha['saldo'], Decimal('14000.00'))
        self.assertEqual(ficha['disponible'], Decimal('-2000.00'))


class VistasDeCobranzaTestCase(BaseCobranzaTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.usuario)
        sesion = self.client.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion['ejercicio_id'] = self.ejercicio.id
        sesion.save()

    def _reparto(self):
        cliente = self.crear_cliente()
        pedido, factura = self.facturar(cliente, 10, condic=1, fecha="2026-02-05")
        return self.reparto_cerrado(pedido), cliente

    def test_la_pantalla_de_cobranza_lista_las_paradas(self):
        reparto, _ = self._reparto()
        respuesta = self.client.get(reverse('distribucion_cobranza', args=[reparto.id]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "CLIENTE UNO")

    def test_previsualizar_muestra_la_imputacion_antes_de_grabar(self):
        reparto, _ = self._reparto()
        parada = reparto.paradas.get()
        respuesta = self.client.post(
            reverse('distribucion_cobranza', args=[reparto.id]),
            {'accion': 'previsualizar', 'parada': parada.id, 'valor_efe': '4.000,00'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['plan']['aplicado_real'], Decimal('4000.00'))
        # Previsualizar no graba nada.
        self.assertEqual(Recibo.objects.count(), 0)

    def test_registrar_desde_la_pantalla_crea_el_recibo(self):
        reparto, _ = self._reparto()
        parada = reparto.paradas.get()
        respuesta = self.client.post(
            reverse('distribucion_cobranza', args=[reparto.id]),
            {'accion': 'registrar', 'parada': parada.id, 'valor_efe': '4.000,00',
             'cobrador': self.juan.id})

        self.assertRedirects(
            respuesta, reverse('distribucion_cobranza', args=[reparto.id]))
        recibo = Recibo.objects.get()
        self.assertEqual(Decimal(str(recibo.total)), Decimal('4000.00'))
        self.assertEqual(ReciboAplicacion.objects.filter(recibo=recibo).count(), 1)

    def test_el_reparto_de_otra_empresa_no_se_ve(self):
        otra = Empresa.objects.create(nombre="Ajena", cuit="30222222229")
        sucursal = Sucursal.objects.create(empresa=otra, nombre="Única", punto=1)
        reparto = crear_reparto(otra.id, sucursal.id, self.usuario)

        respuesta = self.client.get(reverse('distribucion_cobranza', args=[reparto.id]))
        self.assertEqual(respuesta.status_code, 404)

    def test_la_pantalla_de_rendicion_muestra_el_cuadro(self):
        reparto, _ = self._reparto()
        respuesta = self.client.get(reverse('distribucion_rendicion', args=[reparto.id]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Esperado")

    def test_rendir_desde_la_pantalla(self):
        reparto, cliente = self._reparto()
        registrar(reparto, cliente, [{'categoria': 'EFE', 'importe': Decimal('5000.00')}],
                  self.usuario, parada=reparto.paradas.get())

        self.client.post(reverse('distribucion_rendicion', args=[reparto.id]),
                         {'efectivo_pesos': '5.000,00'})
        reparto.refresh_from_db()
        self.assertEqual(reparto.estado, Reparto.RENDIDO)
        self.assertEqual(RetiroCaja.objects.filter(sesion=reparto.sesion_caja).count(), 1)

    def test_el_listado_de_saldos_responde(self):
        cliente = self.crear_cliente()
        CarteraVendedor.objects.create(
            empresa=self.empresa, vendedor=self.vendedor, cliente=cliente)
        self.facturar(cliente, 10, condic=1, fecha="2026-02-05")

        respuesta = self.client.get(reverse('distribucion_saldos'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "ROMINA")
        self.assertContains(respuesta, "CLIENTE UNO")
