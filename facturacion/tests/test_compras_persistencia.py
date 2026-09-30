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
