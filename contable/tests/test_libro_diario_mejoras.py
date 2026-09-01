from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from empresas.models import Empresa, Ejercicio
from contable.models import Asiento, AsientoLinea, Cuenta
from usuarios.models import Perfil

User = get_user_model()


class LibroDiarioMejorasTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Empresa Test Contable",
            cuit="30111111118"
        )

        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa,
            ejercicio="Ejercicio 2026",
            inicio=timezone.datetime(2026, 1, 1).date(),
            cierre=timezone.datetime(2026, 12, 31).date()
        )

        self.user = User.objects.create_user(
            username="testuser_cble",
            password="password123"
        )

        self.perfil = Perfil.objects.create(usuario=self.user)
        self.perfil.empresas.add(self.empresa)

        # Cuentas imputables de prueba
        self.cta_caja = Cuenta.objects.create(
            empresa=self.empresa,
            jerarquia="1.1.1.01",
            cuenta="CAJA MONEDA NACIONAL",
            imputable=1,
            tipo="A"
        )
        self.cta_ventas = Cuenta.objects.create(
            empresa=self.empresa,
            jerarquia="4.1.1.01",
            cuenta="VENTAS DE MERCADERIAS",
            imputable=1,
            tipo="R"
        )

        # Asiento 1 (Real - condic=1)
        self.asiento1 = Asiento.objects.create(
            empresa=self.empresa,
            ejercicio=self.ejercicio,
            fecha=timezone.localdate(),
            concepto="VENTA DE MERCADERIA EN EFECTIVO",
            condic=1,
            monto=Decimal("1210.00"),
            modulo=1,
            creado_por=self.user
        )
        AsientoLinea.objects.create(
            asiento=self.asiento1,
            orden=1,
            cuenta=self.cta_caja,
            debe=Decimal("1210.00"),
            haber=Decimal("0.00")
        )
        AsientoLinea.objects.create(
            asiento=self.asiento1,
            orden=2,
            cuenta=self.cta_ventas,
            debe=Decimal("0.00"),
            haber=Decimal("1210.00")
        )

        # Asiento 2 (Proyectado - condic=2)
        self.asiento2 = Asiento.objects.create(
            empresa=self.empresa,
            ejercicio=self.ejercicio,
            fecha=timezone.localdate(),
            concepto="PROYECCION VENTA MES",
            condic=2,
            monto=Decimal("5000.00"),
            modulo=1,
            creado_por=self.user
        )

        self.client = Client()
        self.client.login(username="testuser_cble", password="password123")

        session = self.client.session
        session['empresa_id'] = self.empresa.pk
        session['ejercicio_id'] = self.ejercicio.pk
        session.save()

    def test_libro_diario_carga_inicial_diferida(self):
        """Verifica que la carga inicial del diario no consulte filas (0 registros, ejecutado=False)."""
        url = reverse('libro_diario_rows')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Seleccione los parámetros de consulta y presione "Filtrar"')
        self.assertNotContains(response, "VENTA DE MERCADERIA EN EFECTIVO")

    def test_libro_diario_filtrado_asiento_id(self):
        """Verifica la filtración por rango de asiento_id (cble_asiento_enc)."""
        url = reverse('libro_diario_rows')
        response = self.client.get(url, {
            'filtering': '1',
            'asiento_desde': str(self.asiento1.asiento_id),
            'asiento_hasta': str(self.asiento1.asiento_id),
            'condic': ['1', '2']
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "VENTA DE MERCADERIA EN EFECTIVO")
        self.assertNotContains(response, "PROYECCION VENTA MES")

    def test_libro_diario_columna_asiento_id(self):
        """Verifica que se muestre el ID de Asiento (asiento_id) en lugar de Nº de Diario."""
        url = reverse('libro_diario_rows')
        response = self.client.get(url, {'filtering': '1', 'condic': ['1', '2']})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(self.asiento1.asiento_id))
        self.assertContains(response, str(self.asiento2.asiento_id))

    def test_despliegue_movimientos_asiento(self):
        """Verifica que el endpoint de detalle devuelva las líneas de cble_asiento_mov."""
        url = reverse('detalle_asiento', kwargs={'id': self.asiento1.asiento_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CAJA MONEDA NACIONAL")
        self.assertContains(response, "VENTAS DE MERCADERIAS")
        self.assertContains(response, "1210")

    def test_modal_nuevo_asiento_condicion_y_typeahead(self):
        """Verifica que el modal de nuevo asiento contenga las opciones 1 - Real y 2 - Presupuestado.

        Son los únicos condic cargables a mano: el 3 y el 4 llegan por procesos específicos y los
        estructurales 5/6/7 los genera el sistema (ver la tabla de `condic` en `.cursorrules`).
        """
        url = reverse('asiento_add')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 - Real")
        self.assertContains(response, "2 - Presupuestado")
        self.assertContains(response, "/contable/htmx/typeahead/cuentas/")

    def test_fechas_predeterminadas_ejercicio(self):
        """Verifica que la vista devuelva fecha_inicio (inicio ejercicio) y fecha_cierre (min entre date() y cierre_ejercicio)."""
        url = reverse('contable_libro_diario')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('fecha_inicio', response.context)
        self.assertIn('fecha_cierre', response.context)
        self.assertEqual(response.context['fecha_inicio'], '2026-01-01')

    def test_libro_diario_filtro_estado(self):
        """Verifica que el filtro de estado (1=Sólo Activos, 2=Sólo Anulados, 0=Todos) funcione correctamente."""
        # Anular asiento 2
        self.asiento2.anulado = True
        self.asiento2.save()

        url = reverse('libro_diario_rows')

        # 1. Sólo Activos (estado=1)
        res1 = self.client.get(url, {'filtering': '1', 'estado': '1', 'condic': ['1', '2']})
        self.assertContains(res1, "VENTA DE MERCADERIA EN EFECTIVO")
        self.assertNotContains(res1, "PROYECCION VENTA MES")

        # 2. Sólo Anulados (estado=2)
        res2 = self.client.get(url, {'filtering': '1', 'estado': '2', 'condic': ['1', '2']})
        self.assertNotContains(res2, "VENTA DE MERCADERIA EN EFECTIVO")
        self.assertContains(res2, "PROYECCION VENTA MES")

        # 3. Todos (estado=0)
        res0 = self.client.get(url, {'filtering': '1', 'estado': '0', 'condic': ['1', '2']})
        self.assertContains(res0, "VENTA DE MERCADERIA EN EFECTIVO")
        self.assertContains(res0, "PROYECCION VENTA MES")

