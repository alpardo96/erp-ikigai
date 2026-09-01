"""Reparto, Hoja de Ruta y Consolidado de Artículos (Plan 074, fase 5).

Los dos documentos que salen impresos con el camión, replicando las hojas 3 y 4 del
sistema anterior.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from contable.models import Cuenta, Ejercicio, ParametrosContables
from verticalidades.distribucion.models import (DomicilioEntrega, Personal, Reparto, RepartoParada,
                                 Vehiculo, ZonaReparto)
from verticalidades.distribucion.services.facturacion import facturar_pedido
from verticalidades.distribucion.services.pedidos import guardar_pedido
from verticalidades.distribucion.services.reparto import (agregar_paradas, cerrar_reparto,
                                           comprobantes_sin_reparto, consolidado,
                                           crear_reparto, hoja_de_ruta, quitar_parada,
                                           totales_hoja_de_ruta)
from empresas.models import Empresa, PuntoVenta, Sucursal
from facturacion.models import ClienteProveedor,  TipoComprobante
from verticalidades.distribucion.models import ExtensionDistribuidora
from productos.models import Producto, Rubro, StockSucursal


class BaseRepartoTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Distribuidora Prueba", cuit="30111111118",
            tipo_actividad="DISTRIBUIDORA")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, nombre="Depósito Central", punto=1)
        PuntoVenta.objects.create(empresa=self.empresa, sucursal=self.sucursal, numero=4)
        Ejercicio.objects.create(
            empresa=self.empresa, inicio="2026-01-01", cierre="2026-12-31")

        self.usuario = User.objects.create_user(username="admin1", password="x", is_staff=True)
        TipoComprobante.objects.create(codigo='006', detalle="Factura B", signo=1)
        TipoComprobante.objects.create(codigo='PRE', detalle="Comprobante Interno", signo=1)

        cta_cli = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.3", cuenta="DEUDORES", imputable=1)
        cta_vta = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="4.1.1", cuenta="VENTAS", imputable=1)
        ParametrosContables.objects.create(
            empresa=self.empresa, cta_clientes_default=cta_cli, cta_ventas=cta_vta,
            metodo_contabilizacion_ventas=1)

        self.zona = ZonaReparto.objects.create(
            empresa=self.empresa, nombre="San Cayetano", orden=1)
        self.vehiculo = Vehiculo.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, patente="AB123CD",
            descripcion="Furgón", capacidad_kg=Decimal('500.00'))
        self.juan = Personal.objects.create(
            empresa=self.empresa, nombre="Juan", es_repartidor=True)
        self.romina = Personal.objects.create(
            empresa=self.empresa, nombre="Romina", es_repartidor=True)

        rubro = Rubro.objects.create(empresa=self.empresa, detalle="LACTEOS",
                                     cta_ventas=cta_vta)
        # 2 kg por unidad: con 10 unidades por pedido, 20 kg cada uno.
        self.producto = Producto.objects.create(
            empresa=self.empresa, detalle="Yogur x 900", precio_total=Decimal('1000.00'),
            codigo_anterior="3002", peso_unitario_kg=Decimal('2.000'), rubro=rubro)
        StockSucursal.objects.create(
            producto=self.producto, sucursal=self.sucursal,
            stock_inicial=Decimal('5000.00'), cantidad=Decimal('5000.00'))

    def crear_cliente(self, nombre, limite='100000.00'):
        cliente = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social=nombre, tipo_entidad=1,
            domicilio="Belgrano 100", condicion_iva="CONSUMIDOR FINAL",
            limite=Decimal(limite))
        ExtensionDistribuidora.objects.create(
            cliente=cliente, coeficiente_mayorista=Decimal('1.0000'))
        DomicilioEntrega.objects.create(
            empresa=self.empresa, cliente=cliente, nombre="Casa Central",
            domicilio="Belgrano 100", zona=self.zona, es_principal=True)
        return cliente

    def pedido_facturado(self, nombre, cantidad=10, limite='100000.00'):
        cliente = self.crear_cliente(nombre, limite=limite)
        pedido = guardar_pedido(
            empresa_id=self.empresa.id, sucursal_id=self.sucursal.id,
            cliente=cliente, usuario=self.usuario, condic_destino=2,
            items=[{'producto_id': self.producto.id, 'cantidad': cantidad,
                    'precio_unitario': 1000.0, 'total': 1000.0 * cantidad,
                    'descuento': 0}])
        facturar_pedido(pedido, self.usuario)
        pedido.refresh_from_db()
        return pedido

    def reparto_con(self, *pedidos):
        reparto = crear_reparto(
            self.empresa.id, self.sucursal.id, self.usuario,
            vehiculo=self.vehiculo, zona=self.zona,
            responsables=[self.juan, self.romina])
        agregar_paradas(reparto, list(pedidos))
        return reparto


class ArmadoDelRepartoTestCase(BaseRepartoTestCase):
    def test_el_reparto_lleva_numero_correlativo(self):
        primero = crear_reparto(self.empresa.id, self.sucursal.id, self.usuario)
        segundo = crear_reparto(self.empresa.id, self.sucursal.id, self.usuario)
        self.assertEqual([primero.numero, segundo.numero], [1, 2])

    def test_los_responsables_se_muestran_como_en_el_papel(self):
        reparto = crear_reparto(self.empresa.id, self.sucursal.id, self.usuario,
                                responsables=[self.juan, self.romina])
        self.assertEqual(reparto.responsables_display, "JUAN + ROMINA")

    def test_solo_se_ofrecen_comprobantes_emitidos_y_sin_reparto(self):
        pedido = self.pedido_facturado("Cliente Uno")
        disponibles = comprobantes_sin_reparto(self.empresa.id, self.sucursal.id)
        self.assertEqual(list(disponibles), [pedido])

        self.reparto_con(pedido)
        self.assertEqual(comprobantes_sin_reparto(self.empresa.id, self.sucursal.id).count(), 0)

    def test_un_pedido_sin_facturar_no_se_ofrece(self):
        """Al reparto entran comprobantes emitidos, no pedidos."""
        cliente = self.crear_cliente("Sin Facturar")
        guardar_pedido(
            empresa_id=self.empresa.id, sucursal_id=self.sucursal.id,
            cliente=cliente, usuario=self.usuario, condic_destino=2,
            items=[{'producto_id': self.producto.id, 'cantidad': 5,
                    'precio_unitario': 1000.0, 'total': 5000.0, 'descuento': 0}])
        self.assertEqual(comprobantes_sin_reparto(self.empresa.id, self.sucursal.id).count(), 0)

    def test_un_comprobante_no_puede_estar_en_dos_repartos(self):
        """Si estuviera en dos, la mercadería se cargaría dos veces."""
        pedido = self.pedido_facturado("Cliente Uno")
        self.reparto_con(pedido)

        otro = crear_reparto(self.empresa.id, self.sucursal.id, self.usuario)
        self.assertEqual(agregar_paradas(otro, [pedido]), 0)

    def test_se_pueden_quitar_paradas_mientras_esta_armado(self):
        pedido = self.pedido_facturado("Cliente Uno")
        reparto = self.reparto_con(pedido)
        quitar_parada(reparto.paradas.first())
        self.assertEqual(reparto.paradas.count(), 0)
        # Vuelve a estar disponible para otro reparto.
        self.assertEqual(comprobantes_sin_reparto(self.empresa.id, self.sucursal.id).count(), 1)

    def test_un_reparto_cerrado_no_admite_cambios(self):
        reparto = self.reparto_con(self.pedido_facturado("Cliente Uno"))
        cerrar_reparto(reparto, self.usuario)

        with self.assertRaises(ValueError):
            agregar_paradas(reparto, [self.pedido_facturado("Cliente Dos")])
        with self.assertRaises(ValueError):
            quitar_parada(reparto.paradas.first())

    def test_no_se_puede_cerrar_un_reparto_vacio(self):
        reparto = crear_reparto(self.empresa.id, self.sucursal.id, self.usuario)
        with self.assertRaises(ValueError):
            cerrar_reparto(reparto, self.usuario)


class CongeladoDeImportesTestCase(BaseRepartoTestCase):
    """El papel es la foto de un momento: si el reporte recalculara, el control contra
    la firma del cliente dejaría de servir."""

    def test_al_cerrar_se_congelan_los_tres_importes(self):
        pedido = self.pedido_facturado("Cliente Uno", cantidad=10)   # 10.000
        reparto = self.reparto_con(pedido)
        cerrar_reparto(reparto, self.usuario)

        parada = reparto.paradas.first()
        self.assertEqual(parada.saldo_anterior, Decimal('0.00'))
        self.assertEqual(parada.saldo_disponible, Decimal('90000.00'))
        self.assertEqual(parada.cobro_minimo, Decimal('0.00'))

    def test_el_cobro_minimo_sale_del_disponible_negativo(self):
        """Límite 5.000 y carga de 10.000 → disponible −5.000, cobro mínimo 5.000."""
        pedido = self.pedido_facturado("Ajustado", cantidad=10, limite='5000.00')
        reparto = self.reparto_con(pedido)
        cerrar_reparto(reparto, self.usuario)

        parada = reparto.paradas.first()
        self.assertEqual(parada.saldo_disponible, Decimal('-5000.00'))
        self.assertEqual(parada.cobro_minimo, Decimal('5000.00'))

    def test_los_importes_no_cambian_si_el_cliente_paga_despues(self):
        pedido = self.pedido_facturado("Ajustado", cantidad=10, limite='5000.00')
        reparto = self.reparto_con(pedido)
        cerrar_reparto(reparto, self.usuario)
        congelado = reparto.paradas.first().cobro_minimo

        cliente = pedido.preventa.cliente
        cliente.saldo = Decimal('0.00')
        cliente.save(update_fields=['saldo'])

        reparto.paradas.first().refresh_from_db()
        self.assertEqual(reparto.paradas.first().cobro_minimo, congelado)

    def test_cerrar_deja_el_reparto_en_estado_cerrado(self):
        reparto = self.reparto_con(self.pedido_facturado("Cliente Uno"))
        cerrar_reparto(reparto, self.usuario)
        reparto.refresh_from_db()
        self.assertEqual(reparto.estado, Reparto.CERRADO)
        self.assertFalse(reparto.editable)


class HojaDeRutaTestCase(BaseRepartoTestCase):
    def test_las_paradas_salen_en_orden_alfabetico_por_cliente(self):
        """Es el orden del control: el repartidor busca al cliente por nombre."""
        zeta = self.pedido_facturado("Zapatería Zeta")
        alfa = self.pedido_facturado("Almacén Alfa")
        medio = self.pedido_facturado("Mercado Medio")

        reparto = self.reparto_con(zeta, alfa, medio)
        nombres = [p.venta.cliente_razon_social for p in hoja_de_ruta(reparto)]
        self.assertEqual(nombres, ["ALMACÉN ALFA", "MERCADO MEDIO", "ZAPATERÍA ZETA"])

    def test_la_parada_expone_el_pedido_y_el_comprobante(self):
        """Los dos números: con ellos se arma después la devolución y la NC."""
        pedido = self.pedido_facturado("Cliente Uno")
        reparto = self.reparto_con(pedido)
        parada = reparto.paradas.first()

        self.assertEqual(parada.pedido, pedido)
        self.assertEqual(parada.venta, pedido.venta)

    def test_la_parada_expone_el_domicilio_de_entrega(self):
        pedido = self.pedido_facturado("Cliente Uno")
        reparto = self.reparto_con(pedido)
        self.assertIn("BELGRANO 100", reparto.paradas.first().domicilio_entrega.upper())

    def test_los_totales_del_pie(self):
        reparto = self.reparto_con(
            self.pedido_facturado("Uno", cantidad=10),
            self.pedido_facturado("Dos", cantidad=5, limite='1000.00'))
        cerrar_reparto(reparto, self.usuario)

        totales = totales_hoja_de_ruta(reparto)
        self.assertEqual(totales['paradas'], 2)
        self.assertEqual(totales['total'], Decimal('15000.00'))
        self.assertEqual(totales['cobro_minimo'], Decimal('4000.00'))   # 5.000 − 1.000


class ConsolidadoTestCase(BaseRepartoTestCase):
    def test_agrupa_por_producto_y_suma_kilos(self):
        reparto = self.reparto_con(
            self.pedido_facturado("Uno", cantidad=10),
            self.pedido_facturado("Dos", cantidad=15))

        filas, totales = consolidado(reparto)
        self.assertEqual(len(filas), 1)                       # un solo artículo
        self.assertEqual(filas[0]['cantidad'], Decimal('25'))
        self.assertEqual(filas[0]['kilos'], Decimal('50.000'))   # 25 × 2 kg
        self.assertEqual(totales['cantidad'], Decimal('25'))
        self.assertEqual(totales['kilos'], Decimal('50.000'))

    def test_avisa_cuando_la_carga_supera_la_capacidad(self):
        # 300 unidades × 2 kg = 600 kg, sobre una capacidad de 500.
        reparto = self.reparto_con(self.pedido_facturado(
            "Grande", cantidad=300, limite='9999999.00'))
        _, totales = consolidado(reparto)
        self.assertEqual(totales['kilos'], Decimal('600.000'))
        self.assertTrue(totales['excede_capacidad'])

    def test_producto_sin_peso_no_rompe_pero_avisa(self):
        sin_peso = Producto.objects.create(
            empresa=self.empresa, detalle="Sin peso", precio_total=Decimal('500.00'))
        StockSucursal.objects.create(
            producto=sin_peso, sucursal=self.sucursal,
            stock_inicial=Decimal('100.00'), cantidad=Decimal('100.00'))
        cliente = self.crear_cliente("Cliente Mixto")
        pedido = guardar_pedido(
            empresa_id=self.empresa.id, sucursal_id=self.sucursal.id,
            cliente=cliente, usuario=self.usuario, condic_destino=2,
            items=[{'producto_id': sin_peso.id, 'cantidad': 4,
                    'precio_unitario': 500.0, 'total': 2000.0, 'descuento': 0}])
        facturar_pedido(pedido, self.usuario)
        pedido.refresh_from_db()

        filas, totales = consolidado(self.reparto_con(pedido))
        self.assertEqual(totales['kilos'], Decimal('0'))
        self.assertEqual(totales['sin_peso'], 1)

    def test_un_reparto_vacio_da_consolidado_vacio(self):
        reparto = crear_reparto(self.empresa.id, self.sucursal.id, self.usuario)
        filas, totales = consolidado(reparto)
        self.assertEqual(filas, [])
        self.assertEqual(totales['cantidad'], Decimal('0.00'))


class PantallasRepartoTestCase(BaseRepartoTestCase):
    def setUp(self):
        super().setUp()
        self.pedido = self.pedido_facturado("Almacén Don José")
        self.client = Client()
        self.client.force_login(self.usuario)
        sesion = self.client.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion.save()

    def test_el_listado_responde(self):
        self.assertEqual(self.client.get(reverse('distribucion_repartos')).status_code, 200)

    def test_crear_reparto_desde_la_pantalla(self):
        respuesta = self.client.post(reverse('distribucion_repartos'), {
            'vehiculo': self.vehiculo.id, 'zona': self.zona.id,
            'responsables': [self.juan.id]})
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Reparto.objects.count(), 1)

    def test_agregar_y_cerrar_desde_la_pantalla(self):
        reparto = crear_reparto(self.empresa.id, self.sucursal.id, self.usuario)
        url = reverse('distribucion_reparto_detalle', args=[reparto.id])

        self.client.post(url, {'accion': 'agregar', 'pedidos': [str(self.pedido.id)]})
        self.assertEqual(reparto.paradas.count(), 1)

        self.client.post(url, {'accion': 'cerrar'})
        reparto.refresh_from_db()
        self.assertEqual(reparto.estado, Reparto.CERRADO)

    def test_la_hoja_de_ruta_se_imprime_con_los_datos_del_papel(self):
        reparto = self.reparto_con(self.pedido)
        cerrar_reparto(reparto, self.usuario)

        respuesta = self.client.get(reverse('distribucion_hoja_de_ruta', args=[reparto.id]))
        contenido = respuesta.content.decode('utf-8')
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Hoja de Ruta", contenido)
        self.assertIn("ALMACÉN DON JOSÉ", contenido.upper())
        self.assertIn("Cobro Mínimo", contenido)
        self.assertIn("Firma", contenido)
        self.assertIn("Devolución", contenido)
        self.assertIn(f"Reparto: {reparto.numero}", contenido)

    def test_el_consolidado_se_imprime_con_cantidad_y_kilos(self):
        reparto = self.reparto_con(self.pedido)
        respuesta = self.client.get(reverse('distribucion_consolidado', args=[reparto.id]))
        contenido = respuesta.content.decode('utf-8')
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Consolidado de Artículos", contenido)
        self.assertIn("Kgs", contenido)
        self.assertIn("YOGUR X 900", contenido.upper())

    def test_un_reparto_de_otra_empresa_no_se_puede_abrir(self):
        otra = Empresa.objects.create(nombre="Otra", cuit="30222222229")
        otra_suc = Sucursal.objects.create(empresa=otra, nombre="Suc", punto=1)
        ajeno = crear_reparto(otra.id, otra_suc.id, self.usuario)
        respuesta = self.client.get(
            reverse('distribucion_reparto_detalle', args=[ajeno.id]))
        self.assertEqual(respuesta.status_code, 404)
