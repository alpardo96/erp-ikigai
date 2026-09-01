from django.utils import timezone

# Columnas predeterminadas requeridas: ID Asiento, fecha, concepto, debe, haber, saldo, condic
COLUMNAS_MAYOR_CATALOGO = [
    {'clave': 'asiento_id', 'nombre': 'ID Asiento', 'origen': 'Asiento', 'default': True},
    {'clave': 'fecha', 'nombre': 'Fecha', 'origen': 'Asiento', 'default': True},
    {'clave': 'concepto', 'nombre': 'Concepto', 'origen': 'Asiento', 'default': True},
    {'clave': 'leyenda', 'nombre': 'Leyenda', 'origen': 'Línea', 'default': False},
    {'clave': 'cuenta_id', 'nombre': 'ID Cuenta', 'origen': 'Cuenta', 'default': False},
    {'clave': 'jerarquia', 'nombre': 'Jerarquía', 'origen': 'Cuenta', 'default': False},
    {'clave': 'cuenta', 'nombre': 'Nombre Cuenta', 'origen': 'Cuenta', 'default': False},
    {'clave': 'tipo', 'nombre': 'Tipo Cuenta', 'origen': 'Cuenta', 'default': False},
    {'clave': 'debe', 'nombre': 'Debe', 'origen': 'Línea', 'default': True},
    {'clave': 'haber', 'nombre': 'Haber', 'origen': 'Línea', 'default': True},
    {'clave': 'saldo', 'nombre': 'Saldo Acumulado', 'origen': 'Calculado', 'default': True},
    {'clave': 'condic', 'nombre': 'Condición', 'origen': 'Asiento', 'default': True},
    {'clave': 'sucursal', 'nombre': 'Sucursal', 'origen': 'Asiento', 'default': False},

    # Opcionales
    {'clave': 'numero_diario', 'nombre': 'Nº Diario', 'origen': 'Asiento', 'default': False},
    {'clave': 'monto_asiento', 'nombre': 'Monto Asiento', 'origen': 'Asiento', 'default': False},
    {'clave': 'modulo', 'nombre': 'Módulo', 'origen': 'Asiento', 'default': False},
    {'clave': 'cli_pro_asiento', 'nombre': 'Cli/Prov Asiento', 'origen': 'Asiento', 'default': False},
    {'clave': 'fec_vto_asiento', 'nombre': 'Vto Asiento', 'origen': 'Asiento', 'default': False},
    {'clave': 'anulado', 'nombre': 'Anulado', 'origen': 'Asiento', 'default': False},
    {'clave': 'fec_anulacion', 'nombre': 'Fecha Anulación', 'origen': 'Asiento', 'default': False},
    {'clave': 'ejercicio', 'nombre': 'Ejercicio', 'origen': 'Asiento', 'default': False},
    {'clave': 'sesion_caja', 'nombre': 'Sesión Caja', 'origen': 'Asiento', 'default': False},

    {'clave': 'orden_linea', 'nombre': 'Orden Línea', 'origen': 'Línea', 'default': False},
    {'clave': 'divisa', 'nombre': 'Divisa', 'origen': 'Línea', 'default': False},
    {'clave': 'cotizacion', 'nombre': 'Cotización', 'origen': 'Línea', 'default': False},
    {'clave': 'debe_divisa', 'nombre': 'Debe Divisa', 'origen': 'Línea', 'default': False},
    {'clave': 'haber_divisa', 'nombre': 'Haber Divisa', 'origen': 'Línea', 'default': False},
    {'clave': 'fec_vto_linea', 'nombre': 'Vto Línea', 'origen': 'Línea', 'default': False},
    {'clave': 'cli_pro_linea', 'nombre': 'Cli/Prov Línea', 'origen': 'Línea', 'default': False},

    {'clave': 'imputable', 'nombre': 'Imputable', 'origen': 'Cuenta', 'default': False},
    {'clave': 'codigo_legacy', 'nombre': 'Cód. Legacy', 'origen': 'Cuenta', 'default': False},
    {'clave': 'tipo_disponibilidad', 'nombre': 'Disponibilidad', 'origen': 'Cuenta', 'default': False},
    {'clave': 'rg_830', 'nombre': 'Régimen RG830', 'origen': 'Cuenta', 'default': False},
]

def obtener_columnas_seleccionadas(request):
    """Devuelve las claves de las columnas a mostrar según la petición GET (o por defecto)."""
    columnas_solicitadas = request.GET.getlist('columnas')
    if not columnas_solicitadas:
        return [c['clave'] for c in COLUMNAS_MAYOR_CATALOGO if c['default']]
    return columnas_solicitadas


def obtener_valor_columna_movimiento(mov, cta_data, col_key):
    """Retorna el valor correspondiente a una columna específica para un movimiento."""
    asiento = mov.asiento
    cuenta = cta_data['cuenta']

    if col_key == 'asiento_id':
        return asiento.asiento_id
    elif col_key == 'numero_diario':
        return asiento.numero_diario or asiento.asiento_id
    elif col_key == 'fecha':
        return asiento.fecha.strftime('%d/%m/%Y') if asiento.fecha else ''
    elif col_key == 'concepto':
        return asiento.concepto or ''
    elif col_key == 'leyenda':
        return mov.leyenda or ''
    elif col_key == 'cuenta_id':
        return cuenta.id
    elif col_key == 'jerarquia':
        return cuenta.jerarquia
    elif col_key == 'cuenta':
        return cuenta.cuenta
    elif col_key == 'tipo':
        return cuenta.get_tipo_display() if hasattr(cuenta, 'get_tipo_display') else cuenta.tipo
    elif col_key == 'debe':
        return float(mov.debe) if mov.debe else 0.0
    elif col_key == 'haber':
        return float(mov.haber) if mov.haber else 0.0
    elif col_key == 'saldo':
        return float(mov.saldo_acumulado) if hasattr(mov, 'saldo_acumulado') else 0.0
    elif col_key == 'condic':
        return asiento.get_condic_display() if hasattr(asiento, 'get_condic_display') else asiento.condic
    elif col_key == 'sucursal':
        return asiento.sucursal.nombre if asiento.sucursal else (asiento.sucursal_id or '')
    elif col_key == 'monto_asiento':
        return float(asiento.monto) if asiento.monto else 0.0
    elif col_key == 'modulo':
        return asiento.get_modulo_display() if hasattr(asiento, 'get_modulo_display') else asiento.modulo
    elif col_key == 'cli_pro_asiento':
        return asiento.cli_pro.razon_social if asiento.cli_pro else ''
    elif col_key == 'fec_vto_asiento':
        return asiento.fec_vto.strftime('%d/%m/%Y') if asiento.fec_vto else ''
    elif col_key == 'anulado':
        return 'Sí' if asiento.anulado else 'No'
    elif col_key == 'fec_anulacion':
        return asiento.fec_anulacion.strftime('%d/%m/%Y %H:%M') if asiento.fec_anulacion else ''
    elif col_key == 'ejercicio':
        return asiento.ejercicio.ejercicio if asiento.ejercicio else (asiento.ejercicio_id or '')
    elif col_key == 'sesion_caja':
        return asiento.sesion_caja_id or ''
    elif col_key == 'orden_linea':
        return mov.orden
    elif col_key == 'divisa':
        return mov.divisa or ''
    elif col_key == 'cotizacion':
        return float(mov.cotizacion) if mov.cotizacion else 1.0
    elif col_key == 'debe_divisa':
        return float(mov.debe_divisa) if mov.debe_divisa else 0.0
    elif col_key == 'haber_divisa':
        return float(mov.haber_divisa) if mov.haber_divisa else 0.0
    elif col_key == 'fec_vto_linea':
        return mov.fec_vto.strftime('%d/%m/%Y') if mov.fec_vto else ''
    elif col_key == 'cli_pro_linea':
        return mov.cli_pro.razon_social if mov.cli_pro else ''
    elif col_key == 'imputable':
        return 'Sí' if cuenta.imputable == 1 else 'No'
    elif col_key == 'codigo_legacy':
        return cuenta.codigo or ''
    elif col_key == 'tipo_disponibilidad':
        return cuenta.tipo_disponibilidad or ''
    elif col_key == 'rg_830':
        return cuenta.rg_830 or ''
    return ''
