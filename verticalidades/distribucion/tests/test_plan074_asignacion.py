"""Tests de faltantes y asignación de stock escaso (Plan 074, fase 3)."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from verticalidades.distribucion.models import (AjusteAsignacion, DomicilioEntrega,
                                 ExtensionPedidoDistribucion, Personal)
from verticalidades.distribucion.services.asignacion import (aplicar_asignacion, detalle_por_pedido,
                                              detectar_faltantes, sugerir_asignacion)
from verticalidades.distribucion.services.pedidos import guardar_pedido
from empresas.models import Empresa, Sucursal
from facturacion.models import ClienteProveedor,  PreventaItem
from verticalidades.distribucion.models import ExtensionDistribuidora
from productos.models import Producto, StockSucursal
from usuarios.models import Perfil


class BaseAsignacionTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Distribuidora Prueba", cuit="30111111118",
            tipo_actividad="DISTRIBUIDORA")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, nombre="Depósito Central", punto=1)
        self.usuario = User.objects.create_user(username="admin1", password="x",
                                                is_staff=True)

        # Hay 100 unidades y se van a pedir 150: déficit de 50.
        self.producto = Producto.objects.create(
            empresa=self.empresa, detalle="Yogur x 900 vainilla",
            precio_total=Decimal('1000.00'), codigo_anterior="3002")
        StockSucursal.objects.create(
            producto=self.producto, sucursal=self.sucursal,
            stock_inicial=Decimal('100.00'), cantidad=Decimal('100.00'))

        self.clientes = []
        for nombre in ("Almacén Primero", "Kiosco Segundo", "Super Tercero"):
            cliente = ClienteProveedor.objects.create(
                empresa=self.empresa, razon_social=nombre, tipo_entidad=1,
                domicilio=f"Calle {nombre}", limite=Decimal('1000000.00'))
            ExtensionDistribuidora.objects.create(
                cliente=cliente, coeficiente_mayorista=Decimal('1.0000'))
            self.clientes.append(cliente)

    def pedir(self, cliente, cantidad):
        """Crea un pedido del producto para ese cliente."""
        return guardar_pedido(
            empresa_id=self.empresa.id, sucursal_id=self.sucursal.id,
            cliente=cliente, usuario=self.usuario,
            items=[{'producto_id': self.producto.id, 'cantidad': cantidad,
                    'precio_unitario': 1000.0, 'total': 1000.0 * cantidad,
                    'descuento': 0}])


class DeteccionDeFaltantesTestCase(BaseAsignacionTestCase):
    def test_sin_pedidos_no_hay_faltantes(self):
        self.assertEqual(detectar_faltantes(self.empresa.id, self.sucursal.id), [])

    def test_si_el_stock_alcanza_no_hay_faltante(self):
        self.pedir(self.clientes[0], 40)
        self.pedir(self.clientes[1], 50)   # 90 de 100
        self.assertEqual(detectar_faltantes(self.empresa.id, self.sucursal.id), [])

    def test_detecta_el_deficit(self):
        self.pedir(self.clientes[0], 60)
        self.pedir(self.clientes[1], 50)
        self.pedir(self.clientes[2], 40)   # 150 de 100

        faltantes = detectar_faltantes(self.empresa.id, self.sucursal.id)
        self.assertEqual(len(faltantes), 1)
        self.assertEqual(faltantes[0]['producto'], self.producto)
        self.assertEqual(faltantes[0]['stock'], Decimal('100.00'))
        self.assertEqual(faltantes[0]['pedido'], Decimal('150.00'))
        self.assertEqual(faltantes[0]['deficit'], Decimal('50.00'))

    def test_un_pedido_facturado_deja_de_competir(self):
        p1 = self.pedir(self.clientes[0], 60)
        self.pedir(self.clientes[1], 50)
        self.assertTrue(detectar_faltantes(self.empresa.id, self.sucursal.id))

        p1.preventa.estado = 3   # Facturada: ya descontó stock real
        p1.preventa.save()
        self.assertEqual(detectar_faltantes(self.empresa.id, self.sucursal.id), [])

    def test_producto_sin_stock_cargado_cuenta_como_cero(self):
        otro = Producto.objects.create(
            empresa=self.empresa, detalle="Sin stock", precio_total=Decimal('500.00'))
        guardar_pedido(
            empresa_id=self.empresa.id, sucursal_id=self.sucursal.id,
            cliente=self.clientes[0], usuario=self.usuario,
            items=[{'producto_id': otro.id, 'cantidad': 5, 'precio_unitario': 500.0,
                    'total': 2500.0, 'descuento': 0}])
        faltantes = detectar_faltantes(self.empresa.id, self.sucursal.id)
        deficit = next(f for f in faltantes if f['producto'] == otro)
        self.assertEqual(deficit['stock'], Decimal('0.00'))
        self.assertEqual(deficit['deficit'], Decimal('5.00'))

    def test_no_cruza_sucursales(self):
        otra = Sucursal.objects.create(empresa=self.empresa, nombre="Norte", punto=2)
        self.pedir(self.clientes[0], 150)
        self.assertTrue(detectar_faltantes(self.empresa.id, self.sucursal.id))
        self.assertEqual(detectar_faltantes(self.empresa.id, otra.id), [])


class OrdenDeLlegadaTestCase(BaseAsignacionTestCase):
    """El que pidió primero se sirve primero; el faltante lo absorben los últimos."""

    def setUp(self):
        super().setUp()
        self.p1 = self.pedir(self.clientes[0], 60)
        self.p2 = self.pedir(self.clientes[1], 50)
        self.p3 = self.pedir(self.clientes[2], 40)

    def test_el_detalle_sale_en_orden_de_llegada(self):
        filas = detalle_por_pedido(self.empresa.id, self.sucursal.id, self.producto.id)
        numeros = [f['pedido'].numero for f in filas]
        self.assertEqual(numeros, [self.p1.numero, self.p2.numero, self.p3.numero])

    def test_la_sugerencia_sirve_completo_hasta_agotar(self):
        filas = sugerir_asignacion(self.empresa.id, self.sucursal.id, self.producto.id)
        sugeridos = [f['sugerido'] for f in filas]
        # 100 de stock: el primero se lleva 60, el segundo los 40 que quedan, el tercero 0.
        self.assertEqual(sugeridos, [Decimal('60'), Decimal('40'), Decimal('0')])

    def test_la_sugerencia_nunca_supera_el_stock(self):
        filas = sugerir_asignacion(self.empresa.id, self.sucursal.id, self.producto.id)
        self.assertEqual(sum(f['sugerido'] for f in filas), Decimal('100'))

    def test_el_detalle_trae_cliente_y_vendedor(self):
        vendedor = Personal.objects.create(
            empresa=self.empresa, nombre="Juan", es_vendedor=True)
        self.p1.vendedor = vendedor
        self.p1.save()

        filas = detalle_por_pedido(self.empresa.id, self.sucursal.id, self.producto.id)
        self.assertEqual(filas[0]['cliente'], self.clientes[0])
        self.assertEqual(filas[0]['vendedor'], vendedor)
        self.assertIsNotNone(filas[0]['hora_carga'])


class AplicarAsignacionTestCase(BaseAsignacionTestCase):
    def setUp(self):
        super().setUp()
        self.p1 = self.pedir(self.clientes[0], 60)
        self.p2 = self.pedir(self.clientes[1], 50)
        self.items = {
            f['pedido'].numero: f['item']
            for f in detalle_por_pedido(self.empresa.id, self.sucursal.id, self.producto.id)
        }

    def test_recorta_la_cantidad_del_item(self):
        item = self.items[self.p2.numero]
        aplicar_asignacion(self.empresa.id, self.sucursal.id, self.producto.id,
                           {item.id: '40'}, self.usuario)
        item.refresh_from_db()
        self.assertEqual(item.cantidad, Decimal('40.00'))

    def test_recalcula_el_total_del_item_y_del_pedido(self):
        item = self.items[self.p2.numero]
        aplicar_asignacion(self.empresa.id, self.sucursal.id, self.producto.id,
                           {item.id: '40'}, self.usuario)
        item.refresh_from_db()
        self.p2.preventa.refresh_from_db()
        self.assertEqual(item.total, Decimal('40000.00'))
        self.assertEqual(self.p2.preventa.total, Decimal('40000.00'))

    def test_deja_rastro_del_ajuste(self):
        """Al vendedor hay que poder explicarle por qué su cliente recibió menos."""
        item = self.items[self.p2.numero]
        aplicar_asignacion(self.empresa.id, self.sucursal.id, self.producto.id,
                           {item.id: '40'}, self.usuario, observacion="Faltó stock")

        ajuste = AjusteAsignacion.objects.get()
        self.assertEqual(ajuste.pedido, self.p2)
        self.assertEqual(ajuste.cantidad_original, Decimal('50.00'))
        self.assertEqual(ajuste.cantidad_asignada, Decimal('40.00'))
        self.assertEqual(ajuste.recortado, Decimal('10.00'))
        self.assertEqual(ajuste.usuario, self.usuario)
        self.assertEqual(ajuste.observacion, "Faltó stock")

    def test_asignar_lo_mismo_que_pidio_no_genera_ajuste(self):
        item = self.items[self.p1.numero]
        ajustes = aplicar_asignacion(self.empresa.id, self.sucursal.id, self.producto.id,
                                     {item.id: '60'}, self.usuario)
        self.assertEqual(ajustes, 0)
        self.assertEqual(AjusteAsignacion.objects.count(), 0)

    def test_asignar_cero_saca_el_articulo_del_pedido(self):
        """Dejar un renglón en cero ensuciaría el comprobante y la hoja de ruta."""
        item = self.items[self.p2.numero]
        aplicar_asignacion(self.empresa.id, self.sucursal.id, self.producto.id,
                           {item.id: '0'}, self.usuario)
        self.assertFalse(PreventaItem.objects.filter(id=item.id).exists())
        # El ajuste queda igual: es la explicación de por qué desapareció.
        self.assertEqual(AjusteAsignacion.objects.count(), 1)

    def test_libera_el_stock_comprometido(self):
        item = self.items[self.p2.numero]
        aplicar_asignacion(self.empresa.id, self.sucursal.id, self.producto.id,
                           {item.id: '40'}, self.usuario)
        fila = StockSucursal.objects.get(producto=self.producto, sucursal=self.sucursal)
        self.assertEqual(fila.comprometido, Decimal('100.00'))   # 60 + 40

    def test_el_reparto_completo_elimina_el_faltante(self):
        asignaciones = {
            self.items[self.p1.numero].id: '60',
            self.items[self.p2.numero].id: '40',
        }
        aplicar_asignacion(self.empresa.id, self.sucursal.id, self.producto.id,
                           asignaciones, self.usuario)
        self.assertEqual(detectar_faltantes(self.empresa.id, self.sucursal.id), [])

    def test_cantidad_negativa_se_rechaza(self):
        item = self.items[self.p2.numero]
        with self.assertRaises(ValueError):
            aplicar_asignacion(self.empresa.id, self.sucursal.id, self.producto.id,
                               {item.id: '-5'}, self.usuario)

    def test_no_toca_items_de_otra_sucursal(self):
        otra = Sucursal.objects.create(empresa=self.empresa, nombre="Norte", punto=2)
        item = self.items[self.p2.numero]
        ajustes = aplicar_asignacion(self.empresa.id, otra.id, self.producto.id,
                                     {item.id: '10'}, self.usuario)
        self.assertEqual(ajustes, 0)
        item.refresh_from_db()
        self.assertEqual(item.cantidad, Decimal('50.00'))


class PantallasAsignacionTestCase(BaseAsignacionTestCase):
    def setUp(self):
        super().setUp()
        self.pedir(self.clientes[0], 60)
        self.pedir(self.clientes[1], 50)
        self.pedir(self.clientes[2], 40)

        self.client = Client()
        self.client.force_login(self.usuario)
        sesion = self.client.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion.save()

    def test_el_reporte_responde_y_muestra_el_deficit(self):
        respuesta = self.client.get(reverse('distribucion_faltantes'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("YOGUR X 900 VAINILLA", respuesta.content.decode('utf-8').upper())

    def test_la_pantalla_de_reparto_responde(self):
        respuesta = self.client.get(
            reverse('distribucion_asignacion', args=[self.producto.id]))
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode('utf-8').upper()
        for cliente in self.clientes:
            self.assertIn(cliente.razon_social.upper(), contenido)

    def test_aplicar_desde_la_pantalla_recorta_y_audita(self):
        filas = sugerir_asignacion(self.empresa.id, self.sucursal.id, self.producto.id)
        datos = {f'cantidad_{f["item"].id}': str(int(f['sugerido'])) for f in filas}
        respuesta = self.client.post(
            reverse('distribucion_asignacion', args=[self.producto.id]), datos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('reloadFaltantes', respuesta['HX-Trigger'])
        self.assertEqual(detectar_faltantes(self.empresa.id, self.sucursal.id), [])
        self.assertTrue(AjusteAsignacion.objects.exists())

    def test_acepta_cantidades_en_formato_es_ar(self):
        filas = detalle_por_pedido(self.empresa.id, self.sucursal.id, self.producto.id)
        item = filas[0]['item']
        self.client.post(reverse('distribucion_asignacion', args=[self.producto.id]),
                         {f'cantidad_{item.id}': '1.234,00'})
        item.refresh_from_db()
        self.assertEqual(item.cantidad, Decimal('1234.00'))

    def test_sin_permiso_no_se_puede_aplicar(self):
        raso = User.objects.create_user(username="raso", password="x")
        Perfil.objects.create(usuario=raso).empresas.add(self.empresa)
        cliente = Client()
        cliente.force_login(raso)
        sesion = cliente.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion.save()

        filas = detalle_por_pedido(self.empresa.id, self.sucursal.id, self.producto.id)
        item = filas[0]['item']
        respuesta = cliente.post(
            reverse('distribucion_asignacion', args=[self.producto.id]),
            {f'cantidad_{item.id}': '1'})

        self.assertEqual(respuesta.status_code, 403)
        item.refresh_from_db()
        self.assertEqual(item.cantidad, Decimal('60.00'))

    def test_con_el_permiso_propio_si_puede(self):
        autorizado = User.objects.create_user(username="jefe", password="x")
        perfil = Perfil.objects.create(
            usuario=autorizado, permiso_distribucion_asignar_stock=True)
        perfil.empresas.add(self.empresa)
        cliente = Client()
        cliente.force_login(autorizado)
        sesion = cliente.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion.save()

        filas = detalle_por_pedido(self.empresa.id, self.sucursal.id, self.producto.id)
        item = filas[0]['item']
        respuesta = cliente.post(
            reverse('distribucion_asignacion', args=[self.producto.id]),
            {f'cantidad_{item.id}': '10'})

        self.assertEqual(respuesta.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.cantidad, Decimal('10.00'))
