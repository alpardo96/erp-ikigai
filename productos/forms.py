from django import forms
from .models import Producto, Marca, Rubro, Familia, Subfamilia
from core.forms import DecimalARField
from empresas.models import Sucursal

class MarcaForm(forms.ModelForm):
    class Meta:
        model = Marca
        # Catálogos unificados por Empresa: se remueve el campo 'sucursales'
        fields = ['detalle', 'margen']
        widgets = {
            'detalle': forms.TextInput(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
            'margen': forms.NumberInput(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)

class RubroForm(forms.ModelForm):
    class Meta:
        model = Rubro
        # Catálogos unificados por Empresa: se remueve el campo 'sucursales'
        fields = ['detalle', 'margen', 'cta_ventas', 'cta_compras']
        widgets = {
            'detalle': forms.TextInput(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
            'margen': forms.NumberInput(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
            'cta_ventas': forms.Select(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
            'cta_compras': forms.Select(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        if empresa:
            from contable.models import Cuenta
            # Show only 'imputable' accounts for operations
            cuentas = Cuenta.objects.filter(empresa=empresa, imputable=True).order_by('jerarquia')
            self.fields['cta_ventas'].queryset = cuentas
            self.fields['cta_compras'].queryset = cuentas

class FamiliaForm(forms.ModelForm):
    class Meta:
        model = Familia
        # Catálogos unificados por Empresa: se remueve el campo 'sucursales'
        fields = ['rubro', 'detalle', 'margen']
        widgets = {
            'rubro': forms.Select(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
            'detalle': forms.TextInput(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
            'margen': forms.NumberInput(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        if empresa:
            self.fields['rubro'].queryset = Rubro.objects.filter(empresa=empresa)

class SubfamiliaForm(forms.ModelForm):
    class Meta:
        model = Subfamilia
        fields = ['familia', 'detalle', 'margen']
        widgets = {
            'familia': forms.Select(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
            'detalle': forms.TextInput(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
            'margen': forms.NumberInput(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        if empresa:
            self.fields['familia'].queryset = Familia.objects.filter(empresa=empresa)

class ProductoForm(forms.ModelForm):
    # Distribución (Plan 074): llegan en formato es-AR desde inputs `.fInputAR`.
    peso_unitario_kg = DecimalARField(
        max_digits=10, decimal_places=3, required=False, initial=0,
        label="Peso por Unidad de Venta (kg)",
        widget=forms.TextInput(attrs={
            'class': 'fInputAR w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2',
            'placeholder': '0,000'}))
    unidades_por_bulto = DecimalARField(
        max_digits=10, decimal_places=2, required=False, initial=0,
        label="Unidades por Bulto",
        widget=forms.TextInput(attrs={
            'class': 'fInputAR w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2',
            'placeholder': '0,00'}))

    def clean_peso_unitario_kg(self):
        return self.cleaned_data.get('peso_unitario_kg') or 0

    def clean_unidades_por_bulto(self):
        return self.cleaned_data.get('unidades_por_bulto') or 0

    def clean_unidad_venta(self):
        """Conserva o procesa el valor de unidad_venta / calibre según la actividad.

        - En DISTRIBUCION: maneja los choices (UNIDAD, BULTO, KG).
        - En ARMERIA: almacena el calibre (texto libre, ej. C.22, 9mm).
        - En otras actividades o default: repone el valor anterior o el default del modelo ('UNIDAD').
        """
        valor = self.cleaned_data.get('unidad_venta')
        if valor:
            return str(valor).strip()
        if self.instance and self.instance.pk and self.instance.unidad_venta:
            return self.instance.unidad_venta
        return Producto._meta.get_field('unidad_venta').default

    class Meta:
        model = Producto
        fields = [
            'cod_prov', 'cod_fab', 'detalle', 'proveedor', 'minimo', 'ptopedir',
            'creden', 'moneda', 'alic_iva', 'margen', 'marca', 'rubro', 'familia', 'subfamilia', 'subprod',
            # Distribución (Plan 074). Sólo se muestran si la empresa es DISTRIBUIDORA;
            # en el resto quedan en su valor por defecto.
            'codigo_anterior', 'unidad_venta', 'peso_unitario_kg', 'unidades_por_bulto',
            'observaciones',
        ]
        widgets = {
            'observaciones': forms.Textarea(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2', 'rows': 2, 'placeholder': 'Notas u observaciones del producto...'}),
            'detalle': forms.TextInput(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
            'cod_prov': forms.TextInput(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
            'cod_fab': forms.TextInput(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
            'proveedor': forms.Select(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
            'minimo': forms.NumberInput(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
            'ptopedir': forms.NumberInput(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
            'moneda': forms.Select(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
            'alic_iva': forms.Select(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
            'margen': forms.NumberInput(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2', 'step': '0.01'}),
            'marca': forms.Select(attrs={
                'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2',
                'hx-get': '/productos/obtener-margen/',
                'hx-target': '#margen-marca',
                'hx-vals': 'js:{tipo: "marca", id: event.target.value}',
                'hx-trigger': 'change'
            }),
            'rubro': forms.Select(attrs={
                'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2',
                'hx-get': '/productos/obtener-margen/',
                'hx-target': '#rubro-prod-margen',
                'hx-vals': 'js:{tipo: "rubro", id: event.target.value}',
                'hx-trigger': 'change',
                'hx-on:change': 'htmx.ajax("GET", "/productos/filtrar-familias/", {target: "#id_familia", swap: "innerHTML", values: {id: this.value}})'
            }),
            'familia': forms.Select(attrs={
                'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2',
                'hx-get': '/productos/obtener-margen/',
                'hx-target': '#familia-margen',
                'hx-vals': 'js:{tipo: "familia", id: event.target.value}',
                'hx-trigger': 'change',
                'hx-on:change': 'htmx.ajax("GET", "/productos/filtrar-subfamilias/", {target: "#id_subfamilia", swap: "innerHTML", values: {id: this.value}})'
            }),
            'subfamilia': forms.Select(attrs={
                'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2',
                'hx-get': '/productos/obtener-margen/',
                'hx-target': '#subfamilia-margen',
                'hx-vals': 'js:{tipo: "subfamilia", id: event.target.value}',
                'hx-trigger': 'change'
            }),
            'creden': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500'}),
            'subprod': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500'}),
            # --- Distribución (Plan 074) ---
            'codigo_anterior': forms.TextInput(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2', 'placeholder': 'Código del sistema anterior'}),
            'unidad_venta': forms.Select(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2'}),
            # `peso_unitario_kg` y `unidades_por_bulto` se declaran arriba como
            # DecimalARField, que trae su propio widget.
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        self._empresa = empresa
        if self.instance and self.instance.pk and hasattr(self.instance, 'alic_iva_porc'):
            self.initial['alic_iva'] = self.instance.alic_iva_porc

        # Unidad de Venta / Calibre según actividad:
        if empresa and getattr(empresa, 'tipo_actividad', '') == 'ARMERIA':
            # En Armería se utiliza para almacenar el calibre (ej. C.22, 9mm, .308 WIN) en rubros que inicien con ARMA o MUNI
            self.fields['unidad_venta'] = forms.CharField(
                max_length=30,
                required=False,
                label="Calibre",
                widget=forms.TextInput(attrs={
                    'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2',
                    'placeholder': 'Ej. C.22, 9mm, .308'
                })
            )
        elif not empresa or empresa.tipo_actividad != 'DISTRIBUCION':
            # En otras verticales lo hacemos no-obligatorio para que el form no rompa
            self.fields['unidad_venta'].required = False

        if empresa:
            self.fields['marca'].queryset = Marca.objects.filter(empresa=empresa).order_by('detalle')
            self.fields['rubro'].queryset = Rubro.objects.filter(empresa=empresa).order_by('detalle')
            self.fields['familia'].queryset = Familia.objects.filter(empresa=empresa).order_by('detalle')
            from facturacion.models import ClienteProveedor
            from django.db.models import Q
            qs_proveedor = ClienteProveedor.objects.filter(
                Q(empresa=empresa) | Q(empresa__isnull=True), 
                tipo_entidad=2
            )
            if self.instance and self.instance.proveedor_id:
                qs_proveedor = qs_proveedor | ClienteProveedor.objects.filter(pk=self.instance.proveedor_id)
            self.fields['proveedor'].queryset = qs_proveedor.distinct().order_by('razon_social')


class TomaInventarioFiltroForm(forms.Form):
    """
    Formulario de configuración y filtros para iniciar un inventario general o parcial (Plan 095).
    """
    ALCANCE_CHOICES = [
        ('PARCIAL', 'Inventario Parcial (Según filtros)'),
        ('GENERAL', 'Inventario General (Todos los productos)'),
    ]

    tipo_alcance = forms.ChoiceField(
        choices=ALCANCE_CHOICES,
        initial='PARCIAL',
        label="Tipo de Inventario",
        widget=forms.Select(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500'})
    )
    rubro = forms.ModelChoiceField(
        queryset=Rubro.objects.none(),
        required=False,
        empty_label="-- Todos los Rubros --",
        widget=forms.Select(attrs={
            'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500',
            'hx-get': '/productos/filtrar-familias/',
            'hx-target': '#id_familia',
            'hx-trigger': 'change'
        })
    )
    familia = forms.ModelChoiceField(
        queryset=Familia.objects.none(),
        required=False,
        empty_label="-- Todas las Familias --",
        widget=forms.Select(attrs={
            'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500',
            'hx-get': '/productos/filtrar-subfamilias/',
            'hx-target': '#id_subfamilia',
            'hx-trigger': 'change'
        })
    )
    subfamilia = forms.ModelChoiceField(
        queryset=Subfamilia.objects.none(),
        required=False,
        empty_label="-- Todas las Subfamilias --",
        widget=forms.Select(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500'})
    )
    marca = forms.ModelChoiceField(
        queryset=Marca.objects.none(),
        required=False,
        empty_label="-- Todas las Marcas --",
        widget=forms.Select(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500'})
    )
    proveedor = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="-- Todos los Proveedores --",
        widget=forms.Select(attrs={'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500'})
    )
    buscar_texto = forms.CharField(
        required=False,
        label="Buscar por Código o Detalle",
        widget=forms.TextInput(attrs={
            'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Ej. PISTOLA, 5320, BERSA...'
        })
    )
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500',
            'rows': 2,
            'placeholder': 'Observaciones o motivo de la toma de inventario...'
        })
    )

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        if empresa:
            self.fields['rubro'].queryset = Rubro.objects.filter(empresa=empresa).order_by('detalle')
            self.fields['familia'].queryset = Familia.objects.filter(empresa=empresa).order_by('detalle')
            self.fields['subfamilia'].queryset = Subfamilia.objects.filter(familia__rubro__empresa=empresa).order_by('detalle')
            self.fields['marca'].queryset = Marca.objects.filter(empresa=empresa).order_by('detalle')
            from facturacion.models import ClienteProveedor
            from django.db.models import Q
            self.fields['proveedor'].queryset = ClienteProveedor.objects.filter(
                Q(empresa=empresa) | Q(empresa__isnull=True),
                tipo_entidad=2
            ).distinct().order_by('razon_social')


class TomaInventarioItemEditForm(forms.Form):
    """Edición ágil de cantidad contada de un ítem en la grilla."""
    cantidad_contada = DecimalARField(
        max_digits=15, decimal_places=2, required=True,
        widget=forms.TextInput(attrs={
            'class': 'fInputAR w-28 text-center font-bold text-gray-900 border border-gray-300 rounded p-1 focus:ring-2 focus:ring-blue-500'
        })
    )
    observaciones = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full text-xs text-gray-900 border border-gray-300 rounded p-1 focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Nota...'
        })
    )


class TomaInventarioRechazoForm(forms.Form):
    """Formulario para rechazar / devolver a conteo un inventario pendiente."""
    motivo_rechazo = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'w-full bg-white text-gray-900 border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-red-500',
            'rows': 3,
            'placeholder': 'Indique el motivo por el cual se devuelve el inventario para reconteo...'
        })
    )

