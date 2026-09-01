import os
import sys
import django
from datetime import date

# Configurar el entorno de Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from empresas.models import Empresa, Sucursal, Ejercicio
from tesoreria.models import Caja

User = get_user_model()

def init_base():
    print("Iniciando creación de Entorno Base (Fase 0)...")
    
    # 1. Superusuario
    try:
        if not User.objects.filter(username='Ikigai').exists():
            User.objects.create_superuser('Ikigai', 'admin@ikigai.com', 'ortiz')
            print("OK Superusuario 'Ikigai' creado.")
        else:
            print("OK Superusuario 'Ikigai' ya existe.")
    except Exception as e:
        print(f"Error creando usuario: {e}")
        
    user = User.objects.get(username='Ikigai')

    # 2. Empresa "Lopez Rios"
    empresa, created = Empresa.objects.get_or_create(
        id=1,
        defaults={
            'nombre': 'Lopez Rios',
            'cuit': '30111111111', # Ajustado a 11 chars
            'condicion_iibb': 'CM',
            'entorno_afip': 'HOMO',
            'creado_por': user,
            'fecha_creacion': date.today(),
            'fecha_modificacion': date.today()
        }
    )
    if created:
        print("OK Empresa 'Lopez Rios' creada con id=1.")
    else:
        print("OK Empresa 'Lopez Rios' ya existe (id=1).")

    # 3. Sucursal "Casa Central"
    sucursal, created = Sucursal.objects.get_or_create(
        id=1,
        empresa=empresa,
        defaults={
            'nombre': 'Casa Central',
            'punto': 1,
            'creado_por': user,
            'fecha_creacion': date.today(),
            'fecha_modificacion': date.today()
        }
    )
    if created:
        print("OK Sucursal 'Casa Central' creada con id=1.")
    else:
        print("OK Sucursal 'Casa Central' ya existe (id=1).")

    # 4. Ejercicio 2027 (01/06/2026 - 31/05/2027)
    ejercicio, created = Ejercicio.objects.get_or_create(
        id=1,
        empresa=empresa,
        defaults={
            'ejercicio': '2027',
            'inicio': date(2026, 6, 1),
            'cierre': date(2027, 5, 31)
        }
    )
    if created:
        print("OK Ejercicio 2027 creado con id=1.")
    else:
        print("OK Ejercicio 2027 ya existe (id=1).")

    # 5. Caja de Tesorería (Tipo 'T')
    caja, created = Caja.objects.get_or_create(
        id=1,
        empresa=empresa,
        defaults={
            'sucursal': sucursal,
            'nombre': 'Caja Principal (Migración)',
            'tipo': 'T' # Suponiendo que el field tipo acepta 'T' o que no hay restricción
        }
    )
    if created:
        print("OK Caja Principal creada con id=1.")
    else:
        print("OK Caja Principal ya existe (id=1).")
        
    print("Fase 0 completada con éxito.")

if __name__ == '__main__':
    init_base()
