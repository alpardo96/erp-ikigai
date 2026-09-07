"""Plan 083 — humo de las pantallas de liquidación.

Recorre el circuito completo desde el cliente de prueba: elegir productor, previsualizar,
emitir, ver el detalle, imprimir y anular. Es la única forma de que un `{% url %}` mal escrito o
un filtro inexistente se caigan acá y no en producción.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from contable.models import Asiento, LibroIvaCompras
from verticalidades.agricola.tabaco.models import LiquidacionTabaco, RomaneoTabaco
from verticalidades.agricola.tabaco.services import liquidacion as liq_svc

from .test_plan083_liquidacion import LiquidacionBaseTestCase


class PantallasLiquidacionTests(LiquidacionBaseTestCase):

    def setUp(self):
        super().setUp()
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)
        sesion = self.client.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id      # el menú lateral lo exige
        sesion.save()

    # -- pantallas ----------------------------------------------------------

    def test_listado_renderiza(self):
        liq_svc.confirmar_liquidacion(self._preparar(), self.user)

        r = self.client.get(reverse('agro_liquidacion_listado'))

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'PRODUCTOR RI')

    def test_listado_ofrece_el_filtro_de_condicion(self):
        r = self.client.get(reverse('agro_liquidacion_listado'))

        self.assertContains(r, 'name="condic"')
        self.assertContains(r, 'Presupuestado')

    def test_grilla_filtra_por_letra(self):
        liq_svc.confirmar_liquidacion(self._preparar(), self.user)
        liq_svc.confirmar_liquidacion(self._preparar(self.monotributista), self.user)

        r = self.client.get(reverse('agro_liquidacion_grilla'), {'letra': 'B'})

        self.assertContains(r, 'PRODUCTOR MONO')
        self.assertNotContains(r, 'PRODUCTOR RI')

    def test_formulario_de_alta_renderiza(self):
        r = self.client.get(reverse('agro_liquidacion_nueva'))

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Emitir liquidación')

    def test_detalle_e_impresion_renderizan(self):
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)

        for nombre in ('agro_liquidacion_detalle', 'agro_liquidacion_imprimir'):
            with self.subTest(url=nombre):
                r = self.client.get(reverse(nombre, args=[liq.id]))
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, 'PRODUCTOR RI')

    def test_el_detalle_muestra_las_retenciones(self):
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)

        r = self.client.get(reverse('agro_liquidacion_detalle', args=[liq.id]))

        self.assertContains(r, 'RETENCION EEAOC')
        self.assertContains(r, '105.000,00')          # ret. IVA, en formato es-AR
        self.assertContains(r, '1.087.000,00')        # total

    def test_modal_de_anulacion_renderiza(self):
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)

        r = self.client.get(reverse('agro_liquidacion_anular', args=[liq.id]))

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'no se tocan')          # los fardos sobreviven

    # -- previsualización ---------------------------------------------------

    def test_pendientes_sin_productor_no_rompe(self):
        r = self.client.get(reverse('agro_liquidacion_pendientes'))

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Elegí un productor')

    def test_pendientes_lista_y_previsualiza(self):
        romaneo = self._romaneo()

        r = self.client.get(reverse('agro_liquidacion_pendientes'),
                            {'productor': self.productor.pk})

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f'{romaneo.numero:08d}')
        self.assertContains(r, 'Liquidación A')        # RI
        self.assertContains(r, '1.087.000,00')         # total previsualizado
        self.assertContains(r, 'RETENCION EEAOC')

    def test_la_previsualizacion_coincide_con_lo_emitido(self):
        """Lo que el operador ve y lo que se graba salen de la misma función."""
        self._romaneo()
        previa = self.client.get(reverse('agro_liquidacion_pendientes'),
                                 {'productor': self.productor.pk})
        self.assertContains(previa, '1.087.000,00')

        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)
        self.assertEqual(liq.total, Decimal('1087000.00'))

    def test_pendientes_de_monotributista_muestra_letra_b(self):
        self._romaneo(self.monotributista)

        r = self.client.get(reverse('agro_liquidacion_pendientes'),
                            {'productor': self.monotributista.pk})

        self.assertContains(r, 'Liquidación B')
        self.assertNotContains(r, 'RETENCION IVA')     # sólo aplica a RI

    def test_pendientes_no_muestra_romaneos_ya_liquidados(self):
        romaneo = self._romaneo()
        liq_svc.confirmar_liquidacion(self._preparar(romaneos=[romaneo]), self.user)

        r = self.client.get(reverse('agro_liquidacion_pendientes'),
                            {'productor': self.productor.pk})

        self.assertContains(r, 'no tiene romaneos confirmados sin liquidar')

    # -- emisión desde la pantalla -----------------------------------------

    def test_emitir_desde_el_formulario(self):
        romaneo = self._romaneo()

        r = self.client.post(reverse('agro_liquidacion_nueva'), {
            'productor': self.productor.pk, 'fecha': '2026-09-06',
            'romaneos': [romaneo.pk],
        })

        self.assertEqual(r.status_code, 302)
        liq = LiquidacionTabaco.objects.get()
        self.assertEqual(liq.estado, LiquidacionTabaco.CONFIRMADA)
        self.assertEqual(liq.letra, 'A')
        self.assertEqual(liq.total, Decimal('1087000.00'))
        # Y quedó contabilizada y en el Libro IVA.
        self.assertTrue(Asiento.objects.filter(pk=liq.asiento_id).exists())
        self.assertTrue(LibroIvaCompras.objects.filter(asiento_id=liq.asiento_id).exists())

    def test_emitir_sin_romaneos_avisa(self):
        r = self.client.post(reverse('agro_liquidacion_nueva'), {
            'productor': self.productor.pk, 'fecha': '2026-09-06',
        })

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'al menos un romaneo')
        self.assertFalse(LiquidacionTabaco.objects.exists())

    def test_emitir_respeta_el_numero_cargado(self):
        romaneo = self._romaneo()

        self.client.post(reverse('agro_liquidacion_nueva'), {
            'productor': self.productor.pk, 'fecha': '2026-09-06',
            'romaneos': [romaneo.pk], 'numero': 8877,
        })

        self.assertEqual(LiquidacionTabaco.objects.get().numero, 8877)

    def test_anular_desde_el_modal(self):
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)
        romaneo = liq.romaneos.first()

        r = self.client.post(reverse('agro_liquidacion_anular', args=[liq.id]),
                             {'motivo': 'Error de emisión'})

        self.assertEqual(r.status_code, 200)
        liq.refresh_from_db()
        romaneo.refresh_from_db()
        self.assertEqual(liq.estado, LiquidacionTabaco.ANULADA)
        self.assertEqual(romaneo.estado, RomaneoTabaco.CONFIRMADO)
        self.assertEqual(romaneo.fardos.count(), 1)

    def test_anular_sin_motivo_devuelve_el_formulario(self):
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)

        r = self.client.post(reverse('agro_liquidacion_anular', args=[liq.id]), {'motivo': ''})

        self.assertEqual(r.status_code, 200)
        liq.refresh_from_db()
        self.assertEqual(liq.estado, LiquidacionTabaco.CONFIRMADA)

    def test_una_emision_fallida_no_deja_romaneos_bloqueados(self):
        """El bug que motivó envolver preparar+confirmar en una sola transacción.

        Si la confirmación falla —acá, quitando el CAI en modo manual— y cada paso commiteara por
        su cuenta, el borrador quedaría reteniendo los romaneos para siempre.
        """
        from verticalidades.agricola.tabaco.models import ConfiguracionTabaco
        ConfiguracionTabaco.objects.filter(empresa=self.empresa).update(cai='')
        romaneo = self._romaneo()

        r = self.client.post(reverse('agro_liquidacion_nueva'), {
            'productor': self.productor.pk, 'fecha': '2026-09-06',
            'romaneos': [romaneo.pk],
        })

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'CAI')
        # Nada quedó grabado y el romaneo sigue disponible.
        self.assertFalse(LiquidacionTabaco.objects.exists())
        romaneo.refresh_from_db()
        self.assertIsNone(romaneo.liquidacion)
        self.assertEqual(romaneo.estado, RomaneoTabaco.CONFIRMADO)

        r2 = self.client.get(reverse('agro_liquidacion_pendientes'),
                             {'productor': self.productor.pk})
        self.assertContains(r2, f'{romaneo.numero:08d}')

    def test_la_liquidacion_aparece_en_el_libro_iva_del_erp(self):
        """El cierre del círculo: es todo el sentido de engancharse por `asiento_id`.

        La liquidación NO es una `Compra`, pero la pantalla de Libro IVA Compras del core la
        muestra igual, sin que se haya tocado una línea de `impuestos` ni de `contable`.
        """
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)

        r = self.client.get(reverse('impuestos:libro_iva_compras'), {'anio': 2026, 'mes': 9})

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'PRODUCTOR RI')
        self.assertContains(r, liq.productor.cuit)
        self.assertContains(r, '150')                     # código de comprobante ARCA
        # Los importes los formatea la plantilla del core; se verifica el contenido, no el estilo.
        self.assertContains(r, '1000000,00')              # neto gravado
        self.assertContains(r, '210000,00')               # IVA computable
        self.assertContains(r, '1087000,00')              # total

    # -- menú y aislamiento -------------------------------------------------

    def test_el_menu_muestra_las_liquidaciones(self):
        from verticalidades.agricola.core_agricola.models import EmpresaVertical
        EmpresaVertical.objects.create(empresa=self.empresa, hace_tabaco=True)

        r = self.client.get(reverse('agro_liquidacion_listado'))

        self.assertContains(r, reverse('agro_liquidacion_nueva'))

    def test_no_se_accede_a_una_liquidacion_de_otra_empresa(self):
        from empresas.models import Empresa, Sucursal
        otra = Empresa.objects.create(nombre="OTRO ACOPIO", cuit="30999999998")
        otra_suc = Sucursal.objects.create(empresa=otra, nombre="C")
        ajena = LiquidacionTabaco.objects.create(
            empresa=otra, sucursal=otra_suc, productor=self.productor, fecha=date(2026, 9, 6))

        for nombre in ('agro_liquidacion_detalle', 'agro_liquidacion_imprimir',
                       'agro_liquidacion_anular'):
            with self.subTest(url=nombre):
                self.assertEqual(
                    self.client.get(reverse(nombre, args=[ajena.id])).status_code, 404)
