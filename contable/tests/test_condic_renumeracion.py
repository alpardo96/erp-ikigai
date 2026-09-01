"""Fase 1 del Plan 047 — renumeración y semántica del campo `condic`.

Cubre los puntos 27 y 29-33 del plan de pruebas:
  27. `editar_asiento` rechaza una fecha fuera del ejercicio del asiento (D-9).
  29. `procesar_cierre_ejercicio` crea el asiento con condic=6 (Refundición).
  30. Una compra condic=3 genera Libro IVA; una condic=2 o 4, no.
  31. El asiento condic=6 entra al período de `_calcular_balance` y no al Libro IVA.
  32. `editar_asiento` rechaza editar un asiento con condic >= 5 (D-6).
  33. La data migration reetiqueta 3->5 y las refundiciones históricas a 6.
"""
from decimal import Decimal
from importlib import import_module

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from contable.models import (
    Asiento, Cuenta, LibroIvaAlic, LibroIvaCompras, ParametrosContables,
    CONDIC_ASIENTO, CONDIC_ESTRUCTURAL, CONDIC_FISCAL, CONDIC_MOVIMIENTO,
)
from contable.services.asientos import crear_asiento, editar_asiento
from contable.services.cierre import procesar_cierre_ejercicio
from empresas.models import Empresa, Ejercicio, Sucursal
from facturacion.models import (
    ClienteProveedor, Compra, CompraItem, TipoComprobante,
)
from productos.models import Producto, Rubro

# El módulo de la migración empieza con dígito: no se puede importar con `from ... import`.
_migracion = import_module('contable.migrations.0019_renumerar_condic')
renumerar_condic = _migracion.renumerar_condic
revertir_condic = _migracion.revertir_condic

User = get_user_model()


class CondicBaseTestCase(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="cond_user", password="x")
        self.empresa = Empresa.objects.create(
            nombre="EMPRESA CONDIC SAS", cuit="30999999997",
            direccion="Calle 1", correo="c@e.com",
        )
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa, ejercicio="Ejercicio 2026",
            inicio=timezone.datetime(2026, 1, 1).date(),
            cierre=timezone.datetime(2026, 12, 31).date(),
        )
        self.cta_caja = Cuenta.objects.create(
            jerarquia="111001", cuenta="CAJA", imputable=1, tipo="A", empresa=self.empresa,
        )
        self.cta_ventas = Cuenta.objects.create(
            jerarquia="410101", cuenta="VENTAS", imputable=1, tipo="R", empresa=self.empresa,
        )
        self.cta_resultado = Cuenta.objects.create(
            jerarquia="320101", cuenta="RESULTADO DEL EJERCICIO",
            imputable=1, tipo="N", empresa=self.empresa,
        )

    def _asiento(self, condic=1, fecha=None, monto="1000.00"):
        """Asiento balanceado Caja/Ventas con el condic pedido."""
        return crear_asiento(
            empresa=self.empresa,
            fecha=fecha or timezone.datetime(2026, 3, 15).date(),
            concepto="MOVIMIENTO DE PRUEBA",
            condic=condic,
            lineas=[
                {'cuenta': self.cta_caja, 'debe': Decimal(monto), 'haber': Decimal("0.00")},
                {'cuenta': self.cta_ventas, 'debe': Decimal("0.00"), 'haber': Decimal(monto)},
            ],
            usuario=self.usuario,
        )


class SemanticaCondicTests(CondicBaseTestCase):
    """Las constantes son la fuente de verdad que consumen servicios y templates."""

    def test_los_siete_valores_estan_definidos(self):
        self.assertEqual([v for v, _ in CONDIC_ASIENTO], [1, 2, 3, 4, 5, 6, 7])

    def test_grupos_coherentes_y_disjuntos(self):
        # Movimiento y estructural no se pisan, y juntos cubren los 7 valores.
        self.assertEqual(set(CONDIC_MOVIMIENTO) & set(CONDIC_ESTRUCTURAL), set())
        self.assertEqual(
            set(CONDIC_MOVIMIENTO) | set(CONDIC_ESTRUCTURAL),
            {v for v, _ in CONDIC_ASIENTO},
        )
        # El circuito fiscal es 1 (Real) y 3 (Ajuste): son los que tienen respaldo documental.
        self.assertEqual(set(CONDIC_FISCAL), {1, 3})
        # El 2 (sin respaldo) y el 4 (ajuste de auditoría) nunca son fiscales.
        self.assertNotIn(2, CONDIC_FISCAL)
        self.assertNotIn(4, CONDIC_FISCAL)


class EditarAsientoTests(CondicBaseTestCase):
    """D-6 y D-9: la edición no puede degradar el condic ni sacar al asiento del ejercicio."""

    def _lineas(self, monto="1000.00"):
        return [
            {'cuenta': self.cta_caja, 'debe': Decimal(monto), 'haber': Decimal("0.00")},
            {'cuenta': self.cta_ventas, 'debe': Decimal("0.00"), 'haber': Decimal(monto)},
        ]

    def test_27_rechaza_fecha_fuera_del_ejercicio(self):
        asiento = self._asiento()
        with self.assertRaises(ValidationError) as ctx:
            editar_asiento(
                asiento=asiento,
                fecha=timezone.datetime(2027, 3, 15).date(),  # ejercicio siguiente
                concepto="MOVIDO DE EJERCICIO",
                lineas=self._lineas(),
            )
        self.assertIn("fuera del ejercicio", '; '.join(ctx.exception.messages))

        asiento.refresh_from_db()
        self.assertEqual(asiento.fecha, timezone.datetime(2026, 3, 15).date())

    def test_27b_acepta_fecha_dentro_del_ejercicio(self):
        asiento = self._asiento()
        editar_asiento(
            asiento=asiento,
            fecha=timezone.datetime(2026, 7, 1).date(),
            concepto="FECHA CORREGIDA",
            lineas=self._lineas(),
        )
        asiento.refresh_from_db()
        self.assertEqual(asiento.fecha, timezone.datetime(2026, 7, 1).date())

    def test_27c_acepta_los_bordes_del_ejercicio(self):
        """El caso real: factura del ejercicio anterior cargada el primer día del actual."""
        for fecha in (self.ejercicio.inicio, self.ejercicio.cierre):
            asiento = self._asiento()
            editar_asiento(
                asiento=asiento, fecha=fecha,
                concepto="BORDE DEL EJERCICIO", lineas=self._lineas(),
            )
            asiento.refresh_from_db()
            self.assertEqual(asiento.fecha, fecha)

    def test_32_rechaza_editar_asientos_estructurales(self):
        for condic in CONDIC_ESTRUCTURAL:
            asiento = self._asiento(condic=condic)
            with self.assertRaises(ValidationError) as ctx:
                editar_asiento(
                    asiento=asiento,
                    fecha=timezone.datetime(2026, 4, 1).date(),
                    concepto="INTENTO DE EDICION",
                    lineas=self._lineas(),
                )
            mensaje = '; '.join(ctx.exception.messages)
            self.assertIn("lo genera el sistema", mensaje)
            # El condic no se degradó a Real, que era el bug.
            asiento.refresh_from_db()
            self.assertEqual(asiento.condic, condic)

    def test_32b_los_condic_de_movimiento_si_se_editan(self):
        for condic in CONDIC_MOVIMIENTO:
            asiento = self._asiento(condic=condic)
            editar_asiento(
                asiento=asiento,
                fecha=timezone.datetime(2026, 4, 1).date(),
                concepto="EDICION VALIDA",
                lineas=self._lineas("2000.00"),
            )
            asiento.refresh_from_db()
            self.assertEqual(asiento.condic, condic)
            self.assertEqual(asiento.concepto, "EDICION VALIDA")


class RefundicionTests(CondicBaseTestCase):
    """29 y 31: la refundición se identifica por condic=6, no por el texto del concepto."""

    def setUp(self):
        super().setUp()
        ParametrosContables.objects.create(
            empresa=self.empresa, cta_resultado_ejercicio=self.cta_resultado,
        )

    def test_29_la_refundicion_nace_con_condic_6(self):
        self._asiento(condic=1)  # movimiento que deja saldo en la cuenta de resultado
        asiento = procesar_cierre_ejercicio(self.ejercicio.pk, self.empresa.pk, self.usuario)
        self.assertEqual(asiento.condic, 6)

    def test_29b_no_permite_dos_refundiciones(self):
        self._asiento(condic=1)
        procesar_cierre_ejercicio(self.ejercicio.pk, self.empresa.pk, self.usuario)
        self._asiento(condic=1)
        with self.assertRaises(ValueError):
            procesar_cierre_ejercicio(self.ejercicio.pk, self.empresa.pk, self.usuario)

    def test_29c_la_deteccion_no_depende_del_concepto(self):
        """Renombrar el asiento no debe habilitar una segunda refundición."""
        self._asiento(condic=1)
        refundicion = procesar_cierre_ejercicio(self.ejercicio.pk, self.empresa.pk, self.usuario)
        Asiento.objects.filter(pk=refundicion.pk).update(concepto="AJUSTE ANUAL DE RESULTADOS")

        self._asiento(condic=1)
        with self.assertRaises(ValueError):
            procesar_cierre_ejercicio(self.ejercicio.pk, self.empresa.pk, self.usuario)

    def test_31_la_refundicion_entra_al_periodo_del_balance(self):
        """El balance al cierre debe reflejar la refundición: cuentas de resultado en cero."""
        from contable.views_htmx import _calcular_balance

        self._asiento(condic=1, monto="5000.00")
        procesar_cierre_ejercicio(self.ejercicio.pk, self.empresa.pk, self.usuario)

        contexto = _calcular_balance(
            self.empresa.pk,
            fecha_desde=self.ejercicio.inicio,
            fecha_hasta=self.ejercicio.cierre,
        )
        saldos = {f['cuenta'].id: f['saldo'] for f in contexto['balance']}
        self.assertEqual(saldos.get(self.cta_ventas.id, Decimal("0.00")), Decimal("0.00"))
        # Y la ganancia quedó en Resultado del Ejercicio.
        self.assertEqual(saldos.get(self.cta_resultado.id), Decimal("-5000.00"))


class LibroIvaPorCondicTests(CondicBaseTestCase):
    """30: el subsistema fiscal se puebla con condic in (1, 3).

    El `3` (Ajuste) es una factura válida a nombre de la empresa que el dueño pagó con fondos
    propios: no es gasto de la empresa, pero la factura le pertenece y se computa en IVA y
    Ganancias. Ésa es la razón de que alimente el Libro IVA igual que el `1`.

    Arma sus propias fixtures en vez de heredar de `ContabilizacionTestCase`: heredar de una
    TestCase con métodos de test los vuelve a correr dentro de este módulo.
    """

    def setUp(self):
        super().setUp()
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, nombre="Casa Central",
            direccion="Calle 1", telefono="0381-000000",
        )
        self.cta_proveedores = Cuenta.objects.create(
            jerarquia="211001", cuenta="PROVEEDORES", imputable=1, tipo="P", empresa=self.empresa,
        )
        self.cta_iva_credito = Cuenta.objects.create(
            jerarquia="113101", cuenta="IVA CREDITO FISCAL",
            imputable=1, tipo="A", empresa=self.empresa,
        )
        self.cta_compras = Cuenta.objects.create(
            jerarquia="510001", cuenta="COMPRAS MERCADERIAS",
            imputable=1, tipo="R", empresa=self.empresa,
        )
        ParametrosContables.objects.create(
            empresa=self.empresa,
            cta_iva_credito=self.cta_iva_credito,
            cta_compras=self.cta_compras,
            cta_proveedores_default=self.cta_proveedores,
            cta_resultado_ejercicio=self.cta_resultado,
        )
        self.rubro = Rubro.objects.create(empresa=self.empresa, detalle="Rubro General", margen=30)
        self.producto = Producto.objects.create(
            empresa=self.empresa, detalle="Mercadería", rubro=self.rubro, alic_iva=21.0,
        )
        self.proveedor = ClienteProveedor.objects.create(
            razon_social="PROVEEDOR SA", tipo_documento="80", cuit="30112223334",
            tipo_entidad=2, empresa=self.empresa,
        )
        self.tipo_factura_a, _ = TipoComprobante.objects.get_or_create(
            codigo="FAC", defaults={'detalle': "Factura A", 'signo': 1},
        )

    def _compra(self, condic, numero):
        compra = Compra.objects.create(
            fecha=timezone.datetime(2026, 5, 20).date(),
            tipo=self.tipo_factura_a, punto=1, numero=numero, condic=condic,
            proveedor=self.proveedor,
            neto=Decimal("1000.00"), iva=Decimal("210.00"),
            total=Decimal("1210.00"), saldo=Decimal("1210.00"),
            usuario=self.usuario, sucursal=self.sucursal,
            empresa=self.empresa, ejercicio=self.ejercicio,
        )
        CompraItem.objects.create(
            compra=compra, producto=self.producto,
            cantidad=Decimal("10.00"), precio_unitario=Decimal("100.00"),
            iva_alicuota=Decimal("21.00"), total=Decimal("1000.00"),
        )
        compra.save()
        return compra

    def _tiene_libro_iva(self, compra):
        return LibroIvaCompras.objects.filter(
            empresa=self.empresa, asiento_id=compra.asiento_id
        ).exists()

    def test_30_condic_1_y_3_alimentan_el_libro_iva(self):
        for condic, numero in ((1, 5001), (3, 5003)):
            with self.subTest(condic=condic):
                compra = self._compra(condic, numero)
                self.assertTrue(
                    self._tiene_libro_iva(compra),
                    f"condic={condic} deberia generar registro en Libro IVA",
                )
                # Y el desglose por alicuota, que es lo que arma el TXT de ARCA.
                self.assertTrue(
                    LibroIvaAlic.objects.filter(asiento_id=compra.asiento_id, c_v='C').exists()
                )

    def test_30b_condic_2_y_4_no_alimentan_el_libro_iva(self):
        for condic, numero in ((2, 5002), (4, 5004)):
            with self.subTest(condic=condic):
                compra = self._compra(condic, numero)
                self.assertFalse(
                    self._tiene_libro_iva(compra),
                    f"condic={condic} NO debe generar registro en Libro IVA",
                )
                self.assertFalse(
                    LibroIvaAlic.objects.filter(asiento_id=compra.asiento_id, c_v='C').exists()
                )

    def test_30c_el_asiento_hereda_el_condic_del_comprobante(self):
        """Regla inflexible de `.cursorrules`: nunca un valor calculado ni hardcodeado."""
        for condic, numero in ((1, 5011), (2, 5012), (3, 5013), (4, 5014)):
            with self.subTest(condic=condic):
                compra = self._compra(condic, numero)
                self.assertEqual(Asiento.objects.get(pk=compra.asiento_id).condic, condic)


class DataMigrationTests(CondicBaseTestCase):
    """33: la data migration reetiqueta 3->5 y las refundiciones históricas a 6.

    Se invocan las funciones de la migración con el registro real de modelos: el modelo histórico
    tiene la misma forma que el actual para los campos que toca (`condic`, `concepto`), así que la
    prueba es fiel sin necesidad de un migrador.
    """

    def _crear_crudo(self, condic, concepto, numero_dia):
        """Asiento creado por ORM directo, salteando `crear_asiento`, para simular datos previos."""
        return Asiento.objects.create(
            empresa=self.empresa,
            ejercicio=self.ejercicio,
            fecha=timezone.datetime(2026, 6, numero_dia).date(),
            concepto=concepto,
            condic=condic,
            monto=Decimal("100.00"),
            modulo=1,
        )

    def test_33_reetiqueta_apertura_y_refundicion(self):
        apertura = self._crear_crudo(3, "ASIENTO DE APERTURA MIGRADO", 1)
        refundicion = self._crear_crudo(1, "CIERRE DE EJERCICIO Ejercicio 2026", 2)
        normal = self._crear_crudo(1, "VENTA DEL DIA", 3)
        presupuestado = self._crear_crudo(2, "GASTO SIN FACTURA", 4)

        renumerar_condic(django_apps, None)

        for obj, esperado in (
            (apertura, 5), (refundicion, 6), (normal, 1), (presupuestado, 2),
        ):
            obj.refresh_from_db()
            self.assertEqual(obj.condic, esperado)

    def test_33b_es_idempotente(self):
        apertura = self._crear_crudo(3, "APERTURA", 1)
        normal = self._crear_crudo(1, "VENTA DEL DIA", 2)

        renumerar_condic(django_apps, None)
        renumerar_condic(django_apps, None)

        apertura.refresh_from_db()
        normal.refresh_from_db()
        self.assertEqual(apertura.condic, 5)
        # Correr dos veces no debe arrastrar un asiento normal a otro valor.
        self.assertEqual(normal.condic, 1)

    def test_33c_no_toca_una_refundicion_ya_anulada_ni_ajena(self):
        # Un asiento presupuestado con ese concepto no es una refundición: sólo se migran los que
        # quedaron con el default 1.
        falso = self._crear_crudo(2, "CIERRE DE EJERCICIO manual", 5)
        renumerar_condic(django_apps, None)
        falso.refresh_from_db()
        self.assertEqual(falso.condic, 2)


class AperturaTests(CondicBaseTestCase):
    """El 5 es la apertura: `_calcular_balance` la separa del movimiento del período."""

    def test_el_condic_5_alimenta_la_apertura_y_no_el_periodo(self):
        from contable.views_htmx import _calcular_balance

        crear_asiento(
            empresa=self.empresa,
            fecha=self.ejercicio.inicio,
            concepto="ASIENTO DE APERTURA",
            condic=5,
            lineas=[
                {'cuenta': self.cta_caja, 'debe': Decimal("7000.00"), 'haber': Decimal("0.00")},
                {'cuenta': self.cta_resultado, 'debe': Decimal("0.00"), 'haber': Decimal("7000.00")},
            ],
            usuario=self.usuario,
        )

        contexto = _calcular_balance(
            self.empresa.pk,
            fecha_desde=self.ejercicio.inicio,
            fecha_hasta=self.ejercicio.cierre,
        )
        fila = next(f for f in contexto['balance'] if f['cuenta'].id == self.cta_caja.id)
        self.assertEqual(fila['apertura'], Decimal("7000.00"))
        # No se computó además como movimiento del período (sería contarlo dos veces).
        self.assertEqual(fila['periodo_debe'], Decimal("0.00"))
        self.assertEqual(fila['periodo_haber'], Decimal("0.00"))
