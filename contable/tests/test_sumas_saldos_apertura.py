from datetime import date
from decimal import Decimal
from django.test import TestCase

from empresas.models import Empresa, Ejercicio
from contable.models import Cuenta, Asiento, AsientoLinea
from contable.views_htmx import _calcular_balance


class SumasSaldosAperturaTest(TestCase):
    def setUp(self):
        Empresa.objects.filter(cuit="30111111118").delete()
        self.empresa = Empresa.objects.create(
            nombre="EMPRESA TEST SUMAS Y SALDOS",
            cuit="30111111118",
            direccion="Calle Test 123",
        )
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa,
            ejercicio="2026",
            inicio=date(2026, 1, 1),
            cierre=date(2026, 12, 31),
        )
        self.ejercicio_anterior = Ejercicio.objects.create(
            empresa=self.empresa,
            ejercicio="2025",
            inicio=date(2025, 1, 1),
            cierre=date(2025, 12, 31),
        )

        # Cuentas
        self.cuenta_caja = Cuenta.objects.create(
            empresa=self.empresa,
            codigo=111,
            cuenta="Caja",
            jerarquia="1.1.01",
            imputable=1,
            tipo="A",
        )

        # 1. Asiento del ejercicio anterior (no debe entrar jamás)
        asiento_2025 = Asiento.objects.create(
            empresa=self.empresa,
            ejercicio=self.ejercicio_anterior,
            fecha=date(2025, 6, 15),
            concepto="Movimiento 2025",
            monto=Decimal("5000.00"),
            condic=1,
        )
        AsientoLinea.objects.create(
            asiento=asiento_2025,
            cuenta=self.cuenta_caja,
            debe=Decimal("5000.00"),
            haber=Decimal("0.00"),
        )

        # 2. Asiento de Apertura 2026 (condic = 5)
        asiento_apertura = Asiento.objects.create(
            empresa=self.empresa,
            ejercicio=self.ejercicio,
            fecha=date(2026, 1, 1),
            concepto="Asiento de Apertura 2026",
            monto=Decimal("10000.00"),
            condic=5,
        )
        AsientoLinea.objects.create(
            asiento=asiento_apertura,
            cuenta=self.cuenta_caja,
            debe=Decimal("10000.00"),
            haber=Decimal("0.00"),
        )

        # 3. Asientos de Enero 2026 (15/01/2026 y 18/01/2026) (condic = 1)
        asiento_enero = Asiento.objects.create(
            empresa=self.empresa,
            ejercicio=self.ejercicio,
            fecha=date(2026, 1, 15),
            concepto="Venta Enero Debe",
            monto=Decimal("2000.00"),
            condic=1,
        )
        AsientoLinea.objects.create(
            asiento=asiento_enero,
            cuenta=self.cuenta_caja,
            debe=Decimal("2000.00"),
            haber=Decimal("0.00"),
        )

        asiento_enero_h = Asiento.objects.create(
            empresa=self.empresa,
            ejercicio=self.ejercicio,
            fecha=date(2026, 1, 18),
            concepto="Pago Enero Haber",
            monto=Decimal("500.00"),
            condic=1,
        )
        AsientoLinea.objects.create(
            asiento=asiento_enero_h,
            cuenta=self.cuenta_caja,
            debe=Decimal("0.00"),
            haber=Decimal("500.00"),
        )

        # 4. Asiento de Febrero 2026 (10/02/2026) (condic = 1)
        asiento_febrero = Asiento.objects.create(
            empresa=self.empresa,
            ejercicio=self.ejercicio,
            fecha=date(2026, 2, 10),
            concepto="Cobranza Febrero",
            monto=Decimal("3000.00"),
            condic=1,
        )
        AsientoLinea.objects.create(
            asiento=asiento_febrero,
            cuenta=self.cuenta_caja,
            debe=Decimal("3000.00"),
            haber=Decimal("0.00"),
        )

    def test_apertura_desde_inicio_ejercicio_con_apertura_activada(self):
        """Si fecha_desde es 01/01/2026 y mostrar_apertura=True, la apertura es 10000.00."""
        res = _calcular_balance(
            empresa_id=self.empresa.id,
            ejercicio=self.ejercicio,
            fecha_desde=date(2026, 1, 1),
            fecha_hasta=date(2026, 1, 31),
            mostrar_apertura=True,
        )
        caja_data = next(f for f in res['balance'] if f['cuenta'].id == self.cuenta_caja.id)

        self.assertEqual(caja_data['apertura'], Decimal("10000.00"))
        self.assertEqual(caja_data['periodo_debe'], Decimal("2000.00"))
        self.assertEqual(caja_data['periodo_haber'], Decimal("500.00"))
        self.assertEqual(caja_data['saldo'], Decimal("11500.00"))

    def test_apertura_desde_inicio_ejercicio_con_apertura_desactivada(self):
        """Si mostrar_apertura=False, el asiento condic=5 no aporta a apertura."""
        res = _calcular_balance(
            empresa_id=self.empresa.id,
            ejercicio=self.ejercicio,
            fecha_desde=date(2026, 1, 1),
            fecha_hasta=date(2026, 1, 31),
            mostrar_apertura=False,
        )
        caja_data = next(f for f in res['balance'] if f['cuenta'].id == self.cuenta_caja.id)

        self.assertEqual(caja_data['apertura'], Decimal("0.00"))
        self.assertEqual(caja_data['periodo_debe'], Decimal("2000.00"))
        self.assertEqual(caja_data['periodo_haber'], Decimal("500.00"))
        self.assertEqual(caja_data['saldo'], Decimal("1500.00"))

    def test_apertura_con_fecha_desde_posterior_a_inicio(self):
        """Si fecha_desde es 01/02/2026 y mostrar_apertura=True:
        Apertura = apertura_condic5 (10000) + neto de enero (2000 - 500 = 1500) = 11500.
        Período = febrero (debe 3000, haber 0).
        """
        res = _calcular_balance(
            empresa_id=self.empresa.id,
            ejercicio=self.ejercicio,
            fecha_desde=date(2026, 2, 1),
            fecha_hasta=date(2026, 2, 28),
            mostrar_apertura=True,
        )
        caja_data = next(f for f in res['balance'] if f['cuenta'].id == self.cuenta_caja.id)

        self.assertEqual(caja_data['apertura'], Decimal("11500.00"))
        self.assertEqual(caja_data['periodo_debe'], Decimal("3000.00"))
        self.assertEqual(caja_data['periodo_haber'], Decimal("0.00"))
        self.assertEqual(caja_data['saldo'], Decimal("14500.00"))

    def test_apertura_con_fecha_desde_posterior_y_apertura_desactivada(self):
        """Si fecha_desde es 01/02/2026 y mostrar_apertura=False:
        Apertura = solo neto de enero (1500).
        """
        res = _calcular_balance(
            empresa_id=self.empresa.id,
            ejercicio=self.ejercicio,
            fecha_desde=date(2026, 2, 1),
            fecha_hasta=date(2026, 2, 28),
            mostrar_apertura=False,
        )
        caja_data = next(f for f in res['balance'] if f['cuenta'].id == self.cuenta_caja.id)

        self.assertEqual(caja_data['apertura'], Decimal("1500.00"))
        self.assertEqual(caja_data['periodo_debe'], Decimal("3000.00"))
        self.assertEqual(caja_data['periodo_haber'], Decimal("0.00"))
        self.assertEqual(caja_data['saldo'], Decimal("4500.00"))
