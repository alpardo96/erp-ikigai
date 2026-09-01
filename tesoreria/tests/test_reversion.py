"""Pruebas de la reversión total de comprobantes de tesorería (Plan 035 §1.7).

Anular una Orden de Pago tiene que deshacer TODO: aplicaciones, cheques entregados, valores
bancarios, retenciones y movimientos de caja. Antes sólo se marcaba el asiento como anulado y
la factura seguía figurando pagada.
"""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from contable.models import Asiento, Cuenta, ParametrosContables, RetencionPracticada
from contable.services.reversion import (
    ReversionBloqueada, revertir_orden_pago, revertir_por_asiento,
)
from empresas.models import Empresa, Ejercicio, Sucursal
from facturacion.models import ClienteProveedor, Compra, TipoComprobante
from tesoreria.models import (
    Banco, CuentaBancaria, MedioPago, OrdenPago, OrdenPagoAplicacion,
    TransaccionBancaria, ValorTerceros,
)

User = get_user_model()


class ReversionOrdenPagoTestCase(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="tesorero3", password="clave", is_staff=True)
        self.empresa = Empresa.objects.create(
            nombre="REVERSAS SA", cuit="30222111004", direccion="C 1", correo="r@t.com")
        self.sucursal = Sucursal.objects.create(empresa=self.empresa, nombre="CENTRAL")
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa, ejercicio="2026",
            inicio=timezone.datetime(2026, 1, 1).date(),
            cierre=timezone.datetime(2026, 12, 31).date())

        def cuenta(jerarquia, nombre, tipo, disp=''):
            return Cuenta.objects.create(
                jerarquia=jerarquia, cuenta=nombre, imputable=1, tipo=tipo,
                empresa=self.empresa, tipo_disponibilidad=disp)

        self.cta_caja = cuenta("111001", "CAJA TESORERIA", "A", "EFE")
        self.cta_valores = cuenta("111002", "VALORES EN CARTERA", "A", "VAL")
        self.cta_banco = cuenta("111011", "BANCO NACION", "A", "BCO")
        self.cta_cheques = cuenta("211005", "CHEQUES EMITIDOS A PAGAR", "P")
        self.cta_proveedores = cuenta("211001", "PROVEEDORES", "P")
        self.cta_ret_gan = cuenta("211010", "RET GANANCIAS A DEPOSITAR", "P")
        self.cta_compras = cuenta("411001", "COMPRAS", "R")

        ParametrosContables.objects.create(
            empresa=self.empresa, cta_caja=self.cta_caja, cta_caja_central=self.cta_caja,
            cta_valores_cartera=self.cta_valores, cta_proveedores_default=self.cta_proveedores,
            cta_compras=self.cta_compras, cta_ret_practicada_ganancias=self.cta_ret_gan)

        self.proveedor = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="PROVEEDOR SA", cuit="20111111112",
            tipo_entidad=2, cta_pat=self.cta_proveedores.id)

        MedioPago.objects.create(empresa=self.empresa, codigo="EFE", nombre="Efectivo",
                                 categoria="EFE", cuenta_contable=self.cta_caja)
        MedioPago.objects.create(empresa=self.empresa, codigo="CHQ", nombre="Cheque",
                                 categoria="CHQ", cuenta_contable=self.cta_valores)
        MedioPago.objects.create(empresa=self.empresa, codigo="TRA", nombre="Transferencia",
                                 categoria="TRA", cuenta_contable=self.cta_banco)
        self.medio_ret = MedioPago.objects.create(
            empresa=self.empresa, codigo="RETG", nombre="Retencion Ganancias",
            categoria="RET", cuenta_contable=self.cta_ret_gan)

        Banco.objects.create(nombre="BANCO NACION")
        self.cuenta_bancaria = CuentaBancaria.objects.create(
            empresa=self.empresa, banco="BANCO NACION", cta_numero="123/4",
            cuenta_contable=self.cta_banco, cuenta_contable_cheques=self.cta_cheques)

        self.tipo_fac = TipoComprobante.objects.create(
            codigo="F01", detalle="FACTURA A", signo=1, estado=True)

        # Factura de gasto sin ítems: el DEBE va a la cuenta de compras general. Se cargan
        # `subtotal` y `neto` porque de ahí sale el importe del asiento (sin ellos el Debe
        # quedaría en cero y la contabilización automática rechazaría el asiento).
        self.factura = Compra.objects.create(
            fecha=timezone.datetime(2026, 7, 1).date(), tipo=self.tipo_fac, punto=1,
            numero=5001, proveedor=self.proveedor,
            subtotal=Decimal("10000.00"), neto=Decimal("10000.00"), iva=Decimal("0.00"),
            total=Decimal("10000.00"),
            saldo=Decimal("10000.00"), usuario=self.usuario, sucursal=self.sucursal,
            empresa=self.empresa, ejercicio=self.ejercicio)

        self.cliente_http = Client()
        self.cliente_http.force_login(self.usuario)
        s = self.cliente_http.session
        s['empresa_id'] = self.empresa.id
        s['sucursal_id'] = self.sucursal.id
        s['ejercicio_id'] = self.ejercicio.id
        s.save()

    def _crear_op(self, **extra):
        payload = {
            'proveedor_id': self.proveedor.codigo_id, 'sucursal_id': self.sucursal.id,
            'fecha': '2026-07-27', 'punto': 1, 'tipo': 'P', 'condic': 1, 'cotizacion': 1,
            'observaciones': '', 'aplicaciones': [], 'imputaciones': [], 'valores': [],
        }
        payload.update(extra)
        datos = json.loads(self.cliente_http.post(
            reverse('htmx_procesar_orden_pago'),
            data=json.dumps(payload), content_type="application/json").content)
        self.assertEqual(datos['status'], 'success', datos)
        return OrdenPago.objects.get(empresa=self.empresa, numero=datos['op_id'])

    def _cheque_en_cartera(self):
        """Cheque de tercero disponible, con su importe propio."""
        return ValorTerceros.objects.create(
            empresa=self.empresa, banco=Banco.objects.first(), numero_cheque="CH-TER-1",
            importe=Decimal("4000.00"), fecha_emision=timezone.datetime(2026, 7, 1).date(),
            fecha_vencimiento=timezone.datetime(2026, 9, 1).date(),
            sucursal_id=self.sucursal.id, estado='C')

    # --------------------------------------------------------------------- pruebas
    def test_reversion_devuelve_la_factura_a_su_saldo(self):
        op = self._crear_op(
            aplicaciones=[{'id': self.factura.compras_id, 'importe': 10000}],
            valores=[{'categoria': 'EFE-ARS', 'importe': 10000}])

        self.factura.refresh_from_db()
        self.assertEqual(self.factura.saldo, Decimal("0.00"))
        self.assertEqual(self.factura.pagado, Decimal("10000.00"))

        revertir_orden_pago(op, usuario=self.usuario)

        self.factura.refresh_from_db()
        self.assertEqual(self.factura.saldo, Decimal("10000.00"))
        self.assertEqual(self.factura.pagado, Decimal("0.00"))
        self.assertFalse(OrdenPagoAplicacion.objects.filter(orden_pago=op).exists())

        op.refresh_from_db()
        self.assertTrue(op.anulado)

    def test_reversion_devuelve_el_cheque_de_terceros_a_cartera(self):
        cheque = self._cheque_en_cartera()
        op = self._crear_op(valores=[{'categoria': 'CHQ-TER', 'id': cheque.pk, 'importe': 4000}])

        cheque.refresh_from_db()
        self.assertEqual(cheque.estado, 'E')
        self.assertEqual(cheque.orden_pago_id, op.pk)

        revertir_orden_pago(op, usuario=self.usuario)

        cheque.refresh_from_db()
        self.assertEqual(cheque.estado, 'C')
        self.assertIsNone(cheque.orden_pago_id)
        self.assertIsNone(cheque.fecha_entrega)
        self.assertIsNone(cheque.asiento_entrega_id)

    def test_reversion_borra_valores_bancarios_y_retenciones(self):
        op = self._crear_op(valores=[
            {'categoria': 'CP', 'importe': 5000, 'numero_comprobante': 'CH-P-1',
             'cuenta_bancaria_id': self.cuenta_bancaria.cta_bc_id},
            {'categoria': 'RET', 'medio_pago_id': self.medio_ret.id, 'importe': 1000,
             'numero_comprobante': 'CERT-9', 'fecha': '2026-07-27', 'regimen': '116',
             'base': 10000},
        ])

        self.assertTrue(TransaccionBancaria.objects.filter(numero_operacion='CH-P-1').exists())
        self.assertTrue(RetencionPracticada.objects.filter(orden_pago=op).exists())

        revertir_orden_pago(op, usuario=self.usuario)

        self.assertFalse(TransaccionBancaria.objects.filter(numero_operacion='CH-P-1').exists())
        self.assertFalse(RetencionPracticada.objects.filter(orden_pago=op).exists())

    def test_reversion_anula_el_asiento_sin_borrarlo(self):
        """El asiento se ANULA: la trazabilidad contable no se destruye."""
        op = self._crear_op(valores=[{'categoria': 'EFE-ARS', 'importe': 2000}])
        asiento_id = op.asiento_id

        revertir_orden_pago(op, usuario=self.usuario)

        asiento = Asiento.objects.get(pk=asiento_id)
        self.assertTrue(asiento.anulado)
        self.assertIsNotNone(asiento.fec_anulacion)

    def test_no_se_puede_revertir_con_un_cheque_ya_debitado(self):
        op = self._crear_op(valores=[
            {'categoria': 'CP', 'importe': 5000, 'numero_comprobante': 'CH-P-2',
             'cuenta_bancaria_id': self.cuenta_bancaria.cta_bc_id}])

        # El banco lo debitó (lo marcaría la conciliación bancaria).
        TransaccionBancaria.objects.filter(numero_operacion='CH-P-2').update(estado='D')

        with self.assertRaises(ReversionBloqueada):
            revertir_orden_pago(op, usuario=self.usuario)

        op.refresh_from_db()
        self.assertFalse(op.anulado)

        # Con `forzar` sí procede, para casos excepcionales.
        revertir_orden_pago(op, usuario=self.usuario, forzar=True)
        op.refresh_from_db()
        self.assertTrue(op.anulado)

    def test_revertir_desde_el_asiento_arrastra_la_orden_de_pago(self):
        op = self._crear_op(
            aplicaciones=[{'id': self.factura.compras_id, 'importe': 3000}],
            valores=[{'categoria': 'EFE-ARS', 'importe': 3000}])

        revertir_por_asiento(op.asiento_id, usuario=self.usuario)

        op.refresh_from_db()
        self.assertTrue(op.anulado)
        self.factura.refresh_from_db()
        self.assertEqual(self.factura.saldo, Decimal("10000.00"))

    def test_reversion_es_idempotente(self):
        op = self._crear_op(valores=[{'categoria': 'EFE-ARS', 'importe': 1000}])
        revertir_orden_pago(op, usuario=self.usuario)
        revertir_orden_pago(op, usuario=self.usuario)   # no debe romper ni duplicar efectos
        op.refresh_from_db()
        self.assertTrue(op.anulado)

    # ------------------------------------------------------- listado y reimpresión
    def test_listado_muestra_aplicado_y_pendiente(self):
        """La OP se emite por 10.000 y sólo se imputan 4.000: el resto queda pendiente."""
        self._crear_op(
            aplicaciones=[{'id': self.factura.compras_id, 'importe': 4000}],
            valores=[{'categoria': 'EFE-ARS', 'importe': 10000}])

        respuesta = self.cliente_http.get(
            reverse('ordenpago_grilla'), {'desde': '2026-07-01', 'hasta': '2026-07-31'})
        self.assertEqual(respuesta.status_code, 200)

        contenido = respuesta.content.decode()
        self.assertIn('10.000,00', contenido)   # total
        self.assertIn('4.000,00', contenido)    # aplicado
        self.assertIn('6.000,00', contenido)    # pendiente de aplicar

    def test_anular_desde_el_listado_revierte_todo(self):
        op = self._crear_op(
            aplicaciones=[{'id': self.factura.compras_id, 'importe': 10000}],
            valores=[{'categoria': 'EFE-ARS', 'importe': 10000}])

        respuesta = self.cliente_http.post(reverse('ordenpago_anular', args=[op.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['HX-Trigger'], 'reloadOrdenesPago')

        op.refresh_from_db()
        self.assertTrue(op.anulado)
        self.factura.refresh_from_db()
        self.assertEqual(self.factura.saldo, Decimal("10000.00"))

    def test_anular_bloqueado_devuelve_409_con_el_motivo(self):
        op = self._crear_op(valores=[
            {'categoria': 'CP', 'importe': 5000, 'numero_comprobante': 'CH-P-3',
             'cuenta_bancaria_id': self.cuenta_bancaria.cta_bc_id}])
        TransaccionBancaria.objects.filter(numero_operacion='CH-P-3').update(estado='D')

        respuesta = self.cliente_http.post(reverse('ordenpago_anular', args=[op.pk]))
        self.assertEqual(respuesta.status_code, 409)
        self.assertIn('el banco ya debitó', respuesta.content.decode())

        op.refresh_from_db()
        self.assertFalse(op.anulado)

    def test_reimpresion_pdf_incluye_todo_lo_vinculado(self):
        op = self._crear_op(
            aplicaciones=[{'id': self.factura.compras_id, 'importe': 9000}],
            valores=[
                {'categoria': 'EFE-ARS', 'importe': 9000},
                {'categoria': 'RET', 'medio_pago_id': self.medio_ret.id, 'importe': 1000,
                 'numero_comprobante': 'CERT-77', 'fecha': '2026-07-27', 'regimen': '116',
                 'base': 10000},
            ])

        respuesta = self.cliente_http.get(reverse('ordenpago_pdf', args=[op.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')
        self.assertGreater(len(respuesta.content), 1000)

    def test_listado_solo_muestra_ordenes_de_la_empresa_activa(self):
        """Aislamiento multi-tenant también en la consulta."""
        self._crear_op(valores=[{'categoria': 'EFE-ARS', 'importe': 7777}])

        otra = Empresa.objects.create(
            nombre="AJENA SA", cuit="30999888772", direccion="X", correo="x@x.com")
        sesion = self.cliente_http.session
        sesion['empresa_id'] = otra.id
        sesion.save()

        respuesta = self.cliente_http.get(
            reverse('ordenpago_grilla'), {'desde': '2026-07-01', 'hasta': '2026-07-31'})
        self.assertNotIn('7.777,00', respuesta.content.decode())

    def test_usuario_no_administrador_no_puede_anular(self):
        op = self._crear_op(valores=[{'categoria': 'EFE-ARS', 'importe': 5000}])
        operario = User.objects.create_user(username="operario1", password="clave", is_staff=False)
        cli = Client()
        cli.force_login(operario)
        s = cli.session
        s['empresa_id'] = self.empresa.id
        s.save()

        respuesta = cli.post(reverse('ordenpago_anular', args=[op.pk]))
        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("Solamente los usuarios administradores pueden anular", respuesta.content.decode())

