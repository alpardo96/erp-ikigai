from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal

from empresas.models import Empresa, Sucursal, Ejercicio
from facturacion.models import ClienteProveedor, TipoComprobante, Venta, Compra

User = get_user_model()

class SaldosTestCase(TestCase):
    def setUp(self):
        # 1. Crear Usuario
        self.usuario = User.objects.create_user(
            username="testuser",
            password="testpassword"
        )
        
        # 2. Crear Empresa
        self.empresa = Empresa.objects.create(
            nombre="EMPRESA DE TEST SAS",
            cuit="30123456789",
            direccion="Calle Ficticia 123",
            correo="test@empresa.com"
        )
        
        # 3. Crear Sucursal
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa,
            nombre="CENTRAL",
            direccion="Calle Ficticia 123"
        )
        
        # 4. Crear Ejercicio Fiscal
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa,
            ejercicio="Ejercicio Test 2026",
            inicio=timezone.now().date() - timezone.timedelta(days=30),
            cierre=timezone.now().date() + timezone.timedelta(days=30)
        )
        
        # 5. Crear Tipos de Comprobante
        self.tipo_factura_a = TipoComprobante.objects.create(
            codigo="001",
            detalle="FACTURA A",
            signo=1,
            estado=True
        )
        
        # 6. Crear Cliente
        self.cliente = ClienteProveedor.objects.create(
            razon_social="CLIENTE RESPONSABLE INSCRIPTO",
            cuit="30987654321",
            tipo_entidad=1,  # Cliente
            saldo_inicial=Decimal("1000.00"),
            saldo=Decimal("1000.00"),
            empresa=self.empresa
        )
        
        # 7. Crear Proveedor
        self.proveedor = ClienteProveedor.objects.create(
            razon_social="PROVEEDOR S.A.",
            cuit="30111111112",
            tipo_entidad=2,  # Proveedor
            saldo_inicial=Decimal("0.00"),
            saldo=Decimal("0.00"),
            empresa=self.empresa
        )

    def test_saldo_cliente_recalculo(self):
        """
        Verifica el recalculo de saldos de cliente ante creación, edición,
        cobro parcial, anulación y eliminación de ventas.
        """
        # 1. El saldo inicial debe ser $1000
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.saldo, Decimal("1000.00"))
        
        # 2. Crear una Venta por $5000 (sin cobrar nada)
        venta = Venta.objects.create(
            fecha=timezone.localdate(),
            tipo=self.tipo_factura_a,
            punto=1,
            numero=101,
            cliente=self.cliente,
            neto=Decimal("5000.00"),
            total=Decimal("5000.00"),
            cobrado=Decimal("0.00"),
            saldo=Decimal("5000.00"),
            estado=0,  # Activa
            usuario=self.usuario,
            sucursal=self.sucursal,
            empresa=self.empresa,
            ejercicio=self.ejercicio
        )
        
        # Al crearse la venta, la signal debe recalcular el saldo a $6000
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.saldo, Decimal("6000.00"))
        
        # 3. Registrar un cobro parcial de $2000 en la venta
        venta.cobrado = Decimal("2000.00")
        venta.save()
        
        # El saldo debe bajar a $4000 ($1000 inicial + $3000 restante)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.saldo, Decimal("4000.00"))
        
        # 4. Anular la venta (cambiar estado a 1)
        venta.estado = 1  # Anulada
        venta.save()
        
        # El saldo debe volver a $1000, ya que las ventas anuladas no computan
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.saldo, Decimal("1000.00"))
        
        # 5. Activar la venta y luego eliminarla
        venta.estado = 0
        venta.save()
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.saldo, Decimal("4000.00"))
        
        venta.delete()
        
        # El saldo debe volver a $1000
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.saldo, Decimal("1000.00"))

    def test_saldo_proveedor_recalculo(self):
        """Saldo de proveedor con la fórmula unificada (Plan 035 §1.4).

        Convención de signos: NEGATIVO = le debemos. Una compra mueve el saldo hacia negativo;
        la Orden de Pago lo acerca a cero.
        """
        # 1. El saldo inicial debe ser $0
        self.proveedor.refresh_from_db()
        self.assertEqual(self.proveedor.saldo, Decimal("0.00"))

        # 2. Crear una Compra por $3000 -> le debemos 3000
        compra = Compra.objects.create(
            fecha=timezone.now().date(),
            tipo=self.tipo_factura_a,
            punto=1,
            numero=201,
            proveedor=self.proveedor,
            total=Decimal("3000.00"),
            pagado=Decimal("0.00"),
            saldo=Decimal("3000.00"),
            usuario=self.usuario,
            sucursal=self.sucursal,
            empresa=self.empresa,
            ejercicio=self.ejercicio
        )

        self.proveedor.refresh_from_db()
        self.assertEqual(self.proveedor.saldo, Decimal("-3000.00"))

        # 3. El saldo de la ENTIDAD no se mueve tocando `pagado` a mano: sólo lo mueven los
        #    comprobantes. El saldo de la FACTURA, en cambio, se deriva de sus aplicaciones.
        compra.refresh_from_db()
        self.assertEqual(compra.saldo, Decimal("3000.00"))
        self.assertEqual(compra.pagado, Decimal("0.00"))

        # 4. Eliminar la compra -> el saldo vuelve a $0
        compra.delete()

        self.proveedor.refresh_from_db()
        self.assertEqual(self.proveedor.saldo, Decimal("0.00"))

    def test_saldo_compra_derivado_de_aplicaciones(self):
        """`pagado`/`saldo` de una compra se derivan de sus OrdenPagoAplicacion (§1.3).

        Cubre el bug B1: antes `pagado` no se actualizaba nunca y el saldo se decrementaba con
        `-=`, así que ambos campos derivaban por caminos distintos.
        """
        from tesoreria.models import OrdenPago, OrdenPagoAplicacion
        from contable.services.saldos import recalcular_saldo_compra

        compra = Compra.objects.create(
            fecha=timezone.localdate(), tipo=self.tipo_factura_a, punto=1, numero=301,
            proveedor=self.proveedor, total=Decimal("10000.00"),
            pagado=Decimal("0.00"), saldo=Decimal("10000.00"),
            usuario=self.usuario, sucursal=self.sucursal,
            empresa=self.empresa, ejercicio=self.ejercicio
        )
        op = OrdenPago.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, ejercicio=self.ejercicio,
            proveedor=self.proveedor, fecha=timezone.localdate(), punto=1,
            total=Decimal("4000.00"), creado_por=self.usuario, modificado_por=self.usuario
        )

        OrdenPagoAplicacion.objects.create(
            orden_pago=op, compra=compra,
            importe=Decimal("4000.00"), importe_pesos=Decimal("4000.00"))
        recalcular_saldo_compra(compra.pk)

        compra.refresh_from_db()
        self.assertEqual(compra.pagado, Decimal("4000.00"))
        self.assertEqual(compra.saldo, Decimal("6000.00"))

        # Anular la OP devuelve el saldo: las aplicaciones de OP anuladas no computan.
        op.anulado = True
        op.save(update_fields=['anulado'])
        recalcular_saldo_compra(compra.pk)

        compra.refresh_from_db()
        self.assertEqual(compra.pagado, Decimal("0.00"))
        self.assertEqual(compra.saldo, Decimal("10000.00"))

    def test_editar_compra_pagada_no_resetea_saldo(self):
        """Bug B2: `recalcular_totales()` hacía `saldo = total - pagado` con `pagado` en 0,
        de modo que editar una compra ya pagada la dejaba figurando impaga por su total."""
        from tesoreria.models import OrdenPago, OrdenPagoAplicacion
        from contable.services.saldos import recalcular_saldo_compra

        compra = Compra.objects.create(
            fecha=timezone.localdate(), tipo=self.tipo_factura_a, punto=1, numero=302,
            proveedor=self.proveedor, subtotal=Decimal("1000.00"), neto=Decimal("1000.00"),
            total=Decimal("1000.00"), pagado=Decimal("0.00"), saldo=Decimal("1000.00"),
            usuario=self.usuario, sucursal=self.sucursal,
            empresa=self.empresa, ejercicio=self.ejercicio
        )
        op = OrdenPago.objects.create(
            empresa=self.empresa, sucursal=self.sucursal, ejercicio=self.ejercicio,
            proveedor=self.proveedor, fecha=timezone.localdate(), punto=1,
            total=Decimal("1000.00"), creado_por=self.usuario, modificado_por=self.usuario
        )
        OrdenPagoAplicacion.objects.create(
            orden_pago=op, compra=compra,
            importe=Decimal("1000.00"), importe_pesos=Decimal("1000.00"))
        recalcular_saldo_compra(compra.pk)

        # Editar la compra (sin ítems el total queda en 0 + conceptos de cabecera)
        compra.refresh_from_db()
        self.assertEqual(compra.saldo, Decimal("0.00"))

        compra.recalcular_totales()

        compra.refresh_from_db()
        # Lo aplicado se conserva: el saldo no vuelve a ser el total.
        self.assertEqual(compra.pagado, Decimal("1000.00"))
        self.assertEqual(compra.saldo, compra.total - Decimal("1000.00"))
