from django.test import TestCase, RequestFactory
from empresas.models import Empresa
from productos.models import Familia, Subfamilia, Rubro, Producto
from productos.forms import SubfamiliaForm, ProductoForm
from productos.views_htmx import filtrar_familias, filtrar_subfamilias

class CatalogosFamiliasTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.empresa = Empresa.objects.create(
            nombre="Empresa Test",
            cuit="30111111118"
        )
        self.rubro_armas = Rubro.objects.create(
            empresa=self.empresa,
            detalle="ARMAS"
        )
        self.rubro_muni = Rubro.objects.create(
            empresa=self.empresa,
            detalle="MUNICIONES"
        )
        self.familia_pistolas = Familia.objects.create(
            empresa=self.empresa,
            rubro=self.rubro_armas,
            detalle="PISTOLAS"
        )
        self.familia_balas = Familia.objects.create(
            empresa=self.empresa,
            rubro=self.rubro_muni,
            detalle="BALAS"
        )
        self.subfam_9mm = Subfamilia.objects.create(
            empresa=self.empresa,
            familia=self.familia_pistolas,
            detalle="9MM"
        )
        self.subfam_40 = Subfamilia.objects.create(
            empresa=self.empresa,
            familia=self.familia_pistolas,
            detalle=".40 S&W"
        )
        self.subfam_caja50 = Subfamilia.objects.create(
            empresa=self.empresa,
            familia=self.familia_balas,
            detalle="CAJA X 50"
        )

    def test_familia_str_representation(self):
        self.assertEqual(str(self.familia_pistolas), "PISTOLAS")

    def test_subfamilia_str_representation(self):
        self.assertEqual(str(self.subfam_9mm), "9MM")

    def test_subfamilia_form_familia_choices(self):
        form = SubfamiliaForm(empresa=self.empresa)
        choices = list(form.fields['familia'].choices)
        self.assertTrue(any("PISTOLAS" in str(label) for val, label in choices if val))

    def test_producto_form_edicion_filtra_subfamilias_por_familia(self):
        # Producto con familia PISTOLAS
        prod = Producto.objects.create(
            empresa=self.empresa,
            detalle="BERETTA 92FS",
            rubro=self.rubro_armas,
            familia=self.familia_pistolas,
            subfamilia=self.subfam_9mm
        )
        form = ProductoForm(instance=prod, empresa=self.empresa)
        subfam_choices = [str(label) for val, label in form.fields['subfamilia'].choices if val]
        
        # Deben estar las subfamilias de PISTOLAS
        self.assertIn("9MM", subfam_choices)
        self.assertIn(".40 S&W", subfam_choices)
        # NO debe estar la subfamilia de BALAS
        self.assertNotIn("CAJA X 50", subfam_choices)

    def test_producto_form_alta_sin_familia_subfamilias_vacio(self):
        form = ProductoForm(empresa=self.empresa)
        subfam_choices = [val for val, label in form.fields['subfamilia'].choices if val]
        self.assertEqual(len(subfam_choices), 0)

    def test_filtrar_subfamilias_view_htmx(self):
        request = self.factory.get(f'/productos/filtrar-subfamilias/?id={self.familia_pistolas.id}')
        request.session = {'empresa_id': self.empresa.id}
        response = filtrar_subfamilias(request)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn("9MM", content)
        self.assertIn(".40 S&amp;W", content)
        self.assertNotIn("CAJA X 50", content)

    def test_producto_modal_render_edicion(self):
        from productos.views_htmx import producto_modal
        prod = Producto.objects.create(
            empresa=self.empresa,
            detalle="BERETTA 92FS",
            rubro=self.rubro_armas,
            familia=self.familia_pistolas,
            subfamilia=self.subfam_9mm
        )
        request = self.factory.get(f'/productos/{prod.id}/editar/')
        request.session = {'empresa_id': self.empresa.id}
        response = producto_modal(request, id=prod.id)
        self.assertEqual(response.status_code, 200)

    def test_producto_modal_render_producto_sin_relaciones(self):
        from productos.views_htmx import producto_modal
        prod = Producto.objects.create(
            empresa=self.empresa,
            detalle="PRODUCTO HUERFANO"
        )
        request = self.factory.get(f'/productos/{prod.id}/editar/')
        request.session = {'empresa_id': self.empresa.id}
        response = producto_modal(request, id=prod.id)
        self.assertEqual(response.status_code, 200)
