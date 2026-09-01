"""El cajero opera únicamente su Caja Mostrador (Plan 077 §G).

Definición del usuario: *"Para el cajero de caja mostrador no debe estar habilitado ni
recibos, ni órdenes de pago ni caja tesorería. El cajero todo lo que maneje será a través de
su CAJA MOSTRADOR."*

EL BLOQUEO SE PRUEBA EN LAS VISTAS, NO EN EL MENÚ. Esconder un link no es un permiso: la URL
sigue estando ahí para quien la escriba. Por eso cada prueba pega contra la URL directa.
"""
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from contable.models import Ejercicio
from empresas.models import Empresa, Sucursal
from tesoreria.models import Caja, CajaSesion
from usuarios.models import Perfil

# Todo lo que el cajero NO debe poder abrir.
VEDADAS = [
    'recibo_carga',
    'recibo_listado',
    'ordenpago_carga',
    'ordenpago_listado',
    'caja_diaria_index',
    'eoaf_index',
    'rendiciones_recepcion',
]


class BaseCajeroTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nombre="Empresa Prueba", cuit="30111111118")
        self.sucursal = Sucursal.objects.create(
            id=1, empresa=self.empresa, nombre="Casa Central", punto=1)
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa, inicio="2026-01-01", cierre="2026-12-31")
        self.caja = Caja.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, nombre="Mostrador", tipo='M')

    def usuario(self, nombre, *, cajero=False, admin=False):
        user = User.objects.create_user(username=nombre, password="x")
        perfil, _ = Perfil.objects.get_or_create(usuario=user)
        perfil.es_cajero_mostrador = cajero
        perfil.es_admin_sistema = admin
        perfil.save()
        perfil.empresas.add(self.empresa)
        return user

    def sesion_de(self, user):
        cliente = Client()
        cliente.force_login(user)
        sesion = cliente.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion['ejercicio_id'] = self.ejercicio.id
        sesion.save()
        return cliente


class ElCajeroNoEntraATesoreriaTestCase(BaseCajeroTestCase):
    def test_todas_las_pantallas_vedadas_lo_redirigen_a_su_caja(self):
        navegador = self.sesion_de(self.usuario("cajero1", cajero=True))
        for nombre in VEDADAS:
            with self.subTest(vista=nombre):
                respuesta = navegador.get(reverse(nombre))
                self.assertRedirects(
                    respuesta, reverse('caja_mostrador_index'),
                    fetch_redirect_response=False,
                    msg_prefix=f"{nombre} no bloqueó al cajero")

    def test_el_bloqueo_explica_por_dónde_tiene_que_operar(self):
        """Un 'no tenés permiso' a secas no le dice al cajero qué hacer en su lugar."""
        navegador = self.sesion_de(self.usuario("cajero1", cajero=True))
        respuesta = navegador.get(reverse('recibo_carga'), follow=False)
        mensajes = [str(m) for m in respuesta.wsgi_request._messages]
        self.assertTrue(any("Emitir Recibo" in m for m in mensajes), mensajes)


class LoQueElCajeroSiPuedeTestCase(BaseCajeroTestCase):
    def test_entra_a_su_caja_mostrador(self):
        navegador = self.sesion_de(self.usuario("cajero1", cajero=True))
        respuesta = navegador.get(reverse('caja_mostrador_index'))
        self.assertEqual(respuesta.status_code, 200)

    def test_emite_el_recibo_de_su_caja(self):
        """Es la misma vista que la vedada: lo que la distingue es el origen."""
        user = self.usuario("cajero1", cajero=True)
        CajaSesion.objects.create(caja=self.caja, usuario=user, estado='A')
        navegador = self.sesion_de(user)

        respuesta = navegador.get(reverse('recibo_carga_mostrador'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['origen'], 'MOSTRADOR')


class LaRestriccionEsOptativaTestCase(BaseCajeroTestCase):
    """Arranca en False: nadie pierde accesos al aplicar el cambio."""

    def test_un_usuario_comun_conserva_todo(self):
        navegador = self.sesion_de(self.usuario("tesorero1"))
        for nombre in VEDADAS:
            with self.subTest(vista=nombre):
                respuesta = navegador.get(reverse(nombre))
                self.assertNotEqual(
                    respuesta.status_code, 302,
                    f"{nombre} bloqueó a un usuario que no es cajero restringido")

    def test_el_perfil_nace_sin_la_restriccion(self):
        user = User.objects.create_user(username="nuevo", password="x")
        perfil, _ = Perfil.objects.get_or_create(usuario=user)
        self.assertFalse(perfil.es_cajero_mostrador)

    def test_el_admin_de_sistema_no_queda_atrapado(self):
        """Si se marca por error, el administrador sigue pudiendo entrar a arreglarlo."""
        navegador = self.sesion_de(
            self.usuario("admin1", cajero=True, admin=True))
        respuesta = navegador.get(reverse('recibo_carga'))
        self.assertEqual(respuesta.status_code, 200)


class ElMenuAcompanaTestCase(BaseCajeroTestCase):
    """Esconder el link no alcanza, pero mostrar lo que no se puede usar sería peor."""

    def test_el_cajero_no_ve_las_entradas_vedadas(self):
        navegador = self.sesion_de(self.usuario("cajero1", cajero=True))
        html = navegador.get(reverse('caja_mostrador_index')).content.decode()
        self.assertNotIn(reverse('recibo_carga'), html)
        self.assertNotIn(reverse('ordenpago_carga'), html)
        self.assertNotIn(reverse('caja_diaria_index'), html)

    def test_y_si_ve_su_caja_mostrador(self):
        navegador = self.sesion_de(self.usuario("cajero1", cajero=True))
        html = navegador.get(reverse('caja_mostrador_index')).content.decode()
        self.assertIn(reverse('caja_mostrador_index'), html)

    def test_el_tesorero_las_sigue_viendo(self):
        navegador = self.sesion_de(self.usuario("tesorero1"))
        html = navegador.get(reverse('caja_mostrador_index')).content.decode()
        self.assertIn(reverse('recibo_carga'), html)
        self.assertIn(reverse('ordenpago_carga'), html)
