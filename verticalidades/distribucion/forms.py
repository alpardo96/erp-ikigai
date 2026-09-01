"""Formularios de los maestros de Distribución (Plan 074, fase 1a).

Todos reciben `empresa_id` como primer argumento para acotar los combos a la empresa
de la sesión: regla inflexible de multi-tenant del proyecto.
"""
from django import forms

from core.forms import DateInputHTML5, DecimalARField
from empresas.models import Sucursal
from .models import (DomicilioEntrega, MotivoDevolucion, Personal, Vehiculo,
                     ZonaReparto)

INPUT_CLASS = ("w-full rounded-xl border-gray-200 text-sm "
               "focus:ring-indigo-500 focus:border-indigo-500 transition-all")
CHECK_CLASS = "h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"


class _BaseDistribucionForm(forms.ModelForm):
    """Aplica el estilo Tailwind estándar del panel de configuración."""

    def _estilar(self):
        for nombre, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = CHECK_CLASS
            else:
                actual = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f"{actual} {INPUT_CLASS}".strip()


class ZonaRepartoForm(_BaseDistribucionForm):
    class Meta:
        model = ZonaReparto
        fields = ['nombre', 'orden', 'activa']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'SAN CAYETANO'}),
            'orden': forms.NumberInput(attrs={'min': 0}),
        }

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa_id = empresa_id
        self._estilar()

    def clean_nombre(self):
        nombre = (self.cleaned_data.get('nombre') or '').upper().strip()
        qs = ZonaReparto.objects.filter(empresa_id=self.empresa_id, nombre=nombre)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe una zona con ese nombre.")
        return nombre


class PersonalForm(_BaseDistribucionForm):
    comision_porcentaje = DecimalARField(
        max_digits=5, decimal_places=2, required=False, initial=0,
        label="Comisión (%)",
        widget=forms.TextInput(attrs={'class': 'fInputAR', 'placeholder': '0,00'}))

    class Meta:
        model = Personal
        fields = ['codigo', 'nombre', 'documento', 'telefono', 'usuario',
                  'es_vendedor', 'es_repartidor', 'es_cobrador',
                  'comision_porcentaje', 'zona', 'activo',
                  'fecha_alta', 'fecha_baja', 'codigo_anterior']
        widgets = {
            'codigo': forms.NumberInput(attrs={'min': 1, 'placeholder': 'Automático'}),
            'nombre': forms.TextInput(attrs={'placeholder': 'JUAN PEREZ'}),
            'documento': forms.TextInput(attrs={'placeholder': '20123456'}),
            'telefono': forms.TextInput(attrs={'placeholder': '381 555-0000'}),
            'fecha_alta': DateInputHTML5(),
            'fecha_baja': DateInputHTML5(),
            'codigo_anterior': forms.TextInput(attrs={'placeholder': 'Código del sistema anterior'}),
        }

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa_id = empresa_id
        # El código es opcional: si viene vacío, el modelo asigna el siguiente.
        self.fields['codigo'].required = False
        if empresa_id:
            self.fields['zona'].queryset = ZonaReparto.objects.filter(
                empresa_id=empresa_id, activa=True).order_by('orden', 'nombre')
            # Sólo usuarios habilitados en la empresa, y sin `Personal` ya asignado
            # (la relación es OneToOne).
            from django.contrib.auth.models import User
            usuarios = User.objects.filter(perfil__empresas__id=empresa_id, is_active=True)
            ocupados = Personal.objects.filter(empresa_id=empresa_id, usuario__isnull=False)
            if self.instance.pk:
                ocupados = ocupados.exclude(pk=self.instance.pk)
            usuarios = usuarios.exclude(id__in=ocupados.values_list('usuario_id', flat=True))
            self.fields['usuario'].queryset = usuarios.distinct().order_by('username')
        self.fields['usuario'].required = False
        self.fields['usuario'].empty_label = "Sin acceso al sistema"
        self.fields['zona'].empty_label = "Sin zona asignada"
        self._estilar()

    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo')
        if not codigo:
            return codigo
        qs = Personal.objects.filter(empresa_id=self.empresa_id, codigo=codigo)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe personal con ese código.")
        return codigo

    def clean_comision_porcentaje(self):
        # El campo es opcional: vacío significa sin comisión, no NULL.
        return self.cleaned_data.get('comision_porcentaje') or 0

    def clean(self):
        cleaned = super().clean()
        if not any([cleaned.get('es_vendedor'), cleaned.get('es_repartidor'),
                    cleaned.get('es_cobrador')]):
            raise forms.ValidationError(
                "Asigná al menos un rol: vendedor, repartidor o cobrador.")
        alta, baja = cleaned.get('fecha_alta'), cleaned.get('fecha_baja')
        if alta and baja and baja < alta:
            self.add_error('fecha_baja', "La fecha de baja no puede ser anterior a la de alta.")
        return cleaned


class VehiculoForm(_BaseDistribucionForm):
    capacidad_kg = DecimalARField(
        max_digits=15, decimal_places=2, required=False, initial=0,
        label="Capacidad (kg)",
        widget=forms.TextInput(attrs={'class': 'fInputAR', 'placeholder': '0,00'}))

    class Meta:
        model = Vehiculo
        fields = ['patente', 'descripcion', 'sucursal', 'capacidad_kg', 'refrigerado', 'activo']
        widgets = {
            'patente': forms.TextInput(attrs={'placeholder': 'AB123CD'}),
            'descripcion': forms.TextInput(attrs={'placeholder': 'FURGÓN BLANCO'}),
        }

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa_id = empresa_id
        if empresa_id:
            self.fields['sucursal'].queryset = Sucursal.objects.filter(
                empresa_id=empresa_id).order_by('nombre')
        self._estilar()

    def clean_capacidad_kg(self):
        # Vacío significa "sin capacidad declarada" (0), no NULL.
        return self.cleaned_data.get('capacidad_kg') or 0

    def clean_patente(self):
        patente = (self.cleaned_data.get('patente') or '').upper().strip()
        qs = Vehiculo.objects.filter(empresa_id=self.empresa_id, patente=patente)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe un vehículo con esa patente.")
        return patente


class MotivoDevolucionForm(_BaseDistribucionForm):
    class Meta:
        model = MotivoDevolucion
        fields = ['codigo', 'descripcion', 'momento', 'sugiere_apto_reventa',
                  'requiere_observacion', 'activo']
        widgets = {
            'codigo': forms.TextInput(attrs={'placeholder': 'NEGOCIO_CERRADO'}),
            'descripcion': forms.TextInput(attrs={'placeholder': 'El negocio estaba cerrado'}),
        }

    def __init__(self, empresa_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa_id = empresa_id
        self._estilar()

    def clean_codigo(self):
        codigo = (self.cleaned_data.get('codigo') or '').upper().strip().replace(' ', '_')
        qs = MotivoDevolucion.objects.filter(empresa_id=self.empresa_id, codigo=codigo)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe un motivo con ese código.")
        return codigo


class DomicilioEntregaForm(_BaseDistribucionForm):
    """Punto físico de entrega. La zona y la agenda viven acá, no en el cliente."""

    class Meta:
        model = DomicilioEntrega
        fields = ['nombre', 'domicilio', 'localidad', 'codigo_postal', 'zona',
                  'contacto', 'telefono', 'horario_recepcion', 'observaciones_entrega',
                  'es_principal', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'SUCURSAL CENTRO'}),
            'domicilio': forms.TextInput(attrs={'placeholder': 'Calle y número'}),
            'localidad': forms.TextInput(),
            'codigo_postal': forms.TextInput(),
            'contacto': forms.TextInput(attrs={'placeholder': 'A quién buscar al llegar'}),
            'telefono': forms.TextInput(),
            'horario_recepcion': forms.TextInput(attrs={'placeholder': 'Ej. Hasta las 13'}),
            'observaciones_entrega': forms.Textarea(
                attrs={'rows': 2, 'placeholder': 'Ej. Entrar por la calle lateral'}),
        }

    def __init__(self, empresa_id=None, cliente=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa_id = empresa_id
        self.cliente = cliente
        if empresa_id:
            self.fields['zona'].queryset = ZonaReparto.objects.filter(
                empresa_id=empresa_id, activa=True).order_by('orden', 'nombre')
        self.fields['zona'].required = False
        self.fields['zona'].empty_label = "Sin zona asignada"
        for campo in ('localidad', 'codigo_postal', 'contacto', 'telefono',
                      'horario_recepcion', 'observaciones_entrega'):
            self.fields[campo].required = False
        self._estilar()

    def clean_nombre(self):
        nombre = (self.cleaned_data.get('nombre') or '').upper().strip()
        cliente = self.cliente or getattr(self.instance, 'cliente', None)
        if cliente:
            qs = DomicilioEntrega.objects.filter(cliente=cliente, nombre=nombre)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("El cliente ya tiene un domicilio con ese nombre.")
        return nombre


class ExtensionDistribuidoraForm(forms.ModelForm):
    """Datos del cliente propios de la actividad DISTRIBUIDORA (Plan 074 §5.C).

    El coeficiente se carga a mano cliente por cliente; la clasificación es
    descriptiva y no interviene en el precio.
    """

    coeficiente_mayorista = DecimalARField(
        max_digits=10, decimal_places=4, required=False, initial=1,
        label="Coeficiente Mayorista",
        widget=forms.TextInput(attrs={'class': 'fInputAR', 'placeholder': '1,0000'}))

    class Meta:
        from .models import ExtensionDistribuidora
        model = ExtensionDistribuidora
        # La zona NO está acá: vive en `DomicilioEntrega`, porque un cliente con
        # sucursales entrega en varias zonas.
        fields = ['clasificacion', 'coeficiente_mayorista', 'bloqueado_credito']
        widgets = {
            'clasificacion': forms.TextInput(attrs={'placeholder': 'Ej. A, B, C'}),
        }

    def __init__(self, *args, empresa_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['clasificacion'].required = False

        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = "h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
            else:
                clase_actual = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f"{clase_actual} w-full rounded-xl border-gray-200 text-sm focus:ring-indigo-500 focus:border-indigo-500 transition-all".strip()

    def clean_coeficiente_mayorista(self):
        # Vacío significa "sin recargo ni descuento": el precio de lista tal cual.
        return self.cleaned_data.get('coeficiente_mayorista') or 1

