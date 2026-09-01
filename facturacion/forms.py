from django import forms
from core.forms import DecimalARField
from .models import (ClienteProveedor, 
                     Jurisdiccion, Compra, Venta, TipoComprobante, Preventa)
# ... (formularios previos)

class PreventaForm(forms.ModelForm):
    class Meta:
        model = Preventa
        fields = ['cliente', 'vendedor', 'es_consumidor_final']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select-sm'}),
            'vendedor': forms.Select(attrs={'class': 'w-full py-1.5 px-3 bg-white border border-slate-300 rounded text-sm font-bold text-slate-800 outline-none focus:border-blue-500 cursor-pointer shadow-sm uppercase'}),
            'es_consumidor_final': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500 cursor-pointer'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vendedor'].empty_label = None
        if 'es_consumidor_final' in self.fields:
            self.fields['es_consumidor_final'].required = False


class VentaForm(forms.ModelForm):
    class Meta:
        model = Venta
        exclude = [
            'ventas_id', 'usuario', 'fec_vta', 'asiento_id', 'periodo', 
            'saldo', 'cobrado', 'empresa', 'sucursal', 'estado',
            'cae', 'vto_cae', 'cod_qr', 'fec_cob'
        ]
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control-sm'}),
            'tipo': forms.Select(attrs={'class': 'form-select-sm'}),
            'punto': forms.NumberInput(attrs={'class': 'form-control-sm', 'placeholder': '0000'}),
            'numero': forms.TextInput(attrs={'class': 'form-control-sm', 'placeholder': '00000000'}),
            'cliente': forms.Select(attrs={'class': 'form-select-sm'}),
            'vendedor': forms.Select(attrs={'class': 'form-select-sm'}),
            'cajero': forms.Select(attrs={'class': 'form-select-sm'}),
            'moneda': forms.Select(attrs={'class': 'form-select-sm'}),
            'cotizacion': forms.NumberInput(attrs={'class': 'form-control-sm', 'step': '0.0001'}),
            'neto': forms.TextInput(),
            'iva': forms.TextInput(),
            'no_gravado': forms.TextInput(),
            'exento': forms.TextInput(),
            'p_iva': forms.TextInput(),
            'p_gcia': forms.TextInput(),
            'p_iibb': forms.TextInput(),
            'p_recbc': forms.TextInput(),
            'p_sircreb': forms.TextInput(),
            'p_mun': forms.TextInput(),
            'otros': forms.TextInput(),
            'total': forms.TextInput(attrs={'readonly': 'readonly'}),
            'efectivo': forms.TextInput(),
            'tarjeta': forms.TextInput(),
            'transferencia': forms.TextInput(),
            'valores': forms.TextInput(),
            'id_fac_rem': forms.NumberInput(attrs={'class': 'form-control-sm'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacemos que todos los campos de importes y cobros sean opcionales en el form
        opcionales = [
            'neto', 'iva', 'no_gravado', 'exento', 'p_iva', 'p_gcia', 
            'p_iibb', 'p_recbc', 'p_sircreb', 'p_mun', 'otros', 'total',
            'efectivo', 'tarjeta', 'transferencia', 'valores', 'dolares',
            'numero', 'condic'
        ]
        for campo in opcionales:
            if campo in self.fields:
                self.fields[campo].required = False
        
        if 'tipo' in self.fields:
            self.fields['tipo'].queryset = TipoComprobante.objects.filter(estado=True)
            self.fields['tipo'].to_field_name = "codigo"

class ClienteProveedorForm(forms.ModelForm):
    clasificacion_cli = forms.ChoiceField(choices=ClienteProveedor.CLASIFICACION_CLI, required=False, label="Clasificación (Cliente)")
    clasificacion_pro = forms.ChoiceField(choices=ClienteProveedor.CLASIFICACION_PRO, required=False, label="Clasificación (Proveedor)")

    class Meta:
        model = ClienteProveedor
        fields = [
            'razon_social', 'tipo_documento', 'cuit', 'fecha_nacimiento', 'tipo_entidad',
            'domicilio', 'codigo_postal', 'localidad', 'jurisdiccion',
            'contacto', 'telefono', 'correo',
            'condicion_iva', 'tipo_iibb', 'saldo_inicial', 'limite',
            'objetivo_mensual', 'observaciones', 'cta_pat', 'cta_res', 'usa_orden_compra'
        ]
        widgets = {
            'razon_social': forms.TextInput(),
            'tipo_documento': forms.Select(),
            'cuit': forms.TextInput(),
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
            'tipo_entidad': forms.Select(),
            'domicilio': forms.TextInput(),
            'codigo_postal': forms.TextInput(),
            'localidad': forms.TextInput(),
            'jurisdiccion': forms.Select(),
            'contacto': forms.TextInput(),
            'telefono': forms.TextInput(),
            'correo': forms.EmailInput(),
            'condicion_iva': forms.Select(),
            'tipo_iibb': forms.Select(),
            'saldo_inicial': forms.TextInput(),
            'limite': forms.TextInput(),
            'objetivo_mensual': forms.NumberInput(attrs={'step': '0.01'}),
            'observaciones': forms.Textarea(attrs={'rows': 2}),
            'usa_orden_compra': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500'})
        }

    def __init__(self, *args, **kwargs):
        empresa_id = kwargs.pop('empresa_id', None)
        super().__init__(*args, **kwargs)
        self._empresa_id = empresa_id  # Disponible en clean() para validación de cuentas CLIPRO
        # Estilo base para todos los campos (Premium Design)
        for field_name, field in self.fields.items():
            clase_actual = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{clase_actual} w-full rounded-xl border-gray-200 text-sm focus:ring-indigo-500 focus:border-indigo-500 transition-all".strip()

        # Campos que NO son obligatorios para crear un registro.
        # La validación estricta se hace en clean() según el tipo de documento.
        campos_opcionales = [
            'razon_social', 'cuit', 'fecha_nacimiento', 'domicilio', 'codigo_postal',
            'localidad', 'jurisdiccion', 'contacto', 'telefono', 'correo',
            'objetivo_mensual', 'observaciones', 'saldo_inicial', 'limite',
            'cta_pat', 'cta_res'
        ]
        for campo in campos_opcionales:
            if campo in self.fields:
                self.fields[campo].required = False

        self.default_cta_cli_id = ''
        self.default_cta_cli_nombre = ''
        self.default_cta_vta_id = ''
        self.default_cta_vta_nombre = ''
        self.default_cta_prov_id = ''
        self.default_cta_prov_nombre = ''

        if empresa_id:
            from contable.models import ParametrosContables
            try:
                params = ParametrosContables.objects.get(empresa_id=empresa_id)
                if params.cta_clientes_default:
                    self.default_cta_cli_id = params.cta_clientes_default.id
                    self.default_cta_cli_nombre = f"{params.cta_clientes_default.jerarquia} - {params.cta_clientes_default.cuenta}"
                if params.cta_ventas:
                    self.default_cta_vta_id = params.cta_ventas.id
                    self.default_cta_vta_nombre = f"{params.cta_ventas.jerarquia} - {params.cta_ventas.cuenta}"
                if params.cta_proveedores_default:
                    self.default_cta_prov_id = params.cta_proveedores_default.id
                    self.default_cta_prov_nombre = f"{params.cta_proveedores_default.jerarquia} - {params.cta_proveedores_default.cuenta}"
            except ParametrosContables.DoesNotExist:
                pass

        if self.instance and self.instance.pk:
            if self.instance.tipo_entidad == 1:
                self.fields['clasificacion_cli'].initial = self.instance.clasificacion
            else:
                self.fields['clasificacion_pro'].initial = self.instance.clasificacion
            
            # Obtener nombres de las cuentas actuales si existen
            from contable.models import Cuenta
            self.cta_pat_nombre = ''
            self.cta_res_nombre = ''
            if self.instance.cta_pat:
                cta = Cuenta.objects.filter(id=self.instance.cta_pat).first()
                if cta: self.cta_pat_nombre = f"{cta.jerarquia} - {cta.cuenta}"
            if self.instance.cta_res:
                cta = Cuenta.objects.filter(id=self.instance.cta_res).first()
                if cta: self.cta_res_nombre = f"{cta.jerarquia} - {cta.cuenta}"
        else:
            # Al crear, ocultamos saldo_inicial y limite (lógica para permisos a futuro)
            self.fields['saldo_inicial'].widget = forms.HiddenInput()
            self.fields['limite'].widget = forms.HiddenInput()
            self.fields['saldo_inicial'].initial = 0
            self.fields['limite'].initial = 0
            self.fields['clasificacion_cli'].initial = 'MINORISTA'
            self.fields['clasificacion_pro'].initial = 'BIENES DE CAMBIO'
            
            # Inicializar con valores vacíos para que Alpine JS se encargue
            self.cta_pat_nombre = ''
            self.cta_res_nombre = ''

    def clean(self):
        """
        Validación central del formulario basada prioritariamente en la Condición ante el IVA:
        1. Para RESPONSABLE INSCRIPTO, MONOTRIBUTO y EXENTO:
           - Se impone Tipo de Documento '80 - CUIT'.
           - CUIT es obligatorio de exactamente 11 dígitos numéricos.
        2. Para CONSUMIDOR FINAL:
           - Admite Tipo 99 (Sin Identificar -> CUIT='0'), 96 (DNI -> 7/8 dígitos) u 80 (CUIT -> 11 dígitos).
        """
        cleaned_data = super().clean()
        condicion_iva = cleaned_data.get('condicion_iva') or 'CONSUMIDOR FINAL'
        tipo_doc = cleaned_data.get('tipo_documento') or '99'
        cuit = str(cleaned_data.get('cuit') or '').replace('-', '').strip()
        cleaned_data['cuit'] = cuit
        razon_social = cleaned_data.get('razon_social')
        
        if not razon_social:
            self.add_error('razon_social', 'La razón social o nombre es obligatorio.')

        # 1. Reglas estrictas para Entidades Fiscales (RI, Monotributo, Exento)
        if condicion_iva in ['RESPONSABLE INSCRIPTO', 'MONOTRIBUTO', 'EXENTO']:
            cleaned_data['tipo_documento'] = '80'
            if not cuit or not cuit.isdigit() or len(cuit) != 11:
                self.add_error('cuit', f"Para {condicion_iva} el CUIT es obligatorio y debe tener exactamente 11 dígitos numéricos.")
        
        # 2. Reglas para Consumidor Final
        elif condicion_iva == 'CONSUMIDOR FINAL':
            if tipo_doc == '99' or not cuit or cuit in ['0', '00']:
                cleaned_data['tipo_documento'] = '99'
                cleaned_data['cuit'] = '0'
                # Limpiar error de cuit si vino vacío para tipo 99
                if 'cuit' in self.errors:
                    del self.errors['cuit']
            elif tipo_doc == '96':
                if not cuit.isdigit() or len(cuit) not in [7, 8]:
                    self.add_error('cuit', "Para DNI se requieren 7 u 8 dígitos numéricos.")
            elif tipo_doc == '80':
                if not cuit.isdigit() or len(cuit) != 11:
                    self.add_error('cuit', "Para CUIT se requieren 11 dígitos numéricos.")

        # 3. Reglas específicas para Proveedores (tipo_entidad == 2): No pueden ser Consumidor Final ni Sin Identificar (99)
        tipo_entidad = cleaned_data.get('tipo_entidad')
        if tipo_entidad == 2:
            if condicion_iva == 'CONSUMIDOR FINAL':
                self.add_error('condicion_iva', "Un proveedor debe poseer una condición fiscal válida (ej. Responsable Inscripto, Monotributo o Exento).")
            if cleaned_data.get('tipo_documento') == '99' or cuit in ['0', '00', '']:
                self.add_error('cuit', "Para registrar un proveedor el CUIT es obligatorio (11 dígitos numéricos).")

        # CLIPRO: Forzar cuentas contables según rol comercial.
        # Para Clientes (tipo=1), cta_pat y cta_res se imponen desde ParametrosContables,
        # ignorando cualquier valor que venga del formulario (campos bloqueados en frontend).
        if tipo_entidad == 1 and hasattr(self, '_empresa_id') and self._empresa_id:
            from contable.models import ParametrosContables
            _par = ParametrosContables.objects.filter(empresa_id=self._empresa_id).first()
            if _par:
                if _par.cta_clientes_default_id:
                    cleaned_data['cta_pat'] = _par.cta_clientes_default_id
                if _par.cta_ventas_id:
                    cleaned_data['cta_res'] = _par.cta_ventas_id

        # Set defaults for cta_pat and cta_res to 0 if left blank
        if cleaned_data.get('cta_pat') is None:
            cleaned_data['cta_pat'] = 0
        if cleaned_data.get('cta_res') is None:
            cleaned_data['cta_res'] = 0

        return cleaned_data


class JurisdiccionForm(forms.ModelForm):
    class Meta:
        model = Jurisdiccion
        fields = ['codigo', 'nombre']
        widgets = {
            'codigo': forms.TextInput(),
            'nombre': forms.TextInput(),
        }

class TipoComprobanteForm(forms.ModelForm):
    class Meta:
        model = TipoComprobante
        fields = ['codigo', 'detalle', 'signo', 'estado']
        widgets = {
            'codigo': forms.TextInput(),
            'detalle': forms.TextInput(),
            'signo': forms.NumberInput(),
            'estado': forms.CheckboxInput(),
        }

class CompraForm(forms.ModelForm):
    class Meta:
        model = Compra
        exclude = ['compras_id', 'usuario', 'modificado', 'asiento_id', 'periodo', 'saldo', 'pagado', 'empresa', 'sucursal']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control-sm'}),
            'tipo': forms.Select(attrs={'class': 'form-select-sm'}),
            'punto': forms.NumberInput(attrs={'class': 'form-control-sm', 'placeholder': '0000'}),
            'numero': forms.TextInput(attrs={'class': 'form-control-sm', 'placeholder': '00000000'}),
            'proveedor': forms.Select(attrs={'class': 'form-select-sm'}),
            'moneda': forms.Select(attrs={'class': 'form-select-sm'}),
            'cotizacion': forms.NumberInput(attrs={'class': 'form-control-sm', 'step': '0.0001'}),
            'neto': forms.TextInput(),
            'iva': forms.TextInput(),
            'no_gravado': forms.TextInput(),
            'exento': forms.TextInput(),
            'p_iva': forms.TextInput(),
            'p_gcia': forms.TextInput(),
            'p_iibb': forms.TextInput(),
            'p_recbc': forms.TextInput(),
            'p_sircreb': forms.TextInput(),
            'p_mun': forms.TextInput(),
            'otros': forms.TextInput(),
            'total': forms.TextInput(attrs={'readonly': 'readonly'}),
            'id_fac_rem': forms.NumberInput(attrs={'class': 'form-control-sm'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacemos que todos los campos de importes sean opcionales
        opcionales = [
            'neto', 'iva', 'no_gravado', 'exento', 'p_iva', 'p_gcia', 
            'p_iibb', 'p_recbc', 'p_sircreb', 'p_mun', 'otros', 'total'
        ]
        for campo in opcionales:
            if campo in self.fields:
                self.fields[campo].required = False

        if 'tipo' in self.fields:
            self.fields['tipo'].queryset = TipoComprobante.objects.all()
            self.fields['tipo'].to_field_name = "codigo"
