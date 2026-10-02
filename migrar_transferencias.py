import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tesoreria.models import ValorTerceros, TransaccionBancaria, CuentaBancaria
from django.db import transaction
from django.utils import timezone

@transaction.atomic
def migrar():
    valores = ValorTerceros.objects.filter(numero_cheque='0')
    count = valores.count()
    print(f"Encontrados {count} registros a migrar.")
    
    if count == 0:
        return

    # Obtenemos la primera cuenta bancaria para asignar (PATAGONIA S.A.)
    cuenta_default = CuentaBancaria.objects.first()

    creados = 0
    for v in valores:
        TransaccionBancaria.objects.create(
            empresa=v.empresa,
            tipo_transaccion='TR', # Transferencia Recibida
            movimiento_detalle=v.movimiento_detalle,
            cuenta_bancaria=cuenta_default,
            numero_operacion=f"Migracion {v.id}",
            importe=v.importe,
            cuit_contraparte=v.cuit_firmante,
            fecha_operacion=v.fecha_recepcion or v.fecha_emision or timezone.localdate(),
            estado='D', # Acreditada
            asiento_id=v.asiento_recepcion_id
        )
        creados += 1
    
    valores.delete()
    print(f"Se crearon {creados} Transacciones Bancarias y se eliminaron los Valores de Terceros.")

if __name__ == '__main__':
    migrar()
