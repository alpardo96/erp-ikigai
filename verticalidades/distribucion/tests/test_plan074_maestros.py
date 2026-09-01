"""Tests de los maestros de Distribución (Plan 074, fase 1a)."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from verticalidades.distribucion.forms import PersonalForm, VehiculoForm, ZonaRepartoForm
from verticalidades.distribucion.models import (CarteraVendedor, DiaVisita, DomicilioEntrega,
                                 MotivoDevolucion, Personal, ZonaReparto)
from verticalidades.distribucion.services.catalogos import MOTIVOS_INICIALES, sembrar_motivos
from empresas.models import Empresa, Sucursal
from facturacion.forms import ExtensionDistribuidoraForm
from facturacion.models import ClienteProveedor
from verticalidades.distribucion.models import ExtensionDistribuidora
from productos.models import Producto
from usuarios.models import Perfil


class BaseDistribucionTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Distribuidora Prueba", cuit="30111111118",
            tipo_actividad="DISTRIBUIDORA")
        self.otra_empresa = Empresa.objects.create(
            nombre="Otra Empresa", cuit="30222222229", tipo_actividad="DISTRIBUIDORA")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, nombre="Depósito Central", punto=1)
        self.zona = ZonaReparto.objects.create(
            empresa=self.empresa, nombre="San Cayetano", orden=1)


class PersonalTestCase(BaseDistribucionTestCase):
    """El vendedor/repartidor es una entidad de negocio, no un usuario del sistema."""

    def test_personal_sin_usuario_es_valido(self):
        """El repartidor trabaja con la hoja de ruta en papel: no necesita credenciales."""
        persona = Personal.objects.create(
            empresa=self.empresa, nombre="Maximiliano", es_repartidor=True)
        self.assertIsNone(persona.usuario)
        self.assertEqual(persona.roles_display, "Repartidor")

    def test_codigo_se_autoasigna_correlativo_por_empresa(self):
        p1 = Personal.objects.create(empresa=self.empresa, nombre="Juan", es_vendedor=True)
        p2 = Personal.objects.create(empresa=self.empresa, nombre="Romina", es_repartidor=True)
        self.assertEqual(p1.codigo, 1)
        self.assertEqual(p2.codigo, 2)
        # La serie es por empresa: otra empresa arranca de nuevo en 1.
        p3 = Personal.objects.create(empresa=self.otra_empresa, nombre="Pedro", es_vendedor=True)
        self.assertEqual(p3.codigo, 1)

    def test_codigo_es_unico_por_empresa(self):
        Personal.objects.create(empresa=self.empresa, codigo=5, nombre="Juan", es_vendedor=True)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Personal.objects.create(empresa=self.empresa, codigo=5, nombre="Otro",
                                        es_vendedor=True)

    def test_roles_son_acumulables(self):
        """En una distribuidora chica la misma persona vende, reparte y cobra."""
        persona = Personal.objects.create(
            empresa=self.empresa, nombre="Juan",
            es_vendedor=True, es_repartidor=True, es_cobrador=True)
        self.assertEqual(persona.roles_display, "Vendedor / Repartidor / Cobrador")

    def test_nombre_se_normaliza_a_mayusculas(self):
        persona = Personal.objects.create(
            empresa=self.empresa, nombre="  juan perez  ", es_vendedor=True)
        self.assertEqual(persona.nombre, "JUAN PEREZ")


class PersonalFormTestCase(BaseDistribucionTestCase):
    def _datos(self, **extra):
        datos = {
            'nombre': 'Juan Perez', 'es_vendedor': True,
            'comision_porcentaje': '', 'documento': '', 'telefono': '',
            'codigo': '', 'zona': '', 'usuario': '', 'fecha_alta': '',
            'fecha_baja': '', 'codigo_anterior': '', 'activo': True,
        }
        datos.update(extra)
        return datos

    def test_exige_al_menos_un_rol(self):
        form = PersonalForm(self.empresa.id, data=self._datos(es_vendedor=False))
        self.assertFalse(form.is_valid())
        self.assertIn("al menos un rol", str(form.errors))

    def test_comision_acepta_formato_es_ar(self):
        """El input `.fInputAR` manda '12,50', no '12.50'."""
        form = PersonalForm(self.empresa.id, data=self._datos(comision_porcentaje='12,50'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['comision_porcentaje'], Decimal('12.50'))

    def test_comision_vacia_es_cero_y_no_nulo(self):
        form = PersonalForm(self.empresa.id, data=self._datos(comision_porcentaje=''))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['comision_porcentaje'], 0)

    def test_las_fechas_se_guardan(self):
        form = PersonalForm(self.empresa.id, data=self._datos(
            fecha_alta='2026-08-28', fecha_baja='2026-09-30'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(str(form.cleaned_data['fecha_alta']), '2026-08-28')
        self.assertEqual(str(form.cleaned_data['fecha_baja']), '2026-09-30')

    def test_las_fechas_guardadas_se_muestran_al_editar(self):
        """Regresión: con `LANGUAGE_CODE = 'es-ar'`, un `DateInput` común renderiza
        `value="28/08/2026"`, y un input HTML5 de tipo date descarta ese formato en
        silencio: el campo aparecía vacío y al grabar se borraba la fecha."""
        import datetime
        import re

        persona = Personal.objects.create(
            empresa=self.empresa, nombre="Con Fechas", es_vendedor=True,
            fecha_alta=datetime.date(2026, 8, 28), fecha_baja=datetime.date(2026, 9, 30))
        form = PersonalForm(self.empresa.id, instance=persona)

        for campo, esperado in (('fecha_alta', '2026-08-28'), ('fecha_baja', '2026-09-30')):
            html = str(form[campo])
            valor = re.search(r'value="([^"]*)"', html).group(1)
            self.assertEqual(valor, esperado,
                             f"{campo} debe renderizarse en ISO para el input HTML5")

    def test_baja_anterior_al_alta_es_invalida(self):
        form = PersonalForm(self.empresa.id, data=self._datos(
            fecha_alta='2026-05-10', fecha_baja='2026-05-01'))
        self.assertFalse(form.is_valid())
        self.assertIn('fecha_baja', form.errors)

    def test_usuarios_ofrecidos_se_acotan_a_la_empresa(self):
        """Multi-tenant: no se puede vincular un usuario de otra empresa."""
        propio = User.objects.create_user(username="propio", password="x")
        Perfil.objects.create(usuario=propio).empresas.add(self.empresa)
        ajeno = User.objects.create_user(username="ajeno", password="x")
        Perfil.objects.create(usuario=ajeno).empresas.add(self.otra_empresa)

        form = PersonalForm(self.empresa.id)
        ofrecidos = list(form.fields['usuario'].queryset)
        self.assertIn(propio, ofrecidos)
        self.assertNotIn(ajeno, ofrecidos)

    def test_usuario_ya_asignado_no_se_vuelve_a_ofrecer(self):
        usuario = User.objects.create_user(username="vendedor1", password="x")
        Perfil.objects.create(usuario=usuario).empresas.add(self.empresa)
        Personal.objects.create(empresa=self.empresa, nombre="Juan",
                                es_vendedor=True, usuario=usuario)

        form = PersonalForm(self.empresa.id)
        self.assertNotIn(usuario, list(form.fields['usuario'].queryset))


class ZonaYVehiculoTestCase(BaseDistribucionTestCase):
    def test_zona_no_se_repite_en_la_misma_empresa(self):
        form = ZonaRepartoForm(self.empresa.id,
                               data={'nombre': 'san cayetano', 'orden': 2, 'activa': True})
        self.assertFalse(form.is_valid())
        self.assertIn('nombre', form.errors)

    def test_misma_zona_en_otra_empresa_es_valida(self):
        form = ZonaRepartoForm(self.otra_empresa.id,
                               data={'nombre': 'San Cayetano', 'orden': 1, 'activa': True})
        self.assertTrue(form.is_valid(), form.errors)

    def test_capacidad_acepta_formato_es_ar(self):
        form = VehiculoForm(self.empresa.id, data={
            'patente': 'AB123CD', 'descripcion': 'Furgón',
            'sucursal': self.sucursal.id, 'capacidad_kg': '1.500,50',
            'refrigerado': True, 'activo': True})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['capacidad_kg'], Decimal('1500.50'))

    def test_sucursales_ofrecidas_se_acotan_a_la_empresa(self):
        ajena = Sucursal.objects.create(empresa=self.otra_empresa, nombre="Ajena", punto=1)
        form = VehiculoForm(self.empresa.id)
        ofrecidas = list(form.fields['sucursal'].queryset)
        self.assertIn(self.sucursal, ofrecidas)
        self.assertNotIn(ajena, ofrecidas)


class MotivosDevolucionTestCase(BaseDistribucionTestCase):
    def test_siembra_crea_el_catalogo_completo(self):
        creados = sembrar_motivos(self.empresa.id)
        self.assertEqual(creados, len(MOTIVOS_INICIALES))
        self.assertEqual(
            MotivoDevolucion.objects.filter(empresa=self.empresa).count(),
            len(MOTIVOS_INICIALES))

    def test_siembra_es_idempotente_y_no_pisa_lo_editado(self):
        sembrar_motivos(self.empresa.id)
        motivo = MotivoDevolucion.objects.get(empresa=self.empresa, codigo='NEGOCIO_CERRADO')
        motivo.descripcion = "Cerrado (texto propio del usuario)"
        motivo.save()

        self.assertEqual(sembrar_motivos(self.empresa.id), 0)
        motivo.refresh_from_db()
        self.assertEqual(motivo.descripcion, "Cerrado (texto propio del usuario)")

    def test_motivos_de_calidad_no_devuelven_al_stock(self):
        """Un envase roto o una rotura de cadena de frío no vuelven al stock vendible."""
        sembrar_motivos(self.empresa.id)
        no_reingresan = set(
            MotivoDevolucion.objects
            .filter(empresa=self.empresa, sugiere_apto_reventa=False)
            .values_list('codigo', flat=True))
        self.assertEqual(
            no_reingresan,
            {'PRODUCTO_DANADO', 'PROXIMO_A_VENCER', 'CADENA_DE_FRIO'})

    def test_negocio_cerrado_si_devuelve_al_stock(self):
        sembrar_motivos(self.empresa.id)
        motivo = MotivoDevolucion.objects.get(empresa=self.empresa, codigo='NEGOCIO_CERRADO')
        self.assertTrue(motivo.sugiere_apto_reventa)


class CarteraYAgendaTestCase(BaseDistribucionTestCase):
    def setUp(self):
        super().setUp()
        self.vendedor = Personal.objects.create(
            empresa=self.empresa, nombre="Juan", es_vendedor=True)
        self.otro_vendedor = Personal.objects.create(
            empresa=self.empresa, nombre="Romina", es_vendedor=True)
        self.cliente = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="Almacén Don José", tipo_entidad=1)

    def test_un_cliente_tiene_un_solo_vendedor(self):
        """Es el responsable directo de su saldo: la asignación es única."""
        CarteraVendedor.objects.create(
            empresa=self.empresa, vendedor=self.vendedor, cliente=self.cliente)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CarteraVendedor.objects.create(
                    empresa=self.empresa, vendedor=self.otro_vendedor, cliente=self.cliente)

    def test_dia_de_visita_no_se_duplica_en_el_mismo_punto(self):
        domicilio = DomicilioEntrega.objects.create(
            empresa=self.empresa, cliente=self.cliente, nombre="Casa Central",
            domicilio="Belgrano 100")
        DiaVisita.objects.create(empresa=self.empresa, domicilio=domicilio, dia_semana=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DiaVisita.objects.create(
                    empresa=self.empresa, domicilio=domicilio, dia_semana=1)

    def test_dos_sucursales_pueden_visitarse_el_mismo_dia(self):
        """La agenda es del punto de entrega, no del cliente."""
        for nombre in ("Sucursal Centro", "Sucursal Norte"):
            d = DomicilioEntrega.objects.create(
                empresa=self.empresa, cliente=self.cliente, nombre=nombre,
                domicilio=f"Calle {nombre}")
            DiaVisita.objects.create(empresa=self.empresa, domicilio=d, dia_semana=1)
        self.assertEqual(DiaVisita.objects.filter(dia_semana=1).count(), 2)


class ExtensionDistribuidoraTestCase(BaseDistribucionTestCase):
    def test_precio_se_calcula_sobre_precio_total_por_coeficiente(self):
        """El precio base es el de lista CON IVA; `cto_rep` no interviene en la venta."""
        producto = Producto.objects.create(
            empresa=self.empresa, detalle="Yogur x 900 vainilla",
            precio_total=Decimal('1690.00'), cto_rep=Decimal('900.00'))
        cliente = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="Almacén Don José", tipo_entidad=1)
        extension = ExtensionDistribuidora.objects.create(
            cliente=cliente, coeficiente_mayorista=Decimal('0.9000'))

        precio = producto.precio_total * extension.coeficiente_mayorista
        self.assertEqual(precio, Decimal('1521.000000'))

    def test_la_extension_es_opcional(self):
        """Un cliente sin extensión cargada no debe romper nada."""
        cliente = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="Sin Extensión", tipo_entidad=1)
        self.assertFalse(hasattr(cliente, 'distribuidora'))

    def test_form_acepta_coeficiente_en_formato_es_ar(self):
        form = ExtensionDistribuidoraForm(
            data={'clasificacion': 'A', 'coeficiente_mayorista': '0,9500',
                  'bloqueado_credito': False},
            empresa_id=self.empresa.id)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['coeficiente_mayorista'], Decimal('0.9500'))

    def test_coeficiente_vacio_queda_en_uno(self):
        """Sin coeficiente cargado, el cliente paga el precio de lista tal cual."""
        form = ExtensionDistribuidoraForm(
            data={'clasificacion': '', 'coeficiente_mayorista': '',
                  'bloqueado_credito': False},
            empresa_id=self.empresa.id)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['coeficiente_mayorista'], 1)

    def test_la_zona_no_esta_en_el_cliente(self):
        """La zona vive en el domicilio de entrega: un cliente con sucursales
        entrega en varias, y colgarla del cliente obligaría a compartir una sola."""
        form = ExtensionDistribuidoraForm(empresa_id=self.empresa.id)
        self.assertNotIn('zona', form.fields)


class ProductoDistribucionTestCase(BaseDistribucionTestCase):
    def test_campos_de_distribucion_tienen_default_neutro(self):
        """Una empresa que no es distribuidora no se ve afectada por los campos nuevos."""
        producto = Producto.objects.create(empresa=self.empresa, detalle="Leche sachet")
        self.assertEqual(producto.peso_unitario_kg, 0)
        self.assertEqual(producto.unidad_venta, 'UNIDAD')
        self.assertEqual(producto.unidades_por_bulto, 0)
        self.assertIsNone(producto.codigo_anterior)

    def test_codigo_anterior_se_normaliza(self):
        producto = Producto.objects.create(
            empresa=self.empresa, detalle="Leche", codigo_anterior=" 1001 ")
        self.assertEqual(producto.codigo_anterior, "1001")
