from django.utils import timezone

def validar_clu_cliente_armeria(cliente, empresa_id):
    """
    Verifica si para empresas de tipo ARMERIA el cliente posee una CLU válida (no vencida y no nula),
    a menos que sea policía (es_policia=True).
    Retorna (es_valido: bool, mensaje_error: str)
    """
    from empresas.models import Empresa
    from facturacion.models import ClienteProveedor
    from verticalidades.armeria.models import ExtensionArmeria
    
    if not empresa_id:
        return True, ""

    try:
        empresa = Empresa.objects.get(pk=empresa_id)
        if not empresa.tipo_actividad or empresa.tipo_actividad.upper() != "ARMERIA":
            return True, ""
    except Empresa.DoesNotExist:
        return True, ""

    if not cliente:
        return False, "Debe seleccionar un cliente para operar productos de Armería."

    # Si se pasa un ID entero o string en lugar del objeto cliente
    if not isinstance(cliente, ClienteProveedor):
        cliente_obj = ClienteProveedor.objects.filter(pk=cliente, empresa_id=empresa_id).first()
        if not cliente_obj:
            return False, "Cliente invalido o no encontrado."
        cliente = cliente_obj

    # Validación de cliente identificado: no se permite tipo_documento = '99' (Consumidor Final / Sin Identificar)
    if getattr(cliente, 'tipo_documento', '') == '99' or getattr(cliente, 'codigo_id', None) == 1:
        return False, "Debe identificar al cliente que compra este tipo de producto. Para poder avanzar debe seleccionar al cliente real."

    extension = ExtensionArmeria.objects.filter(cliente=cliente).first()
    if not extension:
        return False, f"El cliente '{cliente.razon_social}' NO posee CLU registrado en Armería."

    if extension.es_policia:
        return True, ""

    if extension.esta_vencida:
        vto_str = extension.clu_vto.strftime("%d/%m/%Y") if extension.clu_vto else "Sin fecha"
        return False, f"El CLU del cliente '{cliente.razon_social}' está VENCIDO ({vto_str}). No se permite la venta de artículos de Armería."

    return True, ""


def parsear_decimal_ar(val, default=0.0):
    """
    Parsea de forma segura y robusta un valor numérico recibido desde el frontend,
    manejando tanto formato es-AR ('444.808,00' o '444.808,0'),
    formato desformateado por JS ('444808.00' o '444808.0'),
    números directos (int, float, Decimal) o valores vacíos.
    Evita la multiplicación por 100 causada por eliminar el punto en valores ya normalizados.
    """
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    from decimal import Decimal
    if isinstance(val, Decimal):
        return float(val)

    texto = str(val).strip()
    if not texto:
        return default

    # Si contiene coma y punto: ej. "1.234.567,89" -> punto es miles, coma es decimal
    if ',' in texto and '.' in texto:
        texto = texto.replace('.', '').replace(',', '.')
    # Si contiene sólo coma: ej. "1234,56" o "444808,0" -> coma es decimal
    elif ',' in texto:
        texto = texto.replace(',', '.')
    # Si contiene sólo punto(s)
    elif '.' in texto:
        partes = texto.split('.')
        if len(partes) > 2:
            # Múltiples puntos: "1.234.567" -> separador de miles
            texto = texto.replace('.', '')
        else:
            # Un solo punto: notación decimal estándar (ej. "444808.00", "444808.0", "12.5")
            pass

    try:
        return float(texto)
    except (ValueError, TypeError):
        return default

