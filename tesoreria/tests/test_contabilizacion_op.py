"""Pruebas de la registración contable de la Orden de Pago (espejo del Recibo).

DEBE : - Pago a Proveedor -> cuenta patrimonial del proveedor.
       - Pago Simple      -> las cuentas elegidas en "Imputaciones Contables Manuales".
HABER: los medios de pago entregados.
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
from tesoreria.models import Banco, CuentaBancaria, MedioPago, OrdenPago

User = get_user_model()


class ContabilizacionOrdenPagoTestCase(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="tesorero2", password="clave")

        self.empresa = Empresa.objects.create(
            nombre="PAGOS SA", cuit="30222111003", direccion="C 1", correo="p@t.com",
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
        self.cta_proveedores = cuenta("211001", "PROVEEDORES", "P")
        self.cta_gastos = cuenta("411005", "ADM-REFRIGERIOS", "R")
        # Pasivo por cheques librados y todavía no debitados por el banco (Plan 035 §1.6).
        self.cta_cheques_emitidos = cuenta("211005", "CHEQUES EMITIDOS A PAGAR", "P")
        self.cta_ret_gan_practicada = cuenta("211010", "RET. GANANCIAS A DEPOSITAR", "P")

        ParametrosContables.objects.create(
            empresa=self.empresa,
            cta_caja=self.cta_caja,
            cta_dolar=self.cta_dolar,
            cta_caja_central=self.cta_caja,
            cta_caja_central_dolares=self.cta_dolar,
            cta_valores_cartera=self.cta_valores,
            cta_proveedores_default=self.cta_proveedores,
            cta_ret_practicada_ganancias=self.cta_ret_gan_practicada,
        )

        self.proveedor = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="PROVEEDORES VARIOS", cuit="20111111112",
            cta_pat=self.cta_proveedores.id, cta_res=self.cta_gastos.id,
        )

        MedioPago.objects.create(empresa=self.empresa, codigo="EFE", nombre="Efectivo",
                                 categoria="EFE", cuenta_contable=self.cta_caja)
        MedioPago.objects.create(empresa=self.empresa, codigo="CHQ", nombre="Cheque",
                                 categoria="CHQ", cuenta_contable=self.cta_valores)
        MedioPago.objects.create(empresa=self.empresa, codigo="TRA", nombre="Transferencia",
                                 categoria="TRA", cuenta_contable=self.cta_banco)

        Banco.objects.create(nombre="BANCO NACION")
        self.cuenta_bancaria = CuentaBancaria.objects.create(
            empresa=self.empresa, banco="BANCO NACION", cta_numero="123/4",
            cuenta_contable=self.cta_banco,
            cuenta_contable_cheques=self.cta_cheques_emitidos,
        )

        self.cliente_http = Client()
        self.cliente_http.force_login(self.usuario)
        sesion = self.cliente_http.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion['ejercicio_id'] = self.ejercicio.id
        sesion.save()

    def _postear(self, **extra):
        payload = {
            'proveedor_id': self.proveedor.codigo_id,
            'sucursal_id': self.sucursal.id,
            'fecha': '2026-07-27',
            'punto': 1,
            'tipo': 'P',
            'condic': 1,
            'cotizacion': 1,
            'observaciones': '',
            'aplicaciones': [],
            'imputaciones': [],
            'valores': [],
        }
        payload.update(extra)
        return json.loads(self.cliente_http.post(
            reverse('htmx_procesar_orden_pago'),
            data=json.dumps(payload),
            content_type="application/json",
        ).content)

    # ------------------------------------------------------------------- pruebas
    def test_pago_proveedor_debe_cuenta_patrimonial_haber_medios(self):
        datos = self._postear(tipo='P', valores=[{'categoria': 'EFE-ARS', 'importe': 20000}])
        self.assertEqual(datos['status'], 'success', datos)
        self.assertIsNotNone(datos['asiento_id'])

        asiento = Asiento.objects.get(pk=datos['asiento_id'])
        debe = [l for l in asiento.lineas.all() if l.debe > 0]
        haber = [l for l in asiento.lineas.all() if l.haber > 0]

        self.assertEqual(len(debe), 1)
        self.assertEqual(debe[0].cuenta_id, self.cta_proveedores.id)
        self.assertEqual(debe[0].debe, Decimal("20000.00"))

        self.assertEqual(len(haber), 1)
        self.assertEqual(haber[0].cuenta_id, self.cta_caja.id)
        self.assertEqual(haber[0].haber, Decimal("20000.00"))

        self.assertEqual(asiento.modulo, 4)
        orden = OrdenPago.objects.get(empresa=self.empresa, numero=datos['op_id'])
        self.assertEqual(orden.asiento_id, asiento.asiento_id)

    def test_pago_simple_admite_varias_cuentas_imputadas_al_debe(self):
        datos = self._postear(
            tipo='S',
            valores=[{'categoria': 'EFE-ARS', 'importe': 9000}],
            imputaciones=[
                {'cuenta_contable_id': self.cta_gastos.id, 'importe': 6000, 'leyenda': 'ALMUERZOS'},
                {'cuenta_contable_id': self.cta_proveedores.id, 'importe': 3000, 'leyenda': 'SEÑA'},
            ],
        )
        self.assertEqual(datos['status'], 'success', datos)

        asiento = Asiento.objects.get(pk=datos['asiento_id'])
        debe = {l.cuenta_id: l.debe for l in asiento.lineas.all() if l.debe > 0}
        haber = [l for l in asiento.lineas.all() if l.haber > 0]

        self.assertEqual(len(debe), 2)
        self.assertEqual(debe[self.cta_gastos.id], Decimal("6000.00"))
        self.assertEqual(debe[self.cta_proveedores.id], Decimal("3000.00"))
        self.assertEqual(len(haber), 1)
        self.assertEqual(haber[0].haber, Decimal("9000.00"))

    def test_varios_cheques_entregados_una_sola_linea_de_valores(self):
        """Regla: los cheques van en UNA línea contra Valores en Cartera, por la suma."""
        datos = self._postear(
            tipo='P',
            valores=[
                {'categoria': 'CP', 'importe': 5000,
                 'cuenta_bancaria_id': self.cuenta_bancaria.cta_bc_id, 'numero_comprobante': 'CH-1'},
                {'categoria': 'EFE-ARS', 'importe': 1000},
            ],
        )
        self.assertEqual(datos['status'], 'success', datos)

        asiento = Asiento.objects.get(pk=datos['asiento_id'])
        haber = [l for l in asiento.lineas.all() if l.haber > 0]
        self.assertEqual(len(haber), 2)   # cheques emitidos a pagar + caja
        self.assertEqual(asiento.monto, Decimal("6000.00"))

    def test_cheque_propio_acredita_cheques_emitidos_y_no_el_banco(self):
        """Tramo 1 del circuito del cheque propio (Plan 035 §1.6).

        Al librar el cheque el banco todavía no debitó nada: se acredita el pasivo
        "Cheques Emitidos a Pagar" de la cuenta bancaria, NO la cuenta corriente. Recién la
        conciliación, con el débito real, cancela ese pasivo contra el banco.
        """
        datos = self._postear(
            tipo='P',
            valores=[{'categoria': 'CP', 'importe': 5000,
                      'cuenta_bancaria_id': self.cuenta_bancaria.cta_bc_id,
                      'numero_comprobante': 'CH-9', 'fecha_vencimiento': '2026-10-27'}],
        )
        self.assertEqual(datos['status'], 'success', datos)

        asiento = Asiento.objects.get(pk=datos['asiento_id'])
        haber = [l for l in asiento.lineas.all() if l.haber > 0]
        self.assertEqual(len(haber), 1)
        self.assertEqual(haber[0].cuenta_id, self.cta_cheques_emitidos.id)
        self.assertNotEqual(haber[0].cuenta_id, self.cta_banco.id)

        # La transacción bancaria queda pendiente de débito, con sus datos propios.
        from tesoreria.models import TransaccionBancaria
        tr = TransaccionBancaria.objects.get(numero_operacion='CH-9')
        self.assertEqual(tr.tipo_transaccion, 'CP')
        self.assertEqual(tr.estado, 'E')
        self.assertEqual(tr.importe, Decimal("5000.00"))
        self.assertEqual(tr.empresa_id, self.empresa.id)
        # La fecha del movimiento es la del comprobante, no la del día de carga.
        self.assertEqual(tr.fecha_operacion, timezone.datetime(2026, 7, 27).date())

    def test_transferencia_emitida_si_impacta_el_banco(self):
        """La transferencia no tiene tramo intermedio: debita la cuenta bancaria de una vez."""
        datos = self._postear(
            tipo='P',
            valores=[{'categoria': 'TRA', 'importe': 3000,
                      'cuenta_bancaria_id': self.cuenta_bancaria.cta_bc_id,
                      'numero_comprobante': 'TR-1'}],
        )
        self.assertEqual(datos['status'], 'success', datos)

        asiento = Asiento.objects.get(pk=datos['asiento_id'])
        haber = [l for l in asiento.lineas.all() if l.haber > 0]
        self.assertEqual(haber[0].cuenta_id, self.cta_banco.id)

        from tesoreria.models import TransaccionBancaria
        tr = TransaccionBancaria.objects.get(numero_operacion='TR-1')
        self.assertEqual(tr.estado, 'D')

    def test_retencion_practicada_se_persiste_para_sicore(self):
        """Los datos del certificado ya no se descartan: quedan en RetencionPracticada."""
        from contable.models import RetencionPracticada

        medio_ret = MedioPago.objects.create(
            empresa=self.empresa, codigo="RETG", nombre="Retencion Ganancias",
            categoria="RET", cuenta_contable=self.cta_ret_gan_practicada)

        datos = self._postear(
            tipo='P',
            valores=[
                {'categoria': 'EFE-ARS', 'importe': 9000},
                {'categoria': 'RET', 'medio_pago_id': medio_ret.id, 'impuesto': 'GAN',
                 'importe': 1000, 'numero_comprobante': 'CERT-001',
                 'fecha': '2026-07-27', 'cuit': '20111111112',
                 'regimen': '116', 'base': 10000},
            ],
        )
        self.assertEqual(datos['status'], 'success', datos)

        ret = RetencionPracticada.objects.get(nro_certificado='CERT-001')
        self.assertEqual(ret.impuesto, 'GAN')
        self.assertEqual(ret.regimen, '116')
        self.assertEqual(ret.importe, Decimal("1000.00"))
        self.assertEqual(ret.base, Decimal("10000.00"))
        self.assertEqual(ret.alicuota, Decimal("10.000"))   # 1000 / 10000
        self.assertEqual(ret.empresa_id, self.empresa.id)
        self.assertIsNotNone(ret.asiento_id)

        # Y la retención es un HABER más del asiento: deuda con el fisco.
        asiento = Asiento.objects.get(pk=datos['asiento_id'])
        haber = {l.cuenta_id: l.haber for l in asiento.lineas.all() if l.haber > 0}
        self.assertEqual(haber[self.cta_ret_gan_practicada.id], Decimal("1000.00"))
        self.assertEqual(asiento.monto, Decimal("10000.00"))

    def test_op_rechaza_proveedor_de_otra_empresa(self):
        """Aislamiento multi-tenant: los ids llegan por JSON y hay que verificarlos."""
        otra = Empresa.objects.create(
            nombre="AJENA SA", cuit="30999888771", direccion="X", correo="x@x.com")
        intruso = ClienteProveedor.objects.create(
            empresa=otra, razon_social="PROVEEDOR AJENO", cuit="20999888771")

        datos = self._postear(
            proveedor_id=intruso.codigo_id,
            valores=[{'categoria': 'EFE-ARS', 'importe': 1000}])

        self.assertEqual(datos['status'], 'error')
        self.assertIn('no pertenece a la empresa activa', datos['message'])
        self.assertFalse(OrdenPago.objects.filter(proveedor=intruso).exists())

    def test_pago_en_dolares_pesificado_con_divisa_y_cotizacion(self):
        datos = self._postear(
            tipo='P', cotizacion=1420,
            valores=[{'categoria': 'EFE-USD', 'importe': 50}],
        )
        self.assertEqual(datos['status'], 'success', datos)

        asiento = Asiento.objects.get(pk=datos['asiento_id'])
        haber = [l for l in asiento.lineas.all() if l.haber > 0]

        self.assertEqual(len(haber), 1)
        self.assertEqual(haber[0].cuenta_id, self.cta_dolar.id)
        # En cble_asiento_mov el importe va PESIFICADO...
        self.assertEqual(haber[0].haber, Decimal("71000.00"))     # 50 x 1.420
        # ...y la divisa original queda en las columnas bimonetarias.
        self.assertEqual(haber[0].divisa, 'DOL')
        self.assertEqual(haber[0].cotizacion, Decimal("1420.0000"))
        self.assertEqual(haber[0].haber_divisa, Decimal("50.00"))

    def test_la_op_aparece_en_la_caja_diaria(self):
        datos = self._postear(tipo='P', valores=[{'categoria': 'EFE-ARS', 'importe': 4000}])
        orden = OrdenPago.objects.get(empresa=self.empresa, numero=datos['op_id'])
        asiento = Asiento.objects.get(pk=datos['asiento_id'])

        self.assertEqual(asiento.sesion_caja_id, orden.sesion_caja_id)

        from tesoreria.services.caja_diaria import armar_caja_diaria
        reporte = armar_caja_diaria(orden.sesion_caja)
        self.assertEqual(len(reporte['movimientos']), 1)
        # Es un egreso: sale plata de la caja.
        self.assertEqual(reporte['movimientos'][0]['efectivo'], Decimal("-4000.00"))
        self.assertEqual(reporte['saldos']['movimiento']['egresos'], Decimal("4000.00"))
