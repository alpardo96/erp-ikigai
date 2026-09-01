from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model

from empresas.models import Empresa, Sucursal
from facturacion.models import ClienteProveedor
from contable.models import LibroIvaCompras, LibroIvaVentas
from impuestos.models import ArcaMisComprobantes
from impuestos.services import (
    conciliar_mis_comprobantes_arca,
    obtener_reporte_conciliacion_arca,
)

User = get_user_model()


class MisComprobantesArcaTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Empresa Conciliacion ARCA",
            cuit="30711111118"
        )
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa,
            nombre="Sucursal Centro"
        )
        self.user = User.objects.create_user(
            username="testuser_arca",
            email="arca@example.com",
            password="password"
        )
        self.clipro = ClienteProveedor.objects.create(
            empresa=self.empresa,
            razon_social="Proveedor / Cliente ARCA",
            cuit="30722222224",
            tipo_entidad=3
        )

    def test_conciliacion_compras(self):
        # 1. Crear comprobantes en LibroIvaCompras (uno sin CAE y otro con CAE)
        libro_item = LibroIvaCompras.objects.create(
            empresa=self.empresa,
            asiento_id=1001,
            fecha=date(2026, 8, 15),
            periodo="202608",
            clienteproveedor=self.clipro,
            codiva="001",
            punto=1,
            numero=150,
            cuit="30722222224",
            neto_gravado=Decimal("1000.00"),
            iva_total=Decimal("210.00"),
            total=Decimal("1210.00"),
            cae="",  # Vacío inicialmente
        )

        # 2. Crear comprobante importado de ARCA (Compras Recibidos)
        arca_item = ArcaMisComprobantes.objects.create(
            empresa=self.empresa,
            origen="C",
            periodo="202608",
            fecha=date(2026, 8, 15),
            codiva="001",
            punto=1,
            numero=150,
            cuit_contraparte="30722222224",
            razon_social_contraparte="Proveedor ARCA",
            total=Decimal("1210.00"),
            cae="71234567890123",
            asiento_id=None,
            usuario=self.user,
        )

        # 3. Ejecutar conciliación bi-direccional
        res = conciliar_mis_comprobantes_arca(self.empresa.id, "C", "202608")
        self.assertEqual(res['conciliados'], 1)

        # 4. Verificar que ArcaMisComprobantes adquirió el asiento_id
        arca_item.refresh_from_db()
        self.assertEqual(arca_item.asiento_id, 1001)

        # 5. Verificar que LibroIvaCompras adquirió el CAE del comprobante de ARCA
        libro_item.refresh_from_db()
        self.assertEqual(libro_item.cae, "71234567890123")

        # 6. Reporte de Conciliación
        rep = obtener_reporte_conciliacion_arca(self.empresa.id, "C", "202608")
        self.assertEqual(rep['cant_conciliados'], 1)
        self.assertEqual(rep['cant_solo_libro'], 0)
        self.assertEqual(rep['cant_solo_arca'], 0)
