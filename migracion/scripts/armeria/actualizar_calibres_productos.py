import os
import sys
import re
import pathlib
import django

# Configurar el entorno de Django
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from empresas.models import Empresa
from productos.models import Producto, Rubro

MARCAS_CONOCIDAS = {
    'ORBEA', 'REMING', 'REMINGTON', 'ARMUSA', 'RD', 'FM', 'FIOCCHI', 'FALCO', 'HORNADY',
    'MAGTECH', 'MARLIN', 'ROSSI', 'RUGER', 'SAVAGE', 'LEGEND', 'KRAL', 'WEATH', 'ZASTAVA',
    'TAURUS', 'BERSA', 'GLOCK', 'CZ', 'BERETTA', 'BENELLI', 'BROWNING', 'WINCHESTER',
    'SMITH', 'WESSON', 'NORINCO', 'CANIK', 'STEYR', 'WALTHER', 'SIG', 'SAUER', 'HATSAN',
    'H&K', 'HK', 'BOITO', 'HUGAN', 'YILDIZ', 'MAVERICK', 'MOSSBERG', 'BAIKAL', 'DILLON',
    'LYMAN', 'IMAZ', 'STOP', 'POWER'
}

def extract_exact_calibre(detalle):
    """
    Deduce y extrae el calibre del producto a partir de su detalle
    para rubros específicos de Armería y Municiones.
    """
    if not detalle:
        return ""
    d = detalle.upper().strip()

    # 1. Detección con prefijo explícito (C., CAL., CALIBRE, C/)
    m = re.search(r'\b(?:CALIBRE|CAL\.|CAL|C\.|C/|C:)\s*([0-9A-Z\.\-\/\&]+(?:\s+[0-9A-Z\.\-\/\&]+)?)', d)
    if m:
        raw_val = m.group(1).strip()
        tokens = raw_val.split()
        first_token = tokens[0].strip(' .,-/:')
        second_token = tokens[1].strip(' .,-/:') if len(tokens) > 1 else ''
        
        valid_suffixes = {'LR', 'MG', 'MAG', 'MAGNUM', 'HMR', 'ACP', 'SPL', 'SP', 'WIN', 'REM', 'GOV', 'S&W', 'SW', 'WM', 'CREEDMOOR', 'MM', 'X19', '06', '70', '76'}
        
        if second_token and (second_token in valid_suffixes or (first_token in {'30', '45', '12', '16', '20', '28', '36'} and second_token in {'06', '70', '76', 'GOV', 'AT', 'PG', 'SLUG', 'POSTA', 'MAG', '410'})):
            if second_token in {'AT', 'PG', 'SLUG', 'POSTA'}:
                cal = first_token
            else:
                cal = f"{first_token} {second_token}"
        else:
            cal = first_token
            
        if cal in MARCAS_CONOCIDAS or cal in {'POSTA', 'CART', 'MUN', 'BALIN', 'PLOMO', 'TIRO', 'CAZA'}:
            cal = ""
            
        if cal:
            cal = cal.replace('CAL.', '').replace('CAL', '').strip()
            return f"C.{cal}"[:30]

    # 2. Aire comprimido / MUNI AA (4.5, 5.5, 6.35, etc.)
    m_aa = re.search(r'\b(4\.5|5\.5|6\.35|7\.62)\s*(?:MM)?\b', d)
    if m_aa and any(k in d for k in ['AA', 'BALIN', 'CO2', 'RESORTE', 'NITRO', 'PCP', 'AIR', 'G-MAGNUM', 'PRO-MAGNUM']):
        return f"C.{m_aa.group(1)} MM"

    # 3. Menciones directas de calibres conocidos
    direct_calibres = [
        (r'9\s*X\s*19', '9X19'), (r'9\s*MM', '9MM'), (r'40\s*S&W', '40 S&W'), (r'40\s*SW', '40 SW'),
        (r'45\s*ACP', '45 ACP'), (r'380\s*ACP', '380 ACP'), (r'38\s*SPL', '38 SPL'), (r'38\s*SP', '38 SP'),
        (r'357\s*MAG(?:NUM)?', '357 MAG'), (r'357\s*MG', '357 MG'), (r'44\s*MAG(?:NUM)?', '44 MAG'),
        (r'44\s*MG', '44 MG'), (r'44-40', '44-40'), (r'30-06', '30-06'), (r'30\s*06', '30-06'),
        (r'30-30', '30-30'), (r'308\s*WIN', '308 WIN'), (r'308', '308'), (r'223\s*REM', '223 REM'),
        (r'223', '223'), (r'22\s*LR', '22 LR'), (r'22\s*MAG', '22 MAG'), (r'22\s*MG', '22 MG'),
        (r'17\s*HMR', '17 HMR'), (r'12/70', '12/70'), (r'12/76', '12/76'), (r'16/70', '16/70'),
        (r'20/70', '20/70'), (r'28/70', '28/70'), (r'36/70', '36/70'), (r'410', '410')
    ]
    for pattern, name in direct_calibres:
        if re.search(r'\b' + pattern + r'\b', d):
            return f"C.{name}"

    return ""

def run():
    print("=== ACTUALIZACIÓN DE CALIBRES EN UNIDAD_VENTA (RUBROS QUE INICIAN CON ARMA O MUNI) ===")
    
    empresa = Empresa.objects.get(id=1)
    from django.db.models import Q
    prods = Producto.objects.filter(empresa=empresa).filter(
        Q(rubro__detalle__startswith='ARMA') | Q(rubro__detalle__startswith='MUNI')
    )
    total = prods.count()
    print(f"Total productos en rubros que inician con ARMA o MUNI: {total}")
    
    actualizados = 0
    sin_calibre = 0
    
    for p in prods:
        cal = extract_exact_calibre(p.detalle)
        if cal:
            p.unidad_venta = cal
            actualizados += 1
        else:
            p.unidad_venta = 'UNIDAD'
            sin_calibre += 1
        p.save(update_fields=['unidad_venta'])
        
    print(f"\nResultado de la actualización:")
    print(f"  - Productos con calibre asignado: {actualizados} ({actualizados/total*100:.1f}%)")
    print(f"  - Productos sin calibre (pólvoras, fulminantes, prensas, etc.): {sin_calibre} ({sin_calibre/total*100:.1f}%)")
    print("\nOK: Proceso finalizado con éxito.")

if __name__ == '__main__':
    run()
