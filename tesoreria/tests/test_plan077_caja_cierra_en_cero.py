"""La caja mostrador cierra en cero, o en el fondo fijo (Plan 077 §E).

Definición del usuario: *"Caja mostrador descarga sobre las cuentas definidas por parámetro
—cobranzas por un lado y retiros / cierre de caja por el otro—, por lo que deberían quedar en
cero o lo que se defina como fondo fijo al final de cada cierre."*

ESTAS PRUEBAS VERIFICAN EL REQUERIMIENTO, NO LA IMPLEMENTACIÓN. Si mañana la cuenta se
resolviera de otra manera pero la caja siguiera cerrando en el fondo fijo, deberían seguir
pasando.

Lo que estaba roto: el efectivo tenía TRES destinos contables según por dónde entrara —la
venta de mostrador iba a `cta_caja`, el recibo a la cuenta del medio de pago, y el retiro
acreditaba `cta_caja_mostrador`—, así que la cuenta del mostrador sólo recibía haber y nunca
debe. No es que no cerrara en cero: se volvía cada vez más acreedora.
"""
import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from contable.models import AsientoLinea, Cuenta, Ejercicio, ParametrosContables
from empresas.models import Empresa, Sucursal
from facturacion.models import ClienteProveedor, TipoComprobante, Venta, VentaItem
from productos.models import Producto, Rubro
from tesoreria.models import Caja, CajaSesion, MedioPago, Recibo


class BaseCajaCierraTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nombre="Empresa Prueba", cuit="30111111118")
        # `id=1` a propósito: el cierre de mostrador rinde a la sucursal 1 por convención
        # heredada (`destino_id = 1` en `caja_cierre_procesar`). Es la casa central.
        self.sucursal = Sucursal.objects.create(
            id=1, empresa=self.empresa, nombre="Casa Central", punto=1)
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa, inicio="2026-01-01", cierre="2026-12-31")
        self.usuario = User.objects.create_user(username="cajero1", password="x")

        self.factura_b, _ = TipoComprobante.objects.get_or_create(
            codigo='006', defaults={'detalle': "Factura B", 'signo': 1})

        # LAS TRES CUENTAS SEPARADAS: es lo que hace visible el problema.
        self.cta_caja = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.1", cuenta="CAJA", imputable=1)
        self.cta_mostrador = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.2", cuenta="CAJA MOSTRADOR", imputable=1)
        self.cta_central = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.4", cuenta="CAJA CENTRAL", imputable=1)
        cta_cli = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.3", cuenta="DEUDORES", imputable=1)
        cta_vta = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="4.1.1", cuenta="VENTAS", imputable=1)
        cta_iva = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="2.1.1", cuenta="IVA DEBITO", imputable=1)

        ParametrosContables.objects.create(
            empresa=self.empresa, cta_clientes_default=cta_cli, cta_ventas=cta_vta,
            cta_iva_debito=cta_iva, cta_caja=self.cta_caja,
            cta_caja_mostrador=self.cta_mostrador, cta_caja_central=self.cta_central,
            metodo_contabilizacion_ventas=1)

        # El medio de efectivo apunta a la cuenta GENÉRICA, como en las empresas reales.
        # Antes del Plan 077 eso bastaba para que la cobranza no tocara la del mostrador.
        MedioPago.objects.create(
            empresa=self.empresa, codigo='EFE-ARS', nombre="Efectivo",
            categoria='EFE', cuenta_contable=self.cta_caja)

        self.caja = Caja.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, nombre="Mostrador", tipo='M')
        self.sesion = CajaSesion.objects.create(
            caja=self.caja, usuario=self.usuario, estado='A')

        rubro = Rubro.objects.create(empresa=self.empresa, detalle="GENERAL",
                                     cta_ventas=cta_vta)
        self.producto = Producto.objects.create(
            empresa=self.empresa, detalle="Servicio", precio_total=Decimal('1000.00'),
            rubro=rubro)

        self.cliente = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="Cliente Uno", tipo_entidad=1,
            domicilio="Belgrano 100", condicion_iva="CONSUMIDOR FINAL")

        self.client = Client()
        self.client.force_login(self.usuario)
        sesion = self.client.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion['ejercicio_id'] = self.ejercicio.id
        sesion.save()

    # ------------------------------------------------------------------ helpers
    def saldo(self, cuenta):
        """Saldo deudor de una cuenta: debe − haber sobre asientos vigentes."""
        return sum((l.debe - l.haber for l in
                    AsientoLinea.objects.filter(cuenta=cuenta, asiento__anulado=False)),
                   Decimal('0.00'))

    def crear_factura(self, total='10000.00', numero=1):
        venta = Venta.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, ejercicio=self.ejercicio,
            tipo=self.factura_b, punto=1, numero=numero, fecha="2026-02-01",
            periodo="202602", cliente=self.cliente,
            cliente_razon_social=self.cliente.razon_social,
            usuario=self.usuario, condic=1, estado=0)
        VentaItem.objects.create(
            venta=venta, producto=self.producto, concepto="Servicio", cantidad=Decimal('1'),
            precio_unitario=Decimal(total), iva_alicuota=Decimal('0.00'),
            total=Decimal(total))
        venta.recalcular_totales()
        from contable.services.saldos import recalcular_saldo_venta
        recalcular_saldo_venta(venta.pk)
        venta.refresh_from_db()
        return venta

    def cobrar_con_recibo(self, venta, importe):
        respuesta = self.client.post(
            reverse('htmx_procesar_recibo'),
            data=json.dumps({
                'cliente_id': self.cliente.pk,
                'sucursal_id': self.sucursal.id,
                'fecha': "2026-02-10", 'punto': 1, 'tipo': 'C', 'condic': 1,
                'origen': 'MOSTRADOR',
                'aplicaciones': [{'id': venta.pk, 'importe': str(importe)}],
                'imputaciones': [],
                'valores': [{'categoria': 'EFE-ARS', 'importe': str(importe)}],
            }),
            content_type='application/json')
        self.assertEqual(respuesta.status_code, 200, respuesta.content[:400])
        return respuesta

    def cerrar_caja(self, contado, fondo_fijo='0.00'):
        respuesta = self.client.post(
            reverse('caja_cierre_procesar'),
            data=json.dumps({'contado_pesos': str(contado), 'contado_dolares': '0',
                             'fondo_fijo': str(fondo_fijo)}),
            content_type='application/json')
        self.assertEqual(respuesta.status_code, 200, respuesta.content[:400])
        return respuesta


class ElCircuitoDelEfectivoTestCase(BaseCajaCierraTestCase):
    def test_la_cobranza_del_mostrador_debita_la_cuenta_del_mostrador(self):
        """La plata la va a rendir el cajero: tiene que estar en SU cuenta."""
        venta = self.crear_factura('10000.00')
        self.cobrar_con_recibo(venta, '10000.00')

        self.assertEqual(self.saldo(self.cta_mostrador), Decimal('10000.00'))
        self.assertEqual(self.saldo(self.cta_caja), Decimal('0.00'))

    def test_al_cerrar_sin_fondo_fijo_la_caja_queda_en_cero(self):
        """El requerimiento, en su forma más simple."""
        venta = self.crear_factura('10000.00')
        self.cobrar_con_recibo(venta, '10000.00')

        self.cerrar_caja(contado='10000.00')

        self.assertEqual(self.saldo(self.cta_mostrador), Decimal('0.00'))

    def test_al_cerrar_con_fondo_fijo_la_caja_queda_en_el_fondo_fijo(self):
        """El sencillo se queda físicamente en el cajón, y la cuenta lo refleja."""
        venta = self.crear_factura('10000.00')
        self.cobrar_con_recibo(venta, '10000.00')

        self.cerrar_caja(contado='10000.00', fondo_fijo='1500.00')

        self.assertEqual(self.saldo(self.cta_mostrador), Decimal('1500.00'))

    def test_lo_rendido_llega_a_la_caja_central(self):
        """La contrapartida: lo que sale del mostrador entra a Tesorería."""
        venta = self.crear_factura('10000.00')
        self.cobrar_con_recibo(venta, '10000.00')

        self.cerrar_caja(contado='10000.00', fondo_fijo='1500.00')

        self.assertEqual(self.saldo(self.cta_central), Decimal('8500.00'))

    def test_dos_cobranzas_y_un_cierre_siguen_cerrando(self):
        primera = self.crear_factura('10000.00', numero=1)
        segunda = self.crear_factura('4000.00', numero=2)
        self.cobrar_con_recibo(primera, '10000.00')
        self.cobrar_con_recibo(segunda, '4000.00')

        self.cerrar_caja(contado='14000.00')

        self.assertEqual(self.saldo(self.cta_mostrador), Decimal('0.00'))


class ElRecibleDelMostradorTestCase(BaseCajaCierraTestCase):
    """Plan 077 §F: el mismo recibo de siempre, pero cae en la caja del cajero."""

    def test_el_recibo_del_mostrador_entra_en_la_sesion_del_cajero(self):
        venta = self.crear_factura('10000.00')
        self.cobrar_con_recibo(venta, '10000.00')

        recibo = Recibo.objects.get()
        self.assertEqual(recibo.sesion_caja_id, self.sesion.id)
        self.assertEqual(recibo.sesion_caja.caja.tipo, 'M')

    def test_sin_caja_abierta_el_recibo_del_mostrador_se_rechaza(self):
        """No se puede meter plata en un cajón que no está abierto."""
        self.sesion.estado = 'C'
        self.sesion.save(update_fields=['estado'])

        venta = self.crear_factura('10000.00')
        respuesta = self.client.post(
            reverse('htmx_procesar_recibo'),
            data=json.dumps({
                'cliente_id': self.cliente.pk, 'sucursal_id': self.sucursal.id,
                'fecha': "2026-02-10", 'punto': 1, 'tipo': 'C', 'condic': 1,
                'origen': 'MOSTRADOR',
                'aplicaciones': [{'id': venta.pk, 'importe': '10000.00'}],
                'imputaciones': [],
                'valores': [{'categoria': 'EFE-ARS', 'importe': '10000.00'}],
            }),
            content_type='application/json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(Recibo.objects.count(), 0)

    def test_el_recibo_de_tesoreria_sigue_yendo_a_tesoreria(self):
        """El del menú principal es el del Tesorero y no cambia."""
        venta = self.crear_factura('10000.00')
        respuesta = self.client.post(
            reverse('htmx_procesar_recibo'),
            data=json.dumps({
                'cliente_id': self.cliente.pk, 'sucursal_id': self.sucursal.id,
                'fecha': "2026-02-10", 'punto': 1, 'tipo': 'C', 'condic': 1,
                'aplicaciones': [{'id': venta.pk, 'importe': '10000.00'}],
                'imputaciones': [],
                'valores': [{'categoria': 'EFE-ARS', 'importe': '10000.00'}],
            }),
            content_type='application/json')
        self.assertEqual(respuesta.status_code, 200, respuesta.content[:400])

        recibo = Recibo.objects.get()
        self.assertEqual(recibo.sesion_caja.caja.tipo, 'T')
        self.assertEqual(self.saldo(self.cta_central), Decimal('10000.00'))
        self.assertEqual(self.saldo(self.cta_mostrador), Decimal('0.00'))
