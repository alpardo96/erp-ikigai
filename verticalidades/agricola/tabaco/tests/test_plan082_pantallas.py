"""Plan 082 — humo de las pantallas del romaneo.

Compilar una plantilla no alcanza: `{% url %}`, los filtros y los accesos a atributos fallan
recién al RENDERIZAR. Estos tests recorren el circuito completo desde el cliente de prueba —abrir,
cargar fardos, cotizar, confirmar, imprimir, anular, reclasificar— que es la única forma de que un
nombre de ruta mal escrito se caiga acá y no en producción.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from empresas.models import Empresa, Sucursal
from facturacion.models import ClienteProveedor
from verticalidades.agricola.core_agricola.models import Campania
from verticalidades.agricola.tabaco.models import (ClaseTabaco, ListaPrecioTabaco,
                                                   ReclasificacionFardo, RomaneoTabaco,
                                                   VariedadTabaco)
from verticalidades.agricola.tabaco.services import romaneo as svc

User = get_user_model()


class PantallasRomaneoTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='romaneador', password='pw', is_staff=True)
        self.empresa = Empresa.objects.create(nombre="ACOPIO TEST", cuit="30111111112",
                                              tipo_actividad='AGRICOLA')
        self.sucursal = Sucursal.objects.create(empresa=self.empresa, nombre="CENTRAL")
        self.productor = ClienteProveedor.objects.create(
            razon_social="PRODUCTOR TEST", cuit="20181662515", tipo_entidad=2,
            empresa=self.empresa)

        self.campania = Campania.objects.create(
            empresa=self.empresa, codigo='2023/2024', detalle='TEST',
            fecha_inicio=date(2024, 1, 1))
        self.burley = VariedadTabaco.objects.create(empresa=self.empresa, codigo=1,
                                                    detalle='BURLEY')
        self.b1f = ClaseTabaco.objects.create(empresa=self.empresa, variedad=self.burley,
                                              codigo=1, detalle='B1F', coeficiente=Decimal('1'))
        self.b2f = ClaseTabaco.objects.create(empresa=self.empresa, variedad=self.burley,
                                              codigo=2, detalle='B2F', coeficiente=Decimal('0.92'))
        self.lista = ListaPrecioTabaco.objects.create(
            empresa=self.empresa, variedad=self.burley, campania=self.campania,
            vigencia_desde=date(2024, 1, 1), precio_ponderante=Decimal('2500.00'),
            aprobada=True)

        self.client.force_login(self.user)
        sesion = self.client.session
        sesion['empresa_id'] = self.empresa.id
        # El menú lateral de `base.html` sólo se dibuja con sucursal en sesión.
        sesion['sucursal_id'] = self.sucursal.id
        sesion.save()

    def _romaneo(self, con_fardo=True):
        r = svc.abrir_romaneo(empresa=self.empresa, sucursal=self.sucursal,
                              productor=self.productor, variedad=self.burley,
                              campania=self.campania, fecha=date(2024, 3, 1), usuario=self.user)
        if con_fardo:
            svc.agregar_fardo(r, clase=self.b1f, kilos=Decimal('100'), usuario=self.user)
            r.refresh_from_db()
        return r

    # -- pantallas ----------------------------------------------------------

    def test_listado_renderiza(self):
        self._romaneo()
        r = self.client.get(reverse('agro_romaneo_listado'))

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'PRODUCTOR TEST')

    def test_listado_ofrece_el_filtro_de_condicion(self):
        """Regla del proyecto: todo listado con importes lleva el filtro de condición."""
        r = self.client.get(reverse('agro_romaneo_listado'))

        self.assertContains(r, 'name="condic"')
        self.assertContains(r, 'Presupuestado')

    def test_grilla_filtra_por_estado(self):
        borrador = self._romaneo()
        confirmado = svc.confirmar_romaneo(self._romaneo(), self.user)

        r = self.client.get(reverse('agro_romaneo_grilla'),
                            {'estado': RomaneoTabaco.CONFIRMADO})

        self.assertContains(r, f'{confirmado.numero:08d}')
        self.assertNotContains(r, f'romaneos/{borrador.id}/carga/')

    def test_formulario_de_alta_renderiza(self):
        r = self.client.get(reverse('agro_romaneo_nuevo'))

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Abrir Romaneo')

    def test_pantalla_de_carga_renderiza(self):
        romaneo = self._romaneo()
        r = self.client.get(reverse('agro_romaneo_carga', args=[romaneo.id]))

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Agregar Fardo')
        self.assertContains(r, 'B1F')

    def test_detalle_e_impresion_renderizan(self):
        romaneo = svc.confirmar_romaneo(self._romaneo(), self.user)

        for nombre in ('agro_romaneo_detalle', 'agro_romaneo_imprimir'):
            with self.subTest(url=nombre):
                r = self.client.get(reverse(nombre, args=[romaneo.id]))
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, 'PRODUCTOR TEST')

    def test_modales_renderizan(self):
        romaneo = svc.confirmar_romaneo(self._romaneo(), self.user)
        fardo = romaneo.fardos.first()

        self.assertEqual(self.client.get(
            reverse('agro_romaneo_anular', args=[romaneo.id])).status_code, 200)
        self.assertEqual(self.client.get(
            reverse('agro_fardo_reclasificar', args=[fardo.id])).status_code, 200)

    # -- circuito de carga --------------------------------------------------

    def test_abrir_desde_el_formulario(self):
        r = self.client.post(reverse('agro_romaneo_nuevo'), {
            'productor': self.productor.pk, 'variedad': self.burley.id,
            'campania': self.campania.id, 'fecha': '2024-03-01', 'condic': 1,
        })

        self.assertEqual(r.status_code, 302)
        romaneo = RomaneoTabaco.objects.get()
        self.assertEqual(romaneo.estado, RomaneoTabaco.BORRADOR)
        self.assertEqual(romaneo.ponderante_aplicado, Decimal('2500.00'))

    def test_abrir_sin_lista_aprobada_muestra_el_error_en_pantalla(self):
        self.lista.aprobada = False
        self.lista.save(update_fields=['aprobada'])

        r = self.client.post(reverse('agro_romaneo_nuevo'), {
            'productor': self.productor.pk, 'variedad': self.burley.id,
            'campania': self.campania.id, 'fecha': '2024-03-01', 'condic': 1,
        })

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'lista de precio aprobada')
        self.assertFalse(RomaneoTabaco.objects.exists())

    def test_cotizar_devuelve_precio_e_importe(self):
        romaneo = self._romaneo(con_fardo=False)

        r = self.client.get(reverse('agro_fardo_cotizar', args=[romaneo.id]),
                            {'clase': self.b1f.id, 'kilos': '750,00'})

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '2.500,00')        # precio unitario
        self.assertContains(r, '1.875.000,00')    # importe

    def test_cotizar_sin_clase_no_rompe(self):
        romaneo = self._romaneo(con_fardo=False)
        r = self.client.get(reverse('agro_fardo_cotizar', args=[romaneo.id]), {'kilos': '10'})

        self.assertEqual(r.status_code, 200)

    def test_agregar_fardo_desde_la_pantalla(self):
        romaneo = self._romaneo(con_fardo=False)

        r = self.client.post(reverse('agro_fardo_agregar', args=[romaneo.id]),
                             {'clase': self.b2f.id, 'kilos': '565,00'})

        self.assertEqual(r.status_code, 200)
        romaneo.refresh_from_db()
        self.assertEqual(romaneo.total_fardos, 1)
        self.assertEqual(romaneo.total_importe, Decimal('1299500.00'))
        self.assertContains(r, '1.299.500,00')     # el panel vuelve con el total actualizado

    def test_agregar_fardo_con_kilos_invalidos_avisa_sin_romper(self):
        romaneo = self._romaneo(con_fardo=False)

        r = self.client.post(reverse('agro_fardo_agregar', args=[romaneo.id]),
                             {'clase': self.b1f.id, 'kilos': '0,00'})

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'mayores que cero')
        self.assertEqual(romaneo.fardos.count(), 0)

    def test_quitar_fardo_desde_la_pantalla(self):
        romaneo = self._romaneo()
        fardo = romaneo.fardos.first()

        r = self.client.post(reverse('agro_fardo_quitar', args=[fardo.id]))

        self.assertEqual(r.status_code, 200)
        romaneo.refresh_from_db()
        self.assertEqual(romaneo.total_fardos, 0)

    def test_typeahead_de_clases_acotado_a_la_variedad(self):
        virginia = VariedadTabaco.objects.create(empresa=self.empresa, codigo=2,
                                                 detalle='VIRGINIA')
        ClaseTabaco.objects.create(empresa=self.empresa, variedad=virginia, codigo=50,
                                   detalle='X1L', coeficiente=Decimal('0.71'))
        romaneo = self._romaneo(con_fardo=False)

        r = self.client.get(reverse('agro_clase_typeahead', args=[romaneo.id]))

        self.assertContains(r, 'B1F')
        self.assertNotContains(r, 'X1L')

    # -- confirmación, anulación y reclasificación --------------------------

    def test_confirmar_redirige_al_detalle(self):
        romaneo = self._romaneo()

        r = self.client.post(reverse('agro_romaneo_confirmar', args=[romaneo.id]))

        self.assertEqual(r.status_code, 200)
        self.assertIn('HX-Redirect', r.headers)
        romaneo.refresh_from_db()
        self.assertEqual(romaneo.estado, RomaneoTabaco.CONFIRMADO)
        self.assertEqual(romaneo.numero, 1)

    def test_confirmar_vacio_avisa_en_pantalla(self):
        romaneo = self._romaneo(con_fardo=False)

        r = self.client.post(reverse('agro_romaneo_confirmar', args=[romaneo.id]))

        self.assertContains(r, 'sin fardos')
        romaneo.refresh_from_db()
        self.assertEqual(romaneo.estado, RomaneoTabaco.BORRADOR)

    def test_la_carga_de_un_confirmado_redirige_al_detalle(self):
        romaneo = svc.confirmar_romaneo(self._romaneo(), self.user)

        r = self.client.get(reverse('agro_romaneo_carga', args=[romaneo.id]))

        self.assertRedirects(r, reverse('agro_romaneo_detalle', args=[romaneo.id]))

    def test_anular_desde_el_modal(self):
        romaneo = svc.confirmar_romaneo(self._romaneo(), self.user)

        r = self.client.post(reverse('agro_romaneo_anular', args=[romaneo.id]),
                             {'motivo': 'Error de carga'})

        self.assertEqual(r.status_code, 200)
        romaneo.refresh_from_db()
        self.assertEqual(romaneo.estado, RomaneoTabaco.ANULADO)
        self.assertEqual(romaneo.fardos.count(), 1)     # los fardos no se borran

    def test_anular_sin_motivo_devuelve_el_formulario_con_error(self):
        romaneo = svc.confirmar_romaneo(self._romaneo(), self.user)

        r = self.client.post(reverse('agro_romaneo_anular', args=[romaneo.id]), {'motivo': ''})

        self.assertEqual(r.status_code, 200)
        romaneo.refresh_from_db()
        self.assertEqual(romaneo.estado, RomaneoTabaco.CONFIRMADO)

    def test_reclasificar_desde_el_modal(self):
        romaneo = svc.confirmar_romaneo(self._romaneo(), self.user)
        fardo = romaneo.fardos.first()

        r = self.client.post(reverse('agro_fardo_reclasificar', args=[fardo.id]),
                             {'clase_nueva': self.b2f.id, 'motivo': 'Revisión de calidad'})

        self.assertEqual(r.status_code, 200)
        fardo.refresh_from_db()
        self.assertEqual(fardo.clase, self.b2f)
        self.assertEqual(ReclasificacionFardo.objects.filter(fardo=fardo).count(), 1)

    def test_el_detalle_muestra_la_reclasificacion(self):
        romaneo = svc.confirmar_romaneo(self._romaneo(), self.user)
        fardo = romaneo.fardos.first()
        svc.reclasificar_fardo(fardo, clase_nueva=self.b2f, motivo='Revisión', usuario=self.user)

        r = self.client.get(reverse('agro_romaneo_detalle', args=[romaneo.id]))

        self.assertContains(r, 'Reclasificaciones')
        self.assertContains(r, 'Revisión')


    # -- menú lateral (hook de verticalidad) --------------------------------

    def test_el_menu_muestra_el_acopio_si_hace_tabaco(self):
        """El enlace se inyecta por `hook_menu`, no está escrito en `base.html`."""
        from verticalidades.agricola.core_agricola.models import EmpresaVertical
        EmpresaVertical.objects.create(empresa=self.empresa, hace_tabaco=True)

        r = self.client.get(reverse('agro_romaneo_listado'))

        self.assertContains(r, 'Acopio de Tabaco')
        self.assertContains(r, reverse('agro_romaneo_nuevo'))

    def test_el_menu_no_aparece_sin_el_submodulo(self):
        """Sin fila de EmpresaVertical la relación falla en silencio y el bloque no se muestra."""
        r = self.client.get(reverse('agro_romaneo_listado'))

        self.assertNotContains(r, 'Acopio de Tabaco')

    def test_el_menu_no_aparece_si_solo_hace_granos(self):
        from verticalidades.agricola.core_agricola.models import EmpresaVertical
        EmpresaVertical.objects.create(empresa=self.empresa, hace_tabaco=False, hace_granos=True)

        r = self.client.get(reverse('agro_romaneo_listado'))

        self.assertNotContains(r, 'Acopio de Tabaco')

    # -- aislamiento --------------------------------------------------------

    def test_no_se_accede_a_un_romaneo_de_otra_empresa(self):
        otra = Empresa.objects.create(nombre="OTRO ACOPIO", cuit="30999999998")
        otra_suc = Sucursal.objects.create(empresa=otra, nombre="CENTRAL OTRA")
        otra_camp = Campania.objects.create(empresa=otra, codigo='X', detalle='X',
                                            fecha_inicio=date(2024, 1, 1))
        otra_var = VariedadTabaco.objects.create(empresa=otra, codigo=1, detalle='BURLEY')
        otra_lista = ListaPrecioTabaco.objects.create(
            empresa=otra, variedad=otra_var, campania=otra_camp,
            vigencia_desde=date(2024, 1, 1), precio_ponderante=Decimal('100'), aprobada=True)
        ajeno = RomaneoTabaco.objects.create(
            empresa=otra, sucursal=otra_suc, fecha=date(2024, 3, 1), productor=self.productor,
            variedad=otra_var, campania=otra_camp, lista_precio=otra_lista,
            ponderante_aplicado=Decimal('100'))

        for nombre in ('agro_romaneo_detalle', 'agro_romaneo_carga', 'agro_romaneo_imprimir'):
            with self.subTest(url=nombre):
                self.assertEqual(
                    self.client.get(reverse(nombre, args=[ajeno.id])).status_code, 404)

    def test_el_listado_no_muestra_romaneos_ajenos(self):
        otra = Empresa.objects.create(nombre="OTRO ACOPIO", cuit="30999999998")
        ClienteProveedor.objects.create(razon_social="PRODUCTOR AJENO", tipo_entidad=2,
                                        empresa=otra)
        self._romaneo()

        r = self.client.get(reverse('agro_romaneo_listado'))

        self.assertContains(r, 'PRODUCTOR TEST')
        self.assertNotContains(r, 'PRODUCTOR AJENO')
