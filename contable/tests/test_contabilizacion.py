from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from decimal import Decimal

from empresas.models import Empresa, Ejercicio, Sucursal
from contable.models import Asiento, AsientoLinea, Cuenta, ParametrosContables
from facturacion.models import Venta, VentaItem, Compra, CompraItem, TipoComprobante, ClienteProveedor
from productos.models import Producto, Rubro
from contable.services.contabilizacion import (
    contabilizar_venta_individual,
    contabilizar_compras,
    consolidar_ventas_diarias,
    anular_asiento_de_comprobante
)

User = get_user_model()

class ContabilizacionTestCase(TestCase):
    """
    Suite de pruebas unitarias para la automatización contable (Fase 3).
    Garantiza que la lógica de inmutabilidad, multi-actividad y alta transaccionalidad
    funcione perfectamente bajo las reglas de negocio del ERP.
    """

    def setUp(self):
        # 1. Crear Usuario de Auditoría
        self.usuario = User.objects.create_user(
            username="contador_test",
            password="securepassword123"
        )
        
        # 2. Crear Empresa de Test
        self.empresa = Empresa.objects.create(
            nombre="FRACCIONADORA Y DISTRIBUIDORA IKIGAI SAS",
            cuit="30777777779",
            direccion="Av. Belgrano 1230",
            correo="administracion@ikigai.com"
        )
        
        # 3. Crear Sucursal
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa,
            nombre="Sucursal Central",
            direccion="Av. Belgrano 1230",
            telefono="0381-123456"
        )
        
        # 4. Crear Ejercicio Fiscal Activo 2026
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa,
            ejercicio="Ejercicio Anual 2026",
            inicio=timezone.datetime(2026, 1, 1).date(),
            cierre=timezone.datetime(2026, 12, 31).date()
        )
        
        # 5. Crear Cuentas Contables Imputables
        self.cta_caja = Cuenta.objects.create(jerarquia="1.1.1.01", cuenta="Caja Principal", imputable=1, tipo="A", empresa=self.empresa)
        self.cta_clientes = Cuenta.objects.create(jerarquia="1.1.2.01", cuenta="Deudores por Ventas", imputable=1, tipo="A", empresa=self.empresa)
        self.cta_proveedores = Cuenta.objects.create(jerarquia="2.1.1.01", cuenta="Proveedores Locales", imputable=1, tipo="P", empresa=self.empresa)
        
        self.cta_iva_debito = Cuenta.objects.create(jerarquia="2.1.2.01", cuenta="IVA Débito Fiscal", imputable=1, tipo="P", empresa=self.empresa)
        self.cta_iva_credito = Cuenta.objects.create(jerarquia="1.1.3.01", cuenta="IVA Crédito Fiscal", imputable=1, tipo="A", empresa=self.empresa)
        self.cta_percep_iibb = Cuenta.objects.create(jerarquia="1.1.3.05", cuenta="Percepciones IIBB Sufridas", imputable=1, tipo="A", empresa=self.empresa)
        
        self.cta_ventas_gen = Cuenta.objects.create(jerarquia="4.1.1.01", cuenta="Ventas Mercaderías Generales", imputable=1, tipo="R", empresa=self.empresa)
        self.cta_ventas_esp = Cuenta.objects.create(jerarquia="4.1.1.02", cuenta="Ventas Especiales Josen", imputable=1, tipo="R", empresa=self.empresa)
        
        self.cta_compras_gen = Cuenta.objects.create(jerarquia="5.1.1.01", cuenta="Compras Mercaderías", imputable=1, tipo="R", empresa=self.empresa)

        # 6. Configurar Parámetros Contables por Empresa
        self.parametros = ParametrosContables.objects.create(
            empresa=self.empresa,
            cta_iva_debito=self.cta_iva_debito,
            cta_iva_credito=self.cta_iva_credito,
            cta_ret_iibb=self.cta_percep_iibb,
            cta_caja=self.cta_caja,
            cta_ventas=self.cta_ventas_gen,
            cta_compras=self.cta_compras_gen,
            cta_clientes_default=self.cta_clientes,
            cta_proveedores_default=self.cta_proveedores,
            metodo_contabilizacion_ventas=1  # Por defecto: Individual
        )

        # 7. Crear Rubros y Productos
        # Rubro Común (Ventas van a la cuenta general de ventas)
        self.rubro_comun = Rubro.objects.create(empresa=self.empresa, detalle="Rubro General", margen=30)
        
        # Rubro Especial (Ventas van a la cuenta de ventas especiales)
        self.rubro_especial = Rubro.objects.create(
            empresa=self.empresa,
            detalle="Rubro Josen Especial",
            margen=40,
            cta_ventas=self.cta_ventas_esp
        )

        self.producto_comun = Producto.objects.create(
            empresa=self.empresa, detalle="Azúcar Ikigai Común 1kg", rubro=self.rubro_comun, alic_iva=21.0
        )
        self.producto_especial = Producto.objects.create(
            empresa=self.empresa, detalle="Licor Especial Josen 750ml", rubro=self.rubro_especial, alic_iva=21.0
        )

        # 8. Crear Clientes y Proveedores
        self.cliente = ClienteProveedor.objects.create(
            razon_social="DISTRIBUIDORA SUR SRL",
            tipo_documento="80",
            cuit="30987654321",
            tipo_entidad=1,  # Cliente
            empresa=self.empresa
        )
        
        self.proveedor = ClienteProveedor.objects.create(
            razon_social="INGENIO ARCOR SA",
            tipo_documento="80",
            cuit="30112223334",
            tipo_entidad=2,  # Proveedor
            empresa=self.empresa
        )

        # 9. Tipos de Comprobante
        self.tipo_factura_a, _ = TipoComprobante.objects.get_or_create(
            codigo="FAC",
            defaults={'detalle': "Factura A", 'signo': 1}
        )

    def test_contabilizacion_individual_venta_por_rubros(self):
        """
        Verifica que al guardar una venta activa con el método INDIVIDUAL se genere
        el Asiento Contable desglosando los netos en el Haber en base a las cuentas del Rubro.
        """
        # Desactivamos signals de forma temporal o las dejamos actuar. Dado que signals.py
        # tiene conectado 'post_save', guardar la venta directamente llamará a 'contabilizar_venta_individual'
        # de forma automática. ¡Excelente para probar la integración real de signals!
        
        # Crear Venta
        venta = Venta.objects.create(
            fecha=timezone.datetime(2026, 5, 20).date(),
            tipo=self.tipo_factura_a,
            punto=1,
            numero=1054,
            cliente=self.cliente,
            neto=Decimal("2000.00"),
            iva=Decimal("420.00"),
            total=Decimal("2420.00"),
            saldo=Decimal("2420.00"),
            estado=0,  # Activa
            usuario=self.usuario,
            sucursal=self.sucursal,
            empresa=self.empresa,
            ejercicio=self.ejercicio
        )

        # Crear ítems de la venta
        # 1. Ítem común (imputa a cta_ventas general)
        VentaItem.objects.create(
            venta=venta,
            producto=self.producto_comun,
            cantidad=Decimal("10.00"),
            precio_unitario=Decimal("100.00"),
            iva_alicuota=Decimal("21.00"),
            total=Decimal("1210.00")
        )

        # 2. Ítem especial (imputa a cta_ventas_esp)
        VentaItem.objects.create(
            venta=venta,
            producto=self.producto_especial,
            cantidad=Decimal("10.00"),
            precio_unitario=Decimal("100.00"),
            iva_alicuota=Decimal("21.00"),
            total=Decimal("1210.00")
        )

        # Forzar un guardado para que se actualicen totales y se dispare la señal
        venta.save()

        # Comprobar que la venta tenga un asiento contable asociado
        self.assertIsNotNone(venta.asiento_id)

        asiento = Asiento.objects.get(pk=venta.asiento_id)
        self.assertEqual(asiento.monto, Decimal("2420.00"))
        self.assertFalse(asiento.anulado)

        # Validar líneas del asiento contable
        lineas = AsientoLinea.objects.filter(asiento=asiento).order_by('orden')
        self.assertEqual(lineas.count(), 4)  # 1 Debe (Clientes) + 3 Haber (Vta Gen + Vta Esp + IVA)

        # Línea 1: Debe Clientes
        l_clientes = lineas[0]
        self.assertEqual(l_clientes.cuenta, self.cta_clientes)
        self.assertEqual(l_clientes.debe, Decimal("2420.00"))
        self.assertEqual(l_clientes.haber, Decimal("0.00"))

        # Líneas de Haber (desglosadas por cuenta de rubro)
        # Neto de ítem común: 1210 / 1.21 = 1000.00 -> cta_ventas_gen
        l_vta_gen = lineas.filter(cuenta=self.cta_ventas_gen).first()
        self.assertIsNotNone(l_vta_gen)
        self.assertEqual(l_vta_gen.haber, Decimal("1000.00"))

        # Neto de ítem especial: 1210 / 1.21 = 1000.00 -> cta_ventas_esp
        l_vta_esp = lineas.filter(cuenta=self.cta_ventas_esp).first()
        self.assertIsNotNone(l_vta_esp)
        self.assertEqual(l_vta_esp.haber, Decimal("1000.00"))

        # Línea de IVA Débito Fiscal
        l_iva = lineas.filter(cuenta=self.cta_iva_debito).first()
        self.assertIsNotNone(l_iva)
        self.assertEqual(l_iva.haber, Decimal("420.00"))

    def test_contabilizacion_compra_por_rubros(self):
        """
        Verifica que al guardar una compra se genere de forma atómica su asiento
        contable desglosando los gastos según la cuenta de rubro.
        """
        compra = Compra.objects.create(
            fecha=timezone.datetime(2026, 5, 20).date(),
            tipo=self.tipo_factura_a,
            punto=1,
            numero=2098,
            proveedor=self.proveedor,
            neto=Decimal("1000.00"),
            iva=Decimal("210.00"),
            total=Decimal("1210.00"),
            saldo=Decimal("1210.00"),
            usuario=self.usuario,
            sucursal=self.sucursal,
            empresa=self.empresa,
            ejercicio=self.ejercicio
        )

        # Crear ítem discriminado (imputa a cta_compras_gen).
        # OJO: en COMPRAS `item.total` es el NETO de la línea (10 x 100 = 1000), sin IVA. Es la
        # convención opuesta a la de VENTAS, donde `item.total` viene con IVA incluido.
        # Cargar acá 1210 hacía que `recalcular_totales()` lo tomara como neto y le sumara IVA
        # otra vez (1210 + 254,10 = 1464,10), descuadrando el asiento contra lo esperado.
        CompraItem.objects.create(
            compra=compra,
            producto=self.producto_comun,
            cantidad=Decimal("10.00"),
            precio_unitario=Decimal("100.00"),
            iva_alicuota=Decimal("21.00"),
            total=Decimal("1000.00")
        )

        compra.save()

        # Verificar generación de asiento
        self.assertIsNotNone(compra.asiento_id)

        asiento = Asiento.objects.get(pk=compra.asiento_id)
        self.assertEqual(asiento.monto, Decimal("1210.00"))

        lineas = AsientoLinea.objects.filter(asiento=asiento).order_by('orden')
        self.assertEqual(lineas.count(), 3)  # 1 Haber (Proveedores) + 2 Debe (Compras + IVA)

        # Haber: Proveedores
        l_prov = lineas[0]
        self.assertEqual(l_prov.cuenta, self.cta_proveedores)
        self.assertEqual(l_prov.haber, Decimal("1210.00"))

        # Debe: Compras
        l_cpra = lineas.filter(cuenta=self.cta_compras_gen).first()
        self.assertIsNotNone(l_cpra)
        self.assertEqual(l_cpra.debe, Decimal("1000.00"))

        # Debe: IVA Crédito Fiscal
        l_iva = lineas.filter(cuenta=self.cta_iva_credito).first()
        self.assertIsNotNone(l_iva)
        self.assertEqual(l_iva.debe, Decimal("210.00"))

    def test_anulacion_de_comprobante_no_borra_sino_anula(self):
        """
        Verifica que al marcar una venta como anulada (estado = 1), el asiento
        contable asociado NO se borre de DB, sino que se marque como anulado.
        Esto valida el principio de inmutabilidad contable y auditoría.
        """
        venta = Venta.objects.create(
            fecha=timezone.datetime(2026, 5, 20).date(),
            tipo=self.tipo_factura_a,
            punto=1,
            numero=1055,
            cliente=self.cliente,
            neto=Decimal("1000.00"),
            iva=Decimal("210.00"),
            total=Decimal("1210.00"),
            estado=0,
            usuario=self.usuario,
            sucursal=self.sucursal,
            empresa=self.empresa,
            ejercicio=self.ejercicio
        )

        VentaItem.objects.create(
            venta=venta,
            producto=self.producto_comun,
            cantidad=Decimal("10.00"),
            precio_unitario=Decimal("100.00"),
            iva_alicuota=Decimal("21.00"),
            total=Decimal("1210.00")
        )
        venta.save()

        asiento_id = venta.asiento_id
        self.assertIsNotNone(asiento_id)

        # Simulamos la anulación de la factura modificando el estado
        venta.estado = 1  # 1 = Anulada
        venta.save()

        # Comprobar que el asiento no se eliminó físicamente de la base de datos
        asiento = Asiento.objects.get(pk=asiento_id)
        self.assertTrue(asiento.anulado)
        self.assertIsNotNone(asiento.fec_anulacion)
        
        # Las líneas deben persistir intactas
        self.assertEqual(AsientoLinea.objects.filter(asiento=asiento).count(), 3)

    def test_consolidacion_resumen_diario(self):
        """
        Verifica el método de alta transaccionalidad:
        1. Modifica la configuración de la empresa a método Consolidado.
        2. Crea varias ventas del mismo día, las cuales no deben generar asientos síncronos.
        3. Invoca la consolidación en lote y verifica que se genere un ÚNICO asiento de resumen.
        """
        # Configurar método Consolidado Diario
        self.parametros.metodo_contabilizacion_ventas = 2  # Consolidado
        self.parametros.save()

        # Crear 3 ventas de la misma fecha
        ventas = []
        for i in range(3):
            v = Venta.objects.create(
                fecha=timezone.datetime(2026, 5, 22).date(),
                tipo=self.tipo_factura_a,
                punto=1,
                numero=3000 + i,
                cliente=self.cliente,
                neto=Decimal("1000.00"),
                iva=Decimal("210.00"),
                total=Decimal("1210.00"),
                estado=0,
                usuario=self.usuario,
                sucursal=self.sucursal,
                empresa=self.empresa,
                ejercicio=self.ejercicio
            )
            VentaItem.objects.create(
                venta=v,
                producto=self.producto_comun,
                cantidad=Decimal("10.00"),
                precio_unitario=Decimal("100.00"),
                iva_alicuota=Decimal("21.00"),
                total=Decimal("1210.00")
            )
            v.save()
            ventas.append(v)

        # Confirmar que ninguna venta haya generado asiento contable al instante
        for v in ventas:
            v.refresh_from_db()
            self.assertIsNone(v.asiento_id)

        # Ejecutar la consolidación en lote para el final del día
        asiento_resumen = consolidar_ventas_diarias(
            empresa=self.empresa,
            fecha=timezone.datetime(2026, 5, 22).date(),
            sucursal=self.sucursal
        )

        self.assertIsNotNone(asiento_resumen)
        self.assertEqual(asiento_resumen.monto, Decimal("3630.00")) # 1210 * 3
        self.assertEqual(asiento_resumen.concepto, "ASIENTO RESUMEN DIARIO - SUC. SUCURSAL CENTRAL - 22/05/2026")

        # Verificar que todas las ventas del lote ahora referencien al mismo asiento resumen único
        for v in ventas:
            v.refresh_from_db()
            self.assertEqual(v.asiento_id, asiento_resumen.asiento_id)

        # Validar líneas del asiento resumen diario
        lineas = AsientoLinea.objects.filter(asiento=asiento_resumen).order_by('orden')
        self.assertEqual(lineas.count(), 3)  # 1 Debe (Clientes) + 2 Haber (Ventas + IVA)

        # Debe: Deudores por ventas consolidado
        self.assertEqual(lineas[0].cuenta, self.cta_clientes)
        self.assertEqual(lineas[0].debe, Decimal("3630.00"))

        # Haber: Ventas consolidado
        l_vta = lineas.filter(cuenta=self.cta_ventas_gen).first()
        self.assertIsNotNone(l_vta)
        self.assertEqual(l_vta.haber, Decimal("3000.00")) # 1000 * 3

        # Haber: IVA Débito Fiscal consolidado
        l_iva = lineas.filter(cuenta=self.cta_iva_debito).first()
        self.assertIsNotNone(l_iva)
        self.assertEqual(l_iva.haber, Decimal("630.00")) # 210 * 3
