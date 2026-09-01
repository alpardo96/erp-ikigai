"""La caja de distribución tiene cuenta contable propia (Plan 076 §B, `cta_caja_reparto`).

Definición del usuario: *"Agreguemos un nuevo parámetro `cta_caja_reparto` porque incluso
ambos responsables son totalmente distintos."*

El efectivo que está en la calle es de otro responsable que el de la caja mostrador —el
repartidor y el administrativo de reparto, frente al cajero de turno—, así que el balance
tiene que poder mostrarlo por separado.

CÓMO LLEGA LA PLATA A ESA CUENTA: por la regla del Plan 077 §E — para el efectivo, la cuenta
la resuelve LA CAJA donde entró. El mismo "Efectivo" vale para todas, y sólo la caja sabe de
quién es esa plata.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from contable.models import Asiento, AsientoLinea, Cuenta, Ejercicio, ParametrosContables
from verticalidades.distribucion.models import DomicilioEntrega, Personal, Vehiculo, ZonaReparto
from contable.services.contabilizacion import cuenta_efectivo_de_caja
from verticalidades.distribucion.services.caja_reparto import (cuenta_de_reparto, medio_pago_efectivo,
                                                recibir, rendir)
from verticalidades.distribucion.services.cobranza_fifo import registrar
from verticalidades.distribucion.services.facturacion import facturar_pedido
from verticalidades.distribucion.services.pedidos import guardar_pedido
from verticalidades.distribucion.services.reparto import agregar_paradas, cerrar_reparto, crear_reparto
from empresas.models import Empresa, PuntoVenta, Sucursal
from facturacion.models import ClienteProveedor,  TipoComprobante
from verticalidades.distribucion.models import ExtensionDistribuidora
from productos.models import Producto, Rubro, StockSucursal
from tesoreria.models import MedioPago


class BaseCuentaRepartoTestCase(TestCase):
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

        # Las tres cuentas SEPARADAS: es lo que estas pruebas verifican.
        self.cta_mostrador = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.1", cuenta="CAJA MOSTRADOR", imputable=1)
        self.cta_reparto = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.2", cuenta="CAJA DE REPARTO", imputable=1)
        self.cta_central = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.4", cuenta="CAJA CENTRAL", imputable=1)
        self.cta_dif = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.9", cuenta="DIFERENCIAS DE CAJA", imputable=1)
        cta_cli = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.3", cuenta="DEUDORES", imputable=1)
        cta_vta = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="4.1.1", cuenta="VENTAS", imputable=1)
        cta_iva = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="2.1.1", cuenta="IVA DEBITO", imputable=1)

        self.parametros = ParametrosContables.objects.create(
            empresa=self.empresa, cta_clientes_default=cta_cli, cta_ventas=cta_vta,
            cta_iva_debito=cta_iva, cta_caja_central=self.cta_central,
            cta_caja_mostrador=self.cta_mostrador, cta_caja_reparto=self.cta_reparto,
            cta_diferencia_caja=self.cta_dif, metodo_contabilizacion_ventas=1)

        # El efectivo GENÉRICO apunta a la mostrador: es el de siempre.
        MedioPago.objects.create(
            empresa=self.empresa, codigo='EFE-ARS', nombre="Efectivo",
            categoria='EFE', cuenta_contable=self.cta_mostrador)

        self.zona = ZonaReparto.objects.create(
            empresa=self.empresa, nombre="San Cayetano", orden=1)
        self.vehiculo = Vehiculo.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, patente="AB123CD",
            descripcion="Furgón", capacidad_kg=Decimal('5000.00'))
        self.juan = Personal.objects.create(
            empresa=self.empresa, nombre="Juan", es_repartidor=True)
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

    def reparto_con_cobranza(self, efectivo='5000.00'):
        cliente = self.crear_cliente()
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

        recibos = registrar(reparto, cliente,
                            [{'categoria': 'EFE', 'importe': Decimal(efectivo)}],
                            self.usuario, parada=reparto.paradas.get())
        return reparto, recibos[0]


class ElParametroTestCase(BaseCuentaRepartoTestCase):
    def test_devuelve_la_cuenta_configurada(self):
        self.assertEqual(cuenta_de_reparto(self.empresa.id).id, self.cta_reparto.id)

    def test_sin_configurar_falla_con_un_mensaje_claro(self):
        """Sin fallback a la mostrador: mezclarlas en silencio es justo lo que se evita."""
        self.parametros.cta_caja_reparto = None
        self.parametros.save(update_fields=['cta_caja_reparto'])

        with self.assertRaises(ValueError) as caso:
            cuenta_de_reparto(self.empresa.id)
        self.assertIn("Caja de Reparto", str(caso.exception))


class LaCuentaLaDefineLaCajaTestCase(BaseCuentaRepartoTestCase):
    """Plan 077 §E: para el efectivo, la cuenta sale de la CAJA, no del medio de pago.

    El mismo "Efectivo" vale para todas las cajas; sólo la caja sabe de quién es esa plata.
    """

    def _caja(self, tipo):
        from tesoreria.models import Caja
        return Caja.objects.create(empresa=self.empresa, sucursal=self.sucursal,
                                   nombre=f"Caja {tipo}", tipo=tipo)

    def test_la_mostrador_resuelve_su_propia_cuenta(self):
        self.assertEqual(
            cuenta_efectivo_de_caja(self._caja('M'), self.parametros).id,
            self.cta_mostrador.id)

    def test_las_de_distribucion_resuelven_la_cuenta_de_reparto(self):
        for tipo in ('R', 'D'):
            self.assertEqual(
                cuenta_efectivo_de_caja(self._caja(tipo), self.parametros).id,
                self.cta_reparto.id,
                f"La caja '{tipo}' no resolvió la cuenta de reparto.")

    def test_la_de_tesoreria_resuelve_la_caja_central(self):
        self.assertEqual(
            cuenta_efectivo_de_caja(self._caja('T'), self.parametros).id,
            self.cta_central.id)

    def test_sin_el_parametro_de_reparto_falla(self):
        """Sustituirlo en silencio mezclaría lo que ese parámetro vino a separar."""
        from django.core.exceptions import ValidationError

        self.parametros.cta_caja_reparto = None
        with self.assertRaises(ValidationError):
            cuenta_efectivo_de_caja(self._caja('R'), self.parametros)

    def test_sin_el_parametro_de_mostrador_deja_seguir_la_cadena(self):
        """Es el estado heredado de las empresas que nunca lo cargaron: no se les rompe nada."""
        self.parametros.cta_caja_mostrador = None
        self.assertIsNone(cuenta_efectivo_de_caja(self._caja('M'), self.parametros))

    def test_el_medio_de_pago_del_reparto_es_el_generico(self):
        """Ya no hace falta uno propio: la caja dice la cuenta (Plan 077 §E.4)."""
        medio = medio_pago_efectivo(self.empresa.id)
        self.assertEqual(medio.codigo, 'EFE-ARS')
        self.assertFalse(
            MedioPago.objects.filter(empresa=self.empresa, codigo='EFE-REP').exists())


class ElAsientoDeLaCobranzaTestCase(BaseCuentaRepartoTestCase):
    def test_la_cobranza_del_reparto_debita_la_caja_de_reparto(self):
        """Es la prueba de fondo: sin el medio propio, esto caería en la mostrador."""
        _, recibo = self.reparto_con_cobranza('5000.00')

        asiento = Asiento.objects.get(pk=recibo.asiento_id)
        lineas_debe = AsientoLinea.objects.filter(asiento=asiento, debe__gt=0)
        cuentas = {l.cuenta_id for l in lineas_debe}
        self.assertIn(self.cta_reparto.id, cuentas)
        self.assertNotIn(self.cta_mostrador.id, cuentas)

    def test_la_cobranza_del_vendedor_tambien(self):
        cliente = self.crear_cliente("Cliente Esquivo")
        pedido = guardar_pedido(
            empresa_id=self.empresa.id, sucursal_id=self.sucursal.id,
            cliente=cliente, usuario=self.usuario, condic_destino=1,
            items=[{'producto_id': self.producto.id, 'cantidad': 10,
                    'precio_unitario': 1000.0, 'total': 10000.0, 'descuento': 0}])
        facturar_pedido(pedido, self.usuario)

        recibos = registrar(None, cliente,
                            [{'categoria': 'EFE', 'importe': Decimal('3000.00')}],
                            self.usuario, cobrador=self.romina,
                            sucursal_id=self.sucursal.id)

        asiento = Asiento.objects.get(pk=recibos[0].asiento_id)
        cuentas = {l.cuenta_id for l in AsientoLinea.objects.filter(asiento=asiento, debe__gt=0)}
        self.assertIn(self.cta_reparto.id, cuentas)


class ElAsientoDeLaRendicionTestCase(BaseCuentaRepartoTestCase):
    def test_la_diferencia_de_arqueo_ajusta_la_caja_de_reparto(self):
        """La plata contada está en la Tesorería de Reparto, no en Tesorería."""
        reparto, _ = self.reparto_con_cobranza('5000.00')
        retiro = rendir(reparto, self.usuario, efectivo_pesos=Decimal('5000.00'))

        recibir(retiro, self.usuario, contado_pesos=Decimal('4800.00'))

        retiro.refresh_from_db()
        asiento = Asiento.objects.get(pk=retiro.asiento_diferencia_id)
        cuentas = {l.cuenta_id for l in AsientoLinea.objects.filter(asiento=asiento)}
        self.assertEqual(cuentas, {self.cta_dif.id, self.cta_reparto.id})
        self.assertNotIn(self.cta_central.id, cuentas)

    def test_el_faltante_acredita_la_caja_de_reparto(self):
        reparto, _ = self.reparto_con_cobranza('5000.00')
        retiro = rendir(reparto, self.usuario, efectivo_pesos=Decimal('5000.00'))
        recibir(retiro, self.usuario, contado_pesos=Decimal('4800.00'))

        retiro.refresh_from_db()
        linea = AsientoLinea.objects.get(
            asiento_id=retiro.asiento_diferencia_id, cuenta=self.cta_reparto)
        self.assertEqual(linea.haber, Decimal('200.00'))
        self.assertEqual(linea.debe, Decimal('0.00'))


class ElTrasladoAtesoreriaTestCase(BaseCuentaRepartoTestCase):
    """El segundo tramo: la Tesorería de Reparto rinde a Caja Tesorería."""

    def test_el_traslado_de_una_caja_de_distribucion_acredita_su_cuenta(self):
        from tesoreria.models import Caja
        from tesoreria.views_htmx import cuenta_origen_de_caja

        caja = Caja.objects.create(empresa=self.empresa, sucursal=self.sucursal,
                                   nombre="Tesorería de Reparto", tipo='D')
        self.assertEqual(cuenta_origen_de_caja(caja, self.parametros).id,
                         self.cta_reparto.id)

    def test_el_traslado_de_la_mostrador_no_cambia(self):
        from tesoreria.models import Caja
        from tesoreria.views_htmx import cuenta_origen_de_caja

        caja = Caja.objects.create(empresa=self.empresa, sucursal=self.sucursal,
                                   nombre="Mostrador", tipo='M')
        self.assertEqual(cuenta_origen_de_caja(caja, self.parametros).id,
                         self.cta_mostrador.id)

    def test_sin_el_parametro_el_traslado_de_distribucion_falla(self):
        from tesoreria.models import Caja
        from tesoreria.views_htmx import cuenta_origen_de_caja

        self.parametros.cta_caja_reparto = None
        caja = Caja.objects.create(empresa=self.empresa, sucursal=self.sucursal,
                                   nombre="Tesorería de Reparto", tipo='D')
        with self.assertRaises(Exception):
            cuenta_origen_de_caja(caja, self.parametros)


class LaPlataEnLaCalleSeVeSeparadaTestCase(BaseCuentaRepartoTestCase):
    """El objetivo de todo el cambio, verificado de punta a punta."""

    def test_lo_cobrado_en_la_calle_no_toca_la_cuenta_de_la_mostrador(self):
        self.reparto_con_cobranza('5000.00')

        saldo_reparto = sum(
            (l.debe - l.haber for l in AsientoLinea.objects.filter(cuenta=self.cta_reparto)),
            Decimal('0.00'))
        saldo_mostrador = sum(
            (l.debe - l.haber for l in AsientoLinea.objects.filter(cuenta=self.cta_mostrador)),
            Decimal('0.00'))

        self.assertEqual(saldo_reparto, Decimal('5000.00'))
        self.assertEqual(saldo_mostrador, Decimal('0.00'))
