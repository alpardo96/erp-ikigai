from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from empresas.models import Empresa, Sucursal
from productos.models import Producto, Marca, Rubro, Familia
from productos.services.busqueda_service import buscar_productos_inteligente, construir_filtro_busqueda_producto

User = get_user_model()

class BusquedaInteligenteProductosTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='vendedor_test', password='password123')
        self.empresa_a = Empresa.objects.create(nombre="Empresa Armeria Test")
        self.empresa_b = Empresa.objects.create(nombre="Empresa Otra Test")
        self.sucursal = Sucursal.objects.create(nombre="Casa Central", empresa=self.empresa_a)

        self.marca_bersa = Marca.objects.create(detalle="BERSA", empresa=self.empresa_a)
        self.marca_glock = Marca.objects.create(detalle="GLOCK", empresa=self.empresa_a)
        self.rubro_armas = Rubro.objects.create(detalle="ARMAS DE FUEGO", empresa=self.empresa_a)

        # Productos en Empresa A
        self.prod1 = Producto.objects.create(
            detalle="PISTOLA BERSA TPR9 CALIBRE 9X19MM PAVONADA",
            cod_fab="TPR9-9",
            cod_prov="BER-001",
            codigo_anterior="VFP-991",
            marca=self.marca_bersa,
            rubro=self.rubro_armas,
            empresa=self.empresa_a
        )

        self.prod2 = Producto.objects.create(
            detalle="PISTOLA GLOCK 17 GEN 5 9X19MM",
            cod_fab="G17-GEN5",
            cod_prov="GLO-017",
            codigo_anterior="VFP-992",
            marca=self.marca_glock,
            rubro=self.rubro_armas,
            empresa=self.empresa_a
        )

        self.prod3 = Producto.objects.create(
            detalle="CARGADOR BERSA 17 TIROS 9MM",
            cod_fab="CARG-TPR9",
            cod_prov="BER-CARG",
            marca=self.marca_bersa,
            empresa=self.empresa_a
        )

        self.prod4 = Producto.objects.create(
            detalle="LINTERNA TACTICA LED RECARGABLE USB",
            cod_fab="LINT-USB",
            empresa=self.empresa_a
        )

        # Producto en Empresa B (para testear aislamiento)
        self.prod_empresa_b = Producto.objects.create(
            detalle="PISTOLA BERSA TPR9 CALIBRE 9X19MM",
            cod_fab="TPR9-9",
            empresa=self.empresa_b
        )

    def test_busqueda_palabras_orden_invertido(self):
        """Búsqueda '9mm bersa' encuentra 'PISTOLA BERSA TPR9 CALIBRE 9X19MM PAVONADA' y el cargador"""
        resultados = list(buscar_productos_inteligente(
            q="9mm bersa",
            empresa_id=self.empresa_a.id
        ))
        ids = [p.id for p in resultados]
        self.assertIn(self.prod1.id, ids)
        self.assertIn(self.prod3.id, ids)
        self.assertNotIn(self.prod2.id, ids)

    def test_busqueda_palabras_en_el_medio_e_intercaladas(self):
        """Búsqueda 'tpr9 pavonada' encuentra el producto 1 aunque estén separadas por otras palabras"""
        resultados = list(buscar_productos_inteligente(
            q="tpr9 pavonada",
            empresa_id=self.empresa_a.id
        ))
        ids = [p.id for p in resultados]
        self.assertEqual(ids, [self.prod1.id])

    def test_busqueda_palabras_adelante_atras_medio(self):
        """Búsqueda 'recargable linterna' encuentra 'LINTERNA TACTICA LED RECARGABLE USB'"""
        resultados = list(buscar_productos_inteligente(
            q="recargable linterna",
            empresa_id=self.empresa_a.id
        ))
        ids = [p.id for p in resultados]
        self.assertEqual(ids, [self.prod4.id])

    def test_busqueda_por_marca_y_codigo_anterior(self):
        """Búsqueda por código del sistema anterior 'VFP-991' o código de fábrica"""
        resultados = list(buscar_productos_inteligente(
            q="VFP-991",
            empresa_id=self.empresa_a.id
        ))
        self.assertEqual([p.id for p in resultados], [self.prod1.id])

        resultados_codfab = list(buscar_productos_inteligente(
            q="G17-GEN5",
            empresa_id=self.empresa_a.id
        ))
        self.assertEqual([p.id for p in resultados_codfab], [self.prod2.id])

    def test_relevancia_prioriza_coincidencia_exacta_de_codigo(self):
        """Un producto cuyo código exacto coincide con la búsqueda debe figurar antes que otros"""
        resultados = list(buscar_productos_inteligente(
            q="TPR9-9",
            empresa_id=self.empresa_a.id
        ))
        self.assertEqual(resultados[0].id, self.prod1.id)

    def test_aislamiento_multitenant(self):
        """No debe devolver productos de otra empresa"""
        resultados_a = list(buscar_productos_inteligente(
            q="bersa",
            empresa_id=self.empresa_a.id
        ))
        ids_a = [p.id for p in resultados_a]
        self.assertNotIn(self.prod_empresa_b.id, ids_a)

        resultados_b = list(buscar_productos_inteligente(
            q="bersa",
            empresa_id=self.empresa_b.id
        ))
        ids_b = [p.id for p in resultados_b]
        self.assertEqual(ids_b, [self.prod_empresa_b.id])

    def test_endpoints_htmx_typeahead_y_buscar_codigo(self):
        """Verificar los endpoints HTMX de preventa y ventas con la nueva búsqueda inteligente"""
        client = Client()
        client.force_login(self.user)
        session = client.session
        session['empresa_id'] = self.empresa_a.id
        session['sucursal_id'] = self.sucursal.id
        session.save()

        # 1. Typeahead ventas con términos permutados
        url_typeahead = reverse('typeahead_productos_venta') + '?q=9mm+bersa'
        response = client.get(url_typeahead)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PISTOLA BERSA TPR9")
        self.assertContains(response, "CARGADOR BERSA 17")

        # 2. Enter rápido en input de preventa
        url_buscar_codigo = reverse('ventas_producto_buscar_codigo') + '?q=TPR9-9'
        response = client.get(url_buscar_codigo)
        self.assertEqual(response.status_code, 200)
        self.assertIn('HX-Trigger', response.headers)
        self.assertIn('productoVentaEncontrado', response.headers['HX-Trigger'])
        self.assertIn(self.prod1.detalle, response.headers['HX-Trigger'])

        # 3. Enter rápido con fallback inteligente
        url_buscar_inteligente = reverse('ventas_producto_buscar_codigo') + '?q=recargable+linterna'
        response = client.get(url_buscar_inteligente)
        self.assertEqual(response.status_code, 200)
        self.assertIn('HX-Trigger', response.headers)
        self.assertIn(self.prod4.detalle, response.headers['HX-Trigger'])
