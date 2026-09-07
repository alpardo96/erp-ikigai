"""Plan 084 — humo de las pantallas de pago.

Recorre el circuito desde el cliente de prueba: elegir productor, previsualizar la retención,
emitir la Orden de Pago, ver el detalle, imprimir el certificado y anular.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from contable.models import Asiento
from tesoreria.models import MovimientoCajaDetalle, OrdenPago
from verticalidades.agricola.tabaco.models import RetencionPago
from verticalidades.agricola.tabaco.services import pago as pago_svc

from .test_plan084_pago import PagoBaseTestCase


class PantallasPagoTests(PagoBaseTestCase):

    def setUp(self):
        super().setUp()
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)
        sesion = self.client.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion.save()

    # -- pantallas ----------------------------------------------------------

    def test_listado_renderiza(self):
        liq = self._liquidacion()
        self._pagar([liq], Decimal('1071480.00'))

        r = self.client.get(reverse('agro_pago_listado'))

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'PRODUCTOR RI')

    def test_listado_ofrece_el_filtro_de_condicion(self):
        r = self.client.get(reverse('agro_pago_listado'))

        self.assertContains(r, 'name="condic"')
        self.assertContains(r, 'Presupuestado')

    def test_el_listado_solo_muestra_pagos_de_tabaco(self):
        """Una OP común de tesorería no tiene por qué aparecer en esta pantalla."""
        ajena = OrdenPago.objects.create(
            empresa=self.empresa, sucursal=self.sucursal,
            ejercicio=self.empresa.ejercicios.first(),
            proveedor=self.monotributista, fecha=date(2026, 9, 10), punto=1,
            total=Decimal('500'))
        liq = self._liquidacion()
        propia = self._pagar([liq], Decimal('1071480.00'))

        # Se consulta la GRILLA y no la página: en la página el nombre aparece igual dentro del
        # combo de filtros, que lista a todos los terceros de la empresa.
        r = self.client.get(reverse('agro_pago_grilla'))

        self.assertContains(r, reverse('agro_pago_detalle', args=[propia.pk]))
        self.assertNotContains(r, reverse('agro_pago_detalle', args=[ajena.pk]))

    def test_formulario_de_alta_renderiza(self):
        r = self.client.get(reverse('agro_pago_nuevo'))

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Emitir Orden de Pago')
        self.assertContains(r, 'EFECTIVO')          # el medio de pago disponible

    def test_detalle_renderiza(self):
        liq = self._liquidacion()
        op = self._pagar([liq], Decimal('1071480.00'))

        r = self.client.get(reverse('agro_pago_detalle', args=[op.id]))

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'PRODUCTOR RI')
        self.assertContains(r, '15.520,00')          # la retención, en formato es-AR
        self.assertContains(r, 'Certificados de retención')

    def test_certificado_renderiza(self):
        liq = self._liquidacion()
        op = self._pagar([liq], Decimal('1071480.00'))
        cert = RetencionPago.objects.get(orden_pago=op)

        r = self.client.get(reverse('agro_pago_certificado', args=[cert.id]))

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Certificado de Retención')
        self.assertContains(r, 'Régimen 78')
        self.assertContains(r, '224.000,00')         # mínimo no imponible
        self.assertContains(r, '15.520,00')          # importe retenido

    def test_modal_de_anulacion_renderiza(self):
        liq = self._liquidacion()
        op = self._pagar([liq], Decimal('1071480.00'))

        r = self.client.get(reverse('agro_pago_anular', args=[op.id]))

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'acumulado del mes baja solo')

    # -- previsualización ---------------------------------------------------

    def test_pendientes_sin_productor_no_rompe(self):
        r = self.client.get(reverse('agro_pago_pendientes'))

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Elegí un productor')

    def test_pendientes_previsualiza_la_retencion(self):
        liq = self._liquidacion()

        r = self.client.get(reverse('agro_pago_pendientes'),
                            {'productor': self.productor.pk, 'fecha': '2026-09-10'})

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f'{liq.numero:08d}')
        self.assertContains(r, '15.520,00')          # retención
        self.assertContains(r, '1.071.480,00')       # a entregar
        self.assertContains(r, 'Cálculo del acumulado')

    def test_pendientes_muestra_cuando_no_corresponde_retener(self):
        self._liquidacion(productor=self.monotributista, kilos='100')

        r = self.client.get(reverse('agro_pago_pendientes'),
                            {'productor': self.monotributista.pk})

        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Cálculo del acumulado')

    def test_pendientes_no_lista_las_ya_pagadas(self):
        liq = self._liquidacion()
        self._pagar([liq], Decimal('1071480.00'))

        r = self.client.get(reverse('agro_pago_pendientes'),
                            {'productor': self.productor.pk})

        self.assertContains(r, 'no tiene liquidaciones pendientes')

    # -- emisión ------------------------------------------------------------

    def test_pagar_desde_el_formulario(self):
        liq = self._liquidacion()

        r = self.client.post(reverse('agro_pago_nuevo'), {
            'productor': self.productor.pk, 'fecha': '2026-09-10', 'condic': 1,
            'liquidaciones': [liq.pk],
            'medio_pago': [self.efectivo.pk], 'importe': ['1.071.480,00'],
        })

        self.assertEqual(r.status_code, 302)
        op = OrdenPago.objects.get()
        self.assertEqual(op.total, Decimal('1087000.00'))
        liq.refresh_from_db()
        self.assertEqual(liq.saldo, Decimal('0.00'))
        self.assertTrue(Asiento.objects.filter(pk=op.asiento_id).exists())
        self.assertTrue(RetencionPago.objects.filter(orden_pago=op).exists())

    def test_el_importe_llega_en_formato_es_ar(self):
        """Los `.fInputAR` mandan `1.071.480,00`: si se leyera crudo daría un importe absurdo."""
        liq = self._liquidacion()

        self.client.post(reverse('agro_pago_nuevo'), {
            'productor': self.productor.pk, 'fecha': '2026-09-10', 'condic': 1,
            'liquidaciones': [liq.pk],
            'medio_pago': [self.efectivo.pk], 'importe': ['500.000,50'],
        })

        detalle = MovimientoCajaDetalle.objects.get(medio_pago=self.efectivo)
        self.assertEqual(detalle.importe, Decimal('500000.50'))

    def test_pagar_con_varios_medios(self):
        from tesoreria.models import MedioPago
        transferencia = MedioPago.objects.create(
            empresa=self.empresa, codigo='TRA-BCO', nombre='TRANSFERENCIA',
            categoria='TRA', cuenta_contable=self.cta_caja)
        liq = self._liquidacion()

        self.client.post(reverse('agro_pago_nuevo'), {
            'productor': self.productor.pk, 'fecha': '2026-09-10', 'condic': 1,
            'liquidaciones': [liq.pk],
            'medio_pago': [self.efectivo.pk, transferencia.pk],
            'importe': ['71.480,00', '1.000.000,00'],
        })

        op = OrdenPago.objects.get()
        self.assertEqual(op.total, Decimal('1087000.00'))
        self.assertEqual(
            MovimientoCajaDetalle.objects.filter(movimiento_caja__orden_pago=op).count(), 3)

    def test_sin_liquidaciones_avisa(self):
        r = self.client.post(reverse('agro_pago_nuevo'), {
            'productor': self.productor.pk, 'fecha': '2026-09-10', 'condic': 1,
            'medio_pago': [self.efectivo.pk], 'importe': ['1.000,00'],
        })

        self.assertContains(r, 'al menos una liquidación')
        self.assertFalse(OrdenPago.objects.exists())

    def test_sin_medios_avisa(self):
        liq = self._liquidacion()

        r = self.client.post(reverse('agro_pago_nuevo'), {
            'productor': self.productor.pk, 'fecha': '2026-09-10', 'condic': 1,
            'liquidaciones': [liq.pk],
        })

        self.assertContains(r, 'al menos un medio de pago')
        self.assertFalse(OrdenPago.objects.exists())

    def test_un_pago_fallido_no_deja_nada(self):
        """Preparar y contabilizar van juntos: un error no puede dejar una OP a medias."""
        liq = self._liquidacion()

        r = self.client.post(reverse('agro_pago_nuevo'), {
            'productor': self.productor.pk, 'fecha': '2026-09-10', 'condic': 1,
            'liquidaciones': [liq.pk],
            'medio_pago': [self.efectivo.pk], 'importe': ['9.000.000,00'],
        })

        self.assertContains(r, 'supera el saldo')
        self.assertFalse(OrdenPago.objects.exists())
        liq.refresh_from_db()
        self.assertEqual(liq.saldo, liq.total)

    def test_anular_desde_el_modal(self):
        liq = self._liquidacion()
        op = self._pagar([liq], Decimal('1071480.00'))

        r = self.client.post(reverse('agro_pago_anular', args=[op.id]),
                             {'motivo': 'Error de carga'})

        self.assertEqual(r.status_code, 200)
        op.refresh_from_db()
        liq.refresh_from_db()
        self.assertTrue(op.anulado)
        self.assertEqual(liq.saldo, liq.total)

    # -- menú y aislamiento -------------------------------------------------

    def test_el_menu_muestra_los_pagos(self):
        from verticalidades.agricola.core_agricola.models import EmpresaVertical
        EmpresaVertical.objects.create(empresa=self.empresa, hace_tabaco=True)

        r = self.client.get(reverse('agro_pago_listado'))

        self.assertContains(r, reverse('agro_pago_nuevo'))

    def test_no_se_accede_a_un_pago_de_otra_empresa(self):
        from empresas.models import Empresa, Sucursal
        from contable.models import Ejercicio
        otra = Empresa.objects.create(nombre="OTRO ACOPIO", cuit="30999999998")
        otra_suc = Sucursal.objects.create(empresa=otra, nombre="C")
        otro_eje = Ejercicio.objects.create(empresa=otra, ejercicio="2026",
                                            inicio=date(2026, 1, 1), cierre=date(2026, 12, 31))
        ajena = OrdenPago.objects.create(
            empresa=otra, sucursal=otra_suc, ejercicio=otro_eje, proveedor=self.productor,
            fecha=date(2026, 9, 10), punto=1, total=Decimal('100'))

        for nombre in ('agro_pago_detalle', 'agro_pago_anular'):
            with self.subTest(url=nombre):
                self.assertEqual(
                    self.client.get(reverse(nombre, args=[ajena.id])).status_code, 404)
