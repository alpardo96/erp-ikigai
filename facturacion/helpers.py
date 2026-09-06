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

    extension = ExtensionArmeria.objects.filter(cliente=cliente).first()
    if not extension:
        return False, f"El cliente '{cliente.razon_social}' NO posee CLU registrado en Armería."

    if extension.es_policia:
        return True, ""

    if extension.esta_vencida:
        vto_str = extension.clu_vto.strftime("%d/%m/%Y") if extension.clu_vto else "Sin fecha"
        return False, f"El CLU del cliente '{cliente.razon_social}' está VENCIDO ({vto_str}). No se permite la venta de artículos de Armería."

    return True, ""
