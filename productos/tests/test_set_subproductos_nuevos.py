from django.test import TestCase
from django.core.management import call_command
from io import StringIO
from empresas.models import Empresa, Sucursal
from productos.models import Producto, Subproducto

class SetSubproductosNuevosCommandTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Empresa Armeria Test",
            cuit="30111111118"
        )
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa,
            nombre="Casa Central"
        )
        self.producto = Producto.objects.create(
            empresa=self.empresa,
            detalle="PISTOLA TEST",
            subprod=True
        )
        # Subproductos en distintos estados
        self.sub_nuevo = Subproducto.objects.create(
            empresa=self.empresa,
            producto=self.producto,
            sucursal=self.sucursal,
            serie="SERIE001",
            feccpra="2026-01-01",
            estado='NUEVO'
        )
        self.sub_usado_1 = Subproducto.objects.create(
            empresa=self.empresa,
            producto=self.producto,
            sucursal=self.sucursal,
            serie="SERIE002",
            feccpra="2026-01-01",
            estado='USADO'
        )
        self.sub_usado_2 = Subproducto.objects.create(
            empresa=self.empresa,
            producto=self.producto,
            sucursal=self.sucursal,
            serie="SERIE003",
            feccpra="2026-01-01",
            estado='USADO'
        )

    def test_dry_run_no_modifica(self):
        out = StringIO()
        call_command('set_subproductos_nuevos', '--dry-run', stdout=out)
        self.assertEqual(Subproducto.objects.filter(estado='USADO').count(), 2)

    def test_ejecucion_cambia_todos_a_nuevo(self):
        out = StringIO()
        call_command('set_subproductos_nuevos', stdout=out)
        self.assertEqual(Subproducto.objects.filter(estado='USADO').count(), 0)
        self.assertEqual(Subproducto.objects.filter(estado='NUEVO').count(), 3)
        self.assertIn("Se actualizaron 2 subproductos a estado 'NUEVO'", out.getvalue())
