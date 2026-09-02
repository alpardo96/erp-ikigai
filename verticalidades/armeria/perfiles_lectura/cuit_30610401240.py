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
    Extrae los ítems de la factura de BOWIE S.R.L. (CUIT: 30-61040124-0).
    Retorna una lista de diccionarios con los detalles y la cabecera_overrides.
    """
    items = []
    # La factura de Bowie tiene líneas de productos con este formato:
    # Codigo Cantidad Descripción $ Unitario Total
    # Ej: 20831 2.000 BALAS CCI C.22LR SUB-SONIC M.56/1050 PH 40G(X100) 0,23 460,00
    
    patron_item = r'^\s*(\d+)\s+([\d\.]+)\s+(.*?)\s+([\d\,]+)\s+([\d\,]+)\s*$'
    
    matches = re.findall(patron_item, texto_completo, re.MULTILINE)
    for match in matches:
        codigo = match[0].strip()
        cantidad_raw = match[1].strip()
        descripcion = match[2].strip()
        precio_uni_raw = match[3].strip()
        total_raw = match[4].strip()
        
        # Limpiar cantidad (ej: 2.000 -> 2000.0)
        cantidad = float(cantidad_raw.replace('.', '').replace(',', '.'))
        
        # Limpiar precios
        precio_uni = parse_monto_local(precio_uni_raw)
        total = parse_monto_local(total_raw)
        
        items.append({
            'codigo': codigo,
            'cantidad': cantidad,
            'descripcion': descripcion,
            'precio_unitario': precio_uni,
            'total': total,
            'iva_porc': 21.0
        })
        
    punto = ""
    numero = ""
    # Factura Bowie suele tener "00013 - 00150995"
    nro_match = re.search(r'(\d{4,5})\s*-\s*(\d{8})', texto_completo)
    if nro_match:
        punto = nro_match.group(1).lstrip('0') or '0'
        numero = nro_match.group(2).lstrip('0') or '0'

    neto = 0.0
    iva = 0.0
    total = 0.0
    iibb = 0.0
    cotizacion = 1.0
    
    # Intentar capturar importes fijos (Subtotal, IVA, Total)
    neto_match = re.search(r'(?:Subtotal|Neto Gravado)[^\d]*([\d\.\,]{4,})', texto_completo, re.IGNORECASE)
    if neto_match: neto = parse_monto_local(neto_match.group(1))
    
    iva_match = re.search(r'(?:I\.V\.A\.|IVA).*?21(?:,00)?\s*%\s*([\d\.\,]{4,})', texto_completo, re.IGNORECASE)
    if not iva_match:
        iva_match = re.search(r'(?:I\.V\.A\.|IVA)[^\d]*([\d\.\,]{4,})', texto_completo, re.IGNORECASE)
    if iva_match: iva = parse_monto_local(iva_match.group(1))
    
    total_match = re.search(r'(?:Total\s+Factura|Total\s+u\$s)\s*([\d\.\,]{4,})', texto_completo, re.IGNORECASE)
    if total_match: total = parse_monto_local(total_match.group(1))
    
    iibb_match = re.search(r'(?:Reg[íi]menes Especiales|RG86).*?([\d\.\,]{4,})', texto_completo, re.IGNORECASE)
    if iibb_match: iibb = parse_monto_local(iibb_match.group(1))
    
    cot_match = re.search(r'(?:Tipo de Cambio:\s*)([\d\.\,]{4,})', texto_completo, re.IGNORECASE)
    if cot_match: cotizacion = parse_monto_local(cot_match.group(1))
    
    # Tipo de Comprobante
    tipo_comprobante_codigo = '001'  # Default a Factura A
    if re.search(r'NOTA DE CREDITO', texto_completo, re.IGNORECASE):
        tipo_comprobante_codigo = '003'  # Nota de Credito A 
    
    # Si falta alguno, lo deducimos de la suma de los items (BOWIE tiene los items netos)
    if not neto and items:
        neto = sum(it['precio_unitario'] * it['cantidad'] for it in items)
    if not iva and neto:
        iva = neto * 0.21
    if not total and neto:
        total = neto + iva + iibb
        
    overrides = {
        'punto': punto,
        'numero': numero,
        'moneda': 'DOL',
        'neto': neto,
        'iva': iva,
        'total': total,
        'p_iibb': iibb,
        'cotizacion': cotizacion,
        'tipo_comprobante_codigo': tipo_comprobante_codigo
    }

    return {
        'items': items,
        'cabecera_overrides': overrides
    }
