"""Balance de Saldos Mensuales — pruebas del servicio (Plan 047, fase 3).

Cubre los puntos 1-11, 14-20 y 23-26 del plan de pruebas.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from contable.models import Asiento, Cuenta
from contable.services.asientos import crear_asiento
from contable.services.saldos_mensuales import (
    calcular_saldos_mensuales, periodos_ejercicio,
)
from empresas.models import Empresa, Ejercicio, Sucursal

User = get_user_model()
CERO = Decimal("0.00")


class SaldosMensualesBase(TestCase):
    """Plan de cuentas de 3 niveles para poder verificar el rollup.

        1     ACTIVO                 (sumarizadora)
        11    CAJA Y BANCOS          (sumarizadora)
        111001  CAJA                 (imputable)
        111011  BANCO                (imputable)
        4     INGRESOS               (sumarizadora)
        410101  VENTAS               (imputable)
        5     EGRESOS                (sumarizadora)
        510001  COSTO DE VENTAS      (imputable)
    """

    def setUp(self):
        self.usuario = User.objects.create_user(username="sm_user", password="x")
        self.empresa = Empresa.objects.create(
            nombre="EMPRESA SALDOS SA", cuit="30999999996",
            direccion="Calle 1", correo="sm@e.com",
        )
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa, ejercicio="Ejercicio 2026",
            inicio=timezone.datetime(2026, 1, 1).date(),
            cierre=timezone.datetime(2026, 12, 31).date(),
        )
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, nombre="Central", direccion="Calle 1", telefono="0381",
        )

        def cta(jerarquia, nombre, tipo, imputable, padre=None):
            return Cuenta.objects.create(
                jerarquia=jerarquia, cuenta=nombre, tipo=tipo, imputable=imputable,
                sumariza=padre, empresa=self.empresa,
            )

        self.activo = cta("1", "ACTIVO", "A", 0)
        self.caja_bancos = cta("11", "CAJA Y BANCOS", "A", 0, self.activo)
        self.caja = cta("111001", "CAJA", "A", 1, self.caja_bancos)
        self.banco = cta("111011", "BANCO", "A", 1, self.caja_bancos)

        self.ingresos = cta("4", "INGRESOS", "R", 0)
        self.ventas = cta("410101", "VENTAS", "R", 1, self.ingresos)

        self.egresos = cta("5", "EGRESOS", "R", 0)
        self.costo = cta("510001", "COSTO DE VENTAS", "R", 1, self.egresos)

    def _asiento(self, mes, condic=1, monto="1000.00", debe=None, haber=None,
                 dia=15, sucursal=None, modulo=1, anio=2026):
        """Asiento balanceado. Por defecto Caja al debe contra Ventas al haber.

        `crear_asiento` no expone `sucursal` (ver nota en el plan 047), así que se asigna con un
        UPDATE posterior para poder ejercitar el filtro del reporte.
        """
        debe = debe or self.caja
        haber = haber or self.ventas
        asiento = crear_asiento(
            empresa=self.empresa,
            fecha=timezone.datetime(anio, mes, dia).date(),
            concepto=f"MOV {mes:02d}",
            condic=condic,
            modulo=modulo,
            lineas=[
                {'cuenta': debe, 'debe': Decimal(monto), 'haber': CERO},
                {'cuenta': haber, 'debe': CERO, 'haber': Decimal(monto)},
            ],
            usuario=self.usuario,
        )
        if sucursal is not None:
            Asiento.objects.filter(pk=asiento.pk).update(sucursal=sucursal)
            asiento.refresh_from_db()
        return asiento

    def _calcular(self, **kwargs):
        kwargs.setdefault('empresa_id', self.empresa.pk)
        kwargs.setdefault('ejercicio', self.ejercicio)
        return calcular_saldos_mensuales(**kwargs)

    def _fila(self, resultado, cuenta):
        return next((f for f in resultado['filas'] if f['cuenta'].id == cuenta.id), None)


class PeriodosTests(SaldosMensualesBase):
    """1-3: las columnas mensuales son dinámicas según el ejercicio."""

    def _periodos(self, inicio, cierre):
        ej = Ejercicio(inicio=inicio, cierre=cierre)
        return [p['clave'] for p in periodos_ejercicio(ej)]

    def test_1_ejercicio_calendario(self):
        claves = self._periodos(
            timezone.datetime(2025, 1, 1).date(), timezone.datetime(2025, 12, 31).date())
        self.assertEqual(len(claves), 12)
        self.assertEqual(claves[0], "202501")
        self.assertEqual(claves[-1], "202512")

    def test_2_ejercicio_que_cierra_en_marzo(self):
        """Si cierra en marzo de 2026, la primera columna es 202504 y la última 202603."""
        claves = self._periodos(
            timezone.datetime(2025, 4, 1).date(), timezone.datetime(2026, 3, 31).date())
        self.assertEqual(len(claves), 12)
        self.assertEqual(claves[0], "202504")
        self.assertEqual(claves[-1], "202603")
        # El cruce de año no colisiona: 202601 y 202501 son columnas distintas.
        self.assertIn("202601", claves)
        self.assertNotIn("202501", claves)

    def test_3_ejercicio_irregular(self):
        claves = self._periodos(
            timezone.datetime(2025, 9, 1).date(), timezone.datetime(2025, 12, 31).date())
        self.assertEqual(claves, ["202509", "202510", "202511", "202512"])

    def test_3b_bordes_de_cada_periodo(self):
        periodos = periodos_ejercicio(self.ejercicio)
        enero, diciembre = periodos[0], periodos[-1]
        self.assertEqual(enero['primer_dia'], timezone.datetime(2026, 1, 1).date())
        self.assertEqual(enero['ultimo_dia'], timezone.datetime(2026, 1, 31).date())
        self.assertEqual(diciembre['ultimo_dia'], timezone.datetime(2026, 12, 31).date())
        # Febrero de un año no bisiesto.
        self.assertEqual(periodos[1]['ultimo_dia'], timezone.datetime(2026, 2, 28).date())


class ReglaCondicTests(SaldosMensualesBase):
    """4-6: el reparto por `condic` es el corazón del reporte."""

    def test_4_la_apertura_no_cae_en_ningun_mes(self):
        """Aunque su fecha sea el primer día del ejercicio, que está dentro de enero."""
        crear_asiento(
            empresa=self.empresa, fecha=self.ejercicio.inicio,
            concepto="APERTURA", condic=5,
            lineas=[
                {'cuenta': self.caja, 'debe': Decimal("7000.00"), 'haber': CERO},
                {'cuenta': self.banco, 'debe': CERO, 'haber': Decimal("7000.00")},
            ],
            usuario=self.usuario,
        )
        fila = self._fila(self._calcular(), self.caja)
        self.assertEqual(fila['apertura'], Decimal("7000.00"))
        self.assertEqual(fila['meses'][0], CERO)
        self.assertEqual(sum(fila['meses'], CERO), CERO)

    def test_5_un_movimiento_no_cae_en_apertura(self):
        """Aunque su fecha sea la del primer día del ejercicio."""
        self._asiento(mes=1, dia=1)
        fila = self._fila(self._calcular(), self.caja)
        self.assertEqual(fila['apertura'], CERO)
        self.assertEqual(fila['meses'][0], Decimal("1000.00"))

    def test_6_refundicion_y_cierre_nunca_entran(self):
        self._asiento(mes=5, monto="1000.00")
        for condic in (6, 7):
            crear_asiento(
                empresa=self.empresa, fecha=timezone.datetime(2026, 12, 31).date(),
                concepto=f"ESTRUCTURAL {condic}", condic=condic,
                lineas=[
                    {'cuenta': self.ventas, 'debe': Decimal("1000.00"), 'haber': CERO},
                    {'cuenta': self.caja, 'debe': CERO, 'haber': Decimal("1000.00")},
                ],
                usuario=self.usuario,
            )
        fila = self._fila(self._calcular(), self.ventas)
        # Sólo el movimiento de mayo: la refundición no dio vuelta la cuenta de resultado.
        self.assertEqual(fila['total'], Decimal("-1000.00"))
        self.assertEqual(fila['meses'][11], CERO)


class CalculoTests(SaldosMensualesBase):
    """7-9: mes, identidad Total y rollup jerárquico."""

    def test_7_cada_movimiento_cae_en_su_mes(self):
        self._asiento(mes=3, monto="300.00")
        self._asiento(mes=7, monto="700.00")
        fila = self._fila(self._calcular(), self.caja)
        self.assertEqual(fila['meses'][2], Decimal("300.00"))   # marzo
        self.assertEqual(fila['meses'][6], Decimal("700.00"))   # julio
        self.assertEqual(fila['meses'][0], CERO)
        self.assertEqual(sum(fila['meses'], CERO), Decimal("1000.00"))

    def test_8_total_es_apertura_mas_meses(self):
        crear_asiento(
            empresa=self.empresa, fecha=self.ejercicio.inicio,
            concepto="APERTURA", condic=5,
            lineas=[
                {'cuenta': self.caja, 'debe': Decimal("500.00"), 'haber': CERO},
                {'cuenta': self.banco, 'debe': CERO, 'haber': Decimal("500.00")},
            ],
            usuario=self.usuario,
        )
        self._asiento(mes=2, monto="250.00")
        resultado = self._calcular()
        for fila in resultado['filas']:
            self.assertEqual(
                fila['total'], fila['apertura'] + sum(fila['meses'], CERO),
                f"No cierra la identidad en {fila['cuenta'].cuenta}",
            )
        self.assertEqual(self._fila(resultado, self.caja)['total'], Decimal("750.00"))

    def test_8b_el_total_coincide_con_el_saldo_final_del_sumas_y_saldos(self):
        """Prueba cruzada: si este reporte y el Balance divergen, uno de los dos está mal."""
        from contable.views_htmx import _calcular_balance

        crear_asiento(
            empresa=self.empresa, fecha=self.ejercicio.inicio,
            concepto="APERTURA", condic=5,
            lineas=[
                {'cuenta': self.caja, 'debe': Decimal("1500.00"), 'haber': CERO},
                {'cuenta': self.banco, 'debe': CERO, 'haber': Decimal("1500.00")},
            ],
            usuario=self.usuario,
        )
        self._asiento(mes=4, monto="600.00")
        self._asiento(mes=9, monto="400.00", debe=self.costo, haber=self.caja)

        mensual = self._calcular()
        balance = _calcular_balance(
            self.empresa.pk,
            fecha_desde=self.ejercicio.inicio,
            fecha_hasta=self.ejercicio.cierre,
            mostrar_sumarizadoras=True,
        )
        saldos_balance = {f['cuenta'].id: f['saldo'] for f in balance['balance']}

        for fila in mensual['filas']:
            if fila['cuenta'].imputable != 1:
                continue
            self.assertEqual(
                fila['total'], saldos_balance.get(fila['cuenta'].id, CERO),
                f"Divergencia con el Sumas y Saldos en {fila['cuenta'].cuenta}",
            )

    def test_9_rollup_de_tres_niveles(self):
        self._asiento(mes=2, monto="100.00", debe=self.caja)
        self._asiento(mes=2, monto="250.00", debe=self.banco)
        self._asiento(mes=6, monto="400.00", debe=self.caja)

        resultado = self._calcular()
        caja_bancos = self._fila(resultado, self.caja_bancos)
        activo = self._fila(resultado, self.activo)

        # Nivel intermedio = suma exacta de sus dos hijas, columna por columna.
        self.assertEqual(caja_bancos['meses'][1], Decimal("350.00"))
        self.assertEqual(caja_bancos['meses'][5], Decimal("400.00"))
        self.assertEqual(caja_bancos['total'], Decimal("750.00"))
        # Y el nivel raíz arrastra el consolidado, sin contarlo dos veces.
        self.assertEqual(activo['total'], Decimal("750.00"))

    def test_9b_niveles_de_indentacion(self):
        self._asiento(mes=1)
        resultado = self._calcular()
        self.assertEqual(self._fila(resultado, self.activo)['nivel'], 1)
        self.assertEqual(self._fila(resultado, self.caja_bancos)['nivel'], 2)
        self.assertEqual(self._fila(resultado, self.caja)['nivel'], 3)


class SignoTests(SaldosMensualesBase):
    """10-11: el servicio devuelve siempre signo natural; los totales controlan partida doble."""

    def test_10_la_fila_totales_da_cero_en_modo_todas(self):
        self._asiento(mes=3, monto="1000.00")
        self._asiento(mes=8, monto="450.00", debe=self.costo, haber=self.caja)
        totales = self._calcular()['totales']
        self.assertEqual(totales['apertura'], CERO)
        for i, m in enumerate(totales['meses']):
            self.assertEqual(m, CERO, f"La columna {i} no cierra en cero")
        self.assertEqual(totales['total'], CERO)

    def test_11_signo_natural_tambien_en_modo_resultados(self):
        """Un ingreso sale NEGATIVO (haber) también con alcance='resultados'.

        La inversión (× −1) vive sólo en el export a Excel: en pantalla el operador necesita ver
        el movimiento tal cual se registró para detectar un error de carga.
        """
        self._asiento(mes=3, monto="1000.00")                                  # ingreso
        self._asiento(mes=3, monto="400.00", debe=self.costo, haber=self.caja)  # egreso

        for alcance in ('todas', 'resultados'):
            with self.subTest(alcance=alcance):
                resultado = self._calcular(alcance=alcance)
                self.assertEqual(
                    self._fila(resultado, self.ventas)['total'], Decimal("-1000.00"))
                self.assertEqual(
                    self._fila(resultado, self.costo)['total'], Decimal("400.00"))

    def test_11b_totales_en_modo_resultados_son_el_resultado_del_mes(self):
        self._asiento(mes=3, monto="1000.00")
        self._asiento(mes=3, monto="400.00", debe=self.costo, haber=self.caja)
        totales = self._calcular(alcance='resultados')['totales']
        # Signo natural: −1000 (ingreso) + 400 (egreso) = −600. Al invertirlo, el Excel mostrará
        # la ganancia de 600 del mes.
        self.assertEqual(totales['meses'][2], Decimal("-600.00"))


class FiltrosTests(SaldosMensualesBase):
    """14-20: filtros de condición, alcance, sucursal, módulo y omisión de vacías."""

    def test_14_cada_combinacion_de_condic(self):
        self._asiento(mes=1, condic=1, monto="100.00")
        self._asiento(mes=1, condic=2, monto="20.00")
        self._asiento(mes=1, condic=3, monto="3.00")
        self._asiento(mes=1, condic=4, monto="4000.00")

        casos = {
            (1,): Decimal("100.00"),
            (2,): Decimal("20.00"),
            (1, 2): Decimal("120.00"),          # gestión
            (1, 3, 4): Decimal("4103.00"),      # estados contables
            (4,): Decimal("4000.00"),           # ajustes de auditoría
            (3,): Decimal("3.00"),              # fuera de la operatoria
            (1, 2, 3, 4): Decimal("4123.00"),
        }
        for condics, esperado in casos.items():
            with self.subTest(condics=condics):
                fila = self._fila(self._calcular(condics=condics), self.caja)
                self.assertEqual(fila['meses'][0], esperado)

    def test_15_la_apertura_no_la_tocan_los_checkboxes(self):
        crear_asiento(
            empresa=self.empresa, fecha=self.ejercicio.inicio,
            concepto="APERTURA", condic=5,
            lineas=[
                {'cuenta': self.caja, 'debe': Decimal("900.00"), 'haber': CERO},
                {'cuenta': self.banco, 'debe': CERO, 'haber': Decimal("900.00")},
            ],
            usuario=self.usuario,
        )
        self._asiento(mes=1, condic=1, monto="100.00")
        for condics in ((1,), (2,), (1, 2), (1, 2, 3, 4)):
            with self.subTest(condics=condics):
                fila = self._fila(self._calcular(condics=condics), self.caja)
                self.assertEqual(fila['apertura'], Decimal("900.00"))

    def test_16_sin_condicion_tildada_devuelve_grilla_vacia_con_aviso(self):
        self._asiento(mes=1)
        resultado = self._calcular(condics=())
        self.assertEqual(resultado['filas'], [])
        self.assertTrue(resultado['aviso'])
        self.assertEqual(resultado['totales']['total'], CERO)

    def test_17_saneamiento_de_condics(self):
        """Un querystring armado a mano no puede meter apertura ni cierre en un mes."""
        self._asiento(mes=1, condic=1, monto="100.00")
        crear_asiento(
            empresa=self.empresa, fecha=self.ejercicio.inicio,
            concepto="APERTURA", condic=5,
            lineas=[
                {'cuenta': self.caja, 'debe': Decimal("900.00"), 'haber': CERO},
                {'cuenta': self.banco, 'debe': CERO, 'haber': Decimal("900.00")},
            ],
            usuario=self.usuario,
        )
        resultado = self._calcular(condics=(5, 6, 7))
        self.assertEqual(resultado['condics'], [])
        self.assertEqual(resultado['filas'], [])

        # Y una lista mixta conserva sólo lo válido.
        resultado = self._calcular(condics=(1, 5, 99, 'x'))
        self.assertEqual(resultado['condics'], [1])
        self.assertEqual(self._fila(resultado, self.caja)['meses'][0], Decimal("100.00"))

    def test_18_los_anulados_no_se_computan(self):
        from contable.services.contabilizacion import anular_asiento_de_comprobante

        asiento = self._asiento(mes=4, monto="500.00")
        anular_asiento_de_comprobante(asiento.asiento_id)
        self.assertIsNone(self._fila(self._calcular(), self.caja))

    def test_19_filtro_por_sucursal_y_modulo(self):
        self._asiento(mes=2, monto="100.00", sucursal=self.sucursal, modulo=2)
        self._asiento(mes=2, monto="70.00", sucursal=None, modulo=5)

        fila = self._fila(self._calcular(sucursal_id=self.sucursal.pk), self.caja)
        self.assertEqual(fila['meses'][1], Decimal("100.00"))

        fila = self._fila(self._calcular(modulo=5), self.caja)
        self.assertEqual(fila['meses'][1], Decimal("70.00"))

        fila = self._fila(self._calcular(), self.caja)
        self.assertEqual(fila['meses'][1], Decimal("170.00"))

    def test_20_omitir_sin_movimiento_usa_valor_absoluto(self):
        """Una cuenta que netea cero pero TUVO movimiento se conserva; una sin nada, se omite."""
        self._asiento(mes=2, monto="500.00", debe=self.caja, haber=self.ventas)
        self._asiento(mes=5, monto="500.00", debe=self.ventas, haber=self.caja)

        resultado = self._calcular()
        fila = self._fila(resultado, self.caja)
        self.assertIsNotNone(fila, "La cuenta neteó cero pero tuvo movimiento: debe verse")
        self.assertEqual(fila['total'], CERO)
        # El banco no tuvo ningún movimiento: se omite.
        self.assertIsNone(self._fila(resultado, self.banco))

        # Y con el filtro apagado aparecen todas.
        completo = self._calcular(omitir_sin_movimiento=False)
        self.assertIsNotNone(self._fila(completo, self.banco))

    def test_20b_alcance_y_sumarizadoras(self):
        self._asiento(mes=2, monto="500.00")

        solo_r = self._calcular(alcance='resultados')
        self.assertTrue(all(f['cuenta'].tipo == 'R' for f in solo_r['filas']))
        self.assertIsNone(self._fila(solo_r, self.caja))

        patrimoniales = self._calcular(alcance='patrimoniales')
        self.assertTrue(all(f['cuenta'].tipo in ('A', 'P', 'N') for f in patrimoniales['filas']))
        self.assertIsNone(self._fila(patrimoniales, self.ventas))

        sin_sumarizadoras = self._calcular(mostrar_sumarizadoras=False)
        self.assertTrue(all(f['cuenta'].imputable == 1 for f in sin_sumarizadoras['filas']))


class AlcanceInflexibleTests(SaldosMensualesBase):
    """23-26: empresa y ejercicio acotan siempre, y el caso de negocio del primer día."""

    def test_23_no_se_mezclan_empresas(self):
        otra = Empresa.objects.create(
            nombre="OTRA SA", cuit="30999999995", direccion="x", correo="o@e.com")
        ej_otra = Ejercicio.objects.create(
            empresa=otra, ejercicio="Otra 2026",
            inicio=timezone.datetime(2026, 1, 1).date(),
            cierre=timezone.datetime(2026, 12, 31).date(),
        )
        cta_otra = Cuenta.objects.create(
            jerarquia="111001", cuenta="CAJA AJENA", tipo="A", imputable=1, empresa=otra)
        crear_asiento(
            empresa=otra, fecha=timezone.datetime(2026, 3, 10).date(),
            concepto="AJENO", condic=1, ejercicio=ej_otra,
            lineas=[
                {'cuenta': cta_otra, 'debe': Decimal("999.00"), 'haber': CERO},
                {'cuenta': cta_otra, 'debe': CERO, 'haber': Decimal("999.00")},
            ],
            usuario=self.usuario,
        )
        self._asiento(mes=3, monto="100.00")

        resultado = self._calcular()
        self.assertTrue(all(f['cuenta'].empresa_id == self.empresa.pk for f in resultado['filas']))
        self.assertEqual(self._fila(resultado, self.caja)['meses'][2], Decimal("100.00"))

    def test_24_no_entran_asientos_de_otro_ejercicio(self):
        """Ni siquiera si su fecha cae dentro del rango del ejercicio consultado.

        Es el caso que un filtro sólo por fechas dejaría pasar, y el que justifica acotar por la
        FK `ejercicio` además del rango.
        """
        otro_ejercicio = Ejercicio.objects.create(
            empresa=self.empresa, ejercicio="Ejercicio 2027",
            inicio=timezone.datetime(2027, 1, 1).date(),
            cierre=timezone.datetime(2027, 12, 31).date(),
        )
        self._asiento(mes=3, monto="100.00")
        # Fecha dentro de 2026 pero adjudicado a mano al ejercicio 2027.
        crear_asiento(
            empresa=self.empresa, fecha=timezone.datetime(2026, 3, 20).date(),
            concepto="EJERCICIO AJENO", condic=1, ejercicio=otro_ejercicio,
            lineas=[
                {'cuenta': self.caja, 'debe': Decimal("555.00"), 'haber': CERO},
                {'cuenta': self.ventas, 'debe': CERO, 'haber': Decimal("555.00")},
            ],
            usuario=self.usuario,
        )
        fila = self._fila(self._calcular(), self.caja)
        self.assertEqual(fila['meses'][2], Decimal("100.00"))
        self.assertEqual(fila['total'], Decimal("100.00"))

    def test_25_el_ejercicio_es_obligatorio(self):
        with self.assertRaises(ValueError):
            calcular_saldos_mensuales(empresa_id=self.empresa.pk, ejercicio=None)

    def test_26_factura_del_ejercicio_anterior_cae_en_la_primera_columna(self):
        """Caso de negocio cotidiano: se registra con la fecha del primer día del ejercicio."""
        self._asiento(mes=1, dia=1, monto="820.00", debe=self.costo, haber=self.caja)
        fila = self._fila(self._calcular(), self.costo)
        self.assertEqual(fila['meses'][0], Decimal("820.00"))
        self.assertEqual(fila['apertura'], CERO)
