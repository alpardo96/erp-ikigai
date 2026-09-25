from django.test import TestCase, Client
from django.contrib.auth.models import User, Permission
from empresas.models import Empresa, Sucursal
from facturacion.models import ClienteProveedor
from productos.models import Producto, Rubro
from usuarios.models import Perfil


class ToggleActivoAdminTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Empresa Test",
            cuit="30111111118",
            tipo_actividad="ARMERIA"
        )
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa,
            nombre="Central",
            punto=1
        )
        # Usuario Admin
        self.admin_user = User.objects.create_user(
            username="adminuser",
            password="password123",
            is_superuser=True
        )
        # Usuario Estándar (Vendedor / No Admin)
        self.std_user = User.objects.create_user(
            username="stduser",
            password="password123",
            is_superuser=False,
            is_staff=False
        )
        perfil = Perfil.objects.create(
            usuario=self.std_user,
            es_admin_sistema=False
        )
        perfil.empresas.add(self.empresa)

        # Permisos básicos de menú para usuario estándar
        for codename in ['menu_clientes', 'menu_stock', 'menu_stock_dashboard']:
            p = Permission.objects.filter(codename=codename).first()
            if p:
                self.std_user.user_permissions.add(p)

        # Clientes
        self.cli_activo = ClienteProveedor.objects.create(
            empresa=self.empresa,
            razon_social="Cliente Activo",
            cuit="20111111111",
            tipo_entidad=1,
            activo=True
        )
        self.cli_inactivo = ClienteProveedor.objects.create(
            empresa=self.empresa,
            razon_social="Cliente Inactivo",
            cuit="20222222222",
            tipo_entidad=1,
            activo=False
        )

        # Productos
        self.rubro = Rubro.objects.create(empresa=self.empresa, detalle="General")
        self.prod_activo = Producto.objects.create(
            empresa=self.empresa,
            detalle="Producto Activo",
            rubro=self.rubro,
            activo=True
        )
        self.prod_inactivo = Producto.objects.create(
            empresa=self.empresa,
            detalle="Producto Inactivo",
            rubro=self.rubro,
            activo=False
        )

    def test_std_user_no_puede_deshabilitar_cliente(self):
        client = Client()
        client.force_login(self.std_user)
        session = client.session
        session['empresa_id'] = self.empresa.id
        session['sucursal_id'] = self.sucursal.id
        session.save()

        resp = client.post(f"/clientes/{self.cli_activo.codigo_id}/eliminar/", HTTP_HX_REQUEST='true')
        self.assertEqual(resp.status_code, 403)
        self.cli_activo.refresh_from_db()
        self.assertTrue(self.cli_activo.activo)

    def test_admin_user_puede_deshabilitar_y_habilitar_cliente(self):
        client = Client()
        client.force_login(self.admin_user)
        session = client.session
        session['empresa_id'] = self.empresa.id
        session['sucursal_id'] = self.sucursal.id
        session.save()

        # 1. Deshabilitar
        resp1 = client.post(f"/clientes/{self.cli_activo.codigo_id}/eliminar/", HTTP_HX_REQUEST='true')
        self.assertEqual(resp1.status_code, 200)
        self.cli_activo.refresh_from_db()
        self.assertFalse(self.cli_activo.activo)

        # 2. Habilitar
        resp2 = client.post(f"/clientes/{self.cli_activo.codigo_id}/eliminar/", HTTP_HX_REQUEST='true')
        self.assertEqual(resp2.status_code, 200)
        self.cli_activo.refresh_from_db()
        self.assertTrue(self.cli_activo.activo)

    def test_filtro_estado_clientes_admin_vs_std(self):
        # Usuario estándar solo ve activos aunque intente pasar estado_activo=deshabilitados
        client_std = Client()
        client_std.force_login(self.std_user)
        s = client_std.session
        s['empresa_id'] = self.empresa.id
        s['sucursal_id'] = self.sucursal.id
        s.save()

        resp_std = client_std.get("/clientes/buscar/?estado_activo=deshabilitados", HTTP_HX_REQUEST='true')
        self.assertEqual(resp_std.status_code, 200)
        self.assertIn(b"CLIENTE ACTIVO", resp_std.content)
        self.assertNotIn(b"CLIENTE INACTIVO", resp_std.content)

        # Administrador puede ver deshabilitados
        client_admin = Client()
        client_admin.force_login(self.admin_user)
        s_adm = client_admin.session
        s_adm['empresa_id'] = self.empresa.id
        s_adm['sucursal_id'] = self.sucursal.id
        s_adm.save()

        resp_adm = client_admin.get("/clientes/buscar/?estado_activo=deshabilitados", HTTP_HX_REQUEST='true')
        self.assertEqual(resp_adm.status_code, 200)
        self.assertNotIn(b"CLIENTE ACTIVO", resp_adm.content)
        self.assertIn(b"CLIENTE INACTIVO", resp_adm.content)

        # Administrador puede ver todos
        resp_todos = client_admin.get("/clientes/buscar/?estado_activo=todos", HTTP_HX_REQUEST='true')
        self.assertEqual(resp_todos.status_code, 200)
        self.assertIn(b"CLIENTE ACTIVO", resp_todos.content)
        self.assertIn(b"CLIENTE INACTIVO", resp_todos.content)

    def test_std_user_no_puede_deshabilitar_producto(self):
        client = Client()
        client.force_login(self.std_user)
        session = client.session
        session['empresa_id'] = self.empresa.id
        session['sucursal_id'] = self.sucursal.id
        session.save()

        resp = client.post(f"/productos/{self.prod_activo.id}/eliminar/", HTTP_HX_REQUEST='true')
        self.assertEqual(resp.status_code, 403)
        self.prod_activo.refresh_from_db()
        self.assertTrue(self.prod_activo.activo)

    def test_admin_user_puede_deshabilitar_y_habilitar_producto(self):
        client = Client()
        client.force_login(self.admin_user)
        session = client.session
        session['empresa_id'] = self.empresa.id
        session['sucursal_id'] = self.sucursal.id
        session.save()

        # 1. Deshabilitar
        resp1 = client.post(f"/productos/{self.prod_activo.id}/eliminar/", HTTP_HX_REQUEST='true')
        self.assertEqual(resp1.status_code, 200)
        self.prod_activo.refresh_from_db()
        self.assertFalse(self.prod_activo.activo)

        # 2. Habilitar
        resp2 = client.post(f"/productos/{self.prod_activo.id}/eliminar/", HTTP_HX_REQUEST='true')
        self.assertEqual(resp2.status_code, 200)
        self.prod_activo.refresh_from_db()
        self.assertTrue(self.prod_activo.activo)

    def test_filtro_estado_productos_admin_vs_std(self):
        # Usuario estándar solo ve activos
        client_std = Client()
        client_std.force_login(self.std_user)
        s = client_std.session
        s['empresa_id'] = self.empresa.id
        s['sucursal_id'] = self.sucursal.id
        s.save()

        resp_std = client_std.get("/productos/buscar/?estado_activo=deshabilitados", HTTP_HX_REQUEST='true')
        self.assertEqual(resp_std.status_code, 200)
        self.assertIn(b"PRODUCTO ACTIVO", resp_std.content)
        self.assertNotIn(b"PRODUCTO INACTIVO", resp_std.content)

        # Administrador puede ver deshabilitados
        client_admin = Client()
        client_admin.force_login(self.admin_user)
        s_adm = client_admin.session
        s_adm['empresa_id'] = self.empresa.id
        s_adm['sucursal_id'] = self.sucursal.id
        s_adm.save()

        resp_adm = client_admin.get("/productos/buscar/?estado_activo=deshabilitados", HTTP_HX_REQUEST='true')
        self.assertEqual(resp_adm.status_code, 200)
        self.assertNotIn(b"PRODUCTO ACTIVO", resp_adm.content)
        self.assertIn(b"PRODUCTO INACTIVO", resp_adm.content)
