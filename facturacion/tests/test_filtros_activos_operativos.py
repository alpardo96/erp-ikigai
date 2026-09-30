from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from empresas.models import Empresa
from facturacion.models import ClienteProveedor
from productos.models import Producto
from facturacion.views_htmx import (
    buscar_producto_venta_por_codigo,
    buscar_producto_por_codigo,
    buscar_producto_por_codprov,
    typeahead_clientes,
    lista_clientes_venta_resultados,
)
from tesoreria.views_htmx import (
    buscar_cliente_proveedor,
    lista_clientes_recibo_resultados,
    lista_proveedores_op_resultados,
)

User = get_user_model()

class FiltrosActivosOperativosTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.empresa = Empresa.objects.create(
            nombre="Empresa Activos Test",
            cuit="30111111118"
        )
        # Productos
        self.prod_activo = Producto.objects.create(
            empresa=self.empresa,
            detalle="PISTOLA 9MM ACTIVA",
            cod_prov="P01",
            cod_fab="F01",
            activo=True
        )
        self.prod_inactivo = Producto.objects.create(
            empresa=self.empresa,
            detalle="PISTOLA 9MM INACTIVA",
            cod_prov="P02",
            cod_fab="F02",
            activo=False
        )
        # Clientes
        self.cli_activo = ClienteProveedor.objects.create(
            empresa=self.empresa,
            razon_social="JUAN PEREZ ACTIVO",
            cuit="20111111112",
            tipo_entidad=1,
            activo=True
        )
        self.cli_inactivo = ClienteProveedor.objects.create(
            empresa=self.empresa,
            razon_social="PEDRO GOMEZ INACTIVO",
            cuit="20222222222",
            tipo_entidad=1,
            activo=False
        )
        # Proveedores
        self.prov_activo = ClienteProveedor.objects.create(
            empresa=self.empresa,
            razon_social="PROVEEDOR ACTIVO SA",
            cuit="30333333333",
            tipo_entidad=2,
            activo=True
        )
        self.prov_inactivo = ClienteProveedor.objects.create(
            empresa=self.empresa,
            razon_social="PROVEEDOR INACTIVO SA",
            cuit="30444444444",
            tipo_entidad=2,
            activo=False
        )

    def _prepare_request(self, path):
        request = self.factory.get(path)
        request.user = self.user
        request.session = {'empresa_id': self.empresa.id}
        return request

    def test_buscar_producto_venta_ignora_inactivo(self):
        request = self._prepare_request(f'/facturacion/buscar-producto-venta/?q={self.prod_inactivo.id}')
        response = buscar_producto_venta_por_codigo(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("No encontrado", response.content.decode('utf-8'))

    def test_buscar_producto_venta_encuentra_activo(self):
        request = self._prepare_request(f'/facturacion/buscar-producto-venta/?q={self.prod_activo.id}')
        response = buscar_producto_venta_por_codigo(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("HX-Trigger", response.headers)
        self.assertIn("productoVentaEncontrado", response.headers["HX-Trigger"])

    def test_buscar_producto_compra_ignora_inactivo(self):
        request = self._prepare_request(f'/facturacion/buscar-producto-codigo/?q={self.prod_inactivo.cod_prov}')
        response = buscar_producto_por_codigo(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("No encontrado", response.content.decode('utf-8'))

    def test_typeahead_clientes_ignora_inactivos(self):
        request = self._prepare_request('/facturacion/typeahead/clientes/?q=INACTIVO')
        response = typeahead_clientes(request)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("PEDRO GOMEZ INACTIVO", response.content.decode('utf-8'))

    def test_typeahead_clientes_muestra_activos(self):
        request = self._prepare_request('/facturacion/typeahead/clientes/?q=ACTIVO')
        response = typeahead_clientes(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("JUAN PEREZ ACTIVO", response.content.decode('utf-8'))

    def test_tesoreria_op_proveedores_ignora_inactivos(self):
        request = self._prepare_request('/tesoreria/htmx/ordenes-pago/proveedores/buscar-lista/?q=PROVEEDOR')
        response = lista_proveedores_op_resultados(request)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn("PROVEEDOR ACTIVO SA", content)
        self.assertNotIn("PROVEEDOR INACTIVO SA", content)

    def test_tesoreria_recibos_clientes_ignora_inactivos(self):
        request = self._prepare_request('/tesoreria/htmx/recibos/clientes/buscar-lista/?q=ACTIVO')
        response = lista_clientes_recibo_resultados(request)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn("JUAN PEREZ ACTIVO", content)
        self.assertNotIn("PEDRO GOMEZ INACTIVO", content)
