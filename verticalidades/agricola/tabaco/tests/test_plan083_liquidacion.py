"""Plan 083 — liquidación de compra de tabaco.

Esta es la primera pieza con efectos contables, así que lo que se protege es distinto de las
etapas anteriores:

1. Que el asiento BALANCEE y que cada importe caiga en la cuenta que corresponde.
2. Que el Libro IVA refleje la letra correcta (A con crédito fiscal, B sin él).
3. Que la deuda aparezca en la cuenta corriente por el término del Plan 080.
4. Que confirmar dos veces no duplique asiento ni renumere.
5. Que anular revierta TODO menos la recepción física.
6. Que las reglas se congelen: un maestro corregido después no puede mover un comprobante emitido.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from contable.models import (Asiento, AsientoLinea, Cuenta, Ejercicio, LibroIvaAlic,
                             LibroIvaCompras, ParametrosContables)
from contable.services.saldos import recalcular_saldo_cliente_proveedor
from empresas.models import Empresa, Sucursal
from facturacion.models import ClienteProveedor
from verticalidades.agricola.core_agricola.models import Campania
from verticalidades.agricola.tabaco.models import (ClaseTabaco, ConfiguracionTabaco,
                                                   LiquidacionRetencion, LiquidacionTabaco,
                                                   ListaPrecioTabaco, RomaneoTabaco,
                                                   TipoRetencionTabaco, VariedadTabaco)
from verticalidades.agricola.tabaco.services import liquidacion as liq_svc
from verticalidades.agricola.tabaco.services import romaneo as rom_svc

User = get_user_model()


class LiquidacionBaseTestCase(TestCase):
    """Escenario realista: las cinco retenciones que el cliente cargó, con sus cuentas."""

    def setUp(self):
        self.user = User.objects.create_user(username='liquidador', password='pw')
        self.empresa = Empresa.objects.create(nombre="ACOPIO TEST", cuit="30111111112",
                                              tipo_actividad='AGRICOLA')
        self.sucursal = Sucursal.objects.create(empresa=self.empresa, nombre="CENTRAL", punto=2)
        Ejercicio.objects.create(empresa=self.empresa, ejercicio="2026",
                                 inicio=date(2026, 1, 1), cierre=date(2026, 12, 31))

        self.cta_bs_cambio = self._cuenta('114002', 'COMPRA DE TABACO', 'A')
        self.cta_iva_cred = self._cuenta('114900', 'IVA CREDITO FISCAL', 'A')
        self.cta_proveedores = self._cuenta('211001', 'PROVEEDORES', 'P')
        self.cta_ret_iva = self._cuenta('214010', 'RET IVA A DEPOSITAR', 'P')
        self.cta_eeaoc = self._cuenta('214401', 'EEAOC A DEPOSITAR', 'P')
        self.cta_agua = self._cuenta('214402', 'USO AGUA A DEPOSITAR', 'P')
        self.cta_salud = self._cuenta('214105', 'SALUD PUBLICA A DEPOSITAR', 'P')
        self.cta_gcias = self._cuenta('214005', 'RET GCIAS A DEPOSITAR', 'P')

        ParametrosContables.objects.create(
            empresa=self.empresa, cta_iva_credito=self.cta_iva_cred,
            cta_proveedores_default=self.cta_proveedores)

        ConfiguracionTabaco.objects.create(
            empresa=self.empresa, cuenta_bienes_cambio=self.cta_bs_cambio,
            punto_venta=2, modo_autorizacion=ConfiguracionTabaco.MANUAL,
            cai='12345678901234', cai_vencimiento=date(2026, 12, 31),
            alicuota_iva=Decimal('21.00'))

        self._retenciones()

        self.productor = ClienteProveedor.objects.create(
            razon_social="PRODUCTOR RI", cuit="20181662515", tipo_entidad=2,
            condicion_iva='RESPONSABLE INSCRIPTO', empresa=self.empresa)
        self.monotributista = ClienteProveedor.objects.create(
            razon_social="PRODUCTOR MONO", cuit="20111111112", tipo_entidad=2,
            condicion_iva='MONOTRIBUTO', empresa=self.empresa)

        self.campania = Campania.objects.create(
            empresa=self.empresa, codigo='2026/2027', detalle='TEST',
            fecha_inicio=date(2026, 1, 1))
        self.burley = VariedadTabaco.objects.create(empresa=self.empresa, codigo=1,
                                                    detalle='BURLEY')
        self.b1f = ClaseTabaco.objects.create(empresa=self.empresa, variedad=self.burley,
                                              codigo=1, detalle='B1F', coeficiente=Decimal('1'))
        ListaPrecioTabaco.objects.create(
            empresa=self.empresa, variedad=self.burley, campania=self.campania,
            vigencia_desde=date(2026, 1, 1), precio_ponderante=Decimal('1000.00'),
            aprobada=True)

    def _cuenta(self, jerarquia, nombre, tipo):
        return Cuenta.objects.create(empresa=self.empresa, jerarquia=jerarquia, cuenta=nombre,
                                     imputable=1, tipo=tipo)

    def _retenciones(self):
        comunes = dict(empresa=self.empresa, activa=True, vigencia_desde=date(2026, 1, 1))
        T = TipoRetencionTabaco
        TipoRetencionTabaco.objects.create(
            codigo='EEAOC', detalle='RETENCION EEAOC', tipo_base=T.NETO, columna_fet='ret_eeaoc',
            alicuota=Decimal('0.5'), momento=T.LIQUIDACION, cuenta_contable=self.cta_eeaoc,
            **comunes)
        TipoRetencionTabaco.objects.create(
            codigo='USO AGUA', detalle='RETENCION USO DE AGUA', tipo_base=T.NETO, columna_fet='ret_agua',
            alicuota=Decimal('0.3'), momento=T.LIQUIDACION, cuenta_contable=self.cta_agua,
            **comunes)
        TipoRetencionTabaco.objects.create(
            codigo='SALUD', detalle='RETENCION SALUD PUBLICA', tipo_base=T.NETO, columna_fet='ret_salud',
            alicuota=Decimal('1.0'), momento=T.LIQUIDACION, cuenta_contable=self.cta_salud,
            **comunes)
        self.ret_iva = TipoRetencionTabaco.objects.create(
            codigo='RET-IVA', detalle='RETENCION IVA', tipo_base=T.IVA, columna_fet='ret_iva',
            alicuota=Decimal('50.0'), momento=T.LIQUIDACION, solo_responsable_inscripto=True,
            cuenta_contable=self.cta_ret_iva, **comunes)
        # Ganancias: su momento es el PAGO. No debe aparecer en la liquidación.
        TipoRetencionTabaco.objects.create(
            codigo='RET-GCIAS', detalle='RETENCION GANANCIAS', tipo_base=T.ACUM_MENSUAL, columna_fet='ret_ganancias',
            alicuota=Decimal('2.0'), minimo_no_imponible=Decimal('224000'),
            momento=T.PAGO, solo_responsable_inscripto=True, regimen='78',
            cuenta_contable=self.cta_gcias, **comunes)

    # -- helpers ------------------------------------------------------------

    def _romaneo(self, productor=None, kilos='1000'):
        """Romaneo confirmado. Con ponderante 1.000 y coef 1, 1.000 kg = $ 1.000.000 de neto."""
        r = rom_svc.abrir_romaneo(
            empresa=self.empresa, sucursal=self.sucursal, productor=productor or self.productor,
            variedad=self.burley, campania=self.campania, fecha=date(2026, 9, 1),
            usuario=self.user)
        rom_svc.agregar_fardo(r, clase=self.b1f, kilos=Decimal(kilos), usuario=self.user)
        return rom_svc.confirmar_romaneo(r, self.user)

    def _preparar(self, productor=None, romaneos=None):
        productor = productor or self.productor
        romaneos = romaneos or [self._romaneo(productor)]
        return liq_svc.preparar_liquidacion(
            empresa=self.empresa, sucursal=self.sucursal, productor=productor,
            romaneos=romaneos, fecha=date(2026, 9, 6), usuario=self.user)


class CalculoTests(LiquidacionBaseTestCase):
    """Neto 1.000.000 · IVA 21% = 210.000 · Ret.IVA 105.000 · EEAOC 5.000 · Agua 3.000 · Salud 10.000."""

    def test_responsable_inscripto_es_letra_a(self):
        liq = self._preparar()

        self.assertEqual(liq.letra, LiquidacionTabaco.A)
        self.assertEqual(liq.codiva, '150')
        self.assertEqual(liq.neto, Decimal('1000000.00'))
        self.assertEqual(liq.alicuota_iva, Decimal('21.00'))
        self.assertEqual(liq.iva, Decimal('210000.00'))

    def test_monotributista_es_letra_b_sin_iva(self):
        liq = self._preparar(productor=self.monotributista)

        self.assertEqual(liq.letra, LiquidacionTabaco.B)
        self.assertEqual(liq.codiva, '151')
        self.assertEqual(liq.iva, Decimal("0.00"))
        self.assertEqual(liq.alicuota_iva, Decimal('0.00'))

    def test_retenciones_de_liquidacion(self):
        liq = self._preparar()
        por_codigo = {r.codigo: r for r in liq.retenciones_aplicadas.all()} if liq.pk else {}
        # Todavía no se congelaron: se congelan al confirmar. Se valida el cálculo.
        calculo = liq_svc.calcular(empresa=self.empresa, productor=self.productor,
                                   neto=liq.neto, fecha=liq.fecha)
        importes = {a['regla'].codigo: a['importe'] for a in calculo['retenciones']}

        self.assertEqual(importes['EEAOC'], Decimal('5000.00'))        # 0,5 % de 1.000.000
        self.assertEqual(importes['USO AGUA'], Decimal('3000.00'))     # 0,3 %
        self.assertEqual(importes['SALUD'], Decimal('10000.00'))       # 1,0 %
        self.assertEqual(importes['RET-IVA'], Decimal('105000.00'))    # 50 % DEL IVA, no del neto
        self.assertEqual(calculo['total_retenciones'], Decimal('123000.00'))

    def test_ganancias_no_se_practica_al_liquidar(self):
        """Su base es el acumulado mensual de lo PAGADO: acá daría un importe incorrecto."""
        calculo = liq_svc.calcular(empresa=self.empresa, productor=self.productor,
                                   neto=Decimal('1000000'), fecha=date(2026, 9, 6))
        codigos = {a['regla'].codigo for a in calculo['retenciones']}

        self.assertNotIn('RET-GCIAS', codigos)

    def test_ganancias_mal_configurada_igual_se_excluye(self):
        """Barrera de seguridad: aunque un dato viejo la ponga en LIQUIDACION, no se calcula."""
        TipoRetencionTabaco.objects.filter(codigo='RET-GCIAS').update(
            momento=TipoRetencionTabaco.LIQUIDACION)

        calculo = liq_svc.calcular(empresa=self.empresa, productor=self.productor,
                                   neto=Decimal('1000000'), fecha=date(2026, 9, 6))

        self.assertNotIn('RET-GCIAS', {a['regla'].codigo for a in calculo['retenciones']})

    def test_retenciones_solo_ri_no_aplican_a_monotributo(self):
        calculo = liq_svc.calcular(empresa=self.empresa, productor=self.monotributista,
                                   neto=Decimal('1000000'), fecha=date(2026, 9, 6))
        codigos = {a['regla'].codigo for a in calculo['retenciones']}

        self.assertNotIn('RET-IVA', codigos)                # es sólo para RI
        self.assertEqual(codigos, {'EEAOC', 'USO AGUA', 'SALUD'})

    def test_total_es_neto_mas_iva_menos_retenciones(self):
        liq = self._preparar()
        # 1.000.000 + 210.000 − 123.000
        self.assertEqual(liq.total, Decimal('1087000.00'))

    def test_no_aplica_retencion_vencida(self):
        TipoRetencionTabaco.objects.filter(codigo='EEAOC').update(
            vigencia_hasta=date(2026, 8, 31))

        calculo = liq_svc.calcular(empresa=self.empresa, productor=self.productor,
                                   neto=Decimal('1000000'), fecha=date(2026, 9, 6))

        self.assertNotIn('EEAOC', {a['regla'].codigo for a in calculo['retenciones']})


class PreparacionTests(LiquidacionBaseTestCase):

    def test_el_detalle_se_agrupa_por_romaneo_y_clase(self):
        liq = self._preparar()
        detalle = liq.detalles.get()

        self.assertEqual(detalle.clase, self.b1f)
        self.assertEqual(detalle.kilos, Decimal('1000.00'))
        self.assertEqual(detalle.fardos, 1)
        self.assertEqual(detalle.precio, Decimal('1000.00'))

    def test_el_romaneo_queda_vinculado(self):
        romaneo = self._romaneo()
        liq = self._preparar(romaneos=[romaneo])

        romaneo.refresh_from_db()
        self.assertEqual(romaneo.liquidacion, liq)

    def test_no_se_liquida_dos_veces_el_mismo_romaneo(self):
        romaneo = self._romaneo()
        self._preparar(romaneos=[romaneo])
        romaneo.refresh_from_db()

        with self.assertRaises(ValidationError) as ctx:
            self._preparar(romaneos=[romaneo])
        self.assertIn('ya fue liquidado', str(ctx.exception))

    def test_solo_romaneos_confirmados(self):
        borrador = rom_svc.abrir_romaneo(
            empresa=self.empresa, sucursal=self.sucursal, productor=self.productor,
            variedad=self.burley, campania=self.campania, fecha=date(2026, 9, 1),
            usuario=self.user)

        with self.assertRaises(ValidationError) as ctx:
            self._preparar(romaneos=[borrador])
        self.assertIn('no se puede liquidar', str(ctx.exception))

    def test_una_liquidacion_es_de_un_solo_productor(self):
        r1 = self._romaneo(self.productor)
        r2 = self._romaneo(self.monotributista)

        with self.assertRaises(ValidationError) as ctx:
            self._preparar(romaneos=[r1, r2])
        self.assertIn('otro productor', str(ctx.exception))

    def test_agrupa_varios_romaneos(self):
        r1, r2 = self._romaneo(), self._romaneo()
        liq = self._preparar(romaneos=[r1, r2])

        self.assertEqual(liq.detalles.count(), 2)
        self.assertEqual(liq.neto, Decimal('2000000.00'))

    def test_hereda_el_condic_del_romaneo(self):
        romaneo = self._romaneo()
        RomaneoTabaco.objects.filter(pk=romaneo.pk).update(condic=2)
        romaneo.refresh_from_db()

        liq = self._preparar(romaneos=[romaneo])
        self.assertEqual(liq.condic, 2)

    def test_toma_punto_y_cai_de_la_configuracion(self):
        liq = self._preparar()

        self.assertEqual(liq.punto, 2)
        self.assertEqual(liq.cai, '12345678901234')
        self.assertEqual(liq.origen_autorizacion, LiquidacionTabaco.MANUAL)


class ConfirmacionTests(LiquidacionBaseTestCase):

    def test_confirmar_numera_por_letra(self):
        a1 = liq_svc.confirmar_liquidacion(self._preparar(), self.user)
        a2 = liq_svc.confirmar_liquidacion(self._preparar(), self.user)
        b1 = liq_svc.confirmar_liquidacion(self._preparar(self.monotributista), self.user)

        self.assertEqual((a1.letra, a1.numero), ('A', 1))
        self.assertEqual((a2.letra, a2.numero), ('A', 2))
        self.assertEqual((b1.letra, b1.numero), ('B', 1))     # serie independiente

    def test_respeta_el_numero_cargado_a_mano(self):
        """En modo manual el número real viene del talonario, no de un contador interno."""
        liq = self._preparar()
        liq.numero = 4521
        liq.save(update_fields=['numero'])

        liq = liq_svc.confirmar_liquidacion(liq, self.user)
        self.assertEqual(liq.numero, 4521)

    def test_sin_cai_no_confirma_en_modo_manual(self):
        liq = self._preparar()
        liq.cai = ''
        liq.save(update_fields=['cai'])

        with self.assertRaises(ValidationError) as ctx:
            liq_svc.confirmar_liquidacion(liq, self.user)
        self.assertIn('CAI', str(ctx.exception))

    def test_confirmar_es_idempotente(self):
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)
        numero, asiento = liq.numero, liq.asiento_id

        liq = liq_svc.confirmar_liquidacion(liq, self.user)

        self.assertEqual(liq.numero, numero)
        self.assertEqual(liq.asiento_id, asiento)
        self.assertEqual(Asiento.objects.filter(empresa=self.empresa).count(), 1)

    def test_los_romaneos_pasan_a_liquidado(self):
        romaneo = self._romaneo()
        liq_svc.confirmar_liquidacion(self._preparar(romaneos=[romaneo]), self.user)

        romaneo.refresh_from_db()
        self.assertEqual(romaneo.estado, RomaneoTabaco.LIQUIDADO)

    def test_las_reglas_quedan_congeladas(self):
        """Corregir un maestro después no puede mover un comprobante ya emitido."""
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)
        aplicada = liq.retenciones_aplicadas.get(codigo='EEAOC')
        self.assertEqual(aplicada.alicuota, Decimal('0.5000'))

        TipoRetencionTabaco.objects.filter(codigo='EEAOC').update(alicuota=Decimal('9.9'))

        aplicada.refresh_from_db()
        liq.refresh_from_db()
        self.assertEqual(aplicada.alicuota, Decimal('0.5000'))
        self.assertEqual(aplicada.importe, Decimal('5000.00'))
        self.assertEqual(liq.total, Decimal('1087000.00'))

    def test_no_confirma_sin_detalle(self):
        liq = LiquidacionTabaco.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, productor=self.productor,
            fecha=date(2026, 9, 6), cai='123')

        with self.assertRaises(ValidationError) as ctx:
            liq_svc.confirmar_liquidacion(liq, self.user)
        self.assertIn('sin detalle', str(ctx.exception))


class AsientoTests(LiquidacionBaseTestCase):

    def _lineas(self, liq):
        return {l.cuenta.jerarquia: (l.debe, l.haber)
                for l in AsientoLinea.objects.filter(asiento_id=liq.asiento_id)}

    def test_asiento_balanceado_letra_a(self):
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)
        lineas = self._lineas(liq)

        self.assertEqual(lineas['114002'], (Decimal('1000000.00'), Decimal('0.00')))   # bs de cambio
        self.assertEqual(lineas['114900'], (Decimal('210000.00'), Decimal('0.00')))    # IVA crédito
        self.assertEqual(lineas['214010'], (Decimal('0.00'), Decimal('105000.00')))    # ret IVA
        self.assertEqual(lineas['214401'], (Decimal('0.00'), Decimal('5000.00')))      # EEAOC
        self.assertEqual(lineas['214402'], (Decimal('0.00'), Decimal('3000.00')))      # uso agua
        self.assertEqual(lineas['214105'], (Decimal('0.00'), Decimal('10000.00')))     # salud
        self.assertEqual(lineas['211001'], (Decimal('0.00'), Decimal('1087000.00')))   # productor

        debe = sum(d for d, _ in lineas.values())
        haber = sum(h for _, h in lineas.values())
        self.assertEqual(debe, haber)
        self.assertEqual(debe, Decimal('1210000.00'))

    def test_asiento_letra_b_sin_linea_de_iva(self):
        liq = liq_svc.confirmar_liquidacion(self._preparar(self.monotributista), self.user)
        lineas = self._lineas(liq)

        self.assertNotIn('114900', lineas)                  # no hay crédito fiscal
        self.assertNotIn('214010', lineas)                  # ni retención de IVA
        self.assertEqual(lineas['114002'][0], Decimal('1000000.00'))
        # 1.000.000 − (5.000 + 3.000 + 10.000)
        self.assertEqual(lineas['211001'][1], Decimal('982000.00'))
        self.assertEqual(sum(d for d, _ in lineas.values()), sum(h for _, h in lineas.values()))

    def test_el_asiento_hereda_el_condic_y_va_al_modulo_compras(self):
        romaneo = self._romaneo()
        RomaneoTabaco.objects.filter(pk=romaneo.pk).update(condic=3)
        romaneo.refresh_from_db()

        liq = liq_svc.confirmar_liquidacion(self._preparar(romaneos=[romaneo]), self.user)
        asiento = Asiento.objects.get(pk=liq.asiento_id)

        self.assertEqual(asiento.condic, 3)
        self.assertEqual(asiento.modulo, 5)

    def test_usa_la_cuenta_patrimonial_del_productor_si_la_tiene(self):
        propia = self._cuenta('211050', 'PRODUCTORES TABACO', 'P')
        self.productor.cta_pat = propia.pk
        self.productor.save(update_fields=['cta_pat'])

        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)
        lineas = self._lineas(liq)

        self.assertIn('211050', lineas)
        self.assertNotIn('211001', lineas)


class LibroIvaTests(LiquidacionBaseTestCase):

    def test_letra_a_computa_credito_fiscal(self):
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)
        fila = LibroIvaCompras.objects.get(asiento_id=liq.asiento_id)

        self.assertEqual(fila.codiva, '150')
        self.assertEqual(fila.neto_gravado, Decimal('1000000.00'))
        self.assertEqual(fila.no_gravado, Decimal('0.00'))
        self.assertEqual(fila.iva_total, Decimal('210000.00'))
        self.assertEqual(fila.otros, Decimal('123000.00'))
        self.assertEqual(fila.total, Decimal('1087000.00'))
        self.assertEqual(fila.cuit, '20181662515')
        self.assertEqual(fila.periodo, '202609')

        alic = LibroIvaAlic.objects.get(asiento_id=liq.asiento_id, c_v='C')
        self.assertEqual(alic.alicuota, Decimal('21.00'))
        self.assertEqual(alic.computable, Decimal('210000.00'))

    def test_letra_b_no_genera_credito_ni_alicuotas(self):
        liq = liq_svc.confirmar_liquidacion(self._preparar(self.monotributista), self.user)
        fila = LibroIvaCompras.objects.get(asiento_id=liq.asiento_id)

        self.assertEqual(fila.codiva, '151')
        self.assertEqual(fila.neto_gravado, Decimal('0.00'))
        self.assertEqual(fila.no_gravado, Decimal('1000000.00'))
        self.assertEqual(fila.iva_total, Decimal('0.00'))
        self.assertFalse(LibroIvaAlic.objects.filter(asiento_id=liq.asiento_id).exists())

    def test_reconfirmar_no_duplica_el_libro_iva(self):
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)
        liq_svc.confirmar_liquidacion(liq, self.user)

        self.assertEqual(LibroIvaCompras.objects.filter(asiento_id=liq.asiento_id).count(), 1)


class CuentaCorrienteTests(LiquidacionBaseTestCase):
    """El término del Plan 080 en funcionamiento: acá se ve para qué se construyó."""

    def test_la_liquidacion_confirmada_genera_deuda(self):
        saldo_previo = recalcular_saldo_cliente_proveedor(self.productor.pk)
        self.assertEqual(saldo_previo, Decimal('0.00'))

        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)

        self.productor.refresh_from_db()
        # Negativo = le debemos, misma convención que una compra.
        self.assertEqual(self.productor.saldo, -liq.total)
        self.assertEqual(self.productor.saldo, Decimal('-1087000.00'))

    def test_un_borrador_no_es_deuda(self):
        self._preparar()

        self.assertEqual(recalcular_saldo_cliente_proveedor(self.productor.pk), Decimal('0.00'))

    def test_anular_borra_la_deuda(self):
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)
        liq_svc.anular_liquidacion(liq, "Error de carga", self.user)

        self.assertEqual(recalcular_saldo_cliente_proveedor(self.productor.pk), Decimal('0.00'))

    def test_la_deuda_es_el_total_y_no_el_neto(self):
        """El total ya viene neto de las retenciones de liquidación, pero NO de Ganancias."""
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)

        self.assertEqual(liq.total, liq.neto + liq.iva - liq.retenciones)
        self.productor.refresh_from_db()
        self.assertEqual(self.productor.saldo, -(liq.neto + liq.iva - liq.retenciones))


class AnulacionTests(LiquidacionBaseTestCase):

    def test_anula_el_asiento_sin_borrarlo(self):
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)
        asiento_id = liq.asiento_id

        liq_svc.anular_liquidacion(liq, "Error", self.user)

        asiento = Asiento.objects.get(pk=asiento_id)
        self.assertTrue(asiento.anulado)
        self.assertIsNotNone(asiento.fec_anulacion)
        # Las líneas siguen ahí: la trazabilidad no se destruye.
        self.assertTrue(AsientoLinea.objects.filter(asiento_id=asiento_id).exists())

    def test_limpia_el_libro_iva(self):
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)
        liq_svc.anular_liquidacion(liq, "Error", self.user)

        self.assertFalse(LibroIvaCompras.objects.filter(asiento_id=liq.asiento_id).exists())
        self.assertFalse(LibroIvaAlic.objects.filter(asiento_id=liq.asiento_id).exists())

    def test_libera_los_romaneos_para_relicuidar(self):
        romaneo = self._romaneo()
        liq = liq_svc.confirmar_liquidacion(self._preparar(romaneos=[romaneo]), self.user)

        liq_svc.anular_liquidacion(liq, "Error", self.user)

        romaneo.refresh_from_db()
        self.assertEqual(romaneo.estado, RomaneoTabaco.CONFIRMADO)
        self.assertIsNone(romaneo.liquidacion)
        # Y se puede volver a liquidar.
        nueva = self._preparar(romaneos=[romaneo])
        self.assertEqual(nueva.neto, Decimal('1000000.00'))

    def test_no_toca_los_fardos(self):
        """La mercadería entró y se pesó: anular el comprobante no borra la recepción."""
        romaneo = self._romaneo()
        liq = liq_svc.confirmar_liquidacion(self._preparar(romaneos=[romaneo]), self.user)

        liq_svc.anular_liquidacion(liq, "Error", self.user)

        romaneo.refresh_from_db()
        self.assertEqual(romaneo.fardos.count(), 1)
        self.assertEqual(romaneo.total_kilos, Decimal('1000.00'))

    def test_exige_motivo(self):
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)

        with self.assertRaises(ValidationError):
            liq_svc.anular_liquidacion(liq, "  ", self.user)

    def test_es_idempotente(self):
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)
        liq_svc.anular_liquidacion(liq, "Primero", self.user)
        liq_svc.anular_liquidacion(liq, "Segundo", self.user)

        liq.refresh_from_db()
        self.assertEqual(liq.motivo_anulacion, "Primero")

    def test_no_se_anula_con_pagos_imputados(self):
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)
        LiquidacionTabaco.objects.filter(pk=liq.pk).update(pagado=Decimal('100'))
        liq.refresh_from_db()

        with self.assertRaises(ValidationError) as ctx:
            liq_svc.anular_liquidacion(liq, "Error", self.user)
        self.assertIn('Orden de Pago', str(ctx.exception))

    def test_una_anulada_no_se_confirma(self):
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)
        liq_svc.anular_liquidacion(liq, "Error", self.user)

        with self.assertRaises(ValidationError):
            liq_svc.confirmar_liquidacion(liq, self.user)


class AislamientoTests(LiquidacionBaseTestCase):

    def test_no_se_liquida_un_romaneo_de_otra_empresa(self):
        otra = Empresa.objects.create(nombre="OTRO ACOPIO", cuit="30999999998")
        otra_suc = Sucursal.objects.create(empresa=otra, nombre="C")
        otra_camp = Campania.objects.create(empresa=otra, codigo='X', detalle='X',
                                            fecha_inicio=date(2026, 1, 1))
        otra_var = VariedadTabaco.objects.create(empresa=otra, codigo=1, detalle='BURLEY')
        otra_lista = ListaPrecioTabaco.objects.create(
            empresa=otra, variedad=otra_var, campania=otra_camp,
            vigencia_desde=date(2026, 1, 1), precio_ponderante=Decimal('100'), aprobada=True)
        ajeno = RomaneoTabaco.objects.create(
            empresa=otra, sucursal=otra_suc, fecha=date(2026, 9, 1), productor=self.productor,
            variedad=otra_var, campania=otra_camp, lista_precio=otra_lista,
            ponderante_aplicado=Decimal('100'), estado=RomaneoTabaco.CONFIRMADO)

        with self.assertRaises(ValidationError) as ctx:
            self._preparar(romaneos=[ajeno])
        self.assertIn('otra empresa', str(ctx.exception))

    def test_no_usa_retenciones_de_otra_empresa(self):
        otra = Empresa.objects.create(nombre="OTRO ACOPIO", cuit="30999999998")
        cta = Cuenta.objects.create(empresa=otra, jerarquia='999', cuenta='AJENA',
                                    imputable=1, tipo='P')
        TipoRetencionTabaco.objects.create(
            empresa=otra, codigo='AJENA', detalle='AJENA', tipo_base=TipoRetencionTabaco.NETO,
            alicuota=Decimal('50'), momento=TipoRetencionTabaco.LIQUIDACION,
            cuenta_contable=cta, activa=True, vigencia_desde=date(2026, 1, 1))

        calculo = liq_svc.calcular(empresa=self.empresa, productor=self.productor,
                                   neto=Decimal('1000000'), fecha=date(2026, 9, 6))

        self.assertNotIn('AJENA', {a['regla'].codigo for a in calculo['retenciones']})


class DescarteDeBorradorTests(LiquidacionBaseTestCase):
    """`preparar_liquidacion` toma los romaneos apenas arma el borrador.

    Si ese borrador quedara abandonado, sus romaneos no volverían a figurar como pendientes y no
    habría forma de recuperarlos. Estos tests cubren la red de seguridad.
    """

    def test_descartar_libera_los_romaneos(self):
        romaneo = self._romaneo()
        liq = self._preparar(romaneos=[romaneo])
        romaneo.refresh_from_db()
        self.assertEqual(romaneo.liquidacion, liq)

        liq_svc.descartar_liquidacion(liq)

        romaneo.refresh_from_db()
        self.assertIsNone(romaneo.liquidacion)
        self.assertFalse(LiquidacionTabaco.objects.filter(pk=liq.pk).exists())
        # Y vuelve a estar disponible para liquidar.
        self.assertIn(romaneo, liq_svc.romaneos_liquidables(self.empresa.pk, self.productor))

    def test_no_se_descarta_una_confirmada(self):
        liq = liq_svc.confirmar_liquidacion(self._preparar(), self.user)

        with self.assertRaises(ValidationError) as ctx:
            liq_svc.descartar_liquidacion(liq)
        self.assertIn('anulala', str(ctx.exception))
        self.assertTrue(LiquidacionTabaco.objects.filter(pk=liq.pk).exists())
