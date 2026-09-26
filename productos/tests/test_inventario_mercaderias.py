from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from empresas.models import Empresa, Sucursal
from productos.models import Producto, StockSucursal, TomaInventario, TomaInventarioItem, MovimientoStock
from productos.services.stock_service import recalcular_stock, aplicar_inventario_al_stock

User = get_user_model()


class InventarioMercaderiasTestCase(TestCase):
    """
    Pruebas unitarias para el Plan 095: Módulo de Toma de Inventarios y recálculo de stock.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='password')
        self.empresa = Empresa.objects.create(nombre="Empresa Test", tipo_actividad="ARMERIA")
        self.sucursal = Sucursal.objects.create(empresa=self.empresa, nombre="Central Test")
        
        # Producto de prueba con stock inicial = 10
        self.producto = Producto.objects.create(
            empresa=self.empresa,
            detalle="PISTOLA TEST CAL. 9MM",
            cod_prov="P-999"
        )
        StockSucursal.objects.create(
            producto=self.producto,
            sucursal=self.sucursal,
            stock_inicial=Decimal('10.00'),
            cantidad=Decimal('10.00')
        )

    def test_circuito_inventario_y_recalculo_stock(self):
        # 1. Stock disponible inicial debe ser 10
        stk = recalcular_stock(self.producto.id, self.sucursal.id)
        self.assertEqual(stk, Decimal('10.00'))

        # 2. Se crea un inventario físico parcial en BORRADOR
        # El sistema detecta stock teórico = 10, pero se contaron 7 (faltante de 3)
        inv = TomaInventario.objects.create(
            empresa=self.empresa,
            sucursal=self.sucursal,
            numero=1,
            fecha_toma=timezone.now(),
            tipo_alcance='PARCIAL',
            estado='BORRADOR',
            creado_por=self.user
        )
        item = TomaInventarioItem.objects.create(
            inventario=inv,
            producto=self.producto,
            stock_teorico=Decimal('10.00'),
            cantidad_contada=Decimal('7.00'),
            usuario_conteo=self.user
        )
        self.assertEqual(item.diferencia, Decimal('-3.00'))

        # 3. Mientras esté en BORRADOR, NO debe afectar el stock disponible
        stk_borrador = recalcular_stock(self.producto.id, self.sucursal.id)
        self.assertEqual(stk_borrador, Decimal('10.00'), "El inventario en borrador no debe alterar el stock")

        # 4. Pasa a PENDIENTE de autorización
        inv.estado = 'PENDIENTE'
        inv.save()
        stk_pendiente = recalcular_stock(self.producto.id, self.sucursal.id)
        self.assertEqual(stk_pendiente, Decimal('10.00'), "El inventario pendiente no debe alterar el stock")

        # 5. El autorizador aprueba y aplica el inventario al stock
        aplicar_inventario_al_stock(inv, usuario_autorizo=self.user)
        inv.refresh_from_db()
        self.assertEqual(inv.estado, 'APLICADO')

        # 6. Tras estar APLICADO, el stock debe reflejar el recálculo exacto (10 - 3 = 7)
        stk_final = recalcular_stock(self.producto.id, self.sucursal.id)
        self.assertEqual(stk_final, Decimal('7.00'), "El stock disponible debe ser 7 tras aplicar el inventario")

        # 7. Verificar que se haya emitido la auditoría de MovimientoStock
        mov = MovimientoStock.objects.filter(producto=self.producto, sucursal=self.sucursal).last()
        self.assertIsNotNone(mov)
        self.assertEqual(mov.tipo, 'SALIDA')
        self.assertEqual(mov.cantidad, Decimal('3.00'))
