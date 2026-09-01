"""Pruebas de la registración contable del Recibo.

DEBE : los medios de cobro (caja, dólares, banco, valores en cartera, tarjetas).
HABER: - Cobranza a Cliente -> cuenta patrimonial del cliente.
       - Recibo Simple      -> la/s cuenta/s elegidas en "Imputación Contable (Haber)".
"""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from contable.models import Asiento, Cuenta, ParametrosContables
from empresas.models import Empresa, Ejercicio, Sucursal
from facturacion.models import ClienteProveedor
from tesoreria.models import Banco, CuentaBancaria, MedioPago, Recibo

User = get_user_model()


class ContabilizacionReciboTestCase(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="cajero", password="clave")

        self.empresa = Empresa.objects.create(
            nombre="RECIBOS SA", cuit="30444333221", direccion="C 1", correo="r@t.com",
        )
        self.sucursal = Sucursal.objects.create(empresa=self.empresa, nombre="CENTRAL")
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa, ejercicio="2026",
            inicio=timezone.datetime(2026, 1, 1).date(),
            cierre=timezone.datetime(2026, 12, 31).date(),
        )

        def cuenta(jerarquia, nombre, tipo, disponibilidad=''):
            return Cuenta.objects.create(
                jerarquia=jerarquia, cuenta=nombre, imputable=1, tipo=tipo,
                empresa=self.empresa, tipo_disponibilidad=disponibilidad,
            )

        self.cta_caja = cuenta("111001", "CAJA TESORERIA", "A", "EFE")
        self.cta_dolar = cuenta("111003", "CAJA DOLARES", "A", "DOL")
        self.cta_valores = cuenta("111002", "VALORES EN CARTERA", "A", "VAL")
        self.cta_banco = cuenta("111011", "BANCO NACION", "A", "BCO")
        self.cta_clientes = cuenta("112001", "DEUDORES POR VENTAS", "A")
        self.cta_ingresos = cuenta("511001", "INGRESOS VARIOS", "R")

        ParametrosContables.objects.create(
            empresa=self.empresa,
            cta_caja=self.cta_caja,
            cta_dolar=self.cta_dolar,
            cta_caja_central=self.cta_caja,
            cta_caja_central_dolares=self.cta_dolar,
            cta_valores_cartera=self.cta_valores,
            cta_clientes_default=self.cta_clientes,
        )

        self.cliente = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="CLIENTE UNO SRL", cuit="20111111112",
            cta_pat=self.cta_clientes.id, cta_res=self.cta_ingresos.id,
        )

        MedioPago.objects.create(empresa=self.empresa, codigo="EFE", nombre="Efectivo",
                                 categoria="EFE", cuenta_contable=self.cta_caja)
        MedioPago.objects.create(empresa=self.empresa, codigo="CHQ", nombre="Cheque",
                                 categoria="CHQ", cuenta_contable=self.cta_valores)
        MedioPago.objects.create(empresa=self.empresa, codigo="TRA", nombre="Transferencia",
                                 categoria="TRA", cuenta_contable=self.cta_banco)

        banco = Banco.objects.create(nombre="BANCO NACION")
        self.cuenta_bancaria = CuentaBancaria.objects.create(
            empresa=self.empresa, banco="BANCO NACION", cta_numero="123/4",
            cuenta_contable=self.cta_banco,
        )
        self.banco = banco

        self.cliente_http = Client()
        self.cliente_http.force_login(self.usuario)
        sesion = self.cliente_http.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion['ejercicio_id'] = self.ejercicio.id
        sesion.save()

    def _postear(self, payload):
        return self.cliente_http.post(
            reverse('htmx_procesar_recibo'),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def _payload_base(self, **extra):
        base = {
            'cliente_id': self.cliente.codigo_id,
            'sucursal_id': self.sucursal.id,
            'fecha': '2026-07-27',
            'punto': 1,
            'tipo': 'C',
            'condic': 1,
            'cotizacion': 1,
            'observaciones': '',
            'aplicaciones': [],
            'imputaciones': [],
            'valores': [],
        }
        base.update(extra)
        return base

    # ------------------------------------------------------------------- pruebas
    def test_cobranza_cliente_debe_medios_haber_cuenta_patrimonial(self):
        respuesta = self._postear(self._payload_base(
            tipo='C',
            valores=[{'categoria': 'EFE-ARS', 'importe': 15000}],
        ))
        datos = json.loads(respuesta.content)

        self.assertEqual(respuesta.status_code, 200, datos)
        self.assertEqual(datos['status'], 'success')
        self.assertIsNotNone(datos['asiento_id'], "Debe devolver el número de asiento")

        asiento = Asiento.objects.get(pk=datos['asiento_id'])
        self.assertEqual(asiento.modulo, 4)          # Tesorería
        self.assertEqual(asiento.condic, 1)          # hereda la condición del recibo
        self.assertEqual(asiento.monto, Decimal("15000.00"))

        lineas = list(asiento.lineas.all())
        debe = [l for l in lineas if l.debe > 0]
        haber = [l for l in lineas if l.haber > 0]

        self.assertEqual(len(debe), 1)
        self.assertEqual(debe[0].cuenta_id, self.cta_caja.id)
        self.assertEqual(debe[0].debe, Decimal("15000.00"))

        self.assertEqual(len(haber), 1)
        self.assertEqual(haber[0].cuenta_id, self.cta_clientes.id)
        self.assertEqual(haber[0].haber, Decimal("15000.00"))

        recibo = Recibo.objects.get(empresa=self.empresa, numero=datos['recibo_id'])
        self.assertEqual(recibo.asiento_id, asiento.asiento_id)

    def test_recibo_simple_haber_va_a_la_cuenta_imputada(self):
        respuesta = self._postear(self._payload_base(
            tipo='S',
            valores=[{'categoria': 'EFE-ARS', 'importe': 8000}],
            imputaciones=[{'cuenta_contable_id': self.cta_ingresos.id, 'importe': 8000,
                           'leyenda': 'ALQUILER COCHERA'}],
        ))
        datos = json.loads(respuesta.content)
        self.assertEqual(datos['status'], 'success', datos)

        asiento = Asiento.objects.get(pk=datos['asiento_id'])
        haber = [l for l in asiento.lineas.all() if l.haber > 0]

        self.assertEqual(len(haber), 1)
        self.assertEqual(haber[0].cuenta_id, self.cta_ingresos.id)
        self.assertEqual(haber[0].haber, Decimal("8000.00"))
        self.assertEqual(haber[0].leyenda, 'ALQUILER COCHERA')

    def test_varios_medios_de_cobro_generan_una_linea_de_debe_cada_uno(self):
        respuesta = self._postear(self._payload_base(
            tipo='C',
            valores=[
                {'categoria': 'EFE-ARS', 'importe': 10000},
                {'categoria': 'CHQ', 'importe': 25000, 'banco_id': self.banco.id,
                 'numero_comprobante': '00012345'},
                {'categoria': 'TRA', 'importe': 5000,
                 'cuenta_bancaria_id': self.cuenta_bancaria.cta_bc_id,
                 'numero_comprobante': 'TR-99'},
            ],
        ))
        datos = json.loads(respuesta.content)
        self.assertEqual(datos['status'], 'success', datos)

        asiento = Asiento.objects.get(pk=datos['asiento_id'])
        debe = {l.cuenta_id: l.debe for l in asiento.lineas.all() if l.debe > 0}
        haber = [l for l in asiento.lineas.all() if l.haber > 0]

        self.assertEqual(debe[self.cta_caja.id], Decimal("10000.00"))
        self.assertEqual(debe[self.cta_valores.id], Decimal("25000.00"))
        self.assertEqual(debe[self.cta_banco.id], Decimal("5000.00"))

        # El haber cancela el total en una sola línea contra la cuenta del cliente.
        self.assertEqual(len(haber), 1)
        self.assertEqual(haber[0].haber, Decimal("40000.00"))
        self.assertEqual(asiento.monto, Decimal("40000.00"))

    def test_cobro_en_dolares_se_imputa_a_la_cuenta_de_dolares_pesificado(self):
        respuesta = self._postear(self._payload_base(
            tipo='C',
            cotizacion=1420,
            valores=[{'categoria': 'EFE-USD', 'importe': 100}],
        ))
        datos = json.loads(respuesta.content)
        self.assertEqual(datos['status'], 'success', datos)

        asiento = Asiento.objects.get(pk=datos['asiento_id'])
        debe = [l for l in asiento.lineas.all() if l.debe > 0]

        self.assertEqual(len(debe), 1)
        self.assertEqual(debe[0].cuenta_id, self.cta_dolar.id)
        self.assertEqual(debe[0].debe, Decimal("142000.00"))   # 100 USD x 1.420, pesificado
        self.assertEqual(debe[0].debe_divisa, Decimal("100.00"))
        self.assertEqual(debe[0].divisa, 'DOL')

    def test_el_asiento_queda_vinculado_a_la_caja_para_la_caja_diaria(self):
        respuesta = self._postear(self._payload_base(
            tipo='C', valores=[{'categoria': 'EFE-ARS', 'importe': 3000}],
        ))
        datos = json.loads(respuesta.content)
        asiento = Asiento.objects.get(pk=datos['asiento_id'])
        recibo = Recibo.objects.first()

        self.assertIsNotNone(asiento.sesion_caja_id)
        self.assertEqual(asiento.sesion_caja_id, recibo.sesion_caja_id)

        # Y por lo tanto aparece en el reporte de Caja Diaria de esa caja.
        from tesoreria.services.caja_diaria import armar_caja_diaria
        datos_caja = armar_caja_diaria(recibo.sesion_caja)
        self.assertEqual(len(datos_caja['movimientos']), 1)
        self.assertEqual(datos_caja['movimientos'][0]['efectivo'], Decimal("3000.00"))
        self.assertEqual(datos_caja['saldos']['final']['efectivo'], Decimal("3000.00"))

    def test_varios_cheques_van_en_una_sola_linea_de_valores_en_cartera(self):
        """Regla: el asiento lleva UNA línea contra Valores en Cartera por la suma de los cheques.
        El seguimiento individual de cada cheque vive en `tesoreria_valor_terceros`."""
        respuesta = self._postear(self._payload_base(
            tipo='C',
            valores=[
                {'categoria': 'CHQ', 'importe': 10000, 'banco_id': self.banco.id,
                 'numero_comprobante': '0001', 'titular_emisor': 'JUAN'},
                {'categoria': 'CHQ', 'importe': 15000, 'banco_id': self.banco.id,
                 'numero_comprobante': '0002', 'titular_emisor': 'PEDRO'},
                {'categoria': 'CHQ', 'importe': 5000, 'banco_id': self.banco.id,
                 'numero_comprobante': '0003', 'titular_emisor': 'ANA'},
            ],
        ))
        datos = json.loads(respuesta.content)
        self.assertEqual(datos['status'], 'success', datos)

        asiento = Asiento.objects.get(pk=datos['asiento_id'])
        debe = [l for l in asiento.lineas.all() if l.debe > 0]

        # Una sola línea, por la suma de los tres cheques.
        self.assertEqual(len(debe), 1)
        self.assertEqual(debe[0].cuenta_id, self.cta_valores.id)
        self.assertEqual(debe[0].debe, Decimal("30000.00"))

        # Pero los tres cheques quedan cargados uno por uno para su seguimiento.
        from tesoreria.models import ValorTerceros
        valores = ValorTerceros.objects.filter(
            movimiento_detalle__movimiento_caja__recibo__numero=datos['recibo_id']
        )
        self.assertEqual(valores.count(), 3)
        self.assertEqual(
            sorted(valores.values_list('numero_cheque', flat=True)),
            ['0001', '0002', '0003'],
        )
        self.assertTrue(all(v.estado == 'C' for v in valores))   # quedan en cartera

    def test_movimiento_de_caja_guarda_los_tres_valores_del_cobro_en_dolares(self):
        """En tesoreria_movimiento_caja todo se guarda pesificado, pero el detalle conserva los
        tres datos para poder exponerlos: dólares originales, cotización y valor pesificado."""
        respuesta = self._postear(self._payload_base(
            tipo='C', cotizacion=1420,
            valores=[{'categoria': 'EFE-USD', 'importe': 200}],
        ))
        datos = json.loads(respuesta.content)
        self.assertEqual(datos['status'], 'success', datos)

        from tesoreria.models import MovimientoCaja, MovimientoCajaDetalle
        movimiento = MovimientoCaja.objects.get(recibo__numero=datos['recibo_id'])
        detalle = MovimientoCajaDetalle.objects.get(movimiento_caja=movimiento)

        # Cabecera pesificada.
        self.assertEqual(movimiento.importe, Decimal("284000.00"))
        # Los tres valores en el detalle.
        self.assertEqual(detalle.importe_moneda_extranjera, Decimal("200.00"))   # USD originales
        self.assertEqual(detalle.cotizacion, Decimal("1420.0000"))               # cotización
        self.assertEqual(detalle.importe, Decimal("284000.00"))                  # pesificado

    def test_recibo_presupuestado_genera_asiento_no_fiscal(self):
        respuesta = self._postear(self._payload_base(
            tipo='C', condic=2, valores=[{'categoria': 'EFE-ARS', 'importe': 1000}],
        ))
        datos = json.loads(respuesta.content)
        asiento = Asiento.objects.get(pk=datos['asiento_id'])
        self.assertEqual(asiento.condic, 2)
