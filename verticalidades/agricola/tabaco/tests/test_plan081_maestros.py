"""Plan 081 — maestros del acopio de tabaco: importación, restricciones y formación de precio.

Lo que más importa acá es que el precio sea reproducible: el importe de una liquidación se tiene
que poder reconstruir desde la lista, la clase y el coeficiente, al centavo. Los casos de
`PrecioTests` son datos reales del sistema heredado (marzo 2024, Burley, ponderante 2.500).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.db.utils import IntegrityError
from django.test import TestCase

from empresas.models import Empresa
from verticalidades.agricola.core_agricola.models import Campania
from verticalidades.agricola.tabaco.models import (ClaseTabaco, ListaPrecioTabaco,
                                                   VariedadTabaco)
from verticalidades.agricola.tabaco.services.importacion_clases import (
    ErrorImportacion, importar_clases,
)
from verticalidades.agricola.tabaco.services.precios import (
    importe_de_linea, lista_vigente, precio_de_clase,
)

User = get_user_model()

CSV_CABECERA = "codigo;id_var;detalle;porciento\n"


def escribir_csv(tmp, filas, cabecera=CSV_CABECERA):
    """Escribe un CSV con el mismo formato que el maestro real: UTF-8 con BOM, `;`, coma decimal."""
    tmp.write_text(cabecera + "".join(filas), encoding='utf-8-sig', newline='')
    return tmp


class ImportacionClasesTests(TestCase):

    def setUp(self):
        self.empresa = Empresa.objects.create(nombre="ACOPIO TEST", cuit="30111111112")

    def _csv(self, nombre, filas, cabecera=CSV_CABECERA):
        from django.conf import settings
        ruta = settings.BASE_DIR / 'scratch' / nombre
        ruta.parent.mkdir(exist_ok=True)
        self.addCleanup(lambda: ruta.unlink(missing_ok=True))
        return escribir_csv(ruta, filas, cabecera)

    def test_carga_el_maestro_real_completo(self):
        """El CSV versionado del repo tiene que cargar 27 Burley + 48 Virginia."""
        from django.conf import settings
        ruta = settings.BASE_DIR / 'docs' / 'agricola' / 'tabaco_clase.csv'

        resultado = importar_clases(self.empresa, ruta)

        self.assertEqual(resultado.creadas, 75)
        self.assertEqual(resultado.variedades_creadas, 2)

        burley = VariedadTabaco.objects.get(empresa=self.empresa, codigo=1)
        virginia = VariedadTabaco.objects.get(empresa=self.empresa, codigo=2)
        self.assertEqual(burley.detalle, 'BURLEY')
        self.assertEqual(virginia.detalle, 'VIRGINIA')
        self.assertEqual(ClaseTabaco.objects.filter(variedad=burley).count(), 27)
        self.assertEqual(ClaseTabaco.objects.filter(variedad=virginia).count(), 48)

        coeficientes = ClaseTabaco.objects.filter(empresa=self.empresa).values_list(
            'coeficiente', flat=True)
        self.assertEqual(min(coeficientes), Decimal('0.1000'))
        self.assertEqual(max(coeficientes), Decimal('1.0500'))

    def test_es_idempotente(self):
        from django.conf import settings
        ruta = settings.BASE_DIR / 'docs' / 'agricola' / 'tabaco_clase.csv'

        importar_clases(self.empresa, ruta)
        segunda = importar_clases(self.empresa, ruta)

        self.assertEqual(segunda.creadas, 0)
        self.assertEqual(segunda.actualizadas, 0)
        self.assertEqual(segunda.sin_cambios, 75)
        self.assertEqual(ClaseTabaco.objects.filter(empresa=self.empresa).count(), 75)

    def test_actualiza_un_coeficiente_cambiado(self):
        ruta = self._csv('t081_a.csv', ["1;1;B1F;1\n", "2;1;B1FR;0,85\n"])
        importar_clases(self.empresa, ruta)

        escribir_csv(ruta, ["1;1;B1F;1\n", "2;1;B1FR;0,90\n"])
        resultado = importar_clases(self.empresa, ruta)

        self.assertEqual(resultado.actualizadas, 1)
        self.assertEqual(resultado.sin_cambios, 1)
        self.assertEqual(
            ClaseTabaco.objects.get(empresa=self.empresa, codigo=2).coeficiente,
            Decimal('0.9000'))

    def test_deriva_el_grupo_de_la_primera_letra(self):
        """El grupo sale del dato, no de una lista fija: el sistema heredado se olvidaba del H."""
        ruta = self._csv('t081_g.csv', ["1;1;B1F;1\n", "73;2;H1F;1,05\n"])
        importar_clases(self.empresa, ruta)

        self.assertEqual(ClaseTabaco.objects.get(empresa=self.empresa, codigo=1).grupo, 'B')
        self.assertEqual(ClaseTabaco.objects.get(empresa=self.empresa, codigo=73).grupo, 'H')

    def test_rechaza_coeficiente_no_positivo_sin_escribir_nada(self):
        ruta = self._csv('t081_neg.csv', ["1;1;B1F;1\n", "2;1;B1FR;0\n"])

        with self.assertRaises(ErrorImportacion):
            importar_clases(self.empresa, ruta)
        self.assertEqual(ClaseTabaco.objects.count(), 0)
        self.assertEqual(VariedadTabaco.objects.count(), 0)

    def test_rechaza_codigo_duplicado(self):
        ruta = self._csv('t081_dup.csv', ["1;1;B1F;1\n", "1;1;B2F;0,92\n"])

        with self.assertRaises(ErrorImportacion):
            importar_clases(self.empresa, ruta)
        self.assertEqual(ClaseTabaco.objects.count(), 0)

    def test_rechaza_clase_repetida_en_la_misma_variedad(self):
        """Es exactamente el caso `N5K` del maestro heredado: dos códigos, misma clase."""
        ruta = self._csv('t081_n5k.csv', ["38;2;N5K;0,17\n", "72;2;N5K;0,15\n"])

        with self.assertRaises(ErrorImportacion) as ctx:
            importar_clases(self.empresa, ruta)
        self.assertIn('N5K', str(ctx.exception))
        self.assertEqual(ClaseTabaco.objects.count(), 0)

    def test_rechaza_variedad_desconocida(self):
        ruta = self._csv('t081_var.csv', ["1;7;B1F;1\n"])

        with self.assertRaises(ErrorImportacion):
            importar_clases(self.empresa, ruta)

    def test_rechaza_cabecera_distinta(self):
        ruta = self._csv('t081_cab.csv', ["1,1,B1F,1\n"], cabecera="codigo,id_var,detalle,porciento\n")

        with self.assertRaises(ErrorImportacion):
            importar_clases(self.empresa, ruta)

    def test_dry_run_no_escribe(self):
        ruta = self._csv('t081_dry.csv', ["1;1;B1F;1\n"])

        resultado = importar_clases(self.empresa, ruta, dry_run=True)

        self.assertEqual(resultado.creadas, 1)          # informa lo que HARÍA
        self.assertEqual(ClaseTabaco.objects.count(), 0)  # pero no lo hizo

    def test_comando_falla_con_empresa_inexistente(self):
        with self.assertRaises(CommandError):
            call_command('importar_clases_tabaco', empresa=999999)


class RestriccionesTests(TestCase):

    def setUp(self):
        self.empresa = Empresa.objects.create(nombre="ACOPIO TEST", cuit="30111111112")
        self.variedad = VariedadTabaco.objects.create(
            empresa=self.empresa, codigo=1, detalle='BURLEY')

    def test_coeficiente_debe_ser_positivo(self):
        with self.assertRaises(IntegrityError):
            ClaseTabaco.objects.create(empresa=self.empresa, variedad=self.variedad,
                                       codigo=1, detalle='B1F', coeficiente=Decimal('0'))

    def test_codigo_unico_por_variedad(self):
        ClaseTabaco.objects.create(empresa=self.empresa, variedad=self.variedad,
                                   codigo=1, detalle='B1F', coeficiente=Decimal('1'))
        with self.assertRaises(IntegrityError):
            ClaseTabaco.objects.create(empresa=self.empresa, variedad=self.variedad,
                                       codigo=1, detalle='B2F', coeficiente=Decimal('0.92'))

    def test_misma_clase_puede_existir_en_otra_variedad(self):
        """`B1F` vale 1,00 en Burley y también en Virginia: son la clase índice de cada una."""
        virginia = VariedadTabaco.objects.create(empresa=self.empresa, codigo=2, detalle='VIRGINIA')
        ClaseTabaco.objects.create(empresa=self.empresa, variedad=self.variedad,
                                   codigo=1, detalle='B1F', coeficiente=Decimal('1'))
        ClaseTabaco.objects.create(empresa=self.empresa, variedad=virginia,
                                   codigo=56, detalle='B1F', coeficiente=Decimal('1'))

        self.assertEqual(ClaseTabaco.objects.filter(detalle='B1F').count(), 2)

    def test_campania_con_fin_anterior_al_inicio_es_rechazada(self):
        with self.assertRaises(IntegrityError):
            Campania.objects.create(
                empresa=self.empresa, codigo='2026/2027', detalle='TEST',
                fecha_inicio=date(2026, 6, 1), fecha_fin=date(2026, 5, 1))

    def test_precio_ponderante_debe_ser_positivo(self):
        campania = Campania.objects.create(
            empresa=self.empresa, codigo='2026/2027', detalle='TEST',
            fecha_inicio=date(2026, 6, 1))
        with self.assertRaises(IntegrityError):
            ListaPrecioTabaco.objects.create(
                empresa=self.empresa, variedad=self.variedad, campania=campania,
                vigencia_desde=date(2026, 6, 1), precio_ponderante=Decimal('0'))


class PrecioTests(TestCase):
    """Casos reales del sistema heredado: marzo 2024, Burley, ponderante 2.500."""

    CASOS = [
        # (clase, coeficiente, precio esperado, kilos, importe esperado)
        ('B1F',  '1',    '2500.00', '750', '1875000.00'),
        ('B1FR', '0.85', '2125.00',  '76',  '161500.00'),
        ('B2F',  '0.92', '2300.00', '565', '1299500.00'),
        ('B3F',  '0.78', '1950.00',  '36',   '70200.00'),
        ('C1F',  '0.96', '2400.00', '576', '1382400.00'),
        ('C2F',  '0.86', '2150.00', '843', '1812450.00'),
    ]

    def setUp(self):
        self.empresa = Empresa.objects.create(nombre="ACOPIO TEST", cuit="30111111112")
        self.variedad = VariedadTabaco.objects.create(
            empresa=self.empresa, codigo=1, detalle='BURLEY')
        self.campania = Campania.objects.create(
            empresa=self.empresa, codigo='2023/2024', detalle='TEST',
            fecha_inicio=date(2024, 1, 1))
        self.lista = ListaPrecioTabaco.objects.create(
            empresa=self.empresa, variedad=self.variedad, campania=self.campania,
            vigencia_desde=date(2024, 3, 1), precio_ponderante=Decimal('2500.00'),
            aprobada=True)

    def test_precio_e_importe_contra_datos_reales(self):
        for n, (nombre, coef, precio_esp, kilos, importe_esp) in enumerate(self.CASOS, start=1):
            with self.subTest(clase=nombre):
                clase = ClaseTabaco.objects.create(
                    empresa=self.empresa, variedad=self.variedad, codigo=n,
                    detalle=nombre, coeficiente=Decimal(coef))

                precio = precio_de_clase(self.lista, clase)
                self.assertEqual(precio, Decimal(precio_esp))
                self.assertEqual(importe_de_linea(precio, Decimal(kilos)),
                                 Decimal(importe_esp))

    def test_lista_vigente_devuelve_la_aprobada(self):
        encontrada = lista_vigente(self.empresa.id, self.variedad, self.campania,
                                   date(2024, 3, 15))
        self.assertEqual(encontrada, self.lista)

    def test_no_devuelve_lista_en_borrador(self):
        """Un ponderante todavía en negociación no puede formar precios."""
        self.lista.aprobada = False
        self.lista.save(update_fields=['aprobada'])

        self.assertIsNone(lista_vigente(self.empresa.id, self.variedad, self.campania,
                                        date(2024, 3, 15)))

    def test_no_devuelve_lista_futura_ni_vencida(self):
        self.assertIsNone(lista_vigente(self.empresa.id, self.variedad, self.campania,
                                        date(2024, 2, 1)))

        self.lista.vigencia_hasta = date(2024, 3, 31)
        self.lista.save(update_fields=['vigencia_hasta'])
        self.assertIsNone(lista_vigente(self.empresa.id, self.variedad, self.campania,
                                        date(2024, 4, 1)))

    def test_gana_la_vigencia_mas_reciente(self):
        nueva = ListaPrecioTabaco.objects.create(
            empresa=self.empresa, variedad=self.variedad, campania=self.campania,
            vigencia_desde=date(2024, 3, 10), precio_ponderante=Decimal('2800.00'),
            aprobada=True)

        self.assertEqual(
            lista_vigente(self.empresa.id, self.variedad, self.campania, date(2024, 3, 15)),
            nueva)

    def test_aislamiento_multiempresa(self):
        """Una empresa no puede formar precios con la lista de otra."""
        otra = Empresa.objects.create(nombre="OTRO ACOPIO", cuit="30999999998")

        self.assertIsNone(lista_vigente(otra.id, self.variedad, self.campania,
                                        date(2024, 3, 15)))

    def test_vigencia_sin_corte_sigue_vigente(self):
        lejos = date(2024, 3, 1) + timedelta(days=900)
        self.assertEqual(
            lista_vigente(self.empresa.id, self.variedad, self.campania, lejos),
            self.lista)
