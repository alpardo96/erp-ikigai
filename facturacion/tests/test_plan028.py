"""Tests del circuito de abastecimiento — Plan 028 (OC → Recepción → Factura + interno)."""
import json
from decimal import Decimal
from datetime import date

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model

from empresas.models import Empresa, Sucursal
from productos.models import Producto, StockSucursal
from facturacion.models import (
    ClienteProveedor, TipoComprobante, OrdenCompra, OrdenCompraItem,
    Compra, CompraItem, CompraOCImputacion, Recepcion, RemitoInterno,
)
from core.models import ContadorDocumento
from core.services.numeracion import siguiente_numero, auditar_correlativos

User = get_user_model()


class Plan028Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u', password='x')
        self.emp = Empresa.objects.create(nombre="Test", cuit="20111111119")
        self.s1 = Sucursal.objects.create(empresa=self.emp, nombre="Central", punto=1)
        self.s2 = Sucursal.objects.create(empresa=self.emp, nombre="Sucursal B", punto=2)
        self.prov = ClienteProveedor.objects.create(razon_social="Prov", tipo_entidad=2, empresa=self.emp)
        self.tipo = TipoComprobante.objects.create(codigo="1", detalle="Factura A", signo=1)
        self.A = Producto.objects.create(detalle="Prod A", empresa=self.emp, alic_iva=Decimal('21'))

    def _stock(self, sucursal, prod=None):
        r = StockSucursal.objects.filter(producto=prod or self.A, sucursal=sucursal).first()
        return r.cantidad if r else Decimal('0')

    def _oc(self, cantidad, precio=100, sucursal=None):
        suc = sucursal or self.s1
        oc = OrdenCompra.objects.create(
            empresa=self.emp, sucursal=suc, punto=suc.punto,
            fecha=date(2026, 7, 9), proveedor=self.prov, carga_costos=True, usuario=self.user,
            estado=OrdenCompra.CONFIRMADA, creado_por=self.user, modificado_por=self.user,
            numero=siguiente_numero(self.emp.id, suc.punto, ContadorDocumento.ORDEN_COMPRA),
        )
        li = OrdenCompraItem.objects.create(
            orden=oc, producto=self.A, cantidad=Decimal(str(cantidad)),
            cantidad_original=Decimal(str(cantidad)), precio_unitario=Decimal(str(precio)))
        return oc, li

    def _factura_oc(self, numero, cantidad, fuentes, decision_post=None):
        """Crea una factura de bienes en circuito OC y procesa el circuito. Devuelve la compra."""
        from facturacion.views import ComprasCargaView
        c = Compra(empresa=self.emp, sucursal=self.s1, tipo=self.tipo, punto=1, numero=numero,
                   proveedor=self.prov, fecha=date(2026, 7, 9), moneda='PES', cotizacion=1,
                   condic=1, usuario=self.user, gestion_stock_por_recepcion=True)
        c._no_contabilizar = True
        c.save()
        CompraItem.objects.create(compra=c, producto=self.A, cantidad=Decimal(str(cantidad)),
                                  precio_unitario=Decimal('100'), iva_alicuota=21,
                                  total=Decimal(str(cantidad)) * Decimal('100'))
        req = RequestFactory().post('/x', decision_post or {})
        req.user = self.user
        ComprasCargaView()._procesar_circuito_oc(
            req, c, [{'producto_id': self.A.id, 'cantidad': cantidad, 'oc_fuentes': fuentes}])
        return c


class NumeradorTests(Plan028Base):
    def test_series_independientes_por_punto_y_tipo(self):
        OC = ContadorDocumento.ORDEN_COMPRA
        IR = ContadorDocumento.INFORME_RECEPCION
        self.assertEqual([siguiente_numero(self.emp.id, 1, OC) for _ in range(3)], [1, 2, 3])
        self.assertEqual([siguiente_numero(self.emp.id, 2, OC) for _ in range(2)], [1, 2])
        self.assertEqual([siguiente_numero(self.emp.id, 1, IR) for _ in range(2)], [1, 2])


class RecepcionTests(Plan028Base):
    def test_recepcion_parcial_via_http_imputa_fifo_y_mueve_stock(self):
        oc, li = self._oc(10)
        self.client.force_login(self.user)
        s = self.client.session
        s['empresa_id'] = self.emp.id
        s['sucursal_id'] = self.s1.id
        s.save()
        self.client.get('/compras/recepciones/nueva/')
        self.client.post('/compras/recepciones/vincular-oc/', {'oc_ids': [oc.oc_id]})
        self.client.post('/compras/recepciones/item/0/editar/', {'cantidad_recibida': '6'})
        self.client.post('/compras/recepciones/nueva/',
                         {'fecha': '2026-07-09', 'sucursal': self.s1.id, 'proveedor': self.prov.codigo_id})
        li.refresh_from_db()
        self.assertEqual(li.cantidad_recibida, Decimal('6.00'))
        self.assertEqual(self._stock(self.s1), Decimal('6.00'))
        oc.refresh_from_db()
        self.assertEqual(oc.estado_recepcion, OrdenCompra.PARCIAL)


class FacturaOcTests(Plan028Base):
    def test_factura_sin_remito_genera_recepcion_y_mueve_stock(self):
        oc, li = self._oc(10)
        c = self._factura_oc(9001, 10, [{'oc_item_id': li.pk, 'pendiente_facturacion': 10.0}])
        li.refresh_from_db()
        self.assertEqual(li.cantidad_facturada, Decimal('10.00'))
        self.assertEqual(li.cantidad_recibida, Decimal('10.00'))
        self.assertEqual(Recepcion.objects.filter(generada_por_factura=c).count(), 1)
        self.assertEqual(self._stock(self.s1), Decimal('10.00'))
        oc.refresh_from_db()
        self.assertEqual(oc.estado, OrdenCompra.CERRADA)

    def test_factura_con_remito_previo_no_duplica_stock(self):
        from facturacion.models import RecepcionItem, RecepcionImputacion
        oc, li = self._oc(10)
        rec = Recepcion.objects.create(
            empresa=self.emp, sucursal=self.s1, punto=self.s1.punto, fecha=date(2026, 7, 9),
            origen=Recepcion.PROVEEDOR_REMITO, proveedor=self.prov, usuario=self.user,
            creado_por=self.user, modificado_por=self.user,
            numero=siguiente_numero(self.emp.id, self.s1.punto, ContadorDocumento.INFORME_RECEPCION))
        ri = RecepcionItem.objects.create(recepcion=rec, producto=self.A, cantidad_recibida=Decimal('10'))
        RecepcionImputacion.objects.create(recepcion_item=ri, orden_item=li, cantidad=Decimal('10'))
        li.cantidad_recibida = Decimal('10')
        li.save()
        self.assertEqual(self._stock(self.s1), Decimal('10.00'))
        c = self._factura_oc(9002, 10, [{'oc_item_id': li.pk, 'pendiente_facturacion': 10.0}])
        self.assertEqual(Recepcion.objects.filter(generada_por_factura=c).count(), 0)
        self.assertEqual(self._stock(self.s1), Decimal('10.00'))

    def test_baja_factura_oc_revierte_todo(self):
        from contable.services.contabilizacion import dar_de_baja_compra
        oc, li = self._oc(10)
        c = self._factura_oc(9003, 10, [{'oc_item_id': li.pk, 'pendiente_facturacion': 10.0}])
        self.assertEqual(self._stock(self.s1), Decimal('10.00'))
        dar_de_baja_compra(c)
        li.refresh_from_db()
        oc.refresh_from_db()
        self.assertEqual(self._stock(self.s1), Decimal('0.00'))
        self.assertEqual(li.cantidad_facturada, Decimal('0.00'))
        self.assertEqual(li.cantidad_recibida, Decimal('0.00'))
        self.assertEqual(oc.estado, OrdenCompra.CONFIRMADA)
        self.assertFalse(CompraOCImputacion.objects.filter(orden_item=li).exists())
        self.assertFalse(Compra.objects.filter(pk=c.compras_id).exists())

    def test_ajuste_diferencia_conserva_original(self):
        oc, li = self._oc(10)
        self._factura_oc(9004, 8, [{'oc_item_id': li.pk, 'pendiente_facturacion': 10.0}],
                         decision_post={f'oc_ajuste_{li.pk}': 'ajustar'})
        li.refresh_from_db()
        self.assertEqual(li.cantidad, Decimal('8.00'))            # ajustada
        self.assertEqual(li.cantidad_original, Decimal('10.00'))  # original conservada
        self.assertFalse(li.marcado_diferencia)


class TransferenciaInternaTests(Plan028Base):
    def test_transferencia_dos_pasos(self):
        self.client.force_login(self.user)
        s = self.client.session
        s['empresa_id'] = self.emp.id
        s['sucursal_id'] = self.s1.id
        s.save()
        self.client.get('/compras/remitos-internos/nuevo/')
        self.client.post('/compras/remitos-internos/item/agregar/', {'producto_id': self.A.id, 'cantidad': '10'})
        self.client.post('/compras/remitos-internos/nuevo/',
                         {'fecha': '2026-07-09', 'sucursal_origen': self.s1.id,
                          'sucursal_destino': self.s2.id, 'tipo': 'ENVIO'})
        ri = RemitoInterno.objects.get(empresa=self.emp)
        self.assertEqual(self._stock(self.s1), Decimal('-10.00'))
        self.assertEqual(self._stock(self.s2), Decimal('0.00'))
        self.assertEqual(ri.items.first().pendiente, Decimal('10.00'))
        s = self.client.session
        s['sucursal_id'] = self.s2.id
        s.save()
        self.client.get('/compras/recepcion-interna/nueva/')
        self.client.post('/compras/recepcion-interna/vincular/', {'ri_ids': [ri.ri_id]})
        self.client.post('/compras/recepcion-interna/nueva/', {'fecha': '2026-07-09', 'sucursal': self.s2.id})
        ri.refresh_from_db()
        self.assertEqual(self._stock(self.s2), Decimal('10.00'))
        self.assertEqual(ri.estado, RemitoInterno.RECEPCIONADO)


class AuditoriaCorrelativosTests(Plan028Base):
    def test_detecta_hueco(self):
        self._oc(5)          # numero 1
        oc3, _ = self._oc(5)  # numero 2 -> lo forzamos a 3 (hueco en el 2)
        oc3.numero = 3
        oc3.save(update_fields=['numero'])
        filas = auditar_correlativos(empresa_id=self.emp.id)
        oc_fila = [f for f in filas if f['tipo'] == ContadorDocumento.ORDEN_COMPRA and f['punto'] == 1][0]
        self.assertIn(2, oc_fila['faltantes'])
        self.assertFalse(oc_fila['ok'])


class BuscadorProductosStockTests(Plan028Base):
    def setUp(self):
        super().setUp()
        # Establecer existencias de prueba en ambas sucursales
        StockSucursal.objects.create(producto=self.A, sucursal=self.s1, cantidad=Decimal('15.00'))
        StockSucursal.objects.create(producto=self.A, sucursal=self.s2, cantidad=Decimal('5.00'))
        self.client.force_login(self.user)
        s = self.client.session
        s['empresa_id'] = self.emp.id
        s['sucursal_id'] = self.s1.id
        s.save()

    def test_buscador_modal_remito_interno_contexto_sucursales(self):
        resp = self.client.get(
            f'/compras/productos/buscar-modal/?sucursal_origen={self.s1.id}&sucursal_destino={self.s2.id}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['sucursal_origen_id'], str(self.s1.id))
        self.assertEqual(resp.context['sucursal_destino_id'], str(self.s2.id))
        self.assertEqual(resp.context['sucursal_origen_obj'], self.s1)
        self.assertEqual(resp.context['sucursal_destino_obj'], self.s2)

    def test_lista_productos_calcula_stock_origen_y_destino(self):
        resp = self.client.get(
            f'/compras/productos/buscar-lista/?sucursal_origen={self.s1.id}&sucursal_destino={self.s2.id}'
        )
        self.assertEqual(resp.status_code, 200)
        productos = resp.context['productos']
        prod_a = [p for p in productos if p.id == self.A.id][0]
        self.assertEqual(prod_a.stock_origen, Decimal('15.00'))
        self.assertEqual(prod_a.stock_destino, Decimal('5.00'))

    def test_lista_productos_modo_estandar_solo_sucursal_activa(self):
        resp = self.client.get('/compras/productos/buscar-lista/')
        self.assertEqual(resp.status_code, 200)
        productos = resp.context['productos']
        prod_a = [p for p in productos if p.id == self.A.id][0]
        self.assertEqual(prod_a.stock_origen, Decimal('15.00'))
        self.assertIsNone(prod_a.stock_destino)


class SubproductoRemitoInternoTests(Plan028Base):
    def setUp(self):
        super().setUp()
        from productos.models import Subproducto
        # Producto trazable y subproducto en sucursal Origen (s1)
        self.prod_trazable = Producto.objects.create(
            detalle="Arma Trazable 9mm", empresa=self.emp, alic_iva=Decimal('21'), subprod=True
        )
        self.subp = Subproducto.objects.create(
            empresa=self.emp, producto=self.prod_trazable, sucursal=self.s1,
            serie="SN998877", cuim="554433", feccpra=date(2026, 8, 1)
        )
        self.client.force_login(self.user)
        s = self.client.session
        s['empresa_id'] = self.emp.id
        s['sucursal_id'] = self.s1.id
        s.save()

    def test_ri_item_add_valida_serie_y_carga_subproducto(self):
        # 1. Sin serie -> error
        resp = self.client.post('/compras/remitos-internos/item/agregar/', {
            'producto_id': self.prod_trazable.id, 'cantidad': '1', 'serie': '', 'sucursal_origen': self.s1.id
        })
        self.assertIn('requiere ingresar el Número de Serie', resp.content.decode('utf-8'))

        # 2. Serie correcta -> éxito
        resp = self.client.post('/compras/remitos-internos/item/agregar/', {
            'producto_id': self.prod_trazable.id, 'cantidad': '1', 'serie': 'SN998877', 'sucursal_origen': self.s1.id
        })
        self.assertEqual(resp.status_code, 200)
        items = self.client.session['ri_items_temp']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['subproducto_id'], self.subp.subpro)
        self.assertEqual(items[0]['serie'], 'SN998877')
        self.assertEqual(items[0]['cuim'], 'CUIM554433')

    def test_circuito_completo_remito_y_recepcion_transfiere_subproducto_a_destino(self):
        from facturacion.models import RemitoInterno, RemitoInternoItem, Recepcion
        # 1. Cargar ítem en sesión
        self.client.post('/compras/remitos-internos/item/agregar/', {
            'producto_id': self.prod_trazable.id, 'cantidad': '1', 'serie': 'SN998877', 'sucursal_origen': self.s1.id
        })

        # 2. Emitir Remito Interno (s1 -> s2)
        resp_emitir = self.client.post('/compras/remitos-internos/nuevo/', {
            'fecha': '2026-08-16', 'sucursal_origen': self.s1.id, 'sucursal_destino': self.s2.id,
            'tipo': 'ENVIO', 'observaciones': 'Transferencia trazable'
        })
        self.assertEqual(resp_emitir.status_code, 302)
        ri = RemitoInterno.objects.get(empresa=self.emp)
        ri_item = ri.items.first()
        self.assertEqual(ri_item.subproducto_id, self.subp.subpro)
        self.assertEqual(ri_item.serie, 'SN998877')
        self.assertEqual(ri_item.cuim, 'CUIM554433')

        # 3. Descarga de PDF
        resp_pdf = self.client.get(f'/compras/remitos-internos/{ri.pk}/imprimir/')
        self.assertEqual(resp_pdf.status_code, 200)

        # 4. Recepción en Destino (s2)
        s = self.client.session
        s['sucursal_id'] = self.s2.id
        s.save()

        # Vincular remito en la recepción
        self.client.post('/compras/recepcion-interna/vincular/', {'ri_ids': [ri.ri_id]})
        reci_items = self.client.session['reci_items_temp']
        self.assertEqual(reci_items[0]['subproducto_id'], self.subp.subpro)
        self.assertEqual(reci_items[0]['serie'], 'SN998877')

        # Guardar recepción interna en sucursal 2
        resp_rec = self.client.post('/compras/recepcion-interna/nueva/', {
            'fecha': '2026-08-16', 'sucursal': self.s2.id, 'observaciones': 'Recepción verificada'
        })
        self.assertEqual(resp_rec.status_code, 302)

        # 5. Comprobar que subproducto.sucursal se actualizó a s2
        self.subp.refresh_from_db()
        self.assertEqual(self.subp.sucursal_id, self.s2.id)

    def test_ri_buscar_serie_subproducto_valido(self):
        resp = self.client.get(f'/compras/remitos-internos/buscar-serie/?serie=SN998877&sucursal_origen={self.s1.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('HX-Trigger', resp.headers)
        payload = json.loads(resp.headers['HX-Trigger'])
        self.assertEqual(payload['serieEncontradaRI']['id'], self.prod_trazable.id)
        self.assertEqual(payload['serieEncontradaRI']['serie'], 'SN998877')
        self.assertEqual(payload['serieEncontradaRI']['cuim'], 'CUIM554433')

    def test_ri_buscar_serie_subproducto_vendido_y_recomprado(self):
        from productos.models import Subproducto
        # Crear un registro histórico del mismo número de serie marcado como VENDIDA
        Subproducto.objects.create(
            empresa=self.emp, producto=self.prod_trazable, sucursal=self.s1,
            serie="SN998877", cuim="CUIM_VIEJO", situacion='VENDIDA', feccpra=date(2026, 8, 1)
        )
        # La consulta debe omitir el vendido y retornar la unidad activa con CUIM554433
        resp = self.client.get(f'/compras/remitos-internos/buscar-serie/?serie=SN998877&sucursal_origen={self.s1.id}')
        self.assertEqual(resp.status_code, 200)
        payload = json.loads(resp.headers['HX-Trigger'])
        self.assertEqual(payload['serieEncontradaRI']['cuim'], 'CUIM554433')

    def test_ri_buscar_serie_sucursal_incorrecta(self):
        resp = self.client.get(f'/compras/remitos-internos/buscar-serie/?serie=SN998877&sucursal_origen={self.s2.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('pertenece a', resp.content.decode('utf-8'))



