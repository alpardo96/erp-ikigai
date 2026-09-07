"""Plan 086 — lotes de acopio, acondicionamiento, venta y margen (Etapa 5).

Lo que se protege:

1. Que un fardo no entre a dos lotes, ni venga de un romaneo que no existe físicamente.
2. Que la merma baje el stock de la variedad y el coproducto entre al suyo, sin contarse dos veces.
3. Que sólo el acondicionamiento CERRADO mueva existencias, y que anularlo las devuelva.
4. Que la merma extraordinaria haya que explicarla.
5. Que el margen use el costo EXACTO de compra por fardo y prorratee sólo lo que no es atribuible.
6. Que la etapa NO genere un solo asiento.
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from productos.models import Producto, StockSucursal
from productos.services.stock_service import recalcular_stock
from verticalidades.agricola.tabaco.models import (Acondicionamiento, FardoTabaco, LoteAcopio,
                                                   ProcesoAcondicionamiento, RomaneoTabaco)
from verticalidades.agricola.tabaco.services import acondicionamiento as ac_svc
from verticalidades.agricola.tabaco.services import lotes as lote_svc
from verticalidades.agricola.tabaco.services import margen as margen_svc
from verticalidades.agricola.tabaco.services import romaneo as rom_svc
from verticalidades.agricola.tabaco.services import stock as stock_svc
from verticalidades.agricola.tabaco.services import stock_acondicionamiento as stock_ac

from .test_plan085_stock import StockBaseTestCase


class LoteBaseTestCase(StockBaseTestCase):
    """Sobre el escenario del Plan 085 —que ya tiene producto de stock— agrega lote y proceso."""

    def setUp(self):
        super().setUp()

        # Los tres términos se registran en `ready()`, una vez por proceso. Se garantizan acá para
        # que estos tests no dependan de si otro módulo los limpió antes.
        from productos.services import stock_service
        for termino in (stock_ac.termino_de_bajas(), stock_ac.termino_de_coproductos()):
            if not any(t['nombre'] == termino['nombre'] for t in stock_service._TERMINOS_EXTRA):
                stock_service.registrar_termino_stock(termino)

        self.palo = Producto.objects.create(
            empresa=self.empresa, detalle="PALO DE TABACO", unidad_venta='KG',
            alic_iva=Decimal('21.00'))

        self.despalillado = ProcesoAcondicionamiento.objects.create(
            empresa=self.empresa, codigo='DESP', detalle='DESPALILLADO',
            merma_normal_porcentaje=Decimal('5.000'))

    # -- ayudantes ---------------------------------------------------------

    def _lote(self, fecha=date(2026, 9, 10)):
        return lote_svc.abrir_lote(
            empresa=self.empresa, sucursal=self.sucursal, campania=self.campania,
            variedad=self.burley, fecha=fecha, descripcion='LOTE TEST', usuario=self.user)

    def _lote_armado(self, kilos='1000'):
        """Lote con todos los fardos de un romaneo confirmado de `kilos`."""
        romaneo = self._romaneo_confirmado(kilos=kilos)
        lote = self._lote()
        for fardo in romaneo.fardos.all():
            lote_svc.agregar_fardo(lote, fardo, self.user)
        return lote_svc.armar_lote(lote, self.user)

    def _acond(self, lote, entrada='1000', salida='900', motivo_merma='Merma de proceso',
               **extra):
        """Corrida de despalillado.

        Lleva motivo por defecto porque 1.000 -> 900 es un 10 % contra un 5 % normal: es merma
        extraordinaria y el modelo la obliga a justificar. Los tests que prueban justamente esa
        exigencia pasan `motivo_merma=''` a proposito.
        """
        return ac_svc.abrir_acondicionamiento(
            lote, proceso=self.despalillado, fecha=date(2026, 9, 12),
            kilos_entrada=Decimal(entrada), kilos_salida=Decimal(salida),
            motivo_merma=motivo_merma, usuario=self.user, **extra)

    def _stock_palo(self):
        return recalcular_stock(self.palo.pk, self.sucursal.pk)


# ===========================================================================
# Armado del lote
# ===========================================================================

class ArmadoDelLoteTests(LoteBaseTestCase):

    def test_armar_lote_marca_los_fardos_y_toma_numero(self):
        lote = self._lote_armado(kilos='1000')

        self.assertEqual(lote.estado, LoteAcopio.ARMADO)
        self.assertIsNotNone(lote.numero)
        self.assertEqual(lote.total_fardos, 1)
        self.assertEqual(lote.total_kilos, Decimal('1000.00'))
        self.assertTrue(all(f.estado == FardoTabaco.EN_LOTE for f in lote.fardos.all()))

    def test_un_fardo_no_entra_a_dos_lotes(self):
        lote_a = self._lote_armado()
        fardo = lote_a.fardos.first()
        lote_b = self._lote()

        with self.assertRaises(ValidationError) as ctx:
            lote_svc.agregar_fardo(lote_b, fardo, self.user)
        self.assertIn("ya pertenece al lote", str(ctx.exception))

    def test_agregar_el_mismo_fardo_dos_veces_es_idempotente(self):
        lote = self._lote()
        romaneo = self._romaneo_confirmado()
        fardo = romaneo.fardos.first()

        lote_svc.agregar_fardo(lote, fardo, self.user)
        lote_svc.agregar_fardo(lote, fardo, self.user)

        lote.refresh_from_db()
        self.assertEqual(lote.total_fardos, 1)

    def test_fardo_de_romaneo_borrador_rechazado(self):
        """Un borrador todavía se está cargando: esos kilos no existen para el negocio."""
        borrador = rom_svc.abrir_romaneo(
            empresa=self.empresa, sucursal=self.sucursal, productor=self.productor,
            variedad=self.burley, campania=self.campania, fecha=date(2026, 9, 1),
            usuario=self.user)
        rom_svc.agregar_fardo(borrador, clase=self.b1f, kilos=Decimal('300'), usuario=self.user)
        lote = self._lote()

        with self.assertRaises(ValidationError) as ctx:
            lote_svc.agregar_fardo(lote, borrador.fardos.first(), self.user)
        self.assertIn("confirmados", str(ctx.exception))

    def test_fardo_de_otra_variedad_rechazado(self):
        """Un lote es de una variedad: el stock se imputa a un solo producto."""
        from verticalidades.agricola.tabaco.models import ClaseTabaco, ListaPrecioTabaco, VariedadTabaco

        virginia = VariedadTabaco.objects.create(empresa=self.empresa, codigo=2,
                                                 detalle='VIRGINIA')
        clase_v = ClaseTabaco.objects.create(empresa=self.empresa, variedad=virginia, codigo=1,
                                             detalle='V1', coeficiente=Decimal('1'))
        ListaPrecioTabaco.objects.create(
            empresa=self.empresa, variedad=virginia, campania=self.campania,
            vigencia_desde=date(2026, 1, 1), precio_ponderante=Decimal('900.00'), aprobada=True)

        otro = rom_svc.abrir_romaneo(
            empresa=self.empresa, sucursal=self.sucursal, productor=self.productor,
            variedad=virginia, campania=self.campania, fecha=date(2026, 9, 1), usuario=self.user)
        rom_svc.agregar_fardo(otro, clase=clase_v, kilos=Decimal('400'), usuario=self.user)
        otro = rom_svc.confirmar_romaneo(otro, self.user)

        lote = self._lote()                                    # es de BURLEY
        with self.assertRaises(ValidationError) as ctx:
            lote_svc.agregar_fardo(lote, otro.fardos.first(), self.user)
        self.assertIn("una sola variedad", str(ctx.exception))

    def test_fardo_de_otra_sucursal_rechazado(self):
        from empresas.models import Sucursal

        otra = Sucursal.objects.create(empresa=self.empresa, nombre="GALPON SUR", punto=3)
        romaneo = rom_svc.abrir_romaneo(
            empresa=self.empresa, sucursal=otra, productor=self.productor, variedad=self.burley,
            campania=self.campania, fecha=date(2026, 9, 1), usuario=self.user)
        rom_svc.agregar_fardo(romaneo, clase=self.b1f, kilos=Decimal('200'), usuario=self.user)
        romaneo = rom_svc.confirmar_romaneo(romaneo, self.user)

        lote = self._lote()
        with self.assertRaises(ValidationError) as ctx:
            lote_svc.agregar_fardo(lote, romaneo.fardos.first(), self.user)
        self.assertIn("otra sucursal", str(ctx.exception))

    def test_no_se_arma_un_lote_vacio(self):
        with self.assertRaises(ValidationError):
            lote_svc.armar_lote(self._lote(), self.user)

    def test_armar_es_idempotente_y_no_renumera(self):
        lote = self._lote_armado()
        numero = lote.numero

        lote_svc.armar_lote(lote, self.user)

        lote.refresh_from_db()
        self.assertEqual(lote.numero, numero)

    def test_totales_del_lote_se_reconstruyen_al_quitar(self):
        lote = self._lote_armado(kilos='1000')
        self.assertEqual(lote.costo_compra, Decimal('1000000.00'))

        lote_svc.quitar_fardo(lote, lote.fardos.first(), self.user)

        lote.refresh_from_db()
        self.assertEqual(lote.total_fardos, 0)
        self.assertEqual(lote.total_kilos, Decimal('0.00'))
        self.assertEqual(lote.costo_compra, Decimal('0.00'))

    def test_anular_lote_libera_los_fardos(self):
        lote = self._lote_armado()
        fardo_id = lote.fardos.first().pk

        lote_svc.anular_lote(lote, "Se rearma", self.user)

        fardo = FardoTabaco.objects.get(pk=fardo_id)
        self.assertIsNone(fardo.lote_id)
        self.assertEqual(fardo.estado, FardoTabaco.CLASIFICADO)

    def test_anular_exige_motivo(self):
        lote = self._lote_armado()
        with self.assertRaises(ValidationError):
            lote_svc.anular_lote(lote, "   ", self.user)

    def test_fardos_disponibles_excluye_los_ya_agrupados(self):
        romaneo = self._romaneo_confirmado()
        disponibles = lote_svc.fardos_disponibles(self.empresa.pk, variedad_id=self.burley.pk)
        self.assertEqual(disponibles.count(), romaneo.fardos.count())

        lote = self._lote()
        lote_svc.agregar_fardo(lote, romaneo.fardos.first(), self.user)

        self.assertEqual(
            lote_svc.fardos_disponibles(self.empresa.pk, variedad_id=self.burley.pk).count(), 0)


# ===========================================================================
# Acondicionamiento y stock
# ===========================================================================

class AcondicionamientoTests(LoteBaseTestCase):

    def test_borrador_de_acondicionamiento_no_mueve_stock(self):
        lote = self._lote_armado(kilos='1000')
        self.assertEqual(self._stock(), Decimal('1000.00'))

        self._acond(lote, entrada='1000', salida='900')

        self.assertEqual(self._stock(), Decimal('1000.00'))

    def test_merma_baja_el_stock_de_la_variedad(self):
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote, entrada='1000', salida='900')

        ac_svc.cerrar_acondicionamiento(acond, self.user)

        self.assertEqual(self._stock(), Decimal('900.00'))

    def test_coproducto_entra_a_su_producto_sin_contarse_dos_veces(self):
        """80 kg de palo: el tabaco baja 100 y el palo sube 80. La merma real es 20."""
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote, entrada='1000', salida='900')
        ac_svc.agregar_coproducto(acond, producto=self.palo, kilos=Decimal('80'),
                                  valor_estimado=Decimal('4000'))

        ac_svc.cerrar_acondicionamiento(acond, self.user)

        acond.refresh_from_db()
        self.assertEqual(acond.kilos_baja, Decimal('100.00'))
        self.assertEqual(acond.kilos_coproductos, Decimal('80.00'))
        self.assertEqual(acond.kilos_merma, Decimal('20.00'))
        self.assertEqual(self._stock(), Decimal('900.00'))
        self.assertEqual(self._stock_palo(), Decimal('80.00'))

    def test_anular_acondicionamiento_devuelve_el_stock(self):
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote, entrada='1000', salida='900')
        ac_svc.agregar_coproducto(acond, producto=self.palo, kilos=Decimal('80'))
        ac_svc.cerrar_acondicionamiento(acond, self.user)

        ac_svc.anular_acondicionamiento(acond, "Mal pesado", self.user)

        self.assertEqual(self._stock(), Decimal('1000.00'))
        self.assertEqual(self._stock_palo(), Decimal('0.00'))

    def test_merma_extraordinaria_exige_motivo(self):
        """5 % es lo normal del proceso; una merma de 20 % hay que explicarla."""
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote, entrada='1000', salida='800', motivo_merma='')

        with self.assertRaises(ValidationError) as ctx:
            ac_svc.cerrar_acondicionamiento(acond, self.user)
        self.assertIn("motivo", str(ctx.exception).lower())

        ac_svc.editar_acondicionamiento(acond, motivo_merma="Partida con humedad",
                                        usuario=self.user)
        ac_svc.cerrar_acondicionamiento(acond, self.user)

        acond.refresh_from_db()
        self.assertEqual(acond.estado, Acondicionamiento.CERRADO)
        self.assertEqual(acond.merma_normal_esperada, Decimal('50.00'))
        self.assertEqual(acond.merma_extraordinaria, Decimal('150.00'))

    def test_merma_dentro_de_lo_normal_no_es_extraordinaria(self):
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote, entrada='1000', salida='960',      # 4 % < 5 %
                            motivo_merma='')

        ac_svc.cerrar_acondicionamiento(acond, self.user)

        acond.refresh_from_db()
        self.assertEqual(acond.merma_extraordinaria, Decimal('0.00'))
        self.assertEqual(acond.kilos_merma, Decimal('40.00'))

    def test_el_coproducto_no_cuenta_para_la_merma_extraordinaria(self):
        """El palo no se perdió: si contara como merma, exigiría un motivo que no existe."""
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote, entrada='1000', salida='800', motivo_merma='')
        ac_svc.agregar_coproducto(acond, producto=self.palo, kilos=Decimal('180'))

        ac_svc.cerrar_acondicionamiento(acond, self.user)       # no debe pedir motivo

        acond.refresh_from_db()
        self.assertEqual(acond.kilos_merma, Decimal('20.00'))
        self.assertEqual(acond.merma_extraordinaria, Decimal('0.00'))

    def test_no_pueden_salir_mas_kilos_de_los_que_entraron(self):
        lote = self._lote_armado(kilos='1000')
        with self.assertRaises(ValidationError) as ctx:
            self._acond(lote, entrada='500', salida='600')
        self.assertIn("no crea materia", str(ctx.exception))

    def test_no_se_procesa_mas_de_lo_que_queda_en_el_lote(self):
        lote = self._lote_armado(kilos='1000')
        with self.assertRaises(ValidationError) as ctx:
            self._acond(lote, entrada='1500', salida='1400')
        self.assertIn("disponibles", str(ctx.exception))

    def test_dos_procesos_encadenados_descuentan_del_remanente(self):
        lote = self._lote_armado(kilos='1000')
        primero = self._acond(lote, entrada='1000', salida='950')
        ac_svc.cerrar_acondicionamiento(primero, self.user)

        lote.refresh_from_db()
        self.assertEqual(lote.kilos_actuales, Decimal('950.00'))

        segundo = self._acond(lote, entrada='950', salida='930')
        ac_svc.cerrar_acondicionamiento(segundo, self.user)

        self.assertEqual(segundo.numero, 2)
        self.assertEqual(self._stock(), Decimal('930.00'))

    def test_no_se_edita_un_acondicionamiento_cerrado(self):
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote)
        ac_svc.cerrar_acondicionamiento(acond, self.user)

        with self.assertRaises(ValidationError):
            ac_svc.agregar_costo(acond, concepto="Tarde", importe=Decimal('100'))

    def test_el_coproducto_no_puede_ser_el_producto_del_lote(self):
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote)

        with self.assertRaises(ValidationError) as ctx:
            ac_svc.agregar_coproducto(acond, producto=self.producto, kilos=Decimal('10'))
        self.assertIn("no puede ser el mismo producto", str(ctx.exception))

    def test_no_se_saca_un_fardo_con_acondicionamiento_cerrado(self):
        """Sacarlo reescribiría en silencio el margen prorrateado de todos los demás."""
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote)
        ac_svc.cerrar_acondicionamiento(acond, self.user)

        with self.assertRaises(ValidationError) as ctx:
            lote_svc.quitar_fardo(lote, lote.fardos.first(), self.user)
        self.assertIn("prorratean", str(ctx.exception))

    def test_cerrar_es_idempotente(self):
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote, entrada='1000', salida='900')
        ac_svc.cerrar_acondicionamiento(acond, self.user)
        ac_svc.cerrar_acondicionamiento(acond, self.user)

        self.assertEqual(self._stock(), Decimal('900.00'))

    def test_el_porcentaje_del_proceso_queda_congelado(self):
        """Corregir el maestro no puede cambiar una corrida ya registrada."""
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote, entrada='1000', salida='900')

        self.despalillado.merma_normal_porcentaje = Decimal('30.000')
        self.despalillado.save(update_fields=['merma_normal_porcentaje'])

        acond.refresh_from_db()
        self.assertEqual(acond.porcentaje_merma_normal_aplicado, Decimal('5.000'))

    def test_el_lote_pasa_a_acondicionado_y_vuelve_al_anular(self):
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote)

        ac_svc.cerrar_acondicionamiento(acond, self.user)
        lote.refresh_from_db()
        self.assertEqual(lote.estado, LoteAcopio.ACONDICIONADO)

        ac_svc.anular_acondicionamiento(acond, "Error", self.user)
        lote.refresh_from_db()
        self.assertEqual(lote.estado, LoteAcopio.ARMADO)


# ===========================================================================
# La regla más importante del plan
# ===========================================================================

class SinEfectoContableTests(LoteBaseTestCase):

    def test_el_acondicionamiento_no_genera_asientos(self):
        """Los insumos ya se contabilizaron al comprarlos: registrarlos de nuevo duplicaría el gasto.

        La imputación al lote es GERENCIAL. Si algún día alguien agrega un `crear_asiento()` acá,
        este test lo frena.
        """
        from contable.models import Asiento

        antes = Asiento.objects.count()

        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote, entrada='1000', salida='900')
        ac_svc.agregar_costo(acond, concepto="Mano de obra", importe=Decimal('50000'))
        ac_svc.agregar_coproducto(acond, producto=self.palo, kilos=Decimal('50'),
                                  valor_estimado=Decimal('2500'))
        ac_svc.cerrar_acondicionamiento(acond, self.user)
        ac_svc.anular_acondicionamiento(acond, "Prueba", self.user)

        self.assertEqual(Asiento.objects.count(), antes)


# ===========================================================================
# Venta y margen
# ===========================================================================

class VentaYMargenTests(LoteBaseTestCase):

    def _venta(self, *, kilos='900', precio='1500', con_flete=False):
        """Venta real del producto de la variedad, por el circuito de siempre."""
        from facturacion.models import TipoComprobante, Venta, VentaItem

        tipo, _ = TipoComprobante.objects.get_or_create(
            codigo='086', defaults={'detalle': 'FACTURA A', 'signo': 1})
        self._nro_venta = getattr(self, '_nro_venta', 0) + 1
        venta = Venta.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, tipo=tipo, punto=2,
            numero=self._nro_venta, fecha=date(2026, 9, 20), cliente=self.productor,
            usuario=self.user, estado=0, condic=1)
        VentaItem.objects.create(venta=venta, producto=self.producto, cantidad=Decimal(kilos),
                                 precio_unitario=Decimal(precio), iva_alicuota=Decimal('21'),
                                 total=Decimal(kilos) * Decimal(precio))
        if con_flete:
            flete = Producto.objects.create(empresa=self.empresa, detalle="FLETE",
                                            alic_iva=Decimal('21.00'))
            VentaItem.objects.create(venta=venta, producto=flete, cantidad=Decimal('1'),
                                     precio_unitario=Decimal('99999'),
                                     iva_alicuota=Decimal('21'), total=Decimal('99999'))
        return venta

    def test_asignar_venta_marca_los_fardos_como_vendidos(self):
        lote = self._lote_armado(kilos='1000')
        venta = self._venta(kilos='1000', precio='1500')

        lote_svc.asignar_venta(lote, venta, self.user)

        lote.refresh_from_db()
        self.assertEqual(lote.estado, LoteAcopio.VENDIDO)
        self.assertEqual(lote.importe_venta, Decimal('1500000.00'))
        self.assertTrue(all(f.estado == FardoTabaco.VENDIDO for f in lote.fardos.all()))

    def test_el_importe_de_venta_ignora_lo_que_no_es_tabaco(self):
        """Un flete en la misma factura no es ingreso del tabaco: contarlo inflaría el margen."""
        lote = self._lote_armado(kilos='1000')
        venta = self._venta(kilos='1000', precio='1500', con_flete=True)

        lote_svc.asignar_venta(lote, venta, self.user)

        lote.refresh_from_db()
        self.assertEqual(lote.importe_venta, Decimal('1500000.00'))

    def test_no_se_vende_un_lote_en_borrador(self):
        lote = self._lote()
        with self.assertRaises(ValidationError) as ctx:
            lote_svc.asignar_venta(lote, self._venta(), self.user)
        self.assertIn("Armá el lote", str(ctx.exception))

    def test_quitar_la_venta_devuelve_el_lote_a_su_estado_anterior(self):
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote, entrada='1000', salida='950')
        ac_svc.cerrar_acondicionamiento(acond, self.user)
        lote_svc.asignar_venta(lote, self._venta(kilos='950'), self.user)

        lote_svc.quitar_venta(lote, self.user)

        lote.refresh_from_db()
        self.assertEqual(lote.estado, LoteAcopio.ACONDICIONADO)
        self.assertEqual(lote.importe_venta, Decimal('0.00'))

    def test_margen_por_lote(self):
        """Compra 1.000.000 · acond. 50.000 · coprod. 2.500 · venta 1.425.000 → margen 377.500."""
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote, entrada='1000', salida='900')
        ac_svc.agregar_costo(acond, concepto="Mano de obra", importe=Decimal('50000'))
        ac_svc.agregar_coproducto(acond, producto=self.palo, kilos=Decimal('50'),
                                  valor_estimado=Decimal('2500'))
        ac_svc.cerrar_acondicionamiento(acond, self.user)
        lote_svc.asignar_venta(lote, self._venta(kilos='900', precio='1583.3333'), self.user)

        lote.refresh_from_db()
        self.assertEqual(lote.costo_compra, Decimal('1000000.00'))
        self.assertEqual(lote.costo_acondicionamiento, Decimal('50000.00'))
        self.assertEqual(lote.valor_coproductos, Decimal('2500.00'))
        self.assertEqual(lote.costo_total, Decimal('1050000.00'))
        self.assertEqual(lote.margen, lote.importe_venta + Decimal('2500.00')
                         - Decimal('1050000.00'))

    def test_margen_por_fardo_usa_el_costo_exacto_de_compra(self):
        """El costo de compra existe por fardo: prorratearlo perdería información."""
        otro = rom_svc.abrir_romaneo(
            empresa=self.empresa, sucursal=self.sucursal, productor=self.productor,
            variedad=self.burley, campania=self.campania, fecha=date(2026, 9, 2),
            usuario=self.user)
        rom_svc.agregar_fardo(otro, clase=self.b1f, kilos=Decimal('600'), usuario=self.user)
        rom_svc.agregar_fardo(otro, clase=self.b1f, kilos=Decimal('400'), usuario=self.user)
        otro = rom_svc.confirmar_romaneo(otro, self.user)

        lote = self._lote()
        for fardo in otro.fardos.all():
            lote_svc.agregar_fardo(lote, fardo, self.user)
        lote = lote_svc.armar_lote(lote, self.user)

        filas = margen_svc.margen_por_fardo(lote)
        por_kilos = {f['kilos']: f for f in filas}

        # Sin acondicionar ni vender: el costo es exactamente el importe del fardo.
        self.assertEqual(por_kilos[Decimal('600.00')]['costo_compra'], Decimal('600000.00'))
        self.assertEqual(por_kilos[Decimal('400.00')]['costo_compra'], Decimal('400000.00'))
        self.assertEqual(sum(f['costo_compra'] for f in filas), lote.costo_compra)

    def test_margen_por_fardo_prorratea_acondicionamiento_e_ingreso(self):
        """1.000 kg en dos fardos de 600 y 400: el costo de proceso se reparte 60/40."""
        otro = rom_svc.abrir_romaneo(
            empresa=self.empresa, sucursal=self.sucursal, productor=self.productor,
            variedad=self.burley, campania=self.campania, fecha=date(2026, 9, 2),
            usuario=self.user)
        rom_svc.agregar_fardo(otro, clase=self.b1f, kilos=Decimal('600'), usuario=self.user)
        rom_svc.agregar_fardo(otro, clase=self.b1f, kilos=Decimal('400'), usuario=self.user)
        otro = rom_svc.confirmar_romaneo(otro, self.user)

        lote = self._lote()
        for fardo in otro.fardos.all():
            lote_svc.agregar_fardo(lote, fardo, self.user)
        lote = lote_svc.armar_lote(lote, self.user)

        acond = self._acond(lote, entrada='1000', salida='950')
        ac_svc.agregar_costo(acond, concepto="Proceso", importe=Decimal('100000'))
        ac_svc.cerrar_acondicionamiento(acond, self.user)
        lote_svc.asignar_venta(lote, self._venta(kilos='950', precio='2000'), self.user)
        lote.refresh_from_db()

        filas = margen_svc.margen_por_fardo(lote)
        por_kilos = {f['kilos']: f for f in filas}

        self.assertEqual(por_kilos[Decimal('600.00')]['costo_acondicionamiento'],
                         Decimal('60000.00'))
        self.assertEqual(por_kilos[Decimal('400.00')]['costo_acondicionamiento'],
                         Decimal('40000.00'))
        self.assertEqual(por_kilos[Decimal('600.00')]['ingreso'], Decimal('1140000.00'))
        self.assertEqual(por_kilos[Decimal('400.00')]['ingreso'], Decimal('760000.00'))
        # Y la suma de los fardos reconstruye el margen del lote.
        self.assertEqual(sum(f['margen'] for f in filas), lote.margen)

    def test_margen_por_lote_filtra_por_condic(self):
        lote = self._lote_armado(kilos='1000')
        lote_svc.asignar_venta(lote, self._venta(kilos='1000'), self.user)

        self.assertEqual(len(margen_svc.margen_por_lote(self.empresa.pk, condic=1)), 1)
        self.assertEqual(len(margen_svc.margen_por_lote(self.empresa.pk, condic=2)), 0)

    def test_resumen_por_clase_suma_lo_mismo_que_los_fardos(self):
        lote = self._lote_armado(kilos='1000')
        lote_svc.asignar_venta(lote, self._venta(kilos='1000', precio='1500'), self.user)
        lote.refresh_from_db()

        por_fardo = margen_svc.margen_por_fardo(lote)
        por_clase = margen_svc.resumen_por_clase(lote)

        self.assertEqual(sum(g['margen'] for g in por_clase),
                         sum(f['margen'] for f in por_fardo))

    def test_totales_recalculan_el_porcentaje_y_no_lo_promedian(self):
        lote = self._lote_armado(kilos='1000')
        lote_svc.asignar_venta(lote, self._venta(kilos='1000', precio='1500'), self.user)

        filas = margen_svc.margen_por_lote(self.empresa.pk)
        acumulado = margen_svc.totales(filas)

        esperado = (acumulado['margen'] / acumulado['costo_total'] * Decimal('100')).quantize(
            Decimal('0.01'))
        self.assertEqual(acumulado['margen_porcentaje'], esperado)


# ===========================================================================
# La Etapa 4 tiene que seguir cerrando
# ===========================================================================

class ConciliacionTests(LoteBaseTestCase):

    def test_la_conciliacion_contempla_las_bajas_de_acondicionamiento(self):
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote, entrada='1000', salida='900')
        ac_svc.agregar_coproducto(acond, producto=self.palo, kilos=Decimal('80'))
        ac_svc.cerrar_acondicionamiento(acond, self.user)

        filas = stock_svc.conciliar(self.empresa.pk, self.sucursal.pk)
        fila = next(f for f in filas if f['variedad'].pk == self.burley.pk)

        self.assertEqual(fila['recibidos'], Decimal('1000.00'))
        self.assertEqual(fila['acondicionados'], Decimal('100.00'))
        self.assertEqual(fila['esperado'], Decimal('900.00'))
        self.assertEqual(fila['diferencia'], Decimal('0.00'))

    def test_el_stock_se_reconstruye_solo(self):
        lote = self._lote_armado(kilos='1000')
        acond = self._acond(lote, entrada='1000', salida='900')
        ac_svc.cerrar_acondicionamiento(acond, self.user)

        StockSucursal.objects.filter(producto=self.producto).update(cantidad=Decimal('7'))

        self.assertEqual(self._stock(), Decimal('900.00'))

    def test_no_regresion_de_los_terminos_anteriores(self):
        """Los tres términos del tabaco no pueden alterar compras, ventas ni remitos."""
        from productos.services import stock_service

        nombres = {t['nombre'] for t in stock_service._terminos()}
        self.assertTrue({'compras', 'recepciones', 'ventas', 'remitos_internos'} <= nombres)
        self.assertIn('agricola_tabaco_fardos', nombres)
        self.assertIn('agricola_tabaco_acond_bajas', nombres)
        self.assertIn('agricola_tabaco_acond_coproductos', nombres)


class DosBorradoresTests(LoteBaseTestCase):
    """Dos corridas abiertas a la vez no pueden consumir, sumadas, más kilos de los que hay.

    Al abrir el segundo borrador el primero todavía no descontaba nada —un borrador no mueve
    stock—, así que la validación de apertura no podía detectarlo. La detecta el cierre.
    """

    def test_no_se_cierran_dos_borradores_que_suman_mas_que_el_lote(self):
        lote = self._lote_armado(kilos='1000')
        primero = self._acond(lote, entrada='1000', salida='950')
        segundo = self._acond(lote, entrada='1000', salida='950')

        ac_svc.cerrar_acondicionamiento(primero, self.user)

        with self.assertRaises(ValidationError) as ctx:
            ac_svc.cerrar_acondicionamiento(segundo, self.user)
        self.assertIn("disponibles", str(ctx.exception))
        self.assertEqual(self._stock(), Decimal('950.00'))
