from decimal import Decimal
from datetime import date
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore

from empresas.models import Empresa, Sucursal
from productos.models import Producto
from facturacion.models import ClienteProveedor, TipoComprobante
from facturacion.views import ComprasCargaView

User = get_user_model()


class ComprasPersistenciaHeaderTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_persistencia', password='password123')
        self.emp = Empresa.objects.create(nombre="Empresa Test", cuit="20111111119")
        self.suc = Sucursal.objects.create(empresa=self.emp, nombre="Casa Central", punto=1)
        self.prov = ClienteProveedor.objects.create(
            razon_social="Distribuidora Mayorista SA",
            tipo_entidad=2,
            empresa=self.emp,
            activo=True
        )
        self.tipo = TipoComprobante.objects.create(codigo="001", detalle="FACTURA A", signo=1)
        self.prod = Producto.objects.create(
            detalle="Cartucho Test",
            empresa=self.emp,
            alic_iva=Decimal('21'),
            activo=True
        )
        self.factory = RequestFactory()

    def test_persistencia_datos_cabecera_en_error_validacion(self):
        """Verifica que ante un error en POST (ej. grilla vacía), el formulario y la plantilla preservan todos los campos."""
        post_data = {
            'fecha': '2026-09-29',
            'periodo': '202609',
            'proveedor': str(self.prov.pk),
            'tipo': '001',
            'punto': '00001',
            'numero': '00001234',
            'moneda': 'PES',
            'cotizacion': '1',
            'condic': '1',
            'subtotal': '1000,00',
            'descuento': '100,00',
            'neto': '900,00',
            'iva': '189,00',
            'p_iibb': '25,00',
            'p_iva': '15,00',
            'otros': '10,00',
            'total': '1139,00',
        }
        
        request = self.factory.post('/facturacion/compras/carga/', post_data)
        request.user = self.user
        request.session = SessionStore()
        request.session['empresa_id'] = self.emp.id
        request.session['sucursal_id'] = self.suc.id
        request.session['compra_items_temp'] = []  # Grilla vacía para disparar error
        request.session.save()
        
        # Agregar soporte de messages al request
        setattr(request, '_messages', FallbackStorage(request))
        
        view = ComprasCargaView.as_view()
        response = view(request)
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8').upper()
        
        # Debe contener la fecha intacta en el value del input
        self.assertIn('VALUE="2026-09-29"', content)
        
        # Debe contener el período sugerido / ingresado
        self.assertIn('VALUE="202609"', content)
        
        # Debe contener el proveedor seleccionado y su display legible
        self.assertIn(f'VALUE="{self.prov.pk}"', content)
        self.assertIn('DISTRIBUIDORA MAYORISTA SA', content)
        
        # Debe contener el tipo de comprobante y su display
        self.assertIn('001 - FACTURA A', content)
        
        # Debe contener punto y número
        self.assertIn('VALUE="00001"', content)
        self.assertIn('VALUE="00001234"', content)

    def test_carga_compra_condic_3_ajuste(self):
        """Verifica que un comprobante condic=3 (AJUSTE) se registre en LibroIvaCompras y Asiento pero NO en la tabla Compra."""
        from empresas.models import Ejercicio
        from contable.models import Cuenta, ParametrosContables, Asiento, LibroIvaCompras, LibroIvaAlic
        from facturacion.models import Compra

        ej = Ejercicio.objects.create(
            empresa=self.emp,
            ejercicio="Ejercicio 2026",
            inicio=date(2026, 1, 1),
            cierre=date(2026, 12, 31)
        )

        cta_prov = Cuenta.objects.create(empresa=self.emp, jerarquia="2.1.1.01", cuenta="Proveedores Locales", imputable=1, tipo="P")
        cta_gasto = Cuenta.objects.create(empresa=self.emp, jerarquia="5.1.1.01", cuenta="Gastos Generales", imputable=1, tipo="R")
        cta_iva = Cuenta.objects.create(empresa=self.emp, jerarquia="1.1.3.01", cuenta="IVA Credito Fiscal", imputable=1, tipo="A")
        cta_iibb = Cuenta.objects.create(empresa=self.emp, jerarquia="1.1.3.02", cuenta="Retenciones IIBB", imputable=1, tipo="A")
        cta_internos = Cuenta.objects.create(empresa=self.emp, jerarquia="5.1.2.01", cuenta="Impuestos Internos", imputable=1, tipo="R")

        self.prov.cta_pat = cta_prov.pk
        self.prov.save()

        ParametrosContables.objects.create(
            empresa=self.emp,
            cta_proveedores_default=cta_prov,
            cta_compras=cta_gasto,
            cta_iva_credito=cta_iva,
            cta_ret_iibb=cta_iibb,
            cta_impuestos_internos=cta_internos,
        )

        post_data = {
            'fecha': '2026-09-29',
            'periodo': '202609',
            'proveedor': str(self.prov.pk),
            'tipo': '001',
            'punto': '00001',
            'numero': '00005678',
            'moneda': 'PES',
            'cotizacion': '1',
            'condic': '3',  # AJUSTE
            'neto': '1000,00',
            'iva': '210,00',
            'p_iibb': '0,00',
            'p_iva': '0,00',
            'otros': '0,00',
            'total': '1210,00',
            'modo': 'gasto',
        }

        request = self.factory.post('/facturacion/compras/carga/', post_data)
        request.user = self.user
        request.session = SessionStore()
        request.session['empresa_id'] = self.emp.id
        request.session['sucursal_id'] = self.suc.id
        request.session['compra_items_temp'] = []
        request.session.save()
        setattr(request, '_messages', FallbackStorage(request))

        view = ComprasCargaView.as_view()
        response = view(request)

        # Si no es 302, mostramos el error del contexto o de mensajes
        if response.status_code != 302:
            form_errors = response.context_data.get('form').errors if hasattr(response, 'context_data') and response.context_data and response.context_data.get('form') else 'No context form'
            msg_list = [m.message for m in getattr(request, '_messages')]
            self.fail(f"Response status {response.status_code}. Form errors: {form_errors}. Messages: {msg_list}")

        self.assertEqual(response.status_code, 302)

        # 1. NO debe cargarse en la tabla Compra
        self.assertEqual(Compra.objects.filter(empresa=self.emp, numero=5678).count(), 0)

        # 2. DEBE cargarse en LibroIvaCompras
        iva_compra = LibroIvaCompras.objects.filter(empresa=self.emp, numero=5678).first()
        self.assertIsNotNone(iva_compra)
        self.assertEqual(iva_compra.neto_gravado, Decimal('1000.00'))
        self.assertEqual(iva_compra.iva_total, Decimal('210.00'))
        self.assertEqual(iva_compra.total, Decimal('1210.00'))
        self.assertEqual(iva_compra.periodo, '202609')

        # 3. DEBE generar el Asiento Contable con condic=3
        asiento = Asiento.objects.filter(empresa=self.emp, asiento_id=iva_compra.asiento_id).first()
        self.assertIsNotNone(asiento)
        self.assertEqual(asiento.condic, 3)
        self.assertEqual(asiento.modulo, 5)

        # 4. DEBE generar el registro de alícuota en LibroIvaAlic
        alic = LibroIvaAlic.objects.filter(asiento_id=asiento.asiento_id, c_v='C').first()
        self.assertIsNotNone(alic)
        self.assertEqual(alic.neto, Decimal('1000.00'))
        self.assertEqual(alic.iva, Decimal('210.00'))

        # 5. El saldo del proveedor NO debe verse alterado
        self.prov.refresh_from_db()
        self.assertEqual(self.prov.saldo, Decimal('0.00'))

