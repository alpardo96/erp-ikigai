"""La Nota de Crédito descuenta el saldo de su factura de origen (Plan 076 §D).

La regla, en palabras del usuario: *"Las notas de crédito, como están vinculadas a la factura
que le dio origen, deben computarse en el saldo pendiente de la factura (factura − NC
relacionadas), y de ahí sale el saldo real de la factura. La NC queda con saldo cero porque se
aplicó totalmente a la factura de origen."*
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from contable.models import Cuenta, Ejercicio, ParametrosContables
from contable.services.saldos import (recalcular_saldo_cliente_proveedor,
                                      recalcular_saldo_venta)
from empresas.models import Empresa, PuntoVenta, Sucursal
from facturacion.models import (ClienteProveedor, TipoComprobante, Venta, VentaItem)
from facturacion.services.notas_credito import emitir_nota_credito_desde_venta
from productos.models import Producto, Rubro, StockSucursal
from tesoreria.models import Recibo, ReciboAplicacion


class BaseNotaCreditoTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Empresa Prueba", cuit="30111111118")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, nombre="Casa Central", punto=1)
        PuntoVenta.objects.create(empresa=self.empresa, sucursal=self.sucursal, numero=1)
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa, inicio="2026-01-01", cierre="2026-12-31")
        self.usuario = User.objects.create_user(username="admin1", password="x")

        self.factura_b, _ = TipoComprobante.objects.get_or_create(
            codigo='006', defaults={'detalle': "Factura B", 'signo': 1})
        TipoComprobante.objects.get_or_create(
            codigo='008', defaults={'detalle': "Nota de Crédito B", 'signo': -1})

        cta_cli = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.3", cuenta="DEUDORES", imputable=1)
        cta_vta = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="4.1.1", cuenta="VENTAS", imputable=1)
        cta_iva = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="2.1.1", cuenta="IVA DEBITO", imputable=1)
        ParametrosContables.objects.create(
            empresa=self.empresa, cta_clientes_default=cta_cli, cta_ventas=cta_vta,
            cta_iva_debito=cta_iva, metodo_contabilizacion_ventas=1)

        rubro = Rubro.objects.create(empresa=self.empresa, detalle="GENERAL",
                                     cta_ventas=cta_vta)
        self.producto = Producto.objects.create(
            empresa=self.empresa, detalle="Producto Uno",
            precio_total=Decimal('1000.00'), rubro=rubro)
        StockSucursal.objects.create(
            producto=self.producto, sucursal=self.sucursal,
            stock_inicial=Decimal('1000.00'), cantidad=Decimal('1000.00'))

        self.cliente = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="Cliente Uno", tipo_entidad=1,
            domicilio="Belgrano 100", condicion_iva="CONSUMIDOR FINAL")

    def crear_factura(self, cantidad=10, precio='1000.00', numero=1):
        venta = Venta.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, ejercicio=self.ejercicio,
            tipo=self.factura_b, punto=1, numero=numero, fecha="2026-02-01",
            periodo="202602", cliente=self.cliente,
            cliente_razon_social=self.cliente.razon_social,
            usuario=self.usuario, condic=1, estado=0)
        total = Decimal(precio) * Decimal(str(cantidad))
        VentaItem.objects.create(
            venta=venta, producto=self.producto, concepto=self.producto.detalle,
            cantidad=Decimal(str(cantidad)), precio_unitario=Decimal(precio),
            iva_alicuota=Decimal('21.00'), total=total)
        venta.recalcular_totales()
        recalcular_saldo_venta(venta.pk)
        venta.refresh_from_db()
        return venta


class SaldoDeLaFacturaTestCase(BaseNotaCreditoTestCase):
    def test_la_nc_descuenta_el_saldo_de_su_factura(self):
        factura = self.crear_factura(cantidad=10)
        self.assertEqual(Decimal(str(factura.saldo)), Decimal('10000.00'))

        item = factura.items.get()
        emitir_nota_credito_desde_venta(factura, {item.id: 4}, self.usuario)

        factura.refresh_from_db()
        self.assertEqual(Decimal(str(factura.saldo)), Decimal('6000.00'))

    def test_la_nc_queda_con_saldo_cero(self):
        """Se aplicó totalmente a la factura de origen: no queda nada pendiente en ella."""
        factura = self.crear_factura(cantidad=10)
        item = factura.items.get()
        nota = emitir_nota_credito_desde_venta(factura, {item.id: 4}, self.usuario)

        nota.refresh_from_db()
        self.assertEqual(Decimal(str(nota.saldo)), Decimal('0.00'))

    def test_la_nc_guarda_el_comprobante_que_le_dio_origen(self):
        factura = self.crear_factura(cantidad=10)
        item = factura.items.get()
        nota = emitir_nota_credito_desde_venta(factura, {item.id: 4}, self.usuario)

        self.assertEqual(nota.venta_origen_id, factura.pk)
        self.assertEqual([n.pk for n in factura.notas_credito.all()], [nota.pk])

    def test_una_nc_total_deja_la_factura_en_cero(self):
        factura = self.crear_factura(cantidad=10)
        item = factura.items.get()
        emitir_nota_credito_desde_venta(factura, {item.id: 10}, self.usuario)

        factura.refresh_from_db()
        self.assertEqual(Decimal(str(factura.saldo)), Decimal('0.00'))

    def test_dos_nc_parciales_se_acumulan(self):
        factura = self.crear_factura(cantidad=10)
        item = factura.items.get()
        emitir_nota_credito_desde_venta(factura, {item.id: 3}, self.usuario)
        emitir_nota_credito_desde_venta(factura, {item.id: 2}, self.usuario)

        factura.refresh_from_db()
        self.assertEqual(Decimal(str(factura.saldo)), Decimal('5000.00'))

    def test_la_nc_y_la_cobranza_conviven_en_el_mismo_saldo(self):
        """`total − cobrado − recibos − NC`: los términos se restan todos, sin pisarse."""
        factura = self.crear_factura(cantidad=10)
        recibo = Recibo.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, ejercicio=self.ejercicio,
            cliente=self.cliente, fecha="2026-02-10", punto=1,
            total=Decimal('3000.00'), condic=1)
        ReciboAplicacion.objects.create(
            recibo=recibo, venta=factura, importe=Decimal('3000.00'),
            importe_pesos=Decimal('3000.00'))

        item = factura.items.get()
        emitir_nota_credito_desde_venta(factura, {item.id: 2}, self.usuario)

        factura.refresh_from_db()
        self.assertEqual(Decimal(str(factura.saldo)), Decimal('5000.00'))

    def test_anular_la_nc_le_devuelve_el_saldo_a_la_factura(self):
        """El descuento se revierte: la deuda vuelve a existir."""
        factura = self.crear_factura(cantidad=10)
        item = factura.items.get()
        nota = emitir_nota_credito_desde_venta(factura, {item.id: 4}, self.usuario)

        nota.estado = 1
        nota.save()

        factura.refresh_from_db()
        self.assertEqual(Decimal(str(factura.saldo)), Decimal('10000.00'))


class SaldoDeLaEntidadTestCase(BaseNotaCreditoTestCase):
    def test_el_saldo_del_cliente_no_se_cuenta_dos_veces(self):
        """La NC ya entra en negativo por su signo: descontarla de nuevo la duplicaría."""
        factura = self.crear_factura(cantidad=10)
        recalcular_saldo_cliente_proveedor(self.cliente.pk)
        self.cliente.refresh_from_db()
        self.assertEqual(Decimal(str(self.cliente.saldo)), Decimal('10000.00'))

        item = factura.items.get()
        emitir_nota_credito_desde_venta(factura, {item.id: 4}, self.usuario)

        recalcular_saldo_cliente_proveedor(self.cliente.pk)
        self.cliente.refresh_from_db()
        self.assertEqual(Decimal(str(self.cliente.saldo)), Decimal('6000.00'))

    def test_el_saldo_del_cliente_coincide_con_la_suma_de_los_comprobantes(self):
        """La prueba de fondo: las dos lentes tienen que dar lo mismo."""
        primera = self.crear_factura(cantidad=10, numero=1)
        segunda = self.crear_factura(cantidad=5, numero=2)
        item = primera.items.get()
        emitir_nota_credito_desde_venta(primera, {item.id: 4}, self.usuario)

        recalcular_saldo_cliente_proveedor(self.cliente.pk)
        self.cliente.refresh_from_db()

        suma = sum((Decimal(str(v.saldo or 0)) for v in
                    Venta.objects.filter(cliente=self.cliente, estado=0)), Decimal('0.00'))
        self.assertEqual(suma, Decimal(str(self.cliente.saldo)))
        self.assertEqual(suma, Decimal('11000.00'))


class ComprobantesAbiertosTestCase(BaseNotaCreditoTestCase):
    def test_el_fifo_no_ofrece_una_factura_ya_cubierta_por_una_nc(self):
        """Con la regla nueva el filtro `saldo > 0` es correcto POR CONSTRUCCIÓN."""
        from verticalidades.distribucion.services.cobranza_fifo import comprobantes_abiertos

        factura = self.crear_factura(cantidad=10)
        item = factura.items.get()
        emitir_nota_credito_desde_venta(factura, {item.id: 10}, self.usuario)

        abiertos = list(comprobantes_abiertos(self.cliente, self.empresa.id))
        self.assertEqual(abiertos, [])

    def test_la_nc_nunca_aparece_como_comprobante_a_cobrar(self):
        factura = self.crear_factura(cantidad=10)
        item = factura.items.get()
        nota = emitir_nota_credito_desde_venta(factura, {item.id: 4}, self.usuario)

        from verticalidades.distribucion.services.cobranza_fifo import comprobantes_abiertos
        abiertos = [v.pk for v in comprobantes_abiertos(self.cliente, self.empresa.id)]
        self.assertIn(factura.pk, abiertos)
        self.assertNotIn(nota.pk, abiertos)
