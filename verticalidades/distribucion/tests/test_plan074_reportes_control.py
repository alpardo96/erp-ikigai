"""Reporte de devoluciones e integridad de numeración (Plan 074, fase 8).

Los dos reportes de CONTROL del módulo:

- **Devoluciones** (§7.10): *"por período, motivo, momento, repartidor, cliente y producto:
  muestra si el problema es de crédito, de calidad, de carga o de un repartidor puntual."*
  La pregunta que responde no es cuánto sino POR QUÉ.
- **Correlativos** (§4.2): el control de integridad sólo es posible sobre los comprobantes
  que uno EMITE con numeración propia.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from contable.models import Cuenta, Ejercicio, ParametrosContables
from core.models import ContadorDocumento
from core.services.numeracion import auditar_correlativos
from verticalidades.distribucion.models import (DomicilioEntrega, MotivoDevolucion,
                                 NotaCreditoDistribucion, Personal, RecepcionDevolucion,
                                 Reparto, Vehiculo, ZonaReparto)
from verticalidades.distribucion.services.devoluciones import (cargar_items, confirmar_recepcion,
                                                crear_recepcion, emitir_nota_credito,
                                                marcar_no_entregada)
from verticalidades.distribucion.services.facturacion import facturar_pedido
from verticalidades.distribucion.services.pedidos import guardar_pedido
from verticalidades.distribucion.services.reparto import agregar_paradas, cerrar_reparto, crear_reparto
from verticalidades.distribucion.services.reporte_devoluciones import reporte
from empresas.models import Empresa, PuntoVenta, Sucursal
from facturacion.models import ClienteProveedor,  TipoComprobante
from verticalidades.distribucion.models import ExtensionDistribuidora
from productos.models import Producto, Rubro, StockSucursal


class BaseReportesTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Distribuidora Prueba", cuit="30111111118",
            tipo_actividad="DISTRIBUIDORA")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, nombre="Depósito Central", punto=1)
        PuntoVenta.objects.create(empresa=self.empresa, sucursal=self.sucursal, numero=4)
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa, inicio="2026-01-01", cierre="2026-12-31")
        self.usuario = User.objects.create_user(username="admin1", password="x", is_staff=True)

        TipoComprobante.objects.get_or_create(
            codigo='PRE', defaults={'detalle': "Comprobante Interno", 'signo': 1})
        TipoComprobante.objects.get_or_create(
            codigo='NCI', defaults={'detalle': "Nota de Crédito Interna", 'signo': -1})

        cta_caja = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.1", cuenta="CAJA", imputable=1)
        cta_cli = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.3", cuenta="DEUDORES", imputable=1)
        cta_vta = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="4.1.1", cuenta="VENTAS", imputable=1)
        ParametrosContables.objects.create(
            empresa=self.empresa, cta_clientes_default=cta_cli, cta_ventas=cta_vta,
            cta_caja_central=cta_caja, cta_caja_mostrador=cta_caja,
            metodo_contabilizacion_ventas=1)

        self.zona = ZonaReparto.objects.create(
            empresa=self.empresa, nombre="San Cayetano", orden=1)
        self.vehiculo = Vehiculo.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, patente="AB123CD",
            descripcion="Furgón", capacidad_kg=Decimal('5000.00'))
        self.juan = Personal.objects.create(
            empresa=self.empresa, nombre="Juan", es_repartidor=True)
        self.pedro = Personal.objects.create(
            empresa=self.empresa, nombre="Pedro", es_repartidor=True)

        self.cerrado = MotivoDevolucion.objects.create(
            empresa=self.empresa, codigo="CERRADO", descripcion="Negocio cerrado",
            momento=MotivoDevolucion.MOMENTO_EN_ENTREGA, sugiere_apto_reventa=True)
        self.roto = MotivoDevolucion.objects.create(
            empresa=self.empresa, codigo="ROTO", descripcion="Envase roto",
            momento=MotivoDevolucion.MOMENTO_EN_ENTREGA, sugiere_apto_reventa=False)

        rubro = Rubro.objects.create(empresa=self.empresa, detalle="LACTEOS",
                                     cta_ventas=cta_vta)
        self.yogur = Producto.objects.create(
            empresa=self.empresa, detalle="Yogur x 900",
            precio_total=Decimal('1000.00'), rubro=rubro)
        self.leche = Producto.objects.create(
            empresa=self.empresa, detalle="Leche entera",
            precio_total=Decimal('1000.00'), rubro=rubro)
        for producto in (self.yogur, self.leche):
            StockSucursal.objects.create(
                producto=producto, sucursal=self.sucursal,
                stock_inicial=Decimal('99999.00'), cantidad=Decimal('99999.00'))

    # ------------------------------------------------------------------ helpers
    def crear_cliente(self, nombre):
        cliente = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social=nombre, tipo_entidad=1,
            domicilio="Belgrano 100", condicion_iva="CONSUMIDOR FINAL",
            limite=Decimal('1000000.00'))
        ExtensionDistribuidora.objects.create(
            cliente=cliente, coeficiente_mayorista=Decimal('1.0000'))
        DomicilioEntrega.objects.create(
            empresa=self.empresa, cliente=cliente, nombre="Casa Central",
            domicilio="Belgrano 100", zona=self.zona, es_principal=True)
        return cliente

    def devolver(self, nombre_cliente, producto, cantidad, motivo, repartidor=None,
                 con_nc=True):
        """Circuito completo hasta la devolución: pedido, reparto, no entrega y recepción."""
        cliente = self.crear_cliente(nombre_cliente)
        pedido = guardar_pedido(
            empresa_id=self.empresa.id, sucursal_id=self.sucursal.id,
            cliente=cliente, usuario=self.usuario, condic_destino=2,
            items=[{'producto_id': producto.id, 'cantidad': 10,
                    'precio_unitario': 1000.0, 'total': 10000.0, 'descuento': 0}])
        facturar_pedido(pedido, self.usuario)
        pedido.refresh_from_db()

        reparto = crear_reparto(
            self.empresa.id, self.sucursal.id, self.usuario,
            vehiculo=self.vehiculo, zona=self.zona,
            responsables=[repartidor or self.juan])
        agregar_paradas(reparto, [pedido])
        cerrar_reparto(reparto, self.usuario)
        reparto.refresh_from_db()

        parada = reparto.paradas.get()
        marcar_no_entregada(parada, "No estaba")
        recepcion = crear_recepcion(parada, self.usuario)
        item = parada.venta.items.first()
        cargar_items(recepcion, {item.id: cantidad}, {str(item.id): motivo.id})
        confirmar_recepcion(recepcion, self.usuario)
        if con_nc:
            emitir_nota_credito(recepcion, self.usuario)
        return reparto, recepcion


class ElReporteRespondePorQueTestCase(BaseReportesTestCase):
    def test_el_corte_por_motivo_muestra_la_concentracion(self):
        """«Muestra si el problema es de crédito, de calidad, de carga...»"""
        self.devolver("Cliente Uno", self.yogur, 6, self.cerrado)
        self.devolver("Cliente Dos", self.leche, 2, self.roto)

        datos = reporte(self.empresa.id)
        por_motivo = {f['entidad'].codigo: f for f in datos['por_motivo']}

        self.assertEqual(por_motivo['CERRADO']['importe'], Decimal('6000.00'))
        self.assertEqual(por_motivo['ROTO']['importe'], Decimal('2000.00'))
        self.assertEqual(por_motivo['CERRADO']['porcentaje'], Decimal('75.00'))

    def test_los_cortes_vienen_de_mayor_a_menor(self):
        """El reporte tiene que empezar por lo que más pesa."""
        self.devolver("Cliente Uno", self.yogur, 2, self.cerrado)
        self.devolver("Cliente Dos", self.leche, 7, self.roto)

        datos = reporte(self.empresa.id)
        self.assertEqual(datos['por_motivo'][0]['entidad'].codigo, 'ROTO')

    def test_el_corte_por_repartidor_sale_de_los_responsables_del_reparto(self):
        """`entregado_por` es opcional: con un solo responsable, la devolución es suya."""
        self.devolver("Cliente Uno", self.yogur, 5, self.cerrado, repartidor=self.juan)
        self.devolver("Cliente Dos", self.leche, 3, self.cerrado, repartidor=self.pedro)

        datos = reporte(self.empresa.id)
        por_repartidor = {f['entidad'].nombre: f for f in datos['por_repartidor']}
        self.assertEqual(por_repartidor['JUAN']['importe'], Decimal('5000.00'))
        self.assertEqual(por_repartidor['PEDRO']['importe'], Decimal('3000.00'))

    def test_con_varios_responsables_no_se_le_atribuye_a_ninguno(self):
        """Repartir la culpa por partes iguales sería inventar un dato."""
        cliente = self.crear_cliente("Cliente Uno")
        pedido = guardar_pedido(
            empresa_id=self.empresa.id, sucursal_id=self.sucursal.id,
            cliente=cliente, usuario=self.usuario, condic_destino=2,
            items=[{'producto_id': self.yogur.id, 'cantidad': 10,
                    'precio_unitario': 1000.0, 'total': 10000.0, 'descuento': 0}])
        facturar_pedido(pedido, self.usuario)
        pedido.refresh_from_db()

        reparto = crear_reparto(
            self.empresa.id, self.sucursal.id, self.usuario,
            vehiculo=self.vehiculo, responsables=[self.juan, self.pedro])
        agregar_paradas(reparto, [pedido])
        cerrar_reparto(reparto, self.usuario)
        parada = reparto.paradas.get()
        marcar_no_entregada(parada, "No estaba")
        recepcion = crear_recepcion(parada, self.usuario)
        item = parada.venta.items.first()
        cargar_items(recepcion, {item.id: 4}, {str(item.id): self.cerrado.id})
        confirmar_recepcion(recepcion, self.usuario)

        datos = reporte(self.empresa.id)
        self.assertEqual(len(datos['por_repartidor']), 1)
        self.assertIsNone(datos['por_repartidor'][0]['entidad'])

    def test_el_corte_por_producto_señala_al_articulo(self):
        self.devolver("Cliente Uno", self.yogur, 3, self.cerrado)
        self.devolver("Cliente Dos", self.yogur, 4, self.roto)
        self.devolver("Cliente Tres", self.leche, 1, self.cerrado)

        datos = reporte(self.empresa.id)
        self.assertEqual(datos['por_producto'][0]['entidad'].id, self.yogur.id)
        self.assertEqual(datos['por_producto'][0]['importe'], Decimal('7000.00'))

    def test_lo_no_apto_para_reventa_se_mide_aparte(self):
        """Lo que volvió roto es pérdida, no una devolución más."""
        self.devolver("Cliente Uno", self.yogur, 6, self.cerrado)
        self.devolver("Cliente Dos", self.leche, 2, self.roto)

        datos = reporte(self.empresa.id)
        self.assertEqual(datos['total_importe'], Decimal('8000.00'))
        self.assertEqual(datos['total_no_apto'], Decimal('2000.00'))
        self.assertEqual(datos['porcentaje_no_apto'], Decimal('25.00'))


class LosFiltrosTestCase(BaseReportesTestCase):
    def test_por_motivo(self):
        self.devolver("Cliente Uno", self.yogur, 6, self.cerrado)
        self.devolver("Cliente Dos", self.leche, 2, self.roto)

        datos = reporte(self.empresa.id, motivo_id=self.roto.id)
        self.assertEqual(datos['total_importe'], Decimal('2000.00'))

    def test_por_repartidor(self):
        self.devolver("Cliente Uno", self.yogur, 5, self.cerrado, repartidor=self.juan)
        self.devolver("Cliente Dos", self.leche, 3, self.cerrado, repartidor=self.pedro)

        datos = reporte(self.empresa.id, repartidor_id=self.pedro.id)
        self.assertEqual(datos['total_importe'], Decimal('3000.00'))

    def test_por_producto(self):
        self.devolver("Cliente Uno", self.yogur, 5, self.cerrado)
        self.devolver("Cliente Dos", self.leche, 3, self.cerrado)

        datos = reporte(self.empresa.id, producto_id=self.leche.id)
        self.assertEqual(datos['total_importe'], Decimal('3000.00'))

    def test_solo_lo_no_apto(self):
        self.devolver("Cliente Uno", self.yogur, 6, self.cerrado)
        self.devolver("Cliente Dos", self.leche, 2, self.roto)

        datos = reporte(self.empresa.id, solo_no_apto=True)
        self.assertEqual(datos['total_importe'], Decimal('2000.00'))

    def test_por_periodo(self):
        import datetime

        _, recepcion = self.devolver("Cliente Uno", self.yogur, 5, self.cerrado)
        RecepcionDevolucion.objects.filter(pk=recepcion.pk).update(
            fecha=datetime.date(2026, 1, 15))

        self.assertEqual(
            reporte(self.empresa.id, desde=datetime.date(2026, 2, 1))['total_importe'],
            Decimal('0.00'))
        self.assertEqual(
            reporte(self.empresa.id, desde=datetime.date(2026, 1, 1),
                    hasta=datetime.date(2026, 1, 31))['total_importe'],
            Decimal('5000.00'))

    def test_una_recepcion_anulada_no_cuenta(self):
        """No devolvió nada: contarla inflaría todos los cortes."""
        _, recepcion = self.devolver("Cliente Uno", self.yogur, 5, self.cerrado)
        RecepcionDevolucion.objects.filter(pk=recepcion.pk).update(
            estado=RecepcionDevolucion.ANULADA)

        self.assertEqual(reporte(self.empresa.id)['total_importe'], Decimal('0.00'))

    def test_el_reporte_esta_acotado_a_la_empresa(self):
        self.devolver("Cliente Uno", self.yogur, 5, self.cerrado)
        otra = Empresa.objects.create(nombre="Ajena", cuit="30222222229")
        self.assertEqual(reporte(otra.id)['total_importe'], Decimal('0.00'))


class LasAnulacionesPreCargaVanAparteTestCase(BaseReportesTestCase):
    """La mercadería nunca salió: mezclarla sería contarla como «vuelto del reparto»."""

    def test_no_se_suman_al_total_devuelto(self):
        _, recepcion = self.devolver("Cliente Uno", self.yogur, 5, self.cerrado)
        satelite = NotaCreditoDistribucion.objects.get(recepcion=recepcion)
        satelite.momento = NotaCreditoDistribucion.PRE_CARGA
        satelite.save(update_fields=['momento'])

        datos = reporte(self.empresa.id)
        # Lo devuelto sigue siendo lo que la recepción contó.
        self.assertEqual(datos['total_importe'], Decimal('5000.00'))
        # Y la NC aparece en su propia lista, con su propio total.
        self.assertEqual(len(datos['pre_carga']), 1)
        self.assertEqual(datos['total_pre_carga'], Decimal('5000.00'))

    def test_sin_anulaciones_la_lista_viene_vacia(self):
        self.devolver("Cliente Uno", self.yogur, 5, self.cerrado)
        self.assertEqual(reporte(self.empresa.id)['pre_carga'], [])


class LaIntegridadDeNumeracionTestCase(BaseReportesTestCase):
    """Sólo se puede auditar lo que uno EMITE con numeración propia (§4.2)."""

    def test_el_reparto_y_la_recepcion_entran_en_la_auditoria(self):
        """Eran los dos documentos del módulo que faltaban."""
        self.devolver("Cliente Uno", self.yogur, 5, self.cerrado)

        tipos = {f['tipo'] for f in auditar_correlativos(empresa_id=self.empresa.id)}
        self.assertIn(ContadorDocumento.REPARTO, tipos)
        self.assertIn(ContadorDocumento.RECEPCION_DEVOLUCION, tipos)

    def test_una_serie_sin_huecos_da_completa(self):
        self.devolver("Cliente Uno", self.yogur, 5, self.cerrado)
        self.devolver("Cliente Dos", self.leche, 3, self.cerrado)

        filas = {f['tipo']: f for f in auditar_correlativos(empresa_id=self.empresa.id)}
        reparto = filas[ContadorDocumento.REPARTO]
        self.assertEqual(reparto['cantidad'], 2)
        self.assertTrue(reparto['ok'], reparto)

    def test_un_hueco_se_detecta(self):
        """Un número consumido que no llegó a ningún documento vigente."""
        for _ in range(3):
            crear_reparto(self.empresa.id, self.sucursal.id, self.usuario)
        # El del medio desaparece: el contador siguió en 3 y el 2 quedó sin documento.
        Reparto.objects.filter(empresa=self.empresa, numero=2).delete()

        filas = {f['tipo']: f for f in auditar_correlativos(empresa_id=self.empresa.id)}
        reparto = filas[ContadorDocumento.REPARTO]
        self.assertFalse(reparto['ok'])
        self.assertEqual(reparto['faltantes'], [2])


class LasVistasTestCase(BaseReportesTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.usuario)
        sesion = self.client.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion['ejercicio_id'] = self.ejercicio.id
        sesion.save()

    def test_el_reporte_de_devoluciones_responde(self):
        self.devolver("Cliente Uno", self.yogur, 5, self.roto)
        respuesta = self.client.get(reverse('distribucion_reporte_devoluciones'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "ROTO")
        self.assertContains(respuesta, "CLIENTE UNO")

    def test_el_reporte_acepta_los_filtros_por_querystring(self):
        self.devolver("Cliente Uno", self.yogur, 6, self.cerrado)
        self.devolver("Cliente Dos", self.leche, 2, self.roto)

        respuesta = self.client.get(reverse('distribucion_reporte_devoluciones'),
                                    {'motivo': self.roto.id})
        self.assertEqual(respuesta.context['datos']['total_importe'], Decimal('2000.00'))

    def test_la_pantalla_de_correlativos_responde(self):
        self.devolver("Cliente Uno", self.yogur, 5, self.cerrado)
        respuesta = self.client.get(reverse('distribucion_correlativos'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Reparto / Hoja de Ruta")
        self.assertContains(respuesta, "Recepción de Devoluciones")

    def test_correlativos_solo_muestra_las_series_del_modulo(self):
        """Las de compras tienen su propia pantalla: acá sólo lo que emite Distribución."""
        self.devolver("Cliente Uno", self.yogur, 5, self.cerrado)
        respuesta = self.client.get(reverse('distribucion_correlativos'))
        tipos = {f['tipo'] for f in respuesta.context['filas']}
        self.assertNotIn(ContadorDocumento.ORDEN_COMPRA, tipos)
