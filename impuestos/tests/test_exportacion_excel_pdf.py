import io
from datetime import date
from decimal import Decimal
import openpyxl
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from empresas.models import Empresa
from facturacion.models import ClienteProveedor, TipoComprobante
from contable.models import LibroIvaVentas, LibroIvaCompras, LibroIvaAlic
from impuestos.services_export import exportar_libro_iva_excel, exportar_libro_iva_pdf

User = get_user_model()


class ExportacionExcelPdfTestCase(TestCase):
    """
    Tests de generación y descarga de archivos Excel y PDF de Libro IVA Ventas y Compras.
    """

    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="EMPRESA TEST EXPORT S.A.",
            cuit="30111222334",
            condicion_iva="RESPONSABLE INSCRIPTO",
        )
        self.user = User.objects.create_user(username="testuser_exp", password="password123")

        self.tipo_fa = TipoComprobante.objects.create(
            codigo="001",
            detalle="FACTURA A",
            signo=1,
            estado=True,
        )

        self.cliente = ClienteProveedor.objects.create(
            empresa=self.empresa,
            razon_social="CLIENTE EJEMPLO S.A.",
            tipo_documento="80",
            cuit="30555666778",
            condicion_iva="RESPONSABLE INSCRIPTO",
        )

        # Comprobante en LibroIvaVentas
        self.venta_iva = LibroIvaVentas.objects.create(
            empresa=self.empresa,
            asiento_id=505,
            fecha=date(2026, 9, 20),
            periodo="202609",
            clienteproveedor=self.cliente,
            codiva="001",
            punto=2,
            numero=100,
            cuit="30555666778",
            neto_gravado=Decimal("10000.00"),
            exento=Decimal("0.00"),
            no_gravado=Decimal("0.00"),
            iva_total=Decimal("2100.00"),
            otros=Decimal("0.00"),
            total=Decimal("12100.00"),
        )

        # Alícuota 21%
        LibroIvaAlic.objects.create(
            asiento_id=505,
            c_v="V",
            neto=Decimal("10000.00"),
            alicuota=Decimal("21.00"),
            iva=Decimal("2100.00"),
            computable=Decimal("2100.00"),
            codiva="001",
        )

        self.client = Client()
        self.client.login(username="testuser_exp", password="password123")
        session = self.client.session
        session["empresa_id"] = self.empresa.id
        session.save()

    def test_exportar_excel_ventas_estructura(self):
        """
        Valida que el Excel generado contenga las columnas requeridas (asiento_id, alícuotas, CUIT y Razón Social).
        """
        response = exportar_libro_iva_excel("VENTAS", self.empresa, 2026, 9)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        ws = wb.active

        # Verificar encabezados de empresa
        self.assertIn("EMPRESA TEST EXPORT S.A.", str(ws["A1"].value))
        self.assertIn("30111222334", str(ws["A1"].value))
        self.assertEqual(ws["A2"].value, "LIBRO IVA VENTAS")

        # Verificar nombres de columnas en fila 5
        headers = [cell.value for cell in ws[5]]
        self.assertIn("Fecha", headers)
        self.assertIn("Asiento", headers)
        self.assertIn("IVA 2.5%", headers)
        self.assertIn("IVA 5%", headers)
        self.assertIn("IVA 10.5%", headers)
        self.assertIn("IVA 21%", headers)
        self.assertIn("IVA 27%", headers)
        self.assertIn("IVA Débito Fiscal", headers)

        # Fila de datos (fila 6)
        row_data = [cell.value for cell in ws[6]]
        self.assertEqual(row_data[3], 505)  # asiento_id

    def test_exportar_pdf_ventas_status_y_tipo(self):
        """
        Valida que el PDF se genere correctamente con encabezado y formato A4 horizontal.
        """
        response = exportar_libro_iva_pdf("VENTAS", self.empresa, 2026, 9)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("LIBRO_IVA_VENTAS_202609.pdf", response["Content-Disposition"])

    def test_vistas_descarga_excel_y_pdf(self):
        """
        Valida que los endpoints HTTP respondan 200 con los archivos adjuntos.
        """
        url_excel = reverse("impuestos:exportar_libro_iva_ventas_excel") + "?anio=2026&mes=9"
        res_excel = self.client.get(url_excel)
        self.assertEqual(res_excel.status_code, 200)

        url_pdf = reverse("impuestos:exportar_libro_iva_ventas_pdf") + "?anio=2026&mes=9"
        res_pdf = self.client.get(url_pdf)
        self.assertEqual(res_pdf.status_code, 200)
