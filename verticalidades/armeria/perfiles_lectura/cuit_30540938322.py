import re

def parse_monto_local(texto):
    if not texto:
        return 0.0
    texto = str(texto).strip().replace('$', '').strip()
    if texto.lower() == 'null': return 0.0
    
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
    Perfil de lectura para Armería ARMAR S.A.S. (CUIT: 30-54093832-2)
    Extrae ítems, porcentajes de descuento, series y cuim.
    """
    items = []
    lineas = texto_completo.split('\n')
    
    num_pattern = r'(\d{1,3}(?:\.\d{3})*(?:,\d+))'
    
    for i, line in enumerate(lineas):
        line = line.strip()
        if not line:
            continue
            
        if line.startswith("Serie:") or line.startswith("DIM:"):
            if items:
                if "subproductos" not in items[-1]:
                    items[-1]["subproductos"] = []
                
                sub_info = {}
                if "Serie:" in line:
                    match_serie = re.search(r'Serie:\s*(\S+)', line)
                    if match_serie: sub_info['serie'] = match_serie.group(1)
                
                if "CUIM:" in line:
                    match_cuim = re.search(r'CUIM:\s*(\S+)', line)
                    if match_cuim: sub_info['cuim'] = match_cuim.group(1)
                    
                if line.startswith("DIM:"):
                    match_dim = re.search(r'DIM:\s*(\S+)', line)
                    if match_dim: sub_info['dim'] = match_dim.group(1)
                
                if sub_info:
                    items[-1]["subproductos"].append(sub_info)
            continue
            
        line_clean = re.sub(r'\s*-\s*null\s*$', '', line).strip()
        line_clean = re.sub(r'\s*null\s*$', '', line_clean).strip()
        
        matches_nums = list(re.finditer(num_pattern, line_clean))
        
        if len(matches_nums) >= 5:
            last_match_end = matches_nums[-1].end()
            if len(line_clean) - last_match_end < 10: 
                valid_consecutive = []
                valid_consecutive.append(matches_nums[-1])
                
                for j in range(len(matches_nums)-2, -1, -1):
                    curr = matches_nums[j]
                    prev = valid_consecutive[-1]
                    between = line_clean[curr.end():prev.start()].strip()
                    if between == "":
                        valid_consecutive.append(curr)
                    else:
                        break
                        
                valid_consecutive.reverse()
                
                if len(valid_consecutive) >= 5:
                    num_block = valid_consecutive[-6:] if len(valid_consecutive) >= 6 else valid_consecutive[-5:]
                    start_idx = num_block[0].start()
                    
                    desc_cod = line_clean[:start_idx].strip()
                    desc_cod = re.sub(r'\s*-\s*(?:null)?$', '', desc_cod).strip()
                    desc_cod = re.sub(r'\s*-\s*$', '', desc_cod).strip()
                    
                    codigo = ""
                    descripcion = desc_cod
                    
                    parts = desc_cod.split()
                    if len(parts) > 1:
                        if re.match(r'^[A-Z0-9\-\.]+$', parts[-1]) and not re.search(r'[a-z]', parts[-1]) and len(parts[-1]) >= 3 and re.search(r'\d', parts[-1]):
                            codigo = parts[-1]
                            descripcion = " ".join(parts[:-1])
                        elif re.match(r'^[A-Z0-9\-\.]+$', parts[0]) and not re.search(r'[a-z]', parts[0]) and len(parts[0]) >= 3 and re.search(r'\d', parts[0]):
                            codigo = parts[0]
                            descripcion = " ".join(parts[1:])
                        elif parts[0] == "Flete":
                            codigo = "FLETE"
                            descripcion = " ".join(parts[1:])
                    
                    ultimos_nums = [m.group(1) for m in num_block]
                    
                    if len(ultimos_nums) == 5:
                        iva = parse_monto_local(ultimos_nums[0])
                        cant = parse_monto_local(ultimos_nums[1])
                        desc_porc = parse_monto_local(ultimos_nums[2])
                        bonif_porc = 0.0
                        p_unit = parse_monto_local(ultimos_nums[3])
                        total = parse_monto_local(ultimos_nums[4])
                    else:
                        iva = parse_monto_local(ultimos_nums[0])
                        cant = parse_monto_local(ultimos_nums[1])
                        desc_porc = parse_monto_local(ultimos_nums[2])
                        bonif_porc = parse_monto_local(ultimos_nums[3])
                        p_unit = parse_monto_local(ultimos_nums[4])
                        total = parse_monto_local(ultimos_nums[5])
                    
                    if total > 0 or p_unit > 0:
                        items.append({
                            'codigo': codigo,
                            'descripcion': descripcion,
                            'cantidad': cant,
                            'precio_unitario': p_unit,
                            'descuento_porc': desc_porc,
                            'bonificacion_porc': bonif_porc,
                            'iva_porc': iva,
                            'total': total,
                            'subproductos': []
                        })
                    
    punto = ""
    numero = ""
    nro_match = re.search(r'(\d{4,5})\s*-\s*(\d{8})', texto_completo)
    if nro_match:
        punto = nro_match.group(1).lstrip('0') or '0'
        numero = nro_match.group(2).lstrip('0') or '0'
        
    neto = 0.0
    iva = 0.0
    total = 0.0
    
    for line in lineas:
        if re.search(r'\bSubtotal:', line, re.IGNORECASE):
            montos = re.findall(r'\$\s*([\d\.\,]+)', line)
            if montos:
                neto = parse_monto_local(montos[-1])
        elif re.search(r'\bIVA:', line, re.IGNORECASE):
            montos = re.findall(r'\$\s*([\d\.\,]+)', line)
            if montos:
                iva = parse_monto_local(montos[-1])
        elif re.search(r'\bTOTAL:', line, re.IGNORECASE):
            montos = re.findall(r'\$\s*([\d\.\,]+)', line)
            if montos:
                total = parse_monto_local(montos[-1])
    
    overrides = {
        'punto': punto,
        'numero': numero,
        'neto': neto,
        'iva': iva,
        'total': total,
    }
    
    return {
        'items': items,
        'cabecera_overrides': overrides
    }
