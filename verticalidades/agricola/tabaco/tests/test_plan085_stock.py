"""Plan 085 — stock del tabaco.

Lo que se protege:

1. Que los kilos entren al CONFIRMAR el romaneo y salgan al anularlo.
2. Que la venta descuente por el término de siempre, sin un egreso propio que duplicaría la baja.
3. Que reclasificar y liquidar NO muevan stock: no cambian lo que hay en el galpón.
4. Que los cuatro términos originales del core sigan dando idéntico.
5. Que la conciliación cierre en cero y detecte la diferencia cuando la haya.
"""
from datetime import date
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from facturacion.models import TipoComprobante, Venta, VentaItem
from productos.models import Producto, StockSucursal
from productos.services.stock_service import recalcular_stock, recalcular_stock_masivo
from verticalidades.agricola.tabaco.models import RomaneoTabaco, VariedadTabaco
from verticalidades.agricola.tabaco.services import liquidacion as liq_svc
from verticalidades.agricola.tabaco.services import romaneo as rom_svc
from verticalidades.agricola.tabaco.services import stock as stock_svc

from .test_plan083_liquidacion import LiquidacionBaseTestCase


class StockBaseTestCase(LiquidacionBaseTestCase):
    """Sobre el escenario del Plan 083, asigna el producto de stock de la variedad."""

    def setUp(self):
        super().setUp()
        # Crear una Venta dispara la contabilización automática del core, que exige estas
        # cuentas. Se cargan acá y no en el escenario del Plan 083 porque son de VENTAS: aquella
        # etapa sólo compraba.
        from contable.models import ParametrosContables
        ParametrosContables.objects.filter(empresa=self.empresa).update(
            cta_clientes_default=self._cuenta('112001', 'DEUDORES POR VENTAS', 'A').pk,
            cta_ventas=self._cuenta('411001', 'VENTAS', 'R').pk,
            cta_iva_debito=self._cuenta('213001', 'IVA DEBITO FISCAL', 'P').pk)

        self.producto = Producto.objects.create(
            empresa=self.empresa, detalle="TABACO BURLEY", unidad_venta='KG',
            alic_iva=Decimal('21.00'))
        self.burley.producto = self.producto
        self.burley.save(update_fields=['producto'])

        # El término se registra en `ready()`, una sola vez por proceso. Se garantiza acá para
        # que estos tests no dependan de si otro módulo lo limpió antes.
        from productos.services import stock_service
        if not any(t['nombre'] == 'agricola_tabaco_fardos' for t in stock_service._TERMINOS_EXTRA):
            stock_service.registrar_termino_stock(stock_svc.termino_de_stock())

    def _stock(self):
        return recalcular_stock(self.producto.pk, self.sucursal.pk)

    def _romaneo_confirmado(self, kilos='1000'):
        r = self._romaneo(kilos=kilos)
        r.refresh_from_db()
        return r


class IngresoDeStockTests(StockBaseTestCase):

    def test_confirmar_romaneo_ingresa_los_kilos(self):
        self.assertEqual(self._stock(), Decimal('0.00'))

        self._romaneo_confirmado(kilos='1000')

        self.assertEqual(self._stock(), Decimal('1000.00'))

    def test_un_borrador_no_mueve_stock(self):
        borrador = rom_svc.abrir_romaneo(
            empresa=self.empresa, sucursal=self.sucursal, productor=self.productor,
            variedad=self.burley, campania=self.campania, fecha=date(2026, 9, 1),
            usuario=self.user)
        rom_svc.agregar_fardo(borrador, clase=self.b1f, kilos=Decimal('500'), usuario=self.user)

        self.assertEqual(self._stock(), Decimal('0.00'))

    def test_anular_romaneo_saca_los_kilos(self):
        romaneo = self._romaneo_confirmado(kilos='1000')
        self.assertEqual(self._stock(), Decimal('1000.00'))

        rom_svc.anular_romaneo(romaneo, "Error de carga", self.user)

        self.assertEqual(self._stock(), Decimal('0.00'))

    def test_varios_romaneos_suman(self):
        self._romaneo_confirmado(kilos='1000')
        self._romaneo_confirmado(kilos='250')

        self.assertEqual(self._stock(), Decimal('1250.00'))

    def test_el_stock_se_actualiza_sin_recalcular_a_mano(self):
        """`confirmar_romaneo()` dispara el recálculo: el operador no tiene que hacer nada."""
        self._romaneo_confirmado(kilos='700')

        fila = StockSucursal.objects.get(producto=self.producto, sucursal=self.sucursal)
        self.assertEqual(fila.cantidad, Decimal('700.00'))


class NoMuevenStockTests(StockBaseTestCase):

    def test_liquidar_no_mueve_stock(self):
        """Liquidar factura la compra; la mercadería ya había entrado con el romaneo."""
        romaneo = self._romaneo_confirmado(kilos='1000')
        self.assertEqual(self._stock(), Decimal('1000.00'))

        liq_svc.confirmar_liquidacion(self._preparar(romaneos=[romaneo]), self.user)

        self.assertEqual(self._stock(), Decimal('1000.00'))

    def test_reclasificar_no_mueve_stock(self):
        """Son los mismos kilos, mejor descriptos."""
        romaneo = self._romaneo_confirmado(kilos='1000')
        fardo = romaneo.fardos.first()
        otra = self.b1f.__class__.objects.create(
            empresa=self.empresa, variedad=self.burley, codigo=90, detalle='B2F',
            coeficiente=Decimal('0.92'))

        rom_svc.reclasificar_fardo(fardo, clase_nueva=otra, motivo="Revisión", usuario=self.user)

        self.assertEqual(self._stock(), Decimal('1000.00'))


class EgresoPorVentaTests(StockBaseTestCase):

    def test_la_venta_descuenta_por_el_termino_de_siempre(self):
        """No hay término de egreso propio: lo resuelve `ventas`, que existe desde antes."""
        self._romaneo_confirmado(kilos='1000')

        tipo = TipoComprobante.objects.create(codigo='085', detalle='FACTURA A', signo=1)
        venta = Venta.objects.create(
            fecha=date(2026, 9, 15), tipo=tipo, punto=1, numero=1,
            cliente=self.productor, empresa=self.empresa, sucursal=self.sucursal,
            usuario=self.user, estado=0)
        VentaItem.objects.create(
            venta=venta, producto=self.producto, cantidad=Decimal('300'),
            precio_unitario=Decimal('5000'), iva_alicuota=Decimal('21'),
            total=Decimal('1500000'))

        self.assertEqual(self._stock(), Decimal('700.00'))


class RobustezTests(StockBaseTestCase):

    def test_variedad_sin_producto_no_rompe(self):
        """Degradación silenciosa y deliberada: se confirma igual y no mueve stock."""
        self.burley.producto = None
        self.burley.save(update_fields=['producto'])

        romaneo = self._romaneo_confirmado(kilos='1000')

        self.assertEqual(romaneo.estado, RomaneoTabaco.CONFIRMADO)
        self.assertFalse(StockSucursal.objects.filter(producto=self.producto).exists())

    def test_el_stock_se_reconstruye_solo(self):
        """Aunque el caché quede mal, `recalcular_stock` lo repara: es un valor derivado."""
        self._romaneo_confirmado(kilos='1000')
        StockSucursal.objects.filter(producto=self.producto).update(cantidad=Decimal('99999'))

        self.assertEqual(self._stock(), Decimal('1000.00'))

    def test_el_recalculo_masivo_incluye_los_fardos(self):
        self._romaneo_confirmado(kilos='1000')
        StockSucursal.objects.filter(producto=self.producto).update(cantidad=Decimal('0'))

        diferencias = recalcular_stock_masivo(self.empresa.pk)

        self.assertTrue(any(d[0] == self.producto.pk and d[3] == Decimal('1000.00')
                            for d in diferencias))

    def test_no_regresion_de_los_terminos_del_core(self):
        """Los cuatro de siempre siguen dando idéntico con el término agrícola registrado."""
        otro = Producto.objects.create(empresa=self.empresa, detalle="PRODUCTO COMUN")
        tipo = TipoComprobante.objects.create(codigo='086', detalle='FACTURA A', signo=1)
        venta = Venta.objects.create(
            fecha=date(2026, 9, 15), tipo=tipo, punto=1, numero=2,
            cliente=self.productor, empresa=self.empresa, sucursal=self.sucursal,
            usuario=self.user, estado=0)
        VentaItem.objects.create(
            venta=venta, producto=otro, cantidad=Decimal('5'),
            precio_unitario=Decimal('100'), iva_alicuota=Decimal('21'), total=Decimal('500'))

        # Un producto ajeno al tabaco no se ve afectado por el término nuevo.
        self.assertEqual(recalcular_stock(otro.pk, self.sucursal.pk), Decimal('-5.00'))


class ConciliacionTests(StockBaseTestCase):

    def _fila(self):
        filas = stock_svc.conciliar(self.empresa.pk)
        return next(f for f in filas if f['variedad'] == self.burley and not f['sin_producto'])

    def test_conciliacion_en_cero(self):
        self._romaneo_confirmado(kilos='1000')

        fila = self._fila()

        self.assertEqual(fila['recibidos'], Decimal('1000.00'))
        self.assertEqual(fila['vendidos'], Decimal('0.00'))
        self.assertEqual(fila['esperado'], Decimal('1000.00'))
        self.assertEqual(fila['en_erp'], Decimal('1000.00'))
        self.assertEqual(fila['diferencia'], Decimal('0.00'))

    def test_conciliacion_con_venta(self):
        self._romaneo_confirmado(kilos='1000')
        tipo = TipoComprobante.objects.create(codigo='087', detalle='FACTURA A', signo=1)
        venta = Venta.objects.create(
            fecha=date(2026, 9, 15), tipo=tipo, punto=1, numero=3,
            cliente=self.productor, empresa=self.empresa, sucursal=self.sucursal,
            usuario=self.user, estado=0)
        VentaItem.objects.create(
            venta=venta, producto=self.producto, cantidad=Decimal('400'),
            precio_unitario=Decimal('1'), iva_alicuota=Decimal('21'), total=Decimal('400'))

        fila = self._fila()

        self.assertEqual(fila['vendidos'], Decimal('400.00'))
        self.assertEqual(fila['esperado'], Decimal('600.00'))
        self.assertEqual(fila['diferencia'], Decimal('0.00'))

    def test_conciliacion_detecta_diferencia(self):
        self._romaneo_confirmado(kilos='1000')
        StockSucursal.objects.filter(producto=self.producto).update(cantidad=Decimal('900'))

        fila = self._fila()

        self.assertEqual(fila['diferencia'], Decimal('100.00'))

    def test_conciliacion_señala_variedad_sin_producto(self):
        """El silencio se leería como 'está todo bien'."""
        self.burley.producto = None
        self.burley.save(update_fields=['producto'])
        self._romaneo_confirmado(kilos='1000')

        sin_producto = [f for f in stock_svc.conciliar(self.empresa.pk) if f['sin_producto']]

        self.assertTrue(sin_producto)
        self.assertEqual(sin_producto[0]['variedad'], self.burley)
        self.assertEqual(sin_producto[0]['recibidos'], Decimal('1000.00'))

    def test_un_borrador_no_entra_en_la_conciliacion(self):
        borrador = rom_svc.abrir_romaneo(
            empresa=self.empresa, sucursal=self.sucursal, productor=self.productor,
            variedad=self.burley, campania=self.campania, fecha=date(2026, 9, 1),
            usuario=self.user)
        rom_svc.agregar_fardo(borrador, clase=self.b1f, kilos=Decimal('500'), usuario=self.user)
        self._romaneo_confirmado(kilos='1000')

        self.assertEqual(self._fila()['recibidos'], Decimal('1000.00'))


class ComandoProductosTests(StockBaseTestCase):

    def test_crea_y_vincula_las_variedades_sin_producto(self):
        self.burley.producto = None
        self.burley.save(update_fields=['producto'])
        VariedadTabaco.objects.create(empresa=self.empresa, codigo=2, detalle='VIRGINIA')

        call_command('crear_productos_tabaco', empresa=self.empresa.pk, verbosity=0)

        self.burley.refresh_from_db()
        virginia = VariedadTabaco.objects.get(empresa=self.empresa, codigo=2)
        self.assertIsNotNone(self.burley.producto)
        self.assertIsNotNone(virginia.producto)
        self.assertEqual(virginia.producto.detalle, 'TABACO VIRGINIA')
        self.assertEqual(virginia.producto.unidad_venta, 'KG')
        self.assertEqual(virginia.producto.alic_iva, Decimal('21.00'))

    def test_es_idempotente(self):
        self.burley.producto = None
        self.burley.save(update_fields=['producto'])

        call_command('crear_productos_tabaco', empresa=self.empresa.pk, verbosity=0)
        antes = Producto.objects.filter(empresa=self.empresa).count()
        call_command('crear_productos_tabaco', empresa=self.empresa.pk, verbosity=0)

        self.assertEqual(Producto.objects.filter(empresa=self.empresa).count(), antes)

    def test_respeta_un_producto_ya_asignado(self):
        propio = Producto.objects.create(empresa=self.empresa, detalle="MI TABACO")
        self.burley.producto = propio
        self.burley.save(update_fields=['producto'])

        call_command('crear_productos_tabaco', empresa=self.empresa.pk, verbosity=0)

        self.burley.refresh_from_db()
        self.assertEqual(self.burley.producto, propio)

    def test_dry_run_no_escribe(self):
        self.burley.producto = None
        self.burley.save(update_fields=['producto'])

        call_command('crear_productos_tabaco', empresa=self.empresa.pk, dry_run=True, verbosity=0)

        self.burley.refresh_from_db()
        self.assertIsNone(self.burley.producto)


class PantallaConciliacionTests(StockBaseTestCase):

    def setUp(self):
        super().setUp()
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)
        sesion = self.client.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion.save()

    def test_renderiza_y_avisa_que_todo_concilia(self):
        from django.urls import reverse
        self._romaneo_confirmado(kilos='1000')

        r = self.client.get(reverse('agro_stock_conciliacion'))

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Todo concilia')
        self.assertContains(r, 'TABACO BURLEY')

    def test_avisa_cuando_hay_diferencia(self):
        from django.urls import reverse
        self._romaneo_confirmado(kilos='1000')
        StockSucursal.objects.filter(producto=self.producto).update(cantidad=Decimal('900'))

        r = self.client.get(reverse('agro_stock_conciliacion'))

        self.assertContains(r, 'Hay diferencias')

    def test_avisa_variedad_sin_producto(self):
        from django.urls import reverse
        self.burley.producto = None
        self.burley.save(update_fields=['producto'])

        r = self.client.get(reverse('agro_stock_conciliacion'))

        self.assertContains(r, 'sin producto de stock asignado')

    def test_recalcular_corrige_la_diferencia(self):
        from django.urls import reverse
        self._romaneo_confirmado(kilos='1000')
        StockSucursal.objects.filter(producto=self.producto).update(cantidad=Decimal('900'))

        r = self.client.post(reverse('agro_stock_recalcular'))

        self.assertEqual(r.status_code, 302)
        fila = StockSucursal.objects.get(producto=self.producto, sucursal=self.sucursal)
        self.assertEqual(fila.cantidad, Decimal('1000.00'))

    def test_el_menu_muestra_la_conciliacion(self):
        from django.urls import reverse
        from verticalidades.agricola.core_agricola.models import EmpresaVertical
        EmpresaVertical.objects.create(empresa=self.empresa, hace_tabaco=True)

        r = self.client.get(reverse('agro_stock_conciliacion'))

        self.assertContains(r, reverse('agro_stock_conciliacion'))
