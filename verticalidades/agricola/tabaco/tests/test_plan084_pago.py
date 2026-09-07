"""Plan 084 — pago al productor y retención de Ganancias.

Lo que se protege, en orden:

1. Que el acumulado mensual funcione: el segundo pago del mes descuenta lo ya retenido, y otro mes
   arranca de cero.
2. Que la retención sea un MEDIO DE PAGO, de modo que el asiento del core balancee solo.
3. Que el saldo de la liquidación se DERIVE de las imputaciones.
4. Que la OP no quede figurando como "sin aplicar" (Plan 080).
5. Que anular revierta todo, incluido el acumulado del mes.
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from contable.models import Asiento, AsientoLinea
from contable.services.saldos import pendiente_de_aplicar_op, recalcular_saldo_cliente_proveedor
from tesoreria.models import MedioPago, MovimientoCajaDetalle, OrdenPago
from verticalidades.agricola.tabaco.models import (LiquidacionPago, LiquidacionTabaco,
                                                   RetencionPago)
from verticalidades.agricola.tabaco.services import liquidacion as liq_svc
from verticalidades.agricola.tabaco.services import pago as pago_svc

from .test_plan083_liquidacion import LiquidacionBaseTestCase


class PagoBaseTestCase(LiquidacionBaseTestCase):
    """Sobre el escenario del Plan 083, agrega la caja y el efectivo para poder pagar."""

    def setUp(self):
        super().setUp()
        self.cta_caja = self._cuenta('111001', 'CAJA', 'A')
        self.efectivo = MedioPago.objects.create(
            empresa=self.empresa, codigo='EFE-ARS', nombre='EFECTIVO',
            categoria='EFE', cuenta_contable=self.cta_caja)

    def _liquidacion(self, productor=None, kilos='1000', fecha=date(2026, 9, 6)):
        """Liquidación confirmada. Con 1.000 kg a $1.000: neto 1.000.000, total 1.087.000."""
        productor = productor or self.productor
        romaneo = self._romaneo(productor, kilos=kilos)
        liq = liq_svc.preparar_liquidacion(
            empresa=self.empresa, sucursal=self.sucursal, productor=productor,
            romaneos=[romaneo], fecha=fecha, usuario=self.user)
        return liq_svc.confirmar_liquidacion(liq, self.user)

    def _pagar(self, liquidaciones, efectivo, fecha=date(2026, 9, 10), productor=None):
        return pago_svc.pagar_liquidaciones(
            empresa=self.empresa, sucursal=self.sucursal,
            productor=productor or self.productor, liquidaciones=liquidaciones,
            medios=[{'medio_pago': self.efectivo, 'importe': Decimal(efectivo)}],
            fecha=fecha, usuario=self.user)


class RetencionGananciasTests(PagoBaseTestCase):
    """Neto 1.000.000 · MNI 224.000 · 2 % → (1.000.000 − 224.000) × 2 % = 15.520."""

    def test_sobre_el_minimo_retiene(self):
        calculo = pago_svc.calcular_ganancias(
            empresa=self.empresa, productor=self.productor,
            base_del_pago=Decimal('1000000'), fecha=date(2026, 9, 10))

        self.assertEqual(calculo['minimo_no_imponible'], Decimal('224000.00'))
        self.assertEqual(calculo['retencion_del_mes'], Decimal('15520.00'))
        self.assertEqual(calculo['importe'], Decimal('15520.00'))

    def test_bajo_el_minimo_no_retiene(self):
        calculo = pago_svc.calcular_ganancias(
            empresa=self.empresa, productor=self.productor,
            base_del_pago=Decimal('200000'), fecha=date(2026, 9, 10))

        self.assertEqual(calculo['importe'], Decimal('0.00'))

    def test_justo_en_el_minimo_no_retiene(self):
        calculo = pago_svc.calcular_ganancias(
            empresa=self.empresa, productor=self.productor,
            base_del_pago=Decimal('224000'), fecha=date(2026, 9, 10))

        self.assertEqual(calculo['importe'], Decimal('0.00'))

    def test_monotributista_no_sufre_ganancias(self):
        calculo = pago_svc.calcular_ganancias(
            empresa=self.empresa, productor=self.monotributista,
            base_del_pago=Decimal('1000000'), fecha=date(2026, 9, 10))

        self.assertIsNone(calculo)

    def test_el_acumulado_mensual_descuenta_lo_ya_retenido(self):
        """La razón de ser del régimen: el segundo pago del mes no vuelve a retener lo mismo."""
        primera = self._liquidacion()
        self._pagar([primera], primera.saldo - Decimal('15520.00'))

        # Segundo pago del MISMO mes: base acumulada 2.000.000.
        calculo = pago_svc.calcular_ganancias(
            empresa=self.empresa, productor=self.productor,
            base_del_pago=Decimal('1000000'), fecha=date(2026, 9, 20))

        self.assertEqual(calculo['base_acumulada'], Decimal('2000000.00'))
        # (2.000.000 − 224.000) × 2 % = 35.520
        self.assertEqual(calculo['retencion_del_mes'], Decimal('35520.00'))
        self.assertEqual(calculo['retenido_previo'], Decimal('15520.00'))
        self.assertEqual(calculo['importe'], Decimal('20000.00'))

    def test_el_acumulado_no_cruza_de_mes(self):
        primera = self._liquidacion()
        self._pagar([primera], primera.saldo - Decimal('15520.00'))

        calculo = pago_svc.calcular_ganancias(
            empresa=self.empresa, productor=self.productor,
            base_del_pago=Decimal('1000000'), fecha=date(2026, 10, 5))

        self.assertEqual(calculo['base_acumulada'], Decimal('1000000.00'))
        self.assertEqual(calculo['retenido_previo'], Decimal('0.00'))
        self.assertEqual(calculo['importe'], Decimal('15520.00'))

    def test_el_acumulado_es_por_productor(self):
        primera = self._liquidacion()
        self._pagar([primera], primera.saldo - Decimal('15520.00'))

        otro = self._liquidacion(productor=self.monotributista)
        calculo = pago_svc.calcular_ganancias(
            empresa=self.empresa, productor=otro.productor,
            base_del_pago=Decimal('1000000'), fecha=date(2026, 9, 20))

        self.assertIsNone(calculo)   # monotributista: no aplica


class PagoTests(PagoBaseTestCase):

    def test_pago_total_deja_la_liquidacion_en_cero(self):
        liq = self._liquidacion()
        # Total 1.087.000; se retienen 15.520, se entregan 1.071.480.
        op = self._pagar([liq], Decimal('1071480.00'))

        liq.refresh_from_db()
        self.assertEqual(op.total, Decimal('1087000.00'))
        self.assertEqual(liq.pagado, Decimal('1087000.00'))
        self.assertEqual(liq.saldo, Decimal('0.00'))

    def test_pago_parcial_deja_saldo(self):
        liq = self._liquidacion()
        self._pagar([liq], Decimal('500000.00'))

        liq.refresh_from_db()
        # 500.000 entregados + 15.520 retenidos
        self.assertEqual(liq.pagado, Decimal('515520.00'))
        self.assertEqual(liq.saldo, Decimal('571480.00'))

    def test_no_se_paga_de_mas(self):
        liq = self._liquidacion()

        with self.assertRaises(ValidationError) as ctx:
            self._pagar([liq], Decimal('2000000.00'))
        self.assertIn('supera el saldo', str(ctx.exception))

    def test_la_retencion_es_un_medio_de_pago(self):
        liq = self._liquidacion()
        op = self._pagar([liq], Decimal('1071480.00'))

        detalles = MovimientoCajaDetalle.objects.filter(movimiento_caja__orden_pago=op)
        por_categoria = {d.medio_pago.categoria: d.importe for d in detalles}

        self.assertEqual(por_categoria['EFE'], Decimal('1071480.00'))
        self.assertEqual(por_categoria['RET'], Decimal('15520.00'))
        # Y su cuenta salió del concepto del maestro, no de una configuración aparte.
        ret = detalles.get(medio_pago__categoria='RET')
        self.assertEqual(ret.medio_pago.cuenta_contable, self.cta_gcias)

    def test_el_asiento_de_la_op_balancea(self):
        liq = self._liquidacion()
        op = self._pagar([liq], Decimal('1071480.00'))

        lineas = {l.cuenta.jerarquia: (l.debe, l.haber)
                  for l in AsientoLinea.objects.filter(asiento_id=op.asiento_id)}

        self.assertEqual(lineas['211001'], (Decimal('1087000.00'), Decimal('0.00')))  # productor
        self.assertEqual(lineas['111001'], (Decimal('0.00'), Decimal('1071480.00')))  # caja
        self.assertEqual(lineas['214005'], (Decimal('0.00'), Decimal('15520.00')))    # ret gcias
        self.assertEqual(sum(d for d, _ in lineas.values()),
                         sum(h for _, h in lineas.values()))

    def test_la_op_no_queda_sin_aplicar(self):
        """Plan 080: sin el punto de extensión, esta OP figuraría eternamente como no imputada."""
        liq = self._liquidacion()
        op = self._pagar([liq], Decimal('1071480.00'))

        self.assertEqual(pendiente_de_aplicar_op(op), Decimal('0.00'))

    def test_el_saldo_del_productor_vuelve_a_cero(self):
        liq = self._liquidacion()
        self.productor.refresh_from_db()
        self.assertEqual(self.productor.saldo, -liq.total)

        self._pagar([liq], Decimal('1071480.00'))

        self.assertEqual(recalcular_saldo_cliente_proveedor(self.productor.pk), Decimal('0.00'))

    def test_se_emite_el_certificado(self):
        liq = self._liquidacion()
        op = self._pagar([liq], Decimal('1071480.00'))

        cert = RetencionPago.objects.get(orden_pago=op)
        self.assertEqual(cert.nro_certificado, 1)
        self.assertEqual(cert.codigo, 'RET-GCIAS')
        self.assertEqual(cert.regimen, '78')
        self.assertEqual(cert.periodo, '202609')
        self.assertEqual(cert.base_acumulada, Decimal('1000000.00'))
        self.assertEqual(cert.minimo_no_imponible, Decimal('224000.00'))
        self.assertEqual(cert.importe, Decimal('15520.00'))

    def test_los_certificados_se_numeran_correlativos(self):
        primera = self._liquidacion()
        self._pagar([primera], primera.saldo - Decimal('15520.00'))
        segunda = self._liquidacion()
        self._pagar([segunda], Decimal('100000.00'), fecha=date(2026, 9, 20))

        self.assertEqual(
            list(RetencionPago.objects.order_by('nro_certificado')
                 .values_list('nro_certificado', flat=True)), [1, 2])

    def test_paga_varias_liquidaciones_de_la_mas_vieja_a_la_mas_nueva(self):
        vieja = self._liquidacion(fecha=date(2026, 9, 1))
        nueva = self._liquidacion(fecha=date(2026, 9, 5))

        # Base 2.000.000 → retención del mes 35.520. Se entregan 100.000.
        op = self._pagar([vieja, nueva], Decimal('100000.00'))

        imputaciones = {p.liquidacion_id: p.importe
                        for p in LiquidacionPago.objects.filter(orden_pago=op)}
        self.assertEqual(imputaciones[vieja.pk], Decimal('135520.00'))
        self.assertNotIn(nueva.pk, imputaciones)          # no alcanzó para la segunda

    def test_no_se_paga_una_liquidacion_anulada(self):
        liq = self._liquidacion()
        liq_svc.anular_liquidacion(liq, "Error", self.user)

        with self.assertRaises(ValidationError) as ctx:
            self._pagar([liq], Decimal('1000.00'))
        self.assertIn('no se puede pagar', str(ctx.exception))

    def test_una_op_cancela_comprobantes_de_un_solo_productor(self):
        mia = self._liquidacion()
        ajena = self._liquidacion(productor=self.monotributista)

        with self.assertRaises(ValidationError) as ctx:
            self._pagar([mia, ajena], Decimal('1000.00'))
        self.assertIn('otro productor', str(ctx.exception))

    def test_exige_medios_de_pago(self):
        liq = self._liquidacion()

        with self.assertRaises(ValidationError) as ctx:
            pago_svc.pagar_liquidaciones(
                empresa=self.empresa, sucursal=self.sucursal, productor=self.productor,
                liquidaciones=[liq], medios=[], fecha=date(2026, 9, 10), usuario=self.user)
        self.assertIn('al menos un medio de pago', str(ctx.exception))

    def test_pendientes_lista_solo_las_que_tienen_saldo(self):
        pagada = self._liquidacion()
        self._pagar([pagada], Decimal('1071480.00'))
        con_saldo = self._liquidacion(fecha=date(2026, 9, 20))

        pendientes = list(pago_svc.liquidaciones_pendientes(self.empresa.pk, self.productor))

        self.assertIn(con_saldo, pendientes)
        self.assertNotIn(pagada, pendientes)


class AnulacionPagoTests(PagoBaseTestCase):

    def test_anular_restituye_el_saldo(self):
        liq = self._liquidacion()
        op = self._pagar([liq], Decimal('1071480.00'))

        pago_svc.anular_pago(op, "Error de carga", self.user)

        liq.refresh_from_db()
        self.assertEqual(liq.pagado, Decimal('0.00'))
        self.assertEqual(liq.saldo, liq.total)
        self.assertEqual(recalcular_saldo_cliente_proveedor(self.productor.pk), -liq.total)

    def test_anular_marca_el_asiento_sin_borrarlo(self):
        liq = self._liquidacion()
        op = self._pagar([liq], Decimal('1071480.00'))
        asiento_id = op.asiento_id

        pago_svc.anular_pago(op, "Error", self.user)

        self.assertTrue(Asiento.objects.get(pk=asiento_id).anulado)
        self.assertTrue(AsientoLinea.objects.filter(asiento_id=asiento_id).exists())

    def test_anular_baja_el_acumulado_del_mes(self):
        """El acumulado se deriva de los certificados vigentes: se corrige solo."""
        liq = self._liquidacion()
        op = self._pagar([liq], Decimal('1071480.00'))

        pago_svc.anular_pago(op, "Error", self.user)

        calculo = pago_svc.calcular_ganancias(
            empresa=self.empresa, productor=self.productor,
            base_del_pago=Decimal('1000000'), fecha=date(2026, 9, 20))
        self.assertEqual(calculo['base_acumulada'], Decimal('1000000.00'))
        self.assertEqual(calculo['retenido_previo'], Decimal('0.00'))
        self.assertEqual(calculo['importe'], Decimal('15520.00'))

    def test_anular_permite_volver_a_pagar(self):
        liq = self._liquidacion()
        op = self._pagar([liq], Decimal('1071480.00'))
        pago_svc.anular_pago(op, "Error", self.user)

        liq.refresh_from_db()
        nueva_op = self._pagar([liq], Decimal('1071480.00'), fecha=date(2026, 9, 12))

        liq.refresh_from_db()
        self.assertEqual(liq.saldo, Decimal('0.00'))
        self.assertEqual(pendiente_de_aplicar_op(nueva_op), Decimal('0.00'))

    def test_anular_exige_motivo(self):
        liq = self._liquidacion()
        op = self._pagar([liq], Decimal('1071480.00'))

        with self.assertRaises(ValidationError):
            pago_svc.anular_pago(op, "   ", self.user)

    def test_anular_es_idempotente(self):
        liq = self._liquidacion()
        op = self._pagar([liq], Decimal('1071480.00'))

        pago_svc.anular_pago(op, "Primero", self.user)
        pago_svc.anular_pago(op, "Segundo", self.user)

        liq.refresh_from_db()
        self.assertEqual(liq.saldo, liq.total)

    def test_no_se_anula_una_liquidacion_con_pagos(self):
        liq = self._liquidacion()
        self._pagar([liq], Decimal('1071480.00'))
        liq.refresh_from_db()

        with self.assertRaises(ValidationError) as ctx:
            liq_svc.anular_liquidacion(liq, "Error", self.user)
        self.assertIn('Orden de Pago', str(ctx.exception))


class AislamientoPagoTests(PagoBaseTestCase):

    def test_no_se_paga_una_liquidacion_de_otra_empresa(self):
        from empresas.models import Empresa, Sucursal
        otra = Empresa.objects.create(nombre="OTRO ACOPIO", cuit="30999999998")
        otra_suc = Sucursal.objects.create(empresa=otra, nombre="C")
        ajena = LiquidacionTabaco.objects.create(
            empresa=otra, sucursal=otra_suc, productor=self.productor,
            fecha=date(2026, 9, 6), estado=LiquidacionTabaco.CONFIRMADA,
            total=Decimal('1000'), saldo=Decimal('1000'))

        with self.assertRaises(ValidationError) as ctx:
            self._pagar([ajena], Decimal('100.00'))
        self.assertIn('otra empresa', str(ctx.exception))
