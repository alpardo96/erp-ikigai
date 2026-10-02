import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tesoreria.models import TransaccionBancaria, CuentaBancaria
from contable.models import AsientoLinea
from django.db import transaction

@transaction.atomic
def fix_cuentas_2():
    transacciones = TransaccionBancaria.objects.filter(numero_operacion__startswith='Migracion')
    print(f"Re-analizando {transacciones.count()} transacciones migradas.")
    
    arregladas = 0
    no_encontradas = 0
    
    # Pre-cargar los IDs de cuentas contables vinculadas a cuentas bancarias
    ctas_bancarias_por_ctacontable = {}
    for cb in CuentaBancaria.objects.all():
        if cb.cuenta_contable_id:
            ctas_bancarias_por_ctacontable[cb.cuenta_contable_id] = cb
        if cb.cuenta_contable_cheques_id:
            ctas_bancarias_por_ctacontable[cb.cuenta_contable_cheques_id] = cb
            
    for t in transacciones:
        if not t.asiento_id:
            no_encontradas += 1
            continue
            
        # Buscar TODAS las lineas del asiento que tengan DEBE > 0
        lineas = AsientoLinea.objects.filter(asiento__asiento_id=t.asiento_id, debe__gt=0)
        
        cuenta_bancaria_encontrada = None
        for linea in lineas:
            cb = ctas_bancarias_por_ctacontable.get(linea.cuenta_id)
            if cb:
                cuenta_bancaria_encontrada = cb
                break
                
        if cuenta_bancaria_encontrada:
            # Si era la default, la reasignamos a la correcta que encontramos
            if t.cuenta_bancaria_id != cuenta_bancaria_encontrada.cta_bc_id:
                t.cuenta_bancaria = cuenta_bancaria_encontrada
                t.save(update_fields=['cuenta_bancaria'])
            arregladas += 1
        else:
            no_encontradas += 1

    print(f"Completado. {arregladas} transacciones correctamente asociadas a su banco real. {no_encontradas} quedaron con el banco por defecto.")

if __name__ == '__main__':
    fix_cuentas_2()
