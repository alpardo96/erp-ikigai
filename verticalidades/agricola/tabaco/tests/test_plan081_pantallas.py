"""Plan 081 — humo de las pantallas de maestros.

Compilar una plantilla NO alcanza: `{% url %}`, los filtros y los accesos a atributos fallan
recién al RENDERIZAR. Estos tests entran a cada pestaña y a cada modal con el cliente de prueba,
que es la única forma de que un nombre de ruta mal escrito se caiga acá y no en producción.

También cubren el aislamiento por empresa y el interruptor `hace_tabaco`, que son las dos reglas
que no se pueden romper nunca.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contable.models import Cuenta
from empresas.models import Empresa, Sucursal
from verticalidades.agricola.core_agricola.models import Campania, EmpresaVertical
from verticalidades.agricola.tabaco.models import (ClaseTabaco, ListaPrecioTabaco,
                                                   TipoRetencionTabaco, VariedadTabaco)

User = get_user_model()

TABS = ['agro_campanias', 'agro_variedades', 'agro_clases',
        'agro_listas_precio', 'agro_retenciones', 'agro_config_tabaco']


class PantallasMaestrosTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='agro_admin', password='pw', is_staff=True)
        self.empresa = Empresa.objects.create(nombre="ACOPIO TEST", cuit="30111111112",
                                              tipo_actividad='AGRICOLA')
        Sucursal.objects.create(empresa=self.empresa, nombre="CENTRAL")
        EmpresaVertical.objects.create(empresa=self.empresa, hace_tabaco=True)

        self.cuenta = Cuenta.objects.create(
            empresa=self.empresa, jerarquia='2.1.1.01', cuenta='RETENCIONES A DEPOSITAR',
            imputable=1, tipo='P')

        self.campania = Campania.objects.create(
            empresa=self.empresa, codigo='2026/2027', detalle='CAMPAÑA TEST',
            fecha_inicio=date(2026, 6, 1))
        self.variedad = VariedadTabaco.objects.create(
            empresa=self.empresa, codigo=1, detalle='BURLEY')
        self.clase = ClaseTabaco.objects.create(
            empresa=self.empresa, variedad=self.variedad, codigo=1,
            detalle='B1F', coeficiente=Decimal('1'))
        self.lista = ListaPrecioTabaco.objects.create(
            empresa=self.empresa, variedad=self.variedad, campania=self.campania,
            vigencia_desde=date(2026, 6, 1), precio_ponderante=Decimal('2500.00'))
        self.retencion = TipoRetencionTabaco.objects.create(
            empresa=self.empresa, codigo='EEAOC', detalle='RETENCION EEAOC',
            tipo_base=TipoRetencionTabaco.NETO, alicuota=Decimal('0.5'),
            cuenta_contable=self.cuenta, vigencia_desde=date(2026, 1, 1))

        self.client.force_login(self.user)
        sesion = self.client.session
        sesion['empresa_id'] = self.empresa.id
        sesion.save()

    # -- pestañas -----------------------------------------------------------

    def test_todas_las_pestanias_renderizan(self):
        url = reverse('configuracion_index')
        for tab in TABS:
            with self.subTest(tab=tab):
                r = self.client.get(f"{url}?tab={tab}", headers={'hx-request': 'true'})
                self.assertEqual(r.status_code, 200)

    def test_el_hub_muestra_el_bloque_cuando_hace_tabaco(self):
        r = self.client.get(reverse('configuracion_index'))
        self.assertContains(r, 'Acopio de Tabaco')

    def test_el_hub_oculta_el_bloque_si_no_hace_tabaco(self):
        EmpresaVertical.objects.filter(empresa=self.empresa).update(hace_tabaco=False)

        r = self.client.get(reverse('configuracion_index'))
        self.assertNotContains(r, 'tab=agro_clases')

    # -- modales ------------------------------------------------------------

    def test_modales_de_alta_renderizan(self):
        for nombre in ['agro_campania_add', 'agro_variedad_add', 'agro_clase_add',
                       'agro_lista_precio_add', 'agro_retencion_add']:
            with self.subTest(url=nombre):
                r = self.client.get(reverse(nombre))
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, 'Guardar')

    def test_modales_de_edicion_renderizan(self):
        casos = [('agro_campania_edit', self.campania.id),
                 ('agro_variedad_edit', self.variedad.id),
                 ('agro_clase_edit', self.clase.id),
                 ('agro_lista_precio_edit', self.lista.id),
                 ('agro_retencion_edit', self.retencion.id)]
        for nombre, pk in casos:
            with self.subTest(url=nombre):
                r = self.client.get(reverse(nombre, args=[pk]))
                self.assertEqual(r.status_code, 200)

    # -- buscadores ---------------------------------------------------------

    def test_buscadores_devuelven_filas(self):
        casos = [('agro_campania_buscar', '2026/2027'),
                 ('agro_variedad_buscar', 'BURLEY'),
                 ('agro_clase_buscar', 'B1F'),
                 ('agro_lista_precio_buscar', 'BURLEY'),
                 ('agro_retencion_buscar', 'EEAOC')]
        for nombre, esperado in casos:
            with self.subTest(url=nombre):
                r = self.client.get(reverse(nombre))
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, esperado)

    def test_el_buscador_de_clases_filtra_por_variedad(self):
        otra = VariedadTabaco.objects.create(empresa=self.empresa, codigo=2, detalle='VIRGINIA')
        ClaseTabaco.objects.create(empresa=self.empresa, variedad=otra, codigo=56,
                                   detalle='X1L', coeficiente=Decimal('0.71'))

        r = self.client.get(reverse('agro_clase_buscar'), {'variedad': otra.id})

        self.assertContains(r, 'X1L')
        self.assertNotContains(r, 'B1F')

    # -- aislamiento multiempresa ------------------------------------------

    def test_no_se_ven_maestros_de_otra_empresa(self):
        otra = Empresa.objects.create(nombre="OTRO ACOPIO", cuit="30999999998")
        otra_var = VariedadTabaco.objects.create(empresa=otra, codigo=9, detalle='AJENA')

        r = self.client.get(reverse('agro_variedad_buscar'))

        self.assertContains(r, 'BURLEY')
        self.assertNotContains(r, 'AJENA')
        # Y tampoco se puede llegar por URL directa al registro de la otra empresa.
        self.assertEqual(self.client.get(reverse('agro_variedad_edit', args=[otra_var.id])).status_code, 404)

    # -- alta y edición reales ---------------------------------------------

    def test_alta_de_campania_sella_empresa_y_auditoria(self):
        r = self.client.post(reverse('agro_campania_add'), {
            'codigo': '2027/2028', 'detalle': 'nueva campaña',
            'fecha_inicio': '2027-06-01', 'estado': Campania.ABIERTA, 'activa': 'on',
        })

        self.assertEqual(r.status_code, 200)
        nueva = Campania.objects.get(codigo='2027/2028')
        self.assertEqual(nueva.empresa_id, self.empresa.id)
        self.assertEqual(nueva.creado_por, self.user)
        self.assertEqual(nueva.detalle, 'NUEVA CAMPAÑA')     # normalizado a mayúsculas

    def test_alta_rechaza_codigo_de_campania_repetido(self):
        r = self.client.post(reverse('agro_campania_add'), {
            'codigo': '2026/2027', 'detalle': 'DUPLICADA',
            'fecha_inicio': '2026-06-01', 'estado': Campania.ABIERTA,
        })

        self.assertContains(r, 'Ya existe una campaña con ese código')
        self.assertEqual(Campania.objects.filter(empresa=self.empresa).count(), 1)

    def test_aprobar_una_lista_deja_rastro(self):
        r = self.client.post(reverse('agro_lista_precio_edit', args=[self.lista.id]), {
            'variedad': self.variedad.id, 'campania': self.campania.id,
            'vigencia_desde': '2026-06-01', 'moneda': 'PES',
            'precio_ponderante': '2.800,00', 'aprobada': 'on',
        })

        self.assertEqual(r.status_code, 200)
        self.lista.refresh_from_db()
        self.assertTrue(self.lista.aprobada)
        self.assertEqual(self.lista.aprobada_por, self.user)
        self.assertIsNotNone(self.lista.aprobada_el)
        # El importe llegó en formato es-AR y se guardó como Decimal.
        self.assertEqual(self.lista.precio_ponderante, Decimal('2800.00'))

    def test_no_se_puede_borrar_una_lista_aprobada(self):
        self.lista.aprobada = True
        self.lista.save(update_fields=['aprobada'])

        r = self.client.post(reverse('agro_lista_precio_del', args=[self.lista.id]))

        self.assertContains(r, 'No se puede eliminar')
        self.assertTrue(ListaPrecioTabaco.objects.filter(pk=self.lista.pk).exists())

    def test_ganancias_no_puede_practicarse_al_liquidar(self):
        """Su base es el acumulado mensual de lo PAGADO: en la liquidación daría mal."""
        r = self.client.post(reverse('agro_retencion_add'), {
            'codigo': 'GCIAS', 'detalle': 'RETENCION GANANCIAS',
            'tipo_base': TipoRetencionTabaco.ACUM_MENSUAL,
            'momento': TipoRetencionTabaco.LIQUIDACION,
            'alicuota': '2,0000', 'minimo_no_imponible': '224.000,00',
            'cuenta_contable': self.cuenta.id, 'vigencia_desde': '2026-01-01',
        })

        self.assertContains(r, 'sólo puede practicarse al pagar')
        self.assertFalse(TipoRetencionTabaco.objects.filter(codigo='GCIAS').exists())

    def test_config_manual_exige_cai(self):
        r = self.client.post(reverse('agro_config_tabaco_guardar'), {
            'punto_venta': 7, 'modo_autorizacion': 'MANUAL',
            'cai': '', 'tolerancia_pesaje': '0,00',
        })

        self.assertContains(r, 'hay que cargar el CAI')
