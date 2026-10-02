import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tesoreria.models import TransaccionBancaria, CuentaBancaria
from contable.models import AsientoLinea
from django.db import transaction

@transaction.atomic
def fix_cuentas():
    transacciones = TransaccionBancaria.objects.filter(numero_operacion__startswith='Migracion')
    print(f"Analizando {transacciones.count()} transacciones migradas.")
    
    arregladas = 0
    no_encontradas = 0
    
    for t in transacciones:
        if not t.asiento_id:
            no_encontradas += 1
            continue
            
        # Buscar la linea del asiento que tenga el importe de la transferencia (o muy similar) en el debe
        lineas = AsientoLinea.objects.filter(asiento__asiento_id=t.asiento_id, debe=t.importe)
        
        cuenta_bancaria_encontrada = None
        for linea in lineas:
            # Buscar si la cuenta contable de esta linea pertenece a alguna cuenta bancaria
            cb = CuentaBancaria.objects.filter(cuenta_contable_id=linea.cuenta_id).first()
            if not cb:
                cb = CuentaBancaria.objects.filter(cuenta_contable_cheques_id=linea.cuenta_id).first()
                
            if cb:
                cuenta_bancaria_encontrada = cb
                break
                
        if cuenta_bancaria_encontrada:
            t.cuenta_bancaria = cuenta_bancaria_encontrada
            t.save(update_fields=['cuenta_bancaria'])
            arregladas += 1
        else:
            no_encontradas += 1
            print(f"No se pudo resolver la cuenta bancaria para la transaccion {t.id} (Asiento {t.asiento_id})")

    print(f"Completado. {arregladas} transacciones corregidas. {no_encontradas} no pudieron asociarse con precisión.")

if __name__ == '__main__':
    fix_cuentas()
