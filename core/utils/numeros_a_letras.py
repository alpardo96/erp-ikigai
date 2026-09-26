"""Conversión de números a palabras en español (moneda / cheques / recibos).

Basado en la lógica estándar argentina y la rutina histórica VFP:
'CIEN MIL DOSCIENTOS TREINTA Y CUATRO CON 50/100.-'
"""
from decimal import Decimal

UNIDADES = {
    0: 'CERO', 1: 'UN', 2: 'DOS', 3: 'TRES', 4: 'CUATRO',
    5: 'CINCO', 6: 'SEIS', 7: 'SIETE', 8: 'OCHO', 9: 'NUEVE',
    10: 'DIEZ', 11: 'ONCE', 12: 'DOCE', 13: 'TRECE', 14: 'CATORCE',
    15: 'QUINCE', 16: 'DIECISEIS', 17: 'DIECISIETE', 18: 'DIECIOCHO', 19: 'DIECINUEVE',
    20: 'VEINTE', 21: 'VEINTIUN', 22: 'VEINTIDOS', 23: 'VEINTITRES', 24: 'VEINTICUATRO',
    25: 'VEINTICINCO', 26: 'VEINTISEIS', 27: 'VEINTISIETE', 28: 'VEINTIOCHO', 29: 'VEINTINUEVE'
}

DECENAS = {
    3: 'TREINTA', 4: 'CUARENTA', 5: 'CINCUENTA', 6: 'SESENTA',
    7: 'SETENTA', 8: 'OCHENTA', 9: 'NOVENTA'
}

CENTENAS = {
    1: 'CIENTO', 2: 'DOSCIENTOS', 3: 'TRESCIENTOS', 4: 'CUATROCIENTOS',
    5: 'QUINIENTOS', 6: 'SEISCIENTOS', 7: 'SETECIENTOS', 8: 'OCHOCIENTOS', 9: 'NOVECIENTOS'
}


def _centenas_a_letras(n: int) -> str:
    """Convierte un número entre 0 y 999 a letras."""
    if n == 0:
        return ""
    if n == 100:
        return "CIEN"
    
    letras = []
    c = n // 100
    resto = n % 100
    
    if c > 0:
        letras.append(CENTENAS[c])
        
    if resto > 0:
        if resto <= 29:
            letras.append(UNIDADES[resto])
        else:
            d = resto // 10
            u = resto % 10
            if u > 0:
                letras.append(f"{DECENAS[d]} Y {UNIDADES[u]}")
            else:
                letras.append(DECENAS[d])
                
    return " ".join(letras)


def numero_a_letras(monto) -> str:
    """
    Convierte un importe numérico a letras con el formato estándar argentino:
    Ejemplo: 1234.50 -> 'UN MIL DOSCIENTOS TREINTA Y CUATRO CON 50/100.-'
    """
    if monto is None or monto == '':
        return ''
    
    try:
        val = Decimal(str(monto))
    except Exception:
        return str(monto)
        
    es_negativo = val < 0
    val = abs(val)
    
    entero = int(val)
    centavos = int(round((val - entero) * 100))
    if centavos >= 100:
        entero += 1
        centavos = 0
        
    if entero == 0:
        texto_entero = "CERO"
    else:
        partes = []
        
        # Millones (hasta 999.999 millones)
        millones = (entero // 1000000) % 1000000
        # Miles
        miles = (entero // 1000) % 1000
        # Unidades
        unidades = entero % 1000
        
        if millones > 0:
            if millones == 1:
                partes.append("UN MILLON")
            else:
                partes.append(f"{_centenas_a_letras(millones)} MILLONES")
                
        if miles > 0:
            if miles == 1:
                partes.append("UN MIL")
            else:
                partes.append(f"{_centenas_a_letras(miles)} MIL")
                
        if unidades > 0:
            partes.append(_centenas_a_letras(unidades))
            
        texto_entero = " ".join(partes)
        
    resultado = f"{texto_entero} CON {centavos:02d}/100.-"
    if es_negativo:
        resultado = f"MENOS {resultado}"
        
    return resultado
