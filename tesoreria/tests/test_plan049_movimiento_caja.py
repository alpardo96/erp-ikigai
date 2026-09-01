"""Plan 049 — Vínculo contable de `tesoreria_movimiento_caja`.

Cubre los campos que se agregaron para poder construir el Estado de Origen y Aplicación de
Fondos: `asiento`, `cuenta`, `cli_pro`, `empresa` y el cambio de `fecha` a la del comprobante.
"""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from contable.models import Asiento, AsientoLinea, Cuenta, ParametrosContables
from empresas.models import Empresa, Ejercicio, Sucursal
from facturacion.models import ClienteProveedor
from tesoreria.models import Caja, CajaSesion, MedioPago, MovimientoCaja
from tesoreria.services.imputacion import (
    condic_por_comprobante,
    cuenta_principal_del_asiento,
)

User = get_user_model()


class BasePlan049(TestCase):
    """Plan de cuentas mínimo con disponibilidades marcadas y medios de pago configurados."""

    def setUp(self):
        self.usuario = User.objects.create_user(username="tesorero", password="clave")

        self.empresa = Empresa.objects.create(
            nombre="FONDOS SA", cuit="30555444332", direccion="C 1", correo="f@t.com",
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
        self.cta_valores = cuenta("111002", "VALORES EN CARTERA", "A", "VAL")
        self.cta_banco = cuenta("111011", "BANCO NACION", "A", "BCO")
        self.cta_clientes = cuenta("112001", "DEUDORES POR VENTAS", "A")
        self.cta_proveedores = cuenta("211001", "PROVEEDORES VARIOS", "P")
        self.cta_ingresos = cuenta("511001", "INGRESOS VARIOS", "R")
        self.cta_gastos = cuenta("531001", "GASTOS VARIOS", "R")

        ParametrosContables.objects.create(
            empresa=self.empresa,
            cta_caja=self.cta_caja,
            cta_caja_central=self.cta_caja,
            cta_valores_cartera=self.cta_valores,
            cta_clientes_default=self.cta_clientes,
            cta_proveedores_default=self.cta_proveedores,
        )

        self.cliente = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="CLIENTE UNO SRL", cuit="20111111112",
            cta_pat=self.cta_clientes.id, cta_res=self.cta_ingresos.id,
        )
        self.proveedor = ClienteProveedor.objects.create(
            empresa=self.empresa, razon_social="PROVEEDOR UNO SA", cuit="30111111113",
            tipo_entidad=2, cta_pat=self.cta_proveedores.id, cta_res=self.cta_gastos.id,
        )

        MedioPago.objects.create(empresa=self.empresa, codigo="EFE", nombre="Efectivo",
                                 categoria="EFE", cuenta_contable=self.cta_caja)
        MedioPago.objects.create(empresa=self.empresa, codigo="CHQ", nombre="Cheque",
                                 categoria="CHQ", cuenta_contable=self.cta_valores)
        MedioPago.objects.create(empresa=self.empresa, codigo="TRA", nombre="Transferencia",
                                 categoria="TRA", cuenta_contable=self.cta_banco)

        self.cliente_http = Client()
        self.cliente_http.force_login(self.usuario)
        sesion = self.cliente_http.session
        sesion['empresa_id'] = self.empresa.id
        sesion['sucursal_id'] = self.sucursal.id
        sesion['ejercicio_id'] = self.ejercicio.id
        sesion.save()

    # ------------------------------------------------------------------ helpers
    def postear_recibo(self, **extra):
        payload = {
            'cliente_id': self.cliente.codigo_id,
            'sucursal_id': self.sucursal.id,
            'fecha': '2026-07-27',
            'punto': 1, 'tipo': 'C', 'condic': 1, 'cotizacion': 1,
            'observaciones': '', 'aplicaciones': [], 'imputaciones': [], 'valores': [],
        }
        payload.update(extra)
        return json.loads(self.cliente_http.post(
            reverse('htmx_procesar_recibo'),
            data=json.dumps(payload), content_type="application/json",
        ).content)

    def postear_op(self, **extra):
        payload = {
            'proveedor_id': self.proveedor.codigo_id,
            'sucursal_id': self.sucursal.id,
            'fecha': '2026-07-27',
            'punto': 1, 'tipo': 'P', 'condic': 1, 'cotizacion': 1,
            'observaciones': '', 'aplicaciones': [], 'imputaciones': [], 'valores': [],
        }
        payload.update(extra)
        return json.loads(self.cliente_http.post(
            reverse('htmx_procesar_orden_pago'),
            data=json.dumps(payload), content_type="application/json",
        ).content)


class ServicioImputacionTest(BasePlan049):
    """Unitarias del servicio: no dependen de ningún circuito."""

    def _asiento(self, *lineas):
        asiento = Asiento.objects.create(
            empresa=self.empresa, ejercicio=self.ejercicio, fecha=timezone.localdate(),
            concepto="PRUEBA", monto=Decimal("100.00"),
        )
        for orden, (cta, debe, haber) in enumerate(lineas, start=1):
            AsientoLinea.objects.create(asiento=asiento, orden=orden, cuenta=cta,
                                        debe=debe, haber=haber)
        return asiento

    def test_descarta_las_cuentas_de_disponibilidad(self):
        """Caja y banco son el BOLSILLO por donde pasa la plata, no el origen ni la aplicación."""
        asiento = self._asiento(
            (self.cta_caja, Decimal("1000"), 0),
            (self.cta_clientes, 0, Decimal("1000")),
        )
        self.assertEqual(cuenta_principal_del_asiento(asiento), self.cta_clientes)

    def test_devuelve_la_contrapartida_de_mayor_importe(self):
        asiento = self._asiento(
            (self.cta_caja, Decimal("1000"), 0),
            (self.cta_gastos, 0, Decimal("600")),
            (self.cta_ingresos, 0, Decimal("400")),
        )
        self.assertEqual(cuenta_principal_del_asiento(asiento), self.cta_gastos)

    def test_desempate_determinístico_por_id_de_cuenta(self):
        """Dos corridas del backfill tienen que dar lo mismo ante un empate de importes."""
        asiento = self._asiento(
            (self.cta_caja, Decimal("1000"), 0),
            (self.cta_ingresos, 0, Decimal("500")),
            (self.cta_gastos, 0, Decimal("500")),
        )
        menor_id = min(self.cta_ingresos, self.cta_gastos, key=lambda c: c.id)
        self.assertEqual(cuenta_principal_del_asiento(asiento), menor_id)

    def test_sin_contrapartida_devuelve_none(self):
        """Traslado puro entre disponibilidades: no hay origen ni aplicación de fondos."""
        asiento = self._asiento(
            (self.cta_banco, Decimal("1000"), 0),
            (self.cta_caja, 0, Decimal("1000")),
        )
        self.assertIsNone(cuenta_principal_del_asiento(asiento))

    def test_asiento_nulo_devuelve_none(self):
        self.assertIsNone(cuenta_principal_del_asiento(None))

    def test_condic_por_comprobante(self):
        self.assertEqual(condic_por_comprobante('PRE'), 2)
        self.assertEqual(condic_por_comprobante('pre'), 2)
        self.assertEqual(condic_por_comprobante('6'), 1)    # Factura B
        self.assertEqual(condic_por_comprobante('FA'), 1)
        self.assertEqual(condic_por_comprobante(None), 1)


class ReciboTest(BasePlan049):

    def test_fecha_es_la_del_comprobante_y_no_la_de_carga(self):
        """El caso que rompía cualquier reporte por período: comprobante retroactivo."""
        datos = self.postear_recibo(
            fecha='2026-05-15',
            valores=[{'categoria': 'EFE-ARS', 'importe': 15000}],
        )
        self.assertEqual(datos['status'], 'success', datos)

        mov = MovimientoCaja.objects.get(recibo__numero=datos['recibo_id'])
        asiento = Asiento.objects.get(pk=datos['asiento_id'])

        self.assertEqual(str(mov.fecha), '2026-05-15')
        self.assertEqual(mov.fecha, asiento.fecha, "Debe coincidir con la fecha del asiento")
        # `fecha_creacion` es un timestamp con zona (se guarda en UTC), así que hay que llevarlo
        # a hora local antes de comparar el día: cerca de medianoche el día UTC ya es el siguiente.
        self.assertEqual(timezone.localtime(mov.fecha_creacion).date(), timezone.localdate(),
                         "La fecha de carga sigue disponible en fecha_creacion")
        self.assertNotEqual(mov.fecha, timezone.localdate(),
                            "El movimiento NO debe quedar fechado el día de carga")

    def test_cobranza_a_cliente_vincula_asiento_cuenta_y_clipro(self):
        datos = self.postear_recibo(valores=[{'categoria': 'EFE-ARS', 'importe': 15000}])
        mov = MovimientoCaja.objects.get(recibo__numero=datos['recibo_id'])

        self.assertEqual(mov.asiento_id, datos['asiento_id'])
        self.assertEqual(mov.cli_pro_id, self.cliente.codigo_id)
        self.assertEqual(mov.empresa_id, self.empresa.id)
        # La contrapartida del cobro es la cuenta patrimonial del cliente, no la caja.
        self.assertEqual(mov.cuenta_id, self.cta_clientes.id)

    def test_recibo_simple_guarda_la_cuenta_de_mayor_importe(self):
        """Con varias imputaciones, `cuenta` guarda la mayor; el desglose queda en el asiento."""
        datos = self.postear_recibo(
            tipo='S',
            valores=[{'categoria': 'EFE-ARS', 'importe': 10000}],
            imputaciones=[
                {'cuenta_contable_id': self.cta_ingresos.id, 'importe': 6000},
                {'cuenta_contable_id': self.cta_gastos.id, 'importe': 4000},
            ],
        )
        self.assertEqual(datos['status'], 'success', datos)

        mov = MovimientoCaja.objects.get(recibo__numero=datos['recibo_id'])
        self.assertEqual(mov.cuenta_id, self.cta_ingresos.id, "Debe quedar la del 60 %")

        # Lo importante: el asiento conserva LAS DOS cuentas con su importe exacto. Es de ahí de
        # donde los reportes de fondos toman los números, no de `cuenta`.
        cuentas_haber = {l.cuenta_id: l.haber for l in mov.asiento.lineas.filter(haber__gt=0)}
        self.assertEqual(cuentas_haber[self.cta_ingresos.id], Decimal("6000.00"))
        self.assertEqual(cuentas_haber[self.cta_gastos.id], Decimal("4000.00"))

    def test_recontabilizar_reapunta_el_movimiento_al_asiento_nuevo(self):
        from contable.services.contabilizacion import contabilizar_recibo
        from tesoreria.models import Recibo
        from tesoreria.services.imputacion import estampar_asiento

        datos = self.postear_recibo(valores=[{'categoria': 'EFE-ARS', 'importe': 15000}])
        recibo = Recibo.objects.get(numero=datos['recibo_id'])
        mov = MovimientoCaja.objects.get(recibo=recibo)
        asiento_viejo_id = mov.asiento_id

        asiento_nuevo = contabilizar_recibo(recibo)
        estampar_asiento(mov, asiento_nuevo)
        mov.refresh_from_db()

        self.assertNotEqual(mov.asiento_id, asiento_viejo_id)
        self.assertEqual(mov.asiento_id, asiento_nuevo.asiento_id)
        # El asiento anterior no se borra nunca: queda anulado, por trazabilidad.
        self.assertTrue(Asiento.objects.get(pk=asiento_viejo_id).anulado)


class OrdenPagoTest(BasePlan049):

    def test_pago_a_proveedor_vincula_asiento_cuenta_y_clipro(self):
        datos = self.postear_op(valores=[{'categoria': 'EFE-ARS', 'importe': 20000}])
        self.assertEqual(datos['status'], 'success', datos)

        mov = MovimientoCaja.objects.get(orden_pago__numero=datos['op_id'])
        self.assertEqual(mov.asiento_id, datos['asiento_id'])
        self.assertEqual(mov.cli_pro_id, self.proveedor.codigo_id)
        self.assertEqual(mov.empresa_id, self.empresa.id)
        self.assertEqual(mov.cuenta_id, self.cta_proveedores.id)
        self.assertEqual(str(mov.fecha), '2026-07-27')

    def test_op_simple_guarda_la_cuenta_de_mayor_importe(self):
        datos = self.postear_op(
            tipo='S',
            valores=[{'categoria': 'EFE-ARS', 'importe': 10000}],
            imputaciones=[
                {'cuenta_contable_id': self.cta_gastos.id, 'importe': 7000},
                {'cuenta_contable_id': self.cta_ingresos.id, 'importe': 3000},
            ],
        )
        self.assertEqual(datos['status'], 'success', datos)

        mov = MovimientoCaja.objects.get(orden_pago__numero=datos['op_id'])
        self.assertEqual(mov.cuenta_id, self.cta_gastos.id, "Debe quedar la del 70 %")


class CajaMostradorTest(BasePlan049):
    """Cierre de la deuda técnica de §10 del Plan 049.

    El asiento de la venta de mostrador se arma a mano (no vía `crear_asiento()`) y hasta ahora
    salía sin `condic` —quedaba en el default 1 aunque la venta fuera presupuestada— y sin
    `sesion_caja`, con lo cual el cobro no aparecía en el reporte de Caja Diaria.

    Se prueba con un comprobante PRE (Presupuesto) porque ese camino no llama a ARCA.
    """

    def setUp(self):
        super().setUp()
        from facturacion.models import Preventa, PreventaItem, TipoComprobante
        from productos.models import Producto, Rubro

        TipoComprobante.objects.create(codigo='PRE', detalle='PRESUPUESTO')

        parametros = ParametrosContables.objects.get(empresa=self.empresa)
        parametros.cta_ventas = self.cta_ingresos
        parametros.cta_iva_debito = self.cta_proveedores   # cualquier cuenta sirve acá
        parametros.save()

        rubro = Rubro.objects.create(empresa=self.empresa, detalle="GENERAL",
                                     cta_ventas=self.cta_ingresos)
        producto = Producto.objects.create(empresa=self.empresa, detalle="PRODUCTO UNO",
                                           rubro=rubro)

        self.caja_mostrador = Caja.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, nombre="MOSTRADOR", tipo='M')
        self.sesion_mostrador = CajaSesion.objects.create(
            caja=self.caja_mostrador, usuario=self.usuario)

        self.preventa = Preventa.objects.create(
            cliente=self.cliente, vendedor=self.usuario, empresa=self.empresa,
            sucursal=self.sucursal, neto=Decimal("1000.00"), total=Decimal("1210.00"),
        )
        PreventaItem.objects.create(
            preventa=self.preventa, producto=producto, cantidad=1,
            precio_unitario=Decimal("1210.00"), total=Decimal("1210.00"),
        )

    def _cobrar(self, condic):
        respuesta = self.cliente_http.post(
            reverse('htmx_caja_mostrador_procesar_cobro', args=[self.preventa.preventa_id]),
            data=json.dumps({'efectivo': 1210, 'condic': condic}),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        return MovimientoCaja.objects.get(sesion=self.sesion_mostrador)

    def test_venta_presupuestada_marca_condic_2_en_movimiento_y_asiento(self):
        movimiento = self._cobrar(condic=2)

        self.assertEqual(movimiento.condic, 2, "El movimiento de fondos debe ser Presupuestado")
        self.assertIsNotNone(movimiento.asiento_id)
        # El asiento HEREDA el condic del comprobante: antes quedaba fijo en 1.
        self.assertEqual(movimiento.asiento.condic, 2)
        self.assertEqual(movimiento.venta.condic, 2)

    def test_la_venta_de_mostrador_debita_la_cuenta_de_su_caja(self):
        """Plan 077 §E: el tercer camino del efectivo, el que faltaba unificar.

        La venta cobrada en el acto debitaba `cta_caja` mientras el retiro acreditaba
        `cta_caja_mostrador`: dos cuentas distintas que nunca neteaban. Ahora la cuenta la
        define LA CAJA, así que el cajero puede cerrar.
        """
        from contable.models import AsientoLinea, Cuenta

        cta_mostrador = Cuenta.objects.create(
            empresa=self.empresa, jerarquia="1.1.77", cuenta="CAJA MOSTRADOR 077",
            imputable=1)
        parametros = ParametrosContables.objects.get(empresa=self.empresa)
        parametros.cta_caja_mostrador = cta_mostrador
        parametros.save(update_fields=['cta_caja_mostrador'])

        # Presupuestada porque el setUp sólo carga el tipo 'PRE'. La línea del efectivo es
        # la misma en los dos casos: el condic no cambia a qué caja entró la plata.
        movimiento = self._cobrar(condic=2)

        debitadas = {l.cuenta_id for l in AsientoLinea.objects.filter(
            asiento_id=movimiento.asiento_id, debe__gt=0)}
        self.assertIn(cta_mostrador.id, debitadas,
                      "El efectivo de la venta no fue a la cuenta de la caja que lo cobró.")

    def test_el_asiento_queda_vinculado_a_la_caja(self):
        """Sin `sesion_caja` el cobro de mostrador no aparecía en el reporte de Caja Diaria."""
        movimiento = self._cobrar(condic=2)
        self.assertEqual(movimiento.asiento.sesion_caja_id, self.sesion_mostrador.id)
        self.assertEqual(movimiento.asiento.fecha, movimiento.fecha)

    def test_no_se_cuenta_dos_veces_en_la_caja_diaria(self):
        """Regresión del efecto colateral de estampar `sesion_caja`.

        Con el asiento ya vinculado a la caja, el cobro llega al reporte por sus DOS fuentes
        (`_lineas_desde_asientos` y `_lineas_desde_movimientos`). La deduplicación solo miraba
        `recibo` y `orden_pago`; los cobros de mostrador cuelgan de `venta`, así que se contaban
        dos veces. Ahora se deduplica por `MovimientoCaja.asiento_id`.
        """
        from tesoreria.services.caja_diaria import armar_caja_diaria

        self._cobrar(condic=2)
        resultado = armar_caja_diaria(self.sesion_mostrador)

        efectivo = sum(m['efectivo'] for m in resultado['movimientos'])
        self.assertEqual(efectivo, Decimal("1210.00"),
                         f"El cobro se contó más de una vez: {resultado['movimientos']}")
        self.assertEqual(resultado['saldos']['movimiento']['efectivo'], Decimal("1210.00"))
        self.assertEqual(resultado['saldos']['final']['neto'], Decimal("1210.00"))


class CajaDiariaOrdenamientoTest(BasePlan049):
    """Regresión: el reporte de Caja Diaria ordena juntas las filas de asientos y de movimientos.

    `armar_caja_diaria` arma una sola lista con las filas que salen de `Asiento.sesion_caja` y las
    que salen de `MovimientoCaja`, y la ordena por la tupla (fecha, id). Mientras
    `MovimientoCaja.fecha` fue `DateTimeField` y `Asiento.fecha` `DateField`, comparar las dos
    tuplas rompía con "'<' not supported between instances of 'datetime.datetime' and
    'datetime.date'" en cuanto una caja tenía movimientos de las dos fuentes. Al pasar `fecha` a
    `DateField` (Plan 049) los dos lados quedan del mismo tipo.
    """

    def test_convive_una_fila_de_asiento_con_una_de_movimiento(self):
        from tesoreria.models import MovimientoCajaDetalle
        from tesoreria.services.caja_diaria import armar_caja_diaria

        caja = Caja.objects.create(empresa=self.empresa, sucursal=self.sucursal,
                                   nombre="TESORERIA", tipo='T')
        sesion = CajaSesion.objects.create(caja=caja, usuario=self.usuario)

        # Fuente 1: un asiento estampado en la caja.
        asiento = Asiento.objects.create(
            empresa=self.empresa, ejercicio=self.ejercicio, fecha=timezone.localdate(),
            concepto="COMPRA CONTADO", monto=Decimal("500.00"), sesion_caja=sesion,
        )
        AsientoLinea.objects.create(asiento=asiento, orden=1, cuenta=self.cta_gastos,
                                    debe=Decimal("500"), haber=0)
        AsientoLinea.objects.create(asiento=asiento, orden=2, cuenta=self.cta_caja,
                                    debe=0, haber=Decimal("500"))

        # Fuente 2: un movimiento de caja sin asiento propio.
        movimiento = MovimientoCaja.objects.create(
            sesion=sesion, empresa=self.empresa, fecha=timezone.localdate(),
            tipo='I', importe=Decimal("300.00"), concepto="INGRESO SUELTO", condic=1,
        )
        MovimientoCajaDetalle.objects.create(
            movimiento_caja=movimiento,
            medio_pago=MedioPago.objects.get(empresa=self.empresa, categoria='EFE'),
            importe=Decimal("300.00"),
        )

        resultado = armar_caja_diaria(sesion)   # antes: TypeError al ordenar
        conceptos = [m['descripcion'] for m in resultado['movimientos']]
        self.assertIn("INGRESO SUELTO", conceptos)
        self.assertEqual(len(resultado['movimientos']), 2)


class CondicConstraintTest(BasePlan049):

    def _sesion(self):
        caja = Caja.objects.create(empresa=self.empresa, sucursal=self.sucursal,
                                   nombre="TESORERIA", tipo='T')
        return CajaSesion.objects.create(caja=caja, usuario=self.usuario)

    def _crear(self, condic):
        return MovimientoCaja.objects.create(
            sesion=self._sesion(), empresa=self.empresa, fecha=timezone.localdate(),
            tipo='I', importe=Decimal("100.00"), concepto="PRUEBA", condic=condic,
        )

    def test_admite_real_y_presupuestado(self):
        self.assertEqual(self._crear(1).condic, 1)
        self.assertEqual(self._crear(2).condic, 2)

    def test_rechaza_ajuste_auditoria_y_los_estructurales(self):
        """Un movimiento de FONDOS no puede ser Ajuste, Auditoría, Apertura, Refundición ni Cierre.

        El 3 lo paga el socio y no sale plata de la empresa; el 4 son ajustes del estudio; los
        5/6/7 los genera el sistema y no tocan caja. La regla va en la base, no en la vista.
        """
        for condic in (0, 3, 4, 5, 6, 7):
            with self.subTest(condic=condic):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        self._crear(condic)
