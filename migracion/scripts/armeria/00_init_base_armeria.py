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
    print("=== FASE 0: CREACIÓN DE ENTORNO BASE PARA ARMERÍA ===")
    
    # 1. Superusuario
    user, created_user = User.objects.get_or_create(
        username='ikigai',
        defaults={
            'email': 'admin@ikigai.com',
            'is_staff': True,
            'is_superuser': True
        }
    )
    if created_user:
        user.set_password('ortiz')
        user.save()
        print("OK: Superusuario 'ikigai' creado.")
    else:
        print("OK: Superusuario 'ikigai' verificado.")

    # 2. Empresa "Armería"
    empresa, created_emp = Empresa.objects.get_or_create(
        id=1,
        defaults={
            'nombre': 'Armería',
            'cuit': '30718098226',
            'condicion_iibb': 'CM',
            'entorno_afip': 'PROD',
            'creado_por': user,
            'fecha_creacion': date.today(),
            'fecha_modificacion': date.today()
        }
    )
    print(f"OK: Empresa 'Armería' (ID: {empresa.id})")

    # 3. Sucursales
    # Sucursal 1: Casa Central (Punto de Venta: 4)
    # Sucursal 2: Yerba Buena (Punto de Venta: 6)
    # Sucursal 3: DSK (Punto de Venta: 0 / DSK)
    sucursal1, _ = Sucursal.objects.get_or_create(
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
    
    sucursal2, _ = Sucursal.objects.get_or_create(
        id=2,
        empresa=empresa,
        defaults={
            'nombre': 'Yerba Buena',
            'punto': 6,
            'creado_por': user,
            'fecha_creacion': date.today(),
            'fecha_modificacion': date.today()
        }
    )
    
    sucursal3, _ = Sucursal.objects.get_or_create(
        id=3,
        empresa=empresa,
        defaults={
            'nombre': 'DSK',
            'punto': 0,
            'creado_por': user,
            'fecha_creacion': date.today(),
            'fecha_modificacion': date.today()
        }
    )
    print(f"OK: Sucursales configuradas -> 1: {sucursal1.nombre}, 2: {sucursal2.nombre}, 3: {sucursal3.nombre}")

    # 4. Ejercicio 2026
    ejercicio, _ = Ejercicio.objects.get_or_create(
        id=1,
        empresa=empresa,
        defaults={
            'ejercicio': 'Ejercicio 2026',
            'inicio': date(2026, 1, 1),
            'cierre': date(2026, 12, 31)
        }
    )
    print(f"OK: Ejercicio fiscal 2026 activo (ID: {ejercicio.id})")

    # 5. Cajas de Tesorería por Sucursal
    caja_central, _ = Caja.objects.get_or_create(
        id=1,
        empresa=empresa,
        defaults={
            'sucursal': sucursal1,
            'nombre': 'Caja Casa Central',
            'tipo': 'T' 
        }
    )
    caja_yb, _ = Caja.objects.get_or_create(
        id=2,
        empresa=empresa,
        defaults={
            'sucursal': sucursal2,
            'nombre': 'Caja Yerba Buena',
            'tipo': 'T'
        }
    )
    caja_dsk, _ = Caja.objects.get_or_create(
        id=3,
        empresa=empresa,
        defaults={
            'sucursal': sucursal3,
            'nombre': 'Caja DSK',
            'tipo': 'T'
        }
    )
    print("OK: Cajas de Tesorería configuradas para las 3 sucursales.")
    print("Fase 0 completada con éxito.")

if __name__ == '__main__':
    init_base()
