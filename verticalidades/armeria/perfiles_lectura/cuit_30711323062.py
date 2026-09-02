import re

def parse_monto_local(texto):
    if not texto:
        return 0.0
    texto = texto.strip().replace('$', '').strip()
    last_comma = texto.rfind(',')
    last_dot = texto.rfind('.')
    if last_comma > last_dot:
        texto = texto.replace('.', '')
        texto = texto.replace(',', '.')
    elif last_dot > last_comma and last_comma != -1:
        texto = texto.replace(',', '')
    else:
        if last_comma != -1:
            if len(texto) - last_comma - 1 <= 2:
                texto = texto.replace(',', '.')
            else:
                texto = texto.replace(',', '')
        elif last_dot != -1:
            if len(texto) - last_dot - 1 == 2:
                pass
            else:
                texto = texto.replace('.', '')
    try:
        return float(texto)
    except:
        return 0.0

def procesar_perfil(texto_completo):
    """
    Extrae los ítems de la factura del proveedor con CUIT: 30-71132306-2.
    Preparado para lectura de PDF con sort=True.
    """
    items = []
    
    # Patrón para layout sort=True: Cantidad | Articulo | Descripcion 1 | Precio | Total \n Descripcion 2
    patron_item = r'^[\s]*([\d\,\.]+)[\s]+(\d+)[\s]+(.*?)[\s]+([\d\,\.]+)[\s]+([\d\,\.]+)[\s]*\n[\s]*(.*?)[\s]*\n'
    matches = re.findall(patron_item, texto_completo, re.MULTILINE)
    
    for match in matches:
        cantidad_raw = match[0].strip()
        codigo = match[1].strip()
        descripcion = match[2].strip()
        precio_uni_raw = match[3].strip()
        total_raw = match[4].strip()
        codigo_alt_raw = match[5].strip()
        
        # Extraemos solo la última palabra del código alternativo (ej: SCOL-67)
        codigo_alt = codigo_alt_raw.split()[-1] if codigo_alt_raw else ""
        
        cantidad = float(cantidad_raw.replace('.', '').replace(',', '.'))
        precio_uni = parse_monto_local(precio_uni_raw)
        total = parse_monto_local(total_raw)
        
        desc_completa = f"{descripcion} {codigo_alt_raw}".strip()
        
        items.append({
            'codigo': codigo,
            'codigo_alt': codigo_alt,
            'cantidad': cantidad,
            'descripcion': desc_completa,
            'precio_unitario': precio_uni,
            'total': total,
            'iva_porc': 21.0
        })

    punto = ""
    numero = ""
    nro_match = re.search(r'N[°ºo\.\s]*(\d{4,5})\s*-\s*(\d{6,8})', texto_completo)
    if nro_match:
        punto = nro_match.group(1).lstrip('0') or '0'
        numero = nro_match.group(2).lstrip('0') or '0'

    neto = 0.0
    iva = 0.0
    total_fac = 0.0
    descuento = 0.0
    
    # El proveedor imprime el subtotal bruto y luego el neto descontado. 
    subtotal = 0.0
    neto = 0.0
    neto_matches = re.findall(r'SUBTOTAL\s*[:\-]*\s*([\d\.\,]{4,})', texto_completo, re.IGNORECASE)
    if len(neto_matches) >= 2:
        subtotal = parse_monto_local(neto_matches[0])
        neto = parse_monto_local(neto_matches[1])
    elif len(neto_matches) == 1:
        subtotal = parse_monto_local(neto_matches[0])
        neto = subtotal

    dto_match = re.search(r'DTO\s*:\s*%\s*([\d\.\,]+)\s+([\d\.\,]{4,})', texto_completo, re.IGNORECASE)
    if dto_match: 
        descuento = parse_monto_local(dto_match.group(2))

    iva_match = re.search(r'IVA\s*21\s*%\s*[:\-]*\s*([\d\.\,]{4,})', texto_completo, re.IGNORECASE)
    if iva_match: 
        iva = parse_monto_local(iva_match.group(1))

    total_match = re.search(r'\bTOTAL\s*[:\-]*\s*([\d\.\,]{4,})', texto_completo, re.IGNORECASE)
    if total_match: 
        total_fac = parse_monto_local(total_match.group(1))
    
    if not neto and items:
        neto = sum(it['precio_unitario'] * it['cantidad'] for it in items)
    if not iva and neto:
        iva = neto * 0.21
    if not total_fac and neto:
        total_fac = neto + iva
        
    overrides = {
        'punto': punto,
        'numero': numero,
        'moneda': 'PES',
        'subtotal': subtotal,
        'neto': neto,
        'iva': iva,
        'descuento': descuento,
        'total': total_fac,
    }

    return {
        'items': items,
        'cabecera_overrides': overrides
    }
