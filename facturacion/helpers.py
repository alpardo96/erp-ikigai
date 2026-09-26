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


def deducir_jurisdiccion_por_provincia_o_cp(provincia_texto=None, codigo_postal=None):
    """
    Deduce la instancia de Jurisdiccion a partir del nombre de provincia o del Código Postal.
    Maneja alias históricos de VFP, nombres oficiales y rangos de código postal argentino.
    """
    from facturacion.models import Jurisdiccion
    import re
    import unicodedata

    def _limpiar(txt):
        if not txt:
            return ''
        nfkd = unicodedata.normalize('NFKD', str(txt))
        sin_tildes = "".join([c for c in nfkd if not unicodedata.combining(c)])
        return sin_tildes.strip().upper()

    alias_provincias = {
        'TUCUMAN': 'TUCUMAN',
        'SIMOCA': 'TUCUMAN',
        'BUENOS AIRES': 'BUENOS AIRES',
        'BS AS': 'BUENOS AIRES',
        'BS. AS.': 'BUENOS AIRES',
        'CAPITAL FEDERAL': 'CAPITAL FEDERAL',
        'CIUDAD AUTONOMA DE B': 'CAPITAL FEDERAL',
        'CIUDAD AUTONOMA DE BUENOS AIRES': 'CAPITAL FEDERAL',
        'CABA': 'CAPITAL FEDERAL',
        'SALTA': 'SALTA',
        'SANTIAGO DEL ESTERO': 'SGO. DEL ESTERO',
        'STGO DEL ESTERO': 'SGO. DEL ESTERO',
        'CATAMARCA': 'CATAMARCA',
        'CASTAMARCA': 'CATAMARCA',
        'CORDOBA': 'CORDOBA',
        'NEUQUEN': 'NEUQUEN',
        'JUJUY': 'JUJUY',
        'SAN LUIS': 'SAN LUIS',
        'MENDOZA': 'MENDOZA',
        'SANTA FE': 'SANTA FE',
        'SANTA CRUZ': 'SANTA CRUZ',
        'MISIONES': 'MISIONES',
        'RIO NEGRO': 'RIO NEGRO',
        'LA RIOJA': 'LA RIOJA',
        'CORRIENTES': 'CORRIENTES',
        'CHUBUT': 'CHUBUT',
        'CHACO': 'CHACO',
        'SAN JUAN': 'SAN JUAN',
        'ENTRE RIOS': 'ENTRE RIOS',
        'LA PAMPA': 'LA PAMPA',
        'FORMOSA': 'FORMOSA',
        'TIERRA DEL FUEGO': 'TIERRA DEL FUEGO'
    }

    # 1. Búsqueda por texto de provincia
    if provincia_texto:
        p_clean = _limpiar(provincia_texto)
        nombre_oficial = alias_provincias.get(p_clean)
        if nombre_oficial:
            j = Jurisdiccion.objects.filter(nombre__iexact=nombre_oficial).first()
            if j:
                return j
        # Búsqueda directa parcial por nombre
        for k, v in alias_provincias.items():
            if k in p_clean or p_clean in k:
                j = Jurisdiccion.objects.filter(nombre__iexact=v).first()
                if j:
                    return j

    # 2. Deducción por Código Postal
    if codigo_postal:
        m = re.search(r'\d{4}', str(codigo_postal))
        if m:
            num = int(m.group(0))
            pcia = None
            if 4000 <= num <= 4199: pcia = 'TUCUMAN'
            elif 4400 <= num <= 4499: pcia = 'SALTA'
            elif 4200 <= num <= 4399: pcia = 'SGO. DEL ESTERO'
            elif 4600 <= num <= 4699: pcia = 'JUJUY'
            elif 4700 <= num <= 4799: pcia = 'CATAMARCA'
            elif 5000 <= num <= 5999: pcia = 'CORDOBA'
            elif 5300 <= num <= 5399: pcia = 'LA RIOJA'
            elif 5400 <= num <= 5499: pcia = 'SAN JUAN'
            elif 5500 <= num <= 5699: pcia = 'MENDOZA'
            elif 5700 <= num <= 5899: pcia = 'SAN LUIS'
            elif 1000 <= num <= 1499: pcia = 'CAPITAL FEDERAL'
            elif (1600 <= num <= 1999) or (2700 <= num <= 2999) or (6000 <= num <= 8199): pcia = 'BUENOS AIRES'
            elif (2000 <= num <= 2699) or (3000 <= num <= 3099): pcia = 'SANTA FE'
            elif 3100 <= num <= 3299: pcia = 'ENTRE RIOS'
            elif 3300 <= num <= 3399: pcia = 'MISIONES'
            elif 3400 <= num <= 3499: pcia = 'CORRIENTES'
            elif 3500 <= num <= 3799: pcia = 'CHACO'
            elif 3600 <= num <= 3699: pcia = 'FORMOSA'
            elif 6300 <= num <= 6399: pcia = 'LA PAMPA'
            elif 8300 <= num <= 8399: pcia = 'NEUQUEN'
            elif 8400 <= num <= 8599: pcia = 'RIO NEGRO'
            elif 9000 <= num <= 9299: pcia = 'CHUBUT'
            elif 9300 <= num <= 9499: pcia = 'SANTA CRUZ'
            elif 9410 <= num <= 9420: pcia = 'TIERRA DEL FUEGO'

            if pcia:
                return Jurisdiccion.objects.filter(nombre__iexact=pcia).first()

    return None


