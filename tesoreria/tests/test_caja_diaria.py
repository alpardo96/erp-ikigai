"""Pruebas de la Caja Diaria de Tesorería.

Cubren el criterio de saldos acordado (Efectivo + Dólares + Valores arrastran; Banco y Tarjetas
solo informan), el prorrateo entre varias contrapartidas, el filtro Real/Presupuestado, el cierre
con arrastre y el aislamiento por empresa/sucursal.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from contable.models import Asiento, Cuenta
from contable.services.asientos import crear_asiento
from empresas.models import Empresa, Ejercicio, Sucursal
from tesoreria.models import Caja, CajaSesion
from tesoreria.services.caja_diaria import (
    abrir_caja, agrupar_para_pdf, armar_caja_diaria, cerrar_caja, get_caja_tesoreria,
)

User = get_user_model()


class CajaDiariaTestCase(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="tesorero", password="x")

        self.empresa = Empresa.objects.create(
            nombre="EMPRESA CAJA SA", cuit="30999888771",
            direccion="Calle 1", correo="caja@test.com",
        )
        self.sucursal = Sucursal.objects.create(empresa=self.empresa, nombre="TUCUMAN")
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa, ejercicio="Ejercicio 2026",
            inicio=timezone.datetime(2026, 1, 1).date(),
            cierre=timezone.datetime(2026, 12, 31).date(),
        )

        def cuenta(jerarquia, nombre, tipo, disponibilidad=''):
            return Cuenta.objects.create(
                jerarquia=jerarquia, cuenta=nombre, imputable=1, tipo=tipo,
                empresa=self.empresa, tipo_disponibilidad=disponibilidad,
            )

        self.cta_efectivo = cuenta("111001", "CAJA TESORERIA", "A", "EFE")
        self.cta_dolares = cuenta("111003", "CAJA DOLARES", "A", "DOL")
        self.cta_valores = cuenta("111002", "VALORES EN CARTERA", "A", "VAL")
        self.cta_banco = cuenta("111011", "BANCO NACION", "A", "BCO")
        self.cta_clientes = cuenta("112001", "CLIENTES", "A")
        self.cta_gastos = cuenta("411001", "GASTOS GENERALES", "R")
        self.cta_sueldos = cuenta("411002", "SUELDOS A PAGAR", "P")

        self.caja = get_caja_tesoreria(self.empresa.id, self.sucursal.id)
        self.sesion = abrir_caja(
            self.caja, self.usuario,
            si_efectivo=Decimal("100000.00"),
            si_dolares=Decimal("50000.00"),
            si_valores=Decimal("20000.00"),
        )

    # ------------------------------------------------------------------ helpers
    def _asiento(self, lineas, condic=1, concepto="MOVIMIENTO", sesion=None):
        asiento = crear_asiento(
            empresa=self.empresa, fecha=timezone.datetime(2026, 7, 27).date(),
            concepto=concepto, lineas=lineas, condic=condic,
            ejercicio=self.ejercicio, usuario=self.usuario,
        )
        asiento.sesion_caja = sesion or self.sesion
        asiento.save(update_fields=['sesion_caja'])
        return asiento

    def _cobro_efectivo(self, importe, condic=1):
        return self._asiento([
            {'cuenta': self.cta_efectivo, 'debe': importe, 'haber': Decimal("0.00")},
            {'cuenta': self.cta_clientes, 'debe': Decimal("0.00"), 'haber': importe},
        ], condic=condic, concepto="COBRANZA")

    # ------------------------------------------------------------------- pruebas
    def test_saldo_inicial_es_efectivo_mas_dolares_mas_valores(self):
        datos = armar_caja_diaria(self.sesion)
        self.assertEqual(datos['saldos']['inicial']['neto'], Decimal("170000.00"))

    def test_cobro_en_efectivo_suma_al_saldo(self):
        self._cobro_efectivo(Decimal("15000.00"))
        datos = armar_caja_diaria(self.sesion)

        self.assertEqual(len(datos['movimientos']), 1)
        movimiento = datos['movimientos'][0]
        self.assertEqual(movimiento['efectivo'], Decimal("15000.00"))
        self.assertEqual(movimiento['cuenta'], "CLIENTES")
        self.assertEqual(movimiento['saldo'], Decimal("185000.00"))
        self.assertEqual(datos['saldos']['final']['neto'], Decimal("185000.00"))

    def test_pago_en_efectivo_resta_del_saldo(self):
        self._asiento([
            {'cuenta': self.cta_gastos, 'debe': Decimal("8000.00"), 'haber': Decimal("0.00")},
            {'cuenta': self.cta_efectivo, 'debe': Decimal("0.00"), 'haber': Decimal("8000.00")},
        ], concepto="PAGO GASTOS")

        datos = armar_caja_diaria(self.sesion)
        self.assertEqual(datos['movimientos'][0]['efectivo'], Decimal("-8000.00"))
        self.assertEqual(datos['saldos']['final']['efectivo'], Decimal("92000.00"))
        self.assertEqual(datos['saldos']['movimiento']['egresos'], Decimal("8000.00"))

    def test_banco_informa_movimiento_pero_no_altera_el_saldo(self):
        """Regla acordada: Banco y Tarjetas se informan pero NO integran el saldo disponible."""
        self._asiento([
            {'cuenta': self.cta_sueldos, 'debe': Decimal("500000.00"), 'haber': Decimal("0.00")},
            {'cuenta': self.cta_banco, 'debe': Decimal("0.00"), 'haber': Decimal("500000.00")},
        ], concepto="TRANSFERENCIA SUELDOS")

        datos = armar_caja_diaria(self.sesion)
        saldos = datos['saldos']

        self.assertEqual(saldos['movimiento']['banco'], Decimal("-500000.00"))
        # El neto disponible no se movió: el banco no forma parte de la caja.
        self.assertEqual(saldos['movimiento']['neto'], Decimal("0.00"))
        self.assertEqual(saldos['final']['neto'], saldos['inicial']['neto'])

    def test_saldo_final_cierra_contra_inicial_mas_movimientos(self):
        self._cobro_efectivo(Decimal("30000.00"))
        self._asiento([
            {'cuenta': self.cta_gastos, 'debe': Decimal("5000.00"), 'haber': Decimal("0.00")},
            {'cuenta': self.cta_valores, 'debe': Decimal("0.00"), 'haber': Decimal("5000.00")},
        ], concepto="PAGO CON VALORES")

        saldos = armar_caja_diaria(self.sesion)['saldos']
        self.assertEqual(saldos['inicial']['neto'] + saldos['movimiento']['neto'], saldos['final']['neto'])
        self.assertEqual(saldos['final']['neto'], Decimal("195000.00"))

    def test_prorrateo_entre_varias_contrapartidas(self):
        """Un pago único que cancela dos conceptos reparte el efectivo en proporción."""
        self._asiento([
            {'cuenta': self.cta_gastos, 'debe': Decimal("3000.00"), 'haber': Decimal("0.00")},
            {'cuenta': self.cta_sueldos, 'debe': Decimal("1000.00"), 'haber': Decimal("0.00")},
            {'cuenta': self.cta_efectivo, 'debe': Decimal("0.00"), 'haber': Decimal("4000.00")},
        ], concepto="PAGO MIXTO")

        datos = armar_caja_diaria(self.sesion)
        movimientos = datos['movimientos']

        self.assertEqual(len(movimientos), 2)
        # 3.000 / 4.000 = 75% y 1.000 / 4.000 = 25% del efectivo egresado.
        self.assertEqual(movimientos[0]['efectivo'], Decimal("-3000.00"))
        self.assertEqual(movimientos[1]['efectivo'], Decimal("-1000.00"))
        # La suma de las partes cierra exactamente contra el total del asiento.
        self.assertEqual(sum(m['efectivo'] for m in movimientos), Decimal("-4000.00"))

    def test_filtro_condic_real_y_presupuestado(self):
        self._cobro_efectivo(Decimal("10000.00"), condic=1)
        self._cobro_efectivo(Decimal("7000.00"), condic=2)

        self.assertEqual(len(armar_caja_diaria(self.sesion)['movimientos']), 2)
        self.assertEqual(len(armar_caja_diaria(self.sesion, condic=1)['movimientos']), 1)
        self.assertEqual(len(armar_caja_diaria(self.sesion, condic=2)['movimientos']), 1)

        solo_real = armar_caja_diaria(self.sesion, condic=1)
        self.assertEqual(solo_real['saldos']['final']['efectivo'], Decimal("110000.00"))

    def test_asiento_sin_disponibilidades_no_entra_al_reporte(self):
        self._asiento([
            {'cuenta': self.cta_gastos, 'debe': Decimal("1000.00"), 'haber': Decimal("0.00")},
            {'cuenta': self.cta_sueldos, 'debe': Decimal("0.00"), 'haber': Decimal("1000.00")},
        ], concepto="DEVENGAMIENTO")

        self.assertEqual(len(armar_caja_diaria(self.sesion)['movimientos']), 0)

    def test_asiento_anulado_no_entra_al_reporte(self):
        asiento = self._cobro_efectivo(Decimal("9000.00"))
        asiento.anulado = True
        asiento.save(update_fields=['anulado'])

        self.assertEqual(len(armar_caja_diaria(self.sesion)['movimientos']), 0)

    def test_cierre_congela_saldos_y_abre_la_siguiente_con_arrastre(self):
        self._cobro_efectivo(Decimal("25000.00"))

        cerrada, nueva = cerrar_caja(self.sesion, self.usuario)

        self.assertEqual(cerrada.estado, 'C')
        self.assertIsNotNone(cerrada.fecha_operativa)
        self.assertEqual(cerrada.sf_efectivo, Decimal("125000.00"))
        self.assertEqual(cerrada.saldo_final_neto, Decimal("195000.00"))

        # La caja siguiente arranca exactamente donde terminó la anterior.
        self.assertEqual(nueva.estado, 'A')
        self.assertEqual(nueva.numero, cerrada.numero + 1)
        self.assertEqual(nueva.si_efectivo, cerrada.sf_efectivo)
        self.assertEqual(nueva.si_dolares, cerrada.sf_dolares)
        self.assertEqual(nueva.si_valores, cerrada.sf_valores)
        self.assertEqual(armar_caja_diaria(nueva)['saldos']['inicial']['neto'], Decimal("195000.00"))

    def test_no_se_puede_cerrar_dos_veces(self):
        cerrada, _ = cerrar_caja(self.sesion, self.usuario)
        with self.assertRaises(ValueError):
            cerrar_caja(cerrada, self.usuario)

    def test_solo_hay_una_caja_activa_por_sucursal(self):
        otra = abrir_caja(self.caja, self.usuario)
        self.assertEqual(otra.id, self.sesion.id)
        self.assertEqual(CajaSesion.objects.filter(caja=self.caja, estado='A').count(), 1)

    def test_aislamiento_entre_empresas(self):
        """Regla inflexible del proyecto: nada se mezcla entre empresas."""
        otra_empresa = Empresa.objects.create(
            nombre="OTRA SA", cuit="30111222334", direccion="Calle 2", correo="otra@test.com",
        )
        otra_sucursal = Sucursal.objects.create(empresa=otra_empresa, nombre="SALTA")
        otra_caja = get_caja_tesoreria(otra_empresa.id, otra_sucursal.id)
        otra_sesion = abrir_caja(otra_caja, self.usuario)

        self._cobro_efectivo(Decimal("40000.00"))

        self.assertEqual(len(armar_caja_diaria(self.sesion)['movimientos']), 1)
        self.assertEqual(len(armar_caja_diaria(otra_sesion)['movimientos']), 0)
        self.assertNotEqual(otra_caja.id, self.caja.id)

    def test_agrupacion_pdf_une_la_misma_cuenta_en_un_solo_subtotal(self):
        """El reporte legado repetía la misma cuenta varias veces; acá se agrupa de verdad."""
        self._asiento([
            {'cuenta': self.cta_sueldos, 'debe': Decimal("1000.00"), 'haber': Decimal("0.00")},
            {'cuenta': self.cta_efectivo, 'debe': Decimal("0.00"), 'haber': Decimal("1000.00")},
        ], concepto="SUELDOS 1")
        self._cobro_efectivo(Decimal("500.00"))
        self._asiento([
            {'cuenta': self.cta_sueldos, 'debe': Decimal("2000.00"), 'haber': Decimal("0.00")},
            {'cuenta': self.cta_efectivo, 'debe': Decimal("0.00"), 'haber': Decimal("2000.00")},
        ], concepto="SUELDOS 2")

        secciones = agrupar_para_pdf(armar_caja_diaria(self.sesion)['movimientos'])
        egresos = next(s for s in secciones if s['titulo'] == 'EGRESOS')

        # Las dos imputaciones a SUELDOS quedan en un único grupo con un único subtotal.
        self.assertEqual(len(egresos['grupos']), 1)
        self.assertEqual(egresos['grupos'][0]['cuenta'], "SUELDOS A PAGAR")
        self.assertEqual(len(egresos['grupos'][0]['movimientos']), 2)
        self.assertEqual(egresos['grupos'][0]['subtotal']['efectivo'], Decimal("-3000.00"))

        ingresos = next(s for s in secciones if s['titulo'] == 'INGRESOS')
        self.assertEqual(ingresos['total']['total'], Decimal("500.00"))
