"""Entrega, devoluciones y notas de crédito (Plan 074, fase 6).

El comprobante ya está emitido cuando el camión sale, así que todo lo que no se entrega
llega con la factura hecha. Estas pruebas fijan la regla que ordena el circuito:
PRIMERO SE CUENTA, DESPUÉS SE ACREDITA.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from contable.models import Cuenta, Ejercicio, ParametrosContables
from verticalidades.distribucion.models import (DomicilioEntrega, MotivoDevolucion,
                                 NotaCreditoDistribucion, Personal,
                                 RecepcionDevolucion, RecepcionDevolucionItem, Reparto,
                                 RepartoParada, Vehiculo, ZonaReparto)
from verticalidades.distribucion.services.devoluciones import (cargar_items, conciliacion,
                                                confirmar_recepcion, crear_recepcion,
                                                emitir_nota_credito, marcar_entregada,
                                                marcar_no_entregada, paradas_por_recibir)
from verticalidades.distribucion.services.facturacion import facturar_pedido
from verticalidades.distribucion.services.pedidos import guardar_pedido
from verticalidades.distribucion.services.reparto import agregar_paradas, cerrar_reparto, crear_reparto
from empresas.models import Empresa, PuntoVenta, Sucursal
from facturacion.models import ClienteProveedor,  TipoComprobante
from verticalidades.distribucion.models import ExtensionDistribuidora
from productos.models import Producto, Rubro, StockSucursal
from productos.services.stock_service import recalcular_stock


class BaseDevolucionesTestCase(TestCase):
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
        # Pueden venir ya sembrados por una migración de datos.
        TipoComprobante.objects.get_or_create(
            codigo='PRE', defaults={'detalle': "Comprobante Interno", 'signo': 1})
        TipoComprobante.objects.get_or_create(
            codigo='NCI', defaults={'detalle': "Nota de Crédito Interna", 'signo': -1})

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
            descripcion="Furgón", capacidad_kg=Decimal('5000.00'))
        self.juan = Personal.objects.create(
            empresa=self.empresa, nombre="Juan", es_repartidor=True)

        rubro = Rubro.objects.create(empresa=self.empresa, detalle="LACTEOS",
                                     cta_ventas=cta_vta)
        self.producto = Producto.objects.create(
            empresa=self.empresa, detalle="Yogur x 900", precio_total=Decimal('1000.00'),
            codigo_anterior="3002", peso_unitario_kg=Decimal('2.000'), rubro=rubro)
        StockSucursal.objects.create(
            producto=self.producto, sucursal=self.sucursal,
            stock_inicial=Decimal('5000.00'), cantidad=Decimal('5000.00'))

        # Dos motivos con criterio opuesto sobre el reingreso al stock vendible.
        self.cerrado = MotivoDevolucion.objects.create(
            empresa=self.empresa, codigo="CERRADO", descripcion="Negocio cerrado",
            momento=MotivoDevolucion.MOMENTO_EN_ENTREGA, sugiere_apto_reventa=True)
        self.roto = MotivoDevolucion.objects.create(
            empresa=self.empresa, codigo="ROTO", descripcion="Envase roto",
            momento=MotivoDevolucion.MOMENTO_EN_ENTREGA, sugiere_apto_reventa=False)
        # No debe ofrecerse en la recepción: aplica antes de cargar el vehículo.
        self.sin_stock = MotivoDevolucion.objects.create(
            empresa=self.empresa, codigo="SIN_STOCK", descripcion="Faltante en depósito",
            momento=MotivoDevolucion.MOMENTO_PRE_CARGA)

    # ------------------------------------------------------------------ helpers
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

    def pedido_facturado(self, nombre, cantidad=10):
        cliente = self.crear_cliente(nombre)
        pedido = guardar_pedido(
            empresa_id=self.empresa.id, sucursal_id=self.sucursal.id,
            cliente=cliente, usuario=self.usuario, condic_destino=2,
            items=[{'producto_id': self.producto.id, 'cantidad': cantidad,
                    'precio_unitario': 1000.0, 'total': 1000.0 * cantidad,
                    'descuento': 0}])
        facturar_pedido(pedido, self.usuario)
        pedido.refresh_from_db()
        return pedido

    def reparto_cerrado_con(self, *pedidos):
        reparto = crear_reparto(
            self.empresa.id, self.sucursal.id, self.usuario,
            vehiculo=self.vehiculo, zona=self.zona, responsables=[self.juan])
        agregar_paradas(reparto, list(pedidos))
        cerrar_reparto(reparto, self.usuario)
        reparto.refresh_from_db()
        return reparto

    def parada_no_entregada(self, nombre="Cliente Uno", cantidad=10):
        pedido = self.pedido_facturado(nombre, cantidad=cantidad)
        reparto = self.reparto_cerrado_con(pedido)
        parada = reparto.paradas.get()
        marcar_no_entregada(parada, "El local estaba cerrado")
        return reparto, parada

    def item_de(self, parada):
        return parada.venta.items.first()


class EstadoDeEntregaTestCase(BaseDevolucionesTestCase):
    def test_la_parada_nace_pendiente(self):
        """Mientras nadie diga lo contrario, la entrega no está resuelta."""
        pedido = self.pedido_facturado("Cliente Uno")
        reparto = self.reparto_cerrado_con(pedido)
        self.assertEqual(reparto.paradas.get().estado_entrega, RepartoParada.PENDIENTE)

    def test_marcar_entregada_cierra_la_parada(self):
        pedido = self.pedido_facturado("Cliente Uno")
        reparto = self.reparto_cerrado_con(pedido)
        parada = reparto.paradas.get()

        marcar_entregada(parada, self.usuario)
        parada.refresh_from_db()
        self.assertEqual(parada.estado_entrega, RepartoParada.ENTREGADA)

    def test_marcar_no_entregada_guarda_la_observacion_del_repartidor(self):
        """El motivo estandariza la estadística; la observación captura lo que sólo él sabe."""
        _, parada = self.parada_no_entregada()
        parada.refresh_from_db()
        self.assertEqual(parada.estado_entrega, RepartoParada.NO_ENTREGADA)
        self.assertEqual(parada.observacion_repartidor, "El local estaba cerrado")

    def test_una_parada_entregada_no_figura_para_recibir(self):
        pedido = self.pedido_facturado("Cliente Uno")
        reparto = self.reparto_cerrado_con(pedido)
        marcar_entregada(reparto.paradas.get(), self.usuario)
        self.assertEqual(list(paradas_por_recibir(reparto)), [])


class RecepcionDeDevolucionesTestCase(BaseDevolucionesTestCase):
    def test_la_recepcion_lleva_numero_correlativo_propio(self):
        """Sólo lo que se emite numerado puede auditarse."""
        _, primera = self.parada_no_entregada("Cliente Uno")
        _, segunda = self.parada_no_entregada("Cliente Dos")

        r1 = crear_recepcion(primera, self.usuario)
        r2 = crear_recepcion(segunda, self.usuario)
        self.assertEqual([r1.numero, r2.numero], [1, 2])
        # Igual que el PRE y el Reparto, el punto de la serie interna es la sucursal.
        self.assertEqual(r1.numero_formateado, f"{self.sucursal.id:04d}-00000001")

    def test_se_emite_una_recepcion_por_pedido_devuelto(self):
        """Abrir dos veces la misma parada devuelve la misma recepción, no una nueva."""
        _, parada = self.parada_no_entregada()
        primera = crear_recepcion(parada, self.usuario)
        segunda = crear_recepcion(parada, self.usuario)
        self.assertEqual(primera.id, segunda.id)
        self.assertEqual(RecepcionDevolucion.objects.count(), 1)

    def test_la_recepcion_identifica_reparto_pedido_y_comprobante(self):
        """Los tres datos que el documento tiene que imprimir, en un solo salto."""
        reparto, parada = self.parada_no_entregada()
        recepcion = crear_recepcion(parada, self.usuario)

        self.assertEqual(recepcion.reparto_id, reparto.id)
        self.assertEqual(recepcion.parada.pedido_id, parada.pedido_id)
        self.assertEqual(recepcion.parada.venta_id, parada.venta_id)

    def test_no_se_puede_devolver_mas_de_lo_entregado(self):
        _, parada = self.parada_no_entregada(cantidad=10)
        recepcion = crear_recepcion(parada, self.usuario)
        item = self.item_de(parada)

        with self.assertRaises(ValueError):
            cargar_items(recepcion, {item.id: 11}, {str(item.id): self.cerrado.id})

    def test_no_se_puede_devolver_una_cantidad_negativa(self):
        _, parada = self.parada_no_entregada()
        recepcion = crear_recepcion(parada, self.usuario)
        item = self.item_de(parada)

        with self.assertRaises(ValueError):
            cargar_items(recepcion, {item.id: -1}, {str(item.id): self.cerrado.id})

    def test_el_motivo_es_obligatorio(self):
        _, parada = self.parada_no_entregada()
        recepcion = crear_recepcion(parada, self.usuario)
        item = self.item_de(parada)

        with self.assertRaises(ValueError):
            cargar_items(recepcion, {item.id: 3}, {})

    def test_cargar_cero_borra_el_renglon(self):
        """El depósito contó y de ese artículo no volvió nada."""
        _, parada = self.parada_no_entregada()
        recepcion = crear_recepcion(parada, self.usuario)
        item = self.item_de(parada)

        cargar_items(recepcion, {item.id: 4}, {str(item.id): self.cerrado.id})
        self.assertEqual(recepcion.items.count(), 1)

        cargar_items(recepcion, {item.id: 0}, {str(item.id): self.cerrado.id})
        self.assertEqual(recepcion.items.count(), 0)

    def test_el_motivo_decide_si_la_mercaderia_vuelve_al_stock_vendible(self):
        """No se deja librado al criterio de quien carga."""
        _, parada = self.parada_no_entregada()
        recepcion = crear_recepcion(parada, self.usuario)
        item = self.item_de(parada)

        cargar_items(recepcion, {item.id: 2}, {str(item.id): self.roto.id})
        self.assertFalse(recepcion.items.get().apto_reventa)

        cargar_items(recepcion, {item.id: 2}, {str(item.id): self.cerrado.id})
        self.assertTrue(recepcion.items.get().apto_reventa)

    def test_el_total_devuelto_usa_el_precio_al_que_se_facturo(self):
        """La NC tiene que acreditar exactamente lo mismo que se cobró."""
        _, parada = self.parada_no_entregada(cantidad=10)
        recepcion = crear_recepcion(parada, self.usuario)
        item = self.item_de(parada)

        cargar_items(recepcion, {item.id: 4}, {str(item.id): self.cerrado.id})
        self.assertEqual(recepcion.total_devuelto, Decimal('4000.00'))

    def test_una_recepcion_confirmada_no_admite_cambios_en_el_conteo(self):
        _, parada = self.parada_no_entregada()
        recepcion = crear_recepcion(parada, self.usuario)
        item = self.item_de(parada)
        cargar_items(recepcion, {item.id: 3}, {str(item.id): self.cerrado.id})
        confirmar_recepcion(recepcion, self.usuario)

        with self.assertRaises(ValueError):
            cargar_items(recepcion, {item.id: 5}, {str(item.id): self.cerrado.id})

    def test_no_se_confirma_una_recepcion_vacia(self):
        _, parada = self.parada_no_entregada()
        recepcion = crear_recepcion(parada, self.usuario)
        with self.assertRaises(ValueError):
            confirmar_recepcion(recepcion, self.usuario)


class PrimeroSeCuentaDespuesSeAcreditaTestCase(BaseDevolucionesTestCase):
    """La regla que ordena todo el circuito."""

    def test_no_se_acredita_sin_confirmar_la_recepcion(self):
        """Si no, se acreditaría mercadería que puede no haber vuelto."""
        _, parada = self.parada_no_entregada()
        recepcion = crear_recepcion(parada, self.usuario)
        item = self.item_de(parada)
        cargar_items(recepcion, {item.id: 3}, {str(item.id): self.cerrado.id})

        with self.assertRaises(ValueError):
            emitir_nota_credito(recepcion, self.usuario)

    def test_la_nc_acredita_exactamente_lo_que_el_deposito_conto(self):
        _, parada = self.parada_no_entregada(cantidad=10)
        recepcion = crear_recepcion(parada, self.usuario)
        item = self.item_de(parada)
        cargar_items(recepcion, {item.id: 4}, {str(item.id): self.cerrado.id})
        confirmar_recepcion(recepcion, self.usuario)

        nota = emitir_nota_credito(recepcion, self.usuario)
        self.assertEqual(nota.tipo.codigo, 'NCI')
        self.assertEqual(nota.items.get().cantidad, Decimal('4.00'))
        self.assertEqual(Decimal(str(nota.total)), Decimal('4000.00'))

    def test_la_nc_hereda_el_condic_del_comprobante_acreditado(self):
        """El asiento hereda el condic del comprobante: nunca un valor calculado."""
        _, parada = self.parada_no_entregada()
        recepcion = crear_recepcion(parada, self.usuario)
        item = self.item_de(parada)
        cargar_items(recepcion, {item.id: 2}, {str(item.id): self.cerrado.id})
        confirmar_recepcion(recepcion, self.usuario)

        nota = emitir_nota_credito(recepcion, self.usuario)
        self.assertEqual(nota.condic, parada.venta.condic)
        self.assertEqual(nota.condic, 2)

    def test_la_nci_lleva_serie_propia_numerada_por_el_sistema(self):
        """PRE y NCI son series separadas: el número lo da el contador, no ARCA."""
        _, primera = self.parada_no_entregada("Cliente Uno")
        _, segunda = self.parada_no_entregada("Cliente Dos")

        numeros = []
        for parada in (primera, segunda):
            recepcion = crear_recepcion(parada, self.usuario)
            item = self.item_de(parada)
            cargar_items(recepcion, {item.id: 1}, {str(item.id): self.cerrado.id})
            confirmar_recepcion(recepcion, self.usuario)
            numeros.append(emitir_nota_credito(recepcion, self.usuario).numero)

        self.assertEqual(numeros, [1, 2])

    def test_emitir_dos_veces_devuelve_la_misma_nc(self):
        """Un doble clic no puede acreditarle dos veces al cliente."""
        _, parada = self.parada_no_entregada()
        recepcion = crear_recepcion(parada, self.usuario)
        item = self.item_de(parada)
        cargar_items(recepcion, {item.id: 2}, {str(item.id): self.cerrado.id})
        confirmar_recepcion(recepcion, self.usuario)

        primera = emitir_nota_credito(recepcion, self.usuario)
        segunda = emitir_nota_credito(recepcion, self.usuario)
        self.assertEqual(primera.pk, segunda.pk)

    def test_la_nc_deja_su_contexto_operativo_en_el_satelite(self):
        """Motivo, observación, parada y recepción, sin tocar el modelo compartido Venta."""
        _, parada = self.parada_no_entregada()
        recepcion = crear_recepcion(parada, self.usuario)
        item = self.item_de(parada)
        cargar_items(recepcion, {item.id: 2}, {str(item.id): self.roto.id})
        confirmar_recepcion(recepcion, self.usuario)

        nota = emitir_nota_credito(recepcion, self.usuario, observacion="Se cayó el cajón")
        satelite = NotaCreditoDistribucion.objects.get(nota_credito=nota)
        self.assertEqual(satelite.motivo_id, self.roto.id)
        self.assertEqual(satelite.observacion, "Se cayó el cajón")
        self.assertEqual(satelite.parada_id, parada.id)
        self.assertEqual(satelite.recepcion_id, recepcion.id)
        self.assertEqual(satelite.venta_origen_id, parada.venta_id)
        self.assertEqual(satelite.momento, NotaCreditoDistribucion.EN_ENTREGA)

    def test_el_stock_lo_devuelve_la_nota_de_credito(self):
        """`stock_service` deriva el stock de los comprobantes: la NC invierte por signo -1.

        Si la recepción también moviera stock, se contaría dos veces.
        """
        _, parada = self.parada_no_entregada(cantidad=10)
        despues_de_facturar = recalcular_stock(self.producto.id, self.sucursal.id)

        recepcion = crear_recepcion(parada, self.usuario)
        item = self.item_de(parada)
        cargar_items(recepcion, {item.id: 4}, {str(item.id): self.cerrado.id})
        confirmar_recepcion(recepcion, self.usuario)
        self.assertEqual(recalcular_stock(self.producto.id, self.sucursal.id),
                         despues_de_facturar,
                         "La recepción es el control físico: no debe mover el inventario.")

        emitir_nota_credito(recepcion, self.usuario)
        self.assertEqual(recalcular_stock(self.producto.id, self.sucursal.id),
                         despues_de_facturar + Decimal('4.00'))


class ConciliacionTestCase(BaseDevolucionesTestCase):
    """El control de fondo: lo acreditado al cliente contra lo recibido en el depósito."""

    def test_una_devolucion_completa_concilia(self):
        _, parada = self.parada_no_entregada(cantidad=10)
        recepcion = crear_recepcion(parada, self.usuario)
        item = self.item_de(parada)
        cargar_items(recepcion, {item.id: 10}, {str(item.id): self.cerrado.id})
        confirmar_recepcion(recepcion, self.usuario)
        emitir_nota_credito(recepcion, self.usuario)

        datos = conciliacion(parada.reparto)
        fila = datos['filas'][0]
        self.assertTrue(fila['concilia'])
        self.assertEqual(fila['diferencia'], Decimal('0.00'))
        self.assertEqual(datos['con_descalce'], [])
        self.assertEqual(datos['total_recibido'], Decimal('10000.00'))
        self.assertEqual(datos['total_acreditado'], Decimal('10000.00'))

    def test_una_recepcion_sin_nc_queda_marcada(self):
        """Volvió al depósito pero todavía no se le acreditó al cliente."""
        _, parada = self.parada_no_entregada()
        recepcion = crear_recepcion(parada, self.usuario)
        item = self.item_de(parada)
        cargar_items(recepcion, {item.id: 3}, {str(item.id): self.cerrado.id})
        confirmar_recepcion(recepcion, self.usuario)

        fila = conciliacion(parada.reparto)['filas'][0]
        self.assertTrue(fila['sin_nc'])
        self.assertEqual(fila['acreditado'], Decimal('0.00'))

    def test_una_parada_no_entregada_sin_recepcion_queda_pendiente(self):
        """El cliente no recibió y nadie declaró la mercadería de vuelta."""
        reparto, parada = self.parada_no_entregada()
        datos = conciliacion(reparto)
        self.assertEqual([p.id for p in datos['pendientes_de_recibir']], [parada.id])

    def test_abierta_la_recepcion_la_parada_deja_de_estar_pendiente(self):
        reparto, parada = self.parada_no_entregada()
        crear_recepcion(parada, self.usuario)
        self.assertEqual(list(paradas_por_recibir(reparto)), [])


class VistasDeEntregaTestCase(BaseDevolucionesTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.usuario)
        sesion = self.client.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion.save()

    def test_no_se_rinde_la_entrega_de_un_reparto_todavia_armado(self):
        """Los saldos y el cobro mínimo recién se congelan al cerrar."""
        pedido = self.pedido_facturado("Cliente Uno")
        reparto = crear_reparto(self.empresa.id, self.sucursal.id, self.usuario)
        agregar_paradas(reparto, [pedido])

        respuesta = self.client.get(reverse('distribucion_entrega', args=[reparto.id]))
        self.assertRedirects(
            respuesta, reverse('distribucion_reparto_detalle', args=[reparto.id]))

    def test_la_pantalla_de_entrega_lista_las_paradas(self):
        pedido = self.pedido_facturado("Cliente Uno")
        reparto = self.reparto_cerrado_con(pedido)

        respuesta = self.client.get(reverse('distribucion_entrega', args=[reparto.id]))
        self.assertEqual(respuesta.status_code, 200)
        # `ClienteProveedor` guarda la razón social en mayúsculas.
        self.assertContains(respuesta, "CLIENTE UNO")

    def test_marcar_no_entregada_desde_la_pantalla(self):
        pedido = self.pedido_facturado("Cliente Uno")
        reparto = self.reparto_cerrado_con(pedido)
        parada = reparto.paradas.get()

        self.client.post(reverse('distribucion_entrega', args=[reparto.id]), {
            'accion': 'no_entregada', 'parada': parada.id,
            'observacion': "Estaba cerrado"})
        parada.refresh_from_db()
        self.assertEqual(parada.estado_entrega, RepartoParada.NO_ENTREGADA)

    def test_el_reparto_de_otra_empresa_no_se_ve(self):
        """Toda consulta queda acotada a la empresa de la sesión."""
        otra = Empresa.objects.create(nombre="Ajena", cuit="30222222229")
        sucursal = Sucursal.objects.create(empresa=otra, nombre="Única", punto=1)
        reparto = crear_reparto(otra.id, sucursal.id, self.usuario)

        respuesta = self.client.get(reverse('distribucion_entrega', args=[reparto.id]))
        self.assertEqual(respuesta.status_code, 404)

    def test_la_recepcion_se_abre_con_los_articulos_del_comprobante(self):
        _, parada = self.parada_no_entregada()
        respuesta = self.client.get(
            reverse('distribucion_recepcion', args=[parada.id]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "YOGUR X 900")

    def test_el_selector_no_ofrece_motivos_de_pre_carga(self):
        """Ese motivo aplica antes de cargar el vehículo, no en la entrega."""
        _, parada = self.parada_no_entregada()
        respuesta = self.client.get(
            reverse('distribucion_recepcion', args=[parada.id]))
        codigos = [m.codigo for m in respuesta.context['motivos']]
        self.assertIn("CERRADO", codigos)
        self.assertNotIn("SIN_STOCK", codigos)

    def test_circuito_completo_desde_la_pantalla(self):
        """Marcar, contar, confirmar y acreditar, tal como se opera."""
        _, parada = self.parada_no_entregada(cantidad=10)
        item = self.item_de(parada)
        url = reverse('distribucion_recepcion', args=[parada.id])

        self.client.post(url, {'accion': 'guardar',
                               f'cantidad_{item.id}': '4,00',
                               f'motivo_{item.id}': self.cerrado.id,
                               f'obs_{item.id}': "Dos cajones sin abrir"})
        recepcion = RecepcionDevolucion.objects.get(parada=parada)
        self.assertEqual(recepcion.items.get().cantidad, Decimal('4.00'))
        self.assertEqual(recepcion.items.get().observacion, "Dos cajones sin abrir")

        self.client.post(url, {'accion': 'confirmar'})
        recepcion.refresh_from_db()
        self.assertEqual(recepcion.estado, RecepcionDevolucion.CONFIRMADA)

        respuesta = self.client.post(url, {'accion': 'emitir_nc',
                                           'observacion': "Vuelve mañana"})
        self.assertRedirects(
            respuesta, reverse('distribucion_entrega', args=[parada.reparto_id]))
        recepcion.refresh_from_db()
        self.assertIsNotNone(recepcion.nota_credito_id)
        self.assertEqual(Decimal(str(recepcion.nota_credito.total)), Decimal('4000.00'))
