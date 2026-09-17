"""
Tests unitarios y de integración para el módulo de Liquidaciones de Granos (LPG).
Valida:
1. Extracción de datos con LpgPdfParser.
2. Cotejo y auto-aprendizaje con LpgMatcher.
3. Persistencia atómica con LpgPersister y cuadre estricto de asientos contables.
"""
import os
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from empresas.models import Empresa, Sucursal, Ejercicio
from contable.models import Cuenta, ParametrosContables, Asiento, AsientoLinea, LibroIvaVentas, LibroIvaCompras
from productos.models import Producto, Rubro, Familia, Marca
from facturacion.models import ClienteProveedor, TipoComprobante, Venta, Compra
from verticalidades.agricola.granos.models import GranoMapeo, GastoMapeo
from verticalidades.agricola.granos.services.lpg_parser import LpgPdfParser
from verticalidades.agricola.granos.services.lpg_matcher import LpgMatcher
from verticalidades.agricola.granos.services.lpg_persister import LpgPersister


User = get_user_model()


class LpgIntegrationTest(TestCase):
    def setUp(self):
        self.user, _ = User.objects.get_or_create(username='testadmin_lpg', defaults={'password': 'password123'})
        
        # 1. Empresa y Sucursal
        self.empresa, _ = Empresa.objects.get_or_create(
            cuit="30717305538",
            defaults={"nombre": "AGROJAS S.A.S.", "tipo_actividad": "AGRICOLA"}
        )
        self.sucursal, _ = Sucursal.objects.get_or_create(
            empresa=self.empresa,
            nombre="Casa Central",
            defaults={"punto": 1}
        )
        self.ejercicio, _ = Ejercicio.objects.get_or_create(
            empresa=self.empresa,
            ejercicio="Ejercicio 2026",
            defaults={"inicio": "2026-01-01", "cierre": "2026-12-31"}
        )

        # 2. Plan de Cuentas Básico
        self.cta_clientes, _ = Cuenta.objects.get_or_create(empresa=self.empresa, jerarquia="1.1.2.01", defaults={"cuenta": "Deudores por Granos", "imputable": 1, "tipo": "A"})
        self.cta_iva_debito, _ = Cuenta.objects.get_or_create(empresa=self.empresa, jerarquia="2.1.1.01", defaults={"cuenta": "IVA Débito Fiscal", "imputable": 1, "tipo": "P"})
        self.cta_iva_credito, _ = Cuenta.objects.get_or_create(empresa=self.empresa, jerarquia="1.1.3.01", defaults={"cuenta": "IVA Crédito Fiscal", "imputable": 1, "tipo": "A"})
        self.cta_ret_iva, _ = Cuenta.objects.get_or_create(empresa=self.empresa, jerarquia="1.1.3.05", defaults={"cuenta": "Retenciones Sufridas IVA", "imputable": 1, "tipo": "A"})
        self.cta_ret_gan, _ = Cuenta.objects.get_or_create(empresa=self.empresa, jerarquia="1.1.3.06", defaults={"cuenta": "Retenciones Sufridas Ganancias", "imputable": 1, "tipo": "A"})
        
        self.cta_venta_maiz, _ = Cuenta.objects.get_or_create(empresa=self.empresa, jerarquia="4.1.1.01", defaults={"cuenta": "Venta de Maíz", "imputable": 1, "tipo": "R"})
        self.cta_venta_soja, _ = Cuenta.objects.get_or_create(empresa=self.empresa, jerarquia="4.1.1.02", defaults={"cuenta": "Venta de Soja", "imputable": 1, "tipo": "R"})
        
        self.cta_fletes, _ = Cuenta.objects.get_or_create(empresa=self.empresa, jerarquia="5.1.2.01", defaults={"cuenta": "Fletes de Granos", "imputable": 1, "tipo": "R"})
        self.cta_comisiones, _ = Cuenta.objects.get_or_create(empresa=self.empresa, jerarquia="5.1.2.02", defaults={"cuenta": "Comisiones de Acopio", "imputable": 1, "tipo": "R"})
        self.cta_sellados, _ = Cuenta.objects.get_or_create(empresa=self.empresa, jerarquia="5.1.3.01", defaults={"cuenta": "Impuesto de Sellos", "imputable": 1, "tipo": "R"})

        # 3. Parámetros Contables
        self.params, _ = ParametrosContables.objects.get_or_create(
            empresa=self.empresa,
            defaults={
                "cta_iva_debito": self.cta_iva_debito,
                "cta_iva_credito": self.cta_iva_credito,
                "cta_ret_iva": self.cta_ret_iva,
                "cta_ret_ganancias": self.cta_ret_gan,
                "cta_clientes_default": self.cta_clientes
            }
        )

        # 4. Productos
        self.prod_maiz, _ = Producto.objects.get_or_create(empresa=self.empresa, detalle="MAIZ GRANO", defaults={"alic_iva": Decimal('10.50')})
        self.prod_soja, _ = Producto.objects.get_or_create(empresa=self.empresa, detalle="SOJA GRANO", defaults={"alic_iva": Decimal('10.50')})

        # 5. Mapeos de Granos ARCA
        GranoMapeo.objects.get_or_create(empresa=self.empresa, codigo_arca=19, defaults={"descripcion_arca": "MAIZ", "producto": self.prod_maiz, "cta_ventas": self.cta_venta_maiz})
        GranoMapeo.objects.get_or_create(empresa=self.empresa, codigo_arca=23, defaults={"descripcion_arca": "SOJA", "producto": self.prod_soja, "cta_ventas": self.cta_venta_soja})

        # 6. Mapeos de Gastos Base
        GastoMapeo.objects.get_or_create(empresa=self.empresa, patron="FLETE", defaults={"descripcion": "Fletes de Granos", "cta_gasto": self.cta_fletes, "alicuota_sugerida": Decimal('10.50')})
        GastoMapeo.objects.get_or_create(empresa=self.empresa, patron="COMISION", defaults={"descripcion": "Comisiones de Acopio", "cta_gasto": self.cta_comisiones, "alicuota_sugerida": Decimal('10.50')})
        GastoMapeo.objects.get_or_create(empresa=self.empresa, patron="SELLADO", defaults={"descripcion": "Impuesto de Sellos", "cta_gasto": self.cta_sellados, "alicuota_sugerida": Decimal('0.00')})

    def test_parser_and_persister_lpg_real(self):
        """Prueba end-to-end de lectura y contabilización de liquidación01.pdf."""
        pdf_path = r"d:\borrador\agrojas\liquidacion01.pdf"
        if not os.path.exists(pdf_path):
            self.skipTest("No se encontró archivo de prueba en d:\\borrador\\agrojas")

        parsed = LpgPdfParser.parse_pdf(pdf_path)
        self.assertTrue(parsed['es_lpg'])
        self.assertEqual(parsed['coe'], '330232053707')
        self.assertEqual(parsed['grano']['codigo_arca'], 19)
        self.assertEqual(parsed['grano']['descripcion_arca'], 'MAIZ')

        # Matcher
        matched = LpgMatcher.match_single(self.empresa, parsed)
        self.assertFalse(matched['es_duplicado'])
        self.assertIsNotNone(matched['grano_match'])
        self.assertGreater(len(matched['deducciones_matched']), 0)

        # Persister
        res = LpgPersister.persistir_liquidacion(
            empresa=self.empresa,
            sucursal=self.sucursal,
            usuario=self.user,
            matched_data=matched,
            overrides={'cta_pat_cliente_id': self.cta_clientes.id}
        )

        self.assertIsNotNone(res['asiento_id'])
        self.assertIsNotNone(res['ventas_id'])
        self.assertIsNotNone(res['compras_id'])

        # Verificar Cuadre Estricto del Asiento Contable
        asiento = Asiento.objects.get(asiento_id=res['asiento_id'])
        lineas = asiento.lineas.all()
        total_debe = sum((l.debe for l in lineas), Decimal('0.00'))
        total_haber = sum((l.haber for l in lineas), Decimal('0.00'))
        self.assertEqual(total_debe, total_haber, f"El asiento no balancea: Debe {total_debe} != Haber {total_haber}")

        # Verificar Venta y Libro IVA Ventas
        venta = Venta.objects.get(ventas_id=res['ventas_id'])
        self.assertEqual(venta.cae, '330232053707')
        self.assertEqual(venta.neto + venta.iva, venta.total)
        self.assertTrue(LibroIvaVentas.objects.filter(asiento_id=asiento.asiento_id).exists())

        # Verificar Compra y Libro IVA Compras
        compra = Compra.objects.get(compras_id=res['compras_id'])
        self.assertEqual(compra.total, Decimal('19332910.48'))
        self.assertTrue(LibroIvaCompras.objects.filter(asiento_id=asiento.asiento_id).exists())

        # Verificar Control Anti-Duplicados
        matched_2 = LpgMatcher.match_single(self.empresa, parsed)
        self.assertTrue(matched_2['es_duplicado'])
        self.assertEqual(matched_2['estado'], 'DUPLICADO')

    def test_batch_parse_all_26_samples(self):
        """Valida que los 26 PDFs de muestra se parseen correctamente sin errores."""
        import glob
        pdf_dir = r"d:\borrador\agrojas"
        pdf_files = glob.glob(os.path.join(pdf_dir, "*.pdf"))
        if not pdf_files:
            self.skipTest("No se encontraron PDFs en el directorio de muestra")

        self.assertGreaterEqual(len(pdf_files), 20)
        for pdf_file in pdf_files:
            parsed = LpgPdfParser.parse_pdf(pdf_file)
            self.assertTrue(parsed['es_lpg'], f"El archivo {os.path.basename(pdf_file)} no fue reconocido como LPG")
            self.assertTrue(len(parsed['coe']) >= 8, f"COE inválido en {os.path.basename(pdf_file)}: {parsed['coe']}")
            self.assertIsNotNone(parsed['fecha'], f"Fecha no encontrada en {os.path.basename(pdf_file)}")
            self.assertTrue(len(parsed['comprador']['cuit']) >= 10, f"CUIT comprador inválido en {os.path.basename(pdf_file)}")
            self.assertGreater(parsed['grano']['codigo_arca'], 0, f"Código de grano ARCA no detectado en {os.path.basename(pdf_file)}")
