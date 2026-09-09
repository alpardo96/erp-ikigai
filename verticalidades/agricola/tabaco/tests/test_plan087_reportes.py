"""Plan 087 — reportes oficiales y gerenciales del acopio (Etapa 6).

Lo que se protege:

1. Que la planilla FET tenga una fila por romaneo y que la suma de las filas reconstruya
   exactamente el comprobante, aunque una liquidación agrupe varios romaneos.
2. Que Ganancias aparezca recién después del pago — es la decisión DA-01.
3. Que el adicional NO entre en «a pagar»: hoy el circuito no lo paga (DA-05 abierta).
4. Que una retención nueva del maestro no rompa la planilla.
5. Que las existencias se reconstruyan a una fecha pasada y no lean el stock de hoy.
6. Que el libro una los dos orígenes de retención y excluya lo anulado.
7. Que esta etapa NO agregue ninguna tabla.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from verticalidades.agricola.tabaco.models import (LiquidacionTabaco, RetencionPago,
                                                   TipoRetencionTabaco)
from verticalidades.agricola.tabaco.services import acondicionamiento as ac_svc
from verticalidades.agricola.tabaco.services import lotes as lote_svc
from verticalidades.agricola.tabaco.services import reportes as rep
from verticalidades.agricola.tabaco.services import retenciones_libro as libro_svc
from verticalidades.agricola.tabaco.services import romaneo as rom_svc
from verticalidades.agricola.tabaco.services import tableros as tab_svc

from .test_plan086_lotes import LoteBaseTestCase


class ReportesBaseTestCase(LoteBaseTestCase):
    """Escenario de las etapas 0-5, más la caja y el efectivo para poder pagar."""

    def setUp(self):
        super().setUp()
        from tesoreria.models import MedioPago

        self.cta_caja = self._cuenta('111001', 'CAJA', 'A')
        self.efectivo = MedioPago.objects.create(
            empresa=self.empresa, codigo='EFE-ARS', nombre='EFECTIVO',
            categoria='EFE', cuenta_contable=self.cta_caja)

    def _liquidar(self, romaneos=None, fecha=date(2026, 9, 6)):
        from verticalidades.agricola.tabaco.services import liquidacion as liq_svc

        romaneos = romaneos or [self._romaneo_confirmado(kilos='1000')]
        liq = liq_svc.preparar_liquidacion(
            empresa=self.empresa, sucursal=self.sucursal, productor=self.productor,
            romaneos=romaneos, fecha=fecha, usuario=self.user)
        return liq_svc.confirmar_liquidacion(liq, self.user)

    def _pagar(self, liquidaciones, importe, fecha=date(2026, 9, 15)):
        """Paga en efectivo. La retención de Ganancias la agrega el servicio como medio `RET`."""
        from verticalidades.agricola.tabaco.services import pago as pago_svc

        calculo = pago_svc.calcular_ganancias(
            empresa=self.empresa, productor=self.productor,
            base_del_pago=sum(l.neto for l in liquidaciones), fecha=fecha)
        efectivo = Decimal(importe) - calculo['importe']

        return pago_svc.pagar_liquidaciones(
            empresa=self.empresa, sucursal=self.sucursal, productor=self.productor,
            liquidaciones=liquidaciones,
            medios=[{'medio_pago': self.efectivo, 'importe': efectivo}],
            fecha=fecha, usuario=self.user)


# ===========================================================================
# Planilla FET
# ===========================================================================

class PlanillaFETTests(ReportesBaseTestCase):

    def test_una_fila_por_romaneo(self):
        romaneos = [self._romaneo_confirmado(kilos='600'),
                    self._romaneo_confirmado(kilos='400')]
        self._liquidar(romaneos)

        filas = rep.planilla_fet(self.empresa.pk)

        self.assertEqual(len(filas), 2)
        self.assertEqual({f['kilos'] for f in filas},
                         {Decimal('600.00'), Decimal('400.00')})

    def test_las_retenciones_se_prorratean_y_reconstruyen_el_comprobante(self):
        """El dato existe a nivel comprobante; la suma de las filas tiene que devolverlo intacto."""
        romaneos = [self._romaneo_confirmado(kilos='600'),
                    self._romaneo_confirmado(kilos='400')]
        liq = self._liquidar(romaneos)

        filas = rep.planilla_fet(self.empresa.pk)
        totales = rep.totales_fet(filas)

        self.assertEqual(totales['importe'], liq.neto)
        self.assertEqual(totales['iva'], liq.iva)
        # `retenciones` de la planilla incluye Ganancias, que en la liquidación todavía no está.
        retenidas_al_liquidar = totales['retenciones'] - totales['ret_ganancias']
        self.assertEqual(retenidas_al_liquidar, liq.retenciones)

    def test_el_prorrateo_respeta_la_proporcion_de_kilos(self):
        """60/40 en kilos al mismo precio es 60/40 en IVA."""
        romaneos = [self._romaneo_confirmado(kilos='600'),
                    self._romaneo_confirmado(kilos='400')]
        liq = self._liquidar(romaneos)

        filas = {f['kilos']: f for f in rep.planilla_fet(self.empresa.pk)}

        self.assertEqual(filas[Decimal('600.00')]['iva'],
                         (liq.iva * Decimal('0.6')).quantize(Decimal('0.01')))
        self.assertEqual(filas[Decimal('400.00')]['iva'],
                         (liq.iva * Decimal('0.4')).quantize(Decimal('0.01')))

    def test_ganancias_es_cero_si_todavia_no_se_pago(self):
        """DA-01: Ganancias se practica al pagar. Estimarla sería declarar lo que no se retuvo."""
        self._liquidar()

        fila = rep.planilla_fet(self.empresa.pk)[0]

        self.assertEqual(fila['ret_ganancias'], Decimal('0.00'))

    def test_ganancias_aparece_despues_del_pago(self):
        liq = self._liquidar()
        self._pagar([liq], liq.total)

        fila = rep.planilla_fet(self.empresa.pk)[0]
        certificado = RetencionPago.objects.get(empresa=self.empresa, anulado=False)

        self.assertEqual(fila['ret_ganancias'], certificado.importe)

    def test_a_pagar_cierra_contra_la_liquidacion(self):
        liq = self._liquidar()

        totales = rep.totales_fet(rep.planilla_fet(self.empresa.pk))

        self.assertEqual(totales['a_pagar'], liq.total)

    def test_el_adicional_no_entra_en_a_pagar(self):
        """DA-05 cerrada: el adicional es un comodín que queda en cero y no se paga.

        El campo sobrevive en el modelo y en el servicio, pero la pantalla de carga no lo dibuja.
        Este test fija que, si alguien lo carga por API o importación, la planilla lo informa pero
        NO lo declara como pagado — que es lo que el comprobante dice.
        """
        romaneo = rom_svc.abrir_romaneo(
            empresa=self.empresa, sucursal=self.sucursal, productor=self.productor,
            variedad=self.burley, campania=self.campania, fecha=date(2026, 9, 1),
            usuario=self.user)
        rom_svc.agregar_fardo(romaneo, clase=self.b1f, kilos=Decimal('1000'),
                              adicional=Decimal('50000'), usuario=self.user)
        romaneo = rom_svc.confirmar_romaneo(romaneo, self.user)
        liq = self._liquidar([romaneo])

        fila = rep.planilla_fet(self.empresa.pk)[0]

        self.assertEqual(fila['adicional'], Decimal('50000.00'))     # se informa
        self.assertEqual(fila['a_pagar'], liq.total)                 # pero no se paga
        self.assertNotIn(Decimal('50000.00'), [liq.neto])

    def test_una_retencion_nueva_del_maestro_va_a_otras(self):
        """El maestro es extensible por diseño: la planilla no puede dejar de serlo."""
        TipoRetencionTabaco.objects.create(
            empresa=self.empresa, codigo='NUEVA', detalle='CONCEPTO NUEVO',
            organismo='ORGANISMO X', tipo_base=TipoRetencionTabaco.NETO,
            alicuota=Decimal('1.0'), momento=TipoRetencionTabaco.LIQUIDACION,
            cuenta_contable=self._cuenta('214999', 'NUEVA A DEPOSITAR', 'P'),
            vigencia_desde=date(2026, 1, 1), activa=True)

        liq = self._liquidar()
        fila = rep.planilla_fet(self.empresa.pk)[0]

        self.assertEqual(fila['otras_retenciones'], Decimal('10000.00'))   # 1 % de 1.000.000
        self.assertEqual(fila['a_pagar'], liq.total)                       # la fila sigue cerrando

    def test_excluye_las_liquidaciones_anuladas(self):
        from verticalidades.agricola.tabaco.services import liquidacion as liq_svc

        liq = self._liquidar()
        liq_svc.anular_liquidacion(liq, "Error de carga", self.user)

        self.assertEqual(rep.planilla_fet(self.empresa.pk), [])

    def test_filtra_por_condic(self):
        self._liquidar()

        self.assertEqual(len(rep.planilla_fet(self.empresa.pk, condic=1)), 1)
        self.assertEqual(len(rep.planilla_fet(self.empresa.pk, condic=2)), 0)

    def test_trae_el_codigo_fet_del_productor(self):
        from verticalidades.agricola.tabaco.models import ProductorTabaco

        ProductorTabaco.objects.create(cliente_proveedor=self.productor, empresa=self.empresa,
                                       codigo_fet='FET-0001')
        self._liquidar()

        self.assertEqual(rep.planilla_fet(self.empresa.pk)[0]['codigo_fet'], 'FET-0001')

    def test_sin_productor_tabaco_el_codigo_queda_vacio_y_no_falla(self):
        """La extensión sectorial es opcional: no tenerla no puede romper la declaración."""
        self._liquidar()

        self.assertEqual(rep.planilla_fet(self.empresa.pk)[0]['codigo_fet'], '')


# ===========================================================================
# Resumen de acopio
# ===========================================================================

class ResumenDeAcopioTests(ReportesBaseTestCase):

    def test_agrupa_por_variedad_y_clase(self):
        self._romaneo_confirmado(kilos='600')
        self._romaneo_confirmado(kilos='400')

        variedades = rep.resumen_de_acopio(self.empresa.pk)

        self.assertEqual(len(variedades), 1)
        self.assertEqual(variedades[0]['variedad'], 'BURLEY')
        self.assertEqual(variedades[0]['kilos'], Decimal('1000.00'))
        self.assertEqual(variedades[0]['fardos'], 2)
        self.assertEqual(len(variedades[0]['clases']), 1)

    def test_precio_promedio_ponderado_por_kilos(self):
        """Un fardo de 5 kg y otro de 500 no pesan lo mismo en el precio de la campaña."""
        self._romaneo_confirmado(kilos='1000')

        variedad = rep.resumen_de_acopio(self.empresa.pk)[0]

        self.assertEqual(variedad['precio_promedio'],
                         (variedad['importe'] / variedad['kilos']).quantize(Decimal('0.01')))

    def test_ignora_los_borradores(self):
        borrador = rom_svc.abrir_romaneo(
            empresa=self.empresa, sucursal=self.sucursal, productor=self.productor,
            variedad=self.burley, campania=self.campania, fecha=date(2026, 9, 1),
            usuario=self.user)
        rom_svc.agregar_fardo(borrador, clase=self.b1f, kilos=Decimal('500'), usuario=self.user)

        self.assertEqual(rep.resumen_de_acopio(self.empresa.pk), [])

    def test_filtra_por_condic(self):
        self._romaneo_confirmado(kilos='1000')

        self.assertEqual(len(rep.resumen_de_acopio(self.empresa.pk, condic=1)), 1)
        self.assertEqual(len(rep.resumen_de_acopio(self.empresa.pk, condic=2)), 0)


# ===========================================================================
# DDJJ de existencias
# ===========================================================================

class ExistenciasTests(ReportesBaseTestCase):

    def test_a_una_fecha_pasada_ignora_lo_posterior(self):
        """El stock del ERP sólo sabe el presente; la declaración necesita el pasado."""
        self._romaneo_confirmado(kilos='1000')      # fecha 2026-09-01

        antes = rep.existencias_a_fecha(self.empresa.pk, date(2026, 8, 31))
        despues = rep.existencias_a_fecha(self.empresa.pk, date(2026, 9, 30))

        self.assertEqual(antes, [])
        self.assertEqual(despues[0]['existencia'], Decimal('1000.00'))

    def test_descuenta_las_bajas_de_acondicionamiento(self):
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote, entrada='1000', salida='900')
        ac_svc.cerrar_acondicionamiento(acond, self.user)

        fila = rep.existencias_a_fecha(self.empresa.pk, date(2026, 9, 30))[0]

        self.assertEqual(fila['recibidos'], Decimal('1000.00'))
        self.assertEqual(fila['acondicionados'], Decimal('100.00'))
        self.assertEqual(fila['existencia'], Decimal('900.00'))

    def test_el_acondicionamiento_posterior_al_corte_no_cuenta(self):
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote, entrada='1000', salida='900')       # fecha 2026-09-12
        ac_svc.cerrar_acondicionamiento(acond, self.user)

        fila = rep.existencias_a_fecha(self.empresa.pk, date(2026, 9, 10))[0]

        self.assertEqual(fila['acondicionados'], Decimal('0.00'))
        self.assertEqual(fila['existencia'], Decimal('1000.00'))

    def test_totales(self):
        self._romaneo_confirmado(kilos='1000')

        filas = rep.existencias_a_fecha(self.empresa.pk, date(2026, 9, 30))

        self.assertEqual(rep.totales_existencias(filas)['existencia'], Decimal('1000.00'))


# ===========================================================================
# Libro de retenciones
# ===========================================================================

class LibroDeRetencionesTests(ReportesBaseTestCase):

    def test_une_los_dos_origenes(self):
        liq = self._liquidar()
        self._pagar([liq], liq.total)

        filas = libro_svc.libro(self.empresa.pk)
        origenes = {f['origen'] for f in filas}

        self.assertIn(libro_svc.LIQUIDACION, origenes)
        self.assertIn(libro_svc.PAGO, origenes)

    def test_solo_liquidar_si_no_se_pago(self):
        self._liquidar()

        filas = libro_svc.libro(self.empresa.pk)

        self.assertTrue(all(f['origen'] == libro_svc.LIQUIDACION for f in filas))

    def test_excluye_la_liquidacion_anulada(self):
        from verticalidades.agricola.tabaco.services import liquidacion as liq_svc

        liq = self._liquidar()
        liq_svc.anular_liquidacion(liq, "Error", self.user)

        self.assertEqual(libro_svc.libro(self.empresa.pk), [])

    def test_excluye_el_certificado_anulado(self):
        liq = self._liquidar()
        self._pagar([liq], liq.total)
        RetencionPago.objects.filter(empresa=self.empresa).update(anulado=True)

        filas = libro_svc.libro(self.empresa.pk)

        self.assertTrue(all(f['origen'] == libro_svc.LIQUIDACION for f in filas))

    def test_totales_por_organismo(self):
        self._liquidar()

        filas = libro_svc.libro(self.empresa.pk)
        por_organismo = libro_svc.totales_por_organismo(filas)

        self.assertEqual(sum(g['importe'] for g in por_organismo),
                         libro_svc.total_general(filas))
        self.assertTrue(all(g['cuenta'] for g in por_organismo))

    def test_filtra_por_concepto(self):
        self._liquidar()

        solo_eeaoc = libro_svc.libro(self.empresa.pk, codigo='EEAOC')

        self.assertTrue(solo_eeaoc)
        self.assertTrue(all(f['codigo'] == 'EEAOC' for f in solo_eeaoc))

    def test_filtra_por_condic(self):
        self._liquidar()

        self.assertTrue(libro_svc.libro(self.empresa.pk, condic=1))
        self.assertEqual(libro_svc.libro(self.empresa.pk, condic=2), [])


# ===========================================================================
# Tableros
# ===========================================================================

class TablerosTests(ReportesBaseTestCase):

    def _lote_vendido(self, kilos='1000', precio='1500'):
        from facturacion.models import TipoComprobante, Venta, VentaItem

        lote = self._lote_armado(kilos=kilos)
        tipo, _ = TipoComprobante.objects.get_or_create(
            codigo='087', defaults={'detalle': 'FACTURA A', 'signo': 1})
        self._nro = getattr(self, '_nro', 0) + 1
        venta = Venta.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, tipo=tipo, punto=2, numero=self._nro,
            fecha=date(2026, 9, 20), cliente=self.productor, usuario=self.user, estado=0, condic=1)
        VentaItem.objects.create(venta=venta, producto=self.producto, cantidad=Decimal(kilos),
                                 precio_unitario=Decimal(precio), iva_alicuota=Decimal('21'),
                                 total=Decimal(kilos) * Decimal(precio))
        return lote_svc.asignar_venta(lote, venta, self.user)

    def test_por_campania(self):
        lote = self._lote_vendido()

        filas = tab_svc.por_campania(self.empresa.pk)

        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]['rotulo'], self.campania.codigo)
        self.assertEqual(filas[0]['margen'], lote.margen)

    def test_por_productor(self):
        self._lote_vendido()

        filas = tab_svc.por_productor(self.empresa.pk)

        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]['rotulo'], 'PRODUCTOR RI')
        self.assertEqual(filas[0]['cuit'], self.productor.cuit)

    def test_por_clase(self):
        self._lote_vendido()

        filas = tab_svc.por_clase(self.empresa.pk)

        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]['rotulo'], 'B1F')

    def test_las_cuatro_agrupaciones_dan_el_mismo_margen_total(self):
        """Son lecturas del mismo margen: si difirieran, alguna estaría mal."""
        self._lote_vendido()

        margenes = {nombre: tab_svc.totales(funcion(self.empresa.pk))['margen']
                    for nombre, funcion in (('campania', tab_svc.por_campania),
                                            ('variedad', tab_svc.por_variedad),
                                            ('productor', tab_svc.por_productor),
                                            ('clase', tab_svc.por_clase))}

        self.assertEqual(len(set(margenes.values())), 1, margenes)

    def test_filtra_por_condic(self):
        self._lote_vendido()

        self.assertEqual(len(tab_svc.por_campania(self.empresa.pk, condic=1)), 1)
        self.assertEqual(len(tab_svc.por_campania(self.empresa.pk, condic=2)), 0)

    def test_el_porcentaje_total_se_recalcula_y_no_se_promedia(self):
        self._lote_vendido()

        filas = tab_svc.por_campania(self.empresa.pk)
        totales = tab_svc.totales(filas)

        esperado = (totales['margen'] / totales['costo_total'] * Decimal('100')).quantize(
            Decimal('0.01'))
        self.assertEqual(totales['margen_porcentaje'], esperado)


# ===========================================================================
# La propiedad que define la etapa
# ===========================================================================

class SinTablasNuevasTests(TestCase):

    def test_la_etapa_6_no_agrega_ninguna_tabla(self):
        """Si para emitir la planilla FET hiciera falta un campo, sería señal de que algo no se
        estaba capturando cuando correspondía. No hace falta ninguno.
        """
        from django.apps import apps

        esperadas = {
            # Etapa 0 — maestros
            'agricola_tabaco_configuracion', 'agricola_tabaco_variedad', 'agricola_tabaco_clase',
            'agricola_tabaco_lista_precio', 'agricola_tabaco_tipo_retencion',
            'agricola_tabaco_productor',
            # Etapa 1 — romaneo
            'agricola_tabaco_romaneo', 'agricola_tabaco_fardo', 'agricola_tabaco_reclasificacion',
            # Etapa 2 — liquidación
            'agricola_tabaco_liquidacion', 'agricola_tabaco_liquidacion_detalle',
            'agricola_tabaco_liquidacion_retencion',
            # Etapa 3 — pago
            'agricola_tabaco_liquidacion_pago', 'agricola_tabaco_retencion_pago',
            # Etapa 5 — lotes y acondicionamiento
            'agricola_tabaco_lote', 'agricola_tabaco_proceso_acond',
            'agricola_tabaco_acondicionamiento', 'agricola_tabaco_acond_coproducto',
            'agricola_tabaco_acond_costo',
        }
        tablas = {m._meta.db_table for m in apps.get_app_config('tabaco').get_models()}

        self.assertEqual(tablas, esperadas, sorted(tablas ^ esperadas))


# ===========================================================================
# Las decisiones que el usuario cerró
# ===========================================================================

class DecisionesCerradasTests(ReportesBaseTestCase):

    def test_la_columna_fet_la_declara_el_maestro_y_no_se_adivina(self):
        """Los conceptos reales se llaman `RET-IVA`, `RET-GCIAS` y `USO AGUA`.

        Un mapa de códigos exactos los habría mandado a «otras» sin que nada fallara a la vista.
        La columna es un dato del maestro, editable desde el ABM.
        """
        esperado = {
            'RET-IVA': 'ret_iva',
            'RET-GCIAS': 'ret_ganancias',
            'EEAOC': 'ret_eeaoc',
            'SALUD': 'ret_salud',
            'USO AGUA': 'ret_agua',
        }
        for codigo, columna in esperado.items():
            with self.subTest(codigo=codigo):
                concepto = TipoRetencionTabaco.objects.get(empresa=self.empresa, codigo=codigo)
                self.assertEqual(rep.columna_de(concepto), columna)

    def test_cambiar_la_columna_en_el_maestro_cambia_la_planilla(self):
        """Es la prueba de que se corrige sin tocar código."""
        eeaoc = TipoRetencionTabaco.objects.get(empresa=self.empresa, codigo='EEAOC')
        eeaoc.columna_fet = 'otras'                  # el usuario la manda a «otras»
        eeaoc.save(update_fields=['columna_fet'])

        self._liquidar()
        fila = rep.planilla_fet(self.empresa.pk)[0]

        self.assertEqual(fila['ret_eeaoc'], Decimal('0.00'))
        self.assertEqual(fila['otras_retenciones'], Decimal('5000.00'))

    def test_un_concepto_sin_columna_declarada_se_deduce(self):
        """La red para lo que entre por importación sin pasar por el ABM."""
        nuevo = TipoRetencionTabaco.objects.create(
            empresa=self.empresa, codigo='X-SALUD-2', detalle='OTRA DE SALUD PUBLICA',
            tipo_base=TipoRetencionTabaco.NETO, alicuota=Decimal('0.1'),
            momento=TipoRetencionTabaco.LIQUIDACION,
            cuenta_contable=self._cuenta('214777', 'OTRA SALUD', 'P'),
            vigencia_desde=date(2026, 1, 1), activa=True)

        self.assertEqual(nuevo.columna_fet, '')
        self.assertEqual(rep.columna_de(nuevo), 'ret_salud')

    def test_el_alta_de_romaneo_no_deja_elegir_la_condicion(self):
        """Toda liquidación de tabaco es fiscal: un Presupuestado desaparecería de la planilla."""
        from django import forms as django_forms

        from verticalidades.agricola.tabaco.forms_romaneo import AbrirRomaneoForm

        form = AbrirRomaneoForm(self.empresa.pk)

        self.assertIsInstance(form.fields['condic'].widget, django_forms.HiddenInput)
        self.assertEqual(form.fields['condic'].initial, 1)

    def test_la_carga_de_fardos_no_dibuja_el_adicional(self):
        """Un campo que se puede llenar y nunca se cobra miente en silencio."""
        from django import forms as django_forms

        from verticalidades.agricola.tabaco.forms_romaneo import FardoForm

        form = FardoForm()

        self.assertIsInstance(form.fields['adicional'].widget, django_forms.HiddenInput)
