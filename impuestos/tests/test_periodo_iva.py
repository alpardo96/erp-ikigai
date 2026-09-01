from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from empresas.models import Empresa, Sucursal
from facturacion.models import ClienteProveedor, Compra, Venta, TipoComprobante
from impuestos.models import PeriodoIva
from impuestos.services import (
    es_periodo_cerrado,
    obtener_primer_periodo_vigente_compra,
    cerrar_periodo_iva,
    reabrir_periodo_iva,
    calcular_liquidacion_iva
)

User = get_user_model()


class PeriodoIvaTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Empresa Test IVA",
            cuit="30711111118"
        )
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa,
            nombre="Sucursal Centro"
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="password"
        )
        self.tipo_fc = TipoComprobante.objects.create(
            codigo="001",
            detalle="Factura A",
            signo=1
        )
        self.clipro = ClienteProveedor.objects.create(
            empresa=self.empresa,
            razon_social="Proveedor / Cliente Test",
            cuit="30722222224",
            tipo_entidad=3
        )

    def test_cierre_y_reapertura_periodo_iva(self):
        # 1. El período 202605 inicia abierto
        self.assertFalse(es_periodo_cerrado(self.empresa.id, "202605"))

        # 2. Ejecutar cierre del período 202605
        periodo_obj = cerrar_periodo_iva(self.empresa.id, 2026, 5, self.user)
        self.assertEqual(periodo_obj.periodo, "202605")
        self.assertEqual(periodo_obj.estado, "CERRADO")
        self.assertTrue(es_periodo_cerrado(self.empresa.id, "202605"))

        # 3. Reabrir período
        reabrir_periodo_iva(self.empresa.id, "202605", self.user)
        self.assertFalse(es_periodo_cerrado(self.empresa.id, "202605"))

    def test_compra_periodo_vigente_con_periodos_cerrados(self):
        """
        Ejemplo del usuario: si están cerrados 202601 a 202607,
        una factura de compra del 22/05/2026 se asigna al período vigente 202608.
        """
        # Cerrar los períodos 202601 al 202607
        for m in range(1, 8):
            cerrar_periodo_iva(self.empresa.id, 2026, m, self.user)

        fecha_compra = date(2026, 5, 22)
        periodo_vigente = obtener_primer_periodo_vigente_compra(self.empresa.id, fecha_compra)
        
        # Debe trasladarse a Agosto 2026 (202608)
        self.assertEqual(periodo_vigente, "202608")

    def test_compra_periodo_vigente_sin_cierres(self):
        fecha_compra = date(2026, 8, 15)
        periodo_vigente = obtener_primer_periodo_vigente_compra(self.empresa.id, fecha_compra)
        
        # Al no estar cerrado 202608, se mantiene 202608
        self.assertEqual(periodo_vigente, "202608")

    def test_calcular_liquidacion_iva(self):
        liq = calcular_liquidacion_iva(self.empresa.id, 2026, 8)
        self.assertEqual(liq['periodo'], "202608")
        self.assertEqual(liq['debito_fiscal'], Decimal('0.00'))
        self.assertEqual(liq['credito_fiscal'], Decimal('0.00'))
