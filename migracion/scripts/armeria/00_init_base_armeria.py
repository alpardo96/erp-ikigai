import os
import sys
import django
from datetime import date

# Configurar el entorno de Django
import pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from empresas.models import Empresa, Sucursal, Ejercicio
from tesoreria.models import Caja

User = get_user_model()

def init_base():
    print("Iniciando creación de Entorno Base (Fase 0) para Armería...")
    
    # 1. Superusuario
    try:
        if not User.objects.filter(username='ikigai').exists():
            User.objects.create_superuser('ikigai', 'admin@ikigai.com', 'ortiz')
            print("OK Superusuario 'ikigai' creado.")
        else:
            print("OK Superusuario 'ikigai' ya existe.")
    except Exception as e:
        print(f"Error creando usuario: {e}")
        
    user = User.objects.get(username='ikigai')

    # 2. Empresa "Armeria"
    empresa, created = Empresa.objects.get_or_create(
        id=1,
        defaults={
            'nombre': 'Armería',
            'cuit': '30000000000', # Por defecto
            'condicion_iibb': 'CM',
            'entorno_afip': 'HOMO',
            'creado_por': user,
            'fecha_creacion': date.today(),
            'fecha_modificacion': date.today()
        }
    )
    if created:
        print("OK Empresa 'Armería' creada con id=1.")
    else:
        print("OK Empresa 'Armería' ya existe (id=1).")

    # 3. Sucursales (Casa Central y Sucursal)
    sucursal1, created1 = Sucursal.objects.get_or_create(
        id=1,
        empresa=empresa,
        defaults={
            'nombre': 'Casa Central',
            'punto': 4,
            'creado_por': user,
            'fecha_creacion': date.today(),
            'fecha_modificacion': date.today()
        }
    )
    
    sucursal2, created2 = Sucursal.objects.get_or_create(
        id=2,
        empresa=empresa,
        defaults={
            'nombre': 'Sucursal',
            'punto': 6,
            'creado_por': user,
            'fecha_creacion': date.today(),
            'fecha_modificacion': date.today()
        }
    )
    
    if created1: print("OK Sucursal 'Casa Central' (PV: 4) creada con id=1.")
    if created2: print("OK Sucursal 'Sucursal' (PV: 6) creada con id=2.")

    # 4. Ejercicio (Amplio para capturar todo el historial)
    ejercicio, created = Ejercicio.objects.get_or_create(
        id=1,
        empresa=empresa,
        defaults={
            'ejercicio': 'Ejercicio 2026',
            'inicio': date(2026, 1, 1),
            'cierre': date(2026, 12, 31)
        }
    )
    if created:
        print("OK Ejercicio 2026 creado con id=1.")
    else:
        print("OK Ejercicio 2026 ya existe (id=1).")

    # 5. Cajas
    caja_central, created_c1 = Caja.objects.get_or_create(
        id=1,
        empresa=empresa,
        defaults={
            'sucursal': sucursal1,
            'nombre': 'Caja Casa Central',
            'tipo': 'T' 
        }
    )
    caja_suc, created_c2 = Caja.objects.get_or_create(
        id=2,
        empresa=empresa,
        defaults={
            'sucursal': sucursal2,
            'nombre': 'Caja Sucursal',
            'tipo': 'T'
        }
    )
    if created_c1: print("OK Caja Casa Central creada con id=1.")
    if created_c2: print("OK Caja Sucursal creada con id=2.")
        
    print("Fase 0 completada con éxito.")

if __name__ == '__main__':
    init_base()
