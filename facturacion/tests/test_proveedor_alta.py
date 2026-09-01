from django.test import TestCase
from empresas.models import Empresa
from facturacion.models import ClienteProveedor
from facturacion.forms import ClienteProveedorForm

class ProveedorAltaTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nombre="Empresa Test Proveedores")

    def test_crear_proveedor_valido(self):
        """Verifica que un proveedor con CUIT y Responsable Inscripto se guarde correctamente como tipo_entidad=2."""
        data = {
            'razon_social': 'PROVEEDOR INDUSTRIAL SA',
            'tipo_entidad': 2,
            'condicion_iva': 'RESPONSABLE INSCRIPTO',
            'tipo_documento': '80',
            'cuit': '30712345678',
            'tipo_iibb': 'LOCAL',
            'domicilio': 'Av. Industrial 1234',
        }
        form = ClienteProveedorForm(data=data, empresa_id=self.empresa.id)
        self.assertTrue(form.is_valid(), f"Errores de formulario: {form.errors}")
        
        obj = form.save(commit=False)
        obj.empresa = self.empresa
        obj.save()

        # Verificar que la entidad guardada sea Proveedor (tipo_entidad == 2)
        proveedor = ClienteProveedor.objects.get(pk=obj.pk)
        self.assertEqual(proveedor.tipo_entidad, 2)
        self.assertEqual(proveedor.razon_social, 'PROVEEDOR INDUSTRIAL SA')
        self.assertEqual(proveedor.cuit, '30712345678')

    def test_proveedor_consumidor_final_invalido(self):
        """Verifica que un proveedor NO pueda registrarse con condición Consumidor Final."""
        data = {
            'razon_social': 'PROVEEDOR INVALIDO',
            'tipo_entidad': 2,
            'condicion_iva': 'CONSUMIDOR FINAL',
            'tipo_documento': '99',
            'cuit': '0',
        }
        form = ClienteProveedorForm(data=data, empresa_id=self.empresa.id)
        self.assertFalse(form.is_valid())
        self.assertIn('condicion_iva', form.errors)
        self.assertIn('cuit', form.errors)

    def test_modelo_save_preserva_tipo_entidad_proveedor(self):
        """Verifica que ClienteProveedor.save() respete tipo_entidad=2."""
        p = ClienteProveedor.objects.create(
            razon_social='PROVEEDOR DIRECTO',
            tipo_entidad=2,
            condicion_iva='MONOTRIBUTO',
            tipo_documento='80',
            cuit='20334445556',
            empresa=self.empresa
        )
        self.assertEqual(p.tipo_entidad, 2)
