import zipfile
import io
from datetime import date
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from empresas.models import Empresa
from facturacion.models import ClienteProveedor, TipoComprobante
from contable.models import LibroIvaVentas, LibroIvaCompras, LibroIvaAlic, RetPercSufrida
from impuestos.services import (
    generar_txt_libro_iva_ventas,
    generar_txt_libro_iva_compras,
    generar_zip_libro_iva,
)

User = get_user_model()


class ExportacionTxtArcaTestCase(TestCase):
    """
    Tests de generación y descarga de archivos TXT y ZIP de Libro IVA Digital ARCA (RG 4597 / RG 5616).
    """

    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="EMPRESA TEST ARCA S.A.",
            cuit="30700000001",
            condicion_iva="RESPONSABLE INSCRIPTO",
        )
        self.user = User.objects.create_user(username="testuser", password="password123")

        self.tipo_fa = TipoComprobante.objects.create(
            codigo="001",
            detalle="FACTURA A",
            signo=1,
            estado=True,
        )
        self.tipo_fb = TipoComprobante.objects.create(
            codigo="006",
            detalle="FACTURA B",
            signo=1,
            estado=True,
        )

        self.cliente = ClienteProveedor.objects.create(
            empresa=self.empresa,
            razon_social="CLIENTE PRUEBA SA",
            tipo_documento="80",
            cuit="30612345678",
            condicion_iva="RESPONSABLE INSCRIPTO",
        )

        self.proveedor = ClienteProveedor.objects.create(
            empresa=self.empresa,
            razon_social="PROVEEDOR PRUEBA SRL",
            tipo_documento="80",
            cuit="30987654321",
            condicion_iva="RESPONSABLE INSCRIPTO",
        )

        # Crear comprobante de venta en LibroIvaVentas
        self.venta_iva = LibroIvaVentas.objects.create(
            empresa=self.empresa,
            asiento_id=101,
            fecha=date(2026, 9, 15),
            periodo="202609",
            clienteproveedor=self.cliente,
            codiva="001",
            punto=1,
            numero=1234,
            cuit="30612345678",
            neto_gravado=Decimal("10000.00"),
            exento=Decimal("0.00"),
            no_gravado=Decimal("0.00"),
            iva_total=Decimal("2100.00"),
            otros=Decimal("0.00"),
            total=Decimal("12100.00"),
            cae="74321098765432",
        )

        # Alícuota asociada a la venta
        LibroIvaAlic.objects.create(
            asiento_id=101,
            c_v="V",
            neto=Decimal("10000.00"),
            alicuota=Decimal("21.00"),
            iva=Decimal("2100.00"),
            computable=Decimal("2100.00"),
            codiva="001",
        )

        # Crear comprobante de compra en LibroIvaCompras
        self.compra_iva = LibroIvaCompras.objects.create(
            empresa=self.empresa,
            asiento_id=202,
            fecha=date(2026, 9, 10),
            periodo="202609",
            clienteproveedor=self.proveedor,
            codiva="001",
            punto=5,
            numero=9999,
            cuit="30987654321",
            neto_gravado=Decimal("5000.00"),
            exento=Decimal("0.00"),
            no_gravado=Decimal("0.00"),
            iva_total=Decimal("1050.00"),
            otros=Decimal("150.00"),
            total=Decimal("6200.00"),
            cae="88887777666655",
        )

        # Alícuota asociada a la compra
        LibroIvaAlic.objects.create(
            asiento_id=202,
            c_v="C",
            neto=Decimal("5000.00"),
            alicuota=Decimal("21.00"),
            iva=Decimal("1050.00"),
            computable=Decimal("1050.00"),
            codiva="001",
        )

        # Percepción IIBB asociada
        RetPercSufrida.objects.create(
            empresa=self.empresa,
            asiento_id=202,
            origen="C",
            tipo="P",
            impuesto="IIBB",
            importe=Decimal("150.00"),
        )

        self.client = Client()
        self.client.login(username="testuser", password="password123")
        session = self.client.session
        session["empresa_id"] = self.empresa.id
        session.save()

    def test_generacion_txt_libro_iva_ventas_longitudes_correctas(self):
        """
        Valida que cada línea de Libro IVA Ventas cumpla las longitudes de campo fijas de AFIP/ARCA:
        - CBTE: 266 caracteres por línea.
        - ALICUOTAS: 62 caracteres por línea.
        """
        txt_cbte, txt_alic = generar_txt_libro_iva_ventas(self.empresa.id, 2026, 9)

        lineas_cbte = [l for l in txt_cbte.split("\r\n") if l]
        lineas_alic = [l for l in txt_alic.split("\r\n") if l]

        self.assertEqual(len(lineas_cbte), 1)
        self.assertEqual(len(lineas_alic), 1)

        # Verificación estricta de longitud de caracteres
        self.assertEqual(len(lineas_cbte[0]), 266, "La línea de comprobantes de ventas debe tener exactamente 266 caracteres.")
        self.assertEqual(len(lineas_alic[0]), 62, "La línea de alícuotas de ventas debe tener exactamente 62 caracteres.")

        # Verificar contenido de la cabecera
        linea = lineas_cbte[0]
        self.assertEqual(linea[:8], "20260915")  # Fecha
        self.assertEqual(linea[8:11], "001")      # Tipo comprobante
        self.assertEqual(linea[11:16], "00001")   # Punto de venta
        self.assertEqual(linea[16:36], "00000000000000001234")  # Número

    def test_generacion_txt_libro_iva_compras_longitudes_correctas(self):
        """
        Valida que cada línea de Libro IVA Compras cumpla las longitudes de campo fijas de AFIP/ARCA:
        - CBTE: 325 caracteres por línea.
        - ALICUOTAS: 84 caracteres por línea.
        """
        txt_cbte, txt_alic = generar_txt_libro_iva_compras(self.empresa.id, 2026, 9)

        lineas_cbte = [l for l in txt_cbte.split("\r\n") if l]
        lineas_alic = [l for l in txt_alic.split("\r\n") if l]

        self.assertEqual(len(lineas_cbte), 1)
        self.assertEqual(len(lineas_alic), 1)

        # Verificación estricta de longitud de caracteres
        self.assertEqual(len(lineas_cbte[0]), 325, "La línea de comprobantes de compras debe tener exactamente 325 caracteres.")
        self.assertEqual(len(lineas_alic[0]), 84, "La línea de alícuotas de compras debe tener exactamente 84 caracteres.")

        # Verificar contenido de la cabecera
        linea = lineas_cbte[0]
        self.assertEqual(linea[:8], "20260910")  # Fecha
        self.assertEqual(linea[8:11], "001")      # Tipo comprobante
        self.assertEqual(linea[11:16], "00005")   # Punto de venta
        self.assertEqual(linea[16:36], "00000000000000009999")  # Número

    def test_generacion_zip_empaquetado(self):
        """
        Valida que el archivo ZIP contenga los 2 archivos de texto correspondientes.
        """
        zip_bytes = generar_zip_libro_iva("VENTAS", self.empresa.id, 2026, 9)
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            nombres = zf.namelist()
            self.assertIn("LIBRO_IVA_DIGITAL_VENTAS_CBTE.txt", nombres)
            self.assertIn("LIBRO_IVA_DIGITAL_VENTAS_ALICUOTAS.txt", nombres)

        zip_bytes_c = generar_zip_libro_iva("COMPRAS", self.empresa.id, 2026, 9)
        with zipfile.ZipFile(io.BytesIO(zip_bytes_c), "r") as zf:
            nombres = zf.namelist()
            self.assertIn("LIBRO_IVA_DIGITAL_COMPRAS_CBTE.txt", nombres)
            self.assertIn("LIBRO_IVA_DIGITAL_COMPRAS_ALICUOTAS.txt", nombres)

    def test_vista_descarga_libro_iva_ventas_txt(self):
        """
        Valida la respuesta HTTP de la vista de exportación de ventas.
        """
        url = reverse("impuestos:exportar_libro_iva_ventas_txt") + "?anio=2026&mes=9"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertIn("LIBRO_IVA_DIGITAL_VENTAS_202609.zip", response["Content-Disposition"])

    def test_vista_descarga_libro_iva_compras_txt(self):
        """
        Valida la respuesta HTTP de la vista de exportación de compras.
        """
        url = reverse("impuestos:exportar_libro_iva_compras_txt") + "?anio=2026&mes=9"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertIn("LIBRO_IVA_DIGITAL_COMPRAS_202609.zip", response["Content-Disposition"])
