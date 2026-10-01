"""`unidad_venta` no puede ser obligatorio fuera de DISTRIBUCION.

El campo se dibuja SÓLO dentro del hook `ui_producto_modal_campos` de Distribución, que está
gateado por `tipo_actividad == 'DISTRIBUCION'`. En ARMERIA, ESTUDIO o AGRICOLA no aparece en
pantalla y por lo tanto no viaja en el POST.

Mientras el modelo no tenía `blank=True`, el formulario lo exigía igual: el alta de producto
fallaba con «Este campo es obligatorio» y el usuario no tenía dónde verlo, porque el campo no
estaba en el modal. Estos tests fijan que eso no vuelva a pasar.
"""
from decimal import Decimal

from django.test import TestCase

from empresas.models import Empresa
from productos.forms import ProductoForm
from productos.models import Producto


def datos_del_modal(**extra):
    """Los campos que el modal de producto SÍ renderiza para cualquier actividad."""
    base = {'detalle': 'PISTOLA 9MM', 'moneda': 'PES', 'alic_iva': '21.00',
            'margen': '0', 'minimo': '0', 'ptopedir': '0'}
    base.update(extra)
    return base


class UnidadVentaOpcionalTests(TestCase):

    def setUp(self):
        self.empresa = Empresa.objects.create(nombre="ARMERIA TEST", cuit="30111111112",
                                              tipo_actividad='ARMERIA')

    def test_el_alta_no_exige_unidad_venta(self):
        """Es el bug reportado: en ARMERIA el modal no dibuja el campo y el alta fallaba."""
        form = ProductoForm(datos_del_modal())

        self.assertTrue(form.is_valid(), form.errors.as_text())
        self.assertNotIn('unidad_venta', form.errors)

    def test_sin_el_campo_queda_el_default_y_no_cadena_vacia(self):
        """Con `blank=True` a secas se guardaría `''` y el choice quedaría roto."""
        form = ProductoForm(datos_del_modal())
        self.assertTrue(form.is_valid(), form.errors.as_text())

        producto = form.save(commit=False)
        producto.empresa = self.empresa
        producto.save()

        producto.refresh_from_db()
        self.assertEqual(producto.unidad_venta, 'UNIDAD')
        self.assertEqual(producto.get_unidad_venta_display(), 'Unidad')

    def test_distribucion_sigue_pudiendo_elegirla(self):
        """La corrección no puede quitarle la funcionalidad a quien sí usa el campo."""
        form = ProductoForm(datos_del_modal(unidad_venta='BULTO'))

        self.assertTrue(form.is_valid(), form.errors.as_text())
        self.assertEqual(form.cleaned_data['unidad_venta'], 'BULTO')

    def test_editar_sin_el_campo_conserva_el_valor(self):
        """Editar un producto de distribución desde otra pantalla no puede pisarle la unidad."""
        producto = Producto.objects.create(
            empresa=self.empresa, detalle="CAJON DE MUNICION", unidad_venta='BULTO',
            alic_iva=Decimal('21.00'))

        form = ProductoForm(datos_del_modal(detalle='CAJON DE MUNICION'), instance=producto)
        self.assertTrue(form.is_valid(), form.errors.as_text())
        form.save()

        producto.refresh_from_db()
        self.assertEqual(producto.unidad_venta, 'BULTO')

    def test_los_otros_campos_de_distribucion_ya_eran_opcionales(self):
        """`unidad_venta` era el único de los cuatro que fallaba; se deja fijado."""
        form = ProductoForm()

        for campo in ('codigo_anterior', 'unidad_venta', 'peso_unitario_kg',
                      'unidades_por_bulto'):
            with self.subTest(campo=campo):
                self.assertFalse(form.fields[campo].required)

    def test_estudio_alta_y_edicion_sin_campos_de_stock(self):
        """En verticalidad ESTUDIO los campos minimo, ptopedir, cod_prov y cod_fab no están en pantalla."""
        empresa_estudio = Empresa.objects.create(nombre="ESTUDIO CONTABLE", cuit="30111111113",
                                                 tipo_actividad='ESTUDIO')
        # Datos tal como viajan desde el modal de Estudio (sin minimo ni ptopedir)
        datos_estudio = {
            'detalle': 'HONORARIOS MENSUALES',
            'moneda': 'PES',
            'alic_iva': '21.00',
            'margen': '0'
        }
        form = ProductoForm(datos_estudio, empresa=empresa_estudio)
        self.assertTrue(form.is_valid(), form.errors.as_text())
        prod = form.save(commit=False)
        prod.empresa = empresa_estudio
        prod.save()

        self.assertEqual(prod.minimo, Decimal('0.00'))
        self.assertEqual(prod.ptopedir, Decimal('0.00'))
        self.assertIsNone(prod.proveedor)

        # Edición también exitosa sin enviar minimo/ptopedir
        form_edit = ProductoForm(datos_estudio, instance=prod, empresa=empresa_estudio)
        self.assertTrue(form_edit.is_valid(), form_edit.errors.as_text())
        prod_editado = form_edit.save()
        self.assertEqual(prod_editado.detalle, 'HONORARIOS MENSUALES')

