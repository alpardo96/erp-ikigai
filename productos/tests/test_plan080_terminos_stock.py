"""Plan 080 — registro enchufable de términos de stock.

Dos cosas se prueban acá, y la primera importa más que la segunda:

1. NO REGRESIÓN: con el registro vacío —el estado de cualquier empresa sin verticalidades
   enchufadas— el stock se calcula exactamente igual que antes del Plan 080.
2. El mecanismo: un término registrado participa del cálculo, el alta es idempotente y el
   `excluir` se respeta.

Para no crear un modelo de mentira (que exigiría migraciones), los términos de prueba se
registran sobre `VentaItem` con signo +1: si el mecanismo funciona, compensan exactamente al
término 'ventas' que ya existe y el stock queda en cero.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.test import TestCase

from empresas.models import Empresa, Sucursal
from facturacion.models import ClienteProveedor, TipoComprobante, Venta, VentaItem
from productos.models import Producto, StockSucursal
from productos.services import stock_service
from productos.services.stock_service import (
    recalcular_stock, recalcular_stock_masivo, registrar_termino_stock,
)

User = get_user_model()


class Plan080TerminosStockTestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='plan080_user', password='password')
        self.empresa = Empresa.objects.create(nombre="Empresa Plan 080")
        self.sucursal = Sucursal.objects.create(nombre="Central", empresa=self.empresa)
        self.cliente = ClienteProveedor.objects.create(
            razon_social="Cliente Plan 080", tipo_entidad=1, empresa=self.empresa,
        )
        self.tipo_cbte = TipoComprobante.objects.create(codigo="080", detalle="Factura A")
        self.producto = Producto.objects.create(detalle="Producto Plan 080", empresa=self.empresa)
        self.venta = Venta.objects.create(
            fecha=date.today(), tipo=self.tipo_cbte, punto=1, numero=80001,
            cliente=self.cliente, empresa=self.empresa, sucursal=self.sucursal,
            usuario=self.user, estado=0,
        )
        # El registro es estado de módulo: se limpia antes y después para no contaminar al
        # resto de la suite si un test falla a mitad de camino.
        # Se GUARDA y se RESTAURA, no se vacía y listo: las verticalidades instaladas se
        # anuncian una sola vez en `ready()`. Vaciar el registro dejaría sin su término a los
        # tests que corran después en la misma corrida.
        self._previos = list(stock_service._TERMINOS_EXTRA)
        stock_service._TERMINOS_EXTRA.clear()
        self.addCleanup(self._restaurar)

    def _restaurar(self):
        stock_service._TERMINOS_EXTRA[:] = self._previos

    # -- helpers ------------------------------------------------------------

    def _crear_item(self, cantidad="5.00"):
        return VentaItem.objects.create(
            venta=self.venta, producto=self.producto, cantidad=Decimal(cantidad),
            precio_unitario=Decimal("100.00"), iva_alicuota=Decimal("21.00"),
            total=Decimal(cantidad) * Decimal("100.00"),
        )

    def _termino(self, nombre='test_plan080', excluir=None):
        return {
            'nombre': nombre,
            'modelo': VentaItem,
            'signo': 1,
            'cantidad': 'cantidad',
            'producto': 'producto_id',
            'sucursal': 'venta__sucursal_id',
            'signo_cbte': None,
            'excluir': excluir if excluir is not None else Q(pk__in=[]),
        }

    def _stock(self):
        return recalcular_stock(self.producto.pk, self.sucursal.pk)

    # -- no regresión -------------------------------------------------------

    def test_registro_vacio_no_altera_el_calculo(self):
        """Sin términos registrados, una venta de 5 sigue dejando el stock en −5."""
        self._crear_item("5.00")
        self.assertEqual(len(stock_service._TERMINOS_EXTRA), 0)
        self.assertEqual(self._stock(), Decimal("-5.00"))

    def test_registro_vacio_no_altera_el_masivo(self):
        self._crear_item("5.00")
        self._stock()
        self.assertEqual(recalcular_stock_masivo(self.empresa.pk), [])

    # -- mecanismo ----------------------------------------------------------

    def test_termino_extra_participa_del_calculo(self):
        """El término +1 compensa al término 'ventas': −5 + 5 = 0."""
        self._crear_item("5.00")
        self.assertEqual(self._stock(), Decimal("-5.00"))

        registrar_termino_stock(self._termino())
        self.assertEqual(self._stock(), Decimal("0.00"))

    def test_termino_extra_participa_del_masivo(self):
        """`recalcular_stock_masivo()` itera la misma lista: hereda la extensión sin tocarlo."""
        self._crear_item("5.00")
        self._stock()                                   # deja cantidad = −5

        registrar_termino_stock(self._termino())
        diferencias = recalcular_stock_masivo(self.empresa.pk)

        self.assertEqual(len(diferencias), 1)
        _pid, _sid, antes, despues = diferencias[0]
        self.assertEqual(antes, Decimal("-5.00"))
        self.assertEqual(despues, Decimal("0.00"))

    def test_excluir_se_respeta(self):
        """Con el ítem excluido, el término no aporta nada y el stock queda en −5."""
        item = self._crear_item("5.00")
        registrar_termino_stock(self._termino(excluir=Q(pk=item.pk)))
        self.assertEqual(self._stock(), Decimal("-5.00"))

    # -- integridad del registro -------------------------------------------

    def test_alta_repetida_no_duplica(self):
        """Es la protección crítica: `ready()` puede correr dos veces y el stock se contaría doble."""
        self._crear_item("5.00")
        registrar_termino_stock(self._termino())
        registrar_termino_stock(self._termino())        # mismo nombre

        self.assertEqual(len(stock_service._TERMINOS_EXTRA), 1)
        self.assertEqual(self._stock(), Decimal("0.00"))

    def test_distinto_nombre_si_se_registra(self):
        self._crear_item("5.00")
        registrar_termino_stock(self._termino(nombre='uno'))
        registrar_termino_stock(self._termino(nombre='dos'))

        self.assertEqual(len(stock_service._TERMINOS_EXTRA), 2)
        self.assertEqual(self._stock(), Decimal("5.00"))     # −5 + 5 + 5

    def test_termino_incompleto_falla_al_registrar(self):
        """Mejor un ValueError al arrancar que un stock silenciosamente mal calculado."""
        incompleto = self._termino()
        del incompleto['sucursal']

        with self.assertRaises(ValueError):
            registrar_termino_stock(incompleto)
        self.assertEqual(len(stock_service._TERMINOS_EXTRA), 0)

    def test_excluir_mal_tipeado_falla_al_registrar(self):
        """Un `excluir` que no es Q reventaría dentro de `recalcular_stock()`, tarde y para todos."""
        malo = self._termino()
        malo['excluir'] = "venta__estado=1"

        with self.assertRaises(ValueError):
            registrar_termino_stock(malo)
        self.assertEqual(len(stock_service._TERMINOS_EXTRA), 0)

    def test_excluir_none_se_normaliza(self):
        """`None` es una forma legítima de decir 'no excluyas nada'."""
        self._crear_item("5.00")
        termino = self._termino()
        termino['excluir'] = None
        registrar_termino_stock(termino)

        self.assertEqual(self._stock(), Decimal("0.00"))

    def test_stock_sucursal_se_persiste(self):
        self._crear_item("5.00")
        registrar_termino_stock(self._termino())
        self._stock()

        registro = StockSucursal.objects.get(producto=self.producto, sucursal=self.sucursal)
        self.assertEqual(registro.cantidad, Decimal("0.00"))
