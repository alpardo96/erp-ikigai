"""Plan 080 — registros enchufables de cuenta corriente e imputación de Órdenes de Pago.

Igual que en el test de stock, lo primero que se prueba es la NO REGRESIÓN: con los registros
vacíos —el estado de cualquier empresa sin verticalidades enchufadas— el saldo de un tercero y
lo pendiente de aplicar de una OP se calculan exactamente como antes del Plan 080.

Los orígenes de prueba se registran sobre modelos que ya existen (`Compra` y
`OrdenPagoAplicacion`) para no inventar un modelo de mentira que exigiría migraciones. Un
término sobre `Compra` con signo +1 compensa exactamente al término 'compras' que ya está
cableado: si el mecanismo funciona, el saldo vuelve al inicial.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.test import TestCase
from django.utils import timezone

from contable.services import saldos as saldos_service
from contable.services.saldos import (
    pendiente_de_aplicar_op, recalcular_saldo_cliente_proveedor,
    registrar_aplicacion_op, registrar_termino_ctacte,
)
from empresas.models import Ejercicio, Empresa, Sucursal
from facturacion.models import ClienteProveedor, Compra, TipoComprobante

User = get_user_model()


class Plan080TerminosCtaCteTestCase(TestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(username="plan080_ctacte", password="pw")
        self.empresa = Empresa.objects.create(nombre="EMPRESA PLAN 080", cuit="30123456789")
        self.sucursal = Sucursal.objects.create(empresa=self.empresa, nombre="CENTRAL")
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa, ejercicio="Ejercicio Plan 080",
            inicio=timezone.now().date() - timezone.timedelta(days=30),
            cierre=timezone.now().date() + timezone.timedelta(days=30),
        )
        self.tipo = TipoComprobante.objects.create(codigo="081", detalle="FACTURA A", signo=1)
        self.proveedor = ClienteProveedor.objects.create(
            razon_social="PROVEEDOR PLAN 080", cuit="30111111112", tipo_entidad=2,
            saldo_inicial=Decimal("0.00"), saldo=Decimal("0.00"), empresa=self.empresa,
        )

        saldos_service._TERMINOS_CTACTE_EXTRA.clear()
        saldos_service._APLICACIONES_OP_EXTRA.clear()
        self.addCleanup(saldos_service._TERMINOS_CTACTE_EXTRA.clear)
        self.addCleanup(saldos_service._APLICACIONES_OP_EXTRA.clear)

    # -- helpers ------------------------------------------------------------

    def _crear_compra(self, total="1000.00", numero=1):
        return Compra.objects.create(
            fecha=timezone.now().date(), tipo=self.tipo, punto=1, numero=numero,
            proveedor=self.proveedor, empresa=self.empresa, sucursal=self.sucursal,
            ejercicio=self.ejercicio, usuario=self.usuario, total=Decimal(total),
        )

    def _crear_op(self, total="400.00", numero=1):
        from tesoreria.models import OrdenPago
        return OrdenPago.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, ejercicio=self.ejercicio,
            proveedor=self.proveedor, fecha=timezone.now().date(), punto=1, numero=numero,
            total=Decimal(total),
        )

    def _termino(self, nombre='test_plan080', signo=1, excluir=None):
        return {
            'nombre': nombre,
            'modelo': Compra,
            'campo_entidad': 'proveedor',
            'campo_empresa': 'empresa_id',
            'campo_importe': 'total',
            'signo': signo,
            'excluir': excluir,
        }

    def _saldo(self):
        return recalcular_saldo_cliente_proveedor(self.proveedor.pk)

    # -- no regresión -------------------------------------------------------

    def test_registro_vacio_no_altera_el_saldo(self):
        """Sin términos registrados, una compra de 1.000 deja el saldo del proveedor en −1.000."""
        self._crear_compra("1000.00")
        self.assertEqual(len(saldos_service._TERMINOS_CTACTE_EXTRA), 0)
        self.assertEqual(self._saldo(), Decimal("-1000.00"))

    def test_registro_vacio_no_altera_el_pendiente_de_op(self):
        from tesoreria.models import OrdenPagoAplicacion

        compra = self._crear_compra("1000.00")
        op = self._crear_op("400.00")
        OrdenPagoAplicacion.objects.create(
            orden_pago=op, compra=compra, importe=Decimal("250.00"),
        )
        self.assertEqual(pendiente_de_aplicar_op(op), Decimal("150.00"))

    # -- mecanismo de cuenta corriente --------------------------------------

    def test_termino_extra_participa_del_saldo(self):
        """El término +1 compensa al término 'compras': −1.000 + 1.000 = 0."""
        self._crear_compra("1000.00")
        self.assertEqual(self._saldo(), Decimal("-1000.00"))

        registrar_termino_ctacte(self._termino())
        self.assertEqual(self._saldo(), Decimal("0.00"))

    def test_signo_negativo_genera_deuda(self):
        """Es el signo que usará la liquidación de tabaco: mismo que una compra."""
        self._crear_compra("1000.00")
        registrar_termino_ctacte(self._termino(signo=-1))
        self.assertEqual(self._saldo(), Decimal("-2000.00"))

    def test_saldo_inicial_se_respeta(self):
        self.proveedor.saldo_inicial = Decimal("500.00")
        self.proveedor.save(update_fields=['saldo_inicial'])
        self._crear_compra("1000.00")
        registrar_termino_ctacte(self._termino())
        self.assertEqual(self._saldo(), Decimal("500.00"))

    def test_excluir_se_respeta(self):
        compra = self._crear_compra("1000.00")
        registrar_termino_ctacte(self._termino(excluir=Q(pk=compra.pk)))
        self.assertEqual(self._saldo(), Decimal("-1000.00"))

    def test_excluir_none_no_rompe(self):
        """`excluir=None` es válido: significa 'no excluyas nada'."""
        self._crear_compra("1000.00")
        registrar_termino_ctacte(self._termino(excluir=None))
        self.assertEqual(self._saldo(), Decimal("0.00"))

    def test_filtra_por_empresa(self):
        """El término no puede arrastrar comprobantes de otra empresa."""
        otra = Empresa.objects.create(nombre="OTRA EMPRESA", cuit="30999999998")
        otra_suc = Sucursal.objects.create(empresa=otra, nombre="CENTRAL OTRA")
        otro_eje = Ejercicio.objects.create(
            empresa=otra, ejercicio="Otro",
            inicio=timezone.now().date() - timezone.timedelta(days=30),
            cierre=timezone.now().date() + timezone.timedelta(days=30),
        )
        Compra.objects.create(
            fecha=timezone.now().date(), tipo=self.tipo, punto=9, numero=99,
            proveedor=self.proveedor, empresa=otra, sucursal=otra_suc,
            ejercicio=otro_eje, usuario=self.usuario, total=Decimal("7777.00"),
        )
        self._crear_compra("1000.00")
        registrar_termino_ctacte(self._termino())
        self.assertEqual(self._saldo(), Decimal("0.00"))

    # -- mecanismo de imputación de OP --------------------------------------

    def test_aplicacion_extra_reduce_el_pendiente(self):
        """Registrar `OrdenPagoAplicacion` como origen extra la cuenta dos veces: 400 − 250 − 250."""
        from tesoreria.models import OrdenPagoAplicacion

        compra = self._crear_compra("1000.00")
        op = self._crear_op("400.00")
        OrdenPagoAplicacion.objects.create(
            orden_pago=op, compra=compra, importe=Decimal("250.00"),
        )
        self.assertEqual(pendiente_de_aplicar_op(op), Decimal("150.00"))

        registrar_aplicacion_op({
            'nombre': 'test_plan080',
            'modelo': OrdenPagoAplicacion,
            'campo_op': 'orden_pago',
            'campo_importe': 'importe',
        })
        self.assertEqual(pendiente_de_aplicar_op(op), Decimal("-100.00"))

    def test_op_anulada_sigue_devolviendo_cero(self):
        from tesoreria.models import OrdenPagoAplicacion

        op = self._crear_op("400.00")
        op.anulado = True
        op.save(update_fields=['anulado'])

        registrar_aplicacion_op({
            'nombre': 'test_plan080',
            'modelo': OrdenPagoAplicacion,
            'campo_op': 'orden_pago',
            'campo_importe': 'importe',
        })
        self.assertEqual(pendiente_de_aplicar_op(op), Decimal("0.00"))

    # -- integridad de los registros ---------------------------------------

    def test_alta_repetida_no_duplica(self):
        """La protección crítica: sin ella, `ready()` dos veces contaría la deuda dos veces."""
        self._crear_compra("1000.00")
        registrar_termino_ctacte(self._termino())
        registrar_termino_ctacte(self._termino())

        self.assertEqual(len(saldos_service._TERMINOS_CTACTE_EXTRA), 1)
        self.assertEqual(self._saldo(), Decimal("0.00"))

    def test_termino_incompleto_falla_al_registrar(self):
        incompleto = self._termino()
        del incompleto['campo_importe']

        with self.assertRaises(ValueError):
            registrar_termino_ctacte(incompleto)
        self.assertEqual(len(saldos_service._TERMINOS_CTACTE_EXTRA), 0)

    def test_excluir_mal_tipeado_falla_al_registrar(self):
        malo = self._termino()
        malo['excluir'] = "estado=1"

        with self.assertRaises(ValueError):
            registrar_termino_ctacte(malo)
        self.assertEqual(len(saldos_service._TERMINOS_CTACTE_EXTRA), 0)

    def test_signo_invalido_falla_al_registrar(self):
        """Un signo 0 o 2 daría un saldo silenciosamente mal, sin excepción en ningún lado."""
        malo = self._termino(signo=0)

        with self.assertRaises(ValueError):
            registrar_termino_ctacte(malo)
        self.assertEqual(len(saldos_service._TERMINOS_CTACTE_EXTRA), 0)

    def test_aplicacion_incompleta_falla_al_registrar(self):
        with self.assertRaises(ValueError):
            registrar_aplicacion_op({'nombre': 'x', 'modelo': Compra})
        self.assertEqual(len(saldos_service._APLICACIONES_OP_EXTRA), 0)
