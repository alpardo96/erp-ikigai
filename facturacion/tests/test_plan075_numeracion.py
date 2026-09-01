"""Integridad de la numeración de comprobantes de venta (Plan 075).

El control de integridad sólo es posible sobre los comprobantes que uno EMITE, con
numeración correlativa propia y auditable. `Venta` era el único documento emitido del
sistema sin bloqueo al numerar **ni** restricción única en la base.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from core.models import ContadorDocumento
from core.services.numeracion import (auditar_correlativos, siguiente_numero_nci,
                                      siguiente_numero_pre)
from empresas.models import Empresa, PuntoVenta, Sucursal
from facturacion.models import ClienteProveedor, TipoComprobante, Venta
from facturacion.services.facturacion_lote_service import FacturacionLoteService


class BaseNumeracionTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Empresa Prueba", cuit="30111111118")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, nombre="Casa Central", punto=1)
        self.usuario = User.objects.create_user(username="operador", password="x")
        self.tipo_pre = TipoComprobante.objects.create(
            codigo='PRE', detalle="Comprobante Interno", signo=1)
        self.tipo_b = TipoComprobante.objects.create(
            codigo='006', detalle="Factura B", signo=1)
        self.cliente = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="Cliente Uno", tipo_entidad=1)

    def crear_venta(self, tipo, punto, numero):
        return Venta.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, usuario=self.usuario,
            cliente=self.cliente, tipo=tipo, punto=punto, numero=numero,
            fecha="2026-08-29", neto=Decimal('100.00'), total=Decimal('100.00'))


class RestriccionUnicaTestCase(BaseNumeracionTestCase):
    def test_no_se_puede_repetir_numero_en_la_misma_serie(self):
        """La segunda barrera que faltaba: aunque la lógica falle, la base rechaza."""
        self.crear_venta(self.tipo_b, punto=1, numero=100)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.crear_venta(self.tipo_b, punto=1, numero=100)

    def test_el_mismo_numero_en_otro_punto_es_valido(self):
        self.crear_venta(self.tipo_b, punto=1, numero=100)
        self.crear_venta(self.tipo_b, punto=2, numero=100)
        self.assertEqual(Venta.objects.filter(numero=100).count(), 2)

    def test_el_mismo_numero_en_otro_tipo_es_valido(self):
        self.crear_venta(self.tipo_b, punto=1, numero=100)
        self.crear_venta(self.tipo_pre, punto=1, numero=100)
        self.assertEqual(Venta.objects.filter(numero=100).count(), 2)

    def test_el_mismo_numero_en_otra_empresa_es_valido(self):
        otra = Empresa.objects.create(nombre="Otra", cuit="30222222229")
        otra_suc = Sucursal.objects.create(empresa=otra, nombre="Suc", punto=1)
        self.crear_venta(self.tipo_b, punto=1, numero=100)
        Venta.objects.create(
            empresa=otra, sucursal=otra_suc, usuario=self.usuario,
            cliente=self.cliente, tipo=self.tipo_b, punto=1, numero=100,
            fecha="2026-08-29", neto=Decimal('100.00'), total=Decimal('100.00'))
        self.assertEqual(Venta.objects.filter(numero=100).count(), 2)


class ContadoresNoFiscalesTestCase(BaseNumeracionTestCase):
    def test_el_pre_avanza_correlativo_por_sucursal(self):
        numeros = [siguiente_numero_pre(self.empresa.id, self.sucursal.id)
                   for _ in range(3)]
        self.assertEqual(numeros, [1, 2, 3])

    def test_cada_sucursal_lleva_su_propia_serie(self):
        otra = Sucursal.objects.create(empresa=self.empresa, nombre="Norte", punto=2)
        self.assertEqual(siguiente_numero_pre(self.empresa.id, self.sucursal.id), 1)
        self.assertEqual(siguiente_numero_pre(self.empresa.id, otra.id), 1)
        self.assertEqual(siguiente_numero_pre(self.empresa.id, self.sucursal.id), 2)

    def test_pre_y_nci_son_series_independientes(self):
        """Decisión del usuario: series separadas, para auditar sin excepciones."""
        self.assertEqual(siguiente_numero_pre(self.empresa.id, self.sucursal.id), 1)
        self.assertEqual(siguiente_numero_nci(self.empresa.id, self.sucursal.id), 1)
        self.assertEqual(siguiente_numero_pre(self.empresa.id, self.sucursal.id), 2)

    def test_el_contador_arranca_del_ultimo_emitido_si_ya_existe(self):
        """Es lo que hace la migración de datos: no pisar series preexistentes."""
        ContadorDocumento.objects.create(
            empresa=self.empresa, punto=self.sucursal.id,
            tipo_documento=ContadorDocumento.VENTA_PRE, ultimo_numero=57)
        self.assertEqual(siguiente_numero_pre(self.empresa.id, self.sucursal.id), 58)


class AuditoriaDeCorrelativosTestCase(BaseNumeracionTestCase):
    def test_una_serie_completa_da_ok(self):
        for numero in (1, 2, 3):
            self.crear_venta(self.tipo_pre, punto=self.sucursal.id, numero=numero)
        ContadorDocumento.objects.create(
            empresa=self.empresa, punto=self.sucursal.id,
            tipo_documento=ContadorDocumento.VENTA_PRE, ultimo_numero=3)

        filas = auditar_correlativos(self.empresa.id)
        pre = next(f for f in filas if f['tipo'] == ContadorDocumento.VENTA_PRE)
        self.assertTrue(pre['ok'])
        self.assertEqual(pre['faltantes'], [])

    def test_detecta_un_hueco_en_la_serie(self):
        for numero in (1, 2, 4):
            self.crear_venta(self.tipo_pre, punto=self.sucursal.id, numero=numero)

        filas = auditar_correlativos(self.empresa.id)
        pre = next(f for f in filas if f['tipo'] == ContadorDocumento.VENTA_PRE)
        self.assertFalse(pre['ok'])
        self.assertEqual(pre['faltantes'], [3])

    def test_detecta_el_desfasaje_contra_el_contador(self):
        for numero in (1, 2):
            self.crear_venta(self.tipo_pre, punto=self.sucursal.id, numero=numero)
        ContadorDocumento.objects.create(
            empresa=self.empresa, punto=self.sucursal.id,
            tipo_documento=ContadorDocumento.VENTA_PRE, ultimo_numero=9)

        filas = auditar_correlativos(self.empresa.id)
        pre = next(f for f in filas if f['tipo'] == ContadorDocumento.VENTA_PRE)
        self.assertFalse(pre['ok'])
        self.assertEqual(pre['contador'], 9)
        self.assertEqual(pre['maximo'], 2)

    def test_la_auditoria_no_mezcla_pre_con_facturas(self):
        self.crear_venta(self.tipo_pre, punto=self.sucursal.id, numero=1)
        self.crear_venta(self.tipo_b, punto=1, numero=500)

        filas = auditar_correlativos(self.empresa.id)
        pre = next(f for f in filas if f['tipo'] == ContadorDocumento.VENTA_PRE)
        self.assertEqual(pre['cantidad'], 1)
        self.assertEqual(pre['maximo'], 1)


class LoteSinFallbacksTestCase(BaseNumeracionTestCase):
    """Plan 075 §5.5: un comprobante mal emitido es peor que uno no emitido."""

    def setUp(self):
        super().setUp()
        self.punto_venta = PuntoVenta.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, numero=3)

    def _servicio(self):
        return FacturacionLoteService(empresa_id=self.empresa.id, usuario=self.usuario)

    def test_sin_tipo_pre_configurado_falla_explicito(self):
        self.tipo_pre.delete()
        with self.assertRaises(ValueError) as contexto:
            self._servicio().procesar_lote([], "202608", self.punto_venta.id)
        self.assertIn("PRE", str(contexto.exception))

    def test_punto_de_venta_inexistente_falla_explicito(self):
        """Antes asumía el punto 1 en silencio y emitía en la serie equivocada."""
        with self.assertRaises(ValueError) as contexto:
            self._servicio().procesar_lote([], "202608", 999999)
        self.assertIn("punto de venta", str(contexto.exception).lower())

    def test_punto_de_venta_de_otra_empresa_falla(self):
        otra = Empresa.objects.create(nombre="Otra", cuit="30222222229")
        otra_suc = Sucursal.objects.create(empresa=otra, nombre="Suc", punto=1)
        ajeno = PuntoVenta.objects.create(empresa=otra, sucursal=otra_suc, numero=9)
        with self.assertRaises(ValueError):
            self._servicio().procesar_lote([], "202608", ajeno.id)

    def test_la_emision_real_esta_bloqueada_hasta_cablear_arca(self):
        """Mejor cortar antes de emitir que generar un número que ARCA no autorizó."""
        from productos.models import Producto
        from facturacion.models import TarifaEstudio
        producto = Producto.objects.create(empresa=self.empresa, detalle="Servicio")
        tarifa = TarifaEstudio.objects.create(
            empresa=self.empresa, cliente=self.cliente, producto=producto,
            tarifa_f=Decimal('1000.00'), tarifa_p=Decimal('0.00'))

        resultados = self._servicio().procesar_lote(
            [{'id_tarifa': tarifa.id, 'cliente_id': self.cliente.codigo_id,
              'producto_id': producto.id, 'producto_detalle': 'Servicio',
              'tarifa_f': 1000.0, 'tarifa_p': 0.0, 'alic_iva': 21.0}],
            "202608", self.punto_venta.id, modo_prueba=False)

        self.assertEqual(resultados[0]['status'], 'error')
        self.assertIn("ARCA", resultados[0]['msg'])
        self.assertEqual(Venta.objects.count(), 0)
