"""Plan 086 — humo de las pantallas de lotes, acondicionamiento y margen.

Recorre el circuito desde el cliente de prueba: crear el lote, armarlo con fardos por el
typeahead, acondicionarlo con costos y coproductos, cerrarlo, vincular la venta y leer el margen.

También fija las reglas de UX del proyecto: filtro de `condic` en todo listado con importes y
formato es-AR en los displays.
"""
from datetime import date
from decimal import Decimal

from django.urls import reverse

from verticalidades.agricola.tabaco.models import (Acondicionamiento, FardoTabaco, LoteAcopio,
                                                   ProcesoAcondicionamiento)
from verticalidades.agricola.tabaco.services import acondicionamiento as ac_svc
from verticalidades.agricola.tabaco.services import lotes as lote_svc

from .test_plan086_lotes import LoteBaseTestCase


class PantallasBaseTestCase(LoteBaseTestCase):

    def setUp(self):
        super().setUp()
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)
        sesion = self.client.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion.save()


class PantallasDeLoteTests(PantallasBaseTestCase):

    def test_listado_renderiza(self):
        self._lote_armado(kilos='1000')

        r = self.client.get(reverse('agro_lote_listado'))

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'LOTE TEST')

    def test_listado_ofrece_el_filtro_de_condicion(self):
        """Regla del proyecto: todo listado con importes lo ofrece."""
        r = self.client.get(reverse('agro_lote_listado'))

        self.assertContains(r, 'name="condic"')
        self.assertContains(r, 'Presupuestado')

    def test_la_grilla_respeta_el_filtro_de_estado(self):
        self._lote_armado(kilos='1000')

        armados = self.client.get(reverse('agro_lote_grilla'),
                                  {'estado': LoteAcopio.ARMADO})
        borradores = self.client.get(reverse('agro_lote_grilla'),
                                     {'estado': LoteAcopio.BORRADOR})

        self.assertContains(armados, 'LOTE TEST')
        self.assertNotContains(borradores, 'LOTE TEST')

    def test_alta_crea_el_lote_y_lleva_al_detalle(self):
        r = self.client.post(reverse('agro_lote_nuevo'), {
            'sucursal': self.sucursal.pk,
            'variedad': self.burley.pk,
            'campania': self.campania.pk,
            'fecha': '2026-09-10',
            'descripcion': 'LOTE POR PANTALLA',
            'observaciones': '',
        })

        lote = LoteAcopio.objects.get(descripcion='LOTE POR PANTALLA')
        self.assertRedirects(r, reverse('agro_lote_detalle', args=[lote.pk]))
        self.assertEqual(lote.estado, LoteAcopio.BORRADOR)

    def test_el_typeahead_lista_los_fardos_disponibles(self):
        romaneo = self._romaneo_confirmado(kilos='1000')
        lote = self._lote()

        r = self.client.get(reverse('agro_lote_fardo_typeahead', args=[lote.pk]))

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f'Fardo {romaneo.fardos.first().numero_fardo}')

    def test_el_typeahead_deja_de_ofrecer_el_fardo_ya_agrupado(self):
        romaneo = self._romaneo_confirmado(kilos='1000')
        lote = self._lote()
        lote_svc.agregar_fardo(lote, romaneo.fardos.first(), self.user)

        r = self.client.get(reverse('agro_lote_fardo_typeahead', args=[lote.pk]))

        self.assertContains(r, 'No hay fardos disponibles')

    def test_agregar_fardo_por_pantalla(self):
        romaneo = self._romaneo_confirmado(kilos='1000')
        lote = self._lote()

        r = self.client.post(reverse('agro_lote_fardo_agregar', args=[lote.pk]),
                             {'fardo': romaneo.fardos.first().pk})

        self.assertEqual(r.status_code, 200)
        lote.refresh_from_db()
        self.assertEqual(lote.total_fardos, 1)

    def test_el_error_de_negocio_se_muestra_sin_romper_la_grilla(self):
        """Un fardo de otra variedad: la pantalla avisa y el panel queda consistente."""
        from verticalidades.agricola.tabaco.models import (ClaseTabaco, ListaPrecioTabaco,
                                                           VariedadTabaco)
        from verticalidades.agricola.tabaco.services import romaneo as rom_svc

        virginia = VariedadTabaco.objects.create(empresa=self.empresa, codigo=2, detalle='VIRGINIA')
        clase = ClaseTabaco.objects.create(empresa=self.empresa, variedad=virginia, codigo=1,
                                           detalle='V1', coeficiente=Decimal('1'))
        ListaPrecioTabaco.objects.create(
            empresa=self.empresa, variedad=virginia, campania=self.campania,
            vigencia_desde=date(2026, 1, 1), precio_ponderante=Decimal('900'), aprobada=True)
        otro = rom_svc.abrir_romaneo(
            empresa=self.empresa, sucursal=self.sucursal, productor=self.productor,
            variedad=virginia, campania=self.campania, fecha=date(2026, 9, 1), usuario=self.user)
        rom_svc.agregar_fardo(otro, clase=clase, kilos=Decimal('400'), usuario=self.user)
        otro = rom_svc.confirmar_romaneo(otro, self.user)

        lote = self._lote()
        r = self.client.post(reverse('agro_lote_fardo_agregar', args=[lote.pk]),
                             {'fardo': otro.fardos.first().pk})

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'una sola variedad')
        self.assertContains(r, 'panel-fardos')

    def test_quitar_fardo_por_pantalla(self):
        lote = self._lote_armado(kilos='1000')
        fardo = lote.fardos.first()

        self.client.post(reverse('agro_lote_fardo_quitar', args=[lote.pk, fardo.pk]))

        lote.refresh_from_db()
        self.assertEqual(lote.total_fardos, 0)

    def test_armar_desde_la_pantalla(self):
        romaneo = self._romaneo_confirmado(kilos='1000')
        lote = self._lote()
        lote_svc.agregar_fardo(lote, romaneo.fardos.first(), self.user)

        r = self.client.get(reverse('agro_lote_armar', args=[lote.pk]))

        self.assertRedirects(r, reverse('agro_lote_detalle', args=[lote.pk]))
        lote.refresh_from_db()
        self.assertEqual(lote.estado, LoteAcopio.ARMADO)
        self.assertIsNotNone(lote.numero)

    def test_el_detalle_muestra_importes_en_formato_argentino(self):
        """Regla del proyecto: nunca se formatea a mano, siempre `|formato_ar`."""
        lote = self._lote_armado(kilos='1000')

        r = self.client.get(reverse('agro_lote_detalle', args=[lote.pk]))

        self.assertContains(r, '1.000.000,00')

    def test_anular_por_pantalla_libera_los_fardos(self):
        lote = self._lote_armado(kilos='1000')
        fardo_id = lote.fardos.first().pk

        r = self.client.post(reverse('agro_lote_anular', args=[lote.pk]),
                             {'motivo': 'Se rearma'})

        self.assertEqual(r.status_code, 200)
        self.assertIn('HX-Redirect', r)
        self.assertIsNone(FardoTabaco.objects.get(pk=fardo_id).lote_id)

    def test_anular_sin_motivo_devuelve_el_modal_con_el_error(self):
        lote = self._lote_armado(kilos='1000')

        r = self.client.post(reverse('agro_lote_anular', args=[lote.pk]), {'motivo': ''})

        self.assertEqual(r.status_code, 200)
        self.assertNotIn('HX-Redirect', r)
        lote.refresh_from_db()
        self.assertEqual(lote.estado, LoteAcopio.ARMADO)

    def test_no_se_ve_un_lote_de_otra_empresa(self):
        from empresas.models import Empresa, Sucursal

        ajena = Empresa.objects.create(nombre="OTRA", cuit="30999999993",
                                       tipo_actividad='AGRICOLA')
        suc = Sucursal.objects.create(empresa=ajena, nombre="X", punto=1)
        from verticalidades.agricola.core_agricola.models import Campania
        from verticalidades.agricola.tabaco.models import VariedadTabaco

        camp = Campania.objects.create(empresa=ajena, codigo='2026/2027', detalle='X',
                                       fecha_inicio=date(2026, 1, 1))
        var = VariedadTabaco.objects.create(empresa=ajena, codigo=1, detalle='BURLEY')
        otro = LoteAcopio.objects.create(empresa=ajena, sucursal=suc, campania=camp,
                                         variedad=var, fecha=date(2026, 9, 1))

        r = self.client.get(reverse('agro_lote_detalle', args=[otro.pk]))

        self.assertEqual(r.status_code, 404)


class PantallasDeAcondicionamientoTests(PantallasBaseTestCase):

    def test_alta_de_acondicionamiento(self):
        lote = self._lote_armado(kilos='1000')

        r = self.client.post(reverse('agro_acond_nuevo', args=[lote.pk]), {
            'proceso': self.despalillado.pk,
            'fecha': '2026-09-12',
            'kilos_entrada': '1.000,00',
            'kilos_salida': '950,00',
            'motivo_merma': '',
            'observaciones': '',
        })

        acond = Acondicionamiento.objects.get(lote=lote)
        self.assertRedirects(r, reverse('agro_acond_detalle', args=[acond.pk]))
        self.assertEqual(acond.kilos_merma, Decimal('50.00'))
        self.assertEqual(acond.estado, Acondicionamiento.BORRADOR)

    def test_los_kilos_se_leen_en_formato_argentino(self):
        """`1.000,00` tiene que interpretarse como mil, no como uno."""
        lote = self._lote_armado(kilos='1000')

        self.client.post(reverse('agro_acond_nuevo', args=[lote.pk]), {
            'proceso': self.despalillado.pk, 'fecha': '2026-09-12',
            'kilos_entrada': '1.000,00', 'kilos_salida': '950,50',
            'motivo_merma': '', 'observaciones': ''})

        acond = Acondicionamiento.objects.get(lote=lote)
        self.assertEqual(acond.kilos_entrada, Decimal('1000.00'))
        self.assertEqual(acond.kilos_salida, Decimal('950.50'))

    def test_cargar_costo_y_coproducto_por_pantalla(self):
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote, entrada='1000', salida='900')

        self.client.post(reverse('agro_acond_costo_agregar', args=[acond.pk]),
                         {'concepto': 'Mano de obra', 'importe': '50.000,00'})
        r = self.client.post(reverse('agro_acond_coproducto_agregar', args=[acond.pk]),
                             {'producto': self.palo.pk, 'kilos': '80,00',
                              'valor_estimado': '4.000,00'})

        self.assertEqual(r.status_code, 200)
        acond.refresh_from_db()
        self.assertEqual(acond.costo_total, Decimal('50000.00'))
        self.assertEqual(acond.kilos_coproductos, Decimal('80.00'))
        self.assertEqual(acond.kilos_merma, Decimal('20.00'))

    def test_cerrar_sin_motivo_avisa_en_pantalla(self):
        """Cerrar llega por un enlace: el error vuelve al detalle entero, no como fragmento."""
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote, entrada='1000', salida='800', motivo_merma='')

        r = self.client.get(reverse('agro_acond_cerrar', args=[acond.pk]), follow=True)

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Indic')                 # «Indicá el motivo»
        acond.refresh_from_db()
        self.assertEqual(acond.estado, Acondicionamiento.BORRADOR)

    def test_armar_un_lote_vacio_vuelve_al_detalle_con_el_aviso(self):
        lote = self._lote()

        r = self.client.get(reverse('agro_lote_armar', args=[lote.pk]), follow=True)

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'sin fardos')
        lote.refresh_from_db()
        self.assertEqual(lote.estado, LoteAcopio.BORRADOR)

    def test_cerrar_por_pantalla_mueve_el_stock(self):
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote, entrada='1000', salida='900')

        r = self.client.get(reverse('agro_acond_cerrar', args=[acond.pk]))

        self.assertRedirects(r, reverse('agro_acond_detalle', args=[acond.pk]))
        self.assertEqual(self._stock(), Decimal('900.00'))

    def test_anular_por_pantalla_devuelve_el_stock(self):
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote, entrada='1000', salida='900')
        ac_svc.cerrar_acondicionamiento(acond, self.user)

        r = self.client.post(reverse('agro_acond_anular', args=[acond.pk]),
                             {'motivo': 'Mal pesado'})

        self.assertIn('HX-Redirect', r)
        self.assertEqual(self._stock(), Decimal('1000.00'))

    def test_el_typeahead_de_productos_responde(self):
        r = self.client.get(reverse('agro_producto_typeahead'), {'q': 'PALO'})

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'PALO DE TABACO')


class PantallasDeVentaYMargenTests(PantallasBaseTestCase):

    def _venta_de(self, lote, kilos='1000', precio='1500'):
        from facturacion.models import TipoComprobante, Venta, VentaItem

        tipo, _ = TipoComprobante.objects.get_or_create(
            codigo='086', defaults={'detalle': 'FACTURA A', 'signo': 1})
        venta = Venta.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, tipo=tipo, punto=2, numero=1,
            fecha=date(2026, 9, 20), cliente=self.productor, usuario=self.user, estado=0, condic=1)
        VentaItem.objects.create(venta=venta, producto=self.producto, cantidad=Decimal(kilos),
                                 precio_unitario=Decimal(precio), iva_alicuota=Decimal('21'),
                                 total=Decimal(kilos) * Decimal(precio))
        return venta

    def test_el_modal_de_venta_lista_las_candidatas(self):
        lote = self._lote_armado(kilos='1000')
        self._venta_de(lote)

        r = self.client.get(reverse('agro_lote_venta', args=[lote.pk]))

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'PRODUCTOR RI')

    def test_asignar_la_venta_por_pantalla(self):
        lote = self._lote_armado(kilos='1000')
        venta = self._venta_de(lote)

        r = self.client.post(reverse('agro_lote_venta', args=[lote.pk]), {'venta': venta.pk})

        self.assertIn('HX-Redirect', r)
        lote.refresh_from_db()
        self.assertEqual(lote.estado, LoteAcopio.VENDIDO)
        self.assertEqual(lote.importe_venta, Decimal('1500000.00'))

    def test_quitar_la_venta_por_pantalla(self):
        lote = self._lote_armado(kilos='1000')
        lote_svc.asignar_venta(lote, self._venta_de(lote), self.user)

        r = self.client.get(reverse('agro_lote_venta_quitar', args=[lote.pk]))

        self.assertRedirects(r, reverse('agro_lote_detalle', args=[lote.pk]))
        lote.refresh_from_db()
        self.assertIsNone(lote.venta_id)

    def test_el_reporte_de_margen_renderiza_con_totales(self):
        lote = self._lote_armado(kilos='1000')
        lote_svc.asignar_venta(lote, self._venta_de(lote), self.user)

        r = self.client.get(reverse('agro_margen'))

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Totales')
        self.assertContains(r, '1.500.000,00')

    def test_el_reporte_de_margen_ofrece_el_filtro_de_condicion(self):
        r = self.client.get(reverse('agro_margen'))

        self.assertContains(r, 'name="condic"')
        self.assertContains(r, 'Presupuestado')

    def test_la_grilla_de_margen_respeta_el_condic(self):
        lote = self._lote_armado(kilos='1000')
        lote_svc.asignar_venta(lote, self._venta_de(lote), self.user)

        con = self.client.get(reverse('agro_margen_grilla'), {'condic': '1'})
        sin = self.client.get(reverse('agro_margen_grilla'), {'condic': '2'})

        self.assertContains(con, '1.500.000,00')
        self.assertContains(sin, 'No hay lotes')

    def test_el_margen_por_fardo_renderiza(self):
        lote = self._lote_armado(kilos='1000')
        lote_svc.asignar_venta(lote, self._venta_de(lote), self.user)

        r = self.client.get(reverse('agro_margen_lote', args=[lote.pk]))

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Resumen por clase')
        self.assertContains(r, 'B1F')


class ConfiguracionDeProcesosTests(PantallasBaseTestCase):
    """El maestro que resuelve DA-07 tiene que estar operable sin Django Admin."""

    def test_la_pestania_de_procesos_renderiza(self):
        r = self.client.get(reverse('configuracion_index'), {'tab': 'agro_procesos'})

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'DESPALILLADO')

    def test_alta_de_proceso_por_el_modal(self):
        r = self.client.post(reverse('agro_proceso_add'), {
            'codigo': 'secado', 'detalle': 'SECADO', 'merma_normal_porcentaje': '3,500',
            'orden': '2', 'activo': 'on'})

        self.assertEqual(r.status_code, 200)
        proceso = ProcesoAcondicionamiento.objects.get(empresa=self.empresa, codigo='SECADO')
        self.assertEqual(proceso.merma_normal_porcentaje, Decimal('3.500'))

    def test_no_se_repite_el_codigo_en_la_misma_empresa(self):
        r = self.client.post(reverse('agro_proceso_add'), {
            'codigo': 'DESP', 'detalle': 'OTRO', 'merma_normal_porcentaje': '1,000',
            'orden': '0', 'activo': 'on'})

        self.assertContains(r, 'Ya hay un proceso con ese código')
        self.assertEqual(
            ProcesoAcondicionamiento.objects.filter(empresa=self.empresa, codigo='DESP').count(), 1)

    def test_no_se_borra_un_proceso_ya_usado(self):
        lote = self._lote_armado(kilos='1000')
        self._acond(lote)

        r = self.client.post(reverse('agro_proceso_del', args=[self.despalillado.pk]))

        self.assertContains(r, 'No se puede eliminar')
        self.assertTrue(ProcesoAcondicionamiento.objects.filter(pk=self.despalillado.pk).exists())

    def test_el_buscador_de_procesos_filtra(self):
        r = self.client.get(reverse('agro_proceso_buscar'), {'q': 'DESPAL'})
        vacio = self.client.get(reverse('agro_proceso_buscar'), {'q': 'ZZZZ'})

        self.assertContains(r, 'DESPALILLADO')
        self.assertContains(vacio, 'Todavía no hay procesos cargados')
