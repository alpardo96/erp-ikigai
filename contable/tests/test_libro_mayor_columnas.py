from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from empresas.models import Empresa, Sucursal, Ejercicio
from contable.models import Cuenta, Asiento, AsientoLinea

User = get_user_model()

class LibroMayorMejorasTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.empresa = Empresa.objects.create(
            nombre="Empresa Test Mayor",
            cuit="30111111118"
        )
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa,
            nombre="Central"
        )
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa,
            ejercicio="2026",
            inicio=timezone.datetime(2026, 1, 1).date(),
            cierre=timezone.datetime(2026, 12, 31).date()
        )
        self.user = User.objects.create_user(
            username="testuser_mayor",
            email="mayor@test.com",
            password="password123"
        )
        self.client.force_login(self.user)

        session = self.client.session
        session['empresa_id'] = self.empresa.id
        session['ejercicio_id'] = self.ejercicio.id
        session.save()

        # Cuentas imputables
        self.cta_caja = Cuenta.objects.create(
            empresa=self.empresa,
            jerarquia="1.1.1.01",
            cuenta="Caja Moneda Nacional",
            tipo="A",
            imputable=1
        )
        self.cta_ventas = Cuenta.objects.create(
            empresa=self.empresa,
            jerarquia="4.1.1.01",
            cuenta="Ventas",
            tipo="R",
            imputable=1
        )

        # Asiento de prueba
        self.asiento = Asiento.objects.create(
            empresa=self.empresa,
            fecha=timezone.datetime(2026, 3, 15).date(),
            concepto="Venta al contado",
            condic=1, # Real
            sucursal=self.sucursal,
            ejercicio=self.ejercicio,
            monto=1000
        )
        AsientoLinea.objects.create(
            asiento=self.asiento,
            cuenta=self.cta_caja,
            debe=1000,
            haber=0,
            orden=1,
            leyenda="Cobro efectivo"
        )
        AsientoLinea.objects.create(
            asiento=self.asiento,
            cuenta=self.cta_ventas,
            debe=0,
            haber=1000,
            orden=2,
            leyenda="Venta contado"
        )

    def test_mayor_cuenta_modal_contexto(self):
        """Verifica que el modal se renderice con los filtros y condic predeterminados 1, 2 y 5."""
        url = reverse('mayor_cuenta_modal', kwargs={'cuenta_id': self.cta_caja.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('cuenta', response.context)
        self.assertIn('condics_seleccionados', response.context)
        self.assertEqual(response.context['condics_seleccionados'], ['1', '2', '5'])
        self.assertIn('catalogo_columnas', response.context)

    def test_libro_mayor_rows_fallback_cuentas(self):
        """Verifica que si no se envían cuentas en la consulta, fallbackeé a la primera y última sin dar pantalla en blanco."""
        url = reverse('libro_mayor_rows')
        response = self.client.get(url, {'condic': ['1']})
        self.assertEqual(response.status_code, 200)
        self.assertIn('cuentas_data', response.context)
        self.assertTrue(len(response.context['cuentas_data']) > 0)

    def test_exportar_mayor_csv(self):
        """Verifica que la exportación a CSV responda con HTTP 200, formato text/csv y BOM UTF-8."""
        url = reverse('exportar_mayor_csv')
        response = self.client.get(url, {
            'cuenta_desde': self.cta_caja.id,
            'cuenta_hasta': self.cta_ventas.id,
            'condic': ['1'],
            'columnas': ['asiento_id', 'fecha', 'concepto', 'debe', 'haber']
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8-sig')
        self.assertIn('attachment; filename="libro_mayor_', response['Content-Disposition'])

        contenido = response.content.decode('utf-8-sig')
        lines = contenido.strip().split('\r\n')
        self.assertTrue(len(lines) >= 2)
        self.assertIn('ID Asiento;Fecha;Concepto;Debe;Haber', lines[0])
