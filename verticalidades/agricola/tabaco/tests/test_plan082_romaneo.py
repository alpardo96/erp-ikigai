"""Plan 082 — servicios del romaneo.

Lo que se está protegiendo acá, en orden de importancia:

1. Que el precio quede CONGELADO. Si cambiar una lista de precio moviera el importe de un romaneo
   ya cargado, la liquidación que se le entregó al productor dejaría de ser reconstruible.
2. Que los totales se DERIVEN del detalle y nunca se ajusten por delta.
3. Que la reclasificación no borre la historia.
4. Que un documento confirmado no se pueda editar por la puerta de atrás.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase

from core.models import ContadorDocumento
from empresas.models import Empresa, Sucursal
from facturacion.models import ClienteProveedor
from verticalidades.agricola.core_agricola.models import Campania
from verticalidades.agricola.tabaco.models import (ClaseTabaco, FardoTabaco, ListaPrecioTabaco,
                                                   ProductorTabaco, ReclasificacionFardo,
                                                   RomaneoTabaco, VariedadTabaco)
from verticalidades.agricola.tabaco.services import romaneo as svc

User = get_user_model()


class RomaneoBaseTestCase(TestCase):
    """Escenario mínimo: una empresa con Burley, su lista aprobada y unas clases reales."""

    # (detalle, coeficiente) tomados del maestro real
    CLASES = [('B1F', '1'), ('B1FR', '0.85'), ('B2F', '0.92'), ('B3F', '0.78'),
              ('C1F', '0.96'), ('C2F', '0.86'), ('X1F', '0.83'), ('N5K', '0.17')]

    def setUp(self):
        self.user = User.objects.create_user(username='romaneador', password='pw')
        self.empresa = Empresa.objects.create(nombre="ACOPIO TEST", cuit="30111111112",
                                              tipo_actividad='AGRICOLA')
        self.sucursal = Sucursal.objects.create(empresa=self.empresa, nombre="CENTRAL")
        self.productor = ClienteProveedor.objects.create(
            razon_social="PRODUCTOR TEST", cuit="20181662515", tipo_entidad=2,
            empresa=self.empresa)

        self.campania = Campania.objects.create(
            empresa=self.empresa, codigo='2023/2024', detalle='TEST',
            fecha_inicio=date(2024, 1, 1))
        self.burley = VariedadTabaco.objects.create(
            empresa=self.empresa, codigo=1, detalle='BURLEY')
        self.virginia = VariedadTabaco.objects.create(
            empresa=self.empresa, codigo=2, detalle='VIRGINIA')

        self.clases = {}
        for n, (detalle, coef) in enumerate(self.CLASES, start=1):
            self.clases[detalle] = ClaseTabaco.objects.create(
                empresa=self.empresa, variedad=self.burley, codigo=n,
                detalle=detalle, coeficiente=Decimal(coef))

        self.lista = ListaPrecioTabaco.objects.create(
            empresa=self.empresa, variedad=self.burley, campania=self.campania,
            vigencia_desde=date(2024, 3, 1), precio_ponderante=Decimal('2500.00'),
            aprobada=True)

    def _abrir(self, **kwargs):
        opciones = dict(empresa=self.empresa, sucursal=self.sucursal, productor=self.productor,
                        variedad=self.burley, campania=self.campania, fecha=date(2024, 3, 1),
                        usuario=self.user)
        opciones.update(kwargs)
        return svc.abrir_romaneo(**opciones)


class AperturaTests(RomaneoBaseTestCase):

    def test_abre_en_borrador_con_el_ponderante_congelado(self):
        r = self._abrir()

        self.assertEqual(r.estado, RomaneoTabaco.BORRADOR)
        self.assertIsNone(r.numero)                      # el número se toma al confirmar
        self.assertEqual(r.lista_precio, self.lista)
        self.assertEqual(r.ponderante_aplicado, Decimal('2500.00'))

    def test_sin_lista_aprobada_no_abre(self):
        self.lista.aprobada = False
        self.lista.save(update_fields=['aprobada'])

        with self.assertRaises(ValidationError) as ctx:
            self._abrir()
        self.assertIn('lista de precio aprobada', str(ctx.exception))

    def test_productor_inhabilitado_no_abre(self):
        ProductorTabaco.objects.create(cliente_proveedor=self.productor, empresa=self.empresa,
                                       habilitado=False)

        with self.assertRaises(ValidationError) as ctx:
            self._abrir()
        self.assertIn('no está habilitado', str(ctx.exception))

    def test_toma_el_coeficiente_del_productor(self):
        ProductorTabaco.objects.create(cliente_proveedor=self.productor, empresa=self.empresa,
                                       coeficiente=Decimal('1.0500'))

        self.assertEqual(self._abrir().coeficiente_productor, Decimal('1.0500'))


class CargaDeFardosTests(RomaneoBaseTestCase):

    # Casos reales del sistema heredado: ponderante 2.500, marzo 2024.
    CASOS = [('B1F', '750', '2500.00', '1875000.00'),
             ('B1FR', '76', '2125.00', '161500.00'),
             ('B2F', '565', '2300.00', '1299500.00'),
             ('B3F', '36', '1950.00', '70200.00'),
             ('C1F', '576', '2400.00', '1382400.00'),
             ('C2F', '843', '2150.00', '1812450.00')]

    def test_precio_e_importe_contra_datos_reales(self):
        r = self._abrir()
        for detalle, kilos, precio_esp, importe_esp in self.CASOS:
            with self.subTest(clase=detalle):
                f = svc.agregar_fardo(r, clase=self.clases[detalle], kilos=Decimal(kilos),
                                      usuario=self.user)
                self.assertEqual(f.precio_aplicado, Decimal(precio_esp))
                self.assertEqual(f.importe, Decimal(importe_esp))

    def test_el_precio_queda_congelado(self):
        """La prueba que sostiene todo: renegociar la lista no puede mover un fardo ya cargado."""
        r = self._abrir()
        f = svc.agregar_fardo(r, clase=self.clases['B1F'], kilos=Decimal('100'), usuario=self.user)
        self.assertEqual(f.precio_aplicado, Decimal('2500.00'))

        self.lista.precio_ponderante = Decimal('9999.00')
        self.lista.save(update_fields=['precio_ponderante'])

        f.refresh_from_db()
        self.assertEqual(f.precio_aplicado, Decimal('2500.00'))
        self.assertEqual(f.importe, Decimal('250000.00'))
        # Y un fardo nuevo del MISMO romaneo también usa el ponderante congelado.
        f2 = svc.agregar_fardo(r, clase=self.clases['B1F'], kilos=Decimal('100'), usuario=self.user)
        self.assertEqual(f2.precio_aplicado, Decimal('2500.00'))

    def test_se_congela_tambien_el_coeficiente(self):
        r = self._abrir()
        f = svc.agregar_fardo(r, clase=self.clases['B1FR'], kilos=Decimal('10'), usuario=self.user)

        self.clases['B1FR'].coeficiente = Decimal('0.5')
        self.clases['B1FR'].save(update_fields=['coeficiente'])

        f.refresh_from_db()
        self.assertEqual(f.coeficiente_aplicado, Decimal('0.8500'))

    def test_numera_los_fardos_correlativos(self):
        r = self._abrir()
        for _ in range(3):
            svc.agregar_fardo(r, clase=self.clases['B1F'], kilos=Decimal('10'), usuario=self.user)

        self.assertEqual(list(r.fardos.values_list('numero_fardo', flat=True)), [1, 2, 3])

    def test_renumera_desde_el_maximo_y_no_desde_el_conteo(self):
        """Si se borra un fardo del medio, contar daría un número ya usado."""
        r = self._abrir()
        f1 = svc.agregar_fardo(r, clase=self.clases['B1F'], kilos=Decimal('10'), usuario=self.user)
        svc.agregar_fardo(r, clase=self.clases['B1F'], kilos=Decimal('10'), usuario=self.user)
        svc.quitar_fardo(f1)

        f3 = svc.agregar_fardo(r, clase=self.clases['B1F'], kilos=Decimal('10'), usuario=self.user)
        self.assertEqual(f3.numero_fardo, 3)

    def test_rechaza_clase_de_otra_variedad(self):
        ajena = ClaseTabaco.objects.create(empresa=self.empresa, variedad=self.virginia,
                                           codigo=99, detalle='X1L', coeficiente=Decimal('0.71'))
        r = self._abrir()

        with self.assertRaises(ValidationError) as ctx:
            svc.agregar_fardo(r, clase=ajena, kilos=Decimal('10'), usuario=self.user)
        self.assertIn('VIRGINIA', str(ctx.exception))

    def test_rechaza_clase_inactiva(self):
        self.clases['B1F'].activa = False
        self.clases['B1F'].save(update_fields=['activa'])
        r = self._abrir()

        with self.assertRaises(ValidationError):
            svc.agregar_fardo(r, clase=self.clases['B1F'], kilos=Decimal('10'), usuario=self.user)

    def test_rechaza_kilos_no_positivos(self):
        r = self._abrir()
        for kilos in (Decimal('0'), Decimal('-5')):
            with self.subTest(kilos=kilos):
                with self.assertRaises(ValidationError):
                    svc.agregar_fardo(r, clase=self.clases['B1F'], kilos=kilos, usuario=self.user)

    def test_constraint_de_kilos_en_la_base(self):
        """Segunda barrera: aunque alguien esquive el servicio, la base rechaza."""
        r = self._abrir()
        with self.assertRaises(IntegrityError):
            FardoTabaco.objects.create(
                romaneo=r, numero_fardo=1, clase=self.clases['B1F'],
                coeficiente_aplicado=Decimal('1'), precio_aplicado=Decimal('2500'),
                kilos=Decimal('0'))

    def test_editar_recalcula_el_importe(self):
        r = self._abrir()
        f = svc.agregar_fardo(r, clase=self.clases['B1F'], kilos=Decimal('100'), usuario=self.user)

        svc.editar_fardo(f, clase=self.clases['B2F'], kilos=Decimal('200'), usuario=self.user)

        f.refresh_from_db()
        self.assertEqual(f.precio_aplicado, Decimal('2300.00'))
        self.assertEqual(f.importe, Decimal('460000.00'))


class TotalesTests(RomaneoBaseTestCase):

    def test_totales_se_derivan_del_detalle(self):
        r = self._abrir()
        svc.agregar_fardo(r, clase=self.clases['B1F'], kilos=Decimal('750'), usuario=self.user)
        svc.agregar_fardo(r, clase=self.clases['B2F'], kilos=Decimal('565'), usuario=self.user)

        r.refresh_from_db()
        self.assertEqual(r.total_fardos, 2)
        self.assertEqual(r.total_kilos, Decimal('1315.00'))
        self.assertEqual(r.total_importe, Decimal('3174500.00'))
        # PPP = 3.174.500 / 1.315
        self.assertEqual(r.precio_promedio, Decimal('2414.07'))
        # % sobre el ponderante = 2.414,07 × 100 / 2.500
        self.assertEqual(r.porcentaje_ponderante, Decimal('96.56'))

    def test_quitar_un_fardo_baja_los_totales(self):
        r = self._abrir()
        f = svc.agregar_fardo(r, clase=self.clases['B1F'], kilos=Decimal('100'), usuario=self.user)
        svc.agregar_fardo(r, clase=self.clases['B1F'], kilos=Decimal('50'), usuario=self.user)

        svc.quitar_fardo(f)

        r.refresh_from_db()
        self.assertEqual(r.total_fardos, 1)
        self.assertEqual(r.total_kilos, Decimal('50.00'))

    def test_recalcular_es_autorreparable(self):
        """Aunque el caché quede mal por cualquier motivo, se reconstruye desde los fardos."""
        r = self._abrir()
        svc.agregar_fardo(r, clase=self.clases['B1F'], kilos=Decimal('100'), usuario=self.user)

        RomaneoTabaco.objects.filter(pk=r.pk).update(
            total_kilos=Decimal('99999'), total_fardos=42, total_importe=Decimal('1'))
        r.refresh_from_db()

        svc.recalcular_totales(r)

        r.refresh_from_db()
        self.assertEqual(r.total_kilos, Decimal('100.00'))
        self.assertEqual(r.total_fardos, 1)
        self.assertEqual(r.total_importe, Decimal('250000.00'))

    def test_romaneo_vacio_no_divide_por_cero(self):
        r = self._abrir()
        svc.recalcular_totales(r)

        r.refresh_from_db()
        self.assertEqual(r.precio_promedio, Decimal('0.00'))
        self.assertEqual(r.porcentaje_ponderante, Decimal('0.00'))


class EstadisticaPorGrupoTests(RomaneoBaseTestCase):

    def test_agrupa_y_calcula_participacion(self):
        r = self._abrir()
        svc.agregar_fardo(r, clase=self.clases['B1F'], kilos=Decimal('600'), usuario=self.user)
        svc.agregar_fardo(r, clase=self.clases['B2F'], kilos=Decimal('200'), usuario=self.user)
        svc.agregar_fardo(r, clase=self.clases['C1F'], kilos=Decimal('200'), usuario=self.user)

        r.refresh_from_db()
        por_grupo = {g['grupo']: g for g in svc.estadistica_por_grupo(r)}

        self.assertEqual(por_grupo['B']['kilos'], Decimal('800.00'))
        self.assertEqual(por_grupo['B']['fardos'], 2)
        self.assertEqual(por_grupo['B']['porcentaje'], Decimal('80.00'))
        self.assertEqual(por_grupo['C']['porcentaje'], Decimal('20.00'))

    def test_incluye_grupos_que_el_sistema_heredado_perdia(self):
        """El VFP agrupaba con una lista fija B/C/N/T/X: los kilos del grupo H no aparecían."""
        h1f = ClaseTabaco.objects.create(empresa=self.empresa, variedad=self.burley,
                                         codigo=90, detalle='H1F', coeficiente=Decimal('1.05'))
        r = self._abrir()
        svc.agregar_fardo(r, clase=self.clases['B1F'], kilos=Decimal('50'), usuario=self.user)
        svc.agregar_fardo(r, clase=h1f, kilos=Decimal('50'), usuario=self.user)

        r.refresh_from_db()
        grupos = {g['grupo'] for g in svc.estadistica_por_grupo(r)}
        self.assertEqual(grupos, {'B', 'H'})

        # Y la suma por grupo cierra contra el total general.
        suma = sum(g['kilos'] for g in svc.estadistica_por_grupo(r))
        self.assertEqual(suma, r.total_kilos)


class ConfirmacionTests(RomaneoBaseTestCase):

    def _con_un_fardo(self):
        r = self._abrir()
        svc.agregar_fardo(r, clase=self.clases['B1F'], kilos=Decimal('100'), usuario=self.user)
        return r

    def test_confirmar_numera_correlativo(self):
        r1 = svc.confirmar_romaneo(self._con_un_fardo(), self.user)
        r2 = svc.confirmar_romaneo(self._con_un_fardo(), self.user)

        self.assertEqual(r1.numero, 1)
        self.assertEqual(r2.numero, 2)
        self.assertEqual(r1.estado, RomaneoTabaco.CONFIRMADO)

    def test_confirmar_dos_veces_no_renumera(self):
        r = self._con_un_fardo()
        primero = svc.confirmar_romaneo(r, self.user).numero
        segundo = svc.confirmar_romaneo(r, self.user).numero

        self.assertEqual(primero, segundo)
        contador = ContadorDocumento.objects.get(
            empresa=self.empresa, punto=1, tipo_documento=ContadorDocumento.ROMANEO_TABACO)
        self.assertEqual(contador.ultimo_numero, 1)

    def test_no_se_confirma_un_romaneo_vacio(self):
        with self.assertRaises(ValidationError) as ctx:
            svc.confirmar_romaneo(self._abrir(), self.user)
        self.assertIn('sin fardos', str(ctx.exception))

    def test_confirmado_no_admite_mas_fardos(self):
        r = svc.confirmar_romaneo(self._con_un_fardo(), self.user)

        with self.assertRaises(ValidationError) as ctx:
            svc.agregar_fardo(r, clase=self.clases['B2F'], kilos=Decimal('10'), usuario=self.user)
        self.assertIn('no admite cambios', str(ctx.exception))

    def test_confirmado_no_admite_edicion_ni_borrado(self):
        r = self._con_un_fardo()
        fardo = r.fardos.first()
        svc.confirmar_romaneo(r, self.user)

        with self.assertRaises(ValidationError):
            svc.editar_fardo(fardo, kilos=Decimal('999'), usuario=self.user)
        with self.assertRaises(ValidationError):
            svc.quitar_fardo(fardo)


class AnulacionTests(RomaneoBaseTestCase):

    def _confirmado(self):
        r = self._abrir()
        svc.agregar_fardo(r, clase=self.clases['B1F'], kilos=Decimal('100'), usuario=self.user)
        return svc.confirmar_romaneo(r, self.user)

    def test_anular_conserva_los_fardos(self):
        """La mercadería entró y se pesó: anular el documento no borra el hecho."""
        r = self._confirmado()

        svc.anular_romaneo(r, "Error de carga", self.user)

        r.refresh_from_db()
        self.assertEqual(r.estado, RomaneoTabaco.ANULADO)
        self.assertEqual(r.motivo_anulacion, "Error de carga")
        self.assertEqual(r.anulado_por, self.user)
        self.assertIsNotNone(r.anulado_el)
        self.assertEqual(r.fardos.count(), 1)
        self.assertIsNotNone(r.numero)                    # el número usado no se recicla

    def test_anular_exige_motivo(self):
        with self.assertRaises(ValidationError):
            svc.anular_romaneo(self._confirmado(), "   ", self.user)

    def test_no_se_anula_un_romaneo_liquidado(self):
        r = self._confirmado()
        RomaneoTabaco.objects.filter(pk=r.pk).update(estado=RomaneoTabaco.LIQUIDADO)
        r.refresh_from_db()

        with self.assertRaises(ValidationError) as ctx:
            svc.anular_romaneo(r, "motivo", self.user)
        self.assertIn('liquidación', str(ctx.exception))

    def test_anular_es_idempotente(self):
        r = self._confirmado()
        svc.anular_romaneo(r, "Error", self.user)
        svc.anular_romaneo(r, "Otro motivo", self.user)

        r.refresh_from_db()
        self.assertEqual(r.motivo_anulacion, "Error")     # no se pisa el motivo original

    def test_no_se_confirma_un_anulado(self):
        r = self._confirmado()
        svc.anular_romaneo(r, "Error", self.user)

        with self.assertRaises(ValidationError):
            svc.confirmar_romaneo(r, self.user)


class ReclasificacionTests(RomaneoBaseTestCase):

    def setUp(self):
        super().setUp()
        self.romaneo = self._abrir()
        self.fardo = svc.agregar_fardo(self.romaneo, clase=self.clases['B1F'],
                                       kilos=Decimal('100'), usuario=self.user)
        svc.confirmar_romaneo(self.romaneo, self.user)
        self.romaneo.refresh_from_db()

    def test_versiona_la_clasificacion_anterior(self):
        svc.reclasificar_fardo(self.fardo, clase_nueva=self.clases['B2F'],
                               motivo="Revisión de calidad", usuario=self.user)

        version = ReclasificacionFardo.objects.get(fardo=self.fardo)
        self.assertEqual(version.clase_anterior, self.clases['B1F'])
        self.assertEqual(version.coeficiente_anterior, Decimal('1.0000'))
        self.assertEqual(version.precio_anterior, Decimal('2500.00'))
        self.assertEqual(version.importe_anterior, Decimal('250000.00'))
        self.assertEqual(version.clase_nueva, self.clases['B2F'])
        self.assertEqual(version.precio_nuevo, Decimal('2300.00'))
        self.assertEqual(version.motivo, "Revisión de calidad")
        self.assertEqual(version.usuario, self.user)

    def test_actualiza_el_fardo_y_los_totales(self):
        svc.reclasificar_fardo(self.fardo, clase_nueva=self.clases['B2F'],
                               motivo="Revisión", usuario=self.user)

        self.fardo.refresh_from_db()
        self.romaneo.refresh_from_db()
        self.assertEqual(self.fardo.clase, self.clases['B2F'])
        self.assertEqual(self.fardo.importe, Decimal('230000.00'))
        self.assertEqual(self.romaneo.total_importe, Decimal('230000.00'))

    def test_admite_varias_reclasificaciones_encadenadas(self):
        svc.reclasificar_fardo(self.fardo, clase_nueva=self.clases['B2F'],
                               motivo="Primera", usuario=self.user)
        svc.reclasificar_fardo(self.fardo, clase_nueva=self.clases['B3F'],
                               motivo="Segunda", usuario=self.user)

        historia = list(ReclasificacionFardo.objects.filter(fardo=self.fardo)
                        .order_by('fecha', 'id'))
        self.assertEqual(len(historia), 2)
        self.assertEqual(historia[0].clase_anterior, self.clases['B1F'])
        self.assertEqual(historia[1].clase_anterior, self.clases['B2F'])

    def test_exige_motivo(self):
        with self.assertRaises(ValidationError):
            svc.reclasificar_fardo(self.fardo, clase_nueva=self.clases['B2F'],
                                   motivo="", usuario=self.user)

    def test_rechaza_la_misma_clase(self):
        with self.assertRaises(ValidationError):
            svc.reclasificar_fardo(self.fardo, clase_nueva=self.clases['B1F'],
                                   motivo="Sin cambio", usuario=self.user)

    def test_no_reclasifica_un_romaneo_liquidado(self):
        RomaneoTabaco.objects.filter(pk=self.romaneo.pk).update(estado=RomaneoTabaco.LIQUIDADO)
        self.fardo.refresh_from_db()

        with self.assertRaises(ValidationError) as ctx:
            svc.reclasificar_fardo(self.fardo, clase_nueva=self.clases['B2F'],
                                   motivo="Tarde", usuario=self.user)
        self.assertIn('ya fue liquidado', str(ctx.exception))

    def test_no_reclasifica_un_romaneo_anulado(self):
        svc.anular_romaneo(self.romaneo, "Error", self.user)
        self.fardo.refresh_from_db()

        with self.assertRaises(ValidationError):
            svc.reclasificar_fardo(self.fardo, clase_nueva=self.clases['B2F'],
                                   motivo="Tarde", usuario=self.user)


class AislamientoTests(RomaneoBaseTestCase):

    def test_no_se_usa_una_clase_de_otra_empresa(self):
        otra = Empresa.objects.create(nombre="OTRO ACOPIO", cuit="30999999998")
        otra_var = VariedadTabaco.objects.create(empresa=otra, codigo=1, detalle='BURLEY')
        clase_ajena = ClaseTabaco.objects.create(empresa=otra, variedad=otra_var, codigo=1,
                                                 detalle='B1F', coeficiente=Decimal('1'))
        r = self._abrir()

        with self.assertRaises(ValidationError):
            svc.agregar_fardo(r, clase=clase_ajena, kilos=Decimal('10'), usuario=self.user)

    def test_la_serie_es_por_empresa(self):
        """Cada empresa lleva su propia numeración de romaneos."""
        r = self._abrir()
        svc.agregar_fardo(r, clase=self.clases['B1F'], kilos=Decimal('10'), usuario=self.user)
        svc.confirmar_romaneo(r, self.user)

        self.assertEqual(
            ContadorDocumento.objects.filter(
                tipo_documento=ContadorDocumento.ROMANEO_TABACO).count(), 1)
        self.assertEqual(
            ContadorDocumento.objects.get(
                tipo_documento=ContadorDocumento.ROMANEO_TABACO).empresa, self.empresa)
