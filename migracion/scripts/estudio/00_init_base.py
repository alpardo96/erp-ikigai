import os
import sys
import django
from datetime import date
from decimal import Decimal

# Configurar el entorno de Django
import pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from empresas.models import Empresa, Sucursal, Ejercicio
from tesoreria.models import Caja
from productos.models import Producto

User = get_user_model()

def init_base():
    print("Iniciando creación de Entorno Base (Fase 0 - Estudio)...")
    
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

    # 2. Empresa "Lopez Rios y Asoc SA"
    empresa, created = Empresa.objects.get_or_create(
        id=1,
        defaults={
            'nombre': 'Lopez Rios y Asoc SA',
            'cuit': '30708395206',
            'condicion_iibb': 'CM',
            'entorno_afip': 'HOMO',
            'creado_por': user,
            'fecha_creacion': date.today(),
            'fecha_modificacion': date.today()
        }
    )
    if not created:
        empresa.nombre = 'Lopez Rios y Asoc SA'
        empresa.cuit = '30708395206'
        empresa.condicion_iibb = 'CM'
        empresa.save()
        print("OK Empresa 'Lopez Rios y Asoc SA' asegurada (id=1).")
    else:
        print("OK Empresa 'Lopez Rios y Asoc SA' creada con id=1.")

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

    # 4. Ejercicios Contables
    # Ejercicio 2026 (01/06/2025 - 31/05/2026)
    ej_2026, created = Ejercicio.objects.get_or_create(
        id=1,
        empresa=empresa,
        defaults={
            'ejercicio': 'LOPEZ RIOS & ASOC. SA - Ejercicio 2026',
            'inicio': date(2025, 6, 1),
            'cierre': date(2026, 5, 31)
        }
    )
    if created:
        print("OK Ejercicio 2026 creado con id=1.")
    else:
        print("OK Ejercicio 2026 ya existe (id=1).")

    # Ejercicio 2027 (01/06/2026 - 31/05/2027)
    ej_2027, created = Ejercicio.objects.get_or_create(
        id=2,
        empresa=empresa,
        defaults={
            'ejercicio': 'LOPEZ RIOS Y ASOC. SA - Ejercicio 2027',
            'inicio': date(2026, 6, 1),
            'cierre': date(2027, 5, 31)
        }
    )
    if created:
        print("OK Ejercicio 2027 creado con id=2.")
    else:
        print("OK Ejercicio 2027 ya existe (id=2).")

    # 5. Caja de Tesorería (Tipo 'T')
    caja, created = Caja.objects.get_or_create(
        id=1,
        empresa=empresa,
        defaults={
            'sucursal': sucursal,
            'nombre': 'Caja Principal (Migración)',
            'tipo': 'T'
        }
    )
    if created:
        print("OK Caja Principal creada con id=1.")
    else:
        print("OK Caja Principal ya existe (id=1).")

    # 6. Producto Default (Honorarios / Servicios Contables)
    prod, created = Producto.objects.get_or_create(
        id=1,
        defaults={
            'empresa': empresa,
            'detalle': 'Honorarios / Servicios Contables',
            'alic_iva': Decimal('21.00'),
            'moneda': 'PES',
            'creado_por': user,
            'activo': True
        }
    )
    if created:
        print("OK Producto Default 'Honorarios / Servicios Contables' creado (id=1).")
    else:
        print("OK Producto Default 'Honorarios / Servicios Contables' ya existe (id=1).")
        
    print("Fase 0 completada con éxito.")

if __name__ == '__main__':
    init_base()
