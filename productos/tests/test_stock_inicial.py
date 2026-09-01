"""Plan 053 — Stock derivado de `stock_inicial` más los comprobantes.

    stock = stock_inicial + compras + recepciones − ventas − remitos internos

Lo que se prueba no es sólo que los números den, sino que el stock sea **reconstruible**: el caso
`test_se_autorrepara` es el que da sentido a todo el plan y con el modelo anterior —un contador
incremental sin punto de partida— era imposible.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from empresas.models import Empresa, Sucursal
from facturacion.models import (
    ClienteProveedor, Compra, CompraItem, Recepcion, RecepcionItem,
    RemitoInterno, RemitoInternoItem, TipoComprobante, Venta, VentaItem,
)
from productos.models import Producto, StockSucursal
from productos.services.stock_service import recalcular_stock

User = get_user_model()

D = lambda v: Decimal(str(v))  # noqa: E731


class BaseStock(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='stock_user', password='clave')
        self.empresa = Empresa.objects.create(nombre="STOCK SA")
        self.suc_a = Sucursal.objects.create(nombre="CENTRAL", empresa=self.empresa)
        self.suc_b = Sucursal.objects.create(nombre="DEPOSITO", empresa=self.empresa)

        self.cliente = ClienteProveedor.objects.create(
            razon_social="CLIENTE SRL", tipo_entidad=1, empresa=self.empresa)
        self.proveedor = ClienteProveedor.objects.create(
            razon_social="PROVEEDOR SA", tipo_entidad=2, empresa=self.empresa)

        # `signo` es lo que distingue una factura de una nota de crédito.
        self.factura = TipoComprobante.objects.create(codigo="1", detalle="Factura A", signo=1)
        self.nota_credito = TipoComprobante.objects.create(codigo="3", detalle="NC A", signo=-1)

        self.producto = Producto.objects.create(detalle="PRODUCTO UNO", empresa=self.empresa)

    # ------------------------------------------------------------------ helpers
    def sembrar(self, inicial, sucursal=None):
        registro, _ = StockSucursal.objects.get_or_create(
            producto=self.producto, sucursal=sucursal or self.suc_a)
        registro.stock_inicial = D(inicial)
        registro.save(update_fields=['stock_inicial'])
        return recalcular_stock(self.producto.id, (sucursal or self.suc_a).id)

    def stock(self, sucursal=None):
        return StockSucursal.objects.get(
            producto=self.producto, sucursal=sucursal or self.suc_a).cantidad

    def crear_venta(self, cantidad, tipo=None, estado=0, id_fac_rem=None, sucursal=None):
        venta = Venta.objects.create(
            fecha=date.today(), tipo=tipo or self.factura, punto=1,
            numero=Venta.objects.count() + 1000, cliente=self.cliente,
            empresa=self.empresa, sucursal=sucursal or self.suc_a, usuario=self.user,
            estado=estado, id_fac_rem=id_fac_rem)
        item = VentaItem.objects.create(
            venta=venta, producto=self.producto, cantidad=D(cantidad),
            precio_unitario=D(100), iva_alicuota=D(21), total=D(cantidad) * D(100))
        return venta, item

    def crear_compra(self, cantidad, tipo=None, id_fac_rem=None, por_recepcion=False,
                     sucursal=None):
        compra = Compra.objects.create(
            fecha=date.today(), tipo=tipo or self.factura, punto=1,
            numero=Compra.objects.count() + 2000, proveedor=self.proveedor,
            empresa=self.empresa, sucursal=sucursal or self.suc_a, usuario=self.user,
            id_fac_rem=id_fac_rem, gestion_stock_por_recepcion=por_recepcion)
        item = CompraItem.objects.create(
            compra=compra, producto=self.producto, cantidad=D(cantidad),
            precio_unitario=D(50), total=D(cantidad) * D(50))
        return compra, item

    def crear_recepcion(self, cantidad, estado=0, sucursal=None, origen='PROVEEDOR'):
        recepcion = Recepcion.objects.create(
            empresa=self.empresa, sucursal=sucursal or self.suc_a, punto=1,
            numero=Recepcion.objects.count() + 1, fecha=date.today(),
            origen=origen, proveedor=self.proveedor, usuario=self.user, estado=estado)
        item = RecepcionItem.objects.create(
            recepcion=recepcion, producto=self.producto, cantidad_recibida=D(cantidad))
        return recepcion, item

    def crear_remito_interno(self, cantidad, estado=0):
        remito = RemitoInterno.objects.create(
            empresa=self.empresa, sucursal_origen=self.suc_a, sucursal_destino=self.suc_b,
            punto=1, numero=RemitoInterno.objects.count() + 1, fecha=date.today(),
            usuario=self.user, estado=estado)
        item = RemitoInternoItem.objects.create(
            remito=remito, producto=self.producto, cantidad_enviada=D(cantidad))
        return remito, item


class FormulaTest(BaseStock):

    def test_sin_movimientos_el_stock_es_el_inicial(self):
        self.assertEqual(self.sembrar(100), D(100))
        self.assertEqual(self.stock(), D(100))

    def test_compra_suma(self):
        self.sembrar(10)
        self.crear_compra(5)
        self.assertEqual(self.stock(), D(15))

    def test_compra_con_gestion_por_recepcion_no_suma(self):
        """Circuito OC (Plan 028): el stock lo da la Recepción, no la factura."""
        self.sembrar(10)
        self.crear_compra(5, por_recepcion=True)
        self.assertEqual(self.stock(), D(10))

    def test_compra_con_remito_previo_no_suma(self):
        self.sembrar(10)
        self.crear_compra(5, id_fac_rem=999)
        self.assertEqual(self.stock(), D(10))

    def test_recepcion_suma(self):
        self.sembrar(10)
        self.crear_recepcion(7)
        self.assertEqual(self.stock(), D(17))

    def test_recepcion_anulada_no_suma(self):
        self.sembrar(10)
        self.crear_recepcion(7, estado=1)
        self.assertEqual(self.stock(), D(10))

    def test_venta_resta(self):
        self.sembrar(10)
        self.crear_venta(4)
        self.assertEqual(self.stock(), D(6))

    def test_venta_anulada_no_resta(self):
        self.sembrar(10)
        venta, _ = self.crear_venta(4)
        venta.estado = 1
        venta.save()
        recalcular_stock(self.producto.id, self.suc_a.id)
        self.assertEqual(self.stock(), D(10))

    def test_venta_con_remito_previo_no_resta(self):
        self.sembrar(10)
        self.crear_venta(4, id_fac_rem=888)
        self.assertEqual(self.stock(), D(10))


class NotasDeCreditoTest(BaseStock):
    """El signo del comprobante invierte el movimiento (`TipoComprobante.signo = −1`)."""

    def test_nc_de_venta_devuelve_stock(self):
        self.sembrar(10)
        self.crear_venta(4)                              # −4
        self.assertEqual(self.stock(), D(6))
        self.crear_venta(3, tipo=self.nota_credito)      # devolución: +3
        self.assertEqual(self.stock(), D(9))

    def test_nc_de_compra_saca_stock(self):
        self.sembrar(10)
        self.crear_compra(6)                             # +6
        self.assertEqual(self.stock(), D(16))
        self.crear_compra(2, tipo=self.nota_credito)     # devolución al proveedor: −2
        self.assertEqual(self.stock(), D(14))


class RemitoInternoTest(BaseStock):

    def test_remito_resta_en_origen_y_no_toca_destino(self):
        self.sembrar(20)
        self.sembrar(0, sucursal=self.suc_b)
        self.crear_remito_interno(5)
        self.assertEqual(self.stock(), D(15))
        self.assertEqual(self.stock(self.suc_b), D(0), "La mercadería queda en tránsito")

    def test_transferencia_completa_no_cambia_el_total(self):
        """Remito (salida del origen) + Recepción interna (entrada al destino): el total se mantiene."""
        self.sembrar(20)
        self.sembrar(0, sucursal=self.suc_b)
        self.crear_remito_interno(5)
        self.crear_recepcion(5, sucursal=self.suc_b, origen='INTERNO')

        self.assertEqual(self.stock(), D(15))
        self.assertEqual(self.stock(self.suc_b), D(5))
        self.assertEqual(self.stock() + self.stock(self.suc_b), D(20))

    def test_remito_anulado_no_resta(self):
        self.sembrar(20)
        self.crear_remito_interno(5, estado=3)
        self.assertEqual(self.stock(), D(20))


class ReconstruccionTest(BaseStock):
    """Lo que el modelo anterior no permitía."""

    def test_borrar_un_item_devuelve_el_stock(self):
        self.sembrar(10)
        _, item = self.crear_venta(4)
        self.assertEqual(self.stock(), D(6))
        item.delete()
        self.assertEqual(self.stock(), D(10))

    def test_el_recalculo_es_idempotente(self):
        self.sembrar(10)
        self.crear_compra(5)
        self.crear_venta(3)
        primero = recalcular_stock(self.producto.id, self.suc_a.id)
        segundo = recalcular_stock(self.producto.id, self.suc_a.id)
        self.assertEqual(primero, segundo)
        self.assertEqual(primero, D(12))

    def test_se_autorrepara(self):
        """El caso que justifica el plan.

        Si algo deja `cantidad` mal —un borrado con las señales desactivadas, una importación, un
        proceso interrumpido— el recálculo lo corrige. Con el contador incremental anterior el
        valor erróneo quedaba para siempre y no había forma de detectarlo.
        """
        self.sembrar(10)
        self.crear_venta(4)
        self.assertEqual(self.stock(), D(6))

        StockSucursal.objects.filter(
            producto=self.producto, sucursal=self.suc_a).update(cantidad=D(-999))
        self.assertEqual(self.stock(), D(-999))

        recalcular_stock(self.producto.id, self.suc_a.id)
        self.assertEqual(self.stock(), D(6))

    def test_los_movimientos_de_auditoria_se_siguen_registrando(self):
        from productos.models import MovimientoStock
        self.sembrar(10)
        self.crear_venta(4)
        self.assertTrue(
            MovimientoStock.objects.filter(producto=self.producto, tipo='SALIDA').exists())


class AislamientoTest(BaseStock):

    def test_cada_sucursal_lleva_su_propio_stock(self):
        self.sembrar(10)
        self.sembrar(50, sucursal=self.suc_b)
        self.crear_venta(4, sucursal=self.suc_a)

        self.assertEqual(self.stock(self.suc_a), D(6))
        self.assertEqual(self.stock(self.suc_b), D(50), "La otra sucursal no se toca")

    def test_el_stock_inicial_es_por_sucursal(self):
        self.sembrar(10)
        self.sembrar(50, sucursal=self.suc_b)
        a = StockSucursal.objects.get(producto=self.producto, sucursal=self.suc_a)
        b = StockSucursal.objects.get(producto=self.producto, sucursal=self.suc_b)
        self.assertEqual((a.stock_inicial, b.stock_inicial), (D(10), D(50)))
