"""El lote de ESTUDIO debe marcar bien la condición de cada comprobante.

El comprobante interno (INTERNO/PRE) es NO FISCAL: `condic = 2`. Si queda con el default
(1 = Real), el comprobante dice ser fiscal mientras su asiento dice lo contrario, y
`contabilizar_venta_individual` —que puebla el Libro IVA cuando `condic in (1, 3)`—
terminaría declarando ante ARCA una operación que no existe fiscalmente.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from contable.models import (Asiento, AsientoLinea, Cuenta, Ejercicio,
                             LibroIvaVentas, ParametrosContables)
from empresas.models import Empresa, PuntoVenta, Sucursal
from facturacion.models import ClienteProveedor, TipoComprobante, Venta
from verticalidades.estudio.models import TarifaEstudio
from facturacion.services.facturacion_lote_service import FacturacionLoteService
from productos.models import Producto, Rubro


class LoteEstudioCondicTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Estudio Prueba", cuit="30111111118", tipo_actividad="ESTUDIO")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, nombre="Casa Central", punto=1)
        self.punto_venta = PuntoVenta.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, numero=3)
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa, inicio="2026-01-01", cierre="2026-12-31")

        self.usuario = User.objects.create_user(username="contador", password="x")

        TipoComprobante.objects.create(codigo='006', detalle="Factura B", signo=1)
        TipoComprobante.objects.create(codigo='PRE', detalle="Comprobante Interno", signo=1)

        self.cuenta = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="4.1.1", cuenta="HONORARIOS", imputable=1)
        self.cuenta_cliente = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.3", cuenta="DEUDORES", imputable=1)

        self.cuenta_rubro = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="4.1.2", cuenta="HONORARIOS RUBRO", imputable=1)
        self.cta_iva = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="2.1.4", cuenta="IVA DEBITO FISCAL", imputable=1)
        # Sin ParametrosContables la señal no contabiliza nada, y en silencio.
        ParametrosContables.objects.create(
            empresa=self.empresa,
            cta_clientes_default=self.cuenta_cliente,
            cta_ventas=self.cuenta,
            cta_iva_debito=self.cta_iva,
            metodo_contabilizacion_ventas=1)

        self.cliente = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="Cliente Uno SA", tipo_entidad=1,
            cuit="30712345678", condicion_iva="MONOTRIBUTO",
            cta_pat=self.cuenta_cliente.id)
        self.producto = Producto.objects.create(
            empresa=self.empresa, detalle="Honorarios mensuales",
            alic_iva=Decimal('21.00'))

        self.tarifa = TarifaEstudio.objects.create(
            empresa=self.empresa, cliente=self.cliente, producto=self.producto,
            cuenta=self.cuenta, tarifa_f=Decimal('100000.00'),
            tarifa_p=Decimal('50000.00'), activo=True)

    def _procesar(self):
        servicio = FacturacionLoteService(empresa_id=self.empresa.id, usuario=self.usuario)
        # Misma forma de fila que arma `api_facturacion_lotes` para la grilla.
        fila = {
            'id_tarifa': self.tarifa.id,
            'cliente_id': self.cliente.codigo_id,
            'producto_id': self.producto.id,
            'producto_detalle': self.producto.detalle,
            'tarifa_f': 100000.0,
            'tarifa_p': 50000.0,
            'alic_iva': 21.0,
        }
        return servicio.procesar_lote(
            [fila], periodo="202608", pto_vta_id=self.punto_venta.id, modo_prueba=True)

    def test_el_lote_genera_los_dos_comprobantes(self):
        self._procesar()
        self.assertEqual(Venta.objects.count(), 2)

    def test_la_factura_queda_como_fiscal(self):
        self._procesar()
        fiscal = Venta.objects.get(tipo__codigo='006')
        self.assertEqual(fiscal.condic, 1)

    def test_el_comprobante_interno_queda_como_NO_fiscal(self):
        """Regresión: quedaba con el default 1 y se declaraba como fiscal."""
        self._procesar()
        interno = Venta.objects.get(tipo__codigo='PRE')
        self.assertEqual(interno.condic, 2)

    def test_el_interno_no_entra_al_libro_iva(self):
        self._procesar()
        interno = Venta.objects.get(tipo__codigo='PRE')
        self.assertFalse(
            LibroIvaVentas.objects.filter(asiento_id=interno.asiento_id).exists(),
            "Un comprobante no fiscal nunca debe alimentar el Libro IVA de Ventas.")

    def test_el_comprobante_y_su_asiento_coinciden_en_condic(self):
        """Regla inflexible: el asiento hereda el `condic` del comprobante."""
        self._procesar()
        interno = Venta.objects.get(tipo__codigo='PRE')
        asiento = Asiento.objects.get(asiento_id=interno.asiento_id)
        self.assertEqual(asiento.condic, interno.condic)

    def test_cliente_sin_cuenta_patrimonial_usa_la_del_parametro(self):
        """Regla de ventas: si el cliente no tiene `cta_pat`, se usa
        `ParametrosContables.cta_clientes_default`.

        Antes el lote armaba el asiento a mano y, si no resolvía las dos cuentas, emitía
        el comprobante **sin registración y sin ningún aviso**. Ahora delega en
        `contabilizar_venta_individual`, que aplica el fallback y valida.
        """
        self.cliente.cta_pat = 0
        self.cliente.save(update_fields=['cta_pat'])

        self._procesar()
        interno = Venta.objects.get(tipo__codigo='PRE')
        self.assertIsNotNone(interno.asiento_id)

        lineas = AsientoLinea.objects.filter(asiento__asiento_id=interno.asiento_id)
        debe = lineas.filter(debe__gt=0).first()
        self.assertEqual(debe.cuenta_id, self.cuenta_cliente.id)

    def test_la_cuenta_de_resultado_sale_del_rubro_del_producto(self):
        """Regla de ventas: el haber lo define el RUBRO del producto facturado, no el
        parámetro general, que es sólo el respaldo."""
        rubro = Rubro.objects.create(
            empresa=self.empresa, detalle="HONORARIOS PROFESIONALES",
            cta_ventas=self.cuenta_rubro)
        self.producto.rubro = rubro
        self.producto.save(update_fields=['rubro'])

        self._procesar()
        interno = Venta.objects.get(tipo__codigo='PRE')
        lineas = AsientoLinea.objects.filter(asiento__asiento_id=interno.asiento_id)
        haber = lineas.filter(haber__gt=0).first()
        self.assertEqual(haber.cuenta_id, self.cuenta_rubro.id)

    def test_sin_rubro_el_haber_cae_al_parametro_general(self):
        self._procesar()
        interno = Venta.objects.get(tipo__codigo='PRE')
        lineas = AsientoLinea.objects.filter(asiento__asiento_id=interno.asiento_id)
        haber = lineas.filter(haber__gt=0).first()
        self.assertEqual(haber.cuenta_id, self.cuenta.id)

    def test_los_importes_van_a_donde_corresponde(self):
        self._procesar()
        fiscal = Venta.objects.get(tipo__codigo='006')
        interno = Venta.objects.get(tipo__codigo='PRE')
        self.assertEqual(fiscal.neto, Decimal('100000.00'))
        self.assertEqual(interno.total, Decimal('50000.00'))
        # El interno no lleva IVA: no es un comprobante fiscal.
        self.assertEqual(interno.iva, Decimal('0.00'))
