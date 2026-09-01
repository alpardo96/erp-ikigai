from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from decimal import Decimal

from empresas.models import Empresa, Ejercicio
from contable.models import Asiento, AsientoLinea, Cuenta
from contable.services.asientos import crear_asiento

User = get_user_model()

class AsientosTestCase(TestCase):
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
        
        # 3. Crear Ejercicio Fiscal Activo (Enero a Diciembre de 2026)
        self.ejercicio = Ejercicio.objects.create(
            empresa=self.empresa,
            ejercicio="Ejercicio 2026",
            inicio=timezone.datetime(2026, 1, 1).date(),
            cierre=timezone.datetime(2026, 12, 31).date()
        )
        
        # 4. Crear Cuentas Contables (Imputables y No Imputables)
        # Cuenta no imputable (sumariza)
        self.cta_activo_gen = Cuenta.objects.create(
            jerarquia="1.0.0",
            cuenta="ACTIVO",
            imputable=0,  # No imputable
            tipo="A",
            empresa=self.empresa
        )
        
        # Cuentas imputables
        self.cta_caja = Cuenta.objects.create(
            sumariza=self.cta_activo_gen,
            jerarquia="1.1.1",
            cuenta="CAJA CHICA",
            imputable=1,  # Imputable
            tipo="A",
            empresa=self.empresa
        )
        
        self.cta_capital = Cuenta.objects.create(
            jerarquia="3.1.1",
            cuenta="CAPITAL SOCIAL",
            imputable=1,  # Imputable
            tipo="N",
            empresa=self.empresa
        )
        
        self.cta_ventas = Cuenta.objects.create(
            jerarquia="4.1.1",
            cuenta="VENTAS DIRECTAS",
            imputable=1,  # Imputable
            tipo="R",
            empresa=self.empresa
        )

    def test_crear_asiento_exitoso(self):
        """
        Verifica que se pueda crear un asiento contable balanceado con cuentas imputables.
        """
        fecha_asiento = timezone.datetime(2026, 5, 20).date()
        
        lineas = [
            {
                'cuenta': self.cta_caja,
                'debe': Decimal("1000.00"),
                'haber': Decimal("0.00"),
                'leyenda': "Ingreso de caja"
            },
            {
                'cuenta': self.cta_ventas,
                'debe': Decimal("0.00"),
                'haber': Decimal("1000.00"),
                'leyenda': "Contrapartida de venta"
            }
        ]
        
        asiento = crear_asiento(
            empresa=self.empresa,
            fecha=fecha_asiento,
            concepto="Venta al contado de mercadería",
            lineas=lineas,
            usuario=self.usuario
        )
        
        # Verificar cabecera del asiento
        self.assertIsNotNone(asiento.asiento_id)
        self.assertEqual(asiento.concepto, "VENTA AL CONTADO DE MERCADERÍA")  # Debe estar en mayúsculas
        self.assertEqual(asiento.monto, Decimal("1000.00"))
        self.assertEqual(asiento.ejercicio, self.ejercicio)
        
        # Verificar líneas creadas
        lineas_creadas = AsientoLinea.objects.filter(asiento=asiento).order_by('orden')
        self.assertEqual(lineas_creadas.count(), 2)
        
        linea_debe = lineas_creadas[0]
        self.assertEqual(linea_debe.cuenta, self.cta_caja)
        self.assertEqual(linea_debe.debe, Decimal("1000.00"))
        self.assertEqual(linea_debe.haber, Decimal("0.00"))
        self.assertEqual(linea_debe.orden, 1)
        
        linea_haber = lineas_creadas[1]
        self.assertEqual(linea_haber.cuenta, self.cta_ventas)
        self.assertEqual(linea_haber.debe, Decimal("0.00"))
        self.assertEqual(linea_haber.haber, Decimal("1000.00"))
        self.assertEqual(linea_haber.orden, 2)

    def test_asiento_desbalanceado_falla(self):
        """
        Verifica que se lance un ValidationError si la suma del Debe no es igual a la del Haber.
        """
        fecha_asiento = timezone.datetime(2026, 5, 20).date()
        
        lineas = [
            {
                'cuenta': self.cta_caja,
                'debe': Decimal("1500.00"),
                'haber': Decimal("0.00"),
                'leyenda': "Asiento desbalanceado"
            },
            {
                'cuenta': self.cta_ventas,
                'debe': Decimal("0.00"),
                'haber': Decimal("1000.00"),
                'leyenda': "Contrapartida incorrecta"
            }
        ]
        
        with self.assertRaises(ValidationError) as ctx:
            crear_asiento(
                empresa=self.empresa,
                fecha=fecha_asiento,
                concepto="Intento de asiento descuadrado",
                lineas=lineas,
                usuario=self.usuario
            )
        self.assertIn("desbalanceado", str(ctx.exception))

    def test_cuenta_no_imputable_falla(self):
        """
        Verifica que se lance un ValidationError si se intenta imputar a una cuenta no imputable.
        """
        fecha_asiento = timezone.datetime(2026, 5, 20).date()
        
        lineas = [
            {
                'cuenta': self.cta_activo_gen,  # No imputable
                'debe': Decimal("1000.00"),
                'haber': Decimal("0.00"),
            },
            {
                'cuenta': self.cta_capital,
                'debe': Decimal("0.00"),
                'haber': Decimal("1000.00"),
            }
        ]
        
        with self.assertRaises(ValidationError) as ctx:
            crear_asiento(
                empresa=self.empresa,
                fecha=fecha_asiento,
                concepto="Intento imputar cuenta jerárquica",
                lineas=lineas,
                usuario=self.usuario
            )
        self.assertIn("no es imputable", str(ctx.exception))

    def test_fuera_ejercicio_falla(self):
        """
        Verifica que se lance un ValidationError si la fecha del asiento está fuera de cualquier ejercicio fiscal activo.
        """
        # 2027 está fuera del ejercicio creado en setUp (2026)
        fecha_fuera_rango = timezone.datetime(2027, 1, 1).date()
        
        lineas = [
            {
                'cuenta': self.cta_caja,
                'debe': Decimal("500.00"),
                'haber': Decimal("0.00"),
            },
            {
                'cuenta': self.cta_capital,
                'debe': Decimal("0.00"),
                'haber': Decimal("500.00"),
            }
        ]
        
        with self.assertRaises(ValidationError) as ctx:
            crear_asiento(
                empresa=self.empresa,
                fecha=fecha_fuera_rango,
                concepto="Asiento fuera de año",
                lineas=lineas,
                usuario=self.usuario
            )
        self.assertIn("ejercicio fiscal activo", str(ctx.exception))

    def test_debe_xor_haber_constraint(self):
        """
        Verifica que la base de datos lance una violación de constraint si una línea contiene Debe y Haber mayores a cero simultáneamente.
        """
        fecha_asiento = timezone.datetime(2026, 5, 20).date()
        
        # Creamos una cabecera directamente usando ORM para evitar la validación en Python del service
        asiento = Asiento.objects.create(
            empresa=self.empresa,
            ejercicio=self.ejercicio,
            fecha=fecha_asiento,
            concepto="Violación directa de constraint",
            monto=Decimal("500.00"),
            creado_por=self.usuario
        )
        
        # Intentamos insertar una línea que tiene valores mayores a 0 tanto en debe como en haber
        linea_invalida = AsientoLinea(
            asiento=asiento,
            orden=1,
            cuenta=self.cta_caja,
            debe=Decimal("500.00"),
            haber=Decimal("200.00"),
        )
        
        with self.assertRaises(IntegrityError):
            linea_invalida.save()
